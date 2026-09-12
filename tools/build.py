"""Regenerates every asset, validates, then zips each add-on into dist/.

This repository ships two add-ons built on one toolchain:

    Kaiju No.8            packs/kaiju8_BP + packs/kaiju8_RP
    GRAND LINE AWAKENING  packs/gla_BP    + packs/gla_RP   (ワンピース / 非公式)

Add a third by appending to PROJECTS.  Everything else here is generic.
"""
from __future__ import annotations

import hashlib
import json
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


def content_hash(folder):
    """パックの中身だけのハッシュ。zip の mtime に左右されないので、
    同じ中身なら何度ビルドしても同じ値になる。"""
    h = hashlib.sha256()
    for base, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.endswith((".pyc", ".DS_Store")):
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            h.update(rel.encode("utf-8"))
            with open(full, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def release_record():
    """基準版の記録（企画書 §18）。

    「配布ファイル名、ハッシュ値、BP/RPのUUIDと版、Minecraft本体版」を残す。
    実機名・設定・確認日・確認者・合格したQA項目は、実機で確認した人が
    このファイルに追記する欄として空けてある — ここで埋めると、
    確認していないことを確認済みとして書くことになる。
    """
    rows = []
    for project in PROJECTS:
        bp = os.path.join(ROOT, "packs", project["bp"])
        rp = os.path.join(ROOT, "packs", project["rp"])
        bpm = json.load(open(os.path.join(bp, "manifest.json"), encoding="utf-8"))
        rpm = json.load(open(os.path.join(rp, "manifest.json"), encoding="utf-8"))
        rows.append(dict(
            name=project["name"], version=project["version"],
            bp_uuid=bpm["header"]["uuid"], rp_uuid=rpm["header"]["uuid"],
            engine=".".join(str(v) for v in bpm["header"]["min_engine_version"]),
            modules=[d for d in bpm.get("dependencies", []) if "module_name" in d],
            bp_hash=content_hash(bp), rp_hash=content_hash(rp),
            files=sorted(f for f in os.listdir(DIST)
                         if f.startswith(project["name"] + "_")),
        ))

    lines = ["# 基準版の記録 / Release record", "",
             "企画書 §18「基準版の記録」。中身のハッシュは zip の時刻に",
             "左右されないので、同じ中身なら何度ビルドしても同じ値になる。", ""]
    for r in rows:
        lines += [f"## {r['name']} v{r['version']}", "",
                  "| 項目 | 値 |", "|---|---|",
                  f"| Minecraft 本体版 (min_engine_version) | {r['engine']} |",
                  f"| BP UUID | `{r['bp_uuid']}` |",
                  f"| RP UUID | `{r['rp_uuid']}` |"]
        for m in r["modules"]:
            lines.append(f"| {m['module_name']} | {m['version']} |")
        lines += [f"| BP 中身のハッシュ (sha256) | `{r['bp_hash']}` |",
                  f"| RP 中身のハッシュ (sha256) | `{r['rp_hash']}` |", ""]
        lines.append("配布ファイル:")
        lines.append("")
        for f in r["files"]:
            size = os.path.getsize(os.path.join(DIST, f))
            lines.append(f"- `{f}` ({size / 1024:.1f} KB)")
        lines += ["", "### 実機での確認欄（未記入）", "",
                  "| 項目 | 記入する内容 |", "|---|---|",
                  "| 実機名 / OS | |", "| 本体版（タイトル画面の表示） | |",
                  "| 画質・描画距離の設定 | |", "| 確認日 | |", "| 確認者 | |",
                  "| 合格した QA 項目 | |", "| 再現した不具合 | |", "",
                  "この欄が空のうちは、実機での確認は行われていない。", ""]
    with open(os.path.join(DIST, "RELEASE_RECORD.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("  RELEASE_RECORD.md")


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
    release_record()

    print("\n=== dist ===")
    for f in sorted(os.listdir(DIST)):
        size = os.path.getsize(os.path.join(DIST, f))
        print(f"  {f:42s} {size / 1024:8.1f} KB")


if __name__ == "__main__":
    main()
