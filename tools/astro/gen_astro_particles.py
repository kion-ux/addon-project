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
    pen.poly(pts, 2.6)
    for _ in range(3):                                  # 枝
        i = rng.randint(8, len(pts) - 20)
        bx, by = pts[i]
        L = rng.uniform(30, 60)
        ex = bx + L
        ey = float(np.clip(by + rng.choice([-1, 1]) * rng.uniform(6, h / 2 - 3), 3, h - 3))
        br = _bolt_pts(rng, bx, ex, by, ey, 4, 0.3)
        br = [(px, float(np.clip(py, 2, h - 2))) for px, py in br]
        pen.poly(br, 1.3)
    a = pen.alpha()
    core = Pen(w, h)
    core.poly(pts, 1.0)
    white = 0.7 + 0.3 * core.alpha()
    return halo(a, 2.2, 0.75), white


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
        pen.poly(pts, 1.6)
    a = pen.alpha()
    return halo(a, 2.0, 0.7)


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
    edge = 0.62 + 0.1 * np.sin(th * 7) + 0.06 * np.sin(th * 13 + 1.3)
    flame = hard(r < edge) * 0.92
    core = sat((0.34 - r) / 0.05)
    hal = sat(1 - r) ** 2 * 0.5
    a = np.maximum(np.maximum(flame, core), hal)
    return down(a), down(np.where(r < 0.36, 1.0, 0.8))


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
    "slash_big": (256, 256, 1, "x", sp_slash, (0.34, 220.0, 4)),
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
    "scan": (256, 32, 1, "x", sp_scan, ()),
    "slash": (128, 128, 1, "x", sp_slash, (0.3, 200.0, 3)),
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


# ==== PARTICLES ====


def main():
    atlas = build_atlas()
    print(f"  atlas: {AW}x{AH}  sprites: {len(SPRITES)}")
    if os.environ.get("ASTRO_PREVIEW"):
        preview_atlas(atlas)


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
