// ===========================================================================
//  技の実行エンジン
//  * 入力の状況（スニーク／空中／ダッシュ）から 4 種の技のどれを出すかを決める
//  * 再使用時間・ゲージ・「技の最中」ロック
//  * 技は ctx.at(tick, fn) で時間割を組む。途中で死亡・退出したら以降は走らない
//  * 技どうしで共通の動き（突進・急降下・ホバー・瞬間移動）をここにまとめる
// ===========================================================================
import { system } from "@minecraft/server";
import { GAUGE_MAX, MOVE_LABEL, WEIGHT } from "./config.js";
import { gauge, setGauge, enemiesNear, lockGauge } from "./combat.js";
import { P, body, bodyStop, cutin, flash, sound, white } from "./fx.js";
import { markAirborne } from "./mobility.js";
import { holdHud } from "./hud.js";
import { blocked } from "./projectiles.js";
import {
  valid, health, knock, flatDir, viewDir, effect, add, now, dist, norm, sub,
} from "./util.js";

const cooldowns = new Map();   // playerId -> { kind: untilTick }
const busy = new Map();        // playerId -> untilTick
const errorsSeen = new Set();

export const MOVES = {};       // key -> { skill, dash, air, ult }
export function register(key, impl) { MOVES[key] = impl; }

export function cdLeft(player, w, kind) {
  const m = cooldowns.get(player.id);
  return Math.max(0, (m?.[`${w.key}.${kind}`] ?? 0) - now());
}
function setCd(player, w, kind, ticks) {
  const m = cooldowns.get(player.id) ?? {};
  m[`${w.key}.${kind}`] = now() + ticks;
  cooldowns.set(player.id, m);
}
export function isBusy(player) { return (busy.get(player.id) ?? 0) > now(); }
export function clearBusy(player) { busy.delete(player.id); }

function alive(p) {
  if (!valid(p)) return false;
  const h = health(p);
  return !h || h.currentValue > 0;
}

function report(where, err) {
  const key = `${where}:${err?.message ?? err}`;
  if (errorsSeen.has(key)) return;
  errorsSeen.add(key);
  console.warn(`[hd] ${where}: ${err?.stack ?? err}`);
}

/** 状況から技の種類を選ぶ。 */
export function chooseKind(player) {
  if (player.isSneaking && gauge(player) >= GAUGE_MAX) return "ult";
  if (!player.isOnGround && !player.isInWater) return "air";
  if (player.isSprinting) return "dash";
  return "skill";
}

/** 技を出す。出せたら true。 */
export function perform(player, w, kind, extra = {}) {
  if (!alive(player)) return false;
  if (isBusy(player) && !extra.force) return false;
  const impl = MOVES[w.key]?.[kind];
  if (!impl) return false;
  const mv = w.moves[kind];
  const left = cdLeft(player, w, kind);
  if (left > 0) {
    try {
      player.onScreenDisplay.setActionBar(
        `§7${MOVE_LABEL[kind]}「${mv.name}」 §cあと ${(left / 20).toFixed(1)} 秒`);
      holdHud(player, 16);
    } catch (_) { }
    sound(player.dimension, "note.bass", player.location, 0.6, 0.4);
    return false;
  }
  if (kind === "ult") {
    if (gauge(player) < GAUGE_MAX) return false;
    setGauge(player, 0);
  }
  const ctx = makeCtx(player, w, kind, extra);
  let dur = 10;
  try { dur = impl(ctx) ?? 10; } catch (e) { report(`${w.key}.${kind}`, e); }
  busy.set(player.id, now() + dur);
  if (kind === "ult") lockGauge(player, dur + 10);
  setCd(player, w, kind, mv.cd);
  return true;
}

// ---------------------------------------------------------------------------
//  技の文脈
// ---------------------------------------------------------------------------
function makeCtx(p, w, kind, extra) {
  const ctx = {
    p, w, kind, extra,
    dim: p.dimension,
    c: w.color, deep: w.deep, hot: white(w.color, 0.45),
    f: flatDir(p), v: viewDir(p),
    start: { ...p.location },
    struck: new Map(),
    /** t tick 後に fn を実行（t <= 0 なら今すぐ）。 */
    at(t, fn) {
      const go = () => {
        if (!alive(p) || p.dimension.id !== ctx.dim.id) return;
        try { fn(); } catch (e) { report(`${w.key}.${kind}@${t}`, e); }
      };
      if (t <= 0) go(); else system.runTimeout(go, Math.round(t));
    },
    /** 0..n-1 の i について、every tick おきに fn(i)。 */
    every(t0, n, every, fn) {
      for (let i = 0; i < n; i++) ctx.at(t0 + i * every, () => fn(i));
    },
    /** 同じ技で同じ相手に当てる回数を制限する。 */
    once(e, max = 1) {
      const k = ctx.struck.get(e.id) ?? 0;
      if (k >= max) return false;
      ctx.struck.set(e.id, k + 1);
      return true;
    },
    loc() { return p.location; },
    chest() { const l = p.location; return { x: l.x, y: l.y + 1.0, z: l.z }; },
    front(d = 1.6, y = 1.0) {
      const l = p.location;
      return { x: l.x + ctx.f.x * d, y: l.y + y, z: l.z + ctx.f.z * d };
    },
    liveDir() { return flatDir(p); },
  };
  return ctx;
}

// ---------------------------------------------------------------------------
//  共通の動き
// ---------------------------------------------------------------------------
export function weightOf(w) { return WEIGHT[w.weight] ?? WEIGHT.mid; }

/** 前へ突進。power は水平速度（block/tick 相当）。 */
export function lunge(ctx, dir, power, up = 0.12) {
  knock(ctx.p, dir.x, dir.z, power, up);
  markAirborne(ctx.p);
}

/** 宙に浮いて静止気味にする（空中技の溜め）。 */
export function hover(ctx, ticks, lift = 0.35) {
  knock(ctx.p, 0, 0, 0, lift);
  effect(ctx.p, "slow_falling", ticks, 0);
  markAirborne(ctx.p);
}

/** 真下へ叩きつけ、着地した瞬間に onLand(loc)。着地しなければ maxT で強制。 */
export function plunge(ctx, onLand, maxT = 34, speed = 2.6) {
  const p = ctx.p;
  try { p.removeEffect?.("slow_falling"); } catch (_) { }
  knock(p, 0, 0, 0, -speed);
  markAirborne(p);
  let landed = false;
  for (let t = 1; t <= maxT; t++) {
    ctx.at(t, () => {
      if (landed) return;
      if (p.isOnGround || t === maxT) {
        landed = true;
        onLand({ ...p.location });
      } else if (t % 2 === 0) {
        P(ctx.dim, "trail", { x: p.location.x, y: p.location.y + 1.0, z: p.location.z },
          { color: ctx.c, size: 1.4, life: 0.25 });
        P(ctx.dim, "speedline", { x: p.location.x, y: p.location.y + 1.6, z: p.location.z },
          { color: ctx.hot, count: 3, dir: { x: 0, y: 1, z: 0 }, speed: 10, spread: 0.6 });
      }
    });
  }
}

/** その場所に立てるか（足元と頭が空いているか）。 */
export function standable(dim, loc) {
  return !blocked(dim, loc) && !blocked(dim, { x: loc.x, y: loc.y + 1.2, z: loc.z });
}

/** 壁にめり込まない範囲で from から dir へ最大 maxD 進んだ地点。 */
export function safeAhead(dim, from, dir, maxD) {
  let last = { ...from };
  for (let d = 0.5; d <= maxD; d += 0.5) {
    const q = { x: from.x + dir.x * d, y: from.y, z: from.z + dir.z * d };
    if (!standable(dim, q)) break;
    last = q;
  }
  return last;
}

export function warp(p, loc, facing) {
  try {
    const opts = { dimension: p.dimension, keepVelocity: false };
    if (facing) opts.facingLocation = facing;
    p.teleport(loc, opts);
    markAirborne(p);
    return true;
  } catch (_) { return false; }
}

/** 標的の背後（標的から見て後ろ）に立つ位置。 */
export function behind(target, d = 1.4) {
  let fd = { x: 0, y: 0, z: 1 };
  try { fd = target.getViewDirection(); } catch (_) { }
  const l = Math.hypot(fd.x, fd.z) || 1;
  const t = target.location;
  return { x: t.x - fd.x / l * d, y: t.y, z: t.z - fd.z / l * d };
}

/** 必殺技の開幕: カットイン・フラッシュ・無敵・時間停止（周囲の敵の足止め）。 */
export function ultOpen(ctx, ticks, freezeRadius = 12) {
  const { p, dim, w } = ctx;
  const mv = w.moves.ult;
  cutin(p, w.tc, mv.name, mv.en);
  flash(dim, p.location, 26, white(ctx.c, 0.4), 0.06, 0.3);
  sound(dim, "hd.cutin", p.location, 1.0, 1.4);
  effect(p, "resistance", ticks, 4);
  for (const e of enemiesNear(p, p.location, freezeRadius)) {
    effect(e, "slowness", Math.min(ticks, 50), 6);
  }
  body(p, "ult_rise");
  P(dim, "circle", { x: p.location.x, y: p.location.y + 0.05, z: p.location.z },
    { color: ctx.c, size: 3.2, life: 2.2, spin: 60 });
  P(dim, "converge", ctx.chest(), { color: ctx.hot, count: 26, spread: 3.2, life: 0.6, size: 1.2 });
}

export function dirTo(from, to) {
  return norm({ x: to.x - from.x, y: 0, z: to.z - from.z });
}

export { body, bodyStop, add, dist, sub, now };
