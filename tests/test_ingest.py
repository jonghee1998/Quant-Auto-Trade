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
    assert f.calls[0][1]["output_type"] == 4 and f.calls[0][1]["realtime_start"] == "1776-07-04"


def test_fred_without_vintage_history_uses_conservative_lag():
    # 빈티지가 없으면 realtime_start가 수년 뒤 → 실제 발표일로 믿지 않는다(미래 데이터 방지)
    f = FakeFetch((200, {"observations": [{"date": "2010-03-01", "realtime_start": "2019-06-01", "value": "1"},
                                          {"date": "2010-03-01", "realtime_start": "2010-04-02", "value": "2"}]}))
    daily = S.fred_series(f, "VIXCLS", date(2010, 1, 1), "FAKE")
    assert daily[0]["release_date"] == "2010-03-02" and daily[1]["release_date"] == "2010-04-02"
    f2 = FakeFetch((200, {"observations": [{"date": "2010-03-01", "realtime_start": "2019-06-01", "value": "1"}]}))
    assert S.fred_series(f2, "CPIAUCSL", date(2010, 1, 1), "FAKE")[0]["release_date"] == "2010-04-05"


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


def test_network_error_and_output_never_leak_keys():
    from urllib.parse import quote
    from quant.ingest.http import NETWORK_ERROR, redact, requests_fetch
    from quant.ingest.run import run
    key = "FAKE+KEY/abc=123456"
    assert redact(f"a {key} b {quote(key, safe='')}", [key]) == "a *** b ***"

    def boom(url, params=None, headers=None):  # 예외 메시지에 키가 든 URL
        raise RuntimeError(f"https://example.com/x?api_key={quote(key, safe='')}")
    out = []
    s = run({"FRED_API_KEY": key}, boom, None, today=date(2024, 1, 5), out=out.append)
    assert s["failed"] > 0
    joined = "\n".join(out)
    assert key not in joined and quote(key, safe="") not in joined and "***" in joined

    f = FakeFetch((NETWORK_ERROR, "ConnectTimeout"), (NETWORK_ERROR, "ConnectTimeout"), (NETWORK_ERROR, "ConnectTimeout"))
    with pytest.raises(HttpError) as e:
        get_json(f, "https://x", {"serviceKey": key}, source="t", sleep=lambda s: None)
    assert "연결 실패" in str(e.value) and key not in str(e.value)
    assert len(f.calls) == 3  # 연결 실패도 재시도


def test_http_error_includes_redactable_snippet():
    f = FakeFetch((403, "<OpenAPI_ServiceResponse><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>"))
    with pytest.raises(HttpError) as e:
        get_json(f, "https://x", None, source="data.go.kr", sleep=lambda s: None)
    assert "SERVICE_KEY_IS_NOT_REGISTERED" in str(e.value)


def test_run_sources_filter():
    from quant.ingest.run import run
    calls = []

    def fetch(url, params=None, headers=None):
        calls.append(url)
        return Response(200, json.dumps({"observations": []}))
    out = []
    run({"FRED_API_KEY": "FAKEKEY1", "FINNHUB_TOKEN": "FAKEKEY2"}, fetch, None, today=date(2024, 1, 5), out=out.append, sources={"fred"})
    assert calls and all("stlouisfed" in u for u in calls)
