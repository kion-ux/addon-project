# -*- coding: utf-8 -*-
"""アストロ・ナノギア — パックのデータ一式。

マニフェスト・アイテム・レシピ・言語・item_texture.json と、スクリプトが読む data.js を
astro_data.py（ゲームデータの単一ソース）から書き出す。
アイコンの絵そのものはモデルを描く生成スクリプト（ウェポン・コア・スーツ）と gen_astro_ui.py が作る。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import astro_data as D  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BP = os.path.join(ROOT, "packs", "astro_BP")
RP = os.path.join(ROOT, "packs", "astro_RP")
NS = D.NS

VERSION = list(D.VERSION)
MIN_ENGINE = [1, 21, 30]
UUID = {
    "bp": "14dd5439-958f-4b19-b75d-2c837106e231",
    "bp_data": "ef9b672e-34a0-4ef4-9f37-dcd59df09326",
    "bp_script": "c4db21f0-4351-4e88-9ab8-256833196077",
    "rp": "5edff4c1-24c6-4359-89b0-834d74773e7e",
    "rp_res": "f57ffe15-461b-4ae4-802a-d8b425302272",
}
SERVER_VERSION = "1.13.0"
SERVER_UI_VERSION = "1.2.0"


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ===========================================================================
#  マニフェスト
# ===========================================================================
def manifests():
    meta = {"authors": ["Astro Nanogear Project"], "license": "MIT", "product_type": "addon"}
    write_json(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": UUID["bp"],
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUID["bp_data"], "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUID["bp_script"],
             "version": VERSION, "entry": "scripts/main.js"},
        ],
        "dependencies": [
            {"uuid": UUID["rp"], "version": VERSION},
            {"module_name": "@minecraft/server", "version": SERVER_VERSION},
            {"module_name": "@minecraft/server-ui", "version": SERVER_UI_VERSION},
        ],
        "metadata": meta,
    })
    write_json(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": UUID["rp"],
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUID["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUID["bp"], "version": VERSION}],
        "metadata": meta,
    })


# ===========================================================================
#  アイテム
# ===========================================================================
def item(ident, icon, comps, category="equipment", group=None):
    desc = {"identifier": f"{NS}:{ident}", "menu_category": {"category": category}}
    if group:
        desc["menu_category"]["group"] = group
    base = {"minecraft:icon": {"texture": icon},
            "minecraft:display_name": {"value": f"item.{NS}.{ident}.name"}}
    base.update(comps)
    return {"format_version": "1.21.20", "minecraft:item": {"description": desc, "components": base}}


def items():
    d = os.path.join(BP, "items")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith(".item.json"):
            os.remove(os.path.join(d, f))
    for key, pl in D.PLANETS.items():
        # 惑星コア: 右クリックで変身
        write_json(os.path.join(d, f"core_{key}.item.json"), item(
            f"core_{key}", f"{NS}_core_{key}",
            {"minecraft:max_stack_size": 1,
             "minecraft:hand_equipped": True,
             "minecraft:use_modifiers": {"use_duration": 0.2, "movement_modifier": 1.0},
             "minecraft:should_despawn": False,
             "minecraft:glint": False},
            "equipment", "itemGroup.name.sword"))
        # ナノウェポン: 変身中だけ手に現れる（一覧には出さない）
        write_json(os.path.join(d, f"weapon_{key}.item.json"), item(
            f"weapon_{key}", f"{NS}_weapon_{key}",
            {"minecraft:max_stack_size": 1,
             "minecraft:hand_equipped": True,
             "minecraft:damage": {"value": pl["damage"]},
             "minecraft:use_modifiers": {"use_duration": 1.0, "movement_modifier": 1.0},
             "minecraft:can_destroy_in_creative": False,
             "minecraft:should_despawn": False,
             "minecraft:glint": False},
            "none"))
        # スーツ（頭スロット）。_on = 組み上がり中（アタッチャブルが組み上がりアニメを再生）、
        # 無印 = 装着中（後から見えた人には組み上がりを繰り返さない）、_off = 分解中
        for suffix, prot in (("_on", pl["defense"]), ("", pl["defense"]), ("_off", 0)):
            write_json(os.path.join(d, f"suit_{key}{suffix}.item.json"), item(
                f"suit_{key}{suffix}", f"{NS}_suit_{key}",
                {"minecraft:max_stack_size": 1,
                 "minecraft:wearable": {"slot": "slot.armor.head", "protection": prot},
                 "minecraft:should_despawn": False,
                 "minecraft:glint": False},
                "none"))
    for name, m in D.MATERIALS.items():
        comps = {"minecraft:max_stack_size": m["stack"], "minecraft:glint": m["glint"]}
        cat = "items"
        if name == "terminal":
            comps["minecraft:use_modifiers"] = {"use_duration": 0.2, "movement_modifier": 1.0}
            cat = "equipment"
        if name == "void_signal":
            comps["minecraft:use_modifiers"] = {"use_duration": 0.6, "movement_modifier": 0.5}
        write_json(os.path.join(d, f"{name}.item.json"), item(name, f"{NS}_{name}", comps, cat))


# ===========================================================================
#  レシピ
# ===========================================================================
def shaped(ident, pattern, keys, count=1):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": f"{NS}:{ident}"},
            "tags": ["crafting_table"],
            "pattern": pattern,
            "key": {k: {"item": v} for k, v in keys.items()},
            "result": {"item": f"{NS}:{ident}", "count": count},
        }}


def recipes():
    d = os.path.join(BP, "recipes")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith(".json"):
            os.remove(os.path.join(d, f))
    for name, (pattern, keys, count) in D.RECIPES.items():
        write_json(os.path.join(d, f"{name}.json"), shaped(name, pattern, keys, count))
    for key, pl in D.PLANETS.items():
        keys = {"N": f"{NS}:nano_cell", "F": f"{NS}:core_frame",
                "A": pl["recipe"]["A"], "B": pl["recipe"]["B"]}
        write_json(os.path.join(d, f"core_{key}.json"), shaped(f"core_{key}", D.CORE_PATTERN, keys))


# ===========================================================================
#  item_texture.json（アイコンの絵は各生成スクリプトが textures/items/astro/ に書く）
# ===========================================================================
def icon_names():
    names = []
    for key in D.PLANETS:
        names += [f"core_{key}", f"weapon_{key}", f"suit_{key}"]
    names += list(D.MATERIALS)
    return names


def item_atlas():
    data = {f"{NS}_{n}": {"textures": f"textures/items/{NS}/{n}"} for n in icon_names()}
    write_json(os.path.join(RP, "textures", "item_texture.json"),
               {"resource_pack_name": "astro_nanogear", "texture_name": "atlas.items",
                "texture_data": data})


# ===========================================================================
#  言語
# ===========================================================================
def lang_lines():
    ja = [f"pack.name={D.ADDON_JA}",
          "pack.description=惑星の力を宿す星核で全身装甲に変身して戦う宇宙アドオン（9 形態）"]
    en = [f"pack.name={D.ADDON_EN}",
          "pack.description=Transform into planet-powered nanomachine mech suits (9 forms)"]
    for key, pl in D.PLANETS.items():
        ja += [f"item.{NS}.core_{key}.name={pl['core_ja']}",
               f"item.{NS}.weapon_{key}.name={pl['weapon']['ja']}",
               f"item.{NS}.suit_{key}.name={pl['suit_ja']}",
               f"item.{NS}.suit_{key}_on.name={pl['suit_ja']}",
               f"item.{NS}.suit_{key}_off.name={pl['suit_ja']}"]
        en += [f"item.{NS}.core_{key}.name={pl['core_en']}",
               f"item.{NS}.weapon_{key}.name={pl['weapon']['en']}",
               f"item.{NS}.suit_{key}.name={pl['suit_en']}",
               f"item.{NS}.suit_{key}_on.name={pl['suit_en']}",
               f"item.{NS}.suit_{key}_off.name={pl['suit_en']}"]
    for name, m in D.MATERIALS.items():
        ja.append(f"item.{NS}.{name}.name={m['ja']}")
        en.append(f"item.{NS}.{name}.name={m['en']}")
    for name, e in D.ENEMIES.items():
        ja += [f"entity.{NS}:{name}.name={e['ja']}",
               f"item.spawn_egg.entity.{NS}:{name}.name={e['ja']}"]
        en += [f"entity.{NS}:{name}.name={e['en']}",
               f"item.spawn_egg.entity.{NS}:{name}.name=Spawn {e['en']}"]
    ja += [f"entity.{NS}:dmg_text.name=ダメージ表示", f"entity.{NS}:void_bolt.name=ヴォイド・ボルト"]
    en += [f"entity.{NS}:dmg_text.name=Damage Text", f"entity.{NS}:void_bolt.name=Void Bolt"]
    return {"ja_JP": ja, "en_US": en}


def lang():
    langs = lang_lines()
    for pack in (BP, RP):
        d = os.path.join(pack, "texts")
        os.makedirs(d, exist_ok=True)
        write_json(os.path.join(d, "languages.json"), list(langs))
        for code, lines in langs.items():
            with open(os.path.join(d, f"{code}.lang"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")


# ===========================================================================
#  data.js（スクリプトが読むゲームデータ）
# ===========================================================================
def planet_js(key, pl):
    c = pl["colors"]
    return {
        "key": key, "order": pl["order"], "symbol": pl["symbol"],
        "ja": pl["ja"], "en": pl["en"], "form_ja": pl["form_ja"], "form_en": pl["form_en"],
        "core_ja": pl["core_ja"], "suit_ja": pl["suit_ja"], "tc": pl["tc"],
        "color": D.rgb01(c["glow"]), "light": D.rgb01(c["light"]), "deep": D.rgb01(c["deep"]),
        "plate": D.rgb01(c["plate"]), "plate2": D.rgb01(c["plate2"]), "accent": D.rgb01(c["accent"]),
        "weapon": pl["weapon"], "damage": pl["damage"], "defense": pl["defense"],
        "mobility": pl["mobility"], "passive": pl["passive"], "combo3": pl["combo3"],
        "moves": pl["moves"], "motif": pl["motif"],
        "core": f"{NS}:core_{key}", "suit": f"{NS}:suit_{key}", "suitOn": f"{NS}:suit_{key}_on",
        "suitOff": f"{NS}:suit_{key}_off",
        "weaponId": f"{NS}:weapon_{key}",
    }


def data_js():
    planets = {k: planet_js(k, v) for k, v in D.PLANETS.items()}

    def dump(v):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))

    lines = [
        "// 自動生成（tools/astro/gen_astro_packs.py ← tools/astro/astro_data.py）。手で編集しない",
        f"export const NS = {dump(NS)};",
        f"export const COMMON = {dump(D.COMMON)};",
        f"export const TRANSFORM = {dump(D.TRANSFORM)};",
        f"export const ASSEMBLE_ORDER = {dump(D.ASSEMBLE_ORDER)};",
        f"export const MOVE_KINDS = {dump(list(D.MOVE_KINDS))};",
        f"export const MOVE_LABEL = {dump(D.MOVE_LABEL_JA)};",
        f"export const MOVE_INPUT = {dump(D.MOVE_INPUT_JA)};",
        f"export const PLANETS = {dump(planets)};",
        f"export const PLANET_KEYS = {dump(D.PLANET_KEYS)};",
        "export const CORE_TO_PLANET = Object.fromEntries(Object.values(PLANETS).map((p) => [p.core, p.key]));",
        "export const WEAPON_TO_PLANET = Object.fromEntries(Object.values(PLANETS).map((p) => [p.weaponId, p.key]));",
        "export const SUIT_TO_PLANET = Object.fromEntries(Object.values(PLANETS).flatMap((p) => [[p.suit, p.key], [p.suitOn, p.key], [p.suitOff, p.key]]));",
        f"export const MATERIALS = {dump({k: {'ja': v['ja'], 'en': v['en']} for k, v in D.MATERIALS.items()})};",
        f"export const ENEMIES = {dump(D.ENEMIES)};",
        f"export const ADDON = {dump({'ja': D.ADDON_JA, 'en': D.ADDON_EN, 'version': '.'.join(map(str, D.VERSION))})};",
        "",
    ]
    path = os.path.join(BP, "scripts", "data.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main():
    manifests()
    items()
    recipes()
    item_atlas()
    lang()
    data_js()
    n_items = len(os.listdir(os.path.join(BP, "items")))
    n_rec = len(os.listdir(os.path.join(BP, "recipes")))
    print(f"  packs: {n_items} items, {n_rec} recipes, lang, item_texture, data.js")


if __name__ == "__main__":
    main()
