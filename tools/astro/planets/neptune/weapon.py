# -*- coding: utf-8 -*-
"""海王星（トリトン）のナノウェポン「深淵三叉槍 トリトン」と星核「海王星核 ネプチューン・コア」。

武器空間: 握りの中心 = 原点、穂先 = -Z、三本の穂先は ±Y に開く（刃の平の法線 = ±X）。16 単位 = 1 ブロック。
手に持つと 0.88 倍（astro_hold.SPEC["trident"]）。握りの前後 ±3.4 は篭手に隠れる。
全長（穂先 z -33.6 〜 石突き z +17.6）と握りの位置は v1.0 のまま（body.py の全身モーションが前提にしている）。

v1.1（7 頭身のスーツに合わせた細部）:
  form_0_grip    柄巻と三本の指当ての輪・リベット留めの真珠の口金・水色の光の輪
  form_1_shaft   柄（握りから両側へ伸びる）。藍の地を螺旋に巡る水色の「波の刻み」（細い光の節の螺旋）、
                 鋲を打った真珠の節、穂の側の節の間に膜の張った白い小ビレ
  form_2_butt    石突き: 暗い受け輪・真珠の冠（鋲）・光の輪・藍の台・宝玉・尖り（先に光）・膜の張った尾ビレ
  form_2_socket  穂の付け根: 真珠の襟と光の輪・藍の八角の台・鰓の板（スリット）・暗斑の海王星（fx_spin_globe）・
                 真珠の縁の輪・横木（鋲・光の溝）・両端の発振器・波頭の白い鍔（膜の張ったヒレ + 真珠の巻き）
                 └ fx_spin_vortex  付け根の後ろで逆向きに回る嵐の羽根（大暗斑の渦）
                 └ fx_spin_moon    付け根の下の傾いた軌道を逆行する小さな衛星トリトン
  form_3_prongs  三本の穂先（中央は長く、左右は外へ張って先が返る）: 根元の真珠の襟・中央の光の溝・
                 二段の返し・返しの付いた鏃と水色の刃・穂先の小さな発光・左右の穂の内側の光の縁

細かい部品の作り方は planets/earth/weapon.py と同じ（鋲は板を X 方向に貫く細い箱、彫りの溝は暗い帯 + 光の芯）。
"""
from __future__ import annotations

import math

import astro_weapon as W
from astro_common import mat_cube, taper
from astro_paint import core_styles, mix, weapon_styles

from .suit import AQUA, FIN, FOAM, INDIGO, PEARL, ray_fin

KIND = "trident"

Z_SOCK0 = -16.6         # 穂の付け根（台の後ろ）
Z_BAR = -20.6           # 横木
Z_TIP = -33.6           # 中央の穂先の先端
Z_BUTT = 15.0           # 石突きの端
EDGE = (96, 236, 255)   # 水色の刃
LEAD = ["pearl", "fin", "fin"]


def helix(bone, z0, z1, r, turns, n, w, style, phase=0.0, **kw):
    """柄を螺旋に巡る細い帯（z0 → z1 を n 節、turns 回り、半径 r）。彫った波の刻みの光に。"""
    pts = []
    for i in range(n + 1):
        t = i / n
        a = math.radians(phase + 360.0 * turns * t)
        pts.append((math.cos(a) * r, math.sin(a) * r, z0 + (z1 - z0) * t))
    return W.polyline(bone, pts, w, w, style, overlap=0.08, **kw)


def studs(bone, z, r, n, style="rivet", size=0.24, phase=45.0, **kw):
    """柄の輪の周りに n 個の鋲（半径 r、z の位置）。"""
    out = []
    for i in range(n):
        a = math.radians(phase + 360.0 * i / n)
        out.append(W.cbox(bone, (math.cos(a) * r, math.sin(a) * r, z), (size, size, size), style,
                          **kw))
    return out


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄巻（篭手に隠れる）・指当ての輪・口金
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0), 1.55, 6.8, "wrap", uv_scale=8)
    for z in (-3.6, 3.6):
        W.octa(grip, (0, 0, z), 2.0, 0.8, "pearl", uv_scale=8)
        W.octa(grip, (0, 0, z + (0.55 if z > 0 else -0.55)), 1.7, 0.3, "glow", uv_scale=10)
        studs(grip, z, 0.98, 4, uv_scale=12)

    # =====================================================================
    #  form_1_shaft — 柄（螺旋に巡る波の刻みの光・鋲の節・白い小ビレ）
    # =====================================================================
    shaft = W.form(m, root, 1, "shaft", (0, 0, 0))
    W.octa(shaft, (0, 0, -10.2), 1.25, 12.4, "shaft", uv_scale=6)          # 穂の側
    W.octa(shaft, (0, 0, 8.7), 1.25, 9.4, "shaft", uv_scale=6)             # 石突きの側
    helix(shaft, -4.4, -15.6, 0.6, 2.0, 11, 0.2, "glow", uv_scale=12)
    helix(shaft, 4.4, 12.8, 0.6, 1.5, 8, 0.2, "glow", phase=180.0, uv_scale=12)
    for z, w in ((-8.6, 1.7), (-14.0, 1.75), (8.6, 1.7)):                    # 真珠の節
        W.octa(shaft, (0, 0, z), w, 0.55, "pearl", uv_scale=10)
        W.octa(shaft, (0, 0, z + 0.42), w - 0.2, 0.22, "plate2_b", uv_scale=12)
        if z < 0:
            studs(shaft, z, w / 2 + 0.02, 4, phase=0.0, size=0.22, uv_scale=12)
    # 穂の側の節の間の小ビレ（±Y。白い条と淡い膜）
    for s in (-1, 1):
        ray_fin(shaft, [(0, s * 0.62, -10.9), (0, s * 0.62, -13.2)],
                [(0, s * 1.55, -12.3), (0, s * 1.7, -13.3), (0, s * 1.15, -13.9)], 0.3, LEAD,
                seg=1.3, w0=0.4, w1=0.3, web="fin_web", web_seg=2.0, web_t=0.8,
                normal=(1, 0, 0), uv_scale=10)

    # =====================================================================
    #  form_2_butt — 石突き
    # =====================================================================
    butt = W.form(m, root, 2, "butt", (0, 0, 13.4))
    W.octa(butt, (0, 0, 13.05), 2.1, 0.3, "dark", uv_scale=10)
    W.octa(butt, (0, 0, 13.6), 1.9, 1.0, "pearl", uv_scale=8)
    studs(butt, 13.6, 0.98, 4, uv_scale=12)
    W.octa(butt, (0, 0, 14.15), 1.72, 0.24, "glow", uv_scale=12)
    W.octa(butt, (0, 0, 14.75), 1.55, 1.1, "plate2", uv_scale=8)
    W.cbox(butt, (0, 0, 15.5), (1.0, 1.0, 0.8), "gem", rotation=(0, 0, 45), uv_scale=12)
    taper(butt, (0, 0, 15.6), (0, 0, 17.6), 0.9, 0.2, 2, "pearl", round_=False, uv_scale=10)
    W.cbox(butt, (0, 0, 17.0), (0.36, 0.36, 0.5), "glow", rotation=(0, 0, 45), uv_scale=12)
    for s in (-1, 1):                                                        # 尾ビレ（±Y）
        ray_fin(butt, [(0, s * 0.6, 13.3), (0, s * 0.6, 15.1)],
                [(0, s * 2.5, 16.0), (0, s * 2.15, 16.95), (0, s * 1.35, 17.45)], 0.32, LEAD,
                seg=1.4, w0=0.42, w1=0.3, web="fin_web", web_seg=2.0, web_t=0.82,
                normal=(1, 0, 0), uv_scale=10)

    # =====================================================================
    #  form_2_socket — 穂の付け根: 襟・台・鰓の板・海王星・横木・発振器・波頭の鍔・渦・衛星
    # =====================================================================
    sock = W.form(m, root, 2, "socket", (0, 0, Z_SOCK0))
    W.octa(sock, (0, 0, -16.9), 2.0, 0.6, "pearl", uv_scale=8)
    W.octa(sock, (0, 0, -16.45), 1.6, 0.24, "glow", uv_scale=12)
    studs(sock, -16.9, 1.02, 4, uv_scale=12)
    W.bevel(sock, (0, 0, -18.6), (2.0, 3.0, 2.8), "plate2", cut=0.6, axis="x",
            edge_style="plate2_b", uv_scale=8)
    for s in (-1, 1):                                                        # 鰓の板（±Y）
        gp = W.cbox(sock, (0, s * 1.62, -18.6), (1.5, 0.3, 2.2), "plate", uv_scale=10)
        _ = gp
        for z in (-18.05, -18.6, -19.15):
            W.cbox(sock, (0, s * 1.8, z), (1.1, 0.16, 0.2), "vent", uv_scale=14)
    globe = W.spin(m, sock, "globe", (0, 0, -18.6))
    W.sphere(globe, (0, 0, -18.6), 1.3, "globe", uv_scale=14)
    for s in (-1, 1):                                                        # 球の真珠の縁（両面）
        W.ring(sock, (s * 1.02, 0, -18.6), 1.5, 8, (0, 0.3, 0.26), "pearl", axis="x",
               uv_scale=10)
    # 横木（三本の穂の根元を受ける）: 藍の梁 + 暗い溝と光の芯 + 鋲 + 真珠の端 + 両端の発振器
    W.cbox(sock, (0, 0, Z_BAR), (1.1, 6.4, 1.2), "plate2", uv_scale=8)
    W.cbox(sock, (0, 0, Z_BAR - 0.05), (1.16, 5.4, 0.42), "dark", uv_scale=10)
    W.cbox(sock, (0, 0, Z_BAR - 0.08), (1.24, 5.0, 0.2), "glow", uv_scale=12)
    for y in (-2.1, -1.2, 1.2, 2.1):
        W.cbox(sock, (0, y, Z_BAR + 0.42), (1.22, 0.22, 0.22), "rivet", uv_scale=14)
    for s in (-1, 1):
        W.cbox(sock, (0, s * 3.2, Z_BAR), (1.3, 1.0, 1.5), "pearl", uv_scale=10)
        W.octa(sock, (0, s * 3.82, Z_BAR), 0.9, 0.3, "dark", axis="y", uv_scale=12)
        W.octa(sock, (0, s * 4.0, Z_BAR), 0.5, 0.2, "glow", axis="y", uv_scale=14)
        # 波頭の鍔: 横木の端から外後ろへ張り、先が内へ巻き込む（砕ける波の形）
        ray_fin(sock, [(0, s * 3.4, Z_BAR + 0.5), (0, s * 1.5, Z_BAR + 1.7)],
                [(0, s * 5.5, -16.6), (0, s * 4.5, -15.3), (0, s * 2.9, -15.4)], 0.42,
                ["fin", "fin_m", "fin"], seg=2.6, w0=0.7, w1=0.5, web="fin_web",
                web_seg=3.4, web_t=0.86, normal=(1, 0, 0), uv_scale=8)
        W.polyline(sock, [(0, s * 3.4, Z_BAR + 0.2), (0, s * 5.0, -17.8), (0, s * 5.7, -16.2),
                          (0, s * 5.2, -15.0), (0, s * 4.3, -14.9)],
                   [0.7, 0.62, 0.55, 0.45], [0.62, 0.55, 0.5, 0.4], "pearl", uv_scale=10)
        W.cbox(sock, (0, s * 4.75, -17.1), (0.62, 0.3, 1.5), "glow", rotation=(s * 30, 0, 0),
               uv_scale=12)
        W.cbox(sock, (0, s * 5.66, -16.25), (0.6, 0.26, 0.26), "rivet", uv_scale=14)
    # 嵐の羽根（付け根の後ろで逆向きに回る大暗斑の渦。柄を巻く 6 枚の曲がった羽根）
    vx = W.spin(m, sock, "vortex", (0, 0, -15.3))
    for i in range(6):
        a = math.radians(i * 60)
        pts = [(math.cos(a + dt) * r, math.sin(a + dt) * r, -15.3) for r, dt in
               ((0.82, 0.0), (1.12, 0.35), (1.36, 0.8))]
        W.polyline(vx, pts, [0.24, 0.2], [0.22, 0.2], "glow" if i % 2 == 0 else "pearl",
                   overlap=0.1, uv_scale=12)
    # 衛星トリトン: 付け根の下の傾いた軌道を逆向きに回る（WEAPON_ANIMS）
    orbit = W.part(m, sock, "orbit", (0, 0, -12.6), rotation=(0, 18, 0))
    W.ring(orbit, (0, 0, -12.6), 2.7, 10, (0, 0.14, 0.16), "glow_soft", axis="z", uv_scale=10)
    moon = W.spin(m, orbit, "moon", (0, 0, -12.6))
    W.sphere(moon, (0, 2.7, -12.6), 0.8, "triton", uv_scale=14)
    W.cbox(moon, (0, 2.7, -11.75), (0.3, 0.3, 0.3), "glow", uv_scale=14)     # 衛星の目

    # =====================================================================
    #  form_3_prongs — 三本の穂先（台から -Z へ伸びる）
    # =====================================================================
    pr = W.form(m, root, 3, "prongs", (0, 0, Z_BAR))
    # 根元の真珠の襟（三本とも）
    W.octa(pr, (0, 0, Z_BAR - 0.75), 1.9, 0.4, "pearl", uv_scale=10)
    for s in (-1, 1):
        W.octa(pr, (0, s * 3.32, Z_BAR - 0.62), 1.4, 0.36, "pearl", uv_scale=10)
    # 中央の穂: 真珠の芯・暗い溝と光の芯（X 方向に貫く）・水色の刃・二段の返し・返しの付いた大きな鏃
    taper(pr, (0, 0, Z_BAR - 0.5), (0, 0, -28.6), 1.5, 1.0, 3, "prong", round_=False,
          uv_scale=8)
    W.beam(pr, (0, 0, -21.6), (0, 0, -28.0), 1.62, 0.36, "dark", uv_scale=10)
    W.beam(pr, (0, 0, -21.8), (0, 0, -27.8), 1.72, 0.18, "glow", uv_scale=12)
    for s in (-1, 1):
        W.beam(pr, (0, s * 0.72, Z_BAR - 0.8), (0, s * 0.5, -28.4), 0.56, 0.3, "edge",
               uv_scale=8)
        for z in (-23.6, -25.8):                                             # 二段の小さな返し
            W.beam(pr, (0, s * 0.62, z), (0, s * 1.15, z + 0.8), 0.42, 0.3, "prong",
                   uv_scale=12)
    for z in (-22.6, -27.0):                                                 # 鋲（X に貫く）
        W.cbox(pr, (0, 0, z), (1.66, 0.24, 0.24), "rivet", uv_scale=14)
    arrowhead(pr, 0.0, -28.6, 1.65, Z_TIP, 0.8)
    W.cbox(pr, (0, 0, -32.2), (0.96, 0.3, 0.6), "glow", uv_scale=14)       # 穂先の発光
    # 左右の穂: 外へ張ってから前へ。内側の光の縁・先に鏃と外向きの返し・発光
    for s in (-1, 1):
        pts = [(0, s * 3.2, Z_BAR - 0.4), (0, s * 4.2, -23.4), (0, s * 4.15, -26.0),
               (0, s * 3.8, -27.2)]
        W.polyline(pr, pts, [1.1, 1.0, 0.9], [1.1, 1.0, 0.9], "prong", uv_scale=8)
        W.polyline(pr, [(0, s * 4.8, -23.0), (0, s * 4.75, -26.0)], 0.62, 0.34, "edge",
                   uv_scale=8)
        W.polyline(pr, [(0, s * 3.55, -22.0), (0, s * 3.62, -23.6), (0, s * 3.58, -25.8)], 1.18,
                   0.2, "glow", overlap=0.1, uv_scale=12)
        W.cbox(pr, (0, s * 4.12, -24.6), (1.14, 0.24, 0.24), "rivet", uv_scale=14)
        arrowhead(pr, s * 3.75, -27.0, 1.25, -30.8, 0.72)
        W.cbox(pr, (0, s * 3.75, -29.7), (0.86, 0.26, 0.5), "glow", uv_scale=14)
        W.beam(pr, (0, s * 4.6, -26.4), (0, s * 5.5, -25.2), 0.55, 0.5, "prong", uv_scale=10)
        W.beam(pr, (0, s * 5.45, -25.25), (0, s * 5.6, -24.4), 0.45, 0.42, "edge", uv_scale=10)


def arrowhead(bone, y0, z_base, half_w, z_tip, thick):
    """返しの付いた鏃（YZ 平面）: 真珠の三角・水色に光る両刃・後ろへ返る二本の返し。"""
    W.blade_point(bone, z_base, half_w, z_tip, thick, "prong_flat", layer=0.85, y0=y0, uv_scale=8)
    for s in (-1, 1):
        W.beam(bone, (0, y0 + s * (half_w + 0.15), z_base + 0.1), (0, y0 + s * 0.1, z_tip - 0.2),
               thick + 0.12, 0.34, "edge", uv_scale=8, extend=0.2)
        W.beam(bone, (0, y0 + s * half_w, z_base + 0.2), (0, y0 + s * (half_w - 0.45), z_base + 1.7),
               thick * 0.9, 0.5, "prong", uv_scale=10)
    W.cbox(bone, (0, y0, z_base - 1.0), (thick + 0.16, 0.4, 1.6), "edge", uv_scale=12)


def build_core(m, root):
    """海王星核: 暗斑の海王星を、真珠の籠（鋲を打った縦の輪と極の冠）・傾いた淡い環・
    逆向きに回る小さな衛星トリトンが囲む。直径 6.4。"""
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    spin = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(spin, (0, 0, 0), 1.8, "globe", uv_scale=16)
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    W.ring(cage, (0, 0, 0), 3.0, 14, (0, 0.45, 0.6), "plate2", axis="z", uv_scale=8,
           styles=["plate2", "plate2", "pearl"])
    for i in range(7):                                                       # 輪の鋲
        a = math.radians(360.0 * (i + 0.5) / 7)
        W.cbox(cage, (-math.sin(a) * 3.0, math.cos(a) * 3.0, -0.38), (0.24, 0.24, 0.2), "rivet",
               uv_scale=14)
    for s in (-1, 1):
        y = s * 3.15
        W.octa(cage, (0, y, 0), 1.5, 0.8, "pearl", axis="y", uv_scale=10)
        W.octa(cage, (0, y + s * 0.5, 0), 0.9, 0.4, "glow", axis="y", uv_scale=12)
        W.cbox(cage, (s * 3.05, 0, 0), (0.8, 1.0, 1.0), "pearl", uv_scale=10)
        W.cbox(cage, (s * 3.35, 0, 0), (0.3, 0.6, 0.6), "glow", uv_scale=12)
        W.cbox(cage, (s * 3.05, 0, -0.56), (0.24, 0.24, 0.16), "rivet", uv_scale=14)
    # 北極の三叉の冠（真ん中の穂に光）
    taper(cage, (0, 3.6, 0), (0, 5.0, 0), 0.5, 0.15, 1, "pearl", round_=False, uv_scale=12)
    W.cbox(cage, (0, 4.5, -0.2), (0.18, 0.5, 0.16), "glow", uv_scale=14)
    for s in (-1, 1):
        W.polyline(cage, [(0, 3.6, s * 0.4), (0, 4.2, s * 0.85), (0, 4.7, s * 0.7)], 0.3, 0.3,
                   "pearl", uv_scale=12)
    # 南極の小さな尾ビレ（白）
    for s in (-1, 1):
        W.beam(cage, (0, -3.6, s * 0.2), (0, -4.4, s * 0.75), 0.3, 0.42, "fin", uv_scale=12)
    # 海王星の淡い環（傾いて回る）
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    rg = W.spin(m, rings, "ring", (0, 0, 0), rotation=(-22, 0, 8))
    W.ring(rg, (0, 0, 0), 2.45, 12, (0, 0.28, 0.32), "ring_dark", axis="y",
           styles=["ring_dark", "glow_soft", "ring_dark"], uv_scale=10)
    # 衛星トリトン（逆行。傾いた軌道）
    tr = W.spin(m, rings, "triton", (0, 0, 0), rotation=(-30, 0, 20))
    W.sphere(tr, (-2.2, 0, -2.3), 0.5, "triton", uv_scale=14)


# ---------------------------------------------------------------------------
#  塗り
# ---------------------------------------------------------------------------
def _common(key):
    return dict(
        pearl={"kind": "trim", "base": PEARL, "light": (255, 255, 255), "dark": (96, 132, 176),
               "line": (36, 52, 96)},
        gold={"kind": "trim", "base": PEARL, "light": (255, 255, 255), "dark": (96, 132, 176),
              "line": (36, 52, 96)},
        rivet={"kind": "trim", "base": (214, 232, 246), "light": (255, 255, 255),
               "dark": (110, 140, 184), "line": (30, 44, 86), "bevel": False},
        plate2={"base": INDIGO, "light": (92, 116, 218), "dark": (18, 24, 86),
                "line": (8, 10, 44), "panel": 0},
        plate2_b={"base": (26, 34, 112), "light": (70, 88, 180), "dark": (14, 18, 64),
                  "line": (6, 8, 32), "panel": 0},
        plate={"base": (36, 92, 214), "light": (120, 170, 245), "dark": (18, 52, 140),
               "line": (10, 30, 92), "panel": 0},
        dark={"base": (14, 18, 44), "line": (4, 6, 16)},
        vent={"kind": "vent", "base": (22, 28, 60), "glow": AQUA, "deep": (8, 40, 110)},
        glow={"glow": AQUA, "light": (220, 252, 255)},
        glow_soft={"glow": AQUA, "light": (220, 252, 255)},
        gem={"glow": (90, 240, 255), "deep": (10, 40, 120)},
        fin={"kind": "armor", "base": FOAM, "light": (255, 255, 255), "dark": (176, 204, 238),
             "line": (120, 160, 220), "panel": 0, "bolts": False, "outline_k": 0.35,
             "bevel_lo": 0.92, "unlit": True},
        fin_m={"kind": "armor", "base": (190, 222, 250), "light": (236, 248, 255),
               "dark": (140, 186, 236), "line": (110, 150, 214), "panel": 0, "bolts": False,
               "sheen": False, "outline_k": 0.3, "bevel_lo": 0.92, "unlit": True},
        fin_web={"kind": "armor", "base": (150, 196, 242), "light": (214, 238, 255),
                 "dark": (96, 146, 214), "line": (70, 112, 186), "panel": 0, "bolts": False,
                 "sheen": False, "outline_k": 0.25, "bevel_lo": 0.94, "unlit": True},
        globe=W.globe_style("neptune", emit=34, spin=-180),   # 大暗斑がアイコンの正面に来る経度
        triton=W.globe_style("luna", emit=255, halo=(255, 214, 228)),
    )


def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        **_common(key),
        # 柄: 藍の地に、斜めに巡る水色の波の刻み（発光の筋）
        shaft={"kind": "armor", "base": INDIGO, "light": (92, 116, 218), "dark": (18, 24, 86),
               "line": (8, 10, 44), "panel": 0, "bolts": False,
               "stripe": {"dir": "d", "period": 16, "width": 1, "color": AQUA, "glow": True,
                          "emit": 50}},
        # 穂: 真珠の鋼（鏡面）
        prong={"kind": "chrome", "base": (214, 234, 250), "light": (255, 255, 255),
               "line": (34, 52, 96)},
        edge={"glow": EDGE, "sat": 0.45, "emit": 30},
        prong_flat={"kind": "blade", "base": (200, 224, 244), "light": (250, 254, 255),
                    "dark": (130, 156, 196), "outline": False, "bevel": False, "fuller": False,
                    "hamon_off": True, "glint_period": 9999, "hi": 0.0, "lo": 1.1},
        wrap={"base": (14, 20, 48), "strap": (40, 120, 220), "skin": (200, 230, 246)},
        energy={"glow": mix(EDGE, (255, 255, 255), 0.3)},
    )


def CORE_STYLES(key):
    return core_styles(
        key, **_common(key),
        ring_dark={"kind": "armor", "base": (40, 70, 150), "light": (110, 150, 230),
                   "dark": (20, 34, 90), "line": (10, 16, 50), "panel": 0, "bolts": False},
    )


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）
#    v.astro_sw 攻撃の振り 0→1 / v.astro_fp 一人称で 1 / v.astro_usew 右クリック中 0→1
#    待機ループの長さは速さから自動（60・120・180°/秒 → 6 秒）
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        # トリトンは海王星の自転と逆向きに回る（逆行衛星）。大暗斑の渦も逆向き
        "fx_spin_moon": {"rotation": [0, 0, "-q.anim_time * 120.0"]},
        "fx_spin_globe": {"rotation": [0, 0, "q.anim_time * 60.0"]},
        "fx_spin_vortex": {"rotation": [0, 0, "-q.anim_time * 180.0"]},
    },
    "swing": {
        "fx_spin_moon": {"rotation": [0, 0, "-v.astro_sw * 360.0"]},
        "fx_spin_vortex": {"rotation": [0, 0, "-v.astro_sw * 720.0"]},
    },
    "form_axes": {"form_1_shaft": "z", "form_3_prongs": "z"},
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": {"rotation": [0, "q.anim_time * 45.0", 0]},
        "fx_spin_ring": {"rotation": [0, "q.anim_time * 60.0", 0]},
        "fx_spin_triton": {"rotation": [0, "-q.anim_time * 150.0", 0]},
    },
}
