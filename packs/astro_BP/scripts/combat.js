// ===========================================================================
//  当たり判定・ダメージ・ゲージ・同調率・ダメージ表示
//
//  連続ヒットの扱い: Minecraft は被弾後およそ 10 tick 無敵になるので、技の細かい多段ヒットを
//  そのまま applyDamage すると大半が消える。そこで「通らなかった分」を対象ごとに貯め、
//  無敵が切れた瞬間にまとめて通す（ダメージバンク。hyperdim と同じ）。
//  見た目の当たり（火花・数字・音）は毎回その場で出す。
//
//  hit() の第 1 引数は ctx（技の文脈）でもプレイヤーでもよい。base は「素のダメージ」で、
//  同調率 Lv・惑星の補正・パッシブの倍率は hit() の中で掛かる（o.raw で掛けない）。
// ===========================================================================
import { world } from "@minecraft/server";
import { COMMON, PLANETS } from "./data.js";
import {
  S, level, addXpRaw, setNovaRaw, novaLocked, addEnergy, addRecord, maxRecord, settings, formOf,
} from "./state.js";
import { P, burst, sound, white, title, glyph, emblem, ring } from "./fx.js";
import {
  valid, health, knock, dist, norm, sub, chest, rand, now, effect, isPlayer, gameMode, BUS, heal,
  dirTo, report,
} from "./util.js";

/** 標的にしないエンティティ。 */
export const IGNORE_TYPES = new Set([
  "astro:dmg_text", "minecraft:item", "minecraft:xp_orb", "minecraft:arrow", "minecraft:armor_stand",
  "minecraft:npc", "minecraft:painting", "minecraft:leash_knot", "minecraft:ender_crystal",
  "astro:void_bolt", "minecraft:fishing_hook", "minecraft:tripod_camera", "minecraft:agent",
]);

// ---------------------------------------------------------------------------
//  標的
// ---------------------------------------------------------------------------
/** attacker から見て e を攻撃してよいか（自分・ペット・クリエイティブ等を除く）。 */
export function isTarget(attacker, e) {
  if (!valid(e) || (attacker && e.id === attacker.id)) return false;
  let type;
  try { type = e.typeId; } catch (_) { return false; }
  if (IGNORE_TYPES.has(type)) return false;
  const h = health(e);
  if (!h) return false;
  try { if (h.currentValue <= 0) return false; } catch (_) { return false; }
  if (type === "minecraft:player") {
    const gm = gameMode(e);
    if (gm === "creative" || gm === "spectator") return false;
  }
  try {
    const tame = e.getComponent("minecraft:tameable");
    if (tame?.isTamed && attacker && tame.tamedToPlayerId === attacker.id) return false;
  } catch (_) { }
  return true;
}

// 同じ tick の同じ問い合わせはまとめる（getEntities の嵐を避ける）
let qTick = -1;
const qCache = new Map();
let qCount = 0;

/** dim の loc から radius m 以内のエンティティ（tick 内でキャッシュ）。 */
export function entitiesNear(dim, loc, radius) {
  const t = now();
  if (t !== qTick) { qTick = t; qCache.clear(); qCount = 0; }
  const key = `${dim.id}|${Math.round(loc.x * 2)}|${Math.round(loc.y * 2)}|${Math.round(loc.z * 2)}|${Math.round(radius * 4)}`;
  let list = qCache.get(key);
  if (!list) {
    list = [];
    if (qCount++ < 400) {
      try { list = dim.getEntities({ location: loc, maxDistance: radius }); } catch (_) { list = []; }
    }
    qCache.set(key, list);
  }
  return list;
}

/** loc から radius m 以内の攻撃してよい相手。src は ctx かプレイヤー。 */
export function enemiesNear(src, loc, radius, dim) {
  const p = src?.p ?? src;
  const d = dim ?? src?.dim ?? p?.dimension;
  if (!d || !loc || !Number.isFinite(radius)) return [];
  return entitiesNear(d, loc, radius).filter((e) => isTarget(p, e));
}

/** origin から dir 方向の扇形（range m、半角 deg 度）。 */
export function enemiesInCone(src, origin, dir, range, deg) {
  const cos = Math.cos(deg * Math.PI / 180);
  return enemiesNear(src, origin, range + 1.5).filter((e) => {
    const to = sub(chest(e), origin);
    const d = Math.hypot(to.x, to.y, to.z);
    if (d < 1.2) return true;
    return (to.x * dir.x + to.y * dir.y + to.z * dir.z) / d >= cos && d <= range + 0.6;
  });
}

/** a→b の線分から width m 以内。 */
export function enemiesOnLine(src, a, b, width) {
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
  const half = dist(a, b) / 2 + width + 1;
  const ab = sub(b, a);
  const L2 = ab.x * ab.x + ab.y * ab.y + ab.z * ab.z || 1;
  return enemiesNear(src, mid, half).filter((e) => {
    const c = chest(e);
    const ap = sub(c, a);
    const t = Math.max(0, Math.min(1, (ap.x * ab.x + ap.y * ab.y + ap.z * ab.z) / L2));
    const q = { x: a.x + ab.x * t, y: a.y + ab.y * t, z: a.z + ab.z * t };
    // 体の縦の広がり（足元〜頭）を許す
    const dy = Math.max(0, Math.abs(q.y - c.y) - 0.8);
    return Math.hypot(q.x - c.x, dy, q.z - c.z) <= width + 0.4;
  });
}

/** loc から radius 以内で一番近い相手（dir と deg を渡すとその扇形の中だけ）。 */
export function nearestEnemy(src, loc, radius, dir, deg = 180) {
  const list = deg >= 180 || !dir ? enemiesNear(src, loc, radius) : enemiesInCone(src, loc, dir, radius, deg);
  let best, bd = Infinity;
  for (const e of list) {
    const d = dist(e.location, loc);
    if (d < bd) { bd = d; best = e; }
  }
  return best;
}

// ---------------------------------------------------------------------------
//  ダメージ
// ---------------------------------------------------------------------------
const bank = new Map();   // targetId -> { e, attacker, pending, tries }
const crits = new Map();  // targetId -> 会心表示の期限 tick

/** 惑星の補正（ナノウェポンの攻撃力 8 を 1.0 として ±3%/点）。 */
export function planetMul(key) {
  const pl = PLANETS[key];
  return pl ? 1 + (pl.damage - 8) * 0.03 : 1;
}

let dmgMulHook = () => 1;
/** パッシブの与ダメージ倍率の差し込み口（passives.js が入れる）。 */
export function setDamageMulHook(fn) { dmgMulHook = fn; }

/** p が key の形態で出すダメージの倍率（同調率 Lv・惑星・パッシブ）。 */
export function damageMul(p, key = formOf(p)) {
  if (!key) return 1;
  let k = (1 + COMMON.sync_damage_per_level * (level(p, key) - 1)) * planetMul(key);
  try { k *= dmgMulHook(p, key) || 1; } catch (_) { }
  return k;
}

function rawDamage(attacker, target, amount) {
  if (!(amount > 0)) return true;
  try {
    return target.applyDamage(amount, { cause: "entityAttack", damagingEntity: attacker }) !== false;
  } catch (_) {
    try { return target.applyDamage(amount) !== false; } catch (__) { return false; }
  }
}

/**
 * 技の一撃。
 * @param src     ctx（技の文脈）かプレイヤー
 * @param target  当てる相手（isTarget で弾かれたら何もしない）
 * @param base    素のダメージ（同調率・惑星の補正はここで掛かる。o.raw で掛けない）
 * @param o       kb 水平ノックバック / up 上向き / dir ノックバック方向（既定 src→target）/
 *                color 当たりの色 / power 演出の規模（1 普通・2 大技）/ crit true か確率 0..1（1.5 倍）/
 *                quiet 演出なし / sound 当たりの音（既定 astro.hit / 大技 astro.hit_heavy）/
 *                nova 超新星ゲージの増加（既定: 技 2、通常攻撃 3）/ xp 同調率 XP（既定 2）/
 *                raw 倍率を掛けない / pull {x,y,z} へ引き寄せる（kb の代わり）
 * @returns 当たったら true
 */
export function hit(src, target, base, o = {}) {
  const ctx = src && src.p && src.kind ? src : null;
  const p = ctx ? ctx.p : src;
  if (!valid(p) || !isTarget(p, target)) return false;
  if (!Number.isFinite(base)) { report("combat.hit", new Error(`bad damage ${base}`)); return false; }
  const key = ctx?.key ?? (isPlayer(p) ? formOf(p) : null);
  let amount = Math.max(0, o.raw ? base : base * damageMul(p, key));
  const crit = o.crit === true || (typeof o.crit === "number" && Math.random() < o.crit);
  if (crit) amount *= 1.5;
  if (!rawDamage(p, target, amount)) {
    const b = bank.get(target.id) ?? { e: target, attacker: p, pending: 0, tries: 0 };
    b.pending = Math.min(b.pending + amount, 400);
    b.attacker = p;
    bank.set(target.id, b);
  }
  // ノックバック
  try {
    if (o.pull) {
      const d = sub(o.pull, target.location);
      const l = Math.hypot(d.x, d.z) || 1;
      knock(target, d.x / l, d.z / l, Math.min(o.kb ?? 0.6, l * 0.3), o.up ?? 0.05);
    } else if (o.kb || o.up) {
      const d = o.dir ?? dirTo(p.location, target.location);
      const l = Math.hypot(d.x, d.z) || 1;
      knock(target, d.x / l, d.z / l, o.kb ?? 0, o.up ?? 0);
    }
  } catch (_) { }
  if (!o.quiet) {
    const c = o.color ?? ctx?.c ?? [1, 1, 1];
    const at = chest(target);
    burst(target.dimension, at, c, o.power ?? 1);
    const snd = o.sound ?? ((o.power ?? 1) >= 1.6 ? "astro.hit_heavy" : "astro.hit");
    sound(target.dimension, snd, at, rand(0.9, 1.15), 0.9);
    if (crit) {
      sound(target.dimension, "astro.crit", at, rand(1.0, 1.2), 0.9);
      P(target.dimension, "star", at, { color: white(c, 0.4), count: 6, spread: 0.5, speed: 3 });
    }
  }
  if (crit) crits.set(target.id, now() + 30);
  if (isPlayer(p)) {
    maxRecord(p, "maxHit", amount);
    if (key) {
      const isMelee = !ctx || ctx.kind === "melee";
      let nv = o.nova ?? (isMelee ? COMMON.nova_on_hit : COMMON.nova_on_skill_hit);
      let xp = o.xp ?? COMMON.xp_on_hit;
      if (ctx) {
        // 一つの技で稼げる量には上限（多段・多数の敵で一気に満タンにならないように）
        const g = ctx.gain ?? (ctx.gain = { nova: 0, xp: 0 });
        nv = Math.max(0, Math.min(nv, (ctx.novaCap ?? 14) - g.nova));
        xp = Math.max(0, Math.min(xp, (ctx.xpCap ?? 12) - g.xp));
        g.nova += nv; g.xp += xp;
      }
      if (nv > 0) addNova(p, nv);
      if (xp > 0) addXp(p, key, xp);
    }
    BUS.emit("hit", p, target, amount, ctx);
  }
  return true;
}

/** 無敵切れを待っている分を流す（毎 tick）。 */
export function flushBank() {
  if (!bank.size) return;
  for (const [id, b] of bank) {
    if (!valid(b.e) || !valid(b.attacker)) { bank.delete(id); continue; }
    if (rawDamage(b.attacker, b.e, b.pending)) bank.delete(id);
    else if (++b.tries > 30) bank.delete(id);
  }
}

// ---------------------------------------------------------------------------
//  状態異常・移動のまとめ（planets/*.js から使う）
// ---------------------------------------------------------------------------
/** 足止め（strong で強い鈍化＋弱体化）。 */
export function freeze(e, ticks, strong = false) {
  effect(e, "slowness", ticks, strong ? 9 : 3);
  if (strong) effect(e, "weakness", ticks, 1);
}

/** e を to の方へ引き寄せる（strength は水平の強さ、近いほど弱く）。 */
export function pull(e, to, strength = 0.6, upv = 0.05) {
  if (!valid(e)) return;
  const d = sub(to, e.location);
  const l = Math.hypot(d.x, d.z);
  if (l < 0.4) return;
  knock(e, d.x / l, d.z / l, Math.min(strength, l * 0.35), upv);
}

/** 打ち上げる（kb と dir で横にも飛ばせる）。 */
export function launch(e, upv = 0.8, kb = 0, dir) {
  if (!valid(e)) return;
  const d = dir ?? { x: 0, z: 0 };
  const l = Math.hypot(d.x, d.z) || 1;
  knock(e, d.x / l, d.z / l, kb, upv);
}

/** 押し出す（from から離れる向き）。 */
export function push(e, from, kb = 1, upv = 0.2) {
  if (!valid(e)) return;
  const d = dirTo(from, e.location);
  knock(e, d.x, d.z, kb, upv);
}

/** 味方（自分と周りのプレイヤー、自分のペット）を数える／癒やす。 */
export function alliesNear(p, loc, radius) {
  const out = [];
  for (const e of entitiesNear(p.dimension, loc, radius)) {
    if (!valid(e)) continue;
    try {
      if (e.id === p.id || e.typeId === "minecraft:player") { out.push(e); continue; }
      const tame = e.getComponent("minecraft:tameable");
      if (tame?.isTamed && tame.tamedToPlayerId === p.id) out.push(e);
    } catch (_) { }
  }
  if (!out.some((e) => e.id === p.id)) out.push(p);
  return out;
}

export { heal };

// ---------------------------------------------------------------------------
//  ゲージ・XP・星力（演出つき）
// ---------------------------------------------------------------------------
/** 超新星ゲージを足す（必殺技の最中は溜まらない）。満タンになった瞬間に合図。 */
export function addNova(p, v) {
  if (!valid(p) || !isPlayer(p) || novaLocked(p)) return;
  setNova(p, S(p).nova + v);
}

export function setNova(p, v) {
  const before = S(p).nova;
  const after = setNovaRaw(p, v);
  if (before < COMMON.nova_max && after >= COMMON.nova_max && formOf(p)) {
    const pl = PLANETS[formOf(p)];
    sound(p.dimension, "astro.supernova", p.location, 1.6, 0.5);
    sound(p.dimension, "astro.alert", p.location, 1.4, 0.4);
    title(p, " ", `§r${glyph("icon.nova", "")}§r §6必殺 READY §r${glyph("icon.nova", "")}`, { fadeIn: 2, stay: 20, fadeOut: 6 });
    P(p.dimension, "ring", chest(p), { color: [1, 0.85, 0.3], size: 1.6, life: 0.4 });
    if (pl) P(p.dimension, "aura", p.location, { color: pl.color, size: 1.2, life: 0.6 });
  }
}

/** 同調率 XP を足す。Lv が上がったら演出（タイトル＋astro.sync_up）。 */
export function addXp(p, key, n) {
  const lv = addXpRaw(p, key, n);
  if (!lv || !valid(p)) return;
  const pl = PLANETS[key];
  try {
    const dim = p.dimension;
    sound(dim, "astro.sync_up", p.location, 1.0, 1.0);
    title(p, `§r${glyph(["emblemBig", key], pl.symbol)}`, `${pl.tc}${pl.form_ja} §f同調率 Lv${lv}`, { fadeIn: 4, stay: 40, fadeOut: 12 });
    emblem(dim, { ...p.location, y: p.location.y + 0.05 }, pl, { size: 3, life: 1.4 });
    ring(dim, "star", p.location, 1.2, 10, { color: white(pl.color, 0.4), count: 2, spread: 0.2, life: 1.0 }, 1.0);
    P(dim, "converge", chest(p), { color: pl.color, count: 20, spread: 2.4, life: 0.6 });
    p.sendMessage?.(`${pl.tc}${pl.form_ja}§r の同調率が §bLv${lv}§r に上がった（与ダメージ・最大星力・再使用短縮）`);
  } catch (_) { }
}

/** 撃破の処理（main の entityDie から）。星力 +5・XP +12・パッシブの onKill。 */
export function onKill(p, victim) {
  const key = formOf(p);
  if (!key) return;
  addEnergy(p, COMMON.energy_on_kill);
  addXp(p, key, COMMON.xp_on_kill);
  addRecord(p, "kills", 1, key);
  BUS.emit("kill", p, victim);
}

// ---------------------------------------------------------------------------
//  ダメージ表示（浮かび上がる数字: astro:dmg_text の nameTag）
// ---------------------------------------------------------------------------
const pops = [];
const MAX_POPS = 36;
export const DMG_TEXT = "astro:dmg_text";

/** entityHurt から: 実際に通ったダメージを出す（攻撃者の設定で OFF にできる）。 */
export function showDamage(target, amount, attacker) {
  if (!(amount >= 0.05)) return;
  if (attacker && isPlayer(attacker) && settings(attacker).dmg === false) return;
  const until = crits.get(target.id);
  const crit = until !== undefined && until >= now();
  if (crit) crits.delete(target.id);
  popNumber(target, amount, crit);
}

export function popNumber(target, amount, crit) {
  if (pops.length >= MAX_POPS) return;
  try {
    const l = target.location;
    const h = target.typeId === "minecraft:player" ? 2.1 : 1.8;
    const at = { x: l.x + rand(-0.5, 0.5), y: l.y + h + rand(0, 0.4), z: l.z + rand(-0.5, 0.5) };
    const e = target.dimension.spawnEntity(DMG_TEXT, at);
    const n = Math.round(amount * 10) / 10;
    e.nameTag = crit ? `§c${n}!` : (amount >= 10 ? `§6${n}` : `§e${n}`);
    pops.push({ e, t: 0, x: at.x, y: at.y, z: at.z, vx: rand(-0.04, 0.04), vz: rand(-0.04, 0.04) });
  } catch (_) { }
}

export function tickPops() {
  for (let i = pops.length - 1; i >= 0; i--) {
    const q = pops[i];
    q.t++;
    if (!valid(q.e) || q.t > 18) {
      try { q.e.remove(); } catch (_) { }
      pops.splice(i, 1);
      continue;
    }
    const rise = q.t < 6 ? 0.12 : 0.03;
    q.x += q.vx; q.z += q.vz; q.y += rise;
    try { q.e.teleport({ x: q.x, y: q.y, z: q.z }); } catch (_) { }
  }
}

/** 前回の残りのダメージ表示を掃除（起動時）。 */
export function sweepTexts() {
  for (const id of ["overworld", "nether", "the_end"]) {
    try {
      for (const e of world.getDimension(id).getEntities({ type: DMG_TEXT })) e.remove();
    } catch (_) { }
  }
}

export { norm, white };
