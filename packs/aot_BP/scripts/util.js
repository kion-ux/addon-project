// ===========================================================================
//  進撃の巨人アドオン — 共通ユーティリティ
//  API の版差（1.x / 2.x）を吸収する薄いラッパと、ベクトル計算。
// ===========================================================================
import { world, system } from "@minecraft/server";

export const now = () => system.currentTick;

export function tr(key, ...args) {
  return { rawtext: [{ translate: key, with: args.map(String) }] };
}

/** 翻訳キーと素の文字列を混ぜたメッセージ。parts: ["§a", {t:"key", w:[..]}, "123"] */
export function rt(...parts) {
  return {
    rawtext: parts.map((p) => (typeof p === "string" ? { text: p }
      : { translate: p.t, with: (p.w ?? []).map(String) })),
  };
}

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

export function dims() {
  const out = [];
  for (const id of ["overworld", "nether", "the_end"]) {
    try { out.push(world.getDimension(id)); } catch (_) { }
  }
  return out;
}

/** 同期コマンドが無い版では非同期版へ落とす。 */
export function cmd(source, command) {
  try {
    if (typeof source.runCommand === "function") return source.runCommand(command);
  } catch (_) { /* 次へ */ }
  try { return source.runCommandAsync?.(command); } catch (_) { return undefined; }
}

export function tell(p, msg) { try { p.sendMessage(msg); } catch (_) { } }
export function actionbar(p, msg) { try { p.onScreenDisplay.setActionBar(msg); } catch (_) { } }
export function title(p, main, sub, stay = 30) {
  try {
    p.onScreenDisplay.setTitle(main, { subtitle: sub, fadeInDuration: 2, stayDuration: stay,
                                       fadeOutDuration: 10 });
  } catch (_) { }
}

export function container(p) {
  try { return p.getComponent("minecraft:inventory")?.container; } catch (_) { return undefined; }
}

export function selectedSlot(p) {
  const v = p.selectedSlotIndex;
  return typeof v === "number" ? v : (p.selectedSlot ?? 0);
}

export function heldItem(p) {
  try {
    const eq = p.getComponent("minecraft:equippable");
    const it = eq?.getEquipment?.("Mainhand");
    if (it) return it;
  } catch (_) { /* 次へ */ }
  try { return container(p)?.getItem(selectedSlot(p)); } catch (_) { return undefined; }
}

export function equipped(p, slot) {
  try { return p.getComponent("minecraft:equippable")?.getEquipment?.(slot); } catch (_) { return undefined; }
}

export function isCreative(p) {
  try {
    const gm = p.getGameMode?.();
    if (gm !== undefined) return String(gm).toLowerCase() === "creative";
  } catch (_) { }
  try { return p.matches?.({ gameMode: "creative" }) ?? false; } catch (_) { return false; }
}

/** インベントリから typeId を n 個探して減らす。足りなければ何もせず false。 */
export function consume(p, typeId, n = 1) {
  const inv = container(p);
  if (!inv) return false;
  let have = 0;
  for (let i = 0; i < inv.size; i++) {
    const it = inv.getItem(i);
    if (it?.typeId === typeId) have += it.amount;
  }
  if (have < n) return false;
  let left = n;
  for (let i = 0; i < inv.size && left > 0; i++) {
    const it = inv.getItem(i);
    if (it?.typeId !== typeId) continue;
    const take = Math.min(left, it.amount);
    left -= take;
    if (it.amount > take) { it.amount -= take; inv.setItem(i, it); } else inv.setItem(i, undefined);
  }
  return true;
}

export function count(p, typeId) {
  const inv = container(p);
  if (!inv) return 0;
  let n = 0;
  for (let i = 0; i < inv.size; i++) {
    const it = inv.getItem(i);
    if (it?.typeId === typeId) n += it.amount;
  }
  return n;
}

/** applyKnockback は 1.x (dx, dz, 水平, 垂直) と 2.x ({x,z}*強さ, 垂直) で引数が違う。 */
export function knock(entity, dx, dz, horizontal, vertical) {
  try { entity.applyKnockback(dx, dz, horizontal, vertical); return; } catch (_) { /* 2.x */ }
  try { entity.applyKnockback({ x: dx * horizontal, z: dz * horizontal }, vertical); } catch (_) { }
}

/** 速度をそのまま与える（プレイヤーはノックバック、それ以外はインパルス）。 */
export function setVelocity(entity, v) {
  if (entity.typeId === "minecraft:player") {
    const h = Math.hypot(v.x, v.z);
    if (h < 1e-4) knock(entity, 0, 0, 0, v.y);
    else knock(entity, v.x / h, v.z / h, h, v.y);
    return;
  }
  try { entity.clearVelocity(); } catch (_) { }
  try { entity.applyImpulse(v); } catch (_) { }
}

export function velocity(e) {
  try { return e.getVelocity(); } catch (_) { return { x: 0, y: 0, z: 0 }; }
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

export function boolProp(holder, key, fallback = false) {
  try {
    const v = holder.getDynamicProperty(key);
    return typeof v === "boolean" ? v : fallback;
  } catch (_) { return fallback; }
}

export function setProp(holder, key, v) {
  try { holder.setDynamicProperty(key, v); } catch (_) { }
}

export function event(entity, id) {
  try { entity.triggerEvent(id); return true; } catch (_) { return false; }
}

export function damage(target, amount, source, cause = "override") {
  try {
    target.applyDamage(Math.max(1, Math.round(amount)),
                       source ? { cause, damagingEntity: source } : { cause });
    return true;
  } catch (_) {
    try { target.applyDamage(Math.max(1, Math.round(amount))); return true; } catch (__) { return false; }
  }
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
export function viewDir(e) {
  try { return norm(e.getViewDirection()); } catch (_) { return { x: 0, y: 0, z: 1 }; }
}
export function flatDir(e) {
  const d = viewDir(e);
  const l = Math.hypot(d.x, d.z) || 1;
  return { x: d.x / l, y: 0, z: d.z / l };
}
/** 体の向き（ヨー）からの前・右。Minecraft のヨー 0 は +Z を向く。 */
export function yawFrame(e) {
  let yaw = 0;
  try { yaw = e.getRotation().y; } catch (_) { }
  const r = yaw * Math.PI / 180;
  const f = { x: -Math.sin(r), y: 0, z: Math.cos(r) };
  const right = { x: -f.z, y: 0, z: f.x };
  return { f, r: right, yaw };
}
export function eye(e) {
  try { return e.getHeadLocation(); } catch (_) { return add(e.location, { x: 0, y: 1.6, z: 0 }); }
}
export function chest(e) { const l = e.location; return { x: l.x, y: l.y + 1.0, z: l.z }; }
export function rand(a, b) { return a + Math.random() * (b - a); }
export function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
export function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

/** 線分 p0→p1 と点 q の最短距離と、その時の線分上の位置 t (0..1)。 */
export function segPoint(p0, p1, q) {
  const d = sub(p1, p0);
  const L2 = dot(d, d) || 1e-9;
  const t = clamp(dot(sub(q, p0), d) / L2, 0, 1);
  const c = add(p0, d, t);
  return { t, d: dist(c, q), at: c };
}

/** 半直線（o, dir 正規化, 長さ L）と、縦の線分（底 a・高さ h）の最短距離。 */
export function rayVsColumn(o, dir, L, a, h) {
  // 近似: 半直線を細かく刻まずに、縦軸との最近接を解析的に求める
  const b = { x: a.x, y: a.y + h, z: a.z };
  const u = dir;
  const v = sub(b, a);
  const w = sub(o, a);
  const A = dot(u, u), B = dot(u, v), Cc = dot(v, v), D = dot(u, w), E = dot(v, w);
  const den = A * Cc - B * B;
  let s = den > 1e-9 ? (B * E - Cc * D) / den : 0;
  let t = den > 1e-9 ? (A * E - B * D) / den : 0;
  s = clamp(s, 0, L);
  t = clamp(t, 0, 1);
  // 片方を固定してもう一方を取り直す（端点処理）
  const p = add(o, u, s);
  const q = add(a, v, clamp(dot(sub(p, a), v) / (Cc || 1e-9), 0, 1));
  s = clamp(dot(sub(q, o), u), 0, L);
  const p2 = add(o, u, s);
  return { s, d: dist(p2, q), at: p2, on: q };
}
