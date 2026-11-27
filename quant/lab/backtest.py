"""원화 기준 일별 백테스트 엔진.

- 체결: as_of(거래일 i) 종가로 정한 비중을 다음 거래일(i+1) 종가에 체결한다.
- 계좌: 원화 현금으로 시작한다. 살 때 원화→달러, 팔 때 달러→원화로 바꾸며 환전 스프레드와 수수료를 낸다.
- 세금: 해외주식 양도소득세. 매도 차익(원화, 평균단가)을 연 단위로 합산해 공제 후 세율을 곱해 그해 마지막 거래일에 낸다.
  결손금 이월은 없다. 끝까지 들고 있는 종목의 세금은 `after_tax_if_liquidated` 로 따로 보여 준다.
- 소수 주식을 허용한다(비중 재현을 우선).
- 2차(Fable 판정 #57·설계 #59): 슬리피지(편도), 비용 배수, 같은 날 팔고 사는 달러는 순액만 환전,
  배당세 15%(배당락일 배당률 × 보유액), 연말 세금으로 현금이 모자라면 보유분을 비례로 팔아 냄,
  전략이 None을 주면 '그대로 둠'(매매 없음), 날짜별 비중 기록.
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
    slippage: float = 0.0003     # 편도 호가 차이(체결 금액 대비)
    dividend_tax: float = 0.15   # 미국 배당 원천징수

    def scaled(self, k: float) -> "Costs":
        """비용 k배(수수료·환전·슬리피지). 세금은 그대로."""
        return Costs(self.fee * k, self.fx_spread * k, self.tax_rate, self.tax_deduction_krw, self.slippage * k, self.dividend_tax)


@dataclass
class BacktestResult:
    nav: pd.Series                       # 원화 평가액(세금 낸 뒤), 날짜별
    trades: list[dict] = field(default_factory=list)
    taxes: dict[int, float] = field(default_factory=dict)
    after_tax_if_liquidated: float = float("nan")
    weights: pd.DataFrame | None = None  # 날짜별 종가 기준 보유 비중(현금 제외)
    dividend_taxes: float = 0.0
    liq_nav: pd.Series | None = None     # 날짜별 '그날 다 팔고 세금까지 내면 남는 돈'(3차, 계획 #66)


def _liquidation_value(cash: float, shares: dict, basis: dict, realized_year: float, px, rate: float, costs: "Costs") -> float:
    """그날 종가에 전부 팔고(매도 비용·환전) 올해 실현이익 + 미실현이익에 양도세까지 낸 뒤 남는 원화."""
    trade_cost = costs.fee + costs.slippage
    gain, out = realized_year, cash
    for t, q in shares.items():
        net = q * float(px[t]) * rate * (1 - trade_cost) * (1 - costs.fx_spread)
        gain += net - basis[t]
        out += net
    return out - max(0.0, gain - costs.tax_deduction_krw) * costs.tax_rate


def _check_inputs(prices: pd.DataFrame, fx: pd.Series) -> pd.Series:
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError("prices 날짜는 중복 없이 오름차순이어야 한다")
    return fx.reindex(prices.index).ffill()  # 앞으로만 채운다(미래 환율 금지)


def _rebalance_days(index: pd.DatetimeIndex, rule: str) -> set[pd.Timestamp]:
    if rule == "D":
        return set(index)
    if rule == "M":
        s = pd.Series(index, index=index)
        return set(s.groupby([index.year, index.month]).max())
    if rule == "W":  # 주마다 마지막 거래일(스윙)
        s = pd.Series(index, index=index)
        iso = index.isocalendar()
        return set(s.groupby([iso.year.to_numpy(), iso.week.to_numpy()]).max())
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
    div_yield: pd.DataFrame | None = None,
) -> BacktestResult:
    """start~end 구간을 돌린다. 신호 계산에는 start 이전 가격도 history 로 쓸 수 있다.
    div_yield: 날짜×종목 배당률(배당락일에만 값). 수정종가가 배당을 이미 담고 있으므로 세금만 현금에서 뺀다."""
    fx = _check_inputs(prices, fx)
    mask = prices.index >= pd.Timestamp(start)
    if end is not None:
        mask &= prices.index <= pd.Timestamp(end)
    idx = prices.index[mask]
    if len(idx) < 2:
        raise ValueError("구간에 거래일이 2일 이상 있어야 한다")
    # 환율은 평가(원화 환산)에만 쓰므로 백테스트 구간 안에서만 있으면 된다(신호용 과거 시세는 환율보다 길 수 있다)
    if fx.loc[idx].isna().any():
        raise ValueError("구간 안에 환율이 없는 날이 있다: 환율을 상수로 대신 채우지 않는다")
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

    trade_cost = costs.fee + costs.slippage
    div_tax_total = 0.0
    wrows = []
    liq: list[float] = []
    wants_state = bool(getattr(strategy, "wants_state", False))
    for i, d in enumerate(idx):
        px = prices.loc[d]
        rate = float(fx.loc[d])
        # 배당세: 배당락일에 그 전날 종가 보유액 × 배당률 × 세율(원화)
        if div_yield is not None and shares and i > 0 and d in div_yield.index:
            prev = prices.loc[idx[i - 1]]
            for t, q in shares.items():
                y = div_yield.at[d, t] if t in div_yield.columns else 0.0
                if y and y > 0:
                    tax = q * float(prev[t]) * rate * y * costs.dividend_tax
                    cash -= tax
                    div_tax_total += tax
        if pending is not None:
            value = cash + sum(q * float(px[t]) * rate for t, q in shares.items())
            target_val = {t: w * value for t, w in pending.items() if w > 0}
            usd_sold = usd_bought = 0.0
            # 1) 팔기: 목표보다 많이 가진 만큼(환전 전 달러로 받는다)
            for t in sorted(set(shares) | set(target_val)):
                p = float(px[t]) if t in px.index else np.nan
                if np.isnan(p):
                    raise ValueError(f"{d.date()} {t} 가격이 없다")
                cur_val = shares.get(t, 0.0) * p * rate
                diff = target_val.get(t, 0.0) - cur_val
                if diff < -1e-9 and shares.get(t, 0.0) > 0:
                    qty = min(shares[t], -diff / (p * rate))
                    usd = qty * p * (1 - trade_cost)
                    usd_sold += usd
                    net = usd * rate
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
            # 환전은 순액만: 판 달러로 먼저 사고 모자란 만큼만 원화→달러(반대면 남은 달러만 원화로)
            gross_buy = sum(v * (1 + trade_cost) for v in buys.values())
            fx_need = max(0.0, gross_buy - usd_sold * rate) * costs.fx_spread + max(0.0, usd_sold * rate - gross_buy) * costs.fx_spread
            need = gross_buy + fx_need
            scale = min(1.0, cash / need) if need > 0 else 0.0
            for t, v in buys.items():
                p = float(px[t])
                spend = v * scale * (1 + trade_cost)
                qty = v * scale / (p * rate)
                usd_bought += qty * p
                shares[t] = shares.get(t, 0.0) + qty
                basis[t] = basis.get(t, 0.0) + spend
                cash -= spend
                trades.append({"date": d, "ticker": t, "side": "buy", "qty": qty, "krw": spend})
            cash -= abs(usd_bought - usd_sold) * rate * costs.fx_spread
            pending = None

        # 연말 세금(현금이 모자라면 보유분을 비례로 팔아 낸다)
        last_of_year = i == len(idx) - 1 or idx[i + 1].year != d.year
        if last_of_year and i < len(idx) - 1:
            tax = max(0.0, realized_year - costs.tax_deduction_krw) * costs.tax_rate
            if tax > 0:
                cash -= tax
                taxes[d.year] = taxes.get(d.year, 0.0) + tax
            realized_year = 0.0
            if cash < 0 and shares:
                hold = sum(q * float(px[t]) * rate for t, q in shares.items())
                frac = min(1.0, -cash / (hold * (1 - trade_cost) * (1 - costs.fx_spread)))
                for t in list(shares):
                    qty = shares[t] * frac
                    net = qty * float(px[t]) * rate * (1 - trade_cost) * (1 - costs.fx_spread)
                    avg = basis[t] / shares[t]
                    realized_year += net - avg * qty  # 다음 해 실현분으로
                    basis[t] -= avg * qty
                    shares[t] -= qty
                    cash += net
                    trades.append({"date": d, "ticker": t, "side": "sell", "qty": qty, "krw": net, "why": "세금"})

        value = cash + sum(q * float(px[t]) * rate for t, q in shares.items())
        nav.append(value)
        liq.append(_liquidation_value(cash, shares, basis, realized_year, px, rate, costs))
        wrows.append({t: q * float(px[t]) * rate / value for t, q in shares.items()} if value > 0 else {})

        if i < len(idx) - 1 and (first_signal or d in rebal):
            history = prices.loc[:d]
            if wants_state:  # 계좌 상태(그날 종가 기준, 과거만)를 넘긴다 — 절세 매도용
                pos = {t: {"value": q * float(px[t]) * rate, "basis": basis[t]} for t, q in shares.items()}
                state = {"value": value, "cash": cash, "positions": pos, "realized": realized_year, "year": d.year}
                raw = strategy.weights(d, history, state)
            else:
                raw = strategy.weights(d, history)
            if raw is None and not first_signal:  # 그대로 둠(띠 안·변화 없음)
                continue
            w = {t: float(v) for t, v in dict(raw or {}).items() if v and float(v) > 0}
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
        net = q * float(px[t]) * rate * (1 - trade_cost) * (1 - costs.fx_spread)
        liq_gain += net - basis[t]
        liq_cash += net
    liq_tax = max(0.0, liq_gain - costs.tax_deduction_krw) * costs.tax_rate
    wdf = pd.DataFrame(wrows, index=idx).fillna(0.0)
    return BacktestResult(pd.Series(nav, index=idx, name=strategy.name), trades, taxes, liq_cash - liq_tax, wdf, div_tax_total,
                          pd.Series(liq, index=idx, name=strategy.name))
