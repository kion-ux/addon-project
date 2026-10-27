// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 免疫（夜の感染。DESIGN §7、PARKOUR_TUNING.immunity）
//
//  * 暗い所（夜の屋外・昼でも屋内の暗がり）で drain_per_s ずつ減る。0 になると damage_interval_ticks ごとに
//    damage_at_zero のダメージ・赤い画面・吐き気。heartbeat_below_s 未満で心音（残りが少ないほど速い）。
//    warn_s（60/30/10 秒）を下回るたびに警告の音とバス "immunity" {kind: "warn"}。
//  * 戻る: UV ランプ（ブロック nr:uv_lamp。カスタムコンポーネントの params の radius / immunity_regen_per_s、
//    状態 nr:powered が 1 の時）の範囲・バス "uv_zone" の範囲（UV 発煙筒）で immunity_regen_per_s、
//    昼の日なた（空が見えて昼）でゆっくり（DAYLIGHT_REGEN_PER_S）。アイテム（data/items.js の use.type "immunity":
//    nr:immunity_booster・nr:uv_shroom）の immunity_s と pause_s（その間は減らない）。バス "immunity_restore"。
//  * 暗さ: Dimension.getLightLevel / getSkyLightLevel（2.3.0 の安定版。script_api.md §6.4）。実機の getLightLevel が
//    時刻で空の光を落とすかは要実機確認なので、どちらでも正しくなるように読む（lightInfo の説明）。
//  * 保存: プレイヤーの動的プロパティ `nr:immunity`（秒）。死んで戻ると満タン。設定 immunity_enabled が false なら減らない。
// ===========================================================================
import { world, BlockVolume, EntityDamageCause } from "@minecraft/server";
import { on, emit } from "../core/bus.js";
import { valid, now, clamp, dist } from "../core/util.js";
import { playerSound, particle, fade, playerAnim, PRIO } from "../core/fx.js";
import { get as setting } from "../core/settings.js";
import { onBlockComponent } from "../core/components.js";
import * as ITEMS_D from "../data/items.js";
import { PEV, PT, nv, playerMap, onPlayerTick, onWorldTick, isActive, skyFactor, LIGHT_BLOCKS, guard } from "./common.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */

const IM = PT.immunity ?? {};
export const IMMUNITY = Object.freeze({
  max: nv(IM.max_s, 300),
  drain: nv(IM.drain_per_s, 1),
  dark: nv(IM.dark_light_level, 5),
  uvRegen: nv(IM.uv_regen_per_s, 10),
  warn: (Array.isArray(IM.warn_s) ? IM.warn_s : [60, 30, 10]).map(Number).filter(Number.isFinite).sort((a, b) => b - a),
  damage: nv(IM.damage_at_zero, 2),
  damageEvery: Math.max(1, Math.floor(nv(IM.damage_interval_ticks, 20))),
  heartbeatBelow: nv(IM.heartbeat_below_s, 30),
});
/** 昼の日なたで戻る速さ（秒あたり。PARKOUR_TUNING に無いので player/ の決め）。 */
export const DAYLIGHT_REGEN_PER_S = 2;
/** 保存の鍵（秒）。 */
export const IMMUNITY_KEY = "nr:immunity";
const STEP = 10;                 // 何 tick ごとに計算するか（0.5 秒）
const LIGHT_SCAN_RADIUS = 6;     // 区別のつかない時に光源を探す半径

/** @type {any} */
const ID = ITEMS_D;
/** @type {Record<string, any>} */
const ITEM_BY_ID = Object.fromEntries((Array.isArray(ID.ITEMS) ? ID.ITEMS : []).map((/** @type {any} */ it) => [it.id, it]));

/**
 * @typedef {{value: number, loaded: boolean, savedV: number, pauseUntil: number, warned: number, lastDmg: number,
 *   beatT: number, dark: boolean, uv: boolean, sun: boolean, light: number, state: string, zeroT: number}} IState
 */
/** @type {Map<string, IState>} */
const states = playerMap();

/** @param {Player} p @returns {IState} */
function istate(p) {
  let s = states.get(p.id);
  if (!s) {
    s = { value: IMMUNITY.max, loaded: false, savedV: IMMUNITY.max, pauseUntil: -1, warned: Infinity, lastDmg: -9999, beatT: -9999, dark: false, uv: false, sun: false, light: 15, state: "", zeroT: -1 };
    try {
      const v = p.getDynamicProperty(IMMUNITY_KEY);
      if (typeof v === "number" && Number.isFinite(v)) s.value = clamp(v, 0, IMMUNITY.max);
    } catch { /* 無い */ }
    s.savedV = s.value;
    s.warned = warnLevel(s.value);
    states.set(p.id, s);
  }
  return s;
}
/** その値で既に出した警告の段（警告の閾値の何番目まで下回ったか）。 @param {number} v */
function warnLevel(v) { let n = 0; for (const w of IMMUNITY.warn) if (v <= w) n++; return n; }

/** 免疫が効いているか（設定）。 */
export function immunityEnabled() { return setting("immunity_enabled") !== false; }

/**
 * 今の免疫。value は残り秒。dark = 暗い所にいる、uv = UV の光の中、draining = 今減っている。
 * @param {Player} p
 */
export function immunityOf(p) {
  if (!valid(p)) return { value: IMMUNITY.max, max: IMMUNITY.max, dark: false, uv: false, sun: false, paused: false, draining: false, light: 15 };
  const s = istate(p);
  const paused = now() < s.pauseUntil;
  return { value: s.value, max: IMMUNITY.max, dark: s.dark, uv: s.uv, sun: s.sun, paused, draining: immunityEnabled() && isActive(p) && s.dark && !s.uv && !paused, light: s.light };
}
/** 値を直接書く（秒）。 @param {Player} p @param {number} seconds */
export function setImmunity(p, seconds) {
  if (!valid(p)) return;
  const s = istate(p);
  s.value = clamp(seconds, 0, IMMUNITY.max);
  s.warned = warnLevel(s.value);
}
/**
 * 免疫を戻す（秒）。pauseS 秒は減らない。source は表示・記録用。
 * @param {Player} p @param {number} seconds @param {string} [source] @param {number} [pauseS]
 */
export function restoreImmunity(p, seconds, source = "", pauseS = 0) {
  if (!valid(p) || !(seconds > 0 || pauseS > 0)) return;
  const s = istate(p);
  const was = s.value;
  s.value = clamp(s.value + Math.max(0, seconds), 0, IMMUNITY.max);
  if (pauseS > 0) s.pauseUntil = Math.max(s.pauseUntil, now() + Math.round(pauseS * 20));
  s.warned = warnLevel(s.value);
  if (s.value > was) {
    playerSound(p, "nr.pl.immunity_restore");
    emit(PEV.IMMUNITY, { player: p, value: s.value, max: IMMUNITY.max, kind: "restore", source });
  }
}

// ---------------------------------------------------------------------------
//  暗さ
// ---------------------------------------------------------------------------
/**
 * 頭の位置の明るさの見積もり。
 *  total = getLightLevel、sky = getSkyLightLevel、skyNow = sky × 時刻の倍率（夜 4/15）。
 *   * total > sky → ブロックの光が空より強い → max(total, skyNow)
 *   * total < sky → 実機が時刻で空の光を落としている（偽物もこれ） → total
 *   * total = sky → 区別がつかない。空の光が暗い時（夜の屋外）だけ近くの光源（LIGHT_BLOCKS）を探して足す
 * @param {Player} p
 * @returns {{total: number, sky: number, skyNow: number, eff: number, dark: boolean, sun: boolean}}
 */
export function lightInfo(p) {
  const dim = p.dimension;
  const head = p.getHeadLocation();
  let total = 15, sky = 15, time = 6000;
  try { total = dim.getLightLevel(head); } catch { /* 読み込み外 */ }
  try { sky = dim.getSkyLightLevel(head); } catch { sky = total; }
  try { time = world.getTimeOfDay(); } catch { /* worldLoad 前 */ }
  if (dim.id !== "minecraft:overworld" && dim.id !== "overworld") sky = Math.min(sky, total);
  const skyNow = sky * skyFactor(time);
  let eff;
  if (total > sky) eff = Math.max(total, skyNow);
  else if (total < sky) eff = total;
  else eff = skyNow <= IMMUNITY.dark && sky > IMMUNITY.dark ? Math.max(skyNow, scanLights(dim, head)) : skyNow;
  return { total, sky, skyNow, eff, dark: eff <= IMMUNITY.dark, sun: sky >= 12 && skyFactor(time) >= 0.99 };
}

const LIGHT_TYPES = Object.keys(LIGHT_BLOCKS);
let scanBroken = false;
/** 近くの光源から届く明るさ（光の強さ − マンハッタン距離）の最大。 @param {Dimension} dim @param {Vector3} at */
function scanLights(dim, at) {
  if (scanBroken || !LIGHT_TYPES.length) return 0;
  const R = LIGHT_SCAN_RADIUS;
  const c = { x: Math.floor(at.x), y: Math.floor(at.y), z: Math.floor(at.z) };
  let best = 0;
  try {
    const vol = dim.getBlocks(new BlockVolume({ x: c.x - R, y: c.y - R, z: c.z - R }, { x: c.x + R, y: c.y + R, z: c.z + R }), { includeTypes: LIGHT_TYPES }, true);
    for (const q of vol.getBlockLocationIterator()) {
      const b = dim.getBlock(q);
      const le = b ? LIGHT_BLOCKS[b.typeId] ?? 0 : 0;
      const d = Math.abs(q.x - c.x) + Math.abs(q.y - c.y) + Math.abs(q.z - c.z);
      if (le - d > best) best = le - d;
    }
  } catch (err) {
    scanBroken = true;
    console.warn("[nr] immunity: 光源の検索ができない（以後は空の光だけで判定）", err instanceof Error ? err.message : String(err));
  }
  return best;
}

// ---------------------------------------------------------------------------
//  UV ランプ（nr:uv_lamp の onTick で場所を覚える）と UV の範囲（バス）
// ---------------------------------------------------------------------------
/** @typedef {{dim: string, pos: Vector3, radius: number, regen: number, powered: boolean, seen: number, state: string}} Lamp */
/** @type {Map<string, Lamp>} */
const lamps = new Map();
/** @type {{dim: string, pos: Vector3, radius: number, until: number, regen: number}[]} */
const zones = [];

onBlockComponent("nr:uv_lamp", {
  onTick(e, params) {
    const b = e.block;
    /** @type {any} */
    const prm = params ?? {};
    const state = String(prm.state ?? "nr:powered");
    const key = `${e.dimension.id}:${b.x},${b.y},${b.z}`;
    lamps.set(key, { dim: e.dimension.id, pos: { x: b.x + 0.5, y: b.y + 0.5, z: b.z + 0.5 }, radius: nv(prm.radius, 10),
      regen: nv(prm.immunity_regen_per_s, IMMUNITY.uvRegen), powered: lampPowered(b, state), seen: now(), state });
  },
});
on(PEV.UV_ZONE, (d) => {
  if (!d?.pos || !Number.isFinite(d.pos.x)) return;
  const dimId = typeof d.dim === "string" ? d.dim : d.dim?.id ?? "minecraft:overworld";
  zones.push({ dim: dimId, pos: d.pos, radius: nv(d.radius, 6), until: nv(d.until, now() + 200), regen: nv(d.regen, IMMUNITY.uvRegen) });
});
onWorldTick("immunity.lamps", 40, (t) => {
  for (const [k, l] of lamps) if (t - l.seen > 70) lamps.delete(k);
  for (let i = zones.length - 1; i >= 0; i--) if (t > zones[i].until) zones.splice(i, 1);
});
/**
 * その位置の UV の回復（秒あたり。範囲外は 0）。範囲内のランプはブロックを読み直す（壊された・消された
 * ランプはすぐ効かなくなる。onTick を待たない）。
 * @param {Dimension} dim @param {Vector3} at
 */
export function uvAt(dim, at) {
  let best = 0;
  const id = dim.id;
  for (const [k, l] of lamps) {
    if (l.dim !== id || dist(l.pos, at) > l.radius) continue;
    /** @type {import("@minecraft/server").Block | undefined} */
    let b;
    try { b = dim.getBlock({ x: Math.floor(l.pos.x), y: Math.floor(l.pos.y), z: Math.floor(l.pos.z) }); } catch { b = undefined; }
    if (!b) continue;
    if (b.typeId !== "nr:uv_lamp") { lamps.delete(k); continue; }
    l.powered = lampPowered(b, l.state);
    if (l.powered) best = Math.max(best, l.regen);
  }
  const t = now();
  for (const z of zones) if (z.until >= t && z.dim === id && dist(z.pos, at) <= z.radius) best = Math.max(best, z.regen);
  return best;
}
/** ランプの状態（nr:powered が 1 / true / 無い）。 @param {import("@minecraft/server").Block} b @param {string} state */
function lampPowered(b, state) {
  try {
    const st = b.permutation.getState(/** @type {any} */ (state));
    return st === undefined ? true : st === 1 || st === true || st === "1";
  } catch { return true; }
}
/** 覚えている UV ランプの数（テスト・デバッグ）。 */
export function lampCount() { return [...lamps.values()].filter((l) => l.powered).length; }

// ---------------------------------------------------------------------------
//  毎 0.5 秒
// ---------------------------------------------------------------------------
onPlayerTick("immunity", STEP, (p, t) => {
  const s = istate(p);
  const dt = STEP / 20;
  if (!isActive(p, true) || !immunityEnabled()) {
    s.dark = false; s.uv = false;
    if (!immunityEnabled() && s.value < IMMUNITY.max) { s.value = IMMUNITY.max; s.warned = 0; }
    return;
  }
  const li = guard("immunity.light", () => lightInfo(p)) ?? { eff: 15, dark: false, sun: false };
  const uv = uvAt(p.dimension, p.location);
  s.light = li.eff; s.dark = li.dark; s.uv = uv > 0; s.sun = !!li.sun && !li.dark;
  const was = s.value;
  if (uv > 0) s.value = Math.min(IMMUNITY.max, s.value + uv * dt);
  else if (s.sun) s.value = Math.min(IMMUNITY.max, s.value + DAYLIGHT_REGEN_PER_S * dt);
  else if (s.dark && t >= s.pauseUntil) s.value = Math.max(0, s.value - IMMUNITY.drain * dt);

  if (s.value > was) {
    s.warned = Math.min(s.warned, warnLevel(s.value));
    if (s.value >= IMMUNITY.max && was < IMMUNITY.max) {
      playerSound(p, "nr.pl.immunity_restore", { volume: 0.7 });
      emit(PEV.IMMUNITY, { player: p, value: s.value, max: IMMUNITY.max, kind: "full" });
    }
    if (uv > 0 && t % 20 === 0) particle(p.dimension, "uv_glow", { x: p.location.x, y: p.location.y + 1, z: p.location.z }, undefined, PRIO.LOW);
  }
  const wl = warnLevel(s.value);
  if (wl > s.warned) {
    s.warned = wl;
    const w = IMMUNITY.warn[wl - 1];
    playerSound(p, "nr.pl.immunity_warn");
    emit(PEV.IMMUNITY, { player: p, value: s.value, max: IMMUNITY.max, kind: "warn", threshold: w });
  }
  if (Math.abs(s.value - s.savedV) >= 5 || (s.value === 0 && s.savedV !== 0) || (s.value === IMMUNITY.max && s.savedV !== IMMUNITY.max)) {
    s.savedV = s.value;
    try { p.setDynamicProperty(IMMUNITY_KEY, Math.round(s.value * 10) / 10); } catch { /* 抜けた */ }
  }
});

// 心音・0 のダメージ（毎 tick 見て、間隔は自前で数える）
onPlayerTick("immunity.heart", 2, (p, t) => {
  const s = states.get(p.id);
  if (!s || !isActive(p, true) || !immunityEnabled()) return;
  if (s.value <= 0 && !s.uv) {
    if (s.zeroT < 0) {
      s.zeroT = t;
      emit(PEV.IMMUNITY, { player: p, value: 0, max: IMMUNITY.max, kind: "zero" });
    }
    if (t - s.lastDmg >= IMMUNITY.damageEvery) {
      s.lastDmg = t;
      try { p.applyDamage(IMMUNITY.damage, { cause: EntityDamageCause.magic }); } catch { /* 無敵 */ }
      fade(p, { red: 0.35, green: 0, blue: 0.05 }, 0.1, 0.1, 0.6);
      try { p.addEffect("nausea", 100, { amplifier: 0, showParticles: false }); } catch { /* 効かない */ }
    }
  } else s.zeroT = -1;
  if (s.value < IMMUNITY.heartbeatBelow && !s.uv) {
    const every = s.value <= 0 ? 10 : s.value < 10 ? 14 : 20;
    if (t - s.beatT >= every) {
      s.beatT = t;
      playerSound(p, "nr.pl.heartbeat", { volume: 1, pitch: s.value < 10 ? 1.15 : 1 });
      if (s.value < 10 && s.value > 0) fade(p, { red: 0.2, green: 0, blue: 0.04 }, 0.05, 0, 0.35);
    }
  }
});

// ---------------------------------------------------------------------------
//  アイテム・バス・生き返り
// ---------------------------------------------------------------------------
world.afterEvents.itemStartUse.subscribe((ev) => {
  const it = ev.itemStack;
  const use = it ? ITEM_BY_ID[it.typeId]?.use : undefined;
  if (!use || use.type !== "immunity" || !valid(ev.source) || !use.anim) return;
  playerAnim(ev.source, String(use.anim));
});
world.afterEvents.itemCompleteUse.subscribe((ev) => {
  const p = ev.source;
  const it = ev.itemStack;
  if (!valid(p) || !it) return;
  const use = ITEM_BY_ID[it.typeId]?.use;
  if (!use || use.type !== "immunity") return;
  restoreImmunity(p, nv(use.immunity_s, 30), it.typeId, nv(use.pause_s, 0));
  particle(p.dimension, "heal_sparkle", { x: p.location.x, y: p.location.y + 1, z: p.location.z }, undefined, PRIO.NORMAL);
});
on(PEV.IMMUNITY_RESTORE, (d) => {
  if (valid(d?.player)) restoreImmunity(d.player, nv(d.seconds, 0), String(d.source ?? ""));
});
world.afterEvents.playerSpawn.subscribe((ev) => {
  const p = ev.player;
  if (!valid(p)) return;
  const s = istate(p);
  if (!ev.initialSpawn) { s.value = IMMUNITY.max; s.warned = 0; s.zeroT = -1; s.pauseUntil = -1; }
});
