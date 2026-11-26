"""AI 브리프: 매일 수집 뒤 AI(Claude)가 오늘 3줄·시장 해석·핫한 뉴스·트렌드 이유를 쓴다.

흐름: prepare(DB → 입력 JSON, 부분별) → AI가 docs/BRIEF.md 형식으로 출력 JSON 작성 → save(검사 → daily_brief.payload["ai"]).
AI 작업에는 DB 주소·키를 주지 않는다. 입력은 공개 시장 데이터와 뉴스 제목뿐.
"""
