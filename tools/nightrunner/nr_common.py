# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 生成スクリプト共通の定数・パス・書き出し補助。

約束事は tools/nightrunner/DESIGN.md。ここの定数を変えるときは DESIGN.md も直す。
"""
from __future__ import annotations

import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)

NS = "nr"
NAME = "NightRunner"
VERSION = "1.0.0"
VERSION_TUPLE = [1, 0, 0]
MIN_ENGINE = [1, 21, 120]
SERVER_API = "2.3.0"
SERVER_UI_API = "2.0.0"

BP = os.path.join(ROOT, "packs", "nightrunner_BP")
RP = os.path.join(ROOT, "packs", "nightrunner_RP")
DIST = os.path.join(ROOT, "dist")
SCRIPTS = os.path.join(BP, "scripts")
DATA_JS = os.path.join(SCRIPTS, "data")
FRAG = os.path.join(HERE, ".frag")
SCRATCH = os.environ.get("NR_SCRATCH", os.path.join(ROOT, "build_preview", "nightrunner"))
PREVIEW = os.environ.get("NR_PREVIEW") == "1"

# 断片をまとめる登録ファイルの名前（DESIGN.md §1）
FRAG_KINDS = ("item_texture", "terrain_texture", "sound_definitions", "blocks", "flipbook",
              "lang", "sounds_json")


def write_json(path: str, doc, indent: int = 2) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=indent, ensure_ascii=False)
        fh.write("\n")


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def frag(kind: str, producer: str, doc) -> None:
    """共有の登録ファイルへの断片を書く（gen_nr_packs.py が最後にまとめる）。

    kind は FRAG_KINDS のどれか、producer は書いた生成器の名前（例 "gen_nr_weapons"）。
    lang の断片は {"ja_JP": {...}, "en_US": {...}}、flipbook はリスト、他は辞書。
    """
    if kind not in FRAG_KINDS:
        raise ValueError(f"unknown frag kind {kind}")
    write_json(os.path.join(FRAG, kind, f"{producer}.json"), doc)


def read_frags(kind: str):
    """kind の断片をすべて読む。[(producer, doc), ...]（名前順）。"""
    folder = os.path.join(FRAG, kind)
    if not os.path.isdir(folder):
        return []
    return [(f[:-5], load_json(os.path.join(folder, f)))
            for f in sorted(os.listdir(folder)) if f.endswith(".json")]


def stable_hash(text) -> int:
    """プロセスをまたいで同じ値になるハッシュ（組み込み hash() は使わない）。"""
    return zlib.crc32(str(text).encode("utf-8"))


def rp_path(*parts) -> str:
    return os.path.join(RP, *parts)


def bp_path(*parts) -> str:
    return os.path.join(BP, *parts)


def js_literal(obj) -> str:
    """Python の値を JS のリテラルに（scripts/data/*.js 用）。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def write_data_js(name: str, exports: dict, header: str = "") -> None:
    """scripts/data/<name>.js を書く。exports は {名前: 値}。"""
    lines = ["// このファイルは生成物です（tools/nightrunner/）。直接編集しないでください。"]
    if header:
        lines += ["// " + h for h in header.splitlines()]
    for k, v in exports.items():
        lines.append(f"export const {k} = {js_literal(v)};")
    write_text(os.path.join(DATA_JS, f"{name}.js"), "\n".join(lines) + "\n")


GEOMETRY_FORMAT = "1.16.0"   # binding は 1.16.0 から（reference/rendering.md §6.1）


def geometry_doc(*models) -> dict:
    """mcmodel.Model（と NRModel）を 1.16.0 の geometry ファイルの中身にする。"""
    geos = []
    for m in models:
        if not m.tex_w:
            m.pack()
        geos.append(m.to_json())
    return {"format_version": GEOMETRY_FORMAT, "minecraft:geometry": geos}


def write_geometry(path: str, *models) -> None:
    """NR のジオメトリは全部これで書く（mcmodel.Model.write は 1.12.0 固定なので使わない）。"""
    write_json(path, geometry_doc(*models))
