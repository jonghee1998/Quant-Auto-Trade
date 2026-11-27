"""실험실 5차(Fable 설계 #79) 가계 정책: 달력과 그날 종가의 계좌 상태만 쓴다(예측 없음). quant.lab.household.simulate가 부른다.

정책이 돌려주는 '할 일'은 다음 거래일 종가에 실행된다.
"""
from __future__ import annotations

import pandas as pd

from quant.lab.household import ISA_TOTAL, ISA_YEAR, TAX, Book, Household

from .rules import harvest_move


def _invest_cash(hh: Household, b: Book, mix: dict[str, float], d, px, rate):
    """현금이 있으면 mix 비중대로 산다(이미 든 것은 안 판다)."""
    if b.cash <= 1_000:
        return
    cash = b.cash
    for t, w in mix.items():
        hh.buy(b, t, cash * w, px, rate, d)


def _rebalance_if_drift(hh: Household, b: Book, mix: dict[str, float], band: float, px, rate, d) -> bool:
    R = hh.R(rate)
    V = b.value(px, R)
    if V <= 0 or len(mix) < 2:
        return False
    h = b.holdings(px, R)
    if max(abs(h.get(t, 0.0) / V - w) for t, w in mix.items()) <= band:
        return False
    hh.rebalance(b, mix, px, rate, d)
    return True


def _gain_ratio(b: Book, t: str, px, R) -> float:
    if b.q.get(t, 0) <= 0 or b.basis.get(t, 0) <= 0:
        return 0.0
    return b.q[t] * float(px[t]) * R(t) / b.basis[t] - 1


def _harvest_job(pair=("SPY", "IVV"), use_eq_only=True):
    """11월 마지막 거래일 신호 → 다음 거래일: 공제 남은 만큼 이익 비율 큰 쪽을 팔아 다른 쪽을 산다(그날 다시 계산)."""
    def job(hh: Household, d, px, rate, b: Book):
        R = hh.R(rate)
        vals = {t: b.q[t] * float(px[t]) * R(t) for t in b.q}
        ratio = {t: _gain_ratio(b, t, px, R) for t in b.q}
        mv = harvest_move(vals, ratio, b.realized_year, deduction=TAX["deduction"], pair=pair)
        if mv is None or pd.isna(px.get(pair[1], float("nan"))) or pd.isna(px.get(pair[0], float("nan"))):
            return
        a, c, amt = mv
        got = hh.sell(b, a, amt, px, rate, d)
        hh.buy(b, c, got, px, rate, d)
    return job


class Hold:
    """한 계좌, 목표 비중. 입금은 다음 거래일 목표대로 산다. rebalance: 'year'(해마다 1월 첫 거래일) / 'band'(월말 5%p 띠) / None."""

    def __init__(self, name: str, kind: str, mix: dict[str, float], rebalance: str | None = None, band: float = 0.05,
                 harvest: bool = False, comp_rate: float | None = None):
        self.name, self.kind, self.mix, self.reb, self.band, self.harvest, self.comp = name, kind, mix, rebalance, band, harvest, comp_rate
        self.extra = {"harvests": 0}

    def books(self):
        return {"main": Book(self.kind, comp_rate=self.comp)}

    def deposit(self, hh, amt, d, px, rate):
        b = hh.books["main"]
        b.cash += amt
        b.contrib += amt

    def signal(self, hh, d, px, rate, ctx):
        b = hh.books["main"]
        jobs = []
        if b.cash > 1_000:
            jobs.append(lambda hh, d, px, rate: _invest_cash(hh, b, self.mix, d, px, rate))
        if self.reb == "year" and ctx["year_first"] and not ctx["first_day"] and len(self.mix) > 1:
            jobs.append(lambda hh, d, px, rate: hh.rebalance(b, self.mix, px, rate, d))
        if self.reb == "band" and ctx["month_last"]:
            jobs.append(lambda hh, d, px, rate: _rebalance_if_drift(hh, b, self.mix, self.band, px, rate, d))
        if self.harvest and ctx["month_last"] and d.month == 11:
            self.extra["harvests"] += 1
            jobs.append(lambda hh, d, px, rate: _harvest_job()(hh, d, px, rate, b))
        return jobs


class IsaPlus:
    """A1~A5: ISA(연 2천만·총 1억·만기 정산) 먼저, 넘친 돈은 바깥(해외 직접).
    - 입금: ISA 한도 안이면 ISA, 넘치면 바깥.
    - 1월 첫 거래일: 남는 한도만큼 바깥 → ISA(그 매도로 실현되는 이익이 250만 원 이하가 되는 금액까지).
    - 만기(가입 후 years년): 정산 (순이익 − 200만) × 9.9% 내고 전액 바깥 → 그날 새 ISA 시작(한도 새로).
    - isa_mix·out_mix: 계좌 안 비중. ISA 안은 월말 5%p 띠(세금 없음), 바깥은 1월 첫 거래일 맞춤. out_harvest: 바깥 11월 말 절세 매도."""

    def __init__(self, name: str, isa_mix: dict[str, float], out_mix: dict[str, float], years: int = 3, out_harvest: bool = False,
                 band: float = 0.05):
        self.name, self.isa_mix, self.out_mix, self.years, self.harvest, self.band = name, isa_mix, out_mix, years, out_harvest, band
        self.extra = {"maturities": 0, "transfers": 0, "harvests": 0}

    def books(self):
        return {"isa": Book("isa"), "out": Book("foreign")}

    def room(self, isa: Book, d) -> float:
        if isa.opened is None:
            return ISA_YEAR
        allowed = min(ISA_TOTAL, ISA_YEAR * (d.year - isa.opened.year + 1))
        return max(0.0, allowed - isa.contrib)

    def deposit(self, hh, amt, d, px, rate):
        isa, out = hh.books["isa"], hh.books["out"]
        if isa.opened is None:
            isa.opened = d
        to_isa = min(amt, self.room(isa, d))
        isa.cash += to_isa
        isa.contrib += to_isa
        out.cash += amt - to_isa

    def _transfer(self, hh: Household, d, px, rate):
        isa, out = hh.books["isa"], hh.books["out"]
        R = hh.R(rate)
        room = self.room(isa, d)
        hold = out.holdings(px, R)
        V = sum(hold.values())
        if room <= 0 or V <= 0:
            return
        basis = sum(out.basis[t] for t in hold)
        g = V / basis - 1 if basis > 0 else 0.0
        cap = (TAX["deduction"] - out.realized_year) * (1 + g) / g if g > 0 else float("inf")
        amt = min(room, V, max(0.0, cap))
        if amt < 100_000:
            return
        got = sum(hh.sell(out, t, amt * v / V, px, rate, d) for t, v in hold.items())
        out.cash -= got
        isa.cash += got
        isa.contrib += got
        self.extra["transfers"] += 1
        _invest_cash(hh, isa, self.isa_mix, d, px, rate)

    def _mature(self, hh: Household, d, px, rate):
        isa, out = hh.books["isa"], hh.books["out"]
        for t in list(isa.q):
            hh.sell(isa, t, isa.q[t] * float(px[t]) * hh.R(rate)(t) * 2, px, rate, d)
        tax = max(0.0, isa.cash - isa.contrib - TAX["isa_free"]) * TAX["isa"]
        isa.cash -= tax
        isa.taxes += tax
        out.cash += isa.cash
        hh.books["isa"] = Book("isa", opened=d, taxes=isa.taxes)
        self.extra["maturities"] += 1
        _invest_cash(hh, out, self.out_mix, d, px, rate)

    def signal(self, hh, d, px, rate, ctx):
        isa, out = hh.books["isa"], hh.books["out"]
        jobs = []
        if isa.opened is not None and d >= isa.opened + pd.DateOffset(years=self.years):
            jobs.append(self._mature)
        elif ctx["year_first"] and not ctx["first_day"]:
            if len(self.out_mix) > 1:  # 바깥은 1월 첫 거래일 맞춤(이전 전에)
                jobs.append(lambda hh, d, px, rate: hh.rebalance(hh.books["out"], self.out_mix, px, rate, d))
            jobs.append(self._transfer)
        if isa.cash > 1_000:
            jobs.append(lambda hh, d, px, rate: _invest_cash(hh, hh.books["isa"], self.isa_mix, d, px, rate))
        if out.cash > 1_000:
            jobs.append(lambda hh, d, px, rate: _invest_cash(hh, hh.books["out"], self.out_mix, d, px, rate))
        if ctx["month_last"] and len(self.isa_mix) > 1:
            jobs.append(lambda hh, d, px, rate: _rebalance_if_drift(hh, hh.books["isa"], self.isa_mix, self.band, px, rate, d))
        if self.harvest and ctx["month_last"] and d.month == 11:
            self.extra["harvests"] += 1
            jobs.append(lambda hh, d, px, rate: _harvest_job()(hh, d, px, rate, hh.books["out"]))
        return jobs


class Pension:
    """P1(보고 전용): 매달 입금은 연금(KSPX_N, 연 600만까지), 넘치면 바깥 SPY. 전년 납입 × 13.2% 환급금은 3월 첫 거래일 바깥 SPY."""

    def __init__(self, name: str, mode: str = "early", cap: float = 6_000_000.0):
        self.name, self.pension_mode, self.cap = name, mode, cap
        self.year_contrib: dict[int, float] = {}
        self.extra = {"refunds": 0.0}

    def books(self):
        return {"pen": Book("pension"), "out": Book("foreign")}

    def deposit(self, hh, amt, d, px, rate):
        pen, out = hh.books["pen"], hh.books["out"]
        used = self.year_contrib.get(d.year, 0.0)
        to_pen = max(0.0, min(amt, self.cap - used))
        pen.cash += to_pen
        pen.contrib += to_pen
        self.year_contrib[d.year] = used + to_pen
        out.cash += amt - to_pen

    def signal(self, hh, d, px, rate, ctx):
        pen, out = hh.books["pen"], hh.books["out"]
        jobs = []
        if ctx["month_first"] and d.month == 3:
            refund = self.year_contrib.get(d.year - 1, 0.0) * TAX["pension_credit"]
            if refund > 0 and not self.extra.get(f"r{d.year}"):
                out.cash += refund  # 세금 환급(바깥에서 들어온 돈이 아님 → 입금 기록에 안 셈)
                self.extra["refunds"] += refund
                self.extra[f"r{d.year}"] = True
        if pen.cash > 1_000:
            jobs.append(lambda hh, d, px, rate: _invest_cash(hh, hh.books["pen"], {"KSPX_N": 1.0}, d, px, rate))
        if out.cash > 1_000:
            jobs.append(lambda hh, d, px, rate: _invest_cash(hh, hh.books["out"], {"SPY": 1.0}, d, px, rate))
        return jobs
