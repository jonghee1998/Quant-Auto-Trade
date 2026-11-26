import json

import numpy as np
import pandas as pd

from quant import snapshot as SN


def _px():
    idx = pd.bdate_range("2023-01-02", periods=300)
    cols = {"SPY": 1.0005, "QQQ": 1.0007, "EWY": 0.9998, "XLK": 1.001, "XLE": 0.999, "EWJ": 1.0003, "AAPL": 1.0004}
    return pd.DataFrame({c: 100 * g ** np.arange(300) for c, g in cols.items()}, index=idx)


def test_build_payload_shape_and_nulls():
    idx = pd.bdate_range("2023-01-02", periods=300)
    macro = {"VIXCLS": pd.Series(np.r_[np.full(299, 15.0), 22.0], index=idx), "DEXKOUS": pd.Series(np.linspace(1300, 1390, 300), index=idx)}
    news = [{"title": "합성 헤드라인", "source": "finnhub"}, {"title": "합성 기사", "source": "naver"}]
    p = SN.build_payload(_px(), macro, news, as_of="2024-02-23")
    json.dumps(p)  # JSON 직렬화 가능(NaN 없음)
    assert "NaN" not in json.dumps(p)
    q = {x["id"]: x for x in p["quotes"]}
    assert q["vix"]["value"] == 22.0 and q["vix"]["changeText"] == "+7.0"
    assert q["spx"]["m1"] > 0 and q["korea"]["m1"] < 0
    assert p["trendLight"]["state"] == "green"
    assert p["breadth"] == {"above": 1, "total": 2}
    kinds = {(u["market"], u["kind"]) for u in p["universe"]}
    assert ("US", "업종") in kinds and ("W", "나라") in kinds and ("US", "주식") in kinds
    assert "미국은" in p["summary"] and "VIX" in p["summary"]
    assert [n["where"] for n in p["news"]] == ["미국", "한국"]


def test_missing_data_becomes_null():
    p = SN.build_payload(pd.DataFrame(), {}, [], as_of=None)
    assert all(q["value"] is None for q in p["quotes"])
    assert p["trendLight"]["state"] is None and p["universe"] == []
    assert "아직" in p["summary"]
