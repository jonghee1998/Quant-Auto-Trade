import test from 'node:test';
import assert from 'node:assert/strict';
import { memo, memoClear } from '../lib/memo.ts';
import { nearestIndex, shortDate, sparkPoints } from '../lib/spark.ts';

test('memo: 기한 안에는 다시 읽지 않고, 지나면 다시 읽는다', async () => {
  memoClear();
  let t = 1000, calls = 0;
  const load = async () => ++calls;
  const now = () => t;
  assert.equal(await memo('k', 100, load, undefined, now), 1);
  t += 99; assert.equal(await memo('k', 100, load, undefined, now), 1);
  t += 2; assert.equal(await memo('k', 100, load, undefined, now), 2);
  assert.equal(calls, 2);
});

test('memo: 실패·빈 값은 기억하지 않는다(다음에 다시 읽는다)', async () => {
  memoClear();
  const seq = [null, 'TEST01'];
  let calls = 0;
  const load = async () => seq[calls++];
  const keep = (v) => v !== null;
  assert.equal(await memo('d', 1000, load, keep, () => 0), null);
  assert.equal(await memo('d', 1000, load, keep, () => 0), 'TEST01');
  assert.equal(await memo('d', 1000, load, keep, () => 0), 'TEST01');
  assert.equal(calls, 2);
});

test('memo: 키가 다르면 따로 기억한다', async () => {
  memoClear();
  assert.equal(await memo('a', 1000, async () => 'A'), 'A');
  assert.equal(await memo('b', 1000, async () => 'B'), 'B');
  assert.equal(await memo('a', 1000, async () => 'X'), 'A');
});

test('차트: 누른 위치에서 가장 가까운 점을 고른다', () => {
  assert.equal(nearestIndex(0, 53), 0);
  assert.equal(nearestIndex(1, 53), 52);
  assert.equal(nearestIndex(0.5, 53), 26);
  assert.equal(nearestIndex(-0.3, 53), 0);
  assert.equal(nearestIndex(1.4, 53), 52);
  assert.equal(nearestIndex(NaN, 53), 0);
  assert.equal(nearestIndex(0.5, 1), 0);
});

test('차트: 빈 값은 빼고 날짜는 짧게', () => {
  assert.deepEqual(sparkPoints([['2026-01-02', 10], ['2026-01-09', null], ['2026-01-16', 12]]), [['2026-01-02', 10], ['2026-01-16', 12]]);
  assert.equal(shortDate('2026-03-06'), '26.03.06');
});
