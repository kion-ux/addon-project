# -*- coding: utf-8 -*-
"""アニメ調（セル塗り）の武器テクスチャを UV 矩形に直接描くペインタ。

面ごとに次の順で重ねる:
  1. 素材（kind）ごとの塗り … 刃の刃文と樋、装甲のパネルとボルト、金の唐草彫り、
     組紐の立体的な柄巻、宝玉のファセット、流れるプラズマ、星雲の裂け目、氷のファセット…
  2. トゥーンの面取り … 上辺と左辺に 1px の照り返し、下辺と右辺に影、外周に輪郭線
  3. 発光 … entity_emissive_alpha の規約で、アルファを下げた texel が光る
     （alpha 255 = 通常、低いほど自己発光。EMI ≈ 全発光、SOFT ≈ 半発光）
全ての描画は面ローカル座標 (x, y, w, h) で書くので、uv_scale を上げればそのまま細かくなる。
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

FACE_LIGHT = {"up": 1.12, "down": 0.72, "north": 1.0, "south": 0.92,
              "east": 1.0, "west": 0.93}


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


def hash2(x, y, k=0):
    """座標の安定した擬似乱数 0..1。"""
    n = (int(x) * 374761393 + int(y) * 668265263 + k * 2246822519) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def vnoise(x, y, k=0):
    """値ノイズ（双線形補間）。"""
    xi, yi = math.floor(x), math.floor(y)
    fx, fy = x - xi, y - yi
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = hash2(xi, yi, k)
    b = hash2(xi + 1, yi, k)
    c = hash2(xi, yi + 1, k)
    d = hash2(xi + 1, yi + 1, k)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


def fbm(x, y, k=0, oct_=3):
    v, amp, f, tot = 0.0, 1.0, 1.0, 0.0
    for i in range(oct_):
        v += vnoise(x * f, y * f, k + i * 17) * amp
        tot += amp
        amp *= 0.5
        f *= 2.0
    return v / tot


# 5x5 のルーン（古代文字風）。発光させて刃や柄に刻む
GLYPHS5 = [
    ("00100", "01110", "10101", "00100", "00100"),
    ("10001", "01010", "00100", "01010", "10001"),
    ("11100", "00100", "01110", "00100", "00111"),
    ("01110", "10001", "10101", "10001", "01110"),
    ("10101", "10101", "11111", "00100", "00100"),
    ("11111", "00001", "01110", "10000", "11111"),
    ("00100", "01010", "11111", "01010", "00100"),
    ("10000", "11100", "10110", "10011", "10001"),
    ("01010", "11111", "01010", "11111", "01010"),
    ("00111", "00100", "11100", "00100", "11100"),
    ("10011", "10100", "11000", "10100", "10011"),
    ("01100", "10010", "11110", "10000", "01110"),
]
GLYPHS3 = [
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
        ctx = {"face": face, "w": w, "h": h, "rng": rng, "light": light, "key": key,
               "seed": (self.seed * 977 + key * 131 + _h(face)) & 0xFFFF}
        prep = getattr(self, "p_" + kind, None)
        if prep:
            prep(st, ctx)
        bevel = st.get("bevel", True) and w >= 4 and h >= 4
        outline = st.get("outline", True) and w >= 5 and h >= 5
        line = hexc(st.get("line", shade(hexc(st.get("base", (90, 90, 90))), 0.42)))
        for y in range(h):
            for x in range(w):
                c, a = fn(x, y, st, ctx)
                if st.get("opaque"):
                    a = 255
                if a > 200:
                    c = shade(c, light)
                    n = st.get("noise", 2)
                    if n:
                        d = rng.randint(-n, n)
                        c = (c[0] + d, c[1] + d, c[2] + d)
                    # トゥーンの面取り: 上・左に照り返し、下・右に影
                    if bevel:
                        if y == 1 or x == 1:
                            c = mix(c, (255, 255, 255), 0.18)
                        elif y == h - 2 or x == w - 2:
                            c = shade(c, 0.82)
                    if outline and (x == 0 or y == 0 or x == w - 1 or y == h - 1):
                        c = mix(c, line, st.get("outline_k", 0.78))
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
        hi, lo = st.get("hi", 0.22), st.get("lo", 0.74)
        if v < hi:
            return mix(lt, base, (v / max(hi, 1e-3)) ** 3 * 0.5)
        if v > lo:
            return mix(base, dk, 0.55 + 0.45 * (v - lo) / max(1e-3, 1 - lo))
        return base

    def _along_across(self, x, y, c):
        """面の長い方を「沿う」、短い方を「横切る」方向として返す（0..1）。"""
        w, h = c["w"], c["h"]
        if w >= h:
            return x / max(1, w - 1), y / max(1, h - 1), w, h
        return y / max(1, h - 1), x / max(1, w - 1), h, w

    # ---- 刃 -----------------------------------------------------------
    def k_blade(self, x, y, st, c):
        """鏡面の刃。3 階調 + 刃文（波打つ焼きの境）+ 樋 + 斜めの映り込み + 細かな擦り傷。"""
        along, across, L, S = self._along_across(x, y, c)
        col = self._tones(st, across)
        flat = (c["face"] in ("east", "west") or st.get("all_faces")) and not st.get("hamon_off")
        lt = hexc(st.get("light", (240, 240, 250)))
        if flat and S >= 6:
            # 刃文: 刃先側（across が 0 に近い側）に白く冴えた帯。境は波打つ
            wave = 0.30 + 0.07 * math.sin(along * L * 0.55 + c["key"]) \
                + 0.04 * math.sin(along * L * 1.7 + 2.0)
            if across < wave:
                col = mix(col, (250, 252, 255), 0.38 + 0.25 * (1 - across / wave))
            elif across < wave + 1.6 / S:
                col = mix(col, hexc(st.get("hamon", lt)), 0.55)
            # 樋（中央の溝）: 暗い線と、その下の照り返し
            if st.get("fuller", True) and S >= 8:
                mid = 0.60
                if abs(across - mid) < 0.6 / S:
                    col = shade(col, 0.66)
                elif abs(across - (mid + 1.0 / S)) < 0.55 / S:
                    col = mix(col, (255, 255, 255), 0.30)
        # 斜めの映り込み（二本組）
        period = st.get("glint_period", 26)
        g = (x + y * 1.3 + (c["key"] * 11) % period) % period
        if g < 1.6:
            col = mix(col, lt, 0.70)
        elif 3.0 < g < 3.9:
            col = mix(col, (255, 255, 255), 0.35)
        # 擦り傷
        if not st.get("hamon_off") and hash2(x // 2, y, c["seed"]) > 0.985:
            col = mix(col, (255, 255, 255), 0.25)
        return col, 255

    def k_edge(self, x, y, st, c):
        """刃先。白に近い発光色。外側ほど白く、内側は属性色に染まる。脈打つ光の粒。"""
        glow = hexc(st["glow"])
        along, across, L, S = self._along_across(x, y, c)
        t = abs(across - 0.5) * 2
        sat = st.get("sat", 0.25)
        col = mix((255, 255, 255), glow, sat + (1 - sat) * 0.75 * t)
        pulse = 0.5 + 0.5 * math.sin(along * L * 0.8 + c["key"])
        col = mix(col, (255, 255, 255), 0.25 * pulse * (1 - t))
        if hash2(x, y, c["seed"]) > 0.93:
            col = mix(col, (255, 255, 255), 0.6)
        return col, st.get("emit", 70)

    # ---- 装甲 ---------------------------------------------------------
    def k_metal(self, x, y, st, c):
        """装甲板。3 階調・浮き彫りのパネルライン・四隅のボルト・角の擦れ。"""
        w, h = c["w"], c["h"]
        v = y / max(1, h - 1)
        col = self._tones(st, v)
        col = shade(col, 0.94 + 0.12 * fbm(x * 0.35, y * 0.35, c["seed"], 2))
        step = st.get("panel", 7)
        lt = hexc(st.get("light", (220, 220, 230)))
        dk = hexc(st.get("dark", (40, 40, 50)))
        if w > step * 1.6:
            m = x % step
            if m == step - 1:
                col = mix(col, dk, 0.55)
            elif m == 0 and x > 0:
                col = mix(col, lt, 0.30)
        if h > step * 1.6:
            m = y % step
            if m == step - 1:
                col = mix(col, dk, 0.55)
            elif m == 0 and y > 0:
                col = mix(col, lt, 0.30)
        if w >= 9 and h >= 9 and st.get("rivets", True):
            for rx, ry in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):
                dx, dy = x - rx, y - ry
                if dx == 0 and dy == 0:
                    return mix(lt, (255, 255, 255), 0.3), 255
                if abs(dx) + abs(dy) == 1:
                    return (mix(lt, col, 0.4) if dx + dy < 0 else shade(col, 0.55)), 255
        # 角の擦れ（明るい点）
        edge = min(x, y, w - 1 - x, h - 1 - y)
        if edge <= 1 and hash2(x, y, c["seed"]) > 0.82:
            col = mix(col, lt, 0.45)
        return col, 255

    # ---- 金具 ---------------------------------------------------------
    def k_gold(self, x, y, st, c):
        """装飾金具。帯状の光沢、唐草の彫り（浮き彫り）、細かな打刻。"""
        w, h = c["w"], c["h"]
        v = y / max(1, h - 1)
        col = self._tones(st, v)
        if w >= 6 and h >= 4:
            # 唐草: 正弦で渦を描く彫り線。線の上側を明るく、下側を暗く
            s = math.sin(x * 0.9 + math.sin(y * 0.8 + c["key"]) * 2.2) * math.cos(y * 0.7 - x * 0.2)
            if 0.82 < s:
                col = shade(col, 0.72)
            elif 0.62 < s <= 0.82:
                col = mix(col, (255, 248, 200), 0.35)
            if (x + y) % 7 == 0 and (x - y) % 7 == 0:
                col = mix(col, (255, 255, 240), 0.6)
        return col, 255

    # ---- 柄巻 ---------------------------------------------------------
    def k_wrap(self, x, y, st, c):
        """柄巻。菱形に交差する組紐を立体的に（紐の中央が明るく、縁が暗い）、隙間に鮫皮。"""
        base = hexc(st["base"])
        strap = hexc(st.get("strap", shade(base, 1.6)))
        p = st.get("period", 6)
        d1, d2 = (x + y) % p, (x - y) % p
        def band(d):
            return 1 - abs(d - 0.75) / 1.25
        if d1 < 2 and d2 < 2:
            # 交点: 上に重なる紐（交互）
            top = ((x + y) // p + (x - y) // p) % 2
            b = band(d1 if top else d2)
            return mix(shade(strap, 0.8), mix(strap, (255, 255, 255), 0.25), b), 255
        if d1 < 2:
            return mix(shade(strap, 0.7), strap, band(d1)), 255
        if d2 < 2:
            return mix(shade(strap, 0.6), shade(strap, 0.92), band(d2)), 255
        skin = hexc(st.get("skin", shade(base, 1.0)))
        dots = hash2(x, y, c["seed"]) > 0.6
        return (mix(skin, (255, 255, 255), 0.18) if dots else shade(skin, 0.86)), 255

    # ---- 宝玉 ---------------------------------------------------------
    def k_gem(self, x, y, st, c):
        """宝玉。8 枚のファセットで明暗を割り、中心に白い輝き、内部に星のきらめき。"""
        w, h = c["w"], c["h"]
        u = x / max(1, w - 1) - 0.5
        v = y / max(1, h - 1) - 0.5
        r = math.sqrt(u * u + v * v) * 2
        glow = hexc(st["glow"])
        deep = hexc(st.get("deep", shade(glow, 0.35)))
        ang = math.atan2(v, u)
        facet = int(((ang + math.pi) / (2 * math.pi)) * 8) % 8
        fb = (0.55, 0.85, 1.0, 0.75, 0.45, 0.35, 0.5, 0.7)[facet]
        if r < 0.28:
            col = mix((255, 255, 255), glow, r / 0.28 * 0.5)
        elif r < 0.8:
            col = mix(mix(deep, glow, fb), shade(glow, 0.6), (r - 0.28) / 0.52 * 0.4)
        else:
            col = shade(deep, 0.8)
        # ファセットの稜線
        if w >= 5 and abs(((ang + math.pi) / (2 * math.pi) * 8) % 1.0 - 0.0) < 0.07 and r > 0.3:
            col = mix(col, (255, 255, 255), 0.35)
        # 左上のハイライト
        if abs(u + 0.22) < 0.09 and abs(v + 0.22) < 0.09:
            col = (255, 255, 255)
        if hash2(x, y, c["seed"]) > 0.96 and r < 0.75:
            col = mix(col, (255, 255, 255), 0.8)
        return col, (EMI if r < 0.8 else SOFT)

    # ---- エネルギー ----------------------------------------------------
    def k_energy(self, x, y, st, c):
        """プラズマ。うねる縞（多重の正弦）と白熱した芯。全発光。"""
        glow = hexc(st["glow"])
        light = hexc(st.get("light", (255, 255, 255)))
        along, across, L, S = self._along_across(x, y, c)
        core = 1 - abs(across - 0.5) * 2
        k = c["key"]
        flow = (math.sin(along * st.get("waves", 9) * math.pi + across * 3 + k)
                + 0.6 * math.sin(along * 23.0 - across * 5 + k * 1.7)
                + 0.4 * fbm(along * L * 0.25, across * S * 0.5, c["seed"], 2) * 2 - 0.4)
        s = 0.5 + 0.25 * flow
        col = mix(shade(glow, 0.85), light, max(0.0, core) ** 1.2 * 0.75 + s * 0.3)
        return col, EMI

    def k_void(self, x, y, st, c):
        """次元の裂け目。深い紺に二色の星雲がたなびき、大小の星（十字の輝き）が散る。"""
        base = hexc(st["base"])
        glow = hexc(st["glow"])
        neb2 = hexc(st.get("nebula", (150, 70, 220)))
        n = fbm(x * 0.18, y * 0.32, c["seed"], 3)
        m = fbm(x * 0.11 + 7, y * 0.21 + 3, c["seed"] + 5, 3)
        col = mix(base, shade(glow, 0.55), max(0.0, n - 0.45) * 1.6)
        col = mix(col, shade(neb2, 0.6), max(0.0, m - 0.55) * 1.8)
        r = hash2(x, y, c["seed"])
        if r > 0.985:
            return (255, 255, 255), EMI
        if r > 0.965:
            return mix(glow, (255, 255, 255), 0.5), EMI
        # 大きな星: 十字の光芒
        for sx, sy in ((5, 2), (17, 1), (29, 3), (41, 1)):
            if c["w"] > sx + 2:
                dx, dy = abs(x - sx), abs(y - sy % max(1, c["h"]))
                if dx + dy == 0:
                    return (255, 255, 255), EMI
                if (dx == 0 and dy <= 1) or (dy == 0 and dx <= 2):
                    return mix(glow, (255, 255, 255), 0.6), EMI
        return col, SOFT

    # ---- ルーン -------------------------------------------------------
    def k_rune(self, x, y, st, c):
        """ルーン彫り。暗い地金、光る内枠、5x5（細い面は 3x3）の発光文字が並ぶ。"""
        w, h = c["w"], c["h"]
        base = hexc(st["base"])
        glow = hexc(st["glow"])
        horiz = w >= h
        along, across = (x, y) if horiz else (y, x)
        span = h if horiz else w
        length = w if horiz else h
        col = shade(base, 0.92 + 0.12 * fbm(x * 0.3, y * 0.3, c["seed"], 2))
        if span >= 9:
            g, gs, cell = GLYPHS5, 5, 7
        elif span >= 5:
            g, gs, cell = GLYPHS3, 3, 5
        else:
            return col, 255
        off = (span - gs) // 2
        idx, local = divmod(along - 1, cell)
        ly = across - off
        if 0 <= ly < gs and 0 <= local < gs and along < length - 1:
            glyph = g[(idx * 5 + c["key"]) % len(g)]
            gx, gy = (local, ly) if horiz else (ly, local)
            if glyph[gy][gx] == "1":
                return mix(glow, (255, 255, 255), 0.35), EMI
            # 文字の周りの淡い滲み
            return mix(col, glow, 0.22), 255
        # 内枠の光る線
        if span >= 7 and (across == 1 or across == span - 2):
            return mix(glow, col, 0.35), SOFT
        return col, 255

    # ---- 氷晶 ---------------------------------------------------------
    def k_crystal(self, x, y, st, c):
        """氷晶。3 枚のファセット、内部のひび（明るい線）、下へ行くほど属性色に光る。"""
        w, h = c["w"], c["h"]
        base = hexc(st["base"])
        u, v = x / max(1, w - 1), y / max(1, h - 1)
        if u + v < 0.7:
            col = mix(base, (255, 255, 255), 0.5)
        elif u - v > 0.25:
            col = base
        else:
            col = shade(base, 0.78)
        if abs(u - v * 0.8 - 0.12) < 0.05 or abs(u + v * 0.6 - 0.95) < 0.04:
            col = (250, 255, 255)
        crack = math.sin(x * 1.3 + y * 0.4 + c["key"]) * math.cos(y * 1.1 - x * 0.3)
        if crack > 0.93:
            col = mix(col, (255, 255, 255), 0.6)
        glow = hexc(st.get("glow", base))
        col = mix(col, glow, 0.25 * v)
        return col, st.get("emit", SOFT)

    # ---- 布 -----------------------------------------------------------
    def k_cloth(self, x, y, st, c):
        """布・房飾り。織り目、縦のひだ、端の刺繍（菱形の連続）と光る縁取り。"""
        base = hexc(st["base"])
        fold = math.sin(x * 1.1 + c["key"]) * 0.12
        col = shade(base, 1.0 + fold)
        if (x + y) % 2 == 0:
            col = shade(col, 1.06)
        h = c["h"]
        if h >= 6 and st.get("hem"):
            if y >= h - 2:
                return hexc(st["hem"]), st.get("hem_emit", 255)
            if y >= h - 5 and (x + y) % 4 == 0:
                return mix(hexc(st["hem"]), col, 0.4), 255
        return col, 255

    # ---- 黒鋼 ---------------------------------------------------------
    def k_dark(self, x, y, st, c):
        """黒鋼・黒曜。上辺の照り返し、艶の斜線、属性色に淡く光るひび。"""
        base = hexc(st["base"])
        glow = hexc(st.get("glow", (120, 120, 160)))
        v = y / max(1, c["h"] - 1)
        col = mix(base, glow, max(0.0, 0.30 - v) * 0.9)
        if (x * 2 + y) % 23 < 2:
            col = shade(col, 1.45)
        vein = fbm(x * 0.25, y * 0.25, c["seed"], 3)
        if 0.495 < vein < 0.515 and st.get("veins", True):
            return mix(glow, (255, 255, 255), 0.2), SOFT
        return col, 255

    def k_fur(self, x, y, st, c):
        base = hexc(st["base"])
        strand = hash2(x, y // 3, c["seed"])
        col = shade(base, 0.70 + strand * 0.45)
        if y % 3 == 0 and strand > 0.6:
            col = mix(col, (240, 228, 210), 0.35)    # 毛先
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
        """象牙・牙。根元から先へのグラデーション、成長線、細いひび。"""
        base = hexc(st["base"])
        v = y / max(1, c["h"] - 1)
        col = mix(shade(base, 1.08), shade(base, 0.80), v)
        if (y + int(math.sin(x * 0.7) * 2)) % 5 == 0:
            col = shade(col, 0.92)
        if hash2(x, y, c["seed"]) > 0.97:
            col = shade(col, 0.75)
        return col, 255

    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        self.img.save(path, optimize=True)
