-- 10-Q는 같은 끝 날짜로 '3개월 값'과 '연초부터 누적(6·9개월) 값'을 함께 낸다.
-- 기본키에 기간 길이가 없어서 둘이 서로 덮어써 2·3분기 분기 값이 사라졌다 → 기간 길이(일)를 키에 넣는다.
-- 매일 다시 실행돼도 안전하게(이미 바뀌었으면 건너뜀).
alter table fundamentals add column if not exists period_days integer not null default 0;
update fundamentals set period_days = coalesce(period_end - period_start, 0)
 where period_days = 0 and period_start is not null;
do $$
begin
  if not exists (
    select 1 from information_schema.key_column_usage
    where table_name = 'fundamentals' and constraint_name = 'fundamentals_pkey' and column_name = 'period_days'
  ) then
    alter table fundamentals drop constraint fundamentals_pkey;
    alter table fundamentals add constraint fundamentals_pkey
      primary key (market, code, concept, unit, period_end, period_days, filed_date);
  end if;
end $$;
