// ===========================================================================
//  マーベル・ミュータント / 磁界の帝王
//  Marvel Mutants — Master of Magnetism, for Minecraft Bedrock
//
//  マグニートーとブラザーフッド。地上のあらゆる金属を意のままに操り、
//  ミュータント狩りのセンチネルを鉄屑に変える。
// ===========================================================================
import { world, system } from "@minecraft/server";
import { ITEM, TECH_BY_ITEM, PROP, FX } from "./config.js";
import { allPlayers, safe, setProp, tell, tr } from "./util.js";
import { fx } from "./effects.js";
import {
  awaken, heroOf, hud, isMutant, isTransformed, restore, sweepFormItems,
  tickForm, tickTransform, toggle,
} from "./transform.js";
import {
  clearTechniqueState, cooldowns, tickTechniques, useTechnique,
} from "./techniques.js";
import { useAllyTechnique } from "./powers.js";
import { clearMobility, tickMobility } from "./mobility.js";
import { tickAI } from "./ai.js";
import {
  ALLY_SLOT_ITEMS, hudExtra, layoutHotbar, openTerminal, pickTechnique,
  scanMetal,
} from "./ui.js";
import { tickProjectiles } from "./magnetism.js";
import { hit } from "./effects.js";

const swallowing = new Map();

// ---------------------------------------------------------------- 入力
//  技アイテムは `itemStartUse`（使用開始）で発動させたい。
//  一人称の `fp.tech` コントローラは `query.is_using_item` で act へ遷移する
//  ので、`itemUse`（単発）だけだと 0.6 秒の手元アニメが実質再生されない。
//
//  ただし `itemStartUse` は **use_duration を持つアイテムでしか飛ばない**。
//  担当 10 が `use_modifiers {use_duration: 0.7}` を入れるまでは飛ばないので、
//  両方を購読して **8 tick の重複除け** で片方だけ通す。
//  こうしておけば、担当 10 の作業が入った瞬間に自動で良い側へ寄る。
const lastUse = new Map();

function debounced(player, id) {
  const key = `${player.id}/${id}`;
  const now = system.currentTick;
  if (now - (lastUse.get(key) ?? -99) < 8) return false;
  lastUse.set(key, now);
  return true;
}

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
  if (!techKey) return;
  if (sneaking) { pickTechnique(player); return; }

  if (heroOf(player) === "magneto") {
    useTechnique(player, techKey);
    return;
  }
  // ブラザーフッドは 3 種しか持たない。**どのアイテムが何番か** は
  // ui.ALLY_SLOT_ITEMS が正典で、ここはそれを引くだけ。
  // （以前は Object.keys(TECH_BY_ITEM).indexOf(id) で、
  //   技を増やすたびに割り当てが黙って入れ替わっていた。）
  const slot = ALLY_SLOT_ITEMS.indexOf(id);
  if (slot < 0) {
    tell(player, tr("msg.locked"));
    return;
  }
  useAllyTechnique(player, slot);
}

world.afterEvents.itemUse.subscribe((ev) => {
  const player = ev.source;
  if (player?.typeId !== "minecraft:player") return;
  const id = ev.itemStack?.typeId;
  if (id === ITEM.x_gene) {
    swallowing.set(player.id, system.currentTick);
    system.runTimeout(() => swallowing.delete(player.id), 120);
    return;
  }
  if (!debounced(player, id)) return;
  handleUse(player, ev.itemStack);
});

if (world.afterEvents.itemStartUse) {
  world.afterEvents.itemStartUse.subscribe((ev) => {
    const player = ev.source;
    if (player?.typeId !== "minecraft:player") return;
    const id = ev.itemStack?.typeId;
    if (id === ITEM.x_gene) return;
    if (!debounced(player, id)) return;
    handleUse(player, ev.itemStack);
  });
}

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
//  与ダメの倍率（コア露出・磁力視）は ai.js の entityHurt が一括で見る。
//  ここは火花だけ。二箇所でダメージを足すと必ず二重になる。
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (player?.typeId !== "minecraft:player") return;
  if (!isTransformed(player)) return;
  const target = ev.hitEntity;
  if (!target) return;
  fx(player.dimension, FX.mag_spark,
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

// --- 後始末 ---------------------------------------------------------------
//  死亡・退出で fog を押したまま、足場を置いたままにしない。
world.afterEvents.entityDie.subscribe((ev) => {
  const e = ev.deadEntity;
  if (e?.typeId !== "minecraft:player") return;
  system.run(() => {
    safe(() => clearTechniqueState(e));
    safe(() => clearMobility(e));
  });
});

world.beforeEvents.playerLeave?.subscribe?.((ev) => {
  const player = ev.player;
  safe(() => clearTechniqueState(player));
  safe(() => clearMobility(player));
  cooldowns.clear(player.id);
});

// ---------------------------------------------------------------- loops
// 速いループ: 手応えに直結するもの
system.runInterval(() => {
  try {
    tickProjectiles((p, target) => {
      const owner = allPlayers().find((pl) => pl.id === p.ownerId);
      if (owner) hit(owner, target, p.damage);
      fx(target.dimension, FX.lance_impact, target.location);
    });
  } catch (_) { }
  try { tickForm(); } catch (_) { }
  // 剥がしたブロックの戻しと、磁力ジップの牽引。
  try { tickTechniques(); } catch (_) { }
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
    if (!isMutant(player)) continue;
    try { hud(player, hudExtra(player)); } catch (_) { }
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
    case "marvel:kit":
      layoutHotbar(src);
      break;
    case "marvel:stage":
      setProp(src, PROP.stage, Math.max(1, Math.min(3, parseInt(ev.message, 10) || 1)));
      break;
    case "marvel:mastery":
      setProp(src, PROP.mastery, Math.max(0, parseInt(ev.message, 10) || 0));
      break;
    case "marvel:reset":
      setProp(src, PROP.mutant, false);
      setProp(src, PROP.form, false);
      setProp(src, PROP.stage, 1);
      setProp(src, PROP.mastery, 0);
      cooldowns.clear(src.id);
      safe(() => clearTechniqueState(src));
      safe(() => clearMobility(src));
      tell(src, tr("msg.reset"));
      break;
    default:
      break;
  }
}, { namespaces: ["marvel"] });

world.afterEvents.worldLoad?.subscribe?.(() => {
  console.warn("[marvel] マーベル・ミュータント 起動 / Marvel Mutants loaded");
});
