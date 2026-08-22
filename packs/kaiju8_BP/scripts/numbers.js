// ===========================================================================
//  識別怪獣兵器（ナンバーズ）
//  「持つ」武器ではなく「着る」武器。頭スロットに装備すると全身モデルが
//  差し替わり、機体ごとの能力が常時発動する。
// ===========================================================================
import { world, system, EquipmentSlot } from "@minecraft/server";
import { tr, tell, allPlayers, knockback, hasFamily, distance } from "./util.js";
import {
  fx, fxRing, fxScatter, sound, shake, shakeNearby, targetsNear, hit, bleed,
} from "./effects.js";

export const NUMBERS = {
  "kaiju8:numbers_1": {
    id: "1",
    // 全身のねじ穴から突出する眼球 — 索敵と反応速度
    tick(player) {
      try {
        player.addEffect("night_vision", 260, { amplifier: 0, showParticles: false });
        player.addEffect("speed", 60, { amplifier: 0, showParticles: false });
      } catch (_) { }
      if (system.currentTick % 40 !== 0) return;
      for (const t of targetsNear(player, 24)) {
        if (!hasFamily(t, "kaiju")) continue;
        fx(player.dimension, "kaiju8:regen_knit",
           { x: t.location.x, y: t.location.y + 1.4, z: t.location.z });
      }
    },
    onHit(player, target) {
      try { hit(player, target, 4); } catch (_) { }
    },
  },
  "kaiju8:numbers_2": {
    id: "2",
    // 巨大ガントレット — 拳から指向性エネルギー弾とソニックブーム
    tick(player) {
      try {
        player.addEffect("strength", 60, { amplifier: 1, showParticles: false });
      } catch (_) { }
    },
    onHit(player, target) {
      fx(player.dimension, "kaiju8:fist_shock",
         { x: target.location.x, y: target.location.y + 1.0, z: target.location.z });
      for (const t of targetsNear(target, 3.4)) {
        if (t.id === target.id) continue;
        if (hit(player, t, 7)) bleed(t);
      }
      const dx = target.location.x - player.location.x;
      const dz = target.location.z - player.location.z;
      const len = Math.hypot(dx, dz) || 1;
      knockback(target, dx / len, dz / len, 1.6, 0.35);
      sound(player.dimension, "mob.ravager.stun", player.location,
            { pitch: 0.7, volume: 1.0 });
      shake(player, 0.14, 0.2);
    },
  },
  "kaiju8:numbers_4": {
    id: "4",
    // ナンバーズ唯一の飛行能力。腕のリパルサー
    tick(player) {
      try {
        player.addEffect("slow_falling", 60, { amplifier: 0, showParticles: false });
        player.addEffect("jump_boost", 60, { amplifier: 2, showParticles: false });
      } catch (_) { }
      let onGround = true;
      try { onGround = player.isOnGround; } catch (_) { }
      if (!onGround && system.currentTick % 6 === 0) {
        fxScatter(player.dimension, "kaiju8:release_aura", player.location, 4, 0.7);
      }
    },
    onHit(player, target) {
      fxScatter(player.dimension, "kaiju8:socket_burst", target.location, 6, 0.8);
      for (const t of targetsNear(target, 3.0)) {
        if (hit(player, t, 6)) bleed(t);
      }
      sound(player.dimension, "random.explode", player.location,
            { pitch: 1.4, volume: 0.7 });
    },
  },
  "kaiju8:numbers_6": {
    id: "6",
    // 怪獣6号由来の凍結。触れた箇所を広範囲凍結させる
    tick(player) {
      try {
        player.addEffect("fire_resistance", 60, { amplifier: 0, showParticles: false });
      } catch (_) { }
    },
    onHit(player, target) {
      try {
        target.addEffect("slowness", 140, { amplifier: 3, showParticles: true });
        target.addEffect("weakness", 140, { amplifier: 0, showParticles: false });
      } catch (_) { }
      fxScatter(player.dimension, "kaiju8:socket_freeze",
                { x: target.location.x, y: target.location.y + 0.8,
                  z: target.location.z }, 8, 0.9);
      for (const t of targetsNear(target, 3.2)) {
        try { t.addEffect("slowness", 80, { amplifier: 2, showParticles: true }); }
        catch (_) { }
      }
      sound(player.dimension, "random.glass", player.location, { pitch: 1.6 });
    },
  },
  "kaiju8:numbers_10": {
    id: "10",
    // 意思を持つ兵器。尾が装着者の意思と無関係に第3の刃として動く
    tick(player) {
      if (system.currentTick % 40 !== 0) return;
      let nearest;
      let best = 99;
      for (const t of targetsNear(player, 6.0)) {
        if (!hasFamily(t, "kaiju")) continue;
        const d = distance(player.location, t.location);
        if (d < best) { best = d; nearest = t; }
      }
      if (!nearest) return;
      if (hit(player, nearest, 9)) bleed(nearest);
      fx(player.dimension, "kaiju8:slash_air",
         { x: nearest.location.x, y: nearest.location.y + 1.0, z: nearest.location.z });
      sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.5 });
    },
    onHit() { },
  },
};

const worn = new Map();     // playerId -> item id

export function wornNumbers(player) {
  try {
    const eq = player.getComponent("minecraft:equippable");
    const head = eq?.getEquipment(EquipmentSlot.Head);
    const id = head?.typeId;
    return id && NUMBERS[id] ? id : undefined;
  } catch (_) { return undefined; }
}

/** 適合者専用装備なので、着ている間は解放戦力の上限が外れる。 */
export function liftsReleaseCap(player) {
  return wornNumbers(player) !== undefined;
}

export function tickNumbers() {
  for (const player of allPlayers()) {
    const id = wornNumbers(player);
    const before = worn.get(player.id);
    if (id !== before) {
      if (id) {
        worn.set(player.id, id);
        tell(player, {
          rawtext: [{
            translate: "kaiju8.msg.numbers_on",
            with: { rawtext: [{ translate: `item.${id}` }] },
          }],
        });
        tell(player, tr(`kaiju8.numbers.${NUMBERS[id].id}`));
        sound(player.dimension, "beacon.activate", player.location, { pitch: 1.2 });
        fxRing(player.dimension, "kaiju8:release_burst", player.location, 1.4, 10, 0.6);
        shake(player, 0.22, 0.4);
      } else {
        worn.delete(player.id);
        tell(player, tr("kaiju8.msg.numbers_off"));
      }
    }
    if (!id) continue;
    try { NUMBERS[id].tick(player); } catch (_) { }
  }
}

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (player?.typeId !== "minecraft:player") return;
  const target = ev.hitEntity;
  if (!target) return;
  const id = wornNumbers(player);
  if (!id) return;
  system.run(() => {
    try { NUMBERS[id].onHit(player, target); } catch (_) { }
  });
});
