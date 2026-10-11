// ===========================================================================
//  進撃の巨人アドオン / Attack on Titan fan add-on for Minecraft Bedrock
//  立体機動装置・うなじを削ぐ戦い・無垢の巨人・調査兵団。
// ===========================================================================
import { ItemStack, system, world } from "@minecraft/server";
import { GAS_MAX, ITEM, PROP, TITAN_TYPES } from "./config.js";
import {
  fireAnchor, forget, holdsBlades, refill, releaseAnchor, shouldCancelFall, state as odmState,
  swingAt, tickODM,
} from "./odm.js";
import {
  forgetTitan, forgetVictim, isGrabbed, isTitan, kneel, onTitanDie, onTitanHurt, struggle,
  tickTitans, tickTitansFast, tryGrab, GRAB,
} from "./titans.js";
import { cycleFlare, fireFlare, fireSpear, tickSpears } from "./spear.js";
import { forgetSoldier, isSoldier, tickRally, tickSoldiers } from "./soldiers.js";
import { giveKit, hud, openJournal } from "./ui.js";
import {
  allPlayers, boolProp, consume, container, dist, health, isCreative, now, numProp, rt, selectedSlot,
  setProp, tell, valid,
} from "./util.js";
import { sound } from "./fx.js";

// ---------------------------------------------------------------------------
//  アイテムの使用（押した瞬間／離した瞬間）
// ---------------------------------------------------------------------------
function startUse(p, item) {
  if (!item) return;
  const s = odmState(p);
  if (s.lastUse === now()) return;          // itemUse と itemStartUse の二重発火
  s.lastUse = now();
  switch (item.typeId) {
    case ITEM.blades: fireAnchor(p); break;
    case ITEM.spear: fireSpear(p); break;
    case ITEM.journal: openJournal(p); break;
    case ITEM.flare:
      if (p.isSneaking) cycleFlare(p);
      else {
        fireFlare(p);
        wearItem(p, 1);
      }
      break;
    default:
  }
}

/** 手に持った道具の耐久を減らす（尽きたら消える）。 */
function wearItem(p, n) {
  if (isCreative(p)) return;
  const inv = container(p);
  const slot = selectedSlot(p);
  try {
    const it = inv.getItem(slot);
    const d = it?.getComponent("minecraft:durability");
    if (!d) return;
    if (d.damage + n >= d.maxDurability) inv.setItem(slot, undefined);
    else { d.damage += n; inv.setItem(slot, it); }
  } catch (_) { }
}

function stopUse(p, item) {
  if (item?.typeId === ITEM.blades || holdsBlades(p)) releaseAnchor(p);
}

const isPlayer = (e) => e?.typeId === "minecraft:player";

world.afterEvents.itemUse.subscribe((ev) => {
  if (isPlayer(ev.source)) startUse(ev.source, ev.itemStack);
});
// 近くのブロックに向けて押すと「ブロックに使う」扱いになることがあるので、それも開始とみなす
world.afterEvents.itemUseOn?.subscribe?.((ev) => {
  if (isPlayer(ev.source) && ev.itemStack?.typeId === ITEM.blades) startUse(ev.source, ev.itemStack);
});
world.afterEvents.itemStartUse?.subscribe?.((ev) => {
  if (isPlayer(ev.source)) startUse(ev.source, ev.itemStack);
});
world.afterEvents.itemStopUse?.subscribe?.((ev) => {
  if (isPlayer(ev.source)) stopUse(ev.source, ev.itemStack);
});
world.afterEvents.itemReleaseUse?.subscribe?.((ev) => {
  if (isPlayer(ev.source)) stopUse(ev.source, ev.itemStack);
});
world.afterEvents.itemCompleteUse?.subscribe?.((ev) => {
  const p = ev.source;
  if (!isPlayer(p)) return;
  if (ev.itemStack?.typeId === ITEM.gas) {
    if (refill(p) && !isCreative(p)) consume(p, ITEM.gas, 1);
  } else if (ev.itemStack?.typeId === ITEM.blades) {
    releaseAnchor(p);
  }
});

// ---------------------------------------------------------------------------
//  攻撃が当たった
// ---------------------------------------------------------------------------
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const a = ev.damagingEntity;
  const t = ev.hitEntity;
  if (!a || !t) return;
  if (isPlayer(a) && isTitan(t)) {
    if (isGrabbed(a)) { if (holdsBlades(a)) struggle(a, false); return; }
    if (holdsBlades(a)) swingAt(a, t, "hit");
    return;
  }
  if (isSoldier(a) && isTitan(t)) {
    // 兵士が地上で足首を斬る
    if (Math.random() < 0.12) kneel(t);
  }
});

world.afterEvents.entityHurt.subscribe((ev) => {
  const e = ev.hurtEntity;
  if (!e) return;
  const src = ev.damageSource ?? {};
  const cause = String(src.cause ?? "");
  const attacker = src.damagingEntity;
  if (isTitan(e)) {
    onTitanHurt(e, ev.damage, cause, attacker);
    return;
  }
  // 落下ダメージ: 立体機動の後ならガスで受け止めたことにする
  if (isPlayer(e) && cause === "fall" && shouldCancelFall(e)) {
    const h = health(e);
    try { if (h && h.currentValue > 0) h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + ev.damage)); }
    catch (_) { }
    return;
  }
  // 巨人の手が届いた: 掴まれることがある
  if (attacker && isTitan(attacker) && (cause === "entityAttack" || cause === "entity_attack")) {
    if (isPlayer(e) && isCreative(e)) return;
    tryGrab(attacker, e);
  }
});

world.afterEvents.entityDie.subscribe((ev) => {
  const e = ev.deadEntity;
  if (!e) return;
  if (isTitan(e)) { onTitanDie(e, ev.damageSource?.damagingEntity); return; }
  if (isPlayer(e)) {
    releaseAnchor(e, true);
    forgetVictim(e.id);
    return;
  }
  if (isSoldier(e)) { forgetVictim(e.id); forgetSoldier(e.id); }
});

world.afterEvents.playerLeave?.subscribe?.((ev) => {
  forget(ev.playerId);
  forgetVictim(ev.playerId);
});

// ---------------------------------------------------------------------------
//  初めて入った時: 手帳を配る
// ---------------------------------------------------------------------------
world.afterEvents.playerSpawn.subscribe((ev) => {
  const p = ev.player;
  forget(p.id);                        // 持ち姿勢を出し直す（リスポーンで消えるため）
  system.run(() => {
    if (!valid(p)) return;
    if (typeof p.getDynamicProperty(PROP.gas) !== "number") setProp(p, PROP.gas, GAS_MAX);
    if (!boolProp(p, PROP.welcomed, false)) {
      setProp(p, PROP.welcomed, true);
      try { container(p)?.addItem(new ItemStack(ITEM.journal, 1)); } catch (_) { }
      tell(p, rt("§2§l", { t: "aot.msg.welcome" }));
      tell(p, rt("§7", { t: "aot.msg.welcome_hint" }));
    }
  });
});

// ---------------------------------------------------------------------------
//  巨人の自然湧きを止める設定（スポーンエッグ・コマンドで出したものは残す）
// ---------------------------------------------------------------------------
world.afterEvents.entitySpawn.subscribe((ev) => {
  const e = ev.entity;
  if (!e || !TITAN_TYPES[e.typeId]) return;
  if (!boolProp(world, PROP.spawns, false)) return;
  if (String(ev.cause ?? "") !== "Spawned") return;
  system.run(() => {
    if (!valid(e)) return;
    let near = false;
    for (const p of allPlayers()) {
      if (p.dimension.id === e.dimension.id && dist(p.location, e.location) < 20) { near = true; break; }
    }
    if (!near) { try { e.remove(); } catch (_) { } }
  });
});

// ---------------------------------------------------------------------------
//  ループ
// ---------------------------------------------------------------------------
system.runInterval(() => {
  for (const p of allPlayers()) {
    try { tickODM(p); } catch (err) { report("odm", err); }
  }
  try { tickTitansFast(); } catch (err) { report("titans_fast", err); }
  try { tickSpears(); } catch (err) { report("spears", err); }
}, 1);

system.runInterval(() => {
  try { tickSoldiers(); } catch (err) { report("soldiers", err); }
}, 2);

system.runInterval(() => {
  for (const p of allPlayers()) {
    try { hud(p); } catch (err) { report("hud", err); }
  }
}, 5);

system.runInterval(() => {
  try { tickTitans(); } catch (err) { report("titans", err); }
}, 10);

system.runInterval(() => {
  try { tickRally(); } catch (err) { report("rally", err); }
}, 200);

const reported = new Set();
function report(where, err) {
  const key = `${where}:${err}`;
  if (reported.has(key)) return;
  reported.add(key);
  console.warn(`[aot] ${where}: ${err}${err?.stack ? `\n${err.stack}` : ""}`);
}

// ---------------------------------------------------------------------------
//  /scriptevent aot:kit | aot:gas | aot:journal | aot:reset
// ---------------------------------------------------------------------------
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  const p = ev.sourceEntity;
  if (!isPlayer(p)) return;
  switch (ev.id) {
    case "aot:kit": giveKit(p, true); break;
    case "aot:gas": setProp(p, PROP.gas, GAS_MAX); sound(p.dimension, "aot.gas", p.location); break;
    case "aot:journal": openJournal(p); break;
    case "aot:reset":
      setProp(p, PROP.kills, 0);
      setProp(p, PROP.kit, false);
      tell(p, rt("§7", { t: "aot.msg.reset" }));
      break;
    default:
  }
}, { namespaces: ["aot"] });

export { GRAB, numProp, forgetTitan };
