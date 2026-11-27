"""실험실 4차(Fable 설계 #73) 실행 본체.

- 크기 4개(1천만·3천만·5천만·1억) × 비용 2개(1·2배) = 8조건, 기준 1억·1배. 모든 숫자는 청산 기준 평가액(liq_nav).
- 계좌 모형: foreign(해외 직접) / deferred(절세계좌형) / domestic(국내 일반). 원화 자산(합성 국내 ETF·원화 현금)은 환율·환전 없음.
- 구조 몫 = 전략 − 같은 비중 해외 직접(절세 매도 없음). 판단 몫 = F 전략 − 평균 헤지 비율이 같은 고정 혼합(BKM_<id>).
- 자격(eligibility4)·통과(pass_table4)는 계획 숫자 그대로. 점수는 순위·자격에 쓰지 않는다(계획 #73).
DB 없이 돌 수 있게 가격·환율·지표·합성 시세만 받는다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant.lab.backtest import Costs, run_backtest
from quant.lab.metrics import (beta_adjusted_alpha, cagr, deflated_sharpe_excess, drawdown_in, excess_sharpe, max_drawdown,
                               recovery_days, summary, ulcer_index)
from quant.lab.splits import CRASH_2008, DEFAULT_SPLITS, DEV_FX, GL_CRASHES, GL_PERIOD, VALID_DRAWDOWNS
from quant.lab.strategy import BuyAndHold

from .experiments import PREV_TRIALS, ROUND4, Exp
from .rules import FixedMix, GrowthTrend
from .synthetic import KRW_ASSETS

SIZES = [10_000_000.0, 30_000_000.0, 50_000_000.0, 100_000_000.0]
CONDITIONS = [(s, k) for k in (1.0, 2.0) for s in SIZES]
BASE = (100_000_000.0, 1.0)
H1_MIN = {10_000_000.0: 0.003, 30_000_000.0: 0.0015, 50_000_000.0: 0.001, 100_000_000.0: 0.0}
STRUCT_REF = {"R4_H1": "BIV", "R4_C1": "B90", "R4_I2": "B90", "R4_C2": "B80", "R4_I3": "B80", "R4_I1": "B00"}
MAIN_F = ("R4_F1", "R4_F2")
NEIGHBORS = {"R4_F1": ("R4_F1a", "R4_F1b"), "R4_F2": ("R4_F2a", "R4_F2b")}


def ck(c) -> str:
    return f"{int(c[0] / 1e6)}M_x{c[1]:g}"


def account_costs(account: str, k: float) -> Costs:
    c = Costs().scaled(k)
    if account == "deferred":
        return Costs(fee=c.fee, fx_spread=c.fx_spread, slippage=c.slippage, dividend_tax=0.0)  # 이연: 분배금 세금도 나중에
    if account == "domestic":
        return Costs(fee=c.fee, fx_spread=c.fx_spread, slippage=c.slippage, dividend_tax=Costs().domestic_tax)
    return c


def period_of(e: Exp, period: str) -> tuple[pd.Timestamp, pd.Timestamp | None]:
    if period == "dev" and (e.params or {}).get("period") == "fx":
        return pd.Timestamp(DEV_FX[0]), pd.Timestamp(DEV_FX[1])
    return DEFAULT_SPLITS.period(period)


@dataclass
class Ctx:
    prices: pd.DataFrame
    fx: pd.Series
    mf: pd.DataFrame
    div: pd.DataFrame | None = None


def _bh(ticker: str, account: str):
    return Exp(f"B00" if ticker == "SPY" else f"BH_{ticker}", "기준선", "", lambda px, mf: BuyAndHold(ticker), "M", {"account": account})


B00 = _bh("SPY", "foreign")


def run_one(ctx: Ctx, e: Exp, start, end, cond, account: str | None = None):
    acc = account or (e.params or {}).get("account", "foreign")
    strat = e.build(ctx.prices, ctx.mf)
    div = ctx.div if acc != "deferred" else None
    res = run_backtest(ctx.prices, ctx.fx, strat, start, end, capital_krw=cond[0], rebalance=e.rebalance,
                       costs=account_costs(acc, cond[1]), div_yield=div, krw_assets=KRW_ASSETS, account=acc)
    return strat, res


def yearly_returns(liq: pd.Series) -> pd.Series:
    y = liq.groupby(liq.index.year).last()
    first = liq.iloc[0]
    return pd.concat([pd.Series([first], index=[y.index[0] - 1]), y]).pct_change().dropna()


def measure(res, ref) -> dict:
    """ref = 같은 조건의 B00(해외 직접 S&P) 결과. 모두 청산 기준."""
    s, b = res.liq_nav, ref.liq_nav
    m = summary(s, b)
    m.update({"liq_cagr": cagr(s), "bench_liq_cagr": cagr(b), "mdd": max_drawdown(s), "bench_mdd": max_drawdown(b),
              "ulcer": ulcer_index(s), "bench_ulcer": ulcer_index(b), "recovery_days": recovery_days(s),
              "trades": len(res.trades), "taxes_paid": float(sum(res.taxes.values())),
              "crash_2008": drawdown_in(s, *CRASH_2008), "bench_crash_2008": drawdown_in(b, *CRASH_2008)})
    return m


class Runner:
    """같은 (실험, 구간, 조건, 계좌) 실행은 한 번만(기준선 재사용)."""

    def __init__(self, ctx: Ctx, log=print):
        self.ctx, self.log, self.cache = ctx, log, {}

    def get(self, e: Exp, start, end, cond, account: str | None = None):
        acc = account or (e.params or {}).get("account", "foreign")
        key = (e.id, str(start), str(end), cond, acc)
        if key not in self.cache:
            self.cache[key] = run_one(self.ctx, e, start, end, cond, acc)
        return self.cache[key]


def _krw_usd(liq: pd.Series, fx: pd.Series) -> pd.Series:
    return liq / fx.reindex(liq.index).ffill()


def run_batch4(ctx: Ctx, exps: list[Exp], benches: list[Exp], *, period: str = "dev", conditions=CONDITIONS,
               n_trials: int | None = None, f_var: float | None = None, log=print) -> dict:
    R = Runner(ctx, log)
    rows, daily = [], {}
    bench_by = {b.id: b for b in benches}
    for e in exps + benches:
        t0 = time.time()
        start, end = period_of(e, period)
        row = {"id": e.id, "group": e.group, "hypothesis": e.hypothesis, "account": (e.params or {}).get("account", "foreign"),
               "period": [str(start.date()), str(end.date()) if end is not None else None], "benchmark": e in benches,
               "neighbor_of": (e.params or {}).get("neighbor_of"), "cond": {}}
        try:
            for c in conditions:
                strat, res = R.get(e, start, end, c)
                _, ref = R.get(B00, start, end, c)
                m = measure(res, ref)
                if c == BASE:
                    a = beta_adjusted_alpha(res.liq_nav, ref.liq_nav, (ctx.prices["SHY"] * ctx.fx.reindex(ctx.prices.index).ffill()))
                    m["alpha"], m["alpha_t"] = a["alpha"], a["t"]
                    m["usd_mdd"] = max_drawdown(_krw_usd(res.liq_nav, ctx.fx))
                    m["harvests"] = len(getattr(strat, "harvests", []) or [])
                    if hasattr(strat, "switches"):
                        hd = pd.Series(dict(strat.hedge_days)).astype(float)
                        m["switches"], m["hedge_ratio"] = strat.switches, float(hd.mean()) if len(hd) else 0.0
                    m["year_end"] = {str(k): float(v) for k, v in res.liq_nav.groupby(res.liq_nav.index.year).last().items()}
                    if period == "valid":
                        m["valid_drawdowns"] = {k: {"s": drawdown_in(res.liq_nav, *v), "spy": drawdown_in(ref.liq_nav, *v)}
                                                for k, v in VALID_DRAWDOWNS.items()}
                    daily[e.id] = pd.DataFrame({"liq_nav": res.liq_nav, "spy_liq_nav": ref.liq_nav, "nav": res.nav})
                    row["_res"] = res
                row["cond"][ck(c)] = m
            b = row["cond"][ck(BASE)]
            log(f"{e.id}: 청산 기준 {b['liq_cagr'] * 100:+.2f}% (S&P {b['bench_liq_cagr'] * 100:+.2f}%), 최악 {b['mdd'] * 100:.0f}% "
                f"(S&P {b['bench_mdd'] * 100:.0f}%) [{row['account']}, {row['period'][0][:4]}~] ({time.time() - t0:.0f}초)")
        except Exception as ex:  # noqa: BLE001
            row["error"] = f"{type(ex).__name__}: {ex}"
            log(f"{e.id}: 실패 {row['error']}")
        rows.append(row)
    by = {r["id"]: r for r in rows if "error" not in r}
    # 구조 몫: 같은 비중 해외 직접(절세 매도 없음)과의 청산 기준 연수익 차이(모든 조건)
    for i, ref_id in STRUCT_REF.items():
        if i not in by:
            continue
        e = next(x for x in exps if x.id == i)
        start, end = period_of(e, period)
        ref_e = B00 if ref_id == "B00" else bench_by.get(ref_id)
        if ref_e is None:
            continue
        for c in conditions:
            _, rr = R.get(ref_e, start, end, c)
            by[i]["cond"][ck(c)]["struct_ref"] = ref_id
            by[i]["cond"][ck(c)]["struct_share"] = by[i]["cond"][ck(c)]["liq_cagr"] - cagr(rr.liq_nav)
            by[i]["cond"][ck(c)]["ref_liq_cagr"] = cagr(rr.liq_nav)
            by[i]["cond"][ck(c)]["ref_mdd"] = max_drawdown(rr.liq_nav)
    # 판단 몫: F 전략 − 평균 헤지 비율 같은 고정 혼합(BKM_<id>), 같은 계좌(절세계좌형)와 국내 일반 둘 다
    f_rows = [r for r in rows if r["group"] == "F" and "error" not in r]
    f_ex = []
    for r in f_rows:
        e = next(x for x in exps if x.id == r["id"])
        start, end = period_of(e, period)
        h = r["cond"][ck(BASE)].get("hedge_ratio", 0.0)
        mix = {k: v for k, v in {"KSPX_H": h, "KSPX_U": 1 - h}.items() if v > 1e-9}
        bkm = Exp(f"BKM_{r['id']}", "기준선", "", lambda px, mf, mix=mix, n=f"BKM_{r['id']}": FixedMix(n, mix), "M", {"account": "deferred"})
        i1 = next((x for x in exps if x.id == "R4_I1"), None) or Exp("R4_I1", "I", "", lambda px, mf: BuyAndHold("KSPX_U"), "M", {"account": "deferred"})
        for c in conditions:
            _, bk = R.get(bkm, start, end, c)
            _, i1r = R.get(i1, start, end, c)
            m = r["cond"][ck(c)]
            m["judge_share"] = m["liq_cagr"] - cagr(bk.liq_nav)
            m["i1_liq_cagr"], m["i1_mdd"], m["i1_ulcer"] = cagr(i1r.liq_nav), max_drawdown(i1r.liq_nav), ulcer_index(i1r.liq_nav)
            if c == BASE:
                res = r["_res"]
                m["bkm_mix"] = mix
                ex_l = excess_sharpe(res.liq_nav, bk.liq_nav)
                f_ex.append(ex_l)
                yr = yearly_returns(res.liq_nav) - yearly_returns(bk.liq_nav)
                m["judge_years"] = {str(k): float(v) for k, v in yr.items()}
                m["_pair"] = (res, bk)
                if period == "valid":
                    m["i1_valid_drawdowns"] = {k: drawdown_in(i1r.liq_nav, *v) for k, v in VALID_DRAWDOWNS.items()}
        # 국내 일반계좌에서도
        _, fd = R.get(e, start, end, BASE, account="domestic")
        _, bd = R.get(bkm, start, end, BASE, account="domestic")
        r["cond"][ck(BASE)]["judge_share_domestic"] = cagr(fd.liq_nav) - cagr(bd.liq_nav)
    f_ex = [x for x in f_ex if x == x]
    var = f_var if f_var is not None else (float(np.var(f_ex, ddof=1)) if len(f_ex) >= 2 else None)
    n = n_trials if n_trials is not None else PREV_TRIALS + len(ROUND4)
    for r in f_rows:
        m = r["cond"][ck(BASE)]
        res, bk = m.pop("_pair")
        m["dsr_judge"] = min(deflated_sharpe_excess(res.liq_nav, bk.liq_nav, n, var), deflated_sharpe_excess(res.nav, bk.nav, n, var))
        m["n_trials"] = n
    for r in rows:
        r.pop("_res", None)
    return {"rows": rows, "n_trials": n, "f_var": var, "daily": daily, "_runner": R}


def _by(rows):
    return {r["id"]: r for r in rows if "error" not in r}


def _c_ok(by, i) -> tuple[bool, str]:
    """C·I 자격 (가)~(라)."""
    base, x2 = ck(BASE), ck((BASE[0], 2.0))
    m, m2 = by[i]["cond"][base], by[i]["cond"][x2]
    if not (m["liq_cagr"] >= m["bench_liq_cagr"] - 0.003 and m2["liq_cagr"] >= m2["bench_liq_cagr"] - 0.003):
        return False, "(가) 연수익 < S&P − 0.3%p"
    if not m["mdd"] >= 0.85 * m["bench_mdd"]:
        return False, "(나) 최악 손실 > S&P × 0.85"
    if not m["crash_2008"] > m["bench_crash_2008"] + 0.01:
        return False, "(다) 2008 하락이 S&P보다 1%p 넘게 작지 않음"
    if not all((c.get("struct_share") or -1) > 0 for c in by[i]["cond"].values()):
        return False, "(라) 구조 몫 ≤ 0인 조건이 있음"
    return True, ""


def eligibility4(rows: list[dict]) -> dict:
    by = _by(rows)
    base, x2 = ck(BASE), ck((BASE[0], 2.0))
    out: dict[str, tuple[bool, str]] = {}
    for i in ("R4_C1", "R4_C2", "R4_I1", "R4_I2", "R4_I3"):
        if i in by:
            out[i] = _c_ok(by, i)
    if "R4_H1" in by and "BIV" in by:
        h, why = by["R4_H1"], ""
        for c in CONDITIONS:
            m, bv = h["cond"][ck(c)], by["BIV"]["cond"][ck(c)]
            if not (m["liq_cagr"] > bv["liq_cagr"] and m["liq_cagr"] > m["bench_liq_cagr"]):
                why = f"{ck(c)}에서 BIV·B00보다 높지 않음"
                break
            if c[1] == 1.0 and not m["liq_cagr"] - bv["liq_cagr"] > H1_MIN[c[0]] - 1e-12:
                why = f"{int(c[0] / 1e6)}백만 원 이득 {(m['liq_cagr'] - bv['liq_cagr']) * 100:+.2f}%p < 문턱 {H1_MIN[c[0]] * 100:.2f}%p"
                break
        if not why and h["cond"][base]["mdd"] < h["cond"][base]["bench_mdd"] - 0.005:
            why = "최악 손실이 S&P보다 0.5%p 넘게 나쁨"
        out["R4_H1"] = (not why, why)
    for i in MAIN_F + tuple(n for v in NEIGHBORS.values() for n in v):
        if i not in by:
            continue
        m, m2 = by[i]["cond"][base], by[i]["cond"][x2]
        if i not in MAIN_F:
            out[i] = (False, f"이웃(판단 몫 {m['judge_share'] * 100:+.2f}%p) — 올리지 않음")
            continue
        yrs = list((m.get("judge_years") or {}).values())
        why = ""
        if not (m["judge_share"] >= 0.005 and m2["judge_share"] >= 0.005 and m.get("judge_share_domestic", -1) > 0):
            why = "(가) 판단 몫 < 0.5%p(비용 1·2배) 또는 국내 일반에서 ≤ 0"
        elif not (m["liq_cagr"] >= m["bench_liq_cagr"] and m["liq_cagr"] >= m["i1_liq_cagr"]):
            why = "(나) 연수익 < S&P 또는 < I1"
        elif not (m["mdd"] >= m["i1_mdd"] and m["ulcer"] < m["i1_ulcer"]):
            why = "(다) 최악 손실·물린 정도가 I1보다 나쁨"
        elif not ((m.get("switches") or 0) >= 10 and yrs and np.mean([y > 0 for y in yrs]) >= 0.6
                  and np.mean(sorted(yrs)[:-1]) > 0
                  and np.mean([v for k, v in m["judge_years"].items() if k not in ("2008", "2009")]) > 0):
            why = "(라) 갈아타기 < 10번 또는 해마다 승률·한 해 빼기·2008~09 빼기 실패"
        elif not all(by.get(nb, {}).get("cond", {}).get(base, {}).get("judge_share", -1) > 0 for nb in NEIGHBORS[i]):
            why = "(마) 이웃 설정의 판단 몫 ≤ 0"
        elif not (m.get("dsr_judge") or 0) >= 0.95:
            why = f"(바) 증명 부족 — DSR {m.get('dsr_judge', float('nan')):.2f} < 0.95"
        out[i] = (not why, why)
    ok = lambda i: out.get(i, (False,))[0]  # noqa: E731
    lc = lambda i: by[i]["cond"][base]["liq_cagr"]  # noqa: E731
    promoted = []
    cs = sorted([i for i in ("R4_C1", "R4_C2") if ok(i)], key=lambda i: -lc(i))
    if cs:
        promoted.append(cs[0])
    elif ok("R4_H1"):
        promoted.append("R4_H1")
    iz = sorted([i for i in ("R4_I1", "R4_I2", "R4_I3") if ok(i)], key=lambda i: -lc(i))
    if iz:
        promoted.append(iz[0])
    elif "R4_I1" in by and by["R4_I1"]["cond"][base]["liq_cagr"] >= by["R4_I1"]["cond"][base]["bench_liq_cagr"] + 0.005:
        promoted.append("R4_I1")
    fs = sorted([i for i in MAIN_F if ok(i)], key=lambda i: -(by[i]["cond"][base].get("dsr_judge") or 0))
    if fs:
        promoted.append(fs[0])
    close_fx = all(not ok(i) and not out.get(i, (False, ""))[1].startswith("(바)") for i in MAIN_F if i in out)
    return {"by_id": {i: {"eligible": a, "why": w} for i, (a, w) in out.items()}, "promoted": promoted[:3], "close_fx": close_fx}


def rolling_windows(runner: Runner, e: Exp, years: int = 5, first: int = 2004, last_end: int = 2022) -> dict:
    """시작 해를 한 해씩 옮긴 5년 구간에서 1번 기준(연수익 ≥ S&P − 0.3%p, C는 ≥ S&P)을 넘는 비율(통과 기준 5)."""
    need = 0.0 if e.group == "C" else -0.003
    hits, total = 0, 0
    for y in range(first, last_end - years + 2):
        s, t = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + years - 1}-12-31")
        _, r = runner.get(e, s, t, BASE)
        _, b = runner.get(B00, s, t, BASE)
        total += 1
        hits += int(cagr(r.liq_nav) - cagr(b.liq_nav) >= need)
    return {"share": hits / total if total else float("nan"), "n": total}


def pass_table4(res: dict, exps: list[Exp], benches: list[Exp]) -> dict:
    by = _by(res["rows"])
    R: Runner = res["_runner"]
    base, x2 = ck(BASE), ck((BASE[0], 2.0))
    out = {}
    for i, r in by.items():
        if r["benchmark"] or r.get("neighbor_of"):
            continue
        m = r["cond"][base]
        checks = []
        if i == "R4_H1":
            for c in [c for c in CONDITIONS if c[1] == 1.0]:
                bv = by["BIV"]["cond"][ck(c)]["liq_cagr"] if "BIV" in by else float("nan")
                d = r["cond"][ck(c)]["liq_cagr"] - bv
                checks.append((f"{int(c[0] / 1e6)}백만 이득 ≥ {H1_MIN[c[0]] * 100:.2f}%p", d > H1_MIN[c[0]] - 1e-12, f"{d * 100:+.2f}%p"))
            ys = pd.Series(m.get("year_end", {}))
            bys = pd.Series(by["BIV"]["cond"][base].get("year_end", {})) if "BIV" in by else pd.Series(dtype=float)
            if len(ys) and len(bys):
                a = ys.pct_change().dropna()
                b = bys.pct_change().dropna()
                wins = int(((a - b).dropna() > 0).sum())
                checks.append(("해마다 수익률 차이 > 0이 4년 이상", wins >= 4, f"{wins}/{len((a - b).dropna())}"))
            checks.append(("사람 확인(원가 방식·결제일·공제·되사기 인정)", None, "사람"))
        elif r["group"] in ("C", "I"):
            m2 = r["cond"][x2]
            need = 0.0 if r["group"] == "C" else -0.003
            checks.append(("1 연수익 ≥ S&P−0.3%p(1·2배)", m["liq_cagr"] - m["bench_liq_cagr"] >= -0.003 and m2["liq_cagr"] - m2["bench_liq_cagr"] >= -0.003,
                           f"{(m['liq_cagr'] - m['bench_liq_cagr']) * 100:+.2f}%p"))
            checks.append(("2 최악 손실 ≤ S&P×0.85", m["mdd"] >= 0.85 * m["bench_mdd"],
                           f"{m['mdd'] * 100:.0f}% vs {m['bench_mdd'] * 100:.0f}% · 달러 {m.get('usd_mdd', float('nan')) * 100:.0f}% · 회복 {m.get('recovery_days')}일"))
            vd = m.get("valid_drawdowns") or {}
            less = sum(1 for v in vd.values() if v["s"] > v["spy"] + 0.01)
            checks.append(("3 세 하락 중 2번 이상 1%p 넘게 덜 빠짐", less >= 2, f"{less}/3"))
            checks.append(("4 내린 달 < 오른 달 − 0.03", m["down_capture"] < m["up_capture"] - 0.03, f"{m['up_capture']:.2f}/{m['down_capture']:.2f}"))
            e = next(x for x in exps if x.id == i)
            rw = rolling_windows(R, e)
            checks.append(("5 구조 몫 > 0(모든 조건), 5년 이동 구간 80% 이상",
                           all((c.get("struct_share") or -1) > 0 for c in r["cond"].values()) and rw["share"] >= 0.8,
                           f"이동 구간 {rw['share'] * 100:.0f}%"))
            same = "R4_H1·B00" if r["group"] == "C" else "R4_I1"
            checks.append(("6 같은 계좌 S&P만 든 것과 나란히", None, same))
            checks.append(("7 DSR(보고)", None, "구조 묶음 — 보고만"))
            sm = r["cond"][ck((10_000_000.0, 1.0))]
            checks.append(("크기: 1천만에서도 1·2번", sm["liq_cagr"] - sm["bench_liq_cagr"] >= need and sm["mdd"] >= 0.85 * sm["bench_mdd"], ""))
        elif r["group"] == "F":
            m2 = r["cond"][x2]
            checks.append(("① 연수익 ≥ S&P, ≥ I1", m["liq_cagr"] >= m["bench_liq_cagr"] and m["liq_cagr"] >= m["i1_liq_cagr"], ""))
            checks.append(("② 판단 몫 > 0(1·2배, 두 계좌)", m["judge_share"] > 0 and m2["judge_share"] > 0 and m.get("judge_share_domestic", -1) > 0,
                           f"{m['judge_share'] * 100:+.2f}%p"))
            checks.append(("③ 최악 손실 ≤ I1", m["mdd"] >= m["i1_mdd"], ""))
            checks.append(("④ DSR ≥ 0.95", (m.get("dsr_judge") or 0) >= 0.95, f"{m.get('dsr_judge', float('nan')):.2f}"))
            vd, iv = m.get("valid_drawdowns") or {}, m.get("i1_valid_drawdowns") or {}
            bad = sum(1 for k, v in vd.items() if k in iv and v["s"] < iv[k] - 0.01)
            checks.append(("⑤ 세 하락 중 2번 이상 I1보다 1%p 넘게 나쁘지 않음", (len(vd) - bad) >= 2, f"나빴던 하락 {bad}"))
        hard = [c for c in checks if c[1] is not None]
        out[i] = {"checks": checks, "pass": bool(hard) and all(c[1] for c in hard)}
    return out


def gl_report(prices_usd: pd.DataFrame, unrate: pd.DataFrame) -> dict:
    """R4_GL(보고 전용): G02 규칙(조절값 그대로)을 VFINX·3개월 국채(달러, 세금 없음)로 1980~2003. 다섯 하락 중 4번 이상 1%p 넘게 덜 빠져야 G 묶음을 남긴다."""
    if prices_usd.get("SPY") is None or prices_usd["SPY"].dropna().empty:
        return {"status": "확인 못 함(VFINX 시세 없음)"}
    s, t = pd.Timestamp(GL_PERIOD[0]), pd.Timestamp(GL_PERIOD[1])
    px = prices_usd.loc[: pd.Timestamp("2020-12-31")]
    first = px["SPY"].first_valid_index()
    start = max(s, first + pd.Timedelta(days=300))
    ones = pd.Series(1.0, index=px.index)
    zero = Costs(fx_spread=0.0, tax_rate=0.0, dividend_tax=0.0)
    g = run_backtest(px, ones, GrowthTrend("R4_GL", unrate.reindex(px.index), avoid_equity=0.5), start, pd.Timestamp("2020-12-31"),
                     capital_krw=1e8, rebalance="M", costs=zero)
    b = run_backtest(px, ones, BuyAndHold("SPY"), start, pd.Timestamp("2020-12-31"), capital_krw=1e8, rebalance="M", costs=zero)
    rows = {}
    for k, (a0, a1) in GL_CRASHES.items():
        if pd.Timestamp(a0) < start:
            rows[k] = {"status": "자료 없음"}
            continue
        ds, db = drawdown_in(g.nav, a0, a1), drawdown_in(b.nav, a0, a1)
        rows[k] = {"g02": ds, "spy": db, "less": bool(ds > db + 0.01)}
    n_less = sum(1 for v in rows.values() if v.get("less"))
    n_ok = sum(1 for v in rows.values() if "less" in v)
    return {"status": "ok", "from": str(start.date()), "crashes": rows, "less": n_less, "seen": n_ok,
            "close_g": n_less < 4, "cagr": cagr(g.nav.loc[:t]), "spy_cagr": cagr(b.nav.loc[:t])}


def table4(res: dict, period: str, plan: int, elig: dict | None, passes: dict | None, extra: dict | None = None) -> str:
    p = lambda v, d=1: "—" if v is None or v != v else f"{v * 100:+.{d}f}%"  # noqa: E731
    base = ck(BASE)
    out = [f"### 실험실 4차 · Fable 설계 #{plan} · {period} · 1억·비용 1배 · 모두 청산 기준", "",
           "| 실험 | 계좌 | 구간 | 연수익 | S&P | 최악 손실 | S&P | 2008 | 구조 몫 | 판단 몫 | 헤지 비율·갈아타기 | 매매 | 1천만/3천만/5천만/1억 연수익 | 자격 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(res["rows"], key=lambda r: (r["benchmark"], r["id"])):
        if "error" in r:
            out.append(f"| {r['id']} | {r.get('account')} | 실패: {r['error'][:80]} |" + " |" * 11)
            continue
        m = r["cond"][base]
        e = (elig or {}).get("by_id", {}).get(r["id"])
        tag = "기준선" if r["benchmark"] else ("—" if e is None else "✅ 올림" if r["id"] in elig["promoted"] else "자격" if e["eligible"] else f"✗ {e['why']}")
        sizes = " / ".join(p(r["cond"][ck((s, 1.0))]["liq_cagr"], 2) for s in SIZES)
        hedge = f"{m['hedge_ratio'] * 100:.0f}% · {m['switches']}번" if "switches" in m else "—"
        out.append(f"| {r['id']} | {r['account']} | {r['period'][0][:4]}~ | {p(m['liq_cagr'], 2)} | {p(m['bench_liq_cagr'], 2)} | {p(m['mdd'], 0)} | "
                   f"{p(m['bench_mdd'], 0)} | {p(m.get('crash_2008'), 0)} | {p(m.get('struct_share'), 2)} | {p(m.get('judge_share'), 2)} | {hedge} | "
                   f"{m['trades']} | {sizes} | {tag} |")
    out += ["", f"시도 수 {res['n_trials']}. 구조 몫 = 같은 비중을 해외 직접 계좌에서 절세 매도 없이 든 것과의 차이. 판단 몫 = 평균 헤지 비율이 같은 고정 혼합과의 차이."
            " 계좌 세율(22%·250만, 9.9%·200만, 15.4%)은 사람 확인 필요. 국내 ETF는 합성 시세."]
    if elig is not None:
        out += ["", f"검증으로 올림(계획 규칙대로 자동): {', '.join(elig['promoted']) or '없음 → 검증 안 돌리고 라운드 종료'}"
                + (" · 환율 묶음 닫음" if elig.get("close_fx") else "")]
    if passes:
        out += ["", "#### 통과 기준(검증)"]
        for i, v in passes.items():
            out.append(f"- **{i}**: {'통과' if v['pass'] else '탈락'} — " + " · ".join(
                f"{n} {'○' if ok else '✗' if ok is False else '·'} {d}".strip() for n, ok, d in v["checks"]))
    for k, v in (extra or {}).items():
        out += ["", f"#### {k}", "```", str(v), "```"]
    return "\n".join(out)
