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
