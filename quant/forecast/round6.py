"""실험실 6차(Fable 설계 #85) 실행 본체: 나눠 파는 결말(E10), 계좌 채우는 순서, 세금 없는 계좌 안 G02, 긴 과거 관문.

결과표마다 '세법 확인 필요'. 판단(G)만 DSR을 쓴다. 숫자 규칙은 계획 그대로(eligibility6·pass_table6).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant.lab.backtest import Costs, run_backtest
from quant.lab.household import PLANS, Costs5, irr, max_dd, simulate, unit_price
from quant.lab.metrics import cagr, deflated_sharpe_excess, excess_sharpe
from quant.lab.splits import DEFAULT_SPLITS, VALID_DRAWDOWNS
from quant.lab.strategy import BuyAndHold

from .round5 import KRW5
from .rules import GrowthTrend
from .rules5 import Hold, IsaPlus, Pension
from .rules6 import Harvest, InsideSwitch, Ladder
from .synthetic import haircut

TAX_NOTE = "세법 확인 필요(22%·250만, ISA 2천만·1억·200만·9.9%, 연금 600만·13.2%·16.5%·5.5%)"
COSTS = [1.0, 2.0]
EXCL = ("2008-01-01", "2009-06-30")
PREV = 73


@dataclass(frozen=True)
class E6:
    id: str
    group: str
    hypothesis: str
    make: object                 # (ctx) → 정책
    plans: tuple
    base_plan: str
    ending: str = "E10"          # 판정 결말(해외 직접 계좌)


def _a4():
    return IsaPlus("BA4", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=5)


ROUND6: list[E6] = [
    E6("R6_H1", "H", "10년 나눠 파는 결말에서도 절세 매도가 IVV 보유보다 P150·L1억에서 각각 100만 원 이상", lambda c: Harvest("R6_H1"),
       ("P50", "P150", "L1천만", "L1억"), "P150"),
    E6("R6_W1", "W", "연금 600만 → ISA 5년 → 해외 직접 + 절세 매도가 중도 해지 기준 P150·P300에서 S&P +0.5%p 이상, W2·W3보다 높다",
       lambda c: Ladder("R6_W1", pension=True, isa=True), ("P50", "P150", "P300"), "P150"),
    E6("R6_W2", "W", "ISA 없이 연금 → 해외 직접 + 절세 매도도 P150·P300에서 S&P +0.3%p 이상", lambda c: Ladder("R6_W2", pension=True, isa=False),
       ("P50", "P150", "P300"), "P150"),
    E6("R6_W3", "W", "연금 없이 ISA 5년 → 해외 직접 + 절세 매도가 P150·P300에서 S&P +0.2%p 이상", lambda c: Ladder("R6_W3", pension=False, isa=True),
       ("P50", "P150", "P300"), "P150"),
    E6("R6_G1", "G", "ISA 안에서만 G02로 줄이면 같은 구조 그냥 보유(BA4)보다 +0.1%p 이상, 2008~09를 빼도 0 이상",
       lambda c: InsideSwitch("R6_G1", _a4(), "isa", c["spy"], c["unrate"]), ("P50", "P150", "L1억"), "P150"),
    E6("R6_G2", "G", "연금 안에서만 G02로 줄이면 같은 구조 그냥 보유(BP1)보다 +0.1%p 이상, 2008~09를 빼도 0 이상",
       lambda c: InsideSwitch("R6_G2", Pension("BP1", "early"), "pen", c["spy"], c["unrate"]), ("P50", "P150"), "P50"),
]
BENCH6: list[E6] = [
    E6("B00", "기준선", "SPY 해외 직접", lambda c: Hold("B00", "foreign", {"SPY": 1.0}), ("P50", "P150", "P300", "L1천만", "L1억"), "P150"),
    E6("BIV", "기준선", "IVV 해외 직접", lambda c: Hold("BIV", "foreign", {"IVV": 1.0}), ("P50", "P150", "P300", "L1천만", "L1억"), "P150"),
    E6("BA4", "기준선", "R5_A4 그대로", lambda c: _a4(), ("P50", "P150", "L1억"), "P150"),
    E6("BP1", "기준선", "R5_P1 그대로", lambda c: Pension("BP1", "early"), ("P50", "P150"), "P50"),
    E6("B90", "기준선", "SPY 90·SHY 10", lambda c: Hold("B90", "foreign", {"SPY": 0.9, "SHY": 0.1}, rebalance="year"), ("P150",), "P150"),
]


def ck(plan, k):
    return f"{plan}_x{k:g}"


def _run(px, fx, div, ctx, make, plan, k, start, end, cut=0.0):
    p = px
    if cut:
        p = px.copy()
        p["KSPX_N"] = haircut(px["KSPX_N"], cut)
    pol = make(ctx)
    return pol, simulate(p, fx, pol, PLANS[plan], start, end, costs=Costs5().scaled(k), krw=KRW5, div_yield=div)


def _m(r, fx, ending="E10"):
    f = fx.reindex(r.nav.index).ffill()
    up = unit_price(r.nav, r.flows)
    m = {"irr": irr(r.flows, r.endings[ending]), "irr_E0": irr(r.flows, r.endings["E0"]), "irr_E20": irr(r.flows, r.endings["E20"]),
         "final": {k: float(v) for k, v in r.endings.items()}, "mdd_krw": max_dd(up), "mdd_usd": max_dd(unit_price(r.nav / f, r.flows / f)),
         "paid_in": float(r.flows.sum()), "_up": up, "_upu": unit_price(r.nav / f, r.flows / f)}
    ex = up.drop(up.loc[EXCL[0]:EXCL[1]].index)
    m["_up_ex"] = ex
    return m


def run_batch6(px, fx, div, ctx, exps, benches, *, period="dev", cut=0.0, log=print) -> dict:
    start, end = DEFAULT_SPLITS.period(period)
    end = end or px.index[-1]
    rows, cache = [], {}
    for e in exps + benches:
        t0 = time.time()
        row = {"id": e.id, "group": e.group, "hypothesis": e.hypothesis, "benchmark": e in benches, "base": ck(e.base_plan, 1.0), "cond": {}}
        try:
            for plan in e.plans:
                for k in COSTS:
                    key = (e.id, plan, k)
                    pol, r = _run(px, fx, div, ctx, e.make, plan, k, start, end, cut)
                    m = _m(r, fx)
                    m["extra"] = {kk: vv for kk, vv in (getattr(pol, "extra", {}) or {}).items() if not kk.startswith("r20")}
                    cache[key] = m
                    row["cond"][ck(plan, k)] = m
            b = row["cond"][row["base"]]
            log(f"{e.id}: {row['base']} 세후(E10) {b['irr'] * 100:+.2f}% · E0 {b['irr_E0'] * 100:+.2f}% · 최악 {b['mdd_krw'] * 100:.0f}%/{b['mdd_usd'] * 100:.0f}% "
                f"({time.time() - t0:.0f}초)")
        except Exception as ex:  # noqa: BLE001
            row["error"] = f"{type(ex).__name__}: {ex}"
            log(f"{e.id}: 실패 {row['error']}")
        rows.append(row)
    by = {r["id"]: r for r in rows if "error" not in r}
    # 구조 몫·판단 몫
    for r in rows:
        if "error" in r or r["benchmark"]:
            continue
        for key, m in r["cond"].items():
            plan, k = key.rsplit("_x", 1)
            ref = by.get("B00", {}).get("cond", {}).get(key)
            if ref:
                m["struct_share"] = m["irr"] - ref["irr"]
                m["ref_mdd_krw"], m["ref_mdd_usd"] = ref["mdd_krw"], ref["mdd_usd"]
            if r["id"] == "R6_H1" and "BIV" in by and key in by["BIV"]["cond"]:
                m["vs_biv_krw"] = m["final"]["E10"] - by["BIV"]["cond"][key]["final"]["E10"]
                m["vs_biv_irr"] = m["irr"] - by["BIV"]["cond"][key]["irr"]
            if r["group"] == "G":
                bref = by.get("BA4" if r["id"] == "R6_G1" else "BP1", {}).get("cond", {}).get(key)
                if bref:
                    m["judge_share"] = m["irr"] - bref["irr"]
                    a, b = m["_up_ex"], bref["_up_ex"]
                    m["ex0809"] = float((a.iloc[-1] / a.iloc[0]) - (b.iloc[-1] / b.iloc[0])) if len(a) and len(b) else float("nan")
                    m["_pair"] = (m["_up"], bref["_up"])
    # G만 DSR(판단 몫 일수익)
    g_rows = [r for r in rows if r["group"] == "G" and "error" not in r]
    ex = [excess_sharpe(*r["cond"][r["base"]]["_pair"]) for r in g_rows if "_pair" in r["cond"][r["base"]]]
    ex = [x for x in ex if x == x]
    var = float(np.var(ex, ddof=1)) if len(ex) >= 2 else None
    for r in g_rows:
        m = r["cond"][r["base"]]
        if "_pair" in m:
            m["dsr"] = deflated_sharpe_excess(*m["_pair"], PREV + 9, var)
    if period == "valid":
        for r in rows:
            if "error" in r:
                continue
            for key, m in r["cond"].items():
                ref = by.get("B00", {}).get("cond", {}).get(key)
                if ref and key.endswith("_x1"):
                    m["valid_dd"] = {n: {"krw": _dd(m["_up"], a, b), "usd": _dd(m["_upu"], a, b), "spy_krw": _dd(ref["_up"], a, b),
                                         "spy_usd": _dd(ref["_upu"], a, b)} for n, (a, b) in VALID_DRAWDOWNS.items()}
    return {"rows": rows}


def _dd(s, a, b):
    x = s.loc[a:b]
    return float((x / x.cummax() - 1).min()) if len(x) > 1 else float("nan")


def strip(res):
    for r in res["rows"]:
        for m in r["cond"].values():
            for k in [k for k in m if k.startswith("_")]:
                m.pop(k)
    return res


def episodes(s: pd.Series, depth: float = 0.15) -> list[tuple[str, str]]:
    """직전 고점 대비 −depth 이하로 내려간 '고점일~최저일' 구간 전부(사람이 고르지 않음)."""
    s = s.dropna()
    out, peak_d, peak, trough_d, trough, deep = [], s.index[0], s.iloc[0], None, None, False
    for d, v in s.items():
        if v >= peak:
            if deep:
                out.append((str(peak_d.date()), str(trough_d.date())))
            peak, peak_d, trough, trough_d, deep = v, d, v, d, False
        else:
            if trough is None or v < trough:
                trough, trough_d = v, d
            if v / peak - 1 <= -depth:
                deep = True
    if deep:
        out.append((str(peak_d.date()), str(trough_d.date())))
    return out


def gl_report6(vf: pd.DataFrame, unrate: pd.DataFrame) -> dict:
    """R6_G0 관문: 달러·세금 0·비용(편도 0.08%) 포함, 1980~2022 하락 전부에서 G02가 1%p 이상 덜 빠진 횟수 > 절반, 1980~2003 연수익 ≥ 그냥 보유."""
    if "SPY" not in vf or vf["SPY"].dropna().empty:
        return {"status": "확인 못 함(VFINX 없음)", "pass": False}
    ones = pd.Series(1.0, index=vf.index)
    c = Costs(fee=0.0005, slippage=0.0003, fx_spread=0.0, tax_rate=0.0, dividend_tax=0.0)
    first = vf["SPY"].first_valid_index() + pd.Timedelta(days=300)
    s, t = max(pd.Timestamp("1980-01-02"), first), pd.Timestamp("2022-12-30")
    g = run_backtest(vf, ones, GrowthTrend("R6_G0", unrate.reindex(vf.index), avoid_equity=0.5), s, t, capital_krw=1e8, rebalance="M", costs=c)
    b = run_backtest(vf, ones, BuyAndHold("SPY"), s, t, capital_krw=1e8, rebalance="M", costs=c)
    eps = episodes(b.nav, 0.15)
    rows = []
    for a, z in eps:
        dg, db = _dd(g.nav, a, z), _dd(b.nav, a, z)
        rows.append({"from": a, "to": z, "g02": dg, "hold": db, "less": bool(dg > db + 0.01)})
    less = sum(r["less"] for r in rows)
    c1, c2 = cagr(g.nav.loc[:"2003-12-31"]), cagr(b.nav.loc[:"2003-12-31"])
    return {"status": "ok", "from": str(s.date()), "episodes": rows, "less": less, "n": len(rows), "cagr_80_03": c1, "hold_80_03": c2,
            "pass": bool(rows) and less > len(rows) / 2 and c1 >= c2}


def eligibility6(res, px, fx, div, ctx, tracking_ok: bool, gate: dict) -> dict:
    by = {r["id"]: r for r in res["rows"] if "error" not in r}
    out = {}
    # H
    if "R6_H1" in by:
        c = by["R6_H1"]["cond"]
        why = ""
        for p in ("P150", "L1억"):
            if not c[ck(p, 1.0)].get("vs_biv_krw", -1) >= 1_000_000:
                why = f"{p}에서 BIV보다 {c[ck(p, 1.0)].get('vs_biv_krw', 0) / 1e4:,.0f}만 원(< 100만)"
                break
            if not c[ck(p, 2.0)].get("vs_biv_krw", -1) > 0:
                why = f"{p} 비용 2배 ≤ 0"
                break
            if not c[ck(p, 1.0)]["struct_share"] > 0:
                why = f"{p} B00보다 낮음"
                break
        out["R6_H1"] = (not why, why or "", "H 묶음 닫음" if why else "")
    # W
    th = {"R6_W1": 0.005, "R6_W2": 0.003, "R6_W3": 0.002}
    for i, t in th.items():
        if i not in by:
            continue
        if not tracking_ok:
            out[i] = (False, "검산 '확인 못 함' — 보고만", "")
            continue
        c = by[i]["cond"]
        e = next(x for x in ROUND6 if x.id == i)
        why = ""
        if not all(c[ck(p, 1.0)]["struct_share"] >= t for p in ("P150", "P300")):
            why = f"(가) P150·P300 구조 몫 < {t * 100:.1f}%p"
        elif not all(c[ck(p, 2.0)]["struct_share"] > 0 for p in ("P150", "P300")):
            why = "(나) 비용 2배 ≤ 0"
        else:
            s, z = DEFAULT_SPLITS.period("dev")
            _, a = _run(px, fx, div, ctx, e.make, "P150", 1.0, s, z, 0.003)
            _, b = _run(px, fx, div, ctx, BENCH6[0].make, "P150", 1.0, s, z, 0.003)
            cut = irr(a.flows, a.endings["E10"]) - irr(b.flows, b.endings["E10"])
            if not cut > 0:
                why = f"(다) 0.3%p 더 깎으면 {cut * 100:+.2f}%p"
            else:
                pos = 0
                for y in (2004, 2006, 2008, 2010):
                    s2, z2 = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 7}-12-31")
                    _, a = _run(px, fx, div, ctx, e.make, "P150", 1.0, s2, z2)
                    _, b = _run(px, fx, div, ctx, BENCH6[0].make, "P150", 1.0, s2, z2)
                    pos += int(irr(a.flows, a.endings["E10"]) > irr(b.flows, b.endings["E10"]))
                if pos < 3:
                    why = f"(라) 8년 구간 4개 중 {pos}개만 > 0"
        out[i] = (not why, why, "")
    order_ok = all(i in by for i in th) and all(by["R6_W1"]["cond"][ck(p, 1.0)]["irr"] > max(by["R6_W2"]["cond"][ck(p, 1.0)]["irr"],
                                                                                              by["R6_W3"]["cond"][ck(p, 1.0)]["irr"]) for p in ("P150", "P300"))
    # G
    for i in ("R6_G1", "R6_G2"):
        if i not in by:
            continue
        c, base = by[i]["cond"], by[i]["base"]
        why = ""
        if not gate.get("pass"):
            why = "R6_G0 관문 실패 — G 묶음 닫음"
        elif not tracking_ok:
            why = "검산 '확인 못 함' — 보고만"
        elif not (c[base].get("judge_share", -1) >= 0.001 and c[base.replace("_x1", "_x2")].get("judge_share", -1) >= 0):
            why = "판단 몫 < +0.1%p 또는 비용 2배 < 0 — G 묶음 닫음"
        elif not c[base].get("ex0809", -1) >= 0:
            why = "2008~09를 빼면 같은 구조 보유보다 낮음 — G 묶음 닫음"
        out[i] = (not why, why, "")
    ok = lambda i: out.get(i, (False,))[0]  # noqa: E731
    promoted = []
    if ok("R6_H1"):
        promoted.append("R6_H1")
    ws = sorted([i for i in th if ok(i)], key=lambda i: -by[i]["cond"][ck("P150", 1.0)]["struct_share"])
    if ws:
        promoted.append(ws[0])
    gs = sorted([i for i in ("R6_G1", "R6_G2") if ok(i)], key=lambda i: -by[i]["cond"][by[i]["base"]]["judge_share"])
    if gs:
        promoted.append(gs[0])
    return {"by_id": {i: {"eligible": a, "why": w} for i, (a, w, _) in out.items()}, "promoted": promoted[:3], "order_ok": order_ok,
            "closed": sorted({w for _, w, _ in out.values() if "닫음" in w} | ({"H 묶음 닫음"} if out.get("R6_H1", (True,))[0] is False else set()))}


def pass_table6(res) -> dict:
    by = {r["id"]: r for r in res["rows"] if "error" not in r}
    out = {}
    for i, r in by.items():
        if r["benchmark"]:
            continue
        c, checks = r["cond"], []
        if i == "R6_H1":
            checks.append(("P150·L1억, 비용 1·2배 모두 BIV보다 많이 남음",
                           all(c[ck(p, k)].get("vs_biv_krw", -1) > 0 for p in ("P150", "L1억") for k in COSTS), ""))
        elif r["group"] == "W":
            checks.append(("① P150·P300 구조 몫 > 0(1·2배)", all(c[ck(p, k)]["struct_share"] > 0 for p in ("P150", "P300") for k in COSTS), ""))
            checks.append(("② 최악 손실 원화·달러 S&P보다 1%p 넘게 안 나쁨",
                           all(c[ck(p, 1.0)]["mdd_krw"] >= c[ck(p, 1.0)]["ref_mdd_krw"] - 0.01 and c[ck(p, 1.0)]["mdd_usd"] >= c[ck(p, 1.0)]["ref_mdd_usd"] - 0.01
                               for p in ("P150", "P300")), ""))
        elif r["group"] == "G":
            m, m2 = c[r["base"]], c[r["base"].replace("_x1", "_x2")]
            vd = m.get("valid_dd") or {}
            less = sum(1 for v in vd.values() if v["krw"] > v["spy_krw"] + 0.01 and v["usd"] > v["spy_usd"] + 0.01)
            checks += [("① 판단 몫 ≥ 0(1·2배)", m.get("judge_share", -1) >= 0 and m2.get("judge_share", -1) >= 0, ""),
                       ("② 세 하락 중 2번 이상 원화·달러 1%p 이상 덜 빠짐", less >= 2, f"{less}/3"),
                       ("③ 세후 ≥ B00 − 0.3%p", m["struct_share"] >= -0.003, ""),
                       ("④ DSR ≥ 0.95", (m.get("dsr") or 0) >= 0.95, f"{m.get('dsr', float('nan')):.2f}")]
        hard = [x for x in checks if x[1] is not None]
        out[i] = {"checks": checks, "pass": bool(hard) and all(x[1] for x in hard)}
    return out


def table6(res, period, plan, elig, passes, extra) -> str:
    p = lambda v, d=2: "—" if v is None or v != v else f"{v * 100:+.{d}f}%"  # noqa: E731
    out = [f"### 실험실 6차 · Fable 설계 #{plan} · {period} · 결말 E10(10년 나눠 팔기) 기준 세후 내부수익률 · {TAX_NOTE}", "",
           "| 실험 | 묶음 | 기준 일정 | 세후(E10) | E0 | 구조 몫(vs S&P) | 판단 몫 | 최악 원화/달러 | 일정별 구조 몫 | 자격 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        if "error" in r:
            out.append(f"| {r['id']} | {r['group']} | 실패: {r['error'][:80]} |" + " |" * 7)
            continue
        b = r["cond"][r["base"]]
        per = " / ".join(f"{k.split('_x')[0]} {p(m.get('struct_share'))}" for k, m in r["cond"].items() if k.endswith("_x1"))
        e = (elig or {}).get("by_id", {}).get(r["id"])
        tag = "기준선" if r["benchmark"] else ("—" if e is None else "✅ 올림" if r["id"] in elig["promoted"] else "자격" if e["eligible"] else f"✗ {e['why']}")
        h = f" · BIV보다 {b['vs_biv_krw'] / 1e4:+,.0f}만 원" if "vs_biv_krw" in b else ""
        out.append(f"| {r['id']} | {r['group']} | {r['base'].split('_x')[0]} | {p(b['irr'])} | {p(b['irr_E0'])} | {p(b.get('struct_share'))}{h} | "
                   f"{p(b.get('judge_share'))} | {p(b['mdd_krw'], 0)} / {p(b['mdd_usd'], 0)} | {per} | {tag} |")
    if elig:
        out += ["", f"검증으로 올림(계획 규칙대로 자동): {', '.join(elig['promoted']) or '없음 → 라운드 종료'} · 순서가 맞다(W1 > W2·W3): {elig['order_ok']}"
                + (f" · 닫음: {', '.join(elig['closed'])}" if elig.get("closed") else "")]
    if passes:
        out += ["", "#### 통과 기준(검증)"] + [f"- **{i}**: {'통과' if v['pass'] else '탈락'} — " + " · ".join(
            f"{n} {'○' if ok else '✗' if ok is False else '·'} {d}".strip() for n, ok, d in v["checks"]) for i, v in passes.items()]
    for k, v in extra.items():
        out += ["", f"#### {k}", "```", str(v), "```"]
    return "\n".join(out)
