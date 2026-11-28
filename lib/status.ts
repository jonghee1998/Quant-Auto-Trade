import 'server-only';
import { memo } from './memo';

export type SourceStatus = {
  source: string; lastAt: string; lastStatus: string; lastRows: number; jobsLast: number; failedLast: number;
  days: { day: string; ok: boolean | null }[]; lastError: string | null;
};
export type DataStatus = { sources: SourceStatus[]; dbBytes: number | null; briefDate: string | null; aiAt: string | null };

const NAMES: Record<string, string> = {
  tiingo: '미국 시세 (Tiingo)', fred: '미국 경제 지표 (FRED)', 'data.go.kr': '한국 시세·지수 (data.go.kr)',
  google_news: '뉴스 (구글 뉴스)', finnhub: '미국 뉴스 (Finnhub)', sec: '미국 재무 (SEC)', naver: '한국 뉴스 (네이버)',
};
export const sourceName = (s: string) => NAMES[s] ?? s;

/** 수집 기록(ingest_runs) 최근 7일: 소스별 날마다 성공했나, 마지막 실행의 건수·실패. 오류 문구는 수집 때 이미 비밀값을 가렸다. */
export function getStatus(): Promise<DataStatus | null> {
  return memo('status', 60_000, readStatus, (v) => v !== null);
}

async function readStatus(): Promise<DataStatus | null> {
  const url = process.env.DATABASE_URL;
  if (!url) return null;
  try {
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(url);
    // 날짜·소스별로 DB에서 묶어 온다(수천 건을 화면 쪽에서 돌리면 Workers CPU 한도에 걸릴 수 있다)
    const runs = (await sql`
      with r as (
        select source, dataset, (started_at at time zone 'Asia/Seoul')::date as day, status, coalesce(rows, 0) as n, error, started_at
        from ingest_runs where started_at >= now() - interval '7 days'),
      -- 같은 날 같은 데이터를 여러 번 돌렸으면 마지막 결과만 본다(고치기 전 실패가 남아 '일부 실패'로 보이지 않게)
      l as (select distinct on (source, day, dataset) * from r order by source, day, dataset, started_at desc)
      select source, day::text as day, bool_and(status <> 'failed') as ok, count(*)::int as jobs,
             (count(*) filter (where status = 'failed'))::int as failed, sum(n)::bigint as n,
             to_char(max(started_at) at time zone 'Asia/Seoul', 'MM/DD HH24:MI') as at,
             (array_agg(dataset || ': ' || error order by started_at desc) filter (where status = 'failed'))[1] as err
      from l group by source, day order by source, day desc`) as
      { source: string; day: string; ok: boolean; jobs: number; failed: number; n: string | number; at: string; err: string | null }[];
    // 각 값은 따로 읽는다: 하나가 느리거나 실패해도 수집 기록은 보이게
    const one = async <T,>(q: Promise<unknown>, pick: (r: Record<string, unknown>) => T): Promise<T | null> => {
      try { const r = (await q) as Record<string, unknown>[]; return r[0] ? pick(r[0]) : null; } catch (e) { console.error('getStatus: 보조 값 실패', e instanceof Error ? e.name : 'unknown'); return null; }
    };
    // pg_database_size는 Neon에서 느릴 수 있어 표 크기 합으로 대신(색인 포함)
    const dbBytes = await one(sql`select coalesce(sum(pg_total_relation_size(c.oid)), 0)::bigint as b from pg_class c
      join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind in ('r', 'm')`, (r) => Number(r.b));
    const brief = await one(sql`select date::text as d, payload->'ai'->>'generatedAt' as ai from daily_brief order by date desc limit 1`,
      (r) => ({ d: (r.d as string) ?? null, ai: (r.ai as string) ?? null }));
    const days: string[] = [];
    for (let i = 6; i >= 0; i--) days.push(new Date(Date.now() + 9 * 3600e3 - i * 86400e3).toISOString().slice(0, 10));
    const by = new Map<string, typeof runs>();
    for (const r of runs) { const l = by.get(r.source); if (l) l.push(r); else by.set(r.source, [r]); }
    const sources = [...by.entries()].map(([source, rs]) => {
      const last = rs[0]; // 날짜 내림차순
      return {
        source, lastAt: last.at, lastStatus: last.failed === 0 ? 'ok' : last.failed === last.jobs ? 'failed' : 'partial',
        lastRows: Number(last.n), jobsLast: last.jobs, failedLast: last.failed,
        days: days.map((day) => { const x = rs.find((r) => r.day === day); return { day, ok: x ? x.ok : null }; }),
        lastError: last.err?.slice(0, 160) ?? null,
      };
    });
    return { sources, dbBytes, briefDate: brief?.d ?? null, aiAt: brief?.ai ?? null };
  } catch (e) {
    console.error('getStatus: DB 읽기 실패', e instanceof Error ? e.name : 'unknown');
    return null;
  }
}
