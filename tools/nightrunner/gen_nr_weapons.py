# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 近接武器（nr_spec_catalog.WEAPONS の kind == "melee" の全部）を生成する。

武器ごとに（置き場所と形は nr_weapon_common の docstring）:
  RP  models/entity/weapons/<key>.geo.json      geometry.nr.w.<key>（1.16.0、hold(binding) → root）
  RP  textures/nr/weapons/<key>.png             写実寄りのテクスチャ（nr_paint ＋ 後処理: 陰・研いだ縁・欠け・血）
  RP  textures/nr/items/<key>.png               アイコン（3D モデルを斜めから描いて 64×64 の透過 PNG）
  RP  attachables/weapons/<key>.attachable.json identifier = nr:w_<key>
  RP  animations/weapons/<key>.animation.json   持ち方（三人称・一人称・構え）と待機（丸ノコの回転など）
  BP  items/weapons/<key>.item.json             1.21.120 のアイテム（nr:weapon で耐久をスクリプトに渡す）
  BP  recipes/weapons/<key>.recipe.json         spec に作業台レシピがあるものだけ
  断片 .frag/item_texture/gen_nr_weapons.json（nr_w_<key>）・.frag/lang/gen_nr_weapons.json（item.nr:w_<key>）

形は spec の model（部品・寸法・素材・作り込みの指示）をなぞり、武器 1 つを 60〜180 キューブで作る:
研いだ刃（峰・平の段・研いだ縁の 3 層。縁は後処理で磨いた銀の線と V 字の欠け）、テープ・布・革の巻き
（帯を少しずつ傾けて重ねる）、鋲・ボルト・ナット（六角）・溶接のビード・釘・針金、ぼろ布（端がほつれて抜ける）。
血は spec の blood 部品の範囲に武器空間の 3D ノイズで塗る（厚い塊・拭った跡・垂れ・飛沫・濡れた照り）。

使い方:
  python3 tools/nightrunner/gen_nr_weapons.py                 # 全部書く（build_nr.py --only weapons と同じ）
  python3 tools/nightrunner/gen_nr_weapons.py --only machete,cleaver --preview   # 一部だけ、確認画像も
  python3 tools/nightrunner/gen_nr_weapons.py --preview       # 全部 + build_preview/nightrunner/weapons_melee*.png
  （NR_PREVIEW=1 でも確認画像を描く）

確認画像（build_preview/nightrunner/）:
  weapons_melee.png        全近接武器の 3/4 と横（テクスチャ付き）
  weapons_melee_held.png   三人称でプレイヤーに持たせた姿（正面斜め・横・構え）。めり込み・左手の届きを数字で
  weapons_melee_fp.png     一人称の画面（持ち・構え）
  weapons_melee_icons.png  アイコン（等倍と 4 倍）
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import nr_paint as NP  # noqa: E402
import nr_weapon_common as WC  # noqa: E402
from nr_common import PREVIEW, SCRATCH  # noqa: E402
from nr_weapon_common import (band, beam, blade, bolt, box, cbox, coil, curved_blade, disc,  # noqa: E402,F401
                              fill_poly_yz, hex_prism, lash, nail, polyline, rag, ring_of, rivet, rod, teeth_row,
                              weld, wrap)

try:  # 登録データの入口（nr_spec が無い・作り直し中ならカタログを直接）
    import nr_spec as SPEC  # noqa: E402
    _WEAPONS = SPEC.WEAPONS
except Exception:  # noqa: BLE001
    import nr_spec_catalog as SPEC  # type: ignore  # noqa: E402
    _WEAPONS = SPEC.WEAPONS

PRODUCER = "gen_nr_weapons"
MELEE = [w for w in _WEAPONS if w["kind"] == "melee"]
BY_KEY = {w["key"]: w for w in MELEE}


@dataclass
class Built:
    """builder の戻り値。hold は WC.hold_for に渡す引数（grip / scale / pitch / fp / use ...）。"""
    wm: WC.WeaponModel
    book: WC.Stylebook
    blood: List[dict] = field(default_factory=list)
    hold: dict = field(default_factory=dict)
    icon_flip: bool = False
    icon_yaw: float = 72.0
    icon_roll: float = 0.0          # アイコンで武器を自分の軸まわりに回す（横に広がる爪・刃を見せる）


BUILDERS: Dict[str, Callable[[dict], Built]] = {}


def builder(key: str):
    def deco(fn):
        BUILDERS[key] = fn
        return fn
    return deco


def spec_blood(w, grow=0.45, scale=1.0, amount=None, **kw) -> List[dict]:
    """spec の blood 部品から血の範囲（amount を上書きできる）。"""
    zs = WC.blood_zones_from_spec(w, grow=grow)
    for z in zs:
        if amount is not None:
            z["amount"] = amount
        z.update(kw)
    return zs


def chips_on(cubes, chips):
    """研いだ縁のキューブ全部に同じ欠けの一覧を付ける（重なる所だけが抜ける）。"""
    for c in cubes:
        c.fx = dict(getattr(c, "fx", {}) or {})
        c.fx["chips"] = list(chips)


def add_fx(cubes, **fx):
    for c in cubes:
        c.fx = dict(getattr(c, "fx", {}) or {})
        c.fx.update(fx)


# ===========================================================================
#  片手の刃
# ===========================================================================
@builder("machete")
def b_machete(w) -> Built:
    wm = WC.WeaponModel("machete", uv=6)
    b = wm.root
    # ---- 柄: 全通しの中子（タング）を 2 枚の樹脂で挟む。中央が膨らみ、尻で少し広がる ----
    beam(b, (0, 0, 3.05), (0, 0, -2.25), 0.34, 1.62, "tang", uv=6)
    segs = [(-2.2, -0.9, 1.5, 0.0), (-0.9, 1.7, 1.74, -0.04), (1.7, 3.0, 1.64, 0.0)]
    for s in (-1, 1):
        for z0, z1, h, yo in segs:
            beam(b, (s * 0.41, yo, z1), (s * 0.41, yo, z0), 0.48, h, "scale", fx={"knurl": 0.34}, uv=7)
            beam(b, (s * 0.71, yo, z1 - 0.12), (s * 0.71, yo, z0 + 0.12), 0.14, h * 0.72, "scale",
                 fx={"knurl": 0.34}, uv=7)
        for z in (-1.4, 0.6, 2.2):
            rivet(b, (s * 0.78, -0.02, z), (s, 0, 0), d=0.44, h=0.1, style="rivet", uv=10)
    # 口金（指を守る小さな出っ張り付き）と尻金
    cbox(b, (0, 0, -2.42), (1.52, 2.0, 0.42), "bolster", uv=8)
    cbox(b, (0, -1.12, -2.48), (1.2, 0.5, 0.32), "bolster", uv=8)
    cbox(b, (0, -0.05, 3.32), (1.46, 1.86, 0.6), "bolster", uv=8)
    cbox(b, (0, -0.05, 3.72), (1.2, 1.5, 0.26), "bolster", uv=8)
    wm.cut((0, -0.42, 3.36), (1, 0, 0), r=0.24, half=1.2)
    # 尻金の穴から垂れるパラコードの輪（2 本の撚りと結び目）
    for s in (-1, 1):
        polyline(b, [(s * 0.17, -0.45, 3.4), (s * 0.28, -1.35, 4.0), (s * 0.22, -2.35, 4.4), (s * 0.06, -3.05, 4.25)],
                 0.26, 0.26, "cord", overlap=0.18, uv=10)
    cbox(b, (0, -3.15, 4.2), (0.5, 0.42, 0.46), "cord", rot=(20, 15, 0), uv=10)
    beam(b, (0.05, -3.3, 4.15), (0.15, -3.95, 4.0), 0.22, 0.22, "cord", uv=10)
    beam(b, (-0.08, -3.3, 4.3), (-0.2, -3.8, 4.55), 0.22, 0.22, "cord", uv=10)
    # 柄の割れを留めた補修テープ（巻き終わりが少しめくれる）
    wrap(b, (0, -0.02, -2.08), (0, -0.02, -0.82), (1.72, 1.88), "tape", pitch=0.42, tilt=9, seed=1, uv=9,
         tail=(0.55, (0.3, -1.0, 0.25)))
    # ---- 刃: 根元 2.2 → 腹 2.6 と膨らみ、峰を斜めに落とした切っ先。刃は 3 か所欠ける ----
    prof = [(-2.6, 1.0, -1.12), (-4.0, 1.02, -1.18), (-5.6, 1.04, -1.27), (-7.2, 1.05, -1.4),
            (-8.6, 1.05, -1.55), (-9.9, 1.03, -1.66), (-11.0, 0.98, -1.68), (-11.9, 0.88, -1.56),
            (-12.6, 0.62, -1.28), (-13.15, 0.28, -0.86), (-13.55, -0.12, -0.42), (-13.75, -0.3, -0.34)]
    bl = blade(b, prof, "blade", "edge", "spine", t_body=0.34, t_edge=0.14, t_spine=0.42, bevel=0.55,
               spine_h=0.26, uv=7, edge_uv=10)
    chips_on(bl["edge"], [(-6.2, 0.32, 0.3), (-9.05, 0.24, 0.22), (-11.3, 0.4, 0.34)])
    # 打刻（根元の平に、架空の銘）と研ぎの段
    add_fx(bl["body"], world=WC.stamp("NR-7", (-4.1, 0.25), 0.42, mul=0.62))
    book = WC.Stylebook(w["palette"])
    book.add("tang", "steel_dark", base=(64, 66, 70))
    book.add("scale", "plastic_black", base=book.pal(2), wear=0.5, dirt=0.45)
    book.add("rivet", "brass", wear=0.8)
    book.add("bolster", "steel_dark", wear=0.9, dirt=0.4)
    book.add("cord", "paracord", base=book.pal(3))
    book.add("tape", "tape_grey", dirt=0.6)
    book.add("blade", "steel_worn", base=book.pal(0), scratches=0.85, dirt=0.25)
    book.add("edge", "steel_clean", base=book.pal(1))
    book.add("spine", "steel_rusty", amount=0.65, metal=book.pal(0))
    blood = spec_blood(w, amount=0.48) + [WC.blood_zone((-0.5, -1.9, -13.8), (0.5, -0.6, -10.5), 0.42, "wet")]
    return Built(wm, book, blood, hold=dict(pitch=36.0))


def scaled_handle(b, segs, scale_style, tang_style, *, rivets=(), rivet_style="rivet", knurl=None, tang_w=0.34,
                  scale_t=0.48, bulge=True, uv=7, rivet_d=0.44):
    """全通しの中子を 2 枚の板（樹脂・木）で挟んだ柄。segs = [(z0, z1, 高さ, y のずれ), ...]（柄尻へ順に）。
    両面に鋲。bulge なら板の外側にもう一枚の細い板を重ねて丸みを出す。"""
    z_lo = min(min(sg[0], sg[1]) for sg in segs)
    z_hi = max(max(sg[0], sg[1]) for sg in segs)
    hmax = max(sg[2] for sg in segs)
    beam(b, (0, 0, z_hi + 0.05), (0, 0, z_lo - 0.05), tang_w, hmax - 0.1, tang_style, uv=uv)
    fx = {"knurl": knurl} if knurl else None
    xo = tang_w / 2 + scale_t / 2
    for s_ in (-1, 1):
        for z0, z1, h, yo in segs:
            beam(b, (s_ * xo, yo, z1), (s_ * xo, yo, z0), scale_t, h, scale_style, fx=fx, uv=uv)
            if bulge:
                beam(b, (s_ * (xo + scale_t / 2 + 0.06), yo, z1 - 0.12), (s_ * (xo + scale_t / 2 + 0.06), yo, z0 + 0.12),
                     0.14, h * 0.72, scale_style, fx=fx, uv=uv)
        for z in rivets:
            rivet(b, (s_ * (xo + scale_t / 2 + (0.13 if bulge else 0.0)), -0.02, z), (s_, 0, 0), d=rivet_d, h=0.1,
                  style=rivet_style, uv=10)


@builder("cleaver")
def b_cleaver(w) -> Built:
    wm = WC.WeaponModel("cleaver", uv=6)
    b = wm.root
    scaled_handle(b, [(-2.0, -0.6, 1.42, 0.0), (-0.6, 1.6, 1.56, -0.03), (1.6, 2.8, 1.72, -0.07)], "wood", "tang",
                  rivets=(-1.0, 0.6, 2.2), rivet_style="rivet", tang_w=0.36, scale_t=0.46)
    cbox(b, (0, -0.02, -2.08), (1.38, 1.5, 0.26), "tang", uv=8)
    beam(b, (0, 0.06, -1.95), (0, 0.42, -2.95), 0.42, 1.18, "tang", uv=8)          # 中子の首
    prof = [(-2.75, 0.92, -2.85), (-4.0, 0.93, -3.05), (-5.5, 0.93, -3.15), (-7.0, 0.92, -3.18),
            (-8.5, 0.9, -3.15), (-9.55, 0.87, -3.05), (-10.05, 0.8, -2.8)]
    bl = blade(b, prof, "blade", "edge", "spine", t_body=0.46, t_edge=0.16, t_spine=0.5, bevel=0.72,
               spine_h=0.3, uv=7, edge_uv=10, grind=0.55)
    chips_on(bl["edge"], [(-7.6, 0.5, 0.42), (-4.4, 0.16, 0.14)])
    wm.cut((0, 0.25, -9.0), (1, 0, 0), r=0.4, half=1.0, rim=0.16)
    dents = [(-4.6, -0.6), (-6.2, 0.1), (-7.9, -1.2), (-5.3, -1.9), (-8.8, -0.4), (-3.6, -1.5)]
    add_fx(bl["body"], world=WC.compose(WC.stamp("NR-CO", (-4.3, 0.15), 0.5, mul=0.6),
                                        WC.spots(dents, 0.18, mul=0.86, ring=0.1, ring_mul=1.12)))
    book = WC.Stylebook(w["palette"])
    book.add("wood", "wood_dark", base=book.pal(2), dirt=0.55)
    book.add("tang", "steel_worn", base=(120, 122, 124), dirt=0.45)
    book.add("rivet", "steel_worn", base=(170, 172, 170), wear=0.9)
    book.add("blade", "steel_worn", base=book.pal(0), scratches=0.6, dirt=0.3)
    book.add("edge", "steel_clean", base=book.pal(1))
    book.add("spine", "steel_rusty", amount=0.75, metal=book.pal(0))
    blood = spec_blood(w, amount=0.55, grow=0.25)
    return Built(wm, book, blood, hold=dict(pitch=30.0))


@builder("kukri")
def b_kukri(w) -> Built:
    wm = WC.WeaponModel("kukri", uv=6)
    b = wm.root
    # 柄: 中央が膨らむ木の柄、真鍮の輪 2 本、真鍮の尻金と中子の留めナット
    rod(b, (0, 0, -2.05), (0, 0, -0.55), 1.36, "wood", uv=7)
    rod(b, (0, -0.03, -0.6), (0, -0.03, 1.25), 1.62, "wood", uv=7)
    rod(b, (0, -0.02, 1.2), (0, -0.02, 2.6), 1.48, "wood", uv=7)
    for z in (-1.6, 0.6):
        band(b, (0, -0.02, z), (0, 0, 1), 1.72, 0.36, "brass", uv=9)
    rod(b, (0, -0.02, 2.55), (0, -0.02, 3.15), 1.62, "brass", uv=9)
    disc(b, (0, -0.02, 3.22), (0, 0, 1), 0.36, 0.16, "brass", n=2, star=0.86, uv=10)
    cbox(b, (0, 0, -2.2), (1.2, 1.6, 0.36), "brass", uv=9)
    prof = [(-2.3, 0.72, -0.72), (-3.4, 0.92, -0.7), (-4.8, 1.18, -0.78), (-6.2, 1.38, -0.95), (-7.4, 1.32, -1.18),
            (-8.4, 1.0, -1.45), (-9.3, 0.45, -1.72), (-10.1, -0.25, -1.9), (-10.7, -0.9, -1.92),
            (-11.15, -1.45, -1.82), (-11.45, -1.74, -1.78)]
    bl = blade(b, prof, "blade", "edge", "spine", t_body=0.38, t_edge=0.15, t_spine=0.5, bevel=0.5, spine_h=0.3,
               uv=8, edge_uv=10)
    wm.cut((0, -0.72, -2.85), (1, 0, 0), r=0.3, half=1.0, rim=0.1)      # チョー（刃元の切り欠き）
    chips_on(bl["edge"], [(-8.9, 0.2, 0.18)])
    add_fx(bl["body"] + bl["spine"], world=WC.groove(prof, 0.66, 0.8, -3.0, -8.6, dark=0.6))
    # 割れた柄をテープで補修、尻金の穴にパラコードの輪、刃に貼り付いた髪
    add_fx(wm.cubes[:6], world=WC.crack((0.0, 0.8, 2.2), (0.0, 0.8, -0.5), width=0.05, seed=31, wiggle=0.12,
                                        normal=(0, 1, 0)))
    wrap(b, (0, -0.02, 1.3), (0, -0.02, 2.4), 1.58, "tape", pitch=0.5, tilt=9, seed=32, uv=9,
         tail=(0.5, (0.3, -1.0, 0.2)))
    wm.cut((0, -0.45, 2.85), (1, 0, 0), r=0.18, half=1.0, rim=0.1)
    for s_ in (-1, 1):
        polyline(b, [(s_ * 0.82, -0.45, 2.85), (s_ * 0.9, -1.3, 3.2), (s_ * 0.3, -2.3, 3.5)], 0.17, 0.17, "cord",
                 overlap=0.08, uv=12)
    cbox(b, (0, -2.42, 3.52), (0.5, 0.4, 0.4), "cord", rot=(0, 20, 0), uv=12)
    polyline(b, [(0.1, -2.6, 3.55), (0.25, -3.3, 3.8), (0.15, -3.8, 3.7)], 0.17, 0.17, "cord", overlap=0.06, uv=12)
    hairs(b, 0.19, (-0.4, -8.6), 2, 1.3, "hair", seed=33, side=1)
    book = WC.Stylebook(w["palette"])
    book.add("wood", "wood_dark", base=book.pal(2), dirt=0.45, grain=1.6)
    book.add("brass", "brass", wear=0.85)
    book.add("blade", "steel_worn", base=book.pal(0), scratches=0.7, dirt=0.25)
    book.add("edge", "steel_clean", base=book.pal(1))
    book.add("spine", "steel_worn", base=(112, 114, 116), scratches=0.4, dirt=0.4)
    book.add("tape", "tape_black", base=book.pal(3), dirt=0.5)
    book.add("cord", "paracord", base=(96, 86, 62))
    book.raw("hair", NP.style("hair", base=(30, 24, 20), style="matted"))
    blood = spec_blood(w, amount=0.46)
    return Built(wm, book, blood, hold=dict(pitch=34.0))


@builder("combat_knife")
def b_combat_knife(w) -> Built:
    wm = WC.WeaponModel("combat_knife", uv=7)
    b = wm.root
    # 柄: 角を落とした四角いゴム、輪の刻み 6 本、指の掛かりの凹凸
    WC.rbeam(b, (0, 0, 2.5), (0, 0, -1.9), 1.2, 1.5, "rubber", k=0.76, fx={"ribs": 0.72}, uv=8)
    for i, z in enumerate((-1.2, 0.0, 1.2)):
        cbox(b, (0, -0.72, z), (1.0, 0.24, 0.55), "rubber", uv=8)
    # 鍔（下へ長い十字）と尻（ガラス割りの尖り・紐穴）
    cbox(b, (0, -0.32, -2.12), (0.56, 2.7, 0.46), "guard", uv=9)
    cbox(b, (0, -1.6, -2.18), (0.7, 0.36, 0.58), "guard", uv=9)
    cbox(b, (0, 0.95, -2.12), (0.7, 0.3, 0.5), "guard", uv=9)
    cbox(b, (0, 0, 2.82), (1.32, 1.62, 0.66), "guard", uv=9)
    cbox(b, (0, 0, 3.32), (0.7, 0.7, 0.7), "guard", rot=(45, 0, 0), uv=10)
    cbox(b, (0, 0, 3.32), (0.7, 0.7, 0.7), "guard", rot=(0, 45, 0), uv=10)
    wm.cut((0, -0.38, 2.82), (1, 0, 0), r=0.2, half=1.0)
    # 根元のパラコード巻き
    wrap(b, (0, 0, -1.75), (0, 0, -0.75), (1.36, 1.66), "cord", pitch=0.34, tilt=12, seed=3, uv=10)
    # 刃: 黒染めのクリップポイント、峰の鋸刃、銀に研ぎ出した刃
    prof = [(-2.35, 0.74, -0.72), (-3.5, 0.76, -0.76), (-5.0, 0.77, -0.79), (-6.3, 0.76, -0.77),
            (-7.0, 0.56, -0.69), (-7.7, 0.33, -0.5), (-8.3, 0.14, -0.22), (-8.7, 0.04, -0.02)]
    bl = blade(b, prof, "blade", "edge", "spine", t_body=0.3, t_edge=0.13, t_spine=0.34, bevel=0.42, spine_h=0.22,
               uv=9, edge_uv=11)
    teeth_row(b, (0, 0.8, -2.55), (0, 0.8, -4.75), 6, (0.3, 0.34, 0.34), "serr", uv=10)
    add_fx(bl["body"], world=WC.compose(WC.stamp("NR", (-3.6, 0.1), 0.36, mul=1.0, tint=(150, 152, 150)),
                                        WC.groove(prof, 0.6, 0.72, -2.9, -6.4, dark=0.7)))
    # 尻の紐穴にパラコードの輪（コードロック）、柄の中ほどにテープ、鍔に結んだ布切れ、刃に髪
    for s_ in (-1, 1):
        polyline(b, [(s_ * 0.68, -0.38, 2.82), (s_ * 0.8, -1.25, 3.3), (s_ * 0.28, -2.3, 3.55)], 0.16, 0.16, "cord",
                 overlap=0.08, uv=12)
    cbox(b, (0, -2.42, 3.58), (0.5, 0.42, 0.36), "lock", uv=12)
    beam(b, (0.1, -2.6, 3.6), (0.2, -3.25, 3.78), 0.16, 0.16, "cord", uv=12)
    wrap(b, (0, 0, 0.4), (0, 0, 1.5), (1.34, 1.64), "tape", pitch=0.55, tilt=-8, seed=34, uv=9)
    rag(b, (0, -1.75, -2.2), 1.6, 0.6, "rag", hang=(0.1, -1.0, 0.5), strips=2, spread=0.3, seed=35)
    hairs(b, 0.16, (0.0, -6.0), 2, 1.2, "hair", seed=36, side=1)
    book = WC.Stylebook(w["palette"])
    book.add("rubber", "rubber_black", base=book.pal(2), dirt=0.35)
    book.add("guard", "steel_dark", base=(52, 54, 58), wear=0.9, dirt=0.25)
    book.add("cord", "paracord", base=book.pal(3))
    book.add("blade", "steel_dark", base=book.pal(0), dirt=0.2)
    book.add("edge", "steel_clean", base=book.pal(1))
    book.add("spine", "steel_dark", base=(46, 48, 52), wear=0.95)
    book.add("serr", "steel_worn", base=(150, 152, 154), wear=0.7)
    book.add("lock", "plastic_black", base=(36, 36, 40))
    book.add("tape", "tape_grey", base=(124, 124, 120), dirt=0.6)
    book.add("rag", "cloth_rag", base=(118, 112, 88), dirt=0.7)
    book.raw("hair", NP.style("hair", base=(48, 34, 24), style="matted"))
    blood = [WC.blood_zone((-0.4, -0.9, -8.9), (0.4, 0.4, -6.4), 0.5, "wet", soft=0.9),
             WC.blood_zone((-0.4, -0.9, -6.4), (0.4, -0.3, -3.6), 0.3, "dry", soft=1.0)]
    return Built(wm, book, blood, hold=dict(pitch=30.0))


@builder("scrap_katana")
def b_scrap_katana(w) -> Built:
    wm = WC.WeaponModel("scrap_katana", uv=6)
    b = wm.root

    def tsukamaki(P, N, L, size, col):
        # 菱巻き: 交差する赤い組紐、菱の窓から白い鮫皮が見える
        z = P[:, 2]
        aside = np.where(np.abs(N[:, 0]) > 0.5, P[:, 1], P[:, 0])
        g1 = ((z + aside * 1.1) / 1.1) % 1.0
        g2 = ((z - aside * 1.1) / 1.1) % 1.0
        win = (np.abs(g1 - 0.5) < 0.17) & (np.abs(g2 - 0.5) < 0.17)
        edge_ = ((np.abs(g1 - 0.5) < 0.22) & (np.abs(g2 - 0.5) < 0.22)) & ~win
        cross = (np.abs(g1 - 0.0) < 0.05) | (np.abs(g2 - 0.0) < 0.05)
        same = np.array([206, 200, 182], np.float32) * (0.9 + 0.1 * (col.mean(1, keepdims=True) / 140.0))
        col = np.where(win[:, None], same, col)
        col = np.where(edge_[:, None], col * 0.45, col)
        return np.where(cross[:, None], col * 0.7, col)
    WC.rbeam(b, (0, 0, 4.5), (0, 0, -2.1), 1.3, 1.6, "tsuka", k=0.8, fx={"world": tsukamaki}, uv=9)
    # 巻きの結び目の盛り上がり（両面に並ぶ）
    for s_ in (-1, 1):
        for i, z in enumerate(np.arange(-1.55, 3.6, 1.1)):
            cbox(b, (s_ * 0.67, 0.0, float(z)), (0.12, 0.42, 0.42), "tsuka", rot=(45, 0, 0), uv=9)
    wrap(b, (0, 0, 3.55), (0, 0, 4.6), (1.42, 1.72), "tape", pitch=0.35, tilt=10, seed=5, uv=10)
    cbox(b, (0, 0, 4.72), (1.2, 1.5, 0.3), "tsuba", uv=8)
    # 鍔: 丸ノコの刃を切って作った（外周に歯）
    tsuba = cbox(b, (0, 0, -2.42), (3.6, 3.6, 0.42), "tsuba", uv=9)
    tsuba.fx = {"sdf": lambda Lr, size: WC.sdf_circle(Lr, size, axes=(0, 1), teeth=14, tooth_h=0.32, hole=0.0)}
    cbox(b, (0, 0, -2.42), (1.6, 1.9, 0.62), "tsuba", uv=9)                                   # 切羽
    # はばき（銅線を巻く）
    cbox(b, (0, 0.08, -2.98), (0.56, 1.6, 0.8), "brass", uv=10)
    coil(b, (0, 0.08, -3.0), (0, 0, 1), 1.0, 0.7, 3, "copper", wire=0.12, uv=12)
    # 刃: 反り。中心線を上へ曲げ、切っ先は刃の線が峰へ回り込む
    pts = [(-3.35, 0.1, 1.5), (-6.0, 0.15, 1.5), (-9.0, 0.3, 1.46), (-12.0, 0.55, 1.4), (-15.0, 0.9, 1.3),
           (-17.5, 1.3, 1.2), (-19.5, 1.66, 1.1)]
    prof = [(z, yc + h / 2, yc - h / 2) for z, yc, h in pts]
    prof += [(-20.4, 2.17, 1.45), (-20.95, 2.07, 1.86), (-21.25, 1.97, 1.96)]
    bl = blade(b, prof, "blade", "edge", "spine", t_body=0.36, t_edge=0.14, t_spine=0.42, bevel=0.45, spine_h=0.24,
               uv=8, edge_uv=10)
    spf, edf = WC.prof_fns(prof)
    holes = [(-5.0, 0.3), (-9.0, 0.6)]
    add_fx(bl["body"] + bl["edge"], world=WC.compose(WC.hamon(edf, offset=0.32, amp=0.09, period=1.4, width=0.07),
                                                     WC.spots(holes, 0.22, mul=0.55, ring=0.14, ring_mul=1.3)))
    # 目釘（柄を貫く鋲 2 本）と、柄頭に結んだ下緒の切れ端
    for z in (-0.95, 2.3):
        for s_ in (-1, 1):
            rivet(b, (s_ * 0.66, 0.42, z), (s_, 0, 0), d=0.32, h=0.08, style="brass", uv=12)
    cbox(b, (0, -0.86, 4.7), (0.62, 0.5, 0.5), "sageo", rot=(0, 25, 0), uv=12)
    rag(b, (0, -0.95, 4.7), 2.2, 0.48, "sageo", hang=(0.12, -1.0, 0.45), strips=2, spread=0.26, seed=37)
    book = WC.Stylebook(w["palette"])
    book.add("tsuka", "cloth_red", base=book.pal(3), dirt=0.5)
    book.add("tape", "tape_black", base=book.pal(2))
    book.add("tsuba", "steel_rusty", amount=0.75, metal=(96, 96, 98))
    book.add("brass", "brass", wear=0.8)
    book.add("copper", "copper_wire", wear=0.6)
    book.add("blade", "steel_worn", base=book.pal(0), scratches=0.55, dirt=0.15)
    book.add("edge", "steel_clean", base=book.pal(1))
    book.add("spine", "steel_worn", base=(126, 128, 130), dirt=0.3)
    book.add("sageo", "cloth_red", base=(96, 22, 18), dirt=0.6)
    blood = spec_blood(w, amount=0.46, drip=1.4) + \
        [WC.blood_zone((-0.4, 0.8, -21.4), (0.4, 2.2, -19.0), 0.5, "wet", soft=0.8)]
    return Built(wm, book, blood, hold=dict(pitch=40.0, scale=0.92))


def axe_head(b, *, top, edge_y, z_top, z_edge, belly, thick_top, thick_edge, body="axe", edge="edge", uv=8,
             strip=0.42):
    """斧の刃（-Y へ張り出す扇）。top: 付け根の y、edge_y: 刃の線の両端の y、z_top / z_edge: (前, 後) の z、
    belly: 刃の中央が膨らむ量。刃の線（円弧）に研いだ縁を沿わせる。戻り値 (板, 縁)。"""
    za, zb = z_top
    ea, eb = z_edge
    n = 6
    arc = []
    for i in range(n + 1):
        t = i / n
        z = ea + (eb - ea) * t
        y = edge_y - belly * math.sin(math.pi * t)
        arc.append((y, z))
    poly = [(top, za), (top, zb)] + [(y, z) for y, z in reversed(arc)]
    y_low = min(y for y, _ in arc)
    plates = fill_poly_yz(b, poly, body, thick=lambda yz: WC.lerp(thick_top, thick_edge,
                                                                     np.clip((top - yz[0]) / (top - y_low), 0, 1)),
                          strip=strip, uv=uv, bt=(y_low, top))
    edges = []
    for i in range(n):
        (y0, z0), (y1, z1) = arc[i], arc[i + 1]
        c = beam(b, (0, y0 + 0.24, z0), (0, y1 + 0.24, z1), thick_edge * 0.55, 0.5, edge, up=(0, 1, 0), extend=0.12,
                 uv=uv + 2, tags=("edge",))
        c.bt = (0.0, 0.5 / (top - y_low))
        edges.append(c)
    return plates, edges


@builder("hatchet")
def b_hatchet(w) -> Built:
    wm = WC.WeaponModel("hatchet", uv=6)
    b = wm.root
    WC.rbeam(b, (0, 0, 2.5), (0, 0, -10.15), 1.2, 1.5, "handle", k=0.8, uv=6)
    WC.rbeam(b, (0, 0, 2.2), (0, 0, -1.8), 1.32, 1.62, "grip", k=0.8, fx={"ribs": 0.5}, uv=8)
    WC.rbeam(b, (0, -0.06, 2.95), (0, -0.06, 2.2), 1.5, 1.85, "grip", k=0.8, uv=8)
    cbox(b, (0, -0.4, -10.2), (1.26, 0.22, 0.32), "wedge", uv=10)
    # 頭: 赤く塗った胴（目の周り）、-Y の扇形の刃、+Y の先細りのピック
    cbox(b, (0, -0.4, -8.6), (1.42, 3.0, 2.4), "head", uv=8)
    cbox(b, (0, -0.4, -8.6), (1.62, 2.4, 1.9), "head", uv=8)
    plates, edges = axe_head(b, top=-1.75, edge_y=-4.45, z_top=(-9.65, -7.55), z_edge=(-10.45, -6.75), belly=0.4,
                             thick_top=1.0, thick_edge=0.34)
    chips_on(edges, [(-9.6, 0.22, 0.2), (-7.3, 0.3, 0.26)])
    polyline(b, [(0, 1.0, -8.6), (0, 2.3, -8.5), (0, 3.4, -8.25)], [0.82, 0.62], [0.9, 0.7], "head", uv=8)
    polyline(b, [(0, 3.3, -8.27), (0, 4.0, -8.0), (0, 4.4, -7.75)], [0.46, 0.26], [0.5, 0.3], "pick", uv=10)
    for s_ in (-1, 1):
        rivet(b, (s_ * 0.81, 0.0, -8.6), (s_, 0, 0), d=0.36, h=0.08, style="wedge", uv=10)
    hairs(b, 0.5, (-3.4, -8.6), 4, 1.6, "hair", seed=6, side=1)
    hairs(b, -0.5, (-3.0, -8.9), 3, 1.4, "hair", seed=7, side=-1)
    # 柄の割れを針金とテープで補修、柄尻の穴に革紐
    add_fx(wm.cubes[:2], world=WC.crack((0.6, 0.15, -2.4), (0.6, -0.2, -6.2), width=0.05, seed=39, wiggle=0.14,
                                        normal=(1, 0, 0)))
    coil(b, (0, 0, -5.3), (0, 0, 1), 1.36, 0.8, 2, "wire", wire=0.12, uv=12)
    wrap(b, (0, 0, -3.0), (0, 0, -4.2), (1.3, 1.6), "tape", pitch=0.6, tilt=8, seed=38, uv=9,
         tail=(0.5, (0.3, -1.0, 0.1)))
    wm.cut((0, -0.06, 2.6), (1, 0, 0), r=0.22, half=1.2, rim=0.1)
    for s_ in (-1, 1):
        polyline(b, [(s_ * 0.77, -0.06, 2.6), (s_ * 0.86, -0.9, 3.0), (s_ * 0.3, -1.9, 3.3)], 0.22, 0.12, "strap",
                 overlap=0.08, uv=12)
    cbox(b, (0, -2.0, 3.32), (0.56, 0.36, 0.36), "strap", uv=12)
    book = WC.Stylebook(w["palette"])
    book.add("handle", "wood_painted", base=book.pal(0), wear=0.5)
    book.add("grip", "rubber_black", base=book.pal(2), dirt=0.4)
    book.add("head", "steel_painted", base=(158, 36, 28), wear=0.45, rust=0.35)
    book.add("axe", "steel_worn", base=book.pal(1), scratches=0.7, dirt=0.3)
    book.add("edge", "steel_clean", base=book.pal(3))
    book.add("pick", "steel_clean", base=(170, 174, 178))
    book.add("wedge", "steel_dark", wear=0.9)
    book.add("wire", "steel_worn", base=(136, 134, 128), dirt=0.45)
    book.add("tape", "tape_grey", dirt=0.6)
    book.add("strap", "leather_brown", base=(80, 52, 32))
    book.raw("hair", NP.style("hair", base=(34, 26, 20), style="matted"))
    blood = spec_blood(w, amount=0.52) + [WC.blood_zone((-0.4, 3.6, -8.6), (0.4, 4.5, -7.6), 0.45, "dry", soft=0.5)]
    return Built(wm, book, blood, hold=dict(pitch=26.0), icon_flip=False)


hairs = WC.hairs


@builder("sickle")
def b_sickle(w) -> Built:
    wm = WC.WeaponModel("sickle", uv=6)
    b = wm.root
    rod(b, (0, 0, 3.3), (0, 0, -2.1), 1.42, "handle", uv=7)
    rod(b, (0, -0.02, 3.3), (0, -0.02, 3.62), 1.2, "handle", uv=7)
    for z in (-1.6, 2.6):
        coil(b, (0, 0, z), (0, 0, 1), 1.52, 0.62, 3, "wire", wire=0.13, uv=12)
    band(b, (0, 0, -2.42), (0, 0, 1), 1.56, 0.8, "ferrule", uv=8)
    bolt(b, (0, 0, -2.42), (1, 0, 0), 1.9, 0.18, "wire", nut_size=0.36, uv=10)
    # 柄尻の革の吊り紐
    polyline(b, [(0, 0.3, 3.6), (0, 0.9, 4.3), (0, 0.4, 5.0), (0, -0.4, 4.6), (0, -0.3, 3.7)], 0.18, 0.4, "strap",
             overlap=0.1, uv=10)
    # 刃: 根元はまっすぐ、上へ回り込んで手前へ返る三日月。刃は内側（中心の側）
    pts = [(0, 0.35, -2.7), (0, 0.38, -4.6), (0, 0.6, -5.9), (0, 1.2, -6.95), (0, 2.1, -7.7), (0, 3.15, -8.05),
           (0, 4.15, -7.85), (0, 4.95, -7.25), (0, 5.45, -6.4), (0, 5.62, -5.55), (0, 5.6, -4.9)]
    widths = [0.95, 0.98, 0.98, 0.95, 0.92, 0.88, 0.8, 0.7, 0.55, 0.36, 0.15]
    cb = curved_blade(b, pts, widths, "blade", "edge", edge_side=1, t_body=0.3, t_edge=0.16, bevel=0.38, uv=8,
                      edge_uv=10)
    chips_on(cb["edge"], [(-7.9, 0.25, 0.16)])
    book = WC.Stylebook(w["palette"])
    book.add("handle", "wood_old", base=book.pal(2), dirt=0.55, grain=1.8)
    book.add("wire", "steel_worn", base=(150, 150, 146), wear=0.6, dirt=0.4)
    book.add("ferrule", "steel_rusty", amount=0.9)
    book.add("strap", "leather_brown", base=(84, 54, 34))
    book.add("blade", "steel_rusty", amount=0.62, metal=book.pal(1))
    book.add("edge", "steel_worn", base=(176, 178, 176), scratches=0.9, dirt=0.15)
    blood = spec_blood(w, amount=0.46, grow=0.6)
    return Built(wm, book, blood, hold=dict(pitch=10.0, roll=0.0))


# ===========================================================================
#  両手の刃
# ===========================================================================
@builder("fire_axe")
def b_fire_axe(w) -> Built:
    wm = WC.WeaponModel("fire_axe", uv=5)
    b = wm.root
    haft = WC.rbeam(b, (0, 0, 4.45), (0, 0, -17.4), 1.5, 1.7, "haft", k=0.8, uv=5)
    add_fx(haft, world=WC.stamp("FIRE", (-7.6, 0.0), 0.95, mul=1.0, tint=(232, 228, 214)))
    for z in (-12.0, -3.0):
        WC.rbeam(b, (0, 0, z + 0.4), (0, 0, z - 0.4), 1.62, 1.82, "band", k=0.8, uv=7)
    WC.rbeam(b, (0, 0, 4.4), (0, 0, 0.4), 1.64, 1.84, "grip", k=0.8, fx={"ribs": 0.55}, uv=7)
    WC.rbeam(b, (0, 0, 5.25), (0, 0, 4.35), 1.92, 2.12, "grip", k=0.76, uv=7)
    # 頭: 赤い胴（目の周りの膨らみ）、-Y へ広がる扇形の刃、+Y の尖ったピック
    cbox(b, (0, -0.2, -17.2), (1.82, 3.6, 3.0), "head", uv=7)
    cbox(b, (0, -0.2, -17.2), (2.05, 2.6, 2.3), "head", uv=7)
    plates, edges = axe_head(b, top=-1.9, edge_y=-5.95, z_top=(-18.55, -15.85), z_edge=(-19.75, -14.65),
                             belly=0.42, thick_top=1.35, thick_edge=0.42, uv=7, strip=0.5)
    chips_on(edges, [(-18.9, 0.22, 0.2), (-16.6, 0.3, 0.28), (-15.3, 0.16, 0.14)])
    polyline(b, [(0, 1.5, -17.2), (0, 3.2, -17.05), (0, 4.9, -16.75)], [1.05, 0.82], [1.2, 0.95], "head", uv=7)
    polyline(b, [(0, 4.8, -16.77), (0, 5.9, -16.45), (0, 6.75, -16.1)], [0.62, 0.34], [0.72, 0.38], "pick", uv=9)
    for s_ in (-1, 1):
        rivet(b, (s_ * 1.03, 0.4, -17.2), (s_, 0, 0), d=0.42, h=0.1, style="pin", uv=10)
    hairs(b, 0.62, (-4.4, -17.0), 4, 1.8, "hair", seed=11, side=1)
    # 頭の付け根を針金で締め、ホースバンドで補強。目の反対側に楔代わりの釘
    coil(b, (0, 0, -14.75), (0, 0, 1), 1.68, 1.0, 3, "wire", wire=0.12, uv=12)
    hose_clamp(b, -13.4, (1.66, 1.86), "clamp", side=1)
    for x, y in ((0.32, 0.5), (-0.3, -0.75)):
        nail(b, (x, y, -18.84), (x, y, -17.8), "nail", d=0.18, head=0.42, uv=12)
    book = WC.Stylebook(w["palette"])
    book.add("haft", "wood_painted", base=book.pal(0), wear=0.42)
    book.add("band", "plastic_yellow", base=book.pal(1), wear=0.6, dirt=0.5)
    book.add("grip", "rubber_black", dirt=0.45)
    book.add("head", "steel_painted", base=(170, 38, 28), wear=0.45, rust=0.35)
    book.add("axe", "steel_worn", base=book.pal(2), scratches=0.75, dirt=0.3)
    book.add("edge", "steel_clean", base=book.pal(3))
    book.add("pick", "steel_clean", base=(176, 180, 184))
    book.add("pin", "steel_dark", wear=0.9)
    book.add("wire", "steel_worn", base=(136, 134, 128), dirt=0.45)
    book.add("clamp", "steel_clean", base=(172, 174, 176), dirt=0.3)
    book.add("nail", "steel_rusty", amount=0.55, metal=(140, 138, 132))
    book.raw("hair", NP.style("hair", base=(40, 30, 22), style="matted"))
    blood = spec_blood(w, amount=0.52, grow=0.35) + \
        [WC.blood_zone((-0.6, 5.6, -16.8), (0.6, 7.0, -15.8), 0.5, "dry", soft=0.5)]
    return Built(wm, book, blood, hold=dict(grip=2.2, scale=0.8))


@builder("scythe")
def b_scythe(w) -> Built:
    wm = WC.WeaponModel("scythe", uv=5)
    b = wm.root
    # 柄（スナス）: 2 本継ぎ、ゆるく曲がる。継ぎ目に針金
    snath = [(0, 0, 5.3), (0, 0.12, -1.5), (0, 0.3, -8.0), (0, 0.28, -12.2)]
    for i in range(len(snath) - 1):
        rod(b, snath[i], snath[i + 1], 1.3, "snath", uv=5)
    snath2 = [(0, 0.22, -12.0), (0, 0.14, -16.5), (0, 0.0, -20.8)]
    for i in range(len(snath2) - 1):
        rod(b, snath2[i], snath2[i + 1], 1.24, "snath2", uv=5)
    coil(b, (0, 0.26, -12.1), (0, 0, 1), 1.45, 1.6, 6, "wire", wire=0.13, uv=12)
    rod(b, (0, 0.4, -8.0), (0, 2.75, -7.7), 0.9, "peg", uv=8)                    # 左手の握り（ニブ）
    rod(b, (0, 2.7, -7.71), (0, 3.15, -7.65), 1.08, "peg", uv=8)
    rod(b, (0, 0, 5.2), (0, 0, 5.7), 1.42, "peg", uv=8)
    # 刃を留める金輪とボルト 2 本
    WC.rbeam(b, (0, -0.1, -19.35), (0, -0.1, -21.45), 1.62, 1.82, "collar", k=0.8, uv=8)
    for z in (-19.95, -20.85):
        bolt(b, (0, -0.1, z), (1, 0, 0), 2.1, 0.26, "bolt", nut_size=0.5, uv=10)
    # 刃: 前へまっすぐ伸ばし直した草刈り鎌の刃。刃は下、切っ先は少し上へ反る
    prof = [(-21.2, 0.05, -1.95), (-23.0, -0.25, -2.6), (-25.0, -0.6, -3.05), (-27.0, -0.95, -3.3),
            (-29.0, -1.33, -3.43), (-31.0, -1.62, -3.42), (-32.5, -1.78, -3.28), (-33.6, -1.85, -2.98),
            (-34.4, -1.9, -2.6), (-35.05, -1.93, -2.15), (-35.4, -1.95, -2.02)]
    bl = blade(b, prof, "blade", "edge", "spine", t_body=0.34, t_edge=0.14, t_spine=0.42, bevel=0.5, spine_h=0.3,
               uv=7, edge_uv=9)
    chips_on(bl["edge"], [(-24.5, 0.3, 0.26), (-28.2, 0.2, 0.16), (-31.8, 0.34, 0.3)])
    add_fx(bl["body"] + bl["spine"], world=WC.groove(prof, 0.72, 0.86, -21.6, -32.0, dark=0.62))
    rag(b, (0, -0.55, -18.6), 2.6, 1.5, "rag", hang=(0.1, -1.0, 0.35), strips=2, spread=0.5, seed=12)
    WC.rbeam(b, (0, 0.0, -18.15), (0, 0.0, -19.0), 1.5, 1.6, "rag", k=0.8, uv=8)          # 結び目
    book = WC.Stylebook(w["palette"])
    book.add("snath", "wood_old", base=book.pal(0), dirt=0.5, grain=1.5)
    book.add("snath2", "wood_old", base=(118, 88, 60), dirt=0.55, grain=1.5)
    book.add("peg", "wood_dark", dirt=0.45)
    book.add("wire", "steel_worn", base=(140, 140, 136), dirt=0.5)
    book.add("collar", "steel_rusty", amount=0.85)
    book.add("bolt", "steel_worn", base=book.pal(1), wear=0.7, dirt=0.4)
    book.add("blade", "steel_worn", base=book.pal(1), scratches=0.7, dirt=0.3)
    book.add("edge", "steel_clean", base=book.pal(2))
    book.add("spine", "steel_rusty", amount=0.6, metal=book.pal(1))
    book.add("rag", "cloth_red", dirt=0.6)
    blood = spec_blood(w, amount=0.46, grow=0.5)
    return Built(wm, book, blood, hold=dict(grip=1.6, scale=0.75), icon_flip=False)


@builder("leaf_spring_greatsword")
def b_leaf_spring_greatsword(w) -> Built:
    wm = WC.WeaponModel("leaf_spring_greatsword", uv=5)
    b = wm.root
    # 握り: 革紐を斜めに重ね巻き（巻きの段差）
    WC.rbeam(b, (0, 0, 2.35), (0, 0, -6.75), 1.38, 1.58, "grip_core", k=0.8, uv=6)
    wrap(b, (0, 0, -6.7), (0, 0, 2.3), (1.5, 1.7), "leather", pitch=0.6, tilt=14, seed=21, round_=False, uv=8,
         tail=(1.1, (0.2, -1.0, 0.45)))
    # 柄頭: 歯車をはめ、ナットで留める
    disc(b, (0, 0, 3.0), (0, 0, 1), 1.0, 1.3, "gear", n=2, star=0.92, uv=7)
    ring_of(b, (0, 0, 3.0), (0, 0, 1), 1.12, 10, (0.42, 0.4, 1.1), "gear", uv=8)
    hex_prism(b, (0, 0, 3.8), (0, 0, 1), 0.9, 0.42, "nut", uv=10)
    # 鍔: 鉄筋 2 本を溶接した十字、端は刃の方へ曲がる
    for x in (-0.36, 0.36):
        g = polyline(b, [(x, -3.25, -8.45), (x, -2.65, -7.65), (x, -1.0, -7.38), (x, 1.0, -7.38), (x, 2.65, -7.65),
                         (x, 3.25, -8.45)], 0.64, 0.64, "rebar", up=(0, 0, 1), overlap=0.2, uv=8)
        add_fx(g, rebar=0.42)
    weld(b, [(0, -1.2, -7.38), (0, 1.2, -7.38)], 0.42, "weld", seed=21, uv=10)
    weld(b, [(0, -0.6, -6.95), (0, 0.6, -6.95)], 0.36, "weld", seed=22, uv=10)
    # 板バネ 3 枚: 1 枚目が刃（下の縁を研ぎ出す。うねり）、2・3 枚目は左右に重ねた短い黒い板
    prof = [(-7.9, 1.5, -1.5), (-11.0, 1.56, -1.46), (-14.0, 1.62, -1.42), (-17.0, 1.66, -1.4), (-20.0, 1.66, -1.42),
            (-23.0, 1.62, -1.46), (-26.0, 1.55, -1.5), (-28.5, 1.45, -1.5), (-30.0, 1.36, -1.22), (-31.0, 1.27, -0.3),
            (-31.65, 1.18, 0.55)]
    bl = blade(b, prof, "leaf1", "edge", "leaf1", t_body=0.5, t_edge=0.22, t_spine=0.52, bevel=0.62, spine_h=0.34,
               uv=6, edge_uv=8, grind=0.85)
    chips_on(bl["edge"], [(-13.4, 0.3, 0.26), (-19.7, 0.45, 0.4), (-24.9, 0.25, 0.2)])
    for x, z0, z1, h, yc in ((0.5, -8.1, -21.9, 2.6, 0.1), (-0.5, -8.1, -16.0, 2.2, 0.2)):
        beam(b, (x, yc, z0), (x, yc, z1), 0.5, h, "leaf2", uv=6)
        beam(b, (x, yc + 0.25, z1 + 0.05), (x, yc + 0.45, z1 - 1.1), 0.5, h * 0.6, "leaf2", uv=6)
    for z in (-11.0, -16.0):
        bolt(b, (0, 0.05, z), (1, 0, 0), 2.3, 0.4, "bolt", nut_size=0.78, washer=True, uv=9)
    # U ボルトの締め金（峰をまたいで、両側の脚を下の板で締める）
    for z, y_low in ((-9.0, -1.9), (-20.0, -0.3)):
        cbox(b, (0, 1.92, z), (2.1, 0.42, 0.62), "clamp", uv=8)
        for x in (-1.0, 1.0):
            beam(b, (x, 1.95, z), (x, y_low, z), 0.34, 0.34, "clamp", uv=8)
            hex_prism(b, (x, y_low - 0.1, z), (0, 1, 0), 0.62, 0.3, "nut", uv=10)
        cbox(b, (0, y_low + 0.12, z), (2.25, 0.26, 0.82), "clamp", uv=8)
    # ボルトに挟まった肉片
    cbox(b, (0.95, -0.55, -16.25), (0.42, 0.9, 0.6), "meat", rot=(20, 0, 15), uv=10)
    cbox(b, (-0.92, -0.8, -15.7), (0.36, 0.6, 0.5), "meat", rot=(-15, 10, 0), uv=10)
    book = WC.Stylebook(w["palette"])
    book.add("grip_core", "leather_brown", base=(70, 46, 30))
    book.add("leather", "leather_brown", base=(96, 62, 38), dirt=0.45)
    book.add("gear", "iron_cast", base=(78, 78, 80))
    book.add("nut", "steel_worn", base=book.pal(1), dirt=0.45)
    book.add("rebar", "rebar")
    book.add("weld", "steel_dark", base=(72, 66, 60), wear=0.3, dirt=0.4)
    book.add("leaf1", "steel_worn", base=book.pal(1), scratches=0.8, dirt=0.35)
    book.add("leaf2", "steel_dark", base=book.pal(0), wear=0.8, dirt=0.4)
    book.add("edge", "steel_clean", base=book.pal(2))
    book.add("bolt", "steel_worn", base=(120, 122, 124), dirt=0.5)
    book.add("clamp", "steel_rusty", amount=0.7, metal=(96, 98, 100))
    book.add("meat", "gore_meat")
    blood = spec_blood(w, amount=0.5, grow=0.4) + \
        [WC.blood_zone((-1.2, -1.6, -17.0), (1.2, 0.6, -15.0), 0.55, "wet", soft=0.6)]
    return Built(wm, book, blood, hold=dict(grip=2.0, scale=0.85))


@builder("buzzsaw_glaive")
def b_buzzsaw_glaive(w) -> Built:
    wm = WC.WeaponModel("buzzsaw_glaive", uv=5)
    b = wm.root
    rod(b, (0, 0, 5.0), (0, 0, -18.4), 1.4, "pole", uv=5)
    rod(b, (0, 0, 5.0), (0, 0, 5.5), 1.62, "cap", uv=7)
    for z in (-4.0, -10.0):
        band(b, (0, 0, z), (0, 0, 1), 1.52, 3.0, "hazard", fx={"hazard": 0.42}, uv=7)
    wrap(b, (0, 0, -0.4), (0, 0, 3.6), 1.62, "tape", pitch=0.5, tilt=12, seed=31, uv=8)
    # 電動工具の電池パック（針金で吊るす）: 黄色の筐体、黒い底、残量の LED、外す釦
    cbox(b, (0, -2.05, -12.0), (2.4, 2.1, 4.0), "battery", uv=7)
    cbox(b, (0, -3.2, -12.0), (2.5, 0.5, 4.1), "plastic", uv=7)
    cbox(b, (0, -1.0, -12.0), (1.9, 0.5, 3.4), "plastic", uv=7)
    cbox(b, (0, -1.7, -14.12), (1.2, 0.5, 0.26), "plastic", uv=9)
    for i in range(3):
        cbox(b, (-0.6 + i * 0.6, -2.55, -14.06), (0.3, 0.22, 0.16), "led" if i < 2 else "plastic", uv=12)
    for z in (-10.7, -13.3):
        for (y0, y1, x0, x1) in ((0.82, 0.82, -1.32, 1.32), (-3.52, -3.52, -1.32, 1.32)):
            beam(b, (x0, y0, z), (x1, y1, z), 0.14, 0.14, "wire", uv=12)
        for x in (-1.32, 1.32):
            beam(b, (x, 0.82, z), (x, -3.52, z), 0.14, 0.14, "wire", uv=12)
    polyline(b, [(0, -1.9, -14.0), (0, -2.35, -15.6), (0, -2.0, -17.3), (0, -1.25, -18.5)], 0.4, 0.4, "cable",
             overlap=0.12, uv=9)
    # モーター（パイプと同じ軸）と、直角に曲げるギアの頭。円盤はギアの頭の +X 側に付く（グラインダーと同じ）
    rod(b, (0, 0, -17.4), (0, 0, -21.0), 2.6, "motor", fx={"ribs": 0.42}, uv=7)
    rod(b, (0, 0, -16.9), (0, 0, -17.5), 2.0, "motor", uv=7)
    cbox(b, (0.1, 0, -21.85), (2.3, 2.2, 1.75), "gearhead", uv=8)
    rod(b, (0.6, 0, -21.85), (1.4, 0, -21.85), 1.2, "gearhead", uv=8)
    for i, (y, z) in enumerate(((0.95, -18.0), (-0.95, -18.9), (1.0, -19.8))):
        cbox(b, (-0.2 - 0.02 * i, y, z), (2.66, 0.14, 0.42), "spark", uv=12)
    # 安全カバー（円盤の上半分、外側）
    guard_pts = WC.arc_points((1.95, 0.0, -21.85), 4.65, -95, 95, 6, plane="yz")
    # 板もの（カバー・円盤）は薄い向きを Z にして Y まわりに 90° 回す（アトラスの無駄を減らす）
    R90 = WC.HS.rot(0.0, 90.0, 0.0)
    cover = WC.oriented(b, (1.98, 1.15, -21.85), (9.6, 2.6, 0.14), R90, "guard", uv=8)
    cover.fx = {"sdf": lambda Lr, size: np.maximum(np.hypot(Lr[:, 0] - size[0] / 2, Lr[:, 1] + 1.15) - 4.7,
                                                   1.25 - np.hypot(Lr[:, 0] - size[0] / 2, Lr[:, 1] + 1.15)),
                "border": ((40, 38, 34), 0.18)}
    for i in range(len(guard_pts) - 1):
        p0, p1 = guard_pts[i], guard_pts[i + 1]
        if p0[1] < -0.2 and p1[1] < -0.2:
            continue
        beam(b, (1.55, p0[1], p0[2]), (1.55, p1[1], p1[2]), 0.95, 0.2, "guard", up=(0, p0[1], -(p0[2] + 21.85)),
             extend=0.15, uv=8)
    # 円盤（子ボーン saw が回る）: 外周の歯・ガレット・拡張スリット・中央の印字。軸のナットと押さえ金
    saw = wm.bone("saw", (1.5, 0.0, -21.85), parent="root")

    def disc_sdf(Lr, size):
        return WC.sdf_circle(Lr, size, axes=(0, 1), teeth=28, tooth_h=0.45, hole=0.42)

    def disc_paint(P, N, L, size, col):
        y, z = P[:, 1], P[:, 2] + 21.85
        r = np.hypot(y, z)
        ang = np.arctan2(y, z)
        col = np.where((r > 3.55)[:, None] & (r < 3.75)[:, None], col * 0.8, col)   # 歯の付け根の段
        tip = (r > 3.72)
        col = np.where(tip[:, None], np.minimum(255, col * 0.5 + np.array([92, 90, 84], np.float32)), col)
        slot = np.zeros(len(r), bool)
        for k in range(4):
            a0 = k * math.pi / 2
            da = np.angle(np.exp(1j * (ang - a0)))
            slot |= (np.abs(da) < 0.05 + 0.02 * (r - 2.6)) & (r > 2.6) & (r < 3.45)
        col = np.where(slot[:, None], col * 0.32, col)
        ring = (r > 1.25) & (r < 1.38)
        col = np.where(ring[:, None], col * 0.7, col)
        lab = (r > 1.4) & (r < 2.3) & (np.abs(np.angle(np.exp(1j * (ang - 0.6)))) < 0.6)
        return np.where(lab[:, None], col * 0.6 + np.array([90, 70, 20], np.float32), col)
    dsk = WC.oriented(saw, (1.55, 0.0, -21.85), (8.9, 8.9, 0.22), R90, "disc", uv=9)
    dsk.fx = {"sdf": disc_sdf, "world": disc_paint}
    disc(saw, (1.72, 0, -21.85), (1, 0, 0), 0.95, 0.18, "flange", n=2, star=0.9, uv=10)
    hex_prism(saw, (1.95, 0, -21.85), (1, 0, 0), 0.9, 0.36, "nut", uv=10)
    wm.idle = {"saw": {"rotation": ["q.anim_time * 1440.0", 0.0, 0.0]}}
    book = WC.Stylebook(w["palette"])
    book.add("pole", "steel_worn", base=book.pal(0), dirt=0.45)
    book.add("cap", "rubber_black")
    book.add("hazard", "plastic_yellow", base=book.pal(2), wear=0.5, dirt=0.45)
    book.add("tape", "tape_black", base=book.pal(3))
    book.add("battery", "plastic_yellow", base=(214, 170, 36), wear=0.55, dirt=0.5)
    book.add("plastic", "plastic_black", wear=0.4, dirt=0.45)
    book.add("led", "emissive_green")
    book.add("wire", "steel_worn", base=(150, 150, 146))
    book.add("cable", "rubber_black")
    book.add("motor", "plastic_black", base=(48, 48, 52), dirt=0.45)
    book.add("gearhead", "aluminium", base=(138, 140, 144), dirt=0.55)
    book.add("spark", "emissive_blue", base=book.pal(4))
    book.add("guard", "steel_painted", base=(206, 170, 50), wear=0.6, rust=0.3)
    book.add("disc", "steel_worn", base=book.pal(1), scratches=0.9, dirt=0.15)
    book.add("flange", "steel_dark", wear=0.8)
    book.add("nut", "brass", wear=0.7)
    blood = [WC.blood_zone((1.2, -4.6, -26.4), (1.9, -0.6, -17.6), 0.52, "wet", soft=0.9),
             WC.blood_zone((1.2, -1.0, -26.6), (2.3, 1.8, -23.6), 0.36, "wet", soft=0.9),
             WC.blood_zone((-1.4, -1.6, -21.0), (1.4, 1.4, -17.2), 0.3, "dry", soft=1.0)]
    return Built(wm, book, blood, hold=dict(grip=1.6, scale=0.8))


# ===========================================================================
#  片手の打撃
# ===========================================================================
R90 = WC.HS.rot(0.0, 90.0, 0.0)          # 薄い板を Z 向きに作って X 向きへ回す（アトラスの節約）


def gear_sdf(teeth, tooth_h, hole=0.0, axes=(0, 1)):
    """歯車の輪郭（台形の歯）。"""
    def fn(Lr, size):
        cx, cy = size[axes[0]] / 2, size[axes[1]] / 2
        x = Lr[:, axes[0]] - cx
        y = Lr[:, axes[1]] - cy
        rr = np.hypot(x, y)
        R = min(cx, cy)
        ph = (np.arctan2(y, x) / (2 * math.pi) * teeth) % 1.0
        tooth = np.clip(1.0 - np.abs(ph - 0.5) * 4.0 + 0.6, 0, 1)
        d = rr - (R - tooth_h + tooth_h * tooth)
        if hole > 0:
            d = np.maximum(d, hole - rr)
        return d
    return fn


@builder("pipe_wrench")
def b_pipe_wrench(w) -> Built:
    wm = WC.WeaponModel("pipe_wrench", uv=6)
    b = wm.root
    # 柄: I 字断面（ウェブと上下のフランジ）。頭の側が太い
    web = beam(b, (0, 0.02, 3.3), (0, 0.06, -5.2), 0.52, 1.5, "handle", uv=7)
    add_fx([web], world=WC.stamp("NR 18", (-1.4, 0.04), 0.62, mul=0.55))
    for sy in (1, -1):
        beam(b, (0, sy * 0.78, 3.3), (0, sy * 0.9 + 0.05, -5.2), 1.22, 0.32, "handle", uv=7)
    cbox(b, (0, 0, 3.75), (1.3, 1.85, 1.1), "iron", uv=7)
    WC.rbeam(b, (0, 0, 4.25), (0, 0, 4.7), 1.1, 1.5, "iron", k=0.7, uv=7)
    wm.cut((0, 0, 3.85), (1, 0, 0), r=0.36, half=1.0, rim=0.12)
    # 枠（下の固定の顎と一体）と調整ナット、上の可動の顎
    cbox(b, (0, -0.1, -6.1), (1.62, 1.8, 2.4), "iron", uv=7)
    cbox(b, (0, -0.1, -6.1), (1.8, 1.3, 1.9), "iron", uv=7)
    beam(b, (0, -0.42, -7.2), (0, -0.36, -10.6), 1.4, 1.0, "jaw", uv=8)
    beam(b, (0, -0.1, -10.35), (0, 0.15, -10.75), 1.4, 0.9, "jaw", uv=8)
    teeth_row(b, (0, 0.08, -10.45), (0, 0.08, -8.0), 6, (1.32, 0.3, 0.3), "teeth", uv=10)
    rod(b, (0, -0.6, -6.0), (0, 2.6, -6.0), 0.86, "jaw", uv=8)                       # 可動の顎の軸
    nut = rod(b, (0, 0.82, -6.0), (0, 2.0, -6.0), 1.85, "nut", uv=9)
    add_fx(nut, ribs=0.22)
    beam(b, (0, 2.42, -5.5), (0, 2.42, -10.25), 1.4, 1.2, "jaw", uv=8)
    beam(b, (0, 2.6, -10.1), (0, 2.25, -10.55), 1.4, 0.8, "jaw", uv=8)
    teeth_row(b, (0, 1.8, -10.15), (0, 1.8, -7.4), 7, (1.32, 0.3, 0.3), "teeth", uv=10)
    # 枠の窓（ばねが見える）
    coil(b, (0, -0.2, -6.0), (0, 1, 0), 0.62, 0.9, 3, "spring", wire=0.1, uv=12)
    hairs(b, 0.72, (1.4, -9.0), 4, 1.4, "hair", seed=41, side=1)
    # 柄の握りに黒テープ、上の顎の背にボルトを溶接して研いだ棘 3 本
    wrap(b, (0, 0.04, 0.4), (0, 0.04, 3.1), (1.42, 2.06), "tape", pitch=0.55, tilt=9, seed=42, round_=False, uv=9,
         tail=(0.6, (0.3, -1.0, 0.1)))
    for i, z in enumerate((-6.3, -7.8, -9.3)):
        beam(b, (0, 2.96, z), (0, 3.95, z + 0.28), 0.42, 0.42, "spike", roll=45.0, uv=12)
        beam(b, (0, 3.9, z + 0.27), (0, 4.55, z + 0.47), 0.24, 0.24, "spike", roll=45.0, uv=12)
        weld(b, [(-0.32, 3.06, z), (0.32, 3.06, z)], 0.3, "weld", seed=43 + i, step=0.6, uv=12)
    book = WC.Stylebook(w["palette"])
    book.add("handle", "steel_painted", base=book.pal(0), wear=0.6, rust=0.35)
    book.add("iron", "iron_cast", base=(70, 70, 72))
    book.add("jaw", "steel_worn", base=book.pal(1), dirt=0.45)
    book.add("teeth", "steel_worn", base=book.pal(3), wear=0.9, dirt=0.3)
    book.add("nut", "steel_worn", base=book.pal(3), wear=0.8, dirt=0.35)
    book.add("spring", "steel_dark")
    book.add("tape", "tape_black", base=book.pal(2))
    book.add("spike", "steel_worn", base=(150, 152, 150), scratches=0.8, dirt=0.3)
    book.add("weld", "steel_dark", base=(80, 70, 62), wear=0.3, dirt=0.4)
    book.raw("hair", NP.style("hair", base=(52, 36, 24), style="matted"))
    blood = spec_blood(w, amount=0.48, grow=0.5)
    return Built(wm, book, blood, hold=dict(pitch=28.0))


@builder("crowbar")
def b_crowbar(w) -> Built:
    wm = WC.WeaponModel("crowbar", uv=6)
    b = wm.root
    hex_prism(b, (0, 0, -2.45), (0, 0, 1), 0.92, 13.1, "shaft", uv=6)
    wrap(b, (0, 0, -0.65), (0, 0, 3.4), 1.12, "tape", pitch=0.45, tilt=11, seed=51, uv=9,
         tail=(0.7, (0.2, -1.0, 0.3)))
    # 鉤: なめらかに曲がって、先は平たく二股の釘抜き
    hook = [(0, 0, -8.7), (0, 0.22, -9.55), (0, 0.85, -10.3), (0, 1.75, -10.65), (0, 2.72, -10.55),
            (0, 3.45, -10.05), (0, 3.86, -9.3), (0, 3.98, -8.62)]
    for i in range(len(hook) - 1):
        rod(b, hook[i], hook[i + 1], 0.92 - 0.02 * i, "shaft" if i < 5 else "worn", uv=7)
    for x in (-0.27, 0.27):
        polyline(b, [(x, 3.98, -8.75), (x, 3.92, -8.05), (x, 3.72, -7.45)], [0.44, 0.34], [0.42, 0.26], "worn",
                 uv=9)
    cbox(b, (0, 3.9, -8.3), (0.12, 0.5, 0.9), "dark", uv=10)
    # 尻の平たいへら（少し反る）
    beam(b, (0, 0, 3.9), (0, -0.18, 4.75), 1.0, 0.62, "worn", uv=8)
    beam(b, (0, -0.16, 4.7), (0, -0.42, 5.5), 1.1, 0.32, "worn", uv=8)
    add_fx(wm.cubes[:3], world=WC.stamp("FORGED", (-4.4, 0.0), 0.42, mul=0.6))
    # 鉤の手前に有刺鉄線、鉤の背に前向きの釘を 2 本溶接
    coil(b, (0, 0, -6.6), (0, 0, 1), 1.12, 1.6, 3, "barb", wire=0.11, uv=12)
    for i, (x, y, z) in enumerate(((0.58, 0.2, -6.0), (-0.58, -0.1, -6.6), (0.1, 0.6, -7.2), (-0.1, -0.6, -6.3))):
        cbox(b, (x, y, z), (0.08, 0.45, 0.08), "barb", rot=(35, 25 * i, 40), uv=12)
    for y in (1.35, 2.45):
        nail(b, (0, y, -10.75), (0, y + 0.1, -12.1), "nail", d=0.2, uv=12)
        weld(b, [(-0.25, y, -10.72), (0.25, y, -10.72)], 0.28, "weld", seed=int(y * 10), step=0.6, uv=12)
    book = WC.Stylebook(w["palette"])
    book.add("shaft", "steel_painted", base=book.pal(0), wear=0.9, rust=0.45)
    book.add("worn", "steel_worn", base=book.pal(1), scratches=0.8, dirt=0.4)
    book.add("dark", "steel_dark", base=book.pal(2))
    book.add("tape", "tape_black", base=book.pal(2))
    book.add("barb", "steel_rusty", amount=0.55, metal=(140, 140, 136))
    book.add("nail", "steel_rusty", amount=0.5, metal=(140, 138, 132))
    book.add("weld", "steel_dark", base=(80, 70, 62), wear=0.3, dirt=0.4)
    blood = spec_blood(w, amount=0.5, grow=0.5) + [
        WC.blood_zone((-0.4, 1.0, -12.3), (0.4, 2.8, -10.6), 0.45, "wet", soft=0.5)]
    return Built(wm, book, blood, hold=dict(pitch=30.0))


@builder("nail_bat")
def b_nail_bat(w) -> Built:
    wm = WC.WeaponModel("nail_bat", uv=6)
    b = wm.root
    rod(b, (0, 0, 3.15), (0, 0, -1.7), 1.18, "wood", uv=6)
    wrap(b, (0, 0, -1.9), (0, 0, 3.1), 1.3, "tape", pitch=0.5, tilt=10, seed=61, uv=8,
         tail=(0.8, (0.25, -1.0, -0.2)))
    disc(b, (0, 0, 3.45), (0, 0, 1), 0.92, 0.7, "wood", n=3, uv=7)
    for z0, z1, d in ((-1.6, -3.0, 1.36), (-3.0, -4.3, 1.62), (-4.3, -5.6, 1.92)):
        rod(b, (0, 0, z0), (0, 0, z1), d, "wood", uv=6)
    barrel = disc(b, (0, 0, -9.2), (0, 0, 1), 1.26, 7.6, "wood", n=3, uv=6)
    disc(b, (0, 0, -13.25), (0, 0, 1), 1.12, 0.7, "wood", n=3, uv=6)
    disc(b, (0, 0, -13.7), (0, 0, 1), 0.86, 0.3, "wood", n=2, uv=6)
    brand = WC.stamp("NR34", (-8.0, 0.0), 0.62, mul=1.0, tint=(46, 26, 14))

    def split(P, N, L, size, col):
        ok = (P[:, 1] > 0.3) & (np.abs(N[:, 0]) < 0.6)
        wig = 0.12 * np.sin(P[:, 2] * 2.3)
        m = ok & (np.abs(P[:, 0] - 0.35 - wig) < 0.06) & (P[:, 2] < -9.8) & (P[:, 2] > -12.9)
        return np.where(m[:, None], col * 0.35, col)
    add_fx(barrel, world=WC.compose(brand, split))
    # 釘: 貫通（頭あり・先が曲がる）、縦の貫通、斜めに打ち込んで飛び出したもの
    for i, (y, z) in enumerate(((0.6, -7.0), (-0.5, -8.4), (0.4, -10.0), (-0.8, -11.4), (0.2, -12.6))):
        sgn = 1 if i % 2 == 0 else -1
        bend = (0.5, (0, 0.5 if i % 2 else -0.6, 0.6)) if i in (1, 3) else None
        nail(b, (sgn * 1.6, y, z), (-sgn * 1.75, y, z), "nail", head=0.5 if i != 2 else 0.0, bend=bend, uv=12)
    for i, (x, z) in enumerate(((0.4, -7.6), (-0.5, -9.2), (0.2, -10.8), (-0.3, -12.2))):
        nail(b, (x, 1.65, z), (x, -1.75, z), "nail", head=0.46 if i % 2 else 0.0,
             bend=(0.45, (0.6, 0, -0.5)) if i == 2 else None, uv=12)
    for (p0, p1) in (((0.55, 0.9, -8.8), (1.4, 1.9, -9.3)), ((-0.6, -0.8, -10.6), (-1.6, -1.6, -10.1)),
                     ((0.9, -0.5, -12.0), (1.9, -1.1, -12.7)), ((-0.8, 0.8, -7.2), (-1.7, 1.6, -6.7))):
        nail(b, p1, p0, "nail", head=0.42, uv=12)
    rag(b, (-1.7, -0.8, -11.4), 1.6, 0.8, "rag", hang=(-0.2, -1.0, 0.2), strips=1, seed=62)
    book = WC.Stylebook(w["palette"])
    book.add("wood", "wood_raw", base=book.pal(0), dirt=0.45, grain=1.2)
    book.add("tape", "tape_grey", base=(132, 132, 128), dirt=0.6)
    book.add("nail", "steel_rusty", amount=0.65, metal=book.pal(1))
    book.add("rag", "cloth_rag", dirt=0.7)
    blood = spec_blood(w, amount=0.5, grow=0.4) + [WC.blood_zone((-2, -2, -13.9), (2, 2, -12.4), 0.55, "wet")]
    return Built(wm, book, blood, hold=dict(pitch=30.0))


@builder("police_baton")
def b_police_baton(w) -> Built:
    wm = WC.WeaponModel("police_baton", uv=7)
    b = wm.root
    rod(b, (0, 0, 3.1), (0, 0, -1.9), 1.2, "foam", fx={"ribs": 0.32}, uv=8)
    for z in (-1.35, 0.55, 2.45):
        band(b, (0, 0, z), (0, 0, 1), 1.3, 0.3, "foam", uv=8)
    rod(b, (0, 0, 3.0), (0, 0, 3.85), 1.32, "cap", fx={"knurl": 0.22}, uv=9)
    disc(b, (0, 0, 3.95), (0, 0, 1), 0.5, 0.22, "cap", n=2, star=0.86, uv=10)
    polyline(b, [(0, 0.5, 4.0), (0, 0.9, 4.7), (0, 0.2, 5.25), (0, -0.55, 4.9), (0, -0.5, 4.05)], 0.16, 0.16,
             "cord", overlap=0.1, uv=12)
    rod(b, (0, 0, -1.8), (0, 0, -5.8), 1.0, "tube", uv=8)
    band(b, (0, 0, -5.85), (0, 0, 1), 1.12, 0.32, "chrome", uv=10)
    rod(b, (0, 0, -5.7), (0, 0, -9.6), 0.8, "tube", uv=8)
    band(b, (0, 0, -9.65), (0, 0, 1), 0.92, 0.3, "chrome", uv=10)
    rod(b, (0, 0, -9.5), (0, 0, -12.9), 0.6, "worn", uv=9)
    disc(b, (0, 0, -13.2), (0, 0, 1), 0.47, 0.82, "worn", n=3, uv=10)
    rod(b, (0, 0, -12.85), (0, 0, -13.6), 0.72, "worn", uv=10)
    add_fx(wm.cubes[:2], world=WC.stamp("POLICE", (1.0, 0.0), 0.36, mul=1.0, tint=(200, 196, 180)))
    # 破れた発泡グリップを留めたテープ、先の筒にボルト 3 本をホースバンドで抱かせる、2 段目に結んだ布切れ
    wrap(b, (0, 0, -0.9), (0, 0, 0.3), 1.36, "tape", pitch=0.6, tilt=8, seed=44, uv=9)
    for a in (90.0, 210.0, 330.0):
        ca, sa = math.cos(math.radians(a)) * 0.42, math.sin(math.radians(a)) * 0.42
        rod(b, (ca, sa, -10.5), (ca, sa, -12.45), 0.22, "bolt", uv=12)
        hex_prism(b, (ca, sa, -12.55), (0, 0, 1), 0.46, 0.24, "bolt", uv=12)
    hose_clamp(b, -11.4, (1.16, 1.16), "clamp", side=1)
    WC.rbeam(b, (0, 0, -7.2), (0, 0, -7.8), 0.98, 0.98, "rag", k=0.8, uv=10)
    rag(b, (0, -0.5, -7.5), 1.8, 0.7, "rag", hang=(0.15, -1.0, 0.35), strips=2, spread=0.3, seed=46)
    book = WC.Stylebook(w["palette"])
    book.add("foam", "rubber_black", base=book.pal(0), dirt=0.3)
    book.add("cap", "steel_dark", base=book.pal(3), wear=0.9)
    book.add("cord", "paracord", base=(40, 40, 44))
    book.add("tube", "steel_dark", base=book.pal(0), wear=0.95, dirt=0.2)
    book.add("chrome", "chrome", base=book.pal(2))
    book.add("worn", "steel_worn", base=book.pal(1), scratches=0.95, dirt=0.2)
    book.add("tape", "tape_grey", base=(128, 128, 124), dirt=0.55)
    book.add("bolt", "steel_worn", base=(132, 134, 134), dirt=0.45)
    book.add("clamp", "steel_clean", base=(172, 174, 176), dirt=0.3)
    book.add("rag", "cloth_rag", base=(150, 140, 120), dirt=0.6)
    blood = [WC.blood_zone((-0.6, -0.6, -13.8), (0.6, 0.6, -11.6), 0.42, "dry", soft=0.7),
             WC.blood_zone((-0.8, -2.4, -8.4), (0.8, 0.0, -6.6), 0.4, "wet", soft=0.6)]
    return Built(wm, book, blood, hold=dict(pitch=34.0))


@builder("claw_hammer")
def b_claw_hammer(w) -> Built:
    wm = WC.WeaponModel("claw_hammer", uv=7)
    b = wm.root
    WC.rbeam(b, (0, 0, 3.4), (0, 0, -5.0), 1.1, 1.4, "handle", k=0.78, uv=7)
    WC.rbeam(b, (0, 0, 3.25), (0, 0, -0.4), 1.24, 1.54, "grip", k=0.78, fx={"ribs": 0.42}, uv=8)
    for s_ in (-1, 1):
        beam(b, (s_ * 0.63, 0.0, 2.9), (s_ * 0.63, 0.0, -0.1), 0.06, 0.46, "handle", uv=10)
    WC.rbeam(b, (0, 0, 3.4), (0, 0, 3.85), 1.3, 1.64, "grip", k=0.72, uv=8)
    wm.cut((0, 0, 3.55), (1, 0, 0), r=0.24, half=1.0)
    rod(b, (0, 0, -4.8), (0, 0, -6.0), 1.02, "head", uv=9)
    cbox(b, (0, 0, -6.6), (1.3, 1.3, 1.6), "head", uv=9)
    rod(b, (0, -0.45, -6.6), (0, -2.55, -6.6), 1.62, "head", uv=9)
    band(b, (0, -2.3, -6.6), (0, 1, 0), 1.78, 0.42, "face", uv=10)
    rod(b, (0, -2.55, -6.6), (0, -2.95, -6.6), 1.82, "strike", uv=10)
    # 二股の釘抜き（後ろへ反る）。付け根は一体
    cbox(b, (0, 0.95, -6.55), (1.2, 0.8, 0.95), "head", uv=9)
    for x in (-0.3, 0.3):
        polyline(b, [(x, 0.9, -6.6), (x, 1.75, -6.42), (x, 2.5, -5.95), (x, 3.08, -5.25), (x, 3.32, -4.55)],
                 [0.54, 0.5, 0.46, 0.4], [0.8, 0.66, 0.5, 0.32], "head", up=(0, 0, 1), uv=9)
    for (c, sz) in (((0.3, -3.1, -6.3), 0.3), ((-0.4, -3.05, -6.9), 0.24), ((0.75, -2.7, -6.6), 0.2)):
        cbox(b, c, (sz, sz * 0.8, sz * 1.2), "bonechip", rot=(20, 35, 10), uv=12)
    # 柄にテープ、尻の穴に紐。頭の横（+X）に研いだマイナスドライバーを沿わせ、テープと針金で縛る（突きの棘）
    wrap(b, (0, 0, -0.6), (0, 0, -2.4), (1.26, 1.56), "tape", pitch=0.6, tilt=10, seed=45, uv=9,
         tail=(0.5, (0.3, -1.0, 0.2)))
    for s_ in (-1, 1):
        polyline(b, [(s_ * 0.67, 0, 3.55), (s_ * 0.76, -0.9, 3.95), (s_ * 0.26, -1.8, 4.2)], 0.16, 0.16, "cord",
                 overlap=0.08, uv=12)
    cbox(b, (0, -1.9, 4.22), (0.46, 0.36, 0.36), "cord", uv=12)
    rod(b, (1.02, 0, -1.6), (1.02, 0, -3.7), 0.92, "sd_handle", fx={"ribs": 0.5}, uv=10)
    rod(b, (1.02, 0, -3.65), (1.02, 0, -4.0), 0.62, "sd_shaft", uv=12)
    rod(b, (1.02, 0, -3.95), (1.02, 0, -8.6), 0.3, "sd_shaft", uv=12)
    beam(b, (1.02, 0, -8.55), (1.02, 0, -9.3), 0.3, 0.12, "sd_tip", uv=12)
    wrap(b, (0.48, 0, -1.9), (0.48, 0, -2.9), (2.22, 1.66), "tape", pitch=0.5, tilt=-6, seed=47, round_=False, uv=9)
    lash(b, (0.48, 0, -4.4), (0, 0, 1), 2.1, 1.5, 0.5, 2, "wire", wire=0.12, uv=12)
    hairs(b, 0.92, (-2.3, -6.6), 2, 1.0, "hair", seed=48, side=1)
    book = WC.Stylebook(w["palette"])
    book.add("handle", "plastic_yellow", base=book.pal(2), wear=0.5, dirt=0.45)
    book.add("grip", "rubber_black", base=book.pal(3), dirt=0.4)
    book.add("head", "steel_dark", base=book.pal(0), wear=0.85, dirt=0.3)
    book.add("face", "steel_worn", base=book.pal(1), dirt=0.3)
    book.add("strike", "steel_clean", base=(190, 194, 198))
    book.add("bonechip", "bone")
    book.add("tape", "tape_grey", dirt=0.55)
    book.add("cord", "paracord", base=(60, 70, 96))
    book.add("sd_handle", "plastic_red", base=(150, 34, 28), wear=0.4, dirt=0.45)
    book.add("sd_shaft", "chrome", base=(190, 194, 198))
    book.add("sd_tip", "steel_clean", base=(206, 208, 210))
    book.add("wire", "steel_worn", base=(140, 138, 132), dirt=0.4)
    book.raw("hair", NP.style("hair", base=(40, 30, 22), style="matted"))
    blood = spec_blood(w, amount=0.52, grow=0.45) + [
        WC.blood_zone((0.7, -0.4, -9.4), (1.4, 0.4, -7.6), 0.5, "wet", soft=0.5)]
    return Built(wm, book, blood, hold=dict(pitch=26.0))


@builder("pipe_mace")
def b_pipe_mace(w) -> Built:
    wm = WC.WeaponModel("pipe_mace", uv=6)
    b = wm.root
    rod(b, (0, 0, 3.0), (0, 0, -8.8), 1.2, "pipe", uv=6)
    rod(b, (0, 0, 3.0), (0, 0, 3.35), 1.0, "pipe", uv=6)
    wrap(b, (0, 0, -0.75), (0, 0, 3.55), 1.42, "rag", pitch=0.55, tilt=16, seed=71, uv=8)
    for z0, z1 in ((-1.05, -0.55), (3.35, 3.85)):
        wrap(b, (0, 0, z0), (0, 0, z1), 1.58, "tape", pitch=0.25, tilt=6, seed=int(-z0 * 10), uv=10)
    # T 字の継ぎ手（横に短い枝）
    rod(b, (0, 0, -8.5), (0, 0, -10.75), 1.82, "iron", uv=7)
    rod(b, (-1.35, 0, -9.62), (1.35, 0, -9.62), 1.62, "iron", uv=7)
    for x in (-1.35, 1.35):
        band(b, (x, 0, -9.62), (1, 0, 0), 1.78, 0.3, "iron", uv=8)
    for z in (-8.6, -10.65):
        band(b, (0, 0, z), (0, 0, 1), 1.98, 0.3, "iron", uv=8)
    # 溶接で盛った頭（不揃いの塊）とボルトの頭、先の歯車
    for c, sz, r in (((0, 0, -11.6), (2.5, 2.4, 3.2), (6, 8, 4)), ((0.2, 0.3, -11.3), (2.7, 2.0, 2.4), (-10, 20, 8)),
                     ((-0.25, -0.2, -12.1), (2.2, 2.7, 2.2), (14, -12, -6)), ((0, 0, -12.8), (1.9, 1.9, 1.2), (0, 0, 22))):
        cbox(b, c, sz, "head", rot=r, uv=7)
    bolts = [((1.6, 0, -11.0), (1, 0, 0)), ((-1.6, 0, -11.0), (-1, 0, 0)), ((0, 1.6, -12.2), (0, 1, 0)),
             ((0, -1.6, -12.2), (0, -1, 0)), ((1.2, 1.2, -12.8), (0.7, 0.7, 0)), ((-1.2, -1.2, -10.4), (-0.7, -0.7, 0))]
    for c, n in bolts:
        n_ = np.asarray(n, float) / np.linalg.norm(n)
        hex_prism(b, np.asarray(c) + n_ * 0.1, n_, 0.82, 0.5, "bolt", uv=10)
        rod(b, np.asarray(c) + n_ * 0.3, np.asarray(c) + n_ * 0.72, 0.4, "bolt", uv=10)
        weld(b, [np.asarray(c) - n_ * 0.2 + np.array([0.0, 0.0, 0.35]), np.asarray(c) - n_ * 0.2 - np.array([0.0, 0.0, 0.35])],
             0.3, "weld", seed=int(abs(c[0] * 10 + c[1] * 7 + c[2])), uv=10)
    gear = WC.oriented(b, (0, 0, -13.55), (3.6, 3.6, 0.6), R90, "gear", uv=8)
    gear.fx = {"sdf": gear_sdf(12, 0.42, hole=0.0)}
    disc(b, (0, 0, -13.55), (1, 0, 0), 0.62, 1.0, "bolt", n=2, star=0.86, uv=10)
    hairs(b, 1.32, (0.2, -11.6), 5, 1.6, "hair", seed=72, side=1)
    book = WC.Stylebook(w["palette"])
    book.add("pipe", "steel_worn", base=(150, 154, 152), scratches=0.5, dirt=0.4)
    book.add("rag", "cloth_rag", dirt=0.65)
    book.add("tape", "tape_black")
    book.add("iron", "iron_cast", base=(72, 70, 70))
    book.add("head", "steel_rusty", amount=0.8)
    book.add("bolt", "steel_worn", base=book.pal(2), dirt=0.45)
    book.add("weld", "steel_dark", base=(80, 70, 62), wear=0.3, dirt=0.4)
    book.add("gear", "iron_cast", base=(84, 82, 80))
    book.raw("hair", NP.style("hair", base=(30, 24, 20), style="matted"))
    blood = spec_blood(w, amount=0.5, grow=0.5)
    return Built(wm, book, blood, hold=dict(pitch=28.0))


# ===========================================================================
#  模様の補助（この生成器だけで使う world 模様）
# ===========================================================================
def grime(*ranges, dark=0.62, seed=0):
    """手の当たる所の黒ずみ（手垢と油）。ranges = [(z0, z1), ...]。端はぼかす。"""
    def fn(P, N, L, size, col):
        z = P[:, 2]
        m = np.zeros(len(P))
        for z0, z1 in ranges:
            za, zb = min(z0, z1), max(z0, z1)
            m = np.maximum(m, np.clip(np.minimum(z - za, zb - z) / 0.9 + 0.5, 0, 1))
        n = NP.fbm3(P[:, 0] * 2.0, P[:, 1] * 2.0, P[:, 2] * 1.2, seed, octaves=2)
        f = 1.0 - (1.0 - dark) * m * np.clip(0.6 + 0.7 * n, 0, 1)
        return col * f[:, None]
    return fn


def soot(z_hot, z_cold, *, dark=0.3, seed=0):
    """煤と焼け（z_hot で最も濃く、z_cold で消える）。少し茶色に寄せる。"""
    def fn(P, N, L, size, col):
        t = np.clip((P[:, 2] - z_cold) / (z_hot - z_cold), 0, 1)
        n = NP.fbm3(P[:, 0] * 1.7, P[:, 1] * 1.7, P[:, 2] * 1.7, seed, octaves=3)
        k = np.clip(t * (0.45 + 0.8 * n), 0, 1)[:, None]
        burnt = col * dark + np.array([18, 12, 6], np.float32)
        return col * (1 - k) + burnt * k
    return fn


def dots(centres, r, rgb, *, normal=None):
    """小さな丸（樹脂の柄の鋲・ねじの頭）。centres は武器空間の点（面の上）。normal の向きの面だけ（None は全部）。"""
    C = np.asarray(centres, np.float32).reshape(-1, 3)
    rgb_ = np.asarray(rgb, np.float32)
    nrm = None if normal is None else np.asarray(normal, np.float32)

    def fn(P, N, L, size, col):
        d = np.min(np.linalg.norm(P[:, None, :] - C[None, :, :], axis=2), axis=1)
        ok = np.ones(len(P), bool) if nrm is None else (N @ nrm) > 0.6
        inner = ok & (d < r * 0.7)
        ring = ok & (d >= r * 0.7) & (d < r)
        col = np.where(ring[:, None], rgb_ * 0.6, col)
        return np.where(inner[:, None], rgb_ * (0.88 + 0.24 * col.mean(1, keepdims=True) / 255.0), col)
    return fn


def barcode(z0, z1, y0, y1, *, side=1, seed=0):
    """値札・管理シール（白地に黒いバーコード）。±X の面（side）に。"""
    za, zb = min(z0, z1), max(z0, z1)
    bars = np.random.RandomState(seed).rand(30) < 0.5

    def fn(P, N, L, size, col):
        ok = (np.sign(N[:, 0]) == side) & (np.abs(N[:, 0]) > 0.6)
        z, y = P[:, 2], P[:, 1]
        inn = ok & (z > za) & (z < zb) & (y > y0) & (y < y1)
        paper = np.array([224, 220, 204], np.float32) * (0.82 + 0.18 * col.mean(1, keepdims=True) / 255.0)
        out = np.where(inn[:, None], paper, col)
        fz = (z - za) / (zb - za)
        k = np.clip((fz * len(bars)).astype(int), 0, len(bars) - 1)
        fy = (y - y0) / (y1 - y0)
        bar = inn & bars[k] & (fy > 0.32) & (fy < 0.86) & (fz > 0.1) & (fz < 0.9)
        return np.where(bar[:, None], np.array([34, 32, 34], np.float32), out)
    return fn


def graffiti(rgb, strokes, *, side=1, width=0.15):
    """スプレーの落書き（±X の面に (z, y) の折れ線を太い線で。周りに霧）。"""
    segs = [(np.asarray(a, float), np.asarray(b_, float)) for s in strokes for a, b_ in zip(s[:-1], s[1:])]
    rgbv = np.asarray(rgb, np.float32)

    def fn(P, N, L, size, col):
        ok = (np.sign(N[:, 0]) == side) & (np.abs(N[:, 0]) > 0.6)
        q = P[:, [2, 1]]
        dmin = np.full(len(P), 1e9)
        for a, b_ in segs:
            ab = b_ - a
            t = np.clip(((q - a) @ ab) / max(1e-6, float(ab @ ab)), 0, 1)
            dmin = np.minimum(dmin, np.linalg.norm(q - (a + t[:, None] * ab), axis=1))
        core = ok & (dmin < width)
        mist = ok & (dmin >= width) & (dmin < width * 2.4)
        col = np.where(mist[:, None], col * 0.75 + rgbv * 0.25, col)
        return np.where(core[:, None], rgbv * (0.8 + 0.25 * col.mean(1, keepdims=True) / 255.0), col)
    return fn


def beads(seed, *, side=-1, amount=0.16):
    """標識の反射材のつぶつぶ（細かい明るい点）。"""
    def fn(P, N, L, size, col):
        ok = (np.sign(N[:, 0]) == side) & (np.abs(N[:, 0]) > 0.6)
        n = NP.fbm3(P[:, 0] * 11.0, P[:, 1] * 11.0, P[:, 2] * 11.0, seed, octaves=1)
        m = ok & (n > 1.0 - amount)
        return np.where(m[:, None], np.minimum(255, col * 1.16 + 16), col)
    return fn


def tube_end(z_end, half, wall=0.12):
    """開いた角管の端（-Z を向いた端の面の、肉厚 wall より内側を暗い穴に）。half = (x の半幅, y の半幅)。"""
    def fn(P, N, L, size, col):
        ok = (N[:, 2] < -0.7) & (np.abs(P[:, 2] - z_end) < 0.08)
        inn = ok & (np.abs(P[:, 0]) < half[0] - wall) & (np.abs(P[:, 1]) < half[1] - wall)
        return np.where(inn[:, None], np.array([14, 13, 14], np.float32), col)
    return fn


def zline(z0, *, w=0.05, dark=0.42):
    """z = z0 の割り線（コンロッドのキャップの合わせ目など）。"""
    def fn(P, N, L, size, col):
        m = (np.abs(P[:, 2] - z0) < w) & (np.abs(N[:, 2]) < 0.6)
        return np.where(m[:, None], col * dark, col)
    return fn


def aggregate(seed, *, cell=0.62, r=0.24, frac=0.62):
    """コンクリの割れ面に見える骨材（灰・茶・白っぽい小石）と、その周りの暗い縁。"""
    pal = np.array([[116, 112, 104], [148, 130, 106], [178, 174, 162], [90, 86, 82], [134, 112, 92]], np.float32)

    def fn(P, N, L, size, col):
        d, rnd = WC.worley3(P, cell, seed)
        rr = r * (0.6 + 0.8 * rnd[:, 1])
        ok = rnd[:, 0] < frac
        k = np.minimum((rnd[:, 2] * len(pal)).astype(int), len(pal) - 1)
        shade = 0.82 + 0.3 * np.clip(1 - d / rr, 0, 1)
        stone = pal[k] * shade[:, None] * (0.85 + 0.3 * col.mean(1, keepdims=True) / 255.0)
        inner = ok & (d < rr)
        rim = ok & (d >= rr) & (d < rr + 0.07)
        col = np.where(rim[:, None], col * 0.7, col)
        return np.where(inner[:, None], stone, col)
    return fn


def hose_clamp(b, z, d, style, *, side=1, uv=10) -> list:
    """ホースバンド（柄に巻いた薄い帯 + side 側の締めネジの箱とネジの頭）。d = (幅, 高さ)。"""
    out = WC.rbeam(b, (0, 0, z + 0.17), (0, 0, z - 0.17), d[0], d[1], style, k=0.82, uv=uv)
    hx = side * (d[0] / 2 + 0.14)
    out.append(cbox(b, (hx, 0.12, z), (0.34, 0.5, 0.56), style, uv=uv))
    out += rod(b, (hx, 0.36, z), (hx, 0.62, z), 0.34, style, uv=uv)
    return out


# ===========================================================================
#  両手の打撃
# ===========================================================================
@builder("sledgehammer")
def b_sledgehammer(w) -> Built:
    wm = WC.WeaponModel("sledgehammer", uv=5)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # ---- 柄（ヒッコリー）: 尻のゴム握り（膨らむ）→ 細い喉 → 頭の手前で太る。頭の目を貫いて先に楔 ----
    WC.rbeam(b, (0, 0, 4.85), (0, 0, -0.85), 1.74, 1.88, "grip", k=0.8, fx={"ribs": 0.5}, uv=7)
    WC.rbeam(b, (0, 0, 5.8), (0, 0, 4.75), 1.98, 2.14, "grip", k=0.76, uv=7)
    haft = WC.rbeam(b, (0, 0, -0.7), (0, 0, -10.2), 1.4, 1.55, "haft", k=0.8, uv=5)
    haft += WC.rbeam(b, (0, 0, -10.1), (0, 0, -14.4), 1.5, 1.66, "haft", k=0.8, uv=5)
    haft += WC.rbeam(b, (0, 0, -14.3), (0, 0, -18.02), 1.38, 1.52, "haft", k=0.8, uv=6)
    add_fx(haft, world=WC.compose(
        WC.paint_band(-10.6, -12.0, book.pal(2), seed=81, chip=0.34),
        WC.crack((0.7, 0.2, -2.3), (0.7, -0.25, -6.7), width=0.05, seed=82, wiggle=0.16, normal=(1, 0, 0)),
        WC.crack((0.0, 0.78, -1.6), (0.0, 0.78, -4.2), width=0.04, seed=83, wiggle=0.12, normal=(0, 1, 0)),
        grime((-0.8, -2.6), (-6.6, -9.4), dark=0.7, seed=84)))
    # 割れの補修: 灰色のテープと、締め上げた針金
    wrap(b, (0, 0, -2.9), (0, 0, -4.3), (1.56, 1.7), "tape", pitch=0.7, tilt=8, seed=85, uv=8,
         tail=(0.6, (0.35, -1.0, 0.2)))
    coil(b, (0, 0, -5.65), (0, 0, 1), 1.66, 0.95, 3, "wire", wire=0.12, uv=12)
    # 左手の位置の黄色いテープ
    wrap(b, (0, 0, -7.05), (0, 0, -9.0), (1.54, 1.69), "band", pitch=0.5, tilt=11, seed=86, uv=8)
    # 打ち損じの保護スリーブ（鉄板を巻いてホースバンドで締める）
    WC.rbeam(b, (0, 0, -12.5), (0, 0, -14.3), 1.66, 1.8, "collar", k=0.8, uv=7)
    hose_clamp(b, -12.85, (1.78, 1.92), "clamp", side=1)
    hose_clamp(b, -13.9, (1.78, 1.92), "clamp", side=-1)
    # ---- 頭: 縦長の八角。面取りの段、めくれた打撃面、楔、打刻、打痕 ----
    hz = -16.0
    k8 = 1.0 / math.cos(math.radians(22.5))            # 八角の対辺 → 外接円の半径
    head = WC.octo(b, (0, 0, hz), (0, 1, 0), 1.7 * k8, 5.72, "head", uv=7)
    for s in (-1, 1):
        head += WC.octo(b, (0, s * 2.99, hz), (0, 1, 0), 1.54 * k8, 0.32, "head", uv=8)
    low = WC.octo(b, (0, -3.39, hz), (0, 1, 0), 1.78 * k8, 0.58, "face_low", uv=8)
    high = WC.octo(b, (0, 3.35, hz), (0, 1, 0), 1.73 * k8, 0.5, "face_high", uv=8)
    for c, sz, r in (((1.72, -3.5, hz + 0.6), (0.24, 0.3, 0.5), (0, 20, 15)),
                     ((-0.6, -3.52, hz - 1.74), (0.5, 0.26, 0.22), (10, -15, 0)),
                     ((-1.62, -3.48, hz + 1.0), (0.22, 0.28, 0.42), (0, 35, -10))):
        low.append(cbox(b, c, sz, "face_low", rot=r, uv=12))                      # めくれ（バリ）
    add_fx(head, world=WC.compose(WC.stamp("10LB", (hz, 1.05), 0.78, mul=0.45),
                                  WC.stamp("FORGE", (hz, -0.25), 0.5, mul=0.55),
                                  WC.pock(87, cell=0.8, r=0.28, frac=0.55)))
    add_fx(low + high, world=WC.pock(88, cell=0.6, r=0.2, frac=0.6, dark=0.7))
    # 目から出た柄の木口と楔（斜めの鉄の楔と丸い楔）
    cbox(b, (0, 0, -18.1), (1.64, 0.3, 0.3), "wedge", rot=(0, 0, 32), uv=12)
    disc(b, (0.36, -0.44, -18.08), (0, 0, 1), 0.24, 0.2, "wedge", n=2, uv=12)
    # ---- 下の打撃面: 肉片・脳片・骨のかけら・髪 ----
    for c, sz, r in (((0.6, -3.8, hz + 0.4), (0.9, 0.36, 0.8), (10, 20, 5)),
                     ((-0.7, -3.76, hz - 0.8), (0.7, 0.3, 0.62), (-8, 40, 0)),
                     ((0.1, -3.72, hz - 0.1), (0.52, 0.26, 0.5), (0, 10, 12))):
        cbox(b, c, sz, "meat", rot=r, uv=12)
    cbox(b, (1.14, -3.7, hz - 0.92), (0.44, 0.24, 0.36), "brain", rot=(0, 30, 0), uv=12)
    cbox(b, (-1.12, -3.66, hz + 1.0), (0.36, 0.2, 0.3), "bonechip", rot=(0, -20, 10), uv=12)
    hairs(b, 1.7, (-2.5, hz), 4, 1.5, "hair", seed=89, side=1)
    hairs(b, -1.7, (-2.7, hz + 0.3), 3, 1.3, "hair", seed=90, side=-1)
    book.add("grip", "rubber_black", dirt=0.4)
    book.add("haft", "wood_old", base=book.pal(1), dirt=0.45, grain=1.4)
    book.add("tape", "tape_grey", dirt=0.6)
    book.add("band", "tape_grey", base=book.pal(2), dirt=0.5)
    book.add("wire", "steel_worn", base=(132, 130, 124), dirt=0.5)
    book.add("collar", "steel_worn", base=(116, 118, 120), dirt=0.5)
    book.add("clamp", "steel_clean", base=(172, 174, 176), dirt=0.3)
    book.add("head", "steel_dark", base=book.pal(0), wear=0.9, dirt=0.35)
    book.add("face_low", "steel_clean", base=book.pal(3))
    book.add("face_high", "steel_worn", base=book.pal(3), dirt=0.3)
    book.add("wedge", "steel_rusty", amount=0.8)
    book.add("meat", "gore_meat")
    book.add("brain", "gore_meat", base=(198, 150, 146))
    book.add("bonechip", "bone")
    book.raw("hair", NP.style("hair", base=(44, 32, 24), style="matted"))
    blood = spec_blood(w, amount=0.62, grow=0.4) + [
        WC.blood_zone((-1.9, -3.4, hz - 1.9), (1.9, -0.6, hz + 1.9), 0.35, "wet", soft=0.8),
        WC.blood_zone((-0.9, -0.9, -14.4), (0.9, 0.9, -11.8), 0.28, "dry", soft=0.6)]
    return Built(wm, book, blood, hold=dict(grip=0.5, scale=0.85))


@builder("rebar_club")
def b_rebar_club(w) -> Built:
    wm = WC.WeaponModel("rebar_club", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # ---- 鉄筋 2 本: 1 本目は尻から塊まで（少し曲がる）、2 本目は途中から並走して塊へ曲がり込む ----
    r1 = [(0, 0, 5.3), (0, 0, -0.6), (0.06, 0.14, -7.4), (0.16, 0.06, -13.6)]
    for i in range(3):
        rod(b, r1[i], r1[i + 1], 1.0, "rebar", fx={"rebar": 0.46}, uv=7)
    for i in (1, 2):                                   # 縦の節（両側の筋）
        for s in (-1, 1):
            beam(b, np.add(r1[i], (s * 0.5, 0, 0)), np.add(r1[i + 1], (s * 0.5, 0, 0)), 0.16, 0.22, "rebar",
                 uv=10)
    r2 = [(0.95, 0.28, -2.9), (0.94, 0.3, -9.6), (1.24, 0.0, -13.8)]
    for i in range(2):
        rod(b, r2[i], r2[i + 1], 0.8, "rebar", fx={"rebar": 0.4}, uv=8)
    cbox(b, (0.95, 0.28, -2.84), (0.84, 0.84, 0.1), "cut", uv=12)                    # 切り口
    # ---- 握り: 布を巻いた上にダクトテープ。尻は溶接したナット ----
    wrap(b, (0, 0, -0.75), (0, 0, 4.35), 1.5, "tape", pitch=0.62, tilt=10, seed=101, uv=8,
         tail=(0.7, (0.3, -1.0, 0.1)))
    wrap(b, (0, 0, 4.3), (0, 0, 4.95), 1.36, "cloth", pitch=0.65, tilt=4, seed=102, uv=9)
    rag(b, (0.25, -0.62, 4.7), 1.3, 0.5, "cloth", hang=(0.25, -1.0, 0.45), strips=1, seed=103)
    hex_prism(b, (0, 0, 5.36), (0, 0, 1), 1.5, 0.72, "nut", uv=10)
    weld(b, [(-0.62, 0.62, 5.0), (0.62, 0.62, 5.0)], 0.32, "weld", seed=104, uv=12)
    weld(b, [(0.62, -0.62, 5.0), (-0.62, -0.62, 5.0)], 0.3, "weld", seed=105, uv=12)
    # ---- 結束線（2 本をまとめて 2 周、ねじった端が立つ） ----
    for z in (-6.0, -10.2):
        lash(b, (0.44, 0.15, z), (0, 0, 1), 2.0, 1.28, 0.5, 2, "wire", wire=0.13, uv=12)
        polyline(b, [(1.5, 0.82, z), (1.85, 1.1, z + 0.2), (2.05, 1.45, z + 0.12)], 0.13, 0.13, "wire",
                 overlap=0.06, uv=12)
    # ---- 割れたコンクリの塊（回した箱を重ねて角の欠けた塊に）と、くっついた小塊 ----
    cc = np.array([0.3, -0.2, -15.7])
    chunk = [cbox(b, cc, (4.6, 4.2, 5.4), "concrete", rot=(6, 10, -4), uv=6),
             cbox(b, cc + (-0.2, -0.3, 0.4), (4.0, 4.5, 4.2), "concrete", rot=(-8, -14, 10), uv=6),
             cbox(b, cc + (0.3, 0.25, -0.5), (3.7, 3.5, 5.6), "concrete", rot=(18, 4, -16), uv=6),
             cbox(b, cc + (1.2, -1.3, 1.6), (2.6, 2.4, 2.4), "concrete", rot=(32, 24, 10), uv=7),
             cbox(b, cc + (-0.3, -1.9, -0.6), (3.0, 1.6, 3.4), "concrete", rot=(-5, 30, 0), uv=7)]
    small = [cbox(b, (-1.4, 1.4, -17.7), (3.2, 3.0, 3.0), "concrete2", rot=(-12, 20, 8), uv=7),
             cbox(b, (-1.9, 1.9, -18.6), (2.0, 2.0, 1.9), "concrete2", rot=(25, -10, 30), uv=7)]
    add_fx(chunk, world=WC.compose(aggregate(106), WC.crack((2.4, 1.6, -13.4), (1.0, -2.0, -18.2), width=0.06,
                                                             seed=107, wiggle=0.3),
                                   WC.pock(108, cell=0.7, r=0.2, frac=0.4, dark=0.75)))
    add_fx(small, world=WC.compose(aggregate(109, cell=0.55, r=0.2), WC.pock(110, cell=0.7, r=0.2, frac=0.4)))
    # 表面に飛び出た骨材の小石
    allc = chunk + small
    for i, dv in enumerate(((1, 0.3, 0.2), (0.2, 1, 0.3), (-1, -0.3, -0.2), (0.5, -1, -0.4), (0.3, 0.2, -1),
                            (-0.6, 0.8, -0.6))):
        p = WC.surface_point(allc, cc, dv, sink=0.12)
        s = 0.42 + 0.06 * (i % 3)
        cbox(b, p, (s, s * 0.8, s * 0.9), "pebble", rot=(17 * i, 31 * i, 11 * i), uv=12)
    # 塊から突き出た鉄筋（曲がる）2 本
    for pts in (((0.9, -0.9, -17.2), (1.45, -1.4, -19.1), (2.15, -1.2, -20.0)),
                ((0.3, 1.2, -16.4), (0.55, 2.9, -17.0), (1.25, 3.35, -16.85))):
        for i in range(2):
            rod(b, pts[i], pts[i + 1], 0.6, "rebar", fx={"rebar": 0.36}, uv=10)
    rag(b, (1.5, -1.45, -19.2), 1.4, 0.6, "cloth", hang=(0.3, -1.0, 0.3), strips=1, seed=111)
    # 下面の肉片と歯
    for i, dv in enumerate(((0.2, -1, 0.3), (-0.4, -1, -0.2), (0.6, -1, -0.5))):
        p = WC.surface_point(allc, cc, dv, sink=0.15)
        cbox(b, p, (0.8 - 0.15 * i, 0.4, 0.65), "meat", rot=(10 * i, 25 * i + 10, 6), uv=12)
    cbox(b, WC.surface_point(allc, cc, (-0.1, -1, 0.0), sink=0.1), (0.24, 0.36, 0.26), "tooth", rot=(20, 0, 15),
         uv=12)
    book.raw("rebar", NP.style("rust", base=book.pal(1), amount=0.72, metal=(86, 80, 74), wear=0.2, dirt=0.55))
    book.add("cut", "steel_clean", base=(168, 164, 158))
    book.add("tape", "tape_grey", base=(150, 150, 146), dirt=0.62)
    book.add("cloth", "cloth_rag", dirt=0.65)
    book.add("nut", "steel_worn", base=(120, 118, 114), dirt=0.5)
    book.add("weld", "steel_dark", base=(76, 68, 60), wear=0.3, dirt=0.4)
    book.add("wire", "steel_worn", base=(150, 150, 146), dirt=0.35)
    book.add("concrete", "concrete", base=book.pal(0))
    book.add("concrete2", "concrete_dark", base=book.pal(2))
    book.add("pebble", "concrete", base=(128, 120, 108), cracks=0.0)
    book.add("meat", "gore_meat")
    book.add("tooth", "bone", base=(226, 214, 186))
    blood = spec_blood(w, amount=0.6, grow=0.35) + [
        WC.blood_zone((-0.4, -3.6, -19.4), (3.0, -0.6, -15.0), 0.45, "wet", soft=0.8),
        WC.blood_zone((-2.6, -1.0, -20.0), (2.8, 3.6, -17.5), 0.22, "dry", soft=1.0)]
    return Built(wm, book, blood, hold=dict(grip=1.5, scale=0.85))


# 道路標識の板（柱の -X 面に裏を当てる）。八角形を半分に切った形で、下の 3 辺を研いで刃にする
SIGN_X = -0.93          # 赤い板の中心 x
SIGN_Y = (0.5, -6.1)    # 上の端（柱の横まで）, 下の刃の線
SIGN_Z = (-13.6, -21.6)  # 柄の側, 先
SIGN_CH = 2.34          # 八角の面取り（正八角形の比 = 幅 × 0.293）
SIGN_EB = 0.44          # 研いだ帯の幅


def _sign_sdf(inset):
    """標識の板の輪郭（局所: y = 0 が刃の線、z = 0 が先の端）。inset は下の 3 辺を内へ寄せる量。"""
    L = SIGN_Z[0] - SIGN_Z[1]
    s2 = math.sqrt(2.0)

    def fn(Lr, size):
        y, z = Lr[:, 1], Lr[:, 2]
        d = np.maximum(-z, z - L)
        d = np.maximum(d, -y + inset)
        d = np.maximum(d, (SIGN_CH - z - y) / s2 + inset)
        d = np.maximum(d, (SIGN_CH - (L - z) - y) / s2 + inset)
        return d
    return fn


@builder("sign_axe")
def b_sign_axe(w) -> Built:
    wm = WC.WeaponModel("sign_axe", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # ---- 柱: 角を丸めた角管、等間隔の穴の列。先は開いた端、尻と左手に黒テープ ----
    post = WC.rbeam(b, (0, 0, 5.15), (0, 0, -21.0), 1.4, 1.4, "post", k=0.86, fx={"holes": (1.5, 0.36)}, uv=6)
    add_fx(post, world=tube_end(-21.0, (0.7, 0.7), wall=0.12))
    wrap(b, (0, 0, -1.3), (0, 0, 4.9), (1.56, 1.56), "tape", pitch=0.66, tilt=9, seed=111, round_=False, uv=8,
         tail=(0.7, (0.3, -1.0, 0.2)))
    cbox(b, (0, 0, 5.2), (1.6, 1.6, 0.3), "tape", uv=8)
    wrap(b, (0, 0, -8.0), (0, 0, -10.0), (1.56, 1.56), "tape", pitch=0.66, tilt=-8, seed=112, round_=False, uv=8)
    # 有刺鉄線を柱に巻く（棘は短い棒の十字）
    coil(b, (0, 0, -11.8), (0, 0, 1), 1.72, 1.5, 3, "barb", wire=0.12, uv=12)
    for i, (x, y, z) in enumerate(((0.92, 0.3, -11.3), (-0.92, -0.2, -11.8), (0.2, 0.93, -12.3), (-0.3, -0.93, -11.5))):
        cbox(b, (x, y, z), (0.08, 0.5, 0.08), "barb", rot=(35, 20 * i, 40), uv=12)
    # ---- 標識の板: 赤い表（白い縁・白文字「ST」・反射材の粒・弾痕）とアルミの裏（落書き） ----
    yt, yb = SIGN_Y
    zn, zf = SIGN_Z
    hgt, lng = yt - yb, zn - zf
    cy, cz = (yt + yb) / 2, (zn + zf) / 2
    face = cbox(b, (SIGN_X, cy, cz), (0.26, hgt, lng), "sign", uv=8)
    face.fx = {"sdf": _sign_sdf(SIGN_EB), "border": ((236, 234, 226), 0.34),
               "world": WC.compose(WC.stamp("ST", (cz + 0.15, -2.55), 2.2, tint=(236, 234, 226), side=-1),
                                   beads(113, side=-1, amount=0.1), WC.pock(114, cell=1.1, r=0.3, frac=0.3,
                                                                            dark=0.8))}
    back = cbox(b, (SIGN_X + 0.16, cy, cz), (0.06, hgt, lng), "back", uv=8)
    back.fx = {"sdf": _sign_sdf(SIGN_EB),
               "world": graffiti((40, 150, 70), [[(zn - 0.8, -2.0), (zn - 1.6, -3.6), (zn - 2.4, -2.2),
                                                  (zn - 3.2, -3.8), (zn - 4.0, -2.4)],
                                                 [(zn - 4.6, -4.4), (zn - 5.6, -2.6), (zn - 6.2, -4.2)]],
                                 side=1, width=0.17)}
    wm.cut((SIGN_X, -4.4, -19.1), (1, 0, 0), r=0.2, half=0.32, rim=0.16)            # 弾痕
    wm.cut((SIGN_X, -2.0, -15.6), (1, 0, 0), r=0.16, half=0.32, rim=0.14)
    # 研いだ下の 3 辺（刃）: 板より薄い銀の帯。局所 -Y が刃の線
    pts = [(yb + SIGN_CH, zn), (yb, zn - SIGN_CH), (yb, zf + SIGN_CH), (yb + SIGN_CH, zf)]
    edges = []
    for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
        d = np.array([0.0, y1 - y0, z1 - z0])
        n_in = np.array([0.0, -(z1 - z0), y1 - y0])
        n_in /= np.linalg.norm(n_in)
        if n_in[1] < 0:
            n_in = -n_in
        off = n_in * (SIGN_EB / 2 + 0.02)
        p0 = np.array([SIGN_X, y0, z0]) + off
        p1 = np.array([SIGN_X, y1, z1]) + off
        c = beam(b, p0, p1, 0.12, SIGN_EB + 0.08, "edge", up=n_in, extend=0.16, uv=12, tags=("edge",))
        c.bt = (0.0, 0.12)
        edges.append(c)
        del d
    chips_on(edges, [(-15.2, 0.3, 0.22), (-17.9, 0.22, 0.16), (-20.2, 0.32, 0.26)])
    # 留め金具: 柱の上をまたぐ帯と脚、板と柱を貫くボルト（丸い頭と六角ナット）
    for zc in (-15.4, -19.8):
        beam(b, (SIGN_X - 0.16, 0.86, zc), (0.86, 0.86, zc), 1.0, 0.3, "bracket", uv=9)
        beam(b, (0.86, 1.0, zc), (0.86, -1.2, zc), 1.0, 0.3, "bracket", up=(1, 0, 0), uv=9)
        beam(b, (SIGN_X - 0.28, 1.0, zc), (SIGN_X - 0.28, -1.32, zc), 1.0, 0.3, "bracket", up=(1, 0, 0), uv=9)
        beam(b, (SIGN_X - 0.5, -1.0, zc), (1.16, -1.0, zc), 0.3, 0.3, "bolt", uv=12)
        disc(b, (SIGN_X - 0.5, -1.0, zc), (1, 0, 0), 0.3, 0.16, "bolt", n=2, uv=12)
        hex_prism(b, (1.08, -1.0, zc), (1, 0, 0), 0.56, 0.24, "bolt", uv=12)
    # 板を柱に留めたねじ、裏に当てた山形鋼（鋲で留める）
    for z in (-14.35, -17.6, -20.85):
        rivet(b, (SIGN_X - 0.13, 0.05, z), (-1, 0, 0), d=0.42, h=0.1, style="bolt", uv=12)
    beam(b, (SIGN_X + 0.25, -2.3, -14.6), (SIGN_X + 0.25, -2.3, -20.6), 0.24, 0.9, "angle", uv=9)
    beam(b, (SIGN_X + 0.6, -2.62, -14.6), (SIGN_X + 0.6, -2.62, -20.6), 0.82, 0.24, "angle", uv=9)
    for z in (-15.0, -17.6, -20.2):
        rivet(b, (SIGN_X - 0.13, -2.3, z), (-1, 0, 0), d=0.36, h=0.08, style="bolt", uv=12)
    hairs(b, SIGN_X - 0.13, (-5.5, -17.0), 3, 1.3, "hair", seed=115, side=-1)
    cbox(b, (SIGN_X, SIGN_Y[1] - 0.06, -16.9), (0.5, 0.36, 0.7), "meat", rot=(0, 10, 12), uv=12)
    book.add("post", "steel_painted", base=book.pal(2), wear=0.5, rust=0.45)
    book.add("tape", "tape_black", base=book.pal(3))
    book.add("barb", "steel_rusty", amount=0.55, metal=(140, 140, 136))
    book.add("sign", "steel_painted", base=book.pal(0), wear=0.18, rust=0.15, dirt=0.35)
    book.add("back", "aluminium", base=(176, 180, 182), dirt=0.45)
    book.add("edge", "steel_clean", base=(200, 204, 206))
    book.add("bracket", "steel_rusty", amount=0.8)
    book.add("bolt", "steel_worn", base=(128, 130, 132), dirt=0.45)
    book.add("angle", "steel_rusty", amount=0.6, metal=(110, 108, 104))
    book.add("meat", "gore_meat")
    book.raw("hair", NP.style("hair", base=(58, 40, 26), style="matted"))
    blood = spec_blood(w, amount=0.55, grow=0.35) + [
        WC.blood_zone((SIGN_X - 0.4, -6.6, -21.4), (SIGN_X + 0.4, -3.4, -13.8), 0.4, "wet", soft=0.8),
        WC.blood_zone((SIGN_X - 0.4, -4.0, -19.5), (SIGN_X + 0.4, -1.0, -15.0), 0.16, "wet", soft=1.4, drip=0.6)]
    return Built(wm, book, blood, hold=dict(grip=-0.2, scale=0.82))


@builder("piston_hammer")
def b_piston_hammer(w) -> Built:
    wm = WC.WeaponModel("piston_hammer", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # ---- 柄: 太い鉄パイプ。尻はねじ込みのキャップ、革巻きの握り、補強スリーブの溶接、緩衝のバルブスプリング ----
    pipe = rod(b, (0, 0, 5.2), (0, 0, -12.4), 1.5, "pipe", uv=6)
    add_fx(pipe, world=WC.compose(WC.stamp("SCH80", (-4.6, 0.0), 0.5, mul=0.55),
                                  WC.pock(121, cell=1.0, r=0.22, frac=0.4, dark=0.72)))
    rod(b, (0, 0, 5.1), (0, 0, 5.75), 1.58, "pipe", fx={"ribs": 0.16}, uv=10)       # ねじ山
    rod(b, (0, 0, 5.6), (0, 0, 6.45), 1.92, "cap", uv=8)                            # パイプキャップ
    disc(b, (0, 0, 6.52), (0, 0, 1), 0.62, 0.16, "cap", n=2, uv=10)
    wrap(b, (0, 0, -0.9), (0, 0, 5.0), 1.78, "leather", pitch=0.72, tilt=14, seed=122, uv=8,
         tail=(1.0, (0.25, -1.0, 0.35)))
    rod(b, (0, 0, -6.6), (0, 0, -9.4), 1.86, "sleeve", uv=7)
    for z, a0 in ((-6.55, 200.0), (-9.45, 20.0)):
        ring = [(0.98 * math.cos(math.radians(a0 + 32 * k)), 0.98 * math.sin(math.radians(a0 + 32 * k)), z)
                for k in range(6)]
        weld(b, ring, 0.32, "weld", seed=int(-z * 10), step=0.5, uv=12)
    coil(b, (0, 0, -11.05), (0, 0, 1), 2.0, 1.8, 4, "spring", wire=0.2, uv=10)
    # ---- 継ぎ目: パイプを溶接したフランジ ----
    disc(b, (0, 0, -12.45), (0, 0, 1), 1.08, 0.5, "flange", n=2, uv=9)
    ring = [(0.84 * math.cos(math.radians(30 + 45 * k)), 0.84 * math.sin(math.radians(30 + 45 * k)), -12.15)
            for k in range(5)]
    weld(b, ring, 0.3, "weld", seed=123, step=0.55, uv=12)
    # ---- コンロッド: 大端（軸 = X、真鍮の軸受けとピンが覗く、キャップのボルト 2 本）→ I 断面 → ピストンへ ----
    BE = -13.7
    big = disc(b, (0, 0, BE), (1, 0, 0), 1.42, 1.3, "rod", n=3, uv=8)
    add_fx(big, world=zline(BE, w=0.045))
    disc(b, (0, 0, BE), (1, 0, 0), 0.8, 1.44, "brass", n=2, uv=10)
    disc(b, (0, 0, BE), (1, 0, 0), 0.48, 1.62, "pin", n=2, uv=12)
    for s in (-1, 1):
        rod(b, (0, s * 1.2, BE + 1.3), (0, s * 1.2, BE - 1.15), 0.34, "bolt", uv=12)
        hex_prism(b, (0, s * 1.2, BE + 1.15), (0, 0, 1), 0.66, 0.36, "bolt", uv=12)
    cbox(b, (0, 1.5, BE - 0.2), (0.3, 0.3, 0.3), "brass", uv=12)                   # グリスニップル
    for s in (-1, 1):
        beam(b, (0, s * 0.84, BE - 0.9), (0, s * 0.5, -18.3), 1.02, 0.3, "rod", uv=8)
    beam(b, (0, 0, BE - 0.9), (0, 0, -16.2), 0.42, 1.56, "rod", uv=8)
    beam(b, (0, 0, -16.1), (0, 0, -18.3), 0.42, 1.14, "rod", uv=8)
    # ---- ピストン: 12 角の胴・リング 3 本・一段小さい冠面（打撃面）・ピストンピンの端 ----
    PZ0, PZ1 = -17.9, -22.4
    k8 = 1.0 / math.cos(math.radians(22.5))
    piston = WC.octo(b, (0, 0, (PZ0 + PZ1) / 2), (0, 0, 1), 2.2 * k8, abs(PZ1 - PZ0), "piston", uv=7)
    rings = WC.octo(b, (0, 0, -21.62), (0, 0, 1), 2.26 * k8, 0.3, "ring", uv=10)     # トップリング
    crown = WC.octo(b, (0, 0, -22.68), (0, 0, 1), 2.0 * k8, 0.6, "crown", uv=8)
    disc(b, (0, 0, -19.0), (1, 0, 0), 0.55, 4.5, "pin", n=2, uv=10)

    def grooves(P, N, L, size, col):
        side = np.abs(N[:, 2]) < 0.6
        out = col
        for z in (-20.55, -21.05):                    # 2 本目のリングとオイルリングの溝
            m = side & (np.abs(P[:, 2] - z) < 0.11)
            hi = side & (P[:, 2] - z > 0.11) & (P[:, 2] - z < 0.2)
            out = np.where(m[:, None], out * 0.32, out)
            out = np.where(hi[:, None], np.minimum(255, out * 1.15 + 8), out)
        return out

    def valves(P, N, L, size, col):
        ok = N[:, 2] < -0.7
        out = col
        for cx, cy, r in ((-0.78, -0.45, 0.62), (0.78, -0.45, 0.62)):
            d = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
            out = np.where((ok & (np.abs(d - r) < 0.06))[:, None], out * 0.5, out)
            out = np.where((ok & (d < r - 0.06))[:, None], out * 0.86, out)
        return out
    add_fx(piston, world=WC.compose(soot(-22.4, -19.6, dark=0.35, seed=124), grooves,
                                    WC.stamp("NR-V8", (-18.7, 1.25), 0.42, mul=0.55)))
    add_fx(crown, world=WC.compose(soot(-23.0, -22.3, dark=0.2, seed=125), valves,
                                   WC.stamp_on("STD", (0.0, 0.72, -23.0), 0.5, normal=(0, 0, -1), mul=0.5),
                                   WC.pock(126, cell=0.7, r=0.22, frac=0.55, dark=0.65)))
    add_fx(rings, world=soot(-22.2, -20.4, dark=0.5, seed=127))
    # ---- 冠面の肉片・脳片・骨片、側面の髪 ----
    for c, sz, r in (((0.7, 0.3, -23.08), (0.9, 0.8, 0.34), (5, 10, 20)),
                     ((-0.8, -0.9, -23.06), (0.7, 0.6, 0.3), (-10, 5, -15)),
                     ((0.2, -1.4, -22.95), (0.6, 0.5, 0.3), (0, -12, 30))):
        cbox(b, c, sz, "meat", rot=r, uv=12)
    cbox(b, (-0.5, 0.9, -23.02), (0.5, 0.42, 0.26), "brain", rot=(0, 0, 25), uv=12)
    cbox(b, (1.3, -0.6, -23.0), (0.3, 0.36, 0.2), "bonechip", rot=(0, 0, 40), uv=12)
    hairs(b, 2.2, (-0.4, -21.0), 3, 1.4, "hair", seed=128, side=1)
    book.add("pipe", "steel_worn", base=(118, 120, 120), scratches=0.6, dirt=0.5)
    book.add("cap", "iron_cast", base=(74, 72, 72))
    book.add("leather", "leather_brown", base=(92, 60, 36), dirt=0.45)
    book.add("sleeve", "steel_dark", base=book.pal(0), wear=0.8, dirt=0.4)
    book.add("weld", "steel_dark", base=(82, 72, 62), wear=0.3, dirt=0.45)
    book.add("spring", "steel_dark", base=(70, 72, 76), wear=0.7)
    book.add("flange", "steel_rusty", amount=0.65, metal=(100, 100, 100))
    book.add("rod", "steel_dark", base=book.pal(0), wear=0.85, dirt=0.35)
    book.add("brass", "brass", base=book.pal(2))
    book.add("pin", "steel_clean", base=(186, 190, 192))
    book.add("bolt", "steel_worn", base=(122, 124, 126), dirt=0.4)
    book.add("piston", "aluminium", base=(176, 178, 176), dirt=0.4)
    book.add("ring", "steel_dark", base=(48, 48, 50))
    book.add("crown", "steel_dark", base=book.pal(3), wear=0.6, dirt=0.3)
    book.add("meat", "gore_meat")
    book.add("brain", "gore_meat", base=(196, 150, 146))
    book.add("bonechip", "bone")
    book.raw("hair", NP.style("hair", base=(34, 28, 24), style="matted"))
    blood = spec_blood(w, amount=0.6, grow=0.3) + [
        WC.blood_zone((-2.4, -2.4, -22.6), (2.4, 2.4, -20.2), 0.3, "wet", soft=0.9, drip=1.2),
        WC.blood_zone((-1.5, -1.5, -15.0), (1.5, 1.5, -12.5), 0.18, "dry", soft=1.0)]
    return Built(wm, book, blood, hold=dict(grip=0.5, scale=0.85))


# ===========================================================================
#  槍（突き）
# ===========================================================================
@builder("rebar_spear")
def b_rebar_spear(w) -> Built:
    wm = WC.WeaponModel("rebar_spear", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # ---- 柄: 節の斜線のある鉄筋（少したわむ）。尻に松葉杖のゴム先 ----
    sh = [(0, 0, 6.1), (0, 0.05, -0.8), (0, 0.13, -8.0), (0, 0.15, -15.0), (0, 0.07, -22.2)]
    for i in range(4):
        rod(b, sh[i], sh[i + 1], 1.0, "rebar", fx={"rebar": 0.46}, uv=6)
    for i in (2, 3):
        for s in (-1, 1):
            beam(b, np.add(sh[i], (s * 0.5, 0, 0)), np.add(sh[i + 1], (s * 0.5, 0, 0)), 0.16, 0.22, "rebar",
                 uv=9)
    rod(b, (0, 0, 5.6), (0, 0, 7.0), 1.46, "rubber", fx={"ribs": 0.3}, uv=8)
    disc(b, (0, 0, 7.08), (0, 0, 1), 0.62, 0.18, "rubber", n=2, uv=10)
    # ---- 握り（右手のテープ）と左手の布巻き ----
    wrap(b, (0, 0.02, -0.6), (0, 0.02, 3.8), 1.36, "tape", pitch=0.55, tilt=10, seed=131, uv=8,
         tail=(0.6, (0.25, -1.0, 0.2)))
    wrap(b, (0, 0.13, -6.4), (0, 0.13, -9.6), 1.44, "cloth", pitch=0.64, tilt=16, seed=132, uv=8,
         tail=(1.0, (0.2, -1.0, 0.35)))
    # ---- 穂先: 鉄筋の端をグラインダーで四角錐に研ぎ出す（銀の削り跡）----
    pz = [(-22.0, 0.98), (-23.2, 0.86), (-24.3, 0.68), (-25.3, 0.5), (-26.2, 0.34), (-26.95, 0.2), (-27.55, 0.08)]
    point = []
    for i in range(len(pz) - 1):
        (z0, d0), (z1, d1) = pz[i], pz[i + 1]
        dd = (d0 + d1) / 2
        point.append(beam(b, (0, 0.07, z0 + 0.05), (0, 0.07, z1 - 0.02), dd, dd, "grind" if i < 2 else "point",
                          roll=45.0, uv=12))

    def grind(P, N, L, size, col):
        n = NP.fbm3(P[:, 0] * 14.0, P[:, 1] * 14.0, P[:, 2] * 0.8, 133, octaves=2)
        m = n > 0.62
        return np.where(m[:, None], np.minimum(255, col * 1.22 + 18), col)
    add_fx(point, world=grind)
    # ---- 返し: 曲げた釘 2 本を後ろ向きに沿わせて針金で縛る ----
    for s in (-1, 1):
        nail(b, (s * 0.24, 0.55, -21.9), (s * 0.85, 1.45, -20.1), "nail", d=0.2, uv=12)
    coil(b, (0, 0.2, -21.45), (0, 0, 1), 1.3, 0.9, 3, "wire", wire=0.12, uv=12)
    # ---- 結んだ赤い布切れ ----
    WC.rbeam(b, (0, 0.12, -19.55), (0, 0.12, -20.15), 1.3, 1.3, "flag", k=0.8, uv=9)
    cbox(b, (0, -0.62, -19.85), (0.62, 0.5, 0.5), "flag", rot=(0, 20, 0), uv=10)
    rag(b, (0, -0.7, -19.85), 2.6, 1.1, "flag", hang=(0.1, -1.0, 0.3), strips=2, spread=0.45, seed=134)
    book.raw("rebar", NP.style("rust", base=book.pal(0), amount=0.72, metal=(86, 80, 74), wear=0.2, dirt=0.55))
    book.add("rubber", "rubber_black", dirt=0.45)
    book.add("tape", "tape_grey", base=book.pal(2), dirt=0.6)
    book.add("cloth", "cloth_rag", dirt=0.7)
    book.add("grind", "steel_worn", base=book.pal(1), scratches=0.9, dirt=0.2)
    book.add("point", "steel_clean", base=(198, 202, 204))
    book.add("nail", "steel_rusty", amount=0.5, metal=(140, 138, 132))
    book.add("wire", "steel_worn", base=(140, 140, 136), dirt=0.4)
    book.add("flag", "cloth_red", base=book.pal(3), dirt=0.5)
    blood = spec_blood(w, amount=0.7, grow=0.3) + [
        WC.blood_zone((-0.8, -0.8, -22.4), (0.8, 0.8, -19.5), 0.3, "wet", soft=0.7, drip=1.4),
        WC.blood_zone((-1.0, -3.6, -21.4), (1.0, -0.6, -18.2), 0.25, "dry", soft=1.0)]
    return Built(wm, book, blood, hold=dict(grip=1.1, scale=0.85))


@builder("pitchfork")
def b_pitchfork(w) -> Built:
    wm = WC.WeaponModel("pitchfork", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # ---- 柄: 古い木（少し反る）、手の当たる所が黒ずむ、焼き印、割れをテープで ----
    hd = [(0, 0, 4.75), (0, 0.04, -3.0), (0, 0.1, -10.5), (0, 0.06, -17.4)]
    handle = []
    for i in range(3):
        handle += rod(b, hd[i], hd[i + 1], 1.1, "handle", uv=6)
    add_fx(handle, world=WC.compose(grime((-1.6, 2.4), (-10.6, -7.4), dark=0.6, seed=141),
                                    WC.stamp("NR FARM", (-4.4, 0.04), 0.46, mul=1.0, tint=(52, 32, 18)),
                                    WC.crack((0.56, 0.1, -9.6), (0.56, 0.0, -14.6), width=0.05, seed=142,
                                             wiggle=0.14, normal=(1, 0, 0))))
    wrap(b, (0, 0.08, -11.5), (0, 0.08, -12.9), 1.24, "tape", pitch=0.7, tilt=8, seed=143, uv=8,
         tail=(0.5, (0.3, -1.0, 0.2)))
    # ---- D 字の握り（割った柄を金輪で締め、横木を鋲で留める） ----
    rod(b, (0, 0, 4.5), (0, 0, 5.25), 1.32, "ferrule", uv=9)
    for s in (-1, 1):
        polyline(b, [(s * 0.3, 0, 5.0), (s * 1.12, 0, 6.35), (s * 1.18, 0, 7.5)], 0.62, 0.84, "dwood", overlap=0.25,
                 uv=7)
        rivet(b, (s * 1.18, 0.42, 7.5), (0, 1, 0), d=0.36, h=0.1, style="ferrule", uv=12)
    rod(b, (-1.6, 0, 7.66), (1.6, 0, 7.66), 0.9, "dwood", uv=7)
    # ---- 口金（柄を受ける金具、鋲、割れ止めの針金）と首 ----
    rod(b, (0, 0.06, -16.6), (0, 0.06, -17.5), 1.22, "socket", uv=8)
    rod(b, (0, 0.06, -17.4), (0, 0.06, -19.4), 1.42, "socket", uv=8)
    rod(b, (0, 0.06, -19.3), (0, 0.06, -20.3), 1.1, "socket", uv=8)
    for s in (-1, 1):
        rivet(b, (s * 0.71, 0.06, -18.3), (s, 0, 0), d=0.42, h=0.1, style="rivet", uv=12)
    coil(b, (0, 0.06, -16.95), (0, 0, 1), 1.34, 0.55, 2, "wire", wire=0.11, uv=12)
    # ---- 横棒（爪の付け根、少し反る）と 4 本の爪（先が上へ反る。1 本は外へ曲がる） ----
    yk = [(-2.62, 0.06, -21.05), (-1.3, 0.06, -20.6), (0, 0.06, -20.45), (1.3, 0.06, -20.6), (2.62, 0.06, -21.05)]
    polyline(b, yk, 0.86, 0.78, "yoke", overlap=0.2, uv=8)
    cbox(b, (0, 0.06, -20.4), (1.4, 0.98, 1.0), "yoke", uv=8)
    for i, x in enumerate((-2.2, -0.75, 0.75, 2.2)):
        x0 = x * 1.16 if abs(x) > 1 else x
        bend = -0.34 if i == 0 else 0.0
        pts = [(x0, 0.06, -20.8), (x, 0.06, -23.3), (x + bend * 0.4, 0.13, -25.7), (x + bend, 0.38, -27.35),
               (x + bend * 1.25, 0.6, -28.2)]
        rod(b, pts[0], pts[1], 0.46, "tine", uv=9)
        rod(b, pts[1], pts[2], 0.4, "tine", uv=9)
        beam(b, pts[2], pts[3], 0.32, 0.32, "tine", roll=45.0, extend=0.15, uv=10)
        beam(b, pts[3], pts[4], 0.2, 0.2, "tip", roll=45.0, extend=0.1, uv=12)
    # 爪に引っ掛かった布切れと、刺さった肉
    rag(b, (0.75, -0.05, -25.0), 1.6, 0.7, "rag", hang=(0.25, -1.0, 0.1), strips=1, seed=144)
    rag(b, (-2.25, -0.05, -23.9), 1.2, 0.6, "rag", hang=(-0.2, -1.0, 0.2), strips=1, seed=145)
    cbox(b, (-0.75, 0.12, -26.4), (0.8, 0.66, 0.56), "meat", rot=(10, 25, 15), uv=12)
    cbox(b, (-0.62, -0.18, -26.0), (0.46, 0.4, 0.4), "meat", rot=(-20, 10, 0), uv=12)
    book.add("handle", "wood_old", base=book.pal(0), dirt=0.4, grain=1.5)
    book.add("dwood", "wood_dark", dirt=0.5)
    book.add("ferrule", "steel_rusty", amount=0.6)
    book.add("tape", "tape_grey", dirt=0.6)
    book.add("socket", "steel_rusty", amount=0.85)
    book.add("rivet", "steel_worn", base=(120, 120, 118), dirt=0.4)
    book.add("wire", "steel_worn", base=(140, 138, 132), dirt=0.45)
    book.add("yoke", "steel_rusty", amount=0.8)
    book.add("tine", "steel_worn", base=book.pal(1), scratches=0.6, dirt=0.4)
    book.add("tip", "steel_clean", base=(190, 194, 196))
    book.add("rag", "cloth_rag", dirt=0.75)
    book.add("meat", "gore_meat")
    blood = spec_blood(w, amount=0.72, grow=0.3) + [
        WC.blood_zone((-1.6, -0.8, -27.2), (0.2, 1.0, -25.3), 0.6, "wet", soft=0.7, drip=1.2)]
    return Built(wm, book, blood, hold=dict(grip=0.1, scale=0.85, up=(0.0, 1.0, 0.0)), icon_roll=90.0)


@builder("kitchen_spear")
def b_kitchen_spear(w) -> Built:
    wm = WC.WeaponModel("kitchen_spear", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # ---- 柄: 木のモップの柄。尻に青い樹脂の握りと吊るしキャップ（穴に紐）、先はねじ山の残り ----
    wood = rod(b, (0, 0, 4.4), (0, 0, -10.0), 1.0, "wood", uv=6)
    wood += rod(b, (0, 0, -9.9), (0, 0, -19.6), 1.0, "wood", uv=6)
    add_fx(wood, world=WC.compose(barcode(-5.6, -7.6, -0.42, 0.42, side=1, seed=151),
                                  grime((-7.0, -9.0), dark=0.7, seed=152)))
    rod(b, (0, 0, -19.5), (0, 0, -20.45), 0.92, "thread", fx={"ribs": 0.2}, uv=10)
    rod(b, (0, 0, -0.3), (0, 0, 4.3), 1.24, "blue", fx={"ribs": 0.42}, uv=8)
    rod(b, (0, 0, 4.2), (0, 0, 5.9), 1.3, "blue", uv=8)
    disc(b, (0, 0, 6.05), (0, 0, 1), 0.5, 0.32, "blue", n=2, uv=10)
    wm.cut((0, 0, 5.15), (1, 0, 0), r=0.3, half=1.0, rim=0.1)
    for s in (-1, 1):
        polyline(b, [(s * 0.66, 0, 5.15), (s * 0.78, -0.8, 5.4), (s * 0.22, -1.8, 5.6)], 0.14, 0.14, "string",
                 overlap=0.08, uv=12)
    cbox(b, (0, -1.86, 5.6), (0.42, 0.3, 0.3), "string", uv=12)
    # ---- 包丁（三徳）: 樹脂の柄を柄の先の上に半分沈め、口金、刃（刃元の刻印・くぼみ） ----
    KY = 0.9
    kh = beam(b, (0, KY, -16.2), (0, KY, -20.0), 0.74, 1.26, "khandle", uv=8)
    kh.fx = {"world": dots([(s * 0.37, KY, z) for s in (-1, 1) for z in (-16.9, -18.1, -19.3)], 0.2,
                           (196, 198, 200))}
    cbox(b, (0, KY - 0.02, -20.15), (0.8, 1.34, 0.3), "bolster", uv=10)
    prof = [(-20.3, 1.5, -0.38), (-21.4, 1.52, -0.42), (-22.6, 1.52, -0.44), (-23.8, 1.5, -0.43),
            (-24.8, 1.44, -0.39), (-25.6, 1.3, -0.32), (-26.3, 1.06, -0.22), (-26.9, 0.74, -0.1),
            (-27.4, 0.4, 0.0), (-27.75, 0.12, 0.04)]
    bl = blade(b, prof, "blade", "edge", "spine", t_body=0.22, t_edge=0.1, t_spine=0.26, bevel=0.42,
               spine_h=0.16, uv=10, edge_uv=12, grind=0.6)
    chips_on(bl["edge"], [(-23.4, 0.22, 0.16), (-25.9, 0.18, 0.12)])
    add_fx(bl["body"], world=WC.compose(
        WC.spots([(z, 0.12) for z in (-21.2, -22.1, -23.0, -23.9, -24.8)], 0.2, mul=0.74),
        WC.stamp("SANTOKU", (-21.9, 0.98), 0.34, mul=0.6)))
    # ---- 縛り: 針金を 4 周（柄と包丁の柄をまとめて）、前後にテープ ----
    lash(b, (0, 0.5, -18.1), (0, 0, 1), 1.12, 2.12, 2.0, 4, "wire", wire=0.13, uv=12)
    wrap(b, (0, 0.5, -16.0), (0, 0.5, -17.05), (1.24, 2.26), "tape", pitch=0.52, tilt=6, seed=153, uv=8)
    wrap(b, (0, 0.5, -19.1), (0, 0.5, -20.0), (1.24, 2.26), "tape", pitch=0.45, tilt=-7, seed=154, uv=8,
         tail=(0.7, (0.3, -1.0, 0.1)))
    book.add("wood", "wood_raw", base=book.pal(0), dirt=0.35, grain=1.2)
    book.add("thread", "plastic_black", base=(64, 64, 68))
    book.add("blue", "plastic_blue", wear=0.5, dirt=0.45)
    book.add("string", "rope", base=(196, 186, 156))
    book.add("khandle", "plastic_black", base=book.pal(3), wear=0.4)
    book.add("bolster", "steel_worn", base=book.pal(2), dirt=0.3)
    book.add("blade", "steel_worn", base=book.pal(1), scratches=0.55, dirt=0.15)
    book.add("edge", "steel_clean", base=(214, 218, 222))
    book.add("spine", "steel_worn", base=book.pal(2), dirt=0.25)
    book.add("wire", "steel_worn", base=(150, 150, 146), dirt=0.3)
    book.add("tape", "tape_grey", dirt=0.55)
    blood = spec_blood(w, amount=0.66, grow=0.3) + [
        WC.blood_zone((-0.6, -0.6, -27.9), (0.6, 1.6, -24.2), 0.4, "wet", soft=0.8, drip=1.2),
        WC.blood_zone((-1.2, -1.0, -20.4), (1.2, 2.0, -16.0), 0.2, "dry", soft=1.0)]
    return Built(wm, book, blood, hold=dict(grip=1.1, scale=0.85))


# ===========================================================================
#  まとめ
# ===========================================================================
def build(key: str):
    w = BY_KEY[key]
    t0 = time.time()
    bt = BUILDERS[key](w)
    wm = bt.wm
    wm.pack()
    tex = WC.texture(wm, bt.book, WC.seed_of(key), blood=bt.blood)
    hold = WC.hold_for(w, wm, **bt.hold)
    return w, bt, wm, tex, hold, time.time() - t0


def all_frags(frags: WC.Frags) -> None:
    """item_texture / lang の断片は spec から全近接武器分を書く（--only で一部だけ作っても欠けない）。"""
    for w in MELEE:
        frags.icon(f"nr_w_{w['key']}", f"{WC.ICON_REL}/{w['key']}")
        frags.name(w["id"], w["ja"], w["en"])


def preview(results, out_dir=SCRATCH) -> List[str]:
    """確認画像（3/4 の一覧・三人称の持ち姿・一人称・アイコン）。一覧と持ち姿は全武器を 1 枚ずつに収める。"""
    os.makedirs(out_dir, exist_ok=True)
    sheet, held, fp, icons = [], [], [], []
    for w, bt, wm, tex, hold, _dt in results:
        key = w["key"]
        sheet.append((f"{key} [{wm.stats()}]", WC.render_model(wm, tex, view=(35.0, 16.0), size=(420, 170))))
        rep = WC.clip_report(wm, hold)
        repu = WC.clip_report(wm, hold, use=True)
        tag = f"{key} clip {rep['depth']}/{repu['depth']} gap {rep['gap']}"
        held.append((tag, WC.render_held(wm, tex, hold, view=(35.0, 8.0), size=(230, 270))))
        held.append(("  use", WC.render_held(wm, tex, hold, view=(60.0, 8.0), size=(230, 270), use=True)))
        fp.append((key, WC.render_fp(wm, tex, hold, size=(320, 180))))
        ic = Image.open(os.path.join(WC.RP, *WC.ICON_REL.split("/"), f"{key}.png")).convert("RGBA")
        slot = Image.new("RGBA", (ic.size[0] * 2 + 8, ic.size[1] * 2 + 8), (139, 139, 139, 255))
        slot.alpha_composite(ic.resize((ic.size[0] * 2, ic.size[1] * 2), Image.NEAREST), (4, 4))
        icons.append((key, slot))
    paths = []
    for name, items, cols in (("weapons_melee", sheet, 4), ("weapons_melee_held", held, 8),
                              ("weapons_melee_fp", fp, 6), ("weapons_melee_icons", icons, 8)):
        img = WC.contact_sheet(items, cols=min(cols, len(items)), title=f"NIGHT RUNNER {name}")
        p = os.path.join(out_dir, name + ".png")
        img.save(p)
        paths.append(p)
    return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="", help="作る武器のキー（カンマ区切り）")
    ap.add_argument("--preview", action="store_true", help="確認画像も描く（NR_PREVIEW=1 と同じ）")
    ap.add_argument("--out", default=SCRATCH, help="確認画像の置き場所")
    a = ap.parse_args(argv)
    keys = [k for k in a.only.split(",") if k] or [w["key"] for w in MELEE]
    missing = [k for k in keys if k not in BUILDERS]
    if missing:
        unknown = [k for k in missing if k not in BY_KEY]
        if unknown:
            print(f"[{PRODUCER}] 近接武器ではない / 知らないキー: {unknown}")
            return 2
        print(f"[{PRODUCER}] まだ作っていない武器: {missing}")
        keys = [k for k in keys if k in BUILDERS]
    frags = WC.Frags(PRODUCER)
    all_frags(frags)
    results = []
    t0 = time.time()
    for k in keys:
        w, bt, wm, tex, hold, dt = build(k)
        out = WC.write_weapon(w, wm, tex, hold, frags, icon=WC.bake_icon(wm, tex, flip=bt.icon_flip, yaw=bt.icon_yaw, roll=bt.icon_roll))
        rep = WC.clip_report(wm, hold)
        print(f"[{PRODUCER}] {k:24s} {wm.stats():34s} clip {rep['depth']:.2f}@{rep['part']} "
              f"gap {rep['gap']}  ({dt:.2f}s){'' if 'recipe' in out else '  (レシピなし)'}")
        results.append((w, bt, wm, tex, hold, dt))
    frags.write()
    print(f"[{PRODUCER}] {len(results)} 武器 / {time.time() - t0:.1f}s")
    if a.preview or PREVIEW:
        for p in preview(results, a.out):
            print(f"[{PRODUCER}] preview {p}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
