// テストの実行: node tests/run.mjs [名前の一部 ...]
// 各 *.test.mjs は `export default async function (t) {}` を出す。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { launch, openGame, OUT_DIR } from './lib/harness.mjs';

const dir = path.dirname(fileURLToPath(import.meta.url));
const filters = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const strictAll = process.argv.includes('--strict');
const files = fs.readdirSync(dir).filter((f) => f.endsWith('.test.mjs')).filter((f) => !filters.length || filters.some((k) => f.includes(k))).sort();
if (!files.length) {
  console.log('該当するテストがありません');
  process.exit(1);
}

const env = await launch();
const results = [];
for (const f of files) {
  const mod = await import(pathToFileURL(path.join(dir, f)).href);
  const failures = [];
  const notes = [];
  const handles = [];
  let required = [];
  const t = {
    // 本物でないと困るモジュールを宣言する（代役で動いていたら失敗）
    require(...names) { required.push(...names); },
    async open(opts = {}) { const h = await openGame(env, opts); handles.push(h); return h; },
    ok(cond, msg) { if (!cond) failures.push(msg); return !!cond; },
    eq(a, b, msg) { if (a !== b) failures.push(`${msg}: ${JSON.stringify(a)} !== ${JSON.stringify(b)}`); return a === b; },
    near(a, b, tol, msg) { const ok = Math.abs(a - b) <= tol; if (!ok) failures.push(`${msg}: ${a} は ${b}±${tol} の外`); return ok; },
    log(...a) { notes.push(a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' ')); },
    out: OUT_DIR,
  };
  const t0 = Date.now();
  const timeoutMs = mod.timeout || 240000;
  try {
    await Promise.race([
      mod.default(t),
      new Promise((_, rej) => setTimeout(() => rej(new Error(`時間切れ (${timeoutMs / 1000}s)`)), timeoutMs)),
    ]);
  } catch (err) {
    failures.push(`例外: ${err && err.stack || err}`);
  }
  // 後始末と共通の確認
  for (const h of handles) {
    try {
      const snap = await h.snapshot();
      for (const e of snap.errors) failures.push(`game.errors: ${e}`);
      const fb = snap.fallbacks || [];
      const must = strictAll ? fb : fb.filter((n) => required.includes(n));
      for (const n of must) failures.push(`${n} が代役（stub）で動いている。本物の読み込みに失敗した`);
      if (fb.length && !strictAll) notes.push(`代役のモジュール: ${fb.join(', ')}`);
    } catch (err) {
      failures.push(`snapshot に失敗: ${err.message}`);
    }
    for (const e of h.pageErrors) failures.push(`pageerror: ${e}`);
    for (const e of h.consoleErrors) if (!/fonts\.(googleapis|gstatic)|ERR_FAILED|Failed to load resource/.test(e)) notes.push(`console.error: ${e.slice(0, 300)}`);
    await h.close().catch(() => {});
  }
  const ms = Date.now() - t0;
  const pass = failures.length === 0;
  results.push({ file: f, pass, ms, failures, notes });
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${f}  (${(ms / 1000).toFixed(1)}s)`);
  for (const n of notes) console.log(`      · ${n}`);
  for (const x of failures) console.log(`      ✗ ${x}`);
}
await env.browser.close();
env.server.close();
fs.writeFileSync(path.join(OUT_DIR, 'report.json'), JSON.stringify(results, null, 2));
const failed = results.filter((r) => !r.pass).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
