import math

import numpy as np
import pandas as pd

from quant.lab import metrics as M


def _nav(monthly):
    idx = pd.date_range("2020-01-31", periods=len(monthly) + 1, freq="ME")
    return pd.Series(np.cumprod([1.0] + [1 + x for x in monthly]) * 100, index=idx)


def test_capture_ratios_half_down():
    bench = _nav([0.02, -0.04, 0.03, -0.02, 0.01])
    strat = _nav([0.02, -0.02, 0.03, -0.01, 0.01])  # 내린 달에 절반만
    up, down = M.capture_ratios(strat, bench)
    assert abs(up - 1.0) < 1e-9
    assert 0.45 < down < 0.55


def test_recovery_and_calmar_ulcer():
    idx = pd.date_range("2021-01-01", periods=6, freq="D")
    nav = pd.Series([100, 110, 90, 95, 111, 120], index=idx, dtype=float)
    assert M.recovery_days(nav) == 3.0           # 1/2 고점 → 1/5 회복
    assert M.max_drawdown(nav) < 0 and not math.isnan(M.calmar(nav))
    assert M.ulcer_index(nav) > 0
    flat = pd.Series([100, 100, 90], index=idx[:3], dtype=float)
    assert math.isnan(M.recovery_days(flat))     # 아직 회복 못 함


def test_sortino_ignores_upside_vol():
    idx = pd.bdate_range("2022-01-03", periods=300)
    rng = np.random.default_rng(0)
    up_only = pd.Series(np.cumprod(1 + np.abs(rng.normal(0.001, 0.01, 300))), index=idx)
    assert math.isnan(M.sortino(up_only))        # 하락이 없으면 정의 안 됨


def test_deflated_sharpe_falls_with_more_trials():
    idx = pd.bdate_range("2015-01-01", periods=1500)
    rng = np.random.default_rng(1)
    nav = pd.Series(np.cumprod(1 + rng.normal(0.0004, 0.01, 1500)), index=idx)
    one = M.deflated_sharpe(nav, 1)
    many = M.deflated_sharpe(nav, 200)
    assert 0 <= many < one <= 1
    noise = pd.Series(np.cumprod(1 + rng.normal(0.0, 0.01, 1500)), index=idx)
    assert M.deflated_sharpe(noise, 50) < 0.95


def test_summary_has_new_keys():
    b = _nav([0.02, -0.04, 0.03, -0.02, 0.01])
    s = M.summary(b, b)
    for k in ["up_capture", "down_capture", "recovery_days", "sortino", "calmar", "ulcer", "bench_ulcer"]:
        assert k in s
