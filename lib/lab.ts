import 'server-only';
import { toRow, type LabRow } from './labRounds';

export type { LabRow };

export async function getLab(): Promise<LabRow[] | null> {
  const url = process.env.DATABASE_URL;
  if (!url) return null;
  try {
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(url);
    const rows = (await sql`
      select distinct on (strategy, period, coalesce(params->>'plan', '')) strategy, hypothesis, period, params->>'plan' as plan,
             to_char(created_at at time zone 'Asia/Seoul', 'YYYY-MM-DD') as at, metrics as m
      from experiments where not final and period in ('dev', 'valid')
      order by strategy, period, coalesce(params->>'plan', ''), created_at desc`) as
      { strategy: string; hypothesis: string; period: string; plan: string | null; at: string; m: Record<string, unknown> }[];
    return rows.map(toRow);
  } catch (e) {
    console.error('getLab: DB 읽기 실패', e instanceof Error ? e.name : 'unknown');
    return null;
  }
}
