"""SEC EDGAR 재무(XBRL companyfacts). 공개 API, 키 없음. User-Agent(연락처)는 SEC_USER_AGENT 환경변수로만.

미래 데이터 금지: 각 값은 `filed`(공시 접수일) 다음 거래일부터 쓸 수 있다. 같은 기간 값이 정정되면 접수일이 다른 행으로 둘 다 남긴다.
"""
from __future__ import annotations

from .http import Fetch, get_json

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# 개념 → 후보 태그(앞에서부터 있는 것 사용)
CONCEPTS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "equity": ["StockholdersEquity"],
    "shares": ["CommonStockSharesOutstanding"],
}
FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A"}


def ticker_map(fetch: Fetch, user_agent: str) -> dict[str, int]:
    data = get_json(fetch, TICKERS_URL, None, {"User-Agent": user_agent}, source="sec")
    return {v["ticker"].upper(): int(v["cik_str"]) for v in data.values()}


def company_facts(fetch: Fetch, cik: int, ticker: str, user_agent: str) -> list[dict]:
    data = get_json(fetch, FACTS_URL.format(cik=cik), None, {"User-Agent": user_agent}, source="sec")
    gaap = (data.get("facts") or {}).get("us-gaap") or {}
    dei = (data.get("facts") or {}).get("dei") or {}
    rows: list[dict] = []
    for concept, tags in CONCEPTS.items():
        for tag in tags:
            node = gaap.get(tag) or dei.get(tag)
            if not node:
                continue
            for unit, items in (node.get("units") or {}).items():
                for it in items:
                    if it.get("form") not in FORMS or it.get("val") is None or not it.get("filed") or not it.get("end"):
                        continue
                    rows.append({"market": "US", "code": ticker.upper(), "concept": concept, "unit": unit,
                                 "period_start": it.get("start"), "period_end": it["end"],
                                 "fiscal_period": f"{it.get('fy')}{it.get('fp') or ''}", "value": float(it["val"]),
                                 "filed_date": it["filed"], "form": it["form"], "source": "sec"})
            break  # 앞 태그가 있으면 뒤 태그는 안 씀
    # 같은 (개념, 기간, 접수일) 중복 제거
    seen, out = set(), []
    for r in rows:
        k = (r["concept"], r["period_start"], r["period_end"], r["filed_date"], r["unit"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out
