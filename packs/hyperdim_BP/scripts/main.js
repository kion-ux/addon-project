// ===========================================================================
//  超次元バトルアーツ / HYPER DIMENSION ARTS — Minecraft 統合版 PvP アドオン
//
//  8 種の超次元武器（大剣・双剣・両手斧・ダガー・弓・盾・鞭・両手かぎ爪）に、
//  三段コンボ・戦技・突進技・空中技・必殺技、そしてアクションゲームの機動を付ける。
// ===========================================================================
import { world, system, ItemStack } from "@minecraft/server";
import { WEAPONS, weaponOf, GAUGE_MAX } from "./config.js";
import {
  flushBank, tickPops, saveGauges, addGauge, setGauge, showDamage, isTarget,
} from "./combat.js";
import { onMeleeHit, forgetCombo } from "./combo.js";
import { chooseKind, perform } from "./engine.js";
import { body, bodyStop, setTickSource } from "./fx.js";
import { openGuide } from "./guide.js";
import { startUse, stopUse, tickHold, onGuardHurt, forgetHold } from "./hold.js";
import { showHud } from "./hud.js";
import { tickMobility, cancelFall, forget } from "./mobility.js";
import { tickShots } from "./projectiles.js";
import { allPlayers, heldItem, health, cmd, valid } from "./util.js";
import "./moves_sword.js";
import "./moves_heavy.js";
import "./moves_range.js";

setTickSource(() => system.currentTick);

const GUIDE = "hd:guide";
const DUMMY = "hd:training_dummy";

function heldWeapon(p) { return weaponOf(heldItem(p)); }

// ---------------------------------------------------------------------------
//  入力
// ---------------------------------------------------------------------------
world.afterEvents.itemUse.subscribe((ev) => {
  const p = ev.source;
  if (p?.typeId !== "minecraft:player") return;
  const id = ev.itemStack?.typeId;
  if (id === GUIDE) { openGuide(p); return; }
  const w = WEAPONS[id];
  if (!w) return;
  if (w.charge || w.guard) { startUse(p, w); return; }   // 開始イベントが無い版の保険
  perform(p, w, chooseKind(p));
});

world.afterEvents.itemStartUse?.subscribe((ev) => {
  const p = ev.source;
  const w = WEAPONS[ev.itemStack?.typeId];
  if (p?.typeId !== "minecraft:player" || !w || !(w.charge || w.guard)) return;
  startUse(p, w);
});

const onStop = (ev) => {
  const p = ev.source;
  if (p?.typeId !== "minecraft:player") return;
  stopUse(p);
};
world.afterEvents.itemStopUse?.subscribe(onStop);
world.afterEvents.itemReleaseUse?.subscribe(onStop);
world.afterEvents.itemCompleteUse?.subscribe(onStop);

// 通常攻撃が当たった
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const p = ev.damagingEntity;
  if (p?.typeId !== "minecraft:player") return;
  const w = heldWeapon(p);
  if (!w || !isTarget(p, ev.hitEntity)) return;
  onMeleeHit(p, ev.hitEntity, w);
});

// 被弾: ダメージ表示・ゲージ・ガード・落下無効・訓練用カカシ
world.afterEvents.entityHurt.subscribe((ev) => {
  const e = ev.hurtEntity;
  const src = ev.damageSource;
  const attacker = src?.damagingEntity;
  if (attacker?.typeId === "minecraft:player" && heldWeapon(attacker)) showDamage(e, ev.damage);
  else if (e?.typeId === DUMMY) showDamage(e, ev.damage);
  if (e?.typeId === DUMMY) { dummyHurt(e, ev.damage); return; }
  if (e?.typeId !== "minecraft:player") return;
  if (src?.cause === "fall" && cancelFall(e, ev.damage)) return;
  if (onGuardHurt(e, ev.damage, attacker)) return;
  if (heldWeapon(e)) addGauge(e, Math.min(6, 1 + ev.damage * 0.6));
});

// ---------------------------------------------------------------------------
//  訓練用カカシ: 倒れず、直近 5 秒の与ダメージと DPS を頭上に出す
// ---------------------------------------------------------------------------
const dummyLog = new Map();   // id -> [{t, d}]

function dummyHurt(e, dmg) {
  const t = system.currentTick;
  const log = (dummyLog.get(e.id) ?? []).filter((x) => t - x.t <= 100);
  log.push({ t, d: dmg });
  dummyLog.set(e.id, log);
  const h = health(e);
  try { if (h) h.setCurrentValue(h.effectiveMax); } catch (_) { }
  const sum = log.reduce((a, x) => a + x.d, 0);
  const span = Math.max(20, t - log[0].t) / 20;
  try { e.nameTag = `§e訓練用カカシ\n§f5秒合計 §c${sum.toFixed(1)} §7| §fDPS §6${(sum / span).toFixed(1)}`; } catch (_) { }
}

// ---------------------------------------------------------------------------
//  持ち替え: 両手持ちの構え・獣の構え
// ---------------------------------------------------------------------------
function onHoldChange(p, w) {
  if (w?.hold) body(p, w.hold, "hd.hold", 0.2);
  else bodyStop(p, "hd.hold");
}

// ---------------------------------------------------------------------------
//  ループ
// ---------------------------------------------------------------------------
system.runInterval(() => {
  try { flushBank(); } catch (e) { console.warn(`[hd] bank: ${e}`); }
  try { tickShots(); } catch (e) { console.warn(`[hd] shots: ${e}`); }
  try { tickPops(); } catch (_) { }
  try { tickHold(heldWeapon); } catch (e) { console.warn(`[hd] hold: ${e}`); }
}, 1);

system.runInterval(() => {
  try { tickMobility(onHoldChange); } catch (e) { console.warn(`[hd] mobility: ${e}`); }
}, 2);

system.runInterval(() => {
  for (const p of allPlayers()) {
    const w = heldWeapon(p);
    if (w) showHud(p, w);
  }
}, 4);

system.runInterval(() => { try { saveGauges(); } catch (_) { } }, 100);

// ---------------------------------------------------------------------------
//  入退出
// ---------------------------------------------------------------------------
world.afterEvents.playerSpawn.subscribe((ev) => {
  const p = ev.player;
  // リスポーン後は持ち姿勢を掛け直す
  forget(p.id);
  forgetHold(p.id);
  if (!ev.initialSpawn) return;
  system.runTimeout(() => {
    if (!valid(p)) return;
    try {
      p.sendMessage("§l§b◆ 超次元バトルアーツ §r§7— 超次元武器でアクションバトル！");
      p.sendMessage("§7右クリック=戦技 / ダッシュ中=突進技 / 空中=空中技 / スニーク+右クリック=必殺技");
      p.sendMessage("§7詳しくは §f超次元指南書§7（初回に配布）を右クリック");
      if (!p.getDynamicProperty("hd:got_guide")) {
        p.setDynamicProperty("hd:got_guide", true);
        p.getComponent("minecraft:inventory")?.container?.addItem(new ItemStack(GUIDE, 1));
      }
    } catch (_) { }
  }, 40);
});

world.afterEvents.playerLeave?.subscribe((ev) => {
  forget(ev.playerId);
  forgetCombo(ev.playerId);
  forgetHold(ev.playerId);
});

// 前回の残りのダメージ表示を掃除
function sweepTexts() {
  for (const id of ["overworld", "nether", "the_end"]) {
    try {
      for (const e of world.getDimension(id).getEntities({ type: "hd:dmg_text" })) e.remove();
    } catch (_) { }
  }
}
system.runTimeout(sweepTexts, 20);

// ---------------------------------------------------------------------------
//  コマンド: /scriptevent hd:<name>
// ---------------------------------------------------------------------------
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  const p = ev.sourceEntity;
  if (p?.typeId !== "minecraft:player") return;
  const inv = p.getComponent("minecraft:inventory")?.container;
  switch (ev.id) {
    case "hd:gauge":
      setGauge(p, GAUGE_MAX);
      p.sendMessage("§6超次元ゲージを満タンにしました");
      break;
    case "hd:kit":
      for (const id of Object.keys(WEAPONS)) inv?.addItem(new ItemStack(id, 1));
      inv?.addItem(new ItemStack(GUIDE, 1));
      p.sendMessage("§b超次元武器を一式支給しました");
      break;
    case "hd:dummy":
      try { p.dimension.spawnEntity(DUMMY, { x: p.location.x + p.getViewDirection().x * 3, y: p.location.y, z: p.location.z + p.getViewDirection().z * 3 }); }
      catch (_) { cmd(p, `summon ${DUMMY} ^ ^ ^3`); }
      break;
    case "hd:guide":
      openGuide(p);
      break;
    default:
      break;
  }
}, { namespaces: ["hd"] });

console.warn("[hd] 超次元バトルアーツ 起動 / Hyper Dimension Arts loaded");
