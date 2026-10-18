# -*- coding: utf-8 -*-
"""海王星 — 深淵機装 トリトン（Triton Frame）。深海の騎士。

紺碧（plate）と藍（plate2）の装甲。藍を主に、紺碧は重ねた上板と鱗に。白い波頭のヒレ（fin）を
前腕・脛・兜に立て、縁取りは金ではなく真珠色の銀（pearl）。生物発光のような水色の線（glow）。

  兜     藍のドーム・額の三叉の冠（三本の返しの付いた穂先）・頭頂から後ろへ流れる高い背ビレの鶏冠・
         左右の耳ビレ・鋭く吊り上がった二つの目のバイザー・鰓（えら）のスリットの面頬
  胴     中央の竜骨に暗斑の海王星の星核（逆回りに回る嵐の羽根 fx_spin_storm）・左右に三枚重ねの
         鰓の胸板（間から水色の光）・腹は菱形の鱗を重ねた鱗鎧
  背中   ヒレの形の双発スラスター（肩の後ろから外上へ反る白い背ビレ + 下向きのノズル）・
         背骨の小さな背ビレ・中央の水流タービン（羽根が回る fx_spin_turbine）
  腰     鱗を重ねた草摺・三叉の紋の留め金・後ろへ垂れる二股の尾ビレのマント（波頭の泡の縁）
  腕     藍の上腕・真珠の腕章・前腕の外へ反る白いヒレ・鱗の篭手
  脚     鱗の脛当て・外へ反る脛のヒレ・貝殻の膝当て・尖ったつま先

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。右側だけ作り `_r` を付ける → 左は自動で鏡映。
回転（統合版の rotation）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く /
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import math

import numpy as np

from astro_common import (bevel, beam, cbox, line_on, mat_cube, octa, polyline, rbox, ring,
                          stick, taper)
from astro_suit import ARM_X, LEG_X, Suit, mirror_x
from hd_space import rot

TRIM_W = 0.4           # 真珠の縁取りの幅
FIN = ["fin", "fin_m"]  # ヒレの条（白と淡い水色を交互に）

# 配色（astro_data の neptune: plate 紺碧 / plate2 藍 / glow 水色 / accent 白）
AZURE = (36, 92, 214)
INDIGO = (36, 48, 148)
ABYSS = (12, 16, 40)
AQUA = (79, 227, 255)
FOAM = (234, 244, 255)
PEARL = (200, 224, 238)


# ===========================================================================
#  形の道具（このスーツとナノウェポンで使う）
# ===========================================================================
def _v(p):
    return np.asarray(p, float)


def fin3(bone, A, B, C, thick, layer, style, overlap=0.15, styles=None, **kw):
    """三角形 ABC を、辺 A→B に平行な細い板（ヒレの条）を C へ向かって重ねて埋める。
    どの向きの平面でもよい（板の厚みは三角形の面の法線の向き）。styles で条を交互に塗る。
    戻り値はキューブのリスト。"""
    A, B, C = _v(A), _v(B), _v(C)
    e = B - A
    L = float(np.linalg.norm(e))
    e /= L
    N = np.cross(B - A, C - A)
    N /= np.linalg.norm(N)
    n = np.cross(N, e)
    cu, cv = float(np.dot(C - A, e)), float(np.dot(C - A, n))
    if cv < 0:
        n, cv = -n, -cv
    R = np.column_stack([N, n, np.cross(N, n)])
    out = []
    k = int(math.ceil(cv / layer - 1e-6))
    h = cv / k
    for i in range(k):
        d = h * (i + 0.5)
        s = d / cv
        u0, u1 = sorted((s * cu, L + s * (cu - L)))
        ln = u1 - u0 + overlap
        if ln < 0.2:
            continue
        cen = A + e * ((u0 + u1) / 2) + n * d
        st = styles[i % len(styles)] if styles else style
        out.append(mat_cube(bone, cen, (thick, h * 1.06, ln), st, R, **kw))
    return out


def fan_fin(bone, base0, base1, edge, thick, style, width=None, styles=None, taper_k=0.7,
            tip_style=None, **kw):
    """ヒレ: 付け根 base0→base1 に沿って並べた根元から、外縁の点列 edge へ放射状に伸びる条の板。
    隣の条と重なって一枚の膜に見え、外縁は条の先で波打つ（波頭）。条の板は付け根から先へ
    taper_k 倍まで細る（2 段）。edge[0] の条が前縁。戻り値はキューブのリスト。"""
    b0, b1 = _v(base0), _v(base1)
    E = [_v(p) for p in edge]
    n = len(E)
    N = np.cross(b1 - b0, E[0] - b0)
    if np.linalg.norm(N) < 1e-6:
        N = np.cross(b1 - b0, E[-1] - b0)
    N /= np.linalg.norm(N)
    out = []
    for i, P in enumerate(E):
        root = b0 + (b1 - b0) * (i / max(1, n - 1))
        d = P - root
        L = float(np.linalg.norm(d))
        if L < 0.2:
            continue
        dz = d / L
        wv = np.cross(N, dz)
        R = np.column_stack([N, wv, np.cross(N, wv)])
        if width is None:
            sp = float(np.linalg.norm(b1 - b0)) / max(1, n - 1)
            nb = float(np.linalg.norm(E[min(n - 1, i + 1)] - E[max(0, i - 1)])) / 2
            w = max(0.5, (sp + nb) * 0.75)
        else:
            w = width[i] if isinstance(width, (list, tuple)) else width
        st = styles[i % len(styles)] if styles else style
        for k, (t0, t1, ww) in enumerate(((0.0, 0.55, w), (0.5, 1.0, w * taper_k))):
            c = root + d * ((t0 + t1) / 2)
            sk = (tip_style[i % len(tip_style)] if isinstance(tip_style, (list, tuple))
                  else tip_style) if (k == 1 and tip_style) else st
            out.append(mat_cube(bone, c, (thick, ww, L * (t1 - t0) + 0.1), sk, R, **kw))
    return out


def diamond(bone, centre, d, t, style, tilt=0.0, yaw=0.0, **kw):
    """対角線 d の菱形の板（厚み t）。tilt は上端を前へ倒す角度（負で下端が前 = 鱗の重なり）。"""
    s = d / math.sqrt(2)
    R = rot(tilt, yaw, 0) @ rot(0, 0, 45)
    return mat_cube(bone, centre, (s, s, t), style, R, **kw)


def scales(bone, cx, y0, z, rows, d, widths, style, t=0.5, tilt=-16.0, styles=None, yaw=0.0):
    """菱形の鱗を段にして並べる（上の段の下端が下の段に重なる）。widths は段ごとの幅（個数を決める）。"""
    out = []
    for r in range(rows):
        y = y0 - r * d * 0.55
        w = widths[r] if isinstance(widths, (list, tuple)) else widths
        n = max(1, int(round(w / d)))
        if r % 2 == 1:
            n = max(1, n - 1)
        x0 = cx - (n - 1) * d / 2
        for i in range(n):
            st = styles[(r + i) % len(styles)] if styles else style
            out.append(diamond(bone, (x0 + i * d, y, z - r * 0.02), d, t, st, tilt=tilt, yaw=yaw))
    return out


# ===========================================================================
#  塗り（astro_paint.suit_styles("neptune") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate": {"base": AZURE, "light": (120, 170, 245), "dark": (18, 52, 140),
              "line": (10, 30, 92)},
    "plate_b": {"base": (26, 68, 170), "light": (90, 140, 230), "dark": (14, 40, 112),
                "line": (8, 24, 80)},
    "plate2": {"base": INDIGO, "light": (92, 116, 218), "dark": (18, 24, 86),
               "line": (8, 10, 44), "groove": (16, 20, 70), "panel": 0},
    "plate2_b": {"base": (26, 34, 112), "light": (70, 88, 180), "dark": (14, 18, 64),
                 "line": (6, 8, 32)},
    # 白い波頭のヒレ（条の筋が斜めに走る）
    "fin": {"kind": "armor", "base": FOAM, "light": (255, 255, 255), "dark": (176, 204, 238),
            "line": (120, 160, 220), "panel": 0, "bolts": False, "outline_k": 0.35,
            "bevel_lo": 0.92, "unlit": True},
    "fin_m": {"kind": "armor", "base": (190, 222, 250), "light": (236, 248, 255),
              "dark": (140, 186, 236), "line": (110, 150, 214), "panel": 0, "bolts": False,
              "sheen": False, "outline_k": 0.3, "bevel_lo": 0.92, "unlit": True},
    "fin_b": {"kind": "armor", "base": (196, 220, 246), "light": (240, 248, 255),
              "dark": (120, 156, 210), "line": (50, 84, 150), "panel": 0, "sheen": False},
    "pearl": {"kind": "trim", "base": PEARL, "light": (255, 255, 255), "dark": (96, 132, 176),
              "line": (36, 52, 96)},
    "gold": {"kind": "trim", "base": PEARL, "light": (255, 255, 255), "dark": (96, 132, 176),
             "line": (36, 52, 96)},
    "chrome": {"base": (170, 200, 236), "line": (30, 44, 90)},
    "frame": {"base": (26, 32, 64), "light": (70, 86, 140), "line": (8, 10, 24)},
    "dark": {"base": (14, 18, 44), "line": (4, 6, 16)},
    "inner": {"base": (16, 20, 48), "glow": AQUA},
    "visor": {"glow": (110, 240, 255), "light": (230, 255, 255), "deep": (10, 70, 140),
              "emit": 18},
    "glow": {"glow": AQUA, "light": (220, 252, 255)},
    "glow_soft": {"glow": AQUA, "light": (220, 252, 255)},
    "vent": {"base": (22, 28, 60), "glow": AQUA, "deep": (8, 40, 110)},
    "grille": {"kind": "vent", "base": (30, 40, 90), "glow": (30, 50, 110), "deep": (8, 12, 30),
               "slat": 2},
    "gill": {"kind": "vent", "base": (20, 26, 62), "glow": (90, 236, 255), "deep": (6, 40, 120),
             "slat": 2},
    "thruster": {"glow": (110, 236, 255), "light": (240, 255, 255), "deep": (14, 60, 170)},
    "flame": {"glow": (90, 220, 255), "light": (230, 255, 255), "deep": (20, 70, 200)},
    "flame_core": {"kind": "flame", "glow": (200, 250, 255), "light": (255, 255, 255),
                   "deep": (90, 190, 255), "bevel": False, "outline": False},
    "core": {"halo": AQUA, "bezel": (10, 14, 36), "emit": 40},
    "gem": {"glow": (90, 240, 255), "deep": (10, 40, 120)},
    # 尾ビレのマント: 深い藍の布、裾は泡（白い雲の縁）と水色の光
    "cape": {"kind": "cloth", "base": (30, 44, 132), "shadow": (14, 20, 70), "hem": None,
             "cloud": True, "cloud_glow": AQUA, "hem_emit": 40, "outline": True,
             "line": (10, 14, 50), "outline_k": 0.6, "fold": 7.0},
    "tail": {"kind": "armor", "base": (44, 104, 222), "light": (120, 170, 245),
             "dark": (22, 60, 160), "line": (12, 32, 96), "panel": 0, "bolts": False,
             "outline_k": 0.45},
    "tail_b": {"kind": "armor", "base": (34, 82, 196), "light": (100, 150, 236),
               "dark": (18, 48, 140), "line": (10, 28, 90), "panel": 0, "bolts": False,
               "sheen": False, "outline_k": 0.45},
    "cape_top": {"kind": "cloth", "base": (40, 96, 214), "shadow": (20, 52, 150),
                 "hem": PEARL, "cloud": False, "outline": True, "line": (10, 14, 50),
                 "outline_k": 0.6, "fold": 7.0},
    "serial": {"text": "TR-08", "under": {"kind": "armor", "base": INDIGO, "panel": 0,
                                          "line": (8, 10, 40)},
               "ink": (150, 236, 255)},
    "hazard": {"c1": AQUA, "c2": ABYSS},
    "face": {"kind": "armor", "base": (60, 76, 150), "panel": 0, "line": (12, 16, 50),
             "light": (120, 140, 210)},
    "emblem": {"under": {"kind": "armor", "base": INDIGO, "panel": 0, "line": (8, 10, 40)},
               "color": AQUA},
}

# ===========================================================================
#  部位アニメ（q.anim_time は 12 秒でループ → 周波数は 30°/秒の倍数）
#  v.astro_air: 空中で 1 / v.astro_run: 疾走で 1。`_r` は左へ自動で鏡映
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # 海王星の大暗斑の嵐は逆向き（時計回り）に回る
        "fx_spin_storm": {"rotation": [0, 0, "-q.anim_time * 90.0"]},
        "fx_spin_turbine": {"rotation": [0, 0, "q.anim_time * 120.0"]},
        "extra_tail_r": {"rotation": ["4.0 + math.sin(q.anim_time * 90.0) * 2.5", 0,
                                      "math.sin(q.anim_time * 60.0) * 1.5"]},
        "extra_tail2_r": {"rotation": ["5.0 + math.sin(q.anim_time * 90.0 - 70.0) * 4.0", 0, 0]},
        "extra_tail_l": {"rotation": ["4.0 + math.sin(q.anim_time * 90.0 + 50.0) * 2.5", 0,
                                      "-math.sin(q.anim_time * 60.0 + 40.0) * 1.5"]},
        "extra_tail2_l": {"rotation": ["5.0 + math.sin(q.anim_time * 90.0 - 20.0) * 4.0", 0, 0]},
    },
    "thrust": {
        "fx_spin_turbine": {"rotation": [0, 0, "q.anim_time * 720.0 * v.astro_air"]},
        # 空中では尾ビレが二股に開き、スラスターの炎の通り道を空ける
        "extra_tail_r": {"rotation": ["v.astro_air * 18.0", 0, "v.astro_air * 16.0"]},
        "extra_tail2_r": {"rotation": [
            "v.astro_air * (14.0 + math.sin(q.anim_time * 720.0) * 6.0)", 0,
            "v.astro_air * 8.0"]},
    },
    "sprint": {
        "fx_spin_turbine": {"rotation": [0, 0, "q.anim_time * 360.0 * v.astro_run"]},
        "extra_tail_r": {"rotation": ["v.astro_run * 26.0", 0, "-v.astro_run * 4.0"]},
        "extra_tail2_r": {"rotation": [
            "v.astro_run * (12.0 + math.sin(q.anim_time * 900.0) * 5.0)", 0, 0]},
    },
}


# ===========================================================================
def build_suit(s: Suit):
    s.inner_suit(gap=0.3)
    boots(s)
    legs(s)
    waist(s)
    tail_cape(s)
    torso(s)
    back(s)
    arms(s)
    shoulders(s)
    helmet(s)


# ---------------------------------------------------------------------------
#  ブーツ（尖ったつま先・踵の噴射口・足首の真珠の関節）
# ---------------------------------------------------------------------------
def boots(s):
    X = LEG_X
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (X, -0.3, -0.6), (5.2, 0.8, 6.6), "frame")                    # 靴底
    cbox(b, (X, 1.7, -0.2), (5.2, 3.2, 5.8), "plate2")                     # 足の殻
    toe = rbox(b, (X, 1.0, -3.25), (4.7, 2.0, 1.9), "plate", rot=(-34, 0, 0))
    line_on(b, toe, "north", (0.5, 0.15), (0.5, 0.9), 0.32, 0.2, "glow")
    # 尖ったつま先（左右の板が前で合わさる舳先）と真珠の縁
    pr = rbox(b, (X - 0.75, 0.45, -4.25), (2.0, 1.1, 1.7), "plate2", rot=(-8, 34, 0))
    pe = stick(b, pr, "north", 0.5, 0.15, (1.9, 0.3, 0.18), "pearl", sink=0.04)
    mirror_x(b, pr, pe, about=X)
    inst = rbox(b, (X, 3.35, -2.45), (4.0, 2.0, 0.8), "plate", rot=(-28, 0, 0))   # 甲
    stick(b, inst, "north", 0.5, 0.92, (3.6, TRIM_W, 0.2), "pearl", sink=0.05)
    rbox(b, (X, 1.7, 2.75), (4.6, 2.8, 0.9), "plate2_b", rot=(8, 0, 0))   # 踵
    cbox(b, (X, 0.45, 3.2), (3.0, 1.0, 1.1), "frame")                      # 踵の噴射口
    cbox(b, (X, -0.05, 3.2), (2.2, 0.2, 0.7), "thruster")
    octa(b, (X - 2.72, 2.8, 0.3), 2.0, 0.55, "pearl", axis="x")           # 足首の関節（外）
    octa(b, (X - 3.0, 2.8, 0.3), 0.9, 0.3, "glow", axis="x")
    cbox(b, (X - 2.66, 0.95, -0.9), (0.22, 0.35, 4.2), "glow")              # 外側の発光線
    # 踵の小さな尾ビレ（後ろへ）
    fin3(b, (X - 0.9, 2.6, 3.1), (X - 0.9, 1.0, 3.3), (X - 0.9, 3.3, 5.0), 0.4, 0.55, "fin")


# ---------------------------------------------------------------------------
#  脚（鱗の脛当て・外へ反る脛のヒレ・貝殻の膝当て・腿）
# ---------------------------------------------------------------------------
def legs(s):
    X = LEG_X
    g = s.part("legs", "greave_r", "rightLeg")
    cbox(g, (X, 5.2, 0.05), (5.3, 4.4, 5.5), "plate2")                     # 脛の殻
    cbox(g, (X, 5.4, -2.85), (3.9, 4.6, 0.3), "frame")                     # 鱗の下地
    scales(g, X, 7.0, -3.1, 4, 1.55, [3.8, 3.8, 3.8, 3.2], "plate", t=0.45, tilt=-18)
    cbox(g, (X, 8.1, 0.05), (5.25, 1.5, 5.35), "frame")                    # 膝の関節
    # 膝当て: 貝殻（扇の三枚）+ 真珠の縁 + 宝玉
    kb = bevel(g, (X, 8.0, -3.0), (3.7, 2.6, 1.1), "plate2", cut=0.5, axis="z")
    for k, a in enumerate((-28, 0, 28)):
        rbox(g, (X + math.sin(math.radians(a)) * 0.9, 8.55, -3.55), (0.9, 2.2, 0.35), "plate",
             rot=(-12, 0, a))
    cbox(g, (X, 7.05, -3.5), (3.2, TRIM_W, 0.4), "pearl")
    rbox(g, (X, 9.35, -3.35), (0.8, 0.8, 0.4), "gem", rot=(0, 0, 45))
    _ = kb
    # ふくらはぎ
    calf = rbox(g, (X, 5.4, 2.85), (4.6, 4.2, 1.0), "plate2_b", rot=(-8, 0, 0))
    stick(g, calf, "south", 0.5, 0.5, (2.6, 2.4, 0.3), "vent", sink=0.1)
    # 外側の板と、外へ反る白いヒレ（脛のヒレ）
    side = rbox(g, (X - 2.72, 5.4, 0.3), (0.6, 4.0, 4.0), "plate", rot=(0, 0, -4))
    line_on(g, side, "west", (0.1, 0.25), (0.9, 0.75), 0.24, 0.2, "glow")
    fn = s.part("legs", "calf_fin_r", g, pivot=(X - 2.9, 5.0, 0.6), rotation=(0, 0, -16))
    fx = X - 3.1
    fan_fin(fn, (fx, 8.6, 0.9), (fx, 3.8, 1.5),
            [(fx, 10.8, 5.8), (fx, 9.0, 6.0), (fx, 7.0, 5.3), (fx, 5.0, 3.8)], 0.42, "fin",
            styles=FIN)
    beam(fn, (fx, 8.6, 0.9), (fx, 10.8, 5.8), 0.55, 0.5, "pearl", extend=0.3)   # 前縁
    beam(fn, (fx - 0.12, 8.2, 1.4), (fx - 0.12, 4.4, 1.9), 0.42, 0.22, "glow")
    # 腿
    t = s.part("legs", "thigh_r", "rightLeg", pivot=(X, 11.6, 0))
    cbox(t, (X, 10.4, 0.05), (5.2, 3.3, 5.4), "plate2")
    th = rbox(t, (X, 10.35, -2.85), (4.4, 3.4, 0.8), "plate", rot=(-5, 0, 0))
    line_on(t, th, "north", (0.8, 0.12), (0.62, 0.5), 0.26, 0.2, "glow")
    line_on(t, th, "north", (0.62, 0.5), (0.8, 0.9), 0.26, 0.2, "glow")
    stick(t, th, "north", 0.5, 0.05, (4.2, TRIM_W, 0.2), "pearl", sink=0.05)
    cbox(t, (X - 2.62, 10.2, 0.3), (0.6, 3.0, 3.8), "plate2",
         decals={"west": {"decal": "serial", "text": "TR-08", "ink": (150, 236, 255)}})


# ---------------------------------------------------------------------------
#  腰（ベルト・三叉の留め金・鱗の草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    cbox(w, (0, 12.6, 0), (9.5, 1.7, 5.9), "frame")
    cbox(w, (0, 12.95, -2.98), (8.8, 0.25, 0.2), "glow")
    octa(w, (0, 12.55, -3.15), 2.6, 0.7, "pearl", axis="z")                # 留め金
    rbox(w, (0, 12.55, -3.55), (1.1, 1.1, 0.4), "gem", rot=(0, 0, 45))
    # 前垂れ: 鱗の三枚
    fr = rbox(w, (0, 10.75, -3.0), (3.0, 2.6, 0.6), "plate2", rot=(-12, 0, 0))
    stick(w, fr, "north", 0.5, 0.5, (0.45, 2.2, 0.2), "glow", sink=0.05)
    side = rbox(w, (-2.3, 11.0, -2.9), (2.0, 2.3, 0.7), "plate", rot=(-10, 14, 6))
    mirror_x(w, side)
    # 草摺（腰の横）: 藍の下板 + 鱗の上板 + 真珠の縁 + 白い波頭の先
    t1 = rbox(w, (-5.25, 10.3, -0.2), (0.8, 4.2, 5.0), "plate2", rot=(0, 0, 12))
    t2 = rbox(w, (-5.6, 9.9, -0.4), (0.6, 3.0, 4.2), "plate", rot=(0, 0, 15))
    t3 = stick(w, t2, "west", 0.5, 0.06, (4.0, TRIM_W, 0.22), "pearl", sink=0.05)
    t4 = line_on(w, t2, "west", (0.12, 0.62), (0.88, 0.62), 0.24, 0.2, "glow")
    t5 = rbox(w, (-5.75, 8.1, 1.0), (0.5, 1.4, 2.2), "fin", rot=(-30, 0, 18))
    mirror_x(w, t1, t2, t3, t4, t5)
    rbox(w, (0, 10.9, 2.95), (6.4, 2.4, 0.8), "plate2", rot=(10, 0, 0))   # 後ろ垂れ


# ---------------------------------------------------------------------------
#  尾ビレのマント（ベルトの後ろから二股に垂れる。上下 2 段で揺れる）
# ---------------------------------------------------------------------------
def tail_cape(s):
    tp = s.part("extra", "tail_r", "body", pivot=(-1.7, 12.6, 3.5), rotation=(4, 0, 8))
    cbox(tp, (-1.7, 12.6, 3.45), (3.4, 1.0, 0.8), "pearl")                 # 留め具
    cbox(tp, (-1.75, 10.5, 3.6), (3.3, 4.2, 0.4), "cape_top")
    cbox(tp, (-3.32, 10.5, 3.6), (0.3, 4.0, 0.5), "glow_soft")
    lo = s.part("extra", "tail2_r", tp, pivot=(-1.75, 8.5, 3.6), rotation=(4, 0, 10))
    # 下の段: 尾ビレ（上の縁から放射に広がる条。外の条が長く尖って二股になる。先は泡の白）
    fan_fin(lo, (-0.2, 8.7, 3.6), (-3.4, 8.7, 3.6),
            [(-0.5, 4.6, 3.6), (-1.6, 3.6, 3.6), (-2.9, 2.6, 3.6), (-4.3, 1.4, 3.6)], 0.36,
            "tail", styles=["tail", "tail_b"], tip_style=["fin", "fin_m"], taper_k=0.75)
    beam(lo, (-3.4, 8.6, 3.62), (-4.3, 1.6, 3.62), 0.3, 0.42, "glow_soft", extend=0.1)


# ---------------------------------------------------------------------------
#  胴（竜骨・鰓の胸板・鱗の腹・星核・襟）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    bevel(c, (0, 21.1, 0.0), (9.8, 5.8, 5.8), "plate2", cut=0.6, axis="y")   # 胸郭（藍）
    cbox(c, (0, 15.9, 0.0), (7.4, 4.8, 5.2), "plate2_b")                    # 腹の殻（細い）
    cbox(c, (0, 15.9, -2.62), (6.0, 4.7, 0.4), "frame")                     # 腹の下地
    # 腹: 菱形の鱗を重ねた鱗鎧（下へ行くほど細い）
    scales(c, 0, 17.6, -2.95, 5, 1.5, [6.0, 5.6, 5.2, 4.6, 4.0], "plate",
           styles=["plate", "plate", "plate_b"], t=0.5, tilt=-16)
    ob = rbox(c, (-3.3, 16.0, -2.3), (1.3, 4.2, 1.0), "plate2", rot=(0, 36, -6))   # 脇腹
    mirror_x(c, ob)
    # 中央の竜骨（星核の台）
    keel = rbox(c, (0, 21.0, -3.05), (2.8, 5.4, 0.9), "plate2", rot=(4, 0, 0))
    stick(c, keel, "north", 0.5, 0.97, (2.6, TRIM_W, 0.2), "pearl", sink=0.05)
    # 鰓の胸板（三枚が外下へ流れて重なる。間から水色の光）
    for k, (y, w, zf) in enumerate(((22.6, 4.0, -3.0), (21.2, 3.7, -2.95), (19.8, 3.3, -2.85))):
        x = -1.6 - w / 2 - k * 0.15
        gl = rbox(c, (x - 0.1, y - 0.62, zf + 0.2), (w - 0.2, 0.35, 0.4), "glow",
                  rot=(10, 10, 14 + k * 3))
        pl = rbox(c, (x, y, zf - k * 0.04), (w, 1.35, 0.7), "plate", rot=(-10, 12, 14 + k * 3))
        tr = stick(c, pl, "north", 0.5, 0.92, (w - 0.3, 0.3, 0.18), "pearl", sink=0.04)
        mirror_x(c, gl, pl, tr)
    # 星核: 黒い台 → 真珠の八角の枠 → 海王星 → 逆回りの嵐の羽根 → 脈打つ光
    octa(c, (0, 20.6, -3.7), 3.6, 0.6, "dark", axis="z")
    octa(c, (0, 20.6, -4.05), 3.2, 0.4, "pearl", axis="z")
    cbox(c, (0, 20.6, -4.3), (2.4, 2.4, 0.8), "core")
    sp = s.fx("spin", "storm", c, pivot=(0, 20.6, -4.45))
    for i in range(6):
        a = math.radians(i * 60)
        p0 = (-math.sin(a) * 1.55, 20.6 + math.cos(a) * 1.55, -4.5)
        p1 = (-math.sin(a + 0.7) * 2.05, 20.6 + math.cos(a + 0.7) * 2.05, -4.5)
        beam(sp, p0, p1, 0.22, 0.3, "glow" if i % 2 == 0 else "glow_soft")
    gl = s.fx("glow", "core", c, pivot=(0, 20.6, -4.5))
    ring(gl, (0, 20.6, -4.76), 1.22, 8, (0, 0.18, 0.2), "glow_soft", axis="z")
    # 襟（首の両脇に立つ）と、外へ開く鰓蓋の白いヒレ
    col = rbox(c, (-3.0, 24.35, -0.2), (2.2, 1.5, 5.0), "plate2", rot=(0, 0, -20))
    colt = stick(c, col, "up", 0.5, 0.5, (1.8, 4.6, 0.25), "fin", sink=0.1)
    mirror_x(c, col, colt)
    # 脇: 排気口
    fl = cbox(c, (-4.8, 21.0, 0.3), (0.5, 3.6, 3.2), "plate")
    fv = cbox(c, (-5.07, 20.9, 0.3), (0.15, 2.4, 2.0), "gill")
    mirror_x(c, fl, fv)


# ---------------------------------------------------------------------------
#  背中（背板・背骨の小ビレ・水流タービン・ヒレの形の双発スラスター）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    cbox(bk, (0, 18.7, 2.95), (8.6, 9.8, 0.7), "plate2_b")                 # 背板
    cbox(bk, (0, 18.4, 3.6), (2.4, 8.4, 1.0), "frame")                     # 背骨
    bevel(bk, (0, 19.9, 4.5), (5.4, 6.2, 2.4), "plate2", cut=0.8, axis="z")   # 背嚢
    side = cbox(bk, (-2.75, 19.9, 4.5), (0.3, 4.4, 1.6), "plate")
    mirror_x(bk, side)
    # 水流タービン（背嚢の中央。真珠の縁の吸気口と回る羽根）
    ring(bk, (0, 20.2, 5.75), 1.75, 10, (0, 0.4, 0.5), "pearl", axis="z")
    cbox(bk, (0, 20.2, 5.6), (2.6, 2.6, 0.3), "dark")
    tb = s.fx("spin", "turbine", bk, pivot=(0, 20.2, 5.85))
    for i in range(5):
        a = math.radians(i * 72)
        beam(tb, (0, 20.2, 5.85), (-math.sin(a) * 1.3, 20.2 + math.cos(a) * 1.3, 5.85),
             0.5, 0.18, "plate", roll=25)
    octa(tb, (0, 20.2, 5.95), 0.7, 0.3, "glow", axis="z")
    cbox(bk, (0, 16.6, 5.0), (3.0, 0.8, 0.25), "hazard")
    # 背骨の小さな背ビレ（下へ小さく）
    for k, (y, h) in enumerate(((23.6, 1.7), (17.4, 1.3), (15.2, 1.0))):
        fin3(bk, (0, y, 4.0 if k else 4.6), (0, y - 1.4, 4.0 if k else 4.6),
             (0, y + 0.2, 4.0 + h + (0.6 if not k else 0)), 0.4, 0.5, "fin")
    # スラスター（右。下後ろへ向けたノズル + 外上へ反る白い背ビレ）
    th = s.part("back", "thruster_r", bk, pivot=(-2.0, 17.2, 5.0), rotation=(14, 0, -8))
    octa(th, (-2.0, 16.2, 5.2), 2.0, 2.8, "plate2", axis="y")
    octa(th, (-2.0, 16.9, 5.2), 2.25, 0.35, "pearl", axis="y")
    octa(th, (-2.0, 14.5, 5.2), 2.5, 1.1, "frame", axis="y")
    ring(th, (-2.0, 13.95, 5.2), 1.0, 8, (0, 0.26, 0.3), "glow", axis="y")
    cbox(th, (-2.0, 13.9, 5.2), (1.8, 0.2, 1.8), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-2.0, 13.85, 5.2))
    taper(fx, (-2.0, 13.85, 5.2), (-2.0, 7.0, 5.2), 2.0, 0.4, 3, "flame")
    taper(fx, (-2.0, 13.8, 5.2), (-2.0, 10.0, 5.2), 0.9, 0.25, 2, "flame_core", round_=False)
    # 背ビレ（スラスターの付け根から外上へ反り、肩の後ろに先が出る）
    bf = s.part("back", "dorsal_r", bk, pivot=(-2.4, 18.5, 5.4), rotation=(-12, -32, -16))
    fx_ = -2.4
    fan_fin(bf, (fx_, 20.4, 5.0), (fx_, 17.8, 6.8),
            [(fx_, 28.6, 10.6), (fx_, 26.2, 11.6), (fx_, 23.2, 11.0), (fx_, 20.4, 9.6)], 0.5,
            "fin", styles=FIN)
    beam(bf, (fx_, 20.4, 5.0), (fx_, 28.6, 10.6), 0.62, 0.6, "pearl", extend=0.3)   # 前縁
    beam(bf, (fx_ - 0.15, 20.2, 5.6), (fx_ - 0.15, 18.2, 7.0), 0.5, 0.22, "glow")
    taper(bf, (fx_, 18.3, 5.5), (fx_, 21.8, 7.4), 1.2, 0.6, 1, "plate2", round_=False)   # 付け根の装甲


# ---------------------------------------------------------------------------
#  腕（藍の上腕・真珠の腕章・前腕の白いヒレ・鱗の篭手）
# ---------------------------------------------------------------------------
def arms(s):
    ar = s.part("arms", "upper_r", "rightArm", pivot=(ARM_X, 20.0, 0))
    bevel(ar, (-6.1, 20.4, 0.0), (5.4, 5.6, 5.8), "plate2", cut=0.5, axis="y")
    cbox(ar, (-6.1, 17.85, 0.0), (5.7, 0.7, 6.1), "plate")                  # 腕章
    cbox(ar, (-6.1, 17.85, 0.0), (5.8, 0.22, 6.2), "pearl")
    op = rbox(ar, (-8.85, 19.8, 0.0), (0.6, 2.8, 3.6), "plate", rot=(0, 0, 4))
    line_on(ar, op, "west", (0.5, 0.12), (0.5, 0.88), 0.26, 0.2, "glow")
    el = s.part("arms", "elbow_r", "rightArm", pivot=(ARM_X, 16.8, 0))
    cbox(el, (-6.0, 16.9, 0.0), (5.3, 1.5, 5.3), "frame")
    octa(el, (-8.45, 16.9, 0.2), 1.8, 0.5, "pearl", axis="x")
    rbox(el, (-6.3, 17.0, 2.75), (3.0, 1.9, 0.8), "plate", rot=(-18, 0, 0))
    # 前腕: 紺碧の篭手、外の稜に鱗、外へ反る白いヒレ
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=(ARM_X, 15.0, 0))
    cbox(fa, (-6.0, 14.95, 0), (4.9, 3.1, 5.1), "plate2")
    ob = rbox(fa, (-8.65, 14.85, 0), (0.7, 3.3, 4.8), "plate", rot=(0, 0, 7))
    line_on(fa, ob, "west", (0.15, 0.2), (0.85, 0.2), 0.24, 0.2, "glow")
    rbox(fa, (-6.15, 14.85, -2.72), (4.1, 3.1, 0.7), "plate", rot=(-8, 0, 0))
    rbox(fa, (-6.15, 14.85, 2.72), (4.1, 3.1, 0.7), "plate2_b", rot=(8, 0, 0))
    cbox(fa, (-6.0, 13.42, 0), (5.7, TRIM_W, 5.9), "pearl")
    af = s.part("arms", "arm_fin_r", fa, pivot=(-8.9, 14.5, 0.5), rotation=(0, 0, -14))
    x = -9.1
    fan_fin(af, (x, 16.4, -0.9), (x, 13.2, -0.4),
            [(x, 19.6, 4.0), (x, 17.8, 4.6), (x, 15.8, 3.9), (x, 14.0, 2.4)], 0.42, "fin",
            styles=FIN)
    beam(af, (x, 16.4, -0.9), (x, 19.6, 4.0), 0.5, 0.45, "pearl", extend=0.3)
    beam(af, (x + 0.12, 16.2, -0.4), (x + 0.12, 13.4, 0.1), 0.42, 0.2, "glow")
    # 拳: 甲の紺碧・真珠の指の関節・二節の指・親指・宝玉
    h = s.part("arms", "gauntlet_r", "rightArm", pivot=(ARM_X, 13.2, 0))
    cbox(h, (-6.0, 12.15, 0.0), (5.3, 2.7, 5.5), "plate2")
    hb = rbox(h, (-6.0, 12.6, -2.95), (4.6, 1.3, 0.7), "plate", rot=(-10, 0, 0))
    stick(h, hb, "north", 0.5, 0.5, (1.0, 0.4, 0.15), "glow", sink=0.04)
    for i in range(4):
        xx = -7.65 + i * 1.1
        cbox(h, (xx, 12.65, -3.37), (0.7, 0.45, 0.3), "pearl")
        rbox(h, (xx, 11.7, -2.88), (0.85, 1.2, 0.6), "plate_b", rot=(18, 0, 0))
        rbox(h, (xx, 10.85, -2.5), (0.8, 0.9, 0.55), "plate2_b", rot=(40, 0, 0))
    rbox(h, (-3.2, 12.2, -1.3), (0.6, 1.8, 1.4), "plate_b", rot=(0, 0, -10))
    rbox(h, (-8.7, 12.35, 0), (0.4, 1.0, 1.0), "gem", rot=(45, 0, 0))


# ---------------------------------------------------------------------------
#  肩（重ねた貝殻の肩当て + 波頭の白い縁）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    C = (-6.1, 21.7, 0.0)
    # 丸い貝殻の肩当て: 肩の上から外へ回り込む二段の弧（藍の殻 → 外へ張る紺碧の段）
    ring(p, C, 3.65, 4, (0, 0.9, 6.9), "plate2", axis="z", a0=-18, a1=100)
    ring(p, (C[0], C[1] - 0.3, C[2] - 0.2), 4.5, 3, (0, 0.8, 5.9), "plate", axis="z", a0=30,
         a1=112)
    ring(p, (C[0], C[1] - 0.3, -3.3), 4.62, 3, (0, 0.5, 0.35), "pearl", axis="z", a0=30, a1=112)
    # 外の面の紋章板と、外下の波頭の白い返し
    rbox(p, (-10.75, 19.4, 0.2), (0.5, 1.8, 3.4), "plate2", rot=(0, 0, 24),
         decals={"west": {"decal": "emblem", "color": AQUA}})
    rbox(p, (-10.95, 18.35, 0.2), (0.35, 0.5, 3.6), "fin", rot=(0, 0, 24))


# ---------------------------------------------------------------------------
#  兜（藍のドーム・三叉の冠・背ビレの鶏冠・耳ビレ・面頬の鰓・吊り目のバイザー）
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 31.2, 0.15), (9.8, 4.6, 10.1), "plate2", cut=1.0, axis="z")
    rf = rbox(hm, (-2.45, 33.75, 0.3), (5.2, 0.8, 9.4), "plate", rot=(0, 0, -12))
    rfr = line_on(hm, rf, "up", (0.04, 0.06), (0.04, 0.94), 0.3, 0.2, "pearl")
    mirror_x(hm, rf, rfr)
    cbox(hm, (0, 34.5, 0.3), (1.6, 1.0, 9.0), "plate2")                      # 中央の稜
    rbox(hm, (0, 32.0, -4.85), (8.6, 2.6, 0.8), "plate2", rot=(-30, 0, 0))   # 額の斜面
    rbox(hm, (0, 31.9, 5.2), (8.6, 2.4, 0.8), "plate2", rot=(30, 0, 0))      # 後ろの斜面
    cbox(hm, (0, 26.9, 4.95), (8.8, 4.6, 0.8), "plate2")                      # 後頭部
    cbox(hm, (0, 28.6, 5.45), (1.2, 5.4, 0.4), "pearl")                       # 後頭の稜（鶏冠の続き）
    cbox(hm, (0, 28.4, 5.66), (0.3, 4.6, 0.2), "glow")
    for zx in (-2.6, 2.6):                                                    # 後頭の鰓のスリット
        cbox(hm, (zx, 27.2, 5.42), (1.8, 1.6, 0.2), "grille")
    sd = cbox(hm, (-4.95, 27.3, 0.1), (0.9, 5.0, 8.4), "plate")               # 側板
    ear = octa(hm, (-5.55, 27.8, 0.9), 2.4, 0.5, "pearl", axis="x")
    eg = octa(hm, (-5.85, 27.8, 0.9), 1.0, 0.25, "glow", axis="x")
    mirror_x(hm, sd, ear, eg)
    # 耳ビレ（側頭から後ろ上へ反る）
    ef = s.part("helmet", "ear_fin_r", hm, pivot=(-5.6, 28.0, 1.0), rotation=(0, 0, -18))
    fan_fin(ef, (-5.9, 29.4, 0.4), (-5.9, 27.0, 1.0),
            [(-5.9, 32.4, 6.0), (-5.9, 30.6, 6.4), (-5.9, 28.6, 5.2)], 0.4, "fin", styles=FIN)
    beam(ef, (-5.9, 29.4, 0.4), (-5.9, 32.4, 6.0), 0.48, 0.42, "pearl", extend=0.3)
    # 背ビレの鶏冠（頭頂の中央を前から後ろへ高く。白い条・水色の付け根・真珠の前縁）
    cr = s.part("helmet", "crest", hm, pivot=(0, 34.8, 1.0))
    fan_fin(cr, (0, 34.7, -1.8), (0, 34.6, 5.0),
            [(0, 40.0, 5.0), (0, 38.6, 6.8), (0, 36.8, 7.8), (0, 34.6, 8.0)], 0.5, "fin",
            styles=FIN)
    polyline(cr, [(0, 34.7, -1.8), (0, 37.6, 1.4), (0, 40.0, 5.0)], 0.62, 0.5, "pearl")
    cbox(cr, (0, 35.05, 1.8), (0.7, 0.35, 7.4), "glow")
    # 三叉の冠（額の上: 中央の高い穂先と、外へ開いて先が内へ返る左右の穂先）
    tc = s.part("helmet", "trident", hm, pivot=(0, 32.6, -5.2))
    cbox(tc, (0, 32.4, -5.35), (4.6, 0.6, 0.6), "pearl")                     # 横木
    octa(tc, (0, 32.4, -5.75), 1.3, 0.4, "pearl", axis="z")
    rbox(tc, (0, 32.4, -6.0), (0.75, 0.75, 0.3), "gem", rot=(0, 0, 45))
    taper(tc, (0, 32.6, -5.4), (0, 38.2, -5.0), 0.95, 0.3, 3, "pearl", round_=False)   # 中央の穂先
    diamond(tc, (0, 36.9, -5.05), 1.8, 0.4, "pearl")                         # 返し
    diamond(tc, (0, 36.9, -5.28), 0.8, 0.2, "glow")
    cbox(tc, (0, 34.2, -5.72), (0.26, 2.6, 0.2), "glow")
    side = polyline(tc, [(-2.1, 32.5, -5.35), (-3.0, 34.0, -5.25), (-3.15, 35.7, -5.15),
                         (-2.55, 36.7, -5.1)], [0.75, 0.6, 0.45], [0.7, 0.6, 0.45], "pearl")
    sb = diamond(tc, (-3.15, 35.3, -5.15), 1.2, 0.34, "pearl")
    sg = cbox(tc, (-3.05, 34.4, -5.6), (0.22, 1.2, 0.2), "glow")
    mirror_x(tc, side, sb, sg)
    # 面: 奥の暗い金属・鰓のスリットの面頬・細い顎・頬当て
    cbox(hm, (0, 25.7, -4.62), (7.6, 3.6, 0.5), "frame")
    mg = rbox(hm, (-1.15, 25.6, -5.05), (2.3, 2.9, 0.7), "face", rot=(0, 28, 0))
    mv = stick(hm, mg, "north", 0.5, 0.45, (1.6, 1.8, 0.1), "grille", sink=0.05)
    mirror_x(hm, mg, mv)
    cbox(hm, (0, 25.9, -5.6), (0.5, 2.8, 0.5), "plate")
    rbox(hm, (0, 24.15, -4.8), (3.0, 0.9, 1.3), "plate2", rot=(-30, 0, 0))
    ck = rbox(hm, (-3.45, 25.7, -3.75), (1.4, 3.8, 3.3), "plate", rot=(0, 34, -6))
    ckt = stick(hm, ck, "west", 0.08, 0.5, (0.35, 3.4, 0.2), "pearl", sink=0.05)
    mirror_x(hm, ck, ckt)
    # しころ（後ろの首の鱗）
    scales(hm, 0, 24.2, 5.45, 2, 1.6, [8.0, 8.0], "plate", t=0.5, tilt=18, yaw=180)
    # バイザー（吊り上がった鋭い二つの目）
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 28.0, -4.8), (8.4, 1.9, 0.6), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 28.0, -5.1))
    half = rbox(fg, (-1.95, 28.05, -5.12), (3.4, 0.75, 0.35), "visor", rot=(0, 10, 14))
    mirror_x(fg, half)
    cbox(vz, (0, 28.1, -5.2), (0.6, 2.0, 0.4), "plate2")                       # 眉間の稜
