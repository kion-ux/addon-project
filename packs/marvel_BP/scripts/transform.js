// 変身 / becoming the mutant
//
// 三人称でキャラクターに見えている正体は、頭スロットに装備した
// 「体アイテム」のアタッチャブル。プレイヤー本体は透明化して隠す。
//
// 技を撃つ瞬間だけ、体アイテムを *その技専用のもの* に差し替える。
// これがスクリプトから三人称アニメーションを切り替える唯一の確実な方法で、
// 技ごとに違う構えが出るのはこの仕組みのおかげ。
import { world, system, ItemStack, EquipmentSlot } from "@minecraft/server";
import {
  PROP, TAG, ITEM, HERO, TECH, MAG_MAX, MAG_REGEN, MAG_REGEN_STAGE3,
  MAG_DRAIN, STAGE_THRESHOLDS, FORM_ITEMS, FX, SOUND,
} from "./config.js";
import {
  actionbar, allPlayers, bar, bool, num, safe, setProp, str, tell, title, tr,
} from "./util.js";
import { chord, fade, fx, fxRing, fxScatter, shake, shakeNearby, sound } from "./effects.js";

const ARMOR_SLOTS = ["Head", "Chest", "Legs", "Feet"];

//: いま技の姿勢を保持しているプレイヤー -> 解除予定 tick
const posing = new Map();

export function container(player) {
  return safe(() => player.getComponent("minecraft:inventory")?.container);
}

export function selectedSlot(player) {
  const v = player.selectedSlotIndex;
  return typeof v === "number" ? v : (player.selectedSlot ?? 0);
}

export function give(player, typeId, amount = 1) {
  const inv = container(player);
  if (!inv) return;
  const left = safe(() => inv.addItem(new ItemStack(typeId, amount)));
  if (left) safe(() => player.dimension.spawnItem(left, player.location));
}

export function consumeSelected(player, amount = 1) {
  const inv = container(player);
  if (!inv) return;
  const slot = selectedSlot(player);
  const item = safe(() => inv.getItem(slot));
  if (!item) return;
  if (item.amount > amount) {
    item.amount -= amount;
    safe(() => inv.setItem(slot, item));
  } else {
    safe(() => inv.setItem(slot, undefined));
  }
}

// ---------------------------------------------------------------- state
export function isMutant(player) { return bool(player, PROP.mutant, false); }
export function isTransformed(player) { return bool(player, PROP.form, false); }
export function heroOf(player) { return str(player, PROP.hero, "magneto"); }
export function stageOf(player) { return Math.max(1, num(player, PROP.stage, 1)); }
export function magOf(player) { return num(player, PROP.mag, MAG_MAX); }

export function spendMag(player, amount) {
  const left = Math.max(0, magOf(player) - amount);
  setProp(player, PROP.mag, left);
  if (left <= 0 && isTransformed(player)) revert(player, true);
  return left;
}

export function stageFor(kills) {
  let stage = 1;
  for (const [threshold, value] of STAGE_THRESHOLDS) {
    if (kills >= threshold) stage = value;
  }
  return stage;
}

export function refreshStage(player) {
  const before = stageOf(player);
  const after = stageFor(num(player, PROP.mastery, 0));
  if (after > before) {
    setProp(player, PROP.stage, after);
    tell(player, tr("msg.stage_up"));
    sound(player.dimension, SOUND.transform_2, player.location, { pitch: 1.2 });
    fx(player.dimension, FX.transform_ring, player.location);
  }
  return after;
}

// ---------------------------------------------------------------- awaken
export function awaken(player) {
  if (isMutant(player)) {
    tell(player, tr("msg.already_mutant"));
    return;
  }
  setProp(player, PROP.mutant, true);
  setProp(player, PROP.mag, MAG_MAX);
  setProp(player, PROP.stage, 1);
  setProp(player, PROP.hero, "magneto");
  setProp(player, PROP.tech, "repulse");
  give(player, ITEM.magneto_helmet);
  give(player, TECH.repulse.item);
  give(player, TECH.attract.item);
  give(player, TECH.flight.item);

  chord(player.dimension, player.location, [
    [SOUND.transform, 0, { volume: 1.4, pitch: 0.7 }],
    ["random.levelup", 6, { pitch: 0.6 }],
    [SOUND.mag_charge, 12, { volume: 1.0, pitch: 1.4 }],
  ]);
  fxScatter(player.dimension, FX.transform_burst, player.location, 8, 1.0);
  fx(player.dimension, FX.transform_ring, player.location);
  shake(player, 0.45, 0.9, "rotational");
  fade(player, { red: 0.55, green: 0.30, blue: 0.95 }, 0.10, 0.08, 0.5);
  title(player, tr("title.awaken"), tr("title.awaken_sub"), 8, 50, 20);
  tell(player, tr("msg.awakened"));
}

// ---------------------------------------------------------------- armour
function stashArmor(player) {
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  const inv = container(player);
  if (!eq || !inv) return;
  const stashed = [];
  for (const slot of ARMOR_SLOTS) {
    const worn = safe(() => eq.getEquipment(slot));
    if (!worn) { stashed.push(null); continue; }
    const left = safe(() => inv.addItem(worn));
    if (left) { stashed.push(null); continue; }
    safe(() => eq.setEquipment(slot, undefined));
    stashed.push(worn.typeId);
  }
  setProp(player, PROP.stored, stashed.some(Boolean) ? JSON.stringify(stashed) : "");
}

function restoreArmor(player) {
  const rawValue = str(player, PROP.stored, "");
  if (!rawValue) return;
  setProp(player, PROP.stored, "");
  let ids;
  try { ids = JSON.parse(rawValue); } catch (_) { return; }
  if (!Array.isArray(ids)) return;
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  const inv = container(player);
  if (!eq || !inv) return;
  for (let i = 0; i < ARMOR_SLOTS.length; i++) {
    const id = ids[i];
    if (!id) continue;
    if (safe(() => eq.getEquipment(ARMOR_SLOTS[i]))) continue;
    for (let slot = 0; slot < inv.size; slot++) {
      const item = safe(() => inv.getItem(slot));
      if (item?.typeId !== id) continue;
      safe(() => eq.setEquipment(ARMOR_SLOTS[i], item));
      safe(() => inv.setItem(slot, undefined));
      break;
    }
  }
}

// ---------------------------------------------------------------- form item
function wearForm(player, typeId) {
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  if (!eq) return;
  safe(() => eq.setEquipment(EquipmentSlot.Head, new ItemStack(typeId, 1)));
}

function clearForm(player) {
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  if (!eq) return;
  const head = safe(() => eq.getEquipment(EquipmentSlot.Head));
  if (head && FORM_ITEMS.includes(head.typeId)) {
    safe(() => eq.setEquipment(EquipmentSlot.Head, undefined));
  }
}

/**
 * 技の姿勢に切り替える。`hold` tick 後に通常の体へ戻す。
 * これがそのまま三人称のアニメーション再生になる。
 */
export function pose(player, formItemId, hold) {
  if (!isTransformed(player)) return;
  if (!hold || hold <= 0) return;
  wearForm(player, formItemId);
  setProp(player, PROP.casting, formItemId);
  posing.set(player.id, system.currentTick + hold);
}

function tickPoses() {
  if (!posing.size) return;
  const now = system.currentTick;
  for (const player of allPlayers()) {
    const until = posing.get(player.id);
    if (until === undefined || now < until) continue;
    posing.delete(player.id);
    setProp(player, PROP.casting, "");
    if (isTransformed(player)) wearForm(player, HERO[heroOf(player)].form);
  }
}

// ---------------------------------------------------------------- buffs
function buffsFor(hero, stage) {
  const list = [
    ["resistance", stage >= 3 ? 2 : 1],
    ["fire_resistance", 0],
    ["night_vision", 0],
  ];
  if (hero === "magneto") {
    list.push(["strength", stage >= 3 ? 2 : 1]);
    list.push(["slow_falling", 0]);
  } else if (hero === "quicksilver") {
    list.push(["speed", 4]);
    list.push(["jump_boost", 2]);
    list.push(["haste", 2]);
  } else if (hero === "sabretooth") {
    list.push(["strength", 2]);
    list.push(["regeneration", 1]);
    list.push(["speed", 1]);
  } else if (hero === "juggernaut" || hero === "blob") {
    list.push(["strength", 3]);
    list.push(["resistance", 3]);
    list.push(["slowness", 0]);
  } else if (hero === "toad") {
    list.push(["jump_boost", 4]);
    list.push(["speed", 1]);
  } else if (hero === "mystique") {
    list.push(["speed", 2]);
    list.push(["jump_boost", 1]);
  } else {
    list.push(["strength", 1]);
    list.push(["speed", 1]);
  }
  return list;
}

function applyBuffs(player) {
  const hero = heroOf(player);
  const stage = stageOf(player);
  for (const [id, amp] of buffsFor(hero, stage)) {
    safe(() => player.addEffect(id, 140, { amplifier: amp, showParticles: false }));
  }
  // プレイヤー自身のスキンを隠す。体アイテムのアタッチャブルだけが残る。
  safe(() => player.addEffect("invisibility", 140, { amplifier: 0, showParticles: false }));
}

function clearBuffs(player) {
  for (const id of ["strength", "resistance", "speed", "jump_boost", "haste",
                    "regeneration", "fire_resistance", "night_vision",
                    "slow_falling", "slowness", "invisibility"]) {
    safe(() => player.removeEffect(id));
  }
}

// ---------------------------------------------------------------- transform
export function transform(player) {
  if (isTransformed(player)) return;
  if (magOf(player) < 10) {
    tell(player, tr("msg.too_tired"));
    return;
  }
  const hero = HERO[heroOf(player)] ?? HERO.magneto;
  stashArmor(player);
  wearForm(player, hero.form);
  setProp(player, PROP.form, true);
  player.addTag(TAG.form);
  applyBuffs(player);

  const at = { x: player.location.x, y: player.location.y + 1.0, z: player.location.z };
  fx(player.dimension, FX.transform_burst, at);
  fx(player.dimension, FX.transform_ring, player.location);
  fxRing(player.dimension, FX.mag_aura, player.location, 1.6, 12, 0.4);
  fxScatter(player.dimension, FX.mag_spark, player.location, 10, 1.2);
  chord(player.dimension, player.location, [
    [SOUND.transform, 0, { volume: 1.6, pitch: 0.75 }],
    [SOUND.transform_2, 5, { volume: 1.0, pitch: 1.1 }],
    [SOUND.mag_release, 9, { volume: 0.7, pitch: 1.6 }],
  ]);
  shake(player, 0.5, 0.7);
  shakeNearby(player.dimension, player.location, 14, 0.3, 0.5);
  fade(player, { red: 0.42, green: 0.18, blue: 0.72 }, 0.08, 0.06, 0.42);
  title(player, tr("title.transform"), tr("title.transform_sub"), 4, 30, 14);
}

export function revert(player, exhausted = false) {
  if (!isTransformed(player)) return;
  clearForm(player);
  posing.delete(player.id);
  setProp(player, PROP.casting, "");
  setProp(player, PROP.form, false);
  setProp(player, PROP.flying, false);
  player.removeTag(TAG.form);
  restoreArmor(player);
  clearBuffs(player);
  fxScatter(player.dimension, FX.revert_smoke, player.location, 12, 1.2);
  sound(player.dimension, SOUND.revert, player.location, { pitch: 0.8 });
  shake(player, 0.2, 0.4);
  if (exhausted) {
    safe(() => player.addEffect("weakness", 260, { amplifier: 1 }));
    safe(() => player.addEffect("slowness", 180, { amplifier: 0, showParticles: false }));
    tell(player, tr("msg.exhausted"));
  } else {
    tell(player, tr("msg.revert"));
  }
}

export function toggle(player) {
  if (!isMutant(player)) {
    tell(player, tr("msg.no_power"));
    return;
  }
  if (isTransformed(player)) revert(player); else transform(player);
}

// ---------------------------------------------------------------- tick
/** 毎秒: ゲージ・バフ・HUD。 */
export function tickTransform() {
  for (const player of allPlayers()) {
    if (!isMutant(player)) continue;
    const transformed = isTransformed(player);
    // 撃破数が伸びても誰も段階を上げ直さないと、永久に段階1のままになり
    // 必殺技（段階3）に一生届かない。毎秒ここで見直す。
    const stage = refreshStage(player);
    let mag = magOf(player);

    if (transformed) {
      applyBuffs(player);
      mag -= MAG_DRAIN;
      if (mag <= 0) { setProp(player, PROP.mag, 0); revert(player, true); continue; }
    } else {
      mag = Math.min(MAG_MAX, mag + (stage >= 3 ? MAG_REGEN_STAGE3 : MAG_REGEN));
    }
    setProp(player, PROP.mag, mag);
  }
}

/** 毎 tick: 姿勢の戻し。 */
export function tickForm() {
  tickPoses();
}

export function hud(player, extra) {
  const mag = magOf(player);
  const ratio = mag / MAG_MAX;
  const colour = ratio > 0.5 ? "§d" : ratio > 0.2 ? "§e" : "§c";
  const techKey = str(player, PROP.tech, "repulse");
  const tech = TECH[techKey];
  const parts = [
    { translate: "marvel.hud.mag" },
    { text: ` ${colour}${bar(ratio, 12)}§r ${Math.ceil(mag)}` },
  ];
  if (tech) {
    parts.push({ text: "  §7|§r  " });
    parts.push({ translate: `marvel.tech.${techKey}` });
  }
  if (extra) parts.push({ text: `  §7|§r ${extra}` });
  actionbar(player, { rawtext: parts });
}

/** ログイン時の復帰処理。 */
export function restore(player) {
  if (!isTransformed(player)) {
    player.removeTag(TAG.form);
    clearForm(player);
    return;
  }
  player.addTag(TAG.form);
  applyBuffs(player);
  wearForm(player, (HERO[heroOf(player)] ?? HERO.magneto).form);
}

/** 変身していないのに残っている体アイテムを掃除する。 */
export function sweepFormItems() {
  for (const player of allPlayers()) {
    if (isTransformed(player)) continue;
    const inv = container(player);
    if (!inv) continue;
    for (let i = 0; i < inv.size; i++) {
      const item = safe(() => inv.getItem(i));
      if (item && FORM_ITEMS.includes(item.typeId)) safe(() => inv.setItem(i, undefined));
    }
  }
}

world.afterEvents.entityDie.subscribe((ev) => {
  const e = ev.deadEntity;
  if (e?.typeId !== "minecraft:player") return;
  system.run(() => {
    setProp(e, PROP.form, false);
    setProp(e, PROP.flying, false);
    setProp(e, PROP.casting, "");
    e.removeTag(TAG.form);
    setProp(e, PROP.mag, MAG_MAX * 0.4);
    posing.delete(e.id);
  });
});
