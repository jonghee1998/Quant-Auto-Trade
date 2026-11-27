"""2차 실험 전략(Fable 설계 #59): 위험 조절 규칙(A·L), 띠를 둔 타이밍(T08), 업종 보유 규칙(K), 기준선(B).

상태(직전 노출·200일선 상태·보유 종목)는 전략이 '스스로 낸 과거 신호'와 과거 가격으로만 갱신한다.
체결 결과(미래)는 읽지 않는다. None을 돌려주면 엔진이 그대로 둔다(띠 안에서는 매매 0건).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC"]


def realized_vol(s: pd.Series, window: int = 21) -> float | None:
    """최근 window거래일 일수익 표준편차 × √252(연)."""
    r = s.dropna().pct_change(fill_method=None).dropna()
    if len(r) < window:
        return None
    return float(r.iloc[-window:].std() * np.sqrt(252))


def _has_today(history: pd.DataFrame, t: str) -> bool:
    return t in history and pd.notna(history[t].iloc[-1])


class TrendState:
    """SPY 200일선 상태: 평균의 (1−band) 아래로 내려가면 '피함', (1+band) 위로 올라오면 '보유', 사이면 그대로. 시작은 보유."""

    def __init__(self, window: int = 200, band: float = 0.02):
        self.window, self.band, self.avoid = window, band, False

    def update(self, spy: pd.Series) -> bool:
        s = spy.dropna()
        if len(s) < self.window:
            return self.avoid
        ratio = float(s.iloc[-1] / s.iloc[-self.window:].mean())
        if ratio < 1 - self.band:
            self.avoid = True
        elif ratio > 1 + self.band:
            self.avoid = False
        return self.avoid


def alloc(expo: float, sso_ok: bool) -> dict[str, float]:
    """노출 E → 비중. E≤1: SPY E·SHY 1−E. E>1(SSO 시세 있을 때만): SSO (E−1)·SPY (2−E) — SSO는 2배라 합쳐 E배."""
    if expo > 1 and sso_ok:
        return {"SSO": expo - 1, "SPY": 2 - expo}
    e = min(max(expo, 0.0), 1.0)
    return {k: v for k, v in {"SPY": e, "SHY": 1 - e}.items() if v > 1e-9}


class VolTarget:
    """A01·L01(trend 있으면 A04·L02): 노출 = min(상한, 목표 ÷ SPY 21일 변동성), 200일선 '피함'이면 0.
    직전에 낸 노출과 band 이상 다를 때만 매매. SSO 시세가 없는 날은 상한 1배."""

    def __init__(self, name: str, target: float = 0.15, cap: float = 1.0, window: int = 21, band: float = 0.10,
                 trend: TrendState | None = None):
        self.name, self.target, self.cap, self.window, self.band, self.trend = name, target, cap, window, band, trend
        self.last: float | None = None
        self.exposures: list[tuple[pd.Timestamp, float]] = []

    def weights(self, as_of, history):
        avoid = self.trend.update(history["SPY"]) if self.trend is not None else False
        vol = realized_vol(history["SPY"], self.window)
        if vol is None or vol <= 0:
            return None
        sso_ok = _has_today(history, "SSO")
        e = 0.0 if avoid else min(self.cap if sso_ok else min(self.cap, 1.0), self.target / vol)
        self.exposures.append((as_of, e))
        if self.last is not None and abs(e - self.last) < self.band:
            return None
        self.last = e
        return alloc(e, sso_ok)


class TrendSwitch:
    """A02(월 1회, band=0)·A03(주 1회, band=0.02): 피함이면 SHY 100%, 아니면 SPY 100%. 상태가 바뀔 때만 매매."""

    def __init__(self, name: str, band: float = 0.0):
        self.name, self.state, self.last = name, TrendState(band=band), None

    def weights(self, as_of, history):
        avoid = self.state.update(history["SPY"])
        if self.last is not None and avoid == self.last:
            return None
        self.last = avoid
        return {"SHY": 1.0} if avoid else {"SPY": 1.0}


class Banded:
    """T08: 타이밍 모델의 주식 비중이 직전에 낸 비중과 band 이상 다를 때만 매매."""

    def __init__(self, name: str, timer, band: float = 0.25):
        self.name, self.timer, self.band, self.last = name, timer, band, None
        self.ic = timer.ic

    def weights(self, as_of, history):
        e = self.timer.exposure(as_of, history)
        if self.last is not None and abs(e - self.last) < self.band:
            return None
        self.last = e
        return alloc(e, False)


def mom12_1(history: pd.DataFrame, tickers: list[str], min_days: int = 252) -> pd.Series:
    """12-1개월 수익(1개월 전 ÷ 12개월 전 − 1), 시세 min_days일 이상·오늘 값 있는 것만, 큰 순."""
    h = history[[t for t in tickers if t in history]]
    ok = (h.notna().sum() >= min_days) & h.iloc[-1].notna()
    m = h.shift(21).iloc[-1] / h.shift(252).iloc[-1] - 1
    return m[ok].dropna().sort_values(ascending=False)


class HoldRule:
    """상위 top개를 들고, 보유 종목이 keep위 안이면 유지, 밀려나면 안 가진 것 중 최상위로 교체. 교체가 없으면 None."""

    def __init__(self, top: int = 3, keep: int = 5):
        self.top, self.keep = top, keep
        self.held: list[str] = []

    def step(self, ranked: list[str]) -> list[str] | None:
        if len(ranked) < self.top:
            return None
        stay = [t for t in self.held if t in ranked[: self.keep]]
        new = stay + [t for t in ranked if t not in stay][: self.top - len(stay)]
        if self.held and set(new) == set(self.held):
            return None
        self.held = new
        return list(new)


class SectorHold:
    """K01: 업종 11개 안에서 12-1개월 수익 상위 3, 5위 안이면 유지. 교체가 있을 때만 1/3씩."""

    def __init__(self, name: str, top: int = 3, keep: int = 5):
        self.name, self.rule = name, HoldRule(top, keep)

    def weights(self, as_of, history):
        pick = self.rule.step(list(mom12_1(history, SECTORS).index))
        return None if pick is None else {t: 1 / len(pick) for t in pick}


class RankHold:
    """K02: 예측 순위(ForecastRanker.rank)로 HoldRule. K03: core(SPY 70%) + 나머지를 3개에 똑같이,
    교체가 있거나 SPY 비중이 band 넘게 벗어났을 때만 매매(벗어남은 마지막 신호 뒤 과거 가격 변화로 계산)."""

    def __init__(self, name: str, ranker, top: int = 3, keep: int = 5, core: float = 0.0, band: float = 0.05):
        self.name, self.ranker, self.rule, self.core, self.band = name, ranker, HoldRule(top, keep), core, band
        self.ic = ranker.ic
        self._last: tuple[pd.Timestamp, dict[str, float]] | None = None

    def _drift(self, history: pd.DataFrame) -> float:
        if self._last is None:
            return 0.0
        d0, w0 = self._last
        g = {t: float(history[t].iloc[-1] / history[t].loc[d0]) for t in w0}
        v = sum(w0[t] * g[t] for t in w0)
        return abs(w0.get("SPY", 0.0) * g.get("SPY", 1.0) / v - self.core) if v > 0 else 0.0

    def weights(self, as_of, history):
        pred = self.ranker.rank(as_of, history)
        if pred is None:
            return None
        pick = self.rule.step(list(pred.sort_values(ascending=False).index))
        if pick is None:
            if not (self.core and self._last is not None and self._drift(history) > self.band):
                return None
            pick = self.rule.held
        rest = (1 - self.core) / len(pick)
        w = {t: rest for t in pick}
        if self.core:
            w["SPY"] = w.get("SPY", 0.0) + self.core
        self._last = (as_of, w)
        return dict(w)


class FixedMix:
    """기준선 B80·B60(고정 비중)·BEQ(업종 11개 중 시세 1년 이상 똑같이): 처음과 해마다 12월 마지막 거래일에만 맞춘다.
    월 1회 리밸런싱으로 부른다(12월의 월말 = 해 마지막 거래일)."""

    def __init__(self, name: str, mix: dict[str, float] | None = None):
        self.name, self.mix, self.started = name, mix, False

    def weights(self, as_of, history):
        if self.started and as_of.month != 12:
            return None
        self.started = True
        if self.mix is not None:
            return dict(self.mix)
        ok = [t for t in SECTORS if t in history and history[t].notna().sum() >= 252 and pd.notna(history[t].iloc[-1])]
        return {t: 1 / len(ok) for t in ok} if ok else None


# ── 3차(Fable 설계 #66): 일부만 줄이기·실업률 추세·변동성 바닥·고정 비중 띠·절세 매도 ──

class TrendPartial:
    """D01~D03: 200일선 상태가 '피함'이면 SPY avoid_equity·SHY 나머지, '보유'면 SPY 100%. 상태가 바뀔 때만 매매."""

    def __init__(self, name: str, avoid_equity: float = 0.7, band: float = 0.02):
        self.name, self.ae, self.state, self.last = name, avoid_equity, TrendState(band=band), None
        self.avoid_count = 0

    def target(self, history) -> bool:
        return self.state.update(history["SPY"])

    def weights(self, as_of, history):
        avoid = self.target(history)
        if self.last is not None and avoid == self.last:
            return None
        if avoid:
            self.avoid_count += 1
        self.last = avoid
        return alloc(self.ae, False) if avoid else {"SPY": 1.0}


class GrowthTrend:
    """G01·G02: 'SPY < 200일 평균 그리고 최신 실업률 > 직전 12개 평균'일 때만 피함(SPY avoid_equity). 월말 1회, 바뀔 때만."""

    def __init__(self, name: str, unrate: pd.DataFrame, avoid_equity: float = 0.0):
        """unrate: 날짜 × (latest, prev_mean) — features.unrate_signal 결과(macro_panel의 unrate_latest·unrate_prev12)."""
        self.name, self.u, self.ae, self.last = name, unrate, avoid_equity, None
        self.avoid_count = 0

    def target(self, history) -> bool:
        as_of = history.index[-1]
        s = history["SPY"].dropna()
        if len(s) < 200 or as_of not in self.u.index:
            return False
        lat, prev = self.u.at[as_of, "latest"], self.u.at[as_of, "prev_mean"]
        if pd.isna(lat) or pd.isna(prev):
            return False
        return bool(s.iloc[-1] < s.iloc[-200:].mean() and lat > prev)

    def weights(self, as_of, history):
        avoid = self.target(history)
        if self.last is not None and avoid == self.last:
            return None
        if avoid:
            self.avoid_count += 1
        self.last = avoid
        return alloc(self.ae, False) if avoid else {"SPY": 1.0}


class VolFloor(VolTarget):
    """V01: 노출 = 목표 ÷ 변동성을 [floor, 1]로 자름. 직전 노출과 band 이상 다를 때만."""

    def __init__(self, name: str, target: float = 0.15, floor: float = 0.6, band: float = 0.15, window: int = 21):
        super().__init__(name, target=target, cap=1.0, window=window, band=band)
        self.floor = floor

    def weights(self, as_of, history):
        vol = realized_vol(history["SPY"], self.window)
        if vol is None or vol <= 0:
            return None
        e = float(np.clip(self.target / vol, self.floor, 1.0))
        self.exposures.append((as_of, e))
        if self.last is not None and abs(e - self.last) < self.band:
            return None
        self.last = e
        return alloc(e, False)


class BandedMix:
    """M01: 목표 비중(시세 없는 자산 몫은 SHY). 11월 마지막 거래일(월말 호출)에만 보고, 한 자산이라도 5%p 넘게 벗어나면 다시 맞춤."""
    wants_state = True

    def __init__(self, name: str, mix: dict[str, float], band: float = 0.05, month: int = 11):
        self.name, self.mix, self.band, self.month, self.started = name, mix, band, month, False

    def _target(self, history) -> dict[str, float]:
        w = {t: v for t, v in self.mix.items() if _has_today(history, t)}
        miss = 1 - sum(w.values())
        if miss > 1e-9:
            w["SHY"] = w.get("SHY", 0.0) + miss
        return w

    def weights(self, as_of, history, state):
        tgt = self._target(history)
        if not self.started:
            self.started = True
            return tgt
        if as_of.month != self.month or state["value"] <= 0:
            return None
        cur = {t: p["value"] / state["value"] for t, p in state["positions"].items()}
        if max(abs(cur.get(t, 0.0) - tgt.get(t, 0.0)) for t in set(cur) | set(tgt)) <= self.band:
            return None
        return tgt


def _gain_ratio(p: dict) -> float:
    return p["value"] / p["basis"] - 1 if p.get("basis", 0) > 0 else 0.0


def harvest_move(vals: dict[str, float], ratio: dict[str, float], realized: float, *, deduction: float = 2_500_000.0,
                 use: float = 0.9, min_ratio: float = 0.02, min_krw: float = 100_000.0, pair=("SPY", "IVV")) -> tuple[str, str, float] | None:
    """절세 매도 한 번: 공제의 use배까지 남은 이익을 실현하도록, 이익 비율이 큰 쪽(pair 안)을 팔아 다른 쪽을 산다.
    반환 (파는 종목, 사는 종목, 원화 금액) 또는 None. 이익 X원을 실현하려면 평가액 X × (1+g)/g 를 판다."""
    room = (deduction - realized) * use
    if room <= 0:
        return None
    held = [t for t in pair if vals.get(t, 0) > 0]
    if not held:
        return None
    a = max(held, key=lambda t: ratio.get(t, 0.0))
    g = ratio.get(a, 0.0)
    if g < min_ratio:
        return None
    amt = min(vals[a], room * (1 + g) / g)
    if amt < min_krw:
        return None
    b = pair[1] if a == pair[0] else pair[0]
    return a, b, float(amt)


def _is_last_check_of(as_of: pd.Timestamp, month: int, step_days: int) -> bool:
    """그 달의 마지막 확인일인가: 다음 확인일(step_days 뒤 영업일)이 다음 달이면 그렇다(달력만 씀, 시세 안 봄)."""
    nxt = as_of + (pd.offsets.BDay(1) if step_days <= 1 else pd.Timedelta(days=step_days))
    return as_of.month == month and nxt.month != month


class TaxHarvest:
    """H01: S&P(SPY·IVV)를 그냥 들되, 11월 마지막 거래일에 공제 한도 90%까지 이익을 실현(SPY↔IVV 갈아타기).
    그 밖에는 그대로 둠. IVV 시세가 없으면 안 함. 계좌 상태는 그날 종가 기준(과거만)."""
    wants_state = True

    def __init__(self, name: str, month: int = 11, deduction: float = 2_500_000.0):
        self.name, self.month, self.deduction, self.started = name, month, deduction, False
        self.harvests: list[tuple[pd.Timestamp, str, float]] = []

    def weights(self, as_of, history, state):
        if not self.started:
            self.started = True
            return {"SPY": 1.0}
        if as_of.month != self.month or not _has_today(history, "IVV") or state["value"] <= 0:
            return None
        pos = state["positions"]
        vals = {t: p["value"] for t, p in pos.items()}
        mv = harvest_move(vals, {t: _gain_ratio(p) for t, p in pos.items()}, state["realized"], deduction=self.deduction)
        if mv is None:
            return None
        a, b, amt = mv
        vals[a] -= amt
        vals[b] = vals.get(b, 0.0) + amt
        self.harvests.append((as_of, a, amt))
        # 배당세를 현금에서 빼 현금이 음수일 수 있다 → 비중 분모는 보유액 합과 총액 중 큰 쪽(합이 1을 넘지 않게)
        den = max(state["value"], sum(v for v in vals.values() if v > 0))
        return {t: v / den for t, v in vals.items() if v > 1e-6}


class HarvestOverlay:
    """C01·C02: 바탕 규칙(D01·G02)의 주식 비중 + 11월 마지막 확인일 절세 매도.
    주식 몫은 SPY+IVV 합. 줄일 때는 이익 비율이 낮은 쪽부터 팔고, 늘릴 때는 보유액이 작은 쪽을 산다. '피함'에서도 절세 매도는 한다."""
    wants_state = True

    def __init__(self, name: str, base, step_days: int, month: int = 11, deduction: float = 2_500_000.0):
        self.name, self.base, self.step, self.month, self.deduction = name, base, step_days, month, deduction
        self.equity: float | None = None
        self.harvests: list[tuple[pd.Timestamp, str, float]] = []

    def weights(self, as_of, history, state):
        b = self.base.weights(as_of, history)
        V = state["value"]
        pos = state["positions"]
        if self.equity is None:  # 첫 신호: 바탕 규칙 그대로(주식은 SPY)
            self.equity = (b or {"SPY": 1.0}).get("SPY", 0.0)
            return b or {"SPY": 1.0}
        vals = {t: p["value"] for t, p in pos.items()}
        ratio = {t: _gain_ratio(p) for t, p in pos.items()}
        changed, realized = False, state["realized"]
        if b is not None:
            e = b.get("SPY", 0.0)
            self.equity, changed = e, True
            eq_now = vals.get("SPY", 0.0) + vals.get("IVV", 0.0)
            diff = e * V - eq_now
            if diff < 0:  # 줄이기: 이익 비율 낮은 쪽부터
                left = -diff
                for t in sorted([t for t in ("SPY", "IVV") if vals.get(t, 0) > 0], key=lambda t: ratio.get(t, 0.0)):
                    cut = min(vals[t], left)
                    g = ratio.get(t, 0.0)
                    realized += cut * g / (1 + g) if g > -1 else 0.0
                    vals[t] -= cut
                    left -= cut
            elif diff > 0:  # 늘리기: 보유액이 작은 쪽(IVV 시세 없으면 SPY)
                cands = ["SPY", "IVV"] if _has_today(history, "IVV") else ["SPY"]
                t = min(cands, key=lambda x: vals.get(x, 0.0))
                vals[t] = vals.get(t, 0.0) + diff
            vals["SHY"] = (1 - e) * V
        if _is_last_check_of(as_of, self.month, self.step) and _has_today(history, "IVV") and V > 0:
            mv = harvest_move(vals, ratio, realized, deduction=self.deduction)
            if mv is not None:
                a, bb, amt = mv
                vals[a] -= amt
                vals[bb] = vals.get(bb, 0.0) + amt
                self.harvests.append((as_of, a, amt))
                changed = True
        if not changed:
            return None
        tot = sum(v for v in vals.values() if v > 0)
        scale = min(1.0, V / tot) if tot > 0 else 1.0
        return {t: v * scale / V for t, v in vals.items() if v > 1e-6}


# ── 4차(Fable 설계 #73): 고정 혼합 + 절세 매도, 환헤지 갈아타기 ──

class MixHarvest:
    """R4_C1·C2: 주식(SPY+IVV) eq·SHY 1−eq. 11월 마지막 거래일(월말 호출)에만 보고, 한 자산이 5%p 넘게 벗어나면 맞춘 뒤
    남은 공제로 절세 매도(SPY↔IVV). 주식 몫 안의 SPY·IVV 비율은 맞출 때 그대로 둔다."""
    wants_state = True

    def __init__(self, name: str, eq: float, band: float = 0.05, month: int = 11, deduction: float = 2_500_000.0):
        self.name, self.eq, self.band, self.month, self.deduction, self.started = name, eq, band, month, deduction, False
        self.harvests: list[tuple[pd.Timestamp, str, float]] = []

    def weights(self, as_of, history, state):
        if not self.started:
            self.started = True
            return alloc(self.eq, False)
        if as_of.month != self.month or state["value"] <= 0:
            return None
        V, pos = state["value"], state["positions"]
        vals = {t: p["value"] for t, p in pos.items()}
        ratio = {t: _gain_ratio(p) for t, p in pos.items()}
        realized, changed = state["realized"], False
        eq_now = vals.get("SPY", 0.0) + vals.get("IVV", 0.0)
        if abs(eq_now / V - self.eq) > self.band or abs(vals.get("SHY", 0.0) / V - (1 - self.eq)) > self.band:
            k = self.eq * V / eq_now if eq_now > 0 else 0.0
            for t in ("SPY", "IVV"):
                if vals.get(t, 0) > 0:
                    if k < 1:  # 줄이는 만큼 이익이 실현된다
                        g = ratio.get(t, 0.0)
                        realized += vals[t] * (1 - k) * g / (1 + g) if g > -1 else 0.0
                    vals[t] *= k
            if eq_now <= 0:
                vals["SPY"] = self.eq * V
            vals["SHY"] = (1 - self.eq) * V
            changed = True
        if _has_today(history, "IVV"):
            mv = harvest_move(vals, ratio, realized, deduction=self.deduction)
            if mv is not None:
                a, b, amt = mv
                vals[a] -= amt
                vals[b] = vals.get(b, 0.0) + amt
                self.harvests.append((as_of, a, amt))
                changed = True
        if not changed:
            return None
        den = max(V, sum(v for v in vals.values() if v > 0))
        return {t: v / den for t, v in vals.items() if v > 1e-6}


class _FxSwitch:
    """환노출(KSPX_U) ↔ 환헤지(KSPX_H) 갈아타기 공통. fx_lag: 원/달러를 하루 미룬 것(전 영업일까지의 값)."""

    def __init__(self, name: str, fx_lag: pd.Series):
        self.name, self.fx, self.hedged, self.last = name, fx_lag, False, None
        self.switches = 0
        self.hedge_days: list[tuple[pd.Timestamp, bool]] = []

    def decide(self, s: pd.Series) -> None:  # 하위 클래스가 self.hedged를 바꾼다
        raise NotImplementedError

    def weights(self, as_of, history):
        s = self.fx.loc[:as_of].dropna()
        if "KSPX_H" not in history or pd.isna(history["KSPX_H"].iloc[-1]):
            self.hedged = False
        else:
            self.decide(s)
        self.hedge_days.append((as_of, self.hedged))
        if self.last is not None and self.hedged == self.last:
            return None
        if self.last is not None:
            self.switches += 1
        self.last = self.hedged
        return {"KSPX_H": 1.0} if self.hedged else {"KSPX_U": 1.0}


class FxHedgeTrend(_FxSwitch):
    """R4_F1(·a·b): 원/달러 ÷ n일 평균 < 0.98 → 헤지, > 1.02 → 환노출, 사이는 유지. 시작은 환노출. 월말 1회."""

    def __init__(self, name: str, fx_lag: pd.Series, window: int = 200, band: float = 0.02):
        super().__init__(name, fx_lag)
        self.window, self.band = window, band

    def decide(self, s):
        if len(s) < self.window:
            return
        ratio = float(s.iloc[-1] / s.iloc[-self.window:].mean())
        if ratio < 1 - self.band:
            self.hedged = True
        elif ratio > 1 + self.band:
            self.hedged = False


class FxHedgeValue(_FxSwitch):
    """R4_F2(·a·b): z = 원/달러 ÷ n일 평균. z ≥ 1.08 이고 환율 < 60일 평균 → 헤지, z ≤ 1.00 → 환노출, 사이는 유지."""

    def __init__(self, name: str, fx_lag: pd.Series, window: int = 756, hi: float = 1.08, lo: float = 1.00, short: int = 60):
        super().__init__(name, fx_lag)
        self.window, self.hi, self.lo, self.short = window, hi, lo, short

    def decide(self, s):
        if len(s) < self.window:
            return
        z = float(s.iloc[-1] / s.iloc[-self.window:].mean())
        if z >= self.hi and s.iloc[-1] < s.iloc[-self.short:].mean():
            self.hedged = True
        elif z <= self.lo:
            self.hedged = False
