import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ROUNDS } from '../lib/labRounds.ts';

const idsIn = (src, from, to) => [...src.slice(src.indexOf(from), src.indexOf(to)).matchAll(/Exp\("([A-Z]\d\d)"/g)].map((m) => m[1]).sort();
const src = readFileSync('quant/forecast/experiments.py', 'utf8');

test('화면 실험 목록 = 코드 실험 목록(1차 30개·2차 11개, 하나씩 다 있음)', () => {
  const r1 = ROUNDS.find((r) => r.round === 1).exps.map((e) => e.id).sort();
  const r2 = ROUNDS.find((r) => r.round === 2).exps.map((e) => e.id).sort();
  assert.deepEqual(r1, idsIn(src, 'ROUND1: list[Exp]', 'assert len(ROUND1)'));
  assert.deepEqual(r2, idsIn(src, 'ROUND2: list[Exp]', 'BENCHMARKS'));
  const r3 = ROUNDS.find((r) => r.round === 3).exps.map((e) => e.id).sort();
  assert.deepEqual(r3, idsIn(src, 'ROUND3: list[Exp]', 'BENCHMARKS3'));
});

test('실험마다 한 줄 요약·접근·결과가 다 있다', () => {
  for (const r of ROUNDS) for (const e of r.exps) {
    assert.ok(e.name && e.approach && e.note, `${e.id} 빈 칸`);
    for (const k of ['ret', 'bench', 'mdd', 'benchMdd']) assert.ok(Number.isFinite(e.dev[k]), `${e.id}.${k}`);
  }
});
