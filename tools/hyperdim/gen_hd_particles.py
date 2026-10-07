# -*- coding: utf-8 -*-
"""パーティクル: スプライトアトラスと、色・大きさ・寿命を後から渡せる汎用パーティクル。

スプライトは白（グレースケール + アルファ）で描き、色はスクリプトが
MolangVariableMap で渡す v.cr / v.cg / v.cb で染める。だから同じ「斬撃の弧」が
大剣では蒼、斧では紅に光る。変数が渡らなかった時のために全て `?? 既定値` を付けてある。

スクリプトから渡す変数（全て任意）:
  v.cr v.cg v.cb  色 (0..1)       v.size  大きさ (m)      v.life  寿命 (秒)
  v.rot           画面内の回転 (度) v.count 粒数           v.speed 初速
  v.vx v.vy v.vz  向き             v.spread 散らばり (m)   v.var   スプライトの種類
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hd_common import NS, RP, SCRATCH, write_json  # noqa: E402

PART_DIR = os.path.join(RP, "particles")
TEX = "textures/particle/hd_atlas"
AW, AH = 512, 512
SS = 4  # スーパーサンプリング

FONT_PATHS = ["/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
              "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"]


# ===========================================================================
#  スプライト（すべて白＋アルファ。float 配列 [h, w, 4] で 0..1）
# ===========================================================================
def field(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return (x + 0.5) / w * 2 - 1, (y + 0.5) / h * 2 - 1


def rgba_from(alpha, white=None):
    a = np.clip(alpha, 0, 1)
    out = np.zeros(a.shape + (4,), np.float32)
    c = np.ones_like(a) if white is None else np.clip(white, 0, 1)
    out[..., 0] = c
    out[..., 1] = c
    out[..., 2] = c
    out[..., 3] = a
    return out


def sp_glow(w, h):
    x, y = field(w, h)
    r = np.sqrt(x * x + y * y)
    a = np.clip(1 - r, 0, 1) ** 2.2
    core = np.clip(1 - r * 3, 0, 1)
    return rgba_from(a + core * 0.5)


def sp_spark(w, h):
    x, y = field(w, h)
    r = np.sqrt(x * x + y * y)
    rays = np.clip(1 - np.abs(x) * 9, 0, 1) * np.clip(1 - np.abs(y), 0, 1) ** 2 + \
        np.clip(1 - np.abs(y) * 9, 0, 1) * np.clip(1 - np.abs(x), 0, 1) ** 2
    d1 = np.clip(1 - np.abs(x - y) * 6, 0, 1) * np.clip(1 - r * 1.6, 0, 1)
    d2 = np.clip(1 - np.abs(x + y) * 6, 0, 1) * np.clip(1 - r * 1.6, 0, 1)
    halo = np.clip(1 - r * 1.4, 0, 1) ** 3
    return rgba_from(rays + (d1 + d2) * 0.5 + halo * 0.6)


def sp_star5(w, h):
    S = w * SS
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(10):
        r = S * (0.47 if i % 2 == 0 else 0.19)
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((S / 2 + r * math.cos(a), S / 2 + r * math.sin(a)))
    d.polygon(pts, fill=255)
    img = img.resize((w, h), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    x, y = field(w, h)
    r = np.sqrt(x * x + y * y)
    return rgba_from(a + np.clip(1 - r, 0, 1) ** 3 * 0.45, white=np.clip(1.25 - r, 0.6, 1))


def sp_ring(w, h, width=0.07):
    x, y = field(w, h)
    r = np.sqrt(x * x + y * y)
    a = np.clip(1 - np.abs(r - 0.86) / width, 0, 1) ** 1.5
    return rgba_from(a)


def sp_ring_thick(w, h):
    x, y = field(w, h)
    r = np.sqrt(x * x + y * y)
    a = np.where(r < 0.92, np.clip((r - 0.35) / 0.57, 0, 1) ** 2.4, 0)
    a = a * np.clip((0.96 - r) * 20, 0, 1)
    return rgba_from(a, white=np.clip(0.5 + a, 0, 1))


def sp_impact(w, h):
    x, y = field(w, h)
    r = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    rng = np.random.RandomState(4)
    n = 14
    lens = 0.55 + rng.rand(n) * 0.45
    a = np.zeros_like(r)
    for i in range(n):
        ang = i / n * 2 * math.pi + rng.rand() * 0.2
        d = np.abs(np.angle(np.exp(1j * (th - ang))))
        spike = np.clip(1 - d / (0.13 * (1 - r / lens[i]).clip(0, 1) + 1e-3), 0, 1)
        a = np.maximum(a, spike * (r < lens[i]))
    core = np.clip(1 - r * 2.6, 0, 1)
    return rgba_from(a + core)


def sp_hex(w, h):
    x, y = field(w, h)
    q = np.maximum(np.abs(x) * 0.866 + np.abs(y) * 0.5, np.abs(y))
    a = np.clip(1 - np.abs(q - 0.82) / 0.07, 0, 1) + np.clip(0.8 - q, 0, 1) * 0.25
    return rgba_from(a)


def sp_dot(w, h):
    x, y = field(w, h)
    r = np.sqrt(x * x + y * y)
    return rgba_from(np.clip((0.55 - r) * 6, 0, 1) + np.clip(1 - r, 0, 1) ** 4 * 0.6)


def sp_slash(w, h, thick=0.32, span=200):
    """三日月の斬撃。円弧の中心がスプライトの中心で、回転させると振りの向きが変わる。
    先頭（右上）が太く白熱し、尾（左）に向かって細く消える。"""
    x, y = field(w, h)
    r = np.sqrt(x * x + y * y)
    th = np.degrees(np.arctan2(-y, x))               # 上 = 90, 右 = 0
    start = 90 + span / 2                            # 尾の角度。そこから時計回りに span 度
    s = np.where(th > start, (start + 360 - th) / span, (start - th) / span)
    valid = (s >= 0) & (s <= 1)
    s = np.clip(s, 0, 1)
    prof = s ** 0.9 * np.clip((1 - s) * 7, 0, 1) ** 0.5     # 0 = 尾, 1 = 先端
    outer = 0.92
    inner = outer - thick * prof
    band = valid & (r < outer) & (r > inner)
    depth = np.where(band, (outer - r) / np.maximum(outer - inner, 1e-3), 1)
    a = np.where(band, (1 - depth) ** 0.6 * (0.35 + 0.65 * s), 0)
    rim = np.clip(1 - np.abs(r - outer) / 0.025, 0, 1) * valid * prof
    white = np.clip(1.25 - depth * 1.1, 0.25, 1)
    return rgba_from(a + rim, white=np.maximum(np.where(band, white, 0), rim))


def sp_cross(w, h):
    x, y = field(w, h)
    a = np.zeros_like(x)
    for s in (1, -1):
        d = np.abs(x - s * y) / math.sqrt(2)
        along = np.abs(x + s * y) / math.sqrt(2)
        a = np.maximum(a, np.clip(1 - d / (0.09 * (1 - along / 1.3)), 0, 1) * (along < 1.3))
    return rgba_from(a + np.clip(1 - np.sqrt(x * x + y * y) * 3, 0, 1))


def sp_claw(w, h):
    x, y = field(w, h)
    a = np.zeros_like(x)
    for off in (-0.48, 0.0, 0.48):
        cx = x - off - 0.18 * (y ** 2)
        along = np.clip(1 - np.abs(y) / 0.95, 0, 1)
        a = np.maximum(a, np.clip(1 - np.abs(cx) / (0.08 * along + 1e-3), 0, 1) * along)
    return rgba_from(a)


def _polyline_img(w, h, pts, width, glow=True):
    img = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(img)
    P = [((px * 0.5 + 0.5) * w * SS, (py * 0.5 + 0.5) * h * SS) for px, py in pts]
    for i in range(len(P) - 1):
        wd = max(1, int(width * SS * (1 - i / len(P) * 0.5)))
        d.line([P[i], P[i + 1]], fill=255, width=wd)
    img = img.resize((w, h), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    if glow:
        g = np.asarray(img.filter(ImageFilter.GaussianBlur(w / 16)), np.float32) / 255
        a = np.clip(a + g * 1.2, 0, 1)
    return a


def sp_bolt(w, h):
    rng = np.random.RandomState(7)
    pts = [(-0.1, -0.95)]
    for i in range(1, 8):
        pts.append((rng.uniform(-0.45, 0.45), -0.95 + i * 0.27))
    a = _polyline_img(w, h, pts, w / 18)
    br = [(pts[3][0], pts[3][1]), (pts[3][0] + 0.4, pts[3][1] + 0.3), (0.6, 0.3)]
    a = np.maximum(a, _polyline_img(w, h, br, w / 30) * 0.8)
    return rgba_from(a)


def sp_rift(w, h):
    rng = np.random.RandomState(11)
    pts = [(-0.95, rng.uniform(-0.1, 0.1))]
    for i in range(1, 10):
        pts.append((-0.95 + i * 0.21, rng.uniform(-0.18, 0.18)))
    a = _polyline_img(w, h, pts, w / 14)
    for k in (2, 5, 7):
        p = pts[k]
        a = np.maximum(a, _polyline_img(w, h, [p, (p[0] + 0.15, p[1] + rng.choice([-1, 1]) * 0.4)],
                                        w / 30) * 0.8)
    return rgba_from(a)


def sp_moon(w, h):
    x, y = field(w, h)
    r1 = np.sqrt(x * x + y * y)
    r2 = np.sqrt((x - 0.35) ** 2 + (y + 0.1) ** 2)
    a = np.clip((0.9 - r1) * 12, 0, 1) * np.clip((r2 - 0.72) * 12, 0, 1)
    halo = np.clip(1 - r1, 0, 1) ** 3 * 0.4
    return rgba_from(a + halo)


def sp_shard(w, h):
    x, y = field(w, h)
    q = np.abs(x) / 0.38 + np.abs(y) / 0.95
    a = np.clip((1 - q) * 8, 0, 1)
    white = np.where(x < 0, 1.0, 0.72)
    return rgba_from(a + np.clip(1 - q, 0, 1) * 0.2, white=white)


def sp_petal(w, h):
    x, y = field(w, h)
    q = (x / 0.62) ** 2 + ((y + 0.15 * x * x) / 0.9) ** 2
    notch = np.clip((np.abs(x) * 6 + (y + 0.9) * 3), 0, 1)
    a = np.clip((1 - q) * 6, 0, 1) * notch
    white = 0.7 + 0.3 * np.clip(1 - np.sqrt(x * x + y * y), 0, 1)
    return rgba_from(a, white=white)


def sp_feather(w, h):
    x, y = field(w, h)
    vane = np.clip(1 - (np.abs(x) / (0.36 * (1 - (y * 0.9) ** 2).clip(0, 1) + 1e-3)), 0, 1)
    barbs = 0.8 + 0.2 * np.sin((y * 16 + np.abs(x) * 10))
    shaft = np.clip(1 - np.abs(x) / 0.04, 0, 1)
    a = np.clip(vane * 4, 0, 1) * barbs
    return rgba_from(np.maximum(a, shaft), white=np.where(shaft > 0.5, 0.8, 1.0))


def sp_smoke(w, h):
    rng = np.random.RandomState(3)
    x, y = field(w, h)
    a = np.zeros_like(x)
    for _ in range(9):
        cx, cy, rr = rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), rng.uniform(0.35, 0.6)
        a = np.maximum(a, np.clip(1 - np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / rr, 0, 1) ** 1.5)
    shade = 0.6 + 0.4 * np.clip(-y * 0.5 + 0.5, 0, 1)
    return rgba_from(a * 0.9, white=shade)


def sp_wind(w, h):
    x, y = field(w, h)
    cy = 0.35 * x * x - 0.2
    along = np.clip(1 - np.abs(x), 0, 1)
    a = np.clip(1 - np.abs(y - cy) / (0.07 * along + 0.01), 0, 1) * along ** 0.5
    a2 = np.clip(1 - np.abs(y - cy - 0.3) / (0.04 * along + 0.01), 0, 1) * along * 0.7
    return rgba_from(np.maximum(a, a2))


def sp_flare(w, h):
    x, y = field(w, h)
    a = np.clip(1 - np.abs(y) / (0.35 * (1 - np.abs(x)) ** 1.5 + 0.02), 0, 1) * \
        np.clip(1 - np.abs(x), 0, 1) ** 0.5
    core = np.clip(1 - np.sqrt((x * 0.25) ** 2 + y ** 2) * 2.2, 0, 1)
    return rgba_from(a + core, white=np.clip(0.6 + core, 0, 1))


def sp_beam(w, h):
    x, y = field(w, h)
    taper = np.clip(1 - np.abs(y) ** 6, 0, 1)
    a = np.clip(1 - np.abs(x), 0, 1) ** 1.6 * taper
    core = np.clip(1 - np.abs(x) * 3.5, 0, 1) * taper
    return rgba_from(a + core, white=np.clip(0.55 + core, 0, 1))


def sp_flame_frames(w, h, n=8):
    frames = []
    for f in range(n):
        x, y = field(w, h)
        t = f / n
        wob = 0.12 * np.sin(y * 6 + t * 2 * math.pi)
        width = 0.55 * np.clip((y + 1) / 1.6, 0, 1) ** 0.6 * (1 - t * 0.5)
        a = np.clip(1 - np.abs(x - wob) / (width + 1e-3), 0, 1) * np.clip((1 - y) * 0.9, 0, 1)
        a *= np.clip((y + 1 - t * 1.2) * 2.5, 0, 1)
        core = np.clip(1 - np.abs(x - wob) / (width * 0.4 + 1e-3), 0, 1) * a
        frames.append(rgba_from(a * (1 - t * 0.4), white=np.clip(0.55 + core, 0, 1)))
    return frames


def sp_after(w, h):
    """人型の残像（シルエット）。中が薄く縁が明るい。"""
    img = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(img)
    s = SS
    W = w * s
    # 頭・胴・腕・脚（前のめりに走る姿）
    d.ellipse([W * 0.38, h * s * 0.02, W * 0.62, h * s * 0.15], fill=255)
    d.polygon([(W * 0.32, h * s * 0.16), (W * 0.68, h * s * 0.16), (W * 0.64, h * s * 0.52),
               (W * 0.36, h * s * 0.52)], fill=255)
    d.polygon([(W * 0.30, h * s * 0.17), (W * 0.16, h * s * 0.44), (W * 0.24, h * s * 0.46),
               (W * 0.38, h * s * 0.22)], fill=255)
    d.polygon([(W * 0.70, h * s * 0.17), (W * 0.86, h * s * 0.40), (W * 0.78, h * s * 0.43),
               (W * 0.62, h * s * 0.22)], fill=255)
    d.polygon([(W * 0.37, h * s * 0.50), (W * 0.50, h * s * 0.50), (W * 0.40, h * s * 0.98),
               (W * 0.28, h * s * 0.98)], fill=255)
    d.polygon([(W * 0.50, h * s * 0.50), (W * 0.63, h * s * 0.50), (W * 0.74, h * s * 0.98),
               (W * 0.61, h * s * 0.98)], fill=255)
    img = img.resize((w, h), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    inner = np.asarray(img.filter(ImageFilter.MinFilter(5)), np.float32) / 255
    rim = np.clip(a - inner, 0, 1)
    return rgba_from(a * 0.45 + rim * 0.9, white=np.clip(0.6 + rim, 0, 1))


def sp_circle(w, h, kind=0):
    """魔法陣。同心円・六芒星（または八芒星）・外周のルーン刻み。"""
    S = w * SS
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    c = S / 2

    def circ(r, wd):
        d.ellipse([c - r, c - r, c + r, c + r], outline=255, width=max(1, int(wd)))

    circ(S * 0.48, S * 0.016)
    circ(S * 0.44, S * 0.008)
    circ(S * 0.31, S * 0.012)
    circ(S * 0.12, S * 0.010)
    pts_n = 6 if kind == 0 else 8
    step = 2 if kind == 0 else 3
    poly = [(c + S * 0.31 * math.cos(2 * math.pi * i / pts_n - math.pi / 2),
             c + S * 0.31 * math.sin(2 * math.pi * i / pts_n - math.pi / 2)) for i in range(pts_n)]
    for i in range(pts_n):
        d.line([poly[i], poly[(i + step) % pts_n]], fill=255, width=int(S * 0.008))
    # 外周のルーン帯: 短い刻みと小さな記号
    rng = np.random.RandomState(20 + kind)
    for i in range(48):
        a = 2 * math.pi * i / 48
        r0, r1 = S * 0.445, S * 0.475
        if i % 4 == 0:
            d.line([(c + r0 * math.cos(a), c + r0 * math.sin(a)),
                    (c + r1 * math.cos(a), c + r1 * math.sin(a))], fill=255, width=int(S * 0.008))
        else:
            rr = (r0 + r1) / 2
            x0, y0 = c + rr * math.cos(a), c + rr * math.sin(a)
            g = S * 0.008
            for _ in range(2):
                dx, dy = rng.uniform(-1, 1, 2) * g
                d.line([(x0 - dx, y0 - dy), (x0 + dx, y0 + dy)], fill=255, width=max(1, int(g * 0.6)))
    # 内側の小円
    for i in range(pts_n):
        a = 2 * math.pi * i / pts_n - math.pi / 2
        x0, y0 = c + S * 0.38 * math.cos(a), c + S * 0.38 * math.sin(a)
        d.ellipse([x0 - S * 0.03, y0 - S * 0.03, x0 + S * 0.03, y0 + S * 0.03], outline=255,
                  width=int(S * 0.006))
    img = img.resize((w, h), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    g = np.asarray(img.filter(ImageFilter.GaussianBlur(w / 40)), np.float32) / 255
    return rgba_from(np.clip(a + g * 0.9, 0, 1))


def sp_kanji(w, h, ch):
    """必殺の一文字。太い縁取りの白文字（色はパーティクル側で乗る）。"""
    font = None
    for p in FONT_PATHS:
        if os.path.exists(p):
            font = ImageFont.truetype(p, int(h * SS * 0.86))
            break
    if font is None:
        return rgba_from(np.zeros((h, w), np.float32))
    S = w * SS
    img = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(img)
    d.text((S / 2, S / 2), ch, font=font, fill=255, anchor="mm", stroke_width=int(S * 0.035),
           stroke_fill=150)
    img = img.resize((w, h), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    core = np.asarray(img.point(lambda v: 255 if v > 200 else 0), np.float32) / 255
    return rgba_from(np.clip(a * 1.2, 0, 1), white=np.clip(0.45 + core, 0, 1))


# アトラスの配置: 名前 -> (x, y, w, h)
LAYOUT = {}
SPRITES = []


def place(name, x, y, w, h, fn, *args):
    LAYOUT[name] = (x, y, w, h)
    SPRITES.append((name, x, y, w, h, fn, args))


row0 = [("glow", sp_glow), ("spark", sp_spark), ("star", sp_star5), ("ring", sp_ring),
        ("ring_thick", sp_ring_thick), ("impact", sp_impact), ("hex", sp_hex), ("dot", sp_dot)]
for i, (n, f) in enumerate(row0):
    place(n, i * 64, 0, 64, 64, f)
row1 = [("slash_a", sp_slash, 0.36, 200), ("slash_b", sp_slash, 0.16, 250), ("cross", sp_cross),
        ("claw", sp_claw), ("bolt", sp_bolt), ("rift", sp_rift), ("moon", sp_moon),
        ("shard", sp_shard)]
for i, entry in enumerate(row1):
    place(entry[0], i * 64, 64, 64, 64, entry[1], *entry[2:])
row2 = [("petal", sp_petal), ("feather", sp_feather), ("smoke", sp_smoke), ("wind", sp_wind)]
for i, (n, f) in enumerate(row2):
    place(n, i * 64, 128, 64, 64, f)
place("flare", 256, 128, 128, 32, sp_flare)
place("beam", 384, 128, 32, 128, sp_beam)
place("after", 416, 128, 64, 128, sp_after)
place("flame", 0, 192, 256, 32, None)            # 8 コマ × 32px
place("circle", 0, 256, 128, 128, sp_circle, 0)
place("circle2", 128, 256, 128, 128, sp_circle, 1)
KANJI = "斬撃破滅絶"
for i, ch in enumerate(KANJI):
    place(f"kanji{i}", 256 + (i % 4) * 64, 256 + (i // 4) * 64, 64, 64, sp_kanji, ch)
place("slash_c", 0, 384, 128, 128, sp_slash, 0.42, 220)   # 大きい必殺技用の弧


def build_atlas():
    atlas = np.zeros((AH, AW, 4), np.float32)
    for name, x, y, w, h, fn, args in SPRITES:
        if name == "flame":
            for f, fr in enumerate(sp_flame_frames(32, 32)):
                atlas[y:y + 32, x + f * 32:x + f * 32 + 32] = fr
            continue
        atlas[y:y + h, x:x + w] = fn(w, h, *args)
    img = Image.fromarray((np.clip(atlas, 0, 1) * 255).astype(np.uint8), "RGBA")
    out = os.path.join(RP, "textures", "particle", "hd_atlas.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, optimize=True)
    return img


# ===========================================================================
#  パーティクル定義
# ===========================================================================
COL = ["v.cr ?? 1.0", "v.cg ?? 1.0", "v.cb ?? 1.0"]
AGE = "(v.particle_age / v.particle_lifetime)"


def uv(name, frames=None):
    x, y, w, h = LAYOUT[name]
    u = {"texture_width": AW, "texture_height": AH, "uv": [x, y], "uv_size": [w, h]}
    return u


def tint(alpha, whiten=None):
    """色。whiten を与えると生まれた瞬間は白く、すぐに属性色へ落ちる（発光の芯）。"""
    if whiten:
        c = [f"math.lerp({c}, 1.0, math.clamp(1.0 - {AGE} * {whiten}, 0.0, 1.0))" for c in COL]
    else:
        c = list(COL)
    return {"color": c + [alpha]}


def effect(ident, material, comps):
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": f"{NS}:{ident}",
                        "basic_render_parameters": {"material": material, "texture": TEX}},
        "components": comps}}


def instant(count="v.count ?? 1"):
    return {"minecraft:emitter_rate_instant": {"num_particles": count},
            "minecraft:emitter_lifetime_once": {"active_time": 0}}


FADE = f"math.clamp((1.0 - {AGE}) * 1.6, 0.0, 1.0)"
FADE_IN_OUT = f"math.clamp(math.min({AGE} * 6.0, (1.0 - {AGE}) * 2.5), 0.0, 1.0)"


def P_point(dir_=None):
    d = dir_ or ["v.vx ?? 0", "v.vy ?? 0", "v.vz ?? 0"]
    return {"minecraft:emitter_shape_point": {"offset": [0, 0, 0], "direction": d}}


def P_sphere(radius="v.spread ?? 0.1", direction="outwards", surface=False):
    return {"minecraft:emitter_shape_sphere": {"radius": radius, "direction": direction,
                                               "surface_only": surface}}


def P_disc(radius="v.spread ?? 0.5", direction="outwards"):
    return {"minecraft:emitter_shape_disc": {"radius": radius, "plane_normal": [0, 1, 0],
                                             "direction": direction}}


def bb(size, sprite, mode="lookat_xyz", **extra):
    d = {"size": size, "facing_camera_mode": mode, "uv": uv(sprite)}
    d["uv"].update(extra.pop("uv_extra", {}))
    d.update(extra)
    return {"minecraft:particle_appearance_billboard": d}


def life(expr):
    return {"minecraft:particle_lifetime_expression": {"max_lifetime": expr}}


def spin(rot="v.rot ?? 0", rate=0):
    return {"minecraft:particle_initial_spin": {"rotation": rot, "rotation_rate": rate}}


def motion(acc=(0, 0, 0), drag=0):
    return {"minecraft:particle_motion_dynamic": {"linear_acceleration": list(acc),
                                                   "linear_drag_coefficient": drag}}


def speed(expr="v.speed ?? 0"):
    return {"minecraft:particle_initial_speed": expr}


def merge(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out


def particles():
    S = "(v.size ?? 1.0)"
    E = {}
    # ---- 発光の基本 -----------------------------------------------------
    E["glow"] = effect("glow", "particles_add", merge(
        instant(), P_point(), speed(), motion(drag=2.5), life("v.life ?? 0.4"),
        bb([f"{S} * 0.5 * (1.0 - {AGE} * 0.5)"] * 2, "glow"), tint(FADE, whiten=4)))
    E["trail"] = effect("trail", "particles_add", merge(
        instant(), P_point(), speed(), life("v.life ?? 0.22"),
        bb([f"{S} * 0.42 * (1.0 - {AGE} * 0.7)"] * 2, "glow"),
        tint(f"math.clamp((1.0 - {AGE}) * 1.3, 0.0, 1.0)", whiten=3)))
    E["spark"] = effect("spark", "particles_add", merge(
        instant("v.count ?? 8"), P_sphere("0.05"), speed("(v.speed ?? 7.0) * (0.5 + v.particle_random_1)"),
        motion((0, -14, 0), 3.2), life("(v.life ?? 0.35) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.07", f"{S} * 0.42 * (1.0 - {AGE})"], "spark", "lookat_direction"),
        tint(FADE, whiten=5)))
    E["impact"] = effect("impact", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.16"),
        bb([f"{S} * (0.6 + {AGE} * 1.6)"] * 2, "impact"), spin("v.particle_random_1 * 360"),
        tint(FADE, whiten=2.5)))
    E["star"] = effect("star", "particles_add", merge(
        instant("v.count ?? 6"), P_sphere("v.spread ?? 0.8", "outwards"),
        speed("(v.speed ?? 0.6) * v.particle_random_1"), motion(drag=1.2),
        life("(v.life ?? 1.0) * (0.5 + v.particle_random_2)"),
        bb([f"{S} * 0.22 * (0.5 + 0.5 * math.sin(v.particle_age * 900.0 + v.particle_random_3 * 360.0))"] * 2,
           "star"), spin("v.particle_random_4 * 70", 60), tint(FADE_IN_OUT, whiten=2)))
    E["dot"] = effect("dot", "particles_add", merge(
        instant("v.count ?? 10"), P_sphere("v.spread ?? 0.6"), speed("(v.speed ?? 1.0) * v.particle_random_1"),
        motion((0, "v.grav ?? 0", 0), 1.5), life("(v.life ?? 0.6) * (0.6 + v.particle_random_2 * 0.8)"),
        bb([f"{S} * 0.08"] * 2, "dot"), tint(FADE, whiten=3)))

    # ---- 斬撃 -----------------------------------------------------------
    for ident, sprite, base_life in (("slash", "slash_a", 0.24), ("slash_thin", "slash_b", 0.22),
                                     ("slash_big", "slash_c", 0.42)):
        E[ident] = effect(ident, "particles_add", merge(
            instant(), P_point(), life(f"v.life ?? {base_life}"),
            bb([f"{S} * 2.2 * (0.85 + {AGE} * 0.35)"] * 2, sprite), spin(),
            tint(f"math.clamp((1.0 - {AGE}) * 1.8, 0.0, 1.0)", whiten=3)))
    E["slash_flat"] = effect("slash_flat", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.26"),
        bb([f"{S} * 2.4 * (0.85 + {AGE} * 0.4)"] * 2, "slash_a", "emitter_transform_xz"), spin(),
        tint(f"math.clamp((1.0 - {AGE}) * 1.8, 0.0, 1.0)", whiten=3)))
    E["cross"] = effect("cross", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.28"),
        bb([f"{S} * 1.6 * (0.7 + {AGE} * 0.6)"] * 2, "cross"), spin(),
        tint(FADE, whiten=3)))
    E["claw"] = effect("claw", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.3"),
        bb([f"{S} * 1.4 * (0.9 + {AGE} * 0.3)"] * 2, "claw"), spin(),
        tint(FADE, whiten=3)))
    E["flare"] = effect("flare", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.3"),
        bb([f"{S} * 3.0 * (0.4 + {AGE} * 1.2)", f"{S} * 0.75 * (1.0 - {AGE})"], "flare"), spin(),
        tint(FADE, whiten=2)))
    E["kanji"] = effect("kanji", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.9"),
        {"minecraft:particle_appearance_billboard": {
            "size": [f"{S} * (1.0 + math.clamp(0.25 - {AGE}, 0.0, 0.25) * 2.4)"] * 2,
            "facing_camera_mode": "lookat_xyz",
            "uv": {"texture_width": AW, "texture_height": AH,
                   "uv": [f"256 + math.mod(math.floor(v.var ?? 0), 4) * 64",
                          f"256 + math.floor((v.var ?? 0) / 4) * 64"], "uv_size": [64, 64]}}},
        spin("v.rot ?? 0"), tint(FADE_IN_OUT, whiten=1.5)))

    # ---- 輪・陣 ---------------------------------------------------------
    E["ring"] = effect("ring", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.35"),
        bb([f"{S} * 2.0 * math.pow({AGE}, 0.5)"] * 2, "ring"), tint(FADE, whiten=3)))
    E["ring_flat"] = effect("ring_flat", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.45"),
        bb([f"{S} * 2.0 * math.pow({AGE}, 0.45)"] * 2, "ring_thick", "emitter_transform_xz"),
        tint(FADE, whiten=3)))
    E["ring_thin_flat"] = effect("ring_thin_flat", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.5"),
        bb([f"{S} * 2.0 * math.pow({AGE}, 0.6)"] * 2, "ring", "emitter_transform_xz"),
        tint(FADE, whiten=2)))
    for ident, sprite, mode in (("circle", "circle", "emitter_transform_xz"),
                                ("circle2", "circle2", "emitter_transform_xz"),
                                ("circle_v", "circle", "rotate_y")):
        E[ident] = effect(ident, "particles_add", merge(
            instant(), P_point(), life("v.life ?? 1.2"),
            bb([f"{S} * 2.0 * math.clamp({AGE} * 5.0, 0.0, 1.0)"] * 2, sprite, mode),
            spin("v.rot ?? 0", "v.spin ?? 45"),
            tint(f"math.clamp(math.min({AGE} * 5.0, (1.0 - {AGE}) * 3.0), 0.0, 1.0)")))
    E["hex"] = effect("hex", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.6"),
        bb([f"{S} * 0.6"] * 2, "hex"), spin("v.rot ?? 0"), tint(FADE_IN_OUT)))
    E["pillar"] = effect("pillar", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.6"),
        bb([f"{S} * (0.4 + math.sin(math.min({AGE} * 3.0, 1.0) * 90.0) * 0.8) * (1.2 - {AGE})",
            f"(v.height ?? 8.0) * (0.6 + math.min({AGE} * 4.0, 1.0) * 0.4)"], "beam", "rotate_y"),
        tint(FADE, whiten=2)))

    # ---- 素材感のある粒 ---------------------------------------------------
    E["shard"] = effect("shard", "particles_add", merge(
        instant("v.count ?? 8"), P_sphere("v.spread ?? 0.2"),
        speed("(v.speed ?? 6.0) * (0.4 + v.particle_random_1 * 0.8)"),
        motion((0, "v.grav ?? -16", 0), 1.0), life("(v.life ?? 0.7) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.14", f"{S} * 0.3"], "shard"), spin("v.particle_random_3 * 360", "(v.particle_random_4 - 0.5) * 720"),
        tint(FADE, whiten=4)))
    E["petal"] = effect("petal", "particles_blend", merge(
        instant("v.count ?? 8"), P_sphere("v.spread ?? 0.8"),
        speed("(v.speed ?? 2.0) * v.particle_random_1"), motion((0, -1.2, 0), 1.6),
        life("(v.life ?? 1.6) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.16", f"{S} * 0.2"], "petal"),
        spin("v.particle_random_3 * 360", "(v.particle_random_4 - 0.5) * 540"),
        tint(FADE)))
    E["feather"] = effect("feather", "particles_blend", merge(
        instant("v.count ?? 6"), P_sphere("v.spread ?? 1.0"),
        speed("(v.speed ?? 1.2) * v.particle_random_1"), motion((0, -0.8, 0), 1.8),
        life("(v.life ?? 2.0) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.18", f"{S} * 0.36"], "feather"),
        spin("v.particle_random_3 * 360", "(v.particle_random_4 - 0.5) * 200"),
        tint(FADE)))
    E["smoke"] = effect("smoke", "particles_blend", merge(
        instant("v.count ?? 6"), P_sphere("v.spread ?? 0.5"),
        speed("(v.speed ?? 1.2) * v.particle_random_1"), motion((0, 0.8, 0), 2.0),
        life("(v.life ?? 1.0) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * (0.4 + {AGE} * 0.9)"] * 2, "smoke"), spin("v.particle_random_3 * 360", 20),
        {"minecraft:particle_appearance_tinting": {"color": [
            "(v.cr ?? 0.25)", "(v.cg ?? 0.24)", "(v.cb ?? 0.28)", f"0.75 * {FADE}"]}}))
    E["dust"] = effect("dust", "particles_blend", merge(
        instant("v.count ?? 12"), P_disc("v.spread ?? 0.6"),
        speed("(v.speed ?? 5.0) * (0.5 + v.particle_random_1 * 0.5)"), motion((0, 0.3, 0), 3.5),
        life("(v.life ?? 0.8) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * (0.35 + {AGE} * 0.6)"] * 2, "smoke"), spin("v.particle_random_3 * 360", 30),
        {"minecraft:particle_appearance_tinting": {"color": [
            "(v.cr ?? 0.62)", "(v.cg ?? 0.56)", "(v.cb ?? 0.48)", f"0.7 * {FADE}"]}}))
    E["flame"] = effect("flame", "particles_add", merge(
        instant("v.count ?? 6"), P_sphere("v.spread ?? 0.4"),
        speed("(v.speed ?? 1.5) * v.particle_random_1"), motion((0, 3.0, 0), 2.0),
        life("(v.life ?? 0.6) * (0.6 + v.particle_random_2 * 0.6)"),
        {"minecraft:particle_appearance_billboard": {
            "size": [f"{S} * 0.35 * (1.0 - {AGE} * 0.4)"] * 2, "facing_camera_mode": "rotate_y",
            "uv": {"texture_width": AW, "texture_height": AH,
                   "flipbook": {"base_UV": [0, 192], "size_UV": [32, 32], "step_UV": [32, 0],
                                "frames_per_second": 14, "max_frame": 8,
                                "stretch_to_lifetime": True}}}},
        tint(FADE, whiten=2.5)))
    E["ember"] = effect("ember", "particles_add", merge(
        instant("v.count ?? 8"), P_sphere("v.spread ?? 0.6"),
        speed("(v.speed ?? 1.0) * v.particle_random_1"), motion((0, 1.8, 0), 0.8),
        life("(v.life ?? 1.2) * (0.5 + v.particle_random_2 * 0.8)"),
        bb([f"{S} * 0.07"] * 2, "dot"), tint(FADE_IN_OUT, whiten=1.5)))
    E["bolt"] = effect("bolt", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.16"),
        bb([f"{S} * 1.2", f"{S} * 2.4"], "bolt"), spin("v.rot ?? (v.particle_random_1 * 360)"),
        tint(f"math.mod(math.floor(v.particle_age * 40.0), 2) > 0 ? 0.35 : 1.0", whiten=1)))
    E["rift"] = effect("rift", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.7"),
        bb([f"{S} * 2.6", f"{S} * 2.6 * (0.15 + math.min({AGE} * 6.0, 1.0) * 0.85)"], "rift"),
        spin(), tint(FADE_IN_OUT, whiten=1.5)))
    E["crack_flat"] = effect("crack_flat", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 1.0"),
        bb([f"{S} * 2.6", f"{S} * 2.6"], "rift", "emitter_transform_xz"), spin(),
        tint(FADE_IN_OUT, whiten=1)))
    E["moon"] = effect("moon", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 1.0"),
        bb([f"{S} * 2.0"] * 2, "moon"), spin("v.rot ?? 0", 30), tint(FADE_IN_OUT, whiten=1)))
    E["speedline"] = effect("speedline", "particles_add", merge(
        instant("v.count ?? 6"), P_sphere("v.spread ?? 0.8", ["v.vx ?? 0", "v.vy ?? 0", "v.vz ?? 1"]),
        speed("(v.speed ?? 14.0) * (0.7 + v.particle_random_1 * 0.6)"), motion(drag=3.0),
        life("(v.life ?? 0.25) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.05", f"{S} * 1.1"], "flare", "lookat_direction"), tint(FADE)))
    E["wind"] = effect("wind", "particles_add", merge(
        instant("v.count ?? 4"), P_sphere("v.spread ?? 0.8", ["v.vx ?? 0", "v.vy ?? 0", "v.vz ?? 1"]),
        speed("(v.speed ?? 6.0) * (0.7 + v.particle_random_1 * 0.6)"), motion(drag=2.4),
        life("(v.life ?? 0.4) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.9", f"{S} * 0.45"], "wind", "lookat_direction"), tint(FADE, whiten=2)))
    E["afterimage"] = effect("afterimage", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.4"),
        bb([f"{S} * 1.0", f"{S} * 2.0"], "after", "rotate_y"),
        tint(f"0.85 * math.clamp(1.0 - {AGE}, 0.0, 1.0)")))
    E["snow"] = effect("snow", "particles_add", merge(
        instant("v.count ?? 10"), P_sphere("v.spread ?? 1.0"),
        speed("(v.speed ?? 0.6) * v.particle_random_1"), motion((0, -1.4, 0), 1.0),
        life("(v.life ?? 1.4) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.12"] * 2, "star"), spin("v.particle_random_3 * 90", 90), tint(FADE_IN_OUT)))

    # ---- 動きのある流れ ---------------------------------------------------
    # 竜巻: 粒が螺旋を描きながら昇る（パラメトリック運動）
    E["vortex"] = effect("vortex", "particles_add", merge(
        {"minecraft:emitter_rate_steady": {"spawn_rate": "v.rate ?? 60", "max_particles": 200},
         "minecraft:emitter_lifetime_once": {"active_time": "v.life ?? 1.0"},
         "minecraft:emitter_shape_point": {"offset": [0, 0, 0]}},
        life("0.8"),
        {"minecraft:particle_initial_speed": 0,
         "minecraft:particle_motion_parametric": {"relative_position": [
             f"math.cos(v.particle_age * 720.0 + v.particle_random_1 * 360.0) * {S} * (0.3 + {AGE})",
             f"{AGE} * (v.height ?? 4.0)",
             f"math.sin(v.particle_age * 720.0 + v.particle_random_1 * 360.0) * {S} * (0.3 + {AGE})"]}},
        bb([f"{S} * 0.5", f"{S} * 0.25"], "wind", "lookat_xyz"),
        spin("v.particle_random_2 * 360", 300), tint(FADE_IN_OUT, whiten=2)))
    # 収束: 球面から中心へ吸い込まれる溜め
    E["converge"] = effect("converge", "particles_add", merge(
        instant("v.count ?? 16"), P_sphere("v.spread ?? 2.0", "inwards", True),
        speed(f"(v.spread ?? 2.0) / (v.life ?? 0.5) * 1.05"), life("v.life ?? 0.5"),
        bb([f"{S} * 0.05", f"{S} * 0.5"], "flare", "lookat_direction"),
        tint(FADE_IN_OUT, whiten=1)))
    # 周回: 中心を回りながら縮む
    E["orbit"] = effect("orbit", "particles_add", merge(
        instant("v.count ?? 10"), P_point([0, 0, 0]), life("v.life ?? 0.8"),
        {"minecraft:particle_initial_speed": 0,
         "minecraft:particle_motion_parametric": {"relative_position": [
             f"math.cos(v.particle_age * 540.0 + v.particle_random_1 * 360.0) * (v.spread ?? 1.5) * (1.0 - {AGE})",
             f"(v.particle_random_2 - 0.5) * (v.spread ?? 1.5) * (1.0 - {AGE})",
             f"math.sin(v.particle_age * 540.0 + v.particle_random_1 * 360.0) * (v.spread ?? 1.5) * (1.0 - {AGE})"]}},
        bb([f"{S} * 0.16"] * 2, "glow"), tint(FADE_IN_OUT, whiten=1)))
    # 足元から立ち昇る闘気
    E["aura"] = effect("aura", "particles_add", merge(
        instant("v.count ?? 6"), P_disc("v.spread ?? 0.5", "outwards"),
        speed("0.2"), motion((0, 2.6, 0), 1.2), life("(v.life ?? 0.7) * (0.6 + v.particle_random_1 * 0.6)"),
        bb([f"{S} * 0.22 * (1.0 - {AGE} * 0.6)", f"{S} * 0.5 * (1.0 - {AGE} * 0.3)"], "flame", "rotate_y",
           uv_extra={"uv": [96, 192], "uv_size": [32, 32]}),
        tint(FADE_IN_OUT, whiten=1)))
    return E


def main():
    atlas = build_atlas()
    os.makedirs(PART_DIR, exist_ok=True)
    for f in os.listdir(PART_DIR):
        if f.endswith(".particle.json"):
            os.remove(os.path.join(PART_DIR, f))
    E = particles()
    for name, doc in E.items():
        write_json(os.path.join(PART_DIR, f"{name}.particle.json"), doc)
    # 確認用: 黒地にアトラスを色付きで敷く
    if os.environ.get("HD_PREVIEW"):
        bg = Image.new("RGBA", atlas.size, (20, 22, 30, 255))
        tinted = Image.new("RGBA", atlas.size, (120, 200, 255, 255))
        tinted.putalpha(atlas.split()[3])
        bg.alpha_composite(tinted)
        bg.alpha_composite(atlas)
        os.makedirs(SCRATCH, exist_ok=True)
        bg.resize((1024, 1024), Image.NEAREST).save(os.path.join(SCRATCH, "atlas.png"))
    print(f"  particles: {len(E)}  sprites: {len(LAYOUT)}")


if __name__ == "__main__":
    main()
