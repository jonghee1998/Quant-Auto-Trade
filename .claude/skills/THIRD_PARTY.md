# 외부 스킬 (원문 그대로, 버전 고정)

| 스킬 | 출처 | 커밋 | 라이선스 |
|---|---|---|---|
| backtest-expert | https://github.com/tradermonty/claude-trading-skills/tree/main/skills/backtest-expert | 4080042 | MIT (각 폴더 LICENSE) |
| residual-edge-analyzer | https://github.com/tradermonty/claude-trading-skills/tree/main/skills/residual-edge-analyzer | 4080042 | MIT |

- 원문과 다른 점: `backtest-expert/scripts/evaluate_backtest.py` 48행 끝에 `# pii-allow` 주석 추가(부동소수 예시가 카드번호 패턴으로 오탐).
- 두 스킬 모두 표준 라이브러리만 쓰고 네트워크 호출이 없다(PM 검토, 2026-11-25).
- 원문의 `python3 skills/<이름>/scripts/...` 경로는 이 저장소에서 `.claude/skills/<이름>/scripts/...`이다.
- 이 저장소의 규칙(CLAUDE.md, docs/LAB.md)과 충돌하면 저장소 규칙이 우선한다. 예: 원문의 Deploy/Refine/Abandon은 우리 단계(백테스트 후보 → 모의 실행 확인 → 사람 승인)로 읽는다.
- 갱신은 PM PR로만, 이 표의 커밋을 함께 바꾼다.
