"""소스별 수집 → DB 스키마 모양의 행(dict) 목록. 저장은 store 단계에서 한다."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import re
from typing import Any

from .http import Fetch, get_json, get_text

_TAG = re.compile(r"<[^>]+>")


def _num(v: Any) -> float | None:
    if v is None or v == "" or v == ".":
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _clean(s: str) -> str:
    return html.unescape(_TAG.sub("", s or "")).strip()


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()[:32]


# ---------------------------------------------------------------- 미국 일봉: Tiingo
def tiingo_daily(fetch: Fetch, ticker: str, start: date, end: date, token: str) -> list[dict]:
    data = get_json(fetch, f"https://api.tiingo.com/tiingo/daily/{ticker.lower()}/prices",
                    {"startDate": start.isoformat(), "endDate": end.isoformat(), "format": "json"},
                    {"Authorization": f"Token {token}"}, source="tiingo")
    rows = []
    for d in data or []:
        close, adj = _num(d.get("close")), _num(d.get("adjClose"))
        if close is None or close <= 0:
            continue
        rows.append({"market": "US", "code": ticker.upper(), "date": d["date"][:10],
                     "open": _num(d.get("open")), "high": _num(d.get("high")), "low": _num(d.get("low")),
                     "close": close, "adj_factor": (adj / close) if adj else 1.0,
                     "volume": _num(d.get("volume")), "source": "tiingo"})
    return rows


# ---------------------------------------------------------------- 매크로·VIX: FRED
FRED_WEEKLY_RELEASE = {"DTWEXBGS", "DEXKOUS"}
# 시장 금리의 월평균(사후 수정 없음): ALFRED 빈티지가 늦게 시작해도 '그 달 끝 + 15일'에 알 수 있던 값으로 본다(계획 #73)
FRED_MARKET_MONTHLY = {"IR3TIB01KRM156N"}  # 일별 값이지만 H.10 보고서로 주 1회 묶어 발표
FRED_DAILY = {"VIXCLS", "VXVCLS", "DEXKOUS", "DGS10", "DGS2", "T10Y2Y", "T10Y3M", "DFF", "BAMLH0A0HYM2",
              "USEPUINDXD", "WLEMUINDXD", "DTWEXBGS", "DCOILWTICO", "T5YIE", "DFII10", "BAMLC0A0CM", "BAA10Y", "DTB3"}


def fred_series(fetch: Fetch, series: str, start: date, api_key: str) -> list[dict]:
    """release_date = 그 값이 처음 공개된 날. 백테스트는 이 날짜 이후에만 쓴다.

    ALFRED '처음 발표된 값만'(output_type=4)으로 받아 정정 전 값과 첫 발표일을 쓴다.
    발표 기록(빈티지)이 시작되기 전 값은 realtime_start가 기록 시작일(수년 뒤)이다 → 그대로 둔다.
    즉 '그날 전에는 몰랐던 값'으로 남긴다. (예전엔 기준일+35일로 바꿔 넣어, 나중에 다시 계산된 값이
    당시에 알던 값처럼 들어갔다 — Fable 판정 #57에서 발견한 누수)
    일간 시장 시리즈는 빈티지가 너무 많아 다음 날 공개로, 주 1회 묶어 발표되는 것(달러지수·원/달러)은 7일 뒤로 본다.
    """
    params = {"series_id": series, "observation_start": start.isoformat(), "api_key": api_key, "file_type": "json"}
    daily = series in FRED_DAILY
    market_monthly = series in FRED_MARKET_MONTHLY
    if not daily and not market_monthly:
        # 일간 시장 시리즈는 빈티지가 수천 개라 FRED가 거절(최대 2,000) → 다음 날 발표로 보고 첫 발표값 조회는 월간·주간만
        params.update({"realtime_start": "1776-07-04", "realtime_end": "9999-12-31", "output_type": 4})
    data = get_json(fetch, "https://api.stlouisfed.org/fred/series/observations", params, source="fred")
    lag = timedelta(days=7 if series in FRED_WEEKLY_RELEASE else 1 if daily else 45 if market_monthly else 35)
    rows = []
    for o in data.get("observations", []):
        v = _num(o.get("value"))
        if v is None:
            continue
        ref = date.fromisoformat(o["date"])
        rel = date.fromisoformat(o.get("realtime_start") or o["date"])
        if daily or market_monthly or rel < ref:  # 일간은 다음 날(또는 주간 발표 7일), 기록이 이상하면(발표일 < 기준일) 보수적으로
            rel = ref + lag
        rows.append({"series": series, "ref_date": o["date"], "release_date": rel.isoformat(), "value": v, "source": "fred"})
    return rows


# ---------------------------------------------------------------- 한국 시세: 공공데이터포털(금융위원회)
# 지금 발급되는 키는 V2 주소에만 등록된다. 예전 /service/... 주소는 같은 키를 "등록되지 않은 키"(403)로 거부.
DATA_GO_KR = "https://apis.data.go.kr/1160100"
KR_ENDPOINTS = {
    "stock": f"{DATA_GO_KR}/GetStockSecuritiesInfoService_V2/getStockPriceInfo_V2",
    "etf": f"{DATA_GO_KR}/GetSecuritiesProductInfoService_V2/getETFPriceInfo_V2",
}


# 지수(금융위원회_지수시세정보 V2). 이름은 포털 표기와 정확히 같아야 해서 후보를 여럿 둔다.
KR_INDEX_URL = f"{DATA_GO_KR}/GetMarketIndexInfoService_V2"
KR_INDEXES = {  # code: (오퍼레이션, 검색어, 허용 이름들)
    "KOSPI": ("getStockMarketIndex_V2", "코스피", ("코스피",)),
    "KOSDAQ": ("getStockMarketIndex_V2", "코스닥", ("코스닥",)),
    "KOSPI200": ("getStockMarketIndex_V2", "코스피", ("코스피 200", "코스피200")),
    "VKOSPI": ("getDerivationProductMarketIndex_V2", "변동성", ("코스피 200 변동성지수", "코스피200 변동성지수", "VKOSPI")),
}


def kr_index(fetch: Fetch, code: str, start: date, end: date, service_key: str, page_size: int = 1000) -> list[dict]:
    """한 지수의 기간 일별 종가. 이름이 안 맞으면 응답에 있던 이름을 오류에 담아 고칠 수 있게 한다."""
    op, like, names = KR_INDEXES[code]
    service_key = kr_service_key(service_key)
    seen: set[str] = set()
    rows, page = [], 1
    while True:
        data = get_json(fetch, f"{KR_INDEX_URL}/{op}",
                        {"serviceKey": service_key, "resultType": "json", "numOfRows": page_size, "pageNo": page,
                         "likeIdxNm": like, "beginBasDt": start.strftime("%Y%m%d"),
                         "endBasDt": (end + timedelta(days=1)).strftime("%Y%m%d")},  # endBasDt는 끝 날짜 미포함
                        source=f"data.go.kr/index")
        body = (data.get("response") or {}).get("body") or {}
        items = (body.get("items") or {}).get("item") or []
        if isinstance(items, dict):
            items = [items]
        for it in items:
            nm = str(it.get("idxNm", "")).strip()
            seen.add(nm)
            close = _num(it.get("clpr"))
            if nm not in names or close is None or close <= 0:
                continue
            d = it["basDt"]
            rows.append({"market": "KR", "code": code, "name": nm, "kind": "index", "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                         "open": _num(it.get("mkp")), "high": _num(it.get("hipr")), "low": _num(it.get("lopr")),
                         "close": close, "adj_factor": 1.0, "volume": None, "source": "data.go.kr"})
        total = int(body.get("totalCount") or 0)
        if page * page_size >= total or not items:
            break
        page += 1
    if not rows and seen:
        raise ValueError(f"지수 이름 불일치({code}): 응답 이름 예 {sorted(seen)[:12]}")
    return rows


def kr_service_key(key: str) -> str:
    """포털의 '인코딩 키'(%2B 등)를 넣어도 두 번 인코딩되지 않게 원래 키로 되돌린다."""
    from urllib.parse import unquote
    key = key.strip()
    return unquote(key) if "%" in key else key


def kr_daily(fetch: Fetch, kind: str, bas_dt: date, service_key: str, page_size: int = 1000,
             with_shares: bool = False) -> list[dict]:
    """하루치 전 종목(페이지 반복). T+1 13시 이후 반영. with_shares: 상장주식수(lstgStCnt)도 담는다(PER·PBR용)."""
    service_key = kr_service_key(service_key)
    rows, page = [], 1
    while True:
        data = get_json(fetch, KR_ENDPOINTS[kind],
                        {"serviceKey": service_key, "resultType": "json", "numOfRows": page_size,
                         "pageNo": page, "basDt": bas_dt.strftime("%Y%m%d")}, source=f"data.go.kr/{kind}")
        body = (data.get("response") or {}).get("body") or {}
        items = (body.get("items") or {}).get("item") or []
        if isinstance(items, dict):
            items = [items]
        for it in items:
            close = _num(it.get("clpr"))
            if close is None or close <= 0:
                continue
            d = it["basDt"]
            rows.append({"market": "KR", "code": it["srtnCd"], "name": it.get("itmsNm"), "kind": kind,
                         "date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "open": _num(it.get("mkp")),
                         "high": _num(it.get("hipr")), "low": _num(it.get("lopr")), "close": close,
                         "adj_factor": 1.0, "volume": _num(it.get("trqu")), "source": "data.go.kr",
                         **({"shares": _num(it.get("lstgStCnt"))} if with_shares and kind == "stock" else {})})
        total = int(body.get("totalCount") or 0)
        if page * page_size >= total or not items:
            return rows
        page += 1


# 검산용 국내 상장 S&P500 ETF(실험실 5차, 계획 #79): 이름으로 고른다 — 레버리지·인버스·커버드콜·채권혼합 등은 뺀다
KR_TRACK_NAME = re.compile(r"^(TIGER|KODEX|ACE|RISE|KBSTAR|SOL|KIWOOM|KOSEF|HANARO|1Q|PLUS) ?미국S&P500(TR)?(\(H\))?$")


def kr_etf_history(fetch: Fetch, start: date, end: date, service_key: str, like: str = "S&P500", page_size: int = 1000) -> list[dict]:
    """이름에 like가 든 ETF의 기간 일별 종가(공공데이터포털 증권상품시세, 기간 조회). 검산용 종목 이름 규칙만 남긴다."""
    service_key = kr_service_key(service_key)
    rows, page = [], 1
    while True:
        data = get_json(fetch, KR_ENDPOINTS["etf"],
                        {"serviceKey": service_key, "resultType": "json", "numOfRows": page_size, "pageNo": page,
                         "likeItmsNm": like, "beginBasDt": start.strftime("%Y%m%d"),
                         "endBasDt": (end + timedelta(days=1)).strftime("%Y%m%d")}, source="data.go.kr/etf_hist")
        body = (data.get("response") or {}).get("body") or {}
        items = (body.get("items") or {}).get("item") or []
        if isinstance(items, dict):
            items = [items]
        for it in items:
            name = (it.get("itmsNm") or "").strip()
            close = _num(it.get("clpr"))
            if not KR_TRACK_NAME.match(name) or close is None or close <= 0:
                continue
            d = it["basDt"]
            rows.append({"market": "KR", "code": it["srtnCd"], "name": name, "kind": "etf", "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                         "open": _num(it.get("mkp")), "high": _num(it.get("hipr")), "low": _num(it.get("lopr")), "close": close,
                         "adj_factor": 1.0, "volume": _num(it.get("trqu")), "source": "data.go.kr"})
        total = int(body.get("totalCount") or 0)
        if page * page_size >= total or not items:
            return rows
        page += 1


# ---------------------------------------------------------------- 뉴스: Naver(한국), Finnhub(미국)
NAVER_NEWS_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"


def naver_news(fetch: Fetch, query: str, client_id: str, client_secret: str, display: int = 100) -> list[dict]:
    # 2026-07-31부터 검색 API는 NAVER API HUB(네이버 클라우드)로 이관: 주소·헤더가 바뀌었고 키도 HUB에서 새로 받는다.
    data = get_json(fetch, NAVER_NEWS_URL,
                    {"query": query, "display": display, "start": 1, "sort": "date"},
                    {"X-NCP-APIGW-API-KEY-ID": client_id.strip(), "X-NCP-APIGW-API-KEY": client_secret.strip()}, source="naver")
    rows = []
    for it in data.get("items", []):
        url = it.get("originallink") or it.get("link")
        if not url:
            continue
        rows.append({"url_hash": url_hash(url), "url": url, "title": _clean(it.get("title", "")),
                     "publisher": None, "published_at": parsedate_to_datetime(it["pubDate"]).isoformat(),
                     "tickers": [], "source": "naver"})
    return rows


GOOGLE_NEWS_URL = "https://news.google.com/rss/search"


def google_news(fetch: Fetch, query: str, lang: str = "ko", when: str = "1d") -> list[dict]:
    """한국 시장 헤드라인(키 없음). 구글 뉴스 RSS: 제목·언론사·시각만 있고 본문 요약은 없다.
    공식 API가 아니라 형식이 바뀔 수 있다 → 파싱 실패는 HttpError처럼 이 소스만 실패로 남는다."""
    import xml.etree.ElementTree as ET
    loc = {"ko": ("ko", "KR", "KR:ko"), "en": ("en-US", "US", "US:en")}[lang]
    text = get_text(fetch, GOOGLE_NEWS_URL, {"q": f"{query} when:{when}", "hl": loc[0], "gl": loc[1], "ceid": loc[2]},
                    {"User-Agent": "Mozilla/5.0 (quant-auto-trade)"}, source="google_news")
    rows = []
    for it in ET.fromstring(text).iter("item"):
        url, title, pub = it.findtext("link"), it.findtext("title") or "", it.findtext("pubDate")
        if not url or not pub:
            continue
        publisher = (it.findtext("source") or "").strip() or None
        if publisher and title.endswith(f" - {publisher}"):  # 제목 끝의 " - 언론사"는 따로 둔다
            title = title[: -len(publisher) - 3]
        rows.append({"url_hash": url_hash(url), "url": url, "title": _clean(title), "publisher": publisher,
                     "published_at": parsedate_to_datetime(pub).isoformat(), "tickers": [],
                     "source": "google_news" if lang == "ko" else "google_news_en"})
    return rows


def finnhub_market_news(fetch: Fetch, token: str) -> list[dict]:
    """시장 전체 뉴스(Finnhub general). 종목 뉴스와 달리 개별 기업 홍보 기사가 거의 없다 → 홈 미국 뉴스의 기본."""
    data = get_json(fetch, "https://finnhub.io/api/v1/news", {"category": "general"},
                    {"X-Finnhub-Token": token}, source="finnhub")
    rows = []
    for it in data or []:
        url = it.get("url")
        if not url or not it.get("headline") or not it.get("datetime"):
            continue
        rows.append({"url_hash": url_hash(url), "url": url, "title": it["headline"].strip(), "publisher": it.get("source"),
                     "published_at": datetime.fromtimestamp(int(it["datetime"]), timezone.utc).isoformat(),
                     "tickers": [], "source": "finnhub_market"})
    return rows


def finnhub_news(fetch: Fetch, symbol: str, start: date, end: date, token: str) -> list[dict]:
    data = get_json(fetch, "https://finnhub.io/api/v1/company-news",
                    {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()},
                    {"X-Finnhub-Token": token}, source="finnhub")
    rows = []
    for it in data or []:
        url = it.get("url")
        if not url or not it.get("headline"):
            continue
        rows.append({"url_hash": url_hash(url), "url": url, "title": it["headline"].strip(),
                     "publisher": it.get("source"),
                     "published_at": datetime.fromtimestamp(int(it["datetime"]), timezone.utc).isoformat(),
                     "tickers": [symbol.upper()], "source": "finnhub"})
    return rows
