"""시장 화면용 계산: 추세 신호등, 업종 폭, 상대강도, 평소 대비 움직임. 입력은 날짜×종목 종가(수정주가)."""
from __future__ import annotations

import pandas as pd


def trend_light(close: pd.Series, window: int = 200) -> dict:
    """마지막 날 종가가 window일 평균선 위면 green. gap_pct = 평균선 대비 %. 데이터가 모자라면 state=None."""
    s = close.dropna()
    if len(s) < window:
        return {"state": None, "gap_pct": None}
    ma = s.rolling(window).mean().iloc[-1]
    gap = (s.iloc[-1] / ma - 1) * 100
    return {"state": "green" if gap >= 0 else "red", "gap_pct": float(gap)}


def breadth(prices: pd.DataFrame, window: int = 200) -> dict:
    """마지막 날 window일 평균선 위에 있는 종목 수 / 계산 가능한 종목 수."""
    above = total = 0
    for col in prices.columns:
        light = trend_light(prices[col], window)
        if light["state"] is None:
            continue
        total += 1
        above += light["state"] == "green"
    return {"above": above, "total": total}


def period_returns(prices: pd.DataFrame, days=(21, 63, 126)) -> pd.DataFrame:
    """종목별 1·3·6개월(거래일 21·63·126) 수익률(%). 데이터가 모자란 칸은 NaN."""
    out = {}
    for d in days:
        out[d] = (prices.iloc[-1] / prices.shift(d).iloc[-1] - 1) * 100 if len(prices) > d else pd.Series(float("nan"), index=prices.columns)
    return pd.DataFrame(out)


def relative_strength(prices: pd.DataFrame, bench: pd.Series, days: int = 63) -> pd.Series:
    """기준선 대비 초과수익(%p) — 클수록 시장보다 강함."""
    r = period_returns(prices, (days,))[days]
    b = period_returns(bench.to_frame("b"), (days,))[days].iloc[0]
    return r - b


def move_z(close: pd.Series, lookback: int = 60) -> dict:
    """오늘 변화(%)와 평소 하루 움직임(최근 lookback일 표준편차, 오늘 제외) 대비 배수."""
    r = close.dropna().pct_change(fill_method=None).dropna() * 100
    if len(r) < lookback + 1:
        return {"change": None, "std": None, "z": None}
    today, hist = r.iloc[-1], r.iloc[-lookback - 1:-1]
    std = float(hist.std())
    return {"change": float(today), "std": std, "z": float(today / std) if std > 0 else None}
