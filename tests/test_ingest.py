import json
from datetime import date

import pytest

from quant.ingest.http import HttpError, Response, get_json
from quant.ingest import sources as S
from quant.ingest.quality import check_prices


class FakeFetch:
    """URL별 가짜 응답을 차례로 돌려주고 호출을 기록한다."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, params=None, headers=None):
        self.calls.append((url, dict(params or {}), dict(headers or {})))
        status, body = self.responses.pop(0)
        return Response(status, body if isinstance(body, str) else json.dumps(body))


def test_get_json_retries_429_then_succeeds_and_hides_key():
    f = FakeFetch((429, ""), (200, {"ok": 1}))
    assert get_json(f, "https://x", {"api_key": "FAKEKEY"}, source="t", sleep=lambda s: None) == {"ok": 1}
    with pytest.raises(HttpError) as e:
        get_json(FakeFetch((403, "")), "https://x", {"api_key": "FAKEKEY"}, source="t", sleep=lambda s: None)
    assert "FAKEKEY" not in str(e.value)


def test_tiingo_rows_and_adj_factor_token_in_header():
    f = FakeFetch((200, [{"date": "2024-01-02T00:00:00.000Z", "open": 10, "high": 11, "low": 9, "close": 10,
                          "adjClose": 5, "volume": 100}, {"date": "2024-01-03T00:00:00.000Z", "close": 0}]))
    rows = S.tiingo_daily(f, "test01", date(2024, 1, 1), date(2024, 1, 3), "FAKE")
    assert rows == [{"market": "US", "code": "TEST01", "date": "2024-01-02", "open": 10.0, "high": 11.0,
                     "low": 9.0, "close": 10.0, "adj_factor": 0.5, "volume": 100.0, "source": "tiingo"}]
    assert f.calls[0][2]["Authorization"] == "Token FAKE"
    assert "token" not in f.calls[0][1]


def test_fred_skips_missing_and_keeps_release_date():
    f = FakeFetch((200, {"observations": [
        {"date": "2024-01-01", "realtime_start": "2024-01-05", "value": "13.2"},
        {"date": "2024-01-02", "realtime_start": "2024-01-05", "value": "."}]}))
    assert S.fred_series(f, "VIXCLS", date(2024, 1, 1), "FAKE") == [
        {"series": "VIXCLS", "ref_date": "2024-01-01", "release_date": "2024-01-05", "value": 13.2, "source": "fred"}]


def _kr_page(items, total):
    return {"response": {"body": {"totalCount": total, "items": {"item": items}}}}


def test_kr_daily_pages_and_parses_strings():
    it = lambda code: {"basDt": "20240102", "srtnCd": code, "itmsNm": "가짜종목A", "clpr": "1,000",
                       "mkp": "990", "hipr": "1010", "lopr": "980", "trqu": "5"}
    f = FakeFetch((200, _kr_page([it("000001"), it("000002")], 3)), (200, _kr_page(it("000003"), 3)))
    rows = S.kr_daily(f, "stock", date(2024, 1, 2), "FAKE", page_size=2)
    assert [r["code"] for r in rows] == ["000001", "000002", "000003"]
    assert rows[0]["close"] == 1000.0 and rows[0]["date"] == "2024-01-02" and rows[0]["market"] == "KR"
    assert [c[1]["pageNo"] for c in f.calls] == [1, 2]


def test_naver_news_cleans_title_and_parses_date():
    f = FakeFetch((200, {"items": [{"title": "<b>합성</b> 뉴스 &amp; 시장", "originallink": "https://example.com/a",
                                    "link": "https://n.example/a", "pubDate": "Tue, 02 Jan 2024 09:00:00 +0900"}]}))
    [r] = S.naver_news(f, "코스피", "ID", "SECRET")
    assert r["title"] == "합성 뉴스 & 시장" and r["url"] == "https://example.com/a"
    assert r["published_at"] == "2024-01-02T09:00:00+09:00" and len(r["url_hash"]) == 32


def test_finnhub_news_tags_ticker():
    f = FakeFetch((200, [{"url": "https://example.com/b", "headline": " 합성 헤드라인 ", "source": "합성통신",
                          "datetime": 1704153600}, {"url": "", "headline": "x", "datetime": 0}]))
    [r] = S.finnhub_news(f, "test01", date(2024, 1, 1), date(2024, 1, 2), "FAKE")
    assert r["tickers"] == ["TEST01"] and r["title"] == "합성 헤드라인"
    assert r["published_at"].startswith("2024-01-02T00:00:00")


def test_quality_flags_duplicates_inverted_and_jumps():
    base = {"market": "US", "code": "TEST01", "adj_factor": 1.0}
    rows = [dict(base, date="2024-01-02", close=10, high=11, low=9),
            dict(base, date="2024-01-02", close=10),
            dict(base, date="2024-01-03", close=20, high=8, low=9)]
    issues = check_prices(rows)
    assert any("중복" in i for i in issues) and any("고가<저가" in i for i in issues)
    assert any("급변" in i for i in issues)
    assert check_prices([dict(base, date="2024-01-02", close=10), dict(base, date="2024-01-03", close=10.5)]) == []


def test_run_skips_missing_keys_and_continues_after_failure():
    from quant.ingest.run import run
    calls = []

    def fetch(url, params=None, headers=None):
        calls.append(url)
        if "VIXCLS" in str(params):
            return Response(500, "")
        return Response(200, json.dumps({"observations": [{"date": "2024-01-01", "realtime_start": "2024-01-02", "value": "1"}]}))

    out = []
    s = run({"FRED_API_KEY": "FAKE"}, fetch, None, today=date(2024, 1, 5), out=out.append)
    from quant.ingest.universe import FRED_SERIES
    assert s["failed"] == 1 and s["ok"] == len(FRED_SERIES) - 1
    assert any("tiingo" in o and "건너뜀" in o for o in out)
    assert not any("FAKE" in o for o in out)
    assert all("stlouisfed" in u for u in calls)
