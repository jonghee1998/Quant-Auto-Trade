"""7차(Fable 설계 #93) 규칙: 자산마다 따로 보는 분산 추세추종. 모델 없음, 조절값은 계획에서 고정.

- 신호: 그날까지의 달러 수정주가만 쓴다(엔진이 다음 거래일 종가에 체결).
- 칸: 묶음 몫 ÷ max(자격 있는 자산 수, 4). 자격 = 시세 273거래일 이상 + 오늘 값 있음. 빈 칸과 신호가 꺼진 몫은 대피처로.
- 띠: 어느 종목이든 목표와 band(SSO는 5%p) 넘게 다를 때만 전체를 목표로 맞춘다. 아니면 None(매매 없음).
"""
from __future__ import annotations

import pandas as pd

ASSETS8 = ("SPY", "EFA", "EEM", "VNQ", "IEF", "TLT", "GLD", "DBC")
DEFENSIVE4 = ("IEF", "TLT", "GLD", "DBC")
WINDOWS = (63, 126, 252)
MIN_DAYS = 273
MIN_SLOTS = 4


def eligible(history: pd.DataFrame, t: str) -> bool:
    if t not in history.columns:
        return False
    s = history[t]
    return bool(pd.notna(s.iloc[-1]) and s.notna().sum() >= MIN_DAYS)


def trend_signal(history: pd.DataFrame, t: str, ref: str = "SHY", windows: tuple[int, ...] = WINDOWS) -> float:
    """창마다 (자산 수익 > 기준(SHY) 같은 기간 수익)인 개수 ÷ 창 수. 둘 다 값이 있는 날만 센다."""
    h = history[[t, ref]].dropna()
    hit = 0
    for k in windows:
        if len(h) <= k:
            continue
        a, b = h.iloc[-1], h.iloc[-1 - k]
        hit += int(a[t] / b[t] > a[ref] / b[ref])
    return hit / len(windows)


def inv_vol_slots(history: pd.DataFrame, assets: list[str], total: float, cap: float, window: int = 63) -> dict[str, float]:
    """total을 1÷변동성(최근 window일 일수익 표준편차) 비례로 나누되 칸마다 cap(포트폴리오 비중)까지. 넘친 몫은 나머지 칸에 다시 나눈다."""
    inv = {}
    for t in assets:
        r = history[t].dropna().pct_change().iloc[-window:]
        v = float(r.std()) if len(r) >= window // 2 else float("nan")
        if v == v and v > 0:
            inv[t] = 1.0 / v
    if not inv:
        return {}
    w = {t: total * x / sum(inv.values()) for t, x in inv.items()}
    for _ in range(len(w)):
        over = [t for t, x in w.items() if x > cap + 1e-12]
        if not over:
            break
        fixed = {t for t, x in w.items() if x >= cap - 1e-12}
        free = [t for t in w if t not in fixed]
        rest = total - cap * len(fixed)
        for t in fixed:
            w[t] = cap
        if not free or rest <= 0:
            break
        s = sum(inv[t] for t in free)
        for t in free:
            w[t] = rest * inv[t] / s
    return w


class TrendSlots:
    """고정 몫(fixed) + 추세 묶음(share). signal: 'blend'(63·126·252 혼합) / 'y12'(252일만) / 'hold'(늘 보유 — 정적 기준선)."""
    wants_state = True

    def __init__(self, name: str, assets=ASSETS8, *, share: float = 1.0, fixed: dict[str, float] | None = None, signal: str = "blend",
                 shelter: str = "SHY", ref: str = "SHY", inv_vol: bool = False, cap: float = 0.25, band: float = 0.025,
                 bands: dict[str, float] | None = None):
        if signal not in ("blend", "y12", "hold"):
            raise ValueError(f"알 수 없는 신호: {signal}")
        self.name, self.assets, self.share, self.fixed = name, tuple(assets), share, dict(fixed or {})
        self.signal, self.shelter, self.ref, self.inv_vol, self.cap = signal, shelter, ref, inv_vol, cap
        self.band, self.bands, self.started = band, dict(bands or {"SSO": 0.05}), False
        if share + sum(self.fixed.values()) > 1 + 1e-9:
            raise ValueError("고정 몫 + 묶음 몫이 1을 넘는다")

    def _sig(self, history, t) -> float:
        if self.signal == "hold":
            return 1.0
        return trend_signal(history, t, self.ref, (252,) if self.signal == "y12" else WINDOWS)

    def target(self, history: pd.DataFrame) -> dict[str, float]:
        w = {t: v for t, v in self.fixed.items() if t in history.columns and pd.notna(history[t].iloc[-1])}
        ok = [t for t in self.assets if eligible(history, t)]
        slot = self.share / max(len(ok), MIN_SLOTS)
        size = inv_vol_slots(history, ok, slot * len(ok), self.cap) if self.inv_vol else {t: slot for t in ok}
        for t, x in size.items():
            v = x * self._sig(history, t)
            if v > 1e-9:
                w[t] = w.get(t, 0.0) + v
        rest = 1.0 - sum(w.values())
        if rest > 1e-9:
            w[self.shelter] = w.get(self.shelter, 0.0) + rest
        return {t: round(float(v), 10) for t, v in w.items()}

    def weights(self, as_of, history, state):
        tgt = self.target(history)
        if not self.started:
            self.started = True
            return tgt
        if state["value"] <= 0:
            return None
        cur = {t: p["value"] / state["value"] for t, p in state["positions"].items()}
        if any(abs(cur.get(t, 0.0) - tgt.get(t, 0.0)) > self.bands.get(t, self.band) for t in set(cur) | set(tgt)):
            return tgt
        return None


class Stacked(TrendSlots):
    """고정 몫(SSO·SPY)을 늘 들고 나머지 몫만 추세 묶음으로(수익 겹치기·E 묶음)."""

    def __init__(self, name: str, fixed: dict[str, float], assets=DEFENSIVE4, **kw):
        super().__init__(name, assets, share=round(1.0 - sum(fixed.values()), 10), fixed=fixed, **kw)

