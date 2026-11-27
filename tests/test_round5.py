"""실험실 5차(Fable 설계 #79): 가계 모형 — 입금·ISA 한도·만기 정산 손계산, 배당 원가, 검산 시각 맞춤, 미래 불변. 합성 값만."""
import numpy as np
import pandas as pd
import pytest

from quant.forecast import synthetic as SYN
from quant.forecast.rules5 import Hold, IsaPlus, Pension
from quant.lab.household import PLANS, Costs5, Plan, irr, simulate, unit_price

ZERO = Costs5(0.0, 0.0, 0.0)


def world(n=1500, start="2004-01-01", drift=0.0004, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    m = rng.normal(drift, 0.01, n)
    px = pd.DataFrame({"SPY": 100 * np.exp(np.cumsum(m)), "IVV": 100 * np.exp(np.cumsum(m)),
                       "SHY": 100 * np.exp(np.cumsum(rng.normal(0.0001, 0.0005, n)))}, index=idx)
    fx = pd.Series(1200.0, index=idx)
    px["KSPX_N"] = px["SPY"] * 1200
    px["KUST_U"] = px["SHY"] * 1200
    return px, fx


KRW = frozenset({"KSPX_N", "KUST_U"})


def test_flat_world_irr_zero_and_lump_matches():
    idx = pd.bdate_range("2010-01-01", periods=300)
    px = pd.DataFrame({"SPY": 100.0}, index=idx)
    r = simulate(px, pd.Series(1000.0, index=idx), Hold("B00", "foreign", {"SPY": 1.0}), PLANS["P50"], idx[0], idx[-1], costs=ZERO)
    assert irr(r.flows, float(r.liq.iloc[-1])) == pytest.approx(0.0, abs=1e-6)
    assert r.flows.sum() == pytest.approx(500_000 * len({(d.year, d.month) for d in idx}))


def test_isa_annual_limit_and_overflow_goes_outside():
    px, fx = world()
    pol = IsaPlus("A1", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=3)
    simulate(px, fx, pol, PLANS["L1억"], px.index[0], px.index[300], costs=ZERO, krw=KRW)
    # 첫날 1억: ISA 2천만, 바깥 8천만
    pol2 = IsaPlus("A1", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=3)
    from quant.lab.household import Household
    hh = Household(pol2.books(), KRW, ZERO)
    pol2.deposit(hh, 1e8, px.index[0], px.iloc[0], 1200.0)
    assert hh.books["isa"].cash == pytest.approx(2e7) and hh.books["out"].cash == pytest.approx(8e7)
    assert pol2.room(hh.books["isa"], pd.Timestamp("2005-01-03")) == pytest.approx(2e7)   # 다음 해 한도 2천만 더


def test_isa_maturity_tax_hand_calc():
    """가격이 두 배 → 만기 정산 세금 = (순이익 − 200만) × 9.9%."""
    idx = pd.bdate_range("2004-01-01", "2007-06-29")
    px = pd.DataFrame({"KSPX_N": np.linspace(100, 200, len(idx)), "SPY": 1.0}, index=idx)
    pol = IsaPlus("A1", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=3)
    r = simulate(px, pd.Series(1.0, index=idx), pol, Plan("x", lump=10_000_000.0), idx[0], idx[-1], costs=ZERO, krw=KRW)
    assert pol.extra["maturities"] == 1
    d = idx[idx >= pd.Timestamp("2007-01-01")][0]
    p0, p1 = px["KSPX_N"].iloc[1], px.loc[idx[idx > d][0], "KSPX_N"]  # 첫날 신호 → 둘째 날 매수, 만기 다음 날 정산
    gross = 1e7 * p1 / p0
    assert r.taxes == pytest.approx((gross - 1e7 - 2e6) * 0.099, rel=1e-6)


def test_dividend_reinvested_adds_to_basis():
    idx = pd.bdate_range("2010-01-04", periods=40)
    px = pd.DataFrame({"SPY": [100.0] * 20 + [102.0] * 20}, index=idx)   # 수정주가: 배당 재투자만큼 오른다
    dy = pd.DataFrame({"SPY": [np.nan] * 20 + [0.02] + [np.nan] * 19}, index=idx)
    a = simulate(px, pd.Series(1.0, index=idx), Hold("B00", "foreign", {"SPY": 1.0}), Plan("x", lump=1e9), idx[0], idx[-1],
                 costs=ZERO, div_yield=dy, div_basis=True)
    b = simulate(px, pd.Series(1.0, index=idx), Hold("B00", "foreign", {"SPY": 1.0}), Plan("x", lump=1e9), idx[0], idx[-1],
                 costs=ZERO, div_yield=dy, div_basis=False)
    assert a.liq.iloc[-1] > b.liq.iloc[-1]   # 원가가 올라 청산 세금이 준다(배당에 세금 두 번 붙던 것 고침)


def test_harvest_in_household_zero_tax_and_beats_hold_in_rising_market():
    px, fx = world(n=2600, drift=0.0009)
    h = simulate(px, fx, Hold("H1", "foreign", {"SPY": 1.0}, harvest=True), PLANS["P150"], px.index[0], px.index[-1], krw=KRW)
    b = simulate(px, fx, Hold("BIV", "foreign", {"IVV": 1.0}), PLANS["P150"], px.index[0], px.index[-1], krw=KRW)
    assert irr(h.flows, float(h.liq.iloc[-1])) > irr(b.flows, float(b.liq.iloc[-1]))


def test_pension_refund_not_counted_as_deposit():
    px, fx = world(n=800)
    pol = Pension("P1")
    r = simulate(px, fx, pol, PLANS["P50"], px.index[0], px.index[-1], krw=KRW)
    assert pol.extra["refunds"] > 0 and r.flows.sum() == pytest.approx(500_000 * len({(d.year, d.month) for d in px.index}))


def test_policy_decisions_ignore_future_prices():
    px, fx = world(n=1600)
    cut = px.index[1000]
    fut = px.copy()
    fut.loc[fut.index > cut] *= 2.5
    for mk in (lambda: IsaPlus("A5", {"KSPX_N": 0.9, "KUST_U": 0.1}, {"SPY": 0.9, "SHY": 0.1}, years=3, out_harvest=True),
               lambda: Hold("H1", "foreign", {"SPY": 1.0}, harvest=True)):
        a = simulate(px, fx, mk(), PLANS["P150"], px.index[0], px.index[-1], krw=KRW)
        b = simulate(fut, fx, mk(), PLANS["P150"], px.index[0], px.index[-1], krw=KRW)
        pd.testing.assert_series_equal(a.nav.loc[:cut], b.nav.loc[:cut])


def test_unit_price_removes_deposits():
    idx = pd.bdate_range("2010-01-04", periods=3)
    nav = pd.Series([100.0, 210.0, 231.0], index=idx)
    flows = pd.Series([100.0, 100.0, 0.0], index=idx)
    up = unit_price(nav, flows)
    assert up.iloc[1] == pytest.approx(1.10) and up.iloc[2] == pytest.approx(1.21)


def test_tracking_alignment_finds_known_gap():
    """한국 d일 = 미국 d−1 값으로 맞추면, 일부러 하루 밀어 만든 실제 시세에서 알려 준 연 차이를 되찾는다."""
    idx = pd.bdate_range("2020-01-01", periods=1000)
    rng = np.random.default_rng(2)
    us = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, 1000))), index=idx)
    years = (idx - idx[0]).days / 365.25
    real = pd.Series(us.shift(1).to_numpy() * np.exp(-0.004 * np.asarray(years)), index=idx).dropna()
    tr = SYN.tracking_trend(us, real)
    assert tr["g"] == pytest.approx(0.004, abs=0.0005) and tr["n"] >= 750
    v = SYN.tracking_verdict(tr)
    assert v["status"] == "확인됨" and v["deduct"] == pytest.approx(tr["g"])


def test_kspx_n_takes_15pct_of_dividend():
    idx = pd.bdate_range("2020-01-01", periods=5)
    u = pd.Series(100.0, index=idx)
    y = pd.Series([0, 0, 0.02, 0, 0], index=idx, dtype=float)
    n = SYN.with_us_div_tax(u, y)
    assert n.iloc[-1] == pytest.approx(100 * (1 - 0.003))


def test_round5_batch_runs_end_to_end():
    from quant.forecast.round5 import BENCH5, ROUND5, eligibility5, run_batch5, strip, table5
    px, fx = world(n=3700, start="2003-06-02")
    res = run_batch5(px, fx, None, ROUND5, BENCH5, period="dev", log=lambda s: None)
    rows = {r["id"]: r for r in res["rows"]}
    assert all("error" not in r for r in rows.values()), {k: r.get("error") for k, r in rows.items() if "error" in r}
    assert set(rows["R5_A1"]["cond"]) == {"P50_x1", "P50_x2", "P150_x1", "P150_x2", "L1억_x1", "L1억_x2"}
    assert rows["R5_A1"]["cond"]["L1억_x1"]["extra"]["maturities"] >= 3
    e = eligibility5(res, px, fx, None, tracking_ok=False)
    assert all(i not in e["promoted"] for i in ("R5_A1", "R5_A3", "R5_I1"))   # 검산 실패면 I·A는 안 올림
    assert "실험실 5차" in table5(strip(res), "dev", 79, e, None, {})
