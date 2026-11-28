// 화면 데이터 출처: DB(daily_brief 최신 payload). 없으면 빈 데이터 + 이유(화면은 '데이터 연결 중'으로 표시, 가짜 값 없음).
// 서버에서만 실행한다. DATABASE_URL은 서버 환경변수(NEXT_PUBLIC_ 금지).
import 'server-only';
import { fromPayload, type MarketData } from './payload';
import { memo } from './memo';

export type { MarketData };

const SAMPLE: MarketData = {
  sample: true, asOf: '—', summary: '', quotes: [], trendLight: { state: null, gapPct: null },
  breadth: { above: 0, total: 0 }, news: [], universe: [], signals: null, coverage: {}, ai: {}, bench: { US: [null, null, null], KR: [null, null, null], W: [null, null, null] },
};

/** 최신 요약. 하루 몇 번만 바뀌므로 1분은 기억해 둔다(실패·빈 값은 기억하지 않는다). */
export function getMarket(): Promise<MarketData> {
  return memo('market', 60_000, readMarket, (v) => !v.sample);
}

async function readMarket(): Promise<MarketData> {
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
    return { ...SAMPLE, sampleReason: 'DB 연결 실패' }; // DB 오류 시에도 화면은 뜬다('데이터 연결 중')
  }
}
