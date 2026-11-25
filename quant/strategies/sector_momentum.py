"""강한 업종 갈아타기: 최근 lookback일 수익이 가장 큰 업종 ETF top개를 똑같이. 시장(SPY)이 추세 아래면 현금."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

SECTOR_ETFS = ("XLK", "XLC", "XLY", "XLF", "XLI", "XLV", "XLP", "XLE", "XLB", "XLU", "XLRE")


@dataclass(frozen=True)
class SectorMomentum:
    top: int = 3
    lookback: int = 63
    trend_window: int | None = 200
    universe: tuple[str, ...] = SECTOR_ETFS
    name: str = "sector_momentum"

    def weights(self, as_of: pd.Timestamp, history: pd.DataFrame) -> dict[str, float]:
        if self.trend_window and "SPY" in history:
            spy = history["SPY"].dropna()
            if len(spy) >= self.trend_window and spy.iloc[-1] < spy.iloc[-self.trend_window:].mean():
                return {}
        cols = [c for c in self.universe if c in history]
        h = history[cols].dropna(axis=1, how="any").iloc[-(self.lookback + 1):]
        if len(h) <= self.lookback or h.shape[1] == 0:
            return {}
        ret = h.iloc[-1] / h.iloc[0] - 1
        pick = ret.sort_values(ascending=False).index[: self.top]
        return {c: 1.0 / len(pick) for c in pick}
