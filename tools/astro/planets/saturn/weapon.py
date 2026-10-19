# -*- coding: utf-8 -*-
"""土星（クロノス）のナノウェポン「環刃 クロノス・リング」と星核「土星核 サターン・コア」。

環刃（kind ring）: YZ 平面の大きな円環の刃（チャクラム）。握りから伸びる二本の軌条（中央の柄）が環の
直径を貫き、その間を歯の付いた外刃が回る（fx_spin_saw）。内側の金の環には時計の目盛り、中心の軸には
小さな環を持つ土星の球と、時針・分針（fx_spin_hour / fx_spin_min）。

武器空間: 握りの中心 = 原点、環の中心 = (0, 0, C_Z)（-Z 側）、環は YZ 平面、平の法線 = ±X。
手に持つと 0.8 倍（astro_hold.SPEC["ring"]）。握りの前後 ±3.25 は篭手に隠れるので、
軌条の付け根（襟）は z = -3.4 より先、歯の一番後ろも z = -3.3 より先に置く。

v1.1（7 頭身のスーツに合わせた細部）: 大きな形（全長・握り・環の中心と半径）は v1.0 のまま、部品を細かく割った。
  form_0_grip   柄巻（暗い節で区切る）・リベット留めの金の口金・柄頭（光の十字の溝・褐色の帯・
                4 本の爪で留めた紫の宝玉）
                └ fx_spin_pommel  柄頭を傾いて回る小さな光の環
  form_1_bar    二股の襟（褐色の帯・紫の宝玉・氷青の発振器・金の蓋・リベット）と二本の軌条
                （彫りの溝と光の芯・リベットの列・金の横木・前の留め金）。z 方向に伸びる
  form_2_ring   内側の金の環（両面に彫った褐色の溝・12 の目盛り）・縦の輻（紫の宝玉）・中心の土星の球と
                傾いた小さな環・軸受けの蓋
                └ fx_spin_hour / fx_spin_min  時針・分針
                └ fx_spin_moons  中心を巡る二つの衛星（金の帯）
  form_3_saw    外刃（淡い金の鋼の環・褐色の帯・氷青の刃・24 の歯・両面に出る 12 本の光の象嵌・紫の鋲）
                └ fx_spin_saw    外刃ごと回る

星核: 土星の球（縞）と、26.7° 傾いた環（紫の鋲。fx_spin_rings）を、ジャイロの籠（回る縦の環 fx_spin_gyro_a・
静止の六角の枠（頂点の光るレンズ）と、リベット留めの極の冠）が囲む。
"""
from __future__ import annotations

import math

import numpy as np

import astro_common as AC
import astro_weapon as W
from astro_paint import core_styles, weapon_styles
from hd_space import rot as _rot

KIND = "ring"

# 一人称: 環の平を画面に向けて右下に立てる（既定の向きでは環が真横から見えて細い線になる）
HOLD = {"fp": {"fwd": (-0.22, 0.9, 0.35), "flat": (0.3, 0.0, -1.0), "at": (11.5, -9.8, 15.0),
               "scale": 0.5}}
ICON = {"weapon": (90, 0, 35)}

C_Z = -12.2              # 環の中心（武器空間の z）
R_BAND = 5.55            # 内側の金の環
R_SAW = 7.05             # 外刃の中心線
SAW_W = 1.8              # 外刃の幅（半径方向）
RAIL_X = 0.62            # 軌条の x（外刃はその間を回る）

ICE = (150, 214, 255)
VIOLET = (142, 124, 255)


def _yz(r, a_deg, cx=0.0, cz=C_Z):
    """YZ 平面の輪の上の点（a=0 で +Y、a=90 で -Z。W.ring axis="x" と同じ向き）と、接線・半径の向き。"""
    t = math.radians(a_deg)
    p = np.array([cx, r * math.cos(t), cz - r * math.sin(t)])
    tan = np.array([0.0, -math.sin(t), -math.cos(t)])
    rad = np.array([0.0, math.cos(t), -math.sin(t)])
    return p, tan, rad


def _tooth(bone, r, a, size, style, spin=45.0, **kw):
    """外刃の歯: 輪の平面の中で 45° 回した菱形（外側の半分が三角に突き出る）。"""
    p, tan, rad = _yz(r, a)
    ax = np.cross(tan, rad)
    R = np.column_stack([tan, rad, ax]) @ _rot(0, 0, spin)
    return AC.mat_cube(bone, p, size, style, R, **kw)


def stud(bone, y, z, through, size=0.28, style="rivet", x=0.0):
    """リベット: 板を X 方向に貫く小さな箱（through = 板の厚み + 0.08 以上。1 個で両面に頭が出る）。"""
    return W.cbox(bone, (x, y, z), (through, size, size), style, uv_scale=12)


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄巻（暗い節で区切る）・リベット留めの口金・柄頭（爪で留めた紫の宝玉・回る光の輪）
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.2), 1.75, 6.4, "wrap", uv_scale=8)
    for z in (-1.75, -0.75, 1.15, 2.15):
        W.octa(grip, (0, 0, z), 1.9, 0.24, "frame_lt", uv_scale=10)
    W.octa(grip, (0, 0, 0.2), 1.95, 0.4, "band", uv_scale=8)
    for z, ln, step in ((-3.05, 0.6, -2.62), (3.55, 0.7, 3.06)):
        W.octa(grip, (0, 0, step), 2.0, 0.26, "frame", uv_scale=10)
        W.octa(grip, (0, 0, z), 2.25, ln, "gold", uv_scale=8)
        stud(grip, 0, z, 2.42)                                                   # ±X の面
        W.cbox(grip, (0, 0, z), (0.28, 2.42, 0.28), "rivet", uv_scale=12)        # ±Y の面
    # 柄頭: 金の八角の台（光の十字の溝）→ 褐色の帯 → 金の座 → 4 本の爪で留めた紫の宝玉
    W.octa(grip, (0, 0, 4.6), 2.2, 1.3, "plate", uv_scale=8)
    W.cbox(grip, (0, 0, 4.6), (2.3, 0.18, 0.8), "glow", uv_scale=12)
    W.cbox(grip, (0, 0, 4.6), (0.18, 2.3, 0.8), "glow", uv_scale=12)
    W.octa(grip, (0, 0, 5.35), 1.6, 0.5, "band", uv_scale=10)
    W.cbox(grip, (0, 0, 5.72), (1.35, 1.35, 0.3), "gold", rotation=(0, 0, 45), uv_scale=10)
    W.cbox(grip, (0, 0, 6.0), (0.95, 0.95, 0.62), "gem_v", rotation=(0, 0, 45), uv_scale=12)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        W.beam(grip, (dx * 0.78, dy * 0.78, 5.62), (dx * 0.42, dy * 0.42, 6.2), 0.2, 0.2, "gold",
               uv_scale=12)
    # 柄頭を回る光の輪（土星の環の見立て。傾いて回る）
    pr = W.spin(m, grip, "pommel", (0, 0, 5.2), rotation=(0, 20, 0))
    W.ring(pr, (0, 0, 5.2), 1.55, 10, (0, 0.18, 0.2), "ring_ice", axis="z",
           styles=["ring_ice", "ring_ivory"], uv_scale=12)

    # =====================================================================
    #  form_1_bar — 襟（二股・層の鍔・発振器）と二本の軌条（彫りの溝・光の芯・リベット・横木）
    # =====================================================================
    bar = W.form(m, root, 1, "bar", (0, 0, -3.3))
    # 二股の襟（外刃の後ろの縁がこの間を通る）: 金の板 + 褐色の帯 + 前の氷青の発振器
    for s in (-1, 1):
        W.cbox(bar, (s * 0.8, 0, -4.45), (0.6, 2.6, 2.3), "plate", uv_scale=8)
        W.cbox(bar, (s * 1.12, 0, -4.45), (0.16, 1.9, 1.6), "band", uv_scale=10)
        W.cbox(bar, (s * 1.16, 0, -4.45), (0.16, 0.5, 0.5), "gem_v", rotation=(45, 0, 0), uv_scale=12)
        W.cbox(bar, (s * 0.8, 0, -5.64), (0.36, 0.7, 0.16), "glow", uv_scale=12)
    # 襟の上下の金の蓋と、両面を貫くリベット（外刃の後ろの縁はこの二股の間を回る）
    for s in (-1, 1):
        for t in (-1, 1):
            W.cbox(bar, (s * 0.8, t * 1.42, -4.45), (0.66, 0.3, 1.9), "gold", uv_scale=10)
        W.cbox(bar, (s * 0.8, 0.9, -3.72), (0.7, 0.26, 0.26), "rivet", uv_scale=12)
        W.cbox(bar, (s * 0.8, -0.9, -3.72), (0.7, 0.26, 0.26), "rivet", uv_scale=12)
    z0, z1 = -5.4, C_Z - R_BAND - 0.15
    zm, L = (z0 + z1) / 2, z0 - z1
    for s in (-1, 1):
        x = s * RAIL_X
        W.cbox(bar, (x, 0, zm), (0.5, 1.1, L), "plate", uv_scale=6)
        W.cbox(bar, (x + s * 0.26, 0, zm), (0.16, 0.52, L - 0.6), "band_d", uv_scale=8)   # 彫りの溝
        W.cbox(bar, (x + s * 0.29, 0, zm), (0.16, 0.24, L - 1.2), "glow", uv_scale=8)      # その芯の光
        for z in (-6.2, -7.6, -9.0, -15.4, -16.8):                                       # リベット
            W.cbox(bar, (x, 0.62, z), (0.28, 0.16, 0.28), "rivet", uv_scale=12)
            W.cbox(bar, (x, -0.62, z), (0.28, 0.16, 0.28), "rivet", uv_scale=12)
    # 横木（軌条を繋ぐ金の小さな梁。中心の球を避ける）
    for z in (-6.9, -8.3, -16.1):
        W.cbox(bar, (0, 0, z), (1.0, 0.5, 0.3), "gold", uv_scale=12)
    W.cbox(bar, (0, 0, z1 + 0.2), (1.9, 1.3, 0.4), "gold", uv_scale=10)      # 前の留め金
    W.cbox(bar, (0, 0, z1 - 0.06), (0.5, 0.5, 0.2), "gem_v", rotation=(0, 0, 45), uv_scale=12)

    # =====================================================================
    #  form_2_ring — 内側の金の環（両面に彫った褐色の溝・12 の目盛り）・縦の輻・中心の土星と環・
    #                軸受けの蓋・時針と分針・中心を巡る二つの衛星
    # =====================================================================
    rg = W.form(m, root, 2, "ring", (0, 0, C_Z))
    W.ring(rg, (0, 0, C_Z), R_BAND, 24, (0, 0.85, 1.0), "gold", axis="x", uv_scale=8)
    for s in (-1, 1):
        W.ring(rg, (s * 0.5, 0, C_Z), R_BAND, 12, (0, 0.28, 0.16), "band_d", axis="x", phase=15.0,
               uv_scale=10)
    for i in range(12):                                       # 目盛り（3 時ごとに紫で大きく）
        a = i * 30.0
        big = i % 3 == 0
        p, tan, rad = _yz(R_BAND - 0.05, a)
        R = np.column_stack([tan, rad, np.cross(tan, rad)])
        AC.mat_cube(rg, p, (0.42 if big else 0.26, 1.0 if big else 0.6, 1.3 if big else 1.16),
                    "gem_v" if big else "hand", R, uv_scale=12)
    # 縦の輻（12 時と 6 時。中ほどに紫の宝玉）
    for s in (-1, 1):
        W.cbox(rg, (0, s * 3.45, C_Z), (0.3, 3.3, 0.3), "gold", uv_scale=10)
        W.cbox(rg, (0, s * 3.45, C_Z), (0.36, 0.5, 0.5), "gem_v", rotation=(45, 0, 0), uv_scale=12)
    # 中心: 土星の球と、傾いた小さな環（静止）。軸受けの蓋（両面）
    W.sphere(rg, (0, 0, C_Z), 1.55, "globe", uv_scale=14)
    for s in (-1, 1):
        W.octa(rg, (s * 1.32, 0, C_Z), 0.9, 0.3, "gold", axis="x", uv_scale=12)
        W.cbox(rg, (s * 1.5, 0, C_Z), (0.16, 0.4, 0.4), "gem_v", rotation=(45, 0, 0), uv_scale=12)
    hub = W.part(m, rg, "hub_ring", (0, 0, C_Z), rotation=(22, 0, 26))
    W.ring(hub, (0, 0, C_Z), 2.45, 14, (0, 0.75, 0.16), "ring_ice", axis="y",
           styles=["ring_ice", "ring_ivory"], uv_scale=10)
    # 時針・分針（軌条の外側、両面に一本ずつ）
    hr = W.spin(m, rg, "hour", (0, 0, C_Z))
    mn = W.spin(m, rg, "min", (0, 0, C_Z))
    for s in (-1, 1):
        W.cbox(hr, (s * 1.04, 2.55, C_Z), (0.16, 2.3, 0.55), "hand", uv_scale=10)
        W.cbox(hr, (s * 1.04, 3.75, C_Z), (0.16, 0.45, 0.45), "hand", rotation=(45, 0, 0), uv_scale=12)
        W.cbox(mn, (s * 1.12, 0, C_Z - 2.95), (0.16, 0.4, 3.3), "hand", uv_scale=10)
    # 中心を巡る二つの衛星（軌条の外、針より外の面）
    mo = W.spin(m, rg, "moons", (0, 0, C_Z))
    for s, a in ((-1, 40.0), (1, 220.0)):
        p, _tan, _rad = _yz(3.2, a)
        W.cbox(mo, (s * 1.55, p[1], p[2]), (0.72, 0.72, 0.72), "moon", uv_scale=14)
        W.cbox(mo, (s * 1.55, p[1], p[2]), (0.64, 0.64, 0.64), "moon", rotation=(45, 0, 0), uv_scale=14)
        W.cbox(mo, (s * 1.55, p[1], p[2]), (0.86, 0.2, 0.86), "gold", rotation=(0, 45, 0), uv_scale=12)

    # =====================================================================
    #  form_3_saw — 外刃（回る）: 淡い金の鋼・褐色の帯・氷青の刃・歯・両面の光の象嵌
    # =====================================================================
    sw = W.form(m, root, 3, "saw", (0, 0, C_Z))
    saw = W.spin(m, sw, "saw", (0, 0, C_Z))
    W.ring(saw, (0, 0, C_Z), R_SAW, 24, (0, SAW_W, 0.5), "blade", axis="x",
           styles=["blade", "blade_b"], uv_scale=6)
    W.ring(saw, (0, 0, C_Z), R_SAW - SAW_W / 2 + 0.12, 24, (0, 0.24, 0.62), "band", axis="x", uv_scale=8)
    W.ring(saw, (0, 0, C_Z), R_SAW + SAW_W / 2 + 0.05, 24, (0, 0.34, 0.36), "edge", axis="x", uv_scale=8)
    for i in range(24):                                       # 歯（ひとつおきに大きく）
        a = i * 15.0 + 7.5
        big = i % 2 == 0
        sz = (1.05, 1.05, 0.34) if big else (0.7, 0.7, 0.3)
        _tooth(saw, R_SAW + SAW_W / 2 + (0.05 if big else 0.0), a, sz, "tooth", uv_scale=10)
    # 光の象嵌（12 本。刃を X 方向に貫いて両面に出る）と、その間の紫の小さな鋲
    for i in range(12):
        a = i * 30.0 + 15.0
        p, tan, rad = _yz(R_SAW + 0.15, a)
        R = np.column_stack([tan, rad, np.cross(tan, rad)])
        AC.mat_cube(saw, p, (1.1, 0.24, 0.6), "inlay", R, uv_scale=12)
    for i in range(6):
        a = i * 60.0
        p, tan, rad = _yz(R_SAW - 0.2, a)
        R = np.column_stack([tan, rad, np.cross(tan, rad)]) @ _rot(0, 0, 45)
        AC.mat_cube(saw, p, (0.36, 0.36, 0.62), "gem_v", R, uv_scale=12)


def build_core(m, root):
    """土星核: 縞の球と 26.7° 傾いた環を、ジャイロの籠が囲む。直径約 6.6。"""
    # 静止の枠: 正面向きの六角の枠（頂点に氷青のレンズ）と、上下の極の冠（リベット）
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    ap = 3.05
    for k in range(6):
        phi = math.radians(30 + 60 * k)
        rad = np.array([math.cos(phi), math.sin(phi), 0.0])
        tan = np.array([math.sin(phi), -math.cos(phi), 0.0])
        R = np.column_stack([tan, rad, (0, 0, 1.0)])
        AC.mat_cube(cage, tuple(rad * ap), (ap * 2 / math.sqrt(3) + 0.3, 0.42, 0.6),
                    "gold" if k % 3 else "band", R, uv_scale=10)
        v = math.radians(60 * k)
        rv = ap * 2 / math.sqrt(3) + 0.05
        if k % 3:                                            # 極の冠の無い頂点に、金の座と光るレンズ
            W.cbox(cage, (rv * math.cos(v), rv * math.sin(v), 0), (0.5, 0.5, 0.72), "plate",
                   rotation=(0, 0, 60 * k), uv_scale=12)
            W.cbox(cage, (rv * math.cos(v), rv * math.sin(v), 0), (0.3, 0.3, 0.8), "glow",
                   rotation=(0, 0, 60 * k), uv_scale=12)
    for s in (-1, 1):
        y = s * 3.3
        W.octa(cage, (0, y, 0), 1.4, 0.6, "plate", axis="y", uv_scale=10)
        W.octa(cage, (0, y + s * 0.45, 0), 0.9, 0.4, "band", axis="y", uv_scale=10)
        W.cbox(cage, (0, y + s * 0.85, 0), (0.46, 0.46, 0.46), "gem_v", rotation=(0, 45, 0), uv_scale=12)
        W.cbox(cage, (0, y, 0), (1.58, 0.28, 0.28), "rivet", uv_scale=12)
        W.cbox(cage, (0, y, 0), (0.28, 0.28, 1.58), "rivet", uv_scale=12)
    for s in (-1, 1):                                        # 左右の留め具
        W.cbox(cage, (s * 2.95, 0, 0), (0.6, 0.9, 0.9), "plate2", uv_scale=10)
        W.cbox(cage, (s * 3.28, 0, 0), (0.2, 0.5, 0.5), "glow", uv_scale=12)
    # 土星（ゆっくり自転）
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    gs = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(gs, (0, 0, 0), 1.45, "globe", uv_scale=16)
    # 土星の環（26.7° 傾けて回す）
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    sr = W.spin(m, rings, "rings", (0, 0, 0), rotation=(0, 0, 27))
    W.ring(sr, (0, 0, 0), 2.35, 16, (0, 0.85, 0.16), "ring_ice", axis="y",
           styles=["ring_ice", "ring_ivory"], uv_scale=12)
    W.ring(sr, (0, 0.12, 0), 2.35, 4, (0.3, 0.3, 0.16), "gem_v", axis="y", phase=22.5, uv_scale=12)
    # ジャイロの環: 縦の環（鉛直軸まわり）
    ga = W.spin(m, rings, "gyro_a", (0, 0, 0))
    W.ring(ga, (0, 0, 0), 2.75, 14, (0, 0.24, 0.42), "gold", axis="x", styles=["gold", "band"],
           uv_scale=10)


# ---------------------------------------------------------------------------
#  塗り
# ---------------------------------------------------------------------------
def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        # 外刃: 淡い金の鏡面（映り込み）とその色違い。歯はアイボリーの鋼
        blade={"kind": "blade", "base": (234, 222, 192), "light": (255, 251, 238), "dark": (178, 160, 120),
               "line": (90, 70, 40), "glint_period": 14},
        blade_b={"kind": "blade", "base": (220, 196, 146), "light": (252, 238, 204), "dark": (160, 134, 86),
                 "line": (80, 60, 34), "glint_period": 14},
        tooth={"kind": "blade", "base": (226, 228, 236), "light": (252, 252, 255),
               "dark": (150, 156, 176), "line": (60, 64, 82), "outline": True},
        edge={"glow": ICE, "sat": 0.45, "emit": 30},
        band={"kind": "armor", "base": (160, 108, 62), "light": (214, 160, 104), "dark": (112, 74, 44),
              "line": (70, 44, 24), "panel": 0, "sheen": False},
        plate={"base": (222, 188, 118), "light": (250, 228, 172), "dark": (160, 126, 70),
               "line": (92, 66, 30), "bolts": False},
        hand={"kind": "trim", "base": (112, 96, 196), "light": (196, 186, 255), "dark": (46, 36, 96),
              "line": (24, 18, 50)},
        gem_v={"kind": "gem", "glow": (168, 150, 255), "deep": (52, 36, 120), "outline": False,
               "bevel": False},
        ring_ice={"kind": "glowline", "glow": (110, 180, 255), "light": (200, 236, 255), "bevel": False,
                  "outline": False, "emit": 30},
        ring_ivory={"kind": "armor", "base": (244, 232, 204), "light": (255, 252, 240),
                    "dark": (200, 182, 140), "line": (130, 110, 76), "panel": 0, "sheen": False},
        wrap={"base": (40, 30, 24), "strap": (160, 108, 62), "skin": (236, 226, 204)},
        band_d={"kind": "armor", "base": (112, 74, 44), "light": (150, 104, 64), "dark": (70, 46, 28),
                "line": (40, 26, 14), "panel": 0, "sheen": False},
        inlay={"kind": "glowline", "glow": (120, 196, 255), "light": (226, 246, 255), "bevel": False,
               "outline": False, "emit": 24},
        moon={"kind": "planet", "planet": "luna", "bevel": False, "outline": False, "radius": 1.45,
              "vary": 0},
        globe=W.globe_style("saturn", emit=170, shade=0.3),
    )


def CORE_STYLES(key):
    return core_styles(
        key,
        globe=W.globe_style("saturn", emit=110, shade=0.3),
        band={"kind": "armor", "base": (160, 108, 62), "light": (214, 160, 104), "dark": (112, 74, 44),
              "line": (70, 44, 24), "panel": 0, "sheen": False},
        gem_v={"kind": "gem", "glow": (168, 150, 255), "deep": (52, 36, 120), "outline": False,
               "bevel": False},
        ring_ice={"kind": "glowline", "glow": (110, 180, 255), "light": (200, 236, 255), "bevel": False,
                  "outline": False, "emit": 30},
        ring_ivory={"kind": "armor", "base": (244, 232, 204), "light": (255, 252, 240),
                    "dark": (200, 182, 140), "line": (130, 110, 76), "panel": 0, "sheen": False},
        plate={"base": (222, 188, 118), "light": (250, 228, 172), "dark": (160, 126, 70),
               "line": (92, 66, 30), "bolts": False},
    )


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）
#    v.astro_sw 攻撃の振り 0→1 / v.astro_fp 一人称で 1 / v.astro_usew 右クリック中 0→1
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        # 外刃は X 軸まわりに回る鋸（一周 3 秒）、時針・分針は時計の速さの見立て、衛星は中心を巡る
        "fx_spin_saw": {"rotation": ["q.anim_time * 120.0", 0, 0]},
        "fx_spin_hour": {"rotation": ["q.anim_time * 30.0", 0, 0]},
        "fx_spin_min": {"rotation": ["q.anim_time * 360.0", 0, 0]},
        "fx_spin_moons": {"rotation": ["-q.anim_time * 60.0", 0, 0]},
        "fx_spin_pommel": {"rotation": [0, 0, "q.anim_time * 90.0"]},
    },
    "swing": {
        # 振るたびに外刃が一気に一回転、針が進む
        "fx_spin_saw": {"rotation": ["v.astro_sw * 720.0", 0, 0]},
        "fx_spin_min": {"rotation": ["v.astro_sw * 360.0", 0, 0]},
        "fx_spin_moons": {"rotation": ["-v.astro_sw * 360.0", 0, 0]},
    },
    "form_axes": {"form_1_bar": "z"},
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": {"rotation": [0, "q.anim_time * 45.0", 0]},
        "fx_spin_rings": {"rotation": [0, "q.anim_time * 60.0", 0]},
        "fx_spin_gyro_a": {"rotation": [0, "q.anim_time * 90.0", 0]},
    },
}
