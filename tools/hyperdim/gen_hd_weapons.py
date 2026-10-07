# -*- coding: utf-8 -*-
"""超次元バトルアーツ — 8 種の武器の 3D モデル・テクスチャ・アタッチャブル・アイコン。

武器空間: 原点 = 握りの中心、-Z = 刃先（前方）、+Y = 上、16 単位 = 1 ブロック。
刃の平（ひら）は ±X を向き、刃先（エッジ）は ±Y を向く。

各武器は「ボーンに箱を足していく builder」で、可動部（大剣の浮遊リング、弓の弦と
リム、鞭の 14 節、双剣・かぎ爪の左手側）は別ボーンに分けてアニメーションで動かす。
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hd_common import (ELEMENTS, NS, RP, SCRATCH, WEAPONS, arc_points, beam,  # noqa: E402
                       box, cbox, fill_tri_yz, lerp, polyline, write_json)
from hd_paint import HDPainter, mix, shade  # noqa: E402
from mcmodel import Model  # noqa: E402

GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", "hd")
ATT_DIR = os.path.join(RP, "attachables")
ICON_DIR = os.path.join(RP, "textures", "items", "hd")

BIND_MAIN = "q.item_slot_to_bone_name(c.item_slot)"
BIND_OFF = "c.item_slot == 'main_hand' ? 'leftitem' : 'rightitem'"


# ===========================================================================
#  共通スタイル（属性色から自動で組む）
# ===========================================================================
def styles_for(element, **over):
    e = ELEMENTS[element]
    g, lt, dp = e["glow"], e["light"], e["deep"]
    st = {
        "blade": {"kind": "blade", "base": (176, 186, 204), "light": (238, 244, 252),
                  "dark": (104, 112, 132), "line": (52, 56, 72), "glint_period": 20},
        "blade_tint": {"kind": "blade", "base": mix((170, 180, 198), g, 0.18),
                       "light": mix((240, 246, 255), lt, 0.4),
                       "dark": mix((92, 100, 124), dp, 0.35), "line": shade(dp, 0.6)},
        "blade_flat": {"kind": "blade", "base": mix((170, 180, 198), g, 0.18),
                       "light": mix((240, 246, 255), lt, 0.4),
                       "dark": mix((92, 100, 124), dp, 0.35), "outline": False,
                       "hi": 0.0, "lo": 1.1},
        "edge": {"kind": "edge", "glow": g, "emit": 60, "outline": False},
        "edge_hot": {"kind": "edge", "glow": g, "emit": 12, "outline": False,
                     "sat": 0.5},
        "metal": {"kind": "metal", "base": (62, 66, 84), "light": (120, 128, 150),
                  "dark": (34, 36, 48), "line": (16, 16, 24), "panel": 7},
        "metal_tint": {"kind": "metal", "base": mix((60, 64, 82), dp, 0.45),
                       "light": mix((126, 134, 160), g, 0.25),
                       "dark": shade(dp, 0.45), "line": (12, 12, 20), "panel": 6},
        "gold": {"kind": "gold", "base": (226, 172, 64), "light": (255, 236, 150),
                 "dark": (150, 96, 28), "line": (90, 52, 14)},
        "silver": {"kind": "gold", "base": (192, 198, 214), "light": (248, 250, 255),
                   "dark": (122, 128, 148), "line": (60, 64, 80)},
        "wrap": {"kind": "wrap", "base": (28, 26, 34), "strap": shade(dp, 1.25),
                 "skin": (222, 220, 210), "period": 6, "outline": False},
        "gem": {"kind": "gem", "glow": g, "deep": dp, "outline": False},
        "energy": {"kind": "energy", "glow": g, "light": lt, "outline": False},
        "void": {"kind": "void", "base": shade(dp, 0.35), "glow": g, "outline": False},
        "rune": {"kind": "rune", "base": (40, 42, 58), "glow": g},
        "crystal": {"kind": "crystal", "base": mix(g, (255, 255, 255), 0.25),
                    "line": shade(dp, 0.8)},
        "cloth": {"kind": "cloth", "base": shade(dp, 1.15), "hem": g, "hem_emit": 60,
                  "outline": False},
        "dark": {"kind": "dark", "base": (24, 22, 32), "glow": g, "line": (6, 6, 10)},
        "fur": {"kind": "fur", "base": (78, 64, 54), "outline": False},
        "ivory": {"kind": "ivory", "base": (236, 228, 206), "line": (120, 104, 84)},
    }
    for k, v in over.items():
        st[k] = dict(st.get(k, {}), **v)
    return st


def octa(bone, centre, w, length, style, axis="z", **kw):
    """八角柱（箱 + 45° 回した箱）。柄・長柄に使う。"""
    if axis == "z":
        size = (w, w, length)
        rot = (0, 0, 45)
    elif axis == "y":
        size = (w, length, w)
        rot = (0, 45, 0)
    else:
        size = (length, w, w)
        rot = (45, 0, 0)
    cbox(bone, centre, size, style, **kw)
    cbox(bone, centre, [s * (0.94 if s == w else 1.0) for s in size], style,
         rotation=rot, **kw)


def ring_band(bone, z, w, depth, style, **kw):
    cbox(bone, (0, 0, z), (w, w, depth), style, **kw)


# ===========================================================================
#  大剣「ディメンション・ブレイカー」— 次元断剣（蒼）
#  幅広の刃の中央に次元の裂け目が走り、鍔元には浮遊する次元環が回る。
# ===========================================================================
def build_greatsword(m: Model, root):
    # ---- 柄頭: 菱形の金具・宝玉・尖端 ----------------------------------
    cbox(root, (0, 0, 7.9), (2.4, 2.4, 1.4), "metal", uv_scale=8)
    cbox(root, (0, 0, 7.9), (2.9, 2.9, 0.7), "gold", rotation=(0, 0, 45), uv_scale=8)
    cbox(root, (0, 0, 9.0), (1.6, 1.6, 1.0), "gem", rotation=(0, 0, 45), uv_scale=10)
    cbox(root, (0, 0, 9.9), (0.8, 0.8, 1.0), "gold", rotation=(0, 0, 45), uv_scale=10)
    for s in (-1, 1):                                   # 柄頭の小さな翼
        beam(root, (0, s * 1.2, 8.2), (0, s * 2.6, 9.6), 0.6, 0.9, "gold", uv_scale=8)
    # ---- 柄: 八角の柄巻と金の帯 ----------------------------------------
    octa(root, (0, 0, 3.8), 1.7, 6.6, "wrap", uv_scale=8)
    for z, d in ((0.6, 0.7), (3.8, 0.45), (7.0, 0.7)):
        cbox(root, (0, 0, z), (2.1, 2.1, d), "gold", uv_scale=8)
        cbox(root, (0, 0, z), (2.1, 2.1, d * 0.9), "gold", rotation=(0, 0, 45), uv_scale=8)
    # ---- 鍔: 中央の機関部・左右の宝玉・後ろへ流れる翼 --------------------
    cbox(root, (0, 0, -1.5), (3.2, 5.2, 2.6), "metal_tint", uv_scale=6)
    cbox(root, (0, 0, -1.5), (3.6, 2.6, 1.6), "gold", uv_scale=6)
    for s in (-1, 1):
        cbox(root, (s * 1.85, 0, -1.5), (0.6, 1.8, 1.8), "gem", rotation=(45, 0, 0),
             uv_scale=10)
        # 翼の主骨（3 本の羽が後方＝柄側へ流れる）
        polyline(root, [(0, s * 2.4, -1.4), (0, s * 4.6, -0.4), (0, s * 6.6, 1.4),
                        (0, s * 7.6, 3.4)], [2.0, 1.6, 1.1], [1.5, 1.2, 0.8],
                 "metal_tint", uv_scale=6)
        polyline(root, [(0, s * 2.6, -2.4), (0, s * 5.0, -2.2), (0, s * 7.2, -1.0),
                        (0, s * 8.4, 0.6)], [1.2, 0.9, 0.6], [0.9, 0.7, 0.5],
                 "edge", uv_scale=8)
        polyline(root, [(0, s * 2.2, -0.2), (0, s * 3.8, 1.2), (0, s * 4.6, 2.8)],
                 [1.0, 0.7], [0.8, 0.6], "gold", uv_scale=8)
        cbox(root, (0, s * 7.7, 3.7), (0.9, 0.9, 0.9), "gem", rotation=(45, 0, 0),
             uv_scale=10)
    # ---- 刃元: 装甲板とスリット状の放熱口 ------------------------------
    cbox(root, (0, 0, -5.4), (2.0, 7.4, 4.4), "metal", uv_scale=6)
    for s in (-1, 1):
        for i in range(3):
            cbox(root, (s * 1.02, -1.8 + i * 1.8, -5.4), (0.12, 0.5, 3.0), "energy",
                 uv_scale=8)
        cbox(root, (s * 1.06, 3.1, -5.4), (0.2, 0.5, 4.0), "gold", uv_scale=8)
        cbox(root, (s * 1.06, -3.1, -5.4), (0.2, 0.5, 4.0), "gold", uv_scale=8)
    # ---- 刃身: 上下の二枚刃と、その間を走る次元の裂け目 -----------------
    z0, z1 = -7.6, -27.0
    L = z0 - z1
    for s in (-1, 1):
        cbox(root, (0, s * 2.1, (z0 + z1) / 2), (1.2, 2.4, L), "blade_tint", uv_scale=4)
        cbox(root, (0, s * 3.55, (z0 + z1) / 2), (0.55, 0.7, L), "edge", uv_scale=4)
        # 平に刻まれた発光ルーン
        cbox(root, (0, s * 2.15, -16.0), (1.26, 0.8, 12.0), "rune", uv_scale=8)
    cbox(root, (0, 0, -16.6), (0.5, 1.8, 17.4), "void", uv_scale=4)       # 裂け目の奥
    cbox(root, (0, 0, -16.6), (0.26, 0.5, 17.2), "energy", uv_scale=5)    # 裂け目の芯
    for z in (-9.0, -13.5, -18.0, -22.5):                                # 梯子状の橋
        cbox(root, (0, 0, z), (1.1, 1.9, 0.7), "metal_tint", uv_scale=6)
        cbox(root, (0, 0, z), (1.16, 0.5, 0.5), "gold", uv_scale=8)
    for i, z in enumerate((-9.0, -11.2, -13.4)):                          # 背の鋸刃
        cbox(root, (0, 3.9, z), (0.5, 1.3, 1.3), "edge", rotation=(45, 0, 0),
             uv_scale=8)
    # ---- 切先: 段で埋め、回転した刃先で輪郭を出す ----------------------
    apex = (0, 0, -35.9)
    for s in (-1, 1):
        fill_tri_yz(root, apex, (0, s * 3.4, z1 + 0.1), (0, -s * 3.4, z1 + 0.1), 1.05,
                    1.15, "blade_flat", uv_scale=5)
    cbox(root, (0, 0, z1 - 0.6), (1.15, 1.2, 2.0), "metal_tint", uv_scale=6)
    for s in (-1, 1):
        beam(root, (0, s * 3.75, z1 + 0.2), (0, s * 0.15, -36.2), 0.5, 0.75, "edge",
             uv_scale=5, extend=0.2)
    cbox(root, (0, 0, -26.4), (0.9, 1.6, 1.6), "gem", rotation=(45, 0, 0), uv_scale=10)

    # ---- 浮遊する次元環（別ボーンで回転させる） ------------------------
    ring = m.bone("ring", (0, 0, -6.0), parent="root")
    for i in range(8):
        a = i * 45.0
        r = 5.6
        x, y = r * math.cos(math.radians(a)), r * math.sin(math.radians(a))
        cbox(ring, (x, y, -6.0), (0.7, 1.9, 0.7), "crystal" if i % 2 else "energy",
             rotation=(0, 0, a + 90), uv_scale=8)
    for i in range(16):
        a = i * 22.5 + 11.25
        r = 5.6
        x, y = r * math.cos(math.radians(a)), r * math.sin(math.radians(a))
        cbox(ring, (x, y, -6.0), (0.3, 1.2, 0.3), "energy", rotation=(0, 0, a + 90),
             uv_scale=8)
    # 房飾り
    tassel = m.bone("tassel", (0, -0.8, 8.4), parent="root")
    for s in (-0.45, 0.45):
        cbox(tassel, (s, -3.2, 8.4), (0.25, 5.2, 0.9), "cloth", uv_scale=8,
             rotation=(0, 0, s * 8))
    cbox(tassel, (0, -1.0, 8.4), (1.2, 0.8, 1.2), "gold", uv_scale=8)


# ===========================================================================
#  双剣「ゼファー＆ガスト」— 疾風双刃（翠）
#  反りのある片刃の短剣を左右一対。三日月の鍔と、峰に生えた風切り羽。
# ===========================================================================
def _twin_blade(m, bone, mirror=1.0, accent="gold"):
    # 柄頭の環
    for i in range(4):
        a = i * 90
        cbox(bone, (0, 1.0 * math.sin(math.radians(a)), 6.6 + 1.0 * math.cos(math.radians(a))),
             (0.5, 0.5, 1.4), accent, rotation=(a, 0, 0), uv_scale=10)
    cbox(bone, (0, 0, 5.4), (1.4, 1.4, 0.8), "metal", uv_scale=10)
    octa(bone, (0, 0, 2.6), 1.35, 5.0, "wrap", uv_scale=10)
    for z in (0.3, 4.8):
        cbox(bone, (0, 0, z), (1.7, 1.7, 0.5), accent, uv_scale=10)
    # 三日月の鍔
    pts = arc_points((0, 0, -0.2), 3.6, -70, 70, 6, plane="yz")
    pts = [(0, p[1], p[2] + 3.4) for p in pts]
    polyline(bone, pts, [0.9] * 6, [0.9, 1.0, 1.2, 1.2, 1.0, 0.9], "metal_tint",
             uv_scale=8)
    polyline(bone, [(0, p[1] * 1.05, p[2] - 0.35) for p in pts], 0.45, 0.4, "edge",
             uv_scale=10)
    cbox(bone, (0, 0, -0.6), (1.9, 2.4, 1.4), accent, uv_scale=8)
    for s in (-1, 1):
        cbox(bone, (s * 1.0, 0, -0.6), (0.4, 1.3, 1.0), "gem", rotation=(45, 0, 0),
             uv_scale=12)
    # 反った刃: 峰（+Y 側）は黒鋼、刃（-Y 側）は発光
    n = 7
    spine, edge = [], []
    for i in range(n + 1):
        t = i / n
        z = lerp(-1.2, -17.5, t)
        bend = 2.6 * t * t
        half = lerp(1.35, 0.25, t ** 1.4)
        spine.append((0, 0.8 + bend - 0.15 * t, z))
        edge.append((0, -half * 1.6 + bend * 1.1, z))
    for i in range(n):
        top = spine[i][1]
        bot = edge[i][1]
        zc = (spine[i][2] + spine[i + 1][2]) / 2
        hgt = max(0.5, (top - bot))
        tilt = math.degrees(math.atan2((spine[i + 1][1] - spine[i][1]),
                                       -(spine[i + 1][2] - spine[i][2])))
        cbox(bone, (0, (top + bot) / 2, zc), (0.62 - i * 0.03, hgt, 2.5), "blade_tint",
             rotation=(-tilt, 0, 0), uv_scale=8)
    polyline(bone, spine, 0.75, 0.42, "dark", uv_scale=8)
    polyline(bone, edge, 0.36, 0.5, "edge", uv_scale=8)
    beam(bone, edge[-1], (0, spine[-1][1] + 0.6, -19.4), 0.32, 0.45, "edge",
         uv_scale=10, extend=0.3)
    # 峰の風切り羽
    for i, t in enumerate((0.25, 0.5)):
        k = int(t * n)
        p = spine[k]
        beam(bone, p, (0, p[1] + 1.9, p[2] + 2.6), 0.3, 0.7, "crystal", uv_scale=10)
    # 刃の付け根の発光スリット
    cbox(bone, (0, 0.0, -3.2), (0.7, 0.4, 3.0), "energy", uv_scale=10)


def build_twinblades(m: Model, root):
    _twin_blade(m, root, 1.0, "gold")
    left = m.bone("left", (0, 0, 0), binding=BIND_OFF)
    _twin_blade(m, left, -1.0, "silver")


# ===========================================================================
#  両手斧「ヴォルカニクス」— 紅蓮戦斧（紅）
#  長柄の先に三日月の双刃。斧頭の芯に溶岩炉が燃え、柄尻は槍の石突き。
# ===========================================================================
def build_greataxe(m: Model, root):
    # 長柄
    octa(root, (0, 0, -6.0), 1.6, 26.0, "metal", uv_scale=4)
    for z0, z1 in ((-1.8, 3.6), (5.2, 7.4)):                  # 握り
        octa(root, (0, 0, (z0 + z1) / 2), 1.85, z1 - z0, "wrap", uv_scale=8)
    for z in (-2.2, 3.9, 4.8, -9.0, -13.6):
        cbox(root, (0, 0, z), (2.2, 2.2, 0.6), "gold", uv_scale=8)
    # 発光する炎の溝
    for s in (-1, 1):
        cbox(root, (s * 0.82, 0, -11.3), (0.12, 0.5, 4.0), "energy", uv_scale=8)
    # 石突き
    cbox(root, (0, 0, 8.2), (2.2, 2.2, 1.6), "metal_tint", uv_scale=8)
    beam(root, (0, 0, 8.8), (0, 0, 12.2), 1.3, 1.3, "edge", uv_scale=8, roll=45)
    for s in (-1, 1):
        beam(root, (0, s * 0.8, 8.4), (0, s * 2.2, 10.2), 0.6, 0.7, "gold", uv_scale=8)
    # 斧頭の芯: 溶岩炉
    cbox(root, (0, 0, -21.2), (2.8, 4.4, 5.2), "metal_tint", uv_scale=6)
    cbox(root, (0, 0, -21.2), (3.0, 2.2, 3.2), "gold", uv_scale=6)
    for s in (-1, 1):
        cbox(root, (s * 1.45, 0, -21.2), (0.5, 1.7, 1.7), "gem", rotation=(45, 0, 0),
             uv_scale=10)
        for i in range(3):
            cbox(root, (s * 1.42, -1.6 + i * 1.6, -18.9), (0.12, 0.35, 1.0), "energy",
                 uv_scale=10)
    # 双刃: Y 方向へ段で広がる三日月
    # 刃の輪郭: 根元 (y=1.9) で幅 4、外縁 (y≈8.2) で幅 11 に開く三日月
    def half_w(y):
        t = (y - 1.9) / 6.4
        return 2.0 + 3.6 * t ** 1.35 + 0.6 * math.sin(t * math.pi) * 0.0
    levels = []
    y = 1.9
    while y < 7.9:
        yb = min(8.0, y + 0.75)
        hw = half_w((y + yb) / 2)
        levels.append((y, yb, -21.4 + hw, -21.4 - hw))
        y = yb
    for s in (-1, 1):
        for i, (ya, yb, za, zb) in enumerate(levels):
            cbox(root, (0, s * (ya + yb) / 2, (za + zb) / 2),
                 (1.25 - i * 0.05, yb - ya + 0.06, za - zb), "blade_flat", uv_scale=4)
        # 刃の平の炎の彫り（ルーン）
        cbox(root, (0, s * 4.4, -21.6), (1.36, 0.6, 5.6), "rune", uv_scale=6)
        cbox(root, (0, s * 3.0, -21.4), (1.42, 0.4, 3.6), "dark", uv_scale=6)
        # 刃先: 三日月の発光縁
        edge = [(0, s * 6.4, -15.4), (0, s * 7.7, -16.6), (0, s * 8.5, -19.0),
                (0, s * 8.75, -21.4), (0, s * 8.5, -23.8), (0, s * 7.7, -26.2),
                (0, s * 6.4, -27.4)]
        polyline(root, edge, 0.6, 0.9, "edge_hot", uv_scale=6)
        # 刃の付け根の鉤
        beam(root, (0, s * 2.0, -17.6), (0, s * 3.6, -15.6), 0.9, 0.9, "metal_tint",
             uv_scale=8)
        beam(root, (0, s * 2.0, -24.8), (0, s * 3.4, -28.8), 0.8, 0.8, "metal_tint",
             uv_scale=8)
        # 炎の装飾（後ろへ流れる）
        polyline(root, [(0, s * 2.4, -19.0), (0, s * 3.4, -17.0), (0, s * 3.0, -15.2)],
                 0.4, 0.5, "gold", uv_scale=10)
    # 先端の槍穂
    cbox(root, (0, 0, -24.6), (1.6, 1.6, 1.8), "gold", rotation=(0, 0, 45), uv_scale=8)
    polyline(root, [(0, 0, -25.0), (0, 0, -28.0), (0, 0, -31.6)], [1.4, 0.8],
             [1.9, 1.1], "blade", roll=0, uv_scale=6)
    beam(root, (0, 0.9, -25.4), (0, 0, -32.0), 0.4, 0.4, "edge", uv_scale=8)
    beam(root, (0, -0.9, -25.4), (0, 0, -32.0), 0.4, 0.4, "edge", uv_scale=8)


# ===========================================================================
#  ダガー「ノクス」— 影刃（紫）
#  波打つクリス刃、蝙蝠の翼の鍔、三日月の柄頭。逆手で構える。
# ===========================================================================
def build_dagger(m: Model, root):
    # 三日月の柄頭
    pts = arc_points((0, 0, 6.2), 1.8, 200, 340, 5, plane="yz")
    polyline(root, pts, 0.6, 0.7, "silver", uv_scale=12)
    cbox(root, (0, 0, 5.6), (0.9, 0.9, 0.9), "gem", rotation=(45, 0, 0), uv_scale=12)
    cbox(root, (0, 0, 4.9), (1.5, 1.5, 0.6), "silver", uv_scale=12)
    octa(root, (0, 0, 2.4), 1.25, 4.4, "wrap", uv_scale=12)
    cbox(root, (0, 0, 0.3), (1.6, 1.6, 0.5), "silver", uv_scale=12)
    # 蝙蝠の翼の鍔
    cbox(root, (0, 0, -0.5), (1.6, 2.4, 1.0), "dark", uv_scale=10)
    for s in (-1, 1):
        polyline(root, [(0, s * 1.0, -0.4), (0, s * 2.6, 0.2), (0, s * 3.6, 1.4),
                        (0, s * 4.2, 0.6)], [0.7, 0.55, 0.4], [0.8, 0.6, 0.45], "dark",
                 uv_scale=10)
        polyline(root, [(0, s * 2.4, 0.0), (0, s * 2.9, 1.3)], 0.35, 0.35, "edge",
                 uv_scale=12)
        polyline(root, [(0, s * 3.4, 1.0), (0, s * 3.8, 2.2)], 0.3, 0.3, "edge",
                 uv_scale=12)
    cbox(root, (0, 0, -0.5), (1.9, 0.9, 0.9), "gem", rotation=(45, 0, 0), uv_scale=12)
    # 波打つ刃: 左右に振れる 5 節
    n = 6
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((0, 0.55 * math.sin(t * math.pi * 2.5) * (1 - t * 0.6),
                    lerp(-1.0, -11.5, t)))
    widths = [lerp(0.9, 0.5, i / n) for i in range(n)]
    heights = [lerp(2.6, 1.0, i / n) for i in range(n)]
    polyline(root, pts, widths, heights, "blade_tint", uv_scale=10)
    polyline(root, [(p[0], p[1] - h / 2 + 0.1, p[2]) for p, h in zip(pts, heights + [0.6])],
             0.32, 0.36, "edge", uv_scale=12)
    polyline(root, [(p[0], p[1] + h / 2 - 0.1, p[2]) for p, h in zip(pts, heights + [0.6])],
             0.32, 0.36, "edge", uv_scale=12)
    polyline(root, pts[:4], 0.96, 0.35, "energy", uv_scale=12)
    beam(root, pts[-1], (0, 0, -13.4), 0.4, 0.6, "edge_hot", uv_scale=12, extend=0.2)
    # 影の飾り紐
    tassel = m.bone("tassel", (0, -0.6, 6.0), parent="root")
    cbox(tassel, (0, -2.4, 6.2), (0.22, 3.8, 0.7), "cloth", uv_scale=12)
    cbox(tassel, (0, -0.7, 6.2), (0.8, 0.6, 0.8), "silver", uv_scale=12)


# ===========================================================================
#  弓「アストライア」— 聖光弓（金）
#  天使の翼を象ったリカーブ弓。引くと上下のリムが撓み、弦の中央に光の矢が生まれる。
# ===========================================================================
LIMB_PTS = [(0, 2.6, 0.0), (0, 6.0, -1.5), (0, 9.6, -2.6), (0, 13.0, -2.6),
            (0, 15.8, -1.6), (0, 17.6, 0.2), (0, 18.4, 1.6)]
STRING_Z = 1.6
STRING_TIP = 18.2


def build_bow(m: Model, root):
    # ハンドル
    octa(root, (0, 0, 0), 1.5, 4.6, "wrap", axis="y", uv_scale=10)
    for y in (-2.5, 2.5):
        cbox(root, (0, y, 0), (1.9, 0.6, 1.9), "gold", uv_scale=10)
    # ライザー（前面に宝玉、背面に矢受け）
    cbox(root, (0, 0, -1.4), (1.6, 6.8, 1.4), "silver", uv_scale=8)
    cbox(root, (0, 0, -2.1), (1.4, 2.0, 0.6), "gem", uv_scale=12)
    cbox(root, (0, 1.6, -0.6), (2.0, 0.5, 2.0), "gold", uv_scale=10)
    for s in (-1, 1):
        beam(root, (0, s * 3.2, -1.6), (0, s * 1.2, -2.6), 1.0, 0.8, "gold", uv_scale=10)
    # 太陽の光輪（弓の面＝YZ 平面。矢の通り道と弦の側は空けてある）
    for a0, a1 in ((28, 152), (208, 332)):
        polyline(root, arc_points((0, 0, -0.6), 4.4, a0, a1, 6, plane="yz"), 0.7, 0.6,
                 "gold", uv_scale=10)
    for a in list(range(40, 150, 22)) + list(range(220, 330, 22)):
        ra = math.radians(a)
        beam(root, (0, 4.6 * math.sin(ra), -0.6 - 4.6 * math.cos(ra)),
             (0, 6.4 * math.sin(ra), -0.6 - 6.4 * math.cos(ra)), 0.3, 0.6, "edge",
             uv_scale=12)
    # 上下のリム（別ボーン。弦を引くと撓む）
    for name, s in (("limb_u", 1), ("limb_l", -1)):
        b = m.bone(name, (0, s * 2.6, 0), parent="root")
        pts = [(p[0], s * p[1], p[2]) for p in LIMB_PTS]
        polyline(b, pts, [1.6, 1.5, 1.35, 1.2, 1.0, 0.8], [2.0, 1.8, 1.5, 1.2, 1.0, 0.8],
                 "silver", uv_scale=8)
        polyline(b, [(0, p[1], p[2] - 0.75) for p in pts[:-1]], 0.7, 0.6, "gold",
                 uv_scale=10)
        polyline(b, [(0, p[1], p[2] + 0.75) for p in pts[1:-1]], 0.5, 0.4, "energy",
                 uv_scale=10)
        # 天使の翼: 前方・外側へ広がる 6 枚の風切り羽と、根元の雨覆い
        for i in range(6):
            t = 0.12 + i * 0.13
            k = t * (len(pts) - 1)
            a, f = int(k), k - int(k)
            p = [lerp(pts[a][j], pts[a + 1][j], f) for j in range(3)]
            ang = math.radians(18 + i * 13)
            ln = (5.8, 6.6, 6.8, 6.4, 5.6, 4.4)[i]
            tip = (0, p[1] + s * ln * math.sin(ang), p[2] - 0.6 - ln * math.cos(ang))
            beam(b, (0, p[1], p[2] - 0.6), tip, 0.32, 1.25, "ivory", uv_scale=10)
            beam(b, (0, p[1] + s * 0.3, p[2] - 0.9),
                 (0, tip[1] - s * 0.2, tip[2] + 0.3), 0.36, 0.3, "gold", uv_scale=12)
            if i % 2 == 0:
                beam(b, (0, p[1], p[2] - 0.6),
                     (0, p[1] + s * ln * 0.55 * math.sin(ang + 0.3),
                      p[2] - 0.6 - ln * 0.55 * math.cos(ang + 0.3)), 0.4, 1.0, "silver",
                     uv_scale=10)
        # 先端の宝玉と弦掛け
        cbox(b, (0, s * 18.4, 1.6), (0.9, 0.9, 0.9), "gem", rotation=(45, 0, 0),
             uv_scale=12)
        cbox(b, (0, s * 11.4, -2.9), (0.7, 1.0, 0.7), "gem", rotation=(45, 0, 0),
             uv_scale=12)
    # 弦（上下 2 本。引くと中央が後ろへ下がる）
    for name, s in (("str_u", 1), ("str_l", -1)):
        b = m.bone(name, (0, s * STRING_TIP, STRING_Z), parent="root")
        cbox(b, (0, s * STRING_TIP / 2, STRING_Z), (0.18, STRING_TIP, 0.18), "energy",
             uv_scale=12)
    # 光の矢（引いている間だけ見える）
    arrow = m.bone("arrow", (0, 0, STRING_Z), parent="root")
    cbox(arrow, (0, 0, STRING_Z - 8.0), (0.3, 0.3, 16.0), "energy", uv_scale=6)
    beam(arrow, (0, 0, STRING_Z - 15.4), (0, 0, STRING_Z - 18.6), 1.0, 1.0, "edge_hot",
         uv_scale=10, roll=45)
    for s in (-1, 1):
        beam(arrow, (0, 0, STRING_Z - 1.2), (0, s * 1.0, STRING_Z + 0.6), 0.15, 0.5,
             "energy", uv_scale=12)
        beam(arrow, (0, 0, STRING_Z - 1.2), (s * 1.0, 0, STRING_Z + 0.6), 0.5, 0.15,
             "energy", uv_scale=12)


# ===========================================================================
#  盾「グレイシャル・イージス」— 氷晶盾（氷）
#  カイトシールド型。中央に氷晶の核、縁は銀、上端に氷の棘。裏に握りと腕帯。
# ===========================================================================
def build_shield(m: Model, root):
    face = m.bone("face", (0, 0, 0), parent="root")
    # 盾面: 行ごとに幅を変えてカイト形に（上 1.0 → 下で尖る）
    rows = []
    for i in range(12):
        y_top = 9.0 - i * 1.7
        t = i / 11
        w = 14.0 if t < 0.35 else lerp(14.0, 2.2, ((t - 0.35) / 0.65) ** 1.3)
        rows.append((y_top, w))
        cbox(face, (0, y_top - 0.85, -1.6), (w, 1.75, 1.2), "metal_tint", uv_scale=4)
    # 内側の一段盛り上がった面
    for i, (y_top, w) in enumerate(rows[1:-1]):
        cbox(face, (0, y_top - 0.85, -2.3), (max(1.0, w - 2.6), 1.75, 0.4), "crystal",
             uv_scale=4, )
    # 銀の縁
    outline_r = [(r[1] / 2, r[0]) for r in rows] + [(0.4, rows[-1][0] - 1.9)]
    for s in (-1, 1):
        pts = [(s * (x + 0.2), y, -1.9) for x, y in outline_r]
        polyline(face, pts, 0.8, 0.8, "silver", uv_scale=6, overlap=0.4)
    beam(face, (-7.2, 9.1, -1.9), (7.2, 9.1, -1.9), 0.8, 0.8, "silver", uv_scale=6)
    # 上端の氷の棘
    for x, hgt, tilt in ((-6.4, 3.2, 18), (-3.0, 2.0, 6), (3.0, 2.0, -6), (6.4, 3.2, -18)):
        cbox(face, (x, 9.6 + hgt / 2, -1.9), (1.2, hgt, 1.2), "crystal",
             rotation=(0, 0, tilt), uv_scale=8)
    # 翼の紋章（放射状の氷の羽）
    for s in (-1, 1):
        for i, (ang, ln) in enumerate(((15, 5.2), (40, 4.6), (65, 3.6))):
            a = math.radians(ang)
            beam(face, (s * 1.6, 1.0, -2.7),
                 (s * (1.6 + ln * math.cos(a)), 1.0 + ln * math.sin(a), -2.7),
                 0.6, 0.35, "edge", uv_scale=8)
    # 中央の氷晶核（別ボーンで脈動）
    core = m.bone("core", (0, 1.0, -3.2), parent="face")
    cbox(core, (0, 1.0, -3.0), (3.0, 3.0, 1.2), "silver", rotation=(0, 0, 45), uv_scale=8)
    cbox(core, (0, 1.0, -3.6), (2.0, 2.0, 1.2), "gem", rotation=(0, 0, 45), uv_scale=12)
    for a in range(0, 360, 60):
        r = math.radians(a)
        cbox(core, (2.1 * math.cos(r), 1.0 + 2.1 * math.sin(r), -3.1), (0.5, 1.4, 0.5),
             "crystal", rotation=(0, 0, a - 90), uv_scale=10)
    # 下半分の縦の溝（発光）
    cbox(face, (0, -6.0, -2.6), (0.5, 7.0, 0.3), "energy", uv_scale=8)
    # 裏: 握りと腕帯
    cbox(root, (0, 0, 0), (1.2, 4.4, 1.2), "wrap", uv_scale=10)
    for y in (-2.4, 2.4):
        cbox(root, (0, y, -0.6), (1.2, 0.9, 1.6), "metal", uv_scale=10)
    cbox(root, (0, 5.4, -0.6), (5.0, 1.4, 0.5), "cloth", uv_scale=8)


# ===========================================================================
#  鞭「ローゼンケッテ」— 薔薇鞭（薔薇）
#  薔薇の花の柄頭、棘の鍔、14 節の茨の鎖、先端に花弁の刃。各節は親子のボーン。
# ===========================================================================
WHIP_SEGS = 14
WHIP_LEN = 2.3


def build_whip(m: Model, root):
    # 薔薇の柄頭: 花弁を放射状に重ねる
    cbox(root, (0, 0, 6.4), (1.6, 1.6, 1.0), "gem", uv_scale=12)
    for layer, (r, n, ln) in enumerate(((1.0, 5, 1.6), (1.6, 6, 1.8))):
        for i in range(n):
            a = i * 360 / n + layer * 30
            ra = math.radians(a)
            cbox(root, (r * math.cos(ra), r * math.sin(ra), 6.0 - layer * 0.4),
                 (0.5, ln, 1.2), "crystal" if layer == 0 else "metal_tint",
                 rotation=(0, 0, a - 90), uv_scale=10)
    octa(root, (0, 0, 2.8), 1.4, 5.0, "wrap", uv_scale=10)
    for z in (0.3, 5.3):
        cbox(root, (0, 0, z), (1.8, 1.8, 0.5), "gold", uv_scale=10)
    # 棘の鍔
    cbox(root, (0, 0, -0.3), (2.2, 2.2, 0.8), "dark", uv_scale=10)
    for a in range(0, 360, 45):
        ra = math.radians(a)
        beam(root, (1.0 * math.cos(ra), 1.0 * math.sin(ra), -0.3),
             (2.3 * math.cos(ra), 2.3 * math.sin(ra), 0.6), 0.4, 0.4, "edge",
             uv_scale=12)
    # 鎖: seg0 は柄先 (z=-0.8) に、以降は前の節の先端に繋がる
    parent = "root"
    z = -0.8
    for i in range(WHIP_SEGS):
        name = f"seg{i}"
        b = m.bone(name, (0, 0, z), parent=parent)
        thick = lerp(0.9, 0.45, i / WHIP_SEGS)
        cbox(b, (0, 0, z - WHIP_LEN / 2), (thick, thick, WHIP_LEN + 0.1), "dark",
             uv_scale=10)
        cbox(b, (0, 0, z - WHIP_LEN / 2), (thick * 0.7, thick * 1.25, WHIP_LEN * 0.6),
             "rune", rotation=(0, 0, 45), uv_scale=10)
        # 棘（交互に上下・左右）
        a = (i * 90) % 360
        ra = math.radians(a)
        beam(b, (0, 0, z - WHIP_LEN * 0.5),
             (0.9 * math.cos(ra), 0.9 * math.sin(ra), z - WHIP_LEN * 0.15), 0.25, 0.25,
             "edge", uv_scale=12)
        parent = name
        z -= WHIP_LEN
    # 先端の花弁の刃
    tip = m.bone("tip", (0, 0, z), parent=parent)
    for a in (0, 120, 240):
        ra = math.radians(a)
        beam(tip, (0, 0, z), (0.9 * math.cos(ra), 0.9 * math.sin(ra), z - 2.6), 0.5, 0.9,
             "crystal", uv_scale=12, roll=a)
    beam(tip, (0, 0, z), (0, 0, z - 3.6), 0.5, 0.5, "edge_hot", uv_scale=12, roll=45)


# ===========================================================================
#  両手かぎ爪「ベヒモス」— 獣王爪（琥珀）
#  拳を覆う篭手から、下へ反る 3 本の爪。手首に獣毛、甲に牙の飾りと琥珀の核。
# ===========================================================================
def _claw(m, b, out=-1.0):
    """篭手は前腕の軸（+Y）に沿う。爪は拳の先（-Y）から伸び、先端が前（-Z）へ反る。
    out は手の甲（外側）の向き。右手は -X、左手は +X。"""
    zc = -1.0                                   # 腕の中心（rightItem の軸より少し前）
    # 篭手の殻と、重ねた装甲板
    cbox(b, (0, 0.6, zc), (4.8, 7.2, 4.8), "metal_tint", uv_scale=6)
    for i in range(3):
        cbox(b, (out * 2.5, 2.4 - i * 2.0, zc), (0.5, 1.7, 4.2 - i * 0.3), "metal",
             rotation=(0, 0, out * -8), uv_scale=8)
    cbox(b, (0, -0.2, zc - 2.5), (3.8, 4.6, 0.4), "metal", uv_scale=8)
    cbox(b, (0, -0.2, zc + 2.5), (3.8, 4.6, 0.4), "metal", uv_scale=8)
    # 発光する琥珀の脈
    for dz in (-1.2, 1.2):
        cbox(b, (out * 2.43, 0.6, zc + dz), (0.12, 5.6, 0.35), "energy", uv_scale=10)
    # 甲の琥珀核と、それを囲む金の爪留め
    cbox(b, (out * 2.6, 0.2, zc), (0.9, 1.8, 1.8), "gem", rotation=(45, 0, 0),
         uv_scale=12)
    cbox(b, (out * 2.55, 0.2, zc), (0.5, 2.6, 2.6), "gold", rotation=(45, 0, 0),
         uv_scale=10)
    # 牙の飾り（外側、上向き）
    for dz in (-1.5, 1.5):
        beam(b, (out * 2.6, 2.6, zc + dz), (out * 3.6, 4.8, zc + dz * 1.3), 0.6, 0.6,
             "ivory", uv_scale=12)
    # 拳の先の金具（爪の根元）
    cbox(b, (0, -3.4, zc), (5.2, 1.4, 5.4), "gold", uv_scale=8)
    cbox(b, (0, -3.0, zc), (5.4, 0.5, 5.6), "dark", uv_scale=8)
    # 3 本の爪: 指の付け根の列（Z 方向）から生える
    for i, dz in enumerate((-1.75, 0.0, 1.75)):
        ln = 13.5 if i == 1 else 12.0
        pts = []
        for k in range(7):
            t = k / 6
            pts.append((out * 0.3 * t, -3.8 - ln * t, zc + dz * (1 - 0.25 * t) - 3.6 * t ** 2.1))
        polyline(b, pts, [0.8, 0.72, 0.64, 0.55, 0.45, 0.32],
                 [1.5, 1.35, 1.2, 1.0, 0.8, 0.55], "blade_tint", uv_scale=10)
        # 前縁（-Z 側）が発光する刃
        edge = [(p[0], p[1], p[2] - lerp(0.75, 0.3, k / 6)) for k, p in enumerate(pts)]
        polyline(b, edge, 0.36, 0.3, "edge_hot", uv_scale=12)
        cbox(b, (0, -4.2, zc + dz), (1.2, 1.0, 1.4), "metal", uv_scale=10)
    # 手首の獣毛（放射状の房）
    for k in range(10):
        a = k * 36
        ra = math.radians(a)
        x, z = 2.6 * math.cos(ra), zc + 2.6 * math.sin(ra)
        cbox(b, (x, 4.6, z), (1.4, 1.8, 1.0), "fur", rotation=(0, -a, 18), uv_scale=8)
    cbox(b, (0, 4.2, zc), (5.0, 0.6, 5.0), "gold", uv_scale=8)


def build_claws(m: Model, root):
    _claw(m, root, -1.0)
    left = m.bone("left", (0, 0, 0), binding=BIND_OFF)
    _claw(m, left, 1.0)


BUILDERS = {
    "greatsword": build_greatsword,
    "twinblades": build_twinblades,
    "greataxe": build_greataxe,
    "dagger": build_dagger,
    "bow": build_bow,
    "shield": build_shield,
    "whip": build_whip,
    "claws": build_claws,
}

STYLE_OVERRIDES = {
    "greatsword": {},
    "twinblades": {"wrap": {"base": (20, 40, 32)}},
    "greataxe": {"edge": {"sat": 0.6}, "edge_hot": {"sat": 0.85},
                 "blade_flat": {"base": (120, 104, 108), "light": (200, 176, 170),
                                "dark": (70, 52, 56), "glint_period": 9},
                 "metal": {"base": (58, 44, 44), "light": (124, 96, 90),
                           "dark": (30, 22, 22)},
                 "wrap": {"base": (40, 14, 12)}},
    "dagger": {"blade_tint": {"base": (88, 72, 118), "light": (196, 170, 236),
                              "dark": (40, 28, 62)},
               "wrap": {"base": (16, 12, 24)}},
    "bow": {"silver": {"base": (232, 230, 222), "light": (255, 255, 250),
                       "dark": (176, 168, 150)},
            "wrap": {"base": (110, 70, 30), "strap": (240, 214, 140)}},
    "shield": {"metal_tint": {"base": (70, 104, 140), "light": (150, 200, 230),
                              "dark": (30, 52, 80)}},
    "whip": {"edge": {"sat": 0.45}, "edge_hot": {"sat": 0.55}, "dark": {"base": (40, 16, 30)}, "metal_tint": {"base": (120, 30, 70),
                                                         "light": (220, 90, 150)},
             "crystal": {"base": (255, 120, 190)}},
    "claws": {"edge_hot": {"sat": 0.7},
              "blade_tint": {"base": (96, 84, 80), "light": (196, 170, 140),
                             "dark": (44, 34, 32), "line": (20, 14, 12)}},
}


def build_model(name: str) -> Model:
    m = Model(f"geometry.{NS}.{name}", uv_scale=4, visible_bounds=(5, 5),
              vb_offset=(0, 0.5, 0), max_atlas=(1024, 1024))
    root = m.bone("root", (0, 0, 0), binding=BIND_MAIN)
    BUILDERS[name](m, root)
    m.pack()
    return m


# アイコンの撮り方: (yaw, pitch, 画面上の回転)。刃が右上を向く斜めの構図
ICON_VIEW = {
    "greatsword": (90, 0, 45), "twinblades": (90, 0, 45), "greataxe": (90, 0, 45),
    "dagger": (90, 0, 45), "bow": (90, 0, -35), "shield": (0, -8, 0),
    "whip": (90, 0, 20), "claws": (90, 0, -30),
}
# 鞭はアイコンでは輪に巻いた姿にする
ICON_POSE = {"whip": {f"seg{i}": {"rotation": [22 if i else 40, 0, 0],
                                  "position": [0, 0, 0]} for i in range(14)}}


def make_icon(name, geo, tex):
    from PIL import Image, ImageFilter
    from hd_preview import render
    yaw, pitch, turn = ICON_VIEW[name]
    hide = ("fp_left", "left", "arrow")
    big = render(geo, tex, 256, yaw, pitch, 0, margin=0.02, bg=(0, 0, 0, 0), ss=2,
                 hide=hide, pose=ICON_POSE.get(name))
    big = big.rotate(turn, resample=Image.BICUBIC, expand=True)
    big = big.crop(big.getbbox())
    side = max(big.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(big, ((side - big.size[0]) // 2, (side - big.size[1]) // 2))
    im = sq.resize((30, 30), Image.LANCZOS)
    canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    canvas.alpha_composite(im, (1, 1))
    a = canvas.split()[3].point(lambda v: 255 if v > 90 else 0)
    canvas.putalpha(a)
    ring = Image.new("RGBA", canvas.size, (14, 12, 20, 255))
    ring.putalpha(a.filter(ImageFilter.MaxFilter(3)))
    ring.alpha_composite(canvas)
    ring.save(os.path.join(ICON_DIR, f"{name}.png"))


def main() -> None:
    from hd_preview import render, sheet
    for d in (GEO_DIR, TEX_DIR, ATT_DIR, ICON_DIR):
        os.makedirs(d, exist_ok=True)
    only = sys.argv[1:]
    tiles = []
    for i, name in enumerate(BUILDERS):
        if only and name not in only:
            continue
        m = build_model(name)
        geo = os.path.join(GEO_DIR, f"hd_{name}.geo.json")
        tex = os.path.join(TEX_DIR, f"{name}.png")
        m.write(geo)
        st = styles_for(WEAPONS[name][2], **STYLE_OVERRIDES.get(name, {}))
        p = HDPainter(m.tex_w, m.tex_h, 300 + i)
        p.paint_model(m, st)
        p.save(tex)
        make_icon(name, geo, tex)
        print(f"  {name:11s} {len(m.bones):3d} bones {len(m.all_cubes()):4d} cubes "
              f"{m.tex_w}x{m.tex_h}")
        if os.environ.get("HD_PREVIEW"):
            for yaw, pitch in ((90, -6), (35, -22), (160, -12), (0, -86)):
                tiles.append(render(geo, tex, 300, yaw, pitch, ss=2,
                                    hide=("fp_left",)))
    if tiles:
        sheet(tiles, os.path.join(SCRATCH, "weapons.png"))


if __name__ == "__main__":
    main()
