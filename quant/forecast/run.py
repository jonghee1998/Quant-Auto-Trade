"""예측 실험 일괄 실행: python -m quant.forecast.run --period dev [--ids C01,C02] [--out lab-out]

DB에서 미국 ETF 수정종가·원/달러·지표(발표일 포함)를 읽어 실험마다 quant.lab.evaluate(다음 날 체결·비용·환전·세금·기준선)로
돌리고 experiments 표에 기록한다(시도 수가 쌓여 DSR에 반영). 홀드아웃은 여기서 돌리지 않는다.
결과는 markdown 표(작업 요약)와 JSON 파일로 남긴다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import pandas as pd

from quant.lab.cli import load_prices
from quant.lab.registry import DbRegistry
from quant.lab.run import evaluate

from .experiments import EXPERIMENTS, MACRO_SERIES
from .features import macro_panel


def load_macro(conn, series: list[str]) -> dict[str, pd.DataFrame]:
    with conn.cursor() as cur:
        cur.execute("select series, ref_date, release_date, value from macro_series where series = any(%s)", (series,))
        df = pd.DataFrame(cur.fetchall(), columns=["series", "ref_date", "release_date", "value"])
    return {k: g.drop(columns="series") for k, g in df.groupby("series")}


def score(m: dict) -> float:
    """검증 구간에 올릴 후보 순서: 세후 전 연수익 차이 + 최악 손실 개선의 절반(잃을 땐 조금, 벌 땐 많이)."""
    ex = (m.get("cagr") or 0) - (m.get("bench_cagr") or 0)
    dd = (m.get("mdd") or 0) - (m.get("bench_mdd") or 0)  # 둘 다 음수: 덜 빠지면 양수
    return ex + 0.5 * dd


def table(rows: list[dict], period: str) -> str:
    p = lambda v, d=1: "—" if v is None else f"{v * 100:+.{d}f}%"  # noqa: E731
    x = lambda v, d=2: "—" if v is None else f"{v:.{d}f}"  # noqa: E731
    out = [f"### 실험실 1차 · 예측 기반 {len(rows)}개 · {period}", "",
           "| 실험 | 묶음 | 연수익 | S&P | 최악 손실 | S&P | 오른 달/내린 달 | 회복(일) | 매매 | 예측력 | DSR | 점수 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -r["score"]):
        m = r["m"]
        ic = r.get("ic") or {}
        pred = (f"IC {ic['ic_mean']:+.3f} (t {ic['ic_t']:.1f})" if ic.get("ic_mean") is not None
                else f"적중 {ic['hit'] * 100:.0f}%/기본 {ic['base_rate'] * 100:.0f}%" if ic.get("hit") is not None else "—")
        out.append(f"| {r['id']} | {r['group']} | {p(m.get('cagr'))} | {p(m.get('bench_cagr'))} | {p(m.get('mdd'), 0)} | "
                   f"{p(m.get('bench_mdd'), 0)} | {x(m.get('up_capture'))}/{x(m.get('down_capture'))} | {x(m.get('recovery_days'), 0)} | "
                   f"{m.get('trades')} | {pred} | {x(m.get('dsr'))} | {r['score'] * 100:+.1f} |")
    n = max((r["m"].get("n_trials") or 0) for r in rows) if rows else 0
    out += ["", f"누적 시도 {n}번(DSR 보정에 반영). 연수익은 세금 전(연말 실현 세금은 반영), 비용·환전 포함. "
            "IC = 예측 순위와 실제 다음 기간 초과수익 순위의 상관(0.03 이상이면 쓸모, t 2 이상이면 우연 아닐 가능성)."]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["dev", "valid"], default="dev")
    ap.add_argument("--ids", default="", help="쉼표로 고르기(빈칸=30개 전부)")
    ap.add_argument("--out", default="lab-out")
    a = ap.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL 없음 → 실행 안 함")
        return 0
    import psycopg
    pick = {s.strip() for s in a.ids.split(",") if s.strip()}
    exps = [e for e in EXPERIMENTS if not pick or e.id in pick]
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    Path(a.out).mkdir(parents=True, exist_ok=True)
    rows = []
    with psycopg.connect(url) as conn:
        prices, fx = load_prices(conn)
        prices = prices.loc[:, [c for c in prices.columns if prices[c].notna().any()]]
        mf = macro_panel(load_macro(conn, MACRO_SERIES), prices.index)
        reg = DbRegistry(conn)
        for e in exps:
            t0 = time.time()
            try:
                strat = e.build(prices, mf)
                m = evaluate(prices, fx, strat, hypothesis=e.hypothesis, params={"group": e.group, "rebalance": e.rebalance},
                             period=a.period, registry=reg, data_version=str(prices.index[-1].date()), code_version=sha,
                             rebalance=e.rebalance, extra=getattr(strat, "ic", None))
                conn.commit()
                ic = {k: m.get(k) for k in ("ic_mean", "ic_t", "ic_n", "brier", "hit", "base_rate") if k in m}
                rows.append({"id": e.id, "group": e.group, "hypothesis": e.hypothesis, "m": m, "ic": ic, "score": score(m)})
                print(f"{e.id}: 연수익 {m['cagr'] * 100:+.1f}% (S&P {m['bench_cagr'] * 100:+.1f}%), 최악 {m['mdd'] * 100:.0f}% "
                      f"({time.time() - t0:.0f}초)", flush=True)
            except Exception as ex:  # noqa: BLE001 — 한 실험 실패가 나머지를 막지 않는다
                conn.rollback()
                print(f"{e.id}: 실패 {type(ex).__name__}: {ex}", flush=True)
    md = table(rows, a.period)
    Path(a.out, f"forecast-{a.period}.md").write_text(md)
    Path(a.out, f"forecast-{a.period}.json").write_text(json.dumps(rows, ensure_ascii=False, default=str, indent=1))
    print(md)
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
