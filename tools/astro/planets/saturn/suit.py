# -*- coding: utf-8 -*-
"""土星 — 環帝機装 クロノス（Kronos Frame）。7 頭身の「環を従える時の王」（v1.1）。

淡い金（plate）とアイボリー（plate2）の優美な装甲に、土星の縞のような褐色の帯（band）。背の高い、
法衣をまとった騎士のシルエット。frame7 の暗い骨格の上に、縁取りのある多層の装甲を重ねる:
* 腰を斜め（約 22°）に回る大きな環: 氷青に光る B 環（スポークの影）・カッシーニの空隙・縞のある A 環・
  点線の F 環。環とは別の速さで環の上を巡る三つの羊飼い衛星（fx_spin）。草摺の蝶番が環の発振器
* 胸の六角形（北極の六角渦）: 褐色の六角の盤・金の六角枠・光る内枠・頂点の紫の宝玉・土星の星核と小さな環
* 肩当ての外と背中の文字盤（目盛り・紫の軸石・回る時針と分針）、兜の耳の小さな文字盤
* 冠の兜（褐色の額環と金の縁・五本の金の尖り・紫の宝玉・氷青のバイザー・アイボリーの面頬）、
  頭頂の小さな土星の宝珠（自分の環が回る）と、冠の周りを斜めに回る光輪
* 長く尖った草摺（金とアイボリーの重ね・褐色の帯・紫の六角の宝玉）と、腰の後ろから垂れる法衣の裾
* 立ち襟、縞の腹、褐色の帯の篭手、六角の膝当て、尖った爪先のサバトン、背中の双発スラスター

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A（7 頭身の目安）から取る。
右側だけ作り `_r` を付ける → 左は自動で鏡映。回転（統合版の rotation）: rx 正 = 上端が前へ /
ry 正 = 正面が右（-X）を向く / rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。

ローカルの補助（共通部分に無いもの）: _grp（部品の組を回して置く）、hex_plate / hex_ring / hex_on（六角形）、
dial（文字盤: 縁・盤・目盛り・軸石）。輪は astro_weapon.ring（各セグメントを接線の向きに置く版）。
"""
from __future__ import annotations

import math

import numpy as np

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, line_on, mat_cube,  # noqa: F401
                        mirror_x, octa, piston, polyline, rbox, rivets, sensor, stick, surface,
                        taper, vents, layered_plate)
from astro_weapon import ring
from hd_space import rot as _rot

SQ3 = math.sqrt(3.0)
LX = A.LEG_X           # 脚の軸 -2.15
HZ = A.HEAD_Z          # 頭の中心の奥行き -0.25
GOLD_W = 0.24          # 金の縁取りの幅

# 色（astro_data の saturn の配色に合わせた追加の色）
BAND = (160, 108, 62)          # 土星の縞の褐色
BAND_D = (112, 74, 44)
VIOLET = (142, 124, 255)

# ===========================================================================
#  塗り（astro_paint.suit_styles("saturn") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate2": {"detail": False},
    "plate": {"base": (222, 188, 118), "light": (250, 228, 172), "dark": (160, 126, 70),
              "line": (92, 66, 30), "bolts": False},
    "plate_b": {"base": (184, 152, 92), "light": (222, 196, 140), "dark": (132, 102, 58),
                "line": (78, 56, 26)},
    "visor": {"glow": (150, 214, 255), "light": (240, 250, 255), "deep": (30, 70, 150), "emit": 20},
    "glow": {"glow": (120, 196, 255), "light": (226, 246, 255)},
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
    # 文字盤（アイボリーの無地）と針
    "dial": {"kind": "armor", "base": (250, 244, 228), "light": (255, 255, 250),
             "dark": (214, 200, 170), "line": (120, 100, 70), "panel": 0, "sheen": False},
    "hand": {"kind": "trim", "base": (60, 50, 74), "light": (150, 140, 190), "dark": (24, 20, 34),
             "line": (14, 12, 20)},
    # 環
    "ring_b": {"kind": "glowline", "glow": (96, 170, 255), "light": (186, 228, 255), "bevel": False,
               "outline": False, "emit": 34},
    "ring_b2": {"kind": "glowline", "glow": (70, 128, 228), "light": (150, 204, 255), "bevel": False,
                "outline": False, "emit": 90},
    "ring_a": {"kind": "armor", "base": (244, 232, 204), "light": (255, 252, 240),
               "dark": (200, 182, 140), "line": (130, 110, 76), "panel": 0, "sheen": False,
               "stripe": {"dir": "h", "period": 3, "width": 1, "color": (214, 192, 150), "k": 0.6}},
    "ring_a2": {"kind": "armor", "base": (222, 196, 140), "light": (250, 236, 196),
                "dark": (170, 140, 90), "line": (110, 86, 50), "panel": 0, "sheen": False,
                "stripe": {"dir": "h", "period": 3, "width": 1, "color": (190, 160, 110), "k": 0.6}},
    "ring_c": {"kind": "armor", "base": (120, 100, 80), "light": (170, 150, 120),
               "dark": (80, 64, 50), "line": (50, 40, 30), "panel": 0, "sheen": False},
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
    "core": {"emit": 150},
    "orb": {"kind": "planet", "planet": "saturn", "bevel": False, "outline": False, "radius": 1.45,
            "vary": 0},
    "face": {"kind": "armor", "base": (236, 226, 204), "panel": 0, "line": (96, 80, 60)},
    "rivet_d": {"kind": "trim", "base": (120, 84, 50), "light": (196, 150, 100),
                "dark": (70, 46, 28), "line": (40, 26, 14)},
}

# ===========================================================================
#  部位アニメ（Molang）。回る部品は v.astro_spin × 角速度（空中・疾走で速く進む累積の位相）、
#  揺れは v.astro_t。重み（v.astro_air / v.astro_run）は振れ幅だけに掛ける。`_r` は左へ自動で鏡映
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # 大環: ゆっくり回り、傾きがかすかに歳差運動する。衛星は環とは別の速さで環の上を巡る
        "fx_spin_ring": {"rotation": [0, "v.astro_spin * 20.0", 0]},
        "fx_spin_moons": {"rotation": [0, "-v.astro_spin * 34.0", 0]},
        "extra_ring": {"rotation": ["math.sin(v.astro_t * 30.0) * 1.5", 0,
                                    "math.cos(v.astro_t * 30.0) * 1.5"],
                       "position": [0, "math.sin(v.astro_t * 60.0) * 0.25", 0]},
        # 冠の光輪（逆回り）と頭頂の宝珠の環
        "fx_spin_halo": {"rotation": [0, "-v.astro_spin * 40.0", 0]},
        "fx_spin_orb": {"rotation": [0, "v.astro_spin * 90.0", 0]},
        "extra_halo": {"position": [0, "math.sin(v.astro_t * 90.0) * 0.12", 0]},
        # 肩の文字盤: 外から見て時計回り（左は鏡に映るので逆向きを書く）。時針 15°/秒・分針 180°/秒
        "fx_spin_hour_r": {"rotation": ["v.astro_spin * 15.0", 0, 0]},
        "fx_spin_min_r": {"rotation": ["v.astro_spin * 180.0", 0, 0]},
        "fx_spin_hour_l": {"rotation": ["-v.astro_spin * 15.0", 0, 0]},
        "fx_spin_min_l": {"rotation": ["-v.astro_spin * 180.0", 0, 0]},
        # 背中の文字盤と、その外を逆に回る光の輪
        "fx_spin_bhour": {"rotation": [0, 0, "-v.astro_spin * 15.0"]},
        "fx_spin_bmin": {"rotation": [0, 0, "-v.astro_spin * 180.0"]},
        "fx_spin_bring": {"rotation": [0, 0, "v.astro_spin * 30.0"]},
        # 草摺と法衣の裾のかすかな揺れ
        "extra_tasset_r": {"rotation": ["math.sin(v.astro_t * 90.0) * 1.0", 0,
                                        "math.sin(v.astro_t * 60.0) * 0.8"]},
        "extra_robe_r": {"rotation": ["1.5 + math.sin(v.astro_t * 90.0) * 1.2", 0, 0]},
        "extra_robe2_r": {"rotation": ["2.0 + math.sin(v.astro_t * 90.0 - 60.0) * 2.0", 0, 0]},
    },
    "thrust": {
        # 空中: 環が水平に近づいて少し浮き、光輪が持ち上がる。草摺と裾が後ろへなびく
        "extra_ring": {"rotation": ["-v.astro_air * 6.0", 0, "v.astro_air * 8.0"],
                       "position": [0, "v.astro_air * 1.0", 0]},
        "extra_halo": {"position": [0, "v.astro_air * 0.5", 0]},
        "extra_tasset_r": {"rotation": ["v.astro_air * 16.0", 0,
                                        "v.astro_air * (5.0 + math.sin(v.astro_t * 720.0) * 2.0)"]},
        "extra_robe_r": {"rotation": ["v.astro_air * 14.0", 0, 0]},
        "extra_robe2_r": {"rotation": ["v.astro_air * (10.0 + math.sin(v.astro_t * 720.0) * 4.0)",
                                       0, 0]},
    },
    "sprint": {
        # 疾走: 環が後ろへ傾き、草摺と裾が後ろへ流れる
        "extra_ring": {"rotation": ["-v.astro_run * 10.0", 0, 0]},
        "extra_tasset_r": {"rotation": ["v.astro_run * (12.0 + math.sin(v.astro_t * 900.0) * 3.0)",
                                        0, "v.astro_run * 4.0"]},
        "extra_robe_r": {"rotation": ["v.astro_run * 22.0", 0, 0]},
        "extra_robe2_r": {"rotation": ["v.astro_run * (12.0 + math.sin(v.astro_t * 900.0) * 5.0)",
                                       0, 0]},
    },
}


# ===========================================================================
#  ローカルの補助
# ===========================================================================
def _grp(bone, parts, rot_=None, centre=(0.0, 0.0, 0.0)):
    """部品の組 [(中心, 大きさ, 局所の回転行列, 塗り)] を、組ごと rot_（統合版の角度）で centre まわりに回して置く。"""
    G = _rot(*rot_) if rot_ is not None and any(abs(a) > 1e-6 for a in rot_) else np.eye(3)
    P = np.asarray(centre, float)
    return [mat_cube(bone, tuple(G @ (np.asarray(c, float) - P) + P), sz, st, G @ R)
            for c, sz, R, st in parts]


_BASIS = {
    "z": np.eye(3),                                                           # 法線 Z（正面向き）
    "x": np.column_stack([(0, 0, 1), (0, 1, 0), (-1, 0, 0)]).astype(float),   # 法線 X（横向き）
    "y": np.column_stack([(1, 0, 0), (0, 0, 1), (0, -1, 0)]).astype(float),   # 法線 Y（水平）
}
FACE_AXIS = {"north": "z", "south": "z", "east": "x", "west": "x", "up": "y", "down": "y"}


def hex_plate(bone, centre, R, depth, style, axis="z", rot_=None, pointy=False, step=0.08):
    """塗りつぶした正六角形（3 枚の箱を 60° ずつ回して重ねる）。R は頂点までの半径。
    面が同じ平面に重ならないよう、厚みを step ずつ変える。"""
    B = _BASIS[axis]
    parts = []
    for k, a in enumerate((0, 60, -60)):
        a2 = a + (30 if pointy else 0)
        parts.append((centre, (R, R * SQ3, depth + step * k), B @ _rot(0, 0, a2), style))
    return _grp(bone, parts, rot_, centre)


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
    return _grp(bone, parts, rot_, centre)


def hex_on(bone, cube, face, a, b, R, depth, style, lift=0.0, sink=0.05, pointy=False, step=0.06):
    """傾いた板 cube の面 face の (a, b) に、同じ傾きで六角形を貼る。戻り値: 一番薄い板の前面の点。"""
    pt, n = surface(cube, face, a, b)
    c = pt + n * (lift + depth / 2 - sink)
    hex_plate(bone, tuple(c), R, depth, style, axis=FACE_AXIS[face], rot_=cube.rotation,
              pointy=pointy, step=step)
    return c + n * depth / 2


def dial(bone, centre, r, axis, facing, rim="gold", face="dial", tick="gold", gem="gem_accent",
         n_ticks=12, tick_size=(0.16, 0.36, 0.16), big_size=(0.24, 0.56, 0.18)):
    """時計の文字盤: 金の縁（八角）→ アイボリーの盤 → 目盛り（3 時ごとに大きく）→ 紫の軸石。
    axis の向きの円盤で、facing（-1 / +1）の側を向く。centre は盤の面の中心。"""
    i = {"x": 0, "y": 1, "z": 2}[axis]
    e = np.zeros(3)
    e[i] = facing
    c = np.asarray(centre, float)
    out = []
    out += octa(bone, tuple(c - e * 0.2), 2 * r + 0.36, 0.34, rim, axis=axis)
    out += octa(bone, tuple(c - e * 0.04), 2 * r, 0.26, face, axis=axis)
    tc = tuple(c + e * 0.07)
    for k in range(n_ticks):
        a = k * 360.0 / n_ticks
        if k % (n_ticks // 4) == 0:
            out += ring(bone, tc, r - 0.12 - (big_size[1] - tick_size[1]) / 2, 1, big_size, tick,
                        axis=axis, phase=a)
        else:
            out += ring(bone, tc, r - 0.12, 1, tick_size, tick, axis=axis, phase=a)
    out += octa(bone, tuple(c + e * 0.12), 0.46, 0.26, gem, axis=axis)
    return out


# ===========================================================================
def build_suit(s: Suit):
    s.frame7(skip=("foot", "spine", "chest"))   # サバトン・胸甲・背板・法衣の裾で包む所は省く
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    arms(s)
    hands(s)
    shoulders(s)
    helmet(s)
    great_ring(s)
    halo(s)


# ---------------------------------------------------------------------------
#  サバトン（足首から生える）: 金の殻・アイボリーの甲・重なる爪先の板・尖った金の爪先・褐色の足首の帯
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (LX, 0.16, -1.2), (2.9, 0.32, 6.0), "dark")                            # 靴底
    shell = bevel(b, (LX, 1.0, -0.6), (2.85, 1.4, 4.2), "plate", cut=0.42, axis="z")
    line_on(b, shell[0], "west", (0.1, 0.45), (0.9, 0.45), 0.18, 0.16, "glow")
    rivets(b, shell[0], "west", 2, edge="top", margin=0.26, span=(0.2, 0.62), style="rivet_d",
           size=0.22)
    chamfer(b, (LX, 1.74, -0.35), (2.92, 0.28, 3.3), "band", cut=0.4, axis="y")   # 足首の帯
    # 甲（アイボリー）と爪先の板が三枚重なり、尖った金の爪先で終わる
    ins = rbox(b, (LX, 1.9, -1.95), (2.3, 0.5, 1.9), "plate2", rot=(-30, 0, 0))
    stick(b, ins, "up", 0.5, 0.15, (2.0, GOLD_W, 0.16), "gold", sink=0.05)
    rbox(b, (LX, 1.0, -3.08), (2.6, 0.9, 1.0), "plate2", rot=(-16, 0, 0))
    cbox(b, (LX, 0.62, -3.62), (2.3, 0.3, 0.3), "dark")
    toe = rbox(b, (LX, 0.6, -3.98), (2.25, 0.62, 0.86), "plate", rot=(-24, 0, 0))
    stick(b, toe, "up", 0.5, 0.5, (0.3, 0.8, 0.16), "band", sink=0.05)
    rbox(b, (LX, 0.42, -4.42), (0.95, 0.36, 0.95), "gold", rot=(0, 45, 0))      # 尖った爪先
    # 踵（金）・拍車・噴射口
    cbox(b, (LX, 1.05, 1.35), (2.5, 1.5, 0.9), "plate_b")
    octa(b, (LX, 0.85, 1.95), 1.05, 0.4, "frame", axis="z")
    cbox(b, (LX, 0.85, 2.18), (0.76, 0.76, 0.16), "thruster")
    rbox(b, (LX, 1.75, 1.95), (0.36, 0.36, 1.0), "gold", rot=(-20, 0, 0))         # 拍車
    # 外の紫の六角と、足首の外の小さな板（ドラムは見せる）
    rbox(b, (LX - 1.5, 1.0, -0.7), (0.2, 0.75, 0.75), "gold", rot=(45, 0, 0))
    rbox(b, (LX - 1.58, 1.0, -0.7), (0.2, 0.46, 0.46), "gem_accent", rot=(45, 0, 0))
    rbox(b, (LX - 1.52, 2.6, 0.75), (0.32, 1.1, 1.3), "plate2", rot=(0, 0, -6))


# ---------------------------------------------------------------------------
#  脚（腿・膝・脛）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前のアイボリーの板（上に金の板・褐色の帯・氷青の線）・外の細い金の帯。後ろと内側は骨格を見せる
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.85, -1.78), (2.75, 4.6, 0.5), "plate2", top="plate",
                       rot=(-3, 0, 0), inset=0.3, trim="gold", trim_edge="bottom",
                       rivet="rivet_d", n_rivets=3, rivet_edge="top")
    stick(t, fr["top"], "north", 0.5, 0.62, (2.15, 0.36, 0.16), "band", sink=0.05)
    line_on(t, fr["top"], "north", (0.3, 0.1), (0.3, 0.52), 0.18, 0.16, "glow")
    line_on(t, fr["top"], "north", (0.3, 0.52), (0.62, 0.52), 0.18, 0.16, "glow")
    side = rbox(t, (LX - 1.56, 11.4, 0.1), (0.28, 3.4, 2.2), "plate", rot=(0, 0, -2))
    rivets(t, side, "west", 3, edge="bottom", margin=0.3, style="rivet_d", size=0.22)
    bk = rbox(t, (LX, 11.0, 1.58), (2.1, 2.6, 0.38), "plate_b", rot=(4, 0, 0))     # 腿の裏
    vents(t, bk, "south", 2, box=(0.25, 0.3, 0.75, 0.7))
    sensor(t, (LX + 0.75, 13.6, -2.12), 0.26, "glow", "dark")
    # 膝: 金の六角 → アイボリーの六角 → 紫の六角の宝玉。上の尖り・外の小さな翼
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    hex_plate(k, (LX, 8.45, -1.9), 1.32, 0.5, "plate", pointy=True)
    hex_plate(k, (LX, 8.45, -2.2), 0.86, 0.3, "plate2", pointy=True, step=0.04)
    hex_plate(k, (LX, 8.45, -2.38), 0.42, 0.24, "gem_accent", pointy=True, step=0.03)
    rbox(k, (LX, 9.75, -1.82), (1.05, 1.05, 0.45), "plate2", rot=(0, 0, 45))     # 上の尖り
    wg = rbox(k, (LX - 1.38, 8.75, -1.05), (0.28, 1.25, 1.35), "plate", rot=(0, 0, -14))
    mirror_x(k, wg, about=LX)
    piston(k, (LX - 1.58, 10.8, 0.55), (LX - 1.48, 6.4, 0.45), r=0.25, style="frame",
           rod_style="chrome", cap_style="dark")
    # 脛: 前の金の板 + アイボリーの V の稜（氷青の線）、褐色の帯、両脇の板、ふくらはぎの縞と排気口、外のヒレ
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 4.85, -1.45), (2.7, 5.0, 0.5), "plate", rot=(4, 0, 0))
    stick(g, front, "north", 0.5, 0.93, (2.55, 0.36, 0.18), "band", sink=0.05)
    stick(g, front, "north", 0.5, 0.04, (2.55, GOLD_W, 0.18), "gold", sink=0.05)
    keel = rbox(g, (LX - 0.36, 4.95, -1.78), (0.78, 4.0, 0.45), "plate2", rot=(4, 24, 0))
    mirror_x(g, keel, about=LX)
    line_on(g, front, "north", (0.1, 0.16), (0.14, 0.82), 0.18, 0.16, "glow")
    line_on(g, front, "north", (0.9, 0.16), (0.86, 0.82), 0.18, 0.16, "glow")
    rbox(g, (LX, 2.9, -1.86), (0.6, 0.6, 0.3), "gem_accent", rot=(4, 0, 45))
    sd = rbox(g, (LX - 1.42, 4.9, -0.1), (0.42, 4.6, 2.6), "plate2", rot=(0, 0, -4))
    sdr = rivets(g, sd, "west", 3, edge="bottom", margin=0.3, style="gold", size=0.22)
    sdb = stick(g, sd, "west", 0.5, 0.86, (2.4, 0.34, 0.16), "band", sink=0.05)
    rbox(g, (LX + 1.4, 4.9, -0.1), (0.36, 4.4, 2.4), "plate_b", rot=(0, 0, 4))
    calf = rbox(g, (LX, 6.05, 1.6), (2.3, 2.5, 0.45), "belted", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.2, 0.2, 0.8, 0.8))
    fin = rbox(g, (LX - 1.8, 5.9, 0.85), (0.3, 2.6, 1.3), "plate", rot=(-14, 0, -8))
    line_on(g, fin, "west", (0.2, 0.25), (0.8, 0.8), 0.16, 0.16, "band")


# ---------------------------------------------------------------------------
#  腰（褐色の帯のベルト・六角の留め金・前垂れ・腰の脇の板・長い草摺・法衣の裾）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    belt = chamfer(w, (0, 16.95, 0.12), (6.6, 0.9, 4.5), "band", cut=0.4, axis="y")
    for y in (17.46, 16.44):
        chamfer(w, (0, y, 0.12), (6.7, 0.24, 4.6), "gold", cut=0.44, axis="y")
    bl = rivets(w, belt[0], "north", 2, edge="bottom", margin=0.45, span=(0.08, 0.26),
                style="gold", size=0.22)
    mirror_x(w, bl)
    # 留め金: 金の六角 + 土星の模様の六角
    hex_plate(w, (0, 16.95, -2.4), 0.95, 0.36, "gold")
    rbox(w, (0, 16.95, -2.62), (0.82, 0.82, 0.24), "planet", rot=(0, 0, 45))
    # 前垂れ（細いアイボリーの板。腿の前を隠さない幅）+ 尖った先
    fp = rbox(w, (0, 15.0, -2.05), (1.8, 2.6, 0.45), "plate2", rot=(-8, 0, 0))
    stick(w, fp, "north", 0.5, 0.92, (1.6, GOLD_W, 0.16), "gold", sink=0.05)
    stick(w, fp, "north", 0.5, 0.62, (1.6, 0.34, 0.16), "band", sink=0.05)
    rbox(w, (0, 13.75, -1.88), (1.2, 1.2, 0.42), "plate2", rot=(-8, 0, 45))
    rbox(w, (0, 14.55, -2.36), (0.5, 0.5, 0.24), "gem_accent", rot=(-8, 0, 45))
    # 腰の脇の金の板（股関節の前を覆う）
    hp = rbox(w, (-2.4, 15.85, -1.95), (2.1, 1.3, 0.45), "plate", rot=(-8, 14, 4))
    hpr = rivets(w, hp, "north", 2, edge="top", margin=0.28, span=(0.25, 0.75), style="rivet_d",
                 size=0.22)
    mirror_x(w, hp, hpr)
    # 後ろの腰板（法衣の裾の付け根）
    rbox(w, (0, 16.0, 2.35), (4.2, 1.4, 0.4), "plate_b", rot=(10, 0, 0))
    # 草摺: 腰の横の蝶番（環の発振器 = 氷青のレンズ）から、短い上の板 → 長く尖った刃（extra。揺れる）
    ts = s.part("waist", "tasset_r", w, pivot=(-3.55, 16.6, 0.0), rotation=(0, 0, 4))
    up = layered_plate(ts, (-3.86, 15.2, 0.05), (0.4, 2.7, 3.3), "plate", top="plate2",
                       face="west", inset=0.32, trim="gold", trim_edge="bottom",
                       rivet="gold", n_rivets=2, rivet_edge="top")
    stick(ts, up["top"], "west", 0.5, 0.42, (2.6, 0.34, 0.16), "band", sink=0.05)
    octa(ts, (-3.68, 16.35, 0.05), 0.95, 0.6, "frame", axis="x")
    cbox(ts, (-4.04, 16.35, 0.05), (0.16, 0.36, 0.36), "glow")
    tb = s.part("extra", "tasset_r", ts, pivot=(-3.9, 13.95, 0.05), rotation=(0, 0, 3))
    blade = rbox(tb, (-3.92, 11.15, 0.12), (0.38, 5.6, 2.9), "plate")
    tp = stick(tb, blade, "west", 0.5, 0.5, (2.3, 5.0, 0.18), "plate2", sink=0.05)
    stick(tb, tp, "west", 0.5, 0.8, (2.3, 0.4, 0.16), "band", sink=0.05)
    stick(tb, tp, "west", 0.5, 0.3, (2.3, 0.3, 0.16), "band", sink=0.05)
    hex_on(tb, tp, "west", 0.5, 0.55, 0.62, 0.18, "gold", pointy=True)
    stick(tb, tp, "west", 0.5, 0.55, (0.5, 0.5, 0.3), "gem_accent", spin=45, sink=0.02)
    rivets(tb, tp, "west", 2, line=((0.22, 0.8), (0.78, 0.8)), style="gold", size=0.2)
    for a in (0.04, 0.96):
        stick(tb, blade, "west", a, 0.5, (GOLD_W, 5.4, 0.16), "gold", sink=0.04)
    # 剣先（菱形の下半分が出る）と先の紫の小さな宝玉
    tip = rbox(tb, (-3.92, 8.35, 0.12), (0.36, 2.05, 2.05), "plate", rot=(45, 0, 0))
    stick(tb, tip, "west", 0.5, 0.5, (0.9, 0.9, 0.16), "plate2", sink=0.04)
    rbox(tb, (-4.1, 7.55, 0.12), (0.2, 0.42, 0.42), "gem_accent", rot=(45, 0, 0))
    # 法衣の裾（腰の後ろから、二段で垂れる。extra で揺れる・計測しない）
    rb = s.part("extra", "robe_r", w, pivot=(-1.7, 16.3, 2.75), rotation=(5, 0, 3))
    p1 = rbox(rb, (-1.78, 14.85, 2.95), (2.8, 3.0, 0.34), "plate")
    stick(rb, p1, "south", 0.5, 0.95, (2.8, GOLD_W, 0.16), "gold", sink=0.04)
    stick(rb, p1, "south", 0.5, 0.45, (2.6, 0.4, 0.16), "band", sink=0.04)
    rivets(rb, p1, "south", 2, edge="bottom", margin=0.22, style="rivet_d", size=0.22)
    r2 = s.part("extra", "robe2_r", rb, pivot=(-1.8, 13.5, 2.95), rotation=(4, 0, 0))
    p2 = rbox(r2, (-1.82, 11.35, 3.0), (2.9, 4.4, 0.32), "plate2")
    for b_ in (0.86, 0.36):
        stick(r2, p2, "south", 0.5, b_, (2.9, 0.42, 0.16), "band", sink=0.04)
    for a in (0.04, 0.96):
        stick(r2, p2, "south", a, 0.5, (GOLD_W, 4.2, 0.16), "gold", sink=0.04)
    stick(r2, p2, "south", 0.5, 0.6, (0.8, 0.8, 0.18), "gold", spin=45, sink=0.03)
    stick(r2, p2, "south", 0.5, 0.6, (0.5, 0.5, 0.3), "gem_accent", spin=45, sink=0.02)
    pt = rbox(r2, (-1.82, 9.15, 3.0), (2.05, 2.05, 0.3), "plate2", rot=(0, 0, 45))
    stick(r2, pt, "south", 0.5, 0.5, (1.0, 1.0, 0.16), "plate", sink=0.04)


# ---------------------------------------------------------------------------
#  胴（胸郭・金の V の胸板・六角形の胸と星核・立ち襟・脇の排気口・縞の腹）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.25, 0.05), (9.0, 3.5, 4.9), "plate2", cut=0.8, axis="y")   # 上が広い
    chamfer(c, (0, 21.55, 0.0), (7.0, 2.2, 4.5), "plate_b", cut=0.7, axis="y")
    sl = rbox(c, (-3.92, 22.15, 0.05), (0.5, 2.9, 3.9), "plate", rot=(0, 0, -24))   # 脇の斜面
    sls = stick(c, sl, "west", 0.5, 0.5, (3.0, 0.34, 0.16), "band", sink=0.05)
    mirror_x(c, sl, sls)
    # 金の V の胸板: 外へ開き、内側の端が前へ、下辺が中央へ（褐色の帯・氷青の線・リベット）
    pec = rbox(c, (-2.65, 24.15, -2.62), (3.5, 2.5, 0.55), "plate", rot=(6, 17, 9))
    pb = stick(c, pec, "north", 0.5, 0.8, (3.3, 0.4, 0.18), "band", sink=0.05)
    gl = [line_on(c, pec, "north", ab0, ab1, 0.18, 0.16, "glow") for ab0, ab1 in (
        ((0.94, 0.42), (0.55, 0.42)), ((0.55, 0.42), (0.3, 0.2)))]
    pr = rivets(c, pec, "north", 3, edge="bottom", margin=0.24, span=(0.15, 0.6), style="rivet_d",
                size=0.22)
    low = rbox(c, (-2.0, 21.95, -2.4), (3.2, 1.45, 0.5), "belted", rot=(-8, 12, 12))
    lr = rivets(c, low, "north", 2, edge="bottom", margin=0.26, span=(0.35, 0.75), style="gold",
                size=0.2)
    mirror_x(c, pec, pb, gl, pr, low, lr)
    # 六角形の胸（北極の六角渦）: 褐色の盤 → 金の枠 → 光る内枠 → 頂点の宝玉 → 星核と小さな環
    hx = s.part("torso", "hexagon", c, pivot=(0, 23.0, -2.9))
    C = (0, 23.0, -2.85)
    hex_plate(hx, C, 1.9, 0.5, "band_d")
    hex_ring(hx, (0, 23.0, -3.12), 1.95, 0.36, 0.24, "gold")
    hex_ring(hx, (0, 23.0, -3.12), 1.3, 0.16, 0.2, "glow")
    for k in range(6):
        a = math.radians(60 * k)
        rbox(hx, (2.0 * math.cos(a), 23.0 + 2.0 * math.sin(a), -3.3), (0.36, 0.36, 0.2),
             "gem_accent", rot=(0, 0, 45))
    cbox(hx, (0, 23.0, -3.22), (1.2, 1.2, 0.56), "core")
    rbox(hx, (0, 23.0, -3.2), (1.06, 1.06, 0.52), "core", rot=(0, 0, 45))
    gc = s.fx("glow", "core", hx, pivot=(0, 23.0, -3.55))
    rbox(gc, (0, 23.0, -3.56), (2.8, 0.24, 0.18), "ring_f", rot=(0, 0, -22))
    # 胸の上の中央の稜（金）と、六角の下の留め
    kl = rbox(c, (0, 25.3, -2.62), (1.0, 1.25, 0.45), "plate", rot=(-12, 0, 0))
    stick(c, kl, "north", 0.5, 0.5, (0.3, 0.9, 0.16), "band", sink=0.06)
    cbox(c, (0, 20.95, -2.35), (1.3, 0.5, 0.4), "gold")
    # 立ち襟: 首の両脇の金の板（アイボリーの上面・金の縁）と、首の後ろに立つアイボリーの高い襟
    col = rbox(c, (-1.75, 26.25, 0.35), (1.4, 1.1, 3.6), "plate", rot=(0, 0, -24))
    colt = stick(c, col, "up", 0.5, 0.5, (1.1, 3.3, 0.2), "plate2", sink=0.06)
    colg = stick(c, col, "west", 0.5, 0.06, (3.4, GOLD_W, 0.18), "gold", sink=0.05)
    cf = rbox(c, (-0.95, 25.95, -1.95), (1.6, 0.9, 0.45), "plate2", rot=(-20, 30, -10))
    hc = rbox(c, (-1.25, 26.55, 1.85), (1.7, 1.5, 0.38), "plate2", rot=(-18, -28, 0))
    hcg = stick(c, hc, "south", 0.5, 0.92, (1.6, GOLD_W, 0.16), "gold", sink=0.04)
    mirror_x(c, col, colt, colg, cf, hc, hcg)
    rbox(c, (0, 26.4, 2.18), (1.3, 1.3, 0.36), "plate", rot=(-18, 0, 0))
    sensor(c, (-1.4, 25.25, -2.6), 0.24, "glow", "dark")
    sensor(c, (1.4, 25.25, -2.6), 0.24, "glow", "dark")
    # 肩の付け根（肩当ての下）と脇の排気口
    yk = rbox(c, (-3.95, 25.95, 0.0), (2.0, 0.55, 3.5), "plate_b", rot=(0, 0, -8))
    sv = cbox(c, (-4.38, 23.75, 0.35), (0.4, 2.0, 2.4), "plate_b")
    svv = vents(c, sv, "west", 1, box=(0.2, 0.3, 0.8, 0.7), w=0.5)
    mirror_x(c, yk, sv, svv)
    rivets(c, up[1], "south", 4, edge="top", margin=0.35, span=(0.12, 0.88), style="gold", size=0.22)
    # 腹: 下ほど細い三枚の板（アイボリー・褐色・アイボリー = 土星の縞）と中央の溝
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))
    for i, (y, ww, st) in enumerate(((19.95, 3.9, "plate2"), (18.95, 3.5, "band"),
                                     (17.95, 3.1, "plate2"))):
        p = rbox(ab, (0, y, -1.98 + i * 0.05), (ww, 0.82, 0.48), st, rot=(-8, 0, 0))
        stick(ab, p, "north", 0.5, 0.5, (0.18, 0.6, 0.16), "dark", sink=0.08)
        r_ = rivets(ab, p, "north", 1, line=((0.12, 0.5), (0.12, 0.5)), size=0.2,
                    style="gold" if st == "band" else "rivet_d")
        mirror_x(ab, r_)
    cbox(ab, (0, 18.9, 2.08), (2.2, 2.6, 0.45), "plate_b")                          # 背の腰板


# ---------------------------------------------------------------------------
#  背中（金の背板・大きな文字盤と回る針・光の輪・双発スラスター・ホース・脇のヒレ）
# ---------------------------------------------------------------------------
BACK_DIAL = (0.0, 22.45, 4.5)


def back(s):
    bk = s.part("back", "pack", "body")
    pk = bevel(bk, (0, 22.4, 3.35), (4.6, 5.0, 1.6), "plate", cut=0.6, axis="z")
    lid = rbox(bk, (0, 25.15, 3.05), (4.0, 0.8, 1.8), "plate2", rot=(20, 0, 0))
    rivets(bk, lid, "up", 4, edge="bottom", margin=0.3, style="gold", size=0.22)
    rivets(bk, pk[0], "south", 8, edge="border", margin=0.24, style="rivet_d", size=0.22)
    # 文字盤（金の縁・アイボリーの盤・目盛り・紫の軸石）
    dial(bk, BACK_DIAL, 1.85, "z", 1, tick_size=(0.18, 0.42, 0.16), big_size=(0.28, 0.66, 0.18))
    sr = s.fx("spin", "bring", bk, pivot=BACK_DIAL)
    ring(sr, (0, BACK_DIAL[1], 4.42), 2.45, 12, (0, 0.26, 0.26), "ring_b", axis="z",
         styles=["ring_b", "ring_f"])
    hh = s.fx("spin", "bhour", bk, pivot=BACK_DIAL)
    cbox(hh, (0, BACK_DIAL[1] + 0.52, 4.86), (0.3, 1.04, 0.16), "hand")
    mh = s.fx("spin", "bmin", bk, pivot=BACK_DIAL)
    cbox(mh, (0, BACK_DIAL[1] + 0.74, 4.94), (0.2, 1.48, 0.16), "hand")
    # 背板の両脇: 肩甲骨の金の板（褐色の帯・氷青の線・リベット）
    sc = rbox(bk, (-3.3, 23.6, 2.62), (2.1, 2.7, 0.4), "plate", rot=(8, -16, 0))
    scb = stick(bk, sc, "south", 0.5, 0.78, (2.0, 0.42, 0.16), "band", sink=0.05)
    scl = line_on(bk, scb, "south", (0.1, 0.5), (0.9, 0.5), 0.16, 0.16, "glow", sink=0.06)
    scr = rivets(bk, sc, "south", 2, edge="bottom", margin=0.28, span=(0.25, 0.75), size=0.22,
                 style="gold")
    mirror_x(bk, sc, scb, scl, scr)
    # ホース: 背板の下から腰の両脇へ（垂れる蛇腹）
    hs = cable(bk, [(-1.3, 20.1, 2.9), (-2.45, 17.7, 2.1)], 0.26, "dark", sag=0.25,
               rib="frame_lt", rib_every=3)
    mirror_x(bk, hs)
    # スラスター（右。下後ろへ向け、少し外へ開く）: 胴・褐色の帯・広がったベル・光る縁の輪・噴射口・炎
    th = s.part("back", "thruster_r", bk, pivot=(-1.65, 19.9, 3.85), rotation=(24, 0, 6))
    octa(th, (-1.65, 19.0, 3.85), 1.45, 1.8, "plate2", axis="y")
    octa(th, (-1.65, 19.6, 3.85), 1.62, 0.3, "band", axis="y")
    octa(th, (-1.65, 17.75, 3.85), 1.8, 0.8, "frame", axis="y")
    ring(th, (-1.65, 17.33, 3.85), 0.68, 4, (0, 0.2, 0.22), "glow", axis="y", phase=45.0)
    cbox(th, (-1.65, 17.32, 3.85), (1.25, 0.16, 1.25), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.65, 17.3, 3.85))
    taper(fx, (-1.65, 17.3, 3.85), (-1.65, 11.6, 3.85), 1.5, 0.32, 2, "flame")
    taper(fx, (-1.65, 17.25, 3.85), (-1.65, 14.2, 3.85), 0.72, 0.2, 2, "flame_core", round_=False)


# ---------------------------------------------------------------------------
#  腕（二の腕・肘・篭手）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.3, 21.35, 0.0), (0.42, 3.2, 2.4), "plate2", rot=(0, 0, 3))
    stick(ua, op, "west", 0.5, 0.62, (2.2, 0.36, 0.16), "band", sink=0.05)
    rbox(ua, (X - 1.56, 21.0, 0.0), (0.2, 0.42, 0.42), "gem_accent", rot=(45, 0, 3))
    rivets(ua, op, "west", 2, edge="bottom", margin=0.28, span=(0.3, 0.7), style="gold", size=0.2)
    upf = rbox(ua, (X + 0.05, 21.4, -1.36), (2.2, 2.9, 0.42), "plate", rot=(-3, 0, 0))
    stick(ua, upf, "north", 0.5, 0.5, (0.5, 2.4, 0.16), "plate2", sink=0.06)
    sensor(ua, (X + 0.05, 22.55, -1.64), 0.22, "glow", "dark")
    rbox(ua, (X + 0.05, 21.7, 1.34), (2.0, 2.3, 0.4), "plate_b", rot=(3, 0, 0))
    octa(ua, (X, 19.72, 0.02), 2.86, 0.32, "gold", axis="y")                       # 腕輪
    octa(ua, (X, 20.08, 0.02), 2.78, 0.3, "band", axis="y")
    # 肘当て（後ろ）: 金の面取り・紫の六角・リベット
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    cop = bevel(el, (A.ELBOW[0], 18.55, 1.62), (2.1, 1.9, 0.6), "plate", cut=0.3, axis="z")
    hex_plate(el, (A.ELBOW[0], 18.6, 1.98), 0.5, 0.2, "gold", pointy=True)
    rbox(el, (A.ELBOW[0], 18.6, 2.12), (0.38, 0.38, 0.2), "gem_accent", rot=(0, 0, 45))
    rivets(el, cop[0], "south", 2, edge="bottom", margin=0.26, span=(0.2, 0.8), style="rivet_d",
           size=0.2)
    # 篭手: 金の上段 → 褐色の帯 → 手首へ開くアイボリーの下段。外の金の板（紫の六角）・前の板・金の袖口
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX_ = A.FOREARM_X
    chamfer(fa, (FX_, 17.25, 0.0), (2.8, 1.7, 2.9), "plate", cut=0.45, axis="y")
    octa(fa, (FX_, 16.3, 0.0), 2.95, 0.3, "band", axis="y")
    lo = bevel(fa, (FX_ - 0.04, 15.45, 0.0), (2.95, 1.45, 3.1), "plate2", cut=0.48, axis="y")
    ob = rbox(fa, (FX_ - 1.66, 16.25, 0.0), (0.4, 3.0, 2.5), "plate", rot=(0, 0, 5))
    hex_on(fa, ob, "west", 0.5, 0.45, 0.72, 0.2, "gold", pointy=True)
    stick(fa, ob, "west", 0.5, 0.45, (0.46, 0.46, 0.32), "gem_accent", spin=45, sink=0.02)
    stick(fa, ob, "west", 0.5, 0.9, (2.3, 0.3, 0.16), "band", sink=0.05)
    fv = rbox(fa, (FX_ - 0.02, 16.45, -1.6), (2.0, 2.2, 0.35), "plate2", rot=(-5, 0, 0))
    stick(fa, fv, "north", 0.5, 0.55, (1.8, 0.34, 0.16), "band", sink=0.06)
    line_on(fa, fv, "north", (0.5, 0.1), (0.5, 0.4), 0.16, 0.16, "gold")
    rivets(fa, fv, "north", 2, edge="top", margin=0.2, span=(0.12, 0.88), style="gold", size=0.2)
    chamfer(fa, (FX_ - 0.04, 14.7, 0.0), (3.06, 0.32, 3.2), "gold", cut=0.4, axis="y")  # 袖口
    sensor(fa, (FX_ + 0.05, 15.5, 1.66), 0.24, "glow", "dark", facing=1)


def hands(s):
    """手の甲のアイボリーの板と紫の宝玉、指の甲当て（4 本の基節）、親指の当て。指そのものは frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.42, 13.62, 0.0), (0.36, 1.7, 2.3), "plate2", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.55, (0.5, 0.5, 0.18), "gem_accent", spin=45, sink=0.05)
    stick(h, hb, "west", 0.5, 0.9, (2.1, GOLD_W, 0.16), "gold", sink=0.05)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        n = (-0.81, -0.58, 0.0)
        o = 0.34
        beam(h, (p0[0] + n[0] * o, p0[1] + n[1] * o, zf), (p1[0] + n[0] * o, p1[1] + n[1] * o, zf),
             0.54, 0.22, "plate")
    rbox(h, (-5.62, 13.55, -1.72), (0.62, 0.9, 0.22), "plate", rot=(0, 0, -36))


# ---------------------------------------------------------------------------
#  肩（丸い三層の肩当て・外の文字盤と回る針・垂れる板）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    # 丸いドーム（正面から見て角を落とす）・アイボリーの冠板・褐色の縞・金のリベット
    dome = bevel(p, (-6.95, 25.6, 0.0), (3.4, 2.2, 4.6), "plate", cut=0.8, axis="z",
                 rot=(0, 0, -16))
    top = stick(p, dome[0], "up", 0.5, 0.5, (1.7, 4.3, 0.28), "plate2", sink=0.08)
    stick(p, top, "up", 0.5, 0.5, (0.42, 4.4, 0.16), "band", sink=0.06)              # 中央の縞
    rivets(p, top, "up", 4, edge="border", margin=0.2, size=0.22, style="gold")
    cbox(p, (-6.4, 24.25, 0.0), (2.2, 0.5, 3.8), "dark")                              # 裏の縁
    # 外へ下る三段の板: アイボリーの屋根板（金の縁）→ 金の文字盤の台 → アイボリーの短い垂れ
    la = rbox(p, (-8.45, 24.85, 0.0), (0.4, 1.7, 4.8), "plate2", rot=(0, 0, 46))
    stick(p, la, "west", 0.5, 0.08, (4.6, GOLD_W, 0.16), "gold", sink=0.05)
    rivets(p, la, "west", 3, edge="top", margin=0.24, size=0.2, style="rivet_d")
    l1 = rbox(p, (-8.62, 23.25, 0.0), (0.44, 2.1, 4.3), "plate", rot=(0, 0, 12))
    stick(p, l1, "west", 0.5, 0.06, (4.1, 0.3, 0.16), "band", sink=0.05)
    rivets(p, l1, "west", 2, line=((0.08, 0.2), (0.08, 0.8)), size=0.2, style="rivet_d")
    l2 = rbox(p, (-8.72, 21.55, 0.05), (0.42, 1.2, 3.7), "plate2", rot=(0, 0, 9))
    stick(p, l2, "west", 0.5, 0.12, (3.5, GOLD_W, 0.16), "gold", sink=0.05)
    rivets(p, l2, "west", 2, edge="top", margin=0.22, span=(0.25, 0.75), size=0.2, style="gold")
    # 前後の小さな板とセンサー、後ろのヒレ
    fr = rbox(p, (-7.05, 24.5, -2.36), (2.4, 1.2, 0.38), "plate_b", rot=(-14, 0, -8))
    sensor(p, (-7.45, 24.5, -2.6), 0.24, "glow", "dark")
    rbox(p, (-7.05, 24.6, 2.36), (2.4, 1.2, 0.38), "plate_b", rot=(14, 0, -8))
    rbox(p, (-6.95, 26.85, 1.95), (0.4, 1.1, 1.5), "plate2", rot=(-25, 0, -10))
    # 文字盤（外 -X を向く。台の板と同じ傾き）: 縁・盤・目盛り・軸石と、回る時針・分針
    D = (-9.22, 23.25, 0.0)
    dl = s.part("shoulders", "dial_r", p, pivot=(-8.62, 23.25, 0.0), rotation=(0, 0, 12))
    dial(dl, D, 1.0, "x", -1, n_ticks=8, tick_size=(0.16, 0.3, 0.16), big_size=(0.22, 0.44, 0.16))
    hr = s.fx("spin", "hour_r", dl, pivot=D)
    cbox(hr, (D[0] - 0.24, D[1] + 0.32, 0.0), (0.16, 0.64, 0.24), "hand")
    mn = s.fx("spin", "min_r", dl, pivot=D)
    cbox(mn, (D[0] - 0.3, D[1] + 0.44, 0.0), (0.16, 0.88, 0.16), "hand")


# ---------------------------------------------------------------------------
#  兜（アイボリーのドーム・褐色の額環と金の縁・金の眉庇・面頬・頬当て・耳の文字盤・後頭部・しころ）
#  冠（金の五本の尖り）と頭頂の土星の宝珠（飾り）、バイザー
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.75, HZ + 0.3), (4.4, 1.9, 4.8), "plate2", cut=0.6, axis="z")
    bevel(hm, (0, 31.65, HZ + 0.4), (3.5, 0.8, 4.2), "plate2", cut=0.32, axis="z")  # 頭頂
    cbox(hm, (0, 32.0, HZ + 0.45), (0.7, 0.3, 3.6), "plate")                        # 中央の稜
    # 額環（褐色）と金の縁、正面の六角の宝玉・両脇の菱形の宝玉
    chamfer(hm, (0, 30.62, HZ + 0.25), (4.62, 0.62, 5.0), "band", cut=0.5, axis="y")
    for y in (31.0, 30.24):
        chamfer(hm, (0, y, HZ + 0.25), (4.7, 0.24, 5.08), "gold", cut=0.52, axis="y")
    hex_plate(hm, (0, 30.62, HZ - 2.3), 0.48, 0.2, "gold", pointy=True)
    hex_plate(hm, (0, 30.62, HZ - 2.4), 0.3, 0.2, "gem_accent", pointy=True, step=0.03)
    gm = rbox(hm, (-1.25, 30.62, HZ - 2.3), (0.34, 0.34, 0.2), "gem_accent", rot=(0, 0, 45))
    gs = rbox(hm, (-2.36, 30.62, HZ + 0.25), (0.2, 0.34, 0.34), "gem_accent", rot=(45, 0, 0))
    # 金の眉庇（中央で下がる V）とこめかみ
    br = rbox(hm, (-1.0, 29.95, HZ - 2.36), (2.1, 0.5, 0.5), "plate", rot=(-8, 8, 10))
    sd = cbox(hm, (-2.12, 29.0, HZ + 0.65), (0.42, 2.1, 3.4), "plate")
    sdr = rivets(hm, sd, "west", 2, edge="bottom", margin=0.28, span=(0.25, 0.75), size=0.2,
                 style="rivet_d")
    # 頬当て（金）と褐色の縁
    ck = rbox(hm, (-1.78, 28.4, HZ - 1.15), (0.5, 2.0, 2.3), "plate", rot=(0, 20, -10))
    ckg = stick(hm, ck, "west", 0.06, 0.5, (0.22, 1.8, 0.16), "band", sink=0.05)
    # 耳の小さな文字盤（目盛り 4 つ・止まった針）
    ear = octa(hm, (-2.34, 29.1, HZ + 0.6), 1.5, 0.3, "gold", axis="x")
    eard = octa(hm, (-2.45, 29.1, HZ + 0.6), 1.2, 0.24, "dial", axis="x")
    earh = cbox(hm, (-2.58, 29.3, HZ + 0.6), (0.16, 0.42, 0.16), "hand")
    mirror_x(hm, gm, gs, br, sd, sdr, ck, ckg, ear, eard, earh)
    # 面頬（アイボリー）: 中央の稜へ折れた V の板・尖った顎・中央の稜
    fc = rbox(hm, (-0.62, 28.45, HZ - 2.2), (1.3, 1.25, 0.42), "face", rot=(8, 26, 0))
    ch = rbox(hm, (-0.45, 27.75, HZ - 1.98), (1.0, 0.7, 0.48), "face", rot=(0, 26, -22))
    fl = line_on(hm, fc, "north", (0.2, 0.3), (0.8, 0.3), 0.16, 0.16, "band")
    mirror_x(hm, fc, ch, fl)
    cbox(hm, (0, 28.5, HZ - 2.5), (0.3, 1.2, 0.3), "plate")
    # 後頭部（金・排気口）としころ（褐色と金の段）
    bh = cbox(hm, (0, 29.15, HZ + 2.6), (4.0, 2.3, 0.45), "plate")
    vents(hm, bh, "south", 3, box=(0.3, 0.25, 0.7, 0.65), w=0.18)
    rbox(hm, (0, 31.3, HZ + 2.55), (0.8, 1.5, 0.4), "plate2", rot=(35, 0, 0))
    rbox(hm, (0, 28.05, HZ + 2.62), (3.7, 0.75, 0.45), "band", rot=(22, 0, 0))
    rbox(hm, (0, 27.6, HZ + 2.75), (3.2, 0.6, 0.42), "plate", rot=(32, 0, 0))
    # 冠（飾り）: 額環から立つ五本の金の尖り（正面がいちばん高い）と根元の宝玉
    cr = s.part("helmet", "crown", "head", pivot=(0, 31.0, HZ), ornament=True)
    # 額環の外に、外を向いた薄い菱形の板（上半分が額環の上に立つ）。正面がいちばん大きい
    for (x, z, yaw, sz, y) in ((0.0, -2.62, 0, 1.55, 31.45), (-1.5, -2.6, 0, 1.0, 31.25),
                               (-2.38, -1.35, 60, 1.1, 31.3), (-2.62, 0.75, 90, 1.0, 31.25),
                               (-1.7, 2.55, 150, 0.9, 31.2)):
        Rm = _rot(0, yaw, 0) @ _rot(0, 0, 45)
        pts = [mat_cube(cr, (x, y, HZ + z), (sz, sz, 0.22), "gold", Rm)]
        if x < -0.01:
            mirror_x(cr, pts)
    rbox(cr, (0, 31.45, HZ - 2.78), (0.5, 0.5, 0.18), "gem_accent", rot=(0, 0, 45))
    # 頭頂の土星の宝珠（金の台・縞の球・自分の小さな環が回る）
    orb_c = (0, 33.25, HZ + 0.4)
    octa(cr, (0, 32.3, HZ + 0.4), 0.9, 0.36, "gold", axis="y")
    octa(cr, (0, 32.6, HZ + 0.4), 0.5, 0.36, "band", axis="y")
    cbox(cr, orb_c, (0.95, 0.95, 0.95), "orb")
    rbox(cr, orb_c, (0.85, 0.85, 0.85), "orb", rot=(0, 45, 0))
    ob = s.part("helmet", "orb_ring", cr, pivot=orb_c, rotation=(0, 0, 26), ornament=True)
    osp = s.fx("spin", "orb", ob, pivot=orb_c)
    ring(osp, orb_c, 0.98, 10, (0, 0.3, 0.16), "ring_b", axis="y", styles=["ring_b", "ring_a"])
    # バイザー: 暗い帯の上に、中央で少し下がる氷青の二枚
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 29.45, HZ - 2.3), (3.8, 0.74, 0.3), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.45, HZ - 2.48))
    eye = rbox(fg, (-0.95, 29.48, HZ - 2.48), (1.45, 0.36, 0.18), "visor", rot=(0, 8, -6))
    mirror_x(fg, eye)


# ---------------------------------------------------------------------------
#  大環（腰を斜めに回る土星の環）と、環の上を巡る羊飼い衛星
# ---------------------------------------------------------------------------
RING_C = (0.0, 16.0, 0.2)
RING_TILT = (10, 0, -20)          # 前が少し下がり、左（+X）が上がる（合わせて約 22°）
R_B, R_A, R_F = 9.1, 10.45, 11.35


def great_ring(s):
    rg = s.part("extra", "ring", "body", pivot=RING_C, rotation=RING_TILT)
    sp = s.fx("spin", "ring", rg, pivot=RING_C)
    C = RING_C
    # C 環（暗く細い）・B 環（氷青に光る・二色の節で回転が見える）・スポークの影
    ring(sp, C, R_B, 24, (0, 1.4, 0.3), "ring_b", axis="y", styles=["ring_b", "ring_b2"])
    ring(sp, (C[0], C[1] + 0.2, C[2]), R_B + 0.05, 6, (0.32, 0.9, 0.16), "ring_c", axis="y",
         phase=13.0)
    # A 環（アイボリーと淡い金の節）と F 環（点線の光）
    ring(sp, C, R_A, 24, (0, 1.0, 0.26), "ring_a", axis="y", styles=["ring_a", "ring_a2"])
    ring(sp, C, R_F, 16, (1.6, 0.22, 0.18), "ring_f", axis="y")
    # 羊飼い衛星（環とは別に回るボーン。環の上に浮く）
    mo = s.fx("spin", "moons", rg, pivot=RING_C)
    for a, r, sz in ((30, R_B + 0.2, 0.78), (150, R_A + 0.1, 0.64), (265, R_F, 0.56)):
        t = math.radians(a)
        p = (C[0] - r * math.sin(t), C[1] + 0.4 + sz / 2, C[2] - r * math.cos(t))
        cbox(mo, p, (sz, sz, sz), "moonlet")
        rbox(mo, p, (sz * 0.88, sz * 0.88, sz * 0.88), "moonlet", rot=(0, a + 45, 0))


# ---------------------------------------------------------------------------
#  冠の光輪（冠の周りを斜めに回る小さな環）
# ---------------------------------------------------------------------------
HALO_C = (0.0, 32.75, HZ + 0.75)


def halo(s):
    hl = s.part("extra", "halo", "head", pivot=HALO_C, rotation=(-16, 0, 8))
    sp = s.fx("spin", "halo", hl, pivot=HALO_C)
    ring(sp, HALO_C, 3.2, 12, (0, 0.36, 0.16), "ring_b", axis="y", styles=["ring_b", "ring_f"])
    ring(sp, (HALO_C[0], HALO_C[1] + 0.2, HALO_C[2]), 3.2, 4, (0.3, 0.3, 0.3), "gold",
         axis="y", phase=15.0)
