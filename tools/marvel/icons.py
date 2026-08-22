# -*- coding: utf-8 -*-
"""アイテムアイコン（32x32）を手続きで描く。

技アイコンは「暗い角丸の下地 + 技の基調色のリング + 技を表す図形」で統一する。
並んだときに一目で技だと判り、色で系統が判るのが狙い。
"""
from __future__ import annotations

import math

import _path  # noqa: F401

import contract as K  # noqa: E402
from PIL import Image  # noqa: E402

S = 32


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


class Icon:
    def __init__(self, size: int = S):
        self.s = size
        self.img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self.px = self.img.load()

    def put(self, x, y, c, a=255):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.s and 0 <= y < self.s:
            self.px[x, y] = (c[0], c[1], c[2], a)

    def blend(self, x, y, c, t, a=255):
        x, y = int(round(x)), int(round(y))
        if not (0 <= x < self.s and 0 <= y < self.s):
            return
        r, g, b, oa = self.px[x, y]
        if oa == 0:
            r, g, b = c
        self.put(x, y, (int(r + (c[0] - r) * t), int(g + (c[1] - g) * t),
                        int(b + (c[2] - b) * t)), max(oa, a))

    def rect(self, x0, y0, x1, y1, c, a=255):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.put(x, y, c, a)

    def disc(self, cx, cy, r, c, a=255):
        for y in range(int(cy - r), int(cy + r) + 1):
            for x in range(int(cx - r), int(cx + r) + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.put(x, y, c, a)

    def ring(self, cx, cy, r, c, thick=1.6, a=255):
        for y in range(int(cy - r - 1), int(cy + r) + 2):
            for x in range(int(cx - r - 1), int(cx + r) + 2):
                d = math.hypot(x - cx, y - cy)
                if r - thick <= d <= r:
                    self.put(x, y, c, a)

    def line(self, x0, y0, x1, y1, c, a=255, thick=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / max(1, n)
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            for dx in range(thick):
                for dy in range(thick):
                    self.put(x + dx, y + dy, c, a)

    def tri(self, pts, c, a=255):
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            for i in range(3):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % 3]
                if ay == by:
                    continue
                if min(ay, by) <= y <= max(ay, by):
                    xs.append(ax + (bx - ax) * (y - ay) / (by - ay))
            if len(xs) >= 2:
                for x in range(int(round(min(xs))), int(round(max(xs))) + 1):
                    self.put(x, y, c, a)

    def plate(self, base=(24, 20, 34), edge=(58, 48, 82)):
        """角を落とした下地。"""
        for y in range(self.s):
            for x in range(self.s):
                if (x + y < 4 or (self.s - 1 - x) + y < 4
                        or x + (self.s - 1 - y) < 4
                        or (self.s - 1 - x) + (self.s - 1 - y) < 4):
                    continue
                t = y / (self.s - 1)
                c = tuple(int(base[i] + (edge[i] - base[i]) * (1 - t) * 0.7)
                          for i in range(3))
                self.put(x, y, c)
        for x in range(4, self.s - 4):
            self.put(x, 1, edge)
        for y in range(4, self.s - 4):
            self.put(1, y, edge)

    def save(self, path):
        self.img.save(path)


# ===========================================================================
#  技のグリフ
# ===========================================================================
def glyph(ic: Icon, name: str, c, light):
    h = ic.s / 2

    def arrow(ang, r0, r1, size=3.0):
        ax, ay = h + math.cos(ang) * r0, h + math.sin(ang) * r0
        bx, by = h + math.cos(ang) * r1, h + math.sin(ang) * r1
        ic.line(ax, ay, bx, by, c, thick=2)
        px, py = -math.sin(ang), math.cos(ang)
        ic.tri([(bx + math.cos(ang) * size, by + math.sin(ang) * size),
                (bx + px * size * 0.8, by + py * size * 0.8),
                (bx - px * size * 0.8, by - py * size * 0.8)], light)

    if name == "repulse":
        ic.disc(h, h, 3.4, light)
        for i in range(6):
            arrow(i * math.pi / 3, 5.5, 11.5)
    elif name == "attract":
        ic.ring(h, h, 4.0, light, 1.6)
        for i in range(6):
            a = i * math.pi / 3
            bx, by = h + math.cos(a) * 6.0, h + math.sin(a) * 6.0
            ax, ay = h + math.cos(a) * 12.5, h + math.sin(a) * 12.5
            ic.line(ax, ay, bx, by, c, thick=2)
            px, py = -math.sin(a), math.cos(a)
            ic.tri([(bx - math.cos(a) * 3.0, by - math.sin(a) * 3.0),
                    (bx + px * 2.6, by + py * 2.6),
                    (bx - px * 2.6, by - py * 2.6)], light)
    elif name == "disarm":
        ic.line(8, 22, 22, 8, c, thick=3)          # 剣
        ic.line(18, 6, 25, 13, light, thick=2)
        ic.line(7, 7, 25, 25, (232, 96, 96), thick=2)   # 断ち切る線
    elif name == "lance":
        ic.tri([(h, 3), (h - 4, 14), (h + 4, 14)], light)
        ic.rect(h - 2, 13, h + 1, 27, c)
        ic.line(h - 5, 18, h + 5, 18, light)
    elif name == "flight":
        ic.tri([(h, 5), (h - 3, 16), (h + 3, 16)], light)
        for s in (-1, 1):
            ic.tri([(h + s * 2, 12), (h + s * 13, 20), (h + s * 3, 20)], c)
        ic.line(h - 6, 26, h + 6, 26, c, thick=2)
    elif name == "sight":
        ic.ring(h, h, 10, c, 1.8)
        ic.disc(h, h, 5.0, c)
        ic.disc(h, h, 2.6, light)
        for i in range(4):
            a = i * math.pi / 2 + math.pi / 4
            ic.line(h + math.cos(a) * 11, h + math.sin(a) * 11,
                    h + math.cos(a) * 14, h + math.sin(a) * 14, light)
    elif name == "barrier":
        pts = [(h + 11 * math.cos(math.pi / 3 * i - math.pi / 2),
                h + 11 * math.sin(math.pi / 3 * i - math.pi / 2))
               for i in range(6)]
        for i in range(6):
            ic.line(pts[i][0], pts[i][1], pts[(i + 1) % 6][0],
                    pts[(i + 1) % 6][1], c, thick=2)
        for i in range(6):
            ic.line(h, h, pts[i][0], pts[i][1], c)
        ic.disc(h, h, 2.4, light)
    elif name == "shard_storm":
        for i in range(7):
            a = i * math.pi * 2 / 7 + 0.3
            r = 6 + (i % 3) * 3
            ic.line(h + math.cos(a) * 3, h + math.sin(a) * 3,
                    h + math.cos(a) * (3 + r), h + math.sin(a) * (3 + r),
                    c, thick=2)
            ic.put(h + math.cos(a) * (3 + r), h + math.sin(a) * (3 + r), light)
        ic.disc(h, h, 2.6, light)
    elif name == "iron_bind":
        for i in range(4):
            x = 6 + i * 6.5
            ic.rect(x, 5, x + 1, 26, c)
        ic.rect(5, 8, 27, 9, light)
        ic.rect(5, 22, 27, 23, light)
    elif name == "crush":
        ic.ring(h, h, 11, c, 1.6)
        for i in range(8):
            a = i * math.pi / 4
            ic.line(h + math.cos(a) * 10, h + math.sin(a) * 10,
                    h + math.cos(a) * 5, h + math.sin(a) * 5, c, thick=2)
        ic.disc(h, h, 4.0, (232, 72, 96))
        ic.disc(h, h, 2.0, light)
    elif name == "uprising":
        ic.rect(3, 24, 28, 27, c)
        for i, (x, top) in enumerate(((7, 12), (14, 6), (22, 14))):
            ic.tri([(x, top), (x - 3, 24), (x + 3, 24)], c)
            ic.line(x, top, x, 24, light)
    elif name == "emp":
        ic.line(18, 4, 11, 16, light, thick=2)
        ic.line(11, 16, 17, 16, light, thick=2)
        ic.line(17, 16, 12, 28, light, thick=2)
        ic.ring(h, h, 12, c, 1.4)
        ic.ring(h, h, 8, c, 1.2)
    elif name == "polarity":
        ic.tri([(10, 4), (6, 13), (14, 13)], light)
        ic.rect(8, 12, 11, 27, c)
        ic.tri([(22, 28), (18, 19), (26, 19)], (120, 190, 255))
        ic.rect(20, 5, 23, 20, c)
    elif name == "throne":
        ic.rect(6, 20, 26, 24, c)
        ic.rect(4, 24, 28, 26, light)
        ic.rect(8, 8, 11, 20, c)
        ic.rect(21, 8, 24, 20, c)
        ic.rect(8, 8, 24, 10, light)
    elif name == "sphere":
        ic.disc(h, h, 9.5, c)
        ic.disc(h, h, 6.0, (240, 120, 150))
        ic.disc(h, h, 3.0, light)
        for i in range(8):
            a = i * math.pi / 4
            ic.line(h + math.cos(a) * 11, h + math.sin(a) * 11,
                    h + math.cos(a) * 14.5, h + math.sin(a) * 14.5, light,
                    thick=2)
    else:
        ic.ring(h, h, 9, c, 2.0)
        ic.disc(h, h, 3.0, light)


# ===========================================================================
#  中核アイテム
# ===========================================================================
def core_icon(ic: Icon, key: str):
    h = ic.s / 2
    if key == "x_gene":
        ic.rect(12, 4, 19, 7, (168, 176, 188))              # 蓋
        ic.rect(11, 7, 20, 28, (36, 40, 52))                # ガラス
        ic.rect(13, 12, 18, 27, (150, 92, 220))             # 中身
        for i in range(5):                                   # 二重螺旋
            y = 13 + i * 3
            ic.put(13 + int(2 + 2 * math.sin(i)), y, (232, 200, 255))
            ic.put(18 - int(2 + 2 * math.sin(i)), y, (232, 200, 255))
        ic.line(11, 7, 11, 28, (110, 118, 132))
    elif key == "magneto_helmet":
        # 画像の兜のシルエット
        ic.tri([(4, 26), (7, 5), (16, 16)], (140, 148, 160))
        ic.tri([(28, 26), (25, 5), (16, 16)], (140, 148, 160))
        ic.tri([(10, 26), (16, 13), (22, 26)], (92, 98, 110))
        ic.line(7, 5, 10, 26, (200, 208, 220), thick=2)
        ic.line(25, 5, 22, 26, (200, 208, 220), thick=2)
        ic.rect(13, 20, 18, 27, (226, 190, 158))            # 覗く顔
        ic.put(14, 22, (40, 40, 56))
        ic.put(17, 22, (40, 40, 56))
    elif key == "brotherhood_pin":
        ic.disc(h, h, 12, (30, 26, 36))
        ic.disc(h, h, 10, (142, 18, 36))
        ic.line(9, 9, 23, 23, (240, 240, 246), thick=3)
        ic.line(23, 9, 9, 23, (240, 240, 246), thick=3)
        ic.ring(h, h, 12, (180, 186, 198), 1.6)
    elif key == "cerebro":
        ic.ring(h, h + 2, 12, (150, 158, 172), 2.2)
        ic.rect(6, 12, 26, 18, (24, 28, 38))
        for x in range(7, 26):
            t = math.sin((x - 7) / 19 * math.pi)
            ic.blend(x, 14, (90, 210, 255), t)
            ic.blend(x, 15, (140, 230, 255), t)
        ic.rect(4, 10, 7, 20, (110, 118, 132))
        ic.rect(25, 10, 28, 20, (110, 118, 132))
    elif key == "brotherhood_beacon":
        ic.tri([(16, 3), (7, 16), (25, 16)], (196, 40, 62))
        ic.rect(7, 16, 25, 26, (52, 44, 64))
        ic.disc(16, 21, 4, (255, 120, 150))
        ic.disc(16, 21, 2, (255, 240, 250))
        for i in range(3):
            ic.line(3, 6 + i * 3, 7, 8 + i * 3, (255, 160, 180))
            ic.line(29, 6 + i * 3, 25, 8 + i * 3, (255, 160, 180))
    elif key == "metal_scrap":
        for (x, y, w, ht) in ((6, 14, 9, 5), (16, 9, 8, 6), (12, 20, 11, 5)):
            ic.rect(x, y, x + w, y + ht, (120, 128, 140))
            ic.rect(x, y, x + w, y + 1, (188, 196, 208))
            ic.rect(x, y + ht - 1, x + w, y + ht, (64, 70, 80))
    elif key == "magnetic_alloy":
        ic.tri([(4, 22), (10, 10), (28, 10)], (150, 158, 172))
        ic.rect(4, 22, 28, 26, (110, 118, 132))
        ic.tri([(22, 10), (28, 10), (28, 26)], (76, 82, 94))
        ic.rect(10, 10, 28, 12, (206, 212, 224))
        for i in range(3):
            ic.line(12 + i * 6, 13, 12 + i * 6, 21, (180, 124, 255))
    elif key == "sentinel_core":
        ic.disc(h, h, 12, (48, 40, 78))
        ic.ring(h, h, 12, (120, 104, 178), 2.0)
        ic.disc(h, h, 7, (255, 110, 50))
        ic.disc(h, h, 3.4, (255, 226, 180))
        for i in range(4):
            a = i * math.pi / 2 + math.pi / 4
            ic.line(h + math.cos(a) * 7, h + math.sin(a) * 7,
                    h + math.cos(a) * 12, h + math.sin(a) * 12,
                    (255, 180, 110), thick=2)
    elif key == "adamantium_ingot":
        ic.tri([(4, 22), (10, 10), (28, 10)], (206, 214, 226))
        ic.rect(4, 22, 28, 26, (168, 176, 190))
        ic.tri([(22, 10), (28, 10), (28, 26)], (120, 128, 142))
        ic.rect(10, 10, 28, 12, (250, 252, 255))
        ic.line(13, 14, 19, 20, (255, 255, 255), thick=2)
    else:
        ic.disc(h, h, 10, (110, 92, 158))
        ic.disc(h, h, 5, (198, 168, 255))


def form_icon(ic: Icon, character: str):
    """変身体アイテム — 普段は見えないので、影のシルエットで十分。"""
    pal = K.CHARACTERS[character]["egg"]
    base, accent = _hex(pal[0]), _hex(pal[1])
    ic.disc(16, 11, 6, base)
    ic.tri([(16, 15), (6, 30), (26, 30)], base)
    ic.disc(16, 11, 3.4, accent)
    ic.line(9, 24, 23, 24, accent)


def build_all():
    """全アイテムのアイコンを描いて保存し、item_texture 用の辞書を返す。"""
    K.ensure_dirs()
    atlas = {}

    def emit(key, painter):
        ic = Icon()
        painter(ic)
        ic.save(K.item_tex_path(key))
        atlas[key] = {"textures": f"textures/items/{key}"}

    for key in K.ITEMS:
        if key == "magneto_form":
            continue
        emit(key, lambda ic, k=key: core_icon(ic, k))

    for name, spec in K.TECHNIQUES.items():
        col = _hex(spec["colour"])
        light = tuple(min(255, int(v * 0.4 + 255 * 0.6)) for v in col)

        def paint(ic, c=col, li=light, n=name):
            ic.plate()
            ic.ring(ic.s / 2, ic.s / 2, 14.5, c, 1.4, 200)
            glyph(ic, n, c, li)
        emit(spec["item"], paint)

    for character, tech, _g, _n in K.form_variants():
        emit(K.form_key(character, tech),
             lambda ic, c=character: form_icon(ic, c))

    return atlas
