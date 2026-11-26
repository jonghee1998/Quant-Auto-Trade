"""OpenDART: 한국 상장사 재무(매출·영업이익·순이익·자산·자본). 키 OPENDART_KEY(GitHub secret).

- 회사 코드: corpCode.xml(ZIP) → 종목코드 → 고유번호(8자리)
- 재무: 다중회사 주요계정(fnlttMultiAcnt, 한 번에 최대 100곳)을 연도·보고서별로
- 미래 데이터 금지: 접수일(rcept_no 앞 8자리)을 filed_date로 둔다. 화면·실험은 접수일 이후에만 쓴다.
- 손익: 분기·반기·3분기 보고서는 '그 분기 3개월'(thstrm_amount), 사업보고서는 1년.
  4분기 = 1년 − 3분기 누적(thstrm_add_amount). 누적과 3개월 값은 다르다.
- 연결(CFS)이 있으면 연결, 없으면 개별(OFS).
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta

from .http import Fetch, HttpError, get_bytes, get_json

BASE = "https://opendart.fss.or.kr/api"
REPORTS = {"11013": ("Q1", "1분기보고서"), "11012": ("Q2", "반기보고서"), "11014": ("Q3", "3분기보고서"), "11011": ("FY", "사업보고서")}
ACCOUNTS = {"매출액": "revenue", "영업이익": "op_income", "당기순이익": "net_income", "자본총계": "equity", "자산총계": "assets"}
FLOW = {"revenue", "op_income", "net_income"}  # 기간 값(손익). 나머지는 시점 값(재무상태)


def corp_codes(fetch: Fetch, key: str) -> dict[str, str]:
    """상장 종목코드(6자리) → 고유번호(8자리)."""
    raw = get_bytes(fetch, f"{BASE}/corpCode.xml", {"crtfc_key": key}, source="opendart")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read(z.namelist()[0])
    except zipfile.BadZipFile:
        raise HttpError("opendart: 회사 코드 파일이 ZIP이 아님(키 확인)") from None
    out = {}
    for it in ET.fromstring(xml).iter("list"):
        stock = (it.findtext("stock_code") or "").strip()
        if len(stock) == 6:
            out[stock] = it.findtext("corp_code").strip()
    return out


def _amount(v) -> float | None:
    s = str(v or "").replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _end(thstrm_dt: str) -> date | None:
    """'2024.01.01 ~ 2024.03.31' 또는 '2024.03.31 현재' → 끝 날짜."""
    parts = [p.strip() for p in str(thstrm_dt or "").replace("현재", "").split("~")]
    try:
        y, m, d = (int(x) for x in parts[-1].split("."))
        return date(y, m, d)
    except (ValueError, IndexError):
        return None


def _months_before(end: date, months: int) -> date:
    """끝 날짜(말일) 기준 months개월 기간의 첫날."""
    m = end.month - months + 1
    y = end.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return date(y, m, 1)


def multi_accounts(fetch: Fetch, key: str, corp: list[str], year: int, reprt: str) -> list[dict]:
    data = get_json(fetch, f"{BASE}/fnlttMultiAcnt.json",
                    {"crtfc_key": key, "corp_code": ",".join(corp), "bsns_year": str(year), "reprt_code": reprt},
                    source="opendart")
    st = str(data.get("status"))
    if st == "013":  # 조회된 데이터 없음(아직 공시 전)
        return []
    if st != "000":
        raise HttpError(f"opendart: status {st} {str(data.get('message', ''))[:80]}")
    return data.get("list") or []


def to_rows(items: list[dict], reprt: str, year: int) -> list[dict]:
    """한 보고서 응답 → fundamentals 행. 회사마다 연결(CFS) 우선."""
    fp, form = REPORTS[reprt]
    has_cfs = {it.get("stock_code") for it in items if it.get("fs_div") == "CFS"}
    rows = []
    for it in items:
        code = (it.get("stock_code") or "").strip()
        concept = ACCOUNTS.get(str(it.get("account_nm", "")).strip())
        if not code or not concept:
            continue
        if it.get("fs_div") != ("CFS" if code in has_cfs else "OFS"):
            continue
        end, rcept = _end(it.get("thstrm_dt")), str(it.get("rcept_no") or "")
        if not end or len(rcept) < 8:
            continue
        filed = f"{rcept[:4]}-{rcept[4:6]}-{rcept[6:8]}"
        base = {"market": "KR", "code": code, "concept": concept, "unit": "KRW", "filed_date": filed,
                "fiscal_period": f"{year}{fp}", "form": form, "source": "opendart"}
        if concept in FLOW:
            months = 12 if reprt == "11011" else 3
            v = _amount(it.get("thstrm_amount"))
            if v is not None:
                rows.append(dict(base, period_start=_months_before(end, months).isoformat(), period_end=end.isoformat(), value=v))
            cum = _amount(it.get("thstrm_add_amount"))
            if reprt == "11014" and cum is not None:  # 3분기 누적(9개월): 4분기 계산용
                rows.append(dict(base, period_start=_months_before(end, 9).isoformat(), period_end=end.isoformat(), value=cum,
                                 fiscal_period=f"{year}Q3누적"))
        else:
            v = _amount(it.get("thstrm_amount"))
            if v is not None:
                rows.append(dict(base, period_start=None, period_end=end.isoformat(), value=v))
    return rows


def q4_rows(rows: list[dict]) -> list[dict]:
    """4분기 = 1년 − 3분기 누적(같은 회사·같은 해 끝). 접수일은 사업보고서 날짜(그 전엔 알 수 없었다)."""
    def span(r):
        return (date.fromisoformat(r["period_end"]) - date.fromisoformat(r["period_start"])).days if r.get("period_start") else 0
    fy = {(r["code"], r["concept"], r["period_end"][:4]): r for r in rows if r["concept"] in FLOW and 350 <= span(r) <= 370}
    nine = {(r["code"], r["concept"], r["period_end"][:4]): r for r in rows if r["concept"] in FLOW and 260 <= span(r) <= 280}
    out = []
    for k, a in fy.items():
        b = nine.get(k)
        if not b:
            continue
        end = date.fromisoformat(a["period_end"])
        out.append(dict(a, period_start=_months_before(end, 3).isoformat(), value=a["value"] - b["value"],
                        fiscal_period=a["fiscal_period"].replace("FY", "Q4")))
    return out


def jobs(key: str, stock_codes: list[str], today: date, years: int = 3) -> list[tuple[str, callable]]:
    """(이름, 수집함수) 목록: 연도·보고서·100곳 묶음마다 하나씩(각자 시간·결과가 로그에 남고 시간 예산이 적용된다).
    회사 코드 ZIP은 처음 한 번만 받는다. 4분기 계산은 상세 화면(detail.fundamentals_view)이 한다."""
    cache: dict = {}
    n = (len(stock_codes) + 99) // 100

    def corps(f) -> list[str]:
        if "c" not in cache:
            m = corp_codes(f, key)
            cache["c"] = [m[c] for c in stock_codes if c in m]
        return cache["c"]
    out = []
    for y in range(today.year, today.year - years, -1):  # 최근 해부터
        for reprt, (fp, _form) in REPORTS.items():
            for b in range(n):
                out.append((f"{y}{fp} {b + 1}/{n}",
                            lambda f, y=y, reprt=reprt, b=b: to_rows(multi_accounts(f, key, corps(f)[b * 100:(b + 1) * 100], y, reprt), reprt, y)
                            if corps(f)[b * 100:(b + 1) * 100] else []))
    return out
