# -*- coding: utf-8 -*-
"""海王星（トリトン）のナノウェポン「深淵三叉槍 トリトン」と星核「海王星核 ネプチューン・コア」。

武器空間: 握りの中心 = 原点、穂先 = -Z、三本の穂先は ±Y に開く（刃の平の法線 = ±X）。16 単位 = 1 ブロック。
手に持つと 0.88 倍（astro_hold.SPEC["trident"]）。握りの前後 ±3.4 は篭手に隠れる。

  form_0_grip    柄巻と真珠の口金
  form_1_shaft   柄（握りから両側へ伸びる）。藍の地に水色の波の刻み（斜めに巡る発光の筋）、真珠の節
  form_2_butt    石突き: 真珠の冠・小さな尾ビレ・水色の宝玉・尖り
  form_2_socket  穂の付け根: 藍の八角の台・暗斑の海王星（fx_spin_globe）・横木・波頭の白い鍔
                 （fx_spin_moon: 付け根の下を逆向きに回る小さな衛星トリトン）
  form_3_prongs  三本の穂先（中央は長く、左右は外へ張って先が返る）。どの穂も返しの付いた鏃と水色の刃
"""
from __future__ import annotations

import astro_weapon as W
from astro_common import taper
from astro_paint import core_styles, mix, weapon_styles

from .suit import AQUA, FIN, FOAM, INDIGO, PEARL, diamond, fan_fin

KIND = "trident"

Z_SOCK0 = -16.6         # 穂の付け根（台の後ろ）
Z_BAR = -20.6           # 横木
Z_TIP = -33.6           # 中央の穂先の先端
Z_BUTT = 15.0           # 石突きの端
EDGE = (96, 236, 255)   # 水色の刃


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄巻（篭手に隠れる）と口金
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0), 1.55, 6.8, "wrap", uv_scale=8)
    for z in (-3.6, 3.6):
        W.octa(grip, (0, 0, z), 2.0, 0.8, "pearl", uv_scale=8)
        W.octa(grip, (0, 0, z + (0.55 if z > 0 else -0.55)), 1.7, 0.3, "glow", uv_scale=10)

    # =====================================================================
    #  form_1_shaft — 柄（握りから両側へ伸びる。波の刻みの発光が斜めに巡る）
    # =====================================================================
    shaft = W.form(m, root, 1, "shaft", (0, 0, 0))
    W.octa(shaft, (0, 0, -10.2), 1.25, 12.4, "shaft", uv_scale=6)          # 穂の側
    W.octa(shaft, (0, 0, 8.7), 1.25, 9.4, "shaft", uv_scale=6)             # 石突きの側
    for z, w in ((-8.6, 1.7), (-14.0, 1.75), (8.6, 1.7)):                    # 真珠の節
        W.octa(shaft, (0, 0, z), w, 0.55, "pearl", uv_scale=10)
    # 穂の側の節の間の波頭の飾り（小さな白い返し ±Y）
    for s in (-1, 1):
        W.beam(shaft, (0, s * 0.7, -11.0), (0, s * 1.35, -12.6), 0.5, 0.45, "fin", uv_scale=10)
        W.beam(shaft, (0, s * 1.35, -12.6), (0, s * 1.0, -13.6), 0.42, 0.4, "fin", uv_scale=10)

    # =====================================================================
    #  form_2_butt — 石突き
    # =====================================================================
    butt = W.form(m, root, 2, "butt", (0, 0, 13.4))
    W.octa(butt, (0, 0, 13.6), 1.9, 1.0, "pearl", uv_scale=8)
    W.octa(butt, (0, 0, 14.6), 1.55, 1.2, "plate2", uv_scale=8)
    W.cbox(butt, (0, 0, 15.5), (1.0, 1.0, 0.8), "gem", rotation=(0, 0, 45), uv_scale=12)
    taper(butt, (0, 0, 15.6), (0, 0, 17.6), 0.9, 0.2, 2, "pearl", round_=False, uv_scale=10)
    for s in (-1, 1):                                                        # 尾ビレ（±Y）
        fan_fin(butt, (0, s * 0.6, 13.2), (0, s * 0.6, 15.0),
                [(0, s * 2.4, 16.4), (0, s * 1.8, 17.1)], 0.36, "fin", styles=FIN, uv_scale=10)

    # =====================================================================
    #  form_2_socket — 穂の付け根: 台・海王星・横木・波頭の鍔・衛星トリトン
    # =====================================================================
    sock = W.form(m, root, 2, "socket", (0, 0, Z_SOCK0))
    W.octa(sock, (0, 0, -16.9), 2.0, 0.6, "pearl", uv_scale=8)
    W.bevel(sock, (0, 0, -18.6), (2.0, 3.0, 2.8), "plate2", cut=0.6, axis="x",
            edge_style="plate2_b", uv_scale=8)
    globe = W.spin(m, sock, "globe", (0, 0, -18.6))
    W.sphere(globe, (0, 0, -18.6), 1.3, "globe", uv_scale=14)
    for s in (-1, 1):                                                        # 球の真珠の縁（両面）
        W.ring(sock, (s * 1.02, 0, -18.6), 1.5, 10, (0, 0.3, 0.26), "pearl", axis="x",
               uv_scale=10)
    # 横木（三本の穂の根元を受ける）
    W.cbox(sock, (0, 0, Z_BAR), (1.1, 6.4, 1.2), "plate2", uv_scale=8)
    W.cbox(sock, (0, 0, Z_BAR - 0.05), (1.2, 5.4, 0.45), "glow", uv_scale=10)
    for s in (-1, 1):
        W.cbox(sock, (0, s * 3.2, Z_BAR), (1.3, 1.0, 1.5), "pearl", uv_scale=10)
        # 波頭の白い鍔: 横木の端から後ろへ巻く（YZ 平面のヒレ）
        fan_fin(sock, (0, s * 3.2, Z_BAR + 0.1), (0, s * 1.3, Z_BAR + 1.3),
                [(0, s * 5.6, -16.0), (0, s * 4.6, -14.6), (0, s * 3.0, -14.2)], 0.6, "fin",
                uv_scale=8)
        W.beam(sock, (0, s * 3.2, Z_BAR + 0.1), (0, s * 5.6, -16.0), 0.7, 0.6, "pearl",
               extend=0.2, uv_scale=10)
        W.beam(sock, (0, s * 5.5, -16.1), (0, s * 5.0, -17.4), 0.5, 0.5, "pearl", uv_scale=10)
    # 衛星トリトン: 付け根の下の傾いた軌道を逆向きに回る（WEAPON_ANIMS）
    orbit = W.part(m, sock, "orbit", (0, 0, -12.6), rotation=(0, 18, 0))
    W.ring(orbit, (0, 0, -12.6), 2.7, 10, (0, 0.14, 0.16), "glow_soft", axis="z", uv_scale=10)
    moon = W.spin(m, orbit, "moon", (0, 0, -12.6))
    W.sphere(moon, (0, 2.7, -12.6), 0.8, "triton", uv_scale=14)

    # =====================================================================
    #  form_3_prongs — 三本の穂先（台から -Z へ伸びる）
    # =====================================================================
    pr = W.form(m, root, 3, "prongs", (0, 0, Z_BAR))
    # 中央の穂: 真珠の芯・水色の刃・返しの付いた大きな鏃
    taper(pr, (0, 0, Z_BAR - 0.5), (0, 0, -28.6), 1.5, 1.0, 3, "prong", round_=False,
          uv_scale=8)
    for s in (-1, 1):
        W.beam(pr, (0, s * 0.72, Z_BAR - 0.8), (0, s * 0.5, -28.4), 0.56, 0.3, "edge",
               uv_scale=8)
    diamond(pr, (0, 0, -30.0), 3.8, 0.8, "prong", tilt=90, uv_scale=8)       # 鏃（YZ 平面の菱形）
    diamond(pr, (0, 0, -30.0), 2.4, 0.92, "edge", tilt=90, uv_scale=10)
    diamond(pr, (0, 0, -30.0), 1.0, 1.0, "prong", tilt=90, uv_scale=12)
    taper(pr, (0, 0, -31.8), (0, 0, Z_TIP), 0.9, 0.2, 2, "prong", round_=False, uv_scale=10)
    # 左右の穂: 外へ張ってから前へ。先に鏃と外向きの返し
    for s in (-1, 1):
        pts = [(0, s * 3.2, Z_BAR - 0.4), (0, s * 4.0, -23.4), (0, s * 3.85, -26.2),
               (0, s * 3.4, -27.6)]
        W.polyline(pr, pts, [1.1, 1.0, 0.9], [1.1, 1.0, 0.9], "prong", uv_scale=8)
        W.polyline(pr, [(0, s * 4.6, -23.0), (0, s * 4.45, -26.2)], 0.62, 0.34, "edge",
                   uv_scale=8)
        diamond(pr, (0, s * 3.3, -29.0), 2.7, 0.7, "prong", tilt=90, uv_scale=8)
        diamond(pr, (0, s * 3.3, -29.0), 1.6, 0.82, "edge", tilt=90, uv_scale=10)
        taper(pr, (0, s * 3.3, -30.3), (0, s * 3.1, -31.8), 0.65, 0.16, 1, "prong",
              round_=False, uv_scale=10)
        W.beam(pr, (0, s * 3.9, -28.2), (0, s * 5.0, -26.8), 0.55, 0.5, "prong", uv_scale=10)
        W.beam(pr, (0, s * 4.95, -26.85), (0, s * 5.15, -25.9), 0.45, 0.42, "edge", uv_scale=10)


def build_core(m, root):
    """海王星核: 暗斑の海王星を、真珠の籠（静止の縦の輪と極の冠）・傾いた淡い環・
    逆向きに回る小さな衛星トリトンが囲む。直径 6.4。"""
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    spin = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(spin, (0, 0, 0), 1.8, "globe", uv_scale=16)
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    W.ring(cage, (0, 0, 0), 3.0, 14, (0, 0.45, 0.6), "plate2", axis="z", uv_scale=8,
           styles=["plate2", "plate2", "pearl"])
    for s in (-1, 1):
        y = s * 3.15
        W.octa(cage, (0, y, 0), 1.5, 0.8, "pearl", axis="y", uv_scale=10)
        W.octa(cage, (0, y + s * 0.5, 0), 0.9, 0.4, "glow", axis="y", uv_scale=12)
        W.cbox(cage, (s * 3.05, 0, 0), (0.8, 1.0, 1.0), "pearl", uv_scale=10)
        W.cbox(cage, (s * 3.35, 0, 0), (0.3, 0.6, 0.6), "glow", uv_scale=12)
    # 北極の三叉の冠
    taper(cage, (0, 3.6, 0), (0, 5.0, 0), 0.5, 0.15, 1, "pearl", round_=False, uv_scale=12)
    for s in (-1, 1):
        W.polyline(cage, [(0, 3.6, s * 0.4), (0, 4.2, s * 0.85), (0, 4.7, s * 0.7)], 0.3, 0.3,
                   "pearl", uv_scale=12)
    # 海王星の淡い環（傾いて回る）
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    rg = W.spin(m, rings, "ring", (0, 0, 0), rotation=(24, 0, 0))
    W.ring(rg, (0, 0, 0), 2.45, 12, (0, 0.28, 0.32), "ring_dark", axis="y",
           styles=["ring_dark", "glow_soft", "ring_dark"], uv_scale=10)
    # 衛星トリトン（逆行。傾いた軌道）
    tr = W.spin(m, rings, "triton", (0, 0, 0), rotation=(-30, 0, 20))
    W.sphere(tr, (0, 0, -3.2), 0.5, "triton", uv_scale=14)


# ---------------------------------------------------------------------------
#  塗り
# ---------------------------------------------------------------------------
def _common(key):
    return dict(
        pearl={"kind": "trim", "base": PEARL, "light": (255, 255, 255), "dark": (96, 132, 176),
               "line": (36, 52, 96)},
        gold={"kind": "trim", "base": PEARL, "light": (255, 255, 255), "dark": (96, 132, 176),
              "line": (36, 52, 96)},
        plate2={"base": INDIGO, "light": (92, 116, 218), "dark": (18, 24, 86),
                "line": (8, 10, 44), "panel": 0},
        plate2_b={"base": (26, 34, 112), "light": (70, 88, 180), "dark": (14, 18, 64),
                  "line": (6, 8, 32), "panel": 0},
        glow={"glow": AQUA, "light": (220, 252, 255)},
        glow_soft={"glow": AQUA, "light": (220, 252, 255)},
        gem={"glow": (90, 240, 255), "deep": (10, 40, 120)},
        fin={"kind": "armor", "base": FOAM, "light": (255, 255, 255), "dark": (176, 204, 238),
             "line": (120, 160, 220), "panel": 0, "bolts": False, "outline_k": 0.35,
             "bevel_lo": 0.92, "unlit": True},
        fin_m={"kind": "armor", "base": (190, 222, 250), "light": (236, 248, 255),
               "dark": (140, 186, 236), "line": (110, 150, 214), "panel": 0, "bolts": False,
               "sheen": False, "outline_k": 0.3, "bevel_lo": 0.92, "unlit": True},
        globe=W.globe_style("neptune", emit=34),
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
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        # トリトンは海王星の自転と逆向きに回る（逆行衛星）
        "fx_spin_moon": {"rotation": [0, 0, "-q.anim_time * 120.0"]},
        "fx_spin_globe": {"rotation": [0, 0, "q.anim_time * 40.0"]},
    },
    "swing": {
        "fx_spin_moon": {"rotation": [0, 0, "-v.astro_sw * 360.0"]},
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
