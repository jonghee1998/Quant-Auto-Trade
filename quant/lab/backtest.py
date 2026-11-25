"""원화 기준 일별 백테스트 엔진.

- 체결: as_of(거래일 i) 종가로 정한 비중을 다음 거래일(i+1) 종가에 체결한다.
- 계좌: 원화 현금으로 시작한다. 살 때 원화→달러, 팔 때 달러→원화로 바꾸며 환전 스프레드와 수수료를 낸다.
- 세금: 해외주식 양도소득세. 매도 차익(원화, 평균단가)을 연 단위로 합산해 공제 후 세율을 곱해 그해 마지막 거래일에 낸다.
  결손금 이월은 없다. 끝까지 들고 있는 종목의 세금은 `after_tax_if_liquidated` 로 따로 보여 준다.
- 소수 주식을 허용한다(비중 재현을 우선).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .strategy import Strategy


@dataclass(frozen=True)
class Costs:
    fee: float = 0.0005          # 편도 수수료율(체결 금액 대비)
    fx_spread: float = 0.001     # 편도 환전 스프레드율
    tax_rate: float = 0.22       # 해외주식 양도소득세(지방세 포함)
    tax_deduction_krw: float = 2_500_000.0  # 연 기본공제(원)


@dataclass
class BacktestResult:
    nav: pd.Series                       # 원화 평가액(세금 낸 뒤), 날짜별
    trades: list[dict] = field(default_factory=list)
    taxes: dict[int, float] = field(default_factory=dict)
    after_tax_if_liquidated: float = float("nan")


def _check_inputs(prices: pd.DataFrame, fx: pd.Series) -> pd.Series:
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("prices 날짜는 중복 없이 오름차순이어야 한다")
    fx = fx.reindex(prices.index).ffill()  # 앞으로만 채운다(미래 환율 금지)
    if fx.isna().any():
        raise ValueError("시작 구간 환율이 없다: 환율을 상수로 대신 채우지 않는다")
    return fx


def _rebalance_days(index: pd.DatetimeIndex, rule: str) -> set[pd.Timestamp]:
    if rule == "D":
        return set(index)
    if rule == "M":
        s = pd.Series(index, index=index)
        return set(s.groupby([index.year, index.month]).max())
    raise ValueError(f"알 수 없는 리밸런싱 주기: {rule}")


def run_backtest(
    prices: pd.DataFrame,
    fx: pd.Series,
    strategy: Strategy,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp | None = None,
    capital_krw: float = 10_000_000.0,
    rebalance: str = "M",
    costs: Costs = Costs(),
) -> BacktestResult:
    """start~end 구간을 돌린다. 신호 계산에는 start 이전 가격도 history 로 쓸 수 있다."""
    fx = _check_inputs(prices, fx)
    mask = prices.index >= pd.Timestamp(start)
    if end is not None:
        mask &= prices.index <= pd.Timestamp(end)
    idx = prices.index[mask]
    if len(idx) < 2:
        raise ValueError("구간에 거래일이 2일 이상 있어야 한다")
    rebal = _rebalance_days(idx, rebalance)
    cash = float(capital_krw)
    shares: dict[str, float] = {}
    basis: dict[str, float] = {}          # 종목별 원화 취득원가 합
    realized_year = 0.0
    taxes: dict[int, float] = {}
    trades: list[dict] = []
    nav = []
    pending: dict[str, float] | None = None
    # 첫날에도 신호를 내 다음 날부터 보유한다(첫날은 현금).
    first_signal = True

    for i, d in enumerate(idx):
        px = prices.loc[d]
        rate = float(fx.loc[d])
        if pending is not None:
            value = cash + sum(q * float(px[t]) * rate for t, q in shares.items())
            target_val = {t: w * value for t, w in pending.items() if w > 0}
            # 1) 팔기: 목표보다 많이 가진 만큼
            for t in sorted(set(shares) | set(target_val)):
                p = float(px[t]) if t in px.index else np.nan
                if np.isnan(p):
                    raise ValueError(f"{d.date()} {t} 가격이 없다")
                cur_val = shares.get(t, 0.0) * p * rate
                diff = target_val.get(t, 0.0) - cur_val
                if diff < -1e-9 and shares.get(t, 0.0) > 0:
                    qty = min(shares[t], -diff / (p * rate))
                    gross = qty * p * rate
                    net = gross * (1 - costs.fee) * (1 - costs.fx_spread)
                    avg = basis[t] / shares[t]
                    realized_year += net - avg * qty
                    basis[t] -= avg * qty
                    shares[t] -= qty
                    cash += net
                    trades.append({"date": d, "ticker": t, "side": "sell", "qty": qty, "krw": net})
                    if shares[t] <= 1e-12:
                        shares.pop(t); basis.pop(t)
            # 2) 사기: 현금 안에서 목표 비율대로
            buys = {}
            for t, tv in target_val.items():
                p = float(px[t])
                cur_val = shares.get(t, 0.0) * p * rate
                if tv - cur_val > 1e-9:
                    buys[t] = tv - cur_val
            need = sum(v * (1 + costs.fee) * (1 + costs.fx_spread) for v in buys.values())
            scale = min(1.0, cash / need) if need > 0 else 0.0
            for t, v in buys.items():
                p = float(px[t])
                spend = v * scale * (1 + costs.fee) * (1 + costs.fx_spread)
                qty = v * scale / (p * rate)
                shares[t] = shares.get(t, 0.0) + qty
                basis[t] = basis.get(t, 0.0) + spend
                cash -= spend
                trades.append({"date": d, "ticker": t, "side": "buy", "qty": qty, "krw": spend})
            pending = None

        # 연말 세금
        last_of_year = i == len(idx) - 1 or idx[i + 1].year != d.year
        if last_of_year and i < len(idx) - 1:
            tax = max(0.0, realized_year - costs.tax_deduction_krw) * costs.tax_rate
            if tax > 0:
                cash -= tax
                taxes[d.year] = taxes.get(d.year, 0.0) + tax
            realized_year = 0.0

        value = cash + sum(q * float(px[t]) * rate for t, q in shares.items())
        nav.append(value)

        if i < len(idx) - 1 and (first_signal or d in rebal):
            history = prices.loc[:d]
            w = {t: float(v) for t, v in dict(strategy.weights(d, history)).items() if v and float(v) > 0}
            total = sum(w.values())
            if total > 1 + 1e-9:
                raise ValueError(f"{strategy.name}: 비중 합이 1을 넘는다 ({total:.4f})")
            pending = w
            first_signal = False

    # 마지막 날 전부 판다고 가정한 세후 금액(올해 실현분 + 미실현분)
    d = idx[-1]
    px = prices.loc[d]
    rate = float(fx.loc[d])
    liq_gain = realized_year
    liq_cash = cash
    for t, q in shares.items():
        net = q * float(px[t]) * rate * (1 - costs.fee) * (1 - costs.fx_spread)
        liq_gain += net - basis[t]
        liq_cash += net
    liq_tax = max(0.0, liq_gain - costs.tax_deduction_krw) * costs.tax_rate
    return BacktestResult(pd.Series(nav, index=idx, name=strategy.name), trades, taxes, liq_cash - liq_tax)
