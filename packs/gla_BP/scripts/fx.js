// 演出 / VFX・音
//
// 企画書 §11 の5層（1予兆 / 2軌道 / 3接触 / 4広がり / 5余韻）をそのまま実装する。
// 豪華さは粒子の総量ではなく「見せたい瞬間に情報を集中させて」作るので、
// ここでは "どう並べるか" だけを持ち、何を出すかは spec.py が決める。
//
// 品質設定は層と密度の2軸で効く（企画書 §15 省略する順番）:
//   軽量   1,2,3 層のみ・密度45%   -> 画面外の飾りと余韻から先に消える
//   標準   1..4 層・密度80%
//   高品質 全層・密度100%
// 顔・身体の輪郭と命中の芯（3層）は、どの設定でも最後まで残る。
import { system } from "@minecraft/server";
import { QUALITY, DEFAULTS } from "./data.js";
import { basis, atBasis, forward, normalise, viewDir, clamp } from "./util.js";

export function spawn(dimension, id, location) {
  try { dimension.spawnParticle(id, location); } catch (_) { }
}

export function sound(dimension, id, location, opts) {
  try { dimension.playSound(id, location, opts); } catch (_) { }
}

/** カメラの揺れ。API ではなくコマンドなので、使えない環境では黙って何もしない。 */
export function shake(player, intensity, seconds, type = "positional") {
  try {
    player.runCommand(
      `camerashake add @s ${intensity.toFixed(2)} ${seconds.toFixed(2)} ${type}`);
  } catch (_) { }
}

// ---------------------------------------------------------------------------
//  並べ方 — 同じ粒でも並べ方を変えると別の技に見える（企画書 §10 差別化の検収）
// ---------------------------------------------------------------------------
function emitPoint(dim, id, origin) {
  spawn(dim, id, origin);
}

function emitRing(dim, id, centre, n, radius, tilt) {
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    spawn(dim, id, {
      x: centre.x + Math.cos(a) * radius,
      y: centre.y + (tilt || 0.2),
      z: centre.z + Math.sin(a) * radius,
    });
  }
}

function emitLine(dim, id, origin, dir, n, dist) {
  const step = dist / Math.max(1, n - 1);
  for (let i = 0; i < n; i++) spawn(dim, id, forward(origin, dir, step * i));
}

function emitArc(dim, id, origin, dir, n, radius, sweepDeg, tilt) {
  const b = basis(dir);
  const half = ((sweepDeg || 150) * Math.PI) / 360;
  for (let i = 0; i < n; i++) {
    const a = -half + (i / Math.max(1, n - 1)) * half * 2;
    spawn(dim, id, atBasis(origin, b, Math.cos(a) * radius,
                           Math.sin(a) * radius, tilt || 0));
  }
}

function emitSpiral(dim, id, origin, dir, n, radius, dist, tilt) {
  const b = basis(dir);
  const turns = 2.2;
  for (let i = 0; i < n; i++) {
    const t = i / Math.max(1, n - 1);
    const a = t * Math.PI * 2 * turns + (tilt || 0);
    spawn(dim, id, atBasis(origin, b, t * dist,
                           Math.cos(a) * radius, Math.sin(a) * radius));
  }
}

function emitCone(dim, id, origin, dir, n, dist, radius) {
  const b = basis(dir);
  for (let i = 0; i < n; i++) {
    const t = (i + 1) / n;
    const a = i * 2.399963;                       // 黄金角。同じ線に乗らない。
    const r = radius * t;
    spawn(dim, id, atBasis(origin, b, dist * t,
                           Math.cos(a) * r, Math.sin(a) * r));
  }
}

function emitFan(dim, id, origin, dir, n, radius, sweepDeg) {
  const b = basis(dir);
  const half = ((sweepDeg || 120) * Math.PI) / 360;
  for (let i = 0; i < n; i++) {
    const a = -half + (i / Math.max(1, n - 1)) * half * 2;
    const r = radius * (0.55 + 0.45 * Math.cos(a));
    spawn(dim, id, atBasis(origin, b, Math.cos(a) * r, Math.sin(a) * r, 0));
  }
}

function emitPillar(dim, id, origin, n, radius, height) {
  for (let i = 0; i < n; i++) {
    const t = i / Math.max(1, n - 1);
    const a = t * Math.PI * 4;
    spawn(dim, id, {
      x: origin.x + Math.cos(a) * radius,
      y: origin.y + height * t,
      z: origin.z + Math.sin(a) * radius,
    });
  }
}

function emitCurtain(dim, id, origin, dir, n, radius, height) {
  const b = basis(dir);
  const cols = Math.max(2, Math.round(Math.sqrt(n)));
  for (let i = 0; i < n; i++) {
    const cx = (i % cols) / (cols - 1) - 0.5;
    const cy = Math.floor(i / cols) / Math.max(1, Math.ceil(n / cols) - 1);
    spawn(dim, id, atBasis(origin, b, 0, cx * radius * 2, cy * height));
  }
}

function emitScatter(dim, id, centre, n, spread) {
  for (let i = 0; i < n; i++) {
    spawn(dim, id, {
      x: centre.x + (Math.random() - 0.5) * spread * 2,
      y: centre.y + Math.random() * spread,
      z: centre.z + (Math.random() - 0.5) * spread * 2,
    });
  }
}

function emitTail(dim, id, origin, dir, n, dist) {
  // 後ろへ引く尾。進行方向の逆に、間隔を広げながら置く。
  const back = { x: -dir.x, y: -dir.y, z: -dir.z };
  for (let i = 0; i < n; i++) {
    const t = (i / Math.max(1, n - 1)) ** 1.4;
    spawn(dim, id, forward(origin, back, dist * t));
  }
}

// ---------------------------------------------------------------------------
//  品質設定
// ---------------------------------------------------------------------------
export function qualityOf(key) {
  return QUALITY[key] ?? QUALITY[DEFAULTS.quality];
}

/** その層を描くか。3層（接触）は常に描く — 命中が読めなくなるのが一番困る。 */
export function layerVisible(q, layer) {
  if (layer === 3) return true;
  return qualityOf(q).layers.includes(layer);
}

function count(q, n) {
  const scaled = Math.round((n ?? 1) * qualityOf(q).density);
  return clamp(scaled, 1, 64);
}

// ---------------------------------------------------------------------------
//  1コマの再生
// ---------------------------------------------------------------------------
/**
 * spec.stage() が作った1コマを描く。
 * `ctx` は {dimension, origin, dir, target, feet, ground, chest, eye, quality}。
 */
export function playStage(ctx, st) {
  if (!layerVisible(ctx.quality, st.layer)) return 0;
  const dim = ctx.dimension;
  const at = originFor(ctx, st.at);
  if (!at) return 0;
  const n = count(ctx.quality, st.n);
  const dir = ctx.dir;
  switch (st.form) {
    case "ring": emitRing(dim, st.fx, at, n, st.r ?? 1, st.tilt); break;
    case "line": emitLine(dim, st.fx, at, dir, n, st.d ?? 4); break;
    case "arc": emitArc(dim, st.fx, at, dir, n, st.r ?? 2, st.sweep, st.tilt); break;
    case "spiral": emitSpiral(dim, st.fx, at, dir, n, st.r ?? 1, st.d ?? 4, st.tilt); break;
    case "cone": emitCone(dim, st.fx, at, dir, n, st.d ?? 4, st.r ?? 2); break;
    case "fan": emitFan(dim, st.fx, at, dir, n, st.r ?? 2, st.sweep); break;
    case "pillar": emitPillar(dim, st.fx, at, n, st.r ?? 0.6, st.d ?? 3); break;
    case "curtain": emitCurtain(dim, st.fx, at, dir, n, st.r ?? 2, st.d ?? 3); break;
    case "scatter": emitScatter(dim, st.fx, at, n, st.spread ?? 1); break;
    case "tail": emitTail(dim, st.fx, at, dir, n, st.d ?? 3); break;
    default: emitPoint(dim, st.fx, at); return 1;
  }
  return n;
}

function originFor(ctx, key) {
  switch (key) {
    case "target": return ctx.target ?? ctx.origin;
    case "feet": return ctx.feet;
    case "ground": return ctx.ground ?? ctx.feet;
    case "chest": return ctx.chest;
    case "eye": return ctx.eye ?? ctx.chest;
    default: return ctx.origin;
  }
}

/** 拳の位置。伸ばす技の始点は目ではなく手にしたい。 */
export function handPoint(player) {
  const dir = viewDir(player);
  const b = basis(dir);
  const head = { x: player.location.x, y: player.location.y + 1.35, z: player.location.z };
  return atBasis(head, b, 0.5, 0.32, -0.18);
}

export function makeContext(player, quality, target) {
  const loc = player.location;
  const dir = normalise(viewDir(player));
  return {
    dimension: player.dimension,
    quality,
    dir,
    origin: handPoint(player),
    chest: { x: loc.x, y: loc.y + 1.2, z: loc.z },
    eye: { x: loc.x, y: loc.y + 1.62, z: loc.z },
    feet: { x: loc.x, y: loc.y + 0.1, z: loc.z },
    ground: { x: loc.x, y: loc.y + 0.1, z: loc.z },
    target: target ?? null,
  };
}

// ---------------------------------------------------------------------------
//  大技のフル演出・同時数（企画書 §15）
//
//  軽量 1 / 標準 2 / 高品質 2。重い演出が同時に何本も走るのが一番効くので、
//  枠を取れなかったものは「予兆・軌道・接触」だけの短い版に落とす。
//  ゲーム上の判定は一切変えない — 落とすのは見た目だけ。
// ---------------------------------------------------------------------------
const bigFx = new Map();        // playerId -> 終了 tick

export function bigFxSlots(quality) {
  return qualityOf(quality).showpiece;
}

/** 大技のフル演出の枠を取る。取れなければ false（短い版で出す）。 */
export function claimBigFx(player, quality, ticks) {
  const now = system.currentTick;
  for (const [id, until] of bigFx) {
    if (until <= now) bigFx.delete(id);
  }
  if (bigFx.has(player.id)) {          // 自分の枠は取り直せる
    bigFx.set(player.id, now + ticks);
    return true;
  }
  if (bigFx.size >= bigFxSlots(quality)) return false;
  bigFx.set(player.id, now + ticks);
  return true;
}

export function releaseBigFx(id) {
  bigFx.delete(id);
}

export function bigFxActive() {
  const now = system.currentTick;
  let n = 0;
  for (const until of bigFx.values()) if (until > now) n++;
  return n;
}

// ---------------------------------------------------------------------------
//  近傍の演出補助エンティティの上限（企画書 §15 VFX補助エンティティ・近傍上限案）
// ---------------------------------------------------------------------------
export function helperBudget(quality) {
  return qualityOf(quality).helpers;
}

export function helpersNear(dimension, location, radius = 24) {
  try {
    return dimension.getEntities({
      location, maxDistance: radius,
      families: ["gla_vfx"],
    }).length;
  } catch (_) { return 0; }
}

/** 予算内なら演出用の表示体を出す。溢れたら黙って粒子だけで済ませる。 */
export function spawnHelper(dimension, typeId, location, quality) {
  if (helpersNear(dimension, location) >= helperBudget(quality)) return undefined;
  try { return dimension.spawnEntity(typeId, location); } catch (_) { return undefined; }
}

export function playSfx(dimension, location, entry) {
  sound(dimension, entry.id, location, { volume: entry.v ?? 1, pitch: entry.p ?? 1 });
}

export const currentTick = () => system.currentTick;
