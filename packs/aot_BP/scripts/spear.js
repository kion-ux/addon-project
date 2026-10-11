// ===========================================================================
//  雷槍と信煙弾
//
//  雷槍: 視線の方向へ撃ち出し（毎 tick 2.4m 進む）、当たった所に突き刺さる。
//        1.2 秒で起爆。うなじの近くに刺されば、鎧のない巨人なら一撃で倒れる。
//        それ以外の場所でも最大体力の 45% を吹き飛ばし、しばらく再生できなくする。
//  信煙弾: 上空へ昇る色付きの煙柱を残す（緑・赤・黒・黄。スニーク＋使用で色を変える）。
// ===========================================================================
import { system } from "@minecraft/server";
import { FLARE_COLORS, ITEM, PROP } from "./config.js";
import { P, shakeAround, sound } from "./fx.js";
import { frame, heavyWound, isDying, isTitan, napeKill, rayTitans, typeOf } from "./titans.js";
import {
  add, consume, damage, dist, eye, health, isCreative, now, numProp, rand, rt, setProp, sub,
  valid, viewDir, yawFrame,
} from "./util.js";

const FLY = [];          // 飛んでいる雷槍
const STUCK = [];        // 刺さって導火中の雷槍
const STEP = 2.4;
const FUSE = 24;

const lastShot = new Map();

export function fireSpear(p) {
  if (now() - (lastShot.get(p.id) ?? -99) < 10) return;     // 押しっぱなしの連射を抑える
  if (!isCreative(p) && !consume(p, ITEM.spear, 1)) return;
  lastShot.set(p.id, now());
  const dir = viewDir(p);
  const at = add(eye(p), dir, 0.9);
  FLY.push({ owner: p, dim: p.dimension, pos: at, dir, born: now() });
  sound(p.dimension, "aot.spear_fire", p.location, rand(0.95, 1.05), 1.0);
  P(p.dimension, "flash", at, { size: 0.8 });
}

function stick(s, hitPos, entity) {
  const rec = { owner: s.owner, dim: s.dim, at: hitPos, entity, until: now() + FUSE };
  if (entity) {
    const { f, r } = yawFrame(entity);
    const rel = sub(hitPos, entity.location);
    rec.local = { f: rel.x * f.x + rel.z * f.z, r: rel.x * r.x + rel.z * r.z, y: rel.y };
  }
  STUCK.push(rec);
  sound(s.dim, "aot.hook", hitPos, 1.2, 1.0);
  sound(s.dim, "aot.fuse", hitPos, 1.0, 1.0);
}

function stuckPos(rec) {
  if (!rec.entity) return rec.at;
  if (!valid(rec.entity)) return rec.at;
  const { f, r } = yawFrame(rec.entity);
  const L = rec.entity.location;
  rec.at = add(add(add(L, f, rec.local.f), r, rec.local.r), { x: 0, y: rec.local.y, z: 0 });
  return rec.at;
}

function explode(rec) {
  const at = stuckPos(rec);
  const dim = rec.dim;
  P(dim, "flash", at, { size: 5, life: 0.25 });
  P(dim, "fire", at, { count: 24, spread: 1.2, speed: 5, size: 1.4 });
  P(dim, "smoke", at, { count: 6, spread: 1.4, size: 2.4, life: 3.5, rise: 0.8, color: [0.22, 0.2, 0.2] });
  P(dim, "debris", at, { count: 14, speed: 8 });
  P(dim, "ring", at, { size: 6, life: 0.35 });
  sound(dim, "aot.boom", at, rand(0.9, 1.05), 2.2);
  shakeAround(dim, at, 28, 0.6, 0.6);
  try {
    dim.createExplosion(at, 2.2, { breaksBlocks: false, causesFire: false, source: rec.owner });
  } catch (_) { }
  const t = rec.entity;
  if (t && valid(t) && isTitan(t) && !isDying(t)) {
    const F = frame(t);
    if (dist(at, F.nape) <= F.radius + 1.6) {
      napeKill(t, valid(rec.owner) ? rec.owner : undefined);
    } else {
      const h = health(t);
      heavyWound(t, 140);
      damage(t, (h?.effectiveMax ?? typeOf(t).hp) * 0.45, valid(rec.owner) ? rec.owner : undefined);
    }
  } else if (t && valid(t)) {
    damage(t, 20, valid(rec.owner) ? rec.owner : undefined);
  }
}

export function tickSpears() {
  for (let i = FLY.length - 1; i >= 0; i--) {
    const s = FLY[i];
    const age = now() - s.born;
    if (age > 40) { FLY.splice(i, 1); continue; }
    // 重力で少しずつ落ちる
    s.dir = { x: s.dir.x, y: s.dir.y - 0.012, z: s.dir.z };
    const l = Math.hypot(s.dir.x, s.dir.y, s.dir.z);
    const dir = { x: s.dir.x / l, y: s.dir.y / l, z: s.dir.z / l };
    let blockHit = null;
    try {
      const b = s.dim.getBlockFromRay(s.pos, dir, { maxDistance: STEP, includeLiquidBlocks: false,
                                                     includePassableBlocks: false });
      if (b) blockHit = add(b.block.location, b.faceLocation);
    } catch (_) { }
    const tHit = rayTitans(s.dim, s.pos, dir, STEP);
    let other = null;
    if (!tHit) {
      try {
        const es = s.dim.getEntitiesFromRay(s.pos, dir, { maxDistance: STEP });
        other = es.find((h) => h.entity.id !== s.owner?.id && h.entity.typeId !== "minecraft:item");
      } catch (_) { }
    }
    if (tHit && (!blockHit || tHit.s <= dist(s.pos, blockHit))) {
      FLY.splice(i, 1);
      stick(s, tHit.at, tHit.entity);
      continue;
    }
    if (other && (!blockHit || other.distance <= dist(s.pos, blockHit))) {
      FLY.splice(i, 1);
      stick(s, add(s.pos, dir, other.distance), other.entity);
      continue;
    }
    if (blockHit) {
      FLY.splice(i, 1);
      stick(s, blockHit, null);
      continue;
    }
    const next = add(s.pos, dir, STEP);
    P(s.dim, "glow", next, { size: 0.5, color: [1.0, 0.75, 0.4], life: 0.15 });
    P(s.dim, "smoke", s.pos, { count: 1, size: 0.4, life: 0.8, rise: 0.2, color: [0.6, 0.6, 0.62] });
    s.pos = next;
  }
  for (let i = STUCK.length - 1; i >= 0; i--) {
    const rec = STUCK[i];
    const at = stuckPos(rec);
    if (now() % 2 === 0) P(rec.dim, "spark", at, { count: 4, speed: 3, size: 0.8 });
    if (now() >= rec.until) {
      STUCK.splice(i, 1);
      explode(rec);
    }
  }
}

// ---------------------------------------------------------------------------
//  信煙弾
// ---------------------------------------------------------------------------
export function cycleFlare(p) {
  const i = (numProp(p, PROP.flare, 0) + 1) % FLARE_COLORS.length;
  setProp(p, PROP.flare, i);
  try { p.onScreenDisplay.setActionBar(rt("§f", { t: FLARE_COLORS[i].key })); } catch (_) { }
  sound(p.dimension, "random.click", p.location, 1.3, 0.6);
}

export function fireFlare(p) {
  const col = FLARE_COLORS[numProp(p, PROP.flare, 0) % FLARE_COLORS.length];
  const dim = p.dimension;
  const d = viewDir(p);
  const dir = { x: d.x * 0.25, y: 1, z: d.z * 0.25 };
  const start = add(eye(p), { x: 0, y: 0.3, z: 0 });
  sound(dim, "aot.flare", p.location, rand(0.95, 1.05), 2.0);
  P(dim, "flash", start, { size: 0.8, color: col.c });
  // 0.05 秒ごとに 1.2m ずつ昇りながら煙を残す
  for (let k = 0; k < 26; k++) {
    system.runTimeout(() => {
      const at = add(start, dir, k * 1.2);
      P(dim, "smoke", at, { count: 2, size: 1.3, life: 9, rise: 0.15, spread: 0.2, color: col.c });
      P(dim, "glow", at, { size: 0.6, life: 0.2, color: col.c });
    }, k + 1);
  }
  try {
    for (const q of dim.getPlayers({ location: p.location, maxDistance: 160 })) {
      if (q.id === p.id) continue;
      q.sendMessage(rt("§7", { t: "aot.msg.flare_seen", w: [p.name] }, " ", { t: col.key }));
    }
  } catch (_) { }
  return col;
}

export function spearCount() { return FLY.length + STUCK.length; }
