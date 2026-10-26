// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 1 tick のパーティクル予算（DESIGN §11: ≤ 300）
//
//  spawnParticle 1 回 = 1 点。上限は設定 particle_budget（既定 300、最大 300）。
//  優先度ごとに「使ってよい割合」を変え、飾り（LOW）が手応え（HIGH）を食い潰さないようにする。
//  全モジュールのパーティクルは core/fx.js の particle() を通す（= ここを通る）。
// ===========================================================================
import { system } from "@minecraft/server";
import { num } from "./settings.js";

/** 優先度。LOW = 血の尾・蝿などの飾り / NORMAL = しぶき・血痕 / HIGH = 命中・切断の瞬間 / CRITICAL = 爆発・頭が弾ける */
export const PRIO = Object.freeze({ LOW: 0, NORMAL: 1, HIGH: 2, CRITICAL: 3 });
// 優先度ごとに使ってよい割合（その tick の上限に対して）
const SHARE = [0.55, 0.8, 0.95, 1.0];
const HARD_CAP = 300;

let tickNo = -1;
let used = 0;
let cap = HARD_CAP;
let denied = 0;
let deniedTotal = 0;

function roll() {
  const t = system.currentTick;
  if (t === tickNo) return;
  tickNo = t;
  used = 0;
  denied = 0;
  cap = Math.max(1, Math.min(HARD_CAP, Math.floor(num("particle_budget", HARD_CAP))));
}

/** その優先度で使える残り。@param {number} [prio] */
export function left(prio = PRIO.NORMAL) {
  roll();
  const share = SHARE[Math.max(0, Math.min(3, prio | 0))];
  return Math.max(0, Math.floor(cap * share) - used);
}

/**
 * n 点を取る。取れた点の数を返す（0..n）。all=true なら全部取れる時だけ取る。
 * @param {number} [n] @param {number} [prio] @param {boolean} [all]
 */
export function take(n = 1, prio = PRIO.NORMAL, all = true) {
  const want = Math.max(0, Math.ceil(n));
  const room = left(prio);
  const got = all ? (room >= want ? want : 0) : Math.min(room, want);
  used += got;
  if (got < want) { denied += want - got; deniedTotal += want - got; }
  return got;
}

/** n 点が取れるか（取らない）。@param {number} [n] @param {number} [prio] */
export function can(n = 1, prio = PRIO.NORMAL) { return left(prio) >= n; }

/**
 * 量の倍率 0..1（予算が混んできたら演出の数を減らすのに使う）。残りが多いほど 1。
 * @param {number} [prio]
 */
export function pressure(prio = PRIO.NORMAL) {
  roll();
  const lim = Math.floor(cap * SHARE[Math.max(0, Math.min(3, prio | 0))]);
  return lim <= 0 ? 0 : Math.max(0, Math.min(1, (lim - used) / lim));
}

/** いまの tick の使用状況。 */
export function stats() { roll(); return { tick: tickNo, used, cap, denied, deniedTotal }; }
