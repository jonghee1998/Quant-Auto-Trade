"""CLI. prepare: DB → .brief/in-<part>.json / save: .brief/out-<part>.json 검사 → daily_brief.payload["ai"].

python -m quant.brief.run prepare --dir .brief
python -m quant.brief.run save --dir .brief
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .core import PARTS, BriefError, check_main, check_why, cluster_news, merge, trend_targets


def _latest(conn) -> tuple:
    with conn.cursor() as cur:
        cur.execute("select date, payload from daily_brief order by date desc limit 1")
        return cur.fetchone() or (None, None)


def _news(conn, hours: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("""select title, url, publisher, source, published_at from news
                       where published_at >= now() - make_interval(hours => %s)""", (hours,))
        return [dict(zip(("title", "url", "publisher", "source", "published_at"), r)) for r in cur.fetchall()]


def _item_news(conn, items: list[dict]) -> dict[str, list[dict]]:
    """종목별 최근 30일 관련 뉴스 제목(미국은 종목 태그, 한국은 제목에 종목 이름)."""
    out: dict[str, list[dict]] = {}
    with conn.cursor() as cur:
        for e in items:
            if e["market"] == "US":
                cur.execute("""select title, url, publisher, published_at from news where %s = any(tickers)
                               and published_at >= now() - interval '30 days' order by published_at desc limit 8""", (e["code"],))
            elif len(e["name"]) >= 2:
                cur.execute("""select title, url, publisher, published_at from news where source in ('google_news', 'naver')
                               and title like %s and published_at >= now() - interval '30 days' order by published_at desc limit 8""",
                            (f"%{e['name']}%",))
            else:
                continue
            rows = [{"title": t, "url": u, "publisher": p, "at": str(a)[:10]} for t, u, p, a in cur.fetchall()]
            if rows:
                out[e["key"]] = rows
    return out


def _fundamentals(conn, codes: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    with conn.cursor() as cur:
        for c in codes:
            cur.execute("""select concept, period_end, value, filed_date, form from fundamentals
                           where market = 'US' and code = %s and concept in ('revenue', 'net_income', 'eps_diluted')
                           order by filed_date desc, period_end desc limit 12""", (c,))
            out[f"US:{c}"] = [{"concept": k, "period_end": str(p), "value": v, "filed": str(f), "form": fm}
                              for k, p, v, f, fm in cur.fetchall()]
    return out


def prepare(conn, d: Path) -> dict[str, int]:
    day, payload = _latest(conn)
    if not payload:
        raise SystemExit("daily_brief 없음")
    d.mkdir(parents=True, exist_ok=True)
    clusters = cluster_news(_news(conn, 36))
    us = [c for c in clusters if c["where"] == "미국"][:40]
    kr = [c for c in clusters if c["where"] == "한국"][:40]
    main = {"date": str(day), "quotes": payload.get("quotes"), "signals": payload.get("signals"),
            "bench": payload.get("bench"), "news": us + kr,
            "movers": {k: v[:5] for k, v in trend_targets(payload.get("universe", []), payload.get("bench", {}), 5).items()}}
    sizes = {"main": len(main["news"])}
    (d / "in-main.json").write_text(json.dumps(main, ensure_ascii=False, default=str))
    for part, items in trend_targets(payload.get("universe", []), payload.get("bench", {})).items():
        news = _item_news(conn, items)
        fund = _fundamentals(conn, [e["code"] for e in items if e["market"] == "US" and e["kind"] == "주식"])
        for e in items:
            e["news"] = news.get(e["key"], [])
            if e["key"] in fund:
                e["fundamentals"] = fund[e["key"]]
        (d / f"in-{part}.json").write_text(json.dumps({"date": str(day), "items": items}, ensure_ascii=False, default=str))
        sizes[part] = len(items)
    return sizes


def save(conn, d: Path, out=print) -> dict[str, str]:
    day, payload = _latest(conn)
    parts, status = {}, {}
    for part in PARTS:
        fin, fout = d / f"in-{part}.json", d / f"out-{part}.json"
        if not fin.exists() or not fout.exists():
            status[part] = "출력 없음"
            continue
        try:
            inp, res = json.loads(fin.read_text()), json.loads(fout.read_text())
            if inp.get("date") != str(day):
                raise BriefError(f"날짜 다름({inp.get('date')} ≠ {day})")
            parts[part] = check_main(res, inp) if part == "main" else check_why(res, inp)
            status[part] = "ok" if part == "main" else f"ok {len(parts[part]['items'])}/{len(inp['items'])}개"
        except (BriefError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            status[part] = f"실패: {e}"
    for k, v in status.items():
        out(f"{k}: {v}")
    if parts:
        new = merge(payload, parts)
        with conn.cursor() as cur:
            cur.execute("update daily_brief set payload = %s where date = %s", (json.dumps(new, ensure_ascii=False), day))
        conn.commit()
    return status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "save"])
    ap.add_argument("--dir", default=".brief")
    a = ap.parse_args()
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        if a.cmd == "prepare":
            print("입력:", prepare(conn, Path(a.dir)))
            return 0
        st = save(conn, Path(a.dir))
        return 0 if any(v.startswith("ok") for v in st.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
