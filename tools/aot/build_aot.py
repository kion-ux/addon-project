# -*- coding: utf-8 -*-
"""進撃の巨人アドオン: 全アセットを生成 → 挙動テスト → 参照検証 → dist/ に書き出し。"""
from __future__ import annotations

import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from aot_common import BP, ROOT, RP, VERSION  # noqa: E402

NAME = "AttackOnTitan"
DIST = os.path.join(ROOT, "dist")
STEPS = ["aot_models.py", "gen_aot_anim.py", "gen_aot_particles.py", "gen_aot_sounds.py",
         "gen_aot_packs.py", "aot_lang.py"]


def run(script):
    print(f"\n=== {script} ===")
    if subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=ROOT).returncode:
        sys.exit(1)


def zip_dir(zf, folder, arc_root):
    for base, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.endswith((".pyc", ".DS_Store")):
                continue
            full = os.path.join(base, f)
            arc = os.path.join(arc_root, os.path.relpath(full, folder))
            zf.write(full, arc.replace(os.sep, "/"))


def main():
    for s in STEPS:
        run(s)
    run("test_aot.py")
    run("validate_aot.py")
    ver = ".".join(map(str, VERSION))
    os.makedirs(DIST, exist_ok=True)
    for f in os.listdir(DIST):
        if f.startswith(NAME):
            os.remove(os.path.join(DIST, f))
    with zipfile.ZipFile(os.path.join(DIST, f"{NAME}_v{ver}.mcaddon"), "w", zipfile.ZIP_DEFLATED) as zf:
        zip_dir(zf, BP, "aot_BP")
        zip_dir(zf, RP, "aot_RP")
    for folder, suffix in ((BP, "BP"), (RP, "RP")):
        with zipfile.ZipFile(os.path.join(DIST, f"{NAME}_{suffix}_v{ver}.mcpack"), "w",
                             zipfile.ZIP_DEFLATED) as zf:
            zip_dir(zf, folder, "")
    print("\n=== dist ===")
    for f in sorted(os.listdir(DIST)):
        if f.startswith(NAME):
            print(f"  {f:40s} {os.path.getsize(os.path.join(DIST, f)) / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
