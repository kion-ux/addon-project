// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 武器の耐久（すり減り・警告・壊れる・修理キット）
//
//  * 近接の命中のすり減りはエンジンの minecraft:durability を nr:weapon の onBeforeDurabilityDamage で
//    決める（COMBAT_TUNING.durability.per_hit × 難易度の durability_mult）。溜め攻撃・壁・銃・弓は
//    スクリプトが wear() で減らす。
//  * 耐久が尽きても消さない（Dying Light と同じ「壊れた武器」）: エンジンの耐久は 1 残し、ItemStack の
//    動的プロパティ nr:broken = true、説明文に「壊れている」、ダメージは broken_damage_mult（0.25）倍。
//    壊れた瞬間に nr.w.break。残りが warn_frac（2 割）を切ったら一度だけ警告。
//  * 修理キット（nr:repair_kit、use.restore / max_loss）: 使って 30 tick 構えると、手の武器（無ければ最後に
//    持っていた武器・ホットバーで一番減った武器）の耐久を戻す。最大値は nr:max_loss（割合）で少しずつ減る。
// ===========================================================================
import { world, system } from "@minecraft/server";
import { COMBAT_TUNING } from "../data/settings.js";
import { ITEM_BY_ID } from "../data/items.js";
import { onItemComponent } from "../core/components.js";
import { sound, particle, playerSound, playerAnim, PRIO } from "../core/fx.js";
import { difficulty } from "../core/settings.js";
import { valid, chance, safe, clamp, now, add, warnOnce } from "../core/util.js";
import { heldInfo, weaponOf, refreshLore, publishWeaponState, containerOf, takeItem, onPlayerTick } from "./common.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").ItemStack} ItemStack */
/** @typedef {import("@minecraft/server").ContainerSlot} ContainerSlot */

/** @type {any} */
const CT = COMBAT_TUNING ?? {};
/** 耐久の調整（spec の COMBAT_TUNING.durability）。 */
export const DUR = Object.freeze({ per_hit: 1, per_miss: 0, per_wall: 2, broken_damage_mult: 0.25, warn_frac: 0.2, ...(CT.durability ?? {}) });

/**
 * @typedef {object} DurInfo
 * @property {number} damage   今の傷（エンジンの値）
 * @property {number} max      エンジンの最大
 * @property {number} cap      ここまで減ると「壊れた」（修理で減った最大値 − 1）
 * @property {number} frac     残りの割合 0..1
 * @property {number} loss     修理で失った最大値の割合
 * @property {boolean} broken
 */
/**
 * 耐久の状態（ItemStack か ContainerSlot。耐久の無い物は undefined）。
 * @param {any} it @returns {DurInfo | undefined}
 */
export function durabilityOf(it) {
  try {
    if (!it) return undefined;
    const item = typeof it.getItem === "function" ? it.getItem() : it;
    const dc = /** @type {any} */ (item?.getComponent("minecraft:durability"));
    if (!dc || !(dc.maxDurability > 0)) return undefined;
    const lossRaw = item.isStackable ? 0 : item.getDynamicProperty("nr:max_loss");
    const loss = typeof lossRaw === "number" ? clamp(lossRaw, 0, 0.9) : 0;
    const max = dc.maxDurability;
    const cap = Math.max(1, Math.min(max, Math.floor(max * (1 - loss))) - 1);
    const damage = dc.damage;
    const broken = (!item.isStackable && item.getDynamicProperty("nr:broken") === true) || damage >= cap;
    return { damage, max, cap, frac: clamp(1 - damage / cap, 0, 1), loss, broken };
  } catch { return undefined; }
}
/** 壊れているか。 @param {any} it */
export function isBroken(it) { return !!durabilityOf(it)?.broken; }
/** 壊れた武器のダメージ倍率（壊れていなければ 1）。 @param {any} it */
export function brokenMult(it) { return isBroken(it) ? Number(DUR.broken_damage_mult) || 0.25 : 1; }

/** すり減りの量（難易度の durability_mult で割り、端数は確率で丸める）。 @param {number} base */
export function wearAmount(base) {
  const mult = Number(/** @type {any} */ (difficulty())?.durability_mult) || 1;
  const v = Math.max(0, base) / Math.max(0.1, mult);
  const n = Math.floor(v);
  return n + (chance(v - n) ? 1 : 0);
}

/** @type {Map<string, number>} 警告を出した tick（同じ武器で何度も出さない） */
const warnedAt = new Map();

/** 壊れた（手の武器が typeId のままなら印を付ける）。 @param {Player} p @param {string} typeId */
function markBroken(p, typeId) {
  if (!valid(p)) return;
  const h = heldInfo(p);
  if (!h?.item || h.item.typeId !== typeId || h.item.isStackable) return;
  safe("markBroken", () => h.slot.setDynamicProperty("nr:broken", true));
  refreshLore(h.slot, h.w);
  const at = add(p.getHeadLocation(), { x: 0, y: -0.4, z: 0 });
  sound(p.dimension, "nr.w.break", at, { volume: 1.1, pitch: 0.95 });
  for (let i = 0; i < 3; i++) particle(p.dimension, "hit_spark", at, { dx: Math.random() - 0.5, dy: 0.6, dz: Math.random() - 0.5 }, PRIO.HIGH);
  safe("actionbar", () => p.onScreenDisplay.setActionBar(`§c${h.w?.ja ?? "武器"}が壊れた（修理キットで直す）`));
  publishWeaponState(p, true);
}
/** 残りわずかの警告。 @param {Player} p @param {any} w */
function warnLow(p, w) {
  if (!valid(p)) return;
  const k = `${p.id}:${w?.id}`;
  if (now() - (warnedAt.get(k) ?? -1e9) < 200) return;
  warnedAt.set(k, now());
  playerSound(p, "nr.ui.error", { volume: 0.7, pitch: 1.5 });
  safe("actionbar", () => p.onScreenDisplay.setActionBar(`§e${w?.ja ?? "武器"}の耐久が残りわずか`));
}

// 近接の命中（エンジンのすり減り）: 量を決め、壊れる手前で止める
onItemComponent("nr:weapon", {
  onBeforeDurabilityDamage(e) {
    const it = e.itemStack;
    const w = weaponOf(it?.typeId);
    if (!it || !w) return;
    const d = durabilityOf(it);
    if (!d) return;
    if (d.broken) { e.durabilityDamage = 0; return; }
    let amt = wearAmount(Number(DUR.per_hit) || 1);
    const p = /** @type {any} */ (e.attackingEntity);
    const isP = p?.typeId === "minecraft:player";
    if (d.damage + amt >= d.cap) {
      amt = Math.max(0, d.cap - d.damage);
      if (isP) { const typeId = it.typeId; system.run(() => markBroken(p, typeId)); }
    } else if (isP && 1 - (d.damage + amt) / d.cap < Number(DUR.warn_frac) && d.frac >= Number(DUR.warn_frac)) {
      system.run(() => warnLow(p, w));
    }
    e.durabilityDamage = Math.max(0, Math.round(amt));
    if (isP) system.run(() => publishWeaponState(p));
  },
});

/**
 * 手の武器をスクリプトで減らす（溜め攻撃・壁・銃・弓）。減らしたら true。
 * @param {Player} p @param {number} base 減らす量（難易度の前） @param {string} [reason]
 */
export function wear(p, base, reason = "use") {
  void reason;
  const h = heldInfo(p);
  if (!h?.item || !h.w || h.item.isStackable) return false;
  const d = durabilityOf(h.item);
  if (!d || d.broken) return false;
  const amt = wearAmount(base);
  if (amt <= 0) return false;
  const dc = /** @type {any} */ (h.item.getComponent("minecraft:durability"));
  const nd = Math.min(d.cap, d.damage + amt);
  try { dc.damage = nd; h.slot.setItem(h.item); } catch (err) { warnOnce("wear", "耐久を書けない", err); return false; }
  if (nd >= d.cap) markBroken(p, h.item.typeId);
  else if (1 - nd / d.cap < Number(DUR.warn_frac) && d.frac >= Number(DUR.warn_frac)) warnLow(p, h.w);
  publishWeaponState(p);
  return true;
}

/**
 * 武器を直す（修理キット・端末から）。slotIndex を省くと手の武器 → 最後に持った武器 → ホットバーで一番減った武器。
 * 戻した耐久（エンジンの点）を返す（直せる物が無ければ 0）。
 * @param {Player} p @param {number} [restore] 最大の何割を戻すか @param {number} [maxLoss] 最大値を何割減らすか @param {number} [slotIndex]
 */
export function repair(p, restore = 0.35, maxLoss = 0.05, slotIndex) {
  const c = containerOf(p);
  if (!c) return 0;
  const idx = slotIndex ?? repairTarget(p);
  if (idx === undefined) return 0;
  const it = c.getItem(idx);
  const w = weaponOf(it?.typeId);
  const d = durabilityOf(it);
  if (!it || !w || !d || it.isStackable) return 0;
  if (d.damage <= 0 && !d.broken) return 0;
  const loss = clamp(d.loss + Math.max(0, maxLoss), 0, 0.6);
  const cap = Math.max(1, Math.min(d.max, Math.floor(d.max * (1 - loss))) - 1);
  const before = d.damage;
  const nd = clamp(Math.round(d.damage - restore * d.max), 0, Math.max(0, cap - 1));
  try {
    const dc = /** @type {any} */ (it.getComponent("minecraft:durability"));
    dc.damage = nd;
    it.setDynamicProperty("nr:max_loss", Math.round(loss * 1000) / 1000);
    it.setDynamicProperty("nr:broken", undefined);
    c.setItem(idx, it);
    refreshLore(c.getSlot(idx), w);
  } catch (err) { warnOnce("repair", "修理を書けない", err); return 0; }
  warnedAt.delete(`${p.id}:${w.id}`);
  sound(p.dimension, "nr.ui.repair", p.location, { volume: 0.9 });
  particle(p.dimension, "heal_sparkle", add(p.location, { x: 0, y: 1.1, z: 0 }), undefined, PRIO.LOW);
  safe("actionbar", () => p.onScreenDisplay.setActionBar(`§a${w.ja}を直した`));
  publishWeaponState(p, true);
  return Math.max(0, before - nd);
}

/** @type {Map<string, {index: number, typeId: string}>} 最後に手に持った耐久のある武器 */
const lastWeapon = new Map();
/** 直す武器のスロット。 @param {Player} p @returns {number | undefined} */
function repairTarget(p) {
  const c = containerOf(p);
  if (!c) return undefined;
  /** @param {number} i */
  const needs = (i) => { const it = c.getItem(i); const d = durabilityOf(it); return weaponOf(it?.typeId) && d && (d.damage > 0 || d.broken) ? d : undefined; };
  const sel = p.selectedSlotIndex;
  if (needs(sel)) return sel;
  const lw = lastWeapon.get(p.id);
  if (lw && c.getItem(lw.index)?.typeId === lw.typeId && needs(lw.index)) return lw.index;
  let best, bf = 2;
  for (let i = 0; i < Math.min(9, c.size); i++) { const d = needs(i); if (d && d.frac < bf) { bf = d.frac; best = i; } }
  return best;
}
onPlayerTick("lastWeapon", 4, (p) => {
  const h = heldInfo(p);
  if (h?.w && h.item && durabilityOf(h.item)) lastWeapon.set(p.id, { index: h.index, typeId: h.item.typeId });
});

// ---------------------------------------------------------------------------
//  修理キット（使って use_ticks 構える → 直す。手を替えたら取りやめ）
// ---------------------------------------------------------------------------
const KIT = "nr:repair_kit";
/** @type {any} */
const KIT_USE = /** @type {any} */ (ITEM_BY_ID)?.[KIT]?.use ?? { use_ticks: 30, restore: 0.35, max_loss: 0.05, anim: "heal", sound: "nr.ui.repair" };
/** @type {Map<string, {until: number, index: number}>} */
const kits = new Map();
world.afterEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack?.typeId !== KIT) return;
  const p = ev.source;
  if (!valid(p) || kits.has(p.id)) return;
  if (repairTarget(p) === undefined) {
    playerSound(p, "nr.ui.error", { volume: 0.7 });
    safe("actionbar", () => p.onScreenDisplay.setActionBar("§7直す武器が無い"));
    return;
  }
  kits.set(p.id, { until: now() + Math.max(1, Number(KIT_USE.use_ticks) || 30), index: p.selectedSlotIndex });
  playerAnim(p, String(KIT_USE.anim ?? "heal"));
  sound(p.dimension, String(KIT_USE.sound ?? "nr.ui.repair"), p.location, { volume: 0.8 });
});
onPlayerTick("repairKit", 1, (p, t) => {
  const k = kits.get(p.id);
  if (!k) return;
  const h = heldInfo(p);
  if (!h?.item || h.item.typeId !== KIT || h.index !== k.index) { kits.delete(p.id); return; }
  if (t < k.until) return;
  kits.delete(p.id);
  if (repair(p, Number(KIT_USE.restore) || 0.35, Number(KIT_USE.max_loss) || 0.05) > 0) takeItem(p, KIT, 1);
});
world.afterEvents.playerLeave.subscribe((ev) => { kits.delete(ev.playerId); lastWeapon.delete(ev.playerId); });
