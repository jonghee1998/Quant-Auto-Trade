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


def test_pick_kr_by_traded_value_and_excludes_leveraged():
    idx = pd.bdate_range("2024-01-02", periods=30)
    rows = []
    spec = [("TEST01", "가짜종목A", "stock", 1000, 10), ("TEST02", "가짜종목B", "stock", 10, 10),
            ("TEST03", "가짜ETF 레버리지", "etf", 1000, 100), ("TEST04", "가짜ETF", "etf", 500, 10), ("069500", "기준ETF", "etf", 100, 1), ("KOSPI", "코스피", "index", 2500, 0)]
    for code, name, kind, close, vol in spec:
        rows += [{"code": code, "name": name, "kind": kind, "date": d, "close": close * (1 + i / 100), "volume": vol} for i, d in enumerate(idx)]
    px, stocks, etfs = SN.pick_kr(pd.DataFrame(rows), n_stock=1, n_etf=5)
    assert stocks == {"TEST01": "가짜종목A"} and "TEST03" not in etfs and "TEST04" in etfs
    assert "069500" in px.columns and "TEST02" not in px.columns
    p = SN.build_payload(_px(), {}, [], px, stocks, as_of="2024-02-12", kr_etf_names=etfs)
    kinds = {(u["market"], u["kind"]) for u in p["universe"]}
    assert ("KR", "주식") in kinds and ("KR", "업종") in kinds
    assert p["bench"]["KR"][0] is not None
    q = {x["id"]: x for x in p["quotes"]}
    assert q["korea"]["name"] == "한국 코스피" and q["korea"]["m1"] > 0  # EWY(달러)가 아니라 실제 지수


def test_pick_news_balances_and_dedupes():
    news = [{"title": f"합성 미국 {i}", "source": "finnhub"} for i in range(5)]
    news += [{"title": "합성 증시 마감", "source": "google_news"}, {"title": "합성 증시 마감!", "source": "google_news"},
             {"title": "합성 환율", "source": "google_news"}]
    p = SN.pick_news(news)
    assert [x["where"] for x in p] == ["미국"] * 3 + ["한국"] * 2
    assert [x["title"] for x in p if x["where"] == "한국"] == ["합성 증시 마감", "합성 환율"]


def test_pick_news_prefers_market_news_and_drops_pr_and_clickbait():
    news = [
        {"title": "합성기업 Launches Center of Excellence", "source": "finnhub", "publisher": "GlobeNewswire"},
        {"title": "2 Ways 합성기업 Pays Off for Investors", "source": "finnhub", "publisher": "Motley Fool"},
        {"title": "Should You Buy 합성기업 Stock?", "source": "finnhub", "publisher": "Zacks"},
        {"title": "합성 종목 실적 발표", "source": "finnhub", "publisher": "합성통신"},
        {"title": "합성국 elections near as leader seeks reelection - Reuters", "source": "finnhub_market", "publisher": "합성통신"},
        {"title": "Stocks fall as yields climb (합성) - Reuters", "source": "finnhub_market", "publisher": "합성통신"},
        {"title": "Fed holds rates (합성)", "source": "finnhub_market", "publisher": "합성통신"},
    ]
    p = SN.pick_news(news)
    assert [x["title"] for x in p] == ["Stocks fall as yields climb (합성)", "Fed holds rates (합성)", "합성 종목 실적 발표"]


def test_signals_three_lights():
    idx = pd.bdate_range("2023-01-02", periods=300)
    up = pd.Series(100 * 1.001 ** np.arange(300), index=idx)
    px = pd.DataFrame({"SPY": up, **{c: up for c in ["XLK", "XLF", "XLE", "XLV"]}})
    calm = {"VIXCLS": pd.Series(15.0, index=idx), "VXVCLS": pd.Series(18.0, index=idx),
            "BAMLH0A0HYM2": pd.Series(3.0, index=idx)}
    s = SN.signals(px, calm)
    assert s["state"] == "green" and [i["good"] for i in s["items"]] == [True, True, True]
    scared = dict(calm, VIXCLS=pd.Series(25.0, index=idx))
    assert SN.signals(px, scared)["state"] == "yellow"
    down = px.iloc[::-1].set_axis(idx)  # 하락 추세
    assert SN.signals(down, scared)["state"] == "red"
    assert SN.signals(px, {})["state"] is None  # 위험 데이터 없으면 판단 안 함


def test_coverage_counts():
    uni = [{"market": "KR", "kind": "주식"}] * 3 + [{"market": "US", "kind": "업종"}] * 2
    c = SN.coverage(uni, {"stock": 2879})
    assert c["KR/주식"] == {"shown": 3, "total": 2879, "note": "거래대금 상위"}
    assert c["US/업종"]["note"] == "직접 고른 대표 목록" and "total" not in c["US/업종"]
