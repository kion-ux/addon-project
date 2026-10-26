// ===========================================================================
//  NIGHT RUNNER: 感染都市 — ゾンビの「本当の体力」（DESIGN §4）
//
//  * minecraft:health は大きなプール（1000）。本当の体力は動的プロパティ nr:hp（最大は nr:hp_max）。
//    初回に spec の hp × 難易度（DIFFICULTY.zombie_hp_mult、人数で強くする設定なら × 人数分）で初期化。
//  * entityHurt の後は必ず resetPool() でプールを満タンに戻す（バニラでは死なない）。
//  * スクリプトが自分で applyDamage する時は hurtVanilla()（= reserve + applyDamage）を使う。
//    entityHurt 側は consumeReservation() で「予約済み」を見分けて二重に数えない。
//  * ダメージの計算・死亡は gore/gore.js の applyHit が一か所でやる（ここは数を持つだけ）。
// ===========================================================================
import { world, EntityDamageCause } from "@minecraft/server";
import * as ZOM_D from "../data/zombies.js";
import { get, difficulty } from "./settings.js";
import { valid, zkey, isZombie, clamp, now, dpNum } from "./util.js";

/** @typedef {import("@minecraft/server").Entity} Entity */

export const HP_KEY = "nr:hp";
export const HP_MAX_KEY = "nr:hp_max";

// ---- spec の引き当て ------------------------------------------------------------------------
/** @type {any} */
const ZD = ZOM_D;
/** @type {Map<string, any>} */
const BY_KEY = new Map();
{
  const list = ZD.ZOMBIES;
  const arr = Array.isArray(list) ? list : list && typeof list === "object" ? Object.values(list) : [];
  arr.forEach((z, i) => { if (z && z.key) BY_KEY.set(String(z.key), { ...z, ztype: Number.isInteger(z.ztype) ? z.ztype : i }); });
}

/** ゾンビの spec（鍵・ID・エンティティのどれでも）。無ければ undefined。@param {string | Entity | undefined} k */
export function zombieSpec(k) {
  if (!k) return undefined;
  const key = typeof k === "string" ? (k.startsWith("nr:z_") ? k.slice(5) : k) : zkey(k.typeId);
  return BY_KEY.get(key);
}
/** 種類番号（ZOMBIES の並び。不明は 63 = 汎用）。@param {string | Entity | undefined} k */
export function ztypeOf(k) {
  const s = zombieSpec(k);
  if (s) return s.ztype;
  return 63;
}
/** 全種類の鍵。 */
export function zombieKeys() { return [...BY_KEY.keys()]; }

// ---- 体力 -----------------------------------------------------------------------------------
/** 種類の基本体力 × 難易度 × 人数。@param {string} key */
export function baseHp(key) {
  const s = zombieSpec(key);
  const hp = Number(s?.hp) > 0 ? Number(s.hp) : 20;
  const d = difficulty();
  let mult = Number(d.zombie_hp_mult) > 0 ? Number(d.zombie_hp_mult) : 1;
  if (get("difficulty_scaling")) {
    let n = 1;
    try { n = Math.max(1, world.getAllPlayers().length); } catch { n = 1; }
    mult *= 1 + Math.max(0, Number(d.player_scale_per_extra) || 0) * (n - 1);
  }
  return Math.max(1, Math.round(hp * mult * 2) / 2);
}

/**
 * nr:hp が無ければ入れる。新しく入れたら true。
 * @param {Entity} z @param {number} [hp] 明示する時（ボスの段階など）
 */
export function initHp(z, hp) {
  if (!valid(z) || !isZombie(z)) return false;
  if (hp === undefined && z.getDynamicProperty(HP_KEY) !== undefined) return false;
  const max = hp ?? baseHp(zkey(z.typeId));
  z.setDynamicProperty(HP_MAX_KEY, max);
  z.setDynamicProperty(HP_KEY, max);
  return true;
}

/** 本当の体力（無ければ初期化してから）。@param {Entity} z */
export function hpOf(z) {
  if (!valid(z)) return 0;
  const v = dpNum(z, HP_KEY, NaN);
  if (Number.isFinite(v)) return v;
  initHp(z);
  return dpNum(z, HP_KEY, 0);
}
/** 最大体力。@param {Entity} z */
export function maxHpOf(z) {
  if (!valid(z)) return 1;
  const v = dpNum(z, HP_MAX_KEY, NaN);
  if (Number.isFinite(v) && v > 0) return v;
  initHp(z);
  return Math.max(1, dpNum(z, HP_MAX_KEY, 1));
}
/** 体力の割合 0..1。@param {Entity} z */
export function hpFraction(z) { return clamp(hpOf(z) / maxHpOf(z), 0, 1); }

/** 体力を書く（0..最大に丸める）。書いた値を返す。@param {Entity} z @param {number} v */
export function setHp(z, v) {
  if (!valid(z)) return 0;
  const max = maxHpOf(z);
  const n = clamp(Number.isFinite(v) ? v : 0, 0, max);
  z.setDynamicProperty(HP_KEY, n);
  return n;
}
/** 体力を足す（負で減る）。新しい値を返す。@param {Entity} z @param {number} d */
export function addHp(z, d) { return setHp(z, hpOf(z) + d); }

/** 最大体力を変える（今の割合を保つ）。@param {Entity} z @param {number} max */
export function setMaxHp(z, max) {
  if (!valid(z) || !(max > 0)) return;
  const f = hpFraction(z);
  z.setDynamicProperty(HP_MAX_KEY, max);
  z.setDynamicProperty(HP_KEY, max * f);
}

/** minecraft:health のプールを満タンへ（バニラの死を防ぐ）。@param {Entity} z */
export function resetPool(z) {
  if (!valid(z)) return;
  try { z.getComponent("minecraft:health")?.resetToMaxValue(); } catch { /* 死体・無効 */ }
}

// ---- 予約（スクリプトが入れるバニラのダメージを entityHurt で二重に数えない） -------------------
/** @type {Map<string, {tick: number, cause: string}[]>} */
const reservations = new Map();

/**
 * これから applyDamage する分を予約する（entityHurt で 1 回ぶん読み飛ばされる）。
 * @param {Entity} z @param {string} [cause] EntityDamageCause の値
 */
export function reserve(z, cause = EntityDamageCause.override) {
  const list = reservations.get(z.id) ?? [];
  list.push({ tick: now(), cause: String(cause) });
  reservations.set(z.id, list);
}

/**
 * entityHurt から: この被弾が予約済みなら消費して true。
 * @param {Entity} z @param {string} cause
 */
export function consumeReservation(z, cause) {
  const list = reservations.get(z.id);
  if (!list) return false;
  const t = now();
  const live = list.filter((r) => t - r.tick <= 3);
  const i = live.findIndex((r) => r.cause === String(cause));
  if (i >= 0) live.splice(i, 1);
  if (live.length) reservations.set(z.id, live); else reservations.delete(z.id);
  return i >= 0;
}

/** 予約を取り消す（applyDamage が通らなかった時）。@param {Entity} z @param {string} cause */
function unreserve(z, cause) {
  const list = reservations.get(z.id);
  if (!list) return;
  const i = list.findIndex((r) => r.cause === String(cause));
  if (i >= 0) list.splice(i, 1);
  if (!list.length) reservations.delete(z.id);
}

/**
 * バニラの被弾（赤い点滅・のけぞり・押し返し）だけを起こす。本当の体力は減らさない
 * （予約して applyDamage → entityHurt では読み飛ばす → プールは戻す）。通ったら true。
 * @param {Entity} z @param {number} [amount] @param {Entity} [attacker] @param {string} [cause]
 */
export function hurtVanilla(z, amount = 1, attacker, cause = EntityDamageCause.override) {
  if (!valid(z)) return false;
  reserve(z, cause);
  let ok = false;
  try {
    /** @type {{cause: any, damagingEntity?: Entity}} */
    const o = { cause };
    if (valid(attacker)) o.damagingEntity = attacker;
    ok = z.applyDamage(Math.max(0.01, amount), o);
  } catch { ok = false; }
  if (!ok) unreserve(z, cause);
  resetPool(z);
  return ok;
}

/** 消えたエンティティの予約を捨てる。@param {string} id */
export function forget(id) { reservations.delete(id); }

world.afterEvents.entityRemove.subscribe((ev) => { if (ev.typeId.startsWith("nr:z_")) reservations.delete(ev.removedEntityId); });
