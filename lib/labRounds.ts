/** 실험실 라운드별 Fable 설계·판정 요약(판정 Issue 원문에서 옮김). 숫자는 화면에서 DB(experiments)로 읽는다.
 *  새 라운드가 끝나면 Fable 판정 Issue를 보고 여기에 한 칸 추가한다. */
export type Verdict = '후보' | '보류' | '탈락';
export type Round = {
  round: number;
  title: string;
  question: string;
  conclusion: string;
  planIssue: number | null;
  judgeIssue: number;
  learned: string[];
  next: string[];
  /** 실험 id → [판정, 한 줄 이유]. 여러 id를 같이 쓰면 'C01~C12'처럼 범위로 */
  verdicts: { ids: string[]; v: Verdict; why: string }[];
  /** 이 라운드 숫자를 읽는 방법: liq = 청산 세후(2차~), cagr = 세금 전 연수익(1차) */
  metric: 'liq' | 'cagr';
  plan: number | null; // experiments.params.plan 값(2차~). 1차는 null
};

const range = (p: string, a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => `${p}${String(a + i).padStart(2, '0')}`);

export const ROUNDS: Round[] = [
  {
    round: 2, title: '위험 조절 규칙·깨끗한 지표·업종', planIssue: 59, judgeIssue: 62, metric: 'liq', plan: 59,
    question: '예측 없이 단순한 위험 조절 규칙(변동성 맞추기·200일선)이 S&P보다 덜 잃으면서 비슷하게 버는가? 깨끗한 지표 타이밍·업종 순위는 그보다 나은가?',
    conclusion: '후보 없음. 11개 모두 개발 구간(2010~2017)에서 S&P 그냥 보유보다 못해 검증에 올린 것이 없다.',
    learned: [
      '손해의 주범은 수수료가 아니라 전부 팔 때 내는 양도세 22%와 팔고 나면 반등하는 뒷북',
      '업종 11개끼리만 비교하면 순위 예측력이 사라진다(IC +0.005) — 1차의 예측력은 주식·채권 구분 효과였다',
      '깨끗한 지표만 쓴 타이밍은 적중률이 "늘 오른다" 찍기보다 낮다',
      '개발 구간이 오르기만 한 장이라 방어 규칙은 보여 줄 것이 없었다',
    ],
    next: ['연 250만 원 공제를 쓰는 절세 매도', '200일선 아래면 전부 대신 일부만 줄이기', '2008년을 포함한 넓은 개발 구간', '베타 보정 알파로 우연 보정'],
    verdicts: [
      { ids: ['K03'], v: '보류', why: '0에 가장 가깝지만 70%가 S&P라서. 나머지 30%는 예측력 0 — 같은 설정 재시도 안 함' },
      { ids: ['A01'], v: '탈락', why: '1.5%p 뒤지고 최악 손실은 그대로. 8년 중 7년을 졌다' },
      { ids: ['A02'], v: '탈락', why: '최악 손실이 오히려 큼. 팔 때마다 쌓인 이익에 세금을 낸다' },
      { ids: ['A03'], v: '탈락', why: '2015~16년에 싸게 팔고 비싸게 되사기를 두 번 반복' },
      { ids: ['A04'], v: '탈락', why: '두 규칙의 나쁜 점이 합쳐짐' },
      { ids: ['L01'], v: '탈락', why: '내린 달에 S&P의 1.29배 빠짐. 2017년 한 해만 좋았다' },
      { ids: ['L02'], v: '탈락', why: '200일선을 더해도 최악 손실이 더 큼' },
      { ids: ['T07'], v: '탈락', why: '적중 68% < "늘 오른다" 69%. 예측력 없음' },
      { ids: ['T08'], v: '탈락', why: '적중 63%로 T07보다 나쁨' },
      { ids: ['K01'], v: '탈락', why: '업종 11개 똑같이 담기보다 낮음' },
      { ids: ['K02'], v: '탈락', why: '예측력 0(IC +0.005, t 0.1). 수익은 운으로 봐야 함' },
    ],
  },
  {
    round: 1, title: '예측 기반 30개', planIssue: null, judgeIssue: 57, metric: 'cagr', plan: null,
    question: '가격·거시 지표·뉴스 지수로 ETF 순위나 시장 방향을 예측하면(ML·DL) S&P보다 나은가?',
    conclusion: '후보 없음. 가장 나은 시장 타이밍(T04·T05)도 S&P 그냥 보유와 사실상 구별되지 않는다. (설계를 Fable 없이 해서 2차부터 Fable 설계로 바꿈)',
    learned: ['한 달 안에 무너지는 하락은 월 1회 판단으로 못 피한다', '주 스윙은 매매 2천 회 넘게 비용에 다 먹힌다', '일부 거시 지표에 사후 수정값이 섞여 있었다(#58에서 고침)'],
    next: ['위험 조절 규칙(변동성·200일선)', '깨끗한 지표만 쓴 타이밍', '업종 안에서만 순위'],
    verdicts: [
      { ids: ['T05'], v: '보류', why: '검증 +13.8% vs S&P +12.8%지만 최악 손실이 같고(−30%) 우연 보정 실패' },
      { ids: ['T04'], v: '보류', why: 'T05에 뉴스 지수 2개만 더한 것이라 별개 증거가 아님' },
      { ids: ['T01'], v: '탈락', why: 'T04와 같은 모델, 매매 방식만 다름 — 볼 것이 없다' },
      { ids: ['T02', 'T06'], v: '탈락', why: '연 2~5%p 낮고 적중률이 기본보다 낮다' },
      { ids: ['T03'], v: '탈락', why: '적중 45%, 최악 −36%' },
      { ids: range('C', 1, 12), v: '탈락', why: '전부 S&P보다 연 4~12%p 낮음. 순위 예측력이 수익으로 안 이어짐' },
      { ids: range('X', 1, 5), v: '탈락', why: '약한 순위 모델에 위험 관리를 얹어 수익만 깎였다' },
      { ids: range('S', 1, 4), v: '탈락', why: '매매 2천 회 넘게 비용에 다 먹힘' },
      { ids: range('R', 1, 3), v: '탈락', why: '연 +3.7~5.5%, 최악 손실도 더 나쁨' },
    ],
  },
];

export function verdictOf(r: Round, id: string): { v: Verdict; why: string } | null {
  const x = r.verdicts.find((v) => v.ids.includes(id));
  return x ? { v: x.v, why: x.why } : null;
}

export function roundIds(r: Round): string[] {
  return r.verdicts.flatMap((v) => v.ids);
}

const ORDER: Record<Verdict, number> = { 후보: 0, 보류: 1, 탈락: 2 };
/** 후보 → 보류 → 탈락 순, 같으면 점수(S&P 대비 차이) 큰 순 */
export function sortCards<T extends { id: string; v: Verdict | null; gap: number | null }>(xs: T[]): T[] {
  return [...xs].sort((a, b) => (ORDER[a.v ?? '탈락'] - ORDER[b.v ?? '탈락']) || ((b.gap ?? -99) - (a.gap ?? -99)) || a.id.localeCompare(b.id));
}

/** 실험 기록(experiments) 한 줄: 전략·구간별 마지막 실행만. 숫자는 비율(0.103 = 10.3%). */
export type LabRow = {
  id: string; hypothesis: string; period: 'dev' | 'valid'; plan: number | null; at: string;
  ret: number | null; benchRet: number | null; liq: boolean;   // liq=true면 청산 세후(2차~), 아니면 세금 전 연수익(1차)
  mdd: number | null; benchMdd: number | null; down: number | null; trades: number | null;
  hit: number | null; base: number | null; ic: number | null;
};

const n = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : typeof v === 'string' && v !== '' && Number.isFinite(Number(v)) ? Number(v) : null);

export function toRow(r: { strategy: string; hypothesis?: string; period: string; plan: string | null; at: string; m: Record<string, unknown> }): LabRow {
  const m = r.m ?? {};
  const liq = m.liq_cagr !== undefined;
  return {
    id: r.strategy, hypothesis: r.hypothesis ?? '', period: r.period === 'valid' ? 'valid' : 'dev', plan: r.plan ? Number(r.plan) : null, at: r.at,
    ret: n(liq ? m.liq_cagr : m.cagr), benchRet: n(liq ? m.bench_liq_cagr : m.bench_cagr), liq,
    mdd: n(m.mdd), benchMdd: n(m.bench_mdd), down: n(m.down_capture), trades: n(m.trades),
    hit: n(m.ic_hit ?? m.hit), base: n(m.ic_base_rate ?? m.base_rate), ic: n(m.ic_ic_mean ?? m.ic_mean),
  };
}

