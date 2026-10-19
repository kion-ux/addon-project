# -*- coding: utf-8 -*-
"""水星（クイックシルバー）のナノウェポン「水銀刃 ヘルメス・エッジ」と星核「水星核 マーキュリー・コア」。

武器空間: 握りの中心 = 原点、切先 = -Z、刃の幅 = ±Y（片刃: **-Y が刃**、+Y が峰）、平の法線 = ±X。
手に持つと 0.9 倍（astro_hold.SPEC["saber"]）。握りの前後 ±2.9 は篭手に隠れるので、
鍔は z = -3.2 より先、柄頭は z = +3.4 より後ろに置く。

  form_0_grip   黒い柄巻と鏡面の口金、柄頭に液体金属の滴（水銀の雫の宝玉を三本の爪が抱く）
  form_1_guard  鏡面の鍔と、刃の付け根を回る冷却フィン（fx_spin_fins: 六枚の放熱板のタービン）、
                昼（橙）と夜（シアン）の放熱口
  form_2_blade  峰の側へ反る片刃の刃。液体金属の波打つ照り（刃文）・シアンに光る刃・暗い樋を走る光・
                平を横切る波紋の筋・峰の鏡面の帯・切先は刃が峰へ反り上がる
  form_3_wings  鍔の両脇から刃に沿って前へ流れるヘルメスの小翼
"""
from __future__ import annotations

import math

import numpy as np

import astro_weapon as W
from astro_paint import core_styles, mix, weapon_styles

KIND = "saber"

DAY = (255, 150, 60)
NIGHT = (120, 240, 255)
EDGE = (110, 236, 255)

# 刃の寸法（武器空間）
Z0 = -5.4                 # 刃の付け根
Z_TIP = -28.6             # 切先
LIFT = 2.4                # 切先での峰側への反り（+Y）
W0, W1 = 3.0, 1.9         # 刃の幅（付け根 → 先）
THICK = 0.72              # 刃の厚み（X）
N_SEG = 8


def centre(t):
    """刃の中心線（t = 0 付け根 … 1 先）。峰の側（+Y）へ二次で反る。"""
    return np.array([0.0, LIFT * t * t, Z0 + (Z_TIP - Z0) * t])


def spine_dir(t):
    """中心線の接線に直交する、峰の側（+Y 寄り）の単位ベクトル（YZ 平面）。"""
    d = np.array([0.0, 2 * LIFT * t, Z_TIP - Z0])
    d /= np.linalg.norm(d)
    return np.array([0.0, -d[2], d[1]])


def width(t):
    return W0 + (W1 - W0) * t


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄・口金・柄頭（水銀の雫を三本の爪と光の冠が抱き、小さな滴が周りを回る）
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.25), 1.6, 6.6, "wrap", uv_scale=8)
    for z, ln in ((-3.25, 0.7), (3.75, 0.7)):
        W.octa(grip, (0, 0, z), 2.15, ln, "chrome", uv_scale=8)
    W.octa(grip, (0, 0, 0.25), 1.8, 0.4, "chrome", uv_scale=8)
    for z in (-1.6, 2.1):                                                 # 柄巻の締め輪
        W.octa(grip, (0, 0, z), 1.74, 0.26, "frame", uv_scale=10)
    for sx in (-1, 1):                                                    # 目貫（柄の両側の菱形）
        W.rbox(grip, (sx * 0.8, 0, 0.95), (0.2, 0.62, 0.62), "chrome", rot=(45, 0, 0), uv_scale=12)
    # 柄頭: 細い首 → 締め輪 → 三本の爪 → 水銀の雫（後ろへ尖る）
    W.octa(grip, (0, 0, 4.5), 1.3, 0.9, "frame", uv_scale=10)
    W.octa(grip, (0, 0, 4.15), 1.7, 0.3, "chrome", uv_scale=10)
    for k in range(3):
        a = math.radians(k * 120 + 90)
        p0 = (math.cos(a) * 0.55, math.sin(a) * 0.55, 4.7)
        p1 = (math.cos(a) * 1.25, math.sin(a) * 1.25, 5.8)
        p2 = (math.cos(a) * 0.7, math.sin(a) * 0.7, 6.9)
        W.polyline(grip, [p0, p1, p2], 0.32, 0.32, "chrome", uv_scale=12)
        W.cbox(grip, p1, (0.36, 0.36, 0.36), "glow_night", uv_scale=16)    # 爪の節の灯り
    drop = W.glow(m, grip, "drop", (0, 0, 5.9))
    W.sphere(drop, (0, 0, 5.9), 1.0, "drop", uv_scale=14)
    W.beam(drop, (0, 0, 6.7), (0, 0, 7.9), 0.9, 0.9, "drop", uv_scale=14)
    W.cbox(drop, (0, 0, 8.05), (0.45, 0.45, 0.5), "drop", rotation=(0, 0, 45), uv_scale=14)
    W.ring(drop, (0, 0, 5.75), 1.38, 6, (0.5, 0.18, 0.22), "glow_night", axis="z",
           styles=["glow_night", "chrome"], uv_scale=14)                 # 爪の光の冠
    # 柄頭の周りを回る三つの小さな滴（液体金属の衛星）
    orb = W.spin(m, grip, "orbit", (0, 0, 6.35))
    for k in range(3):
        a = math.radians(k * 120 + 30)
        c = (math.cos(a) * 1.85, math.sin(a) * 1.85, 6.35)
        W.cbox(orb, c, (0.46, 0.46, 0.46), "drop", uv_scale=16)
        W.rbox(orb, c, (0.4, 0.4, 0.4), "drop", rot=(45, 45, 0), uv_scale=16)

    # =====================================================================
    #  form_1_guard — 鍔（鏡面の芯 + 両面の銀の板・放熱スリット・リベット）・上下の放射口・冷却フィン
    # =====================================================================
    guard = W.form(m, root, 1, "guard", (0, 0, -3.4))
    W.bevel(guard, (0, 0, -4.0), (1.9, 3.4, 1.4), "chrome", cut=0.45, axis="z",
            edge_style="chrome2", uv_scale=8)
    W.octa(guard, (0, 0, -4.9), 2.2, 0.6, "frame", uv_scale=8)            # 刃を受ける襟
    W.chamfer(guard, (0, 0, -3.36), (1.55, 2.9, 0.24), "frame", cut=0.3, axis="z", uv_scale=10)
    for sx, st in ((-1, "glow_day"), (1, "glow_night")):                 # 昼（-X）と夜（+X）の面
        W.cbox(guard, (sx * 1.02, 0, -4.0), (0.2, 2.3, 1.0), "plate", uv_scale=10)
        for y in (-0.62, 0.0, 0.62):                                     # 放熱スリット
            W.cbox(guard, (sx * 1.15, y, -4.02), (0.16, 0.24, 0.62), st, uv_scale=14)
        for y in (-0.95, 0.95):
            for z in (-3.67, -4.35):
                W.cbox(guard, (sx * 1.15, y, z), (0.16, 0.24, 0.24), "rivet", uv_scale=16)
    for sy, st in ((1, "glow_night"), (-1, "glow_day")):                 # 上下（峰・刃の側）の放射口
        W.octa(guard, (0, sy * 1.95, -4.0), 0.78, 0.5, "frame", axis="y", uv_scale=12)
        W.cbox(guard, (0, sy * 2.26, -4.0), (0.42, 0.16, 0.42), st, uv_scale=16)
    # 鍔の外周の細い輪（静止）
    W.ring(guard, (0, 0, -4.15), 2.4, 14, (0, 0.26, 0.55), "chrome", axis="z", uv_scale=10)
    W.ring(guard, (0, 0, -4.15), 2.4, 4, (0.36, 0.4, 0.66), "glow_day", axis="z", phase=45,
           styles=["glow_day", "glow_day", "glow_night", "glow_night"], uv_scale=16)  # 輪の灯り
    # 冷却フィン: 刃の軸まわりに回る六枚の放熱板（ねじれた羽根。先が昼と夜に交互に光る）
    fins = W.spin(m, guard, "fins", (0, 0, -4.15))
    for k in range(6):
        a = k * 60.0
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        W.rbox(fins, (ca * 1.5, sa * 1.5, -4.15), (1.25, 0.26, 1.2), "fin", rot=(30, 0, -a),
               uv_scale=10)
        W.rbox(fins, (ca * 2.08, sa * 2.08, -4.15), (0.28, 0.2, 0.62),
               "glow_day" if k % 2 else "glow_night", rot=(30, 0, -a), uv_scale=16)
    W.octa(fins, (0, 0, -4.15), 1.5, 1.1, "frame", uv_scale=10)          # フィンの軸
    W.ring(fins, (0, 0, -4.15), 1.05, 8, (0, 0.16, 0.2), "glow_soft", axis="z", uv_scale=12)

    # =====================================================================
    #  form_2_blade — 反りのある片刃（-Y が刃）
    # =====================================================================
    blade = W.form(m, root, 2, "blade", (0, 0, Z0))
    ts = np.linspace(0.0, 1.0, N_SEG + 1)
    for i in range(N_SEG):
        t0, t1 = ts[i], ts[i + 1]
        tm = (t0 + t1) / 2
        p0, p1 = centre(t0), centre(t1)
        n0, n1 = spine_dir(t0), spine_dir(t1)
        w = width(tm)
        last = i == N_SEG - 1
        if not last:
            # 鋼（液体金属の波打つ照り）
            W.beam(blade, p0, p1, THICK, w - 0.5, "liquid", extend=0.12, uv_scale=6)
            # 峰の鏡面の帯（+Y）と、光る刃（-Y）
            W.beam(blade, p0 + n0 * (w / 2 - 0.2), p1 + n1 * (w / 2 - 0.2), THICK + 0.08, 0.42,
                   "spine", extend=0.12, uv_scale=8)
            W.beam(blade, p0 - n0 * (w / 2 - 0.05), p1 - n1 * (w / 2 - 0.05), THICK * 0.7, 0.5,
                   "edge", extend=0.12, uv_scale=8)
            if i < N_SEG - 2:
                # 樋（峰寄りの暗い溝）とその芯の光、刃寄りの細い彫りの溝
                W.beam(blade, p0 + n0 * (w * 0.18), p1 + n1 * (w * 0.18), THICK + 0.1, 0.36,
                       "dark", extend=0.12, uv_scale=8)
                W.beam(blade, p0 + n0 * (w * 0.18), p1 + n1 * (w * 0.18), THICK + 0.14, 0.16,
                       "energy", extend=0.0, uv_scale=8)
                W.beam(blade, p0 - n0 * (w * 0.17), p1 - n1 * (w * 0.17), THICK + 0.06, 0.18,
                       "dark", extend=0.04, uv_scale=10)
            if 1 <= i <= 4:
                # 峰の帯に象嵌した夜側の光の筋
                W.beam(blade, p0 + n0 * (w / 2 - 0.2), p1 + n1 * (w / 2 - 0.2), THICK + 0.14, 0.16,
                       "glow_night", extend=-0.3, uv_scale=10)
        else:
            # 切先: 刃が峰へ反り上がる三角（峰の線の延長が頂点）
            tip = centre(1.0) + spine_dir(1.0) * (w / 2) + np.array([0, 0, -0.6])
            sp = p0 + n0 * (w / 2 - 0.1)
            ed = p0 - n0 * (w / 2 - 0.25)
            W.fill_tri_yz(blade, tuple(tip), tuple(sp), tuple(ed), THICK, 0.55, "liquid_flat",
                          uv_scale=6)
            W.beam(blade, ed - n0 * 0.2, tip, THICK * 0.7, 0.42, "edge", extend=0.2, uv_scale=8)
            W.beam(blade, sp, tip, THICK + 0.08, 0.32, "spine", extend=0.2, uv_scale=8)
            # 横手（切先の付け根を横切る鏡面の稜）
            W.beam(blade, p0 - n0 * (w / 2 - 0.3), p0 + n0 * (w / 2 - 0.25), THICK + 0.06, 0.16,
                   "spine", uv_scale=10)
    # 平を横切る波紋の筋（液体金属の波。刃から峰へ斜めに、先へ行くほど細かく）
    for t in (0.14, 0.3, 0.46, 0.62, 0.76):
        c = centre(t)
        n = spine_dir(t)
        w = width(t)
        a = c - n * (w / 2 - 0.45) + np.array([0, 0, 0.5])
        b = c + n * (w / 2 - 0.55) + np.array([0, 0, -0.7])
        W.beam(blade, a, b, THICK + 0.06, 0.16, "ripple", uv_scale=10)
    # 峰の三つの小さな放射口（暗い台 + 夜側の光）
    for t in (0.32, 0.5, 0.68):
        c = centre(t)
        n = spine_dir(t)
        d = centre(t + 0.02) - centre(t - 0.02)
        d = d / np.linalg.norm(d)
        a = c + n * (width(t) / 2 + 0.12)
        W.beam(blade, a - d * 0.4, a + d * 0.4, THICK * 0.7, 0.3, "frame", uv_scale=14)
        W.beam(blade, a + n * 0.18 - d * 0.22, a + n * 0.18 + d * 0.22, THICK * 0.45, 0.16,
               "glow_night", uv_scale=16)
    # 峰の根元の三つの歯（液体金属が固まった鋸）
    for t in (0.05, 0.1, 0.15):
        c = centre(t) + spine_dir(t) * (width(t) / 2 + 0.05)
        W.rbox(blade, tuple(c), (THICK * 0.6, 0.42, 0.42), "chrome", rot=(45, 0, 0), uv_scale=14)
    # 刃元: 液体金属が鍔から流れ出す鏡面の段と、ハバキ（鏡面の襟・暗い帯・両面の目釘）
    for s in (-1, 1):
        W.beam(blade, (s * 0.2, 0.9, -5.2), (s * 0.2, 1.1, -7.6), 0.5, 0.9, "chrome", uv_scale=8)
    W.chamfer(blade, (0, 0.05, -5.75), (THICK + 0.42, W0 + 0.3, 0.9), "chrome", cut=0.24, axis="z",
              uv_scale=10)
    W.cbox(blade, (0, 0.05, -6.28), (THICK + 0.5, W0 + 0.1, 0.24), "frame", uv_scale=12)
    for sx in (-1, 1):
        for y in (-0.7, 0.7):
            W.cbox(blade, (sx * (THICK / 2 + 0.26), y + 0.05, -5.75), (0.16, 0.26, 0.26), "rivet",
                   uv_scale=16)
    # 刃寄りの溝に象嵌した光（昼と夜が交互に脈打つ）
    inl = W.glow(m, blade, "inlay", (0, 0, Z0))
    for k, t in enumerate((0.1, 0.26, 0.42, 0.58, 0.72)):
        c = centre(t) - spine_dir(t) * (width(t) * 0.17)
        W.rbox(inl, tuple(c), (THICK + 0.2, 0.3, 0.3), "glow_day" if k % 2 == 0 else "glow_night",
               rot=(45, 0, 0), uv_scale=16)

    # =====================================================================
    #  form_3_wings — 鍔の両脇から刃に沿って前へ流れるヘルメスの小翼（四枚の羽根・付け根の留め具）
    # =====================================================================
    wings = W.form(m, root, 3, "wings", (0, 0, -4.2))
    for s in (-1, 1):
        gl = "glow_day" if s < 0 else "glow_night"
        base = np.array([s * 1.05, 0.9, -4.3])
        W.cbox(wings, tuple(base + np.array([s * 0.08, 0.15, -0.1])), (0.5, 0.7, 0.7), "frame",
               uv_scale=12)
        for k, (tip, st) in enumerate((((s * 2.1, 3.6, -8.4), "plate"),
                                       ((s * 2.3, 2.6, -9.2), "chrome"),
                                       ((s * 2.0, 1.5, -8.6), "plate"),
                                       ((s * 1.75, 0.75, -7.4), "chrome"))):
            W.beam(wings, base + np.array([0, -0.4 * k, 0.1 * k]), tip, 0.26, 0.7 - 0.1 * k, st,
                   uv_scale=10)
        for tip in ((s * 1.6, 2.55, -6.4), (s * 1.55, 1.45, -6.2)):        # 付け根の雨覆
            W.beam(wings, base + np.array([s * 0.05, -0.1, -0.2]), tip, 0.3, 0.85, "chrome2",
                   uv_scale=10)
        W.beam(wings, base + np.array([0, 0.35, 0]), (s * 2.15, 3.95, -8.5), 0.3, 0.16, gl,
               uv_scale=12)
        W.beam(wings, base + np.array([0, -0.15, 0.05]), (s * 2.35, 2.95, -9.25), 0.3, 0.16, gl,
               uv_scale=12)
        for y in (0.75, 1.3):                                               # 留め具のピン
            W.cbox(wings, (s * 1.38, y, -4.35), (0.16, 0.22, 0.22), "rivet", uv_scale=16)
        W.cbox(wings, (s * 2.32, 2.62, -9.25), (0.3, 0.3, 0.3), gl, uv_scale=16)


def build_core(m, root):
    """水星核: クレーターの銀の球（太陽側が橙に光る）を、細い二重の輪の籠が囲む。直径約 6。"""
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    spin = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(spin, (0, 0, 0), 1.75, "globe", uv_scale=16)
    # 太陽側（-X）の灼熱の三日月: 二本の弧が球の片側を抱く
    sun = W.glow(m, globe, "sun", (0, 0, 0))
    W.ring(sun, (0, 0, 0), 1.95, 7, (0, 0.24, 0.46), "sun", axis="z", a0=35, a1=145,
           uv_scale=12)
    W.ring(sun, (0, 0, 0), 1.95, 7, (0, 0.24, 0.46), "sun", axis="y", a0=40, a1=140,
           uv_scale=12)
    # 夜側（+X）の細い冷光
    W.ring(sun, (0, 0, 0), 1.9, 3, (0, 0.14, 0.2), "glow_soft", axis="z", a0=-120, a1=-60,
           uv_scale=12)
    # 籠: 上下の極の留め具（静止）
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    for s in (-1, 1):
        W.octa(cage, (0, s * 3.0, 0), 1.2, 0.5, "chrome", axis="y", uv_scale=12)
        W.octa(cage, (0, s * 3.35, 0), 0.6, 0.4, "frame", axis="y", uv_scale=12)
        W.cbox(cage, (0, s * 3.7, 0), (0.36, 0.5, 0.36), "gem", rotation=(0, 45, 0), uv_scale=14)
        W.beam(cage, (0, s * 2.75, 0), (0, s * 2.05, 0), 0.22, 0.22, "glow", uv_scale=14)
        W.octa(cage, (0, s * 2.62, 0), 0.62, 0.24, "frame", axis="y", uv_scale=14)  # 極の締め輪
    # 二重の輪: 縦の輪 A（極を通る）と、傾いた輪 B（首を振って回る）。輪 A には液体金属の滴が乗る
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    ra = W.spin(m, rings, "ring_a", (0, 0, 0))
    W.ring(ra, (0, 0, 0), 2.75, 12, (0, 0.24, 0.32), "chrome", axis="x",
           styles=["chrome", "chrome", "glow"], uv_scale=10)
    for a in (90, 270):
        t = math.radians(a)
        W.octa(ra, (0, 2.75 * math.cos(t), -2.75 * math.sin(t)), 0.85, 0.85, "drop", axis="z",
               uv_scale=14)
    rb = W.spin(m, rings, "ring_b", (0, 0, 0), rotation=(22, 0, -12))
    W.ring(rb, (0, 0, 0), 2.35, 10, (0, 0.2, 0.26), "silver", axis="y",
           styles=["silver", "silver", "glow_day"], uv_scale=10)
    for a in (60, 240):                      # 輪 B に乗る小さな滴（角を落とした 2 個）
        t = math.radians(a)
        c = (-2.35 * math.sin(t), 0, -2.35 * math.cos(t))
        W.cbox(rb, c, (0.6, 0.6, 0.6), "drop", uv_scale=16)
        W.rbox(rb, c, (0.52, 0.52, 0.52), "drop", rot=(45, 45, 0), uv_scale=16)


# ---------------------------------------------------------------------------
#  塗り
# ---------------------------------------------------------------------------
def _common(key):
    return dict(
        chrome={"kind": "chrome", "base": (214, 224, 238), "light": (255, 255, 255),
                "line": (50, 58, 78)},
        chrome2={"kind": "chrome", "base": (160, 172, 192), "light": (236, 242, 252),
                 "line": (40, 46, 62)},
        drop=W.globe_style("mercury", emit=110, halo=NIGHT),
        glow_day={"kind": "glowline", "glow": DAY, "light": (255, 238, 204), "bevel": False,
                  "outline": False},
        glow_night={"kind": "glowline", "glow": NIGHT, "light": (222, 252, 255), "bevel": False,
                    "outline": False},
        frame={"kind": "frame", "base": (44, 50, 66), "light": (100, 110, 132),
               "line": (16, 18, 26)},
        gem={"glow": NIGHT, "deep": (18, 70, 104)},
    )


def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        # 液体金属の刃: 鏡面に波打つ照りの境（刃文）と斜めの映り込み
        liquid={"kind": "blade", "all_faces": True, "base": (214, 226, 242),
                "light": (255, 255, 255), "dark": (150, 164, 190), "line": (50, 60, 82),
                "glint_period": 16, "fuller": False, "hamon": (236, 250, 255)},
        liquid_flat={"kind": "blade", "base": (210, 222, 240), "light": (252, 254, 255),
                     "dark": (150, 164, 190), "outline": False, "bevel": False,
                     "fuller": False, "hamon_off": True, "glint_period": 9999},
        spine={"kind": "chrome", "base": (226, 234, 246), "light": (255, 255, 255),
               "line": (60, 70, 90)},
        edge={"glow": EDGE, "sat": 0.45, "emit": 30},
        energy={"glow": EDGE, "light": (240, 255, 255)},
        ripple={"kind": "glowline", "glow": mix(EDGE, (255, 255, 255), 0.3),
                "light": (255, 255, 255), "emit": 120, "bevel": False, "outline": False},
        dark={"base": (16, 22, 36), "glow": EDGE, "line": (6, 8, 14)},
        wrap={"base": (20, 24, 36), "strap": (150, 162, 184), "skin": (40, 46, 62)},
        fin={"kind": "chrome", "base": (190, 202, 222), "light": (250, 252, 255),
             "line": (40, 46, 62)},
        plate={"kind": "armor", "base": (222, 230, 242), "light": (255, 255, 255),
               "dark": (132, 144, 166), "line": (60, 70, 92), "panel": 0, "sheen": False},
        **_common(key),
    )


def CORE_STYLES(key):
    return core_styles(
        key,
        # 銀のクレーターの球（月の模様を銀に）。太陽側の弧は橙に全発光
        globe=W.globe_style("luna", emit=150, halo=(255, 190, 120), shade=0.25),
        sun={"kind": "glowline", "glow": DAY, "light": (255, 240, 210), "bevel": False,
             "outline": False},
        silver={"kind": "trim", "base": (200, 208, 224), "light": (252, 254, 255),
                "dark": (120, 128, 148), "line": (56, 60, 76)},
        **_common(key),
    )


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）
#    v.astro_sw 攻撃の振り 0→1 / v.astro_fp 一人称で 1 / v.astro_usew 右クリック中 0→1
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_fins": {"rotation": [0, 0, "q.anim_time * 240.0"]},
        "fx_spin_orbit": {"rotation": [0, 0, "-q.anim_time * 180.0"]},
        "fx_glow_drop": W.pulse_expr(180, 0.06),
        "fx_glow_inlay": W.pulse_expr(240, 0.08),
    },
    "swing": {
        # 振るとフィンが一気に回って熱を吐き、柄頭の滴が一周する
        "fx_spin_fins": {"rotation": [0, 0, "v.astro_sw * 720.0"]},
        "fx_spin_orbit": {"rotation": [0, 0, "-v.astro_sw * 360.0"]},
    },
    "form_axes": {"form_2_blade": "z", "form_3_wings": "z"},
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": W.spin_expr("y", 30),
        "fx_glow_sun": W.pulse_expr(120, 0.05),
        "fx_spin_ring_a": W.spin_expr("y", 90),
        "fx_spin_ring_b": W.spin_expr("y", -150),
    },
}
