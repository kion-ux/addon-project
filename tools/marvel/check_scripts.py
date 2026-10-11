"""Loads the behaviour-pack scripts against stubbed Minecraft modules.

`node --check` silently ignores ES-module syntax in .js files, so instead we
copy the scripts into a temporary ESM package with proxy stubs for
@minecraft/server and actually import them.  That catches syntax errors,
unresolved relative imports, missing named exports and top-level crashes.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "packs", "marvel_BP", "scripts")

STUB = """
const handler = {
  get(target, prop) {
    if (prop === Symbol.toPrimitive || prop === Symbol.iterator) return undefined;
    if (prop === "then") return undefined;
    if (!target.__cache) target.__cache = new Map();
    if (!target.__cache.has(prop)) target.__cache.set(prop, make());
    return target.__cache.get(prop);
  },
  set() { return true; },
  apply() { return make(); },
  construct() { return make(); },
  has() { return true; },
};
function make() { return new Proxy(function stub() {}, handler); }
export const world = make();
export const system = make();
export const ItemStack = make();
export const EquipmentSlot = make();
export const GameMode = make();
export const EntityComponentTypes = make();
export const ItemComponentTypes = make();
export const BlockComponentTypes = make();
export const BlockPermutation = make();
export const BlockTypes = make();
export const MolangVariableMap = make();
export const EntityDamageCause = make();
export const Direction = make();
export const DisplaySlotId = make();
export const ObjectiveSortOrder = make();
export const EasingType = make();
export const HudElement = make();
export const HudVisibility = make();
export const InputPermissionCategory = make();
export const EntityQueryOptions = make();
export const Dimension = make();
export const Player = make();
export const Entity = make();
export const Vector3 = make();
export const TicksPerSecond = 20;
export const ActionFormData = make();
export const ModalFormData = make();
export const MessageFormData = make();
export const FormCancelationReason = make();
export default make();
"""


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="marvel-scripts-")
    try:
        pkg = os.path.join(tmp, "package.json")
        with open(pkg, "w", encoding="utf-8") as fh:
            json.dump({"name": "marvel-check", "type": "module"}, fh)
        for mod in ("@minecraft/server", "@minecraft/server-ui"):
            d = os.path.join(tmp, "node_modules", *mod.split("/"))
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.js"), "w", encoding="utf-8") as fh:
                fh.write(STUB)
            with open(os.path.join(d, "package.json"), "w", encoding="utf-8") as fh:
                json.dump({"name": mod, "version": "1.0.0", "type": "module",
                           "main": "index.js"}, fh)

        names = []
        for f in sorted(os.listdir(SCRIPTS)):
            if f.endswith(".js"):
                shutil.copy(os.path.join(SCRIPTS, f), os.path.join(tmp, f))
                names.append(f)

        entry = os.path.join(tmp, "__check.js")
        with open(entry, "w", encoding="utf-8") as fh:
            for f in names:
                fh.write(f'import "./{f}";\n')
            fh.write('console.log("scripts loaded: %d modules");\n' % len(names))

        res = subprocess.run([sys.executable and "node", entry],
                             capture_output=True, text=True)
        if res.stdout.strip():
            print("  " + res.stdout.strip())
        if res.returncode:
            print(res.stderr.strip()[:4000])
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
