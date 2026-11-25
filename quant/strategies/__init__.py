"""실험할 전략 목록. 새 전략은 이 폴더에 파일을 만들고 아래 REGISTRY에 이름 → (만드는 함수, 가설 한 줄, 조절값)으로 등록한다.

전략 규칙: weights(as_of, history)는 as_of까지의 가격만 본다(다음 거래일 체결은 엔진이 처리).
"""
from __future__ import annotations

from typing import Callable

from quant.lab.strategy import BuyAndHold, Strategy, TrendFilter

from .sector_momentum import SectorMomentum

REGISTRY: dict[str, tuple[Callable[[], Strategy], str, dict]] = {
    "trend_filter": (lambda: TrendFilter("SPY", 200), "S&P 500이 200일선 아래면 현금으로 피하면 큰 폭락 때 덜 잃는다", {"window": 200}),
    "sector_momentum": (lambda: SectorMomentum(top=3, lookback=63, trend_window=200), "최근 3개월 가장 강한 업종 ETF 3개를 매달 들면 S&P보다 낫다", {"top": 3, "lookback": 63, "trend_window": 200}),
    "buy_and_hold": (lambda: BuyAndHold("SPY"), "기준선", {}),
}
