"""4차(계획 #73): 국내 상장 ETF 합성 시세(원화). 과거 방향 계산만 쓴다(그날까지의 값으로 그날 값).

- KSPX_U(환노출 S&P) = SPY 수정주가 × 원/달러 × 보수 차감(연 0.10%p)
- KSPX_H(환헤지 S&P): 일수익 = SPY 달러 수익 + (한국 3개월 − 미국 3개월 금리)/252 − 연 0.30%p/252
- KUST_U(미국 단기채·환노출) = SHY × 원/달러 × 보수 차감(연 0.10%p)
- KRWCASH(원화 현금): 일수익 = 한국 3개월 금리/252
금리는 '그날 이전에 발표된 가장 최근 값'(features.asof_series)으로 넘겨받는다(% 단위).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

KRW_ASSETS = frozenset({"KSPX_U", "KSPX_H", "KUST_U", "KRWCASH"})


def _drag(idx: pd.DatetimeIndex, fee: float) -> pd.Series:
    t = (idx - idx[0]).days / 365.25
    return pd.Series(np.exp(-fee * np.asarray(t)), index=idx)


def build(prices: pd.DataFrame, fx: pd.Series, kr3m: pd.Series, us3m: pd.Series) -> pd.DataFrame:
    """prices: 달러 수정주가(SPY·SHY), fx: 원/달러(기준일), kr3m·us3m: 날짜별 알 수 있던 금리(%). 반환: 원화 합성 시세."""
    idx = prices.index
    f = fx.reindex(idx).ffill()
    out = pd.DataFrame(index=idx)
    spy = prices["SPY"]
    ok = spy.notna() & f.notna()
    out["KSPX_U"] = (spy * f * _drag(idx, 0.001)).where(ok)
    if "SHY" in prices:
        out["KUST_U"] = (prices["SHY"] * f * _drag(idx, 0.001)).where(prices["SHY"].notna() & f.notna())
    k, u = kr3m.reindex(idx).ffill() / 100, us3m.reindex(idx).ffill() / 100
    r = spy.pct_change(fill_method=None) + (k - u) / 252 - 0.003 / 252
    first = (spy.notna() & k.notna() & u.notna())
    if first.any():
        s = first.idxmax()
        h = (1 + r.loc[s:].fillna(0.0)).cumprod() * 100.0
        h.iloc[0] = 100.0
        out["KSPX_H"] = h.reindex(idx).where(spy.notna())
        c = (1 + (k.loc[s:] / 252).fillna(0.0)).cumprod() * 100.0
        out["KRWCASH"] = c.reindex(idx)
    return out


def tracking_gap(synth: pd.Series, real: pd.Series) -> dict:
    """합성과 실제 국내 ETF의 연 추적 차이(같은 날만, 로그 수익 차의 연 평균·연 표준편차)."""
    df = pd.concat([synth, real], axis=1, keys=["s", "r"]).dropna()
    if len(df) < 30:
        return {"n": len(df), "gap": None, "te": None}
    d = np.log(df).diff().dropna()
    x = d["s"] - d["r"]
    return {"n": len(df), "gap": float(x.mean() * 252), "te": float(x.std() * np.sqrt(252)),
            "from": str(df.index[0].date()), "to": str(df.index[-1].date())}
