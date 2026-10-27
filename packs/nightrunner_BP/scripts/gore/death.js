// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 死亡・死体・ルート・特殊な死（DESIGN §4 / §5）
//
//  kill(zombie, info): nr:hp を 0 にし、BP イベント nr:on_death（nr:dead グループ・nr:state = dead）、
//  nr:pose に死に方（下の POSE）、打たれた向きへ吹き飛ばす（屋上から落ちる）、spec の loot（＋ LOOT_TABLES）を
//  spawnItem、経験値のオーブ、死体の寿命・上限（設定 corpse_lifetime_s / max_corpses）と血だまり・後片付け。
//  * 死体は動き続ける: 高い所から落ちて着地したら衝撃のゴア（脚が折れる・ちぎれる）を applyHit に流す。
//  * 特殊な死: gore.explode（toxic = 毒の雲が周りを蝕む / blast = 爆発が周りを巻き込んで gib にする /
//    acid / spores / water = 破裂の見た目）、gore.crumble・corpse = "ash"（または焼け焦げ nr:burn = 3）は灰になって崩れる、
//    corpse = "melt" は溶けて消える。能力 toxic_death_puff / gas_cloud_death / detonate の「死んだ時」の分もここでやる
//    （zombies/abilities.js は死んだ時の雲・爆発を重ねて出さないこと）。
//  * 周りへのダメージ・死体への衝撃は setHitHandler() で受け取った関数（gore.js の applyHit）を通す。
// ===========================================================================
import { world, system, ItemStack, EntityDamageCause } from "@minecraft/server";
import { particle, sound, shake, PRIO } from "../core/fx.js";
import { num, gore, tuning } from "../core/settings.js";
import { zombieSpec, setHp } from "../core/hp.js";
import { emit, EV } from "../core/bus.js";
import { spawnGib, spawnChunks, GIB } from "./gibs.js";
import { bodyExplodeFx, burst, pool, splatGround, kindOf, bleedOf, GT, makesPools } from "./blood.js";
import { partCenter } from "./hitloc.js";
import {
  valid, norm, add, sub, dist, rand, randInt, chance, clamp, now, despawn, setProp, getProp, trigger, isPlayer,
  isZombie, yawOf, dirToLocal, yawForward, warnOnce, safe, len, finiteVec, later, DOWN,
} from "../core/util.js";

/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Dimension} Dimension */

/** nr:pose の意味（死に方。RP の死体のアニメはこの番号で姿勢を選ぶ）。 */
export const POSE = Object.freeze({
  BACK: 0,      // 仰向けに倒れる（前から打たれた）
  FRONT: 1,     // うつ伏せに倒れる（後ろから打たれた）
  LEFT: 2,      // 左へ倒れる（ゾンビの左へ押された）
  RIGHT: 3,     // 右へ倒れる
  CRUMPLE: 4,   // 膝から崩れ落ちる（首・頭を失った）
  CRAWL: 5,     // 這ったまま突っ伏す（脚が無い・這い中）
  HALF: 6,      // 上半身だけ（胴が真っ二つ）
  BLOWN: 7,     // 大の字に吹き飛ぶ（爆発・オーバーキル）
});

/**
 * @typedef {object} KillInfo
 * @property {Entity} [attacker]
 * @property {any} [hit]            applyHit の hit
 * @property {Vector3} [dir]        打たれた向き（無ければ hit.dir）
 * @property {number} [power]       0..2
 * @property {string} [cause]       "hp" | "head" | "overkill" | "fall" | "explode" | "script" など
 * @property {boolean} [decap]
 * @property {boolean} [crushed]
 * @property {boolean} [overkill]   全身が弾ける
 * @property {Record<string, string>} [parts]  いまの部位の状態（gore.js が渡す）
 * @property {string} [state]       死ぬ直前の nr:state
 * @property {number} [burn]        nr:burn
 * @property {boolean} [byPlayer]   プレイヤーが関わった死（経験値を出す）
 * @property {boolean} [noLoot]
 * @property {boolean} [noXp]
 * @property {number} [pose]        nr:pose を指定する時
 * @property {Vector3} [at]         overkill: エンティティが既に無効な時の位置（最後に見た所）
 * @property {Dimension} [dim]      overkill: 同じく次元
 * @property {string} [key]         overkill: 同じく種類の鍵
 */

/** @type {((z: Entity, hit: any) => any) | undefined} */
let hitHandler;
/** 周りへのダメージ・死体の衝撃を流す先（gore.js が applyHit を登録する）。 @param {(z: Entity, hit: any) => any} fn */
export function setHitHandler(fn) { hitHandler = fn; }
/** @param {Entity} z @param {any} hit */
function hitOther(z, hit) { if (hitHandler && valid(z)) safe("death-hit", () => hitHandler?.(z, hit)); }

// ---------------------------------------------------------------------------
//  死体の記録
// ---------------------------------------------------------------------------
/**
 * @typedef {object} CorpseRec
 * @property {Entity} e
 * @property {string} key
 * @property {number} born
 * @property {number} until
 * @property {"normal" | "ash" | "melt"} kind
 * @property {number} prevVy
 * @property {boolean} settled
 * @property {number} still
 * @property {boolean} pooled
 * @property {number} nextCheck
 * @property {number} nextFx
 * @property {string} blood
 * @property {number} bleed
 */
/** @type {Map<string, CorpseRec>} 追加順 = 古い順 */
const corpses = new Map();
/** @type {Set<string>} 死亡処理を済ませた ID */
const dead = new Set();

function corpseTicks() { return Math.round(clamp(num("corpse_lifetime_s", 90), 1, 3600) * 20); }
function maxCorpses() { return Math.round(clamp(num("max_corpses", 24), 0, 256)); }

/** 死体か（記録にある・nr:state = dead）。 @param {Entity} e */
export function isCorpse(e) { return valid(e) && (corpses.has(e.id) || dead.has(e.id) || getProp(e, "nr:state", "") === "dead"); }
/** 死体の数。 */
export function corpseCount() { return corpses.size; }
/** 死体の一覧（写し）。 */
export function corpseList() { return [...corpses.values()].map((r) => r.e); }
/** 全部消す。 */
export function clearCorpses() { for (const r of corpses.values()) despawn(r.e); corpses.clear(); }

function removeOldestCorpse() {
  const first = corpses.entries().next().value;
  if (!first) return;
  corpses.delete(first[0]);
  despawn(first[1].e);
}

/** @param {Entity} z @param {"normal" | "ash" | "melt"} kind @param {number} [life] */
function registerCorpse(z, kind, life) {
  const t = now();
  const max = maxCorpses();
  if (max <= 0) { despawn(z); return; }
  corpses.set(z.id, {
    e: z, key: z.typeId.slice(5), born: t, until: t + (life ?? (kind === "ash" ? randInt(50, 70) : kind === "melt" ? randInt(90, 120) : corpseTicks())),
    kind, prevVy: 0, settled: false, still: 0, pooled: false, nextCheck: t, nextFx: t + 20, blood: kindOf(z), bleed: bleedOf(z),
  });
  while (corpses.size > max) removeOldestCorpse();
}

// ---------------------------------------------------------------------------
//  ルート・経験値
// ---------------------------------------------------------------------------
// spec の LOOT_TABLES のうち、死体まわりで使うものの写し（生成データに LOOT_TABLES があればそちら）
const FALLBACK_LOOT_TABLES = {
  gore_remains: [["nr:rags", 1, 2, 0.6], ["nr:money", 1, 6, 0.4], ["nr:bandage", 1, 1, 0.15], ["nr:lockpick", 1, 1, 0.1], ["minecraft:bone", 1, 3, 0.7]],
};

/**
 * ルートを落とす。entries は [ID, 最小, 最大, 確率] の並び（spec の loot と同じ形）。文字列か {table} は LOOT_TABLES の名前。
 * 落とした山の数を返す。
 * @param {Dimension} dim @param {Vector3} pos @param {any[]} entries @param {{scatter?: number}} [o]
 */
export function dropLoot(dim, pos, entries, o) {
  const tables = tuning("LOOT_TABLES", FALLBACK_LOOT_TABLES);
  /** @type {any[]} */
  const list = [];
  for (const e of entries ?? []) {
    const tname = typeof e === "string" ? e.replace(/^table:/, "") : e && !Array.isArray(e) && e.table ? String(e.table) : "";
    if (tname) { for (const x of tables[tname] ?? []) list.push(x); } else list.push(e);
  }
  let n = 0;
  const s = o?.scatter ?? 0.3;
  for (const e of list) {
    const row = Array.isArray(e) ? e : [e?.id, e?.min, e?.max, e?.chance];
    const [id, mn, mx, pr] = row;
    if (typeof id !== "string" || !chance(Number(pr ?? 1))) continue;
    const count = clamp(randInt(Number(mn ?? 1), Number(mx ?? mn ?? 1)), 0, 64);
    if (count < 1) continue;
    try {
      dim.spawnItem(new ItemStack(id, count), { x: pos.x + rand(-s, s), y: pos.y + 0.4, z: pos.z + rand(-s, s) });
      n++;
    } catch (err) { warnOnce(`loot:${id}`, "ルートを出せない", id, err); }
  }
  return n;
}

/** 経験値のオーブ（spec の xp を数個のオーブに分ける）。 @param {Dimension} dim @param {Vector3} pos @param {number} xp */
export function dropXp(dim, pos, xp) {
  const total = Math.max(0, Math.round(xp));
  if (!total) return 0;
  const orbs = clamp(Math.ceil(total / 4), 1, 8);
  let n = 0;
  for (let i = 0; i < orbs; i++) {
    try { dim.spawnEntity("minecraft:xp_orb", { x: pos.x + rand(-0.4, 0.4), y: pos.y + 0.5, z: pos.z + rand(-0.4, 0.4) }); n++; } catch { break; }
  }
  return n;
}

// ---------------------------------------------------------------------------
//  死に方
// ---------------------------------------------------------------------------
/** 打たれた向き・部位の状態から nr:pose を選ぶ。 @param {Entity} z @param {Vector3} dir @param {KillInfo} info */
export function poseFrom(z, dir, info) {
  const parts = info.parts ?? {};
  const power = info.power ?? 1;
  if (info.overkill || (info.hit?.dtype === "blast" && power >= 0.7)) return POSE.BLOWN;
  if (parts.torso === "halved") return POSE.HALF;
  const legless = /^cut_/.test(parts.leg_r ?? "") && /^cut_/.test(parts.leg_l ?? "");
  if (info.state === "crawl" || legless) return POSE.CRAWL;
  if ((info.decap || info.crushed) && power < 1.3) return POSE.CRUMPLE;
  const l = dirToLocal(yawOf(z), dir);
  if (l[2] > 0.5) return POSE.FRONT;
  if (l[2] < -0.5) return POSE.BACK;
  return l[0] >= 0 ? POSE.RIGHT : POSE.LEFT;
}

/** 能力の引数（spec の abilities の上書き込み）。 @param {any} spec @param {string} key @returns {Record<string, any> | undefined} */
function abilityParams(spec, key) {
  const ap = spec?.ability_params?.[key];          // data/zombies.js の派生（語彙の既定 + 上書き）
  if (ap && typeof ap === "object") return { ...ap };
  for (const a of spec?.abilities ?? []) {
    if (a === key) return { ...(tuning("ABILITIES", {})[key]?.params ?? {}) };
    if (Array.isArray(a) && a[0] === key) return { ...(tuning("ABILITIES", {})[key]?.params ?? {}), ...(a[1] ?? {}) };
    if (a && typeof a === "object" && !Array.isArray(a) && a.key === key) return { ...(tuning("ABILITIES", {})[key]?.params ?? {}), ...(a.params ?? {}) };
  }
  return undefined;
}

/**
 * ゾンビを死なせる（applyHit が体力 0・即死部位で呼ぶ。罠・能力・コマンドから直接呼んでもよい）。
 * 処理したら true（既に死んでいれば false）。
 * @param {Entity} z @param {KillInfo} [info]
 */
export function kill(z, info = {}) {
  if (!valid(z) || !isZombie(z) || dead.has(z.id)) return false;
  dead.add(z.id);
  const spec = zombieSpec(z);
  const g = spec?.gore ?? {};
  const dim = z.dimension;
  const loc = z.location;
  const yaw = yawOf(z);
  const hit = info.hit ?? {};
  const dir = norm(info.dir ?? hit.dir ?? yawForward(yaw + 180), yawForward(yaw + 180));
  const power = clamp(info.power ?? hit.power ?? 1, 0, 3);
  const G = gore();
  setHp(z, 0);
  // BP: nr:on_death（AI を外し nr:state = dead）。イベントの set_property が遅れても困らないよう自分でも書く
  trigger(z, "nr:on_death");
  setProp(z, "nr:state", "dead");
  setProp(z, "nr:shock", 0);
  setProp(z, "nr:ability", 0);
  const pose = info.pose ?? poseFrom(z, dir, { ...info, power });
  setProp(z, "nr:pose", clamp(Math.round(pose), 0, 7));
  if (spec?.voice) sound(dim, `nr.z.${spec.voice}.death`, loc, { volume: 1, pitch: rand(0.9, 1.1) * (Number(spec.voice_pitch) || 1) });

  // ルート・経験値
  if (!info.noLoot) dropLoot(dim, loc, spec?.loot ?? []);
  if (!info.noXp && (info.byPlayer || isPlayer(info.attacker))) dropXp(dim, loc, Number(spec?.xp) || 0);

  // 死んだ時に出す汎用 gib（spec の gore.gib_extra）
  for (const p of g.gib_extra ?? []) if (chance(G)) spawnGib(z, Number(p), dir, 0.8 + 0.4 * power);

  const explodeKind = g.explode ? String(g.explode_kind ?? "none") : "";
  const overkill = !!info.overkill && G * 100 >= (Number(GT.overkill_burst_min_g) || 70);
  const ab = abilityParams(spec, "toxic_death_puff");
  if (ab) toxicCloud(dim, add(loc, { x: 0, y: 0.8, z: 0 }), { radius: Number(ab.radius) || 2.5, life: Number(ab.life) || 3, poisonS: Number(ab.poison_s) || 3, amp: 0, nauseaS: 0, dmg: 0 });

  /** @type {"normal" | "ash" | "melt" | "gone"} */
  let corpseKind = "normal";
  if (explodeKind || overkill) {
    corpseKind = "gone";
    bodyBurst(z, dir, power, info, overkill && !explodeKind ? "none" : explodeKind);
    if (explodeKind === "toxic") {
      const p = abilityParams(spec, "gas_cloud_death") ?? {};
      toxicCloud(dim, add(loc, { x: 0, y: 0.8, z: 0 }), { radius: Number(p.radius) || 4, life: Number(p.life) || 8, poisonS: Number(p.poison_s) || 4, amp: Number(p.poison_amp) || 1, nauseaS: Number(p.nausea_s) || 4, dmg: 1 });
    }
    if (explodeKind === "blast") {
      const p = abilityParams(spec, "detonate") ?? {};
      const fuse = Math.max(1, Math.round((Number(p.death_fuse) || 0.5) * 20));
      const at = add(loc, { x: 0, y: 0.9, z: 0 });
      later(fuse, () => detonate(dim, at, { radius: Number(p.radius) || 4, dmg: Number(p.dmg) || 12, infectedMult: Number(p.infected_mult) || 2, exclude: z.id }));
    }
    // 体が残らない: spec の loot に加えて「遺骸」の表（LOOT_TABLES.gore_remains）を半分の確率で
    if (!info.noLoot && G > 0.05 && chance(0.5)) dropLoot(dim, loc, ["gore_remains"]);
    later(1, () => despawn(z));
  } else {
    const burnt = (info.burn ?? Number(getProp(z, "nr:burn", 0))) >= 3;
    corpseKind = g.crumble || g.corpse === "ash" || burnt ? "ash" : g.corpse === "melt" ? "melt" : "normal";
    // ぐったり吹き飛ぶ（屋上の縁なら落ちる）
    const k = 0.18 + 0.3 * Math.min(power, 1.6);
    try { z.applyImpulse({ x: dir.x * k, y: 0.12 + 0.08 * Math.min(power, 1.5), z: dir.z * k }); } catch { /* 物理が無い */ }
    registerCorpse(z, corpseKind);
    if (corpseKind === "melt") sound(dim, "nr.fx.acid_sizzle", loc, { volume: 0.8 });
  }

  const h = info.hit ?? {};
  emit(EV.KILL, {
    zombie: z, key: z.typeId.slice(5), attacker: info.attacker ?? h.attacker, hit: info.hit, cause: info.cause ?? "hp", pos: loc,
    overkill, explode: explodeKind || undefined, decap: !!info.decap, crushed: !!info.crushed,
    headshot: !!(h.part === "head" || info.decap || info.crushed), environment: h.source === "trap", byPlayer: !!(info.byPlayer || isPlayer(info.attacker)),
    corpse: corpseKind !== "gone", pose,
  });
  if (corpseKind !== "gone") emit(EV.CORPSE, { zombie: z, created: true, kind: corpseKind });
  return true;
}

/**
 * プールを超える一撃でバニラの死が来た時（entityDie）: 全身が弾ける。gore.js が呼ぶ。
 * @param {Entity} z @param {KillInfo} [info]
 */
export function overkill(z, info = {}) {
  const id = safe("id", () => z.id);
  if (!id || dead.has(id)) return false;
  const live = valid(z);
  const key = live ? z.typeId.slice(5) : String(info.key ?? safe("type", () => z.typeId.slice(5)) ?? "");
  const dim = live ? z.dimension : info.dim;
  const loc = live ? z.location : info.at;
  if (!dim || !loc || !finiteVec(loc)) return false;   // 無効で、最後の位置も知らない
  dead.add(id);
  const spec = zombieSpec(key);
  const dir = norm(info.dir ?? { x: rand(-1, 1), y: 0.5, z: rand(-1, 1) });
  const G = gore();
  const big = G * 100 >= (Number(GT.overkill_burst_min_g) || 70);
  if (big && live) bodyBurst(z, dir, 1.5, info, "none");
  else if (big) bodyExplodeFx(dim, add(loc, { x: 0, y: 1, z: 0 }), 1.5, { kind: kindOf(key) });
  else burst(dim, add(loc, { x: 0, y: 1, z: 0 }), 1.5, { kind: kindOf(key) });
  if (big) sound(dim, "nr.gore.burst", loc, { volume: 1.4, pitch: rand(0.85, 1.05) });
  if (!info.noLoot) {
    dropLoot(dim, loc, spec?.loot ?? []);
    if (G > 0.05 && chance(0.5)) dropLoot(dim, loc, ["gore_remains"]);
  }
  const byPlayer = !!(info.byPlayer || isPlayer(info.attacker));
  if (!info.noXp && byPlayer) dropXp(dim, loc, Number(spec?.xp) || 0);
  emit(EV.KILL, { zombie: z, key, attacker: info.attacker, hit: info.hit, cause: "overkill", pos: loc, overkill: true, corpse: false, byPlayer, headshot: false });
  if (live) later(1, () => despawn(z));
  return true;
}

/**
 * 全身が弾ける（爆発・オーバーキル・破裂する種類）。部位の gib・肉片・血。
 * @param {Entity} z @param {Vector3} dir @param {number} power @param {KillInfo} info @param {string} kind explode_kind
 */
function bodyBurst(z, dir, power, info, kind) {
  const spec = zombieSpec(z);
  const g = spec?.gore ?? {};
  const G = gore();
  const dim = z.dimension;
  const parts = info.parts ?? {};
  let center = add(z.location, { x: 0, y: 1, z: 0 });
  try { center = partCenter(z, "torso", 0); } catch { /* 足元から */ }
  const blood = kindOf(z);
  bodyExplodeFx(dim, center, 1 + 0.3 * Math.min(power, 2), { kind: blood, wet: !!g.wet_burst });
  sound(dim, "nr.gore.burst", center, { volume: 1.4, pitch: rand(0.85, 1.05) });
  if (kind === "toxic") { particle(dim, "toxic_burst", center, { size: 1.4 }, PRIO.CRITICAL); sound(dim, "nr.fx.toxic_hiss", center, { volume: 1.2 }); }
  else if (kind === "acid") { particle(dim, "acid_splash", center, { radius: 2, life: 5 }, PRIO.HIGH); sound(dim, "nr.fx.acid_sizzle", center, { volume: 1.2 }); }
  else if (kind === "spores") particle(dim, "fungal_spores", center, { radius: 3 }, PRIO.HIGH);
  else if (kind === "water") burst(dim, center, 2.5, { kind: "water", prio: PRIO.CRITICAL });
  if (G <= 0.05) return;
  const up = norm({ x: dir.x, y: 0.8, z: dir.z });
  // 残っている部位は丸ごと飛ぶ
  /** @type {[string, number, number][]} [部位, 丸ごと, 下だけ] */
  const limbs = [["arm_r", GIB.arm_r, GIB.forearm_r], ["arm_l", GIB.arm_l, GIB.forearm_l], ["leg_r", GIB.leg_r, GIB.shin_r], ["leg_l", GIB.leg_l, GIB.shin_l]];
  for (const [part, whole, lower] of limbs) {
    const s = parts[part] ?? "intact";
    if (s === "cut_upper" || !chance(G)) continue;
    spawnGib(z, s === "cut_lower" ? GIB.chunk : chance(0.5) ? whole : lower, jitter(up), power * rand(0.8, 1.3));
  }
  const head = parts.head ?? "intact";
  if (head !== "severed" && head !== "crushed" && chance(G)) spawnGib(z, chance(0.6) ? GIB.head : GIB.brain, jitter(up), power * 1.2);
  const ex = GT.gib_count?.explode ?? [6, 14];
  const n = randInt(Number(ex[0]) || 6, Number(ex[1]) || 14);
  spawnChunks(z, n, up, power, [GIB.chunk, GIB.chunk, GIB.bone, GIB.guts, GIB.chunk, GIB.eye, GIB.brain], { at: center });
}
/** @param {Vector3} d */
function jitter(d) { return norm({ x: d.x + rand(-0.6, 0.6), y: d.y + rand(0, 0.5), z: d.z + rand(-0.6, 0.6) }); }

// ---------------------------------------------------------------------------
//  毒の雲・爆発（周りを巻き込む）
// ---------------------------------------------------------------------------
/** @typedef {{dim: Dimension, pos: Vector3, radius: number, until: number, poisonTicks: number, amp: number, nauseaTicks: number, dmg: number, nextFx: number}} Cloud */
/** @type {Cloud[]} */
const clouds = [];

/**
 * 毒の雲（中のプレイヤーに毒・吐き気、ゾンビには dtype toxic のダメージ = 耐性 toxic が 0 なら効かない）。
 * @param {Dimension} dim @param {Vector3} pos @param {{radius: number, life: number, poisonS: number, amp: number, nauseaS: number, dmg: number}} o
 */
export function toxicCloud(dim, pos, o) {
  if (clouds.length >= 12) clouds.shift();
  const t = now();
  clouds.push({ dim, pos, radius: o.radius, until: t + Math.round(o.life * 20), poisonTicks: Math.round(o.poisonS * 20), amp: clamp(Math.round(o.amp), 0, 4), nauseaTicks: Math.round(o.nauseaS * 20), dmg: o.dmg, nextFx: t });
  sound(dim, "nr.fx.toxic_hiss", pos, { volume: 1.0 });
}

system.runInterval(() => {
  if (!clouds.length) return;
  const t = now();
  for (let i = clouds.length - 1; i >= 0; i--) {
    const c = clouds[i];
    if (t >= c.until) { clouds.splice(i, 1); continue; }
    if (t >= c.nextFx) { c.nextFx = t + 20; particle(c.dim, "toxic_gas", c.pos, { radius: c.radius, life: 1.2 }, PRIO.NORMAL); }
    let near = [];
    try { near = c.dim.getEntities({ location: c.pos, maxDistance: c.radius, excludeTypes: ["nr:gib", "minecraft:item", "minecraft:xp_orb"] }); } catch { near = []; }
    for (const e of near) {
      if (isPlayer(e)) {
        try {
          if (c.poisonTicks > 0) e.addEffect("poison", c.poisonTicks, { amplifier: c.amp, showParticles: true });
          if (c.nauseaTicks > 0) e.addEffect("nausea", c.nauseaTicks, { amplifier: 0, showParticles: false });
        } catch { /* クリエイティブ等 */ }
      } else if (isZombie(e) && c.dmg > 0 && !isCorpse(e)) {
        hitOther(e, { dtype: "toxic", source: "toxic", damage: c.dmg, power: 0.2, weight: "light", dir: norm(sub(e.location, c.pos)) });
      }
    }
  }
}, 10);

/**
 * 爆発（破裂者の自爆・死んだ時の爆発）。感染者には × infectedMult、距離で減る。死体と gib も吹き飛ばす。
 * @param {Dimension} dim @param {Vector3} pos @param {{radius: number, dmg: number, infectedMult?: number, exclude?: string, attacker?: Entity}} o
 */
export function detonate(dim, pos, o) {
  if (!finiteVec(pos)) return;
  const r = Math.max(0.5, o.radius);
  particle(dim, "explosion", pos, { size: r / 2 }, PRIO.CRITICAL);
  particle(dim, "smoke_dark", pos, { size: r / 2, life: 3 }, PRIO.NORMAL);
  sound(dim, "nr.fx.explosion", pos, { volume: 2.5, pitch: rand(0.85, 1.0) });
  let near = [];
  try { near = dim.getEntities({ location: pos, maxDistance: r * 2.5, excludeTypes: ["minecraft:item", "minecraft:xp_orb"] }); } catch { near = []; }
  for (const e of near) {
    if (!valid(e) || e.id === o.exclude) continue;
    const d = dist(e.location, pos);
    if (isPlayer(e) && d <= r * 2.5) shake(/** @type {any} */ (e), clamp(1.2 * (1 - d / (r * 2.5)) + 0.2, 0.2, 2), 0.6);
    if (d > r) continue;
    const fall = 1 - d / r;
    const dir = norm(sub(add(e.location, { x: 0, y: 0.6, z: 0 }), pos), { x: 0, y: 1, z: 0 });
    if (e.typeId === "nr:gib") {
      try { e.applyImpulse({ x: dir.x * 0.8 * fall, y: 0.4 + 0.4 * fall, z: dir.z * 0.8 * fall }); } catch { /* 無効 */ }
    } else if (isZombie(e)) {
      hitOther(e, { dtype: "blast", source: "blast", weight: "heavy", damage: o.dmg * (o.infectedMult ?? 1) * fall, power: 0.3 + 1.0 * fall, dir, attacker: o.attacker });
    } else {
      try {
        e.applyDamage(Math.max(0.5, o.dmg * fall), { cause: EntityDamageCause.entityExplosion });
        if (isPlayer(e)) e.applyKnockback({ x: dir.x * 1.2 * fall, z: dir.z * 1.2 * fall }, 0.3 + 0.3 * fall);
      } catch { /* 無敵・クリエイティブ */ }
    }
  }
}

// ---------------------------------------------------------------------------
//  死体の 1 tick（落下・着地の衝撃・血だまり・寿命・灰・溶ける・蝿）
// ---------------------------------------------------------------------------
system.runInterval(() => {
  if (!corpses.size) return;
  const t = now();
  for (const [id, rec] of [...corpses]) {
    if (rec.settled && t < rec.nextCheck && t < rec.until) continue;
    safe("corpse-step", () => corpseStep(id, rec, t));
  }
}, 1);

/** @param {string} id @param {CorpseRec} rec @param {number} t */
function corpseStep(id, rec, t) {
  const e = rec.e;
  if (!valid(e)) { corpses.delete(id); return; }
  const dim = e.dimension;
  if (t >= rec.until) {
    corpses.delete(id);
    if (rec.kind === "ash") {
      particle(dim, "char_flakes", add(e.location, { x: 0, y: 0.3, z: 0 }), { count: 18, size: 1.1 }, PRIO.NORMAL);
      particle(dim, "smoke_dark", e.location, { size: 0.9, life: 2 }, PRIO.LOW);
      sound(dim, "nr.gore.body_fall", e.location, { volume: 0.5, pitch: 1.5 });
    } else if (rec.kind === "melt") {
      particle(dim, "acid_splash", e.location, { radius: 1.2, life: 4 }, PRIO.NORMAL);
    }
    despawn(e);
    emit(EV.CORPSE, { zombie: e, created: false, kind: rec.kind });
    return;
  }
  if (rec.kind === "melt" && t >= rec.nextFx) {
    rec.nextFx = t + 20;
    particle(dim, "smoke_dark", e.location, { size: 0.5, life: 1.5 }, PRIO.LOW);
  }
  if (rec.settled) {
    rec.nextCheck = t + 10;
    // 動かされた（蹴られた・爆風）ら物理を見直す
    const v = e.getVelocity();
    if (len(v) > 0.08) { rec.settled = false; rec.still = 0; }
    else if (rec.kind === "normal" && t - rec.born > 600 && t >= rec.nextFx) { rec.nextFx = t + randInt(80, 140); particle(dim, "flies", add(e.location, { x: 0, y: 0.4, z: 0 }), undefined, PRIO.LOW); }
    return;
  }
  const v = e.getVelocity();
  // 着地: 落ちていたのに縦の速さが消えた
  if (rec.prevVy < -0.25 && v.y > rec.prevVy * 0.3) {
    const impact = -rec.prevVy;
    sound(dim, "nr.gore.body_fall", e.location, { volume: clamp(impact, 0.4, 1.5), pitch: rand(0.85, 1.05) });
    if (impact > 0.6 && makesPools(rec.blood)) splatGround(dim, e.location, 1 + impact, { kind: rec.blood });
    if (impact > 0.85) {
      hitOther(e, { dtype: "blunt", source: "fall", weight: "heavy", damage: impact * 12, power: clamp(impact, 0.5, 2), dir: DOWN, parts: chance(0.5) ? ["leg_r", "leg_l"] : ["leg_r", "leg_l", "arm_r", "arm_l"], corpse: true });
      if (impact > 1.3) burst(dim, add(e.location, { x: 0, y: 0.3, z: 0 }), impact, { kind: rec.blood });
    }
  }
  const on = e.isOnGround;
  if ((on || Math.abs(v.y) < 0.01) && len(v) < 0.04) {
    if (++rec.still >= 6) {
      rec.settled = true;
      rec.nextCheck = t + 10;
      if (!rec.pooled && rec.kind !== "ash") {
        rec.pooled = true;
        pool(dim, e.location, clamp(1.1 * rec.bleed, 0.4, 2.5), { kind: rec.blood });
      }
    }
  } else rec.still = 0;
  rec.prevVy = v.y;
}

// ---------------------------------------------------------------------------
//  読み込み・消えた
// ---------------------------------------------------------------------------
world.afterEvents.entityLoad.subscribe((ev) => {
  const e = ev.entity;
  if (!isZombie(e) || corpses.has(e.id)) return;
  if (getProp(e, "nr:state", "normal") !== "dead") return;
  dead.add(e.id);
  registerCorpse(e, "normal", Math.round(corpseTicks() / 2));
});

world.afterEvents.entityRemove.subscribe((ev) => {
  if (!ev.typeId.startsWith("nr:z_")) return;
  corpses.delete(ev.removedEntityId);
  dead.delete(ev.removedEntityId);
});
