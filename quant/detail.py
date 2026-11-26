"""종목·지표 상세 화면용 값(매일 스냅샷 뒤). item_detail 테이블에 키별 최신 한 줄씩.

키: 'US:XLK', 'KR:005930', 'W:EWJ'(나라 ETF), 'Q:vix'(홈 지표).
홈 payload를 가볍게 두려고 차트·통계는 여기 따로 둔다(상세 화면이 한 줄만 읽음).
"""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd


def _f(x, nd: int = 2) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(v) else round(v, nd)


def weekly_chart(s: pd.Series, days: int = 365) -> list[list]:
    """최근 days일을 주 단위(금요일 종가)로. [날짜, 값]."""
    s = s.dropna()
    if s.empty:
        return []
    s = s[s.index >= s.index[-1] - pd.Timedelta(days=days)]
    w = s.resample("W-FRI").last().dropna()
    pts = [[d.strftime("%Y-%m-%d"), _f(v, 4)] for d, v in w.items()]
    if pts:  # 마지막 주는 아직 금요일이 안 왔을 수 있다 → 실제 마지막 날짜로(미래 날짜 표시 금지)
        pts[-1] = [s.index[-1].strftime("%Y-%m-%d"), _f(s.iloc[-1], 4)]
    return pts


def price_stats(s: pd.Series, bench: pd.Series | None = None) -> dict:
    """최근 1년(252거래일): 변동성(연환산 %), 최대 낙폭(%), 52주 최고·최저·위치(%), 200일선 대비(%), 베타."""
    s = s.dropna()
    y = s.iloc[-252:]
    out: dict = {"days": int(len(y))}
    if len(y) < 20:
        return out
    r = y.pct_change().dropna()
    hi, lo, last = y.max(), y.min(), y.iloc[-1]
    out.update({
        "vol": _f(r.std() * np.sqrt(252) * 100, 1),
        "mdd": _f((y / y.cummax() - 1).min() * 100, 1),
        "high": _f(hi), "low": _f(lo),
        "pos": _f((last - lo) / (hi - lo) * 100, 0) if hi > lo else None,
        "ma200": _f((last / s.iloc[-200:].mean() - 1) * 100, 1) if len(s) >= 200 else None,
    })
    if bench is not None:
        rb = bench.dropna().pct_change()
        both = pd.concat([r, rb], axis=1, join="inner").dropna()
        if len(both) >= 60 and both.iloc[:, 1].var() > 0:
            out["beta"] = _f(both.iloc[:, 0].cov(both.iloc[:, 1]) / both.iloc[:, 1].var(), 2)
    return out


def level_stats(s: pd.Series) -> dict:
    """지표(VIX·환율 등): 1년 중 위치, 10년 평균·최고·최저."""
    s = s.dropna()
    if s.empty:
        return {}
    last = s.iloc[-1]
    y1 = s[s.index >= s.index[-1] - pd.Timedelta(days=365)]
    y10 = s[s.index >= s.index[-1] - pd.Timedelta(days=3652)]
    hi, lo = y1.max(), y1.min()
    return {"pos": _f((last - lo) / (hi - lo) * 100, 0) if hi > lo else None, "high1": _f(hi), "low1": _f(lo),
            "avg10": _f(y10.mean()), "max10": _f(y10.max()), "min10": _f(y10.min()),
            "years": _f((y10.index[-1] - y10.index[0]).days / 365.25, 1)}


def fundamentals_view(rows: pd.DataFrame, price: float | None) -> dict:
    """미국 SEC 재무 → 분기 매출·순이익(최근 8분기, 전년 같은 분기 대비), PER(최근 연간 EPS), PBR.
    rows: concept, period_start, period_end, value, filed_date. 같은 기간은 가장 늦게 접수된 값(정정 반영)."""
    if rows.empty:
        return {}
    rows = rows.copy()
    for c in ("period_start", "period_end", "filed_date"):
        rows[c] = pd.to_datetime(rows[c])
    rows["len"] = (rows["period_end"] - rows["period_start"]).dt.days
    rows = rows.sort_values("filed_date").drop_duplicates(["concept", "period_start", "period_end"], keep="last")
    # 4분기는 연간 보고서에만 있다 → 1년 − 같은 해 시작의 9개월 누적. 접수일은 연간 보고서 날짜(그 전엔 몰랐다)
    annual = rows[rows["len"].between(350, 380)]
    nine = rows[rows["len"].between(260, 280)]
    q4 = annual.merge(nine, on=["concept", "period_start"], suffixes=("", "_9"))
    if len(q4):
        q4 = q4.assign(period_start=q4["period_end_9"] + pd.Timedelta(days=1), value=q4["value"] - q4["value_9"])
        q4 = q4.assign(len=(q4["period_end"] - q4["period_start"]).dt.days)[rows.columns]
        rows = pd.concat([rows, q4[q4["len"].between(80, 100)]], ignore_index=True)
        rows = rows.drop_duplicates(["concept", "period_start", "period_end"], keep="first")

    def quarters(concept: str) -> pd.Series:
        q = rows[(rows["concept"] == concept) & rows["len"].between(80, 100)]
        out = q.set_index("period_end")["value"].sort_index()
        out.index = pd.DatetimeIndex(out.index)
        return out

    out: dict = {"quarters": []}
    rev, ni, op = quarters("revenue"), quarters("net_income"), quarters("op_income")
    for d in rev.index[-8:]:
        prev = rev[(rev.index >= d - pd.Timedelta(days=380)) & (rev.index <= d - pd.Timedelta(days=350))]
        out["quarters"].append({
            "end": d.strftime("%Y-%m-%d"), "revenue": _f(rev[d], 0), "netIncome": _f(ni.get(d), 0), "opIncome": _f(op.get(d), 0),
            "revYoY": _f((rev[d] / prev.iloc[-1] - 1) * 100, 1) if len(prev) and prev.iloc[-1] > 0 else None})
    eps = rows[(rows["concept"] == "eps_diluted") & rows["len"].between(350, 380)].sort_values("period_end")
    if price and len(eps) and eps["value"].iloc[-1] > 0:
        out["per"] = _f(price / eps["value"].iloc[-1], 1)
        out["epsYear"] = eps["period_end"].iloc[-1].strftime("%Y")
    eq = rows[rows["concept"] == "equity"].sort_values("period_end")
    sh = rows[rows["concept"] == "shares"].sort_values("period_end")
    if price and len(eq) and len(sh) and sh["value"].iloc[-1] > 0 and eq["value"].iloc[-1] > 0:
        out["pbr"] = _f(price / (eq["value"].iloc[-1] / sh["value"].iloc[-1]), 1)
    out["filed"] = rows["filed_date"].max().strftime("%Y-%m-%d")
    return out


# 지표 상세 '관련 지표': (id, 이름, FRED 시리즈, 상태 문구 함수)
RELATED = [
    ("NFCI", "금융 여건(NFCI)", lambda v: "돈 구하기 쉬움" if v < 0 else "돈줄이 조이는 중"),
    ("VIXCLS", "불안 지수 VIX(1개월)", lambda v: "평소 수준" if v < 20 else "불안" if v < 30 else "공포"),
    ("VXVCLS", "불안 지수 VIX(3개월)", lambda v: "평소 수준" if v < 22 else "불안"),
    ("BAMLH0A0HYM2", "회사채 위험 가산금리(하이일드)", lambda v: "낮음(안심)" if v < 4 else "보통" if v < 6 else "높음(위험 회피)"),
    ("T10Y2Y", "장단기 금리차(10년−2년)", lambda v: "정상(장기가 더 높음)" if v > 0 else "역전(경기 둔화 신호로 봄)"),
    ("T10Y3M", "장단기 금리차(10년−3개월)", lambda v: "정상" if v > 0 else "역전"),
    ("DGS10", "미국 10년 국채 금리", lambda v: f"{v:.2f}%"),
    ("DFF", "미국 기준금리(실효)", lambda v: f"{v:.2f}%"),
]


def related(macro: dict[str, pd.Series]) -> list[dict]:
    out = []
    for sid, name, say in RELATED:
        s = macro.get(sid, pd.Series(dtype=float)).dropna()
        if s.empty:
            continue
        v = float(s.iloc[-1])
        prev = s[s.index <= s.index[-1] - pd.Timedelta(days=28)]
        out.append({"id": sid, "name": name, "value": _f(v), "state": say(v), "date": s.index[-1].strftime("%Y-%m-%d"),
                    "m1": _f(v - prev.iloc[-1]) if len(prev) else None})
    return out


def build(payload: dict, us: pd.DataFrame, kr: pd.DataFrame, macro_long: dict[str, pd.Series],
          fundamentals: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """상세 화면 값 전부. us·kr: 종가 표(열=코드), macro_long: 10년치 지표."""
    from .snapshot import QUOTE_DEFS
    out: dict[str, dict] = {}
    bench = {"US": us.get("SPY"), "W": us.get("SPY"), "KR": kr.get("KOSPI") if "KOSPI" in kr else kr.get("069500")}
    for u in payload.get("universe", []):
        px = us if u["market"] in ("US", "W") else kr
        if u["code"] not in px:
            continue
        s = px[u["code"]]
        d = {"chart": weekly_chart(s), "stats": price_stats(s, bench.get(u["market"]))}
        f = fundamentals.get((u["market"], u["code"])) if u.get("kind") == "주식" else None
        if f is not None and not f.empty:
            d["fund"] = fundamentals_view(f, _f(s.dropna().iloc[-1]))
        out[f"{u['market']}:{u['code']}"] = d
    rel = related(macro_long)
    for qid, _name, kind, src in QUOTE_DEFS:
        s = (us.get(src) if kind == "etf" else kr.get(src) if kind == "kr" else macro_long.get(src))
        if s is None or s.dropna().empty:
            continue
        out[f"Q:{qid}"] = {"chart": weekly_chart(s), "level": level_stats(s), "related": [r for r in rel if r["id"] != src]}
    return out


def save(conn, details: dict[str, dict], day: date) -> int:
    with conn.cursor() as cur:
        cur.executemany(
            """insert into item_detail (key, date, data) values (%s, %s, %s)
               on conflict (key) do update set date = excluded.date, data = excluded.data""",
            [(k, day, json.dumps(v, ensure_ascii=False)) for k, v in details.items()])
    conn.commit()
    return len(details)


def load_inputs(conn, kr_codes: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    """상세 계산용: 미국·나라 ETF/주식 2년, 한국(화면 종목·지수만 — 전 종목은 너무 큼) 2년, 지표 10년, 미국 주식 재무."""
    from .ingest.universe import US_STOCKS
    with conn.cursor() as cur:
        cur.execute("""select i.market, i.code, p.date, p.close * p.adj_factor from prices_daily p
                       join instruments i on i.id = p.instrument_id
                       where p.date >= current_date - 730 and (i.market <> 'KR' or i.code = any(%s))""", (kr_codes,))
        px = pd.DataFrame(cur.fetchall(), columns=["market", "code", "date", "close"])
        cur.execute("""select distinct on (series, ref_date) series, ref_date, value from macro_series
                       where ref_date >= current_date - 3660 order by series, ref_date, release_date desc""")
        mc = pd.DataFrame(cur.fetchall(), columns=["series", "date", "value"])
        cur.execute("""select market, code, concept, period_start, period_end, value, filed_date from fundamentals
                       where ((market = 'US' and code = any(%s)) or (market = 'KR' and code = any(%s)))
                         and filed_date >= current_date - 1500""", (list(US_STOCKS), kr_codes))
        fd = pd.DataFrame(cur.fetchall(), columns=["market", "code", "concept", "period_start", "period_end", "value", "filed_date"])

    def table(m):
        p = px[px["market"] == m]
        if p.empty:
            return pd.DataFrame()
        t = p.pivot_table(index="date", columns="code", values="close", aggfunc="last").sort_index()
        t.index = pd.to_datetime(t.index)
        return t
    macro = {k: g.set_index(pd.to_datetime(g["date"]))["value"].sort_index() for k, g in mc.groupby("series")} if len(mc) else {}
    return table("US"), table("KR"), macro, {k: g.drop(columns=["market", "code"]) for k, g in fd.groupby(["market", "code"])}
