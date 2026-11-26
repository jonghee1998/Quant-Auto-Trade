"""실험실 1차: 예측 기반 30개(docs/LAB_FORECAST.md). 조절값은 돌리기 전에 정해 두고 결과를 보고 바꾸지 않는다.

모두 미국 상장 ETF만(개별 주식은 '오늘 큰 회사'를 골라 과거를 돌리는 생존 편향이 있어 뺐다). 방어 자산 SHY(단기 국채).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .strategy import ForecastRanker, MarketTimer

UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC",
            "SOXX", "EFA", "EEM", "EWJ", "VGK", "EWY", "EWT", "EWZ", "MCHI", "INDA", "TLT", "IEF", "GLD", "VNQ"]


@dataclass(frozen=True)
class Exp:
    id: str
    group: str        # 규칙 / 순위(월) / 시장 타이밍 / 스윙(주) / 조합
    hypothesis: str
    build: Callable[[pd.DataFrame, pd.DataFrame], object]   # (가격, 지표 특성) → 전략
    rebalance: str = "M"
    params: dict | None = None


class RuleMomentum:
    """규칙 기준선: 12-1개월 수익 상위 top개(모델 없음). trend=True면 S&P 200일선 아래일 때 SHY."""

    def __init__(self, name, px, top=3, trend=False):
        self.name, self.top, self.trend = name, top, trend
        self.universe = [t for t in UNIVERSE if t in px]

    def weights(self, as_of, history):
        if self.trend:
            s = history["SPY"].dropna()
            if len(s) >= 200 and s.iloc[-1] < s.iloc[-200:].mean():
                return {"SHY": 1.0}
        h = history[self.universe]
        ok = h.notna().sum() >= 260
        m = (h.shift(21).iloc[-1] / h.shift(252).iloc[-1] - 1)[ok].dropna()
        pick = m.sort_values(ascending=False).index[: self.top]
        return {t: 1 / len(pick) for t in pick} if len(pick) else {}


class DualMomentum:
    """규칙 기준선(Antonacci식): 미국(SPY)·선진국(EFA) 중 12개월 수익 큰 쪽, 그게 현금(SHY)보다 못하면 장기채(IEF)."""

    def __init__(self, name):
        self.name = name

    def weights(self, as_of, history):
        r = history[["SPY", "EFA", "SHY"]].iloc[-1] / history[["SPY", "EFA", "SHY"]].iloc[-253] - 1
        best = "SPY" if r["SPY"] >= r["EFA"] else "EFA"
        return {best: 1.0} if r[best] > r["SHY"] else {"IEF": 1.0}


def _r(id_, **kw):
    return lambda px, mf: ForecastRanker(id_, px, mf, UNIVERSE, **kw)


def _t(id_, **kw):
    return lambda px, mf: MarketTimer(id_, px, mf, **kw)


def _combo(id_, timer_kw, **kw):
    return lambda px, mf: ForecastRanker(id_, px, mf, UNIVERSE, regime="timer", timer=MarketTimer(id_ + "_timer", px, mf, **timer_kw), **kw)


EXPERIMENTS: list[Exp] = [
    # 규칙 기준선(모델 없이도 되는지 먼저)
    Exp("R01", "규칙", "12-1개월 수익 상위 3개 ETF를 매달 들면 S&P보다 낫다", lambda px, mf: RuleMomentum("R01", px)),
    Exp("R02", "규칙", "R01 + S&P가 200일선 아래면 단기채로 피하면 덜 잃는다", lambda px, mf: RuleMomentum("R02", px, trend=True)),
    Exp("R03", "규칙", "듀얼 모멘텀(미국·선진국 중 강한 쪽, 현금보다 약하면 채권)이 하락장을 피한다", lambda px, mf: DualMomentum("R03")),
    # 순위 예측(월): 특성 묶음 × 모델 — 다음 달 S&P 대비 초과수익 순위
    Exp("C01", "순위(월)", "가격 특성만으로 선형(릿지) 순위 예측이 통한다", _r("C01", feats="P", model="ridge")),
    Exp("C02", "순위(월)", "가격 특성 + 트리 부스팅(비선형)", _r("C02", feats="P", model="hgb")),
    Exp("C03", "순위(월)", "가격 특성 + 신경망(MLP)", _r("C03", feats="P", model="mlp")),
    Exp("C04", "순위(월)", "+ 거시 지표(금리·신용·달러·유가·고용)와 베타 상호작용, 릿지", _r("C04", feats="PM", model="ridge")),
    Exp("C05", "순위(월)", "+ 거시 지표, 트리 부스팅", _r("C05", feats="PM", model="hgb")),
    Exp("C06", "순위(월)", "+ 거시 지표, 신경망", _r("C06", feats="PM", model="mlp")),
    Exp("C07", "순위(월)", "+ 뉴스 기반 지수(정책 불확실성·시장 변동성 기사), 릿지", _r("C07", feats="PMN", model="ridge")),
    Exp("C08", "순위(월)", "+ 뉴스 기반 지수, 트리 부스팅", _r("C08", feats="PMN", model="hgb")),
    Exp("C09", "순위(월)", "+ 뉴스 기반 지수, 신경망", _r("C09", feats="PMN", model="mlp")),
    Exp("C10", "순위(월)", "세 모델(릿지·부스팅·신경망) 순위 평균이 하나보다 안정적이다", _r("C10", feats="PMN", model="ens")),
    Exp("C11", "순위(월)", "랜덤 포레스트(나무 평균)", _r("C11", feats="PMN", model="rf")),
    Exp("C12", "순위(월)", "부스팅 상위 5개를 변동성 반비례로 나눠 담으면 손실이 줄어든다", _r("C12", feats="PMN", model="hgb", top=5, weighting="invvol")),
    # 시장 타이밍: 다음 달 S&P가 단기채보다 나을 확률 → 주식 비중
    Exp("T01", "시장 타이밍", "거시+뉴스 지표로 로지스틱 확률 50% 넘을 때만 S&P", _t("T01", model="logit", feats="PMN", mode="binary")),
    Exp("T02", "시장 타이밍", "같은 판단을 트리 부스팅으로", _t("T02", model="hgb", feats="PMN", mode="binary")),
    Exp("T03", "시장 타이밍", "같은 판단을 신경망으로", _t("T03", model="mlp", feats="PMN", mode="binary")),
    Exp("T04", "시장 타이밍", "확률에 비례해 비중을 나누면(0.35→0%, 0.65→100%) 갑자기 다 빠지는 손해가 준다", _t("T04", model="logit", feats="PMN", mode="scaled")),
    Exp("T05", "시장 타이밍", "T04에서 뉴스 지수를 빼면 나빠진다(뉴스 효과 확인)", _t("T05", model="logit", feats="PM", mode="scaled")),
    Exp("T06", "시장 타이밍", "가격만 본 부스팅 확률(지표 없이)", _t("T06", model="hgb", feats="P", mode="scaled")),
    # 스윙(주): 다음 주(5거래일) 순위, 매주 교체
    Exp("S01", "스윙(주)", "단기 반전·추세 특성 릿지로 다음 주 강한 3개", _r("S01", h=5, feats="S", model="ridge", refit_months=3, train_years=8), "W"),
    Exp("S02", "스윙(주)", "+ 불안·신용·뉴스 지표, 부스팅", _r("S02", h=5, feats="SM", model="hgb", refit_months=3, train_years=8), "W"),
    Exp("S03", "스윙(주)", "+ 지표, 신경망", _r("S03", h=5, feats="SM", model="mlp", refit_months=3, train_years=8), "W"),
    Exp("S04", "스윙(주)", "세 모델 평균 + 200일선 아래면 단기채", _r("S04", h=5, feats="SM", model="ens", refit_months=3, train_years=8, regime="trend"), "W"),
    # 조합: 순위 + 위험 관리(자동매매 후보 모양)
    Exp("X01", "조합", "C08 + 200일선 아래면 단기채", _r("X01", feats="PMN", model="hgb", regime="trend")),
    Exp("X02", "조합", "C10 + 시장 타이밍(T04) 확률만큼만 주식", _combo("X02", {"model": "logit", "feats": "PMN", "mode": "scaled"}, feats="PMN", model="ens")),
    Exp("X03", "조합", "C10 + 목표 변동성 12%(넘으면 비중 줄임)", _r("X03", feats="PMN", model="ens", vol_target=0.12)),
    Exp("X04", "조합", "상위 5 변동성 반비례 + 타이밍 + 목표 변동성 15%(자동매매 후보형)",
        _combo("X04", {"model": "logit", "feats": "PMN", "mode": "scaled"}, feats="PMN", model="ens", top=5, weighting="invvol", vol_target=0.15)),
    Exp("X05", "조합", "C10을 최근 8년 창으로만 학습하면(옛 시장을 잊음) 더 안정적이다", _r("X05", feats="PMN", model="ens", train_years=8)),
]
assert len(EXPERIMENTS) == 30 and len({e.id for e in EXPERIMENTS}) == 30
MACRO_SERIES = ["VIXCLS", "VXVCLS", "BAA10Y", "BAMLH0A0HYM2", "BAMLC0A0CM", "T10Y2Y", "T10Y3M", "DGS10", "DFII10", "T5YIE", "DTWEXBGS",
                "DCOILWTICO", "NFCI", "STLFSI4", "ICSA", "SAHMREALTIME", "UMCSENT", "USEPUINDXD", "WLEMUINDXD", "DEXKOUS"]
