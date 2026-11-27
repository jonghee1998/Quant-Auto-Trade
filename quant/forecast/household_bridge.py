"""6차 R6_K1(보고): 실제 국내 S&P ETF 시세로 A4 구조를 계산해도 합성으로 계산한 것과 구조 몫 차이가 연 0.3%p 안이고 부호가 같은가.
분배금 자료가 없어 둘 다 '가격끼리'(실제 종가 vs KSPX_P)로 맞춘다. 차이와 부호만 낸다(수준은 안 냄)."""
from __future__ import annotations

import pandas as pd

from quant.lab.household import PLANS, Costs5, irr, simulate

from .round5 import KRW5
from .rules5 import Hold, IsaPlus
from .synthetic import align_kr

WIN = ("2021-01-04", "2022-12-30")


def k1_report(px: pd.DataFrame, fx: pd.Series, div, real: pd.Series, synth_p: pd.Series) -> dict:
    out = {}
    real_al = real.reindex(px.index).ffill()  # 한국 종가를 그 날짜 줄에(미국 날짜 기준) — 실제 시세 계산용
    syn_al = synth_p
    for plan in ("P150", "L1억"):
        res = {}
        for name, series in (("실제", real_al), ("합성", syn_al)):
            p = px.copy()
            p["KSPX_N"] = series
            a = simulate(p, fx, IsaPlus("A4", {"KSPX_N": 1.0}, {"SPY": 1.0}, years=5), PLANS[plan], WIN[0], WIN[1], costs=Costs5(), krw=KRW5,
                         div_yield=div)
            b = simulate(p, fx, Hold("B00", "foreign", {"SPY": 1.0}), PLANS[plan], WIN[0], WIN[1], costs=Costs5(), krw=KRW5, div_yield=div)
            res[name] = irr(a.flows, a.endings["E10"]) - irr(b.flows, b.endings["E10"])
        d = res["실제"] - res["합성"]
        out[plan] = {"차이(실제−합성, 연)": round(d * 100, 3), "부호 같음": (res["실제"] >= 0) == (res["합성"] >= 0),
                     "괜찮음": abs(d) <= 0.003 and (res["실제"] >= 0) == (res["합성"] >= 0)}
    return out
