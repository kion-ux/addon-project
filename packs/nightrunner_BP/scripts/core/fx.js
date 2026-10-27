// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 演出の薄い包み（パーティクル・音・アニメ・カメラ）
//
//  * パーティクルは必ず particle() を通す（1 tick 予算 core/budget.js・ID の検査・例外の握り）。
//    変数は {名前: 数} で渡すと MolangVariableMap に "variable.<名前>" で入る（パーティクル側は v.<名前>）。
//  * ID は tools/nightrunner/nr_registry.py（scripts/data/fx.js）にあるものだけ。
//  * ゾンビの一発アニメは zombieAnim()（controller "nr.z.os"・stopExpression・nextState を必ず渡す。DESIGN §13）。
//  * before イベントの中から呼ばない（全部 〔RO✗〕）。
// ===========================================================================
import { system, MolangVariableMap } from "@minecraft/server";
import * as FX_D from "../data/fx.js";
import { take, PRIO } from "./budget.js";
import { finiteVec, valid, warnOnce, clamp, dist } from "./util.js";

/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Player} Player */

export { PRIO };

/** @type {any} */
const FXD = FX_D;
/** @param {any} list @param {string} prefix @returns {Set<string>} */
function idSet(list, prefix) {
  const s = new Set();
  const arr = Array.isArray(list) ? list : list && typeof list === "object" ? Object.keys(list) : [];
  for (const n of arr) {
    const name = String(n);
    s.add(name);
    s.add(name.startsWith(prefix) ? name.slice(prefix.length) : prefix + name);
  }
  return s;
}
const PARTICLE_IDS = idSet(FXD.PARTICLES, "nr:");
const SOUND_IDS = idSet(FXD.SOUNDS, "");
const ZOMBIE_ANIMS = idSet(FXD.ZOMBIE_ONESHOTS, "animation.nr.z.");
const PLAYER_ANIMS = idSet(FXD.PLAYER_ANIMS, "animation.nr.p.");

/** 一発アニメの既定（reference/rendering.md §5）。 */
export const ONESHOT = Object.freeze({ controller: "nr.z.os", blendOutTime: 0.15, stopExpression: "q.any_animation_finished", nextState: "none" });

/**
 * {名前: 数} → MolangVariableMap（"variable.<名前>"。有限でない値は入れない）。
 * @param {Record<string, number> | undefined} vars @returns {MolangVariableMap | undefined}
 */
export function molang(vars) {
  if (!vars) return undefined;
  const mv = new MolangVariableMap();
  for (const [k, v] of Object.entries(vars)) {
    if (typeof v === "number" && Number.isFinite(v) && /^[a-z_][a-z0-9_]*$/i.test(k)) mv.setFloat(`variable.${k}`, v);
  }
  return mv;
}

/**
 * パーティクルを 1 つ出す（予算・ID の検査付き）。出せたら true。
 * @param {Dimension} dim @param {string} id "nr:blood_spray" か "blood_spray"
 * @param {Vector3} loc @param {Record<string, number>} [vars] @param {number} [prio] PRIO @param {number} [cost]
 */
export function particle(dim, id, loc, vars, prio = PRIO.NORMAL, cost = 1) {
  if (!dim || !finiteVec(loc)) return false;
  const full = id.includes(":") ? id : `nr:${id}`;
  if (full.startsWith("nr:") && PARTICLE_IDS.size && !PARTICLE_IDS.has(full)) {
    warnOnce(`particle:${full}`, "登録簿に無いパーティクル", full);
    return false;
  }
  if (take(cost, prio) < cost) return false;
  try {
    dim.spawnParticle(full, loc, molang(vars));
    return true;
  } catch (err) {
    warnOnce(`spawnParticle:${full}`, "spawnParticle 失敗", full, err);
    return false;
  }
}

/**
 * 同じパーティクルを複数の点に（予算が足りる分だけ）。出せた数を返す。
 * @param {Dimension} dim @param {string} id @param {Vector3[]} points @param {Record<string, number>} [vars] @param {number} [prio]
 */
export function particles(dim, id, points, vars, prio = PRIO.NORMAL) {
  let n = 0;
  for (const p of points) if (particle(dim, id, p, vars, prio)) n++; else break;
  return n;
}

// ---- 音（1 tick の上限と、同じ音・同じ場所の重複をまとめる） ----------------------------
const SOUND_CAP = 40;
let soundTick = -1;
/** @type {{id: string, loc: Vector3}[]} */
let soundsThisTick = [];

/**
 * 位置で音を鳴らす（その場の全員に聞こえる）。鳴らしたら true。
 * @param {Dimension} dim @param {string} id @param {Vector3} loc @param {{volume?: number, pitch?: number}} [opts]
 */
export function sound(dim, id, loc, opts) {
  if (!dim || !finiteVec(loc) || !id) return false;
  const t = system.currentTick;
  if (t !== soundTick) { soundTick = t; soundsThisTick = []; }
  if (soundsThisTick.length >= SOUND_CAP) return false;
  for (const s of soundsThisTick) if (s.id === id && dist(s.loc, loc) < 1.5) return false;
  if (id.startsWith("nr.") && SOUND_IDS.size && !SOUND_IDS.has(id) && !/^nr\.(z|ab)\./.test(id)) warnOnce(`sound:${id}`, "登録簿に無い効果音", id);
  soundsThisTick.push({ id, loc });
  /** @type {{volume?: number, pitch?: number}} */
  const o = {};
  if (opts?.volume !== undefined) o.volume = clamp(Number(opts.volume) || 0, 0, 16);
  if (opts?.pitch !== undefined) o.pitch = clamp(Number(opts.pitch) || 1, 0.01, 4);
  try { dim.playSound(id, loc, o); return true; } catch (err) { warnOnce(`playSound:${id}`, "playSound 失敗", id, err); return false; }
}

/** その人にだけ聞こえる音。 @param {Player} p @param {string} id @param {{volume?: number, pitch?: number, location?: Vector3}} [opts] */
export function playerSound(p, id, opts) {
  if (!valid(p) || !id) return false;
  try { p.playSound(id, opts ?? {}); return true; } catch (err) { warnOnce(`playerSound:${id}`, "player.playSound 失敗", id, err); return false; }
}

// ---- アニメ ---------------------------------------------------------------------------------
/**
 * ゾンビの一発アニメ（animation.nr.z.<name>）。controller・stopExpression・nextState を必ず付ける。
 * @param {Entity} z @param {string} name 例 "react_head"、"knockdown"、"ab_scream"
 * @param {{controller?: string, blendOutTime?: number, stopExpression?: string, nextState?: string, players?: Player[]}} [opts]
 */
export function zombieAnim(z, name, opts) {
  if (!valid(z)) return false;
  const full = name.startsWith("animation.") ? name : `animation.nr.z.${name}`;
  const short = full.slice("animation.nr.z.".length);
  if (ZOMBIE_ANIMS.size && !ZOMBIE_ANIMS.has(full) && !/^(ab|atk|walk|run)_/.test(short)) {
    warnOnce(`zanim:${full}`, "登録簿に無いゾンビのアニメ", full);
    return false;
  }
  try { z.playAnimation(full, { ...ONESHOT, ...(opts ?? {}) }); return true; } catch (err) { warnOnce(`zanim!:${full}`, "playAnimation 失敗", full, err); return false; }
}

/**
 * プレイヤーのモーション（animation.nr.p.<name>）。層の既定は "nr.p.act"。
 * @param {Player} p @param {string} name
 * @param {{controller?: string, blendOutTime?: number, stopExpression?: string, nextState?: string, players?: Player[]}} [opts]
 */
export function playerAnim(p, name, opts) {
  if (!valid(p)) return false;
  const full = name.startsWith("animation.") ? name : `animation.nr.p.${name}`;
  if (PLAYER_ANIMS.size && !PLAYER_ANIMS.has(full)) { warnOnce(`panim:${full}`, "登録簿に無いプレイヤーのモーション", full); return false; }
  const o = { controller: "nr.p.act", blendOutTime: 0.1, stopExpression: "q.any_animation_finished", nextState: "none", ...(opts ?? {}) };
  try { p.playAnimation(full, o); return true; } catch (err) { warnOnce(`panim!:${full}`, "playAnimation 失敗", full, err); return false; }
}

// ---- カメラ ---------------------------------------------------------------------------------
/**
 * 画面を色で覆う（返り血の赤など）。時間は秒（0..10 に丸める）。
 * @param {Player} p @param {{red: number, green: number, blue: number}} color
 * @param {number} fadeIn @param {number} hold @param {number} fadeOut
 */
export function fade(p, color, fadeIn, hold, fadeOut) {
  if (!valid(p)) return false;
  const t = (v) => clamp(Number(v) || 0, 0, 10);
  const c = (v) => clamp(Number(v) || 0, 0, 1);
  try {
    p.camera.fade({ fadeColor: { red: c(color.red), green: c(color.green), blue: c(color.blue) }, fadeTime: { fadeInTime: t(fadeIn), holdTime: t(hold), fadeOutTime: t(fadeOut) } });
    return true;
  } catch (err) { warnOnce("fade", "camera.fade 失敗", err); return false; }
}

/**
 * カメラを揺らす（/camerashake。Camera API の揺れはベータなのでコマンドで）。
 * @param {Player} p @param {number} intensity 0..4 @param {number} seconds @param {"positional" | "rotational"} [type]
 */
export function shake(p, intensity, seconds, type = "positional") {
  if (!valid(p)) return false;
  const i = clamp(Number(intensity) || 0, 0, 4), s = clamp(Number(seconds) || 0, 0, 10);
  if (i <= 0 || s <= 0) return false;
  try { p.runCommand(`camerashake add @s ${i.toFixed(2)} ${s.toFixed(2)} ${type}`); return true; } catch (err) { warnOnce("shake", "camerashake 失敗", err); return false; }
}
