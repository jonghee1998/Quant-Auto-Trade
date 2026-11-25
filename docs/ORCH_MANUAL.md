# 오케스트레이터 운영 매뉴얼

이 저장소는 [ai-orchestrator](https://github.com/jonghee1998/ai-orchestrator) 엔진을 그대로 씁니다. 운영 방법(계획 Issue, `orch:go`, ON/OFF, 승인, 멈췄을 때)은 원본 매뉴얼을 따릅니다: https://github.com/jonghee1998/ai-orchestrator/blob/main/docs/ORCH_MANUAL.md

이 저장소만의 차이: 공개 저장소라 실데이터·비밀값 금지(CLAUDE.md), CI에 개인정보 검사(`scripts/orch/pii-scan.mjs`), Python 패키지(`requirements.txt`)를 구현·검수·CI 환경이 설치합니다. 사용량 측정·아이디어함은 ai-orchestrator에서만 합니다.

## 자동 모드 (`ORCH_AUTO`)

상황판(ai-orchestrator) AI 팀 탭의 **자동 모드** 스위치로 켜고 끕니다. 규칙은 [ai-orchestrator 매뉴얼 '자동 모드'](https://github.com/jonghee1998/ai-orchestrator/blob/main/docs/ORCH_MANUAL.md#자동-모드-orch_auto-상황판-ai-팀-탭-스위치)를 따릅니다. 단, 이 저장소에서는 실전 매매(6단계)와 주문 코드 변경은 사람이 승인합니다.
