// ===========================================================================
//  設置型の範囲（雲・嵐・陣・溶岩の噴火口・重力の井戸…）
//
//  中心と半径と寿命を持ち、毎 tick 見た目を描き、every tick ごとに中の敵へダメージ・効果・
//  引き寄せを与える。follow を渡すとその相手（プレイヤー自身など）に付いて動く。
// ===========================================================================
import { enemiesNear, hit, pull as pullTo } from "./combat.js";
import { P, ring, white } from "./fx.js";
import { valid, effect, hdist, knock, report } from "./util.js";

const zones = [];
export const MAX_ZONES = 40;

/**
 * 範囲を置く（engine.js の zone() と同じもの）。
 * @param src  ctx（解除・死亡で範囲も消える）かプレイヤー
 * @param loc  中心（地面の高さを渡す）
 * @param o    radius 半径（3）/ ticks 寿命（60）/ every 何 tick ごとに効くか（10）/ delay 最初に効くまで（0）/
 *             damage 1 回の素のダメージ（0 なら無し）/ hit hit() の追加オプション /
 *             effects [[id, ticks, amp], ...] 中の敵へ / pull 中心へ引き寄せる強さ / lift 上へ浮かせる強さ /
 *             height 上下の当たりの幅（2.5）/ follow 中心が付いて動くエンティティ /
 *             color 既定の見た目の色 / particle 既定の見た目のパーティクル（"aura"）/
 *             visual(dim, center, age, z) 見た目（visualEvery tick ごと、既定 2）/
 *             onPulse(enemies, z) 効く瞬間に追加でしたいこと / onEnd(z) 消える時
 * @returns z（z.stop() で消せる。z.center / z.age / z.radius を読める・書ける）
 */
export function zone(src, loc, o = {}) {
  const ctx = src && src.p && src.kind ? src : null;
  const owner = ctx ? ctx.p : src;
  if (!valid(owner)) return null;
  if (zones.length >= MAX_ZONES) {
    const old = zones.shift();
    try { old.o.onEnd?.(old); } catch (_) { }
  }
  const z = {
    owner, ctx, dim: ctx?.dim ?? owner.dimension, center: { ...loc }, radius: o.radius ?? 3,
    age: 0, o, done: false, pulses: 0,
    stop() { z.done = true; },
  };
  zones.push(z);
  return z;
}

/** 中にいる敵。 */
export function inZone(z) {
  const h = z.o.height ?? 2.5;
  return enemiesNear(z.ctx ?? z.owner, z.center, z.radius + h, z.dim).filter((e) => {
    const l = e.location;
    return hdist(l, z.center) <= z.radius && l.y >= z.center.y - h && l.y <= z.center.y + h;
  });
}

function defaultVisual(z) {
  const c = z.o.color ?? [1, 1, 1];
  const id = z.o.particle ?? "aura";
  if (z.age % 6 === 0) ring(z.dim, "dot", z.center, z.radius, Math.min(14, Math.round(z.radius * 4)), { color: c, size: 0.6, life: 0.4 }, 0.15);
  if (z.age % 4 === 0) {
    const a = Math.random() * Math.PI * 2, r = Math.random() * z.radius;
    P(z.dim, id, { x: z.center.x + Math.cos(a) * r, y: z.center.y + 0.3, z: z.center.z + Math.sin(a) * r },
      { color: white(c, 0.2), size: 1.2, life: 0.6 });
  }
}

/** 毎 tick（main から）。 */
export function tickZones() {
  for (let i = zones.length - 1; i >= 0; i--) {
    const z = zones[i];
    try {
      if (z.done || !valid(z.owner) || (z.ctx && !z.ctx.alive()) || z.age >= (z.o.ticks ?? 60)) {
        if (!z.ended) { z.ended = true; try { z.o.onEnd?.(z); } catch (e) { report("zone.onEnd", e); } }
        zones.splice(i, 1);
        continue;
      }
      if (z.o.follow) {
        if (!valid(z.o.follow)) { z.done = true; continue; }
        const l = z.o.follow.location;
        z.center = { x: l.x, y: l.y, z: l.z };
      }
      const ve = z.o.visualEvery ?? 2;
      if (z.age % ve === 0) {
        if (z.o.visual) z.o.visual(z.dim, z.center, z.age, z);
        else defaultVisual(z);
      }
      const every = Math.max(1, z.o.every ?? 10);
      if (z.age >= (z.o.delay ?? 0) && (z.age - (z.o.delay ?? 0)) % every === 0) {
        z.pulses++;
        const foes = inZone(z);
        for (const e of foes) {
          if (z.o.damage) hit(z.ctx ?? z.owner, e, z.o.damage, { quiet: z.o.quietHits ?? true, ...(z.o.hit ?? {}) });
          for (const [id, t, amp] of z.o.effects ?? []) effect(e, id, t, amp ?? 0);
          if (z.o.pull) pullTo(e, z.center, z.o.pull, 0.04);
          if (z.o.lift) knock(e, 0, 0, 0, z.o.lift);
        }
        z.o.onPulse?.(foes, z);
      }
      z.age++;
    } catch (e) {
      report("zones", e);
      zones.splice(i, 1);
    }
  }
}

export function activeZones() { return zones.length; }

export function clearZones(ownerId) {
  for (const z of zones) if (z.owner?.id === ownerId) z.done = true;
}
