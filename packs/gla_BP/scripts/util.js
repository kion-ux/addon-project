// 共通ヘルパ / shared helpers
//
// Bedrock のスクリプト API は版によって形が変わるので、ここでは
// 「落ちない」ことを最優先にする。try/catch で握りつぶす代わりに、
// 呼び出し側が判断できるよう既定値を返す。
import { world, system } from "@minecraft/server";

export function tr(key, ...args) {
  return { rawtext: [{ translate: key, with: args.map(String) }] };
}

export function line(...parts) {
  return { rawtext: parts.map((p) => (typeof p === "string" ? { text: p } : p)) };
}

export function tell(target, msg) {
  try { target.sendMessage(msg); } catch (_) { }
}

export function actionbar(player, msg) {
  try { player.onScreenDisplay.setActionBar(msg); } catch (_) { }
}

export function title(player, msg, opts) {
  try { player.onScreenDisplay.setTitle(msg, opts); } catch (_) { }
}

export function num(holder, key, fallback = 0) {
  try {
    const v = holder.getDynamicProperty(key);
    return typeof v === "number" ? v : fallback;
  } catch (_) { return fallback; }
}

export function bool(holder, key, fallback = false) {
  try {
    const v = holder.getDynamicProperty(key);
    return typeof v === "boolean" ? v : fallback;
  } catch (_) { return fallback; }
}

export function str(holder, key, fallback = "") {
  try {
    const v = holder.getDynamicProperty(key);
    return typeof v === "string" ? v : fallback;
  } catch (_) { return fallback; }
}

export function setProp(holder, key, value) {
  try { holder.setDynamicProperty(key, value); return true; } catch (_) { return false; }
}

export function allPlayers() {
  try { return world.getAllPlayers(); } catch (_) { return []; }
}

export function bar(ratio, width = 10, full = "▮", empty = "▯") {
  const filled = Math.max(0, Math.min(width, Math.round(ratio * width)));
  return full.repeat(filled) + empty.repeat(width - filled);
}

// ---------------------------------------------------------------------------
//  ベクトル
// ---------------------------------------------------------------------------
export function add(a, b, k = 1) {
  return { x: a.x + b.x * k, y: a.y + b.y * k, z: a.z + b.z * k };
}

export function scale(v, k) {
  return { x: v.x * k, y: v.y * k, z: v.z * k };
}

export function length(v) {
  return Math.hypot(v.x, v.y, v.z);
}

export function normalise(v) {
  const l = length(v) || 1;
  return { x: v.x / l, y: v.y / l, z: v.z / l };
}

export function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

export function forward(origin, dir, d) {
  return { x: origin.x + dir.x * d, y: origin.y + dir.y * d, z: origin.z + dir.z * d };
}

export function dot(a, b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

/** 視線から右手系の基底を作る。真上・真下でも破綻しないよう参照軸を選び直す。 */
export function basis(dir) {
  const f = normalise(dir);
  const up = Math.abs(f.y) > 0.94 ? { x: 0, y: 0, z: 1 } : { x: 0, y: 1, z: 0 };
  const r = normalise({
    x: f.y * up.z - f.z * up.y,
    y: f.z * up.x - f.x * up.z,
    z: f.x * up.y - f.y * up.x,
  });
  const u = {
    x: r.y * f.z - r.z * f.y,
    y: r.z * f.x - r.x * f.z,
    z: r.x * f.y - r.y * f.x,
  };
  return { f, r, u };
}

export function atBasis(origin, b, along, right, up) {
  return {
    x: origin.x + b.f.x * along + b.r.x * right + b.u.x * up,
    y: origin.y + b.f.y * along + b.r.y * right + b.u.y * up,
    z: origin.z + b.f.z * along + b.r.z * right + b.u.z * up,
  };
}

export function viewDir(entity) {
  try {
    const d = entity.getViewDirection();
    if (d && Number.isFinite(d.x)) return d;
  } catch (_) { }
  return { x: 0, y: 0, z: 1 };
}

// ---------------------------------------------------------------------------
//  クールダウン — プレイヤーごと・キーごと。退出時に掃除する。
// ---------------------------------------------------------------------------
const cooldowns = new Map();

export function onCooldown(id, key) {
  return cooldownLeft(id, key) > 0;
}

export function cooldownLeft(id, key) {
  const map = cooldowns.get(id);
  if (!map) return 0;
  return Math.max(0, (map.get(key) ?? 0) - system.currentTick);
}

export function setCooldown(id, key, ticks) {
  let map = cooldowns.get(id);
  if (!map) { map = new Map(); cooldowns.set(id, map); }
  map.set(key, system.currentTick + ticks);
}

export function clearCooldowns(id) {
  cooldowns.delete(id);
}

/** 退出したプレイヤーの残骸を各モジュールから消すための登録口。 */
const cleaners = [clearCooldowns];

export function onForget(fn) {
  cleaners.push(fn);
}

export function forget(id) {
  for (const fn of cleaners) {
    try { fn(id); } catch (_) { }
  }
}

// ---------------------------------------------------------------------------
//  その他
// ---------------------------------------------------------------------------
/**
 * tick をまたいだ予約。技の演出も判定もこれで動く。
 *
 * 中で例外が出てもワールドを止めないが、**黙って消さない**。
 * 握り潰すと「演出が丸ごと死んでいるのに何も起きない」になり、
 * 実機で何時間も探すことになる。コンテンツログには必ず残す。
 */
export function later(ticks, fn) {
  try {
    return system.runTimeout(() => {
      try {
        fn();
      } catch (e) {
        console.warn(`[gla] scheduled work failed: ${e?.stack ?? e}`);
      }
    }, Math.max(1, Math.round(ticks)));
  } catch (e) {
    console.warn(`[gla] could not schedule work: ${e}`);
    return undefined;
  }
}

export function cancel(handle) {
  if (handle === undefined) return;
  try { system.clearRun(handle); } catch (_) { }
}

export function hasFamily(entity, family) {
  try {
    const c = entity.getComponent("minecraft:type_family");
    if (c) return c.hasTypeFamily(family);
  } catch (_) { }
  return false;
}

export function health(entity) {
  try {
    const h = entity.getComponent("minecraft:health");
    if (!h) return null;
    return { now: Math.max(0, Math.round(h.currentValue)), max: Math.round(h.effectiveMax) };
  } catch (_) { return null; }
}

/** applyKnockback は script API 1.x と 2.x で引数が違う。 */
export function knockback(entity, dx, dz, horizontal, vertical) {
  try {
    entity.applyKnockback(dx, dz, horizontal, vertical);
    return;
  } catch (_) { }
  try { entity.applyKnockback({ x: dx, z: dz }, horizontal, vertical); } catch (_) { }
}

export function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}
