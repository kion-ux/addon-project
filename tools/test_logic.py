"""Behaviour tests for the behaviour-pack scripts.

check_scripts.py only proves the modules *load*.  This runs them against a
functional stub of @minecraft/server with a fake player, so the parts that
decide what the player can actually do — the technique wheel, the Numbers
abilities that now live in it, the release-rate caps — are exercised for real.
Minecraft cannot be run here, so this is the only place those code paths get
executed before shipping.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "packs", "kaiju8_BP", "scripts")

SERVER_STUB = """
export const system = {
  currentTick: 0,
  run(f) { try { f(); } catch (_) { } },
  runTimeout(f) { globalThis.__pending.push(f); return 0; },
  runInterval() { return 0; },
  clearRun() { },
};
globalThis.__pending = [];
globalThis.__particles = [];
globalThis.__sounds = [];

const eventList = new Proxy({}, {
  get() { return { subscribe() { }, unsubscribe() { } }; },
});

export const world = {
  afterEvents: eventList,
  beforeEvents: eventList,
  getAllPlayers() { return globalThis.__players ?? []; },
  getDimension() { return globalThis.__dimension; },
  sendMessage() { },
  getDynamicProperty() { return undefined; },
  setDynamicProperty() { },
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

UI_STUB = """
class Form {
  title() { return this; }
  body() { return this; }
  button() { return this; }
  button1() { return this; }
  button2() { return this; }
  slider() { return this; }
  dropdown() { return this; }
  show() { return Promise.resolve({ canceled: true }); }
}
export const ActionFormData = Form;
export const ModalFormData = Form;
export const MessageFormData = Form;
export default {};
"""

# --------------------------------------------------------------------------
TEST = r"""
import { TECH, listFor, selected, selectedIndex, cycle } from "./techniques.js";
import { NUMBERS, wornNumbers, selectedAbility } from "./numbers.js";
import { releaseRate } from "./weapons.js";

let failures = 0;
function check(name, cond, detail) {
  if (cond) return;
  failures++;
  console.log(`  FAIL ${name}${detail === undefined ? "" : "  -> " + detail}`);
}

const dimension = {
  spawnParticle(id) { globalThis.__particles.push(id); },
  playSound(id) { globalThis.__sounds.push(id); },
  getEntities() { return []; },
  spawnEntity() { return { getComponent() { return undefined; } }; },
};
globalThis.__dimension = dimension;

function makePlayer(opts = {}) {
  const props = new Map();
  const equipment = new Map(Object.entries(opts.equipment ?? {}));
  return {
    id: opts.id ?? "p1",
    typeId: "minecraft:player",
    dimension,
    location: { x: 0, y: 64, z: 0 },
    isSneaking: false, isSprinting: false, isOnGround: true, isJumping: false,
    getDynamicProperty(k) { return props.get(k); },
    setDynamicProperty(k, v) { props.set(k, v); },
    getHeadLocation() { return { x: 0, y: 65.6, z: 0 }; },
    getViewDirection() { return { x: 0, y: 0, z: 1 }; },
    getVelocity() { return { x: 0, y: 0, z: 0 }; },
    getComponent(name) {
      if (name === "minecraft:equippable") {
        return { getEquipment(slot) { return equipment.get(slot); } };
      }
      return undefined;
    },
    addEffect() { }, applyDamage() { }, applyKnockback() { },
    runCommand() { }, sendMessage() { }, onScreenDisplay: { setActionBar() { } },
    playSound() { }, triggerEvent() { },
  };
}

// ---------------------------------------------------------------- 1. bare
const bare = makePlayer();
const TWIN = "kaiju8:twin_sw2033";
check("bare wheel equals the weapon's own techniques",
      listFor(bare, TWIN).length === TECH[TWIN].length,
      `${listFor(bare, TWIN).length} vs ${TECH[TWIN].length}`);
check("an item with no techniques stays untouched",
      listFor(bare, "kaiju8:kaiju_detector") === undefined);
check("no Numbers worn", wornNumbers(bare) === undefined);

// ------------------------------------------------- 2. Numbers join the wheel
const NUM10 = "kaiju8:numbers_10";
const worn = makePlayer({ id: "p2", equipment: { Head: { typeId: NUM10 } } });
check("Numbers is detected", wornNumbers(worn) === NUM10);

const abilities = NUMBERS[NUM10].abilities;
const wheel = listFor(worn, TWIN);
check("wheel = weapon techniques + the machine's abilities",
      wheel.length === TECH[TWIN].length + abilities.length,
      `${wheel.length} vs ${TECH[TWIN].length}+${abilities.length}`);
check("the abilities land at the end and are marked",
      wheel.slice(TECH[TWIN].length).every((e) => e.numbers === NUM10));
check("every wheel entry is runnable",
      wheel.every((e) => typeof e.run === "function" && typeof e.name === "string"));
check("no duplicate names in one wheel",
      new Set(wheel.map((e) => e.name)).size === wheel.length);

// --------------------------------------------------------- 3. cycling wraps
const seen = [];
for (let i = 0; i < wheel.length; i++) {
  seen.push(selected(worn, TWIN).name);
  cycle(worn, TWIN, 1);
}
check("one full rotation visits every entry exactly once",
      new Set(seen).size === wheel.length, seen.join(","));
check("a full rotation returns to the start", selectedIndex(worn, TWIN) === 0);

cycle(worn, TWIN, -1);
check("reverse cycling lands on the last entry",
      selectedIndex(worn, TWIN) === wheel.length - 1);

// ------------------------------------ 4. the wheel syncs the terminal choice
cycle(worn, TWIN, 1);                       // back to index 0
for (let i = 0; i < TECH[TWIN].length; i++) cycle(worn, TWIN, 1);
const onAbility = selected(worn, TWIN);
check("cycling past the techniques reaches an ability", onAbility.numbers === NUM10);
check("selecting an ability in the wheel syncs the terminal selection",
      selectedAbility(worn, NUM10)?.id === onAbility.ability,
      `${selectedAbility(worn, NUM10)?.id} vs ${onAbility.ability}`);

// ------------------------------------ 5. taking the Numbers off shrinks it
const bare2 = makePlayer({ id: "p3" });
bare2.setDynamicProperty("kaiju8:tech_select", JSON.stringify({ [TWIN]: 99 }));
const idx = selectedIndex(bare2, TWIN);
check("a stale index is clamped into range",
      idx >= 0 && idx < TECH[TWIN].length, String(idx));
check("selected() still resolves after the Numbers comes off",
      selected(bare2, TWIN) !== undefined);

// ---------------------------------------------- 6. abilities actually fire
let ran = 0;
for (const a of abilities) {
  const before = globalThis.__particles.length;
  try { a.run(worn); ran++; } catch (e) {
    check(`ability ${a.id} runs without throwing`, false, String(e));
  }
  check(`ability ${a.id} emits something`,
        globalThis.__particles.length > before || globalThis.__sounds.length > 0);
}
check("every ability of the worn machine ran", ran === abilities.length);

// ------------------------------------------- 7. every technique in the game
let techCount = 0;
for (const [itemId, list] of Object.entries(TECH)) {
  for (const t of list) {
    techCount++;
    check(`${itemId}/${t.id} has a name`, typeof t.name === "string" && t.name.length > 0);
    check(`${itemId}/${t.id} has a cooldown`, typeof t.cd === "number" && t.cd > 0);
    try { t.run(worn, { mult: 1.5, rate: 50 }); } catch (e) {
      check(`${itemId}/${t.id} runs without throwing`, false, String(e));
    }
  }
}
// drain the later() callbacks the techniques queued
for (let i = 0; i < 3; i++) {
  const pending = globalThis.__pending.splice(0);
  for (const f of pending) { try { f(); } catch (e) {
    check("a queued technique callback throws", false, String(e));
  } }
}

// ------------------------------------------- 8. every machine, every weapon
let combos = 0;
for (const machine of Object.keys(NUMBERS)) {
  const pilot = makePlayer({ id: `m-${machine}`, equipment: { Head: { typeId: machine } } });
  const list = NUMBERS[machine].abilities;
  check(`${machine} declares abilities`, Array.isArray(list) && list.length > 0);
  for (const weapon of Object.keys(TECH)) {
    const w = listFor(pilot, weapon);
    combos++;
    check(`${machine} + ${weapon} wheel length`,
          w.length === TECH[weapon].length + list.length,
          `${w.length} vs ${TECH[weapon].length}+${list.length}`);
    // walk the whole wheel; every stop must resolve and stay in range
    for (let i = 0; i < w.length + 2; i++) {
      const at = selectedIndex(pilot, weapon);
      check(`${machine} + ${weapon} index in range`, at >= 0 && at < w.length, String(at));
      check(`${machine} + ${weapon} entry resolves`, selected(pilot, weapon) !== undefined);
      cycle(pilot, weapon, 1);
    }
  }
  for (const a of list) {
    try { a.run(pilot); } catch (e) {
      check(`${machine}/${a.id} runs`, false, String(e));
    }
  }
}
for (let i = 0; i < 3; i++) {
  const pending = globalThis.__pending.splice(0);
  for (const f of pending) { try { f(); } catch (e) {
    check("a queued ability callback throws", false, String(e));
  } }
}

// -------------------------------------- 9. the geometric effect helpers
import { fxArc, fxSpiral, fxColumn, fxCone, fxWall, sequence, trail }
  from "./effects.js";

const dirs = [
  { x: 0, y: 0, z: 1 }, { x: 1, y: 0, z: 0 }, { x: 0, y: 1, z: 0 },
  { x: 0, y: -1, z: 0 }, { x: 0.577, y: 0.577, z: 0.577 },
  { x: 0, y: 0, z: 0 },                     // 退化した視線でも落ちないこと
];
let emitted = 0;
const spy = {
  spawnParticle(id, loc) {
    emitted++;
    check("effect helpers never emit NaN",
          Number.isFinite(loc.x) && Number.isFinite(loc.y) && Number.isFinite(loc.z),
          `${id} at ${loc.x},${loc.y},${loc.z}`);
  },
  playSound() { }, getEntities() { return []; },
};
const origin = { x: 10, y: 70, z: -4 };
for (const d of dirs) {
  fxArc(spy, "kaiju8:slash_air", origin, d, 3.2, 170, 9);
  fxSpiral(spy, "kaiju8:seam_glow", origin, d, 8, 2.5, 14, 1.1);
  fxColumn(spy, "kaiju8:seam_glow", origin, 6, 8);
  fxCone(spy, "kaiju8:muzzle_flash", origin, d, 9, 0.35, 10);
  fxWall(spy, "kaiju8:slash_air", origin, d, 4, 5, 3, 5, 3);
}
check("the shape helpers emitted particles", emitted > 200, String(emitted));

// 弧は原点から等距離に並ぶこと（半径が崩れていない）
const radii = [];
fxArc({ spawnParticle(_id, loc) {
  radii.push(Math.hypot(loc.x - origin.x, loc.y - origin.y, loc.z - origin.z));
} }, "x", origin, { x: 0, y: 0, z: 1 }, 3.2, 170, 9);
check("every point on the arc sits on its radius",
      radii.every((r) => Math.abs(r - 3.2) < 1e-6), radii.join(","));

let staged = 0;
sequence([[0, () => staged++], [2, () => staged++], [5, () => staged++]]);
check("sequence runs its first stage immediately", staged === 1);
globalThis.__pending.splice(0).forEach((f) => f());
check("sequence queues the later stages", staged === 3, String(staged));

trail({ dimension: spy, location: origin }, "kaiju8:afterimage", 8, 2);
check("trail queues one emission per step",
      globalThis.__pending.length === 4, String(globalThis.__pending.length));
globalThis.__pending.splice(0).forEach((f) => f());

// ----------------------------------------- 10. 味方隊員の二種類の技
import { ALLY_TECH } from "./kaiju.js";

const fakeKaiju = {
  id: "k1", typeId: "kaiju8:yoju", dimension: spy,
  location: { x: 14, y: 70, z: -1 },
  getComponent(n) {
    if (n === "minecraft:type_family") {
      return { hasTypeFamily: (f) => f === "kaiju", getTypeFamilies: () => ["kaiju"] };
    }
    return undefined;
  },
  applyDamage() { return true; }, addEffect() { },
};
let allyTechs = 0;
for (const [id, spec] of Object.entries(ALLY_TECH)) {
  check(`${id} has a 一の型`, typeof spec.one === "function");
  check(`${id} has a 二の型`, typeof spec.two === "function");
  check(`${id} declares range and cooldown`,
        typeof spec.range === "number" && typeof spec.cd === "number");
  const ally = {
    id: `a-${id}`, typeId: id, dimension: spy,
    location: { x: 10, y: 70, z: -4 },
    getViewDirection() { return { x: 1, y: 0, z: 0 }; },
    getHeadLocation() { return { x: 10, y: 71.6, z: -4 }; },
    getComponent() { return undefined; },
    applyDamage() { }, addEffect() { }, runCommand() { }, triggerEvent() { },
  };
  for (const which of ["one", "two"]) {
    allyTechs++;
    try { spec[which](ally, fakeKaiju); } catch (e) {
      check(`${id}.${which} runs`, false, String(e));
    }
  }
}
for (let i = 0; i < 4; i++) {
  globalThis.__pending.splice(0).forEach((f) => { try { f(); } catch (e) {
    check("a queued ally callback throws", false, String(e));
  } });
}
check("both 型 of every ally ran", allyTechs === Object.keys(ALLY_TECH).length * 2);

// ------------------------------------------------ 11. release-rate ceilings
check("release rate is capped without the suit", releaseRate(bare) <= 100);
check("release rate is a number", Number.isFinite(releaseRate(worn)));

console.log(`  ${techCount} techniques, ${Object.keys(NUMBERS).length} machines, `
            + `${combos} weapon x machine wheels, ${allyTechs} ally 型 exercised`);
if (failures) {
  console.log(`  ${failures} assertion(s) failed`);
  process.exit(1);
}
console.log("  behaviour tests passed");
"""


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="kaiju8-logic-")
    try:
        with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as fh:
            json.dump({"name": "kaiju8-test", "type": "module"}, fh)
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
