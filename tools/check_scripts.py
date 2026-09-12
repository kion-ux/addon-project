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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#  このリポジトリは1つのツールチェインで2つのアドオンを作るので、
#  スクリプトの読み込み確認も両方に掛ける。
SCRIPT_DIRS = [
    ("Kaiju No.8", os.path.join(ROOT, "packs", "kaiju8_BP", "scripts")),
    ("GRAND LINE AWAKENING", os.path.join(ROOT, "packs", "gla_BP", "scripts")),
]

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
export const ActionFormData = make();
export const ModalFormData = make();
export const MessageFormData = make();
export default make();
"""


def check(label: str, scripts: str) -> int:
    if not os.path.isdir(scripts):
        # 一覧に載っているのにスクリプトが無いのは、黙って通してよい状態ではない
        print(f"  {label}: ERROR スクリプトが見つからない ({scripts})")
        return 1
    tmp = tempfile.mkdtemp(prefix="addon-scripts-")
    try:
        pkg = os.path.join(tmp, "package.json")
        with open(pkg, "w", encoding="utf-8") as fh:
            json.dump({"name": "addon-check", "type": "module"}, fh)
        for mod in ("@minecraft/server", "@minecraft/server-ui"):
            d = os.path.join(tmp, "node_modules", *mod.split("/"))
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.js"), "w", encoding="utf-8") as fh:
                fh.write(STUB)
            with open(os.path.join(d, "package.json"), "w", encoding="utf-8") as fh:
                json.dump({"name": mod, "version": "1.0.0", "type": "module",
                           "main": "index.js"}, fh)

        names = []
        for f in sorted(os.listdir(scripts)):
            if f.endswith(".js"):
                shutil.copy(os.path.join(scripts, f), os.path.join(tmp, f))
                names.append(f)

        entry = os.path.join(tmp, "__check.js")
        with open(entry, "w", encoding="utf-8") as fh:
            for f in names:
                fh.write(f'import "./{f}";\n')
            fh.write('console.log("%s: %d modules loaded");\n'
                     % (label, len(names)))

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


def main() -> int:
    bad = 0
    for label, scripts in SCRIPT_DIRS:
        bad |= check(label, scripts)
    return bad


if __name__ == "__main__":
    sys.exit(main())
