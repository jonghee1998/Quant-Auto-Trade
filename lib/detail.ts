import 'server-only';

export type Point = [string, number | null];
export type PriceStats = { days: number; vol?: number | null; mdd?: number | null; high?: number | null; low?: number | null; pos?: number | null; ma200?: number | null; beta?: number | null };
export type Fund = { quarters: { end: string; revenue: number | null; netIncome: number | null; revYoY: number | null }[]; per?: number | null; epsYear?: string; pbr?: number | null; filed?: string };
export type Level = { pos?: number | null; high1?: number | null; low1?: number | null; avg10?: number | null; max10?: number | null; min10?: number | null; years?: number | null };
export type Related = { id: string; name: string; value: number | null; state: string; date: string; m1: number | null };
export type Detail = { date: string; chart: Point[]; stats?: PriceStats; fund?: Fund; level?: Level; related?: Related[] };

/** 상세 화면 값 한 줄(item_detail). 없거나 DB를 못 읽으면 null — 화면은 '데이터 연결 중'. */
export async function getDetail(key: string): Promise<Detail | null> {
  const url = process.env.DATABASE_URL;
  if (!url) return null;
  try {
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(url);
    const rows = (await sql`select date::text as date, data from item_detail where key = ${key}`) as { date: string; data: unknown }[];
    const d = rows[0]?.data;
    if (!d || typeof d !== 'object' || !Array.isArray((d as Detail).chart)) return null;
    return { ...(d as Omit<Detail, 'date'>), date: rows[0].date } as Detail;
  } catch (e) {
    console.error('getDetail: DB 읽기 실패', e instanceof Error ? e.name : 'unknown');
    return null;
  }
}
