# -*- coding: utf-8 -*-
"""超次元バトルアーツ: 全アセットを生成 → 挙動テスト → めり込み検査 → 参照検証 → dist/ に書き出し。"""
from __future__ import annotations

import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hd_common import BP, ROOT, RP  # noqa: E402

VERSION = "1.1.0"
NAME = "HyperDimensionArts"
DIST = os.path.join(ROOT, "dist")

STEPS = ["gen_hd_weapons.py", "gen_hd_anim.py", "gen_hd_particles.py", "gen_hd_sounds.py",
         "gen_hd_packs.py"]


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
    run("test_hd.py")
    run("check_hd_clip.py")     # 武器が体にめり込むモーションが無いこと
    run("validate_hd.py")
    os.makedirs(DIST, exist_ok=True)
    for f in os.listdir(DIST):
        if f.startswith(NAME):
            os.remove(os.path.join(DIST, f))
    addon = os.path.join(DIST, f"{NAME}_v{VERSION}.mcaddon")
    with zipfile.ZipFile(addon, "w", zipfile.ZIP_DEFLATED) as zf:
        zip_dir(zf, BP, "hyperdim_BP")
        zip_dir(zf, RP, "hyperdim_RP")
    for folder, suffix in ((BP, "BP"), (RP, "RP")):
        with zipfile.ZipFile(os.path.join(DIST, f"{NAME}_{suffix}_v{VERSION}.mcpack"), "w",
                             zipfile.ZIP_DEFLATED) as zf:
            zip_dir(zf, folder, "")
    print("\n=== dist ===")
    for f in sorted(os.listdir(DIST)):
        if f.startswith(NAME):
            print(f"  {f:44s} {os.path.getsize(os.path.join(DIST, f)) / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
