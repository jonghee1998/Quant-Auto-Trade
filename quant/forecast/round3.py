"""실험실 3차(Fable 설계 #66) 실행 본체: 모든 지표를 '청산 기준 평가액'(그날 다 팔고 세금까지 낸 뒤 남는 돈)으로 잰다.

- 네 조건(1억·1천만 × 비용 1·2배), 기준 조건 1억·1배.
- 베타 보정 알파: 일별 (전략 − SHY) = α + β(S&P − SHY) + 잔차, Newey-West t. DSR은 알파 수익 기준, 시도 간 분산은 묶음을 다 돌린 뒤.
- 검증 자격·올리기·통과 기준은 계획 숫자 그대로(eligibility3, pass_table3).
DB 없이 돌 수 있게 가격·환율·지표만 받는다.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from quant.lab.backtest import Costs, run_backtest
from quant.lab.metrics import (alpha_sharpe, beta_adjusted_alpha, cagr, deflated_sharpe_alpha, drawdown_in, max_drawdown,
                               summary)
from quant.lab.splits import CRASH_2008, DEFAULT_SPLITS, VALID_DRAWDOWNS
from quant.lab.strategy import BuyAndHold

from .experiments import PREV_TRIALS, ROUND3, Exp

CONDITIONS = [(100_000_000.0, 1.0), (10_000_000.0, 1.0), (100_000_000.0, 2.0), (10_000_000.0, 2.0)]
BASE = CONDITIONS[0]
DEFENSE = ("D", "G", "V", "M", "C")


def ck(c) -> str:
    return f"{int(c[0] / 1e6)}M_x{c[1]:g}"


def safe_krw(prices: pd.DataFrame, fx: pd.Series, idx: pd.DatetimeIndex) -> pd.Series:
    """단기채(SHY) 원화 가치(알파 회귀의 무위험 쪽)."""
    f = fx.reindex(prices.index).ffill()
    return (prices["SHY"] * f).reindex(idx)


def score(m: dict) -> float:
    """(청산 기준 연수익 − S&P) + 0.5 × (S&P 최악 손실 − 전략 최악 손실)."""
    return float((m["liq_cagr"] - m["bench_liq_cagr"]) + 0.5 * (m["mdd"] - m["bench_mdd"]))


def year_end(liq: pd.Series) -> dict[str, float]:
    return {str(y): float(v) for y, v in liq.groupby(liq.index.year).last().items()}


def measure(res, bench, safe: pd.Series) -> dict:
    """한 결과(전략·S&P 둘 다 청산 기준 평가액)의 지표."""
    s, b = res.liq_nav, bench.liq_nav
    m = summary(s, b)  # 연수익·최악 손실·오른/내린 달 등(청산 기준으로)
    m["liq_cagr"], m["bench_liq_cagr"] = cagr(s), cagr(b)
    m["mdd"], m["bench_mdd"] = max_drawdown(s), max_drawdown(b)
    a = beta_adjusted_alpha(s, b, safe.reindex(s.index))
    m["alpha"], m["beta"], m["alpha_t"] = a["alpha"], a["beta"], a["t"]
    m["alpha_sharpe_daily"] = alpha_sharpe(a["resid"])
    m["trades"] = len(res.trades)
    m["taxes_paid"] = float(sum(res.taxes.values()))
    m["score"] = score(m)
    m["_resid"] = a["resid"]
    return m


def run_batch3(prices, fx, exps: list[Exp], benches: list[Exp], mf, *, period: str = "dev", div_yield=None,
               conditions=CONDITIONS, n_trials: int | None = None, start=None, end=None, log=print) -> dict:
    s0, e0 = DEFAULT_SPLITS.period(period)
    start, end = start or s0, end if end is not None else e0
    idx = prices.index[(prices.index >= pd.Timestamp(start)) & ((prices.index <= pd.Timestamp(end)) if end is not None else True)]
    safe = safe_krw(prices, fx, idx)
    spy = {c: run_backtest(prices, fx, BuyAndHold("SPY"), start, end, capital_krw=c[0], rebalance="M", costs=Costs().scaled(c[1]),
                           div_yield=div_yield) for c in conditions}
    rows, daily = [], {}
    for e in exps + benches:
        t0 = time.time()
        row = {"id": e.id, "group": e.group, "hypothesis": e.hypothesis, "rebalance": e.rebalance, "benchmark": e in benches, "cond": {}}
        try:
            for c in conditions:
                strat = e.build(prices, mf)
                res = run_backtest(prices, fx, strat, start, end, capital_krw=c[0], rebalance=e.rebalance, costs=Costs().scaled(c[1]),
                                   div_yield=div_yield)
                m = measure(res, spy[c], safe)
                if c == conditions[0]:
                    m["crash_2008"] = drawdown_in(res.liq_nav, *CRASH_2008)
                    m["bench_crash_2008"] = drawdown_in(spy[c].liq_nav, *CRASH_2008)
                    m["year_end"], m["bench_year_end"] = year_end(res.liq_nav), year_end(spy[c].liq_nav)
                    m["avoid_count"] = getattr(strat, "avoid_count", getattr(getattr(strat, "base", None), "avoid_count", None))
                    m["harvests"] = len(getattr(strat, "harvests", []) or [])
                    if period == "valid":
                        m["valid_drawdowns"] = {k: {"s": drawdown_in(res.liq_nav, *v), "spy": drawdown_in(spy[c].liq_nav, *v)}
                                                for k, v in VALID_DRAWDOWNS.items()}
                    w = res.weights
                    eq = sum((w[col] for col in w.columns if col not in ("SHY", "TLT", "GLD")), pd.Series(0.0, index=w.index)) \
                        if w is not None and not w.empty else None
                    daily[e.id] = pd.DataFrame({"liq_nav": res.liq_nav, "spy_liq_nav": spy[c].liq_nav, "nav": res.nav, "equity": eq})
                row["cond"][ck(c)] = m
            b = row["cond"][ck(conditions[0])]
            log(f"{e.id}: 청산 기준 {b['liq_cagr'] * 100:+.2f}% (S&P {b['bench_liq_cagr'] * 100:+.2f}%), 최악 {b['mdd'] * 100:.0f}% "
                f"(S&P {b['bench_mdd'] * 100:.0f}%), 알파 {b['alpha'] * 100:+.2f}% (t {b['alpha_t']:.1f}), 점수 {b['score'] * 100:+.2f} "
                f"({time.time() - t0:.0f}초)")
        except Exception as ex:  # noqa: BLE001
            row["error"] = f"{type(ex).__name__}: {ex}"
            log(f"{e.id}: 실패 {row['error']}")
        rows.append(row)
    trials = [r for r in rows if not r["benchmark"] and "error" not in r]
    srs = [r["cond"][ck(conditions[0])]["alpha_sharpe_daily"] for r in trials]
    srs = [x for x in srs if x == x]
    var = float(np.var(srs, ddof=1)) if len(srs) >= 2 else None
    n = n_trials if n_trials is not None else PREV_TRIALS + len(ROUND3)
    for r in trials:
        b = r["cond"][ck(conditions[0])]
        b["dsr_alpha"], b["n_trials"] = deflated_sharpe_alpha(b["_resid"], n, var), n
    for r in rows:
        for m in r["cond"].values():
            m.pop("_resid", None)
    return {"rows": rows, "n_trials": n, "trial_var": var, "daily": daily}


def _by(rows):
    return {r["id"]: r for r in rows if "error" not in r}


def eligibility3(rows: list[dict]) -> dict:
    """계획 #66 '검증으로 올리는 규칙'."""
    by = _by(rows)
    base, x2 = ck(BASE), ck((BASE[0], 2.0))
    out: dict[str, tuple[bool, str]] = {}
    m_ = lambda i, k=base: by[i]["cond"][k]  # noqa: E731

    if "H01" in by:
        why = ""
        for c in CONDITIONS:
            k = ck(c)
            h = m_("H01", k)
            if not (h["liq_cagr"] > h["bench_liq_cagr"] and "BIV" in by and h["liq_cagr"] > m_("BIV", k)["liq_cagr"]):
                why = f"{k}에서 SPY·IVV 보유보다 높지 않음"
                break
        h = m_("H01")
        if not why and not (h["liq_cagr"] - h["bench_liq_cagr"] >= 0.001 and h["liq_cagr"] - m_("BIV")["liq_cagr"] >= 0.001):
            why = "1억·1배 차이 < 0.1%p"
        if not why and h["mdd"] < h["bench_mdd"] - 0.005:
            why = "최악 손실이 S&P보다 0.5%p 넘게 나쁨"
        out["H01"] = (not why, why)
    for i, r in by.items():
        if r["benchmark"] or r["group"] not in DEFENSE:
            continue
        m, m2 = m_(i), m_(i, x2)
        why = ""
        if not (m["alpha"] > 0 and m2["alpha"] > 0):
            why = "베타 보정 알파 ≤ 0(비용 1배 또는 2배)"
        elif not m["mdd"] >= 0.85 * m["bench_mdd"]:
            why = "최악 손실 > S&P × 0.85"
        elif not m["liq_cagr"] >= m["bench_liq_cagr"] - 0.005:
            why = "청산 기준 연수익 < S&P − 0.5%p"
        elif not m["crash_2008"] > m["bench_crash_2008"]:
            why = "2008 하락에서 S&P보다 덜 빠지지 않음"
        elif i == "M01" and not ("B80" in by and m["liq_cagr"] > m_("B80")["liq_cagr"] and m["mdd"] > m_("B80")["mdd"]):
            why = "B80보다 연수익·최악 손실이 둘 다 낫지 않음"
        elif r["group"] == "G" and not (m.get("avoid_count") or 0) >= 1:
            why = "피함 진입이 한 번도 없음"
        out[i] = (not why, why)
    ok = lambda i: out.get(i, (False,))[0]  # noqa: E731
    if "C01" in out and ok("C01") and not (ok("D01") and ok("H01")):
        out["C01"] = (False, "D01·H01 둘 다 자격이 있어야 함")
    if "C02" in out and ok("C02") and not (ok("G02") and ok("H01")):
        out["C02"] = (False, "G02·H01 둘 다 자격이 있어야 함")
    sc = lambda i: m_(i)["score"]  # noqa: E731
    promoted = []
    if ok("H01"):
        promoted.append("H01")
    fam = lambda i: "D" if i.startswith("D") else by[i]["group"]  # noqa: E731
    defense = sorted([i for i in out if ok(i) and by[i]["group"] in ("D", "G", "V", "M")], key=lambda i: -sc(i))
    if defense:
        top = defense[0]
        promoted.append(top)
        pair = {"D01": "C01", "G02": "C02"}.get(top)
        if pair and ok(pair):
            promoted.append(pair)
        else:
            rest = [i for i in sorted([i for i in out if ok(i) and i not in promoted and i != "H01"], key=lambda i: -sc(i))
                    if fam(i) != fam(top)]
            if rest:
                promoted.append(rest[0])
    return {"by_id": {i: {"eligible": a, "why": w} for i, (a, w) in out.items()}, "promoted": promoted[:3]}


def pass_table3(rows: list[dict], combined_t: dict[str, float] | None = None) -> dict:
    """계획 #66 통과 기준(검증 구간 결과 rows). 항목별 (통과, 설명). DSR은 보고만."""
    by = _by(rows)
    base, x2 = ck(BASE), ck((BASE[0], 2.0))
    out = {}
    for i, r in by.items():
        if r["benchmark"]:
            continue
        m = r["cond"][base]
        checks: list[tuple[str, bool | None, str]] = []
        if i == "H01":
            c1 = all(r["cond"][ck(c)]["liq_cagr"] > r["cond"][ck(c)]["bench_liq_cagr"] and "BIV" in by
                     and r["cond"][ck(c)]["liq_cagr"] > by["BIV"]["cond"][ck(c)]["liq_cagr"] for c in CONDITIONS)
            checks.append(("1 네 조건 모두 SPY·IVV보다 높음", c1, ""))
            d = m["liq_cagr"] - m["bench_liq_cagr"]
            checks.append(("2 차이 ≥ 0.1%p, 손실 0.5%p 이내", d >= 0.001 and m["mdd"] >= m["bench_mdd"] - 0.005, f"{d * 100:+.2f}%p"))
            ye, bye = m["year_end"], m["bench_year_end"]
            wins = sum(1 for y in ye if y in bye and ye[y] > bye[y])
            checks.append(("3 5년 중 4년 이상 연말에 앞섬", wins >= 4, f"{wins}/{len(ye)}"))
            checks.append(("4 사람 확인(원가 방식·결제일·공제)", None, "사람"))
        else:
            need = 0.0 if r["group"] == "C" else -0.003
            checks.append(("1 청산 기준 연수익", m["liq_cagr"] - m["bench_liq_cagr"] >= need, f"{(m['liq_cagr'] - m['bench_liq_cagr']) * 100:+.2f}%p"))
            checks.append(("2 최악 손실 ≤ S&P×0.85", m["mdd"] >= 0.85 * m["bench_mdd"], f"{m['mdd'] * 100:.0f}% vs {m['bench_mdd'] * 100:.0f}%"))
            vd = m.get("valid_drawdowns") or {}
            less = sum(1 for v in vd.values() if v["s"] > v["spy"])
            checks.append(("3 세 하락 중 2번 이상 덜 빠짐", less >= 2, f"{less}/3"))
            checks.append(("4 내린 달 < 0.9, 오른 달 ≥ 0.9", m["down_capture"] < 0.9 and m["up_capture"] >= 0.9,
                           f"{m['up_capture']:.2f}/{m['down_capture']:.2f}"))
            ct = (combined_t or {}).get(i)
            checks.append(("5 알파 > 0(1·2배), 검증 t ≥ 1, 19년 t ≥ 2",
                           m["alpha"] > 0 and r["cond"][x2]["alpha"] > 0 and m["alpha_t"] >= 1.0 and ct is not None and ct >= 2.0,
                           f"t {m['alpha_t']:.1f} / 19년 t {ct if ct is None else round(ct, 1)}"))
            sm = [r["cond"][ck(c)] for c in CONDITIONS if c[0] == 10_000_000.0 and c[1] == 1.0][0]
            checks.append(("6 1천만에서도 1~2번", sm["liq_cagr"] - sm["bench_liq_cagr"] >= need and sm["mdd"] >= 0.85 * sm["bench_mdd"], ""))
            checks.append(("7 DSR(보고)", None, f"{m.get('dsr_alpha', float('nan')):.2f}" + (" 강한 통과" if (m.get("dsr_alpha") or 0) >= 0.95 else "")))
        hard = [c for c in checks if c[1] is not None]
        out[i] = {"checks": checks, "pass": all(c[1] for c in hard)}
    return out


def table3(res: dict, period: str, plan: int, elig: dict | None, passes: dict | None = None) -> str:
    p = lambda v, d=1: "—" if v is None or v != v else f"{v * 100:+.{d}f}%"  # noqa: E731
    x = lambda v, d=2: "—" if v is None or v != v else f"{v:.{d}f}"  # noqa: E731
    base = ck(BASE)
    keys = [ck(c) for c in CONDITIONS]
    out = [f"### 실험실 3차 · Fable 설계 #{plan} · {period} · 1억·비용 1배 · 모두 청산 기준(그날 다 팔고 세금 낸 뒤)", "",
           "| 실험 | 묶음 | 연수익 | S&P | 최악 손실 | S&P | 2008 하락 | S&P | 알파(연) | β | t | DSR | 매매 | 점수(1억·1 / 1천만·1 / 1억·2 / 1천만·2) | 자격 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    rows = sorted(res["rows"], key=lambda r: (r["benchmark"], -(r.get("cond", {}).get(base, {}).get("score", -9))))
    for r in rows:
        if "error" in r:
            out.append(f"| {r['id']} | {r['group']} | 실패: {r['error'][:80]} |" + " |" * 12)
            continue
        m = r["cond"][base]
        e = (elig or {}).get("by_id", {}).get(r["id"])
        tag = "기준선" if r["benchmark"] else ("—" if e is None else "✅ 올림" if r["id"] in elig["promoted"] else "자격" if e["eligible"] else f"✗ {e['why']}")
        out.append(f"| {r['id']} | {r['group']} | {p(m['liq_cagr'], 2)} | {p(m['bench_liq_cagr'], 2)} | {p(m['mdd'], 0)} | {p(m['bench_mdd'], 0)} | "
                   f"{p(m.get('crash_2008'), 0)} | {p(m.get('bench_crash_2008'), 0)} | {p(m['alpha'], 2)} | {x(m['beta'])} | {x(m['alpha_t'], 1)} | "
                   f"{x(m.get('dsr_alpha'))} | {m['trades']} | {' / '.join(f'{r['cond'][k]['score'] * 100:+.2f}' for k in keys)} | {tag} |")
    out += ["", f"시도 수 {res['n_trials']}. 알파 = 일별 (전략 − 단기채)를 (S&P − 단기채)에 맞춘 절편(연), t는 Newey-West. "
            "해가 바뀌면 공제가 새로 생겨 청산 기준 평가액이 하루에 뛴다(버그 아님 — 절세 매도의 이득이 여기서 드러난다)."]
    if elig is not None:
        out += ["", f"검증으로 올림(계획 규칙대로 자동): {', '.join(elig['promoted']) or '없음 → 검증 안 돌리고 라운드 종료'}"]
    if passes:
        out += ["", "#### 통과 기준(검증)"]
        for i, v in passes.items():
            out.append(f"- **{i}**: {'통과' if v['pass'] else '탈락'} — " + " · ".join(
                f"{n} {'○' if ok else '✗' if ok is False else '·'} {d}".strip() for n, ok, d in v["checks"]))
    return "\n".join(out)
