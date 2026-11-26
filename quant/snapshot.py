"""화면용 하루 요약(payload) 계산 → daily_brief 저장. 화면은 이 JSON만 읽는다.

python -m quant.snapshot  (DATABASE_URL 필요)
값이 없으면 null로 두고 화면이 "—"로 보여준다. 문장은 규칙 기반(유료 AI 없음).
"""
from __future__ import annotations

import json
import re
import math
import os
from datetime import date

import pandas as pd

from . import market as MK
from .ingest import universe as U

QUOTE_DEFS = [  # (id, 이름, 종류, 원천)
    ("spx", "미국 S&P 500 (SPY)", "etf", "SPY"),
    ("ndx", "미국 나스닥 100 (QQQ)", "etf", "QQQ"),
    ("korea", "한국 코스피", "kr", "KOSPI"),
    ("kosdaq", "한국 코스닥", "kr", "KOSDAQ"),
    ("usdkrw", "원/달러 환율", "macro", "DEXKOUS"),
    ("vix", "미국 불안 지수 VIX", "macro", "VIXCLS"),
    ("vkospi", "한국 불안 지수 VKOSPI", "kr", "VKOSPI"),
]
KR_INDEX_CODES = ("KOSPI", "KOSDAQ", "KOSPI200", "VKOSPI")


def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _ret(s: pd.Series, days: int) -> float | None:
    s = s.dropna()
    return _f((s.iloc[-1] / s.iloc[-1 - days] - 1) * 100) if len(s) > days else None


def quote(qid: str, name: str, s: pd.Series) -> dict:
    s = s.dropna()
    z = MK.move_z(s) if len(s) else {"change": None, "std": None}
    q = {"id": qid, "name": name, "value": _f(s.iloc[-1]) if len(s) else None, "change": _f(z["change"]),
         "dailyStd": _f(z["std"]), "m1": _ret(s, 21), "y1": _ret(s, 252)}
    if qid in ("vix", "vkospi", "usdkrw") and len(s) > 1:
        diff = s.iloc[-1] - s.iloc[-2]
        q["changeText"] = f"{'+' if diff >= 0 else '−'}{abs(diff):.1f}{'원' if qid == 'usdkrw' else ''}"
    if qid == "usdkrw":
        q["unit"] = "원"
    if qid == "vix":
        q["note"] = "보통 15~20 · 30 넘으면 공포"
    if qid == "vkospi":
        q["note"] = "VIX의 한국판(코스피200 옵션 기준)"
    return q


def summary_line(quotes: list[dict]) -> str:
    by = {q["id"]: q for q in quotes}

    def word(q):
        c, sd = (q or {}).get("change"), (q or {}).get("dailyStd")
        if c is None:
            return None
        size = "크게" if sd and abs(c / sd) >= 2 else "조금"
        return f"{size} {'올랐' if c > 0 else '내렸'}"
    parts = []
    us, kr = word(by.get("spx")), word(by.get("korea"))
    if us:
        parts.append(f"미국은 {us}고")
    if kr:
        parts.append(f"한국은 {kr}어요")
    vix = (by.get("vix") or {}).get("value")
    tail = "" if vix is None else (" 불안감(VIX)은 공포 수준이에요." if vix >= 30 else " 불안감(VIX)은 보통보다 높아요." if vix >= 20 else " 불안감(VIX)은 낮은 편이에요.")
    head = ", ".join(parts) if parts else "오늘 값이 아직 없어요"
    if parts and not head.endswith("요"):
        head += "요"
    return (head + "." if not head.endswith(".") else head) + tail


def universe_rows(px: pd.DataFrame, names: dict, kind: str, market: str) -> list[dict]:
    cols = [c for c in names if c in px.columns]
    if not cols:
        return []
    r = MK.period_returns(px[cols])
    return [{"code": c, "name": names[c], "kind": kind, "market": market, "r": [_f(r.loc[c, d]) for d in (21, 63, 126)]} for c in cols]


KR_BENCH = "069500"  # KODEX 200 — 코스피200을 따르는 ETF(지수 API 전까지 한국 기준선)
KR_EXCLUDE = ("레버리지", "인버스", "2X", "선물")  # 강한/약한 곳 목록을 배수·역방향 상품이 차지하지 않게


def pick_kr(rows: pd.DataFrame, n_stock: int = 300, n_etf: int = 100) -> tuple[pd.DataFrame, dict, dict]:
    """한국 전 종목(약 4천)에서 화면에 올릴 것만: 최근 20거래일 거래대금 상위 주식·ETF.
    rows: code, name, kind(stock/etf), date, close, volume. 반환: (종가 표, 주식 이름, ETF 이름)."""
    if rows.empty:
        return pd.DataFrame(), {}, {}
    rows = rows.assign(date=pd.to_datetime(rows["date"]))
    recent = rows[rows["date"] >= rows["date"].drop_duplicates().nlargest(20).min()]
    value = (recent["close"] * recent["volume"].fillna(0)).groupby(recent["code"]).mean()
    meta = rows.drop_duplicates("code", keep="last").set_index("code")
    def top(kind: str, n: int) -> dict:
        codes = [c for c in value.sort_values(ascending=False).index if meta.at[c, "kind"] == kind
                 and not (kind == "etf" and any(w in str(meta.at[c, "name"]) for w in KR_EXCLUDE))][:n]
        return {c: meta.at[c, "name"] or c for c in codes}
    stocks, etfs = top("stock", n_stock), top("etf", n_etf)
    keep = set(stocks) | set(etfs) | {KR_BENCH, *KR_INDEX_CODES}
    px = rows[rows["code"].isin(keep)].pivot(index="date", columns="code", values="close").sort_index()
    return px, stocks, etfs


KR_NEWS_SOURCES = {"naver", "google_news"}
# 시장과 상관없는 기업 홍보(보도자료 배포사)와 종목 추천 낚시형 제목은 홈에서 뺀다
PR_PUBLISHERS = ("globenewswire", "pr newswire", "prnewswire", "business wire", "businesswire", "accesswire",
                 "newsfile", "einpresswire")
CLICKBAIT = re.compile(r"^\d+\s+(ways|reasons|stocks?|things)\b|should you buy|better buy|time to buy|millionaire|"
                       r"(top|best)\s+\d*\s*stocks? to|buy (and|&) hold forever|no-brainer|could soar|i'?m buying",
                       re.IGNORECASE)


# 시장 전체 뉴스(Finnhub general)는 국제 정치 등 일반 뉴스도 섞인다 → 시장 단어가 있는 것만
MARKET_WORDS = re.compile(r"\b(stocks?|shares|equit(y|ies)|wall st(reet)?|s&p|nasdaq|dow|index(es)?|futures|fed|federal reserve|"
                          r"powell|rates?|yields?|treasur(y|ies)|bonds?|inflation|cpi|pce|jobs report|payrolls|unemployment|gdp|"
                          r"recession|earnings|profit|revenue|guidance|oil|crude|gold|dollar|currenc(y|ies)|tariffs?|"
                          r"ipo|markets?|investors?|traders?|rally|sell-?off|selloff|volatility|vix)\b", re.IGNORECASE)
SUFFIX = re.compile(r"\s+-\s+(reuters|cnbc|bloomberg|marketwatch|associated press|ap|wsj)$", re.IGNORECASE)


def _home_ok(x: dict) -> bool:
    pub = (x.get("publisher") or "").lower()
    return not any(p in pub for p in PR_PUBLISHERS) and not CLICKBAIT.search(x["title"])


def pick_news(news: list[dict], n_us: int = 3, n_kr: int = 2) -> list[dict]:
    """홈 뉴스: 최신순으로 미국 n_us·한국 n_kr. 미국은 시장 전체 뉴스를 먼저, 모자라면 종목 뉴스.
    보도자료·낚시형 제목은 빼고, 언론사만 다른 같은 제목은 하나로."""
    from .news_features import norm_title
    seen, kr = set(), []
    us_market, us_ticker = [], []
    for x in news:
        key = norm_title(x["title"])[:30]
        if not key or key in seen or not _home_ok(x):
            continue
        seen.add(key)
        if x.get("source") in KR_NEWS_SOURCES:
            if len(kr) < n_kr:
                kr.append({"title": x["title"], "where": "한국"})
        elif x.get("source") == "finnhub_market":
            if MARKET_WORDS.search(x["title"]):
                us_market.append({"title": SUFFIX.sub("", x["title"]), "where": "미국"})
        else:
            us_ticker.append({"title": x["title"], "where": "미국"})
    return (us_market + us_ticker)[:n_us] + kr


def coverage(universe: list[dict], kr_totals: dict) -> dict:
    """화면 목록이 전체 중 몇 개인지. 한국은 전 종목 중 거래대금 상위만, 미국·나라는 직접 고른 목록."""
    out: dict[str, dict] = {}
    for u in universe:
        k = f"{u['market']}/{u['kind']}"
        out.setdefault(k, {"shown": 0})["shown"] += 1
    notes = {"KR/주식": ("stock", "거래대금 상위"), "KR/업종": ("etf", "거래대금 상위(레버리지·인버스 제외)")}
    for k, v in out.items():
        if k in notes and kr_totals.get(notes[k][0]):
            v["total"], v["note"] = int(kr_totals[notes[k][0]]), notes[k][1]
        else:
            v["note"] = "직접 고른 대표 목록"
    return out


def signals(us_px: pd.DataFrame, macro: dict[str, pd.Series]) -> dict:
    """신호등 3가지(지금 상태 표시, 매매 신호 아님). 다 좋으면 green, 2개 yellow, 1개 이하 red. 계산 못 한 건 good=None."""
    spy = us_px["SPY"] if "SPY" in us_px else pd.Series(dtype=float)
    light = MK.trend_light(spy)
    gap = _f(light["gap_pct"])
    trend = {"key": "trend", "title": "추세", "good": None if gap is None else gap >= 0,
             "text": "데이터 부족" if gap is None else
             f"S&P 500이 200일 평균보다 {abs(gap):.1f}% {'위' if gap >= 0 else '아래'} ({'장기 상승 중' if gap >= 0 else '장기 하락 쪽'})"}
    sectors = [c for c in U.SECTORS if c.startswith("XL") and c in us_px]
    br = MK.breadth(us_px[sectors]) if sectors else {"above": 0, "total": 0}
    wide = {"key": "breadth", "title": "폭", "good": None if not br["total"] else br["above"] * 2 >= br["total"],
            "text": f"업종 {br['total']}개 중 {br['above']}개가 상승 추세" + (
                " (여러 업종이 함께 오르는 장)" if br["total"] and br["above"] * 2 >= br["total"] else " (오르는 업종이 적음)" if br["total"] else "")}
    vix, vxv = macro.get("VIXCLS", pd.Series(dtype=float)).dropna(), macro.get("VXVCLS", pd.Series(dtype=float)).dropna()
    hy = macro.get("BAMLH0A0HYM2", pd.Series(dtype=float)).dropna()
    parts, good = [], None
    if len(vix) and len(vxv):
        calm = vix.iloc[-1] < vxv.iloc[-1]
        good = calm
        parts.append("단기 불안(VIX)이 중기보다 " + ("낮음" if calm else "높음 — 당장 불안이 큼"))
    if len(hy) > 21:
        d = hy.iloc[-1] - hy.iloc[-22]
        ok = d < 0.3
        good = ok if good is None else (good and ok)
        parts.append(f"회사채 위험 가산금리 한 달 {'+' if d >= 0 else '−'}{abs(d):.2f}%p" + ("" if ok else " (빠르게 오름)"))
    risk = {"key": "risk", "title": "위험", "good": good, "text": " · ".join(parts) or "데이터 부족"}
    items = [trend, wide, risk]
    known = [i["good"] for i in items if i["good"] is not None]
    state = None if len(known) < 3 else ("green" if all(known) else "yellow" if sum(known) == 2 else "red")
    return {"state": state, "good": sum(known), "items": items}


def build_payload(us_px: pd.DataFrame, macro: dict[str, pd.Series], news: list[dict], kr_px: pd.DataFrame | None = None,
                  kr_names: dict | None = None, as_of: str | None = None, kr_etf_names: dict | None = None,
                  kr_totals: dict | None = None) -> dict:
    quotes = []
    for qid, name, kind, src in QUOTE_DEFS:
        if kind == "kr":
            s = kr_px[src] if kr_px is not None and src in kr_px else pd.Series(dtype=float)
            if qid == "korea" and s.dropna().empty and "EWY" in us_px:  # 지수가 아직 없으면 EWY(달러 기준)로 대신
                qid_name = "한국 (EWY · 달러 기준)"
                quotes.append(quote(qid, qid_name, us_px["EWY"]))
                continue
        else:
            s = us_px[src] if kind == "etf" and src in us_px else macro.get(src, pd.Series(dtype=float))
        quotes.append(quote(qid, name, s))
    sectors = [c for c in U.SECTORS if c.startswith("XL") and c in us_px]
    spy = us_px["SPY"] if "SPY" in us_px else pd.Series(dtype=float)
    light = MK.trend_light(spy)
    bench_us = [_ret(spy, d) for d in (21, 63, 126)]
    universe = (universe_rows(us_px, U.SECTORS, "업종", "US") + universe_rows(us_px, U.US_STOCK_NAMES, "주식", "US")
                + universe_rows(us_px, U.COUNTRIES, "나라", "W"))
    bench_kr = [None, None, None]
    if kr_px is not None and not kr_px.empty:
        universe += universe_rows(kr_px, kr_etf_names or {}, "업종", "KR") + universe_rows(kr_px, kr_names or {}, "주식", "KR")
        base = "KOSPI" if "KOSPI" in kr_px and kr_px["KOSPI"].notna().sum() > 126 else KR_BENCH
        if base in kr_px:
            bench_kr = [_ret(kr_px[base], d) for d in (21, 63, 126)]
    return {
        "asOf": as_of, "summary": summary_line(quotes), "quotes": quotes,
        "trendLight": {"state": light["state"], "gapPct": _f(light["gap_pct"])},
        "breadth": MK.breadth(us_px[sectors]) if sectors else {"above": 0, "total": 0},
        "signals": signals(us_px, macro),
        "coverage": coverage(universe, kr_totals or {}),
        "universe": universe, "bench": {"US": bench_us, "W": bench_us, "KR": bench_kr},
        "news": pick_news(news),
    }


def load_kr(conn, days: int = 200) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute("""select i.code, i.name, i.kind, p.date, p.close * p.adj_factor, p.volume from prices_daily p
                       join instruments i on i.id = p.instrument_id
                       where i.market = 'KR' and (p.date >= current_date - %s
                         or (i.kind = 'index' and p.date >= current_date - 400))""", (days,))  # 지수는 1년 수익률용으로 더 길게
        return pd.DataFrame(cur.fetchall(), columns=["code", "name", "kind", "date", "close", "volume"])


def load_from_db(conn, days: int = 400) -> tuple[pd.DataFrame, dict, list[dict]]:
    with conn.cursor() as cur:
        cur.execute("""select i.code, p.date, p.close * p.adj_factor from prices_daily p join instruments i on i.id = p.instrument_id
                       where i.market = 'US' and p.date >= current_date - %s""", (days,))
        px = pd.DataFrame(cur.fetchall(), columns=["code", "date", "close"])
        cur.execute("""select distinct on (series, ref_date) series, ref_date, value from macro_series
                       where ref_date >= current_date - %s order by series, ref_date, release_date desc""", (days,))
        mc = pd.DataFrame(cur.fetchall(), columns=["series", "date", "value"])
        # 미국 종목 뉴스가 하루 수백 건이라 최신 N건만 보면 다른 소스가 밀려난다 → 소스마다 최신 50건씩
        cur.execute("""select title, source, publisher from (
                         select title, source, publisher, published_at,
                                row_number() over (partition by source order by published_at desc) as rn from news) t
                       where rn <= 50 order by published_at desc""")
        news = [{"title": t, "source": s, "publisher": p} for t, s, p in cur.fetchall()]
    us = px.pivot(index="date", columns="code", values="close").sort_index() if len(px) else pd.DataFrame()
    us.index = pd.to_datetime(us.index)
    macro = {k: g.set_index(pd.to_datetime(g["date"]))["value"].sort_index() for k, g in mc.groupby("series")} if len(mc) else {}
    return us, macro, news


def save(conn, payload: dict, day: date) -> None:
    with conn.cursor() as cur:
        cur.execute("""insert into daily_brief (date, summary, payload) values (%s, %s, %s)
                       on conflict (date) do update set summary = excluded.summary, generated_at = now(),
                         -- 같은 날 다시 만들어도 AI가 쓴 부분(ai)은 지우지 않는다
                         payload = case when daily_brief.payload ? 'ai'
                                        then excluded.payload || jsonb_build_object('ai', daily_brief.payload -> 'ai')
                                        else excluded.payload end""",
                    (day, payload["summary"], json.dumps(payload, ensure_ascii=False)))
    conn.commit()


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL 없음 → 건너뜀")
        return 0
    import psycopg
    with psycopg.connect(url) as conn:
        us, macro, news = load_from_db(conn)
        if us.empty:
            print("시세가 아직 없음 → 건너뜀")
            return 0
        day = us.index[-1].date()
        kr_rows = load_kr(conn)
        kr_px, kr_stocks, kr_etfs = pick_kr(kr_rows)
        kr_totals = {}
        if not kr_rows.empty:
            last = kr_rows[kr_rows["date"] == kr_rows["date"].max()]
            kr_totals = last.groupby("kind")["code"].nunique().to_dict()
        payload = build_payload(us, macro, news, kr_px, kr_stocks, as_of=str(day), kr_etf_names=kr_etfs, kr_totals=kr_totals)
        save(conn, payload, day)
        print(f"daily_brief {day}: {payload['summary']}")
        cover: dict[str, int] = {}
        for u in payload["universe"]:
            k = f"{u['market']}/{u['kind']}"
            cover[k] = cover.get(k, 0) + (u["r"][2] is not None)
        print("화면 목록(6개월 수익률 있는 개수): " + ", ".join(f"{k} {v}" for k, v in sorted(cover.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
