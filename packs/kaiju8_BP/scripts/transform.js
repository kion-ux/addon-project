// 怪獣8号への変身 / Kaiju No.8 transformation
import { world, system, ItemStack, EquipmentSlot } from "@minecraft/server";
import {
  PROP, TAG_NO8, FORM_ITEM, ENERGY_MAX, ENERGY_DRAIN, ENERGY_REGEN,
} from "./config.js";
import {
  tr, tell, actionbar, playSound, burst, bar, num, bool, allPlayers,
} from "./util.js";
import { fx, fxRing, fxScatter, sound, shake, shakeNearby } from "./effects.js";

const BUFFS = [
  ["strength", 2],
  ["resistance", 1],
  ["speed", 1],
  ["jump_boost", 2],
  ["regeneration", 0],
  ["fire_resistance", 0],
  ["haste", 1],
];

export function selectedSlot(player) {
  const v = player.selectedSlotIndex;
  return typeof v === "number" ? v : (player.selectedSlot ?? 0);
}

export function container(player) {
  try { return player.getComponent("minecraft:inventory")?.container; } catch (_) { return undefined; }
}

export function consumeSelected(player, amount = 1) {
  const inv = container(player);
  if (!inv) return;
  const slot = selectedSlot(player);
  const item = inv.getItem(slot);
  if (!item) return;
  if (item.amount > amount) {
    item.amount -= amount;
    inv.setItem(slot, item);
  } else {
    inv.setItem(slot, undefined);
  }
}

export function give(player, typeId, amount = 1) {
  const inv = container(player);
  if (!inv) return;
  const stack = new ItemStack(typeId, amount);
  const left = inv.addItem(stack);
  if (left) {
    try { player.dimension.spawnItem(left, player.location); } catch (_) { }
  }
}

export function isTransformed(player) {
  return bool(player, PROP.form, false);
}

export function hasPower(player) {
  return bool(player, PROP.power, false);
}

/** 小型怪獣を飲み込む — the moment Kafka's life changes. */
export function grantPower(player) {
  if (hasPower(player)) {
    tell(player, tr("kaiju8.msg.already_power"));
    return;
  }
  player.setDynamicProperty(PROP.power, true);
  player.setDynamicProperty(PROP.energy, ENERGY_MAX);
  consumeSelected(player);
  give(player, "kaiju8:no8_power");
  sound(player.dimension, "mob.enderdragon.growl", player.location,
        { volume: 1.4, pitch: 0.65 });
  sound(player.dimension, "random.levelup", player.location, { pitch: 0.55 });
  fxScatter(player.dimension, "kaiju8:transform_burst", player.location, 6, 0.8);
  fxScatter(player.dimension, "kaiju8:kaiju_blood", player.location, 8, 0.9);
  shake(player, 0.45, 0.9, "rotational");
  try {
    player.onScreenDisplay.setTitle(tr("kaiju8.title.awaken"), {
      fadeInDuration: 8, stayDuration: 50, fadeOutDuration: 20,
      subtitle: tr("kaiju8.title.awaken_sub"),
    });
  } catch (_) { }
  tell(player, tr("kaiju8.msg.power_gained"));
}

const ARMOR_SLOTS = [
  EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet,
];

/** 変身時、戦闘服は一旦しまう（怪獣の体に重ならないように）。 */
function stashArmor(player) {
  const eq = player.getComponent("minecraft:equippable");
  const inv = container(player);
  if (!eq || !inv) return;
  const stashed = [];
  for (const slot of ARMOR_SLOTS) {
    let worn;
    try { worn = eq.getEquipment(slot); } catch (_) { stashed.push(null); continue; }
    if (!worn) { stashed.push(null); continue; }
    const left = inv.addItem(worn);
    if (left) { stashed.push(null); continue; }  // no room - leave it on
    try { eq.setEquipment(slot, undefined); } catch (_) { }
    stashed.push(worn.typeId);
  }
  try {
    player.setDynamicProperty(PROP.storedArmor,
      stashed.some(Boolean) ? JSON.stringify(stashed) : "");
  } catch (_) { }
}

/** 変身解除時、しまった戦闘服を着せ直す。 */
function restoreArmor(player) {
  let raw;
  try { raw = player.getDynamicProperty(PROP.storedArmor); } catch (_) { return; }
  if (typeof raw !== "string" || !raw) return;
  try { player.setDynamicProperty(PROP.storedArmor, ""); } catch (_) { }
  let ids;
  try { ids = JSON.parse(raw); } catch (_) { return; }
  if (!Array.isArray(ids)) return;
  const eq = player.getComponent("minecraft:equippable");
  const inv = container(player);
  if (!eq || !inv) return;
  for (let i = 0; i < ARMOR_SLOTS.length; i++) {
    const id = ids[i];
    if (!id) continue;
    try { if (eq.getEquipment(ARMOR_SLOTS[i])) continue; } catch (_) { continue; }
    for (let slot = 0; slot < inv.size; slot++) {
      const item = inv.getItem(slot);
      if (item?.typeId !== id) continue;
      try {
        eq.setEquipment(ARMOR_SLOTS[i], item);
        inv.setItem(slot, undefined);
      } catch (_) { }
      break;
    }
  }
}

export function transform(player) {
  if (isTransformed(player)) return;
  if (num(player, PROP.energy, ENERGY_MAX) < 12) {
    tell(player, tr("kaiju8.msg.too_tired"));
    return;
  }
  stashArmor(player);
  const eq = player.getComponent("minecraft:equippable");
  try { eq?.setEquipment(EquipmentSlot.Head, new ItemStack(FORM_ITEM, 1)); } catch (_) { }
  player.setDynamicProperty(PROP.form, true);
  player.addTag(TAG_NO8);
  applyBuffs(player);
  const at = { x: player.location.x, y: player.location.y + 1.0, z: player.location.z };
  fx(player.dimension, "kaiju8:transform_burst", at);
  fx(player.dimension, "kaiju8:shock_ring", player.location);
  fxScatter(player.dimension, "kaiju8:transform_smoke", player.location, 10, 1.4);
  fxRing(player.dimension, "kaiju8:no8_aura", player.location, 1.6, 12, 0.4);
  sound(player.dimension, "mob.enderdragon.growl", player.location,
        { volume: 1.8, pitch: 0.6 });
  sound(player.dimension, "random.explode", player.location, { volume: 0.9, pitch: 1.2 });
  shake(player, 0.5, 0.7);
  shakeNearby(player.dimension, player.location, 14, 0.3, 0.5);
  try {
    player.onScreenDisplay.setTitle(tr("kaiju8.title.transform"), {
      fadeInDuration: 4, stayDuration: 26, fadeOutDuration: 12,
      subtitle: tr("kaiju8.title.transform_sub"),
    });
  } catch (_) { }
}

export function revert(player, exhausted = false) {
  if (!isTransformed(player)) return;
  const eq = player.getComponent("minecraft:equippable");
  try {
    const head = eq?.getEquipment(EquipmentSlot.Head);
    if (head && head.typeId === FORM_ITEM) eq.setEquipment(EquipmentSlot.Head, undefined);
  } catch (_) { }
  player.setDynamicProperty(PROP.form, false);
  player.removeTag(TAG_NO8);
  restoreArmor(player);
  for (const [id] of BUFFS) {
    try { player.removeEffect(id); } catch (_) { }
  }
  try { player.removeEffect("invisibility"); } catch (_) { }
  sound(player.dimension, "mob.evocation_illager.prepare_summon", player.location,
        { pitch: 0.65 });
  fxScatter(player.dimension, "kaiju8:transform_smoke", player.location, 12, 1.2);
  shake(player, 0.2, 0.4);
  if (exhausted) {
    try { player.addEffect("weakness", 300, { amplifier: 1, showParticles: true }); } catch (_) { }
    try { player.addEffect("slowness", 200, { amplifier: 0, showParticles: false }); } catch (_) { }
    tell(player, tr("kaiju8.msg.exhausted"));
  }
}

export function toggle(player) {
  if (!hasPower(player)) {
    tell(player, tr("kaiju8.msg.no_power"));
    return;
  }
  if (isTransformed(player)) revert(player); else transform(player);
}

function applyBuffs(player) {
  const kills = num(player, PROP.kills, 0);
  const bonus = kills >= 150 ? 1 : 0;
  for (const [id, amp] of BUFFS) {
    try {
      player.addEffect(id, 140, { amplifier: amp + (id === "strength" ? bonus : 0), showParticles: false });
    } catch (_) { }
  }
  // Invisibility hides the player's own skin; the worn 怪獣8号 body still renders.
  try { player.addEffect("invisibility", 140, { amplifier: 0, showParticles: false }); } catch (_) { }
}

/** Drives the 怪獣化ゲージ; runs once a second. */
export function tickTransform() {
  for (const player of allPlayers()) {
    const power = hasPower(player);
    if (!power) continue;
    let energy = num(player, PROP.energy, ENERGY_MAX);
    const transformed = isTransformed(player);

    if (transformed) {
      applyBuffs(player);
      energy -= ENERGY_DRAIN;
      if (energy <= 0) {
        energy = 0;
        revert(player, true);
      }
    } else {
      energy = Math.min(ENERGY_MAX, energy + ENERGY_REGEN);
    }
    player.setDynamicProperty(PROP.energy, energy);

    if (transformed) {
      const ratio = energy / ENERGY_MAX;
      const colour = ratio > 0.5 ? "§b" : ratio > 0.2 ? "§e" : "§c";
      actionbar(player, {
        rawtext: [
          { translate: "kaiju8.hud.form" },
          { text: ` ${colour}${bar(ratio, 12)}§r ${Math.ceil(energy)}%` },
        ],
      });
    }
  }
}

export function spendEnergy(player, amount) {
  if (!isTransformed(player)) return;
  const energy = Math.max(0, num(player, PROP.energy, ENERGY_MAX) - amount);
  player.setDynamicProperty(PROP.energy, energy);
  if (energy <= 0) revert(player, true);
}

/** Re-sync a player that logged out mid-transformation. */
export function restore(player) {
  if (!isTransformed(player)) {
    player.removeTag(TAG_NO8);
    return;
  }
  player.addTag(TAG_NO8);
  applyBuffs(player);
}

world.afterEvents.entityDie.subscribe((ev) => {
  const e = ev.deadEntity;
  if (e?.typeId !== "minecraft:player") return;
  system.run(() => {
    try {
      e.setDynamicProperty(PROP.form, false);
      e.removeTag(TAG_NO8);
      e.setDynamicProperty(PROP.energy, ENERGY_MAX * 0.4);
    } catch (_) { }
  });
});
