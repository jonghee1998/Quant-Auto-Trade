"""예측 기반 전략(실험실 엔진의 Strategy 규칙을 따른다: weights(as_of, history) → 다음 거래일 체결).

ForecastRanker: 종목(ETF)들의 앞으로 h거래일 S&P 대비 초과수익 '순위'를 예측해 상위 top개를 산다.
MarketTimer   : 앞으로 h거래일 S&P가 현금(SHY)보다 나을 확률을 예측해 주식 비중을 정한다.

누수 방지:
- 특성은 과거만 보는 계산(features.py)으로 미리 만들어 두되, as_of 행만 꺼낸다.
- 학습은 training_dates()로 '라벨 끝 + embargo ≤ as_of'인 날만, 일정 간격으로.
- 모델(결측 대체·스케일 포함)은 그 학습 표본으로만 fit, refit_months마다 다시.
- 예측은 기록해 두었다가 끝나고 실제 결과와 비교(IC) — 평가용이며 전략 결정에 안 쓴다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import (MACRO_FEATS, NEWS_FEATS, PRICE_FEATS, SWING_FEATS, forward_return, price_panel, stack,
                       training_dates)
from .models import make, make_clf

INTERACT = ["vix", "baa_ch21", "curve_2y", "dgs10_ch21", "usd_ch63", "oil_ch63", "nfci", "real10"]


def _feature_sets(kind: str) -> tuple[list[str], list[str]]:
    """(가격 특성, 지표 특성). P=가격, PM=+지표, PMN=+뉴스 기반 지수, S=스윙(단기), SM=스윙+지표."""
    macro_no_news = [m for m in MACRO_FEATS if m not in NEWS_FEATS]
    return {
        "P": (PRICE_FEATS, []),
        "PM": (PRICE_FEATS, macro_no_news),
        "PMN": (PRICE_FEATS, MACRO_FEATS),
        "S": (SWING_FEATS, []),
        "SM": (SWING_FEATS, ["vix", "vix_term", "baa_ch21", "dgs10_ch21", "usd_ch63", "epu_z", "emv_z"]),
    }[kind]


class ForecastRanker:
    def __init__(self, name: str, px: pd.DataFrame, macro_f: pd.DataFrame, universe: list[str], *, h: int = 21,
                 feats: str = "P", model: str = "ridge", top: int = 3, refit_months: int = 3, train_years: float | None = None,
                 regime: str | None = None, timer: "MarketTimer | None" = None, defensive: str | None = "SHY",
                 weighting: str = "equal", vol_target: float | None = None, step: int = 5, min_hist: int = 252):
        self.name, self.h, self.model_name, self.top = name, h, model, top
        self.refit_months, self.train_years, self.step, self.min_hist = refit_months, train_years, step, min_hist
        self.regime, self.timer, self.defensive, self.weighting, self.vol_target = regime, timer, defensive, weighting, vol_target
        self.universe = [t for t in universe if t in px]
        self.px = px
        pf, mf = _feature_sets(feats)
        panel = price_panel(px)
        self.vol63 = panel["vol63"]
        idx = px.index
        X = stack({k: panel[k] for k in pf}, idx, self.universe)
        if mf:
            m = macro_f.reindex(idx)[mf]
            X = _join_macro(X, m)
            # 지표 × 시장 민감도(베타) 상호작용: 선형 모델도 '금리가 오르면 베타 높은 종목이 약하다' 같은 걸 배우게.
            # 지표는 과거 252일 평균·표준편차로만 표준화(전체 기간 통계 금지)
            mz = (m - m.rolling(252, min_periods=126).mean()) / m.rolling(252, min_periods=126).std()
            dates = X.index.get_level_values(0)
            for c in [c for c in INTERACT if c in mf and "beta63" in X]:
                X[f"{c}_x_beta"] = mz[c].reindex(dates).fillna(0).to_numpy() * (X["beta63"].fillna(0.5) - 0.5).to_numpy()
        self.X = X
        fwd = forward_return(px[self.universe + (["SPY"] if "SPY" not in self.universe else [])], h)
        ex = fwd[self.universe].sub(fwd["SPY"], axis=0)
        self.y = ex.rank(axis=1, pct=True).stack(future_stack=True)  # 라벨(학습 전용)
        self._model, self._fit_key = None, None
        self.preds: list[tuple[pd.Timestamp, pd.Series]] = []
        self.fwd_excess = ex  # 평가(IC)용

    def _available(self, as_of: pd.Timestamp, history: pd.DataFrame) -> list[str]:
        h = history[self.universe]
        ok = h.notna().sum() >= self.min_hist
        return [t for t in self.universe if ok[t] and pd.notna(h[t].iloc[-1])]

    def _fit(self, as_of: pd.Timestamp) -> None:
        key = (as_of.year, (as_of.month - 1) // self.refit_months)
        if key == self._fit_key and self._model is not None:
            return
        dates = training_dates(self.px.index, as_of, self.h, step=self.step, years=self.train_years)
        if len(dates) < 50:
            self._model = None
            return
        rows = self.X.loc[self.X.index.get_level_values(0).isin(dates)]
        assert rows.index.get_level_values(0).max() <= as_of, "미래 날짜가 학습에 들어감"
        self._cols = _usable(rows)  # 학습 창에서 절반 이상 값이 있는 특성만(예: 아직 없던 지표는 뺀다)
        rows = rows[self._cols]
        y = self.y.reindex(rows.index)
        keep = y.notna() & rows.notna().mean(axis=1).ge(0.6)
        if keep.sum() < 200:
            self._model = None
            return
        self._model = make(self.model_name).fit(rows[keep].to_numpy(dtype=float), y[keep].to_numpy())
        self._fit_key = key

    def _exposure(self, as_of: pd.Timestamp, history: pd.DataFrame) -> float:
        """주식 쪽 비중(0~1). 나머지는 방어 자산(없으면 현금)."""
        if self.regime == "trend":
            s = history["SPY"].dropna()
            return 1.0 if len(s) < 200 or s.iloc[-1] >= s.iloc[-200:].mean() else 0.0
        if self.regime == "timer" and self.timer is not None:
            return self.timer.exposure(as_of, history)
        return 1.0

    def weights(self, as_of: pd.Timestamp, history: pd.DataFrame) -> dict[str, float]:
        assert history.index[-1] <= as_of
        avail = self._available(as_of, history)
        if len(avail) < self.top:
            return {}
        self._fit(as_of)
        if self._model is None:
            return {}
        Xd = self.X.loc[as_of].reindex(avail)[self._cols]
        pred = pd.Series(self._model.predict(Xd.to_numpy(dtype=float)), index=avail)
        self.preds.append((as_of, pred))
        pick = list(pred.sort_values(ascending=False).index[: self.top])
        if self.weighting == "invvol":
            iv = 1 / self.vol63.loc[as_of, pick].clip(lower=0.05)
            w = (iv / iv.sum()).to_dict()
        else:
            w = {t: 1.0 / len(pick) for t in pick}
        expo = self._exposure(as_of, history)
        if self.vol_target:
            r = history[pick].pct_change(fill_method=None).iloc[-63:]
            ww = np.array([w[t] for t in pick])
            vol = float(np.sqrt(ww @ r.cov().to_numpy() @ ww * 252)) if len(r) > 20 else 0.0
            if vol > 0:
                expo *= min(1.0, self.vol_target / vol)
        out = {t: v * expo for t, v in w.items()}
        if self.defensive and expo < 1 and self.defensive in history and pd.notna(history[self.defensive].iloc[-1]):
            out[self.defensive] = out.get(self.defensive, 0.0) + (1 - expo)
        return out

    def ic(self) -> dict:
        """예측 순위와 실제 초과수익 순위의 날짜별 상관(평가 전용)."""
        ics = []
        for d, p in self.preds:
            real = self.fwd_excess.loc[d, p.index]
            m = real.notna()
            if m.sum() >= 5:
                ics.append(p[m].rank().corr(real[m].rank()))
        ics = [x for x in ics if pd.notna(x)]
        if len(ics) < 3:
            return {"ic_mean": None, "ic_t": None, "ic_n": len(ics)}
        a = np.array(ics)
        return {"ic_mean": float(a.mean()), "ic_t": float(a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))), "ic_n": len(a)}


def _usable(X: pd.DataFrame, min_share: float = 0.5) -> list[str]:
    return [c for c in X.columns if X[c].notna().mean() >= min_share]


def _join_macro(X: pd.DataFrame, m: pd.DataFrame) -> pd.DataFrame:
    """(날짜, 종목) 표에 날짜별 지표를 붙인다."""
    dates = X.index.get_level_values(0)
    return pd.concat([X, pd.DataFrame(m.reindex(dates).to_numpy(), index=X.index, columns=m.columns)], axis=1)


class MarketTimer:
    """S&P(SPY)가 앞으로 h거래일 현금(SHY)보다 나을 확률."""

    def __init__(self, name: str, px: pd.DataFrame, macro_f: pd.DataFrame, *, model: str = "logit", feats: str = "PMN",
                 h: int = 21, mode: str = "binary", defensive: str | None = "SHY", refit_months: int = 3, step: int = 5,
                 train_years: float | None = None):
        self.name, self.model_name, self.h, self.mode, self.defensive = name, model, h, mode, defensive
        self.refit_months, self.step, self.train_years = refit_months, step, train_years
        self.px = px
        panel = price_panel(px)
        own = pd.DataFrame({k: panel[k]["SPY"] for k in ["r21", "r63", "r252", "vol21", "vol63", "ma200", "dd252", "rsi14"]})
        _, mf = _feature_sets(feats)
        self.X = own.join(macro_f.reindex(px.index)[mf]) if mf else own
        if feats == "P":
            self.X = own
        fwd = forward_return(px[["SPY", "SHY"]], h)
        self.y = (fwd["SPY"] > fwd["SHY"]).astype(float).where(fwd["SPY"].notna() & fwd["SHY"].notna())
        self._model, self._fit_key = None, None
        self.probs: list[tuple[pd.Timestamp, float]] = []

    def _fit(self, as_of):
        key = (as_of.year, (as_of.month - 1) // self.refit_months)
        if key == self._fit_key and self._model is not None:
            return
        dates = training_dates(self.px.index, as_of, self.h, step=self.step, years=self.train_years)
        X, y = self.X.reindex(dates), self.y.reindex(dates)
        self._cols = _usable(X)
        X = X[self._cols]
        keep = y.notna() & X.notna().mean(axis=1).ge(0.6)
        if keep.sum() < 60 or y[keep].nunique() < 2:
            self._model = None
            return
        assert dates.max() <= as_of
        self._model = make_clf(self.model_name).fit(X[keep].to_numpy(dtype=float), y[keep].to_numpy())
        self._fit_key = key

    def prob(self, as_of) -> float | None:
        self._fit(as_of)
        if self._model is None or as_of not in self.X.index:
            return None
        p = float(self._model.predict(self.X.loc[[as_of], self._cols].to_numpy(dtype=float))[0])
        self.probs.append((as_of, p))
        return p

    def exposure(self, as_of, history) -> float:
        p = self.prob(as_of)
        if p is None:
            return 1.0
        if self.mode == "binary":
            return 1.0 if p >= 0.5 else 0.0
        return float(np.clip((p - 0.35) / 0.3, 0, 1))  # 확률 0.35 이하 0%, 0.65 이상 100%

    def weights(self, as_of, history) -> dict[str, float]:
        e = self.exposure(as_of, history)
        out = {"SPY": e} if e > 0 else {}
        if self.defensive and e < 1 and pd.notna(history[self.defensive].iloc[-1]):
            out[self.defensive] = 1 - e
        return out

    def ic(self) -> dict:
        """확률과 실제(시장이 현금을 이겼나)의 맞춤 정도: 브라이어 점수, 적중률."""
        if len(self.probs) < 3:
            return {"brier": None, "hit": None, "n": len(self.probs)}
        d = pd.Series(dict(self.probs))
        y = self.y.reindex(d.index)
        m = y.notna()
        if m.sum() < 3:
            return {"brier": None, "hit": None, "n": int(m.sum())}
        return {"brier": float(((d[m] - y[m]) ** 2).mean()), "hit": float(((d[m] >= 0.5) == (y[m] == 1)).mean()),
                "base_rate": float(y[m].mean()), "n": int(m.sum())}
