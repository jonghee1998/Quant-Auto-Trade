do $$
begin
  insert into fundamentals (market, code, concept, unit, period_end, value, filed_date, source)
  values ('US', 'TEST01', 'revenue', 'USD', '2024-03-31', 100, '2024-05-01', 'fake'),
         ('US', 'TEST01', 'revenue', 'USD', '2024-03-31', 101, '2024-06-01', 'fake');  -- 정정 공시: 둘 다 남음
  if (select count(*) from fundamentals where code = 'TEST01') <> 2 then raise exception '정정 공시가 따로 남지 않음'; end if;
  begin
    insert into fundamentals (market, code, concept, unit, period_end, value, filed_date, source)
    values ('XX', 'TEST01', 'revenue', 'USD', '2024-03-31', 1, '2024-05-01', 'fake');
    raise exception 'market 검사 실패';
  exception when check_violation then null;
  end;
end $$;
