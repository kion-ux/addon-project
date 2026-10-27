// ===========================================================================
//  NIGHT RUNNER: 感染都市 — スタミナ（DESIGN §7、PARKOUR_TUNING.stamina）
//
//  * 減る: パルクール（parkour.js が consumeStamina を呼ぶ）、ジャンプ、攻撃・投擲（combat がバス "stamina_cost"
//    {player, amount, reason} を出す。負は回復）。ダッシュ中の消費は sprint_per_tick（今の表では 0）。
//  * 戻る: 最後に使ってから regen_delay_ticks 後に regen_per_tick（スキル second_wind の stamina_regen_mult、
//    エナジードリンクの regen_mult を掛ける）。食べ物・飲み物の use.stamina でまとめて戻る。
//  * 息切れ: exhausted_below 未満で息切れ（鈍足 exhausted_slow_amp・息の音）。その 3 倍まで戻ると抜ける。
//    息切れ中は費用のある技を始められない（consumeStamina が false）。
//  * 変わったらバス "stamina" {player, value, max, exhausted}（combat の息切れの判定が聞く）。
//  * 最大 = max + スキルの stamina_max_add + 動的プロパティ `nr:stamina_bonus`（抑制血清など。端末が書く）。
//  * クリエイティブ・スペクテイターは減らない。
// ===========================================================================
import { world, InputButton, ButtonState } from "@minecraft/server";
import { on, emit } from "../core/bus.js";
import { valid, now, clamp } from "../core/util.js";
import { playerSound } from "../core/fx.js";
import * as ITEMS_D from "../data/items.js";
import { PEV, PT, nv, playerMap, onPlayerTick, isActive } from "./common.js";
import { skillNum } from "./skills.js";

/** @typedef {import("@minecraft/server").Player} Player */

const ST = PT.stamina ?? {};
export const STAMINA = Object.freeze({
  max: nv(ST.max, 100),
  regen: nv(ST.regen_per_tick, 0.8),
  delay: nv(ST.regen_delay_ticks, 20),
  exhaustedBelow: nv(ST.exhausted_below, 10),
  slowAmp: Math.max(0, Math.floor(nv(ST.exhausted_slow_amp, 1))),
  sprint: nv(ST.sprint_per_tick, 0),
  jump: nv(ST.jump, 2),
});
/** 息切れから抜ける値（息切れの境の 3 倍）。 */
export const RECOVER_AT = STAMINA.exhaustedBelow * 3;
/** 最大スタミナの上乗せ（抑制血清など。数の動的プロパティ）。 */
export const STAMINA_BONUS_KEY = "nr:stamina_bonus";

/** @type {any} */
const ID = ITEMS_D;
/** @type {Record<string, any>} */
const ITEM_BY_ID = Object.fromEntries((Array.isArray(ID.ITEMS) ? ID.ITEMS : []).map((/** @type {any} */ it) => [it.id, it]));

/**
 * @typedef {{value: number, lastUse: number, exhausted: boolean, buffMult: number, buffUntil: number,
 *   pubV: number, pubEx: boolean, pubMax: number, groundT: number, breathT: number, slowT: number}} SState
 */
/** @type {Map<string, SState>} */
const states = playerMap();

/** @param {Player} p @returns {SState} */
function sstate(p) {
  let s = states.get(p.id);
  if (!s) {
    s = { value: maxStamina(p), lastUse: -9999, exhausted: false, buffMult: 1, buffUntil: -1, pubV: -1, pubEx: false, pubMax: -1, groundT: -9999, breathT: -9999, slowT: -9999 };
    states.set(p.id, s);
  }
  return s;
}

/** 最大スタミナ。 @param {Player} p */
export function maxStamina(p) {
  let bonus = 0;
  try { const b = p.getDynamicProperty(STAMINA_BONUS_KEY); if (typeof b === "number" && Number.isFinite(b)) bonus = b; } catch { /* 無い */ }
  return Math.max(1, STAMINA.max + skillNum(p, "stamina_max_add", 0) + bonus);
}

/** 今のスタミナ。 @param {Player} p @returns {{value: number, max: number, exhausted: boolean}} */
export function staminaOf(p) {
  if (!valid(p)) return { value: 0, max: STAMINA.max, exhausted: false };
  const s = sstate(p);
  const max = maxStamina(p);
  if (s.value > max) s.value = max;
  return { value: s.value, max, exhausted: s.exhausted };
}
/** 息切れか。 @param {Player} p */
export function isExhausted(p) { return valid(p) && isActive(p) && sstate(p).exhausted; }
/** その量を払えるか（息切れ中は false。クリエイティブは true）。 @param {Player} p @param {number} amount */
export function canAfford(p, amount) {
  if (!valid(p)) return false;
  if (!isActive(p)) return true;
  const s = sstate(p);
  return !s.exhausted && s.value >= amount;
}

/** @param {Player} p @param {SState} s @param {boolean} [force] */
function publish(p, s, force) {
  const max = maxStamina(p);
  if (!force && Math.abs(s.value - s.pubV) < 0.5 && s.exhausted === s.pubEx && max === s.pubMax && !(s.value >= max && s.pubV < max)) return;
  s.pubV = s.value; s.pubEx = s.exhausted; s.pubMax = max;
  emit(PEV.STAMINA, { player: p, value: Math.round(s.value * 10) / 10, max, exhausted: s.exhausted });
}
/** @param {Player} p @param {SState} s */
function updateExhausted(p, s) {
  if (!s.exhausted && s.value < STAMINA.exhaustedBelow) {
    s.exhausted = true;
    s.breathT = -9999;
  } else if (s.exhausted && s.value >= Math.min(RECOVER_AT, maxStamina(p))) {
    s.exhausted = false;
  }
}

/**
 * スタミナを使う。amount < 0 は回復。足りなければ（force でない限り）減らさず false。
 * 息切れ中は force でない消費を断る。クリエイティブなどは減らさず true。
 * @param {Player} p @param {number} amount
 * @param {{force?: boolean, reason?: string}} [opts] force: 足りなくても 0 まで減らす（攻撃など。決して断らない）
 * @returns {boolean}
 */
export function consumeStamina(p, amount, opts = {}) {
  if (!valid(p) || !Number.isFinite(amount)) return false;
  if (amount === 0) return true;
  if (!isActive(p)) return true;
  const s = sstate(p);
  const max = maxStamina(p);
  if (amount < 0) {
    s.value = Math.min(max, s.value - amount);
    updateExhausted(p, s);
    publish(p, s);
    return true;
  }
  if (!opts.force && (s.exhausted || s.value < amount)) return false;
  s.value = Math.max(0, s.value - amount);
  s.lastUse = now();
  updateExhausted(p, s);
  publish(p, s);
  return true;
}
/** 回復（量は正）。 @param {Player} p @param {number} amount */
export function restoreStamina(p, amount) { return consumeStamina(p, -Math.abs(amount)); }
/** 値を直接書く（端末・テスト）。 @param {Player} p @param {number} v */
export function setStamina(p, v) {
  if (!valid(p)) return;
  const s = sstate(p);
  s.value = clamp(v, 0, maxStamina(p));
  updateExhausted(p, s);
  publish(p, s, true);
}
/** しばらく回復を速くする（エナジードリンク）。 @param {Player} p @param {number} mult @param {number} ticks */
export function boostRegen(p, mult, ticks) {
  if (!valid(p)) return;
  const s = sstate(p);
  s.buffMult = Math.max(1, mult);
  s.buffUntil = now() + Math.max(0, Math.floor(ticks));
}

// ---------------------------------------------------------------------------
//  毎 tick: 回復・ダッシュの消費・息切れの鈍足と息
// ---------------------------------------------------------------------------
onPlayerTick("stamina", 1, (p, t) => {
  const s = sstate(p);
  if (!isActive(p)) {
    if (s.exhausted || s.value < maxStamina(p)) { s.value = maxStamina(p); s.exhausted = false; publish(p, s); }
    return;
  }
  if (p.isOnGround) s.groundT = t;
  const max = maxStamina(p);
  if (STAMINA.sprint > 0 && p.isSprinting) { s.value = Math.max(0, s.value - STAMINA.sprint); s.lastUse = t; }
  if (s.value < max && t - s.lastUse >= STAMINA.delay) {
    const buff = t < s.buffUntil ? s.buffMult : 1;
    s.value = Math.min(max, s.value + STAMINA.regen * skillNum(p, "stamina_regen_mult", 1) * buff);
  }
  if (s.value > max) s.value = max;
  updateExhausted(p, s);
  if (s.exhausted) {
    if (t - s.slowT >= 10) {
      s.slowT = t;
      try { p.addEffect("slowness", 14, { amplifier: STAMINA.slowAmp, showParticles: false }); } catch { /* 効かない */ }
    }
    if (t - s.breathT >= 40) { s.breathT = t; playerSound(p, "nr.pk.breath", { volume: 0.8 }); }
  }
  publish(p, s);
});

// ---------------------------------------------------------------------------
//  バス・入力・アイテム
// ---------------------------------------------------------------------------
on(PEV.STAMINA_COST, (d) => {
  const p = d?.player;
  const amount = Number(d?.amount);
  if (!valid(p) || !Number.isFinite(amount) || amount === 0) return;
  consumeStamina(p, amount, { force: true, reason: String(d.reason ?? "") });
});

// ジャンプ（地面を離れた直後の押下も数える）
world.afterEvents.playerButtonInput.subscribe((ev) => {
  const p = ev.player;
  if (!valid(p) || !isActive(p)) return;
  const s = sstate(p);
  if (p.isOnGround || now() - s.groundT <= 2) consumeStamina(p, STAMINA.jump, { force: true, reason: "jump" });
}, { buttons: [InputButton.Jump], state: ButtonState.Pressed });

// 食べ物・飲み物の use.stamina / regen_mult（エナジードリンク・チョコバー）
world.afterEvents.itemCompleteUse.subscribe((ev) => {
  const p = ev.source;
  const it = ev.itemStack;
  if (!valid(p) || !it) return;
  const use = ITEM_BY_ID[it.typeId]?.use;
  if (!use) return;
  if (nv(use.stamina, 0) > 0) restoreStamina(p, nv(use.stamina, 0));
  if (nv(use.regen_mult, 0) > 1) boostRegen(p, nv(use.regen_mult, 1), nv(use.duration_s, 30) * 20);
});

// 死んで戻ったら満タン
world.afterEvents.playerSpawn.subscribe((ev) => {
  const p = ev.player;
  if (!valid(p)) return;
  const s = sstate(p);
  s.value = maxStamina(p); s.exhausted = false; s.lastUse = -9999;
  publish(p, s, true);
});
