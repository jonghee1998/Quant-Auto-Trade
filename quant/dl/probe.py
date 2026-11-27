"""딥러닝 트랙(#74) 0단계 점검: 못 받은 종목이 '정말 없는 것'인지 '기호·기간 문제'인지 가른다. python -m quant.dl.probe

Tiingo가 공개하는 지원 종목 목록(supported_tickers.zip — 키 없음: 기호·거래소·시작일·끝일)과 R2의 manifest를 견준다.
- A 목록에 있고 필요한 기간을 덮음 → 다시 받으면 될 수 있다(무료로 고칠 수 있음)
- B 같은 기호가 있지만 기간이 다름 → 다른 회사가 기호를 다시 썼거나 일부만 있음
- C 목록에 없음 → Tiingo에는 없다(다른 출처 필요)
출력은 건수와 공개 시장 기호·날짜뿐이다. 전략 성과는 계산하지 않는다.
"""
from __future__ import annotations

import csv
import io
import os
import zipfile

from quant.ingest.http import Fetch, get_bytes, requests_fetch

from . import members as M
from .backfill import _minus, _plus
from .store import R2, configured

LIST_URL = "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip"
GATE = {"share": 0.90, "gone_share": 0.85}   # 계획 #74의 0단계 관문(바꾸지 않는다)


def supported(fetch: Fetch) -> dict[str, list[tuple[str, str]]]:
    """기호 → [(시작일, 끝일)] (주식만, 날짜가 있는 줄만)."""
    raw = get_bytes(fetch, LIST_URL, source="tiingo_list")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    out: dict[str, list[tuple[str, str]]] = {}
    for r in csv.DictReader(io.StringIO(text)):
        if (r.get("assetType") or "").strip().lower() != "stock" or not r.get("startDate") or not r.get("endDate"):
            continue
        out.setdefault(r["ticker"].strip().upper(), []).append((r["startDate"][:10], r["endDate"][:10]))
    return out


def need(spells: list[M.Spell], t: str) -> tuple[str, str, bool]:
    """표본 기호가 덮어야 하는 기간(지수 편입~편출, 관찰 구간 안)과 '중간에 사라졌나'."""
    sp = [s for s in spells if s.ticker == t and s.start <= M.WINDOW[1] and (s.end or "9999") >= M.WINDOW[0]]
    end = max(min(s.end or M.WINDOW[1], M.WINDOW[1]) for s in sp)
    start = max(min(s.start for s in sp), M.WINDOW[0])
    return start, end, any(s.end and s.end <= M.WINDOW[1] for s in sp)


def covers(first: str | None, last: str | None, start: str, end: str) -> bool:
    return bool(first and last and first <= _plus(start, 31) and last >= _minus(end, 31))


def classify(spells: list[M.Spell], manifest: dict, sample: list[str], listed: dict) -> dict:
    rows, n = [], {"A": 0, "B": 0, "C": 0}
    got = gone = gone_got = fix = gone_fix = 0
    for t in sample:
        if t not in manifest:
            continue
        s, e, is_gone = need(spells, t)
        info = manifest[t] or {}
        ok = covers(info.get("first"), info.get("last"), s, e)
        got += ok
        gone += is_gone
        gone_got += ok and is_gone
        if ok:
            continue
        spans = listed.get(t.replace(".", "-"), [])
        k = "A" if any(covers(a, z, s, e) for a, z in spans) else "B" if spans else "C"
        n[k] += 1
        fix += k == "A"
        gone_fix += k == "A" and is_gone
        rows.append({"ticker": t, "gone": is_gone, "need": f"{s}~{e}", "have": f"{info.get('first')}~{info.get('last')}" if info.get("rows") else "없음",
                     "class": k, "tiingo": ", ".join(f"{a}~{z}" for a, z in spans[:3]) or "—"})
    done = sum(1 for t in sample if t in manifest)
    best = {"share": (got + fix) / done if done else 0.0, "gone_share": (gone_got + gone_fix) / gone if gone else 1.0}
    return {"done": done, "n": len(sample), "covered": got, "gone": gone, "gone_covered": gone_got, "classes": n, "rows": rows,
            "best_if_A_fixed": best, "gate_possible": bool(best["share"] >= GATE["share"] and best["gone_share"] >= GATE["gone_share"])}


def card(r: dict) -> str:
    pc = lambda a, b: f"{a} / {b} ({a / b:.0%})" if b else "—"  # noqa: E731
    out = ["## #74 0단계 점검: 못 받은 종목의 원인",
           f"받은 표본 {r['done']} / {r['n']} · 시세 확보 {pc(r['covered'], r['done'])} · 사라진 종목 확보 {pc(r['gone_covered'], r['gone'])} "
           f"(관문 {GATE['share']:.0%} · {GATE['gone_share']:.0%})", "",
           f"- A 목록에 있고 기간도 덮음(다시 받으면 될 수 있음): **{r['classes']['A']}**",
           f"- B 같은 기호가 있지만 기간이 다름: **{r['classes']['B']}**",
           f"- C Tiingo 목록에 없음: **{r['classes']['C']}**",
           f"- A를 전부 고쳤을 때 최대: 시세 확보 {r['best_if_A_fixed']['share']:.0%} · 사라진 종목 {r['best_if_A_fixed']['gone_share']:.0%} → "
           f"관문 {'가능' if r['gate_possible'] else '불가'}", "",
           "| 기호 | 사라짐 | 필요한 기간 | 받은 기간 | 분류 | Tiingo 목록의 기간 |", "|---|---|---|---|---|---|"]
    out += [f"| {x['ticker']} | {'예' if x['gone'] else ''} | {x['need']} | {x['have']} | {x['class']} | {x['tiingo']} |" for x in r["rows"]]
    return "\n".join(out) + "\n"


def run(r2, fetch: Fetch, n: int = 200) -> str:
    spells = M.fetch_spells(fetch)
    return card(classify(spells, r2.get_json("manifest.json", {}) or {}, M.sample(spells, n), supported(fetch)))


def main() -> int:
    if not configured(os.environ):
        print("R2 설정 없음 → 건너뜀")
        return 0
    print(run(R2(), requests_fetch()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
