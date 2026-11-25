import test from 'node:test';
import assert from 'node:assert/strict';
import { rankItems, barSpan } from '../lib/trend.ts';
import { UNIVERSE } from '../lib/mock.ts';

test('강한 곳/약한 곳 정렬과 필터', () => {
  const s = rankItems(UNIVERSE, 'US', '업종', 1, true, 3);
  assert.deepEqual(s.map((x) => x.code), ['XLK', 'GLD', 'XLC']);
  const w = rankItems(UNIVERSE, 'KR', '주식', 2, false, 2);
  assert.deepEqual(w.map((x) => x.code), ['000005', '000004']);
  assert.ok(rankItems(UNIVERSE, 'W', '주식', 0, true).every((x) => x.kind === '나라'));
});

test('막대 위치', () => {
  assert.deepEqual(barSpan(10, 10), { left: 50, width: 48 });
  assert.deepEqual(barSpan(-5, 10), { left: 26, width: 24 });
  assert.deepEqual(barSpan(1, 0), { left: 50, width: 48 });
});
