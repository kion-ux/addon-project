# -*- coding: utf-8 -*-
"""太陽（ソル・オーバードライブ）のナノウェポン「紅炎剣 プロミネンス・ブレイド」と星核「恒星核 ソル・コア」。

片手で持つ大剣（kind greatsword、手に持つと 0.86 倍）。
武器空間: 握りの中心 = 原点、刃先 = -Z、刃の幅 = ±Y、刃の平の法線 = ±X（16 単位 = 1 ブロック）。
握りの前後 ±3.0 は篭手に隠れるので、鍔は z = -3.3 より先、柄頭は z = +4.2 より後ろに置く。

  form_0_grip    紅の柄巻・金の口金・柄頭の小さな太陽（金の光条の冠）
  form_1_guard   太陽フレアの形に反り返る金の鍔（二重の翼と発光の筋）・中央の金の輪に浮かぶ小さな太陽
                 （fx_spin_sun が自転）・翼の先で揺れる紅炎（fx_glow_guard）・刃を受ける発振器
  form_2_blade   刃（鍔から z 方向へ伸びる）: 紅の金属の背骨と金の節・両側のプラズマの刃（fx_glow_blade）・
                 刃先へ向かって反った炎の舌の歯（縁の切り欠きが炎の形になる）・プラズマの切先
"""
from __future__ import annotations

import math

import numpy as np

import astro_weapon as W
from astro_common import mat_cube
from astro_paint import core_styles, weapon_styles
from hd_space import rot

KIND = "greatsword"

Z_BLADE0 = -7.4          # 刃の付け根（発振器の前）
Z_BLADE1 = -35.0         # 平行部の終わり
Z_TIP = -41.6            # 切先
SPINE_W = 0.8            # 背骨の半幅（Y）
PLASMA_W = 2.35          # プラズマの刃の外の縁（Y）

ICON = {"weapon": (90, 0, 45), "core": (20, -16, 0)}


def tongue(bone, base, ang_deg, L, w0, w1, thick, style, n=2, **kw):
    """YZ 平面の炎の舌（刃の縁の歯・鍔の炎）。base から、+Y を 0°・-Z へ倒す向きを正にした角度 ang_deg の向きへ、
    長さ L・幅 w0 → w1 の n 段。局所 +Y が舌の先（flame の dir "up" が先へ向かって細る）。"""
    a = math.radians(ang_deg)
    d = np.array([0.0, math.cos(a), -math.sin(a)])
    R = rot(math.degrees(math.atan2(-d[2], d[1])), 0, 0)      # 局所 +Y → d（X 軸まわり）
    base = np.asarray(base, float)
    out = []
    for i in range(n):
        t = (i + 0.5) / n
        w = w0 + (w1 - w0) * t
        out.append(mat_cube(bone, base + d * (L * t), (thick * (1 - 0.15 * i), L / n * 1.15, w),
                            style, R, **kw))
    return out


# ===========================================================================
#  ナノウェポン
# ===========================================================================
def build_weapon(m, root):
    # ---- form_0_grip: 柄・口金・柄頭の太陽 --------------------------------------------------
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.5), 1.9, 7.6, "wrap", uv_scale=8)
    for z, ln in ((-3.35, 0.8), (4.35, 0.8)):
        W.octa(grip, (0, 0, z), 2.45, ln, "gold", uv_scale=8)
    W.octa(grip, (0, 0, 0.5), 2.08, 0.45, "gold", uv_scale=8)
    W.octa(grip, (0, 0, 5.3), 2.3, 1.2, "spine", uv_scale=8)               # 柄頭の台（紅）
    W.octa(grip, (0, 0, 5.95), 2.8, 0.35, "gold", uv_scale=10)
    W.sphere(grip, (0, 0, 7.1), 1.05, "sun", uv_scale=14)                   # 柄頭の小さな太陽
    for a in (0, 90, 180, 270):                                             # 光条の冠（後ろへ反る）
        d = rot(0, 0, a) @ np.array([0.0, 1.0, 0.0])
        p0 = (d[0] * 1.0, d[1] * 1.0, 6.2)
        p1 = (d[0] * 2.1, d[1] * 2.1, 7.9)
        W.beam(grip, p0, p1, 0.5, 0.5, "gold", uv_scale=10, extend=0.2)

    # ---- form_1_guard: 太陽フレアの鍔・中央の太陽 ------------------------------------------
    guard = W.form(m, root, 1, "guard", (0, 0, -3.6))
    zc = -5.2
    sun = W.spin(m, guard, "sun", (0, 0, zc))
    W.sphere(sun, (0, 0, zc), 1.55, "sun", uv_scale=14)
    for s in (-1, 1):                                                       # 太陽を囲む金の輪（両面）
        W.ring(guard, (s * 0.62, 0, zc), 2.15, 12, (0, 0.42, 0.34), "gold", axis="x", uv_scale=10)
    W.cbox(guard, (0, 0, zc), (0.7, 0.5, 4.9), "spine", uv_scale=8)          # 輪の中の軸（縦）
    for s in (-1, 1):
        # 主翼: 外へ張り出し、刃の側へ反り返る太陽フレアの弧（太い金 → 細い先）
        main = [(0, s * 1.9, -4.5), (0, s * 4.1, -3.5), (0, s * 6.3, -3.9), (0, s * 7.7, -5.6),
                (0, s * 8.0, -7.9), (0, s * 7.4, -9.9)]
        W.polyline(guard, main, [2.1, 1.8, 1.5, 1.1, 0.7], [2.3, 1.9, 1.5, 1.1, 0.7], "plate2", uv_scale=7)
        W.polyline(guard, [(q[0], q[1] + s * 0.5, q[2] + 0.35) for q in main[:4]],
                   [2.2, 1.9, 1.6], [0.3, 0.3, 0.3], "glow", uv_scale=10)
        W.polyline(guard, [(q[0], q[1] - s * 0.55, q[2] - 0.35) for q in main[1:5]],
                   [1.0, 0.9, 0.7], [0.7, 0.6, 0.5], "crimson", uv_scale=8)
        # 副翼: 輪の脇から刃の側へ細く巻く（紅）
        W.polyline(guard, [(0, s * 2.3, -6.2), (0, s * 3.9, -7.2), (0, s * 4.4, -8.9)],
                   [1.3, 0.9], [1.0, 0.7], "crimson", uv_scale=8)
        # 輪の上下の留め具
        W.cbox(guard, (0, s * 2.4, zc), (1.7, 0.7, 1.6), "plate2", uv_scale=8)
    # 翼の先で揺れる紅炎（両面の fx）
    fl = W.glow(m, guard, "guard", (0, 0, -6.0))
    for s in (-1, 1):
        tongue(fl, (0, s * 7.9, -5.2), -10 if s > 0 else 190, 2.6, 1.5, 0.4, 0.5, "flame_t")
        tongue(fl, (0, s * 6.0, -3.4), -50 if s > 0 else 230, 2.2, 1.3, 0.3, 0.45, "flame_t")
        tongue(fl, (0, s * 8.1, -8.0), 20 if s > 0 else 160, 1.8, 1.1, 0.3, 0.45, "flame_t")
    # 刃の発振器（刃を受ける黒い襟と放熱の光）
    W.cbox(guard, (0, 0, -6.95), (2.0, 4.6, 1.1), "frame", uv_scale=8)
    for s in (-1, 1):
        W.cbox(guard, (s * 1.02, 0, -6.95), (0.1, 3.6, 0.35), "edge_hot", uv_scale=10)

    # ---- form_2_blade: 刃 ------------------------------------------------------------------
    blade = W.form(m, root, 2, "blade", (0, 0, Z_BLADE0))
    L = Z_BLADE0 - Z_BLADE1
    zm = (Z_BLADE0 + Z_BLADE1) / 2
    # 背骨（紅の金属）と、両面の発光の筋・金の節
    W.cbox(blade, (0, 0, zm), (1.3, SPINE_W * 2, L), "spine", uv_scale=5)
    for s in (-1, 1):
        W.cbox(blade, (0, s * 0.45, zm - 0.6), (1.36, 0.16, L - 2.4), "energy", uv_scale=8)
    for i in range(5):
        z = -10.0 - i * 5.2
        k = 1.0 - i * 0.08
        W.chamfer(blade, (0, 0, z), (1.6, 1.4 * k, 1.8 * k), "plate2", cut=0.3, axis="x", uv_scale=8)
        W.cbox(blade, (0, 0, z - 0.2), (1.64, 0.9 * k, 0.2), "glow", uv_scale=10)
    W.blade_point(blade, Z_BLADE1 + 0.05, SPINE_W, Z_TIP + 2.4, 1.3, "spine_flat", layer=0.7,
                  uv_scale=6)
    # プラズマの刃（両面の fx。脈打つ）: 背骨の側から 白熱 → 橙 → 紅 の三層の帯と、刃先へ反る炎の舌、プラズマの切先
    pl = W.glow(m, blade, "blade", (0, 0, Z_BLADE0))
    bands = ((SPINE_W, 1.2, "edge_hot", 0.86), (1.2, 2.0, "plasma", 0.8), (2.0, PLASMA_W, "plasma_rim", 0.74))
    for s in (-1, 1):
        for y0, y1, st, th in bands:
            W.cbox(pl, (0, s * (y0 + y1) / 2, zm), (th, y1 - y0, L), st, uv_scale=5)
        # 炎の舌: 長短を不揃いに、根元が太く先へ向かって曲がりながら細る（3 段で反る）
        for k, (z, Lt, a0) in enumerate(((-9.4, 4.4, 34), (-14.8, 3.0, 42), (-19.6, 4.0, 38),
                                         (-24.8, 2.8, 46), (-29.4, 3.0, 48), (-33.2, 1.8, 56))):
            base = np.array([0.0, s * (PLASMA_W - 0.4), z])
            w0 = 2.9 - k * 0.22
            for j in range(3):
                a = a0 + j * 16
                tongue(pl, base, a if s > 0 else 180 - a, Lt / 3 * 1.3,
                       w0 * (1 - j * 0.3), w0 * (1 - (j + 1) * 0.3), 0.64 - j * 0.06, "flame_t", n=1)
                ar = math.radians(a)
                base = base + np.array([0.0, s * math.cos(ar), -math.sin(ar)]) * (Lt / 3)
    W.blade_point(pl, Z_BLADE1 + 0.05, PLASMA_W, Z_TIP, 0.8, "plasma_flat", layer=0.8, uv_scale=6)
    W.blade_point(pl, Z_BLADE1 + 0.3, 1.2, Z_TIP + 1.6, 0.86, "edge_hot", layer=0.6, uv_scale=6)


# ===========================================================================
#  星核: 粒状斑の小さな太陽・炎のコロナの輪・金の籠
# ===========================================================================
def build_core(m, root):
    sun = W.form(m, root, 0, "sun", (0, 0, 0))
    sp = W.spin(m, sun, "sun", (0, 0, 0))
    W.sphere(sp, (0, 0, 0), 1.6, "sun", uv_scale=16)
    # コロナ（正面向きの輪に、炎の舌と金の短い光条が交互に）
    cor = W.form(m, root, 1, "corona", (0, 0, 0))
    cs = W.spin(m, cor, "corona", (0, 0, 0))
    for i in range(8):
        a = i * 45.0
        R = rot(0, 0, a)
        u = R @ np.array([0.0, 1.0, 0.0])
        if i % 2 == 0:
            for k, (r0, w) in enumerate(((1.95, 0.85), (2.45, 0.45))):
                mat_cube(cs, u * r0, (w, 0.62, 0.3), "flame_c", R, uv_scale=12)
        else:
            mat_cube(cs, u * 2.05, (0.55, 0.7, 0.32), "gold", R, uv_scale=12)
            mat_cube(cs, u * 2.45, (0.36, 0.36, 0.3), "gold", R @ rot(0, 0, 45), uv_scale=12)
    # 金の籠: 縦の輪（極の軸受けで留める）と、傾いた銀の輪
    cage = W.form(m, root, 2, "cage", (0, 0, 0))
    ra = W.spin(m, cage, "ring_a", (0, 0, 0))
    W.ring(ra, (0, 0, 0), 2.85, 14, (0, 0.38, 0.5), "gold", axis="x", styles=["gold", "gold", "crimson"],
           uv_scale=10)
    for s in (-1, 1):
        y = s * 3.25
        W.octa(cage, (0, y, 0), 1.4, 0.7, "crimson", axis="y", uv_scale=10)
        W.octa(cage, (0, y + s * 0.5, 0), 0.9, 0.4, "gold", axis="y", uv_scale=10)
        W.cbox(cage, (0, y + s * 0.85, 0), (0.42, 0.45, 0.42), "gem", rotation=(0, 45, 0), uv_scale=12)
    rb = W.spin(m, cage, "ring_b", (0, 0, 0), rotation=(26, 0, 0))
    W.ring(rb, (0, 0, 0), 3.35, 16, (0, 0.26, 0.36), "plate", axis="y", styles=["plate", "glow"],
           uv_scale=10)


# ---------------------------------------------------------------------------
#  塗り
# ---------------------------------------------------------------------------
FLAME = {"kind": "flame", "dir": "up", "glow": (255, 132, 30), "light": (255, 244, 180),
         "deep": (206, 44, 12), "bevel": False, "outline": False}


def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        wrap={"base": (70, 16, 10), "strap": (236, 156, 44), "skin": (255, 232, 180)},
        spine={"kind": "metal", "base": (110, 30, 18), "light": (196, 88, 52), "dark": (56, 12, 8),
               "line": (26, 6, 4), "panel": 6},
        spine_flat={"kind": "blade", "base": (130, 40, 24), "light": (220, 120, 70), "dark": (70, 16, 8),
                    "line": (30, 8, 4), "outline": False, "bevel": False, "fuller": False,
                    "hamon_off": True, "glint_period": 9999, "hi": 0.0, "lo": 1.1},
        plasma={"kind": "energy", "glow": (255, 128, 24), "light": (255, 214, 96), "waves": 7},
        plasma_rim={"kind": "glowline", "glow": (236, 60, 16), "light": (255, 140, 50), "bevel": False,
                    "outline": False},
        plate2={"base": (255, 204, 76), "light": (255, 240, 170), "dark": (196, 120, 28)},
        plasma_flat={"kind": "energy", "glow": (255, 110, 24), "light": (255, 200, 90), "waves": 4},
        edge_hot={"glow": (255, 214, 120), "emit": 10, "sat": 0.35},
        flame_t=dict(FLAME),
        sun=W.globe_style("sol", emit=14, halo=(255, 220, 120)),
        crimson={"kind": "armor", "base": (178, 40, 26), "light": (236, 104, 64), "dark": (112, 22, 14),
                 "line": (64, 12, 8), "panel": 0},
        glow={"glow": (255, 170, 40), "light": (255, 246, 200)},
    )


def CORE_STYLES(key):
    return core_styles(
        key,
        sun=W.globe_style("sol", emit=12, halo=(255, 220, 120)),
        flame_c=dict(FLAME, glow=(255, 160, 40), light=(255, 250, 220)),
        crimson={"kind": "armor", "base": (178, 40, 26), "light": (236, 104, 64), "dark": (112, 22, 14),
                 "line": (64, 12, 8), "panel": 0},
        gem={"glow": (255, 140, 40), "deep": (150, 20, 10)},
        glow={"glow": (255, 170, 40), "light": (255, 246, 200)},
    )


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_sun": {"rotation": [0, 0, "q.anim_time * 90.0"]},
        # プラズマの刃は太さだけ脈打つ（長さは変えない）・鍔の炎は揺らめく
        "fx_glow_blade": {"scale": ["1.0 + math.sin(q.anim_time * 240.0) * 0.06",
                                    "1.0 + math.sin(q.anim_time * 240.0) * 0.06", "1.0"]},
        "fx_glow_guard": {"scale": ["1.0", "1.0 + math.sin(q.anim_time * 420.0) * 0.08",
                                    "1.0 + math.sin(q.anim_time * 300.0) * 0.08"]},
    },
    "swing": {
        # 振ると鍔の太陽が一回転ぶん加速する
        "fx_spin_sun": {"rotation": [0, 0, "v.astro_sw * 360.0"]},
    },
    "form_axes": {"form_2_blade": "z"},
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_sun": {"rotation": [0, "q.anim_time * 40.0", 0]},
        "fx_spin_corona": {"rotation": [0, 0, "q.anim_time * 60.0"]},
        "fx_spin_ring_a": {"rotation": [0, "q.anim_time * 80.0", 0]},
        "fx_spin_ring_b": {"rotation": [0, "-q.anim_time * 120.0", 0]},
    },
}
