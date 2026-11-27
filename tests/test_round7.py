"""실험실 7차(Fable 설계 #93): 추세 칸·띠·합성 2배·긴 과거 관문·자격·통과 숫자. 합성 시세만, 인터넷 없음."""
import numpy as np
import pandas as pd
import pytest

from quant.forecast import round7 as R7
from quant.forecast import rules7 as R
from quant.forecast import synthetic as SYN
from quant.forecast.experiments import PLAN_ISSUE
from quant.lab.backtest import run_backtest
from quant.lab.metrics import cagr_excluding, max_drawdown_usd

COLS = list(R.ASSETS8) + ["SHY", "SSO"]


def panel(n=900, seed=7, start="2003-01-01", drift=0.0005):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    r = rng.normal(drift, 0.01, (n, len(COLS)))
    r[:, COLS.index("SHY")] = 0.0001
    px = pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=COLS)
    return px, pd.Series(1200.0, index=idx)


def state_of(tgt, value=1e8):
    return {"value": value, "cash": 0.0, "positions": {t: {"value": w * value, "basis": w * value} for t, w in tgt.items()}, "realized": 0.0, "year": 2005}


def test_plan_issue_and_fixed_numbers_match_the_plan():
    assert PLAN_ISSUE == 93 and R7.PREV_TRIALS7 + 10 == 92
    assert (R.WINDOWS, R.MIN_DAYS, R.MIN_SLOTS) == ((63, 126, 252), 273, 4)
    assert [e.id for e in R7.ROUND7] == ["R7_M1", "R7_M2", "R7_M3", "R7_M4", "R7_E1", "R7_X1", "R7_X2", "R7_X3", "R7_X4"]
    assert [e.id for e in R7.BENCH7] == ["B00", "BM0", "B60", "BE0", "BX0", "BXS"]
    assert [e.id for e in R7.ROUND7 if not e.promote] == ["R7_M4", "R7_X4"]
    assert R7.WINDOWS7 == ((2004, 2010), (2006, 2012), (2008, 2014), (2010, 2016), (2011, 2017)) and R7.GATE_PERIOD == ("1987-07-01", "2003-12-31")


def test_signal_counts_windows_beating_shelter():
    idx = pd.bdate_range("2003-01-01", periods=400)
    up = pd.Series(np.linspace(100, 200, 400), index=idx)
    flat = pd.Series(100.0, index=idx)
    h = pd.DataFrame({"TEST01": up, "TEST02": flat * 0.999 ** np.arange(400), "SHY": flat})
    assert R.trend_signal(h, "TEST01") == 1.0 and R.trend_signal(h, "TEST02") == 0.0
    mixed = up.copy()
    mixed.iloc[-63:] = np.linspace(mixed.iloc[-64], mixed.iloc[-64] * 0.98, 63)   # 최근 3개월만 내림 → 1창 꺼짐
    assert R.trend_signal(pd.DataFrame({"TEST01": mixed, "SHY": flat}), "TEST01") == pytest.approx(2 / 3)
    assert R.trend_signal(pd.DataFrame({"TEST01": mixed, "SHY": flat}), "TEST01", windows=(252,)) == 1.0


def test_slots_need_273_days_and_empty_slots_go_to_shelter():
    px, _ = panel()
    px.loc[px.index[:700], ["GLD", "DBC", "VNQ", "EEM", "EFA"]] = np.nan       # 5개는 200일뿐 → 자격 없음
    t = R.TrendSlots("BM0", signal="hold").target(px)
    assert set(t) == {"SPY", "IEF", "TLT", "SHY"}                            # 자격 3개 → 칸은 1/4, 빈 칸은 대피처
    assert t["SPY"] == pytest.approx(0.25) and t["SHY"] == pytest.approx(0.25)
    full = R.TrendSlots("BM0", signal="hold").target(panel()[0])
    assert all(full[a] == pytest.approx(0.125) for a in R.ASSETS8) and "SHY" not in full
    x = R.Stacked("BXS", {"SSO": 0.5}, signal="hold").target(px)             # 방어 4개 중 자격 2개 → 각 12.5%, 나머지 25%는 대피처
    assert x == pytest.approx({"SSO": 0.5, "IEF": 0.125, "TLT": 0.125, "SHY": 0.25})
    assert sum(R.TrendSlots("R7_M1").target(px).values()) == pytest.approx(1.0)


def test_band_keeps_position_until_a_ticker_moves_past_it():
    px, _ = panel()
    s = R.Stacked("BXS", {"SSO": 0.5}, signal="hold")
    tgt = s.weights(px.index[-1], px, state_of({}))
    assert tgt == s.target(px)                                               # 첫 호출은 목표 그대로
    assert s.weights(px.index[-1], px, state_of(tgt)) is None
    drift = dict(tgt, IEF=tgt["IEF"] + 0.02, TLT=tgt["TLT"] - 0.02)          # 2%p ≤ 2.5%p → 그대로
    assert s.weights(px.index[-1], px, state_of(drift)) is None
    sso = dict(tgt, SSO=0.54, GLD=tgt["GLD"] - 0.02, DBC=tgt["DBC"] - 0.02)  # SSO는 5%p까지
    assert s.weights(px.index[-1], px, state_of(sso)) is None
    assert s.weights(px.index[-1], px, state_of(dict(tgt, IEF=tgt["IEF"] + 0.03, TLT=tgt["TLT"] - 0.03))) == tgt


def test_inverse_vol_slots_are_capped_and_sum_to_total():
    px, _ = panel()
    px["IEF"] = 100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.001, len(px))))   # 변동성 1/10 → 상한에 걸림
    w = R.inv_vol_slots(px, list(R.ASSETS8), 1.0, 0.25)
    assert w["IEF"] == pytest.approx(0.25) and sum(w.values()) == pytest.approx(1.0) and max(w.values()) <= 0.25 + 1e-9
    assert sum(R.TrendSlots("R7_M3", inv_vol=True, signal="hold").target(px).values()) == pytest.approx(1.0)


def test_no_lookahead_future_prices_do_not_change_weights():
    px, fx = panel()
    cut = px.index[650]
    px2 = px.copy()
    px2.loc[px2.index > cut] *= np.linspace(1.0, 3.0, (px2.index > cut).sum())[:, None]
    for make in (lambda: R.TrendSlots("R7_M1"), lambda: R.Stacked("R7_X1", {"SSO": 0.5}), lambda: R.TrendSlots("R7_M3", inv_vol=True)):
        a = run_backtest(px, fx, make(), px.index[300], None, capital_krw=1e8)
        b = run_backtest(px2, fx, make(), px.index[300], None, capital_krw=1e8)
        pd.testing.assert_frame_equal(a.weights.loc[:cut], b.weights.loc[:cut])
        assert a.nav.loc[:cut].equals(b.nav.loc[:cut])


def test_leveraged2x_splice_and_verdict():
    idx = pd.bdate_range("2005-01-03", periods=1500)
    spy = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(0).normal(0.0004, 0.01, 1500))), index=idx)
    us3m = pd.Series(2.52, index=idx)
    syn = SYN.leveraged2x(spy, us3m)
    r = syn.pct_change().dropna()
    want = 2 * spy.pct_change() - (0.0252 + 0.005) / 252 - 0.0089 / 252
    assert r.iloc[5] == pytest.approx(want.loc[r.index[5]])                # 2배 − (금리 + 0.5%p) − 보수 0.89%
    real = (syn * 3).iloc[400:] * SYN._drag(idx[400:], 0.002)             # 실제가 연 0.2%p 나쁨 → 합성을 그만큼 깎음
    tr = SYN.same_day_slope(syn, real)
    assert tr["g"] == pytest.approx(0.002, abs=1e-4) and SYN.leverage_verdict(tr) == {"status": "확인됨", "deduct": pytest.approx(0.002, abs=1e-4)}
    assert SYN.leverage_verdict({"n": 900, "g": 0.006})["status"] == "확인 못 함"
    assert SYN.leverage_verdict({"n": 700, "g": 0.001})["status"] == "확인 못 함" and SYN.leverage_verdict({"n": 0, "g": None})["deduct"] is None
    sp = SYN.splice(syn, real)
    assert sp.loc[real.index].equals(real) and sp.iloc[399] / sp.iloc[398] == pytest.approx(syn.iloc[399] / syn.iloc[398])


def test_metrics_helpers():
    idx = pd.bdate_range("2007-01-01", periods=1000)
    r = pd.Series(0.0004, index=idx)
    r.loc["2008-01-01":"2009-06-30"] = -0.002                            # 구간 안에서만 날마다 빠짐 → 빼면 바깥 수익만 남는다
    crash = 100 * (1 + r).cumprod()
    assert cagr_excluding(crash, "2008-01-01", "2009-06-30") == pytest.approx(1.0004 ** 252 - 1, rel=1e-6)
    fx = pd.Series(np.where(idx < idx[500], 1000.0, 1250.0), index=idx)     # 환율이 올라 원화로는 안 빠져 보이는 손실
    flat = pd.Series(1e8, index=idx)
    assert max_drawdown_usd(flat, fx) == pytest.approx(-0.2)


def gate_panel(n=5200, drop=None):
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("1985-01-01", periods=n)
    cols = ["VFINX", "VWIGX", "VEIEX", "FRESX", "VFITX", "VUSTX"]
    px = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.009, (n, 6)), axis=0)), index=idx, columns=cols)
    return px.drop(columns=drop or []), pd.Series(5.0, index=idx)


def test_gate_unknown_when_long_history_is_missing_or_starts_late():
    px, us3m = gate_panel(drop=["VWIGX"])
    g = R7.gate7(px, us3m)
    assert g["M"] == {"status": "확인 못 함", "pass": False} and g["X"]["pass"] is False
    px, us3m = gate_panel()
    px.loc[:"1991-06-30", "VUSTX"] = np.nan                               # 1990년 이후 시작 → 확인 못 함
    assert R7.gate7(px, us3m)["M"]["pass"] is False and "1990" in R7.gate7(px, us3m)["why"]
    px, us3m = gate_panel()
    assert R7.gate7(px, us3m.where(us3m.index > "1995-01-01"))["X"]["status"] == "확인 못 함"   # 3개월 국채 값이 빠짐


def test_gate_runs_on_proxies_and_reports_both_bundles():
    px, us3m = gate_panel()
    g = R7.gate7(px, us3m)
    assert g["M"]["status"] == "ok" and g["X"]["status"] == "ok" and g["from"] == "1987-07-01"
    assert g["M"]["c1"] == (g["M"]["mdd"] >= 0.8 * g["M"]["base_mdd"]) and g["M"]["c2"] == (g["M"]["cagr"] >= g["M"]["base_cagr"] - 0.010)
    assert g["X"]["c1"] == (g["X"]["cagr"] >= g["X"]["base_cagr"] - 0.005)
    assert g["M"]["pass"] == bool(g["M"]["c1"] and g["M"]["c2"] and g["M"]["c3"] is not False)


def cond(cagr_, mdd, mdd_usd, *, b=(0.08, -0.40, -0.50), win=None, **kw):
    w = {f"{a}-{z}": {"s": 0.08, "spy": 0.08} for a, z in R7.WINDOWS7} if win is None else win
    return dict({"liq_cagr": cagr_, "bench_liq_cagr": b[0], "mdd": mdd, "bench_mdd": b[1], "mdd_usd": mdd_usd, "bench_mdd_usd": b[2],
                 "score": (cagr_ - b[0]) + 0.5 * (mdd - b[1]), "windows7": w, "up_capture": 0.95, "down_capture": 0.7, "alpha": 0.01,
                 "dsr_alpha": 0.96, "alpha_t": 2.0}, **kw)


def row(i, group, m, *, static=None, plus=None, promote=True, bench=False, m2=None):
    return {"id": i, "group": group, "hypothesis": "", "benchmark": bench, "static": static, "plus": plus, "promote": promote,
            "cond": {"100M_x1": m, "100M_x2": m2 or m, "10M_x1": m, "10M_x2": m2 or m}}


def fake_res(m1=None, x1=None):
    good = cond(0.078, -0.30, -0.40)
    rows = [row("BM0", "기준선", cond(0.079, -0.36, -0.45), bench=True), row("BXS", "기준선", cond(0.08, -0.36, -0.45), bench=True),
            row("BX0", "기준선", cond(0.07, -0.30, -0.40), bench=True),
            row("R7_M1", "M", m1 or good, static="BM0"), row("R7_M2", "M", good, static="BM0"), row("R7_M3", "M", good, static="BM0"),
            row("R7_M4", "M", cond(0.09, -0.20, -0.30), static="BM0", promote=False),
            row("R7_X1", "X", x1 or cond(0.085, -0.31, -0.41), static="BXS", plus="BX0"), row("R7_X2", "X", good, static="BXS", plus="BX0"),
            row("R7_X3", "X", good, static="BXS", plus="BX0"), row("R7_X4", "X", good, static="BXS", plus="BX0", promote=False)]
    return {"rows": rows}


GATE_OK = {"M": {"pass": True}, "X": {"pass": True}}


def test_eligibility_follows_plan_numbers_and_promotes_one_per_bundle():
    e = R7.eligibility7(fake_res(), GATE_OK, True)
    assert e["by_id"]["R7_M1"]["eligible"] and e["by_id"]["R7_M4"]["eligible"]
    assert e["promoted"] == ["R7_X1", "R7_M1"]                               # 묶음마다 점수 1등, 확인용(M4)은 안 올림, 최대 2개
    assert R7.eligibility7(fake_res(), {"M": {"pass": False}, "X": {"pass": True}}, True)["promoted"] == ["R7_X1"]
    off = R7.eligibility7(fake_res(), GATE_OK, False)                        # SSO 검산 '확인 못 함' → X는 안 올림
    assert off["promoted"] == ["R7_M1"] and "SSO" in off["by_id"]["R7_X1"]["why"]
    for bad, key in ((cond(0.0749, -0.30, -0.40), "2 "), (cond(0.078, -0.371, -0.40), "3 "), (cond(0.078, -0.30, -0.451), "3 "),
                     (cond(0.0759, -0.30, -0.40), "5 "), (cond(0.078, -0.341, -0.40), "5 ")):
        assert R7.eligibility7(fake_res(m1=bad), GATE_OK, True)["by_id"]["R7_M1"]["why"].startswith(key)
    w = {f"{a}-{z}": {"s": 0.08 if (a, z) not in R7.NO_2008 else 0.06, "spy": 0.08} for a, z in R7.WINDOWS7}   # 2008년 낀 3개만 좋음
    assert R7.eligibility7(fake_res(m1=cond(0.078, -0.30, -0.40, win=w)), GATE_OK, True)["by_id"]["R7_M1"]["why"].startswith("4 ")
    res = fake_res(x1=cond(0.078, -0.30, -0.40))
    next(r for r in res["rows"] if r["id"] == "BX0")["cond"]["100M_x1"]["liq_cagr"] = 0.076      # +0.2%p뿐 → 겹치기 비용만 낸 쪽보다 +0.3%p가 아님
    assert R7.eligibility7(res, GATE_OK, True)["by_id"]["R7_X1"]["why"].startswith("5 BX0")


def test_pass_table_verdicts():
    vd = {k: {"krw": -0.10, "spy_krw": -0.13, "usd": -0.12, "spy_usd": -0.15} for k in ("a", "b", "c")}
    res = {"rows": [row("BM0", "기준선", cond(0.07, -0.36, -0.45), bench=True), row("R7_M1", "M", cond(0.078, -0.30, -0.40, valid_drawdowns=vd), static="BM0")]}
    p = R7.pass_table7(res)["R7_M1"]
    assert p["pass"] and p["verdict"].startswith("후보")
    res["rows"][1]["cond"]["100M_x1"]["dsr_alpha"] = 0.5
    assert R7.pass_table7(res)["R7_M1"]["verdict"].startswith("보류")
    res["rows"][1]["cond"]["100M_x1"]["valid_drawdowns"] = {k: dict(v, krw=-0.12) for k, v in vd.items()}   # 1%p만 덜 빠짐
    assert R7.pass_table7(res)["R7_M1"]["verdict"].startswith("탈락")


def test_batch_runs_all_experiments_on_synthetic_prices_and_makes_a_table():
    px, fx = panel(n=1100)
    px["KRWCASH"] = 100 * 1.0001 ** np.arange(len(px))
    res = R7.run_batch7(px, fx, R7.ROUND7, R7.BENCH7, start=px.index[320], end=px.index[-1], conditions=[R7.BASE, (R7.BASE[0], 2.0)], log=lambda s: None)
    assert not [r for r in res["rows"] if "error" in r] and len(res["rows"]) == 15 and res["n_trials"] == 92
    by = {r["id"]: r for r in res["rows"]}
    m = by["R7_M1"]["cond"]["100M_x1"]
    assert {"liq_cagr", "mdd_usd", "alpha_vs_static", "dsr_alpha", "pretax_cagr", "ex0809"} <= set(m) and "_liq" not in m
    assert by["B00"]["cond"]["100M_x1"]["liq_cagr"] == pytest.approx(by["B00"]["cond"]["100M_x1"]["bench_liq_cagr"])
    assert by["R7_M4"]["cond"]["100M_x1"]["trades"] > 0
    elig = R7.eligibility7(res, {"M": {"pass": False}, "X": {"pass": False}}, False)
    assert elig["promoted"] == []
    md = R7.table7(res, "dev", 93, elig, None, {"확인": {"a": 1}})
    assert "실험실 7차 · Fable 설계 #93" in md and "없음 → 검증을 열지 않고 라운드 종료" in md and "R7_X4" in md
