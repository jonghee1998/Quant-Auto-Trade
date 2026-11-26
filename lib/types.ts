// 화면 데이터 타입.
export type Quote = { id: string; name: string; value: number | null; unit?: string; change: number | null; changeText?: string; dailyStd: number | null; m1: number | null; y1: number | null; note?: string };
export type Bench = Record<'US' | 'KR' | 'W', (number | null)[]>;
export type Item = { code: string; name: string; kind: '업종' | '주식' | '나라'; market: 'US' | 'KR' | 'W'; r: [number | null, number | null, number | null] };
