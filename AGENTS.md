# AGENTS

Quant Auto Trade는 개인용 시장 현황·뉴스·전략 검증 앱(화면 Next.js 15 + TypeScript, 수집·분석 Python)입니다. 개발은 ai-orchestrator 엔진(`scripts/orch/`)이 계획 Issue를 스텝 단위로 Claude에게 구현시키는 방식입니다. **공개 저장소**입니다.

## 검수 기준 (Codex 독립 검수)

스텝 PR을 볼 때 다음을 확인하고, 문제는 파일·줄과 함께 적습니다.

1. **실데이터·비밀값 노출 (차단)** — 계좌번호·잔고·주문 금액·실제 보유 종목·API 키가 코드·테스트·문서·SUMMARY·로그 출력에 들어갔는지.
2. **주문 안전 (차단)** — 지시 없는 주문 코드, 기본값이 '주문함'인 스위치, 한도·킬 스위치 우회, 같은 리밸런싱일 중복 주문 가능성, 클라이언트에서 주문 키 사용.
3. **미래 데이터 사용 (차단)** — 백테스트·신호가 그날 이후 값을 쓰는지(공시일·발표일 무시, 당일 종가로 당일 체결 등).
4. **CLAUDE.md 규칙** — 지시받은 스텝만 했는지, `.github/`·`scripts/orch/` 수정, 테스트가 인터넷에 접속하는지.
5. **버그·테스트 누락** — 동작 오류, 경계값(휴장일·결측·분할), 예외 처리, 새 동작에 테스트 없음, `npm run typecheck`·`npm test`·`npm run build` 깨짐.

## 먼저 볼 파일

- [CLAUDE.md](./CLAUDE.md) — 구현 규칙
- [docs/PROJECT_PLAN.md](./docs/PROJECT_PLAN.md) — 목표·구조·데이터 소스·검증 절차
- [docs/ORCH_MANUAL.md](./docs/ORCH_MANUAL.md) — 운영 방식
