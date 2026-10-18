# -*- coding: utf-8 -*-
"""水星 — 水銀機装 クイックシルバー（Quicksilver Frame）。

最も速く、最も細い形態。鏡面の銀と液体金属（波打つ刃文のような流れの板）でできた流線形の装甲、
黒い六角メッシュのインナーを細い隙間に覗かせる。
  * 兜: 丸い弾頭形の鏡面ドーム、額から後ろへ流れる稜、こめかみから後ろ上へ掃き上げた
        ヘルメスの翼（三枚の羽根）、顔の中央で鋭く折れたシアンの V 字スリット一本
  * 足: つま先の尖ったブーツ、踵の外側にタラリア（翼のサンダル）の三枚羽
  * 肩: 涙滴形の細いフェアリング（前が丸く、後ろへ尾を引く）
  * 背: 縦に長い二基の細いイオン・スラスター、背中の後ろを回る液体金属の滴（二重の軌道）
  * 発光: 右半身は昼側の灼熱（橙）、左半身は夜側の極寒（シアン）— MIRROR_STYLES で塗り分け
  * 胸: 銀の水星を二重の輪で囲んだ星核（太陽側が橙に光る）

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。右側だけ作り `_r` を付ける → 左は自動で鏡映。
回転（統合版の rotation）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く /
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import numpy as np

from astro_common import (beam, bevel, cbox, frame_to, line_on, octa, polyline, rbox, ring,
                          stick, taper)
from astro_suit import ARM_X, LEG_X, Suit, mirror_x

DAY = (255, 150, 60)          # 昼側（右）の灼熱
DAY_L = (255, 238, 204)
NIGHT = (120, 240, 255)       # 夜側（左）の極寒
NIGHT_L = (222, 252, 255)
TRIM_W = 0.36                 # 縁取りの幅

# 右側（-X）で使う塗り → 左（鏡映）で使う塗り
MIRROR_STYLES = {
    "glow_day": "glow_night", "glow_soft_day": "glow_soft_night", "vent_day": "vent_night",
    "flame_day": "flame_night", "flame_core_day": "flame_core_night",
    "thruster_day": "thruster_night", "rip_day": "rip_night", "gem_accent": "gem",
    "emblem_day": "emblem_night", "serial_day": "serial_night",
}


def _glow(c, lt, emit=None):
    d = {"kind": "glowline", "glow": c, "light": lt, "bevel": False, "outline": False}
    if emit is not None:
        d["emit"] = emit
    return d


# ===========================================================================
#  塗り（astro_paint.suit_styles("mercury") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate": {"base": (210, 220, 232), "light": (252, 254, 255), "dark": (128, 140, 160),
              "line": (70, 80, 100)},
    "plate2": {"base": (146, 158, 176), "light": (214, 224, 238), "dark": (88, 98, 118),
               "line": (40, 48, 64)},
    "chrome": {"base": (214, 224, 238), "light": (255, 255, 255), "line": (56, 64, 84)},
    # 液体金属の流れの板（波打つ照りの境が流れる鏡面）
    "quick": {"kind": "blade", "all_faces": True, "base": (196, 208, 224), "light": (250, 252, 255),
              "dark": (116, 128, 150), "line": (56, 64, 84), "glint_period": 18,
              "fuller": False},
    # 回る滴・液面（水銀の渦の模様）
    "bead": {"kind": "planet", "planet": "mercury", "radius": 1.45, "bevel": False,
             "outline": False},
    "inner": {"base": (30, 36, 50), "glow": NIGHT, "seam": 0.02},
    "frame": {"base": (52, 58, 74), "light": (110, 120, 142)},
    "glow_day": _glow(DAY, DAY_L),
    "glow_night": _glow(NIGHT, NIGHT_L),
    "glow_soft_day": _glow(DAY, DAY_L, 150),
    "glow_soft_night": _glow(NIGHT, NIGHT_L, 150),
    "vent_day": {"kind": "vent", "base": (56, 62, 78), "glow": DAY, "deep": (120, 40, 10),
                 "line": (20, 22, 30)},
    "vent_night": {"kind": "vent", "base": (56, 62, 78), "glow": NIGHT, "deep": (18, 70, 104),
                   "line": (20, 22, 30)},
    "thruster_day": {"kind": "thruster", "base": (56, 62, 78), "glow": DAY, "light": DAY_L,
                     "deep": (150, 50, 12), "line": (20, 22, 30), "bevel": False},
    "thruster_night": {"kind": "thruster", "base": (56, 62, 78), "glow": NIGHT, "light": NIGHT_L,
                       "deep": (18, 70, 104), "line": (20, 22, 30), "bevel": False},
    "flame_day": {"kind": "flame", "glow": (255, 170, 80), "light": (255, 246, 220),
                  "deep": (200, 70, 20), "bevel": False, "outline": False},
    "flame_core_day": {"kind": "flame", "glow": (255, 236, 190), "light": (255, 255, 255),
                       "deep": (255, 160, 70), "bevel": False, "outline": False},
    "flame_night": {"kind": "flame", "glow": (130, 236, 255), "light": (236, 255, 255),
                    "deep": (30, 120, 200), "bevel": False, "outline": False},
    "flame_core_night": {"kind": "flame", "glow": (210, 252, 255), "light": (255, 255, 255),
                         "deep": (100, 210, 255), "bevel": False, "outline": False},
    # 波紋のデカール（入れ子の V。流れる向きを示す）
    "rip_day": {"kind": "decal", "decal": "chevron", "color": DAY, "count": 3,
                "under": {"kind": "armor", "base": (146, 158, 176), "panel": 0,
                          "line": (40, 48, 64)}},
    "rip_night": {"kind": "decal", "decal": "chevron", "color": NIGHT, "count": 3,
                  "under": {"kind": "armor", "base": (146, 158, 176), "panel": 0,
                            "line": (40, 48, 64)}},
    "emblem_day": {"kind": "decal", "decal": "emblem", "color": DAY,
                   "under": {"kind": "armor", "base": (210, 220, 232), "panel": 0,
                             "line": (70, 80, 100)}},
    "emblem_night": {"kind": "decal", "decal": "emblem", "color": NIGHT,
                     "under": {"kind": "armor", "base": (210, 220, 232), "panel": 0,
                               "line": (70, 80, 100)}},
    "serial_day": {"kind": "decal", "decal": "serial", "text": "QS-01", "ink": (150, 60, 16),
                   "under": {"kind": "armor", "base": (146, 158, 176), "panel": 0,
                             "line": (40, 48, 64)}},
    "serial_night": {"kind": "decal", "decal": "serial", "text": "QS-01", "ink": (20, 80, 120),
                     "under": {"kind": "armor", "base": (146, 158, 176), "panel": 0,
                               "line": (40, 48, 64)}},
    "hazard": {"c1": DAY, "c2": (30, 34, 46)},
    "visor": {"glow": (110, 236, 255), "light": (232, 255, 255), "deep": (10, 80, 120),
              "emit": 16},
    "core": {"halo": (255, 170, 80), "emit": 40},
    "gem": {"glow": NIGHT, "deep": (18, 70, 104)},
    "gem_accent": {"glow": DAY, "deep": (130, 50, 10)},
}

# ===========================================================================
#  部位アニメ（Molang。q.anim_time は 12 秒でループ → 周波数は 30°/秒の倍数）
#  v.astro_air: 空中で 1 に近づく / v.astro_run: 疾走で 1 に近づく。`_r` は左へ自動で鏡映
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        "fx_spin_drops": {"rotation": [0, 0, "q.anim_time * 60.0"]},
        "fx_spin_drops2": {"rotation": [0, 0, "-q.anim_time * 90.0"]},
        "extra_droplets": {"position": [0, "math.sin(q.anim_time * 90.0) * 0.3", 0]},
        "helmet_wing_r": {"rotation": [0, "math.sin(q.anim_time * 120.0) * 1.5", 0]},
        "boots_talaria_r": {"rotation": [0, "math.sin(q.anim_time * 180.0) * 3.0", 0]},
    },
    "thrust": {
        # 空中では翼が開いて羽ばたく
        "helmet_wing_r": {"rotation": ["-v.astro_air * 6.0", 0,
                                       "-v.astro_air * (6.0 + math.sin(q.anim_time * 720.0) * 5.0)"]},
        "boots_talaria_r": {"rotation": ["-v.astro_air * 10.0", 0,
                                         "-v.astro_air * (10.0 + math.sin(q.anim_time * 900.0) * 8.0)"]},
    },
    "sprint": {
        # 疾走では翼を後ろへ寝かせ、細かく震わせる
        "helmet_wing_r": {"rotation": ["v.astro_run * 10.0", "-v.astro_run * 8.0",
                                       "v.astro_run * math.sin(q.anim_time * 1080.0) * 2.5"]},
        "boots_talaria_r": {"rotation": ["v.astro_run * 8.0", "-v.astro_run * 10.0",
                                         "-v.astro_run * math.sin(q.anim_time * 1440.0) * 6.0"]},
    },
}


def mx(bone, *cubes, about=0.0):
    """中央の部品の左右対称（左側は夜側の塗りに替える）。"""
    return mirror_x(bone, *cubes, style_map=MIRROR_STYLES, about=about)


def feather(bone, p0, p1, h0, h1, t, style, edge=None, n=3, edge_w=0.24):
    """p0 → p1 へ伸びる羽根（局所 X = 厚み t、局所 Y = 羽根の幅 h0 → h1 の先細り）。
    edge を渡すと前縁（局所 +Y 側）を発光線が走る。"""
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    yax = frame_to(p1 - p0)[:, 1]
    out = []
    for i in range(n):
        a = p0 + (p1 - p0) * i / n
        b = p0 + (p1 - p0) * (i + 1) / n
        h = h0 + (h1 - h0) * (i + 0.5) / n
        # 後縁を少しずつ持ち上げて、先へ行くほど細く（前縁はまっすぐ）
        off = yax * (h0 - h) * 0.5
        out.append(beam(bone, a + off, b + off, t, h, style, extend=0.15))
    if edge:
        out.append(beam(bone, p0 + yax * (h0 / 2 - 0.08), p1 + yax * (h1 / 2 - 0.08),
                        t + 0.1, edge_w, edge))
    return out


def bead(bone, c, r, style="bead"):
    """角を落とした小さな球（3 個）。液体金属の滴。"""
    d = 2 * r
    return [cbox(bone, c, (d * 0.78,) * 3, style),
            rbox(bone, c, (d, d * 0.62, d * 0.62), style, rot=(45, 0, 0)),
            rbox(bone, c, (d * 0.62, d, d * 0.62), style, rot=(0, 45, 0))]


# ===========================================================================
def build_suit(s: Suit):
    s.inner_suit(gap=0.3)
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    droplets(s)
    arms(s)
    shoulders(s)
    helmet(s)


# ---------------------------------------------------------------------------
#  ブーツ（尖ったつま先・踵の噴射口・タラリアの翼）
# ---------------------------------------------------------------------------
def boots(s):
    X = LEG_X
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (X, -0.35, -0.7), (5.2, 0.6, 6.8), "frame")                  # 靴底
    cbox(b, (X, 1.55, -0.2), (5.2, 3.0, 5.6), "plate")                   # 足の殻
    # つま先: 前上を向いた板 + 尖った先端（鏡面）
    toe = rbox(b, (X, 1.05, -3.35), (4.8, 1.9, 1.6), "quick", rot=(-34, 0, 0))
    stick(b, toe, "north", 0.5, 0.6, (0.5, 1.2, 0.2), "glow_day", sink=0.05)
    taper(b, (X, 0.35, -3.9), (X, 0.25, -5.4), 2.6, 0.7, 2, "chrome")
    cbox(b, (X, -0.05, -4.2), (4.0, 0.5, 1.2), "frame")
    # 甲: 斜めの板と中央の稜
    ins = rbox(b, (X, 3.25, -2.35), (4.4, 2.0, 0.8), "plate2", rot=(-30, 0, 0))
    line_on(b, ins, "north", (0.15, 0.35), (0.85, 0.35), 0.22, 0.2, "glow_day")
    # 踵: 後ろへ傾いた板・噴射口
    rbox(b, (X, 1.6, 2.85), (4.6, 2.8, 0.8), "plate_b", rot=(10, 0, 0))
    cbox(b, (X, 0.4, 3.2), (2.8, 1.0, 1.2), "frame")
    cbox(b, (X, -0.12, 3.2), (2.0, 0.2, 0.8), "thruster_day")
    # 足首（外の関節の円盤）と外側の発光線
    octa(b, (X - 2.72, 2.9, 0.3), 1.9, 0.5, "chrome", axis="x")
    octa(b, (X - 2.98, 2.9, 0.3), 0.9, 0.25, "glow_day", axis="x")
    cbox(b, (X - 2.66, 0.75, -0.9), (0.2, 0.3, 4.0), "glow_day")
    # タラリア（踵の外側から後ろ上へ掃き上げる三枚羽）
    w = s.part("boots", "talaria_r", b, pivot=(X - 2.8, 2.6, 1.6))
    octa(w, (X - 2.85, 2.6, 1.7), 1.5, 0.6, "plate2", axis="x")
    feather(w, (X - 2.95, 3.1, 1.6), (X - 3.7, 6.2, 5.8), 1.2, 0.35, 0.36, "plate", "glow_day")
    feather(w, (X - 3.0, 2.6, 2.0), (X - 4.0, 4.6, 6.6), 1.0, 0.32, 0.34, "chrome")
    feather(w, (X - 2.95, 2.1, 2.3), (X - 3.6, 2.9, 6.1), 0.85, 0.3, 0.32, "plate2", n=2)


# ---------------------------------------------------------------------------
#  脚（細い脛・尖った膝・液体金属の流れの板）
# ---------------------------------------------------------------------------
def legs(s):
    X = LEG_X
    g = s.part("legs", "greave_r", "rightLeg")
    cbox(g, (X, 5.9, 0.05), (5.25, 4.6, 5.3), "plate")                  # 脛の殻
    keel = rbox(g, (X - 0.7, 5.6, -2.9), (1.5, 4.6, 0.7), "chrome", rot=(0, 24, 0))
    gl = line_on(g, keel, "north", (0.3, 0.12), (0.3, 0.88), 0.22, 0.18, "glow_day")
    mirror_x(g, keel, gl, about=X)                                       # 脛の稜（V 字）
    cbox(g, (X, 3.7, 0.05), (5.35, 0.7, 5.4), "frame")                   # 足首の帯
    cbox(g, (X, 8.75, 0.05), (5.3, 1.3, 5.35), "frame")                  # 膝の関節
    # 膝当て: 面取りの板 + 上へ尖る鏡面の庇 + 宝玉
    bevel(g, (X, 8.6, -2.95), (3.0, 2.6, 1.0), "plate2", cut=0.45, axis="z")
    taper(g, (X, 9.6, -2.95), (X, 11.0, -2.75), 2.2, 0.6, 2, "chrome", round_=False)
    rbox(g, (X, 8.55, -3.55), (0.9, 0.9, 0.4), "gem_accent", rot=(0, 0, 45))
    # ふくらはぎ: 斜めの板と排気口
    calf = rbox(g, (X, 5.9, 2.85), (4.6, 4.0, 0.8), "plate_b", rot=(-8, 0, 0))
    stick(g, calf, "south", 0.5, 0.5, (2.4, 2.6, 0.3), "vent_day", sink=0.1)
    # 外側の流線のヒレ（後ろへ流れる）
    fin = rbox(g, (X - 2.85, 6.1, 1.0), (0.6, 3.8, 3.4), "rip_day", rot=(-16, 0, -5))
    line_on(g, fin, "west", (0.1, 0.92), (0.95, 0.35), 0.22, 0.18, "glow_day")
    # 腿
    t = s.part("legs", "thigh_r", "rightLeg", pivot=(X, 11.6, 0))
    cbox(t, (X, 10.75, 0.05), (5.2, 3.4, 5.35), "plate_b")
    th = rbox(t, (X, 10.6, -2.85), (4.4, 3.2, 0.7), "quick", rot=(-5, 0, 0))
    line_on(t, th, "north", (0.85, 0.1), (0.55, 0.92), 0.24, 0.2, "glow_day")
    cbox(t, (X, 9.1, -2.95), (4.2, TRIM_W, 0.5), "chrome")
    cbox(t, (X - 2.62, 10.6, 0.3), (0.6, 2.8, 3.8), "serial_day")
    rbox(t, (X, 10.8, 2.85), (4.4, 2.8, 0.7), "plate", rot=(6, 0, 0))


# ---------------------------------------------------------------------------
#  腰（細いベルト・下を指す V の前垂れ・後ろへ流れる草摺）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    cbox(w, (0, 12.6, 0), (9.4, 1.5, 5.8), "frame")
    gd = cbox(w, (-2.6, 12.95, -2.98), (3.4, 0.22, 0.2), "glow_day")
    mx(w, gd)
    octa(w, (0, 12.6, -3.05), 2.2, 0.6, "chrome", axis="z")              # バックル
    octa(w, (0, 12.6, -3.4), 1.1, 0.3, "core", axis="z")
    rbox(w, (0, 10.75, -3.0), (2.4, 2.4, 0.7), "quick", rot=(-10, 0, 45))   # 下を指す菱形
    fr = rbox(w, (-2.3, 11.0, -2.95), (2.2, 2.0, 0.6), "plate", rot=(-10, 18, 14))
    mx(w, fr)
    # 草摺: 細く、後ろへ流れる二枚重ね
    t1 = rbox(w, (-5.0, 10.7, 0.5), (0.7, 3.4, 4.4), "plate", rot=(-8, 0, 9))
    t2 = rbox(w, (-5.3, 10.1, 1.0), (0.5, 2.6, 3.6), "plate2", rot=(-14, 0, 12))
    t3 = line_on(w, t2, "west", (0.08, 0.3), (0.92, 0.8), 0.22, 0.18, "glow_day")
    t4 = stick(w, t1, "west", 0.5, 0.96, (4.0, TRIM_W, 0.2), "chrome", sink=0.05)
    mx(w, t1, t2, t3, t4)
    rbox(w, (0, 10.9, 2.95), (6.0, 2.4, 0.7), "plate", rot=(10, 0, 0))    # 後ろ垂れ


# ---------------------------------------------------------------------------
#  胴（細い逆三角・V の胸板・液体金属の腹・二重の輪の星核）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    bevel(c, (0, 21.0, 0.0), (9.7, 6.0, 5.8), "plate", cut=0.55, axis="y")   # 胸郭
    cbox(c, (0, 15.9, 0.0), (7.4, 4.8, 5.2), "plate_b")                       # 腹の殻（細い）
    cbox(c, (0, 16.0, -2.62), (5.0, 4.6, 0.5), "frame")
    # 腹: 中央の鏡面の稜と、下へ細くなる液体金属の板
    cbox(c, (0, 16.0, -3.0), (0.7, 4.4, 0.6), "chrome")
    for y, wd in ((17.25, 2.2), (16.0, 2.0), (14.75, 1.75)):
        a = rbox(c, (-wd / 2 - 0.4, y, -2.95), (wd, 1.15, 0.6), "quick", rot=(-10, 10, 0))
        mx(c, a)
    ob = rbox(c, (-3.4, 16.0, -2.2), (1.2, 4.2, 1.0), "plate2", rot=(0, 36, -6))   # 脇腹
    obl = line_on(c, ob, "north", (0.5, 0.1), (0.5, 0.9), 0.2, 0.18, "glow_day")
    mx(c, ob, obl)
    # 胸板（V 字）: 外へ開き、内側の端が前へ出る。鏡面の縁と昼/夜の発光線
    pec = rbox(c, (-2.55, 21.5, -3.05), (4.9, 3.9, 0.8), "plate", rot=(6, 18, 10))
    trim = stick(c, pec, "north", 0.5, 0.03, (4.7, TRIM_W, 0.2), "chrome", sink=0.05)
    l1 = line_on(c, pec, "north", (0.96, 0.45), (0.55, 0.62), 0.24, 0.2, "glow_day")
    l2 = line_on(c, pec, "north", (0.55, 0.62), (0.08, 0.66), 0.24, 0.2, "glow_day")
    flow = stick(c, pec, "north", 0.32, 0.3, (2.6, 1.0, 0.18), "quick", sink=0.05)
    low = rbox(c, (-2.3, 18.65, -2.85), (3.8, 1.4, 0.7), "plate2", rot=(-8, 12, 14))
    mx(c, pec, trim, l1, l2, flow, low)
    # 襟（首の両脇へ低く流れる）
    col = rbox(c, (-3.0, 24.3, 0.3), (2.0, 1.2, 4.8), "plate2", rot=(0, 0, -18))
    colt = stick(c, col, "up", 0.5, 0.5, (0.5, 4.4, 0.2), "chrome", sink=0.08)
    mx(c, col, colt)
    # 星核: 黒い菱形の台 → 鏡面の八角枠 → 水星（太陽側が橙に光る）→ 二重の輪
    rbox(c, (0, 20.3, -3.65), (3.4, 3.4, 0.7), "dark", rot=(0, 0, 45))
    ring(c, (0, 20.3, -4.05), 1.85, 12, (0, 0.3, 0.4), "chrome", axis="z")
    cbox(c, (0, 20.3, -4.25), (2.2, 2.2, 0.8), "core")
    gl = s.fx("glow", "core", c, pivot=(0, 20.3, -4.5))
    ring(gl, (0, 20.3, -4.45), 1.42, 10, (0, 0.2, 0.25), "glow_night", axis="z")
    # 脇: 細い板と排気口
    fl = cbox(c, (-4.85, 21.0, 0.3), (0.45, 3.4, 3.0), "plate2")
    fv = cbox(c, (-5.1, 20.9, 0.3), (0.12, 2.2, 1.8), "vent_day")
    mx(c, fl, fv)


# ---------------------------------------------------------------------------
#  背中（背板・背骨・二基の細いイオン・スラスター）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    cbox(bk, (0, 18.6, 2.95), (8.4, 10.0, 0.6), "plate_b")                   # 背板
    cbox(bk, (0, 18.4, 3.5), (2.2, 8.6, 0.8), "frame")                       # 背骨
    for i in range(4):
        cbox(bk, (0, 15.6 + i * 1.9, 3.95), (1.4, 0.5, 0.3), "chrome")      # 背骨の節
    bevel(bk, (0, 20.6, 4.2), (4.2, 4.6, 2.0), "plate2", cut=0.6, axis="z")  # 背嚢（小さく）
    cbox(bk, (0, 20.6, 5.22), (0.3, 3.6, 0.15), "glow_night")
    cbox(bk, (0, 18.05, 4.1), (3.6, 0.8, 1.6), "hazard")
    rbox(bk, (0, 23.4, 3.7), (5.6, 0.9, 1.6), "plate", rot=(20, 0, 0))
    # 腰の後ろの小さな翼板
    wb = rbox(bk, (-2.6, 14.6, 3.4), (2.6, 2.0, 0.6), "plate", rot=(16, -14, 18))
    mx(bk, wb)
    # イオン・スラスター（右）: 細長い胴・鏡面の帯・吸気の尖頭・ノズル・発光の輪・炎
    th = s.part("back", "thruster_r", bk, pivot=(-2.4, 21.6, 4.6), rotation=(12, 0, -4))
    octa(th, (-2.4, 18.3, 4.6), 1.7, 6.2, "plate", axis="y")
    for y in (20.6, 17.0):
        octa(th, (-2.4, y, 4.6), 1.95, 0.4, "chrome", axis="y")
    taper(th, (-2.4, 21.3, 4.6), (-2.4, 23.4, 4.6), 1.6, 0.4, 2, "chrome")
    octa(th, (-2.4, 18.8, 4.6), 1.76, 1.6, "glow_soft_day", axis="y", style2="plate")
    octa(th, (-2.4, 14.6, 4.6), 2.1, 1.2, "frame", axis="y")
    ring(th, (-2.4, 14.0, 4.6), 0.82, 8, (0, 0.24, 0.26), "glow_day", axis="y")
    cbox(th, (-2.4, 13.96, 4.6), (1.5, 0.2, 1.5), "thruster_day")
    beam(th, (-3.2, 16.6, 4.6), (-4.0, 14.6, 5.4), 0.3, 1.0, "plate2")     # 外のヒレ
    fx = s.fx("thrust", "r", th, pivot=(-2.4, 13.9, 4.6))
    taper(fx, (-2.4, 13.9, 4.6), (-2.4, 7.0, 4.6), 1.6, 0.35, 3, "flame_day")
    taper(fx, (-2.4, 13.85, 4.6), (-2.4, 10.0, 4.6), 0.8, 0.2, 2, "flame_core_day",
          round_=False)


# ---------------------------------------------------------------------------
#  液体金属の滴（背中の後ろを二重の軌道で回る）
# ---------------------------------------------------------------------------
def droplets(s):
    C = (0.0, 19.0, 8.4)
    d = s.part("extra", "droplets", "body", pivot=C)
    sp = s.fx("spin", "drops", d, pivot=C)
    for k in range(3):
        a = np.radians(k * 120 + 30)
        bead(sp, (C[0] + np.sin(a) * 4.4, C[1] + np.cos(a) * 4.4, C[2]), 0.62)
    sp2 = s.fx("spin", "drops2", d, pivot=(C[0], C[1], C[2] - 0.4))
    for k in range(3):
        a = np.radians(k * 120 + 90)
        bead(sp2, (C[0] + np.sin(a) * 2.7, C[1] + np.cos(a) * 2.7, C[2] - 0.4), 0.42)
    # 軌道の中心の小さな核（細い光の輪）
    cg = s.fx("glow", "drops", d, pivot=C)
    bead(cg, C, 0.5, "chrome")
    ring(cg, C, 1.0, 8, (0, 0.14, 0.14), "glow_soft_night", axis="z")


# ---------------------------------------------------------------------------
#  腕（細い上腕・後ろへ流れる肘のヒレ・外側の刃のヒレの篭手）
# ---------------------------------------------------------------------------
def arms(s):
    ar = s.part("arms", "upper_r", "rightArm", pivot=(ARM_X, 20.0, 0))
    cbox(ar, (-6.0, 20.3, 0.0), (5.3, 5.2, 5.3), "plate_b")
    op = rbox(ar, (-8.75, 19.8, 0.1), (0.5, 3.4, 3.8), "plate", rot=(0, 0, 3))
    line_on(ar, op, "west", (0.15, 0.5), (0.85, 0.5), 0.22, 0.18, "glow_day")
    cbox(ar, (-6.0, 17.85, 0.0), (5.6, TRIM_W, 5.6), "chrome")
    el = s.part("arms", "elbow_r", "rightArm", pivot=(ARM_X, 16.8, 0))
    cbox(el, (-6.0, 16.9, 0.0), (5.3, 1.4, 5.3), "frame")
    octa(el, (-8.45, 16.9, 0.2), 1.6, 0.5, "chrome", axis="x")
    octa(el, (-8.7, 16.9, 0.2), 0.7, 0.2, "glow_day", axis="x")
    taper(el, (-6.2, 16.9, 2.4), (-6.4, 18.0, 4.6), 1.8, 0.4, 2, "plate2", round_=False)
    # 前腕: 手首へ向かって細くなる篭手と、外側の刃のヒレ
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=(ARM_X, 15.0, 0))
    cbox(fa, (-6.0, 14.95, 0), (5.2, 3.1, 5.25), "plate")
    blade = rbox(fa, (-8.8, 14.9, 0.7), (0.5, 3.0, 4.4), "rip_day", rot=(-12, 0, 3))
    line_on(fa, blade, "west", (0.04, 0.95), (0.96, 0.25), 0.22, 0.18, "glow_day")
    taper(fa, (-8.8, 15.7, 2.8), (-9.0, 16.9, 4.9), 1.0, 0.25, 2, "chrome", round_=False)
    fq = rbox(fa, (-6.1, 14.85, -2.72), (4.0, 3.0, 0.6), "quick", rot=(-6, 0, 0))
    line_on(fa, fq, "north", (0.5, 0.08), (0.5, 0.92), 0.2, 0.16, "glow_day")
    rbox(fa, (-6.1, 14.85, 2.72), (4.0, 3.0, 0.6), "plate_b", rot=(6, 0, 0))
    cbox(fa, (-6.0, 13.45, 0), (5.5, TRIM_W, 5.6), "chrome")
    # 拳: 甲の鏡面・指の関節・二節の指・親指
    h = s.part("arms", "gauntlet_r", "rightArm", pivot=(ARM_X, 13.2, 0))
    cbox(h, (-6.0, 12.15, 0.0), (5.3, 2.7, 5.5), "plate")
    rbox(h, (-6.0, 12.55, -2.92), (4.4, 1.3, 0.6), "chrome", rot=(-10, 0, 0))
    for i in range(4):
        x = -7.65 + i * 1.1
        cbox(h, (x, 12.6, -3.3), (0.7, 0.4, 0.3), "frame")
        rbox(h, (x, 11.7, -2.88), (0.8, 1.2, 0.6), "plate_b", rot=(18, 0, 0))
        rbox(h, (x, 10.85, -2.5), (0.75, 0.9, 0.55), "plate_b", rot=(40, 0, 0))
    rbox(h, (-3.25, 12.2, -1.3), (0.6, 1.8, 1.4), "plate_b", rot=(0, 0, -10))
    rbox(h, (-8.68, 12.3, 0), (0.4, 0.9, 0.9), "gem_accent", rot=(45, 0, 0))


# ---------------------------------------------------------------------------
#  肩（涙滴形の細いフェアリング: 前が丸く、後ろへ尾を引く）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "fairing_r", "rightArm")
    body_ = bevel(p, (-6.9, 23.9, 0.2), (4.8, 2.6, 6.2), "plate", cut=0.9, axis="x",
                  rot=(0, 0, -14))
    top = stick(p, body_[0], "up", 0.42, 0.45, (3.0, 4.6, 0.3), "quick", sink=0.1)
    line_on(p, top, "up", (0.5, 0.06), (0.5, 0.94), 0.22, 0.18, "glow_day")
    # 尾（後ろへ細く流れる）と、前の丸い鼻
    taper(p, (-7.0, 24.0, 3.1), (-7.4, 24.5, 6.6), 2.3, 0.5, 3, "plate", round_=False)
    rbox(p, (-6.9, 23.85, -3.05), (3.6, 1.8, 0.8), "chrome", rot=(-20, 0, -14))
    # 上の小さな後退翼
    feather(p, (-7.2, 25.0, 0.0), (-7.9, 26.4, 4.6), 1.0, 0.3, 0.3, "plate2", "glow_day", n=2)
    # 外の垂れ（細い二枚）
    l1 = rbox(p, (-9.15, 22.0, 0.3), (0.7, 2.4, 5.4), "emblem_day", rot=(0, 0, 12))
    stick(p, l1, "west", 0.5, 0.05, (5.0, TRIM_W, 0.2), "chrome", sink=0.05)
    rbox(p, (-9.35, 20.4, 0.5), (0.6, 1.6, 4.6), "plate2", rot=(0, 0, 9))


# ---------------------------------------------------------------------------
#  兜（弾頭形のドーム・流れる稜・ヘルメスの翼・V 字のスリット）
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 31.3, 0.3), (9.9, 4.6, 10.2), "chrome", cut=1.0, axis="z")
    rbox(hm, (0, 32.7, -4.95), (8.4, 2.2, 0.8), "plate", rot=(-38, 0, 0))      # 額の斜面
    rbox(hm, (0, 32.3, 5.55), (8.4, 2.2, 0.8), "plate", rot=(35, 0, 0))       # 後ろの斜面
    # 稜: 額から頭頂を越えて後ろへ流れ、尾になる
    polyline(hm, [(0, 31.4, -5.7), (0, 33.9, -3.4), (0, 34.3, 0.6), (0, 33.6, 4.6),
                  (0, 31.6, 7.4)], [0.8, 0.8, 0.7, 0.55], [1.1, 1.2, 1.0, 0.8], "plate")
    polyline(hm, [(0, 32.05, -5.55), (0, 34.55, -3.25), (0, 34.95, 0.6), (0, 34.2, 4.6)],
             0.86, 0.22, "glow_night")
    cbox(hm, (0, 27.0, 5.05), (8.8, 4.8, 0.8), "plate")                         # 後頭部
    rbox(hm, (0, 24.3, 5.3), (8.4, 1.8, 0.8), "plate_b", rot=(20, 0, 0))       # しころ
    # 側板と耳の円盤
    sd = cbox(hm, (-4.95, 27.2, 0.3), (0.9, 4.8, 8.6), "plate2")
    sdl = stick(hm, sd, "west", 0.5, 0.15, (7.6, 0.24, 0.16), "glow_soft_day", sink=0.05)
    ear = octa(hm, (-5.5, 28.0, 0.6), 2.6, 0.5, "chrome", axis="x")
    eg = octa(hm, (-5.8, 28.0, 0.6), 1.1, 0.25, "glow_day", axis="x")
    mx(hm, sd, sdl, ear, eg)
    # 顔: 中央で前へ折れた二枚の面頬と鏡面の稜、尖った顎、頬当て
    fc = rbox(hm, (-2.0, 26.3, -5.1), (4.2, 4.6, 0.7), "plate", rot=(0, 16, 0))
    br = rbox(hm, (-2.3, 29.65, -5.25), (4.6, 1.0, 1.0), "chrome", rot=(-12, 16, 8))
    ck = rbox(hm, (-3.7, 25.6, -3.6), (1.3, 3.6, 3.0), "plate2", rot=(0, 34, -6))
    ckl = line_on(hm, ck, "west", (0.15, 0.2), (0.15, 0.85), 0.2, 0.16, "glow_day")
    mx(hm, fc, br, ck, ckl)
    cbox(hm, (0, 26.1, -5.75), (0.5, 4.0, 0.5), "chrome")
    cbox(hm, (0, 26.3, -4.75), (7.6, 4.6, 0.3), "frame")
    rbox(hm, (0, 23.95, -4.75), (2.8, 1.0, 1.4), "chrome", rot=(-30, 0, 0))   # 顎
    # ヘルメスの翼（こめかみから後ろ上へ掃き上げる三枚羽）
    wg = s.part("helmet", "wing_r", hm, pivot=(-5.7, 28.4, 0.8))
    octa(wg, (-5.95, 28.6, 1.2), 1.7, 0.7, "plate2", axis="x")
    feather(wg, (-5.7, 29.5, 0.0), (-6.6, 34.2, 7.0), 1.8, 0.5, 0.44, "plate", "glow_day")
    feather(wg, (-5.85, 28.7, 0.8), (-7.1, 31.9, 8.2), 1.5, 0.45, 0.4, "chrome")
    feather(wg, (-5.85, 27.9, 1.4), (-6.9, 29.4, 7.4), 1.2, 0.4, 0.38, "plate2", "glow_soft_day")
    # バイザー: 顔の中央で鋭く折れた V 字のスリット一本（暗い溝 + シアンの光）
    vz = s.part("visor", "eye", "head")
    vd = rbox(vz, (-1.8, 28.1, -5.6), (4.0, 1.1, 0.4), "dark", rot=(0, 16, 20))
    mirror_x(vz, vd)
    fg = s.fx("glow", "visor", vz, pivot=(0, 27.6, -5.8))
    half = rbox(fg, (-1.8, 28.1, -5.8), (3.8, 0.5, 0.3), "visor", rot=(0, 16, 20))
    mirror_x(fg, half)
