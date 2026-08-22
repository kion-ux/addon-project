# -*- coding: utf-8 -*-
"""正典 (the contract).

十人の担当が並列で作業するので、**識別子はすべてここで決める**。
各モジュールはここから名前を読むだけで、勝手に文字列を書かない。
ここに無い識別子を使いたくなったら、まずここへ足すこと。

命名規則
--------
geometry     ``geometry.marvel.<key>``
texture      ``textures/entity/marvel/<key>``      (RP からの相対)
animation    ``animation.marvel.<group>.<clip>``
controller   ``controller.animation.marvel.<name>``
render ctrl  ``controller.render.marvel.<name>``
particle     ``marvel:<name>``
entity/item  ``marvel:<key>``
"""
from __future__ import annotations

import os

NS = "marvel"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BP = os.path.join(ROOT, "packs", "marvel_BP")
RP = os.path.join(ROOT, "packs", "marvel_RP")

GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", "marvel")
ITEM_TEX_DIR = os.path.join(RP, "textures", "items")
ANIM_DIR = os.path.join(RP, "animations")
CTRL_DIR = os.path.join(RP, "animation_controllers")
RENDER_DIR = os.path.join(RP, "render_controllers")
PART_DIR = os.path.join(RP, "particles")
CLIENT_DIR = os.path.join(RP, "entity")
ATTACH_DIR = os.path.join(RP, "attachables")
SCRIPT_DIR = os.path.join(BP, "scripts")

VERSION = "1.0.0"
ADDON_NAME = "MarvelMutants"


def geo(key: str) -> str:
    return f"geometry.{NS}.{key}"


def tex(key: str) -> str:
    return f"textures/entity/{NS}/{key}"


def anim(group: str, clip: str) -> str:
    return f"animation.{NS}.{group}.{clip}"


def ctrl(name: str) -> str:
    return f"controller.animation.{NS}.{name}"


def render_ctrl(name: str) -> str:
    return f"controller.render.{NS}.{name}"


def part(name: str) -> str:
    return f"{NS}:{name}"


def eid(key: str) -> str:
    return f"{NS}:{key}"


# ===========================================================================
#  1. ロースター  —  ブラザーフッド・オブ・ミュータンツ
# ===========================================================================
#  cm/heads/sh/limb/bulk は rig.Build にそのまま渡る体格パラメータ。
#  pal は palettes.ALL のキー、geo/tex は contract.geo()/tex() のキー。
#
#  役割:
#    "lead"  マグニートー   —  極限まで作り込む主役（技15）
#    "ally"  ブラザーフッド —  召喚できる仲間 NPC + 簡易変身（技3）
#    "enemy" センチネル他   —  敵対 NPC
# ===========================================================================

MAGNETO = "magneto"

BROTHERHOOD = [
    "mystique", "sabretooth", "toad", "juggernaut",
    "quicksilver", "pyro", "avalanche", "blob", "scarlet_witch",
]

ENEMIES = ["sentinel", "prime_sentinel", "sentinel_drone", "mrd_trooper"]

# key -> 体格・見た目・所属
CHARACTERS = {
    # --- 主役 ---------------------------------------------------------
    "magneto": dict(
        role="lead", cm=188, heads=7.6, sh=0.258, limb=1.02, bulk=1.06,
        female=False, pal="magneto", ja="マグニートー", en="Magneto",
        real_ja="エリック・マグナス・レーンシャー", real_en="Erik Lehnsherr",
        egg=("#5B1A6E", "#B0141E"), health=520, damage=14, speed=0.28,
        blurb_ja="磁界の帝王。地球上のあらゆる金属を意のままに操る。",
    ),
    # --- ブラザーフッド -------------------------------------------------
    "mystique": dict(
        role="ally", cm=170, heads=7.8, sh=0.222, limb=0.88, bulk=0.94,
        female=True, pal="mystique", ja="ミスティーク", en="Mystique",
        real_ja="レイヴン・ダークホルム", real_en="Raven Darkhölme",
        egg=("#1E4E8C", "#D14A2B"), health=140, damage=9, speed=0.34,
        blurb_ja="姿を自在に変える変身能力者。潜入と暗殺の達人。",
    ),
    "sabretooth": dict(
        role="ally", cm=201, heads=7.2, sh=0.286, limb=1.24, bulk=1.24,
        female=False, pal="sabretooth", ja="セイバートゥース", en="Sabretooth",
        real_ja="ヴィクター・クリード", real_en="Victor Creed",
        egg=("#7A5A28", "#8E1F1F"), health=260, damage=16, speed=0.32,
        blurb_ja="獣の本能と再生能力を持つ追跡者。爪と牙で獲物を裂く。",
    ),
    "toad": dict(
        role="ally", cm=168, heads=6.6, sh=0.238, limb=0.96, bulk=1.02,
        female=False, pal="toad", ja="トード", en="Toad",
        real_ja="モーティマー・トインビー", real_en="Mortimer Toynbee",
        egg=("#4A6B2A", "#2E4419"), health=120, damage=7, speed=0.31,
        hunch=14.0,
        blurb_ja="跳躍力と伸縮する舌を武器にする。粘液は視界を奪う。",
    ),
    "juggernaut": dict(
        role="ally", cm=290, heads=7.0, sh=0.310, limb=1.55, bulk=1.55,
        female=False, pal="juggernaut", ja="ジャガーノート", en="Juggernaut",
        real_ja="ケイン・マーコ", real_en="Cain Marko",
        egg=("#8E1F1F", "#4A4A52"), health=700, damage=26, speed=0.26,
        blurb_ja="一度走り出せば何者にも止められない、破壊の権化。",
    ),
    "quicksilver": dict(
        role="ally", cm=183, heads=7.8, sh=0.238, limb=0.92, bulk=0.94,
        female=False, pal="quicksilver", ja="クイックシルバー", en="Quicksilver",
        real_ja="ピエトロ・マキシモフ", real_en="Pietro Maximoff",
        egg=("#C8CBD2", "#3C6FA8"), health=130, damage=8, speed=0.52,
        blurb_ja="音を置き去りにする速度。世界が止まって見える。",
    ),
    "pyro": dict(
        role="ally", cm=176, heads=7.5, sh=0.236, limb=0.94, bulk=0.98,
        female=False, pal="pyro", ja="パイロ", en="Pyro",
        real_ja="セント・ジョン・アラーダイス", real_en="St. John Allerdyce",
        egg=("#D8621E", "#2A2A30"), health=130, damage=9, speed=0.31,
        blurb_ja="炎を生み出せはしないが、生まれた炎は全て彼のものだ。",
    ),
    "avalanche": dict(
        role="ally", cm=182, heads=7.3, sh=0.268, limb=1.14, bulk=1.16,
        female=False, pal="avalanche", ja="アバランチ", en="Avalanche",
        real_ja="ドミニク・ペトロス", real_en="Dominic Petros",
        egg=("#6B5A48", "#8E4A1E"), health=200, damage=14, speed=0.29,
        blurb_ja="地殻に振動を送り込み、大地そのものを崩落させる。",
    ),
    "blob": dict(
        role="ally", cm=196, heads=5.4, sh=0.352, limb=1.85, bulk=2.10,
        female=False, pal="blob", ja="ブロブ", en="Blob",
        real_ja="フレッド・デュークス", real_en="Fred Dukes",
        egg=("#C4A05A", "#3E4A2A"), health=560, damage=18, speed=0.22,
        blurb_ja="地面に根を張れば、誰にも動かせない不動の巨体。",
    ),
    "scarlet_witch": dict(
        role="ally", cm=170, heads=7.9, sh=0.220, limb=0.86, bulk=0.92,
        female=True, pal="scarlet_witch", ja="スカーレット・ウィッチ",
        en="Scarlet Witch", real_ja="ワンダ・マキシモフ",
        real_en="Wanda Maximoff",
        egg=("#8E1224", "#2A1420"), health=170, damage=12, speed=0.30,
        blurb_ja="確率を捻じ曲げるヘックス。現実そのものが彼女に従う。",
    ),
    # --- 敵 -------------------------------------------------------------
    "sentinel": dict(
        role="enemy", cm=440, heads=7.4, sh=0.300, limb=1.40, bulk=1.35,
        female=False, pal="sentinel", ja="センチネル Mk-I", en="Sentinel Mk-I",
        egg=("#5B3E8E", "#C43A1E"), health=340, damage=18, speed=0.25,
        blurb_ja="ミュータント狩猟用の巨大ロボット。全身が金属でできている。",
    ),
    "prime_sentinel": dict(
        role="enemy", cm=760, heads=7.0, sh=0.322, limb=1.70, bulk=1.70,
        female=False, pal="prime_sentinel", ja="プライム・センチネル",
        en="Prime Sentinel",
        egg=("#3A2A5E", "#E85A1E"), health=1400, damage=34, speed=0.24,
        blurb_ja="適応学習する最新鋭機。磁力干渉への耐性を持つ。",
    ),
    "sentinel_drone": dict(
        role="enemy", cm=150, heads=4.0, sh=0.400, limb=1.20, bulk=1.30,
        female=False, pal="sentinel", ja="センチネル・ドローン",
        en="Sentinel Drone",
        egg=("#5B3E8E", "#8E8E9A"), health=70, damage=8, speed=0.36,
        blurb_ja="偵察用の浮遊ドローン。センチネル本体に座標を送る。",
    ),
    "mrd_trooper": dict(
        role="enemy", cm=178, heads=7.4, sh=0.252, limb=1.04, bulk=1.08,
        female=False, pal="mrd", ja="MRD隊員", en="MRD Trooper",
        egg=("#2A2E38", "#8E1F1F"), health=90, damage=7, speed=0.30,
        blurb_ja="対ミュータント対応部隊。制圧銃と抑制装甲で武装する。",
    ),
}

PLAYABLE = [MAGNETO] + BROTHERHOOD
ALL_CHARACTERS = list(CHARACTERS)

# 補助エンティティ（モデルはあるが人型ではないもの）
PROP_ENTITIES = {
    "metal_shard": dict(ja="鉄片", en="Metal Shard"),
    "debris": dict(ja="瓦礫", en="Debris"),
    "hex_bolt": dict(ja="ヘックス弾", en="Hex Bolt"),
    "fire_bolt": dict(ja="火炎弾", en="Fire Bolt"),
    "sentinel_beam": dict(ja="センチネル・ビーム", en="Sentinel Beam"),
    "barrier_dome": dict(ja="磁力障壁", en="Magnetic Barrier"),
    "steel_platform": dict(ja="鋼鉄の玉座", en="Steel Throne"),
    "orbit_shard": dict(ja="周回鉄片", en="Orbiting Shard"),
    "ruin_sphere": dict(ja="磁界の棺", en="Sphere of Ruin"),
    "iron_cage": dict(ja="鋼鉄拘束", en="Iron Bind"),
}

ENTITY_KEYS = ALL_CHARACTERS + list(PROP_ENTITIES)

#: エンティティではないが必要なジオメトリ。
#:   fp_hand   一人称で手元に出る磁力ガントレット（技アイテムの attachable）
#:   tech_orb  技アイテムを持っている時に三人称で手に浮かぶ磁力球
#:   helmet_prop  手に持った時に表示される兜そのもの（変身アイテムの見た目）
EXTRA_GEOMETRIES = ["fp_hand", "tech_orb", "helmet_prop"]


# ===========================================================================
#  2. マグニートーの技  —  15種。ここが本作の心臓部。
# ===========================================================================
#  item   : 技を発動するアイテム ID (marvel:tech_*)
#  icon   : textures/items/<icon>.png
#  pose   : 三人称で再生する変身体ポーズ (FORM_POSES のキー)
#  clip   : 技アニメーション clip 名 -> animation.marvel.tech.<clip>
#  fp     : 一人称で手元に出る attachable のクリップ -> animation.marvel.fp.<fp>
#  cost   : 磁力 (MAG) 消費
#  cd     : クールダウン tick
#  stage  : 解禁に必要な段階 (1=エリック, 2=マグニートー, 3=磁界の帝王)
#  colour : UI とパーティクルの基調色
# ===========================================================================

TECHNIQUES = {
    "repulse": dict(
        ja="磁力斥力", en="Repulse", romaji="Jiryoku Sekiryoku",
        item="tech_repulse", icon="tech_repulse", pose="cast", clip="repulse",
        fp="thrust", cost=14, cd=35, stage=1, colour="#7B4BC8",
        desc_ja="正面の全てを磁力で弾き飛ばす。金属を持つ相手ほど強く吹き飛ぶ。",
    ),
    "attract": dict(
        ja="磁力引力", en="Attract", romaji="Jiryoku Inryoku",
        item="tech_attract", icon="tech_attract", pose="cast", clip="attract",
        fp="pull", cost=8, cd=16, stage=1, colour="#4B7BC8",
        desc_ja="視線の先の敵・アイテム・金属ブロックを手元へ引き寄せる。",
    ),
    "disarm": dict(
        ja="金属剥奪", en="Disarm", romaji="Kinzoku Hakudatsu",
        item="tech_disarm", icon="tech_disarm", pose="cast", clip="disarm",
        fp="grip", cost=12, cd=45, stage=1, colour="#C8C04B",
        desc_ja="相手の武器と防具を磁力で引き剥がす。鉄の鎧は文字通り脱げる。",
    ),
    "lance": dict(
        ja="磁界斬", en="Magnetic Lance", romaji="Jikai Zan",
        item="tech_lance", icon="tech_lance", pose="cast", clip="lance",
        fp="lance", cost=14, cd=24, stage=1, colour="#9B5BE0",
        desc_ja="鉄片を槍状に束ね、直線上を貫く。壁も敵も纏めて刺し貫く。",
    ),
    "shard_storm": dict(
        ja="鉄片嵐", en="Shard Storm", romaji="Teppen Arashi",
        item="tech_shard_storm", icon="tech_shard_storm", pose="raise",
        clip="shard_storm", fp="storm", cost=30, cd=160, stage=2,
        colour="#B04BC8",
        desc_ja="周囲の金属を無数の刃に変え、標的へ叩き込む嵐。",
    ),
    "barrier": dict(
        ja="磁力障壁", en="Magnetic Barrier", romaji="Jiryoku Shouheki",
        item="tech_barrier", icon="tech_barrier", pose="guard", clip="barrier",
        fp="guard", cost=20, cd=200, stage=1, colour="#4BC8C0",
        desc_ja="磁界のドームを展開。矢も弾も爆風も、届く前に逸らされる。",
    ),
    "iron_bind": dict(
        ja="鋼鉄拘束", en="Iron Bind", romaji="Koutetsu Kousoku",
        item="tech_iron_bind", icon="tech_iron_bind", pose="cast",
        clip="iron_bind", fp="grip", cost=22, cd=90, stage=2, colour="#8E8E9A",
        desc_ja="鉄格子を編み上げ、標的をその場に縫い止める檻を作る。",
    ),
    "crush": dict(
        ja="磁気圧壊", en="Crush", romaji="Jiki Akkai",
        item="tech_crush", icon="tech_crush", pose="cast", clip="crush",
        fp="crush", cost=34, cd=200, stage=2, colour="#C8344B",
        desc_ja="装甲を内側から握り潰す。金属を纏う者ほど、無惨に潰れる。",
    ),
    "uprising": dict(
        ja="大地隆起", en="Ore Uprising", romaji="Daichi Ryuuki",
        item="tech_uprising", icon="tech_uprising", pose="raise",
        clip="uprising", fp="raise", cost=34, cd=140, stage=2,
        colour="#C8843A",
        desc_ja="地中の鉱脈ごと大地を引き剥がし、鉄塊の柱を突き上げる。",
    ),
    "emp": dict(
        ja="EMPパルス", en="EMP Pulse", romaji="EMP Pulse",
        item="tech_emp", icon="tech_emp", pose="focus", clip="emp",
        fp="pulse", cost=20, cd=160, stage=2, colour="#4BE0FF",
        desc_ja="電磁パルスで機械を沈黙させる。センチネルには致命的。",
    ),
    "polarity": dict(
        ja="磁極反転", en="Polarity Reversal", romaji="Jikyoku Hanten",
        item="tech_polarity", icon="tech_polarity", pose="raise",
        clip="polarity", fp="raise", cost=22, cd=120, stage=2,
        colour="#6B4BE0",
        desc_ja="一帯の磁極を反転させ、重さという概念を取り上げる。",
    ),
    "flight": dict(
        ja="磁気飛行", en="Magnetic Flight", romaji="Jiki Hikou",
        item="tech_flight", icon="tech_flight", pose="fly", clip="flight",
        fp="fly", cost=8, cd=6, stage=1, colour="#9B7BE0",
        desc_ja="己の磁界に乗って空を征く。マントが風を孕む。",
    ),
    "throne": dict(
        ja="鋼鉄の玉座", en="Steel Throne", romaji="Koutetsu no Gyokuza",
        item="tech_throne", icon="tech_throne", pose="cast", clip="throne",
        fp="raise", cost=18, cd=100, stage=2, colour="#8E9AA8",
        desc_ja="鉄塊を足場に組み上げ、乗って移動する。空中の要塞。",
    ),
    "sight": dict(
        ja="磁力視", en="Magnetic Sight", romaji="Jiryoku Shi",
        item="tech_sight", icon="tech_sight", pose="focus", clip="sight",
        fp="focus", cost=6, cd=60, stage=1, colour="#4BC8FF",
        desc_ja="壁越しに金属を視る。鉱脈も、隠れた鎧も、全て光って見える。",
    ),
    "sphere": dict(
        ja="磁界の棺", en="Sphere of Ruin", romaji="Jikai no Hitsugi",
        item="tech_sphere", icon="tech_sphere", pose="raise", clip="sphere",
        fp="storm", cost=70, cd=600, stage=3, colour="#E04B7B", ultimate=True,
        desc_ja="半径40の金属を残らず引き寄せ、圧縮し、解き放つ。必殺技。",
    ),
}

TECH_ORDER = [
    "repulse", "attract", "disarm", "lance", "flight", "sight",
    "barrier", "shard_storm", "iron_bind", "crush", "uprising",
    "emp", "polarity", "throne", "sphere",
]

# ブラザーフッドの技（1人3種）。マグニートーの枠組みを共有する。
ALLY_TECHNIQUES = {
    "mystique": [
        dict(key="shapeshift", ja="擬態", en="Shapeshift", clip="shapeshift",
             cost=14, cd=120, colour="#1E4E8C",
             desc_ja="近くの相手に化け、敵意を逸らす。"),
        dict(key="venom_strike", ja="毒撃", en="Venom Strike", clip="venom_strike",
             cost=10, cd=50, colour="#3AC86B",
             desc_ja="毒を仕込んだ一撃で相手を蝕む。"),
        dict(key="vanish", ja="影渡り", en="Vanish", clip="vanish",
             cost=12, cd=90, colour="#2A2A5E",
             desc_ja="姿を消して背後へ回り込む。"),
    ],
    "sabretooth": [
        dict(key="rend", ja="裂爪", en="Rend", clip="rend", cost=10, cd=30,
             colour="#C8344B", desc_ja="両爪で薙ぎ払い、出血を強いる。"),
        dict(key="feral_roar", ja="獣咆", en="Feral Roar", clip="feral_roar",
             cost=16, cd=100, colour="#C8843A",
             desc_ja="咆哮で周囲を怯ませ、自らを昂ぶらせる。"),
        dict(key="regenerate", ja="超回復", en="Regenerate", clip="regenerate",
             cost=20, cd=160, colour="#3AC86B",
             desc_ja="傷が塞がる。この男は死なない。"),
    ],
    "toad": [
        dict(key="tongue_lash", ja="舌鞭", en="Tongue Lash", clip="tongue_lash",
             cost=8, cd=40, colour="#4A6B2A",
             desc_ja="伸ばした舌で標的を捕らえ引き寄せる。"),
        dict(key="leap", ja="大跳躍", en="Great Leap", clip="leap", cost=10,
             cd=50, colour="#6B8E3A", desc_ja="脚力だけで空へ跳ぶ。"),
        dict(key="slime_spit", ja="粘液弾", en="Slime Spit", clip="slime_spit",
             cost=12, cd=60, colour="#8EC84B",
             desc_ja="粘液を吐き、視界と足を奪う。"),
    ],
    "juggernaut": [
        dict(key="unstoppable", ja="無停止突進", en="Unstoppable",
             clip="unstoppable", cost=26, cd=140, colour="#8E1F1F",
             desc_ja="走り出したら止まらない。壁ごと相手を轢き潰す。"),
        dict(key="quake_stomp", ja="地砕き", en="Quake Stomp", clip="quake_stomp",
             cost=20, cd=100, colour="#6B5A48",
             desc_ja="踏み抜いた大地が割れ、衝撃が走る。"),
        dict(key="hurl", ja="投擲", en="Hurl", clip="hurl", cost=16, cd=80,
             colour="#8E8E9A", desc_ja="掴んだものを何でも投げる。"),
    ],
    "quicksilver": [
        dict(key="blitz", ja="音速連撃", en="Blitz", clip="blitz", cost=18,
             cd=70, colour="#C8CBD2",
             desc_ja="一瞬で間合いを詰め、見えない速さで殴り抜ける。"),
        dict(key="afterimage", ja="残像", en="Afterimage", clip="afterimage",
             cost=14, cd=90, colour="#8EB4E0",
             desc_ja="残像を置き去りにして回避する。"),
        dict(key="sonic_dash", ja="超加速", en="Sonic Dash", clip="sonic_dash",
             cost=10, cd=40, colour="#4B9BE0",
             desc_ja="世界が止まって見えるほどに加速する。"),
    ],
    "pyro": [
        dict(key="flame_wave", ja="炎波", en="Flame Wave", clip="flame_wave",
             cost=16, cd=60, colour="#D8621E",
             desc_ja="既にある炎を掻き集め、波にして放つ。"),
        dict(key="fire_serpent", ja="炎蛇", en="Fire Serpent",
             clip="fire_serpent", cost=22, cd=100, colour="#E88A2A",
             desc_ja="炎を蛇の形に編み、標的を追わせる。"),
        dict(key="ignite", ja="発火", en="Ignite", clip="ignite", cost=8,
             cd=30, colour="#F0B23A", desc_ja="炎を生み、燃料を与える。"),
    ],
    "avalanche": [
        dict(key="tremor", ja="震動", en="Tremor", clip="tremor", cost=14,
             cd=60, colour="#6B5A48", desc_ja="地面を揺らし、立つことを許さない。"),
        dict(key="rockfall", ja="落盤", en="Rockfall", clip="rockfall",
             cost=22, cd=110, colour="#8E7A5A",
             desc_ja="頭上の岩盤を崩し、標的へ落とす。"),
        dict(key="fissure", ja="地割れ", en="Fissure", clip="fissure", cost=26,
             cd=130, colour="#5A4A38",
             desc_ja="足元から裂け目を走らせ、大地ごと引き裂く。"),
    ],
    "blob": [
        dict(key="immovable", ja="不動", en="Immovable", clip="immovable",
             cost=18, cd=120, colour="#C4A05A",
             desc_ja="地に根を張る。この間、何者も彼を動かせない。"),
        dict(key="belly_bounce", ja="弾き返し", en="Belly Bounce",
             clip="belly_bounce", cost=14, cd=70, colour="#D8B46A",
             desc_ja="腹で受け止め、そのまま弾き返す。"),
        dict(key="body_slam", ja="のしかかり", en="Body Slam", clip="body_slam",
             cost=20, cd=90, colour="#8E7A4A",
             desc_ja="全体重を乗せて潰しにかかる。"),
    ],
    "scarlet_witch": [
        dict(key="hex_bolt", ja="ヘックス弾", en="Hex Bolt", clip="hex_bolt",
             cost=12, cd=40, colour="#8E1224",
             desc_ja="確率を捻じ曲げる弾を放つ。当たれば何が起きるか判らない。"),
        dict(key="chaos_field", ja="混沌領域", en="Chaos Field",
             clip="chaos_field", cost=24, cd=130, colour="#C82A4B",
             desc_ja="一帯の因果を乱し、敵の攻撃を外れさせる。"),
        dict(key="telekinesis", ja="念動", en="Telekinesis", clip="telekinesis",
             cost=18, cd=80, colour="#E04B7B",
             desc_ja="視線の先のものを掴み、宙へ吊るし上げる。"),
    ],
}


# ===========================================================================
#  3. 変身体  —  三人称でどう見えるか
# ===========================================================================
#  変身中はプレイヤーの頭スロットに「体」アイテムを装備させ、全身を描画する。
#  スクリプトから三人称のアニメーションを確実に切り替える手段は無いので、
#  **技ごとに別アイテムを用意し、技の間だけそれに差し替える**。
#  差し替わった瞬間に、その技専用のアタッチャブル（＝専用アニメ）が読み込まれる。
#
#  pose は「その技がどの姿勢の系統か」を表すだけの分類で、
#  アニメーションの作り分けの指針として使う（アイテムは技ごとに独立）。
# ===========================================================================

POSE_FAMILIES = {
    "cast":  dict(ja="片手詠唱", hint="片腕を前へ突き出す。腰は逆へ捻る。"),
    "raise": dict(ja="両手掲げ", hint="両腕を頭上へ。マントが下から煽られる。"),
    "guard": dict(ja="防御",     hint="両腕を交差。踏み込んで重心を落とす。"),
    "fly":   dict(ja="飛行",     hint="全身を伸ばし、爪先まで一直線。"),
    "focus": dict(ja="集中",     hint="指をこめかみへ。動きを最小限に。"),
}

#: 技を撃っている間、変身体アイテムを差し替えておく tick 数（既定値）。
POSE_HOLD = {"cast": 22, "raise": 34, "guard": 40, "fly": 0, "focus": 26}
# ===========================================================================
#  4. アイテム
# ===========================================================================

ITEMS = {
    # --- 中核 ---------------------------------------------------------
    "x_gene": dict(
        ja="X遺伝子", en="X-Gene", icon="x_gene", stack=1, glint=True,
        category="items", food=True,
        desc_ja="己の内に眠る力を呼び覚ます。使うとミュータントとして覚醒する。"),
    "magneto_helmet": dict(
        ja="マグニートーのヘルメット", en="Magneto's Helmet", icon="magneto_helmet",
        stack=1, glint=True, category="equipment", hand=True,
        desc_ja="精神干渉を遮断する兜。持って使えば変身、スニーク＋使用で設定。"),
    "brotherhood_pin": dict(
        ja="ブラザーフッドの徽章", en="Brotherhood Pin", icon="brotherhood_pin",
        stack=1, glint=True, category="equipment",
        desc_ja="選んだ仲間の姿へ変身する。スニーク＋使用でメンバーを選ぶ。"),
    "cerebro": dict(
        ja="セレブロ・バイザー", en="Cerebro Visor", icon="cerebro", stack=1,
        category="equipment", hand=True,
        desc_ja="金属とミュータントを探知する。スニーク＋使用で司令端末。"),
    "brotherhood_beacon": dict(
        ja="招集信号", en="Brotherhood Beacon", icon="brotherhood_beacon",
        stack=16, category="items",
        desc_ja="ブラザーフッドの仲間を呼び出す。"),
    # --- 変身体（インベントリには出ない） -------------------------------
    "magneto_form": dict(ja="磁界の帝王の体", en="Master of Magnetism",
                         icon="magneto_form", stack=1, hidden=True),
    # --- 素材 ---------------------------------------------------------
    "metal_scrap": dict(ja="金属片", en="Metal Scrap", icon="metal_scrap",
                        stack=64, category="items",
                        desc_ja="磁力で引き寄せた金属の欠片。"),
    "magnetic_alloy": dict(ja="磁性合金", en="Magnetic Alloy",
                           icon="magnetic_alloy", stack=64, category="items",
                           desc_ja="磁力を蓄えられるよう精錬された合金。"),
    "sentinel_core": dict(ja="センチネル・コア", en="Sentinel Core",
                          icon="sentinel_core", stack=16, glint=True,
                          category="items",
                          desc_ja="センチネルの動力源。まだ微かに脈打っている。"),
    "adamantium_ingot": dict(ja="アダマンチウム・インゴット",
                             en="Adamantium Ingot", icon="adamantium_ingot",
                             stack=64, glint=True, category="items",
                             desc_ja="磁力の効かない唯一の金属。"),
}


def form_key(character: str, tech: str | None = None) -> str:
    """変身体アイテムのキー。``tech`` を渡すとその技専用の姿勢になる。"""
    if tech is None:
        return f"{character}_form"
    return f"{character}_form_{tech}"


def form_item(character: str, tech: str | None = None) -> str:
    return eid(form_key(character, tech))


def tech_item(key: str) -> str:
    return eid(TECHNIQUES[key]["item"])


def ally_tech_keys(character: str) -> list:
    return [t["key"] for t in ALLY_TECHNIQUES.get(character, [])]


def form_variants() -> list:
    """(character, tech_or_None, clip_group, clip_name) の一覧。

    アイテム・アタッチャブル・コントローラを回すときはこれを使う。
    """
    out = [(MAGNETO, None, None, None)]
    for key in TECH_ORDER:
        out.append((MAGNETO, key, "tech", TECHNIQUES[key]["clip"]))
    for c in BROTHERHOOD:
        out.append((c, None, None, None))
        for t in ALLY_TECHNIQUES.get(c, []):
            out.append((c, t["key"], "ally", t["clip"]))
    return out


#: 技アイテム + 変身体アイテム（技ごと）を足した、生成すべき全アイテム ID
def all_item_keys() -> list:
    keys = list(ITEMS)
    keys += [t["item"] for t in TECHNIQUES.values()]
    keys += [form_key(c, t) for c, t, _g, _n in form_variants()]
    return sorted(set(k for k in keys if k != "magneto_form")) + ["magneto_form"]


# ===========================================================================
#  5. アニメーション識別子
# ===========================================================================

ANIM_GROUPS = {
    # 全員共通
    "common": ["look_at_target"],
    # 人型 NPC の基礎
    "humanoid": ["idle", "walk", "run", "air", "attack", "hurt", "death",
                 "sneak"],
    # マグニートー専用（NPC / 変身体の両方で使う）
    "magneto": ["idle", "walk", "run", "air", "hover", "cape_idle", "cape_move",
                "levitate", "enthrone"],
    # 変身体（プレイヤー装着）のベース
    "form": ["idle", "walk", "run", "crouch", "air", "sprint", "swim"],
    # マグニートーの技
    "tech": [t["clip"] for t in TECHNIQUES.values()],
    # 一人称（技アイテムの attachable）
    "fp": ["idle", "third", "thrust", "pull", "grip", "lance", "storm",
           "guard", "crush", "raise", "pulse", "fly", "focus"],
    # ブラザーフッドの技
    "ally": [t["clip"] for lst in ALLY_TECHNIQUES.values() for t in lst],
    # センチネル
    "sentinel": ["idle", "walk", "beam", "stomp", "hurt", "death", "scan"],
    # 小物
    "prop": ["spin", "orbit", "pulse", "drift"],
}

def form_controller_name(character: str, tech: str | None) -> str:
    return f"form.{form_key(character, tech)}"


ANIM_CONTROLLERS = [
    "humanoid.general", "humanoid.action",
    "magneto.general", "magneto.action",
    "sentinel.general", "sentinel.action",
    "fp.tech", "cape", "prop.spin",
] + [form_controller_name(c, t) for c, t, _g, _n in form_variants()]

RENDER_CONTROLLERS = ["default", "glow", "phase", "hologram"]


# ===========================================================================
#  6. パーティクル
# ===========================================================================
#  VFX 担当が実体を作る。ここは「存在すべき名前」の台帳。
# ===========================================================================

PARTICLES = [
    # --- 磁力の基礎表現 ---
    "mag_field", "mag_pull", "mag_push", "mag_line", "mag_glyph", "mag_spark",
    "mag_aura", "mag_aura_max", "mag_ring", "mag_ring_wide", "mag_dust",
    # --- 金属 ---
    "shard_spark", "shard_trail", "shard_burst", "metal_glint", "metal_rip",
    "debris_chunk", "debris_dust", "rust_flake",
    # --- 技ごとの決め絵 ---
    "repulse_wave", "attract_funnel", "disarm_flash", "lance_streak",
    "lance_impact", "storm_swirl", "barrier_hex", "barrier_break",
    "bind_weld", "crush_implode", "crush_blood", "uprising_soil",
    "uprising_pillar", "emp_wave", "emp_arc", "polarity_field",
    "throne_dust", "sight_ping", "sphere_core", "sphere_orbit",
    "sphere_collapse", "sphere_detonate",
    # --- 移動・変身 ---
    "flight_trail", "flight_burst", "cape_wind", "transform_burst",
    "transform_ring", "revert_smoke", "levitate_dust",
    # --- ブラザーフッド ---
    "shift_shimmer", "venom_drip", "claw_slash", "roar_wave", "regen_knit",
    "tongue_slime", "leap_dust", "slime_splat", "quake_dust", "quake_crack",
    "rock_fall", "blur_after", "speed_line", "flame_wave", "flame_serpent",
    "ember_rise", "hex_wave", "hex_bolt_trail", "chaos_motes", "tk_lift",
    "slam_ring",
    # --- 敵 ---
    "sentinel_beam_charge", "sentinel_beam_trail", "sentinel_beam_impact",
    "sentinel_spark", "sentinel_smoke", "sentinel_scan", "core_break",
    "mrd_muzzle",
    # --- 汎用 ---
    "impact_dust", "heavy_land", "hurt_spark", "blood_red",
]


# ===========================================================================
#  7. テクスチャのスタイルキー
# ===========================================================================
#  モデル担当は Cube(style=...) にこの名前だけを渡す。
#  実際の色・パターンは palettes.py（テクスチャ担当）が決める。
# ===========================================================================

STYLE_KEYS = [
    # rig.HumanRig が既定で使うもの
    "base", "skin", "suit", "armor", "accent", "hair", "steel", "cloth",
    "underlay", "decal", "visor", "glow",
    # マグニートー
    "helm", "helm_dark", "helm_crest", "cape", "cape_inner", "plate",
    "plate_dark", "belt", "boot", "glove", "magnet",
    # ブラザーフッド
    "scale", "fur", "claw", "flame", "stone", "hex", "gut", "tongue",
    "goggle", "rune",
    # センチネル / MRD
    "robot", "robot_dark", "optic", "cable", "hazard",
    # 小物
    "shard", "rock", "energy",
]


# ===========================================================================
#  8. スクリプト側の定数（JS と一致させること）
# ===========================================================================

DYNAMIC_PROPS = {
    "mutant": f"{NS}:mutant",         # bool  ミュータント覚醒済みか
    "hero": f"{NS}:hero",             # str   選択中のキャラ key
    "form": f"{NS}:form",             # bool  変身中か
    "stage": f"{NS}:stage",           # int   1..3
    "mag": f"{NS}:mag",               # float 磁力ゲージ 0..100
    "mastery": f"{NS}:mastery",       # int   熟練度（撃破数）
    "tech": f"{NS}:tech",             # str   選択中の技 key
    "flying": f"{NS}:flying",         # bool  磁気飛行中
    "sight": f"{NS}:sight",           # int   磁力視の残り tick
    "barrier": f"{NS}:barrier",       # int   障壁の残り tick
    "stored": f"{NS}:stored_armor",   # str   変身前の防具
    "casting": f"{NS}:casting",       # str   いま姿勢を占有している技
}

TAGS = {
    "form": f"{NS}_form",             # 変身中のプレイヤー
    "ally": f"{NS}_ally",             # ブラザーフッドの仲間
    "hostile": f"{NS}_hostile",
    "bound": f"{NS}_bound",           # 鋼鉄拘束中
    "emp": f"{NS}_emp",               # EMP で沈黙中
}

FAMILIES = {
    "mutant": "mutant",
    "brotherhood": "brotherhood",
    "sentinel": "sentinel",
    "mrd": "mrd",
    "prop": "marvel_prop",
}

#: 磁力ゲージ
MAG_MAX = 100.0
MAG_REGEN = 3.0          # 毎秒
MAG_REGEN_STAGE3 = 6.0
MAG_DRAIN = 0.6          # 変身維持コスト / 秒

#: 段階の解禁条件（撃破数）。25 は現在の敵湧き密度では遠すぎたので 12/40 に。
STAGE_THRESHOLDS = [(0, 1), (12, 2), (40, 3)]

#: 磁力が効く素材。値は「磁化強度」— 引き寄せ・圧壊の効きに比例する。
MAGNETIC_BLOCKS = {
    "minecraft:iron_block": 1.0, "minecraft:iron_ore": 0.55,
    "minecraft:deepslate_iron_ore": 0.55, "minecraft:raw_iron_block": 0.85,
    "minecraft:iron_bars": 0.45, "minecraft:iron_door": 0.6,
    "minecraft:iron_trapdoor": 0.6, "minecraft:heavy_weighted_pressure_plate": 0.4,
    "minecraft:anvil": 1.2, "minecraft:chipped_anvil": 1.1,
    "minecraft:damaged_anvil": 1.0, "minecraft:chain": 0.35,
    "minecraft:rail": 0.3, "minecraft:golden_rail": 0.35,
    "minecraft:detector_rail": 0.35, "minecraft:activator_rail": 0.35,
    "minecraft:hopper": 0.7, "minecraft:cauldron": 0.6,
    "minecraft:gold_block": 0.7, "minecraft:gold_ore": 0.4,
    "minecraft:deepslate_gold_ore": 0.4, "minecraft:raw_gold_block": 0.6,
    "minecraft:copper_block": 0.8, "minecraft:copper_ore": 0.45,
    "minecraft:deepslate_copper_ore": 0.45, "minecraft:raw_copper_block": 0.7,
    "minecraft:cut_copper": 0.75, "minecraft:exposed_copper": 0.75,
    "minecraft:weathered_copper": 0.7, "minecraft:oxidized_copper": 0.65,
    "minecraft:lightning_rod": 0.5, "minecraft:netherite_block": 1.4,
    "minecraft:ancient_debris": 1.0, "minecraft:cauldron_block": 0.6,
    "minecraft:blast_furnace": 0.55, "minecraft:furnace": 0.3,
    "minecraft:iron_chain": 0.35, "minecraft:redstone_block": 0.5,
    "minecraft:redstone_ore": 0.3, "minecraft:crying_obsidian": 0.0,
}

#: 磁力が効く装備。数値は圧壊ダメージ倍率。
MAGNETIC_ITEMS = {
    "iron": 1.0, "gold": 0.8, "chainmail": 0.9, "netherite": 1.3,
    "copper": 0.85, "shield": 0.5,
}

#: アダマンチウムは磁力を受け付けない — 唯一の対抗手段。
IMMUNE_ITEMS = ["adamantium"]


# ===========================================================================
#  9. サウンド（バニラのイベント名を流用する）
# ===========================================================================

SOUNDS = {
    "transform": "mob.evocation_illager.prepare_attack",
    "transform_2": "beacon.activate",
    "revert": "beacon.deactivate",
    "mag_charge": "beacon.ambient",
    "mag_release": "mob.warden.sonic_boom",
    "repulse": "random.explode",
    "attract": "mob.shulker.teleport",
    "disarm": "random.break",
    "lance": "item.trident.throw",
    "shard": "random.bowhit",
    "barrier": "block.beacon.power_select",
    "barrier_hit": "random.anvil_land",
    "bind": "random.anvil_use",
    "crush": "random.anvil_land",
    "uprising": "mob.ravager.roar",
    "emp": "mob.warden.sonic_charge",
    "polarity": "portal.travel",
    "flight": "mob.enderdragon.flap",
    "sight": "mob.warden.heartbeat",
    "sphere_charge": "mob.warden.charge",
    "sphere_blast": "mob.warden.sonic_boom",
    "metal_hit": "random.anvil_land",
    "sentinel_step": "mob.ravager.step",
    "sentinel_beam": "mob.guardian.attack",
    "sentinel_die": "random.explode",
    "ui_select": "random.click",
    "ui_open": "random.orb",
}


# ===========================================================================
#  10. 出力先ヘルパ
# ===========================================================================

def geo_path(key: str) -> str:
    return os.path.join(GEO_DIR, f"{key}.geo.json")


def tex_path(key: str) -> str:
    return os.path.join(TEX_DIR, f"{key}.png")


def item_tex_path(key: str) -> str:
    return os.path.join(ITEM_TEX_DIR, f"{key}.png")


def ensure_dirs() -> None:
    for d in (GEO_DIR, TEX_DIR, ITEM_TEX_DIR, ANIM_DIR, CTRL_DIR, RENDER_DIR,
              PART_DIR, CLIENT_DIR, ATTACH_DIR, SCRIPT_DIR,
              os.path.join(BP, "entities"), os.path.join(BP, "items"),
              os.path.join(BP, "recipes"), os.path.join(BP, "spawn_rules"),
              os.path.join(BP, "loot_tables", "entities"),
              os.path.join(BP, "texts"), os.path.join(RP, "texts")):
        os.makedirs(d, exist_ok=True)
