"""실험실 1차: 예측 기반 30개(docs/LAB_FORECAST.md). 조절값은 돌리기 전에 정해 두고 결과를 보고 바꾸지 않는다.

모두 미국 상장 ETF만(개별 주식은 '오늘 큰 회사'를 골라 과거를 돌리는 생존 편향이 있어 뺐다). 방어 자산 SHY(단기 국채).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .rules import (SECTORS, Banded, BandedMix, FixedMix, GrowthTrend, HarvestOverlay, RankHold, SectorHold, TaxHarvest,
                    TrendPartial, TrendState, TrendSwitch, VolFloor, VolTarget)
from .strategy import ForecastRanker, MarketTimer

# 이 실험 묶음을 설계한 Fable 계획 Issue 번호(라벨 lab:fable-plan). lab-forecast는 이게 없으면 돌지 않는다.
# 1차(30개)는 Fable 설계 없이 만들어졌다(실수). 2차 #59, 3차 #66, 4차 #73, 5차 #79(가계 모형 — quant/forecast/round5.py), 6차 #85(round6.py),
# 7차 #93(여러 자산 ETF 추세추종 — round7.py, 누적 시도 82 + 10).
PLAN_ISSUE: int | None = 93

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


ROUND1: list[Exp] = [
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
assert len(ROUND1) == 30 and len({e.id for e in ROUND1}) == 30
MACRO_SERIES = ["VIXCLS", "VXVCLS", "BAA10Y", "BAMLH0A0HYM2", "BAMLC0A0CM", "T10Y2Y", "T10Y3M", "DGS10", "DFII10", "T5YIE", "DTWEXBGS",
                "DCOILWTICO", "NFCI", "STLFSI4", "ICSA", "SAHMREALTIME", "UMCSENT", "USEPUINDXD", "WLEMUINDXD", "DEXKOUS", "UNRATE"]


# ── 2차(Fable 설계 #59) ── 조절값은 계획에 적힌 그대로 고정. 바꾸면 새 id(시도 +1).
# T07·T08: 사후 수정이 없는 시장 지표 7개만(NFCI·금융 스트레스·샴·실업수당·소비자심리·달러·원/달러·뉴스 지수 제외).
CLEAN_MARKET = ["vix", "vix_term", "baa", "baa_ch21", "curve_2y", "curve_3m", "dgs10_ch21"]
T07_KW = {"model": "logit", "feats": "PM", "mode": "scaled", "h": 21, "refit_months": 3, "step": 5, "cols": CLEAN_MARKET}


def _k_ranker(px, mf, id_):
    return ForecastRanker(id_, px, mf, SECTORS, feats="P", model="ridge", h=21, refit_months=3, top=3)


ROUND2: list[Exp] = [
    Exp("A01", "A", "변동성이 높을 때 주식 비중을 줄이면 최악 손실이 S&P의 80% 이하, 세후 연수익은 0.5%p 넘게 안 뒤진다",
        lambda px, mf: VolTarget("A01", target=0.15, cap=1.0, band=0.10), "W"),
    Exp("A02", "A", "월말 S&P가 200일선 아래면 SHY로 피하면 최악 손실이 S&P의 80% 이하",
        lambda px, mf: TrendSwitch("A02", band=0.0), "M"),
    Exp("A03", "A", "같은 규칙을 주 1회 + ±2% 띠로 보면 A02보다 최악 손실이 작고 매매는 2배 이하",
        lambda px, mf: TrendSwitch("A03", band=0.02), "W"),
    Exp("A04", "A", "변동성 규칙 + 200일선 규칙을 합치면 각각보다 최악 손실이 작다",
        lambda px, mf: VolTarget("A04", target=0.15, cap=1.0, band=0.10, trend=TrendState(band=0.02)), "W"),
    Exp("L01", "L", "변동성 낮을 때 노출을 1.5배까지(SSO) 늘리면 세후 연수익 > S&P, 최악 손실 ≤ S&P",
        lambda px, mf: VolTarget("L01", target=0.15, cap=1.5, band=0.10), "W"),
    Exp("L02", "L", "L01 + 200일선 상태(피함이면 전부 SHY)면 최악 손실이 L01보다 작다",
        lambda px, mf: VolTarget("L02", target=0.15, cap=1.5, band=0.10, trend=TrendState(band=0.02)), "W"),
    Exp("T07", "T", "사후 수정 없는 시장 지표만으로도 확률 모델이 내린 달 빠짐 0.8 미만",
        lambda px, mf: MarketTimer("T07", px, mf, **T07_KW), "M"),
    Exp("T08", "T", "T07을 주 1회 보고 25%p 넘게 바뀔 때만 매매하면 최악 손실이 작고 비용 2배에서도 안 뒤진다",
        lambda px, mf: Banded("T08", MarketTimer("T08_timer", px, mf, **T07_KW), band=0.25), "W"),
    Exp("K01", "K", "업종 11개 12-1개월 상위 3, 5위 밖일 때만 교체하면 11개 똑같이보다 세후 연수익이 높다",
        lambda px, mf: SectorHold("K01", top=3, keep=5), "M"),
    Exp("K02", "K", "같은 11개에서 릿지 순위 예측이 K01보다 세후 연수익이 높고 IC t ≥ 2",
        lambda px, mf: RankHold("K02", _k_ranker(px, mf, "K02_rank"), top=3, keep=5), "M"),
    Exp("K03", "K", "S&P 70% + K02 상위 3개 30%면 S&P에 0.5%p 넘게 안 뒤지면서 세후 연수익이 높다",
        lambda px, mf: RankHold("K03", _k_ranker(px, mf, "K03_rank"), top=3, keep=5, core=0.7, band=0.05), "M"),
]
# 기준선(자): 시도 수에 세지 않고 검증에 올리지 않는다. B00은 엔진 기본 기준선(SPY 그냥 보유)과 같다.
BENCHMARKS: list[Exp] = [
    Exp("B80", "기준선", "SPY 80%·SHY 20%(해마다 맞춤)", lambda px, mf: FixedMix("B80", {"SPY": 0.8, "SHY": 0.2}), "M"),
    Exp("B60", "기준선", "SPY 60%·SHY 40%(해마다 맞춤)", lambda px, mf: FixedMix("B60", {"SPY": 0.6, "SHY": 0.4}), "M"),
    Exp("BEQ", "기준선", "업종 11개 똑같이(해마다 맞춤)", lambda px, mf: FixedMix("BEQ"), "M"),
]
assert len(ROUND2) == 11

# ── 3차(Fable 설계 #66) ── 예측 대신 세법(250만 원 공제)과 '일부만 줄이기'. 개발 구간 2004~2017. 조절값 고정.
def _u(mf):
    return pd.DataFrame({"latest": mf["unrate_latest"], "prev_mean": mf["unrate_prev12"]}) if "unrate_latest" in mf \
        else pd.DataFrame(index=mf.index, columns=["latest", "prev_mean"], dtype=float)


ROUND3: list[Exp] = [
    Exp("H01", "H", "해마다 공제 한도만큼 이익을 실현(SPY↔IVV)하면 청산 세후 연수익이 SPY·IVV 보유보다 0.1%p 이상 높다",
        lambda px, mf: TaxHarvest("H01"), "M"),
    Exp("D01", "D", "200일선 아래에서 30%만 줄이면 최악 손실 ≤ S&P×0.85, 베타 보정 알파 > 0",
        lambda px, mf: TrendPartial("D01", avoid_equity=0.7, band=0.02), "W"),
    Exp("D02", "D", "같은 규칙으로 50% 줄이면 D01보다 손실이 작고 알파는 D01 이상",
        lambda px, mf: TrendPartial("D02", avoid_equity=0.5, band=0.02), "W"),
    Exp("D03", "D", "월 1회만 보는 30% 줄이기가 D01보다 매매가 적고 알파는 같거나 높다",
        lambda px, mf: TrendPartial("D03", avoid_equity=0.7, band=0.0), "M"),
    Exp("G01", "G", "200일선 아래 + 실업률 상승 중일 때만 피하면 헛매매가 줄고 알파 > 0",
        lambda px, mf: GrowthTrend("G01", _u(mf), avoid_equity=0.0), "M"),
    Exp("G02", "G", "G01에서 절반만 줄여도 손실 ≤ S&P×0.85, 청산 세후 연수익 ≥ G01",
        lambda px, mf: GrowthTrend("G02", _u(mf), avoid_equity=0.5), "M"),
    Exp("V01", "V", "변동성이 높을 때 주식을 최대 40%까지만 줄이면(바닥 60%) 알파 > 0",
        lambda px, mf: VolFloor("V01", target=0.15, floor=0.6, band=0.15), "W"),
    Exp("M01", "M", "방어 20%를 장기채·금에 나누면 B80보다 청산 세후 연수익·최악 손실이 모두 낫다",
        lambda px, mf: BandedMix("M01", {"SPY": 0.8, "TLT": 0.1, "GLD": 0.1}, band=0.05), "M"),
    Exp("C01", "C", "D01 + 절세 매도(이익 비율 낮은 쪽부터 줄임)면 D01보다 청산 세후 0.1%p 이상 높다",
        lambda px, mf: HarvestOverlay("C01", TrendPartial("C01_base", avoid_equity=0.7, band=0.02), step_days=7), "W"),
    Exp("C02", "C", "G02 + 절세 매도면 G02보다 청산 세후 0.1%p 이상 높다",
        lambda px, mf: HarvestOverlay("C02", GrowthTrend("C02_base", _u(mf), avoid_equity=0.5), step_days=31), "M"),
]
BENCHMARKS3: list[Exp] = [
    Exp("BIV", "기준선", "IVV 그냥 보유(H01 이득이 종목 차이인지 가림)", lambda px, mf: FixedMix("BIV", {"IVV": 1.0}), "M"),
    Exp("B80", "기준선", "SPY 80%·SHY 20%(해마다 맞춤)", lambda px, mf: FixedMix("B80", {"SPY": 0.8, "SHY": 0.2}), "M"),
    Exp("B60", "기준선", "SPY 60%·SHY 40%(해마다 맞춤)", lambda px, mf: FixedMix("B60", {"SPY": 0.6, "SHY": 0.4}), "M"),
]
PREV_TRIALS_R3 = 48   # 3차 전까지 누적 시도(계획 #66: 1차 30 + 7 + 2차 11) → 개발 DSR 시도 수 = 48 + 10 = 58 (DB 값이 크면 그쪽)
assert len(ROUND3) == 10 and len({e.id for e in ROUND3 + BENCHMARKS3}) == 13

# ── 4차(Fable 설계 #73) ── 맞히지 않고 확실히 얻는 것(절세 매도·계좌 세율) + 원화 투자자의 환헤지 갈아타기.
# params: account = foreign(해외 직접) / deferred(절세계좌형) / domestic(국내 일반), period = dev(2004~) / fx(1999~)
from .rules import FxHedgeTrend, FxHedgeValue, MixHarvest  # noqa: E402
from quant.lab.strategy import BuyAndHold  # noqa: E402


def _fx(mf):
    return mf["fx_lag"]


ROUND4: list[Exp] = [
    Exp("R4_H1", "H", "절세 매도는 계좌가 작을수록 이득이 커서 IVV 보유 대비 1천만 +0.30%p·3천만 +0.15%p·5천만 +0.10%p·1억 > 0",
        lambda px, mf: TaxHarvest("R4_H1"), "M", {"account": "foreign"}),
    Exp("R4_C1", "C", "S&P 90 : 달러 단기채 10 + 절세 매도는 S&P −0.3%p 이내, 최악 손실 ≤ S&P×0.85",
        lambda px, mf: MixHarvest("R4_C1", eq=0.9), "M", {"account": "foreign"}),
    Exp("R4_C2", "C", "같은 규칙 80:20은 C1보다 손실이 작고 절세 매도 덕에 B80보다 연수익이 높다",
        lambda px, mf: MixHarvest("R4_C2", eq=0.8), "M", {"account": "foreign"}),
    Exp("R4_I1", "I", "절세계좌형에서 국내 상장 S&P를 그냥 들면 해외 직접 S&P보다 청산 세후 0.5%p 이상 높다",
        lambda px, mf: BuyAndHold("KSPX_U"), "M", {"account": "deferred"}),
    Exp("R4_I2", "I", "절세계좌형 90:10은 해외 직접 S&P보다 연수익이 같거나 높고 최악 손실이 작다",
        lambda px, mf: BandedMix("R4_I2", {"KSPX_U": 0.9, "KUST_U": 0.1}), "M", {"account": "deferred"}),
    Exp("R4_I3", "I", "절세계좌형 80:20은 해외 직접 S&P −0.3%p 이내, 최악 손실 ≤ S&P×0.85",
        lambda px, mf: BandedMix("R4_I3", {"KSPX_U": 0.8, "KUST_U": 0.2}), "M", {"account": "deferred"}),
    Exp("R4_F1", "F", "원/달러가 200일 평균 아래로 내리는 추세일 때만 환헤지하면 같은 헤지 비율 고정 혼합보다 연 0.5%p 이상 높다",
        lambda px, mf: FxHedgeTrend("R4_F1", _fx(mf), window=200), "M", {"account": "deferred", "period": "fx"}),
    Exp("R4_F1a", "F", "(고원) F1을 100일 평균으로", lambda px, mf: FxHedgeTrend("R4_F1a", _fx(mf), window=100), "M",
        {"account": "deferred", "period": "fx", "neighbor_of": "R4_F1"}),
    Exp("R4_F1b", "F", "(고원) F1을 300일 평균으로", lambda px, mf: FxHedgeTrend("R4_F1b", _fx(mf), window=300), "M",
        {"account": "deferred", "period": "fx", "neighbor_of": "R4_F1"}),
    Exp("R4_F2", "F", "달러가 비싸졌다가 꺾인 뒤에만 헤지하면 같은 헤지 비율 고정 혼합보다 연 0.5%p 이상 높다",
        lambda px, mf: FxHedgeValue("R4_F2", _fx(mf), window=756), "M", {"account": "deferred", "period": "fx"}),
    Exp("R4_F2a", "F", "(고원) F2를 504일 평균으로", lambda px, mf: FxHedgeValue("R4_F2a", _fx(mf), window=504), "M",
        {"account": "deferred", "period": "fx", "neighbor_of": "R4_F2"}),
    Exp("R4_F2b", "F", "(고원) F2를 1260일 평균으로", lambda px, mf: FxHedgeValue("R4_F2b", _fx(mf), window=1260), "M",
        {"account": "deferred", "period": "fx", "neighbor_of": "R4_F2"}),
]
BENCHMARKS4: list[Exp] = [
    Exp("BIV", "기준선", "IVV 그냥 보유", lambda px, mf: FixedMix("BIV", {"IVV": 1.0}), "M", {"account": "foreign"}),
    Exp("B90", "기준선", "SPY 90·SHY 10(해마다)", lambda px, mf: FixedMix("B90", {"SPY": 0.9, "SHY": 0.1}), "M", {"account": "foreign"}),
    Exp("B80", "기준선", "SPY 80·SHY 20(해마다)", lambda px, mf: FixedMix("B80", {"SPY": 0.8, "SHY": 0.2}), "M", {"account": "foreign"}),
    Exp("B70", "기준선", "SPY 70·SHY 30(해마다)", lambda px, mf: FixedMix("B70", {"SPY": 0.7, "SHY": 0.3}), "M", {"account": "foreign"}),
    Exp("BW80", "기준선", "SPY 80·원화 현금 20(해마다)", lambda px, mf: FixedMix("BW80", {"SPY": 0.8, "KRWCASH": 0.2}), "M", {"account": "foreign"}),
    Exp("BKR", "기준선", "국내 일반계좌 KSPX_U 보유", lambda px, mf: BuyAndHold("KSPX_U"), "M", {"account": "domestic"}),
    Exp("BKH", "기준선", "절세계좌형 항상 헤지", lambda px, mf: BuyAndHold("KSPX_H"), "M", {"account": "deferred"}),
]
PREV_TRIALS = 58   # 4차 전까지 누적 서로 다른 전략(계획 #73) → 개발 시도 수 = max(DB, 58 + 12 = 70)
EXPERIMENTS = ROUND4   # 기본 실행 대상
assert len(ROUND4) == 12 and len({e.id for e in ROUND4 + BENCHMARKS4}) == 19
