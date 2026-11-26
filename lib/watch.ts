'use client';
/** 관심 종목: 이 기기 브라우저에 저장(로그인 없이). 키 'US:XLK' 형식. 저장이 막힌 브라우저면 빈 목록. */
const KEY = 'quant.watch.v1';
export const WATCH_EVENT = 'quant-watch';

export function readWatch(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string').slice(0, 50) : [];
  } catch {
    return [];
  }
}

export function toggleWatch(id: string): string[] {
  const cur = readWatch();
  const next = cur.includes(id) ? cur.filter((x) => x !== id) : [id, ...cur].slice(0, 50);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
    window.dispatchEvent(new Event(WATCH_EVENT));
  } catch {
    /* 저장 불가(사파리 개인 정보 보호 모드 등) — 화면만 바뀜 */
  }
  return next;
}
