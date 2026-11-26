import 'server-only';

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
export async function getStatus(): Promise<DataStatus | null> {
  const url = process.env.DATABASE_URL;
  if (!url) return null;
  try {
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(url);
    const runs = (await sql`
      select source, (started_at at time zone 'Asia/Seoul')::date::text as day, status, coalesce(rows, 0) as rows, error,
             to_char(started_at at time zone 'Asia/Seoul', 'MM/DD HH24:MI') as at, started_at
      from ingest_runs where started_at >= now() - interval '7 days' order by started_at desc`) as
      { source: string; day: string; status: string; rows: number; error: string | null; at: string }[];
    const meta = (await sql`
      select pg_database_size(current_database())::bigint as bytes,
             (select date::text from daily_brief order by date desc limit 1) as brief,
             (select payload->'ai'->>'generatedAt' from daily_brief order by date desc limit 1) as ai`) as
      { bytes: string | number | null; brief: string | null; ai: string | null }[];
    const days: string[] = [];
    for (let i = 6; i >= 0; i--) days.push(new Date(Date.now() + 9 * 3600e3 - i * 86400e3).toISOString().slice(0, 10));
    const by = new Map<string, typeof runs>();
    for (const r of runs) by.set(r.source, [...(by.get(r.source) ?? []), r]);
    const sources = [...by.entries()].map(([source, rs]) => {
      const lastDay = rs[0].day;
      const last = rs.filter((r) => r.day === lastDay);
      const failed = last.filter((r) => r.status === 'failed');
      return {
        source, lastAt: rs[0].at, lastStatus: failed.length === 0 ? 'ok' : failed.length === last.length ? 'failed' : 'partial',
        lastRows: last.reduce((a, r) => a + Number(r.rows), 0), jobsLast: last.length, failedLast: failed.length,
        days: days.map((day) => { const x = rs.filter((r) => r.day === day); return { day, ok: x.length ? x.some((r) => r.status !== 'failed') : null }; }),
        lastError: failed[0]?.error?.slice(0, 160) ?? null,
      };
    });
    return { sources, dbBytes: meta[0]?.bytes == null ? null : Number(meta[0].bytes), briefDate: meta[0]?.brief ?? null, aiAt: meta[0]?.ai ?? null };
  } catch (e) {
    console.error('getStatus: DB 읽기 실패', e instanceof Error ? e.name : 'unknown');
    return null;
  }
}
