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
    "venus": (255, 226, 84),
    "earth": (88, 255, 146),
    "mars": (255, 84, 60),
    "jupiter": (255, 160, 70),
    "saturn": (238, 214, 150),
    "uranus": (80, 240, 214),
    "neptune": (84, 128, 255),
    "sol": (255, 204, 56),
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
        "..CWC..",
        "CCWWWCC",
        "..CWC..",
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
        "...W...",
        "c.CWC.c",
        "CWWWWWC",
        "c.CWC.c",
        "...W...",
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
#  小さな惑星紋章（12x12: 六角の枠＋直径 8 の惑星）
# ---------------------------------------------------------------------------
def emblem_small(key):
    c = HUD_COL[key]
    p = Px(16)
    hexpts = [(5.1, 3), (10.9, 3), (14, 8), (10.9, 13), (5.1, 13), (2, 8)]
    m = poly_mask(16, 16, hexpts)
    out = edge(m)
    p.fill_mask(erode(m), PLATE, 216)
    for y, x in zip(*np.nonzero(out)):
        lit = (x + y * 0.8) < 14
        p.put(x, y, lighten(c, 0.5) if lit else shade(c, 0.85), 255)
    pl = render_planet(key, 16, {"saturn": 2.6, "sol": 3.0, "uranus": 3.2}.get(key, 3.6), crisp=True,
                       detail=0.0)
    over(p.a, pl, 0, 0)
    tweak_small_emblem(key, p, c)
    return p


def tweak_small_emblem(key, p, c):
    """極小の惑星は手で一部の画素を整える。"""
    if key == "sol":
        for x, y in [(7, 4), (8, 4), (7, 11), (8, 11), (4, 7), (4, 8), (11, 7), (11, 8)]:
            p.put(x, y, (255, 200, 70), 255)
        for x, y in [(5, 5), (10, 5), (5, 10), (10, 10)]:
            p.put(x, y, (255, 150, 40), 210)
        p.put(7, 7, WHITE, 255)
    if key == "earth":
        p.put(6, 6, (236, 248, 255), 220)


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
        ".CCLLLCC.",
        "CLLpppLLC",
        "CLppWppLC",
        "CLpWWWpLC",
        "CLppWppLC",
        ".CCLLLCC.",
        "...CCC...",
    ], {"C": (96, 214, 255), "L": (200, 244, 255), "p": (30, 70, 120), "W": (255, 255, 255)}),
    "sync": ([
        ".V.....P.",
        ".VwwwwwP.",
        "..V...P..",
        "...VwP...",
        "....X....",
        "...PwV...",
        "..P...V..",
        ".PwwwwwV.",
    ], {"V": (196, 150, 255), "P": (110, 226, 255), "w": ((210, 214, 255), 150), "X": (255, 255, 255)}),
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
    capL = pg.put(0x00, energy_cap("L"), "energy.capL", (0, CAP_W))
    capR = pg.put(0x01, energy_cap("R"), "energy.capR", (0, CAP_W))
    G["nova"] = {
        "full": pg.put(0x02, nova_seg("full"), "nova.full", (0, NOVA_W)),
        "empty": pg.put(0x03, nova_seg("empty"), "nova.empty", (0, NOVA_W)),
        "flow": pg.put(0x04, nova_seg("flow"), "nova.flow", (0, NOVA_W)),
        "capL": pg.put(0x05, nova_cap("L"), "nova.capL", (0, CAP_W)),
        "capR": pg.put(0x06, nova_cap("R"), "nova.capR", (0, CAP_W)),
    }
    G["progress"] = {
        "full": pg.put(0x07, prog_seg("full"), "progress.full", (0, PROG_W)),
        "empty": pg.put(0x08, prog_seg("empty"), "progress.empty", (0, PROG_W)),
        "half": pg.put(0x09, prog_seg("half"), "progress.half", (0, PROG_W)),
        "capL": pg.put(0x0A, prog_cap("L"), "progress.capL", (0, 3)),
        "capR": pg.put(0x0B, prog_cap("R"), "progress.capR", (0, 3)),
    }
    G["sync"] = {
        "full": pg.put(0x0C, sync_seg("full"), "sync.full", (0, SYNC_W)),
        "empty": pg.put(0x0D, sync_seg("empty"), "sync.empty", (0, SYNC_W)),
        "capL": pg.put(0x0E, sync_cap("L"), "sync.capL", (0, 2)),
        "capR": pg.put(0x0F, sync_cap("R"), "sync.capR", (0, 2)),
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
            for sh in ((1, (0.25, 0.25, 0.25)), (0, None)) if shadow else ((0, None),):
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
            for off, kk in (((1, 0.25), (0, 1.0)) if shadow else ((0, 1.0),)):
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


def save_png(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(img, np.ndarray):
        img = Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8), "RGBA")
    img.save(path, optimize=True)
    return path


def main():
    pg, G = build_hud_page()
    save_png(pg.image(), os.path.join(FONT_DIR, "glyph_EA.png"))
    page_preview(pg, os.path.join(SCRATCH, "glyphs_EA.png"))
    print("  ui: glyph_EA")


if __name__ == "__main__":
    main()
