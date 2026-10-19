# -*- coding: utf-8 -*-
"""水星 — 水銀機装 クイックシルバー（Quicksilver Frame）。v1.1: 7 頭身のスプリンター。

九形態でいちばん細く、いちばん脚の長い流線形。frame7（bulk 0.88 の細身の骨格）の上に、鏡面（chrome）の
大きな面と、体の線を絞って見せる暗いガンメタル（gun）の側面を重ね、全部の板を後ろへ流す（後退角）。
細部は液体金属の流れ（波打つ照りの quick・下を指す V の腹）と、左右で塗り分けた発光線が受け持つ。
  * 兜: 小さな頭。前へ尖る眉庇と嘴、後ろへ掃き上げる稜（飾り）、こめかみの回る耳のタービンから
        後ろ上へ開くヘルメスの翼（三枚の羽根。飾り）、顔の中央で鋭く折れたシアンの V 字バイザー一本
  * 胴: 逆三角形。鏡面の V の胸板（下縁が昼／夜の発光線）、胸の中央に二重の輪の星核（太陽側が橙）、
        低く流れる襟、脇の排気口、下を指す液体金属の V が重なる細い腹
  * 腰: 細い帯と菱形の前垂れ、後ろへ流れる涙滴形の草摺（脚の前は塞がない）
  * 腕: 涙滴形の肩のフェアリング（前が丸く、後ろへ尾を引く）、後ろへ流れる肘のヒレ、外側に刃の羽根の篭手
  * 脚: 長い腿と脛。上へ尖る膝当て、前の V の稜、ふくらはぎの排気口、外のスピード・フィン、
        尖ったつま先のスプリンターの靴と、踵の外から後ろへ扇に開くタラリア（翼のサンダル）
  * 背: 細い背骨のフェアリングと肩甲骨の鏡面、二基の細いイオン・スラスター（回るイオンの輪・炎）、
        背中の後ろを二重の軌道で回る液体金属の滴（尾を引いて流れる）
  * 発光: 右半身は昼側の灼熱（橙）、左半身は夜側の極寒（シアン）— MIRROR_STYLES で塗り分け

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A（7 頭身の目安）から取る。
右側だけ作り `_r` を付ける → 左は自動で鏡映（塗りは MIRROR_STYLES で昼 → 夜に替わる）。
回転（統合版の rotation）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く（+X の端が前へ）/
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import math

import numpy as np

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, layered_plate,  # noqa: F401
                        line_on, mat_cube, mirror_x, octa, piston, polyline, rbox, ring,
                        rivets, sensor, stick, taper, vents)

LX = A.LEG_X                  # 脚の軸 -2.15
HZ = A.HEAD_Z                 # 頭の中心の奥行き -0.25

DAY = (255, 150, 60)          # 昼側（右）の灼熱
DAY_L = (255, 238, 204)
NIGHT = (120, 240, 255)       # 夜側（左）の極寒
NIGHT_L = (222, 252, 255)

# 右側（-X）で使う塗り → 左（鏡映）で使う塗り
MIRROR_STYLES = {
    "glow_day": "glow_night", "glow_soft_day": "glow_soft_night", "vent_day": "vent_night",
    "flame_day": "flame_night", "flame_core_day": "flame_core_night",
    "thruster_day": "thruster_night", "rip_day": "rip_night", "gem_accent": "gem",
    "emblem_day": "emblem_night", "serial_day": "serial_night", "stripe_day": "stripe_night",
}


def _glow(c, lt, emit=None):
    d = {"kind": "glowline", "glow": c, "light": lt, "bevel": False, "outline": False}
    if emit is not None:
        d["emit"] = emit
    return d


GUN = {"kind": "armor", "base": (104, 114, 134), "light": (176, 186, 204), "dark": (58, 64, 82),
       "line": (28, 32, 44), "panel": 0}


def _decal_on(under, **kw):
    d = {"kind": "decal", "under": dict(under)}
    d.update(kw)
    return d


# ===========================================================================
#  塗り（astro_paint.suit_styles("mercury") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    # 大きな面は鏡面。パネルの箱は描かず、面の照りと流れで見せる
    "chrome": {"base": (214, 224, 238), "light": (255, 255, 255), "line": (56, 64, 84)},
    "chrome2": {"kind": "chrome", "base": (170, 182, 200), "light": (236, 242, 252),
                "line": (44, 50, 66)},
    "plate": {"base": (206, 216, 230), "light": (252, 254, 255), "dark": (128, 140, 160),
              "line": (64, 74, 94), "panel": 0},
    "plate_b": {"base": (168, 178, 194), "light": (220, 228, 240), "dark": (110, 120, 140),
                "line": (54, 62, 80), "panel": 0},
    "gun": dict(GUN),
    "gun_b": {"kind": "armor", "base": (74, 82, 100), "light": (132, 142, 162),
              "dark": (40, 44, 58), "line": (20, 22, 30), "panel": 0},
    "plate2": dict(GUN),
    # 胸甲の羽根板（重ねて一枚の V に見せる: 輪郭と面取りを弱く）
    "breast": {"kind": "armor", "base": (214, 224, 238), "light": (255, 255, 255),
               "dark": (140, 152, 172), "line": (90, 100, 120), "panel": 0, "outline_k": 0.2,
               "bevel": False, "hi": 0.2, "lo": 0.85},
    # 羽根（重なった羽根が一枚ずつ読めるよう、上が明るく下が暗い無地の板）
    "feather": {"kind": "armor", "base": (222, 230, 242), "light": (255, 255, 255),
                "dark": (132, 144, 166), "line": (60, 70, 92), "panel": 0, "sheen": False,
                "hi": 0.4, "lo": 0.6, "outline_k": 0.35},
    "feather2": {"kind": "armor", "base": (130, 142, 162), "light": (196, 206, 222),
                 "dark": (60, 68, 86), "line": (26, 30, 42), "panel": 0, "sheen": False,
                 "hi": 0.4, "lo": 0.6, "outline_k": 0.35},
    # 液体金属の流れ（波打つ照りの境が流れる鏡面）
    "quick": {"kind": "blade", "all_faces": True, "base": (196, 208, 224), "light": (250, 252, 255),
              "dark": (116, 128, 150), "line": (56, 64, 84), "glint_period": 18,
              "fuller": False},
    # 回る滴（水銀の渦の模様）
    "bead": {"kind": "planet", "planet": "mercury", "radius": 1.45, "bevel": False,
             "outline": False},
    "bead_glow": {"kind": "core", "planet": "mercury", "radius": 1.45, "emit": 110,
                  "halo": NIGHT, "bevel": False, "outline": False},
    "inner": {"base": (26, 30, 42), "glow": NIGHT, "seam": 0.02},
    "frame": {"base": (44, 50, 66), "light": (100, 110, 132)},
    "dark": {"base": (22, 26, 36), "ribs": 0, "line": (8, 10, 16)},
    "rivet": {"base": (196, 204, 220), "light": (255, 255, 255), "dark": (100, 108, 128)},
    "glow_day": _glow(DAY, DAY_L),
    "glow_night": _glow(NIGHT, NIGHT_L),
    "glow_soft_day": _glow(DAY, DAY_L, 150),
    "glow_soft_night": _glow(NIGHT, NIGHT_L, 150),
    "glow_white": _glow((220, 248, 255), (255, 255, 255)),
    "vent_day": {"kind": "vent", "base": (52, 58, 74), "glow": DAY, "deep": (120, 40, 10),
                 "line": (20, 22, 30)},
    "vent_night": {"kind": "vent", "base": (52, 58, 74), "glow": NIGHT, "deep": (18, 70, 104),
                   "line": (20, 22, 30)},
    "thruster_day": {"kind": "thruster", "base": (52, 58, 74), "glow": DAY, "light": DAY_L,
                     "deep": (150, 50, 12), "line": (20, 22, 30), "bevel": False},
    "thruster_night": {"kind": "thruster", "base": (52, 58, 74), "glow": NIGHT, "light": NIGHT_L,
                       "deep": (18, 70, 104), "line": (20, 22, 30), "bevel": False},
    "flame_day": {"kind": "flame", "glow": (255, 170, 80), "light": (255, 246, 220),
                  "deep": (200, 70, 20), "bevel": False, "outline": False},
    "flame_core_day": {"kind": "flame", "glow": (255, 236, 190), "light": (255, 255, 255),
                       "deep": (255, 160, 70), "bevel": False, "outline": False},
    "flame_night": {"kind": "flame", "glow": (130, 236, 255), "light": (236, 255, 255),
                    "deep": (30, 120, 200), "bevel": False, "outline": False},
    "flame_core_night": {"kind": "flame", "glow": (210, 252, 255), "light": (255, 255, 255),
                         "deep": (100, 210, 255), "bevel": False, "outline": False},
    # 波紋のデカール（入れ子の V。流れる向きを示す）・縦の発光帯・紋章・型番
    "rip_day": _decal_on(GUN, decal="chevron", color=DAY, count=3),
    "rip_night": _decal_on(GUN, decal="chevron", color=NIGHT, count=3),
    "stripe_day": _decal_on(GUN, decal="stripe", dir="v", pos=0.3, width=0.08, color=DAY,
                            emit=40),
    "stripe_night": _decal_on(GUN, decal="stripe", dir="v", pos=0.3, width=0.08, color=NIGHT,
                              emit=40),
    "emblem_day": _decal_on(GUN, decal="emblem", color=DAY),
    "emblem_night": _decal_on(GUN, decal="emblem", color=NIGHT),
    "serial_day": _decal_on(GUN, decal="serial", text="QS-01", ink=(255, 190, 120)),
    "serial_night": _decal_on(GUN, decal="serial", text="QS-01", ink=(170, 240, 255)),
    "hazard": {"c1": DAY, "c2": (30, 34, 46)},
    "visor": {"glow": (110, 236, 255), "light": (232, 255, 255), "deep": (10, 80, 120),
              "emit": 16},
    "core": {"halo": (255, 170, 80), "emit": 40},
    "gem": {"glow": NIGHT, "deep": (18, 70, 104)},
    "gem_accent": {"glow": DAY, "deep": (130, 50, 10)},
}

# ===========================================================================
#  部位アニメ（Molang）。回る物は v.astro_spin（空中・疾走で速く進む累積の時間）× 角速度、
#  揺れは v.astro_t（ただの経過時間）。v.astro_air / v.astro_run（0..1）は振れ幅だけに掛ける。
#  `_r` のトラックは左へ自動で鏡映
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        "fx_spin_drops": {"rotation": [0, 0, "v.astro_spin * 60.0"]},
        "fx_spin_drops2": {"rotation": [0, 0, "-v.astro_spin * 96.0"]},
        "extra_droplets": {"position": [0, "math.sin(v.astro_t * 90.0) * 0.3", 0]},
        "fx_spin_ion_r": {"rotation": [0, "v.astro_spin * 240.0", 0]},
        "fx_spin_ear_r": {"rotation": ["v.astro_spin * 300.0", 0, 0]},
        "helmet_wing_r": {"rotation": [0, "math.sin(v.astro_t * 120.0) * 1.5", 0]},
        "boots_talaria_r": {"rotation": [0, "math.sin(v.astro_t * 180.0) * 3.0", 0]},
    },
    "thrust": {
        # 空中では翼が開いて羽ばたき、滴の軌道が後ろへ傾く
        "helmet_wing_r": {"rotation": ["-v.astro_air * 5.0", 0,
                                       "-v.astro_air * (5.0 + math.sin(v.astro_t * 720.0) * 4.0)"]},
        "boots_talaria_r": {"rotation": ["-v.astro_air * 8.0", 0,
                                         "-v.astro_air * (10.0 + math.sin(v.astro_t * 900.0) * 8.0)"]},
        "extra_droplets": {"rotation": ["-v.astro_air * 14.0", 0, 0]},
    },
    "sprint": {
        # 疾走では翼を後ろへ寝かせて細かく震わせ、滴の輪は後ろへ流れる
        "helmet_wing_r": {"rotation": ["v.astro_run * 10.0", "-v.astro_run * 6.0",
                                       "v.astro_run * math.sin(v.astro_t * 1080.0) * 2.5"]},
        "boots_talaria_r": {"rotation": ["v.astro_run * 8.0", "-v.astro_run * 8.0",
                                         "-v.astro_run * math.sin(v.astro_t * 1440.0) * 6.0"]},
        "extra_droplets": {"position": [0, "v.astro_run * 0.6", "v.astro_run * 1.6"],
                           "rotation": ["-v.astro_run * 24.0", 0, 0]},
    },
}


# ===========================================================================
#  道具（この惑星だけで使う）
# ===========================================================================
def mxs(bone, *cubes, about=0.0):
    """中央の部品の左右対称（左側は夜側の塗りに替える）。"""
    return mirror_x(bone, *cubes, style_map=MIRROR_STYLES, about=about)


def plank(bone, a, b, normal, t, h, style, extend=0.1):
    """a → b の板（厚み t は normal の向き、幅 h は面の中）。"""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    d = b - a
    L = float(np.linalg.norm(d))
    z = -d / L
    n = np.asarray(normal, float)
    x = n - z * float(np.dot(n, z))
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return mat_cube(bone, (a + b) / 2, (t, h, L + extend), style, np.column_stack([x, y, z]))


def wing(bone, top, bot, tip, t, style, n=4, curve=0.14, edge=None, edge_w=0.22, step=0.05):
    """後退翼の羽根: 付け根の前縁 top・後縁 bot から、前縁に平行な n 枚の板を重ねる。
    下の板ほど短く（curve ずつ）、先端は前縁に寄せて細くするので、後縁が段々の弧を描く
    （重なった羽根の並び）。板は 1 枚ごとに法線の向きへ step ずつ浮かせる（同じ平面の面が
    重なってちらつかないように。鱗のように後ろの板が前の板に乗る）。edge で前縁に発光線。"""
    top, bot, tip = (np.asarray(v, float) for v in (top, bot, tip))
    nrm = np.cross(tip - top, bot - top)
    nrm /= np.linalg.norm(nrm)
    d = tip - top
    span = bot - top
    h = max(0.2, float(np.linalg.norm(span)) / n * 1.6)
    out = []
    for i in range(n):
        f = (i + 0.5) / n
        r = top + span * f + nrm * step * i
        k = 1.0 - curve * i
        e = top + d * k + span * f * (0.35 + 0.4 * (1 - k)) + nrm * step * i
        out.append(plank(bone, r, e, nrm, t, h, style))
    if edge:
        o = (top - bot) - d * float(np.dot(top - bot, d) / np.dot(d, d))
        o /= np.linalg.norm(o)
        out.append(plank(bone, top + o * 0.05, tip, nrm, t + 0.1, edge_w, edge))
    return out


def bead(bone, c, r, style="bead"):
    """角を落とした小さな球（3 個）。液体金属の滴。"""
    d = 2 * r
    return [cbox(bone, c, (d * 0.78,) * 3, style),
            rbox(bone, c, (d, d * 0.62, d * 0.62), style, rot=(45, 0, 0)),
            rbox(bone, c, (d * 0.62, d, d * 0.62), style, rot=(0, 45, 0))]


def droplet(bone, c, r, tail, style="bead", tail_style="chrome"):
    """尾を引く液体金属の滴: 球（3 個）+ 流れと逆向きに細る尾（2 段）。tail は尾の向き。"""
    c = np.asarray(c, float)
    t = np.asarray(tail, float)
    t = t / np.linalg.norm(t)
    out = bead(bone, tuple(c), r, style)
    out += taper(bone, c + t * r * 0.5, c + t * r * 3.2, r * 1.15, max(0.16, r * 0.36), 2,
                 tail_style, round_=False)
    return out


# ===========================================================================
def build_suit(s: Suit):
    s.frame7(bulk=0.88, skip=("foot", "spine"))  # 細身の骨格。足は靴で包み、背骨は背のフェアリングの中
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    droplets(s)
    arms(s)
    hands(s)
    shoulders(s)
    helmet(s)


# ---------------------------------------------------------------------------
#  靴（尖ったつま先・重なるつま先の板・踵の噴射口・タラリアの翼）
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (LX, 0.14, -1.25), (2.6, 0.28, 5.6), "dark")                          # 靴底
    shell = bevel(b, (LX, 1.0, -0.75), (2.5, 1.45, 3.7), "chrome", cut=0.42, axis="z")
    line_on(b, shell[0], "west", (0.08, 0.36), (0.92, 0.36), 0.18, 0.16, "glow_day")
    rivets(b, shell[0], "west", 3, edge="top", margin=0.26, span=(0.2, 0.8), size=0.22)
    # 甲（ガンメタル）とつま先の板が二枚重なり、先が尖る
    ins = rbox(b, (LX, 1.86, -1.8), (2.05, 0.45, 1.75), "gun", rot=(-28, 0, 0))
    stick(b, ins, "up", 0.5, 0.5, (0.36, 1.4, 0.16), "quick", sink=0.05)
    rivets(b, ins, "up", 2, edge="bottom", margin=0.26, span=(0.2, 0.8), size=0.22)
    t1 = rbox(b, (LX, 0.98, -2.95), (2.4, 0.9, 0.95), "chrome2", rot=(-16, 0, 0))
    line_on(b, t1, "north", (0.15, 0.62), (0.85, 0.62), 0.16, 0.16, "glow_soft_day")
    cbox(b, (LX, 0.62, -3.5), (2.15, 0.3, 0.3), "dark")
    rbox(b, (LX, 0.62, -3.85), (2.1, 0.58, 0.8), "chrome", rot=(-24, 0, 0))
    rbox(b, (LX, 0.42, -4.12), (1.05, 0.42, 1.05), "chrome", rot=(0, 45, 0))     # 尖った先
    # 踵（ガンメタル）と噴射口・蹴爪
    hl = cbox(b, (LX, 1.0, 1.15), (2.3, 1.45, 0.95), "gun")
    rivets(b, hl, "west", 2, edge="top", margin=0.22, span=(0.3, 0.7), size=0.22)
    octa(b, (LX, 0.8, 1.78), 1.0, 0.42, "frame", axis="z")
    cbox(b, (LX, 0.8, 2.02), (0.72, 0.72, 0.16), "thruster_day")
    taper(b, (LX, 1.62, 1.55), (LX, 1.82, 2.5), 0.5, 0.18, 2, "chrome", round_=False)
    # タラリア: 踵の外側の軸から後ろ上へ扇に開く三枚羽
    w = s.part("boots", "talaria_r", b, pivot=(LX - 1.38, 1.3, 1.0))
    octa(w, (LX - 1.38, 1.3, 1.02), 0.95, 0.3, "chrome", axis="x")
    cbox(w, (LX - 1.57, 1.3, 1.02), (0.16, 0.38, 0.38), "glow_day")
    wing(w, (LX - 1.5, 1.95, 0.55), (LX - 1.5, 1.05, 1.15), (LX - 1.9, 4.7, 4.2), 0.24,
         "feather", n=3, curve=0.12, edge="glow_day")
    wing(w, (LX - 1.56, 1.45, 0.95), (LX - 1.56, 0.72, 1.45), (LX - 2.05, 3.15, 4.85), 0.22,
         "feather", n=3, curve=0.12)
    wing(w, (LX - 1.5, 1.0, 1.3), (LX - 1.5, 0.5, 1.7), (LX - 1.85, 1.6, 4.45), 0.2,
         "feather2", n=2, curve=0.12, edge="glow_soft_day")


# ---------------------------------------------------------------------------
#  脚（長い腿・上へ尖る膝当て・V の稜の脛・ふくらはぎの排気口・スピード・フィン）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前の鏡面（ガンメタルの下板に重ねる）・外の型番の板・内の小板。後ろは骨格を見せる
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.6, -1.62), (2.45, 4.0, 0.42), "gun", top="chrome",
                       rot=(-3, 0, 0), inset=0.26, trim="chrome2", trim_edge="bottom",
                       rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(t, fr["top"], "north", (0.78, 0.1), (0.78, 0.58), 0.16, 0.15, "glow_day")
    line_on(t, fr["top"], "north", (0.78, 0.58), (0.5, 0.88), 0.16, 0.15, "glow_day")
    stick(t, fr["top"], "north", 0.3, 0.45, (0.32, 2.4, 0.16), "quick", sink=0.04)
    side = rbox(t, (LX - 1.5, 11.15, -0.25), (0.4, 3.1, 1.9), "serial_day", rot=(0, 0, -3))
    rivets(t, side, "west", 3, edge="bottom", margin=0.24, size=0.22)
    line_on(t, side, "west", (0.06, 0.9), (0.94, 0.9), 0.16, 0.15, "glow_soft_day")
    cbox(t, (LX - 1.38, 9.62, -0.2), (0.36, 0.34, 2.0), "chrome2")
    inn = rbox(t, (LX + 1.2, 11.5, -0.45), (0.32, 2.6, 1.5), "gun_b", rot=(0, 0, 2))
    rivets(t, inn, "east", 2, edge="top", margin=0.22, span=(0.3, 0.7), size=0.2)
    sensor(t, (LX + 0.3, 13.3, -1.92), 0.22, "glow_day", "dark")
    cable(t, [(LX + 0.8, 13.6, 1.05), (LX + 0.8, 9.7, 1.05)], 0.24, "dark", sag=-0.25, seg=1.0)
    # 膝: 上へ尖る鏡面の膝当て（宝玉・リベット）と外の油圧シリンダー
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    kg = chamfer(k, (LX, 8.45, -1.6), (1.95, 1.95, 0.62), "chrome", cut=0.32, axis="z")
    taper(k, (LX, 9.2, -1.64), (LX, 10.75, -1.5), 1.25, 0.26, 2, "chrome")
    rbox(k, (LX, 7.3, -1.58), (0.95, 0.95, 0.46), "gun", rot=(0, 0, 45))
    rbox(k, (LX, 8.45, -1.98), (0.55, 0.55, 0.24), "gem_accent", rot=(0, 0, 45))
    rivets(k, kg[1], "north", 2, edge="bottom", margin=0.26, span=(0.15, 0.85), size=0.2)
    piston(k, (LX - 1.48, 10.5, 0.98), (LX - 1.36, 6.55, 0.9), r=0.22, style="frame",
           rod_style="chrome", cap_style="dark")
    # 脛: 前のガンメタルの板 + 鏡面の V の稜（発光線）、両脇の波紋の板、ふくらはぎ、外のフィン
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 4.85, -1.28), (2.25, 5.0, 0.42), "gun", rot=(4, 0, 0))
    keel = rbox(g, (LX - 0.32, 5.05, -1.58), (0.7, 4.2, 0.4), "chrome", rot=(4, 24, 0))
    mirror_x(g, keel, about=LX)
    line_on(g, front, "north", (0.1, 0.16), (0.14, 0.82), 0.16, 0.15, "glow_day")
    line_on(g, front, "north", (0.9, 0.16), (0.86, 0.82), 0.16, 0.15, "glow_day")
    rivets(g, front, "north", 2, edge="bottom", margin=0.2, span=(0.12, 0.88), size=0.2)
    sd = rbox(g, (LX - 1.25, 4.9, -0.05), (0.36, 4.6, 2.2), "rip_day", rot=(0, 0, -4))
    sdr = rivets(g, sd, "west", 3, edge="bottom", margin=0.24, size=0.2)
    sdi = rbox(g, (LX + 1.2, 4.9, -0.1), (0.32, 4.0, 1.8), "gun_b", rot=(0, 0, 4))
    calf = rbox(g, (LX, 5.95, 1.78), (1.95, 2.7, 0.42), "chrome", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.22, 0.2, 0.78, 0.8), style="vent_day", rim="frame")
    fin = rbox(g, (LX - 1.55, 5.45, 1.05), (0.3, 3.0, 1.6), "chrome", rot=(-14, 0, -6))
    line_on(g, fin, "west", (0.12, 0.25), (0.88, 0.75), 0.16, 0.15, "glow_day")
    chamfer(g, (LX, 2.78, 0.15), (2.3, 0.3, 2.5), "chrome2", cut=0.32, axis="y")  # 足首の縁
    sensor(g, (LX, 7.2, -1.62), 0.2, "glow_day", "dark")
    del sdr, sdi


# ---------------------------------------------------------------------------
#  腰（細いベルト・菱形の前垂れ・腰の脇の板・後ろへ流れる涙滴の草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    belt = chamfer(w, (0, 16.95, 0.12), (6.4, 0.85, 4.4), "frame", cut=0.4, axis="y")
    chamfer(w, (0, 16.95, -2.3), (1.55, 1.1, 0.42), "chrome", cut=0.28, axis="z")    # バックル
    rbox(w, (0, 16.95, -2.55), (0.62, 0.62, 0.22), "core", rot=(0, 0, 45))
    gd = cbox(w, (-1.85, 17.15, -2.13), (1.3, 0.18, 0.16), "glow_day")
    bl = rivets(w, belt[0], "north", 2, edge="bottom", margin=0.3, span=(0.12, 0.3), size=0.2)
    mxs(w, gd, bl)
    # 前垂れ（細い鏡面の菱形。腿の前を塞がない幅）
    fp = rbox(w, (0, 15.4, -2.02), (1.5, 2.1, 0.42), "chrome", rot=(-8, 0, 0))
    line_on(w, fp, "north", (0.5, 0.18), (0.5, 0.86), 0.18, 0.15, "glow_white")
    rbox(w, (0, 14.35, -2.0), (0.95, 0.95, 0.4), "chrome2", rot=(-8, 0, 45))
    # 腰の脇の板（股関節の前を覆う）
    hp = rbox(w, (-2.25, 15.8, -1.92), (1.85, 1.3, 0.4), "gun", rot=(-8, 14, 4))
    hpl = line_on(w, hp, "north", (0.1, 0.3), (0.9, 0.3), 0.16, 0.15, "glow_day")
    hpr = rivets(w, hp, "north", 2, edge="top", margin=0.24, span=(0.25, 0.75), size=0.2)
    mxs(w, hp, hpl, hpr)
    # 後ろ垂れ（警告の帯・リベット・小さな排気口）
    rs = rbox(w, (0, 15.15, 2.38), (4.0, 2.3, 0.42), "gun", rot=(14, 0, 0))
    cbox(w, (0, 14.2, 2.74), (2.4, 0.34, 0.26), "hazard")
    rivets(w, rs, "south", 4, edge="top", margin=0.24, size=0.22)
    # 草摺（腰の横。付け根で外へ開き、後ろへ尾を引く涙滴形）
    ts = s.part("waist", "tasset_r", w, pivot=(-3.25, 16.6, 0.0), rotation=(0, 0, 8))
    base = layered_plate(ts, (-3.5, 15.3, 0.15), (0.38, 2.3, 2.7), "gun", top="chrome",
                         face="west", inset=0.3, trim="chrome2", trim_edge="bottom",
                         rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(ts, base["top"], "west", (0.12, 0.38), (0.88, 0.62), 0.16, 0.15, "glow_day")
    rbox(ts, (-3.5, 15.25, 1.82), (0.32, 1.55, 1.05), "chrome", rot=(-32, 0, 0))       # 尾
    cbox(ts, (-3.32, 16.32, 0.1), (0.42, 0.45, 1.4), "dark")                           # 蝶番


# ---------------------------------------------------------------------------
#  胴（ガンメタルの胸郭・鏡面の V の胸板・二重の輪の星核・襟・脇の排気口・液体金属の V の腹）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.25, 0.05), (8.7, 3.3, 5.1), "gun", cut=0.95, axis="z")     # 上が広い
    chamfer(c, (0, 21.75, 0.0), (6.6, 2.1, 4.6), "gun_b", cut=0.7, axis="y")
    sl = rbox(c, (-3.8, 22.3, 0.05), (0.45, 2.9, 4.0), "gun", rot=(0, 0, -22))     # 脇の斜面
    mirror_x(c, sl)
    # 鏡面の V の胸甲: 襟元で広く、星核の脇へ細る三角を羽根板四枚で重ねる。外の斜辺に発光線、
    # 上縁にリベット
    top_in, top_out, tip = (-0.5, 25.7, -2.8), (-4.2, 25.3, -2.5), (-1.62, 21.45, -2.98)
    pecs = wing(c, top_in, top_out, tip, 0.46, "breast", n=4, curve=0.16)
    edge = beam(c, np.add(top_out, (0.12, -0.3, -0.28)), np.add(tip, (0.22, 0.8, -0.26)),
                0.2, 0.2, "glow_day")
    pr = rivets(c, pecs[-1], "east", 3, line=((0.86, 0.25), (0.86, 0.75)), size=0.2)
    mxs(c, pecs, edge, pr)
    # 胸の中央の稜（鏡面 + 白い光の筋）: 胸板の間を縦に通り、下の星核へ
    kl = rbox(c, (0, 24.75, -2.95), (1.0, 2.4, 0.46), "chrome", rot=(-8, 0, 0))
    stick(c, kl, "north", 0.5, 0.5, (0.22, 1.9, 0.16), "glow_white", sink=0.05)
    # 星核: 黒い菱形の台 → 鏡面の輪 → 水星 → 脈打つ光の輪（夜側のシアン + 太陽側の橙の弧）
    rbox(c, (0, 22.55, -2.66), (2.25, 2.25, 0.44), "dark", rot=(0, 0, 45))
    ring(c, (0, 22.55, -2.9), 1.02, 10, (0, 0.24, 0.3), "chrome", axis="z")
    cbox(c, (0, 22.55, -2.98), (1.3, 1.3, 0.5), "core")
    gl_ = s.fx("glow", "core", c, pivot=(0, 22.55, -3.2))
    ring(gl_, (0, 22.55, -3.18), 0.78, 8, (0, 0.18, 0.2), "glow_night", axis="z")
    ring(gl_, (0, 22.55, -3.1), 1.38, 6, (0, 0.18, 0.2), "glow_soft_day", axis="z",
         a0=30, a1=150)
    # 襟（首の両脇へ低く流れる）と喉元のセンサー
    col = rbox(c, (-1.7, 26.1, 0.3), (1.25, 0.95, 3.3), "gun", rot=(0, 0, -26))
    colt = stick(c, col, "up", 0.5, 0.5, (0.85, 3.0, 0.18), "chrome", sink=0.06)
    coll = line_on(c, colt, "up", (0.25, 0.08), (0.25, 0.92), 0.16, 0.15, "glow_soft_day")
    cf = rbox(c, (-0.95, 25.85, -1.95), (1.45, 0.8, 0.42), "chrome", rot=(-20, 30, -10))
    sn = sensor(c, (-1.35, 25.3, -2.62), 0.22, "glow_day", "dark")
    mxs(c, col, colt, coll, cf, sn)
    # 肩の付け根（肩当ての下）と脇の排気口
    yk = rbox(c, (-3.8, 25.85, 0.0), (1.8, 0.5, 3.4), "plate_b", rot=(0, 0, -10))
    ykr = rivets(c, yk, "up", 2, edge="left", margin=0.3, span=(0.25, 0.75), size=0.2)
    sv = cbox(c, (-4.18, 23.55, 0.45), (0.38, 1.9, 2.2), "gun_b")
    svv = vents(c, sv, "west", 3, box=(0.15, 0.2, 0.85, 0.8), style="vent_day")
    mxs(c, yk, ykr, sv, svv)
    rivets(c, up[1], "south", 4, edge="top", margin=0.32, span=(0.15, 0.85), size=0.22)
    # 腹: 下を指す液体金属の V が三段（流れの向き）と中央の鏡面の筋、外の端の小さな灯り
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))
    cbox(ab, (0, 18.95, -2.08), (0.42, 3.0, 0.4), "chrome")
    for i, (y, ww) in enumerate(((20.0, 1.85), (18.98, 1.7), (17.96, 1.5))):
        v = rbox(ab, (-ww / 2 - 0.14, y, -1.98 + i * 0.04), (ww, 0.72, 0.42), "quick",
                 rot=(-8, 10, 14))
        dot = stick(ab, v, "north", 0.1, 0.5, (0.24, 0.24, 0.15), "glow_day", sink=0.05)
        mxs(ab, v, dot)
    lb = cbox(ab, (0, 18.9, 2.1), (1.9, 2.5, 0.42), "gun")                         # 背の腰板
    rivets(ab, lb, "south", 2, edge="top", margin=0.25, span=(0.25, 0.75), size=0.2)


# ---------------------------------------------------------------------------
#  背中（背骨のフェアリング・肩甲骨の鏡面・ホース・二基の細いイオン・スラスター）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    pk = bevel(bk, (0, 22.35, 3.05), (2.5, 5.4, 1.3), "gun", cut=0.42, axis="z")
    rd = stick(bk, pk[0], "south", 0.5, 0.5, (0.7, 4.7, 0.24), "chrome", sink=0.06)
    stick(bk, rd, "south", 0.5, 0.52, (0.2, 3.6, 0.16), "glow_white", sink=0.05)
    pr = rivets(bk, pk[1], "south", 4, edge="left", margin=0.2, span=(0.12, 0.88), size=0.2)
    mxs(bk, pr)
    rbox(bk, (0, 25.15, 2.95), (3.0, 0.65, 1.35), "chrome2", rot=(20, 0, 0))          # 上の蓋
    cbox(bk, (0, 19.95, 3.55), (1.9, 0.34, 0.3), "hazard")
    sensor(bk, (0, 24.55, 3.78), 0.24, "glow_white", "dark", facing=1)
    # 肩甲骨の鏡面の板（後ろへ流れる）
    sc = rbox(bk, (-2.4, 23.7, 2.82), (2.4, 2.45, 0.42), "chrome", rot=(6, -14, -10))
    scl = line_on(bk, sc, "south", (0.12, 0.85), (0.85, 0.15), 0.16, 0.15, "glow_day")
    scr = rivets(bk, sc, "south", 2, edge="top", margin=0.24, span=(0.3, 0.7), size=0.2)
    # ホース: 背骨の下から腰の両脇へ（垂れる蛇腹）
    hs = cable(bk, [(-0.9, 20.0, 3.45), (-2.3, 17.9, 2.35)], 0.26, "dark", sag=0.3,
               rib="frame_lt", rib_every=2)
    mxs(bk, sc, scl, scr, hs)
    # イオン・スラスター（右。下後ろへ向ける）: 細長い鏡面の胴・吸気の尖頭・帯・ノズル・炎
    TX, TZ = -1.85, 4.15
    th = s.part("back", "thruster_r", bk, pivot=(TX, 22.6, 3.9), rotation=(10, 0, -4))
    body = octa(th, (TX, 20.3, TZ), 1.2, 4.6, "chrome", axis="y")
    taper(th, (TX, 22.55, TZ), (TX, 24.5, TZ), 1.1, 0.26, 2, "chrome")                # 吸気の尖頭
    for y in (22.25, 18.4):
        octa(th, (TX, y, TZ), 1.38, 0.28, "frame", axis="y")
    octa(th, (TX, 21.35, TZ), 1.3, 0.5, "glow_soft_day", axis="y", style2="chrome2")
    rivets(th, body[0], "south", 3, line=((0.5, 0.2), (0.5, 0.45)), size=0.2)
    octa(th, (TX, 17.55, TZ), 1.55, 0.9, "gun", axis="y")                            # ノズル
    ring(th, (TX, 17.08, TZ), 0.6, 8, (0, 0.18, 0.2), "glow_day", axis="y")
    cbox(th, (TX, 17.08, TZ), (1.05, 0.16, 1.05), "thruster_day")
    for dx, dz in ((-0.8, 0.0), (0.0, 0.8)):                                         # 小さな安定板
        beam(th, (TX + dx, 19.0, TZ + dz), (TX + dx * 1.5, 17.4, TZ + dz * 1.5 + 0.5), 0.2, 0.7,
             "gun")
    # 回るイオンの輪（胴の中ほど）
    ion = s.fx("spin", "ion_r", th, pivot=(TX, 19.6, TZ))
    ring(ion, (TX, 19.6, TZ), 0.86, 8, (0.42, 0.2, 0.26), "chrome2", axis="y",
         styles=["chrome2", "glow_day"])
    fx = s.fx("thrust", "r", th, pivot=(TX, 17.0, TZ))
    taper(fx, (TX, 17.0, TZ), (TX, 11.6, TZ), 1.2, 0.26, 3, "flame_day")
    taper(fx, (TX, 16.95, TZ), (TX, 13.8, TZ), 0.6, 0.18, 2, "flame_core_day", round_=False)


# ---------------------------------------------------------------------------
#  液体金属の滴（背中の後ろを二重の軌道で回る。尾を引いて流れる）
# ---------------------------------------------------------------------------
def droplets(s):
    C = (0.0, 19.6, 7.0)
    d = s.part("extra", "droplets", "body", pivot=C)
    # 外の軌道: 五つの滴（時計回り。尾は流れと逆へ）
    sp = s.fx("spin", "drops", d, pivot=C)
    for k in range(5):
        a = math.radians(k * 72 + 18)
        p = (C[0] + math.sin(a) * 4.7, C[1] + math.cos(a) * 4.7, C[2])
        droplet(sp, p, 0.52, (-math.cos(a), math.sin(a), 0.0), "bead_glow" if k % 2 else "bead")
    # 内の軌道: 三つの滴（反時計回り）
    sp2 = s.fx("spin", "drops2", d, pivot=C)
    for k in range(3):
        a = math.radians(k * 120 + 60)
        p = (C[0] + math.sin(a) * 2.6, C[1] + math.cos(a) * 2.6, C[2] + 0.35)
        bead(sp2, p, 0.4, "bead")
    # 軌道の中心: 液体金属の核と細い光の輪（右半分が昼、左半分が夜）
    cg = s.fx("glow", "drops", d, pivot=C)
    bead(cg, C, 0.42, "bead_glow")
    ring(cg, C, 0.9, 3, (0, 0.16, 0.16), "glow_soft_day", axis="z", a0=15, a1=165)
    ring(cg, C, 0.9, 3, (0, 0.16, 0.16), "glow_soft_night", axis="z", a0=195, a1=345)


# ---------------------------------------------------------------------------
#  腕（二の腕・後ろへ流れる肘のヒレ・刃の羽根の篭手）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.16, 21.35, 0.0), (0.4, 3.0, 2.2), "chrome", rot=(0, 0, 3))
    ops = stick(ua, op, "west", 0.42, 0.5, (0.9, 2.5, 0.16), "gun", sink=0.05)
    line_on(ua, ops, "west", (0.5, 0.1), (0.5, 0.9), 0.18, 0.15, "glow_day")
    rivets(ua, op, "west", 2, edge="bottom", margin=0.22, span=(0.3, 0.7), size=0.2)
    upf = rbox(ua, (X + 0.05, 21.45, -1.24), (1.85, 2.7, 0.36), "chrome", rot=(-3, 0, 0))
    stick(ua, upf, "north", 0.5, 0.5, (0.42, 2.2, 0.15), "gun", sink=0.06)
    sensor(ua, (X + 0.05, 22.5, -1.5), 0.2, "glow_day", "dark")
    upb = rbox(ua, (X + 0.05, 21.7, 1.26), (1.75, 2.2, 0.36), "gun_b", rot=(3, 0, 0))
    rivets(ua, upb, "south", 2, edge="top", margin=0.24, span=(0.3, 0.7), size=0.2)
    octa(ua, (X, 19.75, 0.02), 2.5, 0.3, "chrome", axis="y")                         # 腕輪
    # 肘当て（後ろ）と後ろ上へ流れるヒレ、前外の油圧シリンダー
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    cop = chamfer(el, (A.ELBOW[0], 18.55, 1.42), (1.8, 1.65, 0.52), "chrome", cut=0.3, axis="z")
    rivets(el, cop[0], "south", 2, edge="bottom", margin=0.26, span=(0.3, 0.7), size=0.2)
    fin = rbox(el, (A.ELBOW[0], 19.05, 2.2), (0.3, 1.35, 1.55), "chrome", rot=(-38, 0, 0))
    line_on(el, fin, "west", (0.15, 0.2), (0.85, 0.75), 0.16, 0.15, "glow_day")
    piston(el, (-7.12, 20.5, -1.02), (-6.98, 16.7, -1.1), r=0.2, style="frame",
           rod_style="chrome", cap_style="dark")
    # 篭手: 手首へ向かって開く（鏡面の上段・ガンメタルの下段）+ 外の刃の羽根 + 前の鏡面の板 + 袖口
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX_ = A.FOREARM_X
    chamfer(fa, (FX_, 17.15, 0.0), (2.55, 1.8, 2.65), "chrome", cut=0.42, axis="y")
    lo = bevel(fa, (FX_ - 0.04, 15.72, 0.0), (2.75, 1.7, 2.9), "chrome2", cut=0.46, axis="y")
    wing(fa, (-7.42, 17.75, -0.85), (-7.42, 15.35, -1.05), (-7.62, 17.85, 2.95), 0.28, "chrome",
         n=3, curve=0.12, edge="glow_day")
    fv = rbox(fa, (FX_ - 0.02, 16.4, -1.48), (1.8, 2.2, 0.3), "gun", rot=(-5, 0, 0))
    stick(fa, fv, "north", 0.3, 0.5, (0.3, 1.9, 0.16), "quick", sink=0.04)
    line_on(fa, fv, "north", (0.72, 0.08), (0.72, 0.92), 0.16, 0.15, "glow_day")
    rivets(fa, fv, "north", 2, edge="bottom", margin=0.18, span=(0.12, 0.88), size=0.2)
    chamfer(fa, (FX_ - 0.04, 14.72, 0.0), (2.95, 0.32, 3.05), "chrome", cut=0.4, axis="y")
    sensor(fa, (FX_ + 0.05, 15.6, 1.5), 0.22, "glow_day", "dark", facing=1)
    rivets(fa, lo[1], "south", 2, edge="bottom", margin=0.28, span=(0.3, 0.7), size=0.2)


def hands(s):
    """手の甲の板と宝玉、指の甲当て（4 本の基節）、親指の当て。指そのものは frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.42, 13.62, 0.0), (0.34, 1.65, 2.2), "gun", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.55, (0.55, 0.55, 0.2), "gem_accent", sink=0.05)
    stick(h, hb, "west", 0.5, 0.94, (2.1, 0.2, 0.15), "chrome", sink=0.04)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        n = (-0.81, -0.58, 0.0)
        o = 0.34
        beam(h, (p0[0] + n[0] * o, p0[1] + n[1] * o, zf), (p1[0] + n[0] * o, p1[1] + n[1] * o, zf),
             0.54, 0.22, "chrome")
    rbox(h, (-5.62, 13.55, -1.72), (0.6, 0.9, 0.22), "chrome", rot=(0, 0, -36))


# ---------------------------------------------------------------------------
#  肩（涙滴形のフェアリング: 前が丸く、後ろへ尾を引く）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "fairing_r", "rightArm")
    R = (0, 0, -12)
    # 涙滴の胴（前から見て角を落とした楕円）・前の継ぎ目の輪・丸い鼻・後ろへ細る尾
    pod = bevel(p, (-7.15, 25.3, -0.1), (3.1, 2.45, 3.5), "chrome", cut=0.78, axis="z", rot=R)
    chamfer(p, (-7.15, 25.28, -1.72), (3.24, 2.58, 0.26), "chrome2", cut=0.78, axis="z", rot=R)
    chamfer(p, (-7.17, 25.22, -2.2), (2.3, 1.8, 0.7), "chrome2", cut=0.55, axis="z", rot=R)
    sensor(p, (-7.17, 25.22, -2.58), 0.26, "glow_day", "dark")
    taper(p, (-7.2, 25.32, 1.55), (-7.5, 25.0, 3.9), 2.1, 0.36, 2, "chrome")
    # 上の鞍（ガンメタル・発光線・リベット）と、後ろへ流れる小さなヒレ
    top = stick(p, pod[1], "up", 0.42, 0.5, (1.1, 3.2, 0.22), "gun", sink=0.08)
    line_on(p, top, "up", (0.62, 0.06), (0.62, 0.94), 0.18, 0.15, "glow_day")
    rivets(p, top, "up", 3, edge="left", margin=0.16, span=(0.15, 0.85), size=0.2)
    rbox(p, (-7.3, 26.75, 1.15), (0.26, 0.85, 1.6), "chrome", rot=(-30, 0, -12))
    cbox(p, (-6.45, 24.15, 0.0), (2.0, 0.45, 3.0), "dark")                           # 裏の縁
    # 外へ開いて垂れる板（紋章・鏡面の縁・リベット）と、その下の細い板（発光線）
    l1 = rbox(p, (-8.5, 23.75, 0.1), (0.42, 2.0, 3.4), "emblem_day", rot=(0, 0, 12))
    stick(p, l1, "west", 0.5, 0.06, (3.2, 0.22, 0.15), "chrome", sink=0.04)
    rivets(p, l1, "west", 4, edge="top", margin=0.22, size=0.2)
    l2 = rbox(p, (-8.55, 22.35, 0.2), (0.38, 1.25, 2.8), "gun", rot=(0, 0, 9))
    line_on(p, l2, "west", (0.08, 0.5), (0.92, 0.5), 0.16, 0.15, "glow_day")


# ---------------------------------------------------------------------------
#  兜（小さな鏡面の頭・前へ尖る眉庇と嘴・面頬・頬当て・耳・後頭部としころ）、
#  稜とヘルメスの翼（飾り）、V 字のバイザー
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.4, HZ + 0.2), (4.45, 2.6, 4.85), "chrome", cut=1.0, axis="z")
    bevel(hm, (0, 31.66, HZ + 0.35), (2.9, 0.7, 4.3), "chrome", cut=0.25, axis="z")   # 冠
    rbox(hm, (0, 30.85, HZ - 2.22), (4.0, 1.2, 0.48), "chrome", rot=(-24, 0, 0))   # 額の斜面
    # 眉庇（中央で前へ尖る V）と嘴
    br = rbox(hm, (-1.0, 30.12, HZ - 2.5), (2.15, 0.48, 0.52), "gun", rot=(-6, 14, 8))
    brl = line_on(hm, br, "north", (0.06, 0.4), (0.94, 0.4), 0.16, 0.15, "glow_day")
    # こめかみの板（発光線・リベット）と頬当て
    sd = cbox(hm, (-2.2, 29.0, HZ + 0.55), (0.38, 2.3, 3.3), "gun")
    sdl = stick(hm, sd, "west", 0.5, 0.15, (3.0, 0.2, 0.16), "glow_soft_day", sink=0.05)
    sdr = rivets(hm, sd, "west", 2, edge="top", margin=0.26, span=(0.25, 0.75), size=0.2)
    ck = rbox(hm, (-1.75, 28.35, HZ - 1.2), (0.42, 1.85, 2.15), "gun", rot=(0, 20, -10))
    ckl = line_on(hm, ck, "west", (0.15, 0.2), (0.15, 0.85), 0.16, 0.15, "glow_day")
    # 面頬: 中央の稜へ折れた V の鏡面の板、頬の吸気スリット、尖った顎
    fc = rbox(hm, (-0.6, 28.45, HZ - 2.24), (1.3, 1.25, 0.4), "chrome2", rot=(8, 26, 0))
    fv = vents(hm, fc, "north", 2, box=(0.2, 0.22, 0.75, 0.6), w=0.16, style="vent_day")
    ch = rbox(hm, (-0.45, 27.78, HZ - 2.0), (1.0, 0.68, 0.46), "chrome2", rot=(0, 26, -22))
    mxs(hm, br, brl, sd, sdl, sdr, ck, ckl, fc, fv, ch)
    taper(hm, (0, 30.12, HZ - 2.72), (0, 29.98, HZ - 3.35), 0.8, 0.24, 2, "chrome",
          round_=False)                                                                   # 嘴
    cbox(hm, (0, 28.5, HZ - 2.5), (0.3, 1.2, 0.3), "chrome")
    taper(hm, (0, 27.7, HZ - 2.15), (0, 27.38, HZ - 2.35), 0.8, 0.3, 1, "chrome", round_=False)
    # 後頭部（稜が後ろへ降りる・小さな排気口）としころ
    bh = cbox(hm, (0, 29.35, HZ + 2.55), (3.9, 2.3, 0.44), "gun")
    vents(hm, bh, "south", 3, box=(0.28, 0.25, 0.72, 0.65), w=0.18, style="vent")
    rbox(hm, (0, 31.3, HZ + 2.45), (0.7, 1.5, 0.4), "chrome", rot=(35, 0, 0))
    rbox(hm, (0, 28.05, HZ + 2.6), (3.6, 0.7, 0.44), "chrome2", rot=(22, 0, 0))
    rbox(hm, (0, 27.6, HZ + 2.75), (3.1, 0.58, 0.42), "gun", rot=(32, 0, 0))
    # 稜（飾り）: 額から頭頂を越えて後ろへ掃き上がり、後頭部の先で尾になる
    cr = s.part("helmet", "crest", "head", pivot=(0, 30.9, HZ - 2.5), ornament=True)
    polyline(cr, [(0, 30.9, HZ - 2.55), (0, 32.05, HZ - 1.3), (0, 32.45, HZ + 0.9),
                  (0, 32.2, HZ + 2.6), (0, 31.4, HZ + 4.1)],
             [0.52, 0.5, 0.44, 0.34], [0.62, 0.66, 0.6, 0.44], "chrome")
    polyline(cr, [(0, 31.2, HZ - 2.4), (0, 32.36, HZ - 1.2), (0, 32.76, HZ + 0.9),
                  (0, 32.5, HZ + 2.5)], 0.56, 0.16, "glow_white")
    taper(cr, (0, 31.75, HZ + 2.3), (0, 31.15, HZ + 4.7), 1.3, 0.3, 2, "chrome2",
          round_=False)                                                                   # 尾
    # ヘルメスの翼（飾り）: こめかみの耳のタービンから後ろ上へ開く三枚の羽根
    wg = s.part("helmet", "wing_r", "head", pivot=(-2.55, 29.4, HZ + 0.65), ornament=True)
    octa(wg, (-2.55, 29.4, HZ + 0.65), 1.35, 0.3, "chrome", axis="x")
    ear = s.fx("spin", "ear_r", wg, pivot=(-2.7, 29.4, HZ + 0.65))
    ring(ear, (-2.72, 29.4, HZ + 0.65), 0.5, 6, (0.36, 0.18, 0.2), "frame", axis="x",
         styles=["frame", "glow_day"])
    cbox(ear, (-2.78, 29.4, HZ + 0.65), (0.16, 0.42, 0.42), "glow_day")
    wing(wg, (-2.62, 30.45, HZ - 0.15), (-2.62, 29.35, HZ + 0.8), (-3.8, 33.9, HZ + 4.5), 0.26,
         "feather", n=4, curve=0.1, edge="glow_day")
    wing(wg, (-2.7, 29.9, HZ + 0.4), (-2.7, 28.85, HZ + 1.3), (-4.25, 31.85, HZ + 5.4), 0.24,
         "feather", n=3, curve=0.1)
    wing(wg, (-2.66, 29.3, HZ + 0.95), (-2.66, 28.45, HZ + 1.65), (-3.85, 29.5, HZ + 4.9), 0.22,
         "feather2", n=3, curve=0.12, edge="glow_soft_day")
    # バイザー: 顔の中央で鋭く折れたシアンの V 字（暗い溝の上に、外の端が吊り上がる一本の光）
    vz = s.part("visor", "eye", "head")
    vd = rbox(vz, (-0.95, 29.42, HZ - 2.36), (2.0, 0.6, 0.24), "dark", rot=(0, 14, 18))
    mirror_x(vz, vd)
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.4, HZ - 2.52))
    half = rbox(fg, (-0.95, 29.42, HZ - 2.5), (1.9, 0.32, 0.18), "visor", rot=(0, 14, 18))
    mirror_x(fg, half)
