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
