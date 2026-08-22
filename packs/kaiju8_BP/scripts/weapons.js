// 識別怪獣兵器 と 解放戦力 / Numbers weapons and the combat-power release rate
import { world, system, EquipmentSlot } from "@minecraft/server";
import {
  PROP, SUIT, RELEASE_CAP_NO_SUIT, RELEASE_SAFE, WEAPON_COOLDOWN,
} from "./config.js";
import {
  tr, tell, actionbar, playSound, burst, particle, knockback, hasFamily,
  num, forward, onCooldown, setCooldown,
} from "./util.js";
import { container, selectedSlot, isTransformed, spendEnergy } from "./transform.js";

export function wearsFullSuit(player) {
  try {
    const eq = player.getComponent("minecraft:equippable");
    if (!eq) return false;
    const slots = [EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet];
    return slots.every((s, i) => eq.getEquipment(s)?.typeId === SUIT[i]);
  } catch (_) { return false; }
}

export function releaseRate(player) {
  const raw = Math.max(1, Math.min(100, num(player, PROP.release, 10)));
  return wearsFullSuit(player) ? raw : Math.min(raw, RELEASE_CAP_NO_SUIT);
}

export function setReleaseRate(player, value) {
  player.setDynamicProperty(PROP.release, Math.max(1, Math.min(100, Math.round(value))));
}

/** 解放戦力 turns into raw output — and into strain on the body. */
export function releaseMultiplier(player) {
  return 1 + (releaseRate(player) / 100) * 1.8;
}

function strain(player, rate) {
  if (rate <= RELEASE_SAFE) return;
  const over = (rate - RELEASE_SAFE) / 70;
  if (isTransformed(player)) { spendEnergy(player, over * 3); return; }
  try {
    const hunger = player.getComponent("minecraft:player.saturation");
    if (hunger) hunger.currentValue = Math.max(0, hunger.currentValue - over * 2);
  } catch (_) { }
  if (Math.random() < over * 0.5) {
    try { player.applyDamage(Math.ceil(over * 3), { cause: "magic" }); } catch (_) { }
    tell(player, tr("kaiju8.msg.strain"));
  }
}

function damageHeldItem(player, amount) {
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
      playSound(player.dimension, "random.break", player.location);
      return;
    }
    dur.damage += amount;
    inv.setItem(slot, item);
  } catch (_) { }
}

function shoot(player, projectileId, speed, spread = 0) {
  const dir = player.getViewDirection();
  const head = player.getHeadLocation();
  const origin = forward(head, dir, 0.9);
  let proj;
  try { proj = player.dimension.spawnEntity(projectileId, origin); } catch (_) { return; }
  try {
    const pc = proj.getComponent("minecraft:projectile");
    if (pc) {
      pc.owner = player;
      pc.shoot({
        x: (dir.x + (Math.random() - 0.5) * spread) * speed,
        y: (dir.y + (Math.random() - 0.5) * spread) * speed,
        z: (dir.z + (Math.random() - 0.5) * spread) * speed,
      });
    } else {
      proj.applyImpulse?.({ x: dir.x * speed * 0.1, y: dir.y * speed * 0.1, z: dir.z * speed * 0.1 });
    }
  } catch (_) { }
  return proj;
}

function nearbyTargets(player, radius) {
  try {
    return player.dimension.getEntities({
      location: player.location, maxDistance: radius, excludeTypes: ["minecraft:player", "minecraft:item"],
    }).filter((e) => e.id !== player.id && !hasFamily(e, "defense_force"));
  } catch (_) { return []; }
}

function coneHit(player, radius, dot, damage, kb) {
  const dir = player.getViewDirection();
  let hits = 0;
  for (const target of nearbyTargets(player, radius)) {
    const to = {
      x: target.location.x - player.location.x,
      y: target.location.y - player.location.y,
      z: target.location.z - player.location.z,
    };
    const len = Math.hypot(to.x, to.y, to.z) || 1;
    const d = (to.x * dir.x + to.y * dir.y + to.z * dir.z) / len;
    if (d < dot) continue;
    try { target.applyDamage(damage, { cause: "entityAttack", damagingEntity: player }); } catch (_) { }
    if (kb) knockback(target, to.x / len, to.z / len, kb, 0.35);
    burst(player.dimension, "minecraft:critical_hit_emitter", target.location, 4, 0.7);
    hits++;
  }
  return hits;
}

const ABILITIES = {
  // 識別怪獣兵器2号 — 亜白ミナの大型狙撃砲
  "kaiju8:weapon_no2": (player, mult) => {
    shoot(player, "kaiju8:rifle_beam", 3.4);
    playSound(player.dimension, "mob.wither.shoot", player.location, { pitch: 0.7, volume: 1.2 });
    burst(player.dimension, "minecraft:critical_hit_emitter", forward(player.getHeadLocation(), player.getViewDirection(), 1.5), 6, 0.35);
    damageHeldItem(player, 2);
    return "kaiju8.msg.fire_no2";
  },
  // 討伐隊 制式銃
  "kaiju8:df_rifle": (player) => {
    shoot(player, "kaiju8:df_bullet", 3.0, 0.05);
    playSound(player.dimension, "random.explode", player.location, { pitch: 1.8, volume: 0.4 });
    damageHeldItem(player, 1);
    return null;
  },
  // 識別怪獣兵器4号 — 保科の双刃刀による高速斬撃
  "kaiju8:weapon_no4": (player, mult) => {
    const dir = player.getViewDirection();
    knockback(player, dir.x, dir.z, 2.4, 0.25);
    system.runTimeout(() => {
      const hits = coneHit(player, 5.5, 0.1, Math.round(9 * mult), 0.4)
                 + coneHit(player, 5.5, 0.1, Math.round(9 * mult), 0.0);
      playSound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.5 });
      if (hits) burst(player.dimension, "minecraft:critical_hit_emitter", player.location, 10, 2.0);
    }, 4);
    playSound(player.dimension, "item.trident.riptide_1", player.location, { pitch: 1.4 });
    damageHeldItem(player, 3);
    return "kaiju8.msg.slash";
  },
  // 四ノ宮キコルの大型戦斧 — 叩きつけ
  "kaiju8:battle_axe": (player, mult) => {
    const hits = coneHit(player, 6.0, -0.6, Math.round(16 * mult), 1.4);
    playSound(player.dimension, "random.anvil_land", player.location, { pitch: 0.6, volume: 1.4 });
    burst(player.dimension, "minecraft:large_explosion", player.location, 3, 1.6);
    for (let i = 0; i < 24; i++) {
      const a = (i / 24) * Math.PI * 2;
      particle(player.dimension, "minecraft:basic_crit_particle", {
        x: player.location.x + Math.cos(a) * 4, y: player.location.y + 0.3,
        z: player.location.z + Math.sin(a) * 4,
      });
    }
    damageHeldItem(player, 4);
    return hits ? "kaiju8.msg.smash" : null;
  },
  // 討伐隊 制式刀 — 一閃
  "kaiju8:combat_blade": (player, mult) => {
    coneHit(player, 4.5, 0.25, Math.round(8 * mult), 0.6);
    playSound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.2 });
    damageHeldItem(player, 2);
    return null;
  },
};

export function useWeapon(player, typeId) {
  const ability = ABILITIES[typeId];
  if (!ability) return false;
  const cd = WEAPON_COOLDOWN[typeId] ?? 20;
  const rate = releaseRate(player);
  const scaled = Math.max(4, Math.round(cd * (1 - rate / 250)));
  if (onCooldown(player.id, typeId)) return true;
  setCooldown(player.id, typeId, scaled);
  const msg = ability(player, releaseMultiplier(player));
  strain(player, rate);
  if (msg) {
    actionbar(player, {
      rawtext: [{ translate: msg }, { text: `  §b解放戦力 ${rate}%` }],
    });
  }
  return true;
}

/** Melee swings also scale with 解放戦力 while a Numbers weapon is held. */
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (player?.typeId !== "minecraft:player") return;
  const target = ev.hitEntity;
  if (!target?.isValid?.() && target?.isValid !== undefined) return;
  let held;
  try {
    held = container(player)?.getItem(selectedSlot(player));
  } catch (_) { return; }
  if (!held || !(held.typeId in WEAPON_COOLDOWN)) return;
  const rate = releaseRate(player);
  if (rate <= 10) return;
  const bonus = Math.round((releaseMultiplier(player) - 1) * 6);
  if (bonus <= 0) return;
  system.run(() => {
    try { target.applyDamage(bonus, { cause: "entityAttack", damagingEntity: player }); } catch (_) { }
  });
  strain(player, rate);
});
