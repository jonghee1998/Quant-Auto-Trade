# PM 인수인계

_마지막 갱신: 2026-11-27 (실험실 방향 전환·국내 자료 점검)_

## 현재 상태
- 엔진이 아직 멈춰 있어(Claude 토큰·codex-login·ORCH_PAUSED) PM이 직접 PR로 만들었다:
  - 수집: `quant/ingest/`(Tiingo·FRED·공공데이터포털·네이버·Finnhub·SEC EDGAR), 매일 `ingest.yml`(키 없는 소스 건너뜀) → `quant.snapshot`이 화면 요약을 `daily_brief`에 저장. 비밀값 이름: `docs/DATA_SOURCES.md`.
  - DB: `db/migrations/0001_init.sql`, `0002_fundamentals.sql` + CI Postgres 테스트.
  - 화면: 시안(https://claude.ai/artifact/EX1zt5fa8FBmd3D58fzob5) 그대로 Next.js 프로토타입. `lib/source.ts`가 DB 있으면 실데이터, 없으면 예시 값. 시장(오늘·트렌드)·투자(실험실·백테스트·투자) 2탭.
  - 실험실: `quant/lab/`(백테스트·포착률·회복·DSR·DB 기록), `quant/strategies/`(trend_filter, sector_momentum), `lab-run.yml`, 아이디어 흐름 `lab-idea.yml`(사용법 `docs/LAB_RUN.md`, 원칙 `docs/LAB.md`).
  - 계산: `quant/market.py`(추세 신호등·업종 폭·상대강도·평소 대비), `quant/news_features.py`(16:00 ET 경계·중복·건수 급증).
  - 스킬: `.claude/skills/`(quant-research, backtest-expert, residual-edge-analyzer). 리서치: `docs/research/`.
- 엔진 Fable 지원(`model: "fable"`, `ORCH_FABLE`)은 AO #374·PD #136·Quant #3.

## 결정한 것 (사용자)
- 기준선은 미국 상장 S&P 500 ETF 보유(세후·원화). 개별주·ETF 둘 다 검증. 2026-11-27: 국내 시장도 실험 대상(양도세 없음), 세금·계좌 구조 묶음은 닫고 '자동으로 돌아가는 수익 로직'만 설계한다.
- 저장소 공개, 내부 데이터는 DB에 두고 토큰으로 접근. DB는 Neon 무료, 파일은 R2.
- 뉴스 요약에 유료 AI 쓰지 않음. 기존 GCP 앱은 다 끝난 뒤 종료.
- 화면은 개발 전에 시안을 먼저 보여 주고 승인받는다.
- 실전 매매(6단계)와 주문 코드 변경은 자동 모드여도 사람이 승인한다.

## 다음 할 일
0. 실험실: 7차(설계 #93 → 판정 #96) 끝 — 9개 모두 탈락, 검증 안 엶. 누적 시도 92. 다음은 판정 #96 순서: #74(미국 종목 순위 모델) 백필이 끝나면 0단계 관문 확인 → 국내 갈아타기는 새 자료 출처가 있을 때만(#92) → 목표 재정의는 사용자 결정. 갈아타기류는 '세금 0' 조건에서 정적 보유를 먼저 이겨야 한다.
1. 사람: Claude 토큰·codex-login·`ORCH_PAUSED` 삭제, 데이터 키(DATABASE_URL·TIINGO_TOKEN·FRED_API_KEY·DATA_GO_KR_KEY·NAVER_*·FINNHUB_TOKEN·SEC_USER_AGENT), Vercel 연결(0.13, 서버 환경변수 DATABASE_URL).
2. PM: 키가 들어오면 `ingest` 수동 실행(days=400) → `lab-run trend_filter dev`로 첫 실측 → 결과를 투자 탭에 연결.
3. 엔진 가동 후 계획: 휴장일 달력, 한국 지수·업종, 화면의 종목 상세(통계·재무) 실데이터, 투자 탭을 experiments 표와 연결, 모의투자(KIS 모의) 실행 확인.

## 계획 작성 체크리스트
- 실제 코드 확인, 기존 테스트 충돌, 기계로 확인할 수 있는 done_when, 실패·경계 경우(휴장일·결측·분할·호출 제한).
- 테스트는 인터넷 없이(HTTP 주입 + 가짜 응답). 실데이터·키 금지.
- 보호 경로(`.github/`·`scripts/orch/`) 변경은 PM PR.
