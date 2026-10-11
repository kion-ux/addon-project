# -*- coding: utf-8 -*-
"""ビヘイビア／リソースパックのデータ一式。

アイテム・エンティティ（巨人 4 級・調査兵団 10 人）・スポーンルール・レシピ・
クライアント定義・レンダーコントローラ・アイテムアトラスとアイコン・マニフェスト・
パックアイコン。言語ファイルは aot_lang.py。
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

import aot_common as C
from aot_common import BP, BODIES, MIN_ENGINE, NS, RP, SKINS, SOLDIERS, TITANS, VERSION, write_json
import gen_aot_anim as GA
from aot_models import titan_metrics

UUID = {
    "bp": "975c2174-72ed-49f1-a1a3-f8a44773beb5",
    "bp_data": "e10850df-0dd0-46a8-b84d-2e8a4cbf279b",
    "bp_script": "3a5768ee-7a68-43c8-b121-012fccfba24f",
    "rp": "209aeeab-4ffe-4c2b-9c77-f02c03d74d60",
    "rp_res": "1353fd0e-d72b-497d-abb5-34c71f4f30dd",
}
ITEM_FMT = "1.21.20"
ENTITY_FMT = "1.21.0"
TITAN_STATES = ["idle", "grab", "eat", "kneel", "sleep", "dying", "leap", "swat", "blind"]
SOLDIER_STATES = ["idle", "fly", "slash", "grabbed"]


# ===========================================================================
#  マニフェスト
# ===========================================================================
def manifests():
    meta = {"authors": ["Attack on Titan Fan Add-on Project"], "license": "MIT",
            "product_type": "addon"}
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
def item(ident, comps, category="equipment", group=None):
    desc = {"identifier": f"{NS}:{ident}", "menu_category": {"category": category}}
    if group:
        desc["menu_category"]["group"] = group
    base = {"minecraft:icon": {"texture": f"aot_{ident}"},
            "minecraft:display_name": {"value": f"item.{NS}:{ident}"}}
    base.update(comps)
    return {"format_version": ITEM_FMT, "minecraft:item": {"description": desc, "components": base}}


WEARABLES = {
    # id: (スロット, 防御, 耐久, エンチャントの枠)
    "odm_gear": ("slot.armor.legs", 4, 640, "armor_legs"),
    "survey_jacket": ("slot.armor.chest", 5, 520, "armor_torso"),
    "survey_boots": ("slot.armor.feet", 2, 420, "armor_feet"),
}


def items():
    d = os.path.join(BP, "items")
    os.makedirs(d, exist_ok=True)
    steel = f"{NS}:hardened_steel"
    write_json(os.path.join(d, "odm_blades.item.json"), item("odm_blades", {
        "minecraft:max_stack_size": 1,
        "minecraft:hand_equipped": True,
        "minecraft:damage": {"value": 7},
        # 刃こぼれはスクリプトが管理する（巨人を斬るたびに減り、限界で替え刃に交換）
        "minecraft:durability": {"max_durability": 60},
        "minecraft:repairable": {"repair_items": [{"items": [steel], "repair_amount": 30}]},
        "minecraft:enchantable": {"slot": "sword", "value": 14},
        # 押している間ワイヤーを巻き取る。使用中も足は遅くならない
        "minecraft:use_modifiers": {"use_duration": 600, "movement_modifier": 1.0},
        "minecraft:can_destroy_in_creative": False,
        "minecraft:should_despawn": False,
    }, "equipment", "itemGroup.name.sword"))
    write_json(os.path.join(d, "thunder_spear.item.json"), item("thunder_spear", {
        "minecraft:max_stack_size": 8,
        "minecraft:hand_equipped": True,
        "minecraft:use_modifiers": {"use_duration": 0.25, "movement_modifier": 1.0},
        "minecraft:should_despawn": False,
    }, "equipment", "itemGroup.name.sword"))
    write_json(os.path.join(d, "gas_canister.item.json"), item("gas_canister", {
        "minecraft:max_stack_size": 16,
        "minecraft:use_modifiers": {"use_duration": 0.6, "movement_modifier": 0.6},
        "minecraft:use_animation": "drink",
    }, "items"))
    write_json(os.path.join(d, "spare_blades.item.json"), item("spare_blades", {
        "minecraft:max_stack_size": 32}, "items"))
    write_json(os.path.join(d, "hardened_steel.item.json"), item("hardened_steel", {
        "minecraft:max_stack_size": 64}, "items"))
    write_json(os.path.join(d, "survey_journal.item.json"), item("survey_journal", {
        "minecraft:max_stack_size": 1,
        "minecraft:use_modifiers": {"use_duration": 0.2, "movement_modifier": 1.0},
        "minecraft:glint": False}, "items"))
    write_json(os.path.join(d, "flare_gun.item.json"), item("flare_gun", {
        "minecraft:max_stack_size": 1,
        "minecraft:hand_equipped": True,
        "minecraft:durability": {"max_durability": 64},
        "minecraft:use_modifiers": {"use_duration": 0.2, "movement_modifier": 1.0},
    }, "equipment", "itemGroup.name.sword"))
    for ident, (slot, prot, dur, ench) in WEARABLES.items():
        write_json(os.path.join(d, f"{ident}.item.json"), item(ident, {
            "minecraft:max_stack_size": 1,
            "minecraft:wearable": {"slot": slot, "protection": prot},
            "minecraft:durability": {"max_durability": dur},
            "minecraft:repairable": {"repair_items": [
                {"items": [steel if ident == "odm_gear" else "minecraft:leather"],
                 "repair_amount": dur // 3}]},
            "minecraft:enchantable": {"slot": ench, "value": 12},
        }, "equipment", "itemGroup.name.chestplate" if "jacket" in ident else None))


# ===========================================================================
#  エンティティ: 巨人
# ===========================================================================
def titan_entity(key):
    height, hp, dmg, spd, coll, hit, grabs, _xp = TITANS[key]
    abnormal = key == "titan_abnormal"
    targets = {"any_of": [
        {"test": "is_family", "subject": "other", "value": "player"},
        {"test": "is_family", "subject": "other", "value": "villager"},
        {"test": "is_family", "subject": "other", "value": "wandering_trader"},
        {"test": "is_family", "subject": "other", "value": "aot_soldier"},
    ]}
    hunter = {
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.delayed_attack": {
            "priority": 2, "attack_once": False, "track_target": True,
            "require_complete_path": False, "random_stop_interval": 0,
            "reach_multiplier": round(max(1.6, (hit[0] * 1.15 + 1.2) / coll[0]), 2),
            "speed_multiplier": 1.3 if abnormal else 1.1,
            "attack_duration": 1.0, "hit_delay_pct": 0.55},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 3, "must_see": True, "reselect_targets": True,
            "must_see_forget_duration": 10.0, "within_radius": 40,
            "entity_types": [{"filters": targets, "max_dist": 40}]},
        "minecraft:behavior.move_towards_target": {"priority": 4, "speed_multiplier": 1.0,
                                                   "within_radius": 40},
        "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.7,
                                             "xz_dist": 16, "y_dist": 4},
        "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 24,
                                              "probability": 0.04},
        "minecraft:behavior.random_look_around": {"priority": 8},
    }
    groups = {
        "aot:hunter": hunter,
        "aot:dying": {
            "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": False}]},
            "minecraft:timer": {"looping": False, "time": 4.5,
                                "time_down_event": {"event": "aot:evaporate"}},
        },
        "aot:despawn": {"minecraft:instant_despawn": {}},
    }
    for i in range(len(BODIES)):
        groups[f"aot:body{i}"] = {"minecraft:variant": {"value": i}}
    for k in range(SKINS):
        groups[f"aot:skin{k}"] = {"minecraft:skin_id": {"value": k}}
    comps = {
        "minecraft:type_family": {"family": ["titan", "pure_titan", "monster", "mob"]
                                  + (["abnormal"] if abnormal else [])},
        "minecraft:collision_box": {"width": coll[0], "height": coll[1]},
        "minecraft:custom_hit_test": {"hitboxes": [
            {"width": hit[0], "height": hit[1], "pivot": [0, round(hit[1] / 2, 2), 0]}]},
        "minecraft:health": {"value": hp, "max": hp},
        "minecraft:attack": {"damage": dmg},
        "minecraft:movement": {"value": spd},
        "minecraft:movement.basic": {},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": False,
                                      "can_walk_in_lava": False, "can_break_doors": True,
                                      "avoid_damage_blocks": True},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
        "minecraft:knockback_resistance": {"value": 1.0 if height > 6 else 0.7},
        "minecraft:follow_range": {"value": 48, "max": 48},
        "minecraft:nameable": {},
        "minecraft:variant": {"value": 0},
        "minecraft:skin_id": {"value": 0},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0,
                                 "breathes_water": True, "breathes_air": True},
        "minecraft:despawn": {"despawn_from_distance": {"min_distance": 64, "max_distance": 128}},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:experience_reward": {"on_death": "0"},
        "minecraft:break_blocks": {"breakable_blocks": [
            "minecraft:oak_leaves", "minecraft:spruce_leaves", "minecraft:birch_leaves",
            "minecraft:jungle_leaves", "minecraft:acacia_leaves", "minecraft:dark_oak_leaves",
            "minecraft:azalea_leaves", "minecraft:azalea_leaves_flowered",
            "minecraft:mangrove_leaves", "minecraft:cherry_leaves", "minecraft:vine"]},
        "minecraft:damage_sensor": {"triggers": [
            {"cause": "fall", "deals_damage": False},
            {"cause": "suffocation", "deals_damage": False},
            {"cause": "drowning", "deals_damage": False},
            {"cause": "fly_into_wall", "deals_damage": False},
            {"on_damage": {"filters": {"test": "is_family", "subject": "other", "value": "titan"}},
             "deals_damage": False},
            # 体は斬っても再生する。効くのは 1/4（爆発と炎は半分ほど）。うなじと雷槍は
            # スクリプトが cause=override で与えるので、ここには掛からない
            {"cause": "entity_attack", "damage_multiplier": 0.25},
            {"cause": "projectile", "damage_multiplier": 0.25},
            {"cause": "thorns", "damage_multiplier": 0.25},
            {"cause": "entity_explosion", "damage_multiplier": 0.5},
            {"cause": "block_explosion", "damage_multiplier": 0.5},
            {"cause": "fire", "damage_multiplier": 0.4},
            {"cause": "fire_tick", "damage_multiplier": 0.4},
            {"cause": "lava", "damage_multiplier": 0.4},
            {"cause": "magic", "damage_multiplier": 0.5},
        ]},
        "minecraft:behavior.float": {"priority": 0},
    }
    def st(s):
        return {"set_property": {"aot:state": s}}
    events = {
        "minecraft:entity_spawned": {"sequence": [
            {"add": {"component_groups": ["aot:hunter"]}},
            {"randomize": [{"weight": 1, "add": {"component_groups": [f"aot:body{i}"]}}
                           for i in range(len(BODIES))]},
            {"randomize": [{"weight": 1, "add": {"component_groups": [f"aot:skin{k}"]}}
                           for k in range(SKINS)]},
        ]},
        "aot:sleep": {"remove": {"component_groups": ["aot:hunter"]}, **st("sleep")},
        "aot:wake": {"add": {"component_groups": ["aot:hunter"]}, **st("idle")},
        "aot:blind": {"remove": {"component_groups": ["aot:hunter"]}, **st("blind")},
        "aot:unblind": {"add": {"component_groups": ["aot:hunter"]}, **st("idle")},
        "aot:die": {"remove": {"component_groups": ["aot:hunter"]},
                    "add": {"component_groups": ["aot:dying"]}, **st("dying")},
        "aot:evaporate": {"add": {"component_groups": ["aot:despawn"]}},
    }
    for s in ("idle", "grab", "eat", "kneel", "leap", "swat"):
        events[f"aot:st_{s}"] = st(s)
    return {"format_version": ENTITY_FMT, "minecraft:entity": {
        "description": {
            "identifier": f"{NS}:{key}", "is_spawnable": True, "is_summonable": True,
            "is_experimental": False,
            "properties": {"aot:state": {"type": "enum", "values": TITAN_STATES,
                                         "default": "idle", "client_sync": True}}},
        "component_groups": groups, "components": comps, "events": events}}


# ===========================================================================
#  エンティティ: 調査兵団
# ===========================================================================
SOLDIER_STATS = {
    # 体力, 攻撃, 速さ, 当たり判定の高さ, 仲間にする食べ物
    "eren_yeager": (50, 8, 0.34, 1.85),
    "mikasa_ackerman": (70, 11, 0.36, 1.85),
    "armin_arlert": (32, 5, 0.32, 1.78),
    "levi_ackerman": (90, 13, 0.38, 1.75),
    "hange_zoe": (46, 7, 0.33, 1.85),
    "erwin_smith": (56, 8, 0.33, 1.95),
    "jean_kirstein": (46, 8, 0.34, 1.85),
    "sasha_blouse": (42, 7, 0.36, 1.82),
    "connie_springer": (40, 7, 0.36, 1.74),
    "survey_soldier": (34, 6, 0.33, 1.85),
}


def soldier_entity(key):
    hp, dmg, spd, h = SOLDIER_STATS[key]
    food = ["minecraft:baked_potato"] if key == "sasha_blouse" else \
        ["minecraft:bread", "minecraft:baked_potato"]
    titans = {"test": "is_family", "subject": "other", "value": "titan"}
    common_ai = {
        "minecraft:behavior.delayed_attack": {
            "priority": 2, "attack_once": False, "track_target": True,
            "require_complete_path": False, "reach_multiplier": 2.2, "speed_multiplier": 1.15,
            "attack_duration": 0.5, "hit_delay_pct": 0.3},
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 3, "must_see": True, "reselect_targets": True, "within_radius": 32,
            "entity_types": [{"filters": titans, "max_dist": 32}]},
        "minecraft:behavior.look_at_player": {"priority": 8, "look_distance": 8},
        "minecraft:behavior.random_look_around": {"priority": 9},
    }
    groups = {
        "aot:wild": dict(common_ai, **{
            "minecraft:behavior.hurt_by_target": {"priority": 1},
            "minecraft:behavior.random_stroll": {"priority": 7, "speed_multiplier": 0.8},
            "minecraft:tameable": {"probability": 1.0, "tame_items": food,
                                   "tame_event": {"event": "aot:recruited", "target": "self"}},
        }),
        "aot:squad": dict(common_ai, **{
            "minecraft:is_tamed": {},
            "minecraft:sittable": {},
            "minecraft:behavior.stay_while_sitting": {"priority": 0},
            "minecraft:behavior.owner_hurt_by_target": {"priority": 1},
            "minecraft:behavior.owner_hurt_target": {"priority": 2},
            "minecraft:behavior.follow_owner": {"priority": 5, "speed_multiplier": 1.2,
                                                "start_distance": 8, "stop_distance": 3},
        }),
    }
    comps = {
        "minecraft:type_family": {"family": ["aot_soldier", "survey_corps", "human", "mob"]},
        "minecraft:collision_box": {"width": 0.6, "height": h},
        "minecraft:health": {"value": hp, "max": hp},
        "minecraft:attack": {"damage": dmg},
        "minecraft:movement": {"value": spd},
        "minecraft:movement.basic": {},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": True,
                                      "can_open_doors": True},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:nameable": {},
        "minecraft:persistent": {},
        "minecraft:follow_range": {"value": 48, "max": 48},
        "minecraft:knockback_resistance": {"value": 0.3},
        "minecraft:experience_reward": {"on_death": "0"},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:damage_sensor": {"triggers": [
            {"cause": "fall", "deals_damage": False},
            {"cause": "fly_into_wall", "deals_damage": False},
            {"on_damage": {"filters": {"test": "is_family", "subject": "other",
                                       "value": "aot_soldier"}}, "deals_damage": False},
            {"on_damage": {"filters": {"test": "is_family", "subject": "other",
                                       "value": "player"}}, "deals_damage": False}]},
    }
    events = {
        "minecraft:entity_spawned": {"add": {"component_groups": ["aot:wild"]}},
        "aot:recruited": {"remove": {"component_groups": ["aot:wild"]},
                          "add": {"component_groups": ["aot:squad"]}},
    }
    for s in SOLDIER_STATES:
        events[f"aot:st_{s}"] = {"set_property": {"aot:state": s}}
    return {"format_version": ENTITY_FMT, "minecraft:entity": {
        "description": {
            "identifier": f"{NS}:{key}", "is_spawnable": True, "is_summonable": True,
            "is_experimental": False,
            "properties": {"aot:state": {"type": "enum", "values": SOLDIER_STATES,
                                         "default": "idle", "client_sync": True}}},
        "component_groups": groups, "components": comps, "events": events}}


def entities():
    d = os.path.join(BP, "entities")
    os.makedirs(d, exist_ok=True)
    for key in TITANS:
        write_json(os.path.join(d, f"{key}.entity.json"), titan_entity(key))
    for key in SOLDIERS:
        write_json(os.path.join(d, f"{key}.entity.json"), soldier_entity(key))


# ===========================================================================
#  スポーンルール（昼の地上。巨人は日光で動く）
# ===========================================================================
SPAWN = {"titan_small": 5, "titan_medium": 3, "titan_large": 1, "titan_abnormal": 1}


def spawn_rules():
    d = os.path.join(BP, "spawn_rules")
    os.makedirs(d, exist_ok=True)
    biomes = {"any_of": [{"test": "has_biome_tag", "operator": "==", "value": b}
                         for b in ("plains", "forest", "savanna", "taiga", "meadow", "birch")]}
    for key, weight in SPAWN.items():
        write_json(os.path.join(d, f"{key}.json"), {
            "format_version": "1.8.0",
            "minecraft:spawn_rules": {
                "description": {"identifier": f"{NS}:{key}", "population_control": "monster"},
                "conditions": [{
                    "minecraft:spawns_on_surface": {},
                    "minecraft:brightness_filter": {"min": 10, "max": 15,
                                                    "adjust_for_weather": False},
                    "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
                    "minecraft:weight": {"default": weight},
                    "minecraft:herd": {"min_size": 1, "max_size": 1},
                    "minecraft:density_limit": {"surface": 1},
                    "minecraft:biome_filter": biomes,
                }]}})


# ===========================================================================
#  レシピ
# ===========================================================================
def shaped(ident, pattern, keys, result, count=1):
    return {"format_version": "1.20.10", "minecraft:recipe_shaped": {
        "description": {"identifier": f"{NS}:{ident}"}, "tags": ["crafting_table"],
        "pattern": pattern, "key": {k: {"item": v} for k, v in keys.items()},
        "result": {"item": result, "count": count}}}


def shapeless(ident, ingredients, result, count=1):
    return {"format_version": "1.20.10", "minecraft:recipe_shapeless": {
        "description": {"identifier": f"{NS}:{ident}"}, "tags": ["crafting_table"],
        "ingredients": [{"item": i} for i in ingredients],
        "result": {"item": result, "count": count}}}


def recipes():
    d = os.path.join(BP, "recipes")
    os.makedirs(d, exist_ok=True)
    S = f"{NS}:hardened_steel"
    R = {
        "hardened_steel": shaped("hardened_steel", [" I ", "ICI", " I "],
                                 {"I": "minecraft:iron_ingot", "C": "minecraft:coal"}, S, 2),
        "hardened_steel_charcoal": shaped("hardened_steel_charcoal", [" I ", "ICI", " I "],
                                          {"I": "minecraft:iron_ingot", "C": "minecraft:charcoal"},
                                          S, 2),
        "odm_blades": shaped("odm_blades", ["S S", "S S", "T T"],
                             {"S": S, "T": "minecraft:stick"}, f"{NS}:odm_blades"),
        "spare_blades": shaped("spare_blades", ["S", "S"], {"S": S}, f"{NS}:spare_blades", 4),
        "odm_gear": shaped("odm_gear", ["S S", "WPW", "S S"],
                           {"S": S, "W": "minecraft:lead", "P": "minecraft:piston"},
                           f"{NS}:odm_gear"),
        "gas_canister": shaped("gas_canister", [" I ", "IGI", " I "],
                               {"I": "minecraft:iron_ingot", "G": "minecraft:gunpowder"},
                               f"{NS}:gas_canister", 2),
        "thunder_spear": shaped("thunder_spear", ["  T", " S ", "S  "],
                                {"T": "minecraft:tnt", "S": S}, f"{NS}:thunder_spear", 2),
        "flare_gun": shaped("flare_gun", ["IIF", " G "],
                            {"I": "minecraft:iron_ingot", "F": "minecraft:flint_and_steel",
                             "G": "minecraft:gunpowder"}, f"{NS}:flare_gun"),
        "survey_jacket": shaped("survey_jacket", ["LGL", "LLL", "LLL"],
                                {"L": "minecraft:leather", "G": "minecraft:green_dye"},
                                f"{NS}:survey_jacket"),
        "survey_boots": shaped("survey_boots", ["LBL", "L L"],
                               {"L": "minecraft:leather", "B": "minecraft:brown_dye"},
                               f"{NS}:survey_boots"),
        "survey_journal": shapeless("survey_journal", ["minecraft:book", "minecraft:green_dye"],
                                    f"{NS}:survey_journal"),
    }
    for name, doc in R.items():
        write_json(os.path.join(d, f"{name}.json"), doc)


# ===========================================================================
#  RP: クライアント定義
# ===========================================================================
TITAN_ANIMS = {
    "look": "animation.aot.titan.look", "idle": "animation.aot.titan.idle",
    "walk": "animation.aot.titan.walk", "run": "animation.aot.titan.run",
    "attack": "animation.aot.titan.attack", "swat": "animation.aot.titan.swat",
    "grab": "animation.aot.titan.grab", "eat": "animation.aot.titan.eat",
    "kneel": "animation.aot.titan.kneel", "sleep": "animation.aot.titan.sleep",
    "dying": "animation.aot.titan.dying", "leap": "animation.aot.titan.leap",
    "blind": "animation.aot.titan.blind", "hurt": "animation.aot.titan.hurt",
    "general": "controller.animation.aot.titan.general",
    "action": "controller.animation.aot.titan.action",
}
HUMAN_ANIMS = {
    "look": "animation.aot.human.look", "idle": "animation.aot.human.idle",
    "walk": "animation.aot.human.walk", "run": "animation.aot.human.run",
    "attack": "animation.aot.human.attack", "hurt": "animation.aot.human.hurt",
    "death": "animation.aot.human.death", "fly": "animation.aot.human.fly",
    "slash": "animation.aot.human.slash",
    "general": "controller.animation.aot.human.general",
    "action": "controller.animation.aot.human.action",
}
EGG = {
    "titan_small": ("#e3a98e", "#7a3b2a"), "titan_medium": ("#d9987a", "#5a2a1e"),
    "titan_large": ("#cb8f6e", "#3a1a14"), "titan_abnormal": ("#eec5ac", "#b8302a"),
    "eren_yeager": ("#8a5634", "#2c9a8c"), "mikasa_ackerman": ("#8a5634", "#b51f2b"),
    "armin_arlert": ("#8a5634", "#e9cf7c"), "levi_ackerman": ("#8a5634", "#f2f2ee"),
    "hange_zoe": ("#8a5634", "#6b4a32"), "erwin_smith": ("#8a5634", "#3d6eb8"),
    "jean_kirstein": ("#8a5634", "#a47c4e"), "sasha_blouse": ("#8a5634", "#7a5232"),
    "connie_springer": ("#8a5634", "#a2a2a6"), "survey_soldier": ("#8a5634", "#2d4f3a"),
}


def client_entities():
    d = os.path.join(RP, "entity")
    os.makedirs(d, exist_ok=True)
    tex = {f"{b}_{k}": f"textures/entity/aot/titan_{b}_{k}" for b in BODIES for k in range(SKINS)}
    geo = {b: f"geometry.aot.titan_{b}" for b in BODIES}
    total_px = titan_metrics(BODIES[0])["total"]
    for key, (height, *_rest) in TITANS.items():
        scale = height / (total_px / 16.0)        # 描かれる全高 = 級の高さ（ブロック）
        write_json(os.path.join(d, f"{key}.entity.json"), {
            "format_version": "1.10.0", "minecraft:client_entity": {"description": {
                "identifier": f"{NS}:{key}",
                "materials": {"default": "entity_alphatest"},
                "textures": tex, "geometry": geo, "animations": TITAN_ANIMS,
                "scripts": {"scale": f"{scale:.3f}",
                            "pre_animation": GA.titan_pre_animation(scale, key == "titan_abnormal"),
                            "animate": ["general", "action"]},
                "render_controllers": ["controller.render.aot.titan"],
                "spawn_egg": {"base_color": EGG[key][0], "overlay_color": EGG[key][1]},
            }}})
    for key in SOLDIERS:
        anims = dict(HUMAN_ANIMS)
        animate = ["general", "action"]
        extra = {"hange_zoe": "ponytail", "sasha_blouse": "ponytail", "mikasa_ackerman": "scarf"}
        if key in extra:                       # 揺れる髪とマフラー
            anims["hair"] = f"animation.aot.human.{extra[key]}"
            animate.append("hair")
        write_json(os.path.join(d, f"{key}.entity.json"), {
            "format_version": "1.10.0", "minecraft:client_entity": {"description": {
                "identifier": f"{NS}:{key}",
                "materials": {"default": "entity_alphatest"},
                "textures": {"default": f"textures/entity/aot/{key}"},
                "geometry": {"default": f"geometry.aot.{key}"},
                "animations": anims,
                "scripts": {"animate": animate},
                "render_controllers": ["controller.render.aot.default"],
                "spawn_egg": {"base_color": EGG[key][0], "overlay_color": EGG[key][1]},
            }}})


def render_controllers():
    geos = [f"Geometry.{b}" for b in BODIES]
    texs = [f"Texture.{b}_{k}" for b in BODIES for k in range(SKINS)]
    write_json(os.path.join(RP, "render_controllers", "aot.render_controllers.json"), {
        "format_version": "1.8.0", "render_controllers": {
            "controller.render.aot.titan": {
                "arrays": {"geometries": {"Array.geos": geos},
                           "textures": {"Array.skins": texs}},
                "geometry": "Array.geos[q.variant]",
                "materials": [{"*": "Material.default"}],
                "textures": [f"Array.skins[q.variant * {SKINS} + q.skin_id]"],
            },
            "controller.render.aot.default": {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"],
            },
            "controller.render.aot.attachable": {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"],
            },
        }})


# ===========================================================================
#  アイコン（3D モデルから焼く）とアイテムアトラス
# ===========================================================================
ICONS = {
    # item: (ジオメトリ名, yaw, pitch, roll)
    "odm_blades": ("blades", 90, -8, 42),
    "thunder_spear": ("thunder_spear", 90, -8, 40),
    "gas_canister": ("prop_gas_canister", 70, -20, 30),
    "spare_blades": ("prop_spare_blades", 80, -14, 40),
    "hardened_steel": ("prop_hardened_steel", 30, -30, 0),
    "survey_journal": ("prop_journal", 20, -10, 0),
    "flare_gun": ("prop_flare_gun", 90, -14, 0),
    "odm_gear": ("wear_odm_gear", 210, -18, 0),
    "survey_jacket": ("wear_jacket", 180, -8, 0),
    "survey_boots": ("wear_boots", 60, -14, 0),
}


def icons():
    from hd_preview import render
    os.makedirs(C.ICON_DIR, exist_ok=True)
    for name, (geo, yaw, pitch, roll) in ICONS.items():
        g = os.path.join(C.GEO_DIR, f"{geo}.geo.json")
        t = os.path.join(C.TEX_DIR, f"{geo}.png")
        hide = ("hold_l",) if name == "odm_blades" else ()
        im = render(g, t, 32, yaw, pitch, roll=roll, margin=0.04, bg=(0, 0, 0, 0), ss=6,
                    hide=hide, outline=(22, 20, 26))
        im.save(os.path.join(C.ICON_DIR, f"{name}.png"))
    write_json(os.path.join(RP, "textures", "item_texture.json"), {
        "resource_pack_name": "aot", "texture_name": "atlas.items",
        "texture_data": {f"aot_{n}": {"textures": f"textures/items/aot/{n}"} for n in ICONS}})


def pack_icon():
    """パックアイコン: 深緑の地に自由の翼と、巨人の顔の影。"""
    from aot_paint import AotPainter
    p = AotPainter(256, 256, 1)
    for y in range(256):
        for x in range(256):
            k = 1.0 - ((x - 128) ** 2 + (y - 128) ** 2) ** 0.5 / 260
            p.put(x, y, (int(30 + 20 * k), int(52 + 32 * k), int(40 + 22 * k)))
    p.d_wings((0, 0, 256, 256), {}, {"size": 0.82, "cv": 0.48}, 1)
    img = p.img.convert("RGBA")
    draw = ImageDraw.Draw(img)
    draw.rectangle((6, 6, 249, 249), outline=(210, 196, 160, 255), width=4)
    for pack in (BP, RP):
        img.convert("RGB").save(os.path.join(pack, "pack_icon.png"))


def script_meta():
    """スクリプトが使う巨人の寸法（全高に対する比）と級の情報を JS で書き出す。"""
    import json
    bodies = []
    for b in BODIES:
        m = titan_metrics(b)
        T = m["total"]
        bodies.append({"key": b, "napeY": round(m["nape_y"] / T, 4), "napeZ": round(m["nape_z"] / T, 4),
                       "eyeY": round(m["eye_y"] / T, 4), "headZ": round(m["head_z"] / T, 4),
                       "hip": round(m["hip"] / T, 4), "knee": round(m["knee"] / T, 4),
                       "shoulderW": round(m["shoulder_w"] / T, 4), "arm": round(m["arm_len"] / T, 4)})
    types = {}
    for key, (height, hp, dmg, spd, coll, hit, grabs, xp) in TITANS.items():
        types[f"{NS}:{key}"] = {"key": key, "height": height, "hp": hp, "dmg": dmg,
                                "hitW": hit[0], "grab": grabs, "xp": xp,
                                "abnormal": key == "titan_abnormal"}
    path = os.path.join(BP, "scripts", "aot_meta.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("// 自動生成（tools/aot/gen_aot_packs.py）。巨人の体型ごとの寸法（全高に対する比）と級\n")
        fh.write("export const BODY_META = ")
        json.dump(bodies, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\nexport const TITAN_TYPES = ")
        json.dump(types, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\nexport const SOLDIER_TYPES = ")
        json.dump([f"{NS}:{k}" for k in SOLDIERS], fh, separators=(",", ":"))
        fh.write(";\n")


def main():
    manifests()
    script_meta()
    items()
    entities()
    spawn_rules()
    recipes()
    client_entities()
    render_controllers()
    icons()
    pack_icon()
    print(f"  items: {len(ICONS)}  entities: {len(TITANS) + len(SOLDIERS)}")
    _ = Image


if __name__ == "__main__":
    main()
