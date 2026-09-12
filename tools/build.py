"""Regenerates every asset, validates, then zips each add-on into dist/.

This repository ships two add-ons built on one toolchain:

    Kaiju No.8            packs/kaiju8_BP + packs/kaiju8_RP
    GRAND LINE AWAKENING  packs/gla_BP    + packs/gla_RP   (ワンピース / 非公式)

Add a third by appending to PROJECTS.  Everything else here is generic.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
DIST = os.path.join(ROOT, "dist")

PROJECTS = [
    dict(
        name="KaijuNo8",
        version="1.0.0",
        bp="kaiju8_BP",
        rp="kaiju8_RP",
        steps=["gen_weapons.py", "gen_entities.py", "gen_particles.py",
               "gen_anim.py", "gen_client_entities.py", "gen_items.py",
               "gen_bp.py", "gen_lang.py"],
    ),
    dict(
        name="GrandLineAwakening",
        version="1.0.0",
        bp="gla_BP",
        rp="gla_RP",
        # spec -> モデル -> アニメ -> 粒子 -> 表示 -> BP -> 実行時テーブル -> 言語。
        # 後段が前段の出力（geometry 名やアニメ ID）を参照するので順序は固定。
        steps=["gla/gen_models.py", "gla/gen_anim.py", "gla/gen_particles.py",
               "gla/gen_client.py", "gla/gen_bp.py", "gla/gen_data.py",
               "gla/gen_lang.py", "gla/gen_docs.py"],
    ),
]


def run(script):
    print(f"\n=== {script} ===")
    res = subprocess.run([sys.executable, os.path.join(TOOLS, script)], cwd=ROOT)
    if res.returncode:
        sys.exit(res.returncode)


def tool(script, *args):
    return subprocess.run([sys.executable, os.path.join(TOOLS, script), *args],
                          cwd=ROOT).returncode


def zip_dir(zf, folder, arc_root):
    for base, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.endswith((".pyc", ".DS_Store")):
                continue
            full = os.path.join(base, f)
            arc = os.path.join(arc_root, os.path.relpath(full, folder))
            zf.write(full, arc.replace(os.sep, "/"))


def package(project):
    name = project["name"]
    version = project["version"]
    bp = os.path.join(ROOT, "packs", project["bp"])
    rp = os.path.join(ROOT, "packs", project["rp"])

    addon = os.path.join(DIST, f"{name}_v{version}.mcaddon")
    with zipfile.ZipFile(addon, "w", zipfile.ZIP_DEFLATED) as zf:
        zip_dir(zf, bp, project["bp"])
        zip_dir(zf, rp, project["rp"])

    for folder, suffix in ((bp, "BP"), (rp, "RP")):
        path = os.path.join(DIST, f"{name}_{suffix}_v{version}.mcpack")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zip_dir(zf, folder, "")


def main():
    for project in PROJECTS:
        print(f"\n########## {project['name']} ##########")
        for step in project["steps"]:
            run(step)

    print("\n=== check scripts ===")
    if tool("check_scripts.py"):
        sys.exit(1)

    print("\n=== behaviour tests ===")
    for suite in ("test_logic.py", "gla/test_logic.py"):
        if tool(suite):
            sys.exit(1)

    print("\n=== validate ===")
    if tool("validate.py"):
        sys.exit(1)

    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(DIST, exist_ok=True)
    for project in PROJECTS:
        package(project)

    print("\n=== dist ===")
    for f in sorted(os.listdir(DIST)):
        size = os.path.getsize(os.path.join(DIST, f))
        print(f"  {f:42s} {size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
