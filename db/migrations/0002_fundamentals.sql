-- 재무 값(공시일 기준). 정정 공시는 filed_date가 다른 행으로 남긴다 → 백테스트는 그날까지 접수된 최신 값만 쓴다.
create table if not exists fundamentals (
  market        text not null check (market in ('US', 'KR')),
  code          text not null,
  concept       text not null,
  unit          text not null,
  period_start  date,
  period_end    date not null,
  fiscal_period text,
  value         double precision not null,
  filed_date    date not null,
  form          text,
  source        text not null,
  primary key (market, code, concept, unit, period_end, filed_date)
);
create index if not exists fundamentals_lookup on fundamentals (market, code, concept, filed_date);
