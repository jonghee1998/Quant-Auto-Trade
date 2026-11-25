// 프로토타입용 예시 데이터. 실데이터 아님(숫자·종목 모두 가짜/예시). 실데이터 연결 시 이 파일을 대체한다.
export const AS_OF = '11/25 14:40';

export type Quote = { id: string; name: string; value: number | null; unit?: string; change: number | null; changeText?: string; dailyStd: number | null; m1: number | null; y1: number | null; note?: string };
export const QUOTES: Quote[] = [
  { id: 'spx', name: '미국 S&P 500', value: 5980, change: 0.6, dailyStd: 0.9, m1: 2.1, y1: 18 },
  { id: 'ndx', name: '미국 나스닥', value: 19211, change: 0.9, dailyStd: 1.2, m1: 2.8, y1: 24 },
  { id: 'kospi', name: '한국 코스피', value: 2512, change: -0.4, dailyStd: 1.0, m1: -2.0, y1: -4 },
  { id: 'usdkrw', name: '원/달러 환율', value: 1392, unit: '원', change: 0.22, changeText: '+3.1원', dailyStd: 0.4, m1: 1.3, y1: 4, note: '달러 비싸짐' },
  { id: 'vix', name: '불안 지수 VIX', value: 21.8, change: 12.4, changeText: '+2.4', dailyStd: 6, m1: null, y1: null, note: '보통 15~20 · 30 넘으면 공포' },
];

export const SUMMARY = '미국은 평소처럼 조금 올랐고, 한국은 조금 내렸어요. 불안감(VIX)은 보통보다 약간 높아요.';
export const TREND_LIGHT = { state: 'green' as 'green' | 'red', gapPct: 6.1 };
export const BREADTH = { above: 8, total: 11 };

export const NEWS = [
  { title: '합성 헤드라인: 연준, 금리 인하 속도 논쟁', where: '미국' },
  { title: '합성 헤드라인: 반도체 수출 예상보다 좋음', where: '한국' },
  { title: '합성 헤드라인: 가짜종목A 내일 실적 발표', where: '미국' },
];

export type Item = { code: string; name: string; kind: '업종' | '주식' | '나라'; market: 'US' | 'KR' | 'W'; r: [number, number, number] };
export const UNIVERSE: Item[] = [
  ...([['XLK', '기술', [3.0, 11.6, 17.9]], ['XLC', '통신', [2.6, 8.5, 14.2]], ['GLD', '금', [2.9, 10.2, 19.5]], ['XLF', '금융', [1.2, 6.0, 12.1]], ['XLI', '산업', [2.4, 5.1, 9.0]], ['XLV', '헬스케어', [-0.8, 2.2, 3.4]], ['XLE', '에너지', [-2.2, -0.4, 1.9]], ['XLRE', '부동산', [-1.1, 1.3, 2.0]], ['TLT', '장기 국채', [1.8, -1.5, -2.9]]] as const)
    .map(([code, name, r]) => ({ code, name, kind: '업종' as const, market: 'US' as const, r: [...r] as [number, number, number] })),
  ...([['TEST01', '가짜종목A', [6.1, 22.4, 41.0]], ['TEST02', '가짜종목B', [4.0, 18.9, 35.2]], ['TEST07', '가짜종목G', [2.2, 9.1, 15.0]], ['TEST09', '가짜종목I', [-1.9, -0.8, 3.1]], ['TEST03', '가짜종목C', [-5.0, -7.7, -12.4]], ['TEST10', '가짜종목J', [-6.2, -11.0, -19.5]]] as const)
    .map(([code, name, r]) => ({ code, name, kind: '주식' as const, market: 'US' as const, r: [...r] as [number, number, number] })),
  ...([['466920', '조선', [3.3, 15.2, 31.0]], ['091160', '반도체', [5.1, 12.4, 20.3]], ['091170', '금융', [1.9, 6.3, 11.8]], ['091180', '자동차', [0.5, -1.2, 2.0]], ['305540', '2차전지', [-4.0, -9.8, -15.1]]] as const)
    .map(([code, name, r]) => ({ code, name, kind: '업종' as const, market: 'KR' as const, r: [...r] as [number, number, number] })),
  ...([['000001', '가짜종목K', [8.0, 25.1, 48.2]], ['000002', '가짜종목L', [3.2, 14.0, 22.5]], ['000004', '가짜종목N', [-2.8, -6.5, -10.2]], ['000005', '가짜종목O', [-7.1, -14.3, -22.0]]] as const)
    .map(([code, name, r]) => ({ code, name, kind: '주식' as const, market: 'KR' as const, r: [...r] as [number, number, number] })),
  ...([['SPY', '미국', [2.1, 5.4, 9.8]], ['EWJ', '일본', [1.0, 6.8, 11.2]], ['MCHI', '중국', [3.9, 9.1, 21.4]], ['EWT', '대만', [4.4, 10.3, 18.8]], ['VGK', '유럽', [0.6, 2.2, 6.9]], ['INDA', '인도', [-1.2, -3.5, 1.0]], ['EWY', '한국', [-2.0, -3.1, -1.2]], ['EWZ', '브라질', [-3.0, -5.2, -8.1]]] as const)
    .map(([code, name, r]) => ({ code, name, kind: '나라' as const, market: 'W' as const, r: [...r] as [number, number, number] })),
];
export const BENCH = { US: [2.1, 5.4, 9.8], KR: [-2.0, -3.1, -1.2], W: [2.1, 5.4, 9.8] } as const;

export const WATCH = [
  { code: 'TEST01', name: '가짜종목A', meta: '미국 주식', m1: 6.1, above: true },
  { code: 'SOXX', name: '반도체 ETF', meta: '미국 ETF', m1: 5.5, above: true },
  { code: '000001', name: '가짜종목K', meta: '한국 주식', m1: -2.8, above: false },
];

export const PICKS = {
  strategy: '추세 + 실적', note: '과거 15년 S&P 대비 연 +1.4%p, 최악 손실 절반', verified: false,
  good: [
    { code: 'TEST01', name: '가짜종목A', why: '긴 하락 끝나고 상승 전환 + 실적 예상보다 좋음' },
    { code: 'SOXX', name: '반도체 ETF', why: '요즘 돈이 가장 많이 몰리는 업종' },
    { code: '000001', name: '가짜종목K', why: '3개월째 시장보다 강하고 이익 전망 상향' },
  ],
  bad: [
    { code: 'TEST03', name: '가짜종목C', why: '오르던 흐름이 꺾였고 이익 전망 하향' },
    { code: '305540', name: '2차전지 ETF', why: '6개월째 시장보다 약하고 계속 내리는 중' },
    { code: 'TEST10', name: '가짜종목J', why: '실적 발표 후 급락, 아직 반등 신호 없음' },
  ],
};

export const EXPERIMENTS = [
  { title: '폭락 피하기', status: '모의투자로 감', goal: '큰 폭락 때 덜 잃을 수 있나', used: '시장이 200일 평균선 아래면 현금, 위면 다시 삼 (월 1회 확인)', me: { cagr: 8.9, mdd: -17 }, spy: { cagr: 9.4, mdd: -34 }, insight: '수익은 비슷한데 최악 손실이 절반. 반등 초기를 자주 놓침', next: '가상 돈으로 연습 중' },
  { title: '강한 업종 따라가기', status: '후보', goal: '강한 업종이 계속 강한가', used: '매달 최근 3개월 가장 많이 오른 미국 업종 ETF 3개', me: { cagr: 11.2, mdd: -24 }, spy: { cagr: 9.4, mdd: -34 }, insight: '수익도 높고 손실도 적음. 업종이 자주 바뀌어 비용이 큼', next: '폭락 피하기와 합쳐 다시 시험' },
  { title: '짧게 반등 노리기', status: '탈락', goal: '짧은 반등으로 벌 수 있나', used: '크게 떨어진 ETF 반등 시 사서 +5% 또는 10일 뒤 팖 (스윙)', me: { cagr: 7.3, mdd: -14 }, spy: { cagr: 9.4, mdd: -34 }, insight: '세금·수수료 빼면 S&P보다 못함. 매매가 너무 잦음', next: '중단' },
];

export const BACKTEST = {
  name: '강한 업종 갈아타기 v3', logic: '매달 첫 거래일, 최근 3개월 가장 강한 미국 업종 ETF 3개를 똑같이 · 시장이 200일선 아래면 현금',
  rows: [['연 수익', '10.4%', '9.4%'], ['최악 손실', '−19%', '−34%'], ['회복까지', '7개월', '14개월'], ['오른 달 따라감', '92%', '100%'], ['내린 달 빠짐', '61%', '100%']] as [string, string, string][],
  checks: [[true, '세후 수익 S&P 이상 (계좌 1,000만 원 기준)'], [true, '내린 달 빠짐 < 오른 달 따라감'], [true, '최악 손실이 S&P의 절반대'], [false, '운 아님 확인: 23번 시도 중 우연일 확률 8% (기준 5% 이하)']] as [boolean, string][],
  stress: [['2020 코로나 급락', -12, -20], ['2022 금리 급등', -9, -18], ['2025 4월 급락', -7, -12]] as [string, number, number][],
};

export const PAPER = {
  name: '강한 업종 갈아타기 v3', start: '9월 1일', capital: 10_000_000, value: 10_412_000, spyValue: 10_360_000, trades: 6, target: 20,
  checks: [['신호대로 주문', '6 / 6'], ['백테스트와 수익 차이', '−0.2%p'], ['예상보다 비싸게 체결', '평균 0.03%'], ['빠진 주문', '0']] as [string, string][],
  log: [['11/03 XLK 34주 삼', '$231.40', '3개월 1위 업종 · 비용 1,520원'], ['11/03 XLE 41주 팖', '$88.10', '상위 3개에서 빠짐 · 비용 1,480원'], ['10/01 XLC 52주 삼', '$101.20', '3개월 2위 업종 · 비용 1,510원']] as [string, string, string][],
};

export const DATA_STATUS = [
  { name: '미국 시세', src: 'Tiingo', since: '2005년~', today: '07:31 · 24종목', days: 'GGGGGGG' },
  { name: '한국 시세', src: '공공데이터포털', since: '2010년~', today: '14:41 · 2,764종목', days: 'GGYGGGY' },
  { name: '지표 (VIX·금리·환율)', src: 'FRED', since: '1990년~', today: '08:02 · 9개', days: 'GGGGGGG' },
  { name: '미국 뉴스', src: 'Finnhub', since: '1년', today: '14:00 · 312건', days: 'GGGRGGG' },
  { name: '미국 재무', src: 'SEC EDGAR', since: '—', today: '준비 중', days: '-------' },
  { name: '한국 뉴스', src: '네이버', since: '—', today: '키 없음', days: '-------' },
  { name: '한국 재무', src: 'OpenDART', since: '—', today: '키 없음', days: '-------' },
];

export const TERMS: [string, string][] = [
  ['200일 평균선', '지난 200거래일(약 10개월) 종가 평균. 위면 장기 흐름이 오르는 중, 아래면 내리는 중.'],
  ['VIX', '앞으로 한 달 미국 주가가 얼마나 출렁일지에 대한 시장의 예상. 높을수록 불안.'],
  ['최대 낙폭', '고점에서 가장 많이 떨어졌던 폭. 버틸 수 있는 손실인지 보는 값.'],
  ['내린 달 빠짐', '시장이 내린 달에 이 전략이 평균 몇 %만큼 따라 빠졌는지. 낮을수록 잃을 때 조금.'],
  ['오른 달 따라감', '시장이 오른 달에 몇 %만큼 따라 올랐는지. 높을수록 벌 때 많이.'],
  ['PER', '주가가 1년 이익의 몇 배인지. 높을수록 미래 성장을 비싸게 사는 중.'],
  ['베타', '시장이 1% 움직일 때 이 종목이 몇 % 움직이는지.'],
  ['장단기 금리차', '10년 금리 − 2년(또는 3개월) 금리. 마이너스면 과거에 경기 침체 전 신호였던 경우가 많음.'],
];
