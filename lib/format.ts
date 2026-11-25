// 숫자 표시 규칙: 값이 없거나 숫자가 아니면 "—". undefined·NaN을 화면에 내보내지 않는다.
export type Num = number | null | undefined;

const ok = (v: Num): v is number => typeof v === 'number' && Number.isFinite(v);

/** +1.2% / −3.4% (빈 값은 —). */
export function pct(v: Num, digits = 1): string {
  if (!ok(v)) return '—';
  const s = Math.abs(v).toFixed(digits);
  return (v > 0 ? '+' : v < 0 ? '−' : '') + s + '%';
}

/** 퍼센트 포인트 차이: +1.2%p */
export function pp(v: Num, digits = 1): string {
  return ok(v) ? pct(v, digits).replace('%', '%p') : '—';
}

/** 천 단위 구분 숫자 (빈 값은 —). */
export function num(v: Num, digits = 0): string {
  if (!ok(v)) return '—';
  return v.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** 원화 금액: 10,412,000원 */
export function won(v: Num): string {
  return ok(v) ? `${num(Math.round(v))}원` : '—';
}

/** 상승 빨강·하락 파랑·0/빈 값 회색 (한국식). */
export function tone(v: Num): 'up' | 'down' | 'flat' {
  if (!ok(v) || v === 0) return 'flat';
  return v > 0 ? 'up' : 'down';
}

/** 오늘 변화가 평소 하루 움직임(표준편차) 대비 큰지: |z| ≥ 2 → 큰 움직임. */
export function moveLabel(change: Num, dailyStd: Num): '평소 수준' | '큰 움직임' | '—' {
  if (!ok(change) || !ok(dailyStd) || dailyStd <= 0) return '—';
  return Math.abs(change / dailyStd) >= 2 ? '큰 움직임' : '평소 수준';
}
