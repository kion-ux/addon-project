# -*- coding: utf-8 -*-
"""超次元バトルアーツ — 生成スクリプト共通の定数とジオメトリ補助。

座標系（武器空間）: 原点 = 握りの中心、-Z = 刃の向く前方、+Y = 上、16 単位 = 1 ブロック。
"""
from __future__ import annotations

import json
import math
import os
import sys
from typing import Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)

from mcmodel import Cube  # noqa: E402

NS = "hd"
BP = os.path.join(ROOT, "packs", "hyperdim_BP")
RP = os.path.join(ROOT, "packs", "hyperdim_RP")
SCRATCH = os.environ.get("HD_SCRATCH", os.path.join(ROOT, "build_preview"))

# 属性ごとの発光色。武器・パーティクル・HUD・スクリプトの全てがここを参照する
ELEMENTS = {
    "azure":   {"glow": (70, 176, 255),  "light": (200, 236, 255), "deep": (18, 52, 140)},
    "emerald": {"glow": (64, 255, 160),  "light": (206, 255, 228), "deep": (10, 96, 64)},
    "crimson": {"glow": (255, 86, 40),   "light": (255, 214, 150), "deep": (130, 14, 10)},
    "violet":  {"glow": (178, 92, 255),  "light": (234, 208, 255), "deep": (52, 16, 104)},
    "gold":    {"glow": (255, 214, 92),  "light": (255, 248, 214), "deep": (150, 92, 10)},
    "cyan":    {"glow": (130, 244, 255), "light": (232, 252, 255), "deep": (28, 110, 150)},
    "magenta": {"glow": (255, 78, 178),  "light": (255, 214, 238), "deep": (120, 10, 72)},
    "amber":   {"glow": (255, 156, 36),  "light": (255, 230, 170), "deep": (120, 52, 6)},
}

# 武器キー -> (日本語名, 英語名, 属性)
WEAPONS = {
    "greatsword": ("次元断剣 ディメンション・ブレイカー", "Dimension Breaker", "azure"),
    "twinblades": ("疾風双刃 ゼファー＆ガスト", "Zephyr & Gust", "emerald"),
    "greataxe":   ("紅蓮戦斧 ヴォルカニクス", "Volcanix", "crimson"),
    "dagger":     ("影刃 ノクス", "Nox", "violet"),
    "bow":        ("聖光弓 アストライア", "Astraea", "gold"),
    "shield":     ("氷晶盾 グレイシャル・イージス", "Glacial Aegis", "cyan"),
    "whip":       ("薔薇鞭 ローゼンケッテ", "Rosenkette", "magenta"),
    "claws":      ("獣王爪 ベヒモス", "Behemoth Fangs", "amber"),
}


def write_json(path: str, doc) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ---------------------------------------------------------------------------
#  ジオメトリ補助
# ---------------------------------------------------------------------------
def box(bone, origin, size, style, **kw) -> Cube:
    return bone.add(Cube(origin, size, style, **kw))


def cbox(bone, centre, size, style, **kw) -> Cube:
    """中心と大きさで置く箱。回転はその中心まわり。"""
    o = [centre[i] - size[i] / 2 for i in range(3)]
    if kw.get("rotation") and "pivot" not in kw:
        kw["pivot"] = [round(c, 3) for c in centre]
    return bone.add(Cube(o, size, style, **kw))


def beam(bone, p0: Sequence[float], p1: Sequence[float], w: float, h: float,
         style: str, roll: float = 0.0, extend: float = 0.0, **kw) -> Cube:
    """p0 から p1 へ伸びる角柱。局所 Z を線分に合わせ、局所 X 幅 w・Y 高さ h。

    Bedrock の回転は X/Y が右手系に対して符号反転しており、XYZ の順で合成される
    （tools/preview.py の rot_matrix と同じ規約）。局所 -Z を方向 d に向けるには
    d = (-sin b, sin a cos b, -cos a cos b), a = -rx, b = -ry を解けばよい。
    """
    dx, dy, dz = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    length = math.sqrt(dx * dx + dy * dy + dz * dz) + extend
    if length < 1e-6:
        raise ValueError("zero-length beam")
    ux, uy, uz = dx / (length - extend), dy / (length - extend), dz / (length - extend)
    b = math.asin(max(-1.0, min(1.0, -ux)))
    a = math.atan2(uy, -uz)
    rx, ry = -math.degrees(a), -math.degrees(b)
    centre = [(p0[i] + p1[i]) / 2 for i in range(3)]
    rot = [round(rx, 2), round(ry, 2), round(roll, 2)]
    if not any(abs(r) > 1e-3 for r in rot):
        return cbox(bone, centre, (w, h, length), style, **kw)
    return cbox(bone, centre, (w, h, length), style, rotation=rot, **kw)


def polyline(bone, pts, widths, heights, style, roll=0.0, overlap=0.25, **kw):
    """点列に沿って角柱を繋げる。幅・高さは点ごとに補間（先細り）。"""
    n = len(pts) - 1
    out = []
    for i in range(n):
        w = widths[i] if isinstance(widths, (list, tuple)) else widths
        h = heights[i] if isinstance(heights, (list, tuple)) else heights
        r = roll[i] if isinstance(roll, (list, tuple)) else roll
        out.append(beam(bone, pts[i], pts[i + 1], w, h, style, roll=r,
                        extend=overlap, **kw))
    return out


def lerp(a, b, t):
    return a + (b - a) * t


def arc_points(centre, radius, a0, a1, n, plane="yz", z=0.0):
    """平面内の円弧。plane='yz' は (x 固定, y=r sin, z=-r cos)。角度は度。"""
    pts = []
    for i in range(n + 1):
        t = math.radians(lerp(a0, a1, i / n))
        if plane == "yz":
            pts.append((centre[0], centre[1] + radius * math.sin(t),
                        centre[2] - radius * math.cos(t)))
        elif plane == "xy":
            pts.append((centre[0] + radius * math.cos(t),
                        centre[1] + radius * math.sin(t), centre[2]))
        else:  # xz
            pts.append((centre[0] + radius * math.sin(t), centre[1],
                        centre[2] - radius * math.cos(t)))
    return pts


def fill_tri_yz(bone, apex, base_a, base_b, x_w, layer_h, style, **kw):
    """YZ 平面の三角形（切先など）を、辺 apex-base_a に平行な角柱の重ねで埋める。

    段々の箱よりも、刃先の斜めの輪郭が素直に出る。両辺から呼べば左右対称に埋まる。
    """
    ay, az = apex[1], apex[2]
    py, pz = base_a[1], base_a[2]
    qy, qz = base_b[1], base_b[2]
    ey, ez = py - ay, pz - az                    # 辺ベクトル (apex -> base_a)
    el = math.hypot(ey, ez)
    ny, nz = -ez / el, ey / el                   # 法線
    if (qy - ay) * ny + (qz - az) * nz < 0:      # base_b 側を向かせる
        ny, nz = -ny, -nz
    height = abs((qy - ay) * ny + (qz - az) * nz)
    k = 0
    d = layer_h / 2
    while d < height - 1e-3:
        # 平行線上の点: P(t) = apex + n*d + e*t ; 三角形内にクリップ
        oy, oz = ay + ny * d, az + nz * d
        ts = []
        for (sy, sz), (fy, fz) in (((ay, az), (qy, qz)), ((qy, qz), (py, pz)),
                                   ((py, pz), (ay, az))):
            # 交点: o + e t = s + (f - s) u
            dy, dz = fy - sy, fz - sz
            det = ey * (-dz) - ez * (-dy)
            if abs(det) < 1e-9:
                continue
            rhs_y, rhs_z = sy - oy, sz - oz
            t = (rhs_y * (-dz) - rhs_z * (-dy)) / det
            u = (ey * rhs_z - ez * rhs_y) / det
            if -1e-6 <= u <= 1 + 1e-6:
                ts.append(t)
        if len(ts) >= 2:
            t0, t1 = min(ts), max(ts)
            if (t1 - t0) * el > 0.3:
                p0 = (apex[0], oy + ey * t0, oz + ez * t0)
                p1 = (apex[0], oy + ey * t1, oz + ez * t1)
                beam(bone, p0, p1, x_w, layer_h * 1.08, style, **kw)
        k += 1
        d += layer_h
