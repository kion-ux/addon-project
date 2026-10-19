# -*- coding: utf-8 -*-
"""天王星 — 傾天機装 ウラノス（Ouranos Frame）。7 頭身（v1.1）。

横倒しの氷の巨星。frame7 の紺の機械の骨格の上に、結晶のように面を切った淡い青緑の装甲（plate）と
深い青緑の副装甲（plate2）、霜の白（frost / rim）の縁、冷たい白の発光線を重ねる。
  * 背中: 98° 傾いて縦に立つ大きな環（光の ε 環・紺の帯・氷の塵の三重。5 つの氷の衛星）。
    背嚢の ◆ の台座から伸びる支柱の先の軸受けで回り（v.astro_spin）、空中・疾走では後ろへ倒れる
  * 兜: 小さな面を切った冠、額から天へ立つダイヤの鶏冠（◆ の重ね + 結晶）、細い V のバイザー、
    尖った面頬と ◆ の顎、後ろへ水平に流れる氷の耳（横倒しの惑星）
  * 肩: 三層の結晶の肩当て（外に ◆ の垂れ板）。右肩の氷晶は 98° 横倒しに突き出し、左肩は天を突く（非対称）
  * 胸: 霜の白の上の面と青緑の下の面が稜で折れる結晶の胸板、◆ の枠の中の天王星の星核と縦に立つ小さな環
  * 腕: 二の腕の惑星の紋章、肘の後ろの氷晶、篭手の外に沿って肘の上まで伸びる氷晶の刃、手の甲の ◆
  * 腰: ◆ のバックル、◆ の前垂れ、面を切った草摺（下端に氷の尖り）
  * 脚: ◆ の膝当て、V の稜の脛、ふくらはぎの排気口、外の氷晶のヒレ、◆ のつま先、踵の氷の棘

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A（7 頭身の目安）から取る。
右側だけ作り `_r` を付ける → 左は自動で鏡映（肩の氷晶だけは左右で別の物）。回転（統合版の rotation）:
rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く（+X の端が前へ）/ rz 正 = 上端が +X へ（横の板なら +X の端が下へ）。

ローカルの道具: crystal（氷晶）・diamond（◆ の板）・diamond_stack（◆ の重ね）・moon（氷の衛星）は weapon.py も使う。
他に bicrystal（両錐の結晶）。
"""
from __future__ import annotations

import math

import numpy as np

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, layered_plate,  # noqa: F401
                        line_on, mat_cube, mirror_x, octa, piston, rbox, rivets,
                        sensor, stick, taper, vents)
from astro_weapon import ring as wring   # 接線の向きを回転行列で解く輪（傾けたボーンの中でも正しい）
from hd_space import rot

NAVY = (29, 58, 85)
FROST = (226, 244, 250)
TR = 0.26              # 縁取りの幅
LX = A.LEG_X           # 脚の軸 -2.15
HZ = A.HEAD_Z          # 頭の中心の奥行き -0.25

# 背中の環（98° の傾き: 縦に立ち、上端が 8° 後ろへ倒れ、左右に 15° ひねる）
RING_C = (0.0, 21.4, 8.7)
RING_R = 11.0
RING_ROT = (-8, 15, 0)


# ===========================================================================
#  塗り（astro_paint.suit_styles("uranus") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate": {"panel": 7},
    "glow": {"glow": (150, 244, 255), "light": (246, 255, 255)},
    "glow_soft": {"glow": (150, 244, 255), "light": (246, 255, 255)},
    "visor": {"glow": (150, 246, 255), "light": (250, 255, 255), "deep": (14, 90, 120), "emit": 18},
    "flame": {"glow": (140, 236, 255), "light": (246, 255, 255), "deep": (30, 120, 190)},
    "flame_core": {"kind": "flame", "glow": (210, 255, 255), "light": (255, 255, 255),
                   "deep": (110, 210, 255), "bevel": False, "outline": False},
    "thruster": {"glow": (140, 236, 255), "light": (240, 255, 255), "deep": (20, 90, 150)},
    "frost": {"kind": "armor", "base": FROST, "light": (255, 255, 255), "dark": (150, 186, 204),
              "line": (60, 96, 124), "panel": 0},
    "frost_p": {"kind": "armor", "base": FROST, "light": (255, 255, 255), "dark": (150, 186, 204),
                "line": (60, 96, 124)},
    "navy": {"kind": "armor", "base": (36, 70, 104), "light": (78, 128, 166), "dark": (18, 36, 58),
             "line": (10, 22, 36), "panel": 0, "sheen": False},
    "rim": {"kind": "trim", "base": (206, 228, 238), "light": (255, 255, 255), "dark": (112, 146, 168),
            "line": (36, 58, 80)},
    "ice": {"kind": "crystal", "base": (158, 222, 248), "glow": (110, 206, 255), "line": (40, 96, 140),
            "emit": 215},
    "crystal": {"kind": "crystal", "base": (200, 244, 255), "glow": (140, 236, 255), "line": (40, 110, 140),
                "emit": 175},
    "gem": {"glow": (150, 246, 255), "deep": (16, 80, 110)},
    "hazard": {"c1": (150, 244, 255), "c2": NAVY},
    "serial": {"text": "UR-07", "under": {"kind": "armor", "base": (47, 159, 168), "panel": 0,
                                         "line": (14, 50, 64)}, "ink": (226, 250, 255)},
    "ringglow": {"kind": "glowline", "glow": (150, 244, 255), "light": (246, 255, 255),
                 "bevel": False, "outline": False},
    "ringband": {"kind": "armor", "base": (60, 150, 170), "light": (140, 220, 230),
                 "dark": (24, 70, 92), "line": (12, 34, 50), "panel": 0},
    "face": {"kind": "armor", "base": (200, 236, 240), "light": (250, 255, 255), "dark": (120, 168, 186),
             "line": (40, 80, 104), "panel": 0},
    "lamp": {"kind": "glowline", "glow": (190, 250, 255), "light": (250, 255, 255),
             "bevel": False, "outline": False},
}

# ===========================================================================
#  部位アニメ（Molang）。回るものは v.astro_spin（空中・疾走で速く進む累積の時間）、揺れは v.astro_t。
#  重み（v.astro_air / v.astro_run）は振れ幅だけに掛ける。`_r` は左へ自動で鏡映
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # 環はゆっくり回り（30°/秒）、氷の塵は逆へ、軸はわずかに歳差運動する
        "fx_spin_ring": {"rotation": [0, 0, "v.astro_spin * 30.0"]},
        "fx_spin_dust": {"rotation": [0, 0, "-v.astro_spin * 18.0"]},
        "extra_ring": {"rotation": ["math.sin(v.astro_t * 30.0) * 1.5",
                                    "math.cos(v.astro_t * 30.0) * 2.0", 0]},
    },
    "thrust": {
        # 空中では環が後ろへ倒れ（回転は v.astro_spin が自然に速まる）
        "extra_ring": {"rotation": ["-v.astro_air * 12.0", 0, 0]},
    },
    "sprint": {
        "extra_ring": {"rotation": ["-v.astro_run * 14.0", 0, 0]},
    },
}


# ===========================================================================
def build_suit(s: Suit):
    # サバトンが足を包み、背嚢・腰板・後ろ垂れが背骨を隠すので、骨格の足と背骨は省く
    s.frame7(skip=("foot", "spine"))
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    arms(s)
    hands(s)
    shoulders(s)
    shoulder_crystals(s)
    helmet(s)
    tilt_ring(s)


# ===========================================================================
#  ローカルの道具
# ===========================================================================
def _dir(deg, side=-1):
    """上から side 側（-1 = 右 -X）へ deg 度倒した向き（XY 平面）。"""
    a = math.radians(deg)
    return (side * math.sin(a), math.cos(a), 0.0)


def crystal(bone, base, d, length, w, style="ice", tip=0.4, lite=None, **kw):
    """氷晶: 45° ずらして重ねた角柱の胴（六角柱に見える）+ 尖った先。d は向き（正規化不要）。
    6 個（細い物 w < 0.7 は先を 1 段にして 4 個。lite で明示）。"""
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    b = np.asarray(base, float)
    mid = b + d * length * (1 - tip)
    if lite is None:
        lite = w < 0.7
    out = [beam(bone, b, mid, w, w, style, **kw), beam(bone, b, mid, w * 0.9, w * 0.9, style, roll=45, **kw)]
    out += taper(bone, mid - d * 0.05, b + d * length, w * 0.95, 0.16, 1 if lite else 2, style, **kw)
    return out


def diamond(bone, centre, size, depth, style, tilt=(0, 0, 0), **kw):
    """面の中で 45° 回した正方形（◆）を tilt（統合版の角度）で傾けて置く。"""
    return mat_cube(bone, centre, (size, size, depth), style, rot(*tilt) @ rot(0, 0, 45), **kw)


def diamond_stack(bone, centre, layers, tilt=(0, 0, 0), facing=-1, step=0.08):
    """◆ の重ね（台 → 枠 → 宝玉…）。layers = [(大きさ, 厚み, 塗り), ...]。後の層ほど小さく、
    前の層の表の面より step だけ前（facing: -1 = 局所 -Z の側、+1 = +Z の側）に表の面が来る。"""
    R = rot(*tilt) @ rot(0, 0, 45)
    n = R[:, 2] * facing
    c0 = np.asarray(centre, float)
    out = []
    front = None
    for size, depth, st in layers:
        off = 0.0 if front is None else front + step - depth / 2
        out.append(mat_cube(bone, c0 + n * off, (size, size, depth), st, R))
        front = off + depth / 2
    return out


def bicrystal(bone, centre, d, length, w, style="crystal", **kw):
    """両錐の結晶（中央が太く両端が尖る）。8 個。"""
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    c = np.asarray(centre, float)
    out = taper(bone, c - d * 0.04, c + d * length / 2, w, 0.16, 2, style, **kw)
    out += taper(bone, c + d * 0.04, c - d * length / 2, w, 0.16, 2, style, **kw)
    return out


def moon(bone, centre, r, style="ice", style2="crystal", cap="frost"):
    """氷の衛星: 箱 + 45° の箱 + 霜の極冠（3 個。どれも 1.0 以下）。"""
    c = np.asarray(centre, float)
    return [cbox(bone, c, (r * 1.6, r * 1.6, r * 1.6), style),
            rbox(bone, c, (r * 1.5, r * 1.5, r * 1.5), style2, rot=(45, 0, 45)),
            cbox(bone, c + (0, r * 0.82, 0), (r * 1.1, 0.2, r * 1.1), cap)]


# ---------------------------------------------------------------------------
#  サバトン（足首から生える）: 紺の靴底、青緑の殻、◆ に尖ったつま先、霜の甲、踵の噴射口と氷の棘
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (LX, 0.16, -1.05), (2.85, 0.32, 5.7), "navy")                          # 靴底
    shell = chamfer(b, (LX, 1.02, -0.55), (2.8, 1.42, 3.9), "plate2", cut=0.38, axis="z")
    line_on(b, shell[1], "west", (0.08, 0.45), (0.86, 0.45), 0.2, 0.16, "glow")
    rivets(b, shell[1], "west", 3, edge="top", margin=0.3, span=(0.2, 0.7), style="rivet")
    # 甲（霜の白）と ◆
    ins = rbox(b, (LX, 1.92, -1.85), (2.3, 0.5, 1.95), "frost", rot=(-30, 0, 0))
    rivets(b, ins, "up", 2, edge="bottom", margin=0.28, span=(0.25, 0.75), style="rivet")
    stick(b, ins, "up", 0.5, 0.62, (0.62, 0.62, 0.2), "gem", spin=45, sink=0.06)
    # つま先: 二枚の板が重なり、先が ◆（上から見て尖る）
    t1 = rbox(b, (LX, 1.0, -2.95), (2.62, 0.92, 1.1), "plate", rot=(-16, 0, 0))
    rivets(b, t1, "north", 3, edge="top", margin=0.22, span=(0.2, 0.8), size=0.22, style="rivet")
    cbox(b, (LX, 0.6, -3.5), (2.3, 0.32, 0.3), "navy")                              # 関節
    rbox(b, (LX, 0.62, -3.72), (1.55, 0.72, 1.55), "plate", rot=(0, 45, 0))          # ◆ の先
    rbox(b, (LX, 1.02, -3.62), (0.98, 0.22, 0.98), "frost", rot=(0, 45, 0))            # 先の霜の稜
    cbox(b, (LX, 0.3, -4.22), (0.5, 0.3, 0.5), "rim", rotation=(0, 45, 0))           # 先端の金具
    # 踵: 紺の板・噴射口・後ろ上へ伸びる氷の棘
    hl = cbox(b, (LX, 1.05, 1.25), (2.5, 1.5, 0.95), "plate_b")
    vents(b, hl, "south", 2, box=(0.2, 0.55, 0.8, 0.85), w=0.18)
    octa(b, (LX, 0.62, 1.82), 0.98, 0.42, "navy", axis="z")
    cbox(b, (LX, 0.62, 2.06), (0.78, 0.78, 0.16), "thruster")
    crystal(b, (LX, 1.55, 1.55), (0, 0.5, 1.0), 2.2, 0.55, "ice", tip=0.5)
    # 足首の外を守る小さな板（ドラムは見せる）と ◆
    ag = rbox(b, (LX - 1.5, 2.5, 0.75), (0.32, 1.1, 1.35), "plate2", rot=(0, 0, -6))
    stick(b, ag, "west", 0.5, 0.5, (0.55, 0.55, 0.18), "frost", spin=45, sink=0.05)


# ---------------------------------------------------------------------------
#  脚（腿・膝・脛）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前の淡い板（上に青緑の板・氷の亀裂の発光線）、外の型番の板、後ろの板。内側は骨格を見せる
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.7, -1.82), (2.85, 4.2, 0.55), "plate", top="plate2",
                       rot=(-3, 0, 0), inset=0.48, trim="rim", trim_edge="bottom",
                       rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(t, fr["top"], "north", (0.22, 0.12), (0.4, 0.5), 0.18, 0.16, "glow")
    line_on(t, fr["top"], "north", (0.4, 0.5), (0.3, 0.86), 0.18, 0.16, "glow")
    line_on(t, fr["top"], "north", (0.4, 0.5), (0.78, 0.68), 0.18, 0.16, "glow")
    stick(t, fr["top"], "north", 0.72, 0.28, (0.6, 0.6, 0.2), "frost", spin=45, sink=0.06)
    side = rbox(t, (LX - 1.78, 11.35, 0.05), (0.5, 3.2, 2.9), "plate2", rot=(0, 0, -3),
                decals={"west": {"decal": "serial", "text": "UR-07", "ink": (226, 250, 255)}})
    rivets(t, side, "west", 3, edge="bottom", margin=0.3, style="rivet")
    cbox(t, (LX - 1.62, 9.62, 0.05), (0.42, 0.42, 2.7), "rim")
    bkp = rbox(t, (LX, 11.4, 1.72), (2.2, 3.2, 0.4), "plate_b", rot=(3, 0, 0))
    vents(t, bkp, "south", 2, box=(0.25, 0.35, 0.75, 0.75), w=0.2)
    # 膝: ◆ の膝当て（霜の枠 → 結晶 → 宝玉）、膝の庇、両脇の小板、外の油圧シリンダー
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    diamond_stack(k, (LX, 8.45, -1.78), [(1.95, 0.55, "frost"), (1.3, 0.3, "crystal"),
                                         (0.55, 0.22, "gem")])
    vz = rbox(k, (LX, 9.72, -1.68), (2.45, 0.62, 0.55), "plate", rot=(28, 0, 0))
    rivets(k, vz, "north", 2, edge="bottom", margin=0.2, span=(0.2, 0.8), size=0.22, style="rivet")
    piston(k, (LX - 1.62, 10.9, 0.55), (LX - 1.5, 6.3, 0.45), r=0.27, style="frame",
           rod_style="chrome", cap_style="dark")
    # 脛: 前の青緑の板 + V の稜（淡い二枚と発光の稜線）+ 下の ◆、下へ絞る両脇の板、ふくらはぎの排気口、
    #     外の氷晶のヒレ
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 4.72, -1.42), (2.5, 5.0, 0.55), "plate2", rot=(4, 0, 0))
    stick(g, front, "north", 0.5, 0.04, (2.35, TR, 0.18), "rim", sink=0.05)
    keel = rbox(g, (LX - 0.4, 5.05, -1.76), (0.86, 4.2, 0.46), "plate", rot=(4, 28, 0))
    kr = rivets(g, keel, "north", 2, edge="left", margin=0.24, span=(0.25, 0.75), size=0.2,
                style="rivet")
    mirror_x(g, keel, kr, about=LX)
    rbox(g, (LX, 5.05, -2.04), (0.2, 3.8, 0.2), "glow", rot=(4, 0, 0))              # 稜の発光
    diamond_stack(g, (LX, 2.72, -1.86), [(0.95, 0.3, "frost"), (0.5, 0.2, "gem")], tilt=(4, 0, 0))
    sd = rbox(g, (LX - 1.3, 4.7, -0.15), (0.42, 4.6, 2.5), "plate", rot=(0, 0, -3))
    sdr = rivets(g, sd, "west", 2, edge="bottom", margin=0.3, span=(0.25, 0.75), style="rivet")
    mirror_x(g, sd, sdr, about=LX)
    calf = rbox(g, (LX, 6.1, 1.62), (2.3, 2.5, 0.45), "plate2_b", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.2, 0.2, 0.8, 0.8))
    fin = rbox(g, (LX - 1.68, 5.5, 0.8), (0.34, 3.0, 1.8), "plate2", rot=(-10, 0, -8))
    line_on(g, fin, "west", (0.15, 0.28), (0.85, 0.7), 0.18, 0.16, "glow")
    crystal(g, (LX - 1.82, 6.75, 1.15), (-0.28, 1.0, 0.5), 1.9, 0.42, "ice", tip=0.5)


# ---------------------------------------------------------------------------
#  腰（紺のベルト・◆ のバックル・◆ の前垂れ・腰の脇の板・面を切った草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    bl = chamfer(w, (0, 16.95, 0.12), (6.7, 0.95, 4.5), "navy", cut=0.4, axis="y")
    cbox(w, (0, 17.28, -2.13), (5.2, 0.18, 0.16), "glow")
    br = rivets(w, bl[0], "north", 2, edge="bottom", margin=0.28, span=(0.1, 0.26), size=0.22,
                style="rivet")
    mirror_x(w, br)
    diamond_stack(w, (0, 16.95, -2.22), [(1.75, 0.4, "frost"), (1.25, 0.3, "navy"),
                                         (0.72, 0.25, "gem")])
    # 前垂れ（◆。腿の前を隠さない幅）
    diamond_stack(w, (0, 15.2, -2.0), [(1.55, 0.45, "plate2"), (1.0, 0.25, "frost"),
                                       (0.45, 0.2, "glow")], tilt=(-8, 0, 0))
    # 腰の脇の板（股関節の前を覆う）
    hp = rbox(w, (-2.38, 15.85, -1.98), (2.0, 1.15, 0.45), "plate", rot=(-8, 14, 4))
    hpr = rivets(w, hp, "north", 2, edge="top", margin=0.28, span=(0.25, 0.75), style="rivet")
    hpl = line_on(w, hp, "north", (0.1, 0.25), (0.9, 0.25), 0.18, 0.16, "plate2")
    mirror_x(w, hp, hpr, hpl)
    # 後ろ垂れ
    rs = rbox(w, (0, 15.05, 2.45), (4.4, 2.6, 0.5), "plate", rot=(14, 0, 0))
    cbox(w, (0, 14.05, 2.86), (2.8, 0.38, 0.3), "hazard")
    rivets(w, rs, "south", 4, edge="top", margin=0.3, style="rivet")
    diamond(w, (0, 15.35, 2.78), 0.8, 0.3, "frost", (14, 0, 0))
    # 草摺（腰の横。付け根で外へ開く。淡い下板 + 青緑の上板 + 霜の縁 + 発光線 + リベット + 下の氷の尖り）
    ts = s.part("waist", "tasset_r", w, pivot=(-3.35, 16.6, 0.0), rotation=(0, 0, 8))
    base = layered_plate(ts, (-3.62, 15.15, 0.0), (0.45, 2.8, 3.4), "plate", top="plate2",
                         face="west", inset=0.34, trim="rim", trim_edge="bottom",
                         rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(ts, base["top"], "west", (0.12, 0.42), (0.6, 0.42), 0.18, 0.16, "glow")
    line_on(ts, base["top"], "west", (0.6, 0.42), (0.88, 0.7), 0.18, 0.16, "glow")
    cbox(ts, (-3.42, 16.3, 0.0), (0.5, 0.55, 1.6), "navy")                        # 蝶番
    rbox(ts, (-3.64, 13.7, -1.05), (0.36, 0.9, 0.9), "frost", rot=(45, 0, 0))      # 前下の尖り
    rbox(ts, (-3.64, 13.7, 1.05), (0.36, 0.9, 0.9), "frost", rot=(45, 0, 0))       # 後ろ下の尖り


# ---------------------------------------------------------------------------
#  胴（胸郭・結晶の胸板・◆ の星核・襟・肩の受け・脇の排気口・背の板・腹の V の板）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.25, 0.0), (9.3, 3.5, 4.9), "plate", cut=0.85, axis="y")     # 上が広い
    chamfer(c, (0, 21.65, -0.05), (7.2, 2.3, 4.55), "plate2", cut=0.6, axis="y")
    sl = rbox(c, (-3.95, 22.15, 0.0), (0.5, 2.9, 4.0), "plate2", rot=(0, 0, -24))    # 脇の斜面
    mirror_x(c, sl)
    # 結晶の胸板: 霜の白の上の面（前上を向く）と青緑の下の面（前下を向く）が稜で折れ、内の端が前・下へ
    pu = rbox(c, (-2.45, 24.72, -2.6), (3.7, 1.95, 0.5), "frost_p", rot=(-14, 18, 9))
    pt = stick(c, pu, "north", 0.5, 0.94, (3.5, TR, 0.18), "rim", sink=0.05)
    pr = rivets(c, pu, "north", 2, edge="top", margin=0.32, span=(0.15, 0.45), size=0.22,
                style="rivet")
    pl = rbox(c, (-2.2, 22.92, -2.5), (3.4, 1.6, 0.5), "plate2", rot=(18, 16, 13))
    gl = [line_on(c, pl, "north", ab0, ab1, 0.18, 0.16, "glow") for ab0, ab1 in (
        ((0.9, 0.7), (0.55, 0.45)), ((0.55, 0.45), (0.15, 0.6)))]
    plr = rivets(c, pl, "north", 2, edge="bottom", margin=0.24, span=(0.2, 0.5), size=0.22,
                 style="rivet")
    mirror_x(c, pu, pt, pr, pl, gl, plr)
    # 胸の中央の稜（青緑 + 発光）: 首元から星核へ
    kl = rbox(c, (0, 25.3, -2.78), (1.05, 1.75, 0.45), "plate2", rot=(-10, 0, 0))
    line_on(c, kl, "north", (0.5, 0.12), (0.5, 0.9), 0.18, 0.16, "glow")
    # 星核: 紺の ◆ の台 → 霜の ◆ の枠 → 紺 → 天王星 → 縦に立つ小さな光の環（98°）
    diamond_stack(c, (0, 23.55, -2.72), [(2.35, 0.42, "navy"), (2.0, 0.26, "rim"),
                                         (1.6, 0.24, "navy")])
    cbox(c, (0, 23.55, -3.18), (1.05, 1.05, 0.5), "core")
    gl_ = s.fx("glow", "core", c, pivot=(0, 23.55, -3.32), rotation=(0, 64, 8))
    wring(gl_, (0, 23.55, -3.32), 1.0, 8, (0, 0.2, 0.2), "glow", axis="z")
    # 襟（首の両脇に立ち上がる淡い板 + 霜の上板 + 前の氷の小さな尖り）
    col = rbox(c, (-1.78, 26.22, 0.3), (1.4, 1.0, 3.4), "plate", rot=(0, 0, -26))
    colt = stick(c, col, "up", 0.5, 0.5, (1.0, 3.1, 0.2), "frost", sink=0.06)
    cf = rbox(c, (-0.95, 25.98, -1.92), (1.55, 0.85, 0.45), "plate2", rot=(-20, 30, -10))
    cc = crystal(c, (-1.5, 26.35, -1.25), (-0.45, 1.0, -0.35), 1.3, 0.42, "ice", tip=0.55)
    mirror_x(c, col, colt, cf, cc)
    sensor(c, (-1.38, 25.25, -2.62), 0.24, "lamp", "navy")
    sensor(c, (1.38, 25.25, -2.62), 0.24, "lamp", "navy")
    # 肩の受け（肩当ての下）と脇の排気口
    sv = cbox(c, (-4.55, 23.75, 0.3), (0.3, 1.9, 2.2), "plate2")
    svv = vents(c, sv, "west", 3, box=(0.15, 0.2, 0.85, 0.8))
    mirror_x(c, sv, svv)
    # 背の上の板（肩甲骨。外へ傾く青緑の板 + 排気口）
    sc = rbox(c, (-2.65, 24.3, 2.55), (2.4, 2.5, 0.42), "plate2", rot=(8, -14, -8))
    scv = vents(c, sc, "south", 2, box=(0.25, 0.3, 0.75, 0.65), w=0.18)
    mirror_x(c, sc, scv)
    rivets(c, up[1], "south", 4, edge="top", margin=0.3, span=(0.15, 0.85), style="rivet")
    # 腹: 下を向く V の板が三段（淡い・青緑・淡い）、中央の紺の溝とリベット
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))
    for i, (y, ww, st) in enumerate(((19.95, 3.9, "plate"), (18.95, 3.5, "plate2"),
                                     (17.95, 3.1, "plate"))):
        z = -1.98 + i * 0.05
        h_ = rbox(ab, (-ww / 4 - 0.06, y, z), (ww / 2, 0.8, 0.46), st, rot=(-8, 8, 10))
        r_ = rivets(ab, h_, "north", 1, line=((0.25, 0.5), (0.25, 0.5)), size=0.2, style="rivet")
        mirror_x(ab, h_, r_)
        cbox(ab, (0, y - 0.12, z - 0.12), (0.34, 0.62, 0.3), "navy")
    lb = cbox(ab, (0, 18.9, 2.08), (2.2, 2.6, 0.45), "plate2_b")                    # 背の腰板
    vents(ab, lb, "south", 3, box=(0.2, 0.25, 0.8, 0.75), w=0.2)


# ---------------------------------------------------------------------------
#  背中（面を切った背嚢・環の支柱と ◆ の台座・氷晶のタンク・双発スラスター・ホース・アンテナ）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    pk = bevel(bk, (0, 22.2, 3.45), (4.4, 5.0, 1.9), "plate2", cut=0.7, axis="z")
    lid = rbox(bk, (0, 24.95, 3.2), (3.8, 0.75, 1.9), "plate", rot=(20, 0, 0))
    rivets(bk, lid, "up", 3, edge="top", margin=0.25, span=(0.2, 0.8), style="rivet")
    vents(bk, pk[0], "south", 3, box=(0.22, 0.7, 0.78, 0.9), rim="navy")
    rivets(bk, pk[0], "south", 8, edge="border", margin=0.26, style="rivet")
    cbox(bk, (0, 19.95, 4.42), (2.6, 0.38, 0.2), "hazard")
    sensor(bk, (-1.55, 24.2, 4.42), 0.24, "glow", "navy", facing=1)
    sensor(bk, (1.55, 24.2, 4.42), 0.24, "glow", "navy", facing=1)
    # 環の支柱: ◆ の台座（霜 → 紺）から後ろへ伸びる八角の柱（霜の輪・発光の帯）
    diamond_stack(bk, (0, RING_C[1], 4.45), [(2.3, 0.3, "frost"), (1.7, 0.3, "navy")], facing=1)
    zs, ze = 4.6, RING_C[2] - 1.0
    octa(bk, (0, RING_C[1], (zs + ze) / 2), 0.8, ze - zs, "frame", axis="z")
    for z in (zs + 0.55, ze - 0.4):
        octa(bk, (0, RING_C[1], z), 0.98, 0.3, "rim", axis="z")
    octa(bk, (0, RING_C[1], (zs + ze) / 2 + 0.2), 0.98, 0.5, "glow_soft", axis="z")
    # ホース: 背嚢の下から腰の両脇へ（垂れる蛇腹）
    hs = cable(bk, [(-1.5, 19.85, 3.55), (-2.85, 17.5, 2.35)], 0.3, "dark", sag=0.32,
               rib="frame_lt", rib_every=2)
    mirror_x(bk, hs)
    # アンテナ（背嚢の右上から後ろ上へ。氷の先）
    an = s.part("back", "antenna", bk, pivot=(-1.6, 25.2, 3.6), ornament=True)
    beam(an, (-1.6, 25.2, 3.6), (-2.1, 27.6, 4.6), 0.2, 0.2, "frame_lt")
    crystal(an, (-2.1, 27.55, 4.6), (-0.2, 1, 0.42), 1.0, 0.3, "ice", tip=0.6)
    # スラスター（右。真下へ、少し外へ開く）: 胴・霜の輪・広がったベル・光る縁の輪・噴射口・炎
    th = s.part("back", "thruster_r", bk, pivot=(-1.25, 20.4, 4.45), rotation=(6, 0, -10))
    octa(th, (-1.25, 19.5, 4.45), 1.5, 1.9, "plate", axis="y")
    octa(th, (-1.25, 20.2, 4.45), 1.68, 0.3, "rim", axis="y")
    octa(th, (-1.25, 18.15, 4.45), 1.95, 0.9, "navy", axis="y")
    wring(th, (-1.25, 17.72, 4.45), 0.78, 8, (0, 0.22, 0.22), "glow", axis="y")
    cbox(th, (-1.25, 17.7, 4.45), (1.3, 0.16, 1.3), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.25, 17.62, 4.45))
    taper(fx, (-1.25, 17.62, 4.45), (-1.25, 11.8, 4.45), 1.5, 0.36, 2, "flame")
    taper(fx, (-1.25, 17.57, 4.45), (-1.25, 14.4, 4.45), 0.72, 0.3, 1, "flame_core", round_=False)


# ---------------------------------------------------------------------------
#  腕（二の腕・肘の氷晶・篭手と氷晶の刃）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.32, 21.35, 0.0), (0.42, 3.1, 2.4), "plate2", rot=(0, 0, 3),
              decals={"west": {"decal": "emblem", "color": (150, 244, 255)}})        # 惑星の紋章
    rivets(ua, op, "west", 2, edge="bottom", margin=0.28, span=(0.25, 0.75), style="rivet")
    upf = rbox(ua, (X + 0.05, 21.4, -1.36), (2.1, 2.8, 0.4), "plate", rot=(-3, 0, 0))
    stick(ua, upf, "north", 0.5, 0.5, (0.45, 2.3, 0.16), "plate2", sink=0.06)
    sensor(ua, (X + 0.05, 22.55, -1.62), 0.22, "glow", "navy")
    ubk = rbox(ua, (X + 0.05, 21.6, 1.36), (2.0, 2.3, 0.4), "plate_b", rot=(3, 0, 0))
    stick(ua, ubk, "south", 0.5, 0.5, (0.55, 0.55, 0.18), "frost", spin=45, sink=0.05)
    octa(ua, (X, 19.72, 0.02), 2.82, 0.32, "rim", axis="y")                         # 腕輪
    # 肘当て（後ろ）と後ろ下へ伸びる氷晶
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    cop = chamfer(el, (A.ELBOW[0], 18.55, 1.6), (2.05, 1.85, 0.6), "plate", cut=0.32, axis="z")
    rivets(el, cop[1], "south", 2, edge="top", margin=0.26, span=(0.3, 0.7), size=0.22,
           style="rivet")
    crystal(el, (A.ELBOW[0], 18.35, 1.75), (-0.1, -0.4, 1.0), 2.3, 0.66, "ice", tip=0.5)
    # 篭手: 手首へ向かって開く（淡い）+ 外の青緑の板（発光線・リベット）+ 前の板 + 霜の袖口
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX_ = A.FOREARM_X
    chamfer(fa, (FX_, 17.15, 0.0), (2.8, 1.9, 2.9), "plate", cut=0.42, axis="y")
    lo = chamfer(fa, (FX_ - 0.04, 15.7, 0.0), (2.98, 1.75, 3.12), "plate", cut=0.46, axis="y")
    ob = rbox(fa, (FX_ - 1.66, 16.3, 0.0), (0.42, 3.1, 2.55), "plate2", rot=(0, 0, 5))
    line_on(fa, ob, "west", (0.15, 0.2), (0.85, 0.2), 0.18, 0.16, "glow")
    rivets(fa, ob, "west", 3, edge="top", margin=0.26, style="rivet")
    fv = rbox(fa, (FX_ - 0.02, 16.45, -1.6), (2.0, 2.2, 0.35), "plate2", rot=(-5, 0, 0))
    diamond_stack(fa, (FX_ - 0.02, 16.5, -1.8), [(1.15, 0.24, "frost"), (0.6, 0.2, "gem")],
                  tilt=(-5, 0, 0))
    rivets(fa, fv, "north", 2, edge="bottom", margin=0.18, span=(0.12, 0.88), size=0.2,
           style="rivet")
    chamfer(fa, (FX_ - 0.04, 14.72, 0.0), (3.04, 0.34, 3.18), "frost", cut=0.4, axis="y")  # 袖口
    sensor(fa, (FX_ + 0.05, 15.5, 1.66), 0.24, "glow", "navy", facing=1)
    rivets(fa, lo[1], "south", 2, edge="bottom", margin=0.3, span=(0.3, 0.7), style="rivet")
    # 氷晶の刃: 篭手の外に沿って手首から肘の上へ（後ろへ反る）。付け根の紺の留め具
    crystal(fa, (FX_ - 1.85, 14.75, -0.35), (-0.12, 0.92, 0.38), 4.7, 0.62, "ice", tip=0.45)
    crystal(fa, (FX_ - 1.8, 15.0, 0.75), (-0.14, 0.8, 0.6), 2.6, 0.42, "crystal", tip=0.5)
    cbox(fa, (FX_ - 1.88, 15.2, -0.2), (0.3, 0.7, 1.1), "navy")


def hands(s):
    """手の甲の青緑の板と ◆、指の甲当て（4 本の基節）、親指の当て。指そのものは frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.42, 13.62, 0.0), (0.36, 1.7, 2.3), "plate2", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.55, (0.72, 0.72, 0.2), "frost", spin=45, sink=0.05)
    stick(h, hb, "west", 0.5, 0.55, (0.38, 0.38, 0.28), "gem", spin=45, sink=0.05)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        n = (-0.81, -0.58, 0.0)
        o = 0.34
        beam(h, (p0[0] + n[0] * o, p0[1] + n[1] * o, zf), (p1[0] + n[0] * o, p1[1] + n[1] * o, zf),
             0.54, 0.22, "plate")
    rbox(h, (-5.62, 13.55, -1.72), (0.62, 0.9, 0.22), "plate", rot=(0, 0, -36))


# ---------------------------------------------------------------------------
#  肩（結晶の肩当て: 外へ下る芯・霜の上板と青緑の稜・前後の面・反り返る縁・外の ◆ の垂れ板）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    R_ = (0, 0, -15)
    core = chamfer(p, (-7.15, 25.5, 0.0), (3.6, 2.2, 4.6), "plate", cut=0.72, axis="x", rot=R_)
    top = stick(p, core[1], "up", 0.48, 0.5, (3.3, 2.9, 0.26), "frost", sink=0.08)
    rdg = stick(p, top, "up", 0.5, 0.5, (3.35, 0.6, 0.28), "plate2", sink=0.08)       # 中央の稜
    line_on(p, rdg, "up", (0.06, 0.5), (0.94, 0.5), 0.18, 0.16, "glow")
    rivets(p, top, "up", 4, edge="border", margin=0.26, size=0.22, style="rivet")
    for sz in (-1, 1):                                                                # 前後の面
        f_ = rbox(p, (-7.12, 26.02, sz * 1.95), (3.45, 0.32, 1.2), "plate",
                  rot=(-34 * sz, 0, -15))
        rivets(p, f_, "up", 2, edge="bottom" if sz > 0 else "top", margin=0.24,
               span=(0.25, 0.75), size=0.2, style="rivet")
    cbox(p, (-6.5, 24.2, 0.0), (2.2, 0.5, 3.8), "navy")                              # 裏の縁
    # 外の縁: 上・外へ反り返り、前後が尖る青緑の板（上端に霜）
    rim = rbox(p, (-9.05, 25.3, 0.0), (0.45, 1.9, 4.6), "plate2", rot=(0, 0, -30))
    stick(p, rim, "up", 0.5, 0.5, (0.45, 4.6, 0.2), "rim", sink=0.05)
    rivets(p, rim, "west", 3, edge="bottom", margin=0.3, size=0.22, style="rivet")
    for sz in (-1, 1):
        rbox(p, (-9.12, 25.4, sz * 2.45), (0.4, 1.3, 1.3), "plate2", rot=(45 * sz, 0, -30))
    # 外へ開いて垂れる ◆ の板（青緑 → 霜の枠 → 淡い → 宝玉）と、その奥の紺の影
    T = (0, 90, 14)
    diamond_stack(p, (-8.62, 23.15, 0.05), [(3.0, 0.42, "plate2"), (2.45, 0.24, "rim"),
                                            (2.0, 0.24, "plate"), (0.7, 0.22, "gem")],
                  tilt=T, facing=1)
    rbox(p, (-8.1, 23.6, 0.05), (0.5, 1.8, 3.6), "navy", rot=(0, 0, 14))
    # 前後の三角筋の当て（淡い板が下へ尖り、霜の縁と ◆）。前にはセンサー
    for sz in (-1, 1):
        dg = rbox(p, (-7.55, 23.7, sz * 2.12), (2.3, 1.7, 0.36), "plate",
                  rot=(-14 * sz, 16 * sz, 12))
        stick(p, dg, "north" if sz < 0 else "south", 0.5, 0.08, (2.2, TR, 0.16), "rim", sink=0.05)
        if sz < 0:
            stick(p, dg, "north", 0.62, 0.55, (0.62, 0.62, 0.2), "frost", spin=45, sink=0.05)
            stick(p, dg, "north", 0.62, 0.55, (0.3, 0.3, 0.26), "gem", spin=45, sink=0.05)
    sensor(p, (-6.75, 24.65, -2.38), 0.22, "lamp", "navy")


def shoulder_crystals(s):
    """左右非対称の氷晶（鏡映しない）: 右は 98° 横倒しに外へ、左は天を突く。どちらも飾り。"""
    tl = s.part("shoulders", "tilt", "rightArm", pivot=(-8.4, 26.2, 0.1), ornament=True)
    octa(tl, (-8.35, 26.15, 0.1), 1.3, 0.8, "navy", axis="x", rot=(0, 0, 8))
    octa(tl, (-8.85, 26.08, 0.1), 0.98, 0.26, "rim", axis="x", rot=(0, 0, 8))
    crystal(tl, (-8.6, 26.1, 0.1), _dir(98), 5.2, 1.15, "ice", tip=0.36)
    crystal(tl, (-8.5, 26.5, -0.95), _dir(76), 3.2, 0.72, "crystal", tip=0.45, lite=True)
    crystal(tl, (-8.5, 25.8, 1.1), _dir(120), 2.8, 0.66, "crystal", tip=0.45)
    cr = s.part("shoulders", "crown", "leftArm", pivot=(8.2, 26.3, 0.1), ornament=True)
    octa(cr, (8.2, 26.3, 0.1), 1.3, 0.8, "navy", axis="y")
    octa(cr, (8.2, 26.78, 0.1), 0.98, 0.26, "rim", axis="y")
    crystal(cr, (8.2, 26.4, 0.1), _dir(6, +1), 5.0, 1.15, "ice", tip=0.36)
    crystal(cr, (8.65, 26.35, -0.95), _dir(26, +1), 3.1, 0.72, "crystal", tip=0.45, lite=True)
    crystal(cr, (8.65, 26.3, 1.1), _dir(-14, +1), 2.7, 0.66, "crystal", tip=0.45)


# ---------------------------------------------------------------------------
#  兜（面を切った冠・霜の屋根・額・眉の V・面頬・◆ の顎・頬当て・耳・後頭部・しころ）とバイザー・鶏冠
# ---------------------------------------------------------------------------
def helmet(s):
    hz = HZ
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.45, hz + 0.25), (4.3, 2.0, 4.7), "plate", cut=0.62, axis="z")
    chamfer(hm, (0, 31.4, hz + 0.4), (3.2, 0.8, 4.2), "plate", cut=0.32, axis="z")  # 冠
    roof = rbox(hm, (-0.92, 31.62, hz + 0.4), (1.75, 0.34, 4.0), "frost_p", rot=(0, 0, -20))
    rfr = rivets(hm, roof, "up", 2, edge="left", margin=0.22, span=(0.25, 0.75), size=0.2,
                 style="rivet")
    mirror_x(hm, roof, rfr)
    cbox(hm, (0, 31.84, hz + 0.45), (0.5, 0.3, 4.1), "navy")                          # 稜の溝
    cbox(hm, (0, 31.94, hz + 0.6), (0.2, 0.16, 3.4), "glow")
    rbox(hm, (0, 30.68, hz - 2.12), (3.9, 1.25, 0.45), "plate", rot=(-26, 0, 0))   # 額の斜面
    br = rbox(hm, (-0.98, 30.06, hz - 2.42), (1.95, 0.42, 0.42), "frost", rot=(-6, 10, 12))
    sd = cbox(hm, (-2.08, 29.15, hz + 0.65), (0.42, 2.3, 3.4), "plate")               # こめかみ
    sdr = rivets(hm, sd, "west", 2, edge="top", margin=0.3, span=(0.3, 0.7), size=0.2,
                 style="rivet")
    ck = rbox(hm, (-1.78, 28.4, hz - 1.12), (0.48, 2.0, 2.3), "plate2", rot=(0, 20, -10))  # 頬当て
    ckg = stick(hm, ck, "west", 0.06, 0.5, (0.22, 1.8, 0.16), "rim", sink=0.05)
    ear = octa(hm, (-2.3, 29.15, hz + 0.6), 1.25, 0.3, "chrome", axis="x")             # 耳
    eg = cbox(hm, (-2.46, 29.15, hz + 0.6), (0.16, 0.48, 0.48), "glow")
    mirror_x(hm, br, sd, sdr, ck, ckg, ear, eg)
    # 面頬（淡い霜）: 中央の稜へ折れた V の板と小さな吸気口、尖った ◆ の顎
    fc = rbox(hm, (-0.62, 28.48, hz - 2.2), (1.3, 1.2, 0.42), "face", rot=(8, 28, 0))
    fcv = vents(hm, fc, "north", 2, box=(0.3, 0.25, 0.85, 0.6), w=0.16)
    jw = rbox(hm, (-0.48, 27.82, hz - 1.95), (1.0, 0.7, 0.48), "plate2", rot=(0, 26, -22))
    mirror_x(hm, fc, fcv, jw)
    cbox(hm, (0, 28.55, hz - 2.5), (0.3, 1.3, 0.3), "frost")
    diamond(hm, (0, 27.92, hz - 2.22), 0.82, 0.46, "frost", (-14, 0, 0))
    # 後頭部（霜の稜が後ろへ降りる・小さな排気口）としころ
    bh = cbox(hm, (0, 29.15, hz + 2.58), (3.9, 2.3, 0.45), "plate")
    rbox(hm, (0, 31.15, hz + 2.5), (0.8, 1.55, 0.4), "frost", rot=(35, 0, 0))
    vents(hm, bh, "south", 3, box=(0.3, 0.25, 0.7, 0.65), w=0.18)
    rbox(hm, (0, 28.05, hz + 2.62), (3.7, 0.75, 0.45), "plate2", rot=(22, 0, 0))
    rbox(hm, (0, 27.55, hz + 2.75), (3.2, 0.62, 0.42), "plate", rot=(32, 0, 0))
    # ダイヤの鶏冠（飾り）: 額から天へ立つ ◆ の重ね（紺 → 霜 → 結晶 → 宝玉）と、その上の両錐の結晶
    cr = s.part("helmet", "crest", "head", pivot=(0, 30.6, hz - 2.5), ornament=True)
    diamond_stack(cr, (0, 31.55, hz - 2.42), [(1.95, 0.3, "navy"), (1.7, 0.3, "frost"),
                                              (1.15, 0.26, "crystal"), (0.5, 0.2, "gem")],
                  tilt=(-18, 0, 0))
    bicrystal(cr, (0, 33.25, hz - 2.0), (0, 1.0, 0.32), 1.9, 0.52, "ice")
    # 後ろへ水平に流れる氷の耳（横倒しの惑星。飾り）
    fn = s.part("helmet", "fin_r", "head", pivot=(-2.35, 29.6, hz + 0.9), ornament=True)
    crystal(fn, (-2.3, 29.65, hz + 0.75), (-0.32, 0.18, 1.0), 3.3, 0.52, "ice", tip=0.5)
    # バイザー: 紺の帯の上に、中央で下がる細い V の光
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 29.45, hz - 2.3), (3.7, 0.9, 0.3), "navy")
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.45, hz - 2.48))
    eye = rbox(fg, (-0.9, 29.48, hz - 2.48), (1.6, 0.28, 0.18), "visor", rot=(0, 10, 13))
    mirror_x(fg, eye)
    cbox(fg, (0, 29.32, hz - 2.5), (0.3, 0.2, 0.16), "visor")


# ---------------------------------------------------------------------------
#  背中の環（98° 傾いて縦に立ち、ゆっくり回る。光の ε 環・紺の帯・氷の塵と 5 つの氷の衛星）
# ---------------------------------------------------------------------------
def tilt_ring(s):
    C = RING_C
    rg = s.part("extra", "ring", "body", pivot=C, rotation=RING_ROT)
    # 軸受け（静止）: 紺の八角のハブ・光る芯・霜の ◆ の蓋・後ろへ突き出す自転軸・ボルトの輪
    octa(rg, C, 2.1, 1.1, "navy", axis="z")
    octa(rg, (C[0], C[1], C[2] + 0.2), 1.25, 1.0, "glow", axis="z")
    diamond_stack(rg, (C[0], C[1], C[2] + 0.62), [(1.4, 0.26, "frost"), (0.7, 0.2, "gem")],
                  facing=1)
    cbox(rg, (C[0], C[1], C[2] + 1.45), (0.4, 0.4, 1.7), "rim")
    wring(rg, (C[0], C[1], C[2] - 0.62), 0.78, 6, (0.22, 0.22, 0.18), "rivet", axis="z")
    sp = s.fx("spin", "ring", rg, pivot=C)
    wring(sp, C, RING_R, 40, (0, 0.3, 0.28), "ringglow", axis="z",
          styles=["ringglow"] * 4 + ["ice"])
    wring(sp, C, RING_R - 0.7, 20, (0, 0.42, 0.5), "ringband", axis="z",
          styles=["ringband", "navy"])
    for k in range(5):
        a = math.radians(k * 72 + 18)
        M = (C[0] - RING_R * math.sin(a), C[1] + RING_R * math.cos(a), C[2])
        moon(sp, M, 0.6 if k % 2 else 0.5)
    du = s.fx("spin", "dust", rg, pivot=C)
    wring(du, C, RING_R + 0.85, 24, (0.42, 0.22, 0.22), "ice", axis="z")
