import json

from quant.ingest import sec
from quant.ingest.http import Response


def _facts():
    def item(val, end, filed, form="10-Q", fy=2024, fp="Q1", start="2024-01-01"):
        return {"val": val, "end": end, "start": start, "filed": filed, "form": form, "fy": fy, "fp": fp}
    return {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [item(100, "2024-03-31", "2024-05-01"), item(101, "2024-03-31", "2024-06-01", "10-Q/A"),
                                       item(100, "2024-03-31", "2024-05-01"), item(5, "2024-03-31", "2024-05-02", "8-K")]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [item(999, "2024-03-31", "2024-05-01")]}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": [item(1.5, "2024-03-31", "2024-05-01")]}},
    }}}


class Fake:
    def __init__(self):
        self.calls = []

    def __call__(self, url, params=None, headers=None):
        self.calls.append((url, headers))
        if url == sec.TICKERS_URL:
            return Response(200, json.dumps({"0": {"cik_str": 1234, "ticker": "test01", "title": "가짜종목A"}}))
        return Response(200, json.dumps(_facts()))


def test_ticker_map_and_facts_point_in_time():
    f = Fake()
    m = sec.ticker_map(f, "합성앱 test@example.com")
    assert m == {"TEST01": 1234}
    rows = sec.company_facts(f, 1234, "test01", "합성앱 test@example.com")
    rev = [r for r in rows if r["concept"] == "revenue"]
    assert sorted((r["value"], r["filed_date"]) for r in rev) == [(100.0, "2024-05-01"), (101.0, "2024-06-01")]  # 정정 둘 다, 8-K·중복·뒤 태그 제외
    assert {r["concept"] for r in rows} == {"revenue", "eps_diluted"}
    assert f.calls[1][0].endswith("CIK0000001234.json")
    assert all(h["User-Agent"] for _, h in f.calls)


def test_run_skips_sec_without_user_agent():
    from datetime import date
    from quant.ingest.run import plan
    assert not [j for j in plan({}, date(2024, 1, 5), 5) if j[0] == "sec"]
    assert len([j for j in plan({"SEC_USER_AGENT": "x"}, date(2024, 1, 5), 5) if j[0] == "sec"]) == 10
