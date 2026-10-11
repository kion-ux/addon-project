# -*- coding: utf-8 -*-
"""パーティクル — スプライトアトラスと、そこから引く効果の定義。

方針
----
* **一枚絵で勝負しない。** 一つの見せ場は「芯 + 光 + 破片 + 煙 + 衝撃波 + 磁力線」を
  重ねて作る。重ねの時間差を JS の ``system.runTimeout`` に持たせると 50ms 刻みで
  ラグに負けるので、``emitter_lifetime_events`` の timeline に内蔵する。
  こちらは 0.03 秒単位で効き、サーバの重さに引きずられない。
* 色の役割は三つしか無い（docs/DIRECTION.md §2-2）。
      **白** = 撃発の瞬間 / **紫** = 力そのもの（不可視の場） / **鋼** = 動かされている物体
  技ごとの基調色 (contract.TECHNIQUES[*]["colour"]) は *縁の一段* にだけ使い、
  芯は必ず白へ寄せる。基調色一色で塗ると 15 技が同じ紫の靄になる。
* 加算 (``add=True``) は光だけ。質量（破片・煙・塵）は必ず通常合成。
  加算だけで積むと昼の空で完全に飛ぶ。どの見せ場にも通常合成を最低 1 層混ぜる。
* セルの絵は **α だけで描く**。色は tinting が乗せるので、ここは白一色でよい。
"""
from __future__ import annotations

import math
import os
import random

import _path  # noqa: F401

import contract as K  # noqa: E402
from common import write_json  # noqa: E402
from PIL import Image  # noqa: E402

# 512 へ広げた理由: 32px のセルを 11〜40 ブロック幅まで引き伸ばしていたので
# 1 ブロックあたり 0.7px しか無く、輪郭のガタつきが「安っぽさ」の正体になっていた。
# 引き伸ばし率の高い面（環・格子・紋）だけ 128px、残りは 64px。
ATLAS = 512
CELL = 64
CELL_BIG = 128
TEXTURE = "textures/particle/marvel_particles"
TEX_PATH = K.RP + "/textures/particle/marvel_particles.png"
FOG_DIR = os.path.join(K.RP, "fogs")


def _pw(v, e):
    return max(0.0, v) ** e


def _sat(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


# ===========================================================================
#  1. セルの絵
# ===========================================================================
class Cell:
    """一枚のセル。α のみを float で持ち、最後に白 + α として焼き込む。"""

    def __init__(self, n):
        self.n = n
        self.buf = [0.0] * (n * n)

    def add(self, xi, yi, a):
        if a <= 0.0:
            return
        if 0 <= xi < self.n and 0 <= yi < self.n:
            i = yi * self.n + xi
            v = self.buf[i] + a
            self.buf[i] = 1.0 if v > 1.0 else v

    def each(self, fn):
        n = self.n
        for yi in range(n):
            v = (yi + 0.5) / n * 2.0 - 1.0
            for xi in range(n):
                u = (xi + 0.5) / n * 2.0 - 1.0
                a = fn(u, v)
                if a > 0.0:
                    self.add(xi, yi, a)

    def mask(self, fn):
        n = self.n
        for yi in range(n):
            v = (yi + 0.5) / n * 2.0 - 1.0
            for xi in range(n):
                if self.buf[yi * n + xi] > 0.0:
                    u = (xi + 0.5) / n * 2.0 - 1.0
                    self.buf[yi * n + xi] *= _sat(fn(u, v))

    def _box(self, x0, y0, x1, y1, pad):
        n = self.n
        return (max(0, int((min(x0, x1) - pad + 1.0) * 0.5 * n) - 1),
                min(n - 1, int((max(x0, x1) + pad + 1.0) * 0.5 * n) + 1),
                max(0, int((min(y0, y1) - pad + 1.0) * 0.5 * n) - 1),
                min(n - 1, int((max(y0, y1) + pad + 1.0) * 0.5 * n) + 1))

    def seg(self, ax, ay, bx, by, w, a=1.0, e=1.2):
        """線分。距離で減衰させるので端が丸く、繋ぐと自然に一本になる。"""
        n = self.n
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy or 1e-9
        x0, x1, y0, y1 = self._box(ax, ay, bx, by, w)
        for yi in range(y0, y1 + 1):
            v = (yi + 0.5) / n * 2.0 - 1.0
            for xi in range(x0, x1 + 1):
                u = (xi + 0.5) / n * 2.0 - 1.0
                t = ((u - ax) * dx + (v - ay) * dy) / ll
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                d = math.hypot(u - (ax + dx * t), v - (ay + dy * t))
                if d < w:
                    self.add(xi, yi, a * (1.0 - d / w) ** e)

    def path(self, pts, w, a=1.0, e=1.2, taper=0.0):
        for i in range(len(pts) - 1):
            k = 1.0 - taper * (i / max(1, len(pts) - 2))
            self.seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                     w * k, a * k, e)

    def ring(self, r, w, a=1.0, e=1.4, arc=None, ang=0.0):
        def f(u, v):
            d = math.hypot(u, v)
            k = _pw(1.0 - abs(d - r) / w, e)
            if k <= 0.0:
                return 0.0
            if arc is not None:
                da = abs((math.atan2(v, u) - ang + math.pi) % (2 * math.pi) - math.pi)
                if da > arc:
                    return 0.0
                k *= 1.0 - (da / arc) ** 2          # 端を細らせて「弧」にする
            return a * k
        self.each(f)

    def fill(self, poly, a=1.0):
        n = self.n
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1, y0, y1 = self._box(min(xs), min(ys), max(xs), max(ys), 0.02)
        m = len(poly)
        for yi in range(y0, y1 + 1):
            v = (yi + 0.5) / n * 2.0 - 1.0
            for xi in range(x0, x1 + 1):
                u = (xi + 0.5) / n * 2.0 - 1.0
                inside = False
                j = m - 1
                for i in range(m):
                    if (poly[i][1] > v) != (poly[j][1] > v):
                        t = (v - poly[i][1]) / (poly[j][1] - poly[i][1] or 1e-9)
                        if u < poly[i][0] + t * (poly[j][0] - poly[i][0]):
                            inside = not inside
                    j = i
                if inside:
                    self.add(xi, yi, a)

    def blit(self, img, ox, oy):
        px = img.load()
        for yi in range(self.n):
            for xi in range(self.n):
                a = self.buf[yi * self.n + xi]
                if a > 0.002:
                    px[ox + xi, oy + yi] = (255, 255, 255, int(a * 255))


SHAPES: dict = {}
#: 引き伸ばし率が高く、輪郭の粗さがそのまま出る面だけ 128px。
BIG = {"ring", "shock", "glyph", "grid"}


def shape(name):
    def deco(fn):
        SHAPES[name] = fn
        return fn
    return deco


# --- 光の芯 ----------------------------------------------------------------
@shape("dot")               # 柔らかい丸。何にでも敷ける下地
def _dot(c):
    c.each(lambda u, v: _pw(1 - math.hypot(u, v), 2.2))


@shape("core")              # 焼き付いた光の芯。中心を飽和させて「白飛び」を作る
def _core(c):
    def f(u, v):
        d = math.hypot(u, v)
        return min(1.0, _pw(1 - d, 7.0) * 2.6 + _pw(1 - d, 1.7) * 0.45)
    c.each(f)


@shape("spark")             # 四光星
def _spark(c):
    def f(u, v):
        au, av = abs(u), abs(v)
        ray = (_pw(1 - au, 1.2) * _pw(1 - av * 9, 0.7)
               + _pw(1 - av, 1.2) * _pw(1 - au * 9, 0.7))
        return min(1.0, ray + _pw(1 - math.hypot(u, v) * 2.6, 1.6))
    c.each(f)


@shape("burst")             # 放射状に裂けた閃光。縁のギザギザが「弾けた」を作る
def _burst(c):
    def f(u, v):
        d = math.hypot(u, v)
        a = math.atan2(v, u)
        rmax = 0.40 + 0.54 * abs(math.cos(a * 6.0)) ** 0.7
        return _pw(1 - d / rmax, 1.5)
    c.each(f)


@shape("flash")             # 十字フレア。撃発の白はこれ一枚だけ
def _flash(c):
    def f(u, v):
        au, av = abs(u), abs(v)
        d = math.hypot(u, v)
        cross = (_pw(1 - au, 1.0) * _pw(1 - av * 11, 0.55)
                 + _pw(1 - av, 1.0) * _pw(1 - au * 11, 0.55))
        diag = 0.30 * (_pw(1 - abs(u - v) * 6, 0.7)
                       + _pw(1 - abs(u + v) * 6, 0.7)) * _pw(1 - d, 1.4)
        return min(1.0, cross + diag + _pw(1 - d * 2.2, 1.5))
    c.each(f)


@shape("flare")             # 横長のアナモルフィック。カメラのレンズを匂わせる
def _flare(c):
    def f(u, v):
        bar = _pw(1 - abs(v) / 0.06, 1.0) * _pw(1 - abs(u), 0.7)
        core = _pw(1 - math.hypot(u * 2.4, v * 5.0), 1.5)
        return min(1.0, bar + core)
    c.each(f)


@shape("lens")              # 楕円の光。金属面のハイライト
def _lens(c):
    c.each(lambda u, v: _pw(1 - math.hypot(u, v * 3.2), 1.9))


# --- 環 --------------------------------------------------------------------
@shape("ring")              # 細く硬い環（128px）
def _ring(c):
    c.ring(0.84, 0.055, 1.0, 1.5)
    c.ring(0.84, 0.24, 0.18, 2.4)


@shape("ring_thin")         # 極細。収束・走査用
def _ring_thin(c):
    c.ring(0.88, 0.030, 1.0, 1.2)
    c.ring(0.88, 0.13, 0.10, 2.6)


@shape("ring_double")       # 二重環。EMP の決め絵はこれ
def _ring_double(c):
    c.ring(0.90, 0.034, 1.0, 1.2)
    c.ring(0.64, 0.026, 0.60, 1.2)
    c.ring(0.90, 0.17, 0.09, 2.4)


@shape("shock")             # 厚い衝撃環（128px）。外縁を硬く、内へ煤けた尾
def _shock(c):
    def f(u, v):
        d = math.hypot(u, v)
        if d > 0.99:
            return 0.0
        a = math.atan2(v, u)
        edge = _pw(1 - abs(d - 0.86) / 0.13, 1.15)
        tail = _pw((d - 0.30) / 0.56, 1.8) * 0.42
        spoke = _pw(math.cos(a * 19.0), 7.0) * _pw((d - 0.35) / 0.5, 1.2) * 0.5
        return min(1.0, edge + tail + spoke)
    c.each(f)


@shape("shock_soft")        # 塵を含んだ波。通常合成で質量を残すとき
def _shock_soft(c):
    def f(u, v):
        d = math.hypot(u, v)
        if d > 1.0:
            return 0.0
        n = 0.90 + 0.10 * math.sin(math.atan2(v, u) * 7.0)
        return _pw(1 - abs(d - 0.72 * n) / 0.30, 1.6) * 0.92
    c.each(f)


@shape("shock_teeth")       # 縁が裂けた波。地面を割る系
def _shock_teeth(c):
    def f(u, v):
        d = math.hypot(u, v)
        r = 0.86 + 0.10 * math.cos(math.atan2(v, u) * 13.0)
        if d > r:
            return 0.0
        return _pw(1 - abs(d - r * 0.90) / 0.22, 1.3)
    c.each(f)


# --- 格子 ------------------------------------------------------------------
@shape("hex")               # 六角の枠。角に節を打って「面」の一枚に見せる
def _hex(c):
    pts = [(math.cos(i * math.pi / 3) * 0.84,
            math.sin(i * math.pi / 3) * 0.84) for i in range(6)]
    for i in range(6):
        a, b = pts[i], pts[(i + 1) % 6]
        c.seg(a[0], a[1], b[0], b[1], 0.075, 1.0, 1.2)
    for p in pts:
        c.each(lambda u, v, p=p: _pw(1 - math.hypot(u - p[0], v - p[1]) * 7, 1.4) * 0.6)


def _hex_at(c, cx, cy, r, w, a):
    pts = [(cx + math.cos(i * math.pi / 3 + math.pi / 6) * r,
            cy + math.sin(i * math.pi / 3 + math.pi / 6) * r) for i in range(6)]
    for i in range(6):
        p, q = pts[i], pts[(i + 1) % 6]
        c.seg(p[0], p[1], q[0], q[1], w, a, 1.1)


@shape("hexgrid")           # 蜂の巣。障壁の殻の一枚分
def _hexgrid(c):
    r = 0.33
    _hex_at(c, 0, 0, r, 0.052, 0.95)
    for i in range(6):
        a = i * math.pi / 3 + math.pi / 6
        _hex_at(c, math.cos(a) * r * 1.732, math.sin(a) * r * 1.732, r, 0.045, 0.55)
    c.mask(lambda u, v: 1.30 - math.hypot(u, v) * 1.05)


@shape("grid")              # 六角格子の面（128px）。磁極反転・磁界の「場」
def _grid(c):
    r = 0.245
    dx, dy = r * 1.732, r * 1.5
    for row in range(-5, 6):
        for col in range(-5, 6):
            cx = col * dx + (row & 1) * dx * 0.5
            cy = row * dy
            if math.hypot(cx, cy) > 1.3:
                continue
            _hex_at(c, cx, cy, r, 0.030, 0.85)
    c.mask(lambda u, v: 1.35 - math.hypot(u, v) * 1.30)


@shape("lattice")           # 鉄格子。交点に節を打つ（鋼鉄拘束）
def _lattice(c):
    for i in range(-2, 3):
        c.seg(i * 0.44, -0.96, i * 0.44, 0.96, 0.045, 0.9, 1.1)
    for j in (-0.52, 0.52):
        c.seg(-0.96, j, 0.96, j, 0.055, 0.9, 1.1)
    for i in range(-2, 3):
        for j in (-0.52, 0.52):
            c.each(lambda u, v, x=i * 0.44, y=j:
                   _pw(1 - math.hypot(u - x, v - y) * 9, 1.3))


# --- 矢と線 ----------------------------------------------------------------
@shape("chevron")           # 磁力線の矢。lookat_direction で進行方向を向く
def _chevron(c):
    c.seg(-0.52, -0.74, 0.64, 0.0, 0.155, 1.0, 1.1)
    c.seg(-0.52, 0.74, 0.64, 0.0, 0.155, 1.0, 1.1)
    c.seg(-0.92, -0.44, -0.22, 0.0, 0.085, 0.45, 1.4)
    c.seg(-0.92, 0.44, -0.22, 0.0, 0.085, 0.45, 1.4)


@shape("arrow")             # 鋭い一本矢。向きを読ませたいとき
def _arrow(c):
    c.seg(-0.92, 0.0, 0.58, 0.0, 0.070, 1.0, 1.3)
    c.seg(0.10, -0.42, 0.74, 0.0, 0.100, 1.0, 1.1)
    c.seg(0.10, 0.42, 0.74, 0.0, 0.100, 1.0, 1.1)


@shape("field")             # 磁力線の弧。数珠繋ぎにして「束」を作る
def _field(c):
    pts = [(-0.95 + 1.9 * (i / 20.0), -0.42 * math.sin(math.pi * (i / 20.0)))
           for i in range(21)]
    for i in range(20):
        t = (i + 0.5) / 20.0
        c.seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
              0.085 * (0.35 + 0.65 * math.sin(math.pi * t)), 1.0, 1.2)


@shape("funnel")            # 漏斗。引力の「流れ」を一枚で見せる
def _funnel(c):
    for s in (-1, 1):
        for k, off in enumerate((0.92, 0.58, 0.28)):
            c.seg(-0.95, s * off, 0.92, s * off * 0.12,
                  0.055 - k * 0.009, 0.95 - k * 0.22, 1.2)
    c.seg(-0.95, 0.0, 0.94, 0.0, 0.045, 0.7, 1.2)


@shape("streak")            # 尾。右端が先頭
def _streak(c):
    def f(u, v):
        head = (u + 1) * 0.5
        w = 0.36 * (0.16 + 0.84 * head)
        return _pw(1 - abs(v) / w, 1.3) * _pw(head, 0.9)
    c.each(f)


@shape("beam")              # カプセルの芯。中心線だけ飽和させる
def _beam(c):
    def f(u, v):
        if abs(u) > 0.94:
            return 0.0
        w = 0.42 * (1 - _pw(abs(u) / 0.94, 6.0))
        return min(1.0, _pw(1 - abs(v) / max(0.02, w), 0.55) * 1.15)
    c.each(f)


@shape("bolt")              # 稲妻。枝を 2 本、下へ行くほど細らせる
def _bolt(c):
    rng = random.Random(3)
    pts, x, y = [(0.0, -0.96)], 0.0, -0.96
    while y < 0.94:
        x += rng.uniform(-0.26, 0.26)
        y += rng.uniform(0.16, 0.30)
        pts.append((max(-0.9, min(0.9, x)), min(0.96, y)))
    c.path(pts, 0.055, 1.0, 1.1, taper=0.45)
    for k in (2, 4):
        if k + 1 >= len(pts):
            break
        bx, by = pts[k]
        c.path([(bx, by), (bx + rng.uniform(-0.5, 0.5), by + 0.28),
                (bx + rng.uniform(-0.7, 0.7), by + 0.52)],
               0.030, 0.7, 1.2, taper=0.6)


@shape("weld")              # 溶接火花。中心の白点から飛沫が散る
def _weld(c):
    rng = random.Random(9)
    c.each(lambda u, v: _pw(1 - math.hypot(u, v) * 3.0, 1.5))
    for _ in range(14):
        a = rng.uniform(0, math.tau)
        r = rng.uniform(0.30, 0.96)
        c.seg(math.cos(a) * 0.10, math.sin(a) * 0.10,
              math.cos(a) * r, math.sin(a) * r, 0.032,
              rng.uniform(0.45, 0.95), 1.4)


@shape("scan")              # 走査線。磁力視
def _scan(c):
    for k, y in enumerate((-0.55, -0.05, 0.45)):
        c.seg(-0.95, y, 0.95, y, 0.045 - k * 0.009, 1.0 - k * 0.28, 1.2)
    c.each(lambda u, v: _pw(1 - abs(v) * 1.1, 1.2) * _pw(1 - abs(u), 0.8) * 0.10)


# --- 渦 --------------------------------------------------------------------
@shape("swirl")             # 二本腕の渦
def _swirl(c):
    for k in (0.0, math.pi):
        pts = [(math.cos(k + (i / 39.0) * 3.4) * (0.06 + 0.90 * (i / 39.0)),
                math.sin(k + (i / 39.0) * 3.4) * (0.06 + 0.90 * (i / 39.0)))
               for i in range(40)]
        c.path(pts, 0.105, 1.0, 1.2, taper=0.55)


@shape("vortex")            # 四本腕。中心へ吸い込む
def _vortex(c):
    for k in range(4):
        pts = [(math.cos(k * 1.571 + (i / 35.0) * 2.7) * (0.10 + 0.88 * (i / 35.0)),
                math.sin(k * 1.571 + (i / 35.0) * 2.7) * (0.10 + 0.88 * (i / 35.0)))
               for i in range(36)]
        c.path(pts, 0.085, 0.95, 1.3, taper=0.5)
    c.each(lambda u, v: _pw(1 - math.hypot(u, v) * 2.6, 2.0) * 0.75)


# --- 紋 --------------------------------------------------------------------
@shape("glyph")             # 磁界の紋（128px）。同心 + 六角 + 目盛り
def _glyph(c):
    c.ring(0.94, 0.026, 1.0, 1.2)
    c.ring(0.79, 0.048, 0.85, 1.3)
    c.ring(0.38, 0.034, 0.70, 1.3)
    pts = [(math.cos(i * math.pi / 3) * 0.60,
            math.sin(i * math.pi / 3) * 0.60) for i in range(6)]
    for i in range(6):
        a, b = pts[i], pts[(i + 1) % 6]
        c.seg(a[0], a[1], b[0], b[1], 0.032, 0.80, 1.2)
    for i in range(6):
        a = i * math.pi / 3
        c.seg(math.cos(a) * 0.38, math.sin(a) * 0.38,
              math.cos(a) * 0.79, math.sin(a) * 0.79, 0.028, 0.75, 1.3)
    for i in range(24):     # 細かい目盛り。密度が「測っている」感を作る
        a = i * math.pi / 12
        c.seg(math.cos(a) * 0.83, math.sin(a) * 0.83,
              math.cos(a) * 0.92, math.sin(a) * 0.92, 0.014, 0.60, 1.4)
    c.each(lambda u, v: _pw(1 - math.hypot(u, v) * 4.0, 2.0) * 0.45)


@shape("rune")              # 磁極の紋。N/S の弧と極線
def _rune(c):
    c.ring(0.86, 0.045, 0.95, 1.2, arc=1.05, ang=math.pi / 2)
    c.ring(0.86, 0.045, 0.95, 1.2, arc=1.05, ang=-math.pi / 2)
    c.seg(-0.62, 0.0, 0.62, 0.0, 0.055, 1.0, 1.2)
    c.each(lambda u, v: _pw(1 - math.hypot(u, v) * 5.0, 1.6))


# --- 質量 ------------------------------------------------------------------
@shape("smoke")             # 煙。輪郭を二重の波で崩す
def _smoke(c):
    def f(u, v):
        n = (0.84 + 0.20 * math.sin(u * 3.1 + 1.2) * math.cos(v * 2.7 - 0.4)
             + 0.08 * math.sin(u * 7.3 - v * 6.1))
        return _pw(1 - math.hypot(u, v) / max(0.2, n), 1.6) * 0.92
    c.each(f)


@shape("dust")              # 粒立った塵
def _dust(c):
    rng = random.Random(11)
    c.each(lambda u, v: _pw(1 - math.hypot(u, v), 1.9)
           * (0.28 if rng.random() < 0.34 else 1.0))


@shape("gravel")            # 細かい瓦礫。塊 5 つで一粒
def _gravel(c):
    rng = random.Random(5)
    for _ in range(5):
        cx, cy = rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)
        r, rot = rng.uniform(0.16, 0.30), rng.uniform(0, math.pi)
        co, si = math.cos(rot), math.sin(rot)
        c.each(lambda u, v, cx=cx, cy=cy, r=r, co=co, si=si:
               0.95 if (abs((u - cx) * co + (v - cy) * si)
                        + abs(-(u - cx) * si + (v - cy) * co) * 1.3) < r else 0.0)


@shape("debris")            # 角ばった塊。上の稜だけ光らせて厚みを出す
def _debris(c):
    poly = [(-0.62, -0.34), (0.05, -0.72), (0.68, -0.10),
            (0.44, 0.62), (-0.30, 0.70), (-0.74, 0.18)]
    c.fill(poly, 0.72)
    c.seg(-0.62, -0.34, 0.05, -0.72, 0.07, 1.0, 1.0)
    c.seg(0.05, -0.72, 0.68, -0.10, 0.07, 1.0, 1.0)


@shape("plate")             # 鉄板の欠片
def _plate(c):
    poly = [(-0.80, -0.42), (0.72, -0.62), (0.84, 0.30), (-0.62, 0.58)]
    c.fill(poly, 0.68)
    c.seg(-0.80, -0.42, 0.72, -0.62, 0.06, 1.0, 1.0)
    c.seg(0.72, -0.62, 0.84, 0.30, 0.05, 0.55, 1.0)


@shape("nail")              # 太い鉄の破片。先が尖る
def _nail(c):
    c.fill([(-0.88, -0.17), (0.30, -0.23), (0.94, 0.0),
            (0.30, 0.23), (-0.88, 0.17)], 0.72)
    c.seg(-0.88, -0.13, 0.30, -0.17, 0.05, 1.0, 1.0)


@shape("shard")             # 細長い鉄片
def _shard(c):
    c.fill([(-0.95, 0.0), (0.10, -0.30), (0.95, 0.0), (0.10, 0.30)], 0.66)
    c.seg(-0.95, 0.0, 0.10, -0.30, 0.045, 1.0, 1.0)
    c.seg(0.10, -0.30, 0.95, 0.0, 0.045, 1.0, 1.0)


@shape("crescent")          # 薙ぎ払いの弧
def _crescent(c):
    c.ring(0.72, 0.20, 1.0, 1.1, arc=math.pi * 0.80)


@shape("arc")               # 細い弧
def _arc(c):
    c.ring(0.78, 0.080, 1.0, 1.3, arc=math.pi * 0.52)


@shape("claw")              # 三本爪
def _claw(c):
    for off in (-0.40, 0.0, 0.40):
        pts = [(math.cos(a) * 0.80 + off * 0.30, math.sin(a) * 0.80 + off)
               for a in (-0.85, -0.42, 0.0, 0.42, 0.85)]
        c.path(pts, 0.075, 1.0, 1.2, taper=0.55)


@shape("crack")             # 地割れ。中心から枝分かれ
def _crack(c):
    rng = random.Random(31)
    for i in range(5):
        a = i * 1.2566 + rng.uniform(-0.3, 0.3)
        x, y, w = 0.0, 0.0, 0.060
        while math.hypot(x, y) < 0.94:
            a += rng.uniform(-0.35, 0.35)
            s = rng.uniform(0.12, 0.22)
            nx, ny = x + math.cos(a) * s, y + math.sin(a) * s
            c.seg(x, y, nx, ny, w, 1.0, 1.1)
            if rng.random() < 0.3:
                c.seg(x, y, x + math.cos(a + 1.1) * s * 0.8,
                      y + math.sin(a + 1.1) * s * 0.8, w * 0.6, 0.6, 1.2)
            x, y, w = nx, ny, w * 0.87


@shape("plume")             # 立ち上る土煙。上ほど広く薄く
def _plume(c):
    def f(u, v):
        t = _sat((1 - v) * 0.5)
        w = 0.20 + 0.74 * t
        n = 1.0 + 0.22 * math.sin(u * 5.0 + t * 6.0)
        return _pw(1 - abs(u) / (w * n), 1.5) * (1 - t * 0.42) * 0.95
    c.each(f)


@shape("ember")             # 火の粉
def _ember(c):
    c.each(lambda u, v: _pw(1 - math.hypot(u / 0.42, v / 0.86), 1.4))


@shape("flame")             # 炎の舌。縁を揺らす
def _flame(c):
    def f(u, v):
        t = _sat((1 - v) * 0.5)
        w = 0.62 * math.sin(math.pi * _pw(t, 0.75))
        return _pw(1 - abs(u + 0.13 * math.sin(t * 7.0)) / max(0.03, w), 1.1)
    c.each(f)


@shape("drop")              # 雫
def _drop(c):
    def f(u, v):
        r = 0.52 * (1 - _sat((v + 1) * 0.5) * 0.75)
        return 0.95 if math.hypot(u, (v - 0.28) * 0.9) < r else 0.0
    c.each(f)


@shape("splash")            # 飛沫。主滴 + 衛星
def _splash(c):
    rng = random.Random(21)
    c.each(lambda u, v: _pw(1 - math.hypot(u * 1.4, (v + 0.15) * 1.6), 1.4))
    for _ in range(6):
        a, r = rng.uniform(0, math.tau), rng.uniform(0.45, 0.92)
        cx, cy, s = math.cos(a) * r, math.sin(a) * r, rng.uniform(6.0, 12.0)
        c.each(lambda u, v, cx=cx, cy=cy, s=s:
               _pw(1 - math.hypot(u - cx, v - cy) * s, 1.3))


# ---------------------------------------------------------------------------
def _layout():
    """棚詰め。128px を先に並べ、残りを 64px で敷く。"""
    cells, x, y, row_h = {}, 0, 0, 0
    for name in sorted(SHAPES, key=lambda n: 0 if n in BIG else 1):
        s = CELL_BIG if name in BIG else CELL
        if x + s > ATLAS:
            x, y, row_h = 0, y + row_h, 0
        if y + s > ATLAS:
            raise SystemExit(f"アトラスに収まらない: {name}")
        cells[name] = (x, y, s)
        x += s
        row_h = max(row_h, s)
    return cells


CELLS = _layout()


def build_atlas() -> None:
    img = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 0))
    for name, (ox, oy, s) in CELLS.items():
        c = Cell(s)
        SHAPES[name](c)
        c.blit(img, ox, oy)
    img.save(TEX_PATH)
    big = sum(1 for n in CELLS if n in BIG)
    print(f"  atlas {ATLAS}x{ATLAS} / {len(CELLS)} cells ({big} big)")
