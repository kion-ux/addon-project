# -*- coding: utf-8 -*-
"""アストロ・ナノギア — スクリプトの挙動テスト（Minecraft 無しで全形態・全技を実際に走らせる）。

@minecraft/server と @minecraft/server-ui を「動く」スタブに差し替え、偽のプレイヤー（本物の
スロットを持つインベントリ・全装備スロット・動的プロパティ・カメラ・入力ロック）・敵・地面・tick を
用意して、9 形態それぞれについて次を実行して確かめる:

* 変身（時間割が最後まで進む・頭にスーツ・手にウェポン・防具の退避・カメラと入力ロックが戻る）
* 4 技（惑星技と必殺は必ずダメージ。機動技・空中技も meta.noDamage に無ければダメージ）
* 三段コンボ（三段目で combo3 が呼ばれる）・ナノ・バリア・二段ジャンプ・ホバー・ブースト・回避・ジャスト回避
* スニーク静止で解除（スーツの分解 → 防具を着せ直す・ウェポン → コア）
* 星力切れ → 強制解除 → オーバーヒート中は変身できない
* 変身中の死亡 → リスポーンで解除（コアは 1 個だけ残る）・変身の演出中の死亡
* 再参加で変身状態の復元・演出中の退出 → 再参加で後始末
* ターミナル（フォームの移動・設定の保存・UserBusy の再試行）・コマンド・ホログラム標的・enemies.js のフック
* 雛形 planets/_template.js をそのまま読み込んで動くか
* 例外・"[astro]" の警告が無いこと

さらに、使ったパーティクル ID・効果音 ID・全身モーション名・アイテム ID・エンティティ ID・
フォームのアイコンがパックに実在するかを調べる。リソースがまだ生成されていなければ
"SKIPPED (resource not generated yet)" と出してその項目だけ飛ばす（生成された後は食い違いで失敗）。
パーティクル ID・効果音 ID は DESIGN.md の §4.7 / §4.9 の一覧とも照合する。

    python3 tools/astro/test_astro.py              # 全形態
    python3 tools/astro/test_astro.py --planet mars  # 1 形態だけ（共通の検査も走る）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BP = os.path.join(ROOT, "packs", "astro_BP")
RP = os.path.join(ROOT, "packs", "astro_RP")
SCRIPTS = os.path.join(BP, "scripts")
DESIGN = os.path.join(HERE, "DESIGN.md")
PLANET_KEYS = ["mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune", "sol"]

# ---------------------------------------------------------------------------
#  @minecraft/server のスタブ
# ---------------------------------------------------------------------------
SERVER = r"""
const G = globalThis;
G.__log = {
  particles: new Map(), sounds: new Map(), anims: new Map(), cmds: [], warns: [], molang: new Set(),
  items: new Set(), spawned: new Set(), icons: new Set(), forms: [], teleportFails: [], titleFails: [],
  fadeFails: [], perTick: new Map(), budgetMax: 0, animAt: [],
};
G.__handlers = {};
G.__formAnswers = [];
G.__items = new Set(JSON.parse(process.env.ASTRO_ITEMS || "[]"));
G.__walls = [];   // [{x0,x1,y0,y1,z0,z1}] 試験用の壁
G.__holes = [];   // [{x0,x1,z0,z1}] 試験用の穴（虚空。地面が無い）

const sched = new Map();   // tick -> [fn]
const intervals = [];
export const system = {
  currentTick: 0,
  run(f) { return this.runTimeout(f, 1); },
  runTimeout(f, t = 1) {
    const due = this.currentTick + Math.max(1, Math.round(t));
    if (!sched.has(due)) sched.set(due, []);
    sched.get(due).push(f);
    return due;
  },
  runInterval(f, t = 1) { intervals.push({ every: Math.max(1, t), f }); return intervals.length; },
  clearRun() { },
  afterEvents: { scriptEventReceive: { subscribe(f, o) { G.__handlers.scriptEventReceive = f; G.__seOpts = o; return f; } } },
  beforeEvents: {},
};
G.__advance = (n = 1) => {
  for (let i = 0; i < n; i++) {
    system.currentTick++;
    const t = system.currentTick;
    for (const d of G.__dims) for (const e of [...d.entities]) e.__physics?.();
    for (const iv of intervals) if (t % iv.every === 0) iv.f();
    const due = sched.get(t);
    if (due) { sched.delete(t); for (const f of due) f(); }
    G.__onTick?.(t);
  }
};
const mkEvents = () => new Proxy({}, { get(_, name) {
  return { subscribe(f) { G.__handlers[name] = f; return f; }, unsubscribe() { } };
} });
const after = mkEvents();
const before = new Proxy({}, { get(_, name) {
  return { subscribe(f) { G.__handlers["before_" + name] = f; return f; }, unsubscribe() { } };
} });

export const EasingType = { InOutSine: "InOutSine", Linear: "Linear" };
export const ItemLockMode = { inventory: "inventory", none: "none", slot: "slot" };
export const EquipmentSlot = { Head: "Head", Chest: "Chest", Legs: "Legs", Feet: "Feet", Mainhand: "Mainhand", Offhand: "Offhand" };

export class MolangVariableMap {
  constructor() { this.vars = {}; }
  setFloat(k, v) {
    if (!Number.isFinite(v)) throw new Error(`non-finite molang ${k}=${v}`);
    if (!k.startsWith("variable.")) throw new Error(`molang name ${k}`);
    this.vars[k] = v; G.__log.molang.add(k);
  }
  setVector3(k, v) { this.vars[k] = v; }
}

export class ItemStack {
  constructor(typeId, amount = 1) {
    if (typeof typeId !== "string" || !typeId.includes(":")) throw new Error(`bad item id ${typeId}`);
    if (typeId.startsWith("astro:") && G.__items.size && !G.__items.has(typeId)) throw new Error(`unknown item ${typeId}`);
    this.typeId = typeId; this.amount = amount; this.lockMode = "none"; this.keepOnDeath = false;
    this.props = new Map(); this.nameTag = undefined;
    G.__log.items.add(typeId);
  }
  get maxAmount() { return this.typeId.startsWith("astro:") ? 1 : 64; }
  clone() {
    const c = Object.create(ItemStack.prototype);
    Object.assign(c, this); c.props = new Map(this.props); return c;
  }
  getDynamicProperty(k) { return this.props.get(k); }
  setDynamicProperty(k, v) { if (v === undefined) this.props.delete(k); else this.props.set(k, v); }
  getLore() { return []; } setLore() { }
}

export class FakeContainer {
  constructor(size = 36) { this.size = size; this.slots = new Array(size).fill(undefined); }
  _i(i) { if (!Number.isInteger(i) || i < 0 || i >= this.size) throw new Error(`bad slot ${i}`); return i; }
  getItem(i) { const it = this.slots[this._i(i)]; return it ? it.clone() : undefined; }
  setItem(i, it) {
    if (it !== undefined && !(it instanceof ItemStack)) throw new Error("setItem: not an ItemStack");
    this.slots[this._i(i)] = it ? it.clone() : undefined;
  }
  addItem(it) {
    const i = this.slots.findIndex((x) => !x);
    if (i < 0) return it;
    this.slots[i] = it.clone();
    return undefined;
  }
  get emptySlotsCount() { return this.slots.filter((x) => !x).length; }
  getSlot(i) { const c = this; return { getItem: () => c.getItem(i), setItem: (x) => c.setItem(i, x) }; }
}

const FAMILIES = { "minecraft:zombie": ["monster", "zombie", "mob"], "minecraft:cow": ["cow", "mob"],
                   "astro:void_drone": ["monster", "astro_enemy"], "astro:hologram_target": ["target"],
                   "minecraft:zombie_pigman": ["zombie_pigman", "undead", "monster", "mob"],
                   "minecraft:villager_v2": ["villager", "mob"], "minecraft:iron_golem": ["irongolem", "mob"],
                   "minecraft:horse": ["horse", "mob"] };
let nextId = 1;
export class FakeEntity {
  constructor(dim, typeId, loc, hp = 20, id) {
    this.id = id ?? String(nextId++);
    this.typeId = typeId;
    this.dimension = dim;
    this.location = { ...loc };
    this.vel = { x: 0, y: 0, z: 0 };
    this.view = { x: 0, y: 0, z: 1 };
    this.hp = hp; this.maxHp = hp;
    this.alive = true;
    this.isSneaking = false; this.isSprinting = false; this.isOnGround = loc.y <= 64.0001; this.isJumping = false;
    this.isInWater = false;
    this.lastHurt = -99;
    this.props = new Map();
    this.effects = new Map();
    this.nameTag = "";
    this.name = "Tester" + this.id;
    this.selectedSlotIndex = 0;
    this.item = undefined;
    this.title = ""; this.subtitle = ""; this.actionbar = "";
    if (typeId === "minecraft:player") {
      this.inv = new FakeContainer(36);
      this.equip = { Head: undefined, Chest: undefined, Legs: undefined, Feet: undefined, Offhand: undefined };
      this.camState = "clear";
      this.inputPermissions = { movementEnabled: true, cameraEnabled: true };
      const self = this;
      this.camera = {
        setCamera(preset, o) {
          if (preset !== "minecraft:free") throw new Error("preset " + preset);
          for (const k of ["location", "facingLocation"]) if (o?.[k] && !["x", "y", "z"].every((a) => Number.isFinite(o[k][a]))) throw new Error("bad camera");
          self.camState = "set"; G.__log.cmds.push("api:camera set");
        },
        fade(o) {
          const ft = o?.fadeTime;
          if (ft && ft.fadeInTime + ft.holdTime + ft.fadeOutTime < 0.499) G.__log.fadeFails.push(JSON.stringify(ft));
          G.__log.cmds.push("api:camera fade");
        },
        clear() { self.camState = "clear"; G.__log.cmds.push("api:camera clear"); },
      };
      this.onScreenDisplay = {
        setActionBar: (m) => { this.actionbar = String(m); },
        setTitle: (t, o) => {
          if (o && !["fadeInDuration", "stayDuration", "fadeOutDuration"].every((k) => Number.isFinite(o[k]))) G.__log.titleFails.push(String(t));
          this.title = String(t); this.subtitle = String(o?.subtitle ?? "");
        },
        updateSubtitle: (s) => { this.subtitle = String(s); },
        isValid: () => this.alive,
      };
    }
    dim.entities.push(this);
  }
  isValid() { return this.alive; }
  __physics() {
    if (!this.alive || !this.maxHp || this.typeId === "astro:dmg_text") return;
    if (this.hp <= 0) return;
    const lev = this.getEffect("levitation"), slow = this.getEffect("slow_falling");
    this.location.x += this.vel.x; this.location.z += this.vel.z;
    this.vel.x *= 0.55; this.vel.z *= 0.55;
    if (!this.isOnGround || this.vel.y > 0 || lev) {
      if (lev) this.vel.y = 0.045 * (lev.amplifier + 1);
      else { this.vel.y -= 0.08; if (slow) this.vel.y = Math.max(this.vel.y, -0.06); }
      this.vel.y = Math.max(this.vel.y, -3.5);
      this.location.y += this.vel.y;
      if (this.location.y <= 64) { this.location.y = 64; this.vel.y = 0; this.isOnGround = true; }
      else this.isOnGround = false;
    }
  }
  getComponent(name) {
    const e = this;
    if (this.comps && name in this.comps) return this.comps[name];
    if (name === "minecraft:health") {
      if (!this.maxHp) return undefined;
      return { get currentValue() { return e.hp; }, get effectiveMax() { return e.maxHp; },
               setCurrentValue(v) { if (!Number.isFinite(v)) throw new Error("bad hp"); e.hp = Math.max(0, Math.min(e.maxHp, v)); return true; } };
    }
    if (name === "minecraft:equippable" && this.equip) {
      return {
        getEquipment(slot) {
          if (slot === "Mainhand") return e.inv.getItem(e.selectedSlotIndex);
          if (!(slot in e.equip)) throw new Error("bad slot " + slot);
          return e.equip[slot] ? e.equip[slot].clone() : undefined;
        },
        setEquipment(slot, it) {
          if (it !== undefined && !(it instanceof ItemStack)) throw new Error("setEquipment: not an ItemStack");
          if (slot === "Mainhand") { e.inv.setItem(e.selectedSlotIndex, it); return true; }
          if (!(slot in e.equip)) throw new Error("bad slot " + slot);
          e.equip[slot] = it ? it.clone() : undefined; return true;
        },
      };
    }
    if (name === "minecraft:inventory" && this.inv) return { container: this.inv };
    if (name === "minecraft:item" && this.item) return { itemStack: this.item.clone() };
    if (name === "minecraft:projectile" && this.projectile) return this.projectile;
    return undefined;
  }
  applyDamage(amount, opts) {
    if (!Number.isFinite(amount) || amount < 0) throw new Error("bad damage " + amount);
    if (!this.alive || this.hp <= 0) return false;
    const t = system.currentTick;
    // バニラの被弾の無敵時間: 10 tick の間は前の一撃より強い分（差分）だけ通る（無敵の時計は戻らない）
    let take = amount;
    if (t - this.lastHurt < 10) {
      if (!(amount > (this.lastAmt ?? 0))) return false;
      take = amount - (this.lastAmt ?? 0);
    } else {
      this.lastHurt = t;
    }
    this.lastAmt = amount;
    const res = this.getEffect("resistance");
    const dmg = res && res.amplifier >= 4 ? 0 : take;
    this.hp -= dmg;
    if (dmg > 0) G.__handlers.entityHurt?.({ hurtEntity: this, damage: dmg,
      damageSource: { cause: opts?.cause ?? "entityAttack", damagingEntity: opts?.damagingEntity } });
    if (this.hp <= 0 && this.typeId !== "minecraft:player") {
      G.__handlers.entityDie?.({ deadEntity: this, damageSource: { cause: "entityAttack", damagingEntity: opts?.damagingEntity } });
      this.remove();
    }
    return true;
  }
  applyKnockback(dx, dz, h, v) {
    for (const x of [dx, dz, h, v]) if (!Number.isFinite(x)) throw new Error("bad knockback");
    this.vel = { x: dx * h, y: v, z: dz * h };
    if (v > 0) this.isOnGround = false;
  }
  applyImpulse(v) { this.vel = { x: this.vel.x + v.x, y: this.vel.y + v.y, z: this.vel.z + v.z }; }
  clearVelocity() { this.vel = { x: 0, y: 0, z: 0 }; }
  addEffect(id, ticks, o) {
    if (!Number.isFinite(ticks) || ticks <= 0) throw new Error("bad effect");
    this.effects.set(id, { amp: o?.amplifier ?? 0, until: system.currentTick + ticks, particles: o?.showParticles !== false });
  }
  getEffect(id) {
    const e = this.effects.get(id);
    if (!e || e.until <= system.currentTick) return undefined;
    return { typeId: id, amplifier: e.amp, duration: e.until - system.currentTick, particles: e.particles };
  }
  removeEffect(id) { return this.effects.delete(id); }
  hasEffect(id) { return !!this.getEffect(id); }
  teleport(loc, o) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error("bad teleport");
    const b = this.dimension.getBlock(loc), b2 = this.dimension.getBlock({ ...loc, y: loc.y + 1.2 });
    if (this.typeId === "minecraft:player" && (!b.isAir || !b2.isAir)) G.__log.teleportFails.push(JSON.stringify(loc));
    this.location = { ...loc };
  }
  getViewDirection() { return { ...this.view }; }
  getVelocity() { return { ...this.vel }; }
  getHeadLocation() { return { x: this.location.x, y: this.location.y + 1.6, z: this.location.z }; }
  getRotation() { return { x: 0, y: 0 }; }
  getDynamicProperty(k) { return this.props.get(k); }
  setDynamicProperty(k, v) {
    if (v !== undefined && !["string", "number", "boolean"].includes(typeof v)) throw new Error("bad prop type");
    if (typeof v === "string" && v.length > 32000) throw new Error("prop too long");
    if (v === undefined) this.props.delete(k); else this.props.set(k, v);
  }
  remove() { this.alive = false; const a = this.dimension.entities; const i = a.indexOf(this); if (i >= 0) a.splice(i, 1); }
  setOnFire() { return true; }
  matches(q) { const fam = FAMILIES[this.typeId] ?? []; return (q.families ?? []).every((f) => fam.includes(f)); }
  runCommand(c) {
    if (!this.alive) throw new Error("runCommand on removed entity");
    G.__log.cmds.push(c);
    if (c.startsWith("camera @s clear")) this.camState = "clear";
    else if (c.startsWith("camera @s set")) this.camState = "set";
    else if (c.startsWith("inputpermission set @s movement ")) this.inputPermissions.movementEnabled = c.endsWith("enabled");
    return { successCount: 1 };
  }
  playAnimation(name, o) {
    if (!this.alive) throw new Error("playAnimation on removed entity");
    G.__log.anims.set(name, (G.__log.anims.get(name) ?? 0) + 1);
    G.__log.animAt.push([system.currentTick, name, this.id]);
    if (G.__log.animAt.length > 400) G.__log.animAt.splice(0, 200);
  }
  getGameMode() { return this.gameMode ?? "survival"; }
  getEntitiesFromViewDirection(o) {
    if (this.viewHits) return this.viewHits().map((entity) => ({ entity, distance: 3 }));
    return this.dimension.entities.filter((e) => e !== this && e.maxHp && e.typeId !== "astro:dmg_text" && e.alive)
      .slice(0, 1).map((entity) => ({ entity, distance: 3 }));
  }
  getBlockFromViewDirection() {
    return { block: { location: { x: Math.floor(this.location.x + 6), y: 63, z: Math.floor(this.location.z + 6) }, typeId: "minecraft:stone" } };
  }
  sendMessage(m) { (this.messages ??= []).push(String(typeof m === "string" ? m : JSON.stringify(m))); }
  addTag() { return true; } removeTag() { return true; } hasTag() { return false; }
}

export class FakeDimension {
  constructor(id) { this.id = id; this.entities = []; }
  spawnParticle(id, loc, vars) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error(`bad particle loc ${id}`);
    if (vars && !(vars instanceof MolangVariableMap)) throw new Error("vars not MolangVariableMap");
    G.__log.particles.set(id, (G.__log.particles.get(id) ?? 0) + 1);
    const t = system.currentTick;
    const n = (G.__log.perTick.get(t) ?? 0) + 1;
    G.__log.perTick.set(t, n);
    if (n > G.__log.budgetMax) G.__log.budgetMax = n;
    if (G.__log.perTick.size > 400) G.__log.perTick.clear();
  }
  playSound(id, loc, o) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error(`bad sound loc ${id}`);
    G.__log.sounds.set(id, (G.__log.sounds.get(id) ?? 0) + 1);
  }
  getEntities(q = {}) {
    let list = this.entities.filter((e) => e.alive);
    if (q.type) list = list.filter((e) => e.typeId === q.type);
    if (q.families) list = list.filter((e) => e.matches({ families: q.families }));
    if (q.location && q.maxDistance !== undefined) {
      if (!Number.isFinite(q.maxDistance) || !["x", "y", "z"].every((k) => Number.isFinite(q.location[k]))) throw new Error("bad query");
      list = list.filter((e) => Math.hypot(e.location.x - q.location.x, e.location.y - q.location.y, e.location.z - q.location.z) <= q.maxDistance);
    }
    G.__log.queries = (G.__log.queries ?? 0) + 1;
    return list;
  }
  getPlayers() { return this.entities.filter((e) => e.typeId === "minecraft:player" && e.alive); }
  spawnEntity(type, loc) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error("bad spawn loc");
    G.__log.spawned.add(type);
    const hp = type === "astro:hologram_target" ? 200 : type === "astro:dmg_text" ? 0 : 20;
    const e = new FakeEntity(this, type, loc, hp);
    G.__handlers.entitySpawn?.({ entity: e, cause: "Spawned" });
    return e;
  }
  spawnItem(item, loc) {
    if (!(item instanceof ItemStack)) throw new Error("spawnItem: not an ItemStack");
    const e = new FakeEntity(this, "minecraft:item", loc, 0);
    e.item = item.clone();
    G.__handlers.entitySpawn?.({ entity: e, cause: "Spawned" });
    return e;
  }
  getBlock(loc) {
    let solid = loc.y < 64;
    for (const h of G.__holes) {
      if (loc.x >= h.x0 && loc.x < h.x1 && loc.z >= h.z0 && loc.z < h.z1) solid = false;
    }
    for (const w of G.__walls) {
      if (loc.x >= w.x0 && loc.x < w.x1 && loc.y >= w.y0 && loc.y < w.y1 && loc.z >= w.z0 && loc.z < w.z1) solid = true;
    }
    return { typeId: solid ? "minecraft:stone" : "minecraft:air", isAir: !solid, isLiquid: false,
             location: { x: Math.floor(loc.x), y: Math.floor(loc.y), z: Math.floor(loc.z) } };
  }
  runCommand(c) { G.__log.cmds.push(c); return { successCount: 1 }; }
}

const overworld = new FakeDimension("minecraft:overworld");
G.__dim = overworld;
G.__dims = [overworld];
export const world = {
  afterEvents: after, beforeEvents: before,
  getAllPlayers() { return overworld.entities.filter((e) => e.typeId === "minecraft:player" && e.alive); },
  getPlayers() { return this.getAllPlayers(); },
  getDimension() { return overworld; },
  getEntity(id) { return overworld.entities.find((e) => e.id === id && e.alive); },
  sendMessage() { },
  getDynamicProperty() { return undefined; }, setDynamicProperty() { },
};
export default {};
"""

UI = r"""
const G = globalThis;
class Form {
  constructor() { this._title = ""; this._buttons = []; this._icons = []; this._controls = []; this._kind = this.constructor.name; }
  title(t) { this._title = String(t); return this; }
  body(b) { this._body = String(b); return this; }
  button(t, icon) { this._buttons.push(String(t)); if (icon !== undefined) { if (typeof icon !== "string") throw new Error("icon"); this._icons.push(icon); G.__log.icons.add(icon); } return this; }
  button1(t) { this._buttons.push(String(t)); return this; }
  button2(t) { this._buttons.push(String(t)); return this; }
  toggle(label, def) { if (def !== undefined && typeof def !== "boolean") throw new Error("toggle default"); this._controls.push(["toggle", label, def]); return this; }
  dropdown(label, opts, def) { if (!Array.isArray(opts)) throw new Error("dropdown options"); if (def !== undefined && !Number.isInteger(def)) throw new Error("dropdown default"); this._controls.push(["dropdown", label, opts, def]); return this; }
  slider(label, a, b, step, def) { if (!Number.isFinite(step)) throw new Error("slider step"); this._controls.push(["slider", label, a, b, step, def]); return this; }
  textField(label, ph, def) { this._controls.push(["text", label, def]); return this; }
  submitButton() { return this; }
  show(player) {
    G.__log.forms.push({ kind: this._kind, title: this._title, buttons: this._buttons, controls: this._controls.length, body: this._body ?? "" });
    const a = G.__formAnswers.shift();
    if (a === "reject") return Promise.reject(new Error("FormRejectError"));
    return Promise.resolve(a ?? { canceled: true, cancelationReason: "UserClosed" });
  }
}
export class ActionFormData extends Form { }
export class ModalFormData extends Form { }
export class MessageFormData extends Form { }
export const FormCancelationReason = { UserBusy: "UserBusy", UserClosed: "UserClosed" };
export default {};
"""

# ---------------------------------------------------------------------------
#  テスト本体（Node）
# ---------------------------------------------------------------------------
TEST = r"""
import { FakeEntity, ItemStack, system } from "@minecraft/server";
import { PLANETS, PLANET_KEYS, COMMON, TRANSFORM } from "./data.js";
import * as ST from "./state.js";
import { MOVES } from "./engine.js";
import { command } from "./main.js";
import { restoreOnJoin, CLOAK_TICKS } from "./transform.js";
import { comboStep, MIN_GAP } from "./combo.js";
import { TUNE } from "./mobility.js";
import * as CB from "./combat.js";
import * as EG from "./engine.js";

const G = globalThis;
const H = G.__handlers;
const ONLY = process.env.ASTRO_PLANET || "";
let failures = 0, checks = 0;
const fail = (m) => { failures++; console.log("  FAIL " + m); };
const ok = (cond, m) => { checks++; if (!cond) fail(m); return !!cond; };
console.warn = (...a) => { const s = a.map(String).join(" "); if (!/\[astro\].*(起動|loaded)/.test(s)) G.__log.warns.push(s); };
process.on("unhandledRejection", (e) => { fail("unhandled rejection: " + (e?.stack ?? e)); });
const flushWarns = (where) => {
  if (G.__log.warns.length) { fail(`${where}: warnings: ${G.__log.warns.join(" / ").slice(0, 900)}`); G.__log.warns.length = 0; }
};
const tick = (n = 1) => G.__advance(n);
const settle = async (n = 1) => { for (let i = 0; i < n; i++) { tick(1); await Promise.resolve(); await Promise.resolve(); } };

const D = G.__dim;
function clearMobs() { for (const e of [...D.entities]) if (e.typeId !== "minecraft:player") e.remove(); }
function clearAll() { for (const e of [...D.entities]) e.remove(); }

function armorUp(p) {
  p.equip.Head = new ItemStack("minecraft:iron_helmet");
  p.equip.Chest = new ItemStack("minecraft:iron_chestplate");
  p.equip.Legs = new ItemStack("minecraft:iron_leggings");
  p.equip.Feet = new ItemStack("minecraft:iron_boots");
}
function newPlayer() {
  const p = new FakeEntity(D, "minecraft:player", { x: 0, y: 64, z: 0 }, 20);
  armorUp(p);
  H.playerSpawn({ player: p, initialSpawn: true });
  tick(45);
  return p;
}
function count(p, id) {
  let n = p.inv.slots.filter((x) => x?.typeId === id).length;
  for (const k of Object.keys(p.equip)) if (p.equip[k]?.typeId === id) n++;
  return n;
}
function dropped(id) { return D.entities.filter((e) => e.typeId === "minecraft:item" && e.alive && e.item?.typeId === id).length; }
function use(p, slot = p.selectedSlotIndex) {
  const it = p.inv.getItem(slot);
  if (!it) { fail("use(): empty slot"); return; }
  tick(5);   // itemUse の二重発火よけ（4 tick）を越える
  H.itemUse({ source: p, itemStack: it });
}
function foes(n = 3, hp = 200, type = "minecraft:zombie") {
  const out = [];
  for (let i = 0; i < n; i++) out.push(new FakeEntity(D, type, { x: (i - 1) * 1.2, y: 64, z: 2.2 + i * 0.4 }, hp));
  return out;
}
const hpSum = (list) => list.reduce((a, e) => a + Math.max(0, e.hp), 0);
/** スーツの透明化（粒なし）が掛かっているか。 */
const invisible = (p) => { const e = p.getEffect("invisibility"); return !!e && e.particles === false; };
function ground(p) { p.location.y = 64; p.vel = { x: 0, y: 0, z: 0 }; p.isOnGround = true; }
function reset(p) {
  ST.clearCds(p); ST.clearBusy(p); ST.setOverheat(p, 0); ST.setEnergy(p, ST.maxEnergy(p));
  p.isSneaking = false; p.isSprinting = false; p.isJumping = false;
  p.location = { x: 0, y: 64, z: 0 }; p.vel = { x: 0, y: 0, z: 0 }; p.isOnGround = true; p.hp = p.maxHp;
  p.effects.clear();
}
function transformWith(p, key) {
  const pl = PLANETS[key];
  reset(p);
  const slot = p.inv.slots.findIndex((x) => x?.typeId === pl.core);
  if (slot < 0) p.inv.setItem(0, new ItemStack(pl.core));
  p.selectedSlotIndex = slot < 0 ? 0 : slot;
  use(p);
  tick(TRANSFORM.freeze + 8);
  return ST.isReady(p);
}

// ---------------------------------------------------------------------------
async function testPlanet(key) {
  const pl = PLANETS[key];
  const tag = key.padEnd(8);
  clearAll();
  const p = newPlayer();
  G.__log.warns.length = 0;
  // ---- 変身 --------------------------------------------------------------
  reset(p);
  p.inv.setItem(3, new ItemStack(pl.core));
  p.selectedSlotIndex = 3;
  use(p);
  ok(ST.inSequence(p), `${key}: sequence did not start`);
  ok(p.inputPermissions.movementEnabled === false, `${key}: movement not locked during the sequence`);
  ok(p.equip.Head === undefined && count(p, "minecraft:iron_helmet") === 1, `${key}: armor not stashed`);
  ok(p.inv.getItem(3)?.lockMode === "slot", `${key}: core not locked during the sequence`);
  tick(TRANSFORM.suit_equip - 2);
  ok(!p.getEffect("invisibility"), `${key}: invisible before the suit was placed`);
  tick(3);
  ok(p.equip.Head?.typeId === (pl.suitOn ?? pl.suit), `${key}: suit_on not placed at suit_equip (head=${p.equip.Head?.typeId})`);
  ok(invisible(p), `${key}: not invisible (no particles) once the suit is placed`);
  ok(p.camState === "set", `${key}: cinematic camera not set`);
  tick(TRANSFORM.weapon_form - TRANSFORM.suit_equip);
  ok(p.inv.getItem(3)?.typeId === pl.weaponId, `${key}: weapon not formed in the core's slot`);
  tick(TRANSFORM.freeze - TRANSFORM.weapon_form + 4);
  ok(ST.isReady(p), `${key}: not ready after the sequence`);
  const head = p.equip.Head;
  ok(head?.typeId === pl.suit && head.lockMode === "slot" && head.keepOnDeath === true, `${key}: steady suit wrong (${head?.typeId} ${head?.lockMode} ${head?.keepOnDeath})`);
  const w = p.inv.getItem(3);
  ok(w?.typeId === pl.weaponId && w.lockMode === "inventory" && w.keepOnDeath === true, `${key}: weapon lock wrong`);
  ok(count(p, pl.core) === 0, `${key}: core still present after weapon_form`);
  ok(p.inputPermissions.movementEnabled === true, `${key}: movement not restored`);
  ok(p.camState === "clear", `${key}: camera not cleared`);
  ok(invisible(p), `${key}: not invisible after the sequence`);
  ok(String(p.title).length > 0, `${key}: no cut-in title`);
  for (const s of ["astro.core_on", "astro.swarm", "astro.assemble_click", "astro.armor_lock", "astro.visor_on", "astro.transform_burst", "astro.weapon_form"]) {
    ok(G.__log.sounds.get(s) > 0, `${key}: transform sound ${s} not played`);
  }
  tick(4);
  ok(String(p.actionbar).includes(pl.form_ja), `${key}: HUD does not show the form`);
  if (key === (ONLY || "earth")) console.log("  HUD sample: " + JSON.stringify(p.actionbar).replace(/[\uE000-\uF8FF]/g, (c) => "<" + c.charCodeAt(0).toString(16).toUpperCase() + ">"));
  flushWarns(`${key}.transform`);

  // ---- 4 技 --------------------------------------------------------------
  const noDmg = new Set(MOVES[key]?.meta?.noDamage ?? []);
  const dealt = {};
  for (const kind of ["skill", "dash", "air", "ult"]) {
    clearMobs();
    reset(p);
    p.selectedSlotIndex = 3;
    const list = foes(3);
    const before = hpSum(list);
    const e0 = ST.energy(p);
    if (kind === "ult") { ST.setNovaRaw(p, COMMON.nova_max); p.isSneaking = true; }
    if (kind === "dash") p.isSprinting = true;
    if (kind === "air") { p.location.y = 67; p.isOnGround = false; }
    use(p);
    p.isSneaking = false; p.isSprinting = false;
    for (let t = 0; t < 150; t++) { tick(1); await Promise.resolve(); }
    dealt[kind] = before - hpSum(list);
    const need = kind === "skill" || kind === "ult" || !noDmg.has(kind);
    if (need) ok(dealt[kind] > 0, `${key}.${kind}: no damage dealt`);
    if (kind === "ult") ok(ST.nova(p) < COMMON.nova_max, `${key}.ult: nova not consumed`);
    const cost = pl.moves[kind].cost ?? 0;
    if (cost) ok(ST.energy(p) <= e0 - cost + 0.01, `${key}.${kind}: energy cost not spent`);
    ok(ST.cdLeft(p, key, kind) > 0 || pl.moves[kind].cd < 150, `${key}.${kind}: cooldown not set`);
    ok(ST.isReady(p), `${key}.${kind}: no longer transformed after the move`);
    flushWarns(`${key}.${kind}`);
  }
  ok(invisible(p) && p.getEffect("invisibility").duration <= CLOAK_TICKS, `${key}: invisibility not kept up while transformed`);
  console.log(`  ${tag} skill ${dealt.skill.toFixed(1).padStart(6)}  dash ${dealt.dash.toFixed(1).padStart(6)}  air ${dealt.air.toFixed(1).padStart(6)}  ult ${dealt.ult.toFixed(1).padStart(6)}`);

  // ---- 三段コンボ --------------------------------------------------------
  {
    clearMobs(); reset(p); p.selectedSlotIndex = 3;
    const [foe] = foes(1);
    const impl = MOVES[key];
    let called = 0;
    const orig = impl.combo3;
    impl.combo3 = (ctx, tgt) => { called++; ok(ctx.kind === "combo3" && tgt === foe, `${key}: combo3 ctx`); return orig?.(ctx, tgt); };
    const n0 = ST.nova(p);
    for (let i = 0; i < 3; i++) { H.entityHitEntity({ damagingEntity: p, hitEntity: foe }); if (i < 2) ok(comboStep(p) === i + 1, `${key}: combo step ${i + 1}`); tick(8); }
    impl.combo3 = orig;
    ok(called === 1, `${key}: combo3 called ${called} times`);
    ok(ST.nova(p) > n0, `${key}: combo did not add nova`);
    tick(40);
    flushWarns(`${key}.combo`);
  }

  // ---- バリア ------------------------------------------------------------
  {
    clearMobs(); reset(p); p.selectedSlotIndex = 3;
    ST.setNovaRaw(p, 10);
    p.isSneaking = true;
    const s0 = G.__log.sounds.get("astro.barrier") ?? 0;
    use(p);
    p.isSneaking = false;
    ok((G.__log.sounds.get("astro.barrier") ?? 0) > s0, `${key}: barrier did not start`);
    ok(p.getEffect("resistance")?.amplifier >= 4, `${key}: barrier gives no resistance`);
    const [foe] = foes(1, 20);
    const h0 = G.__log.sounds.get("astro.barrier_hit") ?? 0;
    H.entityHitEntity({ damagingEntity: foe, hitEntity: p });
    ok((G.__log.sounds.get("astro.barrier_hit") ?? 0) > h0, `${key}: barrier hit not reacted`);
    // 飛び道具が当たった（projectileHitEntity）
    const h1 = G.__log.sounds.get("astro.barrier_hit") ?? 0;
    H.projectileHitEntity?.({ getEntityHit: () => ({ entity: p }), source: foe, projectile: undefined });
    ok((G.__log.sounds.get("astro.barrier_hit") ?? 0) > h1, `${key}: barrier ignored a projectile hit`);
    // 飛び道具の反射
    const arrow = new FakeEntity(D, "minecraft:arrow", { x: 0.5, y: 65, z: 1.2 }, 0);
    let shot = null;
    arrow.projectile = { owner: foe, shoot(v) { shot = v; } };
    tick(2);
    ok(shot && shot.z > 0 && arrow.projectile.owner === p, `${key}: barrier did not reflect a projectile`);
    tick(COMMON.barrier_ticks + 4);
    const res = p.getEffect("resistance");
    ok(!res || res.amplifier < 4 || res.duration < 2, `${key}: barrier resistance lingers`);
    flushWarns(`${key}.barrier`);
  }

  // ---- 機動 --------------------------------------------------------------
  {
    clearMobs(); reset(p);
    const sj = G.__log.sounds.get("astro.jump") ?? 0;
    p.location.y = 66; p.isOnGround = false; p.vel.y = 0.2; tick(6);
    p.isJumping = true; tick(1); p.isJumping = false; tick(1);
    ok((G.__log.sounds.get("astro.jump") ?? 0) > sj, `${key}: thruster double jump did not trigger`);
    // ホバー
    const e0 = ST.energy(p);
    p.location.y = 67; p.isOnGround = false; tick(2);
    p.isJumping = true; tick(20);
    ok(p.getEffect("levitation") || p.getEffect("slow_falling"), `${key}: hover gives no levitation/slow_falling`);
    ok(ST.energy(p) < e0, `${key}: hover did not cost energy`);
    p.isJumping = false; tick(4);
    ok(p.getEffect("slow_falling") && !p.getEffect("levitation"), `${key}: hover release should glide`);
    // ホバー中のスニークは降りるだけ（同じ押しでブースト・ダッシュを出さない）
    const sb = G.__log.sounds.get("astro.boost") ?? 0;
    p.location.y = 68; p.isOnGround = false; tick(4);
    p.isSneaking = true; tick(1); p.isSneaking = false; tick(TUNE.boostWait + 2);
    ok((G.__log.sounds.get("astro.boost") ?? 0) === sb, `${key}: sneaking to leave the hover also fired a boost dash`);
    ok(!p.getEffect("levitation") && (!p.getEffect("slow_falling") || key === "saturn"), `${key}: sneak while hovering should drop`);
    // ブースト（ホバーしていない空中でスニーク）
    p.location.y = 68; p.vel.y = 0; p.isOnGround = false; tick(4);
    p.isSneaking = true; tick(1); p.isSneaking = false; tick(TUNE.boostWait + 1);
    ok((G.__log.sounds.get("astro.boost") ?? 0) > sb, `${key}: boost dash did not trigger`);
    // 空中でスニーク＋右クリック（バリア）はブーストにしない
    tick(2);
    p.location.y = 69; p.vel.y = 0; p.isOnGround = false; tick(4);
    const sb2 = G.__log.sounds.get("astro.boost") ?? 0, br2 = G.__log.sounds.get("astro.barrier") ?? 0;
    ST.setNovaRaw(p, 10); p.selectedSlotIndex = 3; ST.S(p).barrierCd = -1;
    p.isSneaking = true; tick(1); H.itemUse({ source: p, itemStack: p.inv.getItem(3) }); tick(1); p.isSneaking = false;
    tick(TUNE.boostWait + 2);
    ok((G.__log.sounds.get("astro.barrier") ?? 0) > br2, `${key}: air sneak+use did not raise the barrier`);
    ok((G.__log.sounds.get("astro.boost") ?? 0) === sb2, `${key}: air sneak+use (barrier) also fired a boost dash`);
    // はしご・飛行中はスラスターを使わない
    p.location.y = 68; p.vel.y = 0; p.isOnGround = false; p.isClimbing = true; tick(3);
    const sj2 = G.__log.sounds.get("astro.jump") ?? 0;
    p.isJumping = true; tick(14);
    ok(!p.getEffect("levitation") && (G.__log.sounds.get("astro.jump") ?? 0) === sj2, `${key}: hover/air jump fired while climbing a ladder`);
    p.isJumping = false; p.isClimbing = false; p.isFlying = true; tick(2);
    p.isJumping = true; tick(1); p.isJumping = false; tick(1);
    ok((G.__log.sounds.get("astro.jump") ?? 0) === sj2, `${key}: air jump fired during creative flight`);
    p.isFlying = false;
    // 高いホバーからスニークで降りる → 着地の瞬間は無敵（落下死しない）
    ground(p); tick(3);
    p.location.y = 92; p.vel.y = 0; p.isOnGround = false; tick(5);
    p.isJumping = true; tick(12); p.isJumping = false; tick(2);
    p.isSneaking = true; tick(1); p.isSneaking = false;
    // （土星はパッシブの低速落下でゆっくり降りる = 落下ダメージが無いので、それも保険とみなす）
    let guarded = null;
    for (let i = 0; i < 900 && !p.isOnGround; i++) {
      tick(1);
      if (p.isOnGround) guarded = (p.getEffect("resistance")?.amplifier ?? -1) >= 4 || !!p.getEffect("slow_falling");
    }
    ok(p.isOnGround, `${key}: player never landed`);
    ok(guarded === true, `${key}: a long drop after the hover lands without the fall guard (resistance V)`);
    // 落下ダメージの打ち消し
    p.hp = 20;
    H.entityHurt({ hurtEntity: p, damage: 6, damageSource: { cause: "fall" } });
    ok(p.hp === 20, `${key}: fall damage after mobility not cancelled`);
    tick(10);
    // 回避ステップ → ジャスト回避
    const ss = G.__log.sounds.get("astro.step") ?? 0;
    p.isSneaking = true; tick(1); p.isSneaking = false; tick(2); p.isSneaking = true; tick(1); p.isSneaking = false;
    ok((G.__log.sounds.get("astro.step") ?? 0) > ss, `${key}: dodge step did not trigger`);
    const n0 = ST.nova(p);
    const [foe] = foes(1, 20);
    H.entityHitEntity({ damagingEntity: foe, hitEntity: p });
    ok(ST.nova(p) >= n0 + COMMON.nova_on_just_dodge - 0.01 || ST.nova(p) >= COMMON.nova_max, `${key}: just dodge gave no nova`);
    ok(foe.getEffect("slowness"), `${key}: just dodge did not slow enemies`);
    ok(/JUST/.test(p.subtitle + p.title), `${key}: just dodge title missing`);
    // 疾走
    p.isSprinting = true; tick(4); p.isSprinting = false;
    if (pl.mobility.sprint >= 0) ok(p.getEffect("speed"), `${key}: sprint boost missing`);
    tick(20);
    flushWarns(`${key}.mobility`);
  }

  // ---- スニーク静止で解除 ------------------------------------------------
  {
    clearMobs(); reset(p);
    tick(21);   // 透明化を掛け直させる（reset で効果を消したため）
    // プレイヤーが自分で飲んだ長い薬（解除で消してはいけない）
    p.addEffect("night_vision", 9600, { amplifier: 0 });
    p.addEffect("fire_resistance", 9600, { amplifier: 0 });
    p.addEffect("resistance", 2400, { amplifier: 0 });
    p.isSneaking = true;
    tick(COMMON.revert_hold_ticks - 10);
    ok(/変身解除/.test(p.actionbar), `${key}: revert progress not on HUD`);
    tick(12);
    p.isSneaking = false;
    ok(!ST.formOf(p), `${key}: crouch-still did not revert`);
    ok(p.equip.Head?.typeId === pl.suitOff, `${key}: suit_off not shown during revert`);
    ok(invisible(p), `${key}: not invisible during the release animation`);
    tick(25);
    ok(!p.getEffect("invisibility") && p.getDynamicProperty(ST.PROP.invis) !== true, `${key}: invisibility left after the release animation`);
    for (const id of ["night_vision", "fire_resistance", "resistance"]) ok((p.getEffect(id)?.duration ?? 0) > 2000, `${key}: revert stripped the player's own ${id} potion`);
    ok(p.equip.Head?.typeId === "minecraft:iron_helmet" && p.equip.Chest?.typeId === "minecraft:iron_chestplate" &&
       p.equip.Legs?.typeId === "minecraft:iron_leggings" && p.equip.Feet?.typeId === "minecraft:iron_boots", `${key}: armor not restored after revert`);
    ok(count(p, pl.core) === 1 && count(p, pl.weaponId) === 0, `${key}: weapon->core after revert (cores ${count(p, pl.core)}, weapons ${count(p, pl.weaponId)})`);
    ok(p.inv.getItem(3)?.typeId === pl.core && p.inv.getItem(3)?.lockMode === "none", `${key}: core not back in the weapon's slot / still locked`);
    ok(p.camState === "clear" && p.inputPermissions.movementEnabled, `${key}: camera/input after revert`);
    flushWarns(`${key}.revert`);
  }

  // ---- 星力切れ → オーバーヒート ------------------------------------------
  {
    ok(transformWith(p, key), `${key}: re-transform failed`);
    ST.setEnergy(p, 0.2);
    tick(25);
    ok(!ST.formOf(p) && ST.overheat(p) > 0, `${key}: depletion did not revert with overheat`);
    ok(p.getEffect("weakness"), `${key}: overheat gives no weakness`);
    ok((G.__log.sounds.get("astro.overheat") ?? 0) > 0, `${key}: astro.overheat not played`);
    tick(25);
    ok(!p.getEffect("invisibility"), `${key}: invisibility left after the depleted revert`);
    ST.setEnergy(p, 100);
    p.selectedSlotIndex = p.inv.slots.findIndex((x) => x?.typeId === pl.core);
    use(p);
    ok(!ST.inSequence(p) && !ST.formOf(p), `${key}: transformed while overheated`);
    ST.setOverheat(p, 0);
    tick(5);
    flushWarns(`${key}.overheat`);
  }

  // ---- 変身中の死亡 → リスポーン ------------------------------------------
  {
    ok(transformWith(p, key), `${key}: transform before death failed`);
    const killer = foes(1, 20)[0];
    p.hp = 0;
    for (let i = 0; i < p.inv.size; i++) { const it = p.inv.slots[i]; if (it && !it.keepOnDeath) { D.spawnItem(it, p.location); p.inv.slots[i] = undefined; } }
    for (const k of Object.keys(p.equip)) { const it = p.equip[k]; if (it && !it.keepOnDeath) { D.spawnItem(it, p.location); p.equip[k] = undefined; } }
    H.entityDie({ deadEntity: p, damageSource: { cause: "entityAttack", damagingEntity: killer } });
    ok(p.camState === "clear", `${key}: camera not cleared on death`);
    tick(30);
    p.hp = p.maxHp; p.location = { x: 0, y: 64, z: 0 };
    H.playerSpawn({ player: p, initialSpawn: false });
    tick(25);
    ok(!ST.formOf(p) && !ST.isReady(p), `${key}: still transformed after respawn`);
    ok(!p.equip.Head || !p.equip.Head.typeId.startsWith("astro:suit"), `${key}: suit left after respawn`);
    ok(!p.getEffect("invisibility") && p.getDynamicProperty(ST.PROP.invis) !== true, `${key}: invisibility left after death/respawn`);
    ok(count(p, pl.core) + dropped(pl.core) === 1, `${key}: core count after death = ${count(p, pl.core)} + dropped ${dropped(pl.core)}`);
    ok(count(p, pl.weaponId) === 0 && dropped(pl.weaponId) === 0, `${key}: weapon left after death`);
    ok(p.inputPermissions.movementEnabled && p.camState === "clear", `${key}: input/camera after respawn`);
    // 落ちた防具を拾い直す（次の検査のため）
    for (const e of [...D.entities]) if (e.typeId === "minecraft:item") { p.inv.addItem(e.item); e.remove(); }
    for (const id of ["minecraft:iron_helmet", "minecraft:iron_chestplate", "minecraft:iron_leggings", "minecraft:iron_boots"]) {
      const i = p.inv.slots.findIndex((x) => x?.typeId === id); if (i >= 0) p.inv.slots[i] = undefined;
    }
    armorUp(p);
    flushWarns(`${key}.death`);
  }

  // ---- 演出中の死亡 ------------------------------------------------------
  {
    reset(p);
    let slot = p.inv.slots.findIndex((x) => x?.typeId === pl.core);
    p.selectedSlotIndex = slot;
    use(p);
    tick(20);
    p.hp = 0;
    H.entityDie({ deadEntity: p, damageSource: { cause: "entityAttack" } });
    tick(10);
    p.hp = p.maxHp;
    H.playerSpawn({ player: p, initialSpawn: false });
    tick(25);
    ok(!ST.formOf(p) && !ST.inSequence(p), `${key}: transformed after dying mid-sequence`);
    ok(count(p, pl.core) === 1 && count(p, pl.weaponId) === 0, `${key}: core/weapon after dying mid-sequence`);
    ok(p.inputPermissions.movementEnabled && p.camState === "clear", `${key}: frozen/camera after dying mid-sequence`);
    ok(p.equip.Head?.typeId === "minecraft:iron_helmet", `${key}: armor not restored after dying mid-sequence`);
    ok(!p.getEffect("invisibility"), `${key}: invisibility left after dying mid-sequence`);
    flushWarns(`${key}.death_seq`);
  }

  // ---- 再参加 ------------------------------------------------------------
  let q = p;
  const relog = (who) => {
    H.before_playerLeave?.({ player: who });
    H.playerLeave({ playerId: who.id, playerName: who.name });
    who.remove();
    const n = new FakeEntity(D, "minecraft:player", who.location, 20, who.id);
    n.props = new Map(who.props); n.inv = who.inv; n.equip = who.equip; n.camState = who.camState;
    n.inputPermissions = { ...who.inputPermissions };
    n.selectedSlotIndex = who.selectedSlotIndex;
    n.effects = new Map(who.effects);   // 効果は退出をまたいで残る
    H.playerSpawn({ player: n, initialSpawn: true });
    tick(2);
    return n;
  };
  {
    ok(transformWith(q, key), `${key}: transform before relog failed`);
    tick(30);
    q = relog(q);
    ok(ST.isReady(q) && ST.formOf(q) === key, `${key}: transformation not restored after relog`);
    tick(8);
    ok(invisible(q), `${key}: not invisible after relog with the suit on`);
    ok(String(q.actionbar).includes(pl.form_ja), `${key}: HUD after relog`);
    command(q, "astro:revert", "");
    tick(25);
    ok(!ST.formOf(q) && q.equip.Head?.typeId === "minecraft:iron_helmet" && count(q, pl.core) === 1, `${key}: revert after relog`);
    ok(!q.getEffect("invisibility"), `${key}: invisibility left after revert (relogged)`);
    // 演出の途中で抜ける
    q.selectedSlotIndex = q.inv.slots.findIndex((x) => x?.typeId === pl.core);
    reset(q);
    use(q);
    tick(TRANSFORM.weapon_form - 5);
    q = relog(q);
    tick(5);
    ok(!ST.formOf(q) && !ST.inSequence(q), `${key}: mid-sequence relog left a transformation`);
    ok(q.inputPermissions.movementEnabled && q.camState === "clear", `${key}: mid-sequence relog left camera/input locked`);
    ok(count(q, pl.core) === 1 && count(q, pl.weaponId) === 0 && !String(q.equip.Head?.typeId).startsWith("astro:"), `${key}: mid-sequence relog items`);
    ok(q.inv.slots.every((x) => !x || x.lockMode === "none"), `${key}: an item stayed locked after mid-sequence relog`);
    ok(q.equip.Head?.typeId === "minecraft:iron_helmet", `${key}: armor after mid-sequence relog`);
    ok(!q.getEffect("invisibility") && q.getDynamicProperty(ST.PROP.invis) !== true, `${key}: invisibility left after mid-sequence relog`);
    flushWarns(`${key}.relog`);
  }
  q.remove();
}

// ---------------------------------------------------------------------------
async function testCommon() {
  clearAll();
  G.__log.warns.length = 0;
  // ---- 初参加: ターミナルは 1 回だけ ---------------------------------------
  const p = newPlayer();
  ok(count(p, "astro:terminal") === 1, "first join: terminal not given");
  H.playerLeave({ playerId: p.id, playerName: p.name });
  H.playerSpawn({ player: p, initialSpawn: true });
  tick(45);
  ok(count(p, "astro:terminal") === 1, "terminal given twice");
  // ---- コマンド ----------------------------------------------------------
  ok(G.__seOpts?.namespaces?.includes("astro"), "scriptEventReceive not filtered to the astro namespace");
  H.scriptEventReceive({ id: "astro:kit", message: "", sourceEntity: p });
  ok(PLANET_KEYS.every((k) => count(p, PLANETS[k].core) >= 1), "astro:kit did not give all cores");
  ST.setEnergy(p, 3);
  H.scriptEventReceive({ id: "astro:energy", message: "", sourceEntity: p });
  ok(ST.energy(p) >= COMMON.energy_max, "astro:energy");
  H.scriptEventReceive({ id: "astro:nova", message: "", sourceEntity: p });
  ok(ST.nova(p) >= COMMON.nova_max, "astro:nova");
  p.selectedSlotIndex = p.inv.slots.findIndex((x) => x?.typeId === PLANETS.mars.core);
  H.scriptEventReceive({ id: "astro:sync", message: "", sourceEntity: p });
  ok(ST.level(p, "mars") === 5, "astro:sync did not set Lv5");
  // コア無しで変身 → 解除でコアを作らない
  const cores0 = count(p, PLANETS.venus.core);
  H.scriptEventReceive({ id: "astro:transform", message: "venus", sourceEntity: p });
  tick(TRANSFORM.freeze + 6);
  ok(ST.isReady(p) && ST.formOf(p) === "venus", "astro:transform venus");
  ok(count(p, PLANETS.venus.weaponId) === 1, "coreless transform: no weapon");
  H.scriptEventReceive({ id: "astro:revert", message: "", sourceEntity: p });
  tick(25);
  ok(!ST.formOf(p) && count(p, PLANETS.venus.core) === cores0 && count(p, PLANETS.venus.weaponId) === 0, "coreless revert created/left items");
  // ---- ホログラム標的 ------------------------------------------------------
  H.scriptEventReceive({ id: "astro:target", message: "", sourceEntity: p });
  const tgt = D.entities.find((e) => e.typeId === "astro:hologram_target");
  ok(tgt, "astro:target did not spawn the hologram target");
  if (tgt) {
    tgt.applyDamage(12, { damagingEntity: p });
    ok(/DPS/.test(tgt.nameTag) && tgt.hp === tgt.maxHp, "hologram target: DPS / heal");
    tick(120);
    ok(/DPS/.test(tgt.nameTag), "hologram nameTag lost");
  }
  H.scriptEventReceive({ id: "astro:boss", message: "", sourceEntity: p });
  tick(80);   // 召喚の演出（3.3 秒）の後に現れる
  ok(G.__log.spawned.has("astro:nemesis"), "astro:boss did not try to spawn nemesis");
  // ---- 落ちたウェポン・スーツの掃除 ----------------------------------------
  D.spawnItem(new ItemStack(PLANETS.earth.weaponId), { x: 3, y: 64, z: 3 });
  D.spawnItem(new ItemStack(PLANETS.earth.suit), { x: 3, y: 64, z: 3 });
  tick(3);
  ok(dropped(PLANETS.earth.weaponId) === 0 && dropped(PLANETS.earth.core) === 1 && dropped(PLANETS.earth.suit) === 0, "dropped weapon/suit not fixed");
  for (const e of [...D.entities]) if (e.typeId === "minecraft:item") e.remove();
  // 変身していないのに持っているウェポン・スーツ
  p.inv.setItem(20, new ItemStack(PLANETS.mars.weaponId));
  p.equip.Offhand = new ItemStack(PLANETS.sol.weaponId);
  tick(25);
  ok(count(p, PLANETS.mars.weaponId) === 0 && count(p, PLANETS.sol.weaponId) === 0 && p.inv.getItem(20)?.typeId === PLANETS.mars.core, "stray weapons not converted to cores");
  // ---- ターミナル --------------------------------------------------------
  const term = p.inv.slots.findIndex((x) => x?.typeId === "astro:terminal");
  p.selectedSlotIndex = term;
  G.__log.forms.length = 0;
  // 図鑑 → 地球 → 図鑑へ戻る → 閉じる
  G.__formAnswers.push({ selection: 0 }, { selection: 2 }, { selection: 0 }, { canceled: true, cancelationReason: "UserClosed" });
  use(p, term);
  await settle(6);
  ok(G.__log.forms.length >= 4, `terminal navigation (${G.__log.forms.length} forms)`);
  ok(G.__log.forms.some((f) => /ガイア/.test(f.title) && /潮汐斬/.test(f.body)), "planet page for earth missing");
  // 設定（UserBusy を一度挟む）
  G.__formAnswers.push({ canceled: true, cancelationReason: "UserBusy" }, { selection: 1 }, { formValues: [false, true, 2, false] });
  use(p, term);
  for (let i = 0; i < 40; i++) await settle(1);
  const s = ST.settings(p);
  ok(s.cam === false && s.hud === true && s.fx === 2 && s.dmg === false, `settings not saved ${JSON.stringify(s)}`);
  ok(JSON.parse(p.getDynamicProperty(ST.PROP.settings) ?? "{}").fx === 2, "settings not persisted");
  ST.setSettings(p, { cam: true, dmg: true, fx: 1 });
  // 操作説明・記録・拒否されたフォーム
  G.__formAnswers.push({ selection: 2 }, { selection: 0 }, { selection: 3 }, "reject");
  use(p, term);
  await settle(8);
  ok(G.__log.forms.some((f) => f.title === "操作説明") && G.__log.forms.some((f) => f.title === "記録"), "controls/records pages");
  // 変身中の解除ボタン
  ok(transformWith(p, "earth"), "earth transform for terminal revert");
  p.selectedSlotIndex = term;
  G.__formAnswers.push({ selection: 1 });
  use(p, term);
  await settle(4);
  ok(!ST.formOf(p), "terminal revert button did not revert");
  tick(25);
  // ---- ダメージ数字・撃破 -------------------------------------------------
  ok(transformWith(p, "earth"), "earth transform for kills");
  clearMobs();
  const weak = foes(3, 4);
  const k0 = ST.records(p).kills ?? 0;
  const xp0 = ST.xpOf(p, "earth");
  p.selectedSlotIndex = p.inv.slots.findIndex((x) => x?.typeId === PLANETS.earth.weaponId);
  use(p);
  tick(60);
  ok((ST.records(p).kills ?? 0) > k0 && ST.xpOf(p, "earth") > xp0, "kills not tracked");
  ok(G.__log.spawned.has("astro:dmg_text"), "no damage numbers spawned");
  // ルナ・ビット（パッシブ）
  clearMobs();
  const z = foes(1, 100)[0];
  // 前の技で動いたプレイヤーの位置を基準に置く（6m 以内）
  z.location = { x: p.location.x, y: p.location.y, z: p.location.z + 4 };
  const cow = new FakeEntity(D, "minecraft:cow", { x: p.location.x, y: p.location.y, z: p.location.z - 3 }, 10);
  tick(90);
  ok(z.hp < 100, `earth passive luna_bit did not zap a hostile (player at ${JSON.stringify(p.location)}, form=${ST.formOf(p)}, hp=${z.hp})`);
  ok(cow.hp === 10, "luna_bit shot a passive animal");
  ok(p.getEffect("regeneration"), "earth passive effect (regeneration) missing");
  // ---- 壁に向かうワープ・突進（ブロックに埋まらない） ------------------------
  G.__walls.push({ x0: -3, x1: 3, y0: 64, y1: 70, z0: 3, z1: 5 });
  reset(p);
  const { warp, safeAhead } = await import("./engine.js");
  warp(p, { x: 0, y: 64, z: 4 });
  const a = safeAhead(D, p.location, { x: 0, y: 0, z: 1 }, 8);
  ok(a.z < 3, `safeAhead went through a wall (${a.z})`);
  G.__walls.length = 0;
  ok(G.__log.teleportFails.length === 0, `teleported into blocks: ${G.__log.teleportFails.join(" ")}`);
  command(p, "astro:revert", "");
  tick(25);
  // ---- 起動時の後始末（/reload 相当） ---------------------------------------
  p.setDynamicProperty(ST.PROP.frozen, true); p.inputPermissions.movementEnabled = false;
  p.setDynamicProperty(ST.PROP.cam, true); p.camState = "set";
  restoreOnJoin(p);
  ok(p.inputPermissions.movementEnabled && p.camState === "clear", "startup cleanup did not restore input/camera");
  flushWarns("common");
  p.remove();
}

// ---------------------------------------------------------------------------
async function testTemplate() {
  // 雛形をそのまま（KEY だけ変えて）読み込み、全部の技が動くか
  const fs = await import("node:fs");
  const src = fs.readFileSync(new URL("./planets/_template.js", import.meta.url), "utf8")
    .replace('const KEY = "template";', 'const KEY = "venus";');
  fs.writeFileSync(new URL("./planets/__tpl_check.js", import.meta.url), src);
  await import("./planets/__tpl_check.js");
  clearAll();
  const p = newPlayer();
  G.__log.warns.length = 0;
  ok(transformWith(p, "venus"), "template: transform");
  for (const kind of ["skill", "dash", "air", "ult"]) {
    clearMobs(); reset(p);
    p.selectedSlotIndex = p.inv.slots.findIndex((x) => x?.typeId === PLANETS.venus.weaponId);
    const list = foes(3);
    const before = hpSum(list);
    if (kind === "ult") { ST.setNovaRaw(p, 100); p.isSneaking = true; }
    if (kind === "dash") p.isSprinting = true;
    if (kind === "air") { p.location.y = 67; p.isOnGround = false; }
    use(p);
    p.isSneaking = false; p.isSprinting = false;
    tick(120);
    ok(before - hpSum(list) > 0, `template.${kind}: no damage`);
  }
  flushWarns("template");
}

// ---------------------------------------------------------------------------
const keys = ONLY ? [ONLY] : PLANET_KEYS;
console.log("  planet   damage per move (3 zombies, HP 200)");
for (const key of keys) {
  try { await testPlanet(key); } catch (e) { fail(`${key}: exception ${e?.stack ?? e}`); }
}
try { await testCommon(); } catch (e) { fail(`common: exception ${e?.stack ?? e}`); }
if (!ONLY) { try { await testTemplate(); } catch (e) { fail(`template: exception ${e?.stack ?? e}`); } }

console.log("__USED__" + JSON.stringify({
  particles: [...G.__log.particles.keys()], sounds: [...G.__log.sounds.keys()],
  anims: [...G.__log.anims.keys()],
  cmdAnims: G.__log.cmds.filter((c) => c.startsWith("playanimation")).map((c) => c.split(" ")[2]),
  molang: [...G.__log.molang], items: [...G.__log.items], spawned: [...G.__log.spawned], icons: [...G.__log.icons],
  budgetMax: G.__log.budgetMax, queries: G.__log.queries ?? 0, ticks: system.currentTick,
  titleFails: G.__log.titleFails, fadeFails: G.__log.fadeFails,
}));
console.log(`  ${checks} behaviour checks, ${failures} failure(s)`);
process.exit(failures ? 1 : 0);
"""


# ---------------------------------------------------------------------------
#  参照の実在チェック
# ---------------------------------------------------------------------------
def design_lists():
    """DESIGN.md §4.7（パーティクル）・§4.9（効果音）・§4.6（共通モーション）・§4.7 の変数を読む。"""
    txt = open(DESIGN, encoding="utf-8").read()

    def section(start, end):
        a = txt.find(start)
        b = txt.find(end, a + 1)
        return txt[a:b] if a >= 0 else ""

    s47 = section("### 4.7", "### 4.8")
    particles = set()
    for line in s47.splitlines():
        if line.startswith("| `"):
            first = line.split("|")[1]
            particles.update(re.findall(r"`([a-z_]+)`", first))
    molang = set(re.findall(r"`?v\.([a-z]+)", s47))
    # パーティクルの担当が DESIGN に追記する前に足した ID（PARTICLES.md の一覧）も認める
    pm = os.path.join(HERE, "PARTICLES.md")
    if os.path.isfile(pm):
        particles.update(re.findall(r"^\| `astro:([a-z_]+)`", open(pm, encoding="utf-8").read(), re.M))
    s49 = section("### 4.9", "### 4.10")
    sounds = set()
    m = re.search(r"```\n(.*?)```", s49, re.S)
    if m:
        sounds = {f"astro.{w}" for w in m.group(1).split()}
    s46 = section("### 4.6", "### 4.7")
    shared = set()
    m = re.search(r"共通（全形態）:(.*?)。", s46, re.S)
    if m:
        shared = set(re.findall(r"`([a-z_]+)`", m.group(1)))
    return particles, sounds, molang, shared


def pack_ids(folder, key_path):
    out = set()
    if not os.path.isdir(folder):
        return None
    for base, _, files in os.walk(folder):
        for f in files:
            if not f.endswith(".json"):
                continue
            try:
                d = json.load(open(os.path.join(base, f), encoding="utf-8"))
                v = d
                for k in key_path:
                    v = v[k]
                out.add(v)
            except Exception:  # noqa: BLE001
                continue
    return out or None


def reference_checks(used):
    errs, skipped, passed = [], [], []
    d_particles, d_sounds, d_molang, d_shared = design_lists()

    # パーティクル
    ids = {p.split(":", 1)[1] if p.startswith("astro:") else p for p in used["particles"]}
    bad = sorted(i for i in ids if i not in d_particles)
    errs += [f"particle astro:{i} is not in DESIGN §4.7 / PARTICLES.md" for i in bad]
    rp_particles = pack_ids(os.path.join(RP, "particles"), ["particle_effect", "description", "identifier"])
    if rp_particles is None:
        skipped.append("particles exist in packs/astro_RP/particles: SKIPPED (resource not generated yet)")
    else:
        miss = sorted(p for p in used["particles"] if p not in rp_particles)
        errs += [f"particle {p} does not exist in packs/astro_RP/particles" for p in miss]
        passed.append(f"{len(used['particles'])} particle ids exist")
    # Molang 変数
    for v in used["molang"]:
        name = v.split(".", 1)[1]
        if name not in d_molang:
            errs.append(f"molang variable {v} is not in DESIGN §4.7")
    # 効果音
    snd = sorted(s for s in used["sounds"] if s.startswith("astro."))
    errs += [f"sound {s} is not in DESIGN §4.9" for s in snd if d_sounds and s not in d_sounds]
    sd = os.path.join(RP, "sounds", "sound_definitions.json")
    if not os.path.isfile(sd):
        skipped.append("sounds exist in sound_definitions.json: SKIPPED (resource not generated yet)")
    else:
        defs = set(json.load(open(sd, encoding="utf-8")).get("sound_definitions", {}))
        errs += [f"sound {s} does not exist in sound_definitions.json" for s in snd if s not in defs]
        passed.append(f"{len(snd)} sound ids exist")
    # 全身モーション
    anims = sorted(set(used["anims"]) | set(used["cmdAnims"]))
    errs += [f"body animation {a} is not animation.astro.p.*" for a in anims if not a.startswith("animation.astro.p.")]
    ap = os.path.join(RP, "animations", "astro_player.animation.json")
    if not os.path.isfile(ap):
        skipped.append("body animations exist in astro_player.animation.json: SKIPPED (resource not generated yet)")
    else:
        have = set(json.load(open(ap, encoding="utf-8")).get("animations", {}))
        errs += [f"body animation {a} does not exist in astro_player.animation.json" for a in anims if a not in have]
        missing_shared = sorted(n for n in d_shared if f"animation.astro.p.{n}" not in have)
        if missing_shared:
            errs.append(f"astro_player.animation.json lacks shared animations {missing_shared}")
        passed.append(f"{len(anims)} body animations exist")
    # アイテム
    items = pack_ids(os.path.join(BP, "items"), ["minecraft:item", "description", "identifier"]) or set()
    for i in sorted(used["items"]):
        if i.startswith("astro:") and i not in items:
            errs.append(f"item {i} does not exist in packs/astro_BP/items")
    passed.append(f"{len([i for i in used['items'] if i.startswith('astro:')])} item ids exist")
    # エンティティ
    ents = pack_ids(os.path.join(BP, "entities"), ["minecraft:entity", "description", "identifier"])
    sp = sorted(s for s in used["spawned"] if s.startswith("astro:"))
    if ents is None:
        skipped.append("entities exist in packs/astro_BP/entities: SKIPPED (resource not generated yet)")
    else:
        errs += [f"entity {s} does not exist in packs/astro_BP/entities" for s in sp if s not in ents]
        passed.append(f"{len(sp)} entity ids exist")
    # フォームのアイコン
    icons = sorted(used["icons"])
    if not os.path.isdir(os.path.join(RP, "textures", "ui", "astro")):
        skipped.append("form icons exist in textures/ui/astro: SKIPPED (resource not generated yet)")
    else:
        for i in icons:
            if not any(os.path.isfile(os.path.join(RP, i + ext)) for ext in (".png", ".tga")):
                errs.append(f"form icon {i} does not exist")
        passed.append(f"{len(icons)} form icons exist")
    # タイトルとフェードの引数
    errs += [f"setTitle with incomplete options: {t}" for t in used.get("titleFails", [])]
    errs += [f"camera fade shorter than 0.5 s: {t}" for t in used.get("fadeFails", [])]
    return errs, skipped, passed


def item_ids():
    ids = pack_ids(os.path.join(BP, "items"), ["minecraft:item", "description", "identifier"]) or set()
    return sorted(ids)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--planet", choices=PLANET_KEYS, help="この形態だけ試す（共通の検査も走る）")
    ap.add_argument("--keep", action="store_true", help="作業用の一時フォルダを消さない")
    args = ap.parse_args()

    # 構文の検査
    bad = []
    for base, _, files in os.walk(SCRIPTS):
        for f in files:
            if f.endswith(".js"):
                r = subprocess.run(["node", "--check", os.path.join(base, f)], capture_output=True, text=True)
                if r.returncode:
                    bad.append(f"{os.path.relpath(os.path.join(base, f), SCRIPTS)}: {r.stderr.strip()[:400]}")
    if bad:
        for b in bad:
            print("  FAIL syntax", b)
        return 1

    # 一時ファイルは ASTRO_SCRATCH（既定 build_preview/astro/、.gitignore 済み）へ（DESIGN §0）
    scratch = os.environ.get("ASTRO_SCRATCH", os.path.join(ROOT, "build_preview", "astro"))
    os.makedirs(scratch, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="test-", dir=scratch)
    try:
        with open(os.path.join(tmp, "package.json"), "w") as fh:
            json.dump({"name": "astro-test", "type": "module"}, fh)
        for mod, src in (("@minecraft/server", SERVER), ("@minecraft/server-ui", UI)):
            d = os.path.join(tmp, "node_modules", *mod.split("/"))
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.js"), "w") as fh:
                fh.write(src)
            with open(os.path.join(d, "package.json"), "w") as fh:
                json.dump({"name": mod, "type": "module", "main": "index.js"}, fh)
        work = os.path.join(tmp, "scripts")
        shutil.copytree(SCRIPTS, work)
        with open(os.path.join(work, "__test.js"), "w", encoding="utf-8") as fh:
            fh.write(TEST)
        # node_modules を scripts の親に置いたので scripts から解決できる
        env = dict(os.environ)
        env["ASTRO_ITEMS"] = json.dumps(item_ids())
        if args.planet:
            env["ASTRO_PLANET"] = args.planet
        res = subprocess.run(["node", os.path.join(work, "__test.js")], capture_output=True, text=True,
                             timeout=900, env=env, cwd=work)
        used = None
        for line in res.stdout.splitlines():
            if line.startswith("__USED__"):
                used = json.loads(line[len("__USED__"):])
            else:
                print(line)
        if res.returncode or used is None:
            print(res.stderr[-4000:])
            print("  behaviour tests FAILED")
            return 1
        errs, skipped, passed = reference_checks(used)
        print(f"  used: {len(used['particles'])} particles, {len(used['sounds'])} sounds, "
              f"{len(set(used['anims']) | set(used['cmdAnims']))} body animations, {len(used['items'])} items; "
              f"max {used['budgetMax']} spawnParticle calls in one tick; {used['ticks']} ticks simulated")
        for p in passed:
            print(f"  ok   {p}")
        for s in skipped:
            print(f"  {s}")
        for e in errs:
            print("  FAIL", e)
        print(f"  reference checks: {len(passed)} passed, {len(skipped)} skipped, {len(errs)} failed")
        return 1 if errs else 0
    finally:
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"  kept {tmp}")


if __name__ == "__main__":
    sys.exit(main())
