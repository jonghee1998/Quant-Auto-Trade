"""실험 한 건 실행: 전략과 기준선을 같은 구간·비용으로 돌리고 기록한다."""
from __future__ import annotations

import numpy as np

import pandas as pd

from .backtest import Costs, run_backtest
from .metrics import TRADING_DAYS, deflated_sharpe, summary
from .registry import Experiment, Registry
from .splits import DEFAULT_SPLITS, HoldoutLocked, Splits
from .strategy import BuyAndHold, Strategy


def evaluate(
    prices: pd.DataFrame,
    fx: pd.Series,
    strategy: Strategy,
    *,
    hypothesis: str,
    params: dict,
    period: str = "dev",
    splits: Splits = DEFAULT_SPLITS,
    registry: Registry | None = None,
    data_version: str = "unknown",
    code_version: str = "unknown",
    benchmark: Strategy = BuyAndHold("SPY"),
    costs: Costs = Costs(),
    rebalance: str = "M",
    final: bool = False,
) -> dict:
    if period == "holdout" and registry is not None and registry.has_final(strategy.name):
        raise HoldoutLocked(f"{strategy.name}: 홀드아웃은 이미 평가했다")
    start, end = splits.period(period, final=final)
    res = run_backtest(prices, fx, strategy, start, end, costs=costs, rebalance=rebalance)
    bench = run_backtest(prices, fx, benchmark, start, end, costs=costs, rebalance=rebalance)
    m = summary(res.nav, bench.nav)
    m["after_tax_if_liquidated"] = res.after_tax_if_liquidated
    m["bench_after_tax_if_liquidated"] = bench.after_tax_if_liquidated
    m["taxes_paid"] = sum(res.taxes.values())
    m["trades"] = len(res.trades)
    # 우연 보정: 지금까지 모든 전략의 시도 수(이번 포함)와 시도들 Sharpe의 분산(일 단위)으로 DSR 계산
    n = (registry.total_trials() if registry is not None else 0) + 1
    prev = registry.trial_sharpes() if registry is not None else []
    var = float(np.var([x / np.sqrt(TRADING_DAYS) for x in prev], ddof=1)) if len(prev) >= 2 else None
    m["n_trials"] = n
    m["dsr"] = deflated_sharpe(res.nav, n, var)
    if registry is not None:
        row = registry.add(Experiment(strategy.name, hypothesis, params, period, data_version, code_version, m, final))
        m["trial_no"] = row["trial_no"]
    return m
