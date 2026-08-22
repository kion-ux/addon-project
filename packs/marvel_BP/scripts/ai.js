// NPC の振る舞い / what the mobs do when nobody is scripting them
//
// Bedrock の behavior コンポーネントだけでは「技を撃つ」表現ができないので、
// 一秒ごとに近くの NPC を見て、間合いに応じて mark_variant を切り替え、
// 対応するアニメーションと実際の効果をこちらから起こす。
import { world, system } from "@minecraft/server";
import { FX, SOUND, FAMILY, ENTITY, PROP } from "./config.js";
import {
  allPlayers, distance, forward, hasFamily, normalise, safe, sub,
} from "./util.js";
import { chord, fx, fxRing, hit, knock, shakeNearby, sound } from "./effects.js";
import { launchShard, metalOn } from "./magnetism.js";

const SENTINELS = new Set([ENTITY.sentinel, ENTITY.prime_sentinel,
                           ENTITY.sentinel_drone]);

/** mark_variant を切り替えて、対応するアニメーションを再生させる。 */
function act(entity, variant) {
  safe(() => entity.triggerEvent(`marvel:act${variant}`));
}

function nearestTarget(entity, radius) {
  const found = safe(() => entity.dimension.getEntities({
    location: entity.location, maxDistance: radius,
  })) ?? [];
  let best;
  let bestD = Infinity;
  for (const e of found) {
    if (e.id === entity.id) continue;
    const isTarget = e.typeId === "minecraft:player"
      || hasFamily(e, FAMILY.mutant) || hasFamily(e, FAMILY.brotherhood);
    if (!isTarget) continue;
    const d = distance(e.location, entity.location);
    if (d < bestD) { bestD = d; best = e; }
  }
  return best ? { entity: best, distance: bestD } : undefined;
}

const beamCooldown = new Map();

function tickSentinel(s) {
  const target = nearestTarget(s, 26);
  if (!target) {
    if (Math.random() < 0.12) act(s, 5);          // 走査
    return;
  }
  const now = system.currentTick;
  const ready = (beamCooldown.get(s.id) ?? 0) <= now;
  if (target.distance > 6 && ready) {
    beamCooldown.set(s.id, now + 110);
    act(s, 2);                                     // ビーム
    const eye = safe(() => s.getHeadLocation()) ?? s.location;
    fx(s.dimension, FX.sentinel_beam_charge, eye);
    sound(s.dimension, SOUND.sentinel_beam, s.location, { volume: 1.0, pitch: 0.9 });
    system.runTimeout(() => {
      if (!safe(() => s.isValid?.() !== false)) return;
      const t = nearestTarget(s, 30);
      if (!t) return;
      const dir = normalise(sub(
        { x: t.entity.location.x, y: t.entity.location.y + 1.0, z: t.entity.location.z },
        eye));
      const bolt = safe(() => s.dimension.spawnEntity(ENTITY.sentinel_beam,
        forward(eye, dir, 1.6)));
      let step = 0;
      const fly = system.runInterval(() => {
        if (++step > 24 || !safe(() => bolt?.isValid?.() !== false)) {
          safe(() => bolt?.remove());
          system.clearRun(fly);
          return;
        }
        const next = forward(bolt.location, dir, 1.6);
        safe(() => bolt.teleport(next));
        fx(s.dimension, FX.sentinel_beam_trail, next);
        for (const e of safe(() => s.dimension.getEntities({ location: next, maxDistance: 1.6 })) ?? []) {
          if (e.id === s.id || e.id === bolt.id) continue;
          if (hasFamily(e, FAMILY.sentinel) || hasFamily(e, FAMILY.prop)) continue;
          hit(s, e, 14);
          fx(s.dimension, FX.sentinel_beam_impact, e.location);
          safe(() => bolt.remove());
          system.clearRun(fly);
          break;
        }
      }, 1);
    }, 22);
  } else if (target.distance <= 5 && ready) {
    beamCooldown.set(s.id, now + 60);
    act(s, 1);                                     // 踏みつけ
    system.runTimeout(() => {
      if (!safe(() => s.isValid?.() !== false)) return;
      fx(s.dimension, FX.slam_ring, s.location);
      fxRing(s.dimension, FX.impact_dust, s.location, 2.4, 10, 0.1);
      shakeNearby(s.dimension, s.location, 12, 0.35, 0.4);
      for (const e of safe(() => s.dimension.getEntities({ location: s.location, maxDistance: 4.5 })) ?? []) {
        if (e.id === s.id || hasFamily(e, FAMILY.sentinel) || hasFamily(e, FAMILY.prop)) continue;
        hit(s, e, 16);
        knock(e, normalise(sub(e.location, s.location)), 1.4, 0.7);
      }
      sound(s.dimension, "random.explode", s.location, { volume: 0.9, pitch: 0.7 });
    }, 12);
  }
}

const allyCooldown = new Map();

function tickAlly(a) {
  const now = system.currentTick;
  if ((allyCooldown.get(a.id) ?? 0) > now) return;
  const found = safe(() => a.dimension.getEntities({
    location: a.location, maxDistance: 14,
  })) ?? [];
  let target;
  for (const e of found) {
    if (hasFamily(e, FAMILY.sentinel) || hasFamily(e, FAMILY.mrd)
        || e.matches?.({ families: ["monster"] })) {
      if (hasFamily(e, FAMILY.brotherhood)) continue;
      target = e;
      break;
    }
  }
  if (!target) return;
  allyCooldown.set(a.id, now + 70 + Math.floor(Math.random() * 40));
  act(a, 2);                                        // 技
  const key = a.typeId.split(":")[1];
  system.runTimeout(() => {
    if (!safe(() => a.isValid?.() !== false) || !safe(() => target.isValid?.() !== false)) return;
    const dir = normalise(sub(target.location, a.location));
    switch (key) {
      case "pyro":
        fx(a.dimension, FX.flame_wave, target.location);
        safe(() => target.setOnFire(6, true));
        hit(a, target, 12);
        break;
      case "scarlet_witch":
        fx(a.dimension, FX.hex_bolt_trail, target.location);
        hit(a, target, 14);
        safe(() => target.addEffect("weakness", 120, { amplifier: 2 }));
        break;
      case "quicksilver":
        fx(a.dimension, FX.blur_after, a.location);
        safe(() => a.teleport(forward(target.location, { x: -dir.x, y: 0, z: -dir.z }, 1.4)));
        hit(a, target, 10);
        break;
      case "avalanche":
      case "juggernaut":
      case "blob":
        fx(a.dimension, FX.slam_ring, target.location);
        fx(a.dimension, FX.quake_dust, target.location);
        hit(a, target, 18);
        knock(target, dir, 1.6, 0.7);
        shakeNearby(a.dimension, target.location, 10, 0.25, 0.4);
        break;
      case "sabretooth":
        fx(a.dimension, FX.claw_slash, target.location);
        hit(a, target, 16);
        safe(() => target.addEffect("wither", 80, { amplifier: 0 }));
        break;
      case "toad":
        fx(a.dimension, FX.tongue_slime, target.location);
        hit(a, target, 8);
        safe(() => target.addEffect("slowness", 120, { amplifier: 2 }));
        break;
      case "mystique":
        fx(a.dimension, FX.venom_drip, target.location);
        hit(a, target, 10);
        safe(() => target.addEffect("poison", 120, { amplifier: 1 }));
        break;
      default:
        hit(a, target, 10);
        break;
    }
  }, 8);
}

/** 磁力を帯びたプレイヤーの近くでは、センチネルの金属が軋む。 */
function tickMagnetPressure() {
  for (const player of allPlayers()) {
    if (!player.hasTag?.("marvel_form")) continue;
    const near = safe(() => player.dimension.getEntities({
      location: player.location, maxDistance: 10,
    })) ?? [];
    for (const e of near) {
      if (!hasFamily(e, FAMILY.sentinel)) continue;
      if (Math.random() > 0.3) continue;
      fx(e.dimension, FX.mag_spark, { x: e.location.x, y: e.location.y + 1.4, z: e.location.z });
    }
  }
}

/** 一秒ごとに呼ぶ。 */
export function tickAI() {
  for (const player of allPlayers()) {
    const near = safe(() => player.dimension.getEntities({
      location: player.location, maxDistance: 40,
    })) ?? [];
    for (const e of near) {
      if (SENTINELS.has(e.typeId)) tickSentinel(e);
      else if (hasFamily(e, FAMILY.brotherhood)) tickAlly(e);
    }
  }
  tickMagnetPressure();
}

/** センチネル撃破で熟練度が上がる。 */
world.afterEvents.entityDie.subscribe((ev) => {
  const killer = ev.damageSource?.damagingEntity;
  if (killer?.typeId !== "minecraft:player") return;
  const dead = ev.deadEntity;
  if (!dead?.typeId?.startsWith("marvel:")) return;
  if (hasFamily(dead, FAMILY.brotherhood)) return;
  system.run(() => {
    const before = safe(() => killer.getDynamicProperty(PROP.mastery)) ?? 0;
    safe(() => killer.setDynamicProperty(PROP.mastery,
      (typeof before === "number" ? before : 0) + 1));
    if (SENTINELS.has(dead.typeId)) {
      fx(dead.dimension, FX.core_break, dead.location);
      chord(dead.dimension, dead.location, [
        [SOUND.sentinel_die, 0, { volume: 1.1, pitch: 0.8 }],
        [SOUND.metal_hit, 5, { volume: 0.8, pitch: 0.7 }],
      ]);
    }
  });
});
