-- 0001_init.sql 확인: 표 존재, 홀드아웃 최종 평가 1회 제약, 비중 범위. 가짜 값만 쓴다.
do $$
declare t text;
begin
  foreach t in array array['instruments','prices_daily','macro_series','news','filings','daily_brief','experiments','signals','ingest_runs'] loop
    if to_regclass('public.' || t) is null then raise exception 'missing table %', t; end if;
  end loop;

  insert into experiments (strategy, hypothesis, period, data_version, code_version, final, trial_no)
  values ('test_s', '가짜 가설', 'holdout', 'd0', 'c0', true, 0);
  begin
    insert into experiments (strategy, hypothesis, period, data_version, code_version, final, trial_no)
    values ('test_s', '가짜 가설', 'holdout', 'd0', 'c0', true, 0);
    raise exception 'second final accepted';
  exception when unique_violation then null;
  end;
  begin
    insert into experiments (strategy, hypothesis, period, data_version, code_version, final, trial_no)
    values ('test_s2', '가짜 가설', 'dev', 'd0', 'c0', true, 1);
    raise exception 'final outside holdout accepted';
  exception when check_violation then null;
  end;

  insert into instruments (market, code, kind) values ('US', 'TEST01', 'etf');
  begin
    insert into signals (strategy, as_of, instrument_id, weight)
    values ('test_s', date '2020-01-02', (select id from instruments where code = 'TEST01'), 1.5);
    raise exception 'weight over 1 accepted';
  exception when check_violation then null;
  end;
end $$;
