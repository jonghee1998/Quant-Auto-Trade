"""실험실 실행기: python -m quant.lab.cli <전략> [--period dev|valid] [--issue N]

DB(DATABASE_URL)에서 미국 ETF 수정종가와 원/달러(FRED DEXKOUS)를 읽어 evaluate를 돌리고 experiments 표에 기록한다.
홀드아웃(final)은 이 명령으로 돌리지 않는다(사람이 따로 승인). 결과 요약을 markdown으로 출력한다.
"""
from __future__ import annotations

import argparse
import os
import subprocess

import pandas as pd

from quant.strategies import REGISTRY

from .registry import DbRegistry
from .run import evaluate


def load_prices(conn) -> tuple[pd.DataFrame, pd.Series]:
    with conn.cursor() as cur:
        cur.execute("""select i.code, p.date, p.close * p.adj_factor from prices_daily p join instruments i on i.id = p.instrument_id
                       where i.market = 'US'""")
        px = pd.DataFrame(cur.fetchall(), columns=["code", "date", "close"])
        cur.execute("""select distinct on (ref_date) ref_date, value from macro_series where series = 'DEXKOUS'
                       order by ref_date, release_date desc""")
        fx = pd.DataFrame(cur.fetchall(), columns=["date", "value"])
    prices = px.pivot(index="date", columns="code", values="close").sort_index()
    prices.index = pd.to_datetime(prices.index)
    fxs = fx.set_index(pd.to_datetime(fx["date"]))["value"].sort_index()
    return prices, fxs


def div_yield_from_factors(df: pd.DataFrame, max_jump: float = 0.05) -> pd.DataFrame:
    """(code, date, adj_factor) → 날짜×종목 배당률. 수정계수(수정종가÷종가)가 하루에 r만큼 오르면 그날이 배당락(배당률 r).
    하루 조정폭이 max_jump를 넘으면 분할 등으로 보고 버린다(계획 #59). 배당이 없는 날은 칸이 비어 있다."""
    if df.empty:
        return pd.DataFrame()
    f = df.pivot(index="date", columns="code", values="adj_factor").sort_index()
    f.index = pd.to_datetime(f.index)
    r = f / f.shift(1) - 1
    return r.where((r > 1e-6) & (r <= max_jump)).dropna(how="all")


def load_div_yield(conn) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute("""select i.code, p.date, p.adj_factor from prices_daily p join instruments i on i.id = p.instrument_id
                       where i.market = 'US' and p.adj_factor is not null""")
        df = pd.DataFrame(cur.fetchall(), columns=["code", "date", "adj_factor"])
    df["adj_factor"] = df["adj_factor"].astype(float)
    return div_yield_from_factors(df)


def card(name: str, period: str, m: dict) -> str:
    def p(v, d=1):
        return "—" if v is None or v != v else f"{v * 100:+.{d}f}%"
    def x(v, d=2):
        return "—" if v is None or v != v else f"{v:.{d}f}"
    return "\n".join([
        f"### 실험 결과 · `{name}` · {period}",
        "| | 이 전략 | S&P 그냥 보유 |", "|---|---|---|",
        f"| 연 수익(세후 전) | {p(m.get('cagr'))} | {p(m.get('bench_cagr'))} |",
        f"| 최악 손실 | {p(m.get('mdd'), 0)} | {p(m.get('bench_mdd'), 0)} |",
        f"| 회복까지(일) | {x(m.get('recovery_days'), 0)} | {x(m.get('bench_recovery_days'), 0)} |",
        f"| 오른 달 따라감 / 내린 달 빠짐 | {x(m.get('up_capture'))} / {x(m.get('down_capture'))} | 1.00 / 1.00 |",
        f"| 끝까지 들고 판 뒤 세후(원) | {x(m.get('after_tax_if_liquidated'), 0)} | {x(m.get('bench_after_tax_if_liquidated'), 0)} |",
        "", f"시도 {m.get('n_trials')}번째 · 우연 보정(DSR) {x(m.get('dsr'))} (0.95 이상 통과) · 매매 {m.get('trades')}회",
    ])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy", choices=sorted(REGISTRY))
    ap.add_argument("--period", choices=["dev", "valid"], default="dev")
    a = ap.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL 없음 → 실행 안 함")
        return 0
    import psycopg
    make, hypothesis, params = REGISTRY[a.strategy]
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    with psycopg.connect(url) as conn:
        prices, fx = load_prices(conn)
        if prices.empty or fx.empty:
            print("시세 또는 환율이 아직 없음 → 실행 안 함")
            return 0
        m = evaluate(prices, fx, make(), hypothesis=hypothesis, params=params, period=a.period,
                     registry=DbRegistry(conn), data_version=str(prices.index[-1].date()), code_version=sha)
    print(card(a.strategy, a.period, m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
