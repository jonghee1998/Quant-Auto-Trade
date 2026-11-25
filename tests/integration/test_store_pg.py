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


def test_fundamentals_upsert_keeps_amendments(conn):
    from quant.ingest import store
    r = {"market": "US", "code": "TEST01", "concept": "revenue", "unit": "USD", "period_end": "2024-03-31",
         "value": 100.0, "filed_date": "2024-05-01", "source": "fake"}
    store.upsert_fundamentals(conn, [r, dict(r, value=101.0, filed_date="2024-06-01"), r])
    with conn.cursor() as cur:
        cur.execute("select count(*) from fundamentals where code = 'TEST01'")
        assert cur.fetchone() == (2,)


def test_db_registry_trials_and_final_once(conn):
    import pytest
    from quant.lab.registry import DbRegistry, Experiment
    reg = DbRegistry(conn)
    base = dict(strategy="fake_strategy", hypothesis="합성", params={}, data_version="v", code_version="c")
    r1 = reg.add(Experiment(period="dev", metrics={"sharpe": 0.5, "dsr": float("nan")}, **base))
    r2 = reg.add(Experiment(period="valid", metrics={"sharpe": 0.7}, **base))
    assert (r1["trial_no"], r2["trial_no"]) == (1, 2)
    assert reg.total_trials() >= 2 and 0.5 in reg.trial_sharpes()
    reg.add(Experiment(period="holdout", metrics={}, final=True, **base))
    with pytest.raises(PermissionError):
        reg.add(Experiment(period="holdout", metrics={}, final=True, **base))
def test_snapshot_roundtrip(conn):
    import datetime as dt
    import numpy as np
    from quant import snapshot as SN
    from quant.ingest import store
    today = dt.date.today()
    days = [today - dt.timedelta(days=i) for i in range(260, -1, -1)]
    rows = [{"market": "US", "code": "SPY", "date": d.isoformat(), "close": 100 + i * 0.1, "adj_factor": 1.0, "source": "fake", "kind": "etf"}
            for i, d in enumerate(days)]
    store.upsert_prices(conn, rows)
    store.upsert_macro(conn, [{"series": "VIXCLS", "ref_date": d.isoformat(), "release_date": d.isoformat(), "value": 15.0, "source": "fake"} for d in days[-30:]])
    us, macro, news = SN.load_from_db(conn)
    assert "SPY" in us.columns and "VIXCLS" in macro
    p = SN.build_payload(us, macro, news, as_of=str(today))
    SN.save(conn, p, today)
    with conn.cursor() as cur:
        cur.execute("select payload->'trendLight'->>'state' from daily_brief where date = %s", (today,))
        assert cur.fetchone() == ("green",)
