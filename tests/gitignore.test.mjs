// 소스 파일이 .gitignore에 걸려 커밋·배포에서 빠지는 일을 막는다(app/data가 'data/' 규칙에 걸려 배포에서 404였다).
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const walk = (d) => readdirSync(d).flatMap((f) => { const p = join(d, f); return statSync(p).isDirectory() ? (f === '__pycache__' ? [] : walk(p)) : [p]; });

test('소스 폴더의 파일은 하나도 .gitignore에 걸리지 않는다', () => {
  const files = ['app', 'components', 'lib', 'quant', 'db', 'tests'].flatMap(walk).filter((f) => /\.(tsx?|mjs|py|sql|css)$/.test(f));
  let out = '';
  try {
    out = execFileSync('git', ['check-ignore', '--stdin'], { input: files.join('\n'), encoding: 'utf8' });
  } catch (e) {
    if (e.status !== 1) throw e; // 1 = 걸린 파일 없음
  }
  assert.equal(out.trim(), '', `.gitignore에 걸린 소스: ${out}`);
});
