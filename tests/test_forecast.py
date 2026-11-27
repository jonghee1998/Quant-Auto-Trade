"""예측 실험의 누수 검사: 미래를 바꿔도 오늘 결정이 같아야 한다."""
import numpy as np
import pandas as pd
import pytest

from quant.forecast import features as F
from quant.forecast.strategy import ForecastRanker, MarketTimer
from quant.lab.backtest import _rebalance_days

TICKERS = ["SPY", "SHY", "FAKE1", "FAKE2", "FAKE3", "FAKE4", "FAKE5", "FAKE6"]


def _px(n=900, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-04", periods=n)
    r = rng.normal(0.0003, 0.01, (n, len(TICKERS)))
    r[:, 1] = rng.normal(0.0001, 0.001, n)
    return pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=TICKERS)


def _macro(idx):
    rng = np.random.default_rng(1)
    rows = lambda vals: pd.DataFrame({"ref_date": idx, "release_date": idx + pd.DateOffset(days=1), "value": vals})  # noqa: E731
    m = {"VIXCLS": rows(15 + rng.normal(0, 3, len(idx)).cumsum() * 0.05 + 5), "VXVCLS": rows(np.full(len(idx), 18.0)),
         "BAMLH0A0HYM2": rows(4 + rng.normal(0, 0.05, len(idx)).cumsum()), "USEPUINDXD": rows(np.exp(rng.normal(4.5, 0.3, len(idx))))}
    return F.macro_panel(m, idx)


def test_price_features_use_only_past():
    px = _px()
    full = F.price_panel(px)
    t = px.index[600]
    cut = F.price_panel(px.loc[:t])
    for k in F.PRICE_FEATS:
        pd.testing.assert_series_equal(full[k].loc[t], cut[k].loc[t], check_names=False)


def test_asof_series_waits_for_release_and_takes_latest_reference():
    dates = pd.bdate_range("2024-01-01", periods=10)
    rows = pd.DataFrame({"ref_date": ["2023-12-01", "2024-01-01"], "release_date": ["2024-01-03", "2024-01-08"], "value": [1.0, 2.0]})
    s = F.asof_series(rows, dates)
    assert np.isnan(s["2024-01-02"]) and s["2024-01-03"] == 1.0 and s["2024-01-05"] == 1.0 and s["2024-01-08"] == 2.0


def test_training_dates_purge_and_embargo():
    idx = pd.bdate_range("2020-01-01", periods=300)
    as_of = idx[250]
    d = F.training_dates(idx, as_of, h=21, embargo=5, step=1)
    last = idx.get_loc(d[-1])
    assert last + 21 + 5 <= 250 and last + 21 + 5 == 250


@pytest.mark.parametrize("model", ["ridge", "hgb"])
@pytest.mark.parametrize("feats", ["P", "PMN"])
def test_ranker_decision_ignores_future(model, feats):
    px = _px()
    as_of = px.index[700]
    fut = px.copy()
    fut.loc[fut.index > as_of] *= np.random.default_rng(9).uniform(0.5, 1.5, fut.loc[fut.index > as_of].shape)
    w, preds = [], []
    for p in (px, fut):
        s = ForecastRanker("t", p, _macro(p.index), TICKERS[2:] + ["SPY"], feats=feats, model=model, top=2, min_hist=200)
        w.append(s.weights(as_of, p.loc[:as_of]))
        preds.append(s.preds[-1][1])
    assert w[0] == w[1] and w[0]
    pd.testing.assert_series_equal(preds[0], preds[1])  # 예측값 자체가 같아야(순위만 같은 게 아니라)


def test_timer_decision_ignores_future():
    px = _px()
    as_of = px.index[750]
    fut = px.copy()
    fut.loc[fut.index > as_of] *= 0.3
    ps = [MarketTimer("t", p, _macro(p.index), model="logit", mode="scaled").prob(as_of) for p in (px, fut)]
    assert ps[0] == ps[1] and ps[0] is not None


def test_weekly_rebalance_is_last_day_of_each_week():
    idx = pd.bdate_range("2024-01-01", periods=15)  # 월~금 3주
    days = sorted(_rebalance_days(idx, "W"))
    assert [d.day_name() for d in days] == ["Friday"] * 3


def test_all_thirty_experiments_build():
    from quant.forecast.experiments import ROUND1 as EXPERIMENTS, UNIVERSE
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2010-01-04", periods=400)
    cols = UNIVERSE + ["SHY"]
    px = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (400, len(cols))), axis=0)), index=idx, columns=cols)
    mf = F.macro_panel({}, idx)
    assert len(EXPERIMENTS) == 30
    for e in EXPERIMENTS:
        s = e.build(px, mf)
        assert s.name == e.id and e.rebalance in ("M", "W")
