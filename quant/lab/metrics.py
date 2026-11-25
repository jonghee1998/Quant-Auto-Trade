"""성과 지표: 모두 원화 평가액(세금 반영) 기준."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def cagr(nav: pd.Series) -> float:
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    if years <= 0 or nav.iloc[0] <= 0:
        return float("nan")
    return float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1)


def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1).min())


def sharpe(nav: pd.Series) -> float:
    r = nav.pct_change(fill_method=None).dropna()
    if len(r) < 2 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(TRADING_DAYS))


def monthly_win_rate(nav: pd.Series, bench: pd.Series) -> float:
    """기준선보다 월 수익률이 높았던 달의 비율."""
    a = nav.resample("ME").last().pct_change(fill_method=None).dropna()
    b = bench.resample("ME").last().pct_change(fill_method=None).dropna()
    a, b = a.align(b, join="inner")
    return float((a > b).mean()) if len(a) else float("nan")


def summary(nav: pd.Series, bench: pd.Series) -> dict:
    return {
        "cagr": cagr(nav),
        "mdd": max_drawdown(nav),
        "sharpe": sharpe(nav),
        "bench_cagr": cagr(bench),
        "bench_mdd": max_drawdown(bench),
        "excess_cagr": cagr(nav) - cagr(bench),
        "monthly_win_rate": monthly_win_rate(nav, bench),
    }
