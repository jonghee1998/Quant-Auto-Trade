"""예측 특성·라벨(시점 기준). 모든 특성은 그날 장 마감까지 공개된 값만 쓴다.

- 가격 특성: rolling은 과거 방향만(center 없음). 테스트가 '그날까지 자른 가격으로 다시 계산해도 같은 값'을 확인한다.
- 지표(FRED): 값마다 발표일(release_date)이 있다. 날짜 d의 값 = 발표일 ≤ d 인 것 중 가장 최근 기준일 값.
- 라벨(앞으로 h거래일 수익): 학습에만 쓴다. 학습 표본은 '라벨 끝 날짜 + embargo ≤ 오늘'인 것만(purge).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 가격 특성(종목별)
PRICE_FEATS = ["r5", "r21", "r63", "r126", "r252", "r12_1", "vol21", "vol63", "dd252", "ma50", "ma200", "rsi14",
               "beta63", "rel21", "rel63", "skew63", "rev5_vol"]
SWING_FEATS = ["r5", "r21", "vol21", "rsi14", "ma50", "rel21", "rev5_vol", "dd252", "r63"]


def _rsi(px: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    d = px.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def price_panel(px: pd.DataFrame, bench: str = "SPY") -> dict[str, pd.DataFrame]:
    """특성 이름 → (날짜 × 종목) 표. 모두 과거만 본다."""
    r = px.pct_change(fill_method=None)
    out = {f"r{n}": px / px.shift(n) - 1 for n in (5, 21, 63, 126, 252)}
    out["r12_1"] = px.shift(21) / px.shift(252) - 1
    out["vol21"] = r.rolling(21, min_periods=15).std() * np.sqrt(252)
    out["vol63"] = r.rolling(63, min_periods=40).std() * np.sqrt(252)
    out["dd252"] = px / px.rolling(252, min_periods=126).max() - 1
    out["ma50"] = px / px.rolling(50, min_periods=40).mean() - 1
    out["ma200"] = px / px.rolling(200, min_periods=150).mean() - 1
    out["rsi14"] = _rsi(px)
    b = r[bench] if bench in r else r.mean(axis=1)
    cov = r.rolling(63, min_periods=40).cov(b)
    out["beta63"] = cov.div(b.rolling(63, min_periods=40).var(), axis=0)
    out["rel21"] = out["r21"].sub(out["r21"][bench], axis=0) if bench in px else out["r21"]
    out["rel63"] = out["r63"].sub(out["r63"][bench], axis=0) if bench in px else out["r63"]
    out["skew63"] = r.rolling(63, min_periods=40).skew()
    out["rev5_vol"] = out["r5"] / out["vol21"].replace(0, np.nan)  # 단기 되돌림(변동성 대비)
    return out


# ---------------------------------------------------------------- 지표(날짜별, 모든 종목 공통)
def asof_series(rows: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.Series:
    """rows: ref_date, release_date, value(한 지표). 날짜 d에 알 수 있던 가장 최근 기준일 값."""
    if rows.empty:
        return pd.Series(np.nan, index=dates)
    r = rows.dropna(subset=["value"]).copy()
    r["release_date"] = pd.to_datetime(r["release_date"])
    r["ref_date"] = pd.to_datetime(r["ref_date"])
    # 발표일 순으로 쌓으며, 그때까지 나온 것 중 기준일이 가장 늦은 값
    r = r.sort_values(["release_date", "ref_date"])
    r["best_ref"] = r["ref_date"].cummax()
    r = r[r["ref_date"] == r["best_ref"]].drop_duplicates("release_date", keep="last")
    s = r.set_index("release_date")["value"].sort_index()
    return s.reindex(s.index.union(dates)).ffill().reindex(dates)


def _z(s: pd.Series, n: int = 252) -> pd.Series:
    m, sd = s.rolling(n, min_periods=n // 2).mean(), s.rolling(n, min_periods=n // 2).std()
    return (s - m) / sd.replace(0, np.nan)


MACRO_FEATS = ["vix", "vix_term", "hy", "hy_ch21", "ig_ch21", "curve_2y", "curve_3m", "dgs10_ch21", "real10", "infl5",
               "usd_ch63", "oil_ch63", "nfci", "stress", "claims_yoy", "sahm", "sent_z", "epu_z", "emv_z", "krw_ch21"]
NEWS_FEATS = ["epu_z", "emv_z"]  # 신문 기사 기반(Baker·Bloom·Davis) — 2005년부터 있는 뉴스 재료


def macro_panel(macro: dict[str, pd.DataFrame], dates: pd.DatetimeIndex) -> pd.DataFrame:
    """macro: 지표 이름 → (ref_date, release_date, value) 표. 반환: 날짜 × 특성(발표일 기준)."""
    g = {k: asof_series(v, dates) for k, v in macro.items()}
    nan = pd.Series(np.nan, index=dates)
    s = lambda k: g.get(k, nan)  # noqa: E731
    f = pd.DataFrame(index=dates)
    f["vix"] = s("VIXCLS")
    f["vix_term"] = s("VIXCLS") / s("VXVCLS")
    f["hy"] = s("BAMLH0A0HYM2")
    f["hy_ch21"] = f["hy"] - f["hy"].shift(21)
    f["ig_ch21"] = s("BAMLC0A0CM") - s("BAMLC0A0CM").shift(21)
    f["curve_2y"] = s("T10Y2Y")
    f["curve_3m"] = s("T10Y3M")
    f["dgs10_ch21"] = s("DGS10") - s("DGS10").shift(21)
    f["real10"] = s("DFII10")
    f["infl5"] = s("T5YIE")
    f["usd_ch63"] = s("DTWEXBGS") / s("DTWEXBGS").shift(63) - 1
    f["oil_ch63"] = s("DCOILWTICO") / s("DCOILWTICO").shift(63) - 1
    f["nfci"] = s("NFCI")
    f["stress"] = s("STLFSI4")
    f["claims_yoy"] = s("ICSA") / s("ICSA").shift(252) - 1
    f["sahm"] = s("SAHMREALTIME")
    f["sent_z"] = _z(s("UMCSENT"))
    f["epu_z"] = _z(np.log(s("USEPUINDXD").rolling(21, min_periods=10).mean()))
    f["emv_z"] = _z(np.log(s("WLEMUINDXD").rolling(21, min_periods=10).mean()))
    f["krw_ch21"] = s("DEXKOUS") / s("DEXKOUS").shift(21) - 1
    return f.replace([np.inf, -np.inf], np.nan)


# ---------------------------------------------------------------- 표본 만들기
def forward_return(px: pd.DataFrame, h: int) -> pd.DataFrame:
    """라벨 전용: 날짜 t 종가에서 t+h 종가까지 수익. 특성에 절대 쓰지 않는다."""
    return px.shift(-h) / px - 1


def stack(feats: dict[str, pd.DataFrame], dates: pd.DatetimeIndex, tickers: list[str]) -> pd.DataFrame:
    """(날짜, 종목) × 특성. 날짜마다 종목 간 백분위 순위로 바꾼다(시기마다 크기 차이를 없앰)."""
    cols = {}
    for k, t in feats.items():
        cols[k] = t.reindex(index=dates, columns=tickers).rank(axis=1, pct=True).stack(future_stack=True)
    return pd.DataFrame(cols)


def training_dates(index: pd.DatetimeIndex, as_of: pd.Timestamp, h: int, embargo: int = 5, step: int = 5,
                   years: float | None = None) -> pd.DatetimeIndex:
    """학습 표본 날짜: 라벨 끝(t+h)이 as_of보다 embargo일 이상 앞선 날만(purge), step일 간격(겹침 줄이기)."""
    pos = index.get_indexer([as_of], method="pad")[0]
    last = pos - h - embargo
    if last <= 0:
        return index[:0]
    first = 0
    if years is not None:
        first = max(0, index.searchsorted(index[last] - pd.Timedelta(days=int(years * 365.25))))
    return index[first:last + 1][::-1][::step][::-1]
