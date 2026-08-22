import { world, system } from "@minecraft/server";

export function tr(key, ...args) {
  return { rawtext: [{ translate: key, with: args.map(String) }] };
}

export function actionbar(player, msg) {
  try { player.onScreenDisplay.setActionBar(msg); } catch (_) { }
}

export function tell(target, msg) {
  try { target.sendMessage(msg); } catch (_) { }
}

export function playSound(dimension, id, location, opts) {
  try { dimension.playSound(id, location, opts); } catch (_) { }
}

export function particle(dimension, id, location) {
  try { dimension.spawnParticle(id, location); } catch (_) { }
}

export function burst(dimension, id, location, count, spread = 1.2) {
  for (let i = 0; i < count; i++) {
    particle(dimension, id, {
      x: location.x + (Math.random() - 0.5) * spread * 2,
      y: location.y + Math.random() * spread,
      z: location.z + (Math.random() - 0.5) * spread * 2,
    });
  }
}

/** applyKnockback changed signature between script API 1.x and 2.x. */
export function knockback(entity, dx, dz, horizontal, vertical) {
  try {
    entity.applyKnockback(dx, dz, horizontal, vertical);
  } catch (_) {
    try { entity.applyKnockback({ x: dx, z: dz }, horizontal, vertical); } catch (__) { }
  }
}

export function hasFamily(entity, family) {
  try {
    const c = entity.getComponent("minecraft:type_family");
    if (c) return c.hasTypeFamily(family);
  } catch (_) { }
  return false;
}

export function health(entity) {
  try {
    const h = entity.getComponent("minecraft:health");
    if (!h) return null;
    return { now: Math.max(0, Math.round(h.currentValue)), max: Math.round(h.effectiveMax) };
  } catch (_) { return null; }
}

export function num(holder, key, fallback = 0) {
  const v = holder.getDynamicProperty(key);
  return typeof v === "number" ? v : fallback;
}

export function bool(holder, key, fallback = false) {
  const v = holder.getDynamicProperty(key);
  return typeof v === "boolean" ? v : fallback;
}

export function bar(ratio, width = 10, full = "▮", empty = "▯") {
  const filled = Math.max(0, Math.min(width, Math.round(ratio * width)));
  return full.repeat(filled) + empty.repeat(width - filled);
}

export function forward(origin, dir, distance) {
  return {
    x: origin.x + dir.x * distance,
    y: origin.y + dir.y * distance,
    z: origin.z + dir.z * distance,
  };
}

export function distance(a, b) {
  const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

const cooldowns = new Map();

export function onCooldown(id, key) {
  const map = cooldowns.get(id);
  if (!map) return false;
  const until = map.get(key) ?? 0;
  return system.currentTick < until;
}

export function setCooldown(id, key, ticks) {
  let map = cooldowns.get(id);
  if (!map) { map = new Map(); cooldowns.set(id, map); }
  map.set(key, system.currentTick + ticks);
}

export function allPlayers() {
  try { return world.getAllPlayers(); } catch (_) { return []; }
}
