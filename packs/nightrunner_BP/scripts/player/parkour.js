// ===========================================================================
//  NIGHT RUNNER: 感染都市 — パルクール（DESIGN §7、数値は data/settings.js の PARKOUR_TUNING）
//
//  技: 壁登り（壁に向かってジャンプ長押し）・縁つかまり → よじ登り・乗り越え（ダッシュ中のジャンプ。vault / vault_high）・
//  壁走り（左右）→ 壁蹴り・スライディング（ダッシュ中のスニーク）・受け身（着地の直前のスニーク）・重い着地・
//  ドロップキック（空中でスニーク＋攻撃）・グラップリングフック（アイテム）・パラグライダー（アイテム）・
//  掴まれた状態（バス "grabbed" → 連打で振りほどく → バス "shove"）。
//
//  * プレイヤーは applyKnockback（速度をその値にする）と効果だけで動かす（applyImpulse は使わない）。
//    位置を保つ・登る速さは「目標の高さ − 今の高さ」を毎 tick 速度にする（実機と偽物で重力の順が違っても
//    同じ所に落ち着く）。
//  * 入力: ジャンプ・スニークの押下は playerButtonInput、押し続けは inputInfo.getButtonState、
//    前後は getMovementVector().y、ダッシュは isSprinting、攻撃は entityHitEntity（script_api.md §3.7）。
//  * モーションは core/fx の playerAnim（層 "nr.p.move"。ループは stopExpression にクライアントで判定できる
//    終わりの条件、止める時は同じ層に "none"。rendering.md §9 / P1〜P4）。
//  * 落下: 安全な高さ（fall.safe_height + スキル cat_landing）を超えた分だけバニラの落下ダメージ。受け身は
//    roll.fall_dmg_mult（スキル safe_roll で 0.15）倍、ゴミ袋（タグ landing）は 0。バニラが多く引いた分は
//    entityHurt の後で体力を戻す。バニラの分だけで死ぬ落下は空中で耐性（resistance V）を付けて守る。
//  * 壁走り・壁蹴り・ドロップキックはスキル（wall_run / wall_jump / dropkick）で覚える（SKILL_GATES）。
// ===========================================================================
import { world, system, InputButton, ButtonState, EntityDamageCause } from "@minecraft/server";
import { on, emit } from "../core/bus.js";
import { valid, now, clamp, dist, distXZ, len, sub, scale, lerpV, flat, dot, yawForward, yawRight, isZombie, isPlayer } from "../core/util.js";
import { particle, sound, playerSound, playerAnim, shake, PRIO } from "../core/fx.js";
import { get as setting } from "../core/settings.js";
import { zombieSpec } from "../core/hp.js";
import { applyHit, stagger } from "../gore/gore.js";
import { isCorpse } from "../gore/death.js";
import * as ITEMS_D from "../data/items.js";
import {
  PEV, PT, nv, playerMap, onPlayerTick, isActive, healthOf, setHealth, push, solidAt, blockAt, blockHeight, columnTop,
  clearColumn, parkourTags, groundBelow, angleDiff, guard,
} from "./common.js";
import { consumeStamina, canAfford } from "./stamina.js";
import { hasSkill, skillNum, skillEff } from "./skills.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */

// ---------------------------------------------------------------------------
//  数値
// ---------------------------------------------------------------------------
const CL = PT.climb ?? {}, VA = PT.vault ?? {}, WR = PT.wallrun ?? {}, SL = PT.slide ?? {}, RO = PT.roll ?? {};
const FA = PT.fall ?? {}, DK = PT.dropkick ?? {}, GR = PT.grapple ?? {}, GL = PT.glider ?? {}, SC = PT.stamina ?? {}, JB = PT.jump_boost ?? {};

/** 技のスタミナ（PARKOUR_TUNING.stamina）。 */
export const COST = Object.freeze({
  climb: nv(SC.climb_per_tick, 0.5), vault: nv(SC.vault, 4), wallrun: nv(SC.wallrun, 10), walljump: nv(SC.walljump, 6),
  slide: nv(SC.slide, 6), roll: nv(SC.roll, 0), dropkick: nv(SC.dropkick, 20), grapple: nv(SC.grapple, 10),
});
/** スキルで覚える技（技 → スキルの鍵）。 */
export const SKILL_GATES = Object.freeze({ wallrun: "wall_run", walljump: "wall_jump", dropkick: "dropkick" });
/** 掴まれた時: 振りほどくのに要る連打の数・最長・連打が減っていく間隔。 */
export const GRAB = Object.freeze({ presses: 8, maxTicks: 240, decayEvery: 16 });

const MOVE = "nr.p.move";      // 全身のパルクールの層
const ACT = "nr.p.act";        // 腕の一発もの（フックを撃つ・翼を開く）
const LOOPS = new Set(["climb", "hang", "wallrun", "grapple", "glide", "grabbed"]);
const SOFT_LAND = 3;           // これ以上の落下で着地の音

/** @type {any} */
const ID = ITEMS_D;
/** use.type（grapple / glide）→ アイテムの ID と use。 @type {Record<string, any>} */
const USE_BY_ID = Object.fromEntries((Array.isArray(ID.ITEMS) ? ID.ITEMS : []).filter((/** @type {any} */ it) => it?.use?.type).map((/** @type {any} */ it) => [it.id, it.use]));

// ---------------------------------------------------------------------------
//  プレイヤーごとの状態
// ---------------------------------------------------------------------------
/**
 * @typedef {{mode: string, t0: number, m: any, ground: boolean, groundT: number, groundY: number, airT: number, peakY: number,
 *   vanFall: number, lastY: number, lastLoc: Vector3 | undefined, spd: number, dir: Vector3, sprintT: number, jumpT: number,
 *   sneakT: number, jumpHeldSince: number, cd: Record<string, number>, chain: number, wrUsed: boolean, stunUntil: number,
 *   rollUntil: number, landing: any, guard: boolean, boostT: number, last: string, lastT: number, jumpN: number, sneakN: number,
 *   mJ: number, mS: number, spdHist: number[], runSpd: number}} PState
 */
/** @type {Map<string, PState>} */
const states = playerMap();
/** @param {Player} p @returns {PState} */
function pst(p) {
  let s = states.get(p.id);
  if (!s) {
    const y = p.location.y;
    s = { mode: "", t0: 0, m: {}, ground: true, groundT: now(), groundY: y, airT: -9999, peakY: y, vanFall: 0, lastY: y, lastLoc: undefined,
      spd: 0, dir: { x: 0, y: 0, z: 1 }, sprintT: -9999, jumpT: -9999, sneakT: -9999, jumpHeldSince: -1, cd: {}, chain: 0, wrUsed: false,
      stunUntil: -1, rollUntil: -1, landing: undefined, guard: false, boostT: -9999, last: "", lastT: -9999, jumpN: 0, sneakN: 0,
      mJ: 0, mS: 0, spdHist: [], runSpd: 0 };
    states.set(p.id, s);
  }
  return s;
}

/**
 * 1 tick の入力と姿勢。
 * @typedef {{t: number, dim: Dimension, loc: Vector3, vel: Vector3, onGround: boolean, sprint: boolean, sneak: boolean,
 *   jumpHeld: boolean, yaw: number, fwd: Vector3, right: Vector3, mv: {x: number, y: number}}} Ctx
 */
/** @param {Player} p @param {number} t @returns {Ctx} */
function ctxOf(p, t) {
  const yaw = p.getRotation().y;
  let mv = { x: 0, y: 0 };
  try { mv = p.inputInfo.getMovementVector(); } catch { /* 無い */ }
  let jumpHeld = false;
  try { jumpHeld = p.inputInfo.getButtonState(InputButton.Jump) === ButtonState.Pressed; } catch { jumpHeld = p.isJumping; }
  return {
    t, dim: p.dimension, loc: p.location, vel: p.getVelocity(), onGround: p.isOnGround, sprint: p.isSprinting, sneak: p.isSneaking,
    jumpHeld, yaw, fwd: yawForward(yaw), right: yawRight(yaw), mv,
  };
}

/** 今のパルクールの状態（HUD・テスト・他のモジュール用の写し）。 @param {Player} p */
export function parkourState(p) {
  const s = valid(p) ? states.get(p.id) : undefined;
  if (!s) return { mode: "", since: 0, last: "", lastT: -9999, ground: true, chain: 0 };
  return { mode: s.mode, since: s.t0, last: s.last, lastT: s.lastT, ground: s.ground, chain: s.chain };
}
/** 掴まれているか。 @param {Player} p */
export function isGrabbed(p) { return valid(p) && states.get(p.id)?.mode === "grabbed"; }
/** 掴まれている時の連打 {presses, need, zombie}。 @param {Player} p */
export function grabInfo(p) {
  const s = valid(p) ? states.get(p.id) : undefined;
  if (s?.mode !== "grabbed") return undefined;
  return { presses: s.m.presses, need: s.m.need, zombie: s.m.zombie };
}

// ---------------------------------------------------------------------------
//  アニメ・演出の包み
// ---------------------------------------------------------------------------
/** 一発もの（層 nr.p.move）。 @param {Player} p @param {string} name @param {Record<string, any>} [o] */
function anim(p, name, o) {
  return playerAnim(p, name, { controller: MOVE, blendOutTime: 0.1, stopExpression: "q.any_animation_finished", nextState: "none", ...(o ?? {}) });
}
/** ループ（終わりはクライアントの式 + スクリプトの "none"）。 @param {Player} p @param {string} name @param {string} stop */
function loopAnim(p, name, stop) {
  return playerAnim(p, name, { controller: MOVE, blendOutTime: 0.15, stopExpression: stop, nextState: "none" });
}
/** 層 nr.p.move を空にする。 @param {Player} p */
function stopMove(p) {
  return playerAnim(p, "none", { controller: MOVE, blendOutTime: 0.15, stopExpression: "q.any_animation_finished", nextState: "none" });
}
/** 技が決まった（経験値・HUD）。 @param {Player} p @param {PState} st @param {string} move @param {Record<string, any>} [extra] */
function done(p, st, move, extra) {
  st.last = move; st.lastT = now();
  emit(PEV.PARKOUR, { player: p, move, ...(extra ?? {}) });
}
/** 足元の土煙。 @param {Ctx} c @param {number} n @param {string} [id] */
function dust(c, n, id = "dust_land") {
  for (let i = 0; i < n; i++) {
    const a = (i / Math.max(1, n)) * Math.PI * 2;
    particle(c.dim, id, { x: c.loc.x + Math.cos(a) * 0.35, y: c.loc.y + 0.05, z: c.loc.z + Math.sin(a) * 0.35 }, undefined, PRIO.LOW);
  }
}

// ---------------------------------------------------------------------------
//  モードの出入り
// ---------------------------------------------------------------------------
/** @param {Player} p @param {PState} st @param {string} mode @param {any} m */
function enterMode(p, st, mode, m) {
  if (st.mode) endMode(p, st, "replace", true);
  st.mode = mode; st.t0 = now(); st.m = m ?? {};
  st.mJ = st.jumpN; st.mS = st.sneakN;
}
/** モードに入ってから新しくジャンプを押したか（押下の数で数える。同じ tick の前後に左右されない）。 @param {PState} st */
function jumped(st) { return st.jumpN > st.mJ; }
/** モードに入ってから新しくスニークを押したか。 @param {PState} st */
function sneaked(st) { return st.sneakN > st.mS; }
/**
 * @param {Player} p @param {PState} st @param {string} why @param {boolean} [keepAnim] 次のモードが同じ層に流すなら true
 */
function endMode(p, st, why, keepAnim = false) {
  const mode = st.mode;
  if (!mode) return;
  st.mode = ""; st.m = {};
  const t = now();
  if (!keepAnim && LOOPS.has(mode) && valid(p)) stopMove(p);
  if (mode === "wallrun") st.cd.wallrun = Math.max(st.cd.wallrun ?? 0, t + nv(WR.cooldown_ticks, 10));
  else if (mode === "slide") st.cd.slide = t + nv(SL.cooldown_ticks, 10);
  else if (mode === "climb") st.cd.climb = t + 6;
  else if (mode === "hang" || mode === "mantle") st.cd.ledge = t + 8;
  else if (mode === "grabbed" && valid(p)) { try { p.removeEffect("slowness"); } catch { /* 無い */ } }
  void why;
}

// ---------------------------------------------------------------------------
//  地形の判定
// ---------------------------------------------------------------------------
/** パルクールの補助（設定）。 */
function assist() { return setting("parkour_assist") !== false; }

/** 前の壁（胸と頭の高さに当たり）。 @param {Ctx} c @param {number} reach */
function wallAhead(c, reach) {
  for (const d of [0.35, reach]) {
    const x = c.loc.x + c.fwd.x * d, z = c.loc.z + c.fwd.z * d;
    if (solidAt(c.dim, { x, y: c.loc.y + 0.9, z }) && solidAt(c.dim, { x, y: c.loc.y + 1.5, z })) return { d, x, z };
  }
  return undefined;
}
/** 前の胸の高さに壁があるか（登っている間の判定）。 @param {Ctx} c @param {number} reach */
function chestWall(c, reach) {
  for (const d of [0.35, reach]) if (solidAt(c.dim, { x: c.loc.x + c.fwd.x * d, y: c.loc.y + 0.9, z: c.loc.z + c.fwd.z * d })) return true;
  return false;
}

/**
 * 手の届く縁（前の壁の天辺。その上に立てる空きがあり、自分の頭の上も空いている）。
 * @param {Ctx} c @returns {{top: number, x: number, z: number, dir: Vector3} | undefined}
 */
function findLedge(c) {
  const reach = nv(CL.ledge_reach, 1.2) * (assist() ? 1.25 : 1);
  const handY = c.loc.y + 1.8;
  for (const d of [0.45, Math.max(0.6, nv(CL.wall_check_dist, 0.7) + 0.1)]) {
    const x = c.loc.x + c.fwd.x * d, z = c.loc.z + c.fwd.z * d;
    const lo = Math.floor(c.loc.y + 0.5), hi = Math.floor(handY + reach);
    for (let y = lo; y <= hi; y++) {
      const h = blockHeight(blockAt(c.dim, x, y, z));
      if (h <= 0) continue;
      if (h >= 1 && blockHeight(blockAt(c.dim, x, y + 1, z)) > 0) continue;
      const top = y + h;
      if (top - handY > reach || top - c.loc.y < 0.9) continue;
      if (!clearColumn(c.dim, x, z, top + 0.05, top + 1.75)) continue;
      if (!clearColumn(c.dim, c.loc.x, c.loc.z, c.loc.y + 1.85, Math.max(c.loc.y + 1.85, top + 1.8))) continue;
      return { top, x, z, dir: flat({ x: x - c.loc.x, y: 0, z: z - c.loc.z }, c.fwd) };
    }
  }
  return undefined;
}

/**
 * 前の障害物の高さ（地面からの段差。乗り越えの判定）。
 * @param {Ctx} c @param {number} groundY @returns {{h: number, top: number} | undefined}
 */
function obstacleAhead(c, groundY) {
  const lo = Math.floor(groundY + 0.01);
  for (const d of [0.55, 0.95, 1.35]) {
    const x = c.loc.x + c.fwd.x * d, z = c.loc.z + c.fwd.z * d;
    const top = columnTop(c.dim, x, z, lo, lo + 2);
    if (top === undefined) continue;
    if (!clearColumn(c.dim, x, z, top + 0.05, top + 1.75)) return undefined;
    return { h: top - groundY, top };
  }
  return undefined;
}

/**
 * 横の壁（右 = +1、左 = -1）。n は壁からプレイヤーへの向き。
 * @param {Ctx} c @param {number} reach @returns {{side: number, n: Vector3} | undefined}
 */
function sideWall(c, reach) {
  for (const s of [1, -1]) {
    const R = scale(c.right, s);
    for (const d of [0.45, reach]) {
      const x = c.loc.x + R.x * d, z = c.loc.z + R.z * d;
      if (solidAt(c.dim, { x, y: c.loc.y + 0.6, z }) && solidAt(c.dim, { x, y: c.loc.y + 1.3, z })) return { side: s, n: scale(R, -1) };
    }
  }
  return undefined;
}
/** その側にまだ壁があるか。 @param {Ctx} c @param {Vector3} n @param {number} reach */
function wallStill(c, n, reach) {
  for (const d of [0.45, reach]) {
    const x = c.loc.x - n.x * d, z = c.loc.z - n.z * d;
    if (solidAt(c.dim, { x, y: c.loc.y + 0.9, z })) return true;
  }
  return false;
}

/** 下に上昇気流（タグ updraft）があるか。 @param {Ctx} c */
function updraftBelow(c) {
  const y0 = Math.floor(c.loc.y);
  for (let y = y0; y >= y0 - 12; y--) {
    const b = blockAt(c.dim, c.loc.x, y, c.loc.z);
    if (!b) return false;
    if (parkourTags(b.typeId).includes("updraft")) return true;
    if (blockHeight(b) > 0) return false;
  }
  return false;
}

// ---------------------------------------------------------------------------
//  落下・着地
// ---------------------------------------------------------------------------
/**
 * 着地で受けてよいダメージ（PARKOUR_TUNING.fall / roll とスキル）。
 * @param {Player} p @param {number} fall 落ちた高さ @param {boolean} rolled 受け身 @param {boolean} pile ゴミ袋など（タグ landing）
 */
export function fallDamage(p, fall, rolled, pile) {
  if (pile) return 0;
  const safeH = nv(FA.safe_height, 6) + skillNum(p, "safe_fall_add", 0);
  let d = Math.max(0, fall - safeH);
  if (rolled) d *= skillNum(p, "roll_fall_mult", nv(RO.fall_dmg_mult, 0.4));
  return Math.round(d);
}

/** その着地の結果（同じ着地は 1 回だけ決める）。 @param {Player} p @param {PState} st @param {number} t */
function resolveLanding(p, st, t) {
  if (st.landing && st.landing.air === st.airT) return st.landing;
  const loc = p.location;
  const fall = Math.max(0, st.peakY - loc.y);
  const under = blockAt(p.dimension, loc.x, loc.y - 0.2, loc.z);
  const pile = !!under && parkourTags(under.typeId).includes("landing");
  const win = skillNum(p, "roll_window_ticks", nv(RO.window_ticks, 6));
  const rolled = !pile && fall >= nv(RO.min_fall, 4) && st.sneakT >= st.airT && t - st.sneakT <= win;
  st.landing = { air: st.airT, t, fall, rolled, pile, allowed: fallDamage(p, fall, rolled, pile), guard: st.guard, refunded: false, fx: false };
  return st.landing;
}

/** 空中で: バニラの落下ダメージだけで死ぬなら耐性で守る（着地で決めた分を自分で引く）。 @param {Player} p @param {PState} st @param {Ctx} c */
function fallGuard(p, st, c) {
  const g = groundBelow(c.dim, c.loc, 64);
  if (!g) return;
  const vanilla = st.vanFall + (c.loc.y - g.y) - 3;
  const hp = healthOf(p).cur;
  if (vanilla < hp) return;
  const ours = fallDamage(p, Math.max(0, st.peakY - g.y), false, parkourTags(g.typeId).includes("landing"));
  if (ours >= hp) return;
  try { p.addEffect("resistance", 6, { amplifier: 4, showParticles: false }); st.guard = true; } catch { /* 効かない */ }
}

/** 着地した（毎 tick の判定から）。 @param {Player} p @param {PState} st @param {Ctx} c */
function landed(p, st, c) {
  const L = resolveLanding(p, st, c.t);
  if (L.fx) return;
  L.fx = true;
  if (L.guard) {
    st.guard = false;
    try { p.removeEffect("resistance"); } catch { /* 無い */ }
    if (L.allowed > 0) setHealth(p, healthOf(p).cur - L.allowed);
  }
  if (st.mode === "glide" || st.mode === "grapple" || st.mode === "grabbed") return;
  const minFall = nv(RO.min_fall, 4);
  if (L.rolled) {
    const d = st.spd > 0.05 ? st.dir : c.fwd;
    const f = nv(RO.forward_impulse, 0.4);
    push(p, d.x * f, d.z * f, 0);
    anim(p, "roll", { blendOutTime: 0 });
    sound(c.dim, "nr.pk.roll", c.loc);
    dust(c, 3);
    st.rollUntil = c.t + nv(RO.roll_ticks, 10);
    done(p, st, "roll", { fall: L.fall });
  } else if (L.pile) {
    if (L.fall >= SOFT_LAND) { sound(c.dim, "nr.pk.land_soft", c.loc); dust(c, 2); }
    if (L.fall >= minFall) done(p, st, "landing_pile", { fall: L.fall });
  } else if (L.fall >= minFall) {
    anim(p, "hard_land");
    sound(c.dim, "nr.pk.land_hard", c.loc, { volume: clamp(0.6 + L.fall * 0.05, 0.6, 1.4) });
    dust(c, 5);
    shake(p, clamp(0.15 + L.fall * 0.03, 0.15, 0.8), 0.25);
    const stun = clamp(Math.round(6 + L.fall), 8, 20);
    try { p.addEffect("slowness", stun, { amplifier: 3, showParticles: false }); } catch { /* 効かない */ }
    st.stunUntil = c.t + stun;
    emit("noise", { pos: c.loc, radius: clamp(L.fall * 1.5, 6, 16), dim: c.dim, source: "landing", player: p });
    done(p, st, "hard_land", { fall: L.fall, damage: L.allowed });
  } else if (L.fall >= SOFT_LAND) {
    sound(c.dim, "nr.pk.land_soft", c.loc, { volume: 0.6 });
    dust(c, 2);
  }
}

// バニラの落下ダメージを決めた分まで戻す
world.afterEvents.entityHurt.subscribe((ev) => {
  const e = ev.hurtEntity;
  if (!isPlayer(e) || ev.damageSource.cause !== EntityDamageCause.fall) return;
  const p = /** @type {Player} */ (e);
  if (!valid(p) || !isActive(p)) return;
  guard("fall", () => {
    const st = pst(p);
    const t = now();
    let L = st.landing;
    if (!st.ground || !L || t - L.t > 3) L = resolveLanding(p, st, t);
    if (L.refunded) return;
    L.refunded = true;
    const refund = ev.damage - L.allowed;
    if (refund > 0) setHealth(p, healthOf(p).cur + refund);
  });
}, { entityTypes: ["minecraft:player"] });

// ---------------------------------------------------------------------------
//  毎 tick
// ---------------------------------------------------------------------------
onPlayerTick("parkour", 1, (p, t) => {
  const st = pst(p);
  if (!isActive(p)) {
    if (st.mode) endMode(p, st, "inactive");
    st.ground = true; st.lastLoc = undefined; st.guard = false;
    return;
  }
  const c = ctxOf(p, t);
  // 速さ = 実際に動いた距離（偽物も実機も同じ物差し。テレポートは数えない）
  if (st.lastLoc) {
    const d = distXZ(c.loc, st.lastLoc);
    if (d < 3) {
      st.spd = d;
      if (d > 0.05) st.dir = flat({ x: c.loc.x - st.lastLoc.x, y: 0, z: c.loc.z - st.lastLoc.z }, st.dir);
    }
    st.spdHist.push(st.spd);
    if (st.spdHist.length > 4) st.spdHist.shift();
    st.runSpd = Math.max(...st.spdHist);
  }
  st.lastLoc = c.loc;
  if (c.sprint) st.sprintT = t;
  if (c.jumpHeld) { if (st.jumpHeldSince < 0) st.jumpHeldSince = t; } else st.jumpHeldSince = -1;

  let vanillaMove = false;
  try { vanillaMove = p.isInWater || p.isClimbing || p.isFlying || p.isGliding || p.isSwimming || !!p.getComponent("minecraft:riding")?.entityRidingOn; } catch { vanillaMove = false; }
  if (vanillaMove) {
    if (st.mode && st.mode !== "grabbed") endMode(p, st, "vanilla");
    st.ground = true; st.groundY = c.loc.y; st.peakY = c.loc.y; st.vanFall = 0; st.lastY = c.loc.y;
    return;
  }
  trackAir(p, st, c);
  jumpBoost(p, st, c);
  if (st.mode) {
    const fn = UPDATE[st.mode];
    if (fn) fn(p, st, c); else endMode(p, st, "unknown");
    if (st.mode) return;
  }
  detect(p, st, c);
});

/** 空中の記録（最高点・バニラの落下距離）と着地。 @param {Player} p @param {PState} st @param {Ctx} c */
function trackAir(p, st, c) {
  if (c.onGround) {
    if (!st.ground) { st.ground = true; landed(p, st, c); }
    st.groundT = c.t; st.groundY = c.loc.y; st.chain = 0; st.wrUsed = false; st.vanFall = 0; st.peakY = c.loc.y; st.lastY = c.loc.y;
    st.guard = false;
    return;
  }
  if (st.ground) { st.ground = false; st.airT = c.t; st.peakY = Math.max(c.loc.y, st.groundY); st.vanFall = 0; st.lastY = c.loc.y; }
  if (c.loc.y > st.peakY) st.peakY = c.loc.y;
  if (c.loc.y < st.lastY) st.vanFall += st.lastY - c.loc.y;
  st.lastY = c.loc.y;
  if (c.vel.y < -0.4 && c.t % 2 === 0 && !st.guard) fallGuard(p, st, c);
}

/** ダッシュ中のジャンプ力（PARKOUR_TUNING.jump_boost）。 @param {Player} p @param {PState} st @param {Ctx} c */
function jumpBoost(p, st, c) {
  const amp = Math.floor(nv(JB.amp, -1));
  if (amp < 0 || !c.sprint || c.t - st.boostT < 10) return;
  st.boostT = c.t;
  try { p.addEffect("jump_boost", 14, { amplifier: Math.min(amp, 4), showParticles: false }); } catch { /* 効かない */ }
}

/** 新しい技を始めるか。 @param {Player} p @param {PState} st @param {Ctx} c */
function detect(p, st, c) {
  if (c.t < st.stunUntil || c.t < st.rollUntil) return;
  if (!c.onGround && c.vel.y < 0.2 && c.mv.y > -0.2 && c.t >= (st.cd.ledge ?? 0)) {
    const L = findLedge(c);
    if (L) {
      if (c.jumpHeld || c.mv.y > 0.3) enterMantle(p, st, c, L.top, L.dir, "grab");
      else enterHang(p, st, c, L.top, L.dir);
      return;
    }
  }
  if (!c.onGround && tryWallrun(p, st, c)) return;
  if (tryVault(p, st, c)) return;
  if (tryClimb(p, st, c)) return;
  if (c.onGround) trySlide(p, st, c);
}

// ---------------------------------------------------------------------------
//  壁登り・縁・よじ登り
// ---------------------------------------------------------------------------
/** @param {Player} p @param {PState} st @param {Ctx} c */
function tryClimb(p, st, c) {
  if (!c.jumpHeld || st.jumpHeldSince < 0 || c.t - st.jumpHeldSince < nv(CL.hold_jump_ticks, 4)) return false;
  if (c.t < (st.cd.climb ?? 0) || c.mv.y < -0.2) return false;
  if (!wallAhead(c, nv(CL.wall_check_dist, 0.7))) return false;
  if (!canAfford(p, nv(CL.stamina_needed, 5))) return false;
  enterMode(p, st, "climb", { y0: c.loc.y, ty: c.loc.y, lastY: c.loc.y, acc: 0 });
  loopAnim(p, "climb_loop", "q.is_on_ground && q.state_time > 0.5");
  sound(c.dim, "nr.pk.grab", c.loc);
  return true;
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateClimb(p, st, c) {
  const m = st.m;
  if (!c.jumpHeld) { endMode(p, st, "release"); return; }
  const L = findLedge(c);
  if (L) { enterMantle(p, st, c, L.top, L.dir, "climb"); return; }
  const reach = nv(CL.wall_check_dist, 0.7);
  if (!chestWall(c, reach)) { endMode(p, st, "nowall"); return; }
  const maxH = nv(CL.max_height, 0);
  if (maxH > 0 && c.loc.y - m.y0 >= maxH) { endMode(p, st, "height"); return; }
  if (!consumeStamina(p, COST.climb * skillNum(p, "climb_stamina_mult", 1), { reason: "climb" })) { endMode(p, st, "stamina"); return; }
  const speed = nv(CL.speed, 0.18) * skillNum(p, "climb_speed_mult", 1);
  m.ty = Math.min(m.ty + speed, c.loc.y + speed + 0.3);
  const vy = clamp(m.ty - c.loc.y, -0.1, speed + 0.25);
  push(p, c.fwd.x * 0.03, c.fwd.z * 0.03, vy);
  m.acc += Math.max(0, c.loc.y - m.lastY);
  m.lastY = c.loc.y;
  while (m.acc >= 1) { m.acc -= 1; done(p, st, "climb_block"); }
  if ((c.t - st.t0) % 8 === 0) sound(c.dim, "nr.pk.climb", c.loc, { volume: 0.7 });
  st.peakY = c.loc.y;
}

/** @param {Player} p @param {PState} st @param {Ctx} c @param {number} top @param {Vector3} dir */
function enterHang(p, st, c, top, dir) {
  enterMode(p, st, "hang", { top, hy: top - 1.75, dir });
  loopAnim(p, "ledge_hang", "q.is_on_ground");
  sound(c.dim, "nr.pk.grab", c.loc);
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateHang(p, st, c) {
  const m = st.m;
  const k = c.t - st.t0;
  if (jumped(st) || (c.jumpHeld && k > 3)) { enterMantle(p, st, c, m.top, m.dir, "hang"); return; }
  if (sneaked(st) || k > nv(CL.hang_max_ticks, 200) || c.onGround) {
    endMode(p, st, "drop");
    if (!c.onGround) push(p, -m.dir.x * 0.12, -m.dir.z * 0.12, 0);
    return;
  }
  if (!wallStill(c, scale(m.dir, -1), 0.8)) { endMode(p, st, "lost"); return; }
  push(p, m.dir.x * 0.02, m.dir.z * 0.02, clamp(m.hy - c.loc.y, -0.3, 0.3));
  if (k % 10 === 0) { try { p.addEffect("slow_falling", 12, { amplifier: 0, showParticles: false }); } catch { /* 効かない */ } }
  st.peakY = c.loc.y;
}

/** @param {Player} p @param {PState} st @param {Ctx} c @param {number} top @param {Vector3} dir @param {string} from */
function enterMantle(p, st, c, top, dir, from) {
  enterMode(p, st, "mantle", { top, y0: c.loc.y, dir, from });
  anim(p, "mantle");
  sound(c.dim, from === "climb" ? "nr.pk.climb" : "nr.pk.grab", c.loc);
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateMantle(p, st, c) {
  const m = st.m;
  const k = c.t - st.t0;
  const P = Math.max(4, nv(CL.pullup_ticks, 12));
  if ((c.onGround && c.loc.y >= m.top - 0.1 && k >= 2) || k > P + 8) {
    endMode(p, st, "done");
    if (c.loc.y >= m.top - 0.1) done(p, st, "climb_block", { mult: Math.max(0, m.top - m.y0), mantle: true });
    return;
  }
  const rise = Math.max(1, Math.round(P * 0.6));
  const target = m.y0 + (m.top + 0.12 - m.y0) * Math.min(1, (k + 1) / rise);
  const over = c.loc.y >= m.top - 0.35;
  const h = over ? 0.24 : 0.04;
  const vy = clamp(target - c.loc.y, -0.15, 0.75);
  push(p, m.dir.x * h, m.dir.z * h, over && c.loc.y >= m.top ? Math.min(vy, 0.05) : vy);
  st.peakY = c.loc.y;
}

// ---------------------------------------------------------------------------
//  乗り越え
// ---------------------------------------------------------------------------
/** @param {Player} p @param {PState} st @param {Ctx} c */
function tryVault(p, st, c) {
  if (c.t - st.jumpT > 3 || st.jumpN === (st.cd.vaultJumpN ?? -1)) return false;
  if (c.t < (st.cd.vault ?? 0)) return false;
  const minSpd = nv(VA.min_speed, 0.12);
  const sprinting = c.t - st.sprintT <= 4;
  if (st.runSpd < minSpd) return false;
  if (!sprinting && c.mv.y < 0.3) return false;
  const groundY = c.t - st.groundT <= 4 ? st.groundY : c.loc.y;
  const ob = obstacleAhead(c, groundY);
  if (!ob) return false;
  const extra = assist() ? 0.15 : 0;
  const lowMax = nv(VA.low_max_height, 1.25) + extra;
  const highMax = Math.max(nv(VA.high_max_height, 1.6), skillNum(p, "vault_max_height", 0)) + extra;
  if (ob.h <= 0.55 || ob.h > highMax) return false;
  if (!consumeStamina(p, COST.vault * skillNum(p, "vault_stamina_mult", 1), { reason: "vault" })) return false;
  st.cd.vaultJumpN = st.jumpN;
  const high = ob.h > lowMax;
  const fi = nv(VA.forward_impulse, 0.55);
  const up = Math.min(0.8, Math.max(nv(VA.up_impulse, 0.45), Math.sqrt(2 * 0.08 * (ob.h + 0.2 - Math.max(0, c.loc.y - groundY)))));
  const keep = skillNum(p, "vault_speed_keep", nv(VA.speed_keep, 0.85));
  const dir = flat(c.fwd);
  enterMode(p, st, "vault", { dir, fi, up, exit: Math.max(0.2, Math.max(st.runSpd, 0.28) * keep), h: ob.h, high });
  push(p, dir.x * fi, dir.z * fi, up);
  anim(p, high ? "vault_high" : "vault");
  sound(c.dim, "nr.pk.vault", c.loc);
  done(p, st, "vault", { high, height: ob.h });
  return true;
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateVault(p, st, c) {
  const m = st.m;
  const k = c.t - st.t0;
  const T = Math.max(2, nv(VA.vault_ticks, 8));
  if ((c.onGround && k >= 2) || k >= T + 6) {
    endMode(p, st, "done");
    st.cd.vault = c.t + 4;
    if (c.onGround) push(p, m.dir.x * m.exit, m.dir.z * m.exit, 0);
    return;
  }
  if (k < T && st.spd < m.fi * 0.55) push(p, m.dir.x * m.fi, m.dir.z * m.fi, k <= 2 ? Math.max(c.vel.y, m.up * 0.6) : c.vel.y);
}

// ---------------------------------------------------------------------------
//  壁走り・壁蹴り
// ---------------------------------------------------------------------------
/** @param {Player} p @param {PState} st @param {Ctx} c */
function tryWallrun(p, st, c) {
  if (!c.jumpHeld || st.wrUsed || c.t < (st.cd.wallrun ?? 0) || c.t - st.airT < 2) return false;
  if (!hasSkill(p, SKILL_GATES.wallrun)) return false;
  const sprinting = c.t - st.sprintT <= 6;
  if (!sprinting && st.runSpd < nv(WR.min_speed, 0.18)) return false;
  const w = sideWall(c, nv(WR.wall_check_dist, 0.8));
  if (!w) return false;
  const along = sub(c.fwd, scale(w.n, dot(c.fwd, w.n)));
  const al = Math.hypot(along.x, along.z);
  if (al < 0.5) return false;
  if (!consumeStamina(p, COST.wallrun, { reason: "wallrun" })) return false;
  const dir = { x: along.x / al, y: 0, z: along.z / al };
  const T = Math.max(4, Math.round(skillNum(p, "wallrun_ticks", nv(WR.duration_ticks, 24))));
  st.wrUsed = true;
  enterMode(p, st, "wallrun", { side: w.side, n: w.n, dir, y0: c.loc.y, ty: c.loc.y, T, rise: skillNum(p, "wallrun_rise", nv(WR.rise, 1.2)),
    spd: Math.max(st.runSpd, nv(WR.forward_impulse, 0.42)), sink: 0, miss: 0 });
  loopAnim(p, w.side > 0 ? "wallrun_r" : "wallrun_l", "q.is_on_ground || q.state_time > 1.5");
  sound(c.dim, "nr.pk.wallrun", c.loc);
  done(p, st, "wallrun", { side: w.side > 0 ? "r" : "l" });
  return true;
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateWallrun(p, st, c) {
  const m = st.m;
  const k = c.t - st.t0;
  if ((c.onGround && k > 1) || k >= m.T) { endMode(p, st, c.onGround ? "ground" : "time"); return; }
  if (sneaked(st)) { endMode(p, st, "detach"); push(p, m.n.x * 0.25, m.n.z * 0.25, 0); return; }
  if (jumped(st)) { st.mJ = st.jumpN; if (wallJump(p, st, c)) return; }
  if (!wallStill(c, m.n, nv(WR.wall_check_dist, 0.8) + 0.25)) { if (++m.miss > 1) { endMode(p, st, "edge"); return; } } else m.miss = 0;
  const half = Math.max(1, Math.round(m.T / 2));
  if (k < half) { const f = (k + 1) / half; m.ty = m.y0 + m.rise * (1 - (1 - f) * (1 - f)); }
  else { m.sink += nv(WR.gravity_scale, 0.25) * 0.08; m.ty -= m.sink; }
  const vy = clamp(m.ty - c.loc.y, -0.6, 0.6);
  push(p, m.dir.x * m.spd - m.n.x * 0.04, m.dir.z * m.spd - m.n.z * 0.04, vy);
  st.peakY = c.loc.y;
  if (k % 3 === 0) particle(c.dim, "wall_scrape", { x: c.loc.x - m.n.x * 0.4, y: c.loc.y + 0.4, z: c.loc.z - m.n.z * 0.4 }, undefined, PRIO.LOW);
  if (k % 5 === 4) sound(c.dim, "nr.pk.step_run", c.loc, { volume: 0.5 });
}
/** 壁走り中の新しいジャンプの押下（スキル wall_jump）。 @param {Player} p @param {PState} st @param {Ctx} c */
function wallJump(p, st, c) {
  const eff = skillEff(p, SKILL_GATES.walljump);
  if (!eff) return false;
  if (st.chain >= Math.max(1, nv(eff.chain_max, 1))) return false;
  if (!consumeStamina(p, COST.walljump, { reason: "walljump" })) return false;
  const m = st.m;
  endMode(p, st, "walljump");
  const h = nv(eff.walljump_h, nv(WR.walljump_h, 0.9)), v = nv(eff.walljump_v, nv(WR.walljump_v, 0.55));
  push(p, m.n.x * h + m.dir.x * 0.35, m.n.z * h + m.dir.z * 0.35, v);
  anim(p, "wall_jump");
  sound(c.dim, "nr.pk.jump", c.loc);
  st.chain++;
  st.wrUsed = false;
  st.cd.wallrun = c.t + 4;
  st.cd.vaultJumpN = st.jumpN;
  st.peakY = c.loc.y;
  done(p, st, "walljump", { chain: st.chain });
  return true;
}

// ---------------------------------------------------------------------------
//  スライディング
// ---------------------------------------------------------------------------
/** @param {Player} p @param {PState} st @param {Ctx} c */
function trySlide(p, st, c) {
  if (c.t - st.sneakT > 2 || st.sneakN === (st.cd.slideSneakN ?? -1)) return false;
  if (c.t < (st.cd.slide ?? 0) || c.t - st.sprintT > 3) return false;
  if (st.runSpd < nv(SL.trigger_speed, 0.24)) return false;
  if (!consumeStamina(p, COST.slide, { reason: "slide" })) return false;
  st.cd.slideSneakN = st.sneakN;
  const tackle = skillEff(p, "slide_tackle");
  const T = Math.round(nv(SL.duration_ticks, 18) + (tackle ? nv(tackle.slide_ticks_add, 0) : 0));
  const dir = st.spd > 0.05 ? st.dir : flat(c.fwd);
  enterMode(p, st, "slide", { dir, spd: Math.max(st.runSpd, 0.28) * nv(SL.speed_boost, 1.35), T, hit: new Set(), tackle });
  push(p, dir.x * st.m.spd, dir.z * st.m.spd, 0);
  anim(p, "slide");
  sound(c.dim, "nr.pk.slide", c.loc);
  done(p, st, "slide");
  return true;
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateSlide(p, st, c) {
  const m = st.m;
  const k = c.t - st.t0;
  m.spd *= nv(SL.friction, 0.92);
  if (k >= m.T || m.spd < 0.08 || (!c.onGround && k > 2) || (k >= 2 && st.spd < m.spd * 0.3)) { endMode(p, st, "done"); return; }
  push(p, m.dir.x * m.spd, m.dir.z * m.spd, c.onGround ? 0 : c.vel.y);
  if (k % 2 === 0) particle(c.dim, "dust_slide", { x: c.loc.x - m.dir.x * 0.4, y: c.loc.y + 0.05, z: c.loc.z - m.dir.z * 0.4 }, undefined, PRIO.LOW);
  if (m.tackle) slideTackle(p, st, c);
}
/** スキル slide_tackle: 前の感染者の足を払う。 @param {Player} p @param {PState} st @param {Ctx} c */
function slideTackle(p, st, c) {
  const m = st.m;
  const at = { x: c.loc.x + m.dir.x * 0.8, y: c.loc.y + 0.4, z: c.loc.z + m.dir.z * 0.8 };
  /** @type {Entity[]} */
  let near = [];
  try { near = c.dim.getEntities({ location: at, maxDistance: 1.4, families: ["nr_zombie"] }); } catch { near = []; }
  for (const z of near) {
    if (!valid(z) || m.hit.has(z.id) || isCorpse(z)) continue;
    m.hit.add(z.id);
    applyHit(z, { attacker: p, source: "melee", dtype: "blunt", weight: "medium", damage: nv(m.tackle.slide_damage, 3),
      part: Math.random() < 0.5 ? "leg_r" : "leg_l", dir: m.dir, power: 1, knockdown: !!m.tackle.slide_knockdown, crit: false });
    particle(c.dim, "kick_impact", { x: z.location.x, y: z.location.y + 0.4, z: z.location.z }, undefined, PRIO.NORMAL);
  }
}

// ---------------------------------------------------------------------------
//  ドロップキック（空中でスニーク＋攻撃。スキル dropkick）
// ---------------------------------------------------------------------------
/** @param {Player} p @param {PState} st @param {Entity} z */
function tryDropkick(p, st, z) {
  const t = now();
  if (!hasSkill(p, SKILL_GATES.dropkick) || !isActive(p)) return false;
  if (st.ground || p.isOnGround || !p.isSneaking) return false;
  if (t - st.airT < nv(DK.min_air_ticks, 4) || t < (st.cd.dropkick ?? 0)) return false;
  if (st.mode && st.mode !== "vault" && st.mode !== "wallrun") return false;
  if (!consumeStamina(p, COST.dropkick, { reason: "dropkick" })) return false;
  const eff = skillEff(p, SKILL_GATES.dropkick) ?? {};
  const dir = flat(sub(z.location, p.location), yawForward(p.getRotation().y));
  const force = nv(eff.dropkick_force, nv(DK.force, 2.2));
  const up = nv(DK.up, 0.45);
  const wasCorpse = isCorpse(z);
  const res = applyHit(z, { attacker: p, source: "melee", dtype: "blunt", weight: "heavy", damage: nv(eff.dropkick_damage, nv(DK.damage, 6)),
    power: 1.6, dir, part: "torso", noKnockback: true, crit: false });
  if (valid(z)) {
    const kr = clamp(nv(zombieSpec(z)?.knockback_resist, 0), 0, 1);
    const k = force * (1 - kr);
    if (!wasCorpse && !res?.killed && !isCorpse(z)) stagger(z, Math.round(nv(eff.dropkick_stagger_ticks, nv(DK.stagger_ticks, 30))));
    // 吹き飛ばしは次の tick（同じ一撃のバニラの被弾 → gore の押し返しが速度を上書きするので、その後に足す）
    system.run(() => { if (valid(z)) { try { z.applyImpulse({ x: dir.x * k, y: up * (1 - kr * 0.5), z: dir.z * k }); } catch { /* 物理が無い */ } } });
  }
  if (st.mode) endMode(p, st, "dropkick", true);
  push(p, -dir.x * 0.3, -dir.z * 0.3, 0.3);
  anim(p, "dropkick");
  const hitAt = { x: z.location.x, y: z.location.y + 1, z: z.location.z };
  sound(p.dimension, "nr.pk.dropkick", hitAt);
  particle(p.dimension, "kick_impact", hitAt, undefined, PRIO.HIGH);
  shake(p, 0.4, 0.2);
  st.cd.dropkick = t + nv(DK.cooldown_ticks, 30);
  done(p, st, "dropkick", { zombie: z, killed: !!res?.killed });
  return true;
}

// ---------------------------------------------------------------------------
//  グラップリングフック
// ---------------------------------------------------------------------------
/** 鉤縄の線（grapple_line を点々と）。 @param {Dimension} dim @param {Vector3} a @param {Vector3} b */
function drawLine(dim, a, b) {
  const d = dist(a, b);
  const n = clamp(Math.ceil(d / 1.5), 1, 18);
  for (let i = 1; i <= n; i++) particle(dim, "grapple_line", lerpV(a, b, i / n), undefined, PRIO.LOW);
}

/**
 * フックを撃つ（アイテムの使用から。テストからも直接呼べる）。撃てたら true。
 * @param {Player} p @param {any} [use] data/items.js の use（range / cooldown_ticks）
 */
export function fireGrapple(p, use) {
  if (!valid(p)) return false;
  const st = pst(p);
  const t = now();
  if (!isActive(p) || st.mode === "grabbed") return false;
  if (t < (st.cd.grapple ?? 0)) { playerSound(p, "nr.ui.error"); return false; }
  const range = nv(use?.range, nv(GR.range, 26)) + skillNum(p, "grapple_range_add", 0);
  const head = p.getHeadLocation();
  const view = p.getViewDirection();
  const master = skillEff(p, "grapple_master");
  if (master?.grapple_pull_enemy) {
    /** @type {any} */
    let eh;
    try { eh = p.getEntitiesFromViewDirection({ maxDistance: range, families: ["nr_zombie"] })[0]; } catch { eh = undefined; }
    if (eh && valid(eh.entity) && !isCorpse(eh.entity) && consumeStamina(p, COST.grapple, { reason: "grapple" })) {
      const z = eh.entity;
      const to = flat(sub(p.location, z.location));
      const kr = clamp(nv(zombieSpec(z)?.knockback_resist, 0), 0, 1);
      try { z.applyImpulse({ x: to.x * 1.4 * (1 - kr), y: 0.35, z: to.z * 1.4 * (1 - kr) }); } catch { /* 物理が無い */ }
      stagger(z, 20);
      drawLine(p.dimension, head, { x: z.location.x, y: z.location.y + 1, z: z.location.z });
      playerAnim(p, "grapple_fire", { controller: ACT, blendOutTime: 0.1, stopExpression: "q.any_animation_finished", nextState: "none" });
      sound(p.dimension, "nr.pk.grapple_fire", head);
      st.cd.grapple = t + Math.round(nv(use?.cooldown_ticks, nv(GR.cooldown_ticks, 30)) * skillNum(p, "grapple_cooldown_mult", 1));
      done(p, st, "grapple", { enemy: z });
      return true;
    }
  }
  /** @type {any} */
  let hit;
  try { hit = p.getBlockFromViewDirection({ maxDistance: range, includePassableBlocks: false, includeLiquidBlocks: false }); } catch { hit = undefined; }
  if (!hit) {
    drawLine(p.dimension, head, { x: head.x + view.x * range * 0.5, y: head.y + view.y * range * 0.5, z: head.z + view.z * range * 0.5 });
    playerSound(p, "nr.ui.error");
    st.cd.grapple = t + 10;
    return false;
  }
  const anchor = { x: hit.block.x + hit.faceLocation.x, y: hit.block.y + hit.faceLocation.y, z: hit.block.z + hit.faceLocation.z };
  const d = dist(head, anchor);
  if (d < nv(GR.min_dist, 3)) { playerSound(p, "nr.ui.error"); return false; }
  if (!consumeStamina(p, COST.grapple, { reason: "grapple" })) { playerSound(p, "nr.ui.error"); return false; }
  const cdT = Math.max(1, Math.round(nv(use?.cooldown_ticks, nv(GR.cooldown_ticks, 30)) * skillNum(p, "grapple_cooldown_mult", 1)));
  st.cd.grapple = t + cdT;
  try { p.startItemCooldown("nr:grapple", cdT); } catch { /* 無い */ }
  enterMode(p, st, "grapple", { anchor, fly: Math.max(1, Math.ceil(d / Math.max(0.5, nv(GR.hook_speed, 3)))), lastD: Infinity, stuck: 0, pulling: false });
  playerAnim(p, "grapple_fire", { controller: ACT, blendOutTime: 0.1, stopExpression: "q.any_animation_finished", nextState: "none" });
  sound(p.dimension, "nr.pk.grapple_fire", head);
  return true;
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateGrapple(p, st, c) {
  const m = st.m;
  const k = c.t - st.t0;
  if (sneaked(st)) { endMode(p, st, "cancel"); return; }
  const hand = { x: c.loc.x, y: c.loc.y + 1.3, z: c.loc.z };
  if (k % 2 === 0) drawLine(c.dim, hand, k < m.fly ? lerpV(hand, m.anchor, (k + 1) / m.fly) : m.anchor);
  if (k < m.fly) return;
  if (!m.pulling) {
    m.pulling = true;
    loopAnim(p, "grapple_pull", "q.state_time > 2.0");
    sound(c.dim, "nr.pk.grapple_reel", c.loc);
  }
  const body = { x: c.loc.x, y: c.loc.y + 0.9, z: c.loc.z };
  const to = sub(m.anchor, body);
  const dd = len(to);
  const arrive = () => {
    endMode(p, st, "arrive");
    const f = flat(to, c.fwd);
    push(p, f.x * 0.25, f.z * 0.25, 0.45);
    st.peakY = c.loc.y;
    done(p, st, "grapple");
  };
  if (dd <= 1.6 || k - m.fly >= nv(GR.max_pull_ticks, 30)) { arrive(); return; }
  if (dd > m.lastD - 0.05) { if (++m.stuck >= 4) { arrive(); return; } } else m.stuck = 0;
  m.lastD = dd;
  const sp = Math.min(nv(GR.pull_speed, 1.6), 0.35 + dd * 0.5);
  push(p, (to.x / dd) * sp, (to.z / dd) * sp, (to.y / dd) * sp + 0.08);
  st.peakY = c.loc.y;
}

// ---------------------------------------------------------------------------
//  パラグライダー
// ---------------------------------------------------------------------------
/**
 * 翼を開く・畳む（アイテムの使用から。テストからも直接呼べる）。開いたら true。
 * @param {Player} p @param {any} [use] data/items.js の use（min_height）
 */
export function toggleGlide(p, use) {
  if (!valid(p)) return false;
  const st = pst(p);
  if (st.mode === "glide") { endMode(p, st, "fold"); return false; }
  if (!isActive(p) || st.mode === "grabbed" || p.isOnGround) { playerSound(p, "nr.ui.error"); return false; }
  const g = groundBelow(p.dimension, p.location, 64);
  const h = g ? p.location.y - g.y : 99;
  if (h < nv(use?.min_height, nv(GL.min_height, 3))) { playerSound(p, "nr.ui.error"); return false; }
  enterMode(p, st, "glide", { yaw: p.getRotation().y, up: false });
  playerAnim(p, "glide_open", { controller: ACT, blendOutTime: 0.1, stopExpression: "q.any_animation_finished", nextState: "none" });
  loopAnim(p, "glide", "q.is_on_ground");
  sound(p.dimension, "nr.pk.glider_open", p.location);
  try { p.addEffect("slow_falling", 14, { amplifier: Math.max(0, Math.floor(nv(GL.slow_falling_amp, 0))), showParticles: false }); } catch { /* 効かない */ }
  return true;
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateGlide(p, st, c) {
  const m = st.m;
  const k = c.t - st.t0;
  if (c.onGround && k > 1) { endMode(p, st, "land"); return; }
  if (GL.fold_on_sneak !== false && sneaked(st)) { endMode(p, st, "fold"); return; }
  const turn = nv(GL.turn_rate, 6);
  m.yaw += clamp(angleDiff(c.yaw, m.yaw), -turn, turn);
  const f = yawForward(m.yaw);
  if (k % 4 === 0) m.up = updraftBelow(c);
  const vy = m.up ? nv(GL.updraft_lift, 0.25) * skillNum(p, "updraft_mult", 1) : -nv(GL.sink_per_tick, 0.06) * skillNum(p, "glide_sink_mult", 1);
  const fs = nv(GL.forward_speed, 0.42);
  push(p, f.x * fs, f.z * fs, vy);
  if (k % 10 === 0) { try { p.addEffect("slow_falling", 14, { amplifier: Math.max(0, Math.floor(nv(GL.slow_falling_amp, 0))), showParticles: false }); } catch { /* 効かない */ } }
  if (k % 30 === 15) sound(c.dim, "nr.pk.glider_wind", c.loc, { volume: 0.6 });
  if (k > 0 && k % 20 === 0) done(p, st, "glide_s");
  st.peakY = c.loc.y;
}

// ---------------------------------------------------------------------------
//  掴まれた（バス "grabbed" → 連打で振りほどく → "shove"）
// ---------------------------------------------------------------------------
/**
 * 掴まれた状態にする（zombies/ がバス "grabbed" で知らせる。テストからも直接呼べる）。
 * @param {Player} p @param {Entity} z
 */
export function grab(p, z) {
  if (!valid(p) || !isActive(p)) return false;
  const st = pst(p);
  if (st.mode === "grabbed") { st.m.zombie = z; return true; }
  enterMode(p, st, "grabbed", { zombie: z, presses: 0, need: GRAB.presses, lastPress: now() });
  loopAnim(p, "grabbed_struggle", "q.state_time > 12.0");
  playerSound(p, "nr.pl.grabbed");
  root(p);
  return true;
}
/** 掴みが外れた（振りほどき以外）。 @param {Player} p @param {string} [why] */
export function release(p, why = "release") {
  if (!valid(p)) return false;
  const st = states.get(p.id);
  if (st?.mode !== "grabbed") return false;
  endMode(p, st, why);
  return true;
}
/** 動けなくする（鈍足を短く何度も。スクリプトが止まっても数 tick で切れる）。 @param {Player} p */
function root(p) { try { p.addEffect("slowness", 8, { amplifier: 7, showParticles: false }); } catch { /* 効かない */ } }

/** 連打の 1 回（ジャンプの押下・攻撃）。 @param {Player} p @param {PState} st @param {string} kind */
function mash(p, st, kind) {
  const m = st.m;
  m.presses++;
  m.lastPress = now();
  if (m.presses < m.need) { shake(p, 0.12, 0.1); return; }
  const z = m.zombie;
  const dir = valid(z) ? flat(sub(z.location, p.location)) : yawForward(p.getRotation().y);
  const presses = m.presses;
  endMode(p, st, "shove", true);
  anim(p, "shove");
  if (valid(z)) particle(p.dimension, "kick_impact", { x: z.location.x, y: z.location.y + 1.1, z: z.location.z }, undefined, PRIO.NORMAL);
  emit(PEV.SHOVE, { player: p, zombie: z, dir, presses, by: kind });
  done(p, st, "shove");
}
/** @param {Player} p @param {PState} st @param {Ctx} c */
function updateGrabbed(p, st, c) {
  const m = st.m;
  const k = c.t - st.t0;
  if (!valid(m.zombie) || isCorpse(m.zombie)) { endMode(p, st, "zombie_gone"); return; }
  if (k > GRAB.maxTicks) { endMode(p, st, "timeout"); return; }
  if (m.presses > 0 && c.t - m.lastPress > GRAB.decayEvery) { m.presses--; m.lastPress = c.t; }
  if (k % 5 === 0) root(p);
  st.peakY = c.loc.y;
}

// ---------------------------------------------------------------------------
//  モードの表
// ---------------------------------------------------------------------------
/** @type {Record<string, (p: Player, st: PState, c: Ctx) => void>} */
const UPDATE = {
  climb: updateClimb, hang: updateHang, mantle: updateMantle, vault: updateVault, wallrun: updateWallrun,
  slide: updateSlide, grapple: updateGrapple, glide: updateGlide, grabbed: updateGrabbed,
};

// ---------------------------------------------------------------------------
//  イベント
// ---------------------------------------------------------------------------
world.afterEvents.playerButtonInput.subscribe((ev) => {
  const p = ev.player;
  if (!valid(p)) return;
  const st = pst(p);
  const t = now();
  if (ev.button === InputButton.Jump) {
    st.jumpT = t; st.jumpN++;
    if (st.mode === "grabbed") guard("grab.mash", () => mash(p, st, "jump"));
  } else if (ev.button === InputButton.Sneak) { st.sneakT = t; st.sneakN++; }
}, { buttons: [InputButton.Jump, InputButton.Sneak], state: ButtonState.Pressed });

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const a = ev.damagingEntity;
  if (!isPlayer(a) || !valid(a)) return;
  const p = /** @type {Player} */ (a);
  const st = states.get(p.id);
  if (!st) return;
  if (st.mode === "grabbed") { guard("grab.mash", () => mash(p, st, "attack")); return; }
  const z = ev.hitEntity;
  if (isZombie(z) && valid(z)) guard("dropkick", () => tryDropkick(p, st, z));
});

world.afterEvents.itemUse.subscribe((ev) => {
  const p = ev.source;
  const it = ev.itemStack;
  if (!valid(p) || !it) return;
  const use = USE_BY_ID[it.typeId];
  if (!use) return;
  if (use.type === "grapple") guard("grapple", () => fireGrapple(p, use));
  else if (use.type === "glide") guard("glide", () => toggleGlide(p, use));
});

on(PEV.GRABBED, (d) => { if (valid(d?.player)) grab(d.player, d.zombie); });
on(PEV.GRAB_END, (d) => { if (valid(d?.player)) release(d.player, "grab_end"); });

world.afterEvents.playerSpawn.subscribe((ev) => {
  const st = states.get(ev.player.id);
  if (!st) return;
  if (st.mode) endMode(ev.player, st, "respawn");
  st.ground = true; st.peakY = ev.player.location.y; st.vanFall = 0; st.guard = false; st.landing = undefined; st.lastLoc = undefined;
});
