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
