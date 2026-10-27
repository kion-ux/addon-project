// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 投げ物（kind = "throwable"）
//
//  * 投げ方: 右クリック長押しで振りかぶり（itemStartUse、throw_wind）→ 離すと投げる（itemReleaseUse /
//    itemStopUse。charge_ticks で満タン）。使用時間の無い物（itemStartUse が来ない）は使った次の tick に投げる。
//    手の束から 1 つ減る。スタミナ stamina_cost、スキル lethal_throw で遠く・強く。
//  * 投げナイフ・手裏剣: 刺さる弾（ranged.js の resolveProjectileHit で部位 → applyHit）。拾える
//    （ゾンビに刺さればその場に落ち、壁・地面に刺されば近くを通ると拾う）。手裏剣は固有の出血。
//  * 火炎瓶: 当たる（地面・壁・ゾンビ）と割れて fire_radius の火の海（puddle_ticks）。中のゾンビは applyHit
//    （dtype fire）と火の持続ダメージ（burn_ticks・burn_dps、nr:burn を sets_burn まで → 炭化は gore.js）。
//    中のプレイヤーは燃える。バス "fire_zone"。
//  * パイプ爆弾: fuse_ticks で爆発（跳ねてもよい）。導火線の間はビープで誘う（noise）。爆風は blast_radius、
//    距離で falloff だけ弱まる。近いほど多くの部位に効き（parts）、手足が千切れ・胴が裂ける（gore.js の blast 表）。
//    死体も吹き飛ぶ・千切れる、gib は飛ぶ、プレイヤーにもダメージと揺れ。
//  * 爆竹: 落ちると lure_ticks の間はじけ続け、lure_radius の noise を出す（バス "lure" も）。
//  * UV 発煙筒: 落ちると uv_ticks の間 uv_radius の UV の光。夜の種類（UV に弱い）は焼かれ（dtype uv）、
//    初めて浴びた時に怯む。中のプレイヤーは免疫が戻る（バス "immunity_restore"）。バス "uv_zone"。
// ===========================================================================
import { world, system, EntityDamageCause } from "@minecraft/server";
import { PROJECTILE_BY_ID } from "../data/weapons.js";
import { COMBAT_TUNING } from "../data/settings.js";
import { applyHit, stagger } from "../gore/gore.js";
import { PARTS, partCenter } from "../gore/hitloc.js";
import { GIB_ID } from "../gore/gibs.js";
import { isCorpse } from "../gore/death.js";
import { emit } from "../core/bus.js";
import { particle, sound, playerAnim, zombieAnim, shake, PRIO } from "../core/fx.js";
import { valid, now, norm, add, sub, scale, dist, clamp, isZombie, isPlayer, safe, despawn } from "../core/util.js";
import {
  CEV, heldInfo, weaponOf, animSetOf, sfxOf, rarityOf, skillEff, spendStamina, noise, eyeRay, trackProjectile, projMeta,
  onWorldTick, publishWeaponState,
} from "./common.js";
import { launch } from "./ranged.js";
import { startDot, uvVulnerable } from "./mods.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */

/** @type {any} */
const CT = COMBAT_TUNING ?? {};
/** @type {Record<string, any>} */
const PBY = /** @type {any} */ (PROJECTILE_BY_ID) ?? {};
const EXPLOSION_NOISE = Number(CT.noise?.explosion) || 64;
/** 放物線で投げる物（少し上へ）。 */
const LOBBED = new Set(["molotov", "pipe_bomb", "firecracker", "uv_flare"]);

// ---------------------------------------------------------------------------
//  投げる
// ---------------------------------------------------------------------------
/** @type {Map<string, {start: number, typeId: string, slot: number}>} */
const winds = new Map();
/** @type {Map<string, number>} */
const lastStart = new Map();
/** @type {Map<string, number>} */
const lastThrow = new Map();

world.afterEvents.itemStartUse.subscribe((ev) => {
  const p = ev.source;
  const w = weaponOf(ev.itemStack?.typeId);
  if (!valid(p)) return;
  lastStart.set(p.id, now());
  if (w?.kind !== "throwable") return;
  winds.set(p.id, { start: now(), typeId: w.id, slot: p.selectedSlotIndex });
  playerAnim(p, String(animSetOf(w).wind ?? "throw_wind"));
});
world.afterEvents.itemUse.subscribe((ev) => {
  const p = ev.source;
  const w = weaponOf(ev.itemStack?.typeId);
  if (w?.kind !== "throwable" || !valid(p)) return;
  const t = now();
  // 使用時間の無い物（itemStartUse が来ない）は次の tick に満タンで投げる
  system.run(() => { if (valid(p) && !winds.has(p.id) && lastStart.get(p.id) !== t) throwHeld(p, w, 1); });
});
/** @param {Player} p */
function release(p) {
  const wd = winds.get(p.id);
  if (!wd) return;
  winds.delete(p.id);
  const w = weaponOf(wd.typeId);
  const h = heldInfo(p);
  if (!w || h?.item?.typeId !== wd.typeId || h.index !== wd.slot) return;
  const need = Math.max(1, Number(w.charge_ticks) || 1);
  throwHeld(p, w, clamp((now() - wd.start) / need, 0.3, 1));
}
world.afterEvents.itemReleaseUse.subscribe((ev) => { if (valid(ev.source)) release(ev.source); });
world.afterEvents.itemStopUse.subscribe((ev) => { if (valid(ev.source)) release(ev.source); });
world.afterEvents.itemCompleteUse.subscribe((ev) => { if (valid(ev.source)) release(ev.source); });

/**
 * 手の投げ物を 1 つ投げる（間隔 attack_speed）。投げた弾を返す。
 * @param {Player} p @param {any} w @param {number} charge 0..1 @returns {Entity | undefined}
 */
export function throwHeld(p, w, charge) {
  const h = heldInfo(p);
  if (!h?.item || h.item.typeId !== w.id) return undefined;
  const t = now();
  const cd = Math.max(2, Math.round(20 / Math.max(0.1, Number(w.attack_speed) || 1)));
  if (t - (lastThrow.get(p.id) ?? -1e9) < cd) return undefined;
  lastThrow.set(p.id, t);
  const pd = PBY[w.projectile] ?? {};
  const lt = skillEff(p, "lethal_throw");
  const { eye, dir } = eyeRay(p);
  const lob = LOBBED.has(String(pd.key));
  const d = lob ? norm(add(dir, { x: 0, y: 0.12, z: 0 })) : dir;
  const speed = (Number(pd.speed) || 1.2) * (0.45 + 0.55 * charge) * (Number(lt?.throw_range_mult) || 1);
  const e = launch(p, String(w.projectile), add(eye, scale(d, 0.8)), scale(d, speed));
  if (!e) return undefined;
  // 束から 1 つ
  try {
    if (h.item.amount > 1) { h.item.amount -= 1; h.slot.setItem(h.item); } else h.slot.setItem(undefined);
  } catch { /* 減らせない */ }
  const R = rarityOf(w, h.item);
  const pierce = pd.on_hit === "stick" && (w.dtype === "pierce" || w.dtype === "slash");
  trackProjectile(e, {
    kind: String(pd.key ?? w.key), w, shooter: p, power: charge, born: t, dim: p.dimension, crit: charge >= 0.999,
    damage: (Number(w.damage) || 1) * (Number(R.stat_mult) || 1) * (0.5 + 0.5 * charge) * (Number(lt?.throw_damage_mult) || 1),
    mods: {}, lastPos: e.location,
    extra: { pierce, e, pickup: pierce ? pd.pickup ?? w.id : undefined, pickupChance: Number(pd.pickup_chance) || 0 },
  });
  if (!pierce) flying.set(e.id, { e, kind: String(pd.key), w, owner: p, born: t, dim: p.dimension, pos: e.location, done: false });
  const set = animSetOf(w);
  playerAnim(p, String((lob ? set.lob : set.release) ?? "throw_overhand"));
  sound(p.dimension, sfxOf(w).throw ?? "nr.w.throw", p.location, { volume: 0.9 });
  spendStamina(p, Number(w.stamina_cost) || 0, "throw");
  if (Number(w.noise) > 0) noise(p.dimension, p.location, Number(w.noise) * 0.5, "throw", p);
  publishWeaponState(p);
  return e;
}

// ---------------------------------------------------------------------------
//  飛んでいる物（火炎瓶・パイプ爆弾・爆竹・UV 発煙筒）
// ---------------------------------------------------------------------------
/**
 * @typedef {object} Fly
 * @property {Entity} e
 * @property {string} kind
 * @property {any} w
 * @property {Player | undefined} owner
 * @property {number} born
 * @property {Dimension} dim
 * @property {Vector3} pos
 * @property {boolean} done
 * @property {boolean} [landed]
 */
/** @type {Map<string, Fly>} */
const flying = new Map();

/** 着いた（地面・壁・相手）。 @param {Fly} f @param {Vector3} at @param {Entity} [target] */
function land(f, at, target) {
  if (f.done) return;
  f.pos = at;
  if (f.kind === "molotov") { f.done = true; shatter(f, at, target); despawn(f.e); flying.delete(f.e.id); return; }
  if (f.kind === "firecracker" && !f.landed) { f.landed = true; startLure(f, at); return; }
  if (f.kind === "uv_flare" && !f.landed) { f.landed = true; startUv(f, at); return; }
  f.landed = true;
}

world.afterEvents.projectileHitBlock.subscribe((ev) => {
  const f = flying.get(ev.projectile?.id ?? "");
  if (f) land(f, ev.location);
});
world.afterEvents.projectileHitEntity.subscribe((ev) => {
  const f = flying.get(ev.projectile?.id ?? "");
  if (!f) return;
  let target;
  try { target = ev.getEntityHit()?.entity; } catch { target = undefined; }
  const m = projMeta(ev.projectile);
  if (m) m.hit = true;
  land(f, ev.location, target);
});

onWorldTick("throwables.fly", 1, (t) => {
  for (const [id, f] of [...flying]) {
    if (valid(f.e)) { try { f.pos = f.e.location; } catch { /* 読めない */ } }
    if (f.kind === "pipe_bomb") {
      const fuse = Number(f.w.special?.fuse_ticks) || 50;
      if ((t - f.born) % 10 === 0 && t > f.born) {
        particle(f.dim, f.w.fx?.trail ?? "fuse_spark", f.pos, undefined, PRIO.LOW);
        sound(f.dim, "nr.trap.click", f.pos, { volume: 0.7, pitch: 1.6 });
        if (f.w.special?.beeps_lure) noise(f.dim, f.pos, 16, "pipe_bomb", f.owner);
      }
      if (t - f.born >= fuse) { flying.delete(id); f.done = true; explode(f.dim, f.pos, f.w, f.owner); despawn(f.e); }
      continue;
    }
    if (!valid(f.e)) {
      // 消えた（寿命・当たって消えた）: 火炎瓶はその場で割れる、他は止まった所で始める
      if (!f.done) land(f, f.pos);
      flying.delete(id);
      continue;
    }
    // 落ちないまま時間が経った（どこかに乗った）物は始める
    if (!f.landed && t - f.born >= 30 && f.kind !== "molotov") land(f, f.pos);
    if (f.kind === "molotov" && t - f.born >= 100) land(f, f.pos);
  }
});

// ---------------------------------------------------------------------------
//  火炎瓶の火の海
// ---------------------------------------------------------------------------
/**
 * @typedef {object} Zone
 * @property {string} kind      fire / uv / lure
 * @property {Dimension} dim
 * @property {Vector3} pos
 * @property {number} r
 * @property {number} until
 * @property {any} w
 * @property {Player | undefined} owner
 * @property {Entity} [e]       追う弾（発煙筒）
 * @property {Set<string>} seen
 */
/** @type {Zone[]} */
const zones = [];

/** @param {Fly} f @param {Vector3} at @param {Entity} [target] */
function shatter(f, at, target) {
  const s = f.w.special ?? {};
  const r = Number(s.fire_radius) || 3.5;
  const until = now() + (Number(s.puddle_ticks) || 160);
  const pos = { x: at.x, y: Math.floor(at.y + 0.05), z: at.z };
  sound(f.dim, "nr.fx.glass_break", at, { volume: 1.2 });
  sound(f.dim, "nr.fx.fire_ignite", at, { volume: 1.2 });
  particle(f.dim, f.w.fx?.impact ?? "fire_burst", at, { size: r / 2 }, PRIO.HIGH);
  particle(f.dim, "ground_fire", pos, { radius: r, life: (until - now()) / 20 }, PRIO.HIGH);
  noise(f.dim, at, Number(f.w.noise) || 10, "molotov", f.owner);
  const z = { kind: "fire", dim: f.dim, pos, r, until, w: f.w, owner: f.owner, seen: new Set() };
  zones.push(z);
  emit(CEV.FIRE_ZONE, { dim: f.dim, pos, radius: r, until });
  // 直撃: その相手に火の一撃
  if (target && isZombie(target) && valid(target)) {
    applyHit(target, { attacker: f.owner, source: "fire", dtype: "fire", weight: "light", damage: (Number(f.w.damage) || 3) * 2, power: 0.5, burn: Number(s.sets_burn) || 2, noKnockback: true, crit: false, dir: norm(sub(target.location, f.owner?.location ?? at)) });
  }
  fireStep(z, true);
}

/** @param {Zone} z @param {boolean} first */
function fireStep(z, first) {
  const s = z.w.special ?? {};
  for (const e of entitiesIn(z.dim, z.pos, z.r)) {
    if (isZombie(e)) {
      if (isCorpse(e)) continue;
      startDot(e, "fire", Number(s.burn_dps) || 3, Number(s.burn_ticks) || 120, z.owner, { burn: Number(s.sets_burn) || 2 });
      if (first || !z.seen.has(e.id)) {
        z.seen.add(e.id);
        applyHit(e, { attacker: z.owner, source: "fire", dtype: "fire", weight: "light", damage: Number(z.w.damage) || 3, power: 0.3, burn: Number(s.sets_burn) || 2, noKnockback: true, crit: false, dir: norm(sub(e.location, z.pos)) });
      }
    } else if (isPlayer(e)) {
      safe("fire.player", () => e.setOnFire(3, true));
    }
  }
}

// ---------------------------------------------------------------------------
//  パイプ爆弾の爆発
// ---------------------------------------------------------------------------
/**
 * 爆発（パイプ爆弾。テスト・他のモジュールからも呼べる）。当てた相手の数を返す。
 * @param {Dimension} dim @param {Vector3} pos @param {any} w @param {Player | undefined} owner
 */
export function explode(dim, pos, w, owner) {
  const s = w?.special ?? {};
  const r = Number(s.blast_radius) || 5;
  const dmg = Number(w?.damage) || 40;
  const fo = clamp(Number(s.falloff) || 0.6, 0, 1);
  particle(dim, w?.fx?.impact ?? "explosion", pos, { size: r / 2 }, PRIO.CRITICAL);
  particle(dim, "smoke_dark", pos, { size: r / 2, life: 3 }, PRIO.NORMAL);
  particle(dim, "shockwave_ground", pos, { radius: r }, PRIO.NORMAL);
  sound(dim, "nr.fx.explosion", pos, { volume: 3, pitch: 0.9 + Math.random() * 0.15 });
  noise(dim, pos, EXPLOSION_NOISE, "explosion", owner);
  let n = 0;
  for (const e of entitiesIn(dim, pos, r * 1.8)) {
    const c = add(e.location, { x: 0, y: e.typeId === GIB_ID ? 0.1 : 0.8, z: 0 });
    const d = dist(c, pos);
    if (isPlayer(e) && d <= r * 1.8) shake(/** @type {Player} */ (e), clamp(1.4 * (1 - d / (r * 1.8)) + 0.2, 0.2, 2), 0.6);
    if (d > r) continue;
    const near = 1 - d / r;
    const f = 1 - fo * (d / r);
    const dir = norm(add(sub(c, pos), { x: 0, y: 0.35, z: 0 }), { x: 0, y: 1, z: 0 });
    if (isZombie(e)) {
      const parts = near > 0.65 ? [...PARTS] : nearestParts(e, pos, near > 0.35 ? 3 : 2);
      applyHit(e, {
        attacker: owner, source: "blast", dtype: "blast", weight: "heavy", damage: dmg * f, point: pos, parts, dir,
        power: 0.5 + 1.3 * near, gorePower: clamp((Number(w?.gore_power) || 1) * (0.45 + 0.75 * near), 0, 1.3), crit: false,
      });
      n++;
    } else if (e.typeId === GIB_ID) {
      safe("blast.gib", () => e.applyImpulse({ x: dir.x * 0.9 * near, y: 0.45 + 0.45 * near, z: dir.z * 0.9 * near }));
    } else {
      safe("blast.other", () => {
        e.applyDamage(Math.max(0.5, dmg * 0.35 * f), { cause: EntityDamageCause.entityExplosion, damagingEntity: owner });
        if (isPlayer(e)) e.applyKnockback({ x: dir.x * 1.3 * near, z: dir.z * 1.3 * near }, 0.3 + 0.4 * near);
      });
      n++;
    }
  }
  return n;
}

/** 爆心に近い部位（立ち姿の箱の中心で）。 @param {Entity} z @param {Vector3} pos @param {number} k */
function nearestParts(z, pos, k) {
  return [...PARTS]
    .map((p) => ({ p, d: dist(partCenter(z, p, 0), pos) }))
    .sort((a, b) => a.d - b.d).slice(0, k).map((x) => x.p);
}

// ---------------------------------------------------------------------------
//  爆竹の誘い・UV 発煙筒
// ---------------------------------------------------------------------------
/** @param {Fly} f @param {Vector3} at */
function startLure(f, at) {
  const s = f.w.special ?? {};
  const r = Number(s.lure_radius) || 28;
  const until = now() + (Number(s.lure_ticks) || 120);
  zones.push({ kind: "lure", dim: f.dim, pos: at, r, until, w: f.w, owner: f.owner, e: f.e, seen: new Set() });
  emit(CEV.LURE, { dim: f.dim, pos: at, radius: r, until, pull: Number(s.lure_pull) || 1 });
  noise(f.dim, at, r, "firecracker", f.owner);
}

/** @param {Fly} f @param {Vector3} at */
function startUv(f, at) {
  const s = f.w.special ?? {};
  const r = Number(s.uv_radius) || 7;
  const until = now() + (Number(s.uv_ticks) || 240);
  const z = { kind: "uv", dim: f.dim, pos: at, r, until, w: f.w, owner: f.owner, e: f.e, seen: new Set() };
  zones.push(z);
  particle(f.dim, f.w.fx?.impact ?? "uv_glow", add(at, { x: 0, y: 0.4, z: 0 }), { radius: r }, PRIO.HIGH);
  sound(f.dim, "nr.fx.uv_hum", at, { volume: 1 });
  emit(CEV.UV_ZONE, { dim: f.dim, pos: at, radius: r, until, source: "uv_flare" });
  uvStep(z, now());
}

/** @param {Zone} z @param {number} t */
function uvStep(z, t) {
  const s = z.w.special ?? {};
  const dps = Number(s.uv_dps) || 2;
  for (const e of entitiesIn(z.dim, z.pos, z.r)) {
    if (isZombie(e)) {
      if (isCorpse(e) || !uvVulnerable(e)) continue;
      applyHit(e, { attacker: z.owner, source: "fire", dtype: "uv", weight: "light", damage: dps * 0.5, power: 0.2, noKnockback: true, noVanilla: true, crit: false, dir: norm(sub(e.location, z.pos)) });
      if (!z.seen.has(e.id) && valid(e)) {
        z.seen.add(e.id);
        stagger(e, Number(s.night_stun_ticks) || 40);
        zombieAnim(e, "uv_recoil");
        const away = norm({ x: e.location.x - z.pos.x, y: 0, z: e.location.z - z.pos.z });
        safe("uv.push", () => e.applyKnockback({ x: away.x * 0.6, z: away.z * 0.6 }, 0.15));
      }
    } else if (isPlayer(e) && t % 20 === 0) {
      emit(CEV.IMMUNITY, { player: e, seconds: Number(s.immunity_regen) || 1, source: "uv_flare" });
    }
  }
}

onWorldTick("throwables.zones", 10, (t) => {
  for (let i = zones.length - 1; i >= 0; i--) {
    const z = zones[i];
    if (t >= z.until) { zones.splice(i, 1); if (z.e && z.kind !== "fire") despawn(z.e); continue; }
    if (z.e && valid(z.e)) { try { z.pos = z.e.location; } catch { /* 読めない */ } }
    if (z.kind === "fire") {
      if (t % 40 === 0) particle(z.dim, "ground_fire", z.pos, { radius: z.r, life: Math.min(2.5, (z.until - t) / 20) }, PRIO.NORMAL);
      if (t % 40 === 0) sound(z.dim, "nr.fx.fire_loop", z.pos, { volume: 0.7 });
      fireStep(z, false);
    } else if (z.kind === "uv") {
      if (t % 20 === 0) particle(z.dim, "uv_glow", add(z.pos, { x: 0, y: 0.4, z: 0 }), { radius: z.r }, PRIO.NORMAL);
      if (t % 60 === 0) sound(z.dim, "nr.fx.uv_hum", z.pos, { volume: 0.8 });
      uvStep(z, t);
    } else if (z.kind === "lure") {
      particle(z.dim, z.w.fx?.impact ?? "firecracker_pop", add(z.pos, { x: 0, y: 0.2, z: 0 }), undefined, PRIO.LOW);
      // 爆竹の音は登録簿に無いので、拳銃の音を小さく高くして代わりにする
      sound(z.dim, "nr.w.pistol", z.pos, { volume: 0.6, pitch: 1.9 });
      if (t % 20 === 0) noise(z.dim, z.pos, z.r, "firecracker", z.owner);
    }
  }
});

/** 範囲の中のエンティティ（落ちている物・弾を除く）。 @param {Dimension} dim @param {Vector3} pos @param {number} r @returns {Entity[]} */
function entitiesIn(dim, pos, r) {
  try {
    return dim.getEntities({ location: pos, maxDistance: r, excludeTypes: ["minecraft:item", "minecraft:xp_orb"] })
      .filter((e) => valid(e) && !e.typeId.startsWith("nr:proj_"));
  } catch { return []; }
}

/** 今ある火・UV・誘いの範囲（テスト・他のモジュール用の写し）。 */
export function activeZones() { return zones.map((z) => ({ kind: z.kind, pos: { ...z.pos }, r: z.r, until: z.until })); }
/** 飛んでいる投げ物の数（テスト用）。 */
export function flyingCount() { return flying.size; }
