#!/usr/bin/env node
// 공개 저장소 개인정보 검사: PR(또는 push)에서 "추가된 줄"만 보고 실데이터 패턴을 찾으면 실패한다.
// 사용: node scripts/orch/pii-scan.mjs [base-ref]   (기본 base: origin/main, 없으면 HEAD~1)
// 줄 끝에 `pii-allow` 주석이 있으면 그 줄은 건너뛴다(가짜 데이터임을 사람이 확인한 경우만).
// 이 파일은 scripts/orch/ 에 있어 구현 AI가 바꿀 수 없다.
import { execFileSync } from "node:child_process";

export const RULES = [
  { name: "카드번호", re: /(?<![0-9A-Fa-f-])\d{4}-\d{4}-\d{4}-\d{4}(?![0-9A-Fa-f-])/ },
  { name: "카드번호(붙여쓰기)", re: /(?<![0-9A-Za-z])\d{16}(?![0-9A-Za-z])/ },
  { name: "휴대폰 번호", re: /(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)/ },
  { name: "주민등록번호", re: /(?<!\d)\d{6}-[1-4]\d{6}(?!\d)/ },
  { name: "금액(원)", re: /(?<![0-9,])(?:[1-9]\d{4,}|[1-9]\d{0,2}(?:,\d{3}){1,})(?=\s?원)/, min: 10000 },
  { name: "JWT/Supabase 키", re: /eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}/ },
  { name: "Supabase 비밀키", re: /sb_secret_[A-Za-z0-9_-]{10,}/ },
];
const SKIP_FILES = [/^package-lock\.json$/, /^scripts\/orch\/pii-scan(\.test)?\.mjs$/];

/** unified diff → [{file, line, text}] (추가된 줄만) */
export function addedLines(diff) {
  const out = []; let file = null, ln = 0;
  for (const raw of diff.split("\n")) {
    if (raw.startsWith("+++ ")) { file = raw.slice(4).replace(/^b\//, ""); continue; }
    const h = /^@@ -\d+(?:,\d+)? \+(\d+)/.exec(raw);
    if (h) { ln = Number(h[1]); continue; }
    if (!file || file === "/dev/null") continue;
    if (raw.startsWith("+")) { out.push({ file, line: ln, text: raw.slice(1) }); ln++; }
    else if (!raw.startsWith("-")) ln++;
  }
  return out;
}

export function scan(lines) {
  const hits = [];
  for (const l of lines) {
    if (SKIP_FILES.some((r) => r.test(l.file))) continue;
    if (/pii-allow/.test(l.text)) continue;
    for (const r of RULES) {
      const g = new RegExp(r.re.source, "g");
      const ok = [...l.text.matchAll(g)].some((m) => !r.min || Number(m[0].replace(/,/g, "")) >= r.min); // 1만원 미만은 예시·설명으로 봄
      if (ok) hits.push({ ...l, rule: r.name });
    }
  }
  return hits;
}

function main() {
  const base = process.argv[2] || process.env.PII_BASE || "origin/main";
  let diff;
  try { diff = execFileSync("git", ["diff", "--unified=0", `${base}...HEAD`], { encoding: "utf8", maxBuffer: 64 << 20 }); }
  catch { diff = execFileSync("git", ["diff", "--unified=0", "HEAD~1", "HEAD"], { encoding: "utf8", maxBuffer: 64 << 20 }); }
  const hits = scan(addedLines(diff));
  if (!hits.length) { console.log("pii-scan: 추가된 줄에서 개인정보 패턴 없음"); return; }
  // 값은 다시 출력하지 않는다(공개 로그). 위치와 종류만.
  for (const h of hits) console.log(`::error file=${h.file},line=${h.line}::개인정보 의심(${h.rule}) — 실데이터면 지우고, 가짜 데이터면 줄 끝에 pii-allow 주석`);
  process.exitCode = 1;
}
if (import.meta.url === `file://${process.argv[1]}`) main();
