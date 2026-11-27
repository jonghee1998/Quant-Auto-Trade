"""국내 시세 자료 점검(전략 성과는 계산하지 않는다): python -m quant.lab.kr_probe --n 50

국내 종목 갈아타기 실험을 설계하기 전에 자료 관문 숫자만 잰다. 관문은 실행 전에 고정했다(GATES).
- 공공데이터포털(금융위) 주식 일봉: 몇 년도부터 있는지, 과거 날짜에 지금은 사라진 종목이 들어 있는지, 거래대금 값
- 긴 과거(FinanceDataReader → KRX·네이버): 상장폐지 종목 표본(해시 순)의 시세 확보율, 2010년 이전 시세,
  분할·감자 같은 가격 점프를 보정할 수 있는지(시가총액 또는 KRX 등락률로 설명되는 비율)
결과는 건수·비율만 출력한다(종목 이름·코드는 출력하지 않는다). 키는 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import time
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Callable

import pandas as pd

from quant.ingest import sources as S
from quant.ingest.http import Fetch, HttpError, get_json, redact, requests_fetch

# 실행 전에 고정한 관문. 결과를 보고 바꾸지 않는다.
GATES = {"start_year": 2010, "gone_share": 0.85, "adjust_share": 0.80, "live_2010_min": 10}
YEARS = (2000, 2005, 2010, 2015, 2019, 2020, 2021)
WINDOW = ("2005-01-01", "2022-12-31")   # 긴 과거 시세를 받아 보는 범위
GONE_FROM = "2006-01-01"                # 이 날 이후(2022 말까지) 상장폐지된 종목에서 표본
LIMIT = 0.31                            # 하루 가격제한폭(±30%)을 넘는 종가 변화 = 권리 변동(분할·감자 등) 후보
MIN_ROWS = 20
LIVE_N = 30
TAIL = 10                               # 정리매매(가격제한 없음) 구간은 점프 계산에서 뺀다


def key_of(code: str) -> str:
    return hashlib.sha256(str(code).encode()).hexdigest()


def pick(codes, n: int) -> list[str]:
    """성적과 무관한 표본: 코드의 SHA-256 순서로 n개."""
    return sorted({str(c) for c in codes}, key=key_of)[:n]


# ------------------------------------------------------------------ 공공데이터포털
def portal_window(fetch: Fetch, key: str, start: date, end: date) -> dict:
    """기간 안에 자료가 있는지(건수)와 그 안의 기준일 하나, 거래대금 값이 있는지."""
    data = get_json(fetch, S.KR_ENDPOINTS["stock"],
                    {"serviceKey": S.kr_service_key(key), "resultType": "json", "numOfRows": 1, "pageNo": 1,
                     "beginBasDt": start.strftime("%Y%m%d"), "endBasDt": end.strftime("%Y%m%d")},
                    source="data.go.kr/stock")
    body = (data.get("response") or {}).get("body") or {}
    items = (body.get("items") or {}).get("item") or []
    if isinstance(items, dict):
        items = [items]
    first = items[0] if items else {}
    d = str(first.get("basDt") or "")
    return {"count": int(body.get("totalCount") or 0),
            "day": date(int(d[:4]), int(d[4:6]), int(d[6:])) if len(d) == 8 else None,
            "has_amount": first.get("trPrc") not in (None, "")}


def portal(fetch: Fetch, key: str, today: date) -> dict:
    out: dict = {"years": {}, "errors": []}
    for y in YEARS:
        try:
            out["years"][y] = portal_window(fetch, key, date(y, 1, 1), date(y, 2, 1))
        except (HttpError, ValueError, KeyError) as e:
            out["errors"].append(redact(f"{y}: {type(e).__name__} {e}", [key])[:120])
    have = sorted(y for y, w in out["years"].items() if w["count"] > 0 and w["day"])
    out["first_year"] = have[0] if have else None
    out["recent_codes"] = []
    try:
        recent = portal_window(fetch, key, today - timedelta(days=14), today)
        out["has_amount"] = recent["has_amount"]
        if recent["day"]:
            now = {r["code"] for r in S.kr_daily(fetch, "stock", recent["day"], key)}
            out["recent_n"] = len(now)
            out["recent_codes"] = sorted(now)
            if have:
                early = {r["code"] for r in S.kr_daily(fetch, "stock", out["years"][have[0]]["day"], key)}
                out["early_n"] = len(early)
                out["early_gone"] = len(early - now)
    except (HttpError, ValueError, KeyError) as e:
        out["errors"].append(redact(f"최근: {type(e).__name__} {e}", [key])[:120])
    return out


# ------------------------------------------------------------------ 긴 과거(FinanceDataReader)
def fdr_source() -> SimpleNamespace:
    """실제 호출(워크플로에서만). 테스트는 같은 모양의 가짜를 넣는다."""
    import FinanceDataReader as fdr
    return SimpleNamespace(
        listing=lambda: fdr.StockListing("KRX-DELISTING"),
        delisted=lambda code, s, e: fdr.DataReader(f"KRX-DELISTING:{code}", s, e),
        live=lambda code, s, e: fdr.DataReader(code, s, e))


def gone_sample(listing: pd.DataFrame, n: int) -> pd.DataFrame:
    """2006~2022에 상장폐지된 보통의 주식(스팩 제외)에서 해시 순 n개."""
    if listing is None or len(listing) == 0 or not {"Symbol", "DelistingDate"} <= set(listing.columns):
        return pd.DataFrame(columns=["Symbol", "ListingDate", "DelistingDate"])
    df = listing.copy()
    df["Symbol"] = df["Symbol"].astype(str)
    df["DelistingDate"] = pd.to_datetime(df["DelistingDate"], errors="coerce")
    df["ListingDate"] = pd.to_datetime(df.get("ListingDate"), errors="coerce")
    df = df[(df["DelistingDate"] >= GONE_FROM) & (df["DelistingDate"] <= WINDOW[1]) & df["Symbol"].str.fullmatch(r"\d{6}")]
    if "SecuGroup" in df.columns and (df["SecuGroup"] == "주권").any():
        df = df[df["SecuGroup"] == "주권"]
    if "Name" in df.columns:
        df = df[~df["Name"].astype(str).str.contains("스팩")]
    df = df.drop_duplicates("Symbol")       # 6자리 코드는 재사용될 수 있다 → 하나만
    chosen = pick(df["Symbol"], n)
    return df.set_index("Symbol").loc[chosen].reset_index()[["Symbol", "ListingDate", "DelistingDate"]]


def series_stats(df: pd.DataFrame | None) -> dict:
    """한 종목 시세: 줄 수·처음·끝, 가격 점프 수와 그중 설명되는 수(시가총액 불변 / KRX 등락률이 제한폭 안)."""
    out = {"rows": 0, "first": None, "last": None, "jumps": 0, "by_cap": 0, "by_rate": 0, "has_amount": False}
    if df is None or len(df) == 0 or "Close" not in df.columns:
        return out
    df = df[pd.to_numeric(df["Close"], errors="coerce") > 0].sort_index()
    out.update(rows=len(df), has_amount="Amount" in df.columns)
    if len(df) == 0:
        return out
    out.update(first=pd.Timestamp(df.index[0]).date(), last=pd.Timestamp(df.index[-1]).date())
    body = df.iloc[:-TAIL] if len(df) > TAIL + 2 else df
    ret = body["Close"].astype(float).pct_change()
    jump = ret.abs() > LIMIT
    out["jumps"] = int(jump.sum())
    if out["jumps"]:
        if "MarCap" in body.columns:
            cap = pd.to_numeric(body["MarCap"], errors="coerce").pct_change()
            out["by_cap"] = int((jump & (cap.abs() <= LIMIT)).sum())
        if "ChangeRate" in body.columns:
            rate = pd.to_numeric(body["ChangeRate"], errors="coerce")
            out["by_rate"] = int((jump & (rate.abs() <= LIMIT)).sum())
    return out


def long_history(src, n: int, live_codes: list[str], sleep: Callable[[float], None] = time.sleep) -> dict:
    out = {"sample": 0, "covered": 0, "pre2010": 0, "pre2010_ok": 0, "jumps": 0, "by_cap": 0, "by_rate": 0,
           "has_amount": False, "live_n": 0, "live_2010": 0, "errors": {}}

    def note(e: Exception):
        out["errors"][type(e).__name__] = out["errors"].get(type(e).__name__, 0) + 1

    try:
        sample = gone_sample(src.listing(), n)
    except Exception as e:  # 외부 라이브러리 오류는 종류만 남긴다
        note(e)
        sample = gone_sample(None, n)
    out["sample"] = len(sample)
    for row in sample.itertuples():
        start = max(pd.Timestamp(WINDOW[0]), row.ListingDate) if pd.notna(row.ListingDate) else pd.Timestamp(WINDOW[0])
        try:
            st = series_stats(src.delisted(row.Symbol, start.strftime("%Y-%m-%d"), row.DelistingDate.strftime("%Y-%m-%d")))
        except Exception as e:
            note(e)
            st = series_stats(None)
        ok = st["rows"] >= MIN_ROWS
        out["covered"] += ok
        out["has_amount"] |= st["has_amount"]
        for k in ("jumps", "by_cap", "by_rate"):
            out[k] += st[k]
        if pd.notna(row.ListingDate) and row.ListingDate < pd.Timestamp("2010-01-01") and row.DelistingDate > pd.Timestamp("2010-03-01"):
            out["pre2010"] += 1
            out["pre2010_ok"] += bool(ok and st["first"] and st["first"] <= date(2010, 1, 31))
        sleep(0.3)
    for code in pick([c for c in live_codes if str(c).isdigit() and len(str(c)) == 6], LIVE_N):
        out["live_n"] += 1
        try:
            out["live_2010"] += len(src.live(code, "2009-12-01", "2010-01-31")) > 0
        except Exception as e:
            note(e)
        sleep(0.2)
    return out


# ------------------------------------------------------------------ 판정·출력
def share(a: int, b: int) -> float:
    return a / b if b else 0.0


def gates(p: dict, h: dict) -> dict:
    """미리 정한 숫자로만 판정. 잴 수 없었던 항목은 미달로 본다."""
    portal_ok = p.get("first_year") is not None and p["first_year"] <= GATES["start_year"]
    long_ok = (h["pre2010"] > 0 and share(h["pre2010_ok"], h["pre2010"]) >= GATES["gone_share"]
               and h["live_2010"] >= GATES["live_2010_min"])
    best = max(h["by_cap"], h["by_rate"])
    out = {"start": portal_ok or long_ok,
           "gone": h["sample"] > 0 and share(h["covered"], h["sample"]) >= GATES["gone_share"],
           "adjust": h["covered"] > 0 and (h["jumps"] == 0 or share(best, h["jumps"]) >= GATES["adjust_share"])}
    out["all"] = all(out.values())
    return out


def card(p: dict, h: dict, g: dict) -> str:
    def mark(ok: bool) -> str:
        return "통과" if ok else "미달"

    years = ", ".join(f"{y}:{w['count']:,}" for y, w in sorted(p.get("years", {}).items())) or "잰 값 없음"
    lines = [
        "## 국내 시세 자료 점검",
        f"**관문: {mark(g['all'])}** (실행 전에 고정: {GATES['start_year']}년 이전 시작 · 사라진 종목 {GATES['gone_share']:.0%} · 보정 {GATES['adjust_share']:.0%})",
        "",
        "| 항목 | 값 | 판정 |",
        "|---|---|---|",
        f"| 공공데이터포털 주식 일봉 시작 | {p.get('first_year') or '확인 안 됨'} (연도별 1월 건수 {years}) | — |",
        f"| 포털 과거 날짜의 종목 중 지금 없는 종목 | {p.get('early_gone', '—')} / {p.get('early_n', '—')} (최근 {p.get('recent_n', '—')}종목) | — |",
        f"| 포털 거래대금 값 | {'있음' if p.get('has_amount') else '없음·확인 안 됨'} | — |",
        f"| 긴 과거: 2010년 이전 상장 표본의 2010-01 시세 | {h['pre2010_ok']} / {h['pre2010']} · 지금 상장 표본 {h['live_2010']} / {h['live_n']} | {mark(g['start'])} (시작 연도) |",
        f"| 사라진 종목 시세 확보({MIN_ROWS}일 이상) | {h['covered']} / {h['sample']} ({share(h['covered'], h['sample']):.0%}) | {mark(g['gone'])} |",
        f"| 가격 점프(±{LIMIT:.0%} 초과) 중 설명되는 것 | 점프 {h['jumps']} · 시가총액 {h['by_cap']} · 등락률 {h['by_rate']} | {mark(g['adjust'])} |",
        f"| 긴 과거 거래대금 값 | {'있음' if h['has_amount'] else '없음·확인 안 됨'} | — |",
    ]
    errs = list(p.get("errors", [])) + [f"{k} {v}건" for k, v in sorted(h["errors"].items())]
    if errs:
        lines += ["", "실패한 호출: " + " / ".join(errs)]
    return "\n".join(lines) + "\n"


def run(fetch: Fetch | None, key: str, src, today: date, n: int, sleep: Callable[[float], None] = time.sleep) -> str:
    p = portal(fetch, key, today) if (fetch and key) else {"years": {}, "errors": ["DATA_GO_KR_KEY 없음 — 포털 건너뜀"], "recent_codes": []}
    h = long_history(src, n, p.get("recent_codes", []), sleep=sleep)
    return redact(card(p, h, gates(p, h)), [key])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="사라진 종목 표본 수")
    a = ap.parse_args()
    key = os.environ.get("DATA_GO_KR_KEY", "")
    print(run(requests_fetch(), key, fdr_source(), date.today(), a.n))


if __name__ == "__main__":
    main()
