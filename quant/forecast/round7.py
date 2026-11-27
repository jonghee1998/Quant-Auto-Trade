"""실험실 7차(Fable 설계 #93) 실행 본체: 여러 자산 ETF 분산 추세추종(M), S&P 60 + 방어 추세(E), 수익 겹치기(X), 긴 과거 관문(G0).

판정은 1억·비용 1배, 청산 기준 평가액(그날 다 팔고 세금 낸 뒤)·원화. 자격·올리기·통과 숫자는 계획 그대로(eligibility7·pass_table7).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant.lab.backtest import Costs, run_backtest
from quant.lab.metrics import (alpha_sharpe, beta_adjusted_alpha, cagr, cagr_excluding, deflated_sharpe_alpha, drawdown_in, max_drawdown,
                               summary)
from quant.lab.splits import DEFAULT_SPLITS, VALID_DRAWDOWNS
from quant.lab.strategy import BuyAndHold

from .round3 import safe_krw, score
from .round6 import episodes
from .rules7 import ASSETS8, DEFENSIVE4, Stacked, TrendSlots
from .synthetic import leveraged2x

PREV_TRIALS7 = 82                       # 6차까지 누적 서로 다른 시도 → 7차 시도 수 = max(DB, 82 + 10 = 92)
CONDITIONS = [(100_000_000.0, 1.0), (10_000_000.0, 1.0), (100_000_000.0, 2.0), (10_000_000.0, 2.0)]
BASE = CONDITIONS[0]
WINDOWS7 = ((2004, 2010), (2006, 2012), (2008, 2014), (2010, 2016), (2011, 2017))
NO_2008 = ((2010, 2016), (2011, 2017))
EXCL = ("2008-01-01", "2009-06-30")
GATE_PERIOD = ("1987-07-01", "2003-12-31")
PROXY = {"SPY": "VFINX", "EFA": "VWIGX", "EEM": "VEIEX", "VNQ": "FRESX", "IEF": "VFITX", "TLT": "VUSTX"}   # 금·원자재는 무료 긴 과거 없음
NOTE = "세법 숫자(22%·250만·배당 15%)·DBC 실거래 대체(PDBC)·SSO 거래 요건은 사람 확인 필요"


def ck(c) -> str:
    return f"{int(c[0] / 1e6)}M_x{c[1]:g}"


@dataclass(frozen=True)
class E7:
    id: str
    group: str                   # M / E / X / 기준선
    hypothesis: str
    make: object                 # () → 전략
    static: str | None = None    # 같은 틀의 정적 기준선(추세의 몫)
    plus: str | None = None      # E·X: 이 기준선보다 +0.3%p 이상
    promote: bool = True         # 확인용(M4·X4)은 올리지 않는다
    krw: frozenset = frozenset()


def _m(i, **kw):
    return lambda: TrendSlots(i, ASSETS8, **kw)


def _s(i, fixed, **kw):
    return lambda: Stacked(i, fixed, DEFENSIVE4, **kw)


ROUND7: list[E7] = [
    E7("R7_M1", "M", "8자산 분산 추세는 세후·원화 연수익이 S&P −0.5%p 이상이면서 최악 손실이 원화 3%p·달러 5%p 이상 얕다", _m("R7_M1"), "BM0"),
    E7("R7_M2", "M", "신호를 12개월 하나로 바꿔도 M1과 같은 방향이다", _m("R7_M2", signal="y12"), "BM0"),
    E7("R7_M3", "M", "칸을 변동성 반비례로 나누면 M1보다 최악 손실이 얕고 수익은 낮지 않다", _m("R7_M3", inv_vol=True), "BM0"),
    E7("R7_M4", "M", "대피처가 달러(SHY)인 M1이 원화 현금인 쪽보다 원화 최악 손실이 2%p 이상 얕다", _m("R7_M4", shelter="KRWCASH"), "BM0",
       promote=False, krw=frozenset({"KRWCASH"})),
    E7("R7_E1", "E", "S&P 60%는 늘 들고 40%만 방어 4자산 추세로 굴리면 S&P 60 + SHY 40보다 +0.3%p 이상 벌고 S&P보다 덜 잃는다",
       _s("R7_E1", {"SPY": 0.6}), "BE0", "B60"),
    E7("R7_X1", "X", "S&P 노출 100%(SSO 50%)에 방어 4자산 추세 50%를 얹으면 S&P보다 세후 수익이 높고 최악 손실도 얕다", _s("R7_X1", {"SSO": 0.5}), "BXS", "BX0"),
    E7("R7_X2", "X", "X1의 신호를 12개월 하나로 바꿔도 같은 방향이다", _s("R7_X2", {"SSO": 0.5}, signal="y12"), "BXS", "BX0"),
    E7("R7_X3", "X", "X1의 칸을 변동성 반비례로 나누면 최악 손실이 더 얕다", _s("R7_X3", {"SSO": 0.5}, inv_vol=True), "BXS", "BX0"),
    E7("R7_X4", "X", "얹는 양을 30%로 줄이면 효과도 그만큼 줄어든다", _s("R7_X4", {"SSO": 0.3, "SPY": 0.4}), "BXS", "BX0", promote=False),
]
BENCH7: list[E7] = [
    E7("B00", "기준선", "SPY 보유", lambda: BuyAndHold("SPY")),
    E7("BM0", "기준선", "8자산을 추세 없이 같은 칸으로 보유(같은 띠)", _m("BM0", signal="hold")),
    E7("B60", "기준선", "SPY 60 + SHY 40", lambda: TrendSlots("B60", (), share=0.4, fixed={"SPY": 0.6})),
    E7("BE0", "기준선", "SPY 60 + 방어 4자산 각 10% 보유", _s("BE0", {"SPY": 0.6}, signal="hold")),
    E7("BX0", "기준선", "SSO 50 + SHY 50(겹치기 비용만)", lambda: TrendSlots("BX0", (), share=0.5, fixed={"SSO": 0.5})),
    E7("BXS", "기준선", "SSO 50 + 방어 4자산 각 12.5% 보유", _s("BXS", {"SSO": 0.5}, signal="hold")),
]
NEIGHBORS = {"R7_M1": ("R7_M2", "R7_M3", "R7_M4"), "R7_M2": ("R7_M1", "R7_M3", "R7_M4"), "R7_M3": ("R7_M1", "R7_M2", "R7_M4"),
             "R7_M4": ("R7_M1", "R7_M2", "R7_M3"), "R7_E1": ("R7_M1", "R7_X1"), "R7_X1": ("R7_X2", "R7_X3", "R7_X4"),
             "R7_X2": ("R7_X1", "R7_X3", "R7_X4"), "R7_X3": ("R7_X1", "R7_X2", "R7_X4"), "R7_X4": ("R7_X1", "R7_X2", "R7_X3")}


def _usd(s: pd.Series, fx: pd.Series) -> pd.Series:
    return (s / fx.reindex(s.index).ffill()).dropna()


def _measure(res, bench, safe, fx) -> dict:
    s, b = res.liq_nav, bench.liq_nav
    m = summary(s, b)
    m["liq_cagr"], m["bench_liq_cagr"] = cagr(s), cagr(b)
    m["mdd"], m["bench_mdd"] = max_drawdown(s), max_drawdown(b)
    m["mdd_usd"], m["bench_mdd_usd"] = max_drawdown(_usd(s, fx)), max_drawdown(_usd(b, fx))
    a = beta_adjusted_alpha(s, b, safe.reindex(s.index))
    m["alpha"], m["beta"], m["alpha_t"] = a["alpha"], a["beta"], a["t"]
    m["alpha_sharpe_daily"] = alpha_sharpe(a["resid"])
    m["pretax_cagr"] = cagr(res.nav)
    m["trades"], m["taxes_paid"] = len(res.trades), float(sum(res.taxes.values()))
    m["score"] = score(m)
    m["_resid"], m["_liq"] = a["resid"], s
    return m


def run_batch7(prices, fx, exps: list[E7], benches: list[E7], *, period: str = "dev", div_yield=None, conditions=CONDITIONS,
               n_trials: int = PREV_TRIALS7 + 10, start=None, end=None, log=print) -> dict:
    s0, e0 = DEFAULT_SPLITS.period(period)
    start, end = start or s0, end if end is not None else e0
    idx = prices.index[(prices.index >= pd.Timestamp(start)) & (prices.index <= pd.Timestamp(end))]
    safe = safe_krw(prices, fx, idx)
    spy = {c: run_backtest(prices, fx, BuyAndHold("SPY"), start, end, capital_krw=c[0], rebalance="M", costs=Costs().scaled(c[1]),
                           div_yield=div_yield) for c in conditions}
    rows = []
    for e in benches + exps:
        t0 = time.time()
        row = {"id": e.id, "group": e.group, "hypothesis": e.hypothesis, "benchmark": e in benches, "static": e.static, "plus": e.plus,
               "promote": e.promote, "cond": {}}
        try:
            for c in conditions:
                res = run_backtest(prices, fx, e.make(), start, end, capital_krw=c[0], rebalance="M", costs=Costs().scaled(c[1]),
                                   div_yield=div_yield, krw_assets=e.krw)
                m = _measure(res, spy[c], safe, fx)
                if c == conditions[0]:
                    s, b = res.liq_nav, spy[c].liq_nav
                    m["windows7"] = {f"{a}-{z}": {"s": cagr(s.loc[f"{a}-01-01":f"{z}-12-31"]), "spy": cagr(b.loc[f"{a}-01-01":f"{z}-12-31"])}
                                     for a, z in WINDOWS7 if len(s.loc[f"{a}-01-01":f"{z}-12-31"]) > 250}
                    m["ex0809"], m["bench_ex0809"] = cagr_excluding(s, *EXCL), cagr_excluding(b, *EXCL)
                    if period == "valid":
                        su, bu = _usd(s, fx), _usd(b, fx)
                        m["valid_drawdowns"] = {k: {"krw": drawdown_in(s, *v), "spy_krw": drawdown_in(b, *v), "usd": drawdown_in(su, *v),
                                                    "spy_usd": drawdown_in(bu, *v)} for k, v in VALID_DRAWDOWNS.items()}
                row["cond"][ck(c)] = m
            b = row["cond"][ck(conditions[0])]
            log(f"{e.id}: 청산 기준 {b['liq_cagr'] * 100:+.2f}% (S&P {b['bench_liq_cagr'] * 100:+.2f}%), 최악 원화 {b['mdd'] * 100:.0f}%·달러 "
                f"{b['mdd_usd'] * 100:.0f}% (S&P {b['bench_mdd'] * 100:.0f}%·{b['bench_mdd_usd'] * 100:.0f}%), 매매 {b['trades']} ({time.time() - t0:.0f}초)")
        except Exception as ex:  # noqa: BLE001
            row["error"] = f"{type(ex).__name__}: {ex}"
            log(f"{e.id}: 실패 {row['error']}")
        rows.append(row)
    by = {r["id"]: r for r in rows if "error" not in r}
    base = ck(conditions[0])
    for r in rows:   # 같은 틀 정적 기준선에 회귀한 잔여 수익(추세의 몫)
        if "error" in r or r["benchmark"] or r["static"] not in by:
            continue
        a = beta_adjusted_alpha(r["cond"][base]["_liq"], by[r["static"]]["cond"][base]["_liq"], safe)
        r["cond"][base]["alpha_vs_static"], r["cond"][base]["alpha_vs_static_t"] = a["alpha"], a["t"]
    trials = [r for r in rows if not r["benchmark"] and "error" not in r]
    srs = [x for x in (r["cond"][base]["alpha_sharpe_daily"] for r in trials) if x == x]
    var = float(np.var(srs, ddof=1)) if len(srs) >= 2 else None
    for r in trials:
        b = r["cond"][base]
        b["dsr_alpha"], b["n_trials"] = deflated_sharpe_alpha(b["_resid"], n_trials, var), n_trials
    for r in rows:
        for m in r["cond"].values():
            m.pop("_resid", None)
            m.pop("_liq", None)
    return {"rows": rows, "n_trials": n_trials, "trial_var": var}


# ------------------------------------------------------------------ 긴 과거 관문(R7_G0)
def gate_frame(prices: pd.DataFrame, us3m: pd.Series) -> pd.DataFrame | None:
    """대역 펀드를 ETF 이름으로 바꾼 달러 시세판 + 3개월 국채 합성 현금(SHY 자리) + 합성 2배(SSO 자리). 금·원자재 칸은 없다."""
    if not all(v in prices.columns for v in ("VFINX", "VWIGX", "VUSTX")):
        return None
    out = pd.DataFrame({k: prices[v] for k, v in PROXY.items() if v in prices.columns})
    out = out[out["SPY"].notna()].ffill(limit=5)      # S&P 펀드가 값이 있는 날만, 하루 이틀 빈 값은 앞의 값으로(미래 값 안 씀)
    u = us3m.reindex(out.index).ffill()
    out["SHY"] = ((1 + u / 100 / 252).cumprod() * 100).where(u.notna())
    out["SSO"] = leveraged2x(out["SPY"], u)
    return out


def _less(rule: pd.Series, base: pd.Series, eps: list[tuple[str, str]], by: float) -> list[dict]:
    return [{"from": a, "to": z, "rule": drawdown_in(rule, a, z), "base": drawdown_in(base, a, z),
             "less": bool(drawdown_in(rule, a, z) > drawdown_in(base, a, z) + by)} for a, z in eps]


def gate7(prices: pd.DataFrame, us3m: pd.Series) -> dict:
    """G0-M: M1 규칙 vs 같은 칸 정적 보유. G0-X: X1 규칙 vs VFINX 보유. 달러·세금 0·편도 비용 0.08%, 1987-07~2003-12."""
    fail = {"M": {"status": "확인 못 함", "pass": False}, "X": {"status": "확인 못 함", "pass": False}}
    f = gate_frame(prices, us3m)
    if f is None:
        return {**fail, "why": "VFINX·VWIGX·VUSTX 중 없는 시세가 있다"}
    s, t = pd.Timestamp(GATE_PERIOD[0]), pd.Timestamp(GATE_PERIOD[1])
    firsts = {v: prices[v].first_valid_index() for v in ("VFINX", "VWIGX", "VUSTX")}
    if any(d is None or d > pd.Timestamp("1990-01-01") for d in firsts.values()):
        return {**fail, "why": f"긴 과거 시세가 1990년 이후에 시작: { {k: str(v)[:10] for k, v in firsts.items()} }"}
    f = f.loc[:t].dropna(how="all")
    win = f.loc[s:t]
    if len(win) < 2500 or win[["SPY", "SHY", "SSO"]].isna().any().any():
        return {**fail, "why": "관문 구간에 S&P 펀드·3개월 국채·합성 2배 값이 빠진 날이 있다"}
    ones = pd.Series(1.0, index=f.index)
    c = Costs(fee=0.0005, slippage=0.0003, fx_spread=0.0, tax_rate=0.0, dividend_tax=0.0)
    go = lambda strat: run_backtest(f, ones, strat, s, t, capital_krw=1e8, rebalance="M", costs=c).nav  # noqa: E731
    try:
        m1, bm = go(TrendSlots("G0_M1", ASSETS8)), go(TrendSlots("G0_BM0", ASSETS8, signal="hold"))
        x1, vf = go(Stacked("G0_X1", {"SSO": 0.5}, DEFENSIVE4)), go(BuyAndHold("SPY"))
    except Exception as ex:  # noqa: BLE001
        return {**fail, "why": f"계산 실패: {type(ex).__name__}: {ex}"[:160]}
    em = _less(m1, bm, episodes(bm, 0.10), 0.02)
    lm = sum(r["less"] for r in em)
    gm = {"status": "ok", "mdd": max_drawdown(m1), "base_mdd": max_drawdown(bm), "cagr": cagr(m1), "base_cagr": cagr(bm), "episodes": em, "less": lm,
          "n": len(em)}
    gm["c1"] = bool(gm["mdd"] >= 0.8 * gm["base_mdd"])                 # 최악 손실이 20% 이상 얕다
    gm["c2"] = bool(gm["cagr"] >= gm["base_cagr"] - 0.010)
    gm["c3"] = None if len(em) < 3 else bool(lm > len(em) / 2)         # 하락이 3번 이상일 때만 적용
    gm["pass"] = bool(gm["c1"] and gm["c2"] and gm["c3"] is not False)
    ex_ = _less(x1, vf, episodes(vf, 0.15), 0.01)
    lx = sum(r["less"] for r in ex_)
    gx = {"status": "ok", "cagr": cagr(x1), "base_cagr": cagr(vf), "mdd": max_drawdown(x1), "base_mdd": max_drawdown(vf), "episodes": ex_, "less": lx,
          "n": len(ex_)}
    gx["c1"] = bool(gx["cagr"] >= gx["base_cagr"] - 0.005)
    gx["c2"] = bool(ex_) and bool(lx > len(ex_) / 2)
    gx["c3"] = all(r["rule"] >= r["base"] - 0.03 for r in ex_)        # 어느 구간에서도 3%p 넘게 더 빠지지 않음
    gx["pass"] = bool(gx["c1"] and gx["c2"] and gx["c3"])
    return {"M": gm, "X": gx, "from": str(s.date()), "to": str(t.date()), "note": "금·원자재 칸은 긴 과거 자료가 없어 비움 — X의 관문은 사실상 채권 추세만 본다"}


# ------------------------------------------------------------------ 자격(개발)·통과(검증)
def _rule2(r: dict) -> bool:
    return all(r["cond"][k]["liq_cagr"] >= r["cond"][k]["bench_liq_cagr"] - 0.005 for k in (ck(BASE), ck((BASE[0], 2.0))))


def eligibility7(res: dict, gate: dict, sso_ok: bool) -> dict:
    by = {r["id"]: r for r in res["rows"] if "error" not in r}
    base, out = ck(BASE), {}
    for i, r in by.items():
        if r["benchmark"]:
            continue
        m, g = r["cond"][base], r["group"]
        st = by.get(r["static"], {}).get("cond", {}).get(base)
        pl = by.get(r["plus"], {}).get("cond", {}).get(base) if r["plus"] else None
        why = ""
        if not gate.get("X" if g == "X" else "M", {}).get("pass"):
            why = f"1 긴 과거 관문(G0-{'X' if g == 'X' else 'M'}) 통과 못 함"
        elif g == "X" and not sso_ok:
            why = "1 SSO 합성 검산 '확인 못 함'"
        elif not _rule2(r):
            why = "2 연수익 < S&P − 0.5%p(비용 1배 또는 2배)"
        elif not (m["mdd"] >= m["bench_mdd"] + 0.03 and m["mdd_usd"] >= m["bench_mdd_usd"] + 0.05):
            why = f"3 최악 손실이 원화 3%p·달러 5%p 이상 얕지 않음({(m['mdd'] - m['bench_mdd']) * 100:+.1f}·{(m['mdd_usd'] - m['bench_mdd_usd']) * 100:+.1f}%p)"
        else:
            w = m.get("windows7", {})
            ok = [k for k, v in w.items() if v["s"] >= v["spy"] - 0.010]
            if len(w) < len(WINDOWS7) or len(ok) < 3 or not any(f"{a}-{z}" in ok for a, z in NO_2008):
                why = f"4 7년 구간 {len(ok)}/{len(w)}개(2008년 없는 구간 포함 3개 이상이어야 함)"
            elif st is None or not (m["liq_cagr"] >= st["liq_cagr"] - 0.003 and m["mdd"] >= st["mdd"] + 0.02):
                why = f"5 추세의 몫: 정적 기준선({r['static']})보다 연수익 −0.3%p 이내·최악 손실 2%p 이상 얕음이 아님"
            elif r["plus"] and (pl is None or not m["liq_cagr"] >= pl["liq_cagr"] + 0.003):
                why = f"5 {r['plus']}보다 +0.3%p 이상이 아님"
            else:
                nb = [n for n in NEIGHBORS[i] if n in by]
                good = sum(_rule2(by[n]) for n in nb)
                need = 1 if g == "E" else 2
                if good < need:
                    why = f"6 이웃 {good}/{len(NEIGHBORS[i])}개만 2번 통과(필요 {need})"
        out[i] = (not why, why)
    best = {}
    for i, (ok, _) in out.items():
        r = by[i]
        if ok and r["promote"]:
            sc = r["cond"][base]["score"]
            if r["group"] not in best or sc > best[r["group"]][1]:
                best[r["group"]] = (i, sc)
    promoted = [i for i, _ in sorted(best.values(), key=lambda x: -x[1])][:2]
    return {"by_id": {i: {"eligible": a, "why": w} for i, (a, w) in out.items()}, "promoted": promoted}


def pass_table7(res: dict) -> dict:
    by = {r["id"]: r for r in res["rows"] if "error" not in r}
    base, x2, out = ck(BASE), ck((BASE[0], 2.0)), {}
    for i, r in by.items():
        if r["benchmark"]:
            continue
        m, m2 = r["cond"][base], r["cond"][x2]
        st = by.get(r["static"], {}).get("cond", {}).get(base)
        d = m["liq_cagr"] - m["bench_liq_cagr"]
        vd = m.get("valid_drawdowns") or {}
        less = sum(1 for v in vd.values() if v["krw"] >= v["spy_krw"] + 0.02 and v["usd"] >= v["spy_usd"] + 0.02)
        up, dn = m["up_capture"], m["down_capture"]
        checks = [
            ("1 연수익 ≥ S&P − 0.5%p(2배 −1.0%p)", bool(d >= -0.005 and m2["liq_cagr"] - m2["bench_liq_cagr"] >= -0.010), f"{d * 100:+.2f}%p"),
            ("2 최악 손실 원화 3%p·달러 5%p 이상 얕음", bool(m["mdd"] >= m["bench_mdd"] + 0.03 and m["mdd_usd"] >= m["bench_mdd_usd"] + 0.05),
             f"{(m['mdd'] - m['bench_mdd']) * 100:+.1f}·{(m['mdd_usd'] - m['bench_mdd_usd']) * 100:+.1f}%p"),
            ("3 세 하락 중 2번 이상 원화·달러 2%p 이상 덜 빠짐", less >= 2, f"{less}/{len(vd)}"),
            ("4 오른 달 ≥ 0.90·내린 달 ≤ 0.90·차이 ≥ 0.10", bool(up >= 0.90 and dn <= 0.90 and up - dn >= 0.10), f"{up:.2f}/{dn:.2f}"),
            ("5 정적 기준선보다 연수익 낮지 않고 최악 손실 얕음", bool(st is not None and m["liq_cagr"] >= st["liq_cagr"] and m["mdd"] > st["mdd"]),
             "" if st is None else f"{(m['liq_cagr'] - st['liq_cagr']) * 100:+.2f}%p·{(m['mdd'] - st['mdd']) * 100:+.1f}%p"),
            ("6 베타 보정 알파 > 0·DSR ≥ 0.95", bool(m["alpha"] > 0 and (m.get("dsr_alpha") or 0) >= 0.95),
             f"α {m['alpha'] * 100:+.2f}% · DSR {m.get('dsr_alpha', float('nan')):.2f}"),
        ]
        ok = [c[1] for c in checks]
        verdict = "후보(홀드아웃은 사람 승인 뒤 한 번)" if all(ok) else "보류(주문 없이 장부 기록)" if all(ok[:5]) else \
            "탈락 — 같은 틀은 다시 열지 않음" if not all(ok[:3]) else "미달(4·5번) — 후보·보류 아님"
        out[i] = {"checks": checks, "pass": all(ok), "verdict": verdict}
    return out


def strip(res: dict) -> dict:
    for r in res["rows"]:
        for m in r.get("cond", {}).values():
            for k in [k for k in m if k.startswith("_")]:
                m.pop(k)
    return res


def table7(res: dict, period: str, plan: int, elig: dict | None, passes: dict | None, extra: dict) -> str:
    p = lambda v, d=2: "—" if v is None or v != v else f"{v * 100:+.{d}f}%"  # noqa: E731
    x = lambda v, d=2: "—" if v is None or v != v else f"{v:.{d}f}"  # noqa: E731
    base, keys = ck(BASE), [ck(c) for c in CONDITIONS]
    out = [f"### 실험실 7차 · Fable 설계 #{plan} · {period} · 1억·비용 1배 · 청산 기준(그날 다 팔고 세금 낸 뒤)·원화 · {NOTE}", "",
           "| 실험 | 묶음 | 연수익 | S&P | 세전 | 최악 원화/달러 | S&P | 오른/내린 달 | 알파(연)·t | 정적 대비 알파·t | DSR | 매매·낸 세금 | "
           "연수익 − S&P (1억·1 / 1천만·1 / 1억·2 / 1천만·2) | 자격 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(res["rows"], key=lambda r: (r["benchmark"], r["id"])):
        if "error" in r:
            out.append(f"| {r['id']} | {r['group']} | 실패: {r['error'][:80]} |" + " |" * 11)
            continue
        m = r["cond"][base]
        e = (elig or {}).get("by_id", {}).get(r["id"])
        tag = "기준선" if r["benchmark"] else ("—" if e is None else "✅ 올림" if r["id"] in elig["promoted"] else
                                          "자격(확인용·차순위)" if e["eligible"] else f"✗ {e['why']}")
        diffs = " / ".join(p(r["cond"][k]["liq_cagr"] - r["cond"][k]["bench_liq_cagr"]) for k in keys if k in r["cond"])
        out.append(f"| {r['id']} | {r['group']} | {p(m['liq_cagr'])} | {p(m['bench_liq_cagr'])} | {p(m['pretax_cagr'])} | {p(m['mdd'], 0)} / {p(m['mdd_usd'], 0)} | "
                   f"{p(m['bench_mdd'], 0)} / {p(m['bench_mdd_usd'], 0)} | {x(m['up_capture'])} / {x(m['down_capture'])} | {p(m['alpha'])} · {x(m['alpha_t'], 1)} | "
                   f"{p(m.get('alpha_vs_static'))} · {x(m.get('alpha_vs_static_t'), 1)} | {x(m.get('dsr_alpha'))} | {m['trades']} · {m['taxes_paid'] / 1e4:,.0f}만 | "
                   f"{diffs} | {tag} |")
    out += ["", f"시도 수 {res['n_trials']}. 점수 = (연수익 − S&P) + 0.5 × (원화 최악 손실 개선). 정적 대비 알파 = 같은 틀을 추세 없이 든 기준선에 회귀한 잔여 수익."]
    if elig is not None:
        out += ["", f"검증으로 올림(계획 규칙대로 자동, 묶음마다 1개·최대 2개): {', '.join(elig['promoted']) or '없음 → 검증을 열지 않고 라운드 종료'}"]
    if passes:
        out += ["", "#### 통과 기준(검증)"] + [f"- **{i}**: {v['verdict']} — " + " · ".join(
            f"{n} {'○' if ok else '✗'} {d}".strip() for n, ok, d in v["checks"]) for i, v in passes.items()]
    for k, v in extra.items():
        out += ["", f"#### {k}", "```", str(v), "```"]
    return "\n".join(out)
