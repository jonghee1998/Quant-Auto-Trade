"""실험실 2차(Fable 설계 #59) 규칙 전략·실행기 테스트. 합성 시세만 쓴다(인터넷·DB 없음)."""
import numpy as np
import pandas as pd
import pytest

from quant.forecast import rules as R
from quant.lab.backtest import Costs, _rebalance_days, run_backtest
from quant.lab.cli import div_yield_from_factors

TICKERS = ["SPY", "SHY", "SSO"] + R.SECTORS


def synth(n=900, seed=1, start="2010-01-04"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    r = rng.normal(0.0004, 0.012, (n, len(TICKERS)))
    r[:, 1] = rng.normal(0.0001, 0.001, n)       # SHY 조용
    r[:, 2] = 2 * r[:, 0]                          # SSO = SPY 2배
    return pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=TICKERS)


def decisions(strat_factory, px, rule, upto):
    """rule 리밸런싱 날마다 weights를 부른 결과(upto 이전까지)."""
    s = strat_factory()
    out = []
    for d in sorted(_rebalance_days(px.index[px.index >= px.index[300]], rule)):
        if d > upto:
            break
        out.append((d, s.weights(d, px.loc[:d])))
    return out


class FakeRanker:
    """과거 12-1개월 수익을 점수로 쓰는 가짜 예측기(미래를 안 봄)."""

    def rank(self, as_of, history):
        m = R.mom12_1(history, R.SECTORS)
        return m if len(m) >= 3 else None

    def ic(self):
        return {"ic_mean": 0.01}


FACTORIES = {
    "A01": (lambda: R.VolTarget("A01"), "W"),
    "A02": (lambda: R.TrendSwitch("A02", band=0.0), "M"),
    "A03": (lambda: R.TrendSwitch("A03", band=0.02), "W"),
    "A04": (lambda: R.VolTarget("A04", trend=R.TrendState(band=0.02)), "W"),
    "L02": (lambda: R.VolTarget("L02", cap=1.5, trend=R.TrendState(band=0.02)), "W"),
    "K01": (lambda: R.SectorHold("K01"), "M"),
    "K03": (lambda: R.RankHold("K03", FakeRanker(), core=0.7), "M"),
    "BEQ": (lambda: R.FixedMix("BEQ"), "M"),
}


@pytest.mark.parametrize("name", list(FACTORIES))
def test_future_prices_do_not_change_todays_decision(name):
    fac, rule = FACTORIES[name]
    px = synth()
    cut = px.index[650]
    future = px.copy()
    future.loc[future.index > cut] *= np.linspace(0.3, 3.0, (future.index > cut).sum())[:, None]
    a, b = decisions(fac, px, rule, cut), decisions(fac, future, rule, cut)
    assert len(a) > 5 and a == b


def test_trend_state_hysteresis():
    st = R.TrendState(window=5, band=0.02)
    s = lambda *v: pd.Series(v, dtype=float)  # noqa: E731
    assert st.update(s(100, 100, 100, 100, 100)) is False          # 시작은 보유
    assert st.update(s(100, 100, 100, 100, 99)) is False           # 평균의 98% 위 → 그대로
    assert st.update(s(100, 100, 100, 100, 90)) is True            # 98% 아래 → 피함
    assert st.update(s(100, 100, 100, 100, 101)) is True           # 102% 안 넘음 → 그대로 피함
    assert st.update(s(100, 100, 100, 100, 110)) is False          # 102% 위 → 보유


def test_alloc_leverage_only_with_sso():
    assert R.alloc(1.5, True) == {"SSO": 0.5, "SPY": 0.5}         # 0.5×2 + 0.5 = 1.5배
    assert R.alloc(1.5, False) == {"SPY": 1.0}
    assert R.alloc(0.6, True) == pytest.approx({"SPY": 0.6, "SHY": 0.4})
    assert R.alloc(0.0, True) == {"SHY": 1.0}


def test_vol_target_caps_at_one_when_sso_missing():
    px = synth()
    px.loc[:, "SSO"] = np.nan
    s = R.VolTarget("L01", target=10.0, cap=1.5)   # 목표가 매우 높아 상한에 걸림
    w = s.weights(px.index[400], px.loc[: px.index[400]])
    assert w == {"SPY": 1.0} and s.exposures[-1][1] == 1.0


def test_no_trades_inside_band():
    """변동성이 일정하면 첫 매수 뒤 매매 0건(띠 10%p 안)."""
    idx = pd.bdate_range("2010-01-04", periods=400)
    r = np.tile([0.01, -0.0099], 200)
    px = pd.DataFrame({"SPY": 100 * np.cumprod(1 + r), "SHY": 100.0}, index=idx)
    fx = pd.Series(1200.0, index=idx)
    res = run_backtest(px, fx, R.VolTarget("A01"), idx[60], None, rebalance="W", costs=Costs())
    buy_days = {t["date"] for t in res.trades}
    assert len(buy_days) == 1


def test_hold_rule_keeps_top5_and_swaps_only_when_pushed_out():
    h = R.HoldRule(top=3, keep=5)
    assert h.step(list("ABCDEFG")) == ["A", "B", "C"]
    assert h.step(list("DEABCFG")) is None                         # A·B·C 모두 5위 안 → 유지
    assert h.step(list("DEFGHABC")) == ["D", "E", "F"]             # 모두 6위 밖 → 위에서부터
    assert h.step(list("DXYZEFQ")) == ["D", "E", "X"]              # F가 6위 → 안 가진 최상위 X로


def test_k03_core_and_drift_band():
    px = synth()
    s = R.RankHold("K03", FakeRanker(), core=0.7, band=0.05)
    d0 = px.index[400]
    w = s.weights(d0, px.loc[:d0])
    assert w["SPY"] == pytest.approx(0.7) and sum(w.values()) == pytest.approx(1.0)
    # 다음 달: 같은 3개면 SPY가 크게 벗어날 때만 매매
    px2 = px.copy()
    d1 = px.index[421]
    px2.loc[px.index > d0, "SPY"] *= 3.0
    s2 = R.RankHold("K03", FakeRanker(), core=0.7, band=0.05)
    s2.weights(d0, px2.loc[:d0])
    s2.rule.step = lambda ranked: None                              # 교체 없음으로 고정
    assert s2.weights(d1, px2.loc[:d1]) is not None                 # 벗어남 > 5%p → 다시 맞춤


def test_fixed_mix_rebalances_only_in_december():
    px = synth(n=600)
    s = R.FixedMix("B80", {"SPY": 0.8, "SHY": 0.2})
    days = sorted(_rebalance_days(px.index, "M"))
    out = [(d.month, s.weights(d, px.loc[:d])) for d in days]
    assert out[0][1] == {"SPY": 0.8, "SHY": 0.2}
    assert all((w is None) == (m != 12) for m, w in out[1:])


def test_div_yield_from_factors_ignores_splits():
    d = pd.bdate_range("2020-01-01", periods=4)
    df = pd.DataFrame({"code": ["X"] * 4, "date": d, "adj_factor": [0.98, 0.98, 0.99, 0.495]})
    y = div_yield_from_factors(df)
    assert list(y.index) == [d[2]] and y.loc[d[2], "X"] == pytest.approx(0.99 / 0.98 - 1)


def _fake_exps():
    from quant.forecast.experiments import Exp
    return ([Exp("A01", "A", "h", lambda px, mf: R.VolTarget("A01"), "W"),
             Exp("A03", "A", "h", lambda px, mf: R.TrendSwitch("A03", band=0.02), "W"),
             Exp("K01", "K", "h", lambda px, mf: R.SectorHold("K01"), "M")],
            [Exp("BEQ", "기준선", "h", lambda px, mf: R.FixedMix("BEQ"), "M")])


def test_run_batch_four_conditions_and_shared_trial_count():
    from quant.forecast.run import CONDITIONS, cond_key, eligibility, run_batch, table
    px = synth(n=2600, start="2007-01-01")
    fx = pd.Series(1100.0, index=px.index)
    exps, bench = _fake_exps()
    res = run_batch(px, fx, exps, bench, pd.DataFrame(index=px.index), period="dev", log=lambda s: None)
    rows = {r["id"]: r for r in res["rows"]}
    assert all("error" not in r for r in rows.values())
    a = rows["A01"]["cond"]
    assert set(a) == {cond_key(c) for c in CONDITIONS}
    # 비용 2배면 청산 세후가 낮다, 자금이 다르면(공제 250만 원의 무게) 청산 세후도 다르다
    assert a["100M_x2"]["liq_cagr"] < a["100M_x1"]["liq_cagr"]
    assert a["10M_x1"]["liq_cagr"] != a["100M_x1"]["liq_cagr"]
    # 시도 수는 묶음 전체 같은 값(개발: 이전 37 + 2차 11 = 48), 기준선은 DSR 없음
    assert {rows[i]["cond"]["100M_x1"]["n_trials"] for i in ("A01", "A03", "K01")} == {48}
    assert "dsr_excess" not in rows["BEQ"]["cond"]["100M_x1"]
    assert set(res["daily"]["A01"].columns) == {"nav", "bench", "equity"}
    elig = eligibility(res["rows"])
    assert len(elig["promoted"]) <= 2 and len({rows[i]["group"] for i in elig["promoted"]}) == len(elig["promoted"])
    assert "실험실 2차" in table(res, "dev", elig)


def test_eligibility_rules_follow_plan():
    from quant.forecast.run import eligibility

    def row(i, g, score, score2=None, mdd=-0.1, bmdd=-0.2, liq=0.1, ic=None):
        m = {"score": score, "mdd": mdd, "bench_mdd": bmdd, "liq_cagr": liq}
        return {"id": i, "group": g, "benchmark": False, "ic": ic or {},
                "cond": {"100M_x1": m, "100M_x2": dict(m, score=score if score2 is None else score2)}}

    rows = [row("A01", "A", 0.03), row("A02", "A", -0.01), row("A03", "A", -0.01), row("A04", "A", 0.05),
            row("L01", "L", 0.04, mdd=-0.3), row("L02", "L", 0.02, score2=-0.01),
            row("T07", "T", 0.01, ic={"hit": 0.7, "base_rate": 0.65, "brier": 0.2}),
            row("K01", "K", 0.02, liq=0.05), row("K02", "K", 0.06, liq=0.2, ic={"ic_mean": 0.02}),
            row("K03", "K", 0.07, liq=0.2, ic={"ic_mean": 0.02}),
            {"id": "BEQ", "group": "기준선", "benchmark": True, "cond": {"100M_x1": {"liq_cagr": 0.08}}}]
    e = eligibility(rows)
    b = e["by_id"]
    assert not b["A04"]["eligible"]            # A02·A03 점수 ≤ 0
    assert not b["L01"]["eligible"]            # 최악 손실이 S&P보다 큼
    assert not b["L02"]["eligible"]            # 비용 2배 점수 ≤ 0
    assert b["T07"]["eligible"]                # 적중 0.70 > 0.65, 브라이어 0.20 < 0.2275
    assert not b["K01"]["eligible"]            # BEQ보다 낮음
    assert b["K02"]["eligible"] and b["K03"]["eligible"]
    assert e["promoted"] == ["K03", "A01"]     # 점수 순, 묶음마다 1개, 최대 2개
