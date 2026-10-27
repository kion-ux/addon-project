// ===========================================================================
//  NIGHT RUNNER: 感染都市 — ちぎれた部位 nr:gib と「物理」（DESIGN §5）
//
//  * spawnGib(zombie, part, dir, power): 部位の位置に nr:gib を出し、プロパティ
//    nr:ztype（種類番号。汎用は 63）/ nr:part（0..15）/ nr:spin（空中の回転 1..7、止まると 0）/
//    nr:rest（止まった時の寝姿 0..3）/ nr:bleed（滴っている 1 / 乾いた 0）/ nr:side（裏返しの乱数 0..1）を入れて
//    applyImpulse で打たれた向きへ飛ばす。
//  * スクリプトの物理: 着地のたびに反発係数で跳ね返し、転がりに摩擦を足して止める。止まったら
//    nr:spin = 0（クライアントは nr:rest の寝姿へ）、血だまりを 1 つ。動いている間は血の尾。
//  * 数（設定 max_gibs、既定 48）と寿命（gib_lifetime_s、既定 60 秒）に上限。超えたら古い順に消す。
//  * プレイヤーが殴ると蹴り飛ばせる（entityHitEntity）。飛び道具でも弾ける。
//  * 炭になる種類（gore.crumble）の gib は数秒で灰になって崩れる。
// ===========================================================================
import { world, system } from "@minecraft/server";
import { particle, sound, PRIO } from "../core/fx.js";
import { num, gore, onChange } from "../core/settings.js";
import { ztypeOf, zombieSpec } from "../core/hp.js";
import { emit, EV } from "../core/bus.js";
import { partCenter, locatorPos } from "./hitloc.js";
import { trail, pool, splatGround, burst, kindOf } from "./blood.js";
import {
  valid, norm, add, rand, randInt, clamp, len, lenXZ, now, despawn, setProp, isPlayer, finiteVec, lerpV, warnOnce, safe,
} from "../core/util.js";

/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Dimension} Dimension */

export const GIB_ID = "nr:gib";
/** nr:part の番号（DESIGN §5）。 */
export const GIB = Object.freeze({
  head: 0, jaw: 1, arm_r: 2, arm_l: 3, forearm_r: 4, forearm_l: 5, leg_r: 6, leg_l: 7, shin_r: 8, shin_l: 9,
  lower: 10, guts: 11, brain: 12, chunk: 13, bone: 14, eye: 15,
});
export const GENERIC_ZTYPE = 63;

// 物理の数（ブロック / tick）
const RESTITUTION = 0.38;      // 着地の反発係数
const IMPACT_FRICTION = 0.3;   // 着地で水平の速さを削る割合
const ROLL_FRICTION = 0.22;    // 転がり中に毎回削る割合
const MIN_BOUNCE = 0.16;       // これより遅い着地は跳ねない
const MAX_BOUNCES = 4;
const SETTLE_SPEED = 0.03;
const BLEED_TICKS = 120;       // 断面が滴っている間（その後 nr:bleed = 0）
const ACTIVE_PER_TICK = 48;    // 1 tick に物理を回す gib の数

/**
 * @typedef {object} GibRec
 * @property {Entity} e
 * @property {number} born
 * @property {number} until
 * @property {number} prevVy
 * @property {boolean} settled
 * @property {number} still
 * @property {number} bounces
 * @property {number} bleedUntil
 * @property {boolean} bleeding
 * @property {boolean} crumble
 * @property {string} kind
 * @property {number} nextTrail
 * @property {boolean} pooled
 * @property {number} nextCheck
 */
/** @type {Map<string, GibRec>} 追加順 = 古い順 */
const gibs = new Map();

function lifetimeTicks() { return Math.round(clamp(num("gib_lifetime_s", 60), 1, 3600) * 20); }
function maxGibs() { return Math.round(clamp(num("max_gibs", 48), 0, 256)); }

/** 部位 → nr:part の番号（名前でも数でも）。 @param {string | number} part */
export function gibPart(part) {
  if (typeof part === "number") return clamp(Math.round(part), 0, 15);
  const v = /** @type {Record<string, number>} */ (GIB)[part];
  return v === undefined ? GIB.chunk : v;
}

/** gib の出る位置（部位の箱・ロケータから）。 @param {Entity} z @param {number} p */
function spawnPos(z, p) {
  try {
    switch (p) {
      case GIB.head: case GIB.brain: case GIB.eye: return partCenter(z, "head", 0);
      case GIB.jaw: return locatorPos(z, "loc_mouth");
      case GIB.arm_r: return lerpV(partCenter(z, "arm_r", 0), partCenter(z, "arm_r", 1), 0.5);
      case GIB.arm_l: return lerpV(partCenter(z, "arm_l", 0), partCenter(z, "arm_l", 1), 0.5);
      case GIB.forearm_r: return partCenter(z, "arm_r", 1);
      case GIB.forearm_l: return partCenter(z, "arm_l", 1);
      case GIB.leg_r: return lerpV(partCenter(z, "leg_r", 0), partCenter(z, "leg_r", 1), 0.5);
      case GIB.leg_l: return lerpV(partCenter(z, "leg_l", 0), partCenter(z, "leg_l", 1), 0.5);
      case GIB.shin_r: return partCenter(z, "leg_r", 1);
      case GIB.shin_l: return partCenter(z, "leg_l", 1);
      case GIB.lower: return partCenter(z, "torso", 1);
      case GIB.guts: return locatorPos(z, "loc_belly");
      default: { const c = partCenter(z, "torso", 0); return { x: c.x + rand(-0.2, 0.2), y: c.y + rand(-0.2, 0.2), z: c.z + rand(-0.2, 0.2) }; }
    }
  } catch { return add(z.location, { x: 0, y: 1, z: 0 }); }
}

/** 一番古い gib を消す。 */
function removeOldest() {
  const first = gibs.entries().next().value;
  if (!first) return;
  const [id, rec] = first;
  gibs.delete(id);
  despawn(rec.e);
}

/**
 * gib を 1 つ出して飛ばす。出せなければ undefined。
 * @param {Entity | undefined} zombie 元のゾンビ（死体でも可）。無ければ o.at と o.dim が要る
 * @param {string | number} part GIB の名前か nr:part の番号
 * @param {Vector3} dir 飛ばす向き（打たれた向き）
 * @param {number} [power] 0..2（1 = 普通）
 * @param {{at?: Vector3, dim?: Dimension, ztype?: number, crumble?: boolean, kind?: string, bleed?: boolean, spin?: number}} [o]
 * @returns {Entity | undefined}
 */
export function spawnGib(zombie, part, dir, power = 1, o = {}) {
  const max = maxGibs();
  if (max <= 0) return undefined;
  const p = gibPart(part);
  const src = valid(zombie) ? /** @type {Entity} */ (zombie) : undefined;
  const dim = o.dim ?? src?.dimension;
  const at = o.at ?? (src ? spawnPos(src, p) : undefined);
  if (!dim || !at || !finiteVec(at)) return undefined;
  while (gibs.size >= max) removeOldest();
  const spec = src ? zombieSpec(src) : undefined;
  const crumble = o.crumble ?? !!spec?.gore?.crumble;
  const kind = o.kind ?? (src ? kindOf(src) : "red");
  let e;
  try { e = dim.spawnEntity(GIB_ID, at, { initialRotation: rand(-180, 180) }); } catch (err) { warnOnce("gib-spawn", "nr:gib を出せない", err); return undefined; }
  const zt = clamp(Math.round(o.ztype ?? (src ? ztypeOf(src) : GENERIC_ZTYPE)), 0, 63);
  const bleed = o.bleed ?? (!crumble && kind !== "ash" && gore() > 0.05);
  setProp(e, "nr:ztype", zt);
  setProp(e, "nr:part", p);
  setProp(e, "nr:spin", clamp(Math.round(o.spin ?? randInt(1, 7)), 0, 7));
  setProp(e, "nr:rest", randInt(0, 3));
  setProp(e, "nr:bleed", bleed ? 1 : 0);
  setProp(e, "nr:side", randInt(0, 1));
  fling(e, dir, power);
  const t = now();
  gibs.set(e.id, {
    e, born: t, until: t + (crumble ? randInt(50, 80) : lifetimeTicks()), prevVy: 0, settled: false, still: 0, bounces: 0,
    bleedUntil: t + BLEED_TICKS, bleeding: bleed, crumble, kind, nextTrail: t + 2, pooled: false, nextCheck: t,
  });
  emit(EV.GIB, { gib: e, part: p, zombie: src, ztype: zt });
  return e;
}

/**
 * 汎用の肉片（腸・脳・肉・骨・目玉）をまとめて出す。G で数を減らす。出した数を返す。
 * @param {Entity} zombie @param {number} n G = 100 での数 @param {Vector3} dir @param {number} [power]
 * @param {number[]} [parts] 選ぶ nr:part（既定は 13 肉片・14 骨） @param {{at?: Vector3}} [o]
 */
export function spawnChunks(zombie, n, dir, power = 1, parts = [GIB.chunk, GIB.chunk, GIB.bone], o = {}) {
  const k = Math.round(n * gore());
  let made = 0;
  for (let i = 0; i < k; i++) {
    const d = norm({ x: dir.x + rand(-0.7, 0.7), y: Math.abs(dir.y) + rand(0.2, 0.9), z: dir.z + rand(-0.7, 0.7) });
    const at = o.at ? { x: o.at.x + rand(-0.2, 0.2), y: o.at.y + rand(-0.1, 0.2), z: o.at.z + rand(-0.2, 0.2) } : undefined;
    if (spawnGib(zombie, parts[i % parts.length], d, power * rand(0.6, 1.3), { at })) made++;
  }
  return made;
}

/** 速度を足して飛ばす（重さ・空気は無視。上向きの成分を必ず足す）。 @param {Entity} e @param {Vector3} dir @param {number} power */
function fling(e, dir, power) {
  const d = norm({ x: dir.x, y: 0, z: dir.z }, { x: rand(-1, 1), y: 0, z: rand(-1, 1) });
  const p = clamp(power, 0, 2.5);
  const v = { x: d.x * (0.18 + 0.32 * p) + rand(-0.06, 0.06), y: 0.2 + 0.16 * p + Math.max(0, dir.y) * 0.25 + rand(0, 0.08), z: d.z * (0.18 + 0.32 * p) + rand(-0.06, 0.06) };
  const l = len(v);
  const s = l > 1.4 ? 1.4 / l : 1;
  try { e.applyImpulse({ x: v.x * s, y: v.y * s, z: v.z * s }); } catch { /* 無効 */ }
}

/**
 * gib を蹴る・弾く（向きは蹴った人の視線や弾の向き）。
 * @param {Entity} gib @param {Vector3} dir @param {number} [power]
 */
export function kick(gib, dir, power = 1) {
  if (!valid(gib) || gib.typeId !== GIB_ID) return false;
  const rec = gibs.get(gib.id);
  const d = norm({ x: dir.x, y: 0, z: dir.z });
  try {
    gib.clearVelocity();
    gib.applyImpulse({ x: d.x * 0.75 * power, y: 0.32 + 0.1 * power, z: d.z * 0.75 * power });
  } catch { return false; }
  setProp(gib, "nr:spin", randInt(1, 7));
  if (rec) { rec.settled = false; rec.still = 0; rec.bounces = 0; rec.prevVy = 0.3; rec.pooled = false; }
  sound(gib.dimension, "nr.gore.squish", gib.location, { volume: 0.8, pitch: rand(0.85, 1.15) });
  if (rec?.bleeding) burst(gib.dimension, gib.location, 0.4, { kind: rec.kind, prio: PRIO.NORMAL });
  return true;
}

/** 今ある gib の数。 */
export function gibCount() { return gibs.size; }
/** 全部消す。 */
export function clearGibs() { for (const rec of gibs.values()) despawn(rec.e); gibs.clear(); }
/** 登録中の gib（テスト・デバッグ用の写し）。 */
export function gibList() { return [...gibs.values()].map((r) => r.e); }

/** 寿命の終わり（炭になる種類は灰を散らす）。 @param {string} id @param {GibRec} rec */
function expire(id, rec) {
  gibs.delete(id);
  if (rec.crumble && valid(rec.e)) {
    const l = rec.e.location;
    particle(rec.e.dimension, "char_flakes", l, { count: 6, size: 0.6 }, PRIO.LOW);
  }
  despawn(rec.e);
}

// ---------------------------------------------------------------------------
//  物理の 1 tick（動いている gib を回す。止まった gib は寿命だけ時々見る）
// ---------------------------------------------------------------------------
let cursor = 0;
system.runInterval(() => {
  if (!gibs.size) return;
  const t = now();
  const all = [...gibs];
  let budget = ACTIVE_PER_TICK;
  const n = all.length;
  for (let k = 0; k < n && budget > 0; k++) {
    const [id, rec] = all[(cursor + k) % n];
    if (rec.settled && t < rec.nextCheck) continue;
    budget--;
    safe("gib-step", () => step(id, rec, t));
  }
  cursor = n ? (cursor + ACTIVE_PER_TICK) % n : 0;
}, 1);

/** @param {string} id @param {GibRec} rec @param {number} t */
function step(id, rec, t) {
  const e = rec.e;
  if (!valid(e)) { gibs.delete(id); return; }
  if (t >= rec.until) { expire(id, rec); return; }
  if (rec.bleeding && t >= rec.bleedUntil) { rec.bleeding = false; setProp(e, "nr:bleed", 0); }
  if (rec.settled) { rec.nextCheck = t + 20; return; }
  const v = e.getVelocity();
  const on = e.isOnGround;
  const loc = e.location;
  // 着地: 落ちていたのに縦の速さが消えた
  const landed = rec.prevVy < -MIN_BOUNCE * 0.5 && v.y > rec.prevVy * 0.3 && (on || Math.abs(v.y) < 0.02);
  if (landed) {
    const impact = -rec.prevVy;
    if (impact > MIN_BOUNCE && rec.bounces < MAX_BOUNCES) {
      rec.bounces++;
      try { e.applyImpulse({ x: -v.x * IMPACT_FRICTION, y: impact * RESTITUTION - Math.min(0, v.y), z: -v.z * IMPACT_FRICTION }); } catch { /* 無効 */ }
      sound(e.dimension, "nr.gore.gib_land", loc, { volume: clamp(impact * 1.6, 0.25, 1.2), pitch: rand(0.85, 1.2) });
      if (rec.bleeding && rec.bounces <= 2) splatGround(e.dimension, loc, 0.5 + impact, { kind: rec.kind });
      setProp(e, "nr:spin", randInt(1, 7));
    } else if (impact > 0.08 && rec.bounces === 0) {
      sound(e.dimension, "nr.gore.gib_land", loc, { volume: 0.4, pitch: rand(0.9, 1.1) });
    }
  }
  const speed = len(v);
  // 転がりの摩擦（地面で遅くなったら一気に止める）
  if (on && lenXZ(v) > 0.005 && lenXZ(v) < 0.25) {
    try { e.applyImpulse({ x: -v.x * ROLL_FRICTION, y: 0, z: -v.z * ROLL_FRICTION }); } catch { /* 無効 */ }
  }
  // 血の尾
  if (rec.bleeding && speed > 0.06 && t >= rec.nextTrail) { rec.nextTrail = t + 3; trail(e.dimension, loc, 0.6, { kind: rec.kind }); }
  // 止まった
  if ((on || Math.abs(v.y) < 0.01) && speed < SETTLE_SPEED) {
    if (++rec.still >= 4) {
      rec.settled = true;
      rec.nextCheck = t + 20;
      setProp(e, "nr:spin", 0);
      if (rec.bleeding && !rec.pooled) { rec.pooled = true; pool(e.dimension, loc, 0.6, { kind: rec.kind }); }
    }
  } else rec.still = 0;
  rec.prevVy = v.y;
}

// ---------------------------------------------------------------------------
//  イベント: 蹴る・弾が当たる・読み込み・消えた・設定の変化
// ---------------------------------------------------------------------------
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const g = ev.hitEntity;
  if (g?.typeId !== GIB_ID || !valid(g)) return;
  const a = ev.damagingEntity;
  let dir = { x: 0, y: 0, z: 1 };
  try { dir = isPlayer(a) ? a.getViewDirection() : norm({ x: g.location.x - a.location.x, y: 0, z: g.location.z - a.location.z }); } catch { /* 向きは既定 */ }
  kick(g, dir, 1);
});

world.afterEvents.projectileHitEntity.subscribe((ev) => {
  let g;
  try { g = ev.getEntityHit()?.entity; } catch { g = undefined; }
  if (g?.typeId !== GIB_ID || !valid(g)) return;
  kick(g, ev.hitVector, 0.8);
});

// 読み込まれた gib（前のセッションの残り・遠くから戻ったチャンク）は短い寿命で登録し直す
world.afterEvents.entityLoad.subscribe((ev) => {
  const e = ev.entity;
  if (e?.typeId !== GIB_ID || gibs.has(e.id)) return;
  const t = now();
  gibs.set(e.id, { e, born: t, until: t + 200, prevVy: 0, settled: true, still: 4, bounces: MAX_BOUNCES, bleedUntil: t, bleeding: false, crumble: false, kind: "red", nextTrail: t, pooled: true, nextCheck: t + 20 });
  while (gibs.size > maxGibs()) removeOldest();
});

world.afterEvents.entityRemove.subscribe((ev) => { if (ev.typeId === GIB_ID) gibs.delete(ev.removedEntityId); });

// 上限が下がったら古い順に減らす
onChange((e) => { if (e.key === "max_gibs" || e.key === "*") { const m = maxGibs(); while (gibs.size > m) removeOldest(); } });
