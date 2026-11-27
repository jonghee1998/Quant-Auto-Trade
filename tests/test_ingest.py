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
    assert S.fred_series(f, "CPIAUCSL", date(2024, 1, 1), "FAKE") == [
        {"series": "CPIAUCSL", "ref_date": "2024-01-01", "release_date": "2024-01-05", "value": 13.2, "source": "fred"}]
    assert f.calls[0][1]["output_type"] == 4 and f.calls[0][1]["realtime_start"] == "1776-07-04"
    g = FakeFetch((200, {"observations": [{"date": "2024-01-01", "realtime_start": "2026-11-26", "value": "13.2"}]}))
    assert S.fred_series(g, "VIXCLS", date(2024, 1, 1), "FAKE")[0]["release_date"] == "2024-01-02"  # 일간: 다음 날
    assert "output_type" not in g.calls[0][1]  # 빈티지 수천 개 → FRED 400 방지


def test_fred_before_vintage_history_is_unknown_until_recorded():
    # 발표 기록 시작 전 값(realtime_start가 수년 뒤)은 그날 전엔 몰랐던 값 — 기준일+35일로 바꿔 넣으면
    # 나중에 다시 계산된 값이 당시 값처럼 들어간다(Fable 판정 #57의 누수)
    f = FakeFetch((200, {"observations": [{"date": "2010-03-01", "realtime_start": "2019-06-01", "value": "1"},
                                          {"date": "2010-04-01", "realtime_start": "2010-05-07", "value": "2"}]}))
    rows = S.fred_series(f, "NFCI", date(2010, 1, 1), "FAKE")
    assert [r["release_date"] for r in rows] == ["2019-06-01", "2010-05-07"]
    bad = FakeFetch((200, {"observations": [{"date": "2010-03-01", "realtime_start": "2010-02-01", "value": "1"}]}))
    assert S.fred_series(bad, "CPIAUCSL", date(2010, 1, 1), "FAKE")[0]["release_date"] == "2010-04-05"  # 기록 이상 → 보수적


def test_fred_weekly_published_daily_series_lag_seven_days():
    f = FakeFetch((200, {"observations": [{"date": "2024-01-02", "realtime_start": "2026-11-26", "value": "120"}]}))
    assert S.fred_series(f, "DTWEXBGS", date(2024, 1, 1), "FAKE")[0]["release_date"] == "2024-01-09"


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
    url, _, headers = f.calls[0]
    assert url == "https://naverapihub.apigw.ntruss.com/search/v1/news"  # 예전 openapi.naver.com은 HUB 키를 401로 거부
    assert headers == {"X-NCP-APIGW-API-KEY-ID": "ID", "X-NCP-APIGW-API-KEY": "SECRET"}


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
    s = run({"FRED_API_KEY": "FAKE"}, fetch, None, today=date(2024, 1, 5), out=out.append, sources={"fred"})
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


def test_kr_service_key_undoes_portal_encoding():
    # 가짜 키: 인코딩 형태와 디코딩 형태가 같은 값으로 보내져야 한다
    assert S.kr_service_key("FAKE%2Babc%3D%3D") == "FAKE+abc=="
    assert S.kr_service_key(" FAKE+abc== ") == "FAKE+abc=="


def test_kr_endpoints_use_v2():
    # 예전 /service/ 주소는 V2로 승인된 키를 거부한다
    assert S.KR_ENDPOINTS["stock"].endswith("/1160100/GetStockSecuritiesInfoService_V2/getStockPriceInfo_V2")
    assert S.KR_ENDPOINTS["etf"].endswith("/1160100/GetSecuritiesProductInfoService_V2/getETFPriceInfo_V2")
    assert all("/service/" not in u for u in S.KR_ENDPOINTS.values())


def test_run_stops_starting_jobs_after_time_budget():
    # 느린 소스 때문에 Actions 제한 시간에 걸려 통째로 취소되지 않게: 예산을 넘기면 남은 작업은 건너뛰고 요약을 남긴다
    from quant.ingest.run import run
    now = [0.0]

    def fetch(url, params=None, headers=None):
        now[0] += 100  # 요청 하나에 100초 걸리는 느린 소스
        return Response(200, json.dumps({"observations": []}))
    out = []
    s = run({"FRED_API_KEY": "FAKE"}, fetch, None, today=date(2024, 1, 5), out=out.append,
            budget_s=250, clock=lambda: now[0], sources={"fred"})
    from quant.ingest.universe import FRED_SERIES
    assert s["ok"] == 3 and s["skipped"] == len(FRED_SERIES) - 3
    assert any("시간 부족" in o for o in out) and "건너뜀" in out[-1]


def test_plan_collects_us_stock_prices():
    from quant.ingest.run import plan
    from quant.ingest.universe import US_STOCKS
    codes = {d for s, d, _, k in plan({"TIINGO_TOKEN": "FAKE"}, date(2024, 1, 5), 5) if s == "tiingo"}
    assert set(US_STOCKS) <= codes


def test_plan_skips_kr_dates_already_stored():
    # 시간 예산으로 끊겨도 다음 실행이 이어서 받도록: 이미 받은 날짜는 뺀다. 단 최근 5일은 늘 다시(정정·상장주식수)
    from quant.ingest.run import plan
    env = {"DATA_GO_KR_KEY": "FAKE"}
    def daily(have):
        return [d for s, d, _, _ in plan(env, date(2024, 1, 10), 7, have) if s == "data.go.kr" and not d.startswith("index:")]
    assert daily(set())[-2:] == ["stock:2024-01-03", "etf:2024-01-03"] and len(daily(set())) == 14
    have = {("stock", "2024-01-03"), ("etf", "2024-01-04"), ("stock", "2024-01-08")}  # 1/8은 최근 5일 → 그래도 받음
    got = daily(have)
    assert "stock:2024-01-03" not in got and "etf:2024-01-04" not in got and "stock:2024-01-08" in got

def test_kr_jobs_fetch_in_parallel_and_report_in_order():
    # 하루치가 몇 분 걸리는 data.go.kr: 여러 날짜를 동시에 받되 결과 줄은 계획 순서대로
    import threading
    from quant.ingest.run import run
    live, peak, lock = [0], [0], threading.Lock()
    gate = threading.Barrier(4, timeout=5)

    def fetch(url, params=None, headers=None):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        try:
            gate.wait()  # 4개가 동시에 들어와야 통과
        except threading.BrokenBarrierError:
            pass
        with lock:
            live[0] -= 1
        if "GetMarketIndexInfoService" in url:
            return Response(200, json.dumps({"response": {"body": {"totalCount": 0, "items": ""}}}))
        d = params["basDt"]
        body = {"response": {"body": {"totalCount": 1, "items": {"item": [
            {"basDt": d, "srtnCd": "TEST01", "itmsNm": "가짜종목A", "clpr": "100"}]}}}}
        return Response(200, json.dumps(body))
    out = []
    s = run({"DATA_GO_KR_KEY": "FAKE"}, fetch, None, today=date(2024, 1, 5), days=2, out=out.append)
    assert s["ok"] == 8 and peak[0] == 4
    lines = [o.split(":")[0] + ":" + o.split(":")[1] for o in out if o.startswith("data.go.kr") and "index:" not in o]
    assert [x.split()[1] for x in lines] == ["stock:2024-01-04", "etf:2024-01-04", "stock:2024-01-03", "etf:2024-01-03"]


def test_upsert_prices_uses_few_round_trips():
    # 종목마다 왕복하면 한국 전 종목 저장에 2분+ 걸렸다: 종목 수와 상관없이 왕복 횟수가 고정이어야 한다
    from quant.ingest import store
    calls = []

    class Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def executemany(self, sql, params): calls.append(("many", len(list(params))))
        def execute(self, sql, params=None): calls.append(("one", sql.split()[0]))
        def fetchall(self): return [("KR", f"TEST{i:04d}", i) for i in range(3000)]

    class Conn:
        def cursor(self): return Cur()
    rows = [{"market": "KR", "code": f"TEST{i:04d}", "name": "가짜종목", "kind": "stock", "date": "2024-01-02",
             "close": 1.0, "source": "test"} for i in range(3000)]
    assert store.upsert_prices(Conn(), rows + rows[:5]) == 3005
    assert [c[0] for c in calls] == ["many", "one", "many"] and calls[0][1] == 3000


GOOGLE_RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>x</title>
<item><title>합성 증시 마감 - 합성일보</title><link>https://news.example/a</link>
<pubDate>Tue, 02 Jan 2024 06:30:00 GMT</pubDate><source url="https://s.example">합성일보</source></item>
<item><title>링크 없는 기사</title><pubDate>Tue, 02 Jan 2024 06:30:00 GMT</pubDate></item>
</channel></rss>"""


def test_google_news_parses_rss_without_key():
    f = FakeFetch((200, GOOGLE_RSS))
    [r] = S.google_news(f, "코스피")
    assert r["title"] == "합성 증시 마감" and r["publisher"] == "합성일보" and r["source"] == "google_news"
    assert r["published_at"].startswith("2024-01-02T06:30:00")
    url, params, _ = f.calls[0]
    assert url == "https://news.google.com/rss/search" and params["q"] == "코스피 when:1d" and params["ceid"] == "KR:ko"


def test_plan_has_kr_news_without_naver_key():
    from quant.ingest.run import plan
    jobs = [d for s, d, *_ in plan({}, date(2024, 1, 5), 1)]
    assert "코스피" in jobs and "en:stock market" in jobs


def test_finnhub_market_news_is_marked_market():
    f = FakeFetch((200, [{"url": "https://example.com/m", "headline": " 합성 시장 뉴스 ", "source": "합성통신", "datetime": 1704153600}]))
    [r] = S.finnhub_market_news(f, "FAKE")
    assert r["source"] == "finnhub_market" and r["tickers"] == [] and r["title"] == "합성 시장 뉴스"
    assert f.calls[0][0].endswith("/api/v1/news") and f.calls[0][1] == {"category": "general"}


def test_kr_index_matches_exact_names_and_reports_unknown():
    body = {"response": {"body": {"totalCount": 3, "items": {"item": [
        {"basDt": "20240102", "idxNm": "코스피", "clpr": "2600.5"},
        {"basDt": "20240102", "idxNm": "코스피 200", "clpr": "350.1"},
        {"basDt": "20240102", "idxNm": "코스피 대형주", "clpr": "1.0"}]}}}}
    f = FakeFetch((200, body), (200, body))
    [k] = S.kr_index(f, "KOSPI", date(2024, 1, 2), date(2024, 1, 2), "FAKE")
    assert (k["code"], k["close"], k["kind"], k["date"]) == ("KOSPI", 2600.5, "index", "2024-01-02")
    assert f.calls[0][0].endswith("/GetMarketIndexInfoService_V2/getStockMarketIndex_V2")
    assert f.calls[0][1]["endBasDt"] == "20240103"  # 끝 날짜 미포함이라 하루 더
    [k2] = S.kr_index(f, "KOSPI200", date(2024, 1, 2), date(2024, 1, 2), "FAKE")
    assert k2["close"] == 350.1
    import pytest
    g = FakeFetch((200, {"response": {"body": {"totalCount": 1, "items": {"item": [{"basDt": "20240102", "idxNm": "합성지수", "clpr": "1"}]}}}}))
    with pytest.raises(ValueError, match="합성지수"):
        S.kr_index(g, "VKOSPI", date(2024, 1, 2), date(2024, 1, 2), "FAKE")


def test_kr_daily_jobs_capped_even_with_huge_days():
    from quant.ingest.run import KR_DAILY_MAX_DAYS, plan
    jobs = [d for s, d, _, _ in plan({"DATA_GO_KR_KEY": "FAKE"}, date(2024, 1, 5), 7700) if s == "data.go.kr"]
    daily = [d for d in jobs if not d.startswith(("index:", "etf_hist:"))]
    assert len(daily) == 2 * KR_DAILY_MAX_DAYS and any(d.startswith("index:") for d in jobs)
    assert [d for d in jobs if d.startswith("etf_hist:")] == [f"etf_hist:{y}" for y in range(2019, 2025)]


def test_google_news_english_is_us_source():
    f = FakeFetch((200, GOOGLE_RSS))
    [r] = S.google_news(f, "stock market", "en")
    assert r["source"] == "google_news_en" and f.calls[0][1]["ceid"] == "US:en"



def test_sec_uses_all_revenue_tags_with_priority():
    from quant.ingest import sec
    def item(end, start, val, filed):
        return {"start": start, "end": end, "val": val, "filed": filed, "form": "10-Q", "fy": 2024, "fp": "Q2"}
    facts = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [item("2022-06-30", "2022-04-01", 50, "2022-08-01")]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            item("2024-06-30", "2024-04-01", 100, "2024-08-01"), item("2022-06-30", "2022-04-01", 49, "2022-08-01")]}}}}}
    rows = sec.company_facts(FakeFetch((200, facts)), 1, "TEST", "합성 test@example.com")
    rev = sorted((r["period_end"], r["value"]) for r in rows if r["concept"] == "revenue")
    assert rev == [("2022-06-30", 50.0), ("2024-06-30", 100.0)]  # 새 태그 기간도 받고, 겹치면 앞 태그



def test_kr_daily_shares_only_when_asked():
    body = {"response": {"body": {"totalCount": 1, "items": {"item": [
        {"basDt": "20240102", "srtnCd": "TEST01", "itmsNm": "가짜종목A", "clpr": "100", "lstgStCnt": "1,000"}]}}}}
    assert "shares" not in S.kr_daily(FakeFetch((200, body)), "stock", date(2024, 1, 2), "FAKE")[0]
    assert S.kr_daily(FakeFetch((200, body)), "stock", date(2024, 1, 2), "FAKE", with_shares=True)[0]["shares"] == 1000.0


def test_market_monthly_rate_uses_month_plus_lag_not_alfred():
    """한국 3개월 금리(시장 금리 월평균)는 ALFRED 빈티지 대신 기준일 + 45일에 알 수 있던 값으로(계획 #73)."""
    from quant.ingest import sources as S
    seen = {}

    def fetch(url, params=None, headers=None, *a, **kw):
        seen.update(params or {})
        from quant.ingest.http import Response
        import json
        return Response(200, json.dumps({"observations": [{"date": "2005-01-01", "value": "3.5", "realtime_start": "2015-06-01"}]}))
    rows = S.fred_series(fetch, "IR3TIB01KRM156N", __import__("datetime").date(2005, 1, 1), "TESTKEY")
    assert "output_type" not in seen and rows[0]["release_date"] == "2005-02-15"


def test_kr_etf_history_keeps_only_plain_sp500_names():
    from datetime import date
    import json
    from quant.ingest import sources as S
    from quant.ingest.http import Response
    items = [{"basDt": "20210104", "srtnCd": "TEST01", "itmsNm": "TIGER 미국S&P500", "clpr": "10000"},
             {"basDt": "20210104", "srtnCd": "TEST02", "itmsNm": "KODEX 미국S&P500TR", "clpr": "11000"},
             {"basDt": "20210104", "srtnCd": "TEST03", "itmsNm": "KODEX 미국S&P500(H)", "clpr": "9000"},
             {"basDt": "20210104", "srtnCd": "TEST04", "itmsNm": "TIGER 미국S&P500레버리지(합성 H)", "clpr": "9000"},
             {"basDt": "20210104", "srtnCd": "TEST05", "itmsNm": "KODEX 미국S&P500버퍼3월액티브", "clpr": "9000"}]

    def fetch(url, params=None, headers=None, *a, **kw):
        assert params["beginBasDt"] == "20210101" and params["likeItmsNm"] == "S&P500"
        return Response(200, json.dumps({"response": {"body": {"totalCount": 5, "items": {"item": items}}}}))
    rows = S.kr_etf_history(fetch, date(2021, 1, 1), date(2021, 12, 31), "TESTKEY")
    assert sorted(r["code"] for r in rows) == ["TEST01", "TEST02", "TEST03"]
