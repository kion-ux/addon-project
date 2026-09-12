# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — 挙動テスト (企画書 §17 QA)。

Minecraft はここで動かせないので、@minecraft/server の機能する代役を作って
スクリプトを実際に走らせる。実機でしか見られないもの（描画・音・タッチ操作）は
対象外だが、企画書の受入試験のうち「数えられるもの」はここで潰しておく:

    QA-03  アイテム使用100回で個数が増減しない
    QA-04  変身・解除20往復で残留が出ない
    QA-07  単発は1回、連打は定義回数だけ命中する／壁越しと自分には当たらない
    QA-09  気力無限は消費だけを無効にし、クールダウンは効いたまま
    QA-10  地形破壊 OFF のとき、どの技もブロックを書き換えない
    §09    しゃがみ＋使用は技を発動しない（切替と発動の排他）

自動検査では JSON・参照・数値・命中ロジックを確認し、見た目・音・タッチ操作は
実機で検収する（企画書 §17 のとおり）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(ROOT, "packs", "gla_BP", "scripts")

SERVER_STUB = r"""
globalThis.__tick = 0;
globalThis.__pending = [];      // [fireAtTick, fn]
globalThis.__particles = [];
globalThis.__sounds = [];
globalThis.__blockWrites = [];
globalThis.__commands = [];
globalThis.__wall = false;      // true なら視線が必ず遮られる

export const system = {
  get currentTick() { return globalThis.__tick; },
  run(f) { try { f(); } catch (e) { globalThis.__err = e; } },
  runTimeout(f, ticks) {
    globalThis.__pending.push([globalThis.__tick + (ticks ?? 1), f]);
    return globalThis.__pending.length;
  },
  runInterval() { return 0; },
  clearRun() { },
  afterEvents: new Proxy({}, { get() { return { subscribe() { } }; } }),
};

const eventList = new Proxy({}, {
  get() { return { subscribe() { }, unsubscribe() { } }; },
});

const worldProps = new Map();
export const world = {
  afterEvents: eventList,
  beforeEvents: eventList,
  getAllPlayers() { return globalThis.__players ?? []; },
  sendMessage() { },
  getDynamicProperty(k) { return worldProps.get(k); },
  setDynamicProperty(k, v) { worldProps.set(k, v); },
};

export const EquipmentSlot = {
  Head: "Head", Chest: "Chest", Legs: "Legs", Feet: "Feet",
  Mainhand: "Mainhand", Offhand: "Offhand",
};

export class ItemStack {
  constructor(typeId, amount = 1) { this.typeId = typeId; this.amount = amount; }
  getComponent() { return undefined; }
}

export const GameMode = { survival: "survival", creative: "creative" };
export const EntityComponentTypes = {};
export default {};
"""

UI_STUB = r"""
class Form {
  title() { return this; }
  body() { return this; }
  button() { return this; }
  toggle() { return this; }
  slider() { return this; }
  dropdown() { return this; }
  textField() { return this; }
  show() { return Promise.resolve({ canceled: true }); }
}
export class ActionFormData extends Form { }
export class ModalFormData extends Form { }
export class MessageFormData extends Form { }
export default {};
"""

TEST = r"""
import { world, system } from "@minecraft/server";
import * as data from "./data.js";
import * as state from "./state.js";
import * as skills from "./skills.js";
import * as combat from "./combat.js";
import { handleUse } from "./main.js";

let failures = 0;
function ok(cond, label) {
  if (!cond) { failures++; console.log("  FAIL " + label); }
}
function eq(a, b, label) {
  if (a !== b) { failures++; console.log(`  FAIL ${label}: ${a} !== ${b}`); }
}

// --- 時間を進める ---------------------------------------------------------
function advance(ticks) {
  for (let i = 0; i < ticks; i++) {
    globalThis.__tick++;
    const due = globalThis.__pending.filter(([t]) => t <= globalThis.__tick);
    globalThis.__pending = globalThis.__pending.filter(([t]) => t > globalThis.__tick);
    for (const [, fn] of due) { try { fn(); } catch (e) { console.log("  ERR " + e); } }
  }
}

// --- 代役 -----------------------------------------------------------------
class Container {
  constructor(size = 36) { this.size = size; this.slots = new Array(size).fill(undefined); }
  getItem(i) { return this.slots[i]; }
  setItem(i, v) { this.slots[i] = v; }
  addItem(stack) {
    for (let i = 0; i < this.size; i++) {
      if (!this.slots[i]) { this.slots[i] = stack; return undefined; }
    }
    return stack;
  }
  count(typeId) {
    return this.slots.reduce((n, s) => n + (s?.typeId === typeId ? (s.amount ?? 1) : 0), 0);
  }
}

class Target {
  constructor(id, x, y, z, typeId = "minecraft:zombie") {
    this.id = id; this.typeId = typeId;
    this.location = { x, y, z };
    this.damage = 0; this.knocks = 0; this.burned = 0; this.removed = false;
    this.hp = 200;
  }
  getComponent(n) {
    if (n === "minecraft:health") {
      return { currentValue: this.hp, effectiveMax: 200 };
    }
    return undefined;
  }
  applyDamage(a) { this.damage += a; return true; }
  applyKnockback() { this.knocks++; }
  setOnFire(s) { this.burned += s; return true; }
  teleport(l) { this.location = l; }
  remove() { this.removed = true; }
}

class DroppedItem {
  constructor(id, typeId, x, y, z) {
    this.id = id; this.typeId = "minecraft:item";
    this.stackType = typeId;
    this.location = { x, y, z }; this.removed = false;
  }
  getComponent(n) {
    if (n === "minecraft:item") return { itemStack: { typeId: this.stackType } };
    return undefined;
  }
  remove() { this.removed = true; }
}

class Dimension {
  constructor() { this.entities = []; }
  getEntities(opt) {
    const c = opt?.location;
    const r = opt?.maxDistance ?? 1e9;
    return this.entities.filter((e) => {
      if (e.removed) return false;
      if (opt?.families) return false;             // vfx/target family は使わない
      if (opt?.type && e.typeId !== opt.type) return false;
      if (!c) return true;
      return Math.hypot(e.location.x - c.x, e.location.y - c.y,
                        e.location.z - c.z) <= r;
    });
  }
  spawnParticle(id, loc) { globalThis.__particles.push([id, loc]); }
  playSound(id) { globalThis.__sounds.push(id); }
  spawnEntity(typeId, loc) {
    const e = new Target("spawn" + this.entities.length, loc.x, loc.y, loc.z, typeId);
    this.entities.push(e);
    return e;
  }
  getBlock(p) {
    return {
      isAir: true, isLiquid: false, location: p,
      setType(t) { globalThis.__blockWrites.push([p, t]); },
    };
  }
  getBlockFromRay(from, dir, opt) {
    if (!globalThis.__wall) return undefined;
    return { block: { isAir: false, isLiquid: false,
                      location: { x: from.x, y: from.y, z: from.z } } };
  }
}

class Player {
  constructor(dim) {
    this.id = "p1";
    this.typeId = "minecraft:player";
    this.dimension = dim;
    this.location = { x: 0, y: 64, z: 0 };
    this.isSneaking = false;
    this.props = new Map();
    this.tags = new Set();
    this.effects = new Map();
    this.container = new Container();
    this.head = undefined;
    this.anims = [];
    this.messages = 0;
  }
  get selectedSlotIndex() { return this._slot ?? 0; }
  set selectedSlotIndex(v) { this._slot = v; }
  getDynamicProperty(k) { return this.props.get(k); }
  setDynamicProperty(k, v) { this.props.set(k, v); }
  getViewDirection() { return { x: 0, y: 0, z: 1 }; }
  getComponent(n) {
    if (n === "minecraft:inventory") return { container: this.container };
    if (n === "minecraft:equippable") {
      const self = this;
      return {
        getEquipment(slot) { return slot === "Head" ? self.head : undefined; },
        setEquipment(slot, item) { if (slot === "Head") self.head = item; return true; },
      };
    }
    if (n === "minecraft:health") return { currentValue: 20, effectiveMax: 20 };
    return undefined;
  }
  addEffect(id, ticks, opt) { this.effects.set(id, { ticks, ...opt }); }
  removeEffect(id) { this.effects.delete(id); }
  addTag(t) { this.tags.add(t); }
  removeTag(t) { this.tags.delete(t); }
  sendMessage() { this.messages++; }
  playAnimation(a) { this.anims.push(a); }
  applyKnockback() { }
  runCommand(c) { globalThis.__commands.push(c); return { successCount: 1 }; }
  get onScreenDisplay() {
    return { setActionBar() { }, setTitle() { } };
  }
}

const dim = new Dimension();
const player = new Player(dim);
globalThis.__players = [player];
globalThis.__dimension = dim;

// ---------------------------------------------------------------------------
console.log("GRAND LINE AWAKENING behaviour tests");

// --- 定義そのもの ---------------------------------------------------------
eq(data.TECHS.length, 24, "24 techniques");
eq(data.FORMS.length, 6, "6 forms");
eq(new Set(data.TECHS.map((t) => t.id)).size, 24, "technique ids unique");
for (const t of data.TECHS) {
  ok(t.stages.some((s) => s.layer === 1), `${t.id} has an omen stage`);
  ok(t.windup > 0 && t.recover > 0, `${t.id} has wind-up and recovery`);
  ok(data.FORM_BY_KEY[t.form] !== undefined, `${t.id} belongs to a real form`);
}
// 企画書 §10 差別化: 単発 / 連打 / 重い一撃 がデータ上で区別できること
ok(data.TECHS.some((t) => t.hits === 1 && t.damage <= 12), "a light single hit exists");
ok(data.TECHS.some((t) => t.hits >= 8), "a multi-hit technique exists");
ok(data.TECHS.some((t) => t.damage >= 40 && t.windup >= 20), "a heavy slow hit exists");

// --- 能力の獲得 -----------------------------------------------------------
state.grantPower(player, true);
ok(state.hasPower(player), "power granted");
eq(state.energy(player), data.ENERGY_MAX, "energy starts full");

// --- 悪魔の実は食べたら消え、配り直されない（企画書 §14）----------------------
{
  const p2 = new Player(dim);
  p2.id = "p2";
  globalThis.__players = [player, p2];
  p2.container.setItem(0, { typeId: data.ITEM.fruit, amount: 1 });
  p2.selectedSlotIndex = 0;
  eq(state.hasPower(p2), false, "a fresh player has no power");
  state.grantPower(p2, false, data.ITEM.fruit);
  eq(state.hasPower(p2), true, "eating the fruit grants the power");
  eq(p2.container.count(data.ITEM.fruit), 0, "the fruit is consumed");
  // 二度目は何も起きない（実も減らない）
  p2.container.setItem(1, { typeId: data.ITEM.fruit, amount: 1 });
  p2.selectedSlotIndex = 1;
  state.grantPower(p2, true, data.ITEM.fruit);
  eq(p2.container.count(data.ITEM.fruit), 1,
     "a second fruit is not consumed once the power is held");
  // 実を持っていなければ能力も得られない
  const p3 = new Player(dim);
  p3.id = "p3";
  state.grantPower(p3, false, data.ITEM.fruit);
  eq(state.hasPower(p3), false, "no fruit in hand means no power");
  globalThis.__players = [player];
}

// --- QA-04: 変身・解除 20 往復で残留が出ない --------------------------------
player.setDynamicProperty(data.PROP.hits, 9999);       // 全形態を解放
let residue = 0;
for (let i = 0; i < 20; i++) {
  const key = data.FORM_ORDER[i % data.FORM_ORDER.length];
  state.setEnergy(player, data.ENERGY_MAX);
  state.transform(player, key);
  advance(4);
  if (player.head?.typeId !== data.FORM_BY_KEY[key].item) residue++;
  state.revert(player);
  advance(12);
  if (player.head !== undefined) residue++;
  if (state.formKey(player) !== "") residue++;
  if (player.effects.has("invisibility")) residue++;
}
eq(residue, 0, "QA-04 20 transform/revert round trips leave no residue");
eq(state.phase(player), "normal", "QA-04 ends in the normal phase");

// --- QA-03: アイテム使用100回で個数が変わらない ------------------------------
player.container.setItem(0, { typeId: data.ITEM.hat, amount: 1 });
player.container.setItem(1, { typeId: data.ITEM.wrap, amount: 1 });
player.container.setItem(2, { typeId: data.ITEM.pose, amount: 1 });
const before = [data.ITEM.hat, data.ITEM.wrap, data.ITEM.pose]
  .map((id) => player.container.count(id));
state.setEnergy(player, data.ENERGY_MAX);
state.transform(player, "normal");
advance(20);
for (let i = 0; i < 100; i++) {
  player.isSneaking = i % 3 === 0;
  handleUse(player, { typeId: data.ITEM.wrap });
  handleUse(player, { typeId: data.ITEM.pose });
  advance(2);
}
player.isSneaking = false;
advance(40);
const after = [data.ITEM.hat, data.ITEM.wrap, data.ITEM.pose]
  .map((id) => player.container.count(id));
eq(JSON.stringify(after), JSON.stringify(before), "QA-03 item counts unchanged");
// 形態アイテムは絶対にインベントリへ入らない
let leaked = 0;
for (const id of data.FORM_ITEMS) leaked += player.container.count(id);
eq(leaked, 0, "QA-03 no form item ever reaches the inventory");

// --- QA-03: 持ち物がいっぱいのまま変身しても兜が消えない ----------------------
state.safeReset(player, true);
player.head = { typeId: "minecraft:diamond_helmet", amount: 1 };
for (let i = 0; i < player.container.size; i++) {
  player.container.setItem(i, { typeId: "minecraft:stone", amount: 64 });
}
state.setEnergy(player, data.ENERGY_MAX);
state.transform(player, "normal");
advance(20);
eq(player.head?.typeId, "minecraft:diamond_helmet",
   "QA-03 a full inventory refuses the transform instead of eating the helmet");
eq(state.formKey(player), "", "QA-03 the refused transform left no form behind");
// 片付けて次のテストへ
player.head = undefined;
for (let i = 0; i < player.container.size; i++) player.container.setItem(i, undefined);

// --- 兜は変身でしまわれ、解除で戻る -----------------------------------------
state.safeReset(player, true);
player.head = { typeId: "minecraft:diamond_helmet", amount: 1 };
state.setEnergy(player, data.ENERGY_MAX);
state.transform(player, "normal");
advance(20);
eq(player.head?.typeId, data.FORM_BY_KEY.normal.item, "transform wears the form body");
eq(player.container.count("minecraft:diamond_helmet"), 1, "the helmet was stashed");
state.revert(player);
advance(20);
eq(player.head?.typeId, "minecraft:diamond_helmet", "revert puts the helmet back on");
eq(player.container.count("minecraft:diamond_helmet"), 0, "the helmet is not duplicated");
player.head = undefined;
for (let i = 0; i < player.container.size; i++) player.container.setItem(i, undefined);

// --- 形態表示体は世界に残らない（企画書 §14 / QA-03）-------------------------
// 頭に被ったまま変身していない = 自分の体＋もう一体の二重表示。掃除で外す。
state.safeReset(player, true);
player.head = { typeId: data.FORM_ITEMS[0], amount: 1 };
state.sweepFormItems(player);
eq(player.head, undefined, "a form body worn without a form is taken off");

// 変身中でも、いま選んでいる形態と食い違う表示体は外す
state.setEnergy(player, data.ENERGY_MAX);
state.transform(player, "normal");
advance(20);
player.head = { typeId: data.FORM_ITEMS[5], amount: 1 };   // 別の形態の表示体
state.sweepFormItems(player);
eq(player.head, undefined, "a mismatched form body is taken off while transformed");
state.safeReset(player, true);

// 地面に落ちていたら拾って消す
const dropped = new DroppedItem("d1", data.FORM_ITEMS[2], 0, 64, 2);
const other = new DroppedItem("d2", "minecraft:dirt", 0, 64, 2);
dim.entities = [dropped, other];
state.sweepDroppedForms();
eq(dropped.removed, true, "a dropped form body is removed from the ground");
eq(other.removed, false, "an ordinary dropped item is left alone");
dim.entities = [];

// --- 形態を切り替えても、自分で被り直した兜は消えない -------------------------
state.safeReset(player, true);
state.setEnergy(player, data.ENERGY_MAX);
state.transform(player, "normal");
advance(20);
player.head = { typeId: "minecraft:iron_helmet", amount: 1 };   // 手で被り直した
state.setEnergy(player, data.ENERGY_MAX);
state.transform(player, "gear2");
advance(20);
eq(player.container.count("minecraft:iron_helmet"), 1,
   "switching forms stashes a helmet the player put back on");
eq(player.head?.typeId, data.FORM_BY_KEY.gear2.item, "the new form body is worn");
state.safeReset(player, true);
for (let i = 0; i < player.container.size; i++) player.container.setItem(i, undefined);
player.head = undefined;

// --- §09: しゃがみ＋使用は技を出さない -------------------------------------
state.safeReset(player, true);
state.setEnergy(player, data.ENERGY_MAX);
state.transform(player, "normal");
advance(20);
const t0 = new Target("t0", 0, 64, 4);
dim.entities = [t0];
player.isSneaking = true;
for (let i = 0; i < 10; i++) { handleUse(player, { typeId: data.ITEM.wrap }); advance(6); }
player.isSneaking = false;
advance(40);
eq(t0.damage, 0, "sneak+use never casts a technique");

// --- QA-07: 単発は1回だけ当たる --------------------------------------------
dim.entities = [t0];
t0.damage = 0;
const pistol = data.TECH_BY_ID.pistol;
state.setEnergy(player, data.ENERGY_MAX);
ok(skills.cast(player, pistol), "single-hit technique casts");
advance(pistol.windup + pistol.active + pistol.recover + 6);
eq(t0.damage, Math.round(pistol.damage), "QA-07 a single-hit technique lands exactly once");

// --- 表示体は必ず片付く（企画書 §14 所有者と寿命）----------------------------
dim.entities = [];
state.setEnergy(player, data.ENERGY_MAX);
globalThis.__tick += 200;
skills.cast(player, pistol);
advance(pistol.windup + pistol.active + pistol.recover + 40);
const fists = dim.entities.filter((e) => e.typeId === "gla:vfx_fist");
ok(fists.length > 0, "a line technique spawns the fist display entity");
ok(fists.every((e) => e.removed), "every display entity it spawned was removed");
dim.entities = [];

// --- QA-07: 連打は定義回数だけ当たる ---------------------------------------
const gatling = data.TECH_BY_ID.gatling;
const t1 = new Target("t1", 0, 64, 4);
dim.entities = [t1];
state.setEnergy(player, data.ENERGY_MAX);
globalThis.__tick += 200;                       // クールダウンを流す
ok(skills.cast(player, gatling), "multi-hit technique casts");
advance(gatling.windup + gatling.active + gatling.recover + 10);
const expected = Math.round(gatling.damage) * gatling.hits;
eq(t1.damage, expected, "QA-07 a multi-hit technique lands exactly its defined count");

// --- QA-07: 壁越しには当たらない -------------------------------------------
const t2 = new Target("t2", 0, 64, 6);
dim.entities = [t2];
globalThis.__wall = true;
state.setEnergy(player, data.ENERGY_MAX);
globalThis.__tick += 200;
skills.cast(player, pistol);
advance(pistol.windup + pistol.active + pistol.recover + 6);
globalThis.__wall = false;
eq(t2.damage, 0, "QA-07 no hit through a wall");

// --- QA-07: 自分には当たらない ---------------------------------------------
dim.entities = [player];
state.setEnergy(player, data.ENERGY_MAX);
globalThis.__tick += 200;
const star = data.TECH_BY_ID.white_star;          // 唯一の全方位技
state.transform(player, "gear5");
advance(data.SHOWPIECE_TICKS + 6);
skills.cast(player, star);
advance(star.windup + star.active + star.recover + 6);
ok(true, "all-round technique does not throw");
eq(player.effects.has("__damaged__"), false, "QA-07 the caster is never a target");

// --- 復旧は技が掛けた自己強化も落とす（企画書 §14）---------------------------
state.safeReset(player, true);
player.setDynamicProperty(data.PROP.infinite, true);
state.transform(player, "gear5");
advance(data.SHOWPIECE_TICKS + 6);
globalThis.__tick += 400;
const giant = data.TECH_BY_ID.giant;
skills.cast(player, giant);
advance(giant.windup + 4);
ok(player.effects.size > 0, "the self-buff technique applied effects");
state.safeReset(player, true);
for (const [id] of giant.buffs) {
  eq(player.effects.has(id), false, `safe reset clears the technique effect ${id}`);
}

// --- 長い技の予約が、あとから出した別の技を壊さない（企画書 §14）---------------
// 巨人化は 430 tick ぶんの処理を予約する。復旧してから別の技を出したとき、
// 古い予約が phase を書き換えてしまうと、新しい技が空振りになる。
state.safeReset(player, true);
player.setDynamicProperty(data.PROP.infinite, true);
state.transform(player, "gear5");
advance(data.SHOWPIECE_TICKS + 6);
globalThis.__tick += 500;
skills.cast(player, data.TECH_BY_ID.giant);       // 長い予約を積む
advance(6);
state.safeReset(player, true);                    // 途中で復旧する
state.transform(player, "normal");
advance(24);
const stale = new Target("stale", 0, 64, 4);
dim.entities = [stale];
globalThis.__tick += 500;
ok(skills.cast(player, pistol), "a new technique casts after a long one was reset");
advance(pistol.windup + pistol.active + pistol.recover + 6);
eq(stale.damage, Math.round(pistol.damage),
   "the earlier cast's reservations do not cancel the new one");

// --- 叩きつけは着弾地点の周囲、前方の円錐ではない -----------------------------
state.safeReset(player, true);
player.setDynamicProperty(data.PROP.infinite, true);
state.transform(player, "gear3");
advance(20);
const axe = data.TECH_BY_ID.gigant_axe;
eq(axe.shape, "slam", "巨人の斧 is declared as a slam");
// 射程(5)より遠いが、着弾地点(z=5)からは半径(3.4)以内。
// 前方の円錐なら届かず、着弾地点の周囲なら届く位置。
const beyond = new Target("beyond", 0, 64, 8);
const behind = new Target("behind", 0, 64, -5);
dim.entities = [beyond, behind];
globalThis.__tick += 400;
skills.cast(player, axe);
advance(axe.windup + axe.active + axe.recover + 20);
ok(beyond.damage > 0, "a slam reaches around its impact point, not just a cone");
eq(behind.damage, 0, "a slam does not reach a target behind the caster");

// --- 遅延技も壁越しには当たらない -------------------------------------------
state.safeReset(player, true);
player.setDynamicProperty(data.PROP.infinite, true);
state.transform(player, "gear5");
advance(data.SHOWPIECE_TICKS + 6);
const under = data.TECH_BY_ID.under_strike;
const walled = new Target("walled", 0, 64, 8);
dim.entities = [walled];
globalThis.__wall = true;
globalThis.__tick += 400;
skills.cast(player, under);
advance(under.windup + under.active + under.recover + 20);
globalThis.__wall = false;
eq(walled.damage, 0, "the delayed technique does not reach through a wall");

// --- QA-09: 気力無限は消費だけ無効、クールダウンは生きている -------------------
state.safeReset(player, true);
state.setEnergy(player, data.ENERGY_MAX);
state.transform(player, "normal");
advance(20);
player.setDynamicProperty(data.PROP.infinite, true);
const startEnergy = state.energy(player);
dim.entities = [];
globalThis.__tick += 200;
ok(skills.cast(player, pistol), "first cast with infinite energy");
eq(state.energy(player), startEnergy, "QA-09 infinite energy consumes nothing");
advance(2);
eq(skills.cast(player, pistol), false, "QA-09 cooldown still blocks a second cast");
player.setDynamicProperty(data.PROP.infinite, false);

// --- QA-10: 地形破壊 OFF ではブロックを書き換えない ---------------------------
globalThis.__blockWrites.length = 0;
eq(combat.terrainAllowed(), false, "QA-10 terrain is off by default");
for (const t of data.TECHS) {
  state.safeReset(player, true);
  state.setEnergy(player, data.ENERGY_MAX);
  player.setDynamicProperty(data.PROP.infinite, true);
  state.transform(player, t.form);
  advance(data.SHOWPIECE_TICKS + 4);
  globalThis.__tick += 900;
  skills.cast(player, t);
  advance(t.windup + t.active + t.recover + 40);
}
eq(globalThis.__blockWrites.length, 0,
   "QA-10 no technique writes a block while terrain is off");
eq(combat.pvpAllowed(), false, "PvP is off by default");

// --- 復旧 -----------------------------------------------------------------
state.safeReset(player, true);
eq(state.phase(player), "normal", "safe reset returns to normal");
eq(player.head, undefined, "safe reset removes the form item");
eq(player.effects.has("invisibility"), false, "safe reset clears invisibility");
eq(state.formKey(player), "", "safe reset clears the form");

// --- 全ての技が例外なく走り切る ---------------------------------------------
let cast = 0;
for (const t of data.TECHS) {
  state.safeReset(player, true);
  player.setDynamicProperty(data.PROP.infinite, true);
  state.transform(player, t.form);
  advance(data.SHOWPIECE_TICKS + 4);
  globalThis.__tick += 900;
  dim.entities = [new Target("x" + cast, 0, 64, 3)];
  if (skills.cast(player, t)) cast++;
  advance(t.windup + t.active + t.recover + 40);
}
eq(cast, 24, "every one of the 24 techniques casts without throwing");
ok(globalThis.__err === undefined, "no exception escaped into system.run");

console.log(`  ${data.TECHS.length} techniques, ${data.FORMS.length} forms, ` +
            `${globalThis.__particles.length} particles emitted in test`);
if (failures) {
  console.log(`  ${failures} failing assertion(s)`);
  process.exit(1);
}
console.log("  behaviour tests passed");
"""


def main() -> int:
    if not os.path.isdir(SCRIPTS):
        print("  GRAND LINE AWAKENING: skipped (no scripts)")
        return 0
    tmp = tempfile.mkdtemp(prefix="gla-logic-")
    try:
        with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as fh:
            json.dump({"name": "gla-test", "type": "module"}, fh)
        for mod, body in (("@minecraft/server", SERVER_STUB),
                          ("@minecraft/server-ui", UI_STUB)):
            d = os.path.join(tmp, "node_modules", *mod.split("/"))
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.js"), "w", encoding="utf-8") as fh:
                fh.write(body)
            with open(os.path.join(d, "package.json"), "w", encoding="utf-8") as fh:
                json.dump({"name": mod, "version": "1.0.0", "type": "module",
                           "main": "index.js"}, fh)

        for f in sorted(os.listdir(SCRIPTS)):
            if f.endswith(".js"):
                shutil.copy(os.path.join(SCRIPTS, f), os.path.join(tmp, f))

        entry = os.path.join(tmp, "__test.js")
        with open(entry, "w", encoding="utf-8") as fh:
            fh.write(TEST)

        res = subprocess.run(["node", entry], capture_output=True, text=True)
        if res.stdout.strip():
            print(res.stdout.rstrip())
        if res.returncode:
            if res.stderr.strip():
                print(res.stderr.strip()[:4000])
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
