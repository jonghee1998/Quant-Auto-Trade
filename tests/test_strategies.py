import numpy as np
import pandas as pd

from quant.lab.backtest import Costs
from quant.lab.cli import card
from quant.lab.run import evaluate
from quant.lab.splits import Splits
from quant.strategies import REGISTRY
from quant.strategies.sector_momentum import SectorMomentum


def _prices(n=600):
    idx = pd.bdate_range("2015-01-01", periods=n)
    g = {"SPY": 1.0004, "XLK": 1.0010, "XLE": 0.9995, "XLF": 1.0002, "XLV": 1.0001}
    return pd.DataFrame({k: 100 * v ** np.arange(n) for k, v in g.items()}, index=idx)


def test_sector_momentum_picks_strongest_and_respects_history():
    p = _prices()
    w = SectorMomentum(top=2, lookback=63, trend_window=200).weights(p.index[-1], p)
    assert set(w) == {"XLK", "XLF"} and abs(sum(w.values()) - 1) < 1e-9
    assert SectorMomentum(top=2, lookback=63).weights(p.index[30], p.iloc[:31]) == {}  # 기록이 모자라면 아무것도 안 삼
    down = p.copy()
    down["SPY"] = 100 * 0.999 ** np.arange(len(p))
    assert SectorMomentum(top=2, lookback=63, trend_window=200).weights(down.index[-1], down) == {}  # 시장 추세 아래면 현금


def test_registry_strategies_run_and_card():
    p = _prices(800)
    fx = pd.Series(1300.0, index=p.index)
    sp = Splits(dev=("2015-01-01", "2016-12-31"), valid=("2017-01-01", "2017-12-31"), holdout=("2018-01-01", None))
    for name, (make, hyp, params) in REGISTRY.items():
        m = evaluate(p, fx, make(), hypothesis=hyp, params=params, period="dev", splits=sp, costs=Costs(fee=0, fx_spread=0, slippage=0))
        assert m["cagr"] == m["cagr"]
        text = card(name, "dev", m)
        assert "S&P 그냥 보유" in text and "nan" not in text.lower()
