// ===========================================================================
//  怪獣8号 アドオン  /  Kaiju No.8 Add-on for Minecraft Bedrock
//  日本防衛隊の装備・解放戦力・技・怪獣災害・そして「怪獣8号」への変身。
// ===========================================================================
import { world, system } from "@minecraft/server";
import {
  PARASITE_ITEM, TRANSFORM_ITEM, DETECTOR_ITEM, FORM_ITEM, PROP, ENERGY_MAX,
} from "./config.js";
import { tr, tell, allPlayers } from "./util.js";
import {
  grantPower, toggle, restore, isTransformed, tickTransform, container,
} from "./transform.js";
import { useTechnique } from "./weapons.js";
import { TECH, tickSlams } from "./techniques.js";
import { tickMobility, tickSuitBuffs } from "./mobility.js";
import { tickKaiju, tickAllies } from "./kaiju.js";
import { tickNumbers } from "./numbers.js";
import { tickAlerts } from "./alert.js";
import { openTerminal, quickScan } from "./ui.js";

const swallowing = new Map();  // playerId -> tick the swallow began

function handleUse(player, itemStack) {
  if (!player || !itemStack) return;
  const id = itemStack.typeId;

  if (id === DETECTOR_ITEM) {
    if (player.isSneaking) openTerminal(player); else quickScan(player);
    return;
  }
  if (id === TRANSFORM_ITEM) {
    // 未変身なら変身、変身中はスニーク＋使用で解除、通常使用は技
    if (!isTransformed(player) || player.isSneaking) {
      toggle(player);
      return;
    }
  }
  if (TECH[id]) {
    useTechnique(player, id);
  }
}

world.afterEvents.itemUse.subscribe((ev) => {
  const player = ev.source;
  if (player?.typeId !== "minecraft:player") return;
  if (ev.itemStack?.typeId === PARASITE_ITEM) {
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
    if (ev.itemStack?.typeId !== PARASITE_ITEM) return;
    swallowing.delete(player.id);
    system.run(() => grantPower(player));
  });
}

// Fallback: on builds where itemCompleteUse never fires, finish the swallow
// ourselves once the drink animation has had time to play out.
system.runInterval(() => {
  if (!swallowing.size) return;
  for (const player of allPlayers()) {
    const started = swallowing.get(player.id);
    if (started === undefined) continue;
    if (system.currentTick - started < 40) continue;
    swallowing.delete(player.id);
    const held = container(player)?.getItem(
      typeof player.selectedSlotIndex === "number" ? player.selectedSlotIndex : 0
    );
    if (held?.typeId === PARASITE_ITEM) grantPower(player);
  }
}, 10);

world.afterEvents.playerSpawn.subscribe((ev) => {
  const player = ev.player;
  system.run(() => {
    try {
      restore(player);
      if (typeof player.getDynamicProperty(PROP.energy) !== "number") {
        player.setDynamicProperty(PROP.energy, ENERGY_MAX);
      }
      if (typeof player.getDynamicProperty(PROP.release) !== "number") {
        player.setDynamicProperty(PROP.release, 10);
      }
      if (ev.initialSpawn) {
        tell(player, tr("kaiju8.msg.welcome"));
        tell(player, tr("kaiju8.msg.welcome_hint"));
        tell(player, tr("kaiju8.msg.welcome_tech"));
      }
    } catch (_) { }
  });
});

// Stray 怪獣8号の体 items are meaningless outside a transformation.
function sweepFormItems() {
  for (const player of allPlayers()) {
    if (isTransformed(player)) continue;
    const inv = container(player);
    if (!inv) continue;
    for (let i = 0; i < inv.size; i++) {
      if (inv.getItem(i)?.typeId === FORM_ITEM) inv.setItem(i, undefined);
    }
  }
}

// fast loop: everything that has to feel responsive
system.runInterval(() => {
  try { tickMobility(); } catch (_) { }
  try { tickSlams(); } catch (_) { }
}, 2);

// one-second loop: gauges, AI flavour, world events
let second = 0;
system.runInterval(() => {
  second++;
  try { tickTransform(); } catch (_) { }
  try { tickSuitBuffs(); } catch (_) { }
  try { tickNumbers(); } catch (_) { }
  try { tickKaiju(); } catch (_) { }
  try { tickAllies(); } catch (_) { }
  try { tickAlerts(); } catch (_) { }
  if (second % 10 === 0) {
    try { sweepFormItems(); } catch (_) { }
  }
}, 20);

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  const src = ev.sourceEntity;
  if (src?.typeId !== "minecraft:player") return;
  if (ev.id === "kaiju8:power") {
    src.setDynamicProperty(PROP.power, true);
    src.setDynamicProperty(PROP.energy, ENERGY_MAX);
    tell(src, tr("kaiju8.msg.power_gained"));
  } else if (ev.id === "kaiju8:transform") {
    toggle(src);
  } else if (ev.id === "kaiju8:terminal") {
    openTerminal(src);
  } else if (ev.id === "kaiju8:reset") {
    src.setDynamicProperty(PROP.power, false);
    src.setDynamicProperty(PROP.form, false);
    src.setDynamicProperty(PROP.kills, 0);
    tell(src, tr("kaiju8.msg.reset"));
  }
}, { namespaces: ["kaiju8"] });

world.afterEvents.worldLoad?.subscribe?.(() => {
  console.warn("[kaiju8] 怪獣8号アドオン 起動 / Kaiju No.8 add-on loaded");
});
