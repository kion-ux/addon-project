# -*- coding: utf-8 -*-
"""参照切れの検査。どれか一つでも見つかればビルドを止める。

* クライアント定義・アタッチャブル → ジオメトリ・テクスチャ・アニメーション・コントローラ・
  レンダーコントローラ・パーティクルが実在するか
* ジオメトリの UV がテクスチャの中に収まっているか、親ボーンが実在するか
* アニメーション／コントローラが、使うジオメトリに無いボーンを動かしていないか（巨人と兵士）
* BP のアイテム → アイコン（item_texture）・言語キー、エンティティ ↔ クライアント定義、
  スポーンルール・レシピの対象が実在するか、イベントが参照するコンポーネントグループがあるか
* スクリプトが使う効果音・パーティクル・翻訳キー・全身モーション（文字列リテラル）が実在するか
* 効果音の .ogg が実在し、音が入っているか（無音でないか）
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

import aot_common as C
from aot_lang import KEYS

errs = []


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rp(*p):
    return os.path.join(C.RP, *p)


def bp(*p):
    return os.path.join(C.BP, *p)


def tex_exists(ref):
    return os.path.exists(rp(ref + ".png")) or os.path.exists(rp(ref + ".tga")) \
        or ref.startswith("textures/misc/")


def main() -> int:
    # ---- ジオメトリ ------------------------------------------------------
    geos = {}
    for f in glob.glob(rp("models", "entity", "*.geo.json")):
        for g in load(f)["minecraft:geometry"]:
            ident = g["description"]["identifier"]
            geos[ident] = g
            names = {b["name"] for b in g["bones"]}
            tw, th = g["description"]["texture_width"], g["description"]["texture_height"]
            for b in g["bones"]:
                if b.get("parent") and b["parent"] not in names:
                    errs.append(f"{ident}: bone {b['name']} has missing parent {b['parent']}")
                for c in b.get("cubes", []):
                    uv = c.get("uv")
                    if isinstance(uv, dict):
                        for face, r in uv.items():
                            u, v = r["uv"]
                            du, dv = r["uv_size"]
                            if u < 0 or v < 0 or u + du > tw or v + dv > th:
                                errs.append(f"{ident}: {b['name']} {face} UV outside {tw}x{th}")
    bones_of = {k: {b["name"] for b in g["bones"]} for k, g in geos.items()}

    # ---- アニメーション ----------------------------------------------------
    anims = {}
    for f in glob.glob(rp("animations", "*.json")):
        anims.update(load(f)["animations"])
    ctrls = {}
    for f in glob.glob(rp("animation_controllers", "*.json")):
        ctrls.update(load(f)["animation_controllers"])
    rcs = {}
    for f in glob.glob(rp("render_controllers", "*.json")):
        rcs.update(load(f)["render_controllers"])
    particles = set()
    for f in glob.glob(rp("particles", "*.json")):
        d = load(f)["particle_effect"]
        particles.add(d["description"]["identifier"])
        tex = d["description"]["basic_render_parameters"]["texture"]
        if not tex_exists(tex):
            errs.append(f"particle {f}: texture {tex} missing")

    def check_desc(name, desc, kind):
        for k, ref in desc.get("textures", {}).items():
            if not tex_exists(ref):
                errs.append(f"{name}: texture {k} -> {ref} missing")
        used_geo = []
        for k, ref in desc.get("geometry", {}).items():
            if ref.startswith("geometry.humanoid"):
                continue
            if ref not in geos:
                errs.append(f"{name}: geometry {ref} missing")
            else:
                used_geo.append(ref)
        for k, ref in desc.get("animations", {}).items():
            if ref.startswith("controller."):
                if ref not in ctrls:
                    errs.append(f"{name}: controller {ref} missing")
                else:
                    for st in ctrls[ref]["states"].values():
                        for a in st.get("animations", []):
                            short = a if isinstance(a, str) else list(a)[0]
                            if short not in desc["animations"]:
                                errs.append(f"{name}: controller {ref} uses '{short}' not declared")
            elif ref not in anims:
                errs.append(f"{name}: animation {ref} missing")
            else:
                for bone in anims[ref].get("bones", {}):
                    if used_geo and not any(bone in bones_of[g] for g in used_geo):
                        errs.append(f"{name}: animation {ref} moves bone '{bone}' not in its geometry")
        for a in desc.get("scripts", {}).get("animate", []):
            short = a if isinstance(a, str) else list(a)[0]
            if short not in desc.get("animations", {}):
                errs.append(f"{name}: animate '{short}' not declared")
        for ref in desc.get("render_controllers", []):
            r = ref if isinstance(ref, str) else list(ref)[0]
            if not r.startswith("controller.render.item_default") and r not in rcs:
                errs.append(f"{name}: render controller {r} missing")
        for k, ref in desc.get("particle_effects", {}).items():
            if ref not in particles:
                errs.append(f"{name}: particle {ref} missing")

    client = {}
    for f in glob.glob(rp("entity", "*.json")):
        d = load(f)["minecraft:client_entity"]["description"]
        client[d["identifier"]] = d
        check_desc(os.path.basename(f), d, "entity")
    for f in glob.glob(rp("attachables", "*.json")):
        d = load(f)["minecraft:attachable"]["description"]
        check_desc(os.path.basename(f), d, "attachable")

    # ---- BP --------------------------------------------------------------
    item_tex = load(rp("textures", "item_texture.json"))["texture_data"]
    for k, v in item_tex.items():
        if not tex_exists(v["textures"]):
            errs.append(f"item_texture {k}: {v['textures']} missing")
    items = set()
    for f in glob.glob(bp("items", "*.json")):
        d = load(f)["minecraft:item"]
        ident = d["description"]["identifier"]
        items.add(ident)
        icon = d["components"].get("minecraft:icon", {}).get("texture")
        if icon not in item_tex:
            errs.append(f"item {ident}: icon {icon} not in item_texture.json")
        name = d["components"].get("minecraft:display_name", {}).get("value")
        if name and name not in KEYS:
            errs.append(f"item {ident}: lang key {name} missing")
    entities = set()
    for f in glob.glob(bp("entities", "*.json")):
        d = load(f)["minecraft:entity"]
        ident = d["description"]["identifier"]
        entities.add(ident)
        if ident not in client:
            errs.append(f"entity {ident}: no client entity")
        if f"entity.{ident}.name" not in KEYS:
            errs.append(f"entity {ident}: lang name missing")
        groups = set(d.get("component_groups", {}))

        def walk(ev, where):
            if isinstance(ev, dict):
                for key in ("add", "remove"):
                    for g in ev.get(key, {}).get("component_groups", []):
                        if g not in groups:
                            errs.append(f"{ident}: event {where} uses missing group {g}")
                for sub in ev.get("sequence", []) + ev.get("randomize", []):
                    walk(sub, where)
        for name, ev in d.get("events", {}).items():
            walk(ev, name)
    for f in glob.glob(bp("spawn_rules", "*.json")):
        ident = load(f)["minecraft:spawn_rules"]["description"]["identifier"]
        if ident not in entities:
            errs.append(f"spawn rule for missing entity {ident}")
    for f in glob.glob(bp("recipes", "*.json")):
        d = load(f)
        r = d.get("minecraft:recipe_shaped") or d.get("minecraft:recipe_shapeless")
        res = r["result"]["item"]
        if res.startswith("aot:") and res not in items:
            errs.append(f"recipe {f}: result {res} missing")
        keys = r.get("key", {}).values() if "key" in r else r.get("ingredients", [])
        for k in keys:
            if k["item"].startswith("aot:") and k["item"] not in items:
                errs.append(f"recipe {f}: ingredient {k['item']} missing")

    # ---- 効果音 -----------------------------------------------------------
    sdefs = load(rp("sounds", "sound_definitions.json"))["sound_definitions"]
    for name, d in sdefs.items():
        for s in d["sounds"]:
            path = rp(s["name"] + ".ogg")
            if not os.path.exists(path):
                errs.append(f"sound {name}: {s['name']}.ogg missing")
            elif os.path.getsize(path) < 1500:
                errs.append(f"sound {name}: {s['name']}.ogg looks empty")

    # ---- スクリプトの文字列リテラル ------------------------------------------
    pmeta = set(load(rp("animations", "aot_player.animation.json"))["animations"])
    for f in glob.glob(bp("scripts", "*.js")):
        src = open(f, encoding="utf-8").read()
        for m in re.finditer(r'"(aot\.[a-z0-9_.]+)"', src):
            k = m.group(1)
            if k.startswith(("aot.ui.", "aot.msg.", "aot.title.", "aot.hud.", "aot.rank.",
                             "aot.flare.")):
                if k not in KEYS and not k.endswith("."):
                    errs.append(f"{os.path.basename(f)}: lang key {k} missing")
            elif k not in sdefs and not k.startswith(("aot.act", "aot.move", "aot.hold")):
                errs.append(f"{os.path.basename(f)}: sound {k} missing")
        for m in re.finditer(r'\bP\([^,]+,\s*"([a-z_0-9]+)"', src):
            if f"aot:{m.group(1)}" not in particles:
                errs.append(f"{os.path.basename(f)}: particle aot:{m.group(1)} missing")
        for m in re.finditer(r'\b(?:body|pose)\(p, "([a-z_]+)"', src):
            if f"animation.aot.p.{m.group(1)}" not in pmeta:
                errs.append(f"{os.path.basename(f)}: body animation {m.group(1)} missing")
    for f in (bp("manifest.json"), rp("manifest.json"), bp("pack_icon.png"), rp("pack_icon.png")):
        if not os.path.exists(f):
            errs.append(f"{f} missing")

    for e in errs:
        print("  ERROR", e)
    print(f"  validate: {len(geos)} geometries, {len(anims)} animations, {len(client)} client entities, "
          f"{len(items)} items, {len(entities)} entities, {len(sdefs)} sounds -> {len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
