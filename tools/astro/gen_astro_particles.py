# -*- coding: utf-8 -*-
"""アストロ・ナノギア — パーティクルのスプライトアトラスと定義（DESIGN.md §4.7）。

  python3 tools/astro/gen_astro_particles.py                  # 生成 + 自己検査
  ASTRO_PREVIEW=1 python3 tools/astro/gen_astro_particles.py  # + build_preview/astro/ にプレビュー

* スプライトは白（濃淡）+ アルファで 1024x1024 のアトラス
  packs/astro_RP/textures/particle/astro_atlas.png に描く（4 倍で描いて縮小）。
* 色はスクリプトが MolangVariableMap で渡す variable.cr / cg / cb で、必ず
  "minecraft:particle_appearance_tinting": {"color": [...]} の中で掛ける。
* 変数は全て `(v.x ?? 既定値)` で受けるので、変数無しで出しても見栄えがする。
* 一覧・変数・既定値の表 tools/astro/PARTICLES.md もここから書き出す（このファイルが唯一の出所）。

確かめたスキーマの事実（Mojang/bedrock-samples の metadata/json_schemas/client/particles と
バニラの resource_pack/particles、Snowstorm / Wintersky の実装）:
* format_version は "1.10.0"。direction_x/y/z・lookat_direction・emitter_transform_xz・flipbook・
  billboard の "direction": {"mode": "custom", "custom_direction": [...]} は全てこの版で使える
  （バニラ shriek.json が 1.10.0 で direction_y + custom）。mode の値は "custom"
  （説明文の "custom_direction" は誤り。エンジンのスキーマの enum は derive_from_velocity / custom）。
* lookat_direction はスプライトの横（size[0]・u）が向きに沿い、向きを軸にカメラへ回る。
* スクリプトの変数（MolangVariableMap）はエミッタの式（num_particles・形状）と粒の式（size・tint）の
  両方から読める。emitter_initialization で作った変数も粒から読める。
* particle_motion_parametric の relative_position は位置を上書きする（形状の offset は効かない）。
* 回転速度（rotation_rate）と初速は particle_motion_dynamic がある時だけ積分される（バニラも必ず併記）。
* tinting の color は 4 要素（RGBA）の配列か "#RRGGBB" 文字列。
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import astro_data as AD  # noqa: E402

NS = AD.NS
RP = os.path.join(ROOT, "packs", "astro_RP")
PART_DIR = os.path.join(RP, "particles")
TEX = "textures/particle/astro_atlas"
ATLAS_PNG = os.path.join(RP, TEX + ".png")
DOC_MD = os.path.join(HERE, "PARTICLES.md")
SCRATCH = os.environ.get("ASTRO_SCRATCH", os.path.join(ROOT, "build_preview", "astro"))
AW = AH = 1024
SS = 4                       # スーパーサンプリング倍率
FORMAT_VERSION = "1.10.0"
F32 = np.float32


# ===========================================================================
#  スプライトの道具（全て白の濃淡 + アルファ。float 配列 [h, w] で 0..1）
# ===========================================================================
def grid(w, h, ss=SS):
    """等方な座標。短辺の半分 = 1（中心が原点、y は下向き）。"""
    ys, xs = np.mgrid[0:h * ss, 0:w * ss].astype(F32)
    s = min(w, h) / 2.0
    return ((xs + 0.5) / ss - w / 2.0) / s, ((ys + 0.5) / ss - h / 2.0) / s


def ngrid(w, h, ss=SS):
    """縦横それぞれ [-1, 1] に正規化した座標（細長いスプライト用）。"""
    ys, xs = np.mgrid[0:h * ss, 0:w * ss].astype(F32)
    return (xs + 0.5) / (w * ss) * 2 - 1, (ys + 0.5) / (h * ss) * 2 - 1


def down(a, ss=SS):
    h, w = a.shape[0] // ss, a.shape[1] // ss
    return a.reshape(h, ss, w, ss).mean(axis=(1, 3)).astype(F32)


def sat(x):
    return np.clip(x, 0.0, 1.0)


def hard(cond):
    return cond.astype(F32)


def blur(a, radius):
    img = Image.fromarray((sat(a) * 255 + 0.5).astype(np.uint8), "L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), F32) / 255


def halo(a, radius, k):
    return sat(np.maximum(a, blur(a, radius) * k))


def polar(c, r, deg):
    a = math.radians(deg)
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


class Pen:
    """SS 倍の L 画像に描くペン。座標は出力ピクセル（左上原点、浮動小数、y 下向き）。"""

    def __init__(self, w, h, ss=SS):
        self.w, self.h, self.ss = w, h, ss
        self.img = Image.new("L", (w * ss, h * ss), 0)
        self.d = ImageDraw.Draw(self.img)

    def _p(self, p):
        return (p[0] * self.ss, p[1] * self.ss)

    def _w(self, width):
        return max(1, int(round(width * self.ss)))

    def dot(self, c, r, fill=255):
        s = self.ss
        self.d.ellipse([(c[0] - r) * s, (c[1] - r) * s, (c[0] + r) * s, (c[1] + r) * s], fill=fill)

    def line(self, a, b, width, fill=255, cap=True):
        self.d.line([self._p(a), self._p(b)], fill=fill, width=self._w(width))
        if cap:
            self.dot(a, width / 2, fill)
            self.dot(b, width / 2, fill)

    def poly(self, pts, width, fill=255, closed=False, cap=True):
        pts = list(pts)
        if closed:
            pts = pts + [pts[0]]
        for i in range(len(pts) - 1):
            self.d.line([self._p(pts[i]), self._p(pts[i + 1])], fill=fill, width=self._w(width))
        if cap:
            for p in pts:
                self.dot(p, width / 2, fill)

    def polygon(self, pts, fill=255):
        self.d.polygon([self._p(p) for p in pts], fill=fill)

    def ring(self, c, r, width, fill=255):
        s, R = self.ss, r + width / 2
        self.d.ellipse([(c[0] - R) * s, (c[1] - R) * s, (c[0] + R) * s, (c[1] + R) * s],
                       outline=fill, width=self._w(width))

    def arc(self, c, r, a0, a1, width, fill=255):
        s, R = self.ss, r + width / 2
        self.d.arc([(c[0] - R) * s, (c[1] - R) * s, (c[0] + R) * s, (c[1] + R) * s], a0, a1,
                   fill=fill, width=self._w(width))

    def alpha(self):
        return np.asarray(self.img.resize((self.w, self.h), Image.BOX), F32) / 255


def glyph_strokes(rng):
    """小さな機械文字（2 列 × 3 行の格子の辺から 2〜4 本）。[(x0,y0,x1,y1)] 0..1。"""
    edges = []
    for yy in (0, 0.5, 1):
        edges.append((0, yy, 0.5, yy))
        edges.append((0.5, yy, 1, yy))
    for xx in (0, 0.5, 1):
        edges.append((xx, 0, xx, 0.5))
        edges.append((xx, 0.5, xx, 1))
    n = rng.randint(2, 5)
    pick = [edges[i] for i in rng.choice(len(edges), n, replace=False)]
    if not any(e[0] == e[2] for e in pick):
        pick.append(edges[6 + rng.randint(0, 6)])
    return pick


def glyph_ring(pen, c, r, hh, count, seed, width, skip=(), gap=0.55):
    """円周に沿って並ぶ機械文字の帯。skip の位置には小さな三角を置く。"""
    rng = np.random.RandomState(seed)
    step = 360.0 / count
    ww = 2 * math.pi * r / count * gap               # 1 文字の幅（接線方向）
    for j in range(count):
        a = j * step
        if j in skip:
            pen.polygon([polar(c, r + hh * 0.5, a - step * 0.22), polar(c, r + hh * 0.5, a + step * 0.22),
                         polar(c, r - hh * 0.45, a)])
            continue
        for x0, y0, x1, y1 in glyph_strokes(rng):
            def P(gx, gy):
                aa = a + math.degrees((gx - 0.5) * ww / r)
                return polar(c, r + (0.5 - gy) * hh, aa)
            pen.line(P(x0, y0), P(x1, y1), width)


def glyph_line(pen, p0, p1, hh, count, seed, width, gap=0.6):
    """直線に沿って並ぶ機械文字（六角陣の辺用）。p0→p1 が文字の並び、法線が文字の上。"""
    rng = np.random.RandomState(seed)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    cell = L / count
    for j in range(count):
        cx0 = j * cell + cell * (1 - gap) / 2
        for x0, y0, x1, y1 in glyph_strokes(rng):
            def P(gx, gy):
                t = cx0 + gx * cell * gap
                h = (gy - 0.5) * hh
                return (p0[0] + ux * t + nx * h, p0[1] + uy * t + ny * h)
            pen.line(P(x0, y0), P(x1, y1), width)


def hexagon(c, r, rot=0.0):
    return [polar(c, r, rot + k * 60) for k in range(6)]


def hex_dist(x, y):
    """頂点が 0°,60°… の六角形の内接距離（辺までの距離）。"""
    return np.maximum(np.abs(y), np.abs(x) * 0.8660254 + np.abs(y) * 0.5)


# ===========================================================================
#  スプライト
#  戻り値: alpha か (alpha, white)。white は白の濃淡（加算では明るさ、blend では陰影）
# ===========================================================================
def sp_glow(w, h):
    x, y = grid(w, h)
    r = np.hypot(x, y)
    core = sat((0.24 - r) / 0.05)
    hal = sat(1 - r) ** 2.3 * 0.8
    return down(np.maximum(core, hal))


def sp_dot(w, h):
    x, y = grid(w, h)
    r = np.hypot(x, y)
    return down(np.maximum(hard(r < 0.46), sat(1 - r) ** 3 * 0.55))


def sp_star(w, h):
    """アニメ調の四芒のきらめき（細い光条 + 斜めの短い光条 + 芯）。"""
    x, y = grid(w, h)
    ax, ay = np.abs(x), np.abs(y)

    def spike(along, across, L, W):
        t = sat(1 - along / L)
        return hard(across < W * t ** 1.9) * hard(along < L)

    s2 = math.sqrt(2)
    a = np.maximum(spike(ax, ay, 0.98, 0.17), spike(ay, ax, 0.98, 0.17))
    a = np.maximum(a, spike(np.abs(x + y) / s2, np.abs(x - y) / s2, 0.52, 0.08))
    a = np.maximum(a, spike(np.abs(x - y) / s2, np.abs(x + y) / s2, 0.52, 0.08))
    r = np.hypot(x, y)
    a = np.maximum(a, np.maximum(hard(r < 0.13), sat(1 - r / 0.75) ** 2 * 0.45))
    return down(a)


def sp_spark(w, h):
    """横に細長い火花の筋（lookat_direction で速度の向きに沿う。左右対称）。"""
    x, y = ngrid(w, h)
    hw = 0.55 * sat(1 - x * x) ** 1.4
    body = hard(np.abs(y) < hw)
    core = hard(np.abs(y) < hw * 0.45) * hard(np.abs(x) < 0.75)
    hal = sat(1 - np.abs(y)) ** 2 * sat(1 - x * x) ** 2 * 0.35
    return down(np.maximum(body, hal)), down(0.72 + 0.28 * np.maximum(core, 1 - body))


def sp_speedline(w, h):
    x, y = ngrid(w, h)
    hw = 0.42 * sat(1 - np.abs(x) ** 1.6) ** 1.3
    body = hard(np.abs(y) < hw)
    hal = sat(1 - np.abs(y)) ** 2 * sat(1 - np.abs(x)) * 0.25
    return down(np.maximum(body, hal))


def sp_impact(w, h):
    """打撃の閃光: 長短の鋭い棘の星形 + 白い芯 + 内側の小さな星。"""
    pen = Pen(w, h)
    c, R = (w / 2, h / 2), w / 2 - 1
    rng = np.random.RandomState(5)
    n = 16
    for layer, (lo, hi, inner, rot) in enumerate(((0.60, 0.98, 0.20, 0.0), (0.32, 0.50, 0.12, 0.5))):
        pts = []
        for i in range(2 * n):
            ang = (i + rot) / (2 * n) * 360 + rng.uniform(-3, 3)
            rr = rng.uniform(lo, hi) if i % 2 == 0 else inner * rng.uniform(0.9, 1.15)
            pts.append(polar(c, R * rr, ang))
        pen.polygon(pts, 255 if layer == 0 else 255)
    a = pen.alpha()
    x, y = grid(w, h, 1)
    r = np.hypot(x, y)
    a = np.maximum(a, sat((0.22 - r) / 0.04))
    white = 0.78 + 0.22 * sat((0.55 - r) / 0.25)
    return halo(a, w / 40, 0.45), white


def sp_flare(w, h):
    """アナモルフィックな横一文字の閃光。"""
    x, y = ngrid(w, h)
    ax = np.abs(x)
    line = np.exp(-(y / (0.035 + 0.09 * (1 - ax) ** 2)) ** 2) * sat(1 - ax) ** 0.7
    glow = np.exp(-(x * x * 22 + y * y * 1.8))
    core = hard((x * 9) ** 2 + (y * 1.1) ** 2 < 0.16)
    a = np.maximum(np.maximum(line, glow * 0.85), core)
    return down(a)


def sp_ring(w, h):
    x, y = grid(w, h)
    r = np.hypot(x, y)
    band = hard(np.abs(r - 0.86) < 0.04)
    inner = sat((r - 0.5) / 0.36) ** 3 * 0.3 * hard(r < 0.86)
    outer = sat(1 - (r - 0.9) / 0.09) * 0.35 * hard(r > 0.86)
    return down(np.maximum(band, np.maximum(inner, outer)))


def sp_shock(w, h):
    """衝撃波の太い輪: 外縁がくっきり白く、内側へ筋の入ったグラデーションで消える。"""
    x, y = grid(w, h)
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    rim = hard((r > 0.87) & (r < 0.955))
    streak = 0.78 + 0.22 * np.cos(th * 26 + np.sin(th * 7) * 3) * np.cos(th * 11)
    body = sat((r - 0.36) / 0.51) ** 2.2 * hard(r <= 0.87) * streak
    a = np.maximum(rim, body * 0.85)
    white = 0.78 + 0.22 * rim
    return down(a), down(white)


def sp_circle(w, h):
    """技術の陣: 目盛りの帯・点線の輪・機械文字の帯・三重の弧・三角・十字の照準・節点。"""
    pen = Pen(w, h)
    c, R = (w / 2, h / 2), w / 2 - 2
    lw = R * 0.0085
    pen.ring(c, R * 0.97, R * 0.02)
    for i in range(120):
        a = i * 3.0
        long_ = i % 5 == 0
        pen.line(polar(c, R * (0.865 if long_ else 0.9), a), polar(c, R * 0.94, a),
                 R * (0.013 if long_ else 0.0075), cap=False)
    pen.ring(c, R * 0.85, lw)
    for i in range(36):
        pen.arc(c, R * 0.805, i * 10 + 1, i * 10 + 7, R * 0.024)
    glyph_ring(pen, c, R * 0.715, R * 0.07, count=40, seed=3, width=R * 0.0115, skip=(0, 10, 20, 30))
    pen.ring(c, R * 0.64, R * 0.016)
    for k in range(8):
        p = polar(c, R * 0.64, k * 45 + 22.5)
        pen.dot(p, R * 0.03)
        pen.ring(p, R * 0.052, lw)
    for k in range(3):
        pen.arc(c, R * 0.535, k * 120 + 15, k * 120 + 105, R * 0.04)
        pen.arc(c, R * 0.475, k * 120 + 75, k * 120 + 135, R * 0.012)
    pen.ring(c, R * 0.42, lw)
    for rot in (-90, 90):
        pen.poly([polar(c, R * 0.42, rot + k * 120) for k in range(3)], lw * 1.1, closed=True)
    pen.ring(c, R * 0.2, R * 0.014)
    pen.dot(c, R * 0.055)
    for k in range(4):
        pen.line(polar(c, R * 0.24, k * 90), polar(c, R * 0.37, k * 90), R * 0.014)
        pen.line(polar(c, R * 0.26, k * 90 + 45), polar(c, R * 0.31, k * 90 + 45), lw)
    a = pen.alpha()
    return halo(a, w / 110, 0.55)


def sp_hex_circle(w, h):
    """六角の陣: 二重の六角・辺の目盛り・辺に沿う機械文字・内側のハニカム・頂点の節。"""
    pen = Pen(w, h)
    c, R = (w / 2, h / 2), w / 2 - 2
    lw = R * 0.009
    outer = hexagon(c, R * 0.97)
    pen.poly(outer, R * 0.02, closed=True)
    for k in range(6):
        p0, p1 = outer[k], outer[(k + 1) % 6]
        # 辺の内向き法線
        mx, my = (p0[0] + p1[0]) / 2 - c[0], (p0[1] + p1[1]) / 2 - c[1]
        L = math.hypot(mx, my)
        nx, ny = -mx / L, -my / L
        for j in range(1, 16):
            t = j / 16
            px, py = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
            ln = R * (0.07 if j % 4 == 0 else 0.035)
            pen.line((px, py), (px + nx * ln, py + ny * ln), R * (0.012 if j % 4 == 0 else 0.007),
                     cap=False)
    mid = hexagon(c, R * 0.84)
    pen.poly(mid, lw, closed=True)
    for k in range(6):
        p0, p1 = hexagon(c, R * 0.76)[k], hexagon(c, R * 0.76)[(k + 1) % 6]
        q0 = (p0[0] + (p1[0] - p0[0]) * 0.12, p0[1] + (p1[1] - p0[1]) * 0.12)
        q1 = (p0[0] + (p1[0] - p0[0]) * 0.88, p0[1] + (p1[1] - p0[1]) * 0.88)
        glyph_line(pen, q0, q1, R * 0.06, count=7, seed=40 + k, width=R * 0.011)
    inner = hexagon(c, R * 0.66, 30)
    pen.poly(inner, R * 0.014, closed=True)
    for p in outer:
        pen.dot(p, R * 0.035)
    for p in inner:
        pen.dot(p, R * 0.025)
        pen.ring(p, R * 0.045, lw)
    pen.poly(hexagon(c, R * 0.17, 30), R * 0.014, closed=True)
    pen.dot(c, R * 0.045)
    a = pen.alpha()
    # ハニカム（内側の六角に切り抜き、淡く）
    hp = Pen(w, h)
    cell = R * 0.115
    for i in range(-8, 9):
        for j in range(-8, 9):
            cx = c[0] + i * cell * 1.5
            cy = c[1] + (j + (i % 2) * 0.5) * cell * math.sqrt(3)
            hp.poly(hexagon((cx, cy), cell * 0.92), lw * 0.9, closed=True, cap=False)
    x, y = grid(w, h, 1)
    clip = sat((0.6 - hex_dist(y, x) * (w / 2) / R) * 30) * sat(hex_dist(y, x) * (w / 2) / R / 0.2 - 1)
    a = np.maximum(a, hp.alpha() * clip * 0.45)
    return halo(a, w / 110, 0.55)


# ---- 惑星紋章 ---------------------------------------------------------------
def _arcpts(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def emblem_symbol(key):
    """天文記号を元にした紋章の線（座標は [-0.5, 0.5]、y 下向き）。
    戻り値: (polylines, circles, dots)  circles = [(cx, cy, r)] 輪郭、dots = 塗りの円。"""
    L, C, D = [], [], []
    if key == "mercury":                 # ☿ 角（三日月）+ 円 + 十字
        C.append((0, -0.04, 0.19))
        L.append(_arcpts(0, -0.40, 0.17, 15, 165))
        L.append([(0, 0.15), (0, 0.50)])
        L.append([(-0.15, 0.34), (0.15, 0.34)])
    elif key == "venus":                 # ♀
        C.append((0, -0.16, 0.25))
        L.append([(0, 0.09), (0, 0.50)])
        L.append([(-0.17, 0.31), (0.17, 0.31)])
    elif key == "earth":                 # ♁ 円の上に十字
        C.append((0, 0.13, 0.26))
        L.append([(0, -0.13), (0, -0.50)])
        L.append([(-0.16, -0.33), (0.16, -0.33)])
    elif key == "mars":                  # ♂
        C.append((-0.09, 0.09, 0.26))
        s = 0.26 / math.sqrt(2)
        L.append([(-0.09 + s, 0.09 - s), (0.38, -0.38)])
        L.append([(0.12, -0.38), (0.38, -0.38), (0.38, -0.12)])
    elif key == "jupiter":               # ♃
        L.append([(-0.34, -0.28), (-0.24, -0.40), (-0.08, -0.43), (0.04, -0.33), (0.03, -0.17),
                  (-0.10, 0.0), (-0.25, 0.13), (-0.34, 0.19)])
        L.append([(-0.38, 0.19), (0.36, 0.19)])
        L.append([(0.17, -0.44), (0.17, 0.48)])
    elif key == "saturn":                # ♄
        L.append([(-0.18, -0.47), (-0.18, 0.34)])
        L.append([(-0.36, -0.30), (0.02, -0.30)])
        L.append([(-0.18, 0.0), (-0.04, -0.13), (0.12, -0.12), (0.21, 0.02), (0.13, 0.19),
                  (0.08, 0.33), (0.16, 0.45), (0.31, 0.41)])
    elif key == "uranus":                # ⛢ 点のある円 + 上向きの矢
        C.append((0, 0.19, 0.22))
        D.append((0, 0.19, 0.075))
        L.append([(0, -0.03), (0, -0.48)])
        L.append([(-0.15, -0.33), (0, -0.48), (0.15, -0.33)])
    elif key == "neptune":               # ♆ 三叉
        L.append(_arcpts(0, -0.18, 0.31, 0, 180))
        L.append([(-0.31, -0.18), (-0.31, -0.40)])
        L.append([(0.31, -0.18), (0.31, -0.40)])
        L.append([(0, -0.48), (0, 0.48)])
        L.append([(-0.17, 0.30), (0.17, 0.30)])
        L.append([(-0.40, -0.31), (-0.31, -0.43), (-0.22, -0.31)])
        L.append([(0.22, -0.31), (0.31, -0.43), (0.40, -0.31)])
        L.append([(-0.09, -0.37), (0, -0.49), (0.09, -0.37)])
    elif key == "sol":                   # ☉ + 光条
        C.append((0, 0, 0.30))
        D.append((0, 0, 0.085))
        for k in range(8):
            a = math.radians(k * 45 + 22.5)
            L.append([(0.40 * math.cos(a), 0.40 * math.sin(a)), (0.49 * math.cos(a), 0.49 * math.sin(a))])
    else:                                # 汎用: 四芒星と傾いた軌道
        pts = []
        for i in range(8):
            a = math.radians(-90 + i * 45)
            rr = 0.46 if i % 2 == 0 else 0.11
            pts.append((rr * math.cos(a), rr * math.sin(a)))
        L.append(pts + [pts[0]])
        L.append([(0.40 * math.cos(math.radians(t)) * 1.0 - 0.0,
                   0.15 * math.sin(math.radians(t))) for t in range(200, 341, 10)])
    return L, C, D


EMBLEM_KEYS = list(AD.PLANET_KEYS) + ["astro"]      # v.var = order - 1、9 = 汎用（既定）


def sp_emblem(w, h, idx):
    """惑星紋章: 刻みの入った機械の輪 + 惑星番号の灯 + 中央の天文記号。"""
    key = EMBLEM_KEYS[idx]
    pen = Pen(w, h)
    c, R = (w / 2, h / 2), w / 2 - 2
    pen.ring(c, R * 0.965, R * 0.03)
    seg = 40.0
    for k in range(9):                                   # 9 区画の帯（惑星ごとの灯）
        a0 = -90 + k * seg - seg / 2
        pen.arc(c, R * 0.865, a0 + 3.5, a0 + seg - 3.5, R * 0.075)
    for k in range(9):
        a = -90 + k * seg - seg / 2                      # 区画の切れ目に小さな菱形
        p = polar(c, R * 0.865, a)
        pen.polygon([polar(c, R * 0.92, a), polar(p, R * 0.03, a + 90), polar(c, R * 0.81, a),
                     polar(p, R * 0.03, a - 90)])
    pen.ring(c, R * 0.76, R * 0.022)
    for i in range(36):
        a = i * 10
        pen.line(polar(c, R * 0.715, a), polar(c, R * 0.745, a), R * 0.012, cap=False)
    lines, circles, dots = emblem_symbol(key)
    sc, sw = R * 1.12, R * 0.085
    P = lambda p: (c[0] + p[0] * sc, c[1] + p[1] * sc)    # noqa: E731
    for pl in lines:
        pen.poly([P(p) for p in pl], sw)
    for cx, cy, r in circles:
        pen.ring(P((cx, cy)), r * sc - sw / 2, sw)
    for cx, cy, r in dots:
        pen.dot(P((cx, cy)), r * sc)
    a = pen.alpha()
    # 惑星番号の区画を塗りつぶす（他の区画は輪郭だけ = 中を抜く）
    x, y = grid(w, h, 1)
    r = np.hypot(x, y) * (w / 2) / R
    th = (np.degrees(np.arctan2(y, x)) + 90 + seg / 2) % 360
    k = np.floor(th / seg)
    within = hard((r > 0.835) & (r < 0.895)) * hard(((th % seg) > 7) & ((th % seg) < seg - 7))
    lit = hard(k == idx) if idx < 9 else hard(k < 0)
    a = a * (1 - within * (1 - lit) * 0.78)
    white = 0.8 + 0.2 * np.maximum(lit * within, hard(r < 0.7))
    return halo(a, w / 70, 0.45), white


def sp_hex(w, h):
    x, y = grid(w, h)
    d = hex_dist(x, y)
    border = hard((d > 0.74) & (d < 0.87))
    fill = hard(d <= 0.74) * 0.2
    inner = hard(np.abs(d - 0.58) < 0.035) * hard(x + y < -0.15) * 0.65
    a = np.maximum(np.maximum(border, fill), inner)
    return halo(down(a), w / 30, 0.4)


def sp_scan(w, h):
    x, y = ngrid(w, h)
    ay = np.abs(y)
    core = sat(1 - ay / 0.13)
    glow = np.exp(-(y / 0.5) ** 2) * 0.42
    px = (x + 1) / 2 * w
    ticks = hard(np.abs((px % 16) - 8) < 0.6) * hard(ay < 0.5) * 0.75
    dash = hard(np.abs(ay - 0.62) < 0.05) * hard((px % 12) < 7) * 0.5
    end = sat((1 - np.abs(x)) / 0.18)
    return down(np.maximum(np.maximum(core, glow), np.maximum(ticks, dash)) * end)


def sp_beam(w, h):
    """光線の帯（横向き。lookat_direction で size[0] = 長さが向きに沿う）。両端は柔らかく。"""
    x, y = ngrid(w, h)
    ay = np.abs(y)
    core = hard(ay < 0.26)
    body = sat(1 - ay) ** 1.5 * (0.85 + 0.15 * np.cos(y * 26))
    end = sat((1 - np.abs(x)) / 0.07) ** 0.8
    a = np.maximum(core, body * 0.75) * end
    return down(a), down(0.72 + 0.28 * core)


def sp_pillar(w, h):
    """光の柱（縦向き。下端がくっきり、上へ消える）。"""
    x, y = ngrid(w, h)
    ax = np.abs(x)
    core = hard(ax < 0.24)
    body = sat(1 - ax) ** 1.5 * (0.85 + 0.15 * np.cos(x * 22))
    top = sat((y + 1) / 0.7) ** 1.2
    bottom = sat((1 - y) / 0.03)
    a = np.maximum(core, body * 0.75) * top * bottom
    return down(a), down(0.72 + 0.28 * core)


def sp_slash(w, h, thick=0.3, span=210.0, lines=3):
    """三日月の斬撃。弧の中心がスプライトの中心。進む先（時計回りの先端）が太く鋭い。
    外縁に白い芯、内側へ薄くなる胴、後ろへ流れる細い筋。v.rot で振りの向きを変える。"""
    x, y = grid(w, h)
    r = np.hypot(x, y)
    th = np.degrees(np.arctan2(y, x))                  # y 下向き: 時計回りに増える
    start = -90 - span / 2                             # 尾の角度（上から左回りに span/2）
    s = ((th - start) % 360) / span                    # 0 = 尾, 1 = 先端
    valid = hard(s <= 1)
    s = np.clip(s, 0, 1)
    R = 0.93
    prof = sat(np.sin(np.pi * s ** 0.85)) ** 0.75 * (0.35 + 0.65 * s ** 0.6)
    t = thick * prof
    band = valid * hard((r < R) & (r > R - t))
    depth = np.where(t > 1e-4, (R - r) / np.maximum(t, 1e-4), 1)
    a = band * sat(1 - depth) ** 0.55 * (0.45 + 0.55 * s)
    rim = valid * hard(np.abs(r - R + 0.012) < 0.022) * hard(s > 0.08) * sat(prof * 3)
    a = np.maximum(a, rim)
    for i in range(lines):                             # 尾に流れる細い筋
        rr = R - thick * (0.35 + 0.22 * i)
        s0 = 0.08 + 0.12 * i
        ln = valid * hard(np.abs(r - rr) < 0.011) * hard((s > s0) & (s < 0.55 + 0.1 * i))
        a = np.maximum(a, ln * 0.6)
    white = np.maximum(0.7 + 0.3 * (1 - np.clip(depth, 0, 1)) * band, rim)
    return halo(down(a), w / 70, 0.35), down(np.where(a > 0, white, 1.0))


def sp_cross(w, h):
    x, y = grid(w, h)
    a = np.zeros_like(x)
    for s in (1, -1):
        along = np.abs(x + s * y) / math.sqrt(2)
        perp = np.abs(x - s * y) / math.sqrt(2)
        blade = hard(perp < 0.12 * sat(1 - (along / 0.99) ** 2) ** 0.9) * hard(along < 0.99)
        core = hard(perp < 0.035 * sat(1 - (along / 0.85) ** 2)) * hard(along < 0.85)
        a = np.maximum(a, np.maximum(blade * 0.85, core))
    r = np.hypot(x, y)
    a = np.maximum(a, np.maximum(hard(r < 0.13), sat(1 - r / 0.5) ** 2 * 0.6))
    return halo(down(a), w / 50, 0.4)


def sp_thrust(w, h):
    """突きの閃光（横向き、左右対称のレンズ形 + 上下の細い筋）。"""
    x, y = ngrid(w, h)
    ay = np.abs(y)
    hw = 0.62 * sat(1 - x * x) ** 1.5
    body = hard(ay < hw)
    core = hard(ay < hw * 0.3)
    sides = hard(np.abs(ay - 0.78) < 0.055 * sat(1 - (x / 0.75) ** 2)) * hard(np.abs(x) < 0.75)
    a = np.maximum(np.maximum(body * 0.8, core), sides * 0.65)
    return halo(down(a), h / 12, 0.4), down(0.72 + 0.28 * core)


def sp_wind(w, h):
    x, y = ngrid(w, h)
    c = 0.4 * x * x - 0.28
    hw = 0.13 * sat(1 - x * x) ** 1.2
    s1 = hard(np.abs(y - c) < hw)
    s2 = hard(np.abs(y - (c + 0.48)) < hw * 0.7) * hard(np.abs(x) < 0.72)
    return down(np.maximum(s1, s2 * 0.7))


def sp_nano(w, h, k):
    """ナノマシン: 0 四角の枠 / 1 菱形の枠 / 2 十字の記号 / 3 チップ。"""
    x, y = grid(w, h)
    ax, ay = np.abs(x), np.abs(y)
    if k == 0:
        m = np.maximum(ax, ay)
        a = np.maximum(hard((m < 0.62) & (m > 0.4)), hard(m < 0.14))
    elif k == 1:
        m = ax + ay
        a = np.maximum(hard((m < 0.82) & (m > 0.54)), hard(m < 0.18))
    elif k == 2:
        a = np.maximum(hard((ax < 0.12) & (ay < 0.66)), hard((ay < 0.12) & (ax < 0.66)))
        a = np.maximum(a, hard((np.abs(ax - 0.5) < 0.1) & (np.abs(ay - 0.5) < 0.1)))
    else:
        body = hard((ax < 0.4) & (ay < 0.4))
        pins = hard(((ax < 0.62) & (ay < 0.4)) & (np.abs((y + 0.4) % 0.27 - 0.135) < 0.06))
        pins = np.maximum(pins, hard(((ay < 0.62) & (ax < 0.4)) & (np.abs((x + 0.4) % 0.27 - 0.135) < 0.06)))
        a = np.maximum(body, pins)
    r = np.hypot(x, y)
    return halo(down(a), w / 14, 0.45), down(np.where(r < 0.3, 1.0, 0.85))


def sp_smoke(w, h, seed):
    rng = np.random.RandomState(seed)
    x, y = grid(w, h)
    a = np.zeros_like(x)
    lit = np.zeros_like(x)
    for _ in range(8):
        cx, cy, rr = rng.uniform(-0.38, 0.38), rng.uniform(-0.32, 0.38), rng.uniform(0.32, 0.55)
        d = np.hypot(x - cx, y - cy) / rr
        a = np.maximum(a, sat(1 - d) ** 0.9)
        lit = np.maximum(lit, sat(1 - np.hypot(x - cx + 0.12, y - cy + 0.14) / rr))
    a = sat(a * 1.6) * 0.9
    white = 0.55 + 0.45 * sat(lit * 1.5)
    return down(a), down(white)


def sp_cloud(w, h):
    """アニメ調の雲（丸の集まり、底は平ら。上の明るい面と下の影の二色）。"""
    x, y = grid(w, h)
    blobs = [(-0.44, 0.22, 0.36), (0.0, -0.02, 0.5), (0.44, 0.18, 0.4), (-0.18, -0.30, 0.34),
             (0.26, -0.26, 0.31), (0.68, 0.36, 0.24), (-0.70, 0.38, 0.24), (-0.05, 0.32, 0.4)]
    inside = np.zeros_like(x, dtype=bool)
    lit = np.zeros_like(x, dtype=bool)
    for cx, cy, rr in blobs:
        inside |= np.hypot(x - cx, y - cy) < rr
        lit |= np.hypot(x - cx + 0.05, y - cy + 0.11) < rr * 0.93
    inside &= y < 0.6
    a = hard(inside) * 0.95
    white = np.where(lit, 1.0, 0.72)
    return halo(down(a), w / 50, 0.25), down(np.where(inside, white, 1.0))


def sp_debris(w, h, k):
    """岩の破片: ランダムな多角形を面ごとの陰影で塗る（blend 用。輪郭は暗い）。"""
    rng = np.random.RandomState(70 + k)
    n = rng.randint(5, 8)
    c = (w / 2 + rng.uniform(-1, 1), h / 2 + rng.uniform(-1, 1))
    angs = np.sort(rng.uniform(0, 360, n))
    pts = [polar(c, w / 2 * rng.uniform(0.62, 0.9), a) for a in angs]
    ap = Pen(w, h)
    ap.polygon(pts)
    wp = Pen(w, h)
    hub = (c[0] + rng.uniform(-3, 3), c[1] + rng.uniform(-3, 3))
    for i in range(n):
        p0, p1 = pts[i], pts[(i + 1) % n]
        mx, my = (p0[0] + p1[0]) / 2 - hub[0], (p0[1] + p1[1]) / 2 - hub[1]
        L = math.hypot(mx, my) + 1e-6
        light = (-mx - my) / (L * math.sqrt(2))          # 左上から光
        wp.polygon([hub, p0, p1], int(255 * (0.62 + 0.33 * light)))
    a = ap.alpha()
    white = wp.alpha() / np.maximum(a, 1e-3)
    edge = sat(a - np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)),
                              F32) / 255)
    white = np.clip(white * (1 - edge * 0.5), 0, 1)
    return a, white


def sp_flame(w, h, f, n=8):
    """アニメ調の炎の舌（8 コマ）。外炎は白 0.75、内炎は 1.0。後半のコマは千切れて縮む。"""
    x, y = grid(w, h)
    yy = -y                                            # 上向き
    t = f / n
    hgt = 1.0 - 0.45 * t
    hh = (yy + 0.92) / (1.85 * hgt)                     # 0 = 根元, 1 = 先
    phase = t * 2 * math.pi
    wob = 0.14 * np.sin(hh * 5.5 + phase) * hh
    width = 0.62 * np.sqrt(np.clip(hh, 0, 1)) * np.clip(1 - hh, 0, 1) ** 0.85 * (1 - 0.3 * t)
    body = hard(np.abs(x - wob) < width) * hard((hh > 0) & (hh < 1))
    # 両脇の小さな舌
    for sx, sh, ph in ((-0.36, 0.55, 1.3), (0.34, 0.62, 2.4)):
        h2 = (yy + 0.75) / (1.85 * hgt * sh)
        w2 = 0.24 * np.sqrt(np.clip(h2, 0, 1)) * np.clip(1 - h2, 0, 1) ** 0.9
        body = np.maximum(body, hard(np.abs(x - sx - 0.08 * np.sin(h2 * 5 + phase + ph) * h2) < w2) *
                          hard((h2 > 0) & (h2 < 1)))
    core_w = width * 0.42
    core = hard(np.abs(x - wob * 0.8) < core_w) * hard((hh > 0.02) & (hh < 0.62))
    if t > 0.6:                                         # 千切れる: 上の部分が離れる
        body = body * hard(np.abs(hh - 0.62) > 0.05 * (t - 0.5) * 6)
    a = body * (1 - 0.35 * t)
    white = np.where(core > 0, 1.0, 0.72)
    return down(a), down(np.where(body > 0, white, 1.0))


def sp_plasma(w, h):
    """プラズマの渦: 三本の対数螺旋の腕 + 白い芯 + 淡い外光。"""
    x, y = grid(w, h)
    r = np.hypot(x, y) + 1e-4
    th = np.arctan2(y, x)
    arms = np.cos(3 * (th + 2.4 * np.log(r)))
    band = hard(arms > 0.35) * sat((0.95 - r) / 0.2) * hard(r > 0.12)
    thin = hard(np.abs(arms - 0.95) < 0.04) * sat((0.98 - r) / 0.1)
    core = sat((0.24 - r) / 0.04)
    hal = sat(1 - r) ** 2 * 0.4
    a = np.maximum(np.maximum(band * (0.55 + 0.45 * sat(1 - r)), core), np.maximum(thin, hal))
    return down(a), down(np.where(core > 0.5, 1.0, 0.8))


def _bolt_pts(rng, x0, x1, y0, y1, depth, rough):
    pts = [(x0, y0), (x1, y1)]
    for d in range(depth):
        out = [pts[0]]
        for i in range(len(pts) - 1):
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            L = math.hypot(bx - ax, by - ay)
            mx, my = (ax + bx) / 2, (ay + by) / 2
            off = rng.uniform(-1, 1) * L * rough
            nx, ny = -(by - ay) / (L + 1e-9), (bx - ax) / (L + 1e-9)
            out += [(mx + nx * off, my + ny * off), (bx, by)]
        pts = out
    return pts


def sp_bolt(w, h, k):
    """稲妻（横向き、左端から右端へ。両端は高さの中央 = 端点が正確につながる）。"""
    rng = np.random.RandomState(100 + k)
    pen = Pen(w, h)
    cy = h / 2
    pts = _bolt_pts(rng, 1, w - 1, cy, cy, 6, 0.34)
    pts = [(px, float(np.clip(py, 3, h - 3))) for px, py in pts]
    pen.poly(pts, 5.5)
    for _ in range(3):                                  # 枝
        i = rng.randint(8, len(pts) - 20)
        bx, by = pts[i]
        L = rng.uniform(30, 60)
        ex = bx + L
        ey = float(np.clip(by + rng.choice([-1, 1]) * rng.uniform(6, h / 2 - 3), 3, h - 3))
        br = _bolt_pts(rng, bx, ex, by, ey, 4, 0.3)
        br = [(px, float(np.clip(py, 2, h - 2))) for px, py in br]
        pen.poly(br, 2.8)
    a = pen.alpha()
    core = Pen(w, h)
    core.poly(pts, 2.4)
    white = 0.68 + 0.32 * core.alpha()
    return halo(a, 2.6, 0.8), white


def sp_arc(w, h, k):
    """放電のちらつき: 中心付近から伸びる短いぎざぎざの線 2〜3 本。"""
    rng = np.random.RandomState(200 + k)
    pen = Pen(w, h)
    c = (w / 2, h / 2)
    for _ in range(rng.randint(2, 4)):
        a0 = rng.uniform(0, 360)
        p0 = polar(c, rng.uniform(0, 6), a0)
        p1 = polar(c, rng.uniform(w * 0.3, w * 0.47), a0 + rng.uniform(-40, 40))
        pts = _bolt_pts(rng, p0[0], p1[0], p0[1], p1[1], 4, 0.35)
        pen.poly(pts, 2.6)
    a = pen.alpha()
    return halo(a, 2.4, 0.75)


def sp_shard(w, h):
    x, y = ngrid(w, h)
    q = np.abs(x) / 0.85 + np.abs(y) / 0.96
    a = hard(q < 1)
    white = np.where(x < -0.05, 1.0, np.where(x > 0.05, 0.68, 0.85))
    rim = hard((q > 0.82) & (q < 1))
    return down(a), down(np.maximum(white, rim))


def sp_ice(w, h):
    """氷晶: 六本の腕（各腕に枝）と中央の六角。面ごとに濃淡を変えた結晶（blend 用）。"""
    pen_a = Pen(w, h)
    pen_w = Pen(w, h)
    c, R = (w / 2, h / 2), w / 2 - 1
    for k in range(6):
        a = k * 60 - 90
        tip = polar(c, R * 0.98, a)
        l = polar(c, R * 0.14, a - 30)
        r_ = polar(c, R * 0.14, a + 30)
        pen_a.polygon([c, l, tip, r_])
        pen_w.polygon([c, l, tip], 255)
        pen_w.polygon([c, r_, tip], 175)
        for t, ln in ((0.5, 0.3), (0.72, 0.2)):
            b = polar(c, R * t, a)
            for s in (-1, 1):
                e = polar(b, R * ln, a + s * 55)
                p0 = polar(b, R * 0.045, a + 90)
                p1 = polar(b, R * 0.045, a - 90)
                pen_a.polygon([p0, e, p1])
                pen_w.polygon([p0, e, p1], 235 if s < 0 else 160)
    pen_a.polygon(hexagon(c, R * 0.24, 30))
    pen_w.polygon(hexagon(c, R * 0.24, 30), 255)
    a = pen_a.alpha()
    white = pen_w.alpha() / np.maximum(a, 1e-3)
    return a, np.clip(white, 0, 1)


def sp_diamond(w, h):
    """ダイヤ（横から見たブリリアントカット）: 冠の台形と尖った底、面ごとの濃淡と白い稜線。"""
    pa, pw, pe = Pen(w, h), Pen(w, h), Pen(w, h)
    sx, sy = w / 2, h / 2
    P = lambda x, y: (sx + x * sx * 0.96, sy + y * sy * 0.96)   # noqa: E731
    table = [P(-0.36, -0.62), P(0.36, -0.62)]
    girdle = [P(-0.92, -0.22), P(0.92, -0.22)]
    culet = P(0, 0.92)
    crown = [girdle[0], table[0], table[1], girdle[1]]
    pa.polygon(crown + [culet])
    # 冠の面
    m1, m2 = P(-0.5, -0.22), P(0.5, -0.22)
    mid = P(0, -0.22)
    faces = [([girdle[0], table[0], m1], 200), ([table[0], mid, m1], 245), ([table[0], table[1], mid], 255),
             ([table[1], m2, mid], 225), ([table[1], girdle[1], m2], 170)]
    # 底の面
    faces += [([girdle[0], m1, culet], 215), ([m1, mid, culet], 150), ([mid, m2, culet], 235),
              ([m2, girdle[1], culet], 130)]
    for pts, v in faces:
        pw.polygon(pts, v)
    for pts, _ in faces:
        pe.poly(pts, 0.9, closed=True, cap=False)
    a = pa.alpha()
    white = pw.alpha() / np.maximum(a, 1e-3)
    white = np.maximum(white, pe.alpha() * a)
    return a, np.clip(white, 0, 1)


def sp_droplet(w, h):
    """液体金属の滴（球。上半分は空の照り返し、下半分は暗く、鋭い反射の点）。"""
    x, y = grid(w, h)
    r = np.hypot(x, y)
    a = hard(r < 0.84)
    horizon = 0.12 + 0.08 * x
    white = np.where(y < horizon, 0.85 - 0.25 * sat(-y), 0.38 + 0.25 * sat((y - horizon) / 0.7))
    white = white * (1 - 0.35 * sat((r - 0.6) / 0.24))
    spec = hard(np.hypot((x + 0.3) / 1.4, y + 0.42) < 0.14)
    white = np.maximum(white, spec)
    return down(a), down(white)


def sp_splash(w, h):
    """水しぶきの王冠: 底の楕円から立ち上がる棘と、先に乗る小さな滴。"""
    pen = Pen(w, h)
    rng = np.random.RandomState(9)
    cx, base = w / 2, h * 0.86
    pen.d.ellipse([(cx - w * 0.42) * SS, (base - h * 0.08) * SS, (cx + w * 0.42) * SS,
                   (base + h * 0.08) * SS], fill=255)
    n = 9
    for i in range(n):
        t = (i + 0.5) / n
        xb = cx + (t - 0.5) * w * 0.8
        lean = (t - 0.5) * 0.9
        top_h = h * (0.45 + 0.35 * math.sin(math.pi * t)) * rng.uniform(0.75, 1.05)
        tipx = xb + lean * top_h * 0.5
        tipy = base - top_h
        wid = w * 0.045
        pen.polygon([(xb - wid, base), (tipx, tipy), (xb + wid, base)])
        pen.dot((tipx + lean * 4, tipy - rng.uniform(4, 9)), w * rng.uniform(0.02, 0.032))
    a = pen.alpha()
    x, y = grid(w, h, 1)
    white = 0.75 + 0.25 * sat((-y + 0.2) / 0.6)
    return halo(a, w / 60, 0.3), white


def sp_bubble(w, h):
    x, y = grid(w, h)
    r = np.hypot(x, y)
    rim = hard(np.abs(r - 0.84) < 0.06)
    fill = hard(r < 0.84) * 0.12
    th = np.degrees(np.arctan2(y, x))
    hl = hard(np.abs(r - 0.66) < 0.07) * hard((th > -170) & (th < -110))
    dot = hard(np.hypot(x + 0.28, y + 0.5) < 0.09)
    a = np.maximum(np.maximum(rim * 0.9, fill), np.maximum(hl, dot))
    return down(a)


def sp_wave(w, h):
    """波頭: 中央が高い弧の水の壁。上縁に泡のふくらみ、下へ薄れる胴、流れの筋。"""
    x, y = ngrid(w, h)
    crest = -0.62 + 0.55 * x * x                       # 上縁（y 下向き）
    foam_t = 0.16 + 0.05 * np.sin(x * 23) + 0.03 * np.sin(x * 51 + 1)
    bump = 0.05 * np.abs(np.sin(x * 19))
    top = crest - bump
    inside = hard(y > top) * hard(y < 0.95)
    foam = hard((y > top) & (y < crest + foam_t))
    depth = sat((y - crest) / (0.95 - crest + 1e-3))
    body = (0.8 - 0.65 * depth) * inside
    streak = hard(np.abs(((y - crest) * 9 + x * 2.5) % 1 - 0.5) < 0.05) * inside * hard(depth > 0.15) * 0.25
    side = sat((1 - np.abs(x)) / 0.22)
    a = np.maximum(np.maximum(foam, body), streak) * side
    white = np.where(foam > 0, 1.0, 0.68 + 0.2 * (1 - depth))
    return down(a), down(white)


def sp_aurora(w, h):
    """オーロラの幕（縦長）: 縦の光条が並び、下縁がくっきり明るく上へ長く消える。"""
    x, y = ngrid(w, h)
    rng = np.random.RandomState(31)
    rays = np.zeros_like(x)
    for _ in range(14):
        cx, wd, k = rng.uniform(-0.9, 0.9), rng.uniform(0.04, 0.16), rng.uniform(0.4, 1.0)
        rays += np.exp(-((x - cx) / wd) ** 2) * k
    rays = sat(0.35 + rays * 0.6)
    bottom = 0.78 + 0.05 * np.sin(x * 9) + 0.03 * np.sin(x * 23)
    vert = hard(y < bottom) * np.exp(-np.maximum(bottom - y, 0) * 1.6)
    edge = hard((y < bottom) & (y > bottom - 0.06))
    side = sat((1 - np.abs(x)) / 0.35)
    a = np.maximum(rays * vert, edge * 0.9) * side * sat((y + 1) / 0.2)
    white = 0.75 + 0.25 * sat((y - bottom + 0.6) / 0.6)
    return down(a), down(white)


def sp_fireball(w, h):
    """火球（隕石の頭と尾の粒）: 白い芯とぎざぎざの炎の縁。"""
    x, y = grid(w, h)
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    edge = 0.6 + 0.05 * np.sin(th * 7) + 0.03 * np.sin(th * 13 + 1.3)
    flame = sat((edge - r) / 0.06) * 0.9
    core = sat((0.34 - r) / 0.05)
    hal = sat(1 - r) ** 2 * 0.5
    a = np.maximum(np.maximum(flame, core), hal)
    return down(a), down(np.where(r < 0.36, 1.0, 0.8))


def sp_streak(w, h):
    """尾の筋（横長、左右対称の細いレンズ形に縦の筋目）。重ねると頭側が太く明るい尾になる。"""
    x, y = ngrid(w, h)
    ay = np.abs(y)
    hw = 0.8 * sat(1 - x * x) ** 1.1
    body = sat((hw - ay) / 0.12)
    stri = 0.72 + 0.28 * np.cos(y * 13 + np.sin(x * 6) * 2.2)
    core = hard(ay < hw * 0.28)
    a = np.maximum(body * stri * 0.85, core)
    return down(a), down(0.7 + 0.3 * core)


def sp_black_hole(w, h):
    """ブラックホール（blend 用の一枚絵）: 黒い核（RGB 0）+ 光子の輪 + 降着円盤の渦 + 淡い外光。
    染めても核は黒のまま、輪と円盤だけが色に染まる。"""
    x, y = grid(w, h)
    r = np.hypot(x, y) + 1e-4
    th = np.arctan2(y, x)
    core_r = 0.3
    core = sat((core_r - r) / 0.012)
    photon = hard(np.abs(r - 0.325) < 0.022)
    sp = np.cos(2 * (th - 3.2 * np.log(r)))
    streaks = 0.6 + 0.4 * np.cos(th * 17 + np.log(r) * 30)
    disc = sat((sp + 0.2) / 1.2) ** 1.6 * streaks * sat((0.93 - r) / 0.3) * hard(r > 0.33)
    hal = sat(1 - r) ** 1.4 * 0.45
    a = np.maximum(np.maximum(core, photon), np.maximum(disc * 0.9, hal))
    white = np.where(r < core_r - 0.01, 0.0, 1.0)
    white = np.where(np.abs(r - core_r) < 0.012, sat((r - core_r + 0.012) / 0.024), white)
    return down(a), down(white)


def sp_void(w, h):
    """虚空の裂け目と触手（blend 用）: 中は暗く（白 0.12）縁だけが明るい。"""
    rng = np.random.RandomState(13)
    pen = Pen(w, h)
    c, R = (w / 2, h / 2), w / 2 - 1
    pen.dot(c, R * 0.3)
    for k in range(7):
        a = k * 360 / 7 + rng.uniform(-15, 15)
        L = R * rng.uniform(0.68, 0.98)
        curl = rng.uniform(-1, 1)
        pts = []
        for i in range(15):
            t = i / 14
            ang = a + curl * 70 * t ** 1.5 + 12 * math.sin(t * 7 + k)
            pts.append((polar(c, R * 0.2 + (L - R * 0.2) * t, ang), (1 - t) ** 0.9))
        for i in range(len(pts) - 1):
            (p0, w0), (p1, _) = pts[i], pts[i + 1]
            pen.line(p0, p1, R * 0.16 * w0 + 0.6)
    a = pen.alpha()
    a8 = Image.fromarray((a * 255).astype(np.uint8))
    inner = np.asarray(a8.filter(ImageFilter.MinFilter(5)), F32) / 255
    rim = sat(a - inner)
    white = 0.12 + 0.88 * sat(rim * 1.6)
    return halo(a * 0.95, 2.0, 0.4), white


def sp_warning(w, h):
    """攻撃予告（blend 用）: 縞の外輪 + 細い輪 + 内向きの警告三角 + 淡い塗り + 中央の！。"""
    x, y = grid(w, h)
    r = np.hypot(x, y)
    th = np.degrees(np.arctan2(y, x))
    band = hard((r > 0.84) & (r < 0.97))
    stripe = hard(((th / 360 * 36 + r * 4) % 1) < 0.5)
    a = band * np.where(stripe > 0, 0.95, 0.3)
    white = band * np.where(stripe > 0, 1.0, 0.25)
    ring = hard(np.abs(r - 0.79) < 0.018)
    fill = hard(r < 0.77) * 0.2
    a = np.maximum(np.maximum(a, ring), fill)
    pen = Pen(w, h)
    c, R = (w / 2, h / 2), w / 2
    for k in range(12):
        ang = k * 30 + 15
        pen.polygon([polar(c, R * 0.74, ang - 5), polar(c, R * 0.74, ang + 5), polar(c, R * 0.64, ang)])
    tri = [polar(c, R * 0.36, -90), polar(c, R * 0.36, 30), polar(c, R * 0.36, 150)]
    pen.poly(tri, R * 0.045, closed=True)
    pen.line((c[0], c[1] - R * 0.16), (c[0], c[1] + R * 0.03), R * 0.06)
    pen.dot((c[0], c[1] + R * 0.12), R * 0.035)
    marks = pen.alpha()
    a = np.maximum(down(a), marks)
    white = np.maximum(down(np.where(band > 0, white, 1.0)), marks)
    return a, white


def sp_afterimage(w, h):
    """装甲の人型シルエット（正面）。中は淡く、縁と継ぎ目の線が明るい。"""
    pen = Pen(w, h)
    lines = Pen(w, h)
    W, H = w, h
    P = lambda fx, fy: (fx * W, fy * H)                     # noqa: E731
    # 兜（鶏冠つき）
    pen.d.rounded_rectangle([P(0.38, 0.035)[0] * SS, P(0.38, 0.035)[1] * SS, P(0.62, 0.15)[0] * SS,
                             P(0.62, 0.15)[1] * SS], radius=int(W * 0.06 * SS), fill=255)
    pen.polygon([P(0.47, 0.04), P(0.5, 0.0), P(0.53, 0.04)])
    pen.polygon([P(0.36, 0.09), P(0.30, 0.05), P(0.38, 0.12)])
    pen.polygon([P(0.64, 0.09), P(0.70, 0.05), P(0.62, 0.12)])
    # 首・胴
    pen.polygon([P(0.45, 0.15), P(0.55, 0.15), P(0.56, 0.18), P(0.44, 0.18)])
    pen.polygon([P(0.30, 0.18), P(0.70, 0.18), P(0.66, 0.36), P(0.60, 0.46), P(0.40, 0.46), P(0.34, 0.36)])
    # 肩当て
    for s in (-1, 1):
        cx = 0.5 + s * 0.235
        pen.d.ellipse([P(cx - 0.11, 0.165)[0] * SS, P(cx - 0.11, 0.165)[1] * SS,
                       P(cx + 0.11, 0.255)[0] * SS, P(cx + 0.11, 0.255)[1] * SS], fill=255)
    # 腕（上腕・籠手）
    for s in (-1, 1):
        x0 = 0.5 + s * 0.235
        pen.polygon([P(x0 - 0.06, 0.24), P(x0 + 0.06, 0.24), P(x0 + s * 0.02 + 0.055, 0.36),
                     P(x0 + s * 0.02 - 0.055, 0.36)])
        pen.polygon([P(x0 + s * 0.02 - 0.07, 0.355), P(x0 + s * 0.02 + 0.07, 0.355),
                     P(x0 + s * 0.045 + 0.06, 0.49), P(x0 + s * 0.045 - 0.06, 0.49)])
        pen.dot(P(x0 + s * 0.045, 0.505), W * 0.05)
    # 腰・脚
    pen.polygon([P(0.38, 0.45), P(0.62, 0.45), P(0.64, 0.53), P(0.36, 0.53)])
    for s in (-1, 1):
        x0 = 0.5 + s * 0.075
        pen.polygon([P(x0 - 0.075, 0.52), P(x0 + 0.075, 0.52), P(x0 + s * 0.01 + 0.065, 0.73),
                     P(x0 + s * 0.01 - 0.065, 0.73)])
        pen.d.ellipse([P(x0 + s * 0.01 - 0.06, 0.70)[0] * SS, P(x0, 0.70)[1] * SS,
                       P(x0 + s * 0.01 + 0.06, 0.765)[0] * SS, P(x0, 0.765)[1] * SS], fill=255)
        pen.polygon([P(x0 + s * 0.012 - 0.06, 0.75), P(x0 + s * 0.012 + 0.06, 0.75),
                     P(x0 + s * 0.02 + 0.055, 0.95), P(x0 + s * 0.02 - 0.055, 0.95)])
        pen.polygon([P(x0 + s * 0.02 - 0.065, 0.94), P(x0 + s * 0.02 + 0.065 + s * 0.03, 0.94),
                     P(x0 + s * 0.02 + 0.07 + s * 0.04, 0.995), P(x0 + s * 0.02 - 0.07, 0.995)])
    # 継ぎ目の線（バイザー・胸の V・ベルト・膝）
    lw = W * 0.018
    lines.line(P(0.41, 0.095), P(0.59, 0.095), lw * 1.3)
    lines.poly([P(0.36, 0.22), P(0.5, 0.33), P(0.64, 0.22)], lw)
    lines.line(P(0.5, 0.33), P(0.5, 0.44), lw)
    lines.line(P(0.38, 0.49), P(0.62, 0.49), lw)
    for s in (-1, 1):
        lines.line(P(0.5 + s * 0.085 - 0.04, 0.735), P(0.5 + s * 0.085 + 0.04, 0.735), lw)
    a = pen.alpha()
    a8 = Image.fromarray((a * 255).astype(np.uint8))
    inner = np.asarray(a8.filter(ImageFilter.MinFilter(5)), F32) / 255
    rim = sat(a - inner)
    ln = lines.alpha() * a
    alpha = np.maximum(np.maximum(a * 0.36, rim * 1.0), ln * 0.85)
    return halo(alpha, 1.6, 0.5), sat(0.65 + rim + ln)


def sp_lens(w, h):
    x, y = grid(w, h)
    r = np.hypot(x, y)
    soft = sat(1 - r) ** 2.2 * 0.75
    ghost = hard(np.abs(r - 0.72) < 0.02) * 0.28
    hexb = sat((0.32 - hex_dist(x, y)) / 0.05) * 0.18
    return down(np.maximum(np.maximum(soft, ghost), hexb))


# ===========================================================================
#  アトラス（スカイライン法で詰める）
# ===========================================================================
# 名前 -> (w, h, frames, axis, fn, args)  frames > 1 は連続したコマ（axis 方向に並ぶ / "grid5" は 5 列）
SPRITES = {
    "circle": (256, 256, 1, "x", sp_circle, ()),
    "hex_circle": (256, 256, 1, "x", sp_hex_circle, ()),
    "slash_big": (256, 256, 1, "x", sp_slash, (0.44, 220.0, 4)),
    "black_hole": (192, 192, 1, "x", sp_black_hole, ()),
    "warning": (192, 192, 1, "x", sp_warning, ()),
    "emblem": (128, 128, 10, "grid5", sp_emblem, ()),
    "afterimage": (96, 192, 1, "x", sp_afterimage, ()),
    "aurora": (64, 256, 1, "x", sp_aurora, ()),
    "pillar": (32, 256, 1, "x", sp_pillar, ()),
    "bolt": (256, 36, 3, "y", sp_bolt, ()),
    "flame": (64, 64, 8, "x", sp_flame, ()),
    "arc": (64, 64, 4, "x", sp_arc, ()),
    "wave": (192, 96, 1, "x", sp_wave, ()),
    "thrust": (256, 64, 1, "x", sp_thrust, ()),
    "flare": (256, 64, 1, "x", sp_flare, ()),
    "beam": (256, 32, 1, "x", sp_beam, ()),
    "streak": (256, 32, 1, "x", sp_streak, ()),
    "scan": (256, 32, 1, "x", sp_scan, ()),
    "slash": (128, 128, 1, "x", sp_slash, (0.4, 200.0, 3)),
    "impact": (128, 128, 1, "x", sp_impact, ()),
    "cross": (128, 128, 1, "x", sp_cross, ()),
    "ring": (128, 128, 1, "x", sp_ring, ()),
    "shock": (128, 128, 1, "x", sp_shock, ()),
    "cloud": (128, 128, 1, "x", sp_cloud, ()),
    "void": (128, 128, 1, "x", sp_void, ()),
    "plasma": (96, 96, 1, "x", sp_plasma, ()),
    "lens": (96, 96, 1, "x", sp_lens, ()),
    "splash": (96, 96, 1, "x", sp_splash, ()),
    "fireball": (96, 96, 1, "x", sp_fireball, ()),
    "glow": (64, 64, 1, "x", sp_glow, ()),
    "star": (64, 64, 1, "x", sp_star, ()),
    "hex": (64, 64, 1, "x", sp_hex, ()),
    "bubble": (64, 64, 1, "x", sp_bubble, ()),
    "ice": (64, 64, 1, "x", sp_ice, ()),
    "diamond": (64, 64, 1, "x", sp_diamond, ()),
    "smoke": (64, 64, 2, "x", sp_smoke, ()),
    "wind": (128, 64, 1, "x", sp_wind, ()),
    "spark": (64, 16, 1, "x", sp_spark, ()),
    "speedline": (128, 16, 1, "x", sp_speedline, ()),
    "nano": (32, 32, 4, "x", sp_nano, ()),
    "debris": (32, 32, 4, "x", sp_debris, ()),
    "shard": (32, 64, 1, "x", sp_shard, ()),
    "droplet": (32, 32, 1, "x", sp_droplet, ()),
    "dot": (32, 32, 1, "x", sp_dot, ()),
}
FRAME_SEEDS = {"smoke": (3, 8)}


def block_size(name):
    w, h, n, axis, _, _ = SPRITES[name]
    if n == 1:
        return w, h
    if axis == "x":
        return w * n, h
    if axis == "y":
        return w, h * n
    cols = 5
    return w * cols, h * ((n + cols - 1) // cols)


def frame_origin(name, i):
    """コマ i の左上（アトラスの texel）。"""
    x, y = LAYOUT[name]
    w, h, n, axis, _, _ = SPRITES[name]
    if axis == "x":
        return x + i * w, y
    if axis == "y":
        return x, y + i * h
    return x + (i % 5) * w, y + (i // 5) * h


def pack(items, W, H, pad=2):
    """スカイライン（左下優先）で詰める。items = [(name, w, h)] → {name: (x, y)}。"""
    sky = [[0, 0, W]]                     # [x, y, width]
    out = {}
    for name, w, h in sorted(items, key=lambda it: (-it[2], -it[1], it[0])):
        ww, hh = w + pad, h + pad
        best = None
        for i in range(len(sky)):
            x = sky[i][0]
            if x + ww > W:
                break
            y, rem, j = 0, ww, i
            while rem > 0:
                y = max(y, sky[j][1])
                rem -= sky[j][2]
                j += 1
            if y + hh > H:
                continue
            key = (y + hh, x)
            if best is None or key < best[0]:
                best = (key, x, y)
        if best is None:
            raise RuntimeError(f"atlas full: cannot place {name} ({w}x{h})")
        _, x, y = best
        out[name] = (x + pad // 2, y + pad // 2)
        # スカイラインを更新
        new = []
        for sx, sy, sw in sky:
            ex = sx + sw
            if ex <= x or sx >= x + ww:
                new.append([sx, sy, sw])
                continue
            if sx < x:
                new.append([sx, sy, x - sx])
            if ex > x + ww:
                new.append([x + ww, sy, ex - (x + ww)])
        new.append([x, y + hh, ww])
        new.sort()
        merged = []
        for seg in new:
            if merged and merged[-1][1] == seg[1] and merged[-1][0] + merged[-1][2] == seg[0]:
                merged[-1][2] += seg[2]
            else:
                merged.append(seg)
        sky = merged
    return out


LAYOUT = pack([(n,) + block_size(n) for n in SPRITES], AW, AH)


def rect(name, i=0):
    """コマ i の (x, y, w, h)。"""
    w, h = SPRITES[name][:2]
    x, y = frame_origin(name, i)
    return x, y, w, h


def render_sprite(name, i):
    w, h, n, axis, fn, args = SPRITES[name]
    if name in FRAME_SEEDS:
        res = fn(w, h, FRAME_SEEDS[name][i])
    elif n > 1:
        res = fn(w, h, i, *args)
    else:
        res = fn(w, h, *args)
    if isinstance(res, tuple):
        a, white = res
    else:
        a, white = res, None
    a = sat(np.asarray(a, F32))
    white = np.ones_like(a) if white is None else sat(np.broadcast_to(np.asarray(white, F32), a.shape))
    assert a.shape == (h, w), (name, a.shape, (h, w))
    return a, white


def build_atlas():
    atlas = np.zeros((AH, AW, 4), F32)
    for name in SPRITES:
        n = SPRITES[name][2]
        for i in range(n):
            if name == "emblem" and i >= len(EMBLEM_KEYS):
                continue
            x, y, w, h = rect(name, i)
            a, white = render_sprite(name, i)
            atlas[y:y + h, x:x + w, 0] = white
            atlas[y:y + h, x:x + w, 1] = white
            atlas[y:y + h, x:x + w, 2] = white
            atlas[y:y + h, x:x + w, 3] = a
    img = Image.fromarray((np.clip(atlas, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    os.makedirs(os.path.dirname(ATLAS_PNG), exist_ok=True)
    img.save(ATLAS_PNG, optimize=True)
    return img


# ===========================================================================
#  Molang の小さなコンパイラ（自己検査とプレビューのシミュレーション用）
#  対応: 数値, 変数 (v./variable./t./q./c.), math.*, + - * / ! < > <= >= == != && || ?: ?? = ; return
# ===========================================================================
class MolangError(Exception):
    pass


_TOK = re.compile(r"""\s*(?:
    (?P<num>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)f?
  | (?P<id>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
  | (?P<op>\?\?|&&|\|\||==|!=|<=|>=|[-+*/<>!?:(),;={}])
)""", re.X)
_ALIAS = {"v": "variable", "t": "temp", "q": "query", "c": "context"}
MATH_FUNCS = {"abs", "ceil", "clamp", "cos", "exp", "floor", "lerp", "ln", "max", "min", "mod", "pow",
              "random", "random_integer", "round", "sin", "sqrt", "trunc", "atan2", "sign"}


def canon(name):
    name = name.lower()
    head, _, rest = name.partition(".")
    head = _ALIAS.get(head, head)
    return head + ("." + rest if rest else "")


def tokenize(src):
    pos, out = 0, []
    src = src.rstrip()
    while pos < len(src):
        m = _TOK.match(src, pos)
        if not m or m.end() == pos:
            raise MolangError(f"bad token at {pos}: {src[pos:pos + 12]!r}")
        pos = m.end()
        if m.group("num"):
            out.append(("num", float(m.group("num"))))
        elif m.group("id"):
            out.append(("id", m.group("id")))
        elif m.group("op"):
            out.append(("op", m.group("op")))
    out.append(("end", None))
    return out


class _Parser:
    def __init__(self, src):
        self.t = tokenize(src)
        self.i = 0

    def peek(self, k=0):
        return self.t[self.i + k]

    def take(self, op=None):
        tok = self.t[self.i]
        if op is not None and tok != ("op", op):
            raise MolangError(f"expected {op!r}, got {tok}")
        self.i += 1
        return tok

    def program(self):
        stmts = []
        while self.peek()[0] != "end":
            if self.peek() == ("op", ";"):
                self.take()
                continue
            stmts.append(self.statement())
            if self.peek()[0] != "end":
                self.take(";")
        return stmts

    def statement(self):
        tok = self.peek()
        if tok == ("id", "return"):
            self.take()
            return ("return", self.expr())
        if tok[0] == "id" and self.peek(1) == ("op", "="):
            self.take()
            self.take("=")
            return ("assign", canon(tok[1]), self.expr())
        return ("expr", self.expr())

    def expr(self):
        c = self.coalesce()
        if self.peek() == ("op", "?"):
            self.take()
            a = self.expr()
            if self.peek() == ("op", ":"):
                self.take()
                return ("tern", c, a, self.expr())
            return ("tern", c, a, ("num", 0.0))
        return c

    def coalesce(self):
        a = self.orr()
        if self.peek() == ("op", "??"):
            self.take()
            return ("nc", a, self.coalesce())
        return a

    def _binary(self, sub, ops):
        a = sub()
        while self.peek()[0] == "op" and self.peek()[1] in ops:
            op = self.take()[1]
            a = ("bin", op, a, sub())
        return a

    def orr(self):
        return self._binary(self.andd, ("||",))

    def andd(self):
        return self._binary(self.eq, ("&&",))

    def eq(self):
        return self._binary(self.rel, ("==", "!="))

    def rel(self):
        return self._binary(self.add, ("<", ">", "<=", ">="))

    def add(self):
        return self._binary(self.mul, ("+", "-"))

    def mul(self):
        return self._binary(self.unary, ("*", "/"))

    def unary(self):
        if self.peek() in (("op", "-"), ("op", "!")):
            op = self.take()[1]
            return ("un", op, self.unary())
        return self.primary()

    def primary(self):
        kind, val = self.take()
        if kind == "num":
            return ("num", val)
        if kind == "op" and val == "(":
            e = self.expr()
            self.take(")")
            return e
        if kind == "id":
            name = canon(val)
            if self.peek() == ("op", "("):
                self.take()
                args = []
                if self.peek() != ("op", ")"):
                    args.append(self.expr())
                    while self.peek() == ("op", ","):
                        self.take()
                        args.append(self.expr())
                self.take(")")
                if not name.startswith("math.") or name[5:] not in MATH_FUNCS:
                    raise MolangError(f"unknown function {val}")
                return ("call", name[5:], args)
            if name == "math.pi":
                return ("num", math.pi)
            if name.split(".")[0] not in ("variable", "temp", "query", "context"):
                raise MolangError(f"unknown identifier {val}")
            return ("var", name)
        raise MolangError(f"unexpected {kind} {val!r}")


def molang_parse(src):
    if isinstance(src, (int, float)):
        return [("expr", ("num", float(src)))]
    if not isinstance(src, str):
        raise MolangError(f"not a molang value: {src!r}")
    return _Parser(src).program()


def molang_reads(ast, out=None, guarded=False):
    """読む変数の一覧 [(名前, ?? で守られているか)]。"""
    out = [] if out is None else out
    if isinstance(ast, list):
        for s in ast:
            molang_reads(s, out)
        return out
    k = ast[0]
    if k == "var":
        out.append((ast[1], guarded))
    elif k == "nc":
        molang_reads(ast[1], out, True)
        molang_reads(ast[2], out)
    elif k in ("assign",):
        molang_reads(ast[2], out)
    elif k in ("return", "expr"):
        molang_reads(ast[1], out)
    elif k == "un":
        molang_reads(ast[2], out)
    elif k == "bin":
        molang_reads(ast[2], out)
        molang_reads(ast[3], out)
    elif k == "tern":
        for a in ast[1:]:
            molang_reads(a, out)
    elif k == "call":
        for a in ast[2]:
            molang_reads(a, out)
    return out


def molang_assigns(ast):
    return [s[1] for s in ast if s[0] == "assign"]


def _gen(n):
    k = n[0]
    if k == "num":
        return repr(n[1])
    if k == "var":
        return f"R(c,{n[1]!r})"
    if k == "nc":
        if n[1][0] == "var":
            return f"(_t if (_t := G(c,{n[1][1]!r})) is not None else {_gen(n[2])})"
        return _gen(n[1])
    if k == "un":
        return f"(-{_gen(n[2])})" if n[1] == "-" else f"(0.0 if {_gen(n[2])} else 1.0)"
    if k == "bin":
        a, b, op = _gen(n[2]), _gen(n[3]), n[1]
        if op in "+-*":
            return f"({a} {op} {b})"
        if op == "/":
            return f"D({a},{b})"
        if op == "&&":
            return f"(1.0 if ({a}) and ({b}) else 0.0)"
        if op == "||":
            return f"(1.0 if ({a}) or ({b}) else 0.0)"
        return f"(1.0 if {a} {op} {b} else 0.0)"
    if k == "tern":
        return f"(({_gen(n[2])}) if ({_gen(n[1])}) else ({_gen(n[3])}))"
    if k == "call":
        return f"M_{n[1]}({', '.join(_gen(a) for a in n[2])})"
    raise MolangError(f"cannot generate {k}")


class _Env:
    rng = random.Random(1)
    strict = True


def _R(c, name):
    v = c.get(name)
    if v is None:
        if _Env.strict:
            raise MolangError(f"read of undefined {name}")
        return 0.0
    return v


def _D(a, b):
    return a / b if b != 0 else float("nan")


def _pow(a, b):
    try:
        r = float(a) ** float(b)
        return r if not isinstance(r, complex) else float("nan")
    except (ZeroDivisionError, OverflowError):
        return float("nan")


_GLOBALS = {
    "R": _R, "G": lambda c, n: c.get(n), "D": _D,
    "M_abs": abs, "M_ceil": lambda x: float(math.ceil(x)), "M_floor": lambda x: float(math.floor(x)),
    "M_round": lambda x: float(round(x)), "M_trunc": lambda x: float(math.trunc(x)),
    "M_clamp": lambda v, a, b: min(max(v, a), b), "M_lerp": lambda a, b, t: a + (b - a) * t,
    "M_sin": lambda d: math.sin(math.radians(d)), "M_cos": lambda d: math.cos(math.radians(d)),
    "M_atan2": lambda y, x: math.degrees(math.atan2(y, x)), "M_exp": math.exp,
    "M_ln": lambda x: math.log(x) if x > 0 else float("nan"), "M_max": max, "M_min": min,
    "M_mod": lambda a, b: math.fmod(a, b) if b != 0 else float("nan"), "M_pow": _pow,
    "M_sqrt": lambda x: math.sqrt(x) if x >= 0 else float("nan"),
    "M_random": lambda a, b: _Env.rng.uniform(a, b),
    "M_random_integer": lambda a, b: float(_Env.rng.randint(int(a), int(b))),
    "M_sign": lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0),
}
_CACHE = {}


def molang_compile(src):
    """式をコンパイルして f(ctx) -> float を返す（ctx は変数名 'variable.x' の辞書）。"""
    key = repr(src)
    if key in _CACHE:
        return _CACHE[key]
    ast = molang_parse(src)
    if len(ast) == 1 and ast[0][0] == "expr":
        code = f"lambda c: {_gen(ast[0][1])}"
        fn = eval(code, dict(_GLOBALS))
    else:
        lines = ["def _f(c):"]
        for s in ast:
            if s[0] == "assign":
                lines.append(f"    c[{s[1]!r}] = {_gen(s[2])}")
            elif s[0] == "return":
                lines.append(f"    return {_gen(s[1])}")
            else:
                lines.append(f"    {_gen(s[1])}")
        lines.append("    return 0.0")
        g = dict(_GLOBALS)
        exec("\n".join(lines), g)
        fn = g["_f"]
    _CACHE[key] = fn
    return fn


def parens_balanced(s):
    depth = 0
    for ch in s:
        depth += (ch == "(") - (ch == ")")
        if depth < 0:
            return False
    return depth == 0


# ===========================================================================
#  パーティクル定義
# ===========================================================================
AGE = "(v.particle_age / v.particle_lifetime)"
PA = "v.particle_age"
R1, R2, R3, R4 = (f"v.particle_random_{i}" for i in range(1, 5))
SCRIPT_VARS = ("cr", "cg", "cb", "size", "life", "rot", "count", "speed", "spread", "vx", "vy", "vz",
               "var", "height", "spin", "rate", "grav", "len")
VAR_MEANING = {
    "cr": "色の赤 (0..1)", "cg": "色の緑 (0..1)", "cb": "色の青 (0..1)",
    "size": "大きさの倍率（各粒の基準の大きさに掛ける）", "life": "粒の寿命 (秒)",
    "rot": "面内の回転 (度)", "count": "粒の数", "speed": "初速 (m/s)", "spread": "散らばりの半径 (m)",
    "vx": "向き X", "vy": "向き Y", "vz": "向き Z", "var": "スプライトの種類",
    "height": "高さ (m)", "spin": "回転の速さ (度/秒)", "rate": "放出レート (粒/秒)",
    "grav": "重力加速度 (m/s²、下向きは負)", "len": "長さ (m)",
}
# 既定の色（0..1）
CYAN = (0.47, 0.94, 1.0)
WHITE = (1.0, 0.97, 0.9)
GOLD = (1.0, 0.9, 0.55)
FIRE = (1.0, 0.55, 0.16)
ELEC = (0.6, 0.92, 1.0)
WATER = (0.58, 0.87, 1.0)
ICE = (0.78, 0.95, 1.0)
VIOLET = (0.66, 0.4, 1.0)
VOID = (0.55, 0.15, 0.95)
RED = (1.0, 0.18, 0.12)
SMOKE = (0.25, 0.24, 0.28)
DUST = (0.62, 0.56, 0.48)
ROCK = (0.42, 0.36, 0.32)
MERCURY = (0.85, 0.9, 0.95)
SULFUR = (0.92, 0.86, 0.45)
AURORA = (0.33, 1.0, 0.57)


def num(x):
    if isinstance(x, str):
        return x
    x = float(x)
    if x == int(x) and abs(x) < 1e6:
        return f"{int(x)}.0"
    return f"{x:.4g}"


def clamp01(e):
    return f"math.clamp({e}, 0.0, 1.0)"


def fade_out(k=1.6):
    return clamp01(f"(1.0 - {AGE}) * {num(k)}")


def fade_io(a=6.0, b=2.5):
    return clamp01(f"math.min({AGE} * {num(a)}, (1.0 - {AGE}) * {num(b)})")


def fade_abs(t_in=0.2, t_out=0.3):
    """寿命が長くても短くても同じ速さで現れて消える（秒）。"""
    return clamp01(f"math.min({PA} * {num(1 / t_in)}, (v.particle_lifetime - {PA}) * {num(1 / t_out)})")


def ease(t):
    return f"({t} * {t} * (3.0 - 2.0 * {t}))"


def rnd(scale):
    return f"math.random(-1.0, 1.0) * {scale}"


class FX:
    """1 つのパーティクル効果。変数の既定値と説明を記録し、JSON と PARTICLES.md を作る。"""

    def __init__(self, ident, material, look, uses, typical, star=False):
        self.id, self.material = ident, material
        self.look, self.uses, self.typical, self.star = look, uses, typical, star
        self.vars = {}        # name -> [default_text, note]
        self.comps = {}
        self.init_src = []
        self.cost = ""

    # ---- 変数
    def v(self, name, default, note=None, doc_default=None):
        assert name in SCRIPT_VARS, name
        d = num(default)
        shown = doc_default if doc_default is not None else d
        if name in self.vars:
            assert self.vars[name][2] == d, (self.id, name, self.vars[name][2], d)
            if note:
                self.vars[name][1] = note
        else:
            self.vars[name] = [shown, note, d]
        return f"(v.{name} ?? {d})"

    @property
    def S(self):
        return self.v("size", 1.0)

    def life(self, d, note=None):
        return self.v("life", d, note)

    def col(self, rgb, whiten=None, white_mix=None, doc=None):
        cs = [self.v(n, c, doc_default=None if doc is None else doc[i])
              for i, (n, c) in enumerate(zip(("cr", "cg", "cb"), rgb))]
        if whiten:
            k = clamp01(f"1.0 - {AGE} * {num(whiten)}")
            cs = [f"math.lerp({c}, 1.0, {k})" for c in cs]
        if white_mix:
            cs = [f"math.lerp({c}, 1.0, {white_mix})" for c in cs]
        return cs

    def tint(self, rgb, alpha, whiten=None, white_mix=None, doc=None):
        """色は必ず particle_appearance_tinting の中。加算では RGB にも消え方を掛ける
        （加算の材質がアルファを見るかは確かめられないので、RGB とアルファの両方で消す）。"""
        cs = self.col(rgb, whiten, white_mix, doc)
        if self.material == "add":
            cs = [f"{c} * {alpha}" for c in cs]
        self.comps["minecraft:particle_appearance_tinting"] = {"color": cs + [alpha]}

    # ---- エミッタ
    def init(self, src):
        self.init_src.append(src)

    def instant(self, count):
        self.comps["minecraft:emitter_rate_instant"] = {"num_particles": count}
        self.comps["minecraft:emitter_lifetime_once"] = {"active_time": 0}

    def steady(self, rate, max_particles, active):
        self.comps["minecraft:emitter_rate_steady"] = {"spawn_rate": rate, "max_particles": max_particles}
        self.comps["minecraft:emitter_lifetime_once"] = {"active_time": active}

    def point(self, offset=None, direction=None):
        d = {"offset": offset or [0, 0, 0]}
        if direction is not None:
            d["direction"] = direction
        self.comps["minecraft:emitter_shape_point"] = d

    def sphere(self, radius, direction="outwards", surface=False):
        self.comps["minecraft:emitter_shape_sphere"] = {"offset": [0, 0, 0], "radius": radius,
                                                        "surface_only": surface, "direction": direction}

    def disc(self, radius, direction="outwards"):
        self.comps["minecraft:emitter_shape_disc"] = {"offset": [0, 0, 0], "radius": radius,
                                                      "plane_normal": [0, 1, 0], "direction": direction}

    # ---- 粒
    def lifetime(self, expr):
        self.comps["minecraft:particle_lifetime_expression"] = {"max_lifetime": expr}

    def speed(self, expr):
        self.comps["minecraft:particle_initial_speed"] = expr

    def dyn(self, acc=(0, 0, 0), drag=0):
        self.comps["minecraft:particle_motion_dynamic"] = {"linear_acceleration": list(acc),
                                                           "linear_drag_coefficient": drag}

    def param(self, pos, rotation=None):
        d = {"relative_position": pos}
        if rotation is not None:
            d["rotation"] = rotation
        self.comps["minecraft:particle_motion_parametric"] = d

    def spin(self, rot, rate=0):
        self.comps["minecraft:particle_initial_spin"] = {"rotation": rot, "rotation_rate": rate}

    def collide(self, drag, bounce, radius, expire=False):
        self.comps["minecraft:particle_motion_collision"] = {
            "collision_drag": drag, "coefficient_of_restitution": bounce, "collision_radius": radius,
            "expire_on_contact": expire}

    def bb(self, size, mode, uv, direction=None):
        d = {"size": size, "facing_camera_mode": mode}
        if direction is not None:
            d["direction"] = direction
        d["uv"] = uv
        self.comps["minecraft:particle_appearance_billboard"] = d

    # ---- 書き出し
    def doc(self):
        comps = {}
        if self.init_src:
            comps["minecraft:emitter_initialization"] = {"creation_expression": " ".join(self.init_src)}
        comps.update(self.comps)
        mat = {"add": "particles_add", "blend": "particles_blend", "alpha": "particles_alpha"}[self.material]
        return {"format_version": FORMAT_VERSION, "particle_effect": {
            "description": {"identifier": f"{NS}:{self.id}",
                            "basic_render_parameters": {"material": mat, "texture": TEX}},
            "components": comps}}


# ---- uv
def uv(name, i=0):
    x, y, w, h = rect(name, i)
    return {"texture_width": AW, "texture_height": AH, "uv": [x, y], "uv_size": [w, h]}


def uv_pick(name, idx_expr, n):
    """連続したコマから idx_expr（0..n-1 に丸める）のコマを選ぶ。"""
    x, y, w, h = rect(name, 0)
    axis = SPRITES[name][3]
    i = f"math.clamp(math.floor({idx_expr}), 0.0, {num(n - 1)})"
    if axis == "x":
        u, v = f"{x}.0 + {i} * {w}.0", float(y)
    elif axis == "y":
        u, v = float(x), f"{y}.0 + {i} * {h}.0"
    else:
        u = f"{x}.0 + math.mod({i}, 5.0) * {w}.0"
        v = f"{y}.0 + math.floor({i} / 5.0) * {h}.0"
    return {"texture_width": AW, "texture_height": AH, "uv": [u, v], "uv_size": [w, h]}


def uv_choice(options, idx_expr):
    """v.var などで別々のスプライトを選ぶ uv。options = [(sprite, frame_idx_expr or None)]。"""
    def pick(vals):
        e = num(vals[-1])
        for i in range(len(vals) - 2, -1, -1):
            e = f"({idx_expr} < {num(i + 0.5)} ? {num(vals[i])} : {e})"
        return e
    us, vs, ws, hs = [], [], [], []
    for name, fexpr in options:
        x, y, w, h = rect(name, 0)
        n = SPRITES[name][2]
        if fexpr is not None and n > 1:
            us.append(f"({x}.0 + math.clamp(math.floor({fexpr}), 0.0, {num(n - 1)}) * {w}.0)")
        else:
            us.append(float(x))
        vs.append(float(y))
        ws.append(float(w))
        hs.append(float(h))
    return {"texture_width": AW, "texture_height": AH, "uv": [pick(us), pick(vs)], "uv_size": [pick(ws), pick(hs)]}


EXTRA_IDS = ("ring_n", "line_n")      # DESIGN §4.7 に無い追加（まとめ役の依頼: 1 回の spawn で形を描く）


def flipbook(name, n, fps=12):
    x, y, w, h = rect(name, 0)
    return {"texture_width": AW, "texture_height": AH,
            "flipbook": {"base_UV": [x, y], "size_UV": [w, h], "step_UV": [w, 0],
                         "frames_per_second": fps, "max_frame": n, "stretch_to_lifetime": True}}


def dir_init(f, dflt, note):
    """(vx, vy, vz) を正規化して v.e_nx/ny/nz に入れる。3 つとも無い（長さ 0）時は dflt。
    v.e_dl = 渡された向きの長さ、v.e_has = 向きが渡されたか (0/1)。"""
    vx, vy, vz = (f.v(n, 0.0, note) for n in ("vx", "vy", "vz"))
    L = math.sqrt(sum(c * c for c in dflt))
    dx, dy, dz = (num(c / L) for c in dflt)
    f.init(f"v.e_dx = {vx}; v.e_dy = {vy}; v.e_dz = {vz}; "
           "v.e_dl = math.sqrt(v.e_dx * v.e_dx + v.e_dy * v.e_dy + v.e_dz * v.e_dz); "
           "v.e_has = (v.e_dl > 0.0001) ? 1.0 : 0.0; "
           f"v.e_nx = (v.e_has > 0.5) ? (v.e_dx / math.max(v.e_dl, 0.0001)) : {dx}; "
           f"v.e_ny = (v.e_has > 0.5) ? (v.e_dy / math.max(v.e_dl, 0.0001)) : {dy}; "
           f"v.e_nz = (v.e_has > 0.5) ? (v.e_dz / math.max(v.e_dl, 0.0001)) : {dz};")


def target_init(f, dflt, note):
    """(vx, vy, vz) を終点のずれ (m) として v.e_tx/ty/tz に入れる（3 つとも無い時は dflt）。
    さらに向き v.e_nx.. と、それに直交する 2 本 v.e_ax.. / v.e_bx..（螺旋用）も作る。"""
    vx, vy, vz = (f.v(n, 0.0, note) for n in ("vx", "vy", "vz"))
    tx, ty, tz = (num(c) for c in dflt)
    L = math.sqrt(sum(c * c for c in dflt)) or 1.0
    f.init(f"v.e_dx = {vx}; v.e_dy = {vy}; v.e_dz = {vz}; "
           "v.e_dl = math.sqrt(v.e_dx * v.e_dx + v.e_dy * v.e_dy + v.e_dz * v.e_dz); "
           "v.e_has = (v.e_dl > 0.0001) ? 1.0 : 0.0; "
           f"v.e_tx = (v.e_has > 0.5) ? v.e_dx : {tx}; "
           f"v.e_ty = (v.e_has > 0.5) ? v.e_dy : {ty}; "
           f"v.e_tz = (v.e_has > 0.5) ? v.e_dz : {tz}; "
           f"v.e_tl = (v.e_has > 0.5) ? v.e_dl : {num(L)}; "
           "v.e_nx = v.e_tx / math.max(v.e_tl, 0.0001); v.e_ny = v.e_ty / math.max(v.e_tl, 0.0001); "
           "v.e_nz = v.e_tz / math.max(v.e_tl, 0.0001); "
           "v.e_h = math.sqrt(v.e_nx * v.e_nx + v.e_nz * v.e_nz); "
           "v.e_ax = (v.e_h > 0.2) ? ((0.0 - v.e_nz) / v.e_h) : 1.0; v.e_ay = 0.0; "
           "v.e_az = (v.e_h > 0.2) ? (v.e_nx / v.e_h) : 0.0; "
           "v.e_bx = v.e_ny * v.e_az - v.e_nz * v.e_ay; v.e_by = v.e_nz * v.e_ax - v.e_nx * v.e_az; "
           "v.e_bz = v.e_nx * v.e_ay - v.e_ny * v.e_ax;")


N3 = ["v.e_nx", "v.e_ny", "v.e_nz"]
CUSTOM_N = {"mode": "custom", "custom_direction": list(N3)}
VEL_DIR = {"mode": "derive_from_velocity", "min_speed_threshold": 0.05}
FLICKER_ON = f"({PA} < 0.12 ? (0.35 + 0.65 * math.mod(math.floor({PA} * 50.0), 2.0)) : 1.0)"
DIR_NOTE = "向き（正規化して使う。3 つとも 0/未指定なら既定の向き）"


def build_effects():
    E = []

    def new(*a, **k):
        f = FX(*a, **k)
        E.append(f)
        return f

    # ================= 発光の基本 =================
    f = new("glow", "add", "丸い発光の玉（白い芯 + 柔らかい光）。生まれた瞬間は白く、すぐ色に落ちる",
            "命中点・溜めの芯・軌跡の点打ち", "size 0.6〜2 / life 0.3〜0.6")
    S = f.S
    dir_init(f, (0, 1, 0), "飛ぶ向き（speed > 0 の時。未指定は上）")
    sp = f.v("spread", 0.0)
    f.instant(f.v("count", 1))
    f.point([rnd(sp), rnd(sp), rnd(sp)], list(N3))
    f.lifetime(f"{f.life(0.4)} * math.random(0.85, 1.15)")
    f.speed(f.v("speed", 0.0))
    f.dyn(drag=2.5)
    f.bb([f"{S} * 0.5 * (1.0 - {AGE} * 0.5)"] * 2, "lookat_xyz", uv("glow"))
    f.tint(CYAN, fade_out(1.6), whiten=4)
    f.cost = "count（既定 1）"

    f = new("trail", "add", "小さな発光の点（すぐ縮んで消える）。点を並べて線や軌跡を描く用",
            "fx.js の line()/arc() で並べる軌跡・弾道", "size 0.5〜1.5 / life 0.15〜0.3")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.22))
    f.bb([f"{S} * 0.4 * (1.0 - {AGE} * 0.7)"] * 2, "lookat_xyz", uv("glow"))
    f.tint(CYAN, clamp01(f"(1.0 - {AGE}) * 1.3"), whiten=3)
    f.cost = "1"

    f = new("dot", "add", "小さな光の粒が球状に散る", "命中の細かい粒・オーラの粒・粉",
            "count 6〜16 / size 0.6〜1.5")
    S = f.S
    f.instant(f.v("count", 10))
    f.sphere(f.v("spread", 0.6))
    f.speed(f"{f.v('speed', 1.0)} * math.random(0.3, 1.0)")
    f.dyn((0, f.v("grav", 0.0), 0), 1.5)
    f.lifetime(f"{f.life(0.6)} * math.random(0.6, 1.4)")
    f.bb([f"{S} * 0.08 * (1.0 - {AGE} * 0.4)"] * 2, "lookat_xyz", uv("dot"))
    f.tint(CYAN, fade_out(1.6), whiten=3)
    f.cost = "count（既定 10）"

    f = new("spark", "add", "細長い火花の筋が飛び散り、重力で弧を描いて落ちる（筋は速度の向き）",
            "金属の打撃・斬撃の火花・着地", "count 6〜14 / speed 5〜10")
    S = f.S
    dir_init(f, (0, 1, 0), "飛び散る向きの偏り（未指定なら全方向）")
    f.instant(f.v("count", 8))
    f.point(direction=[f"math.random(-1.0, 1.0) + v.e_has * 2.2 * v.e_nx",
                       f"math.random(-1.0, 1.0) + v.e_has * 2.2 * v.e_ny",
                       f"math.random(-1.0, 1.0) + v.e_has * 2.2 * v.e_nz"])
    f.speed(f"{f.v('speed', 7.0)} * math.random(0.5, 1.1)")
    f.dyn((0, f.v("grav", -14.0), 0), 3.2)
    f.lifetime(f"{f.life(0.35)} * math.random(0.6, 1.2)")
    f.bb([f"{S} * 0.5 * (1.0 - {AGE} * 0.6)", f"{S} * 0.06"], "lookat_direction", uv("spark"), VEL_DIR)
    f.tint((1.0, 0.86, 0.5), fade_out(1.6), whiten=5)
    f.cost = "count（既定 8）"

    f = new("star", "add", "四芒のきらめきが漂いながら瞬く", "変身・星の演出・回復・ドロップの輝き",
            "count 4〜10 / spread 0.5〜2")
    S = f.S
    f.instant(f.v("count", 6))
    f.sphere(f.v("spread", 0.8))
    f.speed(f"{f.v('speed', 0.6)} * math.random(0.0, 1.0)")
    f.dyn(drag=1.2)
    f.lifetime(f"{f.life(1.0)} * math.random(0.5, 1.5)")
    f.spin("math.random(0.0, 90.0)", f.v("spin", 60.0))
    f.bb([f"{S} * 0.22 * (0.55 + 0.45 * math.sin({PA} * 1080.0 + {R3} * 360.0))"] * 2,
         "lookat_xyz", uv("star"))
    f.tint(GOLD, fade_io(6, 2.5), whiten=2)
    f.cost = "count（既定 6）"

    f = new("impact", "add", "打撃の閃光（長短の鋭い棘の星形）が一瞬で広がって消える",
            "命中の瞬間（hit の度に 1 つ）", "size 0.8〜3 / life 0.12〜0.2")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.16))
    f.spin(f.v("rot", "math.random(0.0, 360.0)", doc_default="ランダム"))
    f.bb([f"{S} * 1.5 * (0.5 + 0.7 * (1.0 - math.pow(1.0 - {AGE}, 3.0)))"] * 2, "lookat_xyz", uv("impact"))
    f.tint(WHITE, fade_out(1.4), whiten=2.5)
    f.cost = "1"

    f = new("flare", "add", "横一文字のアナモルフィックな閃光（横に伸び、縦に潰れる）",
            "必殺の閃き・光線の発射口・カットインの瞬間", "size 1〜4 / life 0.2〜0.4")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.3))
    f.spin(f.v("rot", 0.0))
    f.bb([f"{S} * 3.2 * (0.4 + {AGE} * 1.2)", f"{S} * 0.8 * (1.0 - {AGE})"], "lookat_xyz", uv("flare"))
    f.tint(GOLD, fade_out(1.5), whiten=2)
    f.cost = "1"

    # ================= 輪 =================
    f = new("ring", "add", "正面を向いた細い光の輪が広がる", "衝撃・音波・発射の輪（カメラを向く）",
            "size 1〜4 / life 0.25〜0.5")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.35))
    f.bb([f"{S} * 2.0 * math.sqrt({AGE})"] * 2, "lookat_xyz", uv("ring"))
    f.tint(CYAN, fade_out(1.3), whiten=3)
    f.cost = "1"

    f = new("ring_flat", "add", "水平（地面と平行）の細い光の輪が広がる", "足元の波紋・着地・範囲の縁",
            "size 1〜6 / life 0.3〜0.6")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.45))
    f.bb([f"{S} * 2.2 * math.pow({AGE}, 0.45)"] * 2, "emitter_transform_xz", uv("ring"))
    f.tint(CYAN, fade_out(1.4), whiten=3)
    f.cost = "1"

    f = new("shock_flat", "add", "地を走る衝撃波: 外縁がくっきり白い太い輪が水平に一気に広がる",
            "叩きつけ・着地・爆心（dust と重ねると土煙つき）", "size 1.5〜6 / life 0.4〜0.7")
    S = f.S
    f.instant(1)
    f.point([0, 0.05, 0])
    f.lifetime(f.life(0.5))
    f.bb([f"{S} * 3.0 * (1.0 - math.pow(1.0 - {AGE}, 2.2))"] * 2, "emitter_transform_xz", uv("shock"))
    f.tint(CYAN, clamp01(f"math.pow(1.0 - {AGE}, 1.2) * 1.2"), whiten=2)
    f.cost = "1"

    # ================= 陣 =================
    def tech_circle(ident, sprite, mode, look, uses, base=2.4, spin_d=30.0, life_d=1.2, direction=None,
                    pre=None):
        f = new(ident, "add", look, uses, f"size 1〜4（直径 ≈ {base} × size m）/ life 1〜5")
        S = f.S
        if pre:
            pre(f)
        f.instant(1)
        f.point()
        f.lifetime(f.life(life_d))
        f.spin(f.v("rot", 0.0), f.v("spin", spin_d))
        f.dyn()
        app = clamp01(f"{PA} * 5.0")
        f.bb([f"{S} * {num(base)} * {app} * (1.0 + 0.12 * math.sin({app} * 180.0))"] * 2, mode, sprite,
             direction)
        f.cost = "1"
        return f

    f = tech_circle("circle", uv("circle"), "emitter_transform_xz",
                    "水平の技術陣: 目盛りの帯・機械文字の帯・三重の弧・三角・照準。ちらついて点き、回る",
                    "技の発動・溜め・設置範囲・変身の足元")
    f.tint(CYAN, f"{fade_abs(0.2, 0.3)} * {FLICKER_ON}", white_mix=clamp01(f"1.0 - {PA} * 8.0"))

    f = tech_circle("circle_v", uv("circle"), "direction_z",
                    "縦の技術陣。面が (vx,vy,vz) の向きを向く（既定 +Z）。ちらついて点き、回る",
                    "光線・射撃の発射口（視線の向きを渡す）・盾", direction=dict(CUSTOM_N),
                    pre=lambda f: dir_init(f, (0, 0, 1), "陣の面が向く向き（視線など）"))
    f.tint(CYAN, f"{fade_abs(0.2, 0.3)} * {FLICKER_ON}", white_mix=clamp01(f"1.0 - {PA} * 8.0"))

    f = tech_circle("hex_circle", uv("hex_circle"), "emitter_transform_xz",
                    "水平の六角陣: 二重の六角・辺の目盛り・機械文字・内側のハニカム", "バリア・土星の六角渦・設置範囲",
                    spin_d=20.0)
    f.tint(CYAN, f"{fade_abs(0.2, 0.3)} * {FLICKER_ON}", white_mix=clamp01(f"1.0 - {PA} * 8.0"))

    # 紋章: v.var = 惑星番号（order - 1）、色の既定は惑星の発光色
    def emblem_pre(f):
        f.init(f"v.e_idx = math.clamp(math.floor({f.v('var', 9.0, '惑星番号 0..8（order-1: 0 mercury … 8 sol）、9 = 汎用の紋章', doc_default='9（汎用）')} + 0.5), 0.0, 9.0);")
    f = tech_circle("emblem", uv_pick("emblem", "v.e_idx", 10), "emitter_transform_xz",
                    "水平の惑星紋章の陣: 刻みの入った機械の輪 + 惑星番号の灯 + 中央の天文記号（v.var で選ぶ）",
                    "変身の締め・必殺の足元・惑星技の発動", base=3.0, spin_d=20.0, life_d=1.6, pre=emblem_pre)
    glows = [AD.rgb01(AD.PLANETS[k]["colors"]["glow"]) for k in AD.PLANET_KEYS] + [list(CYAN)]

    def by_idx(ch):
        e = num(glows[9][ch])
        for i in range(8, -1, -1):
            e = f"(v.e_idx < {num(i + 0.5)} ? {num(glows[i][ch])} : {e})"
        return e
    f.tint((by_idx(0), by_idx(1), by_idx(2)), f"{fade_abs(0.25, 0.4)} * {FLICKER_ON}",
           white_mix=clamp01(f"1.0 - {PA} * 8.0"), doc=["惑星の発光色（v.var による）"] * 3)

    f = new("hex", "add", "六角形のセル（縁が明るく中は淡い）。ちらついて点き、消える",
            "バリアの面（count と spread で球面に並べる）・ホログラム", "size 0.4〜1 / count 1〜24")
    S = f.S
    f.instant(f.v("count", 1))
    f.sphere(f.v("spread", 0.0, "球面の半径 (m)。0 なら全部中心"), "outwards", True)
    f.lifetime(f"{f.life(0.6)} * math.random(0.85, 1.15)")
    f.spin(f.v("rot", 0.0))
    f.bb([f"{S} * 0.6 * {clamp01(f'{PA} * 8.0')}"] * 2, "lookat_xyz", uv("hex"))
    f.tint(CYAN, f"{fade_io(8, 3)} * {FLICKER_ON}")
    f.cost = "count（既定 1）"

    f = new("scan", "add", "横一文字の走査線（目盛り付き）がエミッタから上へ v.height m 走る（カメラを向く）",
            "変身の走査・ホログラム・分析", "size 1〜2（幅 1.4 × size m）/ height 2 / life 0.6〜1", star=True)
    S = f.S
    H = f.v("height", 2.0, "走る距離 (m)。負なら下へ")
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.8))
    f.param([0, f"{H} * {ease(AGE)}", 0])
    f.bb([f"{S} * 1.4", f"{S} * 0.2"], "rotate_y", uv("scan"))
    f.tint(CYAN, fade_io(10, 4))
    f.cost = "1"

    # ================= 柱・光線 =================
    f = new("pillar", "add", "地面から立ち上がる光の柱（下端がエミッタ、上へ消える。縦軸のまわりでカメラを向く）",
            "天からの光・召喚・必殺の柱", "size 0.5〜3（幅）/ height 4〜12 / life 0.5〜1")
    S = f.S
    H = f.v("height", 6.0)
    hy = f"({H} * (0.6 + 0.4 * math.min({AGE} * 4.0, 1.0)))"
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.6))
    f.param([0, f"{hy} * 0.5", 0])
    f.bb([f"{S} * 0.9 * (0.35 + 0.65 * math.sin(math.min({AGE} * 3.0, 1.0) * 90.0)) * (1.15 - {AGE})", hy],
         "rotate_y", uv("pillar"))
    f.tint(CYAN, fade_out(1.5), whiten=2)
    f.cost = "1"

    f = new("beam", "add", "エミッタから (vx,vy,vz) の向きへ v.len m 伸びるまっすぐな光の帯。"
            "向きを軸にカメラへ回るのでどこから見ても帯に見える。太さが一瞬で立ち上がり、細って消える",
            "光線・レーザー・薙ぎ払い（毎 tick 出し直すか life を伸ばす）",
            "size 0.5〜3（太さ 0.5 × size m）/ len 4〜24 / life 0.2〜1", star=True)
    S = f.S
    dir_init(f, (0, 0, 1), "光線の向き（正規化する。長さは len で渡す。未指定は +Z）")
    f.init(f"v.e_len = {f.v('len', 8.0, '光線の長さ (m)')};")
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.3))
    f.param(["v.e_nx * v.e_len * 0.5", "v.e_ny * v.e_len * 0.5", "v.e_nz * v.e_len * 0.5"])
    f.bb(["v.e_len", f"{S} * 0.5 * math.min({AGE} * 10.0, 1.0) * (1.0 - math.pow({AGE}, 4.0)) * "
          f"(0.9 + 0.1 * math.sin({PA} * 2600.0))"], "lookat_direction", uv("beam"), dict(CUSTOM_N))
    f.tint(CYAN, clamp01(f"(1.0 - {AGE}) * 3.0"), whiten=2)
    f.cost = "1"

    # ================= 斬撃 =================
    def slash_fx(ident, sprite, mode, base, life_d, look, uses):
        f = new(ident, "add", look, uses, f"size 0.8〜3（直径 ≈ {base} × size m）/ life {life_d}")
        S = f.S
        f.instant(1)
        f.point()
        f.lifetime(f.life(life_d))
        f.spin(f.v("rot", 0.0, "振りの向き (度)。0 = 上の弧で左から右へ"))
        f.bb([f"{S} * {num(base)} * (0.85 + {AGE} * 0.35)"] * 2, mode, uv(sprite))
        f.tint(CYAN, clamp01(f"(1.0 - {AGE}) * 1.8"), whiten=3)
        f.cost = "1"
        return f

    slash_fx("slash", "slash", "lookat_xyz", 2.2, 0.24,
             "三日月の斬撃（白い外縁・後ろへ流れる筋）。カメラを向き、v.rot で振りの向きを変える",
             "通常攻撃・コンボの斬撃")
    slash_fx("slash_big", "slash_big", "lookat_xyz", 4.0, 0.4,
             "大きな三日月の斬撃（筋が 4 本、太い）", "必殺・大技の斬撃")
    slash_fx("slash_flat", "slash_big", "emitter_transform_xz", 3.2, 0.3,
             "水平の三日月の斬撃（地面と平行。v.rot = ヨー）", "回転斬り・薙ぎ払い・周囲の一閃")

    f = new("cross", "add", "十字（X 字）の斬撃と中心の閃光", "十字斬り・とどめ", "size 1〜3 / life 0.2〜0.35")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.28))
    f.spin(f.v("rot", 0.0))
    f.bb([f"{S} * 1.8 * (0.7 + {AGE} * 0.5)"] * 2, "lookat_xyz", uv("cross"))
    f.tint(CYAN, fade_out(1.6), whiten=3)
    f.cost = "1"

    f = new("thrust", "add", "突きの閃光: エミッタから (vx,vy,vz) へ v.len m のレンズ形の鋭い光（上下に細い筋）",
            "突き・刺突・槍", "size 0.5〜2（太さ 0.5 × size）/ len 2〜6 / life 0.15〜0.3", star=True)
    S = f.S
    dir_init(f, (0, 0, 1), DIR_NOTE)
    L = f.v("len", 3.0, "閃光の長さ (m)")
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.2))
    f.param([f"v.e_nx * {L} * (0.5 + 0.15 * {AGE})", f"v.e_ny * {L} * (0.5 + 0.15 * {AGE})",
             f"v.e_nz * {L} * (0.5 + 0.15 * {AGE})"])
    f.bb([f"{L} * (0.7 + 0.3 * math.min({AGE} * 6.0, 1.0))", f"{S} * 0.5 * (1.0 - {AGE})"],
         "lookat_direction", uv("thrust"), dict(CUSTOM_N))
    f.tint(CYAN, fade_out(1.5), whiten=3)
    f.cost = "1"

    # ================= 流れ =================
    f = new("speedline", "add", "細い速度線が (vx,vy,vz) の向きへ高速で流れる", "ダッシュ・突進・落下の風切り",
            "count 4〜10 / spread 0.5〜1.5")
    S = f.S
    dir_init(f, (0, 1, 0), "流れる向き（未指定は上）")
    f.instant(f.v("count", 6))
    f.sphere(f.v("spread", 0.8), list(N3))
    f.speed(f"{f.v('speed', 14.0)} * math.random(0.7, 1.3)")
    f.dyn(drag=3.0)
    f.lifetime(f"{f.life(0.25)} * math.random(0.6, 1.2)")
    f.bb([f"{S} * 1.1", f"{S} * 0.045"], "lookat_direction", uv("speedline"), VEL_DIR)
    f.tint((0.85, 0.95, 1.0), fade_out(1.6))
    f.cost = "count（既定 6）"

    f = new("wind", "add", "二本の弧の風切り（速度の向きに沿う）が流れる", "風・突風・回転の風", "count 3〜8")
    S = f.S
    dir_init(f, (0, 0, 1), "流れる向き（未指定は +Z）")
    f.instant(f.v("count", 4))
    f.sphere(f.v("spread", 0.8), list(N3))
    f.speed(f"{f.v('speed', 6.0)} * math.random(0.7, 1.3)")
    f.dyn(drag=2.4)
    f.lifetime(f"{f.life(0.4)} * math.random(0.6, 1.2)")
    f.bb([f"{S} * 1.0", f"{S} * 0.5"], "lookat_direction", uv("wind"), VEL_DIR)
    f.tint((0.85, 1.0, 0.95), f"0.85 * {fade_io(6, 2)}", whiten=2)
    f.cost = "count（既定 4）"

    f = new("vortex", "add", "竜巻: 風の筋が螺旋を描いて広がりながら v.height m 昇る（v.life 秒のあいだ出続ける）",
            "竜巻・渦・大赤斑・吸い上げ", "rate 40〜90 / life 0.6〜2 / spread 1〜2.5 / height 2〜5", star=True)
    S = f.S
    life_e = f.life(1.0, "放出する時間 (秒)。粒自体の寿命は 0.9 秒で固定")
    f.steady(f.v("rate", 70.0), 160, life_e)
    f.point()
    f.lifetime("0.9")
    th = f"({PA} * {f.v('spin', 540.0)} + {R1} * 360.0)"
    rr = f"({f.v('spread', 1.2, '渦の半径 (m)。上ほど広がる')} * (0.35 + 0.65 * {AGE}))"
    H = f.v("height", 3.5)
    f.param([f"math.cos({th}) * {rr}", f"{AGE} * {H}", f"math.sin({th}) * {rr}"])
    f.bb([f"{S} * 0.8 * (1.0 - {AGE} * 0.3)", f"{S} * 0.09"], "lookat_direction", uv("spark"),
         {"mode": "custom", "custom_direction": [f"0.0 - math.sin({th})", "0.35", f"math.cos({th})"]})
    f.tint(CYAN, fade_io(5, 3), whiten=2)
    f.cost = "rate × life（既定 70）、同時最大 160"

    f = new("converge", "add", "光の筋が半径 v.spread の球面から中心（エミッタ）へ加速しながら吸い込まれる",
            "溜め・チャージ・吸収", "count 10〜24 / spread 1〜3 / life 0.4〜0.8", star=True)
    S = f.S
    f.instant(f.v("count", 16))
    f.point()
    f.lifetime(f.life(0.5))
    U = [f"({r} * 2.0 - 1.0)" for r in (R1, R2, R3)]
    n = f"math.max(math.sqrt({U[0]} * {U[0]} + {U[1]} * {U[1]} + {U[2]} * {U[2]}), 0.05)"
    spd = f.v("spread", 2.0, "吸い込み始める球の半径 (m)")
    f.param([f"{u} / {n} * {spd} * (1.0 - {AGE} * {AGE})" for u in U])
    f.bb([f"{S} * 0.5 * (1.0 - {AGE} * 0.5)", f"{S} * 0.05"], "lookat_direction", uv("spark"),
         {"mode": "custom", "custom_direction": [f"0.0 - {u}" for u in U]})
    f.tint(CYAN, fade_io(5, 4), whiten=1)
    f.cost = "count（既定 16）"

    f = new("orbit", "add", "光の筋が傾いた軌道で中心のまわりを回りながら螺旋状に縮む", "溜め・集中・衛星",
            "count 6〜16 / spread 1〜2 / life 0.6〜1.2", star=True)
    S = f.S
    f.instant(f.v("count", 10))
    f.point()
    f.lifetime(f.life(0.8))
    th = f"({PA} * {f.v('spin', 420.0, '周回の速さ (度/秒)')} + {R1} * 360.0)"
    ph = f"(({R2} - 0.5) * 80.0)"
    ps = f"({R3} * 360.0)"
    R = f"({f.v('spread', 1.5, '軌道の半径 (m)')} * (1.0 - 0.8 * math.pow({AGE}, 1.5)))"
    ct, st = f"math.cos({th})", f"math.sin({th})"
    cf, sf, cp, s_p = f"math.cos({ph})", f"math.sin({ph})", f"math.cos({ps})", f"math.sin({ps})"
    f.param([f"{R} * ({ct} * {cp} + {st} * {cf} * {s_p})", f"{R} * (0.0 - {st} * {sf})",
             f"{R} * ({st} * {cf} * {cp} - {ct} * {s_p})"])
    f.bb([f"{S} * 0.34", f"{S} * 0.07"], "lookat_direction", uv("spark"),
         {"mode": "custom", "custom_direction": [f"{ct} * {cf} * {s_p} - {st} * {cp}", f"0.0 - {ct} * {sf}",
                                                 f"{ct} * {cf} * {cp} + {st} * {s_p}"]})
    f.tint(CYAN, fade_io(5, 2.5), whiten=1)
    f.cost = "count（既定 10）"

    f = new("aura", "add", "足元の円から炎の舌のような闘気が立ち昇る（縦軸のまわりでカメラを向く）",
            "変身中の常時演出・強化・溜め", "count 4〜10 / spread 0.4〜0.8")
    S = f.S
    f.instant(f.v("count", 6))
    f.disc(f.v("spread", 0.5))
    f.speed(0.2)
    f.dyn((0, 2.6, 0), 1.2)
    f.lifetime(f"{f.life(0.7)} * math.random(0.6, 1.2)")
    f.bb([f"{S} * 0.24 * (1.0 - {AGE} * 0.6)", f"{S} * 0.55 * (1.0 - {AGE} * 0.3)"], "rotate_y", uv("flame", 2))
    f.tint(CYAN, fade_io(6, 2), whiten=1)
    f.cost = "count（既定 6）"

    # ================= ナノマシン =================
    NANO_UV = uv_pick("nano", f"{R4} * 3.999", 4)
    blink = f"(0.55 + 0.45 * (math.sin({PA} * 1500.0 + {R4} * 1000.0) > 0.0 ? 1.0 : 0.0))"
    f = new("nano", "add", "ナノマシンの粒（小さな四角・菱形・十字・チップが明滅）。散らばった位置から "
            "(vx,vy,vz) のずれの点へ v.life 秒で弧を描いて集まる。speed で外へ流れる成分を足せる",
            "ナノマシンの集合・解除でコアへ還る・修復", "count 10〜30 / spread 0.5〜1.5 / life 0.4〜1", star=True)
    S = f.S
    target_init(f, (0, 0.8, 0), "集まる点（エミッタからのずれ m）。3 つとも未指定なら (0, 0.8, 0)")
    f.instant(f.v("count", 16))
    f.point()
    f.lifetime(f.life(0.6))
    sp = f.v("spread", 0.8, "散らばる立方体の半径 (m)")
    spd = f.v("speed", 0.0, "外へ流れる速さ (m/s)。0 なら集まるだけ")
    e = ease(AGE)
    st = [f"({r} * 2.0 - 1.0)" for r in (R1, R2, R3)]
    f.param([f"{st[0]} * {sp} * (1.0 - {e}) + v.e_tx * {e} + {st[0]} * {spd} * {PA}",
             f"{st[1]} * {sp} * (1.0 - {e}) + v.e_ty * {e} + {st[1]} * {spd} * {PA} + "
             f"math.sin({AGE} * 180.0) * 0.3 * {sp}",
             f"{st[2]} * {sp} * (1.0 - {e}) + v.e_tz * {e} + {st[2]} * {spd} * {PA}"])
    f.bb([f"{S} * 0.09 * (0.75 + 0.25 * math.sin({PA} * 1800.0 + {R4} * 720.0))"] * 2, "lookat_xyz", NANO_UV)
    f.tint(CYAN, f"{fade_io(8, 4)} * {blink}", whiten=1.5)
    f.cost = "count（既定 16）"

    f = new("nano_stream", "add", "ナノマシンの奔流: 粒の列が三本の螺旋を描きながら、エミッタから "
            "(vx,vy,vz) のずれの点へ流れ込む。最初の粒は v.life 秒で着き、count / rate 秒のあいだ出続ける",
            "変身の奔流（コア → 各部位）・ナノの移送・吸収",
            "count 24〜60 / rate 50〜100 / life 0.4〜0.9 / spread 0.2〜0.6", star=True)
    S = f.S
    target_init(f, (0, 2.0, 0), "流れ込む先（エミッタからのずれ m）。3 つとも未指定なら (0, 2, 0)")
    rate = f.v("rate", 72.0)
    f.steady(rate, 120, f"{f.v('count', 36.0, '流す粒の総数（放出時間 = count / rate 秒）')} / math.max({rate}, 1.0)")
    f.point()
    f.lifetime(f.life(0.6, "1 粒が流れ着くまでの時間 (秒)"))
    e = ease(AGE)
    th = f"({PA} * {f.v('spin', 900.0, '螺旋の回る速さ (度/秒)')} + math.floor({R1} * 2.999) * 120.0)"
    rad = f"({f.v('spread', 0.35, '螺旋の半径 (m)')} * math.sin({AGE} * 180.0) * (0.85 + 0.3 * {R3}))"
    f.param([f"v.e_t{c} * {e} + {rad} * (math.cos({th}) * v.e_a{c} + math.sin({th}) * v.e_b{c})"
             for c in "xyz"])
    f.bb([f"{S} * 0.11 * (0.75 + 0.25 * math.sin({PA} * 1800.0 + {R4} * 720.0))"] * 2, "lookat_xyz",
         uv_pick("nano", f"{R2} * 3.999", 4))
    f.tint(CYAN, f"{fade_io(10, 6)} * {blink}", whiten=1)
    f.cost = "count（既定 36）、同時最大 120"

    # ================= 煙・土・破片 =================
    f = new("smoke", "blend", "灰色の煙の塊が膨らみながら昇る（半透明）", "爆発の後・焦げ・排気",
            "count 4〜10 / size 0.8〜2")
    S = f.S
    f.instant(f.v("count", 6))
    f.sphere(f.v("spread", 0.5))
    f.speed(f"{f.v('speed', 1.2)} * math.random(0.0, 1.0)")
    f.dyn((0, 0.8, 0), 2.0)
    f.spin("math.random(0.0, 360.0)", "math.random(-20.0, 20.0)")
    f.lifetime(f"{f.life(1.0)} * math.random(0.6, 1.2)")
    f.bb([f"{S} * (0.4 + {AGE} * 0.9) * (0.8 + 0.4 * {R2})"] * 2, "lookat_xyz",
         uv_pick("smoke", f"{R1} * 1.999", 2))
    f.tint(SMOKE, f"0.75 * {fade_io(8, 1.4)}")
    f.cost = "count（既定 6）"

    f = new("dust", "blend", "土煙が地面に沿って輪状に広がる（半透明）", "着地・叩きつけ・突進の踏み込み",
            "count 8〜20 / spread 0.4〜1.5")
    S = f.S
    f.instant(f.v("count", 12))
    f.disc(f.v("spread", 0.6))
    f.speed(f"{f.v('speed', 5.0)} * math.random(0.5, 1.0)")
    f.dyn((0, 0.3, 0), 3.5)
    f.spin("math.random(0.0, 360.0)", "math.random(-30.0, 30.0)")
    f.lifetime(f"{f.life(0.8)} * math.random(0.6, 1.2)")
    f.bb([f"{S} * (0.35 + {AGE} * 0.6) * (0.8 + 0.4 * {R2})"] * 2, "lookat_xyz",
         uv_pick("smoke", f"{R1} * 1.999", 2))
    f.tint(DUST, f"0.7 * {fade_io(10, 1.3)}")
    f.cost = "count（既定 12）"

    f = new("debris", "blend", "岩の破片（4 種）が上へ跳ね、回りながら重力で落ちて地面で跳ねる",
            "叩きつけ・噴火・隕石の着弾", "count 6〜14 / speed 5〜10", star=True)
    S = f.S
    f.instant(f.v("count", 8))
    f.point(direction=["math.random(-1.0, 1.0)", "math.random(0.3, 1.6)", "math.random(-1.0, 1.0)"])
    f.speed(f"{f.v('speed', 7.0)} * math.random(0.5, 1.0)")
    f.dyn((0, f.v("grav", -16.0), 0), 0.3)
    f.collide(6.0, 0.3, 0.08)
    f.spin("math.random(0.0, 360.0)", "math.random(-540.0, 540.0)")
    f.lifetime(f"{f.life(1.4)} * math.random(0.8, 1.2)")
    f.bb([f"{S} * 0.22 * (0.6 + 0.8 * {R1})"] * 2, "lookat_xyz", uv_pick("debris", f"{R2} * 3.999", 4))
    f.tint(ROCK, clamp01(f"(1.0 - {AGE}) * 4.0"))
    f.cost = "count（既定 8）。地形との衝突あり"

    # ================= 火・プラズマ =================
    f = new("ember", "add", "火の粉が揺らめきながら舞い上がる", "炎の周り・溶岩・太陽", "count 6〜16")
    S = f.S
    f.instant(f.v("count", 8))
    f.sphere(f.v("spread", 0.6))
    f.speed(f"{f.v('speed', 1.0)} * math.random(0.0, 1.0)")
    f.dyn((0, 1.8, 0), 0.8)
    f.lifetime(f"{f.life(1.2)} * math.random(0.5, 1.3)")
    f.bb([f"{S} * 0.07 * (0.7 + 0.3 * math.sin({PA} * 1400.0 + {R1} * 360.0))"] * 2, "lookat_xyz", uv("dot"))
    f.tint(FIRE, fade_io(6, 2), whiten=1.5)
    f.cost = "count（既定 8）"

    f = new("flame", "add", "アニメ調の炎の舌（8 コマのパラパラ）が揺れて昇り、千切れて消える",
            "炎・スラスター・紅炎", "count 3〜10 / size 0.6〜2")
    S = f.S
    f.instant(f.v("count", 6))
    f.sphere(f.v("spread", 0.4))
    f.speed(f"{f.v('speed', 1.5)} * math.random(0.0, 1.0)")
    f.dyn((0, 3.0, 0), 2.0)
    f.lifetime(f"{f.life(0.6)} * math.random(0.6, 1.2)")
    f.bb([f"{S} * 0.42 * (1.0 - {AGE} * 0.3)", f"{S} * 0.56 * (1.0 - {AGE} * 0.2)"], "rotate_y",
         flipbook("flame", 8))
    f.tint(FIRE, fade_io(10, 1.5), whiten=2.5)
    f.cost = "count（既定 6）"

    f = new("plasma", "add", "三本腕のプラズマの渦（重ねた 3 枚が別々の速さで回る）", "雷球・太陽の核・エネルギー弾",
            "size 0.5〜3 / life 0.3〜1")
    S = f.S
    f.instant(f.v("count", 3, "重ねる枚数"))
    f.point()
    f.lifetime(f.life(0.5))
    f.spin("math.random(0.0, 360.0)", f"math.random(-1.0, 1.0) * {f.v('spin', 600.0, '回転の速さの最大 (度/秒)')}")
    f.dyn()
    f.bb([f"{S} * 1.1 * (0.6 + 0.5 * {AGE})"] * 2, "lookat_xyz", uv("plasma"))
    f.tint((1.0, 0.62, 0.25), f"0.9 * {fade_io(8, 2.2)}", whiten=2)
    f.cost = "count（既定 3）"

    # ================= 雷 =================
    f = new("bolt", "add", "稲妻: エミッタから (vx,vy,vz) の向きへ v.len m のぎざぎざの雷光（3 種の形が"
            "ちらついて入れ替わる。向きを軸にカメラへ回る）",
            "落雷（地面の点から上へ len 12）・連鎖放電（A から B へ、向き = B − A、len = 距離）",
            "size 0.5〜2（幅 1.2 × size m）/ len 2〜16 / life 0.15〜0.3", star=True)
    S = f.S
    dir_init(f, (0, 1, 0), "雷光の向き（正規化する。未指定は上 = 地面の点から空へ）")
    f.init(f"v.e_len = {f.v('len', 6.0, '雷光の長さ (m)')};")
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.22))
    f.param(["v.e_nx * v.e_len * 0.5", "v.e_ny * v.e_len * 0.5", "v.e_nz * v.e_len * 0.5"])
    idx = f"math.mod({f.v('var', f'({PA} * 30.0 + v.emitter_random_1 * 3.0)', '形 0..2 を固定（未指定なら時間で入れ替わる）', doc_default='時間で切り替え')}, 3.0)"
    f.bb(["v.e_len", f"{S} * 1.2"], "lookat_direction", uv_pick("bolt", idx, 3), dict(CUSTOM_N))
    f.tint(ELEC, f"(math.mod(math.floor({PA} * 40.0), 2.0) > 0.5 ? 0.5 : 1.0) * {fade_out(1.3)}", whiten=1.2)
    f.cost = "1"

    f = new("arc", "add", "放電のちらつき: 短いぎざぎざの電光（4 種）が瞬いて入れ替わる", "帯電・感電・テスラコイル",
            "count 2〜6 / spread 0.2〜1")
    S = f.S
    sp = f.v("spread", 0.4)
    f.instant(f.v("count", 3))
    f.point([rnd(sp), rnd(sp), rnd(sp)])
    f.spin("math.random(0.0, 360.0)")
    f.lifetime(f"{f.life(0.2)} * math.random(0.7, 1.3)")
    f.bb([f"{S} * 0.6"] * 2, "lookat_xyz", uv_pick("arc", f"math.mod({PA} * 24.0 + {R1} * 4.0, 4.0)", 4))
    f.tint(ELEC, f"(math.mod(math.floor({PA} * 30.0), 2.0) > 0.5 ? 0.6 : 1.0) * {fade_out(1.5)}", whiten=1)
    f.cost = "count（既定 3）"

    # ================= 結晶 =================
    f = new("shard", "add", "光る結晶片が回りながら飛び散り、重力で落ちる", "砕ける・結晶・ガラス",
            "count 6〜14 / speed 4〜9")
    S = f.S
    f.instant(f.v("count", 8))
    f.sphere(f.v("spread", 0.2))
    f.speed(f"{f.v('speed', 6.0)} * math.random(0.4, 1.2)")
    f.dyn((0, f.v("grav", -16.0), 0), 1.0)
    f.spin("math.random(0.0, 360.0)", "math.random(-720.0, 720.0)")
    f.lifetime(f"{f.life(0.7)} * math.random(0.6, 1.2)")
    f.bb([f"{S} * 0.14", f"{S} * 0.3"], "lookat_xyz", uv("shard"))
    f.tint(ICE, fade_out(1.6), whiten=4)
    f.cost = "count（既定 8）"

    f = new("ice", "blend", "六本腕の氷晶（面ごとの濃淡）が回りながら散って落ちる", "凍結・氷の破砕・天王星",
            "count 4〜10 / size 0.6〜2")
    S = f.S
    f.instant(f.v("count", 6))
    f.sphere(f.v("spread", 0.3))
    f.speed(f"{f.v('speed', 4.0)} * math.random(0.3, 1.0)")
    f.dyn((0, f.v("grav", -9.0), 0), 1.2)
    f.spin("math.random(0.0, 360.0)", "math.random(-360.0, 360.0)")
    f.lifetime(f"{f.life(0.9)} * math.random(0.7, 1.2)")
    f.bb([f"{S} * 0.32 * (0.7 + 0.6 * {R1})"] * 2, "lookat_xyz", uv("ice"))
    f.tint(ICE, fade_io(12, 2))
    f.cost = "count（既定 6）"

    f = new("diamond", "blend", "ダイヤ（ブリリアントカット）が回りながら散り、時々白く煌めく",
            "ダイヤモンド・レイン・宝石・結晶の雨", "count 4〜12 / grav -9.8（雨なら speed 0 で高所から）")
    S = f.S
    f.instant(f.v("count", 6))
    f.sphere(f.v("spread", 0.5))
    f.speed(f"{f.v('speed', 3.0)} * math.random(0.3, 1.0)")
    f.dyn((0, f.v("grav", -9.8), 0), 0.6)
    f.spin("math.random(0.0, 360.0)", "math.random(-240.0, 240.0)")
    f.lifetime(f"{f.life(1.0)} * math.random(0.8, 1.2)")
    f.bb([f"{S} * 0.3"] * 2, "lookat_xyz", uv("diamond"))
    f.tint((0.82, 1.0, 1.0), fade_io(12, 2.5),
           white_mix=f"(math.pow(math.max(math.sin({PA} * 500.0 + {R3} * 360.0), 0.0), 12.0) * 0.7)")
    f.cost = "count（既定 6）"

    # ================= 液体 =================
    f = new("droplet", "blend", "液体金属の滴（上が照り返し・下が暗い球、速度の向きに伸びる）が飛び散って落ちる",
            "水銀・液体・血しぶきの代わり", "count 6〜16 / speed 3〜7")
    S = f.S
    f.instant(f.v("count", 10))
    f.sphere(f.v("spread", 0.2))
    f.speed(f"{f.v('speed', 4.0)} * math.random(0.5, 1.2)")
    f.dyn((0, f.v("grav", -14.0), 0), 0.5)
    f.lifetime(f"{f.life(0.7)} * math.random(0.7, 1.2)")
    f.bb([f"{S} * 0.2", f"{S} * 0.13"], "lookat_direction", uv("droplet"), VEL_DIR)
    f.tint(MERCURY, fade_out(3.0))
    f.cost = "count（既定 10）"

    f = new("splash", "blend", "水しぶきの王冠（底の楕円 + 立ち上がる棘と滴）が足元から跳ね上がる",
            "着水・水の着弾・間欠泉の根元", "size 0.6〜3 / life 0.35〜0.6")
    S = f.S
    sp = f.v("spread", 0.0, "複数出す時の散らばり (m)")
    f.instant(f.v("count", 1))
    f.point()
    f.lifetime(f.life(0.45))
    hy = f"({S} * 1.0 * (0.4 + 0.8 * math.sqrt({AGE})))"
    f.param([f"({R1} * 2.0 - 1.0) * {sp}", f"{hy} * 0.5", f"({R2} * 2.0 - 1.0) * {sp}"])
    f.bb([f"{S} * 1.2 * (0.5 + 0.7 * math.sqrt({AGE}))", hy], "rotate_y", uv("splash"))
    f.tint(WATER, fade_out(1.8))
    f.cost = "count（既定 1）"

    f = new("bubble", "add", "泡がゆらゆら揺れながら昇り、最後に膨らんで弾ける", "水中・海王星・酸",
            "count 4〜14 / spread 0.4〜1.2")
    S = f.S
    f.instant(f.v("count", 8))
    f.sphere(f.v("spread", 0.6))
    f.speed(f"{f.v('speed', 0.4)} * math.random(0.0, 1.0)")
    f.dyn((0, 1.5, 0), 1.5)
    f.lifetime(f"{f.life(1.2)} * math.random(0.6, 1.2)")
    base = f"({S} * 0.16 * (0.6 + 0.8 * {R1}) * ({AGE} > 0.92 ? 1.35 : 1.0))"
    wob = f"math.sin({PA} * 900.0 + {R2} * 360.0)"
    f.bb([f"{base} * (1.0 + 0.08 * {wob})", f"{base} * (1.0 - 0.08 * {wob})"], "lookat_xyz", uv("bubble"))
    f.tint(WATER, f"{fade_io(10, 1.0)} * ({AGE} > 0.92 ? 0.6 : 1.0)")
    f.cost = "count（既定 8）"

    f = new("wave", "blend", "波頭: 泡の縁を持つ弧の水の壁が (vx,vy,vz) の向きへ進み、立ち上がってから崩れる。"
            "壁の面は進む向きを向く（横から見ると薄い）",
            "潮汐斬・津波・水の斬撃（横に並べると幅が出る）",
            "size 1〜3（幅 3.2 × size m）/ speed 6〜14 / life 0.6〜1.2", star=True)
    S = f.S
    dir_init(f, (0, 0, 1), "進む向き（未指定は +Z）")
    f.instant(1)
    f.point([0, f"{S} * 0.6", 0], list(N3))
    f.speed(f.v("speed", 8.0))
    f.dyn(drag=0.8)
    f.lifetime(f.life(0.9))
    f.bb([f"{S} * 3.2 * (0.75 + 0.45 * {AGE})",
          f"{S} * 1.4 * (0.4 + 0.6 * math.sin(math.clamp({AGE} * 1.6, 0.0, 1.0) * 180.0))"],
         "direction_z", uv("wave"), dict(CUSTOM_N))
    f.tint(WATER, fade_io(12, 2.5))
    f.cost = "1"

    # ================= 雲・オーロラ・隕石 =================
    f = new("cloud", "blend", "アニメ調の雲（明るい上面と影の二色）がゆっくり膨らみながら (vx,vy,vz) m/s で漂う",
            "硫酸雲・毒霧・砂嵐の塊（life を伸ばして置いておく）",
            "count 3〜8 / spread 0.8〜2.5 / life 2〜6", star=True)
    S = f.S
    target_init(f, (0.15, 0.06, 0.0), "漂う速度 (m/s)。3 つとも未指定なら (0.15, 0.06, 0)")
    f.instant(f.v("count", 5))
    f.point()
    f.lifetime(f"{f.life(4.0)} * math.random(0.9, 1.1)")
    sp = f.v("spread", 1.2, "塊を置く範囲の半径 (m)。縦は半分")
    st = [f"({R1} * 2.0 - 1.0) * {sp}", f"({R2} * 2.0 - 1.0) * {sp} * 0.45", f"({R3} * 2.0 - 1.0) * {sp}"]
    f.param([f"{st[i]} * (1.0 + 0.25 * {AGE}) + v.e_t{c} * {PA}" for i, c in enumerate("xyz")],
            rotation=f"{R4} * 360.0 + {PA} * {f.v('spin', 10.0)}")
    f.bb([f"{S} * 1.6 * (0.8 + 0.5 * {AGE}) * (0.7 + 0.6 * {R4})"] * 2, "lookat_xyz", uv("cloud"))
    f.tint(SULFUR, f"0.85 * {fade_abs(0.4, 0.8)}")
    f.cost = "count（既定 5）"

    f = new("aurora", "add", "オーロラの幕: 縦の光条の帯がエミッタを囲む半径 v.spread の輪に並び、"
            "高さ v.height で揺らぎながらゆっくり回る（縦軸のまわりでカメラを向く）",
            "地球の変身・癒やしの幕・必殺の背景", "count 8〜16 / spread 1.5〜4 / height 3〜6 / life 2〜4",
            star=True)
    S = f.S
    f.instant(f.v("count", 14, "帯の数"))
    f.point()
    f.lifetime(f"{f.life(2.5)} * math.random(0.85, 1.15)")
    H = f.v("height", 4.0)
    a = f"({R1} * 360.0 + {PA} * {f.v('spin', 8.0, '輪が回る速さ (度/秒)')})"
    R = f"({f.v('spread', 2.2, '幕の輪の半径 (m)。0 なら中心に一本')} * (1.0 + 0.06 * math.sin({PA} * 90.0 + {R2} * 360.0)))"
    f.param([f"math.cos({a}) * {R}", f"{H} * 0.5 + 0.15 * math.sin({PA} * 120.0 + {R3} * 360.0)",
             f"math.sin({a}) * {R}"])
    f.bb([f"{S} * 1.8 * (0.8 + 0.4 * {R4})", f"{H} * (0.85 + 0.15 * math.sin({PA} * 150.0 + {R2} * 360.0))"],
         "rotate_y", uv("aurora"))
    f.tint(AURORA, f"0.8 * {fade_abs(0.5, 0.8)} * (0.75 + 0.25 * math.sin({PA} * 200.0 + {R4} * 360.0))")
    f.cost = "count（既定 14）"

    f = new("meteor", "add", "尾を引く火球: 白熱した頭（火球）と、頭から (vx,vy,vz) の逆向きへ伸びる長さの違う"
            "炎の筋の重なり（頭側ほど太く明るい尾）。speed を与えると向きへ飛ぶ（既定は止まった一枚絵 → 毎 tick 位置を"
            "変えて出す）。筋は向きを軸にカメラへ回る",
            "隕石・彗星・火の弾", "size 0.5〜3 / len 2〜8 / speed 0（毎 tick）or 10〜30 / life 0.2〜1",
            star=True)
    S = f.S
    dir_init(f, (0.4, -1.0, 0.0), "飛ぶ向き（頭の向き。未指定は斜め下）")
    f.init(f"v.e_len = {f.v('len', f'{S} * 3.0', '尾の長さ (m)', doc_default='size × 3')};")
    f.instant(f.v("count", 12, "粒の数（約 1/3 が頭、残りが尾の筋）"))
    f.point()
    f.lifetime(f.life(0.3))
    head = f"({R1} < 0.34)"
    spd = f.v("speed", 0.0, "飛ぶ速さ (m/s)。0 ならその場")
    tl = f"(v.e_len * (0.45 + 0.55 * {R2}))"
    jit = [f"({R3} * 2.0 - 1.0)", f"({R4} * 2.0 - 1.0)", f"({R3} + {R4} - 1.0)"]
    f.param([f"v.e_n{c} * ({spd} * {PA} - ({head} ? 0.0 : {tl} * 0.5)) + {jit[i]} * 0.08 * {S}"
             for i, c in enumerate("xyz")],
            rotation=f"({head} ? ({R4} * 360.0 + {PA} * 240.0) : 0.0)")
    f.bb([f"({head} ? {S} * 0.95 : {tl}) * (1.0 - 0.2 * {AGE})",
          f"({head} ? {S} * 0.95 : {S} * (0.22 + 0.4 * {R3})) * (1.0 - 0.2 * {AGE})"], "lookat_direction",
         uv_choice([("fireball", None), ("streak", None)], f"({head} ? 0.0 : 1.0)"), dict(CUSTOM_N))
    f.tint(FIRE, f"({head} ? 1.0 : 0.75) * {fade_out(2.0)}", white_mix=f"({head} ? 0.75 : 0.12)")
    f.cost = "count（既定 12）"

    # ================= 虚空 =================
    f = new("black_hole", "blend", "ブラックホール: 黒い核（染まらない）+ 光子の輪 + 渦巻く降着円盤 + 淡い外光の一枚絵が"
            "回る。現れて縮んで消える。加算の光を足すなら同じ点に lens を重ねる",
            "重力の井戸・吸引・ネメシスの技", "size 0.5〜3（直径 3 × size m）/ life 1〜5")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(2.0))
    f.spin("math.random(0.0, 360.0)", f.v("spin", 90.0))
    f.dyn()
    f.bb([f"{S} * 3.0 * {clamp01(f'{PA} * 4.0')} * math.sqrt({clamp01(f'(v.particle_lifetime - {PA}) * 4.0')})"]
         * 2, "lookat_xyz", uv("black_hole"))
    f.tint(VIOLET, fade_abs(0.1, 0.12))
    f.cost = "1"

    f = new("void", "blend", "紫黒の裂け目と触手（中は暗く縁だけ光る）がうごめく", "敵（ヴォイド）の攻撃・出現・死",
            "count 1〜5 / size 0.8〜3")
    S = f.S
    sp = f.v("spread", 0.3)
    f.instant(f.v("count", 3))
    f.point([rnd(sp), rnd(sp), rnd(sp)])
    f.spin("math.random(0.0, 360.0)", "math.random(-40.0, 40.0)")
    f.dyn()
    f.lifetime(f"{f.life(1.2)} * math.random(0.8, 1.2)")
    f.bb([f"{S} * 1.6 * (0.75 + 0.35 * {AGE}) * (0.8 + 0.4 * {R1})"] * 2, "lookat_xyz", uv("void"))
    f.tint(VOID, f"0.9 * {fade_io(5, 2.5)}")
    f.cost = "count（既定 3）"

    f = new("warning", "blend", "攻撃予告: 地面に赤い縞の輪・内向きの警告三角・中央の ! が点滅する（最後ほど速く）",
            "敵の範囲攻撃の予告（life = 予告の秒数）", "size 1〜5（直径 2.4 × size m）/ life 0.6〜2")
    S = f.S
    f.instant(1)
    f.point([0, 0.06, 0])
    f.lifetime(f.life(1.0, "予告の時間 (秒)"))
    f.spin(f.v("rot", 0.0), f.v("spin", 45.0))
    f.dyn()
    f.bb([f"{S} * 2.4 * {clamp01(f'{PA} * 8.0')}"] * 2, "emitter_transform_xz", uv("warning"))
    f.tint(RED, f"(0.6 + 0.4 * math.mod(math.floor({PA} * (6.0 + 14.0 * {AGE})), 2.0)) * "
                f"{clamp01(f'(v.particle_lifetime - {PA}) * 6.0')}")
    f.cost = "1"

    f = new("afterimage", "add", "装甲の人型シルエットの残像（足元がエミッタ、高さ 2 × size m。縦軸のまわりでカメラを向く）",
            "高速移動の残像・分身・ジャスト回避", "size 0.9〜1.1 / life 0.3〜0.6")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.4))
    f.param([0, f"{S} * 1.0", 0])
    f.bb([f"{S} * 1.0", f"{S} * 2.0"], "rotate_y", uv("afterimage"))
    f.tint(CYAN, f"0.8 * {clamp01(f'1.0 - {AGE}')}")
    f.cost = "1"

    # ================= 1 回の spawn で形を描く（追加） =================
    shapes = [("glow", None), ("star", None), ("nano", f"{R4} * 3.999"), ("hex", None), ("dot", None)]
    var_note = "粒の種類: 0 発光の玉 / 1 きらめき / 2 ナノマシン / 3 六角 / 4 小さな点"
    f = new("ring_n", "add", "粒の輪: count 個の光の粒を半径 spread の円周に散らして並べる（1 回の spawn で輪が描ける）。"
            "輪の面の法線 = (vx,vy,vz)（既定は上 = 水平の輪）。speed で外へ広がる。粒の種類は v.var",
            "fx.js の ring() を 1 パケットで（範囲の縁・衝撃の輪・変身の輪）",
            "count 12〜40 / spread 0.5〜6 / life 0.3〜1")
    S = f.S
    target_init(f, (0, 1, 0), "輪の面の法線（向き。正規化する。未指定は上 = 水平の輪）")
    f.instant(f.v("count", 32))
    f.point()
    f.lifetime(f"{f.life(0.5)} * math.random(0.85, 1.15)")
    a = f"({R1} * 360.0)"
    rr = f"({f.v('spread', 1.5, '輪の半径 (m)')} + {f.v('speed', 0.0, '外へ広がる速さ (m/s)')} * {PA})"
    f.param([f"{rr} * (math.cos({a}) * v.e_a{c} + math.sin({a}) * v.e_b{c})" for c in "xyz"])
    vidx = f.v("var", 0.0, var_note)
    f.bb([f"{S} * 0.16 * (1.0 - {AGE} * 0.5)"] * 2, "lookat_xyz", uv_choice(shapes, vidx))
    f.tint(CYAN, fade_out(1.6), whiten=3)
    f.cost = "count（既定 32）"

    f = new("line_n", "add", "粒の線: count 個の光の粒をエミッタから (vx,vy,vz) のずれの点までの線分上に散らして並べる"
            "（1 回の spawn で線・軌跡が描ける）。spread で線の太さ。粒の種類は v.var",
            "fx.js の line() を 1 パケットで（軌跡・射線・鎖・連鎖の線）",
            "count 8〜40（長さ 1 m あたり 3〜5）/ life 0.2〜0.6")
    S = f.S
    target_init(f, (0, 0, 4), "線の終点（エミッタからのずれ m）。3 つとも未指定なら (0, 0, 4)")
    f.instant(f.v("count", 16))
    f.point()
    f.lifetime(f"{f.life(0.35)} * math.random(0.8, 1.2)")
    j = f.v("spread", 0.0, "線の太さ（横へのばらつき m）")
    f.param([f"v.e_t{c} * {R1} + (({R2} * 2.0 - 1.0) * v.e_a{c} + ({R3} * 2.0 - 1.0) * v.e_b{c}) * {j}"
             for c in "xyz"])
    vidx = f.v("var", 0.0, var_note)
    f.bb([f"{S} * 0.16 * (1.0 - {AGE} * 0.5)"] * 2, "lookat_xyz", uv_choice(shapes, vidx))
    f.tint(CYAN, fade_out(1.6), whiten=3)
    f.cost = "count（既定 16）"

    f = new("lens", "add", "大きく淡い光のにじみ（ゴーストの輪と六角のぼけ）", "必殺の締め・大爆発の光・black_hole の加算層",
            "size 1〜5（直径 4 × size m）/ life 0.4〜1")
    S = f.S
    f.instant(1)
    f.point()
    f.lifetime(f.life(0.6))
    f.bb([f"{S} * 4.0 * (0.6 + 0.6 * math.sqrt({AGE}))"] * 2, "lookat_xyz", uv("lens"))
    f.tint(WHITE, f"0.85 * {fade_out(1.2)}", whiten=1.5)
    f.cost = "1"
    return E


# ===========================================================================
#  PARTICLES.md
# ===========================================================================
MAT_JA = {"add": "加算（光る）", "blend": "半透明（色が乗る・暗くもできる）"}


def write_doc(E):
    L = []
    w = L.append
    w("# アストロ・ナノギア パーティクル一覧（PARTICLES.md）")
    w("")
    w("`tools/astro/gen_astro_particles.py` が生成する。**このファイルは手で直さない**（生成スクリプトを直して作り直す）。")
    w("惑星の技の演出はこの表だけを見て書けるようにしてある。")
    w("")
    w("## 使い方")
    w("")
    w("```js")
    w("const m = new MolangVariableMap();")
    w("m.setFloat(\"variable.cr\", 0.47); m.setFloat(\"variable.cg\", 0.94); m.setFloat(\"variable.cb\", 1.0);")
    w("m.setFloat(\"variable.size\", 2.0);")
    w("dim.spawnParticle(\"astro:ring_flat\", pos, m);   // fx.js の P() がこれを包む")
    w("```")
    w("")
    w("* 変数は全て任意。渡さなければ下の表の既定値になる（変数無しでも見栄えがする既定にしてある）。")
    w("  変数名は必ず `variable.` を付けて setFloat する（`v.` ではない）。")
    w("* **色** `cr cg cb` は 0..1。スプライトは白で描いてあり、`particle_appearance_tinting` でこの色に染める。")
    w("  多くの発光は生まれた瞬間だけ白く光ってから色に落ちる（表の「白→色」）。")
    w("* **size** は倍率。各粒の「基準の大きさ」は個別の欄に書いた m（size 1 の時）。")
    w("* **life** は粒の寿命（秒）。連続で出す粒（vortex・nano_stream）は欄に書いた意味になる。")
    w("* **vx vy vz** の意味は粒ごとに違う（**向き**か**終点のずれ m**か**速度 m/s**か）。向きとして使う粒は内部で"
      "正規化するので長さは関係無い（長さは `len` で渡す）。3 つとも 0 か未指定なら既定の向き/点になる。"
      "1 つだけ渡すと残りは 0 として扱う。")
    w("* 向きのある粒（beam・bolt・thrust・meteor・circle_v・wave）は **ワールド座標の向き** をそのまま渡す"
      "（`p.getViewDirection()` や `B − A`）。")
    w("* 「水平」の粒（ring_flat・shock_flat・circle・hex_circle・emblem・slash_flat・warning）は地面と平行"
      "（emitter_transform_xz。スクリプトから出すエミッタは回転しないので常にワールドの水平面）。"
      "地面に置く時は y を +0.05〜0.1 上げると埋まらない。")
    w("* 「加算」は光る（暗い所ほど目立つ。黒は描けない）。「半透明」は色がそのまま乗る（煙・雲・岩・警告）。")
    w("* 粒数の目安（fx.js の予算は 1 tick 260 粒）は各欄の **粒数**。")
    w("")
    w("### 変数の早見表（共通の意味）")
    w("")
    w("| 変数 | 意味 |")
    w("|---|---|")
    for k in SCRIPT_VARS:
        w(f"| `{k}` | {VAR_MEANING[k]} |")
    w("")
    w("## 一覧")
    w("")
    w("| ID | 見た目 | 材質 | 読む変数 | 粒数 |")
    w("|---|---|---|---|---|")
    for f in E:
        short = f.look.split("。")[0].split("（")[0]
        vars_ = " ".join(f"`{k}`" for k in f.vars if k not in ("cr", "cg", "cb"))
        w(f"| `{NS}:{f.id}`{' ★' if f.star else ''} | {short} | {MAT_JA[f.material].split('（')[0]} | "
          f"{vars_} | {f.cost} |")
    w("")
    w("★ = 流れや形のある特別な動き（DESIGN §4.7）。")
    w("")
    w("## 個別")
    for f in E:
        w("")
        w(f"### `{NS}:{f.id}`{' ★' if f.star else ''}")
        w("")
        w(f"* 見た目: {f.look}")
        w(f"* 材質: {MAT_JA[f.material]} / 粒数: {f.cost}")
        w(f"* 用途: {f.uses}")
        w(f"* 目安: {f.typical}")
        w("")
        w("| 変数 | 既定 | 意味 |")
        w("|---|---|---|")
        for k, (shown, note, _) in f.vars.items():
            w(f"| `{k}` | {shown} | {note or VAR_MEANING[k]} |")
    w("")
    w("## 注意（作業者向け）")
    w("")
    w("* `lookat_direction` の粒（beam・bolt・thrust・spark・speedline・wind・droplet・converge・orbit・vortex）は"
      "スプライトの**横（size[0]）が向きに沿う**。向きの軸まわりにカメラへ回るので帯は常に見える。")
    w("* `circle_v`・`wave` は `direction_z`（面が向きを向く）なので、真横から見ると薄くなる。")
    w("* `black_hole` は半透明（blend）の一枚絵で、核は黒のまま（染まらない）。光らせたい時は同じ点に"
      "`lens`（加算）を同じ色で重ねる（DESIGN の「blend + add の二層」はこの二つで作る）。")
    w("* 寿命の長い陣（circle 系・emblem・black_hole・cloud・aurora）は現れる/消える速さが秒で決まっているので、"
      "life を何秒にしても点き方は同じ。")
    w("* `nano_stream` は放出に `count / rate` 秒かかる。最後の粒が着くのは `life + count / rate` 秒後。")
    w("* `vortex` の `life` は放出時間。同時最大 160 粒、nano_stream は 120 粒で打ち切る。")
    w("* `debris` だけ地形と衝突する（地面で跳ねる）。")
    w("* 色の既定値は粒ごとに違う（下の各表）。`emblem` は v.var の惑星の発光色が既定。")
    w("")
    with open(DOC_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


# ===========================================================================
#  自己検査
# ===========================================================================
KNOWN_COMPONENTS = {
    "minecraft:emitter_initialization", "minecraft:emitter_lifetime_events", "minecraft:emitter_lifetime_expression",
    "minecraft:emitter_lifetime_looping", "minecraft:emitter_lifetime_once", "minecraft:emitter_local_space",
    "minecraft:emitter_rate_instant", "minecraft:emitter_rate_manual", "minecraft:emitter_rate_steady",
    "minecraft:emitter_shape_box", "minecraft:emitter_shape_custom", "minecraft:emitter_shape_disc",
    "minecraft:emitter_shape_entity_aabb", "minecraft:emitter_shape_point", "minecraft:emitter_shape_sphere",
    "minecraft:particle_appearance_billboard", "minecraft:particle_appearance_lighting",
    "minecraft:particle_appearance_tinting", "minecraft:particle_expire_if_in_blocks",
    "minecraft:particle_expire_if_not_in_blocks", "minecraft:particle_initial_speed",
    "minecraft:particle_initial_spin", "minecraft:particle_initialization", "minecraft:particle_kill_plane",
    "minecraft:particle_lifetime_events", "minecraft:particle_lifetime_expression",
    "minecraft:particle_motion_collision", "minecraft:particle_motion_dynamic",
    "minecraft:particle_motion_parametric"}
FACING = {"rotate_xyz", "rotate_y", "lookat_xyz", "lookat_y", "lookat_direction", "direction_x", "direction_y",
          "direction_z", "emitter_transform_xy", "emitter_transform_xz", "emitter_transform_yz"}
EMITTER_COMPS = {k for k in KNOWN_COMPONENTS if k.startswith("minecraft:emitter_")}
BUILTIN_VARS = {"variable.particle_age", "variable.particle_lifetime", "variable.emitter_age",
                "variable.emitter_lifetime"} | {f"variable.particle_random_{i}" for i in range(1, 5)} | \
               {f"variable.emitter_random_{i}" for i in range(1, 5)}
NON_MOLANG_KEYS = {"identifier", "material", "texture", "facing_camera_mode", "mode"}


def design_ids():
    """DESIGN.md §4.7 の表の 1 列目から ID を拾う。"""
    txt = open(os.path.join(HERE, "DESIGN.md"), encoding="utf-8").read()
    sec = txt.split("### 4.7", 1)[1].split("### 4.8", 1)[0]
    ids = []
    for line in sec.splitlines():
        if not line.startswith("| `"):
            continue
        first = line.split("|")[1]
        ids += re.findall(r"`([a-z_]+)`", first)
    return ids


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def sample_contexts(script):
    """変数の組 × 乱数 × 年齢の見本（uv・大きさ・色の範囲を確かめる）。"""
    for var in (None, 0, 1, 2, 3, 4, 8, 9, -2, 14):
        for r in (0.0, 0.37, 0.9999):
            for age in (0.0, 0.31, 0.999):
                c = {f"variable.particle_random_{i}": (r + 0.21 * i) % 1.0 for i in range(1, 5)}
                c.update({f"variable.emitter_random_{i}": (r + 0.13 * i) % 1.0 for i in range(1, 5)})
                c["variable.particle_lifetime"] = 0.8
                c["variable.particle_age"] = age * 0.8
                c["variable.emitter_age"] = 0.0
                c["variable.emitter_lifetime"] = 1.0
                for k, v in script.items():
                    c[f"variable.{k}"] = v
                if var is not None:
                    c["variable.var"] = float(var)
                yield c


TYPICAL_VARS = {"cr": 1.0, "cg": 0.3, "cb": 0.2, "size": 2.0, "life": 1.5, "rot": 45.0, "count": 12.0,
                "speed": 5.0, "spread": 1.5, "vx": 3.0, "vy": 0.5, "vz": -4.0, "height": 5.0, "spin": 90.0,
                "rate": 40.0, "grav": -9.8, "len": 10.0}


def self_check(E, docs):
    errors = []
    err = errors.append
    ids = [f.id for f in E]
    want = design_ids() + list(EXTRA_IDS)
    if sorted(ids) != sorted(want):
        err(f"ids differ from DESIGN §4.7: missing {sorted(set(want) - set(ids))} extra {sorted(set(ids) - set(want))}")
    if len(set(ids)) != len(ids):
        err("duplicate ids")
    # アトラスの配置
    rects = []
    for name in SPRITES:
        x, y = LAYOUT[name]
        bw, bh = block_size(name)
        if x < 0 or y < 0 or x + bw > AW or y + bh > AH:
            err(f"sprite {name} outside atlas")
        rects.append((name, x, y, bw, bh))
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            if a[1] < b[1] + b[3] and b[1] < a[1] + a[3] and a[2] < b[2] + b[4] and b[2] < a[2] + a[4]:
                err(f"sprites overlap: {a[0]} {b[0]}")
    img = Image.open(ATLAS_PNG)
    if img.size != (AW, AH):
        err(f"atlas size {img.size}")
    n_exprs = 0
    for f in E:
        path = os.path.join(PART_DIR, f"{f.id}.particle.json")
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception as ex:   # noqa: BLE001
            err(f"{f.id}: json {ex}")
            continue
        if doc != docs[f.id]:
            err(f"{f.id}: file differs from definition")
        pe = doc["particle_effect"]
        if doc["format_version"] != FORMAT_VERSION:
            err(f"{f.id}: format_version")
        if pe["description"]["identifier"] != f"{NS}:{f.id}":
            err(f"{f.id}: identifier")
        if pe["description"]["basic_render_parameters"]["texture"] != TEX:
            err(f"{f.id}: texture")
        comps = pe["components"]
        for k in comps:
            if k not in KNOWN_COMPONENTS:
                err(f"{f.id}: unknown component {k}")
        if "color" in comps:
            err(f"{f.id}: color directly under components")
        tint = comps.get("minecraft:particle_appearance_tinting")
        if not tint or not isinstance(tint.get("color"), list) or len(tint["color"]) != 4:
            err(f"{f.id}: tinting color must be a 4-element list inside particle_appearance_tinting")
        bb = comps.get("minecraft:particle_appearance_billboard")
        if not bb or bb.get("facing_camera_mode") not in FACING:
            err(f"{f.id}: billboard facing")
        if bb and "direction" in bb and bb["direction"]["mode"] not in ("derive_from_velocity", "custom"):
            err(f"{f.id}: direction mode")
        if bb and bb.get("facing_camera_mode", "").startswith(("direction", "lookat_direction")) and \
                "direction" not in bb:
            err(f"{f.id}: direction facing without direction settings")
        spin = comps.get("minecraft:particle_initial_spin", {})
        if spin.get("rotation_rate", 0) not in (0, "0") and "minecraft:particle_motion_dynamic" not in comps:
            err(f"{f.id}: rotation_rate needs particle_motion_dynamic")
        if "minecraft:particle_initial_speed" in comps and "minecraft:particle_motion_dynamic" not in comps:
            err(f"{f.id}: initial_speed needs particle_motion_dynamic")
        if "minecraft:particle_motion_parametric" in comps and "minecraft:particle_motion_dynamic" in comps:
            err(f"{f.id}: parametric and dynamic together")
        if "minecraft:particle_motion_collision" in comps and "minecraft:particle_motion_dynamic" not in comps:
            err(f"{f.id}: collision needs dynamic")
        steady = comps.get("minecraft:emitter_rate_steady")
        if steady and not (isinstance(steady["max_particles"], (int, float)) and steady["max_particles"] <= 200):
            err(f"{f.id}: steady emitter must cap max_particles <= 200")
        # Molang
        assigned = set()
        init = comps.get("minecraft:emitter_initialization", {}).get("creation_expression")
        if init:
            assigned |= set(molang_assigns(molang_parse(init)))
        reads_script = set()
        for p, val in walk(comps):
            key = p.rsplit("/", 1)[-1].split("[")[0]
            if key in NON_MOLANG_KEYS or isinstance(val, bool):
                continue
            if isinstance(val, str) and key == "direction" and val in ("inwards", "outwards"):
                continue
            if isinstance(val, (int, float)):
                continue
            n_exprs += 1
            if not parens_balanced(val):
                err(f"{f.id}{p}: unbalanced parentheses")
                continue
            try:
                ast = molang_parse(val)
                molang_compile(val)
            except MolangError as ex:
                err(f"{f.id}{p}: {ex}")
                continue
            comp = p.split("/")[1]
            for name, guarded in molang_reads(ast):
                short = name.split(".", 1)[1] if name.startswith("variable.") else name
                if short in SCRIPT_VARS:
                    reads_script.add(short)
                    if not guarded:
                        err(f"{f.id}{p}: {name} read without ?? default")
                elif name in BUILTIN_VARS:
                    if comp in EMITTER_COMPS and name.startswith("variable.particle_"):
                        err(f"{f.id}{p}: particle variable in emitter component")
                elif name not in assigned:
                    err(f"{f.id}{p}: {name} is never set")
        for must in ("cr", "cg", "cb", "size", "life"):
            if must not in reads_script:
                err(f"{f.id}: does not read v.{must}")
        if set(reads_script) != set(f.vars):
            err(f"{f.id}: doc vars {sorted(f.vars)} != read {sorted(reads_script)}")
        # 値の範囲（既定 / 典型の変数で）
        for script in ({}, TYPICAL_VARS):
            for c in sample_contexts(script):
                _Env.strict = True
                _Env.rng = random.Random(3)
                try:
                    if init:
                        molang_compile(init)(c)
                    cols = [molang_compile(e)(c) for e in tint["color"]]
                    size = [molang_compile(e)(c) for e in bb["size"]]
                except MolangError as ex:
                    err(f"{f.id}: eval {ex}")
                    break
                vals = cols + size
                if any(not math.isfinite(v) for v in vals):
                    err(f"{f.id}: non-finite value {vals} with {script and 'typical' or 'default'} vars")
                    break
                if any(v < -1e-6 or v > 1 + 1e-6 for v in cols):
                    err(f"{f.id}: colour/alpha out of range {cols}")
                    break
                if any(v < -1e-6 for v in size):
                    err(f"{f.id}: negative size {size}")
                    break
                u = bb["uv"]
                if "flipbook" in u:
                    fb = u["flipbook"]
                    x0, y0 = fb["base_UV"]
                    sw, sh = fb["size_UV"]
                    stx, sty = fb["step_UV"]
                    n = fb["max_frame"]
                    boxes = [(x0 + stx * i, y0 + sty * i, sw, sh) for i in range(int(n))]
                else:
                    uu = [molang_compile(e)(c) for e in u["uv"]]
                    ss = [molang_compile(e)(c) for e in u["uv_size"]]
                    boxes = [(uu[0], uu[1], ss[0], ss[1])]
                for bx, by, bw2, bh2 in boxes:
                    if not (0 <= bx and 0 <= by and bx + bw2 <= u["texture_width"] and
                            by + bh2 <= u["texture_height"]):
                        err(f"{f.id}: uv {bx, by, bw2, bh2} outside atlas")
                if errors and errors[-1].startswith(f"{f.id}: uv"):
                    break
    return errors, n_exprs


# ===========================================================================
def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main():
    atlas = build_atlas()
    E = build_effects()
    os.makedirs(PART_DIR, exist_ok=True)
    for fn in os.listdir(PART_DIR):
        if fn.endswith(".particle.json"):
            os.remove(os.path.join(PART_DIR, fn))
    docs = {}
    for f in E:
        docs[f.id] = f.doc()
        write_json(os.path.join(PART_DIR, f"{f.id}.particle.json"), docs[f.id])
    write_doc(E)
    errors, n_exprs = self_check(E, docs)
    if os.environ.get("ASTRO_PREVIEW"):
        preview_atlas(atlas)
        preview_effects(E, docs)
    print(f"  particles: {len(E)}  sprites: {len(SPRITES)}  atlas: {AW}x{AH}  molang exprs checked: {n_exprs}")
    if errors:
        for e in errors:
            print("  ERROR:", e)
        sys.exit(1)
    print("  self-check: OK (json, molang parse/eval, ?? defaults, uv in atlas, components, tinting)")


# ===========================================================================
#  プレビュー: JSON をそのまま Molang で動かす簡易シミュレーション（3/4 俯瞰の正射影）
# ===========================================================================
CAM_YAW, CAM_PITCH = 35.0, 24.0
TILE = 190
# 変数を渡した時の見本（particles_demo.png）
DEMO = {
    "beam": {"vx": 1.0, "vy": 0.15, "vz": -0.6, "len": 6.0, "cr": 1.0, "cg": 0.45, "cb": 0.15},
    "bolt": {"len": 7.0, "vx": 0.3, "vy": 1.0},
    "thrust": {"vx": 1.0, "vz": 1.0, "len": 4.0, "cr": 0.3, "cg": 1.0, "cb": 0.55},
    "nano": {"vx": 0.0, "vy": 1.6, "vz": 1.2, "spread": 1.2},
    "nano_stream": {"vx": 2.2, "vy": 1.4, "vz": 0.0, "cr": 1.0, "cg": 0.67, "cb": 0.16},
    "meteor": {"speed": 10.0, "life": 0.6, "vx": 0.5, "vy": -1.0, "vz": 0.2},
    "emblem": {"var": 4.0},
    "circle_v": {"vx": 1.0, "vz": 1.0, "cr": 0.75, "cg": 0.5, "cb": 1.0},
    "wave": {"vx": 1.0, "vz": 0.4},
    "ring_n": {"vx": 1.0, "vy": 0.0, "vz": 0.0, "spread": 1.2, "var": 2.0},
    "line_n": {"vx": 3.0, "vy": 1.0, "vz": -2.0, "var": 1.0, "count": 24.0},
    "cloud": {"vx": 0.8, "life": 3.0},
    "aurora": {"spread": 3.0, "cr": 0.5, "cg": 0.6, "cb": 1.0},
    "vortex": {"cr": 1.0, "cg": 0.35, "cb": 0.2, "spread": 1.6},
    "spark": {"vx": 1.0, "vy": 0.3},
    "speedline": {"vx": 0.0, "vy": 0.0, "vz": 1.0},
    "slash": {"rot": 30.0, "cr": 1.0, "cg": 0.3, "cb": 0.4},
    "slash_flat": {"rot": 90.0},
    "warning": {"size": 1.5, "life": 1.5},
    "debris": {"speed": 9.0},
}


def _cam():
    y, p = math.radians(CAM_YAW), math.radians(CAM_PITCH)
    D = np.array([math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)])
    F = -D
    R = np.cross(F, [0, 1, 0])
    R /= np.linalg.norm(R)
    U = np.cross(R, F)
    return R, U, F


def _unit(v, fallback=(0, 1, 0)):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 and np.isfinite(n) else np.asarray(fallback, float)


def _rand_unit(rng):
    while True:
        v = np.array([rng.uniform(-1, 1) for _ in range(3)])
        n = np.linalg.norm(v)
        if 0.05 < n <= 1:
            return v / n


def simulate(doc, script, seed, snaps, dt, tmax=8.0):
    """エミッタと粒を動かし、snaps の各時刻の描画項目を返す。戻り値 (frames, t_end)。"""
    comps = doc["particle_effect"]["components"]
    C = lambda e, c: molang_compile(e)(c)                       # noqa: E731
    _Env.strict = False
    rng = random.Random(seed)
    _Env.rng = rng
    ectx = {f"variable.{k}": float(v) for k, v in script.items()}
    for i in range(1, 5):
        ectx[f"variable.emitter_random_{i}"] = rng.random()
    ectx["variable.emitter_age"] = 0.0
    ectx["variable.emitter_lifetime"] = 1.0
    init = comps.get("minecraft:emitter_initialization", {}).get("creation_expression")
    if init:
        C(init, ectx)
    active = C(comps["minecraft:emitter_lifetime_once"]["active_time"], ectx)
    ectx["variable.emitter_lifetime"] = active
    inst = comps.get("minecraft:emitter_rate_instant")
    steady = comps.get("minecraft:emitter_rate_steady")
    shape_key = next(k for k in comps if k.startswith("minecraft:emitter_shape_"))
    shape = comps[shape_key]
    bb = comps["minecraft:particle_appearance_billboard"]
    tint = comps["minecraft:particle_appearance_tinting"]["color"]
    dyn = comps.get("minecraft:particle_motion_dynamic")
    par = comps.get("minecraft:particle_motion_parametric")
    col = comps.get("minecraft:particle_motion_collision")
    spin = comps.get("minecraft:particle_initial_spin", {})
    parts = []

    def spawn():
        pc = dict(ectx)
        for i in range(1, 5):
            pc[f"variable.particle_random_{i}"] = rng.random()
        pc["variable.particle_age"] = 0.0
        pc["variable.particle_lifetime"] = 1.0
        off = np.array([C(e, pc) for e in shape.get("offset", [0, 0, 0])], float)
        sp = np.zeros(3)
        kind = shape_key.split("_")[-1]
        if kind == "sphere":
            r = C(shape.get("radius", 1), pc)
            u = _rand_unit(rng)
            sp = u * (r if shape.get("surface_only") else r * rng.random() ** (1 / 3))
        elif kind == "disc":
            r = C(shape.get("radius", 1), pc)
            ang = rng.uniform(0, 2 * math.pi)
            d = r * math.sqrt(rng.random())
            sp = np.array([d * math.cos(ang), 0, d * math.sin(ang)])
        dr = shape.get("direction", "outwards")
        if isinstance(dr, list):
            direction = _unit([C(e, pc) for e in dr])
        elif kind == "point":
            direction = _rand_unit(rng)
        else:
            direction = _unit(sp, _rand_unit(rng)) * (-1 if dr == "inwards" else 1)
        pos = off + sp
        s0 = comps.get("minecraft:particle_initial_speed", 0)
        vel = np.array([C(e, pc) for e in s0]) if isinstance(s0, list) else direction * C(s0, pc)
        life = C(comps["minecraft:particle_lifetime_expression"]["max_lifetime"], pc)
        pc["variable.particle_lifetime"] = max(life, 1e-3)
        parts.append({"c": pc, "pos": pos, "vel": vel, "age": 0.0, "life": life,
                      "rot0": C(spin.get("rotation", 0), pc), "rate": C(spin.get("rotation_rate", 0), pc),
                      "rot": 0.0, "dir": direction})

    def update(p, step):
        c = p["c"]
        c["variable.particle_age"] = p["age"]
        if par:
            p["pos"] = np.array([C(e, c) for e in par["relative_position"]], float)
            p["rot"] = C(par["rotation"], c) if "rotation" in par else p["rot0"]
        elif dyn:
            acc = np.array([C(e, c) for e in dyn.get("linear_acceleration", [0, 0, 0])], float)
            drag = C(dyn.get("linear_drag_coefficient", 0), c)
            p["vel"] = p["vel"] + (acc - drag * p["vel"]) * step
            p["pos"] = p["pos"] + p["vel"] * step
            p["rot"] = p["rot0"] + p["rate"] * p["age"]
            if col and p["pos"][1] < 0:
                if col.get("expire_on_contact"):
                    p["age"] = 1e9
                p["pos"][1] = 0
                if p["vel"][1] < 0:
                    p["vel"][1] *= -col.get("coefficient_of_restitution", 0)
                p["vel"][[0, 2]] *= max(0.0, 1 - col.get("collision_drag", 0) * step * 0.3)
        else:
            p["rot"] = p["rot0"]

    def items():
        out = []
        for p in parts:
            c = p["c"]
            c["variable.particle_age"] = p["age"]
            size = [C(e, c) for e in bb["size"]]
            u = bb["uv"]
            if "flipbook" in u:
                fb = u["flipbook"]
                n = int(fb["max_frame"])
                fr = min(n - 1, int(p["age"] / max(p["life"], 1e-3) * n))
                uvr = (fb["base_UV"][0] + fb["step_UV"][0] * fr, fb["base_UV"][1] + fb["step_UV"][1] * fr,
                       fb["size_UV"][0], fb["size_UV"][1])
            else:
                uvr = tuple(C(e, c) for e in u["uv"]) + tuple(C(e, c) for e in u["uv_size"])
            rgba = [min(1.0, max(0.0, C(e, c))) for e in tint]
            d = None
            ds = bb.get("direction")
            if ds and ds["mode"] == "custom":
                d = _unit([C(e, c) for e in ds["custom_direction"]], (0, 0, 1))
            elif ds:
                v = p["vel"] if not par else None
                d = _unit(v, p["dir"]) if v is not None and np.linalg.norm(v) > 0.05 else p["dir"]
            out.append((p["pos"].copy(), size, uvr, rgba, bb["facing_camera_mode"], d, p["rot"]))
        return out

    if inst:
        for _ in range(int(round(C(inst["num_particles"], ectx)))):
            spawn()
    frames, si, t, acc = {}, 0, 0.0, 0.0
    rate = C(steady["spawn_rate"], ectx) if steady else 0
    maxp = C(steady["max_particles"], ectx) if steady else 0
    t_end = 0.0
    while t <= tmax:
        ectx["variable.emitter_age"] = t
        if steady and t < active:
            acc += rate * dt
            while acc >= 1:
                acc -= 1
                if len(parts) < maxp:
                    spawn()
        for p in parts:
            update(p, dt)
        while si < len(snaps) and t >= snaps[si] - 1e-9:
            frames[si] = items()
            si += 1
        for p in parts:
            p["age"] += dt
        parts = [p for p in parts if p["age"] <= p["life"]]
        t += dt
        if parts or (steady and t < active):
            t_end = t
        elif si >= len(snaps):
            break
    return frames, t_end


def _quad_axes(mode, d, R, U, F, rot):
    up = np.array([0.0, 1.0, 0.0])
    if mode in ("rotate_y", "lookat_y"):
        X, Y = R, up
    elif mode == "emitter_transform_xz":
        X, Y = np.array([1.0, 0, 0]), np.array([0, 0, -1.0])
    elif mode == "emitter_transform_xy":
        X, Y = np.array([1.0, 0, 0]), up
    elif mode == "emitter_transform_yz":
        X, Y = np.array([0, 0, 1.0]), up
    elif mode == "direction_z" and d is not None:
        X = _unit(np.cross(up, d), (1, 0, 0))
        Y = np.cross(d, X)
    elif mode == "direction_x" and d is not None:
        X = d
        Y = _unit(up - np.dot(up, d) * d, F)
    elif mode == "direction_y" and d is not None:
        Y = d
        X = _unit(np.cross(d, up), R)
    elif mode == "lookat_direction" and d is not None:
        X = d
        Y = np.cross(F, d)
        if np.linalg.norm(Y) < 1e-4:
            return None
        Y = Y / np.linalg.norm(Y)
    else:
        X, Y = R, U
    a = math.radians(rot)
    return X * math.cos(a) + Y * math.sin(a), -X * math.sin(a) + Y * math.cos(a)


def render_frames(frames, atlas, material, tile=TILE, bg=(14, 16, 24)):
    R, U, F = _cam()
    pts = []
    for its in frames.values():
        for pos, size, *_ in its:
            r = 0.5 * max(abs(size[0]), abs(size[1]))
            pts.append((pos @ R - r, pos @ U - r))
            pts.append((pos @ R + r, pos @ U + r))
    pts.append((0, 0))
    pts = np.array(pts)
    lo, hi = pts.min(0), pts.max(0)
    ext = max(hi[0] - lo[0], hi[1] - lo[1], 0.6)
    scale = tile * 0.9 / ext
    mid = (lo + hi) / 2
    S = lambda p: (tile / 2 + (p @ R - mid[0]) * scale, tile / 2 - (p @ U - mid[1]) * scale)  # noqa: E731
    base = Image.new("RGB", (tile, tile), bg)
    dr = ImageDraw.Draw(base)
    k = int(min(12, ext * 1.2)) + 1
    for i in range(-k, k + 1):
        for a, b in (((i, 0, -k), (i, 0, k)), ((-k, 0, i), (k, 0, i))):
            dr.line([S(np.array(a, float)), S(np.array(b, float))], fill=(30, 34, 46))
    o = S(np.zeros(3))
    dr.line([(o[0] - 4, o[1]), (o[0] + 4, o[1])], fill=(90, 96, 120))
    dr.line([(o[0], o[1] - 4), (o[0], o[1] + 4)], fill=(90, 96, 120))
    out = []
    for fi in sorted(frames):
        canvas = np.asarray(base, F32) / 255
        its = sorted(frames[fi], key=lambda it: -(it[0] @ F)) if material != "add" else frames[fi]
        for pos, size, uvr, rgba, mode, d, rot in its:
            axes = _quad_axes(mode, d, R, U, F, rot)
            if axes is None or size[0] <= 1e-4 or size[1] <= 1e-4 or rgba[3] <= 0.002:
                continue
            Xa, Ya = axes
            u0, v0, uw, uh = (int(round(q)) for q in uvr)
            if uw <= 0 or uh <= 0:
                continue
            spr = atlas.crop((u0, v0, u0 + uw, v0 + uh))
            A, B = Xa * size[0] / 2, Ya * size[1] / 2
            cx, cy = S(pos)
            ax, ay = A @ R * scale, -(A @ U) * scale
            bx, by = B @ R * scale, -(B @ U) * scale
            M = np.array([[2 * ax / uw, -2 * bx / uh, cx - ax + bx], [2 * ay / uw, -2 * by / uh, cy - ay + by],
                          [0, 0, 1.0]])
            if abs(np.linalg.det(M[:2, :2])) < 1e-6:
                continue
            corners = [M @ np.array([px, py, 1.0]) for px in (0, uw) for py in (0, uh)]
            xs = [q[0] for q in corners]
            ys = [q[1] for q in corners]
            x0, x1 = max(0, int(math.floor(min(xs)))), min(tile, int(math.ceil(max(xs))))
            y0, y1 = max(0, int(math.floor(min(ys)))), min(tile, int(math.ceil(max(ys))))
            if x1 <= x0 or y1 <= y0:
                continue
            Mi = np.linalg.inv(M)
            coef = (Mi[0, 0], Mi[0, 1], Mi[0, 0] * x0 + Mi[0, 1] * y0 + Mi[0, 2],
                    Mi[1, 0], Mi[1, 1], Mi[1, 0] * x0 + Mi[1, 1] * y0 + Mi[1, 2])
            warped = spr.transform((x1 - x0, y1 - y0), Image.AFFINE, coef, resample=Image.BILINEAR)
            w_ = np.asarray(warped, F32) / 255
            src = w_[..., :3] * np.array(rgba[:3], F32)
            a = w_[..., 3:4] * rgba[3]
            reg = canvas[y0:y1, x0:x1]
            if material == "add":
                reg += src * a
            else:
                reg[...] = reg * (1 - a) + src * a
        out.append(Image.fromarray((np.clip(canvas, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB"))
    return out, scale


def preview_effects(E, docs):
    os.makedirs(SCRATCH, exist_ok=True)
    atlas = Image.open(ATLAS_PNG).convert("RGBA")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)

    def cell(f, script, seed=7):
        doc = docs[f.id]
        _, t_end = simulate(doc, script, seed, [], 1 / 40)
        t_end = max(t_end, 0.05)
        snaps = [t_end * q for q in (0.12, 0.42, 0.78)]
        frames, _ = simulate(doc, script, seed, snaps, min(1 / 60, t_end / 60))
        for i in range(3):
            frames.setdefault(i, [])
        imgs, scale = render_frames(frames, atlas, f.material)
        return imgs, snaps, scale

    def sheet(entries, path, cols=3):
        cw, ch = 3 * TILE + 12, TILE + 22
        rows = (len(entries) + cols - 1) // cols
        img = Image.new("RGB", (cols * cw, rows * ch), (8, 9, 14))
        d = ImageDraw.Draw(img)
        for k, (f, script) in enumerate(entries):
            ox, oy = (k % cols) * cw, (k // cols) * ch
            imgs, snaps, scale = cell(f, script)
            for i, im in enumerate(imgs):
                img.paste(im, (ox + i * TILE, oy + 20))
                d.text((ox + i * TILE + 3, oy + 22), f"{snaps[i]:.2f}s", fill=(130, 136, 150), font=small)
            label = f"{f.id}{' *' if f.star else ''}  [{f.material}]"
            d.text((ox + 3, oy + 3), label, fill=(235, 238, 245), font=font)
            info = "  ".join(f"{k2}={v}" for k2, v in script.items()) if script else "no variables"
            d.text((ox + 200, oy + 5), f"{info}   1m={scale:.0f}px", fill=(140, 146, 160), font=small)
        img.save(path)

    only = [x for x in os.environ.get("ASTRO_PREVIEW_ONLY", "").split(",") if x]
    if only:                     # 一部だけ（作業中の確認用）: 変数無しと見本の変数の両方
        ent = [(f, {}) for f in E if f.id in only] + [(f, DEMO[f.id]) for f in E if f.id in only and f.id in DEMO]
        sheet(ent, os.path.join(SCRATCH, "particles_focus.png"), cols=2)
        return
    per = 21
    for s in range(0, len(E), per):
        sheet([(f, {}) for f in E[s:s + per]], os.path.join(SCRATCH, f"particles_sim_{s // per + 1}.png"))
    demo = [(f, DEMO[f.id]) for f in E if f.id in DEMO]
    sheet(demo, os.path.join(SCRATCH, "particles_demo.png"))


def preview_atlas(atlas):
    os.makedirs(SCRATCH, exist_ok=True)
    bg = Image.new("RGBA", atlas.size, (16, 18, 26, 255))
    cols = [(120, 240, 255), (255, 172, 40), (226, 255, 96), (255, 122, 42), (190, 230, 255),
            (84, 255, 146), (178, 92, 255), (255, 90, 120)]
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    d = ImageDraw.Draw(bg)
    arr = np.asarray(atlas, F32) / 255
    out = np.asarray(bg, F32) / 255
    for k, name in enumerate(SPRITES):
        x, y = LAYOUT[name]
        bw, bh = block_size(name)
        c = np.array(cols[k % len(cols)], F32) / 255
        reg = arr[y:y + bh, x:x + bw]
        a = reg[..., 3:4]
        out[y:y + bh, x:x + bw, :3] = out[y:y + bh, x:x + bw, :3] * (1 - a) + reg[..., :3] * c * a
    img = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    for name in SPRITES:
        x, y = LAYOUT[name]
        bw, bh = block_size(name)
        d.rectangle([x, y, x + bw - 1, y + bh - 1], outline=(60, 66, 84))
        d.text((x + 2, y + 1), name, fill=(255, 255, 255), font=font)
    img.convert("RGB").save(os.path.join(SCRATCH, "particles_atlas.png"))


if __name__ == "__main__":
    main()
