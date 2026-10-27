// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 血の演出（しぶき・弾け・霧・噴水・血痕・血だまり・画面の返り血）
//
//  * 量は全部ゴアレベル G（設定 gore_level / 100）と 1 tick の予算（core/budget.js）で決まる。G = 0 なら出さない。
//  * 血痕（地面・壁）と血だまりは blood_decal_mult（設定）で数と大きさが変わり、寿命は GORE_TUNING.decal_lifetime_s。
//  * 血の種類（spec の gore.blood: red / dark / black / bile / acid / ash / water / ember）で出すものを変える
//    （ash / ember は血の代わりに灰・火の粉、bile / acid は緑の飛沫を足す、water は大きく飛んで早く薄まる）。
//  * 噴水は断面のロケータ（data/zombie_shapes.js の locators）を追いかけて拍動する（fountain()）。
// ===========================================================================
import { system, world } from "@minecraft/server";
import { particle, sound, fade, PRIO } from "../core/fx.js";
import { gore, num, get, tuning } from "../core/settings.js";
import { pressure } from "../core/budget.js";
import { zombieSpec } from "../core/hp.js";
import { locatorPos, locatorDir } from "./hitloc.js";
import {
  norm, add, scale, addScaled, clamp, lerp, rand, randInt, chance, jitterDir, valid, finiteVec, dist, now, DOWN,
} from "../core/util.js";

/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {{kind?: string, prio?: number}} BloodOpts */

// spec（nr_spec_catalog.GORE_TUNING）の写し。生成データにあればそちら
const FALLBACK_GT = {
  sever_mult_exp: 0.8, blood_mult: "G/100",
  min_g: { wounded: 0, jawless: 20, cracked: 20, broken: 0, cut_lower: 30, cut_upper: 30, severed: 30, crushed: 40, slashed: 10, gutted: 40, halved: 60 },
  fountain_ticks: { base: 40, at_100: 100 },
  gib_count: { sever: 1, crushed_head: [3, 8], halved: [2, 5], explode: [6, 14], chunk_scale: "G/100" },
  decal_lifetime_s: { base: 30, at_100: 120 },
  screen_blood_range: 3.0, screen_blood_min_g: 50, guts_min_g: 40, overkill_burst_min_g: 70,
};
/** @type {any} */
export const GT = { ...FALLBACK_GT, ...tuning("GORE_TUNING", {}) };

/** 血の種類（spec の gore.blood。無ければ red）。 @param {Entity | string | undefined} z */
export function kindOf(z) {
  const s = zombieSpec(/** @type {any} */ (z));
  return String(s?.gore?.blood ?? "red");
}
/** 血の量の倍率（spec の gore.bleed_mult）。 @param {Entity | string | undefined} z */
export function bleedOf(z) {
  const s = zombieSpec(/** @type {any} */ (z));
  const v = Number(s?.gore?.bleed_mult);
  return Number.isFinite(v) && v > 0 ? v : 1;
}
const DRY = new Set(["ash", "ember"]);       // 血の代わりに灰・火の粉
/** その種類は血だまり・血痕を作るか。 @param {string} kind */
export function makesPools(kind) { return kind !== "ash"; }

/** 血痕・血だまりの寿命（秒）。G が大きいほど長い。 */
export function decalLife() {
  const d = GT.decal_lifetime_s ?? FALLBACK_GT.decal_lifetime_s;
  return lerp(Number(d.base) || 30, Number(d.at_100) || 120, gore());
}
/** 断面の噴水の長さ（tick）。 */
export function fountainTicks() {
  const d = GT.fountain_ticks ?? FALLBACK_GT.fountain_ticks;
  return Math.round(lerp(Number(d.base) || 40, Number(d.at_100) || 100, gore()));
}
function decalMult() { return clamp(num("blood_decal_mult", 1), 0, 2); }

// 1 tick の地形レイの上限（血痕は飾りなので数を抑える）
const RAY_CAP = 24;
let rayTick = -1, rays = 0;
function rayOk() {
  const t = system.currentTick;
  if (t !== rayTick) { rayTick = t; rays = 0; }
  if (rays >= RAY_CAP) return false;
  rays++;
  return true;
}

// ---------------------------------------------------------------------------
//  基本の演出
// ---------------------------------------------------------------------------
/**
 * 向き付きの血しぶき。power 0..2（1 = 普通の一撃）。
 * @param {Dimension} dim @param {Vector3} pos @param {Vector3} dir @param {number} [power] @param {BloodOpts} [o]
 */
export function spray(dim, pos, dir, power = 1, o) {
  const G = gore();
  if (G <= 0.02) return false;
  const kind = o?.kind ?? "red";
  const prio = o?.prio ?? PRIO.NORMAL;
  const d = norm(dir);
  const p = clamp(power, 0.1, 2.5);
  const k = pressure(prio);
  if (DRY.has(kind)) {
    const ok = particle(dim, "char_flakes", pos, { count: Math.round((3 + 6 * p) * G * k) + 1, size: 0.6 + 0.4 * p }, prio);
    if (kind === "ember") particle(dim, "burn_flesh", pos, { size: 0.5 }, PRIO.LOW);
    return ok;
  }
  const wet = kind === "water" ? 1.5 : 1;
  const ok = particle(dim, "blood_spray", pos, {
    dx: d.x, dy: d.y, dz: d.z, speed: 0.5 + 0.7 * p, count: Math.max(1, Math.round((4 + 14 * p) * G * k * wet)),
    spread: (0.12 + 0.18 * p) * wet, size: 0.7 + 0.4 * p, gore: G,
  }, prio);
  if ((kind === "bile" || kind === "acid") && p > 0.8) particle(dim, kind === "acid" ? "acid_splash" : "toxic_burst", pos, kind === "acid" ? { radius: 0.4, life: 1.5 } : { size: 0.4 }, PRIO.LOW);
  return ok;
}

/** 全方向に弾ける血。 @param {Dimension} dim @param {Vector3} pos @param {number} [power] @param {BloodOpts} [o] */
export function burst(dim, pos, power = 1, o) {
  const G = gore();
  if (G <= 0.02) return false;
  const kind = o?.kind ?? "red";
  const prio = o?.prio ?? PRIO.HIGH;
  const p = clamp(power, 0.1, 3);
  if (DRY.has(kind)) return particle(dim, "char_flakes", pos, { count: Math.round((6 + 10 * p) * G) + 1, size: 0.8 + 0.3 * p }, prio);
  const ok = particle(dim, "blood_burst", pos, { count: Math.max(2, Math.round((6 + 16 * p) * G)), speed: 0.4 + 0.5 * p, size: 0.7 + 0.4 * p, gore: G }, prio);
  if (kind === "bile") particle(dim, "toxic_burst", pos, { size: 0.5 + 0.3 * p }, PRIO.NORMAL);
  else if (kind === "acid") particle(dim, "acid_splash", pos, { radius: 0.6 + 0.3 * p, life: 2 }, PRIO.NORMAL);
  return ok;
}

/** 細かい血の霧（頭が弾ける・散弾）。 @param {Dimension} dim @param {Vector3} pos @param {number} [size] @param {BloodOpts} [o] */
export function mist(dim, pos, size = 1, o) {
  const G = gore();
  if (G <= 0.05) return false;
  if (DRY.has(o?.kind ?? "red")) return particle(dim, "smoke_dark", pos, { size: size * 0.8, life: 1.2 }, o?.prio ?? PRIO.NORMAL);
  return particle(dim, "blood_mist", pos, { size: size * (0.6 + 0.4 * G), life: 0.5 + 0.5 * G, gore: G }, o?.prio ?? PRIO.NORMAL);
}

/** ぽたぽた落ちる数滴。 @param {Dimension} dim @param {Vector3} pos @param {number} [n] @param {BloodOpts} [o] */
export function drip(dim, pos, n = 3, o) {
  const G = gore();
  if (G <= 0.05 || DRY.has(o?.kind ?? "red")) return false;
  return particle(dim, "blood_drip", pos, { count: Math.max(1, Math.round(n * G)), size: 0.8 }, o?.prio ?? PRIO.LOW);
}

/** 動く gib・這うゾンビの血の点。 @param {Dimension} dim @param {Vector3} pos @param {number} [size] @param {BloodOpts} [o] */
export function trail(dim, pos, size = 1, o) {
  const G = gore();
  if (G <= 0.1 || !makesPools(o?.kind ?? "red") || DRY.has(o?.kind ?? "red")) return false;
  return particle(dim, "blood_trail", pos, { size: size * (0.5 + 0.5 * G) }, PRIO.LOW);
}

// ---------------------------------------------------------------------------
//  血痕・血だまり（地形のレイで貼る場所を決める）
// ---------------------------------------------------------------------------
/**
 * 下の地面を探して返す（見つからなければ undefined）。 @param {Dimension} dim @param {Vector3} pos @param {number} [reach]
 * @returns {Vector3 | undefined}
 */
export function groundBelow(dim, pos, reach = 4) {
  if (!finiteVec(pos) || !rayOk()) return undefined;
  try {
    const start = { x: pos.x, y: pos.y + 0.3, z: pos.z };
    const hit = dim.getBlockFromRay(start, DOWN, { maxDistance: reach + 0.3, includeLiquidBlocks: false, includePassableBlocks: false });
    if (!hit) return undefined;
    return { x: hit.block.x + hit.faceLocation.x, y: hit.block.y + 1.02, z: hit.block.z + hit.faceLocation.z };
  } catch { return undefined; }
}

/** 地面の血痕。 @param {Dimension} dim @param {Vector3} pos @param {number} [size] @param {BloodOpts} [o] */
export function splatGround(dim, pos, size = 1, o) {
  const G = gore();
  const kind = o?.kind ?? "red";
  if (G <= 0.05 || !makesPools(kind)) return false;
  const m = decalMult();
  if (m <= 0) return false;
  const at = groundBelow(dim, pos);
  if (!at) return false;
  if (DRY.has(kind)) return particle(dim, "char_flakes", at, { count: 3, size: 0.6 }, PRIO.LOW);
  return particle(dim, "blood_splat_ground", at, { size: clamp(size * (0.6 + 0.4 * G) * m, 0.2, 3), life: decalLife() * (kind === "water" ? 0.3 : 1) }, o?.prio ?? PRIO.LOW);
}

/**
 * 当たった向きの先の壁に血痕（±X の壁は wall_x、±Z の壁は wall_z）。上向きの面なら地面の血痕。
 * @param {Dimension} dim @param {Vector3} pos @param {Vector3} dir @param {number} [size] @param {BloodOpts & {reach?: number}} [o]
 */
export function splatWall(dim, pos, dir, size = 1, o) {
  const G = gore();
  const kind = o?.kind ?? "red";
  if (G <= 0.1 || !makesPools(kind) || DRY.has(kind)) return false;
  const m = decalMult();
  if (m <= 0 || !finiteVec(pos) || !rayOk()) return false;
  const d = norm(dir);
  let hit;
  try { hit = dim.getBlockFromRay(pos, d, { maxDistance: o?.reach ?? 2.5, includeLiquidBlocks: false, includePassableBlocks: false }); } catch { hit = undefined; }
  if (!hit) return false;
  const p = { x: hit.block.x + hit.faceLocation.x, y: hit.block.y + hit.faceLocation.y, z: hit.block.z + hit.faceLocation.z };
  const life = decalLife() * (kind === "water" ? 0.3 : 1);
  const sz = clamp(size * (0.6 + 0.4 * G) * m, 0.2, 3);
  switch (String(hit.face)) {
    case "East": return particle(dim, "blood_splat_wall_x", { x: p.x + 0.02, y: p.y, z: p.z }, { dx: 1, size: sz, life }, PRIO.LOW);
    case "West": return particle(dim, "blood_splat_wall_x", { x: p.x - 0.02, y: p.y, z: p.z }, { dx: -1, size: sz, life }, PRIO.LOW);
    case "South": return particle(dim, "blood_splat_wall_z", { x: p.x, y: p.y, z: p.z + 0.02 }, { dz: 1, size: sz, life }, PRIO.LOW);
    case "North": return particle(dim, "blood_splat_wall_z", { x: p.x, y: p.y, z: p.z - 0.02 }, { dz: -1, size: sz, life }, PRIO.LOW);
    case "Up": return particle(dim, "blood_splat_ground", { x: p.x, y: p.y + 0.02, z: p.z }, { size: sz, life }, PRIO.LOW);
    default: return false;
  }
}

/** 広がる血だまり（死体・gib の下）。 @param {Dimension} dim @param {Vector3} pos @param {number} [size] @param {BloodOpts} [o] */
export function pool(dim, pos, size = 1, o) {
  const G = gore();
  const kind = o?.kind ?? "red";
  if (G <= 0.05 || !makesPools(kind) || DRY.has(kind)) return false;
  const m = decalMult();
  if (m <= 0) return false;
  const at = groundBelow(dim, pos, 3);
  if (!at) return false;
  if (kind === "acid") particle(dim, "acid_splash", at, { radius: 0.5 * size, life: 3 }, PRIO.LOW);
  return particle(dim, "blood_pool", at, { size: clamp(size * (0.5 + 0.5 * G) * m, 0.2, 4), life: decalLife() * (kind === "water" ? 0.3 : 1) }, o?.prio ?? PRIO.LOW);
}

// ---------------------------------------------------------------------------
//  断面の噴水（ロケータを追う）
// ---------------------------------------------------------------------------
/** @typedef {{z: Entity, loc: string, until: number, kind: string, nextDrip: number, mult: number}} Fountain */
/** @type {Map<string, Fountain>} */
const fountains = new Map();
const MAX_FOUNTAINS = 24;

/**
 * 断面（ロケータ）から拍動する噴水を ticks の間出し続ける。死体でもよい。
 * @param {Entity} z @param {string} loc 例 "loc_neck"、"loc_shoulder_r" @param {number} [ticks] @param {BloodOpts & {mult?: number}} [o]
 */
export function fountain(z, loc, ticks, o) {
  if (!valid(z) || gore() <= 0.05) return false;
  const kind = o?.kind ?? kindOf(z);
  const len = Math.round((ticks ?? fountainTicks()) * bleedOf(z));
  if (len <= 0) return false;
  if (fountains.size >= MAX_FOUNTAINS) {
    const oldest = fountains.keys().next().value;
    if (oldest !== undefined) fountains.delete(oldest);
  }
  fountains.set(`${z.id}|${loc}`, { z, loc, until: now() + len, kind, nextDrip: now() + 10, mult: o?.mult ?? 1 });
  if (!DRY.has(kind)) sound(z.dimension, "nr.gore.spurt", z.location, { volume: 0.9, pitch: rand(0.9, 1.1) });
  return true;
}

/** そのゾンビの噴水を止める。 @param {Entity | string} z */
export function stopFountains(z) {
  const id = typeof z === "string" ? z : z.id;
  for (const k of [...fountains.keys()]) if (k.startsWith(id + "|")) fountains.delete(k);
}
/** 動いている噴水の数。 */
export function fountainCount() { return fountains.size; }

system.runInterval(() => {
  if (!fountains.size) return;
  const t = now();
  const G = gore();
  for (const [k, f] of fountains) {
    if (!valid(f.z) || t >= f.until || G <= 0.05) { fountains.delete(k); continue; }
    let pos, dir;
    try { pos = locatorPos(f.z, f.loc); dir = locatorDir(f.z, f.loc); } catch { fountains.delete(k); continue; }
    const left = (f.until - t) / 20;
    if (DRY.has(f.kind)) {
      particle(f.z.dimension, "char_flakes", pos, { count: 2, size: 0.5 }, PRIO.LOW);
      continue;
    }
    // 拍動: 残りが短くなるほど弱く
    const fall = clamp(left / 2, 0.25, 1) * f.mult;
    particle(f.z.dimension, "blood_fountain", pos, { dx: dir.x, dy: dir.y, dz: dir.z, life: 0.3, size: (0.6 + 0.6 * G) * fall, gore: G }, PRIO.NORMAL);
    if (t >= f.nextDrip) {
      f.nextDrip = t + randInt(16, 30);
      if (chance(0.6)) splatGround(f.z.dimension, addScaled(pos, dir, 0.6), 0.5 * fall, { kind: f.kind });
    }
  }
}, 3);

// ---------------------------------------------------------------------------
//  まとめた演出
// ---------------------------------------------------------------------------
/**
 * 1 回の命中の血（当たった点の飛沫・抜ける向きのしぶき・後ろの壁の血痕・地面の滴り）。
 * @param {Entity} z @param {Vector3} point @param {Vector3} dir @param {number} power 0..2
 * @param {{armored?: boolean, kind?: string, bleed?: number}} [o]
 */
export function hitFx(z, point, dir, power, o) {
  const dim = z.dimension;
  const d = norm(dir);
  if (o?.armored) {
    particle(dim, "hit_spark", point, { dx: -d.x, dy: -d.y, dz: -d.z }, PRIO.HIGH);
    return;
  }
  const kind = o?.kind ?? kindOf(z);
  const G = gore();
  particle(dim, "hit_flesh", point, { dx: -d.x, dy: -d.y, dz: -d.z }, PRIO.HIGH);
  if (G <= 0.02) return;
  const p = clamp(power * (o?.bleed ?? bleedOf(z)), 0.15, 2.5);
  spray(dim, point, jitterDir(d, 0.25), p, { kind });
  if (p > 0.6 && chance(0.35 * G)) spray(dim, point, jitterDir({ x: -d.x, y: 0.4, z: -d.z }, 0.4), p * 0.5, { kind, prio: PRIO.LOW });
  if (chance(clamp((0.35 + 0.4 * p) * G * decalMult(), 0, 1))) splatWall(dim, point, d, 0.7 + 0.5 * p, { kind });
  if (chance(clamp(0.45 * p * G * decalMult(), 0, 1))) splatGround(dim, addScaled(point, d, rand(0.3, 1.2)), 0.5 + 0.4 * p, { kind });
}

/**
 * 切断の瞬間（断面からの飛沫・噴水）。
 * @param {Entity} z @param {string} loc 断面のロケータ @param {Vector3} dir 打たれた向き @param {number} [power] @param {{kind?: string, fountain?: boolean}} [o]
 */
export function severFx(z, loc, dir, power = 1, o) {
  const G = gore();
  if (G <= 0.05) return;
  const kind = o?.kind ?? kindOf(z);
  let pos;
  try { pos = locatorPos(z, loc); } catch { pos = z.location; }
  const d = norm(dir);
  if (DRY.has(kind)) {
    particle(z.dimension, "char_flakes", pos, { count: Math.round(10 * G) + 2, size: 0.9 }, PRIO.HIGH);
    particle(z.dimension, "smoke_dark", pos, { size: 0.6, life: 1.5 }, PRIO.NORMAL);
    return;
  }
  particle(z.dimension, "sever_burst", pos, { dx: d.x, dy: d.y, dz: d.z, size: 0.8 + 0.4 * power, gore: G }, PRIO.HIGH);
  spray(z.dimension, pos, jitterDir(add(d, { x: 0, y: 0.4, z: 0 }), 0.3), 1.2 * power, { kind, prio: PRIO.HIGH });
  if (o?.fountain !== false) fountain(z, loc, undefined, { kind });
  if (chance(0.7 * decalMult())) splatGround(z.dimension, addScaled(pos, d, 0.8), 1.0, { kind });
}

/**
 * 頭が弾ける（頭蓋・脳・霧）。gib は gore.js が出す。
 * @param {Entity} z @param {Vector3} pos @param {Vector3} dir @param {number} [power] @param {{kind?: string, wet?: boolean}} [o]
 */
export function headExplodeFx(z, pos, dir, power = 1, o) {
  const G = gore();
  const kind = o?.kind ?? kindOf(z);
  const d = norm(dir);
  if (DRY.has(kind)) { burst(z.dimension, pos, 1.5, { kind }); return; }
  particle(z.dimension, "head_explode", pos, { dx: d.x, dy: d.y, dz: d.z, size: 0.8 + 0.4 * power, gore: G }, PRIO.CRITICAL);
  mist(z.dimension, pos, 1.2 + (o?.wet ? 1 : 0), { kind });
  if (o?.wet) burst(z.dimension, pos, 2, { kind });
  for (let i = 0; i < 2; i++) if (chance(0.8 * decalMult())) splatWall(z.dimension, pos, jitterDir(d, 0.5), 1.4, { kind, reach: 3.5 });
  splatGround(z.dimension, addScaled(pos, d, 1.0), 1.4, { kind });
}

/**
 * 全身が弾ける（爆発・オーバーキル・破裂する種類）。
 * @param {Dimension} dim @param {Vector3} pos @param {number} [size] @param {{kind?: string, wet?: boolean}} [o]
 */
export function bodyExplodeFx(dim, pos, size = 1, o) {
  const G = gore();
  const kind = o?.kind ?? "red";
  if (DRY.has(kind)) { particle(dim, "char_flakes", pos, { count: Math.round(24 * G) + 4, size: 1.2 }, PRIO.CRITICAL); particle(dim, "smoke_dark", pos, { size: 1.2, life: 2 }, PRIO.NORMAL); return; }
  particle(dim, "body_explode", pos, { size, gore: G }, PRIO.CRITICAL);
  mist(dim, pos, 1.5 * size, { kind });
  burst(dim, pos, 2 * size, { kind, prio: PRIO.CRITICAL });
  if (G > 0.3) {
    for (let i = 0; i < 4; i++) {
      const a = (i / 4) * Math.PI * 2 + rand(0, 1);
      splatWall(dim, pos, { x: Math.cos(a), y: rand(-0.2, 0.3), z: Math.sin(a) }, 1.6, { kind, reach: 4 });
    }
    for (let i = 0; i < 3; i++) splatGround(dim, add(pos, { x: rand(-1.5, 1.5), y: 0, z: rand(-1.5, 1.5) }), 1.3, { kind });
  }
  pool(dim, pos, 1.8 * size, { kind });
}

// ---------------------------------------------------------------------------
//  画面の返り血（近くで仕留めた・切り落とした時）
// ---------------------------------------------------------------------------
/** @type {Map<string, number>} */
const screenCd = new Map();

/**
 * 近ければ画面を赤く（設定 screen_blood・G >= GORE_TUNING.screen_blood_min_g・距離 <= screen_blood_range）。
 * @param {Player} p @param {Vector3} from 血が飛んだ所 @param {number} [intensity] 0..1
 */
export function screenBlood(p, from, intensity = 1) {
  if (!valid(p) || p.typeId !== "minecraft:player") return false;
  if (!get("screen_blood")) return false;
  const G = gore();
  if (G * 100 < (Number(GT.screen_blood_min_g) || 50)) return false;
  let d = 99;
  try { d = dist(p.getHeadLocation(), from); } catch { return false; }
  if (d > (Number(GT.screen_blood_range) || 3)) return false;
  const t = now();
  if ((screenCd.get(p.id) ?? -99) > t) return false;
  screenCd.set(p.id, t + 16);
  const k = clamp(intensity, 0.2, 1) * G;
  return fade(p, { red: 0.45 * k + 0.1, green: 0, blue: 0 }, 0.04, 0.08 + 0.12 * k, 0.5 + 0.7 * k);
}

world.afterEvents.playerLeave.subscribe((ev) => { screenCd.delete(ev.playerId); });
