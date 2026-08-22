// 識別怪獣兵器 と 解放戦力 / Numbers weapons and the combat-power release rate
import { world, system, EquipmentSlot } from "@minecraft/server";
import { PROP, SUIT, RELEASE_CAP_NO_SUIT, RELEASE_SAFE } from "./config.js";
import {
  tr, tell, actionbar, num, onCooldown, setCooldown,
} from "./util.js";
import { container, selectedSlot, isTransformed, spendEnergy } from "./transform.js";
import { TECH, selected, showWheel } from "./techniques.js";
import { liftsReleaseCap, wornNumbers, fullReleaseActive } from "./numbers.js";
import { fx, sound, shake } from "./effects.js";

export function wearsFullSuit(player) {
  try {
    const eq = player.getComponent("minecraft:equippable");
    if (!eq) return false;
    const slots = [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs,
                   EquipmentSlot.Feet];
    return slots.every((s, i) => eq.getEquipment(s)?.typeId === SUIT[i]);
  } catch (_) { return false; }
}

export function releaseRate(player) {
  // 全開放中は解放戦力が 100% に固定される（ナンバーズ10）
  if (fullReleaseActive(player)) return 100;
  const raw = Math.max(1, Math.min(100, num(player, PROP.release, 10)));
  // 怪獣の身体と適合者専用装備(ナンバーズ)は上限を持たない
  if (isTransformed(player) || liftsReleaseCap(player)) return raw;
  return wearsFullSuit(player) ? raw : Math.min(raw, RELEASE_CAP_NO_SUIT);
}

export function setReleaseRate(player, value) {
  player.setDynamicProperty(PROP.release, Math.max(1, Math.min(100, Math.round(value))));
}

/** 解放戦力 turns into raw output — and into strain on the body. */
export function releaseMultiplier(player) {
  return 1 + (releaseRate(player) / 100) * 1.8;
}

export function strain(player, rate) {
  if (rate <= RELEASE_SAFE) return;
  const over = (rate - RELEASE_SAFE) / 70;
  if (isTransformed(player)) { spendEnergy(player, over * 2.2); return; }
  try {
    const sat = player.getComponent("minecraft:player.saturation");
    if (sat) sat.currentValue = Math.max(0, sat.currentValue - over * 2);
  } catch (_) { }
  if (Math.random() < over * 0.5) {
    try { player.applyDamage(Math.ceil(over * 3), { cause: "magic" }); } catch (_) { }
    tell(player, tr("kaiju8.msg.strain"));
    shake(player, 0.12, 0.25, "rotational");
  }
}

export function damageHeldItem(player, amount) {
  if (!amount) return;
  try {
    const inv = container(player);
    if (!inv) return;
    const slot = selectedSlot(player);
    const item = inv.getItem(slot);
    if (!item) return;
    const dur = item.getComponent("minecraft:durability");
    if (!dur) return;
    if (dur.damage + amount >= dur.maxDurability) {
      inv.setItem(slot, undefined);
      sound(player.dimension, "random.break", player.location);
      return;
    }
    dur.damage += amount;
    inv.setItem(slot, item);
  } catch (_) { }
}

/** Right-click: run whichever 技 is currently selected for the held weapon. */
export function useTechnique(player, typeId) {
  const list = TECH[typeId];
  if (!list) return false;
  const tech = selected(player, typeId);
  if (!tech) return false;

  if (tech.form && !isTransformed(player)) {
    tell(player, tr("kaiju8.msg.form_only"));
    return true;
  }
  // 7式「十二単」はナンバーズ10の全開放状態でのみ解禁される
  if (tech.requires && wornNumbers(player) !== tech.requires) {
    tell(player, {
      rawtext: [{
        translate: "kaiju8.msg.requires_numbers",
        with: { rawtext: [{ translate: `item.${tech.requires}` }] },
      }],
    });
    return true;
  }
  if (onCooldown(player.id, typeId)) {
    sound(player.dimension, "note.bass", player.location, { pitch: 0.7, volume: 0.4 });
    return true;
  }
  const rate = releaseRate(player);
  const cd = Math.max(4, Math.round(tech.cd * (1 - rate / 260)));
  setCooldown(player.id, typeId, cd + (tech.charge ?? 0));

  const ctx = { mult: releaseMultiplier(player), rate };
  try { tech.run(player, ctx); } catch (_) { }

  if (tech.energy) spendEnergy(player, tech.energy);
  damageHeldItem(player, tech.wear ?? 0);
  strain(player, rate);
  if (rate > 40) {
    fx(player.dimension, "kaiju8:release_aura",
       { x: player.location.x, y: player.location.y + 1.0, z: player.location.z });
  }
  actionbar(player, {
    rawtext: [
      { text: "§b" }, { translate: tech.name },
      { text: `§r  §7解放戦力 §b${rate}%` },
    ],
  });
  return true;
}

/** 切り返し: sneak while holding a weapon to rotate through its 技. */
export function cycleTechnique(player, typeId, tech) {
  sound(player.dimension, "random.click", player.location, { pitch: 1.6, volume: 0.5 });
  fx(player.dimension, "kaiju8:release_burst",
     { x: player.location.x, y: player.location.y + 1.2, z: player.location.z });
  showWheel(player, typeId, releaseRate(player));
}

/** Ordinary melee swings also scale with 解放戦力. */
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (player?.typeId !== "minecraft:player") return;
  const target = ev.hitEntity;
  if (!target) return;
  let held;
  try { held = container(player)?.getItem(selectedSlot(player)); } catch (_) { return; }
  if (!held || !(held.typeId in TECH)) return;
  const rate = releaseRate(player);
  if (rate <= 10) return;
  const bonus = Math.round((releaseMultiplier(player) - 1) * 6);
  if (bonus <= 0) return;
  system.run(() => {
    try {
      target.applyDamage(bonus, { cause: "entityAttack", damagingEntity: player });
    } catch (_) { }
  });
  strain(player, rate);
});
