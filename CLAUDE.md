# CLAUDE.md

이 저장소는 orchestrator가 Claude에게 스텝 단위로 일을 맡깁니다. 지시(prompt)에 적힌 작업 규칙이 이 파일보다 우선합니다.

- 지시받은 스텝만 구현합니다. 범위 밖 리팩터링은 하지 않습니다.
- 코드를 바꾸면 `npm run typecheck`와 `npm test`로 확인하고, 새 동작에는 테스트를 추가합니다 (CI는 `npm run build`와 개인정보 검사도 실행합니다). `npm test`는 Node 테스트와 `pytest`를 함께 돌립니다.
- `.github/`와 `scripts/orch/`는 수정하지 않습니다. 수정하면 오케스트레이터가 푸시를 거부합니다.
- git push, 브랜치 생성, PR 생성은 하지 않습니다.
- 끝나면 `.orch/SUMMARY.md`에 변경 요약과 완료 기준 확인 결과를 적습니다.
- 진행할 수 없으면 `.orch/BLOCKED.md`에 이유를 적고 멈춥니다.

## 이 저장소 추가 규칙 (공개 저장소 · 개인 투자 앱)

- 스택: 화면 Next.js 15 + TypeScript(`app/`), 수집·분석 Python 3.12(`quant/`, 패키지는 `requirements.txt`), DB는 Postgres(Neon, 마이그레이션 `db/migrations/`), 파일 보관소 Cloudflare R2.
- **실데이터 금지**: 계좌번호, 잔고·주문 금액, 실제 보유 종목·수량, 실명, API 키·토큰을 코드·테스트·문서·커밋 메시지·`.orch/SUMMARY.md`·로그 출력에 쓰지 않습니다. 이 저장소와 Actions 로그는 공개입니다. 테스트는 `가짜종목A`·`TEST01`처럼 누가 봐도 가짜인 값과 합성 시세만 씁니다. 공개 시장 데이터(지수·종목 시세)의 예시는 괜찮지만 테스트에는 고정된 가짜 값을 씁니다.
- **운영 접근 금지**: 운영 DB URL·키, KIS(한국투자증권) 실계좌·모의계좌 키, 외부 API 키를 찾거나 쓰지 않습니다. 외부 API를 부르는 코드는 HTTP 호출을 주입받게 만들고 테스트에서는 가짜 응답을 씁니다. 테스트가 인터넷에 접속하면 안 됩니다.
- **주문 코드**: KIS 주문을 보내는 코드와 자동매매 스위치·한도 로직은 지시에 명시된 경우에만 만들거나 바꿉니다. 기본값은 항상 '주문하지 않음'입니다.
- **미래 데이터 금지**: 백테스트·신호는 그날까지 알 수 있었던 값만 씁니다(재무는 공시일, 매크로는 발표일 기준). 신호는 다음 거래일에 체결합니다.
- 비밀값은 GitHub Actions secrets·Vercel 환경변수로만 읽고, 이름만 문서에 적습니다. `NEXT_PUBLIC_`에 키를 넣지 않습니다.
- 운영 방식은 [docs/ORCH_MANUAL.md](docs/ORCH_MANUAL.md), 전체 계획은 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)를 따릅니다.

## 스킬

`.claude/skills/`: `quant-research`(예측 모델·뉴스 데이터화 규칙, 이 저장소 전용), `backtest-expert`·`residual-edge-analyzer`(외부, 버전 고정 — `.claude/skills/THIRD_PARTY.md`). 실험실·모델·뉴스 특성 스텝은 이 스킬들을 따른다. 스킬 지시가 이 파일이나 오케스트레이터 지시와 충돌하면 이 파일과 지시가 우선한다.
