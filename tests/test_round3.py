"""실험실 3차(Fable 설계 #66): 청산 기준 평가액, 절세 매도, 일부 줄이기, 실업률 신호, 베타 보정 알파, 자격 규칙. 합성 값만."""
import numpy as np
import pandas as pd
import pytest

from quant.forecast import rules as R
from quant.forecast.features import unrate_signal
from quant.lab.backtest import Costs, _rebalance_days, run_backtest
from quant.lab.metrics import beta_adjusted_alpha
from quant.lab.strategy import BuyAndHold

TICK = ["SPY", "IVV", "SHY", "TLT", "GLD"]


def synth(n=1300, seed=2, start="2004-01-01", drift=0.0006):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    m = rng.normal(drift, 0.011, n)
    r = np.column_stack([m, m + rng.normal(0, 0.0003, n), rng.normal(0.0001, 0.001, n),
                         rng.normal(0.0002, 0.008, n), rng.normal(0.0002, 0.009, n)])
    px = pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=TICK)
    return px, pd.Series(1200.0, index=idx)


def test_liq_nav_last_equals_after_tax_if_liquidated():
    px, fx = synth()
    res = run_backtest(px, fx, BuyAndHold("SPY"), px.index[0], None, capital_krw=1e8)
    assert res.liq_nav.iloc[-1] == pytest.approx(res.after_tax_if_liquidated)
    assert res.liq_nav.iloc[0] == pytest.approx(1e8, rel=1e-3)
    assert (res.liq_nav <= res.nav + 1e-6).all()


def test_harvest_realizes_gain_without_tax_and_raises_basis():
    px, fx = synth(drift=0.0015)
    h = run_backtest(px, fx, R.TaxHarvest("H01"), px.index[0], None, capital_krw=1e8)
    b = run_backtest(px, fx, BuyAndHold("SPY"), px.index[0], None, capital_krw=1e8)
    assert len(h.trades) > 1 and sum(h.taxes.values()) == 0          # 공제 안에서만 실현 → 세금 0
    assert h.after_tax_if_liquidated > b.after_tax_if_liquidated      # 원가가 올라 마지막 청산 세금이 줄어듦
    sells = [t for t in h.trades if t["side"] == "sell"]
    assert {t["date"].month for t in sells} == {12}                    # 11월 말 신호 → 12월 첫 거래일 체결


def test_harvest_move_rules():
    # 이익 비율 2% 미만 → 안 함, 공제 다 쓴 해 → 안 함, 금액은 공제의 90%만큼 이익이 나게
    assert R.harvest_move({"SPY": 1e8}, {"SPY": 0.01}, 0.0) is None
    assert R.harvest_move({"SPY": 1e8}, {"SPY": 0.5}, 2_500_000.0) is None
    a, b, amt = R.harvest_move({"SPY": 1e8}, {"SPY": 0.5}, 0.0)
    assert (a, b) == ("SPY", "IVV") and amt * 0.5 / 1.5 == pytest.approx(2_250_000.0)
    assert R.harvest_move({"SPY": 1e8, "IVV": 5e7}, {"SPY": 0.1, "IVV": 0.4}, 0.0)[0] == "IVV"   # 이익 비율 큰 쪽을 판다


def test_harvest_over_deduction_is_taxed():
    """공제를 넘겨 실현하면 22%가 그대로 매겨진다(엔진 규칙)."""
    px, fx = synth(drift=0.002)
    big = R.TaxHarvest("H01", deduction=50_000_000.0)  # 일부러 공제보다 훨씬 많이 실현
    res = run_backtest(px, fx, big, px.index[0], None, capital_krw=1e8)
    assert sum(res.taxes.values()) > 0


class _Peek:
    """계좌 상태에 미래 값이 없는지: 상태를 받는 전략 래퍼."""
    wants_state = True

    def __init__(self, inner):
        self.inner, self.name, self.seen = inner, inner.name, []

    def weights(self, as_of, history, state):
        assert history.index[-1] == as_of
        self.seen.append((as_of, round(state["value"], 2)))
        return self.inner.weights(as_of, history, state)


@pytest.mark.parametrize("fac", [lambda: R.TaxHarvest("H01"),
                                 lambda: R.HarvestOverlay("C01", R.TrendPartial("b", 0.7, 0.02), step_days=7),
                                 lambda: R.BandedMix("M01", {"SPY": 0.8, "TLT": 0.1, "GLD": 0.1})])
def test_stateful_decisions_ignore_future_prices(fac):
    px, fx = synth()
    cut = px.index[900]
    fut = px.copy()
    fut.loc[fut.index > cut] *= 3.0
    a, b = _Peek(fac()), _Peek(fac())
    run_backtest(px, fx, a, px.index[0], None, capital_krw=1e8, rebalance="W")
    run_backtest(fut, fx, b, px.index[0], None, capital_krw=1e8, rebalance="W")
    upto = lambda s: [x for x in s if x[0] <= cut]  # noqa: E731
    assert len(upto(a.seen)) > 10 and upto(a.seen) == upto(b.seen)


def test_trend_partial_switches_only_on_state_change():
    s = R.TrendPartial("D01", avoid_equity=0.7, band=0.02)
    idx = pd.bdate_range("2010-01-01", periods=260)
    up = pd.DataFrame({"SPY": np.linspace(100, 130, 260), "SHY": 100.0}, index=idx)
    assert s.weights(idx[-1], up) == {"SPY": 1.0}
    assert s.weights(idx[-1], up) is None
    down = up.copy()
    down.iloc[-1, 0] = 90.0
    assert s.weights(idx[-1], down) == pytest.approx({"SPY": 0.7, "SHY": 0.3}) and s.avoid_count == 1


def test_unrate_signal_uses_release_date():
    refs = pd.date_range("2005-01-01", periods=14, freq="MS")
    rows = pd.DataFrame({"ref_date": refs, "release_date": refs + pd.Timedelta(days=36), "value": [5.0] * 13 + [6.0]})
    days = pd.bdate_range("2006-01-02", "2006-04-28")
    u = unrate_signal(rows, days)
    rel = refs[-1] + pd.Timedelta(days=36)
    assert u.loc[u.index < rel, "latest"].dropna().eq(5.0).all()      # 발표 전에는 이전 값
    assert u.loc[u.index >= rel, "latest"].eq(6.0).all() and u.loc[u.index >= rel, "prev_mean"].eq(5.0).all()


def test_growth_trend_needs_both_conditions():
    idx = pd.bdate_range("2010-01-01", periods=260)
    px = pd.DataFrame({"SPY": np.r_[np.linspace(100, 130, 259), 90.0], "SHY": 100.0}, index=idx)
    calm = pd.DataFrame({"latest": 5.0, "prev_mean": 5.5}, index=idx)
    worse = pd.DataFrame({"latest": 6.0, "prev_mean": 5.0}, index=idx)
    assert R.GrowthTrend("G01", calm).weights(idx[-1], px) == {"SPY": 1.0}   # 실업률 안 오름 → 보유
    assert R.GrowthTrend("G01", worse).weights(idx[-1], px) == {"SHY": 1.0}  # 둘 다 → 피함


def test_vol_floor_clips():
    idx = pd.bdate_range("2010-01-01", periods=60)
    wild = pd.DataFrame({"SPY": 100 * np.cumprod(1 + np.tile([0.05, -0.045], 30)), "SHY": 100.0}, index=idx)
    w = R.VolFloor("V01").weights(idx[-1], wild)
    assert w == pytest.approx({"SPY": 0.6, "SHY": 0.4})


def test_banded_mix_fills_missing_with_shy_and_checks_only_november():
    px, fx = synth()
    px.loc[px.index < "2004-11-18", "GLD"] = np.nan
    s = R.BandedMix("M01", {"SPY": 0.8, "TLT": 0.1, "GLD": 0.1})
    d0 = px.index[10]
    assert s.weights(d0, px.loc[:d0], {"value": 1, "positions": {}}) == pytest.approx({"SPY": 0.8, "TLT": 0.1, "SHY": 0.1})
    june = px.index[px.index.month == 6][-1]
    assert s.weights(june, px.loc[:june], {"value": 1, "positions": {"SPY": {"value": 0.5}}}) is None


def test_beta_adjusted_alpha_recovers_known_values():
    rng = np.random.default_rng(5)
    idx = pd.bdate_range("2010-01-01", periods=2000)
    rf = np.full(2000, 0.0001)
    rm = rng.normal(0.0004, 0.01, 2000)
    rs = rf + 0.0002 + 0.6 * (rm - rf) + rng.normal(0, 0.0005, 2000)
    lv = lambda r: pd.Series(np.cumprod(1 + r), index=idx)  # noqa: E731
    a = beta_adjusted_alpha(lv(rs), lv(rm), lv(rf))
    assert a["beta"] == pytest.approx(0.6, abs=0.02)
    assert a["alpha"] == pytest.approx(0.0002 * 252, abs=0.01) and a["t"] > 2


def test_round3_batch_eligibility_and_table():
    from quant.forecast.experiments import BENCHMARKS3, ROUND3
    from quant.forecast.features import macro_panel
    from quant.forecast.round3 import ck, eligibility3, pass_table3, run_batch3, table3
    px, fx = synth(n=3800, start="2003-01-01")
    refs = pd.date_range("2001-01-01", "2018-01-01", freq="MS")
    urows = pd.DataFrame({"ref_date": refs, "release_date": refs + pd.Timedelta(days=36), "value": 5 + np.sin(np.arange(len(refs)) / 9)})
    mf = macro_panel({"UNRATE": urows}, px.index)
    res = run_batch3(px, fx, ROUND3, BENCHMARKS3, mf, period="dev", log=lambda s: None)
    rows = {r["id"]: r for r in res["rows"]}
    assert all("error" not in r for r in rows.values()), [r.get("error") for r in rows.values()]
    assert res["n_trials"] == 58
    assert set(rows["H01"]["cond"]) == {"100M_x1", "10M_x1", "100M_x2", "10M_x2"}
    assert rows["H01"]["cond"]["100M_x1"]["harvests"] >= 1
    e = eligibility3(res["rows"])
    assert len(e["promoted"]) <= 3 and set(e["by_id"]) >= {"H01", "D01", "G01", "M01", "C01"}
    assert "실험실 3차" in table3(res, "dev", 66, e)
    p = pass_table3(res["rows"], {"D01": 2.5})
    assert p["H01"]["checks"][0][0].startswith("1") and isinstance(p["D01"]["pass"], bool)


def test_harvest_weights_never_exceed_one_when_cash_negative():
    """배당세로 현금이 음수인 날(보유액 > 총액)에도 비중 합 ≤ 1 (3차 dev 실행 H01 실패 재현)."""
    s = R.TaxHarvest("H01")
    idx = pd.bdate_range("2010-11-01", "2010-11-30")
    px = pd.DataFrame({"SPY": 100.0, "IVV": 100.0}, index=idx)
    s.weights(idx[0], px.loc[: idx[0]], {"value": 1e8, "positions": {}, "realized": 0.0})
    st = {"value": 1.0e8, "cash": -2e5, "realized": 0.0, "positions": {"SPY": {"value": 1.002e8, "basis": 5e7}}}
    w = s.weights(idx[-1], px, st)
    assert w is not None and sum(w.values()) <= 1 + 1e-12
