// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 近接武器（data/weapons.js の kind = "melee"）
//
//  * 生きたゾンビへの近接はバニラの entityHurt → gore.js → ここの setMeleeResolver の関数で hit を作る
//    （ダメージ・dtype・weight・gore_power・sever_bias・改造は武器の表から。バニラの minecraft:damage は使わない）。
//    死体を叩いた時も gore.js が同じ関数を呼ぶ（info.corpse）。gib は gibs.js が蹴り、ここで武器の重さに直す。
//  * 振り（その tick に一度だけ）: 攻撃の速さ attack_speed より速く振ると弱くなる（0.2 + 0.8 × 溜まり²）、
//    スタミナ stamina_cost をバス "stamina_cost" で出す（息切れなら遅く・弱く = COMBAT_TUNING.exhausted）、
//    ANIM_SETS の振りを combo_window_ticks の間で 1 → 2 → 3 と回す（animation.nr.p.<名前>）、風切り音・振りの軌跡。
//  * 溜め攻撃: 右クリック長押し（itemStartUse → itemReleaseUse / itemStopUse）で heavy.charge_ticks 以上溜めて離すと
//    重い一撃（ANIM_SETS の heavy、スタミナ × stamina_mult、hit.heavy）。軌道で当たる数と角度が変わる
//    （spin は周り全部、横振りの両手武器は 3 体まで、突き・振り下ろしは 1 体）。スキル power_attack なら
//    スニーク＋攻撃も強撃。よろめいた敵への強撃は処刑（finishers.js、スキル finisher）。
//  * 壁を叩く（entityHitBlock）: 金属・木の音、火花、耐久 per_wall。
//  * 届く距離 reach より遠い一撃はかすり傷（0.6 倍・ゴアは半分）。落ちながらの一撃は会心。
//  * 鎧の部位には alt_dtype の方が通るならそちらで叩く（消防斧の背・釘バットの釘）。
// ===========================================================================
import { world } from "@minecraft/server";
import { COMBAT_TUNING } from "../data/settings.js";
import { setMeleeResolver, applyHit, armorOf, goreSpec } from "../gore/gore.js";
import { kick, GIB_ID } from "../gore/gibs.js";
import { isCorpse } from "../gore/death.js";
import { locate, groupOf } from "../gore/hitloc.js";
import { particle, sound, playerAnim, PRIO } from "../core/fx.js";
import { get as getSetting } from "../core/settings.js";
import { valid, now, norm, add, sub, scale, dot, len, clamp, isZombie, isPlayer, safe, later, getProp } from "../core/util.js";
import {
  heldInfo, weaponOf, animSetOf, sfxOf, rarityOf, isExhausted, spendStamina, skillEff, hasSkill, noise, eyeRay, rightOf,
  publishWeaponState,
} from "./common.js";
import { wear, brokenMult, DUR } from "./durability.js";
import { effectiveMods, modDamageMult } from "./mods.js";
import { canStomp, stompHit, canExecute, decapHit } from "./finishers.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */

/** @type {any} */
const CT = COMBAT_TUNING ?? {};
/** 溜め攻撃の調整。 */
export const HEAVY = Object.freeze({ charge_ticks: 10, damage_mult: 1.6, stamina_mult: 1.8, gore_add: 0.2, ...(CT.heavy ?? {}) });
const EXH = { attack_speed_mult: 0.6, damage_mult: 0.7, ...(CT.exhausted ?? {}) };
const COMBO_WINDOW = Number(CT.combo_window_ticks) || 12;
const MELEE_NOISE = Number(CT.noise?.melee) || 4;
/** 重さ → 吹き飛びの勢い。 */
const WEIGHT_POWER = { light: 0.75, medium: 1.0, heavy: 1.35 };
/** 重さ → gib を蹴る強さ。 */
const KICK_POWER = { light: 0.8, medium: 1.1, heavy: 1.6 };

/**
 * その tick の振り（同じ tick の entityHitEntity / entityHurt / onHitEntity で一度だけ）。
 * @typedef {object} Swing
 * @property {number} tick
 * @property {any} w
 * @property {number} combo     振りの番号（0..）
 * @property {number} spam      速すぎる振りの倍率 0.2..1
 * @property {boolean} exhausted
 * @property {boolean} heavy    スニークの強撃（power_attack）
 * @property {string} anim
 */
/** @type {Map<string, {last: number, combo: number, end: number, swing?: Swing, wall: number}>} */
const swings = new Map();
/** @type {Map<string, number>} スニークを押した tick */
const sneakSince = new Map();

/** @param {Player} p */
function rec(p) {
  let r = swings.get(p.id);
  if (!r) { r = { last: -1e9, combo: -1, end: -1e9, wall: -1e9 }; swings.set(p.id, r); }
  return r;
}

/** 攻撃の間隔（tick）。 @param {any} w @param {boolean} exhausted */
export function cooldownTicks(w, exhausted) {
  const sp = Math.max(0.1, Number(w?.attack_speed) || 1) * (exhausted ? Number(EXH.attack_speed_mult) || 0.6 : 1);
  return 20 / sp;
}

/** スニークの強撃か（スキル power_attack・スニークを heavy_charge_ticks 以上）。 @param {Player} p */
function powerAttack(p) {
  if (!p.isSneaking) return false;
  const eff = skillEff(p, "power_attack");
  if (!eff) return false;
  const since = sneakSince.get(p.id);
  const need = Number(eff.heavy_charge_ticks) || HEAVY.charge_ticks;
  return since === undefined ? true : now() - since >= need;
}

/** 振りの軌跡の向き。 @param {string} arcName @param {Vector3} dir */
function arcDir(arcName, dir) {
  const r = rightOf(dir);
  switch (arcName) {
    case "r2l": return scale(r, -1);
    case "l2r": return r;
    case "down": return norm(add(scale(dir, 0.3), { x: 0, y: -1, z: 0 }));
    case "up": return norm(add(scale(dir, 0.3), { x: 0, y: 1, z: 0 }));
    case "thrust": return dir;
    default: return r;
  }
}

/** 振りの音・軌跡（改造の色）。 @param {Player} p @param {any} w @param {any} def ANIM_SETS の振り @param {boolean} heavy */
function swingFx(p, w, def, heavy) {
  const sfx = sfxOf(w);
  const { eye, dir } = eyeRay(p);
  sound(p.dimension, heavy ? sfx.heavy ?? "nr.w.swing_heavy" : sfx.swing ?? "nr.w.swing_light", add(eye, dir), { volume: heavy ? 1.0 : 0.8 });
  const h = heldInfo(p);
  const mods = h ? effectiveMods(w, h.item) : {};
  const first = Object.keys(mods)[0];
  /** @type {any} */
  const MB = { fire: [1, 0.55, 0.2], shock: [0.55, 0.8, 1], bleed: [0.75, 0.05, 0.05], toxic: [0.45, 0.9, 0.2], uv: [0.65, 0.35, 1], impact: [0.95, 0.93, 0.86] };
  const c = MB[first] ?? [0.92, 0.92, 0.95];
  const a = arcDir(String(def?.[4] ?? "r2l"), dir);
  particle(p.dimension, "swing_trail", add(eye, scale(dir, 1.1)), { dx: a.x, dy: a.y, dz: a.z, cr: c[0], cg: c[1], cb: c[2] }, PRIO.LOW);
}

/**
 * その tick の振り（無ければ作る: スタミナ・モーション・音・軌跡・音の知らせ）。
 * @param {Player} p @param {any} w @returns {Swing}
 */
export function swingOf(p, w) {
  const t = now();
  const r = rec(p);
  if (r.swing && r.swing.tick === t && r.swing.w === w) return r.swing;
  const exhausted = isExhausted(p);
  const progress = clamp((t - r.last) / cooldownTicks(w, exhausted), 0, 1);
  const spam = 0.2 + 0.8 * progress * progress;
  const set = animSetOf(w);
  const list = Array.isArray(set.swings) && set.swings.length ? set.swings : [[`${w.anim_set}_1`, 3, 5, 10, "r2l"]];
  const heavy = powerAttack(p);
  const combo = t - r.end <= COMBO_WINDOW ? (r.combo + 1) % list.length : 0;
  const def = heavy && set.heavy ? set.heavy : list[combo];
  spendStamina(p, (Number(w.stamina_cost) || 0) * (heavy ? Number(HEAVY.stamina_mult) || 1.8 : 1), heavy ? "power_attack" : "melee");
  playerAnim(p, String(def[0]));
  swingFx(p, w, def, heavy);
  noise(p.dimension, p.location, MELEE_NOISE, "melee", p);
  r.last = t;
  if (!heavy) r.combo = combo;
  r.end = t + (Number(def[3]) || 10);
  /** @type {Swing} */
  const s = { tick: t, w, combo, spam, exhausted, heavy, anim: String(def[0]) };
  r.swing = s;
  return s;
}

// ---------------------------------------------------------------------------
//  hit を作る
// ---------------------------------------------------------------------------
/** 鎧に通りやすい方の種別（dtype か alt_dtype）。 @param {any} w @param {Entity} z @param {string} part */
function chooseDtype(w, z, part) {
  const main = String(w.dtype ?? "blunt");
  const alt = w.alt_dtype ? String(w.alt_dtype) : "";
  if (!alt) return main;
  const g = goreSpec(z);
  const armoredPart = (g.armored ?? []).includes(part) && armorOf(z) > 0;
  if (!armoredPart) return main;
  /** @type {any} */
  const A = CT.armor ?? {};
  const m = (/** @type {string} */ d) => Number(A[`${d}_mult`] ?? (d === "blunt" ? 0.7 : 0.3));
  return m(alt) > m(main) ? alt : main;
}

/**
 * 武器の一撃の hit（解決・溜め攻撃の共通）。
 * @param {Player} p @param {Entity} z @param {any} w @param {any} item 手の ItemStack
 * @param {{spam?: number, exhausted?: boolean, heavy?: boolean, corpse?: boolean, dir?: Vector3}} o
 * @returns {any}
 */
export function weaponHit(p, z, w, item, o) {
  const mods = effectiveMods(w, item);
  const R = rarityOf(w, item);
  const spam = o.spam ?? 1;
  let dmg = (Number(w.damage) || 1) * (Number(R.stat_mult) || 1) * spam * (o.exhausted ? Number(EXH.damage_mult) || 0.7 : 1)
    * brokenMult(item) * modDamageMult(mods, z);
  const { eye, dir: view } = eyeRay(p);
  const dir = o.dir ?? view;
  const ph = locate(z, { attacker: p, dir });
  const group = groupOf(ph.part);
  const dtype = chooseDtype(w, z, ph.part);
  let gp = (Number(w.gore_power) || 0.5) * (0.55 + 0.45 * spam);
  // スキル
  if (dtype === "slash") gp += Number(skillEff(p, "dismember_mastery")?.slash_gore_add) || 0;
  if (dtype === "blunt" && group === "head") gp += Number(skillEff(p, "skull_crusher")?.blunt_head_crush_add) || 0;
  const hh = skillEff(p, "headhunter");
  /** @type {any} */
  let outcome;
  if (hh && group === "head") {
    dmg *= 1 + (Number(hh.headshot_mult_add) || 0);
    if (dtype === "slash" && getProp(z, "nr:state", "normal") === "stagger" && Number(hh.stagger_decap_add) > 0) outcome = { head: ["severed", Number(hh.stagger_decap_add)] };
  }
  if (o.heavy) {
    const pa = skillEff(p, "power_attack");
    if (pa) {
      dmg *= (Number(pa.heavy_damage_mult) || HEAVY.damage_mult) / (Number(HEAVY.damage_mult) || 1.6);
      gp += (Number(pa.heavy_gore_add) || 0) - (Number(HEAVY.gore_add) || 0);
    }
  }
  // 届かない一撃はかすり傷
  const reach = Number(w.reach) || 3;
  const d = len(sub(ph.point, eye));
  if (d > reach + 0.75) { dmg *= 0.6; gp *= 0.5; }
  let crit;
  try { if (!o.corpse && !p.isOnGround && p.getVelocity().y < -0.08) crit = true; } catch { crit = undefined; }
  const power = (WEIGHT_POWER[/** @type {"light" | "medium" | "heavy"} */ (w.weight)] ?? 1) * (0.7 + 0.3 * spam) * (o.heavy ? 1.2 : 1);
  /** @type {any} */
  const hit = {
    attacker: p, source: "melee", dtype, weight: w.weight ?? "medium", damage: dmg, weapon: w, mods, power,
    gorePower: clamp(gp, 0, 1.3), dir, crit, heavy: o.heavy || undefined, outcome,
  };
  const ib = Number(w.special?.innate_bleed_chance) || 0;
  if (ib > 0) hit._innateBleed = ib;
  return hit;
}

/**
 * 近接の解決（gore.js の setMeleeResolver）。NR の近接武器でなければ undefined（既定の解決）。
 * @param {Player} p @param {Entity} z @param {{damage: number, cause: string, corpse: boolean}} info
 */
export function resolveMelee(p, z, info) {
  const h = heldInfo(p);
  const w = h?.w;
  if (!h || !w || w.kind !== "melee") return undefined;
  const sw = swingOf(p, w);
  if (!info.corpse && canStomp(p, z)) return stompHit(p, z);
  const hit = weaponHit(p, z, w, h.item, { spam: sw.spam, exhausted: sw.exhausted, heavy: sw.heavy, corpse: info.corpse });
  if (sw.heavy && !info.corpse && canExecute(p, z)) return decapHit(p, z, w, { damage: hit.damage, mods: hit.mods });
  return hit;
}
setMeleeResolver((p, z, info) => resolveMelee(p, z, info));

// ---------------------------------------------------------------------------
//  振り（どの相手でも）・gib を蹴る・壁を叩く
// ---------------------------------------------------------------------------
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const p = ev.damagingEntity;
  if (!isPlayer(p) || !valid(p)) return;
  const pl = /** @type {Player} */ (p);
  const h = heldInfo(pl);
  const w = h?.w?.kind === "melee" ? h.w : undefined;
  const sw = w ? swingOf(pl, w) : undefined;
  const target = ev.hitEntity;
  if (target?.typeId === GIB_ID && valid(target)) {
    const kp = (KICK_POWER[/** @type {"light" | "medium" | "heavy"} */ (w?.weight)] ?? 0.9) * (sw ? 0.6 + 0.4 * sw.spam : 1) * (sw?.heavy ? 1.3 : 1);
    safe("kick", () => kick(target, pl.getViewDirection(), kp));
  }
});

world.afterEvents.entityHitBlock.subscribe((ev) => {
  const p = ev.damagingEntity;
  if (!isPlayer(p) || !valid(p)) return;
  const pl = /** @type {Player} */ (p);
  const h = heldInfo(pl);
  const w = h?.w;
  if (!w || w.kind !== "melee") return;
  const r = rec(pl);
  const t = now();
  if (t - r.wall < 8) return;
  r.wall = t;
  swingOf(pl, w);
  const b = ev.hitBlock;
  const at = { x: b.location.x + 0.5, y: b.location.y + 0.5, z: b.location.z + 0.5 };
  const { dir } = eyeRay(pl);
  const face = add(at, scale(dir, -0.5));
  sound(pl.dimension, sfxOf(w).wall ?? "nr.w.hit_metal", face, { volume: 0.9 });
  particle(pl.dimension, "hit_spark", face, { dx: -dir.x, dy: -dir.y, dz: -dir.z }, PRIO.NORMAL);
  wear(pl, Number(DUR.per_wall) || 2, "wall");
});

world.afterEvents.playerButtonInput.subscribe((ev) => {
  if (ev.button !== "Sneak") return;
  if (ev.newButtonState === "Pressed") sneakSince.set(ev.player.id, now());
  else sneakSince.delete(ev.player.id);
});

// ---------------------------------------------------------------------------
//  溜め攻撃（右クリック長押し → 離す）
// ---------------------------------------------------------------------------
/** @type {Map<string, {start: number, typeId: string, slot: number}>} */
const charges = new Map();

world.afterEvents.itemStartUse.subscribe((ev) => {
  const w = weaponOf(ev.itemStack?.typeId);
  if (w?.kind !== "melee" || !valid(ev.source)) return;
  charges.set(ev.source.id, { start: now(), typeId: w.id, slot: ev.source.selectedSlotIndex });
});
/** @param {Player} p */
function release(p) {
  const c = charges.get(p.id);
  if (!c) return;
  charges.delete(p.id);
  const h = heldInfo(p);
  if (!h?.w || h.item?.typeId !== c.typeId || h.index !== c.slot) return;
  const need = Number(skillEff(p, "power_attack")?.heavy_charge_ticks) || Number(HEAVY.charge_ticks) || 10;
  if (now() - c.start < need) return;
  heavyAttack(p, h.w);
}
world.afterEvents.itemReleaseUse.subscribe((ev) => { if (valid(ev.source)) release(ev.source); });
world.afterEvents.itemStopUse.subscribe((ev) => { if (valid(ev.source)) release(ev.source); });
world.afterEvents.itemCompleteUse.subscribe((ev) => { if (valid(ev.source)) release(ev.source); });

/** 軌道 → [当たる数, 角度の cos]。 @param {string} arcName @param {any} w */
function arcReach(arcName, w) {
  if (arcName === "spin") return [6, -1];
  if (arcName === "thrust") return [1, Math.cos(22 * Math.PI / 180)];
  if (arcName === "down" || arcName === "up") return [1, Math.cos(32 * Math.PI / 180)];
  return [Number(w.hands) === 2 ? 3 : 2, Math.cos(62 * Math.PI / 180)];
}

/**
 * 溜め攻撃（右クリックを離した時）。モーション・音・スタミナは今、当たりは振りの当たる tick に。
 * @param {Player} p @param {any} w
 */
export function heavyAttack(p, w) {
  const set = animSetOf(w);
  const hv = Array.isArray(set.heavy) ? set.heavy : [`${w.anim_set}_heavy`, 10, 13, 22, "r2l"];
  spendStamina(p, (Number(w.stamina_cost) || 0) * (Number(HEAVY.stamina_mult) || 1.8), "heavy");
  playerAnim(p, String(hv[0]));
  swingFx(p, w, hv, true);
  const r = rec(p);
  r.last = now(); r.end = now() + (Number(hv[3]) || 20);
  const delay = clamp((Number(hv[2]) || 13) - (Number(hv[1]) || 10), 1, 8);
  later(delay, () => strike(p, w, String(hv[4] ?? "r2l")));
}

/**
 * 溜め攻撃の当たり: 届く距離・角度の中の相手（近い順）に重い一撃。当たった数を返す。
 * @param {Player} p @param {any} w @param {string} arcName
 */
export function strike(p, w, arcName) {
  if (!valid(p)) return 0;
  const h = heldInfo(p);
  if (!h?.item || h.item.typeId !== w.id) return 0;
  const { eye, dir } = eyeRay(p);
  const reach = Number(w.reach) || 3;
  const [maxN, cosMin] = arcReach(arcName, w);
  /** @type {Entity[]} */
  let near = [];
  try { near = p.dimension.getEntities({ location: eye, maxDistance: reach + 1.6, excludeTypes: ["minecraft:item", "minecraft:xp_orb", "minecraft:arrow"] }); } catch { near = []; }
  /** @type {{e: Entity, d: number}[]} */
  const cand = [];
  for (const e of near) {
    if (!valid(e) || e.id === p.id || e.typeId.startsWith("nr:proj_")) continue;
    if (isPlayer(e) && getSetting("friendly_fire") !== true) continue;
    const c = add(e.location, { x: 0, y: e.typeId === GIB_ID ? 0.15 : 0.9, z: 0 });
    const v = sub(c, eye);
    const d = len(v);
    if (d - 0.45 > reach) continue;
    if (cosMin > -1 && d > 0.3 && dot(scale(v, 1 / d), dir) < cosMin) continue;
    cand.push({ e, d });
  }
  cand.sort((a, b) => a.d - b.d);
  let n = 0;
  for (const { e } of cand.slice(0, maxN)) {
    if (!valid(e)) continue;
    if (isZombie(e)) {
      const radial = arcName === "spin" ? norm({ x: e.location.x - p.location.x, y: 0, z: e.location.z - p.location.z }, dir) : dir;
      let hit = weaponHit(p, e, w, h.item, { heavy: true, dir: radial, corpse: isCorpse(e) });
      if (!isCorpse(e) && canExecute(p, e)) hit = decapHit(p, e, w, { damage: hit.damage, mods: hit.mods });
      else hit.heavy = true;
      safe("heavy.applyHit", () => applyHit(e, hit));
      n++;
    } else if (e.typeId === GIB_ID) {
      safe("heavy.kick", () => kick(e, dir, 1.8));
    } else {
      safe("heavy.damage", () => e.applyDamage(Math.max(1, (Number(w.damage) || 4) * 0.55 * (Number(HEAVY.damage_mult) || 1.6)), { cause: /** @type {any} */ ("entityAttack"), damagingEntity: p }));
      n++;
    }
  }
  if (n > 0) wear(p, (Number(DUR.per_hit) || 1) * 2, "heavy");
  noise(p.dimension, p.location, MELEE_NOISE * 1.5, "melee", p);
  publishWeaponState(p);
  return n;
}

world.afterEvents.playerLeave.subscribe((ev) => { swings.delete(ev.playerId); charges.delete(ev.playerId); sneakSince.delete(ev.playerId); });

/** スキル power_attack を持っていて今スニークの強撃になるか（HUD・テスト用）。 @param {Player} p */
export function isPowerAttackReady(p) { return hasSkill(p, "power_attack") && powerAttack(p); }
