# -*- coding: utf-8 -*-
"""木星 — 雷帝機装 ゼウス（Zeus Frame）。

ガス惑星の王。全形態でいちばん重い体格: 広い肩と分厚い胸郭、クリーム（帯 = zone）と褐色・錆色
（縞 = belt）を交互に重ねた帯状の装甲。胸の中央に回転する大赤斑の渦（fx_spin_grs）を重い襟の枠が囲み、
両肩に電光の輪をまとうテスラコイルの塔、王冠の兜（尖りの帯 + 稲妻色のバイザー + 機械の髭）、
コイルを巻いた拳の篭手、ベルトの星核（木星の球）とその左右に並ぶガリレオ衛星（イオ・エウロパ・
ガニメデ・カリスト。それぞれが自転する fx_spin）、背中に稲妻形の翼と嵐のタービン、双発スラスター。
発光は電光の青（PLANETS.jupiter.glow）。

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。右側だけ作り `_r` を付ける → 左は自動で鏡映。
回転（統合版の rotation）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く /
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import math

from astro_common import (bevel, beam, cbox, chamfer, line_on, octa, polyline, rbox, ring, stick,
                          taper)
from astro_suit import ARM_X, LEG_X, Suit, mirror_x

CREAM = (234, 216, 184)      # 帯（zone）
TAN = (201, 142, 90)         # 縞（belt）
RUST = (217, 71, 43)         # 大赤斑・差し色
BROWN = (52, 38, 32)
VOLT = (140, 236, 255)       # 電光
TRIM_W = 0.4


# ===========================================================================
#  塗り（astro_paint.suit_styles("jupiter") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate": {"line": (110, 84, 60)},
    "plate2": {"line": (92, 52, 28)},
    "accent": {"line": (96, 28, 16)},
    # 縞の入った帯（木星の帯と縞）
    "zone": {"kind": "armor", "base": CREAM, "light": (252, 244, 226), "dark": (186, 160, 124),
             "line": (110, 84, 60), "panel": 0,
             "stripe": {"dir": "h", "period": 7, "width": 2, "color": (214, 176, 128), "k": 0.7}},
    "belt": {"kind": "armor", "base": TAN, "light": (232, 186, 140), "dark": (150, 96, 58),
             "line": (92, 52, 28), "panel": 0,
             "stripe": {"dir": "h", "period": 6, "width": 2, "color": (176, 92, 54), "k": 0.75}},
    "rustband": {"kind": "armor", "base": RUST, "light": (246, 132, 96), "dark": (150, 44, 24),
                 "line": (90, 24, 12), "panel": 0,
                 "stripe": {"dir": "h", "period": 5, "width": 1, "color": (240, 120, 80), "k": 0.5}},
    "copper": {"kind": "trim", "base": (206, 120, 70), "light": (255, 200, 150),
               "dark": (120, 58, 30), "line": (64, 28, 12)},
    "coil": {"kind": "trim", "base": (196, 110, 62), "light": (255, 188, 136),
             "dark": (110, 52, 26), "line": (60, 26, 10)},
    "gold": {"base": (232, 184, 84), "light": (255, 242, 180), "dark": (150, 96, 34)},
    "volt": {"kind": "glowline", "glow": VOLT, "light": (236, 252, 255), "bevel": False,
             "outline": False},
    "volt_core": {"kind": "energy", "glow": (110, 210, 255), "light": (240, 252, 255),
                  "outline": False, "bevel": False},
    "visor": {"glow": (110, 222, 255), "light": (236, 252, 255), "deep": (20, 70, 150),
              "emit": 18},
    "flame": {"glow": (120, 220, 255), "light": (236, 252, 255), "deep": (30, 90, 200)},
    "flame_core": {"kind": "flame", "glow": (210, 248, 255), "light": (255, 255, 255),
                   "deep": (110, 200, 255), "bevel": False, "outline": False},
    "thruster": {"glow": (120, 220, 255), "light": (240, 255, 255), "deep": (24, 70, 150)},
    # 大赤斑（回る渦）
    "grs": {"kind": "energy", "glow": (226, 92, 52), "light": (255, 214, 170),
            "outline": False, "bevel": False, "waves": 5},
    "grs_arm": {"kind": "glowline", "glow": (255, 150, 96), "light": (255, 236, 214),
                "bevel": False, "outline": False, "emit": 40},
    "grs_eye": {"kind": "gem", "glow": (255, 120, 70), "deep": (120, 26, 12), "outline": False,
                "bevel": False},
    # ガリレオ衛星
    "io": {"kind": "planet", "planet": "venus", "bevel": False, "outline": False, "vary": 0},
    "europa": {"kind": "planet", "planet": "saturn", "bevel": False, "outline": False, "vary": 0,
               "spin": 90},
    "ganymede": {"kind": "planet", "planet": "luna", "bevel": False, "outline": False, "vary": 0},
    "callisto": {"kind": "armor", "base": (92, 82, 74), "light": (140, 128, 116),
                 "dark": (52, 46, 42), "line": (30, 26, 22), "panel": 0, "noise": 10,
                 "sheen": False},
    "core": {"halo": VOLT, "spin": 31},
    "serial": {"text": "ZS-05", "under": {"kind": "armor", "base": TAN, "panel": 0,
                                         "line": (92, 52, 28)},
               "ink": (60, 30, 16)},
    "hazard": {"c1": (140, 236, 255), "c2": (52, 38, 32)},
    "emblem": {"under": {"kind": "armor", "base": CREAM, "panel": 0, "line": (110, 84, 60)},
               "color": VOLT},
    "face": {"kind": "armor", "base": (226, 214, 196), "panel": 0, "line": (90, 70, 54)},
    "beard": {"kind": "armor", "base": (244, 236, 220), "light": (255, 252, 244),
              "dark": (196, 180, 156), "line": (120, 100, 78), "panel": 0, "sheen": False,
              "stripe": {"dir": "v", "period": 3, "width": 1, "color": (200, 182, 156), "k": 0.6}},
    "grille": {"kind": "vent", "base": (70, 52, 42), "glow": (60, 120, 170), "deep": (14, 24, 40),
               "slat": 2},
}

# ===========================================================================
#  部位アニメ（Molang。q.anim_time は 12 秒でループ → 周波数は 30°/秒の倍数）
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        "fx_spin_grs": {"rotation": [0, 0, "q.anim_time * 60.0"]},
        "fx_spin_fan": {"rotation": [0, 0, "-q.anim_time * 120.0"]},
        "fx_spin_arc_r": {"rotation": [0, "q.anim_time * 180.0", 0]},
        "fx_spin_io": {"rotation": [0, "q.anim_time * 120.0", 0]},
        "fx_spin_europa": {"rotation": [0, "q.anim_time * 90.0", 0]},
        "fx_spin_ganymede": {"rotation": [0, "-q.anim_time * 60.0", 0]},
        "fx_spin_callisto": {"rotation": [0, "-q.anim_time * 30.0", 0]},
        "extra_wing_r": {"rotation": ["math.sin(q.anim_time * 60.0) * 2.0", 0,
                                      "math.sin(q.anim_time * 90.0) * 1.5"]},
    },
    "thrust": {
        "extra_wing_r": {"rotation": ["v.astro_air * 16.0", 0, "-v.astro_air * 10.0"]},
        "fx_spin_arc_r": {"rotation": [0, "v.astro_air * q.anim_time * 360.0", 0]},
    },
    "sprint": {
        "extra_wing_r": {"rotation": ["v.astro_run * 22.0", 0, "-v.astro_run * 6.0"]},
    },
}


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
    wings(s)


# ---------------------------------------------------------------------------
#  ブーツ（重い。足首に錆色の帯、つま先は褐色の縞、踵に噴射口）
# ---------------------------------------------------------------------------
def boots(s):
    X = LEG_X - 0.3
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (X, -0.35, -0.55), (6.0, 0.9, 7.8), "frame")                 # 靴底
    bevel(b, (X, 1.95, -0.2), (5.8, 3.7, 6.5), "plate", cut=0.7, axis="y")  # 足の殻
    toe = rbox(b, (X, 1.3, -3.7), (5.4, 2.4, 1.6), "belt", rot=(-36, 0, 0))
    stick(b, toe, "north", 0.5, 0.55, (0.6, 1.4, 0.25), "volt", sink=0.05)
    cbox(b, (X, 0.35, -4.5), (5.0, 0.8, 0.7), "copper")                  # つま先の金具
    rbox(b, (X, 3.65, -2.6), (4.6, 2.0, 0.9), "rustband", rot=(-30, 0, 0))  # 甲
    cbox(b, (X, 4.05, 0.15), (6.0, 0.9, 6.1), "accent")                  # 足首の帯
    cbox(b, (X, 4.05, 0.15), (6.1, 0.25, 6.2), "copper")
    rbox(b, (X, 1.9, 3.3), (5.2, 3.2, 1.0), "plate_b", rot=(8, 0, 0))    # 踵
    cbox(b, (X, 0.45, 3.55), (3.2, 1.0, 1.1), "frame")                   # 踵の噴射口
    cbox(b, (X, -0.05, 3.55), (2.4, 0.2, 0.8), "thruster")
    octa(b, (X - 3.05, 2.6, 0.3), 2.3, 0.6, "frame", axis="x")           # 足首の関節（外）
    octa(b, (X - 3.38, 2.6, 0.3), 1.2, 0.3, "volt", axis="x")
    cbox(b, (X - 2.98, 1.0, -0.8), (0.22, 0.3, 4.4), "volt")              # 外側の発光線


# ---------------------------------------------------------------------------
#  脚（帯を巻いた脛・丸い膝当て・分厚い腿）
# ---------------------------------------------------------------------------
def legs(s):
    X = LEG_X - 0.2
    g = s.part("legs", "greave_r", "rightLeg")
    bevel(g, (X, 6.2, 0.05), (5.7, 4.9, 5.9), "plate", cut=0.8, axis="y")     # 脛の殻（帯 = zone）
    chamfer(g, (X, 5.3, 0.05), (6.0, 0.9, 6.2), "rustband", cut=0.8, axis="y")  # 縞（錆色）
    chamfer(g, (X, 7.1, 0.05), (5.9, 0.7, 6.1), "belt", cut=0.8, axis="y")      # 縞（褐色）
    keel = rbox(g, (X - 0.7, 6.2, -3.2), (1.6, 4.2, 0.8), "plate2", rot=(0, 22, 0))
    mirror_x(g, keel, about=X)                                            # 脛の稜（V 字）
    line_on(g, keel, "north", (0.3, 0.1), (0.5, 0.5), 0.26, 0.2, "volt")   # 稲妻の線
    line_on(g, keel, "north", (0.5, 0.5), (0.3, 0.6), 0.26, 0.2, "volt")
    line_on(g, keel, "north", (0.3, 0.6), (0.55, 0.92), 0.26, 0.2, "volt")
    cbox(g, (X, 8.85, 0.05), (5.5, 1.3, 5.5), "frame")                     # 膝の関節
    # 膝当て: 丸い褐色の盾 + 銅の縁 + 電光の宝玉
    octa(g, (X, 8.9, -3.05), 4.0, 0.8, "copper", axis="z")
    octa(g, (X, 8.9, -3.35), 3.3, 0.8, "plate2", axis="z")
    rbox(g, (X, 8.9, -3.8), (1.1, 1.1, 0.4), "gem", rot=(0, 0, 45))
    rbox(g, (X, 10.25, -2.9), (3.4, 0.9, 1.0), "plate", rot=(32, 0, 0))   # 膝の庇
    calf = rbox(g, (X, 6.2, 3.05), (4.8, 4.2, 1.0), "plate_b", rot=(-8, 0, 0))
    stick(g, calf, "south", 0.5, 0.5, (2.8, 2.4, 0.3), "vent", sink=0.1)
    fin = rbox(g, (X - 3.1, 6.6, 0.8), (0.7, 3.8, 3.6), "plate2", rot=(-10, 0, -8))
    line_on(g, fin, "west", (0.15, 0.25), (0.85, 0.7), 0.24, 0.2, "volt")
    # 腿: 分厚い殻・正面の帯の板・外側の型番板
    t = s.part("legs", "thigh_r", "rightLeg", pivot=(X, 11.6, 0))
    cbox(t, (X, 10.9, 0.05), (5.8, 3.4, 5.8), "plate_b")
    th = rbox(t, (X, 10.9, -3.05), (5.0, 3.0, 0.8), "zone", rot=(-5, 0, 0))
    line_on(t, th, "north", (0.85, 0.1), (0.85, 0.85), 0.26, 0.2, "volt")
    cbox(t, (X, 9.35, -3.1), (4.6, TRIM_W, 0.6), "copper")
    cbox(t, (X - 3.05, 10.8, 0.3), (0.6, 3.0, 4.2), "plate2",
         decals={"west": {"decal": "serial", "text": "ZS-05", "ink": (60, 30, 16)}})


# ---------------------------------------------------------------------------
#  腰（太いベルト・星核のバックル・ガリレオ衛星・草摺）
# ---------------------------------------------------------------------------
def moon(s, w, name, x, style, size=1.2):
    """ベルトに嵌めたガリレオ衛星: 銅の受け座 + 自転する球（fx_spin_<name>）。"""
    z = -3.45
    octa(w, (x, 12.55, z + 0.05), 1.65, 0.6, "copper", axis="z")
    sp = s.fx("spin", name, w, pivot=(x, 12.55, z - 0.6))
    cbox(sp, (x, 12.55, z - 0.6), (size, size, size), style)
    rbox(sp, (x, 12.55, z - 0.6), (size * 0.92, size * 0.92, size * 0.92), style, rot=(0, 45, 0))


def waist(s):
    w = s.part("waist", "belt", "body")
    cbox(w, (0, 12.65, 0), (10.0, 2.0, 6.5), "frame")
    cbox(w, (0, 12.65, 0), (10.2, 1.0, 6.7), "plate2")                   # 褐色の帯
    cbox(w, (0, 13.25, -3.38), (9.4, 0.2, 0.2), "volt")
    cbox(w, (0, 12.05, -3.38), (9.4, 0.2, 0.2), "volt")
    # バックル: 銅の八角の台 + 木星の星核 + 電光の輪（脈動）
    octa(w, (0, 12.55, -3.45), 3.0, 0.7, "copper", axis="z")
    cbox(w, (0, 12.55, -3.85), (2.0, 2.0, 0.6), "core")
    gl = s.fx("glow", "buckle", w, pivot=(0, 12.55, -4.1))
    ring(gl, (0, 12.55, -4.1), 1.35, 8, (0, 0.22, 0.25), "volt", axis="z")
    # ガリレオ衛星（内から イオ・エウロパ ／ ガニメデ・カリスト）
    moon(s, w, "io", -2.05, "io", 1.1)
    moon(s, w, "europa", -3.55, "europa", 1.05)
    moon(s, w, "ganymede", 2.05, "ganymede", 1.25)
    moon(s, w, "callisto", 3.55, "callisto", 1.2)
    # 前垂れ（縞の板）と、両脇の板
    rbox(w, (0, 10.6, -3.2), (3.4, 3.0, 0.8), "belt", rot=(-10, 0, 0))
    cbox(w, (0, 9.25, -3.45), (2.8, TRIM_W, 0.4), "copper")
    fr = rbox(w, (-2.7, 10.85, -3.0), (2.0, 2.4, 0.7), "plate", rot=(-10, 14, 6))
    mirror_x(w, fr)
    # 草摺（腰の横）: 帯 → 錆色 → 銅の縁 → 発光線
    t1 = rbox(w, (-5.45, 10.4, -0.1), (0.9, 4.4, 5.8), "zone", rot=(0, 0, 13))
    t2 = rbox(w, (-5.9, 9.55, -0.1), (0.7, 3.2, 5.2), "rustband", rot=(0, 0, 17))
    t3 = stick(w, t2, "west", 0.5, 0.06, (5.0, TRIM_W, 0.22), "copper", sink=0.05)
    t4 = line_on(w, t1, "west", (0.12, 0.78), (0.88, 0.78), 0.24, 0.2, "volt")
    mirror_x(w, t1, t2, t3, t4)
    rbox(w, (0, 10.8, 3.15), (7.2, 2.8, 0.8), "zone", rot=(10, 0, 0))     # 後ろ垂れ
    cbox(w, (0, 9.45, 3.45), (6.6, TRIM_W, 0.5), "copper")


# ---------------------------------------------------------------------------
#  胴（分厚い胸郭・大赤斑の炉と重い襟・帯を重ねた腹・肩の付け根の盛り上がり）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    # 胸郭: 横に広い八角の殻（上が広く、腹へ絞る）。上半分は褐色の縞の帯
    bevel(c, (0, 21.1, -0.1), (11.4, 7.0, 6.9), "plate", cut=1.1, axis="y")
    chamfer(c, (0, 23.55, -0.1), (11.0, 1.4, 7.0), "belt", cut=1.15, axis="y")
    # 腹: 帯と縞を交互に重ねた四段（上の段が下に重なる）
    for y, wd, dp, st in ((17.2, 10.0, 6.8, "rustband"), (16.1, 9.7, 6.6, "zone"),
                          (15.0, 9.5, 6.4, "belt"), (13.95, 9.3, 6.2, "zone")):
        chamfer(c, (0, y, -0.05), (wd, 1.15, dp), st, cut=0.7, axis="y")
    # 胸板: 炉の左右に、外へ回り込む帯の板（縞入り）と、その下の錆色の縞
    pec = rbox(c, (-3.85, 21.3, -3.45), (3.7, 4.4, 0.9), "zone", rot=(4, 22, 5))
    trim = stick(c, pec, "north", 0.5, 0.97, (3.5, TRIM_W, 0.22), "copper", sink=0.05)
    l1 = line_on(c, pec, "north", (0.15, 0.2), (0.55, 0.38), 0.26, 0.2, "volt")
    l2 = line_on(c, pec, "north", (0.55, 0.38), (0.4, 0.55), 0.26, 0.2, "volt")
    l3 = line_on(c, pec, "north", (0.4, 0.55), (0.85, 0.75), 0.26, 0.2, "volt")
    low = rbox(c, (-3.4, 18.55, -3.2), (3.4, 1.4, 0.8), "rustband", rot=(-6, 18, 8))
    mirror_x(c, pec, trim, l1, l2, l3, low)
    # 大赤斑の炉: 暗い受け座 → 重い襟（銅と暗い金属の八角の枠）→ 金の縁 → 回る渦
    Y = 20.4
    octa(c, (0, Y, -3.55), 4.4, 0.5, "dark", axis="z")
    ring(c, (0, Y, -3.95), 2.5, 8, (0, 0.95, 0.8), "copper", axis="z",
         styles=["copper", "frame"])
    octa(c, (0, Y, -4.0), 4.05, 0.3, "gold", axis="z")
    sp = s.fx("spin", "grs", c, pivot=(0, Y, -4.1))
    octa(sp, (0, Y, -4.1), 3.6, 0.3, "grs", axis="z")
    for k in range(4):                                                    # 渦の腕（4 本の弧）
        pts = []
        for j in range(3):
            a = math.radians(90 * k + j * 40)
            r = 0.45 + j * 0.6
            pts.append((-r * math.sin(a), Y + r * math.cos(a), -4.32))
        polyline(sp, pts, 0.34, 0.18, "grs_arm", overlap=0.2)
    rbox(sp, (0, Y, -4.35), (1.0, 1.0, 0.3), "grs_eye", rot=(0, 0, 45))
    # 肩の付け根の盛り上がり（首の脇から肩当てへ下る斜面）
    yk = rbox(c, (-4.95, 24.35, -0.1), (2.4, 1.3, 6.0), "plate2", rot=(0, 0, -24))
    ykt = stick(c, yk, "up", 0.5, 0.5, (2.0, 5.6, 0.25), "belt", sink=0.1)
    mirror_x(c, yk, ykt)
    # 脇: 帯の板と排気口
    fl = cbox(c, (-5.75, 20.8, 0.4), (0.4, 3.6, 3.4), "plate2")
    fv = cbox(c, (-5.97, 20.7, 0.4), (0.15, 2.4, 2.2), "vent")
    mirror_x(c, fl, fv)


# ---------------------------------------------------------------------------
#  背中（背板・縞の背嚢・嵐のタービン・双発スラスター）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    cbox(bk, (0, 19.0, 3.05), (9.6, 10.0, 0.8), "plate_b")
    cbox(bk, (0, 18.6, 3.7), (2.6, 8.4, 1.0), "frame")
    bevel(bk, (0, 19.9, 4.8), (7.0, 6.8, 2.6), "plate", cut=0.9, axis="z")
    cbox(bk, (0, 22.35, 4.85), (6.4, 1.1, 2.75), "belt")                  # 背嚢の縞
    cbox(bk, (0, 17.45, 4.85), (6.4, 0.9, 2.75), "rustband")
    rbox(bk, (0, 23.4, 4.3), (5.8, 1.0, 2.6), "plate2", rot=(25, 0, 0))
    side = cbox(bk, (-3.55, 19.9, 4.8), (0.3, 4.6, 1.8), "copper")
    mirror_x(bk, side)
    cbox(bk, (0, 16.35, 6.15), (3.6, 0.9, 0.2), "hazard")
    # 嵐のタービン: 銅の縁の丸い吸気口に、回る羽根
    octa(bk, (0, 20.0, 6.15), 3.8, 0.3, "frame", axis="z")
    octa(bk, (0, 20.0, 6.2), 3.2, 0.3, "copper", axis="z")
    cbox(bk, (0, 20.0, 6.3), (2.2, 2.2, 0.2), "volt_core")
    fan = s.fx("spin", "fan", bk, pivot=(0, 20.0, 6.5))
    for k in range(4):
        a = 45 + 90 * k
        r = math.radians(a)
        rbox(fan, (-0.8 * math.sin(r), 20.0 + 0.8 * math.cos(r), 6.47), (0.55, 1.5, 0.16), "frame",
             rot=(0, 0, a + 20))
    cbox(fan, (0, 20.0, 6.55), (0.6, 0.6, 0.2), "copper", rotation=(0, 0, 45))
    # スラスター（右。下後ろへ）
    th = s.part("back", "thruster_r", bk, pivot=(-1.9, 16.9, 5.6), rotation=(16, 0, -6))
    octa(th, (-1.9, 15.6, 5.6), 2.4, 3.0, "plate", axis="y")
    octa(th, (-1.9, 16.35, 5.6), 2.65, 0.4, "copper", axis="y")
    octa(th, (-1.9, 13.6, 5.6), 3.0, 1.4, "frame", axis="y")
    octa(th, (-1.9, 12.95, 5.6), 2.5, 0.25, "volt", axis="y")
    cbox(th, (-1.9, 12.88, 5.6), (2.2, 0.2, 2.2), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.9, 12.85, 5.6))
    taper(fx, (-1.9, 12.85, 5.6), (-1.9, 5.6, 5.6), 2.4, 0.45, 3, "flame")
    taper(fx, (-1.9, 12.8, 5.6), (-1.9, 8.8, 5.6), 1.1, 0.25, 2, "flame_core", round_=False)


# ---------------------------------------------------------------------------
#  腕（帯を巻いた上腕・肘のコイル・広がる篭手・コイルを巻いた拳）
# ---------------------------------------------------------------------------
def arms(s):
    ar = s.part("arms", "upper_r", "rightArm", pivot=(ARM_X, 20.0, 0))
    bevel(ar, (-6.2, 20.4, 0.0), (5.8, 5.6, 6.0), "plate", cut=0.6, axis="y")
    chamfer(ar, (-6.2, 19.4, 0.0), (6.0, 0.9, 6.2), "belt", cut=0.6, axis="y")
    cbox(ar, (-6.2, 18.0, 0.0), (6.0, 0.7, 6.2), "accent")
    cbox(ar, (-6.2, 18.0, 0.0), (6.1, 0.22, 6.3), "copper")
    el = s.part("arms", "elbow_r", "rightArm", pivot=(ARM_X, 16.8, 0))
    cbox(el, (-6.2, 16.9, 0.0), (5.5, 1.5, 5.5), "frame")
    octa(el, (-9.0, 16.9, 0.2), 1.25, 1.5, "volt_core", axis="y")       # 肘のコイル
    for k in range(3):
        octa(el, (-9.0, 16.4 + k * 0.5, 0.2), 1.6, 0.32, "coil", axis="y")
    rbox(el, (-6.4, 17.0, 2.95), (3.2, 2.0, 0.8), "plate2", rot=(-18, 0, 0))
    # 前腕: 手首へ向かって広がる重い篭手
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=(ARM_X, 15.0, 0))
    cbox(fa, (-6.2, 14.85, 0), (5.3, 3.3, 5.5), "plate")
    ob = rbox(fa, (-9.15, 14.75, 0), (0.9, 3.5, 5.3), "belt", rot=(0, 0, 8))
    stick(fa, ob, "west", 0.5, 0.55, (1.1, 2.6, 0.7), "plate", sink=0.1)
    line_on(fa, ob, "west", (0.12, 0.25), (0.4, 0.55), 0.24, 0.2, "volt")
    line_on(fa, ob, "west", (0.4, 0.55), (0.25, 0.62), 0.24, 0.2, "volt")
    line_on(fa, ob, "west", (0.25, 0.62), (0.6, 0.9), 0.24, 0.2, "volt")
    rbox(fa, (-6.3, 14.75, -2.95), (4.4, 3.3, 0.7), "zone", rot=(-8, 0, 0))
    rbox(fa, (-6.3, 14.75, 2.95), (4.4, 3.3, 0.7), "plate_b", rot=(8, 0, 0))
    cbox(fa, (-6.2, 13.3, 0), (6.0, TRIM_W, 6.2), "copper")
    # 拳: 甲の板・指・親指・拳のコイル（銅の巻き線と電光の芯）
    h = s.part("arms", "gauntlet_r", "rightArm", pivot=(ARM_X, 13.2, 0))
    cbox(h, (-6.2, 12.1, 0.0), (5.6, 2.8, 5.8), "plate")
    rbox(h, (-6.2, 12.6, -3.05), (4.8, 1.3, 0.7), "plate2", rot=(-10, 0, 0))
    for i in range(4):
        x = -7.95 + i * 1.17
        rbox(h, (x, 11.65, -3.05), (0.9, 1.2, 0.6), "plate_b", rot=(18, 0, 0))
        rbox(h, (x, 10.8, -2.65), (0.85, 0.9, 0.55), "plate_b", rot=(40, 0, 0))
    octa(h, (-6.2, 12.75, -3.6), 0.6, 4.4, "volt_core", axis="x")       # 拳の電光の芯
    for i in range(4):                                                  # 巻き線
        octa(h, (-7.85 + i * 1.1, 12.75, -3.6), 1.2, 0.5, "coil", axis="x")
    rbox(h, (-3.25, 12.15, -1.3), (0.6, 1.8, 1.4), "plate_b", rot=(0, 0, -10))
    rbox(h, (-9.05, 12.3, 0), (0.4, 1.0, 1.0), "gem", rot=(45, 0, 0))


# ---------------------------------------------------------------------------
#  肩（帯を重ねた大きな肩当て + テスラコイルの塔）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    dome = bevel(p, (-7.5, 24.2, 0.1), (6.8, 3.6, 7.8), "plate", cut=1.2, axis="x",
                 rot=(0, 0, -14))
    stick(p, dome[0], "up", 0.5, 0.5, (1.4, 7.0, 0.3), "rustband", sink=0.15)  # 頂の縞
    rim = rbox(p, (-10.75, 24.0, 0.1), (0.9, 2.4, 8.0), "plate2", rot=(0, 0, -26))
    stick(p, rim, "up", 0.5, 0.5, (0.9, 8.0, 0.3), "copper", sink=0.05)
    # 垂れ（帯の重なり: 錆色 → 褐色の縞 → クリーム）
    l1 = rbox(p, (-10.35, 21.9, 0.1), (1.1, 2.6, 7.4), "rustband", rot=(0, 0, 16),
              decals={"west": {"decal": "emblem", "color": VOLT}})
    stick(p, l1, "west", 0.5, 0.04, (7.0, TRIM_W, 0.22), "copper", sink=0.05)
    l2 = rbox(p, (-10.65, 20.1, 0.15), (1.0, 2.2, 6.8), "belt", rot=(0, 0, 12))
    stick(p, l2, "west", 0.5, 0.05, (6.4, TRIM_W, 0.22), "copper", sink=0.05)
    rbox(p, (-10.8, 18.6, 0.2), (0.9, 1.6, 6.0), "zone", rot=(0, 0, 9))
    # テスラコイルの塔: 台座 → 光る芯に銅の巻き線 → 鏡面のトロイド → 電光の玉 → 回る放電の輪
    X, Z = -8.3, 0.4
    tw = s.part("shoulders", "tesla_r", p, pivot=(X, 25.8, Z))
    octa(tw, (X, 26.0, Z), 3.0, 0.8, "frame", axis="y")
    octa(tw, (X, 26.5, Z), 2.4, 0.3, "copper", axis="y")
    octa(tw, (X, 28.0, Z), 1.35, 3.0, "volt_core", axis="y")
    for k in range(5):
        octa(tw, (X, 26.9 + k * 0.6, Z), 1.9, 0.38, "coil", axis="y")
    octa(tw, (X, 29.85, Z), 2.7, 0.6, "chrome", axis="y")
    g = s.fx("glow", "tesla_r", tw, pivot=(X, 30.55, Z))
    octa(g, (X, 30.55, Z), 1.25, 1.1, "volt", axis="y")
    arc = s.fx("spin", "arc_r", tw, pivot=(X, 28.4, Z), rotation=(18, 0, 10))
    ring(arc, (X, 28.4, Z), 1.85, 8, (0, 0.18, 0.18), "volt", axis="y")


# ---------------------------------------------------------------------------
#  兜（王冠の兜: 冠の帯と尖り・額の稲妻・稲妻色のバイザー・機械の髭）
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.6, 0.15), (9.8, 4.4, 10.1), "plate", cut=1.0, axis="z")
    rf = rbox(hm, (-2.45, 33.0, 0.3), (5.2, 0.8, 9.2), "zone", rot=(0, 0, -12))
    mirror_x(hm, rf)
    cbox(hm, (0, 33.75, 0.3), (1.4, 0.9, 8.8), "plate2")                      # 中央の稜
    rbox(hm, (0, 31.6, 5.15), (8.6, 2.4, 0.8), "plate", rot=(28, 0, 0))       # 後ろの斜面
    cbox(hm, (0, 26.9, 4.95), (8.8, 4.6, 0.8), "zone")                         # 後頭部（帯）
    cbox(hm, (0, 28.2, 5.4), (7.4, 0.9, 0.3), "belt")
    cbox(hm, (0, 26.4, 5.4), (6.4, 0.6, 0.3), "rustband")
    cbox(hm, (0, 27.3, 5.55), (1.2, 3.6, 0.4), "plate2")
    cbox(hm, (0, 27.3, 5.78), (0.3, 2.8, 0.1), "volt")
    sd = cbox(hm, (-4.95, 27.3, 0.1), (0.9, 5.0, 8.4), "belt")                # 側板（縞）
    ear = octa(hm, (-5.55, 27.6, 0.6), 2.6, 0.5, "frame", axis="x")           # 耳のコイル
    ec = [c for k in range(2)
          for c in octa(hm, (-5.85 - k * 0.32, 27.6, 0.6), 1.7 - k * 0.3, 0.2, "coil", axis="x")]
    eg = octa(hm, (-6.45, 27.6, 0.6), 0.8, 0.2, "volt", axis="x")
    mirror_x(hm, sd, ear, ec, eg)
    # 冠: 金の帯の上に、菱形の尖りが一周する（ジグザグの王冠）。前の中央は大きく、宝玉と稲妻
    band = cbox(hm, (0, 31.55, 0.15), (10.4, 1.2, 10.6), "gold")
    for a in (0.18, 0.82):
        stick(hm, band, "north", a, 1.0, (2.1, 2.1, 0.35), "gold", spin=45, sink=0.1)
    for a in (0.18, 0.5, 0.82):
        stick(hm, band, "south", a, 1.0, (1.9, 1.9, 0.35), "gold", spin=45, sink=0.1)
        for f in ("east", "west"):
            stick(hm, band, f, a, 1.0, (1.9, 1.9, 0.35), "gold", spin=45, sink=0.1)
    big = stick(hm, band, "north", 0.5, 1.15, (3.0, 3.0, 0.45), "gold", spin=45, sink=0.12)
    stick(hm, big, "north", 0.5, 0.5, (1.0, 1.0, 0.3), "gem", sink=0.1)
    polyline(hm, [(-0.75, 35.3, -5.65), (0.3, 34.15, -5.65), (-0.25, 33.95, -5.65),
                  (0.7, 32.75, -5.65)], 0.3, 0.2, "volt", overlap=0.15)       # 額の稲妻
    cbox(hm, (0, 30.55, -5.35), (8.4, 0.5, 0.4), "rustband")                    # 冠の下の錆色の縞
    # 眉庇: 中央で下がる褐色の V
    br = rbox(hm, (-2.45, 29.55, -5.0), (4.9, 1.3, 1.1), "plate2", rot=(-14, 6, 7))
    mirror_x(hm, br)
    # 面: 暗い奥・頬の白い面頬・大きな口ひげ・下へ流れる機械の髭（三筋）
    cbox(hm, (0, 25.7, -4.62), (7.6, 3.6, 0.5), "frame")
    mg = rbox(hm, (-1.2, 26.1, -5.0), (2.5, 2.6, 0.7), "face", rot=(0, 28, 0))
    mu = rbox(hm, (-1.55, 26.55, -5.6), (2.9, 0.75, 0.6), "beard", rot=(0, 16, -16))  # 口ひげ
    mirror_x(hm, mg, mu)
    cbox(hm, (0, 27.0, -5.55), (0.6, 1.4, 0.5), "plate2")                       # 鼻筋
    beard = rbox(hm, (0, 24.6, -5.25), (3.4, 3.0, 0.8), "beard", rot=(10, 0, 0))
    stick(hm, beard, "north", 0.5, 0.06, (2.6, 0.3, 0.2), "copper", sink=0.05)
    bs = rbox(hm, (-2.0, 24.9, -4.95), (1.6, 2.8, 0.8), "beard", rot=(8, 26, -10))
    mirror_x(hm, bs)
    taper(hm, (0, 23.4, -5.45), (0, 22.0, -5.6), 1.6, 0.5, 2, "beard", round_=False)
    ck = rbox(hm, (-3.5, 25.9, -3.75), (1.4, 3.4, 3.3), "plate", rot=(0, 34, -6))  # 頬当て
    ckt = stick(hm, ck, "west", 0.08, 0.5, (0.35, 3.0, 0.2), "copper", sink=0.05)
    mirror_x(hm, ck, ckt)
    rbox(hm, (0, 24.0, 5.3), (8.8, 2.0, 0.9), "zone", rot=(18, 0, 0))          # しころ
    rbox(hm, (0, 22.7, 5.6), (8.2, 1.4, 0.8), "rustband", rot=(30, 0, 0))
    # バイザー（稲妻の青。中央が下がる厳しい目）
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 28.0, -4.8), (8.4, 1.9, 0.6), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 28.0, -5.1))
    half = rbox(fg, (-1.95, 28.05, -5.1), (3.9, 1.0, 0.35), "visor", rot=(0, 9, -6))
    mirror_x(fg, half)


# ---------------------------------------------------------------------------
#  稲妻の翼（背嚢の上から後ろ上へ、ジグザグに伸びる二枚の幅広の板。空中で開く）
# ---------------------------------------------------------------------------
def wings(s):
    wg = s.part("extra", "wing_r", "body", pivot=(-2.4, 22.6, 5.6))
    pts = [(-2.2, 22.2, 5.6), (-4.8, 25.0, 6.8), (-3.9, 25.4, 7.0), (-6.8, 29.0, 8.4)]
    polyline(wg, pts, [0.5, 0.45, 0.4], [2.2, 1.8, 1.4], "plate2", overlap=0.4)
    polyline(wg, [(p[0] + 0.0, p[1], p[2] + 0.12) for p in pts], [0.5, 0.45, 0.4], 0.32, "volt",
             overlap=0.3)
    taper(wg, (-6.8, 29.0, 8.4), (-7.7, 30.6, 9.1), 1.0, 0.2, 2, "rustband", round_=False)
