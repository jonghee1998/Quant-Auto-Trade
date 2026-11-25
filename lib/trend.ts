import type { Item } from './mock';

export type Market = 'US' | 'KR' | 'W';
export type Kind = '업종' | '주식';

/** 강한 곳/약한 곳 목록: 시장·종류·기간(0=1개월,1=3개월,2=6개월)으로 걸러 수익률 순 상위 n개. */
export function rankItems(items: Item[], market: Market, kind: Kind, period: 0 | 1 | 2, strong: boolean, n = 6) {
  const pool = items
    .filter((i) => i.market === market && (market === 'W' ? i.kind === '나라' : i.kind === kind))
    .map((i) => ({ ...i, ret: i.r[period] }))
    .filter((i): i is typeof i & { ret: number } => typeof i.ret === 'number' && Number.isFinite(i.ret)); // 값 없는 종목은 순위에서 뺀다
  const sorted = pool.sort((a, b) => (strong ? b.ret - a.ret : a.ret - b.ret));
  return sorted.slice(0, n);
}

/** 막대 위치(0~100%): 0을 가운데, 가장 큰 절댓값을 끝으로. */
export function barSpan(v: number, maxAbs: number): { left: number; width: number } {
  const m = maxAbs > 0 ? maxAbs : 1;
  const pos = (x: number) => 50 + (x / m) * 48;
  const a = pos(0), b = pos(v);
  return { left: Math.min(a, b), width: Math.abs(b - a) };
}
