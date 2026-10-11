# -*- coding: utf-8 -*-
"""全アセットを生成し、検証し、dist/ に .mcaddon / .mcpack を書き出す。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DIST = os.path.join(ROOT, "dist")
VERSION = "1.0.0"
NAME = "MarvelMutants"

#: 生成順は依存関係の順。モデル -> パーティクル -> アニメ -> 参照 JSON。
STEPS = [
    "gen_config.py",
    "gen_models_magneto.py",
    "gen_models_brotherhood.py",
    "gen_models_enemies.py",
    "gen_particles.py",
    "gen_anim_loco.py",
    "gen_anim_tech.py",
    "gen_client.py",
    "gen_bp.py",
    "gen_lang.py",
]


def run(script: str) -> None:
    print(f"\n=== {script} ===")
    res = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=ROOT)
    if res.returncode:
        sys.exit(res.returncode)


def zip_dir(zf: zipfile.ZipFile, folder: str, arc_root: str) -> None:
    for base, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.endswith((".pyc", ".DS_Store")):
                continue
            full = os.path.join(base, f)
            arc = os.path.join(arc_root, os.path.relpath(full, folder))
            zf.write(full, arc.replace(os.sep, "/"))


def main() -> None:
    for step in STEPS:
        run(step)

    print("\n=== check scripts ===")
    if subprocess.run([sys.executable, os.path.join(HERE, "check_scripts.py")],
                      cwd=ROOT).returncode:
        sys.exit(1)

    print("\n=== validate ===")
    if subprocess.run([sys.executable, os.path.join(HERE, "validate.py")],
                      cwd=ROOT).returncode:
        sys.exit(1)

    os.makedirs(DIST, exist_ok=True)
    bp = os.path.join(ROOT, "packs", "marvel_BP")
    rp = os.path.join(ROOT, "packs", "marvel_RP")
    for stale in os.listdir(DIST):
        if stale.startswith(NAME):
            os.remove(os.path.join(DIST, stale))

    addon = os.path.join(DIST, f"{NAME}_v{VERSION}.mcaddon")
    with zipfile.ZipFile(addon, "w", zipfile.ZIP_DEFLATED) as zf:
        zip_dir(zf, bp, "marvel_BP")
        zip_dir(zf, rp, "marvel_RP")

    for folder, suffix in ((bp, "BP"), (rp, "RP")):
        path = os.path.join(DIST, f"{NAME}_{suffix}_v{VERSION}.mcpack")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zip_dir(zf, folder, "")

    print("\n=== dist ===")
    for f in sorted(os.listdir(DIST)):
        if not f.startswith(NAME):
            continue
        size = os.path.getsize(os.path.join(DIST, f))
        print(f"  {f:38s} {size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
