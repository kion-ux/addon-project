// 戦闘 / 当たり判定・命中履歴・ノックバック
//
// 企画書 §09 の判定方針をそのまま実装する:
//   * 前方打撃は前方の範囲、伸びる拳は通過した軌道、叩きつけは着弾地点の周囲
//   * 「単に自分の周囲を毎回全方向攻撃」しない — 全方位が許されるのは
//     そう宣言した技（白い星銃）だけ
//   * 壁越しの命中、所有者・観客への誤爆を除外する
//   * 技の発動ごとに一意の action_id を発行し、対象ごとの命中履歴を持つ。
//     粒子や見た目エンティティには攻撃責任を持たせない
import { world, system } from "@minecraft/server";
import { PROP, DEFAULTS } from "./data.js";
import {
  distance, normalise, dot, forward, knockback, basis, atBasis, clamp,
} from "./util.js";

// ---------------------------------------------------------------------------
//  ワールド設定（企画書 §09 初期値 OFF）
// ---------------------------------------------------------------------------
export function terrainAllowed() {
  try {
    const v = world.getDynamicProperty(PROP.terrain);
    return typeof v === "boolean" ? v : DEFAULTS.terrain;
  } catch (_) { return DEFAULTS.terrain; }
}

export function pvpAllowed() {
  try {
    const v = world.getDynamicProperty(PROP.pvp);
    return typeof v === "boolean" ? v : DEFAULTS.pvp;
  } catch (_) { return DEFAULTS.pvp; }
}

export function setTerrain(on) {
  try { world.setDynamicProperty(PROP.terrain, !!on); } catch (_) { }
}

export function setPvp(on) {
  try { world.setDynamicProperty(PROP.pvp, !!on); } catch (_) { }
}

// ---------------------------------------------------------------------------
//  action_id と命中履歴
//
//  1回の発動 = 1つの action_id。対象ごとに「あと何回当ててよいか」を持つので、
//  単発は必ず1回、連打は技定義の回数だけになる。押しっぱなしや連打で同じ発動が
//  二重に走っても、履歴が同じなので増えない。
// ---------------------------------------------------------------------------
let nextAction = 1;
const actions = new Map();       // actionId -> {hits, gap, seen: Map<entityId, {n, at}>}

export function beginAction(maxHits, gapTicks) {
  const id = nextAction++;
  actions.set(id, { hits: Math.max(1, maxHits), gap: gapTicks ?? 0, seen: new Map() });
  // 一番長い技でも 30 秒あれば終わる。残骸を溜めない。
  system.runTimeout(() => actions.delete(id), 600);
  return id;
}

export function endAction(id) {
  actions.delete(id);
}

/** この action_id で、この対象へ今ダメージを入れてよいか。 */
export function mayHit(actionId, entity) {
  const a = actions.get(actionId);
  if (!a) return false;
  let key;
  try { key = entity.id; } catch (_) { return false; }
  const rec = a.seen.get(key);
  const now = system.currentTick;
  if (!rec) { a.seen.set(key, { n: 1, at: now }); return true; }
  if (rec.n >= a.hits) return false;
  if (a.gap && now - rec.at < a.gap) return false;
  rec.n += 1;
  rec.at = now;
  return true;
}

export function timesHit(actionId, entity) {
  const a = actions.get(actionId);
  if (!a) return 0;
  try { return a.seen.get(entity.id)?.n ?? 0; } catch (_) { return 0; }
}

// ---------------------------------------------------------------------------
//  対象の抽出
// ---------------------------------------------------------------------------
function candidates(dimension, location, radius) {
  try {
    return dimension.getEntities({ location, maxDistance: radius });
  } catch (_) { return []; }
}

function valid(entity, owner) {
  if (!entity) return false;
  let id;
  try { id = entity.typeId; } catch (_) { return false; }
  if (!id) return false;
  if (entity === owner) return false;
  try { if (entity.id === owner.id) return false; } catch (_) { }
  // 演出用の表示体は攻撃対象にしない（自分の拳を殴らない）
  if (id.startsWith("gla:vfx_") || id === "gla:thrown_bolt") return false;
  if (id === "minecraft:item" || id === "minecraft:xp_orb"
      || id === "minecraft:arrow" || id === "minecraft:area_effect_cloud") return false;
  if (id === "minecraft:player" && !pvpAllowed()) return false;
  try {
    const h = entity.getComponent("minecraft:health");
    if (!h || h.currentValue <= 0) return false;
  } catch (_) { return false; }
  return true;
}

/** 壁越しの命中を弾く。ブロックの取得に失敗したら「見えている」側に倒す。 */
export function blocked(dimension, from, to) {
  const d = { x: to.x - from.x, y: to.y - from.y, z: to.z - from.z };
  const len = Math.hypot(d.x, d.y, d.z);
  if (len < 1.2) return false;
  const dir = { x: d.x / len, y: d.y / len, z: d.z / len };
  try {
    const hit = dimension.getBlockFromRay(from, dir, { maxDistance: len - 0.4 });
    if (hit?.block) {
      // 通り抜けられるものは壁扱いしない
      try {
        if (hit.block.isAir || hit.block.isLiquid) return false;
      } catch (_) { }
      return true;
    }
    return false;
  } catch (_) { }
  // getBlockFromRay が無い版のための保険。粗く標本を取る。
  try {
    const steps = Math.min(16, Math.max(2, Math.round(len)));
    for (let i = 1; i < steps; i++) {
      const p = forward(from, dir, (len * i) / steps);
      const b = dimension.getBlock({
        x: Math.floor(p.x), y: Math.floor(p.y), z: Math.floor(p.z),
      });
      if (b && !b.isAir && !b.isLiquid) return true;
    }
  } catch (_) { }
  return false;
}

function eyeOf(entity) {
  try {
    const l = entity.location;
    return { x: l.x, y: l.y + 0.9, z: l.z };
  } catch (_) { return null; }
}

/** 前方の円錐。視線からの角度と距離で絞る。 */
export function inCone(owner, origin, dir, reach, halfAngleDeg, seeThrough = false) {
  const cosLimit = Math.cos((halfAngleDeg * Math.PI) / 180);
  const f = normalise(dir);
  const out = [];
  for (const e of candidates(owner.dimension, origin, reach + 2)) {
    if (!valid(e, owner)) continue;
    const at = eyeOf(e);
    if (!at) continue;
    const to = { x: at.x - origin.x, y: at.y - origin.y, z: at.z - origin.z };
    const d = Math.hypot(to.x, to.y, to.z);
    if (d > reach) continue;
    if (d > 0.4 && dot(normalise(to), f) < cosLimit) continue;
    if (!seeThrough && blocked(owner.dimension, origin, at)) continue;
    out.push(e);
  }
  return out;
}

/** 通過した軌道。伸びる拳は「通った線の周り」で当たる。 */
export function alongRay(owner, origin, dir, reach, radius) {
  const f = normalise(dir);
  const out = [];
  for (const e of candidates(owner.dimension, forward(origin, f, reach / 2), reach)) {
    if (!valid(e, owner)) continue;
    const at = eyeOf(e);
    if (!at) continue;
    const to = { x: at.x - origin.x, y: at.y - origin.y, z: at.z - origin.z };
    const along = dot(to, f);
    if (along < -0.5 || along > reach) continue;
    const perp = Math.hypot(to.x - f.x * along, to.y - f.y * along, to.z - f.z * along);
    if (perp > radius) continue;
    if (blocked(owner.dimension, origin, at)) continue;
    out.push(e);
  }
  return out;
}

/** 着弾地点の周囲。叩きつけ・区域技はここ。 */
export function aroundPoint(owner, centre, radius, seeThrough = false) {
  const out = [];
  for (const e of candidates(owner.dimension, centre, radius + 1)) {
    if (!valid(e, owner)) continue;
    const at = eyeOf(e);
    if (!at) continue;
    if (distance(at, centre) > radius) continue;
    if (!seeThrough && blocked(owner.dimension, centre, at)) continue;
    out.push(e);
  }
  return out;
}

/** 全方位。宣言した技だけが使う（企画書 §09 当たり判定の方針）。 */
export function allAround(owner, radius) {
  const centre = eyeOf(owner);
  if (!centre) return [];
  return aroundPoint(owner, centre, radius);
}

/** 視線の先で最初に何かに当たる地点。着弾演出の位置に使う。 */
export function impactPoint(owner, origin, dir, reach) {
  const f = normalise(dir);
  const hits = alongRay(owner, origin, f, reach, 1.4);
  if (hits.length) {
    let best = hits[0];
    let bestD = Infinity;
    for (const e of hits) {
      const at = eyeOf(e);
      if (!at) continue;
      const d = distance(origin, at);
      if (d < bestD) { bestD = d; best = e; }
    }
    const at = eyeOf(best);
    if (at) return at;
  }
  try {
    const r = owner.dimension.getBlockFromRay(origin, f, { maxDistance: reach });
    if (r?.block) {
      const l = r.block.location;
      return { x: l.x + 0.5, y: l.y + 0.5, z: l.z + 0.5 };
    }
  } catch (_) { }
  return forward(origin, f, reach);
}

/** 足元の地面。叩きつけ系の原点。 */
export function groundUnder(entity, maxDrop = 6) {
  const l = entity.location;
  try {
    for (let i = 0; i <= maxDrop; i++) {
      const b = entity.dimension.getBlock({
        x: Math.floor(l.x), y: Math.floor(l.y) - i, z: Math.floor(l.z),
      });
      if (b && !b.isAir) return { x: l.x, y: Math.floor(l.y) - i + 1.05, z: l.z };
    }
  } catch (_) { }
  return { x: l.x, y: l.y + 0.05, z: l.z };
}

// ---------------------------------------------------------------------------
//  ダメージとノックバック
// ---------------------------------------------------------------------------
export function strike(owner, entity, amount, kbH, kbV, fireTicks = 0) {
  try {
    entity.applyDamage(Math.max(1, Math.round(amount)),
                       { cause: "entityAttack", damagingEntity: owner });
  } catch (_) {
    try { entity.applyDamage(Math.max(1, Math.round(amount))); } catch (__) { return false; }
  }
  if (kbH || kbV) {
    try {
      const from = owner.location;
      const to = entity.location;
      const dx = to.x - from.x;
      const dz = to.z - from.z;
      const l = Math.hypot(dx, dz) || 1;
      knockback(entity, dx / l, dz / l, kbH, kbV);
    } catch (_) { }
  }
  if (fireTicks > 0) {
    try { entity.setOnFire(Math.round(fireTicks / 20), true); } catch (_) { }
  }
  return true;
}

/** 上へ跳ね上げる（地面のゴム化）。水平成分を持たせない。 */
export function bounce(entity, power) {
  try { knockback(entity, 0, 0, 0, power); } catch (_) { }
}

export function stats() {
  return { openActions: actions.size };
}
