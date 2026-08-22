// ===========================================================================
//  怪獣8号 アドオン  /  Kaiju No.8 Add-on for Minecraft Bedrock
//  日本防衛隊の装備・解放戦力・怪獣災害・そして「怪獣8号」への変身。
// ===========================================================================
import { world, system } from "@minecraft/server";
import {
  PARASITE_ITEM, TRANSFORM_ITEM, DETECTOR_ITEM, FORM_ITEM, PROP, ENERGY_MAX,
} from "./config.js";
import { tr, tell, allPlayers } from "./util.js";
import {
  grantPower, toggle, restore, isTransformed, tickTransform, container,
} from "./transform.js";
import { useWeapon } from "./weapons.js";
import { tickKaiju } from "./kaiju.js";
import { tickAlerts } from "./alert.js";
import { openTerminal, quickScan } from "./ui.js";

const swallowing = new Map();  // playerId -> tick the swallow began

function handleUse(player, itemStack) {
  if (!player || !itemStack) return;
  const id = itemStack.typeId;

  if (id === TRANSFORM_ITEM) {
    toggle(player);
    return;
  }
  if (id === DETECTOR_ITEM) {
    if (player.isSneaking) openTerminal(player); else quickScan(player);
    return;
  }
  useWeapon(player, id);
}

world.afterEvents.itemUse.subscribe((ev) => {
  const player = ev.source;
  if (player?.typeId !== "minecraft:player") return;
  if (ev.itemStack?.typeId === PARASITE_ITEM) {
    // handled on completion so the drink animation plays out
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
      }
    } catch (_) { }
  });
});

// Stray 怪獣8号の体 items are meaningless outside a transformation — clean them up.
function sweepFormItems() {
  for (const player of allPlayers()) {
    if (isTransformed(player)) continue;
    const inv = container(player);
    if (!inv) continue;
    for (let i = 0; i < inv.size; i++) {
      const item = inv.getItem(i);
      if (item?.typeId === FORM_ITEM) inv.setItem(i, undefined);
    }
  }
}

let second = 0;
system.runInterval(() => {
  second++;
  try { tickTransform(); } catch (_) { }
  try { tickKaiju(); } catch (_) { }
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
