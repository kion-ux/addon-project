# -*- coding: utf-8 -*-
"""天王星（ウラノス）のナノウェポン「傾天弩 ティルト・ボウガン」と星核「天王星核 ウラヌス・コア」。

武器空間: 握りの中心 = 原点、銃口 = -Z、弓は ±X に張る、機関部は握りの上（+Y）。16 単位 = 1 ブロック。
手に持つと 0.85 倍（astro_hold.SPEC["crossbow"]）。握りの前後 ±3.1 は篭手に隠れる。

  form_0_grip    握り（溝のある芯と青緑の板・発光線）・紺の口金・引き金と用心金・握りの尻
  form_1_body    機関部: 面を切った淡い青緑の胴、青緑の側板（発光線と霜の ◆）、紺の矢溝と光る矢道、
                 霜の ◆ の照門、短い銃床、銃口の八角の発射口
  form_2_limbs   弓: 紺の弓台から ±X へ後ろへ反って張る二段の弓（霜の前縁・発光線）、
                 先端の滑車と氷晶の弓端、光る弦（矢の尻へ）。形成で ±X へ「開く」
  form_3_bolt    装填された絶対零度の矢（氷の矢柄・結晶の鏃・◆ の矢羽根。fx_glow_bolt で脈打つ）
  form_4_ring    銃口の前で 98° 傾いて回る小さな環（fx_spin_tilt: 二重の帯と 3 つの氷の衛星）
"""
from __future__ import annotations

import math

import astro_weapon as W
from astro_paint import core_styles, weapon_styles

from .suit import SUIT_STYLES, crystal, diamond

KIND = "crossbow"

Y0 = 3.5            # 機関部の中心の高さ（握りの上）
Z_BACK = -2.4       # 機関部の後端（これより後ろ・上は前腕と篭手に入る）
Z_FRONT = -12.4     # 弓台
Z_MUZ = -14.0       # 発射口
Z_RING = -16.2      # 傾いた環の中心
Z_NOCK = -3.5       # 弦を掛ける所（矢の尻）
TILT = (8, 26, 0)   # 環の傾き（98° の意匠: 縦に立ち、上が 8° 前へ、26° ひねる）

ICON = {"weapon": (24, -58, -38), "core": (28, -16, 0)}

# スーツと同じ素材（霜の白・紺・氷・結晶・縁）
_SHARED = {k: SUIT_STYLES[k] for k in ("frost", "frost_p", "navy", "rim", "ice", "crystal", "ringglow",
                                       "ringband", "gem", "glow")}


# ===========================================================================
#  ナノウェポン
# ===========================================================================
def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 握り・口金・引き金と用心金・握りの尻
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.0), 1.6, 5.2, "frame", uv_scale=8)                         # 溝のある握りの芯
    for s in (-1, 1):                                                                  # 握りの青緑の板と発光線
        W.cbox(grip, (s * 0.72, -0.1, 0.0), (0.3, 1.1, 4.4), "plate2", uv_scale=8)
        W.cbox(grip, (s * 0.88, -0.1, 0.0), (0.06, 0.2, 3.6), "glow", uv_scale=12)
    for z in (-2.75, 2.75):
        W.octa(grip, (0, 0, z), 2.0, 0.5, "navy", uv_scale=8)
    W.beam(grip, (0, 0.6, -3.2), (0, Y0 - 0.6, -4.2), 1.3, 1.5, "frame", uv_scale=8)     # 握りと機関部の首
    W.polyline(grip, [(0, Y0 - 1.2, -5.8), (0, -0.8, -5.4), (0, -1.4, -3.6)], 0.5, 0.5, "navy", uv_scale=10)
    W.beam(grip, (0, Y0 - 1.3, -4.5), (0, 0.4, -4.7), 0.45, 0.4, "rim", uv_scale=12)  # 引き金
    W.octa(grip, (0, -0.05, 3.35), 1.7, 0.8, "plate2", uv_scale=8)                    # 握りの尻
    diamond(grip, (0, -0.05, 3.85), 0.9, 0.25, "gem", (0, 0, 0), uv_scale=14)

    # =====================================================================
    #  form_1_body — 機関部（握りの前上。後端は篭手の前）
    # =====================================================================
    body = W.form(m, root, 1, "body", (0, Y0, Z_BACK))
    L = Z_BACK - Z_FRONT
    zc = (Z_BACK + Z_FRONT) / 2
    W.bevel(body, (0, Y0, zc), (2.8, 2.8, L), "plate", cut=0.65, axis="z", uv_scale=6)
    W.cbox(body, (0, Y0, Z_BACK + 0.2), (2.4, 2.4, 0.5), "navy", uv_scale=8)            # 後端の蓋
    W.cbox(body, (0, Y0, Z_BACK + 0.48), (0.9, 0.9, 0.12), "glow", uv_scale=12)
    W.cbox(body, (0, Y0 + 1.5, zc - 0.6), (1.3, 0.45, L + 1.6), "navy", uv_scale=6)      # 矢溝
    W.cbox(body, (0, Y0 + 1.74, zc - 0.6), (0.45, 0.12, L + 1.2), "energy", uv_scale=8)  # 光る矢道
    for s in (-1, 1):
        W.rbox(body, (s * 1.55, Y0 - 0.1, zc), (0.6, 2.3, L - 1.6), "plate2", rot=(0, 0, -12 * s), uv_scale=6)
        W.cbox(body, (s * 1.86, Y0 + 0.55, zc - 0.4), (0.14, 0.26, L - 3.4), "glow", uv_scale=10)
        diamond(body, (s * 1.92, Y0 - 0.25, Z_BACK - 2.0), 1.5, 0.25, "frost", (0, 90, 0), uv_scale=12)
        diamond(body, (s * 2.05, Y0 - 0.25, Z_BACK - 2.0), 0.7, 0.2, "gem", (0, 90, 0), uv_scale=14)
        W.cbox(body, (s * 1.86, Y0 - 0.6, Z_FRONT + 3.4), (0.14, 0.9, 2.2), "vent", uv_scale=10)
    W.rbox(body, (0, Y0 - 1.55, Z_FRONT + 3.0), (1.7, 1.0, 5.0), "navy", rot=(-10, 0, 0), uv_scale=6)  # 下の竜骨
    # 照門: 立てた霜の ◆
    W.cbox(body, (0, Y0 + 1.95, Z_BACK - 0.9), (0.6, 0.8, 0.8), "navy", uv_scale=10)
    diamond(body, (0, Y0 + 2.75, Z_BACK - 0.9), 1.6, 0.3, "frost", uv_scale=12)
    diamond(body, (0, Y0 + 2.75, Z_BACK - 1.1), 0.7, 0.2, "gem", uv_scale=14)
    # 発射口（八角）と縁の光
    W.octa(body, (0, Y0 + 0.6, Z_MUZ), 2.0, 1.4, "navy", uv_scale=8)
    W.ring(body, (0, Y0 + 0.6, Z_MUZ - 0.75), 0.85, 8, (0, 0.24, 0.2), "glow", axis="z", uv_scale=12)

    # =====================================================================
    #  form_2_limbs — 弓（±X へ開く）
    # =====================================================================
    limbs = W.form(m, root, 2, "limbs", (0, Y0, Z_FRONT))
    W.bevel(limbs, (0, Y0 + 0.1, Z_FRONT), (4.2, 2.4, 2.2), "navy", cut=0.5, axis="z", uv_scale=8)
    W.cbox(limbs, (0, Y0 + 0.1, Z_FRONT - 1.12), (2.6, 0.3, 0.12), "glow", uv_scale=10)
    for s in (-1, 1):
        base = (s * 1.9, Y0 + 0.2, Z_FRONT - 0.2)
        mid = (s * 5.0, Y0 + 0.5, Z_FRONT + 0.5)
        tip = (s * 8.0, Y0 + 0.7, Z_FRONT + 2.8)
        W.polyline(limbs, [base, mid, tip], [1.5, 1.15], [1.0, 0.8], "plate", uv_scale=8)
        W.polyline(limbs, [(s * 1.9, Y0 + 0.25, Z_FRONT - 0.9), (s * 5.0, Y0 + 0.5, Z_FRONT - 0.2),
                           (s * 7.7, Y0 + 0.7, Z_FRONT + 2.0)], 0.4, 0.55, "frost", uv_scale=10)
        W.polyline(limbs, [(s * 2.0, Y0 + 0.75, Z_FRONT - 0.1), (s * 5.0, Y0 + 0.95, Z_FRONT + 0.55),
                           (s * 7.6, Y0 + 1.1, Z_FRONT + 2.6)], 0.22, 0.14, "glow", uv_scale=12)
        # 滑車と氷晶の弓端
        W.octa(limbs, tip, 1.5, 1.2, "navy", axis="y", uv_scale=10)
        W.octa(limbs, (tip[0], tip[1] + 0.65, tip[2]), 0.8, 0.2, "glow", axis="y", uv_scale=12)
        crystal(limbs, (tip[0] + s * 0.3, tip[1], tip[2] + 0.2), (s * 0.85, 0.12, 0.5), 3.4, 0.95, "ice",
                uv_scale=10)
        # 弦（滑車から矢の尻へ）
        W.beam(limbs, (s * 7.8, Y0 + 0.75, Z_FRONT + 2.7), (s * 0.15, Y0 + 2.0, Z_NOCK), 0.18, 0.18, "edge",
               uv_scale=12)

    # =====================================================================
    #  form_3_bolt — 装填された絶対零度の矢
    # =====================================================================
    YB = Y0 + 2.05
    bolt = W.form(m, root, 3, "bolt", (0, YB, Z_NOCK))
    gb = W.glow(m, bolt, "bolt", (0, YB, Z_NOCK - 5.0))
    W.beam(gb, (0, YB, Z_NOCK), (0, YB, Z_MUZ - 0.6), 0.34, 0.34, "ice", uv_scale=10)
    crystal(gb, (0, YB, Z_MUZ - 0.4), (0, 0, -1), 2.6, 0.85, "crystal", tip=0.55, uv_scale=12)
    diamond(gb, (0, YB, Z_NOCK - 0.6), 1.1, 0.14, "ice", (0, 90, 0), uv_scale=12)     # 矢羽根（縦）
    diamond(gb, (0, YB, Z_NOCK - 0.6), 1.1, 0.14, "ice", (90, 0, 0), uv_scale=12)     # 矢羽根（横）

    # =====================================================================
    #  form_4_ring — 銃口の前で傾いて回る小さな環
    # =====================================================================
    C = (0, Y0 + 0.6, Z_RING)
    rg = W.form(m, root, 4, "ring", C, rotation=TILT)
    sp = W.spin(m, rg, "tilt", C)
    W.ring(sp, C, 2.8, 16, (0, 0.42, 0.34), "ringglow", axis="z", styles=["ringglow", "ice"], uv_scale=10)
    W.ring(sp, C, 2.2, 16, (0, 0.55, 0.5), "ringband", axis="z", styles=["ringband", "navy"], uv_scale=10)
    for k in range(3):
        a = math.radians(k * 120 + 30)
        M = (C[0] - 2.8 * math.sin(a), C[1] + 2.8 * math.cos(a), C[2])
        W.rbox(sp, M, (0.8, 0.8, 0.8), "crystal", rot=(45, 0, 45), uv_scale=14)


# ===========================================================================
#  星核: 淡い青緑の天王星。98° 傾いて縦に立つ環が球の前を縦に横切り、紺の籠（正面向きの輪）が囲む。直径 6.6
# ===========================================================================
CORE_TILT = (8, 68, 0)      # 環と自転軸: 縦に立ち（側面向きに近い）、8° 傾く


def build_core(m, root):
    # 天王星（環と同じ傾いた軸で自転）
    globe = W.form(m, root, 0, "globe", (0, 0, 0), rotation=CORE_TILT)
    gs = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(gs, (0, 0, 0), 1.6, "globe", uv_scale=16)
    # 籠: 正面向きの輪（紺と青緑）・上下の極の冠（淡い八角 + 霜の ◆ + 宝玉）・左右の留め具
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    W.ring(cage, (0, 0, 0), 3.1, 16, (0, 0.42, 0.7), "navy", axis="z", styles=["navy", "plate2"], uv_scale=8)
    for s in (-1, 1):
        y = s * 3.25
        W.octa(cage, (0, y, 0), 1.6, 0.8, "plate", axis="y", uv_scale=10)
        diamond(cage, (0, y + s * 0.7, 0), 1.1, 0.4, "frost", (0, 0, 0), uv_scale=14)
        W.cbox(cage, (0, y + s * 0.7, -0.25), (0.45, 0.45, 0.2), "gem", rotation=(0, 0, 45), uv_scale=14)
        W.cbox(cage, (s * 3.15, 0, 0), (0.7, 1.0, 1.0), "frost", uv_scale=10)
        W.cbox(cage, (s * 3.5, 0, 0), (0.2, 0.5, 0.5), "glow", uv_scale=12)
    # 環: 天王星と同じ軸で回る細い光の帯（暗い隙間を挟んで内に紺の帯）と、2 つの氷の衛星
    rings = W.form(m, root, 2, "rings", (0, 0, 0), rotation=CORE_TILT)
    ra = W.spin(m, rings, "ring", (0, 0, 0))
    W.ring(ra, (0, 0, 0), 2.75, 16, (0, 0.26, 0.26), "ringglow", axis="z", styles=["ringglow", "ice"],
           uv_scale=10)
    W.ring(ra, (0, 0, 0), 2.25, 14, (0, 0.22, 0.34), "ringband", axis="z", uv_scale=10)
    for k in range(2):
        a = math.radians(k * 180 + 45)
        W.rbox(ra, (-2.75 * math.sin(a), 2.75 * math.cos(a), 0), (0.7, 0.7, 0.7), "crystal", rot=(45, 0, 45),
               uv_scale=14)


# ---------------------------------------------------------------------------
#  塗り（astro_paint の惑星の配色から。上書きだけ書く）
# ---------------------------------------------------------------------------
def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        energy={"glow": (150, 244, 255), "light": (250, 255, 255)},
        edge={"glow": (150, 244, 255), "emit": 30, "sat": 0.4},
        wrap={"base": (22, 36, 54), "strap": (47, 159, 168), "skin": (214, 240, 246)},
        vent={"base": (40, 64, 90), "glow": (150, 244, 255), "deep": (14, 60, 90)},
        **_SHARED,
    )


def CORE_STYLES(key):
    return core_styles(key, globe=W.globe_style("uranus", emit=110, shade=0.3), **_SHARED)


# ---------------------------------------------------------------------------
#  アタッチャブルのアニメ
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_tilt": {"rotation": [0, 0, "q.anim_time * 120.0"]},
        "fx_glow_bolt": W.pulse_expr(180, 0.05),
    },
    "swing": {
        # 撃つたびに環が一回転ぶん加速する
        "fx_spin_tilt": {"rotation": [0, 0, "v.astro_sw * 360.0"]},
    },
    "form_axes": {"form_2_limbs": "x", "form_3_bolt": "z"},   # 弓は ±X へ開き、矢は矢道に沿って伸びる
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": dict(W.spin_expr("z", 40), **W.pulse_expr(150, 0.03)),
        "fx_spin_ring": W.spin_expr("z", -90),
    },
}
