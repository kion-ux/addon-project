# -*- coding: utf-8 -*-
"""超次元バトルアーツの参照整合性チェック。

ジオメトリ・テクスチャ・アニメーション・パーティクル・効果音・アイコン・言語キー・
レシピ・マニフェストが、互いに実在するものだけを指しているかを全件調べる。
加えて UV が貼り先のテクスチャからはみ出していないか、Molang の括弧が閉じているかも見る。
"""
from __future__ import annotations

import json
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hd_common import BP, RP  # noqa: E402

errors: list[str] = []


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def walk(root, suffix=".json"):
    for base, _d, files in os.walk(root):
        for f in files:
            if f.endswith(suffix):
                yield os.path.join(base, f)


def rel(p):
    return os.path.relpath(p, os.path.dirname(BP))


def tex_exists(path):
    return any(os.path.exists(os.path.join(RP, path + ext)) for ext in (".png", ".tga"))


MOLANG_KEYS = re.compile(r"(q\.|v\.|c\.|math\.|query\.|variable\.)")


def molang_strings(obj):
    if isinstance(obj, str):
        if MOLANG_KEYS.search(obj):
            yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from molang_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from molang_strings(v)


def check_molang(where, doc):
    for s in molang_strings(doc):
        depth = 0
        for ch in s:
            depth += ch == "("
            depth -= ch == ")"
            if depth < 0:
                break
        if depth != 0:
            errors.append(f"{where}: unbalanced molang: {s[:80]}")
        if re.search(r"[^=!<>]=[^=]", s.replace("??", "")) and ";" not in s:
            errors.append(f"{where}: suspicious assignment in expression: {s[:80]}")


def main() -> int:
    for pack in (BP, RP):
        for p in walk(pack):
            try:
                load(p)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"invalid json {rel(p)}: {exc}")
    if errors:
        print("\n".join("ERROR " + e for e in errors))
        return 1

    # ---- ジオメトリ ----------------------------------------------------
    geos = {}
    for p in walk(os.path.join(RP, "models")):
        for g in load(p)["minecraft:geometry"]:
            d = g["description"]
            geos[d["identifier"]] = (d["texture_width"], d["texture_height"], g, p)
    for ident, (tw, th, g, p) in geos.items():
        names = set()
        for b in g.get("bones", []):
            if b["name"] in names:
                errors.append(f"{ident}: duplicate bone {b['name']}")
            names.add(b["name"])
        for b in g.get("bones", []):
            if b.get("parent") and b["parent"] not in names:
                errors.append(f"{ident}: bone {b['name']} has missing parent {b['parent']}")
            for c in b.get("cubes", []):
                uv = c.get("uv")
                if isinstance(uv, dict):
                    for face, f in uv.items():
                        u, v = f["uv"]
                        w, h = f["uv_size"]
                        if u < 0 or v < 0 or u + w > tw or v + h > th:
                            errors.append(f"{ident}: {b['name']} {face} uv outside {tw}x{th}")

    # ---- アニメーション ------------------------------------------------
    anims = {}
    for p in walk(os.path.join(RP, "animations")):
        doc = load(p)
        check_molang(rel(p), doc)
        for k, v in doc["animations"].items():
            anims[k] = v

    # ---- アタッチャブル --------------------------------------------------
    att_ids = set()
    for p in walk(os.path.join(RP, "attachables")):
        doc = load(p)
        check_molang(rel(p), doc)
        d = doc["minecraft:attachable"]["description"]
        att_ids.add(d["identifier"])
        for g in d["geometry"].values():
            if g not in geos:
                errors.append(f"{rel(p)}: geometry {g} missing")
        for t in d["textures"].values():
            if not t.startswith("textures/misc/") and not tex_exists(t):
                errors.append(f"{rel(p)}: texture {t} missing")
        tex = d["textures"]["default"]
        geo = geos.get(d["geometry"]["default"])
        if geo and tex_exists(tex):
            im = Image.open(os.path.join(RP, tex + ".png"))
            if im.size != (geo[0], geo[1]):
                errors.append(f"{rel(p)}: texture {im.size} != geometry {geo[0]}x{geo[1]}")
        for short, a in d["animations"].items():
            if a not in anims:
                errors.append(f"{rel(p)}: animation {a} missing")
        for entry in d["scripts"]["animate"]:
            key = entry if isinstance(entry, str) else list(entry)[0]
            if key not in d["animations"]:
                errors.append(f"{rel(p)}: animate refers to unknown key {key}")
        # アニメーションが触るボーンがジオメトリにあるか
        if geo:
            bones = {b["name"] for b in geo[2]["bones"]}
            for a in d["animations"].values():
                for bone in anims.get(a, {}).get("bones", {}):
                    if bone not in bones:
                        errors.append(f"{rel(p)}: {a} animates missing bone {bone}")

    # ---- クライアントエンティティ ---------------------------------------
    for p in walk(os.path.join(RP, "entity")):
        d = load(p)["minecraft:client_entity"]["description"]
        for g in d["geometry"].values():
            if g not in geos:
                errors.append(f"{rel(p)}: geometry {g} missing")
        for t in d["textures"].values():
            if not tex_exists(t):
                errors.append(f"{rel(p)}: texture {t} missing")
        for a in d.get("animations", {}).values():
            if a not in anims:
                errors.append(f"{rel(p)}: animation {a} missing")

    # ---- パーティクル ------------------------------------------------
    for p in walk(os.path.join(RP, "particles")):
        doc = load(p)
        check_molang(rel(p), doc)
        pe = doc["particle_effect"]
        t = pe["description"]["basic_render_parameters"]["texture"]
        if not tex_exists(t):
            errors.append(f"{rel(p)}: texture {t} missing")
        bb = pe["components"].get("minecraft:particle_appearance_billboard", {})
        uv = bb.get("uv", {})
        if "uv" in uv and all(isinstance(x, (int, float)) for x in uv["uv"]):
            if uv["uv"][0] + uv["uv_size"][0] > uv["texture_width"] or uv["uv"][1] + uv["uv_size"][1] > uv["texture_height"]:
                errors.append(f"{rel(p)}: uv outside atlas")

    # ---- 効果音 --------------------------------------------------------
    sd = load(os.path.join(RP, "sounds", "sound_definitions.json"))["sound_definitions"]
    for k, v in sd.items():
        for s in v["sounds"]:
            name = s["name"] if isinstance(s, dict) else s
            if not any(os.path.exists(os.path.join(RP, name + ext)) for ext in (".ogg", ".wav", ".fsb")):
                errors.append(f"sound {k}: file {name} missing")

    # ---- アイテム ------------------------------------------------------
    atlas = load(os.path.join(RP, "textures", "item_texture.json"))["texture_data"]
    for k, v in atlas.items():
        if not tex_exists(v["textures"]):
            errors.append(f"item_texture {k}: {v['textures']} missing")
    langs = {}
    for f in os.listdir(os.path.join(RP, "texts")):
        if f.endswith(".lang"):
            langs[f] = {ln.split("=", 1)[0] for ln in open(os.path.join(RP, "texts", f), encoding="utf-8") if "=" in ln}
    item_ids = set()
    for p in walk(os.path.join(BP, "items")):
        it = load(p)["minecraft:item"]
        ident = it["description"]["identifier"]
        item_ids.add(ident)
        icon = it["components"]["minecraft:icon"]["texture"]
        if icon not in atlas:
            errors.append(f"{rel(p)}: icon {icon} not in item_texture.json")
        key = it["components"].get("minecraft:display_name", {}).get("value")
        for lf, keys in langs.items():
            if key and key not in keys:
                errors.append(f"{lf}: missing {key}")
    for ident in item_ids:
        if ident.split(":")[1] in ("dimension_crystal", "guide"):
            continue
        if ident not in att_ids:
            errors.append(f"weapon {ident} has no attachable")
    for p in walk(os.path.join(BP, "recipes")):
        doc = load(p)
        for v in json.dumps(doc).split('"'):
            if v.startswith("hd:") and ":" in v and v not in item_ids and not v.startswith("hd:guide") \
                    and v not in {f"hd:{os.path.basename(p)[:-5]}"}:
                errors.append(f"{rel(p)}: unknown item {v}")
    for p in walk(os.path.join(BP, "entities")):
        ident = load(p)["minecraft:entity"]["description"]["identifier"]
        if not os.path.exists(os.path.join(RP, "entity", ident.split(":")[1] + ".entity.json")):
            errors.append(f"{ident}: no client entity")
        for lf, keys in langs.items():
            if f"entity.{ident}.name" not in keys:
                errors.append(f"{lf}: missing entity.{ident}.name")

    # ---- マニフェスト ---------------------------------------------------
    bm, rm = load(os.path.join(BP, "manifest.json")), load(os.path.join(RP, "manifest.json"))
    if not any(d.get("uuid") == rm["header"]["uuid"] for d in bm["dependencies"]):
        errors.append("BP manifest does not depend on RP")
    if not any(d.get("uuid") == bm["header"]["uuid"] for d in rm["dependencies"]):
        errors.append("RP manifest does not depend on BP")
    for p in (BP, RP):
        if not os.path.exists(os.path.join(p, "pack_icon.png")):
            errors.append(f"{rel(p)}: pack_icon.png missing")

    for e in errors:
        print("ERROR", e)
    print(f"  validate: {len(geos)} geometries, {len(anims)} animations, {len(att_ids)} attachables, "
          f"{len(sd)} sounds, {len(item_ids)} items — {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
