// 演出まわり / effect helpers: particles, sound, camera shake, hit detection
import { system } from "@minecraft/server";
import { hasFamily, distance, forward } from "./util.js";

export function fx(dimension, id, location) {
  try { dimension.spawnParticle(id, location); } catch (_) { }
}

export function fxRing(dimension, id, centre, radius, count, y = 0.2) {
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    fx(dimension, id, {
      x: centre.x + Math.cos(a) * radius,
      y: centre.y + y,
      z: centre.z + Math.sin(a) * radius,
    });
  }
}

export function fxLine(dimension, id, origin, dir, length, step = 1.2) {
  for (let d = 0; d <= length; d += step) {
    fx(dimension, id, forward(origin, dir, d));
  }
}

export function fxScatter(dimension, id, centre, count, spread = 1.0) {
  for (let i = 0; i < count; i++) {
    fx(dimension, id, {
      x: centre.x + (Math.random() - 0.5) * spread * 2,
      y: centre.y + Math.random() * spread,
      z: centre.z + (Math.random() - 0.5) * spread * 2,
    });
  }
}

// ---------------------------------------------------------------------------
//  形のある演出
//  技ごとの見た目を変えるには、同じ粒でも「どう並べるか」を変えるのが一番効く。
//  以下は視線から右手系の基底を作って、その上に弧・螺旋・柱・扇・幕を描く。
// ---------------------------------------------------------------------------
function basis(dir) {
  const len = Math.hypot(dir.x, dir.y, dir.z) || 1;
  const f = { x: dir.x / len, y: dir.y / len, z: dir.z / len };
  // 視線がほぼ真上・真下でも破綻しないよう、参照軸を選び直す
  const up = Math.abs(f.y) > 0.94 ? { x: 0, y: 0, z: 1 } : { x: 0, y: 1, z: 0 };
  let r = {
    x: f.y * up.z - f.z * up.y,
    y: f.z * up.x - f.x * up.z,
    z: f.x * up.y - f.y * up.x,
  };
  const rl = Math.hypot(r.x, r.y, r.z) || 1;
  r = { x: r.x / rl, y: r.y / rl, z: r.z / rl };
  const u = {
    x: r.y * f.z - r.z * f.y,
    y: r.z * f.x - r.x * f.z,
    z: r.x * f.y - r.y * f.x,
  };
  return { f, r, u };
}

function at(origin, b, a, bb, c) {
  return {
    x: origin.x + b.f.x * a + b.r.x * bb + b.u.x * c,
    y: origin.y + b.f.y * a + b.r.y * bb + b.u.y * c,
    z: origin.z + b.f.z * a + b.r.z * bb + b.u.z * c,
  };
}

/** 薙ぎ払いの弧。視線を中心に sweep 度ぶん、半径 radius で並べる。 */
export function fxArc(dimension, id, origin, dir, radius, sweepDeg = 150,
                      steps = 9, tilt = 0) {
  const b = basis(dir);
  const half = (sweepDeg * Math.PI) / 360;
  for (let i = 0; i < steps; i++) {
    const a = -half + (i / Math.max(1, steps - 1)) * half * 2;
    fx(dimension, id, at(origin, b, Math.cos(a) * radius,
                         Math.sin(a) * radius, tilt));
  }
}

/** 螺旋。回天のような回転系に。 */
export function fxSpiral(dimension, id, origin, dir, length, turns = 2,
                         steps = 16, radius = 1.1) {
  const b = basis(dir);
  for (let i = 0; i < steps; i++) {
    const t = i / Math.max(1, steps - 1);
    const a = t * Math.PI * 2 * turns;
    fx(dimension, id, at(origin, b, t * length,
                         Math.cos(a) * radius, Math.sin(a) * radius));
  }
}

/** 垂直の柱。落雷や噴出に。 */
export function fxColumn(dimension, id, base, height, steps = 8, jitter = 0.25) {
  for (let i = 0; i < steps; i++) {
    const t = i / Math.max(1, steps - 1);
    fx(dimension, id, {
      x: base.x + (Math.random() - 0.5) * jitter * 2,
      y: base.y + t * height,
      z: base.z + (Math.random() - 0.5) * jitter * 2,
    });
  }
}

/** 前方に広がる扇。散弾・炎雨のばら撒きに。 */
export function fxCone(dimension, id, origin, dir, length, spread = 0.5,
                       count = 12) {
  const b = basis(dir);
  for (let i = 0; i < count; i++) {
    const d = (0.25 + Math.random() * 0.75) * length;
    const w = (Math.random() - 0.5) * 2 * spread * d;
    const h = (Math.random() - 0.5) * 2 * spread * d;
    fx(dimension, id, at(origin, b, d, w, h));
  }
}

/** 正面に立てる幕。斬幕砲火のような面の攻撃に。 */
export function fxWall(dimension, id, origin, dir, distance, width, height,
                       cols = 5, rows = 3) {
  const b = basis(dir);
  for (let c = 0; c < cols; c++) {
    const w = (c / Math.max(1, cols - 1) - 0.5) * width;
    for (let r = 0; r < rows; r++) {
      const hgt = (r / Math.max(1, rows - 1) - 0.5) * height;
      fx(dimension, id, at(origin, b, distance, w, hgt));
    }
  }
}

/** 何段かに分けて演出を出す。[[tick, fn], ...] */
export function sequence(steps) {
  for (const [ticks, fn] of steps) {
    if (!ticks) { try { fn(); } catch (_) { } continue; }
    later(ticks, () => { try { fn(); } catch (_) { } });
  }
}

/** 動いている相手／自分に貼りつく尾。 */
export function trail(entity, id, ticks = 8, every = 2, yOff = 1.0) {
  for (let i = 0; i < ticks; i += every) {
    later(i, () => {
      try {
        fx(entity.dimension, id,
           { x: entity.location.x, y: entity.location.y + yOff, z: entity.location.z });
      } catch (_) { }
    });
  }
}

export function sound(dimension, id, location, opts) {
  try { dimension.playSound(id, location, opts); } catch (_) { }
}

/** 画面を揺らす — the single biggest contributor to weight on screen. */
export function shake(player, intensity = 0.2, seconds = 0.3, type = "positional") {
  try {
    player.runCommand(
      `camerashake add @s ${intensity.toFixed(2)} ${seconds.toFixed(2)} ${type}`);
  } catch (_) { }
}

export function shakeNearby(dimension, centre, radius, intensity, seconds) {
  let players = [];
  try {
    players = dimension.getEntities({
      location: centre, maxDistance: radius, type: "minecraft:player",
    });
  } catch (_) { return; }
  for (const p of players) {
    const d = distance(p.location, centre);
    const falloff = Math.max(0.05, intensity * (1 - d / radius));
    shake(p, falloff, seconds);
  }
}

/** Everything worth hitting near `entity`, excluding the attacker and allies. */
export function targetsNear(entity, radius, includeAllies = false) {
  try {
    return entity.dimension.getEntities({
      location: entity.location, maxDistance: radius,
      excludeTypes: ["minecraft:item", "minecraft:xp_orb", "minecraft:arrow"],
    }).filter((e) => e.id !== entity.id &&
      (includeAllies || !hasFamily(e, "defense_force")) &&
      e.typeId !== "minecraft:player");
  } catch (_) { return []; }
}

/** Cone in front of the attacker. `dot` of 1 is dead ahead, -1 is all round. */
export function cone(attacker, radius, dot) {
  const dir = attacker.getViewDirection();
  const from = attacker.location;
  const out = [];
  for (const target of targetsNear(attacker, radius)) {
    const to = {
      x: target.location.x - from.x,
      y: target.location.y + 0.6 - (from.y + 1.0),
      z: target.location.z - from.z,
    };
    const len = Math.hypot(to.x, to.y, to.z) || 1;
    if ((to.x * dir.x + to.y * dir.y + to.z * dir.z) / len < dot) continue;
    out.push({ entity: target, dx: to.x / len, dy: to.y / len, dz: to.z / len });
  }
  return out;
}

/** A pierce ray: everything within `width` of the line of sight. */
export function ray(attacker, length, width) {
  const dir = attacker.getViewDirection();
  const eye = attacker.getHeadLocation();
  const out = [];
  for (const target of targetsNear(attacker, length + 2)) {
    const to = {
      x: target.location.x - eye.x,
      y: target.location.y + 0.8 - eye.y,
      z: target.location.z - eye.z,
    };
    const along = to.x * dir.x + to.y * dir.y + to.z * dir.z;
    if (along < 0 || along > length) continue;
    const perp = Math.hypot(to.x - dir.x * along, to.y - dir.y * along,
                            to.z - dir.z * along);
    if (perp > width) continue;
    out.push({ entity: target, along });
  }
  return out.sort((a, b) => a.along - b.along);
}

export function hit(attacker, target, damage) {
  try {
    target.applyDamage(Math.max(1, Math.round(damage)),
                       { cause: "entityAttack", damagingEntity: attacker });
    return true;
  } catch (_) { return false; }
}

/** Kaiju bleed blue - spawn it wherever we land a hit. */
export function bleed(target) {
  if (!hasFamily(target, "kaiju")) return;
  fxScatter(target.dimension, "kaiju8:kaiju_blood",
            { x: target.location.x, y: target.location.y + 1.0, z: target.location.z },
            3, 0.5);
}

export function later(ticks, fn) {
  try { system.runTimeout(fn, ticks); } catch (_) { }
}
