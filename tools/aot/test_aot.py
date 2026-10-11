# -*- coding: utf-8 -*-
"""スクリプトの挙動テスト（Minecraft 無しで実際に遊ばせる）。

@minecraft/server を「動く」スタブに差し替え、地面・塔・重力・速度のある偽の世界と、
偽のプレイヤー・巨人・兵士を用意して次を確かめる:
* 立体機動: 塔へアンカーを撃って巻き取ると近づく・ガスが減る・離すと切れる
* うなじ: 巨人に刺して巻き取り、脇を抜けると自動で斬る / 後ろから勢いよく斬る / 遅いと「浅い」
* 再生: 体を斬っても時間が経つと戻る
* 掴み: 掴まれて 2.5 秒で噛まれる / スニークで脱出する
* 雷槍: うなじの近くに刺さって爆発すると倒れる
* 調査兵団: リヴァイが近くの巨人を倒す
* 昼夜: 夜は座り込み、朝に起きる
* 刃の消耗と替え刃、ガスボンベ、装備の支給、HUD、討伐の蒸発（消える）
* スクリプトが例外を出さない・使ったパーティクル／効果音／全身モーション／翻訳キーが実在する
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import aot_common as C
from aot_lang import KEYS

SCRIPTS = os.path.join(C.BP, "scripts")

SERVER = r"""
const G = globalThis;
G.__log = { particles: new Map(), sounds: new Map(), anims: new Map(), cmds: [], warns: [],
            events: [], explosions: 0, keys: new Set() };
const timeouts = [];
const intervals = [];
export const system = {
  currentTick: 0,
  run(f) { timeouts.push({ due: this.currentTick + 1, f }); return 0; },
  runTimeout(f, t = 1) { timeouts.push({ due: this.currentTick + Math.max(1, t), f }); return 0; },
  runInterval(f, t = 1) { intervals.push({ every: Math.max(1, t), f }); return 0; },
  clearRun() { },
  afterEvents: { scriptEventReceive: { subscribe(f) { G.__handlers.scriptEventReceive = f; } } },
};
G.__handlers = {};
G.__advance = (n, physics = true) => {
  for (let i = 0; i < n; i++) {
    system.currentTick++;
    const t = system.currentTick;
    for (const iv of intervals) if (t % iv.every === 0) iv.f();
    const due = timeouts.filter((x) => x.due <= t);
    for (const x of due) timeouts.splice(timeouts.indexOf(x), 1);
    for (const x of due) x.f();
    if (physics) for (const e of [...G.__dim.entities]) e.__physics();
  }
};
const events = new Proxy({}, { get(_, name) { return { subscribe(f) { G.__handlers[name] = f; return f; }, unsubscribe() { } }; } });

function scanKeys(m) {
  if (!m || typeof m !== "object") return;
  for (const r of m.rawtext ?? []) if (r.translate) G.__log.keys.add(r.translate);
}

export class MolangVariableMap {
  constructor() { this.vars = {}; }
  setFloat(k, v) { if (!Number.isFinite(v)) throw new Error(`non-finite molang ${k}=${v}`); this.vars[k] = v; }
}
export const EquipmentSlot = { Head: "Head", Chest: "Chest", Legs: "Legs", Feet: "Feet", Mainhand: "Mainhand" };
const MAXDUR = { "aot:odm_blades": 60, "aot:flare_gun": 64 };
export class ItemStack {
  constructor(typeId, amount = 1) {
    this.typeId = typeId; this.amount = amount;
    if (MAXDUR[typeId]) this.__dur = { damage: 0, maxDurability: MAXDUR[typeId] };
  }
  getComponent(n) { return n === "minecraft:durability" ? this.__dur : undefined; }
}

class Container {
  constructor(size) { this.size = size; this.slots = new Array(size).fill(undefined); }
  getItem(i) { return this.slots[i]; }
  setItem(i, it) { this.slots[i] = it; }
  addItem(it) {
    for (let i = 0; i < this.size; i++) {
      const s = this.slots[i];
      if (s && s.typeId === it.typeId && !s.__dur) { s.amount += it.amount; return undefined; }
    }
    const i = this.slots.findIndex((s) => !s);
    if (i < 0) return it;
    this.slots[i] = it;
    return undefined;
  }
}

const STATE_OF = { "aot:sleep": "sleep", "aot:wake": "idle", "aot:blind": "blind", "aot:unblind": "idle",
                   "aot:die": "dying" };
let nextId = 1;
export class FakeEntity {
  constructor(dim, typeId, loc, hp = 20, families = []) {
    this.id = String(nextId++);
    this.typeId = typeId;
    this.dimension = dim;
    this.location = { ...loc };
    this.vel = { x: 0, y: 0, z: 0 };
    this.view = { x: 0, y: 0, z: 1 };
    this.yaw = 0;
    this.hp = hp; this.maxHp = hp;
    this.alive = true;
    this.families = families;
    this.isSneaking = false; this.isSprinting = false; this.isOnGround = true; this.isJumping = false;
    this.lastHurt = -99;
    this.props = new Map();
    this.effects = [];
    this.name = "Tester";
    this.state = "idle";
    this.variant = 0;
    this.speed = 0.25; this.speed0 = 0.25;
    this.inv = new Container(36);
    this.equip = {};
    this.selectedSlotIndex = 0;
    this.gameMode = "survival";
    this.onScreenDisplay = {
      setActionBar: (m) => { scanKeys(m); this.actionbar = m; },
      setTitle: (t, o) => { scanKeys(t); scanKeys(o?.subtitle); this.title = t; this.subtitle = o?.subtitle; },
    };
    dim.entities.push(this);
  }
  get isValid() { return this.alive; }
  getComponent(name) {
    const e = this;
    if (name === "minecraft:health") {
      return { get currentValue() { return e.hp; }, get effectiveMax() { return e.maxHp; },
               setCurrentValue(v) { if (!Number.isFinite(v)) throw new Error("bad hp"); e.hp = Math.max(0, Math.min(e.maxHp, v)); return true; } };
    }
    if (name === "minecraft:equippable") {
      return { getEquipment(slot) { return slot === "Mainhand" ? e.inv.getItem(e.selectedSlotIndex) : e.equip[slot]; },
               setEquipment(slot, it) { e.equip[slot] = it; } };
    }
    if (name === "minecraft:inventory") return { container: this.inv };
    if (name === "minecraft:variant") return { value: this.variant };
    if (name === "minecraft:movement") {
      return { setCurrentValue(v) { e.speed = v; }, resetToDefaultValue() { e.speed = e.speed0; } };
    }
    return undefined;
  }
  getProperty(k) { return k === "aot:state" ? this.state : undefined; }
  triggerEvent(id) {
    G.__log.events.push(`${this.typeId}:${id}`);
    if (STATE_OF[id]) this.state = STATE_OF[id];
    const m = /^aot:st_(.+)$/.exec(id);
    if (m) this.state = m[1];
  }
  applyDamage(amount, opts) {
    if (!Number.isFinite(amount)) throw new Error("bad damage " + amount);
    if (this.state === "dying") return false;
    this.hp -= amount;
    G.__handlers.entityHurt?.({ hurtEntity: this, damage: amount,
      damageSource: { cause: opts?.cause ?? "entityAttack", damagingEntity: opts?.damagingEntity } });
    if (this.hp <= 0 && this.alive) {
      G.__handlers.entityDie?.({ deadEntity: this, damageSource: { damagingEntity: opts?.damagingEntity } });
      if (this.typeId !== "minecraft:player") this.remove();
    }
    return true;
  }
  applyKnockback(dx, dz, h, v) {
    for (const x of [dx, dz, h, v]) if (!Number.isFinite(x)) throw new Error("bad knockback");
    this.vel = { x: dx * h, y: v, z: dz * h };
  }
  applyImpulse(v) { for (const k of ["x", "y", "z"]) if (!Number.isFinite(v[k])) throw new Error("bad impulse"); this.vel.x += v.x; this.vel.y += v.y; this.vel.z += v.z; }
  clearVelocity() { this.vel = { x: 0, y: 0, z: 0 }; }
  addEffect(id, ticks) { if (!Number.isFinite(ticks)) throw new Error("bad effect"); this.effects.push(id); }
  removeEffect() { }
  teleport(loc) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error("bad teleport");
    this.location = { ...loc };
    this.vel = { x: 0, y: 0, z: 0 };
  }
  getRotation() { return { x: 0, y: this.yaw }; }
  getViewDirection() { const l = Math.hypot(this.view.x, this.view.y, this.view.z); return { x: this.view.x / l, y: this.view.y / l, z: this.view.z / l }; }
  getVelocity() { return { ...this.vel }; }
  getHeadLocation() { return { x: this.location.x, y: this.location.y + 1.62, z: this.location.z }; }
  getDynamicProperty(k) { return this.props.get(k); }
  setDynamicProperty(k, v) { this.props.set(k, v); }
  remove() { this.alive = false; const a = this.dimension.entities; const i = a.indexOf(this); if (i >= 0) a.splice(i, 1); }
  runCommand(c) { G.__log.cmds.push(c); return {}; }
  playAnimation(name) { G.__log.anims.set(name, (G.__log.anims.get(name) ?? 0) + 1); }
  getGameMode() { return this.gameMode; }
  sendMessage(m) { scanKeys(m); }
  // 簡単な物理: 重力・空気抵抗・地面（y=64）
  __physics() {
    if (!this.alive || this.__pinned) return;
    if (this.typeId === "minecraft:xp_orb") return;
    this.location.x += this.vel.x; this.location.y += this.vel.y; this.location.z += this.vel.z;
    if (this.location.y <= 64) {
      if (this.vel.y < -0.9 && this.typeId === "minecraft:player") {
        const fall = Math.round((-this.vel.y) * 6);
        this.hp -= fall;
        G.__handlers.entityHurt?.({ hurtEntity: this, damage: fall, damageSource: { cause: "fall" } });
      }
      this.location.y = 64; this.vel.y = 0; this.isOnGround = true;
      this.vel.x *= 0.6; this.vel.z *= 0.6;
    } else {
      this.isOnGround = false;
      this.vel.y = (this.vel.y - 0.08) * 0.98;
      this.vel.x *= 0.91; this.vel.z *= 0.91;
    }
  }
}

function solid(x, y, z) {
  if (y < 64) return true;
  // 塔: x 10..12, z -1..1, 高さ 90 まで
  return x >= 10 && x < 12 && z >= -1 && z < 1 && y < 90;
}

export class FakeDimension {
  constructor(id) { this.id = id; this.entities = []; }
  spawnParticle(id, loc, vars) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error(`bad particle loc ${id}`);
    G.__log.particles.set(id, (G.__log.particles.get(id) ?? 0) + 1);
  }
  playSound(id, loc) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error(`bad sound loc ${id}`);
    G.__log.sounds.set(id, (G.__log.sounds.get(id) ?? 0) + 1);
  }
  getEntities(q = {}) {
    let list = this.entities.filter((e) => e.alive);
    if (q.type) list = list.filter((e) => e.typeId === q.type);
    if (q.families) list = list.filter((e) => q.families.every((f) => e.families.includes(f)));
    if (q.location && q.maxDistance !== undefined) {
      if (!Number.isFinite(q.maxDistance)) throw new Error("bad query");
      list = list.filter((e) => Math.hypot(e.location.x - q.location.x, e.location.y - q.location.y, e.location.z - q.location.z) <= q.maxDistance);
    }
    return list;
  }
  getPlayers(q = {}) { return this.getEntities({ ...q, type: "minecraft:player" }); }
  spawnEntity(type, loc) { return new FakeEntity(this, type, loc, 1); }
  spawnItem() { }
  createExplosion() { G.__log.explosions++; }
  getBlockFromRay(o, d, opt = {}) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(o[k]) || !Number.isFinite(d[k])) throw new Error("bad ray");
    const max = opt.maxDistance ?? 50;
    for (let s = 0; s <= max; s += 0.05) {
      const x = o.x + d.x * s, y = o.y + d.y * s, z = o.z + d.z * s;
      if (solid(x, y, z)) {
        const b = { x: Math.floor(x), y: Math.floor(y), z: Math.floor(z) };
        return { block: { location: b, typeId: "minecraft:stone" }, faceLocation: { x: x - b.x, y: y - b.y, z: z - b.z } };
      }
    }
    return undefined;
  }
  getEntitiesFromRay(o, d, opt = {}) {
    const max = opt.maxDistance ?? 50;
    const out = [];
    for (const e of this.entities) {
      const c = { x: e.location.x, y: e.location.y + 0.9, z: e.location.z };
      const w = { x: c.x - o.x, y: c.y - o.y, z: c.z - o.z };
      const s = w.x * d.x + w.y * d.y + w.z * d.z;
      if (s < 0 || s > max) continue;
      const p = { x: o.x + d.x * s, y: o.y + d.y * s, z: o.z + d.z * s };
      if (Math.hypot(p.x - c.x, p.y - c.y, p.z - c.z) < 0.6) out.push({ entity: e, distance: s });
    }
    return out.sort((a, b) => a.distance - b.distance);
  }
}

const overworld = new FakeDimension("minecraft:overworld");
G.__dim = overworld;
G.__time = 6000;
export const world = {
  afterEvents: events, beforeEvents: events,
  props: new Map(),
  getAllPlayers() { return overworld.entities.filter((e) => e.typeId === "minecraft:player" && e.alive); },
  getDimension(id) { if (id !== "overworld") throw new Error("no dim"); return overworld; },
  getTimeOfDay() { return G.__time; },
  getDynamicProperty(k) { return this.props.get(k); },
  setDynamicProperty(k, v) { this.props.set(k, v); },
  sendMessage() { },
};
export default {};
"""

UI = r"""
class Form { title() { return this; } body() { return this; } button() { return this; } toggle() { return this; }
  show() { return Promise.resolve({ canceled: true }); } }
export const ActionFormData = Form; export const ModalFormData = Form; export const MessageFormData = Form;
export default {};
"""

TEST = r"""
import { FakeEntity, ItemStack, system } from "@minecraft/server";
import { BODY_META, TITAN_TYPES, PROP } from "./config.js";
import { frame, stateOf } from "./titans.js";
import { state as odmState } from "./odm.js";
import { hud } from "./ui.js";
import "./main.js";

const G = globalThis;
const H = G.__handlers;
let failures = 0;
const fail = (m) => { failures++; console.log("  FAIL " + m); };
const ok = (m) => console.log("  ok   " + m);
console.warn = (...a) => { G.__log.warns.push(a.join(" ")); };

function clear() { for (const e of [...G.__dim.entities]) e.remove(); }
function player(at = { x: 0, y: 64, z: 0 }) {
  const p = new FakeEntity(G.__dim, "minecraft:player", at, 20, ["player"]);
  p.inv.setItem(0, new ItemStack("aot:odm_blades"));
  p.inv.setItem(1, new ItemStack("aot:spare_blades", 4));
  p.inv.setItem(2, new ItemStack("aot:thunder_spear", 4));
  p.inv.setItem(3, new ItemStack("aot:gas_canister", 2));
  p.equip.Legs = new ItemStack("aot:odm_gear");
  p.setDynamicProperty("aot:gas", 100);
  p.setDynamicProperty("aot:welcomed", true);
  return p;
}
function titan(type = "aot:titan_medium", at = { x: 0, y: 64, z: 20 }, yaw = 0) {
  const info = TITAN_TYPES[type];
  const t = new FakeEntity(G.__dim, type, at, info.hp, ["titan", "pure_titan", "monster", "mob"]);
  t.yaw = yaw;
  t.__pinned = true;            // 巨人は動かさない（物理は掛けない）
  return t;
}
function aim(p, at) {
  const e = p.getHeadLocation();
  p.view = { x: at.x - e.x, y: at.y - e.y, z: at.z - e.z };
}
const near = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

// 1. 塔へアンカーを撃って巻き取る ---------------------------------------
{
  clear();
  const p = player();
  aim(p, { x: 10.0, y: 80, z: 0 });
  G.__advance(2);
  const d0 = near(p.location, { x: 10, y: 80, z: 0 });
  H.itemStartUse({ source: p, itemStack: p.inv.getItem(0) });
  if (!odmState(p).anchor) fail("anchor did not attach to the tower");
  G.__advance(30);
  const d1 = near(p.location, { x: 10, y: 80, z: 0 });
  const gas = p.getDynamicProperty("aot:gas");
  if (!(d1 < d0 - 6)) fail(`reeling did not pull the player in (${d0.toFixed(1)} -> ${d1.toFixed(1)})`);
  else ok(`reel: ${d0.toFixed(1)}m -> ${d1.toFixed(1)}m, gas ${gas.toFixed(1)}`);
  if (!(gas < 100)) fail("gas was not used");
  if (!G.__log.particles.get("aot:wire")) fail("no wire drawn");
  H.itemStopUse({ source: p, itemStack: p.inv.getItem(0) });
  if (odmState(p).anchor) fail("release did not cut the anchor");
  // 落ちる: ガス噴射で受け止めて落下ダメージ無し
  const hp0 = p.hp;
  G.__advance(80);
  if (!p.isOnGround) fail("player never landed");
  if (p.hp < hp0) fail(`fall damage was not cancelled (${hp0} -> ${p.hp})`);
  else ok("landing: no fall damage");
}

// 2. 巨人に刺して巻き取り、うなじの脇を抜けて斬る ----------------------
for (const type of Object.keys(TITAN_TYPES)) {
  for (let v = 0; v < BODY_META.length; v++) {
    clear();
    const t = titan(type, { x: 0, y: 64, z: 30 }, 0);   // +Z を向く（うなじは -Z 側）
    t.variant = v;
    const F = frame(t);
    const p = player({ x: 2, y: 64, z: 30 - 18 });
    aim(p, { x: F.nape.x, y: F.nape.y + 0.4, z: F.nape.z + F.radius * 0.6 });
    H.itemStartUse({ source: p, itemStack: p.inv.getItem(0) });
    let killed = false;
    for (let i = 0; i < 60 && !killed; i++) { G.__advance(1); killed = t.state === "dying"; }
    if (!killed) fail(`${TITAN_TYPES[type].key}/${BODY_META[v].key}: pass-by nape cut failed (anchor ${!!odmState(p).anchor})`);
    if (killed && p.getDynamicProperty(PROP.kills) !== 1) fail("kill was not credited");
    // 蒸発: しばらくすると消える
    G.__advance(140);
    if (t.alive) fail(`${TITAN_TYPES[type].key}: dying titan was not removed`);
    H.itemStopUse({ source: p, itemStack: p.inv.getItem(0) });
  }
}
ok("pass-by nape cuts on every class and body");

// 3. 後ろから勢いよく斬る / 遅いと浅い / 前からは効かない ------------------
{
  clear();
  const t = titan();
  const F = frame(t);
  const p = player({ x: F.nape.x, y: F.nape.y - 1.4, z: F.nape.z - 2.2 });
  p.__pinned = true;
  p.isOnGround = false;
  aim(p, F.nape);
  p.vel = { x: 0, y: 0, z: 0.8 };
  H.entityHitEntity({ damagingEntity: p, hitEntity: t });
  if (t.state !== "dying") fail("fast hit from behind did not kill"); else ok("fast hit on the nape kills");

  clear();
  const t2 = titan();
  const F2 = frame(t2);
  const q = player({ x: F2.nape.x, y: F2.nape.y - 1.4, z: F2.nape.z - 2.2 });
  q.__pinned = true; q.isOnGround = false;
  aim(q, F2.nape);
  q.vel = { x: 0, y: 0, z: 0 };
  G.__advance(40);
  H.entityHitEntity({ damagingEntity: q, hitEntity: t2 });
  if (t2.state === "dying") fail("slow hit killed (should be shallow)");
  if (!(t2.hp < t2.maxHp * 0.7)) fail("shallow hit did no damage"); else ok("slow hit is shallow");

  clear();
  const t3 = titan();
  const F3 = frame(t3);
  const r = player({ x: F3.nape.x, y: F3.nape.y - 1.2, z: F3.nape.z + 2.6 });
  r.__pinned = true; r.isOnGround = false;
  aim(r, F3.nape);
  r.vel = { x: 0, y: 0, z: -0.9 };
  H.entityHitEntity({ damagingEntity: r, hitEntity: t3 });
  if (t3.state === "dying") fail("hit from the front killed through the face");
  else ok("nape can't be cut from the front");
}

// 4. 再生 ---------------------------------------------------------------
{
  clear();
  const t = titan();
  const p = player({ x: 0, y: 64, z: 17 });
  t.applyDamage(30, { cause: "entityAttack", damagingEntity: p });
  const hp1 = t.hp;
  G.__advance(200);
  if (!(t.hp > hp1)) fail("titan did not regenerate"); else ok(`regen: ${hp1} -> ${t.hp.toFixed(1)}`);
}

// 5. 掴まれて食べられる / スニークで脱出 -----------------------------------
{
  clear();
  const t = titan("aot:titan_large");
  const p = player({ x: 0, y: 64, z: 22 });
  const rnd = Math.random; Math.random = () => 0.01;
  t.lastHurt = -99;
  H.entityHurt({ hurtEntity: p, damage: 4, damageSource: { cause: "entityAttack", damagingEntity: t } });
  Math.random = rnd;
  if (t.state !== "grab") fail("titan did not grab");
  const hp0 = p.hp;
  G.__advance(60);
  if (!(p.hp < hp0 - 10)) fail(`grabbed player was not bitten (${hp0} -> ${p.hp})`); else ok("grab -> eat");
  if (t.state !== "idle" && t.state !== "swat") fail(`titan stuck in ${t.state}`);

  clear();
  const t2 = titan("aot:titan_medium");
  const q = player({ x: 0, y: 64, z: 22 });
  Math.random = () => 0.01;
  H.entityHurt({ hurtEntity: q, damage: 4, damageSource: { cause: "entityAttack", damagingEntity: t2 } });
  Math.random = rnd;
  G.__advance(5);
  q.isSneaking = true; G.__advance(2); q.isSneaking = false;
  G.__advance(60);
  if (q.hp < 15) fail("escape did not work"); else ok("sneak escape from a grab");
}

// 6. 雷槍: うなじの近くに刺さって爆発 ------------------------------------
{
  clear();
  const t = titan("aot:titan_large", { x: 0, y: 64, z: 30 }, 0);
  const F = frame(t);
  const p = player({ x: 0, y: 64, z: 10 });
  p.__pinned = true;
  p.location.y = F.nape.y - 1.0;
  p.selectedSlotIndex = 2;
  aim(p, { x: F.nape.x, y: F.nape.y, z: F.nape.z + 0.3 });
  H.itemUse({ source: p, itemStack: p.inv.getItem(2) });
  G.__advance(60);
  if (t.state !== "dying") fail("thunder spear at the nape did not kill"); else ok("thunder spear");
  if (!G.__log.explosions) fail("no explosion");
}

// 7. リヴァイが巨人を倒す ------------------------------------------------
{
  clear();
  const t = titan("aot:titan_medium", { x: 0, y: 64, z: 14 }, 180);
  const levi = new FakeEntity(G.__dim, "aot:levi_ackerman", { x: 0, y: 64, z: 0 }, 90, ["aot_soldier"]);
  let killed = false;
  for (let i = 0; i < 300 && !killed; i++) { G.__advance(1); killed = t.state === "dying"; }
  if (!killed) fail("Levi never killed the titan"); else ok("Levi's ODM attack");
  G.__advance(120);
  if (levi.state !== "idle") fail(`Levi stuck in ${levi.state}`);
}

// 8. 昼と夜 --------------------------------------------------------------
{
  clear();
  const t = titan();
  G.__time = 18000; G.__advance(30);
  if (t.state !== "sleep") fail(`titan did not sleep at night (${t.state})`);
  G.__time = 2000; G.__advance(30);
  if (t.state !== "idle") fail(`titan did not wake at dawn (${t.state})`); else ok("night sleep / dawn wake");
}

// 9. 刃の消耗と替え刃・ガスボンベ・支給・HUD -------------------------------
{
  clear();
  const t = titan();
  const p = player({ x: 0, y: 64, z: 18.5 });
  p.__pinned = true;
  aim(p, { x: 0, y: 65, z: 20 });
  const blades = p.inv.getItem(0);
  blades.__dur.damage = 58;            // バニラが当たりで 1 減らした後
  H.entityHitEntity({ damagingEntity: p, hitEntity: t });
  const now = p.inv.getItem(0);
  if (now?.typeId !== "aot:odm_blades" || now.__dur.damage !== 0) fail("worn blades were not replaced");
  if (p.inv.getItem(1).amount !== 3) fail("spare blade was not consumed"); else ok("blade swap");
  p.setDynamicProperty("aot:gas", 10);
  H.itemCompleteUse({ source: p, itemStack: p.inv.getItem(3) });
  if (p.getDynamicProperty("aot:gas") !== 100 || p.inv.getItem(3).amount !== 1) fail("gas canister failed");
  else ok("gas refill");
  hud(p);
  if (!p.actionbar) fail("no HUD");
  H.scriptEventReceive({ id: "aot:kit", sourceEntity: p });
  if (!p.inv.slots.some((s) => s?.typeId === "aot:survey_jacket")) fail("kit not given"); else ok("kit");
  // 回転斬り
  p.__pinned = false;
  p.location = { x: 0, y: 70, z: 15 }; p.isOnGround = false;
  G.__advance(1);
  p.isSneaking = true; G.__advance(1); p.isSneaking = false;
  if (!(G.__log.anims.get("animation.aot.p.spin") > 0)) fail("spin slash did not play");
  // 空中でジャンプ: ガス噴射
  p.location = { x: 0, y: 72, z: 0 }; p.isOnGround = false; G.__advance(12);
  p.isJumping = true; G.__advance(1); p.isJumping = false;
  if (!(G.__log.anims.get("animation.aot.p.boost") > 0)) fail("gas boost did not play");
  G.__advance(60);
}

// 10. 信煙弾・手帳 -------------------------------------------------------
{
  clear();
  const p = player();
  p.inv.setItem(5, new ItemStack("aot:flare_gun"));
  p.selectedSlotIndex = 5;
  H.itemUse({ source: p, itemStack: p.inv.getItem(5) });
  G.__advance(40);
  if (!G.__log.particles.get("aot:smoke")) fail("flare made no smoke");
  p.inv.setItem(6, new ItemStack("aot:survey_journal"));
  p.selectedSlotIndex = 6;
  H.itemUse({ source: p, itemStack: p.inv.getItem(6) });
  G.__advance(5);
}

if (G.__log.warns.length) fail("script warnings: " + G.__log.warns.join(" / ").slice(0, 2000));
console.log("__USED__" + JSON.stringify({
  particles: [...G.__log.particles.keys()], sounds: [...G.__log.sounds.keys()],
  anims: [...G.__log.anims.keys()], keys: [...G.__log.keys],
}));
if (failures) { console.log(`  ${failures} failure(s)`); process.exit(1); }
console.log("  all behaviour checks passed");
process.exit(0);
"""


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="aot-test-")
    try:
        with open(os.path.join(tmp, "package.json"), "w") as fh:
            json.dump({"name": "aot-test", "type": "module"}, fh)
        for mod, src in (("@minecraft/server", SERVER), ("@minecraft/server-ui", UI)):
            d = os.path.join(tmp, "node_modules", *mod.split("/"))
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.js"), "w") as fh:
                fh.write(src)
            with open(os.path.join(d, "package.json"), "w") as fh:
                json.dump({"name": mod, "type": "module", "main": "index.js"}, fh)
        for f in os.listdir(SCRIPTS):
            if f.endswith(".js"):
                shutil.copy(os.path.join(SCRIPTS, f), os.path.join(tmp, f))
        with open(os.path.join(tmp, "__test.js"), "w") as fh:
            fh.write(TEST)
        res = subprocess.run(["node", os.path.join(tmp, "__test.js")], capture_output=True, text=True,
                             timeout=600)
        used = None
        for line in res.stdout.splitlines():
            if line.startswith("__USED__"):
                used = json.loads(line[len("__USED__"):])
            else:
                print(line)
        if res.returncode or used is None:
            print(res.stderr[-4000:])
            return 1
        errs = []
        particles = set()
        for f in os.listdir(os.path.join(C.RP, "particles")):
            with open(os.path.join(C.RP, "particles", f)) as fh:
                particles.add(json.load(fh)["particle_effect"]["description"]["identifier"])
        with open(os.path.join(C.RP, "sounds", "sound_definitions.json")) as fh:
            sounds = set(json.load(fh)["sound_definitions"])
        with open(os.path.join(C.RP, "animations", "aot_player.animation.json")) as fh:
            anims = set(json.load(fh)["animations"])
        for pid in used["particles"]:
            if pid not in particles:
                errs.append(f"particle {pid} does not exist")
        for sid in used["sounds"]:
            if sid.startswith("aot.") and sid not in sounds:
                errs.append(f"sound {sid} does not exist")
        for a in used["anims"]:
            if a not in anims:
                errs.append(f"animation {a} does not exist")
        for k in used["keys"]:
            if k not in KEYS:
                errs.append(f"lang key {k} is missing")
        print(f"  used: {len(used['particles'])} particles, {len(used['sounds'])} sounds, "
              f"{len(used['anims'])} body animations, {len(used['keys'])} lang keys")
        unused = sorted(particles - set(used["particles"]))
        if unused:
            print(f"  (particles not reached by the tests: {', '.join(unused)})")
        for e in errs:
            print("  FAIL", e)
        return 1 if errs else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    _ = re
    sys.exit(main())
