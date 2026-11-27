-- 1회 정리(Fable 판정 #57): 월·주간 지표의 '발표 기록 이전' 값이 기준일+35일 발표로 잘못 들어가 있었다(사후 수정값 누수).
-- 일간이 아닌 지표 전부와 주 1회 발표 지표(달러지수·원/달러)를 지우고 다시 받는다. 매일 다시 돌아도 한 번만 지우게 표시를 남긴다.
create table if not exists schema_flags (name text primary key, done_at timestamptz not null default now());
do $$
begin
  if not exists (select 1 from schema_flags where name = '0006_refetch_alfred') then
    delete from macro_series where series not in ('VIXCLS', 'VXVCLS', 'DGS10', 'DGS2', 'T10Y2Y', 'T10Y3M', 'DFF', 'BAMLH0A0HYM2', 'USEPUINDXD', 'WLEMUINDXD', 'DCOILWTICO', 'T5YIE', 'DFII10', 'BAMLC0A0CM', 'BAA10Y');
    insert into schema_flags (name) values ('0006_refetch_alfred');
  end if;
end $$;
