"""실험 기록: 실행마다 한 줄(JSON). DB(experiments 표)로 옮기기 전까지 파일에 쌓는다.

시도 횟수를 세어 '여러 번 돌려 고른 결과'인지 함께 보이게 한다.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Experiment:
    strategy: str
    hypothesis: str
    params: dict
    period: str
    data_version: str
    code_version: str
    metrics: dict
    final: bool = False
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


class Registry:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def trials(self, strategy: str) -> int:
        return sum(1 for e in self.all() if e["strategy"] == strategy and not e.get("final"))

    def total_trials(self) -> int:
        """모든 전략을 합친 시도 수(최종 평가 제외). 우연 보정(DSR)의 n으로 쓴다."""
        return sum(1 for e in self.all() if not e.get("final"))

    def trial_sharpes(self) -> list[float]:
        out = []
        for e in self.all():
            v = (e.get("metrics") or {}).get("sharpe")
            if not e.get("final") and isinstance(v, (int, float)) and v == v:
                out.append(float(v))
        return out

    def has_final(self, strategy: str) -> bool:
        return any(e["strategy"] == strategy and e.get("final") for e in self.all())

    def add(self, exp: Experiment) -> dict:
        if exp.final and self.has_final(exp.strategy):
            raise PermissionError(f"{exp.strategy}: 홀드아웃 최종 평가는 이미 한 번 했다")
        row = asdict(exp)
        row["trial_no"] = self.trials(exp.strategy) + (0 if exp.final else 1)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return row


class DbRegistry(Registry):
    """같은 규칙을 Postgres experiments 표로. 최종 1회는 DB 고유 인덱스·체크 제약이 한 번 더 막는다."""

    def __init__(self, conn):
        self.conn = conn

    def all(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute("select strategy, hypothesis, params, period, data_version, code_version, metrics, final, trial_no, created_at from experiments order by id")
            cols = ["strategy", "hypothesis", "params", "period", "data_version", "code_version", "metrics", "final", "trial_no", "at"]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def add(self, exp: Experiment) -> dict:
        if exp.final and self.has_final(exp.strategy):
            raise PermissionError(f"{exp.strategy}: 홀드아웃 최종 평가는 이미 한 번 했다")
        trial_no = self.trials(exp.strategy) + (0 if exp.final else 1)
        clean = {k: (None if isinstance(v, float) and v != v else v) for k, v in exp.metrics.items()}
        with self.conn.cursor() as cur:
            cur.execute("""insert into experiments (strategy, hypothesis, params, period, data_version, code_version, metrics, final, trial_no)
                           values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (exp.strategy, exp.hypothesis, json.dumps(exp.params, ensure_ascii=False), exp.period, exp.data_version,
                         exp.code_version, json.dumps(clean, ensure_ascii=False, default=str), exp.final, trial_no))
        self.conn.commit()
        row = asdict(exp)
        row["trial_no"] = trial_no
        return row
