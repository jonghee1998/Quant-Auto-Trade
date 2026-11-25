"""전략 인터페이스와 기본 전략(기준선·추세 필터)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

import pandas as pd

Weights = Mapping[str, float]


class Strategy(Protocol):
    """as_of 까지의 가격(history, 행=날짜·열=종목, 달러 수정종가)만 보고 목표 비중을 낸다.

    비중 합이 1보다 작으면 나머지는 원화 현금(수익 0%)으로 둔다.
    """

    name: str

    def weights(self, as_of: pd.Timestamp, history: pd.DataFrame) -> Weights: ...


@dataclass(frozen=True)
class BuyAndHold:
    """기준선: 한 종목(기본 SPY)을 계속 100% 보유."""

    ticker: str = "SPY"
    name: str = "buy_and_hold"

    def weights(self, as_of: pd.Timestamp, history: pd.DataFrame) -> Weights:
        return {self.ticker: 1.0}


@dataclass(frozen=True)
class TrendFilter:
    """기준 종목이 n일 이동평균 위면 보유, 아래면 방어 종목(없으면 현금)."""

    ticker: str = "SPY"
    window: int = 200
    defensive: str | None = None
    name: str = "trend_filter"

    def weights(self, as_of: pd.Timestamp, history: pd.DataFrame) -> Weights:
        s = history[self.ticker].dropna()
        if len(s) < self.window:
            return {self.ticker: 1.0}
        if s.iloc[-1] >= s.iloc[-self.window:].mean():
            return {self.ticker: 1.0}
        return {self.defensive: 1.0} if self.defensive else {}
