# -*- coding: utf-8 -*-
"""二つのパックを突き合わせて、参照切れと担当漏れを検出する。

十人が並列で作るので、検証は「JSON が壊れていないか」だけでは足りない。
*正典 (contract.py) に載っている物が、全部ちゃんと生成されているか* まで見る。
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _path  # noqa: E402,F401

import contract as K  # noqa: E402

ROOT = K.ROOT
BP = K.BP
RP = K.RP

errors: list = []
warnings: list = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def walk(root, suffix=".json"):
    if not os.path.isdir(root):
        return
    for base, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f.endswith(suffix):
                yield os.path.join(base, f)


def rel(path):
    return os.path.relpath(path, ROOT)


def main() -> int:  # noqa: C901
    # ---- 1. すべての JSON が読めるか ----------------------------------
    for pack in (BP, RP):
        for path in walk(pack):
            try:
                load(path)
            except Exception as exc:  # noqa: BLE001
                err(f"invalid json: {rel(path)}: {exc}")
    if errors:
        for e in errors:
            print("ERROR", e)
        return 1

    # ---- 2. ジオメトリ台帳 --------------------------------------------
    geometries = {}
    for path in walk(os.path.join(RP, "models")):
        for g in load(path).get("minecraft:geometry", []):
            ident = g["description"]["identifier"]
            geometries[ident] = {b["name"] for b in g.get("bones", [])}
    known_geo = set(geometries) | {
        "geometry.humanoid.armor.helmet", "geometry.humanoid.armor.chestplate",
        "geometry.humanoid.armor.leggings", "geometry.humanoid.armor.boots",
    }
    all_bones = set().union(*geometries.values()) if geometries else set()
    # 変身体はプレイヤーの骨に乗るので、バニラの骨名も正当
    all_bones |= {"head", "body", "leftArm", "rightArm", "leftLeg", "rightLeg",
                  "hat", "leftItem", "rightItem", "leftSleeve", "rightSleeve",
                  "leftPants", "rightPants", "jacket", "cape", "root"}

    # ---- 3. アニメーション / コントローラ ------------------------------
    animations = set()
    for path in walk(os.path.join(RP, "animations")):
        doc = load(path).get("animations", {})
        animations |= set(doc)
        for name, clip in doc.items():
            for bone in clip.get("bones", {}):
                if bone not in all_bones:
                    err(f"{rel(path)}: {name} が未知のボーン '{bone}' を動かしている")

    controllers = {}
    for path in walk(os.path.join(RP, "animation_controllers")):
        for name, ctrl in load(path).get("animation_controllers", {}).items():
            refs = set()
            states = ctrl.get("states", {})
            if ctrl.get("initial_state") and ctrl["initial_state"] not in states:
                err(f"{rel(path)}: {name} の initial_state が存在しない")
            for sname, state in states.items():
                for a in state.get("animations", []):
                    refs.add(a if isinstance(a, str) else list(a)[0])
                for t in state.get("transitions", []):
                    for target in t:
                        if target not in states:
                            err(f"{rel(path)}: {name}.{sname} -> 未定義の状態 "
                                f"'{target}'")
            controllers[name] = refs

    render_controllers = set()
    for path in walk(os.path.join(RP, "render_controllers")):
        render_controllers |= set(load(path).get("render_controllers", {}))
    render_controllers |= {"controller.render.armor",
                           "controller.render.item_default"}

    # ---- 4. パーティクル -----------------------------------------------
    particles = set()
    for path in walk(os.path.join(RP, "particles")):
        doc = load(path)["particle_effect"]
        particles.add(doc["description"]["identifier"])
        t = doc["description"]["basic_render_parameters"]["texture"]
        if not os.path.exists(os.path.join(RP, t + ".png")):
            err(f"{rel(path)}: テクスチャがない {t}.png")

    used_particles = set()
    spawn_call = re.compile(
        r'(?:fx|fxRing|fxLine|fxScatter|fxArc|fxSphere|fxTrail|spawnParticle)'
        r'\s*\([^;]{0,200}?"(marvel:[a-z0-9_]+)"')
    literal = re.compile(r'"(marvel:[a-z0-9_]+)"')
    for path in walk(os.path.join(BP, "scripts"), ".js"):
        body = open(path, encoding="utf-8").read()
        for m in spawn_call.finditer(body):
            name = m.group(1)
            if name in particles:
                used_particles.add(name)
            else:
                err(f"scripts/{os.path.basename(path)}: 未定義のパーティクル {name}")
        # PARTICLE テーブル等に直接書かれた名前も拾う（誤字検出用）
        for m in literal.finditer(body):
            n = m.group(1)
            if n in particles:
                used_particles.add(n)

    # ---- 5. クライアントエンティティ ------------------------------------
    client_ids = set()
    for path in walk(os.path.join(RP, "entity")):
        desc = load(path)["minecraft:client_entity"]["description"]
        client_ids.add(desc["identifier"])
        anim_map = desc.get("animations", {})
        for g in desc.get("geometry", {}).values():
            if g not in known_geo:
                err(f"{rel(path)}: 未知のジオメトリ {g}")
        for t in desc.get("textures", {}).values():
            if not os.path.exists(os.path.join(RP, t + ".png")):
                err(f"{rel(path)}: テクスチャがない {t}.png")
        for rc in desc.get("render_controllers", []):
            name = rc if isinstance(rc, str) else list(rc)[0]
            if name not in render_controllers:
                err(f"{rel(path)}: 未知の render controller {name}")
        for key, value in anim_map.items():
            if value.startswith("controller."):
                if value not in controllers:
                    err(f"{rel(path)}: 未知の controller {value}")
            elif value not in animations:
                err(f"{rel(path)}: 未知のアニメーション {value}")
        for short in desc.get("scripts", {}).get("animate", []):
            name = short if isinstance(short, str) else list(short)[0]
            if name not in anim_map:
                err(f"{rel(path)}: animate の '{name}' が animations に無い")
        # controller が参照する短縮名は、そのエンティティの animations に無ければならない
        for key, value in anim_map.items():
            if not value.startswith("controller."):
                continue
            for ref in controllers.get(value, ()):
                if ref not in anim_map:
                    err(f"{rel(path)}: {value} が参照する '{ref}' が "
                        f"animations に無い")
        for value in desc.get("particle_effects", {}).values():
            if value.startswith("minecraft:"):
                continue
            if value not in particles:
                err(f"{rel(path)}: 未知のパーティクル {value}")
            else:
                used_particles.add(value)

    # ---- 6. アタッチャブル ---------------------------------------------
    attachable_ids = set()
    for path in walk(os.path.join(RP, "attachables")):
        desc = load(path)["minecraft:attachable"]["description"]
        attachable_ids.add(desc["identifier"])
        anim_map = desc.get("animations", {})
        for g in desc.get("geometry", {}).values():
            if g not in known_geo:
                err(f"{rel(path)}: 未知のジオメトリ {g}")
        for tkey, t in desc.get("textures", {}).items():
            if t.startswith("textures/misc/"):
                continue
            if not os.path.exists(os.path.join(RP, t + ".png")):
                err(f"{rel(path)}: テクスチャがない {t}.png")
        for rc in desc.get("render_controllers", []):
            name = rc if isinstance(rc, str) else list(rc)[0]
            if name not in render_controllers:
                err(f"{rel(path)}: 未知の render controller {name}")
        for key, value in anim_map.items():
            if value.startswith("controller."):
                if value not in controllers:
                    err(f"{rel(path)}: 未知の controller {value}")
                for ref in controllers.get(value, ()):
                    if ref not in anim_map:
                        err(f"{rel(path)}: {value} が参照する '{ref}' が "
                            f"animations に無い")
            elif value not in animations:
                err(f"{rel(path)}: 未知のアニメーション {value}")
        for short in desc.get("scripts", {}).get("animate", []):
            name = short if isinstance(short, str) else list(short)[0]
            if name not in anim_map:
                err(f"{rel(path)}: animate の '{name}' が animations に無い")

    # ---- 7. アイテムアトラス -------------------------------------------
    atlas = {}
    atlas_path = os.path.join(RP, "textures", "item_texture.json")
    if not os.path.exists(atlas_path):
        err("item_texture.json がない")
    else:
        atlas = load(atlas_path).get("texture_data", {})
        for key, entry in atlas.items():
            t = entry["textures"]
            if not os.path.exists(os.path.join(RP, t + ".png")):
                err(f"item_texture.json: {key} のテクスチャがない {t}.png")

    # ---- 8. BP エンティティ / アイテム -----------------------------------
    bp_ids = set()
    for path in walk(os.path.join(BP, "entities")):
        doc = load(path)["minecraft:entity"]
        ident = doc["description"]["identifier"]
        bp_ids.add(ident)
        comps = doc.get("components", {})
        table = comps.get("minecraft:loot", {}).get("table")
        if table and not os.path.exists(os.path.join(BP, table)):
            err(f"{rel(path)}: ルートテーブルがない {table}")
        shooter = comps.get("minecraft:shooter", {}).get("def")
        if shooter and shooter not in bp_ids and shooter.startswith("marvel:"):
            warn(f"{rel(path)}: shooter が未確認のエンティティ {shooter}")

    item_ids = set()
    for path in walk(os.path.join(BP, "items")):
        doc = load(path)["minecraft:item"]
        ident = doc["description"]["identifier"]
        item_ids.add(ident)
        icon = doc["components"].get("minecraft:icon")
        key = icon.get("texture") if isinstance(icon, dict) else icon
        if key not in atlas:
            err(f"item {ident}: アイコン '{key}' が item_texture.json に無い")

    for ident in attachable_ids:
        if ident not in item_ids:
            err(f"attachable {ident} に対応するアイテムが無い")

    for ident in client_ids:
        if ident not in bp_ids:
            err(f"client entity {ident} に対応する BP エンティティが無い")
    for ident in bp_ids:
        if ident not in client_ids:
            err(f"BP エンティティ {ident} に対応する client entity が無い")

    # ---- 9. spawn rules / loot / recipes ---------------------------------
    for path in walk(os.path.join(BP, "spawn_rules")):
        ident = load(path)["minecraft:spawn_rules"]["description"]["identifier"]
        if ident not in bp_ids:
            err(f"spawn rule が未知のエンティティを指す {ident}")

    known_items = item_ids | {f"{i}_spawn_egg" for i in bp_ids}
    for path in walk(os.path.join(BP, "loot_tables")):
        for pool in load(path).get("pools", []):
            for e in pool.get("entries", []):
                name = e.get("name", "")
                if name.startswith("marvel:") and name not in known_items:
                    err(f"{rel(path)}: 未知のアイテム {name}")

    for path in walk(os.path.join(BP, "recipes")):
        doc = load(path)
        recipe = (doc.get("minecraft:recipe_shaped")
                  or doc.get("minecraft:recipe_shapeless")
                  or doc.get("minecraft:recipe_furnace"))
        if not recipe:
            continue
        refs = []
        if "key" in recipe:
            refs += [v["item"] if isinstance(v, dict) else v
                     for v in recipe["key"].values()]
        ing = recipe.get("ingredients", [])
        if isinstance(ing, dict):
            ing = [ing]
        refs += [i["item"] if isinstance(i, dict) else i for i in ing]
        result = recipe.get("result")
        if isinstance(result, dict):
            refs.append(result.get("item"))
        elif isinstance(result, str):
            refs.append(result)
        for name in refs:
            if isinstance(name, str) and name.startswith("marvel:") \
                    and name not in known_items:
                err(f"{rel(path)}: レシピが未知のアイテム {name} を指す")

    # ---- 10. 言語 ---------------------------------------------------------
    langs = {}
    for code in ("ja_JP", "en_US"):
        table = {}
        p = os.path.join(RP, "texts", f"{code}.lang")
        if not os.path.exists(p):
            err(f"texts/{code}.lang がない")
            langs[code] = table
            continue
        for line in open(p, encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                table[k.strip()] = v.strip()
        langs[code] = table
    for code, table in langs.items():
        for ident in item_ids:
            if f"item.{ident}" not in table and f"item.{ident}.name" not in table:
                warn(f"{code}: アイテム名が無い {ident}")
        for ident in bp_ids:
            if f"entity.{ident}.name" not in table:
                warn(f"{code}: エンティティ名が無い {ident}")

    # ---- 11. 正典との突き合わせ（担当漏れの検出）--------------------------
    for key in K.EXTRA_GEOMETRIES:
        if K.geo(key) not in geometries:
            err(f"[担当漏れ] ジオメトリ {K.geo(key)} が生成されていない")
        if not os.path.exists(K.tex_path(key)):
            err(f"[担当漏れ] テクスチャ {key}.png が生成されていない")

    for key in K.ENTITY_KEYS:
        if K.eid(key) not in bp_ids:
            err(f"[担当漏れ] BP エンティティ {K.eid(key)} が生成されていない")
        gname = K.geo(key)
        if gname not in geometries:
            err(f"[担当漏れ] ジオメトリ {gname} が生成されていない")
        if not os.path.exists(K.tex_path(key)) and key in K.ALL_CHARACTERS:
            err(f"[担当漏れ] テクスチャ {key}.png が生成されていない")

    for key in K.all_item_keys():
        if K.eid(key) not in item_ids:
            err(f"[担当漏れ] アイテム {K.eid(key)} が生成されていない")

    for name in K.PARTICLES:
        if K.part(name) not in particles:
            err(f"[担当漏れ] パーティクル {K.part(name)} が生成されていない")

    for group, clips in K.ANIM_GROUPS.items():
        for clip in clips:
            ident = (K.anim(group, clip) if group != "common"
                     else f"animation.{K.NS}.{clip}")
            if ident not in animations:
                err(f"[担当漏れ] アニメーション {ident} が生成されていない")

    for name in K.ANIM_CONTROLLERS:
        if K.ctrl(name) not in controllers:
            err(f"[担当漏れ] コントローラ {K.ctrl(name)} が生成されていない")

    for name in K.RENDER_CONTROLLERS:
        if K.render_ctrl(name) not in render_controllers:
            err(f"[担当漏れ] render controller {K.render_ctrl(name)} が無い")

    for name in sorted(particles - used_particles):
        warn(f"パーティクル {name} は定義されているが誰も使っていない")

    # ---- 12. マニフェスト -------------------------------------------------
    bpm = load(os.path.join(BP, "manifest.json"))
    rpm = load(os.path.join(RP, "manifest.json"))
    if bpm["dependencies"][0]["uuid"] != rpm["header"]["uuid"]:
        err("BP がリソースパックの uuid に依存していない")
    if rpm["dependencies"][0]["uuid"] != bpm["header"]["uuid"]:
        err("RP がビヘイビアパックの uuid に依存していない")
    for pack in (BP, RP):
        if not os.path.exists(os.path.join(pack, "pack_icon.png")):
            err(f"{os.path.basename(pack)}: pack_icon.png がない")

    # ---- 出力 -------------------------------------------------------------
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"\n{len(bp_ids)} entities, {len(item_ids)} items, "
          f"{len(geometries)} geometries, {len(animations)} animations, "
          f"{len(controllers)} controllers, {len(particles)} particles, "
          f"{len(attachable_ids)} attachables")
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
