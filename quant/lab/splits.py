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


# 기본 구간(초안). 데이터가 쌓이면 사용자와 확정한다.
DEFAULT_SPLITS = Splits(dev=("2010-01-01", "2017-12-31"), valid=("2018-01-01", "2022-12-31"), holdout=("2023-01-01", None))
