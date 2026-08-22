// 識別怪獣兵器 と 解放戦力 / Numbers weapons and the combat-power release rate
import { world, system, EquipmentSlot } from "@minecraft/server";
import { PROP, SUIT, RELEASE_CAP_NO_SUIT, RELEASE_SAFE } from "./config.js";
import {
  tr, tell, actionbar, num, onCooldown, setCooldown,
} from "./util.js";
import { container, selectedSlot, isTransformed, spendEnergy } from "./transform.js";
import { TECH, listFor, selected, showWheel } from "./techniques.js";
import { liftsReleaseCap, wornNumbers, fullReleaseActive } from "./numbers.js";
import { fx, fxArc, fxScatter, sound, shake } from "./effects.js";

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
  const list = listFor(player, typeId);
  if (!list || !list.length) return false;
  const tech = selected(player, typeId);
  if (!tech) return false;

  // ホイールがナンバーズの固有能力に乗っている場合。武器の耐久は減らず、
  // クールダウンは機体側で共有する（武器を持ち替えて連打できないように）
  if (tech.numbers) return useNumbersAbility(player, tech);

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

function useNumbersAbility(player, tech) {
  if (wornNumbers(player) !== tech.numbers) {
    tell(player, {
      rawtext: [{
        translate: "kaiju8.msg.requires_numbers",
        with: { rawtext: [{ translate: `item.${tech.numbers}` }] },
      }],
    });
    return true;
  }
  if (onCooldown(player.id, "numbers")) {
    sound(player.dimension, "note.bass", player.location, { pitch: 0.6, volume: 0.4 });
    return true;
  }
  setCooldown(player.id, "numbers", tech.cd);
  try { tech.run(player, { mult: releaseMultiplier(player), rate: releaseRate(player) }); }
  catch (_) { }
  actionbar(player, {
    rawtext: [
      { text: "§d" }, { translate: tech.name },
      { text: "§r  §7" }, { translate: `item.${tech.numbers}` },
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

// 通常攻撃の当たり演出。武器ごとに斬り口を変え、三振りに合わせて弧の形も回す。
// クライアント側の v.alt と厳密に同期はしないが、連撃すれば同じように回る。
const SWING_FX = {
  "kaiju8:combat_knife":    { arcs: ["kaiju8:slash_air", "kaiju8:slash_air",
                                     "kaiju8:slash_cross"],
                              r: 1.5, sweep: 110, hit: "kaiju8:slash_scatter",
                              snd: "mob.ravager.bite", pitch: 1.45, n: 3 },
  "kaiju8:twin_sw2033":     { arcs: ["kaiju8:slash_air", "kaiju8:slash_cross",
                                     "kaiju8:slash_scatter"],
                              r: 2.1, sweep: 150, hit: "kaiju8:slash_scatter",
                              snd: "mob.ravager.bite", pitch: 1.6, n: 4 },
  "kaiju8:blade_sw1023":    { arcs: ["kaiju8:slash_heavy", "kaiju8:slash_air",
                                     "kaiju8:slash_cross"],
                              r: 2.6, sweep: 165, hit: "kaiju8:slash_scatter",
                              snd: "mob.ravager.bite", pitch: 1.15, n: 4 },
  "kaiju8:axe_03ax":        { arcs: ["kaiju8:axe_arc", "kaiju8:axe_crescent",
                                     "kaiju8:axe_arc"],
                              r: 2.8, sweep: 120, hit: "kaiju8:crack_burst",
                              snd: "random.anvil_land", pitch: 1.3, n: 3 },
  "kaiju8:gunblade_gs3305": { arcs: ["kaiju8:slash_heavy", "kaiju8:burst_slash",
                                     "kaiju8:slash_heavy"],
                              r: 2.9, sweep: 130, hit: "kaiju8:cauterize",
                              snd: "random.anvil_land", pitch: 1.5, n: 4 },
  "kaiju8:no8_power":       { arcs: ["kaiju8:fist_shock", "kaiju8:fist_shock",
                                     "kaiju8:shock_ring"],
                              r: 1.2, sweep: 90, hit: "kaiju8:energy_boost",
                              snd: "mob.ravager.stun", pitch: 0.85, n: 3 },
  "kaiju8:df_rifle":        { arcs: ["kaiju8:muzzle_sparks"], r: 1.1, sweep: 60,
                              hit: "kaiju8:impact_dust", snd: "random.anvil_land",
                              pitch: 1.8, n: 2 },
  "kaiju8:df_bazooka":      { arcs: ["kaiju8:muzzle_smoke"], r: 1.3, sweep: 70,
                              hit: "kaiju8:impact_dust", snd: "random.anvil_land",
                              pitch: 0.9, n: 3 },
  "kaiju8:df_pistol":       { arcs: ["kaiju8:muzzle_sparks"], r: 0.9, sweep: 60,
                              hit: "kaiju8:impact_dust", snd: "random.anvil_land",
                              pitch: 2.0, n: 2 },
  "kaiju8:cannon_t25":      { arcs: ["kaiju8:muzzle_smoke"], r: 1.4, sweep: 70,
                              hit: "kaiju8:impact_dust", snd: "random.anvil_land",
                              pitch: 0.8, n: 3 },
};

const swingTurn = new Map();     // playerId -> 何振り目か

function swingSignature(player, typeId, target, rate) {
  const sig = SWING_FX[typeId];
  if (!sig) return;
  const turn = ((swingTurn.get(player.id) ?? -1) + 1) % 3;
  swingTurn.set(player.id, turn);
  const head = player.getHeadLocation();
  const dir = player.getViewDirection();
  const origin = { x: head.x, y: head.y - 0.25, z: head.z };
  const arc = sig.arcs[turn % sig.arcs.length];
  // 三振り目だけ弧を反対に傾けて、同じ形が続かないようにする
  fxArc(player.dimension, arc, origin, dir, sig.r, sig.sweep, sig.n,
        turn === 2 ? -0.35 : 0.25);
  fxScatter(player.dimension, sig.hit,
            { x: target.location.x, y: target.location.y + 1.0, z: target.location.z },
            rate >= 60 ? 5 : 3, 0.6);
  sound(player.dimension, sig.snd, player.location,
        { pitch: sig.pitch + (turn - 1) * 0.08, volume: 0.7 });
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
  system.run(() => {
    try { swingSignature(player, held.typeId, target, rate); } catch (_) { }
  });
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
