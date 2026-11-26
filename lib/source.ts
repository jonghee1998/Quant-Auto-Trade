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
  if (!url) return { ...SAMPLE, sampleReason: 'DB 미설정' };
  try {
    // Neon 서버리스 드라이버(HTTP): Node·Cloudflare Workers 둘 다 동작
    const { neon } = await import('@neondatabase/serverless');
    const sql = neon(url);
    const rows = (await sql`select payload from daily_brief order by date desc limit 1`) as { payload: unknown }[];
    return fromPayload(rows[0]?.payload) ?? { ...SAMPLE, sampleReason: '요약 없음' };
  } catch (e) {
    console.error('getMarket: DB 읽기 실패', e instanceof Error ? e.name : 'unknown'); // 메시지엔 접속 정보가 있을 수 있어 종류만
    return { ...SAMPLE, sampleReason: 'DB 연결 실패' }; // DB 오류 시에도 화면은 뜬다(예시 값 표시)
  }
}
