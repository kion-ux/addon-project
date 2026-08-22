// ===========================================================================
//  マーベル・ミュータント / 磁界の帝王
//  Marvel Mutants — Master of Magnetism, for Minecraft Bedrock
//
//  マグニートーとブラザーフッド。地上のあらゆる金属を意のままに操り、
//  ミュータント狩りのセンチネルを鉄屑に変える。
// ===========================================================================
import { world, system } from "@minecraft/server";
import { ITEM, TECH_BY_ITEM, PROP, ALLY_TECH, FX, SOUND } from "./config.js";
import { allPlayers, safe, setProp, str, tell, tr } from "./util.js";
import { fx } from "./effects.js";
import {
  awaken, heroOf, hud, isMutant, isTransformed, restore, sweepFormItems,
  tickForm, tickTransform, toggle,
} from "./transform.js";
import { useTechnique, cooldowns } from "./techniques.js";
import { useAllyTechnique } from "./powers.js";
import { tickMobility } from "./mobility.js";
import { tickAI } from "./ai.js";
import { openTerminal, pickTechnique, scanMetal } from "./ui.js";
import { tickProjectiles } from "./magnetism.js";
import { hit, fx as spark } from "./effects.js";

const swallowing = new Map();

function handleUse(player, itemStack) {
  if (!player || !itemStack) return;
  const id = itemStack.typeId;
  const sneaking = safe(() => player.isSneaking) === true;

  // --- 変身 ---------------------------------------------------------
  if (id === ITEM.magneto_helmet || id === ITEM.brotherhood_pin) {
    if (sneaking) openTerminal(player); else toggle(player);
    return;
  }
  // --- 端末 ---------------------------------------------------------
  if (id === ITEM.cerebro) {
    if (sneaking) openTerminal(player); else scanMetal(player);
    return;
  }
  // --- 招集 ---------------------------------------------------------
  if (id === ITEM.brotherhood_beacon) {
    openTerminal(player);
    return;
  }
  // --- 技 -----------------------------------------------------------
  const techKey = TECH_BY_ITEM[id];
  if (techKey) {
    if (sneaking) { pickTechnique(player); return; }
    const hero = heroOf(player);
    if (hero === "magneto") {
      useTechnique(player, techKey);
    } else {
      // ブラザーフッドは技アイテムの並び順で 3 種を割り当てる
      const kit = ALLY_TECH[hero] ?? [];
      const index = Object.keys(TECH_BY_ITEM).indexOf(id) % Math.max(1, kit.length);
      useAllyTechnique(player, index);
    }
  }
}

world.afterEvents.itemUse.subscribe((ev) => {
  const player = ev.source;
  if (player?.typeId !== "minecraft:player") return;
  if (ev.itemStack?.typeId === ITEM.x_gene) {
    swallowing.set(player.id, system.currentTick);
    system.runTimeout(() => swallowing.delete(player.id), 120);
    return;
  }
  handleUse(player, ev.itemStack);
});

if (world.afterEvents.itemCompleteUse) {
  world.afterEvents.itemCompleteUse.subscribe((ev) => {
    const player = ev.source;
    if (player?.typeId !== "minecraft:player") return;
    if (ev.itemStack?.typeId !== ITEM.x_gene) return;
    swallowing.delete(player.id);
    system.run(() => awaken(player));
  });
}

// itemCompleteUse が飛ばない環境向けの保険
system.runInterval(() => {
  if (!swallowing.size) return;
  for (const player of allPlayers()) {
    const started = swallowing.get(player.id);
    if (started === undefined) continue;
    if (system.currentTick - started < 40) continue;
    swallowing.delete(player.id);
    awaken(player);
  }
}, 10);

// --- 変身中の素手は磁力を帯びる -------------------------------------------
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (player?.typeId !== "minecraft:player") return;
  if (!isTransformed(player)) return;
  const target = ev.hitEntity;
  if (!target) return;
  spark(player.dimension, FX.mag_spark,
        { x: target.location.x, y: target.location.y + 1.0, z: target.location.z });
});

world.afterEvents.playerSpawn.subscribe((ev) => {
  const player = ev.player;
  system.run(() => {
    safe(() => restore(player));
    if (typeof safe(() => player.getDynamicProperty(PROP.mag)) !== "number") {
      setProp(player, PROP.mag, 100);
    }
    if (ev.initialSpawn) {
      tell(player, tr("msg.welcome"));
      tell(player, tr("msg.welcome_hint"));
      tell(player, tr("msg.welcome_tech"));
    }
  });
});

// ---------------------------------------------------------------- loops
// 速いループ: 手応えに直結するもの
system.runInterval(() => {
  try { tickProjectiles((p, target) => {
    const owner = [...allPlayers()].find((pl) => pl.id === p.ownerId);
    if (owner) hit(owner, target, p.damage);
    fx(target.dimension, FX.lance_impact, target.location);
  }); } catch (_) { }
  try { tickForm(); } catch (_) { }
}, 1);

system.runInterval(() => {
  try { tickMobility(); } catch (_) { }
}, 2);

// 一秒ループ: ゲージ・AI・HUD
let second = 0;
system.runInterval(() => {
  second++;
  try { tickTransform(); } catch (_) { }
  try { tickAI(); } catch (_) { }
  for (const player of allPlayers()) {
    if (isMutant(player)) {
      try { hud(player); } catch (_) { }
    }
  }
  if (second % 10 === 0) {
    try { sweepFormItems(); } catch (_) { }
  }
}, 20);

// ---------------------------------------------------------------- commands
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  const src = ev.sourceEntity;
  if (src?.typeId !== "minecraft:player") return;
  switch (ev.id) {
    case "marvel:awaken":
      setProp(src, PROP.mutant, true);
      setProp(src, PROP.mag, 100);
      tell(src, tr("msg.awakened"));
      break;
    case "marvel:transform":
      toggle(src);
      break;
    case "marvel:terminal":
      openTerminal(src);
      break;
    case "marvel:stage":
      setProp(src, PROP.stage, Math.max(1, Math.min(3, parseInt(ev.message, 10) || 1)));
      break;
    case "marvel:reset":
      setProp(src, PROP.mutant, false);
      setProp(src, PROP.form, false);
      setProp(src, PROP.stage, 1);
      setProp(src, PROP.mastery, 0);
      cooldowns.clear(src.id);
      tell(src, tr("msg.reset"));
      break;
    default:
      break;
  }
}, { namespaces: ["marvel"] });

world.afterEvents.worldLoad?.subscribe?.(() => {
  console.warn("[marvel] マーベル・ミュータント 起動 / Marvel Mutants loaded");
});
