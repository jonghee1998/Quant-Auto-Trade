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
