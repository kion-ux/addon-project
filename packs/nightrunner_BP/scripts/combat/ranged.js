// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 飛び道具（銃 = ヒットスキャン、弓・クロスボウ = nr:proj_*）
//
//  銃（kind = "gun"）:
//  * 使う（itemUse / itemStartUse。同じ tick は 1 回）で撃つ。full_auto は押している間（itemStopUse /
//    itemReleaseUse まで）attack_speed の間隔で撃ち続ける。スニーク＋使うで手でリロード、弾倉が空なら自動。
//  * 弾倉は ItemStack の動的プロパティ nr:mag（重ねられない武器だけ。初めて見た銃は満タン）。弾は持ち物の
//    w.ammo（special.ammo_per_shot 個で 1 発）。リロードは reload_ticks（散弾銃の reload_per_shell は 1 発ずつ、
//    撃てば中断）。持ち替えたら取りやめ。
//  * 1 発ごとに pellets 本のレイ（spread 度の円錐。スニークで狭く・動くと広く）を getEntitiesFromRay /
//    getBlockFromRay で飛ばし、1 本ずつ当たり箱で部位を決める（hitloc.rayPart。体の箱を外れた弾は抜ける）。
//    同じゾンビの同じ部位に当たった弾はまとめて 1 回の applyHit（source "hitscan"）。overpenetrate は貫通。
//    散弾は close_range_blocks 以内なら gore_power + close_gore_bonus、頭に 2 発以上で頭が弾ける。
//    gib は弾で蹴られる、ゾンビ以外の生き物はバニラのダメージ。
//  * 演出: muzzle_flash・bullet_tracer・shell_casing・impact_dust、発射音・空撃ち・リロード・コッキング、
//    発射の反動のモーション（ANIM_SETS の fire / cycle / reload）と揺れ、バス "noise" {pos, radius}。
//  * 水平二連（special.both_barrels_on_heavy）: 2 発込めてスニーク＋使うと 2 発同時（ペレット 2 倍）。
//    猟銃（special.scope_fov）: 手に持ってスニークを SCOPE_TICKS 続けるとスコープ（camera.setFov）。覗いている間の
//    使うは撃つ（リロードにしない）。スコープの銃の手でのリロードは、スニークと同時に使う（覗く前）。
//  弓・クロスボウ（kind = "bow" / "crossbow"）:
//  * 弓は itemStartUse で引き、itemReleaseUse で放つ（charge_ticks で満タン。スキル marksman で速く）。
//    クロスボウは装填（reload_ticks、ボルトを 1 本）→ 使うと撃つ。
//  * nr:proj_* を spawnEntity し、minecraft:projectile の owner と shoot（無ければ applyImpulse）で飛ばす。
//    当たりは projectileHitEntity の着弾点と向き → 部位（体の箱をさかのぼるレイ）→ applyHit（source
//    "projectile"）。BP の impact_damage の entityHurt は setProjectileResolver で読み飛ばす（二重に数えない）。
//  * 刺さった矢・ボルト・投げナイフは拾える（pickup_chance。ゾンビに刺さった物はその場に落ちる）。
//  すり減りは 1 発ごとに durability.wear()。
// ===========================================================================
import { world, system, EntityDamageCause, ItemStack } from "@minecraft/server";
import { PROJECTILE_BY_ID } from "../data/weapons.js";
import { COMBAT_TUNING } from "../data/settings.js";
import { applyHit, setProjectileResolver, goreSpec } from "../gore/gore.js";
import { rayPart, locate } from "../gore/hitloc.js";
import { kick, GIB_ID } from "../gore/gibs.js";
import { isCorpse } from "../gore/death.js";
import { particle, sound, playerSound, playerAnim, shake, PRIO } from "../core/fx.js";
import { get as getSetting } from "../core/settings.js";
import { valid, now, norm, add, sub, scale, dist, len, lenXZ, clamp, chance, isZombie, isPlayer, safe, later, despawn, warnOnce } from "../core/util.js";
import {
  heldInfo, weaponOf, animSetOf, sfxOf, rarityOf, countItem, takeItem, giveItem, heldDp, setHeldDp, skillEff, spendStamina,
  noise, eyeRay, handPos, rightOf, spreadDir, trackProjectile, projMeta, projectiles, reloading, publishWeaponState, onPlayerTick,
  onWorldTick, notify,
} from "./common.js";
import { wear, brokenMult } from "./durability.js";
import { effectiveMods, modDamageMult } from "./mods.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */

/** @type {any} */
const CT = COMBAT_TUNING ?? {};
/** @type {Record<string, any>} */
const PBY = /** @type {any} */ (PROJECTILE_BY_ID) ?? {};
const GUN_NOISE = Number(CT.noise?.gun_default) || 32;
const WEIGHT_POWER = { light: 0.8, medium: 1.0, heavy: 1.3 };
/** 反動の揺れ（強さ）。 */
const RECOIL = { pistol: 0.18, revolver: 0.35, shotgun: 0.6, rifle: 0.5, smg: 0.1 };
const SKIP_TYPES = new Set(["minecraft:item", "minecraft:xp_orb", "minecraft:arrow", "minecraft:snowball"]);

/** @type {Map<string, {lastShot: number, useTick: number, auto?: {typeId: string, slot: number}, zoom?: boolean, aim?: number}>} */
const guns = new Map();
/** スニークをこの tick 続けるとスコープを覗く。 */
const SCOPE_TICKS = 6;
/** @param {Player} p */
function gs(p) {
  let s = guns.get(p.id);
  if (!s) { s = { lastShot: -1e9, useTick: -1 }; guns.set(p.id, s); }
  return s;
}

// ---------------------------------------------------------------------------
//  弾倉
// ---------------------------------------------------------------------------
/** 弾倉の中（無ければ満タン）。 @param {import("./common.js").Held | undefined} h @param {any} w */
export function magOf(h, w) {
  const v = heldDp(h, "nr:mag");
  const max = Math.max(1, Number(w?.mag) || 1);
  return typeof v === "number" && Number.isFinite(v) ? clamp(Math.round(v), 0, max) : max;
}
/** @param {import("./common.js").Held | undefined} h @param {number} n */
function setMag(h, n) { setHeldDp(h, "nr:mag", Math.max(0, Math.round(n))); }
/** 1 発に要る弾の数。 @param {any} w */
function ammoPerShot(w) { return Math.max(1, Number(w?.special?.ammo_per_shot) || 1); }

// ---------------------------------------------------------------------------
//  入力（使う・離す）
// ---------------------------------------------------------------------------
/** @param {Player} p @param {any} item @param {"use" | "start"} how */
function useStart(p, item, how) {
  const w = weaponOf(item?.typeId);
  if (!w || !valid(p)) return;
  if (w.kind === "gun") gunTrigger(p, w, how);
  else if (w.kind === "crossbow") crossbowTrigger(p, w);
  else if (w.kind === "bow") {
    if (how === "start") bowDraw(p, w);
    else {
      // 使用時間の無い弓（itemStartUse が来ない）: 次の tick に 7 割の引きで放つ
      const t = now();
      system.run(() => { if (valid(p) && !draws.has(p.id) && lastStart.get(p.id) !== t) fireProjectile(p, w, 0.75, false); });
    }
  }
}
/** @type {Map<string, number>} */
const lastStart = new Map();
world.afterEvents.itemUse.subscribe((ev) => useStart(ev.source, ev.itemStack, "use"));
world.afterEvents.itemStartUse.subscribe((ev) => {
  if (valid(ev.source)) lastStart.set(ev.source.id, now());
  useStart(ev.source, ev.itemStack, "start");
});
/** @param {Player} p @param {any} item */
function useEnd(p, item) {
  if (!valid(p)) return;
  const st = guns.get(p.id);
  if (st) st.auto = undefined;
  const w = weaponOf(item?.typeId) ?? weaponOf(draws.get(p.id)?.typeId);
  if (w?.kind === "bow") bowRelease(p, w);
}
world.afterEvents.itemReleaseUse.subscribe((ev) => useEnd(ev.source, ev.itemStack));
world.afterEvents.itemStopUse.subscribe((ev) => useEnd(ev.source, ev.itemStack));
world.afterEvents.itemCompleteUse.subscribe((ev) => useEnd(ev.source, ev.itemStack));

// ---------------------------------------------------------------------------
//  銃
// ---------------------------------------------------------------------------
/** @param {Player} p @param {any} w @param {"use" | "start"} how */
function gunTrigger(p, w, how) {
  const h = heldInfo(p);
  if (h?.item?.typeId !== w.id) return;
  const st = gs(p);
  const t = now();
  if (st.useTick === t) { if (how === "start" && w.special?.full_auto) st.auto = { typeId: w.id, slot: h.index }; return; }
  st.useTick = t;
  if (p.isSneaking && !st.zoom) {
    // 水平二連の「強撃」: 2 発込めてあれば 2 発同時。それ以外のスニーク＋使うは手でリロード
    if (w.special?.both_barrels_on_heavy && !reloading.has(p.id) && magOf(h, w) >= 2) { fireGun(p, w, 2); return; }
    startReload(p, w);
    return;
  }
  const r = reloading.get(p.id);
  if (r) {
    if (r.perShell && magOf(h, w) > 0) cancelReload(p);
    else return;
  }
  if (w.special?.full_auto && how === "start") st.auto = { typeId: w.id, slot: h.index };
  fireGun(p, w);
}

/**
 * 1 発撃つ（間隔・弾倉を見る）。barrels = 2 は水平二連の 2 発同時。撃てたら true。
 * @param {Player} p @param {any} w @param {number} [barrels]
 */
export function fireGun(p, w, barrels = 1) {
  const h = heldInfo(p);
  if (!h?.item || h.item.typeId !== w.id) return false;
  const st = gs(p);
  const t = now();
  const cd = Math.max(1, Math.round(20 / Math.max(0.1, Number(w.attack_speed) || 1)));
  if (t - st.lastShot < cd) return false;
  const sfx = sfxOf(w);
  const mag = magOf(h, w);
  if (mag <= 0) {
    st.lastShot = t;
    sound(p.dimension, sfx.empty ?? "nr.w.empty_click", p.location, { volume: 0.8 });
    st.auto = undefined;
    startReload(p, w);
    return false;
  }
  st.lastShot = t;
  const shots = clamp(Math.floor(barrels), 1, mag);
  setMag(h, mag - shots);
  const { eye, dir } = eyeRay(p);
  let moving = false;
  try { moving = lenXZ(p.getVelocity()) > 0.08; } catch { moving = false; }
  const broken = brokenMult(h.item) < 1;
  const steady = p.isSneaking && shots === 1;
  const spread = (Number(w.spread) || 0) * (steady ? 0.6 : 1) * (moving ? 1.35 : 1) * (broken ? 2 : 1) * (shots > 1 ? 1.15 : 1);
  const res = hitscan(p, w, h.item, eye, dir, spread, shots);
  // 演出
  const set = animSetOf(w);
  const muzzle = handPos(p, dir, 0.95);
  const big = Number(w.pellets) > 1 ? 1.6 : w.cls === "rifle" ? 1.3 : w.cls === "smg" ? 0.8 : 1;
  particle(p.dimension, w.fx?.muzzle ?? "muzzle_flash", muzzle, { dx: dir.x, dy: dir.y, dz: dir.z, size: big }, PRIO.HIGH);
  for (const tr of res.tracers.slice(0, 2)) particle(p.dimension, w.fx?.tracer ?? "bullet_tracer", muzzle, { dx: tr.d.x, dy: tr.d.y, dz: tr.d.z, speed: 1 }, PRIO.NORMAL);
  for (const at of res.impacts.slice(0, 3)) particle(p.dimension, w.fx?.impact ?? "impact_dust", at, undefined, PRIO.LOW);
  if (w.fx?.shell) { const r = rightOf(dir); particle(p.dimension, w.fx.shell, add(muzzle, scale(dir, -0.4)), { dx: r.x, dy: 0.6, dz: r.z }, PRIO.LOW); }
  sound(p.dimension, sfx.fire ?? "nr.w.pistol", muzzle, { volume: shots > 1 ? 4 : 3, pitch: (0.95 + Math.random() * 0.1) * (shots > 1 ? 0.85 : 1) });
  playerAnim(p, String(set.fire ?? "pistol_fire"));
  const rc = (RECOIL[/** @type {"pistol"} */ (w.cls)] ?? 0.2) * (shots > 1 ? 1.6 : 1);
  if (w.cls !== "smg" || mag % 3 === 0) shake(p, rc, 0.12, "rotational");
  if (set.cycle && mag - shots > 0) {
    later(5, () => {
      if (!valid(p) || heldInfo(p)?.item?.typeId !== w.id) return;
      playerAnim(p, String(set.cycle));
      if (sfx.cycle) sound(p.dimension, sfx.cycle, p.location, { volume: 0.9 });
    });
  }
  noise(p.dimension, p.location, (Number(w.noise) || GUN_NOISE) * (shots > 1 ? 1.25 : 1), "gun", p);
  wear(p, shots, "shot");
  publishWeaponState(p);
  return true;
}

/**
 * @typedef {object} PelletPart
 * @property {string} part
 * @property {number} sub
 * @property {Vector3} point
 * @property {Vector3} dir
 * @property {number} n      当たった弾の数
 * @property {number} dmg    合計
 * @property {number} dist
 */
/**
 * ヒットスキャン（pellets 本 × shots 発）。当たったゾンビへ部位ごとにまとめて applyHit。
 * @param {Player} p @param {any} w @param {any} item @param {Vector3} eye @param {Vector3} dir @param {number} spread
 * @param {number} [shots] 同時に撃つ数（水平二連の 2 発同時）
 * @returns {{tracers: {d: Vector3, len: number}[], impacts: Vector3[], hits: any[], pellets: {entity?: string, part?: string}[]}}
 */
export function hitscan(p, w, item, eye, dir, spread, shots = 1) {
  const dim = p.dimension;
  const range = Number(w.range) || 32;
  const perShot = Math.max(1, Math.round(Number(w.pellets) || 1));
  const pellets = perShot * Math.max(1, Math.floor(shots));
  const pierce = Math.max(0, Number(w.special?.overpenetrate) || 0);
  const R = rarityOf(w, item);
  const per = (Number(w.damage) || 1) * (Number(R.stat_mult) || 1) * brokenMult(item);
  const close = Number(w.special?.close_range_blocks) || 0;
  const ff = getSetting("friendly_fire") === true;
  /** @type {Map<string, {z: Entity, parts: Map<string, PelletPart>}>} */
  const agg = new Map();
  /** @type {{d: Vector3, len: number}[]} */
  const tracers = [];
  /** @type {Vector3[]} */
  const impacts = [];
  /** @type {{entity?: string, part?: string}[]} */
  const log = [];
  // ゾンビは当たり箱（collision_box）ではなく体の箱（hitloc の SHAPES）でレイを当てる: 頭は当たり箱より
  // 上に出ていることがあるので。射線の近くのゾンビだけを候補にする
  const cands = zombiesAlong(p, eye, dir, range, spread);
  for (let i = 0; i < pellets; i++) {
    const d = spreadDir(dir, spread);
    // 壁（ここで弾は止まる）
    let wallT = range;
    /** @type {Vector3 | undefined} */
    let wallAt;
    try {
      const bh = dim.getBlockFromRay(eye, d, { maxDistance: range, includeLiquidBlocks: false, includePassableBlocks: false });
      if (bh) {
        wallAt = { x: bh.block.location.x + bh.faceLocation.x, y: bh.block.location.y + bh.faceLocation.y, z: bh.block.location.z + bh.faceLocation.z };
        wallT = dist(eye, wallAt);
      }
    } catch { /* レイが読めない */ }
    /** @type {{e: Entity, t: number, ph?: any}[]} */
    const along = [];
    for (const z of cands) {
      if (!valid(z)) continue;
      const ph = rayPart(z, eye, d, { maxDist: wallT });
      if (ph && ph.how === "ray" && Number.isFinite(ph.t) && Number(ph.t) <= wallT) along.push({ e: z, t: Number(ph.t), ph });
    }
    /** @type {import("@minecraft/server").EntityRaycastHit[]} */
    let ents = [];
    try { ents = dim.getEntitiesFromRay(eye, d, { maxDistance: Math.max(0.1, wallT), excludeFamilies: ["nr_zombie"] }); } catch { ents = []; }
    for (const rh of ents) {
      const e = rh.entity;
      if (!valid(e) || e.id === p.id || SKIP_TYPES.has(e.typeId) || e.typeId.startsWith("nr:proj_") || isZombie(e)) continue;
      along.push({ e, t: rh.distance });
    }
    along.sort((a, b) => a.t - b.t);
    let left = 1 + pierce;
    let mul = 1;
    let end = wallT;
    let stopped = false;
    /** @type {{entity?: string, part?: string}} */
    const one = {};
    for (const { e, t, ph } of along) {
      const fall = falloff(w, t, range, close);
      if (ph) {
        let a = agg.get(e.id);
        if (!a) { a = { z: e, parts: new Map() }; agg.set(e.id, a); }
        const k = ph.part;
        const cur = a.parts.get(k);
        if (cur) { cur.n++; cur.dmg += per * fall * mul; }
        else a.parts.set(k, { part: k, sub: ph.sub, point: ph.point, dir: d, n: 1, dmg: per * fall * mul, dist: t });
        if (!one.entity) { one.entity = e.id; one.part = k; }
        left--; mul *= 0.6;
        if (left <= 0) { end = t; stopped = true; break; }
      } else if (e.typeId === GIB_ID) {
        safe("shot.kick", () => kick(e, d, 0.7));
        end = t; stopped = true; break;
      } else if (isPlayer(e)) {
        if (!ff) continue;
        safe("shot.ff", () => e.applyDamage(Math.max(0.5, per * fall * mul * (Number(CT.friendly_fire_mult) || 0.5)), { cause: EntityDamageCause.entityAttack, damagingEntity: p }));
        end = t; stopped = true; break;
      } else {
        safe("shot.mob", () => e.applyDamage(Math.max(0.5, per * fall * mul), { cause: EntityDamageCause.entityAttack, damagingEntity: p }));
        if (!one.entity) one.entity = e.id;
        left--; mul *= 0.6;
        if (left <= 0) { end = t; stopped = true; break; }
      }
    }
    if (!stopped && wallAt) impacts.push(wallAt);
    tracers.push({ d, len: end });
    log.push(one);
  }
  // まとめて当てる（頭から、ダメージの大きい順）
  /** @type {any[]} */
  const hits = [];
  const mods = effectiveMods(w, item);
  for (const { z, parts } of agg.values()) {
    const list = [...parts.values()].sort((a, b) => (b.part === "head" ? 1 : 0) - (a.part === "head" ? 1 : 0) || b.dmg - a.dmg);
    const near = close > 0 && dist(eye, z.location) <= close + 0.6;
    for (const pp of list) {
      if (!valid(z)) break;
      let gp = (Number(w.gore_power) || 0.5) + (near ? Number(w.special?.close_gore_bonus) || 0 : 0) + 0.05 * (pp.n - 1);
      const crush = near && perShot > 1 && pp.part === "head" && pp.n >= 2;
      const ms = skillEff(p, "marksman");
      let dmg = pp.dmg * modDamageMult(mods, z);
      if (pp.part === "head" && ms) dmg *= 1 + (Number(ms.ranged_headshot_add) || 0);
      const hit = {
        attacker: p, source: "hitscan", dtype: String(w.dtype ?? "pierce"), weight: String(w.weight ?? "medium"), damage: dmg,
        weapon: w, mods, part: pp.part, sub: pp.sub, point: pp.point, dir: pp.dir,
        power: (WEIGHT_POWER[/** @type {"light"} */ (w.weight)] ?? 1) * (0.85 + 0.12 * Math.min(pp.n, 6)),
        gorePower: clamp(gp, 0, 1.3), crit: false, outcome: crush ? { head: "crushed" } : undefined,
      };
      const r = safe("hitscan.applyHit", () => applyHit(z, hit));
      if (r) hits.push(r);
    }
  }
  return { tracers, impacts, hits, pellets: log };
}

/**
 * 射線の近くのゾンビ（生きている物も死体も）。spread の円錐の広がりと体の大きさの分だけ余裕を見る。
 * @param {Player} p @param {Vector3} eye @param {Vector3} dir @param {number} range @param {number} spread
 * @returns {Entity[]}
 */
function zombiesAlong(p, eye, dir, range, spread) {
  /** @type {Entity[]} */
  let zs = [];
  try { zs = p.dimension.getEntities({ location: eye, maxDistance: range + 2, families: ["nr_zombie"] }); } catch { zs = []; }
  const tan = Math.tan(((Number(spread) || 0) + 2) * Math.PI / 180);
  return zs.filter((z) => {
    if (!valid(z)) return false;
    const c = add(z.location, { x: 0, y: 1.0, z: 0 });
    const v = sub(c, eye);
    const t = v.x * dir.x + v.y * dir.y + v.z * dir.z;
    if (t < -1.5) return false;
    const perp = len(sub(v, scale(dir, t)));
    return perp <= 1.8 + Math.max(0, t) * tan;
  });
}

/** 距離の減衰（散弾は近距離の外で大きく、他は射程の後半で少し）。 @param {any} w @param {number} d @param {number} range @param {number} close */
function falloff(w, d, range, close) {
  if (Number(w.pellets) > 1) {
    if (d <= close) return 1;
    return clamp(1 - 0.6 * (d - close) / Math.max(1, range - close), 0.35, 1);
  }
  if (d <= range * 0.5) return 1;
  return clamp(1 - 0.3 * (d - range * 0.5) / Math.max(1, range * 0.5), 0.6, 1);
}

// ---------------------------------------------------------------------------
//  リロード
// ---------------------------------------------------------------------------
/**
 * リロードを始める（弾倉が満タン・弾が無い・もうリロード中なら false）。
 * @param {Player} p @param {any} w
 */
export function startReload(p, w) {
  if (reloading.has(p.id)) return false;
  const h = heldInfo(p);
  if (!h?.item || h.item.typeId !== w.id) return false;
  const max = Math.max(1, Number(w.mag) || 1);
  if (magOf(h, w) >= max) return false;
  const sfx = sfxOf(w);
  if (!w.ammo || countItem(p, w.ammo) < ammoPerShot(w)) {
    sound(p.dimension, sfx.empty ?? "nr.w.empty_click", p.location, { volume: 0.7, pitch: 0.8 });
    notify(p, "§7弾が無い", 30);
    return false;
  }
  const mult = Number(skillEff(p, "marksman")?.reload_mult) || 1;
  const ticks = Math.max(4, Math.round((Number(w.reload_ticks) || 30) * mult));
  const t = now();
  reloading.set(p.id, { until: t + ticks, slot: h.index, typeId: w.id, perShell: !!w.special?.reload_per_shell, next: t + ticks });
  const set = animSetOf(w);
  playerAnim(p, String(set.reload ?? "pistol_reload"));
  sound(p.dimension, (w.kind === "crossbow" ? sfx.draw : sfx.reload) ?? "nr.w.reload", p.location, { volume: 0.9 });
  publishWeaponState(p, true);
  return true;
}
/** @param {Player} p */
export function cancelReload(p) {
  if (!reloading.delete(p.id)) return;
  publishWeaponState(p, true);
}
/** リロード中か。 @param {Player} p */
export function isReloading(p) { return reloading.has(p.id); }

onPlayerTick("reload", 1, (p, t) => {
  const r = reloading.get(p.id);
  if (!r) return;
  const h = heldInfo(p);
  if (!h?.item || h.index !== r.slot || h.item.typeId !== r.typeId) { cancelReload(p); return; }
  if (t < r.next) return;
  const w = h.w;
  const max = Math.max(1, Number(w.mag) || 1);
  const per = ammoPerShot(w);
  const mag = magOf(h, w);
  const sfx = sfxOf(w);
  if (r.perShell) {
    if (mag < max && takeItem(p, w.ammo, per) >= per) {
      setMag(h, mag + 1);
      sound(p.dimension, sfx.reload ?? "nr.w.reload_shell", p.location, { volume: 0.8 });
    }
    const h2 = heldInfo(p);
    if (magOf(h2, w) < max && countItem(p, w.ammo) >= per) {
      const step = Math.max(4, Math.round((Number(w.reload_ticks) || 12) * (Number(skillEff(p, "marksman")?.reload_mult) || 1)));
      r.next = t + step; r.until = r.next;
      publishWeaponState(p);
      return;
    }
  } else {
    const need = max - mag;
    const can = Math.min(need, Math.floor(countItem(p, w.ammo) / per));
    if (can > 0) { takeItem(p, w.ammo, can * per); setMag(heldInfo(p), mag + can); }
  }
  reloading.delete(p.id);
  if (sfx.cycle && w.kind === "gun") sound(p.dimension, sfx.cycle, p.location, { volume: 0.8 });
  publishWeaponState(p, true);
});

// 押している間の連射（full_auto）
onPlayerTick("fullAuto", 1, (p) => {
  const st = guns.get(p.id);
  if (!st?.auto) return;
  const h = heldInfo(p);
  if (!h?.w || h.item?.typeId !== st.auto.typeId || h.index !== st.auto.slot) { st.auto = undefined; return; }
  fireGun(p, h.w);
});

// スコープ（special.scope_fov の銃を手に持ってスニーク）。外す時は setFov() を引数なしで（既定の視野へ）
onPlayerTick("scope", 2, (p) => {
  const st = guns.get(p.id);
  if (!p.isSneaking && !st?.zoom && !st?.aim) return;
  const h = heldInfo(p);
  const fov = Number(h?.w?.special?.scope_fov) || 0;
  const aiming = fov > 0 && p.isSneaking && !reloading.has(p.id);
  const g = gs(p);
  g.aim = aiming ? (g.aim ?? 0) + 2 : 0;
  const want = aiming && g.aim >= SCOPE_TICKS;
  if (want && !g.zoom) {
    safe("scope.in", () => p.camera.setFov({ fov: clamp(fov, 30, 110), easeOptions: { easeTime: 0.15 } }));
    g.zoom = true;
  } else if (!want && g.zoom) {
    safe("scope.out", () => p.camera.setFov());
    g.zoom = false;
  }
});
/** スコープを覗いているか（HUD・テスト用）。 @param {Player} p */
export function isScoped(p) { return !!guns.get(p.id)?.zoom; }

// ---------------------------------------------------------------------------
//  弓・クロスボウ
// ---------------------------------------------------------------------------
/** @type {Map<string, {start: number, typeId: string, slot: number}>} */
const draws = new Map();

/** @param {Player} p @param {any} w */
function bowDraw(p, w) {
  if (w.ammo && countItem(p, w.ammo) <= 0) {
    playerSound(p, "nr.w.empty_click", { volume: 0.6 });
    notify(p, "§7矢が無い", 30);
    return;
  }
  draws.set(p.id, { start: now(), typeId: w.id, slot: p.selectedSlotIndex });
  const set = animSetOf(w);
  playerAnim(p, String(set.draw ?? "bow_draw"));
  sound(p.dimension, sfxOf(w).draw ?? "nr.w.bow_draw", p.location, { volume: 0.8 });
}
/** @param {Player} p @param {any} w */
function bowRelease(p, w) {
  const d = draws.get(p.id);
  if (!d) return;
  draws.delete(p.id);
  const h = heldInfo(p);
  if (h?.item?.typeId !== d.typeId || h.index !== d.slot) return;
  const ms = skillEff(p, "marksman");
  const need = Math.max(1, (Number(w.charge_ticks) || 20) / (Number(ms?.draw_speed_mult) || 1));
  const charge = clamp((now() - d.start) / need, 0, 1);
  if (charge < 0.15) return;
  fireProjectile(p, w, charge, false);
}
/** 弓が引かれている割合（HUD・テスト用）。 @param {Player} p @param {any} w */
export function drawFraction(p, w) {
  const d = draws.get(p.id);
  if (!d) return 0;
  return clamp((now() - d.start) / Math.max(1, Number(w?.charge_ticks) || 20), 0, 1);
}

/** @param {Player} p @param {any} w */
function crossbowTrigger(p, w) {
  const h = heldInfo(p);
  if (h?.item?.typeId !== w.id) return;
  const st = gs(p);
  const t = now();
  if (st.useTick === t) return;
  st.useTick = t;
  if (reloading.has(p.id)) return;
  if (magOf(h, w) > 0) {
    const cd = Math.max(1, Math.round(20 / Math.max(0.1, Number(w.attack_speed) || 1)));
    if (t - st.lastShot < cd) return;
    st.lastShot = t;
    setMag(h, 0);
    fireProjectile(p, w, 1, true);
  } else startReload(p, w);
}

/**
 * 弾（nr:proj_*）を撃つ。fromMag なら持ち物の弾を使わない（クロスボウの装填済み）。撃った弾を返す。
 * @param {Player} p @param {any} w @param {number} charge 0..1 @param {boolean} fromMag
 * @returns {Entity | undefined}
 */
export function fireProjectile(p, w, charge, fromMag) {
  const h = heldInfo(p);
  if (!h?.item || h.item.typeId !== w.id) return undefined;
  if (!fromMag && w.ammo && takeItem(p, w.ammo, 1) < 1) {
    playerSound(p, "nr.w.empty_click", { volume: 0.6 });
    return undefined;
  }
  const pd = PBY[w.projectile] ?? {};
  const { eye, dir } = eyeRay(p);
  const d = spreadDir(dir, (Number(w.spread) || 0) * (1.6 - charge));
  const speed = (Number(pd.speed) || 3) * (0.35 + 0.65 * charge);
  const e = launch(p, String(w.projectile), add(eye, scale(d, 0.9)), scale(d, speed));
  if (!e) return undefined;
  const R = rarityOf(w, h.item);
  trackProjectile(e, {
    kind: String(pd.key ?? "arrow"), w, shooter: p, power: charge, born: now(), dim: p.dimension, crit: charge >= 0.999,
    damage: (Number(w.damage) || 1) * (Number(R.stat_mult) || 1) * brokenMult(h.item) * (0.25 + 0.75 * charge * charge),
    mods: effectiveMods(w, h.item), extra: { pierce: true, e, pickup: pd.pickup ?? undefined, pickupChance: Number(pd.pickup_chance) || 0 },
  });
  const set = animSetOf(w);
  playerAnim(p, String(set.release ?? set.fire ?? "bow_release"));
  sound(p.dimension, sfxOf(w).fire ?? "nr.w.bow_release", p.location, { volume: 1 });
  spendStamina(p, (Number(w.stamina_cost) || 0) * (0.5 + 0.5 * charge), w.kind);
  noise(p.dimension, p.location, Number(w.noise) || 4, w.kind, p);
  wear(p, 1, "shot");
  publishWeaponState(p);
  return e;
}

/**
 * 弾のエンティティを出して飛ばす（owner と shoot。無ければ applyImpulse）。
 * @param {Player} p @param {string} id @param {Vector3} at @param {Vector3} vel @returns {Entity | undefined}
 */
export function launch(p, id, at, vel) {
  let e;
  try { e = p.dimension.spawnEntity(id, at); } catch (err) { warnOnce(`launch:${id}`, "弾を出せない", id, err); return undefined; }
  try {
    const pc = /** @type {any} */ (e.getComponent("minecraft:projectile"));
    if (pc) { pc.owner = p; pc.shoot(vel, { uncertainty: 0 }); }
    else e.applyImpulse(vel);
  } catch { safe("launch.impulse", () => e.applyImpulse(vel)); }
  return e;
}

// ---------------------------------------------------------------------------
//  弾が当たった（矢・ボルト・投げナイフ・手裏剣 = extra.pierce）
// ---------------------------------------------------------------------------
/** @type {Map<string, number>} 控えの弾で当てたゾンビ → tick（弾が先に消えても entityHurt を読み飛ばす） */
const projHitAt = new Map();
setProjectileResolver((p, z, info) => {
  if (projMeta(info.projectile)) return false;
  if (!info.projectile && now() - (projHitAt.get(z.id) ?? -99) <= 1) return false;
  return undefined;
});

/**
 * 刺さる弾の当たり（projectileHitEntity から。テストから直接呼んでもよい）。applyHit の結果を返す。
 * @param {Entity} proj @param {Entity} target @param {Vector3} point @param {Vector3} hitVector
 */
export function resolveProjectileHit(proj, target, point, hitVector) {
  const meta = projMeta(proj);
  if (!meta || !meta.extra?.pierce || meta.hit) return undefined;
  meta.hit = true;
  const dir = norm(hitVector);
  /** @type {any} */
  let res;
  if (isZombie(target) && valid(target)) {
    const back = sub(point, scale(dir, 1.6));
    const ph = rayPart(target, back, dir, { maxDist: 4 }) ?? locate(target, { point, dir });
    const w = meta.w;
    let dmg = meta.damage * modDamageMult(meta.mods, target);
    const shooter = valid(meta.shooter) ? meta.shooter : undefined;
    if (ph.part === "head") {
      const hm = Number(w.special?.headshot_mult) || 0;
      if (hm > 0) dmg *= hm / Math.max(1, Number(goreSpec(target).head_mult ?? 2));
      const ms = shooter ? skillEff(shooter, "marksman") : undefined;
      if (ms) dmg *= 1 + (Number(ms.ranged_headshot_add) || 0);
    }
    /** @type {any} */
    const hit = {
      attacker: shooter, source: "projectile", dtype: String(w.dtype ?? "pierce"), weight: String(w.weight ?? "medium"), damage: dmg,
      weapon: w, mods: meta.mods, part: ph.part, sub: ph.sub, point: ph.point, dir,
      power: 0.6 + 0.6 * meta.power, gorePower: clamp((Number(w.gore_power) || 0.5) * (0.6 + 0.4 * meta.power), 0, 1.3),
      crit: meta.crit ? true : false,
    };
    const ib = Number(w.special?.innate_bleed_chance) || 0;
    if (ib > 0) hit._innateBleed = ib;
    res = safe("proj.applyHit", () => applyHit(target, hit));
    if (meta.kind === "throwing_knife" || meta.kind === "throwing_star") sound(target.dimension, "nr.w.knife_stick", point, { volume: 0.8 });
    // ボルトは死体を飛ばす（壁に縫い付けるように）
    if (res?.killed && w.special?.pin_to_wall) safe("pin", () => target.applyImpulse(scale(dir, 0.6)));
  }
  // 拾える物はその場に落とす
  const ex = meta.extra;
  if (ex.pickup && chance(ex.pickupChance)) {
    const at = valid(target) ? add(target.location, { x: 0, y: 0.3, z: 0 }) : point;
    if (meta.dim) dropItem(meta.dim, ex.pickup, at);
  }
  if (valid(target)) projHitAt.set(target.id, now());
  if (projHitAt.size > 64) { const k = projHitAt.keys().next().value; if (k !== undefined) projHitAt.delete(k); }
  // 消すのは次の tick（同じ tick の entityHurt が弾を見て読み飛ばせるように）
  safe("proj.stop", () => proj.clearVelocity());
  system.run(() => despawn(proj));
  return res;
}

/** 拾える物を落とす。 @param {import("@minecraft/server").Dimension} dim @param {string} id @param {Vector3} at */
function dropItem(dim, id, at) { safe("dropItem", () => dim.spawnItem(new ItemStack(id, 1), at)); }

world.afterEvents.projectileHitEntity.subscribe((ev) => {
  const meta = projMeta(ev.projectile);
  if (!meta?.extra?.pierce) return;
  let target;
  try { target = ev.getEntityHit()?.entity; } catch { target = undefined; }
  if (!target || !valid(target)) return;
  if (target.typeId === GIB_ID) return;           // gibs.js が蹴る
  if (!isZombie(target)) { meta.hit = true; return; }  // 他の生き物は BP の impact_damage
  resolveProjectileHit(ev.projectile, target, ev.location, ev.hitVector);
});

// 飛んでいる刺さる弾: 次の 1 tick の道筋を体の箱（hitloc）で調べる。頭が当たり箱（collision_box）より上に
// 出ている種類でも、頭を狙った矢は頭に当たる（当たり箱に先に当たれば projectileHitEntity が解く）
onWorldTick("arrows", 1, () => {
  for (const meta of projectiles.values()) {
    if (!meta.extra?.pierce || meta.hit) continue;
    const e = meta.extra.e;
    if (!valid(e)) continue;
    let v;
    try { v = e.getVelocity(); } catch { continue; }
    const sp = len(v);
    if (sp < 0.05) continue;
    const pos = e.location;
    const d = scale(v, 1 / sp);
    /** @type {Entity[]} */
    let zs = [];
    try { zs = e.dimension.getEntities({ location: pos, maxDistance: sp + 2.5, families: ["nr_zombie"] }); } catch { zs = []; }
    /** @type {{z: Entity, ph: any} | undefined} */
    let best;
    for (const z of zs) {
      if (!valid(z)) continue;
      const ph = rayPart(z, pos, d, { maxDist: sp + 0.25 });
      if (ph && ph.how === "ray" && Number(ph.t) <= sp + 0.25 && (!best || Number(ph.t) < Number(best.ph.t))) best = { z, ph };
    }
    if (!best) continue;
    try {
      const bh = e.dimension.getBlockFromRay(pos, d, { maxDistance: Math.max(0.05, Number(best.ph.t)), includeLiquidBlocks: false, includePassableBlocks: false });
      if (bh) continue;                                      // 壁が先
    } catch { /* レイが読めない */ }
    resolveProjectileHit(e, best.z, best.ph.point, d);
  }
});

// 地面・壁に刺さった物: 近くを通れば拾う（確率は刺さった時に決める）
/** @type {Map<string, {e: Entity, id: string, until: number}>} */
const stuck = new Map();
world.afterEvents.projectileHitBlock.subscribe((ev) => {
  const meta = projMeta(ev.projectile);
  if (!meta?.extra?.pierce || meta.hit) return;
  meta.hit = true;
  const ex = meta.extra;
  if (ex.pickup && chance(ex.pickupChance)) stuck.set(ev.projectile.id, { e: ev.projectile, id: ex.pickup, until: now() + 1200 });
  if (meta.kind === "throwing_knife" || meta.kind === "throwing_star") sound(ev.dimension, "nr.w.knife_stick", ev.location, { volume: 0.7, pitch: 1.2 });
  else particle(ev.dimension, "impact_dust", ev.location, undefined, PRIO.LOW);
});
onWorldTick("pickup", 10, (t) => {
  if (!stuck.size) return;
  for (const [k, s] of [...stuck]) {
    if (!valid(s.e) || t >= s.until) { stuck.delete(k); continue; }
    /** @type {Entity[]} */
    let near = [];
    try { near = s.e.dimension.getEntities({ location: s.e.location, maxDistance: 2.4, type: "minecraft:player" }); } catch { near = []; }
    const p = near.find((x) => valid(x));
    if (!p) continue;
    stuck.delete(k);
    giveItem(/** @type {Player} */ (p), s.id, 1);
    playerSound(/** @type {Player} */ (p), "nr.ui.click", { volume: 0.6, pitch: 1.4 });
    despawn(s.e);
  }
});

world.afterEvents.playerLeave.subscribe((ev) => { guns.delete(ev.playerId); draws.delete(ev.playerId); lastStart.delete(ev.playerId); });
