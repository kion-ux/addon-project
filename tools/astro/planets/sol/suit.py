# -*- coding: utf-8 -*-
"""太陽 — 恒星機装 ソル・オーバードライブ（Sol Overdrive Frame）。第 9 形態・最強の形（v1.1: 7 頭身）。

白金（plate）と金（plate2）の装甲、紅のインナー（六角メッシュ）と紅の差し板、全身を走る太陽の橙の発光線。
frame7 の暗い機械の骨格の上に、縁取りのある多層の装甲と「光条」「炎の舌」の尖った板を重ねる:
* 頭の後ろで回る、棘のあるコロナの光輪（金の槍の刃と炎の棘が交互・鋲と宝玉の付いた金の輪・
  逆回転する内の光の輪・背中の支柱と軸受け）
* 両肩から立つ紅炎（プロミネンス）のループと炎の舌（磁気コイルの根元）、背中の左右に双極の紅炎アーチ
* 胸の核融合炉（太陽の粒状斑の星核・金の八角の枠・紅の輪・回る閉じ込めの環・放射状の光条が脈打つ）
* 兜の白い日輪の前立て（七本の光条と額の小さな太陽）、燃えるような橙白の V 字のバイザー、耳の後ろへ流れる炎の羽根
* 胸・膝・腰の留め金・肩の外縁・篭手は光条（尖った先）の意匠。踵と背中に炎のスラスター

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A（7 頭身の目安）から取る。
右側だけ作り `_r` を付ける → 左は自動で鏡映。回転（統合版の rotation）: rx 正 = 上端が前へ /
ry 正 = 正面が右（-X）を向く（+X の端が前へ）/ rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。

この惑星だけの形の補助（ローカル）: ray（先細りの光条の板）/ spear（菱形の先の付いた光条）/
loop_pts（紅炎のループの弧の点列）/ rosette（小さな日輪: 八角の円盤 + 宝玉 + 短い光条）。
"""
from __future__ import annotations

import math

import numpy as np

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, joint_drum,  # noqa: F401
                        layered_plate, line_on, mat_cube, mirror_x, octa, piston, polyline,
                        rbox, ring, rivets, sensor, stick, taper, vents)
from hd_space import rot

GOLD_W = 0.26          # 縁取りの幅
LX = A.LEG_X           # 脚の軸 -2.15
HZ = A.HEAD_Z          # 頭の中心の奥行き

HALO_C = (0.0, 29.2, 6.2)       # コロナの光輪の中心（頭の後ろ）
REACTOR = (0.0, 23.0, -2.98)    # 胸の核融合炉の中心（面）

# ===========================================================================
#  塗り（astro_paint.suit_styles("sol") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate": {"line": (176, 120, 52)},
    "plate_b": {"line": (150, 100, 44)},
    "plate2": {"line": (130, 70, 18)},
    "plate2_b": {"line": (110, 56, 14)},
    "inner": {"base": (92, 20, 14), "glow": (255, 150, 40)},
    "crimson": {"kind": "armor", "base": (178, 40, 26), "light": (236, 104, 64),
                "dark": (112, 22, 14), "line": (64, 12, 8), "glow": (255, 172, 40)},
    "crimson_b": {"kind": "armor", "base": (128, 26, 16), "light": (190, 70, 44),
                  "dark": (80, 14, 8), "line": (48, 8, 6), "panel": 0, "glow": (255, 172, 40)},
    "bronze": {"kind": "trim", "base": (214, 132, 44), "light": (255, 214, 130),
               "dark": (132, 70, 20), "line": (70, 34, 10)},
    "rivet": {"kind": "trim", "base": (232, 200, 138), "light": (255, 246, 214),
              "dark": (150, 104, 52), "line": (80, 46, 18), "bevel": False},
    "visor": {"glow": (255, 196, 70), "light": (255, 255, 236), "deep": (226, 70, 18),
              "emit": 14},
    "glow": {"glow": (255, 166, 36), "light": (255, 246, 200)},
    "glow_hot": {"kind": "glowline", "glow": (255, 214, 120), "light": (255, 255, 240),
                 "bevel": False, "outline": False},
    "lamp": {"kind": "glowline", "glow": (255, 236, 170), "light": (255, 255, 246),
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
    "serial": {"text": "SOL-09", "under": {"kind": "armor", "base": (255, 214, 96), "panel": 0,
                                            "line": (130, 70, 18)},
               "ink": (150, 40, 20)},
    "hazard": {"c1": (255, 172, 40), "c2": (110, 22, 14)},
    "emblem": {"color": (255, 160, 40)},
    "face": {"kind": "armor", "base": (255, 240, 210), "panel": 0, "line": (150, 96, 50)},
    "grille": {"kind": "vent", "base": (120, 40, 24), "glow": (255, 150, 40), "deep": (120, 20, 8),
               "slat": 2},
    "gem": {"glow": (255, 120, 40), "deep": (150, 20, 10)},
}

# ===========================================================================
#  部位アニメ（Molang）。回るものは v.astro_spin（空中・疾走で速くなる累積の位相）に角速度を掛ける。
#  脈動・揺らぎは q.anim_time（12 秒ループ → 30°/秒の倍数）。重み（v.astro_air / v.astro_run）は振れ幅だけに掛ける。
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # コロナの光輪: 外の棘の輪はゆっくり、内の光の輪は逆向きに速く
        "fx_spin_halo": {"rotation": [0, 0, "v.astro_spin * 24.0"]},
        "fx_spin_halo_in": {"rotation": [0, 0, "-v.astro_spin * 72.0"]},
        # 胸の炉: 閉じ込めの環が回り、光が強く脈打つ
        "fx_spin_reactor": {"rotation": [0, 0, "v.astro_spin * 150.0"]},
        "fx_glow_reactor": {"scale": "1.0 + math.sin(q.anim_time * 180.0) * 0.08"},
        # 紅炎は揺らめく（肩・背中）
        "fx_glow_prom_r": {"scale": ["1.0", "1.0 + math.sin(q.anim_time * 360.0) * 0.07", "1.0"]},
        "fx_glow_arch_r": {"scale": ["1.0 + math.sin(q.anim_time * 300.0) * 0.04",
                                     "1.0 + math.sin(q.anim_time * 300.0) * 0.05", "1.0"]},
    },
    "thrust": {
        # 空中では内の光の輪が広がり、肩の紅炎が大きく燃え上がる
        "fx_spin_halo_in": {"scale": ["1.0 + v.astro_air * 0.12", "1.0 + v.astro_air * 0.12", "1.0"]},
        "fx_glow_prom_r": {"scale": ["1.0", "1.0 + v.astro_air * 0.22", "1.0"]},
    },
    "sprint": {
        # 疾走中は背中の紅炎が根元（磁気コイル）を軸に後ろへなびき、肩の紅炎も後ろへ傾く
        "fx_glow_arch_r": {"rotation": [0, "v.astro_run * 18.0", 0]},
        "fx_glow_prom_r": {"rotation": ["-v.astro_run * 10.0", 0, 0]},
    },
}


# ===========================================================================
#  形の補助（この惑星だけ）
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


def spear(bone, c, a, r0, L, w, depth, style, tilt=0.0, tip=None, yaw=0.0, **kw):
    """c から角度 a の向きに、半径 r0 から長さ L の先の尖った光条（槍の穂: 幅 w の板 + 45° の菱形の先）。"""
    T = rot(tilt, yaw, 0)
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


def rosette(bone, c, w, axis, facing, style="plate2", gem="core", rays=4, ray_style="bronze",
            ray_len=0.45, ray_w=0.3, a0=0.0):
    """小さな日輪の飾り: 八角の円盤（幅 w）+ 中央の宝玉 + 縁から放つ短い光条（rays 本）。
    axis は円盤の軸（"x" / "z"）、facing は外向きの符号（-1 / +1）。"""
    c = np.asarray(c, float)
    i = {"x": 0, "z": 2}[axis]
    e = np.zeros(3)
    e[i] = facing
    out = octa(bone, tuple(c), w, 0.3, style, axis=axis)
    gs = [w * 0.42] * 3
    gs[i] = 0.2
    out.append(cbox(bone, tuple(c + e * 0.18), gs, gem, rotation=(0, 0, 45) if axis == "z"
                    else (45, 0, 0)))
    for k in range(rays):
        a = a0 + k * 360.0 / rays
        if axis == "z":
            out += ray(bone, tuple(c + e * 0.02), a, w / 2 - 0.05, ray_len, ray_w, ray_w * 0.6, 1,
                       0.2, ray_style)
        else:
            out += ray(bone, tuple(c + e * 0.02), a, w / 2 - 0.05, ray_len, ray_w, ray_w * 0.6, 1,
                       0.2, ray_style, yaw=90)
    return out


# ===========================================================================
def build_suit(s: Suit):
    s.frame7(skip=("foot", "cables"))   # サバトンが足を包む / 背骨のケーブルは背嚢のホースに任せる
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    reactor(s)
    back(s)
    arches(s)
    arms(s)
    hands(s)
    shoulders(s)
    helmet(s)
    halo(s)


# ---------------------------------------------------------------------------
#  サバトン（足首から。尖ったつま先・紅の踵・踵の拍車と炎のスラスター・外くるぶしの日輪）
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (LX, 0.16, -1.1), (2.95, 0.32, 5.8), "dark")                           # 靴底
    shell = bevel(b, (LX, 1.05, -0.72), (2.9, 1.5, 4.05), "plate", cut=0.42, axis="z")
    st = stick(b, shell[0], "west", 0.5, 0.4, (3.3, 0.46, 0.16), "crimson", sink=0.05)
    line_on(b, st, "west", (0.04, 0.5), (0.96, 0.5), 0.18, 0.16, "glow")
    rivets(b, shell[0], "west", 2, edge="top", margin=0.28, span=(0.3, 0.7), style="rivet")
    # 甲（金）と、つま先の板が重なって尖る
    ins = rbox(b, (LX, 1.92, -1.95), (2.35, 0.5, 1.9), "plate2", rot=(-30, 0, 0))
    stick(b, ins, "up", 0.5, 0.62, (0.55, 0.55, 0.2), "gem", sink=0.05, spin=45)
    rivets(b, ins, "up", 2, edge="bottom", margin=0.28, span=(0.25, 0.75), style="rivet")
    rbox(b, (LX, 1.0, -3.1), (2.7, 0.95, 1.05), "plate", rot=(-16, 0, 0))
    rbox(b, (LX, 0.62, -3.98), (2.5, 0.7, 0.8), "plate2", rot=(-26, 0, 0))
    taper(b, (LX, 0.4, -4.3), (LX, 0.34, -4.95), 1.3, 0.6, 1, "plate", round_=False)
    cbox(b, (LX, 0.24, -4.38), (2.2, 0.36, 0.34), "bronze")                          # つま先の金具
    # 踵（紅）・拍車・噴射口
    cbox(b, (LX, 1.05, 1.22), (2.55, 1.5, 1.0), "crimson")
    taper(b, (LX, 1.5, 1.75), (LX, 1.2, 2.9), 0.7, 0.3, 1, "plate2", round_=False)
    octa(b, (LX, 0.6, 1.9), 1.15, 0.45, "frame", axis="z")
    cbox(b, (LX, 0.6, 2.16), (0.85, 0.85, 0.16), "thruster")
    fx = s.fx("thrust", "heel_r", b, pivot=(LX, 0.6, 2.2), rotation=(-58, 0, 0))
    taper(fx, (LX, 0.6, 2.2), (LX, -2.4, 2.2), 0.9, 0.24, 2, "flame")
    taper(fx, (LX, 0.6, 2.2), (LX, -0.9, 2.2), 0.46, 0.18, 1, "flame_core", round_=False)
    # 外くるぶしの日輪（足首のドラムの蓋の外）
    rosette(b, (LX - 1.68, 2.15, 0.3), 1.3, "x", -1, rays=0)


# ---------------------------------------------------------------------------
#  脚（腿・日輪の膝・脛）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前の白金の板（紅の上板・光条の発光線）・外の金の装甲（型番）・後ろの紅の板と排気口
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.7, -1.82), (2.85, 4.2, 0.55), "plate2", top="plate",
                       rot=(-3, 0, 0), inset=0.3, trim="bronze", trim_edge="bottom",
                       rivet="rivet", n_rivets=2, rivet_edge="top")
    ch_ = stick(t, fr["top"], "north", 0.72, 0.48, (0.44, 2.9, 0.16), "crimson", sink=0.06)
    line_on(t, ch_, "north", (0.5, 0.05), (0.5, 0.95), 0.18, 0.16, "glow")
    stick(t, fr["top"], "north", 0.3, 0.2, (0.62, 0.62, 0.16), "plate2", sink=0.06, spin=45)
    side = rbox(t, (LX - 1.78, 11.2, 0.05), (0.5, 3.0, 2.9), "plate2", rot=(0, 0, -3),
                decals={"west": {"decal": "serial", "text": "SOL-09", "ink": (150, 40, 20)}})
    rivets(t, side, "west", 3, edge="bottom", margin=0.28, style="rivet")
    hm = rbox(t, (LX, 11.5, 1.72), (2.3, 3.0, 0.4), "plate2_b", rot=(4, 0, 0))     # 腿の裏
    stick(t, hm, "south", 0.5, 0.55, (1.5, 2.1, 0.16), "plate", sink=0.06)
    # 膝: 尖った白金の膝当て（日輪の宝玉・三本の金の光条）と外の油圧シリンダー
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    kg = bevel(k, (LX, 8.45, -1.88), (2.3, 2.3, 0.8), "plate", cut=0.38, axis="z")
    rbox(k, (LX, 7.25, -1.9), (1.2, 1.2, 0.6), "crimson", rot=(0, 0, 45))          # 下の尖り
    octa(k, (LX, 8.45, -2.3), 1.2, 0.26, "bronze", axis="z")
    rbox(k, (LX, 8.45, -2.42), (0.62, 0.62, 0.2), "core", rot=(0, 0, 45))
    for a, L in ((-40, 1.0), (0, 1.45), (40, 1.0)):
        ray(k, (LX, 8.45, -2.36), a, 0.6, L, 0.52, 0.28, 1, 0.26, "plate2", tilt=-6)
    rivets(k, kg[0], "north", 2, edge="bottom", margin=0.32, span=(0.15, 0.85), style="rivet")
    piston(k, (LX - 1.62, 10.9, 0.55), (LX - 1.5, 6.3, 0.45), r=0.27, style="frame",
           rod_style="chrome", cap_style="dark")
    # 脛: 金の前板 + 白金の V の稜 + 紅の帯の発光線、両脇の板、ふくらはぎの排気口、外の炎の舌のヒレ
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 4.75, -1.42), (2.75, 5.1, 0.55), "plate2", rot=(4, 0, 0))
    keel = rbox(g, (LX - 0.36, 4.95, -1.76), (0.78, 4.2, 0.48), "plate", rot=(4, 24, 0))
    mirror_x(g, keel, about=LX)
    for a_ in (0.1, 0.9):
        cs = stick(g, front, "north", a_, 0.5, (0.42, 3.8, 0.16), "crimson", sink=0.06)
        line_on(g, cs, "north", (0.5, 0.06), (0.5, 0.94), 0.18, 0.16, "glow")
    sd = rbox(g, (LX - 1.45, 4.85, -0.15), (0.45, 4.9, 2.7), "plate", rot=(0, 0, -4))
    rivets(g, sd, "west", 2, edge="bottom", margin=0.32, span=(0.25, 0.75), style="rivet")
    calf = rbox(g, (LX, 6.15, 1.62), (2.3, 2.5, 0.45), "crimson", rot=(-12, 0, 0))
    vents(g, calf, "south", 2, box=(0.29, 0.25, 0.71, 0.75), w=0.24)
    fin = rbox(g, (LX - 1.86, 5.4, 0.75), (0.38, 3.1, 2.0), "plate2", rot=(-10, 0, -8))
    fi = stick(g, fin, "west", 0.45, 0.5, (1.1, 2.4, 0.16), "crimson", sink=0.05)
    line_on(g, fi, "west", (0.2, 0.12), (0.75, 0.88), 0.18, 0.16, "glow")
    taper(g, (LX - 1.95, 6.85, 1.3), (LX - 2.3, 8.9, 2.1), 0.85, 0.24, 2, "plate2",
          round_=False)                                                              # 炎の舌の先


# ---------------------------------------------------------------------------
#  腰（ベルト・日輪の留め金・炎の舌の前垂れ・腰の脇の板・草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    chamfer(w, (0, 16.95, 0.12), (6.7, 0.95, 4.5), "frame", cut=0.4, axis="y")
    # 日輪の留め金: 金の八角 + 小さな太陽 + 放射の光条
    octa(w, (0, 16.95, -2.4), 1.9, 0.4, "plate2", axis="z")
    rbox(w, (0, 16.95, -2.66), (0.85, 0.85, 0.24), "core", rot=(0, 0, 45))
    for a in (45, 135, 225, 315):
        ray(w, (0, 16.95, -2.62), a, 0.9, 0.55, 0.32, 0.18, 1, 0.2, "bronze")
    bl = rivets(w, w.cubes[0], "north", 2, edge="bottom", margin=0.44, span=(0.1, 0.26),
                style="rivet")
    mirror_x(w, bl)
    # 前垂れ（紅の細い板 + 下へ尖る金の炎の舌）。腿の前を隠さない幅
    fp = rbox(w, (0, 15.35, -2.08), (1.8, 2.2, 0.48), "crimson", rot=(-8, 0, 0))
    line_on(w, fp, "north", (0.5, 0.15), (0.5, 0.88), 0.2, 0.16, "glow")
    stick(w, fp, "north", 0.5, 0.95, (1.7, GOLD_W, 0.18), "bronze", sink=0.05)
    spear(w, (0, 14.4, -2.25), 180, 0.0, 1.15, 1.2, 0.42, "plate2", tilt=-8, tip="plate2")
    # 腰の脇の白金の板（股関節の前を覆う）
    hp = rbox(w, (-2.35, 15.75, -2.0), (2.1, 1.5, 0.45), "plate", rot=(-8, 14, 4))
    hpr = rivets(w, hp, "north", 1, edge="top", margin=0.3, style="rivet")
    mirror_x(w, hp, hpr)
    # 後ろ垂れ（白金 + 下へ尖る紅の炎の舌）
    rs = rbox(w, (0, 15.1, 2.45), (4.4, 2.5, 0.5), "plate", rot=(14, 0, 0))
    cbox(w, (0, 14.15, 2.82), (3.0, 0.4, 0.3), "hazard")
    rivets(w, rs, "south", 3, edge="top", margin=0.3, span=(0.2, 0.8), style="rivet")
    spear(w, (0, 13.95, 2.72), 180, 0.0, 1.0, 1.3, 0.4, "crimson", tilt=14, tip="crimson")
    # 草摺（腰の横。付け根で外へ開く。金の下板 + 紅の上板 + 縁 + 発光線 + 下縁の尖り）
    # 腿の外の装甲（y 12.7 まで）の上で終わり、篭手の内側（x -4.5）より内に収める
    ts = s.part("waist", "tasset_r", w, pivot=(-3.35, 16.6, 0.0), rotation=(0, 0, 8))
    base = layered_plate(ts, (-3.62, 15.2, 0.0), (0.45, 2.7, 3.5), "plate2", top="crimson",
                         face="west", inset=0.36, trim="bronze", trim_edge="bottom",
                         rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(ts, base["top"], "west", (0.12, 0.45), (0.88, 0.45), 0.2, 0.16, "glow")
    for zz in (-0.75, 0.75):
        rbox(ts, (-3.66, 13.92, zz), (0.36, 0.5, 0.5), "plate2", rot=(45, 0, 0))     # 下縁の尖り


# ---------------------------------------------------------------------------
#  胴（胸郭・白金の胸板・紅の肋・光条・襟・脇の排気口・腹の板）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.25, 0.0), (9.3, 3.4, 5.0), "plate", cut=0.8, axis="y")     # 上が広い
    chamfer(c, (0, 21.65, -0.05), (7.2, 2.3, 4.6), "plate_b", cut=0.7, axis="y")
    sl = rbox(c, (-3.9, 22.15, 0.0), (0.5, 2.9, 4.0), "plate", rot=(0, 0, -24))     # 脇の斜面
    mirror_x(c, sl)
    # 白金の胸板（炉の上で外へ開く V）: 金の上縁・リベット、紅の差し板に発光の光条
    pec = rbox(c, (-2.75, 24.45, -2.62), (3.4, 2.35, 0.55), "plate", rot=(6, 17, 11))
    pt = stick(c, pec, "north", 0.5, 0.95, (3.3, GOLD_W, 0.18), "plate2", sink=0.05)
    pin = stick(c, pec, "north", 0.42, 0.45, (2.2, 0.9, 0.16), "crimson", sink=0.06)
    pg = line_on(c, pin, "north", (0.06, 0.5), (0.94, 0.5), 0.18, 0.16, "glow")
    pr = rivets(c, pec, "north", 2, edge="bottom", margin=0.22, span=(0.3, 0.8), style="rivet")
    # 炉の下で中央へ絞る紅の肋（下縁に金）
    low = rbox(c, (-2.0, 21.8, -2.4), (3.2, 1.45, 0.5), "crimson", rot=(-8, 12, 14))
    lt = stick(c, low, "north", 0.5, 0.08, (3.0, GOLD_W, 0.16), "bronze", sink=0.05)
    lg = line_on(c, low, "north", (0.12, 0.62), (0.82, 0.5), 0.18, 0.16, "glow")
    mirror_x(c, pec, pt, pin, pg, pr, low, lt, lg)
    # 襟（首の両脇に立ち上がる金の板 + 白金の上板 + 縁）と喉の小さな板
    col = rbox(c, (-1.75, 26.25, 0.35), (1.45, 1.1, 3.6), "plate2", rot=(0, 0, -24))
    colt = stick(c, col, "up", 0.5, 0.5, (1.1, 3.3, 0.2), "plate", sink=0.06)
    cf = rbox(c, (-0.95, 25.95, -1.95), (1.6, 0.9, 0.45), "plate", rot=(-20, 30, -10))
    mirror_x(c, col, colt, cf)
    sensor(c, (-1.4, 25.25, -2.62), 0.26, "lamp", "dark")
    sensor(c, (1.4, 25.25, -2.62), 0.26, "lamp", "dark")
    # 肩の付け根（肩当ての下）と脇の排気口
    yk = rbox(c, (-3.95, 25.95, 0.0), (2.0, 0.55, 3.5), "plate_b", rot=(0, 0, -8))
    sv = cbox(c, (-4.4, 23.7, 0.35), (0.4, 2.0, 2.4), "plate2")
    svv = vents(c, sv, "west", 3, box=(0.3, 0.2, 0.7, 0.8))
    mirror_x(c, yk, sv, svv)
    rivets(c, up[1], "south", 6, edge="top", margin=0.35, span=(0.1, 0.9), style="rivet")
    # 腹: 下ほど細い三枚の板（金・白金・金）と中央の溝、脇の紅の板
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))
    for i, (y, ww, st) in enumerate(((19.95, 4.0, "plate2"), (18.95, 3.6, "plate"),
                                     (17.95, 3.2, "plate2"))):
        p = rbox(ab, (0, y, -1.98 + i * 0.05), (ww, 0.82, 0.48), st, rot=(-8, 0, 0))
        stick(ab, p, "north", 0.5, 0.5, (0.2, 0.62, 0.16), "crimson", sink=0.08)
        if i == 1:
            r_ = rivets(ab, p, "north", 1, line=((0.12, 0.5), (0.12, 0.5)), size=0.22,
                        style="rivet")
            mirror_x(ab, r_)
    ob = rbox(ab, (-2.05, 19.0, -1.55), (0.5, 2.6, 0.9), "crimson", rot=(0, 30, -6))
    obg = line_on(ab, ob, "north", (0.5, 0.1), (0.5, 0.9), 0.16, 0.16, "glow")
    mirror_x(ab, ob, obg)
    cbox(ab, (0, 18.9, 2.08), (2.2, 2.6, 0.45), "plate_b")                          # 背の腰板


# ---------------------------------------------------------------------------
#  核融合炉（胸の中央。黒い菱形の台 → 金の八角の枠 → 紅の輪 → 太陽（脈打つ）→ 回る閉じ込めの環 → 光条）
# ---------------------------------------------------------------------------
def reactor(s):
    X, Y, Z = REACTOR
    c = s.part("torso", "reactor", "body", pivot=(X, Y, Z))
    rbox(c, (X, Y, Z + 0.42), (2.75, 2.75, 0.5), "dark", rot=(0, 0, 45))
    octa(c, (X, Y, Z + 0.12), 2.75, 0.36, "plate2", axis="z")
    octa(c, (X, Y, Z - 0.02), 2.2, 0.3, "crimson_b", axis="z")
    for k in range(4):                                                              # 枠のボルト
        a = math.radians(k * 90 + 45)
        cbox(c, (X - 1.18 * math.sin(a), Y + 1.18 * math.cos(a), Z - 0.1), (0.24, 0.24, 0.16),
             "rivet")
    # 炉から胸へ放つ光条（金の長い 4 本 + 発光の短い 4 本）
    for a, L, st in ((0, 1.25, "plate2"), (90, 1.05, "plate2"), (180, 0.9, "plate2"),
                     (270, 1.05, "plate2")):
        spear(c, (X, Y, Z + 0.16), a, 1.42, L, 0.5, 0.26, st, tip="bronze")
    for a in (45, 135, 225, 315):
        ray(c, (X, Y, Z + 0.06), a, 1.4, 0.75, 0.32, 0.16, 1, 0.22, "glow_hot")
    gl = s.fx("glow", "reactor", c, pivot=(X, Y, Z - 0.2))
    cbox(gl, (X, Y, Z - 0.2), (1.5, 1.5, 0.6), "core")
    rbox(gl, (X, Y, Z - 0.22), (1.35, 1.35, 0.56), "core", rot=(0, 0, 45))
    sp = s.fx("spin", "reactor", c, pivot=(X, Y, Z - 0.5))
    ring(sp, (X, Y, Z - 0.52), 1.12, 8, (0, 0.22, 0.24), "glow_hot", axis="z",
         styles=["glow_hot", "bronze"])


# ---------------------------------------------------------------------------
#  背中（炉の背嚢・背の日輪・排気スリット・推進剤タンク・双発スラスター・ホース・光輪の支柱）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    pk = bevel(bk, (0, 22.1, 3.5), (4.4, 5.4, 2.0), "plate", cut=0.6, axis="z")
    lid = rbox(bk, (0, 25.05, 3.2), (3.9, 0.8, 2.0), "plate2", rot=(20, 0, 0))     # 上の蓋
    rivets(bk, lid, "up", 2, edge="bottom", margin=0.28, span=(0.3, 0.7), style="rivet")
    rosette(bk, (0, 23.15, 4.62), 2.1, "z", 1, rays=4, ray_len=0.42, ray_w=0.3, a0=45)
    vents(bk, pk[0], "south", 3, box=(0.35, 0.12, 0.65, 0.36))
    cbox(bk, (0, 19.55, 4.52), (2.6, 0.4, 0.2), "hazard")
    rivets(bk, pk[0], "south", 8, edge="border", margin=0.26, style="rivet")
    # 脇の推進剤タンク（紅の八角の筒 + 蓋 + 金の帯）
    tk = octa(bk, (-2.4, 21.5, 3.75), 1.0, 3.0, "crimson", axis="y")
    tk.append(cbox(bk, (-2.4, 23.1, 3.75), (0.7, 0.3, 0.7), "frame"))
    tk.append(cbox(bk, (-2.4, 21.5, 3.75), (0.72, 0.3, 1.12), "plate2"))
    tk.append(cbox(bk, (-2.4, 20.6, 3.75), (0.72, 0.3, 1.12), "plate2"))
    mirror_x(bk, tk)
    hs = cable(bk, [(-1.6, 19.5, 3.6), (-2.85, 17.4, 2.45)], 0.3, "dark", sag=0.35,
               rib="bronze", rib_every=2)
    mirror_x(bk, hs)
    # 光輪の支柱（背嚢の上から後ろ上へ。光輪の軸受けへ）
    beam(bk, (0, 25.2, 3.6), (0, 27.6, 6.85), 0.7, 0.55, "plate2")
    beam(bk, (0, 25.0, 3.4), (0, 27.4, 6.6), 0.36, 0.3, "frame", roll=0)
    # スラスター（右。下後ろへ向ける）: 胴・金の帯・紅のベル・光る縁の輪・噴射口・炎
    th = s.part("back", "thruster_r", bk, pivot=(-1.45, 20.4, 4.4), rotation=(18, 0, -8))
    octa(th, (-1.45, 19.4, 4.4), 1.6, 2.0, "plate", axis="y")
    octa(th, (-1.45, 20.15, 4.4), 1.8, 0.3, "plate2", axis="y")
    octa(th, (-1.45, 17.95, 4.4), 2.1, 1.0, "crimson_b", axis="y")
    ring(th, (-1.45, 17.48, 4.4), 0.84, 6, (0.95, 0.22, 0.22), "glow", axis="y", phase=30)
    cbox(th, (-1.45, 17.46, 4.4), (1.45, 0.16, 1.45), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.45, 17.4, 4.4))
    taper(fx, (-1.45, 17.4, 4.4), (-1.45, 11.0, 4.4), 1.7, 0.36, 3, "flame")
    taper(fx, (-1.45, 17.35, 4.4), (-1.45, 13.9, 4.4), 0.8, 0.22, 2, "flame_core", round_=False)


def arches(s):
    """背中の左右の双極の紅炎アーチ: 肩甲骨の金の磁気コイルから外へ膨らみ、腰の上のコイルへ戻る弧と炎の舌。"""
    bk = s.bone("back_pack")
    ar = s.part("back", "arch_r", bk, pivot=(-2.7, 21.0, 3.6))
    PA, PB = (-2.75, 24.2, 3.55), (-2.95, 17.9, 3.1)
    for p in (PA, PB):                                                              # 根元の磁気コイル
        octa(ar, (p[0] - 0.3, p[1], p[2]), 1.15, 0.7, "plate2", axis="x")
        cbox(ar, (p[0] - 0.72, p[1], p[2]), (0.24, 0.62, 0.62), "glow_hot", rotation=(45, 0, 0))
    fa = s.fx("glow", "arch_r", ar, pivot=(-3.2, 21.0, 3.5))
    pts = loop_pts((PA[0] - 0.8, PA[1], PA[2]), (PB[0] - 0.8, PB[1], PB[2]), 0.0,
                   out=(-3.9, 0.0, 2.1), n=5)
    polyline(fa, pts, 0.7, 0.7, "plasma")
    polyline(fa, [(q[0] + 0.1, q[1], q[2] + 0.04) for q in pts], 0.32, 1.0, "prom_core")
    for k, (a, L) in zip((2, 3), ((-62, 2.6), (-108, 2.6))):
        ray(fa, pts[k], a, 0.25, L, 1.1, 0.26, 3, 0.4, "prom", yaw=-30)


# ---------------------------------------------------------------------------
#  腕（二の腕・肘・篭手）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.32, 21.35, 0.0), (0.45, 3.2, 2.5), "plate2", rot=(0, 0, 3))
    oi = stick(ua, op, "west", 0.5, 0.5, (1.0, 2.5, 0.16), "crimson", sink=0.05)
    line_on(ua, oi, "west", (0.5, 0.08), (0.5, 0.92), 0.18, 0.16, "glow")
    rivets(ua, op, "west", 2, edge="bottom", margin=0.22, span=(0.2, 0.8), style="rivet")
    upf = rbox(ua, (X + 0.05, 21.4, -1.38), (2.2, 2.9, 0.42), "plate", rot=(-3, 0, 0))
    stick(ua, upf, "north", 0.5, 0.78, (0.6, 0.6, 0.16), "plate2", sink=0.06, spin=45)
    sensor(ua, (X + 0.05, 22.55, -1.66), 0.22, "lamp", "dark")
    octa(ua, (X, 19.72, 0.02), 2.86, 0.32, "plate2", axis="y")                    # 腕輪
    # 肘当て（紅）と後ろへ尖る金の棘
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    cop = bevel(el, (A.ELBOW[0], 18.55, 1.62), (2.1, 1.9, 0.6), "crimson", cut=0.3, axis="z")
    rivets(el, cop[0], "south", 2, edge="bottom", margin=0.3, span=(0.25, 0.75), style="rivet")
    taper(el, (A.ELBOW[0], 18.4, 1.95), (A.ELBOW[0], 19.4, 3.0), 0.75, 0.3, 1, "plate2",
          round_=False)
    # 篭手: 手首へ向かって開く白金 + 外の金の板（紅の差し板・発光線）+ 上外へ尖る光条のヒレ
    #        + 前の金の板 + 金の袖口 + 外の小さなピストン
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX_ = A.FOREARM_X
    chamfer(fa, (FX_, 17.15, 0.0), (2.85, 1.9, 2.95), "plate", cut=0.45, axis="y")
    chamfer(fa, (FX_ - 0.04, 15.7, 0.0), (3.0, 1.75, 3.15), "plate", cut=0.48, axis="y")
    ob = rbox(fa, (FX_ - 1.68, 16.3, 0.0), (0.42, 3.1, 2.6), "plate2", rot=(0, 0, 5))
    obi = stick(fa, ob, "west", 0.5, 0.5, (1.5, 2.5, 0.16), "crimson", sink=0.05)
    line_on(fa, obi, "west", (0.15, 0.15), (0.5, 0.85), 0.18, 0.16, "glow")
    line_on(fa, obi, "west", (0.5, 0.85), (0.85, 0.15), 0.18, 0.16, "glow")
    rivets(fa, ob, "west", 3, edge="top", margin=0.24, style="rivet")
    ray(fa, (FX_ - 1.95, 17.0, 0.35), -32, 0.0, 1.9, 0.9, 0.3, 2, 0.3, "plate2", yaw=-6)
    fv = rbox(fa, (FX_ - 0.02, 16.45, -1.62), (2.0, 2.2, 0.35), "plate2", rot=(-5, 0, 0))
    fvb = stick(fa, fv, "north", 0.5, 0.5, (1.3, 1.7, 0.18), "crimson", sink=0.06)
    line_on(fa, fvb, "north", (0.5, 0.1), (0.5, 0.9), 0.16, 0.16, "glow")
    rivets(fa, fv, "north", 2, edge="bottom", margin=0.18, span=(0.12, 0.88), size=0.2,
           style="rivet")
    chamfer(fa, (FX_ - 0.04, 14.72, 0.0), (3.06, 0.34, 3.2), "plate2", cut=0.4, axis="y")  # 袖口
    sensor(fa, (FX_ + 0.05, 15.5, 1.68), 0.26, "lamp", "dark", facing=1)
    cable(fa, [(FX_ + 0.9, 17.9, 1.5), (FX_ + 1.15, 16.3, 1.62), (FX_ + 0.95, 14.9, 1.45)],
          0.26, "dark", seg=0.8)


def hands(s):
    """手の甲の金の板と小さな太陽、指の甲当て（4 本の基節）、親指の当て。指そのものは frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.42, 13.62, 0.0), (0.36, 1.7, 2.3), "plate2", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.55, (0.62, 0.62, 0.2), "core", sink=0.05, spin=45)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        n = (-0.81, -0.58, 0.0)
        o = 0.34
        beam(h, (p0[0] + n[0] * o, p0[1] + n[1] * o, zf), (p1[0] + n[0] * o, p1[1] + n[1] * o, zf),
             0.56, 0.22, "plate")
    rbox(h, (-5.62, 13.55, -1.72), (0.62, 0.9, 0.22), "plate2", rot=(0, 0, -36))


# ---------------------------------------------------------------------------
#  肩（重ねた日輪の肩当て・外縁の光条・紅炎のループ）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    dome = bevel(p, (-7.2, 25.65, 0.0), (3.8, 2.4, 4.8), "plate", cut=0.75, axis="x",
                 rot=(0, 0, -14))
    top = stick(p, dome[0], "up", 0.45, 0.5, (2.4, 3.7, 0.3), "plate2", sink=0.1)
    rdg = stick(p, top, "up", 0.55, 0.5, (0.55, 3.9, 0.3), "crimson", sink=0.08)       # 中央の稜
    line_on(p, rdg, "up", (0.5, 0.08), (0.5, 0.92), 0.18, 0.16, "glow")
    rivets(p, top, "up", 4, edge="border", margin=0.25, size=0.24, style="rivet")
    # 外の縁: 上・外へ反り返る金の板（上端に白金）→ 肩の線を広く見せる
    rim = rbox(p, (-9.12, 25.35, 0.0), (0.45, 1.9, 4.9), "plate2", rot=(0, 0, -30))
    stick(p, rim, "up", 0.5, 0.5, (0.45, 4.9, 0.2), "plate", sink=0.05)
    rivets(p, rim, "west", 3, edge="bottom", margin=0.3, size=0.22, style="rivet")
    # 外へ開いて垂れる板（白金・紅）と金の縁、紋章、リベットの列
    l1 = rbox(p, (-8.62, 23.6, 0.0), (0.55, 2.3, 4.6), "plate", rot=(0, 0, 15),
              decals={"west": {"decal": "emblem", "color": (255, 150, 40)}})
    stick(p, l1, "west", 0.5, 0.06, (4.4, GOLD_W, 0.18), "plate2", sink=0.05)
    rivets(p, l1, "west", 4, edge="top", margin=0.24, size=0.22, style="rivet")
    l2 = rbox(p, (-8.8, 21.9, 0.05), (0.48, 1.55, 4.0), "crimson", rot=(0, 0, 11))
    stick(p, l2, "west", 0.5, 0.08, (3.7, GOLD_W, 0.18), "bronze", sink=0.05)
    line_on(p, l2, "west", (0.1, 0.55), (0.9, 0.55), 0.16, 0.16, "glow")
    # 前後の小さな板とセンサー、後ろのヒレ
    fr = rbox(p, (-7.25, 24.45, -2.45), (2.6, 1.3, 0.4), "plate_b", rot=(-12, 0, 0))
    sensor(p, (-7.6, 24.45, -2.7), 0.26, "lamp", "dark")
    rivets(p, fr, "north", 2, edge="bottom", margin=0.22, span=(0.2, 0.45), style="rivet")
    # 紅炎のループ（肩当ての上、前から後ろへ外へ膨らむ弧）と、弧の上の炎の舌
    PA, PB = (-6.75, 26.45, -1.75), (-8.15, 26.2, 1.85)
    for q in (PA, PB):                                                              # 磁気コイル
        octa(p, q, 0.95, 0.6, "frame", axis="y")
        cbox(p, (q[0], q[1] + 0.38, q[2]), (0.6, 0.24, 0.6), "glow_hot", rotation=(0, 45, 0))
    fp = s.fx("glow", "prom_r", p, pivot=(-7.45, 26.6, 0.0))
    pts = loop_pts((PA[0], PA[1] + 0.35, PA[2]), (PB[0], PB[1] + 0.35, PB[2]), 2.9,
                   out=(-0.9, 0.0, 0.0), n=5)
    polyline(fp, pts, 0.62, 0.62, "plasma")
    polyline(fp, [(q[0], q[1] + 0.08, q[2]) for q in pts], 0.82, 0.26, "prom_core")
    for k, a, L, n in ((1, -22, 1.5, 2), (2, -4, 2.2, 3), (4, 22, 1.4, 2)):
        ray(fp, pts[k], a, 0.15, L, 1.0, 0.24, n, 0.36, "prom", yaw=30)


# ---------------------------------------------------------------------------
#  兜（ドーム・額・眉・面頬・顎・頬当て・耳・後頭部・しころ）・白い日輪の前立て・炎の羽根・V 字のバイザー
# ---------------------------------------------------------------------------
def helmet(s):
    hz = HZ
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.65, hz + 0.3), (4.5, 1.7, 4.9), "plate", cut=0.6, axis="z")
    chamfer(hm, (0, 31.62, hz + 0.45), (3.5, 0.9, 4.4), "plate", cut=0.32, axis="z")  # 冠
    cbox(hm, (0, 32.0, hz + 0.5), (0.8, 0.34, 3.9), "plate2")                       # 中央の稜
    rbox(hm, (0, 30.7, hz - 2.2), (4.2, 1.3, 0.5), "plate", rot=(-22, 0, 0))       # 額の斜面
    br = rbox(hm, (-1.05, 30.05, hz - 2.42), (2.1, 0.5, 0.5), "plate2", rot=(-8, 8, 12))
    sd = cbox(hm, (-2.12, 28.95, hz + 0.65), (0.42, 2.2, 3.5), "plate2")            # こめかみ
    sdr = rivets(hm, sd, "west", 1, edge="top", margin=0.3, size=0.22, style="rivet")
    ck = rbox(hm, (-1.78, 28.4, hz - 1.15), (0.5, 2.0, 2.3), "plate", rot=(0, 20, -10))  # 頬当て
    ckg = stick(hm, ck, "west", 0.06, 0.5, (0.22, 1.8, 0.16), "bronze", sink=0.05)
    ear = octa(hm, (-2.36, 29.15, hz + 0.65), 1.4, 0.34, "bronze", axis="x")       # 耳
    eg = cbox(hm, (-2.55, 29.15, hz + 0.65), (0.16, 0.62, 0.62), "core")
    mirror_x(hm, br, sd, sdr, ck, ckg, ear, eg)
    # 面頬（白）: 中央の稜へ折れた V の板、紅の吸気口、尖った顎
    fc = rbox(hm, (-0.62, 28.45, hz - 2.2), (1.3, 1.25, 0.42), "face", rot=(8, 26, 0))
    fg_ = stick(hm, fc, "north", 0.45, 0.3, (0.8, 0.36, 0.16), "grille", sink=0.05)
    ch = rbox(hm, (-0.45, 27.75, hz - 1.98), (1.0, 0.7, 0.48), "face", rot=(0, 26, -22))
    mirror_x(hm, fc, fg_, ch)
    cbox(hm, (0, 28.5, hz - 2.5), (0.3, 1.2, 0.3), "plate2")
    # 後頭部（中央の稜が後ろへ降りる・小さな排気口）としころ
    bh = cbox(hm, (0, 29.1, hz + 2.6), (4.0, 2.4, 0.45), "plate")
    vents(hm, bh, "south", 2, box=(0.38, 0.25, 0.62, 0.65), w=0.2)
    rbox(hm, (0, 28.05, hz + 2.62), (3.7, 0.75, 0.45), "plate2", rot=(22, 0, 0))
    rbox(hm, (0, 27.55, hz + 2.75), (3.2, 0.62, 0.42), "crimson", rot=(32, 0, 0))
    # 白い日輪の前立て（飾り）: 額の小さな太陽 + 七本の光条（長短交互・少し後ろへ倒す）
    CC = (0.0, 30.55, hz - 2.62)
    cr = s.part("helmet", "crest", "head", pivot=CC, ornament=True)
    octa(cr, CC, 1.25, 0.36, "plate2", axis="z")
    rbox(cr, (CC[0], CC[1], CC[2] - 0.22), (0.72, 0.72, 0.3), "core", rot=(0, 0, 45))
    for a, L, w in ((0, 3.4, 0.62), (26, 2.6, 0.52), (56, 1.9, 0.46)):
        rr = spear(cr, CC, a, 0.6, L, w, 0.3, "plate", tilt=-20, tip="plate2")
        if a:
            mirror_x(cr, rr)
    ray(cr, (CC[0], CC[1], CC[2] - 0.1), 0, 0.7, 2.4, 0.2, 0.16, 1, 0.34, "glow_hot", tilt=-20)
    # 耳の後ろへ流れる炎の羽根（金の刃 2 枚 + 紅の芯。飾り）
    pl = s.part("helmet", "plume_r", "head", pivot=(-2.45, 29.4, hz + 0.9), ornament=True)
    ray(pl, (-2.5, 29.55, hz + 1.0), 62, 0.0, 2.6, 0.8, 0.22, 2, 0.24, "plate2", yaw=-90)
    ray(pl, (-2.48, 29.1, hz + 1.0), 82, 0.0, 2.0, 0.6, 0.2, 2, 0.22, "crimson", yaw=-90)
    # バイザー: 暗い帯の上に、吊り上がった V 字の二つの目（橙白に燃える）と眉間の灯り
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 29.5, hz - 2.3), (3.7, 0.72, 0.3), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.5, hz - 2.48))
    eye = rbox(fg, (-0.92, 29.5, hz - 2.48), (1.4, 0.34, 0.18), "visor", rot=(0, 8, 14))
    mirror_x(fg, eye)
    rbox(fg, (0, 29.32, hz - 2.5), (0.3, 0.3, 0.16), "visor", rot=(0, 0, 45))


# ---------------------------------------------------------------------------
#  コロナの光輪（頭の後ろ。軸受け・金の輪の鋲と宝玉・金の槍の刃と炎の棘・逆回転の内の光の輪）
# ---------------------------------------------------------------------------
def halo(s):
    C = HALO_C
    hb = s.part("extra", "halo", "body", pivot=C)
    # 軸受け（支柱の先。光輪の後ろ）
    octa(hb, (0, 27.95, C[2] + 0.75), 1.3, 0.55, "frame", axis="z")
    octa(hb, (0, 27.95, C[2] + 1.08), 0.8, 0.26, "glow_hot", axis="z")
    sp = s.fx("spin", "halo", hb, pivot=C)
    ring(sp, C, 4.4, 16, (0, 0.55, 0.5), "plate2", axis="z",
         styles=["plate2", "plate2", "plate2", "crimson"])
    for k in range(8):                                                              # 輪の鋲
        a = math.radians(k * 45 + 22.5)
        dz, st = ((-0.3, "rivet"), (0.3, "bronze"))[k % 2]
        cbox(sp, (C[0] - 4.4 * math.sin(a), C[1] + 4.4 * math.cos(a), C[2] + dz),
             (0.26, 0.26, 0.16), st)
    for i in range(8):
        a = i * 45.0
        long_ = i % 2 == 0
        L = 4.0 if long_ else 3.0
        w = 1.35 if long_ else 1.1
        spear(sp, C, a, 4.75, L, w, 0.42, "plate2" if long_ else "bronze", tip="plate")   # 金の刃
        if long_:
            ray(sp, (C[0], C[1], C[2] - 0.2), a, 5.0, L * 0.62, 0.22, 0.16, 1, 0.16, "crimson")
        R = rot(0, 0, a)
        u = R @ np.array([0.0, 1.0, 0.0])
        mat_cube(sp, np.asarray(C) + u * 4.75 + np.array([0, 0, -0.32]), (0.42, 0.42, 0.2), "gem",
                 R @ rot(0, 0, 45))
        ray(sp, (C[0], C[1], C[2] + 0.05), a + 22.5, 4.7, 2.8, 1.15, 0.3, 2, 0.24, "corona")  # 炎
    si = s.fx("spin", "halo_in", hb, pivot=C)
    ring(si, (C[0], C[1], C[2] - 0.15), 3.72, 16, (0.99, 0.3, 0.3), "glow_hot", axis="z",
         styles=["glow_hot", "glow"])
