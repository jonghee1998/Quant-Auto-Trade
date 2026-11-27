"""4차(계획 #73): 국내 상장 ETF 합성 시세(원화). 과거 방향 계산만 쓴다(그날까지의 값으로 그날 값).

- KSPX_U(환노출 S&P) = SPY 수정주가 × 원/달러 × 보수 차감(연 0.10%p)
- KSPX_H(환헤지 S&P): 일수익 = SPY 달러 수익 + (한국 3개월 − 미국 3개월 금리)/252 − 연 0.30%p/252
- KUST_U(미국 단기채·환노출) = SHY × 원/달러 × 보수 차감(연 0.10%p)
- KRWCASH(원화 현금): 일수익 = 한국 3개월 금리/252
금리는 '그날 이전에 발표된 가장 최근 값'(features.asof_series)으로 넘겨받는다(% 단위).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

KRW_ASSETS = frozenset({"KSPX_U", "KSPX_H", "KUST_U", "KRWCASH"})


def _drag(idx: pd.DatetimeIndex, fee: float) -> pd.Series:
    t = (idx - idx[0]).days / 365.25
    return pd.Series(np.exp(-fee * np.asarray(t)), index=idx)


def build(prices: pd.DataFrame, fx: pd.Series, kr3m: pd.Series, us3m: pd.Series) -> pd.DataFrame:
    """prices: 달러 수정주가(SPY·SHY), fx: 원/달러(기준일), kr3m·us3m: 날짜별 알 수 있던 금리(%). 반환: 원화 합성 시세."""
    idx = prices.index
    f = fx.reindex(idx).ffill()
    out = pd.DataFrame(index=idx)
    spy = prices["SPY"]
    ok = spy.notna() & f.notna()
    out["KSPX_U"] = (spy * f * _drag(idx, 0.001)).where(ok)
    if "SHY" in prices:
        out["KUST_U"] = (prices["SHY"] * f * _drag(idx, 0.001)).where(prices["SHY"].notna() & f.notna())
    k, u = kr3m.reindex(idx).ffill() / 100, us3m.reindex(idx).ffill() / 100
    r = spy.pct_change(fill_method=None) + (k - u) / 252 - 0.003 / 252
    first = (spy.notna() & k.notna() & u.notna())
    if first.any():
        s = first.idxmax()
        h = (1 + r.loc[s:].fillna(0.0)).cumprod() * 100.0
        h.iloc[0] = 100.0
        out["KSPX_H"] = h.reindex(idx).where(spy.notna())
        c = (1 + (k.loc[s:] / 252).fillna(0.0)).cumprod() * 100.0
        out["KRWCASH"] = c.reindex(idx)
    return out


def tracking_gap(synth: pd.Series, real: pd.Series) -> dict:
    """합성과 실제 국내 ETF의 연 추적 차이(같은 날만, 로그 수익 차의 연 평균·연 표준편차)."""
    df = pd.concat([synth, real], axis=1, keys=["s", "r"]).dropna()
    if len(df) < 30:
        return {"n": len(df), "gap": None, "te": None}
    d = np.log(df).diff().dropna()
    x = d["s"] - d["r"]
    return {"n": len(df), "gap": float(x.mean() * 252), "te": float(x.std() * np.sqrt(252)),
            "from": str(df.index[0].date()), "to": str(df.index[-1].date())}


def with_us_div_tax(kspx_u: pd.Series, spy_div_yield: pd.Series | None, rate: float = 0.15) -> pd.Series:
    """KSPX_N: 환노출 합성에서 배당락일마다 배당률 × 15%(펀드 안 미국 배당세)를 뗀다(계획 #79)."""
    if spy_div_yield is None or spy_div_yield.dropna().empty:
        return kspx_u.copy()
    y = spy_div_yield.reindex(kspx_u.index).fillna(0.0)
    return kspx_u * (1 - rate * y).cumprod()


def haircut(s: pd.Series, annual: float) -> pd.Series:
    """연 annual만큼 더 깎은 시세(검산 차이 g·견고성 0.3%p)."""
    return s * _drag(s.index, annual).reindex(s.index)


def align_kr(synth: pd.Series, kr_dates: pd.DatetimeIndex) -> pd.Series:
    """한국 d일 종가 ↔ 미국 d−1 거래일 값: d보다 앞선 마지막 미국 날짜의 합성 값(장 시각 맞추기)."""
    s = synth.dropna()
    pos = s.index.searchsorted(kr_dates, side="left") - 1
    vals = [s.iloc[p] if p >= 0 else np.nan for p in pos]
    return pd.Series(vals, index=kr_dates)


def tracking_trend(synth: pd.Series, real: pd.Series, lags: int = 20) -> dict:
    """log(합성 ÷ 실제)의 시간 기울기(연) — 5일 평균, Newey-West 표준오차. 차이만 낸다(수준·성과는 안 냄)."""
    real = real.dropna()
    a = align_kr(synth, real.index)
    y = np.log(a / real).dropna()
    if len(y) < 30:
        return {"n": len(y), "g": None}
    y = y.rolling(5).mean().dropna()
    t = np.asarray((y.index - y.index[0]).days / 365.25)
    X = np.column_stack([np.ones_like(t), t])
    b = np.linalg.lstsq(X, y.to_numpy(), rcond=None)[0]
    e = y.to_numpy() - X @ b
    xtx = np.linalg.inv(X.T @ X)
    u = X * e[:, None]
    S = u.T @ u
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = u[L:].T @ u[:-L]
        S += w * (G + G.T)
    se = float(np.sqrt(max((xtx @ S @ xtx)[1, 1], 0.0)))
    return {"n": int(len(y)), "g": float(b[1]), "se": se, "upper95": float(b[1] + 1.645 * se),
            "from": str(y.index[0].date()), "to": str(y.index[-1].date())}


def tracking_verdict(tr: dict) -> dict:
    """계획 #79: 표본 750일 이상, 95% 상한이 추정값 + 0.5%p 안이면 '확인됨'. g > 0이면 g만큼 더 깎음. g > 1%p면 '확인 못 함'."""
    if tr.get("g") is None or tr["n"] < 750 or tr["upper95"] - tr["g"] > 0.005 or tr["g"] > 0.01:
        return {"status": "확인 못 함", "deduct": None}
    return {"status": "확인됨", "deduct": max(0.0, tr["g"])}


def price_only(spy_close_raw: pd.Series, fx: pd.Series, fee: float = 0.001) -> pd.Series:
    """KSPX_P(검산 방법 B): SPY 수정 전 종가 × 원/달러 − 보수. 분배금이 빠진 실제 국내 ETF 종가와 같은 기준."""
    f = fx.reindex(spy_close_raw.index).ffill()
    s = spy_close_raw * f
    return s * _drag(s.index, fee)


def tracking_verdict6(main: dict, check: dict | None) -> dict:
    """계획 #85: 표본 750일 이상, 95% 상한 − g ≤ 0.5%p, 판정 종목 |g| ≤ 1.0%p, 확인용과 부호가 같거나 둘 다 |g| ≤ 0.3%p."""
    g = main.get("g")
    if g is None or main["n"] < 750 or main["upper95"] - g > 0.005 or abs(g) > 0.01:
        return {"status": "확인 못 함", "deduct": None, "why": "표본·신뢰구간·크기"}
    if check and check.get("g") is not None:
        gc = check["g"]
        if not ((g >= 0) == (gc >= 0) or (abs(g) <= 0.003 and abs(gc) <= 0.003)):
            return {"status": "확인 못 함", "deduct": None, "why": "확인용 종목과 부호 다름"}
    return {"status": "확인됨", "deduct": max(0.0, g)}


def leveraged2x(spy: pd.Series, us3m: pd.Series, fee: float = 0.0089, spread: float = 0.005) -> pd.Series:
    """7차(계획 #93) 합성 2배: 일수익 = S&P 일수익 × 2 − (전날 3개월 국채 금리 + spread) ÷ 252 − fee ÷ 252. us3m은 % 단위(그날 알 수 있던 값)."""
    s = spy.dropna()
    u = us3m.reindex(s.index).ffill().shift(1) / 100
    r = 2 * s.pct_change(fill_method=None) - (u + spread) / 252 - fee / 252
    ok = r.notna()
    if not ok.any():
        return pd.Series(np.nan, index=spy.index)
    r = r.loc[ok.idxmax():]
    out = (1 + r.fillna(0.0)).cumprod() * 100.0
    return out.reindex(spy.index)


def splice(synth: pd.Series, real: pd.Series) -> pd.Series:
    """실제 시세가 생긴 날부터는 실제, 그 전은 합성(그날 값이 이어지게 비율만 맞춤)."""
    real = real.dropna()
    if real.empty:
        return synth.copy()
    d = real.index[0]
    if d not in synth.index or pd.isna(synth.loc[d]):
        return real.reindex(synth.index)
    head = synth.loc[:d].iloc[:-1] * (real.iloc[0] / synth.loc[d])
    return pd.concat([head, real]).reindex(synth.index.union(real.index)).sort_index()


def same_day_slope(synth: pd.Series, real: pd.Series, lags: int = 20) -> dict:
    """같은 시장·같은 날 종가끼리: log(합성 ÷ 실제)의 연 기울기(Newey-West). tracking_trend의 '하루 앞 값 맞추기'만 뺀 것."""
    return tracking_trend(synth.shift(-1), real, lags)


def leverage_verdict(tr: dict, tol: float = 0.005) -> dict:
    """계획 #93: 합성 2배와 실제 SSO의 연 차이가 tol 안이면 '확인됨'(합성이 더 좋으면 그만큼 깎음), 그 밖·표본 750일 미만은 '확인 못 함'."""
    g = tr.get("g")
    if g is None or tr.get("n", 0) < 750 or abs(g) > tol:
        return {"status": "확인 못 함", "deduct": None}
    return {"status": "확인됨", "deduct": max(0.0, g)}
