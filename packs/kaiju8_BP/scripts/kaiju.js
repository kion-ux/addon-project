// 怪獣の要塞度表示・討伐記録・識別怪獣のAI補強
import { world, system } from "@minecraft/server";
import { FORTITUDE, IDENTIFIED, PROP, RANKS } from "./config.js";
import {
  tr, tell, actionbar, playSound, burst, hasFamily, health, num, bar,
  allPlayers, distance,
} from "./util.js";

export function fortitudeOf(entity) {
  return FORTITUDE[entity.typeId];
}

export function rankKey(kills) {
  let key = RANKS[0][1];
  for (const [threshold, k] of RANKS) if (kills >= threshold) key = k;
  return key;
}

function objective() {
  try {
    return world.scoreboard.getObjective("kaiju8_kills")
      ?? world.scoreboard.addObjective("kaiju8_kills", "討伐数");
  } catch (_) { return undefined; }
}

/** 要塞度スキャン — shown whenever a player lands a hit on a kaiju. */
world.afterEvents.entityHurt.subscribe((ev) => {
  const target = ev.hurtEntity;
  const source = ev.damageSource?.damagingEntity;
  if (!target || source?.typeId !== "minecraft:player") return;
  const fort = fortitudeOf(target);
  if (fort === undefined && !hasFamily(target, "kaiju")) return;
  const hp = health(target);
  if (!hp) return;
  const ratio = hp.max > 0 ? hp.now / hp.max : 0;
  const colour = IDENTIFIED.has(target.typeId) ? "§c" : ratio > 0.5 ? "§a" : "§e";
  actionbar(source, {
    rawtext: [
      { translate: `entity.${target.typeId}.name` },
      { text: `  §7要塞度§r ${IDENTIFIED.has(target.typeId) ? "§c" : "§6"}${(fort ?? 1.0).toFixed(1)}§r  ` },
      { text: `${colour}${bar(ratio, 10)}§r ${hp.now}/${hp.max}` },
    ],
  });
});

/** 討伐記録 — subjugation log. */
world.afterEvents.entityDie.subscribe((ev) => {
  const dead = ev.deadEntity;
  const killer = ev.damageSource?.damagingEntity;
  if (!dead || killer?.typeId !== "minecraft:player") return;
  if (fortitudeOf(dead) === undefined && !hasFamily(dead, "kaiju")) return;

  system.run(() => {
    const kills = num(killer, PROP.kills, 0) + 1;
    killer.setDynamicProperty(PROP.kills, kills);
    try { objective()?.setScore(killer, kills); } catch (_) { }
    const before = rankKey(kills - 1);
    const now = rankKey(kills);
    tell(killer, {
      rawtext: [
        { translate: "kaiju8.msg.subjugated", with: { rawtext: [{ translate: `entity.${dead.typeId}.name` }] } },
        { text: `  §7(${kills})` },
      ],
    });
    if (before !== now) {
      playSound(killer.dimension, "random.levelup", killer.location);
      try {
        killer.onScreenDisplay.setTitle(tr("kaiju8.title.promoted"), {
          fadeInDuration: 6, stayDuration: 40, fadeOutDuration: 14,
          subtitle: { rawtext: [{ translate: now }] },
        });
      } catch (_) { }
    }
    if (IDENTIFIED.has(dead.typeId)) {
      for (const p of allPlayers()) {
        tell(p, {
          rawtext: [{
            translate: "kaiju8.msg.identified_down",
            with: { rawtext: [{ translate: `entity.${dead.typeId}.name` }] },
          }],
        });
      }
    }
  });
});

let phase = 0;

/** Extra behaviour for the identified kaiju, once a second. */
export function tickKaiju() {
  phase++;
  const seen = new Set();
  for (const player of allPlayers()) {
    let kaiju;
    try {
      kaiju = player.dimension.getEntities({
        location: player.location, maxDistance: 72, families: ["identified_kaiju"],
      });
    } catch (_) { continue; }
    for (const k of kaiju) {
      if (seen.has(k.id)) continue;
      seen.add(k.id);
      try { driveIdentified(k); } catch (_) { }
    }
  }
}

function driveIdentified(k) {
  // 咆哮 — every so often, and it staggers anyone close by.
  if (phase % 27 === 0 && Math.random() < 0.5) {
    try { k.triggerEvent("kaiju8:roar"); } catch (_) { }
    playSound(k.dimension, "mob.enderdragon.growl", k.location, { volume: 2.0, pitch: 0.6 });
    for (const p of allPlayers()) {
      if (p.dimension.id !== k.dimension.id) continue;
      if (distance(p.location, k.location) > 14) continue;
      try { p.addEffect("slowness", 40, { amplifier: 1, showParticles: true }); } catch (_) { }
      try { p.addEffect("nausea", 60, { amplifier: 0, showParticles: false }); } catch (_) { }
    }
  }

  if (k.typeId === "kaiju8:kaiju_no9") {
    // 怪獣9号 — regenerates and keeps producing 余獣.
    try { k.addEffect("regeneration", 60, { amplifier: 1, showParticles: false }); } catch (_) { }
    if (phase % 9 === 0) {
      let brood = 0;
      try {
        brood = k.dimension.getEntities({
          location: k.location, maxDistance: 26, type: "kaiju8:yoju",
        }).length;
      } catch (_) { }
      if (brood < 5) {
        for (let i = 0; i < 2; i++) {
          const loc = {
            x: k.location.x + (Math.random() - 0.5) * 6,
            y: k.location.y + 1,
            z: k.location.z + (Math.random() - 0.5) * 6,
          };
          try { k.dimension.spawnEntity("kaiju8:yoju", loc); } catch (_) { }
          burst(k.dimension, "minecraft:basic_smoke_particle", loc, 8, 0.8);
        }
        playSound(k.dimension, "mob.evocation_illager.prepare_summon", k.location, { pitch: 0.6 });
      }
    }
  }

  if (k.typeId === "kaiju8:kaiju_no10" && phase % 5 === 0) {
    // 怪獣10号 — keeps to the air.
    try {
      if (k.isOnGround) k.applyKnockback?.(0, 0, 0, 0.9);
    } catch (_) { }
  }

  if (k.typeId === "kaiju8:kaiju_no8" && phase % 3 === 0) {
    try { k.addEffect("regeneration", 60, { amplifier: 0, showParticles: false }); } catch (_) { }
  }
}
