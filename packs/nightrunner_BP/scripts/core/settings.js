// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 設定（ワールドの動的プロパティ nr:settings に JSON 1 本）
//
//  * 既定値は data/settings.js の SETTINGS_DEFAULTS（spec の SETTINGS_SCHEMA）。
//  * world を読むのは worldLoad の後だけ（early execution では既定値を返す）。
//  * set() は after イベント・system.run の中から呼ぶ（before イベントの中では書かない）。
//  * tuning(name, fallback): 生成データ（data/settings.js・zombies.js）の表を名前で探す。生成器がまだ出していない表は
//    fallback（この JS に写した spec の値）を使う。
// ===========================================================================
import { world } from "@minecraft/server";
import * as SET_D from "../data/settings.js";
import * as ZOM_D from "../data/zombies.js";
import { emit, on, EV } from "./bus.js";
import { clamp, clamp01 } from "./util.js";

const KEY = "nr:settings";

// 生成データの名前空間（data/settings.js と data/zombies.js。export の有無は生成器しだいなので any で引く）
/** @type {any[]} */
const DATA = [SET_D, ZOM_D];
/** @type {Map<string, any>} */
const tableCache = new Map();

/**
 * 生成データの表を名前で引く（data/settings.js・data/zombies.js が export していればそれ、無ければ fallback）。
 * @template T @param {string} name @param {T} fallback @returns {T}
 */
export function tuning(name, fallback) {
  if (tableCache.has(name)) return tableCache.get(name);
  let v;
  for (const ns of DATA) {
    try { if (ns && ns[name] !== undefined) { v = ns[name]; break; } } catch { /* 読めない */ }
  }
  const out = v === undefined ? fallback : v;
  tableCache.set(name, out);
  return out;
}

// spec（nr_spec_catalog.SETTINGS_SCHEMA）の写し。生成データが無い時だけ使う
const FALLBACK_DEFAULTS = {
  gore_level: 100, gib_lifetime_s: 60, corpse_lifetime_s: 90, max_gibs: 48, max_corpses: 24,
  blood_decal_mult: 1.0, screen_blood: true, particle_budget: 300, natural_spawn: true, horde_density: 1.0,
  chase_enabled: true, immunity_enabled: true, friendly_fire: false, difficulty: "normal",
  difficulty_scaling: true, hud_enabled: true, damage_numbers: false, parkour_assist: true,
};
// 数の設定の範囲（SETTINGS_SCHEMA の min / max）。スキーマがデータにあればそちらを使う
const FALLBACK_RANGES = {
  gore_level: [0, 100], gib_lifetime_s: [10, 300], corpse_lifetime_s: [10, 600], max_gibs: [0, 128],
  max_corpses: [0, 64], blood_decal_mult: [0, 2], particle_budget: [50, 300], horde_density: [0.25, 3],
};
const FALLBACK_OPTIONS = { difficulty: ["easy", "normal", "hard", "nightmare"] };

/** @type {Record<string, any>} */
export const DEFAULTS = Object.freeze({ ...FALLBACK_DEFAULTS, ...(tuning("SETTINGS_DEFAULTS", {})) });

/** @returns {{ranges: Record<string, number[]>, options: Record<string, string[]>}} */
function schema() {
  const ranges = { ...FALLBACK_RANGES };
  /** @type {Record<string, string[]>} */
  const options = { ...FALLBACK_OPTIONS };
  const sch = tuning("SETTINGS_SCHEMA", null);
  if (Array.isArray(sch)) {
    for (const s of sch) {
      if (!s || typeof s.key !== "string") continue;
      if (Number.isFinite(s.min) && Number.isFinite(s.max)) ranges[s.key] = [s.min, s.max];
      if (Array.isArray(s.options)) options[s.key] = s.options.map(String);
    }
  }
  return { ranges, options };
}
const SCHEMA = schema();

/** @type {Record<string, any>} */
let cur = { ...DEFAULTS };
let ready = false;

/** 値を既定値の型に合わせて検査する（合わなければ undefined）。 @param {string} key @param {any} v */
function coerce(key, v) {
  const d = DEFAULTS[key];
  if (d === undefined) return undefined;
  if (typeof d === "number") {
    const n = Number(v);
    if (!Number.isFinite(n)) return undefined;
    const r = SCHEMA.ranges[key];
    return r ? clamp(n, r[0], r[1]) : n;
  }
  if (typeof d === "boolean") return typeof v === "boolean" ? v : v === 1 || v === "true" ? true : v === 0 || v === "false" ? false : undefined;
  if (typeof d === "string") {
    const s = String(v);
    const opts = SCHEMA.options[key];
    return !opts || opts.includes(s) ? s : undefined;
  }
  return undefined;
}

function load() {
  ready = true;
  cur = { ...DEFAULTS };
  let raw;
  try { raw = world.getDynamicProperty(KEY); } catch { raw = undefined; }
  if (typeof raw === "string" && raw.length) {
    try {
      const obj = JSON.parse(raw);
      if (obj && typeof obj === "object") {
        for (const [k, v] of Object.entries(obj)) {
          const c = coerce(k, v);
          if (c !== undefined) cur[k] = c;
        }
      }
    } catch { /* 壊れた JSON は既定値へ */ }
  }
}

function save() {
  if (!ready) return;
  /** @type {Record<string, any>} */
  const diff = {};
  for (const [k, v] of Object.entries(cur)) if (v !== DEFAULTS[k]) diff[k] = v;
  try { world.setDynamicProperty(KEY, JSON.stringify(diff)); } catch (err) { console.warn("[nr] settings save", err instanceof Error ? err.message : err); }
}

world.afterEvents.worldLoad.subscribe(() => { load(); emit(EV.SETTINGS, { key: "*", value: undefined }); });

/** 設定の値（worldLoad 前は既定値）。 @param {string} key @returns {any} */
export function get(key) { return key in cur ? cur[key] : DEFAULTS[key]; }

/** 数の設定（数でなければ def）。 @param {string} key @param {number} def */
export function num(key, def) { const v = Number(get(key)); return Number.isFinite(v) ? v : def; }

/**
 * 設定を変える（型・範囲を検査。保存して EV.SETTINGS を出す）。受け付けたら true。
 * before イベントの中から呼ばない（system.run へ）。
 * @param {string} key @param {any} value
 */
export function set(key, value) {
  const c = coerce(key, value);
  if (c === undefined) return false;
  if (cur[key] === c) return true;
  cur[key] = c;
  save();
  emit(EV.SETTINGS, { key, value: c });
  return true;
}

/** まとめて変える。 @param {Record<string, any>} obj @returns {number} 受け付けた数 */
export function setMany(obj) {
  let n = 0;
  for (const [k, v] of Object.entries(obj ?? {})) {
    const c = coerce(k, v);
    if (c === undefined) continue;
    cur[k] = c; n++;
  }
  if (n) { save(); emit(EV.SETTINGS, { key: "*", value: undefined }); }
  return n;
}

/** 既定値へ戻す。 */
export function reset() { cur = { ...DEFAULTS }; save(); emit(EV.SETTINGS, { key: "*", value: undefined }); }

/** いまの設定の写し。 */
export function all() { return { ...cur }; }

/** 設定が読み込まれたか（worldLoad 後）。 */
export function isReady() { return ready; }

/** 変更を受け取る。 @param {(e: {key: string, value: any}) => void} fn */
export function onChange(fn) { return on(EV.SETTINGS, fn); }

/** ゴアレベル 0..1（設定 gore_level / 100）。 */
export function gore() { return clamp01(num("gore_level", 100) / 100); }

// 難易度（spec の DIFFICULTY の写し。生成データにあればそちら）
const FALLBACK_DIFFICULTY = {
  easy: { zombie_hp_mult: 0.75, zombie_damage_mult: 0.6, night_mult: 0.8, horde_mult: 0.75, immunity_drain_mult: 0.6, durability_mult: 1.5, player_scale_per_extra: 0.10 },
  normal: { zombie_hp_mult: 1.0, zombie_damage_mult: 1.0, night_mult: 1.0, horde_mult: 1.0, immunity_drain_mult: 1.0, durability_mult: 1.0, player_scale_per_extra: 0.15 },
  hard: { zombie_hp_mult: 1.3, zombie_damage_mult: 1.4, night_mult: 1.3, horde_mult: 1.3, immunity_drain_mult: 1.25, durability_mult: 0.8, player_scale_per_extra: 0.2 },
  nightmare: { zombie_hp_mult: 1.6, zombie_damage_mult: 1.8, night_mult: 1.6, horde_mult: 1.6, immunity_drain_mult: 1.5, durability_mult: 0.6, player_scale_per_extra: 0.25 },
};

/** いまの難易度の倍率表（DIFFICULTY[settings.difficulty]）。 @returns {Record<string, number>} */
export function difficulty() {
  const t = tuning("DIFFICULTY", FALLBACK_DIFFICULTY);
  return t[String(get("difficulty"))] ?? t.normal ?? FALLBACK_DIFFICULTY.normal;
}
