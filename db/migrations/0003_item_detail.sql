-- 종목·지표 상세 화면 값(차트·통계·재무). 키마다 최신 한 줄만 둔다(홈 요약 payload를 가볍게).
create table if not exists item_detail (
  key   text primary key,   -- 'US:XLK', 'KR:005930', 'W:EWJ', 'Q:vix'
  date  date not null,
  data  jsonb not null
);
