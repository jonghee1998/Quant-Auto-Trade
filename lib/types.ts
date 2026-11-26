// 화면 데이터 타입.
export type Quote = { id: string; name: string; value: number | null; unit?: string; change: number | null; changeText?: string; dailyStd: number | null; m1: number | null; y1: number | null; note?: string };
export type Bench = Record<'US' | 'KR' | 'W', (number | null)[]>;
export type Item = { code: string; name: string; kind: '업종' | '주식' | '나라'; market: 'US' | 'KR' | 'W'; r: [number | null, number | null, number | null] };
export type Signal = { key: 'trend' | 'breadth' | 'risk'; title: string; good: boolean | null; text: string };
export type Signals = { state: 'green' | 'yellow' | 'red' | null; good: number; items: Signal[] };
export type Coverage = Record<string, { shown: number; total?: number; note?: string }>;
export type NewsLink = { name: string; url: string };
export type AiNews = { id: string; cat: string; title: string; summary: string[]; meaning: string; where: string; outlets: number; links: NewsLink[] };
export type AiWhy = { line: string; text: string; tags: string[]; confidence: '높음' | '보통' | '낮음'; evidence: { type: string; label: string; url: string | null }[] };
export type Ai = {
  generatedAt?: string;
  today?: { what: string; why: string; why_news: string[]; next: { what: string; why: string }[] };
  market?: { us: string; kr: string };
  news?: AiNews[];
  why?: Record<string, AiWhy>;
};
