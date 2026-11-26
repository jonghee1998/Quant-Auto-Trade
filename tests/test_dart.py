import io
import json
import zipfile
from datetime import date

import pytest

from quant.ingest import dart as D
from quant.ingest.http import HttpError, Response


class Fake:
    def __init__(self, *resps):
        self.resps, self.calls = list(resps), []

    def __call__(self, url, params=None, headers=None):
        self.calls.append((url, dict(params or {})))
        return self.resps.pop(0)


def _zip(xml: str) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("CORPCODE.xml", xml)
    return b.getvalue()


CORP = _zip("""<result><list><corp_code>00000001</corp_code><corp_name>가짜종목A</corp_name><stock_code>TEST</stock_code></list>
<list><corp_code>00000002</corp_code><corp_name>비상장</corp_name><stock_code> </stock_code></list>
<list><corp_code>00000003</corp_code><corp_name>가짜종목B</corp_name><stock_code>000003</stock_code></list></result>""")


def test_corp_codes_only_listed():
    m = D.corp_codes(Fake(Response(200, "", CORP)), "FAKEKEY")
    assert m == {"000003": "00000003"}  # 6자리 종목코드만(빈칸·6자리 아닌 값 제외 — 새 종목코드는 영문이 섞여도 6자리)


def test_corp_codes_bad_zip_is_error_without_key():
    with pytest.raises(HttpError) as e:
        D.corp_codes(Fake(Response(200, '{"status":"010"}', b'{"status":"010"}')), "FAKEKEY12345")
    assert "FAKEKEY" not in str(e.value)


def _it(acc, amt, add=None, fs="CFS", dt="2024.07.01 ~ 2024.09.30", rcept="20241114000123", code="000003"):
    return {"stock_code": code, "account_nm": acc, "fs_div": fs, "thstrm_dt": dt, "thstrm_amount": amt,
            "thstrm_add_amount": add, "rcept_no": rcept}


def test_q3_report_three_months_and_cumulative_and_cfs_first():
    items = [_it("매출액", "1,000", "2,700"), _it("매출액", "999", "2,000", fs="OFS"),
             _it("자본총계", "5,000", dt="2024.09.30 현재"), _it("이상한계정", "1")]
    rows = D.to_rows(items, "11014", 2024)
    rev = sorted((r["period_start"], r["value"]) for r in rows if r["concept"] == "revenue")
    assert rev == [("2024-01-01", 2700.0), ("2024-07-01", 1000.0)]  # 누적 9개월, 3개월
    eq = [r for r in rows if r["concept"] == "equity"][0]
    assert eq["period_start"] is None and eq["filed_date"] == "2024-11-14"  # 접수일 = 쓸 수 있는 날


def test_ofs_when_no_consolidated_and_q4_derived():
    fy = D.to_rows([_it("당기순이익", "1,200", fs="OFS", dt="2024.01.01 ~ 2024.12.31", rcept="20250320000001")], "11011", 2024)
    q3 = D.to_rows([_it("당기순이익", "300", "900", fs="OFS", rcept="20241114000123")], "11014", 2024)
    q4 = D.q4_rows(fy + q3)
    assert len(q4) == 1 and q4[0]["value"] == 300.0 and q4[0]["period_start"] == "2024-10-01"
    assert q4[0]["filed_date"] == "2025-03-20" and q4[0]["fiscal_period"] == "2024Q4"


def test_jobs_one_per_report_batch_and_zip_once():
    ok = Response(200, json.dumps({"status": "000", "list": [_it("매출액", "10", "10", dt="2024.01.01 ~ 2024.03.31", rcept="20240515000001")]}))
    none = Response(200, json.dumps({"status": "013", "message": "조회된 데이타가 없습니다."}))
    js = D.jobs("FAKEKEY", ["000003", "999999"], date(2024, 6, 1), years=1)
    assert [n for n, _ in js] == ["2024Q1 1/1", "2024Q2 1/1", "2024Q3 1/1", "2024FY 1/1"]
    f = Fake(Response(200, "", CORP), ok, none, none, none)
    rows = [r for _, fn in js for r in fn(f)]
    assert [r["value"] for r in rows] == [10.0]
    assert sum("corpCode" in u for u, _ in f.calls) == 1  # ZIP은 한 번만
    assert f.calls[1][1]["corp_code"] == "00000003" and f.calls[1][1]["reprt_code"] == "11013"


def test_error_status_raises():
    with pytest.raises(HttpError, match="status 020"):
        D.multi_accounts(Fake(Response(200, json.dumps({"status": "020", "message": "한도 초과"}))), "K", ["1"], 2024, "11011")
