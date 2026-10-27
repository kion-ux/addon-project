# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — エンティティの定義（BP）とクライアントエンティティ（RP）。

DESIGN.md §1 の `gen_nr_entities.py`。約束事は DESIGN.md §2（ID）・§3（ボーン・プロパティ）・§4（本当の体力）・
§5（gib と物理）・§12（BP のイベント）・§13（描画）、根拠は reference/content.md §1・§2・§5 と
reference/rendering.md §2〜§4・§11。

■ 書くもの（このファイルが持ち主。走るたびに下のフォルダ・ファイルを消してから書き直す）

| 書くもの | 場所 |
|---|---|
| ゾンビ 50 体（`nr:z_<key>`。format 1.21.120） | BP `entities/zombies/<key>.json` |
| ちぎれた部位 `nr:gib` | BP `entities/gib.json` |
| 飛び道具 `nr:proj_<key>`（spec の `ALL_PROJECTILES` = プレイヤー側 + ゾンビ側） | BP `entities/projectiles/<key>.json` |
| 自然スポーン（spec の `spawn.where` が `structure` でない種類） | BP `spawn_rules/nr_z_<key>.json` |
| クライアントエンティティ（ゾンビ・gib・飛び道具） | RP `entity/zombies/<key>.entity.json`、`entity/gib.entity.json`、`entity/projectiles/<key>.entity.json` |
| レンダーコントローラ `controller.render.nr.zombie` / `.zombie_cloak` / `.gib` / `.proj` | RP `render_controllers/nr_entities.render_controllers.json` |
| 飛び道具のモデル・テクスチャ（`nr_proj_models.py` が作る） | RP `models/entity/projectiles/<key>.geo.json`（`geometry.nr.proj.<key>`）、`textures/nr/proj/<key>.png` |
| 飛び道具の向き・回転・軌跡のアニメ | RP `animations/nr_proj.animation.json`（`animation.nr.proj.*`）、`animation_controllers/nr_proj.animation_controllers.json` |
| 透明化（shadow_cloak）用の「目だけ」テクスチャ（ゾンビのテクスチャから作る。元が無ければ作らない） | RP `textures/nr/zombies_fx/<key>_cloak.png` |
| 名前（`entity.<id>.name`・`item.spawn_egg.entity.<id>.name`） | `.frag/lang/gen_nr_entities.json` |
| 確認用のコンタクトシート（飛び道具のモデル） | `build_preview/nightrunner/entities/projectiles.png` |

小道具 `nr:prop_*` のエンティティは、まだ `gen_nr_props`（モデル）が無いので書かない（下の「残り」）。

■ ゾンビ（content.md §1.5 の形。数値は spec から）
* 基本 `components` には状態で変わらないものだけ: `type_family`（`nr_zombie` `zombie` `undead` `monster` `mob` `nr_<区分>`）、
  体力のプール `minecraft:health {1000, 1000}`（本当の体力はスクリプトの `nr:hp`。§4）、`physics`、押せる体、呼吸、名前、
  `despawn`、帯域。**`runtime_identifier` は付けない、昼に燃えない**（`burns_in_daylight` を書かない）。
* 切り替える値は互いに排他なグループだけに置く（content.md §1.3 の落とし穴よけ）:
  - `nr:alive` … AI・経路・攻撃・標的・押し返し耐性・仲間内のダメージ無効（ボスは `minecraft:boss` も。死ぬとバーが消える）
  - 当たり箱の 3 状態 `nr:body_stand` / `nr:crawler` / `nr:dead`（`collision_box` + `custom_hit_test`）
  - 速さの 4 状態 `nr:mobile` / `nr:mobile_crawl`（35%）/ `nr:enraged`（×1.35・追跡範囲 ×1.75）/ `nr:rooted`（0）
  - `nr:despawn`（`instant_despawn`）
* イベント（DESIGN §12 の 7 つ + 蘇生 2 つ）。順序を確実にするため `sequence: [{remove}, {add}]` の形:
  `minecraft:entity_spawned`（グループ・`nr:armor` = spec の `initial_armor(z)`・`pre_damage` の部位と這い・`nr:variant` を 0..3 の
  `randomize`）、`nr:on_death`（全部外して `nr:dead`、`nr:state = dead`）、`nr:to_crawl`、`nr:root_start` / `nr:root_end`、
  `nr:enrage` / `nr:calm`、`nr:despawn`、`nr:revive` / `nr:revive_crawl`（死体を蘇らせる。蘇生者の reanimate 用。
  `nr:state` を normal / crawl に戻す）。
  **同じ tick に続けて呼んだイベントのフィルタは前のイベントの set_property を見ない**（DOC の文言）ので、蘇らせて這わせる時は
  `nr:revive` → `nr:to_crawl` ではなく `nr:revive_crawl` を一つ呼ぶ。
* 経路: `navigation.walk`（`can_walk` `can_pass_doors` `can_break_doors` `is_amphibious`、水を避ける（溺死体だけ避けない）、
  夜の捕食者は `avoid_sun`、罠は避けない `avoid_damage_blocks: false`）+ `annotation.break_door`（一般・俊敏型は hard だけ）。
  **`can_path_over_damage_blocks` は 1.21.120 に無いキー**（content.md §1.4.1）なので書かない。ドアを「開ける」
  （`can_open_doors` + `annotation.open_door`）はゾンビに付けない（同上。壊して入る）。這う個体は `can_jump: false`。
  壁登りは `zombies/ai.js` が受け持つ（`navigation.climb` で壁を登れるかは UNVERIFIED のため使わない。U7）。
* 攻撃: `minecraft:attack {damage: spec の damage}`（近接の攻撃を一つも持たない種類 — 自爆の ticker・唾と吐瀉の spewer — は 1。
  近づくための押し合いだけで、本当の攻撃はスクリプトの能力）+ `behavior.melee_box_attack`（届く範囲は種類の近接攻撃の range
  から、間隔は主攻撃の windup + active + recover）。飛びかかる種類（攻撃 pounce・能力 pounce_pin / long_leap）は
  `behavior.leap_at_target`。酸の唾・瓦礫投げなどの遠距離攻撃はスクリプト（abilities.js）が溜め・アニメ付きで撃つので
  BP の `ranged_attack` / `shooter` は付けない（二重に撃たないため）。重い種類（heavy_body・ボス）は `break_blocks` で
  ガラスと葉を割りながら進む。
* 標的: プレイヤー・村人・行商人・ゴーレム（`nearest_attackable_target`、範囲は spec の aggro = `follow_range`）。
  殴られたら `hurt_by_target`（ゾンビ同士は除く）。
* 当たり箱は spec の `zombie_collision(z)`。近接と弾の当たり判定（`custom_hit_test`）は少し大きめ（pivot の x/z は 0。U3）。

■ gib（content.md §1.6 の形）: DESIGN §5 の 6 プロパティ、`physics`（埋まったら押し出す）・小さな当たり箱・押せる・
  全ダメージ無効の `damage_sensor`（殴れば entityHitEntity が来る）・押し返し耐性 0・`nr:despawn`。

■ 飛び道具（content.md §2.2 の形。spec の speed / gravity / hitbox / on_hit / lifetime_ticks）
* `minecraft:projectile` は power = speed・gravity = spec・`anchor` 1・`offset` [0, -0.1, 0]。当たりのダメージ
  （`impact_damage`）はスクリプトが entityHurt で読み直す（gore.js は飛び道具の ID → 武器で dtype を決める）ので、
  プレイヤーの弾は武器の damage、ゾンビの弾は能力の dmg を入れる（投げ物は 1）。
* **エンジンには消させない**: `remove_on_hit` を付けず `destroy_on_hit: false`（消えた後の弾は typeId を読めるか
  UNVERIFIED = U10 なので、当たった後の処理 — 刺さる・割れる・燃える・弾む・酸だまり — をしたスクリプトが
  `triggerEvent("nr:despawn")` で消す）。刺さる弾（stick）と弾む弾（bounce）は `stick_in_ground`（矢・トライデントと同じく
  `should_bounce: true` も）、割れる弾（shatter）は地面で止まる。保険に `minecraft:timer` が spec の寿命 + 2 秒で `nr:despawn`。
* 当たり箱 = spec の hitbox、`conditional_bandwidth_optimization` は snowball と同じ値、`dimension_bound`、押されない。
* 見た目: tip が -Z（武器空間と同じ）のモデルを、アニメが `q.movement_direction` から向ける（runtime_identifier が無いと
  エンジンは弾を進行方向へ向けない。wiki の記録）。体の向き（`q.body_y_rotation`、描画が根に掛ける）との差だけ回すので、
  描画が体の向きを掛けても掛けなくても（掛けない時は body_y_rotation = 0）進む向きになる。刺さる弾は止まった時の向き
  のまま、弾む・割れる弾は止まると水平に寝る。spec の spin（x_fast / x_slow / y_fast）は動いている間だけ回す。
  軌跡（spec の trail）はコントローラが動いている間（弾む弾は止まっても）`animation.nr.proj.trail` のタイムラインで出す。

■ RP
* ゾンビ: `gen_nr_zombies.zombie_assets(key)`（あれば。{geometry, texture, material, gib_geometry, visibility?}）、
  無ければ命名規則 `geometry.nr.z.<key>` / `textures/nr/zombies/<key>` / マテリアルは spec から（光る目・発光する肌
  や血・変異の glow・夜の捕食者・ボス → `entity_emissive_alpha`、他は `entity_alphatest`。rendering.md §3.3）。
  アニメ・コントローラ・pre_animation・パーティクルの短名は `gen_nr_zombie_anim` の `client_*`（無ければ大きな警告を出して
  最小限）。スポーンエッグの色は区分ごと（差し色は spec の accent）。
* `controller.render.nr.zombie`: part_visibility は `nr_rig.visibility_rules()`（祖先の条件を全部 AND。rendering.md R2）を
  50 体ぶん合わせたもの（ジオメトリが RP にあればその服・装備の子ボーンも、`zombie_assets` が visibility をくれればそれを）。
  同じ名前のボーンが種類によって違う式になったら（片方は規則なし = いつも表示、も違いに数える）、その種類だけ専用の
  `controller.render.nr.z.<key>`（服の子ボーンは付く部位ごとに名前を分けると 1 本にまとまる）。焼け（`nr:burn`）・
  感電（`nr:shock`）は `overlay_color`（R8）。透明化できる種類（shadow_cloak）は `controller.render.nr.zombie_cloak`
  （cloaked の段階の間は「目だけ」のテクスチャ）。
* gib: 50 体の `geometry.nr.gib.<key>` + `generic` と同じテクスチャを配列で持ち、`nr:ztype`（50 以上・`nr:part` > 10 は
  汎用）で選び、`nr:part` の 1 本だけ表示（R5 の折り返し対策は三項演算子で先に分ける）。アニメは `gen_nr_zombie_anim.gib_client()`。
* 飛び道具: `controller.render.nr.proj`（1 本の geometry / texture / material）。

■ スクリプトへのメモ（このファイルが前提にしていること）
* `nr:to_crawl` などのフィルタは「今の」`nr:state` を見る（set_property の値は次の tick から）。
* 自然スポーン（spawn_rules）は街の外でも湧く。設定 `natural_spawn` が切りなら、`world.afterEvents.entitySpawn` の
  `cause === "Spawned"` のゾンビに `nr:despawn` を（director.js）。
* ボスの `minecraft:boss` のバーは `minecraft:health`（1000 のプール）の割合なので、本当の体力を映すにはスクリプトが
  `health.setCurrentValue(...)`（content.md §1.4.7）。
* 飛び道具は当たってもエンジンが消さない（上）。ranged.js / throwables.js / abilities.js が処理してから `nr:despawn`。
* スクリプトで速さを変える（boss_phases・frenzy・enrage_unarmored）なら `minecraft:movement` の max は種類の速さ × 2 にしてある。

■ UNVERIFIED（実機で確かめること。content.md §10 の番号）
* U1 死体・gib に近接が当たった時の entityHitEntity / U3 custom_hit_test の pivot / U5 movement の max / U6 ボスバーの名前 /
  U7 navigation.climb / U9 projectile の anchor 等 / U10 消えた弾の typeId。
* 自作の飛び道具（runtime_identifier 無し）が `minecraft:throwable` のアイテムから「撃ち出される」か（wiki の throwable の
  手引きは snowball の runtime_identifier を勧めている）。撃ち出されなければ、アイテムの使用でスクリプトが
  `spawnEntity` + `getComponent("minecraft:projectile").shoot(...)` で投げる。
* 弾の向き: `q.movement_direction` と `q.body_y_rotation`（上の式）。弾む弾が地面で弾むか（should_bounce）。

使い方:
    python3 tools/nightrunner/gen_nr_entities.py              # 全部書く（普通は build_nr.py から）
    python3 tools/nightrunner/gen_nr_entities.py --no-models  # 飛び道具のモデル・テクスチャを描き直さない（他は全部書く）
    python3 tools/nightrunner/gen_nr_entities.py --sheet      # + 飛び道具のコンタクトシート（NR_PREVIEW=1 でも描く）
    python3 tools/nightrunner/gen_nr_entities.py --check      # 書いたファイルの自己検査だけ（書かない）
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nr_common import (BP, HERE, PREVIEW, ROOT, RP, SCRATCH, frag, load_json, write_json)  # noqa: E402
import nr_spec as S  # noqa: E402
import nr_rig as RIG  # noqa: E402

PRODUCER = "gen_nr_entities"
ENTITY_FORMAT = "1.21.120"      # content.md §0.1
SPAWN_FORMAT = "1.8.0"
CLIENT_FORMAT = "1.10.0"        # rendering.md A1
RC_FORMAT = "1.10.0"
ANIM_FORMAT = "1.8.0"
CTRL_FORMAT = "1.10.0"

# ---- 出力の置き場所（全部この生成器のもの） ----
BP_ZOMBIES = os.path.join(BP, "entities", "zombies")
BP_GIB = os.path.join(BP, "entities", "gib.json")
BP_PROJ = os.path.join(BP, "entities", "projectiles")
BP_SPAWN = os.path.join(BP, "spawn_rules")
RP_ZOMBIES = os.path.join(RP, "entity", "zombies")
RP_GIB = os.path.join(RP, "entity", "gib.entity.json")
RP_PROJ = os.path.join(RP, "entity", "projectiles")
RP_RC = os.path.join(RP, "render_controllers", "nr_entities.render_controllers.json")
RP_PROJ_ANIM = os.path.join(RP, "animations", "nr_proj.animation.json")
RP_PROJ_CTRL = os.path.join(RP, "animation_controllers", "nr_proj.animation_controllers.json")
RP_PROJ_GEO = os.path.join(RP, "models", "entity", "projectiles")
RP_PROJ_TEX = os.path.join(RP, "textures", "nr", "proj")
RP_ZFX_TEX = os.path.join(RP, "textures", "nr", "zombies_fx")
SHEET_DIR = os.path.join(SCRATCH, "entities")
OWNED = (BP_ZOMBIES, BP_GIB, BP_PROJ, BP_SPAWN, RP_ZOMBIES, RP_GIB, RP_PROJ, RP_RC, RP_PROJ_ANIM, RP_PROJ_CTRL,
         RP_ZFX_TEX)
OWNED_MODELS = (RP_PROJ_GEO, RP_PROJ_TEX)      # --no-models のときは残す

# ---- ID ----
RC_ZOMBIE = "controller.render.nr.zombie"
RC_ZOMBIE_CLOAK = "controller.render.nr.zombie_cloak"
RC_GIB = "controller.render.nr.gib"
RC_PROJ = "controller.render.nr.proj"
GIB_ID = "nr:gib"
GIB_GENERIC_GEO = "geometry.nr.gib.generic"
GIB_GENERIC_TEX_DEFAULT = "textures/nr/zombies/gib_generic"
PROJ_TRAIL_ANIM = "animation.nr.proj.trail"
PROJ_TRAIL_CTRL = "controller.animation.nr.proj.trail"

HEALTH_POOL = 1000              # DESIGN §4

# 区分ごとの値（スポーンエッグの色・密度・ドア・群れ）
CLASS_EGG = {                    # (地の色, 差し色の既定)
    "common": ("#56604a", "#7a1a14"),
    "viral": ("#3b3631", "#c8342a"),
    "special": ("#6b5f2c", "#4f8a2a"),
    "night": ("#17181f", "#e6d34c"),
    "boss": ("#2a0b0b", "#ff4a1c"),
}
CLASS_DENSITY = {"common": (4, 2), "viral": (2, 1), "special": (1, 1), "night": (2, 2), "boss": (1, 0)}
CLASS_DOOR = {"common": ("hard", 8.0), "viral": ("hard", 6.0), "special": ("normal", 5.0),
              "night": ("normal", 4.0), "boss": ("normal", 3.0)}

# 重い種類が歩きながら割るブロック（バニラにある名前だけ使う。catalog の一覧で確かめる）
BREAKABLE_BLOCKS = (
    "glass", "glass_pane", "white_stained_glass", "white_stained_glass_pane", "light_gray_stained_glass_pane",
    "oak_leaves", "spruce_leaves", "birch_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves",
    "mangrove_leaves", "cherry_leaves", "azalea_leaves", "short_grass", "tall_grass", "fern", "large_fern",
    "deadbush", "sweet_berry_bush", "vine",
)

_WARNED: List[str] = []


def warn(msg: str) -> None:
    _WARNED.append(msg)
    print(f"  ! {msg}", file=sys.stderr)


def loud_warning(lines) -> None:
    bar = "!" * 78
    print(bar, file=sys.stderr)
    for ln in lines:
        print(f"!! {ln}", file=sys.stderr)
    print(bar, file=sys.stderr)


def r3(x) -> float:
    return round(float(x), 3)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ===========================================================================
#  1. ゾンビ（BP）
# ===========================================================================
def zombie_properties(z) -> dict:
    """DESIGN §3 の 14 個（並びも表のまま）。enum は spec の PROPERTY_ENUMS、int の範囲と既定は nr_rig.PROPERTIES。
    nr:armor の既定だけは種類ごと（spec の initial_armor）。"""
    out = {}
    for name, pd in RIG.PROPERTIES.items():
        short = name.split(":", 1)[1]
        if pd["type"] == "enum":
            vals = list(S.PROPERTY_ENUMS.get(short, pd["values"]))
            if tuple(vals) != tuple(pd["values"]):
                raise ValueError(f"{name}: spec の PROPERTY_ENUMS {vals} と nr_rig.PROPERTIES {list(pd['values'])} が違う")
            out[name] = {"type": "enum", "values": vals, "default": pd["default"], "client_sync": True}
        else:
            out[name] = {"type": pd["type"], "range": list(pd["range"]), "default": pd["default"], "client_sync": True}
    out["nr:armor"]["default"] = int(S.initial_armor(z))
    return out


def _loco(z) -> dict:
    return S.LOCOMOTION_VOCAB.get(z["locomotion"], {})


def _melee_attacks(z) -> List[str]:
    """近接で届く攻撃（range 2.6 以下）。主攻撃が遠距離（唾・投擲・突進）なら副攻撃から。"""
    return [a for a in S.all_attacks(z) if float(S.ATTACK_VOCAB[a]["range"]) <= 2.6]


def melee_numbers(z) -> Tuple[float, float]:
    """(horizontal_reach, cooldown_time)。届く範囲 = 近接攻撃の range − 自分の半幅 − 相手の半幅（0.3）。"""
    w, _h = S.zombie_collision(z)
    melee = _melee_attacks(z)
    rng = max([float(S.ATTACK_VOCAB[a]["range"]) for a in melee] or [1.6])
    reach = _clamp(rng - w / 2 - 0.3, 0.6, 2.0)
    a = S.ATTACK_VOCAB[melee[0] if melee else z["attack"]]
    cd = (int(a["windup"]) + int(a["active"]) + int(a["recover"])) / 20.0
    return r3(reach), r3(_clamp(cd, 0.6, 2.5))


def body_boxes(z) -> Dict[str, dict]:
    """当たり箱の 3 状態（立つ / 這う / 死体）の collision_box と custom_hit_test。"""
    w, h = S.zombie_collision(z)
    crawl_w = r3(_clamp(max(0.8, w * 1.2), 0.8, 2.6))
    dead_w = r3(_clamp(max(0.9, w * 1.5), 0.9, 3.0))
    dead_h = r3(_clamp(w * 0.55, 0.4, 1.0))

    def hit(width, height):
        return {"hitboxes": [{"width": r3(width), "height": r3(height), "pivot": [0, r3(height / 2), 0]}]}

    return {
        "stand": {"minecraft:collision_box": {"width": r3(w), "height": r3(h)},
                  "minecraft:custom_hit_test": hit(max(w + 0.3, w * 1.5), h + 0.1)},
        "crawl": {"minecraft:collision_box": {"width": crawl_w, "height": 0.6},
                  "minecraft:custom_hit_test": hit(crawl_w + 0.3, 0.7)},
        "dead": {"minecraft:collision_box": {"width": dead_w, "height": dead_h},
                 "minecraft:custom_hit_test": hit(dead_w + 0.5, dead_h + 0.1)},
    }


def navigation(z, crawl: bool = False) -> dict:
    """navigation.walk の引数（content.md §1.4.1 の 1.21.120 のキーだけ）。"""
    nav = {
        "can_walk": True,
        "can_pass_doors": True,
        "can_break_doors": True,
        "can_open_doors": False,        # ゾンビはドアを開けない（壊す）
        "is_amphibious": True,
        "avoid_water": z["key"] != "drowned",
        "avoid_damage_blocks": False,   # 罠に突っ込む（can_path_over_damage_blocks は 1.21.120 に無い）
    }
    if z["cls"] == "night":
        nav["avoid_sun"] = True         # 夜の捕食者は昼は日向を避ける（夜は効かない）
    if crawl:
        nav["can_jump"] = False         # 這う個体は段差を越えない
    return nav


def _has_ability(z, key: str) -> bool:
    return key in S.ability_keys(z)


def _pounces(z) -> bool:
    return "pounce" in S.all_attacks(z) or _has_ability(z, "pounce_pin") or _has_ability(z, "long_leap")


def _heavy(z) -> bool:
    return z["cls"] == "boss" or _has_ability(z, "heavy_body")


_VANILLA_BLOCKS: Optional[set] = None


def breakable_blocks() -> List[str]:
    """BREAKABLE_BLOCKS のうちバニラにある名前（catalog が無ければそのまま）。"""
    global _VANILLA_BLOCKS
    if _VANILLA_BLOCKS is None:
        p = os.path.join(ROOT, "build_preview", "nr_research", "catalog", "vanilla_blocks.txt")
        _VANILLA_BLOCKS = set()
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                _VANILLA_BLOCKS = {ln.strip().replace("minecraft:", "") for ln in fh if ln.strip()}
    if not _VANILLA_BLOCKS:
        return list(BREAKABLE_BLOCKS)
    return [b for b in BREAKABLE_BLOCKS if b in _VANILLA_BLOCKS]


def speeds(z) -> Dict[str, float]:
    sp = float(z["speed"])
    return {"mobile": r3(sp), "crawl": r3(sp * 0.35), "enraged": r3(sp * 1.35), "rooted": 0.0,
            "max": r3(sp * 2.0)}


def follow(z) -> Dict[str, dict]:
    ag = int(z.get("aggro", 18))
    big = int(min(96, round(ag * 1.75)))
    mx = max(64, big)
    return {"normal": {"value": ag, "max": mx}, "enraged": {"value": big, "max": mx}}


def alive_group(z) -> dict:
    """nr:alive（生きている間だけの AI・経路・攻撃・標的）。死ぬと丸ごと外れる。"""
    loco = _loco(z)
    reach, cooldown = melee_numbers(z)
    jump = float(loco.get("jump", 1.0))
    ag = int(z.get("aggro", 18))
    keen = z["cls"] in ("night", "boss")
    g: Dict[str, dict] = {}
    g["minecraft:movement.basic"] = {}
    jp = r3(0.42 * max(1.0, math.sqrt(max(jump, 0.0))))
    g["minecraft:jump.static"] = {"jump_power": jp} if abs(jp - 0.42) > 1e-3 else {}
    g["minecraft:can_climb"] = {}
    g["minecraft:navigation.walk"] = navigation(z)
    diff, bt = CLASS_DOOR[z["cls"]]
    if _heavy(z):
        bt = min(bt, 3.0)
    g["minecraft:annotation.break_door"] = {"break_time": bt, "min_difficulty": diff}
    # 近接の攻撃を一つも持たない種類（自爆 explode・唾 spit / 吐瀉 vomit だけ）は、近づくための押し合いだけ
    # （本当の攻撃はスクリプトの能力。spec の damage は爆発・酸の値）
    g["minecraft:attack"] = {"damage": int(z["damage"]) if _melee_attacks(z) else 1}
    kb = float(z.get("knockback_resist", 0.0))
    if _has_ability(z, "heavy_body"):
        kb = max(kb, float(S.ability_params(z, "heavy_body").get("knockback_resist", 0.95)))
    g["minecraft:knockback_resistance"] = {"value": r3(_clamp(kb, 0.0, 1.0))}
    # ゾンビ同士の殴り合い・流れ弾は効かない（死ぬと nr:alive ごと外れ、nr:dead の全ダメージ無効に替わる）
    g["minecraft:damage_sensor"] = {"triggers": [
        {"on_damage": {"filters": {"test": "is_family", "subject": "other", "value": "nr_zombie"}},
         "deals_damage": "no"}]}
    g["minecraft:behavior.hurt_by_target"] = {
        "priority": 1,
        "entity_types": [{"filters": {"test": "is_family", "subject": "other", "operator": "!=",
                                      "value": "nr_zombie"}, "max_dist": max(16, ag)}]}
    g["minecraft:behavior.nearest_attackable_target"] = {
        "priority": 2,
        "must_see": True,
        "reselect_targets": True,
        "within_radius": float(ag),
        "must_see_forget_duration": 30.0 if keen else 17.0,
        "entity_types": [
            {"filters": {"any_of": [
                {"test": "is_family", "subject": "other", "value": "player"},
                {"test": "is_family", "subject": "other", "value": "irongolem"},
                {"test": "is_family", "subject": "other", "value": "snowgolem"}]},
             "max_dist": ag},
            {"filters": {"any_of": [
                {"test": "is_family", "subject": "other", "value": "villager"},
                {"test": "is_family", "subject": "other", "value": "wandering_trader"}]},
             "max_dist": ag, "must_see": False},
        ]}
    g["minecraft:behavior.melee_box_attack"] = {
        "priority": 3,
        "speed_multiplier": r3(loco.get("chase", 1.0)),
        "track_target": True,
        "horizontal_reach": reach,
        "cooldown_time": cooldown,
        "can_spread_on_fire": _has_ability(z, "ember_aura") or _has_ability(z, "fire_trail"),
    }
    if _pounces(z):
        g["minecraft:behavior.leap_at_target"] = {"priority": 4, "yd": 0.45 if z["cls"] != "boss" else 0.5,
                                                  "must_be_on_ground": False}
    g["minecraft:behavior.random_stroll"] = {"priority": 7, "speed_multiplier": r3(loco.get("walk", 0.6))}
    g["minecraft:behavior.look_at_player"] = {"priority": 8, "look_distance": 8, "probability": 0.02}
    g["minecraft:behavior.random_look_around"] = {"priority": 9}
    if _heavy(z):
        bb = breakable_blocks()
        if bb:
            g["minecraft:break_blocks"] = {"breakable_blocks": bb}
    if z["cls"] == "boss":
        g["minecraft:boss"] = {"hud_range": 64 if z["spawn"]["time"] == "night" else 55,
                               "should_darken_sky": z["spawn"]["time"] == "night"}
    return g


def speed_groups(z) -> Dict[str, dict]:
    sp = speeds(z)
    fr = follow(z)

    def mv(v):
        return {"value": v, "max": sp["max"]}

    return {
        "nr:mobile": {"minecraft:movement": mv(sp["mobile"]), "minecraft:follow_range": dict(fr["normal"])},
        "nr:mobile_crawl": {"minecraft:movement": mv(sp["crawl"]), "minecraft:follow_range": dict(fr["normal"])},
        "nr:enraged": {"minecraft:movement": mv(sp["enraged"]), "minecraft:follow_range": dict(fr["enraged"])},
        "nr:rooted": {"minecraft:movement": mv(sp["rooted"]), "minecraft:follow_range": dict(fr["normal"])},
    }


ALL_ZGROUPS = ("nr:alive", "nr:body_stand", "nr:crawler", "nr:dead", "nr:mobile", "nr:mobile_crawl", "nr:enraged",
               "nr:rooted")


def _st(op: str, value: str) -> dict:
    d = {"test": "enum_property", "subject": "self", "domain": "nr:state", "value": value}
    if op != "==":
        d["operator"] = op
    return d


NOT_DEAD = _st("!=", "dead")


def zombie_events(z) -> dict:
    pre = dict(z["gore"].get("pre_damage") or {})
    crawl0 = pre.get("state") == "crawl"
    spawn_props = {"nr:armor": int(S.initial_armor(z))}
    for k, v in pre.items():
        if k == "state":
            continue
        if k in S.PROPERTY_ENUMS and v in S.PROPERTY_ENUMS[k]:
            spawn_props[f"nr:{k}"] = v
    if crawl0:
        spawn_props["nr:state"] = "crawl"
    elif pre.get("state") in S.PROPERTY_ENUMS["state"] and pre.get("state") != "dead":
        spawn_props["nr:state"] = pre["state"]
    first = ["nr:alive", "nr:crawler", "nr:mobile_crawl"] if crawl0 else ["nr:alive", "nr:body_stand", "nr:mobile"]
    back_to_speed = [
        {"filters": _st("==", "crawl"), "add": {"component_groups": ["nr:mobile_crawl"]}},
        {"filters": _st("!=", "crawl"), "add": {"component_groups": ["nr:mobile"]}},
    ]
    return {
        "minecraft:entity_spawned": {"sequence": [
            {"add": {"component_groups": first}, "set_property": spawn_props},
            {"randomize": [{"weight": 1, "set_property": {"nr:variant": i}} for i in range(4)]},
        ]},
        "nr:on_death": {
            "filters": NOT_DEAD,
            "sequence": [
                {"remove": {"component_groups": [g for g in ALL_ZGROUPS if g != "nr:dead"]}},
                {"add": {"component_groups": ["nr:dead"]}, "set_property": {"nr:state": "dead"}},
            ]},
        "nr:to_crawl": {
            "filters": {"all_of": [NOT_DEAD, _st("!=", "crawl")]},
            "sequence": [
                {"remove": {"component_groups": ["nr:body_stand", "nr:mobile", "nr:enraged", "nr:rooted"]}},
                {"add": {"component_groups": ["nr:crawler", "nr:mobile_crawl"]}, "set_property": {"nr:state": "crawl"}},
            ]},
        "nr:root_start": {
            "filters": NOT_DEAD,
            "sequence": [
                {"remove": {"component_groups": ["nr:mobile", "nr:mobile_crawl", "nr:enraged"]}},
                {"add": {"component_groups": ["nr:rooted"]}},
            ]},
        "nr:root_end": {
            "filters": NOT_DEAD,
            "sequence": [{"remove": {"component_groups": ["nr:rooted", "nr:enraged"]}}] + back_to_speed},
        "nr:enrage": {
            "filters": {"all_of": [NOT_DEAD, _st("!=", "crawl")]},
            "sequence": [
                {"remove": {"component_groups": ["nr:mobile", "nr:rooted"]}},
                {"add": {"component_groups": ["nr:enraged"]}},
            ]},
        "nr:calm": {
            "filters": NOT_DEAD,
            "sequence": [{"remove": {"component_groups": ["nr:enraged", "nr:rooted"]}}] + back_to_speed},
        # 死体を蘇らせる（蘇生者の reanimate）。失った部位はそのまま。這わせるなら revive_crawl を一つ呼ぶ
        "nr:revive": {
            "filters": _st("==", "dead"),
            "sequence": [
                {"remove": {"component_groups": ["nr:dead"]}},
                {"add": {"component_groups": ["nr:alive", "nr:body_stand", "nr:mobile"]},
                 "set_property": {"nr:state": "normal", "nr:pose": 0}},
            ]},
        "nr:revive_crawl": {
            "filters": _st("==", "dead"),
            "sequence": [
                {"remove": {"component_groups": ["nr:dead"]}},
                {"add": {"component_groups": ["nr:alive", "nr:crawler", "nr:mobile_crawl"]},
                 "set_property": {"nr:state": "crawl", "nr:pose": 0}},
            ]},
        "nr:despawn": {"add": {"component_groups": ["nr:despawn"]}},
    }


def zombie_entity(z) -> dict:
    boxes = body_boxes(z)
    groups = {"nr:alive": alive_group(z)}
    groups["nr:body_stand"] = boxes["stand"]
    groups["nr:crawler"] = dict(boxes["crawl"])
    groups["nr:crawler"]["minecraft:navigation.walk"] = navigation(z, crawl=True)
    groups["nr:dead"] = dict(boxes["dead"])
    groups["nr:dead"]["minecraft:damage_sensor"] = {"triggers": [{"cause": "all", "deals_damage": "no"}]}
    groups.update(speed_groups(z))
    groups["nr:despawn"] = {"minecraft:instant_despawn": {}}
    comps = {
        "minecraft:type_family": {"family": ["nr_zombie", "zombie", "undead", "monster", "mob", f"nr_{z['cls']}"]},
        "minecraft:health": {"value": HEALTH_POOL, "max": HEALTH_POOL},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_air": True, "breathes_water": True},
        "minecraft:nameable": {},
        "minecraft:is_hidden_when_invisible": {},
        "minecraft:despawn": {"despawn_from_distance": {}},
        "minecraft:conditional_bandwidth_optimization": {},
    }
    return {
        "format_version": ENTITY_FORMAT,
        "minecraft:entity": {
            "description": {
                "identifier": S.zombie_id(z),
                "spawn_category": "monster",
                "is_spawnable": True,
                "is_summonable": True,
                "properties": zombie_properties(z),
            },
            "component_groups": groups,
            "components": comps,
            "events": zombie_events(z),
        },
    }


# ===========================================================================
#  2. gib（BP）
# ===========================================================================
GIB_PROPS = (("nr:ztype", 0, 63, RIG.GIB_GENERIC_ZTYPE), ("nr:part", 0, 15, 13), ("nr:spin", 0, 7, 0),
             ("nr:rest", 0, 3, 0), ("nr:bleed", 0, 1, 1), ("nr:side", 0, 1, 0))


def gib_entity() -> dict:
    props = {n: {"type": "int", "range": [lo, hi], "default": d, "client_sync": True} for n, lo, hi, d in GIB_PROPS}
    return {
        "format_version": ENTITY_FORMAT,
        "minecraft:entity": {
            "description": {"identifier": GIB_ID, "is_spawnable": False, "is_summonable": True, "properties": props},
            "component_groups": {"nr:despawn": {"minecraft:instant_despawn": {}}},
            "components": {
                "minecraft:type_family": {"family": ["nr_gib", "inanimate"]},
                # 殴れる（entityHitEntity が来る）ように体力は持たせ、ダメージは全部消す
                "minecraft:health": {"value": HEALTH_POOL, "max": HEALTH_POOL},
                "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                "minecraft:collision_box": {"width": 0.3, "height": 0.3},
                # ブロックに埋まったら近い空きへ押し出す
                "minecraft:physics": {"has_gravity": True, "has_collision": True, "push_towards_closest_space": True},
                "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
                "minecraft:knockback_resistance": {"value": 0.0},
                "minecraft:breathable": {"breathes_air": True, "breathes_water": True, "suffocate_time": 0},
                "minecraft:despawn": {"despawn_from_distance": {}},
                "minecraft:conditional_bandwidth_optimization": {
                    "default_values": {"max_optimized_distance": 60.0, "max_dropped_ticks": 2,
                                       "use_motion_prediction_hints": True}},
            },
            "events": {"nr:despawn": {"add": {"component_groups": ["nr:despawn"]}}},
        },
    }


# ===========================================================================
#  3. 飛び道具（BP）
# ===========================================================================
def proj_damage(p) -> int:
    """impact_damage の値（entityHurt を起こすため。ゾンビへの本当の値はスクリプトが武器から計算し直す）。"""
    pid = p["id"]
    for w in S.WEAPONS:
        if w.get("projectile") == pid:
            d = float(w.get("damage") or 0)
            if w.get("kind") == "throwable" and p["on_hit"] != "stick":
                return 1                          # 投げ物は当たった瞬間の打撃だけ。炎・爆発はスクリプト
            return max(1, int(round(d)))
    for z in S.ZOMBIES:                           # ゾンビの弾: 能力の dmg（無ければ種類の攻撃力 × 攻撃の倍率）
        for k in S.ability_keys(z):
            pr = S.ability_params(z, k)
            if pr.get("proj") == pid and pr.get("dmg"):
                return int(pr["dmg"])
        for a in S.all_attacks(z):
            if S.ATTACK_VOCAB[a].get("projectile") == pid:
                return max(1, int(round(float(z["damage"]) * float(S.ATTACK_VOCAB[a]["dmg_mult"]))))
    return 2


def projectile_entity(p) -> dict:
    kind = p["on_hit"]
    hb = list(p.get("hitbox") or (0.25, 0.25))
    zombie_proj = p["id"] in S.ZOMBIE_PROJECTILE_BY_ID
    on_hit = {"impact_damage": {"damage": proj_damage(p), "knockback": kind == "stick" or zombie_proj,
                                "semi_random_diff_damage": False, "destroy_on_hit": False}}
    if kind in ("stick", "bounce"):
        on_hit["stick_in_ground"] = {"shake_time": 0.35 if kind == "stick" else 0.0}
    proj = {
        "on_hit": on_hit,
        "power": r3(p["speed"]),
        "gravity": r3(p["gravity"]),
        "inertia": 0.99,
        "liquid_inertia": 0.6,
        "uncertainty_base": 6.0 if zombie_proj else 1.0,
        "uncertainty_multiplier": 2.0 if zombie_proj else 0.0,
        "anchor": 1,
        "offset": [0, -0.1, 0],
        "multiple_targets": False,
    }
    if kind in ("stick", "bounce"):
        proj["should_bounce"] = True
    life = float(p.get("lifetime_ticks") or 200) / 20.0 + 2.0
    return {
        "format_version": ENTITY_FORMAT,
        "minecraft:entity": {
            "description": {"identifier": p["id"], "is_spawnable": False, "is_summonable": True},
            "component_groups": {"nr:despawn": {"minecraft:instant_despawn": {}}},
            "components": {
                "minecraft:type_family": {"family": ["nr_projectile", "inanimate"]},
                "minecraft:collision_box": {"width": r3(hb[0]), "height": r3(hb[1])},
                "minecraft:projectile": proj,
                "minecraft:physics": {},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": True},
                "minecraft:dimension_bound": {},
                # 素手で殴って壊せないように（runtime_identifier の無い自作の弾は殴れる）
                "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                # 保険: スクリプトが消し損ねても spec の寿命 + 2 秒で消える
                "minecraft:timer": {"looping": False, "time": r3(life), "randomInterval": False,
                                    "time_down_event": {"event": "nr:despawn", "target": "self"}},
                "minecraft:conditional_bandwidth_optimization": {
                    "default_values": {"max_optimized_distance": 100.0, "max_dropped_ticks": 7,
                                       "use_motion_prediction_hints": True}},
            },
            "events": {"nr:despawn": {"add": {"component_groups": ["nr:despawn"]}}},
        },
    }


# ===========================================================================
#  4. スポーンルール（BP。content.md §5.3）
# ===========================================================================
def natural_spawner(z) -> bool:
    """spec の spawn.where が structure（建物の決まった場所だけ）でなければ自然にも湧く。"""
    return z["spawn"].get("where") != "structure"


def spawn_rule(z) -> dict:
    sp = z["spawn"]
    t = sp.get("time", "any")
    lo, hi = {"day": (8, 15), "night": (0, 7)}.get(t, (0, 15))
    gmin, gmax = (int(x) for x in sp.get("group", (1, 1)))
    surf, under = CLASS_DENSITY[z["cls"]]
    cond = {"minecraft:spawns_on_surface": {}}
    if t != "day" and under > 0:
        cond["minecraft:spawns_underground"] = {}
    cond["minecraft:brightness_filter"] = {"min": lo, "max": hi, "adjust_for_weather": True}
    cond["minecraft:difficulty_filter"] = {"min": "easy", "max": "hard"}
    cond["minecraft:weight"] = {"default": max(1, int(sp.get("weight", 1)))}
    cond["minecraft:herd"] = {"min_size": max(1, gmin), "max_size": max(1, gmin, gmax)}
    dl = {"surface": surf}
    if "minecraft:spawns_underground" in cond:
        dl["underground"] = under
    cond["minecraft:density_limit"] = dl
    cond["minecraft:distance_filter"] = {"min": 24, "max": 64}
    cond["minecraft:biome_filter"] = {"all_of": [
        {"test": "has_biome_tag", "operator": "==", "value": "monster"},
        {"test": "has_biome_tag", "operator": "==", "value": "overworld"}]}
    return {
        "format_version": SPAWN_FORMAT,
        "minecraft:spawn_rules": {
            "description": {"identifier": S.zombie_id(z), "population_control": "monster"},
            "conditions": [cond],
        },
    }


# ===========================================================================
#  5. 言語の断片
# ===========================================================================
GIB_NAME = ("ちぎれた肉片", "Severed Remains")


def lang_doc() -> dict:
    ja: Dict[str, str] = {}
    en: Dict[str, str] = {}
    for z in S.ZOMBIES:
        ident = S.zombie_id(z)
        ja[f"entity.{ident}.name"] = z["ja"]
        en[f"entity.{ident}.name"] = z["en"]
        ja[f"item.spawn_egg.entity.{ident}.name"] = f"{z['ja']}のスポーンエッグ"
        en[f"item.spawn_egg.entity.{ident}.name"] = f"Spawn {z['en']}"
    ja[f"entity.{GIB_ID}.name"], en[f"entity.{GIB_ID}.name"] = GIB_NAME
    for p in S.ALL_PROJECTILES:
        ja[f"entity.{p['id']}.name"] = p["ja"]
        en[f"entity.{p['id']}.name"] = p["en"]
    return {"ja_JP": ja, "en_US": en}


# ===========================================================================
#  6. RP の材料: ゾンビの資産・アニメの API（無ければ命名規則と最小限）
# ===========================================================================
def _import_optional(name: str):
    try:
        return __import__(name)
    except ImportError as exc:
        if getattr(exc, "name", None) == name:
            return None
        raise


_ZOO = _import_optional("gen_nr_zombies")          # ゾンビのジオメトリ・テクスチャ（まだ無いことがある）
_ANIM = _import_optional("gen_nr_zombie_anim")     # ゾンビ・gib のアニメの client_* API


def default_material(z) -> str:
    """spec から決めるマテリアル（rendering.md §3.3）。光る画素を持ち得る種類は entity_emissive_alpha。"""
    if z["cls"] in ("night", "boss"):
        return "entity_emissive_alpha"
    if S.EYES_VOCAB.get(z["eyes"], {}).get("emissive"):
        return "entity_emissive_alpha"
    if S.SKIN_VOCAB.get(z["skin"], {}).get("emissive_vein"):
        return "entity_emissive_alpha"
    if S.BLOOD_VOCAB.get(z["gore"].get("blood", "red"), {}).get("emissive"):
        return "entity_emissive_alpha"
    for item in z["mutations"]:
        if S.mutation_params(item).get("glow") or item[0] == "veins_glowing":
            return "entity_emissive_alpha"
    return "entity_alphatest"


_ASSET_CACHE: Dict[str, dict] = {}


def zombie_assets(z) -> dict:
    """{geometry, texture, material, gib_geometry, gib_texture, visibility?}。gen_nr_zombies.zombie_assets(key) が正、
    無い（まだ作られていない・キャッシュが無い）ときは命名規則（DESIGN §2）と spec のマテリアル。"""
    key = z["key"]
    if key in _ASSET_CACHE:
        return _ASSET_CACHE[key]
    d: dict = {}
    fn = getattr(_ZOO, "zombie_assets", None) if _ZOO is not None else None
    if fn is not None:
        try:
            got = fn(key)
            if isinstance(got, dict):
                d = dict(got)
        except Exception as exc:  # noqa: BLE001  キャッシュが無い等。命名規則で続ける
            warn(f"gen_nr_zombies.zombie_assets({key}) が失敗（{type(exc).__name__}: {exc}）→ 命名規則で書く")
    d.setdefault("geometry", f"geometry.nr.z.{key}")
    d.setdefault("texture", f"textures/nr/zombies/{key}")
    d.setdefault("material", default_material(z))
    d.setdefault("gib_geometry", f"geometry.nr.gib.{key}")
    d.setdefault("gib_texture", d["texture"])
    _ASSET_CACHE[key] = d
    return d


def gib_generic_assets() -> dict:
    """汎用の肉片（p_guts p_brain p_chunk p_bone p_eye）のジオメトリとテクスチャ。"""
    fn = getattr(_ZOO, "gib_generic_assets", None) if _ZOO is not None else None
    if fn is not None:
        try:
            got = fn()
            if isinstance(got, dict) and got.get("texture"):
                return {"geometry": got.get("geometry", GIB_GENERIC_GEO), "texture": got["texture"]}
        except Exception as exc:  # noqa: BLE001
            warn(f"gen_nr_zombies.gib_generic_assets() が失敗（{type(exc).__name__}）→ 命名規則で書く")
    for rel in (GIB_GENERIC_TEX_DEFAULT, "textures/nr/gibs/generic", "textures/nr/zombies/generic_gib"):
        if os.path.exists(os.path.join(RP, rel + ".png")):
            return {"geometry": GIB_GENERIC_GEO, "texture": rel}
    return {"geometry": GIB_GENERIC_GEO, "texture": GIB_GENERIC_TEX_DEFAULT}


def zoo_owned_rcs() -> List[str]:
    """gen_nr_zombies が書くレンダーコントローラ（render_controllers/nr_zombie.render_controllers.json の
    controller.render.nr.zombie・.gib ほか）の ID。ここでは書かない（二重定義になる。DESIGN §1）。無ければ空。"""
    fn = getattr(_ZOO, "owned_render_controllers", None) if _ZOO is not None else None
    if fn is None:
        return []
    try:
        return list(fn())
    except Exception as exc:  # noqa: BLE001
        warn(f"gen_nr_zombies.owned_render_controllers() が失敗（{type(exc).__name__}）→ ゾンビ・gib の RC もここで書く")
        return []


def zombie_client_parts(z) -> dict:
    """gen_nr_zombie_anim の client_* から {animations, animate, initialize, pre_animation, particle_effects, sound_effects}。"""
    if _ANIM is None:
        return {"animations": {}, "animate": [], "initialize": [], "pre_animation": [], "particle_effects": {},
                "sound_effects": {}}
    return {
        "animations": dict(_ANIM.client_animations(z)),
        "animate": list(_ANIM.client_animate(z)),
        "initialize": list(_ANIM.client_initialize(z)),
        "pre_animation": list(_ANIM.client_pre_animation(z)),
        "particle_effects": dict(_ANIM.client_particle_effects(z)),
        "sound_effects": dict(_ANIM.client_sound_effects(z) or {}),
    }


# ---- ジオメトリの走査（gen_nr_zombies が書いたボーンから part_visibility を作る） ----
_GEO_INDEX: Optional[Dict[str, dict]] = None


def geometry_index() -> Dict[str, dict]:
    """RP/models の全ジオメトリ {identifier: {"bones": [(name, parent)], "path": p}}。"""
    global _GEO_INDEX
    if _GEO_INDEX is not None:
        return _GEO_INDEX
    _GEO_INDEX = {}
    root = os.path.join(RP, "models")
    for base, _dirs, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith(".json"):
                continue
            p = os.path.join(base, f)
            try:
                doc = load_json(p)
            except Exception:  # noqa: BLE001  壊れた JSON は validate_nr が報告する
                continue
            for g in (doc.get("minecraft:geometry") or []) if isinstance(doc, dict) else []:
                ident = ((g or {}).get("description") or {}).get("identifier")
                if ident:
                    _GEO_INDEX[ident] = {"bones": [(b.get("name"), b.get("parent")) for b in g.get("bones") or []
                                                   if b.get("name")], "path": p}
    return _GEO_INDEX


def zombie_visibility(z) -> Tuple[List[Tuple[str, str]], set, str]:
    """(part_visibility の規則, その種類のボーン全部, 出どころ)。
    zombie_assets の visibility（+ bones があればそれ）> RP のジオメトリのボーン > §3 の骨格だけ。
    規則の無いボーンは「いつも表示」で、これも他の種類と合わせる時の条件になる（plan_zombie_rcs）。"""
    a = zombie_assets(z)
    if a.get("visibility"):
        rules = [(str(b), str(e)) for b, e in a["visibility"]]
        bones = set(a.get("bones") or ()) | {b for b, _e in rules}
        return rules, bones, "zombie_assets"
    info = geometry_index().get(a["geometry"])
    if info and info["bones"]:
        from mcmodel import Bone  # noqa: WPS433  （nr_common が tools/ を sys.path に入れている）
        from types import SimpleNamespace
        model = SimpleNamespace(bones=[Bone(n, (0, 0, 0), p) for n, p in info["bones"]])
        return RIG.visibility_rules(model), {n for n, _p in info["bones"]}, "geometry"
    return RIG.visibility_rules(), {n for n, _p in RIG.SKELETON}, "skeleton"


# ===========================================================================
#  7. レンダーコントローラ
# ===========================================================================
def overlay_color() -> dict:
    """焼け（nr:burn 1..3 で黒く寄せる）と感電（nr:shock で青白く明滅）。それ以外は既定のまま（this）。R8。"""
    shock = "q.property('nr:shock') > 0"
    burn = "q.property('nr:burn') > 0"
    return {
        "r": f"{shock} ? 0.62 : ({burn} ? 0.06 : this)",
        "g": f"{shock} ? 0.82 : ({burn} ? 0.05 : this)",
        "b": f"{shock} ? 1.0 : ({burn} ? 0.04 : this)",
        "a": f"{shock} ? (math.sin(q.life_time * 2400.0) > 0.0 ? 0.55 : 0.12) : "
             f"({burn} ? q.property('nr:burn') * 0.22 : this)",
    }


def zombie_rc(rules, cloak: bool = False) -> dict:
    rc = {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": ["v.nr_cloak ? Texture.cloak : Texture.default"] if cloak else ["Texture.default"],
        "part_visibility": RIG.part_visibility(rules),
        "overlay_color": overlay_color(),
    }
    return rc


class VisMerge:
    """複数の種類の part_visibility を 1 本のレンダーコントローラに合わせる。ボーン名 → 式（None = いつも表示）。
    同じ名前のボーンが種類によって違う式（片方は規則なし = いつも表示、も含む）なら合わせられない。"""

    def __init__(self):
        self.expr: Dict[str, Optional[str]] = {}
        self.order: List[str] = []

    def clash(self, rules, bones) -> List[str]:
        r = dict(rules)
        return [b for b in sorted(set(bones) | set(r)) if b in self.expr and self.expr[b] != r.get(b)]

    def add(self, rules, bones) -> None:
        r = dict(rules)
        for b, _e in list(rules) + [(b, None) for b in sorted(set(bones) - set(r))]:
            if b not in self.expr:
                self.expr[b] = r.get(b)
                self.order.append(b)

    def rules(self) -> List[Tuple[str, str]]:
        return [(b, self.expr[b]) for b in self.order if self.expr[b] is not None]


def plan_zombie_rcs(zombies) -> Tuple[List[Tuple[str, str]], Dict[str, str], Dict[str, list], Dict[str, str]]:
    """全種類の規則を一本の controller.render.nr.zombie に合わせる。同じボーンが違う式になる種類だけ専用の
    controller.render.nr.z.<key> にする。戻り値 (共有の規則, {key: rc の ID}, {専用 rc: 規則}, {key: 規則の出どころ})。"""
    shared = VisMerge()
    rc_of: Dict[str, str] = {}
    own: Dict[str, list] = {}
    src: Dict[str, str] = {}
    for z in zombies:
        rules, bones, src[z["key"]] = zombie_visibility(z)
        clash = shared.clash(rules, bones)
        if clash:
            rid = f"controller.render.nr.z.{z['key']}"
            own[rid] = rules
            rc_of[z["key"]] = rid
            warn(f"{z['key']}: ボーン {', '.join(clash[:4])} の表示の式が他の種類と違うので専用の {rid}")
            continue
        shared.add(rules, bones)
        rc_of[z["key"]] = RC_ZOMBIE
    return shared.rules(), rc_of, own, src


def gib_rc(keys: List[str]) -> dict:
    generic = f"(q.property('nr:part') > 10 || q.property('nr:ztype') >= {len(keys)})"
    idx = "q.property('nr:ztype')"
    return {
        "arrays": {
            "geometries": {"Array.geos": [f"Geometry.z_{k}" for k in keys]},
            "textures": {"Array.skins": [f"Texture.z_{k}" for k in keys]},
        },
        "geometry": f"{generic} ? Geometry.generic : Array.geos[{idx}]",
        "materials": [{"*": f"{generic} ? Material.generic : Material.default"}],
        "textures": [f"{generic} ? Texture.generic : Array.skins[{idx}]"],
        "part_visibility": RIG.part_visibility(RIG.gib_visibility_rules()),
    }


def proj_rc() -> dict:
    return {"geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            "is_hurt_color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.0}}


# ===========================================================================
#  8. クライアントエンティティ
# ===========================================================================
def _egg(z) -> dict:
    base, over = CLASS_EGG[z["cls"]]
    acc = tuple(z.get("accent") or ())
    if len(acc) == 3 and acc != (160, 30, 30):
        over = "#%02x%02x%02x" % tuple(int(_clamp(c, 0, 255)) for c in acc)
    return {"base_color": base, "overlay_color": over}


def cloak_phase(z) -> Optional[int]:
    """透明化（shadow_cloak.cloaked）の nr:ability の値。持っていなければ None。"""
    return S.ability_states(z).get("shadow_cloak.cloaked")


def zombie_client(z, rc_id: str, cloak_tex: Optional[str]) -> dict:
    a = zombie_assets(z)
    parts = zombie_client_parts(z)
    pre = list(parts["pre_animation"])
    textures = {"default": a["texture"]}
    if cloak_tex:
        textures["cloak"] = cloak_tex
        pre.append(f"v.nr_cloak = q.property('nr:ability') == {cloak_phase(z)};")
    scripts: dict = {}
    if parts["initialize"]:
        scripts["initialize"] = parts["initialize"]
    if pre:
        scripts["pre_animation"] = pre
    if parts["animate"]:
        scripts["animate"] = parts["animate"]
    scripts["should_update_effects_offscreen"] = "1.0"
    desc = {
        "identifier": S.zombie_id(z),
        "materials": {"default": a["material"]},
        "textures": textures,
        "geometry": {"default": a["geometry"]},
    }
    if parts["animations"]:
        desc["animations"] = parts["animations"]
    if parts["particle_effects"]:
        desc["particle_effects"] = parts["particle_effects"]
    if parts["sound_effects"]:
        desc["sound_effects"] = parts["sound_effects"]
    desc["scripts"] = scripts
    desc["render_controllers"] = [rc_id]
    desc["spawn_egg"] = _egg(z)
    return {"format_version": CLIENT_FORMAT, "minecraft:client_entity": {"description": desc}}


def gib_client(keys_assets: List[Tuple[str, dict]]) -> dict:
    g = gib_generic_assets()
    if _ANIM is not None:
        gc = _ANIM.gib_client()
    else:
        gc = {"animations": {}, "animate": [], "initialize": [], "pre_animation": [], "particle_effects": {}}
    materials = {"default": "entity_emissive_alpha", "generic": "entity_alphatest"}
    textures = {f"z_{k}": a["gib_texture"] for k, a in keys_assets}
    textures["generic"] = g["texture"]
    geos = {f"z_{k}": a["gib_geometry"] for k, a in keys_assets}
    geos["generic"] = g["geometry"]
    desc = {"identifier": GIB_ID, "materials": materials, "textures": textures, "geometry": geos}
    if gc.get("animations"):
        desc["animations"] = dict(gc["animations"])
    if gc.get("particle_effects"):
        desc["particle_effects"] = dict(gc["particle_effects"])
    scripts = {}
    for k in ("initialize", "pre_animation", "animate"):
        if gc.get(k):
            scripts[k] = list(gc[k])
    scripts["should_update_effects_offscreen"] = "1.0"
    desc["scripts"] = scripts
    desc["render_controllers"] = [RC_GIB]
    return {"format_version": CLIENT_FORMAT, "minecraft:client_entity": {"description": desc}}


# ---- 飛び道具 ----
SPIN_RATE = {"x_fast": 1080.0, "x_slow": 300.0, "y_fast": 1440.0}   # 度 / 秒


def proj_pre_animation(p) -> List[str]:
    """進む向き（q.movement_direction）・回転・軌跡の変数。式の向きは docstring の「飛び道具」。"""
    kind = p["on_hit"]
    rate = SPIN_RATE.get(p.get("spin") or "", 0.0)
    lines = [
        "v.nr_mv = (q.ground_speed + math.abs(q.vertical_speed)) > 0.3;",
        "t.dx = q.movement_direction(0);",
        "t.dy = q.movement_direction(1);",
        "t.dz = q.movement_direction(2);",
        "v.nr_yaw = (v.nr_mv && (t.dx * t.dx + t.dz * t.dz) > 0.0001) ? math.atan2(-t.dx, t.dz) : "
        "(v.nr_yaw ?? q.body_y_rotation);",
    ]
    if kind == "stick":
        # 刺さる弾は進む向きに傾け、止まったらその向きのまま
        lines.append("v.nr_pitch = v.nr_mv ? -math.asin(math.clamp(t.dy, -1.0, 1.0)) : (v.nr_pitch ?? 0.0);")
    else:
        lines.append("v.nr_pitch = 0.0;")
    if rate:
        lines.append(f"v.nr_spin = v.nr_mv ? math.mod((v.nr_spin ?? 0.0) + q.delta_time * {rate:g}, 360.0) : 0.0;")
    if p.get("trail"):
        lines.append("v.nr_trail = 1.0;" if kind == "bounce" else "v.nr_trail = v.nr_mv;")
    return lines


def proj_animation(p) -> dict:
    spin = p.get("spin") or ""
    root = None
    if spin.startswith("x_"):
        root = {"rotation": ["v.nr_spin", 0.0, 0.0]}
    elif spin.startswith("y_"):
        root = {"rotation": [0.0, "v.nr_spin", 0.0]}
    bones = {"body": {"rotation": ["v.nr_pitch", "q.body_y_rotation - v.nr_yaw", 0.0]}}
    if root:
        bones["root"] = root
    return {"loop": True, "bones": bones}


def proj_anim_doc() -> dict:
    anims = {f"animation.nr.proj.{p['key']}": proj_animation(p) for p in S.ALL_PROJECTILES}
    anims[PROJ_TRAIL_ANIM] = {"loop": True, "animation_length": 0.1,
                              "particle_effects": {"0.0": {"effect": "trail"}}}
    return {"format_version": ANIM_FORMAT, "animations": anims}


def proj_ctrl_doc() -> dict:
    return {"format_version": CTRL_FORMAT, "animation_controllers": {
        PROJ_TRAIL_CTRL: {
            "initial_state": "off",
            "states": {
                "off": {"transitions": [{"on": "v.nr_trail"}]},
                "on": {"animations": ["trail"], "transitions": [{"off": "!v.nr_trail"}]},
            },
        }}}


def proj_material(p, glow: Optional[bool]) -> str:
    """光る部分（炎・火花・UV・酸の芯）があれば entity_emissive_alpha。glow は描いたテクスチャから（無ければ spec の素材）。"""
    if glow is None:
        glow = any(str(m.get("mat", "")).startswith("emissive") for m in p.get("model") or [])
    return "entity_emissive_alpha" if glow else "entity_alphatest"


def proj_client(p, glow: Optional[bool]) -> dict:
    key = p["key"]
    anims = {"fly": f"animation.nr.proj.{key}"}
    animate = ["fly"]
    desc = {
        "identifier": p["id"],
        "materials": {"default": proj_material(p, glow)},
        "textures": {"default": f"textures/nr/proj/{key}"},
        "geometry": {"default": p.get("geometry") or f"geometry.nr.proj.{key}"},
    }
    if p.get("trail"):
        anims["trail"] = PROJ_TRAIL_ANIM
        anims["ctrl_trail"] = PROJ_TRAIL_CTRL
        animate.append("ctrl_trail")
        desc["particle_effects"] = {"trail": p["trail"]}
    desc["animations"] = anims
    desc["scripts"] = {"pre_animation": proj_pre_animation(p), "animate": animate}
    desc["render_controllers"] = [RC_PROJ]
    return {"format_version": CLIENT_FORMAT, "minecraft:client_entity": {"description": desc}}


# ---- 透明化の「目だけ」テクスチャ ----
def make_cloak_texture(z) -> Optional[str]:
    """ゾンビのテクスチャから発光の画素（0 < α < 255）だけを残した PNG を作る。元が無ければ None。"""
    a = zombie_assets(z)
    src = os.path.join(RP, a["texture"] + ".png")
    if not os.path.exists(src):
        return None
    import numpy as np
    from PIL import Image
    import nr_paint as NP
    im = np.asarray(Image.open(src).convert("RGBA"), np.uint8).copy()
    glow = (im[..., 3] > 0) & (im[..., 3] < 255)
    if not glow.any():
        warn(f"{z['key']}: テクスチャに発光の画素が無いので透明化の目が描けない（{a['texture']}）")
    out = np.zeros_like(im)
    out[glow] = im[glow]
    rel = f"textures/nr/zombies_fx/{z['key']}_cloak"
    NP.save_png(Image.fromarray(out, "RGBA"), os.path.join(RP, rel + ".png"), quantize=True)
    return rel


def write_rp(models: bool, sheet: bool) -> Dict[str, object]:
    info: Dict[str, object] = {}
    if _ANIM is None:
        loud_warning(["gen_nr_zombie_anim を import できない: ゾンビと gib のクライアントエンティティを",
                      "アニメ・コントローラ・pre_animation なしの最小限で書いた（動かない・切断が出ない）。",
                      "tools/nightrunner/gen_nr_zombie_anim.py を直してから build_nr.py を走らせ直すこと。"])
    if _ZOO is None:
        warn("gen_nr_zombies がまだ無い: ゾンビ・gib のジオメトリとテクスチャは命名規則の名前で参照する"
             "（geometry.nr.z.<key> / textures/nr/zombies/<key>）")
    zombies = list(S.ZOMBIES)
    shared, rc_of, own, src = plan_zombie_rcs(zombies)
    zoo_rcs = zoo_owned_rcs()
    for z in zombies if zoo_rcs else ():      # gen_nr_zombies の割り当て（同じ規則・同じ合わせ方）を使う
        rc_of[z["key"]] = zombie_assets(z).get("render_controller") or rc_of[z["key"]]
    rcs = {RC_ZOMBIE: zombie_rc(shared)}
    for rid, rules in own.items():
        rcs[rid] = zombie_rc(rules)
    # 透明化（shadow_cloak）の種類: 目だけのテクスチャが作れたら専用のコントローラ（合わせられなければ種類ごと）
    cloak = VisMerge()
    cloak_of: Dict[str, str] = {}
    for z in zombies:
        if cloak_phase(z) is None:
            continue
        rel = make_cloak_texture(z)
        if rel is None:
            warn(f"{z['key']}: ゾンビのテクスチャがまだ無いので透明化の目だけのテクスチャを作らない"
                 f"（透明化しても見た目は変わらない）")
            continue
        cloak_of[z["key"]] = rel
        rules, bones, _s = zombie_visibility(z)
        if cloak.clash(rules, bones):
            rid = f"controller.render.nr.z.{z['key']}_cloak"
            rcs[rid] = zombie_rc(rules, cloak=True)
            rc_of[z["key"]] = rid
            continue
        cloak.add(rules, bones)
        rc_of[z["key"]] = RC_ZOMBIE_CLOAK
    if any(v == RC_ZOMBIE_CLOAK for v in rc_of.values()):
        rcs[RC_ZOMBIE_CLOAK] = zombie_rc(cloak.rules(), cloak=True)
    for z in zombies:
        write_json(os.path.join(RP_ZOMBIES, f"{z['key']}.entity.json"),
                   zombie_client(z, rc_of[z["key"]], cloak_of.get(z["key"])))
    write_json(RP_GIB, gib_client([(z["key"], zombie_assets(z)) for z in zombies]))
    rcs[RC_GIB] = gib_rc([z["key"] for z in zombies])
    rcs[RC_PROJ] = proj_rc()
    # 飛び道具のモデル・テクスチャ（nr_proj_models）
    glow: Dict[str, Optional[bool]] = {p["key"]: None for p in S.ALL_PROJECTILES}
    try:
        import nr_proj_models as PM
    except ImportError as exc:
        PM = None
        warn(f"nr_proj_models を import できない（{exc}）: 飛び道具のモデルは書かない")
    if PM is not None:
        if models:
            res = PM.write_all(RP_PROJ_GEO, RP_PROJ_TEX, sheet_dir=SHEET_DIR if (sheet or PREVIEW) else None)
            info["proj_models"] = res
            for k, r in res.items():
                glow[k] = bool(r.get("glow"))
        else:
            for p in S.ALL_PROJECTILES:
                glow[p["key"]] = PM.texture_has_glow(os.path.join(RP_PROJ_TEX, f"{p['key']}.png"))
    for p in S.ALL_PROJECTILES:
        write_json(os.path.join(RP_PROJ, f"{p['key']}.entity.json"), proj_client(p, glow[p["key"]]))
    write_json(RP_PROJ_ANIM, proj_anim_doc())
    write_json(RP_PROJ_CTRL, proj_ctrl_doc())
    for rid in zoo_rcs:                      # gen_nr_zombies が書く RC は書かない（二重定義にしない）
        rcs.pop(rid, None)
    write_json(RP_RC, {"format_version": RC_FORMAT, "render_controllers": rcs})
    info["rcs"] = sorted(rcs)
    info["vis_src"] = {s: sum(1 for v in src.values() if v == s) for s in sorted(set(src.values()))}
    info["shared_rules"] = len(shared)
    info["cloak"] = sorted(cloak_of)
    return info


# ===========================================================================
#  9. 自己検査（書いたファイルを読み直して、この生成器の約束を確かめる。参照切れ一般は validate_nr）
# ===========================================================================
SWITCHED = ("minecraft:movement", "minecraft:collision_box", "minecraft:custom_hit_test", "minecraft:follow_range",
            "minecraft:navigation.walk", "minecraft:damage_sensor")
ZOMBIE_EVENTS = ("minecraft:entity_spawned", "nr:on_death", "nr:to_crawl", "nr:root_start", "nr:root_end",
                 "nr:enrage", "nr:calm", "nr:despawn", "nr:revive", "nr:revive_crawl")
BODY_GROUPS = ("nr:body_stand", "nr:crawler", "nr:dead")
SPEED_GROUPS = ("nr:mobile", "nr:mobile_crawl", "nr:enraged", "nr:rooted")


def _groups_named(ev, act: str) -> List[str]:
    out = list(((ev or {}).get(act) or {}).get("component_groups") or [])
    for k in ("sequence", "randomize"):
        for sub in (ev or {}).get(k) or []:
            out += _groups_named(sub, act)
    return out


def self_check() -> List[str]:
    errs: List[str] = []
    E = errs.append
    for z in S.ZOMBIES:
        key = z["key"]
        p = os.path.join(BP_ZOMBIES, f"{key}.json")
        if not os.path.exists(p):
            E(f"{key}: BP が無い")
            continue
        ent = load_json(p)["minecraft:entity"]
        props = ent["description"].get("properties") or {}
        if list(props) != list(RIG.PROPERTIES):
            E(f"{key}: プロパティの並び・数が DESIGN §3 と違う")
        if props.get("nr:armor", {}).get("default") != S.initial_armor(z):
            E(f"{key}: nr:armor の既定が initial_armor と違う")
        groups, comps, events = ent["component_groups"], ent["components"], ent["events"]
        for c in SWITCHED:
            if c in comps:
                E(f"{key}: 切り替えるコンポーネント {c} が基本 components にある（content.md §1.3）")
        for g in BODY_GROUPS:
            if not {"minecraft:collision_box", "minecraft:custom_hit_test"} <= set(groups.get(g, {})):
                E(f"{key}: {g} に当たり箱が無い")
        for g in SPEED_GROUPS:
            if not {"minecraft:movement", "minecraft:follow_range"} <= set(groups.get(g, {})):
                E(f"{key}: {g} に速さ・追跡範囲が無い")
        for e in ZOMBIE_EVENTS:
            if e not in events:
                E(f"{key}: イベント {e} が無い")
        for name, ev in events.items():
            for act in ("add", "remove"):
                for g in _groups_named(ev, act):
                    if g not in groups:
                        E(f"{key}: {name} の {act} {g} が component_groups に無い")
        first = _groups_named(events.get("minecraft:entity_spawned"), "add")
        if sum(g in BODY_GROUPS for g in first) != 1 or sum(g in SPEED_GROUPS for g in first) != 1:
            E(f"{key}: 出現時に当たり箱と速さのグループを一つずつ足していない（{first}）")
        if "minecraft:damage_sensor" not in groups.get("nr:dead", {}):
            E(f"{key}: nr:dead にダメージ無効の damage_sensor が無い")
        if "runtime_identifier" in ent["description"] or "minecraft:burns_in_daylight" in json_dumps(ent):
            E(f"{key}: runtime_identifier / burns_in_daylight は書かない")
        sp = os.path.join(BP_SPAWN, f"nr_z_{key}.json")
        if natural_spawner(z) != os.path.exists(sp):
            E(f"{key}: スポーンルールの有無が spec の spawn.where と合わない")
        cp = os.path.join(RP_ZOMBIES, f"{key}.entity.json")
        if not os.path.exists(cp):
            E(f"{key}: クライアントエンティティが無い")
            continue
        d = load_json(cp)["minecraft:client_entity"]["description"]
        anims = d.get("animations") or {}
        for a in (d.get("scripts") or {}).get("animate") or []:
            k = a if isinstance(a, str) else next(iter(a))
            if k not in anims:
                E(f"{key}: scripts.animate の {k} が animations に無い")
    if not os.path.exists(BP_GIB) or not os.path.exists(RP_GIB):
        E("nr:gib の BP / RP が無い")
    rcs = load_json(RP_RC)["render_controllers"] if os.path.exists(RP_RC) else {}
    zoo_rc_path = getattr(_ZOO, "RC_PATH", None) if _ZOO is not None else None
    if zoo_rc_path and os.path.exists(zoo_rc_path):      # ゾンビ・gib の RC は gen_nr_zombies のファイル
        rcs.update(load_json(zoo_rc_path)["render_controllers"])
    for rid in (RC_ZOMBIE, RC_GIB, RC_PROJ):
        if rid not in rcs:
            E(f"{rid} が無い")
    gib_vis = {next(iter(d)) for d in (rcs.get(RC_GIB) or {}).get("part_visibility", [])} - {"*"}
    if gib_vis != set(RIG.GIB_PARTS):
        E("controller.render.nr.gib の part_visibility が DESIGN §5 の p_* と違う")
    for p in S.ALL_PROJECTILES:
        key = p["key"]
        bp = os.path.join(BP_PROJ, f"{key}.json")
        cp = os.path.join(RP_PROJ, f"{key}.entity.json")
        if not (os.path.exists(bp) and os.path.exists(cp)):
            E(f"{p['id']}: BP / RP が無い")
            continue
        ent = load_json(bp)["minecraft:entity"]
        on_hit = ent["components"]["minecraft:projectile"]["on_hit"]
        if "remove_on_hit" in on_hit or on_hit.get("impact_damage", {}).get("destroy_on_hit"):
            E(f"{p['id']}: エンジンが弾を消す設定（スクリプトが nr:despawn で消す約束）")
        if "nr:despawn" not in ent["events"]:
            E(f"{p['id']}: nr:despawn が無い")
        geo = os.path.join(RP_PROJ_GEO, f"{key}.geo.json")
        png = os.path.join(RP_PROJ_TEX, f"{key}.png")
        if os.path.exists(geo) and os.path.exists(png):
            g = load_json(geo)["minecraft:geometry"][0]
            bones = {b["name"] for b in g["bones"]}
            if not {"body", "root"} <= bones:
                E(f"{p['id']}: ジオメトリに body / root が無い")
            if any(b.get("binding") for b in g["bones"]):
                E(f"{p['id']}: エンティティのジオメトリに binding がある")
            from PIL import Image
            with Image.open(png) as im:
                if im.size != (g["description"]["texture_width"], g["description"]["texture_height"]):
                    E(f"{p['id']}: テクスチャ {im.size} とジオメトリの寸法が違う")
        else:
            E(f"{p['id']}: モデルかテクスチャが無い（{os.path.relpath(geo, ROOT)}）")
    return errs


def json_dumps(o) -> str:
    import json
    return json.dumps(o)


# ===========================================================================
#  書き出し
# ===========================================================================
def _rm(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def clean(models: bool) -> None:
    for p in OWNED + (OWNED_MODELS if models else ()):
        _rm(p)


def write_bp() -> Dict[str, int]:
    n = {"zombies": 0, "projectiles": 0, "spawn_rules": 0}
    for z in S.ZOMBIES:
        write_json(os.path.join(BP_ZOMBIES, f"{z['key']}.json"), zombie_entity(z))
        n["zombies"] += 1
        if natural_spawner(z):
            write_json(os.path.join(BP_SPAWN, f"nr_z_{z['key']}.json"), spawn_rule(z))
            n["spawn_rules"] += 1
    write_json(BP_GIB, gib_entity())
    for p in S.ALL_PROJECTILES:
        write_json(os.path.join(BP_PROJ, f"{p['key']}.json"), projectile_entity(p))
        n["projectiles"] += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NIGHT RUNNER のエンティティ（BP / RP）を書く")
    ap.add_argument("--no-models", action="store_true", help="飛び道具のモデル・テクスチャを描き直さない")
    ap.add_argument("--sheet", action="store_true", help="飛び道具のコンタクトシートを描く")
    ap.add_argument("--check", action="store_true", help="書いたファイルの自己検査だけ（書かない）")
    args = ap.parse_args(argv)
    if args.check:
        errs = self_check()
        for e in errs:
            print(f"  ✗ {e}", file=sys.stderr)
        print(f"gen_nr_entities --check: {len(errs)} 件")
        return 1 if errs else 0
    models = not args.no_models
    clean(models)
    n = write_bp()
    info = write_rp(models, args.sheet)
    frag("lang", PRODUCER, lang_doc())
    print(f"gen_nr_entities: BP ゾンビ {n['zombies']} / gib 1 / 飛び道具 {n['projectiles']} / "
          f"スポーンルール {n['spawn_rules']}")
    print(f"  RP クライアント {len(S.ZOMBIES) + 1 + len(S.ALL_PROJECTILES)} / レンダーコントローラ "
          f"{', '.join(info['rcs'])}")
    print(f"  part_visibility: 共有 {info['shared_rules']} 行（出どころ {info['vis_src']}）"
          f"{' / 透明化 ' + ', '.join(info['cloak']) if info['cloak'] else ''}")
    pm = info.get("proj_models")
    if pm:
        print("  飛び道具: " + ", ".join(f"{k} {r['cubes']}c {r['tex'][0]}x{r['tex'][1]}" for k, r in pm.items()))
    errs = self_check()
    for e in errs:
        print(f"  ✗ {e}", file=sys.stderr)
    if _WARNED:
        print(f"  警告 {len(_WARNED)} 件（上）", file=sys.stderr)
    if errs:
        print(f"gen_nr_entities: 自己検査で {len(errs)} 件の誤り", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
