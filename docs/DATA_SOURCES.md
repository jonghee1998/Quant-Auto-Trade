# 데이터 소스와 비밀값

수집 코드: `quant/ingest/` · 매일 실행: `.github/workflows/ingest.yml`(한국시간 14:37, 수동 실행 가능).
비밀값은 GitHub → Settings → Secrets and variables → Actions → **Secrets**에만 넣는다. 없는 키의 소스는 건너뛴다.

| Secret 이름 | 소스 | 받는 데이터 | 무료 한도 |
|---|---|---|---|
| `DATABASE_URL` | Neon Postgres | 저장소(없으면 건수만 확인) | 무료 플랜 |
| `TIINGO_TOKEN` | Tiingo | 미국 ETF 일봉·수정주가, 긴 과거용 펀드(VFINX·VWIGX·VEIEX·FRESX·VFITX·VUSTX — 실험실 관문) | 시간당 50, 하루 1,000 |
| `FRED_API_KEY` | FRED | VIX, 원/달러, 금리, 물가, 실업률(발표일 포함) | 넉넉함 |
| `DATA_GO_KR_KEY` | 공공데이터포털(금융위원회 주식·증권상품 시세) | 한국 주식·ETF 일봉 전 종목(T+1 13시) | 개발 하루 10,000 |
| (키 없음) | 구글 뉴스 RSS — 한국 헤드라인 기본. 제목·언론사·시각만, 공식 API 아님 | 한국 시장 뉴스(홈) | 질의 4개/일 |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (선택) | NAVER API HUB 검색(뉴스) — 네이버 클라우드 콘솔에서 발급한 Client ID·Secret (예전 developers.naver.com 키는 안 됨) | 한국 시장 뉴스 | 하루 25,000 |
| `FINNHUB_TOKEN` | Finnhub | 미국 종목 뉴스 | 분당 60 |
| `SEC_USER_AGENT` | SEC EDGAR (키 없음) | 미국 재무(매출·영업이익·순이익·EPS·자본, 공시일 기준) | 초당 10회 · 값은 `앱이름 연락이메일` 형식 |

대상 목록: `quant/ingest/universe.py`. 품질 점검(중복·고가<저가·하루 ±50% 급변)은 `ingest_runs`에 `partial`로 남긴다.

## 화면 배포 (Cloudflare Workers, 무료)
`deploy-cf.yml`이 main의 화면 변경마다 배포한다. Secrets: `CLOUDFLARE_API_TOKEN`(템플릿 "Edit Cloudflare Workers"), `CLOUDFLARE_ACCOUNT_ID`. 주소는 `https://quant-auto-trade.<계정 하위도메인>.workers.dev`. `DATABASE_URL`이 있으면 Worker 비밀값으로 넣어 실데이터를 보여 준다(없으면 예시 값).

## 딥러닝 트랙 (Fable 설계 #74)

- **S&P 500 과거 구성종목**: GitHub `fja05680/sp500`의 `sp500_ticker_start_end.csv`(MIT), 커밋 `a2430f2`로 고정(`quant/dl/members.py`). 2003~2022에 한 번이라도 지수에 있었던 종목에서 기호 SHA-256 순으로 200개(성적과 무관 → 생존 편향 없음).
- **시세**: Tiingo 일봉(1998~2022) → **Cloudflare R2**(`dl/prices/<기호>.parquet`, DB에는 안 넣음 — Neon 무료 512MB 보호). `dl-backfill` 워크플로가 한 시간에 40개씩. 받은 범위·없음은 `dl/manifest.json`, 0단계 자료 관문(시세 확보 90%·사라진 종목 85%)은 `dl/status.json`.
- Secrets: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET`(이름만 적는다).
