# -*- coding: utf-8 -*-
"""アストロ・ナノギア — 2D の UI 一式（HUD グリフ・フォーム用アイコン・惑星紋章・アイテムアイコン・パックアイコン）。

書き出すもの
  packs/astro_RP/font/glyph_EA.png      HUD 用グリフ（256x256、16 px セル、1:1 のドット絵）
  packs/astro_RP/font/glyph_EB.png      カットイン用の大きな絵（512x512、32 px セル）
  packs/astro_BP/scripts/glyphs.js      G（グリフの文字）と bar() などの組み立て関数
  tools/astro/UI.md                     グリフの一覧と HUD の組み方（この生成スクリプトが書く）
  packs/astro_RP/textures/ui/astro/     ターミナルの惑星紋章（128x128）とメニューアイコン（64x64）
  packs/astro_RP/textures/items/astro/  素材・道具のアイコンとスーツのアイコン（64x64）
  packs/astro_{BP,RP}/pack_icon.png     キービジュアル（256x256）
  build_preview/astro/glyphs_EA.png / glyphs_EB.png / docs/astro/hud.png   プレビュー

グリフの規則（統合版のフォント）
  * U+XXRC → font/glyph_XX.png の R 行 C 列（16x16 のマス）。E0/E1 はバニラ、E2/E3 は他のパックと衝突しやすく、
    2E–9F・F9–FF は日本語・繁体字のロケールが使うので使わない。このアドオンは EA（HUD）と EB（大きな絵）。
  * 送り幅 = そのマスの不透明な列の範囲（空の列は詰められる）＋約 1 GUI px の隙間。幅を固定したいグリフは
    両端の列にかすかな画素（アルファ 20）を置く。完全に透明な画素は数えられない。
  * § の色はグリフを染めないので、惑星ごとに色違いのグリフを作る。
  * 絵は 16 px セルの 4〜11 行（文字の高さ）に収める。大きなアイコンも 2〜13 行の内側。
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, HERE)
import astro_data as D  # noqa: E402

BP = os.path.join(ROOT, "packs", "astro_BP")
RP = os.path.join(ROOT, "packs", "astro_RP")
FONT_DIR = os.path.join(RP, "font")
UI_DIR = os.path.join(RP, "textures", "ui", "astro")
ITEM_DIR = os.path.join(RP, "textures", "items", "astro")
SCRATCH = os.environ.get("ASTRO_SCRATCH", os.path.join(ROOT, "build_preview", "astro"))
DOCS = os.path.join(ROOT, "docs", "astro")
GLYPHS_JS = os.path.join(BP, "scripts", "glyphs.js")
UI_MD = os.path.join(HERE, "UI.md")

PAGE_HUD = 0xEA          # 256x256（16 px セル）
PAGE_ART = 0xEB          # 512x512（32 px セル）
FORBIDDEN_PAGES = set(range(0x2E, 0xA0)) | {0xE0, 0xE1, 0xE2, 0xE3} | set(range(0xF9, 0x100))

KEYS = list(D.PLANET_KEYS)
KINDS = list(D.MOVE_KINDS)

FONT_JP = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
FONT_SYM = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SYM_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ---------------------------------------------------------------------------
#  色
# ---------------------------------------------------------------------------
INK = (6, 9, 18)              # 縁取り
PLATE = (12, 18, 32)          # 暗い半透明の地
METAL_L = (226, 234, 244)
METAL = (150, 164, 184)
METAL_D = (74, 86, 108)
WHITE = (255, 255, 255)
GOLD = (255, 206, 72)
GOLD_L = (255, 246, 196)
GOLD_D = (178, 104, 18)
RED = (255, 64, 64)
FAINT = (8, 12, 24)
FAINT_A = 20

# HUD の惑星色（テキスト色コード tc と揃えた見分けやすい色。発光色 glow は水色が多いので HUD 用に分ける）
HUD_COL = {
    "mercury": (120, 232, 255),
    "venus": (255, 238, 120),
    "earth": (88, 255, 146),
    "mars": (255, 84, 60),
    "jupiter": (240, 150, 88),
    "saturn": (232, 206, 168),
    "uranus": (80, 240, 214),
    "neptune": (84, 128, 255),
    "sol": (255, 192, 36),
}


def mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def shade(c, k):
    return tuple(min(255.0, c[i] * k) for i in range(3))


def lighten(c, t):
    return mix(c, WHITE, t)


def grey(c, t=1.0):
    g = 0.30 * c[0] + 0.59 * c[1] + 0.11 * c[2]
    return mix(c, (g, g, g), t)


# ---------------------------------------------------------------------------
#  ドット絵の小さな画布（RGBA float、0..255）
# ---------------------------------------------------------------------------
class Px:
    def __init__(self, w, h=None):
        self.w, self.h = w, (h if h is not None else w)
        self.a = np.zeros((self.h, self.w, 4), np.float32)

    def put(self, x, y, c, a=255.0):
        """アルファを重ねて塗る（over）。"""
        x, y = int(x), int(y)
        if not (0 <= x < self.w and 0 <= y < self.h) or a <= 0:
            return
        src = a / 255.0
        d = self.a[y, x]
        da = d[3] / 255.0
        oa = src + da * (1 - src)
        if oa <= 0:
            return
        for i in range(3):
            d[i] = (c[i] * src + d[i] * da * (1 - src)) / oa
        d[3] = oa * 255.0

    def set(self, x, y, c, a=255.0):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x, :3] = c[:3]
            self.a[y, x, 3] = a

    def fill_mask(self, m, c, a=255.0, over=True):
        for y, x in zip(*np.nonzero(m)):
            (self.put if over else self.set)(x, y, c, a)

    def bitmap(self, x0, y0, rows, pal):
        """rows: 文字列の行。pal: 文字 -> (色, アルファ)。'.' と ' ' は透明。"""
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in ". ":
                    continue
                c, a = pal[ch]
                self.put(x0 + i, y0 + j, c, a)

    def alpha(self):
        return self.a[..., 3]

    def image(self):
        return Image.fromarray(np.clip(self.a + 0.5, 0, 255).astype(np.uint8), "RGBA")


def poly_mask(w, h, pts, ox=0.0, oy=0.0):
    """画素の中心が多角形の内側か（偶奇則）。"""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    xs += 0.5 - ox
    ys += 0.5 - oy
    inside = np.zeros((h, w), bool)
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if y1 == y2:
            continue
        cond = (ys >= min(y1, y2)) & (ys < max(y1, y2))
        xint = x1 + (ys - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cond & (xs < xint)
    return inside


def disc_mask(w, h, cx, cy, r):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return (xs + 0.5 - cx) ** 2 + (ys + 0.5 - cy) ** 2 <= r * r


def erode(m):
    e = m.copy()
    e[1:, :] &= m[:-1, :]
    e[:-1, :] &= m[1:, :]
    e[:, 1:] &= m[:, :-1]
    e[:, :-1] &= m[:, 1:]
    e[0, :] = e[-1, :] = False
    e[:, 0] = e[:, -1] = False
    return e & m


def dilate(m, diag=False):
    d = m.copy()
    d[1:, :] |= m[:-1, :]
    d[:-1, :] |= m[1:, :]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    if diag:
        d[1:, 1:] |= m[:-1, :-1]
        d[1:, :-1] |= m[:-1, 1:]
        d[:-1, 1:] |= m[1:, :-1]
        d[:-1, :-1] |= m[1:, 1:]
    return d


def edge(m):
    return m & ~erode(m)


# ---------------------------------------------------------------------------
#  決まった乱数（値ノイズ）
# ---------------------------------------------------------------------------
_PERM = np.random.default_rng(20261018).permutation(4096)


def _hash3(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    return _PERM[np.abs(h) % 4096] / 4095.0


def vnoise3(x, y, z, seed=0):
    xi, yi, zi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64), np.floor(z).astype(np.int64)
    xf, yf, zf = x - xi, y - yi, z - zi
    u, v, w = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf), zf * zf * (3 - 2 * zf)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                wt = (u if dx else 1 - u) * (v if dy else 1 - v) * (w if dz else 1 - w)
                out = out + wt * _hash3(xi + dx, yi + dy, zi + dz, seed)
    return out


def fbm3(x, y, z, seed=0, octaves=4, freq=1.0, gain=0.5):
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        tot = tot + amp * vnoise3(x * freq, y * freq, z * freq, seed + o * 17)
        norm += amp
        amp *= gain
        freq *= 2.0
    return tot / norm


# ---------------------------------------------------------------------------
#  惑星の描画（球の模様 × 陰影。小さいものはセル調のくっきりした段階、大きいものは滑らか）
# ---------------------------------------------------------------------------
def _ramp(t, stops):
    """t (array 0..1) を色の段 [(pos, rgb), ...] で補間。"""
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,), np.float32)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        m = (t >= p0) & (t <= p1)
        k = ((t - p0) / max(p1 - p0, 1e-6))[..., None]
        out[m] = (np.array(c0, np.float32) * (1 - k) + np.array(c1, np.float32) * k)[m]
    return out


def planet_surface(key, X, Y, Z, detail):
    """球面の点（惑星座標、Y=北）での地の色（float RGB、0..255）と発光（0..1）。detail: 0=極小, 1=大。"""
    lat = np.arcsin(np.clip(Y, -1, 1))
    lon = np.arctan2(X, Z)
    sh = X.shape
    emit = np.zeros(sh, np.float32)
    if key == "mercury":
        n = fbm3(X * 2.2, Y * 2.2, Z * 2.2, 11, 4)
        col = _ramp(n, [(0.0, (104, 104, 112)), (0.45, (160, 160, 168)), (0.7, (196, 194, 192)),
                        (1.0, (226, 224, 220))])
        rng = np.random.default_rng(7)
        nc = 9 if detail < 0.5 else 26
        for i in range(nc):
            th = rng.uniform(0, 2 * math.pi)
            ph = math.asin(rng.uniform(-0.9, 0.9))
            r = rng.uniform(0.16, 0.34) if i < 5 else rng.uniform(0.06, 0.16)
            if detail < 0.5:
                r *= 1.25
            cv = np.array([math.cos(ph) * math.sin(th), math.sin(ph), math.cos(ph) * math.cos(th)])
            d = np.sqrt((X - cv[0]) ** 2 + (Y - cv[1]) ** 2 + (Z - cv[2]) ** 2)
            floor = d < r * 0.78
            rim = (d >= r * 0.78) & (d < r)
            col[floor] *= 0.68
            # 縁は光の来る側（左上）を明るく
            side = ((X - cv[0]) * -0.6 + (Y - cv[1]) * 0.7)
            col[rim & (side > 0)] = np.minimum(255, col[rim & (side > 0)] * 1.28)
            col[rim & (side <= 0)] *= 0.82
        return col, emit
    if key == "venus":
        sw = lat * 5.0 + 1.1 * np.sin(lon * 2.0 + lat * 3.0) + 0.7 * fbm3(X * 3, Y * 3, Z * 3, 21, 3)
        t = 0.5 + 0.5 * np.sin(sw)
        col = _ramp(t, [(0.0, (196, 140, 58)), (0.35, (232, 186, 96)), (0.7, (250, 222, 150)),
                        (1.0, (255, 244, 206))])
        return col, emit
    if key == "earth":
        land = fbm3(X * 1.7 + 3.1, Y * 1.7, Z * 1.7, 31, 5) + 0.06 * np.cos(lat * 2)
        col = _ramp(np.clip((land - 0.36) * 4, 0, 1),
                    [(0.0, (20, 66, 170)), (0.6, (34, 104, 214)), (1.0, (56, 140, 232))])
        lm = land > 0.53
        g = _ramp(np.clip((land - 0.53) * 5, 0, 1), [(0.0, (52, 150, 72)), (0.6, (86, 168, 70)),
                                                     (1.0, (164, 146, 92))])
        col[lm] = g[lm]
        ice = np.abs(Y) > (0.86 if detail > 0.5 else 0.80)
        col[ice] = (236, 244, 250)
        if detail > 0.5:
            cl = fbm3(X * 3.0, Y * 5.0, Z * 3.0, 41, 4)
            cm = np.clip((cl - 0.55) * 4.5, 0, 1)[..., None]
            col = col * (1 - cm * 0.85) + np.array((246, 250, 255), np.float32) * cm * 0.85
        return col, emit
    if key == "mars":
        n = fbm3(X * 2.0, Y * 2.0, Z * 2.0, 51, 5)
        col = _ramp(n, [(0.0, (120, 44, 26)), (0.42, (176, 70, 38)), (0.62, (212, 98, 52)),
                        (1.0, (236, 150, 92))])
        cap = Y > (0.84 if detail > 0.5 else 0.72)
        col[cap] = (246, 238, 230)
        if detail > 0.5:
            vm = (np.abs(lat + 0.12 + 0.05 * np.sin(lon * 3)) < 0.035) & (np.abs(lon - 0.2) < 0.9)
            col[vm] *= 0.6
        return col, emit
    if key == "jupiter":
        w = lat + 0.05 * np.sin(lon * 6 + lat * 9) * detail + 0.04 * (fbm3(X * 4, Y * 8, Z * 4, 61, 3) - 0.5)
        bands = [(-1.6, (196, 160, 120)), (-0.9, (214, 182, 140)), (-0.55, (176, 112, 70)),
                 (-0.32, (236, 216, 180)), (-0.12, (196, 130, 82)), (0.08, (244, 228, 198)),
                 (0.30, (184, 120, 76)), (0.52, (230, 206, 168)), (0.8, (190, 150, 112)),
                 (1.6, (176, 150, 124))]
        t = (w + 1.6) / 3.2
        col = _ramp(t, [((p + 1.6) / 3.2, c) for p, c in bands])
        # 大赤斑
        dl, dn = (lat + 0.36) / 0.13, (lon + 0.35) / 0.30
        spot = dl * dl + dn * dn
        col[spot < 1.0] = np.array((206, 84, 52), np.float32)
        col[spot < 0.45] = np.array((226, 112, 72), np.float32)
        ring = (spot >= 1.0) & (spot < 1.6)
        col[ring] = col[ring] * 0.6 + np.array((250, 236, 214), np.float32) * 0.4
        return col, emit
    if key == "saturn":
        w = lat + 0.03 * np.sin(lon * 5)
        t = 0.5 + 0.5 * np.sin(w * 11)
        col = _ramp(t, [(0.0, (206, 172, 106)), (0.5, (230, 204, 142)), (1.0, (246, 228, 182))])
        polar = Y > 0.86
        col[polar] = col[polar] * 0.8 + np.array((150, 170, 160), np.float32) * 0.2
        return col, emit
    if key == "uranus":
        t = 0.5 + 0.5 * np.sin(lat * 7) * 0.4 + 0.3 * (fbm3(X * 2, Y * 6, Z * 2, 71, 2) - 0.5)
        col = _ramp(t, [(0.0, (120, 206, 214)), (0.5, (160, 230, 234)), (1.0, (206, 246, 246))])
        return col, emit
    if key == "neptune":
        w = lat + 0.06 * (fbm3(X * 3, Y * 7, Z * 3, 81, 3) - 0.5)
        t = 0.5 + 0.5 * np.sin(w * 8)
        col = _ramp(t, [(0.0, (28, 58, 170)), (0.5, (44, 90, 214)), (1.0, (76, 132, 240))])
        dl, dn = (lat + 0.32) / 0.15, (lon - 0.25) / 0.30
        spot = dl * dl + dn * dn
        col[spot < 1.0] = np.array((18, 30, 104), np.float32)
        dl2, dn2 = (lat + 0.12) / 0.05, (lon - 0.12) / 0.26
        cloud = dl2 * dl2 + dn2 * dn2 < 1.0
        col[cloud] = np.array((214, 236, 255), np.float32)
        if detail > 0.5:
            st = (np.abs(lat - 0.42 - 0.03 * np.sin(lon * 4)) < 0.025) & (np.sin(lon * 3 + 1) > 0.2)
            col[st] = np.array((190, 220, 255), np.float32)
        return col, emit
    if key == "sol":
        n = fbm3(X * 7, Y * 7, Z * 7, 91, 3) if detail > 0.5 else 0.5
        col = _ramp(np.asarray(n), [(0.0, (255, 170, 40)), (0.5, (255, 214, 92)), (1.0, (255, 246, 190))])
        if col.shape[:-1] != sh:
            col = np.broadcast_to(col, sh + (3,)).copy()
        emit[:] = 1.0
        return col, emit
    raise KeyError(key)


RING = {
    # (視線から見た環面の仰角, 画面内の傾き, 内径, 外径)
    "saturn": (24.0, -16.0, 1.30, 2.25),
    "uranus": (16.0, 82.0, 1.45, 1.80),
}


def _ring_colour(key, rr, ri, ro):
    t = (rr - ri) / (ro - ri)
    if key == "saturn":
        col = _ramp(t, [(0.0, (150, 130, 96)), (0.25, (214, 192, 140)), (0.58, (240, 224, 180)),
                        (0.62, (60, 50, 40)), (0.68, (60, 50, 40)), (0.72, (220, 200, 156)),
                        (1.0, (176, 156, 116))])
        a = np.where((t > 0.6) & (t < 0.7), 0.25, 0.95)
    else:
        col = _ramp(t, [(0.0, (170, 220, 230)), (0.5, (220, 250, 252)), (1.0, (150, 210, 220))])
        a = np.full(t.shape, 0.85)
    return col, a


def render_planet(key, size, radius=None, ss=4, crisp=False, detail=1.0, light=(-0.55, -0.62, 0.56),
                  atmo=True, spin=0.0):
    """size x size の RGBA（float 0..255、numpy）。惑星は中心に半径 radius（px）。
    crisp=True は 1:1 のドット絵（陰影を段に丸め、縁を硬く）。環・コロナは枠を越えて描く。"""
    if radius is None:
        radius = size * 0.30
    S = size * (1 if crisp else ss)
    R = radius * (1 if crisp else ss)
    ys, xs = np.mgrid[0:S, 0:S].astype(np.float32)
    x = (xs + 0.5 - S / 2) / R
    y = (ys + 0.5 - S / 2) / R
    rr2 = x * x + y * y
    on = rr2 <= 1.0
    z = np.sqrt(np.clip(1 - rr2, 0, 1))
    L = np.array(light, np.float32)
    L /= np.linalg.norm(L)
    # 惑星座標（Y 北）。軸を少し傾け、spin で経度を回す
    tilt = math.radians(-12 if key not in ("uranus",) else 0)
    X0, Y0, Z0 = x, -y, z
    Xa = X0 * math.cos(tilt) - Y0 * math.sin(tilt)
    Ya = X0 * math.sin(tilt) + Y0 * math.cos(tilt)
    cs, sn = math.cos(spin), math.sin(spin)
    Xp = Xa * cs + Z0 * sn
    Zp = -Xa * sn + Z0 * cs
    col, emit = planet_surface(key, Xp, Ya, Zp, detail)
    lam = x * L[0] + y * L[1] + z * L[2]
    if crisp:
        k = np.where(lam > 0.86, 1.20, np.where(lam > 0.42, 1.0, np.where(lam > 0.08, 0.74, 0.50)))
    else:
        k = 0.30 + 0.86 * np.clip(lam, 0, 1) + 0.25 * np.clip(lam, 0, 1) ** 24
        k = k * (0.86 + 0.14 * z)          # 縁を少し暗く
    if key == "sol":
        k = (0.62 + 0.38 * z ** 0.5) if not crisp else np.where(z > 0.55, 1.08, 0.86)
    rgb = col * np.asarray(k, np.float32)[..., None]
    img = np.zeros((S, S, 4), np.float32)
    img[on, :3] = np.clip(rgb[on], 0, 255)
    img[on, 3] = 255
    if atmo and not crisp and key in ("earth", "venus", "uranus", "neptune", "mars"):
        glow = {"earth": (120, 200, 255), "venus": (255, 236, 170), "uranus": (200, 255, 255),
                "neptune": (110, 170, 255), "mars": (255, 170, 120)}[key]
        r = np.sqrt(rr2)
        fres = np.clip((r - 0.70) / 0.30, 0, 1) ** 2 * on * np.clip(0.4 + lam, 0, 1)
        img[..., :3] = img[..., :3] * (1 - fres[..., None] * 0.6) + np.array(glow, np.float32) * fres[..., None] * 0.6
        halo = np.clip(1 - (r - 1.0) / 0.10, 0, 1) * (r > 1.0) * 0.55
        hm = (~on) & (halo > 0)
        img[hm, :3] = glow
        img[hm, 3] = halo[hm] * 255
    if key in RING:
        el, roll, ri, ro = RING[key]
        e, rl = math.radians(el), math.radians(roll)
        n = np.array([0.0, -math.cos(e), math.sin(e)])
        c2, s2 = math.cos(rl), math.sin(rl)
        n = np.array([n[0] * c2 - n[1] * s2, n[0] * s2 + n[1] * c2, n[2]])
        zr = -(n[0] * x + n[1] * y) / n[2]
        rr = np.sqrt(x * x + y * y + zr * zr)
        band = (rr >= ri) & (rr <= ro)
        front = band & ((~on) | (zr > z))
        rc, ra = _ring_colour(key, rr, ri, ro)
        # 環に落ちる惑星の影（光と反対側）
        lit = 0.55 + 0.45 * np.clip(-(x * L[0] + y * L[1]) / np.maximum(rr, 1e-3), -1, 1) * 0.5 + 0.25
        rc = rc * np.clip(lit, 0.6, 1.1)[..., None]
        if crisp:
            ra = np.where(ra > 0.5, 1.0, 0.0)
        a0 = img[..., 3] / 255.0
        a1 = ra * front
        oa = a1 + a0 * (1 - a1)
        img[..., :3] = np.where(oa[..., None] > 0,
                                (rc * a1[..., None] + img[..., :3] * (a0 * (1 - a1))[..., None])
                                / np.maximum(oa, 1e-6)[..., None], img[..., :3])
        img[..., 3] = oa * 255
        # 惑星の上に落ちる環の影（前の環の少し下）
        if not crisp:
            zr2 = -(n[0] * x + n[1] * (y - 0.10)) / n[2]
            rr_s = np.sqrt(x * x + (y - 0.10) ** 2 + zr2 * zr2)
            shadow = on & (rr_s >= ri) & (rr_s <= ro) & ~front
            img[shadow, :3] *= 0.72
    if key == "sol" and not crisp:
        r = np.sqrt(rr2)
        ang = np.arctan2(y, x)
        spikes = (0.5 + 0.5 * np.cos(ang * 12)) ** 6 * 0.7 + (0.5 + 0.5 * np.cos(ang * 7 + 0.6)) ** 10 * 0.5
        cor = np.clip(1 - (r - 1.0) / (0.32 + 0.55 * spikes), 0, 1) ** 1.6 * (r > 1.0)
        cm = cor > 0
        cc = _ramp(cor, [(0.0, (255, 120, 20)), (0.6, (255, 190, 60)), (1.0, (255, 246, 200))])
        img[cm, :3] = cc[cm]
        img[cm, 3] = np.clip(cor[cm] * 255 * 1.1, 0, 255)
    if not crisp and ss > 1:
        im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA")
        # 事前乗算で縮める（縁の色が黒ずまないように）
        arr = np.asarray(im, np.float32)
        pm = arr.copy()
        pm[..., :3] *= pm[..., 3:4] / 255.0
        pm = pm.reshape(size, ss, size, ss, 4).mean(axis=(1, 3))
        out = pm.copy()
        a = np.maximum(out[..., 3:4], 1e-6)
        out[..., :3] = np.where(out[..., 3:4] > 0, out[..., :3] * 255.0 / a, 0)
        return out
    return img


def over(dst, src, ox=0, oy=0):
    """numpy RGBA float の上に src を重ねる（はみ出しは切る）。"""
    h, w = src.shape[:2]
    H, W = dst.shape[:2]
    x0, y0 = max(0, ox), max(0, oy)
    x1, y1 = min(W, ox + w), min(H, oy + h)
    if x0 >= x1 or y0 >= y1:
        return dst
    s = src[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    d = dst[y0:y1, x0:x1]
    sa = s[..., 3:4] / 255.0
    da = d[..., 3:4] / 255.0
    oa = sa + da * (1 - sa)
    rgb = np.where(oa > 0, (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6), 0)
    d[..., :3] = rgb
    d[..., 3:4] = oa * 255
    return dst


# ===========================================================================
#  グリフのページ
# ===========================================================================
class Page:
    def __init__(self, page, cell):
        assert page not in FORBIDDEN_PAGES, hex(page)
        self.page, self.cell = page, cell
        self.img = np.zeros((cell * 16, cell * 16, 4), np.float32)
        self.meta = {}       # idx -> {"name", "span", "rows"}

    def cp(self, idx):
        return (self.page << 8) | idx

    def put(self, idx, px, name, span=None):
        """px: Px（cell x cell）。span = (x0, x1) 送り幅にする列の範囲（既定はマス全体）。
        両端の列に不透明な画素が無ければかすかな画素を置き、範囲の外は消す。"""
        assert idx not in self.meta, (hex(self.cp(idx)), name, self.meta.get(idx))
        c = self.cell
        a = px.a.copy()
        assert a.shape == (c, c, 4)
        if span == "tight":
            cols = np.nonzero(a[..., 3].max(axis=0) >= 0.5)[0]
            span = (int(cols.min()), int(cols.max()) + 1)
        x0, x1 = span or (0, c)
        a[:, :x0] = 0
        a[:, x1:] = 0
        a[a[..., 3] < 0.5] = 0
        mid = c // 2
        for col in (x0, x1 - 1):
            if a[:, col, 3].max() < FAINT_A - 2:
                a[mid, col, :3] = FAINT
                a[mid, col, 3] = FAINT_A
        r, cc = divmod(idx, 16)
        self.img[r * c:(r + 1) * c, cc * c:(cc + 1) * c] = a
        rows = np.nonzero(a[..., 3].max(axis=1) > FAINT_A + 4)[0]
        self.meta[idx] = {"name": name, "span": (x0, x1),
                          "rows": (int(rows.min()), int(rows.max())) if len(rows) else None}
        return chr(self.cp(idx))

    def cell_array(self, idx):
        c = self.cell
        r, cc = divmod(idx, 16)
        return self.img[r * c:(r + 1) * c, cc * c:(cc + 1) * c]

    def image(self):
        return Image.fromarray(np.clip(self.img + 0.5, 0, 255).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------------------
#  HUD のバー（星力・超新星・進捗・同調率）
#  バーのセルは幅の狭いグリフ。並べると 1 GUI px の隙間ができるので、塗りを平行四辺形にして
#  「暗い地＋斜めの区切り」に見えるようにしてある（隙間も区切りの一部に見える）。
# ---------------------------------------------------------------------------
SEG_W = 5          # 星力セルの送り幅（＋隙間 1 = 6 GUI px）
NOVA_W = 6         # 超新星セル
PROG_W = 4         # 進捗セル
SYNC_W = 3         # 同調率セル
CAP_W = 4


def _track(p, w, top=4, bot=11, rail=True):
    """バーの地: 上下の細いレールと暗い半透明の地。"""
    for x in range(w):
        if rail:
            p.put(x, top, METAL_D, 230)
            p.put(x, bot, (40, 48, 64), 230)
        for y in range(top + 1, bot):
            p.put(x, y, PLATE, 196)


def energy_seg(c, state):
    """星力セル。c = 惑星色。state: full / half / empty。"""
    p = Px(16)
    _track(p, SEG_W)
    lit = {5: lighten(c, 0.62), 6: lighten(c, 0.18), 7: c, 8: c, 9: shade(c, 0.86), 10: shade(c, 0.6)}
    dim = {y: mix(PLATE, c, 0.26 if y < 8 else 0.20) for y in range(5, 11)}
    dim[5] = mix(PLATE, c, 0.36)
    for y in range(5, 11):
        xs = range(1, 5) if y <= 7 else range(0, 4)
        for i, x in enumerate(xs):
            on = state == "full" or (state == "half" and i < 2)
            p.put(x, y, lit[y] if on else dim[y], 255)
    if state == "full":
        p.put(4, 5, WHITE, 230)            # 先端の照り
    return p


CAP_ROWS = {
    # 3..12 行。左は左上を、右は右下を面取り（セルの斜めと同じ向き）
    "L": [
        "..MH",
        ".MLR",
        "MLkp",
        "MLkp",
        "MLcp",
        "MLcp",
        "MDkp",
        "MDkp",
        "MDdR",
        "MMDd",
    ],
    "R": [
        "HMM.",
        "RLM.",
        "pkLM",
        "pkLM",
        "pcLM",
        "pcDM",
        "pkDM",
        "pkDM",
        "dDM.",
        "dM..",
    ],
}


def _cap(side, pal):
    p = Px(16)
    p.bitmap(0, 3, CAP_ROWS[side], pal)
    return p


def energy_cap(side, c=None):
    """星力バーの端（中立の金属。c を渡すとその色の LED を灯す）。"""
    led = c or (150, 210, 255)
    pal = {"M": (METAL, 255), "L": (METAL_L, 255), "D": (METAL_D, 255), "H": (WHITE, 230),
           "R": (METAL_D, 230), "k": (INK, 230), "p": (PLATE, 196), "c": (led, 255),
           "d": ((40, 48, 64), 230)}
    return _cap(side, pal)


def nova_seg(state):
    """超新星セル: 右向きの山形（＞）。full=金 / empty=暗い金 / flow=白熱（流れる光）。"""
    p = Px(16)
    _track(p, NOVA_W)
    offs = [0, 1, 2, 2, 1, 0]
    if state == "full":
        top, mid, low = GOLD_L, GOLD, GOLD_D
    elif state == "flow":
        top, mid, low = WHITE, (255, 250, 214), (255, 214, 120)
    else:
        top, mid, low = (96, 78, 40), (74, 58, 30), (56, 42, 24)
    for j, o in enumerate(offs):
        y = 5 + j
        for t in range(3):
            col = top if j <= 1 else (mid if j <= 3 else low)
            if t == 2 and state != "empty":
                col = lighten(col, 0.35)       # 先の縁を明るく
            p.put(o + t, y, col, 255)
    if state == "flow":
        p.put(5, 7, (255, 236, 160), 120)
        p.put(5, 8, (255, 236, 160), 120)
    return p


def nova_cap(side):
    pal = {"M": ((214, 170, 80), 255), "L": (GOLD_L, 255), "D": ((132, 86, 30), 255), "H": (WHITE, 230),
           "R": (METAL_D, 230), "k": (INK, 230), "p": (PLATE, 196), "c": ((255, 240, 160), 255),
           "d": ((40, 48, 64), 230)}
    return _cap(side, pal)


PROG_COL = (150, 236, 255)


def prog_seg(state):
    """変身の進捗（CORE SYNC）セル: 隙間 1 px で並ぶ細い LED。"""
    p = Px(16)
    for x in range(PROG_W):
        p.put(x, 5, METAL_D, 220)
        p.put(x, 10, (40, 48, 64), 220)
    for x in range(PROG_W - 1):
        for y in range(6, 10):
            if state == "full":
                col = WHITE if y == 6 else (PROG_COL if y < 9 else shade(PROG_COL, 0.7))
            elif state == "half":
                col = (lighten(PROG_COL, 0.4) if x == 0 else mix(PLATE, PROG_COL, 0.3)) if y < 9 else \
                    mix(PLATE, PROG_COL, 0.22)
            else:
                col = mix(PLATE, PROG_COL, 0.22 if y > 6 else 0.32)
            p.put(x, y, col, 255)
    for y in range(6, 10):
        p.put(PROG_W - 1, y, PLATE, 196)
    return p


def prog_cap(side):
    p = Px(16)
    rows = [
        ".MH",
        "MLR",
        "Mkp",
        "Mcp",
        "Mcp",
        "Mkp",
        "MDd",
        ".MD",
    ]
    pal = {"M": (METAL, 255), "L": (METAL_L, 255), "D": (METAL_D, 255), "H": (WHITE, 220),
           "R": (METAL_D, 220), "k": (INK, 230), "p": (PLATE, 196), "c": (PROG_COL, 255),
           "d": ((40, 48, 64), 220)}
    if side == "R":
        rows = [r[::-1] for r in rows]
    p.bitmap(0, 4, rows, pal)
    return p


SYNC_COL = (196, 150, 255)


def sync_seg(state):
    p = Px(16)
    for x in range(SYNC_W):
        for y in range(6, 10):
            p.put(x, y, PLATE, 190)
    for x in range(SYNC_W - 1):
        if state == "full":
            p.put(x, 7, lighten(SYNC_COL, 0.55), 255)
            p.put(x, 8, SYNC_COL, 255)
        else:
            p.put(x, 7, mix(PLATE, SYNC_COL, 0.34), 255)
            p.put(x, 8, mix(PLATE, SYNC_COL, 0.24), 255)
    return p


def sync_cap(side):
    p = Px(16)
    rows = ["MH", "Mk", "Mc", "Mc", "Mk", "MD"]
    pal = {"M": (METAL, 255), "H": (WHITE, 200), "D": (METAL_D, 255), "k": (INK, 220),
           "c": (SYNC_COL, 255)}
    if side == "R":
        rows = [r[::-1] for r in rows]
    p.bitmap(0, 5, rows, pal)
    return p


# ---------------------------------------------------------------------------
#  技アイコン（11x11 の面取りした枠＋7x7 の記号）
# ---------------------------------------------------------------------------
MOVE_SYMBOL = {
    # W = 芯（白）、C = 色、c = 暗い色
    "skill": [
        "c..C..c",
        ".c.C.c.",
        "..WWW..",
        "CCWCWCC",
        "..WWW..",
        ".c.C.c.",
        "c..C..c",
    ],
    "dash": [
        ".......",
        "CC.CC..",
        ".CW.CW.",
        "..CW.CW",
        ".CW.CW.",
        "CC.CC..",
        ".......",
    ],
    "air": [
        "c..C..c",
        "Cc.C.cC",
        ".C.C.C.",
        "CCCWCCC",
        ".CWWWC.",
        "..CWC..",
        "...C...",
    ],
    "ult": [
        "...C...",
        ".c.W.c.",
        "..CWC..",
        "CWWWWWC",
        "..CWC..",
        ".c.W.c.",
        "...C...",
    ],
}


MOVE_FRAME = {
    # 3..12 行に収まる 11x10 の枠。左上と右下を斜めに切る（必殺は八角形）
    "std": [(5, 3), (13, 3), (13, 10), (10, 13), (2, 13), (2, 6)],
    "ult": [(5, 3), (10, 3), (13, 6), (13, 10), (10, 13), (5, 13), (2, 10), (2, 6)],
}


def move_icon(c, kind, ready):
    p = Px(16)
    m = poly_mask(16, 16, MOVE_FRAME["ult" if kind == "ult" else "std"])
    out = edge(m)
    inner = edge(erode(m))
    body = erode(m)
    if ready:
        frame, frame_l = c, lighten(c, 0.6)
        plate = mix(PLATE, c, 0.12)
    else:
        g = mix(grey(c, 0.85), (110, 116, 130), 0.55)
        frame, frame_l = shade(g, 0.72), shade(g, 0.92)
        plate = mix(PLATE, (0, 0, 0), 0.25)
    p.fill_mask(body, plate, 218 if ready else 205)
    if ready:
        p.fill_mask(inner, c, 64)                  # 枠の内側のにじみ
    for y, x in zip(*np.nonzero(out)):
        lit = (x + y) < 15                          # 左上の辺は明るく
        p.put(x, y, frame_l if lit else frame, 255)
    if ready:
        for (x, y) in ((5, 3), (12, 3), (2, 12)) if kind != "ult" else ((5, 3), (10, 12)):
            p.put(x, y, WHITE, 255)
    sym = MOVE_SYMBOL[kind]
    if ready:
        pal = {"W": (WHITE, 255), "C": (lighten(c, 0.3), 255), "c": (c, 150)}
    else:
        gs = (150, 156, 170)
        pal = {"W": (mix(gs, c, 0.45), 255), "C": (shade(gs, 0.8), 255), "c": (shade(gs, 0.55), 120)}
    for j, row in enumerate(sym):
        for i, ch in enumerate(row):
            x, y = 4 + i, 4 + j
            if ch in ". " or out[y, x]:
                continue
            col, a = pal[ch]
            p.put(x, y, col, a)
    return p


# ---------------------------------------------------------------------------
#  小さな惑星紋章（12x10: 六角の左右の括弧＋直径 8 の惑星）
#  模様は手で描いた素材の地図（文字 = 素材）、陰影は球の向きからセル調に自動で付ける
# ---------------------------------------------------------------------------
_R = lambda *cs: [tuple(c) for c in cs]  # noqa: E731
SMALL_PLANET = {
    # rows: 12x10（セルの 2..13 列 × 3..12 行）。小文字/大文字 = 素材（ramps は陰影 4 段、flat は単色）
    "mercury": ([
        "............",
        "....aaaa....",
        "...aacraa...",
        "..acraaaca..",
        "..aaaaaaar..",
        "..aaacaaaa..",
        "..acaraaca..",
        "...raaaar...",
        "....aaaa....",
        "............",
    ], (6, 5), 4.05, {
        "a": _R((236, 236, 242), (194, 196, 206), (150, 152, 166), (100, 102, 120)),
        "c": _R((168, 168, 178), (128, 128, 140), (100, 100, 114), (72, 74, 92)),
        "r": _R((255, 255, 255), (240, 240, 246), (206, 206, 214), (140, 142, 158)),
    }, {}),
    "venus": ([
        "............",
        "....aabb....",
        "...abbbaa...",
        "..abbooobb..",
        "..baaaaabb..",
        "..bboobbaa..",
        "..aabbbooo..",
        "...bbaaab...",
        "....oobb....",
        "............",
    ], (6, 5), 4.05, {
        "a": _R((255, 250, 226), (252, 232, 172), (226, 192, 112), (168, 124, 58)),
        "b": _R((252, 228, 152), (238, 198, 106), (204, 152, 66), (148, 100, 40)),
        "o": _R((234, 182, 98), (208, 148, 62), (170, 110, 42), (118, 72, 26)),
    }, {}),
    "earth": ([
        "............",
        "....iiic....",
        "...ooGGooo..",
        "..oGGGooco..",
        "..ooGGoooo..",
        "..oooGoGGo..",
        "..ocooGGGo..",
        "...ooooGo...",
        "....oooo....",
        "............",
    ], (6, 5), 4.05, {
        "o": _R((96, 176, 255), (46, 120, 230), (30, 84, 190), (18, 48, 130)),
        "G": _R((150, 236, 120), (84, 190, 84), (52, 142, 62), (30, 96, 44)),
        "i": _R((255, 255, 255), (238, 246, 254), (204, 218, 236), (140, 160, 192)),
        "c": _R((255, 255, 255), (232, 242, 252), (196, 212, 232), (130, 150, 186)),
    }, {}),
    "mars": ([
        "............",
        "....iiii....",
        "...iiaaaa...",
        "..aaaaddaa..",
        "..aadddaaa..",
        "..aaaaaada..",
        "..addaaaaa..",
        "...aaaaad...",
        "....aaaa....",
        "............",
    ], (6, 5), 4.05, {
        "a": _R((252, 164, 112), (224, 102, 58), (178, 66, 36), (116, 38, 22)),
        "d": _R((206, 112, 76), (170, 72, 44), (130, 50, 30), (88, 30, 20)),
        "i": _R((255, 255, 255), (252, 242, 234), (222, 202, 192), (170, 140, 130)),
    }, {}),
    "jupiter": ([
        "............",
        "....cccc....",
        "...tttttt...",
        "..bbbbbbbb..",
        "..cccccccc..",
        "..oossoooo..",
        "..ccccccct..",
        "...bbbbbb...",
        "....tttt....",
        "............",
    ], (6, 5), 4.05, {
        "c": _R((255, 248, 230), (242, 226, 192), (210, 190, 152), (150, 130, 100)),
        "t": _R((242, 216, 172), (216, 182, 132), (180, 146, 100), (126, 98, 66)),
        "b": _R((210, 154, 108), (174, 112, 72), (138, 86, 54), (94, 56, 36)),
        "o": _R((246, 188, 134), (224, 150, 98), (186, 116, 72), (130, 78, 48)),
        "s": _R((255, 146, 112), (226, 84, 56), (184, 60, 40), (132, 40, 28)),
    }, {}),
    "saturn": ([
        "............",
        "............",
        "....aaaa..RR",
        "...bbbbbRRr.",
        "...aaaRRbb..",
        "..RRRRaaa...",
        ".RRrbbbb....",
        "RR..aaaa....",
        "............",
        "............",
    ], (6, 5), 3.2, {
        "a": _R((255, 242, 204), (242, 216, 152), (206, 176, 110), (150, 120, 70)),
        "b": _R((242, 216, 152), (216, 186, 120), (180, 148, 88), (126, 98, 58)),
    }, {"R": (238, 222, 172), "r": (168, 148, 104)}),
    "uranus": ([
        "......R.....",
        "....aRaa....",
        "...aaRaaa...",
        "..aaaRbaaa..",
        "..bbbRbbbb..",
        "..aaaRaaaa..",
        "..aaaRaaaa..",
        "...aaRaaa...",
        "....aRaa....",
        "......R.....",
    ], (6, 5), 4.05, {
        "a": _R((236, 255, 255), (176, 238, 242), (124, 204, 214), (72, 142, 162)),
        "b": _R((220, 250, 252), (160, 228, 236), (112, 192, 204), (64, 130, 150)),
    }, {"R": (226, 255, 255)}),
    "neptune": ([
        "............",
        "....bbbb....",
        "...bllbbb...",
        "..bbbbbbbb..",
        "..bbbbbwwb..",
        "..bdddbbbb..",
        "..bbddbbbb..",
        "...bbllbb...",
        "....bbbb....",
        "............",
    ], (6, 5), 4.05, {
        "b": _R((122, 172, 255), (62, 112, 238), (36, 74, 190), (20, 40, 120)),
        "l": _R((176, 214, 255), (112, 162, 250), (70, 112, 212), (40, 60, 140)),
        "w": _R((255, 255, 255), (224, 238, 255), (176, 204, 242), (120, 140, 190)),
        "d": _R((44, 64, 168), (28, 42, 124), (20, 30, 94), (12, 18, 62)),
    }, {}),
    "sol": ([
        ".....yy.....",
        "..o..yy..o..",
        "...oyyyyo...",
        "...yWWyyy...",
        ".yyWWWyyyyy.",
        ".yyyWyyyyoy.",
        "...yyyyoo...",
        "...oyyooo...",
        "..o..yy..o..",
        ".....yy.....",
    ], (6, 5), 3.2, {}, {"W": (255, 254, 236), "y": (255, 214, 84), "o": (255, 148, 40)}),
}
LIGHT = np.array([-0.55, -0.62, 0.56]) / np.linalg.norm([-0.55, -0.62, 0.56])

# 括弧の画素（スプライト座標 12x10）。左右対称
BRACKET = [(3, 0), (2, 0), (1, 1), (1, 2), (0, 3), (0, 4), (0, 5), (0, 6), (1, 7), (1, 8), (2, 9), (3, 9)]


def emblem_small(key):
    c = HUD_COL[key]
    p = Px(16)
    # 暗い六角の地
    hexpts = [(5.1, 3), (10.9, 3), (14, 8), (10.9, 13), (5.1, 13), (2, 8)]
    p.fill_mask(poly_mask(16, 16, hexpts), PLATE, 200)
    rows, (cx, cy), rad, ramps, flat = SMALL_PLANET[key]
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            x, y = 2 + i, 3 + j
            if ch in flat:
                p.put(x, y, flat[ch], 255)
                continue
            dx = (i + 0.5 - cx) / rad
            dy = (j + 0.5 - cy) / rad
            nz = math.sqrt(max(0.0, 1 - dx * dx - dy * dy))
            lam = dx * LIGHT[0] + dy * LIGHT[1] + nz * LIGHT[2]
            tone = 0 if lam > 0.90 else 1 if lam > 0.52 else 2 if lam > 0.12 else 3
            p.put(x, y, ramps[ch][tone], 255)
    for (i, j) in BRACKET:
        for (ii, side) in ((i, "L"), (11 - i, "R")):
            x, y = 2 + ii, 3 + j
            if side == "L":
                col = lighten(c, 0.55) if j <= 5 else c
            else:
                col = c if j <= 4 else shade(c, 0.78)
            if (ii in (3, 8)):
                col = mix(col, PLATE, 0.35)          # 角の短い棒は少し暗く
            p.put(x, y, col, 255)
    return p


# ---------------------------------------------------------------------------
#  状態アイコン（9 px 幅、4〜11 行）
# ---------------------------------------------------------------------------
ICON_W = 9
ICONS = {
    "energy": ([
        ".....kYYk",
        "....kYWk.",
        "...kYWk..",
        "..kYYYYYk",
        ".kkkYWYk.",
        "...kYYk..",
        "..kYYk...",
        "..kYk....",
    ], {"Y": (255, 226, 70), "W": (255, 255, 220), "k": (INK, 150)}),
    "nova": ([
        "....Y....",
        "....Y....",
        "...YWY...",
        ".YYWWWYY.",
        "...YWY...",
        "....Y....",
        "....Y....",
    ], {"Y": (255, 206, 72), "W": (255, 252, 226)}),
    "revert": ([
        "....W....",
        "..R.W.R..",
        ".R..W..R.",
        "R...W...R",
        "R.......R",
        "R.......R",
        ".R.....R.",
        "..RRRRR..",
    ], {"W": (255, 255, 255), "R": (255, 96, 96)}),
    "overheat": ([
        "....f....",
        "...fRf...",
        "...fRf.f.",
        "..fRYRff.",
        ".fRYYYRf.",
        ".fRYWYRf.",
        ".fRYWYRf.",
        "..fRRRf..",
    ], {"f": (230, 50, 30), "R": (255, 120, 40), "Y": (255, 214, 90), "W": (255, 252, 220)}),
    "barrier": ([
        "...CCC...",
        ".CCWLLCC.",
        "CWLpppLLC",
        "CLppppaLC",
        "CLpppaaLC",
        "CLLpaaLLC",
        ".CCLLLCC.",
        "...CCC...",
    ], {"C": (96, 214, 255), "L": (190, 240, 255), "p": (24, 64, 116), "a": (60, 130, 200),
        "W": (255, 255, 255)}),
    "sync": ([
        "P...V...P",
        "rP.V.V.Pr",
        "r.X...X.r",
        "r.X...X.r",
        "rV.P.P.Vr",
        "V...P...V",
        ".........",
    ], {"V": (196, 150, 255), "P": (110, 226, 255), "r": ((220, 220, 255), 110), "X": (255, 255, 255)}),
    "check": ([
        "........G",
        ".......GG",
        "......GG.",
        "G....GG..",
        "GG..GG...",
        ".GGGG....",
        "..GG.....",
        ".........",
    ], {"G": (100, 255, 140)}),
    "lock": ([
        "...MMM...",
        "..M...M..",
        "..M...M..",
        ".LLLLLLL.",
        ".LYYkYYL.",
        ".LYYkYYL.",
        ".LYYYYYL.",
        ".DDDDDDD.",
    ], {"M": (176, 186, 204), "L": (255, 226, 120), "Y": (232, 176, 60), "k": (60, 40, 20),
        "D": (150, 96, 30)}),
    "warn": ([
        "....Y....",
        "...YkY...",
        "...YkY...",
        "..YYkYY..",
        "..YYkYY..",
        ".YYYYYYY.",
        ".YYYkYYY.",
        "YYYYYYYYY",
    ], {"Y": (255, 214, 60), "k": (40, 24, 8)}),
}


def status_icon(name):
    p = Px(16)
    rows, pal = ICONS[name]
    pal = {k: (v if isinstance(v[0], tuple) else (v, 255)) for k, v in pal.items()}
    p.bitmap(0, 4, rows, pal)
    return p


def pip(on):
    p = Px(16)
    rows = ["..W..", ".WCW.", "WCCCW", ".WCD.", "..D.."] if on else \
        ["..g..", ".g.g.", "g...g", ".g.g.", "..g.."]
    pal = {"W": (GOLD_L, 255), "C": (GOLD, 255), "D": (GOLD_D, 255), "g": ((120, 128, 146), 255)}
    p.bitmap(0, 5, rows, pal)
    return p


def sep_glyph():
    p = Px(16)
    for y in range(3, 13):
        x = 2 - (y - 3) // 4
        p.put(x, y, METAL, 200 if 4 <= y <= 11 else 120)
    return p


def arrow_glyph():
    p = Px(16)
    p.bitmap(0, 5, ["W...", "CW..", "CCW.", "CCW.", "CW..", "W..."][:6],
             {"W": (WHITE, 255), "C": ((150, 236, 255), 255)})
    return p


# ===========================================================================
#  HUD ページ（glyph_EA）の割り当て
#    行 0      共通のバー部品（星力の端・超新星・進捗・同調率）
#    行 1..9   惑星（order 1..9）: 列 0 紋章 / 1..3 星力 満・半・空 / 4..7 技 使える / 8..B 技 待ち
#    行 A      星力が少ない時の赤いバー
#    行 B      状態アイコン
# ===========================================================================
def build_hud_page():
    pg = Page(PAGE_HUD, 16)
    G = {"emblem": {}, "energy": {}, "move": {}}
    capL = pg.put(0x00, energy_cap("L"), "energy.<key>.capL（全惑星共通）", (0, CAP_W))
    capR = pg.put(0x01, energy_cap("R"), "energy.<key>.capR（全惑星共通）", (0, CAP_W))
    G["nova"] = {
        "full": pg.put(0x02, nova_seg("full"), "nova.full", (0, NOVA_W)),
        "empty": pg.put(0x03, nova_seg("empty"), "nova.empty", (0, NOVA_W)),
        "flow": pg.put(0x04, nova_seg("flow"), "nova.flow", (0, NOVA_W)),
        "capL": pg.put(0x05, nova_cap("L"), "nova.capL", (0, CAP_W)),
        "capR": pg.put(0x06, nova_cap("R"), "nova.capR", (0, CAP_W)),
    }
    G["progress"] = {
        "full": pg.put(0x07, prog_seg("full"), "progress.full = sync.full", (0, PROG_W)),
        "empty": pg.put(0x08, prog_seg("empty"), "progress.empty = sync.empty", (0, PROG_W)),
        "half": pg.put(0x09, prog_seg("half"), "progress.half = sync.half", (0, PROG_W)),
        "capL": pg.put(0x0A, prog_cap("L"), "progress.capL = sync.capL", (0, 3)),
        "capR": pg.put(0x0B, prog_cap("R"), "progress.capR = sync.capR", (0, 3)),
    }
    # G.sync = 変身・解除の進み具合（DESIGN §4.8 の sync。G.progress と同じグリフ）
    G["sync"] = dict(G["progress"])
    # G.xp = 同調率の XP（細い紫のバー）
    G["xp"] = {
        "full": pg.put(0x0C, sync_seg("full"), "xp.full", (0, SYNC_W)),
        "empty": pg.put(0x0D, sync_seg("empty"), "xp.empty", (0, SYNC_W)),
        "capL": pg.put(0x0E, sync_cap("L"), "xp.capL", (0, 2)),
        "capR": pg.put(0x0F, sync_cap("R"), "xp.capR", (0, 2)),
    }
    for key in KEYS:
        row = D.PLANETS[key]["order"] * 16
        c = HUD_COL[key]
        G["emblem"][key] = pg.put(row + 0x0, emblem_small(key), f"emblem.{key}")
        G["energy"][key] = {
            "full": pg.put(row + 0x1, energy_seg(c, "full"), f"energy.{key}.full", (0, SEG_W)),
            "half": pg.put(row + 0x2, energy_seg(c, "half"), f"energy.{key}.half", (0, SEG_W)),
            "empty": pg.put(row + 0x3, energy_seg(c, "empty"), f"energy.{key}.empty", (0, SEG_W)),
            "capL": capL, "capR": capR,
        }
        G["move"][key] = {}
        for i, kind in enumerate(KINDS):
            G["move"][key][kind] = {
                "ready": pg.put(row + 0x4 + i, move_icon(c, kind, True), f"move.{key}.{kind}.ready"),
                "wait": pg.put(row + 0x8 + i, move_icon(c, kind, False), f"move.{key}.{kind}.wait"),
            }
    G["energyLow"] = {
        "full": pg.put(0xA0, energy_seg(RED, "full"), "energyLow.full", (0, SEG_W)),
        "half": pg.put(0xA1, energy_seg(RED, "half"), "energyLow.half", (0, SEG_W)),
        "empty": pg.put(0xA2, energy_seg(RED, "empty"), "energyLow.empty", (0, SEG_W)),
        "capL": pg.put(0xA3, energy_cap("L", RED), "energyLow.capL", (0, CAP_W)),
        "capR": pg.put(0xA4, energy_cap("R", RED), "energyLow.capR", (0, CAP_W)),
    }
    G["energy"]["low"] = dict(G["energyLow"])          # hud.js は G.energy.low（warn）を見る
    G["icon"] = {}
    for i, name in enumerate(["energy", "nova", "revert", "overheat", "barrier", "sync", "check", "lock",
                              "warn"]):
        G["icon"][name] = pg.put(0xB0 + i, status_icon(name), f"icon.{name}", (0, ICON_W))
    G["icon"]["pipOn"] = pg.put(0xB9, pip(True), "icon.pipOn", (0, 5))
    G["icon"]["pipOff"] = pg.put(0xBA, pip(False), "icon.pipOff", (0, 5))
    G["icon"]["sep"] = pg.put(0xBB, sep_glyph(), "icon.sep", (0, 3))
    G["icon"]["arrow"] = pg.put(0xBC, arrow_glyph(), "icon.arrow", (0, 4))
    return pg, G


# ===========================================================================
#  なめらかな絵の画布（ss 倍で描いて事前乗算で縮める）
# ===========================================================================
class Canvas:
    def __init__(self, w, h=None, ss=4):
        self.w, self.h, self.ss = w, (h if h is not None else w), ss
        self.W, self.H = self.w * ss, self.h * ss
        self.a = np.zeros((self.H, self.W, 4), np.float32)

    # --- 形（0..1 の float マスク。座標は出力の px） ---
    def _m(self):
        return Image.new("L", (self.W, self.H), 0)

    def poly(self, pts):
        im = self._m()
        ImageDraw.Draw(im).polygon([(x * self.ss, y * self.ss) for x, y in pts], fill=255)
        return np.asarray(im, np.float32) / 255.0

    def ellipse(self, cx, cy, rx, ry=None):
        ry = rx if ry is None else ry
        im = self._m()
        s = self.ss
        ImageDraw.Draw(im).ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s], fill=255)
        return np.asarray(im, np.float32) / 255.0

    def ring(self, cx, cy, r0, r1):
        return np.clip(self.ellipse(cx, cy, r1) - self.ellipse(cx, cy, r0), 0, 1)

    def line(self, pts, width):
        im = self._m()
        s = self.ss
        ImageDraw.Draw(im).line([(x * s, y * s) for x, y in pts], fill=255, width=max(1, int(round(width * s))),
                                joint="curve")
        return np.asarray(im, np.float32) / 255.0

    def arc(self, cx, cy, r, a0, a1, width):
        im = self._m()
        s = self.ss
        ImageDraw.Draw(im).arc([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], a0, a1, fill=255,
                               width=max(1, int(round(width * s))))
        return np.asarray(im, np.float32) / 255.0

    def coords(self):
        ys, xs = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        return (xs + 0.5) / self.ss, (ys + 0.5) / self.ss

    # --- 塗り ---
    def fill(self, m, col, alpha=1.0):
        """col: RGB か (H, W, 3) の配列。"""
        a = np.clip(m * alpha, 0, 1)[..., None]
        if a.max() <= 0:
            return
        col = np.asarray(col, np.float32)
        da = self.a[..., 3:4] / 255.0
        oa = a + da * (1 - a)
        self.a[..., :3] = np.where(oa > 0, (col * a + self.a[..., :3] * da * (1 - a)) / np.maximum(oa, 1e-6),
                                   self.a[..., :3])
        self.a[..., 3:4] = oa * 255

    def grad(self, p0, p1, c0, c1, stops=None):
        """p0→p1 の線形グラデーションの色配列。"""
        X, Y = self.coords()
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        t = ((X - p0[0]) * dx + (Y - p0[1]) * dy) / max(dx * dx + dy * dy, 1e-6)
        if stops is None:
            stops = [(0.0, c0), (1.0, c1)]
        return _ramp(t, stops)

    def radial(self, cx, cy, r, stops):
        X, Y = self.coords()
        t = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / r
        return _ramp(t, stops)

    def glow(self, m, col, radius, strength=1.0):
        """マスクをぼかした発光（下に敷く）。"""
        im = Image.fromarray(np.clip(m * 255, 0, 255).astype(np.uint8), "L")
        b = np.asarray(im.filter(ImageFilter.GaussianBlur(radius * self.ss)), np.float32) / 255.0
        self.fill(np.clip(b * strength, 0, 1), col)

    def paste(self, arr, ox, oy):
        """出力解像度の RGBA 配列を ss 倍に拡大して重ねる。"""
        im = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8), "RGBA")
        im = im.resize((im.width * self.ss, im.height * self.ss), Image.LANCZOS)
        over(self.a, np.asarray(im, np.float32), int(ox * self.ss), int(oy * self.ss))

    def result_fit(self, n, cell=None, off=None):
        """高解像度の絵を n x n に縮め、cell x cell の中央（off）に置く（事前乗算で縮める）。"""
        cell = cell or self.w
        pm = self.a.copy()
        pm[..., :3] *= pm[..., 3:4] / 255.0
        chans = [Image.fromarray(pm[..., i], "F").resize((n, n), Image.BOX) for i in range(4)]
        sm = np.stack([np.asarray(c, np.float32) for c in chans], axis=-1)
        a = sm[..., 3:4]
        sm[..., :3] = np.where(a > 0, sm[..., :3] * 255.0 / np.maximum(a, 1e-6), 0)
        out = np.zeros((cell, cell, 4), np.float32)
        o = (cell - n) // 2 if off is None else off
        out[o:o + n, o:o + n] = np.clip(sm, 0, 255)
        return out

    def result(self):
        pm = self.a.copy()
        pm[..., :3] *= pm[..., 3:4] / 255.0
        pm = pm.reshape(self.h, self.ss, self.w, self.ss, 4).mean(axis=(1, 3))
        a = pm[..., 3:4]
        pm[..., :3] = np.where(a > 0, pm[..., :3] * 255.0 / np.maximum(a, 1e-6), 0)
        return pm


def outlined(arr, col=(14, 12, 20), thr=96, grow=1):
    """アルファを 2 値にして暗い縁取りを付ける（アイテムアイコンと同じ流儀）。"""
    im = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8), "RGBA")
    a = im.split()[3].point(lambda v: 255 if v > thr else 0)
    im.putalpha(a)
    ring = Image.new("RGBA", im.size, tuple(col) + (255,))
    ring.putalpha(a.filter(ImageFilter.MaxFilter(1 + 2 * grow)))
    ring.alpha_composite(im)
    return np.asarray(ring, np.float32)


def soft_outlined(arr, col=INK, alpha=200, grow=1):
    """縁取り（アルファは保ったまま、外側に暗い縁を足す）。"""
    im = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8), "RGBA")
    a = im.split()[3]
    hard = a.point(lambda v: 255 if v > 60 else 0).filter(ImageFilter.MaxFilter(1 + 2 * grow))
    ring = Image.new("RGBA", im.size, tuple(col) + (0,))
    ring.putalpha(hard.point(lambda v: alpha if v else 0))
    ring.alpha_composite(im)
    return np.asarray(ring, np.float32)


# ===========================================================================
#  大きな絵のページ（glyph_EB、32 px セル）
#    行 0  大きな惑星紋章（order 1..9 → 列 0..8）
#    行 1  カットインの飾り（翼・区切り線）
#    行 2  大きな状態アイコン
# ===========================================================================
def hex_pts(cx, cy, rx, ry, flat=True):
    if flat:
        return [(cx - rx, cy), (cx - rx / 2, cy - ry), (cx + rx / 2, cy - ry), (cx + rx, cy),
                (cx + rx / 2, cy + ry), (cx - rx / 2, cy + ry)]
    return [(cx, cy - ry), (cx + rx, cy - ry / 2), (cx + rx, cy + ry / 2), (cx, cy + ry),
            (cx - rx, cy + ry / 2), (cx - rx, cy - ry / 2)]


def emblem_frame(cv, key, cx, cy, R, detail=1.0):
    """六角のメカ枠（金属の外枠・惑星色の内側の発光線・暗い地・四隅の留め具）。R = 外枠の縦の半径。"""
    c = HUD_COL[key]
    rx = R * 1.16
    outer = cv.poly(hex_pts(cx, cy, rx, R))
    inner = cv.poly(hex_pts(cx, cy, rx - R * 0.22, R * 0.81))
    glow_in = cv.poly(hex_pts(cx, cy, rx - R * 0.30, R * 0.74))
    cv.fill(outer, (0, 0, 0), 0.0)
    metal = cv.grad((cx - rx, cy - R), (cx + rx, cy + R), None, None,
                    [(0.0, (236, 242, 250)), (0.35, (164, 178, 198)), (0.55, (96, 108, 130)),
                     (0.75, (150, 164, 186)), (1.0, (70, 80, 100))])
    cv.fill(np.clip(outer - inner, 0, 1), metal)
    cv.fill(np.clip(inner - glow_in, 0, 1), c)
    plate = cv.radial(cx, cy - R * 0.2, R, [(0.0, mix(PLATE, c, 0.22)), (1.0, (6, 10, 20))])
    cv.fill(glow_in, plate, 0.94)
    # 枠の溝（パネルライン）と留め具
    for ang in (30, 150, 210, 330):
        a = math.radians(ang)
        x, y = cx + math.cos(a) * rx * 0.86, cy + math.sin(a) * R * 0.98
        cv.fill(cv.line([(x - math.cos(a) * R * 0.12, y - math.sin(a) * R * 0.12),
                         (x + math.cos(a) * R * 0.05, y + math.sin(a) * R * 0.05)], max(0.6, R * 0.05)),
                (40, 46, 60))
    for (x, y) in ((cx - rx / 2, cy - R), (cx + rx / 2, cy + R)):
        cv.fill(cv.ellipse(x, y, R * 0.12), lighten(c, 0.5))


def emblem_big(key):
    cv = Canvas(32, ss=8)
    emblem_frame(cv, key, 16, 16, 12.4)
    rad = {"saturn": 5.6, "sol": 5.4, "uranus": 7.0}.get(key, 7.6)
    pl = render_planet(key, 32, rad, ss=6, detail=0.7)
    cv.paste(pl, 0, 0)
    # 4..27 行に収める（縁取り込み）
    return soft_outlined(cv.result_fit(22, 32, 5), INK, 190)


def wing(side):
    """カットインの翼（左向き。付け根が右端）。side="R" は左右反転。尖った 3 枚の刃と付け根の金具。"""
    cv = Canvas(32, ss=8)
    blades = [
        # 付け根の上, 付け根の下, 先端, 下の縁の折れ点
        ((30, 11.2), (30, 15.0), (1.5, 6.0), (7.5, 11.0)),
        ((30, 15.6), (30, 18.8), (4.5, 15.4), (9.5, 18.0)),
        ((30, 19.4), (30, 22.2), (10.0, 25.2), (14.5, 23.6)),
    ]
    for a, b, tip, knee in blades:
        m = cv.poly([a, tip, knee, b])
        metal = cv.grad((a[0], a[1] - 1), (b[0], b[1] + 2), None, None,
                        [(0.0, (252, 254, 255)), (0.35, (186, 200, 222)), (0.7, (110, 124, 152)),
                         (1.0, (70, 80, 104))])
        cv.fill(m, metal)
        cv.fill(cv.line([a, tip], 0.8), (150, 236, 255))                    # 前縁の発光
        cv.fill(cv.line([(a[0] - 1.5, a[1] + 0.35), ((a[0] + tip[0]) / 2, (a[1] + tip[1]) / 2 + 0.3)], 0.35),
                WHITE, 0.9)
        cv.fill(cv.line([knee, ((knee[0] + b[0]) / 2, (knee[1] + b[1]) / 2 - 0.2)], 0.35), (50, 58, 80), 0.9)
    hub = cv.poly([(25, 9.8), (32, 9.8), (32, 23.2), (25, 23.2), (23, 19.6), (23, 13.4)])
    cv.fill(hub, cv.grad((23, 9.8), (32, 23.2), (220, 230, 244), (70, 82, 108)))
    cv.fill(cv.line([(25, 10.4), (31.5, 10.4)], 0.5), WHITE, 0.8)
    cv.fill(cv.poly([(26.6, 13.6), (30.2, 13.6), (30.2, 19.4), (26.6, 19.4)]), (16, 22, 36))
    cv.fill(cv.poly([(27.2, 14.2), (29.6, 14.2), (29.6, 18.8), (27.2, 18.8)]), (150, 236, 255))
    cv.fill(cv.poly([(27.6, 14.6), (28.6, 14.6), (28.6, 16.2), (27.6, 16.2)]), WHITE)
    a = soft_outlined(cv.result(), INK, 210)
    if side == "R":
        a = a[:, ::-1].copy()
    return a


def divider(kind):
    """区切り線。kind: mid（両端が消える・中央にひし形）/ L（右へ伸びて左端が消える）/ R。"""
    cv = Canvas(32, ss=8)
    X, Y = cv.coords()
    if kind == "mid":
        fade = np.clip(1 - np.abs(X - 16) / 16, 0, 1) ** 0.6
    elif kind == "L":
        fade = np.clip(X / 32, 0, 1) ** 0.8
    else:
        fade = np.clip(1 - X / 32, 0, 1) ** 0.8
    line = cv.poly([(0, 15.4), (32, 15.4), (32, 16.6), (0, 16.6)]) * fade
    cv.fill(cv.poly([(0, 14.6), (32, 14.6), (32, 17.4), (0, 17.4)]) * fade, (60, 170, 255), 0.35)
    cv.fill(line, (210, 246, 255))
    if kind == "mid":
        d = cv.poly([(16, 11.5), (20.5, 16), (16, 20.5), (11.5, 16)])
        cv.fill(cv.poly([(16, 10.0), (22, 16), (16, 22), (10, 16)]), INK, 0.8)
        cv.fill(d, cv.grad((13, 12), (19, 20), (255, 255, 255), (120, 210, 255)))
        cv.fill(cv.poly([(16, 13.6), (18.4, 16), (16, 18.4), (13.6, 16)]), (40, 90, 160))
    else:
        tip = 30.5 if kind == "L" else 1.5
        cv.fill(cv.poly([(tip, 13.4), (tip + 2.6, 16), (tip, 18.6), (tip - 2.6, 16)]), (210, 246, 255))
    return cv.result()


def big_icon(name):
    cv = Canvas(32, ss=8)
    if name == "energy":
        pts = [(19, 5), (8, 18), (15, 18), (11, 27), (24, 13), (17, 13), (21, 5)]
        cv.glow(cv.poly(pts), (255, 220, 80), 1.2, 0.8)
        cv.fill(cv.poly(pts), cv.grad((10, 6), (22, 26), (255, 252, 210), (255, 176, 30)))
        cv.fill(cv.line([(18.6, 6.4), (11, 16.4)], 0.8), WHITE)
    elif name == "nova":
        pts = []
        for i in range(8):
            a = math.radians(i * 45 - 90)
            r = 11.5 if i % 2 == 0 else 3.4
            pts.append((16 + math.cos(a) * r, 16 + math.sin(a) * r))
        cv.glow(cv.poly(pts), (255, 210, 90), 1.6, 0.9)
        cv.fill(cv.poly(pts), cv.radial(16, 16, 11, [(0.0, (255, 255, 240)), (0.5, (255, 226, 120)),
                                                     (1.0, (255, 160, 30))]))
        cv.fill(cv.ring(16, 16, 7.2, 8.0), (255, 236, 160), 0.8)
    elif name == "revert":
        cv.fill(cv.arc(16, 16.5, 8.5, -60, 240, 2.6), (255, 110, 110))
        cv.fill(cv.line([(16, 5.5), (16, 15)], 2.6), WHITE)
    elif name == "overheat":
        flame = [(16, 4), (21, 11), (24, 17), (23, 23), (19, 27), (13, 27), (9, 23), (8, 17), (11, 12), (13, 15)]
        cv.glow(cv.poly(flame), (255, 90, 30), 1.4, 0.8)
        cv.fill(cv.poly(flame), cv.grad((16, 4), (16, 27), (255, 210, 90), (230, 40, 20)))
        inner = [(16, 13), (19.5, 18), (19.5, 23), (16, 26), (12.5, 23), (12.5, 19)]
        cv.fill(cv.poly(inner), cv.grad((16, 13), (16, 26), (255, 255, 230), (255, 190, 70)))
    elif name == "barrier":
        h = cv.poly(hex_pts(16, 16, 12, 11, flat=False))
        hi = cv.poly(hex_pts(16, 16, 9.8, 8.8, flat=False))
        cv.glow(h, (90, 210, 255), 1.4, 0.7)
        cv.fill(h, (110, 222, 255))
        cv.fill(hi, cv.grad((8, 6), (24, 26), (40, 110, 180), (12, 34, 80)))
        for (x, y) in ((16, 12), (12.6, 18), (19.4, 18)):
            cv.fill(cv.poly(hex_pts(x, y, 3.0, 2.8, flat=False)), (140, 230, 255), 0.55)
        cv.fill(cv.line([(9.5, 10.5), (13, 8.4)], 1.0), WHITE)
    elif name == "sync":
        for k, col in ((0, (196, 150, 255)), (math.pi, (110, 226, 255))):
            pts = [(6 + t * 20 / 40, 16 + 7 * math.cos(t / 40 * 2 * math.pi + k)) for t in range(41)]
            cv.fill(cv.line(pts, 2.0), col)
        for t in (0, 10, 20, 30, 40):
            x = 6 + t / 2
            cv.fill(cv.line([(x, 16 - 6), (x, 16 + 6)], 0.8), (230, 230, 255), 0.5)
    elif name == "check":
        pts = [(6, 16), (10, 12.5), (14, 17), (24, 6.5), (27.5, 10), (14, 24)]
        cv.glow(cv.poly(pts), (90, 255, 140), 1.2, 0.7)
        cv.fill(cv.poly(pts), cv.grad((6, 6), (26, 24), (200, 255, 210), (40, 200, 90)))
    elif name == "lock":
        cv.fill(cv.arc(16, 13, 6.5, 180, 360, 2.6), (190, 200, 218))
        cv.fill(cv.line([(9.5, 13), (9.5, 16)], 2.6), (190, 200, 218))
        cv.fill(cv.line([(22.5, 13), (22.5, 16)], 2.6), (190, 200, 218))
        body = cv.poly([(7, 15), (25, 15), (25, 27), (7, 27)])
        cv.fill(body, cv.grad((7, 15), (25, 27), (255, 228, 130), (180, 110, 30)))
        cv.fill(cv.ellipse(16, 20, 1.8), (60, 36, 10))
        cv.fill(cv.line([(16, 20), (16, 24)], 1.4), (60, 36, 10))
    elif name == "warn":
        tri = [(16, 4.5), (28, 26), (4, 26)]
        cv.glow(cv.poly(tri), (255, 200, 40), 1.2, 0.7)
        cv.fill(cv.poly(tri), cv.grad((16, 4), (16, 26), (255, 236, 120), (255, 170, 20)))
        cv.fill(cv.line([(16, 11), (16, 19)], 2.6), (40, 24, 8))
        cv.fill(cv.ellipse(16, 22.6, 1.5), (40, 24, 8))
    return soft_outlined(cv.result_fit(22, 32, 5), INK, 200)


def _px_from(arr):
    p = Px(arr.shape[1], arr.shape[0])
    p.a = arr.astype(np.float32)
    return p


def build_art_page():
    pg = Page(PAGE_ART, 32)
    G = {"emblemBig": {}, "banner": {}, "iconBig": {}}
    for key in KEYS:
        G["emblemBig"][key] = pg.put(D.PLANETS[key]["order"] - 1, _px_from(emblem_big(key)), f"emblemBig.{key}",
                                     "tight")
    G["banner"]["wingL"] = pg.put(0x10, _px_from(wing("L")), "banner.wingL", "tight")
    G["banner"]["wingR"] = pg.put(0x11, _px_from(wing("R")), "banner.wingR", "tight")
    G["banner"]["divider"] = pg.put(0x12, _px_from(divider("mid")), "banner.divider", "tight")
    G["banner"]["lineL"] = pg.put(0x13, _px_from(divider("L")), "banner.lineL", "tight")
    G["banner"]["lineR"] = pg.put(0x14, _px_from(divider("R")), "banner.lineR", "tight")
    for i, name in enumerate(["energy", "nova", "revert", "overheat", "barrier", "sync", "check", "lock",
                              "warn"]):
        G["iconBig"][name] = pg.put(0x20 + i, _px_from(big_icon(name)), f"iconBig.{name}", "tight")
    return pg, G


# ===========================================================================
#  プレビュー: グリフのページを 4 倍にして格子と番号を付ける
# ===========================================================================
def page_preview(pg, path, scale=4):
    c = pg.cell
    s = scale if c == 16 else max(1, scale // 2)
    cw = c * s
    lab = 12
    W = 16 * (cw + 2) + 2
    H = 16 * (cw + 2 + lab) + 2
    sheet = Image.new("RGBA", (W, H), (20, 22, 30, 255))
    dr = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT_SYM, 10)
    # 市松の背景（透明を見分ける）
    chk = np.zeros((cw, cw, 4), np.uint8)
    yy, xx = np.mgrid[0:cw, 0:cw]
    k = ((yy // (2 * s)) + (xx // (2 * s))) % 2
    chk[..., :3] = np.where(k[..., None], 44, 34)
    chk[..., 3] = 255
    chk_im = Image.fromarray(chk, "RGBA")
    for idx in range(256):
        r, cc = divmod(idx, 16)
        x0 = 2 + cc * (cw + 2)
        y0 = 2 + r * (cw + 2 + lab)
        cell = Image.fromarray(np.clip(pg.cell_array(idx) + 0.5, 0, 255).astype(np.uint8), "RGBA")
        bg = chk_im.copy()
        bg.alpha_composite(cell.resize((cw, cw), Image.NEAREST))
        sheet.paste(bg, (x0, y0 + lab))
        used = idx in pg.meta
        dr.text((x0 + 1, y0), f"{pg.page:02X}{idx:02X}", fill=(230, 230, 240) if used else (80, 84, 96),
                font=font)
        if used:
            # 送り幅を示す線と、文字の高さの帯（4〜11 行）
            x_0, x_1 = pg.meta[idx]["span"]
            dr.line([(x0 + x_0 * s, y0 + lab + cw - 2), (x0 + x_1 * s - 1, y0 + lab + cw - 2)],
                    fill=(255, 80, 200), width=2)
            unit = c // 16
            for yy_ in (4 * unit, 12 * unit):
                dr.line([(x0, y0 + lab + yy_ * s), (x0 + 3, y0 + lab + yy_ * s)], fill=(120, 255, 120))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.convert("RGB").save(path)
    return path



# ===========================================================================
#  画面の見本を描くための文字（統合版の ASCII に似せた 5x7 のドット文字）と、行の組み立て
#  グリフは「不透明な列の範囲 + 1 px の隙間」で送る（実機の詰め方をまねる）
# ===========================================================================
_MCFONT_SRC = {
    "A": ".XXX.|X...X|XXXXX|X...X|X...X|X...X|X...X",
    "B": "XXXX.|X...X|XXXX.|X...X|X...X|X...X|XXXX.",
    "C": ".XXX.|X...X|X....|X....|X....|X...X|.XXX.",
    "D": "XXXX.|X...X|X...X|X...X|X...X|X...X|XXXX.",
    "E": "XXXXX|X....|XXX..|X....|X....|X....|XXXXX",
    "F": "XXXXX|X....|XXX..|X....|X....|X....|X....",
    "G": ".XXXX|X....|X..XX|X...X|X...X|X...X|.XXX.",
    "H": "X...X|X...X|XXXXX|X...X|X...X|X...X|X...X",
    "I": "XXX|.X.|.X.|.X.|.X.|.X.|XXX",
    "J": "....X|....X|....X|....X|....X|X...X|.XXX.",
    "K": "X...X|X..X.|XXX..|X..X.|X...X|X...X|X...X",
    "L": "X....|X....|X....|X....|X....|X....|XXXXX",
    "M": "X...X|XX.XX|X.X.X|X...X|X...X|X...X|X...X",
    "N": "X...X|XX..X|X.X.X|X..XX|X...X|X...X|X...X",
    "O": ".XXX.|X...X|X...X|X...X|X...X|X...X|.XXX.",
    "P": "XXXX.|X...X|XXXX.|X....|X....|X....|X....",
    "Q": ".XXX.|X...X|X...X|X...X|X...X|X..X.|.XX.X",
    "R": "XXXX.|X...X|XXXX.|X...X|X...X|X...X|X...X",
    "S": ".XXXX|X....|.XXX.|....X|....X|X...X|.XXX.",
    "T": "XXXXX|..X..|..X..|..X..|..X..|..X..|..X..",
    "U": "X...X|X...X|X...X|X...X|X...X|X...X|.XXX.",
    "V": "X...X|X...X|X...X|X...X|X...X|.X.X.|..X..",
    "W": "X...X|X...X|X...X|X...X|X.X.X|XX.XX|X...X",
    "X": "X...X|.X.X.|..X..|.X.X.|X...X|X...X|X...X",
    "Y": "X...X|.X.X.|..X..|..X..|..X..|..X..|..X..",
    "Z": "XXXXX|....X|...X.|..X..|.X...|X....|XXXXX",
    "0": ".XXX.|X...X|X..XX|X.X.X|XX..X|X...X|.XXX.",
    "1": "..X..|.XX..|..X..|..X..|..X..|..X..|XXXXX",
    "2": ".XXX.|X...X|....X|..XX.|.X...|X...X|XXXXX",
    "3": ".XXX.|X...X|....X|..XX.|....X|X...X|.XXX.",
    "4": "...XX|..X.X|.X..X|X...X|XXXXX|....X|....X",
    "5": "XXXXX|X....|XXXX.|....X|....X|X...X|.XXX.",
    "6": "..XX.|.X...|X....|XXXX.|X...X|X...X|.XXX.",
    "7": "XXXXX|X...X|....X|...X.|..X..|..X..|..X..",
    "8": ".XXX.|X...X|X...X|.XXX.|X...X|X...X|.XXX.",
    "9": ".XXX.|X...X|X...X|.XXXX|....X|...X.|.XX..",
    "a": ".....|.....|.XXX.|....X|.XXXX|X...X|.XXXX",
    "b": "X....|X....|X.XX.|XX..X|X...X|X...X|XXXX.",
    "c": ".....|.....|.XXX.|X...X|X....|X...X|.XXX.",
    "d": "....X|....X|.XX.X|X..XX|X...X|X...X|.XXXX",
    "e": ".....|.....|.XXX.|X...X|XXXXX|X....|.XXXX",
    "f": "..XX|.X..|XXXX|.X..|.X..|.X..|.X..",
    "g": ".....|.....|.XXXX|X...X|X...X|.XXXX|....X|XXXX.",
    "h": "X....|X....|X.XX.|XX..X|X...X|X...X|X...X",
    "i": "X|.|X|X|X|X|X",
    "j": "...X|....|...X|...X|...X|...X|X..X|.XX.",
    "k": "X...|X...|X..X|X.X.|XX..|X.X.|X..X",
    "l": "X.|X.|X.|X.|X.|X.|.X",
    "m": ".....|.....|XX.X.|X.X.X|X.X.X|X...X|X...X",
    "n": ".....|.....|XXXX.|X...X|X...X|X...X|X...X",
    "o": ".....|.....|.XXX.|X...X|X...X|X...X|.XXX.",
    "p": ".....|.....|X.XX.|XX..X|X...X|XXXX.|X....|X....",
    "q": ".....|.....|.XX.X|X..XX|X...X|.XXXX|....X|....X",
    "r": ".....|.....|X.XX.|XX..X|X....|X....|X....",
    "s": ".....|.....|.XXXX|X....|.XXX.|....X|XXXX.",
    "t": ".X.|.X.|XXX|.X.|.X.|.X.|..X",
    "u": ".....|.....|X...X|X...X|X...X|X...X|.XXXX",
    "v": ".....|.....|X...X|X...X|X...X|.X.X.|..X..",
    "w": ".....|.....|X...X|X...X|X.X.X|X.X.X|.XXXX",
    "x": ".....|.....|X...X|.X.X.|..X..|.X.X.|X...X",
    "y": ".....|.....|X...X|X...X|X...X|.XXXX|....X|XXXX.",
    "z": ".....|.....|XXXXX|...X.|..X..|.X...|XXXXX",
    ".": ".|.|.|.|.|.|X",
    ",": ".|.|.|.|.|.|X|X",
    ":": ".|X|.|.|.|.|X",
    "!": "X|X|X|X|X|.|X",
    "?": ".XXX.|X...X|....X|...X.|..X..|.....|..X..",
    "%": "X...X|....X|...X.|..X..|.X...|X....|X...X",
    "/": "....X|...X.|...X.|..X..|.X...|.X...|X....",
    "-": ".....|.....|.....|XXXXX|.....|.....|.....",
    "+": ".....|..X..|..X..|XXXXX|..X..|..X..|.....",
    "(": "..XX|.X..|X...|X...|X...|.X..|..XX",
    ")": "XX..|..X.|...X|...X|...X|..X.|XX..",
    "[": "XXX|X..|X..|X..|X..|X..|XXX",
    "]": "XXX|..X|..X|..X|..X|..X|XXX",
    "<": "...X|..X.|.X..|X...|.X..|..X.|...X",
    ">": "X...|.X..|..X.|...X|..X.|.X..|X...",
    "=": ".....|.....|XXXXX|.....|XXXXX|.....|.....",
    "'": "X|X|.|.|.|.|.",
    "&": ".XX..|X..X.|.XX..|.XX.X|X..X.|X..X.|.XX.X",
    "#": ".X.X.|.X.X.|XXXXX|.X.X.|XXXXX|.X.X.|.X.X.",
    "°": ".XX.|X..X|.XX.|....|....|....|....",
}
_MCFONT = {k: [r for r in v.split("|")] for k, v in _MCFONT_SRC.items()}
MC_COLORS = {
    "0": (0, 0, 0), "1": (0, 0, 170), "2": (0, 170, 0), "3": (0, 170, 170), "4": (170, 0, 0),
    "5": (170, 0, 170), "6": (255, 170, 0), "7": (170, 170, 170), "8": (85, 85, 85), "9": (85, 85, 255),
    "a": (85, 255, 85), "b": (85, 255, 255), "c": (255, 85, 85), "d": (255, 85, 255), "e": (255, 255, 85),
    "f": (255, 255, 255), "g": (221, 214, 5), "h": (227, 212, 209), "i": (206, 202, 202),
    "j": (68, 58, 59), "m": (151, 22, 7), "n": (180, 104, 77), "p": (222, 177, 45), "q": (17, 160, 54),
    "s": (44, 186, 168), "t": (33, 73, 123), "u": (154, 92, 198),
}
_JP_FONT = None


def _jp_glyph(ch):
    """日本語の文字: 16 px のドット文字（統合版の日本語ロケールのグリフと同じ密度）。"""
    global _JP_FONT
    if _JP_FONT is None:
        _JP_FONT = ImageFont.truetype("/usr/share/fonts/opentype/unifont/unifont_jp.otf", 16)
    im = Image.new("L", (18, 18), 0)
    ImageDraw.Draw(im).text((0, 0), ch, font=_JP_FONT, fill=255)
    a = np.array(im)[:16, :16] > 127
    cols = np.nonzero(a.any(axis=0))[0]
    if not len(cols):
        return None, 8
    return a[:, cols.min():cols.max() + 1], cols.max() - cols.min() + 1


class Glyphs:
    """mock 用: コードポイント -> (セル画像, セルの大きさ)。"""

    def __init__(self, *pages):
        self.pages = {pg.page: pg for pg in pages}

    def cell(self, ch):
        cp = ord(ch)
        pg = self.pages.get(cp >> 8)
        if pg is None:
            return None, 16
        a = pg.cell_array(cp & 0xFF)
        cols = np.nonzero(a[..., 3].max(axis=0) > 0)[0]
        if not len(cols):
            return None, pg.cell
        return a[:, cols.min():cols.max() + 1], pg.cell


def compose_line(text, glyphs, S=4, shadow=True, title=1):
    """1 行を描く。S = GUI px あたりの画素数、title = 文字の拡大率（タイトルは 2〜3）。
    戻り値: (RGBA float 配列, 幅 GUI px)。行の箱は 16 GUI px（グリフのセルと同じ高さ）。"""
    U = S * title                        # 1 GUI px の画素数（拡大込み）
    H = 16 * U
    out = np.zeros((H, 16 * U * max(1, len(text)) + 8 * U, 4), np.float32)
    x = 0
    colour = (255, 255, 255)
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "§" and i + 1 < len(text):
            code = text[i + 1]
            colour = MC_COLORS.get(code, colour) if code != "r" else (255, 255, 255)
            i += 2
            continue
        i += 1
        if ch == " ":
            x += 4 * U
            continue
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF:
            a, cell = glyphs.cell(ch)
            if a is None:
                continue
            f = 16.0 / cell                      # セル 1 画素 = f GUI px
            w = a.shape[1]
            im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), "RGBA")
            tw, th = max(1, round(w * f * U)), round(cell * f * U)
            im = im.resize((tw, th), Image.NEAREST if (f * U) >= 1 and float(f * U).is_integer()
                           else Image.LANCZOS)
            over(out, np.asarray(im, np.float32), x, 0)
            x += tw + U
            continue
        rows = _MCFONT.get(ch)
        if rows is not None:
            w = len(rows[0])
            dark = sum(colour) < 150
            for sh in ((1, (0.25, 0.25, 0.25)), (0, None)) if shadow and not dark else ((0, None),):
                off, k = sh
                col = colour if k is None else tuple(c * k[0] for c in colour)
                for r, row in enumerate(rows):
                    for cx, v in enumerate(row):
                        if v == "X":
                            yy = (4 + r + off) * U
                            xx = x + (cx + off) * U
                            out[yy:yy + U, xx:xx + U, :3] = col
                            out[yy:yy + U, xx:xx + U, 3] = 255
            x += (w + 1) * U
            continue
        a, w = _jp_glyph(ch)
        if a is not None:
            # 16 px の字を 8 GUI px に（S/2 倍）
            k = U / 2.0
            for off, kk in (((1, 0.25), (0, 1.0)) if shadow and sum(colour) >= 150 else ((0, 1.0),)):
                col = tuple(c * kk for c in colour)
                ys, xs = np.nonzero(a)
                for yy, xx in zip(ys, xs):
                    y0 = int(round((4 * U - 1 * U) + yy * k + off * U))
                    x0 = int(round(x + xx * k + off * U))
                    out[y0:y0 + int(math.ceil(k)), x0:x0 + int(math.ceil(k)), :3] = col
                    out[y0:y0 + int(math.ceil(k)), x0:x0 + int(math.ceil(k)), 3] = 255
            x += int(round(w * k)) + U
        else:
            x += 4 * U
    return out[:, :max(1, x - U)], (x - U) / U


# ===========================================================================
#  テクスチャ: ターミナルの惑星紋章（128x128）
# ===========================================================================
SYMBOL = {k: D.PLANETS[k]["symbol"] for k in KEYS}


def _font(path, size):
    return ImageFont.truetype(path, size)


def text_mask(cv, text, font_path, size, cx, cy, anchor="mm"):
    im = Image.new("L", (cv.W, cv.H), 0)
    ImageDraw.Draw(im).text((cx * cv.ss, cy * cv.ss), text, font=_font(font_path, int(size * cv.ss)), fill=255,
                            anchor=anchor)
    return np.asarray(im, np.float32) / 255.0


def metal_ring_colour(cv, cx, cy, dark=(54, 62, 80), light=(226, 234, 246), light_ang=-135.0):
    X, Y = cv.coords()
    ang = np.degrees(np.arctan2(Y - cy, X - cx))
    k = 0.5 + 0.5 * np.cos(np.radians(ang - light_ang))
    k = k ** 1.4
    # 帯状の映り込み
    k = np.clip(k + 0.12 * np.cos(np.radians(ang * 3 + 40)), 0, 1)
    return _ramp(k, [(0.0, dark), (0.55, mix(dark, light, 0.55)), (1.0, light)])


def ui_emblem(key):
    c = HUD_COL[key]
    cv = Canvas(128, ss=4)
    cx = cy = 64.0
    cv.glow(cv.ellipse(cx, cy, 50), c, 5, 0.45)
    # 四隅の留め具（輪の下）
    for ang in (45, 135, 225, 315):
        a = math.radians(ang)

        def pt(r, t, a=a):
            return (cx + math.cos(a) * r - math.sin(a) * t, cy + math.sin(a) * r + math.cos(a) * t)
        tab = [pt(47, -10), pt(61.5, -6.5), pt(61.5, 6.5), pt(47, 10)]
        cv.fill(cv.poly(tab), metal_ring_colour(cv, cx, cy, (44, 50, 66), (190, 200, 218)))
        cv.fill(cv.line([pt(52, -7.5), pt(52, 7.5)], 1.0), (24, 28, 40))
        cv.fill(cv.poly([pt(56, -3.2), pt(60, -2.4), pt(60, 2.4), pt(56, 3.2)]), c)
        cv.fill(cv.poly([pt(56.6, -2.2), pt(58.4, -1.8), pt(58.4, 0), pt(56.6, 0)]), WHITE, 0.8)
    # 外の金属の輪
    ring = cv.ring(cx, cy, 48.5, 57.5)
    cv.fill(ring, metal_ring_colour(cv, cx, cy))
    cv.fill(cv.ring(cx, cy, 56.6, 57.6), (20, 24, 36))                      # 外縁の溝
    cv.fill(cv.ring(cx, cy, 48.5, 49.6), (30, 34, 48))                      # 内縁の溝
    cv.fill(cv.ring(cx, cy, 52.4, 53.0), (40, 46, 62), 0.8)                 # 中央の溝
    X, Y = cv.coords()
    ang = (np.degrees(np.arctan2(Y - cy, X - cx)) + 360) % 360
    rr = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    # 目盛り（5° ごとに細かく、30° ごとに太く）
    fine = (np.abs(((ang + 2.5) % 5) - 2.5) < 0.45) & (rr > 53.4) & (rr < 56.0)
    cv.fill(fine.astype(np.float32), (30, 36, 50), 0.85)
    major = (np.abs(((ang + 15) % 30) - 15) < 1.1) & (rr > 49.8) & (rr < 56.4)
    cv.fill(major.astype(np.float32), (20, 24, 34))
    # 惑星色の発光の輪
    cv.glow(cv.ring(cx, cy, 45.4, 47.8), c, 2.0, 0.9)
    cv.fill(cv.ring(cx, cy, 45.6, 47.6), c)
    cv.fill(cv.ring(cx, cy, 46.3, 46.9), lighten(c, 0.7), 0.9)
    # 内側の暗い地と照準の格子
    disc = cv.ellipse(cx, cy, 45.6)
    cv.fill(disc, cv.radial(cx - 8, cy - 10, 60, [(0.0, mix((10, 16, 34), c, 0.18)), (1.0, (4, 6, 14))]))
    grid = np.zeros_like(disc)
    for r0 in (22.0, 34.0, 41.5):
        grid = np.maximum(grid, cv.ring(cx, cy, r0, r0 + 0.5))
    for a0 in (0, 90):
        a = math.radians(a0)
        grid = np.maximum(grid, cv.line([(cx - math.cos(a) * 44, cy - math.sin(a) * 44),
                                         (cx + math.cos(a) * 44, cy + math.sin(a) * 44)], 0.5))
    cv.fill(grid * disc, c, 0.16)
    # 星
    rng = np.random.default_rng(D.PLANETS[key]["order"] * 101)
    for _ in range(26):
        sx, sy = rng.uniform(22, 106, 2)
        if (sx - cx) ** 2 + (sy - cy) ** 2 < 42 ** 2:
            cv.fill(cv.ellipse(sx, sy, rng.uniform(0.3, 0.7)), (220, 230, 255), rng.uniform(0.4, 0.9))
    # 惑星
    rad = {"saturn": 22.5, "sol": 25.0, "uranus": 27.0, "jupiter": 31.0}.get(key, 29.5)
    pl = render_planet(key, 128, rad, ss=3, detail=1.0)
    cv.paste(pl, 0, 0)
    # 下の記号の札
    tab = [(48, 107), (80, 107), (85, 113), (80, 121), (48, 121), (43, 113)]
    cv.fill(cv.poly([(x, y + 0.8) for x, y in tab]), (0, 0, 0), 0.5)
    cv.fill(cv.poly(tab), cv.grad((43, 107), (85, 121), (210, 220, 236), (70, 80, 102)))
    inner = [(50, 109), (78, 109), (81.5, 113), (78, 119), (50, 119), (46.5, 113)]
    cv.fill(cv.poly(inner), (8, 12, 24))
    cv.fill(text_mask(cv, SYMBOL[key], FONT_SYM_B, 10.5, 56, 114), c)
    cv.fill(text_mask(cv, f"{D.PLANETS[key]['order']:02d}", FONT_SYM_B, 7.0, 71, 114.2), lighten(c, 0.4), 0.9)
    return soft_outlined(cv.result(), INK, 190)


# ===========================================================================
#  テクスチャ: ターミナルのメニューアイコン（64x64）
# ===========================================================================
MENU_ACCENT = {
    "status": (110, 230, 255), "codex": (150, 170, 255), "revert": (255, 96, 96), "settings": (200, 214, 232),
    "guide": (110, 255, 160), "records": (255, 206, 72), "back": (220, 230, 245),
}


def menu_badge(cv, acc):
    """暗い六角の札と細い縁（全部のアイコンで共通）。"""
    outer = cv.poly(hex_pts(32, 32, 29.5, 29.5 * 1.0, flat=False))
    inner = cv.poly(hex_pts(32, 32, 26.6, 26.6, flat=False))
    cv.fill(outer, cv.grad((8, 4), (56, 60), (214, 224, 240), (70, 80, 104)))
    cv.fill(inner, cv.radial(26, 22, 40, [(0.0, mix((14, 22, 44), acc, 0.20)), (1.0, (6, 9, 20))]))
    cv.fill(np.clip(inner - cv.poly(hex_pts(32, 32, 25.4, 25.4, flat=False)), 0, 1), acc, 0.65)


def menu_icon(name):
    acc = MENU_ACCENT[name]
    cv = Canvas(64, ss=4)
    menu_badge(cv, acc)
    hi = lighten(acc, 0.65)

    def stroke(m, col=None, glow=True):
        if glow:
            cv.glow(m, acc, 1.2, 0.8)
        cv.fill(m, hi if col is None else col)
    if name == "status":
        arc = cv.arc(32, 35, 15, 150, 390, 4.0)
        stroke(arc, acc)
        X, Y = cv.coords()
        ang = (np.degrees(np.arctan2(Y - 35, X - 32)) + 360) % 360
        rr = np.sqrt((X - 32) ** 2 + (Y - 35) ** 2)
        ticks = ((np.abs(((ang + 7.5) % 15) - 7.5) < 1.4) & (rr > 12.5) & (rr < 17.5)).astype(np.float32)
        cv.fill(ticks * arc, (10, 16, 30))
        a = math.radians(300)
        stroke(cv.line([(32, 35), (32 + math.cos(a) * 13, 35 + math.sin(a) * 13)], 2.4), WHITE)
        cv.fill(cv.ellipse(32, 35, 3.4), hi)
        for i, h in enumerate((5, 8, 11)):
            stroke(cv.poly([(24 + i * 6, 49 - h * 0.45), (28 + i * 6, 49 - h * 0.45), (28 + i * 6, 49),
                            (24 + i * 6, 49)]), acc, glow=False)
    elif name == "codex":
        cv.fill(cv.ellipse(32, 32, 10), cv.radial(28, 28, 14, [(0.0, (230, 236, 255)), (0.6, acc),
                                                                (1.0, (40, 50, 120))]))
        for yy in (29, 34):
            cv.fill(cv.line([(23, yy), (41, yy + 1)], 1.0), (60, 70, 150), 0.6)
        orbit = np.clip(cv.ellipse(32, 32, 20, 7) - cv.ellipse(32, 32, 18.2, 5.6), 0, 1)
        X, Y = cv.coords()
        front = (Y > 32).astype(np.float32)
        back = orbit * (1 - front) * (1 - cv.ellipse(32, 32, 10))
        stroke(orbit * front + back, hi)
        cv.fill(cv.ellipse(49, 36, 3.0), WHITE)
        cv.fill(cv.ellipse(16, 27, 1.6), hi)
    elif name == "revert":
        stroke(cv.arc(32, 33.5, 13, -55, 235, 4.2), acc)
        stroke(cv.line([(32, 14), (32, 31)], 4.2), WHITE)
    elif name == "settings":
        X, Y = cv.coords()
        ang = np.arctan2(Y - 32, X - 32)
        rr = np.sqrt((X - 32) ** 2 + (Y - 32) ** 2)
        teeth = np.clip((np.cos(ang * 8) - 0.15) * 6, 0, 1)
        gear = ((rr < 13.5) | ((rr < 18) & (teeth > 0.5))).astype(np.float32)
        gear *= (rr > 6.0)
        cv.glow(gear, acc, 1.2, 0.6)
        cv.fill(gear, cv.grad((16, 14), (48, 50), (250, 252, 255), (130, 144, 170)))
        cv.fill(cv.ring(32, 32, 9.0, 10.0), (60, 70, 92))
        cv.fill(cv.ellipse(32, 32, 3.2), (110, 230, 255))
    elif name == "guide":
        body = cv.poly([(15, 27), (22, 22), (42, 22), (49, 27), (51, 40), (46, 44), (41, 41), (23, 41), (18, 44),
                        (13, 40)])
        cv.glow(body, acc, 1.2, 0.6)
        cv.fill(body, cv.grad((14, 22), (50, 44), (236, 244, 252), (120, 134, 160)))
        cv.fill(cv.poly([(19, 30), (22, 30), (22, 27), (25, 27), (25, 30), (28, 30), (28, 33), (25, 33), (25, 36),
                         (22, 36), (22, 33), (19, 33)]), (30, 36, 52))
        for (x, y, col) in ((41, 28, acc), (45, 31.5, (255, 110, 110)), (37, 31.5, (255, 214, 80)),
                            (41, 35, (120, 190, 255))):
            cv.fill(cv.ellipse(x, y, 2.0), col)
        cv.fill(cv.line([(28, 23.5), (36, 23.5)], 1.0), WHITE, 0.6)
    elif name == "records":
        cup = cv.poly([(21, 16), (43, 16), (41, 29), (36, 34), (28, 34), (23, 29)])
        cv.glow(cup, acc, 1.2, 0.6)
        handles = np.clip(cv.ring(21, 22, 4.0, 6.4) + cv.ring(43, 22, 4.0, 6.4), 0, 1) * \
            (1 - cv.poly([(20, 14), (44, 14), (44, 32), (20, 32)]) * 0)
        cv.fill(handles * (1 - cv.poly([(21, 15), (43, 15), (41, 29), (23, 29)])), (220, 160, 40))
        cv.fill(cup, cv.grad((21, 16), (43, 34), (255, 246, 180), (214, 140, 30)))
        cv.fill(cv.poly([(29, 34), (35, 34), (35, 40), (29, 40)]), (200, 132, 30))
        cv.fill(cv.poly([(23, 40), (41, 40), (43, 46), (21, 46)]), cv.grad((21, 40), (43, 46),
                                                                          (255, 230, 140), (170, 104, 20)))
        star = []
        for i in range(10):
            a = math.radians(i * 36 - 90)
            r = 5.2 if i % 2 == 0 else 2.2
            star.append((32 + math.cos(a) * r, 23.5 + math.sin(a) * r))
        cv.fill(cv.poly(star), WHITE)
        cv.fill(cv.line([(25, 18), (24.5, 25)], 1.2), WHITE, 0.6)
    elif name == "back":
        arrow = cv.poly([(14, 32), (29, 18), (29, 26), (48, 26), (48, 38), (29, 38), (29, 46)])
        stroke(arrow, cv.grad((14, 20), (48, 44), (255, 255, 255), (150, 164, 190)))
    return soft_outlined(cv.result(), INK, 200)


# ===========================================================================
#  テクスチャ: 素材・道具のアイテムアイコン（64x64、2 値のアルファ＋暗い縁取り）
# ===========================================================================
ICON_OUTLINE = (14, 12, 20)


def _rot_fit(arr, deg, size=64, margin=1):
    im = Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8), "RGBA")
    if deg:
        im = im.rotate(deg, resample=Image.BICUBIC, expand=True)
    bb = im.getbbox()
    im = im.crop(bb)
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
    inner = size - 2 * margin
    sq = sq.resize((inner, inner), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(sq, (margin, margin))
    return np.asarray(out, np.float32)


def item_nano_cell():
    cv = Canvas(64, ss=4)
    cyan = (90, 236, 255)
    # 胴（ガラス）
    body = cv.poly([(22, 17), (42, 17), (42, 47), (22, 47)])
    cv.fill(body, cv.grad((22, 0), (42, 0), None, None, [(0.0, (40, 120, 150)), (0.25, (120, 240, 255)),
                                                          (0.6, (40, 170, 210)), (1.0, (16, 70, 100))]))
    liquid = cv.poly([(23, 24), (41, 22.5), (41, 46), (23, 46)])
    cv.fill(liquid, cv.grad((0, 22), (0, 46), (160, 250, 255), (20, 120, 180)), 0.85)
    rng = np.random.default_rng(5)
    for _ in range(16):
        x, y = rng.uniform(24, 40), rng.uniform(25, 45)
        sz = rng.uniform(0.7, 1.4)
        cv.fill(cv.poly([(x, y - sz), (x + sz, y), (x, y + sz), (x - sz, y)]), (230, 255, 255), 0.95)
    cv.fill(cv.poly([(25, 19), (27.5, 19), (27.5, 45), (25, 45)]), WHITE, 0.55)       # ガラスの照り
    cv.fill(cv.line([(23, 31), (41, 31)], 0.6), (20, 60, 90), 0.6)
    cv.fill(cv.line([(23, 38), (41, 38)], 0.6), (20, 60, 90), 0.6)
    # 金属の蓋（上下）
    for (y0, y1, flip) in ((9, 18, False), (46, 55, True)):
        cap = cv.poly([(20, y0 + (0 if flip else 2)), (44, y0 + (0 if flip else 2)), (44, y1 - (2 if flip else 0)),
                       (20, y1 - (2 if flip else 0))])
        cv.fill(cap, cv.grad((20, 0), (44, 0), None, None, [(0.0, (90, 100, 124)), (0.3, (236, 242, 250)),
                                                             (0.65, (140, 152, 176)), (1.0, (52, 60, 80))]))
        yy = y0 + 4.5
        cv.fill(cv.line([(20, yy), (44, yy)], 0.8), (40, 46, 62))
        nub = (26, y0 - 3, 38, y0) if not flip else (26, y1, 38, y1 + 3)
        cv.fill(cv.poly([(nub[0], nub[1]), (nub[2], nub[1]), (nub[2], nub[3]), (nub[0], nub[3])]),
                cv.grad((26, 0), (38, 0), (220, 228, 240), (90, 100, 124)))
    cv.fill(cv.poly([(30.5, 6), (33.5, 6), (33.5, 8), (30.5, 8)]), cyan)
    return outlined(_rot_fit(cv.result(), -28), ICON_OUTLINE)


def item_core_frame():
    cv = Canvas(64, ss=4)
    hx = hex_pts(32, 32, 28, 28, flat=False)
    cv.fill(cv.poly(hx), cv.grad((6, 4), (58, 60), None, None, [(0.0, (236, 242, 252)), (0.45, (150, 164, 188)),
                                                                 (1.0, (60, 70, 92))]))
    cv.fill(cv.poly(hex_pts(32, 32, 24, 24, flat=False)), cv.grad((10, 8), (54, 56), (80, 90, 112), (170, 182, 204)))
    # 中央の空の受け口
    cv.fill(cv.ellipse(32, 32, 15.5), (24, 28, 40))
    cv.fill(cv.ring(32, 32, 13.6, 15.5), metal_ring_colour(cv, 32, 32, (60, 68, 88), (230, 236, 248)))
    cv.fill(cv.ellipse(32, 32, 13.6), cv.radial(32, 32, 13.6, [(0.0, (30, 60, 90)), (0.75, (12, 18, 34)),
                                                               (1.0, (40, 120, 160))]))
    cv.fill(cv.ring(32, 32, 9.5, 10.4), (110, 230, 255), 0.85)
    cv.fill(cv.ellipse(32, 32, 2.0), (190, 250, 255))
    # 4 つの爪
    for a0 in (0, 90, 180, 270):
        a = math.radians(a0)

        def pt(r, t, a=a):
            return (32 + math.cos(a) * r - math.sin(a) * t, 32 + math.sin(a) * r + math.cos(a) * t)
        cl = [pt(11, -3), pt(19, -4.2), pt(19, 4.2), pt(11, 3)]
        cv.fill(cv.poly(cl), cv.grad(pt(19, -4), pt(11, 3), (240, 244, 252), (100, 112, 136)))
        cv.fill(cv.ellipse(*pt(16, 0), 1.1), (110, 230, 255))
    for (x, y) in hx:
        bx, by = 32 + (x - 32) * 0.8, 32 + (y - 32) * 0.8
        cv.fill(cv.ellipse(bx, by, 1.6), (40, 46, 62))
        cv.fill(cv.ellipse(bx - 0.4, by - 0.4, 0.8), (230, 236, 248))
    return outlined(_rot_fit(cv.result(), 0), ICON_OUTLINE)


def crystal(cv, bx, by, length, width, ang, tip_col, body_col, deep_col):
    """結晶の柱（左の面は明るく、右の面は暗く、芯は白く光る）。ang = 傾き（度、0 = 真上）。"""
    a = math.radians(ang)
    d = (math.sin(a), -math.cos(a))
    n = (math.cos(a), math.sin(a))

    def P(t, u):
        return (bx + d[0] * t + n[0] * u, by + d[1] * t + n[1] * u)
    sh = length - width * 0.95
    bl, br, cb = P(0, -width / 2), P(0, width / 2), P(0, width * 0.08)
    sl, sr, cs = P(sh, -width / 2), P(sh, width / 2), P(sh + width * 0.1, width * 0.08)
    tip = P(length, -width * 0.05)
    cv.fill(cv.poly([bl, sl, tip, cs, cb]), cv.grad(P(length, 0), P(0, -width), tip_col, body_col))
    cv.fill(cv.poly([cb, cs, tip, sr, br]), cv.grad(P(length, 0), P(0, width), body_col, deep_col))
    cv.fill(cv.poly([sl, tip, cs]), lighten(tip_col, 0.5), 0.8)
    cv.fill(cv.line([P(width * 0.3, -width * 0.32), P(sh, -width * 0.32)], max(0.5, width * 0.09)), WHITE, 0.75)
    cv.fill(cv.line([cb, cs], max(0.4, width * 0.06)), (255, 255, 236), 0.7)


def item_solar_fragment():
    cv = Canvas(64, ss=4)
    tip, body, deep = (255, 252, 226), (255, 196, 64), (214, 76, 18)
    cv.glow(cv.ellipse(32, 36, 18, 24), (255, 160, 40), 3.0, 0.6)
    crystal(cv, 22, 54, 30, 10, -28, tip, (255, 178, 52), deep)
    crystal(cv, 43, 55, 26, 9.5, 30, tip, (255, 170, 48), deep)
    crystal(cv, 32, 57, 50, 14, 4, tip, body, deep)
    # 根元の岩と火の粉
    cv.fill(cv.poly([(16, 56), (24, 51), (40, 51), (49, 56), (44, 61), (21, 61)]),
            cv.grad((16, 51), (49, 61), (150, 80, 40), (60, 26, 14)))
    cv.fill(cv.ellipse(33, 30, 4.0), (255, 255, 240), 0.8)
    for (x, y, r) in ((48, 13, 4.2), (14, 27, 2.8), (52, 35, 2.0)):
        st = [(x, y - r), (x + r * 0.26, y - r * 0.26), (x + r, y), (x + r * 0.26, y + r * 0.26), (x, y + r),
              (x - r * 0.26, y + r * 0.26), (x - r, y), (x - r * 0.26, y - r * 0.26)]
        cv.fill(cv.poly(st), (255, 250, 214))
    return outlined(_rot_fit(cv.result(), 0), ICON_OUTLINE)


def item_terminal():
    cv = Canvas(64, ss=4)
    body = cv.poly([(14, 10), (46, 10), (50, 14), (50, 54), (46, 58), (18, 58), (14, 54)])
    cv.fill(body, cv.grad((14, 10), (50, 58), None, None, [(0.0, (190, 200, 220)), (0.3, (96, 108, 132)),
                                                            (1.0, (40, 46, 62))]))
    cv.fill(cv.poly([(16, 12), (45, 12), (48, 15), (48, 52), (16, 52)]), (34, 40, 56))
    screen = cv.poly([(18, 15), (46, 15), (46, 40), (18, 40)])
    cv.fill(screen, cv.grad((18, 15), (46, 40), (14, 40, 70), (6, 14, 30)))
    cv.fill(cv.ellipse(28, 27, 6.5), cv.radial(26, 25, 8, [(0.0, (180, 250, 255)), (0.7, (60, 190, 255)),
                                                          (1.0, (20, 80, 160))]))
    orbit = np.clip(cv.ellipse(28, 27, 10.5, 3.6) - cv.ellipse(28, 27, 9.4, 2.7), 0, 1)
    cv.fill(orbit, (140, 240, 255), 0.95)
    for i, w in enumerate((8, 6, 7)):
        cv.fill(cv.line([(37, 20 + i * 4), (37 + w, 20 + i * 4)], 1.2), (120, 230, 255), 0.9)
    cv.fill(cv.line([(19.5, 37.5), (44.5, 37.5)], 0.8), (90, 200, 255), 0.7)
    cv.fill(cv.line([(19, 16), (30, 16)], 0.8), WHITE, 0.35)
    for (x, col) in ((22, (110, 236, 255)), (29, (255, 110, 160)), (36, (255, 214, 80))):
        cv.fill(cv.ellipse(x, 46, 2.4), col)
        cv.fill(cv.ellipse(x - 0.6, 45.4, 0.9), WHITE, 0.8)
    for i in range(3):
        cv.fill(cv.line([(41, 44 + i * 2.2), (46, 44 + i * 2.2)], 0.9), (20, 24, 34))
    cv.fill(cv.poly([(40, 4), (43, 4), (43, 10), (40, 10)]), cv.grad((40, 0), (43, 0), (220, 228, 240),
                                                                     (90, 100, 124)))
    cv.fill(cv.ellipse(41.5, 4, 2.0), (110, 236, 255))
    return outlined(_rot_fit(cv.result(), 0), ICON_OUTLINE)


def item_void_signal():
    cv = Canvas(64, ss=4)
    vio = (176, 90, 255)
    # 信号の弧
    for r in (9.5, 14, 18.5):
        cv.fill(cv.arc(32, 30, r, 215, 325, 1.8), lighten(vio, 0.35) if r < 15 else vio)
    # 台座の爪
    base = cv.poly([(18, 56), (46, 56), (42, 50), (22, 50)])
    cv.fill(base, cv.grad((18, 50), (46, 56), (110, 104, 130), (30, 26, 40)))
    for sgn in (-1, 1):
        claw = cv.poly([(32 + sgn * 6, 51), (32 + sgn * 14, 40), (32 + sgn * 12, 30), (32 + sgn * 9, 31),
                        (32 + sgn * 10, 40), (32 + sgn * 3, 50)])
        cv.fill(claw, cv.grad((32 + sgn * 14, 30), (32, 52), (150, 140, 170), (34, 30, 46)))
    # 暗い結晶（八面体）
    top, left, right, bot, mid = (32, 22), (23, 38), (41, 38), (32, 54), (32, 40)
    cv.glow(cv.poly([top, right, bot, left]), vio, 2.2, 0.9)
    cv.fill(cv.poly([top, left, mid]), cv.grad(top, left, (220, 170, 255), (90, 30, 160)))
    cv.fill(cv.poly([top, right, mid]), cv.grad(top, right, (130, 60, 210), (40, 10, 80)))
    cv.fill(cv.poly([left, bot, mid]), cv.grad(left, bot, (70, 20, 120), (20, 6, 40)))
    cv.fill(cv.poly([right, bot, mid]), cv.grad(right, bot, (40, 10, 80), (14, 4, 30)))
    cv.fill(cv.ellipse(32, 38, 3.2), (240, 214, 255))
    cv.fill(cv.ellipse(32, 38, 1.4), WHITE)
    cv.fill(cv.line([top, (24.5, 37)], 0.7), (250, 230, 255), 0.8)
    return outlined(_rot_fit(cv.result(), 0), ICON_OUTLINE)


ITEM_ICONS = {
    "nano_cell": item_nano_cell, "core_frame": item_core_frame, "solar_fragment": item_solar_fragment,
    "terminal": item_terminal, "void_signal": item_void_signal,
}


# ===========================================================================
#  テクスチャ: スーツのアイコン（モデルがあれば兜と胸を描く。無ければ紋章付きの兜の絵）
# ===========================================================================
def suit_paths(key):
    geo = os.path.join(RP, "models", "entity", f"astro_suit_{key}.geo.json")
    tex = os.path.join(RP, "textures", "entity", "astro", f"suit_{key}.png")
    return geo, tex


def render_bust(geo_path, tex_path, size=64, yaw=-26.0, pitch=-8.0):
    """スーツのジオメトリ（プレイヤーと同じボーン名）を休みの姿勢で描き、脚を隠して頭と胴を切り出す。"""
    hyper = os.path.join(TOOLS, "hyperdim")
    if hyper not in sys.path:
        sys.path.insert(0, hyper)
    from hd_preview import render   # noqa: E402
    geo = json.load(open(geo_path, encoding="utf-8"))["minecraft:geometry"][0]
    bones = geo.get("bones", [])
    parent = {b["name"]: b.get("parent") for b in bones}

    def under(name, roots):
        seen = set()
        while name and name not in seen:
            if name in roots:
                return True
            seen.add(name)
            name = parent.get(name)
        return False
    roots = {"rightLeg", "leftLeg"}
    hide = {b["name"] for b in bones if under(b["name"], roots) or b["name"].startswith("fx_thrust")}
    big = render(geo_path, tex_path, 256, yaw, pitch, 0, margin=0.02, bg=(0, 0, 0, 0), ss=2, hide=tuple(hide))
    bb = big.getbbox()
    if not bb:
        return None
    big = big.crop(bb)
    # 上の 8 割（兜・胸・肩）を残す
    w, h = big.size
    big = big.crop((0, 0, w, int(h * 0.80)))
    side = max(big.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(big, ((side - big.size[0]) // 2, (side - big.size[1]) // 2))
    im = sq.resize((size - 2, size - 2), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(im, (1, 1))
    return outlined(np.asarray(canvas, np.float32), ICON_OUTLINE, thr=90)


def suit_icon_fallback(key):
    """紋章付きの兜の絵（スーツのモデルが無い時の代わり）。惑星ごとの飾り（翼・冠・鶏冠・環・光輪）を付ける。"""
    col = D.PLANETS[key]["colors"]
    plate, plate2, glow, accent = col["plate"], col["plate2"], col["glow"], col["accent"]
    cv = Canvas(64, ss=4)
    metal = lambda p0, p1, c: cv.grad(p0, p1, lighten(c, 0.45), shade(c, 0.55))  # noqa: E731
    # --- 兜の後ろの飾り ---
    if key == "sol":
        for i in range(12):
            a = math.radians(i * 30 + 15)
            r0, r1 = 15, 29 if i % 2 == 0 else 24
            cv.fill(cv.poly([(32 + math.cos(a - 0.16) * r0, 25 + math.sin(a - 0.16) * r0),
                             (32 + math.cos(a) * r1, 25 + math.sin(a) * r1),
                             (32 + math.cos(a + 0.16) * r0, 25 + math.sin(a + 0.16) * r0)]),
                    cv.grad((32, 25), (32 + math.cos(a) * r1, 25 + math.sin(a) * r1), (255, 246, 190), accent))
        cv.fill(cv.ring(32, 25, 17, 19.5), (255, 214, 90))
    if key == "saturn":
        cv.fill(np.clip(cv.ellipse(32, 24, 30, 8) - cv.ellipse(32, 24, 24, 5), 0, 1), metal((2, 16), (62, 32), plate))
    if key == "mercury":
        for sgn in (-1, 1):
            for k in range(3):
                y0 = 14 + k * 4.5
                cv.fill(cv.poly([(32 + sgn * 14, y0 + 2), (32 + sgn * (27 - k * 3), y0 - 6 + k * 1.5),
                                 (32 + sgn * (25 - k * 3), y0 - 3 + k * 1.5), (32 + sgn * 15, y0 + 5)]),
                        metal((32, y0 - 6), (32 + sgn * 26, y0 + 5), (226, 234, 244)))
    # --- 肩と胸 ---
    chest = cv.poly([(6, 63), (10, 47), (22, 41), (42, 41), (54, 47), (58, 63)])
    cv.fill(chest, cv.grad((6, 41), (58, 63), lighten(plate2, 0.2), shade(plate2, 0.45)))
    for sgn in (-1, 1):
        cv.fill(cv.poly([(32 + sgn * 12, 43), (32 + sgn * 25, 46), (32 + sgn * 27, 56), (32 + sgn * 15, 52)]),
                metal((32 + sgn * 12, 43), (32 + sgn * 27, 56), plate))
    cv.fill(cv.poly([(24, 45), (40, 45), (36, 58), (28, 58)]), shade(plate, 0.9))
    cv.glow(cv.ellipse(32, 51, 3.8), glow, 1.2, 0.8)
    cv.fill(cv.ellipse(32, 51, 3.8), glow)
    cv.fill(cv.ellipse(31.2, 50.2, 1.5), WHITE, 0.85)
    # --- 兜 ---
    helm = cv.poly([(32, 6), (44, 10), (49, 21), (48, 33), (42, 42), (32, 45), (22, 42), (16, 33), (15, 21), (20, 10)])
    cv.fill(helm, cv.grad((16, 6), (48, 44), None, None, [(0.0, lighten(plate, 0.5)), (0.45, plate),
                                                           (1.0, shade(plate, 0.42))]))
    cv.fill(cv.poly([(16, 26), (24, 27), (24, 38), (19, 36)]), shade(plate2, 0.8))
    cv.fill(cv.poly([(48, 26), (40, 27), (40, 38), (45, 36)]), shade(plate2, 0.6))
    cv.fill(cv.line([(20, 11), (29, 7.5)], 0.9), WHITE, 0.55)
    visor = cv.poly([(19, 22), (32, 26), (45, 22), (43, 29), (32, 32.5), (21, 29)])
    cv.glow(visor, glow, 1.0, 0.7)
    cv.fill(visor, cv.grad((19, 22), (45, 32), lighten(glow, 0.6), shade(glow, 0.6)))
    cv.fill(cv.line([(22, 24), (30, 26.4)], 0.8), WHITE, 0.8)
    cv.fill(cv.poly([(29, 34), (35, 34), (34, 41), (30, 41)]), shade(plate, 0.6))
    # --- 兜の上の飾り ---
    gold = (255, 210, 90)
    if key == "venus":
        st = []
        for i in range(10):
            a = math.radians(i * 36 - 90)
            r = 7.5 if i % 2 == 0 else 3.2
            st.append((32 + math.cos(a) * r, 6 + math.sin(a) * r))
        cv.fill(cv.poly(st), cv.grad((26, 0), (38, 12), (255, 252, 220), (255, 190, 60)))
    elif key == "earth":
        cv.fill(cv.poly([(30, 9), (33, 0.5), (36, 2), (34.5, 10)]), metal((30, 0), (36, 10), (240, 246, 252)))
        cv.fill(cv.ellipse(47, 9, 3.4), cv.radial(46, 8, 4, [(0.0, (250, 250, 255)), (1.0, (150, 160, 180))]))
    elif key == "mars":
        crest = [(20, 12), (24, 4), (32, 0.8), (40, 4), (44, 12), (40, 9), (32, 5), (24, 9)]
        cv.fill(cv.poly(crest), cv.grad((20, 0), (44, 12), lighten(accent, 0.3), shade(plate, 0.7)))
        for x in range(23, 42, 3):
            cv.fill(cv.line([(x, 6 - 0.15 * abs(x - 32)), (x + 1, 9)], 0.5), shade(plate, 0.5), 0.8)
    elif key == "jupiter":
        crown = [(20, 13), (20, 4), (25, 9), (32, 1), (39, 9), (44, 4), (44, 13)]
        cv.fill(cv.poly(crown), cv.grad((20, 1), (44, 13), (255, 246, 190), (200, 130, 40)))
        cv.fill(cv.poly([(33, 5), (29.5, 10), (32, 10), (30.5, 13.5), (35, 8.5), (32.5, 8.5)]), (140, 236, 255))
    elif key == "uranus":
        dia = [(32, -0.5), (37, 5.5), (32, 13), (27, 5.5)]
        cv.fill(cv.poly(dia), cv.grad((27, 0), (37, 13), (240, 255, 255), (80, 190, 210)))
        cv.fill(cv.poly([(32, -0.5), (37, 5.5), (32, 7)]), (150, 230, 240))
    elif key == "neptune":
        for x, h in ((24, 6), (32, 0.5), (40, 6)):
            cv.fill(cv.poly([(x - 1.6, 12), (x - 1.6, h + 3), (x, h), (x + 1.6, h + 3), (x + 1.6, 12)]),
                    cv.grad((x, h), (x, 12), (234, 244, 255), (60, 120, 220)))
        cv.fill(cv.line([(23, 11), (41, 11)], 1.4), (200, 230, 255))
    elif key == "saturn":
        cv.fill(np.clip(cv.ellipse(32, 24, 30, 8) - cv.ellipse(32, 24, 24, 5), 0, 1) * cv.poly(
            [(0, 24), (64, 24), (64, 40), (0, 40)]), metal((2, 24), (62, 32), plate))
    elif key == "sol":
        cv.fill(cv.poly([(29, 9), (32, 1), (35, 9)]), gold)
    # 額の紋章
    em = render_planet(key, 14, {"saturn": 3.4, "sol": 4.0}.get(key, 4.6), ss=4, detail=0.6)
    cv.fill(cv.poly(hex_pts(32, 15.5, 6.8, 6.0)), (20, 26, 40))
    cv.fill(np.clip(cv.poly(hex_pts(32, 15.5, 6.8, 6.0)) - cv.poly(hex_pts(32, 15.5, 5.7, 4.9)), 0, 1), HUD_COL[key])
    cv.paste(em, 25, 8.5)
    return outlined(_rot_fit(cv.result(), 0), ICON_OUTLINE)


def suit_icon(key):
    geo, tex = suit_paths(key)
    if os.path.exists(geo) and os.path.exists(tex):
        try:
            img = render_bust(geo, tex)
            if img is not None:
                return img, "model"
        except Exception as e:  # noqa: BLE001  モデルの書式が想定外でも代わりの絵で続ける
            print(f"  ui: suit_{key} の描画に失敗（{e}）→ 代わりの絵")
    return suit_icon_fallback(key), "fallback"


# ===========================================================================
#  パックアイコン（256x256）: 深宇宙・軌道の弧に 8 惑星と太陽・中央の星核とナノマシンの奔流・題字
# ===========================================================================
# 面取りしたメカ文字（5x7 の升目。外形と穴の多角形）
LOGO = {
    "A": ([(0, 7), (0, 1.3), (1.3, 0), (5, 0), (5, 7), (3.5, 7), (3.5, 4.4), (1.5, 4.4), (1.5, 7)],
          [[(1.5, 1.4), (3.5, 1.4), (3.5, 3.0), (1.5, 3.0)]]),
    "S": ([(1.3, 0), (5, 0), (5, 1.4), (1.5, 1.4), (1.5, 2.8), (3.7, 2.8), (5, 4.1), (5, 5.7), (3.7, 7), (0, 7),
           (0, 5.6), (3.5, 5.6), (3.5, 4.2), (1.3, 4.2), (0, 2.9), (0, 1.3)], []),
    "T": ([(0, 0), (5, 0), (5, 1.4), (3.25, 1.4), (3.25, 7), (1.75, 7), (1.75, 1.4), (0, 1.4)], []),
    "R": ([(0, 0), (3.7, 0), (5, 1.3), (5, 3.3), (4.1, 4.1), (5, 5.0), (5, 7), (3.5, 7), (3.5, 5.3), (2.9, 4.7),
           (1.5, 4.7), (1.5, 7), (0, 7)], [[(1.5, 1.4), (3.5, 1.4), (3.5, 3.3), (1.5, 3.3)]]),
    "O": ([(1.3, 0), (5, 0), (5, 5.7), (3.7, 7), (0, 7), (0, 1.3)], [[(1.5, 1.4), (3.5, 1.4), (3.5, 5.6), (1.5, 5.6)]]),
    "N": ([(0, 7), (0, 0), (1.5, 0), (3.5, 3.9), (3.5, 0), (5, 0), (5, 7), (3.5, 7), (1.5, 3.1), (1.5, 7)], []),
    "G": ([(1.3, 0), (5, 0), (5, 1.4), (1.5, 1.4), (1.5, 5.6), (3.5, 5.6), (3.5, 4.4), (2.5, 4.4), (2.5, 3.0), (5, 3.0),
           (5, 5.7), (3.7, 7), (0, 7), (0, 1.3)], []),
    "E": ([(1.3, 0), (5, 0), (5, 1.4), (1.5, 1.4), (1.5, 2.8), (4.2, 2.8), (4.2, 4.2), (1.5, 4.2), (1.5, 5.6),
           (5, 5.6), (5, 7), (0, 7), (0, 1.3)], []),
}


def logo_mask(cv, text, x0, y0, unit, gap=1.15, skew=0.22):
    """文字列のマスクと全体の幅（px）。"""
    m = np.zeros((cv.H, cv.W), np.float32)
    x = x0
    for ch in text:
        if ch == " ":
            x += unit * 2.6
            continue
        outer, holes = LOGO[ch]

        def tr(pts, x=x):
            return [(x + (px + (7 - py) * skew) * unit, y0 + py * unit) for px, py in pts]
        lm = cv.poly(tr(outer))
        for h in holes:
            lm = np.clip(lm - cv.poly(tr(h)), 0, 1)
        m = np.maximum(m, lm)
        x += (5 + gap) * unit
    return m, x - gap * unit - x0


def logo_width(text, unit, gap=1.15):
    n = len(text.replace(" ", ""))
    return n * 5 * unit + (n - 1) * gap * unit + text.count(" ") * (2.6 + gap) * unit


def draw_logo(cv, text, cy, unit, stops, glow_col):
    w = logo_width(text, unit) + 7 * 0.22 * unit
    x0 = (cv.w - w) / 2
    m, _ = logo_mask(cv, text, x0, cy - 3.5 * unit, unit)
    # 縁（暗い太線）→ 発光 → 本体のグラデーション → 上の照り
    hard = Image.fromarray((m * 255).astype(np.uint8), "L")
    thick = np.asarray(hard.filter(ImageFilter.MaxFilter(1 + 2 * int(unit * 0.55 * cv.ss) | 1)), np.float32) / 255
    cv.glow(thick, glow_col, unit * 0.9, 0.9)
    cv.fill(thick, (6, 8, 20))
    cv.fill(m, cv.grad((0, cy - 3.5 * unit), (0, cy + 3.5 * unit), None, None, stops))
    top, _ = logo_mask(cv, text, x0, cy - 3.5 * unit - unit * 0.18, unit)
    shine = np.clip(m - top, 0, 1)
    cv.fill(shine, WHITE, 0.0)
    band = cv.poly([(0, cy - 3.5 * unit), (cv.w, cy - 3.5 * unit), (cv.w, cy - 1.9 * unit), (0, cy - 1.4 * unit)])
    cv.fill(m * band, WHITE, 0.35)


def pack_icon():
    S = 256
    cv = Canvas(S, ss=3)
    X, Y = cv.coords()
    # 深宇宙のグラデーション
    sky = _ramp(Y / S, [(0.0, (6, 8, 26)), (0.5, (12, 10, 40)), (1.0, (24, 8, 44))])
    cv.fill(np.ones((cv.H, cv.W), np.float32), sky)
    # 星雲（値ノイズ）
    n1 = fbm3(X / 70, Y / 70, np.full_like(X, 0.3), 301, 5)
    n2 = fbm3(X / 50 + 5, Y / 50, np.full_like(X, 1.7), 302, 4)
    neb = np.clip((n1 - 0.45) * 2.6, 0, 1) ** 1.5
    band = np.exp(-((Y - (0.55 * X + 40)) / 70) ** 2)
    cv.fill(neb * band * 0.75, _ramp(n2, [(0.0, (60, 30, 140)), (0.5, (150, 60, 200)), (1.0, (40, 140, 220))]))
    cv.fill(np.clip((n2 - 0.55) * 3, 0, 1) * band * 0.35, (255, 140, 200))
    rng = np.random.default_rng(42)
    for _ in range(170):
        x, y = rng.uniform(0, S, 2)
        r = rng.choice([0.35, 0.5, 0.7, 1.0], p=[0.45, 0.3, 0.17, 0.08])
        cv.fill(cv.ellipse(x, y, r), (230, 236, 255), rng.uniform(0.35, 1.0))
    for _ in range(7):
        x, y = rng.uniform(10, S - 10), rng.uniform(10, 150)
        r = rng.uniform(3, 6)
        cv.fill(cv.line([(x - r, y), (x + r, y)], 0.5), (220, 230, 255), 0.8)
        cv.fill(cv.line([(x, y - r), (x, y + r)], 0.5), (220, 230, 255), 0.8)
    # 星核の後光とナノマシンの奔流
    cx, cy = 128.0, 96.0
    cv.fill(np.ones((cv.H, cv.W), np.float32), (255, 236, 200),
            np.clip(1 - np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / 90, 0, 1) ** 2.4 * 0.55)
    for i in range(28):
        a = rng.uniform(0, 2 * math.pi)
        r0, r1 = rng.uniform(12, 20), rng.uniform(46, 118)
        col = HUD_COL[KEYS[i % 9]]
        pts = [(cx + math.cos(a + t * 0.25) * (r0 + (r1 - r0) * t), cy + math.sin(a + t * 0.25) * (r0 + (r1 - r0) * t)
                * 0.62) for t in np.linspace(0, 1, 16)]
        ln = cv.line(pts, rng.uniform(0.7, 1.4))
        cv.glow(ln, col, 1.2, 0.5)
        cv.fill(ln, lighten(col, 0.45), rng.uniform(0.45, 0.85))
        for t in np.linspace(0.2, 1.0, 5):
            j = int(t * 15)
            x, y = pts[j]
            sz = rng.uniform(0.8, 1.7)
            cv.fill(cv.poly([(x - sz, y - sz), (x + sz, y - sz), (x + sz, y + sz), (x - sz, y + sz)]),
                    lighten(col, 0.6), rng.uniform(0.5, 1.0))
    # 軌道（傾いた楕円）と惑星
    ocx, ocy, orx, ory, tilt = 128.0, 104.0, 118.0, 46.0, math.radians(-8)

    def opt(th):
        x, y = math.cos(th) * orx, math.sin(th) * ory
        return (ocx + x * math.cos(tilt) - y * math.sin(tilt), ocy + x * math.sin(tilt) + y * math.cos(tilt))
    ring_pts = [opt(t) for t in np.linspace(0, 2 * math.pi, 200)]
    cv.fill(cv.line(ring_pts, 1.2), (150, 220, 255), 0.55)
    cv.fill(cv.line(ring_pts, 0.5), WHITE, 0.6)
    # 星核
    cv.glow(cv.ellipse(cx, cy, 16), (255, 210, 120), 10, 1.0)
    cv.fill(cv.ellipse(cx, cy, 15), cv.radial(cx, cy, 15, [(0.0, (255, 255, 255)), (0.45, (255, 246, 210)),
                                                          (1.0, (255, 196, 90))]))
    for k in range(4):
        a = math.radians(k * 90 + 45)
        L = 40 if k % 2 == 0 else 34
        cv.fill(cv.line([(cx - math.cos(a) * L, cy - math.sin(a) * L), (cx + math.cos(a) * L, cy + math.sin(a) * L)],
                        1.0), (255, 250, 230), 0.5)
    cv.fill(cv.line([(cx - 70, cy), (cx + 70, cy)], 1.4), (255, 250, 230), 0.75)
    cv.fill(cv.line([(cx, cy - 52), (cx, cy + 52)], 1.2), (255, 250, 230), 0.6)
    # 惑星を軌道の上に（奥 → 手前の順）
    order = ["sol", "mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"]
    angs = np.radians(np.linspace(196, 344, 9))
    place = []
    for key, th in zip(order, angs):
        x, y = opt(th)
        depth = (math.sin(th) + 1) / 2
        r = {"sol": 15, "jupiter": 13, "saturn": 10, "uranus": 9, "neptune": 9, "earth": 9, "venus": 8.5,
             "mars": 7.5, "mercury": 6.5}[key] * (0.9 + 0.2 * depth)
        place.append((y, key, x, r))
    # 太陽は左端の奥に大きく
    for y, key, x, r in sorted(place):
        size = int(r * 5.2) + 4
        pl = render_planet(key, size, r, ss=3, detail=1.0)
        cv.paste(soft_outlined(pl, (4, 6, 16), 160), x - size / 2, y - size / 2)
    # 地球のスーツのモデルがあれば、星核の前に兜と胸を置く（無ければ星核だけ）
    geo, tex = suit_paths("earth")
    if os.path.exists(geo) and os.path.exists(tex):
        try:
            bust = render_bust(geo, tex, 92, yaw=-24.0, pitch=-6.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ui: pack_icon のスーツの描画に失敗（{e}）")
            bust = None
        if bust is not None:
            cv.glow(cv.ellipse(cx, cy + 6, 34, 40), (255, 236, 190), 6, 0.55)
            cv.paste(bust, cx - 46, cy - 46)
    # 題字の帯
    cv.fill(np.clip((Y - 150) / 40, 0, 1) * 0.75, (4, 4, 14))
    draw_logo(cv, "ASTRO", 186, 6.2, [(0.0, (255, 255, 255)), (0.45, (200, 244, 255)), (0.55, (110, 210, 255)),
                                       (1.0, (40, 110, 220))], (60, 170, 255))
    draw_logo(cv, "NANOGEAR", 230, 3.6, [(0.0, (255, 252, 226)), (0.45, (255, 224, 120)), (0.55, (255, 176, 50)),
                                          (1.0, (220, 96, 20))], (255, 150, 40))
    # 区切りの細い線
    cv.fill(cv.line([(30, 210.5), (226, 210.5)], 0.8), (150, 220, 255), 0.6)
    cv.fill(cv.poly([(128, 207), (131.5, 210.5), (128, 214), (124.5, 210.5)]), (220, 246, 255))
    out = cv.result()
    out[..., 3] = 255
    return out


# ===========================================================================
#  glyphs.js
# ===========================================================================
G_ORDER = ["emblem", "emblemBig", "energy", "energyLow", "nova", "move", "icon", "iconBig", "sync", "progress",
           "xp", "banner"]


def _js_str(ch):
    return '"' + "".join(f"\\u{ord(c):04X}" for c in ch) + '"'


def _js_obj(v, ind=1):
    pad = "  " * ind
    if isinstance(v, str):
        return _js_str(v)
    flat = all(isinstance(x, str) for x in v.values())
    if flat:
        return "{ " + ", ".join(f"{k}: {_js_str(x)}" for k, x in v.items()) + " }"
    inner = ",\n".join(f"{pad}  {k}: {_js_obj(x, ind + 1)}" for k, x in v.items())
    return "{\n" + inner + f",\n{pad}}}"


def write_glyphs_js(G, pages):
    widths = {}
    for pg in pages:
        for idx, m in sorted(pg.meta.items()):
            x0, x1 = m["span"]
            widths[chr(pg.cp(idx))] = round((x1 - x0) * 16 / pg.cell)
    body = ",\n".join(f"  {k}: {_js_obj(G[k], 1)}" for k in G_ORDER)
    wlist = ", ".join(f"[{_js_str(ch)}, {w}]" for ch, w in widths.items())
    js = f"""// 自動生成（tools/astro/gen_astro_ui.py）。手で編集しない。説明は tools/astro/UI.md
// HUD のグリフ: RP の font/glyph_EA.png（U+EA00–EAFF、16 px セル = 約 16 GUI px）と
//               font/glyph_EB.png（U+EB00–EBFF、32 px セル、タイトル・カットイン用）。
// § の色コードはグリフを染めない（惑星ごとに色違いのグリフがある）。グリフの前は §r、§l（太字）を隣に置かない。

export const GLYPH_PAGES = {{ hud: "EA", art: "EB" }};

export const G = {{
{body},
}};

/** 各グリフの送り幅（GUI px。実際にはこの後に約 1 px の隙間が入る）。 */
export const WIDTH = new Map([{wlist}]);

const clamp01 = (v) => Math.max(0, Math.min(1, Number(v) || 0));

/**
 * セルを並べたバー。set = {{full, half?, empty, capL?, capR?}}（G.energy[key] / G.energyLow / G.nova /
 * G.progress / G.sync）。frac = 0..1、cells = セル数。half があれば半セル単位で丸める。
 * 0 より大きければ最低でも半セル（half が無ければ 1 セル）、1 未満なら最後のセルは満たさない。
 * caps = false で両端を付けない。
 */
export function bar(set, frac, cells, caps = true) {{
  const f = clamp01(frac);
  const step = set.half ? 0.5 : 1;
  let units = Math.round((f * cells) / step) * step;
  if (f > 0 && units <= 0) units = step;
  if (f < 1 && units >= cells) units = cells - step;
  let s = caps && set.capL ? set.capL : "";
  for (let i = 0; i < cells; i++) {{
    s += units >= i + 1 ? set.full : units >= i + 0.5 && set.half ? set.half : set.empty;
  }}
  return s + (caps && set.capR ? set.capR : "");
}}

/** 星力バー（惑星色。frac < 0.2 で赤と惑星色が 8 tick ごとに入れ替わって点滅）。tick = system.currentTick。 */
export function energyBar(key, frac, cells = 16, tick = 0) {{
  const low = clamp01(frac) < 0.2 && Math.floor(tick / 8) % 2 === 0;
  return bar(low ? G.energyLow : G.energy[key] ?? G.energy.mercury, frac, cells);
}}

/** 超新星バー。満タンの時は白熱のセル 3 つが左から右へ流れる（4 tick で 1 セル進む）。 */
export function novaBar(frac, cells = 10, tick = 0) {{
  if (clamp01(frac) < 1) return bar(G.nova, frac, cells);
  const head = Math.floor(tick / 4) % (cells + 4);
  let s = G.nova.capL;
  for (let i = 0; i < cells; i++) {{
    const d = head - i;
    s += d >= 0 && d < 3 ? G.nova.flow : G.nova.full;
  }}
  return s + G.nova.capR;
}}

/** 変身・解除の進み具合（CORE SYNC n%）。 */
export function progressBar(frac, cells = 20) {{
  return bar(G.progress, frac, cells);
}}

/** 同調率の XP（次の Lv までの割合。細い紫のバー）。 */
export function xpBar(frac, cells = 10) {{
  return bar(G.xp, frac, cells);
}}

/** 同調率 Lv の粒（◆◆◆◇◇）。 */
export function pips(n, max = 5) {{
  const k = Math.max(0, Math.min(max, n | 0));
  return G.icon.pipOn.repeat(k) + G.icon.pipOff.repeat(max - k);
}}

/** 技アイコン。ready = 使える（明るい枠）／ false = 待ち（灰色に惑星色の芯）。 */
export function moveIcon(key, kind, ready) {{
  const m = (G.move[key] ?? G.move.mercury)[kind] ?? G.move.mercury.skill;
  return ready ? m.ready : m.wait;
}}

/** グリフと ASCII の幅（GUI px）の目安。日本語は 1 字 9 px として数える。 */
export function textWidth(str) {{
  let w = 0;
  const s = String(str).replace(/§./g, "");
  for (const ch of s) {{
    const g = WIDTH.get(ch);
    if (g !== undefined) w += g + 1;
    else if (ch === " ") w += 4;
    else if (ch.charCodeAt(0) < 128) w += "il.,:;!'|".includes(ch) ? 2 : "It[]".includes(ch) ? 4 : 6;
    else w += 9;
  }}
  return w;
}}
"""
    os.makedirs(os.path.dirname(GLYPHS_JS), exist_ok=True)
    with open(GLYPHS_JS, "w", encoding="utf-8") as fh:
        fh.write(js)
    return GLYPHS_JS


# ===========================================================================
#  UI.md（グリフの一覧と HUD の組み方）
# ===========================================================================
def _g_shape(G):
    """G のキー構造を 1 行ずつの文字列に。"""
    def keys(v):
        return "{" + ", ".join(v.keys()) + "}"
    k0 = KEYS[0]
    return [
        f"emblem:    {{<key>: 文字}}                       （惑星 9 つ: {', '.join(KEYS)}）",
        "emblemBig: {<key>: 文字}",
        f"energy:    {{<key>: {keys(G['energy'][k0])}, low: {keys(G['energy']['low'])}}}",
        f"energyLow: {keys(G['energyLow'])}",
        f"nova:      {keys(G['nova'])}",
        f"move:      {{<key>: {{<kind>: {keys(G['move'][k0]['skill'])}}}}}   kind = {', '.join(KINDS)}",
        f"icon:      {keys(G['icon'])}",
        f"iconBig:   {keys(G['iconBig'])}",
        f"sync:      {keys(G['sync'])}",
        f"progress:  {keys(G['progress'])}",
        f"xp:        {keys(G['xp'])}",
        f"banner:    {keys(G['banner'])}",
    ]


def write_ui_md(G, pages, widths_note):
    hud, art = pages
    lines = []
    w = lines.append
    w("# アストロ・ナノギア — HUD グリフと UI 素材")
    w("")
    w("`tools/astro/gen_astro_ui.py` が書き出す（この文書も自動生成。直すときは生成スクリプトの `write_ui_md` を直す）。")
    w("見本: `docs/astro/hud.png`（HUD・カットイン・ターミナルの見本）、`build_preview/astro/glyphs_EA.png` / "
      "`glyphs_EB.png`（全セルを 4 倍・2 倍にして番号を付けたもの。桃色の線 = 送り幅、緑の印 = 文字の高さ 4〜11 行）。")
    w("")
    w("## 1. 統合版のグリフの規則（このアドオンで守っていること）")
    w("")
    w("* `U+XXRC` → `RP/font/glyph_XX.png` の R 行 C 列（16×16 マス）。**EA = HUD（256×256、16 px セル）**、"
      "**EB = 大きな絵（512×512、32 px セル）**。E0/E1（バニラ）・E2/E3（他パックと衝突しやすい）・2E–9F と F9–FF"
      "（日本語・繁体字ロケールのページ）は使わない。")
    w("* 送り幅 = セルの不透明な列の範囲（空の列は詰められる）＋約 1 GUI px の隙間。負の字間は無い。"
      "幅を決めたいグリフは両端の列にかすかな画素（アルファ 20）を置いてある（下の表の「幅」）。")
    w("* 16 px セルはほぼ 16 GUI px（ASCII の約 2 倍の高さの箱）で描かれる。絵は文字の高さ（4〜11 行）に置き、"
      "技アイコンと紋章でも 3〜12 行に収めた（2 行のアクションバーで上下の行に被らない）。")
    w("* 512 のページ（EB）は 16 px と同じ大きさで細かく描かれる（たぶん）か、2 倍の大きさ（不確か）。"
      "どちらでも崩れないように EB はタイトル・サブタイトル専用にしている（HUD の行には入れない）。")
    w("* **§ の色はグリフを染めない** → 惑星ごとに色違いのグリフを用意した。§ の色はグリフの後ろの文字にだけ効く。")
    w("* **グリフの並びの前に `§r`** を置く（太字・斜体が残っていると崩れる）。**`§l`（太字）をグリフの隣に置かない**"
      "（太字はグリフをずらして二重に描く）。")
    w("* アクションバーは表示が数秒で消えるので **40 tick 以内ごとに送り直す**（HUD は 4 tick ごとなので問題ない）。"
      "各行は中央揃え。行の間は約 10 GUI px。空白は 4 GUI px。")
    w("* グリフはアクションバー・タイトル／サブタイトル・チャット・アイテム名／説明・server-ui のフォーム・"
      "エンティティの nameTag で描かれる。")
    w("")
    w("## 2. `glyphs.js` の形")
    w("")
    w("```js")
    w('import { G, bar, energyBar, novaBar, progressBar, xpBar, pips, moveIcon, textWidth, WIDTH } from "./glyphs.js";')
    w("```")
    w("")
    w("```")
    for ln in _g_shape(G):
        w("G." + ln)
    w("```")
    w("")
    w("* `G.energy[key].capL/capR` は全惑星で同じ金属の端。`G.energy.low` = `G.energyLow`（星力 20% 未満の赤いセルと赤い LED の端）。")
    w("* `G.sync` = `G.progress`（同じグリフ）= 変身・解除の進み具合（CORE SYNC n%）の白いバー（half あり）。"
      "`G.xp` = 同調率の XP の細い紫のバー。")
    w("* `G.icon.sep` は斜めの区切り（│ の代わり）、`G.icon.arrow` はメニュー用の小さな ▶。")
    w("* `G.banner.wingL/wingR`（翼）・`divider`（中央にひし形の線）・`lineL/lineR`（文字を挟む線）と `G.emblemBig`・"
      "`G.iconBig` は EB（タイトル用）。")
    w("")
    w("関数:")
    w("")
    w("| 関数 | 中身 |")
    w("|---|---|")
    w("| `bar(set, frac, cells, caps = true)` | `capL + セル×cells + capR`。`set.half` があれば半セル単位。0 < frac なら最低半セル、frac < 1 なら最後のセルは空ける |")
    w("| `energyBar(key, frac, cells = 16, tick)` | 星力。frac < 0.2 で `G.energyLow`（赤）と惑星色が 8 tick ごとに点滅 |")
    w("| `novaBar(frac, cells = 10, tick)` | 超新星。100% で白熱のセル 3 つが流れる（4 tick で 1 セル） |")
    w("| `progressBar(frac, cells = 20)` / `xpBar(frac, cells = 10)` | 進捗（G.progress = G.sync）・同調率の XP（G.xp） |")
    w("| `pips(n, max = 5)` | 同調率 Lv の粒 ◆◆◆◇◇ |")
    w("| `moveIcon(key, kind, ready)` | 技アイコン（ready = 明るい枠、false = 灰色に惑星色の芯） |")
    w("| `textWidth(str)` | GUI px の幅の目安（グリフは表の幅＋1、ASCII 約 6、日本語 9、空白 4） |")
    w("")
    w("## 3. HUD の組み方（アクションバー 2 行）")
    w("")
    w("```js")
    w("const pl = PLANETS[key];                       // data.js")
    w("const t = system.currentTick;")
    w("const line1 = `§r${G.emblem[key]} ${pl.tc}${pl.form_ja} §fLv${lv} ${G.icon.sep} ` +")
    w("  `${G.icon.energy}${energyBar(key, st.energy / maxE, 16, t)} §f${Math.floor(st.energy)} ${G.icon.sep} ` +")
    w("  `${G.icon.nova}${novaBar(st.nova / 100, 10, t)} ${st.nova >= 100 ? \"§e\" : \"§7\"}${Math.floor(st.nova)}%`;")
    w("")
    w("// 技: アイコン + 再使用の残り秒 / ✔ / READY（間は空白 2 つ）")
    w("const cell = (kind) => {")
    w("  const left = cdLeft(kind);                   // tick")
    w('  const ok = left <= 0 && (kind !== "ult" || st.nova >= 100);')
    w('  const tail = left > 0 ? `§7${(left / 20).toFixed(1)}s` : kind === "ult" ? (ok ? "§6READY" : `§7${Math.floor(st.nova)}%`) : `${G.icon.check}`;')
    w("  return `${moveIcon(key, kind, ok)} ${tail}`;")
    w("};")
    w('const line2 = `§r${cell("skill")}  ${cell("dash")}  ${cell("air")}  ${cell("ult")}`;')
    w('p.onScreenDisplay.setActionBar(`${line1}\\n${line2}`);')
    w("```")
    w("")
    w("2 行目の差し替え（優先順に 1 つ）:")
    w("")
    w("| 状態 | 2 行目 |")
    w("|---|---|")
    w("| 解除の長押し中 | `` `§r${G.icon.revert} §cREVERT ${progressBar(hold / 40)} §f${pct}%` `` |")
    w("| オーバーヒート中 | `` `§r${G.icon.overheat} §cOVERHEAT §f${sec}s ${G.icon.lock}` ``（変身していない時は 1 行目の代わりに） |")
    w("| ナノ・バリア中 | `` `§r${G.icon.barrier} §bNANO BARRIER ${bar(G.progress, left / 14, 10)}` `` |")
    w("| 溜め中 | `` `§r${G.icon.energy} §eCHARGE ${progressBar(c)} §f${pct}%` `` |")
    w("| 星力 20% 未満 | 1 行目の数字の後に `` ` ${G.icon.warn}` `` |")
    w("")
    w("同調率の表示（ターミナルやチャット）: `` `${G.icon.sync} §dSYNC Lv${lv} ${pips(lv)} ${xpBar(xpFrac)}` ``。")
    w("")
    w(f"幅の目安（見本の行を実測）: {widths_note}。GUI の幅は 1080p・GUI 倍率 3 で約 640 px、スマホでは 400〜480 px 程度なので"
      "1 行目は 16 + 10 セルで収まる。狭い端末向けに設定で 12 + 8 セルへ減らせるようにしておくとよい。")
    w("")
    w("## 4. タイトル・カットイン（EB）")
    w("")
    w("```js")
    w("// 変身の進捗（TRANSFORM の各段で）")
    w('p.onScreenDisplay.setTitle(`§fCORE SYNC §b${pct}%`, { subtitle: `§r${progressBar(pct / 100, 20)}`,')
    w("  fadeInDuration: 0, stayDuration: 12, fadeOutDuration: 4 });")
    w("// 締め（planet_burst）: 翼＋大きな紋章、サブタイトルに形態名")
    w("p.onScreenDisplay.setTitle(`§r${G.banner.wingL}${G.emblemBig[key]}${G.banner.wingR}`, {")
    w("  subtitle: `§r${G.banner.lineL} ${pl.tc}${pl.form_ja} §7| ${pl.tc}${pl.form_en} §r${G.banner.lineR}`,")
    w("  fadeInDuration: 2, stayDuration: 30, fadeOutDuration: 10 });")
    w("// 必殺技のカットイン")
    w("p.onScreenDisplay.setTitle(`§r${G.iconBig.nova}`, { subtitle: `§r${G.banner.divider} §6${pl.moves.ult.ja} §r${G.banner.divider}`,")
    w("  fadeInDuration: 0, stayDuration: 24, fadeOutDuration: 6 });")
    w("// 警告（オーバーヒート）")
    w("p.onScreenDisplay.setTitle(`§r${G.iconBig.overheat}`, { subtitle: \"§cOVERHEAT\", stayDuration: 30 });")
    w("```")
    w("")
    w("## 5. フォーム（server-ui）の素材")
    w("")
    w("| パス | 大きさ | 用途 |")
    w("|---|---|---|")
    w("| `textures/ui/astro/emblem_<key>` | 128×128 | 惑星図鑑のボタン（機械の輪の枠に惑星。背景は透明） |")
    w("| `textures/ui/astro/{status,codex,revert,settings,guide,records,back}` | 64×64 | トップのボタン（状態・惑星図鑑・解除・設定・操作説明・記録・戻る） |")
    w("| `textures/items/astro/{nano_cell,core_frame,solar_fragment,terminal,void_signal}` | 64×64 | 素材・道具のアイコン |")
    w("| `textures/items/astro/suit_<key>` | 64×64 | スーツのアイコン（スーツのモデルがあれば兜と胸を描き、無ければ紋章付きの兜の絵） |")
    w("")
    w("ボタン: `form.button(`${pl.tc}${pl.form_ja}\\n§8${pl.ja}`, `textures/ui/astro/emblem_${key}`)`。"
      "ボタンの文字にもグリフを使える（例: `` `${G.emblem[key]} ${pl.form_ja}` ``、`` `${G.icon.lock} §8???` `` = 未入手）。")
    w("")
    w("## 6. グリフの一覧")
    w("")
    for pg, title in ((hud, "glyph_EA（HUD、16 px セル）"), (art, "glyph_EB（大きな絵、32 px セル）")):
        w(f"### {title}")
        w("")
        w("| 番号 | G のキー | 幅 (GUI px) | 行 |")
        w("|---|---|---|---|")
        for idx, m in sorted(pg.meta.items()):
            x0, x1 = m["span"]
            width = round((x1 - x0) * 16 / pg.cell)
            r = m["rows"]
            rows = f"{r[0]}–{r[1]}" if r else "-"
            nm = m["name"].split("（")[0].split(" = ")
            label = " = ".join(f"`G.{x}`" for x in nm) + ("（全惑星共通）" if "（" in m["name"] else "")
            w(f"| U+{pg.cp(idx):04X} | {label} | {width} | {rows} |")
        w("")
    w("配置: EA の行 0 = バーの部品、行 1〜9 = 惑星（order 順）で 列 0 紋章 / 1〜3 星力 満・半・空 / 4〜7 技（使える: "
      "skill, dash, air, ult）/ 8〜B 技（待ち）、行 A = 赤い星力、行 B = 状態アイコン。EB の行 0 = 大きな紋章、行 1 = 飾り、"
      "行 2 = 大きなアイコン。空いているセルは将来用。")
    w("")
    w("## 7. 確かめていないこと")
    w("")
    w("* 実機の行間（見本は 10 GUI px で描いた）と、アクションバーの背景の濃さ。グリフに文字の影が付くか。")
    w("* EB（512×512）の表示の大きさ（16 px 相当か 32 px 相当か）。")
    w("* かすかな画素（アルファ 20）が明るい空の上でうっすら見えるか（見えても 1 画素の暗い点）。")
    with open(UI_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return UI_MD


# ===========================================================================
#  docs/astro/hud.png: 画面の見本（ゲーム画面・アクションバー 2 行・タイトルのカットイン・ターミナル）
#  S = 2（1 GUI px = 2 画素）で描き、最後に 2 倍に拡大する
# ===========================================================================
MS = 2


def _block_scene(W, H, seed=3, planet=True):
    """ゲーム画面らしい背景（夜明け前の空・星・ブロックの丘・木）。GUI px 単位で描いて MS 倍。"""
    rng = np.random.default_rng(seed)
    a = np.zeros((H, W, 4), np.float32)
    y = np.arange(H)[:, None] / H
    a[..., :3] = _ramp(np.broadcast_to(y, (H, W)), [(0.0, (12, 16, 46)), (0.45, (40, 40, 96)), (0.62, (120, 86, 130)),
                                                    (0.70, (230, 150, 120)), (1.0, (230, 150, 120))])
    a[..., 3] = 255
    for _ in range(140):
        sx, sy = int(rng.uniform(0, W)), int(rng.uniform(0, H * 0.5))
        a[sy, sx, :3] = (230, 230, 255)
    # 大きな惑星（空に浮かぶ）
    if planet:
        pl = render_planet("saturn", 70, 16, ss=3)
        over(a, pl * np.array([1, 1, 1, 0.85], np.float32), int(W * 0.72), int(H * 0.08))
    # 遠い丘（ブロック）
    def hills(base, amp, blk, col, top, seed):
        r = np.random.default_rng(seed)
        h = base
        for x0 in range(0, W, blk):
            h = int(np.clip(h + r.integers(-1, 2) * blk // 2, base - amp, base + amp))
            a[h:, x0:x0 + blk, :3] = col
            a[h:h + max(1, blk // 3), x0:x0 + blk, :3] = top
            for yy in range(h, H, blk):
                a[yy, x0:x0 + blk, :3] = np.array(col) * 0.85
                a[yy:yy + blk, x0, :3] = np.array(col) * 0.85
    hills(int(H * 0.64), 8, 6, (52, 50, 78), (70, 74, 100), seed)
    hills(int(H * 0.74), 10, 12, (58, 48, 40), (64, 112, 56), seed + 1)
    # 木
    for tx in (int(W * 0.12), int(W * 0.86)):
        ty = int(H * 0.60)
        a[ty:ty + 34, tx:tx + 6, :3] = (70, 52, 34)
        a[ty - 18:ty + 6, tx - 12:tx + 18, :3] = (36, 76, 40)
        a[ty - 18:ty - 14, tx - 12:tx + 18, :3] = (50, 100, 52)
    a[int(H * 0.86):, :, :3] *= 0.85
    return a


def _hotbar(a, W, H, weapon_icon=None):
    """ホットバー・ハート・満腹・経験値（GUI px）。"""
    x0, y0 = (W - 182) // 2, H - 22
    a[y0:y0 + 22, x0:x0 + 182, :3] = a[y0:y0 + 22, x0:x0 + 182, :3] * 0.35 + 18
    for i in range(9):
        sx = x0 + 1 + i * 20
        a[y0 + 1:y0 + 21, sx:sx + 20, :3] = (60, 60, 64)
        a[y0 + 2:y0 + 20, sx + 1:sx + 19, :3] = (34, 34, 38)
    sel = x0 + 1
    for t in range(2):
        a[y0 - 1 + t, sel - 1:sel + 21, :3] = 230
        a[y0 + 21 - t, sel - 1:sel + 21, :3] = 230
        a[y0 - 1:y0 + 22, sel - 1 + t, :3] = 230
        a[y0 - 1:y0 + 22, sel + 20 - t, :3] = 230
    if weapon_icon is not None:
        ic = np.asarray(Image.fromarray(np.clip(weapon_icon, 0, 255).astype(np.uint8)).resize((16, 16),
                                                                                              Image.LANCZOS),
                        np.float32)
        over(a, ic, sel + 2, y0 + 3)
    # 経験値と体力・満腹
    a[y0 - 7:y0 - 4, x0:x0 + 182, :3] = (20, 30, 20)
    a[y0 - 6:y0 - 5, x0 + 1:x0 + 120, :3] = (128, 255, 32)
    heart = ["X.X", "XXX", ".X."]
    for i in range(10):
        hx, hy = x0 + i * 8, y0 - 16
        for r, row in enumerate(heart):
            for c_, v in enumerate(row):
                if v == "X":
                    a[hy + r * 2:hy + r * 2 + 2, hx + c_ * 2:hx + c_ * 2 + 2, :3] = (220, 30, 40)
        hx2 = x0 + 182 - 8 - i * 8
        a[hy:hy + 6, hx2 + 1:hx2 + 6, :3] = (170, 110, 60)
        a[hy + 1:hy + 3, hx2 + 2:hx2 + 4, :3] = (230, 180, 120)
    # 照準
    cx, cy = W // 2, H // 2
    a[cy - 4:cy + 5, cx, :3] = 235
    a[cy, cx - 4:cx + 5, :3] = 235


def _draw_lines(canvas, lines, cx_gui, top_gui, glyphs, title=1, pitch=10, bg=True):
    """中央揃えの複数行を canvas（MS 倍の画素）へ。戻り値: 各行の幅（GUI px）。"""
    widths = []
    for i, ln in enumerate(lines):
        img, w = compose_line(ln, glyphs, S=MS, title=title)
        widths.append(w)
        x = int(round(cx_gui * MS - img.shape[1] / 2))
        y = int(round((top_gui + i * pitch * title) * MS))
        if bg:
            pad = 2 * MS
            y0, y1 = y + 3 * MS * title, y + 13 * MS * title
            box = canvas[y0:y1, max(0, x - pad):x + img.shape[1] + pad]
            box[..., :3] *= 0.62
        over(canvas, img, x, y)
    return widths


def hud_mock(pg, pg2, G):
    from_hud = Glyphs(pg, pg2)
    key, t = "earth", 6
    pl = D.PLANETS[key]
    sys.path.insert(0, HERE)
    W, H = 480, 270
    scene = _block_scene(W, H)
    wpath = os.path.join(ITEM_DIR, f"weapon_{key}.png")
    wicon = np.asarray(Image.open(wpath).convert("RGBA"), np.float32) if os.path.exists(wpath) else None
    _hotbar(scene, W, H, wicon)
    screen = np.asarray(Image.fromarray(scene.astype(np.uint8)).resize((W * MS, H * MS), Image.NEAREST),
                        np.float32).copy()
    J = js_helpers(G)
    tc = pl["tc"]
    line1 = (f"§r{G['emblem'][key]} {tc}{pl['form_ja']} §fLv3 {G['icon']['sep']} {G['icon']['energy']}"
             f"{J.energy_bar(key, 0.72, 16, t)} §f86 {G['icon']['sep']} {G['icon']['nova']}{J.nova_bar(0.64, 10, t)} §764%")
    line2 = (f"§r{J.move(key, 'skill', False)} §73.4s  {J.move(key, 'dash', True)} {G['icon']['check']}  "
             f"{J.move(key, 'air', True)} {G['icon']['check']}  {J.move(key, 'ult', False)} §764%")
    widths = _draw_lines(screen, [line1, line2], W / 2, H - 68, from_hud)
    # タイトル（変身の締め）
    title = f"§r{G['banner']['wingL']}{G['emblemBig'][key]}{G['banner']['wingR']}"
    sub = f"§r{G['banner']['lineL']} {tc}{pl['form_ja']} §7| {tc}{pl['form_en']} §r{G['banner']['lineR']}"
    _draw_lines(screen, [title], W / 2, 52, from_hud, title=2, bg=False)
    _draw_lines(screen, [sub], W / 2, 92, from_hud, title=1, bg=False)
    panels = [("ゲーム画面（地球 ガイア・変身中）: タイトル = 変身の締め、アクションバー 2 行", screen)]

    # --- 状態の差し替えの見本 ---
    rows = []
    variants = [
        ("通常", line1, line2),
        ("星力 20% 未満（点滅）", (f"§r{G['emblem']['mars']} §cアレス §fLv2 {G['icon']['sep']} {G['icon']['energy']}"
                             f"{J.energy_bar('mars', 0.15, 16, 0)} §c15 {G['icon']['warn']} {G['icon']['sep']} "
                             f"{G['icon']['nova']}{J.nova_bar(1.0, 10, 9)} §e100%"),
         f"§r{J.move('mars', 'skill', True)} {G['icon']['check']}  {J.move('mars', 'dash', False)} §71.2s  "
         f"{J.move('mars', 'air', True)} {G['icon']['check']}  {J.move('mars', 'ult', True)} §6READY"),
        ("解除の長押し", (f"§r{G['emblem']['neptune']} §9トリトン §fLv4 {G['icon']['sep']} {G['icon']['energy']}"
                       f"{J.energy_bar('neptune', 0.48, 16, 0)} §f53 {G['icon']['sep']} {G['icon']['nova']}"
                       f"{J.nova_bar(0.3, 10, 0)} §730%"),
         f"§r{G['icon']['revert']} §cREVERT {J.bar(G['progress'], 0.55, 20)} §f55%"),
        ("ナノ・バリア", (f"§r{G['emblem']['saturn']} §hクロノス §fLv1 {G['icon']['sep']} {G['icon']['energy']}"
                       f"{J.energy_bar('saturn', 0.9, 16, 0)} §f90 {G['icon']['sep']} {G['icon']['nova']}"
                       f"{J.nova_bar(0.82, 10, 0)} §782%"),
         f"§r{G['icon']['barrier']} §bNANO BARRIER {J.bar(G['progress'], 0.6, 10)}"),
        ("オーバーヒート（変身していない）", f"§r{G['icon']['overheat']} §cOVERHEAT §f12s {G['icon']['lock']}",
         f"§r{G['icon']['sync']} §dSYNC Lv3 {J.pips(3)} {J.bar(G['xp'], 0.4, 10)}"),
    ]
    for k2 in KEYS:
        variants.append((D.PLANETS[k2]["ja"], (f"§r{G['emblem'][k2]} {D.PLANETS[k2]['tc']}{D.PLANETS[k2]['form_ja']} "
                                              f"§fLv5 {G['icon']['sep']} {G['icon']['energy']}"
                                              f"{J.energy_bar(k2, 0.66, 16, 0)} §f66"),
                         " ".join(f"{J.move(k2, kd, True)}" for kd in KINDS) + "  " +
                         " ".join(f"{J.move(k2, kd, False)}" for kd in KINDS)))
    VW = 480
    vh = 26 * len(variants) + 6
    strip = np.zeros((vh * MS, VW * MS, 4), np.float32)
    strip[..., :3] = (22, 24, 34)
    strip[..., 3] = 255
    for i, (lab, a1, a2) in enumerate(variants):
        y = 4 + i * 26
        if i % 2:
            strip[y * MS:(y + 26) * MS, :, :3] = (28, 30, 42)
        lab_img, _ = compose_line(f"§7{lab}", from_hud, S=MS)
        over(strip, lab_img, 4 * MS, (y + 6) * MS)
        _draw_lines(strip, [a1, a2], 300, y - 2, from_hud)
    panels.append(("状態ごとの 2 行目の差し替えと 9 惑星の色（技アイコン: 使える / 待ち）", strip))

    # --- タイトル・カットイン ---
    TW, TH = 480, 150
    tpan = _block_scene(TW, TH, seed=9, planet=False)
    tpan[..., :3] *= 0.55
    tpan = np.asarray(Image.fromarray(tpan.astype(np.uint8)).resize((TW * MS, TH * MS), Image.NEAREST),
                      np.float32).copy()
    _draw_lines(tpan, ["§fCORE SYNC §b50%"], TW * 0.25, 10, from_hud, title=2, bg=False)
    _draw_lines(tpan, [f"§r{J.bar(G['progress'], 0.5, 20)}"], TW * 0.25, 48, from_hud, bg=False)
    _draw_lines(tpan, [f"§r{G['iconBig']['nova']}"], TW * 0.75, 2, from_hud, title=2, bg=False)
    _draw_lines(tpan, [f"§r{G['banner']['divider']} §6{pl['moves']['ult']['ja']} §r{G['banner']['divider']}"],
                TW * 0.75, 44, from_hud, bg=False)
    big = "".join(G["emblemBig"][k2] for k2 in KEYS)
    _draw_lines(tpan, [f"§r{big}"], TW / 2, 66, from_hud, title=1, bg=False)
    icons = "".join(G["iconBig"][n] for n in G["iconBig"])
    _draw_lines(tpan, [f"§r{G['banner']['wingL']}{icons}{G['banner']['wingR']}"], TW / 2, 90, from_hud, bg=False)
    _draw_lines(tpan, [f"§r{G['banner']['wingL']}{G['emblemBig']['sol']}{G['banner']['wingR']}"], TW / 2, 104,
                from_hud, title=2, bg=False)
    panels.append(("タイトル: CORE SYNC（左）・必殺技（右）・EB の全部（中、16 px 相当）・太陽の締め（下、2 倍）", tpan))

    # --- ターミナル（server-ui のフォーム） ---
    panels.append(("星核ターミナル（server-ui）: トップと惑星図鑑", terminal_mock(G, from_hud)))
    # 縦に積んで 2 倍に
    lab_h = 14 * MS
    Wp = max(p_[1].shape[1] for p_ in panels)
    Ht = sum(p_[1].shape[0] + lab_h + 4 * MS for p_ in panels)
    out = np.zeros((Ht, Wp, 4), np.float32)
    out[..., :3] = (12, 13, 18)
    out[..., 3] = 255
    y = 0
    for lab, img in panels:
        li, _ = compose_line(f"§f{lab}", from_hud, S=MS)
        over(out, li, 2 * MS, y - 2 * MS)
        y += lab_h
        over(out, img, (Wp - img.shape[1]) // 2, y)
        y += img.shape[0] + 4 * MS
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert("RGB")
    im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    return im, widths


def terminal_mock(G, glyphs):
    """server-ui の ActionForm に似せた見本（GUI px で 2 枚並べる）。"""
    W, H = 480, 300
    a = _block_scene(W, H, seed=21)
    a[..., :3] *= 0.4
    a = np.asarray(Image.fromarray(a.astype(np.uint8)).resize((W * MS, H * MS), Image.NEAREST), np.float32).copy()

    def form(x0, title, body, buttons):
        fw, fh = 220, 286
        X0, Y0 = x0 * MS, 6 * MS
        a[Y0:Y0 + fh * MS, X0:X0 + fw * MS, :3] = (49, 50, 56)
        a[Y0:Y0 + 18 * MS, X0:X0 + fw * MS, :3] = (30, 31, 36)
        a[Y0 + fh * MS - MS:Y0 + fh * MS, X0:X0 + fw * MS, :3] = (20, 20, 24)
        _draw_lines(a, [title], x0 + fw / 2, 7, glyphs, bg=False)
        yy = 26
        for ln in body:
            img, _ = compose_line(ln, glyphs, S=MS)
            over(a, img, X0 + 6 * MS, (yy - 3) * MS)
            yy += 11
        yy += 3
        for icon, text in buttons:
            bh = 30
            by = yy * MS
            a[by:by + bh * MS, X0 + 4 * MS:X0 + (fw - 4) * MS, :3] = (88, 90, 98)
            a[by:by + MS, X0 + 4 * MS:X0 + (fw - 4) * MS, :3] = (120, 122, 132)
            a[by + (bh - 1) * MS:by + bh * MS, X0 + 4 * MS:X0 + (fw - 4) * MS, :3] = (40, 40, 46)
            if icon is not None:
                ic = Image.fromarray(np.clip(icon, 0, 255).astype(np.uint8), "RGBA").resize((26 * MS, 26 * MS),
                                                                                        Image.LANCZOS)
                over(a, np.asarray(ic, np.float32), X0 + 7 * MS, by + 2 * MS)
            for j, tl in enumerate(text.split("\n")):
                img, _ = compose_line(tl, glyphs, S=MS)
                ty = by + (bh // 2 - 8 - (5 if "\n" in text else 0) + j * 10) * MS
                over(a, img, X0 + int((fw / 2 + 12) * MS - img.shape[1] / 2), ty)
            yy += bh + 2
        return yy

    J = js_helpers(G)
    menu = {n: np.asarray(Image.open(os.path.join(UI_DIR, f"{n}.png")).convert("RGBA"), np.float32)
            for n in MENU_ACCENT}
    pl = D.PLANETS["earth"]
    form(8, "§f星核ターミナル", [
        f"§r{G['emblem']['earth']} §a{pl['form_ja']} §7変身中",
        f"§r{G['icon']['energy']}{J.energy_bar('earth', 0.72, 16, 0)} §f72",
        f"§r{G['icon']['nova']}{J.nova_bar(0.64, 10, 0)} §764%",
        f"§r{G['icon']['sync']} §dLv3 {J.pips(3)} {J.bar(G['xp'], 0.4, 10)}",
    ], [(menu["codex"], "§0惑星図鑑"), (menu["revert"], "§4変身解除"), (menu["settings"], "§0設定"),
        (menu["guide"], "§0操作説明"), (menu["records"], "§0記録")])
    emb = {k: np.asarray(Image.open(os.path.join(UI_DIR, f"emblem_{k}.png")).convert("RGBA"), np.float32)
           for k in KEYS}
    btns = []
    for k in KEYS[:7]:
        p_ = D.PLANETS[k]
        locked = k in ("uranus",)
        txt = (f"§0{p_['form_ja']}\n§8{p_['ja']} {p_['en']}" if not locked else
               f"§r{G['icon']['lock']} §8???\n§8{p_['ja']}")
        btns.append((emb[k], txt))
    form(252, "§f惑星図鑑", [f"§r{G['icon']['arrow']} §7形態を選ぶ（9）"], btns + [(menu["back"], "§0戻る")][:1])
    return a


class js_helpers:
    """glyphs.js の関数と同じ規則（見本と検査に使う）。"""

    def __init__(self, G):
        self.G = G

    def bar(self, st, frac, cells, caps=True):
        f = max(0.0, min(1.0, frac))
        step = 0.5 if "half" in st else 1.0
        units = round(f * cells / step) * step
        if f > 0 and units <= 0:
            units = step
        if f < 1 and units >= cells:
            units = cells - step
        s_ = st.get("capL", "") if caps else ""
        for i in range(cells):
            s_ += st["full"] if units >= i + 1 else (st["half"] if units >= i + 0.5 and "half" in st else st["empty"])
        return s_ + (st.get("capR", "") if caps else "")

    def energy_bar(self, key, frac, cells=16, tick=0):
        low = frac < 0.2 and (tick // 8) % 2 == 0
        return self.bar(self.G["energyLow"] if low else self.G["energy"][key], frac, cells)

    def nova_bar(self, frac, cells=10, tick=0):
        if frac < 1:
            return self.bar(self.G["nova"], frac, cells)
        head = (tick // 4) % (cells + 4)
        n = self.G["nova"]
        return n["capL"] + "".join(n["flow"] if 0 <= head - i < 3 else n["full"] for i in range(cells)) + n["capR"]

    def pips(self, n, mx=5):
        return self.G["icon"]["pipOn"] * n + self.G["icon"]["pipOff"] * (mx - n)

    def move(self, key, kind, ready):
        return self.G["move"][key][kind]["ready" if ready else "wait"]


def save_png(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(img, np.ndarray):
        img = Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8), "RGBA")
    img.save(path, optimize=True)
    return path


def iter_glyphs(G, path="G"):
    for k, v in G.items():
        if isinstance(v, dict):
            yield from iter_glyphs(v, f"{path}.{k}")
        else:
            yield f"{path}.{k}", v


def self_check(pages, G):
    errors = []
    by_page = {pg.page: pg for pg in pages}
    for pg in pages:
        h, w = pg.img.shape[:2]
        if h != w or h % 16 or pg.page in FORBIDDEN_PAGES:
            errors.append(f"page {pg.page:02X}: {w}x{h}")
    for name, ch in iter_glyphs(G):
        if len(ch) != 1:
            errors.append(f"{name}: {len(ch)} chars")
            continue
        cp = ord(ch)
        pg = by_page.get(cp >> 8)
        if pg is None:
            errors.append(f"{name}: U+{cp:04X} not on a generated page")
            continue
        idx = cp & 0xFF
        if idx not in pg.meta:
            errors.append(f"{name}: U+{cp:04X} unassigned")
            continue
        a = pg.cell_array(idx)[..., 3]
        x0, x1 = pg.meta[idx]["span"]
        if a.max() < 128:
            errors.append(f"{name}: empty cell")
        if a[:, x0].max() < FAINT_A - 2 or a[:, x1 - 1].max() < FAINT_A - 2:
            errors.append(f"{name}: no edge pixel at its span {x0}..{x1 - 1}")
        if (x0 > 0 and a[:, :x0].max() > 0) or (x1 < a.shape[1] and a[:, x1:].max() > 0):
            errors.append(f"{name}: pixels outside its span")
        unit = pg.cell // 16
        lim = (2 * unit, 14 * unit) if pg.page == PAGE_HUD else (2 * unit, 30 * unit)
        rows = np.nonzero(a.max(axis=1) > 0)[0]
        if len(rows) and (rows.min() < lim[0] or rows.max() >= lim[1]):
            errors.append(f"{name}: rows {rows.min()}..{rows.max()} outside {lim}")
        if pg.page == PAGE_HUD and not name.startswith("G.emblem.") and not name.startswith("G.move."):
            # 小さなグリフは 3〜12 行（バーの端だけ 3〜12、他は 4〜11 が目安）
            if len(rows) and (rows.min() < 3 or rows.max() > 12):
                errors.append(f"{name}: rows {rows.min()}..{rows.max()} outside 3..12")
    # アイテムアイコン（自分の担当 = 素材・道具とスーツ。コアとウェポンは武器の生成スクリプトの担当）
    warnings = []
    mine = set(D.MATERIALS) | {f"suit_{k}" for k in KEYS}
    try:
        atlas = json.load(open(os.path.join(RP, "textures", "item_texture.json"), encoding="utf-8"))
        for k, v in atlas["texture_data"].items():
            if k.startswith("astro_"):
                tex = v["textures"] if isinstance(v["textures"], str) else v["textures"][0]
                if not os.path.exists(os.path.join(RP, tex + ".png")):
                    (errors if k[len("astro_"):] in mine else warnings).append(f"item_texture {k}: {tex}.png missing")
    except FileNotFoundError:
        errors.append("item_texture.json missing (run gen_astro_packs.py)")
    for name in mine:
        if not os.path.exists(os.path.join(ITEM_DIR, f"{name}.png")):
            errors.append(f"textures/items/astro/{name}.png missing")
    return errors, warnings


def main():
    pg, G = build_hud_page()
    pg2, G2 = build_art_page()
    G.update(G2)
    for path, page in ((os.path.join(FONT_DIR, "glyph_EA.png"), pg), (os.path.join(FONT_DIR, "glyph_EB.png"), pg2)):
        save_png(page.image(), path)
    write_glyphs_js(G, (pg, pg2))
    # フォーム・アイテム・パックのアイコン
    for key in KEYS:
        save_png(ui_emblem(key), os.path.join(UI_DIR, f"emblem_{key}.png"))
    for name in MENU_ACCENT:
        save_png(menu_icon(name), os.path.join(UI_DIR, f"{name}.png"))
    for name, fn in ITEM_ICONS.items():
        save_png(fn(), os.path.join(ITEM_DIR, f"{name}.png"))
    kinds = {}
    for key in KEYS:
        img, how = suit_icon(key)
        kinds[how] = kinds.get(how, 0) + 1
        save_png(img, os.path.join(ITEM_DIR, f"suit_{key}.png"))
    icon = Image.fromarray(np.clip(pack_icon() + 0.5, 0, 255).astype(np.uint8), "RGBA").convert("RGB")
    for pack in (BP, RP):
        icon.save(os.path.join(pack, "pack_icon.png"), optimize=True)
    # プレビュー（常に書く。軽い）
    page_preview(pg, os.path.join(SCRATCH, "glyphs_EA.png"))
    page_preview(pg2, os.path.join(SCRATCH, "glyphs_EB.png"))
    mock, widths = hud_mock(pg, pg2, G)
    os.makedirs(DOCS, exist_ok=True)
    mock.save(os.path.join(DOCS, "hud.png"), optimize=True)
    note = f"1 行目 ≈ {widths[0]:.0f} GUI px、2 行目 ≈ {widths[1]:.0f} GUI px（地球・16 + 10 セル）"
    write_ui_md(G, (pg, pg2), note)
    errors, warnings = self_check((pg, pg2), G)
    n = sum(1 for _ in iter_glyphs(G))
    print(f"  ui: glyph_EA {len(pg.meta)} cells, glyph_EB {len(pg2.meta)} cells, glyphs.js {n} keys, "
          f"suit icons {kinds}, {note}")
    if warnings:
        print(f"  ui: 他の担当のアイコンがまだ無い: {len(warnings)} 件（例: {warnings[0]}）")
    if errors:
        for e in errors:
            print("  !!", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
