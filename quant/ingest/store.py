"""수집 행 → Postgres upsert. 연결은 주입받는다(psycopg 3 호환 연결)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


def _now() -> datetime:
    return datetime.now(timezone.utc)


def upsert_instruments(conn, rows: Iterable[dict]) -> dict[tuple[str, str], int]:
    """(market, code) → id. 이름·종류는 새 값이 있을 때만 갱신."""
    ids: dict[tuple[str, str], int] = {}
    with conn.cursor() as cur:
        for r in rows:
            key = (r["market"], r["code"])
            if key in ids:
                continue
            cur.execute(
                """insert into instruments (market, code, name, kind) values (%s, %s, %s, %s)
                   on conflict (market, code) do update
                   set name = coalesce(excluded.name, instruments.name)
                   returning id""",
                (r["market"], r["code"], r.get("name"), r.get("kind") or "etf"))
            ids[key] = cur.fetchone()[0]
    return ids


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


def start_run(conn, source: str, dataset: str) -> int:
    with conn.cursor() as cur:
        cur.execute("insert into ingest_runs (source, dataset, started_at, status) values (%s, %s, %s, 'running') returning id",
                    (source, dataset, _now()))
        return cur.fetchone()[0]


def finish_run(conn, run_id: int, status: str, rows: int, error: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute("update ingest_runs set finished_at = %s, status = %s, rows = %s, error = %s where id = %s",
                    (_now(), status, rows, (error or None) and error[:500], run_id))
