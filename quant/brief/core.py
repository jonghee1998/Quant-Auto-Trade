"""입력 만들기·출력 검사(순수 함수, 테스트 대상)."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from ..snapshot import _home_ok

PARTS = ("main", "why-kr-stock", "why-kr-etf", "why-us")
CATS = ("금리·연준", "미국 증시", "한국 증시", "기업·실적", "유가·환율", "기타")
EVIDENCE = ("공시", "뉴스", "실적", "업종", "가격", "기타")
TOP_N = 15
KR_SOURCES = {"naver", "google_news"}
_TOK = re.compile(r"[\w&]+", re.UNICODE)


def _tokens(title: str) -> set[str]:
    return {t for t in _TOK.findall(title.lower()) if len(t) >= 2}


def _id(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def cluster_news(rows: list[dict], jaccard: float = 0.4) -> list[dict]:
    """같은 사건을 다룬 기사를 묶고 '핫한 순'(보도 언론사 수 → 최신)으로 정렬.
    rows: title, url, publisher, source, published_at(ISO 또는 datetime)."""
    rows = sorted((r for r in rows if r.get("title") and _home_ok(r)),
                  key=lambda r: str(r["published_at"]), reverse=True)
    clusters: list[dict] = []
    for r in rows:
        tok = _tokens(r["title"])
        if not tok:
            continue
        where = "한국" if r.get("source") in KR_SOURCES else "미국"
        best = None
        for c in clusters:
            if c["where"] != where:
                continue
            inter = len(tok & c["_tok"])
            if inter and inter / len(tok | c["_tok"]) >= jaccard:
                best = c
                break
        if best is None:
            best = {"id": _id(r["url"]), "where": where, "_tok": tok, "titles": [], "articles": [], "publishers": set(),
                    "latest": str(r["published_at"])}
            clusters.append(best)
        pub = (r.get("publisher") or r.get("source") or "").strip()
        if pub and pub in best["publishers"]:
            continue
        best["publishers"].add(pub)
        if len(best["titles"]) < 3:
            best["titles"].append(r["title"])
        if len(best["articles"]) < 6:
            best["articles"].append({"name": pub or "?", "url": r["url"], "at": str(r["published_at"])})
    out = []
    for c in clusters:
        out.append({"id": c["id"], "where": c["where"], "outlets": len(c["publishers"]), "latest": c["latest"],
                    "titles": c["titles"], "articles": c["articles"]})
    out.sort(key=lambda c: (c["outlets"], c["latest"]), reverse=True)
    return out


def trend_targets(universe: list[dict], bench: dict, n: int = TOP_N) -> dict[str, list[dict]]:
    """트렌드 목록(시장·종류·기간·강/약 TOP n)에 오르는 종목. 부분(PARTS)별로 나눈다."""
    groups: dict[tuple, list[dict]] = {}
    for u in universe:
        groups.setdefault((u["market"], u["kind"]), []).append(u)
    picked: dict[str, dict] = {}
    for (market, kind), items in groups.items():
        for p, label in enumerate(("1개월", "3개월", "6개월")):
            have = [u for u in items if u["r"][p] is not None]
            ranked = sorted(have, key=lambda u: u["r"][p], reverse=True)
            for side, lst in (("강한", ranked[:n]), ("약한", ranked[::-1][:n])):
                for rank, u in enumerate(lst, 1):
                    key = f"{u['market']}:{u['code']}"
                    e = picked.setdefault(key, {"key": key, "code": u["code"], "name": u["name"], "market": u["market"],
                                                "kind": u["kind"], "returns": dict(zip(("1개월", "3개월", "6개월"), u["r"])),
                                                "benchmark": dict(zip(("1개월", "3개월", "6개월"), bench.get(u["market"], [None] * 3))),
                                                "lists": []})
                    e["lists"].append(f"{label} {side} {rank}위")
    parts: dict[str, list[dict]] = {"why-kr-stock": [], "why-kr-etf": [], "why-us": []}
    for e in picked.values():
        part = "why-kr-stock" if (e["market"], e["kind"]) == ("KR", "주식") else "why-kr-etf" if e["market"] == "KR" else "why-us"
        parts[part].append(e)
    return parts


# ---------------------------------------------------------------- 출력 검사
class BriefError(ValueError):
    pass


def _s(v: Any, name: str, cap: int) -> str:
    if not isinstance(v, str) or not v.strip():
        raise BriefError(f"{name}: 글자가 비었거나 문자열이 아님")
    v = v.strip()
    if len(v) > cap:
        raise BriefError(f"{name}: {cap}자 초과({len(v)}자)")
    return v


def _url(v: Any) -> str | None:
    return v if isinstance(v, str) and re.match(r"^https?://\S+$", v) and len(v) <= 600 else None


def check_main(out: dict, inp: dict) -> dict:
    news_ids = {c["id"] for c in inp.get("news", [])}
    t = out.get("today") or {}
    today = {"what": _s(t.get("what"), "today.what", 160), "why": _s(t.get("why"), "today.why", 200),
             "why_news": [i for i in (t.get("why_news") or []) if i in news_ids][:3],
             "next": [{"what": _s(x.get("what"), "today.next.what", 100), "why": _s(x.get("why"), "today.next.why", 160)}
                      for x in (t.get("next") or [])[:3]]}
    if not today["next"]:
        raise BriefError("today.next: 최소 1개")
    m = out.get("market") or {}
    market = {"us": _s(m.get("us"), "market.us", 400), "kr": _s(m.get("kr"), "market.kr", 400)}
    news = []
    for i, x in enumerate((out.get("news") or [])[:20]):
        if x.get("cat") not in CATS:
            raise BriefError(f"news[{i}].cat: {CATS} 중 하나")
        summary = [_s(s, f"news[{i}].summary", 120) for s in (x.get("summary") or [])[:3]]
        if not summary:
            raise BriefError(f"news[{i}].summary: 비었음")
        links = [{"name": _s(l.get("name"), "link.name", 40), "url": _url(l.get("url"))} for l in (x.get("links") or [])[:6]]
        links = [l for l in links if l["url"]]
        if not links:
            raise BriefError(f"news[{i}].links: 원문 링크가 없음")
        news.append({"id": str(x.get("id") or _id(links[0]["url"])), "cat": x["cat"], "title": _s(x.get("title"), f"news[{i}].title", 90),
                     "summary": summary, "meaning": _s(x.get("meaning"), f"news[{i}].meaning", 200),
                     "where": "한국" if x.get("where") == "한국" else "미국",
                     "outlets": int(x.get("outlets") or len(links)), "links": links})
    if len(news) < 3:
        raise BriefError("news: 최소 3개")
    return {"today": today, "market": market, "news": news}


def check_why(out: dict, inp: dict) -> dict:
    keys = {e["key"] for e in inp.get("items", [])}
    items = {}
    for key, x in (out.get("items") or {}).items():
        if key not in keys or not isinstance(x, dict):
            continue  # 입력에 없는 종목은 버린다
        try:
            ev = []
            for e in (x.get("evidence") or [])[:6]:
                typ = e.get("type") if e.get("type") in EVIDENCE else "기타"
                ev.append({"type": typ, "label": _s(e.get("label"), f"{key}.evidence", 140), "url": _url(e.get("url"))})
            items[key] = {"line": _s(x.get("line"), f"{key}.line", 60), "text": _s(x.get("text"), f"{key}.text", 500),
                          "tags": [str(t)[:12] for t in (x.get("tags") or [])[:4]],
                          "confidence": x.get("confidence") if x.get("confidence") in ("높음", "보통", "낮음") else "낮음",
                          "evidence": ev}
        except BriefError:
            continue  # 한 종목이 잘못돼도 나머지는 살린다
    return {"items": items}


def merge(payload: dict, parts: dict[str, dict], generated_at: str | None = None) -> dict:
    """검사한 부분들을 payload["ai"]에 넣는다. 이번에 없는 부분은 이전 값을 그대로 둔다(일부 실패해도 나머지는 살림)."""
    ai = dict(payload.get("ai") or {})
    if "main" in parts:
        ai.update(parts["main"])
    why = dict(ai.get("why") or {})
    for name, part in parts.items():
        if name.startswith("why"):
            why.update(part["items"])
    ai["why"] = why
    ai["generatedAt"] = generated_at or datetime.now().astimezone().isoformat(timespec="minutes")
    return {**payload, "ai": ai}
