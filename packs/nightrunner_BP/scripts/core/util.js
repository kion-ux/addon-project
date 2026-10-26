// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 共通の小道具（ベクトル・向き・安全な呼び出し）
//
//  向きの約束（DESIGN §12 / §13、nr_rig.hitboxes の docstring と同じ）:
//    yaw = getRotation().y（度）。0 = 南（+Z）、90 = 西（−X）。
//    前 F = (−sin yaw, 0, cos yaw)、右 R = (−cos yaw, 0, −sin yaw)。
//    当たり箱・ロケータの [r, u, f] は「ゾンビ自身の右・上・前」で、
//    ワールド = 足元 + r·R + u·(0,1,0) + f·F。
// ===========================================================================
import { system } from "@minecraft/server";

/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {[number, number, number]} RUF */

export const DEG = Math.PI / 180;
export const UP = Object.freeze({ x: 0, y: 1, z: 0 });
export const DOWN = Object.freeze({ x: 0, y: -1, z: 0 });

// ---------------------------------------------------------------------------
//  ベクトル
// ---------------------------------------------------------------------------
/** @returns {Vector3} */
export function v3(x = 0, y = 0, z = 0) { return { x, y, z }; }
/** @param {Vector3} a @param {Vector3} b @returns {Vector3} */
export function add(a, b) { return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z }; }
/** @param {Vector3} a @param {Vector3} b @returns {Vector3} */
export function sub(a, b) { return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z }; }
/** @param {Vector3} a @param {number} s @returns {Vector3} */
export function scale(a, s) { return { x: a.x * s, y: a.y * s, z: a.z * s }; }
/** a + b·s @param {Vector3} a @param {Vector3} b @param {number} s @returns {Vector3} */
export function addScaled(a, b, s) { return { x: a.x + b.x * s, y: a.y + b.y * s, z: a.z + b.z * s }; }
/** @param {Vector3} a @param {Vector3} b */
export function dot(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
/** @param {Vector3} a */
export function len(a) { return Math.hypot(a.x, a.y, a.z); }
/** @param {Vector3} a */
export function lenXZ(a) { return Math.hypot(a.x, a.z); }
/** @param {Vector3} a @param {Vector3} b */
export function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z); }
/** @param {Vector3} a @param {Vector3} b */
export function distXZ(a, b) { return Math.hypot(a.x - b.x, a.z - b.z); }
/** 正規化（長さ 0 なら fallback）。@param {Vector3} a @param {Vector3} [fallback] @returns {Vector3} */
export function norm(a, fallback = { x: 0, y: 0, z: 1 }) {
  const l = Math.hypot(a.x, a.y, a.z);
  return l > 1e-9 && Number.isFinite(l) ? { x: a.x / l, y: a.y / l, z: a.z / l } : { ...fallback };
}
/** 水平だけ残して正規化。@param {Vector3} a @param {Vector3} [fallback] @returns {Vector3} */
export function flat(a, fallback = { x: 0, y: 0, z: 1 }) { return norm({ x: a.x, y: 0, z: a.z }, fallback); }
/** @param {Vector3} a @param {Vector3} b @param {number} t @returns {Vector3} */
export function lerpV(a, b, t) { return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t }; }
/** @param {number} a @param {number} b @param {number} t */
export function lerp(a, b, t) { return a + (b - a) * t; }
/** @param {number} v @param {number} lo @param {number} hi */
export function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
/** @param {number} v */
export function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
/** 有限の {x,y,z} か。@param {any} v */
export function finiteVec(v) { return !!v && Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z); }

// ---------------------------------------------------------------------------
//  向き（yaw → 前・右）とゾンビの局所座標 [r, u, f]
// ---------------------------------------------------------------------------
/** @param {number} yawDeg @returns {Vector3} */
export function yawForward(yawDeg) { const a = yawDeg * DEG; return { x: -Math.sin(a), y: 0, z: Math.cos(a) }; }
/** @param {number} yawDeg @returns {Vector3} */
export function yawRight(yawDeg) { const a = yawDeg * DEG; return { x: -Math.cos(a), y: 0, z: -Math.sin(a) }; }
/** 向きベクトル → yaw（度）。@param {Vector3} d */
export function yawOfDir(d) { return Math.atan2(-d.x, d.z) / DEG; }
/** エンティティの yaw（読めなければ 0）。@param {Entity} e */
export function yawOf(e) { try { return e.getRotation().y; } catch { return 0; } }

/** ワールドの点 → 局所 [r, u, f]。@param {Vector3} origin @param {number} yawDeg @param {Vector3} p @returns {RUF} */
export function toLocal(origin, yawDeg, p) {
  const F = yawForward(yawDeg), R = yawRight(yawDeg);
  const d = sub(p, origin);
  return [d.x * R.x + d.z * R.z, d.y, d.x * F.x + d.z * F.z];
}
/** 局所 [r, u, f] → ワールドの点。@param {Vector3} origin @param {number} yawDeg @param {ArrayLike<number>} ruf @returns {Vector3} */
export function toWorld(origin, yawDeg, ruf) {
  const F = yawForward(yawDeg), R = yawRight(yawDeg);
  return {
    x: origin.x + ruf[0] * R.x + ruf[2] * F.x,
    y: origin.y + ruf[1],
    z: origin.z + ruf[0] * R.z + ruf[2] * F.z,
  };
}
/** ワールドの向き → 局所の向き [r, u, f]。@param {number} yawDeg @param {Vector3} d @returns {RUF} */
export function dirToLocal(yawDeg, d) {
  const F = yawForward(yawDeg), R = yawRight(yawDeg);
  return [d.x * R.x + d.z * R.z, d.y, d.x * F.x + d.z * F.z];
}
/** 局所の向き → ワールドの向き。@param {number} yawDeg @param {ArrayLike<number>} ruf @returns {Vector3} */
export function dirToWorld(yawDeg, ruf) {
  const F = yawForward(yawDeg), R = yawRight(yawDeg);
  return { x: ruf[0] * R.x + ruf[2] * F.x, y: ruf[1], z: ruf[0] * R.z + ruf[2] * F.z };
}

// ---------------------------------------------------------------------------
//  乱数（Math.random。テストの偽物は種を固定している）
// ---------------------------------------------------------------------------
/** @param {number} lo @param {number} hi */
export function rand(lo, hi) { return lo + Math.random() * (hi - lo); }
/** 両端を含む整数。@param {number} lo @param {number} hi */
export function randInt(lo, hi) { return Math.floor(lo + Math.random() * (Math.floor(hi) - Math.floor(lo) + 1)); }
/** @param {number} p */
export function chance(p) { return p > 0 && Math.random() < p; }
/** @template T @param {readonly T[]} arr @returns {T | undefined} */
export function pick(arr) { return arr.length ? arr[Math.floor(Math.random() * arr.length)] : undefined; }
/** 向きを少し散らして正規化。@param {Vector3} d @param {number} s */
export function jitterDir(d, s) { return norm({ x: d.x + rand(-s, s), y: d.y + rand(-s, s), z: d.z + rand(-s, s) }, d); }
/** [lo, hi] か数を 1 つの数に（範囲なら乱数）。@param {any} v @param {number} def */
export function rangeVal(v, def) {
  if (Array.isArray(v) && v.length >= 2) return rand(Number(v[0]), Number(v[1]));
  return Number.isFinite(v) ? Number(v) : def;
}

// ---------------------------------------------------------------------------
//  エンティティ・安全な呼び出し
// ---------------------------------------------------------------------------
/** 有効なエンティティか（無効・undefined・例外は false）。@param {any} e @returns {boolean} */
export function valid(e) { try { return !!e && e.isValid === true; } catch { return false; } }
/** いまの tick。 */
export function now() { return system.currentTick; }

/** ゾンビの ID か。@param {string | undefined} typeId */
export function isZombieId(typeId) { return typeof typeId === "string" && typeId.startsWith("nr:z_"); }
/** @param {any} e */
export function isZombie(e) { return !!e && isZombieId(e.typeId); }
/** @param {any} e */
export function isPlayer(e) { return !!e && e.typeId === "minecraft:player"; }
/** nr:z_office_worker → office_worker（ゾンビ以外は ""）。@param {string | undefined} typeId */
export function zkey(typeId) { return isZombieId(typeId) ? String(typeId).slice(5) : ""; }

/** プロパティを読む（無い・例外なら def）。@param {Entity} e @param {string} name @param {any} def */
export function getProp(e, name, def) {
  try { const v = e.getProperty(name); return v === undefined ? def : v; } catch { return def; }
}
/** プロパティを書く（失敗は false）。@param {Entity} e @param {string} name @param {boolean | number | string} value */
export function setProp(e, name, value) {
  try { e.setProperty(name, value); return true; } catch (err) { warnOnce(`setProp:${e?.typeId}:${name}`, "setProperty 失敗", name, value, err); return false; }
}
/** BP イベントを呼ぶ（失敗は false）。@param {Entity} e @param {string} name */
export function trigger(e, name) {
  try { e.triggerEvent(name); return true; } catch (err) { warnOnce(`trigger:${e?.typeId}:${name}`, "triggerEvent 失敗", name, err); return false; }
}
/** 数の動的プロパティ（無ければ def）。@param {Entity} e @param {string} k @param {number} def */
export function dpNum(e, k, def) {
  try { const v = e.getDynamicProperty(k); return typeof v === "number" && Number.isFinite(v) ? v : def; } catch { return def; }
}
/** エンティティを消す（remove が駄目なら nr:despawn）。@param {Entity} e */
export function despawn(e) {
  if (!valid(e)) return;
  try { e.remove(); } catch { try { e.triggerEvent("nr:despawn"); } catch { /* 既に無い */ } }
}

const warned = new Set();
/** 同じ key の警告は 1 回だけ。@param {string} key @param {...any} msg */
export function warnOnce(key, ...msg) {
  if (warned.has(key) || warned.size > 500) return;
  warned.add(key);
  console.warn("[nr]", ...msg.map((m) => (m instanceof Error ? m.message : m)));
}
/** fn を例外で止めずに呼ぶ（失敗は label ごとに 1 回警告）。@template T @param {string} label @param {() => T} fn @returns {T | undefined} */
export function safe(label, fn) {
  try { return fn(); } catch (err) { warnOnce(`safe:${label}`, label, err); return undefined; }
}
/** n tick 後に fn（例外は握る）。@param {number} ticks @param {() => void} fn */
export function later(ticks, fn) {
  return system.runTimeout(() => safe("later", fn), Math.max(1, Math.round(ticks)));
}
