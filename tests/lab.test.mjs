import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ROUNDS } from '../lib/labRounds.ts';

const idsIn = (src, from, to) => [...src.slice(src.indexOf(from), src.indexOf(to)).matchAll(/Exp\("((?:R4_)?[A-Z]\d+[a-z]?)"/g)].map((m) => m[1]).sort();
const src = readFileSync('quant/forecast/experiments.py', 'utf8');
const src5 = readFileSync('quant/forecast/round5.py', 'utf8');

test('화면 실험 목록 = 코드 실험 목록(1차 30개·2차 11개, 하나씩 다 있음)', () => {
  const r1 = ROUNDS.find((r) => r.round === 1).exps.map((e) => e.id).sort();
  const r2 = ROUNDS.find((r) => r.round === 2).exps.map((e) => e.id).sort();
  assert.deepEqual(r1, idsIn(src, 'ROUND1: list[Exp]', 'assert len(ROUND1)'));
  assert.deepEqual(r2, idsIn(src, 'ROUND2: list[Exp]', 'BENCHMARKS'));
  const r3 = ROUNDS.find((r) => r.round === 3).exps.map((e) => e.id).sort();
  assert.deepEqual(r3, idsIn(src, 'ROUND3: list[Exp]', 'BENCHMARKS3'));
  const r4 = ROUNDS.find((r) => r.round === 4).exps.map((e) => e.id).sort();
  assert.deepEqual(r4, idsIn(src, 'ROUND4: list[Exp]', 'BENCHMARKS4'));
  const r5 = ROUNDS.find((r) => r.round === 5).exps.map((e) => e.id).sort();
  const ids5 = [...src5.slice(src5.indexOf('ROUND5: list[E5]'), src5.indexOf('BENCH5')).matchAll(/E5\("(R5_[A-Z]\d)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(r5, ids5);
  const src6 = readFileSync('quant/forecast/round6.py', 'utf8');
  const ids6 = [...src6.slice(src6.indexOf('ROUND6: list[E6]'), src6.indexOf('BENCH6')).matchAll(/E6\("(R6_[A-Z]\d)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(ROUNDS.find((r) => r.round === 6).exps.map((e) => e.id).sort(), ids6);
  const src7 = readFileSync('quant/forecast/round7.py', 'utf8');
  const ids7 = [...src7.slice(src7.indexOf('ROUND7: list[E7]'), src7.indexOf('BENCH7')).matchAll(/E7\("(R7_[A-Z]\d)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(ROUNDS.find((r) => r.round === 7).exps.map((e) => e.id).sort(), ids7);
});

test('실험마다 한 줄 요약·접근·결과가 다 있다', () => {
  for (const r of ROUNDS) for (const e of r.exps) {
    assert.ok(e.name && e.approach && e.note, `${e.id} 빈 칸`);
    for (const k of ['ret', 'bench', 'mdd', 'benchMdd']) assert.ok(Number.isFinite(e.dev[k]), `${e.id}.${k}`);
  }
});

test('성적판 집계: 판정별 개수와 칸 목록(오래된 라운드부터, 라운드 사이 빈칸)', async () => {
  const { ROUNDS, labTally, divergeSpan } = await import('../lib/labRounds.ts');
  const t = labTally();
  const n = ROUNDS.reduce((a, r) => a + r.exps.length, 0);
  assert.equal(t.total, n);
  assert.equal(t.count.후보 + t.count.보류 + t.count.탈락, n);
  assert.equal(t.cells.filter((c) => c === null).length, ROUNDS.length - 1);
  const first = [...ROUNDS].sort((a, b) => a.round - b.round)[0];
  assert.deepEqual(t.cells.slice(0, first.exps.length), first.exps.map((e) => e.v));
  const two = labTally([{ round: 2, exps: [{ v: '탈락' }] }, { round: 1, exps: [{ v: '보류' }, { v: '후보' }] }]);
  assert.deepEqual(two.cells, ['보류', '후보', null, '탈락']);
  assert.deepEqual(two.count, { 후보: 1, 보류: 1, 탈락: 1 });
  assert.deepEqual(divergeSpan(4, 8), { left: 50, width: 25, good: true });   // 좋은 쪽은 가운데에서 오른쪽으로
  assert.deepEqual(divergeSpan(-4, 8), { left: 25, width: 25, good: false }); // 나쁜 쪽은 왼쪽으로
  assert.deepEqual(divergeSpan(-99, 8), { left: 0, width: 50, good: false }); // 한계에서 자름
  assert.deepEqual(divergeSpan(-0.1, 8), { left: 47, width: 3, good: false }); // 아주 작은 차이도 보이게
});
