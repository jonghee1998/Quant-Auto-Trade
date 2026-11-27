"""실험실 4차(Fable 설계 #73): 계좌 모형 세금(손계산), 원화 자산, 합성 국내 ETF, 환헤지 규칙, 고정 혼합 + 절세 매도, 자격. 합성 값만."""
import numpy as np
import pandas as pd
import pytest

from quant.forecast import rules as R
from quant.forecast import synthetic as SYN
from quant.lab.backtest import Costs, run_backtest
from quant.lab.strategy import BuyAndHold

ZERO = Costs(fee=0.0, fx_spread=0.0, slippage=0.0, dividend_tax=0.0)


def flat_then(n=300, start=100.0, end=200.0, cols=("X",), d0="2010-01-04"):
    idx = pd.bdate_range(d0, periods=n)
    return pd.DataFrame({c: np.linspace(start, end, n) for c in cols}, index=idx), pd.Series(1.0, index=idx)


def test_default_account_is_unchanged_regression():
    """기본(해외 직접) 결과가 account 인자를 명시해도 같다(3차 결과가 안 바뀜)."""
    px, fx = flat_then(cols=("SPY", "SHY"))
    a = run_backtest(px, fx * 1200, R.TrendPartial("x", 0.7), px.index[0], None)
    b = run_backtest(px, fx * 1200, R.TrendPartial("x", 0.7), px.index[0], None, account="foreign", krw_assets=frozenset())
    assert a.after_tax_if_liquidated == b.after_tax_if_liquidated and a.liq_nav.equals(b.liq_nav)


def test_deferred_tax_matches_hand_calc():
    """절세계좌형: 사고팔 때 세금 없음, 다 팔 때 (순이익 − 200만) × 9.9%. 원화 자산이라 환전 없음."""
    px, fx = flat_then(start=100.0, end=200.0)
    res = run_backtest(px, fx * 1300, BuyAndHold("X"), px.index[0], None, capital_krw=1e7, costs=ZERO, account="deferred",
                       krw_assets={"X"})
    bought_at = px["X"].iloc[1]
    gross = 1e7 * px["X"].iloc[-1] / bought_at
    assert res.after_tax_if_liquidated == pytest.approx(gross - (gross - 1e7 - 2e6) * 0.099, rel=1e-9)
    assert sum(res.taxes.values()) == 0


def test_domestic_tax_each_sale_no_offset():
    """국내 일반: 팔 때마다 이익의 15.4%, 손실은 상계 안 함."""
    idx = pd.bdate_range("2010-01-04", periods=6)
    px = pd.DataFrame({"A": [100, 100, 150, 150, 150, 150.0], "B": [100, 100, 50, 50, 50, 50.0]}, index=idx)

    class Sw:
        name, calls = "sw", 0

        def weights(self, d, h):
            self.calls += 1
            return {"A": 0.5, "B": 0.5} if self.calls == 1 else {}
    res = run_backtest(px, pd.Series(1.0, index=idx), Sw(), idx[0], None, capital_krw=1e6, rebalance="D", costs=ZERO,
                       account="domestic", krw_assets={"A", "B"})
    # A: 50만 → 75만(이익 25만 × 15.4%), B: 50만 → 25만(손실, 상계 없음)
    assert sum(res.taxes.values()) == pytest.approx(250_000 * 0.154)


def test_krw_asset_in_foreign_account_taxed_immediately_and_no_fx_cost():
    px, fx = flat_then(cols=("KRWCASH",), start=100, end=110)
    c = Costs(fee=0.0, fx_spread=0.01, slippage=0.0, dividend_tax=0.0)
    res = run_backtest(px, fx * 1200, BuyAndHold("KRWCASH"), px.index[0], None, capital_krw=1e7, costs=c, krw_assets={"KRWCASH"})
    gross = 1e7 * px["KRWCASH"].iloc[-1] / px["KRWCASH"].iloc[1]
    assert res.after_tax_if_liquidated == pytest.approx(gross - (gross - 1e7) * 0.154, rel=1e-9)  # 환전 비용 없음


def test_synthetic_is_past_only():
    idx = pd.bdate_range("2005-01-03", periods=400)
    rng = np.random.default_rng(1)
    px = pd.DataFrame({"SPY": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 400))), "SHY": 100.0}, index=idx)
    fx = pd.Series(1100 + np.cumsum(rng.normal(0, 3, 400)), index=idx)
    k, u = pd.Series(3.0, index=idx), pd.Series(1.0, index=idx)
    a = SYN.build(px, fx, k, u)
    px2, fx2 = px.copy(), fx.copy()
    px2.iloc[300:] *= 2
    fx2.iloc[300:] += 500
    b = SYN.build(px2, fx2, k, u)
    pd.testing.assert_frame_equal(a.iloc[:300], b.iloc[:300])
    # 헤지판은 환율과 무관, 금리차 연 2% − 0.3%만큼 SPY 달러보다 앞선다
    gap = np.log(a["KSPX_H"].iloc[-1] / a["KSPX_H"].iloc[0]) - np.log((1 + px["SPY"].pct_change()).prod())
    assert gap == pytest.approx((0.02 - 0.003) * 399 / 252, rel=0.05)


def test_fx_rules_use_lagged_fx_and_ignore_future():
    idx = pd.bdate_range("2000-01-03", periods=900)
    fx = pd.Series(np.r_[np.linspace(1100, 1500, 450), np.linspace(1500, 1000, 450)], index=idx)
    hist = pd.DataFrame({"KSPX_U": 100.0, "KSPX_H": 100.0}, index=idx)
    for fac in (lambda f: R.FxHedgeTrend("F1", f, window=200), lambda f: R.FxHedgeValue("F2", f, window=504)):
        lag = fx.shift(1)
        fut = fx.copy()
        fut.iloc[700:] = 5000
        a, b = fac(lag), fac(fut.shift(1))
        days = [d for d in idx[300:700] if d.is_month_end or d == idx[699]]
        da = [a.weights(d, hist.loc[:d]) for d in days]
        db = [b.weights(d, hist.loc[:d]) for d in days]
        assert da == db
    s = R.FxHedgeTrend("F1", fx.shift(1), window=200)
    ws = [s.weights(d, hist.loc[:d]) for d in idx[250:] if d.day >= 26 and d.weekday() == 4]
    assert {"KSPX_H": 1.0} in ws and s.switches >= 1    # 환율이 꺾여 내려가면 헤지로


def test_mix_harvest_rebalances_and_harvests_in_november_only():
    s = R.MixHarvest("C2", eq=0.8)
    idx = pd.bdate_range("2010-01-04", "2010-12-31")
    px = pd.DataFrame({"SPY": 100.0, "IVV": 100.0, "SHY": 100.0}, index=idx)
    assert s.weights(idx[0], px.loc[: idx[0]], {}) == pytest.approx({"SPY": 0.8, "SHY": 0.2})
    st = {"value": 1e8, "realized": 0.0, "positions": {"SPY": {"value": 9e7, "basis": 8.5e7}, "SHY": {"value": 1e7, "basis": 1e7}}}
    june = idx[idx.month == 6][-1]
    assert s.weights(june, px.loc[:june], st) is None
    nov = idx[idx.month == 11][-1]
    w = s.weights(nov, px.loc[:nov], st)
    assert w["SHY"] == pytest.approx(0.2) and w.get("IVV", 0) > 0 and sum(w.values()) <= 1 + 1e-9


def _synth_world(n=6000, start="1998-01-02", seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    m = rng.normal(0.0004, 0.011, n)
    px = pd.DataFrame({"SPY": 100 * np.exp(np.cumsum(m)), "IVV": 100 * np.exp(np.cumsum(m + rng.normal(0, 0.0002, n))),
                       "SHY": 100 * np.exp(np.cumsum(rng.normal(0.0001, 0.0008, n)))}, index=idx)
    fx = pd.Series(1100 * np.exp(np.cumsum(rng.normal(0, 0.006, n))), index=idx)
    syn = SYN.build(px, fx, pd.Series(3.0, index=idx), pd.Series(2.0, index=idx))
    return px.join(syn), fx


def test_round4_batch_end_to_end():
    from quant.forecast.experiments import BENCHMARKS4, ROUND4
    from quant.forecast.round4 import Ctx, ck, eligibility4, run_batch4, table4
    px, fx = _synth_world()
    mf = pd.DataFrame(index=px.index)
    mf["fx_lag"] = fx.shift(1)
    res = run_batch4(Ctx(px, fx, mf), ROUND4, BENCHMARKS4, period="dev", log=lambda s: None)
    rows = {r["id"]: r for r in res["rows"]}
    assert all("error" not in r for r in rows.values()), {k: r.get("error") for k, r in rows.items() if "error" in r}
    assert res["n_trials"] == 70
    assert rows["R4_F1"]["period"][0] == "1999-01-04" and rows["R4_C1"]["period"][0] == "2004-01-01"
    m = rows["R4_F1"]["cond"]["100M_x1"]
    assert "judge_share" in m and "judge_share_domestic" in m and 0 <= m["hedge_ratio"] <= 1
    assert rows["R4_I2"]["cond"]["10M_x2"]["struct_ref"] == "B90"
    # 작은 계좌일수록 절세 매도 이득이 크다(같은 시세에서)
    h = rows["R4_H1"]["cond"]
    biv = rows["BIV"]["cond"]
    assert h["10M_x1"]["liq_cagr"] - biv["10M_x1"]["liq_cagr"] > h["100M_x1"]["liq_cagr"] - biv["100M_x1"]["liq_cagr"]
    e = eligibility4(res["rows"])
    assert len(e["promoted"]) <= 3 and not any(i in e["promoted"] for i in ("R4_F1a", "R4_F1b", "R4_F2a", "R4_F2b"))
    assert "실험실 4차" in table4(res, "dev", 73, e, None)


def test_tracking_gap():
    idx = pd.bdate_range("2021-01-04", periods=300)
    a = pd.Series(np.exp(np.arange(300) * 0.001), index=idx)
    b = a * np.exp(-np.arange(300) * 0.0001)
    g = SYN.tracking_gap(a, b)
    assert g["gap"] == pytest.approx(0.0001 * 252, rel=1e-6)
