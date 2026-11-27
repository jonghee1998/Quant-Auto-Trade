"""실험실 6차(Fable 설계 #85) 가계 정책. 달력·그날 종가의 계좌 상태·(G만) 200일선·실업률 첫 발표값.

- 절세 매도는 신호일(11월 마지막 거래일)에 팔 '수량'을 정하고 다음 거래일 종가에 달러끼리 갈아탄다(환전 비용 없음).
- Ladder: 매달 입금 → 그해 연금 600만까지 → ISA 한도(연 2천만·총 1억) → 나머지 바깥. 단계 켜고 끄기로 W1·W2·W3.
- InsideSwitch: ISA 또는 연금 '안에서만' G02 신호로 KSPX_N 100 ↔ 50:50(KUST_U). 갈아타도 세금 없음.
"""
from __future__ import annotations

import pandas as pd

from quant.lab.household import ISA_TOTAL, ISA_YEAR, TAX, Book, Household

from .rules import harvest_move
from .rules5 import _gain_ratio, _invest_cash


def harvest_signal(hh: Household, b: Book, px, rate, pair=("SPY", "IVV")):
    """신호일 상태로 팔 수량을 정한다. 반환: 다음 날 할 일(또는 None)."""
    R = hh.R(rate)
    vals = {t: b.q[t] * float(px[t]) * R(t) for t in b.q}
    ratio = {t: _gain_ratio(b, t, px, R) for t in b.q}
    if any(pd.isna(px.get(t, float("nan"))) for t in pair):
        return None
    mv = harvest_move(vals, ratio, b.realized_year, deduction=TAX["deduction"], pair=pair)
    if mv is None:
        return None
    a, c, amt = mv
    qty = amt / (float(px[a]) * R(a))

    def job(hh2: Household, d, px2, rate2, book_key=None):
        bb = hh2.books[book_key] if book_key else b
        hh2.swap(bb, a, c, qty, px2, rate2, d)
    return job, a, qty


class Harvest:
    """R6_H1: 해외 직접 S&P 보유 + 11월 말 절세 매도(수량 신호일 고정, 달러끼리 갈아타기)."""

    def __init__(self, name: str):
        self.name = name
        self.extra = {"harvests": 0}

    def books(self):
        return {"main": Book("foreign")}

    def deposit(self, hh, amt, d, px, rate):
        hh.books["main"].cash += amt

    def signal(self, hh, d, px, rate, ctx):
        b = hh.books["main"]
        jobs = []
        if b.cash > 1_000:
            jobs.append(lambda hh, d, px, rate: _invest_cash(hh, hh.books["main"], {"SPY": 1.0}, d, px, rate))
        if ctx["month_last"] and d.month == 11:
            h = harvest_signal(hh, b, px, rate)
            if h:
                self.extra["harvests"] += 1
                jobs.append(lambda hh, d, px, rate, j=h[0]: j(hh, d, px, rate, "main"))
        return jobs


class Ladder:
    """W1(연금→ISA→바깥), W2(연금→바깥), W3(ISA→바깥). 바깥은 SPY + 절세 매도. 환급금은 3월 첫 거래일(ISA 한도 있으면 ISA, 아니면 바깥)."""

    def __init__(self, name: str, pension: bool = True, isa: bool = True, isa_years: int = 5, pension_cap: float = 6_000_000.0,
                 credit: float | None = None, pension_mode: str = "early"):
        self.name, self.use_p, self.use_i, self.years, self.cap = name, pension, isa, isa_years, pension_cap
        self.credit = TAX["pension_credit"] if credit is None else credit
        self.pension_mode = pension_mode
        self.year_p: dict[int, float] = {}
        self.extra = {"refunds": 0.0, "maturities": 0, "transfers": 0, "harvests": 0}

    def books(self):
        b = {"out": Book("foreign")}
        if self.use_p:
            b["pen"] = Book("pension")
        if self.use_i:
            b["isa"] = Book("isa")
        return b

    def room(self, isa: Book, d) -> float:
        if isa.opened is None:
            return ISA_YEAR
        return max(0.0, min(ISA_TOTAL, ISA_YEAR * (d.year - isa.opened.year + 1)) - isa.contrib)

    def _to_isa(self, hh, amt, d) -> float:
        if not self.use_i or amt <= 0:
            return 0.0
        isa = hh.books["isa"]
        if isa.opened is None:
            isa.opened = d
        x = min(amt, self.room(isa, d))
        isa.cash += x
        isa.contrib += x
        return x

    def deposit(self, hh, amt, d, px, rate):
        left = amt
        if self.use_p:
            used = self.year_p.get(d.year, 0.0)
            x = max(0.0, min(left, self.cap - used))
            hh.books["pen"].cash += x
            hh.books["pen"].contrib += x
            self.year_p[d.year] = used + x
            left -= x
        left -= self._to_isa(hh, left, d)
        hh.books["out"].cash += left

    def _mature(self, hh, d, px, rate):
        isa, out = hh.books["isa"], hh.books["out"]
        for t in list(isa.q):
            hh.sell(isa, t, 0.0, px, rate, d, qty=isa.q[t])
        tax = max(0.0, isa.cash - isa.contrib - TAX["isa_free"]) * TAX["isa"]
        isa.cash -= tax
        out.cash += isa.cash
        hh.books["isa"] = Book("isa", opened=d, taxes=isa.taxes + tax)
        self.extra["maturities"] += 1
        _invest_cash(hh, out, {"SPY": 1.0}, d, px, rate)

    def _transfer(self, hh, d, px, rate):
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
        _invest_cash(hh, isa, {"KSPX_N": 1.0}, d, px, rate)

    def signal(self, hh, d, px, rate, ctx):
        jobs, out = [], hh.books["out"]
        if self.use_p and ctx["month_first"] and d.month == 3 and not self.extra.get(f"r{d.year}"):
            refund = self.year_p.get(d.year - 1, 0.0) * self.credit
            if refund > 0:
                self.extra[f"r{d.year}"] = True
                self.extra["refunds"] += refund
                left = refund - self._to_isa(hh, refund, d)
                out.cash += left
        if self.use_i:
            isa = hh.books["isa"]
            if isa.opened is not None and d >= isa.opened + pd.DateOffset(years=self.years):
                jobs.append(self._mature)
            elif ctx["year_first"] and not ctx["first_day"]:
                jobs.append(self._transfer)
            if isa.cash > 1_000:
                jobs.append(lambda hh, d, px, rate: _invest_cash(hh, hh.books["isa"], {"KSPX_N": 1.0}, d, px, rate))
        if self.use_p and hh.books["pen"].cash > 1_000:
            jobs.append(lambda hh, d, px, rate: _invest_cash(hh, hh.books["pen"], {"KSPX_N": 1.0}, d, px, rate))
        if out.cash > 1_000:
            jobs.append(lambda hh, d, px, rate: _invest_cash(hh, hh.books["out"], {"SPY": 1.0}, d, px, rate))
        if ctx["month_last"] and d.month == 11:
            h = harvest_signal(hh, out, px, rate)
            if h:
                self.extra["harvests"] += 1
                jobs.append(lambda hh, d, px, rate, j=h[0]: j(hh, d, px, rate, "out"))
        return jobs


class InsideSwitch:
    """R6_G1(ISA 안)·R6_G2(연금 안): 월말 G02 신호(SPY 200일선 아래 + 실업률 최신 > 직전 12개 평균) → 다음 거래일
    그 계좌 안만 KSPX_N 100 ↔ KSPX_N 50·KUST_U 50. 바깥은 안 건드림. base: R5_A4 구조(ISA 5년) 또는 R5_P1 구조(연금)."""

    def __init__(self, name: str, base, inside: str, spy: pd.Series, unrate: pd.DataFrame, switch: bool = True):
        self.name, self.base, self.inside, self.spy, self.u, self.switch = name, base, inside, spy, unrate, switch
        self.avoid = False
        self.extra = {"signals": 0, "events": []}
        self.pension_mode = getattr(base, "pension_mode", "early")

    def books(self):
        return self.base.books()

    def deposit(self, hh, amt, d, px, rate):
        self.base.deposit(hh, amt, d, px, rate)

    def _target(self, d) -> bool:
        s = self.spy.loc[:d].dropna()
        if len(s) < 200 or d not in self.u.index:
            return False
        lat, prev = self.u.at[d, "latest"], self.u.at[d, "prev_mean"]
        if pd.isna(lat) or pd.isna(prev):
            return False
        return bool(s.iloc[-1] < s.iloc[-200:].mean() and lat > prev)

    def _mix(self):
        return {"KSPX_N": 0.5, "KUST_U": 0.5} if self.avoid else {"KSPX_N": 1.0}

    def signal(self, hh, d, px, rate, ctx):
        jobs = self.base.signal(hh, d, px, rate, ctx) or []
        key = self.inside
        if key in hh.books:
            b = hh.books[key]
            # 바탕 정책이 계좌 안 현금을 KSPX_N 100으로 사는 일을 이 계좌의 목표 비중으로 바꿔 끼운다(피함일 때)
            if self.switch and ctx["month_last"]:
                want = self._target(d)
                if want != self.avoid:
                    self.avoid = want
                    self.extra["signals"] += 1
                    self.extra["events"].append((str(d.date()), "피함" if want else "보유"))
                    mix = self._mix()
                    jobs.append(lambda hh, d, px, rate, mix=mix, k=key: hh.rebalance(hh.books[k], mix, px, rate, d))
            if self.avoid and b.cash > 1_000:
                mix = self._mix()
                jobs.append(lambda hh, d, px, rate, mix=mix, k=key: hh.rebalance(hh.books[k], mix, px, rate, d))
        return jobs
