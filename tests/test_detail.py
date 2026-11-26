import json

import numpy as np
import pandas as pd

from quant import detail as DT


def _s(vals, start="2023-01-02"):
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)), dtype=float)


def test_price_stats_known_values():
    # 100 → 120 → 90 → 110: 최대 낙폭 −25%, 52주 위치 (110−90)/(120−90)=67%
    s = _s(np.r_[np.linspace(100, 120, 100), np.linspace(120, 90, 100), np.linspace(90, 110, 52)])
    st = DT.price_stats(s, bench=s * 2)
    assert st["mdd"] == -25.0 and st["pos"] == 67 and st["high"] == 120 and st["low"] == 90
    assert st["beta"] == 1.0  # 같은 움직임이면 베타 1
    assert st["ma200"] is not None and st["vol"] > 0


def test_price_stats_short_series():
    assert DT.price_stats(_s([1, 2, 3])) == {"days": 3}


def test_weekly_chart_ends_on_last_value():
    s = _s(np.arange(1, 400))
    c = DT.weekly_chart(s)
    assert 50 <= len(c) <= 54 and c[-1][1] == 399.0 and c[-1][0] <= s.index[-1].strftime("%Y-%m-%d")


def test_level_stats_and_related():
    s = _s(np.r_[np.full(2000, 20.0), np.linspace(10, 30, 500)])
    lv = DT.level_stats(s)
    assert lv["pos"] == 100 and lv["max10"] == 30 and lv["min10"] == 10
    rel = DT.related({"T10Y2Y": _s([0.5, -0.2]), "NFCI": _s([-0.4])})
    assert [r["state"] for r in rel] == ["돈 구하기 쉬움", "역전(경기 둔화 신호로 봄)"]


def test_fundamentals_quarters_yoy_per_pbr_and_restatement():
    rows = []
    for i, (end, rev) in enumerate([("2023-03-31", 100), ("2023-06-30", 110), ("2024-03-31", 120), ("2024-06-30", 132)]):
        e = pd.Timestamp(end)
        rows.append({"concept": "revenue", "period_start": e - pd.Timedelta(days=89), "period_end": e, "value": rev, "filed_date": e + pd.Timedelta(days=30)})
    rows.append({"concept": "revenue", "period_start": pd.Timestamp("2024-04-02"), "period_end": pd.Timestamp("2024-06-30"),
                 "value": 999, "filed_date": pd.Timestamp("2023-01-01")})  # 다른 기간(시작일 다름) — 별개 행
    rows.append({"concept": "revenue", "period_start": pd.Timestamp("2024-06-30") - pd.Timedelta(days=89), "period_end": pd.Timestamp("2024-06-30"),
                 "value": 143, "filed_date": pd.Timestamp("2024-12-01")})  # 정정: 늦게 접수된 값
    rows.append({"concept": "eps_diluted", "period_start": pd.Timestamp("2023-01-01"), "period_end": pd.Timestamp("2023-12-31"), "value": 5, "filed_date": pd.Timestamp("2024-02-01")})
    rows.append({"concept": "equity", "period_start": None, "period_end": pd.Timestamp("2024-06-30"), "value": 1000, "filed_date": pd.Timestamp("2024-08-01")})
    rows.append({"concept": "shares", "period_start": None, "period_end": pd.Timestamp("2024-06-30"), "value": 100, "filed_date": pd.Timestamp("2024-08-01")})
    f = DT.fundamentals_view(pd.DataFrame(rows), price=50.0)
    last = f["quarters"][-1]
    assert last["end"] == "2024-06-30" and last["revenue"] == 143 and last["revYoY"] == 30.0  # 143/110
    assert f["per"] == 10.0 and f["epsYear"] == "2023" and f["pbr"] == 5.0


def test_build_is_json_safe():
    idx = pd.bdate_range("2023-01-02", periods=300)
    us = pd.DataFrame({"SPY": np.linspace(100, 130, 300), "XLK": np.linspace(50, 80, 300)}, index=idx)
    kr = pd.DataFrame({"KOSPI": np.linspace(2000, 2500, 300), "TEST01": np.r_[np.full(150, np.nan), np.linspace(1, 2, 150)]}, index=idx)
    payload = {"universe": [{"market": "US", "code": "XLK"}, {"market": "KR", "code": "TEST01"}, {"market": "KR", "code": "NONE"}]}
    out = DT.build(payload, us, kr, {"VIXCLS": pd.Series(np.linspace(15, 25, 300), index=idx)}, {})
    assert set(out) >= {"US:XLK", "KR:TEST01", "Q:spx", "Q:korea", "Q:vix"} and "KR:NONE" not in out
    json.dumps(out, allow_nan=False)
