// daily_brief payload → 화면 데이터. 서버·테스트 공용(의존성 없음).
import type { Item, Quote } from './types';

export type MarketData = {
  sample: boolean;
  /** 예시 값을 보여주는 이유(진단용, 비밀값 없음) */
  sampleReason?: 'DB 미설정' | 'DB 연결 실패' | '요약 없음';
  asOf: string;
  summary: string;
  quotes: Quote[];
  trendLight: { state: 'green' | 'red' | null; gapPct: number | null };
  breadth: { above: number; total: number };
  news: { title: string; where: string }[];
  universe: Item[];
  bench: Record<'US' | 'KR' | 'W', (number | null)[]>;
};

/** payload를 화면 모양으로 검사·변환. 모양이 다르면 null. */
export function fromPayload(p: unknown): MarketData | null {
  const o = p as Record<string, unknown> | null;
  if (!o || typeof o !== 'object' || !Array.isArray(o.quotes) || typeof o.summary !== 'string') return null;
  const tl = (o.trendLight ?? {}) as Record<string, unknown>;
  const br = (o.breadth ?? {}) as Record<string, unknown>;
  const bench = (o.bench ?? {}) as Record<string, unknown>;
  const arr3 = (v: unknown) => (Array.isArray(v) ? v.slice(0, 3).map((x) => (typeof x === 'number' ? x : null)) : [null, null, null]);
  return {
    sample: false,
    asOf: typeof o.asOf === 'string' ? o.asOf : '—',
    summary: o.summary,
    quotes: o.quotes as Quote[],
    trendLight: { state: tl.state === 'green' || tl.state === 'red' ? tl.state : null, gapPct: typeof tl.gapPct === 'number' ? tl.gapPct : null },
    breadth: { above: Number(br.above) || 0, total: Number(br.total) || 0 },
    news: Array.isArray(o.news) ? (o.news as MarketData['news']) : [],
    universe: Array.isArray(o.universe) ? (o.universe as Item[]).map((u) => ({ ...u, r: arr3(u.r) as Item['r'] })) : [],
    bench: { US: arr3(bench.US), KR: arr3(bench.KR), W: arr3(bench.W) },
  };
}

