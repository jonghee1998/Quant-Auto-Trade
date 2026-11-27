"""실험실 5차(Fable 설계 #79) 실행 본체: 입금 일정 × 계좌 구조. 예측 없음.

- 납입 일정 P50·P150·L1천만·L1억 × 비용 1·2배. 기준 조건: I 묶음 L1억·1배, 나머지 P150·1배.
- 수익률 = 내부수익률(마지막 날 다 팔고 세금 낸 금액). 구조 몫 = 전략 − 같은 일정 B00(SPY 해외 직접).
- 최악 손실 = 입금 효과를 뺀 단위 가격, 세금 전 평가액, 원화·달러 둘 다.
- 자격·통과는 계획 숫자 그대로(eligibility5, pass_table5). DSR·알파는 쓰지 않는다(세율 차이가 날마다 쌓인 값 — 판정 #77).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd

from quant.lab.household import PLANS, Costs5, dd_in, irr, max_dd, simulate, unit_price
from quant.lab.splits import DEFAULT_SPLITS, VALID_DRAWDOWNS

from .rules5 import Hold, IsaPlus, Pension
from .synthetic import KRW_ASSETS, haircut

KRW5 = KRW_ASSETS | {"KSPX_N"}
PLAN_IDS = ["P50", "P150", "L1천만", "L1억"]
COSTS = [1.0, 2.0]
DEV_DECLINES = {"2007-10~2009-03": ("2007-10-01", "2009-03-31"), "2010-04~07": ("2010-04-01", "2010-07-31"),
                "2011-04~10": ("2011-04-01", "2011-10-31"), "2015-07~2016-02": ("2015-07-01", "2016-02-29")}


@dataclass(frozen=True)
class E5:
    id: str
    group: str            # H / I / A / P / 기준선 / 재보고
    hypothesis: str
    make: object          # () → 정책
    plans: tuple = tuple(PLAN_IDS)
    base_plan: str = "P150"


def ck(plan: str, k: float) -> str:
    return f"{plan}_x{k:g}"


def b00():
    return Hold("B00", "foreign", {"SPY": 1.0})


ROUND5: list[E5] = [
    E5("R5_H1", "H", "적립식에서도 절세 매도가 IVV 보유보다 세후 높다: P50 +0.20, P150 +0.08, L1천만 +0.30%p, L1억 > 0",
       lambda: Hold("R5_H1", "foreign", {"SPY": 1.0}, harvest=True)),
    E5("R5_I1", "I", "배당세 15%를 넣어도 절세계좌형 국내 S&P가 해외 직접 S&P보다 +0.30%p 이상",
       lambda: Hold("R5_I1", "isa", {"KSPX_N": 1.0}), ("L1억", "L1천만"), "L1억"),
    E5("R5_I2", "I", "같은 계좌 90:10은 S&P보다 같거나 높고 하락 4번 중 3번 이상 원화·달러 모두 0.95배 이하",
       lambda: Hold("R5_I2", "isa", {"KSPX_N": 0.9, "KUST_U": 0.1}, rebalance="band"), ("L1억", "L1천만"), "L1억"),
    E5("R5_I3", "I", "같은 계좌 80:20은 S&P −0.3%p 이내이고 I2보다 덜 빠진다",
       lambda: Hold("R5_I3", "isa", {"KSPX_N": 0.8, "KUST_U": 0.2}, rebalance="band"), ("L1억", "L1천만"), "L1억"),
    E5("R5_A1", "A", "현실 ISA(연 2천만·3년 순환) 먼저 + 넘친 돈 해외 직접 SPY가 모든 일정에서 S&P보다 +0.10%p 이상",
       lambda: IsaPlus("R5_A1", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=3), ("P50", "P150", "L1억")),
    E5("R5_A2", "A", "A1 + 바깥 절세 매도가 A1보다 높고 P150·L1억에서 R5_H1보다도 높다",
       lambda: IsaPlus("R5_A2", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=3, out_harvest=True), ("P50", "P150", "L1억")),
    E5("R5_A3", "A", "각 계좌 안 90:10이 S&P보다 같거나 높고 하락 4번 중 3번 이상 원화·달러 모두 0.95배 이하",
       lambda: IsaPlus("R5_A3", {"KSPX_N": 0.9, "KUST_U": 0.1}, {"SPY": 0.9, "SHY": 0.1}, years=3), ("P50", "P150", "L1억")),
    E5("R5_A4", "A", "ISA 만기 5년이 3년 순환(A1)보다 P150·L1억에서 높다",
       lambda: IsaPlus("R5_A4", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=5), ("P50", "P150", "L1억")),
    E5("R5_A5", "A", "A3 + 바깥 절세 매도가 S&P보다 +0.10%p 이상이고 A3의 덜 빠짐을 그대로 가진다",
       lambda: IsaPlus("R5_A5", {"KSPX_N": 0.9, "KUST_U": 0.1}, {"SPY": 0.9, "SHY": 0.1}, years=3, out_harvest=True),
       ("P50", "P150", "L1억")),
    E5("R5_P1", "P", "(보고 전용) 연금저축 + 환급금 재투자가 중도 해지 기준으로도 S&P −0.2%p 이내",
       lambda: Pension("R5_P1", "early"), ("P50",), "P50"),
]
BENCH5: list[E5] = [
    E5("B00", "기준선", "SPY 해외 직접", b00),
    E5("BIV", "기준선", "IVV 해외 직접", lambda: Hold("BIV", "foreign", {"IVV": 1.0})),
    E5("B90", "기준선", "SPY 90·SHY 10(해마다)", lambda: Hold("B90", "foreign", {"SPY": 0.9, "SHY": 0.1}, rebalance="year")),
    E5("B80", "기준선", "SPY 80·SHY 20(해마다)", lambda: Hold("B80", "foreign", {"SPY": 0.8, "SHY": 0.2}, rebalance="year")),
    E5("BKR", "기준선", "국내 일반 KSPX_N", lambda: Hold("BKR", "domestic", {"KSPX_N": 1.0})),
    E5("BKR_c26", "기준선", "국내 일반 + 종합과세 26.4%", lambda: Hold("BKR_c26", "domestic", {"KSPX_N": 1.0}, comp_rate=0.264)),
    E5("BKR_c38", "기준선", "국내 일반 + 종합과세 38.5%", lambda: Hold("BKR_c38", "domestic", {"KSPX_N": 1.0}, comp_rate=0.385)),
]


def run_sim(px, fx, e_make, plan: str, k: float, start, end, div, kspx_cut: float = 0.0, kspx_col: str = "KSPX_N"):
    p = px
    if kspx_cut:
        p = px.copy()
        p["KSPX_N"] = haircut(px["KSPX_N"], kspx_cut)
    if kspx_col != "KSPX_N":
        p = p.copy()
        p["KSPX_N"] = px[kspx_col]
    pol = e_make()
    r = simulate(p, fx, pol, PLANS[plan], start, end, costs=Costs5().scaled(k), krw=KRW5, div_yield=div)
    return pol, r


def measure(r, fx, ref) -> dict:
    up = unit_price(r.nav, r.flows)
    f = fx.reindex(r.nav.index).ffill()
    up_usd = unit_price(r.nav / f, r.flows / f)
    m = {"irr": irr(r.flows, float(r.liq.iloc[-1])), "mdd_krw": max_dd(up), "mdd_usd": max_dd(up_usd),
         "final_liq": float(r.liq.iloc[-1]), "paid_in": float(r.flows.sum()), "taxes": r.taxes, "trades": r.trades,
         "_up": up, "_upu": up_usd}
    if ref is not None:
        m["struct_share"] = m["irr"] - ref["irr"]
        m["ref_irr"], m["ref_mdd_krw"], m["ref_mdd_usd"] = ref["irr"], ref["mdd_krw"], ref["mdd_usd"]
    return m


def declines(m: dict, ref: dict, windows: dict) -> dict:
    out = {}
    for k, (a, b) in windows.items():
        s_k, r_k = dd_in(m["_up"], a, b), dd_in(ref["_up"], a, b)
        s_u, r_u = dd_in(m["_upu"], a, b), dd_in(ref["_upu"], a, b)
        out[k] = {"krw": s_k, "spy_krw": r_k, "usd": s_u, "spy_usd": r_u,
                  "both_095": bool(s_k >= 0.95 * r_k and s_u >= 0.95 * r_u)}
    return out


def run_batch5(px, fx, div, exps: list[E5], benches: list[E5], *, period: str = "dev", kspx_cut: float = 0.0, log=print) -> dict:
    start, end = DEFAULT_SPLITS.period(period)
    end = end or px.index[-1]
    refs = {}
    rows = []
    windows = DEV_DECLINES if period == "dev" else VALID_DRAWDOWNS
    for e in exps + benches:
        t0 = time.time()
        row = {"id": e.id, "group": e.group, "hypothesis": e.hypothesis, "benchmark": e in benches, "base": ck(e.base_plan, 1.0), "cond": {}}
        plans = PLAN_IDS if e in benches else list(e.plans)
        try:
            for plan in plans:
                for k in COSTS:
                    key = ck(plan, k)
                    if key not in refs:
                        _, rr = run_sim(px, fx, b00, plan, k, start, end, div, kspx_cut)
                        refs[key] = measure(rr, fx, None)
                    pol, r = run_sim(px, fx, e.make, plan, k, start, end, div, kspx_cut)
                    m = measure(r, fx, refs[key])
                    m["extra"] = dict(getattr(pol, "extra", {}) or {})
                    if k == 1.0:
                        m["declines"] = declines(m, refs[key], windows)
                    row["cond"][key] = m
            if e.group == "P":  # 연금 수령 기준도 같이
                pol, r = run_sim(px, fx, lambda: Pension("R5_P1", "annuity"), "P50", 1.0, start, end, div, kspx_cut)
                row["cond"]["P50_x1"]["irr_annuity"] = measure(r, fx, refs[ck("P50", 1.0)])["irr"]
            b = row["cond"][row["base"]] if row["base"] in row["cond"] else next(iter(row["cond"].values()))
            log(f"{e.id}: {row['base']} 세후 연수익 {b['irr'] * 100:+.2f}% (S&P {b.get('ref_irr', b['irr']) * 100:+.2f}%), "
                f"최악(원화·달러) {b['mdd_krw'] * 100:.0f}%·{b['mdd_usd'] * 100:.0f}% ({time.time() - t0:.0f}초)")
        except Exception as ex:  # noqa: BLE001
            row["error"] = f"{type(ex).__name__}: {ex}"
            log(f"{e.id}: 실패 {row['error']}")
        rows.append(row)
    return {"rows": rows, "refs": {k: {kk: v for kk, v in m.items() if not kk.startswith("_")} for k, m in refs.items()},
            "_refs": refs}


def strip(res: dict) -> dict:
    for r in res["rows"]:
        for m in r["cond"].values():
            for k in [k for k in m if k.startswith("_")]:
                m.pop(k)
    res.pop("_refs", None)
    return res


def _by(rows):
    return {r["id"]: r for r in rows if "error" not in r}


def windows_share(px, fx, div, e: E5, plan: str = "P150", starts=(2004, 2006, 2008, 2010), years: int = 8, cut: float = 0.0) -> dict:
    """시작 연도를 바꾼 8년 구간에서 구조 몫 > 0인 수."""
    pos = 0
    for y in starts:
        s, t = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + years - 1}-12-31")
        _, a = run_sim(px, fx, e.make, plan, 1.0, s, t, div, cut)
        _, b = run_sim(px, fx, b00, plan, 1.0, s, t, div, cut)
        pos += int(irr(a.flows, float(a.liq.iloc[-1])) > irr(b.flows, float(b.liq.iloc[-1])))
    return {"positive": pos, "n": len(starts)}


def eligibility5(res: dict, px, fx, div, tracking_ok: bool) -> dict:
    by = _by(res["rows"])
    out: dict[str, tuple[bool, str]] = {}
    # 1. H 기능
    if "R5_H1" in by and "BIV" in by:
        h, bv = by["R5_H1"]["cond"], by["BIV"]["cond"]
        th = {"P50": 0.002, "P150": 0.0008, "L1천만": 0.003, "L1억": 0.0}
        why = ""
        for plan in PLAN_IDS:
            for k in COSTS:
                c = ck(plan, k)
                if not (h[c]["irr"] > bv[c]["irr"] and h[c]["irr"] > h[c]["ref_irr"]):
                    why = f"{c}에서 BIV·B00보다 높지 않음"
                    break
                if k == 1.0 and not h[c]["irr"] - bv[c]["irr"] > th[plan] - 1e-12:
                    why = f"{plan} 이득 {(h[c]['irr'] - bv[c]['irr']) * 100:+.2f}%p < 문턱 {th[plan] * 100:.2f}%p"
                    break
            if why:
                break
        out["R5_H1"] = (not why, why)
    # 2. A 수익형(A1·A2·A4)
    cache_cut, cache_win = {}, {}
    for i in ("R5_A1", "R5_A2", "R5_A4"):
        if i not in by:
            continue
        if not tracking_ok:
            out[i] = (False, "합성 시세 검산 '확인 못 함' — I·A·P는 안 올림")
            continue
        c = by[i]["cond"]
        e = next(x for x in ROUND5 if x.id == i)
        why = ""
        if not all(c[ck(p, 1.0)]["struct_share"] >= 0.001 for p in ("P50", "P150", "L1억")):
            why = "(가) 어느 일정에서 S&P보다 +0.10%p 미만"
        elif not all(c[ck(p, 2.0)]["struct_share"] > 0 for p in ("P50", "P150", "L1억")):
            why = "(가) 비용 2배에서 ≤ 0"
        else:
            _, a = run_sim(px, fx, e.make, "P150", 1.0, *DEFAULT_SPLITS.period("dev"), div, 0.003)
            _, b = run_sim(px, fx, b00, "P150", 1.0, *DEFAULT_SPLITS.period("dev"), div, 0.003)
            cache_cut[i] = irr(a.flows, float(a.liq.iloc[-1])) - irr(b.flows, float(b.liq.iloc[-1]))
            if not cache_cut[i] > 0:
                why = f"(나) 합성 0.3%p 더 깎으면 P150 {cache_cut[i] * 100:+.2f}%p"
            else:
                cache_win[i] = windows_share(px, fx, div, e)
                if cache_win[i]["positive"] < 3:
                    why = f"(다) 8년 구간 4개 중 {cache_win[i]['positive']}개만 > 0"
        out[i] = (not why, why)
    # 3. A 방어형(A3·A5)
    for i in ("R5_A3", "R5_A5"):
        if i not in by:
            continue
        if not tracking_ok:
            out[i] = (False, "합성 시세 검산 '확인 못 함' — I·A·P는 안 올림")
            continue
        c = by[i]["cond"]
        e = next(x for x in ROUND5 if x.id == i)
        dec = c[ck("P150", 1.0)]["declines"]
        n_ok = sum(1 for v in dec.values() if v["both_095"])
        why = ""
        if not all(c[ck(p, 1.0)]["struct_share"] >= 0 for p in ("P150", "L1억")) or not c[ck("P150", 2.0)]["struct_share"] >= -0.001:
            why = "(가) P150·L1억에서 S&P 미만 또는 비용 2배 −0.1%p 넘게 뒤짐"
        elif n_ok < 3:
            why = f"(나) 하락 4번 중 원화·달러 모두 0.95배 이하가 {n_ok}번"
        elif not c[ck("P150", 1.0)]["mdd_usd"] >= c[ck("P150", 1.0)]["ref_mdd_usd"] + 0.01:
            why = "(다) 달러 기준 최악 손실이 1%p 이상 작지 않음"
        else:
            _, a = run_sim(px, fx, e.make, "P150", 1.0, *DEFAULT_SPLITS.period("dev"), div, 0.003)
            _, b = run_sim(px, fx, b00, "P150", 1.0, *DEFAULT_SPLITS.period("dev"), div, 0.003)
            cut = irr(a.flows, float(a.liq.iloc[-1])) - irr(b.flows, float(b.liq.iloc[-1]))
            w = windows_share(px, fx, div, e)
            if not cut > 0:
                why = f"(라) 합성 0.3%p 더 깎으면 P150 {cut * 100:+.2f}%p"
            elif w["positive"] < 3:
                why = f"(라) 8년 구간 4개 중 {w['positive']}개만 > 0"
        out[i] = (not why, why)
    for i in ("R5_I1", "R5_I2", "R5_I3", "R5_P1"):
        if i in by:
            out[i] = (False, "올리지 않음(계획: I·P는 보고)")
    ok = lambda i: out.get(i, (False,))[0]  # noqa: E731
    irr_of = lambda i: by[i]["cond"][ck("P150", 1.0)]["irr"]  # noqa: E731
    promoted = []
    if ok("R5_H1"):
        promoted.append("R5_H1")
    inc = sorted([i for i in ("R5_A1", "R5_A2", "R5_A4") if ok(i)], key=lambda i: -irr_of(i))
    if inc:
        promoted.append(inc[0])
    de = sorted([i for i in ("R5_A3", "R5_A5") if ok(i)], key=lambda i: -irr_of(i))
    if de:
        promoted.append(de[0])
    return {"by_id": {i: {"eligible": a, "why": w} for i, (a, w) in out.items()}, "promoted": promoted[:3],
            "haircut_p150": cache_cut, "windows": cache_win}


def pass_table5(res: dict, px, fx, div) -> dict:
    by = _by(res["rows"])
    out = {}
    for i, r in by.items():
        if r["benchmark"] or r["group"] in ("I", "P"):
            continue
        c = r["cond"]
        checks = []
        if i == "R5_H1":
            bv = by["BIV"]["cond"]
            ok1 = all(c[ck(p, k)]["irr"] > bv[ck(p, k)]["irr"] for p in PLAN_IDS for k in COSTS)
            d50, dl = c[ck("P50", 1.0)]["irr"] - bv[ck("P50", 1.0)]["irr"], c[ck("L1천만", 1.0)]["irr"] - bv[ck("L1천만", 1.0)]["irr"]
            checks += [("네 일정·비용 1·2배 모두 BIV보다 높음", ok1, ""), ("P50·L1천만 +0.15%p 이상", d50 >= 0.0015 and dl >= 0.0015,
                                                                   f"{d50 * 100:+.2f} / {dl * 100:+.2f}%p"),
                       ("사람 세법 확인 뒤 실계좌 기능", None, "사람")]
        elif i in ("R5_A1", "R5_A2", "R5_A4"):
            e = next(x for x in ROUND5 if x.id == i)
            s, t = DEFAULT_SPLITS.period("valid")
            _, a = run_sim(px, fx, e.make, "P150", 1.0, s, t or px.index[-1], div, 0.003)
            _, b = run_sim(px, fx, b00, "P150", 1.0, s, t or px.index[-1], div, 0.003)
            cut = irr(a.flows, float(a.liq.iloc[-1])) - irr(b.flows, float(b.liq.iloc[-1]))
            checks += [("P50·P150·L1억 +0.10%p 이상", all(c[ck(p, 1.0)]["struct_share"] >= 0.001 for p in ("P50", "P150", "L1억")), ""),
                       ("비용 2배 > 0", all(c[ck(p, 2.0)]["struct_share"] > 0 for p in ("P50", "P150", "L1억")), ""),
                       ("합성 0.3%p 더 깎아도 P150 > 0", cut > 0, f"{cut * 100:+.2f}%p"),
                       ("최악 손실(원화·달러)이 S&P보다 1%p 넘게 나쁘지 않음",
                        all(c[ck(p, 1.0)]["mdd_krw"] >= c[ck(p, 1.0)]["ref_mdd_krw"] - 0.01 and c[ck(p, 1.0)]["mdd_usd"] >= c[ck(p, 1.0)]["ref_mdd_usd"] - 0.01
                            for p in ("P50", "P150", "L1억")), "")]
        elif i in ("R5_A3", "R5_A5"):
            dec = c[ck("P150", 1.0)]["declines"]
            n_ok = sum(1 for v in dec.values() if v["both_095"])
            m = c[ck("P150", 1.0)]
            checks += [("P150·L1억 S&P −0.1%p 이내 이상", all(c[ck(p, 1.0)]["struct_share"] >= -0.001 for p in ("P150", "L1억")), ""),
                       ("세 하락 중 2번 이상 원화·달러 0.95배 이하", n_ok >= 2, f"{n_ok}/3"),
                       ("달러 기준 최악 손실 1%p 이상 작음", m["mdd_usd"] >= m["ref_mdd_usd"] + 0.01,
                        f"{m['mdd_usd'] * 100:.0f}% vs {m['ref_mdd_usd'] * 100:.0f}%")]
            pair = "R5_A1" if i == "R5_A3" else "R5_A2"
            if pair in by:
                checks.append(("채권 10%의 값(같은 구조 100% 주식형과 차이)", None,
                               f"{(m['irr'] - by[pair]['cond'][ck('P150', 1.0)]['irr']) * 100:+.2f}%p"))
        hard = [x for x in checks if x[1] is not None]
        out[i] = {"checks": checks, "pass": bool(hard) and all(x[1] for x in hard)}
    return out


def table5(res: dict, period: str, plan: int, elig: dict | None, passes: dict | None, extra: dict) -> str:
    p = lambda v, d=2: "—" if v is None or v != v else f"{v * 100:+.{d}f}%"  # noqa: E731
    out = [f"### 실험실 5차 · Fable 설계 #{plan} · {period} · 5차 엔진(배당 원가 반영) · 세후 내부수익률(다 팔고 세금 낸 뒤)", "",
           "| 실험 | 묶음 | 기준 일정 | 세후 연수익 | S&P(같은 일정) | 구조 몫 | 최악 원화/달러 | S&P 원화/달러 | 일정별 구조 몫(비용 1배) | 자격 |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        if "error" in r:
            out.append(f"| {r['id']} | {r['group']} | 실패: {r['error'][:80]} |" + " |" * 7)
            continue
        b = r["cond"].get(r["base"]) or next(iter(r["cond"].values()))
        per = " / ".join(f"{pl} {p(r['cond'][ck(pl, 1.0)].get('struct_share'))}" for pl in PLAN_IDS if ck(pl, 1.0) in r["cond"])
        e = (elig or {}).get("by_id", {}).get(r["id"])
        tag = "기준선" if r["benchmark"] else ("—" if e is None else "✅ 올림" if r["id"] in elig["promoted"] else "자격" if e["eligible"] else f"✗ {e['why']}")
        out.append(f"| {r['id']} | {r['group']} | {r['base'].split('_x')[0]} | {p(b['irr'])} | {p(b.get('ref_irr'))} | {p(b.get('struct_share'))} | "
                   f"{p(b['mdd_krw'], 0)} / {p(b['mdd_usd'], 0)} | {p(b.get('ref_mdd_krw'), 0)} / {p(b.get('ref_mdd_usd'), 0)} | {per} | {tag} |")
    out += ["", "세법 숫자(22%·250만, ISA 연 2천만·총 1억·200만 뒤 9.9%, 15.4%, 연금 16.5%·5.5%·13.2%)는 **사람 확인 필요**. "
            "구조 몫은 '세금 구조 덕'이지 맞히는 실력이 아니다. 국내 ETF는 합성(KSPX_N = 미국 배당세 15% 뗀 환노출)."]
    if elig is not None:
        out += ["", f"검증으로 올림(계획 규칙대로 자동): {', '.join(elig['promoted']) or '없음 → 검증 안 돌리고 라운드 종료'}"]
    if passes:
        out += ["", "#### 통과 기준(검증)"]
        for i, v in passes.items():
            out.append(f"- **{i}**: {'통과' if v['pass'] else '탈락'} — " + " · ".join(
                f"{n} {'○' if ok else '✗' if ok is False else '·'} {d}".strip() for n, ok, d in v["checks"]))
    for k, v in extra.items():
        out += ["", f"#### {k}", "```", str(v), "```"]
    return "\n".join(out)
