"""실제 Postgres(CI db 작업의 빈 테스트 DB)에서 upsert 확인. TEST_DATABASE_URL 없으면 건너뜀."""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL 없음")


@pytest.fixture
def conn():
    import psycopg
    c = psycopg.connect(URL)
    yield c
    c.rollback()
    c.close()


def test_prices_macro_news_upsert_idempotent(conn):
    from quant.ingest import store
    p = {"market": "US", "code": "TEST01", "date": "2024-01-02", "close": 10.0, "adj_factor": 1.0, "source": "fake", "kind": "etf"}
    assert store.upsert_prices(conn, [p]) == 1
    store.upsert_prices(conn, [dict(p, close=11.0)])
    m = {"series": "FAKE1", "ref_date": "2024-01-01", "release_date": "2024-01-02", "value": 1.0, "source": "fake"}
    store.upsert_macro(conn, [m, m])
    n = {"url_hash": "h1", "url": "https://example.com/x", "title": "합성", "published_at": "2024-01-02T00:00:00Z",
         "tickers": ["TEST01"], "source": "fake"}
    store.upsert_news(conn, [n])
    store.upsert_news(conn, [dict(n, tickers=["TEST02"])])
    rid = store.start_run(conn, "fake", "x")
    store.finish_run(conn, rid, "success", 3)
    with conn.cursor() as cur:
        cur.execute("select close from prices_daily join instruments i on i.id = instrument_id where i.code = 'TEST01'")
        assert cur.fetchall() == [(11.0,)]
        cur.execute("select count(*) from macro_series where series = 'FAKE1'")
        assert cur.fetchone() == (1,)
        cur.execute("select tickers from news where url_hash = 'h1'")
        assert sorted(cur.fetchone()[0]) == ["TEST01", "TEST02"]
        cur.execute("select status, rows from ingest_runs where id = %s", (rid,))
        assert cur.fetchone() == ("success", 3)
