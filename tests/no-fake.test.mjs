// 화면에 가짜 데이터가 다시 들어오지 않게 막는다: mock 모듈·'예시' 문구 금지.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const walk = (d) => readdirSync(d).flatMap((f) => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : [p]; });

test('화면 코드에 가짜 데이터 없음', () => {
  assert.ok(!existsSync('lib/mock.ts'), 'lib/mock.ts는 지웠다. 빈 영역은 <Planned>로 덮는다');
  const files = ['app', 'components', 'lib'].flatMap(walk).filter((f) => /\.(tsx?|mjs)$/.test(f));
  for (const f of files) {
    const s = readFileSync(f, 'utf8');
    assert.ok(!/from ['"][./]+.*mock['"]/.test(s), `${f}: mock import 금지`);
    assert.ok(!/예시 ?값|\(예시\)/.test(s), `${f}: '예시' 값 표시 금지 — 실데이터 또는 <Planned>/<Connecting>`);
  }
});
