// NIGHT RUNNER: 挙動テストの 1 ファイル分を走らせる（test_nr.py が作業フォルダに __nr_runner.mjs として置く）。
//
//   node __nr_runner.mjs <tests/xxx.mjs> <結果の JSON の置き場所>
//   環境変数: NR_ENTRY   アドオンの入口（作業フォルダからの相対。既定 scripts/main.js。"-" で読まない）
//             NR_FILTER  -k の文字列（テスト名かファイル名に含むものだけ）
//             NR_VERBOSE 1 ならアドオンの console.* をそのまま出す
//
// 流れ（v2-overview.md の起動の順）:
//   1. 偽の @minecraft/server を読む（ガードの取り付けまで）。ゲームに無いグローバルを隠す
//   2. アドオンの入口を import（early execution）→ Promise を一度流す → system.beforeEvents.startup
//      → BP が使うのに登録されていないカスタムコンポーネントを違反にする
//   3. テストファイルを import（test() の登録）
//   4. 最初の tick → world.afterEvents.worldLoad（ここで early execution が終わる）
//   5. テストを順に走らせ、結果を JSON に書く
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const [testRel, outPath] = process.argv.slice(2);
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const verbose = process.env.NR_VERBOSE === "1";
const entry = process.env.NR_ENTRY ?? "scripts/main.js";
const filter = process.env.NR_FILTER ?? "";
const REAL = globalThis.__nrReal = { setImmediate, setTimeout, clearTimeout, setInterval, clearInterval };
const write = (s) => process.stdout.write(s + "\n");

const mc = await import("@minecraft/server");
await import("@minecraft/server-ui");
const S = globalThis.__nr;
void mc;

// ---- console（ゲームではコンテンツログ）を捕まえる ----
function fmtArgs(a) {
  return a.map((x) => (typeof x === "string" ? x : x instanceof Error ? `${x.name}: ${x.message}` : S.fmt(x))).join(" ");
}
function whereNow() {
  for (const ln of String(new Error().stack || "").split("\n").slice(2)) {
    const m = ln.match(/\/((?:scripts|tests)\/[^:)]+):(\d+):\d+\)?\s*$/);
    if (m) return `${m[1]}:${m[2]}`;
  }
  return "";
}
console.log = (...a) => { const s = fmtArgs(a); S.logs.push(s); if (verbose) write(`      [log] ${s}`); };
console.info = console.log;
console.debug = console.log;
console.warn = (...a) => { const s = fmtArgs(a); S.warns.push({ msg: s, tick: S.tick, where: whereNow() }); if (verbose) write(`      [warn] ${s}`); };
console.error = (...a) => { const s = fmtArgs(a); S.consoleErrors.push({ msg: s, tick: S.tick, where: whereNow() }); if (verbose) write(`      [error] ${s}`); };

// ---- ゲームに無いグローバル（読むと違反。tsc でも TS2304 になる） ----
for (const name of ["setTimeout", "setInterval", "setImmediate", "clearTimeout", "clearInterval", "clearImmediate", "fetch"]) {
  Object.defineProperty(globalThis, name, {
    configurable: true,
    get() {
      throw S.violation("global", `${name} はゲームに無い — system.runTimeout / runInterval / runJob / waitTicks を使う`, ReferenceError);
    },
  });
}
process.on("unhandledRejection", (e) => S.recordError("Promise（捕まらない reject）", e));
process.on("uncaughtException", (e) => S.recordError("捕まらない例外", e));

const H = await import("nr-test");
const result = { file: testRel, entry, boot: { ok: true, missing: false, errors: [], violations: [], consoleErrors: [] },
  fileError: null, tests: [], names: [] };

// ---- 2. アドオンを起動 ----
if (entry !== "-") {
  const abs = path.join(ROOT, entry);
  if (fs.existsSync(abs)) {
    try { await import(pathToFileURL(abs).href); }
    catch (e) {
      result.boot.ok = false;
      result.boot.errors.push({ where: `import ${entry}`, msg: `${e?.name ?? "Error"}: ${e?.message ?? e}`, stack: String(e?.stack ?? "").split("\n").slice(1, 5).map((s) => s.trim()) });
    }
  } else {
    result.boot.missing = true;
  }
}
await H.__drain();
S.__startup();
for (const m of S.unregisteredCustomComponents()) {
  S.violations.push({ kind: "startup", msg: `BP が使うのに system.beforeEvents.startup で登録されていないカスタムコンポーネント ${m}（実機ではそのブロック／アイテムが読み込みエラー）`, where: "", tick: 0 });
}
await H.__drain();

// ---- 3. テストファイル ----
try { await import(pathToFileURL(path.join(ROOT, testRel)).href); }
catch (e) { result.fileError = { msg: `${e?.name ?? "Error"}: ${e?.message ?? e}`, stack: String(e?.stack ?? "").split("\n").slice(1, 5).map((s) => s.trim()) }; }
result.names = H.__testNames();

// ---- 4. 最初の tick と worldLoad ----
S.early = false; S.phase = "world";
S.__tick();
S.__worldLoad();
await H.__drain();
result.boot.violations = S.violations.splice(0);
result.boot.errors.push(...S.errors.splice(0));
result.boot.consoleErrors = S.consoleErrors.splice(0);
if (result.boot.violations.length || result.boot.errors.length || result.boot.consoleErrors.length) result.boot.ok = false;
if (H.__dataErrors.length) result.boot.dataErrors = H.__dataErrors;

// ---- 5. テスト ----
if (!result.fileError && !(result.boot.errors.length && result.boot.errors[0].where.startsWith("import"))) {
  result.tests = await H.__runTests({ filter, file: testRel });
}

const mapObj = (m) => Object.fromEntries([...m].sort((a, b) => (a[0] < b[0] ? -1 : 1)));
const L = S.log;
result.usage = {
  particles: mapObj(L.particles), sounds: mapObj(L.sounds), anims: mapObj(L.anims), events: mapObj(L.events),
  props: mapObj(L.props), spawned: mapObj(L.spawned), structures: mapObj(L.structures), effects: mapObj(L.effects),
  molangVars: mapObj(L.molangVars), forms: mapObj(S.uiShown ?? new Map()),
  hurts: L.hurts, deaths: L.deaths, camera: L.camera, titles: L.titles, actionbars: L.actionbars, removed: L.removed,
  commands: L.commands.length, messages: L.messages.length,
};
result.maxPerTick = S.maxPerTick;
result.maxPerTickAt = S.maxPerTickAt;
result.limitations = mapObj(S.limitations);
result.notices = mapObj(S.notices);
result.warns = S.warns.length;
result.warnSamples = S.warns.slice(0, 8);
result.ticks = S.tick;
result.leftoverViolations = S.violations.slice();   // テストの外（片付け中など）で起きた違反
fs.writeFileSync(outPath, JSON.stringify(result, (k, v) => (v instanceof Map ? Object.fromEntries(v) : v)));
process.exit(0);
