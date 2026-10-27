// ===========================================================================
//  NIGHT RUNNER: 感染都市 — combat/ の共通の小物
//
//  武器の表引き（data/weapons.js）・手の持ち物・持ち物の数え方・スキルとスタミナの問い合わせ・
//  バスへの知らせ（stamina_cost / noise / weapon_state …）・弾の控え・プレイヤーごとの tick・説明文（lore）。
//  combat/ の各モジュール（melee / ranged / throwables / mods / durability / finishers）が使う。
//  ここはワールドを最上位で触らない（runInterval の中は worldLoad の後だけ動く）。
// ===========================================================================
import { world, system, ItemStack } from "@minecraft/server";
import { WEAPON_BY_ID, ANIM_SETS, SFX_SETS, RARITY } from "../data/weapons.js";
import { MOD_BY_KEY } from "../data/mods.js";
import { SKILL_BY_KEY } from "../data/skills.js";
import { PARKOUR_TUNING } from "../data/settings.js";
import { emit, on } from "../core/bus.js";
import { zombieSpec } from "../core/hp.js";
import { valid, now, add, scale, norm, safe, warnOnce, clamp } from "../core/util.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */
/** @typedef {import("@minecraft/server").ContainerSlot} ContainerSlot */
/** @typedef {import("@minecraft/server").Container} Container */

// ---------------------------------------------------------------------------
//  バスの出来事（combat が出す・聞くもの。core/bus.js の EV に無い分）
// ---------------------------------------------------------------------------
/** combat/ の出来事の名前。中身の形は reference/nr_scripts.md と combat/index.js の先頭のとおり。 */
export const CEV = Object.freeze({
  STAMINA_COST: "stamina_cost",     // {player, amount, reason}（amount < 0 は回復。player/stamina.js が使う）
  STAMINA: "stamina",               // {player, value, max, exhausted?}（player/stamina.js が出す。combat は聞くだけ）
  NOISE: "noise",                   // {pos, radius, dim, source, player?}（zombies/noise.js が聞く）
  WEAPON_STATE: "weapon_state",     // {player, id, key, name, kind, durability, broken, ammo, mag, magMax, reloading, mods}
  FINISHER: "finisher",             // {player, zombie, kind: "stomp" | "decap", result}
  IMMUNITY: "immunity_restore",     // {player, seconds, source}（UV の改造で仕留めた・UV 発煙筒の中）
  UV_ZONE: "uv_zone",               // {dim, pos, radius, until, source}（UV 発煙筒の光の範囲）
  FIRE_ZONE: "fire_zone",           // {dim, pos, radius, until}（火炎瓶の火の範囲）
  LURE: "lure",                     // {dim, pos, radius, until, pull}（爆竹・パイプ爆弾の誘い）
});

// ---------------------------------------------------------------------------
//  武器の表
// ---------------------------------------------------------------------------
/** @type {Record<string, any>} */
const WBY = /** @type {any} */ (WEAPON_BY_ID) ?? {};
/** @type {Record<string, any>} */
const SETS = /** @type {any} */ (ANIM_SETS) ?? {};
/** @type {Record<string, any>} */
const SFX = /** @type {any} */ (SFX_SETS) ?? {};
/** @type {Record<string, any>} */
const RAR = /** @type {any} */ (RARITY) ?? {};

/**
 * 武器の定義（data/weapons.js）。ID・ItemStack・定義そのもののどれでも。NR の武器でなければ undefined。
 * @param {any} x @returns {any}
 */
export function weaponOf(x) {
  if (!x) return undefined;
  if (typeof x === "string") return WBY[x] ?? WBY[`nr:w_${x}`];
  if (typeof x === "object" && typeof x.typeId === "string") return WBY[x.typeId];
  if (typeof x === "object" && typeof x.id === "string" && x.kind) return x;
  return undefined;
}
/** 振りのモーションの組（ANIM_SETS の 1 行）。 @param {any} w @returns {any} */
export function animSetOf(w) { return SETS[w?.anim_set] ?? {}; }
/** 音の組（SFX_SETS の 1 行）。 @param {any} w @returns {Record<string, string>} */
export function sfxOf(w) { return SFX[w?.sfx] ?? {}; }

/** 説明文の色・倍率・改造の枠（ItemStack の nr:rarity があればそれ、無ければ武器の既定）。 @param {any} w @param {any} [item] */
export function rarityOf(w, item) {
  let k = w?.rarity ?? "common";
  try {
    const v = item && !item.isStackable ? item.getDynamicProperty("nr:rarity") : undefined;
    if (typeof v === "string" && RAR[v]) k = v;
  } catch { /* 読めない */ }
  return { key: k, ...(RAR[k] ?? RAR.common ?? { ja: "", color: "§f", stat_mult: 1, mod_slots: 1 }) };
}

// ---------------------------------------------------------------------------
//  手の持ち物・持ち物
// ---------------------------------------------------------------------------
/**
 * @typedef {object} Held
 * @property {number} index           選んでいるスロット
 * @property {ContainerSlot} slot     そのスロット（動的プロパティ・lore を直接書ける）
 * @property {ItemStack | undefined} item   写し（書き換えたら slot.setItem で戻す）
 * @property {any} w                  武器の定義（NR の武器でなければ undefined）
 * @property {Container} container
 */
/** 手（選んでいるスロット）の持ち物。 @param {Player} p @returns {Held | undefined} */
export function heldInfo(p) {
  if (!valid(p)) return undefined;
  try {
    const container = /** @type {any} */ (p.getComponent("minecraft:inventory"))?.container;
    if (!container) return undefined;
    const index = p.selectedSlotIndex;
    const slot = container.getSlot(index);
    const item = container.getItem(index);
    return { index, slot, item, w: item ? weaponOf(item.typeId) : undefined, container };
  } catch { return undefined; }
}
/** 持ち物の入れ物。 @param {Player} p @returns {Container | undefined} */
export function containerOf(p) {
  try { return /** @type {any} */ (p.getComponent("minecraft:inventory"))?.container; } catch { return undefined; }
}
/** 持ち物の中のその ID の数。 @param {Player} p @param {string} id */
export function countItem(p, id) {
  const c = containerOf(p);
  if (!c || !id) return 0;
  let n = 0;
  for (let i = 0; i < c.size; i++) {
    const it = c.getItem(i);
    if (it?.typeId === id) n += it.amount;
  }
  return n;
}
/**
 * 持ち物からその ID を n 個取り除く（手のスロットは最後に使う）。取り除けた数を返す。
 * @param {Player} p @param {string} id @param {number} n
 */
export function takeItem(p, id, n) {
  const c = containerOf(p);
  if (!c || !id || n <= 0) return 0;
  let left = Math.floor(n);
  const sel = p.selectedSlotIndex;
  const order = [];
  for (let i = 0; i < c.size; i++) if (i !== sel) order.push(i);
  order.push(sel);
  for (const i of order) {
    if (left <= 0) break;
    const it = c.getItem(i);
    if (it?.typeId !== id) continue;
    const k = Math.min(left, it.amount);
    left -= k;
    if (it.amount - k <= 0) c.setItem(i, undefined);
    else { it.amount -= k; c.setItem(i, it); }
  }
  return Math.floor(n) - left;
}
/**
 * 持ち物に入れる（入りきらない分は足元に落とす）。
 * @param {Player} p @param {string} id @param {number} n
 */
export function giveItem(p, id, n = 1) {
  if (!valid(p) || n <= 0) return;
  let st;
  try { st = new ItemStack(id, Math.max(1, Math.floor(n))); } catch (err) { warnOnce(`give:${id}`, "ItemStack を作れない", id, err); return; }
  const c = containerOf(p);
  let rest;
  try { rest = c ? c.addItem(st) : st; } catch { rest = st; }
  if (rest) safe("giveItem.drop", () => p.dimension.spawnItem(/** @type {ItemStack} */ (rest), p.location));
}
/** 手の持ち物を消す（壊れた・使い切った）。 @param {Player} p */
export function clearHeld(p) {
  const h = heldInfo(p);
  if (h) safe("clearHeld", () => h.slot.setItem(undefined));
}
/** 手のスロットの動的プロパティ（重ねられないアイテムだけ）。 @param {Held | undefined} h @param {string} k */
export function heldDp(h, k) {
  if (!h?.item || h.item.isStackable) return undefined;
  try { return h.slot.getDynamicProperty(k); } catch { return undefined; }
}
/** @param {Held | undefined} h @param {string} k @param {boolean | number | string | undefined} v */
export function setHeldDp(h, k, v) {
  if (!h?.item || h.item.isStackable) return false;
  try { h.slot.setDynamicProperty(k, v); return true; } catch (err) { warnOnce(`dp:${k}`, "動的プロパティを書けない", k, err); return false; }
}

// ---------------------------------------------------------------------------
//  スキル・スタミナ（player/ の持ち物。問い合わせの差し込み口）
// ---------------------------------------------------------------------------
/** @type {((p: Player, key: string) => boolean) | undefined} */
let skillQuery;
/**
 * スキルを持っているかの問い合わせを差し込む（player/skills.js）。無ければプレイヤーの動的プロパティ
 * `nr:skills`（JSON: 鍵の配列か {鍵: 段階}）を読む。
 * @param {((p: Player, key: string) => boolean) | undefined} fn
 */
export function setSkillQuery(fn) { skillQuery = fn; }
/** @param {Player} p @param {string} key @returns {boolean} */
export function hasSkill(p, key) {
  if (!valid(p)) return false;
  if (skillQuery) return !!safe("skillQuery", () => skillQuery?.(p, key));
  try {
    const raw = p.getDynamicProperty("nr:skills");
    if (typeof raw !== "string" || !raw) return false;
    const v = JSON.parse(raw);
    if (Array.isArray(v)) return v.includes(key);
    return !!(v && typeof v === "object" && v[key]);
  } catch { return false; }
}
/** スキルの効果（data/skills.js の effect）。持っていなければ undefined。 @param {Player} p @param {string} key @returns {any} */
export function skillEff(p, key) {
  if (!hasSkill(p, key)) return undefined;
  return /** @type {any} */ (SKILL_BY_KEY)?.[key]?.effect ?? {};
}

/** @type {((p: Player) => ({value: number, max: number, exhausted?: boolean} | undefined)) | undefined} */
let staminaQuery;
/** @type {Map<string, {value: number, max: number, exhausted?: boolean}>} */
const staminaSeen = new Map();
/**
 * 今のスタミナの問い合わせを差し込む（player/stamina.js）。無ければバスの "stamina" の最新の値。
 * @param {((p: Player) => ({value: number, max: number, exhausted?: boolean} | undefined)) | undefined} fn
 */
export function setStaminaQuery(fn) { staminaQuery = fn; }
on(CEV.STAMINA, (d) => {
  const p = d?.player;
  if (!p?.id) return;
  staminaSeen.set(p.id, { value: Number(d.value) || 0, max: Number(d.max) || 100, exhausted: typeof d.exhausted === "boolean" ? d.exhausted : undefined });
});
/** @param {Player} p */
export function staminaOf(p) {
  if (staminaQuery) return safe("staminaQuery", () => staminaQuery?.(p));
  return staminaSeen.get(p.id);
}
/** 息切れ（スタミナが PARKOUR_TUNING.stamina.exhausted_below 未満）。分からなければ false。 @param {Player} p */
export function isExhausted(p) {
  const s = staminaOf(p);
  if (!s) return false;
  if (typeof s.exhausted === "boolean") return s.exhausted;
  const below = Number(/** @type {any} */ (PARKOUR_TUNING)?.stamina?.exhausted_below ?? 10);
  return Number(s.value) < below;
}
/** スタミナを使う（player/stamina.js がバスで受け取って減らす）。 @param {Player} p @param {number} amount @param {string} reason */
export function spendStamina(p, amount, reason) {
  if (!valid(p) || !Number.isFinite(amount) || amount === 0) return;
  emit(CEV.STAMINA_COST, { player: p, amount: Math.round(amount * 10) / 10, reason });
}

// ---------------------------------------------------------------------------
//  音の知らせ・時間・ゾンビの区分
// ---------------------------------------------------------------------------
/** 音（ゾンビが寄ってくる）。 @param {Dimension} dim @param {Vector3} pos @param {number} radius @param {string} source @param {Player} [player] */
export function noise(dim, pos, radius, source, player) {
  if (!dim || !(radius > 0)) return;
  emit(CEV.NOISE, { pos: { x: pos.x, y: pos.y, z: pos.z }, radius, dim, source, player });
}
/** 夜か（13000〜22999）。 */
export function isNight() {
  try { const t = world.getTimeOfDay(); return t >= 13000 && t < 23000; } catch { return false; }
}
/** ゾンビの区分（common / viral / special / night / boss）。 @param {Entity} z @returns {string} */
export function zclass(z) { return String(/** @type {any} */ (zombieSpec(z))?.cls ?? "common"); }
/** ボスか。 @param {Entity} z */
export function isBoss(z) { const s = /** @type {any} */ (zombieSpec(z)); return !!(s?.boss || s?.cls === "boss"); }

// ---------------------------------------------------------------------------
//  視線
// ---------------------------------------------------------------------------
/** 目と視線。 @param {Player} p @returns {{eye: Vector3, dir: Vector3}} */
export function eyeRay(p) {
  const eye = p.getHeadLocation();
  const dir = norm(p.getViewDirection());
  return { eye, dir };
}
/** 視線の右（水平）。 @param {Vector3} dir */
export function rightOf(dir) { return norm({ x: -dir.z, y: 0, z: dir.x }, { x: 1, y: 0, z: 0 }); }
/** 手元（銃口・投げる手）の位置。 @param {Player} p @param {Vector3} dir @param {number} [fwd] */
export function handPos(p, dir, fwd = 0.7) {
  const eye = p.getHeadLocation();
  const r = rightOf(dir);
  return add(add(eye, scale(dir, fwd)), add(scale(r, -0.28), { x: 0, y: -0.18, z: 0 }));
}
/** 向きを度で散らす（円錐の中の一様に近い向き）。 @param {Vector3} d @param {number} deg */
export function spreadDir(d, deg) {
  if (!(deg > 0)) return norm(d);
  const n = norm(d);
  const a = Math.tan((deg * Math.PI) / 180) * Math.sqrt(Math.random());
  const th = Math.random() * Math.PI * 2;
  const r = rightOf(n);
  // 上（n と r に直交）
  const u = norm({ x: r.y * n.z - r.z * n.y, y: r.z * n.x - r.x * n.z, z: r.x * n.y - r.y * n.x }, { x: 0, y: 1, z: 0 });
  return norm(add(n, add(scale(r, Math.cos(th) * a), scale(u, Math.sin(th) * a))));
}

// ---------------------------------------------------------------------------
//  弾の控え（ranged / throwables が出した nr:proj_*）
// ---------------------------------------------------------------------------
/**
 * @typedef {object} ProjMeta
 * @property {string} kind        "arrow" | "bolt" | "knife" | "star" | "molotov" | "pipe_bomb" | "firecracker" | "uv_flare"
 * @property {any} w              撃った・投げた武器
 * @property {Player | undefined} shooter
 * @property {number} damage      当たった時の基本ダメージ（溜め・レア度の後）
 * @property {number} power       0..1 の溜め
 * @property {Record<string, number>} mods
 * @property {number} born
 * @property {boolean} [crit]
 * @property {boolean} [hit]      もう当たった（二重に数えない）
 * @property {Vector3} [lastPos]
 * @property {Dimension} [dim]
 * @property {any} [extra]
 */
/** @type {Map<string, ProjMeta>} */
export const projectiles = new Map();
/** 弾を控えに入れる。 @param {Entity} e @param {ProjMeta} meta */
export function trackProjectile(e, meta) {
  if (!valid(e)) return;
  projectiles.set(e.id, meta);
  if (projectiles.size > 256) { const k = projectiles.keys().next().value; if (k !== undefined) projectiles.delete(k); }
}
/** @param {Entity | undefined} e @returns {ProjMeta | undefined} */
export function projMeta(e) {
  if (!e) return undefined;
  try { return projectiles.get(e.id); } catch { return undefined; }
}

// ---------------------------------------------------------------------------
//  リロード中（ranged が書き、weapon_state が読む）
// ---------------------------------------------------------------------------
/** @type {Map<string, {until: number, slot: number, typeId: string, perShell: boolean, next: number}>} */
export const reloading = new Map();

// ---------------------------------------------------------------------------
//  説明文（lore）: レア度・改造・壊れている
// ---------------------------------------------------------------------------
const ROMAN = ["", "I", "II", "III", "IV", "V"];
/** @param {number} n */
export function roman(n) { return ROMAN[n] ?? String(n); }

/**
 * 改造（{鍵: 段階}）を読む。ItemStack か ContainerSlot の nr:mods（JSON）。
 * @param {any} it @returns {Record<string, number>}
 */
export function readMods(it) {
  try {
    if (!it || it.isStackable) return {};
    const raw = it.getDynamicProperty("nr:mods");
    if (typeof raw !== "string" || !raw) return {};
    const o = JSON.parse(raw);
    /** @type {Record<string, number>} */
    const out = {};
    if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) if (MOD_BY_KEY && /** @type {any} */ (MOD_BY_KEY)[k] && Number(v) > 0) out[k] = clamp(Math.round(Number(v)), 1, 3);
    return out;
  } catch { return {}; }
}

/**
 * 説明文を作り直す（50 文字・20 行まで）。slot は ContainerSlot（重ねられない武器だけ）。
 * @param {ContainerSlot} slot @param {any} w
 */
export function refreshLore(slot, w) {
  try {
    if (!slot?.hasItem() || slot.isStackable || !w) return;
    const R = rarityOf(w, slot);
    const mods = readMods(slot);
    const keys = Object.keys(mods);
    /** @type {string[]} */
    const lines = [`${R.color}${R.ja}§7 ・ 改造 ${keys.length}/${R.mod_slots}`];
    for (const k of keys) {
      const m = /** @type {any} */ (MOD_BY_KEY)[k];
      if (!m) continue;
      lines.push(`§6${m.ja} ${roman(mods[k])}`);
      lines.push(`§7${String(m.lore_ja ?? "").slice(0, 46)}`);
    }
    if (slot.getDynamicProperty("nr:broken") === true) lines.push("§c[壊れている] 修理キットで直す");
    slot.setLore(lines.slice(0, 20).map((s) => s.slice(0, 50)));
  } catch (err) { warnOnce("lore", "説明文を書けない", err); }
}

// ---------------------------------------------------------------------------
//  HUD への知らせ（weapon_state）
// ---------------------------------------------------------------------------
/** @type {Map<string, string>} */
const lastState = new Map();
/**
 * 手の武器の状態。durability は残りの割合 0..1（耐久の無い物は -1）、ammo は持ち物の弾・投げ物の数（無ければ -1）、
 * mag は弾倉の中（無ければ -1）。
 * @param {Player} p
 */
export function weaponState(p) {
  const h = heldInfo(p);
  const w = h?.w;
  const it = h?.item;
  /** @type {any} */
  const s = { player: p, id: it?.typeId ?? "", key: w?.key ?? "", name: w?.ja ?? "", kind: w?.kind ?? "", durability: -1, broken: false, ammo: -1, mag: -1, magMax: 0, reloading: reloading.has(p.id), mods: {} };
  if (!w || !it || !h) return s;
  try {
    const d = /** @type {any} */ (it.getComponent("minecraft:durability"));
    if (d && d.maxDurability > 0) {
      const lossRaw = heldDp(h, "nr:max_loss");
      const loss = typeof lossRaw === "number" ? clamp(lossRaw, 0, 0.9) : 0;
      const cap = Math.max(1, Math.floor(d.maxDurability * (1 - loss)) - 1);
      s.durability = Math.round(clamp(1 - d.damage / cap, 0, 1) * 1000) / 1000;
    }
  } catch { /* 耐久なし */ }
  s.broken = heldDp(h, "nr:broken") === true;
  s.mods = readMods(it);
  if (w.kind === "gun" || w.kind === "crossbow") {
    s.magMax = Math.max(1, Number(w.mag) || 1);
    const m = heldDp(h, "nr:mag");
    s.mag = typeof m === "number" ? m : s.magMax;
  }
  if (w.ammo) s.ammo = countItem(p, w.ammo);
  else if (w.kind === "throwable") s.ammo = countItem(p, w.id);
  return s;
}
/** 状態が変わった時だけ weapon_state を出す（force なら必ず）。 @param {Player} p @param {boolean} [force] */
export function publishWeaponState(p, force = false) {
  if (!valid(p)) return;
  const s = weaponState(p);
  const key = JSON.stringify({ ...s, player: undefined });
  if (!force && lastState.get(p.id) === key) return;
  lastState.set(p.id, key);
  emit(CEV.WEAPON_STATE, s);
}

// ---------------------------------------------------------------------------
//  プレイヤーごと・ワールドの tick（worldLoad の後だけ）
// ---------------------------------------------------------------------------
let loaded = false;
world.afterEvents.worldLoad.subscribe(() => { loaded = true; });
/** @type {{label: string, every: number, fn: (p: Player, t: number) => void}[]} */
const playerTickers = [];
/** @type {{label: string, every: number, fn: (t: number) => void}[]} */
const worldTickers = [];
/** 全プレイヤーに every tick ごと。 @param {string} label @param {number} every @param {(p: Player, t: number) => void} fn */
export function onPlayerTick(label, every, fn) { playerTickers.push({ label, every: Math.max(1, Math.floor(every)), fn }); }
/** every tick ごと。 @param {string} label @param {number} every @param {(t: number) => void} fn */
export function onWorldTick(label, every, fn) { worldTickers.push({ label, every: Math.max(1, Math.floor(every)), fn }); }

system.runInterval(() => {
  if (!loaded) return;
  const t = now();
  if (playerTickers.length) {
    /** @type {Player[]} */
    let players = [];
    try { players = world.getAllPlayers(); } catch { players = []; }
    for (const tk of playerTickers) {
      if (t % tk.every !== 0) continue;
      for (const p of players) if (valid(p)) safe(tk.label, () => tk.fn(p, t));
    }
  }
  for (const tk of worldTickers) if (t % tk.every === 0) safe(tk.label, () => tk.fn(t));
}, 1);

// 手の持ち物が変わったら HUD へ（4 tick ごとに見る）
onPlayerTick("weapon_state", 4, (p) => publishWeaponState(p));
world.afterEvents.playerLeave.subscribe((ev) => { lastState.delete(ev.playerId); staminaSeen.delete(ev.playerId); reloading.delete(ev.playerId); });
world.afterEvents.entityRemove.subscribe((ev) => { if (ev.typeId.startsWith("nr:proj_")) projectiles.delete(ev.removedEntityId); });
