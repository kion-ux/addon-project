// 怪獣災害警報 / Kaiju disaster alerts
import { world, system } from "@minecraft/server";
import { PROP } from "./config.js";
import { tr, tell, playSound, burst, num, allPlayers } from "./util.js";

const CHECK_SECONDS = 45;
const BASE_CHANCE = 0.18;

export function alertsEnabled() {
  const v = world.getDynamicProperty(PROP.alerts);
  return typeof v === "boolean" ? v : true;
}

export function setAlerts(on) {
  world.setDynamicProperty(PROP.alerts, !!on);
}

function groundNear(player, minDist, maxDist) {
  const angle = Math.random() * Math.PI * 2;
  const dist = minDist + Math.random() * (maxDist - minDist);
  const x = Math.floor(player.location.x + Math.cos(angle) * dist);
  const z = Math.floor(player.location.z + Math.sin(angle) * dist);
  const startY = Math.floor(player.location.y) + 10;
  for (let y = startY; y > startY - 26; y--) {
    let block, above, above2;
    try {
      block = player.dimension.getBlock({ x, y, z });
      above = player.dimension.getBlock({ x, y: y + 1, z });
      above2 = player.dimension.getBlock({ x, y: y + 2, z });
    } catch (_) { return undefined; }
    if (!block || !above || !above2) return undefined;
    if (block.isSolid && above.isAir && above2.isAir) {
      return { x: x + 0.5, y: y + 1, z: z + 0.5 };
    }
  }
  return undefined;
}

/** Spawns a wave sized to how experienced the player is. */
export function spawnWave(player, forced = false) {
  if (player.dimension.id !== "minecraft:overworld" && !forced) return false;
  const origin = groundNear(player, 22, 40);
  if (!origin) return false;

  const kills = num(player, PROP.kills, 0);
  const swarm = 3 + Math.min(7, Math.floor(kills / 25));
  const bringHonju = kills >= 20 || forced;

  for (let i = 0; i < swarm; i++) {
    const loc = {
      x: origin.x + (Math.random() - 0.5) * 10,
      y: origin.y,
      z: origin.z + (Math.random() - 0.5) * 10,
    };
    try { player.dimension.spawnEntity("kaiju8:yoju", loc); } catch (_) { }
  }
  if (bringHonju) {
    try { player.dimension.spawnEntity("kaiju8:honju", origin); } catch (_) { }
  }
  burst(player.dimension, "minecraft:large_explosion", origin, 4, 2.0);
  playSound(player.dimension, "mob.enderdragon.growl", origin, { volume: 3.0, pitch: 0.55 });

  for (const p of allPlayers()) {
    if (p.dimension.id !== player.dimension.id) continue;
    playSound(p.dimension, "note.pling", p.location, { pitch: 0.6 });
    try {
      p.onScreenDisplay.setTitle(tr("kaiju8.title.alert"), {
        fadeInDuration: 6, stayDuration: 44, fadeOutDuration: 16,
        subtitle: tr("kaiju8.title.alert_sub"),
      });
    } catch (_) { }
    tell(p, tr("kaiju8.msg.alert", bringHonju ? "本獣" : "余獣", String(swarm)));
  }
  return true;
}

let counter = 0;

export function tickAlerts() {
  counter++;
  if (counter % CHECK_SECONDS !== 0) return;
  if (!alertsEnabled()) return;
  const players = allPlayers().filter((p) => p.dimension.id === "minecraft:overworld");
  if (!players.length) return;
  const player = players[Math.floor(Math.random() * players.length)];
  const chance = BASE_CHANCE + Math.min(0.25, num(player, PROP.kills, 0) / 400);
  if (Math.random() > chance) return;
  spawnWave(player);
}

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (ev.id === "kaiju8:alert") {
    const src = ev.sourceEntity;
    if (src?.typeId === "minecraft:player") spawnWave(src, true);
  } else if (ev.id === "kaiju8:alerts_on") {
    setAlerts(true);
  } else if (ev.id === "kaiju8:alerts_off") {
    setAlerts(false);
  }
}, { namespaces: ["kaiju8"] });
