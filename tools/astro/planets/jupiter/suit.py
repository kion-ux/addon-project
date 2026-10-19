# -*- coding: utf-8 -*-
"""木星 — 雷帝機装 ゼウス（Zeus Frame）。v1.1: 7 頭身の重装の王。

ガス惑星の王。全形態でいちばん重い体格（frame7 の bulk 1.15、いちばん広い肩・厚い胸）を、
クリーム（帯 = zone）・褐色（縞 = belt）・錆色（rustband）を交互に重ねた帯状の装甲で包む:

  兜      小さな頭に金のジグザグの王冠（尖りが一周、正面に電光の宝玉）・稲妻色の厳しいバイザー・
          V の眉庇・面頬・機械の「ゼウスの髭」（三段の髭板と銅の留め金・口ひげ）・耳のテスラコイルとアンテナ
  胴      上が広い胸郭・帯と縞の胸板（銅の縁・リベット）・胸の中央で回る大赤斑の渦（fx_spin_grs）と
          それを囲む重い銅の襟（ボルトの輪・四方の留め具）・立ち上がる喉当て・脇の排気口・帯の腹板
  背中    嵐のタービン（回る 6 枚羽根 fx_spin_fan）・縞の推進剤タンク（小さなガス惑星の筒）・双発スラスター・
          避雷針のアンテナと稲妻形のヒレ（飾り）・ホース
  腰      ベルトの星核（木星の球）と左右のガリレオ衛星（イオ・エウロパ・ガニメデ・カリスト。それぞれ自転）・
          蓄電セル・細い前垂れ（稲妻の線）・帯を重ねた草摺・後ろ垂れ
  腕      帯を重ねた三段の肩当て（紋章・リベット）＋テスラコイルの塔（巻き線・トロイド・放電の玉・回る電光の輪 2 本）・
          二の腕の帯と銅の腕輪・肘の小さなコイルとピストン・手首へ開く篭手（稲妻の線）・コイルを巻いた拳
  脚      帯の腿当て（型番）・丸い膝の盾（銅の縁・ボルトの輪・宝玉）・膝の外のピストン・V の稜の脛当て・
          ふくらはぎの排気口・稲妻のヒレ・帯を重ねた重いサバトン（踵の噴射口）

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A（7 頭身の目安）。右側だけ作り `_r` を
付ける → 左は自動で鏡映。回転（統合版）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く /
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import math

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, layered_plate,  # noqa: F401
                        line_on, mirror_x, octa, piston, polyline, rbox, ring, rivets, rod,
                        sensor, stick, taper, vents)

CREAM = (234, 216, 184)      # 帯（zone）
TAN = (201, 142, 90)         # 縞（belt）
RUST = (217, 71, 43)         # 大赤斑・差し色
VOLT = (140, 236, 255)       # 電光
K = 1.15                     # frame7 の太さ（いちばんの巨体）
TW = 0.26                    # 縁取りの幅
LX = A.LEG_X                 # 脚の軸 -2.15
HZ = A.HEAD_Z                # 頭の中心の奥行き -0.25

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
             "stripe": {"dir": "h", "period": 9, "width": 2, "color": (220, 190, 146), "k": 0.6}},
    "belt": {"kind": "armor", "base": TAN, "light": (232, 186, 140), "dark": (150, 96, 58),
             "line": (92, 52, 28), "panel": 0,
             "stripe": {"dir": "h", "period": 7, "width": 2, "color": (176, 92, 54), "k": 0.7}},
    "rustband": {"kind": "armor", "base": RUST, "light": (246, 132, 96), "dark": (150, 44, 24),
                 "line": (90, 24, 12), "panel": 0,
                 "stripe": {"dir": "h", "period": 6, "width": 1, "color": (240, 120, 80), "k": 0.5}},
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
    "grs": {"kind": "energy", "glow": (196, 58, 34), "light": (255, 168, 118),
            "outline": False, "bevel": False, "waves": 5},
    "grs_arm": {"kind": "glowline", "glow": (255, 150, 96), "light": (255, 236, 214),
                "bevel": False, "outline": False, "emit": 40},
    "grs_band": {"kind": "glowline", "glow": (246, 214, 170), "light": (255, 246, 230),
                 "bevel": False, "outline": False, "emit": 70},
    "grs_eye": {"kind": "gem", "glow": (255, 120, 70), "deep": (120, 26, 12), "outline": False,
                "bevel": False},
    # ガリレオ衛星
    "io": {"kind": "gem", "glow": (255, 214, 64), "deep": (176, 92, 20), "outline": False,
           "bevel": False},
    "europa": {"kind": "gem", "glow": (236, 232, 222), "deep": (150, 108, 80), "outline": False,
               "bevel": False},
    "ganymede": {"kind": "gem", "glow": (176, 170, 162), "deep": (78, 72, 66), "outline": False,
                 "bevel": False},
    "callisto": {"kind": "gem", "glow": (120, 100, 86), "deep": (40, 32, 28), "outline": False,
                 "bevel": False},
    "core": {"halo": VOLT, "spin": 31},
    "serial": {"text": "ZS-05", "under": {"kind": "armor", "base": TAN, "panel": 0,
                                         "line": (92, 52, 28)},
               "ink": (60, 30, 16)},
    "hazard": {"c1": (140, 236, 255), "c2": (52, 38, 32)},
    "emblem": {"under": {"kind": "armor", "base": RUST, "panel": 0, "line": (90, 24, 12)},
               "color": VOLT},
    "face": {"kind": "armor", "base": (226, 214, 196), "panel": 0, "line": (90, 70, 54)},
    "beard": {"kind": "armor", "base": (244, 236, 220), "light": (255, 252, 244),
              "dark": (196, 180, 156), "line": (120, 100, 78), "panel": 0, "sheen": False,
              "stripe": {"dir": "v", "period": 3, "width": 1, "color": (200, 182, 156), "k": 0.6}},
    "lamp": {"kind": "glowline", "glow": (255, 196, 110), "light": (255, 244, 220),
             "bevel": False, "outline": False},
}

# ===========================================================================
#  部位アニメ（Molang）。回る物は v.astro_spin（空中・疾走で速く進む累積の時間）× 角速度。
#  揺れは v.astro_t。重み（v.astro_air / v.astro_run）は振れ幅にだけ掛ける。`_r` は左へ自動で鏡映
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        "fx_spin_grs": {"rotation": [0, 0, "v.astro_spin * 60.0"]},
        "fx_spin_fan": {"rotation": [0, 0, "-v.astro_spin * 240.0"]},
        "fx_spin_arc_r": {"rotation": [0, "v.astro_spin * 200.0", 0]},
        "fx_spin_arc2_r": {"rotation": [0, "-v.astro_spin * 140.0", 0]},
        "fx_spin_io": {"rotation": [0, "v.astro_spin * 150.0", 0]},
        "fx_spin_europa": {"rotation": [0, "v.astro_spin * 110.0", 0]},
        "fx_spin_ganymede": {"rotation": [0, "-v.astro_spin * 80.0", 0]},
        "fx_spin_callisto": {"rotation": [0, "-v.astro_spin * 50.0", 0]},
        "fx_glow_tesla_r": {"rotation": [0, "v.astro_spin * 90.0", 0]},
    },
    "thrust": {        # 空中: 電光の輪が揺れ、ノズルが真下へ向く
        "fx_spin_arc_r": {"rotation": ["v.astro_air * math.sin(v.astro_t * 540.0) * 10.0", 0, 0]},
        "back_thruster_r": {"rotation": ["-v.astro_air * 12.0", 0, 0]},
    },
    "sprint": {        # 疾走: ノズルが後ろへ向き、電光の輪が傾く
        "back_thruster_r": {"rotation": ["v.astro_run * 20.0", 0, 0]},
        "fx_spin_arc2_r": {"rotation": ["v.astro_run * (8.0 + math.sin(v.astro_t * 720.0) * 4.0)",
                                        0, 0]},
    },
}


# ===========================================================================
#  局所の道具
# ===========================================================================
def zigzag(bone, c, face, pts, w=0.18, t=0.16, style="volt"):
    """面の上を走る稲妻（(a, b) の点列を line_on で繋ぐ）。"""
    return [line_on(bone, c, face, pts[i], pts[i + 1], w, t, style) for i in range(len(pts) - 1)]


def coil(bone, centre, length, w_core, w_ring, n, axis="y", core="volt_core", ring_style="coil",
         ring_len=0.24):
    """テスラコイル: 光る芯（八角柱）に n 本の銅の巻き線を等間隔に巻く。"""
    c = list(centre)
    i = {"x": 0, "y": 1, "z": 2}[axis]
    out = octa(bone, centre, w_core, length, core, axis=axis)
    for k in range(n):
        p = list(c)
        p[i] = c[i] - length / 2 + length * (k + 0.5) / n
        out += octa(bone, tuple(p), w_ring, ring_len, ring_style, axis=axis)
    return out


def banded_tank(bone, centre, w, length, bands):
    """縞の筒（小さなガス惑星）: クリームの筒に、(位置 0..1, 長さ, 塗り) の帯を巻く + 両端の蓋。"""
    x, y, z = centre
    out = octa(bone, centre, w, length, "zone", axis="y")
    for t, ln, st in bands:
        out += octa(bone, (x, y - length / 2 + length * t, z), w + 0.12, ln, st, axis="y")
    out += octa(bone, (x, y + length / 2 + 0.12, z), w * 0.72, 0.28, "frame", axis="y")
    return out


# ===========================================================================
def build_suit(s: Suit):
    s.frame7(bulk=K, skip=("foot", "spine"))   # サバトンが足を、背嚢と腰板が背骨を包むので省く
    boots(s)
    legs(s)
    waist(s)
    moons(s)
    torso(s)
    back(s)
    arms(s)
    hands(s)
    shoulders(s)
    helmet(s)


# ---------------------------------------------------------------------------
#  サバトン（重い。帯を重ねたつま先・銅のつま先金具・踵の噴射口）
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (LX, 0.17, -1.22), (3.15, 0.34, 6.3), "dark")                          # 靴底
    shell = chamfer(b, (LX, 1.1, -0.75), (3.05, 1.6, 4.3), "zone", cut=0.36, axis="z")
    sb = stick(b, shell[1], "west", 0.5, 0.42, (3.6, 0.42, 0.16), "belt", sink=0.05)  # 外の縞
    line_on(b, sb, "west", (0.08, 0.5), (0.92, 0.5), 0.16, 0.15, "volt")
    rivets(b, shell[1], "west", 3, edge="top", margin=0.22, span=(0.2, 0.8), size=0.22)
    # 甲（褐色）と、つま先の板が三枚重なる（帯・錆色・銅）
    ins = rbox(b, (LX, 1.98, -1.95), (2.5, 0.5, 2.0), "belt", rot=(-30, 0, 0))
    rivets(b, ins, "up", 2, edge="bottom", margin=0.3, span=(0.3, 0.7))
    stick(b, ins, "up", 0.5, 0.75, (2.2, 0.3, 0.16), "rustband", sink=0.05)
    t1 = rbox(b, (LX, 1.05, -3.2), (2.85, 0.95, 1.1), "zone", rot=(-16, 0, 0))
    stick(b, t1, "north", 0.5, 0.5, (0.5, 0.5, 0.2), "gem", spin=45, sink=0.05)
    cbox(b, (LX, 0.62, -3.78), (2.5, 0.3, 0.3), "dark")
    rbox(b, (LX, 0.62, -4.08), (2.65, 0.72, 0.8), "rustband", rot=(-26, 0, 0))
    cbox(b, (LX, 0.33, -4.5), (2.3, 0.4, 0.34), "copper")                          # つま先の金具
    # 踵（褐色）と噴射口
    hl = cbox(b, (LX, 1.05, 1.38), (2.7, 1.5, 1.05), "plate2_b")
    octa(b, (LX, 0.75, 2.02), 1.3, 0.5, "frame", axis="z")
    cbox(b, (LX, 0.75, 2.3), (0.95, 0.95, 0.16), "thruster")
    # 足首の外を守る小さな板（ドラムは見せる）
    ag = rbox(b, (LX - 1.68, 2.6, 0.85), (0.32, 1.2, 1.4), "plate2", rot=(0, 0, -6))
    stick(b, ag, "west", 0.5, 0.5, (0.36, 0.36, 0.16), "volt", sink=0.05)


# ---------------------------------------------------------------------------
#  脚（腿・膝・脛）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前の帯の板（褐色の上板・錆の縞・稲妻・銅の下縁）と外の型番板。後ろと内側は骨格を見せる
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.75, -2.0), (3.1, 4.6, 0.5), "zone", top="belt",
                       rot=(-3, 0, 0), inset=0.34, trim="copper", trim_edge="bottom",
                       rivet="rivet", n_rivets=3, rivet_edge="top")
    stick(t, fr["top"], "north", 0.5, 0.6, (2.42, 0.42, 0.16), "rustband", sink=0.04)
    zigzag(t, fr["top"], "north", [(0.78, 0.12), (0.56, 0.36), (0.74, 0.42), (0.5, 0.74)])
    sd = rbox(t, (LX - 1.92, 11.2, 0.05), (0.5, 3.4, 3.0), "belt", rot=(0, 0, -3),
              decals={"west": {"decal": "serial", "text": "ZS-05", "ink": (60, 30, 16)}})
    rivets(t, sd, "west", 3, edge="bottom", margin=0.3)
    cbox(t, (LX - 1.78, 9.42, 0.05), (0.42, 0.36, 2.8), "copper")
    # 膝: 丸い盾（銅の縁・ボルトの輪・帯の盤・宝玉）と庇・外の油圧シリンダー
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    octa(k, (LX, 8.5, -1.98), 2.55, 0.4, "copper", axis="z")
    disc = octa(k, (LX, 8.5, -2.25), 2.05, 0.36, "zone", axis="z")
    cbox(k, (LX, 8.5, -2.47), (1.55, 0.34, 0.16), "rustband")
    ring(k, (LX, 8.5, -2.22), 1.12, 6, (0.22, 0.22, 0.16), "rivet", axis="z", phase=30)
    rbox(k, (LX, 8.5, -2.58), (0.62, 0.62, 0.22), "gem", rot=(0, 0, 45))
    aw = rbox(k, (LX, 9.95, -1.85), (2.6, 0.7, 0.85), "belt", rot=(30, 0, 0))     # 膝の庇
    rivets(k, aw, "north", 2, edge="bottom", margin=0.2, span=(0.25, 0.75), size=0.2)
    piston(k, (LX - 1.98, 10.9, 0.55), (LX - 1.82, 6.3, 0.45), r=0.27, style="frame",
           rod_style="chrome", cap_style="dark")
    _ = disc
    # 脛: クリームの板 + 帯（錆・褐色）+ 褐色の V の稜（稲妻）、両脇の板、ふくらはぎの排気口、外のヒレ
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 4.75, -1.66), (2.95, 5.2, 0.5), "zone", rot=(4, 0, 0))
    stick(g, front, "north", 0.5, 0.82, (2.85, 0.5, 0.16), "rustband", sink=0.04)
    stick(g, front, "north", 0.5, 0.3, (2.85, 0.4, 0.16), "belt", sink=0.04)
    stick(g, front, "north", 0.5, 0.04, (2.8, TW, 0.18), "copper", sink=0.05)
    keel = rbox(g, (LX - 0.4, 4.9, -1.98), (0.82, 4.3, 0.5), "belt", rot=(4, 24, 0))
    kz = line_on(g, keel, "north", (0.5, 0.1), (0.5, 0.9), 0.16, 0.16, "volt")
    mirror_x(g, keel, kz, about=LX)
    sd = rbox(g, (LX - 1.56, 4.85, -0.15), (0.45, 4.9, 2.8), "belt", rot=(0, 0, -4))
    rivets(g, sd, "west", 3, edge="bottom", margin=0.32)
    mirror_x(g, sd, about=LX)
    calf = rbox(g, (LX, 6.2, 1.95), (2.4, 2.6, 0.45), "plate_b", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.2, 0.2, 0.8, 0.8))
    fin = rbox(g, (LX - 2.0, 5.6, 0.8), (0.38, 3.3, 2.0), "belt", rot=(-10, 0, -8))
    line_on(g, fin, "west", (0.15, 0.3), (0.85, 0.72), 0.18, 0.16, "volt")


# ---------------------------------------------------------------------------
#  腰（ベルト・星核のバックル・蓄電セル・前垂れ・腰の脇の板・草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    bl = chamfer(w, (0, 17.05, 0.15), (7.1, 1.05, 4.8), "frame", cut=0.45, axis="y")
    cbox(w, (0, 17.05, -2.3), (6.3, 0.72, 0.26), "plate2")                         # 褐色の帯
    for y in (17.5, 16.6):
        cbox(w, (0, y, -2.32), (6.5, 0.2, 0.3), "copper")
    # バックル: 銅の八角の台 + 木星の星核 + 電光の輪（脈動）
    octa(w, (0, 17.05, -2.55), 1.75, 0.4, "copper", axis="z")
    cbox(w, (0, 17.05, -2.82), (1.15, 1.15, 0.3), "core")
    gl = s.fx("glow", "buckle", w, pivot=(0, 17.05, -2.95))
    ring(gl, (0, 17.05, -2.95), 0.95, 8, (0, 0.18, 0.2), "volt", axis="z")
    # 前垂れ（細い褐色の板。腿の前を隠さない幅）: 錆の縞・稲妻・銅の下縁
    fp = layered_plate(w, (0, 15.3, -2.12), (2.1, 2.6, 0.4), "plate2_b", top="belt",
                       rot=(-8, 0, 0), inset=0.25, trim="copper", trim_edge="bottom",
                       rivet="rivet", n_rivets=2, rivet_edge="top")
    zigzag(w, fp["top"], "north", [(0.55, 0.88), (0.38, 0.55), (0.62, 0.5), (0.45, 0.15)])
    # 腰の脇の板（股関節の前を覆う。クリームに錆の縞）
    hp = rbox(w, (-2.42, 15.82, -1.98), (2.0, 1.45, 0.45), "zone", rot=(-8, 14, 4))
    hps = stick(w, hp, "north", 0.5, 0.35, (1.9, 0.3, 0.16), "rustband", sink=0.04)
    hpr = rivets(w, hp, "north", 2, edge="top", margin=0.25, span=(0.25, 0.75), size=0.22)
    mirror_x(w, hp, hps, hpr)
    # 後ろ垂れ（クリーム + 褐色の縞 + 警告の帯 + リベット）
    rs = rbox(w, (0, 15.1, 2.55), (4.8, 2.7, 0.5), "zone", rot=(14, 0, 0))
    stick(w, rs, "south", 0.5, 0.7, (4.6, 0.5, 0.16), "belt", sink=0.04)
    stick(w, rs, "south", 0.5, 0.22, (3.0, 0.4, 0.16), "hazard", sink=0.04)
    rivets(w, rs, "south", 3, edge="top", margin=0.22, span=(0.2, 0.8), size=0.22)
    # 草摺（腰の横。付け根で外へ開く。クリームの下板 + 褐色の上板 + 錆の縞 + 銅の縁 + 稲妻 + リベット）
    ts = s.part("waist", "tasset_r", w, pivot=(-3.35, 16.6, 0.0), rotation=(0, 0, 8))
    base = layered_plate(ts, (-3.62, 15.15, 0.0), (0.45, 2.8, 3.5), "zone", top="belt",
                         face="west", inset=0.34, trim="copper", trim_edge="bottom",
                         rivet="rivet", n_rivets=3, rivet_edge="top")
    stick(ts, base["top"], "west", 0.5, 0.62, (2.7, 0.36, 0.16), "rustband", sink=0.04)
    line_on(ts, base["top"], "west", (0.15, 0.32), (0.85, 0.32), 0.18, 0.16, "volt")
    cbox(ts, (-3.42, 16.3, 0.0), (0.5, 0.55, 1.6), "dark")                         # 蝶番


def moons(s):
    """ベルトに嵌めたガリレオ衛星: 暗い受け座 + 銅の留め具 + 自転する球（fx_spin_<名前>）。
    内から イオ・エウロパ（右）／ ガニメデ・カリスト（左）。"""
    w = s.bone("waist_belt")
    for name, x, st, sz in (("io", -1.55, "io", 0.6), ("europa", -2.62, "europa", 0.55),
                            ("ganymede", 1.55, "ganymede", 0.66), ("callisto", 2.62, "callisto", 0.62)):
        octa(w, (x, 17.05, -2.5), 0.9, 0.24, "dark", axis="z")
        sp = s.fx("spin", name, w, pivot=(x, 17.05, -2.85))
        cbox(sp, (x, 17.05, -2.85), (sz, sz, sz), st)
        rbox(sp, (x, 17.05, -2.85), (sz * 0.92, sz * 0.92, sz * 0.92), st, rot=(0, 45, 0))


# ---------------------------------------------------------------------------
#  胴（胸郭・帯の胸板・大赤斑の渦と銅の襟・喉当て・脇の排気口・腹の板）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.35, 0.0), (10.0, 3.7, 5.8), "plate", cut=0.95, axis="y")  # 上が広い
    chamfer(c, (0, 21.65, -0.05), (7.9, 2.5, 5.2), "plate_b", cut=0.7, axis="y")
    sl = rbox(c, (-4.32, 22.2, 0.0), (0.55, 3.2, 4.6), "belt", rot=(0, 0, -26))     # 脇の斜面
    mirror_x(c, sl)
    # 胸板: 外へ開き、内側の端が前へ。クリームに褐色の縞・銅の上縁・リベット、下に錆色の板
    pec = rbox(c, (-2.95, 24.25, -2.95), (3.7, 2.6, 0.55), "zone", rot=(6, 17, 9))
    pt = stick(c, pec, "north", 0.5, 0.94, (3.55, TW, 0.18), "copper", sink=0.05)
    pb = stick(c, pec, "north", 0.5, 0.42, (3.55, 0.6, 0.16), "belt", sink=0.05)
    pr = rivets(c, pec, "north", 3, edge="bottom", margin=0.2, span=(0.2, 0.8), size=0.22)
    low = rbox(c, (-2.25, 21.95, -2.68), (3.2, 1.5, 0.5), "rustband", rot=(-8, 12, 12))
    lr = rivets(c, low, "north", 2, edge="bottom", margin=0.26, span=(0.3, 0.75), size=0.22)
    lg = stick(c, low, "north", 0.5, 0.92, (3.0, 0.2, 0.15), "copper", sink=0.05)
    mirror_x(c, pec, pt, pb, pr, low, lr, lg)
    # 胸の中央の稜（褐色）: 喉から渦の上へ
    kl = rbox(c, (0, 25.35, -2.98), (1.1, 1.5, 0.5), "belt", rot=(-10, 0, 0))
    line_on(c, kl, "north", (0.5, 0.15), (0.5, 0.85), 0.18, 0.16, "volt")
    # 大赤斑の炉: 暗い受け座 → 金の内縁 → 重い銅の襟（ボルトの輪・四方の留め具）→ 回る渦
    Y = 23.0
    octa(c, (0, Y, -3.05), 3.4, 0.5, "dark", axis="z")
    octa(c, (0, Y, -3.3), 2.35, 0.24, "gold", axis="z")
    ring(c, (0, Y, -3.38), 1.55, 8, (0, 0.5, 0.45), "copper", axis="z", phase=22.5)
    ring(c, (0, Y, -3.62), 1.55, 8, (0.22, 0.22, 0.16), "rivet", axis="z")
    for k in range(4):
        a = math.radians(45 + 90 * k)
        rbox(c, (-1.95 * math.sin(a), Y + 1.95 * math.cos(a), -3.25), (0.55, 0.42, 0.5), "copper",
             rot=(0, 0, -(45 + 90 * k)))
    sp = s.fx("spin", "grs", c, pivot=(0, Y, -3.45))
    octa(sp, (0, Y, -3.46), 2.05, 0.24, "grs", axis="z")
    for k in range(3):                                                      # 渦の腕（3 本の弧）
        pts = []
        for j in range(4):
            a = math.radians(120 * k + j * 48)
            r = 0.22 + j * 0.25
            pts.append((-r * math.sin(a), Y + r * math.cos(a), -3.6))
        polyline(sp, pts, 0.24, 0.16, "grs_arm", overlap=0.14)
    for k in range(2):                                                      # 帯の弧（クリーム）
        a = math.radians(60 + 180 * k)
        rbox(sp, (-0.82 * math.sin(a), Y + 0.82 * math.cos(a), -3.58), (0.7, 0.18, 0.16),
             "grs_band", rot=(0, 0, -(60 + 180 * k)))
    rbox(sp, (0, Y, -3.66), (0.62, 0.62, 0.18), "grs_eye", rot=(0, 0, 45))
    # 喉当て（首の両脇に立ち上がる褐色の板 + クリームの上板 + 銅の縁）と前の錆色の板
    col = rbox(c, (-1.85, 26.3, 0.35), (1.55, 1.15, 3.8), "belt", rot=(0, 0, -24))
    colt = stick(c, col, "up", 0.5, 0.5, (1.2, 3.5, 0.2), "zone", sink=0.06)
    colg = stick(c, col, "west", 0.5, 0.06, (3.6, TW, 0.18), "copper", sink=0.05)
    cf = rbox(c, (-1.0, 26.0, -2.1), (1.65, 0.95, 0.45), "rustband", rot=(-20, 30, -10))
    mirror_x(c, col, colt, colg, cf)
    sensor(c, (-1.25, 25.15, -3.02), 0.26, "lamp", "dark")
    sensor(c, (1.25, 25.15, -3.02), 0.26, "volt", "dark")
    # 肩の付け根（肩当ての下）と脇の排気口
    yk = rbox(c, (-4.0, 26.0, 0.0), (2.1, 0.55, 3.9), "plate_b", rot=(0, 0, -8))
    sv = cbox(c, (-4.82, 23.7, 0.45), (0.4, 2.0, 2.5), "belt")
    svv = vents(c, sv, "west", 3, box=(0.15, 0.2, 0.85, 0.8))
    mirror_x(c, yk, sv, svv)
    # 背の肩甲の板（バックパックの両脇）
    sb = rbox(c, (-3.35, 24.35, 2.95), (2.9, 2.6, 0.45), "zone", rot=(-6, -10, 0))
    sbs = stick(c, sb, "south", 0.5, 0.35, (2.8, 0.45, 0.16), "belt", sink=0.04)
    mirror_x(c, sb, sbs)
    # 腹: 下ほど細い三枚の帯（クリーム・褐色・錆色）と中央の溝・脇のリベット
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))
    for i, (y, ww, st) in enumerate(((19.95, 4.2, "zone"), (18.95, 3.8, "belt"),
                                     (17.95, 3.4, "rustband"))):
        p = rbox(ab, (0, y, -2.05 + i * 0.05), (ww, 0.82, 0.48), st, rot=(-8, 0, 0))
        stick(ab, p, "north", 0.5, 0.5, (0.2, 0.6, 0.16), "dark", sink=0.08)
        r_ = rivets(ab, p, "north", 1, line=((0.1, 0.5), (0.1, 0.5)), size=0.22)
        mirror_x(ab, r_)
    lb = cbox(ab, (0, 18.95, 2.95), (2.4, 2.6, 0.45), "plate_b")                    # 背の腰板
    rivets(ab, lb, "south", 4, edge="border", margin=0.25, size=0.2)


# ---------------------------------------------------------------------------
#  背中（嵐のタービン・縞のタンク・双発スラスター・ホース・避雷針・稲妻のヒレ）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    pk = bevel(bk, (0, 22.4, 3.85), (5.0, 5.6, 2.0), "plate2", cut=0.6, axis="z")
    lid = rbox(bk, (0, 25.3, 3.5), (4.4, 0.8, 2.1), "zone", rot=(20, 0, 0))         # 上の蓋
    rivets(bk, lid, "up", 2, edge="bottom", margin=0.25, span=(0.2, 0.8), size=0.22)
    rivets(bk, pk[0], "south", 4, edge="border", margin=0.26, size=0.22)
    # 嵐のタービン: 暗い枠 → 銅の縁（ボルト）→ 光る吸気口 → 回る 6 枚羽根と鏡面の軸
    T = (0.0, 23.0)
    octa(bk, (T[0], T[1], 4.98), 3.5, 0.3, "frame", axis="z")
    ring(bk, (T[0], T[1], 5.18), 1.62, 8, (0, 0.38, 0.3), "copper", axis="z", phase=22.5)
    ring(bk, (T[0], T[1], 5.38), 1.62, 6, (0.2, 0.2, 0.16), "rivet", axis="z", phase=30)
    cbox(bk, (T[0], T[1], 5.12), (2.3, 2.3, 0.16), "volt_core")
    fan = s.fx("spin", "fan", bk, pivot=(T[0], T[1], 5.3))
    for k in range(6):
        a = 60 * k
        r = math.radians(a)
        rbox(fan, (-0.7 * math.sin(r), T[1] + 0.7 * math.cos(r), 5.28), (0.34, 1.15, 0.16),
             "copper", rot=(0, 0, -a + 28))
    octa(fan, (T[0], T[1], 5.38), 0.62, 0.24, "chrome", axis="z")
    cbox(fan, (T[0], T[1], 5.5), (0.3, 0.3, 0.16), "gem")
    # 下の排気口と警告の帯、灯り
    gr = cbox(bk, (0, 20.45, 4.86), (3.2, 0.9, 0.16), "frame")
    vents(bk, gr, "south", 3, box=(0.08, 0.15, 0.92, 0.85), w=0.18)
    cbox(bk, (0, 19.85, 4.82), (2.8, 0.36, 0.16), "hazard")
    sensor(bk, (-1.85, 24.8, 4.88), 0.26, "volt", "dark", facing=1)
    sensor(bk, (1.85, 24.8, 4.88), 0.26, "lamp", "dark", facing=1)
    # 縞の推進剤タンク（小さなガス惑星の筒）
    tk = banded_tank(bk, (-2.95, 22.25, 3.75), 1.15, 3.3,
                     [(0.3, 0.42, "rustband"), (0.7, 0.32, "belt")])
    mirror_x(bk, tk)
    # スラスター（右。下後ろへ）: 褐色の胴・銅の帯・広がったベル・電光の縁・噴射口・炎
    th = s.part("back", "thruster_r", bk, pivot=(-1.45, 19.9, 4.2), rotation=(18, 0, -8))
    octa(th, (-1.45, 19.0, 4.2), 1.55, 1.8, "plate2", axis="y")
    octa(th, (-1.45, 19.65, 4.2), 1.75, 0.3, "copper", axis="y")
    octa(th, (-1.45, 18.6, 4.2), 1.7, 0.26, "rustband", axis="y")
    octa(th, (-1.45, 17.7, 4.2), 2.0, 0.9, "frame", axis="y")
    ring(th, (-1.45, 17.28, 4.2), 0.82, 6, (0, 0.22, 0.22), "volt", axis="y")
    cbox(th, (-1.45, 17.26, 4.2), (1.4, 0.16, 1.4), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.45, 17.2, 4.2))
    taper(fx, (-1.45, 17.2, 4.2), (-1.45, 11.4, 4.2), 1.6, 0.36, 2, "flame")
    taper(fx, (-1.45, 17.15, 4.2), (-1.45, 14.1, 4.2), 0.78, 0.2, 2, "flame_core", round_=False)


# ---------------------------------------------------------------------------
#  腕（二の腕・肘・篭手）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = layered_plate(ua, (X - 1.58, 21.35, 0.0), (0.5, 3.2, 2.85), "zone", top="belt",
                       rot=(0, 0, 3), face="west", inset=0.32, trim="copper", trim_edge="bottom",
                       rivet="rivet", n_rivets=2, rivet_edge="top")
    zigzag(ua, op["top"], "west", [(0.3, 0.85), (0.6, 0.5), (0.4, 0.15)])
    upf = rbox(ua, (X - 0.1, 21.45, -1.66), (2.1, 2.9, 0.42), "belt", rot=(-3, 0, 0))
    stick(ua, upf, "north", 0.5, 0.62, (1.9, 0.42, 0.16), "rustband", sink=0.04)
    sensor(ua, (X - 0.1, 22.55, -1.92), 0.22, "volt", "dark")
    rbox(ua, (X - 0.1, 21.7, 2.08), (1.9, 2.3, 0.4), "plate_b", rot=(3, 0, 0))
    octa(ua, (X, 19.75, 0.02), 3.25, 0.34, "copper", axis="y")                     # 腕輪
    # 肘: 後ろの肘当て・外の小さなテスラコイル・外のピストン
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    cop = chamfer(el, (A.ELBOW[0], 18.55, 1.95), (2.2, 1.9, 0.6), "belt", cut=0.3, axis="z")
    rivets(el, cop[0], "south", 2, edge="bottom", margin=0.3, span=(0.3, 0.7), size=0.22)
    stick(el, cop[0], "south", 0.5, 0.65, (1.5, 0.3, 0.16), "rustband", sink=0.04)
    cx, cz = -8.45, 0.65
    beam(el, (-7.75, 18.5, cz), (cx + 0.25, 18.5, cz), 0.4, 0.4, "dark")             # 腕木
    coil(el, (cx, 18.5, cz), 1.6, 0.42, 0.78, 3, axis="y")
    # 篭手: 手首へ向かって開く（クリーム）+ 外の褐色の板（稲妻・リベット）+ 前の板 + 銅の袖口
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX = A.FOREARM_X
    hi = chamfer(fa, (FX - 0.1, 17.2, 0.0), (2.95, 1.9, 3.15), "zone", cut=0.45, axis="y")
    lo = chamfer(fa, (FX - 0.2, 15.72, 0.0), (3.2, 1.75, 3.35), "zone", cut=0.48, axis="y")
    stick(fa, hi[0], "north", 0.5, 0.15, (1.9, 0.36, 0.16), "rustband", sink=0.04)
    ob = rbox(fa, (FX - 1.95, 16.3, 0.0), (0.45, 3.2, 2.7), "belt", rot=(0, 0, 5))
    zigzag(fa, ob, "west", [(0.15, 0.85), (0.5, 0.55), (0.38, 0.45), (0.85, 0.12)])
    rivets(fa, ob, "west", 2, edge="top", margin=0.24, span=(0.25, 0.75), size=0.22)
    fv = rbox(fa, (FX - 0.15, 16.45, -1.8), (2.0, 2.2, 0.35), "belt", rot=(-5, 0, 0))
    fvb = stick(fa, fv, "north", 0.5, 0.5, (1.3, 1.7, 0.18), "zone", sink=0.06)
    stick(fa, fvb, "north", 0.5, 0.5, (1.3, 0.3, 0.16), "rustband", sink=0.04)
    rivets(fa, fv, "north", 2, edge="bottom", margin=0.18, span=(0.12, 0.88), size=0.2)
    chamfer(fa, (FX - 0.2, 14.72, 0.0), (3.28, 0.34, 3.45), "copper", cut=0.42, axis="y")  # 袖口
    sensor(fa, (FX - 0.1, 15.6, 1.75), 0.26, "volt", "dark", facing=1)


def hands(s):
    """手の甲の板と宝玉、指の甲当て（4 本の基節）、その上に巻いた「拳のコイル」、親指の当て。指は frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.5, 13.62, 0.0), (0.36, 1.75, 2.35), "zone", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.3, (2.2, 0.3, 0.16), "rustband", sink=0.04)
    stick(h, hb, "west", 0.5, 0.62, (0.6, 0.6, 0.2), "gem", sink=0.05)
    n = (-0.81, -0.58, 0.0)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        o = 0.34
        beam(h, (p0[0] + n[0] * o, p0[1] + n[1] * o, zf), (p1[0] + n[0] * o, p1[1] + n[1] * o, zf),
             0.56, 0.22, "belt")
    # 拳のコイル: 拳の甲の列に沿って（Z 方向）光る芯に銅の巻き線
    o = 0.66
    q = (-6.98 + n[0] * o + 0.12, 12.45 + n[1] * o + 0.08)
    coil(h, (q[0], q[1], 0.0), 2.45, 0.36, 0.64, 4, axis="z")
    rbox(h, (-5.62, 13.55, -1.85), (0.62, 0.9, 0.22), "belt", rot=(0, 0, -36))     # 親指の当て
    octa(h, (-6.1, 14.55, 0.0), 2.3, 0.24, "copper", axis="y")                     # 手首の輪


# ---------------------------------------------------------------------------
#  肩（帯を重ねた三段の肩当て + テスラコイルの塔）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    dome = chamfer(p, (-7.55, 25.65, 0.0), (4.5, 2.6, 5.5), "zone", cut=0.7, axis="x",
                 rot=(0, 0, -14))
    top = stick(p, dome[1], "up", 0.62, 0.5, (2.5, 3.9, 0.3), "belt", sink=0.1)
    stick(p, top, "up", 0.06, 0.5, (0.26, 3.9, 0.18), "copper", sink=0.08)
    stick(p, top, "up", 0.94, 0.5, (0.26, 3.9, 0.18), "copper", sink=0.08)
    rivets(p, top, "up", 4, edge="border", margin=0.24, size=0.22)
    stick(p, dome[0], "north", 0.5, 0.5, (3.6, 0.45, 0.16), "rustband", sink=0.04)
    stick(p, dome[0], "south", 0.5, 0.5, (3.6, 0.45, 0.16), "rustband", sink=0.04)
    # 外の縁: 上・外へ反り返る褐色の板（上端に銅）→ 肩の線を広く見せる
    rim = rbox(p, (-9.62, 25.35, 0.0), (0.5, 2.0, 5.6), "plate2", rot=(0, 0, -30))
    stick(p, rim, "up", 0.5, 0.5, (0.5, 5.6, 0.2), "copper", sink=0.05)
    rivets(p, rim, "west", 3, edge="bottom", margin=0.3, size=0.22)
    # 垂れ（帯の重なり: 錆色（紋章）→ 褐色 → クリーム）と銅の縁・リベットの列
    l1 = rbox(p, (-9.15, 23.55, 0.0), (0.55, 2.3, 5.1), "rustband", rot=(0, 0, 15),
              decals={"west": {"decal": "emblem", "color": VOLT}})
    stick(p, l1, "west", 0.5, 0.06, (4.9, TW, 0.18), "copper", sink=0.05)
    rivets(p, l1, "west", 3, edge="top", margin=0.24, size=0.22)
    l2 = rbox(p, (-9.38, 21.88, 0.05), (0.5, 1.6, 4.6), "belt", rot=(0, 0, 11))
    stick(p, l2, "west", 0.5, 0.08, (4.4, TW, 0.18), "copper", sink=0.05)
    rivets(p, l2, "west", 3, edge="top", margin=0.22, size=0.22)
    # 前後の小さな板とセンサー、後ろのヒレ
    fr = rbox(p, (-7.6, 24.45, -2.72), (2.8, 1.3, 0.4), "plate2_b", rot=(-12, 0, 0))
    sensor(p, (-7.95, 24.45, -2.98), 0.26, "lamp", "dark")
    rbox(p, (-7.6, 24.55, 2.72), (2.8, 1.3, 0.4), "plate2_b", rot=(12, 0, 0))
    # テスラコイルの塔: 台座 → 銅の輪 → 光る芯に 5 本の巻き線 → 鏡面のトロイド → 放電の玉 → 回る電光の輪 2 本
    X, Z, Y0 = -8.0, 0.2, 26.9
    tw = s.part("shoulders", "tesla_r", p, pivot=(X, Y0, Z), rotation=(0, 0, -6))
    octa(tw, (X, Y0 + 0.2, Z), 1.75, 0.45, "frame", axis="y")
    octa(tw, (X, Y0 + 0.52, Z), 1.4, 0.24, "copper", axis="y")
    coil(tw, (X, Y0 + 1.65, Z), 2.1, 0.62, 1.0, 4, axis="y")
    octa(tw, (X, Y0 + 2.95, Z), 1.6, 0.38, "chrome", axis="y")
    octa(tw, (X, Y0 + 2.95, Z), 1.25, 0.6, "steel", axis="y")
    g = s.fx("glow", "tesla_r", tw, pivot=(X, Y0 + 3.45, Z))
    octa(g, (X, Y0 + 3.45, Z), 0.62, 0.62, "volt", axis="y")
    for k in range(2):                                                      # 放電の小さな稲妻
        a = math.radians(60 + 180 * k)
        d = (-math.sin(a), math.cos(a))
        pts = [(X + d[0] * 0.3, Y0 + 3.5, Z + d[1] * 0.3),
               (X + d[0] * 0.75, Y0 + 3.85, Z + d[1] * 0.75),
               (X + d[0] * 0.95, Y0 + 3.65, Z + d[1] * 0.95),
               (X + d[0] * 1.35, Y0 + 4.05, Z + d[1] * 1.35)]
        polyline(g, pts, 0.16, 0.16, "volt", overlap=0.1)
    arc = s.fx("spin", "arc_r", tw, pivot=(X, Y0 + 1.75, Z), rotation=(18, 0, 10))
    ring(arc, (X, Y0 + 1.75, Z), 1.12, 8, (0.5, 0.16, 0.16), "volt", axis="y",
         styles=["volt", "glow_soft"])
    arc2 = s.fx("spin", "arc2_r", tw, pivot=(X, Y0 + 2.35, Z), rotation=(-16, 0, -12))
    ring(arc2, (X, Y0 + 2.35, Z), 0.9, 6, (0.42, 0.16, 0.16), "volt", axis="y",
         styles=["glow_soft", "volt"])


# ---------------------------------------------------------------------------
#  兜（ドーム・冠の縞・額・眉・面頬・こめかみ・頬当て・後頭部・しころ）・王冠・髭・耳のコイル・バイザー
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.7, HZ + 0.3), (4.5, 1.9, 4.95), "zone", cut=0.6, axis="z")
    chamfer(hm, (0, 31.64, HZ + 0.45), (3.6, 0.75, 4.3), "belt", cut=0.25, axis="z")  # 冠の縞
    cbox(hm, (0, 31.95, HZ + 0.5), (0.6, 0.3, 3.8), "rustband")                    # 中央の稜
    fh = rbox(hm, (0, 30.55, HZ - 2.25), (4.0, 1.1, 0.5), "zone", rot=(-22, 0, 0))  # 額の斜面
    stick(hm, fh, "north", 0.5, 0.25, (3.8, 0.26, 0.16), "rustband", sink=0.04)
    br = rbox(hm, (-1.0, 29.95, HZ - 2.5), (2.0, 0.45, 0.45), "belt", rot=(-8, 8, 10))  # 眉庇
    sd = cbox(hm, (-2.15, 29.0, HZ + 0.6), (0.4, 2.3, 3.6), "belt")                # こめかみ
    ck = rbox(hm, (-1.74, 28.32, HZ - 1.15), (0.45, 1.75, 2.15), "belt", rot=(0, 20, -10))  # 頬当て
    ckg = stick(hm, ck, "west", 0.06, 0.5, (0.22, 1.8, 0.16), "copper", sink=0.05)
    cks = stick(hm, ck, "west", 0.5, 0.7, (2.1, 0.26, 0.16), "rustband", sink=0.04)
    mirror_x(hm, br, sd, ck, ckg, cks)
    # 面頬（白）: 中央の稜へ折れた V の板・鼻筋
    fc = rbox(hm, (-0.62, 28.5, HZ - 2.3), (1.3, 1.1, 0.42), "face", rot=(8, 26, 0))
    mirror_x(hm, fc)
    cbox(hm, (0, 28.75, HZ - 2.62), (0.3, 1.0, 0.3), "plate2")
    # 後頭部（縞・排気口・中央の稜）としころ
    bh = cbox(hm, (0, 29.1, HZ + 2.65), (4.0, 2.4, 0.45), "zone")
    vents(hm, bh, "south", 3, box=(0.3, 0.25, 0.7, 0.65), w=0.18)
    rbox(hm, (0, 31.3, HZ + 2.6), (0.8, 1.6, 0.4), "rustband", rot=(35, 0, 0))
    rbox(hm, (0, 28.05, HZ + 2.72), (3.8, 0.75, 0.45), "belt", rot=(22, 0, 0))
    rbox(hm, (0, 27.55, HZ + 2.85), (3.3, 0.6, 0.42), "rustband", rot=(32, 0, 0))
    # 王冠（金の帯に、菱形の尖りが一周するジグザグ。正面の大きな尖りに電光の宝玉。飾り）
    cr = s.part("helmet", "crown", "head", pivot=(0, 31.1, HZ), ornament=True)
    yb = 31.12
    cbox(cr, (0, yb, HZ - 2.66), (4.4, 0.5, 0.22), "gold")
    cbox(cr, (0, yb, HZ + 2.98), (4.4, 0.5, 0.22), "gold")
    sdb = cbox(cr, (-2.4, yb, HZ + 0.16), (0.22, 0.5, 5.4), "gold")
    mirror_x(cr, sdb)
    for x, sz in ((-0.95, 0.78), (-1.85, 0.62)):
        f = rbox(cr, (x, yb + 0.25, HZ - 2.66), (sz, sz, 0.2), "gold", rot=(0, 0, 45))
        mirror_x(cr, f)
    rbox(cr, (0, yb + 0.42, HZ - 2.7), (1.05, 1.05, 0.24), "gold", rot=(0, 0, 45))
    rbox(cr, (0, yb + 0.42, HZ - 2.84), (0.5, 0.5, 0.16), "gem", rot=(0, 0, 45))
    for x in (-1.4, 1.4):
        cbox(cr, (x, yb - 0.02, HZ - 2.8), (0.22, 0.22, 0.16), "gem")
    for z in (-1.45, 0.1, 1.65):
        sp = rbox(cr, (-2.4, yb + 0.22, HZ + z), (0.2, 0.62, 0.62), "gold", rot=(45, 0, 0))
        mirror_x(cr, sp)
    for x in (-1.65, -0.55):
        bpk = rbox(cr, (x, yb + 0.22, HZ + 2.98), (0.62, 0.62, 0.2), "gold", rot=(0, 0, 45))
        mirror_x(cr, bpk)
    # 機械のゼウスの髭（口ひげ + 三段の髭板 + 銅の留め金 + 先の菱形。飾り = 頭の計測から外す）
    bd = s.part("helmet", "beard", "head", pivot=(0, 28.0, HZ - 2.3), ornament=True)
    mu = polyline(bd, [(-0.1, 28.12, HZ - 2.9), (-0.95, 27.92, HZ - 2.78),
                       (-1.38, 27.4, HZ - 2.55)], [0.44, 0.38], [0.38, 0.32], "beard",
                  overlap=0.16)
    mirror_x(bd, mu)
    for i, (y, wd, z) in enumerate(((27.55, 2.4, -2.55), (26.95, 2.0, -2.68), (26.38, 1.5, -2.8))):
        t = rbox(bd, (0, y, HZ + z), (wd, 0.66, 0.52), "beard", rot=(-10, 0, 0))
        stick(bd, t, "north", 0.5, 0.06, (wd - 0.3, 0.18, 0.16), "copper", sink=0.04)
        if i < 2:
            rr = rivets(bd, t, "north", 1, line=((0.12, 0.6), (0.12, 0.6)), size=0.2)
            mirror_x(bd, rr)
    rbox(bd, (0, 25.86, HZ - 2.9), (0.8, 0.8, 0.42), "beard", rot=(-10, 0, 45))
    cbox(bd, (0, 26.0, HZ - 3.1), (0.24, 0.24, 0.16), "volt")
    # 耳のテスラコイルとアンテナ（飾り）
    an = s.part("helmet", "antenna_r", "head", pivot=(-2.35, 29.2, HZ + 0.55), ornament=True)
    octa(an, (-2.5, 29.2, HZ + 0.55), 1.2, 0.3, "frame", axis="x")
    octa(an, (-2.7, 29.2, HZ + 0.55), 0.9, 0.24, "coil", axis="x")
    octa(an, (-2.9, 29.2, HZ + 0.55), 0.5, 0.24, "volt", axis="x")
    taper(an, (-2.5, 29.7, HZ + 0.9), (-2.78, 31.5, HZ + 2.05), 0.3, 0.16, 2, "copper",
          round_=False)
    cbox(an, (-2.8, 31.58, HZ + 2.1), (0.22, 0.22, 0.22), "volt")
    # バイザー: 暗い帯の上に、中央が下がる厳しい電光の目
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 29.45, HZ - 2.42), (3.7, 0.72, 0.3), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.45, HZ - 2.6))
    eye = rbox(fg, (-0.9, 29.42, HZ - 2.6), (1.45, 0.34, 0.18), "visor", rot=(0, 8, 9))
    mirror_x(fg, eye)
