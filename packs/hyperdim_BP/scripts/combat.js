// ===========================================================================
//  当たり判定・ダメージ・ゲージ・ダメージ表示
//
//  連続ヒットの扱い: Minecraft は被弾後およそ 10 tick 無敵になるので、技の細かい
//  多段ヒットをそのまま applyDamage すると大半が消える。そこで「通らなかった分」を
//  対象ごとに貯めておき、無敵が切れた瞬間にまとめて通す（ダメージバンク）。
//  見た目の当たり（火花・数字・音）は毎回その場で出す。
// ===========================================================================
import { world, system } from "@minecraft/server";
import { GAUGE_MAX, PROP_GAUGE, IGNORE_TYPES } from "./config.js";
import { P, burst, sound, white } from "./fx.js";
import {
  valid, health, knock, dist, norm, sub, chest, numProp, setProp, rand, now, effect,
} from "./util.js";

// ---------------------------------------------------------------------------
//  標的
// ---------------------------------------------------------------------------
export function isTarget(attacker, e) {
  if (!valid(e) || e.id === attacker.id) return false;
  if (IGNORE_TYPES.has(e.typeId)) return false;
  if (!health(e)) return false;
  try {
    if (e.typeId === "minecraft:player") {
      const gm = e.getGameMode?.();
      if (gm === "creative" || gm === "spectator" || gm === "Creative" || gm === "Spectator") return false;
    }
  } catch (_) { }
  try {
    const tame = e.getComponent("minecraft:tameable");
    if (tame?.isTamed && tame.tamedToPlayerId === attacker.id) return false;
  } catch (_) { }
  return true;
}

export function enemiesNear(attacker, loc, radius, dim = attacker.dimension) {
  let list = [];
  try { list = dim.getEntities({ location: loc, maxDistance: radius }); } catch (_) { }
  return list.filter((e) => isTarget(attacker, e));
}

/** 原点から dir 方向の扇形（range m, 半角 deg 度）。 */
export function enemiesInCone(attacker, origin, dir, range, deg) {
  const cos = Math.cos(deg * Math.PI / 180);
  return enemiesNear(attacker, origin, range + 1.5).filter((e) => {
    const to = sub(chest(e), origin);
    const d = Math.hypot(to.x, to.y, to.z);
    if (d < 1.2) return true;
    return (to.x * dir.x + to.y * dir.y + to.z * dir.z) / d >= cos && d <= range + 0.6;
  });
}

/** a→b の線分から width m 以内。 */
export function enemiesOnLine(attacker, a, b, width) {
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
  const half = dist(a, b) / 2 + width + 1;
  const ab = sub(b, a);
  const L2 = ab.x * ab.x + ab.y * ab.y + ab.z * ab.z || 1;
  return enemiesNear(attacker, mid, half).filter((e) => {
    const c = chest(e);
    const ap = sub(c, a);
    const t = Math.max(0, Math.min(1, (ap.x * ab.x + ap.y * ab.y + ap.z * ab.z) / L2));
    const q = { x: a.x + ab.x * t, y: a.y + ab.y * t, z: a.z + ab.z * t };
    return dist(q, c) <= width + 0.4;
  });
}

export function nearestEnemy(attacker, loc, radius, dir, deg = 180) {
  const list = deg >= 180 ? enemiesNear(attacker, loc, radius)
    : enemiesInCone(attacker, loc, dir, radius, deg);
  let best, bd = Infinity;
  for (const e of list) {
    const d = dist(e.location, loc);
    if (d < bd) { bd = d; best = e; }
  }
  return best;
}

// ---------------------------------------------------------------------------
//  ダメージ
// ---------------------------------------------------------------------------
const bank = new Map();   // targetId -> { e, attacker, pending, tries }
const crits = new Map();  // targetId -> 会心表示の期限 tick

/** 実際に通ったダメージ（entityHurt）から数字を出す。会心の印が残っていれば赤字。 */
export function showDamage(target, amount) {
  if (amount < 0.05) return;
  const until = crits.get(target.id);
  const crit = until !== undefined && until >= now();
  if (crit) crits.delete(target.id);
  popNumber(target, amount, crit);
}

function rawDamage(attacker, target, amount) {
  try {
    return target.applyDamage(amount, { cause: "entityAttack", damagingEntity: attacker });
  } catch (_) {
    try { return target.applyDamage(amount); } catch (__) { return false; }
  }
}

/**
 * 技の一撃。o.kb 水平ノックバック / o.up 上方向 / o.dir ノックバック方向 /
 * o.color 当たりの色 / o.power 演出の規模 / o.crit 会心表示 / o.quiet 演出なし /
 * o.gauge ゲージ増加（既定 3）
 */
export function hit(attacker, target, amount, o = {}) {
  if (!isTarget(attacker, target)) return false;
  amount = Math.max(0, amount);
  const applied = rawDamage(attacker, target, amount);
  if (!applied) {
    const b = bank.get(target.id) ?? { e: target, attacker, pending: 0, tries: 0 };
    b.pending += amount;
    b.attacker = attacker;
    bank.set(target.id, b);
  }
  // ノックバック
  if (o.kb || o.up) {
    let d = o.dir;
    if (!d) {
      const t = sub(target.location, attacker.location);
      d = norm({ x: t.x, y: 0, z: t.z });
    }
    knock(target, d.x, d.z, o.kb ?? 0, o.up ?? 0);
  }
  if (!o.quiet) {
    const c = o.color ?? [1, 1, 1];
    const at = chest(target);
    burst(target.dimension, at, c, o.power ?? 1);
    if (o.sound) sound(target.dimension, o.sound, at, rand(0.9, 1.15), 0.9);
  }
  if (o.crit) crits.set(target.id, now() + 30);
  addGauge(attacker, o.gauge ?? 3);
  return true;
}

/** 無敵切れを待っている分を流す（毎 tick）。 */
export function flushBank() {
  if (!bank.size) return;
  for (const [id, b] of bank) {
    if (!valid(b.e) || !valid(b.attacker)) { bank.delete(id); continue; }
    if (rawDamage(b.attacker, b.e, b.pending)) {
      bank.delete(id);
    } else if (++b.tries > 30) {
      bank.delete(id);
    }
  }
}

// ---------------------------------------------------------------------------
//  ダメージ表示（浮かび上がる数字）
// ---------------------------------------------------------------------------
const pops = [];
const MAX_POPS = 36;

export function popNumber(target, amount, crit) {
  if (pops.length >= MAX_POPS) return;
  try {
    const l = target.location;
    const h = (target.typeId === "minecraft:player" ? 2.1 : 1.8);
    const at = { x: l.x + rand(-0.5, 0.5), y: l.y + h + rand(0, 0.4), z: l.z + rand(-0.5, 0.5) };
    const e = target.dimension.spawnEntity("hd:dmg_text", at);
    const n = Math.round(amount * 10) / 10;
    const txt = crit ? `§c§l${n}!` : (amount >= 8 ? `§6§l${n}` : `§e§l${n}`);
    e.nameTag = txt;
    pops.push({ e, t: 0, x: at.x, y: at.y, z: at.z, vx: rand(-0.04, 0.04), vz: rand(-0.04, 0.04) });
  } catch (_) { }
}

export function tickPops() {
  for (let i = pops.length - 1; i >= 0; i--) {
    const p = pops[i];
    p.t++;
    if (!valid(p.e) || p.t > 18) {
      try { p.e.remove(); } catch (_) { }
      pops.splice(i, 1);
      continue;
    }
    const rise = p.t < 6 ? 0.12 : 0.03;
    p.x += p.vx; p.z += p.vz; p.y += rise;
    try { p.e.teleport({ x: p.x, y: p.y, z: p.z }); } catch (_) { }
  }
}

// ---------------------------------------------------------------------------
//  超次元ゲージ
// ---------------------------------------------------------------------------
const gauges = new Map();

export function gauge(player) {
  if (!gauges.has(player.id)) gauges.set(player.id, numProp(player, PROP_GAUGE, 0));
  return gauges.get(player.id);
}

export function setGauge(player, v) {
  const before = gauge(player);
  const g = Math.max(0, Math.min(GAUGE_MAX, v));
  gauges.set(player.id, g);
  if (before < GAUGE_MAX && g >= GAUGE_MAX && valid(player)) {
    // 満タンの合図
    sound(player.dimension, "hd.ding", player.location, 1.0, 0.8);
    try { player.onScreenDisplay.setTitle(" ", { subtitle: "§6§l★ 必殺技 READY ★", fadeInDuration: 2, stayDuration: 20, fadeOutDuration: 6 }); } catch (_) { }
    P(player.dimension, "ring", chest(player), { color: [1, 0.85, 0.3], size: 1.6, life: 0.4 });
  }
}

// 必殺技の最中はゲージが溜まらない（撃った直後に満タンへ戻らないように）
const lockUntil = new Map();
export function lockGauge(player, ticks) { lockUntil.set(player.id, now() + ticks); }

export function addGauge(player, v) {
  if (!valid(player) || player.typeId !== "minecraft:player") return;
  if ((lockUntil.get(player.id) ?? -1) > now()) return;
  setGauge(player, gauge(player) + v);
}

export function saveGauges() {
  for (const [id, g] of gauges) {
    const p = world.getEntity?.(id);
    if (p && valid(p)) setProp(p, PROP_GAUGE, g);
  }
}

// ---------------------------------------------------------------------------
//  状態異常のまとめ
// ---------------------------------------------------------------------------
export function freeze(e, ticks, strong = false) {
  effect(e, "slowness", ticks, strong ? 9 : 3);
  if (strong) effect(e, "weakness", ticks, 1);
}

export function bind(e, ticks) {
  effect(e, "slowness", ticks, 5);
}

export { system, white };
