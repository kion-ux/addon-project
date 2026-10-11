// 変身 / becoming the mutant
//
// 三人称でキャラクターに見えている正体は、頭スロットに装備した
// 「体アイテム」のアタッチャブル。プレイヤー本体は透明化して隠す。
//
// 技を撃つ瞬間だけ、体アイテムを *その技専用のもの* に差し替える。
// これがスクリプトから三人称アニメーションを切り替える唯一の確実な方法で、
// 技ごとに違う構えが出るのはこの仕組みのおかげ。
import { world, system, ItemStack, EquipmentSlot } from "@minecraft/server";
import {
  PROP, TAG, ITEM, HERO, TECH, MAG_MAX, MAG_REGEN, MAG_REGEN_STAGE3,
  MAG_DRAIN, STAGE_THRESHOLDS, FORM_ITEMS, FX, SOUND, ENTITY,
} from "./config.js";
import {
  actionbar, allPlayers, bar, bool, num, readJson, roman, safe, setProp, str,
  tell, title, tr, writeJson,
} from "./util.js";
import {
  chord, fade, fogPopAll, forgetFog, fx, fxRing, fxScatter, shake, shakeNearby,
  sound,
} from "./effects.js";
import { scanMetal } from "./magnetism.js";

const ARMOR_SLOTS = ["Head", "Chest", "Legs", "Feet"];

//: いま技の姿勢を保持しているプレイヤー -> 解除予定 tick
const posing = new Map();

//: 段階 3 の周回する鉄片。プレイヤー -> { shards, born }
const orbits = new Map();
const ORBIT_COUNT = 3;
// 実体側 (orbit_shard.entity.json) が 14 秒で自滅するので、その手前で張り直す。
// 万一スクリプトが止まっても鉄片が世界に残らない、という保険でもある。
const ORBIT_REFRESH = 200;

export function container(player) {
  return safe(() => player.getComponent("minecraft:inventory")?.container);
}

export function selectedSlot(player) {
  const v = player.selectedSlotIndex;
  return typeof v === "number" ? v : (player.selectedSlot ?? 0);
}

export function give(player, typeId, amount = 1) {
  const inv = container(player);
  if (!inv) return;
  const left = safe(() => inv.addItem(new ItemStack(typeId, amount)));
  if (left) safe(() => player.dimension.spawnItem(left, player.location));
}

export function consumeSelected(player, amount = 1) {
  const inv = container(player);
  if (!inv) return;
  const slot = selectedSlot(player);
  const item = safe(() => inv.getItem(slot));
  if (!item) return;
  if (item.amount > amount) {
    item.amount -= amount;
    safe(() => inv.setItem(slot, item));
  } else {
    safe(() => inv.setItem(slot, undefined));
  }
}

// ---------------------------------------------------------------- state
export function isMutant(player) { return bool(player, PROP.mutant, false); }
export function isTransformed(player) { return bool(player, PROP.form, false); }
export function heroOf(player) { return str(player, PROP.hero, "magneto"); }
export function stageOf(player) { return Math.max(1, num(player, PROP.stage, 1)); }
export function magOf(player) { return num(player, PROP.mag, MAG_MAX); }

export function spendMag(player, amount) {
  const left = Math.max(0, magOf(player) - amount);
  setProp(player, PROP.mag, left);
  if (left <= 0 && isTransformed(player)) revert(player, true);
  return left;
}

export function stageFor(kills) {
  let stage = 1;
  for (const [threshold, value] of STAGE_THRESHOLDS) {
    if (kills >= threshold) stage = value;
  }
  return stage;
}

/**
 * 段階ごとの磁力回復量。
 * 1 と 3 は contract の値をそのまま使い、2 はその中点（= 4.5）を採る。
 * 中点なら contract 側が数値を動かしても段階 2 だけ取り残されない。
 */
export function regenFor(stage) {
  if (stage >= 3) return MAG_REGEN_STAGE3;
  if (stage >= 2) return (MAG_REGEN + MAG_REGEN_STAGE3) / 2;
  return MAG_REGEN;
}

/** 段階 3 は同じ角度でも速く見せる（構えの保持を短くする）。 */
export function poseHoldScale(player) {
  return stageOf(player) >= 3 ? 0.85 : 1.0;
}

/**
 * 昇格の 3 秒（DIRECTION §7-4）。
 * 白の暗転 → 揺れ → 見出し → 周囲 20 ブロックの金属が一斉に光る。
 * 最後の「世界の金属が反応する」が、段階が上がった実感そのものになる。
 */
function stageCeremony(player, stage) {
  fade(player, { red: 1.0, green: 0.98, blue: 1.0 }, 0.06, 0.05, 0.70);
  shake(player, 0.5, 1.0, "rotational");
  chord(player.dimension, player.location, [
    [SOUND.transform_2, 0, { volume: 1.4, pitch: 0.9 }],
    [SOUND.mag_charge, 8, { volume: 1.0, pitch: 1.5 }],
    [SOUND.mag_release, 18, { volume: 0.8, pitch: 0.8 }],
  ]);
  fxRing(player.dimension, FX.transform_ring, player.location, 2.0, 14, 0.3);
  // 見出しは段階の数字だけにしてある。翻訳の有無に関係なく必ず読める。
  title(player, { rawtext: [{ text: `§6${roman(stage)}` }] }, tr("msg.stage_up"), 6, 40, 18);

  const metal = scanMetal(player.dimension, player.location, 20, 40);
  for (let t = 0; t <= 20; t += 5) {
    safe(() => system.runTimeout(() => {
      for (const m of metal) {
        fx(player.dimension, FX.metal_glint, { x: m.x + 0.5, y: m.y + 0.5, z: m.z + 0.5 });
      }
    }, t));
  }
}

export function refreshStage(player) {
  const before = stageOf(player);
  const after = stageFor(num(player, PROP.mastery, 0));
  if (after > before) {
    setProp(player, PROP.stage, after);
    tell(player, tr("msg.stage_up"));
    stageCeremony(player, after);
  }
  return after;
}

// ---------------------------------------------------------------- awaken
export function awaken(player) {
  if (isMutant(player)) {
    tell(player, tr("msg.already_mutant"));
    return;
  }
  setProp(player, PROP.mutant, true);
  setProp(player, PROP.mag, MAG_MAX);
  setProp(player, PROP.stage, 1);
  setProp(player, PROP.hero, "magneto");
  setProp(player, PROP.tech, "repulse");
  give(player, ITEM.magneto_helmet);
  give(player, TECH.repulse.item);
  give(player, TECH.attract.item);
  give(player, TECH.flight.item);

  chord(player.dimension, player.location, [
    [SOUND.transform, 0, { volume: 1.4, pitch: 0.7 }],
    ["random.levelup", 6, { pitch: 0.6 }],
    [SOUND.mag_charge, 12, { volume: 1.0, pitch: 1.4 }],
  ]);
  fxScatter(player.dimension, FX.transform_burst, player.location, 8, 1.0);
  fx(player.dimension, FX.transform_ring, player.location);
  shake(player, 0.45, 0.9, "rotational");
  fade(player, { red: 0.55, green: 0.30, blue: 0.95 }, 0.10, 0.08, 0.5);
  title(player, tr("title.awaken"), tr("title.awaken_sub"), 8, 50, 20);
  tell(player, tr("msg.awakened"));
}

// ---------------------------------------------------------------- armour
function stashArmor(player) {
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  const inv = container(player);
  if (!eq || !inv) return;
  const stashed = [];
  for (const slot of ARMOR_SLOTS) {
    const worn = safe(() => eq.getEquipment(slot));
    if (!worn) { stashed.push(null); continue; }
    const left = safe(() => inv.addItem(worn));
    if (left) { stashed.push(null); continue; }
    safe(() => eq.setEquipment(slot, undefined));
    stashed.push(worn.typeId);
  }
  setProp(player, PROP.stored, stashed.some(Boolean) ? JSON.stringify(stashed) : "");
}

function restoreArmor(player) {
  const rawValue = str(player, PROP.stored, "");
  if (!rawValue) return;
  setProp(player, PROP.stored, "");
  let ids;
  try { ids = JSON.parse(rawValue); } catch (_) { return; }
  if (!Array.isArray(ids)) return;
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  const inv = container(player);
  if (!eq || !inv) return;
  for (let i = 0; i < ARMOR_SLOTS.length; i++) {
    const id = ids[i];
    if (!id) continue;
    if (safe(() => eq.getEquipment(ARMOR_SLOTS[i]))) continue;
    for (let slot = 0; slot < inv.size; slot++) {
      const item = safe(() => inv.getItem(slot));
      if (item?.typeId !== id) continue;
      safe(() => eq.setEquipment(ARMOR_SLOTS[i], item));
      safe(() => inv.setItem(slot, undefined));
      break;
    }
  }
}

// ---------------------------------------------------------------- form item
function wearForm(player, typeId) {
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  if (!eq) return;
  safe(() => eq.setEquipment(EquipmentSlot.Head, new ItemStack(typeId, 1)));
}

function clearForm(player) {
  const eq = safe(() => player.getComponent("minecraft:equippable"));
  if (!eq) return;
  const head = safe(() => eq.getEquipment(EquipmentSlot.Head));
  if (head && FORM_ITEMS.includes(head.typeId)) {
    safe(() => eq.setEquipment(EquipmentSlot.Head, undefined));
  }
}

/** その人の「素の体」。英雄名が壊れていてもマグニートーに落として必ず戻す。 */
function baseForm(player) {
  return (HERO[heroOf(player)] ?? HERO.magneto).form;
}

/**
 * 技の姿勢に切り替える。`hold` tick 後に通常の体へ戻す。
 * これがそのまま三人称のアニメーション再生になる。
 *
 * 連打しても取りこぼさないよう、**期限は必ず上書き**する。
 * 短い技を撃った直後に長い技を撃つと、先に来た短い方の期限で
 * 素の体へ戻ってしまい、構えが一瞬で消える。
 */
export function pose(player, formItemId, hold) {
  if (!isTransformed(player)) return;
  if (!hold || hold <= 0) return;
  wearForm(player, formItemId);
  setProp(player, PROP.casting, formItemId);
  const now = system.currentTick;
  const until = posing.get(player.id) ?? 0;
  posing.set(player.id, Math.max(until, now + hold));
}

/** 姿勢を今すぐ解いて素の体へ戻す。変身解除・死亡から必ず通る道。 */
function endPose(player) {
  posing.delete(player.id);
  setProp(player, PROP.casting, "");
}

function tickPoses(player, now) {
  const until = posing.get(player.id);
  if (until === undefined || now < until) return;
  posing.delete(player.id);
  setProp(player, PROP.casting, "");
  // 変身が解けていれば素の体も着せない。ここで着せると
  // 「変身していないのに体アイテムだけ被っている」状態が生まれる。
  if (isTransformed(player)) wearForm(player, baseForm(player));
}

// ---------------------------------------------------------------- 段階3の周回
function dropOrbit(playerId) {
  const state = orbits.get(playerId);
  orbits.delete(playerId);
  if (!state) return;
  for (const shard of state.shards) safe(() => shard.remove());
}

function spawnOrbit(player) {
  dropOrbit(player.id);
  const shards = [];
  for (let i = 0; i < ORBIT_COUNT; i++) {
    const shard = safe(() => player.dimension.spawnEntity(ENTITY.orbit_shard, {
      x: player.location.x, y: player.location.y + 1.2, z: player.location.z,
    }));
    if (shard) shards.push(shard);
  }
  if (shards.length) orbits.set(player.id, { shards, born: system.currentTick });
}

/** 段階 3 だけ、鉄片が三つ周りを回る。遠目にも「帝王」だと分かる印。 */
function tickOrbit(player, now) {
  const want = isTransformed(player) && stageOf(player) >= 3;
  const state = orbits.get(player.id);
  if (!want) { if (state) dropOrbit(player.id); return; }
  if (!state || now - state.born > ORBIT_REFRESH) { spawnOrbit(player); return; }
  if (now % 2) return;                       // 2 tick に一度動かせば充分に滑らか
  const a0 = now * 0.075;
  let lost = false;
  for (let i = 0; i < state.shards.length; i++) {
    const shard = state.shards[i];
    // 消えた／ネザーへ渡ったなどで付いて来られなくなったら作り直す。
    if (!safe(() => shard.isValid?.() !== false)
        || safe(() => shard.dimension.id) !== player.dimension.id) { lost = true; continue; }
    const a = a0 + (i / state.shards.length) * Math.PI * 2;
    const ok = safe(() => {
      shard.teleport({
        x: player.location.x + Math.cos(a) * 1.45,
        y: player.location.y + 1.15 + Math.sin(a * 2) * 0.18,
        z: player.location.z + Math.sin(a) * 1.45,
      }, { facingLocation: { x: player.location.x, y: player.location.y + 1.2, z: player.location.z } });
      return true;
    });
    if (!ok) lost = true;
  }
  // 作り直しは 1 秒に一度まで。失敗が続く場所で毎 tick 湧かせない。
  if (lost && now - state.born > 20) spawnOrbit(player);
  if (now % 8 === 0) {
    fx(player.dimension, FX.levitate_dust,
       { x: player.location.x, y: player.location.y + 0.1, z: player.location.z });
  }
}

// ---------------------------------------------------------------- buffs
// 変身中に配るバフの一覧。解除のときに **これだけ** を消すために、
// 名前を一箇所に集めておく。
const OUR_EFFECTS = ["strength", "resistance", "speed", "jump_boost", "haste",
                     "regeneration", "fire_resistance", "night_vision",
                     "slow_falling", "slowness", "invisibility"];

// 変身前に本人が持っていた効果の控え。contract に無い名前なので
// ここで持つ（担当 10 が PROP に足したら、そちらへ移すこと）。
const PROP_EFFECTS = "marvel:stored_effects";

/**
 * 変身前の効果を控える。
 * `clearBuffs` はバフ名で一括削除するので、控えておかないと
 * **プレイヤーが自分で飲んだ暗視や耐性まで変身解除で消える**。
 */
function stashEffects(player) {
  const rows = [];
  for (const e of safe(() => player.getEffects()) ?? []) {
    const id = (safe(() => e.typeId) ?? "").replace("minecraft:", "");
    if (!id) continue;
    rows.push([id, safe(() => e.duration) ?? 0, safe(() => e.amplifier) ?? 0]);
  }
  writeJson(player, PROP_EFFECTS, { t: system.currentTick, e: rows });
}

/** 控えた効果を、経過した分だけ短くして戻す。 */
function restoreEffects(player) {
  const saved = readJson(player, PROP_EFFECTS, undefined);
  setProp(player, PROP_EFFECTS, "");
  if (!Array.isArray(saved?.e)) return;
  // ワールドを開き直すと currentTick は 0 に戻る。負の経過は 0 と見なす。
  const elapsed = Math.max(0, system.currentTick - (saved.t ?? 0));
  for (const row of saved.e) {
    if (!Array.isArray(row)) continue;
    const [id, duration, amp] = row;
    const left = (duration ?? 0) - elapsed;
    if (!Number.isFinite(left) || left < 20) continue;   // 残り 1 秒未満は戻さない
    safe(() => player.addEffect(id, Math.min(left, 20000000), { amplifier: amp ?? 0 }));
  }
}

/**
 * 段階でバフの強さを変える。
 * 段階 1 は「目覚めたばかりのエリック」なので敢えて素に近く、
 * 3 で一気に硬く強くなる。ここに差が無いと昇格が数字だけの話になる。
 */
function buffsFor(hero, stage) {
  const list = [
    ["resistance", stage >= 3 ? 2 : stage >= 2 ? 1 : 0],
    ["fire_resistance", 0],
    ["night_vision", 0],
  ];
  if (hero === "magneto") {
    list.push(["strength", stage >= 3 ? 2 : stage >= 2 ? 1 : 0]);
    list.push(["slow_falling", 0]);
    if (stage >= 3) list.push(["speed", 1]);
  } else if (hero === "quicksilver") {
    list.push(["speed", 4]);
    list.push(["jump_boost", 2]);
    list.push(["haste", 2]);
  } else if (hero === "sabretooth") {
    list.push(["strength", 2]);
    list.push(["regeneration", 1]);
    list.push(["speed", 1]);
  } else if (hero === "juggernaut" || hero === "blob") {
    list.push(["strength", 3]);
    list.push(["resistance", 3]);
    list.push(["slowness", 0]);
  } else if (hero === "toad") {
    list.push(["jump_boost", 4]);
    list.push(["speed", 1]);
  } else if (hero === "mystique") {
    list.push(["speed", 2]);
    list.push(["jump_boost", 1]);
  } else {
    list.push(["strength", 1]);
    list.push(["speed", 1]);
  }
  return list;
}

function applyBuffs(player) {
  const hero = heroOf(player);
  const stage = stageOf(player);
  for (const [id, amp] of buffsFor(hero, stage)) {
    safe(() => player.addEffect(id, 140, { amplifier: amp, showParticles: false }));
  }
  // プレイヤー自身のスキンを隠す。体アイテムのアタッチャブルだけが残る。
  safe(() => player.addEffect("invisibility", 140, { amplifier: 0, showParticles: false }));
}

function clearBuffs(player) {
  for (const id of OUR_EFFECTS) safe(() => player.removeEffect(id));
}

// ---------------------------------------------------------------- transform
export function transform(player) {
  if (isTransformed(player)) return;
  if (magOf(player) < 10) {
    tell(player, tr("msg.too_tired"));
    return;
  }
  const hero = HERO[heroOf(player)] ?? HERO.magneto;
  stashArmor(player);
  stashEffects(player);
  wearForm(player, hero.form);
  setProp(player, PROP.form, true);
  player.addTag(TAG.form);
  applyBuffs(player);

  const at = { x: player.location.x, y: player.location.y + 1.0, z: player.location.z };
  fx(player.dimension, FX.transform_burst, at);
  fx(player.dimension, FX.transform_ring, player.location);
  fxRing(player.dimension, FX.mag_aura, player.location, 1.6, 12, 0.4);
  fxScatter(player.dimension, FX.mag_spark, player.location, 10, 1.2);
  chord(player.dimension, player.location, [
    [SOUND.transform, 0, { volume: 1.6, pitch: 0.75 }],
    [SOUND.transform_2, 5, { volume: 1.0, pitch: 1.1 }],
    [SOUND.mag_release, 9, { volume: 0.7, pitch: 1.6 }],
  ]);
  shake(player, 0.5, 0.7);
  shakeNearby(player.dimension, player.location, 14, 0.3, 0.5);
  fade(player, { red: 0.42, green: 0.18, blue: 0.72 }, 0.08, 0.06, 0.42);
  title(player, tr("title.transform"), tr("title.transform_sub"), 4, 30, 14);
}

export function revert(player, exhausted = false) {
  if (!isTransformed(player)) return;
  clearForm(player);
  endPose(player);
  dropOrbit(player.id);
  setProp(player, PROP.form, false);
  setProp(player, PROP.flying, false);
  setProp(player, PROP.sight, 0);
  player.removeTag(TAG.form);
  restoreArmor(player);
  clearBuffs(player);
  restoreEffects(player);
  // 霧を押したまま変身を解くと、そのまま視界が濁り続ける。必ず剥がす。
  fogPopAll(player);
  fxScatter(player.dimension, FX.revert_smoke, player.location, 12, 1.2);
  sound(player.dimension, SOUND.revert, player.location, { pitch: 0.8 });
  shake(player, 0.2, 0.4);
  if (exhausted) {
    safe(() => player.addEffect("weakness", 260, { amplifier: 1 }));
    safe(() => player.addEffect("slowness", 180, { amplifier: 0, showParticles: false }));
    tell(player, tr("msg.exhausted"));
  } else {
    tell(player, tr("msg.revert"));
  }
}

export function toggle(player) {
  if (!isMutant(player)) {
    tell(player, tr("msg.no_power"));
    return;
  }
  if (isTransformed(player)) revert(player); else transform(player);
}

// ---------------------------------------------------------------- tick
/** 毎秒: ゲージ・バフ・HUD。 */
export function tickTransform() {
  for (const player of allPlayers()) {
    if (!isMutant(player)) continue;
    const transformed = isTransformed(player);
    // 撃破数が伸びても誰も段階を上げ直さないと、永久に段階1のままになり
    // 必殺技（段階3）に一生届かない。毎秒ここで見直す。
    const stage = refreshStage(player);
    let mag = magOf(player);

    if (transformed) {
      applyBuffs(player);
      mag -= MAG_DRAIN;
      if (mag <= 0) { setProp(player, PROP.mag, 0); revert(player, true); continue; }
    } else {
      mag = Math.min(MAG_MAX, mag + regenFor(stage));
    }
    setProp(player, PROP.mag, mag);
  }
}

/** 毎 tick: 姿勢の戻しと、段階 3 の周回鉄片。 */
export function tickForm() {
  const now = system.currentTick;
  for (const player of allPlayers()) {
    tickPoses(player, now);
    tickOrbit(player, now);
  }
  // 退出・死亡で置き去りになった記録を捨てる。放っておくと Map が太り続ける。
  if (now % 200 === 0 && (posing.size || orbits.size)) {
    const live = new Set(allPlayers().map((p) => p.id));
    for (const id of [...posing.keys()]) if (!live.has(id)) posing.delete(id);
    for (const id of [...orbits.keys()]) if (!live.has(id)) dropOrbit(id);
  }
}

export function hud(player, extra) {
  const mag = magOf(player);
  const ratio = mag / MAG_MAX;
  const colour = ratio > 0.5 ? "§d" : ratio > 0.2 ? "§e" : "§c";
  const techKey = str(player, PROP.tech, "repulse");
  const tech = TECH[techKey];
  // 段階はローマ数字で常に出す。いま自分がどこまで来たのかが
  // 画面のどこにも無いと、昇格しても実感が残らない。
  const parts = [
    { text: `§6${roman(stageOf(player))}§r ` },
    { translate: "marvel.hud.mag" },
    { text: ` ${colour}${bar(ratio, 12)}§r ${Math.ceil(mag)}` },
  ];
  if (tech) {
    parts.push({ text: "  §7|§r  " });
    parts.push({ translate: `marvel.tech.${techKey}` });
  }
  if (extra) parts.push({ text: `  §7|§r ${extra}` });
  actionbar(player, { rawtext: parts });
}

/**
 * ログイン時の復帰処理。
 * 落ちた瞬間に技を撃っていた場合、頭には技の変身体が残り、
 * `casting` も立ったままになる。素の体に戻してから再開する。
 */
export function restore(player) {
  endPose(player);
  dropOrbit(player.id);
  fogPopAll(player);
  if (!isTransformed(player)) {
    player.removeTag(TAG.form);
    clearForm(player);
    return;
  }
  player.addTag(TAG.form);
  applyBuffs(player);
  wearForm(player, baseForm(player));
}

/** 変身していないのに残っている体アイテムを掃除する。 */
export function sweepFormItems() {
  for (const player of allPlayers()) {
    if (isTransformed(player)) continue;
    const inv = container(player);
    if (!inv) continue;
    for (let i = 0; i < inv.size; i++) {
      const item = safe(() => inv.getItem(i));
      if (item && FORM_ITEMS.includes(item.typeId)) safe(() => inv.setItem(i, undefined));
    }
  }
}

/**
 * 死んだ場所に落ちた体アイテムを消す。
 *
 * 体アイテムは頭スロットに装備しているので、死ぬと **普通の落し物として
 * 世界に転がる**。拾えてしまうし、変身していない誰かが被れてしまう。
 * 死亡直後のその場だけを見て回収する（世界中を舐めるのは高い）。
 */
function sweepDroppedForms(dimension, location) {
  const items = safe(() => dimension.getEntities({
    location, maxDistance: 6, type: "minecraft:item",
  })) ?? [];
  for (const entity of items) {
    const stack = safe(() => entity.getComponent("minecraft:item")?.itemStack);
    if (stack && FORM_ITEMS.includes(stack.typeId)) safe(() => entity.remove());
  }
}

world.afterEvents.entityDie.subscribe((ev) => {
  const e = ev.deadEntity;
  if (e?.typeId !== "minecraft:player") return;
  const dimension = safe(() => e.dimension);
  const at = safe(() => e.location);
  system.run(() => {
    setProp(e, PROP.form, false);
    setProp(e, PROP.flying, false);
    setProp(e, PROP.casting, "");
    setProp(e, PROP.sight, 0);
    e.removeTag(TAG.form);
    setProp(e, PROP.mag, MAG_MAX * 0.4);
    posing.delete(e.id);
    dropOrbit(e.id);
    safe(() => fogPopAll(e));
    // 変身前の効果は戻す（死んで消えているので実質は控えの後始末）。
    setProp(e, PROP_EFFECTS, "");
  });
  // 落し物が出るのは死亡処理の後なので、少し置いてから拾いに行く。
  if (dimension && at) safe(() => system.runTimeout(() => sweepDroppedForms(dimension, at), 10));
});

// 退出したプレイヤーの後始末。周回鉄片を消し、Map から名前を落とす。
// ここを忘れると、無人の座標を鉄片が回り続ける。
world.afterEvents.playerLeave?.subscribe?.((ev) => {
  const id = ev.playerId;
  if (!id) return;
  posing.delete(id);
  dropOrbit(id);
  forgetFog(id);
});
