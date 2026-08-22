"""Regenerates every asset, validates, then zips the packs into dist/."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
DIST = os.path.join(ROOT, "dist")
VERSION = "1.0.0"
NAME = "KaijuNo8"

STEPS = ["gen_entities.py", "gen_client_entities.py", "gen_items.py",
         "gen_bp.py", "gen_lang.py"]


def run(script):
    print(f"\n=== {script} ===")
    res = subprocess.run([sys.executable, os.path.join(TOOLS, script)], cwd=ROOT)
    if res.returncode:
        sys.exit(res.returncode)


def zip_dir(zf, folder, arc_root):
    for base, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.endswith((".pyc", ".DS_Store")):
                continue
            full = os.path.join(base, f)
            arc = os.path.join(arc_root, os.path.relpath(full, folder))
            zf.write(full, arc.replace(os.sep, "/"))


def main():
    for step in STEPS:
        run(step)
    print("\n=== check scripts ===")
    if subprocess.run([sys.executable, os.path.join(TOOLS, "check_scripts.py")],
                      cwd=ROOT).returncode:
        sys.exit(1)

    print("\n=== validate ===")
    if subprocess.run([sys.executable, os.path.join(TOOLS, "validate.py")], cwd=ROOT).returncode:
        sys.exit(1)

    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(DIST, exist_ok=True)
    bp = os.path.join(ROOT, "packs", "kaiju8_BP")
    rp = os.path.join(ROOT, "packs", "kaiju8_RP")

    addon = os.path.join(DIST, f"{NAME}_v{VERSION}.mcaddon")
    with zipfile.ZipFile(addon, "w", zipfile.ZIP_DEFLATED) as zf:
        zip_dir(zf, bp, "kaiju8_BP")
        zip_dir(zf, rp, "kaiju8_RP")

    for folder, suffix in ((bp, "BP"), (rp, "RP")):
        path = os.path.join(DIST, f"{NAME}_{suffix}_v{VERSION}.mcpack")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zip_dir(zf, folder, "")

    print("\n=== dist ===")
    for f in sorted(os.listdir(DIST)):
        size = os.path.getsize(os.path.join(DIST, f))
        print(f"  {f:34s} {size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
