-- Quant Auto Trade 기본 스키마 (Postgres, Neon). 운영 DB 적용은 사람이 한다. CI 는 일회용 Postgres 에서만 확인한다.
-- 계좌·주문 표는 매매 단계(5·6단계)에서 따로 추가한다.

create table if not exists instruments (
  id           bigserial primary key,
  market       text not null check (market in ('US', 'KR')),
  code         text not null,
  name         text,
  kind         text not null check (kind in ('stock', 'etf', 'index')),
  listed_on    date,
  delisted_on  date,
  unique (market, code)
);

create table if not exists prices_daily (
  instrument_id bigint not null references instruments(id),
  date          date not null,
  open          double precision,
  high          double precision,
  low           double precision,
  close         double precision not null,
  adj_factor    double precision not null default 1,
  volume        double precision,
  source        text not null,
  primary key (instrument_id, date)
);

-- 매크로·시장 위험 지표(VIX, 금리, 달러 지수 등). 발표일(release_date) 기준으로만 백테스트에 쓴다.
create table if not exists macro_series (
  series        text not null,
  ref_date      date not null,
  release_date  date not null,
  value         double precision not null,
  source        text not null,
  primary key (series, ref_date, release_date)
);

create table if not exists news (
  url_hash      text primary key,
  url           text not null,
  title         text not null,
  publisher     text,
  published_at  timestamptz not null,
  tickers       text[] not null default '{}',
  cluster_id    text,
  source        text not null
);

create table if not exists filings (
  receipt_no    text primary key,
  market        text not null check (market in ('US', 'KR')),
  code          text,
  kind          text,
  title         text not null,
  filed_at      timestamptz not null,
  source        text not null
);

create table if not exists daily_brief (
  date          date primary key,
  summary       text not null,
  payload       jsonb not null default '{}'::jsonb,
  generated_at  timestamptz not null default now()
);

-- 실험실: 실행마다 한 줄. final=true(홀드아웃 최종 평가)는 전략당 한 번만.
create table if not exists experiments (
  id            bigserial primary key,
  strategy      text not null,
  hypothesis    text not null,
  params        jsonb not null default '{}'::jsonb,
  period        text not null check (period in ('dev', 'valid', 'holdout')),
  data_version  text not null,
  code_version  text not null,
  metrics       jsonb not null default '{}'::jsonb,
  final         boolean not null default false,
  trial_no      integer not null,
  created_at    timestamptz not null default now(),
  check (final = false or period = 'holdout')
);
create unique index if not exists experiments_one_final on experiments (strategy) where final;

create table if not exists signals (
  strategy      text not null,
  as_of         date not null,
  instrument_id bigint not null references instruments(id),
  weight        double precision not null check (weight >= 0 and weight <= 1),
  primary key (strategy, as_of, instrument_id)
);

create table if not exists ingest_runs (
  id            bigserial primary key,
  source        text not null,
  dataset       text not null,
  started_at    timestamptz not null,
  finished_at   timestamptz,
  rows          integer,
  status        text not null check (status in ('running', 'success', 'partial', 'failed')),
  error         text
);
