import test from 'node:test';
import assert from 'node:assert/strict';
import { rankItems, barSpan } from '../lib/trend.ts';

// 고정 가짜 값 (테스트 전용)
const it = (code, kind, market, r) => ({ code, name: code, kind, market, r });
const UNIVERSE = [
  it('FAKE1', '업종', 'US', [1, 3.0, 1]), it('FAKE2', '업종', 'US', [1, 2.6, 1]), it('FAKE3', '업종', 'US', [1, 2.9, 1]),
  it('FAKE4', '업종', 'US', [1, -2.2, 1]), it('FAKE5', '업종', 'US', [1, null, 1]), it('FAKE6', '주식', 'US', [1, 9, 1]),
  it('TEST04', '주식', 'KR', [1, 1, -5]), it('TEST05', '주식', 'KR', [1, 1, -9]), it('TEST06', '주식', 'KR', [1, 1, 2]),
  it('FAKEW', '나라', 'W', [1, 1, 1]),
];

test('강한 곳/약한 곳 정렬과 필터', () => {
  const s = rankItems(UNIVERSE, 'US', '업종', 1, true, 3);
  assert.deepEqual(s.map((x) => x.code), ['FAKE1', 'FAKE3', 'FAKE2']);
  const w = rankItems(UNIVERSE, 'KR', '주식', 2, false, 2);
  assert.deepEqual(w.map((x) => x.code), ['TEST05', 'TEST04']);
  assert.ok(rankItems(UNIVERSE, 'W', '주식', 0, true).every((x) => x.kind === '나라'));
});

test('막대 위치', () => {
  assert.deepEqual(barSpan(10, 10), { left: 50, width: 48 });
  assert.deepEqual(barSpan(-5, 10), { left: 26, width: 24 });
  assert.deepEqual(barSpan(1, 0), { left: 50, width: 48 });
});
