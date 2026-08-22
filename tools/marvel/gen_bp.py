# -*- coding: utf-8 -*-
"""ビヘイビアパック — エンティティ・アイテム・ルート・レシピ・スポーン。

AI の考え方
-----------
* ブラザーフッドは ``brotherhood`` ファミリ。プレイヤーを守り、
  ``sentinel`` / ``mrd`` を狙う。
* センチネルは ``mutant`` ファミリ（＝変身中のプレイヤーとブラザーフッド）を狙う。
* 技の実体（鉄片・瓦礫・障壁など）は ``marvel_prop`` ファミリで、
  AI を持たずスクリプトが動かす。
"""
from __future__ import annotations

import _path  # noqa: F401

import contract as K  # noqa: E402
import icons  # noqa: E402
from common import write_json  # noqa: E402

F = K.FAMILIES


# ===========================================================================
#  エンティティ
# ===========================================================================
def base_entity(ident, families, health, damage, speed, width, height,
                loot=None, groups=None, components=None, events=None,
                summonable=True, spawnable=True, fire_immune=False,
                knockback_resist=0.0, follow=24.0, xp=8):
    comps = {
        "minecraft:type_family": {"family": list(families)},
        "minecraft:collision_box": {"width": width, "height": height},
        "minecraft:health": {"value": health, "max": health},
        "minecraft:attack": {"damage": damage},
        "minecraft:movement": {"value": speed},
        "minecraft:navigation.walk": {
            "can_path_over_water": True, "avoid_water": True,
            "can_pass_doors": True, "can_open_doors": True},
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True,
                               "is_pushable_by_piston": True},
        "minecraft:knockback_resistance": {"value": knockback_resist},
        "minecraft:follow_range": {"value": follow, "max": follow},
        "minecraft:nameable": {},
        "minecraft:experience_reward": {"on_death": xp},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.look_at_player": {
            "priority": 9, "look_distance": 10, "probability": 0.02},
        "minecraft:behavior.random_look_around": {"priority": 10},
    }
    if fire_immune:
        comps["minecraft:fire_immune"] = {}
    if loot:
        comps["minecraft:loot"] = {"table": loot}
    if components:
        comps.update(components)
    doc = {
        "format_version": "1.21.0",
        "minecraft:entity": {
            "description": {
                "identifier": ident,
                "is_spawnable": spawnable,
                "is_summonable": summonable,
                "is_experimental": False,
            },
            "component_groups": groups or {},
            "components": comps,
            "events": events or {},
        },
    }
    return doc


#: 技の演出中に mark_variant を切り替えるための共通イベント／グループ。
def action_groups(timers=((1, 0.5), (2, 1.4), (3, 0.35), (4, 3.2), (5, 1.8))):
    groups = {}
    events = {f"{K.NS}:calm": {"remove": {"component_groups":
                                          [f"{K.NS}:act{v}" for v, _ in timers]}}}
    for variant, seconds in timers:
        name = f"{K.NS}:act{variant}"
        groups[name] = {
            "minecraft:mark_variant": {"value": variant},
            "minecraft:timer": {"looping": False, "time": seconds,
                                "time_down_event": {"event": f"{K.NS}:calm"}},
        }
        events[f"{K.NS}:act{variant}"] = {
            "remove": {"component_groups":
                       [f"{K.NS}:act{v}" for v, _ in timers if v != variant]},
            "add": {"component_groups": [name]},
        }
    return groups, events


def hostile_to(families, priority=4):
    return {
        "minecraft:behavior.nearest_attackable_target": {
            "priority": priority,
            "must_see": True,
            "reselect_targets": True,
            "within_radius": 28.0,
            "entity_types": [
                {"filters": {"any_of": [{"test": "is_family", "subject": "other",
                                         "value": f} for f in families]},
                 "max_dist": 28} for _ in (0,)
            ],
        },
        "minecraft:behavior.melee_attack": {"priority": 5, "track_target": True,
                                            "speed_multiplier": 1.1},
    }


def wander(priority=7, speed=1.0):
    return {
        "minecraft:behavior.random_stroll": {"priority": priority,
                                             "speed_multiplier": speed},
    }


def character_entity(key: str) -> dict:
    c = K.CHARACTERS[key]
    px = c["cm"] / 100.0
    width = max(0.6, px * 0.32)
    height = max(1.2, px * 0.97)
    groups, events = action_groups()

    if c["role"] == "enemy":
        families = [F["sentinel"] if "sentinel" in key else F["mrd"],
                    "monster", "mob"]
        targets = [F["mutant"], F["brotherhood"], "player"]
        knock = 0.85 if "sentinel" in key else 0.1
        comps = {}
        comps.update(hostile_to(targets))
        comps.update(wander(7, 0.9))
        if key == "sentinel_drone":
            comps["minecraft:navigation.hover"] = {"can_path_over_water": True}
            comps["minecraft:movement.hover"] = {}
            comps["minecraft:behavior.random_hover"] = {
                "priority": 8, "xz_dist": 8, "y_dist": 4,
                "y_offset": 1.0, "interval": 60, "hover_height": [2.0, 5.0]}
            comps.pop("minecraft:navigation.walk", None)
        comps["minecraft:damage_sensor"] = {"triggers": [{
            "on_damage": {"filters": {"test": "is_family", "subject": "other",
                                      "value": F["sentinel"]}},
            "deals_damage": False}]}
        loot = f"loot_tables/entities/{key}.json"
    else:
        families = [F["mutant"], F["brotherhood"], "mob"]
        targets = [F["sentinel"], F["mrd"], "monster"]
        knock = 0.5 if key in ("juggernaut", "blob") else 0.15
        comps = {}
        comps.update(hostile_to(targets, 4))
        comps.update(wander(7, 1.0))
        comps["minecraft:behavior.follow_owner"] = {
            "priority": 3, "speed_multiplier": 1.2,
            "start_distance": 8, "stop_distance": 3}
        comps["minecraft:is_tamed"] = {}
        comps["minecraft:tameable"] = {"probability": 1.0}
        comps["minecraft:behavior.owner_hurt_by_target"] = {"priority": 1}
        comps["minecraft:behavior.owner_hurt_target"] = {"priority": 2}
        comps["minecraft:persistent"] = {}
        loot = f"loot_tables/entities/{key}.json"

    if key == K.MAGNETO:
        comps["minecraft:behavior.hurt_by_target"] = {"priority": 1}

    doc = base_entity(
        K.eid(key), families, c["health"], c["damage"], c["speed"],
        round(width, 2), round(height, 2), loot=loot, groups=groups,
        components=comps, events=events,
        knockback_resist=knock, fire_immune=(key in ("pyro", "juggernaut")),
        follow=32.0, xp=max(5, int(c["health"] / 18)))
    return doc


def prop_entity(key: str) -> dict:
    """技の実体。AI は持たず、スクリプトが位置を書き換える。"""
    projectile = key in ("metal_shard", "debris", "hex_bolt", "fire_bolt",
                         "sentinel_beam")
    big = key in ("barrier_dome", "ruin_sphere", "iron_cage")
    comps = {
        "minecraft:type_family": {"family": [F["prop"], "inanimate"]},
        "minecraft:collision_box": {"width": 3.0 if big else 0.4,
                                    "height": 4.0 if big else 0.4},
        "minecraft:health": {"value": 400, "max": 400},
        "minecraft:physics": {"has_gravity": False, "has_collision": False},
        "minecraft:pushable": {"is_pushable": False,
                               "is_pushable_by_piston": False},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:damage_sensor": {"triggers": [{"deals_damage": False,
                                                  "on_damage": {}}]},
        "minecraft:fire_immune": {},
        "minecraft:conditional_bandwidth_optimization": {},
    }
    if key == "steel_platform":
        comps["minecraft:collision_box"] = {"width": 2.2, "height": 0.6}
        comps["minecraft:physics"] = {"has_gravity": False,
                                      "has_collision": True}
        comps["minecraft:rideable"] = {
            "seat_count": 1, "family_types": ["player", F["mutant"]],
            "interact_text": "action.interact.ride",
            "seats": [{"position": [0, 0.4, 0]}]}
        comps["minecraft:input_ground_controlled"] = {}
    if projectile:
        comps["minecraft:timer"] = {"looping": False, "time": 6.0,
                                    "time_down_event": {"event": f"{K.NS}:expire"}}
    else:
        comps["minecraft:timer"] = {"looping": False, "time": 14.0,
                                    "time_down_event": {"event": f"{K.NS}:expire"}}
    return {
        "format_version": "1.21.0",
        "minecraft:entity": {
            "description": {"identifier": K.eid(key), "is_spawnable": False,
                            "is_summonable": True, "is_experimental": False},
            "component_groups": {
                f"{K.NS}:gone": {"minecraft:instant_despawn": {}}},
            "components": comps,
            "events": {f"{K.NS}:expire": {
                "add": {"component_groups": [f"{K.NS}:gone"]}}},
        },
    }


# ===========================================================================
#  アイテム
# ===========================================================================
CATEGORY = {"items": "itemGroup.name.miscFood",
            "equipment": "itemGroup.name.helmet"}


def item_doc(key: str, spec: dict) -> dict:
    comps = {
        "minecraft:icon": {"texture": spec.get("icon", key)},
        "minecraft:max_stack_size": spec.get("stack", 1),
        "minecraft:should_despawn": False,
        "minecraft:display_name": {"value": f"item.{K.eid(key)}"},
    }
    if spec.get("glint"):
        comps["minecraft:glint"] = True
    if spec.get("hand", True):
        comps["minecraft:hand_equipped"] = True
    if spec.get("wearable"):
        # 変身体は頭スロットに装備して初めて描画される。これが無いと
        # setEquipment が黙って失敗し、三人称の姿も技の構えも一切出ない。
        comps["minecraft:wearable"] = {"slot": spec["wearable"], "protection": 0}
        comps["minecraft:allow_off_hand"] = False
    desc = {"identifier": K.eid(key)}
    if not spec.get("hidden"):
        desc["menu_category"] = {
            "category": spec.get("category", "items"),
            "group": CATEGORY.get(spec.get("category", "items"),
                                  "itemGroup.name.miscFood"),
        }
    if spec.get("food"):
        comps["minecraft:food"] = {"nutrition": 0, "can_always_eat": True}
        comps["minecraft:use_modifiers"] = {"use_duration": 1.6,
                                            "movement_modifier": 0.35}
    return {"format_version": "1.21.20",
            "minecraft:item": {"description": desc, "components": comps}}


def all_items() -> dict:
    out = {}
    for key, spec in K.ITEMS.items():
        out[key] = dict(spec)
    for name, spec in K.TECHNIQUES.items():
        out[spec["item"]] = dict(
            ja=spec["ja"], en=spec["en"], icon=spec["icon"], stack=1,
            glint=spec.get("ultimate", False), category="equipment",
            hand=True, desc_ja=spec["desc_ja"], tech=name)
    for character, tech, _g, _n in K.form_variants():
        key = K.form_key(character, tech)
        out[key] = dict(ja=f"{K.CHARACTERS[character]['ja']}の体",
                        en=f"{K.CHARACTERS[character]['en']} Form",
                        icon=key, stack=1, hidden=True, hand=False,
                        wearable="slot.armor.head")
    return out


# ===========================================================================
#  ルート / レシピ / スポーン
# ===========================================================================
def loot_table(entries):
    return {"pools": [{"rolls": {"min": e.get("min", 1), "max": e.get("max", 1)},
                       "entries": [{"type": "item", "name": e["item"],
                                    "weight": e.get("weight", 1)}]}
                      for e in entries]}


def shaped(result, pattern, key, count=1):
    return {"format_version": "1.20.10", "minecraft:recipe_shaped": {
        "description": {"identifier": f"{result}_recipe"},
        "tags": ["crafting_table"],
        "pattern": pattern,
        "key": {k: {"item": v} for k, v in key.items()},
        "result": {"item": result, "count": count},
    }}


def spawn_rule(ident, biomes, weight, minc, maxc, brightness=(0, 7)):
    return {"format_version": "1.8.0", "minecraft:spawn_rules": {
        "description": {"identifier": ident, "population_control": "monster"},
        "conditions": [{
            "minecraft:spawns_on_surface": {},
            "minecraft:brightness_filter": {"min": brightness[0],
                                            "max": brightness[1],
                                            "adjust_for_weather": True},
            "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
            "minecraft:weight": {"default": weight},
            "minecraft:herd": {"min_size": minc, "max_size": maxc},
            "minecraft:biome_filter": {"test": "has_biome_tag", "operator": "==",
                                       "value": biomes},
        }],
    }}


def main() -> None:
    K.ensure_dirs()
    print("behaviour pack:")

    # ---- エンティティ ---------------------------------------------------
    for key in K.ALL_CHARACTERS:
        write_json(f"{K.BP}/entities/{key}.entity.json", character_entity(key))
    for key in K.PROP_ENTITIES:
        write_json(f"{K.BP}/entities/{key}.entity.json", prop_entity(key))
    print(f"  {len(K.ENTITY_KEYS)} entities")

    # ---- ルートテーブル --------------------------------------------------
    drops = {
        "magneto": [dict(item=K.eid("magneto_helmet")),
                    dict(item=K.eid("magnetic_alloy"), min=2, max=5)],
        "sentinel": [dict(item=K.eid("sentinel_core")),
                     dict(item=K.eid("metal_scrap"), min=3, max=8)],
        "prime_sentinel": [dict(item=K.eid("sentinel_core"), min=2, max=4),
                           dict(item=K.eid("adamantium_ingot")),
                           dict(item=K.eid("metal_scrap"), min=6, max=14)],
        "sentinel_drone": [dict(item=K.eid("metal_scrap"), min=1, max=3)],
        "mrd_trooper": [dict(item=K.eid("metal_scrap"), min=1, max=3),
                        dict(item="minecraft:iron_ingot", min=0, max=2)],
    }
    for key in K.ALL_CHARACTERS:
        entries = drops.get(key, [dict(item=K.eid("metal_scrap"), min=0, max=2)])
        write_json(f"{K.BP}/loot_tables/entities/{key}.json", loot_table(entries))

    # ---- アイテム ---------------------------------------------------------
    items = all_items()
    for key, spec in items.items():
        write_json(f"{K.BP}/items/{key}.item.json", item_doc(key, spec))
    print(f"  {len(items)} items")

    # ---- アイコン + アトラス ------------------------------------------------
    atlas = icons.build_all()
    # 変身体アイテムのうち、magneto_form だけは form_variants に含まれるので
    # icons 側で描かれている。念のため取りこぼしを検出しておく。
    for key in items:
        if key not in atlas:
            raise SystemExit(f"アイコンが無いアイテム: {key}")
    write_json(f"{K.RP}/textures/item_texture.json", {
        "resource_pack_name": K.NS, "texture_name": "atlas.items",
        "texture_data": dict(sorted(atlas.items())),
    })
    print(f"  {len(atlas)} item icons")

    # ---- レシピ -------------------------------------------------------------
    write_json(f"{K.BP}/recipes/magnetic_alloy.json", shaped(
        K.eid("magnetic_alloy"), ["SIS", "IRI", "SIS"],
        {"S": K.eid("metal_scrap"), "I": "minecraft:iron_ingot",
         "R": "minecraft:redstone"}, count=2))
    write_json(f"{K.BP}/recipes/magneto_helmet.json", shaped(
        K.eid("magneto_helmet"), ["AMA", "M M", "   "],
        {"A": K.eid("magnetic_alloy"), "M": K.eid("adamantium_ingot")}))
    write_json(f"{K.BP}/recipes/cerebro.json", shaped(
        K.eid("cerebro"), ["AAA", "GCG", "   "],
        {"A": K.eid("magnetic_alloy"), "G": "minecraft:glass",
         "C": K.eid("sentinel_core")}))
    write_json(f"{K.BP}/recipes/brotherhood_pin.json", shaped(
        K.eid("brotherhood_pin"), ["  A", " A ", "R  "],
        {"A": K.eid("magnetic_alloy"), "R": "minecraft:redstone"}))
    write_json(f"{K.BP}/recipes/brotherhood_beacon.json", shaped(
        K.eid("brotherhood_beacon"), [" P ", "SAS", " S "],
        {"P": K.eid("brotherhood_pin"), "S": K.eid("metal_scrap"),
         "A": K.eid("magnetic_alloy")}, count=4))
    write_json(f"{K.BP}/recipes/x_gene.json", shaped(
        K.eid("x_gene"), [" G ", "GCG", " A "],
        {"G": "minecraft:glass_bottle", "C": K.eid("sentinel_core"),
         "A": K.eid("magnetic_alloy")}))
    write_json(f"{K.BP}/recipes/adamantium_ingot.json", shaped(
        K.eid("adamantium_ingot"), ["ANA", "NCN", "ANA"],
        {"A": K.eid("magnetic_alloy"), "N": "minecraft:netherite_scrap",
         "C": K.eid("sentinel_core")}))
    # 技アイテムは磁性合金 + それぞれの触媒で作る
    catalyst = {
        "repulse": "minecraft:iron_ingot", "attract": "minecraft:iron_ingot",
        "disarm": "minecraft:shears", "lance": "minecraft:iron_sword",
        "flight": "minecraft:feather", "sight": "minecraft:spyglass",
        "barrier": "minecraft:shield", "shard_storm": "minecraft:iron_nugget",
        "iron_bind": "minecraft:iron_bars", "crush": "minecraft:anvil",
        "uprising": "minecraft:iron_pickaxe", "emp": "minecraft:redstone_block",
        "polarity": "minecraft:ender_pearl", "throne": "minecraft:iron_block",
        "sphere": "minecraft:nether_star",
    }
    for name, spec in K.TECHNIQUES.items():
        write_json(f"{K.BP}/recipes/{spec['item']}.json", shaped(
            K.eid(spec["item"]), [" A ", "ACA", " A "],
            {"A": K.eid("magnetic_alloy"), "C": catalyst[name]}))

    # ---- スポーン規則 -------------------------------------------------------
    write_json(f"{K.BP}/spawn_rules/sentinel.json", spawn_rule(
        K.eid("sentinel"), "overworld", 3, 1, 1))
    write_json(f"{K.BP}/spawn_rules/sentinel_drone.json", spawn_rule(
        K.eid("sentinel_drone"), "overworld", 8, 1, 3, (0, 15)))
    write_json(f"{K.BP}/spawn_rules/mrd_trooper.json", spawn_rule(
        K.eid("mrd_trooper"), "overworld", 6, 2, 4))
    print("  loot / recipes / spawn rules")


if __name__ == "__main__":
    main()
