"""실험실 6차(Fable 설계 #85): 달러끼리 갈아타기 환전 0, 나눠 파는 결말 산수, 계좌 채우는 순서·한도, 하락 목록, 계좌 안 G02, 미래 불변. 합성 값만."""
import numpy as np
import pandas as pd
import pytest

from quant.forecast import round6 as R6
from quant.forecast.rules6 import Harvest, InsideSwitch, Ladder
from quant.forecast.rules5 import IsaPlus
from quant.lab.household import PLANS, Book, Costs5, Household, simulate

KRW = frozenset({"KSPX_N", "KUST_U"})


def world(n=2000, start="2004-01-01", drift=0.0005, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    m = rng.normal(drift, 0.01, n)
    px = pd.DataFrame({"SPY": 100 * np.exp(np.cumsum(m)), "IVV": 100 * np.exp(np.cumsum(m)),
                       "SHY": 100 * np.exp(np.cumsum(rng.normal(0.0001, 0.0005, n)))}, index=idx)
    px["KSPX_N"], px["KUST_U"] = px["SPY"] * 1200, px["SHY"] * 1200
    return px, pd.Series(1200.0, index=idx)


def test_swap_has_no_fx_cost():
    c = Costs5(fee=0.0, slippage=0.0, fx_spread=0.01)
    hh = Household({"m": Book("foreign")}, frozenset(), c)
    b = hh.books["m"]
    b.q, b.basis = {"SPY": 10.0}, {"SPY": 10_000.0}
    px = pd.Series({"SPY": 1.0, "IVV": 1.0})
    hh.swap(b, "SPY", "IVV", 10.0, px, 1000.0, pd.Timestamp("2020-01-02"))
    assert b.q["IVV"] == pytest.approx(10.0) and b.cash == pytest.approx(0.0)


def test_staged_ending_math():
    hh = Household({"m": Book("foreign")}, frozenset(), Costs5(0.0, 0.0, 0.0))
    b = hh.books["m"]
    b.q, b.basis = {"SPY": 1.0}, {"SPY": 50_000_000.0}
    px = pd.Series({"SPY": 100_000_000.0})
    gain = 50_000_000.0
    assert hh.liquidation(b, px, 1.0) == pytest.approx(1e8 - (gain - 2.5e6) * 0.22)
    assert hh.liquidation(b, px, 1.0, staged_years=10) == pytest.approx(1e8 - (gain - 2.5e7) * 0.22)
    assert hh.liquidation(b, px, 1.0, staged_years=20) == pytest.approx(1e8)


def test_ladder_fills_pension_then_isa_then_outside():
    pol = Ladder("W1")
    hh = Household(pol.books(), KRW, Costs5())
    px, d = pd.Series({"SPY": 1.0}), pd.Timestamp("2010-01-04")
    pol.deposit(hh, 30_000_000.0, d, px, 1.0)
    assert hh.books["pen"].cash == pytest.approx(6e6) and hh.books["isa"].cash == pytest.approx(2e7) and hh.books["out"].cash == pytest.approx(4e6)
    pol.deposit(hh, 1_000_000.0, d, px, 1.0)                       # 연금·ISA 한도 찼음 → 바깥
    assert hh.books["out"].cash == pytest.approx(5e6)
    w2 = Ladder("W2", isa=False)
    hh2 = Household(w2.books(), KRW, Costs5())
    w2.deposit(hh2, 1e7, d, px, 1.0)
    assert "isa" not in hh2.books and hh2.books["out"].cash == pytest.approx(4e6)


def test_episodes_found_without_choosing():
    idx = pd.bdate_range("2000-01-03", periods=10)
    s = pd.Series([100, 110, 90, 92, 120, 119, 100, 101, 125, 130.0], index=idx)
    ep = R6.episodes(s, 0.15)
    assert ep == [(str(idx[1].date()), str(idx[2].date())), (str(idx[4].date()), str(idx[6].date()))]


def test_harvest_quantity_fixed_at_signal_and_future_invariant():
    px, fx = world(n=1500, drift=0.001)
    cut = px.index[900]
    fut = px.copy()
    fut.loc[fut.index > cut] *= 2
    a = simulate(px, fx, Harvest("H1"), PLANS["P150"], px.index[0], px.index[-1], krw=KRW)
    b = simulate(fut, fx, Harvest("H1"), PLANS["P150"], px.index[0], px.index[-1], krw=KRW)
    pd.testing.assert_series_equal(a.nav.loc[:cut], b.nav.loc[:cut])
    assert a.extra["harvests"] >= 3


def test_inside_switch_moves_only_inside_account():
    px, fx = world(n=900)
    idx = px.index
    px.loc[idx[700]:, ["SPY", "IVV"]] *= 0.7      # 200일선 아래로
    px["KSPX_N"] = px["SPY"] * 1200
    u = pd.DataFrame({"latest": 6.0, "prev_mean": 5.0}, index=idx)
    pol = InsideSwitch("G1", IsaPlus("BA4", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=5), "isa", px["SPY"], u)
    r = simulate(px, fx, pol, PLANS["L1억"], idx[0], idx[-1], krw=KRW)
    assert pol.extra["signals"] >= 1 and pol.extra["events"][0][1] == "피함"


def test_round6_batch_end_to_end():
    px, fx = world(n=3800, start="2003-06-02")
    idx = px.index
    ctx = {"spy": px["SPY"], "unrate": pd.DataFrame({"latest": 5.0, "prev_mean": 5.5}, index=idx)}
    res = R6.run_batch6(px, fx, None, ctx, R6.ROUND6, R6.BENCH6, period="dev", log=lambda s: None)
    rows = {r["id"]: r for r in res["rows"]}
    assert all("error" not in r for r in rows.values()), {k: r.get("error") for k, r in rows.items() if "error" in r}
    h = rows["R6_H1"]["cond"]["P150_x1"]
    assert "vs_biv_krw" in h and set(h["final"]) == {"E0", "E10", "E20"}
    assert "judge_share" in rows["R6_G1"]["cond"]["P150_x1"]
    e = R6.eligibility6(res, px, fx, None, ctx, tracking_ok=False, gate={"pass": False})
    assert "R6_G1" not in e["promoted"] and "R6_W1" not in e["promoted"]
    assert "세법 확인 필요" in R6.table6(R6.strip(res), "dev", 85, e, None, {})
