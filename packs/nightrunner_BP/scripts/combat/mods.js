// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 武器の改造（火炎・感電・出血・毒・UV・衝撃）
//
//  * 保存: ItemStack の動的プロパティ nr:mods（JSON {鍵: 段階 1..3}）と説明文（lore）。gore.js の
//    defaultMeleeHit も同じ nr:mods を読む。改造の枠はレア度の mod_slots、付けられる改造は武器の mods_allowed
//    と MODS の applies_to / only_dtypes。武器固有の改造（special.innate_mod）は保存せず、当たる時に足す。
//  * 付け方: applyMod(player, 鍵, 段階)。手に持った武器へ、MODS の tiers[].cost の材料を持ち物から払って付ける
//    （端末の「改造」画面 ui/terminal.js から呼ぶ。spec: 「端末の改造画面で手に持った武器へ材料を払って付ける」）。
//  * 当たった時: EV.HIT（applyHit の結果）を聞いて、確率（chance）で持続ダメージ（火・出血・毒は 10 tick ごとに
//    applyHit）・感電の連鎖・毒の霧と鈍足・UV の怯みと免疫の回復。ゴアに効く分（出血の gore_power_add、
//    衝撃の押し返し・骨折・よろめき）は gore.js が hit.mods から読む。UV の夜の種類への倍率は当てる前に
//    modDamageMult() で掛ける（melee / ranged / throwables）。
//  * 持続・連鎖の一撃には _mod: true を付け、改造の効果を重ねない。
// ===========================================================================
import { MODS, MOD_BY_KEY } from "../data/mods.js";
import { applyHit, stagger } from "../gore/gore.js";
import { isCorpse } from "../gore/death.js";
import { spray } from "../gore/blood.js";
import { emit, on, EV } from "../core/bus.js";
import { zombieSpec } from "../core/hp.js";
import { particle, sound, playerSound, PRIO } from "../core/fx.js";
import { valid, chance, clamp, now, dist, sub, norm, add, scale, isPlayer, isZombie, yawOf, yawForward, safe } from "../core/util.js";
import {
  CEV, heldInfo, readMods, refreshLore, rarityOf, countItem, takeItem, publishWeaponState, zclass, roman,
  onWorldTick, skillEff, notify,
} from "./common.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */

/** @type {Record<string, any>} */
const MB = /** @type {any} */ (MOD_BY_KEY) ?? {};
/** 改造の鍵の並び。 */
export const MOD_KEYS = Object.freeze(/** @type {any[]} */ (MODS ?? []).map((m) => String(m.key)));

/** 段階の行（無ければ近い段階）。 @param {string} key @param {number} lv @returns {any} */
export function modTier(key, lv) {
  const m = MB[key];
  if (!m || !(lv > 0)) return undefined;
  return m.tiers?.find((/** @type {any} */ x) => x.level === lv) ?? m.tiers?.[Math.min(lv, m.tiers.length) - 1];
}
/** 相手の区分への倍率（MODS の vs）。 @param {string} key @param {Entity} z */
export function vsMult(key, z) { return Number(MB[key]?.vs?.[zclass(z)] ?? 1) || 1; }

/**
 * 当たる時に効く改造（保存した分 + 武器固有の special.innate_mod）。
 * @param {any} w @param {any} [item] ItemStack か ContainerSlot @returns {Record<string, number>}
 */
export function effectiveMods(w, item) {
  const mods = item ? readMods(item) : {};
  const im = w?.special?.innate_mod;
  if (im && MB[im]) mods[im] = Math.max(mods[im] ?? 0, Number(w.special.innate_tier) || 1);
  return mods;
}

/**
 * 当てる前に掛けるダメージ倍率（UV の改造 × 夜の種類 = night_mult）。
 * @param {Record<string, number> | undefined} mods @param {Entity} z
 */
export function modDamageMult(mods, z) {
  if (!mods?.uv || !valid(z)) return 1;
  const t = modTier("uv", mods.uv);
  return uvVulnerable(z) ? Math.max(1, Number(t?.night_mult) || 1) : 1;
}
/** UV が効く種類か（resist.uv > 0 か夜の区分）。 @param {Entity} z */
export function uvVulnerable(z) {
  const s = /** @type {any} */ (zombieSpec(z));
  return Number(s?.resist?.uv ?? 0) > 0 || s?.cls === "night";
}

// ---------------------------------------------------------------------------
//  付ける・外す（手の武器）
// ---------------------------------------------------------------------------
/**
 * @typedef {object} ModCheck
 * @property {boolean} ok
 * @property {string} reason   "ok" | "no_weapon" | "not_allowed" | "no_slot" | "tier" | "materials" | "unknown"
 * @property {[string, number][]} cost
 * @property {[string, number, number][]} missing   [ID, 要る数, 持っている数]
 * @property {any} [w]
 */
/**
 * 手の武器にこの改造（段階）を付けられるか。
 * @param {Player} p @param {string} key @param {number} [tier] @returns {ModCheck}
 */
export function canApplyMod(p, key, tier = 1) {
  const m = MB[key];
  /** @type {ModCheck} */
  const r = { ok: false, reason: "unknown", cost: [], missing: [] };
  if (!m) return r;
  const h = heldInfo(p);
  const w = h?.w;
  if (!h?.item || !w || h.item.isStackable) { r.reason = "no_weapon"; return r; }
  r.w = w;
  const allowed = (w.mods_allowed ?? []).includes(key) && (m.applies_to ?? []).includes(w.kind)
    && (!m.only_dtypes || m.only_dtypes.includes(w.dtype));
  if (!allowed) { r.reason = "not_allowed"; return r; }
  const t = modTier(key, tier);
  if (!t || t.level !== tier) { r.reason = "tier"; return r; }
  const cur = readMods(h.slot);
  if ((cur[key] ?? 0) >= tier) { r.reason = "tier"; return r; }
  const slots = Number(rarityOf(w, h.slot).mod_slots) || 1;
  if (!cur[key] && Object.keys(cur).length >= slots) { r.reason = "no_slot"; return r; }
  r.cost = (t.cost ?? []).map((/** @type {any} */ c) => /** @type {[string, number]} */ ([String(c[0]), Number(c[1]) || 1]));
  for (const [id, n] of r.cost) { const have = countItem(p, id); if (have < n) r.missing.push([id, n, have]); }
  if (r.missing.length) { r.reason = "materials"; return r; }
  r.ok = true; r.reason = "ok";
  return r;
}

/**
 * 手の武器に改造を付ける（材料を払う）。free なら材料なし（報酬・テスト）。
 * @param {Player} p @param {string} key @param {number} [tier] @param {{free?: boolean}} [o]
 * @returns {ModCheck & {mods?: Record<string, number>}}
 */
export function applyMod(p, key, tier = 1, o) {
  const r = canApplyMod(p, key, tier);
  const ok = r.ok || (o?.free && r.reason === "materials");
  if (!ok) {
    playerSound(p, "nr.ui.error", { volume: 0.7 });
    return r;
  }
  if (!o?.free) for (const [id, n] of r.cost) takeItem(p, id, n);
  const h = heldInfo(p);
  if (!h?.item || !h.w) return { ...r, ok: false, reason: "no_weapon" };
  const mods = readMods(h.slot);
  mods[key] = tier;
  writeMods(p, mods);
  const m = MB[key];
  sound(p.dimension, String(m?.sound ?? "nr.ui.craft"), p.location, { volume: 0.9 });
  playerSound(p, "nr.ui.craft", { volume: 0.8 });
  const rgb = m?.visual?.particle_rgb;
  if (m?.visual?.particle) particle(p.dimension, m.visual.particle, add(p.getHeadLocation(), scale(p.getViewDirection(), 0.8)), rgb ? { cr: rgb[0] / 255, cg: rgb[1] / 255, cb: rgb[2] / 255, size: 0.6, radius: 0.6, count: 6 } : undefined, PRIO.NORMAL);
  notify(p, `§6${m?.ja ?? key} ${roman(tier)}§r を付けた`);
  return { ...r, ok: true, reason: "ok", mods };
}

/** 手の武器から改造を外す（材料は戻らない）。外したら true。 @param {Player} p @param {string} key */
export function removeMod(p, key) {
  const h = heldInfo(p);
  if (!h?.item || !h.w || h.item.isStackable) return false;
  const mods = readMods(h.slot);
  if (!mods[key]) return false;
  delete mods[key];
  writeMods(p, mods);
  return true;
}

/** 手の武器の改造を書く（動的プロパティ・説明文・HUD）。 @param {Player} p @param {Record<string, number>} mods */
export function writeMods(p, mods) {
  const h = heldInfo(p);
  if (!h?.item || !h.w || h.item.isStackable) return false;
  const keys = Object.keys(mods).filter((k) => MB[k] && mods[k] > 0);
  /** @type {Record<string, number>} */
  const clean = {};
  for (const k of keys) clean[k] = clamp(Math.round(mods[k]), 1, 3);
  try { h.slot.setDynamicProperty("nr:mods", keys.length ? JSON.stringify(clean) : undefined); } catch { return false; }
  refreshLore(h.slot, h.w);
  publishWeaponState(p, true);
  return true;
}

// ---------------------------------------------------------------------------
//  持続ダメージ（火・出血・毒）
// ---------------------------------------------------------------------------
/**
 * @typedef {object} Dot
 * @property {Entity} z
 * @property {Entity | undefined} attacker
 * @property {string} kind      fire / bleed / toxic
 * @property {number} dps
 * @property {number} until
 * @property {number} [burn]
 */
/** @type {Map<string, Dot>} */
const dots = new Map();
/** 持続・連鎖の一撃の印（改造の効果を重ねない）。 */
const MOD_MARK = Object.freeze({ _mod: true });
const DOT_STEP = 10;

/**
 * 持続ダメージを始める（同じ種類は長い方・強い方に上書き）。
 * @param {Entity} z @param {string} kind @param {number} dps @param {number} ticks @param {Entity | undefined} attacker @param {{burn?: number}} [o]
 */
export function startDot(z, kind, dps, ticks, attacker, o) {
  if (!valid(z) || !isZombie(z) || isCorpse(z) || !(dps > 0) || !(ticks > 0)) return;
  const k = `${z.id}:${kind}`;
  const cur = dots.get(k);
  const until = now() + Math.round(ticks);
  if (cur && cur.until >= until && cur.dps >= dps) return;
  dots.set(k, { z, attacker, kind, dps: Math.max(dps, cur?.dps ?? 0), until: Math.max(until, cur?.until ?? 0), burn: Math.max(Number(o?.burn) || 0, cur?.burn ?? 0) });
}
/** そのゾンビの持続ダメージ（テスト・HUD 用）。 @param {Entity} z */
export function dotsOn(z) {
  const out = [];
  for (const d of dots.values()) if (d.z === z || (valid(d.z) && valid(z) && d.z.id === z.id)) out.push({ kind: d.kind, dps: d.dps, until: d.until });
  return out;
}

const DOT_FX = { fire: "flame", bleed: "blood_drip", toxic: "toxic_drip" };
onWorldTick("mods.dot", DOT_STEP, (t) => {
  for (const [k, d] of [...dots]) {
    if (!valid(d.z) || isCorpse(d.z) || t >= d.until) { dots.delete(k); continue; }
    const z = d.z;
    const front = scale(yawForward(yawOf(z)), -1);
    const dmg = d.dps * (DOT_STEP / 20);
    const at = add(z.location, { x: 0, y: 1.0, z: 0 });
    particle(z.dimension, DOT_FX[/** @type {"fire" | "bleed" | "toxic"} */ (d.kind)] ?? "blood_drip", at, d.kind === "fire" ? { size: 0.8 } : d.kind === "bleed" ? { count: 3, size: 0.6 } : undefined, PRIO.LOW);
    if (d.kind === "fire") {
      applyHit(z, { attacker: d.attacker, source: "fire", dtype: "fire", weight: "light", damage: dmg, power: 0.1, burn: d.burn, noKnockback: true, noAnim: true, noVanilla: true, crit: false, dir: front, ...MOD_MARK });
    } else if (d.kind === "bleed") {
      applyHit(z, { attacker: d.attacker, source: "melee", dtype: "slash", weight: "light", damage: dmg, power: 0.15, noGore: true, noKnockback: true, noAnim: true, noVanilla: true, crit: false, dir: front, ...MOD_MARK });
    } else {
      applyHit(z, { attacker: d.attacker, source: "toxic", dtype: "toxic", weight: "light", damage: dmg, power: 0.1, noKnockback: true, noAnim: true, noVanilla: true, crit: false, dir: front, ...MOD_MARK });
    }
  }
});

// ---------------------------------------------------------------------------
//  当たった時の効果（EV.HIT）
// ---------------------------------------------------------------------------

/** 近くの生きたゾンビ（自分を除く、近い順）。 @param {Entity} z @param {number} r */
function zombiesNear(z, r) {
  /** @type {Entity[]} */
  let near = [];
  try { near = z.dimension.getEntities({ location: z.location, maxDistance: r, families: ["nr_zombie"] }); } catch { near = []; }
  return near.filter((e) => e.id !== z.id && valid(e) && !isCorpse(e)).sort((a, b) => dist(a.location, z.location) - dist(b.location, z.location));
}

/** 2 点の間に電撃の点を並べる。 @param {Entity} from @param {Entity} to */
function arc(from, to) {
  const a = add(from.location, { x: 0, y: 1.1, z: 0 }), b = add(to.location, { x: 0, y: 1.1, z: 0 });
  const n = clamp(Math.ceil(dist(a, b) / 0.7), 1, 6);
  for (let i = 1; i <= n; i++) particle(from.dimension, "shock_spark", add(a, scale(sub(b, a), i / (n + 1))), { count: 2 }, PRIO.LOW);
}

/**
 * 改造の効果を 1 回分（EV.HIT から。テストから直接呼んでもよい）。
 * @param {any} res HitResult
 */
export function onModHit(res) {
  const hit = res?.hit;
  if (!hit || hit._mod || res.blocked || res.deflected) return;
  const z = res.zombie;
  if (!valid(z)) return;
  /** @type {Record<string, number>} */
  const mods = hit.mods && typeof hit.mods === "object" ? hit.mods : {};
  const p = isPlayer(res.attacker) ? /** @type {Player} */ (res.attacker) : undefined;
  const dim = z.dimension;
  const at = res.point ?? add(z.location, { x: 0, y: 1, z: 0 });
  const dir = norm(hit.dir ?? { x: 0, y: 0, z: 1 });
  const alive = !res.killed && !res.corpse;
  const bm = p ? skillEff(p, "bleed_mastery") : undefined;

  // 武器固有の出血（釘バット・手裏剣）
  const innateBleed = Number(hit._innateBleed) || 0;
  if (alive && innateBleed > 0 && !mods.bleed && chance(innateBleed + (Number(bm?.bleed_chance_add) || 0))) {
    startDot(z, "bleed", 1.5 * (Number(bm?.bleed_mod_mult) || 1), 80, p);
    spray(dim, at, dir, 0.7);
  }
  for (const [key, lv] of Object.entries(mods)) {
    const t = modTier(key, lv);
    const m = MB[key];
    if (!t || !m) continue;
    const vs = vsMult(key, z);
    switch (key) {
      case "fire": {
        if (!alive || !chance(Number(t.chance) || 0)) break;
        startDot(z, "fire", (Number(t.dps) || 2) * vs, Number(t.ticks) || 60, p, { burn: Number(t.sets_burn) || 1 });
        particle(dim, "fire_burst", at, { size: 0.7 }, PRIO.NORMAL);
        sound(dim, String(m.sound), at, { volume: 0.9 });
        if (Number(t.spread_radius) > 0) for (const o of zombiesNear(z, Number(t.spread_radius)).slice(0, 4)) startDot(o, "fire", (Number(t.dps) || 2) * vsMult(key, o) * 0.6, (Number(t.ticks) || 60) * 0.6, p, { burn: 1 });
        break;
      }
      case "shock": {
        if (!alive || !chance(Number(t.chance) || 0)) break;
        const dmg = (Number(t.damage) || 3) * vs;
        const stun = Number(t.stun_ticks) || 30;
        particle(dim, "shock_arcs", add(z.location, { x: 0, y: 1, z: 0 }), { size: 1 }, PRIO.NORMAL);
        sound(dim, String(m.sound), at, { volume: 1 });
        applyHit(z, { attacker: p, source: "shock", dtype: "shock", weight: "medium", damage: dmg, power: 0.4, stunTicks: stun, noKnockback: true, crit: false, dir, ...MOD_MARK });
        let prev = z;
        let k = 0;
        for (const o of zombiesNear(z, Number(t.chain_radius) || 3).slice(0, Math.max(0, Number(t.chain) || 0))) {
          k++;
          arc(prev, o);
          applyHit(o, { attacker: p, source: "shock", dtype: "shock", weight: "light", damage: dmg * Math.pow(0.75, k) * vsMult(key, o) / vs, power: 0.3, stunTicks: Math.round(stun * 0.8), noKnockback: true, crit: false, dir: norm(sub(o.location, prev.location)), ...MOD_MARK });
          prev = o;
        }
        break;
      }
      case "bleed": {
        if (!alive) break;
        const c = (Number(t.chance) || 0) + (Number(bm?.bleed_chance_add) || 0);
        if (!chance(c)) break;
        startDot(z, "bleed", (Number(t.dps) || 1.5) * vs * (Number(bm?.bleed_mod_mult) || 1), Number(t.ticks) || 100, p);
        spray(dim, at, dir, 1.0);
        sound(dim, String(m.sound), at, { volume: 0.8 });
        break;
      }
      case "toxic": {
        if (!alive || !chance(Number(t.chance) || 0)) break;
        const ticks = Number(t.ticks) || 100;
        startDot(z, "toxic", (Number(t.dps) || 1.5) * vs, ticks, p);
        const slow = Number(t.slow) || 0.2;
        safe("toxic.slow", () => z.addEffect("slowness", ticks, { amplifier: slow >= 0.3 ? 1 : 0, showParticles: false }));
        const r = Number(t.cloud_radius) || 1.5;
        particle(dim, "toxic_gas", add(z.location, { x: 0, y: 0.8, z: 0 }), { radius: r, life: ticks / 20 }, PRIO.NORMAL);
        sound(dim, String(m.sound), at, { volume: 0.8 });
        for (const o of zombiesNear(z, r).slice(0, 4)) startDot(o, "toxic", (Number(t.dps) || 1.5) * vsMult(key, o) * 0.5, ticks * 0.6, p);
        break;
      }
      case "uv": {
        if (!uvVulnerable(z)) break;
        particle(dim, "uv_burn", at, { size: 0.8 }, PRIO.NORMAL);
        sound(dim, String(m.sound), at, { volume: 0.9 });
        if (alive && Number(t.night_stun_ticks) > 0) stagger(z, Number(t.night_stun_ticks));
        if (res.killed && p && Number(t.immunity_on_kill_s) > 0) emit(CEV.IMMUNITY, { player: p, seconds: Number(t.immunity_on_kill_s), source: "uv_mod" });
        break;
      }
      case "impact": {
        particle(dim, "impact_ring", at, { dx: dir.x, dy: dir.y, dz: dir.z }, PRIO.NORMAL);
        sound(dim, String(m.sound), at, { volume: 0.9 });
        break;
      }
      default: break;
    }
  }
}
on(EV.HIT, (res) => onModHit(res));

/** 改造の一覧（端末の画面用）: 付けられる改造と段階の材料。 @param {any} w */
export function modsFor(w) {
  return /** @type {any[]} */ (MODS ?? []).filter((m) => (w?.mods_allowed ?? []).includes(m.key) && (m.applies_to ?? []).includes(w?.kind)
    && (!m.only_dtypes || m.only_dtypes.includes(w?.dtype)));
}
