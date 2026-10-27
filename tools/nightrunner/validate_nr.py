# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — パックの静的検証（参照切れ・UV・Molang・ボーン・名前・上限）。

    python3 tools/nightrunner/validate_nr.py            # 普通（まだ無い分類は「まだ無い」と書くだけ）
    python3 tools/nightrunner/validate_nr.py --strict   # 最終・CI 用（分類ごと欠けていても失敗）
    python3 tools/nightrunner/validate_nr.py --all      # 全件を出す（既定は分類ごとに 25 件まで）
    python3 tools/nightrunner/validate_nr.py --json build_preview/nightrunner/validate.json  # 機械向けの全件

調べること（DESIGN.md §10 の 3.）:

* **JSON**: BP / RP の全 .json が読めるか。同じ識別子の二重定義
* **RP の参照**: クライアントエンティティ → ジオメトリ・テクスチャ（png/tga）・アニメーション・
  アニメコントローラ・レンダーコントローラ・パーティクル・効果音・マテリアル。レンダーコントローラが使う
  `Geometry.x` / `Texture.x` / `Material.x` がエンティティにあるか、part_visibility のボーンがあるか。
  アニメ・コントローラの中の短い名前（animate / effect）がエンティティにあるか。アタッチャブルも同様。
  パーティクルのテクスチャ・UV・イベント、sound_definitions の音声ファイル（.ogg）、sounds.json、
  item_texture / terrain_texture / flipbook / blocks.json のパス
* **BP の参照**: エンティティのイベント → コンポーネントグループ、イベントの中の trigger、
  コンポーネントの event（timer・sensor…）、プロパティの型・既定値・set_property の値、
  スポーンルール・ルートテーブル・レシピ → アイテム／エンティティ／ブロックの実在、
  アイテムのアイコン → item_texture、ブロックのジオメトリ・material_instances → terrain_texture、
  .mcstructure のパレットにある nr: ブロック・エンティティ
* **ジオメトリ**: ボーン名の重複・親の欠け・循環、面ごとの UV（箱 UV も）がテクスチャの中か、面の名前
* **Molang**: 括弧・引用符の釣り合い、Python / JS の書き方（and / or / True / ** / === …）、裸の関数呼び出し、
  式の中の `=`、知らない `q.` クエリ・`math.` 関数（公式メタデータの一覧）と math の引数の数、
  `q.property('x')` が**そのエンティティの BP プロパティ**にあるか・client_sync か、
  `== '値'` / `!= '値'` の値が enum にあるか、整数との比較が範囲内か
* **契約（§3 / §5 / §12）**: `geometry.nr.z.*` が §3 の全ボーンを正しい親で持つか、gib の `p_*` ボーン、
  ゾンビ・gib・飛び道具・小道具のプロパティとイベント、演出 ID の登録簿（nr_registry）と spec が要る
  パーティクル・効果音・モーションが全部あるか
* **名前**: 全エンティティ・アイテム・ブロックに ja_JP / en_US の名前があるか、パック名
* **上限（§11）**: ゾンビのキューブ数（区分ごと）・テクスチャ寸法、武器・小道具、パック全体の容量
* **マニフェスト**: UUID・相互依存・Script API の版・エントリの main.js・pack_icon、JS の相対 import

パックがまだ無ければ「まだ無い」と書いて 0 で終わる（--strict では失敗）。
終了コード: 0 = 誤りなし（警告は出してもよい）、1 = 誤りあり。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nr_common import (BP, HERE, MIN_ENGINE, ROOT, RP, SERVER_API, SERVER_UI_API,  # noqa: E402
                       VERSION_TUPLE)

RESEARCH = os.path.join(ROOT, "build_preview", "nr_research")

# ---------------------------------------------------------------------------
#  契約（DESIGN.md）。nr_rig / nr_spec があればそちらと突き合わせる
# ---------------------------------------------------------------------------
def _side(s):
    return [(f"leg_{s}", "pelvis"), (f"shin_{s}", f"leg_{s}"), (f"foot_{s}", f"shin_{s}"),
            (f"stump_leg_{s}_lower", f"leg_{s}"), (f"stump_leg_{s}_upper", "pelvis")]


def _arm(s):
    return [(f"arm_{s}", "chest"), (f"forearm_{s}", f"arm_{s}"), (f"hand_{s}", f"forearm_{s}"),
            (f"arm_{s}_wound", f"arm_{s}"), (f"stump_arm_{s}_lower", f"arm_{s}"),
            (f"stump_arm_{s}_upper", "chest")]


# §3 の骨格（名前 -> 親）
SKELETON = dict([("root", None), ("waist", "root"), ("pelvis", "waist")] + _side("r") + _side("l")
                + [("torso", "waist"), ("torso_wound", "torso"), ("guts", "torso"),
                   ("stump_torso", "torso"), ("chest", "torso"), ("neck", "chest"), ("head", "neck"),
                   ("jaw", "head"), ("head_wound", "head"), ("skull_open", "head"),
                   ("stump_neck", "neck")] + _arm("r") + _arm("l"))
GIB_TYPE_PARTS = ("p_head", "p_jaw", "p_arm_r", "p_arm_l", "p_forearm_r", "p_forearm_l",
                  "p_leg_r", "p_leg_l", "p_shin_r", "p_shin_l", "p_lower")
GIB_GENERIC_PARTS = ("p_guts", "p_brain", "p_chunk", "p_bone", "p_eye")
_LIMB = ("intact", "wounded", "broken", "cut_lower", "cut_upper")
ZOMBIE_PROPS = {
    "nr:head": ("enum", ("intact", "wounded", "jawless", "cracked", "severed", "crushed"), "intact"),
    "nr:arm_r": ("enum", _LIMB, "intact"), "nr:arm_l": ("enum", _LIMB, "intact"),
    "nr:leg_r": ("enum", _LIMB, "intact"), "nr:leg_l": ("enum", _LIMB, "intact"),
    "nr:torso": ("enum", ("intact", "slashed", "gutted", "halved"), "intact"),
    "nr:blood": ("int", (0, 3), 0), "nr:burn": ("int", (0, 3), 0), "nr:shock": ("int", (0, 1), 0),
    "nr:armor": ("int", (0, 3), None),     # 既定は種類ごと（spec の initial_armor）
    "nr:state": ("enum", ("normal", "crawl", "climb", "stagger", "down", "special", "dead"), "normal"),
    "nr:pose": ("int", (0, 7), 0), "nr:ability": ("int", (0, 7), 0), "nr:variant": ("int", (0, 3), 0),
}
GIB_PROPS = {"nr:ztype": ("int", (0, 63), None), "nr:part": ("int", (0, 15), None),
             "nr:spin": ("int", (0, 7), None), "nr:rest": ("int", (0, 3), None),
             "nr:bleed": ("int", (0, 1), None), "nr:side": ("int", (0, 1), None)}
ZOMBIE_EVENTS = ("nr:on_death", "nr:to_crawl", "nr:root_start", "nr:root_end", "nr:enrage", "nr:calm",
                 "nr:despawn")
# §11 の上限（区分 -> (キューブ, テクスチャの一辺)）
CLASS_LIMITS = {"common": (450, 512), "viral": (450, 512), "special": (650, 512), "night": (650, 512),
                "boss": (1100, 1024)}
WEAPON_LIMIT = (180, 512)
PROP_LIMIT = (700, 1024)
PACK_LIMIT_MB = 80.0
TEXTURE_SOFT_MAX = 2048

FACES = {"north", "south", "east", "west", "up", "down"}
SOUND_CATEGORIES = {"ambient", "block", "bottle", "bucket", "hostile", "music", "neutral", "player",
                    "record", "ui", "weather"}
VANILLA_MATERIALS = set("""
entity entity_alphablend entity_alphablend_nocolor entity_alphatest entity_alphatest_change_color
entity_alphatest_change_color_glint entity_alphatest_glint entity_alphatest_glint_item
entity_alphatest_multicolor_tint entity_beam entity_beam_additive entity_change_color entity_change_color_glint
entity_custom entity_dissolve_layer0 entity_dissolve_layer1 entity_emissive entity_emissive_alpha
entity_emissive_alpha_one_sided entity_flat_color_line entity_glint entity_lead_base entity_loyalty_rope
entity_multitexture entity_multitexture_alpha_test entity_multitexture_alpha_test_color_mask
entity_multitexture_color_mask entity_multitexture_masked entity_multitexture_multiplicative_blend entity_nocull
entity_static entity_alphatest_one_sided item_in_hand item_in_hand_entity_alphatest
item_in_hand_entity_alphatest_color item_in_hand_glint item_in_hand_multicolor_tint player player_alphatest
player_animated
""".split())
# バニラのプレイヤーのボーン（animation.nr.p.* が動かしてよい）
PLAYER_BONES = {b.lower() for b in """
root waist body head hat cape leftArm rightArm leftLeg rightLeg leftSleeve rightSleeve leftPants rightPants
jacket leftItem rightItem helmet rightArmArmor leftArmArmor bodyArmor belt rightBoot leftBoot rightLegging
leftLegging chestplate
""".split()}

# 公式メタデータ（bedrock-samples/metadata/molang_modules）の一覧の写し: 名前:最小引数:最大引数（-1 = 無制限）
_QUERIES = """
above_top_solid:0:-1 actor_count:0:-1 all:3:-1 all_animations_finished:0:-1 all_tags:0:-1
anger_level:0:0 anim_time:0:-1 any:3:-1 any_animation_finished:0:-1 any_tag:0:-1 approx_eq:2:-1
armor_color_slot:2:2 armor_damage_slot:1:1 armor_material_slot:1:1 armor_texture_slot:1:1
average_frame_time:0:1 base_swing_duration:0:-1 block_face:0:-1 block_has_all_tags:4:-1
block_has_any_tag:4:-1 block_neighbor_has_all_tags:1:-1 block_neighbor_has_any_tag:1:-1
block_state:1:1 blocking:0:-1 body_x_rotation:0:-1 body_y_rotation:0:-1 bone_aabb:1:1
bone_orientation_matrix:1:2 bone_orientation_trs:1:2 bone_origin:1:1 bone_rotation:1:1
camera_distance_range_lerp:2:2 camera_rotation:1:1 can_climb:0:-1 can_damage_nearby_mobs:0:-1
can_dash:0:-1 can_fly:0:-1 can_power_jump:0:-1 can_swim:0:-1 can_walk:0:-1 cape_flap_amount:0:-1
cardinal_block_face_placed_on:0:-1 cardinal_facing:0:-1 cardinal_facing_2d:0:-1
cardinal_player_facing:0:-1 client_max_render_distance:0:0 client_memory_tier:0:0
combine_entities:0:-1 cooldown_time:1:2 cooldown_time_remaining:0:2 count:0:-1
current_squish_value:0:-1 day:0:0 death_ticks:0:-1 debug_output:1:1 delta_time:0:-1
distance_from_camera:0:-1 effect_emitter_count:0:-1 effect_particle_count:0:-1
entity_biome_has_all_tags:1:-1 entity_biome_has_any_identifier:1:-1 entity_biome_has_any_tags:1:-1
equipment_count:0:0 equipped_item_all_tags:0:1 equipped_item_any_tag:0:1
equipped_item_is_attachable:1:1 eye_target_x_rotation:0:-1 eye_target_y_rotation:0:-1
facing_target_to_range_attack:0:-1 frame_alpha:0:-1 fuse_time:0:-1 get_actor_info_id:1:1
get_animation_frame:0:0 get_default_bone_pivot:0:-1 get_equipped_item_name:0:2
get_level_seed_based_fraction:0:0 get_locator_offset:0:-1 get_name:0:1 get_pack_setting:1:1
get_root_locator_offset:2:2 graphics_mode_is_any:1:255 ground_speed:0:-1 had_component_group:1:1
has_all_biome_tags:0:-1 has_any_biome_tags:0:-1 has_any_family:1:-1
has_any_leashed_entity_of_type:0:-1 has_armor_slot:1:1 has_biome_tag:0:-1 has_block_state:1:1
has_cape:0:-1 has_collision:0:-1 has_dash_cooldown:0:-1 has_gravity:0:-1 has_head_gear:0:-1
has_owner:0:-1 has_player_rider:0:0 has_property:1:1 has_rider:0:-1 has_target:0:-1
head_is_in_water:0:-1 head_roll_angle:0:-1 head_x_rotation:1:-1 head_y_rotation:1:-1 health:0:0
heartbeat_interval:0:0 heartbeat_phase:0:0 heightmap:0:-1 hurt_direction:0:0 hurt_time:0:0
in_range:3:3 invulnerable_ticks:0:-1 is_admiring:0:-1 is_alive:0:-1 is_angry:0:-1 is_attached:0:0
is_attached_to_entity:0:-1 is_avoiding_block:0:-1 is_avoiding_mobs:0:-1 is_baby:0:-1
is_breathing:0:-1 is_bribed:0:-1 is_carrying_block:0:-1 is_casting:0:-1 is_celebrating:0:-1
is_celebrating_special:0:-1 is_charged:0:-1 is_charging:0:-1 is_chested:0:-1
is_cooldown_category:1:2 is_crawling:0:-1 is_critical:0:-1 is_croaking:0:-1 is_dancing:0:-1
is_delayed_attacking:0:-1 is_digging:0:-1 is_eating:0:-1 is_eating_mob:0:-1 is_elder:0:-1
is_emerging:0:-1 is_emoting:0:-1 is_enchanted:0:-1 is_fire_immune:0:-1 is_first_person:0:-1
is_ghost:0:-1 is_gliding:0:-1 is_grazing:0:-1 is_idling:0:-1 is_ignited:0:-1 is_illager_captain:0:-1
is_in_contact_with_water:0:-1 is_in_lava:0:-1 is_in_love:0:-1 is_in_ui:0:-1 is_in_water:0:-1
is_in_water_or_rain:0:-1 is_interested:0:-1 is_invisible:0:-1 is_item_equipped:0:1
is_item_name_any:2:-1 is_jump_goal_jumping:0:-1 is_jumping:0:-1 is_laying_down:0:-1
is_laying_egg:0:-1 is_leashed:0:-1 is_levitating:0:-1 is_lingering:0:-1 is_local_player:0:-1
is_moving:0:-1 is_name_any:1:-1 is_on_fire:0:-1 is_on_ground:0:-1 is_onfire:0:-1 is_orphaned:0:-1
is_owner_identifier_any:1:-1 is_pack_setting_enabled:1:1 is_pack_setting_selected:2:2
is_persona_or_premium_skin:0:0 is_playing_dead:0:-1 is_powered:0:-1 is_pregnant:0:-1
is_ram_attacking:0:-1 is_resting:0:-1 is_riding:0:-1 is_riding_any_entity_of_type:0:-1
is_roaring:0:-1 is_rolling:0:-1 is_saddled:0:-1 is_scared:0:-1 is_searching:0:0
is_selected_item:0:-1 is_shaking:0:-1 is_shaking_wetness:0:-1 is_sheared:0:-1 is_shield_powered:0:-1
is_silent:0:-1 is_sitting:0:-1 is_sleeping:0:-1 is_sneaking:0:-1 is_sneezing:0:-1 is_sniffing:0:-1
is_sonic_boom:0:-1 is_spectator:0:0 is_sprinting:0:-1 is_stackable:0:-1 is_stalking:0:-1
is_standing:0:-1 is_stunned:0:-1 is_swimming:0:-1 is_tamed:0:-1 is_transforming:0:-1
is_using_item:0:-1 is_wall_climbing:0:-1 item_in_use_duration:0:-1 item_is_charged:0:1
item_max_use_duration:0:-1 item_remaining_use_duration:0:-1 item_slot_to_bone_name:1:1
key_frame_lerp_time:0:-1 kinetic_weapon_damage_duration:0:-1 kinetic_weapon_delay:0:-1
kinetic_weapon_dismount_duration:0:-1 kinetic_weapon_knockback_duration:0:-1 last_frame_time:0:1
last_hit_by_player:0:-1 last_input_mode_is_any:1:-1 leashed_entity_count:0:-1 lie_amount:0:-1
life_span:0:-1 life_time:0:-1 lod_index:0:-1 log:1:1 main_hand_item_max_duration:0:-1
main_hand_item_use_duration:0:-1 mark_variant:0:-1 max_durability:0:0 max_health:0:0
max_trade_tier:0:-1 maximum_frame_time:0:1 minimum_frame_time:0:1 model_scale:0:-1
modified_distance_moved:0:-1 modified_move_speed:0:-1 modified_swing_duration:0:-1
moon_brightness:0:0 moon_phase:0:0 movement_direction:1:1 noise:0:-1 on_fire_time:0:-1
out_of_control:0:-1 overlay_alpha:0:-1 owner_identifier:0:0 player_level:0:0 position:1:1
position_delta:1:1 previous_squish_value:0:-1 property:1:1 relative_block_has_all_tags:1:-1
relative_block_has_any_tag:1:-1 remaining_durability:0:0 ride_body_x_rotation:0:0
ride_body_y_rotation:0:0 ride_head_x_rotation:0:0 ride_head_y_rotation:0:1 rider_body_x_rotation:1:1
rider_body_y_rotation:1:1 rider_head_x_rotation:1:1 rider_head_y_rotation:1:2 roll_counter:0:-1
rotation_to_camera:1:1 scoreboard:1:1 server_memory_tier:0:0 shake_angle:0:-1 shake_time:0:-1
shield_blocking_bob:0:0 show_bottom:0:-1 sit_amount:0:-1 skin_id:0:-1 sleep_rotation:0:0
sneeze_counter:0:-1 spellcolor:0:-1 standing_scale:0:-1 state_time:0:0 structural_integrity:0:0
surface_particle_color:0:0 surface_particle_texture_coordinate:0:0 surface_particle_texture_size:0:0
swell_amount:0:-1 swelling_dir:0:-1 swim_amount:0:0 tail_angle:0:-1 target_x_rotation:0:-1
target_y_rotation:0:-1 texture_frame_index:0:-1 ticks_since_last_kinetic_weapon_hit:0:-1
time_of_day:0:0 time_since_last_vibration_detection:0:0 time_stamp:0:-1 timer_flag_1:0:0
timer_flag_2:0:0 timer_flag_3:0:0 total_emitter_count:0:-1 total_particle_count:0:-1
touch_only_affects_hotbar:0:0 trade_tier:0:-1 unhappy_counter:0:-1 variant:0:-1 vertical_speed:0:-1
walk_distance:0:-1 wing_flap_position:0:-1 wing_flap_speed:0:-1 yaw_speed:0:-1
"""
_MATH = """
abs:1:1 acos:1:1 asin:1:1 atan:1:1 atan2:2:2 ceil:1:1 clamp:3:3 copy_sign:2:2 cos:1:1 die_roll:3:3
die_roll_integer:3:3 ease_in_back:3:3 ease_in_bounce:3:3 ease_in_circ:3:3 ease_in_cubic:3:3
ease_in_elastic:3:3 ease_in_expo:3:3 ease_in_out_back:3:3 ease_in_out_bounce:3:3
ease_in_out_circ:3:3 ease_in_out_cubic:3:3 ease_in_out_elastic:3:3 ease_in_out_expo:3:3
ease_in_out_quad:3:3 ease_in_out_quart:3:3 ease_in_out_quint:3:3 ease_in_out_sine:3:3
ease_in_quad:3:3 ease_in_quart:3:3 ease_in_quint:3:3 ease_in_sine:3:3 ease_out_back:3:3
ease_out_bounce:3:3 ease_out_circ:3:3 ease_out_cubic:3:3 ease_out_elastic:3:3 ease_out_expo:3:3
ease_out_quad:3:3 ease_out_quart:3:3 ease_out_quint:3:3 ease_out_sine:3:3 exp:1:1 floor:1:1
hermite_blend:1:1 inverse_lerp:3:3 lerp:3:3 lerprotate:3:3 ln:1:1 max:2:2 min:2:2 min_angle:1:1
mod:2:2 pi:0:0 pow:2:2 random:2:2 random_integer:2:2 round:1:1 sign:1:1 sin:1:1 sqrt:1:1 trunc:1:1
"""


def _arity_table(text):
    out = {}
    for tok in text.split():
        n, a, b = tok.split(":")
        out[n] = (int(a), int(b))
    return out


QUERIES = _arity_table(_QUERIES)
MATH = _arity_table(_MATH)


def _load_live_metadata():
    """build_preview に公式メタデータがあれば一覧に足す（新しいクエリに追いつくため）。"""
    p = os.path.join(RESEARCH, "bedrock-samples", "metadata", "molang_modules", "mojang-molang-queries.json")
    if not os.path.exists(p):
        return
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        for q in d.get("queries", []):
            n = q["name"].split(".", 1)[1]
            QUERIES.setdefault(n, (q.get("min_args", 0), q.get("max_args", -1)))
        for m in d.get("math_functions", []):
            n = m["name"].split(".", 1)[1]
            MATH.setdefault(n, (m.get("min_args", 0), m.get("max_args", -1)))
    except Exception:  # noqa: BLE001
        pass


_load_live_metadata()


# ===========================================================================
#  報告
# ===========================================================================
class Report:
    def __init__(self):
        self.errors = defaultdict(list)
        self.warnings = defaultdict(list)
        self.notes = []
        self._seen = set()

    def err(self, cat, msg):
        if (0, cat, msg) not in self._seen:
            self._seen.add((0, cat, msg))
            self.errors[cat].append(msg)

    def warn(self, cat, msg):
        if (1, cat, msg) not in self._seen:
            self._seen.add((1, cat, msg))
            self.warnings[cat].append(msg)

    def note(self, msg):
        self.notes.append(msg)

    @property
    def n_err(self):
        return sum(len(v) for v in self.errors.values())

    @property
    def n_warn(self):
        return sum(len(v) for v in self.warnings.values())


R = Report()


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def walk(root, exts=(".json",)):
    if not os.path.isdir(root):
        return []
    out = []
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            if f.endswith(exts):
                out.append(os.path.join(base, f))
    return out


DOCS: dict = {}       # 絶対パス -> 読んだ JSON


def load(p):
    return DOCS.get(p)


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def lower_keys(d):
    return {str(k).lower() for k in (d or {})}


# ===========================================================================
#  Molang
# ===========================================================================
_MOLANG_HINT = re.compile(r"(?<![\w.])(q|v|t|c|query|variable|temp|context|math)\.[a-z_]", re.I)
_OPS_HINT = re.compile(r"[()?<>=!&|*+]")
_STR = re.compile(r"'[^']*'")
_PY_WORDS = re.compile(r"(?<![\w.])(and|or|not|True|False|None|elif|lambda|def|pass|is|in)(?![\w.])")
_BARE_CALL = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*\(")
_ALLOWED_BARE = {"loop", "for_each", "return"}
_Q_CALL = re.compile(r"(?<![\w.])(?:q|query)\.([A-Za-z_]\w*)", re.I)
_M_CALL = re.compile(r"(?<![\w.])math\.([A-Za-z_]\w*)", re.I)
_PROP = re.compile(r"(?<![\w.])(?:q|query)\.(property|has_property)\s*\(\s*'([^']*)'\s*\)", re.I)
_PROP_CMP_R = re.compile(r"(?<![\w.])(?:q|query)\.property\s*\(\s*'([^']*)'\s*\)\s*(==|!=)\s*'([^']*)'", re.I)
_PROP_CMP_L = re.compile(r"'([^']*)'\s*(==|!=)\s*(?<![\w.])(?:q|query)\.property\s*\(\s*'([^']*)'\s*\)", re.I)
_PROP_NUM = re.compile(r"(?<![\w.])(?:q|query)\.property\s*\(\s*'([^']*)'\s*\)\s*(==|!=|<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)",
                       re.I)
_PROP_ARG = re.compile(r"(?<![\w.])(?:q|query)\.(?:property|has_property)\s*\(\s*([^'\s)])", re.I)

_molang_cache: dict = {}


def looks_molang(s: str) -> bool:
    return bool(_MOLANG_HINT.search(s))


def _arg_count(s: str, open_idx: int):
    """s[open_idx] == '(' の呼び出しの引数の数（入れ子・文字列を考える）。閉じなければ None。"""
    depth, n, has = 0, 0, False
    i = open_idx
    while i < len(s):
        ch = s[i]
        if ch == "'":
            j = s.find("'", i + 1)
            if j < 0:
                return None
            has = True
            i = j + 1
            continue
        if ch in "([{":
            depth += 1
            if depth > 1:
                has = True
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return n + 1 if has else 0
        elif ch == "," and depth == 1:
            n += 1
        elif not ch.isspace() and depth >= 1:
            has = True
        i += 1
    return None


def molang_issues(s: str):
    """Molang の文字列の一般的な誤り [(重さ 'E'|'W', 文)]。同じ文字列は一度だけ調べる。"""
    if s in _molang_cache:
        return _molang_cache[s]
    out = []
    if s.count("'") % 2:
        out.append(("E", "引用符 ' が閉じていない"))
    bare = _STR.sub("''", s)
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in bare:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack[-1] != pairs[ch]:
                out.append(("E", f"括弧の釣り合いが取れていない（{ch}）"))
                stack = None
                break
            stack.pop()
    if stack:
        out.append(("E", f"括弧が閉じていない（{''.join(stack)}）"))
    m = _PY_WORDS.search(bare)
    if m:
        out.append(("E", f"Python の書き方 '{m.group(1)}'（Molang は && || ! true false）"))
    for bad, why in (("**", "べき乗は math.pow"), ("//", "Molang に // は無い"), ("===", "JS の ==="),
                     ("!==", "JS の !=="), ("<>", "<> は無い"), ("++", "++ は無い"), ("--", "-- は無い"),
                     ("+=", "+= は無い"), ("-=", "-= は無い")):
        if bad in bare:
            out.append(("E", f"'{bad}'（{why}）"))
    # 式の中の単独の = （代入は ; で終わる文の中だけ）
    if ";" not in bare and re.search(r"(?<![=!<>])=(?![=>])", bare):
        out.append(("E", "式の中に単独の '='（比較は ==、代入は 'v.x = 1;' の文で）"))
    for m in _BARE_CALL.finditer(bare):
        if m.group(1).lower() not in _ALLOWED_BARE:
            out.append(("E", f"名前空間の無い関数呼び出し {m.group(1)}(…)（math.{m.group(1)} など）"))
            break
    for m in _Q_CALL.finditer(bare):
        name = m.group(1).lower()
        if name not in QUERIES:
            out.append(("E", f"知らないクエリ q.{name}"))
            continue
        end = m.end()
        while end < len(bare) and bare[end] == " ":
            end += 1
        n = _arg_count(bare, end) if end < len(bare) and bare[end] == "(" else 0
        lo, hi = QUERIES[name]
        if n is not None and (n < lo or (hi >= 0 and n > hi)) and not (n == 0 and lo > 0 and end >= len(bare)):
            out.append(("W", f"q.{name} の引数の数 {n}（公式の一覧では {lo}〜{'∞' if hi < 0 else hi}）"))
    for m in _M_CALL.finditer(bare):
        name = m.group(1).lower()
        if name not in MATH:
            out.append(("E", f"知らない関数 math.{name}"))
            continue
        lo, hi = MATH[name]
        end = m.end()
        while end < len(bare) and bare[end] == " ":
            end += 1
        if name == "pi":
            continue
        if end >= len(bare) or bare[end] != "(":
            out.append(("E", f"math.{name} に括弧が無い"))
            continue
        n = _arg_count(bare, end)
        if n is not None and (n < lo or (hi >= 0 and n > hi)):
            out.append(("E", f"math.{name} の引数が {n} 個（{lo}{'' if lo == hi else '〜' + str(hi)} 個）"))
    if _PROP_ARG.search(s):
        out.append(("E", "q.property / q.has_property の引数は 'nr:名前' の文字列で"))
    _molang_cache[s] = out
    return out


def prop_refs(s: str):
    """(名前の集合, enum 比較 [(名前, op, 値)], 数値比較 [(名前, op, 数)])"""
    names = {m.group(2) for m in _PROP.finditer(s) if m.group(1).lower() == "property"}
    has = {m.group(2) for m in _PROP.finditer(s) if m.group(1).lower() == "has_property"}
    cmps = [(m.group(1), m.group(2), m.group(3)) for m in _PROP_CMP_R.finditer(s)]
    cmps += [(m.group(3), m.group(2), m.group(1)) for m in _PROP_CMP_L.finditer(s)]
    nums = [(m.group(1), m.group(2), float(m.group(3))) for m in _PROP_NUM.finditer(s)]
    return names, has, cmps, nums


def collect_strings(obj, path="", skip_keys=()):
    """(パス, 文字列) を全部。skip_keys の鍵の下は見ない。"""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip_keys:
                continue
            yield from collect_strings(v, f"{path}/{k}", skip_keys)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from collect_strings(v, f"{path}[{i}]", skip_keys)


class MolangUse:
    """リソースごとの Molang（あとでエンティティのプロパティと突き合わせる）。"""

    def __init__(self):
        self.by_res = defaultdict(list)    # 資源名 -> [(どこ, 文字列)]

    def add(self, res, where, s):
        self.by_res[res].append((where, s))


MOL = MolangUse()


def check_molang_list(where_prefix, items, res=None, all_strings=False):
    """items: [(パス, 文字列)]。Molang らしいものの一般の誤りを見て、res があれば MOL に記録。"""
    for path, s in items:
        if not s or not isinstance(s, str):
            continue
        if not all_strings and not looks_molang(s):
            continue
        for sev, msg in molang_issues(s):
            (R.err if sev == "E" else R.warn)("molang", f"{where_prefix}{path}: {msg} — {s[:90]}")
        if res is not None and ("property" in s.lower()):
            MOL.add(res, f"{where_prefix}{path}", s)


# ===========================================================================
#  読み込み
# ===========================================================================
class Idx:
    textures: set = set()
    tex_files: dict = {}
    geos: dict = {}
    anims: dict = {}
    ctrls: dict = {}
    rcs: dict = {}
    particles: dict = {}
    client: dict = {}
    attach: dict = {}
    sound_defs: dict = {}
    item_tex: dict = {}
    terrain_tex: dict = {}
    materials: set = set()
    entities: dict = {}
    items: dict = {}
    blocks: dict = {}
    structures: dict = {}
    lang: dict = {}
    bp_size = 0
    rp_size = 0


I = Idx()


def load_all():
    for pack in (BP, RP):
        for p in walk(pack):
            try:
                with open(p, encoding="utf-8") as fh:
                    DOCS[p] = json.load(fh)
            except Exception as exc:  # noqa: BLE001
                R.err("json", f"{rel(p)}: 読めない JSON — {exc}")
    # テクスチャ（拡張子なしの RP 相対パス）
    for p in walk(RP, (".png", ".tga", ".jpg", ".jpeg")):
        key = os.path.splitext(os.path.relpath(p, RP))[0].replace(os.sep, "/")
        I.textures.add(key)
        I.tex_files[key] = p
    for pack, attr in ((BP, "bp_size"), (RP, "rp_size")):
        total = 0
        for base, _d, files in os.walk(pack):
            for f in files:
                total += os.path.getsize(os.path.join(base, f))
        setattr(I, attr, total)


def _register(table, ident, value, path, kind):
    if ident in table:
        R.err("duplicate", f"{kind} {ident} が二重に定義（{rel(table[ident][1])} と {rel(path)}）")
        return
    table[ident] = (value, path)


def index_rp():
    for p in walk(os.path.join(RP, "models")):
        doc = load(p)
        if not isinstance(doc, dict):
            continue
        if "minecraft:geometry" in doc:
            for g in doc["minecraft:geometry"]:
                d = g.get("description", {})
                ident = d.get("identifier")
                if not ident:
                    R.err("geometry", f"{rel(p)}: identifier の無いジオメトリ")
                    continue
                _register(I.geos, ident, dict(tw=d.get("texture_width", 64), th=d.get("texture_height", 64),
                                              bones=g.get("bones", []) or [], desc=d), p, "geometry")
        else:
            for k, g in doc.items():
                if k.startswith("geometry."):
                    ident = k.split(":")[0]
                    _register(I.geos, ident, dict(tw=g.get("texturewidth", 64), th=g.get("textureheight", 64),
                                                  bones=g.get("bones", []) or [], desc={}), p, "geometry")
    for p in walk(os.path.join(RP, "animations")):
        doc = load(p)
        for k, v in (doc or {}).get("animations", {}).items():
            _register(I.anims, k, v, p, "animation")
    for p in walk(os.path.join(RP, "animation_controllers")):
        doc = load(p)
        for k, v in (doc or {}).get("animation_controllers", {}).items():
            _register(I.ctrls, k, v, p, "animation controller")
    for p in walk(os.path.join(RP, "render_controllers")):
        doc = load(p)
        for k, v in (doc or {}).get("render_controllers", {}).items():
            _register(I.rcs, k, v, p, "render controller")
    for p in walk(os.path.join(RP, "particles")):
        doc = load(p)
        try:
            ident = doc["particle_effect"]["description"]["identifier"]
        except Exception:  # noqa: BLE001
            R.err("particle", f"{rel(p)}: particle_effect.description.identifier が無い")
            continue
        _register(I.particles, ident, doc["particle_effect"], p, "particle")
    for p in walk(os.path.join(RP, "entity")):
        doc = load(p)
        try:
            d = doc["minecraft:client_entity"]["description"]
            ident = d["identifier"]
        except Exception:  # noqa: BLE001
            R.err("client_entity", f"{rel(p)}: minecraft:client_entity.description.identifier が無い")
            continue
        _register(I.client, ident, d, p, "client entity")
    for p in walk(os.path.join(RP, "attachables")):
        doc = load(p)
        try:
            d = doc["minecraft:attachable"]["description"]
            ident = d["identifier"]
        except Exception:  # noqa: BLE001
            R.err("attachable", f"{rel(p)}: minecraft:attachable.description.identifier が無い")
            continue
        _register(I.attach, ident, d, p, "attachable")
    sd = load(os.path.join(RP, "sounds", "sound_definitions.json"))
    if isinstance(sd, dict):
        I.sound_defs = sd.get("sound_definitions", {}) if "sound_definitions" in sd else \
            {k: v for k, v in sd.items() if k != "format_version"}
    it = load(os.path.join(RP, "textures", "item_texture.json"))
    if isinstance(it, dict):
        I.item_tex = it.get("texture_data", {}) or {}
    tt = load(os.path.join(RP, "textures", "terrain_texture.json"))
    if isinstance(tt, dict):
        I.terrain_tex = tt.get("texture_data", {}) or {}
    for p in walk(os.path.join(RP, "materials"), (".material",)):
        try:
            with open(p, encoding="utf-8") as fh:
                src = re.sub(r"//[^\n]*", "", fh.read())
            for k in json.loads(src).get("materials", {}):
                if k != "version":
                    I.materials.add(k.split(":")[0])
        except Exception as exc:  # noqa: BLE001
            R.err("json", f"{rel(p)}: 読めない material — {exc}")
    # 言語
    for pack in (BP, RP):
        d = os.path.join(pack, "texts")
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".lang"):
                I.lang[(pack, f[:-5])] = parse_lang(os.path.join(d, f))


def parse_lang(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if raw.startswith("﻿"):
        R.warn("lang", f"{rel(path)}: BOM 付き（無しにする）")
        raw = raw[1:]
    for i, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("##"):
            continue
        if "=" not in s:
            R.err("lang", f"{rel(path)}:{i}: '=' の無い行: {s[:60]}")
            continue
        k, v = line.split("=", 1)
        if "##" in v:
            v = v.split("##", 1)[0]
        k = k.strip()
        if k in out:
            R.err("lang", f"{rel(path)}:{i}: 鍵 {k} が二重")
        out[k] = v.rstrip("\t ")
    return out


def index_bp():
    for p in walk(os.path.join(BP, "entities")):
        doc = load(p)
        try:
            ent = doc["minecraft:entity"]
            ident = ent["description"]["identifier"]
        except Exception:  # noqa: BLE001
            R.err("entity", f"{rel(p)}: minecraft:entity.description.identifier が無い")
            continue
        _register(I.entities, ident, ent, p, "entity")
    for p in walk(os.path.join(BP, "items")):
        doc = load(p)
        try:
            it = doc["minecraft:item"]
            ident = it["description"]["identifier"]
        except Exception:  # noqa: BLE001
            R.err("item", f"{rel(p)}: minecraft:item.description.identifier が無い")
            continue
        _register(I.items, ident, it, p, "item")
    for p in walk(os.path.join(BP, "blocks")):
        doc = load(p)
        try:
            b = doc["minecraft:block"]
            ident = b["description"]["identifier"]
        except Exception:  # noqa: BLE001
            R.err("block", f"{rel(p)}: minecraft:block.description.identifier が無い")
            continue
        _register(I.blocks, ident, b, p, "block")
    sdir = os.path.join(BP, "structures")
    for p in walk(sdir, (".mcstructure",)):
        for sid in structure_ids(os.path.relpath(p, sdir)):
            I.structures[sid] = p


def structure_ids(relpath):
    """structures/ からの相対パス -> 参照できる ID（'nr/apartment.mcstructure' -> 'nr:apartment'）。"""
    p = relpath.replace(os.sep, "/")[:-len(".mcstructure")]
    if "/" in p:
        ns, rest = p.split("/", 1)
        return [f"{ns}:{rest}"]
    return [p, f"mystructure:{p}"]


# ===========================================================================
#  NBT（.mcstructure は little-endian の NBT）
# ===========================================================================
class _NBT:
    def __init__(self, data):
        self.d = data
        self.i = 0

    def _u(self, fmt):
        v = struct.unpack_from("<" + fmt, self.d, self.i)
        self.i += struct.calcsize("<" + fmt)
        return v[0]

    def _str(self):
        n = self._u("H")
        s = self.d[self.i:self.i + n].decode("utf-8", "replace")
        self.i += n
        return s

    def payload(self, t):
        if t == 1:
            return self._u("b")
        if t == 2:
            return self._u("h")
        if t == 3:
            return self._u("i")
        if t == 4:
            return self._u("q")
        if t == 5:
            return self._u("f")
        if t == 6:
            return self._u("d")
        if t == 7:
            n = self._u("i")
            v = self.d[self.i:self.i + n]
            self.i += n
            return v
        if t == 8:
            return self._str()
        if t == 9:
            et = self._u("b")
            n = self._u("i")
            if et == 3:          # 大きな int のリスト（block_indices）は一気に読む
                v = list(struct.unpack_from(f"<{n}i", self.d, self.i))
                self.i += 4 * n
                return v
            return [self.payload(et) for _ in range(n)]
        if t == 10:
            out = {}
            while True:
                tt = self._u("b")
                if tt == 0:
                    return out
                name = self._str()
                out[name] = self.payload(tt)
        if t == 11:
            n = self._u("i")
            v = list(struct.unpack_from(f"<{n}i", self.d, self.i))
            self.i += 4 * n
            return v
        if t == 12:
            n = self._u("i")
            v = list(struct.unpack_from(f"<{n}q", self.d, self.i))
            self.i += 8 * n
            return v
        raise ValueError(f"知らない NBT タグ {t}")


def read_mcstructure(path):
    """.mcstructure を読んで {size, palette:[name...], states:[{}...], indices:[...], entities:[id...]} を返す。"""
    with open(path, "rb") as fh:
        data = fh.read()
    if not data or data[0] != 10:
        raise ValueError("NBT の compound で始まっていない")
    r = _NBT(data)
    r.i = 1
    r._str()
    root = r.payload(10)
    size = root.get("size")
    st = root.get("structure", {})
    pal = st.get("palette", {}).get("default", {}).get("block_palette", [])
    layers = st.get("block_indices", [])
    ents = []
    for e in st.get("entities", []):
        ident = e.get("identifier") if isinstance(e, dict) else None
        if ident:
            ents.append(ident)
    return {"size": size, "palette": [b.get("name") for b in pal], "states": [b.get("states", {}) for b in pal],
            "indices": layers[0] if layers else [], "water": layers[1] if len(layers) > 1 else [],
            "entities": ents, "format_version": root.get("format_version")}


# ===========================================================================
#  ジオメトリ
# ===========================================================================
GEO_INFO: dict = {}     # id -> {bones: {lower: (name, parent)}, locators: set, cubes: int}


def check_geometries():
    for ident, (g, p) in sorted(I.geos.items()):
        tw, th = g["tw"], g["th"]
        where = f"{ident}（{rel(p)}）"
        if not (is_num(tw) and is_num(th) and tw > 0 and th > 0):
            R.err("geometry", f"{where}: texture_width/height が不正 {tw}x{th}")
            tw, th = 1e9, 1e9
        names = {}
        locators = set()
        cubes = 0
        bad_uv = 0
        bad_uv_first = None
        for b in g["bones"]:
            n = b.get("name")
            if not isinstance(n, str) or not n:
                R.err("geometry", f"{where}: 名前の無いボーン")
                continue
            if n.lower() in names:
                R.err("geometry", f"{where}: ボーン {n} が二重（大文字小文字は区別されない）")
            names[n.lower()] = (n, b.get("parent"))
            for key in ("pivot", "rotation"):
                v = b.get(key)
                if v is not None and not (isinstance(v, list) and len(v) == 3 and all(is_num(x) for x in v)):
                    R.err("geometry", f"{where}: {n}.{key} が数 3 個でない")
            for ln in (b.get("locators") or {}):
                locators.add(ln)
            for c in b.get("cubes", []) or []:
                cubes += 1
                size = c.get("size", [0, 0, 0])
                if not (isinstance(size, list) and len(size) == 3 and all(is_num(x) for x in size)):
                    R.err("geometry", f"{where}: {n} のキューブの size が不正")
                    continue
                if any(x < 0 for x in size):
                    R.warn("geometry", f"{where}: {n} に負の大きさのキューブ {size}")
                uv = c.get("uv")
                if isinstance(uv, dict):
                    for face, f in uv.items():
                        if face not in FACES:
                            R.err("geometry", f"{where}: {n} の面の名前 {face!r}")
                            continue
                        if not isinstance(f, dict) or "uv" not in f:
                            R.err("geometry", f"{where}: {n}.{face} の uv が無い")
                            continue
                        u, v = f["uv"]
                        w, h = f.get("uv_size", [0, 0])
                        if not all(is_num(x) for x in (u, v, w, h)):
                            R.err("geometry", f"{where}: {n}.{face} の uv が数でない")
                            continue
                        lo_u, hi_u = min(u, u + w), max(u, u + w)
                        lo_v, hi_v = min(v, v + h), max(v, v + h)
                        if lo_u < -1e-3 or lo_v < -1e-3 or hi_u > tw + 1e-3 or hi_v > th + 1e-3:
                            bad_uv += 1
                            bad_uv_first = bad_uv_first or f"{n}.{face} [{u},{v}]+[{w},{h}]"
                elif isinstance(uv, list) and len(uv) == 2:
                    u, v = uv
                    sx, sy, sz = size
                    if u < 0 or v < 0 or u + 2 * (sx + sz) > tw + 1e-3 or v + sy + sz > th + 1e-3:
                        bad_uv += 1
                        bad_uv_first = bad_uv_first or f"{n} 箱UV [{u},{v}] size {size}"
        if bad_uv:
            R.err("uv", f"{where}: テクスチャ {tw}x{th} の外に出る UV {bad_uv} 面（最初: {bad_uv_first}）")
        for low, (n, parent) in names.items():
            if parent and parent.lower() not in names:
                R.err("geometry", f"{where}: ボーン {n} の親 {parent} が無い")
        # 循環
        for low in names:
            seen, cur = set(), low
            while cur:
                if cur in seen:
                    R.err("geometry", f"{where}: ボーンの親子が循環（{names[low][0]}）")
                    break
                seen.add(cur)
                par = names.get(cur, (None, None))[1]
                cur = par.lower() if par else None
        GEO_INFO[ident] = {"bones": names, "locators": locators, "cubes": cubes, "tw": tw, "th": th}


def check_rig_contract(spec):
    """§3 / §5: ゾンビと gib のジオメトリのボーン。"""
    skeleton = dict(SKELETON)
    gib_type, gib_generic = GIB_TYPE_PARTS, GIB_GENERIC_PARTS
    required_locators = ()
    try:
        import nr_rig  # noqa: WPS433
        if dict(nr_rig.SKELETON_PARENT) != skeleton:
            R.warn("contract", "nr_rig.SKELETON_PARENT と DESIGN.md §3 の骨格が食い違う（どちらかを直す）")
        if tuple(nr_rig.GIB_TYPE_PARTS) != gib_type or tuple(nr_rig.GIB_GENERIC_PARTS) != gib_generic:
            R.warn("contract", "nr_rig の GIB_*_PARTS と DESIGN.md §5 が食い違う")
        required_locators = tuple(getattr(nr_rig, "REQUIRED_LOCATORS", ()))
    except Exception as exc:  # noqa: BLE001
        R.note(f"nr_rig を読めなかった（{type(exc).__name__}）ので DESIGN.md の表だけで調べる")
    zgeos = sorted(g for g in I.geos if g.startswith("geometry.nr.z."))
    for ident in zgeos:
        info = GEO_INFO.get(ident)
        if not info:
            continue
        bones = info["bones"]
        missing = [b for b in skeleton if b not in bones]
        if missing:
            R.err("rig", f"{ident}: §3 のボーンが無い: {', '.join(missing)}")
        for b, parent in skeleton.items():
            if b in bones:
                actual = bones[b][1]
                if (actual or None) != parent and (actual or "").lower() != (parent or ""):
                    R.err("rig", f"{ident}: {b} の親が {actual}（§3 では {parent}）")
        if required_locators:
            miss = [x for x in required_locators if x not in info["locators"]]
            if miss:
                R.warn("rig", f"{ident}: ロケータが無い: {', '.join(miss)}")
    for ident in sorted(g for g in I.geos if g.startswith("geometry.nr.gib.")):
        info = GEO_INFO.get(ident)
        if not info:
            continue
        need = gib_generic if ident.endswith(".generic") else gib_type
        missing = [b for b in need if b not in info["bones"]]
        if missing:
            R.err("rig", f"{ident}: gib のボーンが無い: {', '.join(missing)}")
    # spec と照らす（ゾンビ 50 体ぶんが揃っているか）
    if spec is not None and getattr(spec, "ZOMBIES", None):
        keys = [z["key"] for z in spec.ZOMBIES]
        completeness("zombie geometry", [f"geometry.nr.z.{k}" for k in keys], set(I.geos))
        completeness("gib geometry", [f"geometry.nr.gib.{k}" for k in keys] + ["geometry.nr.gib.generic"],
                     set(I.geos))


STRICT = False


def completeness(kind, required, have, cat="completeness"):
    """作る側が全部作ったか。一つも無ければ「まだ無い」（strict では誤り）、一部だけなら誤り。"""
    required = list(dict.fromkeys(required))
    missing = [r for r in required if r not in have]
    if not missing:
        return
    if len(missing) == len(required):
        if STRICT:
            R.err(cat, f"{kind}: {len(required)} 件すべて無い（例 {required[0]}）")
        else:
            R.note(f"{kind}: まだ無い（{len(required)} 件。生成器が出来たら揃う）")
        return
    shown = ", ".join(missing[:12]) + (f" …ほか {len(missing) - 12}" if len(missing) > 12 else "")
    R.err(cat, f"{kind}: {len(missing)} / {len(required)} 件が無い: {shown}")


# ===========================================================================
#  RP: アニメ・コントローラ・レンダーコントローラ・エンティティ
# ===========================================================================
def _keyframe_strings(anim):
    out = []
    for bone, ch in (anim.get("bones") or {}).items():
        for chan in ("rotation", "position", "scale"):
            v = ch.get(chan) if isinstance(ch, dict) else None
            if v is None:
                continue
            out.extend(collect_strings(v, f"/bones/{bone}/{chan}"))
    for key in ("anim_time_update", "blend_weight", "start_delay", "loop_delay"):
        if isinstance(anim.get(key), str):
            out.append((f"/{key}", anim[key]))
    for t, v in (anim.get("timeline") or {}).items():
        out.extend(collect_strings(v, f"/timeline/{t}"))
    for key in ("particle_effects", "sound_effects"):
        for path, s in collect_strings(anim.get(key) or {}, f"/{key}"):
            if path.endswith("pre_effect_script"):
                out.append((path, s))
    return out


def anim_effects(anim_or_state):
    """アニメ／コントローラの状態が使う (particle 短名, locator) と sound 短名。"""
    parts, sounds = [], []

    def grab(v, into, with_loc):
        items = v if isinstance(v, list) else [v]
        for e in items:
            if isinstance(e, dict) and "effect" in e:
                into.append((e["effect"], e.get("locator")) if with_loc else e["effect"])
    pe = anim_or_state.get("particle_effects")
    se = anim_or_state.get("sound_effects")
    if isinstance(pe, dict):
        for v in pe.values():
            grab(v, parts, True)
    elif isinstance(pe, list):
        grab(pe, parts, True)
    if isinstance(se, dict):
        for v in se.values():
            grab(v, sounds, False)
    elif isinstance(se, list):
        grab(se, sounds, False)
    return parts, sounds


def check_animations():
    for ident, (a, p) in sorted(I.anims.items()):
        where = f"{ident}: "
        if not isinstance(a, dict):
            R.err("animation", f"{ident}: 辞書でない")
            continue
        loop = a.get("loop", False)
        if loop not in (True, False, "hold_on_last_frame"):
            R.err("animation", f"{where}loop は true / false / \"hold_on_last_frame\"（{loop!r}）")
        length = a.get("animation_length")
        if length is not None and not (is_num(length) and length >= 0):
            R.err("animation", f"{where}animation_length が不正 {length!r}")
        maxt = 0.0
        for bone, ch in (a.get("bones") or {}).items():
            if not isinstance(ch, dict):
                R.err("animation", f"{where}{bone} が辞書でない")
                continue
            for chan, v in ch.items():
                if chan not in ("rotation", "position", "scale", "relative_to"):
                    R.warn("animation", f"{where}{bone} の知らない channel {chan}")
                if isinstance(v, dict) and chan != "relative_to":
                    for t in v:
                        try:
                            maxt = max(maxt, float(t))
                        except ValueError:
                            R.err("animation", f"{where}{bone}.{chan} のキーフレームの時刻 {t!r} が数でない")
                elif isinstance(v, list) and len(v) != 3:
                    R.err("animation", f"{where}{bone}.{chan} は 3 要素")
        for t in list((a.get("timeline") or {})) + list((a.get("particle_effects") or {}) if isinstance(
                a.get("particle_effects"), dict) else []) + list((a.get("sound_effects") or {}) if isinstance(
                a.get("sound_effects"), dict) else []):
            try:
                maxt = max(maxt, float(t))
            except ValueError:
                R.err("animation", f"{where}時刻 {t!r} が数でない")
        if is_num(length) and maxt > length + 1e-3:
            R.warn("animation", f"{where}キーフレーム {maxt:.3f}s が animation_length {length} の後ろ")
        check_molang_list(where, _keyframe_strings(a), res=("anim", ident), all_strings=True)
    for ident, (c, p) in sorted(I.ctrls.items()):
        where = f"{ident}: "
        states = (c or {}).get("states") or {}
        if not states:
            R.err("controller", f"{where}states が空")
            continue
        init = c.get("initial_state", "default")
        if init not in states:
            R.err("controller", f"{where}initial_state {init!r} が states に無い")
        strings = []
        for sname, st in states.items():
            for tr in st.get("transitions", []) or []:
                for target, cond in (tr.items() if isinstance(tr, dict) else []):
                    if target not in states:
                        R.err("controller", f"{where}{sname} → 無い状態 {target}")
                    if isinstance(cond, str):
                        strings.append((f"/{sname}/transitions/{target}", cond))
            for key in ("on_entry", "on_exit"):
                for i, s in enumerate(st.get(key, []) or []):
                    strings.append((f"/{sname}/{key}[{i}]", s))
            for i, an in enumerate(st.get("animations", []) or []):
                if isinstance(an, dict):
                    for k, cond in an.items():
                        if isinstance(cond, str):
                            strings.append((f"/{sname}/animations/{k}", cond))
            bt = st.get("blend_transition")
            if bt is not None and not is_num(bt) and not isinstance(bt, dict):
                R.err("controller", f"{where}{sname}.blend_transition が不正")
        check_molang_list(where, strings, res=("ctrl", ident), all_strings=True)
    for ident, (rc, p) in sorted(I.rcs.items()):
        where = f"{ident}: "
        strings = []
        for key in ("geometry",):
            if isinstance(rc.get(key), str):
                strings.append((f"/{key}", rc[key]))
        for key in ("textures",):
            for i, s in enumerate(rc.get(key, []) or []):
                strings.append((f"/{key}[{i}]", s))
        for key in ("materials", "part_visibility"):
            for i, d in enumerate(rc.get(key, []) or []):
                for b, s in (d.items() if isinstance(d, dict) else []):
                    strings.append((f"/{key}[{i}]/{b}", s))
                    if isinstance(s, bool):
                        continue
        for key in ("color", "overlay_color", "on_fire_color", "is_hurt_color"):
            for k, s in (rc.get(key) or {}).items():
                strings.append((f"/{key}/{k}", s))
        for key in ("uv_anim",):
            strings.extend(collect_strings(rc.get(key) or {}, f"/{key}"))
        for key in ("light_color_multiplier", "ignore_lighting", "filter_lighting"):
            if isinstance(rc.get(key), str):
                strings.append((f"/{key}", rc[key]))
        strings = [(a, b) for a, b in strings if isinstance(b, str)]
        check_molang_list(where, strings, res=("rc", ident), all_strings=True)
        if not rc.get("geometry"):
            R.err("render_controller", f"{where}geometry が無い")


_RES_REF = re.compile(r"(?<![\w.])(geometry|texture|material)\.([A-Za-z_][\w]*)", re.I)
_ARRAY_REF = re.compile(r"(?<![\w.])array\.([A-Za-z_]\w*)", re.I)


def rc_refs(rc):
    """レンダーコントローラが参照する Geometry.x / Texture.x / Material.x（小文字）と、未定義の Array。"""
    refs = {"geometry": set(), "texture": set(), "material": set()}
    arrays_defined = set()
    for kind, arrs in (rc.get("arrays") or {}).items():
        for aname, vals in (arrs or {}).items():
            arrays_defined.add(aname.lower())
            for v in vals or []:
                for m in _RES_REF.finditer(str(v)):
                    refs[m.group(1).lower()].add(m.group(2).lower())
    texts = [rc.get("geometry") or ""] + [str(t) for t in rc.get("textures", []) or []]
    for d in rc.get("materials", []) or []:
        texts.extend(str(v) for v in (d or {}).values())
    used_arrays = set()
    for t in texts:
        for m in _RES_REF.finditer(t):
            refs[m.group(1).lower()].add(m.group(2).lower())
        for m in _ARRAY_REF.finditer(t):
            used_arrays.add("array." + m.group(1).lower())
    return refs, used_arrays - arrays_defined


VANILLA_RC_PREFIX = "controller.render."
USERS = defaultdict(set)          # ("anim"|"ctrl"|"rc", id) -> {("entity"|"attachable", id)}


def _desc_strings(d):
    out = []
    sc = d.get("scripts") or {}
    for key in ("initialize", "pre_animation"):
        for i, s in enumerate(sc.get(key, []) or []):
            out.append((f"/scripts/{key}[{i}]", s))
    for key in ("scale", "scalex", "scaley", "scalez", "should_update_bones_and_effects_offscreen",
                "should_update_effects_offscreen", "parent_setup"):
        if isinstance(sc.get(key), str):
            out.append((f"/scripts/{key}", sc[key]))
    for i, a in enumerate(sc.get("animate", []) or []):
        if isinstance(a, dict):
            for k, cond in a.items():
                if isinstance(cond, str):
                    out.append((f"/scripts/animate/{k}", cond))
    for i, r in enumerate(d.get("render_controllers", []) or []):
        if isinstance(r, dict):
            for k, cond in r.items():
                if isinstance(cond, str):
                    out.append((f"/render_controllers/{k}", cond))
    return out


def check_client_like(kind, table):
    for ident, (d, p) in sorted(table.items()):
        where = f"{kind} {ident}: "
        me = ("entity" if kind == "client entity" else "attachable", ident)
        geos = d.get("geometry") or {}
        for k, g in geos.items():
            if g not in I.geos:
                R.err("reference", f"{where}geometry.{k} → {g} が無い")
        for k, t in (d.get("textures") or {}).items():
            if t in I.textures or t.startswith("textures/misc/enchanted"):
                continue
            if t.startswith("textures/nr/") or not t.startswith("textures/"):
                R.err("reference", f"{where}texture.{k} → {t}(.png) が無い")
            else:
                R.warn("reference", f"{where}texture.{k} → {t} はこのパックに無い（バニラのテクスチャと見なす）")
        for k, m in (d.get("materials") or {}).items():
            base = str(m).split(":")[0]
            if base not in VANILLA_MATERIALS and base not in I.materials:
                R.warn("reference", f"{where}material.{k} → {m} は知らないマテリアル")
        anims = d.get("animations") or {}
        for k, a in anims.items():
            if a.startswith("controller.animation."):
                if a in I.ctrls:
                    USERS[("ctrl", a)].add(me)
                elif a.startswith("controller.animation.nr."):
                    R.err("reference", f"{where}animations.{k} → {a} が無い")
            else:
                if a in I.anims:
                    USERS[("anim", a)].add(me)
                elif a.startswith("animation.nr."):
                    R.err("reference", f"{where}animations.{k} → {a} が無い")
        for entry in (d.get("scripts") or {}).get("animate", []) or []:
            key = entry if isinstance(entry, str) else (list(entry)[0] if isinstance(entry, dict) and entry else None)
            if key and key not in anims:
                R.err("reference", f"{where}scripts.animate の {key} が animations に無い")
        for r in d.get("render_controllers", []) or []:
            rid = r if isinstance(r, str) else (list(r)[0] if isinstance(r, dict) and r else None)
            if not rid:
                continue
            if rid in I.rcs:
                USERS[("rc", rid)].add(me)
            elif rid.startswith("controller.render.nr."):
                R.err("reference", f"{where}render controller {rid} が無い")
            elif not rid.startswith(VANILLA_RC_PREFIX):
                R.err("reference", f"{where}render controller {rid} が無い")
        for k, pid in (d.get("particle_effects") or {}).items():
            if pid not in I.particles and pid.startswith("nr:"):
                R.err("reference", f"{where}particle_effects.{k} → {pid} が無い")
        for k, sid in (d.get("sound_effects") or {}).items():
            if sid.startswith("nr.") and sid not in I.sound_defs:
                R.err("reference", f"{where}sound_effects.{k} → {sid} が sound_definitions に無い")
        egg = d.get("spawn_egg") or {}
        if "texture" in egg and egg["texture"] not in I.item_tex:
            R.err("reference", f"{where}spawn_egg.texture {egg['texture']} が item_texture に無い")
        check_molang_list(where, _desc_strings(d), res=(me[0] + "_desc", ident), all_strings=True)
        USERS[(me[0] + "_desc", ident)].add(me)
        # テクスチャとジオメトリの寸法（同じ短名のテクスチャがあればそれと比べる。nr:gib の z_<key> / generic の
        # ように配列で組を選ぶエンティティ。無ければ最初のテクスチャと）
        texs = d.get("textures") or {}
        for k, g in geos.items():
            info = GEO_INFO.get(g)
            if not info:
                continue
            for t in ([texs[k]] if k in texs else []) + list(texs.values()):
                if t in I.tex_files:
                    tex_size_vs_geo(where, t, info)
                    break


_tex_size_cache: dict = {}


def tex_size(t):
    if t not in _tex_size_cache:
        from PIL import Image
        try:
            with Image.open(I.tex_files[t]) as im:
                _tex_size_cache[t] = (im.size, im.mode)
        except Exception as exc:  # noqa: BLE001
            R.err("texture", f"{t}: 画像として読めない — {exc}")
            _tex_size_cache[t] = ((0, 0), "?")
    return _tex_size_cache[t]


def tex_size_vs_geo(where, t, info):
    (w, h), _mode = tex_size(t)
    if not w:
        return
    tw, th = info["tw"], info["th"]
    if (w, h) != (tw, th):
        if abs(w / h - tw / th) > 1e-6:
            R.err("texture", f"{where}{t} は {w}x{h}、ジオメトリは {tw}x{th}（縦横比が違うので UV がずれる）")
        else:
            R.warn("texture", f"{where}{t} は {w}x{h}、ジオメトリは {tw}x{th}（比は同じなので表示はされる）")


def _desc_of():
    desc_of = {}
    for ident, (d, _p) in I.client.items():
        desc_of[("entity", ident)] = d
    for ident, (d, _p) in I.attach.items():
        desc_of[("attachable", ident)] = d
    return desc_of


def resolve_users():
    """コントローラの状態が使うアニメ（エンティティの短名経由）にも使い手を伝える（入れ子のコントローラも）。"""
    desc_of = _desc_of()
    changed = True
    while changed:
        changed = False
        for cid, (c, _p) in I.ctrls.items():
            users = set(USERS.get(("ctrl", cid), set()))
            names = set()
            for st in ((c or {}).get("states") or {}).values():
                for an in st.get("animations", []) or []:
                    names.add(an if isinstance(an, str) else (list(an)[0] if an else ""))
            for u in users:
                anims = desc_of[u].get("animations") or {}
                for n in names:
                    target = anims.get(n)
                    key = ("anim", target) if target in I.anims else ("ctrl", target) if target in I.ctrls else None
                    if key and u not in USERS[key]:
                        USERS[key].add(u)
                        changed = True


def check_users_detail():
    """エンティティが使うアニメ・コントローラ・レンダーコントローラの中身をエンティティと突き合わせる。"""
    desc_of = _desc_of()

    # レンダーコントローラ: Geometry/Texture/Material の参照・part_visibility のボーン
    for rid, (rc, _p) in sorted(I.rcs.items()):
        users = USERS.get(("rc", rid), set())
        refs, undefined_arrays = rc_refs(rc)
        for a in sorted(undefined_arrays):
            R.err("render_controller", f"{rid}: {a} が arrays に無い")
        if not users:
            if rid.startswith("controller.render.nr."):
                R.warn("unused", f"{rid}: どのエンティティ・アタッチャブルも使っていない")
            continue
        for kind, names in refs.items():
            dict_key = {"geometry": "geometry", "texture": "textures", "material": "materials"}[kind]
            bad = defaultdict(list)
            for u in sorted(users):
                have = lower_keys(desc_of[u].get(dict_key))
                for n in names:
                    if n not in have:
                        bad[n].append(u[1])
            for n, ents in bad.items():
                R.err("render_controller", f"{rid}: {kind.capitalize()}.{n} が {len(ents)} 体に無い"
                                           f"（{', '.join(ents[:4])}{' …' if len(ents) > 4 else ''}）")
        # part_visibility のボーン（どのジオメトリにも無ければ綴り違い）
        all_bones = set()
        for u in users:
            for g in (desc_of[u].get("geometry") or {}).values():
                all_bones |= set(GEO_INFO.get(g, {}).get("bones", {}))
        if all_bones:
            for d in rc.get("part_visibility", []) or []:
                for b in (d or {}):
                    if b != "*" and b.lower() not in all_bones and "*" not in b:
                        R.warn("render_controller", f"{rid}: part_visibility の {b} はどのジオメトリにも無い")

    # アニメーション: 動かすボーン・エフェクトの短名
    for aid, (a, _p) in sorted(I.anims.items()):
        users = USERS.get(("anim", aid), set())
        bones = set((a.get("bones") or {}))
        parts, sounds = anim_effects(a)
        if aid.startswith("animation.nr.p."):
            bad = [b for b in bones if b.lower() not in PLAYER_BONES]
            if bad:
                R.warn("animation", f"{aid}: プレイヤーに無いボーン {', '.join(sorted(bad)[:6])}")
            continue
        if not users:
            continue
        all_bones, all_locs = set(), set()
        for u in users:
            for g in (desc_of[u].get("geometry") or {}).values():
                all_bones |= set(GEO_INFO.get(g, {}).get("bones", {}))
                all_locs |= GEO_INFO.get(g, {}).get("locators", set())
        if all_bones:
            bad = sorted(b for b in bones if b.lower() not in all_bones)
            if bad:
                R.warn("animation", f"{aid}: 使うエンティティのどのジオメトリにも無いボーン {', '.join(bad[:6])}")
        _check_effects(aid, users, desc_of, parts, sounds, all_locs)

    # コントローラ: 状態の animations の短名・エフェクト
    for cid, (c, _p) in sorted(I.ctrls.items()):
        users = USERS.get(("ctrl", cid), set())
        if not users:
            if cid.startswith("controller.animation.nr."):
                R.warn("unused", f"{cid}: どのエンティティも使っていない")
            continue
        names, parts, sounds = set(), [], []
        for st in ((c or {}).get("states") or {}).values():
            for an in st.get("animations", []) or []:
                names.add(an if isinstance(an, str) else (list(an)[0] if an else ""))
            pp, ss = anim_effects(st)
            parts += pp
            sounds += ss
        all_locs = set()
        for u in users:
            for g in (desc_of[u].get("geometry") or {}).values():
                all_locs |= GEO_INFO.get(g, {}).get("locators", set())
        bad = defaultdict(list)
        for u in sorted(users):
            anims = desc_of[u].get("animations") or {}
            for n in names:
                if n and n not in anims:
                    bad[n].append(u[1])
        for n, ents in bad.items():
            R.err("controller", f"{cid}: 状態のアニメ {n} が {len(ents)} 体の animations に無い"
                                f"（{', '.join(ents[:4])}{' …' if len(ents) > 4 else ''}）")
        _check_effects(cid, users, desc_of, parts, sounds, all_locs)


def _check_effects(res, users, desc_of, parts, sounds, all_locs):
    for eff, loc in parts:
        miss = [u[1] for u in sorted(users) if eff not in (desc_of[u].get("particle_effects") or {})]
        if miss:
            R.err("reference", f"{res}: パーティクル短名 {eff} が {len(miss)} 体の particle_effects に無い"
                               f"（{', '.join(miss[:3])}）")
        if loc and all_locs and loc not in all_locs:
            R.warn("reference", f"{res}: ロケータ {loc} がジオメトリに無い")
    for eff in sounds:
        miss = [u[1] for u in sorted(users) if eff not in (desc_of[u].get("sound_effects") or {})]
        if miss:
            R.err("reference", f"{res}: 音の短名 {eff} が {len(miss)} 体の sound_effects に無い（{', '.join(miss[:3])}）")


def check_properties_in_molang():
    """Molang の q.property('x') を、そのリソースを使うエンティティの BP プロパティと突き合わせる。"""
    props_of = {}
    for ident, (ent, _p) in I.entities.items():
        props_of[ident] = (ent.get("description") or {}).get("properties") or {}
    any_props = {}
    for ident, props in props_of.items():
        for k, v in props.items():
            any_props.setdefault(k, v)
    for res, items in sorted(MOL.by_res.items()):
        users = USERS.get(res, set())
        ents = sorted(u[1] for u in users if u[0] == "entity")
        att = sorted(u[1] for u in users if u[0] == "attachable")
        resname = f"{res[1]}"
        for where, s in items:
            names, has, cmps, nums = prop_refs(s)
            if not names and not cmps and not nums:
                continue
            if att and not ents:
                R.warn("property", f"{where}: アタッチャブルの Molang で q.property（持ち主のプロパティは読めない）")
                continue
            targets = ents
            if not targets:
                # どのエンティティにも使われていない: どれかの nr エンティティに定義があればよしとする
                for n in names:
                    if n not in any_props and I.entities:
                        R.err("property", f"{where}: q.property('{n}') はどのエンティティにも無い")
                continue
            for n in sorted(names):
                miss = [e for e in targets if e in props_of and n not in props_of[e]]
                if miss:
                    R.err("property", f"{resname}: q.property('{n}') が {len(miss)} 体に無い"
                                      f"（{', '.join(miss[:4])}{' …' if len(miss) > 4 else ''}）")
                for e in targets:
                    pd = props_of.get(e, {}).get(n)
                    if pd and not pd.get("client_sync", False):
                        R.err("property", f"{resname}: {e} の {n} は client_sync でない（RP から読めない）")
                        break
            for n, op, val in cmps:
                for e in targets:
                    pd = props_of.get(e, {}).get(n)
                    if not pd:
                        continue
                    if pd.get("type") != "enum":
                        R.err("property", f"{resname}: {n} は {pd.get('type')} なのに文字列 '{val}' と比べている")
                        break
                    if val not in (pd.get("values") or []):
                        R.err("property", f"{resname}: {n} {op} '{val}' — '{val}' は {n} の値に無い "
                                          f"({', '.join(pd.get('values') or [])})")
                        break
            for n, op, num in nums:
                for e in targets:
                    pd = props_of.get(e, {}).get(n)
                    if not pd:
                        continue
                    if pd.get("type") == "enum":
                        R.err("property", f"{resname}: {n} は enum なのに数 {num:g} と比べている")
                        break
                    rng = pd.get("range")
                    if isinstance(rng, list) and len(rng) == 2 and op in ("==", "!=") and \
                            not (rng[0] <= num <= rng[1]):
                        R.warn("property", f"{resname}: {n} {op} {num:g} は範囲 {rng} の外（常に同じ結果）")
                        break


# ===========================================================================
#  RP: パーティクル・音・アトラス・blocks.json
# ===========================================================================
_PARTICLE_SKIP = ("texture", "material", "identifier", "facing_camera_mode", "mode", "event", "effect",
                  "event_name", "expression")


def check_particles():
    for ident, (pe, p) in sorted(I.particles.items()):
        where = f"particle {ident}: "
        desc = pe.get("description", {})
        brp = desc.get("basic_render_parameters", {})
        tex = brp.get("texture")
        if not tex:
            R.err("particle", f"{where}basic_render_parameters.texture が無い")
        elif tex not in I.textures and not tex.startswith("textures/particle/"):
            R.err("particle", f"{where}テクスチャ {tex} が無い")
        mat = brp.get("material", "")
        if mat and not mat.startswith("particles_"):
            R.warn("particle", f"{where}material {mat}（particles_alpha / particles_blend / particles_add …）")
        comps = pe.get("components", {}) or {}
        bb = comps.get("minecraft:particle_appearance_billboard", {}) or {}
        uv = bb.get("uv") or {}
        tw, th = uv.get("texture_width", 1), uv.get("texture_height", 1)
        if is_num(tw) and is_num(th) and tw > 0 and th > 0:
            if tex in I.tex_files:
                (w, h), _m = tex_size(tex)
                if w and abs(w / h - tw / th) > 1e-6:
                    R.err("particle", f"{where}{tex} は {w}x{h}、uv の texture_width/height は {tw}x{th}（縦横比が違う）")
            if isinstance(uv.get("uv"), list) and isinstance(uv.get("uv_size"), list) and \
                    all(is_num(x) for x in uv["uv"] + uv["uv_size"]):
                u, v = uv["uv"]
                w2, h2 = uv["uv_size"]
                if u < 0 or v < 0 or u + w2 > tw + 1e-3 or v + h2 > th + 1e-3:
                    R.err("particle", f"{where}uv [{u},{v}]+[{w2},{h2}] がアトラス {tw}x{th} の外")
            fb = uv.get("flipbook")
            if isinstance(fb, dict):
                base, size, step = fb.get("base_UV"), fb.get("size_UV"), fb.get("step_UV")
                mf = fb.get("max_frame")
                if all(isinstance(x, list) and all(is_num(y) for y in x) for x in (base, size, step)) and is_num(mf):
                    lu = base[0] + step[0] * (mf - 1) + size[0]
                    lv = base[1] + step[1] * (mf - 1) + size[1]
                    if lu > tw + 1e-3 or lv > th + 1e-3 or base[0] < 0 or base[1] < 0:
                        R.err("particle", f"{where}flipbook の最後のコマ（{mf} 枚目）がアトラス {tw}x{th} の外")
        # イベント
        for ev_name, ev in (pe.get("events") or {}).items():
            for path, s in collect_strings(ev, f"/events/{ev_name}"):
                if path.endswith("/effect") and s.startswith("nr:") and s not in I.particles:
                    R.err("particle", f"{where}イベント {ev_name} の effect {s} が無い")
                if path.endswith("/event_name") and s.startswith("nr.") and s not in I.sound_defs:
                    R.err("particle", f"{where}イベント {ev_name} の音 {s} が sound_definitions に無い")
        for path, s in collect_strings(comps, ""):
            if re.search(r"(_event|/event)(\[\d+\])?$", path) and s and s not in (pe.get("events") or {}):
                R.err("particle", f"{where}{path} のイベント {s} が events に無い")
        strings = [(path, s) for path, s in collect_strings(comps, "/components", _PARTICLE_SKIP)
                   if isinstance(s, str) and (looks_molang(s) or _OPS_HINT.search(s))]
        strings += [(f"/curves/{k}", s) for k, cv in (pe.get("curves") or {}).items()
                    for _pp, s in collect_strings(cv) if isinstance(s, str) and looks_molang(s)]
        check_molang_list(where, strings, all_strings=True)


def check_sounds():
    for sid, sdef in sorted(I.sound_defs.items()):
        where = f"sound {sid}: "
        if not isinstance(sdef, dict):
            R.err("sound", f"{where}辞書でない")
            continue
        cat = sdef.get("category")
        if cat and cat not in SOUND_CATEGORIES:
            R.warn("sound", f"{where}category {cat!r}")
        snds = sdef.get("sounds") or []
        if not snds:
            R.err("sound", f"{where}sounds が空")
        for s in snds:
            name = s.get("name") if isinstance(s, dict) else s
            if not isinstance(name, str):
                R.err("sound", f"{where}sounds の項目が不正")
                continue
            if not os.path.exists(os.path.join(RP, name + ".ogg")):
                alt = [e for e in (".wav", ".fsb") if os.path.exists(os.path.join(RP, name + e))]
                if alt:
                    R.warn("sound", f"{where}{name}{alt[0]}（.ogg にする約束）")
                else:
                    R.err("sound", f"{where}音声 {name}.ogg が無い")
    sj = load(os.path.join(RP, "sounds.json"))
    if isinstance(sj, dict):
        for path, s in collect_strings(sj):
            if s.startswith("nr.") and s not in I.sound_defs:
                R.err("sound", f"sounds.json{path}: {s} が sound_definitions に無い")
        for ent in ((sj.get("entity_sounds") or {}).get("entities") or {}):
            if ent.startswith("nr:") and ent not in I.entities:
                R.err("sound", f"sounds.json: entity_sounds の {ent} は BP に無い")


def _texture_paths(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from _texture_paths(x)
    elif isinstance(v, dict):
        if "path" in v:
            yield v["path"]
        for x in v.get("variations", []) or []:
            yield from _texture_paths(x)


def check_atlases():
    for k, v in sorted(I.item_tex.items()):
        for t in _texture_paths((v or {}).get("textures")):
            if t not in I.textures:
                R.err("atlas", f"item_texture {k}: {t} が無い")
    for k, v in sorted(I.terrain_tex.items()):
        for t in _texture_paths((v or {}).get("textures")):
            if t not in I.textures:
                R.err("atlas", f"terrain_texture {k}: {t} が無い")
    fb = load(os.path.join(RP, "textures", "flipbook_textures.json"))
    for e in fb if isinstance(fb, list) else []:
        t = e.get("flipbook_texture")
        if t and t not in I.textures:
            R.err("atlas", f"flipbook {e.get('atlas_tile')}: {t} が無い")
        if e.get("atlas_tile") not in I.terrain_tex:
            R.err("atlas", f"flipbook: atlas_tile {e.get('atlas_tile')} が terrain_texture に無い")
    bj = load(os.path.join(RP, "blocks.json"))
    for k, v in (bj or {}).items() if isinstance(bj, dict) else []:
        if k == "format_version":
            continue
        if k.startswith("nr:") and k not in I.blocks:
            R.err("atlas", f"blocks.json: {k} は BP のブロックに無い")
        tx = (v or {}).get("textures")
        for t in ([tx] if isinstance(tx, str) else list((tx or {}).values()) if isinstance(tx, dict) else []):
            if t not in I.terrain_tex:
                R.err("atlas", f"blocks.json {k}: textures {t} が terrain_texture に無い")


def check_textures():
    for t, p in sorted(I.tex_files.items()):
        (w, h), mode = tex_size(t)
        if mode in ("I;16", "I", "F", "I;16B"):
            R.err("texture", f"{t}: 画像の形式 {mode}（8bit の RGBA / RGB / P にする）")
        if max(w, h) > TEXTURE_SOFT_MAX:
            R.warn("texture", f"{t}: {w}x{h} は大きすぎる（{TEXTURE_SOFT_MAX} 以下に）")


# ===========================================================================
#  BP
# ===========================================================================
_EVENT_KEYS = ("event",)


def _event_refs(obj, path=""):
    """コンポーネントの中の {"event": 名前, "target": ...} を集める。"""
    if isinstance(obj, dict):
        ev = obj.get("event")
        if isinstance(ev, str) and obj.get("target", "self") == "self":
            yield path, ev
        for k, v in obj.items():
            yield from _event_refs(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _event_refs(v, f"{path}[{i}]")


def _walk_event(ev, groups, events, where, props, ident):
    if not isinstance(ev, dict):
        R.err("entity_event", f"{where}: 辞書でない")
        return
    for act in ("add", "remove"):
        for g in (ev.get(act) or {}).get("component_groups", []) or []:
            if g not in groups:
                R.err("entity_event", f"{where}: {act} する component_group {g} が無い")
    trig = ev.get("trigger")
    if trig is not None:
        name = trig if isinstance(trig, str) else (trig or {}).get("event")
        target = "self" if isinstance(trig, str) else (trig or {}).get("target", "self")
        if name and target == "self" and name not in events:
            R.err("entity_event", f"{where}: trigger {name} が events に無い")
    for key in ("sequence", "randomize", "first_valid"):
        for i, sub in enumerate(ev.get(key, []) or []):
            _walk_event(sub, groups, events, f"{where}/{key}[{i}]", props, ident)
    for pname, val in (ev.get("set_property") or {}).items():
        pd = props.get(pname)
        if pd is None:
            R.err("entity_event", f"{where}: set_property {pname} はこのエンティティのプロパティに無い")
            continue
        check_prop_value(f"{where}: set_property {pname}", pd, val)


def check_prop_value(where, pd, val):
    t = pd.get("type")
    if isinstance(val, str) and (looks_molang(val) or _OPS_HINT.search(val) or "'" in val):
        for sev, msg in molang_issues(val):
            (R.err if sev == "E" else R.warn)("molang", f"{where}: {msg} — {val[:80]}")
        for lit in re.findall(r"'([^']*)'", val):
            if t == "enum" and lit not in (pd.get("values") or []):
                R.err("property", f"{where}: '{lit}' は enum の値に無い")
        return
    if t == "enum":
        if val not in (pd.get("values") or []):
            R.err("property", f"{where}: {val!r} は enum の値 {pd.get('values')} に無い")
    elif t == "int":
        rng = pd.get("range") or [None, None]
        if not isinstance(val, int) or isinstance(val, bool):
            R.err("property", f"{where}: int に {val!r}")
        elif rng[0] is not None and not (rng[0] <= val <= rng[1]):
            R.err("property", f"{where}: {val} は範囲 {rng} の外")
    elif t == "float":
        rng = pd.get("range") or [None, None]
        if not is_num(val):
            R.err("property", f"{where}: float に {val!r}")
        elif rng[0] is not None and not (rng[0] <= val <= rng[1]):
            R.err("property", f"{where}: {val} は範囲 {rng} の外")
    elif t == "bool":
        if not isinstance(val, bool):
            R.err("property", f"{where}: bool に {val!r}")


_ENUM_VAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")
_PROP_NAME = re.compile(r"^[a-z0-9_]+:[a-z0-9_]+$")


def check_property_defs(ident, props, where):
    if len(props) > 32:
        R.warn("property", f"{where}: プロパティが {len(props)} 個（多すぎると同期が重い）")
    for name, pd in props.items():
        w = f"{where}: プロパティ {name}"
        if not _PROP_NAME.match(name):
            R.err("property", f"{w}: 名前は 'nr:xxx' の形（小文字・数字・_）")
        t = pd.get("type")
        if t not in ("enum", "int", "float", "bool"):
            R.err("property", f"{w}: type {t!r}")
            continue
        if t == "enum":
            vals = pd.get("values") or []
            if not vals or len(set(vals)) != len(vals):
                R.err("property", f"{w}: values が空か重複")
            for v in vals:
                if not isinstance(v, str) or not _ENUM_VAL.match(v):
                    R.err("property", f"{w}: enum の値 {v!r} は英字で始まる 32 文字以内の英数字・_")
            if len(vals) > 16:
                R.warn("property", f"{w}: enum の値が {len(vals)} 個")
        if t in ("int", "float"):
            rng = pd.get("range")
            if not (isinstance(rng, list) and len(rng) == 2 and all(is_num(x) for x in rng) and rng[0] <= rng[1]):
                R.err("property", f"{w}: range [min, max] が要る")
                continue
        if "default" in pd:
            dv = pd["default"]
            if isinstance(dv, str) and t != "enum":
                for sev, msg in molang_issues(dv):
                    (R.err if sev == "E" else R.warn)("molang", f"{w}.default: {msg}")
            else:
                check_prop_value(f"{w}.default", pd, dv)
        else:
            R.warn("property", f"{w}: default が無い")


def _expect_props(ident, props, table, where):
    for name, (t, vr, default) in table.items():
        pd = props.get(name)
        if pd is None:
            R.err("contract", f"{where}: プロパティ {name} が無い（DESIGN.md の表）")
            continue
        if pd.get("type") != t:
            R.err("contract", f"{where}: {name} は {t} のはず（{pd.get('type')}）")
            continue
        if t == "enum" and tuple(pd.get("values") or ()) != tuple(vr):
            R.err("contract", f"{where}: {name} の値 {pd.get('values')} が DESIGN.md の {list(vr)} と違う")
        if t == "int" and list(pd.get("range") or []) != list(vr):
            R.err("contract", f"{where}: {name} の範囲 {pd.get('range')} が DESIGN.md の {list(vr)} と違う")
        if default is not None and pd.get("default") != default:
            R.err("contract", f"{where}: {name} の既定 {pd.get('default')!r} が DESIGN.md の {default!r} と違う")
        if not pd.get("client_sync", False):
            R.err("contract", f"{where}: {name} は client_sync: true のはず")


def check_entities(spec):
    for ident, (ent, p) in sorted(I.entities.items()):
        where = f"entity {ident}"
        desc = ent.get("description") or {}
        groups = ent.get("component_groups") or {}
        events = ent.get("events") or {}
        props = desc.get("properties") or {}
        check_property_defs(ident, props, where)
        for ename, ev in events.items():
            _walk_event(ev, groups, events, f"{where} event {ename}", props, ident)
        for path, ev in _event_refs({"components": ent.get("components") or {}, "component_groups": groups}):
            if ev not in events and not ev.startswith("minecraft:"):
                R.err("entity_event", f"{where}{path}: event {ev} が events に無い")
        # ルートテーブル・装備
        for path, s in collect_strings({"c": ent.get("components") or {}, "g": groups}):
            if (path.endswith("/table") or path.endswith("/loot_table")) and s.endswith(".json"):
                if not os.path.exists(os.path.join(BP, s)):
                    R.err("reference", f"{where}{path}: {s} が無い")
        # 契約
        if ident.startswith("nr:z_"):
            _expect_props(ident, props, ZOMBIE_PROPS, where)
            for e in ZOMBIE_EVENTS:
                if e not in events:
                    R.err("contract", f"{where}: イベント {e} が無い（DESIGN.md §12）")
            hp = ((ent.get("components") or {}).get("minecraft:health") or {})
            if hp and (hp.get("value") != 1000 or hp.get("max") != 1000):
                R.warn("contract", f"{where}: minecraft:health は value/max 1000 のプール（§4）")
        elif ident == "nr:gib":
            _expect_props(ident, props, GIB_PROPS, where)
        if (ident.startswith(("nr:z_", "nr:proj_", "nr:prop_")) or ident == "nr:gib") and "nr:despawn" not in events:
            R.err("contract", f"{where}: イベント nr:despawn が無い")
        if ident.startswith("nr:") and ident not in I.client:
            R.err("reference", f"{where}: クライアントエンティティ（RP entity/）が無い")
    for ident in sorted(I.client):
        if ident.startswith("nr:") and ident not in I.entities:
            R.err("reference", f"client entity {ident}: BP のエンティティが無い")
    if spec is not None and getattr(spec, "ZOMBIES", None):
        completeness("zombie entity (BP)", [f"nr:z_{z['key']}" for z in spec.ZOMBIES], set(I.entities))
        completeness("zombie client entity (RP)", [f"nr:z_{z['key']}" for z in spec.ZOMBIES], set(I.client))
        if any(i.startswith("nr:z_") for i in I.entities):
            completeness("gib entity", ["nr:gib"], set(I.entities))
            if "controller.render.nr.zombie" not in I.rcs:
                R.err("contract", "controller.render.nr.zombie が無い")
        # armor の既定は種類ごと
        if hasattr(spec, "initial_armor"):
            for z in spec.ZOMBIES:
                ent = I.entities.get(f"nr:z_{z['key']}")
                if not ent:
                    continue
                pd = ((ent[0].get("description") or {}).get("properties") or {}).get("nr:armor") or {}
                want = spec.initial_armor(z)
                if pd and pd.get("default") != want:
                    R.err("contract", f"entity nr:z_{z['key']}: nr:armor の既定 {pd.get('default')} が spec の "
                                      f"initial_armor {want} と違う")


def _icon_keys(icon):
    if isinstance(icon, str):
        return [icon]
    if isinstance(icon, dict):
        if "texture" in icon:
            return [icon["texture"]]
        if isinstance(icon.get("textures"), dict):
            return list(icon["textures"].values())
    return []


def known_id(ident):
    return ident in I.items or ident in I.blocks or ident in I.entities


def check_items():
    for ident, (it, p) in sorted(I.items.items()):
        where = f"item {ident}"
        comps = it.get("components") or {}
        icon = comps.get("minecraft:icon")
        if icon is None:
            R.err("item", f"{where}: minecraft:icon が無い")
        for k in _icon_keys(icon):
            if k not in I.item_tex:
                R.err("item", f"{where}: アイコン {k} が item_texture.json に無い")
        refs = []
        bp_ = comps.get("minecraft:block_placer") or {}
        if isinstance(bp_.get("block"), str):
            refs.append(("block_placer.block", bp_["block"], "block"))
        ep = comps.get("minecraft:entity_placer") or {}
        if isinstance(ep.get("entity"), str):
            refs.append(("entity_placer.entity", ep["entity"], "entity"))
        pr = comps.get("minecraft:projectile") or {}
        if isinstance(pr.get("projectile_entity"), str):
            refs.append(("projectile.projectile_entity", pr["projectile_entity"], "entity"))
        for i, a in enumerate((comps.get("minecraft:shooter") or {}).get("ammunition", []) or []):
            if isinstance(a, dict) and isinstance(a.get("item"), str):
                refs.append((f"shooter.ammunition[{i}]", a["item"], "item"))
        for i, r in enumerate((comps.get("minecraft:repairable") or {}).get("repair_items", []) or []):
            for x in (r or {}).get("items", []) or []:
                name = x if isinstance(x, str) else (x or {}).get("name") if isinstance(x, dict) else None
                if isinstance(name, str):
                    refs.append((f"repairable.repair_items[{i}]", name, "item"))
        food = comps.get("minecraft:food") or {}
        if isinstance(food.get("using_converts_to"), str):
            refs.append(("food.using_converts_to", food["using_converts_to"], "item"))
        for path, ref, kind in refs:
            if ref.startswith("nr:"):
                ok = {"block": ref in I.blocks, "entity": ref in I.entities, "item": known_id(ref)}[kind]
                if not ok:
                    R.err("reference", f"{where}: {path} の {ref} が無い")
        if ident.startswith("nr:w_") and ident not in I.attach:
            R.err("reference", f"{where}: 武器のアタッチャブル（RP attachables/）が無い")
    for ident in sorted(I.attach):
        if ident.startswith("nr:") and ident not in I.items:
            R.err("reference", f"attachable {ident}: BP のアイテムが無い")


def check_blocks():
    for ident, (b, p) in sorted(I.blocks.items()):
        where = f"block {ident}"
        states = (b.get("description") or {}).get("states") or {}
        comp_sets = [("components", b.get("components") or {})]
        for i, perm in enumerate(b.get("permutations", []) or []):
            comp_sets.append((f"permutations[{i}]", perm.get("components") or {}))
            cond = perm.get("condition", "")
            for sev, msg in molang_issues(cond):
                (R.err if sev == "E" else R.warn)("molang", f"{where} permutations[{i}].condition: {msg}")
            for sname in re.findall(r"(?:q|query)\.block_state\s*\(\s*'([^']*)'\s*\)", cond):
                if sname not in states:
                    R.err("block", f"{where} permutations[{i}]: 状態 {sname} が description.states に無い")
        for label, comps in comp_sets:
            geo = comps.get("minecraft:geometry")
            gid = geo if isinstance(geo, str) else (geo or {}).get("identifier") if isinstance(geo, dict) else None
            if gid and not gid.startswith("minecraft:geometry.") and gid not in I.geos:
                R.err("block", f"{where} {label}: ジオメトリ {gid} が無い")
            if isinstance(geo, dict) and gid in GEO_INFO:
                for bone in (geo.get("bone_visibility") or {}):
                    if bone.lower() not in GEO_INFO[gid]["bones"]:
                        R.err("block", f"{where} {label}: bone_visibility の {bone} がジオメトリに無い")
            for face, mi in (comps.get("minecraft:material_instances") or {}).items():
                tex = (mi or {}).get("texture") if isinstance(mi, dict) else None
                if tex and tex not in I.terrain_tex:
                    R.err("block", f"{where} {label}: material_instances.{face} の {tex} が terrain_texture に無い")
            loot = comps.get("minecraft:loot")
            if isinstance(loot, str) and not os.path.exists(os.path.join(BP, loot)):
                R.err("block", f"{where} {label}: loot {loot} が無い")
            dp = comps.get("minecraft:destruction_particles") or {}
            if isinstance(dp.get("texture"), str) and dp["texture"] not in I.terrain_tex:
                R.err("block", f"{where} {label}: destruction_particles.texture {dp['texture']} が terrain_texture に無い")
            le = comps.get("minecraft:light_emission")
            if le is not None and not (isinstance(le, int) and 0 <= le <= 15):
                R.err("block", f"{where} {label}: light_emission は 0〜15 の整数")


def _recipe_refs(doc):
    out = []
    for kind, r in doc.items():
        if not kind.startswith("minecraft:recipe") or not isinstance(r, dict):
            continue
        for k, v in (r.get("key") or {}).items():
            out.append(v if isinstance(v, str) else (v or {}).get("item"))
        for v in r.get("ingredients", []) or []:
            out.append(v if isinstance(v, str) else (v or {}).get("item"))
        for key in ("result", "output", "input"):
            v = r.get(key)
            for x in (v if isinstance(v, list) else [v]):
                out.append(x if isinstance(x, str) else (x or {}).get("item") if isinstance(x, dict) else None)
        for key in ("base", "addition", "template"):
            v = r.get(key)
            out.append(v if isinstance(v, str) else (v or {}).get("item") if isinstance(v, dict) else None)
    return [x for x in out if isinstance(x, str)]


def check_recipes_loot_spawn():
    seen = {}
    for p in walk(os.path.join(BP, "recipes")):
        doc = load(p)
        if not isinstance(doc, dict):
            continue
        for kind, r in doc.items():
            if kind.startswith("minecraft:recipe") and isinstance(r, dict):
                rid = (r.get("description") or {}).get("identifier")
                if rid in seen:
                    R.err("recipe", f"{rel(p)}: レシピ ID {rid} が二重（{rel(seen[rid])}）")
                seen[rid] = p
                if not r.get("tags"):
                    R.err("recipe", f"{rel(p)}: tags が無い（crafting_table など）")
        for ref in _recipe_refs(doc):
            name = ref.split(":")[0] + ":" + ref.split(":")[1] if ref.count(":") >= 2 else ref
            if name.startswith("nr:") and not known_id(name):
                R.err("recipe", f"{rel(p)}: {name} が無い")
            if name.startswith("minecraft:") and VANILLA_ITEMS and name not in VANILLA_ITEMS \
                    and name not in VANILLA_BLOCKS:
                R.warn("recipe", f"{rel(p)}: バニラに {name} が見当たらない")
    for p in walk(os.path.join(BP, "loot_tables")):
        doc = load(p)
        for pool in (doc or {}).get("pools", []) or []:
            for e in pool.get("entries", []) or []:
                t, name = e.get("type"), e.get("name")
                if t == "item" and isinstance(name, str):
                    if name.startswith("nr:") and not known_id(name):
                        R.err("loot", f"{rel(p)}: {name} が無い")
                    if name.startswith("minecraft:") and VANILLA_ITEMS and name not in VANILLA_ITEMS \
                            and name not in VANILLA_BLOCKS:
                        R.warn("loot", f"{rel(p)}: バニラに {name} が見当たらない")
                elif t == "loot_table" and isinstance(name, str):
                    if not os.path.exists(os.path.join(BP, name)):
                        R.err("loot", f"{rel(p)}: 入れ子のルートテーブル {name} が無い")
    for p in walk(os.path.join(BP, "spawn_rules")):
        doc = load(p)
        ident = (((doc or {}).get("minecraft:spawn_rules") or {}).get("description") or {}).get("identifier")
        if not ident:
            R.err("spawn", f"{rel(p)}: description.identifier が無い")
        elif ident.startswith("nr:") and ident not in I.entities:
            R.err("spawn", f"{rel(p)}: {ident} は BP のエンティティに無い")


def check_structures():
    for sid, p in sorted(I.structures.items()):
        if sid.startswith("mystructure:"):
            continue
        try:
            st = read_mcstructure(p)
        except Exception as exc:  # noqa: BLE001
            R.err("structure", f"{rel(p)}: .mcstructure として読めない — {exc}")
            continue
        size = st["size"]
        if not (isinstance(size, list) and len(size) == 3 and all(isinstance(x, int) and x > 0 for x in size)):
            R.err("structure", f"{rel(p)}: size が不正 {size}")
            continue
        n = size[0] * size[1] * size[2]
        if len(st["indices"]) != n:
            R.err("structure", f"{rel(p)}: block_indices が {len(st['indices'])} 個（size から {n} 個のはず）")
        if st["indices"] and max(st["indices"]) >= len(st["palette"]):
            R.err("structure", f"{rel(p)}: block_indices がパレットの外を指す")
        for name in st["palette"]:
            if isinstance(name, str) and name.startswith("nr:") and name not in I.blocks:
                R.err("structure", f"{rel(p)}: パレットの {name} は BP のブロックに無い")
            if isinstance(name, str) and name.startswith("minecraft:") and VANILLA_BLOCKS and \
                    name not in VANILLA_BLOCKS:
                R.warn("structure", f"{rel(p)}: バニラに {name} が見当たらない")
        for ident in st["entities"]:
            if ident.startswith("nr:") and ident not in I.entities:
                R.err("structure", f"{rel(p)}: 中のエンティティ {ident} が BP に無い")


# ===========================================================================
#  名前・マニフェスト・スクリプト
# ===========================================================================
def check_lang():
    langs_needed = ("ja_JP", "en_US")
    for pack in (BP, RP):
        lj = load(os.path.join(pack, "texts", "languages.json"))
        if lj is None:
            R.err("lang", f"{rel(pack)}/texts/languages.json が無い")
        elif not all(c in lj for c in langs_needed):
            R.err("lang", f"{rel(pack)}/texts/languages.json に {langs_needed} が要る（{lj}）")
        for code in langs_needed:
            lang = I.lang.get((pack, code))
            if lang is None:
                R.err("lang", f"{rel(pack)}/texts/{code}.lang が無い")
                continue
            for k in ("pack.name", "pack.description"):
                if not lang.get(k):
                    R.err("lang", f"{rel(pack)}/texts/{code}.lang: {k} が無い")
    rp_langs = {code: I.lang.get((RP, code), {}) for code in langs_needed}
    missing = defaultdict(list)
    for ident in I.entities:
        if ident.startswith("nr:"):
            for code in langs_needed:
                if f"entity.{ident}.name" not in rp_langs[code]:
                    missing[code].append(f"entity.{ident}.name")
    for ident, (it, _p) in I.items.items():
        if not ident.startswith("nr:"):
            continue
        dn = ((it.get("components") or {}).get("minecraft:display_name") or {}).get("value")
        key = dn if isinstance(dn, str) and "." in dn and " " not in dn else f"item.{ident}.name"
        if isinstance(dn, str) and key != dn:
            R.warn("lang", f"item {ident}: display_name が翻訳されない文字列 {dn!r}（言語キーにする）")
            continue
        for code in langs_needed:
            if key not in rp_langs[code]:
                missing[code].append(key)
    for ident, (b, _p) in I.blocks.items():
        if not ident.startswith("nr:"):
            continue
        dn = ((b.get("components") or {}).get("minecraft:display_name"))
        key = dn if isinstance(dn, str) and "." in dn and " " not in dn else f"tile.{ident}.name"
        for code in langs_needed:
            if key not in rp_langs[code]:
                missing[code].append(key)
    for code, keys in missing.items():
        R.err("lang", f"RP {code}.lang に名前が無い {len(keys)} 件: {', '.join(sorted(keys)[:10])}"
                      f"{' …' if len(keys) > 10 else ''}")
    for ident, (d, _p) in I.client.items():
        if ident.startswith("nr:") and d.get("spawn_egg"):
            for code in langs_needed:
                if f"item.spawn_egg.entity.{ident}.name" not in rp_langs[code]:
                    R.warn("lang", f"RP {code}.lang: item.spawn_egg.entity.{ident}.name が無い")
    a, b = set(rp_langs["ja_JP"]), set(rp_langs["en_US"])
    if a ^ b:
        only = sorted(a ^ b)
        R.warn("lang", f"ja_JP と en_US で鍵が揃っていない {len(only)} 件: {', '.join(only[:8])}")


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def check_manifests():
    bm = load(os.path.join(BP, "manifest.json"))
    rm = load(os.path.join(RP, "manifest.json"))
    if not bm or not rm:
        R.err("manifest", "manifest.json が BP / RP のどちらかに無い")
        return
    uuids = [bm["header"].get("uuid"), rm["header"].get("uuid")] + \
            [m.get("uuid") for m in bm.get("modules", []) + rm.get("modules", [])]
    for u in uuids:
        if not isinstance(u, str) or not _UUID.match(u):
            R.err("manifest", f"UUID の形が不正: {u}")
    if len(set(uuids)) != len(uuids):
        R.err("manifest", "UUID が重複している")
    for m, name in ((bm, "BP"), (rm, "RP")):
        h = m["header"]
        if h.get("version") != VERSION_TUPLE:
            R.err("manifest", f"{name}: version {h.get('version')} != {VERSION_TUPLE}")
        if h.get("min_engine_version") != MIN_ENGINE:
            R.err("manifest", f"{name}: min_engine_version {h.get('min_engine_version')} != {MIN_ENGINE}")
        if m.get("format_version") != 2:
            R.err("manifest", f"{name}: format_version は 2")
    deps = {d.get("module_name") or d.get("uuid"): d.get("version") for d in bm.get("dependencies", [])}
    if rm["header"]["uuid"] not in deps:
        R.err("manifest", "BP が RP に依存していない")
    if not any(d.get("uuid") == bm["header"]["uuid"] for d in rm.get("dependencies", [])):
        R.err("manifest", "RP が BP に依存していない")
    if deps.get("@minecraft/server") != SERVER_API:
        R.err("manifest", f"@minecraft/server は {SERVER_API}（{deps.get('@minecraft/server')}）")
    if deps.get("@minecraft/server-ui") != SERVER_UI_API:
        R.err("manifest", f"@minecraft/server-ui は {SERVER_UI_API}（{deps.get('@minecraft/server-ui')}）")
    scripts = [m for m in bm.get("modules", []) if m.get("type") == "script"]
    if len(scripts) != 1:
        R.err("manifest", "BP に script モジュールが 1 つ要る")
    else:
        entry = scripts[0].get("entry", "")
        if not os.path.exists(os.path.join(BP, entry)):
            if STRICT:
                R.err("manifest", f"script のエントリ {entry} が無い")
            else:
                R.note(f"script のエントリ {entry} がまだ無い（手書き JS 待ち）")
    for pack in (BP, RP):
        icon = os.path.join(pack, "pack_icon.png")
        if not os.path.exists(icon):
            R.err("manifest", f"{rel(pack)}/pack_icon.png が無い")


_IMPORT = re.compile(r"""(?:^|[;\s])(?:import|export)\s+(?:[^'"]*?\sfrom\s+)?['"]([^'"]+)['"]""", re.M)
_DYN_IMPORT = re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)""")
ALLOWED_MODULES = {"@minecraft/server", "@minecraft/server-ui", "@minecraft/common"}


def check_scripts():
    sdir = os.path.join(BP, "scripts")
    for p in walk(sdir, (".js",)):
        with open(p, encoding="utf-8") as fh:
            src = fh.read()
        for m in list(_IMPORT.finditer(src)) + list(_DYN_IMPORT.finditer(src)):
            spec = m.group(1)
            if spec.startswith("."):
                target = os.path.normpath(os.path.join(os.path.dirname(p), spec))
                if not os.path.exists(target):
                    R.err("script", f"{rel(p)}: import '{spec}' が無い")
                elif not spec.endswith(".js"):
                    R.err("script", f"{rel(p)}: import '{spec}' は拡張子 .js まで書く")
            elif spec not in ALLOWED_MODULES:
                R.err("script", f"{rel(p)}: import '{spec}'（ゲームにあるのは {', '.join(sorted(ALLOWED_MODULES))} だけ）")


def data_js(name):
    """scripts/data/<name>.js の export const X = <JSON>; を読む（無ければ None）。"""
    p = os.path.join(BP, "scripts", "data", f"{name}.js")
    if not os.path.exists(p):
        return None
    out = {}
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^export const (\w+) = (.*);\s*$", line)
            if m:
                try:
                    out[m.group(1)] = json.loads(m.group(2))
                except ValueError:
                    pass
    return out


def check_registry(spec):
    """演出 ID の登録簿・spec が要る ID が RP に全部あるか（作る側の約束）。"""
    try:
        import nr_registry as reg
    except Exception as exc:  # noqa: BLE001
        R.note(f"nr_registry を読めなかった（{type(exc).__name__}）")
        return
    completeness("particles (nr_registry)", [f"nr:{n}" for n in reg.PARTICLES], set(I.particles))
    completeness("sounds (nr_registry)", reg.all_sound_ids(spec), set(I.sound_defs))
    completeness("player animations (nr_registry)", [f"animation.nr.p.{n}" for n in reg.PLAYER_ANIMS], set(I.anims))
    completeness("zombie one-shot animations (nr_registry)",
                 [f"animation.nr.z.{n}" for n in reg.all_zombie_oneshots(spec)], set(I.anims))
    if spec is not None:
        if hasattr(spec, "required_particles"):
            completeness("particles (spec)", spec.required_particles(), set(I.particles))
        if hasattr(spec, "required_sounds"):
            completeness("sounds (spec)", spec.required_sounds(), set(I.sound_defs))
        if hasattr(spec, "required_player_animations"):
            completeness("player animations (spec)", spec.required_player_animations(), set(I.anims))
        if hasattr(spec, "zombie_animations") and getattr(spec, "ZOMBIES", None):
            need = sorted({a for z in spec.ZOMBIES for a in spec.zombie_animations(z).values()})
            completeness("zombie animations (spec)", need, set(I.anims))
    st = data_js("structures")
    if st and isinstance(st.get("STRUCTURES"), dict):
        for key, s in st["STRUCTURES"].items():
            sid = (s or {}).get("id")
            if sid and sid not in I.structures:
                R.err("structure", f"scripts/data/structures.js: {key} の {sid} が BP structures/ に無い")


def check_limits(spec):
    zclass = {}
    if spec is not None:
        for z in getattr(spec, "ZOMBIES", []):
            zclass[z["key"]] = z.get("cls")
        info = getattr(spec, "CLASS_INFO", None)
        if info:
            for cls, d in info.items():
                if cls in CLASS_LIMITS and (d.get("cubes"), d.get("tex")) != CLASS_LIMITS[cls]:
                    R.warn("limits", f"spec の CLASS_INFO[{cls}] の上限 {d.get('cubes')}/{d.get('tex')} が "
                                     f"DESIGN.md §11 の {CLASS_LIMITS[cls]} と違う")
    geo_limit = {}
    for gid, info in GEO_INFO.items():
        lim = None
        if gid.startswith("geometry.nr.z."):
            key = gid.split(".", 3)[3]
            cls = zclass.get(key)
            lim = CLASS_LIMITS.get(cls) if cls else (CLASS_LIMITS["boss"] if not zclass else None)
            if cls is None and zclass:
                R.warn("limits", f"{gid}: spec に {key} が無い（区分が分からない）")
                lim = CLASS_LIMITS["boss"]
        elif gid.startswith("geometry.nr.w."):
            lim = WEAPON_LIMIT
        elif gid.startswith("geometry.nr.prop."):
            lim = PROP_LIMIT
        if lim:
            geo_limit[gid] = lim
            if info["cubes"] > lim[0]:
                R.err("limits", f"{gid}: キューブ {info['cubes']} 個（上限 {lim[0]}）")
            if max(info["tw"], info["th"]) > lim[1]:
                R.err("limits", f"{gid}: テクスチャ {info['tw']}x{info['th']}（上限 {lim[1]}）")
    for table in (I.client, I.attach):
        for ident, (d, _p) in table.items():
            lims = [geo_limit[g] for g in (d.get("geometry") or {}).values() if g in geo_limit]
            if not lims:
                continue
            side = max(x[1] for x in lims)
            for t in (d.get("textures") or {}).values():
                if t in I.tex_files:
                    (w, h), _m = tex_size(t)
                    if max(w, h) > side:
                        R.err("limits", f"{ident}: テクスチャ {t} が {w}x{h}（上限 {side}）")
    total = (I.bp_size + I.rp_size) / 1024 / 1024
    if total > PACK_LIMIT_MB:
        R.err("limits", f"パック全体 {total:.1f} MB（上限 {PACK_LIMIT_MB:.0f} MB）")
    elif total > PACK_LIMIT_MB * 0.8:
        R.warn("limits", f"パック全体 {total:.1f} MB（上限 {PACK_LIMIT_MB:.0f} MB の 8 割を超えた）")


# ===========================================================================
VANILLA_ITEMS: set = set()
VANILLA_BLOCKS: set = set()


def load_vanilla():
    for name, target in (("vanilla_items.txt", VANILLA_ITEMS), ("vanilla_blocks.txt", VANILLA_BLOCKS)):
        p = os.path.join(RESEARCH, "catalog", name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if ln:
                        target.add(ln if ":" in ln else "minecraft:" + ln)


def load_spec():
    if not os.path.exists(os.path.join(HERE, "nr_spec.py")):
        R.note("nr_spec.py がまだ無い（区分ごとの上限・50 体の揃い・spec の ID は調べない）")
        return None
    try:
        import nr_spec
        return nr_spec
    except Exception as exc:  # noqa: BLE001
        R.err("spec", f"nr_spec.py を読めない — {type(exc).__name__}: {exc}")
        return None


def print_report(show_all: bool, limit: int = 25):
    def block(title, d):
        n = sum(len(v) for v in d.values())
        if not n:
            return
        print(f"\n  {title} ({n})")
        for cat in sorted(d, key=lambda c: -len(d[c])):
            items = d[cat]
            print(f"   [{cat}] {len(items)}")
            for m in items if show_all else items[:limit]:
                print(f"     - {m}")
            if not show_all and len(items) > limit:
                print(f"     … ほか {len(items) - limit} 件（--all で全部）")
    block("ERRORS", R.errors)
    block("WARNINGS", R.warnings)
    if R.notes:
        print("\n  NOTES")
        for n in R.notes:
            print(f"     · {n}")


def main(argv=None) -> int:
    global STRICT
    ap = argparse.ArgumentParser(description="NIGHT RUNNER のパックの静的検証")
    ap.add_argument("--strict", action="store_true", help="分類ごと欠けていても失敗にする（最終・CI 用）")
    ap.add_argument("--all", action="store_true", help="全件を出す")
    ap.add_argument("--json", metavar="PATH", help="全件を JSON に書く")
    args = ap.parse_args(argv)
    STRICT = args.strict

    if not os.path.isdir(BP) and not os.path.isdir(RP):
        msg = f"{rel(BP)} / {rel(RP)} がまだ無い（生成前）"
        if STRICT:
            print(f"  ERROR validate: {msg}")
            return 1
        print(f"  validate: {msg} — 何もしない（OK）")
        return 0
    load_vanilla()
    load_all()
    spec = load_spec()
    index_rp()
    index_bp()
    steps = [check_geometries, lambda: check_rig_contract(spec), check_animations,
             lambda: check_client_like("client entity", I.client),
             lambda: check_client_like("attachable", I.attach), resolve_users, check_users_detail,
             check_properties_in_molang,
             check_particles, check_sounds, check_atlases, check_textures, lambda: check_entities(spec),
             check_items, check_blocks, check_recipes_loot_spawn, check_structures, check_lang, check_manifests,
             check_scripts, lambda: check_registry(spec), lambda: check_limits(spec)]
    for fn in steps:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — 検証器の不具合で全体を止めない
            import traceback
            R.err("validator", f"{getattr(fn, '__name__', 'step')}: 検証器の中で例外 {type(exc).__name__}: {exc} "
                               f"@ {traceback.extract_tb(exc.__traceback__)[-1].lineno}")
    zg = sum(1 for g in I.geos if g.startswith("geometry.nr.z."))
    size_mb = (I.bp_size + I.rp_size) / 1024 / 1024
    print(f"  validate_nr: {len(DOCS)} JSON / {len(I.tex_files)} textures / {size_mb:.1f} MB"
          f"{' / STRICT' if STRICT else ''}")
    print(f"    geometries {len(I.geos)} (zombie {zg}) · animations {len(I.anims)} · controllers {len(I.ctrls)} · "
          f"render controllers {len(I.rcs)} · particles {len(I.particles)} · sounds {len(I.sound_defs)} · "
          f"client entities {len(I.client)} · attachables {len(I.attach)}")
    print(f"    BP: entities {len(I.entities)} · items {len(I.items)} · blocks {len(I.blocks)} · "
          f"structures {len(set(I.structures.values()))} · lang keys {len(I.lang.get((RP, 'ja_JP'), {}))}")
    print_report(args.all)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"errors": R.errors, "warnings": R.warnings, "notes": R.notes}, fh, ensure_ascii=False,
                      indent=1)
    print(f"\n  validate_nr: {R.n_err} error(s), {R.n_warn} warning(s)")
    return 1 if R.n_err else 0


if __name__ == "__main__":
    sys.exit(main())
