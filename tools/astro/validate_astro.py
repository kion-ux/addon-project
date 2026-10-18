# -*- coding: utf-8 -*-
"""アストロ・ナノギアの参照整合性チェック。

ジオメトリ・テクスチャ・アニメーション・コントローラ・アタッチャブル・クライアントエンティティ・
パーティクル・効果音・アイコン・言語キー・レシピ・ルートテーブル・スポーンルール・マニフェスト・
フォント（グリフ）が、互いに実在するものだけを指しているかを全件調べる。
加えて UV がテクスチャ内か、Molang の括弧が閉じているか、パーティクルの色が
particle_appearance_tinting の中にあるか（components 直下の "color" は無視されて染まらない）も見る。
"""
from __future__ import annotations

import json
import os
import re
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import astro_data as D  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
BP = os.path.join(ROOT, "packs", "astro_BP")
RP = os.path.join(ROOT, "packs", "astro_RP")
NS = D.NS

errors: list[str] = []
warnings: list[str] = []


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def walk(root, suffix=".json"):
    if not os.path.isdir(root):
        return
    for base, _d, files in os.walk(root):
        for f in sorted(files):
            if f.endswith(suffix):
                yield os.path.join(base, f)


def rel(p):
    return os.path.relpath(p, os.path.dirname(BP))


def tex_exists(path):
    return any(os.path.exists(os.path.join(RP, path + ext)) for ext in (".png", ".tga"))


MOLANG_KEYS = re.compile(r"(q\.|v\.|c\.|t\.|math\.|query\.|variable\.|context\.|temp\.)")


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
            errors.append(f"{where}: unbalanced molang: {s[:90]}")
        body = s.replace("??", "").replace("==", "").replace("!=", "").replace("<=", "").replace(">=", "")
        if "=" in body and ";" not in s:
            errors.append(f"{where}: assignment in a non-statement expression: {s[:90]}")


PARTICLE_COMPONENTS = {
    "minecraft:emitter_local_space", "minecraft:emitter_initialization", "minecraft:emitter_rate_instant",
    "minecraft:emitter_rate_steady", "minecraft:emitter_rate_manual", "minecraft:emitter_lifetime_once",
    "minecraft:emitter_lifetime_looping", "minecraft:emitter_lifetime_expression",
    "minecraft:emitter_lifetime_events", "minecraft:emitter_shape_point", "minecraft:emitter_shape_sphere",
    "minecraft:emitter_shape_box", "minecraft:emitter_shape_disc", "minecraft:emitter_shape_custom",
    "minecraft:emitter_shape_entity_aabb", "minecraft:particle_initial_speed", "minecraft:particle_initial_spin",
    "minecraft:particle_initialization", "minecraft:particle_motion_dynamic", "minecraft:particle_motion_parametric",
    "minecraft:particle_motion_collision", "minecraft:particle_appearance_billboard",
    "minecraft:particle_appearance_tinting", "minecraft:particle_appearance_lighting",
    "minecraft:particle_lifetime_expression", "minecraft:particle_lifetime_events",
    "minecraft:particle_kill_plane", "minecraft:particle_expire_if_in_blocks",
    "minecraft:particle_expire_if_not_in_blocks",
}


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
            if d["identifier"] in geos:
                errors.append(f"duplicate geometry {d['identifier']} ({rel(p)})")
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

    # ---- アニメーション・コントローラ -----------------------------------
    anims = {}
    for p in walk(os.path.join(RP, "animations")):
        doc = load(p)
        check_molang(rel(p), doc)
        for k, v in doc["animations"].items():
            if k in anims:
                errors.append(f"duplicate animation {k} ({rel(p)})")
            anims[k] = v
    controllers = {}
    for p in walk(os.path.join(RP, "animation_controllers")):
        doc = load(p)
        check_molang(rel(p), doc)
        for k, v in doc["animation_controllers"].items():
            controllers[k] = v
            for sname, st in v.get("states", {}).items():
                for tr in st.get("transitions", []):
                    for target in tr:
                        if target not in v["states"]:
                            errors.append(f"{k}: state {sname} transitions to unknown {target}")

    def check_anim_refs(where, d, geo_bones):
        amap = d.get("animations", {})
        for short, a in amap.items():
            if a.startswith("controller."):
                if a not in controllers:
                    errors.append(f"{where}: controller {a} missing")
                    continue
                for st in controllers[a].get("states", {}).values():
                    for entry in st.get("animations", []):
                        key = entry if isinstance(entry, str) else list(entry)[0]
                        if key not in amap:
                            errors.append(f"{where}: controller {a} plays unknown key {key}")
            elif a not in anims:
                errors.append(f"{where}: animation {a} missing")
            elif geo_bones is not None:
                for bone in anims[a].get("bones", {}):
                    if bone not in geo_bones:
                        errors.append(f"{where}: {a} animates missing bone {bone}")
        for entry in d.get("scripts", {}).get("animate", []):
            key = entry if isinstance(entry, str) else list(entry)[0]
            if key not in amap:
                errors.append(f"{where}: animate refers to unknown key {key}")

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
        tex = d["textures"].get("default")
        geo = geos.get(d["geometry"].get("default"))
        if geo and tex and tex_exists(tex):
            im = Image.open(os.path.join(RP, tex + ".png"))
            if im.size != (geo[0], geo[1]):
                errors.append(f"{rel(p)}: texture {im.size} != geometry {geo[0]}x{geo[1]}")
        bones = {b["name"] for b in geo[2]["bones"]} if geo else None
        check_anim_refs(rel(p), d, bones)

    # ---- クライアントエンティティ ---------------------------------------
    client_ids = set()
    for p in walk(os.path.join(RP, "entity")):
        doc = load(p)
        check_molang(rel(p), doc)
        d = doc["minecraft:client_entity"]["description"]
        client_ids.add(d["identifier"])
        bones = set()
        for g in d.get("geometry", {}).values():
            if g not in geos:
                errors.append(f"{rel(p)}: geometry {g} missing")
            else:
                bones |= {b["name"] for b in geos[g][2]["bones"]}
        for t in d.get("textures", {}).values():
            if not tex_exists(t):
                errors.append(f"{rel(p)}: texture {t} missing")
        check_anim_refs(rel(p), d, bones or None)
        for rc in d.get("render_controllers", []):
            name = rc if isinstance(rc, str) else list(rc)[0]
            if not name.startswith("controller.render.") :
                errors.append(f"{rel(p)}: odd render controller {name}")

    # ---- パーティクル ------------------------------------------------
    particle_ids = set()
    for p in walk(os.path.join(RP, "particles")):
        doc = load(p)
        check_molang(rel(p), doc)
        pe = doc["particle_effect"]
        particle_ids.add(pe["description"]["identifier"])
        t = pe["description"]["basic_render_parameters"]["texture"]
        if not tex_exists(t):
            errors.append(f"{rel(p)}: texture {t} missing")
        for k in pe["components"]:
            if k not in PARTICLE_COMPONENTS:
                errors.append(f"{rel(p)}: unknown particle component {k!r} (ignored by the game)")
        if "minecraft:particle_appearance_tinting" not in pe["components"]:
            warnings.append(f"{rel(p)}: no tinting (cannot be coloured from script)")
        bb = pe["components"].get("minecraft:particle_appearance_billboard", {})
        uv = bb.get("uv", {})
        if "uv" in uv and all(isinstance(x, (int, float)) for x in uv["uv"]):
            if uv["uv"][0] + uv["uv_size"][0] > uv["texture_width"] or \
                    uv["uv"][1] + uv["uv_size"][1] > uv["texture_height"]:
                errors.append(f"{rel(p)}: uv outside atlas")

    # ---- 効果音 --------------------------------------------------------
    sd_path = os.path.join(RP, "sounds", "sound_definitions.json")
    sd = load(sd_path)["sound_definitions"] if os.path.exists(sd_path) else {}
    if not sd:
        errors.append("sound_definitions.json missing or empty")
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
            langs[f] = {ln.split("=", 1)[0] for ln in open(os.path.join(RP, "texts", f), encoding="utf-8")
                        if "=" in ln}
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
    for key in D.PLANETS:
        for ident in (f"{NS}:core_{key}", f"{NS}:weapon_{key}", f"{NS}:suit_{key}", f"{NS}:suit_{key}_off"):
            if ident not in item_ids:
                errors.append(f"item {ident} missing")
            if ident not in att_ids:
                errors.append(f"{ident} has no attachable")
    for p in walk(os.path.join(BP, "recipes")):
        doc = load(p)
        for v in json.dumps(doc).split('"'):
            if v.startswith(f"{NS}:") and v not in item_ids:
                ident_ok = v == f"{NS}:{os.path.basename(p)[:-5]}"
                if not ident_ok:
                    errors.append(f"{rel(p)}: unknown item {v}")

    # ---- エンティティ（BP）-------------------------------------------
    entity_ids = set()
    for p in walk(os.path.join(BP, "entities")):
        doc = load(p)
        ident = doc["minecraft:entity"]["description"]["identifier"]
        entity_ids.add(ident)
        if ident not in client_ids:
            errors.append(f"{ident}: no client entity")
        for lf, keys in langs.items():
            if f"entity.{ident}.name" not in keys:
                errors.append(f"{lf}: missing entity.{ident}.name")
        txt = json.dumps(doc)
        for lt in re.findall(r'"table":\s*"([^"]+)"', txt):
            if not os.path.exists(os.path.join(BP, lt)):
                errors.append(f"{rel(p)}: loot table {lt} missing")
    for p in walk(os.path.join(BP, "loot_tables")):
        for v in json.dumps(load(p)).split('"'):
            if v.startswith(f"{NS}:") and v not in item_ids:
                errors.append(f"{rel(p)}: unknown item {v}")
    for p in walk(os.path.join(BP, "spawn_rules")):
        ident = load(p)["minecraft:spawn_rules"]["description"]["identifier"]
        if ident not in entity_ids:
            errors.append(f"{rel(p)}: spawn rule for unknown entity {ident}")

    # ---- フォント・UI テクスチャ -----------------------------------------
    font_dir = os.path.join(RP, "font")
    if os.path.isdir(font_dir):
        for f in os.listdir(font_dir):
            if f.startswith("glyph_") and f.endswith(".png"):
                im = Image.open(os.path.join(font_dir, f))
                if im.size[0] != im.size[1] or im.size[0] % 16:
                    errors.append(f"font/{f}: glyph page must be square and a multiple of 16 ({im.size})")
                if f.upper() in ("GLYPH_E0.PNG", "GLYPH_E1.PNG"):
                    warnings.append(f"font/{f}: overrides a vanilla glyph page")

    # ---- スクリプトが参照するリソース ------------------------------------
    js_dir = os.path.join(BP, "scripts")
    used_ui = set()
    for p in walk(js_dir, ".js"):
        src = open(p, encoding="utf-8").read()
        for t in re.findall(r'"(textures/[A-Za-z0-9_/]+)"', src):
            used_ui.add(t)
    for t in sorted(used_ui):
        if not tex_exists(t):
            errors.append(f"scripts reference missing texture {t}")

    # ---- マニフェスト ---------------------------------------------------
    bm, rm = load(os.path.join(BP, "manifest.json")), load(os.path.join(RP, "manifest.json"))
    if not any(d.get("uuid") == rm["header"]["uuid"] for d in bm["dependencies"]):
        errors.append("BP manifest does not depend on RP")
    if not any(d.get("uuid") == bm["header"]["uuid"] for d in rm["dependencies"]):
        errors.append("RP manifest does not depend on BP")
    for p in (BP, RP):
        if not os.path.exists(os.path.join(p, "pack_icon.png")):
            errors.append(f"{rel(p)}: pack_icon.png missing")
    entry = next((m.get("entry") for m in bm["modules"] if m["type"] == "script"), None)
    if not entry or not os.path.exists(os.path.join(BP, entry)):
        errors.append(f"script entry {entry} missing")

    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"  validate: {len(geos)} geometries, {len(anims)} animations, {len(controllers)} controllers, "
          f"{len(att_ids)} attachables, {len(client_ids)} client entities, {len(particle_ids)} particles, "
          f"{len(sd)} sounds, {len(item_ids)} items — {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
