// nr-test — NIGHT RUNNER の挙動テストの道具（test_nr.py が node_modules/nr-test/index.js に置く）。
//
// テストファイル（tools/nightrunner/tests/<名前>.mjs）から import して使う:
//
//   import { test, tick, spawnZombie, spawnPlayer, hit, expect, prop, used } from "nr-test";
//
// 考え方
// * 偽の @minecraft/server（server.js）の中身は globalThis.__nr（= export の S）にある。道具は
//   その中身を直接いじってワールドを作り、イベントを「実機と同じ形」でアドオンへ流す。
// * 道具が偽物の API を自分で呼ぶ間だけ S.harness を上げる（read-only・early のガードを外す）。
//   アドオンのコード（購読者・カスタムコンポーネント）を呼ぶ間は必ず 0 に戻す。
// * tick を進めるのは tick() だけ。フォームの答え・waitTicks・runTimeout は tick を進めないと来ない。
// * 時間・乱数は決まっている（Math.random も偽物の決まった乱数）。同じテストは同じ結果になる。
import fs from "node:fs";
import * as mc from "@minecraft/server";
import * as ui from "@minecraft/server-ui";

export const S = globalThis.__nr;
export { mc, ui };
const REAL = globalThis.__nrReal ?? { setImmediate, setTimeout, clearTimeout };

// ---- scripts/data/*.js（生成物）を読む。無ければ空 ------------------------------------------
export const DATA = {};
const DATA_ERRORS = [];
{
  const dir = new URL("../../scripts/data/", import.meta.url);
  let files = [];
  try { files = fs.readdirSync(dir).filter((f) => f.endsWith(".js")).sort(); } catch { files = []; }
  for (const f of files) {
    try { DATA[f.slice(0, -3)] = await import(new URL(f, dir).href); }
    catch (e) { DATA_ERRORS.push(`scripts/data/${f}: ${e?.message ?? e}`); }
  }
  if (DATA.zombie_shapes && !DATA.shapes) DATA.shapes = DATA.zombie_shapes;
}
export const __dataErrors = DATA_ERRORS;

// ---- 小物 ---------------------------------------------------------------------------------
function asHarness(fn) { S.harness++; try { return fn(); } finally { S.harness--; } }
export async function __drain() { await new Promise((r) => REAL.setImmediate(r)); }
const isEnt = (e) => e instanceof mc.Entity;
function needEnt(e, what) { if (!isEnt(e)) throw new Error(`${what}: Entity でないもの ${S.fmt(e)}`); return e; }
function needLive(e, what) { needEnt(e, what); if (!e._valid) throw new Error(`${what}: もう無いエンティティ ${e._typeId}`); return e; }
function vec(p, what) {
  if (!p || typeof p !== "object" || ![p.x, p.y, p.z].every(Number.isFinite)) throw new Error(`${what}: {x, y, z} でない ${S.fmt(p)}`);
  return { x: p.x, y: p.y, z: p.z };
}
const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
const len = (v) => Math.hypot(v.x, v.y, v.z);
const norm = (v) => { const l = len(v) || 1; return { x: v.x / l, y: v.y / l, z: v.z / l }; };
const PARTS = ["head", "torso", "arm_r", "arm_l", "leg_r", "leg_l"];
export { PARTS };

// ===========================================================================
//  テストの登録と実行
// ===========================================================================
const TESTS = [];
let CUR = null;          // 走っているテスト
let TEST_MARK = null;    // used() の起点
let STUCK = null;

/** テストを登録する。fn は async 可。名前はファイルの中で一意に。 */
export function test(name, fn) {
  if (typeof name !== "string" || !name) throw new Error("test(name, fn): name は文字列");
  if (typeof fn !== "function") throw new Error(`test(${name}): fn が関数でない`);
  if (TESTS.some((t) => t.name === name)) throw new Error(`test: 同じ名前のテストが二つ: ${name}`);
  TESTS.push({ name, fn });
}

class ExpectError extends Error { constructor(m) { super(m); this.name = "ExpectError"; } }

function shortStack(e) {
  const out = [];
  for (const ln of String(e?.stack || "").split("\n").slice(1)) {
    const m = ln.match(/\/((?:scripts|tests)\/[^:)]+):(\d+):\d+\)?\s*$/);
    if (m) out.push(`${m[1]}:${m[2]}`);
    if (out.length >= 4) break;
  }
  return out;
}
function errInfo(e) {
  return { name: e?.name ?? "Error", msg: String(e?.message ?? e), stack: shortStack(e) };
}

function runOne(t) {
  return new Promise((resolve, reject) => {
    let done = false;
    const ms = Number(process.env.NR_TEST_TIMEOUT_MS || 120000);
    const timer = REAL.setTimeout(() => finish(new Error(`テストが ${ms / 1000} 秒で終わらない`)), ms);
    timer.unref?.();
    function finish(err, v) {
      if (done) return;
      done = true; STUCK = null; REAL.clearTimeout(timer);
      if (err) reject(err); else resolve(v);
    }
    STUCK = () => finish(new Error("await が終わらないまま止まった（tick() を進めずにフォームの答え・waitTicks・runTimeout を待っている？）"));
    Promise.resolve().then(t.fn).then((v) => finish(null, v), (e) => finish(e));
  });
}
process.on("beforeExit", () => { if (STUCK) STUCK(); });

/** runner.mjs から呼ぶ。登録されたテストを順に走らせて結果を返す。 */
export async function __runTests({ filter = "", file = "" } = {}) {
  const results = [];
  for (const t of TESTS) {
    if (filter && !(t.name.includes(filter) || file.includes(filter))) continue;
    S.resetWorld();
    CUR = t;
    TEST_MARK = snap();
    const c0 = { v: S.violations.length, e: S.errors.length, c: S.consoleErrors.length, w: S.warns.length, lim: new Map(S.limitations) };
    const t0 = Date.now();
    let error = null;
    try { await runOne(t); await __drain(); }
    catch (e) { error = errInfo(e); }
    // このテストの分は記録から外す（残るのは「テストの外」で起きたものだけ）
    const violations = S.violations.splice(c0.v);
    const errors = S.errors.splice(c0.e);
    const consoleErrors = S.consoleErrors.splice(c0.c);
    const limitations = {};
    for (const [k, n] of S.limitations) { const d = n - (c0.lim.get(k) ?? 0); if (d) limitations[k] = d; }
    results.push({ name: t.name, ok: !error && !violations.length && !errors.length && !consoleErrors.length,
      ms: Date.now() - t0, error, violations, errors, consoleErrors, warns: S.warns.length - c0.w, limitations, ticks: S.tick });
    CUR = null;
  }
  return results;
}
export function __testNames() { return TESTS.map((t) => t.name); }

// ===========================================================================
//  時間
// ===========================================================================
/** n tick 進める（物理・効果・タイマー・runJob・after イベント・Promise）。必ず await する。 */
export async function tick(n = 1) {
  if (!Number.isInteger(n) || n < 0 || n > 2000000) throw new Error(`tick(${n}): 0 以上の整数`);
  for (let i = 0; i < n; i++) { S.__tick(); await __drain(); }
}
/** 時刻（0〜23999）。13000〜22999 が夜。 */
export function setTime(t) {
  if (!Number.isInteger(t) || t < 0 || t > 23999) throw new Error(`setTime(${t}): 0〜23999 の整数`);
  S.time = t;
}
/** 光の強さを固定する（数 / (location) => 数 / null で既定＝時刻と空と光るブロックから）。 */
export function setLight(v) {
  if (!(v === null || typeof v === "function" || (Number.isInteger(v) && v >= 0 && v <= 15))) throw new Error(`setLight(${S.fmt(v)}): 0〜15 / 関数 / null`);
  S.light = v;
}

// ===========================================================================
//  地形
// ===========================================================================
function floorPos(p) { const v = vec(p, "位置"); return { x: Math.floor(v.x), y: Math.floor(v.y), z: Math.floor(v.z) }; }
/** ブロックを置く（イベントもカスタムコンポーネントも呼ばない。地形づくり用）。 */
export function setBlock(pos, id, states) {
  const p = floorPos(pos);
  asHarness(() => {
    const n = S.checkBlockId(id, "setBlock");
    S.setBlockAt(p.x, p.y, p.z, n, states ?? mc.BlockPermutation.resolve(n).getAllStates());
  });
}
/** 直方体を埋める（両端を含む）。 */
export function fill(from, to, id) {
  const a = floorPos(from), b = floorPos(to);
  const n = (Math.abs(b.x - a.x) + 1) * (Math.abs(b.y - a.y) + 1) * (Math.abs(b.z - a.z) + 1);
  if (n > 2000000) throw new Error(`fill: ${n} ブロックは多すぎる`);
  asHarness(() => {
    const t = S.checkBlockId(id, "fill");
    const st = mc.BlockPermutation.resolve(t).getAllStates();
    for (let x = Math.min(a.x, b.x); x <= Math.max(a.x, b.x); x++)
      for (let y = Math.min(a.y, b.y); y <= Math.max(a.y, b.y); y++)
        for (let z = Math.min(a.z, b.z); z <= Math.max(a.z, b.z); z++) S.setBlockAt(x, y, z, t, st);
  });
}
/** その場所のブロックに random tick を一回入れる（カスタムコンポーネントの onRandomTick。偽物は自分では
 *  random tick を起こさない）。フックが呼ばれたら true。 */
export async function randomTick(pos) {
  const p = floorPos(pos);
  const any = S.blockHook(p, "onRandomTick", {});
  S.flush(); await __drain();
  return any;
}
/** その場所のブロックの ID。 */
export function blockAt(pos) { const p = floorPos(pos); return S.blockAt(p.x, p.y, p.z).typeId; }
/** 平らな地面の高さ（y 未満が石・草。y 自身は空気）。null で地面なし（奈落）。 */
export function setGround(y) {
  if (y === null || y === false) { S.flat = false; return; }
  if (!Number.isInteger(y)) throw new Error(`setGround(${y}): 整数か null`);
  S.flat = true; S.groundY = y;
}

// ===========================================================================
//  エンティティ
// ===========================================================================
function nearestPlayer(pos) {
  let best = null, bd = Infinity;
  for (const p of S.players) { if (!p._valid) continue; const d = len(sub(p._loc, pos)); if (d < bd) { bd = d; best = p; } }
  return best;
}
function zid(type) {
  if (typeof type !== "string" || !type) throw new Error(`spawnZombie: 種類 ${S.fmt(type)}`);
  return type.includes(":") ? type : `nr:z_${type}`;
}
function faceTo(e, target) {
  const head = e.getHeadLocation ? asHarness(() => e.getHeadLocation()) : e._loc;
  const to = isEnt(target) ? asHarness(() => target.getHeadLocation()) : vec(target, "face");
  const r = S.rotToward(head, to);
  e._rot = { x: e._isPlayer ? Math.max(-90, Math.min(90, r.x)) : 0, y: r.y };
}
/** 何でも出す（dimension.spawnEntity 経由。entitySpawn も来る）。opts: {yaw, face, event}。 */
export function spawn(id, pos = { x: 0, y: 64, z: 2 }, o = {}) {
  const at = vec(pos, `spawn(${id})`);
  const e = asHarness(() => S.overworld.spawnEntity(id, at, o.event ? { spawnEvent: o.event } : undefined));
  if (o.yaw !== undefined) e._rot.y = o.yaw;
  else if (o.face) faceTo(e, o.face);
  S.flush();
  return e;
}
/** ゾンビを出す。type は spec の鍵（"office_worker"）か ID。既定で一番近いプレイヤーの方を向く。 */
export function spawnZombie(type, pos = { x: 0, y: 64, z: 2 }, o = {}) {
  const at = vec(pos, "spawnZombie");
  const e = asHarness(() => S.overworld.spawnEntity(zid(type), at, o.event ? { spawnEvent: o.event } : undefined));
  if (o.yaw !== undefined) e._rot.y = o.yaw;
  else { const t = o.face ?? nearestPlayer(at); if (t) faceTo(e, t); }
  S.flush();
  return e;
}
let playerN = 0;
/** プレイヤーを出す（playerJoin / playerSpawn が来る）。item は ID か ItemStack（0 番のスロット＝手）。 */
export function spawnPlayer(pos = { x: 0, y: 64, z: 0 }, item, o = {}) {
  const at = vec(pos, "spawnPlayer");
  const name = o.name ?? (S.players.length ? `Runner${++playerN}` : "Runner");
  const p = asHarness(() => S.createPlayer(name, at));
  if (o.mode) { asHarness(() => p.setGameMode(o.mode)); }
  if (o.yaw !== undefined) p._rot.y = o.yaw;
  if (item !== undefined) give(p, item, 0);
  S.flush();
  return p;
}
/** 持ち物に入れる（既定は今選んでいるスロット）。入れた ItemStack を返す。 */
export function give(player, item, slot) {
  needLive(player, "give");
  if (!player._isPlayer) throw new Error("give: プレイヤーでない");
  const it = typeof item === "string" ? asHarness(() => new mc.ItemStack(item)) : item;
  if (!(it instanceof mc.ItemStack)) throw new Error(`give: ID か ItemStack: ${S.fmt(item)}`);
  const i = slot ?? player._slot;
  asHarness(() => player._inv.setItem(i, it));
  return player._inv._slots[i];
}
/** 手に持っている ItemStack（の写し）。 */
export function held(player) { needEnt(player, "held"); return asHarness(() => player._inv.getItem(player._slot)); }
/** 消す（イベントなし。後片付け用）。 */
export function despawn(e) { needEnt(e, "despawn"); e._removeNow(true); }
/** プレイヤーが抜ける（beforeEvents.playerLeave → 無効になる → afterEvents.playerLeave）。開いているフォームは
 *  次の tick に FormRejectError（PlayerQuit）で reject される。 */
export async function leave(player) {
  needLive(player, "leave");
  if (!player._isPlayer) throw new Error("leave: プレイヤーでない");
  S.fireBefore("playerLeave", { player });
  const id = player._id, name = player._name;
  player._valid = false;
  S.entities.delete(id);
  S.players.splice(S.players.indexOf(player), 1);
  S.queueAfter("playerLeave", { playerId: id, playerName: name });
  S.flush(); await __drain();
}

/** エンティティのプロパティ（"nr:" は省略可）。書いた最新の値（実機で次の tick にクライアントへ届く値）を返す。
 *  アドオンの getProperty は d.ts のとおり setProperty の次の tick まで古い値を返す（server:L7592）。 */
export function prop(e, name) {
  needEnt(e, "prop");
  const n = name.includes(":") ? name : `nr:${name}`;
  if (!e._props.has(n)) throw new Error(`prop: ${e._typeId} に ${n} は無い（BP の description.properties）`);
  return e._latestProp(n);
}
/** 今いるエンティティ（プレイヤー以外）。type は ID か鍵、省略で全部。 */
export function entities(type) {
  const id = type === undefined ? undefined : (type.includes(":") ? type : `nr:z_${type}`);
  return [...S.entities.values()].filter((e) => e._valid && !e._isPlayer && (id === undefined || e._typeId === id));
}
/** BP にある全ゾンビの ID（scripts/data/zombies.js があれば ztype の順）。 */
export function zombieTypes() {
  const ids = Object.keys(S.DEFS.entities).filter((x) => x.startsWith("nr:z_"));
  const order = (DATA.zombies?.ZOMBIES ?? []).map((z) => z.id ?? `nr:z_${z.key}`);
  return order.filter((x) => ids.includes(x)).concat(ids.filter((x) => !order.includes(x)).sort());
}

// ===========================================================================
//  部位と狙い
// ===========================================================================
// SHAPES が無いときの人型の目安（単位ブロック、r = 右、u = 上、f = 前）
function fallbackBox(e, pose, part) {
  const h = e._size().h;
  const T = {
    stand: { head: [0, 0.9 * h, 0], torso: [0, 0.62 * h, 0], arm_r: [0.32, 0.64 * h, 0], arm_l: [-0.32, 0.64 * h, 0], leg_r: [0.12, 0.25 * h, 0], leg_l: [-0.12, 0.25 * h, 0] },
    lie: { head: [0, 0.15, -0.8 * h / 1.8], torso: [0, 0.18, -0.25], arm_r: [0.32, 0.15, -0.4], arm_l: [-0.32, 0.15, -0.4], leg_r: [0.12, 0.12, 0.5], leg_l: [-0.12, 0.12, 0.5] },
    prone: { head: [0, 0.3, 0.8], torso: [0, 0.3, 0.3], arm_r: [0.32, 0.25, 0.6], arm_l: [-0.32, 0.25, 0.6], leg_r: [0.12, 0.12, -0.5], leg_l: [-0.12, 0.12, -0.5] },
  };
  return T[pose][part];
}
/** 部位の世界座標（scripts/data/zombie_shapes.js の当たり箱の中心）。part は head / torso / arm_r … 。
 *  "arm_r:1" で 2 つめの箱（前腕）。nr:state が crawl なら prone（無ければ lie）、down / dead なら lie。 */
export function partPoint(e, part = "torso") {
  needLive(e, "partPoint");
  const [name, idxS] = String(part).split(":");
  if (!PARTS.includes(name)) throw new Error(`partPoint: 部位 ${part}（${PARTS.join(" / ")}）`);
  const idx = idxS === undefined ? 0 : Number(idxS);
  const key = e._typeId.startsWith("nr:z_") ? e._typeId.slice(5) : e._typeId.replace(/^.*:/, "");
  const shape = DATA.shapes?.SHAPES?.[key];
  const st = e._latestProp("nr:state");
  const pose = st === "crawl" ? "prone" : (st === "down" || st === "dead") ? "lie" : "stand";
  const boxes = shape?.[pose]?.[name] ?? (pose === "prone" ? shape?.lie?.[name] : undefined);
  const c = boxes?.length ? (boxes[idx] ?? boxes[0]).c : fallbackBox(e, shape?.[pose] ? pose : (pose === "prone" ? "prone" : pose), name);
  const yaw = e._rot.y * Math.PI / 180;
  const F = { x: -Math.sin(yaw), z: Math.cos(yaw) }, R = { x: -Math.cos(yaw), z: -Math.sin(yaw) };
  const L = e._loc;
  return { x: L.x + R.x * c[0] + F.x * c[2], y: L.y + c[1], z: L.z + R.z * c[0] + F.z * c[2] };
}
/** プレイヤーの視線を点（か相手）へ向ける。 */
export function aim(player, point) {
  needLive(player, "aim");
  faceTo(player, isEnt(point) ? point : vec(point, "aim"));
}

// ===========================================================================
//  戦う
// ===========================================================================
function itemDamage(item) {
  const c = item && S.DEFS.items[item.typeId]?.components?.["minecraft:damage"];
  return typeof c === "number" ? c : (c && typeof c === "object" ? c.value : undefined);
}
function useDurationTicks(item) {
  const um = item && S.DEFS.items[item.typeId]?.components?.["minecraft:use_modifiers"];
  return um?.use_duration !== undefined ? Math.round(um.use_duration * 20) : 72000;
}
function wearHeld(p, it, ev) {
  const dc = it?.getComponent?.("minecraft:durability");
  if (!dc) return;
  const e = { ...ev, itemStack: it, durabilityDamage: 1 };
  S.itemHook(it, "onBeforeDurabilityDamage", e);
  const cur = p._inv._slots[p._slot];
  if (!cur || cur.typeId !== it.typeId || !Number.isInteger(e.durabilityDamage) || e.durabilityDamage <= 0) return;
  const max = asHarness(() => dc.maxDurability);
  cur._dmg += e.durabilityDamage;
  if (cur._dmg > max) p._inv._slots[p._slot] = undefined;   // 壊れた
}
/** 近接で殴る。部位を狙って視線を合わせ、onHitEntity → entityHitEntity → entityHurt の順に流す。
 *  opts: {part, point, damage（既定は武器の minecraft:damage か 1）, cause（既定 entityAttack）}。
 *  同じ相手を 10 tick 以内に続けて殴ると、実機と同じく小さい一撃は無視される（無敵時間）。 */
export async function hit(player, target, o = {}) {
  needLive(player, "hit"); needLive(target, "hit");
  const point = o.point ? vec(o.point, "hit の point") : partPoint(target, o.part ?? "torso");
  aim(player, point);
  const it = held(player);
  if (it) S.itemHook(it, "onHitEntity", { attackingEntity: player, hitEntity: target, hadEffect: false, itemStack: it });
  S.queueAfter("entityHitEntity", { damagingEntity: player, hitEntity: target });
  const dmg = o.damage ?? itemDamage(it) ?? 1;
  const hurt = target._hurt(dmg, { cause: o.cause ?? "entityAttack", damagingEntity: player });
  if (it) wearHeld(player, it, { attackingEntity: player, hitEntity: target });
  S.flush();
  await __drain();
  return { hurt, point };
}
/** 飛び道具が当たる（projectileHitEntity → entityHurt）。弾は当たった所に出す。
 *  opts: {part, point, projectile（既定 minecraft:arrow）, damage（既定 5）}。 */
export async function shoot(player, target, o = {}) {
  needLive(player, "shoot"); needLive(target, "shoot");
  const point = o.point ? vec(o.point, "shoot の point") : partPoint(target, o.part ?? "torso");
  aim(player, point);
  const head = asHarness(() => player.getHeadLocation());
  const dir = norm(sub(point, head));
  const proj = asHarness(() => S.overworld.spawnEntity(o.projectile ?? "minecraft:arrow", point));
  proj._owner = player; proj._stuck = true; proj._vel = { x: 0, y: 0, z: 0 };
  S.queueAfter("projectileHitEntity", { dimension: S.overworld, hitVector: dir, location: point, projectile: proj,
    source: player, getEntityHit: () => ({ entity: target._valid ? target : undefined }) });
  const hurt = target._hurt(o.damage ?? 5, { cause: "projectile", damagingEntity: player, damagingProjectile: proj });
  S.flush();
  await __drain();
  return { hurt, point, projectile: proj };
}

// ===========================================================================
//  アイテムを使う
// ===========================================================================
function heldOrGive(player, item, what) {
  needLive(player, what);
  if (item !== undefined) give(player, item);
  const it = held(player);
  if (!it) throw new Error(`${what}: 手に何も持っていない`);
  return it;
}
/** 使う（beforeEvents.itemUse → カスタムコンポーネントの onUse → afterEvents.itemUse）。取り消されたら false。 */
export async function use(player, item) {
  const it = heldOrGive(player, item, "use");
  const be = S.fireBefore("itemUse", { itemStack: it, source: player, cancel: false });
  if (!be.cancel) {
    S.itemHook(it, "onUse", { itemStack: it, source: player });
    S.queueAfter("itemUse", { itemStack: it, source: player });
  }
  S.flush(); await __drain();
  return !be.cancel;
}
/** 使い始める（itemStartUse。useDuration は使用時間の tick）。 */
export async function startUse(player, item) {
  const it = heldOrGive(player, item, "startUse");
  S.queueAfter("itemStartUse", { itemStack: it, source: player, useDuration: useDurationTicks(it) });
  S.flush(); await __drain();
}
/** 使うのをやめる（itemStopUse。ticks = 使っていた長さ。useDuration は残り）。 */
export async function stopUse(player, item, ticks = 0) {
  const it = heldOrGive(player, item, "stopUse");
  S.queueAfter("itemStopUse", { itemStack: it, source: player, useDuration: Math.max(0, useDurationTicks(it) - ticks) });
  S.flush(); await __drain();
}
/** 離して放つ（弓など。itemReleaseUse。ticks = 溜めた長さ）。 */
export async function releaseUse(player, item, ticks = 20) {
  const it = heldOrGive(player, item, "releaseUse");
  S.queueAfter("itemReleaseUse", { itemStack: it, source: player, useDuration: Math.max(0, useDurationTicks(it) - ticks) });
  S.flush(); await __drain();
}
/** 使い終わる（onCompleteUse・食べ物なら onConsume → itemCompleteUse）。 */
export async function completeUse(player, item) {
  const it = heldOrGive(player, item, "completeUse");
  S.itemHook(it, "onCompleteUse", { itemStack: it, source: player });
  if (S.DEFS.items[it.typeId]?.components?.["minecraft:food"]) S.itemHook(it, "onConsume", { itemStack: it, source: player });
  S.queueAfter("itemCompleteUse", { itemStack: it, source: player, useDuration: 0 });
  S.flush(); await __drain();
}

// ===========================================================================
//  入力
// ===========================================================================
/** ボタン（"Jump" / "Sneak"）を押す・離す（playerButtonInput）。Jump は地面にいれば跳ぶ。 */
export async function press(player, button, down = true) {
  needLive(player, "press");
  if (button !== "Jump" && button !== "Sneak") throw new Error(`press: ボタンは Jump / Sneak だけ（${button}）`);
  const st = down ? "Pressed" : "Released";
  if (player._buttons[button] !== st) {
    player._buttons[button] = st;
    S.queueAfter("playerButtonInput", { button, newButtonState: st, player });
  }
  if (button === "Sneak") player._sneaking = !!down;
  if (button === "Jump") {
    player._jumping = !!down;
    if (down && player._onGround) { player._vel.y = 0.42; player._onGround = false; }
  }
  S.flush(); await __drain();
}
/** 移動の入力。x = 右(+)/左(-)、y = 前(+)/後(-)（偽物の約束。実機の符号は要確認）、sprint / sneak / jump。
 *  移動は tick ごとに偽物がプレイヤーを動かす（歩き 0.215、走り 0.28、しゃがみ 0.065 ブロック/tick）。 */
export async function setInput(player, o = {}) {
  needLive(player, "setInput");
  const cl = (v) => Math.max(-1, Math.min(1, Number(v) || 0));
  if ("x" in o || "y" in o) player._move = { x: cl(o.x ?? player._move.x), y: cl(o.y ?? player._move.y) };
  if ("sprint" in o) player._sprinting = !!o.sprint;
  if ("sneak" in o) await press(player, "Sneak", !!o.sneak);
  if ("jump" in o) await press(player, "Jump", !!o.jump);
  S.flush(); await __drain();
}

// ===========================================================================
//  触る・壊す・置く
// ===========================================================================
/** エンティティかブロック（位置）に「使う」（playerInteractWith*。ブロックなら onPlayerInteract / onUseOn）。 */
export async function interact(player, target) {
  needLive(player, "interact");
  const it = held(player);
  if (isEnt(target)) {
    needLive(target, "interact");
    const be = S.fireBefore("playerInteractWithEntity", { player, target, itemStack: it, cancel: false });
    if (!be.cancel) S.queueAfter("playerInteractWithEntity", { player, target, itemStack: held(player), beforeItemStack: it });
    S.flush(); await __drain();
    return !be.cancel;
  }
  const p = floorPos(target);
  const block = asHarness(() => S.overworld.getBlock(p));
  const face = "Up", faceLocation = { x: 0.5, y: 1, z: 0.5 };
  const be = S.fireBefore("playerInteractWithBlock", { player, block, blockFace: face, faceLocation, isFirstEvent: true, itemStack: it, cancel: false });
  if (!be.cancel) {
    S.blockHook(p, "onPlayerInteract", { player, face, faceLocation });
    if (it) S.itemHook(it, "onUseOn", { source: player, itemStack: it, block, blockFace: face, faceLocation, usedOnBlockPermutation: asHarness(() => block.permutation) });
    S.queueAfter("playerInteractWithBlock", { player, block, blockFace: face, faceLocation, isFirstEvent: true, itemStack: held(player), beforeItemStack: it });
  }
  S.flush(); await __drain();
  return !be.cancel;
}
/** プレイヤーがブロックを壊す（before → onPlayerBreak → after playerBreakBlock → 道具の onMineBlock）。 */
export async function breakBlock(player, pos) {
  needLive(player, "breakBlock");
  const p = floorPos(pos);
  const block = asHarness(() => S.overworld.getBlock(p));
  const it = held(player);
  const be = S.fireBefore("playerBreakBlock", { player, block, dimension: S.overworld, itemStack: it, cancel: false });
  if (be.cancel) { S.flush(); await __drain(); return false; }
  const perm = asHarness(() => block.permutation);
  const was = perm.type.id;
  asHarness(() => S.setBlockAt(p.x, p.y, p.z, "minecraft:air"));
  S.blockHookFor(was, p, "onPlayerBreak", { brokenBlockPermutation: perm, player });
  S.queueAfter("playerBreakBlock", { player, block, dimension: S.overworld, brokenBlockPermutation: perm, itemStackBeforeBreak: it, itemStackAfterBreak: held(player) });
  if (it) S.itemHook(it, "onMineBlock", { source: player, itemStack: it, block, minedBlockPermutation: perm });
  S.flush(); await __drain();
  return true;
}
/** プレイヤーがブロックを置く（beforeOnPlayerPlace → onPlace → after playerPlaceBlock）。 */
export async function placeBlock(player, pos, id) {
  needLive(player, "placeBlock");
  const p = floorPos(pos);
  const perm = asHarness(() => mc.BlockPermutation.resolve(id));
  const block = asHarness(() => S.overworld.getBlock(p));
  const prev = asHarness(() => block.permutation);
  const ev = { block, dimension: S.overworld, face: "Up", permutationToPlace: perm, player, cancel: false };
  S.blockHookFor(perm.type.id, p, "beforeOnPlayerPlace", ev);
  if (ev.cancel) { S.flush(); await __drain(); return false; }
  asHarness(() => S.setBlockAt(p.x, p.y, p.z, ev.permutationToPlace.type.id, ev.permutationToPlace.getAllStates()));
  S.blockHookFor(ev.permutationToPlace.type.id, p, "onPlace", { previousBlock: prev });
  S.queueAfter("playerPlaceBlock", { player, block, dimension: S.overworld });
  S.flush(); await __drain();
  return true;
}

// ===========================================================================
//  コマンド
// ===========================================================================
/** `/scriptevent id message`（source を渡すとそのエンティティから）。 */
export async function scriptEvent(id, message = "", source) {
  if (typeof id !== "string" || !/^[a-z0-9_.-]+:[\w.-]+$/i.test(id) || id.startsWith("minecraft:")) throw new Error(`scriptEvent: ID ${S.fmt(id)}（"ns:name"）`);
  S.queueAfter("scriptEventReceive", { id, message: String(message), sourceEntity: source, initiator: undefined, sourceBlock: undefined,
    sourceType: source ? "Entity" : "Server" });
  S.flush(); await __drain();
}
/** startup で登録されたカスタムコマンドを打つ（コールバックは read-only で呼ばれる）。結果を返す。 */
export async function command(name, args = [], source) {
  const c = S.reg.commands.get(name);
  if (!c) throw new Error(`command: 登録されていないコマンド ${name}（登録済み: ${[...S.reg.commands.keys()].join(", ") || "なし"}）`);
  let res;
  S.readOnly++;
  try { res = c.cb({ sourceEntity: source, initiator: undefined, sourceBlock: undefined, sourceType: source ? "Entity" : "Server" }, ...args); }
  catch (e) { S.recordError(`custom command ${name}`, e); }
  finally { S.readOnly--; }
  S.flush(); await __drain();
  return res;
}

// ===========================================================================
//  フォーム
// ===========================================================================
/** 次に開くフォームの答えを積む。番号（ActionForm / MessageForm のボタン）・配列（ModalForm の入力の値）・
 *  "defaults"（ModalForm を既定値のまま送る）・{canceled: true, reason: "UserBusy"}・{reject: "PlayerQuit"}・
 *  (form) => 答え。積まれていないフォームは「閉じた」扱い。 */
export function answerForm(resp) { S.formQueue.push(resp); }
/** 最後に開いたフォーム {type, title, body, buttons, controls, inputs, answer, ...}。 */
export function lastForm() { return S.forms[S.forms.length - 1]; }

// ===========================================================================
//  使った演出の回数
// ===========================================================================
function counts(m) {
  return new Proxy(m, { get: (t, k) => (typeof k === "string" && !(k in t) && k !== "toJSON" && k !== "then" ? 0 : t[k]) });
}
function snap() {
  const o = {};
  for (const [k, v] of Object.entries(S.log)) {
    if (v instanceof Map) o[k] = Object.fromEntries(v);
    else if (Array.isArray(v)) o[k] = v.slice();
    else o[k] = v;
  }
  return o;
}
function diff(a, b) {
  const o = {};
  for (const [k, v] of Object.entries(b)) {
    if (typeof v === "number") o[k] = v - (a?.[k] ?? 0);
    else if (Array.isArray(v)) o[k] = v.slice((a?.[k] ?? []).length);
    else {
      const m = {};
      for (const [kk, n] of Object.entries(v)) { const d = n - (a?.[k]?.[kk] ?? 0); if (d) m[kk] = d; }
      o[k] = counts(m);
    }
  }
  return o;
}
/** このテストが始まってから使った演出: {particles, sounds, anims, events, props, spawned, structures, effects,
 *  molangVars（"パーティクル 変数" ごと）, commands, messages, hurts, deaths, camera, titles, actionbars, removed}。
 *  無い ID は 0。 */
export function used() { return diff(TEST_MARK, snap()); }
/** 今の回数を覚える（since(mark) で差を取る）。 */
export function mark() { return snap(); }
export function since(m) { return diff(m, snap()); }
/** このテストで 1 tick に出たパーティクルの最大（ファイル全体は S.maxPerTick）。 */
export function particlePeak() { return S.maxPerTick; }

// ===========================================================================
//  expect
// ===========================================================================
function show(v) {
  if (typeof v === "string") return JSON.stringify(v);
  if (typeof v === "function") return `[関数 ${v.name || "?"}]`;
  try { const s = S.fmt(v); return s && s.length > 160 ? s.slice(0, 157) + "..." : s; } catch { return String(v); }
}
function deepEq(a, b) {
  if (Object.is(a, b)) return true;
  if (typeof a !== "object" || typeof b !== "object" || !a || !b) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const ka = Object.keys(a), kb = Object.keys(b);
  if (ka.length !== kb.length) return false;
  return ka.every((k) => Object.prototype.hasOwnProperty.call(b, k) && deepEq(a[k], b[k]));
}
function matchErr(e, pat) {
  if (pat === undefined) return true;
  const msg = String(e?.message ?? e);
  if (pat instanceof RegExp) return pat.test(msg);
  if (typeof pat === "string") return msg.includes(pat);
  if (typeof pat === "function") return e instanceof pat;
  return false;
}
/** expect(実際の値).toBe(期待) など。.not で反対。 */
export function expect(actual) {
  const make = (neg) => {
    const ok = (cond, msg) => { if (!!cond === neg) throw new ExpectError(`${neg ? "[not] " : ""}${msg}`); };
    const a = show(actual);
    return {
      toBe: (x) => ok(Object.is(actual, x), `expect(${a}).toBe(${show(x)})`),
      toEqual: (x) => ok(deepEq(actual, x), `expect(${a}).toEqual(${show(x)})`),
      toBeTruthy: () => ok(!!actual, `expect(${a}).toBeTruthy()`),
      toBeFalsy: () => ok(!actual, `expect(${a}).toBeFalsy()`),
      toBeDefined: () => ok(actual !== undefined, `expect(${a}).toBeDefined()`),
      toBeUndefined: () => ok(actual === undefined, `expect(${a}).toBeUndefined()`),
      toBeNull: () => ok(actual === null, `expect(${a}).toBeNull()`),
      toBeGreaterThan: (n) => ok(typeof actual === "number" && actual > n, `expect(${a}).toBeGreaterThan(${n})`),
      toBeGreaterThanOrEqual: (n) => ok(typeof actual === "number" && actual >= n, `expect(${a}).toBeGreaterThanOrEqual(${n})`),
      toBeLessThan: (n) => ok(typeof actual === "number" && actual < n, `expect(${a}).toBeLessThan(${n})`),
      toBeLessThanOrEqual: (n) => ok(typeof actual === "number" && actual <= n, `expect(${a}).toBeLessThanOrEqual(${n})`),
      toBeCloseTo: (n, digits = 2) => ok(typeof actual === "number" && Math.abs(actual - n) < Math.pow(10, -digits) / 2, `expect(${a}).toBeCloseTo(${n}, ${digits})`),
      toContain: (x) => ok(typeof actual === "string" ? actual.includes(x) : [...(actual ?? [])].some((y) => deepEq(y, x)), `expect(${a}).toContain(${show(x)})`),
      toBeOneOf: (list) => ok(Array.isArray(list) && list.some((y) => deepEq(actual, y)), `expect(${a}).toBeOneOf(${show(list)})`),
      toHaveLength: (n) => ok(actual != null && actual.length === n, `expect(${a}).toHaveLength(${n})（長さ ${actual?.length}）`),
      toMatch: (re) => ok(typeof actual === "string" && (re instanceof RegExp ? re.test(actual) : actual.includes(re)), `expect(${a}).toMatch(${re})`),
      toBeInstanceOf: (C) => ok(actual instanceof C, `expect(${a}).toBeInstanceOf(${C?.name})`),
      toThrow: (pat) => {
        if (typeof actual !== "function") throw new ExpectError("toThrow は関数を expect に渡す（同期の関数だけ）");
        let threw = false, err;
        try { actual(); } catch (e) { threw = true; err = e; }
        ok(threw && matchErr(err, pat), `expect(fn).toThrow(${pat === undefined ? "" : show(pat)})${threw ? `（投げたのは: ${err?.message ?? err}）` : "（投げなかった）"}`);
      },
    };
  };
  const o = make(false);
  o.not = make(true);
  return o;
}

/** わざと契約違反を起こすテスト用: fn の中で kind の違反が起きたことを確かめ、記録から消す（必ず await）。
 *  違反で投げられた例外は飲み込む。起きた違反の配列を返す。 */
export async function expectViolation(fn, kind) {
  const v0 = S.violations.length, e0 = S.errors.length;
  let thrown;
  try { await fn(); } catch (e) { thrown = e; }
  const got = S.violations.slice(v0);
  const hit = got.filter((v) => !kind || v.kind === kind);
  if (!hit.length) {
    throw new ExpectError(`expectViolation: 違反${kind ? ` "${kind}"` : ""} が起きなかった（起きた違反: ${got.map((v) => v.kind).join(", ") || "なし"}${thrown ? `、例外: ${thrown.message}` : ""}）`);
  }
  const rest = got.filter((v) => !hit.includes(v));
  S.violations.splice(v0, got.length, ...rest);
  // 違反の例外が購読者の中で投げられて「捕まらない例外」になった分も消す
  const tags = new Set(hit.map((v) => `[fake:${v.kind}]`));
  const errs = S.errors.slice(e0).filter((e) => ![...tags].some((t) => String(e.msg).startsWith(t)));
  S.errors.splice(e0, S.errors.length - e0, ...errs);
  if (thrown && !String(thrown.message).startsWith("[fake:")) throw thrown;
  return hit;
}
