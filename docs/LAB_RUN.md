# 실험실 운영 (아이디어 → 검토 → 계획 → 실행)

| 하는 일 | 방법 | 누가 |
|---|---|---|
| 아이디어 넣기 | Issue를 쓰고 `lab:idea` 라벨 | 나(저장소 주인만 동작) |
| 검토 | `lab-idea` 워크플로가 Fable 검토 댓글(판정·다듬은 가설·주의·겹침·시험 계획) | Fable(ORCH_FABLE off면 Opus) |
| 시험 승인 | `lab:approve` 라벨 → `[plan] 실험: …` Issue 생성 → plan-review → 엔진 구현 | 나 / 자동 아이디어는 '시험할 만함'이면 자동 |
| 실행 | Actions → `lab-run` → 전략 이름·dev/valid·Issue 번호 → 결과 표가 댓글로 | 코드(AI 아님), DB 필요 |
| 자동 아이디어 | 변수 `LAB_AUTO=on`이면 매주 월 09:23 KST Fable이 2개 제출(`lab:auto`) | Fable |

- 월 실험 계획 상한: 변수 `LAB_MONTHLY_PLANS`(기본 10). 시도 수는 `experiments` 표에 쌓이고 우연 보정(DSR)에 쓰인다.
- 홀드아웃(최종)은 `lab-run`으로 돌리지 않는다. 사람이 따로 승인한다.
- 등록 전략: `quant/strategies/__init__.py`의 `REGISTRY` (지금: trend_filter, sector_momentum, buy_and_hold).
