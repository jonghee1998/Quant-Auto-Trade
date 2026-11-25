"""실험실 엔진 테스트: 합성 가격만 쓴다(인터넷 없음)."""
import math

import numpy as np
import pandas as pd
import pytest

from quant.lab.backtest import Costs, run_backtest
from quant.lab.metrics import cagr, max_drawdown, summary
from quant.lab.registry import Experiment, Registry
from quant.lab.run import evaluate
from quant.lab.splits import HoldoutLocked, Splits
from quant.lab.strategy import BuyAndHold, TrendFilter

NO_COST = Costs(fee=0.0, fx_spread=0.0, tax_rate=0.0, tax_deduction_krw=0.0)


def _prices(n=300, start="2020-01-01", growth=0.001, ticker="TEST01"):
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame({ticker: 100 * (1 + growth) ** np.arange(n)}, index=idx)


def _fx(prices, rate=1000.0):
    return pd.Series(rate, index=prices.index)


def test_buy_and_hold_tracks_price_from_second_day():
    p = _prices()
    res = run_backtest(p, _fx(p), BuyAndHold("TEST01"), p.index[0], costs=NO_COST, rebalance="D")
    # 첫날은 현금, 둘째 날 종가에 사서 그 뒤로 가격을 그대로 따라간다
    assert res.nav.iloc[0] == pytest.approx(10_000_000)
    assert res.nav.iloc[1] == pytest.approx(10_000_000)
    assert res.nav.iloc[-1] / res.nav.iloc[1] == pytest.approx(p["TEST01"].iloc[-1] / p["TEST01"].iloc[1])


def test_signal_cannot_earn_the_day_it_sees():
    """하루 급등을 아는 '미래 엿보기' 전략도 그날 수익은 못 먹는다(다음 날 체결)."""
    idx = pd.bdate_range("2021-01-01", periods=5)
    p = pd.DataFrame({"TEST01": [100, 100, 200, 200, 200]}, index=idx, dtype=float)

    class Peek:
        name = "peek"

        def weights(self, as_of, history):
            # history 는 as_of 까지만 있어야 한다
            assert history.index[-1] == as_of
            return {"TEST01": 1.0} if as_of == idx[1] else {}

    res = run_backtest(p, _fx(p), Peek(), idx[0], costs=NO_COST, rebalance="D")
    assert res.nav.max() == pytest.approx(10_000_000)


def test_costs_reduce_value():
    p = _prices()
    free = run_backtest(p, _fx(p), BuyAndHold("TEST01"), p.index[0], costs=NO_COST)
    paid = run_backtest(p, _fx(p), BuyAndHold("TEST01"), p.index[0], costs=Costs(fee=0.001, fx_spread=0.01, tax_rate=0.0))
    assert paid.nav.iloc[-1] < free.nav.iloc[-1]


def test_yearly_tax_on_realized_gain_after_deduction():
    idx = pd.bdate_range("2021-12-01", "2022-01-31")
    price = pd.Series(100.0, index=idx)
    price[idx >= "2021-12-10"] = 200.0
    p = pd.DataFrame({"TEST01": price})

    class InThenOut:
        name = "in_then_out"

        def weights(self, as_of, history):
            return {"TEST01": 1.0} if as_of < pd.Timestamp("2021-12-15") else {}

    c = Costs(fee=0.0, fx_spread=0.0, tax_rate=0.22, tax_deduction_krw=2_500_000)
    res = run_backtest(p, _fx(p), InThenOut(), idx[0], capital_krw=10_000_000, costs=c, rebalance="D")
    gain = 10_000_000  # 100 → 200 으로 두 배
    assert res.taxes[2021] == pytest.approx((gain - 2_500_000) * 0.22)
    assert res.nav.iloc[-1] == pytest.approx(20_000_000 - res.taxes[2021])


def test_unrealized_gain_is_taxed_only_in_liquidation_view():
    p = _prices(n=600)
    c = Costs(fee=0.0, fx_spread=0.0, tax_rate=0.22, tax_deduction_krw=2_500_000)
    res = run_backtest(p, _fx(p), BuyAndHold("TEST01"), p.index[0], costs=c)
    assert res.taxes == {}
    gain = res.nav.iloc[-1] - 10_000_000
    assert res.after_tax_if_liquidated == pytest.approx(res.nav.iloc[-1] - (gain - 2_500_000) * 0.22)


def test_missing_fx_at_start_is_an_error_not_a_constant():
    p = _prices(n=10)
    fx = _fx(p).copy()
    fx.iloc[0] = np.nan
    with pytest.raises(ValueError):
        run_backtest(p, fx, BuyAndHold("TEST01"), p.index[0], costs=NO_COST)


def test_trend_filter_goes_to_cash_below_average():
    up = _prices(n=250, growth=0.002)
    down = pd.DataFrame({"TEST01": up["TEST01"].iloc[-1] * (0.99 ** np.arange(1, 101))},
                        index=pd.bdate_range(up.index[-1] + pd.offsets.BDay(), periods=100))
    p = pd.concat([up, down])
    tf = TrendFilter("TEST01", window=50)
    assert tf.weights(p.index[-1], p) == {}
    assert tf.weights(up.index[-1], up) == {"TEST01": 1.0}


def test_metrics_known_values():
    idx = pd.date_range("2020-01-01", periods=3, freq="365D")
    nav = pd.Series([100.0, 50.0, 100.0], index=idx)
    assert max_drawdown(nav) == pytest.approx(-0.5)
    assert cagr(pd.Series([100.0, 121.0], index=pd.to_datetime(["2020-01-01", "2022-01-01"]))) == pytest.approx(0.1, rel=1e-3)
    s = summary(nav, nav)
    assert s["excess_cagr"] == pytest.approx(0.0)


def test_holdout_is_locked_and_final_only_once(tmp_path):
    p = pd.DataFrame({"SPY": 100 * 1.0005 ** np.arange(800)}, index=pd.bdate_range("2019-01-01", periods=800))
    sp = Splits(dev=("2019-01-01", "2019-12-31"), valid=("2020-01-01", "2020-12-31"), holdout=("2021-01-01", None))
    reg = Registry(tmp_path / "experiments.jsonl")
    kw = dict(hypothesis="시험", params={}, splits=sp, registry=reg, costs=NO_COST)
    m = evaluate(p, _fx(p), BuyAndHold("SPY"), period="dev", **kw)
    assert m["trial_no"] == 1 and math.isfinite(m["cagr"])
    evaluate(p, _fx(p), BuyAndHold("SPY"), period="valid", **kw)
    assert reg.trials("buy_and_hold") == 2
    with pytest.raises(HoldoutLocked):
        evaluate(p, _fx(p), BuyAndHold("SPY"), period="holdout", **kw)
    evaluate(p, _fx(p), BuyAndHold("SPY"), period="holdout", final=True, **kw)
    with pytest.raises(HoldoutLocked):
        evaluate(p, _fx(p), BuyAndHold("SPY"), period="holdout", final=True, **kw)


def test_registry_rejects_second_final(tmp_path):
    reg = Registry(tmp_path / "e.jsonl")
    e = Experiment("s", "h", {}, "holdout", "d1", "c1", {}, final=True)
    reg.add(e)
    with pytest.raises(PermissionError):
        reg.add(e)
