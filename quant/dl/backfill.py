"""딥러닝 트랙 시세 백필: python -m quant.dl.backfill --batch 40

Tiingo 무료 한도(시간당 50건·월 500종목) 안에서 한 번에 batch개만. 이미 받은 종목은 건너뛴다(manifest).
없는 종목(사라진 회사를 Tiingo가 안 줌)도 '없음'으로 기록해 0단계 자료 관문(계획 #74)에 쓴다.
"""
from __future__ import annotations

import argparse
import os
from datetime import date

import pandas as pd

from quant.ingest import sources as S
from quant.ingest.http import HttpError, requests_fetch

from . import members as M
from .store import R2, configured

START = date(1998, 1, 1)
END = date(2022, 12, 31)


def coverage(spells: list[M.Spell], manifest: dict, sample: list[str]) -> dict:
    """0단계: 표본 기호의 지수 구간 중 시세가 편출일(또는 2022 말)까지 있는 비율, 중간에 사라진 종목만 따로."""
    got = gone_got = gone = 0
    for t in sample:
        sp = [s for s in spells if s.ticker == t and s.start <= M.WINDOW[1] and (s.end or "9999") >= M.WINDOW[0]]
        need_end = max(min(s.end or M.WINDOW[1], M.WINDOW[1]) for s in sp)
        need_start = max(min(s.start for s in sp), M.WINDOW[0])
        info = manifest.get(t) or {}
        ok = bool(info.get("first") and info["first"] <= _plus(need_start, 31) and info.get("last") and info["last"] >= _minus(need_end, 31))
        got += ok
        if any(s.end and s.end <= M.WINDOW[1] for s in sp):
            gone += 1
            gone_got += ok
    n = len(sample)
    return {"n": n, "covered": got, "share": got / n if n else 0.0, "gone": gone, "gone_covered": gone_got,
            "gone_share": gone_got / gone if gone else 1.0}


def _plus(d: str, days: int) -> str:
    return str((pd.Timestamp(d) + pd.Timedelta(days=days)).date())


def _minus(d: str, days: int) -> str:
    return str((pd.Timestamp(d) - pd.Timedelta(days=days)).date())


def run(r2: R2, fetch, token: str, n: int = 200, batch: int = 40, log=print) -> dict:
    spells = M.fetch_spells(fetch)
    r2.put("members.csv", ("ticker,start_date,end_date\n" + "\n".join(f"{s.ticker},{s.start},{s.end or ''}" for s in spells)).encode())
    sample = M.sample(spells, n)
    manifest = r2.get_json("manifest.json", {}) or {}
    todo = [t for t in sample if t not in manifest][:batch]
    for t in todo:
        try:
            rows = S.tiingo_daily(fetch, t, START, END, token)
        except HttpError as e:
            msg = str(e)
            if "HTTP 429" in msg or "연결 실패" in msg or "재시도 초과" in msg or "HTTP 5" in msg:
                log(f"{t}: 한도·연결 문제로 멈춤 — 다음 실행에서 이어 받음")
                break
            manifest[t] = {"first": None, "last": None, "rows": 0, "error": str(e)[:120]}
            log(f"{t}: 없음 ({str(e)[:60]})")
            continue
        if not rows:
            manifest[t] = {"first": None, "last": None, "rows": 0}
            log(f"{t}: 0건")
            continue
        df = pd.DataFrame(rows)[["date", "open", "high", "low", "close", "adj_factor", "volume"]]
        r2.put_frame(f"prices/{t}.parquet", df)
        manifest[t] = {"first": df["date"].min(), "last": df["date"].max(), "rows": len(df)}
        log(f"{t}: {len(df)}건 {df['date'].min()}~{df['date'].max()}")
    r2.put_json("manifest.json", manifest)
    cov = coverage(spells, manifest, [t for t in sample if t in manifest])
    done = all(t in manifest for t in sample)
    r2.put_json("status.json", {"sample_n": n, "done": done, "fetched": sum(1 for t in sample if t in manifest), "coverage": cov,
                                "members_commit": M.COMMIT})
    log(f"진행 {sum(1 for t in sample if t in manifest)}/{n}, 관문 {cov}")
    return {"done": done, "coverage": cov}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--n", type=int, default=200)
    a = ap.parse_args()
    if not configured() or not os.environ.get("TIINGO_TOKEN"):
        print("R2 또는 TIINGO_TOKEN 없음 → 건너뜀")
        return 0
    run(R2(), requests_fetch(), os.environ["TIINGO_TOKEN"], a.n, a.batch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
