import json
import pytest

from quant.brief import core as B


def _n(title, pub, src="finnhub_market", at="2024-01-02T10:00:00+00:00", url=None):
    return {"title": title, "publisher": pub, "source": src, "published_at": at, "url": url or f"https://e.example/{pub}/{title[:5]}"}


def test_cluster_counts_outlets_and_ranks_hot_first():
    rows = [_n("합성 연준 금리 동결 결정 발표", "통신A"), _n("합성 연준 금리 동결 결정", "통신B"),
            _n("합성 연준, 금리 동결 결정 발표", "통신C"), _n("합성 유가 소폭 하락", "통신A", at="2024-01-02T11:00:00+00:00"),
            _n("합성 코스피 하락 마감 외국인 매도", "합성일보", "google_news"), _n("Should You Buy 합성 Stock?", "Zacks")]
    c = B.cluster_news(rows)
    assert c[0]["outlets"] == 3 and len(c[0]["articles"]) == 3  # 3곳이 다룬 사건이 맨 위
    assert {x["where"] for x in c} == {"미국", "한국"}
    assert not any("Should You Buy" in t for x in c for t in x["titles"])  # 낚시형 제외


def test_trend_targets_top_n_and_parts():
    uni = [{"code": f"TEST{i:02d}", "name": f"가짜종목{i}", "market": "KR", "kind": "주식", "r": [i, -i, None]} for i in range(40)]
    uni += [{"code": "FAKE1", "name": "가짜ETF", "market": "US", "kind": "업종", "r": [1, 2, 3]}]
    p = B.trend_targets(uni, {"KR": [0, 0, 0], "US": [1, 1, 1]}, n=15)
    kr = {e["code"] for e in p["why-kr-stock"]}
    assert len(kr) == 30  # 1개월 강/약 15씩 = 3개월에서 뒤집혀 같은 종목
    assert "TEST39" in kr and "TEST20" not in kr
    assert p["why-us"][0]["key"] == "US:FAKE1"


MAIN_IN = {"news": [{"id": "n1"}]}
GOOD_MAIN = {
    "today": {"what": "미국은 내렸어요.", "why": "물가가 높았어요.", "why_news": ["n1", "없는것"],
              "next": [{"what": "고용 지표", "why": "강하면 금리 인하가 늦어져요."}]},
    "market": {"us": "금리 걱정 장.", "kr": "환율 부담."},
    "news": [{"id": "n1", "cat": "금리·연준", "title": "합성 제목", "summary": ["a", "b", "c"], "meaning": "의미",
              "where": "미국", "outlets": 3, "links": [{"name": "통신A", "url": "https://e.example/a"}]}] * 3,
}


def test_check_main_ok_and_filters_unknown_ids():
    m = B.check_main(GOOD_MAIN, MAIN_IN)
    assert m["today"]["why_news"] == ["n1"] and len(m["news"]) == 3


@pytest.mark.parametrize("bad", [
    {**GOOD_MAIN, "today": {**GOOD_MAIN["today"], "next": []}},
    {**GOOD_MAIN, "news": [{**GOOD_MAIN["news"][0], "cat": "엉뚱"}] * 3},
    {**GOOD_MAIN, "news": [{**GOOD_MAIN["news"][0], "links": [{"name": "x", "url": "javascript:alert(1)"}]}] * 3},
    {**GOOD_MAIN, "market": {"us": "", "kr": "x"}},
])
def test_check_main_rejects(bad):
    with pytest.raises(B.BriefError):
        B.check_main(bad, MAIN_IN)


def test_check_why_keeps_good_items_only_and_merge():
    inp = {"items": [{"key": "KR:TEST01"}, {"key": "KR:TEST02"}]}
    out = {"items": {"KR:TEST01": {"line": "수주 공시", "text": "설명", "tags": ["공시"], "confidence": "높음",
                                   "evidence": [{"type": "공시", "label": "합성 공시", "url": "https://e.example/d"}]},
                     "KR:TEST02": {"line": "", "text": "x"}, "KR:NOPE": {"line": "x", "text": "y"}}}
    w = B.check_why(out, inp)
    assert list(w["items"]) == ["KR:TEST01"]
    p = B.merge({"quotes": [], "ai": {"why": {"KR:OLD": {}}}}, {"why-kr-stock": w}, generated_at="t")
    assert set(p["ai"]["why"]) == {"KR:OLD", "KR:TEST01"} and p["ai"]["generatedAt"] == "t" and p["quotes"] == []


def test_cluster_korean_titles_despite_particles():
    rows = [_n("코스피가 6% 급락하며 4700선 마감", "합성일보", "google_news"),
            _n("코스피는 6% 급락, 4700선으로 마감", "합성경제", "google_news"),
            _n("[속보] 코스피 6% 급락 4700선 마감", "합성뉴스", "google_news"),
            _n("원달러 환율 10원 올라 1342원", "합성일보", "google_news")]
    c = B.cluster_news(rows)
    assert c[0]["outlets"] == 3 and c[0]["where"] == "한국"
    assert len(c) == 2


def test_merge_records_data_date():
    p = B.merge({}, {"main": {"today": {}, "market": {}, "news": []}}, generated_at="t", data_date="2024-01-02")
    assert p["ai"]["date"] == "2024-01-02"


def test_split_parts_by_rank_into_chunks_of_22_or_less():
    items = [{"key": f"KR:TEST{i:02d}", "lists": [f"1개월 강한 {i % 15 + 1}위", "3개월 약한 9위"]} for i in range(66)]
    p = B.split_parts({"why-kr-stock": items, "why-us": items[:10]})
    assert sorted(p) == ["why-kr-stock-1", "why-kr-stock-2", "why-kr-stock-3", "why-us"]
    assert [len(p[f"why-kr-stock-{i}"]) for i in (1, 2, 3)] == [22, 22, 22]
    assert {e["key"] for k in p if k.startswith("why-kr") for e in p[k]} == {e["key"] for e in items}   # 빠진 종목 없음
    assert B.best_rank(p["why-kr-stock-1"][0]) == 1 and B.best_rank(p["why-kr-stock-3"][0]) == 1     # 조각마다 높은 순위부터
    assert B.best_rank({"lists": []}) == 99


def test_check_why_drops_copied_sentences_and_unsupported_low_confidence():
    inp = {"items": [{"key": f"KR:TEST{i:02d}"} for i in range(6)]}
    same = {"line": "뚜렷한 이유를 못 찾았어요", "text": "뚜렷한 이유를 못 찾았어요.", "confidence": "낮음", "evidence": []}
    good = {"line": "수주 공시", "text": "합성 공시로 올랐어요.", "confidence": "보통", "evidence": [{"type": "공시", "label": "합성 공시", "url": "https://e.example/d"}]}
    copy = dict(good, text="업종 전체가 올랐어요.")
    out = {"items": {"KR:TEST00": same, "KR:TEST01": dict(same), "KR:TEST02": dict(same), "KR:TEST03": good,
                     "KR:TEST04": {"line": "x", "text": "혼자만 근거 없이 낮음", "confidence": "낮음", "evidence": []}}}
    w = B.check_why(out, inp)
    assert list(w["items"]) == ["KR:TEST03"] and set(w["dropped"]) == {"KR:TEST00", "KR:TEST01", "KR:TEST02", "KR:TEST04"}
    three = B.check_why({"items": {f"KR:TEST{i:02d}": dict(copy) for i in range(3)}}, inp)      # 근거가 있어도 같은 문장 3개면 복사로 본다
    assert three["items"] == {} and len(three["dropped"]) == 3
    p = B.merge({"ai": {"why": {"KR:TEST00": {"line": "어제 값"}, "KR:OLD": {}}}}, {"why-kr-stock-1": w}, generated_at="t")
    assert set(p["ai"]["why"]) == {"KR:OLD", "KR:TEST03"}                                       # 버린 종목은 이전 값도 지운다


def test_match_news_needs_name_in_title_and_recent_date():
    rows = [{"title": "가짜종목A 대규모 수주", "url": "https://e.example/1", "publisher": None, "published_at": "2026-11-20T09:00:00+09:00"},
            {"title": "가짜종목A 대규모 수주", "url": "https://e.example/2", "publisher": None, "published_at": "2026-11-19T09:00:00+09:00"},
            {"title": "다른 회사 소식", "url": "https://e.example/3", "publisher": None, "published_at": "2026-11-21T09:00:00+09:00"},
            {"title": "가짜종목A 옛날 기사", "url": "https://e.example/4", "publisher": None, "published_at": "2026-09-01T09:00:00+09:00"},
            {"title": "가짜종목A 내일 기사", "url": "https://e.example/5", "publisher": None, "published_at": "2026-11-28T09:00:00+09:00"}]
    got = B.match_news("가짜종목A", rows, "2026-11-27")
    assert [g["url"] for g in got] == ["https://e.example/1"] and got[0]["at"] == "2026-11-20"   # 같은 제목은 한 번, 미래·옛 기사 제외


def test_item_news_search_uses_naver_with_keys_else_google_news():
    from quant.brief import run as R
    from quant.ingest.http import Response
    calls = []

    def fetch(url, params=None, headers=None):
        if "news.google.com" in url:
            calls.append(("google", params["q"]))
            name = params["q"].split('"')[1]
            return Response(200, f"""<rss><channel><item><title>{name} 공장 증설 - 합성일보</title><link>https://e.example/g</link>
                <pubDate>Thu, 26 Nov 2026 10:00:00 +0900</pubDate><source>합성일보</source></item></channel></rss>""")
        calls.append(("naver", params["query"]))
        return Response(200, json.dumps({"items": [{"title": f"{params['query']} 신제품 발표", "originallink": "https://e.example/n",
                                                    "pubDate": "Thu, 26 Nov 2026 10:00:00 +0900"}]}))
    items = [{"key": "KR:TEST01", "name": "가짜종목A", "market": "KR", "kind": "주식", "news": []},
             {"key": "KR:TEST02", "name": "가짜종목B", "market": "KR", "kind": "주식", "news": [{"title": "t"}] * 3},
             {"key": "US:FAKE1", "name": "Fake", "market": "US", "kind": "주식", "news": []}]
    quiet = dict(log=lambda s: None, sleep=lambda s: None)
    got = R._search_item_news(items, "2026-11-27", {"NAVER_CLIENT_ID": "FAKE-ID", "NAVER_CLIENT_SECRET": "FAKE-SECRET"}, fetch, **quiet)
    assert calls == [("naver", "가짜종목A")] and got["KR:TEST01"][0]["title"] == "가짜종목A 신제품 발표"   # 뉴스 모자란 한국 주식만
    calls.clear()
    got = R._search_item_news(items, "2026-11-27", {}, fetch, **quiet)                                 # 키 없으면 구글 뉴스(최근 30일)
    assert calls == [("google", '"가짜종목A" when:30d')] and got["KR:TEST01"][0] == {
        "title": "가짜종목A 공장 증설", "url": "https://e.example/g", "publisher": "합성일보", "at": "2026-11-26"}

    def broken(url, params=None, headers=None):
        return Response(500, "x")
    assert R._search_item_news(items * 4, "2026-11-27", {}, broken, **quiet) == {}                     # 실패해도 멈추지 않고 빈 값
