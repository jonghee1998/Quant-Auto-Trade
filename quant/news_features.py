"""뉴스를 숫자 특성으로. 규칙: 미국 동부 16:00 이후 기사는 다음 거래일 것. 유료 AI 없음.

감성 점수는 주입식(score_fn). 기본은 없음(NaN) — Loughran–McDonald 사전 등은 라이선스 확인 후 따로 넣는다.
휴장일 달력은 아직 반영하지 않는다(주말만 건너뜀).
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")
CLOSE = time(16, 0)


def session_date(published_at: str | datetime) -> date:
    """기사가 특성에 반영되는 거래일. 16:00 ET 이후·주말 기사는 다음 평일."""
    t = datetime.fromisoformat(published_at) if isinstance(published_at, str) else published_at
    if t.tzinfo is None:
        raise ValueError("published_at에 시간대가 없다")
    et = t.astimezone(ET)
    d = et.date() + (timedelta(days=1) if et.time() >= CLOSE else timedelta(0))
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


_NORM = re.compile(r"[\W_]+", re.UNICODE)


def norm_title(title: str) -> str:
    return _NORM.sub("", title.lower())


def dedupe(rows: Iterable[dict]) -> list[dict]:
    """같은 URL 또는 같은 거래일·종목의 같은 제목(기호·대소문자 무시)은 하나로."""
    seen_url: set[str] = set()
    seen_title: set[tuple] = set()
    out = []
    for r in rows:
        d = session_date(r["published_at"])
        tickers = tuple(sorted(r.get("tickers") or [""]))
        key = (d, tickers, norm_title(r["title"]))
        if r["url_hash"] in seen_url or key in seen_title:
            continue
        seen_url.add(r["url_hash"])
        seen_title.add(key)
        out.append({**r, "session_date": d})
    return out


def daily_features(rows: Iterable[dict], score_fn: Callable[[str], float] | None = None,
                   lookback: int = 60, half_life: float = 5.0) -> pd.DataFrame:
    """종목×거래일 특성: news_count, news_abn(오늘 건수 / 이전 lookback일 평균), news_sent, news_sent_decay.

    결과 인덱스는 (ticker, session_date). 이전 기록이 없으면 news_abn은 NaN.
    """
    recs = []
    for r in dedupe(rows):
        s = score_fn(r["title"]) if score_fn else float("nan")
        for t in r.get("tickers") or []:
            recs.append({"ticker": t, "session_date": pd.Timestamp(r["session_date"]), "sent": s})
    cols = ["news_count", "news_abn", "news_sent", "news_sent_decay"]
    if not recs:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(recs)
    g = df.groupby(["ticker", "session_date"]).agg(news_count=("sent", "size"), news_sent=("sent", "mean"))
    out = []
    for t, sub in g.groupby(level=0):
        sub = sub.droplevel(0)
        days = pd.bdate_range(sub.index.min(), sub.index.max())
        sub = sub.reindex(days)
        sub["news_count"] = sub["news_count"].fillna(0)
        prev = sub["news_count"].shift(1).rolling(lookback, min_periods=5).mean()
        sub["news_abn"] = sub["news_count"] / prev.where(prev > 0)
        sub["news_sent_decay"] = sub["news_sent"].fillna(0).ewm(halflife=half_life).mean() if score_fn else float("nan")
        sub = sub[sub["news_count"] > 0]
        sub.index = pd.MultiIndex.from_product([[t], sub.index], names=["ticker", "session_date"])
        out.append(sub[cols])
    return pd.concat(out)
