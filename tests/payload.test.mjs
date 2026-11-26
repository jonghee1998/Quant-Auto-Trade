import test from 'node:test';
import assert from 'node:assert/strict';
import { fromPayload } from '../lib/payload.ts';
import { rankItems } from '../lib/trend.ts';

test('payload 검사: 모양이 다르면 null, 빈 값은 null로', () => {
  assert.equal(fromPayload(null), null);
  assert.equal(fromPayload({ quotes: 'x', summary: 's' }), null);
  const d = fromPayload({ summary: '합성 요약', quotes: [], trendLight: { state: 'blue' }, universe: [{ code: 'TEST01', name: '가짜종목A', kind: '업종', market: 'US', r: [1, 'x'] }] });
  assert.equal(d.sample, false);
  assert.equal(d.trendLight.state, null);
  assert.deepEqual(d.universe[0].r, [1, null]);
  assert.deepEqual(d.bench.US, [null, null, null]);
});

test('값 없는 종목은 순위에서 제외', () => {
  const items = [{ code: 'A', name: 'a', kind: '업종', market: 'US', r: [1, null, 1] }, { code: 'B', name: 'b', kind: '업종', market: 'US', r: [2, 3, 2] }];
  assert.deepEqual(rankItems(items, 'US', '업종', 1, true).map((x) => x.code), ['B']);
});

test('AI·신호등·종목 수: 없거나 모양이 틀리면 빈 값', () => {
  const base = { summary: '합성 요약', quotes: [] };
  const d = fromPayload(base);
  assert.deepEqual(d.ai, {});
  assert.equal(d.signals, null);
  assert.deepEqual(d.coverage, {});
  const e = fromPayload({ ...base, ai: { today: { what: '합성', why: '합성', why_news: [], next: [] } }, signals: { state: 'green', good: 3, items: [] }, coverage: { 'KR/주식': { shown: 3, total: 9 } } });
  assert.equal(e.ai.today.what, '합성');
  assert.equal(e.signals.state, 'green');
  assert.equal(e.coverage['KR/주식'].total, 9);
  assert.equal(fromPayload({ ...base, signals: { state: 'green' } }).signals, null);
});
