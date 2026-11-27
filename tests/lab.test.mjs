import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ROUNDS, roundIds, sortCards, toRow, verdictOf } from '../lib/labRounds.ts';

test('2차 실험 11개 모두 판정이 있다(실험 목록과 화면이 어긋나지 않게)', () => {
  const src = readFileSync('quant/forecast/experiments.py', 'utf8');
  const r2 = src.slice(src.indexOf('ROUND2: list[Exp]'), src.indexOf('BENCHMARKS'));
  const ids = [...r2.matchAll(/Exp\("([A-Z]\d\d)"/g)].map((m) => m[1]);
  assert.equal(ids.length, 11);
  const round = ROUNDS.find((r) => r.plan === 59);
  for (const id of ids) assert.ok(verdictOf(round, id), `${id} 판정 없음`);
  assert.equal(new Set(roundIds(round)).size, roundIds(round).length);
});

test('1차 30개 모두 판정이 있다', () => {
  const r1 = ROUNDS.find((r) => r.round === 1);
  assert.equal(new Set(roundIds(r1)).size, 30);
});

test('2차는 청산 세후, 1차는 세금 전 연수익을 읽는다', () => {
  const a = toRow({ strategy: 'TEST01', period: 'dev', plan: '59', at: '2026-01-01', m: { liq_cagr: 0.08, bench_liq_cagr: 0.1, cagr: 0.2, mdd: -0.2, ic_hit: 0.6 } });
  assert.equal(a.ret, 0.08); assert.equal(a.liq, true); assert.equal(a.plan, 59); assert.equal(a.hit, 0.6);
  const b = toRow({ strategy: 'TEST02', period: 'valid', plan: null, at: '2026-01-01', m: { cagr: 0.12, bench_cagr: 0.1, mdd: 'x' } });
  assert.equal(b.ret, 0.12); assert.equal(b.liq, false); assert.equal(b.mdd, null); assert.equal(b.plan, null);
});

test('카드 순서: 후보 → 보류 → 탈락, 같으면 S&P 대비 큰 순', () => {
  const s = sortCards([{ id: 'X', v: '탈락', gap: 0.05 }, { id: 'Y', v: '보류', gap: -0.1 }, { id: 'Z', v: '탈락', gap: 0.1 }, { id: 'W', v: '후보', gap: -0.2 }]);
  assert.deepEqual(s.map((x) => x.id), ['W', 'Y', 'Z', 'X']);
});
