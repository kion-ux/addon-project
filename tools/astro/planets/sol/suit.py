# -*- coding: utf-8 -*-
"""太陽 — 恒星機装 ソル・オーバードライブ（Sol Overdrive Frame）。第 9 形態・最強の形。

白金（plate）と金（plate2）の装甲、紅のインナー（六角メッシュ）と紅の差し板、全身を走る太陽の橙の発光線。
* 頭の後ろで回る、棘のあるコロナの光輪（金の刃の棘と炎の棘が交互・内側の光の輪は逆回転）
* 両肩から立つ紅炎（プロミネンス）のループと炎の舌、背中の左右に双極の紅炎アーチ（炎の舌つき）
* 胸の核融合炉（太陽の粒状斑の星核・金の八角の枠・閉じ込めの環が回り、光が脈打つ・放射状の光条）
* 兜の日輪の前立て（七本の光条と小さな太陽）、燃えるような V 字のバイザー、耳の後ろへ流れる炎の羽根
* 膝・肩の外縁・腰の草摺は「光条」「炎の舌」の形（尖った先）。踵と背中に炎のスラスター

座標: -Z が正面、右手が -X。右側だけ作って `_r` を付ける → 左は自動で鏡映。
回転: rx 正 = 上端が前へ / ry 正 = 正面が右(-X)を向く / rz 正 = 上端が +X へ（右の部品なら下端が外へ）。
"""
from __future__ import annotations

import math

import numpy as np

from astro_common import (bevel, beam, cbox, line_on, mat_cube, octa, polyline, rbox, ring,
                          stick, taper)
from astro_suit import ARM_X, LEG_X, Suit, mirror_x
from hd_space import rot

GOLD_W = 0.42          # 縁取りの幅

HALO_C = (0.0, 28.6, 8.5)       # コロナの光輪の中心（頭の後ろ）
REACTOR = (0.0, 20.2, -4.35)    # 胸の核融合炉の中心（面）


# ===========================================================================
#  塗り（astro_paint.suit_styles("sol") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate": {"line": (176, 120, 52)},
    "plate_b": {"line": (150, 100, 44)},
    "plate2": {"line": (130, 70, 18)},
    "inner": {"base": (92, 20, 14), "glow": (255, 150, 40)},
    "crimson": {"kind": "armor", "base": (178, 40, 26), "light": (236, 104, 64),
                "dark": (112, 22, 14), "line": (64, 12, 8), "glow": (255, 172, 40)},
    "crimson_b": {"kind": "armor", "base": (128, 26, 16), "light": (190, 70, 44),
                  "dark": (80, 14, 8), "line": (48, 8, 6), "panel": 0, "glow": (255, 172, 40)},
    "bronze": {"kind": "trim", "base": (214, 132, 44), "light": (255, 214, 130),
               "dark": (132, 70, 20), "line": (70, 34, 10)},
    "visor": {"glow": (255, 196, 70), "light": (255, 255, 236), "deep": (226, 70, 18),
              "emit": 14},
    "glow": {"glow": (255, 166, 36), "light": (255, 246, 200)},
    "glow_hot": {"kind": "glowline", "glow": (255, 214, 120), "light": (255, 255, 240),
                 "bevel": False, "outline": False},
    "plasma": {"kind": "glowline", "glow": (255, 112, 28), "light": (255, 236, 168),
               "bevel": False, "outline": False, "emit": 10},
    "flame": {"glow": (255, 160, 40), "light": (255, 248, 214), "deep": (214, 56, 14)},
    "flame_core": {"kind": "flame", "glow": (255, 236, 160), "light": (255, 255, 255),
                   "deep": (255, 160, 50), "bevel": False, "outline": False},
    "prom": {"kind": "flame", "dir": "up", "glow": (255, 120, 30), "light": (255, 236, 164),
             "deep": (196, 30, 12), "bevel": False, "outline": False},
    "prom_core": {"kind": "flame", "dir": "up", "glow": (255, 220, 120), "light": (255, 255, 240),
                  "deep": (255, 140, 40), "bevel": False, "outline": False},
    "corona": {"kind": "flame", "dir": "up", "glow": (255, 178, 50), "light": (255, 250, 220),
               "deep": (230, 70, 20), "bevel": False, "outline": False},
    "core": {"planet": "sol", "emit": 18, "halo": (255, 230, 140)},
    "thruster": {"glow": (255, 170, 50), "light": (255, 250, 220), "deep": (190, 40, 12)},
    "vent": {"glow": (255, 150, 40), "deep": (150, 30, 10)},
    "serial": {"text": "SOL-09", "under": {"kind": "armor", "base": (255, 244, 196), "panel": 0,
                                            "line": (176, 120, 52)},
               "ink": (150, 40, 20)},
    "hazard": {"c1": (255, 172, 40), "c2": (110, 22, 14)},
    "emblem": {"color": (255, 160, 40)},
    "face": {"kind": "armor", "base": (255, 236, 200), "panel": 0, "line": (150, 96, 50)},
    "grille": {"kind": "vent", "base": (120, 40, 24), "glow": (255, 150, 40), "deep": (120, 20, 8),
               "slat": 2},
    "gem": {"glow": (255, 120, 40), "deep": (150, 20, 10)},
}

# ===========================================================================
#  部位アニメ（Molang。q.anim_time は 12 秒でループするので周波数は 30°/秒の倍数に）
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # コロナの光輪: 外の棘はゆっくり、内の光の輪は逆向きに速く
        "fx_spin_halo": {"rotation": [0, 0, "q.anim_time * 30.0"]},
        "fx_spin_halo_in": {"rotation": [0, 0, "-q.anim_time * 90.0"]},
        # 胸の炉: 閉じ込めの環が回り、光が強く脈打つ
        "fx_spin_reactor": {"rotation": [0, 0, "q.anim_time * 120.0"]},
        "fx_glow_reactor": {"scale": "1.0 + math.sin(q.anim_time * 180.0) * 0.07"},
        # 紅炎は揺らめく（肩・背中・耳の炎）
        "fx_glow_prom_r": {"scale": ["1.0", "1.0 + math.sin(q.anim_time * 360.0) * 0.06", "1.0"]},
        "fx_glow_prom_l": {"scale": ["1.0", "1.0 + math.sin(q.anim_time * 360.0 + 120.0) * 0.06", "1.0"]},
        "fx_glow_arch_r": {"scale": ["1.0 + math.sin(q.anim_time * 300.0) * 0.04",
                                     "1.0 + math.sin(q.anim_time * 300.0) * 0.05", "1.0"]},
        "fx_glow_arch_l": {"scale": ["1.0 + math.sin(q.anim_time * 300.0 + 90.0) * 0.04",
                                     "1.0 + math.sin(q.anim_time * 300.0 + 90.0) * 0.05", "1.0"]},
    },
    "thrust": {
        # 空中では光輪が速く回り、紅炎が大きく燃え上がる
        "fx_spin_halo": {"rotation": [0, 0, "v.astro_air * q.anim_time * 90.0"]},
        "fx_glow_prom_r": {"scale": ["1.0", "1.0 + v.astro_air * 0.18", "1.0"]},
        "fx_glow_prom_l": {"scale": ["1.0", "1.0 + v.astro_air * 0.18", "1.0"]},
    },
    "sprint": {
        # 疾走中は背中の紅炎が後ろへなびく
        "fx_glow_arch_r": {"rotation": ["v.astro_run * 16.0", 0, 0]},
    },
}


# ===========================================================================
#  形の補助
# ===========================================================================
def ray(bone, c, a, r0, L, w0, w1, n, depth, style, tilt=0.0, styles=None, yaw=0.0, **kw):
    """c から面内の角度 a（0 = 上、正 = +X へ）の向きへ、半径 r0 から長さ L の先細りの光条（板）。
    n 段で幅 w0 → w1。tilt は面ごと X 軸まわりに傾ける（負で上が後ろへ）、yaw は Y 軸まわり。"""
    R = rot(tilt, yaw, 0) @ rot(0, 0, a)
    u = R @ np.array([0.0, 1.0, 0.0])
    out = []
    for i in range(n):
        t = (i + 0.5) / n
        w = w0 + (w1 - w0) * t
        cen = np.asarray(c, float) + u * (r0 + L * t)
        st = styles[i % len(styles)] if styles else style
        out.append(mat_cube(bone, cen, (w, L / n * 1.12, depth), st, R, **kw))
    return out


def spear(bone, c, a, r0, L, w, depth, style, tilt=0.0, tip=None, **kw):
    """c から角度 a の向きに、半径 r0 から長さ L の先の尖った光条（槍の穂の形: 幅 w の板 + 45° の菱形の先）。
    tilt は面ごと X 軸まわりに傾ける。tip で先の菱形だけ別の塗り。"""
    T = rot(tilt, 0, 0)
    R = T @ rot(0, 0, a)
    u = R @ np.array([0.0, 1.0, 0.0])
    c = np.asarray(c, float)
    Lb = max(0.2, L - w / 2)
    out = [mat_cube(bone, c + u * (r0 + Lb / 2), (w, Lb, depth), style, R, **kw)]
    sd = w / math.sqrt(2)
    out.append(mat_cube(bone, c + u * (r0 + Lb), (sd, sd, depth * 0.96), tip or style,
                        T @ rot(0, 0, a + 45), **kw))
    return out


def loop_pts(a, b, h, out=(0.0, 0.0, 0.0), n=6):
    """a から b へ、高さ h（+Y）に膨らみ、頂で out だけずれる弧の点列（紅炎のループ）。"""
    pts = []
    for i in range(n + 1):
        t = i / n
        s = math.sin(math.pi * t)
        pts.append(tuple(a[k] + (b[k] - a[k]) * t + out[k] * s + (h * s if k == 1 else 0.0)
                         for k in range(3)))
    return pts


# ===========================================================================
def build_suit(s: Suit):
    s.inner_suit(gap=0.3)
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    arms(s)
    shoulders(s)
    helmet(s)
    halo(s)


# ---------------------------------------------------------------------------
#  ブーツ（足首から。尖ったつま先・踵の拍車・踵の炎）
# ---------------------------------------------------------------------------
def boots(s):
    X = LEG_X
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (X, -0.3, -0.6), (5.3, 0.8, 6.8), "frame")                    # 靴底
    cbox(b, (X, 1.7, -0.2), (5.3, 3.2, 5.8), "plate")                     # 足の殻
    toe = rbox(b, (X, 1.15, -3.25), (4.9, 2.3, 1.8), "plate", rot=(-40, 0, 0))
    stick(b, toe, "north", 0.5, 0.5, (0.45, 1.6, 0.25), "glow", sink=0.05)
    taper(b, (X, 0.55, -3.9), (X, 0.3, -5.3), 3.2, 1.0, 2, "plate2", round_=False)   # 尖った爪先
    rbox(b, (X, 3.4, -2.55), (4.1, 2.2, 0.8), "plate", rot=(-28, 0, 0))   # 甲
    rbox(b, (X, 3.55, -2.98), (1.2, 1.2, 0.4), "gem", rot=(-28, 0, 45))
    rbox(b, (X, 1.6, 2.75), (4.7, 2.9, 0.9), "crimson", rot=(8, 0, 0))   # 踵（紅）
    taper(b, (X, 1.0, 3.2), (X, -0.2, 5.0), 1.6, 0.5, 2, "plate2", round_=False)    # 踵の拍車
    cbox(b, (X, 0.45, 2.3), (3.0, 1.0, 1.2), "frame")                      # 踵の噴射口
    cbox(b, (X, -0.08, 2.3), (2.2, 0.2, 0.8), "thruster")
    fx = s.fx("thrust", "heel_r", b, pivot=(X, -0.2, 2.3))
    taper(fx, (X, -0.2, 2.3), (X, -2.6, 2.6), 1.6, 0.4, 2, "flame")
    # 足首の日輪（外）: 八角の金具 + 光る芯 + 放射の小さな光条
    octa(b, (X - 2.72, 2.9, 0.2), 2.1, 0.55, "bronze", axis="x")
    octa(b, (X - 3.0, 2.9, 0.2), 1.0, 0.3, "glow_hot", axis="x")
    cbox(b, (X - 2.68, 0.95, -0.7), (0.22, 0.35, 4.4), "glow")              # 外側の発光線


# ---------------------------------------------------------------------------
#  脚（脛・日輪の膝・腿）
# ---------------------------------------------------------------------------
def legs(s):
    X = LEG_X
    g = s.part("legs", "greave_r", "rightLeg")
    cbox(g, (X, 5.2, 0.05), (5.3, 4.4, 5.5), "plate")                    # 脛の殻
    keel = rbox(g, (X - 0.72, 5.0, -2.95), (1.55, 4.3, 0.8), "plate2", rot=(0, 22, 0))
    kl = line_on(g, keel, "north", (0.85, 0.05), (0.85, 0.95), 0.24, 0.2, "glow")
    mirror_x(g, keel, kl, about=X)                                       # 脛の稜（金の V）
    cbox(g, (X, 3.25, -2.95), (4.6, 0.5, 0.6), "crimson")               # 脛の下の紅の帯
    cbox(g, (X, 8.1, 0.05), (5.25, 1.5, 5.35), "frame")                  # 膝の関節
    # 日輪の膝当て: 面取りした白の板 + 中央の太陽の宝玉 + 上へ放つ三本の光条
    bevel(g, (X, 7.5, -3.0), (3.7, 3.0, 1.2), "plate", cut=0.6, axis="z")
    rbox(g, (X, 7.5, -3.66), (1.3, 1.3, 0.5), "core", rot=(0, 0, 45))
    for a, L in ((-38, 1.8), (0, 2.6), (38, 1.8)):
        ray(g, (X, 7.5, -3.45), a, 0.95, L, 1.0, 0.45, 1, 0.4, "plate2", tilt=-14)
    cbox(g, (X, 6.05, -3.55), (3.2, GOLD_W, 0.5), "bronze")
    # ふくらはぎ（紅）と排気口
    calf = rbox(g, (X, 5.4, 2.85), (4.6, 4.2, 1.0), "crimson", rot=(-8, 0, 0))
    stick(g, calf, "south", 0.5, 0.5, (2.6, 2.4, 0.3), "vent", sink=0.1)
    # 外側の炎の舌のヒレ（上へ尖る）
    fin = rbox(g, (X - 2.75, 5.4, 0.9), (0.7, 3.6, 3.0), "plate2", rot=(-12, 0, -6))
    line_on(g, fin, "west", (0.2, 0.15), (0.75, 0.85), 0.24, 0.2, "glow")
    taper(g, (X - 2.85, 7.0, 1.4), (X - 3.2, 9.6, 2.4), 1.4, 0.35, 2, "plate2", round_=False)
    # 腿
    t = s.part("legs", "thigh_r", "rightLeg", pivot=(X, 11.6, 0))
    cbox(t, (X, 10.4, 0.05), (5.2, 3.3, 5.4), "plate_b")
    th = rbox(t, (X, 10.35, -2.85), (4.4, 3.4, 0.8), "plate", rot=(-5, 0, 0))
    line_on(t, th, "north", (0.2, 0.1), (0.5, 0.75), 0.26, 0.2, "glow")
    line_on(t, th, "north", (0.8, 0.1), (0.5, 0.75), 0.26, 0.2, "glow")
    cbox(t, (X, 8.75, -2.9), (4.2, GOLD_W, 0.6), "bronze")
    cbox(t, (X - 2.62, 10.2, 0.3), (0.6, 3.0, 3.8), "plate2",
         decals={"west": {"decal": "serial", "text": "SOL-9", "ink": (150, 40, 20)}})


# ---------------------------------------------------------------------------
#  腰（ベルト・日輪のバックル・炎の舌の草摺）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    cbox(w, (0, 12.6, 0), (9.5, 1.7, 5.9), "frame")
    cbox(w, (0, 12.95, -2.98), (8.8, 0.25, 0.2), "glow")
    # 日輪のバックル: 金の八角 + 小さな太陽 + 放射の光条
    octa(w, (0, 12.6, -3.2), 2.8, 0.8, "plate2", axis="z")
    cbox(w, (0, 12.6, -3.66), (1.5, 1.5, 0.4), "core")
    for a in (90, 270):
        ray(w, (0, 12.6, -3.4), a, 1.3, 1.6, 0.8, 0.3, 2, 0.35, "bronze")
    # 前垂れ: 下へ尖る金の炎の舌（紅の下板）
    rbox(w, (0, 10.7, -3.0), (3.2, 2.6, 0.6), "crimson_b", rot=(-12, 0, 0))
    ray(w, (0, 11.6, -3.25), 180, 0.0, 3.6, 2.6, 0.7, 2, 0.5, "plate2", tilt=-12)
    fr = rbox(w, (-2.45, 10.95, -2.95), (2.0, 2.4, 0.7), "plate", rot=(-10, 14, 6))
    mirror_x(w, fr)
    # 草摺（腰の横）: 紅の下板 + 白の上板 + 金の縁 + 発光線 + 下へ尖る先
    t1 = rbox(w, (-5.25, 10.3, -0.2), (0.8, 4.2, 5.0), "crimson", rot=(0, 0, 12))
    t2 = rbox(w, (-5.6, 9.8, -0.2), (0.6, 3.4, 4.4), "plate", rot=(0, 0, 15))
    t3 = stick(w, t2, "west", 0.5, 0.94, (4.2, GOLD_W, 0.22), "bronze", sink=0.05)
    t4 = line_on(w, t2, "west", (0.12, 0.45), (0.88, 0.45), 0.24, 0.2, "glow")
    tips = ray(w, (-6.05, 8.3, -0.2), 180 + 15, 0.0, 2.4, 3.6, 0.8, 2, 0.5, "plate2", yaw=90)
    mirror_x(w, t1, t2, t3, t4, tips)
    rbox(w, (0, 10.8, 2.95), (6.4, 2.6, 0.8), "plate", rot=(10, 0, 0))    # 後ろ垂れ
    ray(w, (0, 9.8, 3.15), 180, 0.0, 2.4, 2.4, 0.9, 1, 0.5, "crimson", tilt=10)


# ---------------------------------------------------------------------------
#  胴（胸郭・核融合炉・光条の胸板・腹・襟）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    bevel(c, (0, 21.1, 0.0), (10.0, 6.0, 5.9), "plate", cut=0.7, axis="y")   # 胸郭（上が広い）
    cbox(c, (0, 15.9, 0.0), (7.4, 4.8, 5.2), "plate_b")                     # 腹の殻（細い）
    cbox(c, (0, 16.0, -2.62), (5.2, 4.6, 0.5), "frame")
    for y, w in ((17.25, 5.0), (16.0, 4.6), (14.75, 4.1)):                  # 腹の三段（金と紅の筋）
        rbox(c, (0, y, -2.98), (w, 1.3, 0.7), "plate2", rot=(-10, 0, 0),
             decals={"north": {"decal": "stripe", "dir": "v", "pos": 0.5, "width": 0.08,
                               "color": (150, 30, 14)}})
    ob = rbox(c, (-3.3, 16.0, -2.3), (1.4, 4.2, 1.0), "crimson", rot=(0, 36, -6))   # 脇腹
    mirror_x(c, ob)
    # 金の胸板（炉から外へ開く V）と、炉から放射する光条
    pec = rbox(c, (-2.75, 21.6, -3.05), (5.0, 4.1, 0.9), "plate2", rot=(6, 17, 9))
    trim = stick(c, pec, "north", 0.5, 0.97, (4.8, GOLD_W, 0.22), "plate", sink=0.05)
    l1 = line_on(c, pec, "north", (0.9, 0.35), (0.12, 0.62), 0.26, 0.2, "glow")
    l2 = line_on(c, pec, "north", (0.88, 0.2), (0.3, 0.08), 0.26, 0.2, "glow")
    l3 = line_on(c, pec, "north", (0.9, 0.55), (0.35, 0.92), 0.26, 0.2, "glow")
    low = rbox(c, (-2.3, 18.55, -2.85), (3.9, 1.5, 0.8), "crimson", rot=(-6, 12, 13))
    mirror_x(c, pec, trim, l1, l2, l3, low)
    # 襟（首の両脇に高く立つ金の板 + 白の縁）
    col = rbox(c, (-3.0, 24.5, 0.0), (2.2, 1.8, 5.2), "plate2", rot=(0, 0, -24))
    colt = stick(c, col, "up", 0.5, 0.5, (1.8, 4.8, 0.25), "plate", sink=0.1)
    mirror_x(c, col, colt)
    # 核融合炉: 黒い菱形の台 → 金の八角の枠 → 紅の輪 → 太陽（脈打つ光）→ 回る閉じ込めの環
    X, Y, Z = REACTOR
    rbox(c, (X, Y, Z + 0.65), (4.4, 4.4, 0.8), "dark", rot=(0, 0, 45))
    octa(c, (X, Y, Z + 0.25), 4.0, 0.45, "plate2", axis="z")
    octa(c, (X, Y, Z + 0.05), 3.3, 0.35, "crimson_b", axis="z")
    for a in range(0, 360, 45):                                             # 炉の放射の光条（短い）
        ray(c, (X, Y, Z + 0.2), a + 22.5, 2.05, 0.9, 0.5, 0.2, 1, 0.3, "glow_hot")
    gl = s.fx("glow", "reactor", c, pivot=(X, Y, Z - 0.1))
    cbox(gl, (X, Y, Z - 0.1), (2.6, 2.6, 0.9), "core")
    rbox(gl, (X, Y, Z - 0.12), (2.3, 2.3, 0.86), "core", rot=(0, 0, 45))
    sp = s.fx("spin", "reactor", c, pivot=(X, Y, Z - 0.8))
    ring(sp, (X, Y, Z - 0.8), 1.75, 8, (0, 0.3, 0.3), "glow_hot", axis="z",
         styles=["glow_hot", "bronze"])
    # 脇: 白い板と排気口
    fl = cbox(c, (-4.85, 21.0, 0.3), (0.5, 3.6, 3.2), "plate2")
    fv = cbox(c, (-5.12, 20.9, 0.3), (0.15, 2.4, 2.0), "vent")
    mirror_x(c, fl, fv)


# ---------------------------------------------------------------------------
#  背中（背板・炉の背嚢・双発スラスター・双極の紅炎アーチ）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    cbox(bk, (0, 18.7, 2.95), (8.6, 9.8, 0.7), "plate_b")                  # 背板
    cbox(bk, (0, 18.4, 3.6), (2.6, 8.4, 1.0), "frame")                     # 背骨
    bevel(bk, (0, 19.6, 4.6), (5.2, 6.2, 2.6), "plate", cut=0.8, axis="z")  # 背嚢
    rbox(bk, (0, 22.95, 4.25), (4.6, 1.0, 2.6), "plate2", rot=(25, 0, 0))
    side = cbox(bk, (-2.65, 19.6, 4.6), (0.3, 4.4, 1.8), "plate2")
    mirror_x(bk, side)
    cbox(bk, (0, 17.1, 5.95), (3.6, 0.9, 0.2), "hazard")
    octa(bk, (0, 20.0, 5.95), 2.6, 0.4, "bronze", axis="z")                # 背の小さな炉
    cbox(bk, (0, 20.0, 6.2), (1.6, 1.6, 0.4), "core")
    # スラスター（右。下後ろへ向ける）
    th = s.part("back", "thruster_r", bk, pivot=(-1.4, 16.9, 5.4), rotation=(18, 0, -8))
    octa(th, (-1.4, 15.6, 5.4), 2.2, 3.0, "plate", axis="y")
    octa(th, (-1.4, 16.3, 5.4), 2.45, 0.4, "bronze", axis="y")
    octa(th, (-1.4, 13.6, 5.4), 2.8, 1.4, "crimson_b", axis="y")
    ring(th, (-1.4, 12.95, 5.4), 1.1, 6, (0, 0.28, 0.3), "glow", axis="y")
    cbox(th, (-1.4, 12.92, 5.4), (2.0, 0.2, 2.0), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.4, 12.85, 5.4))
    taper(fx, (-1.4, 12.85, 5.4), (-1.4, 5.0, 5.4), 2.3, 0.45, 3, "flame")
    taper(fx, (-1.4, 12.8, 5.4), (-1.4, 8.6, 5.4), 1.1, 0.25, 2, "flame_core", round_=False)
    # 双極の紅炎アーチ（背の左右。上の肩甲骨から外へ膨らみ、腰の上へ戻る）
    ar = s.part("back", "arch_r", bk, pivot=(-2.6, 19.0, 5.2))
    A, B = (-3.9, 22.6, 5.0), (-4.5, 15.0, 4.0)
    for p in (A, B):                                                       # 根元の金の磁気コイル
        octa(ar, p, 1.5, 1.1, "plate2", axis="x")
        octa(ar, (p[0] - 0.62, p[1], p[2]), 0.8, 0.3, "glow_hot", axis="x")
    fa = s.fx("glow", "arch_r", ar, pivot=(-3.6, 19.0, 5.0))
    pts = loop_pts((A[0] - 0.3, A[1], A[2] + 0.1), (B[0] - 0.3, B[1], B[2] + 0.1), 0.0,
                   out=(-5.6, 0.2, 2.4), n=6)
    polyline(fa, pts, 0.9, 0.9, "plasma")
    polyline(fa, [(q[0] + 0.15, q[1], q[2] + 0.05) for q in pts], 0.4, 1.25, "prom_core")
    # 弧の外へ立つ炎の舌
    for k, (a, L) in zip((2, 3, 4), ((-50, 3.4), (-80, 4.2), (-112, 3.2))):
        ray(fa, pts[k], a, 0.3, L, 1.7, 0.35, 2, 0.5, "prom", yaw=-12)


# ---------------------------------------------------------------------------
#  腕（上腕・肘・篭手・ガントレット）
# ---------------------------------------------------------------------------
def arms(s):
    ar = s.part("arms", "upper_r", "rightArm", pivot=(ARM_X, 20.0, 0))
    bevel(ar, (-6.1, 20.4, 0.0), (5.4, 5.6, 5.8), "plate", cut=0.5, axis="y")
    cbox(ar, (-6.1, 17.85, 0.0), (5.7, 0.7, 6.1), "crimson")                # 腕章（紅）
    cbox(ar, (-6.1, 17.85, 0.0), (5.8, 0.22, 6.2), "bronze")
    op = rbox(ar, (-8.85, 19.6, 0.0), (0.6, 2.8, 3.6), "plate2", rot=(0, 0, 4))
    line_on(ar, op, "west", (0.5, 0.12), (0.5, 0.88), 0.26, 0.2, "glow")
    el = s.part("arms", "elbow_r", "rightArm", pivot=(ARM_X, 16.8, 0))
    cbox(el, (-6.0, 16.9, 0.0), (5.3, 1.5, 5.3), "frame")
    octa(el, (-8.45, 16.9, 0.2), 1.8, 0.5, "bronze", axis="x")
    rbox(el, (-6.3, 17.0, 2.75), (3.0, 1.9, 0.8), "crimson", rot=(-18, 0, 0))   # 肘当て
    taper(el, (-6.3, 17.2, 3.1), (-6.4, 18.6, 5.0), 1.2, 0.3, 2, "plate2", round_=False)   # 肘の棘
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=(ARM_X, 15.0, 0))
    cbox(fa, (-6.0, 14.95, 0), (4.9, 3.1, 5.1), "plate")
    ob = rbox(fa, (-8.7, 14.85, 0), (0.8, 3.3, 4.8), "plate2", rot=(0, 0, 7))
    stick(fa, ob, "west", 0.5, 0.55, (1.0, 2.6, 0.6), "crimson", sink=0.1)
    line_on(fa, ob, "west", (0.12, 0.3), (0.35, 0.85), 0.24, 0.2, "glow")
    line_on(fa, ob, "west", (0.65, 0.85), (0.88, 0.3), 0.24, 0.2, "glow")
    # 篭手の外の炎の舌（上外へ尖る）
    ray(fa, (-9.0, 15.6, 0.6), -25, 0.0, 3.2, 1.6, 0.35, 3, 0.5, "plate2", yaw=-8)
    rbox(fa, (-6.15, 14.85, -2.72), (4.1, 3.1, 0.7), "plate2", rot=(-8, 0, 0))
    rbox(fa, (-6.15, 14.85, 2.72), (4.1, 3.1, 0.7), "plate_b", rot=(8, 0, 0))
    cbox(fa, (-6.0, 13.42, 0), (5.7, GOLD_W, 5.9), "bronze")
    h = s.part("arms", "gauntlet_r", "rightArm", pivot=(ARM_X, 13.2, 0))
    cbox(h, (-6.0, 12.15, 0.0), (5.3, 2.7, 5.5), "plate")
    rbox(h, (-6.0, 12.6, -2.95), (4.6, 1.3, 0.7), "plate2", rot=(-10, 0, 0))
    for i in range(4):
        x = -7.65 + i * 1.1
        cbox(h, (x, 12.65, -3.37), (0.7, 0.45, 0.3), "bronze")
        rbox(h, (x, 11.35, -2.75), (0.85, 1.9, 0.6), "plate_b", rot=(26, 0, 0))
    rbox(h, (-3.2, 12.2, -1.3), (0.6, 1.8, 1.4), "plate_b", rot=(0, 0, -10))
    cbox(h, (-8.72, 12.3, 0), (0.4, 1.1, 1.1), "core")                        # 手の甲の小さな太陽


# ---------------------------------------------------------------------------
#  肩（重ねた日輪の肩当て・外縁の光条・紅炎のループ）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    dome = bevel(p, (-7.1, 24.1, 0.0), (6.0, 3.2, 7.2), "plate2", cut=1.0, axis="x",
                 rot=(0, 0, -14))
    top = stick(p, dome[0], "up", 0.42, 0.5, (3.9, 4.8, 0.5), "plate", sink=0.15)
    stick(p, top, "west", 0.5, 0.5, (4.8, 0.5, 0.25), "bronze", sink=0.05)
    line_on(p, top, "up", (0.12, 0.5), (0.88, 0.5), 0.3, 0.2, "glow")
    # 外へ開いて垂れる板（白・紅）と金の縁
    l1 = rbox(p, (-9.85, 22.2, 0.0), (1.0, 2.6, 6.8), "plate", rot=(0, 0, 18),
              decals={"west": {"decal": "emblem", "color": (255, 160, 40)}})
    stick(p, l1, "west", 0.5, 0.04, (6.4, GOLD_W, 0.22), "bronze", sink=0.05)
    l2 = rbox(p, (-10.15, 20.5, 0.1), (0.9, 2.1, 6.2), "crimson", rot=(0, 0, 14))
    stick(p, l2, "west", 0.5, 0.05, (5.8, GOLD_W, 0.22), "bronze", sink=0.05)
    # 外縁から下外へ放つ光条（日輪の肩）
    for zc in (-2.2, 0.0, 2.2):
        ray(p, (-10.3, 19.6, zc), -160, 0.0, 2.2 if zc else 2.8, 1.4, 0.5, 1, 0.5, "plate2")
    # 紅炎のループ（肩当ての上、前から後ろへ外へ膨らむ弧）と、弧の上の炎の舌
    PA, PB = (-6.4, 25.7, -2.6), (-9.4, 25.4, 2.6)
    for q in (PA, PB):
        octa(p, q, 1.4, 0.9, "frame", axis="y")
        octa(p, (q[0], q[1] + 0.5, q[2]), 1.0, 0.3, "glow_hot", axis="y")
    fp = s.fx("glow", "prom_r", p, pivot=(-7.9, 25.8, 0.0))
    pts = loop_pts((PA[0], PA[1] + 0.4, PA[2]), (PB[0], PB[1] + 0.4, PB[2]), 3.8,
                   out=(-1.2, 0.0, 0.0), n=6)
    polyline(fp, pts, 0.85, 0.85, "plasma")
    polyline(fp, [(q[0], q[1] + 0.1, q[2]) for q in pts], 1.1, 0.35, "prom_core")
    for k, a, L in ((2, -24, 2.2), (3, -8, 3.0), (4, 14, 2.0)):
        ray(fp, pts[k], a, 0.2, L, 1.3, 0.3, 2, 0.45, "prom", yaw=30)


# ---------------------------------------------------------------------------
#  兜（ドーム・日輪の前立て・V 字のバイザー・炎の羽根の耳・面頬）
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 31.2, 0.15), (9.8, 4.6, 10.1), "plate", cut=1.0, axis="z")
    rf = rbox(hm, (-2.45, 33.75, 0.4), (5.2, 0.8, 9.2), "plate", rot=(0, 0, -12))
    rfr = line_on(hm, rf, "up", (0.04, 0.06), (0.04, 0.94), 0.3, 0.2, "bronze")
    mirror_x(hm, rf, rfr)
    cbox(hm, (0, 34.6, 0.6), (1.4, 1.0, 8.4), "plate2")                          # 中央の稜（金）
    cbox(hm, (0, 35.15, 0.6), (0.4, 0.2, 7.6), "glow")
    rbox(hm, (0, 32.0, -4.85), (8.6, 2.6, 0.8), "plate", rot=(-30, 0, 0))       # 額の斜面
    rbox(hm, (0, 31.9, 5.2), (8.6, 2.4, 0.8), "plate", rot=(30, 0, 0))          # 後ろの斜面
    cbox(hm, (0, 26.9, 4.95), (8.8, 4.6, 0.8), "plate")                          # 後頭部
    rbox(hm, (0, 31.6, 5.45), (1.4, 2.4, 0.5), "plate2", rot=(30, 0, 0))        # 稜が後ろへ降りる
    cbox(hm, (0, 27.4, 5.45), (1.4, 4.4, 0.4), "plate2")
    cbox(hm, (0, 27.4, 5.7), (0.4, 3.6, 0.2), "glow")
    sd = cbox(hm, (-4.95, 27.3, 0.1), (0.9, 5.0, 8.4), "plate2")                 # 側板（金）
    sdl = cbox(hm, (-5.42, 26.0, 0.4), (0.2, 0.3, 6.0), "glow")
    ear = octa(hm, (-5.55, 28.0, 0.9), 2.6, 0.5, "bronze", axis="x")
    eg = octa(hm, (-5.85, 28.0, 0.9), 1.2, 0.25, "core", axis="x")
    # 耳の後ろへ流れる炎の羽根（金の刃 2 枚）
    wing = ray(hm, (-5.8, 28.8, 1.4), 58, 0.6, 4.4, 1.4, 0.3, 2, 0.4, "plate2", yaw=-90)
    mirror_x(hm, sd, sdl, ear, eg, wing)
    # 日輪の前立て: 額の小さな太陽 + 七本の光条（長短交互・少し後ろへ倒す）
    CC = (0.0, 30.4, -5.55)
    octa(hm, CC, 2.4, 0.6, "plate2", axis="z")
    cbox(hm, (CC[0], CC[1], CC[2] - 0.35), (1.5, 1.5, 0.5), "core")
    for a, L, w in ((0, 5.2, 1.4), (30, 3.5, 1.15), (62, 2.5, 1.0)):
        rr = spear(hm, CC, a, 1.15, L, w, 0.45, "plate", tilt=-16, tip="plate2")
        if a:
            mirror_x(hm, rr)
    ray(hm, (CC[0], CC[1], CC[2] - 0.12), 0, 1.4, 4.0, 0.3, 0.3, 1, 0.5, "glow_hot", tilt=-16)
    # 眉庇: 中央で下がる金の V
    br = rbox(hm, (-2.45, 29.4, -5.0), (4.9, 1.2, 1.1), "plate2", rot=(-14, 6, 8))
    mirror_x(hm, br)
    # 面頬: 白の V + 紅の吸気スリット、細い顎
    mg = rbox(hm, (-1.1, 25.75, -5.05), (2.3, 3.2, 0.7), "face", rot=(0, 30, 0))
    mv = stick(hm, mg, "north", 0.5, 0.22, (1.4, 0.5, 0.1), "grille", sink=0.05)
    mirror_x(hm, mg, mv)
    cbox(hm, (0, 25.9, -5.6), (0.5, 2.8, 0.5), "plate2")
    cbox(hm, (0, 25.7, -4.62), (7.6, 3.6, 0.5), "frame")
    rbox(hm, (0, 24.15, -4.8), (3.0, 0.9, 1.3), "plate", rot=(-30, 0, 0))
    ck = rbox(hm, (-3.45, 25.7, -3.75), (1.4, 3.8, 3.3), "plate", rot=(0, 34, -6))
    ckt = stick(hm, ck, "west", 0.08, 0.5, (0.35, 3.4, 0.2), "bronze", sink=0.05)
    ckc = stick(hm, ck, "west", 0.6, 0.35, (1.2, 1.2, 0.2), "crimson", sink=0.05)
    mirror_x(hm, ck, ckt, ckc)
    rbox(hm, (0, 24.0, 5.3), (8.8, 2.0, 0.9), "plate", rot=(18, 0, 0))     # しころ
    rbox(hm, (0, 22.7, 5.6), (8.2, 1.4, 0.8), "crimson_b", rot=(30, 0, 0))
    # バイザー（燃える V 字）
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 27.95, -4.8), (8.4, 1.9, 0.6), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 28.0, -5.1))
    half = rbox(fg, (-1.95, 27.95, -5.1), (3.9, 1.35, 0.35), "visor", rot=(0, 9, 11))
    mirror_x(fg, half)


# ---------------------------------------------------------------------------
#  コロナの光輪（頭の後ろ。金の機械の輪・金の刃の棘と炎の棘・逆回転の内の光の輪）
# ---------------------------------------------------------------------------
def halo(s):
    C = HALO_C
    hb = s.part("extra", "halo", "body", pivot=C)
    # 支え: 背嚢の上から首の後ろの輪の内側へ伸びる金の腕と、光輪を浮かせる小さな発振器
    beam(hb, (0, 23.4, 5.4), (0, 24.6, C[2] + 0.3), 1.0, 0.8, "plate2")
    octa(hb, (0, 24.6, C[2] + 0.5), 1.6, 0.6, "frame", axis="z")
    octa(hb, (0, 24.6, C[2] + 0.15), 0.9, 0.25, "glow_hot", axis="z")
    sp = s.fx("spin", "halo", hb, pivot=C)
    ring(sp, C, 6.3, 16, (0, 0.8, 0.6), "plate2", axis="z",
         styles=["plate2", "plate2", "plate2", "crimson"])
    for i in range(8):
        a = i * 45.0
        L = 4.6 if i % 2 == 0 else 3.4
        spear(sp, C, a, 6.4, L, 1.7 if i % 2 == 0 else 1.4, 0.5,
              "plate2" if i % 2 == 0 else "bronze")                           # 金の刃
        ray(sp, (C[0], C[1], C[2] + 0.05), a + 22.5, 6.4, 3.4, 1.6, 0.2, 2, 0.3, "corona")   # 炎
    si = s.fx("spin", "halo_in", hb, pivot=C)
    ring(si, (C[0], C[1], C[2] - 0.2), 5.6, 10, (0, 0.3, 0.3), "glow_hot", axis="z",
         styles=["glow_hot", "glow"])
