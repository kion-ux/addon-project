// ===========================================================================
//  NIGHT RUNNER: 感染都市 — ゴアの結果の決定と適用（DESIGN §4 / §12）
//
//  applyHit(zombie, hit) が**ゾンビへのダメージの唯一の入口**。体力・部位・装甲・ゴア・死亡・演出・
//  バスの通知がここで一度に決まる。hit の形（DESIGN §12）:
//    {attacker?, part?, sub?, point?, dir, dtype, weight, damage, power,
//     source: "melee"|"projectile"|"hitscan"|"blast"|"trap"|"fire"|"shock"|"toxic"|"fall", weapon?, mods?}
//  追加で読むもの（無くてよい）: corpse, crit, heavy, gorePower, outcome, parts, knockdown, stunTicks, burn,
//  noGore, noKnockback, noAnim, noVanilla（細かくは reference/nr_scripts.md）。
//
//  * 部位の状態の「真実」はプロパティ。ただし setProperty は次の tick まで getProperty に出ないので、
//    同じ tick の中ではこのファイルの書き込みの控え（rec.w）を正とする（script_api.md §4.3）。
//  * entityHurt（バニラの被弾）はここで hit に直して applyHit へ流す。プレイヤーの近接は
//    setMeleeResolver() で登録された関数（combat/melee.js）が武器から hit を作る（無ければ既定の解決）。
//  * 死体（nr:state = dead）は damage_sensor で entityHurt が来ないので、entityHitEntity /
//    projectileHitEntity から corpse: true で流す（死体の切断）。
//  * プールを超える一撃（バニラの死）は entityDie → death.overkill（全身が弾ける）。
//  * 能力（zombies/abilities.js）は onBeforeHit() で被弾を細工でき（盾・骨の兜・回避・重い体）、
//    バスの weakspot / armor_break / hit を聞いて発動する。
// ===========================================================================
import { world, system, EquipmentSlot } from "@minecraft/server";
import { ZOMBIES, GORE_DEFAULTS, PROPERTY_ENUMS } from "../data/zombies.js";
import { DTYPE_OUTCOMES, COMBAT_TUNING } from "../data/settings.js";
import { WEAPONS, WEAPON_BY_ID } from "../data/weapons.js";
import { MOD_BY_KEY } from "../data/mods.js";
import { gore } from "../core/settings.js";
import { emit, EV } from "../core/bus.js";
import { particle, sound, zombieAnim, PRIO } from "../core/fx.js";
import {
  zombieSpec, hpOf, maxHpOf, addHp, setHp, initHp, resetPool, consumeReservation, hurtVanilla, HP_KEY,
} from "../core/hp.js";
import {
  valid, norm, flat, add, sub, dot, clamp, clamp01, rand, randInt, chance, now, getProp, setProp, trigger,
  isPlayer, isZombie, yawOf, yawForward, warnOnce, safe, finiteVec, dpNum, UP, DOWN,
} from "../core/util.js";
import { locate, groupOf, sideOf, partCenter, locatorPos, inZone, PARTS } from "./hitloc.js";
import { spawnGib, spawnChunks, GIB } from "./gibs.js";
import {
  hitFx, severFx, headExplodeFx, burst, spray, screenBlood, kindOf, bleedOf, GT,
} from "./blood.js";
import { kill, overkill, isCorpse, setHitHandler } from "./death.js";

/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Dimension} Dimension */

/**
 * @typedef {object} Hit
 * @property {Entity} [attacker]
 * @property {string} [part]          head / torso / arm_r / arm_l / leg_r / leg_l（無ければ point・レイ・高さで決める）
 * @property {number} [sub]           0 = 上の箱、1 = 下の箱（前腕・脛）
 * @property {Vector3} [point]        当たった点（ワールド）
 * @property {Vector3} [dir]          打たれた向き（攻撃者 → ゾンビ）
 * @property {string} [dtype]         slash / blunt / pierce / blast / fire / shock / toxic / uv
 * @property {string} [weight]        light / medium / heavy
 * @property {number} [damage]        体力の点（耐性・部位の倍率の前）
 * @property {number} [power]         0..2（1 = 普通の一撃。吹き飛び・血・gib の勢い）
 * @property {string} [source]        melee / projectile / hitscan / blast / trap / fire / shock / toxic / fall
 * @property {any} [weapon]           data/weapons.js の武器（WEAPON_BY_ID の値）か武器の ID
 * @property {Record<string, number>} [mods]  {改造の鍵: 段階}
 * @property {boolean} [corpse]       死体への一撃（体力は減らない・切断だけ）
 * @property {boolean} [crit]         会心（無ければ COMBAT_TUNING.crit_base_chance で振る）
 * @property {boolean} [heavy]        溜め攻撃（COMBAT_TUNING.heavy）
 * @property {number} [gorePower]     切断・破壊の起きやすさ 0..1.2（無ければ武器の gore_power）
 * @property {string | Record<string, string | [string, number]>} [outcome]  結果の指定（罠・とどめ）
 * @property {string[]} [parts]       複数の部位に同時に効く（落下・爆発）。体力は一度だけ減る
 * @property {boolean} [knockdown]    倒す（nr:state down）
 * @property {number} [stunTicks]     感電の長さ
 * @property {number} [burn]          nr:burn をこの段階まで上げる（火の改造の sets_burn）
 * @property {boolean} [noGore]       部位の状態を進めない
 * @property {boolean} [noKnockback]
 * @property {boolean} [noAnim]
 * @property {boolean} [noVanilla]    バニラの被弾（赤い点滅）を出さない
 */

// ---------------------------------------------------------------------------
//  表
// ---------------------------------------------------------------------------
/** @type {any} */
const PE = PROPERTY_ENUMS ?? {};
const HEAD_STATES = PE.head ?? ["intact", "wounded", "jawless", "cracked", "severed", "crushed"];
const LIMB_STATES = PE.arm_r ?? ["intact", "wounded", "broken", "cut_lower", "cut_upper"];
const TORSO_STATES = PE.torso ?? ["intact", "slashed", "gutted", "halved"];
const STATES = PE.state ?? ["normal", "crawl", "climb", "stagger", "down", "special", "dead"];
/** 部位 → 取りうる値。 */
const ENUM_OF = { head: HEAD_STATES, torso: TORSO_STATES, arm_r: LIMB_STATES, arm_l: LIMB_STATES, leg_r: LIMB_STATES, leg_l: LIMB_STATES };
/** @type {Record<string, Record<string, number>>} 状態の重さ（下がる方向には変えない） */
const RANK = {
  head: { intact: 0, wounded: 1, jawless: 2, cracked: 3, severed: 4, crushed: 4 },
  limb: { intact: 0, wounded: 1, broken: 2, cut_lower: 3, cut_upper: 4 },
  torso: { intact: 0, slashed: 1, gutted: 2, halved: 3 },
};
/** 切断・破壊（ゴアレベルの指数 sever_mult_exp と spec の sever_mult が効く結果）。 */
const DISMEMBER = new Set(["cut_lower", "cut_upper", "severed", "crushed", "halved"]);
const FINAL_HEAD = new Set(["severed", "crushed"]);

// DESIGN §4 の表（ダメージ種別 × 部位）。weak = 軽い一撃 / mid = 中くらい・累積 / strong = 強い一撃・部位体力を超えた。
// 実際に使えるのは DTYPE_OUTCOMES（spec）に載っている結果だけ（＋どの種別でも起きる wounded / slashed）。
// strong の "cut" は当たった箱で決める（前腕・脛 = cut_lower、上腕・太腿 = cut_upper）。
/** @type {Record<string, Record<string, {weak?: string, mid?: string, strong?: string}>>} */
const TABLE = {
  slash: {
    head: { weak: "wounded", mid: "jawless", strong: "severed" },
    arm: { weak: "wounded", mid: "wounded", strong: "cut" }, leg: { weak: "wounded", mid: "wounded", strong: "cut" },
    torso: { weak: "slashed", mid: "gutted", strong: "halved" },
  },
  blunt: {
    head: { weak: "wounded", mid: "cracked", strong: "crushed" },
    arm: { weak: "wounded", mid: "broken", strong: "broken" }, leg: { weak: "wounded", mid: "broken", strong: "broken" },
    torso: {},
  },
  pierce: {
    head: { weak: "wounded", mid: "cracked", strong: "crushed" },
    arm: { weak: "wounded", mid: "wounded", strong: "cut_lower" }, leg: { weak: "wounded", mid: "wounded", strong: "cut_lower" },
    torso: { weak: "slashed", mid: "slashed", strong: "slashed" },
  },
  blast: {
    head: { weak: "wounded", mid: "cracked", strong: "crushed" },
    arm: { weak: "wounded", mid: "broken", strong: "cut_upper" }, leg: { weak: "wounded", mid: "broken", strong: "cut_upper" },
    torso: { weak: "slashed", mid: "gutted", strong: "halved" },
  },
};
const DTYPES = ["slash", "blunt", "pierce", "blast", "fire", "shock", "toxic", "uv"];
const WEIGHTS = ["light", "medium", "heavy"];
const SOURCES = ["melee", "projectile", "hitscan", "blast", "trap", "fire", "shock", "toxic", "fall"];

/** spec の DTYPE_OUTCOMES で許された結果か（wounded / slashed はその種別に結果が一つでもあれば可）。 */
function allowed(dtype, group, state) {
  /** @type {any} */
  const tbl = DTYPE_OUTCOMES ?? {};
  const list = tbl[dtype]?.[group] ?? [];
  if (!list.length) return false;
  if (list.includes(state)) return true;
  return group === "torso" ? state === "slashed" : state === "wounded";
}

/** @type {any} */
const CT = COMBAT_TUNING ?? {};
const PART_HP_FRAC = { head: 0.45, arm: 0.35, leg: 0.4, torso: 0.9, ...(CT.part_hp_frac ?? {}) };
const HITZONE = { head: 2.0, torso: 1.0, arm: 0.7, leg: 0.8, ...(CT.hitzone_mult ?? {}) };
const ARMOR_T = { slash_mult: 0.3, pierce_mult: 0.4, blunt_mult: 0.7, blast_mult: 0.8, ...(CT.armor ?? {}) };
const MIN_G = { ...(GT.min_g ?? {}) };
const SEVER_EXP = Number(GT.sever_mult_exp) || 0.8;

// 飛び道具 → それを撃つ武器（矢 = 弓 など）
/** @type {Record<string, any>} */
const WEAPON_OF_PROJ = {};
for (const w of /** @type {any[]} */ (WEAPONS ?? [])) if (w && w.projectile && !WEAPON_OF_PROJ[w.projectile]) WEAPON_OF_PROJ[w.projectile] = w;

/** 全ゾンビの ID（entityHurt などのフィルタ）。 */
export const ZOMBIE_IDS = Object.freeze(/** @type {any[]} */ (ZOMBIES ?? []).map((z) => String(z.id ?? `nr:z_${z.key}`)));

/** spec の gore（GORE_DEFAULTS で埋めたもの）。 @param {Entity | string} z @returns {Record<string, any>} */
export function goreSpec(z) {
  const s = zombieSpec(/** @type {any} */ (z));
  return { .../** @type {any} */ (GORE_DEFAULTS ?? {}), ...(s?.gore ?? {}) };
}

// ---------------------------------------------------------------------------
//  ゾンビごとの控え（同じ tick の書き込み・累積ダメージ・装甲の耐久・タイマー）
// ---------------------------------------------------------------------------
/**
 * @typedef {object} ZRec
 * @property {Record<string, {t: number, v: any}>} w   このファイルが書いたプロパティ（同じ tick の読み直し用）
 * @property {Record<string, number>} dmg              部位ごとの累積ダメージ
 * @property {number} armorHp                          今の装甲の段階の残り耐久
 * @property {number} wounds
 * @property {number} fireDmg
 * @property {Set<number>} weakUsed
 * @property {number} weakDmg
 * @property {number} lastVoice
 * @property {number} lastAnim
 * @property {number} lastLiveHit
 * @property {string} lastAttacker
 * @property {Vector3} lastLoc
 * @property {Dimension | undefined} dim
 */
/** @type {Map<string, ZRec>} */
const recs = new Map();

/** @param {Entity} z @returns {ZRec} */
function rec(z) {
  let r = recs.get(z.id);
  if (!r) {
    const g = goreSpec(z);
    const ah = dpNum(z, "nr:armor_hp", NaN);
    r = {
      w: {}, dmg: { head: 0, torso: 0, arm_r: 0, arm_l: 0, leg_r: 0, leg_l: 0 },
      armorHp: Number.isFinite(ah) ? ah : armorStageHp(g), wounds: 0, fireDmg: 0, weakUsed: new Set(), weakDmg: 0,
      lastVoice: -99, lastAnim: -99, lastLiveHit: -99, lastAttacker: "", lastLoc: { x: 0, y: 0, z: 0 }, dim: undefined,
    };
    recs.set(z.id, r);
  }
  try { r.lastLoc = z.location; r.dim = z.dimension; } catch { /* 無効 */ }
  return r;
}
/** @param {Record<string, any>} g */
function armorStageHp(g) { return Number(g.armor_hp) > 0 ? Number(g.armor_hp) : 10; }

/** プロパティを読む（このファイルが 1 tick 以内に書いた値を優先）。 @param {Entity} z @param {ZRec} r @param {string} name @param {any} def */
function rd(z, r, name, def) {
  const w = r.w[name];
  if (w && now() - w.t <= 1) return w.v;
  return getProp(z, name, def);
}
/** プロパティを書く（同じ値なら書かない）。書いたら true。 @param {Entity} z @param {ZRec} r @param {string} name @param {any} v */
function wr(z, r, name, v) {
  if (rd(z, r, name, undefined) === v) return false;
  if (!setProp(z, name, v)) return false;
  r.w[name] = { t: now(), v };
  return true;
}

/** いまの部位の状態。 @param {Entity} z @param {string} part */
export function partState(z, part) {
  if (!valid(z)) return "intact";
  return String(rd(z, rec(z), `nr:${part}`, "intact"));
}
/** 全部位の状態 {head, torso, arm_r, arm_l, leg_r, leg_l}。 @param {Entity} z @returns {Record<string, string>} */
export function partsOf(z) {
  /** @type {Record<string, string>} */
  const out = {};
  for (const p of PARTS) out[p] = partState(z, p);
  return out;
}
/** nr:state（同じ tick の書き込みを含む）。 @param {Entity} z */
export function stateOf(z) { return valid(z) ? String(rd(z, rec(z), "nr:state", "normal")) : "dead"; }
/** nr:armor。 @param {Entity} z */
export function armorOf(z) { return valid(z) ? Number(rd(z, rec(z), "nr:armor", 3)) : 0; }

/**
 * 部位の状態を直接書く（能力の生え戻り・とどめ・pre_damage）。enum に無い値は書かない。書いたら true。
 * @param {Entity} z @param {string} part @param {string} value
 */
export function setPart(z, part, value) {
  if (!valid(z) || !ENUM_OF[part]?.includes(value)) { warnOnce(`setPart:${part}:${value}`, "setPart: 無い部位か値", part, value); return false; }
  return wr(z, rec(z), `nr:${part}`, value);
}
/**
 * nr:state を書く（ほかのモジュールもここを通すと同じ tick の読み直しが正しくなる）。crawl は BP の nr:to_crawl も呼ぶ。
 * @param {Entity} z @param {string} state
 */
export function setState(z, state) {
  if (!valid(z) || !STATES.includes(state)) { warnOnce(`setState:${state}`, "setState: 無い値", state); return false; }
  const r = rec(z);
  if (rd(z, r, "nr:state", "normal") === "dead" && state !== "dead") return false;
  if (state === "crawl") trigger(z, "nr:to_crawl");
  return wr(z, r, "nr:state", state);
}
/** nr:armor を書く（0..3。能力の破裂・ボスの段階）。 @param {Entity} z @param {number} n */
export function setArmor(z, n) {
  if (!valid(z)) return false;
  const r = rec(z);
  const v = clamp(Math.round(n), 0, 3);
  const was = Number(rd(z, r, "nr:armor", 3));
  if (!wr(z, r, "nr:armor", v)) return false;
  if (v < was) r.armorHp = armorStageHp(goreSpec(z));
  return true;
}

// ---------------------------------------------------------------------------
//  外から差し込む関数（近接・飛び道具の解決、被弾の細工）
// ---------------------------------------------------------------------------
/**
 * @typedef {object} ResolveInfo
 * @property {number} damage   バニラが報告したダメージ（entityHurt.damage。死体の一撃では武器から）
 * @property {string} cause    EntityDamageCause の値
 * @property {boolean} corpse  死体への一撃
 * @property {Entity} [projectile]
 * @property {Vector3} [point]
 * @property {Vector3} [dir]
 */
/** @typedef {(attacker: Player, zombie: Entity, info: ResolveInfo) => (Hit | false | null | undefined)} Resolver */
/** @type {Resolver | undefined} */
let meleeResolver;
/** @type {Resolver | undefined} */
let projectileResolver;

/**
 * プレイヤーの近接の hit を作る関数を登録する（combat/melee.js）。戻り値: hit（既定の値に上書きされる）/
 * false（この被弾は無視。combat が自分で applyHit する）/ undefined（既定の解決 defaultMeleeHit を使う）。
 * @param {Resolver | undefined} fn
 */
export function setMeleeResolver(fn) { meleeResolver = fn; }
/** 飛び道具（entityHurt の projectile）の hit を作る関数を登録する。戻り値の意味は setMeleeResolver と同じ。 @param {Resolver | undefined} fn */
export function setProjectileResolver(fn) { projectileResolver = fn; }

/**
 * @typedef {object} HitCtx
 * @property {Entity} zombie
 * @property {Hit} hit
 * @property {string} part
 * @property {string} group
 * @property {number} sub
 * @property {Vector3} point
 * @property {number} damage      体力へ入る予定の点（耐性・部位・弱点・会心の後、装甲の前）
 * @property {boolean} cancel     true: 何も起きない（回避）
 * @property {boolean} deflect    true: 弾いた（火花だけ。盾・骨の兜）
 * @property {boolean} noGore
 * @property {boolean} noStagger
 * @property {boolean} noKnockback
 * @property {boolean} corpse
 */
/** @type {Set<(z: Entity, ctx: HitCtx) => void>} */
const hooks = new Set();
/**
 * 被弾を細工する関数を登録する（能力の盾・骨の兜・回避・重い体）。ctx を書き換える。戻り値を呼ぶと解除。
 * @param {(z: Entity, ctx: HitCtx) => void} fn @returns {() => void}
 */
export function onBeforeHit(fn) { hooks.add(fn); return () => { hooks.delete(fn); }; }

// ---------------------------------------------------------------------------
//  武器 → hit（既定の解決）
// ---------------------------------------------------------------------------
/** @param {any} w */
function weaponOf(w) { return typeof w === "string" ? /** @type {any} */ (WEAPON_BY_ID)?.[w] : w && typeof w === "object" ? w : undefined; }

/** バニラの道具の種別。 @param {string} id @returns {{dtype: string, weight: string}} */
function vanillaTool(id) {
  if (/_sword$/.test(id)) return { dtype: "slash", weight: "medium" };
  if (/_axe$/.test(id)) return { dtype: "slash", weight: "heavy" };
  if (id === "minecraft:trident") return { dtype: "pierce", weight: "medium" };
  if (id === "minecraft:mace") return { dtype: "blunt", weight: "heavy" };
  if (/_(pickaxe|shovel|hoe)$/.test(id)) return { dtype: "blunt", weight: "medium" };
  return { dtype: "blunt", weight: "light" };
}

/** 武器（data/weapons.js）から hit の中身。 @param {any} w @param {number} damage @returns {Hit} */
function weaponHit(w, damage) {
  const ranged = w.kind && w.kind !== "melee";
  if (ranged && w.kind !== "throwable") return { dtype: "blunt", weight: "light", damage: Math.max(1, damage), weapon: w, gorePower: 0.2 };
  return { dtype: DTYPES.includes(w.dtype) ? w.dtype : "blunt", weight: WEIGHTS.includes(w.weight) ? w.weight : "medium", damage, weapon: w };
}

/**
 * プレイヤーの近接の既定の解決: 手の武器（WEAPON_BY_ID）の dtype・weight・gore_power、改造（ItemStack の nr:mods）。
 * NR の武器でなければバニラの道具から（剣 = 斬、斧 = 重い斬、素手 = 軽い打撃）。
 * @param {Player} p @param {Entity} z @param {ResolveInfo} info @returns {Hit}
 */
export function defaultMeleeHit(p, z, info) {
  let item;
  try { item = p.getComponent("minecraft:equippable")?.getEquipment(EquipmentSlot.Mainhand); } catch { item = undefined; }
  const id = item?.typeId ?? "";
  const w = weaponOf(id);
  /** @type {Hit} */
  let h;
  if (w) {
    const dmg = info.damage > 1 ? info.damage : Number(w.damage) || 1;
    h = weaponHit(w, dmg);
    try {
      const raw = item?.getDynamicProperty("nr:mods");
      if (typeof raw === "string" && raw) h.mods = JSON.parse(raw);
    } catch { /* 壊れた JSON は無視 */ }
  } else {
    const t = vanillaTool(id);
    h = { ...t, damage: Math.max(0.5, info.damage) };
  }
  let dir;
  try { dir = p.getViewDirection(); } catch { dir = undefined; }
  return { ...h, attacker: p, source: "melee", dir };
}

/** 飛び道具の既定の解決（撃った武器を飛び道具の ID から引く。矢・トライデントはバニラ）。 @param {Entity | undefined} attacker @param {Entity} z @param {ResolveInfo} info @returns {Hit} */
function defaultProjectileHit(attacker, z, info) {
  const pid = info.projectile?.typeId ?? "";
  const w = WEAPON_OF_PROJ[pid];
  /** @type {Hit} */
  const h = w ? weaponHit(w, Math.max(0.5, info.damage)) : { dtype: "pierce", weight: pid === "minecraft:trident" ? "heavy" : "medium", damage: Math.max(0.5, info.damage) };
  return { ...h, attacker, source: "projectile", point: info.point, dir: info.dir };
}

// ---------------------------------------------------------------------------
//  applyHit
// ---------------------------------------------------------------------------
/**
 * @typedef {object} HitResult
 * @property {Entity} zombie
 * @property {string} key
 * @property {string} part
 * @property {number} sub
 * @property {Vector3} point
 * @property {string} dtype
 * @property {string} weight
 * @property {string} source
 * @property {Entity | undefined} attacker
 * @property {number} damage       体力から引いた点（死体・弾かれた時は 0）
 * @property {number} hp           残りの体力
 * @property {number} maxHp
 * @property {boolean} killed
 * @property {boolean} corpse
 * @property {boolean} armored     装甲・盾に止められた
 * @property {boolean} armorBroke
 * @property {boolean} deflected
 * @property {boolean} blocked     onBeforeHit が取り消した
 * @property {boolean} crit
 * @property {boolean} backstab
 * @property {any} weak            当たった弱点（spec の weak_spots の 1 つ）
 * @property {{part: string, from: string, to: string}[]} changes
 * @property {string[]} severed
 * @property {boolean} decap
 * @property {boolean} crushed
 * @property {boolean} headshot
 * @property {boolean} gutted
 * @property {boolean} halved
 * @property {boolean} staggered
 * @property {boolean} knockdown
 * @property {boolean} crawl
 * @property {Hit} hit
 */

let depth = 0;

/**
 * ゾンビ（死体も）に一撃を入れる。ゾンビへのダメージは必ずここを通す（DESIGN §12）。
 * before イベントの中から呼ばない（system.run へ）。結果を返す（ゾンビでなければ undefined）。
 * @param {Entity} zombie @param {Hit} hitIn @returns {HitResult | undefined}
 */
export function applyHit(zombie, hitIn) {
  if (!valid(zombie) || !isZombie(zombie) || !hitIn) return undefined;
  if (depth > 4) return undefined;            // 爆発の連鎖などの暴走よけ
  depth++;
  try { return applyHitInner(zombie, hitIn); } finally { depth--; }
}

/** @param {Entity} z @param {Hit} hitIn @returns {HitResult | undefined} */
function applyHitInner(z, hitIn) {
  const r = rec(z);
  const t = now();
  const g = goreSpec(z);
  const spec = zombieSpec(z);
  /** @type {Hit} */
  const hit = { ...hitIn };
  hit.dtype = DTYPES.includes(String(hit.dtype)) ? String(hit.dtype) : "blunt";
  hit.weight = WEIGHTS.includes(String(hit.weight)) ? String(hit.weight) : "medium";
  hit.source = SOURCES.includes(String(hit.source)) ? String(hit.source) : (hit.dtype === "blast" ? "blast" : "melee");
  const w = weaponOf(hit.weapon);
  const damage0 = Math.max(0, Number.isFinite(hit.damage) ? Number(hit.damage) : Number(w?.damage) || 1);
  const power = clamp(Number.isFinite(hit.power) ? Number(hit.power) : hit.weight === "heavy" ? 1.35 : hit.weight === "light" ? 0.7 : 1.0, 0, 3);
  const attacker = valid(hit.attacker) ? hit.attacker : undefined;
  const state0 = String(rd(z, r, "nr:state", "normal"));
  const corpse = !!hit.corpse || state0 === "dead" || isCorpse(z);
  // 向き（攻撃者 → ゾンビ。無ければゾンビの後ろ向き）
  let dir = finiteVec(hit.dir) ? norm(/** @type {Vector3} */ (hit.dir)) : undefined;
  if (!dir && attacker) { try { dir = norm(sub(z.location, attacker.location), yawForward(yawOf(z) + 180)); } catch { dir = undefined; } }
  if (!dir && hit.point) dir = norm(sub(z.location, hit.point), yawForward(yawOf(z) + 180));
  dir = dir ?? yawForward(yawOf(z) + 180);
  hit.dir = dir;

  // ---- 部位 ----
  const ph = locate(z, hit, { state: corpse ? "dead" : state0, pose: Number(getProp(z, "nr:pose", 0)) });
  const part = ph.part, group = groupOf(part);
  const point = ph.point;
  // 複数の部位（落下・爆発）。部位も点も無い爆発は全身に効く
  const multi = Array.isArray(hit.parts) ? hit.parts.filter((p) => PARTS.includes(p))
    : hit.dtype === "blast" && !hitIn.part && !hitIn.point ? [...PARTS] : [];
  hit.part = part;     // 決まった部位（bus・死亡の通知で使う）

  // ---- ダメージ（耐性・部位・弱点・会心・背後） ----
  const resist = spec?.resist ?? {};
  const rmul = hit.dtype === "uv" ? Number(resist.uv ?? 0) : Number(resist[hit.dtype] ?? 1);
  const partMul = part === "head" ? Number(g.head_mult ?? HITZONE.head) : Number(HITZONE[group] ?? 1);
  let dmg = damage0 * (Number.isFinite(rmul) ? Math.max(0, rmul) : 1) * (multi.length ? 1 : partMul);
  const ranged = hit.source === "projectile" || hit.source === "hitscan";
  // 弱点（spec の weak_spots。zone は hitloc.inZone）
  /** @type {any} */
  let weak;
  let weakIdx = -1;
  (g.weak_spots ?? []).forEach((ws, i) => {
    if (weak || !ws || ws.part !== part) return;
    if (!inZone(z, ph, String(ws.zone ?? "any"), ranged || hit.dtype === "pierce")) return;
    weak = ws; weakIdx = i;
  });
  const weakFirst = weak ? !r.weakUsed.has(weakIdx) : false;
  if (weak && (weakFirst || !weak.once)) dmg *= Math.max(1, Number(weak.mult) || 1);
  let crit = false, backstab = false;
  if (!corpse && hit.source === "melee") {
    crit = hit.crit ?? chance(Number(CT.crit_base_chance) || 0.05);
    if (crit) dmg *= Math.max(1, Number(w?.crit_mult) || 1.5);
    if (attacker) {
      const fwd = yawForward(yawOf(z));
      if (dot(flat(dir), fwd) > 0.5) { backstab = true; dmg *= Math.max(1, Number(CT.backstab_mult) || 1.5); }
    }
  } else if (hit.crit) { crit = true; dmg *= Math.max(1, Number(w?.crit_mult) || 1.5); }
  if (hit.heavy) dmg *= Math.max(1, Number(CT.heavy?.damage_mult) || 1.6);
  // 改造（ゴアに効く分だけ。持続ダメージ・連鎖は combat/mods.js）
  const mods = hit.mods && typeof hit.mods === "object" ? hit.mods : {};
  const tier = (/** @type {string} */ key) => {
    const lv = Number(mods[key]) || 0;
    if (lv <= 0) return undefined;
    /** @type {any} */
    const m = /** @type {any} */ (MOD_BY_KEY)?.[key];
    return m?.tiers?.find((x) => x.level === lv) ?? m?.tiers?.[Math.min(lv, m?.tiers?.length ?? 1) - 1];
  };
  const bleedMod = tier("bleed"), impactMod = tier("impact");
  let gp = Number.isFinite(hit.gorePower) ? Number(hit.gorePower) : Number.isFinite(w?.gore_power) ? Number(w.gore_power)
    : ({ slash: 0.6, blunt: 0.5, pierce: 0.35, blast: 1.0 }[hit.dtype] ?? 0) + (hit.weight === "heavy" ? 0.2 : hit.weight === "light" ? -0.15 : 0);
  gp += Number(bleedMod?.gore_power_add) || 0;
  if (hit.heavy) gp += Number(CT.heavy?.gore_add) || 0.2;
  gp = clamp(gp, 0, 1.3);

  // ---- 細工（能力）----
  /** @type {HitCtx} */
  const ctx = { zombie: z, hit, part, group, sub: ph.sub, point, damage: dmg, cancel: false, deflect: false,
    noGore: !!hit.noGore, noStagger: false, noKnockback: !!hit.noKnockback, corpse };
  for (const fn of hooks) safe("onBeforeHit", () => fn(z, ctx));
  dmg = Math.max(0, Number(ctx.damage) || 0);

  /** @type {HitResult} */
  const res = {
    zombie: z, key: z.typeId.slice(5), part, sub: ph.sub, point, dtype: hit.dtype, weight: hit.weight, source: hit.source,
    attacker, damage: 0, hp: hpOf(z), maxHp: maxHpOf(z), killed: false, corpse, armored: false, armorBroke: false,
    deflected: false, blocked: false, crit, backstab, weak, changes: [], severed: [], decap: false, crushed: false,
    headshot: false, gutted: false, halved: false, staggered: false, knockdown: false, crawl: false, hit,
  };
  if (ctx.cancel) { res.blocked = true; emit(EV.HIT, res); return res; }
  if (weak) {
    r.weakUsed.add(weakIdx);
    emit(EV.WEAKSPOT, { zombie: z, part, zone: weak.zone, ability: weak.ability ?? undefined, once: !!weak.once, first: weakFirst, attacker, hit, corpse });
  }
  if (!corpse && attacker) { r.lastLiveHit = t; r.lastAttacker = attacker.id; }

  const dim = z.dimension;
  const G = gore();
  const kind = kindOf(z);

  // ---- 弾いた（盾・骨の兜）----
  if (ctx.deflect) {
    res.deflected = true; res.armored = true;
    particle(dim, "hit_spark", point, { dx: -dir.x, dy: -dir.y, dz: -dir.z }, PRIO.HIGH);
    sound(dim, "nr.w.hit_metal", point, { volume: 1, pitch: rand(0.9, 1.15) });
    if (!corpse && !hit.noAnim) oneShot(z, r, `react_${part}`);
    emit(EV.HIT, res);
    return res;
  }

  // ---- 装甲（gore.armored・nr:armor の段階）----
  let armor = Number(rd(z, r, "nr:armor", 3));
  const armoredPart = (/** @type {string} */ p) => (g.armored ?? []).includes(p) && armor >= (Number(g.armor_strip?.[p]) || 1);
  const shielded = !corpse && armoredPart(part) && hit.dtype !== "uv";
  if (shielded) {
    res.armored = true;
    const brk = Number(g.armor_break?.[hit.dtype] ?? 0.5);
    r.armorHp -= dmg * Math.max(0, brk);
    const physical = ["slash", "pierce", "blunt", "blast"].includes(hit.dtype);
    const pass = physical ? clamp((Number(g.armor_mult ?? 0.25) + Number(ARMOR_T[`${hit.dtype}_mult`] ?? 0.5)) / 2, 0, 1)
      : Math.max(Number(g.armor_mult ?? 0.25), 0.5);
    dmg *= pass;
    particle(dim, "hit_spark", point, { dx: -dir.x, dy: -dir.y, dz: -dir.z }, PRIO.HIGH);
    sound(dim, hit.dtype === "blunt" ? "nr.fx.metal_clang" : "nr.w.hit_metal", point, { volume: 1, pitch: rand(0.85, 1.15) });
    if (r.armorHp <= 0 && armor > 0) {
      armor -= 1;
      r.armorHp = armorStageHp(g);
      wr(z, r, "nr:armor", armor);
      res.armorBroke = true;
      for (let i = 0; i < 3; i++) particle(dim, "hit_spark", add(point, { x: rand(-0.3, 0.3), y: rand(-0.2, 0.3), z: rand(-0.3, 0.3) }), { dx: dir.x, dy: 0.5, dz: dir.z }, PRIO.HIGH);
      particle(dim, "bone_shards", point, { count: 4, speed: 0.4 }, PRIO.NORMAL);
      sound(dim, "nr.fx.metal_clang", point, { volume: 1.4, pitch: 0.7 });
      emit(EV.ARMOR_BREAK, { zombie: z, armor, part, attacker, breakable: false, hit });
    }
    safe("armor_hp", () => z.setDynamicProperty("nr:armor_hp", Math.max(0, r.armorHp)));
  } else if (weak && !corpse && Object.keys(g.breakables ?? {}).length && !(g.armored ?? []).length && armor > 0) {
    // 装甲の無い種類の「壊れる部品」（ボンベ・声の袋・余分な頭）: 一度きりの弱点は一撃で、繰り返しの弱点は累積で 1 段ずつ
    r.weakDmg += dmg;
    if (weak.once || r.weakDmg >= maxHpOf(z) * 0.15) {
      r.weakDmg = 0;
      armor = weak.once ? 0 : armor - 1;
      wr(z, r, "nr:armor", armor);
      res.armorBroke = true;
      burst(dim, point, 0.8, { kind });
      emit(EV.ARMOR_BREAK, { zombie: z, armor, part, attacker, breakable: true, hit });
    }
  }

  // ---- 部位の状態（ゴア）----
  const maxHp = maxHpOf(z);
  const noGore = ctx.noGore || (shielded && !multi.length);
  const flesh = !shielded;
  if (flesh) {
    if (G > 0.02 && (hit.dtype === "slash" || hit.dtype === "blunt" || hit.dtype === "pierce" || hit.dtype === "blast")) {
      hitFx(z, point, dir, power * (0.6 + 0.5 * clamp01(dmg / Math.max(1, maxHp * 0.3))), { kind, bleed: bleedOf(z) });
      r.wounds++;
      if (bleedMod) spray(dim, point, norm(add(dir, UP)), 0.8, { kind, prio: PRIO.LOW });
    }
    hitSound(dim, point, hit);
  }
  const partsToRoll = multi.length ? multi : [part];
  if (!noGore && G >= 0 && ["slash", "blunt", "pierce", "blast"].includes(hit.dtype)) {
    for (const p of partsToRoll) {
      if (multi.length && armoredPart(p)) continue;
      const pm = p === "head" ? Number(g.head_mult ?? HITZONE.head) : Number(HITZONE[groupOf(p)] ?? 1);
      const pd = multi.length ? dmg * pm * (hit.dtype === "blast" ? rand(0.4, 1.0) : 1) : dmg;
      const subp = p === part ? ph.sub : (hit.dtype === "blast" ? 0 : 1);
      const to = decide(z, r, g, hit, w, p, subp, ph.how, pd, gp, maxHp, corpse, impactMod);
      if (to) applyOutcome(z, r, g, hit, res, p, to, dir, power, corpse);
    }
    // 打撃の胴: 肋骨が折れて倒れる（DESIGN §4）
    if (hit.dtype === "blunt" && part === "torso" && !multi.length) {
      const strength = (dmg / Math.max(1, maxHp * PART_HP_FRAC.torso)) * (0.4 + gp);
      if (strength >= 0.9 || (hit.weight === "heavy" && strength >= 0.6)) {
        sound(dim, "nr.gore.bone_crunch", point, { volume: 1.1 });
        if (G > 0.2 && chance(0.6 * G)) spawnGib(z, GIB.bone, norm(add(dir, UP)), power);
        particle(dim, "bone_shards", point, { count: Math.round(3 + 4 * G), speed: 0.5 }, PRIO.NORMAL);
        if (!corpse) hit.knockdown = hit.knockdown ?? true;
      }
    }
  }
  // 火・電気・毒・UV
  if (hit.dtype === "fire" || (Number(hit.burn) > 0)) burnUp(z, r, hit, dmg, maxHp, point);
  if (hit.dtype === "shock" && !corpse) shockUp(z, r, hit, point);
  if (hit.dtype === "toxic") particle(dim, "toxic_gas", point, { radius: 0.5, life: 1 }, PRIO.LOW);
  if (hit.dtype === "uv" && dmg > 0) { particle(dim, "uv_burn", point, { size: 0.8 }, PRIO.NORMAL); sound(dim, "nr.fx.uv_burn", point, { volume: 0.8 }); }

  // nr:blood（傷の数）
  if (G > 0.05 && r.wounds > 0) wr(z, r, "nr:blood", clamp(Math.ceil(r.wounds / 2) + (res.severed.length ? 1 : 0), 0, 3));

  // ---- 死体: 吹き飛ぶだけ ----
  if (corpse) {
    try {
      const k = 0.12 + 0.25 * Math.min(power, 2);
      z.applyImpulse({ x: dir.x * k, y: 0.08 + 0.06 * Math.min(power, 2), z: dir.z * k });
    } catch { /* 物理が無い */ }
    emit(EV.HIT, res);
    return res;
  }

  // ---- 体力 ----
  const lethalHead = res.decap || res.crushed;
  if (res.changes.some((c) => c.part === "head" && c.to === "cracked")) dmg += maxHp * 0.25;   // cracked = 大ダメージ
  res.damage = dmg;
  const hp = addHp(z, -dmg);
  res.hp = hp;
  if (!hit.noVanilla && !(/** @type {any} */ (hit))._fromHurt && dmg > 0 && ["melee", "projectile", "hitscan", "blast", "trap"].includes(hit.source)) {
    hurtVanilla(z, 0.01, attacker);
  }

  // ---- 死亡 ----
  if (hp <= 0 || lethalHead) {
    if (lethalHead && hp > 0) setHp(z, 0);
    res.hp = 0;
    res.killed = killZombie(z, r, res, hit, dir, power, lethalHead ? "head" : "hp");
    finish(z, r, res, hit, point);
    return res;
  }
  // 弱点で死ぬ種類（膨れた体の腹・結節）: 能力 gas_cloud_death / detonate
  if (weak && weakFirst && ((weak.ability === "gas_cloud_death" && (hit.dtype === "pierce" || hit.dtype === "slash"))
    || weak.ability === "detonate")) {
    setHp(z, 0); res.hp = 0;
    res.killed = killZombie(z, r, res, hit, dir, power, "weakspot");
    finish(z, r, res, hit, point);
    return res;
  }
  if (dmg > 0 && (hit.dtype === "fire" || hit.dtype === "blast") && (g.weak_spots ?? []).some((ws) => ws?.ability === "detonate")) {
    setHp(z, 0); res.hp = 0;
    res.killed = killZombie(z, r, res, hit, dir, power, "weakspot");
    finish(z, r, res, hit, point);
    return res;
  }

  // ---- 生きている: 反応・よろめき・転倒・押し返し・声 ----
  const st = String(rd(z, r, "nr:state", "normal"));
  const boss = spec?.cls === "boss";
  if (hit.knockdown && st === "normal" && (!boss || hitIn.knockdown) && !res.crawl) {
    res.knockdown = knockdown(z, 50);
  } else if (!ctx.noStagger && st === "normal" && !res.crawl) {
    const frac = Number(g.stagger_frac ?? CT.stagger_threshold ?? 0.25);
    const imp = impactMod && chance(Number(impactMod.stagger_chance) || 0);
    if (dmg >= frac * maxHp || imp) res.staggered = stagger(z, Number(CT.stagger_ticks) || 24);
  }
  if (!ctx.noKnockback && !ctx.noStagger && hit.source !== "fire" && hit.source !== "toxic" && hit.dtype !== "uv") {
    const kb = (Number(w?.knockback) || ({ light: 0.2, medium: 0.3, heavy: 0.5 }[hit.weight] ?? 0.3)) * (0.6 + 0.4 * Math.min(power, 2))
      + (Number(impactMod?.knockback_add) || 0) + (hit.dtype === "blast" ? 0.5 * power : 0);
    try { z.applyKnockback({ x: flat(dir).x * kb, z: flat(dir).z * kb }, Math.min(0.5, 0.08 + 0.1 * kb)); } catch { /* 無効 */ }
  }
  if (!hit.noAnim && !res.knockdown && t - r.lastAnim >= 4) {
    const anim = res.severed.length ? "sever_recoil" : res.staggered || hit.weight === "heavy" || power >= 1.4 ? "react_heavy"
      : hit.dtype === "shock" ? "stunned" : hit.dtype === "fire" || hit.dtype === "toxic" ? "" : st === "crawl" ? "react_torso" : `react_${part}`;
    if (anim) oneShot(z, r, anim);
  }
  if (spec?.voice && t - r.lastVoice >= 12 && dmg > 0) {
    r.lastVoice = t;
    sound(dim, `nr.z.${spec.voice}.hurt`, z.location, { volume: 0.9, pitch: rand(0.92, 1.08) * (Number(spec.voice_pitch) || 1) });
  }
  finish(z, r, res, hit, point);
  return res;
}

/** 結果の通知と画面の返り血。 @param {Entity} z @param {ZRec} r @param {HitResult} res @param {Hit} hit @param {Vector3} point */
function finish(z, r, res, hit, point) {
  void r;
  res.headshot = res.part === "head" && (hit.source === "projectile" || hit.source === "hitscan" || res.decap || res.crushed);
  if (res.headshot) emit(EV.HEADSHOT, { zombie: z, attacker: res.attacker, hit, kill: res.killed, part: "head" });
  const a = res.attacker;
  if (a && isPlayer(a) && (res.killed || res.severed.length || res.crushed || res.decap)) {
    screenBlood(/** @type {Player} */ (a), point, res.crushed || res.decap ? 1 : res.severed.length ? 0.7 : 0.5);
  }
  emit(EV.HIT, res);
}

/** @param {Entity} z @param {ZRec} r @param {HitResult} res @param {Hit} hit @param {Vector3} dir @param {number} power @param {string} cause */
function killZombie(z, r, res, hit, dir, power, cause) {
  const parts = partsOf(z);
  const ok = kill(z, {
    attacker: res.attacker, hit, dir, power, cause, decap: res.decap, crushed: res.crushed, parts,
    state: String(rd(z, r, "nr:state", "normal")), burn: Number(rd(z, r, "nr:burn", 0)), byPlayer: isPlayer(res.attacker),
  });
  if (ok) {
    r.w["nr:state"] = { t: now(), v: "dead" };
    clearTimers(z.id);
  }
  return ok;
}

// ---------------------------------------------------------------------------
//  結果の決定（DESIGN §4 の表 × 部位体力の累積 × 強い一撃の確率 × ゴアレベル）
// ---------------------------------------------------------------------------
/**
 * 次の状態を決める（変えないなら undefined）。
 * @param {Entity} z @param {ZRec} r @param {Record<string, any>} g @param {Hit} hit @param {any} w
 * @param {string} part @param {number} sub @param {string} how @param {number} pd この部位へのダメージ @param {number} gp
 * @param {number} maxHp @param {boolean} corpse @param {any} impactMod
 * @returns {string | undefined}
 */
function decide(z, r, g, hit, w, part, sub, how, pd, gp, maxHp, corpse, impactMod) {
  const group = groupOf(part);
  const cur = String(rd(z, r, `nr:${part}`, "intact"));
  const rankT = RANK[group === "arm" || group === "leg" ? "limb" : group];
  if (group === "head" && FINAL_HEAD.has(cur)) return undefined;
  if (group === "torso" && cur === "halved") return undefined;
  const G = gore();
  const partHp = Math.max(1, maxHp * (Number(PART_HP_FRAC[group]) || 0.4));
  r.dmg[part] = (r.dmg[part] ?? 0) + pd;
  const k = pd / partHp;
  const cum = r.dmg[part] / partHp;
  let strength = k * (0.4 + gp) * (corpse ? 1.4 : 1);
  if (impactMod && (hit.dtype === "blunt" || hit.dtype === "pierce")) strength += Number(impactMod.bone_break_add) || 0;

  /** @type {string[]} 強い順の候補 */
  const cands = [];
  // 指定された結果（罠・とどめ）
  const forced = forcedOutcome(hit, part, group);
  if (forced) {
    const [st, prob] = forced;
    const p = DISMEMBER.has(st) ? prob * Math.pow(G, SEVER_EXP) : prob;
    if (chance(p)) cands.push(st);
  }
  const row = TABLE[hit.dtype]?.[group] ?? {};
  // 強い結果
  let strong = row.strong;
  const bias = w?.sever_bias?.[group];
  if (strong === "cut") {
    if (how === "ray" || how === "point" || how === "near" || hit.point) strong = sub >= 1 ? "cut_lower" : "cut_upper";
    else strong = bias === "cut_upper" || bias === "cut_lower" ? bias : "cut_lower";
  }
  if (hit.dtype === "slash" && group === "torso" && strong === "halved" && !(hit.weight === "heavy" || gp >= 0.95 || bias === "halved")) strong = "gutted";
  if (hit.dtype === "slash" && group !== "torso" && bias && rankT[bias] !== undefined && rankT[bias] > (rankT[strong ?? ""] ?? -1) && allowed(hit.dtype, group, bias)) strong = bias;
  if (hit.dtype === "pierce") {
    if (group === "head") strong = gp >= 0.85 ? "crushed" : gp >= 0.5 ? "cracked" : "wounded";
    else if (group !== "torso") strong = gp >= 0.85 ? "cut_lower" : "wounded";
  }
  if (hit.dtype === "blunt" && group === "head" && bias === "cracked") strong = "cracked";
  let mid = row.mid;
  if (hit.dtype === "pierce" && group === "head" && gp < 0.6) mid = "wounded";
  if (hit.dtype === "blast") strength *= 0.6 + 0.5 * clamp(Number(hit.power ?? 1), 0, 2);
  // 強い一撃・部位体力を超えた
  if (strong) {
    let p = cum >= 1 ? 1 : clamp((strength - 0.55) / 0.5, 0, 1);
    if (DISMEMBER.has(strong)) p *= Math.pow(G, SEVER_EXP) * Math.max(0, Number(g.sever_mult ?? 1));
    if (p > 0 && chance(Math.min(1, p))) cands.push(strong);
  }
  if (mid && (strength >= 0.5 || cum >= 0.6)) cands.push(mid);
  if (row.weak && (strength >= 0.12 || cum >= 0.25)) cands.push(row.weak);

  const curRank = rankT[cur] ?? 0;
  for (const c of cands) {
    if (!c || rankT[c] === undefined) continue;
    if (!forced || c !== forced[0]) { if (!allowed(hit.dtype, group, c)) continue; }
    if (G * 100 < (Number(MIN_G[c]) || 0)) continue;
    if (capped(g, part, group, c)) continue;
    if ((rankT[c] ?? 0) <= curRank) continue;
    return c;
  }
  return undefined;
}

/** hit.outcome から [結果, 確率]。 @param {Hit} hit @param {string} part @param {string} group @returns {[string, number] | undefined} */
function forcedOutcome(hit, part, group) {
  const o = hit.outcome;
  if (!o) return undefined;
  /** @type {any} */
  let v;
  if (typeof o === "string") v = part === (hit.part ?? part) ? o : undefined;
  else v = /** @type {any} */ (o)[part] ?? /** @type {any} */ (o)[group];
  if (!v) return undefined;
  if (Array.isArray(v)) return [String(v[0]), clamp(Number(v[1] ?? 1), 0, 1)];
  return [String(v), 1];
}

/** spec の no_sever / halve で止める結果か。 @param {Record<string, any>} g @param {string} part @param {string} group @param {string} c */
function capped(g, part, group, c) {
  const noSever = (g.no_sever ?? []).includes(part);
  if (group === "torso") {
    if (c === "halved" && (g.halve === false || noSever)) return true;
    return false;
  }
  if (!noSever) return false;
  if (group === "head") return c === "severed" || c === "crushed";
  return c === "cut_lower" || c === "cut_upper";
}

// ---------------------------------------------------------------------------
//  結果の適用（プロパティ・BP イベント・gib・血・音・通知）
// ---------------------------------------------------------------------------
/** 断面のロケータ。 @param {string} part @param {string} to */
function stumpLoc(part, to) {
  const s = sideOf(part);
  if (part === "head") return to === "jawless" ? "loc_mouth" : "loc_neck";
  if (part === "torso") return to === "halved" ? "loc_waist" : "loc_belly";
  if (part.startsWith("arm")) return to === "cut_upper" ? `loc_shoulder_${s}` : `loc_elbow_${s}`;
  return to === "cut_upper" ? `loc_hip_${s}` : `loc_knee_${s}`;
}

/**
 * @param {Entity} z @param {ZRec} r @param {Record<string, any>} g @param {Hit} hit @param {HitResult} res
 * @param {string} part @param {string} to @param {Vector3} dir @param {number} power @param {boolean} corpse
 */
function applyOutcome(z, r, g, hit, res, part, to, dir, power, corpse) {
  const from = String(rd(z, r, `nr:${part}`, "intact"));
  if (!wr(z, r, `nr:${part}`, to)) return;
  res.changes.push({ part, from, to });
  const dim = z.dimension;
  const G = gore();
  const kind = kindOf(z);
  const s = sideOf(part);
  const up = norm(add(dir, { x: 0, y: 0.9, z: 0 }));
  const at = safe("loc", () => locatorPos(z, stumpLoc(part, to))) ?? z.location;
  const gibPower = clamp(0.7 + 0.5 * power, 0.5, 2.2);
  const sever = (/** @type {number} */ gibPart) => {
    res.severed.push(part);
    severFx(z, stumpLoc(part, to), dir, power, { kind });
    sound(dim, part === "head" ? "nr.gore.decap" : "nr.gore.sever", at, { volume: 1.2, pitch: rand(0.9, 1.1) });
    const gib = gibPart >= 0 ? spawnGib(z, gibPart, up, gibPower) : undefined;
    emit(EV.SEVER, { zombie: z, part, state: to, from, attacker: res.attacker, hit, gib, corpse });
    scheduleRegrow(z, g, part);
  };
  switch (to) {
    case "wounded":
      if (part.startsWith("arm") || part.startsWith("leg")) particle(dim, "hit_flesh", at, { dx: dir.x, dy: dir.y, dz: dir.z }, PRIO.NORMAL);
      break;
    case "jawless":
      sound(dim, "nr.gore.squish", at, { volume: 1 });
      severFx(z, "loc_mouth", dir, power * 0.6, { kind, fountain: false });
      spawnGib(z, GIB.jaw, up, gibPower);
      break;
    case "cracked":
      sound(dim, "nr.gore.bone_crunch", at, { volume: 1.2 });
      particle(dim, "bone_shards", at, { count: 5, speed: 0.5 }, PRIO.HIGH);
      if (G > 0.3) particle(dim, "brain_matter", at, { count: Math.round(2 + 4 * G), speed: 0.4 }, PRIO.NORMAL);
      if (chance(0.4 * G)) spawnGib(z, GIB.brain, up, gibPower * 0.8);
      break;
    case "severed":
      res.decap = true;
      sever(GIB.head);
      emit(EV.DECAP, { zombie: z, attacker: res.attacker, hit, corpse });
      break;
    case "crushed": {
      res.crushed = true;
      res.severed.push(part);
      const hp = safe("head", () => partCenter(z, "head", 0)) ?? at;
      headExplodeFx(z, hp, dir, power, { kind, wet: !!g.wet_burst });
      sound(dim, "nr.gore.head_pop", hp, { volume: 1.4, pitch: rand(0.9, 1.1) });
      const ch = GT.gib_count?.crushed_head ?? [3, 8];
      spawnChunks(z, randInt(Number(ch[0]) || 3, Number(ch[1]) || 8), up, gibPower, [GIB.brain, GIB.chunk, GIB.bone, GIB.eye, GIB.chunk], { at: hp });
      emit(EV.CRUSH, { zombie: z, attacker: res.attacker, hit, corpse });
      break;
    }
    case "broken":
      sound(dim, "nr.gore.bone_crack", at, { volume: 1.1, pitch: rand(0.9, 1.1) });
      particle(dim, "bone_shards", at, { count: 3, speed: 0.3 }, PRIO.NORMAL);
      break;
    case "cut_lower":
      sever(part.startsWith("arm") ? (s === "r" ? GIB.forearm_r : GIB.forearm_l) : (s === "r" ? GIB.shin_r : GIB.shin_l));
      break;
    case "cut_upper": {
      const whole = from !== "cut_lower";
      sever(whole ? (part.startsWith("arm") ? (s === "r" ? GIB.arm_r : GIB.arm_l) : (s === "r" ? GIB.leg_r : GIB.leg_l)) : GIB.chunk);
      if (!whole && chance(0.5 * G)) spawnGib(z, GIB.bone, up, gibPower);
      break;
    }
    case "slashed":
      sound(dim, "nr.gore.slash_flesh", at, { volume: 0.8 });
      break;
    case "gutted":
      res.gutted = true;
      sound(dim, "nr.gore.gut_spill", at, { volume: 1.2 });
      if (G * 100 >= (Number(GT.guts_min_g) || 40)) {
        particle(dim, "gut_strands", at, { count: Math.round(3 + 4 * G), speed: 0.3 }, PRIO.HIGH);
        spawnGib(z, GIB.guts, norm(add(dir, { x: 0, y: 0.3, z: 0 })), 0.6);
        if (chance(0.5 * G)) spawnGib(z, GIB.eye, norm(add(dir, UP)), 0.6);   // 15 = 臓器
      }
      severFx(z, "loc_belly", dir, power * 0.7, { kind, fountain: false });
      emit(EV.GUTTED, { zombie: z, attacker: res.attacker, hit, corpse });
      break;
    case "halved": {
      res.halved = true;
      sever(GIB.lower);
      sound(dim, "nr.gore.squish", at, { volume: 1.3 });
      const hv = GT.gib_count?.halved ?? [2, 5];
      spawnChunks(z, randInt(Number(hv[0]) || 2, Number(hv[1]) || 5), up, gibPower, [GIB.guts, GIB.chunk, GIB.bone, GIB.eye], { at });
      if (g.wet_burst) burst(dim, at, 2.2, { kind });
      emit(EV.HALVED, { zombie: z, attacker: res.attacker, hit, corpse });
      break;
    }
    default: break;
  }
  if (corpse) return;
  // 歩けなくなった（脚が無い・両脚が折れた・胴が真っ二つ）
  const legs = ["leg_r", "leg_l"].map((p) => String(rd(z, r, `nr:${p}`, "intact")));
  const cut = legs.some((v) => v.startsWith("cut_"));
  const bothBroken = legs.every((v) => v === "broken" || v.startsWith("cut_"));
  const halved = String(rd(z, r, "nr:torso", "intact")) === "halved";
  const st = String(rd(z, r, "nr:state", "normal"));
  if ((cut || bothBroken || halved) && st !== "crawl" && st !== "dead") {
    if (g.crawl_legless === false && !halved) {
      trigger(z, "nr:root_start");
      wr(z, r, "nr:state", "down");
    } else {
      trigger(z, "nr:to_crawl");
      wr(z, r, "nr:state", "crawl");
      timed.delete(z.id);
      res.crawl = true;
      emit(EV.CRAWL, { zombie: z, attacker: res.attacker, hit });
    }
    safe("slow-", () => z.removeEffect("slowness"));
  } else if (to === "broken" && part.startsWith("leg") && st !== "crawl") {
    safe("slow", () => z.addEffect("slowness", 20 * 600, { amplifier: 1, showParticles: false }));
  }
}

/** 打撃・斬撃などの手応えの音。 @param {Dimension} dim @param {Vector3} at @param {Hit} hit */
function hitSound(dim, at, hit) {
  const heavy = hit.weight === "heavy";
  const id = hit.dtype === "slash" ? (heavy ? "nr.gore.chop" : "nr.gore.slash_flesh")
    : hit.dtype === "blunt" ? (heavy ? "nr.gore.smash" : "nr.gore.blunt_flesh")
      : hit.dtype === "pierce" ? "nr.gore.pierce_flesh"
        : hit.dtype === "blast" ? "nr.gore.splat" : "";
  if (id) sound(dim, id, at, { volume: heavy ? 1.2 : 0.9, pitch: rand(0.9, 1.1) });
}

/** ゾンビの一発アニメ（controller nr.z.os。DESIGN §13）。 @param {Entity} z @param {ZRec} r @param {string} name */
function oneShot(z, r, name) {
  r.lastAnim = now();
  zombieAnim(z, name);
}

/** 火で焼ける（nr:burn 0..3。3 で炭化 → 死体は灰）。 @param {Entity} z @param {ZRec} r @param {Hit} hit @param {number} dmg @param {number} maxHp @param {Vector3} at */
function burnUp(z, r, hit, dmg, maxHp, at) {
  r.fireDmg += hit.dtype === "fire" ? dmg : 0;
  const cur = Number(rd(z, r, "nr:burn", 0));
  const byDmg = Math.floor(r.fireDmg / Math.max(1, maxHp * 0.22));
  const next = clamp(Math.max(cur, byDmg, Math.round(Number(hit.burn) || 0)), 0, 3);
  particle(z.dimension, "burn_flesh", at, { size: 0.6 + 0.2 * next }, PRIO.LOW);
  if (next > cur && wr(z, r, "nr:burn", next)) {
    sound(z.dimension, "nr.fx.fire_ignite", at, { volume: 0.8 });
    if (getProp(z, "nr:state", "normal") !== "dead" && !hit.noAnim) oneShot(z, r, "burn_flail");
  }
}

/** 感電（nr:shock = 1 の間しびれる）。 @param {Entity} z @param {ZRec} r @param {Hit} hit @param {Vector3} at */
function shockUp(z, r, hit, at) {
  const ticks = Math.round(clamp(Number(hit.stunTicks) || 30, 1, 400));
  wr(z, r, "nr:shock", 1);
  particle(z.dimension, "shock_arcs", at, { size: 1 }, PRIO.NORMAL);
  particle(z.dimension, "shock_spark", at, { count: 6 }, PRIO.NORMAL);
  sound(z.dimension, "nr.fx.electric_zap", at, { volume: 1 });
  shocks.set(z.id, { z, until: now() + ticks });
}

// ---------------------------------------------------------------------------
//  時間で戻る状態（よろめき・転倒・感電）と生え戻り
// ---------------------------------------------------------------------------
/** @type {Map<string, {z: Entity, state: string, until: number, end?: string}>} */
const timed = new Map();
/** @type {Map<string, {z: Entity, until: number}>} */
const shocks = new Map();
/** @type {Map<string, {z: Entity, part: string, at: number}>} */
const regrows = new Map();

/** @param {string} id */
function clearTimers(id) {
  timed.delete(id); shocks.delete(id);
  for (const k of [...regrows.keys()]) if (k.startsWith(id + "|")) regrows.delete(k);
}

/**
 * よろめかせる（nr:state stagger、ticks 後に normal）。普通の状態の時だけ。よろめいたら true。
 * @param {Entity} z @param {number} [ticks]
 */
export function stagger(z, ticks = 24) {
  if (!valid(z)) return false;
  const r = rec(z);
  if (String(rd(z, r, "nr:state", "normal")) !== "normal") return false;
  wr(z, r, "nr:state", "stagger");
  timed.set(z.id, { z, state: "stagger", until: now() + Math.max(1, Math.round(ticks)) });
  emit(EV.STAGGER, { zombie: z, ticks });
  return true;
}
/**
 * 倒す（nr:state down、ticks 後に起き上がる）。転んだら true。
 * @param {Entity} z @param {number} [ticks]
 */
export function knockdown(z, ticks = 50) {
  if (!valid(z)) return false;
  const r = rec(z);
  const st = String(rd(z, r, "nr:state", "normal"));
  if (st !== "normal" && st !== "stagger") return false;
  wr(z, r, "nr:state", "down");
  timed.set(z.id, { z, state: "down", until: now() + Math.max(1, Math.round(ticks)), end: "getup" });
  oneShot(z, r, "knockdown");
  sound(z.dimension, "nr.gore.body_fall", z.location, { volume: 1 });
  emit(EV.KNOCKDOWN, { zombie: z, ticks });
  return true;
}

/** @param {Entity} z @param {Record<string, any>} g @param {string} part */
function scheduleRegrow(z, g, part) {
  const s = Number(g.regrow?.[part]);
  if (!(s > 0)) return;
  regrows.set(`${z.id}|${part}`, { z, part, at: now() + Math.round(s * 20) });
}
/** 予定の生え戻りを取り消す（火で焼かれた等。能力 regenerate が使う）。 @param {Entity} z @param {string} [part] */
export function cancelRegrow(z, part) {
  for (const k of [...regrows.keys()]) if (k.startsWith(z.id + "|") && (!part || k.endsWith("|" + part))) regrows.delete(k);
}

system.runInterval(() => {
  const t = now();
  if (timed.size) {
    for (const [id, s] of timed) {
      if (!valid(s.z)) { timed.delete(id); continue; }
      if (t < s.until) continue;
      timed.delete(id);
      const r = rec(s.z);
      if (String(rd(s.z, r, "nr:state", "normal")) === s.state) {
        wr(s.z, r, "nr:state", "normal");
        if (s.end) oneShot(s.z, r, s.end);
      }
    }
  }
  if (shocks.size) {
    for (const [id, s] of shocks) {
      if (!valid(s.z)) { shocks.delete(id); continue; }
      if (t < s.until) continue;
      shocks.delete(id);
      wr(s.z, rec(s.z), "nr:shock", 0);
    }
  }
  if (regrows.size && t % 10 === 0) {
    for (const [k, s] of regrows) {
      if (!valid(s.z)) { regrows.delete(k); continue; }
      if (t < s.at) continue;
      regrows.delete(k);
      const r = rec(s.z);
      if (String(rd(s.z, r, "nr:state", "normal")) === "dead") continue;
      if (wr(s.z, r, `nr:${s.part}`, "intact")) {
        r.dmg[s.part] = 0;
        particle(s.z.dimension, "gore_chunks", partCenter(s.z, s.part, 0), { count: 4, speed: 0.2, spread: 0.2, size: 0.6 }, PRIO.NORMAL);
        sound(s.z.dimension, "nr.gore.squish", s.z.location, { volume: 1, pitch: 0.7 });
        emit(EV.REGROW, { zombie: s.z, part: s.part });
      }
    }
  }
}, 1);

// ---------------------------------------------------------------------------
//  出現時の初期化（本当の体力・装甲の段階・pre_damage）
// ---------------------------------------------------------------------------
/**
 * まだならゾンビを初期化する（nr:hp、nr:armor = initial_armor、spec の pre_damage）。初期化したら true。
 * @param {Entity} z
 */
export function initZombie(z) {
  if (!valid(z) || !isZombie(z)) return false;
  if (z.getDynamicProperty("nr:init") !== undefined) { if (z.getDynamicProperty(HP_KEY) === undefined) initHp(z); return false; }
  if (getProp(z, "nr:state", "normal") === "dead") return false;
  z.setDynamicProperty("nr:init", 1);
  initHp(z);
  const spec = zombieSpec(z);
  const g = goreSpec(z);
  const r = rec(z);
  const ia = Number(spec?.initial_armor);
  if (Number.isFinite(ia)) wr(z, r, "nr:armor", clamp(Math.round(ia), 0, 3));
  r.armorHp = armorStageHp(g);
  for (const [k, v] of Object.entries(g.pre_damage ?? {})) {
    if (k === "state") continue;
    if (ENUM_OF[k]?.includes(v)) wr(z, r, `nr:${k}`, v);
  }
  const ps = g.pre_damage?.state;
  if (ps === "crawl") { trigger(z, "nr:to_crawl"); wr(z, r, "nr:state", "crawl"); }
  else if (typeof ps === "string" && STATES.includes(ps) && ps !== "dead") wr(z, r, "nr:state", ps);
  return true;
}

// ---------------------------------------------------------------------------
//  バニラの被弾 → hit
// ---------------------------------------------------------------------------
/** @type {Map<string, {tick: number, loc: Vector3, dir: Vector3, proj: string}>} 飛び道具の着弾（相手の ID ごと） */
const projHits = new Map();

/**
 * entityHurt の中身を hit に直す（undefined = 何もしない）。
 * @param {Entity} z @param {number} damage @param {{cause: string, damagingEntity?: Entity, damagingProjectile?: Entity}} src
 * @returns {Hit | undefined}
 */
export function hurtToHit(z, damage, src) {
  const cause = String(src.cause);
  const by = valid(src.damagingEntity) ? src.damagingEntity : undefined;
  const info = { damage, cause, corpse: false };
  switch (cause) {
    case "entityAttack": case "ramAttack": case "maceSmash": {
      if (by && isPlayer(by)) {
        const res = meleeResolver ? safe("meleeResolver", () => meleeResolver?.(/** @type {Player} */ (by), z, info)) : undefined;
        if (res === false) return undefined;
        const base = defaultMeleeHit(/** @type {Player} */ (by), z, info);
        return res ? { ...base, ...res } : base;
      }
      return { attacker: by, source: "melee", dtype: "blunt", weight: cause === "entityAttack" ? "medium" : "heavy", damage };
    }
    case "projectile": {
      const proj = valid(src.damagingProjectile) ? src.damagingProjectile : undefined;
      const ph = projHits.get(z.id);
      const fresh = ph && now() - ph.tick <= 1 ? ph : undefined;
      let point = fresh?.loc;
      let dir = fresh?.dir;
      if (!point && proj) { try { point = proj.location; } catch { point = undefined; } }
      if (!dir && proj) { try { const v = proj.getVelocity(); if (Math.hypot(v.x, v.y, v.z) > 1e-3) dir = norm(v); } catch { dir = undefined; } }
      const pinfo = { ...info, projectile: proj, point, dir };
      const shooter = by ?? undefined;
      const res = projectileResolver && shooter && isPlayer(shooter) ? safe("projectileResolver", () => projectileResolver?.(/** @type {Player} */ (shooter), z, pinfo)) : undefined;
      if (res === false) return undefined;
      const base = defaultProjectileHit(shooter, z, pinfo);
      return res ? { ...base, ...res } : base;
    }
    case "entityExplosion": case "blockExplosion": case "fireworks": {
      /** @type {Vector3} */
      let dir = { ...UP };
      try { if (by) dir = norm(sub(z.location, by.location), UP); } catch { /* 上へ */ }
      return { attacker: by, source: "blast", dtype: "blast", weight: "heavy", damage, power: clamp(damage / 8, 0.3, 2), dir };
    }
    case "fire": case "fireTick": case "lava": case "campfire": case "soulCampfire": case "magma":
      return { attacker: by, source: "fire", dtype: "fire", weight: "light", damage, power: 0.2, noKnockback: true, noAnim: cause === "fireTick" };
    case "lightning":
      return { attacker: by, source: "shock", dtype: "shock", weight: "heavy", damage, power: 1 };
    case "fall":
      return { source: "fall", dtype: "blunt", weight: "heavy", damage, power: clamp(damage / 6, 0.3, 2), dir: DOWN, part: "leg_r",
        parts: damage >= 10 ? ["leg_r", "leg_l", "torso"] : ["leg_r", "leg_l"], noKnockback: true };
    case "contact": case "thorns": case "stalagmite": case "stalactite":
      return { attacker: by, source: "trap", dtype: "pierce", weight: "light", damage, part: cause === "stalactite" ? "head" : undefined };
    case "anvil": case "fallingBlock": case "piston":
      return { attacker: by, source: "trap", dtype: "blunt", weight: "heavy", damage, part: cause === "piston" ? undefined : "head", dir: DOWN };
    case "magic": case "wither":
      return { attacker: by, source: "toxic", dtype: "toxic", weight: "light", damage, noKnockback: true };
    case "sonicBoom":
      return { attacker: by, source: "blast", dtype: "blast", weight: "heavy", damage, power: 1.2 };
    default:
      return { attacker: by, source: "trap", dtype: "blunt", weight: "light", damage, noGore: true, noKnockback: true, noAnim: true };
  }
}

/** バニラの死（プールを超えた一撃・/kill）。 @param {Entity} z @param {any} src */
function vanillaDeath(z, src) {
  const r = recs.get(z.id);
  const by = valid(src?.damagingEntity) ? src.damagingEntity : undefined;
  let dir;
  try { if (by && valid(z)) dir = norm(sub(z.location, by.location)); } catch { dir = undefined; }
  overkill(z, { attacker: by, dir, byPlayer: isPlayer(by), at: r?.lastLoc, dim: r?.dim, key: z.typeId.slice(5) });
  clearTimers(z.id);
}

// ---------------------------------------------------------------------------
//  イベント
// ---------------------------------------------------------------------------
setHitHandler(applyHit);

world.afterEvents.entityHurt.subscribe((ev) => {
  const z = ev.hurtEntity;
  if (!valid(z) || !isZombie(z)) return;
  const src = ev.damageSource;
  let cur = 1;
  try { cur = z.getComponent("minecraft:health")?.currentValue ?? 1; } catch { cur = 1; }
  if (cur <= 0) { vanillaDeath(z, src); return; }      // プールを超えた: 全身が弾ける
  resetPool(z);
  if (consumeReservation(z, String(src.cause))) return;
  if (isCorpse(z) || getProp(z, "nr:state", "normal") === "dead") return;
  const hit = safe("hurtToHit", () => hurtToHit(z, ev.damage, { cause: String(src.cause), damagingEntity: src.damagingEntity, damagingProjectile: src.damagingProjectile }));
  if (!hit) return;
  /** @type {any} */ (hit)._fromHurt = true;
  safe("applyHit", () => applyHit(z, hit));
}, { entityTypes: [...ZOMBIE_IDS] });

world.afterEvents.entityDie.subscribe((ev) => {
  const z = ev.deadEntity;
  if (!isZombie(z)) return;
  safe("vanillaDeath", () => vanillaDeath(z, ev.damageSource));
}, { entityTypes: [...ZOMBIE_IDS] });

// 死体を殴る（死体は damage_sensor で entityHurt が来ない）。生きている相手は entityHurt に任せる
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const z = ev.hitEntity;
  if (!z || !isZombie(z) || !valid(z)) return;
  const a = ev.damagingEntity;
  const r = rec(z);
  if (!isCorpse(z) && getProp(z, "nr:state", "normal") !== "dead") return;
  if (valid(a) && r.lastLiveHit === now() && r.lastAttacker === a.id) return;   // 同じ tick にとどめを刺した一撃
  /** @type {Hit | undefined} */
  let hit;
  if (valid(a) && isPlayer(a)) {
    const info = { damage: 0, cause: "entityAttack", corpse: true };
    const res = meleeResolver ? safe("meleeResolver", () => meleeResolver?.(/** @type {Player} */ (a), z, info)) : undefined;
    if (res === false) return;
    const base = defaultMeleeHit(/** @type {Player} */ (a), z, info);
    if (!(Number(base.damage) > 1)) base.damage = Number(weaponOf(base.weapon)?.damage) || 3;
    hit = res ? { ...base, ...res } : base;
  } else if (valid(a)) {
    hit = { attacker: a, source: "melee", dtype: "blunt", weight: "medium", damage: 3 };
  }
  if (hit) safe("corpseHit", () => applyHit(z, { ...hit, corpse: true }));
});

world.afterEvents.projectileHitEntity.subscribe((ev) => {
  let z;
  try { z = ev.getEntityHit()?.entity; } catch { z = undefined; }
  if (!z || !isZombie(z) || !valid(z)) return;
  const dir = norm(ev.hitVector);
  projHits.set(z.id, { tick: now(), loc: ev.location, dir, proj: ev.projectile?.typeId ?? "" });
  if (projHits.size > 64) { const first = projHits.keys().next().value; if (first !== undefined) projHits.delete(first); }
  if (!isCorpse(z) && getProp(z, "nr:state", "normal") !== "dead") return;
  // 死体に刺さった: 体力は無いが切断・吹き飛びはある
  const shooter = valid(ev.source) ? ev.source : undefined;
  const info = { damage: 0, cause: "projectile", corpse: true, projectile: ev.projectile, point: ev.location, dir };
  const res = projectileResolver && shooter && isPlayer(shooter) ? safe("projectileResolver", () => projectileResolver?.(/** @type {Player} */ (shooter), z, info)) : undefined;
  if (res === false) return;
  const base = defaultProjectileHit(shooter, z, info);
  if (!(Number(base.damage) > 0.5)) base.damage = Number(WEAPON_OF_PROJ[ev.projectile?.typeId ?? ""]?.damage) || 5;
  safe("corpseShot", () => applyHit(z, { ...base, ...(res ?? {}), corpse: true }));
});

world.afterEvents.entitySpawn.subscribe((ev) => { const e = ev.entity; if (isZombie(e)) safe("initZombie", () => initZombie(e)); });
world.afterEvents.entityLoad.subscribe((ev) => { const e = ev.entity; if (isZombie(e)) safe("initZombie", () => initZombie(e)); });
world.afterEvents.entityRemove.subscribe((ev) => {
  if (!ev.typeId.startsWith("nr:z_")) return;
  recs.delete(ev.removedEntityId);
  projHits.delete(ev.removedEntityId);
  clearTimers(ev.removedEntityId);
});

/** 控えの大きさ（テスト・デバッグ用）。 */
export function debugCounts() { return { recs: recs.size, timed: timed.size, shocks: shocks.size, regrows: regrows.size, projHits: projHits.size }; }
