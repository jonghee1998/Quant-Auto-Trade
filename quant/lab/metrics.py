"""성과 지표: 모두 원화 평가액(세금 반영) 기준."""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def cagr(nav: pd.Series) -> float:
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    if years <= 0 or nav.iloc[0] <= 0:
        return float("nan")
    return float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1)


def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1).min())


def sharpe(nav: pd.Series) -> float:
    r = nav.pct_change(fill_method=None).dropna()
    if len(r) < 2 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(TRADING_DAYS))


def monthly_win_rate(nav: pd.Series, bench: pd.Series) -> float:
    """기준선보다 월 수익률이 높았던 달의 비율."""
    a = nav.resample("ME").last().pct_change(fill_method=None).dropna()
    b = bench.resample("ME").last().pct_change(fill_method=None).dropna()
    a, b = a.align(b, join="inner")
    return float((a > b).mean()) if len(a) else float("nan")


def _monthly(nav: pd.Series) -> pd.Series:
    return nav.resample("ME").last().pct_change(fill_method=None).dropna()


def capture_ratios(nav: pd.Series, bench: pd.Series) -> tuple[float, float]:
    """(상승 포착률, 하락 포착률). 기준선이 오른 달/내린 달만 모아 기하평균 수익을 비교.

    하락 포착률 0.6 = 기준선이 내린 달에 평균 60%만 따라 빠짐(낮을수록 '잃을 땐 조금').
    """
    a, b = _monthly(nav).align(_monthly(bench), join="inner")

    def ratio(mask: pd.Series) -> float:
        if not mask.any():
            return float("nan")
        ga = (1 + a[mask]).prod() ** (1 / mask.sum()) - 1
        gb = (1 + b[mask]).prod() ** (1 / mask.sum()) - 1
        return float(ga / gb) if gb != 0 else float("nan")

    return ratio(b > 0), ratio(b < 0)


def recovery_days(nav: pd.Series) -> float:
    """최대 낙폭의 고점에서 그 고점을 다시 넘을 때까지 달력 일수. 아직 회복 못 했으면 nan."""
    dd = nav / nav.cummax() - 1
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    after = nav.loc[trough:]
    back = after[after >= nav.loc[peak]]
    return float((back.index[0] - peak).days) if len(back) else float("nan")


def sortino(nav: pd.Series) -> float:
    r = nav.pct_change(fill_method=None).dropna()
    down = np.sqrt((np.minimum(r, 0) ** 2).mean())
    return float(r.mean() / down * np.sqrt(TRADING_DAYS)) if down > 0 else float("nan")


def calmar(nav: pd.Series) -> float:
    m = max_drawdown(nav)
    return float(cagr(nav) / abs(m)) if m < 0 else float("nan")


def ulcer_index(nav: pd.Series) -> float:
    """낙폭(%)의 제곱평균제곱근. 깊고 오래 빠질수록 커진다."""
    dd = (nav / nav.cummax() - 1) * 100
    return float(np.sqrt((dd ** 2).mean()))


def deflated_sharpe(nav: pd.Series, n_trials: int, trial_sharpe_var: float | None = None) -> float:
    """Deflated Sharpe Ratio (Bailey & López de Prado 2014): 시도 n번 중 최고가 우연일 가능성을 반영한 확률.

    0.95 이상이면 '운 아님'으로 본다. Sharpe는 기간(일) 단위로 계산한다.
    trial_sharpe_var: 시도들의 (일 단위) Sharpe 분산. 모르면 1/T(귀무가설 하 근사)로 둔다.
    """
    r = nav.pct_change(fill_method=None).dropna()
    t = len(r)
    if t < 3 or r.std() == 0 or n_trials < 1:
        return float("nan")
    sr = float(r.mean() / r.std())
    skew = float(r.skew())
    kurt = float(r.kurt()) + 3.0  # 초과첨도 → 첨도
    nd = NormalDist()
    var = trial_sharpe_var if trial_sharpe_var is not None else 1.0 / t
    if n_trials == 1:
        sr0 = 0.0
    else:
        g = 0.5772156649
        sr0 = math.sqrt(var) * ((1 - g) * nd.inv_cdf(1 - 1 / n_trials) + g * nd.inv_cdf(1 - 1 / (n_trials * math.e)))
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr ** 2, 1e-12))
    return float(nd.cdf((sr - sr0) * math.sqrt(t - 1) / denom))


def deflated_sharpe_excess(nav: pd.Series, bench: pd.Series, n_trials: int, trial_var: float | None = None) -> float:
    """S&P 대비 DSR: 날마다 (전략 수익 − S&P 수익)으로 계산(Fable 판정 #57 — 0 대비가 아니라 S&P 대비)."""
    ex = (nav.pct_change(fill_method=None) - bench.pct_change(fill_method=None)).dropna()
    return deflated_sharpe((1 + ex).cumprod(), n_trials, trial_var)


def excess_sharpe(nav: pd.Series, bench: pd.Series) -> float:
    """일 단위 (전략 − S&P) 수익의 평균 ÷ 표준편차. 묶음 전체 분산 계산용."""
    ex = (nav.pct_change(fill_method=None) - bench.pct_change(fill_method=None)).dropna()
    return float(ex.mean() / ex.std()) if len(ex) > 2 and ex.std() > 0 else float("nan")


def beta_adjusted_alpha(nav: pd.Series, market: pd.Series, safe: pd.Series, lags: int = 5) -> dict:
    """일별 (전략 − 단기채) = α + β × (S&P − 단기채) + 잔차 (계획 #66). 셋 다 같은 통화(원화) 평가액.
    반환: 연 α(×252), β, Newey-West(지연 lags) t값, 일별 '알파 수익'(α + 잔차) 시계열, 관측 수."""
    df = pd.concat([nav, market, safe], axis=1, keys=["s", "m", "f"]).dropna().pct_change(fill_method=None).dropna()
    nanres = {"alpha": float("nan"), "beta": float("nan"), "t": float("nan"), "resid": pd.Series(dtype=float), "n": len(df)}
    if len(df) < 30:
        return nanres
    y = (df["s"] - df["f"]).to_numpy()
    x = (df["m"] - df["f"]).to_numpy()
    X = np.column_stack([np.ones_like(x), x])
    xtx_inv = np.linalg.pinv(X.T @ X)
    b = xtx_inv @ X.T @ y
    e = y - X @ b
    # Newey-West(Bartlett 가중) 공분산
    u = X * e[:, None]
    S = u.T @ u
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = u[L:].T @ u[:-L]
        S += w * (G + G.T)
    cov = xtx_inv @ S @ xtx_inv
    se = math.sqrt(max(cov[0, 0], 0.0))
    resid = pd.Series(b[0] + e, index=df.index)
    return {"alpha": float(b[0] * TRADING_DAYS), "beta": float(b[1]), "t": float(b[0] / se) if se > 0 else float("nan"),
            "resid": resid, "n": len(df)}


def alpha_sharpe(resid: pd.Series) -> float:
    """알파 수익(α + 잔차)의 일 단위 샤프 — 묶음 전체 분산 계산용."""
    return float(resid.mean() / resid.std()) if len(resid) > 2 and resid.std() > 0 else float("nan")


def deflated_sharpe_alpha(resid: pd.Series, n_trials: int, trial_var: float | None = None) -> float:
    """베타 보정 알파 기준 DSR: 주식을 덜 든 만큼은 빼고, 남는 수익이 우연인지(계획 #66)."""
    if len(resid) < 3:
        return float("nan")
    return deflated_sharpe((1 + resid).cumprod(), n_trials, trial_var)


def liquidated_cagr(after_tax: float, capital: float, nav: pd.Series) -> float:
    """마지막 날 다 팔고 세금까지 낸 금액 기준 연수익."""
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    return float((after_tax / capital) ** (1 / years) - 1) if years > 0 and after_tax > 0 else float("nan")


def drawdown_in(nav: pd.Series, start: str, end: str) -> float:
    """한 구간 안 최악 손실(구간 시작 직전 고점 기준이 아니라 구간 안에서만)."""
    s = nav.loc[start:end]
    return float((s / s.cummax() - 1).min()) if len(s) > 1 else float("nan")


def cagr_excluding(nav: pd.Series, start: str, end: str) -> float:
    """start~end 구간을 뺀 연수익: 날짜를 지우지 않고 남은 날의 일수익을 이어 붙인다(구간 앞뒤 값의 차이가 수익으로 새지 않게, 판정 #88)."""
    r = nav.pct_change(fill_method=None).dropna()
    keep = r.drop(r.loc[start:end].index)
    if len(keep) < 2:
        return float("nan")
    return float((1 + keep).prod() ** (TRADING_DAYS / len(keep)) - 1)


def max_drawdown_usd(nav_krw: pd.Series, fx: pd.Series) -> float:
    """원화 평가액을 그날 환율로 달러로 바꾼 뒤의 최악 손실(환율 덕을 뺀 손실)."""
    f = fx.reindex(nav_krw.index).ffill()
    return max_drawdown((nav_krw / f).dropna())


def summary(nav: pd.Series, bench: pd.Series) -> dict:
    return {
        "cagr": cagr(nav),
        "mdd": max_drawdown(nav),
        "sharpe": sharpe(nav),
        "bench_cagr": cagr(bench),
        "bench_mdd": max_drawdown(bench),
        "excess_cagr": cagr(nav) - cagr(bench),
        "monthly_win_rate": monthly_win_rate(nav, bench),
        "up_capture": (cap := capture_ratios(nav, bench))[0],
        "down_capture": cap[1],
        "recovery_days": recovery_days(nav),
        "bench_recovery_days": recovery_days(bench),
        "sortino": sortino(nav),
        "calmar": calmar(nav),
        "ulcer": ulcer_index(nav),
        "bench_ulcer": ulcer_index(bench),
    }
