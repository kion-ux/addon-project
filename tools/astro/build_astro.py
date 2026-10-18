# -*- coding: utf-8 -*-
"""アストロ・ナノギア: 全アセットを生成 → 挙動テスト → スーツ検査 → 参照検証 → dist/ に書き出し。"""
from __future__ import annotations

import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import astro_data as D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
BP = os.path.join(ROOT, "packs", "astro_BP")
RP = os.path.join(ROOT, "packs", "astro_RP")
DIST = os.path.join(ROOT, "dist")
NAME = "AstroNanogear"
VERSION = ".".join(map(str, D.VERSION))

# 生成の順番: モデル（アイコンも描く）→ アニメ → パーティクル → 音 → UI → 敵 → パックの表
STEPS = ["gen_astro_suits.py", "gen_astro_weapons.py", "gen_astro_anim.py", "gen_astro_particles.py",
         "gen_astro_sounds.py", "gen_astro_ui.py", "gen_astro_entities.py", "gen_astro_packs.py"]
CHECKS = ["test_astro.py", "check_astro_suits.py", "validate_astro.py"]


def run(script, *args):
    print(f"\n=== {script} {' '.join(args)} ===", flush=True)
    if subprocess.run([sys.executable, os.path.join(HERE, script), *args], cwd=ROOT).returncode:
        print(f"!!! {script} failed")
        sys.exit(1)


def zip_dir(zf, folder, arc_root):
    for base, dirs, files in os.walk(folder):
        dirs.sort()
        for f in sorted(files):
            if f.endswith((".pyc", ".DS_Store")):
                continue
            full = os.path.join(base, f)
            arc = os.path.join(arc_root, os.path.relpath(full, folder))
            zf.write(full, arc.replace(os.sep, "/"))


def main():
    skip_gen = "--no-gen" in sys.argv
    if not skip_gen:
        for s in STEPS:
            run(s)
    for s in CHECKS:
        run(s)
    os.makedirs(DIST, exist_ok=True)
    for f in os.listdir(DIST):
        if f.startswith(NAME):
            os.remove(os.path.join(DIST, f))
    addon = os.path.join(DIST, f"{NAME}_v{VERSION}.mcaddon")
    with zipfile.ZipFile(addon, "w", zipfile.ZIP_DEFLATED) as zf:
        zip_dir(zf, BP, "astro_BP")
        zip_dir(zf, RP, "astro_RP")
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
