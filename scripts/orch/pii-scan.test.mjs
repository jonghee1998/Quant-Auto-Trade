import test from "node:test";
import assert from "node:assert/strict";
import { addedLines, scan } from "./pii-scan.mjs";

const diff = (lines) => ["+++ b/x.ts", "@@ -0,0 +1," + lines.length + " @@", ...lines.map((l) => "+" + l)].join("\n");
const rules = (lines) => scan(addedLines(diff(lines))).map((h) => h.rule);

test("UUID 는 카드번호로 잡지 않는다", () => {
  assert.deepEqual(rules(["id:'00000000-0000-4000-8000-000000000001'"]), []);
});
test("카드번호·휴대폰·주민번호·쉼표 금액·키를 잡는다", () => {
  assert.deepEqual(rules(["1234-5678-9012-3456"]), ["카드번호"]);
  assert.deepEqual(rules(["010-1234-5678"]), ["휴대폰 번호"]);
  assert.deepEqual(rules(["900101-1234567"]), ["주민등록번호"]);
  assert.deepEqual(rules(["총 12,500원"]), ["금액(원)"]);
  assert.deepEqual(rules(["1234567원"]), ["금액(원)"]);
  assert.deepEqual(rules(["1,000원 아니고 12,500원"]), ["금액(원)"]);
  assert.deepEqual(rules(["sb_secret_abcdefghijkl"]), ["Supabase 비밀키"]);
});
test("작은 금액과 pii-allow 줄은 통과", () => {
  assert.deepEqual(rules(["1,000원 차이"]), []);
  assert.deepEqual(rules(["'12,500원' // pii-allow 가짜 예시"]), []);
});
test("삭제된 줄과 줄 번호", () => {
  const d = ["+++ b/a.md", "@@ -1,2 +1,2 @@", "-12,500원", " keep", "+010-1111-2222"].join("\n");
  const h = scan(addedLines(d));
  assert.equal(h.length, 1); assert.equal(h[0].line, 2); assert.equal(h[0].file, "a.md");
});
