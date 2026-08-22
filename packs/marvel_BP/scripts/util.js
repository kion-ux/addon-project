// 小道具 / small shared helpers
import { world, system } from "@minecraft/server";

export const NSP = "marvel";

/** 翻訳可能なテキスト。表示は必ずこれを通す（日本語/英語の切替をクライアントに任せる）。 */
export function tr(key, ...args) {
  const node = { translate: key.startsWith(NSP) ? key : `${NSP}.${key}` };
  if (args.length) node.with = args.map(String);
  return { rawtext: [node] };
}

export function raw(...parts) {
  return {
    rawtext: parts.map((p) => (typeof p === "string" ? { text: p } : (p.rawtext ? p.rawtext[0] : p))),
  };
}

export function tell(player, message) {
  try { player.sendMessage(message); } catch (_) { }
}

export function actionbar(player, message) {
  try { player.onScreenDisplay.setActionBar(message); } catch (_) { }
}

export function title(player, main, sub, fade = 6, stay = 34, out = 16) {
  try {
    player.onScreenDisplay.setTitle(main, {
      fadeInDuration: fade, stayDuration: stay, fadeOutDuration: out,
      subtitle: sub,
    });
  } catch (_) { }
}

export function allPlayers() {
  try { return world.getAllPlayers(); } catch (_) { return []; }
}

export function num(entity, key, fallback = 0) {
  try {
    const v = entity.getDynamicProperty(key);
    return typeof v === "number" ? v : fallback;
  } catch (_) { return fallback; }
}

export function str(entity, key, fallback = "") {
  try {
    const v = entity.getDynamicProperty(key);
    return typeof v === "string" ? v : fallback;
  } catch (_) { return fallback; }
}

export function bool(entity, key, fallback = false) {
  try {
    const v = entity.getDynamicProperty(key);
    return typeof v === "boolean" ? v : fallback;
  } catch (_) { return fallback; }
}

export function setProp(entity, key, value) {
  try { entity.setDynamicProperty(key, value); } catch (_) { }
}

/** 0..1 を目盛りバーにする。HUD の読みやすさはここで決まる。 */
export function bar(ratio, width = 12, filled = "|", empty = "'") {
  const n = Math.max(0, Math.min(width, Math.round(ratio * width)));
  return filled.repeat(n) + empty.repeat(width - n);
}

export function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

export function add(a, b) {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

export function sub(a, b) {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

export function scale(v, k) {
  return { x: v.x * k, y: v.y * k, z: v.z * k };
}

export function length(v) {
  return Math.hypot(v.x, v.y, v.z);
}

export function normalise(v) {
  const l = length(v) || 1;
  return { x: v.x / l, y: v.y / l, z: v.z / l };
}

export function forward(origin, dir, d) {
  return { x: origin.x + dir.x * d, y: origin.y + dir.y * d, z: origin.z + dir.z * d };
}

export function hasFamily(entity, family) {
  try {
    return entity.matches({ families: [family] });
  } catch (_) {
    try {
      return entity.getComponent("minecraft:type_family")?.hasTypeFamily(family) === true;
    } catch (_e) { return false; }
  }
}

export function isPlayer(entity) {
  return entity?.typeId === "minecraft:player";
}

export function alive(entity) {
  try { return entity?.isValid?.() !== false && entity?.dimension !== undefined; }
  catch (_) { return false; }
}

/** 同じ処理を毎 tick 走らせないための、ごく軽いクールダウン表。 */
export class Cooldowns {
  constructor() { this.map = new Map(); }
  ready(id, key) {
    const until = this.map.get(`${id}/${key}`) ?? 0;
    return system.currentTick >= until;
  }
  remaining(id, key) {
    return Math.max(0, (this.map.get(`${id}/${key}`) ?? 0) - system.currentTick);
  }
  set(id, key, ticks) {
    this.map.set(`${id}/${key}`, system.currentTick + ticks);
  }
  clear(id) {
    for (const k of [...this.map.keys()]) {
      if (k.startsWith(`${id}/`)) this.map.delete(k);
    }
  }
}

export function safe(fn) {
  try { return fn(); } catch (_) { return undefined; }
}
