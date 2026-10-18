# -*- coding: utf-8 -*-
"""土星 — 環帝機装 クロノス（Kronos Frame）。

環を従える時の王。淡い金（plate）とアイボリー（plate2）の優美な装甲に、土星の縞のような褐色の帯（band）。
* 腰を斜め（約 22°）に回る大きな環（氷青に光る B 環・カッシーニの空隙・アイボリーの A 環・点線の F 環・
  環に乗る二つの羊飼い衛星）。fx_spin で静かに回る、このスーツの看板のシルエット
* 胸の六角形（北極の六角渦）: 金の六角枠の中に褐色の六角の盤・光る六角の線・土星の星核（小さな環付き）
* 肩当ての外と背中の大きな文字盤（目盛り・紫の軸石・回る時針と分針）
* 冠の兜（褐色の額環・金の尖塔・紫の宝玉）と、冠の周りを斜めに回る小さな環の光輪
* 長い草摺（金とアイボリーを重ね、先が尖る）、紫の六角の差し色、背中の双発スラスター

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。右側だけ作り `_r` を付ける → 左は自動で鏡映。
回転（統合版の rotation）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く /
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import math

import numpy as np

from astro_common import (_group, bevel, beam, cbox, line_on, octa, rbox, ring, stick, surface,
                          taper)
from astro_suit import ARM_X, LEG_X, Suit, mirror_x
from hd_space import rot as _rot

SQ3 = math.sqrt(3.0)
TRIM_W = 0.36          # 金の縁取りの幅

# 色（astro_data の saturn の配色に合わせた追加の色）
BAND = (160, 108, 62)          # 土星の縞の褐色
BAND_D = (112, 74, 44)
ICE = (190, 230, 255)
VIOLET = (142, 124, 255)

# ===========================================================================
#  塗り（astro_paint.suit_styles("saturn") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate": {"bolts": False},
    "visor": {"glow": (176, 226, 255), "light": (240, 250, 255), "deep": (40, 80, 150), "emit": 20},
    "flame": {"glow": (150, 210, 255), "light": (246, 252, 255), "deep": (70, 110, 210)},
    "flame_core": {"kind": "flame", "glow": (220, 240, 255), "light": (255, 255, 255),
                   "deep": (120, 170, 255), "bevel": False, "outline": False},
    "thruster": {"glow": (160, 220, 255), "light": (246, 252, 255), "deep": (40, 80, 150)},
    # 褐色の帯（土星の縞）
    "band": {"kind": "armor", "base": BAND, "light": (214, 160, 104), "dark": BAND_D,
             "line": (70, 44, 24), "panel": 0, "sheen": False},
    "band_d": {"kind": "armor", "base": BAND_D, "light": (150, 104, 64), "dark": (70, 46, 28),
               "line": (40, 26, 14), "panel": 0, "sheen": False},
    # 縞の装甲（腹・草摺の奥）: 淡い金に褐色の横縞
    "belted": {"kind": "armor", "base": (227, 201, 138), "light": (250, 236, 196),
               "dark": (176, 146, 86), "line": (96, 72, 36), "panel": 0,
               "stripe": {"dir": "h", "period": 7, "width": 2, "color": (176, 124, 70), "k": 0.8}},
    # 文字盤（アイボリーの無地）
    "dial": {"kind": "armor", "base": (250, 244, 228), "light": (255, 255, 250),
             "dark": (214, 200, 170), "line": (120, 100, 70), "panel": 0, "sheen": False},
    "hand": {"kind": "trim", "base": (60, 50, 74), "light": (150, 140, 190), "dark": (24, 20, 34),
             "line": (14, 12, 20)},
    # 環
    "ring_b": {"kind": "glowline", "glow": ICE, "light": (246, 252, 255), "bevel": False,
               "outline": False, "emit": 26},
    "ring_b2": {"kind": "glowline", "glow": (150, 200, 245), "light": (214, 238, 255), "bevel": False,
                "outline": False, "emit": 70},
    "ring_a": {"kind": "armor", "base": (244, 232, 204), "light": (255, 252, 240),
               "dark": (200, 182, 140), "line": (130, 110, 76), "panel": 0, "sheen": False,
               "stripe": {"dir": "h", "period": 3, "width": 1, "color": (214, 192, 150), "k": 0.6}},
    "ring_a2": {"kind": "armor", "base": (222, 196, 140), "light": (250, 236, 196),
                "dark": (170, 140, 90), "line": (110, 86, 50), "panel": 0, "sheen": False,
                "stripe": {"dir": "h", "period": 3, "width": 1, "color": (190, 160, 110), "k": 0.6}},
    "ring_f": {"kind": "glowline", "glow": (210, 240, 255), "light": (255, 255, 255), "bevel": False,
               "outline": False, "emit": 14},
    "moonlet": {"kind": "planet", "planet": "luna", "bevel": False, "outline": False,
                "radius": 1.45, "vary": 0},
    "serial": {"text": "KR-06", "under": {"kind": "armor", "base": (247, 238, 216), "panel": 0,
                                          "line": (110, 90, 60)},
               "ink": (112, 74, 44)},
    "hazard": {"c1": (227, 201, 138), "c2": (90, 60, 36)},
    "emblem": {"color": VIOLET},
    "gem_accent": {"glow": (168, 150, 255), "deep": (52, 36, 120)},
    "gem": {"glow": (190, 236, 255), "deep": (40, 80, 150)},
    "face": {"kind": "armor", "base": (236, 226, 204), "panel": 0, "line": (96, 80, 60)},
}

# ===========================================================================
#  部位アニメ（Molang。q.anim_time は 12 秒でループ → 周波数は 30°/秒の倍数）
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # 大環: 一周 12 秒でゆっくり回り、傾きがかすかに歳差運動する
        "fx_spin_ring": {"rotation": [0, "q.anim_time * 30.0", 0]},
        "extra_ring": {"rotation": ["math.sin(q.anim_time * 30.0) * 1.5", 0,
                                    "math.cos(q.anim_time * 30.0) * 1.5"],
                       "position": [0, "math.sin(q.anim_time * 60.0) * 0.25", 0]},
        # 冠の光輪（逆回り）
        "fx_spin_halo": {"rotation": [0, "-q.anim_time * 60.0", 0]},
        # 肩の文字盤: 時針 30°/秒・分針 360°/秒（左は外から見て時計回りになるよう逆向き）
        "fx_spin_hour_r": {"rotation": ["q.anim_time * 30.0", 0, 0]},
        "fx_spin_min_r": {"rotation": ["q.anim_time * 360.0", 0, 0]},
        "fx_spin_hour_l": {"rotation": ["-q.anim_time * 30.0", 0, 0]},
        "fx_spin_min_l": {"rotation": ["-q.anim_time * 360.0", 0, 0]},
        # 背中の文字盤
        "fx_spin_bhour": {"rotation": [0, 0, "q.anim_time * 30.0"]},
        "fx_spin_bmin": {"rotation": [0, 0, "q.anim_time * 180.0"]},
        "fx_spin_bring": {"rotation": [0, 0, "-q.anim_time * 30.0"]},
        # 草摺のかすかな揺れ
        "waist_tasset_r": {"rotation": [0, 0, "math.sin(q.anim_time * 90.0) * 0.8"]},
    },
    "thrust": {
        # 空中: 環が水平に近づいて少し浮き、速く回る印に光輪が持ち上がる。草摺が後ろへなびく
        "extra_ring": {"rotation": ["-v.astro_air * 6.0", 0, "v.astro_air * 8.0"],
                       "position": [0, "v.astro_air * 1.2", 0]},
        "extra_halo": {"position": [0, "v.astro_air * 0.6", 0]},
        "waist_tasset_r": {"rotation": ["v.astro_air * 16.0", 0,
                                        "v.astro_air * (6.0 + math.sin(q.anim_time * 720.0) * 2.0)"]},
        "waist_tasset_back": {"rotation": ["v.astro_air * 18.0", 0, 0]},
    },
    "sprint": {
        # 疾走: 環が後ろへ傾き、草摺が後ろへ流れる
        "extra_ring": {"rotation": ["-v.astro_run * 10.0", 0, 0]},
        "waist_tasset_r": {"rotation": ["v.astro_run * (10.0 + math.sin(q.anim_time * 900.0) * 4.0)",
                                        0, "v.astro_run * 4.0"]},
        "waist_tasset_back": {"rotation": ["v.astro_run * 14.0", 0, 0]},
    },
}


# ===========================================================================
#  六角形の補助
# ===========================================================================
_BASIS = {
    "z": np.eye(3),                                                    # 法線 Z（正面向き）
    "x": np.column_stack([(0, 0, 1), (0, 1, 0), (-1, 0, 0)]).astype(float),   # 法線 X（横向き）
    "y": np.column_stack([(1, 0, 0), (0, 0, 1), (0, -1, 0)]).astype(float),   # 法線 Y（水平）
}


def hex_plate(bone, centre, R, depth, style, axis="z", rot_=None, pointy=False, step=0.1):
    """塗りつぶした正六角形（3 枚の箱を 60° ずつ回して重ねる）。R は頂点までの半径。
    面が同じ平面に重ならないよう、厚みを step ずつ変える。"""
    B = _BASIS[axis]
    parts = []
    for k, a in enumerate((0, 60, -60)):
        a2 = a + (30 if pointy else 0)
        parts.append((centre, (R, R * SQ3, depth + step * k), B @ _rot(0, 0, a2), style))
    return _group(bone, parts, rot_, centre, centre)


def hex_ring(bone, centre, R, w, t, style, axis="z", rot_=None, pointy=False, styles=None):
    """正六角形の枠（6 本の帯）。R は帯の中心線の頂点半径、w は帯の幅、t は厚み。"""
    B = _BASIS[axis]
    ap = R * SQ3 / 2
    parts = []
    c = np.asarray(centre, float)
    for k in range(6):
        phi = math.radians(30 + 60 * k + (30 if pointy else 0))
        rad = np.array([math.cos(phi), math.sin(phi), 0.0])
        tan = np.array([math.sin(phi), -math.cos(phi), 0.0])
        Rl = np.column_stack([tan, rad, (0.0, 0.0, 1.0)])
        st = styles[k % len(styles)] if styles else style
        parts.append((c + B @ (rad * ap), (R + w * 0.577, w, t), B @ Rl, st))
    return _group(bone, parts, rot_, centre, centre)


FACE_AXIS = {"north": "z", "south": "z", "east": "x", "west": "x", "up": "y", "down": "y"}


def hex_on(bone, cube, face, a, b, R, depth, style, lift=0.0, sink=0.05, pointy=False, step=0.1):
    """傾いた板 cube の面 face の (a, b) に、同じ傾きで六角形を貼る。戻り値: 一番薄い板の前面の点。"""
    pt, n = surface(cube, face, a, b)
    c = pt + n * (lift + depth / 2 - sink)
    hex_plate(bone, tuple(c), R, depth, style, axis=FACE_AXIS[face], rot_=cube.rotation,
              pointy=pointy, step=step)
    return c + n * depth / 2


def dial_ticks(bone, centre, r, axis, big="gold", small="gold", n=12, size=(0.22, 0.5, 0.14),
               big_size=(0.36, 0.8, 0.16)):
    """文字盤の目盛り（n 本の放射状の小片。3 時ごとに大きく）。"""
    out = []
    for i in range(n):
        a = i * 360.0 / n
        if i % (n // 4) == 0:
            out += ring(bone, centre, r - (big_size[1] - size[1]) / 2, 1, big_size, big, axis=axis,
                        phase=a, a0=0, a1=360)
        else:
            out += ring(bone, centre, r, 1, size, small, axis=axis, phase=a, a0=0, a1=360)
    return out


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
    great_ring(s)
    halo(s)


# ---------------------------------------------------------------------------
#  ブーツ（足首から）: 金の殻・アイボリーのつま先・褐色の足首の帯・踵の噴射口・外の紫の六角
# ---------------------------------------------------------------------------
def boots(s):
    X = LEG_X
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (X, -0.35, -0.6), (5.3, 0.7, 6.7), "frame")                    # 靴底
    cbox(b, (X, 1.6, -0.2), (5.2, 3.0, 5.8), "plate")                      # 足の殻
    toe = rbox(b, (X, 1.1, -3.25), (4.8, 2.2, 1.7), "plate2", rot=(-40, 0, 0))
    stick(b, toe, "north", 0.5, 0.5, (0.45, 1.4, 0.22), "glow", sink=0.05)
    cbox(b, (X, 0.25, -4.05), (4.6, 0.6, 0.7), "gold")                     # つま先の金具
    ins = rbox(b, (X, 3.3, -2.45), (4.2, 2.0, 0.8), "plate2", rot=(-28, 0, 0))   # 甲
    stick(b, ins, "north", 0.5, 0.15, (3.9, TRIM_W, 0.2), "gold", sink=0.05)
    cbox(b, (X, 3.5, 0.0), (5.45, 0.9, 6.0), "band")                       # 足首の褐色の帯
    cbox(b, (X, 3.5, 0.0), (5.55, 0.25, 6.1), "gold")
    rbox(b, (X, 1.7, 2.75), (4.6, 2.9, 0.9), "plate_b", rot=(8, 0, 0))     # 踵
    cbox(b, (X, 0.5, 3.25), (3.0, 1.0, 1.1), "frame")                      # 踵の噴射口
    cbox(b, (X, -0.05, 3.25), (2.2, 0.2, 0.7), "thruster")
    side = cbox(b, (X - 2.7, 1.7, -0.3), (0.3, 2.4, 3.6), "plate2")         # 外の板
    hex_plate(b, (X - 2.95, 1.75, -0.3), 0.85, 0.2, "gold", axis="x")
    hex_plate(b, (X - 3.05, 1.75, -0.3), 0.55, 0.2, "gem_accent", axis="x", step=0.05)
    del side
    cbox(b, (X - 2.66, 0.55, -2.5), (0.22, 0.3, 2.4), "glow")               # 外側の発光線


# ---------------------------------------------------------------------------
#  脚（脛・膝・腿）
# ---------------------------------------------------------------------------
def legs(s):
    X = LEG_X
    g = s.part("legs", "greave_r", "rightLeg")
    cbox(g, (X, 5.6, 0.05), (5.3, 3.9, 5.5), "plate")                      # 脛の殻
    keel = rbox(g, (X - 0.72, 5.5, -2.95), (1.55, 3.9, 0.8), "plate2", rot=(0, 22, 0))
    kl = line_on(g, keel, "north", (0.5, 0.12), (0.5, 0.88), 0.24, 0.2, "glow")
    mirror_x(g, keel, kl, about=X)                                          # 脛の稜（V 字）
    cbox(g, (X, 7.25, 0.05), (5.45, 0.55, 5.65), "band")                   # 脛の上の褐色の帯
    cbox(g, (X, 8.25, 0.05), (5.25, 1.5, 5.35), "frame")                   # 膝の関節
    # 膝当て: 金の六角枠 + アイボリーの六角 + 紫の六角の宝玉
    hex_plate(g, (X, 8.05, -3.0), 1.75, 0.6, "plate2", pointy=True)
    hex_ring(g, (X, 8.05, -3.35), 1.75, 0.34, 0.25, "gold", pointy=True)
    hex_plate(g, (X, 8.05, -3.42), 0.7, 0.25, "gem_accent", pointy=True, step=0.04)
    rbox(g, (X, 9.65, -2.75), (3.0, 0.8, 1.0), "plate", rot=(28, 0, 0))    # 膝の庇
    # ふくらはぎ: 縞の板と排気口
    calf = rbox(g, (X, 5.5, 2.85), (4.6, 4.0, 1.0), "belted", rot=(-8, 0, 0))
    stick(g, calf, "south", 0.5, 0.45, (2.4, 2.2, 0.3), "vent", sink=0.1)
    # 外側の羽根（上端が外へ反る薄い金の板と発光線）
    fin = rbox(g, (X - 2.75, 5.6, 0.6), (0.6, 3.8, 3.0), "plate2", rot=(-8, 0, -6))
    line_on(g, fin, "west", (0.2, 0.15), (0.8, 0.85), 0.22, 0.2, "glow")
    # 腿: アイボリーの殻・金の外板（型番）・褐色の帯・前の重ね板
    t = s.part("legs", "thigh_r", "rightLeg", pivot=(X, 11.6, 0))
    cbox(t, (X, 10.45, 0.05), (5.2, 3.2, 5.4), "plate2_b")
    th = rbox(t, (X, 10.5, -2.85), (4.4, 3.2, 0.8), "plate2", rot=(-5, 0, 0))
    stick(t, th, "north", 0.5, 0.06, (4.2, TRIM_W, 0.2), "gold", sink=0.05)
    line_on(t, th, "north", (0.2, 0.55), (0.8, 0.55), 0.22, 0.2, "glow_soft")
    cbox(t, (X - 2.62, 10.4, 0.3), (0.6, 2.9, 3.9), "plate",
         decals={"west": {"decal": "serial", "text": "KR-06", "ink": (112, 74, 44)}})
    cbox(t, (X, 11.95, 0.05), (5.3, 0.5, 5.5), "band")


# ---------------------------------------------------------------------------
#  腰（ベルト・前垂れ・長い草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    cbox(w, (0, 12.65, 0), (9.6, 1.8, 6.0), "band")                        # 褐色の帯のベルト
    for y in (13.5, 11.8):
        cbox(w, (0, y, 0), (9.7, 0.22, 6.1), "gold")
    # バックル: 金の六角 + 土星（模様）の宝玉
    hex_plate(w, (0, 12.65, -3.2), 1.45, 0.5, "gold")
    hex_plate(w, (0, 12.65, -3.5), 0.95, 0.3, "planet", step=0.04)
    # 前垂れ: アイボリーの台形（二枚重ね）と金の縁・紫の小さな宝玉
    fr = rbox(w, (0, 10.4, -3.1), (3.4, 2.6, 0.6), "plate2", rot=(-10, 0, 0))
    stick(w, fr, "north", 0.5, 0.05, (3.2, TRIM_W, 0.2), "gold", sink=0.05)
    stick(w, fr, "north", 0.5, 0.45, (0.7, 0.7, 0.25), "gem_accent", spin=45, sink=0.05)
    fs = rbox(w, (-2.4, 10.85, -2.95), (1.7, 2.1, 0.6), "plate", rot=(-8, 14, 8))
    mirror_x(w, fs)
    # 後ろ垂れ（短く・縞）
    bk = s.part("waist", "tasset_back", w, pivot=(0, 12.0, 2.8))
    rbox(bk, (0, 10.4, 3.05), (6.6, 3.0, 0.7), "belted", rot=(10, 0, 0))
    rbox(bk, (0, 9.0, 3.3), (4.6, 1.2, 0.6), "plate2", rot=(14, 0, 0))
    # 長い草摺（右。左は鏡映）: 金の外板 + アイボリーの内板 + 褐色の帯 + 先の尖り + 発光線 + 紫の六角
    tz = s.part("waist", "tasset_r", w, pivot=(-4.9, 12.6, 0.0))
    t1 = rbox(tz, (-5.3, 9.0, -0.1), (0.8, 6.8, 5.0), "plate", rot=(0, 0, 9))
    t2 = rbox(tz, (-5.7, 8.6, -0.1), (0.5, 5.6, 4.0), "plate2", rot=(0, 0, 11))
    stick(tz, t2, "west", 0.5, 0.86, (4.0, 0.6, 0.18), "band", sink=0.04)
    line_on(tz, t2, "west", (0.5, 0.1), (0.5, 0.72), 0.22, 0.18, "glow")
    stick(tz, t2, "west", 0.08, 0.5, (TRIM_W, 5.4, 0.16), "gold", sink=0.04)
    stick(tz, t2, "west", 0.92, 0.5, (TRIM_W, 5.4, 0.16), "gold", sink=0.04)
    hex_on(tz, t2, "west", 0.5, 0.82, 0.62, 0.22, "gem_accent", step=0.04, pointy=True)
    # 先の尖り（下へ細る金の剣先）
    taper(tz, (-5.25, 5.75, -0.1), (-5.0, 3.6, -0.1), 1.6, 0.35, 2, "plate", round_=False)
    del t1


# ---------------------------------------------------------------------------
#  胴（胸郭・六角形の胸・星核・腹の縞・襟）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    bevel(c, (0, 21.1, 0.0), (9.8, 5.8, 5.9), "plate2", cut=0.7, axis="y")   # アイボリーの胸郭
    cbox(c, (0, 15.9, 0.0), (7.6, 4.8, 5.3), "plate_b")                    # 腹の殻（細い）
    cbox(c, (0, 16.0, -2.66), (5.4, 4.6, 0.5), "frame")
    # 腹: 縞の三段（土星の縞）
    for y, wd in ((17.15, 5.2), (15.95, 4.8), (14.75, 4.3)):
        rbox(c, (0, y, -2.98), (wd, 1.25, 0.7), "belted", rot=(-10, 0, 0))
    ob = rbox(c, (-3.3, 16.0, -2.3), (1.4, 4.2, 1.0), "plate", rot=(0, 36, -6))   # 脇腹
    mirror_x(c, ob)
    # 金の胸板（六角の両脇、外へ開く）
    pec = rbox(c, (-3.35, 21.3, -2.95), (3.3, 4.6, 0.8), "plate", rot=(4, 22, 6))
    pt = stick(c, pec, "north", 0.5, 0.04, (3.1, TRIM_W, 0.2), "band", sink=0.05)
    pl = line_on(c, pec, "north", (0.85, 0.25), (0.2, 0.75), 0.22, 0.2, "glow")
    low = rbox(c, (-2.6, 18.45, -2.85), (3.6, 1.3, 0.75), "plate", rot=(-6, 14, 14))
    mirror_x(c, pec, pt, pl, low)
    # 襟: 金の立ち襟（首の両脇）と褐色の首輪
    col = rbox(c, (-3.0, 24.35, -0.2), (2.2, 1.5, 5.0), "plate", rot=(0, 0, -22))
    colt = stick(c, col, "up", 0.5, 0.5, (1.6, 4.6, 0.22), "band", sink=0.08)
    mirror_x(c, col, colt)
    # 六角形の胸（北極の六角渦）: 褐色の盤 → 金の枠 → 光る内枠 → 星核
    hx = s.part("torso", "hexagon", c, pivot=(0, 20.6, -3.2))
    C = (0, 20.6, -3.2)
    hex_plate(hx, C, 2.7, 0.7, "band_d")
    hex_ring(hx, (0, 20.6, -3.58), 2.75, 0.5, 0.3, "gold")
    hex_ring(hx, (0, 20.6, -3.62), 1.85, 0.2, 0.2, "glow")
    for k in range(6):                                                   # 頂点の紫の宝玉
        a = math.radians(60 * k)
        rbox(hx, (2.75 * math.cos(a), 20.6 + 2.75 * math.sin(a), -3.82), (0.5, 0.5, 0.3),
             "gem_accent", rot=(0, 0, 45))
    cbox(hx, (0, 20.6, -3.9), (2.2, 2.2, 0.9), "core")                    # 土星の星核
    gl = s.fx("glow", "core", hx, pivot=(0, 20.6, -4.4))
    rbox(gl, (0, 20.6, -4.42), (3.6, 0.32, 0.22), "ring_f", rot=(0, 0, -22))   # 星核の小さな環
    # 脇: アイボリーの板と排気口
    fl = cbox(c, (-4.8, 21.0, 0.3), (0.5, 3.6, 3.2), "plate")
    fv = cbox(c, (-5.07, 20.9, 0.3), (0.15, 2.4, 2.0), "vent")
    mirror_x(c, fl, fv)


# ---------------------------------------------------------------------------
#  背中（背板・大きな文字盤・双発スラスター）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    cbox(bk, (0, 18.7, 2.95), (8.6, 9.8, 0.7), "plate_b")                  # 背板
    cbox(bk, (0, 17.0, 3.6), (2.6, 6.0, 1.0), "frame")                     # 背骨
    rbox(bk, (0, 23.0, 3.5), (6.0, 1.0, 1.4), "plate", rot=(20, 0, 0))     # 肩の間の板
    # 文字盤: 八角の台（金）→ アイボリーの盤 → 目盛り → 紫の軸石
    D = (0, 19.4, 4.3)
    octa(bk, (0, 19.4, 3.85), 5.4, 0.8, "plate", axis="z")
    octa(bk, (0, 19.4, 4.25), 4.7, 0.4, "dial", axis="z")
    dial_ticks(bk, (0, 19.4, 4.5), 2.5, "z", size=(0.24, 0.55, 0.16), big_size=(0.4, 0.9, 0.18))
    octa(bk, (0, 19.4, 4.55), 0.9, 0.3, "gem_accent", axis="z")
    sr = s.fx("spin", "bring", bk, pivot=D)
    ring(sr, (0, 19.4, 4.1), 4.0, 16, (0, 0.34, 0.34), "glow", axis="z",
         styles=["glow", "ring_b2"])
    hh = s.fx("spin", "bhour", bk, pivot=D)
    cbox(hh, (0, 20.1, 4.68), (0.36, 1.4, 0.12), "hand")
    mh = s.fx("spin", "bmin", bk, pivot=D)
    cbox(mh, (0, 20.45, 4.74), (0.24, 2.1, 0.1), "hand")
    # スラスター（右。下後ろへ）
    th = s.part("back", "thruster_r", bk, pivot=(-2.4, 16.0, 4.0), rotation=(18, 0, -10))
    octa(th, (-2.4, 15.0, 4.0), 1.9, 2.6, "plate2", axis="y")
    octa(th, (-2.4, 15.9, 4.0), 2.2, 0.35, "band", axis="y")
    octa(th, (-2.4, 13.4, 4.0), 2.4, 1.0, "frame", axis="y")
    ring(th, (-2.4, 12.85, 4.0), 0.95, 8, (0, 0.24, 0.26), "glow", axis="y")
    cbox(th, (-2.4, 12.82, 4.0), (1.7, 0.2, 1.7), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-2.4, 12.75, 4.0))
    taper(fx, (-2.4, 12.75, 4.0), (-2.4, 6.4, 4.0), 1.9, 0.4, 3, "flame")
    taper(fx, (-2.4, 12.7, 4.0), (-2.4, 9.2, 4.0), 0.9, 0.22, 2, "flame_core", round_=False)


# ---------------------------------------------------------------------------
#  腕（上腕・肘・前腕・篭手）
# ---------------------------------------------------------------------------
def arms(s):
    ar = s.part("arms", "upper_r", "rightArm", pivot=(ARM_X, 20.0, 0))
    bevel(ar, (-6.1, 20.4, 0.0), (5.4, 5.6, 5.8), "plate", cut=0.5, axis="y")
    cbox(ar, (-6.1, 17.85, 0.0), (5.7, 0.75, 6.1), "band")                 # 褐色の腕輪
    cbox(ar, (-6.1, 18.3, 0.0), (5.8, 0.2, 6.2), "gold")
    op = rbox(ar, (-8.85, 19.9, 0.0), (0.5, 2.6, 3.4), "plate2", rot=(0, 0, 4))
    line_on(ar, op, "west", (0.5, 0.12), (0.5, 0.88), 0.24, 0.2, "glow")
    el = s.part("arms", "elbow_r", "rightArm", pivot=(ARM_X, 16.8, 0))
    cbox(el, (-6.0, 16.9, 0.0), (5.3, 1.5, 5.3), "frame")
    octa(el, (-8.45, 16.9, 0.2), 1.8, 0.5, "gold", axis="x")
    octa(el, (-8.72, 16.9, 0.2), 0.9, 0.2, "gem_accent", axis="x")
    rbox(el, (-6.3, 17.0, 2.75), (3.0, 1.9, 0.8), "plate", rot=(-18, 0, 0))
    # 前腕: アイボリーの篭手（手首へ開く）・外に金の板と紫の六角・褐色の手首の帯
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=(ARM_X, 15.0, 0))
    cbox(fa, (-6.0, 14.9, 0), (5.3, 3.3, 5.4), "plate2")
    ob = rbox(fa, (-8.85, 14.85, 0), (0.7, 3.4, 4.6), "plate", rot=(0, 0, 7))
    stick(fa, ob, "west", 0.5, 0.92, (4.4, TRIM_W, 0.16), "band", sink=0.04)
    hex_on(fa, ob, "west", 0.5, 0.45, 1.0, 0.24, "gold", pointy=True)
    hex_on(fa, ob, "west", 0.5, 0.45, 0.62, 0.2, "gem_accent", lift=0.2, pointy=True, step=0.04)
    rbox(fa, (-6.15, 14.85, -2.82), (4.1, 3.0, 0.6), "plate2", rot=(-8, 0, 0))
    rbox(fa, (-6.15, 14.85, 2.82), (4.1, 3.0, 0.6), "plate2_b", rot=(8, 0, 0))
    cbox(fa, (-6.0, 13.3, 0), (5.7, 0.5, 5.9), "band")
    # 拳: 金の甲・アイボリーの拳当て・指・親指
    h = s.part("arms", "gauntlet_r", "rightArm", pivot=(ARM_X, 13.2, 0))
    cbox(h, (-6.0, 12.1, 0.0), (5.3, 2.6, 5.5), "plate")
    rbox(h, (-6.0, 12.55, -2.95), (4.6, 1.3, 0.7), "plate2", rot=(-10, 0, 0))
    for i in range(4):
        x = -7.65 + i * 1.1
        cbox(h, (x, 12.65, -3.37), (0.7, 0.45, 0.3), "gold")
        rbox(h, (x, 11.7, -2.88), (0.85, 1.2, 0.6), "plate_b", rot=(18, 0, 0))
        rbox(h, (x, 10.85, -2.5), (0.8, 0.9, 0.55), "plate_b", rot=(40, 0, 0))
    rbox(h, (-3.2, 12.2, -1.3), (0.6, 1.8, 1.4), "plate_b", rot=(0, 0, -10))


# ---------------------------------------------------------------------------
#  肩（丸い肩当て・外の文字盤・垂れる金の板）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    dome = bevel(p, (-7.0, 24.0, 0.0), (5.8, 3.0, 7.0), "plate2", cut=1.1, axis="x",
                 rot=(0, 0, -12))
    top = stick(p, dome[0], "up", 0.45, 0.5, (3.4, 4.8, 0.4), "plate", sink=0.12)
    line_on(p, top, "up", (0.5, 0.1), (0.5, 0.9), 0.26, 0.2, "glow")
    # 外の文字盤（外 -X を向く）: 金の縁 → アイボリーの盤 → 目盛り → 紫の軸石 → 時針・分針
    C = (-10.2, 22.2, 0.0)
    octa(p, (-9.85, 22.2, 0.0), 3.7, 0.7, "plate", axis="x")
    octa(p, (-10.15, 22.2, 0.0), 3.1, 0.3, "dial", axis="x")
    dial_ticks(p, (-10.33, 22.2, 0.0), 1.6, "x", size=(0.18, 0.4, 0.12), big_size=(0.28, 0.62, 0.14))
    octa(p, (-10.36, 22.2, 0.0), 0.6, 0.2, "gem_accent", axis="x")
    hr = s.fx("spin", "hour_r", p, pivot=C)
    cbox(hr, (-10.42, 22.7, 0.0), (0.1, 1.0, 0.28), "hand")
    mn = s.fx("spin", "min_r", p, pivot=C)
    cbox(mn, (-10.47, 22.2, -0.7), (0.08, 0.2, 1.4), "hand")
    # 上の縁: 外へ反る金の環の縁（土星の環の意匠）
    rim = rbox(p, (-9.6, 25.1, 0.0), (0.8, 1.2, 7.4), "plate", rot=(0, 0, -32))
    stick(p, rim, "up", 0.5, 0.5, (0.8, 7.4, 0.24), "band", sink=0.05)
    # 垂れる板（金・アイボリー）と褐色の縁
    l1 = rbox(p, (-9.85, 19.75, 0.0), (0.9, 1.6, 6.4), "plate", rot=(0, 0, 16))
    stick(p, l1, "west", 0.5, 0.08, (6.0, 0.3, 0.18), "band", sink=0.05)
    rbox(p, (-9.95, 18.65, 0.1), (0.8, 1.2, 5.6), "plate2", rot=(0, 0, 12))
    rbox(p, (-7.0, 25.7, 2.9), (0.5, 1.6, 2.2), "plate", rot=(-25, 0, -12))   # 後ろのヒレ


# ---------------------------------------------------------------------------
#  兜（丸い兜・褐色の額環・金の冠・耳の文字盤・面頬）とバイザー
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.9, 0.15), (9.8, 4.4, 10.0), "plate2", cut=1.3, axis="z")
    bevel(hm, (0, 31.2, 0.15), (9.0, 4.2, 10.0), "plate2", cut=1.3, axis="x")
    cbox(hm, (0, 33.25, 0.15), (6.4, 0.6, 7.2), "plate2_b")                 # 頭頂（帽子の角を覆う）
    cbox(hm, (0, 26.8, 4.95), (8.8, 4.4, 0.8), "plate2")                    # 後頭部
    rbox(hm, (0, 24.1, 5.25), (8.6, 1.9, 0.9), "plate", rot=(18, 0, 0))     # しころ
    rbox(hm, (0, 22.85, 5.5), (8.0, 1.2, 0.8), "band", rot=(30, 0, 0))
    sd = cbox(hm, (-4.95, 27.2, 0.6), (0.9, 4.8, 7.4), "plate")             # 側板（金）
    # 耳の文字盤（小）
    ear = octa(hm, (-5.55, 27.6, 0.6), 2.4, 0.5, "plate", axis="x")
    eard = octa(hm, (-5.75, 27.6, 0.6), 1.9, 0.2, "dial", axis="x")
    earg = octa(hm, (-5.88, 27.6, 0.6), 0.6, 0.16, "gem_accent", axis="x")
    mirror_x(hm, sd, ear, eard, earg)
    # 額環（褐色の冠の帯）と金の縁
    band = cbox(hm, (0, 30.15, -0.1), (9.9, 1.3, 9.9), "band")
    cbox(hm, (0, 30.9, -0.1), (10.0, 0.22, 10.0), "gold")
    cbox(hm, (0, 29.45, -0.1), (10.0, 0.22, 10.0), "gold")
    del band
    # 冠: 前の大きな尖塔 + 斜め前・横・後ろの尖塔（金）と、その根元の紫の宝玉
    spikes = [((0.0, -5.1), 5.6, 1.4), ((-2.9, -4.4), 4.0, 1.1), ((-4.6, -1.6), 3.2, 1.0),
              ((-4.4, 2.2), 2.6, 0.9), ((0.0, 4.9), 2.6, 0.9)]
    for (x, z), hgt, wd in spikes:
        out = np.array([x, 0.0, z])
        n = np.linalg.norm(out)
        tip = out / n * (n + 0.5) if n else out
        sp = taper(hm, (x, 31.0, z), (tip[0], 31.0 + hgt, tip[2]), wd, 0.22, 2, "gold", round_=False)
        if x < -0.01:
            mirror_x(hm, sp)
    for x, z in ((0.0, -5.06), (-2.9, -4.32)):
        g = rbox(hm, (x, 30.15, z - 0.1), (0.62, 0.62, 0.3), "gem_accent", rot=(0, 0, 45))
        if x < -0.01:
            mirror_x(hm, g)
    # 額の六角（紫）と眉庇
    hex_plate(hm, (0, 31.75, -5.2), 0.75, 0.3, "gold", pointy=True)
    hex_plate(hm, (0, 31.75, -5.38), 0.48, 0.2, "gem_accent", pointy=True, step=0.04)
    br = rbox(hm, (-2.3, 29.15, -5.0), (4.6, 0.9, 1.0), "plate", rot=(-12, 6, 6))
    mirror_x(hm, br)
    # 面頬: アイボリーの面と金の頬当て・縦の吸気スリット
    mg = rbox(hm, (-1.15, 25.75, -5.05), (2.4, 3.1, 0.7), "face", rot=(0, 26, 0))
    mv = stick(hm, mg, "north", 0.5, 0.36, (0.5, 1.2, 0.1), "vent", sink=0.05)
    mirror_x(hm, mg, mv)
    cbox(hm, (0, 25.9, -5.55), (0.5, 2.8, 0.5), "plate")                   # 中央の稜（金）
    cbox(hm, (0, 25.7, -4.62), (7.6, 3.6, 0.5), "frame")                   # 顔の奥
    rbox(hm, (0, 24.15, -4.8), (3.0, 0.9, 1.3), "plate", rot=(-30, 0, 0))   # 顎
    ck = rbox(hm, (-3.45, 25.7, -3.75), (1.4, 3.8, 3.3), "plate", rot=(0, 34, -6))
    ckt = stick(hm, ck, "west", 0.08, 0.5, (0.35, 3.4, 0.2), "band", sink=0.05)
    mirror_x(hm, ck, ckt)
    # バイザー: 暗い窓 + 氷青の二枚（中央で少し下がる）
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 27.95, -4.8), (8.4, 1.8, 0.6), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 28.0, -5.1))
    half = rbox(fg, (-2.0, 28.0, -5.1), (3.8, 0.95, 0.35), "visor", rot=(0, 8, -5))
    mirror_x(fg, half)


# ---------------------------------------------------------------------------
#  大環（腰を斜めに回る土星の環）
# ---------------------------------------------------------------------------
RING_C = (0.0, 13.2, 0.0)
RING_TILT = (12, 0, -20)          # 前が下がり、左（+X）が上がる（右手の側が下）


def great_ring(s):
    rg = s.part("extra", "ring", "body", pivot=RING_C, rotation=RING_TILT)
    sp = s.fx("spin", "ring", rg, pivot=RING_C)
    C = RING_C
    # B 環（氷青に光る・二色の節で回転が見える）
    ring(sp, C, 10.9, 28, (0, 1.7, 0.34), "ring_b", axis="y", styles=["ring_b", "ring_b2"])
    # A 環（アイボリーと淡い金の節）
    ring(sp, C, 12.75, 28, (0, 1.25, 0.28), "ring_a", axis="y", styles=["ring_a", "ring_a2"])
    # F 環（点線の光）
    ring(sp, C, 13.85, 18, (1.9, 0.22, 0.18), "ring_f", axis="y")
    # 羊飼い衛星（環に乗る小さな月）
    for a, r in ((40, 11.95), (215, 13.85)):
        t = math.radians(a)
        p = (C[0] - r * math.sin(t), C[1] + 0.05, C[2] - r * math.cos(t))
        rbox(sp, p, (0.7, 0.7, 0.7), "moonlet", rot=(0, a + 45, 0))


# ---------------------------------------------------------------------------
#  冠の光輪（小さな環が冠の周りを斜めに回る）
# ---------------------------------------------------------------------------
HALO_C = (0.0, 33.6, 0.0)


def halo(s):
    hl = s.part("extra", "halo", "head", pivot=HALO_C, rotation=(-10, 0, 14))
    sp = s.fx("spin", "halo", hl, pivot=HALO_C)
    ring(sp, HALO_C, 6.4, 20, (0, 0.6, 0.18), "ring_b", axis="y", styles=["ring_b", "ring_f"])
