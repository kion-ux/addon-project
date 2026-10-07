# -*- coding: utf-8 -*-
"""アニメ調（セル塗り）の武器テクスチャを UV 矩形に直接描くペインタ。

* 面ごとに「明・中・暗」の 3 階調 + 1px の輪郭線でセル塗りの見え方を作る
* 発光部は entity_emissive_alpha の規約で **アルファを下げた texel** が光る
  （alpha 255 = 通常、alpha が低いほど自己発光）。EMI はほぼ全発光、SOFT は半発光
* 全ての描画は面ローカル座標 (x, y, w, h) で書くので、小さい部品にも
  uv_scale を上げればそのまま細部が乗る
"""
from __future__ import annotations

import math
import random
import zlib
from typing import Dict, Tuple

from PIL import Image

RGB = Tuple[int, int, int]
EMI = 12      # ほぼ全発光
SOFT = 150    # 半発光（縁の滲み）

FACE_LIGHT = {"up": 1.10, "down": 0.74, "north": 1.0, "south": 0.94,
              "east": 1.0, "west": 0.94}


def clamp(v, lo=0, hi=255):
    return int(max(lo, min(hi, v)))


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return (clamp(a[0] + (b[0] - a[0]) * t), clamp(a[1] + (b[1] - a[1]) * t),
            clamp(a[2] + (b[2] - a[2]) * t))


def shade(c, f):
    return (clamp(c[0] * f), clamp(c[1] * f), clamp(c[2] * f))


def hexc(s) -> RGB:
    if isinstance(s, (tuple, list)):
        return (int(s[0]), int(s[1]), int(s[2]))
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _h(text) -> int:
    return zlib.crc32(str(text).encode("utf-8"))


# 3x3 のルーン（古代文字風）。発光させて刃や柄に刻む
GLYPHS = [
    ("010", "111", "010"), ("101", "010", "101"), ("110", "011", "001"),
    ("011", "110", "100"), ("111", "101", "001"), ("100", "111", "001"),
    ("010", "101", "111"), ("111", "010", "011"), ("001", "111", "100"),
]


class HDPainter:
    def __init__(self, width: int, height: int, seed: int = 0):
        self.img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        self.px = self.img.load()
        self.w, self.h = width, height
        self.seed = seed

    def put(self, x, y, c, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[int(x), int(y)] = (clamp(c[0]), clamp(c[1]), clamp(c[2]), int(a))

    # ------------------------------------------------------------------
    def paint_model(self, model, styles: Dict[str, Dict]) -> None:
        for i, cube in enumerate(model.all_cubes()):
            st = styles.get(cube.style)
            if st is None:
                raise KeyError(f"{model.identifier}: no style '{cube.style}'")
            for face, rect in cube.rects.items():
                self.paint_face(rect, face, st, i)

    def paint_face(self, rect, face, st, key):
        x0, y0, w, h = rect
        if w <= 0 or h <= 0:
            return
        kind = st.get("kind", "flat")
        fn = getattr(self, "k_" + kind)
        rng = random.Random((self.seed * 131 + key * 7919) ^ _h(face))
        light = FACE_LIGHT.get(face, 1.0) if not st.get("unlit") else 1.0
        ctx = {"face": face, "w": w, "h": h, "rng": rng, "light": light, "key": key}
        outline = st.get("outline", True) and w >= 5 and h >= 5
        line = hexc(st.get("line", shade(hexc(st.get("base", (90, 90, 90))), 0.45)))
        for y in range(h):
            for x in range(w):
                c, a = fn(x, y, st, ctx)
                if st.get("opaque"):
                    a = 255
                if a > 200:
                    c = shade(c, light)
                    n = st.get("noise", 3)
                    if n:
                        d = rng.randint(-n, n)
                        c = (c[0] + d, c[1] + d, c[2] + d)
                    if outline and (x == 0 or y == 0 or x == w - 1 or y == h - 1):
                        c = mix(c, line, st.get("outline_k", 0.75))
                self.put(x0 + x, y0 + y, c, a)

    # ==================================================================
    #  塗りの種類（kind）— (x, y, st, ctx) -> (rgb, alpha)
    # ==================================================================
    def k_flat(self, x, y, st, c):
        return hexc(st["base"]), 255

    def _tones(self, st, v):
        base = hexc(st["base"])
        lt = hexc(st.get("light", shade(base, 1.35)))
        dk = hexc(st.get("dark", shade(base, 0.62)))
        if v < st.get("hi", 0.22):
            return lt
        if v > st.get("lo", 0.74):
            return dk
        return base

    def k_blade(self, x, y, st, c):
        """鏡面の刃。3 階調 + 斜めの映り込み + 芯に沿う細い溝。"""
        w, h = c["w"], c["h"]
        v = y / max(1, h - 1)
        col = self._tones(st, v)
        period = st.get("glint_period", 22)
        g = (x + y * 1.4 + (c["key"] * 7) % period) % period
        if g < 2.2:
            col = mix(col, hexc(st.get("light", (240, 240, 250))), 0.65)
        elif g < 3.4:
            col = mix(col, (255, 255, 255), 0.25)
        if st.get("fuller") and h >= 6 and abs(v - 0.5) < 0.6 / h * 2 and \
                c["face"] in ("east", "west"):
            col = shade(col, 0.78)
        return col, 255

    def k_edge(self, x, y, st, c):
        """刃先。白に近い発光色。外側ほど白く、内側は属性色に染まる。"""
        w, h = c["w"], c["h"]
        glow = hexc(st["glow"])
        t = abs(y / max(1, h - 1) - 0.5) * 2 if c["face"] in ("east", "west", "north", "south") \
            else abs(x / max(1, w - 1) - 0.5) * 2
        sat = st.get("sat", 0.25)
        col = mix((255, 255, 255), glow, sat + (1 - sat) * 0.75 * t)
        flick = (x * 3 + y * 5 + c["key"]) % 11 == 0
        if flick:
            col = mix(col, (255, 255, 255), 0.6)
        return col, st.get("emit", 70)

    def k_metal(self, x, y, st, c):
        """装甲板。3 階調・パネルライン・四隅のリベット。"""
        w, h = c["w"], c["h"]
        v = y / max(1, h - 1)
        col = self._tones(st, v)
        step = st.get("panel", 7)
        if w > step * 1.6 and x % step == step - 1:
            col = shade(col, 0.70)
        if h > step * 1.6 and y % step == step - 1:
            col = shade(col, 0.72)
        if w >= 8 and h >= 8 and st.get("rivets", True):
            for rx, ry in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):
                if x == rx and y == ry:
                    return hexc(st.get("light", (220, 220, 230))), 255
                if abs(x - rx) + abs(y - ry) == 1:
                    col = shade(col, 0.6)
        return col, 255

    def k_gold(self, x, y, st, c):
        """装飾金具。帯状の光沢と、細い菱形の彫り（フィリグリー）。"""
        v = y / max(1, c["h"] - 1)
        col = self._tones(st, v)
        if c["w"] >= 6 and c["h"] >= 4:
            if (x + y) % 6 == 0 or (x - y) % 6 == 0:
                col = shade(col, 0.80)
            if (x + y) % 6 == 3 and (x - y) % 6 == 3:
                col = mix(col, (255, 255, 230), 0.5)
        return col, 255

    def k_wrap(self, x, y, st, c):
        """柄巻。菱形に交差する組紐と、その隙間の鮫皮。"""
        base = hexc(st["base"])
        strap = hexc(st.get("strap", shade(base, 1.6)))
        p = st.get("period", 6)
        d1, d2 = (x + y) % p, (x - y) % p
        if d1 < 2 and d2 < 2:
            return mix(strap, (255, 255, 255), 0.2), 255
        if d1 < 2:
            return strap, 255
        if d2 < 2:
            return shade(strap, 0.78), 255
        skin = hexc(st.get("skin", shade(base, 1.0)))
        return (skin if (x * 7 + y * 3) % 5 else shade(skin, 1.2)), 255

    def k_gem(self, x, y, st, c):
        """宝玉。中心が白く、縁へ行くほど深い色。対角のファセット線。"""
        w, h = c["w"], c["h"]
        u = x / max(1, w - 1) - 0.5
        v = y / max(1, h - 1) - 0.5
        r = math.sqrt(u * u + v * v) * 2
        glow = hexc(st["glow"])
        deep = hexc(st.get("deep", shade(glow, 0.35)))
        if r < 0.32:
            col = mix((255, 255, 255), glow, r / 0.32 * 0.6)
        elif r < 0.75:
            col = mix(glow, deep, (r - 0.32) / 0.43 * 0.6)
        else:
            col = deep
        if w >= 4 and (abs(abs(u) - abs(v)) < 0.06):
            col = mix(col, (255, 255, 255), 0.35)
        if x == int(w * 0.3) and y == int(h * 0.3):
            col = (255, 255, 255)
        return col, (EMI if r < 0.78 else SOFT)

    def k_energy(self, x, y, st, c):
        """純粋なエネルギー。流れる縞と白熱した芯。全発光。"""
        w, h = c["w"], c["h"]
        glow = hexc(st["glow"])
        light = hexc(st.get("light", (255, 255, 255)))
        if c["face"] in ("east", "west", "up", "down"):
            along, across = x / max(1, w - 1), y / max(1, h - 1)
        else:
            along, across = y / max(1, h - 1), x / max(1, w - 1)
        core = 1 - abs(across - 0.5) * 2
        s = 0.5 + 0.5 * math.sin(along * st.get("waves", 9) * math.pi + across * 3 + c["key"])
        col = mix(glow, light, core * 0.65 + s * 0.25)
        return col, EMI

    def k_void(self, x, y, st, c):
        """次元の裂け目。深い紺に星が散る。星だけ光る。"""
        base = hexc(st["base"])
        glow = hexc(st["glow"])
        n = (x * 73856093 ^ y * 19349663 ^ c["key"] * 83492791) & 0xFFFF
        if n % 37 == 0:
            return (255, 255, 255), EMI
        if n % 11 == 0:
            return mix(base, glow, 0.7), EMI
        v = y / max(1, c["h"] - 1)
        return mix(base, shade(glow, 0.5), 0.25 * (1 - abs(v - 0.5) * 2)), SOFT

    def k_rune(self, x, y, st, c):
        """ルーン彫り。暗い地金に 3x3 の発光文字が並ぶ。"""
        w, h = c["w"], c["h"]
        base = hexc(st["base"])
        glow = hexc(st["glow"])
        horiz = w >= h
        along, across = (x, y) if horiz else (y, x)
        span = h if horiz else w
        if span >= 5:
            off = (span - 3) // 2
            cell, local = divmod(along, 5)
            ly = across - off
            if 0 <= ly < 3 and local < 3:
                g = GLYPHS[(cell * 5 + c["key"]) % len(GLYPHS)]
                gx, gy = (local, ly) if horiz else (ly, local)
                if g[gy][gx] == "1":
                    return mix(glow, (255, 255, 255), 0.35), EMI
        if (across == 0 or across == span - 1) and span >= 5:
            return shade(base, 1.5), 255
        return base, 255

    def k_crystal(self, x, y, st, c):
        """氷晶。ファセットで 3 面に割れ、白いハイライトが走る。半発光。"""
        w, h = c["w"], c["h"]
        base = hexc(st["base"])
        u, v = x / max(1, w - 1), y / max(1, h - 1)
        if u + v < 0.7:
            col = mix(base, (255, 255, 255), 0.45)
        elif u - v > 0.25:
            col = base
        else:
            col = shade(base, 0.78)
        if abs(u - v * 0.8 - 0.12) < 0.06:
            col = (250, 255, 255)
        return col, st.get("emit", SOFT)

    def k_cloth(self, x, y, st, c):
        """布・房飾り。縦のひだと、端の光る縁取り。"""
        base = hexc(st["base"])
        col = shade(base, 1.18) if x % 3 == 0 else (shade(base, 0.84) if x % 3 == 2 else base)
        if c["h"] >= 4 and y >= c["h"] - 2 and st.get("hem"):
            return hexc(st["hem"]), st.get("hem_emit", 255)
        return col, 255

    def k_dark(self, x, y, st, c):
        """黒鋼・黒曜。上辺にだけ属性色の照り返し。"""
        base = hexc(st["base"])
        glow = hexc(st.get("glow", (120, 120, 160)))
        v = y / max(1, c["h"] - 1)
        col = mix(base, glow, max(0.0, 0.32 - v) * 0.9)
        if (x * 5 + y * 3 + c["key"]) % 19 == 0:
            col = shade(col, 1.25)
        return col, 255

    def k_fur(self, x, y, st, c):
        base = hexc(st["base"])
        n = (x * 92821 ^ (y // 2) * 68917 ^ c["key"] * 31) % 7
        col = shade(base, 0.72 + n * 0.08)
        if y % 4 == 0 and n > 4:
            col = shade(base, 1.35)
        return col, 255

    def k_wood(self, x, y, st, c):
        base = hexc(st["base"])
        horiz = c["w"] >= c["h"]
        a, b = (x, y) if horiz else (y, x)
        ring = math.sin(b * 1.3 + math.sin(a * 0.21 + c["key"]) * 2.2)
        col = shade(base, 1.0 + 0.16 * ring)
        if (a + c["key"] * 13) % 29 == 0 and b % 5 == 2:
            col = shade(base, 0.6)
        return col, 255

    def k_straw(self, x, y, st, c):
        base = hexc(st["base"])
        n = (x * 31 + c["key"]) % 5
        col = shade(base, 0.8 + n * 0.08)
        if (y + x * 2) % 9 == 0:
            col = shade(base, 0.6)
        return col, 255

    def k_ivory(self, x, y, st, c):
        base = hexc(st["base"])
        v = y / max(1, c["h"] - 1)
        col = mix(shade(base, 1.08), shade(base, 0.82), v)
        if (x + c["key"]) % 9 == 0:
            col = shade(col, 0.92)
        return col, 255

    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        self.img.save(path, optimize=True)
