# -*- coding: utf-8 -*-
"""ビヘイビア／リソースパックのデータ一式。

アイテム・レシピ・エンティティ（訓練用カカシ・ダメージ表示）・クライアント定義・
アイテムアトラス・言語ファイル・マニフェスト・パックアイコン・素材アイコン。
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hd_common import BP, ELEMENTS, NS, RP, WEAPONS, cbox, write_json  # noqa: E402
from hd_paint import HDPainter  # noqa: E402
from mcmodel import Model  # noqa: E402

VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 30]
UUID = {
    "bp": "6f1d2a4e-8c3b-4f7a-9e21-3b5c7d9e1a01",
    "bp_data": "6f1d2a4e-8c3b-4f7a-9e21-3b5c7d9e1a02",
    "bp_script": "6f1d2a4e-8c3b-4f7a-9e21-3b5c7d9e1a03",
    "rp": "6f1d2a4e-8c3b-4f7a-9e21-3b5c7d9e1a04",
    "rp_res": "6f1d2a4e-8c3b-4f7a-9e21-3b5c7d9e1a05",
}

# 武器: (攻撃力, 耐久, 使用時間 秒, 使用中の移動倍率)
STATS = {
    "greatsword": (8, 2400, 1.0, 0.9),
    "twinblades": (6, 2000, 1.0, 1.0),
    "greataxe": (9, 2400, 1.0, 0.9),
    "dagger": (5, 1800, 1.0, 1.0),
    "bow": (3, 1800, 60.0, 0.55),
    "shield": (4, 2600, 4.5, 0.45),
    "whip": (5, 2000, 1.0, 1.0),
    "claws": (6, 2000, 1.0, 1.0),
}

RECIPES = {
    "greatsword": (["C C", " D ", "CSC"], {"C": "hd:dimension_crystal", "D": "minecraft:diamond_block", "S": "minecraft:blaze_rod"}),
    "twinblades": (["C C", "D D", "S S"], {"C": "hd:dimension_crystal", "D": "minecraft:diamond", "S": "minecraft:feather"}),
    "greataxe": (["CDC", "CS ", " S "], {"C": "hd:dimension_crystal", "D": "minecraft:magma", "S": "minecraft:blaze_rod"}),
    "dagger": ([" C", "S "], {"C": "hd:dimension_crystal", "S": "minecraft:ender_pearl"}),
    "bow": ([" CG", "C G", " CG"], {"C": "hd:dimension_crystal", "G": "minecraft:gold_ingot"}),
    "shield": (["CDC", "CPC", " C "], {"C": "hd:dimension_crystal", "D": "minecraft:diamond", "P": "minecraft:packed_ice"}),
    "whip": (["  C", " V ", "R  "], {"C": "hd:dimension_crystal", "V": "minecraft:vine", "R": "minecraft:rose_bush"}),
    "claws": (["C C", "CIC", " L "], {"C": "hd:dimension_crystal", "I": "minecraft:iron_block", "L": "minecraft:leather"}),
}

MOVE_EN = {}


# ===========================================================================
#  BP
# ===========================================================================
def manifests():
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
            {"module_name": "@minecraft/server", "version": "1.13.0"},
            {"module_name": "@minecraft/server-ui", "version": "1.2.0"},
        ],
        "metadata": {"authors": ["Hyper Dimension Arts Project"], "license": "MIT",
                     "product_type": "addon"},
    })
    write_json(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": UUID["rp"],
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUID["rp_res"], "version": VERSION}],
        "dependencies": [{"uuid": UUID["bp"], "version": VERSION}],
        "metadata": {"authors": ["Hyper Dimension Arts Project"], "license": "MIT",
                     "product_type": "addon"},
    })


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
    for name, (dmg, dur, use, move) in STATS.items():
        comps = {
            "minecraft:max_stack_size": 1,
            "minecraft:hand_equipped": True,
            "minecraft:damage": {"value": dmg},
            "minecraft:durability": {"max_durability": dur},
            "minecraft:repairable": {"repair_items": [
                {"items": [f"{NS}:dimension_crystal"], "repair_amount": dur // 3}]},
            "minecraft:enchantable": {"slot": "bow" if name == "bow" else "sword", "value": 18},
            "minecraft:use_modifiers": {"use_duration": use, "movement_modifier": move},
            "minecraft:can_destroy_in_creative": False,
            "minecraft:should_despawn": False,
            "minecraft:glint": False,
        }
        write_json(os.path.join(d, f"{name}.item.json"),
                   item(name, f"hd_{name}", comps, "equipment", "itemGroup.name.sword"))
    write_json(os.path.join(d, "dimension_crystal.item.json"), item(
        "dimension_crystal", "hd_dimension_crystal",
        {"minecraft:max_stack_size": 64, "minecraft:glint": True}, "items"))
    write_json(os.path.join(d, "guide.item.json"), item(
        "guide", "hd_guide",
        {"minecraft:max_stack_size": 1, "minecraft:use_modifiers": {"use_duration": 0.2, "movement_modifier": 1.0},
         "minecraft:glint": True}, "items"))


def recipes():
    d = os.path.join(BP, "recipes")
    os.makedirs(d, exist_ok=True)
    for name, (pattern, keys) in RECIPES.items():
        write_json(os.path.join(d, f"{name}.json"), {
            "format_version": "1.20.10",
            "minecraft:recipe_shaped": {
                "description": {"identifier": f"{NS}:{name}"},
                "tags": ["crafting_table"],
                "pattern": pattern,
                "key": {k: {"item": v} for k, v in keys.items()},
                "result": {"item": f"{NS}:{name}", "count": 1},
            }})
    write_json(os.path.join(d, "dimension_crystal.json"), {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": f"{NS}:dimension_crystal"},
            "tags": ["crafting_table"],
            "ingredients": [{"item": "minecraft:amethyst_shard"}, {"item": "minecraft:amethyst_shard"},
                            {"item": "minecraft:diamond"}, {"item": "minecraft:ender_pearl"}],
            "result": {"item": f"{NS}:dimension_crystal", "count": 2},
        }})
    write_json(os.path.join(d, "guide.json"), {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": f"{NS}:guide"},
            "tags": ["crafting_table"],
            "ingredients": [{"item": "minecraft:book"}, {"item": f"{NS}:dimension_crystal"}],
            "result": {"item": f"{NS}:guide", "count": 1},
        }})


def entities():
    d = os.path.join(BP, "entities")
    os.makedirs(d, exist_ok=True)
    write_json(os.path.join(d, "dmg_text.json"), {
        "format_version": "1.20.80",
        "minecraft:entity": {
            "description": {"identifier": f"{NS}:dmg_text", "is_spawnable": False,
                            "is_summonable": True, "is_experimental": False},
            "component_groups": {"despawn": {"minecraft:instant_despawn": {}}},
            "components": {
                "minecraft:type_family": {"family": ["hd_text", "inanimate"]},
                "minecraft:collision_box": {"width": 0.01, "height": 0.01},
                "minecraft:physics": {"has_gravity": False, "has_collision": False},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                "minecraft:damage_sensor": {"triggers": {"cause": "all", "deals_damage": False}},
                "minecraft:health": {"value": 1, "max": 1},
                "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
                "minecraft:fire_immune": True,
                "minecraft:breathable": {"breathes_water": True, "breathes_air": True},
                "minecraft:timer": {"time": 2.0, "looping": False,
                                    "time_down_event": {"event": "hd:despawn"}},
            },
            "events": {"hd:despawn": {"add": {"component_groups": ["despawn"]}}},
        }})
    write_json(os.path.join(d, "training_dummy.json"), {
        "format_version": "1.20.80",
        "minecraft:entity": {
            "description": {"identifier": f"{NS}:training_dummy", "is_spawnable": True,
                            "is_summonable": True, "is_experimental": False},
            "components": {
                "minecraft:type_family": {"family": ["hd_dummy", "mob"]},
                "minecraft:collision_box": {"width": 0.8, "height": 2.0},
                "minecraft:health": {"value": 1000, "max": 1000},
                "minecraft:physics": {},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                "minecraft:knockback_resistance": {"value": 1.0},
                "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": True},
                "minecraft:damage_sensor": {"triggers": [
                    {"cause": "fall", "deals_damage": False},
                    {"cause": "suffocation", "deals_damage": False},
                    {"cause": "drowning", "deals_damage": False}]},
                "minecraft:fire_immune": True,
                "minecraft:breathable": {"breathes_water": True, "breathes_air": True},
                "minecraft:persistent": {},
            },
        }})


# ===========================================================================
#  RP
# ===========================================================================
def dummy_model():
    m = Model(f"geometry.{NS}.training_dummy", uv_scale=4, visible_bounds=(2, 3),
              vb_offset=(0, 1.2, 0), max_atlas=(256, 256))
    root = m.bone("root", (0, 0, 0))
    cbox(root, (0, 0.5, 0), (8, 1, 8), "wood")
    cbox(root, (0, 9, 0), (2.2, 16, 2.2), "wood")
    body = m.bone("body", (0, 14, 0), parent="root")
    cbox(body, (0, 20, 0), (8, 11, 5), "straw")
    cbox(body, (0, 21, -2.6), (5.4, 5.4, 0.3), "cloth", uv_scale=8)       # 的の布
    cbox(body, (0, 21, -2.8), (3.2, 3.2, 0.2), "target", uv_scale=10)
    cbox(body, (0, 15.2, 0), (8.6, 1.4, 5.6), "rope", uv_scale=6)
    cbox(body, (0, 24.6, 0), (16, 1.6, 1.6), "wood")                      # 腕木
    for s in (-1, 1):
        cbox(body, (s * 8.4, 22.8, 0), (2.0, 3.6, 2.0), "straw")
        cbox(body, (s * 6.8, 24.6, 0), (0.6, 2.0, 2.0), "rope", uv_scale=6)
    cbox(body, (0, 29.5, 0), (6, 6, 6), "sack")                           # 頭の麻袋
    cbox(body, (0, 26.7, 0), (3.2, 0.8, 3.2), "rope", uv_scale=6)
    cbox(body, (-1.4, 30.2, -3.05), (1.0, 1.0, 0.1), "ink", uv_scale=10)
    cbox(body, (1.4, 30.2, -3.05), (1.0, 1.0, 0.1), "ink", uv_scale=10)
    cbox(body, (0, 28.2, -3.05), (2.6, 0.5, 0.1), "ink", uv_scale=10)
    m.pack()
    return m


DUMMY_STYLES = {
    "wood": {"kind": "wood", "base": (132, 94, 58), "line": (60, 40, 24)},
    "straw": {"kind": "straw", "base": (214, 182, 104), "line": (120, 96, 44)},
    "cloth": {"kind": "cloth", "base": (220, 214, 196), "outline": False},
    "target": {"kind": "gem", "glow": (230, 60, 50), "deep": (130, 20, 20), "outline": False,
               "opaque": True},   # entity_alphatest では低アルファが抜けるので不透明に
    "rope": {"kind": "wrap", "base": (120, 92, 54), "strap": (176, 142, 88), "skin": (150, 116, 70),
             "period": 4, "outline": False},
    "sack": {"kind": "cloth", "base": (190, 168, 124), "outline": True, "line": (110, 92, 60)},
    "ink": {"kind": "flat", "base": (30, 26, 24), "outline": False},
}


def client():
    m = dummy_model()
    m.write(os.path.join(RP, "models", "entity", "hd_training_dummy.geo.json"))
    p = HDPainter(m.tex_w, m.tex_h, 77)
    p.paint_model(m, DUMMY_STYLES)
    # 的の中心だけは光らせない（普通の布の赤丸）
    p.save(os.path.join(RP, "textures", "entity", "hd", "training_dummy.png"))
    write_json(os.path.join(RP, "models", "entity", "hd_empty.geo.json"), {
        "format_version": "1.12.0",
        "minecraft:geometry": [{"description": {"identifier": f"geometry.{NS}.empty",
                                                "texture_width": 16, "texture_height": 16,
                                                "visible_bounds_width": 1, "visible_bounds_height": 1,
                                                "visible_bounds_offset": [0, 0.5, 0]},
                                "bones": [{"name": "root", "pivot": [0, 0, 0]}]}]})
    ent = os.path.join(RP, "entity")
    write_json(os.path.join(ent, "training_dummy.entity.json"), {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": f"{NS}:training_dummy",
            "materials": {"default": "entity_alphatest"},
            "textures": {"default": "textures/entity/hd/training_dummy"},
            "geometry": {"default": f"geometry.{NS}.training_dummy"},
            "animations": {"wobble": f"animation.{NS}.dummy.wobble"},
            "scripts": {"animate": ["wobble"]},
            "render_controllers": ["controller.render.default"],
            "spawn_egg": {"base_color": "#C9A15E", "overlay_color": "#3FA9FF"},
        }}})
    write_json(os.path.join(ent, "dmg_text.entity.json"), {
        "format_version": "1.10.0",
        "minecraft:client_entity": {"description": {
            "identifier": f"{NS}:dmg_text",
            "materials": {"default": "entity_alphatest"},
            "textures": {"default": "textures/entity/hd/training_dummy"},
            "geometry": {"default": f"geometry.{NS}.empty"},
            "render_controllers": ["controller.render.default"],
        }}})
    write_json(os.path.join(RP, "animations", "hd_dummy.animation.json"), {
        "format_version": "1.8.0",
        "animations": {f"animation.{NS}.dummy.wobble": {"loop": True, "bones": {"body": {
            "rotation": ["math.sin(q.hurt_time * 95.0) * q.hurt_time * 2.4", 0,
                         "math.cos(q.hurt_time * 70.0) * q.hurt_time * 1.2"]}}}}})


# ---------------------------------------------------------------------------
#  アイコン（32x32）: 次元結晶・指南書
# ---------------------------------------------------------------------------
def _supersample(draw_fn, size=32, ss=8):
    img = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(img), size * ss, img)
    img = img.resize((size, size), Image.LANCZOS)
    a = img.split()[3].point(lambda v: 255 if v > 100 else 0)
    img.putalpha(a)
    ring = Image.new("RGBA", img.size, (14, 12, 20, 255))
    ring.putalpha(a.filter(ImageFilter.MaxFilter(3)))
    ring.alpha_composite(img)
    return ring


def icon_crystal():
    def fn(d, S, img):
        cx = S / 2
        pts = [(cx, S * 0.06), (S * 0.78, S * 0.40), (cx, S * 0.94), (S * 0.22, S * 0.40)]
        d.polygon(pts, fill=(120, 190, 255, 255))
        d.polygon([(cx, S * 0.06), (S * 0.78, S * 0.40), (cx, S * 0.48)], fill=(200, 236, 255, 255))
        d.polygon([(cx, S * 0.06), (S * 0.22, S * 0.40), (cx, S * 0.48)], fill=(150, 210, 255, 255))
        d.polygon([(S * 0.22, S * 0.40), (cx, S * 0.48), (cx, S * 0.94)], fill=(70, 120, 220, 255))
        d.polygon([(S * 0.78, S * 0.40), (cx, S * 0.48), (cx, S * 0.94)], fill=(100, 80, 210, 255))
        d.line([(cx, S * 0.48), (cx, S * 0.9)], fill=(230, 245, 255, 255), width=S // 40)
        d.ellipse([cx - S * 0.05, S * 0.2 - S * 0.05, cx + S * 0.05, S * 0.2 + S * 0.05], fill=(255, 255, 255, 255))
    return _supersample(fn)


def icon_guide():
    def fn(d, S, img):
        d.rounded_rectangle([S * 0.14, S * 0.10, S * 0.86, S * 0.92], radius=S * 0.06, fill=(36, 40, 76, 255))
        d.rectangle([S * 0.14, S * 0.10, S * 0.24, S * 0.92], fill=(214, 168, 70, 255))
        d.rectangle([S * 0.78, S * 0.14, S * 0.84, S * 0.88], fill=(236, 230, 210, 255))
        c = (S * 0.53, S * 0.50)
        r = S * 0.22
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=(120, 210, 255, 255), width=S // 30)
        pts = [(c[0] + r * 0.85 * math.cos(-math.pi / 2 + i * 2 * math.pi / 6),
                c[1] + r * 0.85 * math.sin(-math.pi / 2 + i * 2 * math.pi / 6)) for i in range(6)]
        for i in range(6):
            d.line([pts[i], pts[(i + 2) % 6]], fill=(180, 236, 255, 255), width=S // 46)
        d.ellipse([c[0] - S * 0.04, c[1] - S * 0.04, c[0] + S * 0.04, c[1] + S * 0.04], fill=(255, 255, 255, 255))
    return _supersample(fn)


def item_atlas():
    icons = os.path.join(RP, "textures", "items", "hd")
    os.makedirs(icons, exist_ok=True)
    icon_crystal().save(os.path.join(icons, "dimension_crystal.png"))
    icon_guide().save(os.path.join(icons, "guide.png"))
    data = {f"hd_{n}": {"textures": f"textures/items/hd/{n}"} for n in WEAPONS}
    data["hd_dimension_crystal"] = {"textures": "textures/items/hd/dimension_crystal"}
    data["hd_guide"] = {"textures": "textures/items/hd/guide"}
    write_json(os.path.join(RP, "textures", "item_texture.json"),
               {"resource_pack_name": "hyperdim", "texture_name": "atlas.items", "texture_data": data})


# ---------------------------------------------------------------------------
#  パックアイコン: 交差する二振りと次元の輪
# ---------------------------------------------------------------------------
def pack_icon():
    S = 256
    y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S
    r = np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2)
    bg = np.zeros((S, S, 4), np.float32)
    top = np.array([18, 22, 52]); bot = np.array([60, 20, 80])
    for i in range(3):
        bg[..., i] = top[i] + (bot[i] - top[i]) * y
    glow = np.clip(1 - r * 2.2, 0, 1) ** 2
    bg[..., 0] += glow * 60; bg[..., 1] += glow * 140; bg[..., 2] += glow * 255
    bg[..., 3] = 255
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    d.ellipse([28, 28, 228, 228], outline=(140, 220, 255, 255), width=5)
    d.ellipse([44, 44, 212, 212], outline=(90, 160, 255, 160), width=2)
    for i in range(24):
        a = i / 24 * 2 * math.pi
        d.line([(128 + 100 * math.cos(a), 128 + 100 * math.sin(a)),
                (128 + 110 * math.cos(a), 128 + 110 * math.sin(a))], fill=(170, 230, 255, 255), width=3)
    icons = os.path.join(RP, "textures", "items", "hd")
    for name, ang, off in (("greatsword", 0, (-6, 0)), ("twinblades", 90, (6, 0))):
        ic = Image.open(os.path.join(icons, f"{name}.png")).resize((176, 176), Image.NEAREST)
        ic = ic.rotate(ang, expand=False)
        img.alpha_composite(ic, (40 + off[0], 40 + off[1]))
    star = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(star)
    sd.polygon([(128, 92), (136, 120), (164, 128), (136, 136), (128, 164), (120, 136), (92, 128), (120, 120)],
               fill=(255, 255, 255, 230))
    img.alpha_composite(star.filter(ImageFilter.GaussianBlur(1.2)))
    for pack in (BP, RP):
        img.convert("RGB").save(os.path.join(pack, "pack_icon.png"))


# ---------------------------------------------------------------------------
#  言語
# ---------------------------------------------------------------------------
def lang():
    from gen_hd_lang import LANGS
    for pack in (BP, RP):
        d = os.path.join(pack, "texts")
        os.makedirs(d, exist_ok=True)
        write_json(os.path.join(d, "languages.json"), list(LANGS))
        for code, lines in LANGS.items():
            with open(os.path.join(d, f"{code}.lang"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")


def main():
    manifests()
    items()
    recipes()
    entities()
    client()
    item_atlas()
    pack_icon()
    lang()
    print("  packs: items/recipes/entities/client/lang/manifests written")


if __name__ == "__main__":
    main()
