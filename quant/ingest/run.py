"""매일 수집: python -m quant.ingest.run [--days N]

키(환경변수)가 없는 소스는 건너뛰고, DATABASE_URL이 없으면 저장 없이 건수만 출력한다.
키 값은 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from typing import Callable

from . import sources as S, store, universe as U
from .http import Fetch, requests_fetch
from .quality import check_prices

ENV = {"tiingo": ["TIINGO_TOKEN"], "fred": ["FRED_API_KEY"], "kr": ["DATA_GO_KR_KEY"],
       "naver": ["NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"], "finnhub": ["FINNHUB_TOKEN"]}


def plan(env: dict, today: date, days: int) -> list[tuple[str, str, Callable[[Fetch], list[dict]], str]]:
    """(source, dataset, 수집함수, 저장 종류). 키가 없는 소스는 빠진다."""
    start = today - timedelta(days=days)
    jobs = []
    if env.get("TIINGO_TOKEN"):
        for t in U.US_ETFS:
            jobs.append(("tiingo", t, lambda f, t=t: S.tiingo_daily(f, t, start, today, env["TIINGO_TOKEN"]), "prices"))
    if env.get("FRED_API_KEY"):
        for s in U.FRED_SERIES:
            jobs.append(("fred", s, lambda f, s=s: S.fred_series(f, s, start, env["FRED_API_KEY"]), "macro"))
    if env.get("DATA_GO_KR_KEY"):
        for k in range(1, days + 1):  # 영업일 여부는 응답으로 판단(빈 응답이면 0건)
            d = today - timedelta(days=k)
            for kind in ("stock", "etf"):
                jobs.append(("data.go.kr", f"{kind}:{d}", lambda f, kind=kind, d=d: S.kr_daily(f, kind, d, env["DATA_GO_KR_KEY"]), "prices"))
    if env.get("NAVER_CLIENT_ID") and env.get("NAVER_CLIENT_SECRET"):
        for q in U.KR_NEWS_QUERIES:
            jobs.append(("naver", q, lambda f, q=q: S.naver_news(f, q, env["NAVER_CLIENT_ID"], env["NAVER_CLIENT_SECRET"]), "news"))
    if env.get("FINNHUB_TOKEN"):
        for t in U.US_NEWS_TICKERS:
            jobs.append(("finnhub", t, lambda f, t=t: S.finnhub_news(f, t, today - timedelta(days=2), today, env["FINNHUB_TOKEN"]), "news"))
    return jobs


SAVE = {"prices": store.upsert_prices, "macro": store.upsert_macro, "news": store.upsert_news}


def run(env: dict, fetch: Fetch, conn=None, today: date | None = None, days: int = 5, out=print) -> dict:
    today = today or date.today()
    missing = [s for s, keys in ENV.items() if not all(env.get(k) for k in keys)]
    if missing:
        out(f"키 없음 → 건너뜀: {', '.join(missing)}")
    summary = {"ok": 0, "failed": 0, "rows": 0, "issues": 0}
    for source, dataset, collect, kind in plan(env, today, days):
        run_id = store.start_run(conn, source, dataset) if conn else None
        try:
            rows = collect(fetch)
            issues = check_prices(rows) if kind == "prices" else []
            n = SAVE[kind](conn, rows) if conn and rows else len(rows)
            if conn:
                store.finish_run(conn, run_id, "partial" if issues else "success", n, "; ".join(issues[:20]) or None)
                conn.commit()
            summary["ok"] += 1
            summary["rows"] += n
            summary["issues"] += len(issues)
            out(f"{source} {dataset}: {n}건" + (f", 점검 {len(issues)}" if issues else ""))
        except Exception as e:  # 한 소스 실패가 나머지를 막지 않는다
            if conn:
                conn.rollback()
                store.finish_run(conn, store.start_run(conn, source, dataset), "failed", 0, str(e))
                conn.commit()
            summary["failed"] += 1
            out(f"{source} {dataset}: 실패 {type(e).__name__}: {e}")
    out(f"합계: 성공 {summary['ok']}, 실패 {summary['failed']}, {summary['rows']}건, 점검 {summary['issues']}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    a = ap.parse_args()
    env = dict(os.environ)
    conn = None
    if env.get("DATABASE_URL"):
        import psycopg
        conn = psycopg.connect(env["DATABASE_URL"])
    else:
        print("DATABASE_URL 없음 → 저장 없이 건수만 확인")
    s = run(env, requests_fetch(), conn, days=a.days)
    return 1 if s["ok"] == 0 and s["failed"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
