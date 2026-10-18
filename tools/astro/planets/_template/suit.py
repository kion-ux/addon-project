# -*- coding: utf-8 -*-
"""<惑星名> — <スーツ名>（雛形）。

使い方: tools/astro/planets/<key>/ にコピーし（__init__.py も空で作る）、各関数を作り込む。
お手本は planets/earth/suit.py。説明は同じフォルダの README.md。

    python3 tools/astro/preview_astro.py suit <key>    # 絵を見る
    python3 tools/astro/check_astro_suits.py <key>     # 検査
    python3 tools/astro/gen_astro_suits.py <key>       # pack へ書き出す

座標: -Z が正面、右手が -X。右側だけ作って名前の末尾を `_r` に → 左は自動で鏡映。
回転: rx 正 = 上端が前へ / ry 正 = 正面が右(-X)を向く / rz 正 = 下端が右(-X)へ（右の部品なら外へ開く）。
"""
from __future__ import annotations

from astro_common import (bevel, beam, cbox, line_on, octa, polyline, rbox, ring,  # noqa: F401
                          stick, taper)
from astro_suit import ARM_X, LEG_X, Suit, mirror_x  # noqa: F401

# 塗りの上書き・追加（astro_paint.suit_styles(key) の上に重なる）。README §6
SUIT_STYLES = {
    # "plate": {"panel": 1},
    # "flame": {"glow": (255, 140, 40), "light": (255, 240, 200), "deep": (160, 40, 10)},
}

# 部位アニメ（Molang）。周波数は 30°/秒の倍数。`_r` は左へ自動で鏡映。README §7
SUIT_ANIMS = {
    "idle": {
        # "fx_spin_halo": {"rotation": [0, 0, "q.anim_time * 60.0"]},
    },
    "thrust": {},
    "sprint": {},
}


def build_suit(s: Suit):
    s.inner_suit(gap=0.3)        # 肌を確実に覆う黒いインナー（これで被覆検査は通る）
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    arms(s)
    shoulders(s)
    helmet(s)
    extra(s)


def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")                 # pivot は足首（既定）
    cbox(b, (LEG_X, -0.3, -0.5), (5.2, 0.8, 6.4), "frame")    # 靴底
    cbox(b, (LEG_X, 1.7, -0.25), (5.2, 3.2, 5.7), "plate")    # 足の殻
    rbox(b, (LEG_X, 1.15, -3.15), (4.8, 2.3, 1.7), "plate2", rot=(-38, 0, 0))   # つま先（前上を向く）


def legs(s):
    g = s.part("legs", "greave_r", "rightLeg")                # pivot は膝（既定）
    cbox(g, (LEG_X, 5.2, 0.05), (5.3, 4.4, 5.5), "plate")
    bevel(g, (LEG_X, 7.45, -3.0), (3.6, 2.8, 1.2), "plate2", cut=0.5, axis="z")   # 膝当て


def waist(s):
    w = s.part("waist", "belt", "body")
    cbox(w, (0, 12.6, 0), (9.5, 1.7, 5.9), "frame")
    t = rbox(w, (-5.25, 10.3, -0.2), (0.8, 4.2, 5.0), "plate", rot=(0, 0, 12))   # 草摺（下端が外へ）
    mirror_x(w, t)                                            # 中央の部品の中の左右対称


def torso(s):
    c = s.part("torso", "chest", "body")
    bevel(c, (0, 21.1, 0.0), (9.8, 5.8, 5.8), "plate", cut=0.8, axis="y")   # 上が広い胸郭
    pec = rbox(c, (-2.6, 21.55, -3.05), (5.0, 4.0, 0.9), "plate2", rot=(6, 17, 9))
    glow = line_on(c, pec, "north", (0.9, 0.4), (0.2, 0.5), 0.26, 0.2, "glow")
    mirror_x(c, pec, glow)
    cbox(c, (0, 20.3, -4.35), (2.4, 2.4, 0.9), "core")       # 星核（惑星の模様が描かれる）


def back(s):
    bk = s.part("back", "pack", "body")
    cbox(bk, (0, 19.5, 4.0), (5.0, 6.0, 2.4), "plate2")
    th = s.part("back", "thruster_r", bk, pivot=(-1.4, 16.5, 4.6), rotation=(15, 0, -5))
    octa(th, (-1.4, 15.4, 4.6), 2.0, 2.4, "plate", axis="y")
    cbox(th, (-1.4, 14.1, 4.6), (1.7, 0.2, 1.7), "thruster")  # 下面に同心円の発光
    fx = s.fx("thrust", "r", th, pivot=(-1.4, 14.0, 4.6))     # 炎は局所 -Y へ全長で作る
    taper(fx, (-1.4, 14.0, 4.6), (-1.4, 8.0, 4.6), 1.8, 0.4, 3, "flame")


def arms(s):
    a = s.part("arms", "vambrace_r", "rightArm")              # pivot は前腕（既定）
    cbox(a, (ARM_X, 14.9, 0), (4.9, 3.1, 5.1), "plate")
    cbox(a, (ARM_X, 12.25, 0), (4.9, 2.4, 5.1), "plate2")


def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")         # pivot は肩の付け根（既定）
    bevel(p, (-7.0, 24.0, 0.0), (5.8, 3.0, 7.0), "plate", cut=1.0, axis="x", rot=(0, 0, -12))


def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 31.2, 0.15), (9.8, 4.6, 10.1), "plate", cut=1.0, axis="z")
    v = s.part("visor", "eye", "head")
    cbox(v, (0, 27.95, -4.8), (8.4, 1.9, 0.6), "dark")
    g = s.fx("glow", "visor", v, pivot=(0, 28.0, -5.1))       # visor の下の fx_glow は変身時に閃光
    cbox(g, (0, 28.0, -5.1), (7.6, 1.1, 0.35), "visor")


def extra(s):
    pass                                                      # 環・衛星・マントなど（earth の cape / luna_bit 参照）
