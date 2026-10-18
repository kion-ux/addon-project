# -*- coding: utf-8 -*-
"""アストロ・ナノギア — メカ用のセル塗りテクスチャペインタ。

hd_paint.HDPainter（アニメ調の武器ペインタ）を継承し、スーツ・ウェポン・コアに要る素材（kind）を足す。
面ごとに次の順で重ねる:
  1. 素材（kind）ごとの塗り … 装甲のグラデーション・パネルライン・ボルト、六角メッシュのインナー、
     鏡面の映り込み、バイザーの照り返し、発光ライン、排気口、ノズル、惑星の星核…
  2. トゥーンの面取り … 上辺と左辺に 1px の照り、下辺と右辺に影、外周に輪郭線
  3. デカール … 警告ストライプ・型番・紋章（キューブの decals={"north": "serial"} 等、または kind "decal"）
発光は entity_emissive_alpha の規約: アルファ 255 = 通常、低いほど自己発光（EMI ≈ 全発光、SOFT ≈ 半発光）。

スタイル（cube.style の名前 → 辞書）は suit_styles / weapon_styles / core_styles が惑星の配色から作る。
惑星ごとの上書きは `suit_styles("earth", plate={"panel": 6}, mystyle={"kind": "armor", "base": (..)})`。

主な kind と、辞書で効くキー（色は (r,g,b) か "#rrggbb"）:
  armor / armor2  base light dark line / panel(パネル線の間隔 px, 0 で無し) / bolts / sheen(斜めの照り) /
                  stripe={"dir":"h|v|d","period":8,"width":3,"color":(..),"glow":False} / trim=(色)（下辺の帯）
  inner           base glow / hex(六角の半径 px) / seam(発光する継ぎ目の割合 0..1)
  frame           base light / ribs(溝の間隔)
  chrome          base(色味) light
  visor           glow light deep / emit
  glowline        glow light / emit
  vent            base glow deep / slat(間隔)
  thruster        base glow light deep
  core / planet   planet="earth" 等（mercury venus earth mars jupiter saturn uranus neptune sol luna）
                  halo(外周の発光の輪) / bezel(角の色) / spin(経度のずれ 度)
  flame           glow light deep / dir="down|up|north|..."（炎の先の向き。面の局所 y の向きに合わせる）
  cloth           base hem shadow / cloud(下端の雲の縁取り)
  trim            base light dark（金具。照りの帯と刻線）
  decal           under=（下地のスタイル辞書） decal="hazard|serial|emblem|chevron|stripe|lights" text=...
  crystal / ice / gem / energy / blade / edge / metal / gold / wrap / rune / void …（hd_paint のもの）
"""
from __future__ import annotations

import math
import os
import sys
from typing import Dict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import astro_common  # noqa: E402,F401  (sys.path 設定)
from astro_data import PLANETS  # noqa: E402
from hd_paint import (EMI, SOFT, FACE_LIGHT, HDPainter, _h, clamp, fbm, hash2,  # noqa: E402,F401
                      hexc, mix, shade, vnoise)

import random  # noqa: E402

WHITE = (255, 255, 255)
SQ3 = math.sqrt(3.0)


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / ((e1 - e0) or 1e-6)))
    return t * t * (3 - 2 * t)


# 3x5 のドット文字（型番・注意書き）
FONT35 = {
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111",
    "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
    "6": "111100111101111", "7": "111001010010010", "8": "111101111101111",
    "9": "111101111001111", "A": "010101111101101", "B": "110101110101110",
    "C": "011100100100011", "D": "110101101101110", "E": "111100110100111",
    "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
    "I": "111010010010111", "J": "001001001101010", "K": "101110100110101",
    "L": "100100100100111", "M": "101111111101101", "N": "110101101101101",
    "O": "010101101101010", "P": "110101110100100", "Q": "010101101110011",
    "R": "110101110110101", "S": "011100010001110", "T": "111010010010010",
    "U": "101101101101111", "V": "101101101101010", "W": "101101111111101",
    "X": "101101010101101", "Y": "101101010010010", "Z": "111001010100111",
    "-": "000000111000000", ".": "000000000000010", "/": "001001010100100",
    " ": "000000000000000", "+": "000010111010000", "#": "101111101111101",
}


def text_width(text):
    return len(text) * 4 - 1


# ---------------------------------------------------------------------------
#  惑星の模様（core / planet）。lon, lat はラジアン、(px,py,pz) は球面上の点
# ---------------------------------------------------------------------------
def _n3(px, py, pz, f, k, oct_=3):
    """3 次元っぽいノイズ（2 平面の fbm の和）。球の継ぎ目が出ないように。"""
    return 0.5 * fbm(px * f + 11.3, py * f + pz * 0.7 * f, k, oct_) + \
        0.5 * fbm(pz * f - 4.1, py * f - px * 0.6 * f, k + 3, oct_)


def planet_color(name, lon, lat, P, seed=0):
    """惑星 name の表面色（発光させる前の色）を返す。"""
    px, py, pz = P
    if name == "earth":
        n = _n3(px, py, pz, 2.2, 7, 4)
        ice = abs(lat) > 1.18 + 0.08 * math.sin(lon * 5)
        if ice:
            col = (236, 246, 255)
        elif n > 0.53:
            hgt = (n - 0.53) / 0.2
            col = mix((70, 168, 70), (160, 150, 92), smooth(0.35, 0.9, hgt))
            if abs(lat) < 0.35 and n > 0.6:
                col = mix(col, (196, 170, 104), 0.5)       # 砂漠
        elif n > 0.5:
            col = (60, 150, 200)                           # 浅瀬
        else:
            col = mix((22, 70, 170), (14, 46, 128), smooth(0.3, 0.5, 0.5 - n + 0.3))
        cl = _n3(px * 1.4 + 3, py * 2.6, pz * 1.4, 2.0, 21, 3)
        swirl = math.sin(lat * 7 + cl * 6 + lon * 1.5)
        if cl > 0.56 or (swirl > 0.86 and cl > 0.47):
            col = mix(col, (250, 252, 255), 0.85)
        return col
    if name == "mercury":
        r = math.sin(lon * 9 + math.sin(lat * 7) * 2) * 0.5 + 0.5
        n = _n3(px, py, pz, 3.0, 5, 3)
        col = mix((120, 128, 142), (236, 242, 250), 0.35 + 0.45 * r * n + 0.25 * n)
        if n > 0.66:
            col = mix(col, (255, 255, 255), 0.6)
        return col
    if name == "venus":
        tw = lat * 5 + _n3(px, py, pz, 2.4, 9, 3) * 5 + lon * 0.8
        b = 0.5 + 0.5 * math.sin(tw)
        return mix(mix((206, 150, 56), (246, 220, 140), b), (255, 246, 214),
                   max(0.0, math.sin(tw * 2.1 + 1)) * 0.35)
    if name == "mars":
        n = _n3(px, py, pz, 2.6, 13, 4)
        col = mix((206, 92, 44), (150, 52, 26), smooth(0.45, 0.7, n))
        if n < 0.38:
            col = mix(col, (232, 140, 84), 0.5)
        if lat > 1.15 + 0.06 * math.sin(lon * 6):
            col = (250, 240, 236)
        cr = hash2(int(lon * 18), int(lat * 18), 3)
        if cr > 0.93:
            col = shade(col, 0.78)
        return col
    if name == "jupiter":
        t = lat * 9 + 0.6 * math.sin(lon * 3 + lat * 4) + _n3(px, py, pz, 3, 17, 2) * 1.6
        band = math.sin(t)
        col = mix((236, 220, 190), (176, 112, 70), smooth(-0.2, 0.6, band))
        if abs(lat) < 0.12:
            col = mix(col, (250, 240, 220), 0.4)
        dl, dt = lon - 0.55, lat + 0.36
        e = (dl / 0.42) ** 2 + (dt / 0.2) ** 2
        if e < 1.0:
            col = mix((222, 92, 52), (190, 60, 40), e)
            if e < 0.25:
                col = mix(col, (240, 140, 90), 0.5)
        elif e < 1.4:
            col = mix(col, (250, 236, 214), 0.6)
        return col
    if name == "saturn":
        t = lat * 8 + _n3(px, py, pz, 2, 19, 2) * 0.8
        band = math.sin(t)
        return mix((246, 226, 170), (204, 166, 96), smooth(-0.3, 0.8, band) * 0.8)
    if name == "uranus":
        b = 0.5 + 0.5 * math.sin(lat * 4 + _n3(px, py, pz, 1.6, 23, 2) * 1.2)
        col = mix((150, 228, 232), (200, 246, 246), b * 0.6)
        if lat > 1.0:
            col = mix(col, (236, 255, 255), 0.6)
        return col
    if name == "neptune":
        n = _n3(px, py, pz, 2.0, 29, 3)
        col = mix((30, 70, 200), (60, 120, 236), smooth(0.4, 0.7, n))
        st = math.sin(lat * 14 + lon * 2 + n * 4)
        if st > 0.92:
            col = mix(col, (230, 244, 255), 0.75)
        dl, dt = lon + 0.35, lat + 0.3
        e = (dl / 0.34) ** 2 + (dt / 0.17) ** 2
        if e < 1.0:
            col = mix((14, 28, 92), (24, 50, 140), e)
        return col
    if name == "sol":
        # 粒状斑: セル（ボロノイ風）の明るい中心と暗い境
        f = 7.0
        gx, gy = lon * f, lat * f
        best, second = 9.0, 9.0
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                cx, cy = math.floor(gx) + ox, math.floor(gy) + oy
                fx = cx + hash2(cx, cy, 41)
                fy = cy + hash2(cx, cy, 43)
                d = (gx - fx) ** 2 + (gy - fy) ** 2
                if d < best:
                    best, second = d, best
                elif d < second:
                    second = d
        edge = math.sqrt(second) - math.sqrt(best)
        col = mix((255, 150, 30), (255, 236, 150), smooth(0.05, 0.45, edge))
        pl = _n3(px, py, pz, 2.0, 47, 3)
        if pl > 0.6:
            col = mix(col, (255, 255, 236), (pl - 0.6) * 2.2)
        return col
    if name == "luna":
        n = _n3(px, py, pz, 2.0, 53, 3)
        col = mix((176, 178, 184), (120, 122, 132), smooth(0.48, 0.62, n))   # 海（暗い所）
        # クレーター: 格子ごとに 1 個、暗い底と明るい縁
        f = 4.5
        gx, gy = lon * f, lat * f
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                cx, cy = math.floor(gx) + ox, math.floor(gy) + oy
                if hash2(cx, cy, 61) < 0.45:
                    continue
                fx = cx + 0.2 + 0.6 * hash2(cx, cy, 62)
                fy = cy + 0.2 + 0.6 * hash2(cx, cy, 63)
                rr = 0.18 + 0.2 * hash2(cx, cy, 64)
                d = math.hypot(gx - fx, gy - fy)
                if d < rr * 0.75:
                    col = shade(col, 0.74)
                elif d < rr:
                    col = mix(col, (226, 228, 232), 0.55 if (gy - fy) < 0 else 0.0) \
                        if (gy - fy) < 0 else shade(col, 0.86)
        return col
    return (180, 180, 180)


ATMOS = {"earth": (120, 190, 255), "venus": (255, 236, 160), "mars": (255, 170, 120),
         "jupiter": (250, 230, 200), "saturn": (255, 240, 200), "uranus": (210, 255, 255),
         "neptune": (120, 180, 255), "sol": (255, 220, 120), "mercury": (230, 236, 246),
         "luna": (220, 222, 228)}


class AstroPainter(HDPainter):
    """HDPainter + メカの素材。paint_model(model, styles) で全キューブを塗る。"""

    def __init__(self, width: int, height: int, seed: int = 0):
        super().__init__(width, height, seed)

    # ------------------------------------------------------------------
    def paint_model(self, model, styles: Dict[str, Dict]) -> None:
        for i, cube in enumerate(model.all_cubes()):
            st = styles.get(cube.style)
            if st is None:
                raise KeyError(f"{model.identifier}: no style '{cube.style}'")
            dec = getattr(cube, "decals", {}) or {}
            for face, rect in cube.rects.items():
                d = dec.get(face)
                self.paint_face(rect, face, st, i, decals=([d] if isinstance(d, (str, dict))
                                                         else list(d or [])),
                                cube=cube)

    def paint_face(self, rect, face, st, key, decals=(), cube=None):
        x0, y0, w, h = rect
        if w <= 0 or h <= 0:
            return
        kind = st.get("kind", "flat")
        if kind == "decal":
            under = dict(st.get("under", {"kind": "armor", "base": (200, 200, 200)}))
            spec = {k: v for k, v in st.items() if k not in ("kind", "under")}
            self.paint_face(rect, face, under, key, cube=cube)
            self.decal(rect, face, spec, under, key)
            for d in decals:
                self.decal(rect, face, d, under, key)
            return
        fn = getattr(self, "k_" + kind)
        rng = random.Random((self.seed * 131 + key * 7919) ^ _h(face))
        light = FACE_LIGHT.get(face, 1.0) if not st.get("unlit") else 1.0
        ctx = {"face": face, "w": w, "h": h, "rng": rng, "light": light, "key": key,
               "seed": (self.seed * 977 + key * 131 + _h(face)) & 0xFFFF, "cube": cube}
        prep = getattr(self, "p_" + kind, None)
        if prep:
            prep(st, ctx)
        bevel = st.get("bevel", True) and w >= 4 and h >= 4
        outline = st.get("outline", True) and w >= 3 and h >= 3
        base = hexc(st.get("base", (90, 90, 90)))
        line = hexc(st.get("line", shade(base, 0.38)))
        ok = st.get("outline_k", 0.72)
        noise = st.get("noise", 0)
        hi_k = st.get("bevel_hi", 0.30)
        lo_k = st.get("bevel_lo", 0.78)
        for y in range(h):
            for x in range(w):
                c, a = fn(x, y, st, ctx)
                if st.get("opaque"):
                    a = 255
                if a > 200:
                    c = shade(c, light)
                    if noise:
                        d = rng.randint(-noise, noise)
                        c = (c[0] + d, c[1] + d, c[2] + d)
                    if bevel:
                        if y == 1 or x == 1:
                            c = mix(c, WHITE, hi_k)
                        elif y == h - 2 or x == w - 2:
                            c = shade(c, lo_k)
                    if outline and (x == 0 or y == 0 or x == w - 1 or y == h - 1):
                        c = mix(c, line, ok)
                elif outline and st.get("emit_outline") and (
                        x == 0 or y == 0 or x == w - 1 or y == h - 1):
                    c = mix(c, hexc(st["emit_outline"]), 0.6)
                self.put(x0 + x, y0 + y, c, a)
        for d in decals:
            self.decal(rect, face, d, st, key)

    # ==================================================================
    #  装甲
    # ==================================================================
    def p_armor(self, st, c):
        """パネルの割り付けを面ごとに一度だけ決める。"""
        w, h = c["w"], c["h"]
        rng = random.Random(c["seed"] * 31 + 7)
        c["panels"] = []
        step = st.get("panel", 1)
        if not step:
            return
        if w >= 9 and h >= 9:
            ins = max(2, min(w, h) // 6)
            c["panels"].append(("rect", ins, ins, w - 1 - ins, h - 1 - ins,
                                max(1, min(w, h) // 7)))
            # 長い面は継ぎ目で 2〜3 枚に割る
            if w >= 2.2 * h and w >= 20:
                n = 2 + (w >= 40)
                for k in range(1, n):
                    c["panels"].append(("vseam", int(w * k / n) + rng.randint(-1, 1)))
            elif h >= 2.2 * w and h >= 20:
                n = 2 + (h >= 40)
                for k in range(1, n):
                    c["panels"].append(("hseam", int(h * k / n) + rng.randint(-1, 1)))
        elif w >= 14 and h >= 5:
            c["panels"].append(("vseam", w // 2 + rng.randint(-2, 2)))
        elif h >= 14 and w >= 5:
            c["panels"].append(("hseam", h // 2 + rng.randint(-2, 2)))

    p_armor2 = p_armor
    p_decal = None

    def _armor_tone(self, x, y, st, c):
        w, h = c["w"], c["h"]
        base = hexc(st["base"])
        lt = hexc(st.get("light", mix(base, WHITE, 0.42)))
        dk = hexc(st.get("dark", shade(base, 0.66)))
        v = y / max(1, h - 1)
        face = c["face"]
        if face == "up":
            col = mix(base, lt, 0.35)
        elif face == "down":
            col = mix(base, dk, 0.35)
        else:
            hi, lo = st.get("hi", 0.28), st.get("lo", 0.72)
            if v < hi:
                col = mix(lt, base, smooth(0.0, hi, v) * 0.85 + 0.15)
            elif v > lo:
                col = mix(base, dk, smooth(lo, 1.0, v) * 0.7)
            else:
                col = base
        # アニメ調の斜めの照り（左上の面に 1〜2 本）
        if st.get("sheen", True) and w >= 7 and h >= 5 and face not in ("down",):
            p = (x * 0.8 + y * 1.0 + c["key"] * 5) % max(18, w + h)
            if p < 1.4:
                col = mix(col, WHITE, 0.22)
            elif 2.6 < p < 3.3:
                col = mix(col, WHITE, 0.10)
        return col, lt, dk

    def _stripe(self, x, y, st, c, col):
        s = st.get("stripe")
        if not s:
            return col, 255
        per = s.get("period", 8)
        wid = s.get("width", 3)
        d = s.get("dir", "h")
        q = {"h": y, "v": x, "d": x + y, "a": x - y + 1000}[d] + s.get("offset", 0)
        if q % per < wid:
            sc = hexc(s.get("color", shade(hexc(st["base"]), 0.7)))
            if s.get("glow"):
                return mix(sc, WHITE, 0.3 if q % per == wid // 2 else 0.0), s.get("emit", SOFT)
            return mix(col, sc, s.get("k", 0.85)), 255
        return col, 255

    def k_armor(self, x, y, st, c):
        """主装甲。グラデーション・斜めの照り・面取りのパネル線（彫り: 暗線+明線）・ボルト。"""
        w, h = c["w"], c["h"]
        col, lt, dk = self._armor_tone(x, y, st, c)
        a = 255
        groove = hexc(st.get("groove", shade(hexc(st["base"]), 0.5)))
        for pan in c.get("panels", ()):
            if pan[0] == "rect":
                _, ax, ay, bx, by, cut = pan
                # 角を斜めに落とした矩形の彫り
                inside = ax <= x <= bx and ay <= y <= by
                if inside:
                    dx = min(x - ax, bx - x)
                    dy = min(y - ay, by - y)
                    corner = dx + dy
                    if corner == cut or (corner > cut and (dx == 0 or dy == 0)):
                        col = mix(col, groove, 0.75)
                    elif corner == cut + 1 and (x - ax <= bx - x) == (y - ay <= by - y) and \
                            (x - ax <= bx - x):
                        col = mix(col, WHITE, 0.25)
                    elif (dx == 1 and x - ax == 1) or (dy == 1 and y - ay == 1):
                        if corner > cut:
                            col = mix(col, WHITE, 0.22)
                    # ボルト（パネルの四隅の内側）
                    if st.get("bolts", True) and w >= 16 and h >= 14:
                        for bx_, by_ in ((ax + cut + 2, ay + 2), (bx - cut - 2, ay + 2),
                                         (ax + 2, by - cut - 2), (bx - 2, by - cut - 2)):
                            if x == bx_ and y == by_:
                                return mix(lt, WHITE, 0.5), 255
                            if x == bx_ + 1 and y == by_ + 1:
                                return shade(col, 0.6), 255
            elif pan[0] == "vseam" and x == pan[1]:
                col = mix(col, groove, 0.75)
            elif pan[0] == "vseam" and x == pan[1] + 1:
                col = mix(col, WHITE, 0.2)
            elif pan[0] == "hseam" and y == pan[1]:
                col = mix(col, groove, 0.75)
            elif pan[0] == "hseam" and y == pan[1] + 1:
                col = mix(col, WHITE, 0.2)
        tr = st.get("trim")
        if tr and h >= 6 and c["face"] not in ("up", "down") and y >= h - max(2, h // 8) - 1 \
                and y < h - 1:
            col = mix(hexc(tr), WHITE, 0.25 if y == h - max(2, h // 8) - 1 else 0.0)
        col, a = self._stripe(x, y, st, c, col)
        return col, a

    def k_armor2(self, x, y, st, c):
        return self.k_armor(x, y, st, c)

    # ==================================================================
    #  インナー（六角メッシュ）
    # ==================================================================
    def k_inner(self, x, y, st, c):
        base = hexc(st["base"])
        glow = hexc(st.get("glow", (90, 200, 255)))
        R = st.get("hex", 2.6)
        # pointy-top の六角格子に丸める
        q = (SQ3 / 3 * x - y / 3) / R
        r = (2 / 3 * y) / R
        xs, zs = q, r
        ys = -xs - zs
        rx, ry, rz = round(xs), round(ys), round(zs)
        dx_, dy_, dz_ = abs(rx - xs), abs(ry - ys), abs(rz - zs)
        if dx_ > dy_ and dx_ > dz_:
            rx = -ry - rz
        elif dy_ > dz_:
            ry = -rx - rz
        else:
            rz = -rx - ry
        cx = R * SQ3 * (rx + rz / 2)
        cy = R * 1.5 * rz
        ddx, ddy = x - cx, y - cy
        e = max(abs(ddx), abs(ddx * 0.5 + ddy * SQ3 / 2), abs(ddx * 0.5 - ddy * SQ3 / 2))
        inr = R * SQ3 / 2
        v = y / max(1, c["h"] - 1)
        col = shade(base, 1.08 - 0.16 * v)
        cell = hash2(rx, rz, c["seed"] % 97)
        if e > inr - 0.75:
            if cell > 1.0 - st.get("seam", 0.06):
                return mix(glow, WHITE, 0.15), SOFT
            return mix(col, (150, 170, 200), 0.22), 255
        # 六角の内側: 上が少し明るい（膨らみ）
        if ddy < -inr * 0.3:
            col = mix(col, WHITE, 0.06)
        if cell < 0.08:
            col = shade(col, 0.85)
        return col, 255

    # ==================================================================
    #  フレーム（関節の暗い金属）
    # ==================================================================
    def k_frame(self, x, y, st, c):
        base = hexc(st["base"])
        lt = hexc(st.get("light", mix(base, WHITE, 0.35)))
        w, h = c["w"], c["h"]
        along, across = (x, y) if w >= h else (y, x)
        L, S = (w, h) if w >= h else (h, w)
        col = mix(base, lt, 0.25 * (1 - y / max(1, h - 1)))
        rib = st.get("ribs", 3)
        if L >= 6 and S >= 3 and rib:
            m = along % rib
            if m == 0:
                col = shade(col, 0.62)
            elif m == 1:
                col = mix(col, lt, 0.35)
        # 細かな部品（小さな明るい四角）
        if S >= 6 and L >= 8:
            cell = hash2(along // 5, across // 4, c["seed"])
            if cell > 0.8 and along % 5 in (2, 3) and across % 4 in (1, 2):
                col = mix(lt, WHITE, 0.2)
        return col, 255

    # ==================================================================
    #  鏡面（クローム）
    # ==================================================================
    def k_chrome(self, x, y, st, c):
        base = hexc(st.get("base", (200, 210, 225)))
        lt = hexc(st.get("light", (250, 252, 255)))
        h, w = c["h"], c["w"]
        v = y / max(1, h - 1) + (x / max(1, w - 1) - 0.5) * 0.25
        if v < 0.38:
            col = mix(lt, mix(base, (170, 200, 240), 0.4), v / 0.38)
        elif v < 0.52:
            col = mix(shade(base, 0.45), shade(base, 0.3), (v - 0.38) / 0.14)
        else:
            col = mix(shade(base, 0.55), mix(base, (230, 214, 190), 0.3), (v - 0.52) / 0.48)
        if w >= 5 and abs((x - y * 0.6) - w * 0.3) < 0.8:
            col = mix(col, WHITE, 0.55)
        return col, 255

    # ==================================================================
    #  金具（縁取り）
    # ==================================================================
    def k_trim(self, x, y, st, c):
        base = hexc(st.get("base", (226, 172, 64)))
        lt = hexc(st.get("light", (255, 240, 170)))
        dk = hexc(st.get("dark", (140, 88, 26)))
        w, h = c["w"], c["h"]
        along, across = (x, y) if w >= h else (y, x)
        S = h if w >= h else w
        t = across / max(1, S - 1)
        if t < 0.3:
            col = mix(lt, base, t / 0.3)
        elif t < 0.55:
            col = base
        else:
            col = mix(base, dk, (t - 0.55) / 0.45)
        if S >= 5 and across == S // 2:
            col = shade(col, 0.72)
        if (along + c["key"]) % 11 == 0 and S >= 3:
            col = mix(col, WHITE, 0.5)
        return col, 255

    # ==================================================================
    #  発光
    # ==================================================================
    def k_visor(self, x, y, st, c):
        glow = hexc(st["glow"])
        lt = hexc(st.get("light", mix(glow, WHITE, 0.7)))
        dp = hexc(st.get("deep", shade(glow, 0.35)))
        w, h = c["w"], c["h"]
        v = y / max(1, h - 1)
        col = mix(lt, glow, smooth(0.0, 0.45, v))
        col = mix(col, dp, smooth(0.55, 1.0, v) * 0.75)
        g = (x - y * 1.4 + c["key"] * 3) % max(10, w)
        if g < 1.2 or 2.4 < g < 3.0:
            col = mix(col, WHITE, 0.55)
        # 走査線
        if h >= 6 and y % 3 == 2:
            col = shade(col, 0.88)
        return col, st.get("emit", 30)

    def k_glowline(self, x, y, st, c):
        glow = hexc(st["glow"])
        lt = hexc(st.get("light", mix(glow, WHITE, 0.75)))
        w, h = c["w"], c["h"]
        across = (y / max(1, h - 1)) if w >= h else (x / max(1, w - 1))
        S = h if w >= h else w
        t = abs(across - 0.5) * 2
        if S <= 2:
            col = mix(lt, glow, 0.35)
        else:
            col = mix(WHITE, lt, smooth(0.0, 0.35, t))
            col = mix(col, glow, smooth(0.3, 1.0, t))
        return col, st.get("emit", EMI)

    def k_vent(self, x, y, st, c):
        base = hexc(st.get("base", (40, 44, 56)))
        glow = hexc(st.get("glow", (255, 140, 60)))
        dp = hexc(st.get("deep", shade(glow, 0.4)))
        w, h = c["w"], c["h"]
        along, across = (x, y) if w >= h else (y, x)
        L, S = (w, h) if w >= h else (h, w)
        per = st.get("slat", 3)
        if c["face"] not in st.get("faces", ("north", "south", "east", "west", "up", "down")):
            return shade(base, 1.1), 255
        if across <= 0 or across >= S - 1 or along <= 0 or along >= L - 1:
            return shade(base, 0.9), 255
        m = across % per
        if m == 0:
            return mix(base, WHITE, 0.25), 255           # 羽板の上面
        if m == 1 and per > 2:
            return shade(base, 0.8), 255
        t = 1 - abs(along / max(1, L - 1) - 0.5) * 2
        return mix(dp, mix(glow, WHITE, 0.2), t ** 0.7), SOFT if t < 0.4 else 60

    def k_thruster(self, x, y, st, c):
        base = hexc(st.get("base", (60, 64, 78)))
        glow = hexc(st.get("glow", (120, 220, 255)))
        lt = hexc(st.get("light", WHITE))
        dp = hexc(st.get("deep", shade(glow, 0.35)))
        w, h = c["w"], c["h"]
        u = (x + 0.5) / w * 2 - 1
        v = (y + 0.5) / h * 2 - 1
        r = max(abs(u), abs(v)) * 0.55 + math.hypot(u, v) * 0.45
        if c["face"] not in st.get("faces", ("down",)):
            return self.k_frame(x, y, {"base": base, "ribs": 2}, c)
        if r > 0.86:
            return mix(base, WHITE, 0.25 if v < 0 else 0.0), 255
        if r > 0.72:
            return shade(base, 0.55), 255
        if r < 0.22:
            return lt, EMI
        ringv = math.sin(r * 26) * 0.5 + 0.5
        col = mix(mix(lt, glow, smooth(0.2, 0.5, r)), dp, smooth(0.45, 0.72, r) * 0.7)
        col = mix(col, shade(col, 0.7), ringv * 0.35)
        return col, EMI if r < 0.5 else 60

    def k_flame(self, x, y, st, c):
        glow = hexc(st.get("glow", (120, 220, 255)))
        lt = hexc(st.get("light", WHITE))
        dp = hexc(st.get("deep", shade(glow, 0.4)))
        w, h = c["w"], c["h"]
        face = c["face"]
        if face in ("up", "down"):
            u = (x + 0.5) / w * 2 - 1
            v = (y + 0.5) / h * 2 - 1
            r = math.hypot(u, v)
            return mix(mix(WHITE, lt, smooth(0, 0.4, r)), glow, smooth(0.3, 1.0, r)), EMI
        t = y / max(1, h - 1)              # 0 = 根元, 1 = 先
        if st.get("dir", "down") == "up":
            t = 1 - t
        across = abs((x + 0.5) / w - 0.5) * 2
        flick = 0.06 * math.sin(y * 1.7 + c["key"]) + 0.05 * (hash2(x, y // 2, c["seed"]) - 0.5)
        core = 0.55 * (1 - t) + flick
        if across < core * 0.6:
            col = mix(WHITE, lt, across / max(0.01, core * 0.6))
        elif across < core:
            col = mix(lt, glow, (across - core * 0.6) / max(0.01, core * 0.4))
        else:
            col = mix(glow, dp, smooth(core, 1.0, across))
        col = mix(col, dp, smooth(0.55, 1.0, t) * 0.6)
        return col, EMI

    # ==================================================================
    #  星核・惑星
    # ==================================================================
    def p_core(self, st, c):
        c["planet"] = st.get("planet", "earth")

    p_planet = p_core

    def _sphere(self, x, y, st, c, emissive):
        w, h = c["w"], c["h"]
        u = (x + 0.5) / w * 2 - 1
        v = (y + 0.5) / h * 2 - 1
        r = math.hypot(u, v)
        name = c["planet"]
        R = st.get("radius", 0.9 if emissive else 1.02)
        halo = hexc(st.get("halo", ATMOS.get(name, (200, 220, 255))))
        bezel = hexc(st.get("bezel", (30, 34, 46)))
        if r > R:
            if emissive and r < R + 0.16:
                return mix(halo, WHITE, 0.3 * (1 - (r - R) / 0.16)), EMI
            if not emissive:
                return self._sphere_fill(st, c), 255
            # 角: 台座の暗い金属（四隅に小さなボルト）
            col = mix(bezel, WHITE, 0.12 * (1 - v) * 0.5)
            return col, 255
        rn = r / R
        z = math.sqrt(max(0.0, 1 - rn * rn))
        nx, ny = u / R, -v / R
        spin = math.radians(st.get("spin", 0) + (c["key"] * 37) % 360 * st.get("vary", 1))
        lon = math.atan2(nx, z) + spin
        lat = math.asin(max(-1.0, min(1.0, ny)))
        P = (math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon))
        col = planet_color(name, lon, lat, P, c["seed"])
        # セル塗りの陰: 左上からの光。明 / 暗 の 2 段 + 境のなじみ
        L = (-0.5, 0.6, 0.62)
        lam = nx * L[0] + ny * L[1] + z * L[2]
        if name != "sol":
            col = mix(shade(col, 0.55), col, smooth(-0.15, 0.1, lam))
            if lam > 0.82:
                col = mix(col, WHITE, 0.18)
        else:
            col = mix(col, (255, 120, 20), smooth(0.65, 1.0, rn) * 0.6)    # 周縁減光
        # 大気の縁
        col = mix(col, halo, smooth(0.78, 1.0, rn) * 0.55)
        if emissive:
            return col, st.get("emit", 70)
        return col, 255

    def _sphere_fill(self, st, c):
        return hexc(st.get("bezel", (30, 34, 46)))

    def k_core(self, x, y, st, c):
        return self._sphere(x, y, st, c, True)

    def k_planet(self, x, y, st, c):
        return self._sphere(x, y, st, c, False)

    # ==================================================================
    #  布（マント）
    # ==================================================================
    def k_cloth(self, x, y, st, c):
        base = hexc(st["base"])
        sh = hexc(st.get("shadow", mix(shade(base, 0.72), (90, 120, 200), 0.25)))
        w, h = c["w"], c["h"]
        face = c["face"]
        if face in ("up", "down", "east", "west") and min(w, h) < 4:
            return mix(base, sh, 0.3), 255
        fold = math.sin(x * 0.9 + c["key"] * 1.3 + math.sin(y * 0.15) * 1.5)
        col = base if fold > -0.35 else mix(base, sh, 0.55)
        if fold > 0.8:
            col = mix(col, WHITE, 0.35)
        v = y / max(1, h - 1)
        col = mix(col, sh, smooth(0.3, 1.0, v) * 0.25)
        hem = st.get("hem")
        if hem and y <= 1:
            return mix(hexc(hem), WHITE, 0.2 if y == 0 else 0.0), st.get("hem_emit", 255)
        if st.get("cloud", True) and h >= 12:
            # 下端の雲の縁取り: ふくらみ（半円）の連続
            band = max(4, h // 4)
            top = h - band
            if y >= top - 2:
                pw = max(5, band + 1)
                k = (x + c["key"] * 3) // pw
                cx = k * pw + pw / 2 - c["key"] * 3
                rr = pw / 2 + 0.3
                dy = y - (top + rr * 0.6)
                inside = (x - cx) ** 2 + dy ** 2 <= rr * rr or y >= top + rr * 0.6
                if inside:
                    puff = mix(WHITE, base, 0.15)
                    if dy > rr * 0.35 or (x - cx) > rr * 0.55:
                        puff = mix(puff, sh, 0.45)
                    if (x - cx) ** 2 + dy ** 2 > (rr - 1.1) ** 2 and dy < 0:
                        puff = mix(puff, sh, 0.6)
                    acc = st.get("cloud_glow")
                    if acc and y >= h - 2:
                        return mix(hexc(acc), WHITE, 0.3), st.get("hem_emit", 60)
                    return puff, 255
                if y >= top - 2:
                    return mix(col, sh, 0.35), 255
        return col, 255

    def k_luna(self, x, y, st, c):
        c["planet"] = "luna"
        return self._sphere(x, y, dict(st, radius=1.3), c, False)

    # ==================================================================
    #  デカール
    # ==================================================================
    def decal(self, rect, face, spec, st, key):
        if isinstance(spec, str):
            spec = {"decal": spec}
        if not spec:
            return
        x0, y0, w, h = rect
        if w < 4 or h < 3:
            return
        faces = spec.get("faces")
        if faces and face not in faces:
            return
        name = spec.get("decal", "hazard")
        base = hexc(st.get("base", (200, 200, 200)))
        ink = hexc(spec.get("ink", shade(base, 0.3) if sum(base) > 360 else mix(base, WHITE, 0.8)))
        glow = hexc(spec.get("glow", st.get("glow", (120, 255, 160))))
        px = self.px

        def put(x, y, c, a=255):
            if 0 <= x < w and 0 <= y < h:
                self.put(x0 + x, y0 + y, c, a)

        def get(x, y):
            return px[x0 + x, y0 + y][:3]

        if name == "hazard":
            # 斜めの縞の帯（面全体 or 上下の帯）
            band = spec.get("band", "full")
            ya, yb = 0, h
            if band == "bottom":
                ya = h - max(3, h // 3)
            elif band == "top":
                yb = max(3, h // 3)
            c1 = hexc(spec.get("c1", (250, 206, 40)))
            c2 = hexc(spec.get("c2", (34, 30, 30)))
            per = spec.get("period", max(4, min(8, h // 2 + 1)))
            for y in range(ya + 1, yb - 1):
                for x in range(1, w - 1):
                    put(x, y, c1 if (x + y) % per < per // 2 else c2)
            return
        if name == "stripe":
            col = hexc(spec.get("color", glow))
            pos = spec.get("pos", 0.5)
            wid = max(1, int(round(spec.get("width", 0.18) * (h if spec.get("dir", "h") == "h" else w))))
            if spec.get("dir", "h") == "h":
                yc = int(pos * (h - 1))
                for y in range(yc - wid // 2, yc - wid // 2 + wid):
                    for x in range(1, w - 1):
                        put(x, y, col, spec.get("emit", 255))
            else:
                xc = int(pos * (w - 1))
                for x in range(xc - wid // 2, xc - wid // 2 + wid):
                    for y in range(1, h - 1):
                        put(x, y, col, spec.get("emit", 255))
            return
        if name == "serial":
            text = str(spec.get("text", "AN-01")).upper()
            tw = text_width(text)
            if tw + 2 > w or h < 7:
                text = text[: max(1, (w - 1) // 4)]
                tw = text_width(text)
            ax = int(spec.get("x", 0.5) * (w - tw)) if "x" in spec else (w - tw) // 2
            ay = int(spec.get("y", 0.5) * (h - 5))
            col = hexc(spec.get("color", ink))
            a = spec.get("emit", 255)
            for i, ch in enumerate(text):
                bits = FONT35.get(ch, FONT35[" "])
                for r in range(5):
                    for k in range(3):
                        if bits[r * 3 + k] == "1":
                            put(ax + i * 4 + k, ay + r, col, a)
            if spec.get("underline", True) and ay + 6 < h - 1:
                for x in range(ax, ax + tw):
                    put(x, ay + 6, mix(col, get(x, ay + 6) if 0 <= x < w else col, 0.5), a)
            return
        if name == "emblem":
            # 惑星の紋章: 円 + 傾いた軌道 + 中心の星
            cx, cy = (w - 1) / 2, (h - 1) / 2
            R = min(w, h) * spec.get("size", 0.36)
            col = hexc(spec.get("color", glow))
            for y in range(h):
                for x in range(w):
                    dx, dy = x - cx, y - cy
                    r = math.hypot(dx, dy)
                    orb = abs((dx * 0.35 + dy) ** 2 / (R * 0.45) ** 2 + (dx * 0.94 - dy * 0.35) ** 2 /
                              (R * 1.55) ** 2 - 1)
                    if abs(r - R) < 0.6:
                        put(x, y, col, SOFT)
                    elif r < R * 0.45:
                        put(x, y, mix(col, WHITE, 0.5), EMI)
                    elif orb < 0.12 and r > R * 0.5:
                        put(x, y, mix(col, WHITE, 0.2), SOFT)
            return
        if name == "chevron":
            col = hexc(spec.get("color", glow))
            n = spec.get("count", 2)
            for k in range(n):
                for x in range(1, w - 1):
                    yy = int(abs(x - (w - 1) / 2) * 0.6) + 2 + k * 3
                    put(x, yy, col, spec.get("emit", SOFT))
            return
        if name == "lights":
            col = hexc(spec.get("color", glow))
            n = spec.get("count", 3)
            yc = int(spec.get("y", 0.5) * (h - 1))
            for k in range(n):
                xc = int((k + 1) * w / (n + 1))
                put(xc, yc, mix(col, WHITE, 0.5), EMI)
                put(xc + 1, yc, col, EMI)
                put(xc, yc + 1, shade(col, 0.7), SOFT)
                put(xc + 1, yc + 1, shade(col, 0.6), SOFT)
            return
        if name == "bolt":       # 大きめのボルト 1 個（中央）
            cx, cy = w // 2, h // 2
            put(cx, cy, WHITE)
            put(cx - 1, cy, mix(base, WHITE, 0.4))
            put(cx, cy - 1, mix(base, WHITE, 0.4))
            put(cx + 1, cy, shade(base, 0.5))
            put(cx, cy + 1, shade(base, 0.5))
            return


# ===========================================================================
#  スタイル一式
# ===========================================================================
GOLD = {"kind": "trim", "base": (226, 176, 70), "light": (255, 240, 170),
        "dark": (140, 88, 26), "line": (86, 52, 14)}
SILVER = {"kind": "trim", "base": (196, 204, 220), "light": (250, 252, 255),
          "dark": (118, 126, 146), "line": (56, 60, 76)}


def _merge(st, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(st.get(k), dict):
            st[k] = dict(st[k], **v)
        else:
            st[k] = dict(v) if isinstance(v, dict) else v
    return st


def palette(key):
    """惑星の配色（astro_data.PLANETS[key]["colors"]）を (r,g,b) の辞書で。"""
    return {k: tuple(v) for k, v in PLANETS[key]["colors"].items()}


def _armor(base, line=None, **kw):
    d = {"kind": "armor", "base": base, "light": mix(base, WHITE, 0.45),
         "dark": shade(base, 0.62), "line": line or shade(base, 0.32)}
    d.update(kw)
    return d


def common_styles(key):
    """スーツ・ウェポン・コアで共通に使える素材（惑星の配色から）。"""
    C = palette(key)
    plate, plate2, frame = C["plate"], C["plate2"], C["frame"]
    glow, lt, dp, acc = C["glow"], C["light"], C["deep"], C["accent"]
    fr = mix(frame, (96, 104, 124), 0.30)
    st = {
        "plate": _armor(plate),
        "plate_b": _armor(shade(plate, 0.80), panel=0),          # 一段奥の板（重ねの奥行き）
        "plate2": _armor(plate2, line=mix(shade(plate2, 0.32), dp, 0.3)),
        "plate2_b": _armor(shade(plate2, 0.84), panel=0,
                           line=mix(shade(plate2, 0.3), dp, 0.3)),
        "accent": _armor(acc),
        "plain": _armor(plate, panel=0, sheen=False),
        "plain2": _armor(plate2, panel=0, sheen=False),
        "inner": {"kind": "inner", "base": frame, "glow": glow, "line": shade(frame, 0.5),
                  "outline_k": 0.5, "bevel": False},
        "frame": {"kind": "frame", "base": fr, "light": mix(fr, WHITE, 0.3),
                  "line": shade(frame, 0.5)},
        "dark": {"kind": "frame", "base": shade(frame, 0.9), "ribs": 0,
                 "line": shade(frame, 0.4)},
        "chrome": {"kind": "chrome", "base": mix((200, 210, 226), plate2, 0.15),
                   "line": (50, 56, 70)},
        "gold": dict(GOLD),
        "silver": dict(SILVER),
        "visor": {"kind": "visor", "glow": glow, "light": lt, "deep": dp, "line": dp,
                  "bevel": False, "emit_outline": shade(dp, 0.7)},
        "glow": {"kind": "glowline", "glow": glow, "light": lt, "bevel": False,
                 "outline": False},
        "glow_soft": {"kind": "glowline", "glow": glow, "light": lt, "bevel": False,
                      "outline": False, "emit": SOFT},
        "glow_accent": {"kind": "glowline", "glow": acc, "light": mix(acc, WHITE, 0.7),
                        "bevel": False, "outline": False},
        "vent": {"kind": "vent", "base": fr, "glow": glow, "deep": dp, "line": shade(frame, 0.4)},
        "thruster": {"kind": "thruster", "base": fr, "glow": glow, "light": lt, "deep": dp,
                     "line": shade(frame, 0.4), "bevel": False},
        "flame": {"kind": "flame", "glow": glow, "light": lt, "deep": dp, "bevel": False,
                  "outline": False},
        "core": {"kind": "core", "planet": key, "bevel": False, "outline": False,
                 "halo": glow, "bezel": shade(frame, 0.9)},
        "planet": {"kind": "planet", "planet": key, "bevel": False, "outline": False},
        "gem": {"kind": "gem", "glow": glow, "deep": dp, "outline": False, "bevel": False},
        "gem_accent": {"kind": "gem", "glow": acc, "deep": shade(acc, 0.35), "outline": False,
                       "bevel": False},
        "energy": {"kind": "energy", "glow": glow, "light": lt, "outline": False, "bevel": False},
        "crystal": {"kind": "crystal", "base": mix(glow, WHITE, 0.3), "glow": glow,
                    "line": shade(dp, 0.8)},
        "ice": {"kind": "crystal", "base": (200, 236, 255), "glow": (150, 220, 255),
                "line": (60, 110, 150), "emit": 200},
        "cloth": {"kind": "cloth", "base": plate2, "hem": acc, "outline": False,
                  "bevel": False},
        "hazard": {"kind": "decal", "decal": "hazard", "under": _armor(plate2)},
        "serial": {"kind": "decal", "decal": "serial", "text": f"{key[:2].upper()}-0{PLANETS[key]['order']}",
                   "under": _armor(plate, panel=0)},
        "emblem": {"kind": "decal", "decal": "emblem", "under": _armor(plate2, panel=0),
                   "color": glow},
        "luna": {"kind": "planet", "planet": "luna", "bevel": False, "outline": False},
    }
    return st


def suit_styles(key, **over):
    """スーツの素材一式。名前: plate plate_b plate2 plate2_b accent plain plain2 inner frame dark
    chrome gold silver visor glow glow_soft glow_accent vent thruster flame core planet gem
    gem_accent energy crystal ice cloth hazard serial emblem luna。
    over で上書き・追加（辞書は浅くマージ、新しい名前は追加）。"""
    st = common_styles(key)
    return _merge(st, over)


def weapon_styles(key, **over):
    """ナノウェポンの素材一式（hyperdim の styles_for と同じ名前 + スーツの素材）。
    blade blade_tint blade_flat edge edge_hot metal metal_tint gold silver wrap gem energy void
    rune crystal cloth dark fur ivory + plate plate2 frame chrome glow vent thruster core planet …"""
    C = palette(key)
    g, lt, dp, acc = C["glow"], C["light"], C["deep"], C["accent"]
    st = common_styles(key)
    st.update({
        "blade": {"kind": "blade", "base": (176, 186, 204), "light": (238, 244, 252),
                  "dark": (104, 112, 132), "line": (52, 56, 72), "glint_period": 20},
        "blade_tint": {"kind": "blade", "base": mix((170, 180, 198), g, 0.18),
                       "light": mix((240, 246, 255), lt, 0.4),
                       "dark": mix((92, 100, 124), dp, 0.35), "line": shade(dp, 0.6)},
        "blade_flat": {"kind": "blade", "base": mix((170, 180, 198), g, 0.18),
                       "light": mix((240, 246, 255), lt, 0.4),
                       "dark": mix((92, 100, 124), dp, 0.35), "outline": False,
                       "bevel": False, "fuller": False, "hamon_off": True,
                       "glint_period": 9999, "hi": 0.0, "lo": 1.1},
        "edge": {"kind": "edge", "glow": g, "emit": 60, "outline": False, "bevel": False},
        "edge_hot": {"kind": "edge", "glow": g, "emit": 12, "outline": False, "bevel": False,
                     "sat": 0.5},
        "metal": {"kind": "metal", "base": (62, 66, 84), "light": (120, 128, 150),
                  "dark": (34, 36, 48), "line": (16, 16, 24), "panel": 7},
        "metal_tint": {"kind": "metal", "base": mix((60, 64, 82), dp, 0.45),
                       "light": mix((126, 134, 160), g, 0.25),
                       "dark": shade(dp, 0.45), "line": (12, 12, 20), "panel": 6},
        "wrap": {"kind": "wrap", "base": (28, 26, 34), "strap": shade(dp, 1.25),
                 "skin": (222, 220, 210), "period": 6, "outline": False},
        "void": {"kind": "void", "base": shade(dp, 0.35), "glow": g, "outline": False,
                 "bevel": False, "nebula": mix(g, acc, 0.6)},
        "rune": {"kind": "rune", "base": (40, 42, 58), "glow": g},
        "dark": {"kind": "dark", "base": (24, 22, 32), "glow": g, "line": (6, 6, 10)},
        "fur": {"kind": "fur", "base": (78, 64, 54), "outline": False},
        "ivory": {"kind": "ivory", "base": (236, 228, 206), "line": (120, 104, 84)},
        "cloth": {"kind": "cloth", "base": shade(dp, 1.15), "hem": g, "hem_emit": 60,
                  "outline": False, "bevel": False, "cloud": False},
    })
    return _merge(st, over)


def core_styles(key, **over):
    """星核（手に持つコア）の素材一式。core（球・発光）planet（球・非発光）frame chrome gold
    silver plate plate2 glow ring(=gold) gem energy …"""
    st = common_styles(key)
    st["ring"] = dict(GOLD)
    st["core"] = dict(st["core"], radius=1.05, emit=40)      # コアは面いっぱいに球を描く
    return _merge(st, over)


if __name__ == "__main__":
    # 素材見本: 各スタイルを 48x48 の面に描いて並べる
    from PIL import Image
    key = sys.argv[1] if len(sys.argv) > 1 else "earth"
    st = suit_styles(key)
    names = list(st)
    cols = 8
    rows = (len(names) + cols - 1) // cols
    p = AstroPainter(cols * 52, rows * 52, 1)
    for i, n in enumerate(names):
        p.paint_face(((i % cols) * 52 + 2, (i // cols) * 52 + 2, 48, 48), "north", st[n], i)
    out = os.path.join(astro_common.SCRATCH, f"materials_{key}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rgb = p.img.convert("RGB")      # アルファは発光の印なので、見本では不透明に
    rgb.resize((p.w * 3, p.h * 3), Image.NEAREST).save(out)
    print(out, names)
