"""S&P 500 과거 구성종목(공개, MIT): GitHub fja05680/sp500 의 sp500_ticker_start_end.csv — 특정 커밋으로 고정.

표본: 2003-01-01~2022-12-31 사이 한 번이라도 지수에 있었던 종목에서, 기호의 SHA-256 앞 8자리 오름차순으로 N개(계획 #74).
성적과 무관한 순서라 생존 편향이 없다. 같은 기호를 다른 회사가 다시 쓴 경우는 기간(구간)마다 따로 기록한다.
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass

from quant.ingest.http import Fetch, get_text

COMMIT = "a2430f2af0c79ddf0748e91de11bdeb1616ab5a7"
URL = f"https://raw.githubusercontent.com/fja05680/sp500/{COMMIT}/sp500_ticker_start_end.csv"
WINDOW = ("2003-01-01", "2022-12-31")


@dataclass(frozen=True)
class Spell:
    ticker: str
    start: str
    end: str | None   # None = 아직 지수 안


def parse(text: str) -> list[Spell]:
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        t = (r.get("ticker") or "").strip().upper()
        if t:
            out.append(Spell(t, r["start_date"].strip(), (r.get("end_date") or "").strip() or None))
    return out


def fetch_spells(fetch: Fetch) -> list[Spell]:
    return parse(get_text(fetch, URL, source="sp500_members"))


def key(ticker: str) -> str:
    return hashlib.sha256(ticker.encode()).hexdigest()[:8]


def sample(spells: list[Spell], n: int = 200, window: tuple[str, str] = WINDOW) -> list[str]:
    """구간이 window와 겹치는 기호에서 해시 순 n개."""
    tick = sorted({s.ticker for s in spells if s.start <= window[1] and (s.end or "9999-12-31") >= window[0]}, key=key)
    return tick[:n]


def members_on(spells: list[Spell], day: str) -> set[str]:
    """그날 지수 구성종목(편입일부터, 편출일 전날까지)."""
    return {s.ticker for s in spells if s.start <= day and (s.end is None or day < s.end)}
