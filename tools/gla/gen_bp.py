# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — 挙動パック (BP) 一式 (企画書 §09 / §12 / §14 / §18)。

ここが書くのは「ワールド側の事実」だけ:

* アイテム — 何を持てて、何がクリエイティブに並ぶか
* エンティティ — 訓練用の標的2種と、演出のためだけに湧く内部表示体2種
* ルートテーブル — 訓練用の標的は何も落とさない
* レシピ — 作れるのは操作用の4つだけ。形態表示体は絶対に作らせない
* 2枚の manifest.json と pack_icon.png

技の数値・見た目・コストは一切ここに書かない。すべて spec.py から読む。
技を1つ足してもこのファイルは変わらない、という切り分けにしてある。

企画書 §14「所有者と寿命」を BP 側で担保するのがこのファイルの主目的:
内部表示体は スクリプトが死んでも自分で消える ように、必ず自前の寿命
(minecraft:timer) と即時消滅の component group を持たせる。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw                        # noqa: E402

import palette                                          # noqa: E402
import spec                                             # noqa: E402

BP = os.path.join(ROOT, spec.BP_DIR)
RP = os.path.join(ROOT, spec.RP_DIR)
NS = spec.NS

# 資産の種類ごとに format_version が違う。怪獣8号パックと同じ値に揃える。
ITEM_FMT = "1.21.20"
ENTITY_FMT = "1.21.0"
RECIPE_FMT = "1.20.10"

# 内部表示体の共通語彙。スクリプトはこの2つしか知らなくてよい。
EV_EXPIRE = f"{NS}:expire"          # 呼べば即座に消える
CG_DESPAWN = f"{NS}:despawn"

# 種族名 (family)。コロンは使えないのでアンダースコアで名前空間を作る。
# 企画書 §18「他パックとの競合」— 単語 1 つの family は必ず衝突するので接頭辞付き。
FAM_ALL = NS                        # gla のもの全部
FAM_TARGET = f"{NS}_target"         # 技の判定コードが探す的
FAM_VFX = f"{NS}_vfx"               # 演出専用。掃除のとき一括で拾う

# 食べる動作の移動制限。spec に持たせる数値ではないのでここの定数。
EAT_SLOWDOWN = 0.35


def dump(path: str, doc: dict) -> None:
    """唯一の書き出し口。Painter.save() と違いディレクトリを自分で作る。

    ensure_ascii=False は必須 — アイテム名も含めて日本語が通る前提の生成物。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# =====================================================================  ITEMS
def item(it: spec.Item) -> dict:
    """spec.Item 1件 → アイテム定義。名前も説明も lang キー経由で出す。

    企画書 §14「アイテム増殖を防ぐ構造」— hidden な形態表示体は
    (1) クリエイティブに出さない (2) 1個しか重ならない (3) レシピを持たない、
    の3点で「増える経路」を塞ぐ。ここでは (1)(2) を担保する。
    """
    desc = {"identifier": it.id}
    if it.hidden:
        # category "none" がクリエイティブ非表示の指定。group を書くと
        # タブに並んでしまうので、こちらには絶対に付けない。
        desc["menu_category"] = {"category": "none"}
    else:
        desc["menu_category"] = {"category": it.category}
        if it.group:
            desc["menu_category"]["group"] = it.group

    comps: dict = {
        "minecraft:icon": {"texture": it.icon},
        # 内部用は必ず1個。重なると「解除し忘れた表示体」が束になって残る。
        "minecraft:max_stack_size": 1 if it.hidden else it.stack,
        "minecraft:display_name": {"value": it.name_key},
        # 落としても消えない。死亡・再参加からの復旧で拾い直せること (企画書 §17 QA-11)。
        "minecraft:should_despawn": False,
    }
    if it.glint:
        comps["minecraft:glint"] = True
    if it.wearable:
        # 見た目を着せるためだけの装備。防御力を持たせると
        # 「変身すると硬くなる」という意図しない強化が混ざる。
        comps["minecraft:wearable"] = {"slot": it.wearable, "protection": 0}
        comps["minecraft:allow_off_hand"] = False
    elif not it.use_duration:
        # 手持ちの操作具。三人称で道具として持って見えるようにする。
        comps["minecraft:hand_equipped"] = True
    if it.use_duration:
        # 押しっぱなしの「食べる」動作。発動自体は itemUse の瞬間なので
        # ここで待たされることはない (怪獣8号パックの構え物と同じ形)。
        comps["minecraft:use_animation"] = "eat"
        comps["minecraft:use_modifiers"] = {
            "use_duration": it.use_duration,
            "movement_modifier": EAT_SLOWDOWN,
        }
    return {"format_version": ITEM_FMT,
            "minecraft:item": {"description": desc, "components": comps}}


def gen_items() -> int:
    out = os.path.join(BP, "items")
    for it in spec.ITEMS:
        dump(os.path.join(out, it.slug + ".item.json"), item(it))
    hidden = sum(1 for i in spec.ITEMS if i.hidden)
    print(f"  items          {len(spec.ITEMS):2d}  (うち非表示 {hidden})")
    return len(spec.ITEMS)


# ==================================================================  ENTITIES
def _hp(m: spec.Mob) -> dict:
    """体力。Bedrock の health は整数を取るので、割り切れる値は int に落とす。"""
    v = int(m.health) if float(m.health).is_integer() else m.health
    return {"value": v, "max": v}


def _families(m: spec.Mob, role: str, mob: bool) -> list:
    """種族名は spec の slug から導く。ここで技名や的の名前を再入力しない。

    `mob` を付けるかどうかが要点 — 演出用の表示体に "mob" を付けると
    他の敵の攻撃対象になり、演出が殴られて消える (企画書 §14 所有者と寿命)。
    """
    fam = [FAM_ALL, role, f"{NS}_{m.slug}"]
    return fam + ["mob"] if mob else fam


def target_entity(m: spec.Mob) -> dict:
    """訓練用の標的 (企画書 §12 訓練場)。

    測るための的なので、攻撃手段も遠くへ行く行動も持たせない。
    ノックバック耐性を上げてあるのは「同じ位置で何回当たったか」を
    数えるため — 吹き飛ぶと距離目盛りの意味がなくなる (企画書 §12)。
    """
    comps: dict = {
        "minecraft:type_family": {"family": _families(m, FAM_TARGET, True)},
        "minecraft:collision_box": {"width": m.collision[0],
                                    "height": m.collision[1]},
        "minecraft:health": _hp(m),
        "minecraft:movement": {"value": m.speed},
        # 静止する的は完全固定、群れの的も測定の邪魔にならない程度まで粘る。
        "minecraft:knockback_resistance": {"value": 1.0 if m.stationary else 0.85},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": True},
        "minecraft:nameable": {},
        # RP のアニメーションコントローラが分岐に使う既定値 (怪獣8号パックと同じ約束)。
        "minecraft:mark_variant": {"value": 0},
        # 検証用の設置物なので、離れても消えない。
        "minecraft:persistent": {},
        "minecraft:experience_reward": {"on_death": "0"},
        "minecraft:loot": {"table": f"loot_tables/entities/{m.slug}.json"},
        "minecraft:conditional_bandwidth_optimization": {},
        # 落下ダメージは測定値を汚すだけなので無効化する。
        "minecraft:damage_sensor": {
            "triggers": [
                {"cause": "fall", "damage_multiplier": 0.0, "deals_damage": False}
            ]
        },
        # 水に落ちても沈まない。コースの水際で的が消えると検証が止まる。
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.look_at_player": {"priority": 5, "look_distance": 10},
        "minecraft:behavior.random_look_around": {"priority": 6},
    }
    if m.scale != 1.0:
        comps["minecraft:scale"] = {"value": m.scale}
    if not m.stationary:
        # 群れの的だけ動く。xz_dist を小さく取り、区画の外へ出さない。
        comps["minecraft:movement.basic"] = {}
        comps["minecraft:navigation.walk"] = {"can_path_over_water": False,
                                              "avoid_water": True,
                                              "can_break_doors": False}
        comps["minecraft:jump.static"] = {}
        comps["minecraft:behavior.random_stroll"] = {
            "priority": 4, "speed_multiplier": 0.6,
            "xz_dist": 4, "y_dist": 2, "interval": 120
        }
    return {
        "format_version": ENTITY_FMT,
        "minecraft:entity": {
            "description": {
                "identifier": m.id,
                # spec.Mob.summonable は「配布してよいか＝スポーンエッグを出すか」。
                # /summon とスクリプトからの生成は is_summonable 側なので常に True。
                "is_spawnable": m.summonable,
                "is_summonable": True,
                "is_experimental": False
            },
            "components": comps,
            "events": {}
        }
    }


def vfx_entity(m: spec.Mob) -> dict:
    """内部用の表示体 (企画書 §14 所有者と寿命)。

    「捨てられても安全」が要件。スクリプトが落ちても、ワールドを離れても、
    minecraft:timer が Mob.despawn tick 後に自分で EV_EXPIRE を撃って消える。
    スクリプトは同じイベントを前倒しで叩けるので、正常系と異常系で
    消し方が分かれない。

    当たり判定も持たせない — 当たるのは技のコード側の仕事で、
    表示体が独自にダメージを出すと「見えている接触」と判定が二重になる
    (企画書 §17 QA-08 命中タイミング)。
    """
    comps: dict = {
        # "mob" を付けない。敵に狙われず、湧き数の上限にも数えられない。
        "minecraft:type_family": {"family": _families(m, FAM_VFX, False)},
        "minecraft:collision_box": {"width": m.collision[0],
                                    "height": m.collision[1]},
        "minecraft:health": _hp(m),
        # 静止する拳は重力なし。投げた雷だけは投擲の弧を描かせる。
        "minecraft:physics": {"has_gravity": not m.stationary,
                              "has_collision": False},
        "minecraft:pushable": {"is_pushable": False,
                               "is_pushable_by_piston": False},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:fire_immune": {},
        "minecraft:mark_variant": {"value": 0},
        "minecraft:conditional_bandwidth_optimization": {},
        # 演出は殴っても壊せない。壊せると「消えない拳」より質の悪い
        # 「途中で消える拳」が出る。cause "all" は原因を問わないの意。
        "minecraft:damage_sensor": {
            "triggers": [
                {"cause": "all", "damage_multiplier": 0.0, "deals_damage": False}
            ]
        },
        # 寿命。spec の tick を秒に直す (Bedrock の timer は秒)。
        "minecraft:timer": {
            "looping": False,
            "time": round(m.despawn / 20.0, 2),
            "time_down_event": {"event": EV_EXPIRE}
        },
    }
    if m.scale != 1.0:
        comps["minecraft:scale"] = {"value": m.scale}
    return {
        "format_version": ENTITY_FMT,
        "minecraft:entity": {
            "description": {
                # スポーンエッグを作らせない。配布経路を持たせないための指定。
                "identifier": m.id,
                "is_spawnable": m.summonable,
                "is_summonable": True,
                "is_experimental": False
            },
            "component_groups": {
                CG_DESPAWN: {"minecraft:instant_despawn": {}}
            },
            "components": comps,
            "events": {
                EV_EXPIRE: {"add": {"component_groups": [CG_DESPAWN]}}
            }
        }
    }


def gen_entities() -> int:
    out = os.path.join(BP, "entities")
    for m in spec.MOBS:
        # spec.Mob.despawn が 0 でないものが内部表示体、という切り分け。
        doc = vfx_entity(m) if m.despawn else target_entity(m)
        dump(os.path.join(out, m.slug + ".entity.json"), doc)
    vfx = sum(1 for m in spec.MOBS if m.despawn)
    print(f"  entities       {len(spec.MOBS):2d}  (的 {len(spec.MOBS) - vfx} / "
          f"内部表示体 {vfx})")
    return len(spec.MOBS)


# ================================================================ LOOT TABLES
def gen_loot() -> int:
    """訓練用の標的は何も落とさない (企画書 §12)。

    落とし物があると、負荷テスト区画でアイテムが溜まって計測が濁る。
    空のプールを明示的に書くのは、ルートテーブル自体が無いと
    エンティティ側の参照が宙に浮くため。
    """
    out = os.path.join(BP, "loot_tables", "entities")
    slugs = [m.slug for m in spec.MOBS if not m.despawn]
    for slug in slugs:
        dump(os.path.join(out, slug + ".json"), {"pools": []})
    print(f"  loot tables    {len(slugs):2d}  (すべて空)")
    return len(slugs)


# =====================================================================  CRAFT
#  作れるのはこの4つだけ。形態表示体 (form_*) には絶対にレシピを与えない
#  — 企画書 §14 増殖防止。配布経路が1つ増えるたびに「解除し忘れた見た目」が
#  ワールドに残る余地が増える。材料はすべてバニラ由来で、他パックと競合しない。
RECIPES = {
    # slug: (pattern, key)
    "devil_fruit": ([" C ", "CAC", " C "],
                    {"C": "minecraft:chorus_fruit", "A": "minecraft:apple"}),
    "straw_hat": ([" W ", "WRW", "WWW"],
                  {"W": "minecraft:wheat", "R": "minecraft:red_wool"}),
    "fist_wrap": (["SSS", "SLS"],
                  {"S": "minecraft:string", "L": "minecraft:leather"}),
    "log_pose": ([" G ", "GCG", "LLL"],
                 {"G": "minecraft:glass", "C": "minecraft:compass",
                  "L": "minecraft:leather"}),
}


def shaped(slug: str, pattern: list, keys: dict, count: int = 1) -> dict:
    return {
        "format_version": RECIPE_FMT,
        "minecraft:recipe_shaped": {
            "description": {"identifier": f"{NS}:{slug}"},
            "tags": ["crafting_table"],
            "pattern": list(pattern),
            "key": {k: {"item": v} for k, v in keys.items()},
            "result": {"item": spec.ITEM_BY_SLUG[slug].id, "count": count}
        }
    }


def gen_recipes() -> int:
    out = os.path.join(BP, "recipes")
    for slug, (pattern, keys) in RECIPES.items():
        it = spec.ITEM_BY_SLUG[slug]
        if it.hidden:
            # 事故で form_* が RECIPES に入った場合はここで生成を止める。
            raise SystemExit(f"{it.id}: 内部用アイテムにレシピを与えてはいけない")
        dump(os.path.join(out, slug + ".json"), shaped(slug, pattern, keys))
    print(f"  recipes        {len(RECIPES):2d}  "
          f"(形態表示体 {len(spec.FORM_ITEMS)} 件は意図的に無し)")
    return len(RECIPES)


# =================================================================  MANIFESTS
def gen_manifests() -> int:
    """BP と RP の manifest。UUID は spec.py の固定値をそのまま使う。

    企画書 §18「他パックとの競合」— 怪獣8号パックと同時に入れても
    衝突しないよう、5つの UUID は spec.py 側で固定済み。
    名前と説明は pack.name / pack.description の lang キーに逃がしてあるので、
    表示言語の切り替えがそのまま効く。
    """
    version = list(spec.VERSION)
    authors = [f"{spec.PROJECT} Addon Project"]

    dump(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {
            "name": "pack.name",
            "description": "pack.description",
            "uuid": spec.UUID_BP_HEADER,
            "version": version,
            "min_engine_version": list(spec.MIN_ENGINE)
        },
        "modules": [
            {"type": "data", "uuid": spec.UUID_BP_DATA, "version": version},
            {"type": "script", "language": "javascript",
             "uuid": spec.UUID_BP_SCRIPT, "version": version,
             "entry": "scripts/main.js"}
        ],
        # 先頭は必ず相方の RP。検証がこの並びを見て相互依存を確かめる。
        "dependencies": [
            {"uuid": spec.UUID_RP_HEADER, "version": version},
            {"module_name": "@minecraft/server", "version": spec.SERVER_MODULE},
            {"module_name": "@minecraft/server-ui",
             "version": spec.SERVER_UI_MODULE}
        ],
        "metadata": {"authors": authors, "license": "MIT",
                     "product_type": "addon"}
    })

    dump(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {
            "name": "pack.name",
            "description": "pack.description",
            "uuid": spec.UUID_RP_HEADER,
            "version": version,
            "min_engine_version": list(spec.MIN_ENGINE)
        },
        "modules": [
            {"type": "resources", "uuid": spec.UUID_RP_RES, "version": version}
        ],
        "dependencies": [{"uuid": spec.UUID_BP_HEADER, "version": version}],
        "metadata": {"authors": authors, "license": "MIT",
                     "product_type": "addon"}
    })
    print("  manifests       2  (BP <-> RP 相互依存)")
    return 2


# =================================================================  PACK ICON
def _rgb(hex_col: str) -> tuple:
    """palette.py の #RRGGBB を PIL の (r,g,b) へ。色の定義元を二重に持たない。"""
    h = hex_col.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def pack_icon(path: str, sky=(96, 164, 208), sea=(20, 54, 96)) -> None:
    """麦わら帽子のシルエット。

    企画書 §06「小さくても読める輪郭」— パックの一覧では 64px 程度まで
    縮むので、要素を つば・山・赤い帯 の3つに絞り、背景は
    水平線1本だけの縦グラデーションにして情報を持たせない。
    """
    size = 128
    straw, straw_d = _rgb(palette.STRAW), _rgb(palette.STRAW_D)
    band = _rgb(palette.HATBAND)
    ink = (26, 20, 14)

    img = Image.new("RGBA", (size, size), sky + (255,))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        d.line([(0, y), (size, y)],
               fill=(int(sky[0] + (sea[0] - sky[0]) * t),
                     int(sky[1] + (sea[1] - sky[1]) * t),
                     int(sky[2] + (sea[2] - sky[2]) * t), 255))
    # 水平線。帽子の下半分が背景に溶けないよう、ここで明度差を作る。
    d.rectangle([0, 86, size - 1, size - 1], fill=sea + (255,))

    # 山 → つば → 帯 の順。つばが山の裾を隠し、帯がつばの上に乗る。
    d.ellipse([40, 24, 88, 70], fill=straw, outline=ink, width=3)
    d.ellipse([8, 68, 120, 108], fill=straw_d, outline=ink, width=3)
    d.ellipse([8, 62, 120, 100], fill=straw, outline=ink, width=3)
    # 編み目は同心の2本だけ。これ以上増やすと 64px で潰れて灰色になる。
    d.ellipse([24, 68, 104, 94], outline=straw_d, width=2)
    d.ellipse([38, 72, 90, 90], outline=straw_d, width=2)
    d.rectangle([42, 48, 86, 64], fill=band, outline=ink, width=2)

    d.rectangle([0, 0, size - 1, size - 1], outline=(232, 226, 206, 255), width=3)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


def gen_pack_icons() -> int:
    # BP は夕方の海、RP は昼の海。並んだときにどちらか判別できる程度の差。
    pack_icon(os.path.join(BP, "pack_icon.png"), (214, 146, 92), (74, 42, 78))
    pack_icon(os.path.join(RP, "pack_icon.png"))
    print("  pack icons      2  (BP 夕 / RP 昼)")
    return 2


# ===========================================================================
def check() -> None:
    """生成前に前提を潰す。企画書 §14 の3条件は壊れたら気付きにくい。"""
    for it in spec.ITEMS:
        if it.hidden and it.stack != 1:
            raise SystemExit(f"{it.id}: 内部用アイテムは 1 スタックのはず")
        if it.hidden and it.slug in RECIPES:
            raise SystemExit(f"{it.id}: 内部用アイテムにレシピがある")
    for slug in RECIPES:
        if slug not in spec.ITEM_BY_SLUG:
            raise SystemExit(f"{slug}: spec.ITEMS に無いアイテムのレシピ")
    for m in spec.MOBS:
        if m.despawn and m.summonable:
            raise SystemExit(f"{m.id}: 内部表示体にスポーンエッグを出さない")
        if m.despawn == 0 and not m.summonable:
            raise SystemExit(f"{m.id}: 寿命の無い非配布エンティティは掃除できない")


def main() -> None:
    print(f"behaviour pack ({NS}):")
    n = {
        "items": gen_items(),
        "entities": gen_entities(),
        "loot": gen_loot(),
        "recipes": gen_recipes(),
        "manifests": gen_manifests(),
        "icons": gen_pack_icons(),
    }
    total_json = n["items"] + n["entities"] + n["loot"] + n["recipes"] \
        + n["manifests"]
    print(f"\n  {total_json} json + {n['icons']} png  ->  "
          f"{spec.BP_DIR} / {spec.RP_DIR}")
    print(f"  {len(spec.FORMS)} 形態 / {len(spec.TECHS)} 技 は spec.py 側の定義のまま "
          f"— このファイルは技を1つも知らない")


if __name__ == "__main__":
    check()
    main()
