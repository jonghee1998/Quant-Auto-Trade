"""예측·규칙 실험 일괄 실행: python -m quant.forecast.run --period dev [--ids A01,K02] [--out lab-out] [--round 2]

2차(Fable 설계 #59): 실험마다 네 조건(자금 1천만·1억 × 비용 1배·2배)으로 돌리고, 기준 조건(1억·1배)으로 점수·DSR·검증 자격을 정한다.
- 연수익 비교는 '청산 세후'(마지막 날 다 팔고 세금까지 낸 금액)로. S&P(SPY 그냥 보유)도 같은 조건.
- DSR은 날마다 '전략 − S&P' 수익으로, 시도 수는 묶음 전체 같은 값(개발 48), 시도 간 분산은 묶음을 다 돌린 뒤 한 번에.
- 기준선(B80·B60·BEQ)은 자: 시도 수에 안 세고 검증에 안 올린다.
- 결과: markdown 표, JSON(코드 버전·데이터 날짜·특성별 첫 사용 날짜·조건별 결과·자격), 실험별 날짜별 평가액 CSV.
홀드아웃(2023~)은 여기서 돌리지 않는다. 1차(30개)는 --round 1 로만(예전 방식 그대로 evaluate).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from quant.lab.backtest import Costs, run_backtest
from quant.lab.cli import load_div_yield, load_prices
from quant.lab.metrics import deflated_sharpe_excess, drawdown_in, excess_sharpe, liquidated_cagr, max_drawdown, summary
from quant.lab.registry import DbRegistry, Experiment
from quant.lab.splits import DEFAULT_SPLITS, STRESS, VALID_DRAWDOWNS
from quant.lab.strategy import BuyAndHold

from .experiments import BENCHMARKS, CLEAN_MARKET, MACRO_SERIES, PLAN_ISSUE, PREV_TRIALS, ROUND1, ROUND2, Exp
from .features import macro_panel

CONDITIONS = [(100_000_000.0, 1.0), (10_000_000.0, 1.0), (100_000_000.0, 2.0), (10_000_000.0, 2.0)]
BASE = CONDITIONS[0]


def cond_key(c: tuple[float, float]) -> str:
    return f"{int(c[0] / 1e6)}M_x{c[1]:g}"


def load_macro(conn, series: list[str]) -> dict[str, pd.DataFrame]:
    with conn.cursor() as cur:
        cur.execute("select series, ref_date, release_date, value from macro_series where series = any(%s)", (series,))
        df = pd.DataFrame(cur.fetchall(), columns=["series", "ref_date", "release_date", "value"])
    return {k: g.drop(columns="series") for k, g in df.groupby("series")}


def dev_score(m: dict) -> float:
    """계획 #59 개발 점수: (청산 세후 연수익 − S&P 청산 세후) + 0.5 × (S&P 최악 손실 − 전략 최악 손실, 덜 빠진 만큼)."""
    ex = (m.get("liq_cagr") or 0) - (m.get("bench_liq_cagr") or 0)
    dd = (m.get("mdd") or 0) - (m.get("bench_mdd") or 0)  # 둘 다 음수: 덜 빠지면 양수
    return float(ex + 0.5 * dd)


def equity_weight(w: pd.DataFrame | None) -> pd.Series | None:
    """날짜별 주식 노출(SHY 제외, SSO는 2배로 셈)."""
    if w is None or w.empty:
        return None
    cols = [c for c in w.columns if c != "SHY"]
    return sum((w[c] * (2.0 if c == "SSO" else 1.0) for c in cols), pd.Series(0.0, index=w.index))


def run_one(prices, fx, e: Exp, mf, start, end, capital, k, div_yield, bench_res):
    strat = e.build(prices, mf)
    res = run_backtest(prices, fx, strat, start, end, capital_krw=capital, rebalance=e.rebalance, costs=Costs().scaled(k),
                       div_yield=div_yield)
    m = summary(res.nav, bench_res.nav)
    m["liq_cagr"] = liquidated_cagr(res.after_tax_if_liquidated, capital, res.nav)
    m["bench_liq_cagr"] = liquidated_cagr(bench_res.after_tax_if_liquidated, capital, bench_res.nav)
    m["taxes_paid"] = float(sum(res.taxes.values()))
    m["dividend_taxes"] = float(res.dividend_taxes)
    m["trades"] = len(res.trades)
    m["excess_sharpe_daily"] = excess_sharpe(res.nav, bench_res.nav)
    ew = equity_weight(res.weights)
    m["avg_equity"] = float(ew.mean()) if ew is not None else None
    m["score"] = dev_score(m)
    return strat, res, m


def run_batch(prices: pd.DataFrame, fx: pd.Series, exps: list[Exp], benches: list[Exp], mf: pd.DataFrame, *,
              period: str = "dev", div_yield: pd.DataFrame | None = None, conditions=CONDITIONS,
              n_trials: int | None = None, log=print) -> dict:
    """DB 없이 돌 수 있는 본체. 반환: {"rows": [...], "bench": {...}, "n_trials", "trial_var", "daily": {id: DataFrame}}."""
    start, end = DEFAULT_SPLITS.period(period)
    spy = {c: run_backtest(prices, fx, BuyAndHold("SPY"), start, end, capital_krw=c[0], rebalance="M",
                           costs=Costs().scaled(c[1]), div_yield=div_yield) for c in conditions}
    rows, daily = [], {}
    for e in exps + benches:
        t0 = time.time()
        row = {"id": e.id, "group": e.group, "hypothesis": e.hypothesis, "rebalance": e.rebalance,
               "benchmark": e in benches, "cond": {}}
        try:
            for c in conditions:
                strat, res, m = run_one(prices, fx, e, mf, start, end, c[0], c[1], div_yield, spy[c])
                if c == conditions[0]:
                    ic = getattr(strat, "ic", None)
                    row["ic"] = ic() if callable(ic) else {}
                    row["_nav"], row["_bench"] = res.nav, spy[c].nav
                    daily[e.id] = pd.DataFrame({"nav": res.nav, "bench": spy[c].nav, "equity": equity_weight(res.weights)})
                row["cond"][cond_key(c)] = m
            b = row["cond"][cond_key(conditions[0])]
            log(f"{e.id}: 청산 세후 {b['liq_cagr'] * 100:+.1f}% (S&P {b['bench_liq_cagr'] * 100:+.1f}%), "
                f"최악 {b['mdd'] * 100:.0f}% (S&P {b['bench_mdd'] * 100:.0f}%), 점수 {b['score'] * 100:+.1f} ({time.time() - t0:.0f}초)")
        except Exception as ex:  # noqa: BLE001 — 한 실험 실패가 나머지를 막지 않는다
            row["error"] = f"{type(ex).__name__}: {ex}"
            log(f"{e.id}: 실패 {row['error']}")
        rows.append(row)
    # DSR 2단계: 묶음(기준선 제외)을 다 돌린 뒤 시도 간 '초과 샤프' 분산을 한 번에, 시도 수는 모두 같은 값
    trials = [r for r in rows if not r["benchmark"] and "error" not in r]
    srs = [r["cond"][cond_key(conditions[0])]["excess_sharpe_daily"] for r in trials]
    srs = [s for s in srs if s == s]
    var = float(np.var(srs, ddof=1)) if len(srs) >= 2 else None
    n = n_trials if n_trials is not None else 37 + len(ROUND2) + (0 if period == "dev" else len(trials))  # 2차 계획 #59 값
    for r in trials:
        r["cond"][cond_key(conditions[0])]["dsr_excess"] = deflated_sharpe_excess(r["_nav"], r["_bench"], n, var)
        r["cond"][cond_key(conditions[0])]["n_trials"] = n
    if period == "valid":
        for r in rows:
            if "error" in r:
                continue
            r["valid_drawdowns"] = {k: {"strategy": drawdown_in(r["_nav"], *v), "spy": drawdown_in(r["_bench"], *v)}
                                    for k, v in VALID_DRAWDOWNS.items()}
            if r["group"] in ("A", "L"):
                r["stress"] = stress_check(prices, fx, next(e for e in exps if e.id == r["id"]), mf, div_yield)
    for r in rows:
        r.pop("_nav", None), r.pop("_bench", None)
    return {"rows": rows, "n_trials": n, "trial_var": var, "daily": daily}


def stress_check(prices, fx, e: Exp, mf, div_yield) -> dict:
    """과거 스트레스 구간(2005~2009) 최악 손실(보고 전용, 통과 기준 9번). 시세가 모자라면 '확인 못 함'."""
    try:
        s, t = pd.Timestamp(STRESS[0]), pd.Timestamp(STRESS[1])
        need = prices.loc[s:t, ["SPY", "SHY"]]
        if need.dropna().empty or need.dropna().index[0] > s + pd.Timedelta(days=366):
            return {"status": "확인 못 함(시세 없음)"}
        first = need.dropna().index[0]
        res = run_backtest(prices, fx, e.build(prices, mf), first, t, capital_krw=BASE[0], rebalance=e.rebalance, div_yield=div_yield)
        b = run_backtest(prices, fx, BuyAndHold("SPY"), first, t, capital_krw=BASE[0], rebalance="M", div_yield=div_yield)
        return {"status": "ok", "from": str(first.date()), "mdd": max_drawdown(res.nav), "spy_mdd": max_drawdown(b.nav)}
    except Exception as ex:  # noqa: BLE001
        return {"status": f"확인 못 함({type(ex).__name__}: {ex})"}


def eligibility(rows: list[dict]) -> dict:
    """계획 #59 '검증으로 올리는 규칙'을 숫자 그대로. 반환: {id: (자격, 이유)}, promoted(최대 2, 묶음마다 1)."""
    by = {r["id"]: r for r in rows if "error" not in r}
    base, x2 = cond_key(BASE), cond_key((BASE[0], 2.0))
    sc = lambda i: by[i]["cond"][base]["score"] if i in by else float("-inf")  # noqa: E731
    beq = by.get("BEQ", {}).get("cond", {}).get(base, {}).get("liq_cagr")
    out: dict[str, tuple[bool, str]] = {}

    def k_ok(i):
        m = by[i]["cond"][base]
        if beq is None or not (m["liq_cagr"] > beq):
            return False, "BEQ보다 청산 세후 연수익이 높지 않음"
        if i in ("K02", "K03") and not ((by[i].get("ic") or {}).get("ic_mean") or 0) > 0:
            return False, "IC 평균 ≤ 0"
        return True, ""

    for i in ["A01", "A02", "A03", "A04", "L01", "L02", "T07", "T08", "K01", "K02", "K03"]:
        if i not in by:
            out[i] = (False, "실행 실패·없음")
            continue
        m, m2 = by[i]["cond"][base], by[i]["cond"][x2]
        if not m["score"] > 0:
            out[i] = (False, "점수 ≤ 0")
            continue
        if not m2["score"] > 0:
            out[i] = (False, "비용 2배 점수 ≤ 0")
            continue
        g = by[i]["group"]
        ok, why = True, ""
        if i == "A04" and not (sc("A01") > 0 and (sc("A02") > 0 or sc("A03") > 0)):
            ok, why = False, "A01과 (A02 또는 A03) 점수가 각각 > 0 이 아님"
        elif g == "L" and m["mdd"] < m["bench_mdd"]:
            ok, why = False, "개발 최악 손실이 S&P보다 큼"
        elif g == "T":
            ic = by[i].get("ic") or {}
            p = ic.get("base_rate")
            if p is None or ic.get("hit") is None or ic.get("brier") is None:
                ok, why = False, "적중률·브라이어 없음"
            elif not (ic["hit"] > p and ic["brier"] < p * (1 - p)):
                ok, why = False, "적중률·브라이어가 기본 비율 예측보다 낫지 않음"
        elif g == "K":
            ok, why = k_ok(i)
        out[i] = (ok, why)
    if out.get("K03", (False,))[0] and not out.get("K02", (False,))[0]:
        out["K03"] = (False, "K02가 자격 없음")
    passed = sorted([i for i, (ok, _) in out.items() if ok], key=lambda i: -sc(i))
    promoted, groups = [], set()
    for i in passed:
        g = by[i]["group"]
        if g not in groups and len(promoted) < 2:
            promoted.append(i)
            groups.add(g)
    return {"by_id": {i: {"eligible": ok, "why": why} for i, (ok, why) in out.items()}, "promoted": promoted}


def table(res: dict, period: str, elig: dict | None) -> str:
    p = lambda v, d=1: "—" if v is None or v != v else f"{v * 100:+.{d}f}%"  # noqa: E731
    x = lambda v, d=2: "—" if v is None or v != v else f"{v:.{d}f}"  # noqa: E731
    base, keys = cond_key(BASE), [cond_key(c) for c in CONDITIONS]
    out = [f"### 실험실 2차 · Fable 설계 #59 · {period} · 기준 조건 1억·비용 1배", "",
           "| 실험 | 묶음 | 청산 세후 | S&P | 최악 손실 | S&P | 오른/내린 달 | 매매 | 평균 주식 | 예측력 | S&P 대비 DSR | 점수(1억·1배 / 1천만·1배 / 1억·2배 / 1천만·2배) | 자격 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    rows = sorted(res["rows"], key=lambda r: (r["benchmark"], -(r.get("cond", {}).get(base, {}).get("score", -9))))
    for r in rows:
        if "error" in r:
            out.append(f"| {r['id']} | {r['group']} | 실패: {r['error'][:60]} |" + " |" * 10)
            continue
        m, ic = r["cond"][base], r.get("ic") or {}
        pred = (f"IC {ic['ic_mean']:+.3f} (t {ic['ic_t']:.1f})" if ic.get("ic_mean") is not None
                else f"적중 {ic['hit'] * 100:.0f}%/기본 {ic['base_rate'] * 100:.0f}%" if ic.get("hit") is not None else "—")
        scores = " / ".join(f"{r['cond'][k]['score'] * 100:+.1f}" for k in keys)
        e = (elig or {}).get("by_id", {}).get(r["id"])
        tag = "기준선" if r["benchmark"] else ("—" if e is None else ("✅ 올림" if r["id"] in elig["promoted"] else "자격" if e["eligible"] else f"✗ {e['why']}"))
        out.append(f"| {r['id']} | {r['group']} | {p(m['liq_cagr'])} | {p(m['bench_liq_cagr'])} | {p(m['mdd'], 0)} | {p(m['bench_mdd'], 0)} | "
                   f"{x(m['up_capture'])}/{x(m['down_capture'])} | {m['trades']} | {x(m.get('avg_equity'))} | {pred} | "
                   f"{x(m.get('dsr_excess'))} | {scores} | {tag} |")
    out += ["", f"시도 수 {res['n_trials']}(묶음 전체 같은 값), 시도 간 초과 샤프 분산은 묶음을 다 돌린 뒤 계산. "
            "청산 세후 = 마지막 날 다 팔고 양도세까지 낸 금액 기준 연수익(배당세 15%·슬리피지·환전 포함). "
            "점수 = 청산 세후 차이 + 0.5 × 최악 손실 개선."]
    if elig is not None:
        out += ["", f"검증으로 올림(계획 규칙대로 자동): {', '.join(elig['promoted']) or '없음 → 검증 안 돌리고 라운드 종료'}"]
    if period == "valid":
        out += ["", "| 실험 | " + " | ".join(VALID_DRAWDOWNS) + " | 스트레스 2005~09 |", "|---|" + "---|" * (len(VALID_DRAWDOWNS) + 1)]
        for r in rows:
            if "valid_drawdowns" not in r:
                continue
            cells = [f"{p(v['strategy'], 0)} vs {p(v['spy'], 0)}" for v in r["valid_drawdowns"].values()]
            st = r.get("stress")
            st_s = "—" if st is None else (f"{p(st['mdd'], 0)} vs {p(st['spy_mdd'], 0)}" if st["status"] == "ok" else st["status"])
            out.append(f"| {r['id']} | " + " | ".join(cells) + f" | {st_s} |")
    return "\n".join(out)


def _clean(v):
    """jsonb는 NaN을 못 받는다 → None(중첩 포함)."""
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, float) and v != v:
        return None
    return v


def first_dates(mf: pd.DataFrame, cols: list[str]) -> dict[str, str | None]:
    return {c: (str(mf[c].first_valid_index().date()) if c in mf and mf[c].first_valid_index() is not None else None) for c in cols}


def _round1(a, conn, prices, fx, mf, sha):
    """1차 30개(기록용): 예전 방식(evaluate)."""
    from quant.lab.run import evaluate
    reg = DbRegistry(conn)
    pick = {s.strip() for s in a.ids.split(",") if s.strip()}
    for e in [e for e in ROUND1 if not pick or e.id in pick]:
        m = evaluate(prices, fx, e.build(prices, mf), hypothesis=e.hypothesis, params={"group": e.group, "rebalance": e.rebalance},
                     period=a.period, registry=reg, data_version=str(prices.index[-1].date()), code_version=sha, rebalance=e.rebalance)
        conn.commit()
        print(f"{e.id}: 연수익 {m['cagr'] * 100:+.1f}%", flush=True)
    return 0


def _round3(a, conn, prices, fx, mf, sha, out: Path) -> int:
    """3차(계획 #66): 청산 기준 평가액으로 모든 지표, 베타 보정 알파, 계획 규칙대로 자격·통과."""
    from .experiments import BENCHMARKS3, ROUND3
    from .round3 import BASE, ck, eligibility3, pass_table3, run_batch3, table3
    div = load_div_yield(conn)
    reg = DbRegistry(conn)
    pick = {s.strip() for s in a.ids.split(",") if s.strip()}
    exps = [e for e in ROUND3 if not pick or e.id in pick]
    db_trials = reg.distinct_trials()
    if a.period == "dev":
        n = max(PREV_TRIALS + len(ROUND3), db_trials)
    else:
        n = 5 + len(exps)  # 검증에 올라간 전략 수: 1차 5 + 이번에 올린 수(계획 #66 통과 기준 7)
    # 실업률 첫 발표값 점검: 2003~2022에 발표가 기준월보다 60일 넘게 늦게 기록된 값이 있으면 멈춘다(계획 #66)
    um = load_macro(conn, ["UNRATE"]).get("UNRATE")
    if um is not None and not um.empty:
        late = um[(pd.to_datetime(um["ref_date"]) >= "2003-01-01") & (pd.to_datetime(um["ref_date"]) <= "2022-12-31")
                  & ((pd.to_datetime(um["release_date"]) - pd.to_datetime(um["ref_date"])).dt.days > 60)]
        if len(late):
            print(f"멈춤: 실업률 발표일이 60일 넘게 늦은 값 {len(late)}개(예: {late.iloc[0]['ref_date']}) — 계획 #66 규칙")
            return 1
    else:
        print("멈춤: 실업률(UNRATE) 기록이 없다")
        return 1
    first = {t: (str(prices[t].first_valid_index().date()) if t in prices and prices[t].first_valid_index() is not None else None)
             for t in ["SPY", "IVV", "SHY", "TLT", "GLD"]}
    if a.period == "dev" and (first["SPY"] is None or first["SHY"] is None or first["SPY"] > "2003-01-01" or first["SHY"] > "2003-01-01"):
        print(f"멈춤: SPY·SHY 시세가 2003-01-01 이전부터 없다 {first}")
        return 1
    res = run_batch3(prices, fx, exps, BENCHMARKS3, mf, period=a.period, div_yield=div, n_trials=n,
                     log=lambda s: print(s, flush=True))
    elig = eligibility3(res["rows"]) if a.period == "dev" else None
    passes, combined = None, {}
    if a.period == "valid":
        both = run_batch3(prices, fx, exps, [], mf, period="valid", div_yield=div, conditions=[BASE], n_trials=n,
                          start="2004-01-01", end="2022-12-31", log=lambda s: print("[2004~2022] " + s, flush=True))
        combined = {r["id"]: r["cond"][ck(BASE)]["alpha_t"] for r in both["rows"] if "error" not in r}
        passes = pass_table3(res["rows"], combined)
    data_date = str(prices.index[-1].date())
    for r in res["rows"]:
        if r["benchmark"] or "error" in r:
            continue
        m = {k: v for k, v in r["cond"][ck(BASE)].items() if k not in ("year_end", "bench_year_end", "valid_drawdowns")}
        m["conditions"] = {k: {kk: v.get(kk) for kk in ("liq_cagr", "mdd", "alpha", "score", "trades")} for k, v in r["cond"].items()}
        reg.add(Experiment(r["id"], r["hypothesis"], {"group": r["group"], "rebalance": r["rebalance"], "plan": PLAN_ISSUE},
                           a.period, data_date, sha, _clean(m), False))
    conn.commit()
    for k, df in res.pop("daily").items():
        df.to_csv(out / f"daily-{a.period}-{k}.csv", index_label="date")
    meta = {"plan_issue": PLAN_ISSUE, "round": 3, "code_version": sha, "data_date": data_date, "period": a.period,
            "split": [str(x.date()) if x is not None else None for x in DEFAULT_SPLITS.period(a.period)],
            "n_trials": n, "db_distinct_trials": db_trials, "price_first_dates": first,
            "unrate_first": str(mf["unrate_latest"].first_valid_index()) if "unrate_latest" in mf else None,
            "dividend_days": int(div.notna().sum().sum()) if not div.empty else 0, "combined_alpha_t": combined}
    md = table3(res, a.period, PLAN_ISSUE, elig, passes)
    (out / f"forecast-{a.period}.md").write_text(md)
    (out / f"forecast-{a.period}.json").write_text(json.dumps({"meta": meta, **res, "eligibility": elig, "passes": passes},
                                                              ensure_ascii=False, default=str, indent=1))
    print(md)
    return 0 if any("error" not in r for r in res["rows"]) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["dev", "valid"], default="dev")
    ap.add_argument("--ids", default="", help="쉼표로 고르기(빈칸=2차 11개 전부, 기준선은 늘 같이)")
    ap.add_argument("--out", default="lab-out")
    ap.add_argument("--round", type=int, choices=[1, 2, 3], default=3)
    a = ap.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL 없음 → 실행 안 함")
        return 0
    import psycopg
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(url) as conn:
        prices, fx = load_prices(conn)
        prices = prices.loc[:, [c for c in prices.columns if prices[c].notna().any()]]
        mf = macro_panel(load_macro(conn, MACRO_SERIES), prices.index)
        if a.round == 1:
            return _round1(a, conn, prices, fx, mf, sha)
        if a.round == 3:
            return _round3(a, conn, prices, fx, mf, sha, out)
        div = load_div_yield(conn)
        pick = {s.strip() for s in a.ids.split(",") if s.strip()}
        exps = [e for e in ROUND2 if not pick or e.id in pick]
        res = run_batch(prices, fx, exps, BENCHMARKS, mf, period=a.period, div_yield=div,
                        log=lambda s: print(s, flush=True))
        elig = eligibility(res["rows"]) if a.period == "dev" else None
        reg = DbRegistry(conn)
        data_date = str(prices.index[-1].date())
        for r in res["rows"]:
            if r["benchmark"] or "error" in r:
                continue
            m = dict(r["cond"][cond_key(BASE)], **{f"ic_{k}": v for k, v in (r.get("ic") or {}).items()})
            m["conditions"] = {k: {kk: v.get(kk) for kk in ("liq_cagr", "mdd", "score", "trades")} for k, v in r["cond"].items()}
            reg.add(Experiment(r["id"], r["hypothesis"], {"group": r["group"], "rebalance": r["rebalance"], "plan": 59},
                               a.period, data_date, sha, _clean(m), False))
        conn.commit()
    for k, df in res.pop("daily").items():
        df.to_csv(out / f"daily-{a.period}-{k}.csv", index_label="date")
    meta = {"plan_issue": 59, "code_version": sha, "data_date": data_date, "period": a.period,
            "conditions": [cond_key(c) for c in CONDITIONS], "base": cond_key(BASE),
            "feature_first_dates": first_dates(mf, CLEAN_MARKET),
            "price_first_dates": {t: (str(prices[t].first_valid_index().date()) if t in prices else None)
                                  for t in ["SPY", "SHY", "SSO", "XLRE", "XLC"]},
            "dividend_days": int(div.notna().sum().sum()) if not div.empty else 0}
    md = table(res, a.period, elig)
    (out / f"forecast-{a.period}.md").write_text(md)
    (out / f"forecast-{a.period}.json").write_text(json.dumps({"meta": meta, **res, "eligibility": elig}, ensure_ascii=False,
                                                              default=str, indent=1))
    print(md)
    return 0 if any("error" not in r for r in res["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
