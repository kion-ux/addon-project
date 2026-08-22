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

export function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}

export function lerp(a, b, t) {
  return a + (b - a) * t;
}

/** ブロック座標の鍵。磁化ペイントと剥がしたブロックの台帳が同じ書式を使う。 */
export function posKey(dimensionId, pos) {
  return `${dimensionId}|${Math.floor(pos.x)},${Math.floor(pos.y)},${Math.floor(pos.z)}`;
}

export function parsePosKey(key) {
  const bar = key.indexOf("|");
  if (bar < 0) return undefined;
  const [x, y, z] = key.slice(bar + 1).split(",").map(Number);
  if ([x, y, z].some((n) => !Number.isFinite(n))) return undefined;
  return { dimensionId: key.slice(0, bar), x, y, z };
}

/**
 * 動的プロパティに JSON を出し入れする。
 *
 * 文字列の動的プロパティは 32,767 バイトが上限で、超えると **例外ではなく
 * 保存の失敗**として黙って消えることがある。書く側で必ず長さを見て、
 * 入らないなら捨てる（呼び元は false を見て件数を減らせる）。
 * 余裕を見て 30,000 で止める。
 */
export const JSON_PROP_LIMIT = 30000;

export function readJson(holder, key, fallback) {
  const text = safe(() => holder.getDynamicProperty(key));
  if (typeof text !== "string" || !text) return fallback;
  try {
    const value = JSON.parse(text);
    return value ?? fallback;
  } catch (_) { return fallback; }
}

export function writeJson(holder, key, value) {
  let text;
  try { text = JSON.stringify(value); } catch (_) { return false; }
  if (text.length > JSON_PROP_LIMIT) return false;
  return safe(() => { holder.setDynamicProperty(key, text); return true; }) === true;
}

/** 段階を画面に出すときの見出し。言語に依らないのでどの翻訳でも読める。 */
export function roman(n) {
  return ["", "I", "II", "III", "IV", "V"][n] ?? String(n);
}
