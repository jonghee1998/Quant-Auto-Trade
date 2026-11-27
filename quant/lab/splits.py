"""개발·검증·홀드아웃 구간과 홀드아웃 잠금."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class HoldoutLocked(PermissionError):
    """홀드아웃은 final=True(최종 평가)로만, 전략당 한 번만 볼 수 있다."""


@dataclass(frozen=True)
class Splits:
    dev: tuple[str, str]
    valid: tuple[str, str]
    holdout: tuple[str, str | None]

    def period(self, name: str, final: bool = False) -> tuple[pd.Timestamp, pd.Timestamp | None]:
        if name == "holdout" and not final:
            raise HoldoutLocked("홀드아웃은 최종 평가 명령으로만 연다 (final=True)")
        if name not in ("dev", "valid", "holdout"):
            raise ValueError(f"알 수 없는 구간: {name}")
        s, e = getattr(self, name)
        return pd.Timestamp(s), (pd.Timestamp(e) if e else None)


# 과거 스트레스 구간(보고 전용 — 고르기에 쓰지 않는다, Fable 설계 #59). 수집 시세가 2005년 가을부터라 그 앞은 없음.
STRESS = ("2005-01-01", "2009-12-31")
# 검증 구간 안의 하락 세 번(통과 기준 5번: 두 번 이상 S&P보다 덜 빠졌나)
VALID_DRAWDOWNS = {"2018년 4분기": ("2018-09-20", "2018-12-31"), "2020년 2~3월": ("2020-02-19", "2020-04-30"),
                   "2022년": ("2022-01-03", "2022-12-31")}

# 기본 구간(초안). 데이터가 쌓이면 사용자와 확정한다.
# 3차(계획 #66)부터 개발 구간을 2004~2017로 넓힘(2008년 큰 하락 포함). 1·2차 기록은 2010~2017.
CRASH_2008 = ("2007-10-01", "2009-03-31")
DEFAULT_SPLITS = Splits(dev=("2004-01-01", "2017-12-31"), valid=("2018-01-01", "2022-12-31"), holdout=("2023-01-01", None))

# 4차(계획 #73): 환헤지(F) 묶음은 원화 자유변동 뒤 2000~02 하락을 넣어 1999년부터. R4_GL(긴 과거 확인)의 하락 다섯 번.
DEV_FX = ("1999-01-04", "2017-12-31")
GL_PERIOD = ("1980-01-02", "2003-12-31")
GL_CRASHES = {"1980-11~1982-08": ("1980-11-28", "1982-08-12"), "1990-07~10": ("1990-07-16", "1990-10-11"),
              "2000-03~2002-10": ("2000-03-24", "2002-10-09"), "2007-10~2009-03": ("2007-10-09", "2009-03-09"),
              "2020-02~03": ("2020-02-19", "2020-03-23")}
