// ===========================================================================
//  アストロ・ナノギア — 共通ユーティリティ
//  API の版差（1.x / 2.x）を吸収する薄いラッパ、ベクトル計算、インベントリと装備の操作、
//  例外の報告（同じものは一度だけ console.warn）、モジュール間の小さなイベントバス。
//  （hyperdim の util.js を土台にしている）
// ===========================================================================
import { world, system } from "@minecraft/server";

export const now = () => system.currentTick;
export const TICKS = 20;

// ---------------------------------------------------------------------------
//  報告: 例外や異常を "[astro] 場所: 内容" で一度だけ出す
// ---------------------------------------------------------------------------
const seen = new Set();
/** 同じ場所・同じ内容の警告は一度だけ出す。 */
export function report(where, err) {
  const msg = err?.message ?? String(err);
  const key = `${where}:${msg}`;
  if (seen.has(key)) return;
  if (seen.size > 400) seen.clear();
  seen.add(key);
  console.warn(`[astro] ${where}: ${err?.stack ?? msg}`);
}

/** fn を try/catch で包む（イベントハンドラ・ループ用）。 */
export function guard(where, fn) {
  return (...a) => {
    try { return fn(...a); } catch (e) { report(where, e); return undefined; }
  };
}

// ---------------------------------------------------------------------------
//  モジュール間のイベントバス（循環 import を避けるため）
//   "hit"(p, target, dmg, ctx) / "kill"(p, victim) / "hurt"(p, attacker, dmg)
//   "revert"(p, reason) / "transformed"(p, key) / "reverted"(p, key, reason)
// ---------------------------------------------------------------------------
const listeners = new Map();
export const BUS = {
  on(name, fn) {
    if (!listeners.has(name)) listeners.set(name, []);
    listeners.get(name).push(fn);
  },
  emit(name, ...args) {
    const list = listeners.get(name);
    if (!list) return;
    for (const fn of list) {
      try { fn(...args); } catch (e) { report(`bus.${name}`, e); }
    }
  },
};

// ---------------------------------------------------------------------------
//  エンティティ
// ---------------------------------------------------------------------------
/** isValid は 1.x では関数、2.x ではプロパティ。 */
export function valid(e) {
  if (!e) return false;
  try {
    const v = e.isValid;
    return typeof v === "function" ? v.call(e) : v !== false;
  } catch (_) { return false; }
}

export function health(entity) {
  try { return entity.getComponent("minecraft:health"); } catch (_) { return undefined; }
}

/** 生きている（有効で HP が 0 より大きい）。 */
export function alive(e) {
  if (!valid(e)) return false;
  const h = health(e);
  try { return !h || h.currentValue > 0; } catch (_) { return false; }
}

export function isPlayer(e) {
  try { return e?.typeId === "minecraft:player"; } catch (_) { return false; }
}

export function allPlayers() {
  try { return world.getAllPlayers(); } catch (_) { return []; }
}

export function playerById(id) {
  for (const p of allPlayers()) if (p.id === id) return p;
  return undefined;
}

/** 同期コマンド（無ければ非同期版）。失敗しても例外は外に出さない。成功で true。 */
export function cmd(source, command) {
  try {
    if (typeof source.runCommand === "function") { source.runCommand(command); return true; }
  } catch (_) { return false; }
  try { source.runCommandAsync?.(command)?.catch?.(() => { }); return true; } catch (_) { return false; }
}

/** applyKnockback は 1.x (dx, dz, 水平, 垂直) と 2.x ({x,z}*強さ, 垂直) で引数が違う。 */
export function knock(entity, dx, dz, horizontal, vertical) {
  if (![dx, dz, horizontal, vertical].every(Number.isFinite)) return;
  try {
    entity.applyKnockback(dx, dz, horizontal, vertical);
    return;
  } catch (_) { /* 2.x */ }
  try { entity.applyKnockback({ x: dx * horizontal, z: dz * horizontal }, vertical); } catch (_) { }
}

/** 効果を付ける（amp は 0 始まり）。 */
export function effect(entity, id, ticks, amp = 0, particles = false) {
  if (!Number.isFinite(ticks) || ticks <= 0) return;
  try { entity.addEffect(id, Math.max(1, Math.round(ticks)), { amplifier: Math.max(0, Math.round(amp)), showParticles: particles }); }
  catch (_) { }
}

export function removeEffect(entity, id) {
  try { entity.removeEffect(id); } catch (_) { }
}

export function getEffect(entity, id) {
  try { return entity.getEffect?.(id); } catch (_) { return undefined; }
}

export function heal(entity, amount) {
  const h = health(entity);
  if (!h) return;
  try {
    if (h.currentValue > 0) h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + amount));
  } catch (_) { }
}

export function velocity(e) {
  try { return e.getVelocity(); } catch (_) { return { x: 0, y: 0, z: 0 }; }
}

export function gameMode(p) {
  try { return String(p.getGameMode?.() ?? "").toLowerCase(); } catch (_) { return ""; }
}

// ---------------------------------------------------------------------------
//  動的プロパティ
// ---------------------------------------------------------------------------
export function getProp(holder, key, fallback) {
  try {
    const v = holder.getDynamicProperty(key);
    return v === undefined ? fallback : v;
  } catch (_) { return fallback; }
}

export function numProp(holder, key, fallback = 0) {
  const v = getProp(holder, key, undefined);
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

export function setProp(holder, key, v) {
  try { holder.setDynamicProperty(key, v); } catch (_) { }
}

export function jsonProp(holder, key, fallback) {
  const v = getProp(holder, key, undefined);
  if (typeof v !== "string" || !v) return fallback;
  try { return JSON.parse(v); } catch (_) { return fallback; }
}

export function setJsonProp(holder, key, v) {
  setProp(holder, key, v === undefined || v === null ? undefined : JSON.stringify(v));
}

// ---------------------------------------------------------------------------
//  インベントリと装備
// ---------------------------------------------------------------------------
export const ARMOR_SLOTS = ["Head", "Chest", "Legs", "Feet"];

export function container(p) {
  try { return p.getComponent("minecraft:inventory")?.container; } catch (_) { return undefined; }
}

export function equippable(p) {
  try { return p.getComponent("minecraft:equippable"); } catch (_) { return undefined; }
}

export function getEquip(p, slot) {
  try { return equippable(p)?.getEquipment(slot); } catch (_) { return undefined; }
}

export function setEquip(p, slot, item) {
  try { return equippable(p)?.setEquipment(slot, item) !== false; } catch (_) { return false; }
}

export function selectedSlot(p) {
  try {
    const v = p.selectedSlotIndex;
    return typeof v === "number" ? v : (p.selectedSlot ?? 0);
  } catch (_) { return 0; }
}

export function heldItem(p) {
  const inv = container(p);
  try {
    const it = inv?.getItem(selectedSlot(p));
    if (it) return it;
  } catch (_) { }
  return getEquip(p, "Mainhand");
}

export function emptySlots(inv) {
  if (!inv) return 0;
  try {
    if (typeof inv.emptySlotsCount === "number") return inv.emptySlotsCount;
  } catch (_) { }
  let n = 0;
  for (let i = 0; i < (inv.size ?? 0); i++) { try { if (!inv.getItem(i)) n++; } catch (_) { } }
  return n;
}

/** インベントリから条件に合うスロットを全部探す。 */
export function findSlots(inv, pred) {
  const out = [];
  if (!inv) return out;
  for (let i = 0; i < (inv.size ?? 0); i++) {
    let it;
    try { it = inv.getItem(i); } catch (_) { continue; }
    if (it && pred(it, i)) out.push(i);
  }
  return out;
}

export function firstEmpty(inv, prefer = -1) {
  if (!inv) return -1;
  try { if (prefer >= 0 && !inv.getItem(prefer)) return prefer; } catch (_) { }
  for (let i = 0; i < (inv.size ?? 0); i++) {
    try { if (!inv.getItem(i)) return i; } catch (_) { }
  }
  return -1;
}

/** ItemStack に lockMode / keepOnDeath を付ける（無い版では黙って無視）。 */
export function lockItem(it, mode, keep) {
  if (!it) return it;
  try { if (mode !== undefined) it.lockMode = mode; } catch (_) { }
  try { if (keep !== undefined) it.keepOnDeath = keep; } catch (_) { }
  return it;
}

export function lockModeOf(it) {
  try { return it?.lockMode ?? "none"; } catch (_) { return "none"; }
}

/** アイテムを渡す。入りきらなければ足元に落とす。 */
export function give(p, item) {
  const inv = container(p);
  try {
    const left = inv ? inv.addItem(item) : item;
    if (left) p.dimension.spawnItem(left, p.location);
  } catch (_) { }
}

// ---------------------------------------------------------------------------
//  ブロック
// ---------------------------------------------------------------------------
const PASS = /(short_grass|tallgrass|tall_grass|fern|flower|sapling|torch|vine|snow_layer|carpet|button|lever|rail|pressure_plate|_sign|banner|bush|kelp|seagrass|mushroom|wheat|carrots|potatoes|beetroot|sugar_cane|dandelion|poppy|tulip|orchid|allium|azure_bluet|oxeye|cornflower|lily_of|rose_bush|peony|lilac|sunflower|web|structure_void|light_block|^minecraft:air$|fire|scaffolding|redstone_wire|tripwire|petals|glow_lichen|hanging_roots|moss_carpet|pink_petals|deadbush|nether_sprouts|crimson_roots|warped_roots)/;

/** そのブロック座標が固体か（草・花・松明などは通れる扱い）。 */
export function blocked(dim, pos) {
  try {
    const b = dim.getBlock({ x: Math.floor(pos.x), y: Math.floor(pos.y), z: Math.floor(pos.z) });
    if (!b) return false;
    if (b.isAir || b.isLiquid) return false;
    return !PASS.test(b.typeId);
  } catch (_) { return false; }
}

/** loc から下へ最大 maxDown ブロック探して地面の上面の高さを返す（見つからなければ loc.y）。 */
export function groundY(dim, loc, maxDown = 8, maxUp = 2) {
  const x = loc.x, z = loc.z;
  // 埋まっていたら上へ抜ける
  let y = Math.floor(loc.y);
  for (let k = 0; k < maxUp && blocked(dim, { x, y, z }); k++) y++;
  for (let k = 0; k <= maxDown; k++) {
    if (blocked(dim, { x, y: y - 1, z })) return y;
    y--;
  }
  return loc.y;
}

/** 地面に貼り付けた位置（y を上面に）。 */
export function onGround(dim, loc, maxDown = 8) {
  return { x: loc.x, y: groundY(dim, loc, maxDown), z: loc.z };
}

// ---------------------------------------------------------------------------
//  ベクトル
// ---------------------------------------------------------------------------
export const v3 = (x, y, z) => ({ x, y, z });
export const add = (a, b, k = 1) => ({ x: a.x + b.x * k, y: a.y + b.y * k, z: a.z + b.z * k });
export const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
export const scale = (a, k) => ({ x: a.x * k, y: a.y * k, z: a.z * k });
export const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;
export const len = (a) => Math.hypot(a.x, a.y, a.z);
export const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
export const hdist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
export const up = (a, y) => ({ x: a.x, y: a.y + y, z: a.z });
export function norm(a) {
  const l = len(a) || 1;
  return { x: a.x / l, y: a.y / l, z: a.z / l };
}
export function cross(a, b) {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}
export function lerp3(a, b, t) {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t };
}
/** 水平な前方向（視線の上下は捨てる）。 */
export function flatDir(e) {
  let d = { x: 0, y: 0, z: 1 };
  try { d = e.getViewDirection(); } catch (_) { }
  const l = Math.hypot(d.x, d.z);
  if (l < 1e-4) return { x: 0, y: 0, z: 1 };
  return { x: d.x / l, y: 0, z: d.z / l };
}
export function viewDir(e) {
  try { return norm(e.getViewDirection()); } catch (_) { return { x: 0, y: 0, z: 1 }; }
}
/** 水平面内で dir を deg 度回す（上から見て時計回りが正）。 */
export function yawRotate(dir, deg) {
  const r = deg * Math.PI / 180;
  const c = Math.cos(r), s = Math.sin(r);
  return { x: dir.x * c - dir.z * s, y: dir.y, z: dir.x * s + dir.z * c };
}
/** 前方 f から右 r・上 u の正規直交基底。 */
export function basis(f) {
  f = norm(f);
  const upv = Math.abs(f.y) > 0.95 ? { x: 0, y: 0, z: 1 } : { x: 0, y: 1, z: 0 };
  const r = norm(cross(f, upv));
  const u = norm(cross(r, f));
  return { f, r, u };
}
/** 水平な前方 f に対する右方向（プレイヤーから見て右）。 */
export function rightOf(f) {
  return { x: -f.z, y: 0, z: f.x };
}
export function chest(e) {
  const l = e.location;
  return { x: l.x, y: l.y + 1.0, z: l.z };
}
/** 水平方向の向き（度）。particle の v.rot 用: dir が +Z で 0、時計回りが正。 */
export function yawDeg(d) {
  return Math.atan2(-d.x, d.z) * 180 / Math.PI;
}
export function dirTo(from, to) {
  const d = { x: to.x - from.x, y: 0, z: to.z - from.z };
  const l = Math.hypot(d.x, d.z);
  return l < 1e-4 ? { x: 0, y: 0, z: 1 } : { x: d.x / l, y: 0, z: d.z / l };
}
export function rand(a, b) { return a + Math.random() * (b - a); }
export function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
export function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
export function finite(v) { return Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z); }
export const fmt = (n, d = 2) => (Number.isFinite(n) ? n : 0).toFixed(d);

export { world, system };
