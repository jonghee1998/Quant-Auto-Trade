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


def test_upsert_instruments_bulk_keeps_names(conn):
    from quant.ingest import store
    rows = [{"market": "KR", "code": f"TEST{i:04d}", "name": f"가짜종목{i}", "kind": "stock"} for i in range(300)]
    ids = store.upsert_instruments(conn, rows)
    assert len(ids) == 300 and len(set(ids.values())) == 300
    again = store.upsert_instruments(conn, [dict(r, name=None) for r in rows[:10]] + [rows[0]])
    assert again == {k: ids[k] for k in again} and len(again) == 10
    with conn.cursor() as cur:
        cur.execute("select name from instruments where market = 'KR' and code = 'TEST0003'")
        assert cur.fetchone()[0] == "가짜종목3"


def test_snapshot_save_keeps_ai_part(conn):
    # 같은 날 스냅샷을 다시 만들어도 AI가 쓴 부분은 남아야 한다(수동 수집 때마다 지워지던 문제 방지)
    import json
    from datetime import date
    from quant import snapshot as SN
    day = date(2000, 1, 3)
    SN.save(conn, {"summary": "합성1", "quotes": []}, day)
    with conn.cursor() as cur:
        cur.execute("update daily_brief set payload = payload || %s::jsonb where date = %s", (json.dumps({"ai": {"market": {"us": "합성"}}}), day))
    SN.save(conn, {"summary": "합성2", "quotes": [1]}, day)
    with conn.cursor() as cur:
        cur.execute("select payload->'ai'->'market'->>'us', payload->>'summary', jsonb_array_length(payload->'quotes') from daily_brief where date = %s", (day,))
        assert cur.fetchone() == ("합성", "합성2", 1)



def test_fundamentals_quarter_and_ytd_same_end_both_kept(conn):
    # 10-Q: 같은 끝 날짜·접수일로 3개월 값과 6개월 누적 값 → 둘 다 남아야 한다(전엔 서로 덮어씀)
    from quant.ingest import store
    base = {"market": "US", "code": "TEST02", "concept": "revenue", "unit": "USD", "period_end": "2024-06-30",
            "fiscal_period": "2024Q2", "filed_date": "2024-08-01", "form": "10-Q", "source": "test"}
    store.upsert_fundamentals(conn, [dict(base, period_start="2024-04-01", value=100.0),
                                     dict(base, period_start="2024-01-01", value=190.0)])
    with conn.cursor() as cur:
        cur.execute("select period_days, value from fundamentals where code = 'TEST02' order by period_days")
        assert cur.fetchall() == [(90, 100.0), (181, 190.0)]



def test_kr_shares_only_when_changed(conn):
    from quant.ingest import store
    def rows(d, n):
        return [{"market": "KR", "code": "TEST03", "name": "가짜종목C", "kind": "stock", "date": d, "close": 1.0,
                 "source": "test", "shares": n}]
    store.upsert_prices(conn, rows("2024-01-02", 100.0))
    store.upsert_prices(conn, rows("2024-01-03", 100.0))  # 같으면 안 쌓임
    store.upsert_prices(conn, rows("2024-01-04", 120.0))
    with conn.cursor() as cur:
        cur.execute("select period_end::text, value from fundamentals where code = 'TEST03' and concept = 'shares' order by 1")
        assert cur.fetchall() == [("2024-01-02", 100.0), ("2024-01-04", 120.0)]
