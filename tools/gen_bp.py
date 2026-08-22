"""Generates the behaviour pack: items, entities, spawn rules, loot, recipes."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "packs", "kaiju8_BP")
RP = os.path.join(ROOT, "packs", "kaiju8_RP")

ITEM_FMT = "1.21.20"
ENTITY_FMT = "1.21.0"


def dump(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# =====================================================================  ITEMS
MATERIALS = [
    # id, icon, stack, category/group
    ("kaiju_core", "kaiju_core", 16, "items", "itemGroup.name.miscFood"),
    ("kaiju_shell", "kaiju_shell", 64, "items", "itemGroup.name.miscFood"),
    ("kaiju_alloy", "kaiju_alloy", 64, "items", "itemGroup.name.miscFood"),
    ("kaiju_remains", "kaiju_remains", 64, "items", "itemGroup.name.miscFood"),
    ("identified_core", "identified_core", 8, "items", "itemGroup.name.miscFood"),
]

# 識別怪獣兵器（ナンバーズ）— 着る武器。頭スロットに装備し全身モデルを差し替える
NUMBERS = [
    # id, protection, durability
    ("numbers_1", 7, 1600),
    ("numbers_2", 8, 1700),
    ("numbers_4", 7, 1600),
    ("numbers_6", 7, 1500),
    ("numbers_10", 8, 1800),
]

WEAPONS = [
    # id, icon, damage, durability, enchant value
    ("combat_knife", "combat_knife", 6, 620, 10),
    ("df_pistol", "df_pistol", 3, 520, 10),
    ("df_bazooka", "df_bazooka", 5, 900, 14),
    ("blade_sw1023", "blade_sw1023", 11, 1750, 20),
    ("df_rifle", "df_rifle", 4, 700, 12),
    ("twin_sw2033", "twin_sw2033", 9, 1700, 20),
    ("axe_03ax", "axe_03ax", 13, 1900, 18),
    ("cannon_t25", "cannon_t25", 7, 1900, 20),
    ("gunblade_gs3305", "gunblade_gs3305", 12, 2000, 20),
]

# 技を撃つあいだ「構え」の姿勢が出るよう、右クリックを保持できる武器にする。
# use_duration があるとアタッチャブル側の q.is_using_item が立ち、技モーション
# へ遷移する。技そのものは押した瞬間の itemUse で発動するので発生は遅れない。
# 技のモーション本体が 0.86〜1.02 秒あるので、押しっぱなしで最後まで見られるよう
# use_duration はそれより長く取る。指を離せばそこで止まるので、連打の邪魔にはならない。
BRACE = {
    "combat_knife":    (1.10, 0.95),
    "df_pistol":       (1.10, 0.90),
    "df_bazooka":      (1.30, 0.55),
    "blade_sw1023":    (1.20, 0.85),
    "df_rifle":        (1.10, 0.80),
    "twin_sw2033":     (1.20, 0.88),
    "axe_03ax":        (1.40, 0.60),
    "cannon_t25":      (1.40, 0.45),
    "gunblade_gs3305": (1.30, 0.65),
}

ARMOR = [
    # id, slot, protection, durability, enchant slot
    ("combat_suit_helmet", "slot.armor.head", 3, 560, "armor_head"),
    ("combat_suit_chestplate", "slot.armor.chest", 8, 800, "armor_torso"),
    ("combat_suit_leggings", "slot.armor.legs", 6, 750, "armor_legs"),
    ("combat_suit_boots", "slot.armor.feet", 3, 650, "armor_feet"),
]


def item(identifier, components, category="equipment", group=None):
    desc = {"identifier": f"kaiju8:{identifier}",
            "menu_category": {"category": category}}
    if group:
        desc["menu_category"]["group"] = group
    components = dict(components)
    components["minecraft:display_name"] = {"value": f"item.kaiju8:{identifier}"}
    return {"format_version": ITEM_FMT,
            "minecraft:item": {"description": desc, "components": components}}


def gen_items():
    out = os.path.join(BP, "items")
    for ident, icon, stack, cat, group in MATERIALS:
        dump(os.path.join(out, ident + ".item.json"), item(ident, {
            "minecraft:icon": {"texture": icon},
            "minecraft:max_stack_size": stack,
        }, cat, group))

    for ident, icon, dmg, dur, ench in WEAPONS:
        dump(os.path.join(out, ident + ".item.json"), item(ident, {
            "minecraft:icon": {"texture": icon},
            "minecraft:max_stack_size": 1,
            "minecraft:hand_equipped": True,
            "minecraft:damage": {"value": dmg},
            "minecraft:durability": {"max_durability": dur},
            "minecraft:repairable": {
                "repair_items": [{"items": ["kaiju8:kaiju_alloy"], "repair_amount": dur // 4}]
            },
            "minecraft:enchantable": {"slot": "sword", "value": ench},
            "minecraft:use_modifiers": {
                "use_duration": BRACE[ident][0],
                "movement_modifier": BRACE[ident][1],
            },
            "minecraft:can_destroy_in_creative": False,
            "minecraft:should_despawn": False,
        }, "equipment", "itemGroup.name.sword"))

    for ident, slot, prot, dur, ench in ARMOR:
        dump(os.path.join(out, ident + ".item.json"), item(ident, {
            "minecraft:icon": {"texture": ident},
            "minecraft:max_stack_size": 1,
            "minecraft:wearable": {"slot": slot, "protection": prot},
            "minecraft:durability": {"max_durability": dur},
            "minecraft:repairable": {
                "repair_items": [{"items": ["kaiju8:kaiju_alloy"], "repair_amount": dur // 4}]
            },
            "minecraft:enchantable": {"slot": ench, "value": 12},
        }, "equipment", "itemGroup.name.helmet"))

    # the little kaiju that crawls down Kafka's throat
    dump(os.path.join(out, "parasite_kaiju.item.json"), item("parasite_kaiju", {
        "minecraft:icon": {"texture": "parasite_kaiju"},
        "minecraft:max_stack_size": 1,
        "minecraft:glint": True,
        "minecraft:use_animation": "drink",
        "minecraft:use_modifiers": {"use_duration": 1.6, "movement_modifier": 0.35},
    }, "items", "itemGroup.name.miscFood"))

    dump(os.path.join(out, "no8_power.item.json"), item("no8_power", {
        "minecraft:icon": {"texture": "no8_power"},
        "minecraft:max_stack_size": 1,
        "minecraft:glint": True,
        "minecraft:hand_equipped": True,
        "minecraft:use_modifiers": {"use_duration": 1.2, "movement_modifier": 0.8},
        "minecraft:should_despawn": False,
    }, "items", "itemGroup.name.miscFood"))

    dump(os.path.join(out, "kaiju_detector.item.json"), item("kaiju_detector", {
        "minecraft:icon": {"texture": "kaiju_detector"},
        "minecraft:max_stack_size": 1,
        "minecraft:hand_equipped": True,
        "minecraft:durability": {"max_durability": 320},
    }, "items", "itemGroup.name.miscFood"))

    for ident, prot, dur in NUMBERS:
        dump(os.path.join(out, ident + ".item.json"), item(ident, {
            "minecraft:icon": {"texture": ident},
            "minecraft:max_stack_size": 1,
            "minecraft:wearable": {"slot": "slot.armor.head", "protection": prot},
            "minecraft:durability": {"max_durability": dur},
            "minecraft:repairable": {
                "repair_items": [{"items": ["kaiju8:identified_core"],
                                  "repair_amount": dur // 3}]
            },
            "minecraft:enchantable": {"slot": "armor_head", "value": 16},
            "minecraft:allow_off_hand": False,
            "minecraft:should_despawn": False,
            "minecraft:glint": True,
        }, "equipment", "itemGroup.name.helmet"))

    # invisible "body" item worn in the helmet slot while transformed
    dump(os.path.join(out, "no8_form.item.json"), item("no8_form", {
        "minecraft:icon": {"texture": "no8_power"},
        "minecraft:max_stack_size": 1,
        "minecraft:wearable": {"slot": "slot.armor.head", "protection": 0},
        "minecraft:allow_off_hand": False,
        "minecraft:should_despawn": False,
        "minecraft:glint": True,
    }, "equipment", "itemGroup.name.helmet"))
    print("  items")


# ==================================================================  ENTITIES
def behaviours_common(walk_speed, attack_damage, reach, attack_dur=0.6,
                      hit_delay=0.4, targets=("player",), family=("kaiju",),
                      follow=48):
    filters = {"any_of": [{"test": "is_family", "subject": "other", "value": t}
                          for t in targets]}
    return {
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.delayed_attack": {
            "priority": 2, "attack_once": False, "track_target": True,
            "require_complete_path": False, "random_stop_interval": 0,
            "reach_multiplier": reach, "speed_multiplier": 1.15,
            "attack_duration": attack_dur, "hit_delay_pct": hit_delay
        },
        "minecraft:behavior.nearest_attackable_target": {
            "priority": 3, "must_see": True, "reselect_targets": True,
            "must_see_forget_duration": 12.0, "within_radius": follow,
            "entity_types": [{"filters": filters, "max_dist": follow}]
        },
        "minecraft:behavior.move_towards_target": {"priority": 4, "speed_multiplier": 1.0,
                                                   "within_radius": 32},
        "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
        "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
        "minecraft:behavior.random_look_around": {"priority": 8},
    }


def state_groups(roar_time=2.0):
    """mark_variant drives the resource-pack animation controllers:
       0 normal / 1 咆哮 / 2 技 / 4 被弾リアクション"""
    return {
        "kaiju8:roaring": {
            "minecraft:mark_variant": {"value": 1},
            "minecraft:timer": {"looping": False, "time": roar_time,
                                "time_down_event": {"event": "kaiju8:calm_down"}}
        },
        "kaiju8:performing": {
            "minecraft:mark_variant": {"value": 2},
            "minecraft:timer": {"looping": False, "time": 0.9,
                                "time_down_event": {"event": "kaiju8:calm_down"}}
        },
        # 二の型。同じ技が続けて出ないよう技モーションを交互に振る
        "kaiju8:performing2": {
            "minecraft:mark_variant": {"value": 3},
            "minecraft:timer": {"looping": False, "time": 1.1,
                                "time_down_event": {"event": "kaiju8:calm_down"}}
        },
        "kaiju8:reeling": {
            "minecraft:mark_variant": {"value": 4},
            "minecraft:timer": {"looping": False, "time": 0.35,
                                "time_down_event": {"event": "kaiju8:calm_down"}}
        },
    }


STATE_EVENTS = {
    "minecraft:entity_spawned": {"add": {"component_groups": ["kaiju8:roaring"]}},
    "kaiju8:roar": {
        "remove": {"component_groups": ["kaiju8:performing", "kaiju8:reeling"]},
        "add": {"component_groups": ["kaiju8:roaring"]}},
    "kaiju8:tech": {
        "remove": {"component_groups": ["kaiju8:roaring", "kaiju8:reeling",
                                        "kaiju8:performing2"]},
        "add": {"component_groups": ["kaiju8:performing"]}},
    "kaiju8:tech2": {
        "remove": {"component_groups": ["kaiju8:roaring", "kaiju8:reeling",
                                        "kaiju8:performing"]},
        "add": {"component_groups": ["kaiju8:performing2"]}},
    "kaiju8:hurt_flash": {
        "add": {"component_groups": ["kaiju8:reeling"]}},
    "kaiju8:calm_down": {
        "remove": {"component_groups": ["kaiju8:roaring", "kaiju8:performing",
                                        "kaiju8:performing2", "kaiju8:reeling"]}},
}


def kaiju_entity(name, health, damage, speed, width, height, xp, loot,
                 reach=1.6, families=("kaiju", "monster"), boss=None,
                 fly=False, ranged=None, fire_immune=False, knockback=0.6,
                 targets=("player", "villager", "defense_force"), scale=None,
                 summonable=True, spawnable=True, persistent=None, extra=None):
    comps = {
        "minecraft:type_family": {"family": list(families) + ["mob"]},
        "minecraft:collision_box": {"width": width, "height": height},
        "minecraft:health": {"value": health, "max": health},
        "minecraft:attack": {"damage": damage},
        "minecraft:movement": {"value": speed},
        "minecraft:knockback_resistance": {"value": knockback},
        "minecraft:follow_range": {"value": 64, "max": 64},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": True},
        "minecraft:nameable": {},
        "minecraft:mark_variant": {"value": 0},
        "minecraft:experience_reward": {"on_death": str(xp)},
        "minecraft:loot": {"table": f"loot_tables/entities/{loot}.json"},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:damage_sensor": {
            "triggers": [
                {"on_damage": {"filters": {"all_of": [
                    {"test": "is_family", "subject": "other", "value": "kaiju"},
                    {"test": "is_family", "subject": "other", "operator": "!=",
                     "value": "identified_kaiju"}
                ]}}, "deals_damage": False},
                {"cause": "fall", "damage_multiplier": 0.0, "deals_damage": False}
            ]
        },
    }
    if persistent if persistent is not None else bool(boss):
        comps["minecraft:persistent"] = {}
    else:
        comps["minecraft:despawn"] = {
            "despawn_from_distance": {"max_distance": 128, "min_distance": 96}}
    if scale:
        comps["minecraft:scale"] = {"value": scale}
    if fire_immune:
        comps["minecraft:fire_immune"] = {}
    if fly:
        comps["minecraft:can_fly"] = {}
        comps["minecraft:movement.fly"] = {}
        comps["minecraft:navigation.fly"] = {"can_path_over_water": True,
                                             "can_path_from_air": True}
        comps["minecraft:behavior.float_wander"] = {"priority": 9, "xz_dist": 12,
                                                    "y_dist": 8, "y_offset": 2,
                                                    "must_reach": True, "random_reselect": True}
    else:
        comps["minecraft:movement.basic"] = {}
        comps["minecraft:navigation.walk"] = {"can_path_over_water": True,
                                              "avoid_water": True,
                                              "can_break_doors": True}
        comps["minecraft:behavior.float"] = {"priority": 0}
    comps.update(behaviours_common(speed, damage, reach, targets=targets))
    if ranged:
        comps["minecraft:shooter"] = {"def": ranged[0]}
        comps["minecraft:behavior.ranged_attack"] = {
            "priority": 3, "burst_shots": ranged[1], "burst_interval": 0.3,
            "charge_charged_trigger": 0.0, "charge_shoot_trigger": 2.0,
            "attack_interval_min": ranged[2], "attack_interval_max": ranged[2] + 2,
            "attack_radius": 24, "speed_multiplier": 1.0
        }
    if boss:
        comps["minecraft:boss"] = {"should_darken_sky": boss[1], "hud_range": 60,
                                   "name": boss[0]}
    if extra:
        comps.update(extra)

    doc = {
        "format_version": ENTITY_FMT,
        "minecraft:entity": {
            "description": {
                "identifier": f"kaiju8:{name}",
                "is_spawnable": True,
                "is_summonable": summonable,
                "is_experimental": False
            },
            "component_groups": state_groups(),
            "components": comps,
            "events": dict(STATE_EVENTS)
        }
    }
    return doc


def soldier_entity(name, health, damage, speed, xp, ranged=None, reach=1.2,
                   knockback=0.35, box=(0.6, 1.85)):
    comps = {
        "minecraft:type_family": {"family": ["defense_force", "kaiju8_ally", "mob"]},
        "minecraft:collision_box": {"width": box[0], "height": box[1]},
        "minecraft:mark_variant": {"value": 0},
        "minecraft:health": {"value": health, "max": health},
        "minecraft:attack": {"damage": damage},
        "minecraft:movement": {"value": speed},
        "minecraft:movement.basic": {},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": True,
                                      "can_open_doors": True, "can_break_doors": False},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:nameable": {},
        "minecraft:knockback_resistance": {"value": knockback},
        "minecraft:follow_range": {"value": 48, "max": 48},
        "minecraft:experience_reward": {"on_death": str(xp)},
        "minecraft:loot": {"table": "loot_tables/entities/defense_force.json"},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:persistent": {},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:damage_sensor": {
            "triggers": [{"cause": "fall", "damage_multiplier": 0.35}]
        },
    }
    comps.update(behaviours_common(speed, damage, reach,
                                   targets=("kaiju",), follow=48))
    # 変身中の隊員（＝怪獣8号）は防衛隊にも怪獣として認識される
    comps["minecraft:behavior.nearest_attackable_target"]["entity_types"].append({
        "filters": {"all_of": [
            {"test": "is_family", "subject": "other", "value": "player"},
            {"test": "has_tag", "subject": "other", "value": "kaiju8_no8"}
        ]},
        "max_dist": 32
    })
    if ranged:
        comps["minecraft:shooter"] = {"def": ranged[0]}
        comps["minecraft:behavior.ranged_attack"] = {
            "priority": 2, "burst_shots": ranged[1], "burst_interval": 0.25,
            "charge_charged_trigger": 0.0, "charge_shoot_trigger": 1.5,
            "attack_interval_min": ranged[2], "attack_interval_max": ranged[2] + 1,
            "attack_radius": 28, "speed_multiplier": 1.0
        }
    return {
        "format_version": ENTITY_FMT,
        "minecraft:entity": {
            "description": {"identifier": f"kaiju8:{name}", "is_spawnable": True,
                            "is_summonable": True, "is_experimental": False},
            "component_groups": state_groups(1.2),
            "components": comps,
            "events": dict(STATE_EVENTS, **{
                "minecraft:entity_spawned": {"remove": {"component_groups": []}}})
        }
    }


def projectile_entity(name, damage, power, gravity, particle, knockback=True,
                      lifetime=6.0):
    return {
        "format_version": ENTITY_FMT,
        "minecraft:entity": {
            "description": {"identifier": f"kaiju8:{name}", "is_spawnable": False,
                            "is_summonable": True, "is_experimental": False},
            "component_groups": {
                "kaiju8:despawn": {"minecraft:instant_despawn": {}}
            },
            "components": {
                "minecraft:collision_box": {"width": 0.25, "height": 0.25},
                "minecraft:physics": {"has_gravity": gravity > 0},
                "minecraft:conditional_bandwidth_optimization": {},
                "minecraft:projectile": {
                    "on_hit": {
                        "impact_damage": {"damage": damage, "knockback": knockback,
                                          "semi_random_diff_damage": False,
                                          "destroy_on_hit": True},
                        "definition_event": {"affect_projectile": True,
                                             "event_trigger": {"event": "kaiju8:explode",
                                                               "target": "self"}},
                        "particle_on_hit": {"particle_type": particle,
                                            "on_other_hit": True, "num_particles": 8},
                        "remove_on_hit": {}
                    },
                    "power": power,
                    "gravity": gravity,
                    "angle_offset": 0.0,
                    "hit_sound": "bow.hit",
                    "uncertainty_base": 2.0,
                    "uncertainty_multiplier": 0.0,
                    "anchor": 1,
                    "should_bounce": False,
                    "offset": [0, -0.1, 0]
                },
                "minecraft:timer": {"looping": False, "time": lifetime,
                                    "time_down_event": {"event": "kaiju8:explode"}}
            },
            "events": {"kaiju8:explode": {"add": {"component_groups": ["kaiju8:despawn"]}}}
        }
    }


def gen_entities():
    out = os.path.join(BP, "entities")

    # collision boxes follow the actual modelled heights
    dump(os.path.join(out, "yoju.entity.json"), kaiju_entity(
        "yoju", 46, 8, 0.34, 1.90, 2.40, 14, "yoju", reach=2.0,
        families=("kaiju", "yoju", "monster"), knockback=0.30))

    dump(os.path.join(out, "honju.entity.json"), kaiju_entity(
        "honju", 300, 18, 0.30, 2.60, 5.00, 110, "honju", reach=3.2,
        families=("kaiju", "honju", "monster"), knockback=0.90,
        boss=("entity.kaiju8:honju.name", False), persistent=False,
        ranged=("kaiju8:kaiju_acid", 1, 5.0)))

    dump(os.path.join(out, "kaiju_no8.entity.json"), kaiju_entity(
        "kaiju_no8", 420, 26, 0.46, 1.10, 1.95, 170, "kaiju_no8", reach=2.0,
        families=("kaiju", "identified_kaiju", "no8"), knockback=0.95,
        boss=("entity.kaiju8:kaiju_no8.name", True), fire_immune=True,
        targets=("kaiju", "monster")))

    dump(os.path.join(out, "kaiju_no9.entity.json"), kaiju_entity(
        "kaiju_no9", 540, 22, 0.40, 1.30, 3.60, 240, "kaiju_no9", reach=2.6,
        families=("kaiju", "identified_kaiju", "no9", "monster"), knockback=1.0,
        boss=("entity.kaiju8:kaiju_no9.name", True), fire_immune=True))

    dump(os.path.join(out, "kaiju_no10.entity.json"), kaiju_entity(
        "kaiju_no10", 460, 25, 0.40, 2.20, 4.90, 220, "kaiju_no10", reach=3.0,
        families=("kaiju", "identified_kaiju", "no10", "monster"),
        boss=("entity.kaiju8:kaiju_no10.name", True), fire_immune=True,
        knockback=1.0, ranged=("kaiju8:kaiju_acid", 2, 3.0)))

    # 日本防衛隊: speed and reach follow each character's build
    dump(os.path.join(out, "defense_force_officer.entity.json"),
         soldier_entity("defense_force_officer", 44, 7, 0.33, 10,
                        ranged=("kaiju8:df_bullet", 3, 2.0), box=(0.60, 1.75)))
    dump(os.path.join(out, "kafka_hibino.entity.json"),
         soldier_entity("kafka_hibino", 70, 10, 0.34, 18, box=(0.62, 1.87)))
    dump(os.path.join(out, "reno_ichikawa.entity.json"),
         soldier_entity("reno_ichikawa", 60, 9, 0.36, 18,
                        ranged=("kaiju8:df_bullet", 3, 1.8), box=(0.60, 1.76)))
    dump(os.path.join(out, "mina_ashiro.entity.json"),
         soldier_entity("mina_ashiro", 150, 13, 0.33, 70,
                        ranged=("kaiju8:rifle_beam", 1, 2.5), knockback=0.7,
                        box=(0.60, 1.75)))
    dump(os.path.join(out, "soshiro_hoshina.entity.json"),
         soldier_entity("soshiro_hoshina", 140, 24, 0.46, 70, reach=1.5,
                        knockback=0.6, box=(0.60, 1.68)))
    dump(os.path.join(out, "kikoru_shinomiya.entity.json"),
         soldier_entity("kikoru_shinomiya", 130, 28, 0.36, 70, reach=1.7,
                        knockback=0.6, box=(0.55, 1.56)))
    dump(os.path.join(out, "gen_narumi.entity.json"),
         soldier_entity("gen_narumi", 170, 20, 0.42, 90, reach=1.5,
                        ranged=("kaiju8:rifle_beam", 2, 2.0), knockback=0.75,
                        box=(0.62, 1.80)))

    dump(os.path.join(out, "iharu_furuhashi.entity.json"),
         soldier_entity("iharu_furuhashi", 95, 13, 0.36, 40, reach=1.4,
                        box=(0.62, 1.77)))
    dump(os.path.join(out, "haruichi_izumo.entity.json"),
         soldier_entity("haruichi_izumo", 85, 11, 0.35, 40,
                        ranged=("kaiju8:df_bullet", 3, 1.8), box=(0.60, 1.78)))
    dump(os.path.join(out, "aoi_kaguragi.entity.json"),
         soldier_entity("aoi_kaguragi", 115, 17, 0.34, 45, reach=1.6,
                        knockback=0.5, box=(0.64, 1.83)))
    dump(os.path.join(out, "isao_shinomiya.entity.json"),
         soldier_entity("isao_shinomiya", 220, 26, 0.36, 110, reach=1.6,
                        ranged=("kaiju8:rifle_beam", 1, 2.2), knockback=0.85,
                        box=(0.66, 1.90)))

    dump(os.path.join(out, "rifle_beam.entity.json"),
         projectile_entity("rifle_beam", 24, 3.4, 0.0, "critical_hit_emitter"))
    dump(os.path.join(out, "kaiju_acid.entity.json"),
         projectile_entity("kaiju_acid", 10, 1.7, 0.05, "mob_block_on_fire"))
    dump(os.path.join(out, "df_bullet.entity.json"),
         projectile_entity("df_bullet", 6, 2.8, 0.02, "crit"))

    # the parasite kaiju as a tiny crawling creature
    dump(os.path.join(out, "parasite_kaiju.entity.json"), {
        "format_version": ENTITY_FMT,
        "minecraft:entity": {
            "description": {"identifier": "kaiju8:parasite_kaiju", "is_spawnable": True,
                            "is_summonable": True, "is_experimental": False},
            "components": {
                "minecraft:type_family": {"family": ["kaiju", "parasite", "mob"]},
                "minecraft:collision_box": {"width": 0.50, "height": 0.35},
                "minecraft:health": {"value": 4, "max": 4},
                "minecraft:movement": {"value": 0.26},
                "minecraft:movement.basic": {},
                "minecraft:navigation.walk": {"avoid_water": True},
                "minecraft:jump.static": {},
                "minecraft:physics": {},
                "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
                "minecraft:despawn": {"despawn_from_distance": {"max_distance": 96, "min_distance": 64}},
                "minecraft:experience_reward": {"on_death": "3"},
                "minecraft:loot": {"table": "loot_tables/entities/parasite_kaiju.json"},
                "minecraft:conditional_bandwidth_optimization": {},
                "minecraft:behavior.float": {"priority": 0},
                "minecraft:behavior.panic": {"priority": 1, "speed_multiplier": 1.6},
                "minecraft:behavior.random_stroll": {"priority": 4, "speed_multiplier": 1.0},
                "minecraft:behavior.random_look_around": {"priority": 6}
            },
            "events": {}
        }
    })
    print("  entities")


# ===============================================================  SPAWN RULES
def spawn_rule(name, weight, pop, biomes, min_g, max_g, brightness=(0, 7),
               surface=True, min_height=None, max_height=None):
    conds = [{
        "minecraft:spawns_on_surface" if surface else "minecraft:spawns_underground": {},
        "minecraft:brightness_filter": {"min": brightness[0], "max": brightness[1],
                                        "adjust_for_weather": True},
        "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
        "minecraft:weight": {"default": weight},
        "minecraft:herd": {"min_size": min_g, "max_size": max_g},
        "minecraft:biome_filter": {"test": "has_biome_tag", "operator": "==",
                                   "value": biomes},
        "minecraft:density_limit": {"surface": 3}
    }]
    if min_height is not None:
        conds[0]["minecraft:height_filter"] = {"min": min_height, "max": max_height}
    return {
        "format_version": "1.8.0",
        "minecraft:spawn_rules": {
            "description": {"identifier": f"kaiju8:{name}", "population_control": pop},
            "conditions": conds
        }
    }


def gen_spawn_rules():
    out = os.path.join(BP, "spawn_rules")
    dump(os.path.join(out, "yoju.json"),
         spawn_rule("yoju", 22, "monster", "overworld", 2, 4))
    dump(os.path.join(out, "honju.json"),
         spawn_rule("honju", 2, "monster", "overworld", 1, 1))
    print("  spawn rules")


# ================================================================ LOOT TABLES
def loot(entries):
    return {"pools": entries}


def roll(items, rolls=1):
    return {"rolls": rolls, "entries": items}


def entry(name, weight=1, count=(1, 1), functions=None):
    e = {"type": "item", "name": name, "weight": weight}
    fns = list(functions or [])
    if count != (1, 1):
        fns.append({"function": "set_count", "count": {"min": count[0], "max": count[1]}})
    if fns:
        e["functions"] = fns
    return e


def gen_loot():
    out = os.path.join(BP, "loot_tables", "entities")
    dump(os.path.join(out, "yoju.json"), loot([
        roll([entry("kaiju8:kaiju_remains", 6, (1, 3)),
              entry("kaiju8:kaiju_shell", 4, (1, 2))]),
        {"rolls": 1, "conditions": [{"condition": "random_chance", "chance": 0.08}],
         "entries": [entry("kaiju8:kaiju_core")]}
    ]))
    dump(os.path.join(out, "honju.json"), loot([
        roll([entry("kaiju8:kaiju_remains", 1, (4, 9))]),
        roll([entry("kaiju8:kaiju_shell", 1, (3, 6))]),
        roll([entry("kaiju8:kaiju_core", 1, (1, 2))]),
        {"rolls": 1, "conditions": [{"condition": "random_chance", "chance": 0.15}],
         "entries": [entry("kaiju8:parasite_kaiju")]}
    ]))
    for name, cores, alloy in (("kaiju_no8", (2, 4), (2, 4)),
                               ("kaiju_no9", (3, 5), (3, 6)),
                               ("kaiju_no10", (3, 5), (3, 6))):
        dump(os.path.join(out, name + ".json"), loot([
            roll([entry("kaiju8:identified_core", 1, (1, 2))]),
            roll([entry("kaiju8:kaiju_core", 1, cores)]),
            roll([entry("kaiju8:kaiju_alloy", 1, alloy)]),
            roll([entry("kaiju8:kaiju_shell", 1, (6, 12))]),
            {"rolls": 1, "conditions": [{"condition": "random_chance", "chance": 0.5}],
             "entries": [entry("kaiju8:parasite_kaiju")]}
        ]))
    dump(os.path.join(out, "parasite_kaiju.json"), loot([
        roll([entry("kaiju8:parasite_kaiju")])
    ]))
    dump(os.path.join(out, "defense_force.json"), loot([
        {"rolls": 1, "conditions": [{"condition": "random_chance", "chance": 0.25}],
         "entries": [entry("kaiju8:kaiju_alloy", 1, (1, 2))]}
    ]))
    print("  loot tables")


# =====================================================================  CRAFT
def shaped(pattern, keys, result, count=1, tags=("crafting_table",), ident=None):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": f"kaiju8:{ident or result.split(':')[1]}"},
            "tags": list(tags),
            "pattern": pattern,
            "key": {k: {"item": v} for k, v in keys.items()},
            "result": {"item": result, "count": count}
        }
    }


def gen_recipes():
    out = os.path.join(BP, "recipes")
    dump(os.path.join(out, "kaiju_alloy.json"), {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": "kaiju8:kaiju_alloy"},
            "tags": ["crafting_table"],
            "ingredients": [{"item": "kaiju8:kaiju_shell"}, {"item": "kaiju8:kaiju_shell"},
                            {"item": "minecraft:iron_ingot"}, {"item": "minecraft:iron_ingot"}],
            "result": {"item": "kaiju8:kaiju_alloy", "count": 2}
        }
    })
    dump(os.path.join(out, "kaiju_shell_from_remains.json"), {
        "format_version": "1.20.10",
        "minecraft:recipe_shapeless": {
            "description": {"identifier": "kaiju8:kaiju_shell_from_remains"},
            "tags": ["crafting_table"],
            "ingredients": [{"item": "kaiju8:kaiju_remains"}, {"item": "kaiju8:kaiju_remains"},
                            {"item": "kaiju8:kaiju_remains"}],
            "result": {"item": "kaiju8:kaiju_shell", "count": 1}
        }
    })
    dump(os.path.join(out, "combat_knife.json"), shaped(
        [" A ", " A ", " S "], {"A": "kaiju8:kaiju_alloy", "S": "minecraft:stick"},
        "kaiju8:combat_knife"))
    dump(os.path.join(out, "df_rifle.json"), shaped(
        ["AAI", " SA", "  S"], {"A": "kaiju8:kaiju_alloy", "I": "minecraft:iron_ingot",
                                "S": "minecraft:stick"}, "kaiju8:df_rifle"))
    dump(os.path.join(out, "df_pistol.json"), shaped(
        ["AA ", " SA", "  S"], {"A": "kaiju8:kaiju_alloy", "S": "minecraft:stick"},
        "kaiju8:df_pistol"))
    dump(os.path.join(out, "df_bazooka.json"), shaped(
        ["AAA", "IRA", "S  "], {"A": "kaiju8:kaiju_alloy", "I": "minecraft:iron_block",
                                "R": "minecraft:redstone_block",
                                "S": "minecraft:stick"}, "kaiju8:df_bazooka"))
    dump(os.path.join(out, "blade_sw1023.json"), shaped(
        [" AC", " AA", "S  "], {"A": "kaiju8:kaiju_alloy", "C": "kaiju8:kaiju_core",
                                "S": "minecraft:stick"}, "kaiju8:blade_sw1023"))
    dump(os.path.join(out, "twin_sw2033.json"), shaped(
        ["A A", "ACA", "S S"], {"A": "kaiju8:kaiju_alloy", "C": "kaiju8:kaiju_core",
                                "S": "minecraft:stick"}, "kaiju8:twin_sw2033"))
    dump(os.path.join(out, "axe_03ax.json"), shaped(
        ["AAA", "ACR", "  S"], {"A": "kaiju8:kaiju_alloy", "C": "kaiju8:kaiju_core",
                                "R": "minecraft:redstone_block",
                                "S": "minecraft:stick"}, "kaiju8:axe_03ax"))
    dump(os.path.join(out, "cannon_t25.json"), shaped(
        ["CAA", "AAR", "S  "], {"C": "kaiju8:kaiju_core", "A": "kaiju8:kaiju_alloy",
                                "R": "minecraft:redstone_block",
                                "S": "minecraft:stick"}, "kaiju8:cannon_t25"))
    dump(os.path.join(out, "gunblade_gs3305.json"), shaped(
        ["AAC", "AAR", "S  "], {"A": "kaiju8:kaiju_alloy", "C": "kaiju8:kaiju_core",
                                "R": "minecraft:iron_block",
                                "S": "minecraft:stick"}, "kaiju8:gunblade_gs3305"))
    dump(os.path.join(out, "kaiju_detector.json"), shaped(
        [" A ", "ACA", " A "], {"A": "kaiju8:kaiju_alloy", "C": "minecraft:compass"},
        "kaiju8:kaiju_detector"))
    for ident, _prot, _dur in [(n[0], n[1], n[2]) for n in
                               [("numbers_1", 0, 0), ("numbers_2", 0, 0),
                                ("numbers_4", 0, 0), ("numbers_6", 0, 0),
                                ("numbers_10", 0, 0)]]:
        dump(os.path.join(out, ident + ".json"), shaped(
            ["ACA", "AIA", "AAA"],
            {"A": "kaiju8:kaiju_alloy", "C": "kaiju8:identified_core",
             "I": "minecraft:netherite_ingot"}, f"kaiju8:{ident}"))
    for ident, pattern in (
        ("combat_suit_helmet", ["AAA", "A A"]),
        ("combat_suit_chestplate", ["A A", "AAA", "AAA"]),
        ("combat_suit_leggings", ["AAA", "A A", "A A"]),
        ("combat_suit_boots", ["A A", "A A"]),
    ):
        dump(os.path.join(out, ident + ".json"), shaped(
            pattern, {"A": "kaiju8:kaiju_alloy"}, f"kaiju8:{ident}"))
    print("  recipes")


def gen_item_texture():
    names = [m[0] for m in MATERIALS] + [w[0] for w in WEAPONS] + \
            [a[0] for a in ARMOR] + [n[0] for n in NUMBERS] + \
            ["no8_power", "parasite_kaiju", "kaiju_detector"]
    dump(os.path.join(RP, "textures", "item_texture.json"), {
        "resource_pack_name": "kaiju8",
        "texture_name": "atlas.items",
        "texture_data": {n: {"textures": f"textures/items/{n}"} for n in sorted(set(names))}
    })
    print("  item_texture.json")


if __name__ == "__main__":
    print("behaviour pack:")
    gen_items()
    gen_entities()
    gen_spawn_rules()
    gen_loot()
    gen_recipes()
    gen_item_texture()
