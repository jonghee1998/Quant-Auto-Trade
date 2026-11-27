"""국내 시세 자료 점검: 표본(해시), 점프 설명, 관문 판정, 출력. 가짜 응답·가짜 시세만, 인터넷 없음."""
import json
from datetime import date
from types import SimpleNamespace

import pandas as pd

from quant.ingest.http import Response
from quant.lab import kr_probe as K

KEY = "FAKEKEY-12345678"


def series(closes, caps=None, rates=None, start="2009-06-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    df = pd.DataFrame({"Close": closes, "Amount": [1.0] * len(closes)}, index=idx)
    if caps is not None:
        df["MarCap"] = caps
    if rates is not None:
        df["ChangeRate"] = rates
    return df


def listing():
    return pd.DataFrame({
        "Symbol": ["900001", "900002", "900003", "900004", "90000A"],
        "Name": ["가짜종목A", "가짜종목B", "가짜스팩1호", "가짜종목D", "가짜종목E"],
        "SecuGroup": ["주권", "주권", "주권", "주권", "주권"],
        "ListingDate": ["2001-01-02", "2012-05-02", "2015-01-02", "1999-01-04", "2001-01-02"],
        "DelistingDate": ["2015-03-02", "2020-06-01", "2018-01-02", "2005-06-01", "2015-03-02"],
    })


def test_gone_sample_filters_window_spac_and_code_then_hash_order():
    s = K.gone_sample(listing(), 10)
    assert set(s["Symbol"]) == {"900001", "900002"}       # 스팩·2006 이전 폐지·6자리 숫자 아님은 빠짐
    assert list(s["Symbol"]) == sorted(s["Symbol"], key=K.key_of)
    assert len(K.gone_sample(listing(), 1)) == 1 and len(K.gone_sample(pd.DataFrame(), 5)) == 0


def test_series_stats_counts_jumps_and_explanations():
    closes = [100.0] * 15 + [50.0] * 15 + [20.0] * 15          # 두 번의 점프(정리매매 꼬리 10일 앞)
    caps = [1000.0] * 30 + [400.0] * 15                        # 첫 점프만 시가총액 불변(분할)
    rates = [0.0] * 15 + [0.0] + [0.0] * 14 + [-0.6] + [0.0] * 14
    st = K.series_stats(series(closes, caps, rates))
    assert (st["rows"], st["jumps"], st["by_cap"], st["by_rate"], st["has_amount"]) == (45, 2, 1, 1, True)
    assert st["first"] == date(2009, 6, 1)
    assert K.series_stats(None)["rows"] == 0 and K.series_stats(pd.DataFrame())["jumps"] == 0


def test_tail_moves_are_not_counted_as_jumps():
    st = K.series_stats(series([100.0] * 40 + [10.0] * 5))   # 마지막 10일 안의 급락(정리매매)
    assert st["jumps"] == 0


class Portal:
    """공공데이터포털 가짜: 2020년부터만 자료가 있고, 과거 날짜에는 지금 없는 종목이 하나 있다."""
    def __init__(self):
        self.calls = []

    def __call__(self, url, params=None, headers=None):
        p = dict(params or {})
        self.calls.append(p)
        if "beginBasDt" in p:
            y = int(p["beginBasDt"][:4])
            if p["beginBasDt"][4:] == "0101":
                items = [{"basDt": f"{y}0103", "srtnCd": "900010", "clpr": "100", "trPrc": "5"}] if y >= 2020 else []
            else:
                items = [{"basDt": "20261120", "srtnCd": "900010", "clpr": "100", "trPrc": "5"}]
            return self._ok(items, 2000 if items else 0)
        codes = ["900010", "900011"] if p["basDt"] == "20200103" else ["900010", "900012", "900013"]
        return self._ok([{"basDt": p["basDt"], "srtnCd": c, "itmsNm": "가짜", "clpr": "100"} for c in codes], len(codes))

    @staticmethod
    def _ok(items, total):
        return Response(200, json.dumps({"response": {"body": {"items": {"item": items}, "totalCount": total}}}))


def test_portal_reads_first_year_gone_codes_and_amount():
    p = K.portal(Portal(), KEY, date(2026, 11, 27))
    assert p["first_year"] == 2020 and p["years"][2010]["count"] == 0
    assert (p["early_n"], p["early_gone"], p["recent_n"], p["has_amount"]) == (2, 1, 3, True)


def fake_src(delisted=None, live=None, fail=False):
    def boom():
        raise RuntimeError("https://example.invalid/?serviceKey=" + KEY)
    good = series([100.0] * 300)
    return SimpleNamespace(listing=boom if fail else listing,
                           delisted=delisted or (lambda c, s, e: good),
                           live=live or (lambda c, s, e: good.iloc[:5]))


def test_long_history_and_gates_pass_when_data_is_there():
    live = [f"{900100 + i}" for i in range(40)]
    h = K.long_history(fake_src(), 10, live, sleep=lambda s: None)
    assert (h["sample"], h["covered"], h["pre2010"], h["pre2010_ok"]) == (2, 2, 1, 1)
    assert h["live_n"] == 30 and h["live_2010"] == 30
    g = K.gates({"first_year": 2020}, h)
    assert g == {"start": True, "gone": True, "adjust": True, "all": True}


def test_gates_fail_when_delisted_prices_are_missing_or_unexplained():
    empty = K.long_history(fake_src(delisted=lambda c, s, e: pd.DataFrame()), 10, [], sleep=lambda s: None)
    assert K.gates({"first_year": 2020}, empty) == {"start": False, "gone": False, "adjust": False, "all": False}
    jumpy = series([100.0] * 100 + [10.0] * 100, caps=[1000.0] * 100 + [100.0] * 100)
    h = K.long_history(fake_src(delisted=lambda c, s, e: jumpy), 10, [], sleep=lambda s: None)
    assert h["jumps"] == 2 and K.gates({"first_year": 2005}, h)["adjust"] is False
    assert K.gates({"first_year": 2005}, h)["start"] is True      # 포털이 2010년 이전부터 있으면 시작 연도는 통과


def test_run_prints_verdict_without_key_or_codes_even_when_calls_fail():
    out = K.run(Portal(), KEY, fake_src(fail=True), date(2026, 11, 27), 10, sleep=lambda s: None)
    assert "관문: 미달" in out and "RuntimeError 1건" in out
    assert KEY not in out and "900010" not in out and "example.invalid" not in out
    assert "DATA_GO_KR_KEY 없음" in K.run(None, "", fake_src(), date(2026, 11, 27), 10, sleep=lambda s: None)
