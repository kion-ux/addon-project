// ===========================================================================
//  NIGHT RUNNER: 感染都市 — player/ の共通部品
//
//  * バスの名前（player/ が出す・聞くもの。core/bus.js の EV に無い分）
//  * プレイヤーごとの tick の登録（system.runInterval は 1 本だけ。worldLoad の後だけ動く）
//  * プレイヤーごとの控え（抜けたら消える Map）・ゲームモード・夜の判定
//  * 地形の判定（2.3.0 の安定版に Block.isSolid は無いので、当たりの有無と高さを自前で持つ）
//  * プレイヤーを動かす薄い包み（applyKnockback だけ。プレイヤーに applyImpulse は使わない）
//
//  最上位は subscribe と runInterval の登録だけ（world を触るのは worldLoad の後の tick の中）。
// ===========================================================================
import { world, system, GameMode } from "@minecraft/server";
import * as SETTINGS_D from "../data/settings.js";
import * as BLOCKS_D from "../data/blocks.js";
import { valid, now, clamp } from "../core/util.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */
/** @typedef {import("@minecraft/server").Block} Block */

// ---------------------------------------------------------------------------
//  バスの出来事（player/ が出す・聞くもの。中身の形はここが正）
// ---------------------------------------------------------------------------
export const PEV = Object.freeze({
  STAMINA_COST: "stamina_cost",         // 聞く {player, amount, reason}（combat 他。負は回復）
  STAMINA: "stamina",                   // 出す {player, value, max, exhausted}（combat が聞く）
  WEAPON_STATE: "weapon_state",         // 聞く {player, id, key, name, kind, durability, broken, ammo, mag, magMax, reloading, mods}
  FINISHER: "finisher",                 // 聞く {player, zombie, kind, result}（combat のとどめ）
  IMMUNITY_RESTORE: "immunity_restore", // 聞く {player, seconds, source}（UV の改造・UV 発煙筒など）
  UV_ZONE: "uv_zone",                   // 聞く {dim, pos, radius, until, source}（UV の光の範囲 = 免疫が減らず戻る）
  GRABBED: "grabbed",                   // 聞く {player, zombie}（zombies/ の掴み）
  GRAB_END: "grab_end",                 // 聞く {player, zombie?}（ゾンビ側が離した・倒れた）
  SHOVE: "shove",                       // 出す {player, zombie, dir, presses}（連打で振りほどいた。zombies/ が離す）
  PARKOUR: "parkour",                   // 出す {player, move, ...}（技が決まった。skills.js が経験値に、HUD が表示に使う）
  XP: "xp",                             // 聞く {player, tree: "parkour" | "combat", amount, reason}（他のモジュールからの経験値）
  LEVEL_UP: "level_up",                 // 出す {player, tree, level, points}
  COMBO: "gore_combo",                  // 出す {player, list: [{key, ja, en, xp}], xp, kills}（skills.js が 1 tick 分をまとめる）
  IMMUNITY: "immunity",                 // 出す {player, value, max, kind: "warn" | "zero" | "restore" | "full"}
  NOTICE: "hud_notice",                 // 聞く {player, text, ticks?}（HUD のアクションバーに短く出す。他のモジュールも使ってよい）
});

/** 生成物の表（無い・古い時でも落ちないように any で読む）。 @type {any} */
const SD = SETTINGS_D;
/** パルクールの数値（data/settings.js の PARKOUR_TUNING）。 @type {any} */
export const PT = SD.PARKOUR_TUNING ?? {};
/** @type {any} */
const BD = BLOCKS_D;
/** @type {Record<string, any>} */
const BLOCK_BY_ID = BD.BLOCK_BY_ID ?? {};

/**
 * 数の設定値（無い・数でなければ def）。
 * @param {any} v @param {number} def @returns {number}
 */
export function nv(v, def) { const n = Number(v); return v !== undefined && v !== null && Number.isFinite(n) ? n : def; }

// ---------------------------------------------------------------------------
//  時間・ゲームモード
// ---------------------------------------------------------------------------
let loaded = false;
world.afterEvents.worldLoad.subscribe(() => { loaded = true; });
/** worldLoad の後か（テスト・デバッグ用）。 */
export function isLoaded() { return loaded; }

/** 夜か（13000〜22999。偽物の約束と同じ）。 @param {number} [time] */
export function isNight(time) {
  let t = time;
  if (t === undefined) { try { t = world.getTimeOfDay(); } catch { t = 6000; } }
  return t >= 13000 && t < 23000;
}

/** 空の明るさの倍率（昼 1、夜 4/15、夕方・明け方はなめらかに）。 @param {number} t 0..23999 */
export function skyFactor(t) {
  const NIGHT = 4 / 15;
  if (t >= 13000 && t < 23000) return NIGHT;
  if (t >= 12000 && t < 13000) return 1 - (1 - NIGHT) * ((t - 12000) / 1000);
  if (t >= 23000) return NIGHT + (1 - NIGHT) * ((t - 23000) / 1000);
  return 1;
}

/** サバイバル・アドベンチャーで生きているか（クリエイティブ・スペクテイターはパルクール・スタミナ・免疫の外）。 @param {Player} p */
export function isActive(p) {
  if (!valid(p)) return false;
  try {
    const m = p.getGameMode();
    if (m !== GameMode.Survival && m !== GameMode.Adventure) return false;
    const h = p.getComponent("minecraft:health");
    return !h || h.currentValue > 0;
  } catch { return false; }
}

/** 体力 {cur, max}（読めなければ 20/20）。 @param {Player} p */
export function healthOf(p) {
  try {
    const h = p.getComponent("minecraft:health");
    if (h) return { cur: h.currentValue, max: h.effectiveMax };
  } catch { /* 無い */ }
  return { cur: 20, max: 20 };
}

/** 体力を書く（0..最大に丸める）。 @param {Player} p @param {number} v */
export function setHealth(p, v) {
  try {
    const h = p.getComponent("minecraft:health");
    if (!h) return false;
    h.setCurrentValue(clamp(v, 0, h.effectiveMax));
    return true;
  } catch { return false; }
}

// ---------------------------------------------------------------------------
//  プレイヤーごとの控え（抜けたら消える）
// ---------------------------------------------------------------------------
/** @type {Map<string, any>[]} */
const maps = [];
/**
 * プレイヤーの ID をキーにした Map（playerLeave で自動で消える）。
 * @template T @returns {Map<string, T>}
 */
export function playerMap() { /** @type {Map<string, T>} */ const m = new Map(); maps.push(m); return m; }
world.afterEvents.playerLeave.subscribe((ev) => { for (const m of maps) m.delete(ev.playerId); });

// ---------------------------------------------------------------------------
//  tick の登録（1 本の runInterval で順に回す。例外は console.error（テストでは失敗になる）で 1 回だけ）
// ---------------------------------------------------------------------------
/** @type {{label: string, every: number, fn: (p: Player, t: number) => void}[]} */
const playerTickers = [];
/** @type {{label: string, every: number, fn: (t: number) => void}[]} */
const worldTickers = [];
/** @type {Map<string, number>} */
const errAt = new Map();
/** @param {string} label @param {unknown} err */
function report(label, err) {
  const t = now();
  const last = errAt.get(label);
  if (last !== undefined && t - last < 200) return;
  errAt.set(label, t);
  console.error(`[nr] player/${label}`, err instanceof Error ? `${err.message}\n${err.stack ?? ""}` : String(err));
}
/**
 * 全プレイヤーに every tick ごと（登録した順に回る）。
 * @param {string} label @param {number} every @param {(p: Player, t: number) => void} fn
 */
export function onPlayerTick(label, every, fn) { playerTickers.push({ label, every: Math.max(1, Math.floor(every)), fn }); }
/** every tick ごと（プレイヤーの後）。 @param {string} label @param {number} every @param {(t: number) => void} fn */
export function onWorldTick(label, every, fn) { worldTickers.push({ label, every: Math.max(1, Math.floor(every)), fn }); }
/**
 * 例外を握って呼ぶ（console.error を 200 tick に 1 回）。
 * @template R @param {string} label @param {() => R} fn @returns {R | undefined}
 */
export function guard(label, fn) { try { return fn(); } catch (err) { report(label, err); return undefined; } }

system.runInterval(() => {
  if (!loaded) return;
  const t = now();
  /** @type {Player[]} */
  let players = [];
  try { players = world.getAllPlayers(); } catch { players = []; }
  for (const tk of playerTickers) {
    if (t % tk.every !== 0) continue;
    for (const p of players) {
      if (!valid(p)) continue;
      try { tk.fn(p, t); } catch (err) { report(tk.label, err); }
    }
  }
  for (const tk of worldTickers) {
    if (t % tk.every !== 0) continue;
    try { tk.fn(t); } catch (err) { report(tk.label, err); }
  }
}, 1);

// ---------------------------------------------------------------------------
//  プレイヤーを動かす（applyKnockback({x, z}, 縦) だけ。水平は強さ込みのベクトル）
// ---------------------------------------------------------------------------
/**
 * 速度を置き換える（実機の applyKnockback はプレイヤーの速度をこの値にする）。
 * @param {Player} p @param {number} hx @param {number} hz @param {number} vy
 */
export function push(p, hx, hz, vy) {
  if (!Number.isFinite(hx) || !Number.isFinite(hz) || !Number.isFinite(vy)) return false;
  const h = Math.hypot(hx, hz);
  const k = h > 3 ? 3 / h : 1;
  try { p.applyKnockback({ x: hx * k, z: hz * k }, clamp(vy, -3, 3)); return true; } catch { return false; }
}

// ---------------------------------------------------------------------------
//  地形: ブロックの当たりの高さ（0 = 当たり無し、1 = 1 段、1.5 = 柵・塀）
// ---------------------------------------------------------------------------
const PASS_EXACT = new Set([
  "minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:structure_void", "minecraft:light_block",
  "minecraft:water", "minecraft:flowing_water", "minecraft:lava", "minecraft:flowing_lava", "minecraft:fire", "minecraft:soul_fire",
  "minecraft:short_grass", "minecraft:tall_grass", "minecraft:fern", "minecraft:large_fern", "minecraft:deadbush", "minecraft:seagrass",
  "minecraft:kelp", "minecraft:vine", "minecraft:weeping_vines", "minecraft:twisting_vines", "minecraft:glow_lichen", "minecraft:sculk_vein",
  "minecraft:ladder", "minecraft:torch", "minecraft:soul_torch", "minecraft:redstone_torch", "minecraft:unlit_redstone_torch",
  "minecraft:lever", "minecraft:tripwire", "minecraft:trip_wire", "minecraft:tripwire_hook", "minecraft:redstone_wire", "minecraft:rail",
  "minecraft:golden_rail", "minecraft:detector_rail", "minecraft:activator_rail", "minecraft:web", "minecraft:cobweb",
  "minecraft:sweet_berry_bush", "minecraft:reeds", "minecraft:sugar_cane", "minecraft:wheat", "minecraft:carrots", "minecraft:potatoes",
  "minecraft:beetroot", "minecraft:melon_stem", "minecraft:pumpkin_stem", "minecraft:nether_wart", "minecraft:pink_petals",
  "minecraft:hanging_roots", "minecraft:spore_blossom", "minecraft:crimson_roots", "minecraft:warped_roots", "minecraft:nether_sprouts",
  "minecraft:poppy", "minecraft:dandelion", "minecraft:red_flower", "minecraft:yellow_flower", "minecraft:blue_orchid", "minecraft:allium",
  "minecraft:azure_bluet", "minecraft:oxeye_daisy", "minecraft:cornflower", "minecraft:lily_of_the_valley", "minecraft:wither_rose",
  "minecraft:end_portal", "minecraft:portal", "minecraft:end_gateway", "minecraft:powder_snow", "minecraft:snow_layer",
]);
const PASS_RE = /(_sapling|_button|_pressure_plate|_sign|_banner|carpet|_tulip|_mushroom|coral_fan|_coral|_flower|_vines|_torch|_rail)$/;
const TALL_RE = /(_fence|_wall|fence_gate|^minecraft:fence|^minecraft:cobblestone_wall|^minecraft:border_block)$/;
const SLAB_RE = /_slab$/;

/** @type {Map<string, number>} */
const nrHeight = new Map();
for (const [id, b] of Object.entries(BLOCK_BY_ID)) {
  const c = b?.collision;
  if (c === false || c === null) nrHeight.set(id, 0);
  else if (c && Array.isArray(c.origin) && Array.isArray(c.size)) nrHeight.set(id, clamp((nv(c.origin[1], 0) + nv(c.size[1], 16)) / 16, 0, 1.5));
  else nrHeight.set(id, 1);
}

/**
 * ブロックの当たりの上端（ブロックの底から。0 = 通り抜けられる）。
 * @param {Block | undefined} b @returns {number}
 */
export function blockHeight(b) {
  if (!b) return 0;
  let id = "";
  try { id = b.typeId; } catch { return 0; }
  if (!id) return 0;
  const nr = nrHeight.get(id);
  if (nr !== undefined) return nr;
  if (PASS_EXACT.has(id) || PASS_RE.test(id)) return 0;
  if (TALL_RE.test(id)) return 1.5;
  if (SLAB_RE.test(id) && !id.includes("double")) {
    try {
      const half = b.permutation.getState(/** @type {any} */ ("minecraft:vertical_half"));
      return half === "top" ? 1 : 0.5;
    } catch { return 0.5; }
  }
  return 1;
}

/** @param {Dimension} dim @param {number} x @param {number} y @param {number} z @returns {Block | undefined} */
export function blockAt(dim, x, y, z) {
  try { return dim.getBlock({ x: Math.floor(x), y: Math.floor(y), z: Math.floor(z) }); } catch { return undefined; }
}

/** その点が当たりの中か（下のブロックの柵・塀の背の高い当たりも見る）。 @param {Dimension} dim @param {Vector3} p */
export function solidAt(dim, p) {
  const by = Math.floor(p.y);
  const h = blockHeight(blockAt(dim, p.x, by, p.z));
  if (h > 0 && p.y - by < h) return true;
  const h2 = blockHeight(blockAt(dim, p.x, by - 1, p.z));
  return h2 > 1 && p.y - (by - 1) < h2;
}

/**
 * 柱（x, z）の y0 から上の当たりの上端（地面からの段差の高さを測る）。lo..hi の層だけ見る。
 * 一番下の層が空いていれば undefined（障害物ではない）。
 * @param {Dimension} dim @param {number} x @param {number} z @param {number} lo 最初の層（整数） @param {number} hi 最後の層（整数）
 * @returns {number | undefined} 上端のワールド y
 */
export function columnTop(dim, x, z, lo, hi) {
  let top;
  for (let y = lo; y <= hi; y++) {
    const h = blockHeight(blockAt(dim, x, y, z));
    if (h <= 0) { if (top === undefined) return undefined; break; }
    top = y + h;
    if (h < 1) break;
  }
  return top;
}

/** 柱（x, z）の y0..y1 の間が全部空いているか。 @param {Dimension} dim @param {number} x @param {number} z @param {number} y0 @param {number} y1 */
export function clearColumn(dim, x, z, y0, y1) {
  for (let y = y0; y <= y1 + 1e-6; y += 0.9) if (solidAt(dim, { x, y, z })) return false;
  return !solidAt(dim, { x, y: y1, z });
}

/** パルクールのタグ（data/blocks.js の parkour: climb / vault / landing / zipline / updraft）。 @param {string} typeId @returns {string[]} */
export function parkourTags(typeId) {
  const t = BLOCK_BY_ID[typeId]?.parkour;
  return Array.isArray(t) ? t : [];
}

/**
 * 足元から下へ地面を探す（当たりのある最初のブロックの上端）。
 * @param {Dimension} dim @param {Vector3} at @param {number} [reach]
 * @returns {{y: number, typeId: string} | undefined}
 */
export function groundBelow(dim, at, reach = 48) {
  const x = at.x, z = at.z;
  const start = Math.floor(at.y);
  for (let y = start; y >= start - reach; y--) {
    const b = blockAt(dim, x, y, z);
    const h = blockHeight(b);
    if (h > 0 && y + h <= at.y + 1e-3) return { y: y + h, typeId: b?.typeId ?? "" };
    if (h > 0 && y === start) continue;
  }
  return undefined;
}

/** 光るブロックの明るさ（data/blocks.js の light_emission と、バニラの主な光源）。 */
export const LIGHT_BLOCKS = (() => {
  /** @type {Record<string, number>} */
  const m = {
    "minecraft:torch": 14, "minecraft:lantern": 15, "minecraft:glowstone": 15, "minecraft:sea_lantern": 15, "minecraft:shroomlight": 15,
    "minecraft:lit_pumpkin": 15, "minecraft:campfire": 15, "minecraft:soul_campfire": 10, "minecraft:soul_torch": 10,
    "minecraft:soul_lantern": 10, "minecraft:end_rod": 14, "minecraft:beacon": 15, "minecraft:lit_redstone_lamp": 15,
    "minecraft:lava": 15, "minecraft:fire": 15, "minecraft:ochre_froglight": 15, "minecraft:verdant_froglight": 15,
    "minecraft:pearlescent_froglight": 15,
  };
  for (const [id, b] of Object.entries(BLOCK_BY_ID)) { const le = nv(b?.light_emission, 0); if (le > 0) m[id] = le; }
  return Object.freeze(m);
})();

/**
 * 角度の差（-180..180）。 @param {number} a @param {number} b
 */
export function angleDiff(a, b) { let d = (a - b) % 360; if (d > 180) d -= 360; if (d < -180) d += 360; return d; }
