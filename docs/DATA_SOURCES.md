# 데이터 소스와 비밀값

수집 코드: `quant/ingest/` · 매일 실행: `.github/workflows/ingest.yml`(한국시간 14:37, 수동 실행 가능).
비밀값은 GitHub → Settings → Secrets and variables → Actions → **Secrets**에만 넣는다. 없는 키의 소스는 건너뛴다.

| Secret 이름 | 소스 | 받는 데이터 | 무료 한도 |
|---|---|---|---|
| `DATABASE_URL` | Neon Postgres | 저장소(없으면 건수만 확인) | 무료 플랜 |
| `TIINGO_TOKEN` | Tiingo | 미국 ETF 일봉·수정주가 | 시간당 50, 하루 1,000 |
| `FRED_API_KEY` | FRED | VIX, 원/달러, 금리, 물가, 실업률(발표일 포함) | 넉넉함 |
| `DATA_GO_KR_KEY` | 공공데이터포털(금융위원회 주식·증권상품 시세) | 한국 주식·ETF 일봉 전 종목(T+1 13시) | 개발 하루 10,000 |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | NAVER API HUB 검색(뉴스) — 네이버 클라우드 콘솔에서 발급한 Client ID·Secret (예전 developers.naver.com 키는 안 됨) | 한국 시장 뉴스 | 하루 25,000 |
| `FINNHUB_TOKEN` | Finnhub | 미국 종목 뉴스 | 분당 60 |
| `SEC_USER_AGENT` | SEC EDGAR (키 없음) | 미국 재무(매출·영업이익·순이익·EPS·자본, 공시일 기준) | 초당 10회 · 값은 `앱이름 연락이메일` 형식 |

대상 목록: `quant/ingest/universe.py`. 품질 점검(중복·고가<저가·하루 ±50% 급변)은 `ingest_runs`에 `partial`로 남긴다.

## 화면 배포 (Cloudflare Workers, 무료)
`deploy-cf.yml`이 main의 화면 변경마다 배포한다. Secrets: `CLOUDFLARE_API_TOKEN`(템플릿 "Edit Cloudflare Workers"), `CLOUDFLARE_ACCOUNT_ID`. 주소는 `https://quant-auto-trade.<계정 하위도메인>.workers.dev`. `DATABASE_URL`이 있으면 Worker 비밀값으로 넣어 실데이터를 보여 준다(없으면 예시 값).
