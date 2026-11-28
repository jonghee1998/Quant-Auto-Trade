import test from 'node:test';
import assert from 'node:assert/strict';
import { pct, pp, num, won, tone, moveLabel } from '../lib/format.ts';

test('빈 값·NaN은 —로 표시', () => {
  for (const v of [null, undefined, NaN, Infinity]) {
    assert.equal(pct(v), '—'); assert.equal(pp(v), '—'); assert.equal(num(v), '—'); assert.equal(won(v), '—');
    assert.equal(tone(v), 'flat');
  }
});

test('부호와 단위', () => {
  assert.equal(pct(1.234), '+1.2%');
  assert.equal(pct(-3.45), '−3.5%');
  assert.equal(pct(0), '0.0%');
  assert.equal(pp(2), '+2.0%p');
  assert.equal(won(10412000.4), '10,412,000원'); // pii-allow (가짜 금액)
  assert.equal(tone(0.1), 'up'); assert.equal(tone(-0.1), 'down');
});

test('평소 움직임 대비 판정', () => {
  assert.equal(moveLabel(0.6, 0.9), '평소 수준');
  assert.equal(moveLabel(-2.1, 1.0), '큰 움직임');
  assert.equal(moveLabel(1, 0), '—');
});

test('지표 값 소수 자리: 금리는 둘째 자리(4.21%가 4%로 보이지 않게), VIX는 첫째 자리, 나머지는 정수', async () => {
  const { quoteDigits, num } = await import('../lib/format.ts');
  assert.equal(quoteDigits('us10y', '%'), 2);
  assert.equal(quoteDigits('vix'), 1);
  assert.equal(quoteDigits('spx'), 0);
  assert.equal(quoteDigits('usdkrw', '원'), 0);
  assert.equal(num(4.21, quoteDigits('us10y', '%')), '4.21');
});

test('문장 나누기: 마침표 뒤 공백에서만 끊고 소수점은 끊지 않는다', async () => {
  const { sentences } = await import('../lib/format.ts');
  assert.deepEqual(sentences('S&P 500이 5.2% 위에 있어요. 다만 불안해요. 왜일까요? 끝.'), ['S&P 500이 5.2% 위에 있어요.', '다만 불안해요.', '왜일까요?', '끝.']);
  assert.deepEqual(sentences(''), []);
  assert.deepEqual(sentences(null), []);
  assert.deepEqual(sentences('한 문장'), ['한 문장']);
});

test('좁은 칸용 짧은 이름', async () => {
  const { shortName } = await import('../lib/format.ts');
  assert.equal(shortName('미국 S&P 500 (SPY)'), 'S&P 500');
  assert.equal(shortName('미국 나스닥 100 (QQQ)'), '나스닥 100');
  assert.equal(shortName('한국 코스피'), '코스피');
  assert.equal(shortName('VIX (불안 지수)'), 'VIX');
  assert.equal(shortName('미국'), '미국');
});
