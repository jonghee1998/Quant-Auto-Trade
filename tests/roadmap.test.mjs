import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const r = JSON.parse(readFileSync(new URL('../docs/roadmap.json', import.meta.url), 'utf8'));
const STATUS = new Set(['todo', 'doing', 'done', 'na']);

test('roadmap.json: setup·phases 항목 형식과 상태 값', () => {
  assert.equal(r.version, 1);
  for (const list of [r.setup, r.phases]) {
    assert.ok(Array.isArray(list) && list.length > 0);
    for (const p of list) {
      assert.equal(typeof p.id, 'string');
      assert.equal(typeof p.title, 'string');
      assert.ok(STATUS.has(p.status), `${p.id} status ${p.status}`);
    }
  }
  assert.deepEqual(r.phases.map((p) => p.id), ['0', '1', '2', '3', '4', '5', '6', '7']);
});
