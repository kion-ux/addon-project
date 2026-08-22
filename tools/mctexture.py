"""Procedural texture painter that follows the UV rectangles produced by mcmodel."""
from __future__ import annotations

import math
import random
from typing import Dict, Sequence, Tuple

from PIL import Image

RGB = Tuple[int, int, int]

FACE_LIGHT = {"up": 1.16, "down": 0.68, "north": 1.0, "south": 0.9, "east": 0.86, "west": 0.94}


def clamp(v: float, lo: float = 0.0, hi: float = 255.0) -> int:
    return int(max(lo, min(hi, v)))


def mix(a: RGB, b: RGB, t: float) -> RGB:
    return (
        clamp(a[0] + (b[0] - a[0]) * t),
        clamp(a[1] + (b[1] - a[1]) * t),
        clamp(a[2] + (b[2] - a[2]) * t),
    )


def shade(c: RGB, f: float) -> RGB:
    return (clamp(c[0] * f), clamp(c[1] * f), clamp(c[2] * f))


class Painter:
    def __init__(self, width: int, height: int, seed: int = 0):
        self.img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        self.px = self.img.load()
        self.rng = random.Random(seed)
        self.w = width
        self.h = height

    def put(self, x: int, y: int, c: RGB, a: int = 255) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = (clamp(c[0]), clamp(c[1]), clamp(c[2]), a)

    def get(self, x: int, y: int) -> RGB:
        if 0 <= x < self.w and 0 <= y < self.h:
            r, g, b, _ = self.px[x, y]
            return (r, g, b)
        return (0, 0, 0)

    def rect(self, r, c: RGB) -> None:
        x0, y0, w, h = r
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.put(x, y, c)

    # ------------------------------------------------------------------
    def paint_face(self, rect, face: str, style: Dict, key: int) -> None:
        x0, y0, w, h = rect
        if w <= 0 or h <= 0:
            return
        rng = random.Random((key * 7919) ^ hash(face) & 0xFFFF)
        base: RGB = style.get("base", (128, 128, 128))
        base = shade(base, FACE_LIGHT.get(face, 1.0))
        second: RGB = style.get("second", shade(base, 0.78))
        second = shade(second, FACE_LIGHT.get(face, 1.0))
        noise = style.get("noise", 10)
        pattern = style.get("pattern", "flat")
        grad = style.get("grad", 0.16)

        for y in range(h):
            gy = (y / max(1, h - 1)) if h > 1 else 0.0
            for x in range(w):
                gx = (x / max(1, w - 1)) if w > 1 else 0.0
                t = self._pattern(pattern, x, y, w, h, gx, gy, rng)
                if pattern == "crack" and t >= 1.0:
                    self.put(x0 + x, y0 + y, style.get("second", (255, 255, 255)), 254)
                    continue
                c = mix(base, second, t)
                # soft top-down lighting inside the face
                c = shade(c, 1.0 + grad * (0.5 - gy))
                n = rng.randint(-noise, noise)
                c = (c[0] + n, c[1] + n, c[2] + n)
                self.put(x0 + x, y0 + y, c)

        if style.get("edge", True) and w > 2 and h > 2:
            ec = shade(base, style.get("edge_factor", 0.62))
            for x in range(w):
                self.put(x0 + x, y0, mix(self.get(x0 + x, y0), shade(base, 1.12), 0.5))
                self.put(x0 + x, y0 + h - 1, mix(self.get(x0 + x, y0 + h - 1), ec, 0.65))
            for y in range(h):
                self.put(x0, y0 + y, mix(self.get(x0, y0 + y), ec, 0.45))
                self.put(x0 + w - 1, y0 + y, mix(self.get(x0 + w - 1, y0 + y), ec, 0.45))

        for name in style.get("glow_faces", {}).get(face, []):
            self.decal(rect, name, style)

    def _pattern(self, pattern, x, y, w, h, gx, gy, rng) -> float:
        if pattern == "flat":
            return 0.0
        if pattern == "cloth":
            return 0.35 if (x + y) % 4 == 0 else (0.15 if x % 4 == 0 else 0.0)
        if pattern == "metal":
            return 0.55 if x % 3 == 0 else (0.0 if x % 3 == 1 else 0.2)
        if pattern == "plate":
            band = 5
            if y % band == 0:
                return 0.85
            if y % band == 1:
                return 0.12
            if x in (0, w - 1):
                return 0.5
            return 0.0
        if pattern == "scale":
            sw, sh = 4, 3
            oy = y // sh
            ox = (x + (sw // 2 if oy % 2 else 0)) % sw
            if ox == 0 or y % sh == sh - 1:
                return 0.8
            return 0.18 if ox == 1 else 0.0
        if pattern == "carapace":
            ridge = abs(math.sin((x * 1.7 + y * 0.9) * 0.55))
            return 0.75 if y % 4 == 0 else ridge * 0.35
        if pattern == "muscle":
            v = math.sin(x * 1.3 + math.sin(y * 0.5) * 2.0)
            return 0.5 + 0.45 * v if v > 0.55 else max(0.0, 0.25 * v)
        if pattern == "crack":
            v = math.sin(x * 2.1 + y * 1.7) * math.cos(y * 0.8 - x * 0.4)
            return 1.0 if v > 0.86 else 0.0
        if pattern == "hair":
            return 0.6 if (x * 3 + (y // 2) * 5) % 7 < 2 else 0.0
        if pattern == "denim":
            return 0.3 if y % 3 == 0 else (0.1 if x % 5 == 0 else 0.0)
        return 0.0

    # ------------------------------------------------------------------
    def decal(self, rect, name: str, style: Dict) -> None:
        x0, y0, w, h = rect
        glow: RGB = style.get("glow", (255, 90, 40))
        dark: RGB = style.get("dark", (18, 16, 22))
        light: RGB = style.get("light", (238, 236, 240))
        skin: RGB = style.get("skin", (236, 199, 168))

        EM = 254

        def blob(cx, cy, rx, ry, c, a=255):
            for yy in range(-ry, ry + 1):
                for xx in range(-rx, rx + 1):
                    if (xx / max(0.5, rx)) ** 2 + (yy / max(0.5, ry)) ** 2 <= 1.05:
                        self.put(x0 + cx + xx, y0 + cy + yy, c, a)

        if name.startswith("eyes"):
            col = {"eyes_red": (255, 60, 40), "eyes_blue": (90, 210, 255),
                   "eyes_gold": (255, 205, 70), "eyes_white": (245, 245, 245),
                   "eyes_violet": (198, 120, 255)}.get(name, glow)
            ey = max(1, h // 3)
            inset = max(1, w // 6)
            for sx in (inset, w - inset - 1):
                self.put(x0 + sx, y0 + ey, col, EM)
                if w >= 8:
                    self.put(x0 + sx + (1 if sx < w // 2 else -1), y0 + ey, shade(col, 0.75), EM)
                if h >= 8:
                    self.put(x0 + sx, y0 + ey + 1, shade(col, 0.6), EM)
        elif name == "face_human":
            ey = max(1, h // 2 - 1)
            for sx in (max(1, w // 4), w - max(1, w // 4) - 1):
                self.put(x0 + sx, y0 + ey, (250, 250, 250))
                self.put(x0 + sx, y0 + ey + 1, style.get("iris", (60, 60, 80)))
            for xx in range(w // 3, w - w // 3):
                self.put(x0 + xx, y0 + min(h - 1, ey + 4), shade(skin, 0.72))
        elif name == "fangs":
            row = h - max(2, h // 4)
            for xx in range(1, w - 1):
                self.put(x0 + xx, y0 + row, light if xx % 2 == 0 else dark)
                if xx % 2 == 0 and row + 1 < h:
                    self.put(x0 + xx, y0 + row + 1, shade(light, 0.8))
            for xx in range(w):
                self.put(x0 + xx, y0 + row - 1, dark)
        elif name == "maw":
            top = h // 2
            for yy in range(top, h - 1):
                for xx in range(1, w - 1):
                    self.put(x0 + xx, y0 + yy, (52, 12, 16) if yy > top else dark)
            for xx in range(1, w - 1, 2):
                self.put(x0 + xx, y0 + top, light)
                self.put(x0 + xx, y0 + h - 2, light)
        elif name == "visor":
            band = max(1, h // 4)
            top = h // 3
            for yy in range(top, min(h, top + band + 1)):
                for xx in range(1, w - 1):
                    self.put(x0 + xx, y0 + yy, mix((28, 36, 52), (96, 190, 235), 0.15 + 0.5 * (xx / max(1, w))))
        elif name == "mask_no8":
            # bone-white plate with a jagged seam and burning eyes
            for yy in range(h):
                for xx in range(w):
                    self.put(x0 + xx, y0 + yy, mix((226, 224, 214), (176, 172, 160), (yy / max(1, h))))
            for xx in range(w):
                yy = h // 2 + (1 if xx % 3 == 0 else 0)
                self.put(x0 + xx, y0 + yy, (46, 42, 48))
            ey = max(1, h // 3)
            for sx in (max(1, w // 5), w - max(1, w // 5) - 1):
                blob(sx, ey, 1, 1, glow, EM)
                self.put(x0 + sx, y0 + ey, (255, 240, 200), EM)
        elif name == "emblem":
            cx, cy = w // 2, h // 2
            for yy in range(-2, 3):
                for xx in range(-2, 3):
                    if abs(xx) + abs(yy) <= 2:
                        self.put(x0 + cx + xx, y0 + cy + yy, (232, 236, 244))
            self.put(x0 + cx, y0 + cy, (196, 30, 46))
        elif name == "core":
            cx, cy = w // 2, h // 2
            blob(cx, cy, max(1, w // 4), max(1, h // 4), shade(glow, 0.55), EM)
            blob(cx, cy, max(1, w // 6), max(1, h // 6), glow, EM)
            self.put(x0 + cx, y0 + cy, (255, 255, 230), EM)
        elif name == "veins":
            for _ in range(max(2, w * h // 22)):
                cx = self.rng.randrange(w)
                cy = self.rng.randrange(h)
                for step in range(self.rng.randint(2, 5)):
                    self.put(x0 + cx, y0 + cy, glow if step % 2 == 0 else shade(glow, 0.6), EM)
                    cx += self.rng.choice((-1, 0, 1))
                    cy += 1
        elif name == "stripe":
            for yy in range(h):
                self.put(x0 + w // 2, y0 + yy, glow, EM)
                self.put(x0 + w // 2 - 1, y0 + yy, shade(glow, 0.5), EM)
        elif name == "number":
            cx, cy = w // 2, h // 2
            for yy in range(-2, 3):
                self.put(x0 + cx, y0 + cy + yy, light)
            self.put(x0 + cx - 1, y0 + cy - 1, light)

    # ------------------------------------------------------------------
    def paint_model(self, model, styles: Dict[str, Dict]) -> None:
        for i, cube in enumerate(model.all_cubes()):
            style = dict(styles.get(cube.style, styles.get("base", {})))
            glow_faces: Dict[str, list] = {}
            for face, decal in cube.decals.items():
                glow_faces.setdefault(face, []).append(decal)
            style["glow_faces"] = glow_faces
            for face, rect in cube.rects.items():
                self.paint_face(rect, face, style, i + 1)

    def save(self, path: str) -> None:
        self.img.save(path)


def new_icon(size: int = 16) -> Image.Image:
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))
