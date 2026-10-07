// ===========================================================================
//  超次元バトルアーツ — 共通ユーティリティ
//  API の版差（1.x / 2.x）を吸収する薄いラッパと、ベクトル計算。
// ===========================================================================
import { world, system } from "@minecraft/server";

export const now = () => system.currentTick;

export function valid(e) {
  if (!e) return false;
  try {
    const v = e.isValid;
    return typeof v === "function" ? v.call(e) : v !== false;
  } catch (_) { return false; }
}

export function allPlayers() {
  try { return world.getAllPlayers(); } catch (_) { return []; }
}

/** 同期コマンドが無い版では非同期版へ落とす。 */
export function cmd(source, command) {
  try {
    if (typeof source.runCommand === "function") return source.runCommand(command);
  } catch (_) { /* 次へ */ }
  try { return source.runCommandAsync?.(command); } catch (_) { return undefined; }
}

export function heldItem(player) {
  try {
    const eq = player.getComponent("minecraft:equippable");
    const it = eq?.getEquipment?.("Mainhand");
    if (it) return it;
  } catch (_) { /* 次へ */ }
  try {
    const inv = player.getComponent("minecraft:inventory")?.container;
    const slot = typeof player.selectedSlotIndex === "number"
      ? player.selectedSlotIndex : (player.selectedSlot ?? 0);
    return inv?.getItem(slot);
  } catch (_) { return undefined; }
}

/** applyKnockback は 1.x (dx, dz, 水平, 垂直) と 2.x ({x,z}*強さ, 垂直) で引数が違う。 */
export function knock(entity, dx, dz, horizontal, vertical) {
  try {
    entity.applyKnockback(dx, dz, horizontal, vertical);
    return;
  } catch (_) { /* 2.x */ }
  try { entity.applyKnockback({ x: dx * horizontal, z: dz * horizontal }, vertical); } catch (_) { }
}

export function effect(entity, id, ticks, amp = 0, particles = false) {
  try { entity.addEffect(id, Math.max(1, Math.round(ticks)), { amplifier: amp, showParticles: particles }); }
  catch (_) { }
}

export function health(entity) {
  try { return entity.getComponent("minecraft:health"); } catch (_) { return undefined; }
}

export function numProp(holder, key, fallback = 0) {
  try {
    const v = holder.getDynamicProperty(key);
    return typeof v === "number" ? v : fallback;
  } catch (_) { return fallback; }
}

export function setProp(holder, key, v) {
  try { holder.setDynamicProperty(key, v); } catch (_) { }
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
export function flatDir(player) {
  let d = { x: 0, y: 0, z: 1 };
  try { d = player.getViewDirection(); } catch (_) { }
  const l = Math.hypot(d.x, d.z) || 1;
  return { x: d.x / l, y: 0, z: d.z / l };
}
export function viewDir(player) {
  try { return norm(player.getViewDirection()); } catch (_) { return { x: 0, y: 0, z: 1 }; }
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
  const up = Math.abs(f.y) > 0.95 ? { x: 0, y: 0, z: 1 } : { x: 0, y: 1, z: 0 };
  const r = norm(cross(f, up));
  const u = norm(cross(r, f));
  return { f, r, u };
}
export function chest(e) {
  const l = e.location;
  return { x: l.x, y: l.y + 1.0, z: l.z };
}
export function rand(a, b) { return a + Math.random() * (b - a); }
export function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
export function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
