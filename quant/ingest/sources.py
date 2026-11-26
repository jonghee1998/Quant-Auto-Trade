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
FRED_DAILY = {"VIXCLS", "VXVCLS", "DEXKOUS", "DGS10", "DGS2", "T10Y2Y", "T10Y3M", "DFF", "BAMLH0A0HYM2"}


def fred_series(fetch: Fetch, series: str, start: date, api_key: str) -> list[dict]:
    """release_date = 그 값이 처음 공개된 날. 백테스트는 이 날짜 이후에만 쓴다.

    ALFRED '처음 발표된 값만'(output_type=4)으로 받아 정정 전 값과 첫 발표일을 쓴다.
    빈티지 기록이 없는 시리즈는 realtime_start가 실제 발표일이 아니라(수년 뒤) → 일간 시리즈는 다음 날,
    그 밖은 35일 뒤로 보수적으로 둔다.
    """
    params = {"series_id": series, "observation_start": start.isoformat(), "api_key": api_key, "file_type": "json"}
    daily = series in FRED_DAILY
    if not daily:
        # 일간 시장 시리즈는 빈티지가 수천 개라 FRED가 거절(최대 2,000) → 다음 날 발표로 보고 첫 발표값 조회는 월간·주간만
        params.update({"realtime_start": "1776-07-04", "realtime_end": "9999-12-31", "output_type": 4})
    data = get_json(fetch, "https://api.stlouisfed.org/fred/series/observations", params, source="fred")
    lag = timedelta(days=1 if daily else 35)
    rows = []
    for o in data.get("observations", []):
        v = _num(o.get("value"))
        if v is None:
            continue
        ref = date.fromisoformat(o["date"])
        rel = date.fromisoformat(o.get("realtime_start") or o["date"])
        if daily or rel < ref or (rel - ref).days > 60:
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


def kr_service_key(key: str) -> str:
    """포털의 '인코딩 키'(%2B 등)를 넣어도 두 번 인코딩되지 않게 원래 키로 되돌린다."""
    from urllib.parse import unquote
    key = key.strip()
    return unquote(key) if "%" in key else key


def kr_daily(fetch: Fetch, kind: str, bas_dt: date, service_key: str, page_size: int = 1000) -> list[dict]:
    """하루치 전 종목(페이지 반복). T+1 13시 이후 반영."""
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


def google_news(fetch: Fetch, query: str) -> list[dict]:
    """한국 시장 헤드라인(키 없음). 구글 뉴스 RSS: 제목·언론사·시각만 있고 본문 요약은 없다.
    공식 API가 아니라 형식이 바뀔 수 있다 → 파싱 실패는 HttpError처럼 이 소스만 실패로 남는다."""
    import xml.etree.ElementTree as ET
    text = get_text(fetch, GOOGLE_NEWS_URL, {"q": f"{query} when:1d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
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
                     "published_at": parsedate_to_datetime(pub).isoformat(), "tickers": [], "source": "google_news"})
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
