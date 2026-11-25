# Quant-Auto-Trade

개인용 한·미 시장 현황·뉴스 브리핑과 전략 검증·자동매매 앱. 기존 Quant_Manager_App을 완전히 새로 만든다.

- 계획: [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) · 로드맵: [docs/roadmap.json](docs/roadmap.json)
- 개발 방식: [ai-orchestrator](https://github.com/jonghee1998/ai-orchestrator) 엔진 ([docs/ORCH_MANUAL.md](docs/ORCH_MANUAL.md))
- 공개 저장소: 계좌·잔고·키 같은 실데이터는 코드에 넣지 않는다([CLAUDE.md](CLAUDE.md)).

로컬 확인: `pip install -r requirements.txt && npm ci && npm run typecheck && npm test && npm run build`
