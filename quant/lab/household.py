"""가계 모형(실험실 5차, Fable 설계 #79): 입금 일정 + 계좌 여러 개(해외 직접·ISA·국내 일반·연금)를 함께 굴린다.

예측 없는 규칙(달력·계좌 상태)만 다룬다. 신호는 그날 종가의 계좌 상태로 정하고 다음 거래일 종가에 체결한다.
세법 숫자는 모두 상수(사람 확인 필요): 해외 직접 22%·연 250만 공제·그해 손익 통산, 배당 15%,
ISA 연 2천만·총 1억·만기 정산 (순이익 − 200만) × 9.9%, 국내 일반 15.4%(종합과세 선택), 연금 중도 해지 16.5%·연금 수령 5.5%.

배당: 수정주가(배당 재투자)를 쓰므로 배당락일에 세금만 현금에서 빼고, div_basis=True면 재투자된 배당액을 취득원가에 더한다
(엔진 run_backtest는 더하지 않아 재투자분에 양도세가 한 번 더 붙었다 — 판정 #77, 5차 엔진에서 고침).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TAX = {"foreign": 0.22, "deduction": 2_500_000.0, "div_foreign": 0.15, "domestic": 0.154, "isa": 0.099, "isa_free": 2_000_000.0,
       "pension_early": 0.165, "pension_annuity": 0.055, "pension_credit": 0.132, "comp_threshold": 20_000_000.0}
ISA_YEAR, ISA_TOTAL = 20_000_000.0, 100_000_000.0
DIV_SRC = {"KSPX_N": "SPY", "KSPX_U": "SPY", "KUST_U": "SHY"}  # 원화 합성 시세의 배당 출처


@dataclass
class Book:
    kind: str                         # foreign / isa / domestic / pension
    cash: float = 0.0
    q: dict = field(default_factory=dict)
    basis: dict = field(default_factory=dict)
    realized_year: float = 0.0        # foreign: 그해 실현 손익 합(통산)
    income_year: float = 0.0          # domestic: 그해 금융소득(종합과세 판단)
    contrib: float = 0.0              # isa·pension: 넣은 돈 합
    opened: pd.Timestamp | None = None
    taxes: float = 0.0
    comp_rate: float | None = None    # domestic 종합과세 세율(보고용 기준선)

    def value(self, px, R) -> float:
        return self.cash + sum(q * float(px[t]) * R(t) for t, q in self.q.items())

    def holdings(self, px, R) -> dict[str, float]:
        return {t: q * float(px[t]) * R(t) for t, q in self.q.items()}


@dataclass
class Costs5:
    fee: float = 0.0005
    slippage: float = 0.0003
    fx_spread: float = 0.001

    def scaled(self, k: float) -> "Costs5":
        return Costs5(self.fee * k, self.slippage * k, self.fx_spread * k)


class Household:
    """계좌 묶음 + 체결 규칙. krw: 원화 자산(국내 상장 ETF 합성 등) — 환율·환전 없음."""

    def __init__(self, books: dict[str, Book], krw: frozenset, costs: Costs5, div_basis: bool = True):
        self.books, self.krw, self.c, self.div_basis = books, krw, costs, div_basis
        self.trades: list[dict] = []

    # ---- 단가·환율
    def R(self, rate):
        return lambda t: 1.0 if t in self.krw else rate

    # ---- 매매(그날 종가)
    def sell(self, b: Book, t: str, krw_amt: float, px, rate, d, qty: float | None = None, no_fx: bool = False) -> float:
        """t를 원화 krw_amt어치(평가액 기준, 또는 qty주) 판다. 받은 원화(비용·환전·즉시 세금 뺀 뒤) 반환.
        no_fx: 달러로 받아 바로 다른 달러 자산을 사는 경우(갈아타기) — 환전 비용 없음(6차, 계획 #85)."""
        if b.q.get(t, 0) <= 0 or (krw_amt <= 0 and not qty):
            return 0.0
        r = 1.0 if t in self.krw else rate
        p = float(px[t])
        qty = min(b.q[t], qty if qty else krw_amt / (p * r))
        net = qty * p * r * (1 - self.c.fee - self.c.slippage) * (1.0 if (t in self.krw or no_fx) else 1 - self.c.fx_spread)
        avg = b.basis[t] / b.q[t]
        gain = net - avg * qty
        b.basis[t] -= avg * qty
        b.q[t] -= qty
        if b.q[t] <= 1e-12:
            b.q.pop(t)
            b.basis.pop(t)
        if b.kind == "foreign":
            if t in self.krw:  # 해외 직접 계좌 안의 원화 자산은 국내 과세(15.4%)
                tx = max(0.0, gain) * TAX["domestic"]
                net -= tx
                b.taxes += tx
            else:
                b.realized_year += gain
        elif b.kind == "domestic":
            tx = self._domestic_tax(b, gain)
            net -= tx
            b.taxes += tx
        b.cash += net
        self.trades.append({"date": d, "book": b.kind, "ticker": t, "side": "sell", "krw": net})
        return net

    def _domestic_tax(self, b: Book, gain: float) -> float:
        if gain <= 0:
            return 0.0
        if b.comp_rate is None:
            return gain * TAX["domestic"]
        before = b.income_year
        b.income_year += gain
        over = max(0.0, b.income_year - TAX["comp_threshold"]) - max(0.0, before - TAX["comp_threshold"])
        return (gain - over) * TAX["domestic"] + over * b.comp_rate

    def buy(self, b: Book, t: str, krw_amt: float, px, rate, d, no_fx: bool = False) -> None:
        if krw_amt <= 0:
            return
        r = 1.0 if t in self.krw else rate
        fx = 0.0 if (t in self.krw or no_fx) else self.c.fx_spread
        spend = min(krw_amt, b.cash)
        if spend <= 0:
            return
        gross = spend / (1 + self.c.fee + self.c.slippage + fx)
        qty = gross / (float(px[t]) * r)
        b.q[t] = b.q.get(t, 0.0) + qty
        b.basis[t] = b.basis.get(t, 0.0) + spend
        b.cash -= spend
        self.trades.append({"date": d, "book": b.kind, "ticker": t, "side": "buy", "krw": spend})

    def swap(self, b: Book, a: str, c: str, qty: float, px, rate, d) -> None:
        """달러 자산끼리 갈아타기: a를 qty주 팔아 받은 돈으로 c를 산다. 환전 비용 없음(수수료·호가만)."""
        got = self.sell(b, a, 0.0, px, rate, d, qty=qty, no_fx=True)
        self.buy(b, c, got, px, rate, d, no_fx=True)

    def rebalance(self, b: Book, target: dict[str, float], px, rate, d) -> None:
        """b의 총액(현금 포함)을 target 비중으로(팔기 먼저, 그다음 현금 안에서 사기)."""
        R = self.R(rate)
        V = b.value(px, R)
        hold = b.holdings(px, R)
        for t in list(hold):
            want = target.get(t, 0.0) * V
            if hold[t] > want + 1e-6:
                self.sell(b, t, hold[t] - want, px, rate, d)
        hold = b.holdings(px, R)
        need = {t: max(0.0, w * V - hold.get(t, 0.0)) for t, w in target.items()}
        tot = sum(need.values())
        if tot <= 0:
            return
        k = min(1.0, b.cash / tot)
        for t, v in need.items():
            self.buy(b, t, v * k, px, rate, d)

    # ---- 배당·세금
    def dividends(self, b: Book, prev_px, d, rate, div_yield: pd.DataFrame | None) -> None:
        if div_yield is None or d not in div_yield.index:
            return
        for t, q in list(b.q.items()):
            src = DIV_SRC.get(t, t)
            if src not in div_yield.columns:
                continue
            y = div_yield.at[d, src]
            if not (y and y > 0):
                continue
            if t in self.krw:
                # 국내 상장 합성 시세는 분배금(미국 배당세 15% 뗀 뒤)을 시세 안에서 재투자한다 → 국내 일반계좌만 15.4% 분배금 세금
                if b.kind == "domestic":
                    net_div = q * float(prev_px[t]) * y * (1 - TAX["div_foreign"] if src == "SPY" else 1.0)
                    tx = self._domestic_tax(b, net_div)
                    b.cash -= tx
                    b.taxes += tx
                    if self.div_basis:
                        b.basis[t] += net_div
                continue
            gross = q * float(prev_px[t]) * rate * y
            if b.kind == "foreign":
                b.cash -= gross * TAX["div_foreign"]
                b.taxes += gross * TAX["div_foreign"]
            elif b.kind == "domestic":
                tx = self._domestic_tax(b, gross)
                b.cash -= tx
                b.taxes += tx
            if self.div_basis and b.kind in ("foreign", "domestic"):
                b.basis[t] += gross  # 재투자된 배당은 새로 산 것과 같다

    def year_end(self, b: Book, px, rate, d) -> None:
        """해외 직접: 그해 실현 손익 합에서 공제 뒤 22%를 현금으로 낸다(모자라면 보유분 비례 매도)."""
        if b.kind == "foreign":
            tax = max(0.0, b.realized_year - TAX["deduction"]) * TAX["foreign"]
            b.cash -= tax
            b.taxes += tax
            b.realized_year = 0.0
            if b.cash < 0 and b.q:
                R = self.R(rate)
                hold = b.holdings(px, R)
                H = sum(hold.values())
                for t, v in hold.items():
                    self.sell(b, t, min(v, -b.cash * v / H * 1.002), px, rate, d)
        b.income_year = 0.0

    def liquidation(self, b: Book, px, rate, pension_mode: str = "early", staged_years: int = 0) -> float:
        """그날 다 팔고 세금까지 낸 뒤 남는 원화(계좌 종류별).
        staged_years=N(6차 E-N 결말): 해외 직접 계좌는 가격이 멈춘다고 치고 N년에 나눠 판다 → 남은 이익 중 N × 250만 원 비과세."""
        R = self.R(rate)
        out, gain, imm = b.cash, b.realized_year, 0.0
        for t, q in b.q.items():
            k = t in self.krw
            net = q * float(px[t]) * R(t) * (1 - self.c.fee - self.c.slippage) * (1.0 if k else 1 - self.c.fx_spread)
            out += net
            g = net - b.basis[t]
            if b.kind == "foreign":
                if k:
                    imm += max(0.0, g) * TAX["domestic"]
                else:
                    gain += g
            elif b.kind == "domestic":
                if b.comp_rate is None:
                    imm += max(0.0, g) * TAX["domestic"]
                else:
                    imm += self._domestic_tax(Book("domestic", income_year=b.income_year, comp_rate=b.comp_rate), g)
        if b.kind == "foreign":
            free = TAX["deduction"] * max(1, staged_years)
            return out - max(0.0, gain - free) * TAX["foreign"] - imm
        if b.kind == "domestic":
            return out - imm
        if b.kind == "isa":
            return out - max(0.0, out - b.contrib - TAX["isa_free"]) * TAX["isa"]
        if b.kind == "pension":
            return out * (1 - (TAX["pension_early"] if pension_mode == "early" else TAX["pension_annuity"]))
        raise ValueError(b.kind)


def first_days(idx: pd.DatetimeIndex, freq: str) -> set[pd.Timestamp]:
    s = pd.Series(idx, index=idx)
    key = [idx.year, idx.month] if freq == "M" else [idx.year]
    return set(s.groupby(key).min())


def last_days(idx: pd.DatetimeIndex, freq: str) -> set[pd.Timestamp]:
    s = pd.Series(idx, index=idx)
    key = [idx.year, idx.month] if freq == "M" else [idx.year]
    return set(s.groupby(key).max())


@dataclass
class Plan:
    """입금 일정: monthly(매달 첫 거래일 금액) 또는 lump(첫날 한 번)."""
    name: str
    monthly: float = 0.0
    lump: float = 0.0


PLANS = {"P50": Plan("P50", monthly=500_000.0), "P150": Plan("P150", monthly=1_500_000.0), "P300": Plan("P300", monthly=3_000_000.0),
         "L1천만": Plan("L1천만", lump=10_000_000.0), "L1억": Plan("L1억", lump=100_000_000.0)}


@dataclass
class SimResult:
    nav: pd.Series            # 세금 전 평가액(원화, 모든 계좌 합)
    liq: pd.Series            # 그날 다 팔고 세금 낸 뒤(원화)
    flows: pd.Series          # 날짜별 입금(원화)
    taxes: float
    trades: int
    extra: dict
    endings: dict = field(default_factory=dict)   # 마지막 날 결말별 금액: E0(한꺼번에)·E10·E20(나눠 팔기)


def simulate(prices: pd.DataFrame, fx: pd.Series, policy, plan: Plan, start, end, *, costs: Costs5 = Costs5(),
             krw: frozenset = frozenset(), div_yield: pd.DataFrame | None = None, div_basis: bool = True) -> SimResult:
    """policy: .setup(hh, d) → 계좌들, .deposit(hh, amt, d, px, rate) → 입금 배분, .signal(hh, d, px, rate, ctx) → 다음 날 할 일(함수 목록)."""
    idx = prices.index[(prices.index >= pd.Timestamp(start)) & (prices.index <= pd.Timestamp(end))]
    f = fx.reindex(prices.index).ffill()
    if f.loc[idx].isna().any():
        raise ValueError("구간 안에 환율이 없는 날이 있다")
    hh = Household(policy.books(), krw, costs, div_basis)
    m_first, y_first = first_days(idx, "M"), first_days(idx, "Y")
    m_last, y_last = last_days(idx, "M"), last_days(idx, "Y")
    pending: list = []
    nav, liq, flows = [], [], []
    for i, d in enumerate(idx):
        px, rate = prices.loc[d], float(f.loc[d])
        if i > 0:
            prev = prices.loc[idx[i - 1]]
            for b in hh.books.values():
                hh.dividends(b, prev, d, rate, div_yield)
        for job in pending:  # 어제 정한 일을 오늘 종가에
            job(hh, d, px, rate)
        pending = []
        amt = plan.lump if i == 0 else 0.0
        if plan.monthly and d in m_first:
            amt += plan.monthly
        if amt:
            policy.deposit(hh, amt, d, px, rate)
        flows.append(amt)
        ctx = {"month_first": d in m_first, "year_first": d in y_first, "month_last": d in m_last, "year_last": d in y_last,
               "first_day": i == 0, "last_day": i == len(idx) - 1}
        if i < len(idx) - 1:
            pending = policy.signal(hh, d, px, rate, ctx) or []
        if d in y_last and i < len(idx) - 1:
            for b in hh.books.values():
                hh.year_end(b, px, rate, d)
        R = hh.R(rate)
        nav.append(sum(b.value(px, R) for b in hh.books.values()))
        liq.append(sum(hh.liquidation(b, px, rate, getattr(policy, "pension_mode", "early")) for b in hh.books.values()))
    taxes = sum(b.taxes for b in hh.books.values())
    pm = getattr(policy, "pension_mode", "early")
    endings = {f"E{n}": sum(hh.liquidation(b, px, rate, pm, staged_years=n) for b in hh.books.values()) for n in (0, 10, 20)}
    return SimResult(pd.Series(nav, index=idx), pd.Series(liq, index=idx), pd.Series(flows, index=idx), taxes, len(hh.trades),
                     getattr(policy, "extra", {}), endings)


# ---------------------------------------------------------------- 재는 법(입금이 있을 때)

def irr(flows: pd.Series, final_value: float) -> float:
    """돈 넣은 시점을 반영한 연수익(내부수익률). flows: 날짜별 입금(+), 마지막 날 final_value를 돌려받는다."""
    f = flows[flows != 0]
    if f.empty or final_value <= 0:
        return float("nan")
    t0 = flows.index[0]
    t = np.array([(d - t0).days / 365.25 for d in f.index] + [(flows.index[-1] - t0).days / 365.25])
    cf = np.array(list(-f.to_numpy()) + [final_value])

    def npv(r):
        return float(np.sum(cf / (1 + r) ** t))
    lo, hi = -0.99, 1.0
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return float((lo + hi) / 2)


def unit_price(nav: pd.Series, flows: pd.Series) -> pd.Series:
    """입금 효과를 뺀 단위 가격(시간 가중): 하루 수익 = (오늘 평가액 − 오늘 입금) ÷ 어제 평가액 − 1."""
    v, f = nav.to_numpy(), flows.reindex(nav.index).fillna(0.0).to_numpy()
    out = np.ones(len(v))
    for i in range(1, len(v)):
        r = (v[i] - f[i]) / v[i - 1] - 1 if v[i - 1] > 0 else 0.0
        out[i] = out[i - 1] * (1 + r)
    s = pd.Series(out, index=nav.index)
    first = np.argmax(v > 0) if (v > 0).any() else 0
    return s.iloc[first:] / s.iloc[first]


def max_dd(s: pd.Series) -> float:
    return float((s / s.cummax() - 1).min()) if len(s) > 1 else float("nan")


def dd_in(s: pd.Series, a, b) -> float:
    x = s.loc[a:b]
    return float((x / x.cummax() - 1).min()) if len(x) > 1 else float("nan")
