// 화면 데이터 출처: DB(daily_brief 최신 payload)가 있으면 그것, 없으면 예시 값(lib/mock).
// 서버에서만 실행한다. DATABASE_URL은 서버 환경변수(NEXT_PUBLIC_ 금지).
import 'server-only';
import * as M from './mock';
import { fromPayload, type MarketData } from './payload';

export type { MarketData };

const SAMPLE: MarketData = {
  sample: true, asOf: M.AS_OF, summary: M.SUMMARY, quotes: M.QUOTES,
  trendLight: M.TREND_LIGHT, breadth: M.BREADTH, news: M.NEWS, universe: M.UNIVERSE,
  bench: { US: [...M.BENCH.US], KR: [...M.BENCH.KR], W: [...M.BENCH.W] },
};

export async function getMarket(): Promise<MarketData> {
  const url = process.env.DATABASE_URL;
  if (!url) return SAMPLE;
  try {
    const { Client } = await import('pg');
    const c = new Client({ connectionString: url, ssl: { rejectUnauthorized: false } });
    await c.connect();
    try {
      const r = await c.query('select payload from daily_brief order by date desc limit 1');
      return fromPayload(r.rows[0]?.payload) ?? SAMPLE;
    } finally {
      await c.end();
    }
  } catch {
    return SAMPLE; // DB 오류 시에도 화면은 뜬다(예시 값 표시)
  }
}
