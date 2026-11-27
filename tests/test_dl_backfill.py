"""딥러닝 트랙 자료: 구성종목 표본(해시·재현), 그날 구성종목, 백필(가짜 R2·가짜 Tiingo), 0단계 관문. 인터넷 없음."""
import json

import pandas as pd

from quant.dl import backfill as B
from quant.dl import members as M
from quant.ingest.http import Response

CSV = """ticker,start_date,end_date
TEST01,1996-01-02,
TEST02,1999-12-08,2010-06-19
TEST03,2001-03-23,2004-09-23
TEST03,2015-03-23,
TEST04,1990-01-02,2001-01-15
TEST05,2019-01-02,
"""


def test_sample_is_hash_ordered_and_window_filtered():
    sp = M.parse(CSV)
    s = M.sample(sp, n=10)
    assert "TEST04" not in s and set(s) == {"TEST01", "TEST02", "TEST03", "TEST05"}
    assert s == sorted(s, key=M.key) and M.sample(sp, n=2) == s[:2]


def test_members_on_day():
    sp = M.parse(CSV)
    assert M.members_on(sp, "2003-06-02") == {"TEST01", "TEST02", "TEST03"}
    assert M.members_on(sp, "2010-06-19") == {"TEST01"}      # 편출일에는 빠짐


class FakeR2:
    def __init__(self):
        self.d = {}

    def put(self, n, b):
        self.d[n] = b

    def get(self, n):
        return self.d.get(n)

    def put_json(self, n, o):
        self.d[n] = json.dumps(o).encode()

    def get_json(self, n, default=None):
        return json.loads(self.d[n]) if n in self.d else default

    def put_frame(self, n, df):
        self.d[n] = df


def test_backfill_batches_records_missing_and_stops_on_rate_limit():
    calls = []

    def fetch(url, params=None, headers=None):
        if "raw.githubusercontent" in url:
            return Response(200, CSV)
        t = url.split("/daily/")[1].split("/")[0].upper()
        calls.append(t)
        if t == "TEST02":
            return Response(404, "not found")
        if t == "TEST05":
            return Response(429, "limit")
        return Response(200, json.dumps([{"date": "2003-01-02T00:00:00", "close": 10, "adjClose": 9},
                                         {"date": "2022-12-30T00:00:00", "close": 12, "adjClose": 12}]))
    r2 = FakeR2()
    sample = M.sample(M.parse(CSV), 10)
    out = B.run(r2, fetch, "FAKE", n=10, batch=10, log=lambda s: None)
    man = json.loads(r2.d["manifest.json"])
    assert man["TEST02"]["rows"] == 0                        # 사라진 회사: '없음'으로 기록
    assert "TEST05" not in man and not out["done"]            # 한도에 걸리면 기록하지 않고 멈춤(다음에 이어 받기)
    stop = sample.index("TEST05")
    assert all(t in man for t in sample[:stop])
    cov = out["coverage"]
    assert cov["gone"] >= 1 and 0 <= cov["share"] <= 1


def test_dotted_ticker_uses_dash_for_tiingo():
    seen = []

    def fetch(url, params=None, headers=None):
        if "raw.githubusercontent" in url:
            return Response(200, "ticker,start_date,end_date\nTEST.B,2000-01-03,\n")
        seen.append(url.split("/daily/")[1].split("/")[0])
        return Response(200, json.dumps([{"date": "2003-01-02T00:00:00", "close": 10, "adjClose": 10}]))
    r2 = FakeR2()
    r2.put_json("manifest.json", {"TEST.B": {"first": None, "last": None, "rows": 0}})
    B.run(r2, fetch, "FAKE", n=5, batch=5, log=lambda s: None)
    assert seen == ["test-b"] and json.loads(r2.d["manifest.json"])["TEST.B"]["rows"] == 1


def _zip(text):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("supported_tickers.csv", text)
    return buf.getvalue()


def test_probe_classifies_missing_tickers_against_tiingo_list():
    from quant.dl import probe as P
    listed = ("ticker,exchange,assetType,priceCurrency,startDate,endDate\n"
              "TEST02,NYSE,Stock,USD,1999-01-04,2010-06-18\n"      # 목록에는 있고 기간도 덮음 → A
              "TEST03,NYSE,Stock,USD,2015-03-23,2022-12-30\n"      # 같은 기호의 뒤 기간만 → B
              "TEST05,NYSE,ETF,USD,2019-01-02,2022-12-30\n")       # 주식이 아님 → 없는 것으로

    def fetch(url, params=None, headers=None):
        if "raw.githubusercontent" in url:
            return Response(200, CSV)
        return Response(200, "", _zip(listed))
    r2 = FakeR2()
    r2.put_json("manifest.json", {"TEST01": {"first": "2003-01-02", "last": "2022-12-30", "rows": 5000},
                                  "TEST02": {"first": None, "last": None, "rows": 0}, "TEST03": {"first": "2015-03-23", "last": "2022-12-30", "rows": 1900},
                                  "TEST05": {"first": None, "last": None, "rows": 0}})
    sp = M.parse(CSV)
    r = P.classify(sp, r2.get_json("manifest.json"), M.sample(sp, 10), P.supported(fetch))
    assert (r["done"], r["covered"], r["gone"], r["gone_covered"]) == (4, 1, 2, 0)
    assert r["classes"] == {"A": 1, "B": 1, "C": 1}
    assert {x["ticker"]: x["class"] for x in r["rows"]} == {"TEST02": "A", "TEST03": "B", "TEST05": "C"}
    assert r["best_if_A_fixed"] == {"share": 0.5, "gone_share": 0.5} and r["gate_possible"] is False
    md = P.run(r2, fetch, 10)
    assert "A 목록에 있고 기간도 덮음" in md and "| TEST02 | 예 |" in md and "관문 불가" in md
