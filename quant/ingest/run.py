"""매일 수집: python -m quant.ingest.run [--days N]

키(환경변수)가 없는 소스는 건너뛰고, DATABASE_URL이 없으면 저장 없이 건수만 출력한다.
키 값은 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import functools
import time
from concurrent.futures import ThreadPoolExecutor
import os
from datetime import date, timedelta
from typing import Callable

from . import sec, sources as S, store, universe as U
from .http import Fetch, redact, requests_fetch
from .quality import check_prices

ENV = {"tiingo": ["TIINGO_TOKEN"], "fred": ["FRED_API_KEY"], "kr": ["DATA_GO_KR_KEY"],
       "naver": ["NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"], "finnhub": ["FINNHUB_TOKEN"], "sec": ["SEC_USER_AGENT"]}


def plan(env: dict, today: date, days: int, kr_have: set[tuple[str, str]] | None = None
         ) -> list[tuple[str, str, Callable[[Fetch], list[dict]], str]]:
    """(source, dataset, 수집함수, 저장 종류). 키가 없는 소스는 빠진다.
    kr_have: 이미 받은 data.go.kr (kind, 날짜) — 다시 받지 않는다(하루치가 2분쯤 걸려 이어 받기가 필요)."""
    kr_have = kr_have or set()
    start = today - timedelta(days=days)
    jobs = []
    if env.get("TIINGO_TOKEN"):
        for t in U.US_ETFS + U.US_STOCKS:  # 주식도 시세가 있어야 트렌드의 '주식'이 채워진다
            jobs.append(("tiingo", t, lambda f, t=t: S.tiingo_daily(f, t, start, today, env["TIINGO_TOKEN"]), "prices"))
    if env.get("FRED_API_KEY"):
        for s in U.FRED_SERIES:
            jobs.append(("fred", s, lambda f, s=s: S.fred_series(f, s, start, env["FRED_API_KEY"]), "macro"))
    if env.get("DATA_GO_KR_KEY"):
        for k in range(1, days + 1):  # 영업일 여부는 응답으로 판단(빈 응답이면 0건)
            d = today - timedelta(days=k)
            for kind in ("stock", "etf"):
                if (kind, str(d)) in kr_have:
                    continue
                jobs.append(("data.go.kr", f"{kind}:{d}", lambda f, kind=kind, d=d: S.kr_daily(f, kind, d, env["DATA_GO_KR_KEY"]), "prices"))
    for q in U.KR_NEWS_QUERIES:  # 키 없는 한국 헤드라인(네이버 키가 없을 때의 기본)
        jobs.append(("google_news", q, lambda f, q=q: S.google_news(f, q), "news"))
    if env.get("NAVER_CLIENT_ID") and env.get("NAVER_CLIENT_SECRET"):
        for q in U.KR_NEWS_QUERIES:
            jobs.append(("naver", q, lambda f, q=q: S.naver_news(f, q, env["NAVER_CLIENT_ID"], env["NAVER_CLIENT_SECRET"]), "news"))
    if env.get("FINNHUB_TOKEN"):
        for t in U.US_NEWS_TICKERS:
            jobs.append(("finnhub", t, lambda f, t=t: S.finnhub_news(f, t, today - timedelta(days=2), today, env["FINNHUB_TOKEN"]), "news"))
    if env.get("SEC_USER_AGENT"):
        ua = env["SEC_USER_AGENT"]
        cache: dict = {}

        def facts(f, t):
            if "map" not in cache:
                cache["map"] = sec.ticker_map(f, ua)
            cik = cache["map"].get(t)
            return sec.company_facts(f, cik, t, ua) if cik else []
        for t in U.US_STOCKS:
            jobs.append(("sec", t, lambda f, t=t: facts(f, t), "fundamentals"))
    return jobs


PARALLEL = {"data.go.kr": 4}  # 동시에 받을 개수(그 외 소스는 1개씩: 한도·순서가 중요)
SAVE = {"fundamentals": store.upsert_fundamentals, "prices": store.upsert_prices, "macro": store.upsert_macro, "news": store.upsert_news}


def run(env: dict, fetch: Fetch, conn=None, today: date | None = None, days: int = 5, out=print,
        sources: set[str] | None = None, budget_s: float | None = None, clock=time.monotonic) -> dict:
    """budget_s: 이 시간을 넘기면 남은 작업은 시작하지 않고 '시간 부족'으로 남긴다.
    (Actions 제한 시간에 걸려 로그·요약 없이 통째로 취소되는 일을 막는다)"""
    today = today or date.today()
    t0 = clock()
    secrets = [v for k, v in env.items() if any(w in k for w in ("KEY", "TOKEN", "SECRET", "DATABASE_URL", "AGENT")) and v]
    raw_out = out
    out = lambda msg: raw_out(redact(msg, secrets))  # noqa: E731 — 모든 출력에서 비밀값 가림
    missing = [s for s, keys in ENV.items() if not all(env.get(k) for k in keys)]
    if missing:
        out(f"키 없음 → 건너뜀: {', '.join(missing)}")
    summary = {"ok": 0, "failed": 0, "rows": 0, "issues": 0, "skipped": 0}
    kr_have = set()
    if conn and env.get("DATA_GO_KR_KEY") and (not sources or "data.go.kr" in sources):
        kr_have = store.kr_done(conn, today - timedelta(days=days))
        if kr_have:
            out(f"data.go.kr: 이미 받은 {len(kr_have)}개(종류·날짜)는 건너뜀")
    jobs = plan(env, today, days, kr_have)
    if sources:
        jobs = [j for j in jobs if j[0] in sources]
        out(f"고른 소스만: {', '.join(sorted(sources))}")
    # 응답이 느린 소스는 여러 개를 동시에 받는다(받기만 병렬, 저장·로그는 순서대로 하나씩)
    i = 0
    with ThreadPoolExecutor(max_workers=max(PARALLEL.values())) as pool:
        while i < len(jobs):
            if budget_s is not None and clock() - t0 > budget_s:
                summary["skipped"] += len(jobs) - i
                break
            src = jobs[i][0]
            size = PARALLEL.get(src, 1)
            batch = [jobs[i]]
            while len(batch) < size and i + len(batch) < len(jobs) and jobs[i + len(batch)][0] == src:
                batch.append(jobs[i + len(batch)])
            i += len(batch)

            def timed(collect):
                t = clock()
                try:
                    return collect(fetch), None, clock() - t
                except Exception as e:  # noqa: BLE001 — 한 작업 실패가 나머지를 막지 않는다
                    return None, e, clock() - t
            results = list(pool.map(lambda j: timed(j[2]), batch)) if len(batch) > 1 else [timed(batch[0][2])]
            for (source, dataset, _, kind), (rows, err, secs) in zip(batch, results):
                run_id = store.start_run(conn, source, dataset) if conn else None  # 실패하면 rollback으로 사라지므로 아래에서 새로 남긴다
                try:
                    if err is not None:
                        raise err
                    issues = check_prices(rows) if kind == "prices" else []
                    n = SAVE[kind](conn, rows) if conn and rows else len(rows)
                    if conn:
                        store.finish_run(conn, run_id, "partial" if issues else "success", n, "; ".join(issues[:20]) or None)
                        conn.commit()
                    summary["ok"] += 1
                    summary["rows"] += n
                    summary["issues"] += len(issues)
                    out(f"{source} {dataset}: {n}건" + (f", 점검 {len(issues)}" if issues else "") + f" ({secs:.0f}초)")
                except Exception as e:  # 한 소스 실패가 나머지를 막지 않는다
                    if conn:
                        conn.rollback()
                        store.finish_run(conn, store.start_run(conn, source, dataset), "failed", 0, redact(f"{type(e).__name__}: {e}", secrets))
                        conn.commit()
                    summary["failed"] += 1
                    out(f"{source} {dataset}: 실패 {type(e).__name__}: {e} ({secs:.0f}초)")
    if summary["skipped"]:
        out(f"시간 부족({budget_s:.0f}초 초과)으로 {summary['skipped']}개 작업을 건너뜀 — 다음 실행에서 이어서 받는다")
    out(f"합계: 성공 {summary['ok']}, 실패 {summary['failed']}, {summary['rows']}건, 점검 {summary['issues']}, 건너뜀 {summary['skipped']}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--budget-min", type=float, default=20, help="수집에 쓸 최대 분(Actions 제한 30분보다 작게)")
    ap.add_argument("--sources", default="", help="쉼표 구분: tiingo,fred,data.go.kr,google_news,naver,finnhub,sec (빈칸=전부)")
    a = ap.parse_args()
    env = dict(os.environ)
    conn = None
    if env.get("DATABASE_URL"):
        import psycopg
        conn = psycopg.connect(env["DATABASE_URL"])
    else:
        print("DATABASE_URL 없음 → 저장 없이 건수만 확인")
    sources = {x.strip() for x in a.sources.split(",") if x.strip()} or None
    out = functools.partial(print, flush=True)  # 파이프(tee)여도 줄마다 바로 로그에 남긴다
    s = run(env, requests_fetch(), conn, days=a.days, out=out, sources=sources, budget_s=a.budget_min * 60)
    return 1 if s["ok"] == 0 and s["failed"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
