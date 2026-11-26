"""수집 행 → Postgres upsert. 연결은 주입받는다(psycopg 3 호환 연결)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable


def _now() -> datetime:
    return datetime.now(timezone.utc)


def upsert_instruments(conn, rows: Iterable[dict]) -> dict[tuple[str, str], int]:
    """(market, code) → id. 이름·종류는 새 값이 있을 때만 갱신.
    종목마다 한 번씩 왕복하면 한국 전 종목(약 4천)에 2분 넘게 걸려서, 넣기 1번·읽기 1번으로 끝낸다."""
    uniq: dict[tuple[str, str], dict] = {}
    for r in rows:
        uniq.setdefault((r["market"], r["code"]), r)
    if not uniq:
        return {}
    with conn.cursor() as cur:
        cur.executemany(
            """insert into instruments (market, code, name, kind) values (%s, %s, %s, %s)
               on conflict (market, code) do update set name = coalesce(excluded.name, instruments.name)""",
            [(m, c, r.get("name"), r.get("kind") or "etf") for (m, c), r in uniq.items()])
        cur.execute(
            """select i.market, i.code, i.id from instruments i
               join unnest(%s::text[], %s::text[]) as k(market, code) on i.market = k.market and i.code = k.code""",
            ([m for m, _ in uniq], [c for _, c in uniq]))
        return {(m, c): i for m, c, i in cur.fetchall()}


def upsert_prices(conn, rows: list[dict]) -> int:
    ids = upsert_instruments(conn, rows)
    with conn.cursor() as cur:
        cur.executemany(
            """insert into prices_daily (instrument_id, date, open, high, low, close, adj_factor, volume, source)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               on conflict (instrument_id, date) do update set open = excluded.open, high = excluded.high,
                 low = excluded.low, close = excluded.close, adj_factor = excluded.adj_factor,
                 volume = excluded.volume, source = excluded.source""",
            [(ids[(r["market"], r["code"])], r["date"], r.get("open"), r.get("high"), r.get("low"), r["close"],
              r.get("adj_factor", 1.0), r.get("volume"), r["source"]) for r in rows])
    return len(rows)


def upsert_macro(conn, rows: list[dict]) -> int:
    with conn.cursor() as cur:
        cur.executemany(
            """insert into macro_series (series, ref_date, release_date, value, source) values (%s, %s, %s, %s, %s)
               on conflict (series, ref_date, release_date) do update set value = excluded.value""",
            [(r["series"], r["ref_date"], r["release_date"], r["value"], r["source"]) for r in rows])
    return len(rows)


def upsert_news(conn, rows: list[dict]) -> int:
    """같은 URL이 여러 종목에 걸리면 tickers를 합친다."""
    with conn.cursor() as cur:
        cur.executemany(
            """insert into news (url_hash, url, title, publisher, published_at, tickers, source)
               values (%s, %s, %s, %s, %s, %s, %s)
               on conflict (url_hash) do update set tickers =
                 (select array(select distinct unnest(news.tickers || excluded.tickers)))""",
            [(r["url_hash"], r["url"], r["title"], r.get("publisher"), r["published_at"], r.get("tickers", []),
              r["source"]) for r in rows])
    return len(rows)


def _days(r: dict) -> int:
    """기간 길이(일). 분기(약 90일)와 누적(180·270일), 시점 값(0)을 구분하는 키."""
    if not r.get("period_start"):
        return 0
    return (date.fromisoformat(str(r["period_end"])[:10]) - date.fromisoformat(str(r["period_start"])[:10])).days


def upsert_fundamentals(conn, rows: list[dict]) -> int:
    with conn.cursor() as cur:
        cur.executemany(
            """insert into fundamentals (market, code, concept, unit, period_start, period_end, period_days, fiscal_period, value,
                 filed_date, form, source) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               on conflict (market, code, concept, unit, period_end, period_days, filed_date) do update set value = excluded.value""",
            [(r["market"], r["code"], r["concept"], r["unit"], r.get("period_start"), r["period_end"], _days(r),
              r.get("fiscal_period"), r["value"], r["filed_date"], r.get("form"), r["source"]) for r in rows])
    return len(rows)


def start_run(conn, source: str, dataset: str) -> int:
    with conn.cursor() as cur:
        cur.execute("insert into ingest_runs (source, dataset, started_at, status) values (%s, %s, %s, 'running') returning id",
                    (source, dataset, _now()))
        return cur.fetchone()[0]


def finish_run(conn, run_id: int, status: str, rows: int, error: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute("update ingest_runs set finished_at = %s, status = %s, rows = %s, error = %s where id = %s",
                    (_now(), status, rows, (error or None) and error[:500], run_id))


def kr_done(conn, since) -> set[tuple[str, str]]:
    """data.go.kr에서 이미 받은 (kind, 날짜). 하루치가 충분히(100종목 이상) 들어온 날만 완료로 본다."""
    with conn.cursor() as cur:
        cur.execute("""select i.kind, p.date from prices_daily p join instruments i on i.id = p.instrument_id
                       where i.market = 'KR' and p.source = 'data.go.kr' and p.date >= %s
                       group by i.kind, p.date having count(*) >= 100""", (since,))
        return {(k, str(d)) for k, d in cur.fetchall()}
