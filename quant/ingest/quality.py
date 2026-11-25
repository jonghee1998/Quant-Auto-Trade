"""수집 결과 품질 점검. 문제는 막지 않고 목록으로 돌려준다(ingest_runs에 기록)."""
from __future__ import annotations

from collections import defaultdict


def check_prices(rows: list[dict], max_jump: float = 0.5) -> list[str]:
    issues: list[str] = []
    seen: set[tuple] = set()
    by_code: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        key = (r["market"], r["code"], r["date"])
        if key in seen:
            issues.append(f"중복 {r['market']}:{r['code']} {r['date']}")
        seen.add(key)
        hi, lo = r.get("high"), r.get("low")
        if hi is not None and lo is not None and hi < lo:
            issues.append(f"고가<저가 {r['code']} {r['date']}")
        by_code[(r["market"], r["code"])].append(r)
    for (_, code), rs in by_code.items():
        rs.sort(key=lambda r: r["date"])
        for a, b in zip(rs, rs[1:]):
            pa, pb = a["close"] * a.get("adj_factor", 1), b["close"] * b.get("adj_factor", 1)
            if pa > 0 and abs(pb / pa - 1) > max_jump:
                issues.append(f"급변 {code} {b['date']} {pb / pa - 1:+.0%}")
    return issues
