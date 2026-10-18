# -*- coding: utf-8 -*-
"""水星 — 水銀機装 クイックシルバー（Quicksilver Frame）。

最も速く、最も細い形態。殻はインナーの最小の殻（inner_box）のすぐ外に沿わせ、大きな面は鏡面（chrome）、
側面は暗いガンメタルにして体の線を細く見せる。細部は液体金属の流れ（波打つ照りの板・波紋の V）と、
左右で塗り分けた発光線が受け持つ。
  * 兜: 前へ尖る眉庇、後ろへ掃き上げる冠と稜（後頭部の先で尾になる）、こめかみから後ろ上へ大きく
        開くヘルメスの翼（三角の羽根を三枚重ね）、顔の中央で鋭く折れたシアンの V 字スリット一本
  * 足: 尖ったつま先のブーツ、踵の外側から後ろへ扇に開くタラリア（翼のサンダル）の三枚羽、
        膝が広く足首が細い（暗い）先細りの脛
  * 肩: 肩に沿う薄い涙滴形のフェアリング（前が丸く、後ろへ尾を引く）
  * 背: 縦に長い二基の細いイオン・スラスター、背中の後ろを二重の軌道で回る液体金属の滴
  * 発光: 右半身は昼側の灼熱（橙）、左半身は夜側の極寒（シアン）— MIRROR_STYLES で塗り分け
  * 胸: 細い V の鏡面の胸板の合わせ目に、銀の水星を二重の輪で囲んだ星核（太陽側が橙に光る）

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。右側だけ作り `_r` を付ける → 左は自動で鏡映。
回転（統合版の rotation）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く /
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import numpy as np

from astro_common import (beam, bevel, cbox, line_on, mat_cube, octa, polyline, rbox, ring,
                          stick, taper)
from astro_suit import ARM_X, LEG_X, Suit, mirror_x

DAY = (255, 150, 60)          # 昼側（右）の灼熱
DAY_L = (255, 238, 204)
NIGHT = (120, 240, 255)       # 夜側（左）の極寒
NIGHT_L = (222, 252, 255)
TRIM_W = 0.32                 # 縁取りの幅

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


GUN = {"kind": "armor", "base": (92, 102, 122), "light": (160, 172, 192), "dark": (52, 58, 74),
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
    "plate2": dict(GUN),
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
    "inner": {"base": (26, 30, 42), "glow": NIGHT, "seam": 0.02},
    "frame": {"base": (44, 50, 66), "light": (100, 110, 132)},
    "dark": {"base": (22, 26, 36), "ribs": 0, "line": (8, 10, 16)},
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
        "helmet_wing_r": {"rotation": ["-v.astro_air * 5.0", 0,
                                       "-v.astro_air * (5.0 + math.sin(q.anim_time * 720.0) * 4.0)"]},
        "boots_talaria_r": {"rotation": ["-v.astro_air * 8.0", 0,
                                         "-v.astro_air * (10.0 + math.sin(q.anim_time * 900.0) * 8.0)"]},
    },
    "sprint": {
        # 疾走では翼を後ろへ寝かせ、細かく震わせる
        "helmet_wing_r": {"rotation": ["v.astro_run * 10.0", "-v.astro_run * 6.0",
                                       "v.astro_run * math.sin(q.anim_time * 1080.0) * 2.5"]},
        "boots_talaria_r": {"rotation": ["v.astro_run * 8.0", "-v.astro_run * 8.0",
                                         "-v.astro_run * math.sin(q.anim_time * 1440.0) * 6.0"]},
    },
}


# ===========================================================================
#  道具
# ===========================================================================
def mx(bone, *cubes, about=0.0):
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


def wing(bone, top, bot, tip, t, style, n=4, curve=0.14, edge=None, edge_w=0.26):
    """後退翼の羽根: 付け根の前縁 top・後縁 bot から、前縁に平行な n 枚の板を重ねる。
    下の板ほど短く（curve ずつ）、先端は前縁に寄せて細くするので、後縁が段々の弧を描く
    （重なった羽根の並び）。edge で前縁に発光線。"""
    top, bot, tip = (np.asarray(v, float) for v in (top, bot, tip))
    nrm = np.cross(tip - top, bot - top)
    nrm /= np.linalg.norm(nrm)
    d = tip - top
    span = bot - top
    h = float(np.linalg.norm(span)) / n * 1.6
    out = []
    for i in range(n):
        f = (i + 0.5) / n
        r = top + span * f
        k = 1.0 - curve * i
        # 先端は前縁の方へ寄る（先細り）
        e = top + d * k + span * f * (0.35 + 0.4 * (1 - k))
        out.append(plank(bone, r, e, nrm, t, h, style))
    if edge:
        d = tip - top
        o = (top - bot) - d * float(np.dot(top - bot, d) / np.dot(d, d))
        o /= np.linalg.norm(o)
        out.append(plank(bone, top + o * 0.05, tip, nrm, t + 0.12, edge_w, edge))
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
    cbox(b, (X, -0.35, -0.8), (5.2, 0.6, 7.0), "frame")                  # 靴底
    cbox(b, (X, 1.5, -0.15), (5.2, 2.9, 5.6), "gun")                     # 足の殻
    # つま先: 前上を向いた鏡面の板 + 尖った先端
    toe = rbox(b, (X, 1.0, -3.3), (4.7, 1.9, 1.6), "chrome", rot=(-34, 0, 0))
    stick(b, toe, "north", 0.5, 0.55, (0.4, 1.3, 0.2), "glow_day", sink=0.05)
    taper(b, (X, 0.35, -3.9), (X, 0.2, -5.6), 2.8, 0.6, 2, "chrome")
    # 甲: 前へ倒れた鏡面の板と、液体金属の筋
    ins = rbox(b, (X, 3.1, -2.35), (4.4, 2.0, 0.8), "chrome2", rot=(-30, 0, 0))
    stick(b, ins, "north", 0.5, 0.5, (1.0, 1.6, 0.15), "quick", sink=0.05)
    # 踵: 後ろへ傾いた板・噴射口
    rbox(b, (X, 1.6, 2.85), (4.6, 2.8, 0.8), "gun", rot=(10, 0, 0))
    cbox(b, (X, 0.4, 3.2), (2.6, 1.0, 1.2), "frame")
    cbox(b, (X, -0.12, 3.2), (1.8, 0.2, 0.8), "thruster_day")
    # 足首の外の関節と、側面の発光線
    octa(b, (X - 2.72, 2.7, 0.3), 1.6, 0.45, "chrome", axis="x")
    cbox(b, (X - 2.66, 0.7, -1.0), (0.18, 0.28, 4.4), "glow_day")
    # タラリア: 踵の外側から後ろへ扇に開く三枚羽
    w = s.part("boots", "talaria_r", b, pivot=(X - 2.8, 2.4, 1.6))
    octa(w, (X - 2.9, 2.4, 1.7), 1.6, 0.6, "chrome", axis="x")
    wing(w, (X - 2.95, 3.4, 0.9), (X - 2.95, 2.2, 1.9), (X - 4.6, 8.2, 6.4), 0.32, "feather",
         n=4, edge="glow_day")
    wing(w, (X - 3.0, 2.8, 1.4), (X - 3.0, 1.7, 2.3), (X - 4.9, 5.4, 8.0), 0.3, "feather",
         n=3)
    wing(w, (X - 2.95, 2.0, 1.9), (X - 2.95, 1.0, 2.6), (X - 4.2, 2.6, 7.6), 0.28, "feather2",
         n=3, edge="glow_soft_day")


# ---------------------------------------------------------------------------
#  脚（膝が広く足首が細い先細りの脛・尖った膝・鏡面の腿）
# ---------------------------------------------------------------------------
def legs(s):
    X = LEG_X
    g = s.part("legs", "greave_r", "rightLeg")
    cbox(g, (X, 6.2, 0.0), (5.2, 4.6, 5.3), "gun")                       # 脛の殻
    cbox(g, (X, 3.65, 0.0), (5.25, 0.7, 5.35), "frame")                  # 細い足首の帯
    # 脛の前: 上で広く下で細い鏡面の V（二枚）と発光の稜線
    sh = rbox(g, (X - 0.95, 6.4, -2.92), (2.1, 4.8, 0.7), "chrome", rot=(4, 22, -5))
    shl = line_on(g, sh, "north", (0.2, 0.08), (0.05, 0.9), 0.2, 0.16, "glow_day")
    mirror_x(g, sh, shl, about=X)
    # 脛の外: 上で外へ開く板（先細りの輪郭）と、液体金属の流れ
    so = rbox(g, (X - 2.72, 6.7, 0.2), (0.55, 4.0, 4.4), "rip_day", rot=(0, 0, -6))
    line_on(g, so, "west", (0.05, 0.25), (0.95, 0.9), 0.2, 0.16, "glow_day")
    rbox(g, (X + 2.72, 6.7, 0.2), (0.55, 4.0, 4.4), "gun", rot=(0, 0, 6))
    # 膝: 関節の帯・上へ尖る鏡面の膝当て・宝玉
    cbox(g, (X, 8.85, 0.0), (5.35, 1.2, 5.4), "frame")
    kn = bevel(g, (X, 8.7, -2.95), (3.0, 2.4, 0.9), "chrome", cut=0.45, axis="z")
    taper(g, (X, 9.6, -2.95), (X, 11.2, -2.7), 2.3, 0.5, 2, "chrome", round_=False)
    rbox(g, (X, 8.6, -3.5), (0.8, 0.8, 0.4), "gem_accent", rot=(0, 0, 45))
    # ふくらはぎ: 上が張り出し、下へ細る鏡面の板と排気口
    calf = rbox(g, (X, 6.9, 2.95), (4.8, 3.8, 0.8), "chrome2", rot=(-14, 0, 0))
    stick(g, calf, "south", 0.5, 0.45, (2.2, 2.2, 0.3), "vent_day", sink=0.1)
    # 腿: ガンメタルの筒に鏡面の前板、外側の型番、液体金属の筋
    t = s.part("legs", "thigh_r", "rightLeg", pivot=(X, 11.6, 0))
    cbox(t, (X, 10.75, 0.0), (5.2, 3.4, 5.3), "gun")
    th = rbox(t, (X, 10.6, -2.85), (4.4, 3.2, 0.6), "chrome", rot=(-5, 0, 0))
    stick(t, th, "north", 0.3, 0.5, (1.0, 3.0, 0.12), "quick", sink=0.04)
    line_on(t, th, "north", (0.8, 0.1), (0.62, 0.92), 0.2, 0.16, "glow_day")
    cbox(t, (X - 2.62, 10.6, 0.3), (0.5, 2.6, 3.8), "serial_day")
    rbox(t, (X, 10.8, 2.82), (4.4, 2.8, 0.6), "chrome2", rot=(6, 0, 0))


# ---------------------------------------------------------------------------
#  腰（細いベルト・下を指す菱形・後ろへ流れる細い草摺）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    cbox(w, (0, 12.55, 0), (9.3, 1.4, 5.7), "frame")
    gd = cbox(w, (-2.6, 12.9, -2.92), (3.4, 0.2, 0.2), "glow_day")
    mx(w, gd)
    octa(w, (0, 12.55, -3.0), 2.0, 0.6, "chrome", axis="z")              # バックル
    octa(w, (0, 12.55, -3.35), 1.0, 0.3, "core", axis="z")
    rbox(w, (0, 10.8, -2.95), (2.2, 2.2, 0.6), "chrome", rot=(-10, 0, 45))   # 下を指す菱形
    # 草摺: 細く、後ろへ流れる一枚（発光の縁）
    t1 = rbox(w, (-4.95, 10.7, 0.8), (0.5, 3.0, 4.2), "chrome2", rot=(-12, 0, 8))
    t2 = line_on(w, t1, "west", (0.05, 0.25), (0.95, 0.75), 0.2, 0.16, "glow_day")
    mx(w, t1, t2)
    rbox(w, (0, 10.9, 2.92), (5.6, 2.2, 0.6), "gun", rot=(10, 0, 0))     # 後ろ垂れ


# ---------------------------------------------------------------------------
#  胴（最小の殻に沿うガンメタル・細い V の鏡面の胸板・液体金属の腹・二重の輪の星核）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    bevel(c, (0, 21.1, 0.0), (9.4, 6.0, 5.6), "gun", cut=0.35, axis="y")   # 胸郭（殻に沿う）
    cbox(c, (0, 16.0, -2.62), (5.0, 4.6, 0.5), "frame")                     # 腹の下地
    # 腹: 中央の鏡面の稜と、下へ細くなる液体金属の板
    cbox(c, (0, 16.0, -2.95), (0.6, 4.4, 0.5), "chrome")
    for y, wd in ((17.25, 2.0), (16.0, 1.8), (14.75, 1.55)):
        a = rbox(c, (-wd / 2 - 0.4, y, -2.92), (wd, 1.1, 0.5), "quick", rot=(-10, 10, 0))
        mx(c, a)
    # 脇腹: 細い斜めの板と発光の線（胴を絞って見せる）
    ob = rbox(c, (-3.55, 16.2, -2.25), (1.0, 4.4, 0.9), "chrome2", rot=(0, 38, -8))
    obl = line_on(c, ob, "north", (0.5, 0.05), (0.5, 0.95), 0.2, 0.16, "glow_day")
    mx(c, ob, obl)
    # 胸板: 中央で前へ折れる細い鏡面の V（二枚）。外の縁に昼/夜の発光線
    pec = rbox(c, (-1.75, 21.3, -3.0), (3.3, 4.6, 0.6), "chrome", rot=(4, 22, 9))
    pl1 = line_on(c, pec, "north", (0.04, 0.95), (0.25, 0.05), 0.22, 0.18, "glow_day")
    flow = stick(c, pec, "north", 0.62, 0.62, (0.9, 2.2, 0.12), "quick", sink=0.04)
    # 鎖骨の板（襟へ流れる）と胸の下の細い板
    clv = rbox(c, (-3.0, 23.6, -2.2), (3.0, 1.0, 1.6), "chrome2", rot=(-20, 10, -14))
    low = rbox(c, (-1.9, 18.55, -2.85), (3.0, 1.1, 0.6), "gun", rot=(-8, 14, 16))
    lol = line_on(c, low, "north", (0.05, 0.5), (0.95, 0.5), 0.18, 0.14, "glow_soft_day")
    mx(c, pec, pl1, flow, clv, low, lol)
    # 胸の脇: 斜めに流れる液体金属の筋（ガンメタルの上）
    sf = rbox(c, (-4.75, 21.0, -0.6), (0.3, 4.6, 1.0), "quick", rot=(-28, 0, 0))
    fv = cbox(c, (-4.82, 20.2, 1.2), (0.2, 2.2, 1.6), "vent_day")
    mx(c, sf, fv)
    # 襟（首の両脇へ低く流れる）
    col = rbox(c, (-3.0, 24.35, 0.4), (2.0, 1.0, 4.6), "gun", rot=(0, 0, -16))
    colt = stick(c, col, "up", 0.5, 0.5, (0.4, 4.2, 0.18), "glow_soft_day", sink=0.08)
    mx(c, col, colt)
    # 星核: 黒い菱形の台 → 鏡面の輪 → 水星（太陽側が橙に光る）→ 光の輪
    rbox(c, (0, 20.4, -3.45), (3.0, 3.0, 0.7), "dark", rot=(0, 0, 45))
    ring(c, (0, 20.4, -3.85), 1.7, 12, (0, 0.28, 0.4), "chrome", axis="z")
    cbox(c, (0, 20.4, -4.05), (2.0, 2.0, 0.8), "core")
    gl = s.fx("glow", "core", c, pivot=(0, 20.4, -4.3))
    ring(gl, (0, 20.4, -4.25), 1.3, 10, (0, 0.18, 0.22), "glow_night", axis="z")
    ring(gl, (0, 20.4, -4.1), 2.15, 14, (0, 0.14, 0.16), "glow_soft_day", axis="z",
         a0=-150, a1=-30)


# ---------------------------------------------------------------------------
#  背中（背板・背骨・二基の細いイオン・スラスター）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    cbox(bk, (0, 18.6, 2.85), (8.4, 10.0, 0.5), "gun")                     # 背板
    cbox(bk, (0, 18.4, 3.35), (2.0, 8.6, 0.7), "frame")                    # 背骨
    for i in range(4):
        cbox(bk, (0, 15.6 + i * 1.9, 3.75), (1.3, 0.45, 0.25), "chrome")  # 背骨の節
    bevel(bk, (0, 20.8, 3.9), (3.6, 4.2, 1.6), "chrome2", cut=0.5, axis="z")  # 小さな背嚢
    cbox(bk, (0, 20.8, 4.72), (0.28, 3.2, 0.12), "glow_white")
    cbox(bk, (0, 18.2, 3.75), (3.2, 0.7, 0.9), "hazard")
    rbox(bk, (0, 23.5, 3.4), (5.4, 0.8, 1.4), "gun", rot=(20, 0, 0))
    # 肩甲骨の板（後ろへ流れる）
    sc = rbox(bk, (-2.6, 21.6, 3.05), (2.6, 3.2, 0.5), "chrome", rot=(6, -14, -10))
    scl = line_on(bk, sc, "south", (0.1, 0.9), (0.85, 0.1), 0.2, 0.16, "glow_day")
    mx(bk, sc, scl)
    # イオン・スラスター（右）: 細長い胴・鏡面の帯・吸気の尖頭・ノズル・発光の輪・炎
    th = s.part("back", "thruster_r", bk, pivot=(-2.5, 21.6, 4.4), rotation=(12, 0, -4))
    octa(th, (-2.5, 18.3, 4.4), 1.6, 6.2, "chrome", axis="y")
    for y in (20.6, 16.6):
        octa(th, (-2.5, y, 4.4), 1.85, 0.36, "frame", axis="y")
    octa(th, (-2.5, 18.6, 4.4), 1.66, 1.4, "glow_soft_day", axis="y", style2="chrome2")
    taper(th, (-2.5, 21.3, 4.4), (-2.5, 23.4, 4.4), 1.5, 0.35, 2, "chrome")
    octa(th, (-2.5, 14.7, 4.4), 2.0, 1.2, "gun", axis="y")
    ring(th, (-2.5, 14.05, 4.4), 0.8, 8, (0, 0.22, 0.24), "glow_day", axis="y")
    cbox(th, (-2.5, 14.0, 4.4), (1.4, 0.2, 1.4), "thruster_day")
    wing(th, (-3.2, 17.6, 4.4), (-3.2, 15.2, 4.4), (-4.4, 14.0, 5.6), 0.26, "gun", n=3)
    fx = s.fx("thrust", "r", th, pivot=(-2.5, 13.9, 4.4))
    taper(fx, (-2.5, 13.9, 4.4), (-2.5, 7.0, 4.4), 1.5, 0.3, 3, "flame_day")
    taper(fx, (-2.5, 13.85, 4.4), (-2.5, 10.0, 4.4), 0.75, 0.2, 2, "flame_core_day",
          round_=False)


# ---------------------------------------------------------------------------
#  液体金属の滴（背中の後ろを二重の軌道で回る）
# ---------------------------------------------------------------------------
def droplets(s):
    C = (0.0, 18.6, 8.6)
    d = s.part("extra", "droplets", "body", pivot=C)
    sp = s.fx("spin", "drops", d, pivot=C)
    for k in range(4):
        a = np.radians(k * 90 + 45)
        bead(sp, (C[0] + np.sin(a) * 4.8, C[1] + np.cos(a) * 4.8, C[2]), 0.8)
    sp2 = s.fx("spin", "drops2", d, pivot=(C[0], C[1], C[2] - 0.3))
    for k in range(3):
        a = np.radians(k * 120 + 60)
        bead(sp2, (C[0] + np.sin(a) * 2.8, C[1] + np.cos(a) * 2.8, C[2] - 0.3), 0.55)
    # 軌道の中心: 液体金属の核と細い光の輪
    cg = s.fx("glow", "drops", d, pivot=C)
    bead(cg, C, 0.6)
    ring(cg, C, 1.15, 10, (0, 0.14, 0.14), "glow_soft_night", axis="z")


# ---------------------------------------------------------------------------
#  腕（殻に沿う上腕・後ろへ流れる肘のヒレ・外側に刃のヒレの鏡面の篭手）
# ---------------------------------------------------------------------------
def arms(s):
    ar = s.part("arms", "upper_r", "rightArm", pivot=(ARM_X, 20.0, 0))
    cbox(ar, (-6.0, 20.6, 0.0), (5.2, 4.8, 5.3), "gun")
    op = rbox(ar, (-8.66, 20.2, 0.2), (0.3, 3.6, 3.4), "stripe_day", rot=(0, 0, 3))
    cbox(ar, (-6.0, 18.05, 0.0), (5.35, TRIM_W, 5.4), "chrome")
    el = s.part("arms", "elbow_r", "rightArm", pivot=(ARM_X, 16.8, 0))
    cbox(el, (-6.0, 16.95, 0.0), (5.25, 1.4, 5.35), "frame")
    octa(el, (-8.45, 16.95, 0.2), 1.5, 0.45, "chrome", axis="x")
    octa(el, (-8.68, 16.95, 0.2), 0.65, 0.2, "glow_day", axis="x")
    taper(el, (-6.2, 16.9, 2.4), (-6.5, 18.1, 4.9), 1.8, 0.35, 2, "chrome", round_=False)
    # 前腕: 鏡面の篭手と、外側の刃のヒレ（後ろへ流れて尖る）
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=(ARM_X, 15.0, 0))
    cbox(fa, (-6.0, 14.95, 0), (5.2, 3.1, 5.3), "chrome2")
    fq = rbox(fa, (-6.05, 14.9, -2.75), (4.0, 3.0, 0.5), "chrome", rot=(-6, 0, 0))
    stick(fa, fq, "north", 0.7, 0.5, (0.8, 2.8, 0.12), "quick", sink=0.04)
    line_on(fa, fq, "north", (0.28, 0.06), (0.28, 0.94), 0.2, 0.16, "glow_day")
    wing(fa, (-8.75, 16.2, -1.4), (-8.75, 13.7, -1.6), (-8.95, 16.6, 5.0), 0.4, "rip_day",
         n=3, curve=0.1, edge="glow_day")
    rbox(fa, (-6.1, 14.85, 2.75), (4.0, 3.0, 0.5), "gun", rot=(6, 0, 0))
    cbox(fa, (-6.0, 13.45, 0), (5.4, TRIM_W, 5.5), "chrome")
    # 拳: 甲の鏡面・指の関節・二節の指・親指
    h = s.part("arms", "gauntlet_r", "rightArm", pivot=(ARM_X, 13.2, 0))
    cbox(h, (-6.0, 12.15, 0.0), (5.25, 2.7, 5.45), "gun")
    rbox(h, (-6.0, 12.55, -2.92), (4.4, 1.3, 0.6), "chrome", rot=(-10, 0, 0))
    for i in range(4):
        x = -7.65 + i * 1.1
        cbox(h, (x, 12.6, -3.3), (0.7, 0.4, 0.3), "frame")
        rbox(h, (x, 11.7, -2.88), (0.8, 1.2, 0.6), "chrome2", rot=(18, 0, 0))
        rbox(h, (x, 10.85, -2.5), (0.75, 0.9, 0.55), "chrome2", rot=(40, 0, 0))
    rbox(h, (-3.25, 12.2, -1.3), (0.6, 1.8, 1.4), "chrome2", rot=(0, 0, -10))
    rbox(h, (-8.66, 12.3, 0), (0.4, 0.9, 0.9), "gem_accent", rot=(45, 0, 0))


# ---------------------------------------------------------------------------
#  肩（肩に沿う薄い涙滴形のフェアリング: 前が丸く、後ろへ尾を引く）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "fairing_r", "rightArm")
    shell = bevel(p, (-6.1, 24.85, 0.0), (5.4, 1.2, 5.8), "chrome", cut=0.5, axis="x",
                  rot=(0, 0, -8))
    line_on(p, shell[0], "up", (0.18, 0.05), (0.18, 0.95), 0.2, 0.16, "glow_day")
    stick(p, shell[0], "up", 0.6, 0.5, (1.2, 4.6, 0.12), "quick", sink=0.04)
    # 前の丸い鼻と、後ろへ細く流れる尾
    rbox(p, (-6.2, 24.6, -3.0), (4.6, 1.3, 0.8), "chrome2", rot=(-30, 0, -8))
    taper(p, (-6.4, 24.9, 2.8), (-6.9, 25.4, 6.4), 2.4, 0.45, 3, "chrome", round_=False)
    # 外の薄い垂れ（上腕に沿う）
    l1 = rbox(p, (-8.75, 23.0, 0.2), (0.4, 2.4, 4.6), "emblem_day", rot=(0, 0, 6))
    stick(p, l1, "west", 0.5, 0.04, (4.2, TRIM_W, 0.16), "chrome", sink=0.04)


# ---------------------------------------------------------------------------
#  兜（前へ尖る眉庇・後ろへ掃き上げる冠と稜・ヘルメスの翼・V 字のスリット）
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.9, 0.3), (9.7, 4.0, 10.0), "chrome", cut=0.9, axis="z")    # 冠の台
    # 冠の屋根: 中央の稜へ上る二枚（外の端が下がる）
    rf = rbox(hm, (-2.45, 33.3, 0.6), (5.2, 0.7, 9.6), "chrome", rot=(0, 0, -16))
    rfl = line_on(hm, rf, "up", (0.08, 0.06), (0.08, 0.9), 0.2, 0.16, "glow_soft_day")
    mx(hm, rf, rfl)
    rbox(hm, (0, 32.3, -4.95), (8.4, 2.4, 0.8), "chrome2", rot=(-36, 0, 0))     # 額の斜面
    rbox(hm, (0, 32.3, 5.5), (8.4, 2.4, 0.8), "chrome2", rot=(36, 0, 0))       # 後ろの斜面
    # 稜: 額から頭頂を越えて後ろへ掃き上がり、後頭部の先で尾になる
    polyline(hm, [(0, 32.4, -5.6), (0, 34.6, -2.6), (0, 35.0, 1.2), (0, 34.6, 5.0),
                  (0, 33.2, 9.2)], [0.9, 0.85, 0.75, 0.55], [1.2, 1.3, 1.2, 0.9], "chrome")
    polyline(hm, [(0, 33.1, -5.45), (0, 35.3, -2.45), (0, 35.7, 1.2), (0, 35.3, 5.0)],
             0.95, 0.2, "glow_white")
    cbox(hm, (0, 27.0, 5.0), (8.8, 4.8, 0.7), "gun")                           # 後頭部
    rbox(hm, (0, 24.3, 5.25), (8.4, 1.8, 0.7), "gun", rot=(20, 0, 0))         # しころ
    # 側板と耳の円盤
    sd = cbox(hm, (-4.92, 27.0, 0.3), (0.8, 4.6, 8.6), "gun")
    sdl = stick(hm, sd, "west", 0.5, 0.12, (7.6, 0.22, 0.14), "glow_soft_day", sink=0.05)
    ear = octa(hm, (-5.45, 28.4, 0.6), 2.4, 0.5, "chrome", axis="x")
    eg = octa(hm, (-5.75, 28.4, 0.6), 1.0, 0.25, "glow_day", axis="x")
    mx(hm, sd, sdl, ear, eg)
    # 眉庇: 中央で前へ尖る鏡面の V（バイザーの上にかぶさる）
    br = rbox(hm, (-2.1, 30.0, -5.6), (4.6, 0.8, 2.0), "chrome", rot=(6, 26, -6))
    brl = line_on(hm, br, "north", (0.05, 0.3), (0.95, 0.3), 0.2, 0.14, "glow_day")
    mx(hm, br, brl)
    taper(hm, (0, 30.1, -6.2), (0, 29.8, -7.8), 1.4, 0.3, 2, "chrome", round_=False)
    # 顔: 中央で前へ折れた二枚の面頬と鏡面の稜、尖った顎、頬当て
    fc = rbox(hm, (-2.0, 26.5, -5.1), (4.2, 4.6, 0.7), "chrome2", rot=(0, 16, 0))
    ck = rbox(hm, (-3.7, 25.6, -3.5), (1.2, 3.6, 3.0), "gun", rot=(0, 34, -6))
    ckl = line_on(hm, ck, "west", (0.15, 0.2), (0.15, 0.85), 0.2, 0.16, "glow_day")
    mx(hm, fc, ck, ckl)
    cbox(hm, (0, 26.0, -5.7), (0.45, 3.6, 0.45), "chrome")
    cbox(hm, (0, 26.3, -4.75), (7.6, 4.6, 0.3), "frame")
    taper(hm, (0, 24.6, -5.0), (0, 23.4, -5.6), 2.6, 0.8, 2, "chrome", round_=False)  # 顎
    # ヘルメスの翼: こめかみから後ろ上へ大きく開く三枚の三角の羽根
    wg = s.part("helmet", "wing_r", hm, pivot=(-5.6, 28.6, 0.8))
    octa(wg, (-5.85, 28.6, 1.0), 2.0, 0.8, "chrome", axis="x")
    wing(wg, (-5.65, 31.2, -0.8), (-5.65, 28.4, 1.0), (-8.6, 37.0, 7.4), 0.4, "feather",
         n=4, curve=0.1, edge="glow_day")
    wing(wg, (-5.8, 30.0, 0.6), (-5.8, 27.4, 2.0), (-9.4, 33.0, 9.4), 0.36, "feather",
         n=4, curve=0.1)
    wing(wg, (-5.8, 28.4, 1.6), (-5.8, 26.4, 2.6), (-8.4, 28.6, 8.6), 0.32, "feather2",
         n=3, curve=0.12, edge="glow_soft_day")
    # バイザー: 顔の中央で鋭く折れた V 字のスリット一本（暗い溝 + シアンの光）
    vz = s.part("visor", "eye", "head")
    vd = rbox(vz, (-1.8, 28.1, -5.6), (4.0, 1.1, 0.4), "dark", rot=(0, 16, 20))
    mirror_x(vz, vd)
    fg = s.fx("glow", "visor", vz, pivot=(0, 27.6, -5.8))
    half = rbox(fg, (-1.8, 28.1, -5.8), (3.8, 0.5, 0.3), "visor", rot=(0, 16, 20))
    mirror_x(fg, half)
