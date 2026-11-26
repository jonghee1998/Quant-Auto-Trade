-- 날짜로 거르는 조회(최근 20거래일 거래대금 상위, 이미 받은 날짜, 스냅샷 최근 N일)가 전체 행을 훑지 않게.
-- 한국 전 종목 일별이 하루 4천 행이라 표가 커질수록 느려졌다(OpenDART 종목 고르기 수 분).
create index if not exists prices_daily_date_idx on prices_daily (date);
