# -*- coding: utf-8 -*-
"""Procedural texture painter.

Paints straight into the UV rectangles `mcmodel` handed out, so texture and
geometry cannot drift.  Everything is written in *normalised* face coordinates
so the same routine draws a 12-texel face and a 48-texel one - which is what
lets the small parts (faces, insignia, blade edges) carry real detail once the
cube is given a higher `uv_scale`.
"""
from __future__ import annotations

import math
import random
from typing import Dict, Optional, Sequence, Tuple

from PIL import Image

RGB = Tuple[int, int, int]
EM = 254           # alpha marker for emissive texels (entity_emissive_alpha)

FACE_LIGHT = {"up": 1.18, "down": 0.64, "north": 1.02, "south": 0.88,
              "east": 0.84, "west": 0.94}


def clamp(v: float, lo: float = 0.0, hi: float = 255.0) -> int:
    return int(max(lo, min(hi, v)))


def mix(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (clamp(a[0] + (b[0] - a[0]) * t),
            clamp(a[1] + (b[1] - a[1]) * t),
            clamp(a[2] + (b[2] - a[2]) * t))


def shade(c: RGB, f: float) -> RGB:
    return (clamp(c[0] * f), clamp(c[1] * f), clamp(c[2] * f))


def hexc(s) -> RGB:
    if isinstance(s, (tuple, list)):
        return (int(s[0]), int(s[1]), int(s[2]))
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


class Painter:
    def __init__(self, width: int, height: int, seed: int = 0):
        self.img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        self.px = self.img.load()
        self.rng = random.Random(seed)
        self.w = width
        self.h = height

    # -- primitives -----------------------------------------------------
    def put(self, x: int, y: int, c: RGB, a: int = 255) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[int(x), int(y)] = (clamp(c[0]), clamp(c[1]), clamp(c[2]), a)

    def get(self, x: int, y: int) -> RGB:
        if 0 <= x < self.w and 0 <= y < self.h:
            r, g, b, _ = self.px[int(x), int(y)]
            return (r, g, b)
        return (0, 0, 0)

    def blend(self, x: int, y: int, c: RGB, t: float, a: int = 255) -> None:
        self.put(x, y, mix(self.get(x, y), c, t), a)

    # -- pattern field --------------------------------------------------
    def _pattern(self, name, x, y, w, h, scale, rng) -> float:
        """Returns 0..1 - how far to mix towards the style's secondary colour."""
        s = max(1.0, scale)
        if name == "flat":
            return 0.0
        if name == "skin":
            return 0.06 * math.sin(y * 0.7 / s)
        if name == "cloth":
            u, v = int(x / s), int(y / s)
            return 0.30 if (u + v) % 3 == 0 else (0.12 if u % 3 == 0 else 0.0)
        if name == "weave":
            u, v = int(x / s), int(y / s)
            return 0.45 if (u % 2) ^ (v % 2) else 0.05
        if name == "metal":
            u = int(x / s)
            return 0.55 if u % 3 == 0 else (0.0 if u % 3 == 1 else 0.22)
        if name == "brushed":
            return 0.10 + 0.35 * abs(math.sin(x * 2.3 / s + y * 0.05))
        if name == "plate":
            band = max(3.0, 5 * s)
            v = y % band
            if v < 1:
                return 0.90
            if v < 2:
                return 0.18
            if x < s or x > w - s - 1:
                return 0.42
            return 0.0
        if name == "panel":
            bw, bh = max(4.0, 7 * s), max(4.0, 9 * s)
            if x % bw < 1 or y % bh < 1:
                return 0.85
            if x % bw < 2 or y % bh < 2:
                return 0.20
            return 0.0
        if name == "scale":
            sw, sh = max(3.0, 4 * s), max(2.0, 3 * s)
            row = int(y // sh)
            ox = (x + (sw / 2 if row % 2 else 0)) % sw
            if ox < 1 or y % sh > sh - 1.2:
                return 0.85
            return 0.20 if ox < 2 else 0.0
        if name == "carapace":
            ridge = abs(math.sin((x * 1.6 + y * 0.8) * 0.5 / s))
            return 0.80 if y % max(3.0, 4 * s) < 1 else ridge * 0.35
        if name == "muscle":
            v = math.sin(x * 1.15 / s + math.sin(y * 0.45 / s) * 2.0)
            return 0.55 + 0.40 * v if v > 0.5 else max(0.0, 0.22 * v)
        if name == "sinew":
            v = math.sin(y * 1.4 / s) * math.cos(x * 0.6 / s)
            return 0.7 if v > 0.55 else 0.0
        if name == "crack":
            v = math.sin(x * 1.9 / s + y * 1.5 / s) * math.cos(y * 0.7 / s - x * 0.35 / s)
            return 1.0 if v > 0.88 else 0.0
        if name == "hair":
            u = int(x * 3 + (y // max(1.0, 2 * s)) * 5)
            return 0.55 if u % 7 < 2 else (0.2 if u % 7 == 2 else 0.0)
        if name == "leather":
            return 0.25 * (rng.random() ** 3) + (0.5 if (int(x / s) * 7 + int(y / s) * 3) % 23 == 0 else 0)
        if name == "rubber":
            return 0.35 if int(y / s) % 2 == 0 else 0.0
        if name == "glass":
            return 0.6 * max(0.0, math.sin((x + y) * 0.4 / s))
        return 0.0

    # -- one face -------------------------------------------------------
    def paint_face(self, rect, face: str, style: Dict, key: int, scale: float) -> None:
        x0, y0, w, h = rect
        if w <= 0 or h <= 0:
            return
        rng = random.Random((key * 7919) ^ (hash(face) & 0xFFFF))
        light = FACE_LIGHT.get(face, 1.0)
        base = shade(hexc(style.get("base", (128, 128, 128))), light)
        second = shade(hexc(style.get("second", shade(hexc(style.get("base", (128, 128, 128))), 0.74))), light)
        noise = style.get("noise", 8)
        pattern = style.get("pattern", "flat")
        grad = style.get("grad", 0.14)
        ao = style.get("ao", 0.30)

        for y in range(h):
            gy = y / max(1, h - 1)
            for x in range(w):
                t = self._pattern(pattern, x, y, w, h, scale, rng)
                if pattern == "crack" and t >= 1.0:
                    self.put(x0 + x, y0 + y, hexc(style.get("second", (255, 255, 255))), EM)
                    continue
                c = mix(base, second, t)
                c = shade(c, 1.0 + grad * (0.5 - gy))
                # cheap ambient occlusion towards the silhouette of the face
                edge = min(x, y, w - 1 - x, h - 1 - y)
                if edge < 2 and ao:
                    c = shade(c, 1.0 - ao * (0.55 if edge == 0 else 0.22))
                n = rng.randint(-noise, noise)
                self.put(x0 + x, y0 + y, (c[0] + n, c[1] + n, c[2] + n))

        if style.get("rim", True) and w > 3 and h > 3:
            for x in range(w):
                self.blend(x0 + x, y0, shade(base, 1.18), 0.35)

        for decal in style.get("_decals", []):
            self.decal(rect, decal, style, scale)

    # ==================================================================
    #  decals
    # ==================================================================
    def decal(self, rect, decal, style: Dict, scale: float) -> None:
        if isinstance(decal, str):
            decal = {"name": decal}
        name = decal.get("name", "")
        x0, y0, w, h = rect
        if w < 2 or h < 2:
            return

        def P(u, v):  # normalised -> texel
            return (x0 + int(round(u * (w - 1))), y0 + int(round(v * (h - 1))))

        def box(u0, v0, u1, v1, c, a=255):
            ax, ay = P(u0, v0)
            bx, by = P(u1, v1)
            for yy in range(min(ay, by), max(ay, by) + 1):
                for xx in range(min(ax, bx), max(ax, bx) + 1):
                    self.put(xx, yy, c, a)

        def ellipse(cu, cv, ru, rv, c, a=255):
            cx, cy = P(cu, cv)
            rx = max(1, int(round(ru * w)))
            ry = max(1, int(round(rv * h)))
            for yy in range(-ry, ry + 1):
                for xx in range(-rx, rx + 1):
                    if (xx / rx) ** 2 + (yy / ry) ** 2 <= 1.05:
                        self.put(cx + xx, cy + yy, c, a)

        def line(u0, v0, u1, v1, c, a=255):
            ax, ay = P(u0, v0)
            bx, by = P(u1, v1)
            steps = max(abs(bx - ax), abs(by - ay), 1)
            for i in range(steps + 1):
                self.put(ax + (bx - ax) * i // steps, ay + (by - ay) * i // steps, c, a)

        glow = hexc(decal.get("glow", style.get("glow", (255, 120, 60))))
        light = hexc(style.get("light", (240, 242, 246)))
        dark = hexc(style.get("dark", (24, 22, 28)))

        if name == "face":
            self._face(P, box, ellipse, line, style, decal, w, h)
        elif name in ("eyes", "eyes_red", "eyes_blue", "eyes_gold", "eyes_violet",
                      "eyes_white", "eyes_green"):
            col = {
                "eyes_red": (255, 64, 44), "eyes_blue": (120, 214, 255),
                "eyes_gold": (255, 206, 74), "eyes_violet": (206, 122, 255),
                "eyes_white": (246, 246, 250), "eyes_green": (150, 255, 140),
            }.get(name, glow)
            ey = decal.get("y", 0.42)
            r = decal.get("r", 0.09)
            for cu in (decal.get("inset", 0.26), 1 - decal.get("inset", 0.26)):
                ellipse(cu, ey, r * 1.5, r, shade(col, 0.45), EM)
                ellipse(cu, ey, r, r * 0.7, col, EM)
                ellipse(cu, ey - 0.02, r * 0.4, r * 0.3, (255, 255, 240), EM)
        elif name == "brow_eyes":       # kaiju: a heavy brow ridge over glowing eyes
            box(0.0, 0.18, 1.0, 0.30, shade(dark, 1.4))
            for cu in (0.24, 0.76):
                ellipse(cu, 0.44, 0.10, 0.08, shade(glow, 0.4), EM)
                ellipse(cu, 0.44, 0.06, 0.05, glow, EM)
        elif name == "mask_no8":
            for yy in range(h):
                for xx in range(w):
                    self.put(x0 + xx, y0 + yy,
                             mix(hexc(decal.get("plate", "#e6e3d8")),
                                 hexc(decal.get("plate_dark", "#a9a596")),
                                 yy / max(1, h - 1)))
            line(0.0, 0.52, 1.0, 0.50, shade(dark, 1.2))
            line(0.0, 0.53, 1.0, 0.51, shade(dark, 0.8))
            for cu in (0.24, 0.76):
                ellipse(cu, 0.36, 0.13, 0.10, shade(dark, 1.0))
                ellipse(cu, 0.36, 0.09, 0.07, shade(glow, 0.55), EM)
                ellipse(cu, 0.36, 0.055, 0.045, (255, 255, 235), EM)
            # cheek seams
            line(0.10, 0.66, 0.26, 0.86, shade(dark, 1.1))
            line(0.90, 0.66, 0.74, 0.86, shade(dark, 1.1))
        elif name == "fangs":
            row = decal.get("y", 0.62)
            box(0.0, row - 0.10, 1.0, row, dark)
            n = max(3, int(w / max(2, 3 * scale)))
            for i in range(n):
                u = (i + 0.5) / n
                ellipse(u, row + 0.12, 0.5 / n, 0.16, light)
                ellipse(u, row + 0.05, 0.32 / n, 0.10, shade(light, 0.85))
        elif name == "maw":
            box(0.0, 0.28, 1.0, 1.0, (48, 10, 14))
            box(0.0, 0.34, 1.0, 0.62, (86, 22, 26))
            n = max(3, int(w / max(2, 3 * scale)))
            for i in range(n):
                u = (i + 0.5) / n
                ellipse(u, 0.30, 0.45 / n, 0.10, light)
                ellipse(u, 0.94, 0.45 / n, 0.09, shade(light, 0.9))
        elif name == "visor":
            box(0.0, 0.12, 1.0, 0.86, (18, 24, 34))
            for yy in range(h):
                v = yy / max(1, h - 1)
                if 0.14 <= v <= 0.84:
                    for xx in range(w):
                        u = xx / max(1, w - 1)
                        t = 0.15 + 0.55 * math.sin(math.pi * u) * (1 - abs(v - 0.5))
                        self.blend(x0 + xx, y0 + yy, hexc(style.get("glow", "#4a9eec")), t, EM)
            line(0.0, 0.12, 1.0, 0.12, shade(light, 0.9))
        elif name == "emblem":
            # 日本防衛隊: white shield, red centre, dark outline
            ellipse(0.5, 0.5, 0.20, 0.22, dark)
            ellipse(0.5, 0.5, 0.16, 0.18, light)
            ellipse(0.5, 0.5, 0.085, 0.10, (198, 42, 54))
            line(0.5, 0.30, 0.5, 0.70, dark)
        elif name == "rivets":
            n = max(2, int(w / max(4, 6 * scale)))
            for i in range(n):
                for v in (0.12, 0.88):
                    u = (i + 0.5) / n
                    ellipse(u, v, 0.035, 0.035, shade(dark, 1.5))
                    self.put(*P(u, v - 0.02), shade(light, 0.9))
        elif name == "panel_line":
            line(0.0, 0.32, 1.0, 0.32, shade(dark, 1.4))
            line(0.0, 0.34, 1.0, 0.34, shade(light, 0.85))
            line(0.0, 0.70, 1.0, 0.70, shade(dark, 1.4))
        elif name == "scale_row":
            rows = max(2, int(h / max(3, 4 * scale)))
            for r in range(rows):
                v = (r + 0.5) / rows
                cols = max(2, int(w / max(3, 4 * scale)))
                for c in range(cols):
                    u = (c + (0.5 if r % 2 else 0.0)) / cols
                    ellipse(u, v, 0.5 / cols, 0.45 / rows, shade(dark, 1.25))
                    ellipse(u, v - 0.1 / rows, 0.34 / cols, 0.28 / rows,
                            shade(light, 0.55))
        elif name == "stubble":
            rng = random.Random(w * 31 + h)
            for _ in range(max(8, w * h // 10)):
                u = 0.18 + rng.random() * 0.64
                v = 0.66 + rng.random() * 0.30
                self.put(*P(u, v), shade(hexc(style.get("hair_col", "#2a2630")), 1.0))
        elif name == "ribbon":
            box(0.0, 0.30, 1.0, 0.56, hexc(decal.get("colour", "#1a1a20")))
            line(0.0, 0.30, 1.0, 0.30, shade(light, 0.5))
            line(0.0, 0.56, 1.0, 0.56, shade(dark, 1.2))
        elif name == "cross_slit":
            # 怪獣10号: 目鼻のない装甲面に走る十字の切れ込み
            box(0.0, 0.0, 1.0, 1.0, hexc(style.get("base", "#C4202A")))
            box(0.44, 0.06, 0.56, 0.94, (14, 6, 9))
            box(0.10, 0.40, 0.90, 0.52, (14, 6, 9))
            box(0.46, 0.10, 0.54, 0.90, (32, 12, 18))
            box(0.14, 0.42, 0.86, 0.50, (32, 12, 18))
            for u in (0.30, 0.70):
                line(u, 0.06, u, 0.94, shade(dark, 1.6))
        elif name == "single_eye":
            box(0.0, 0.0, 1.0, 1.0, (10, 8, 14))
            ellipse(0.5, 0.5, 0.34, 0.34, shade(glow, 0.35), EM)
            ellipse(0.5, 0.5, 0.22, 0.22, glow, EM)
            ellipse(0.5, 0.46, 0.09, 0.09, (240, 252, 255), EM)
        elif name == "eye_rows":
            # 余獣: 左右に3対並ぶ小さな黒目。発光なし
            for i in range(3):
                v = 0.34 + i * 0.16
                for u in (0.22 + i * 0.04, 0.78 - i * 0.04):
                    ellipse(u, v, 0.055, 0.05, (12, 14, 17))
                    ellipse(u, v - 0.012, 0.022, 0.02, (60, 66, 74))
        elif name == "logo":
            # an abstract manufacturer wordmark — deliberately not a real logo
            bar_h = 0.16
            for i, (u0, u1) in enumerate(((0.10, 0.30), (0.36, 0.50), (0.56, 0.90))):
                box(u0, 0.42 - i * 0.02, u1, 0.42 + bar_h - i * 0.02, light)
            box(0.10, 0.66, 0.90, 0.72, shade(light, 0.55))
        elif name == "powerline":
            for yy in range(h):
                v = yy / max(1, h - 1)
                t = 0.55 + 0.45 * math.sin(v * math.pi * 3)
                for xx in range(w):
                    self.put(x0 + xx, y0 + yy,
                             mix(shade(glow, 0.35), glow, t),
                             EM if t > 0.7 else 255)
        elif name == "buckle":
            box(0.36, 0.18, 0.64, 0.82, shade(light, 0.55))
            box(0.40, 0.28, 0.60, 0.72, light)
            ellipse(0.5, 0.5, 0.06, 0.16, glow, EM)
        elif name == "pauldron":
            line(0.5, 0.0, 0.5, 1.0, shade(dark, 1.1))
            box(0.10, 0.36, 0.90, 0.46, shade(light, 0.72))
        elif name == "vent":
            for i in range(3):
                v = 0.24 + i * 0.24
                box(0.18, v, 0.82, v + 0.08, shade(dark, 1.0))
                box(0.20, v + 0.01, 0.80, v + 0.05, shade(glow, 0.8), EM)
        elif name == "number":
            self._digits(P, box, decal.get("text", "3"), light)
        elif name == "core":
            ellipse(0.5, 0.5, 0.34, 0.34, shade(glow, 0.30), EM)
            ellipse(0.5, 0.5, 0.22, 0.22, shade(glow, 0.7), EM)
            ellipse(0.5, 0.5, 0.11, 0.11, (255, 255, 236), EM)
        elif name == "veins":
            rng = random.Random(hash(name) ^ w ^ h)
            for _ in range(max(3, w * h // 26)):
                u, v = rng.random(), rng.random()
                du, dv = (rng.random() - 0.5) * 0.3, 0.18 + rng.random() * 0.2
                line(u, v, u + du, v + dv, glow, EM)
        elif name == "stripe":
            box(0.44, 0.0, 0.56, 1.0, shade(glow, 0.5), EM)
            box(0.47, 0.0, 0.53, 1.0, glow, EM)
        elif name == "edge_glow":
            box(0.0, 0.0, 1.0, 0.10, glow, EM)
        elif name == "gills":
            for i in range(3):
                v = 0.30 + i * 0.18
                line(0.18, v, 0.82, v + 0.04, shade(dark, 1.2))
                line(0.20, v + 0.03, 0.80, v + 0.07, shade(glow, 0.55), EM)

    # -- anime face ------------------------------------------------------
    def _face(self, P, box, ellipse, line, style, decal, w, h) -> None:
        """Drawn in integer texels - at x6 UV a head front face is ~24x28,
        which is enough for a proper anime eye (lash, sclera, iris, pupil,
        highlight) instead of a two-pixel dot."""
        x0, y0 = P(0.0, 0.0)
        iris = hexc(decal.get("iris", style.get("iris", "#3c3c50")))
        brow = hexc(decal.get("brow", style.get("hair_col", style.get("dark", "#2a2630"))))
        mouth = hexc(decal.get("mouth", "#96545a"))
        skin = style_skin(style)
        sclera = (250, 250, 252)
        dark = hexc(style.get("dark", "#221f28"))

        ew = max(2, int(round(w * decal.get("eye_w", 0.24))))
        eh = max(2, int(round(h * decal.get("eye_h", 0.17))))
        ey = int(round(h * decal.get("eye_v", 0.50)))
        gap = max(1, int(round(w * decal.get("eye_gap", 0.10))))
        detail = ew >= 4 and eh >= 3
        expr = decal.get("expr", "normal")
        if expr == "narrow":          # 保科: 常に細めた目
            eh = max(1, int(eh * 0.55))
        elif expr == "stern":         # ミナ / 功: 目つきが鋭い
            eh = max(2, int(eh * 0.82))

        def rect(px, py, rw, rh, c, a=255):
            for yy in range(rh):
                for xx in range(rw):
                    self.put(x0 + px + xx, y0 + py + yy, c, a)

        centres = [(w // 2) - gap - ew, (w // 2) + gap]
        for i, ex in enumerate(centres):
            outer = 0 if i == 0 else ew - 1       # the temple side of each eye
            top = ey - eh // 2
            rect(ex, top, ew, eh, sclera)
            # round the eye off so it does not read as a rectangle
            if detail:
                for cx, cy in ((0, eh - 1), (ew - 1, eh - 1)):
                    rect(ex + cx, top + cy, 1, 1, shade(skin, 0.92))
            ix = ex + (1 if detail else 0)
            iw = max(1, ew - (2 if detail else 0))
            rect(ix, top, iw, eh, iris)
            if detail:
                rect(ix + (iw - 1) // 2, top + 1, max(1, iw // 3), max(1, eh - 1),
                     shade(iris, 0.38))
                rect(ex + outer, top, 1, 1, (255, 255, 255))
                rect(ex + outer + (1 if i == 0 else -1), top, 1, 1, (244, 248, 255))
                rect(ex, top + eh - 1, ew, 1, shade(iris, 0.55))
            # upper lash - the heaviest line on an anime face
            rect(ex - 1, top - 1, ew + 2, 1, dark)
            if detail:
                rect(ex + (0 if i == 0 else ew // 2) - 1, top - 2,
                     ew // 2 + 2, 1, shade(dark, 1.35))
                rect(ex, ey + (eh + 1) // 2, ew, 1, shade(skin, 0.74))
            # brow
            by = top - (4 if detail else 3)
            for xx in range(ew + 1):
                lift = 0
                if decal.get("brow_tilt", 1):
                    inner_side = (xx >= ew // 2) if i == 0 else (xx < ew // 2)
                    lift = 0 if inner_side else -1
                rect(ex - 1 + xx, by + lift, 1, 1, brow)

        if detail:
            nose = ey + eh + 1
            rect(w // 2, nose, 1, max(1, h // 12), shade(skin, 0.78))
        if expr == "grin" and detail:      # 八重歯の見える口元
            gy = ey + eh + max(2, h // 7)
            gw = max(3, int(round(w * 0.26)))
            rect((w - gw) // 2, gy, gw, 1, dark)
            rect((w - gw) // 2, gy - 1, 1, 1, (250, 250, 250))
            rect((w + gw) // 2 - 1, gy - 1, 1, 1, (250, 250, 250))
        if decal.get("stubble") and detail:
            rng2 = random.Random(w * 17 + h * 5)
            beard = shade(hexc(style.get("hair_col", "#2a2630")), 1.3)
            for _ in range(max(6, w * h // 22)):
                u = 0.18 + rng2.random() * 0.64
                v = 0.80 + rng2.random() * 0.18
                px_, py_ = P(u, v)
                self.blend(px_, py_, beard, 0.30)
        if decal.get("moles"):
            for ex in centres:
                rect(ex + ew // 2, ey + eh // 2 + 2, 1, 1, shade(skin, 0.52))
        mv = ey + eh + max(2, h // 7)
        mw = max(2, int(round(w * 0.20)))
        rect((w - mw) // 2, mv, mw, 1, mouth)
        if decal.get("smile") and detail:
            rect((w - mw) // 2 - 1, mv - 1, 1, 1, mouth)
            rect((w + mw) // 2, mv - 1, 1, 1, mouth)

    def _digits(self, P, box, text: str, colour) -> None:
        FONT = {
            "0": ["111", "101", "101", "101", "111"],
            "1": ["010", "110", "010", "010", "111"],
            "2": ["111", "001", "111", "100", "111"],
            "3": ["111", "001", "111", "001", "111"],
            "4": ["101", "101", "111", "001", "001"],
            "8": ["111", "101", "111", "101", "111"],
            "9": ["111", "101", "111", "001", "111"],
        }
        n = len(text)
        cw = 1.0 / (n * 4)
        for i, ch in enumerate(text):
            rows = FONT.get(ch)
            if not rows:
                continue
            for r, row in enumerate(rows):
                for c, bit in enumerate(row):
                    if bit == "1":
                        u = (i * 4 + c + 0.5) * cw
                        v = 0.22 + r * 0.12
                        box(u, v, u + cw * 0.9, v + 0.10, colour)

    # ==================================================================
    def paint_model(self, model, styles: Dict[str, Dict]) -> None:
        default = styles.get("base", {})
        for i, cube in enumerate(model.all_cubes()):
            style = dict(styles.get(cube.style, default))
            scale = float(cube._scale or 1)
            by_face: Dict[str, list] = {}
            for face, decal in cube.decals.items():
                by_face.setdefault(face, []).append(decal)
            for face, rect in cube.rects.items():
                s = dict(style)
                s["_decals"] = by_face.get(face, [])
                self.paint_face(rect, face, s, i + 1, scale)

    def save(self, path: str, posterize: int = 4) -> None:
        """Posterising the colour channels costs nothing visible at 16px-per-block
        but roughly halves the PNG, because the per-texel noise stops defeating
        the compressor.  Alpha is left exactly as painted — the 254 marker that
        drives `entity_emissive_alpha` must survive."""
        if posterize > 1:
            px = self.img.load()
            q = posterize
            for y in range(self.h):
                for x in range(self.w):
                    r, g, b, a = px[x, y]
                    if a == 0:
                        continue
                    px[x, y] = (min(255, (r + q // 2) // q * q),
                                min(255, (g + q // 2) // q * q),
                                min(255, (b + q // 2) // q * q), a)
        self.img.save(path, optimize=True)


def style_skin(style) -> RGB:
    return hexc(style.get("skin", style.get("base", (230, 200, 170))))
