import math
from datetime import date

import numpy as np
import pandas as pd

from quant import market as MK
from quant import news_features as NF


def _px(vals):
    return pd.Series(vals, index=pd.bdate_range("2023-01-02", periods=len(vals)), dtype=float)


def test_trend_light_and_breadth():
    up = _px(np.linspace(100, 200, 260))
    down = _px(np.linspace(200, 100, 260))
    assert MK.trend_light(up)["state"] == "green" and MK.trend_light(up)["gap_pct"] > 0
    assert MK.trend_light(down)["state"] == "red"
    assert MK.trend_light(up.iloc[:50])["state"] is None
    b = MK.breadth(pd.DataFrame({"TEST01": up, "TEST02": down, "TEST03": up.iloc[:50]}))
    assert b == {"above": 1, "total": 2}


def test_relative_strength_and_move_z():
    idx = pd.bdate_range("2023-01-02", periods=130)
    prices = pd.DataFrame({"TEST01": 100 * 1.002 ** np.arange(130), "TEST02": 100 * 0.999 ** np.arange(130)}, index=idx)
    bench = pd.Series(100 * 1.001 ** np.arange(130), index=idx)
    rs = MK.relative_strength(prices, bench, 63)
    assert rs["TEST01"] > 0 > rs["TEST02"]
    rng = np.random.default_rng(0)
    s = pd.Series(np.cumprod(1 + rng.normal(0, 0.01, 80)), index=pd.bdate_range("2023-01-02", periods=80))
    s.iloc[-1] = s.iloc[-2] * 1.05
    z = MK.move_z(s)
    assert z["z"] > 2
    assert MK.move_z(s.iloc[:10])["z"] is None


def test_session_date_cutoff_and_weekend():
    assert NF.session_date("2024-03-05T20:59:00+00:00") == date(2024, 3, 5)   # 15:59 ET
    assert NF.session_date("2024-03-05T21:00:00+00:00") == date(2024, 3, 6)   # 16:00 ET → 다음 날
    assert NF.session_date("2024-03-08T22:00:00+00:00") == date(2024, 3, 11)  # 금요일 장 후 → 월요일
    assert NF.session_date("2024-03-09T15:00:00+00:00") == date(2024, 3, 11)  # 토요일
    try:
        NF.session_date("2024-03-05T10:00:00")
        assert False
    except ValueError:
        pass


def _n(h, title, ts, tickers=("TEST01",)):
    return {"url_hash": h, "url": f"https://example.com/{h}", "title": title, "published_at": ts, "tickers": list(tickers), "source": "fake"}


def test_dedupe_and_features():
    rows = [
        _n("a", "합성 헤드라인: 가짜종목A 신제품", "2024-03-05T14:00:00+00:00"),
        _n("a", "합성 헤드라인: 가짜종목A 신제품", "2024-03-05T14:00:00+00:00"),       # 같은 URL
        _n("b", "합성 헤드라인 — 가짜종목A 신제품!", "2024-03-05T15:00:00+00:00"),     # 같은 제목(기호 무시)
        _n("c", "합성 헤드라인: 가짜종목A 실적 좋음", "2024-03-05T16:00:00+00:00"),
    ]
    assert len(NF.dedupe(rows)) == 2
    hist = [_n(f"h{i}", f"합성 기사 {i}", f"2024-02-{i:02d}T14:00:00+00:00") for i in range(1, 29) if date(2024, 2, i).weekday() < 5]
    feats = NF.daily_features(hist + rows, score_fn=lambda t: 1.0 if "좋음" in t else 0.0)
    today = feats.loc[("TEST01", pd.Timestamp("2024-03-05"))]
    assert today["news_count"] == 2
    assert today["news_abn"] > 1.5          # 평소 하루 1건 수준 → 2건
    assert today["news_sent"] == 0.5
    empty = NF.daily_features([])
    assert list(empty.columns) == ["news_count", "news_abn", "news_sent", "news_sent_decay"]
    no_score = NF.daily_features(rows)
    assert math.isnan(no_score.iloc[0]["news_sent"])
