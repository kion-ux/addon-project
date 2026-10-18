// ===========================================================================
//  アストロ・ナノギア / ASTRO NANOGEAR — Minecraft 統合版 変身アドオン
//
//  惑星ごとの「星核」に宿るナノマシンが全身装甲と専用ナノウェポンを組み上げ、
//  惑星の力で戦う（9 形態）。ここはイベントとループの配線と /scriptevent astro:* だけ。
// ===========================================================================
import { world, system, ItemStack } from "@minecraft/server";
import {
  COMMON, PLANETS, PLANET_KEYS, CORE_TO_PLANET, WEAPON_TO_PLANET, ADDON,
} from "./data.js";
import {
  S, PROP, forgetState, save, saveAll, settings, setEnergy, maxEnergy, setXp, isReady,
  setOverheat, FX_SCALE, clearCds, clearBusy,
} from "./state.js";
import { setFxScale, forgetFx, announce, sound } from "./fx.js";
import {
  flushBank, tickPops, showDamage, sweepTexts, isTarget, onKill, addNova, setNova, noteHurt, markProvoked,
} from "./combat.js";
import { tickShots } from "./projectiles.js";
import { tickZones } from "./zones.js";
import {
  tickMobility, cancelFall, tryJustDodge, onBarrierHit, forgetMobility, barrierActive, isDodging,
  cancelBoost,
} from "./mobility.js";
import { chooseKind, perform } from "./engine.js";
import {
  startTransform, revert, tickTransforms, tickOff, sweep, sweepDropped, fixDroppedItem, tickEnergy,
  onDeath, onSpawn, startupCleanup, forgetTransform, restoreOnJoin, tickCloak,
} from "./transform.js";
import { onMeleeHit, forgetCombo } from "./combo.js";
import { tickPassives, tickPassiveEffects, PASSIVE_EVERY } from "./passives.js";
import { tickHud } from "./hud.js";
import { openTerminal, forgetUi } from "./ui.js";
import * as EN from "./enemies.js";
import {
  allPlayers, valid, heldItem, selectedSlot, isPlayer, report, guard, heal, getProp, setProp, give,
  now, BUS,
} from "./util.js";
import "./planets/index.js";

const TERMINAL = "astro:terminal";
const VOID_SIGNAL = "astro:void_signal";

BUS.on("revert", (p, reason) => revert(p, reason));

// ---------------------------------------------------------------------------
//  入力（右クリック）
// ---------------------------------------------------------------------------
const lastUse = new Map();   // playerId -> tick（itemUse と itemUseOn の二重発火を防ぐ）

function onUse(p, item) {
  if (!isPlayer(p) || !item) return;
  const t = now();
  if ((lastUse.get(p.id) ?? -99) > t - 4) return;
  lastUse.set(p.id, t);
  const id = item.typeId;
  const st = S(p);
  if (id === TERMINAL) { openTerminal(p); return; }
  const core = CORE_TO_PLANET[id];
  if (core) {
    if (st.seq) return;
    if (st.form) { announce(p, "§7変身中は使えない（スニークしたまま 2 秒静止で解除）", 30); return; }
    startTransform(p, core, { slot: selectedSlot(p) });
    return;
  }
  const wk = WEAPON_TO_PLANET[id];
  if (wk) {
    if (!isReady(p) || st.form !== wk) return;
    cancelBoost(p);   // 空中でスニーク＋右クリック（バリア・必殺）はブースト・ダッシュにしない
    perform(p, chooseKind(p));
    return;
  }
  if (id === VOID_SIGNAL) EN.useVoidSignal(p);
}

world.afterEvents.itemUse.subscribe(guard("itemUse", (ev) => onUse(ev.source, ev.itemStack)));
world.afterEvents.itemUseOn?.subscribe(guard("itemUseOn", (ev) => onUse(ev.source, ev.itemStack)));

// ---------------------------------------------------------------------------
//  当たり
// ---------------------------------------------------------------------------
world.afterEvents.entityHitEntity.subscribe(guard("entityHitEntity", (ev) => {
  const victim = ev.hitEntity;
  const attacker = ev.damagingEntity;
  if (isPlayer(victim) && isReady(victim)) {
    if (barrierActive(victim)) onBarrierHit(victim, attacker);
    else if (isDodging(victim)) tryJustDodge(victim, attacker);
  }
  if (!isPlayer(attacker) || !isReady(attacker)) return;
  const wk = WEAPON_TO_PLANET[heldItem(attacker)?.typeId];
  if (wk !== S(attacker).form || !isTarget(attacker, victim)) return;
  onMeleeHit(attacker, victim);
}));

world.afterEvents.entityHurt.subscribe(guard("entityHurt", (ev) => {
  const e = ev.hurtEntity;
  const src = ev.damageSource;
  const attacker = src?.damagingEntity;
  if (!valid(e)) return;
  if (valid(attacker) && attacker.id !== e.id && ev.damage > 0) {
    // プレイヤーの攻撃が通った（被弾の無敵時間の始まり。バニラの通常攻撃も）/ 戦った mob を覚える
    if (isPlayer(attacker)) { noteHurt(e); markProvoked(e, attacker, false); }
    else if (isPlayer(e)) markProvoked(attacker, e, true);
  }
  const quiet = EN.onEntityHurt(e, ev.damage, src) === true;
  if (!quiet) {
    if (valid(attacker) && isPlayer(attacker) && S(attacker).form && attacker.id !== e.id) showDamage(e, ev.damage, attacker);
    else if (e.typeId === EN.TYPES.target) showDamage(e, ev.damage, isPlayer(attacker) ? attacker : undefined);
  }
  if (!isPlayer(e)) return;
  if (src?.cause === "fall" && cancelFall(e, ev.damage)) return;
  if (!isReady(e)) return;
  if (barrierActive(e)) {
    onBarrierHit(e, attacker);
    if (ev.damage > 0) heal(e, ev.damage);
    return;
  }
  if (isDodging(e) && tryJustDodge(e, attacker)) {
    if (ev.damage > 0) heal(e, ev.damage);
    return;
  }
  addNova(e, ev.damage * COMMON.nova_per_damage_taken);
  BUS.emit("hurt", e, attacker, ev.damage);
}));

// 飛び道具が当たった: バリア中なら弾いた演出、回避中ならジャスト回避
world.afterEvents.projectileHitEntity?.subscribe(guard("projectileHitEntity", (ev) => {
  let victim;
  try { victim = ev.getEntityHit?.()?.entity; } catch (_) { return; }
  if (!valid(victim) || !isPlayer(victim) || !isReady(victim)) return;
  const shooter = valid(ev.source) ? ev.source : undefined;
  if (barrierActive(victim)) onBarrierHit(victim, shooter);
  else if (isDodging(victim)) tryJustDodge(victim, shooter);
}));

world.afterEvents.entityDie.subscribe(guard("entityDie", (ev) => {
  const e = ev.deadEntity;
  const killer = ev.damageSource?.damagingEntity;
  if (isPlayer(e)) onDeath(e);
  if (isPlayer(killer) && valid(killer) && killer.id !== e?.id && S(killer).form) onKill(killer, e);
  EN.onEntityDie(e, ev.damageSource);
}));

world.afterEvents.entitySpawn?.subscribe(guard("entitySpawn", (ev) => {
  const e = ev.entity;
  let type;
  try { type = e.typeId; } catch (_) { return; }
  if (type === "minecraft:item") {
    // 中身が読めるのは次の tick から
    system.run(() => { try { fixDroppedItem(e); } catch (_) { } });
    return;
  }
  if (type?.startsWith("astro:")) EN.onEntitySpawn(e);
}));

// ---------------------------------------------------------------------------
//  入退出・リスポーン
// ---------------------------------------------------------------------------
const joined = new Set();   // このスクリプトの起動中に参加処理を済ませたプレイヤー

function welcome(p) {
  try {
    p.sendMessage(`§l§b◆ ${ADDON.ja} §r§7— 惑星の星核で全身装甲に変身して戦う`);
    p.sendMessage("§7惑星コアを持って右クリックで変身 / 攻撃=三段コンボ / 右クリック=惑星技");
    p.sendMessage("§7ダッシュ中=機動技 / 空中=空中技 / スニーク+右クリック=必殺技・ナノ・バリア");
    p.sendMessage("§7詳しくは §f星核ターミナル§7（初回に配布）を右クリック");
  } catch (_) { }
  if (getProp(p, PROP.gotTerminal, false) !== true) {
    setProp(p, PROP.gotTerminal, true);
    try { give(p, new ItemStack(TERMINAL, 1)); } catch (_) { }
  }
}

world.afterEvents.playerSpawn.subscribe(guard("playerSpawn", (ev) => {
  const p = ev.player;
  forgetMobility(p.id);
  forgetCombo(p.id);
  if (ev.initialSpawn) {
    if (!joined.has(p.id)) { joined.add(p.id); onSpawn(p, true); }
    else onSpawn(p, false);
    system.runTimeout(() => { if (valid(p)) welcome(p); }, 40);
    return;
  }
  onSpawn(p, false);
}));

world.beforeEvents?.playerLeave?.subscribe((ev) => {
  // 読み取り専用の場面なので、書けなければ数秒おきの保存に任せる
  try { save(ev.player); } catch (_) { }
});

world.afterEvents.playerLeave?.subscribe(guard("playerLeave", (ev) => {
  const id = ev.playerId;
  joined.delete(id);
  lastUse.delete(id);
  forgetMobility(id);
  forgetCombo(id);
  forgetFx(id);
  forgetTransform(id);
  forgetUi(id);
  forgetState(id);
}));

// ---------------------------------------------------------------------------
//  ループ
// ---------------------------------------------------------------------------
function step(name, fn) {
  try { fn(); } catch (e) { report(name, e); }
}

function perSecond() {
  let k = Infinity;
  for (const p of allPlayers()) {
    step("energy", () => tickEnergy(p));
    step("sweep", () => sweep(p));
    step("cloak", () => tickCloak(p));
    if (now() % 40 === 0) step("dropped", () => sweepDropped(p));
    k = Math.min(k, FX_SCALE[settings(p).fx] ?? 1);
  }
  setFxScale(Number.isFinite(k) ? k : 1);
  step("passiveEffects", tickPassiveEffects);
}

system.runInterval(() => {
  const t = system.currentTick;
  step("bank", flushBank);
  step("transform", tickTransforms);
  step("off", tickOff);
  step("mobility", tickMobility);
  step("shots", tickShots);
  step("zones", tickZones);
  step("pops", tickPops);
  step("enemies", () => EN.tickEnemies(t));
  if (t % 4 === 0) step("hud", tickHud);
  if (t % PASSIVE_EVERY === 0) step("passives", tickPassives);
  if (t % 20 === 0) perSecond();
  if (t % 100 === 0) step("save", saveAll);
}, 1);

// 起動直後（/reload を含む）: 残ったダメージ表示・カメラ・入力ロック・中断された変身を片付ける
system.run(() => {
  step("startup.texts", sweepTexts);
  for (const p of allPlayers()) {
    joined.add(p.id);
    step("startup.player", () => restoreOnJoin(p));
  }
  step("startup.enemies", EN.initEnemies);
});

// ---------------------------------------------------------------------------
//  コマンド: /scriptevent astro:<name> [引数]
// ---------------------------------------------------------------------------
function currentKey(p) {
  const st = S(p);
  return st.form ?? CORE_TO_PLANET[heldItem(p)?.typeId] ?? st.last ?? null;
}

export function command(p, id, message = "") {
  const name = id.split(":")[1] ?? "";
  switch (name) {
    case "kit": {
      for (const key of PLANET_KEYS) give(p, new ItemStack(PLANETS[key].core, 1));
      give(p, new ItemStack(TERMINAL, 1));
      give(p, new ItemStack("astro:nano_cell", 16));
      give(p, new ItemStack("astro:core_frame", 4));
      give(p, new ItemStack("astro:solar_fragment", 4));
      give(p, new ItemStack(VOID_SIGNAL, 2));
      p.sendMessage("§b全コアとターミナル・素材を支給した");
      return true;
    }
    case "energy":
      setOverheat(p, 0);
      setEnergy(p, maxEnergy(p));
      p.sendMessage("§e星力を満タンにした");
      return true;
    case "nova":
      setNova(p, COMMON.nova_max);
      p.sendMessage("§6超新星ゲージを満タンにした");
      return true;
    case "sync": {
      const key = currentKey(p);
      if (!key) { p.sendMessage("§c形態がわからない（変身するかコアを持つ）"); return false; }
      setXp(p, key, COMMON.sync_xp[COMMON.sync_xp.length - 1]);
      p.sendMessage(`${PLANETS[key].tc}${PLANETS[key].form_ja}§r の同調率を Lv5 にした`);
      return true;
    }
    case "cooldown":
      clearCds(p); clearBusy(p);
      p.sendMessage("§7再使用時間を戻した");
      return true;
    case "target": EN.summonTarget(p); return true;
    case "boss": EN.summonBoss(p); return true;
    case "revert":
      if (!revert(p, "manual")) p.sendMessage("§7変身していない");
      return true;
    case "transform": {
      const key = String(message ?? "").trim().toLowerCase() || currentKey(p);
      if (!PLANETS[key]) { p.sendMessage(`§c形態: ${PLANET_KEYS.join(" / ")}`); return false; }
      return startTransform(p, key, { coreless: true });
    }
    default:
      p.sendMessage("§7astro:kit / energy / nova / sync / cooldown / target / boss / revert / transform <形態>");
      return false;
  }
}

system.afterEvents.scriptEventReceive.subscribe(guard("scriptEvent", (ev) => {
  const p = ev.sourceEntity;
  if (!isPlayer(p)) return;
  command(p, ev.id, ev.message);
}), { namespaces: ["astro"] });

console.warn(`[astro] ${ADDON.ja} 起動 / ${ADDON.en} ${ADDON.version} loaded`);
