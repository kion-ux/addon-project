# -*- coding: utf-8 -*-
"""スクリプトの挙動テスト（Minecraft 無しで全技を実際に走らせる）。

@minecraft/server を「動く」スタブに差し替え、偽のプレイヤー・敵・地面・tick を用意して
* 8 武器 × 4 技（戦技／突進／空中／必殺）を状況を作って発動
* 弓の溜め（3 段階）・盾のガード／ジャストガード／反射
* 通常攻撃の三連コンボ、二段ジャンプ・空中ダッシュ・回避ステップ
を実行し、次を検査する:
* スクリプトが例外を出さない（engine の report や console.warn に [hd] が出ない）
* 技が敵にダメージを与える（必殺技・戦技）
* 使ったパーティクル ID・効果音 ID・全身モーション名がリソースパックに実在する
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hd_common import BP, RP  # noqa: E402

SCRIPTS = os.path.join(BP, "scripts")

SERVER = r"""
const G = globalThis;
G.__log = { particles: new Map(), sounds: new Map(), anims: new Map(), cmds: [], warns: [], molang: new Set() };
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
G.__advance = (n) => {
  for (let i = 0; i < n; i++) {
    system.currentTick++;
    const t = system.currentTick;
    for (const iv of intervals) if (t % iv.every === 0) iv.f();
    const due = timeouts.filter((x) => x.due <= t);
    for (const x of due) timeouts.splice(timeouts.indexOf(x), 1);
    for (const x of due) x.f();
  }
};
const events = new Proxy({}, { get(_, name) { return { subscribe(f) { G.__handlers[name] = f; return f; }, unsubscribe() { } }; } });
export class MolangVariableMap {
  constructor() { this.vars = {}; }
  setFloat(k, v) {
    if (!Number.isFinite(v)) throw new Error(`non-finite molang ${k}=${v}`);
    this.vars[k] = v; G.__log.molang.add(k);
  }
}
export class ItemStack { constructor(typeId, amount = 1) { this.typeId = typeId; this.amount = amount; } }

let nextId = 1;
export class FakeEntity {
  constructor(dim, typeId, loc, hp = 20) {
    this.id = String(nextId++);
    this.typeId = typeId;
    this.dimension = dim;
    this.location = { ...loc };
    this.vel = { x: 0, y: 0, z: 0 };
    this.view = { x: 0, y: 0, z: 1 };
    this.hp = hp; this.maxHp = hp;
    this.alive = true;
    this.isSneaking = false; this.isSprinting = false; this.isOnGround = true; this.isJumping = false;
    this.isInWater = false;
    this.lastHurt = -99;
    this.props = new Map();
    this.effects = [];
    this.nameTag = "";
    this.name = "Tester";
    this.held = undefined;
    this.onScreenDisplay = { setActionBar: (m) => { this.actionbar = m; }, setTitle: (t, o) => { this.title = t; } };
    dim.entities.push(this);
  }
  get isValid() { return this.alive; }
  getComponent(name) {
    if (name === "minecraft:health") {
      const e = this;
      return { get currentValue() { return e.hp; }, get effectiveMax() { return e.maxHp; },
               setCurrentValue(v) { e.hp = Math.max(0, Math.min(e.maxHp, v)); return true; } };
    }
    if (name === "minecraft:equippable") {
      const e = this;
      return { getEquipment(slot) { return slot === "Mainhand" ? e.held : undefined; } };
    }
    if (name === "minecraft:inventory") {
      return { container: { addItem() { }, getItem() { return undefined; }, size: 36 } };
    }
    return undefined;
  }
  applyDamage(amount, opts) {
    if (!Number.isFinite(amount)) throw new Error("bad damage " + amount);
    const t = system.currentTick;
    if (t - this.lastHurt < 10) return false;
    this.lastHurt = t;
    this.hp -= amount;
    G.__handlers.entityHurt?.({ hurtEntity: this, damage: amount,
      damageSource: { cause: "entityAttack", damagingEntity: opts?.damagingEntity } });
    return true;
  }
  applyKnockback(dx, dz, h, v) {
    for (const x of [dx, dz, h, v]) if (!Number.isFinite(x)) throw new Error("bad knockback");
    this.vel = { x: dx * h, y: v, z: dz * h };
    if (v > 0) this.isOnGround = false;
  }
  addEffect(id, ticks, o) { if (!Number.isFinite(ticks)) throw new Error("bad effect"); this.effects.push(id); }
  removeEffect() { }
  teleport(loc, o) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error("bad teleport");
    this.location = { ...loc };
  }
  getViewDirection() { return { ...this.view }; }
  getVelocity() { return { ...this.vel }; }
  getHeadLocation() { return { x: this.location.x, y: this.location.y + 1.6, z: this.location.z }; }
  getDynamicProperty(k) { return this.props.get(k); }
  setDynamicProperty(k, v) { this.props.set(k, v); }
  remove() { this.alive = false; const a = this.dimension.entities; a.splice(a.indexOf(this), 1); }
  setOnFire() { return true; }
  runCommand(c) { G.__log.cmds.push(c); return {}; }
  playAnimation(name) { G.__log.anims.set(name, (G.__log.anims.get(name) ?? 0) + 1); }
  getGameMode() { return "survival"; }
  getEntitiesFromViewDirection() {
    return this.dimension.entities.filter((e) => e !== this && e.typeId !== "hd:dmg_text").slice(0, 1).map((entity) => ({ entity, distance: 3 }));
  }
  getBlockFromViewDirection() { return { block: { location: { x: this.location.x + 6, y: 63, z: this.location.z + 6 }, typeId: "minecraft:stone" } }; }
  sendMessage() { }
}

export class FakeDimension {
  constructor(id) { this.id = id; this.entities = []; }
  spawnParticle(id, loc, vars) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error(`bad particle loc ${id}`);
    G.__log.particles.set(id, (G.__log.particles.get(id) ?? 0) + 1);
  }
  playSound(id) { G.__log.sounds.set(id, (G.__log.sounds.get(id) ?? 0) + 1); }
  getEntities(q = {}) {
    let list = [...this.entities];
    if (q.type) list = list.filter((e) => e.typeId === q.type);
    if (q.location && q.maxDistance !== undefined) {
      if (!Number.isFinite(q.maxDistance)) throw new Error("bad query");
      list = list.filter((e) => Math.hypot(e.location.x - q.location.x, e.location.y - q.location.y, e.location.z - q.location.z) <= q.maxDistance);
    }
    return list;
  }
  spawnEntity(type, loc) { return new FakeEntity(this, type, loc, 1); }
  getBlock(loc) {
    const solid = loc.y < 64;
    return { typeId: solid ? "minecraft:stone" : "minecraft:air", isAir: !solid, isLiquid: false };
  }
}

const overworld = new FakeDimension("minecraft:overworld");
G.__dim = overworld;
export const world = {
  afterEvents: events, beforeEvents: events,
  getAllPlayers() { return overworld.entities.filter((e) => e.typeId === "minecraft:player"); },
  getDimension() { return overworld; },
  getEntity(id) { return overworld.entities.find((e) => e.id === id); },
  sendMessage() { },
};
export default {};
"""

UI = r"""
class Form { title() { return this; } body() { return this; } button() { return this; }
  show() { return Promise.resolve({ canceled: true }); } }
export const ActionFormData = Form; export const ModalFormData = Form; export const MessageFormData = Form;
export default {};
"""

TEST = r"""
import { FakeEntity, ItemStack, system } from "@minecraft/server";
import { WEAPONS, GAUGE_MAX } from "./config.js";
import { setGauge, gauge } from "./combat.js";
import { clearBusy } from "./engine.js";
import "./main.js";

const G = globalThis;
const H = G.__handlers;
let failures = 0;
const fail = (m) => { failures++; console.log("  FAIL " + m); };
const origWarn = console.warn;
console.warn = (...a) => { const s = a.join(" "); if (!s.includes("起動")) G.__log.warns.push(s); };

function makePlayer(id) {
  const p = new FakeEntity(G.__dim, "minecraft:player", { x: 0, y: 64, z: 0 });
  p.held = new ItemStack(id);
  return p;
}
function enemies(n = 3) {
  const out = [];
  for (let i = 0; i < n; i++) out.push(new FakeEntity(G.__dim, "minecraft:zombie", { x: (i - 1) * 1.2, y: 64, z: 2.2 + i * 0.4 }, 200));
  return out;
}
function clear() { for (const e of [...G.__dim.entities]) e.remove(); }
function ground(p, on) { p.isOnGround = on; p.location.y = on ? 64 : 67; }

const kinds = ["skill", "dash", "air", "ult"];
for (const [id, w] of Object.entries(WEAPONS)) {
  for (const kind of kinds) {
    clear();
    const p = makePlayer(id);
    const foes = enemies();
    const before = foes.reduce((a, e) => a + e.hp, 0);
    G.__log.warns.length = 0;
    p.isSneaking = kind === "ult";
    p.isSprinting = kind === "dash";
    ground(p, kind !== "air");
    if (kind === "ult") setGauge(p, GAUGE_MAX);
    if (w.charge) {
      H.itemStartUse?.({ source: p, itemStack: p.held });
      if (kind === "skill" || kind === "air") {
        G.__advance(22);
        ground(p, kind !== "air");
        H.itemStopUse?.({ source: p, itemStack: p.held });
      }
    } else if (w.guard) {
      H.itemStartUse?.({ source: p, itemStack: p.held });
      if (kind === "skill") {
        G.__advance(2);
        // ジャストガード → 通常ガード → 離して反射
        const atk = foes[0];
        p.applyDamage(4, { damagingEntity: atk });
        G.__advance(12);
        p.lastHurt = -99;
        p.applyDamage(3, { damagingEntity: atk });
        H.itemStopUse?.({ source: p, itemStack: p.held });
      }
    } else {
      H.itemUse({ source: p, itemStack: p.held });
    }
    for (let t = 0; t < 130; t++) {
      G.__advance(1);
      // 落下を少しずつ地面へ
      if (!p.isOnGround) { p.location.y -= 0.4; if (p.location.y <= 64) ground(p, true); }
    }
    const after = foes.reduce((a, e) => a + Math.max(e.hp, 0), 0);
    if (G.__log.warns.length) fail(`${w.key}.${kind}: ${G.__log.warns.join(" / ").slice(0, 600)}`);
    if (kind === "ult" && gauge(p) !== 0) fail(`${w.key}.ult: gauge not consumed`);
    const dealt = before - after;
    if ((kind === "ult" || kind === "skill") && dealt <= 0) fail(`${w.key}.${kind}: no damage dealt`);
    console.log(`  ${w.key.padEnd(11)} ${kind.padEnd(5)} dmg ${dealt.toFixed(1).padStart(6)}`);
    clearBusy(p);
  }
  // 三連コンボ
  clear();
  const p = makePlayer(id);
  const [foe] = enemies(1);
  for (let i = 0; i < 3; i++) {
    foe.lastHurt = -99;
    H.entityHitEntity({ damagingEntity: p, hitEntity: foe });
    G.__advance(8);
  }
  G.__advance(40);
  if (G.__log.warns.length) fail(`${w.key}.combo: ${G.__log.warns.join(" / ")}`);
}

// 機動: 二段ジャンプ・空中ダッシュ・回避ステップ
clear();
const p = makePlayer("hd:dagger");
ground(p, false); p.isJumping = false; G.__advance(6);
p.isJumping = true; G.__advance(2);
if (!(G.__log.anims.get("animation.hd.p.airjump") > 0)) fail("double jump did not trigger");
p.isSneaking = true; G.__advance(2); p.isSneaking = false; G.__advance(2);
if (!(G.__log.anims.get("animation.hd.p.dash") > 0)) fail("air dash did not trigger");
ground(p, true); G.__advance(4);
p.isSneaking = true; G.__advance(2); p.isSneaking = false; G.__advance(2); p.isSneaking = true; G.__advance(2);
if (!(G.__log.anims.get("animation.hd.p.step") > 0)) fail("step did not trigger");

// 弓の溜めの段階
for (const [hold, lv] of [[3, 0], [12, 1], [25, 2]]) {
  clear(); const b = makePlayer("hd:bow"); enemies(1);
  H.itemStartUse({ source: b, itemStack: b.held }); G.__advance(hold);
  H.itemStopUse({ source: b, itemStack: b.held }); G.__advance(60);
}
if (G.__log.warns.length) fail(`bow charge: ${G.__log.warns.join(" / ")}`);

// 訓練用カカシ
clear();
const tester = makePlayer("hd:greatsword");
const dummy = new FakeEntity(G.__dim, "hd:training_dummy", { x: 0, y: 64, z: 2 }, 1000);
dummy.applyDamage(12, { damagingEntity: tester });
if (!dummy.nameTag.includes("DPS")) fail("dummy nameTag not updated");
if (dummy.hp !== 1000) fail("dummy not healed");
G.__advance(40);

console.log("__USED__" + JSON.stringify({
  particles: [...G.__log.particles.keys()], sounds: [...G.__log.sounds.keys()],
  anims: [...G.__log.anims.keys()], cmds: G.__log.cmds.filter((c) => c.startsWith("playanimation")).map((c) => c.split(" ")[2]),
  molang: [...G.__log.molang],
}));
if (failures) { console.log(`  ${failures} failure(s)`); process.exit(1); }
console.log("  all behaviour checks passed");
process.exit(0);
"""


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="hd-test-")
    try:
        with open(os.path.join(tmp, "package.json"), "w") as fh:
            json.dump({"name": "hd-test", "type": "module"}, fh)
        for mod, src in (("@minecraft/server", SERVER), ("@minecraft/server-ui", UI)):
            d = os.path.join(tmp, "node_modules", *mod.split("/"))
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "index.js"), "w").write(src)
            json.dump({"name": mod, "type": "module", "main": "index.js"}, open(os.path.join(d, "package.json"), "w"))
        for f in os.listdir(SCRIPTS):
            if f.endswith(".js"):
                shutil.copy(os.path.join(SCRIPTS, f), os.path.join(tmp, f))
        open(os.path.join(tmp, "__test.js"), "w").write(TEST)
        res = subprocess.run(["node", os.path.join(tmp, "__test.js")], capture_output=True, text=True, timeout=300)
        out = res.stdout
        used = None
        for line in out.splitlines():
            if line.startswith("__USED__"):
                used = json.loads(line[len("__USED__"):])
            else:
                print(line)
        if res.returncode:
            print(res.stderr[-3000:])
            return 1
        # 参照の実在チェック
        errs = []
        particles = set()
        for f in os.listdir(os.path.join(RP, "particles")):
            particles.add(json.load(open(os.path.join(RP, "particles", f)))["particle_effect"]["description"]["identifier"])
        sounds = set(json.load(open(os.path.join(RP, "sounds", "sound_definitions.json")))["sound_definitions"])
        anims = set(json.load(open(os.path.join(RP, "animations", "hd_player.animation.json")))["animations"])
        for pid in used["particles"]:
            if pid not in particles:
                errs.append(f"particle {pid} does not exist")
        for sid in used["sounds"]:
            if sid.startswith("hd.") and sid not in sounds:
                errs.append(f"sound {sid} does not exist")
        for a in used["anims"] + used["cmds"]:
            if a not in anims:
                errs.append(f"animation {a} does not exist")
        unused = sorted(particles - set(used["particles"]))
        print(f"  used: {len(used['particles'])} particles, {len(used['sounds'])} sounds, "
              f"{len(set(used['anims']))} body animations")
        if unused:
            print(f"  (particles never used by the tested paths: {', '.join(unused)})")
        for e in errs:
            print("  FAIL", e)
        return 1 if errs else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
