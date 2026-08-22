# -*- coding: utf-8 -*-
"""マーベル用のデカール群。

``mctexture.Painter`` を継承して、この addon 固有の模様だけを足す。
kaiju8 側のペインタには一切触らないので、既存アドオンは壊れない。

デカールは *正規化座標* (0..1) で描くので、同じ処理が 12 テクセルの面でも
48 テクセルの面でも成立する。細部を出したい面は ``uv_scale`` を上げるだけでよい。
"""
from __future__ import annotations

import math
import random

import _path  # noqa: F401  (sys.path を整える。必ず最初に import する)

from mctexture import EM, Painter, hexc, mix, shade  # noqa: E402


class MarvelPainter(Painter):
    """kaiju8 のデカールをすべて継承しつつ、マーベル固有のものを追加する。"""

    def decal(self, rect, decal, style, scale):
        if isinstance(decal, str):
            decal = {"name": decal}
        name = decal.get("name", "")
        x0, y0, w, h = rect
        if w < 2 or h < 2:
            return

        # --- 正規化座標のプリミティブ -----------------------------------
        def P(u, v):
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

        def ring(cu, cv, ru, rv, c, thick=0.22, a=255):
            cx, cy = P(cu, cv)
            rx = max(1, int(round(ru * w)))
            ry = max(1, int(round(rv * h)))
            for yy in range(-ry, ry + 1):
                for xx in range(-rx, rx + 1):
                    d = (xx / rx) ** 2 + (yy / ry) ** 2
                    if (1 - thick) ** 2 <= d <= 1.05:
                        self.put(cx + xx, cy + yy, c, a)

        def line(u0, v0, u1, v1, c, a=255, thick=1):
            ax, ay = P(u0, v0)
            bx, by = P(u1, v1)
            steps = max(abs(bx - ax), abs(by - ay), 1)
            for i in range(steps + 1):
                px = ax + (bx - ax) * i // steps
                py = ay + (by - ay) * i // steps
                for k in range(thick):
                    self.put(px, py + k, c, a)

        def tri(u0, v0, u1, v1, u2, v2, c, a=255):
            pts = [P(u0, v0), P(u1, v1), P(u2, v2)]
            ys = [p[1] for p in pts]
            for yy in range(min(ys), max(ys) + 1):
                xs = []
                for i in range(3):
                    (ax, ay), (bx, by) = pts[i], pts[(i + 1) % 3]
                    if ay == by:
                        continue
                    if min(ay, by) <= yy <= max(ay, by):
                        xs.append(ax + (bx - ax) * (yy - ay) / (by - ay))
                if len(xs) >= 2:
                    for xx in range(int(round(min(xs))), int(round(max(xs))) + 1):
                        self.put(xx, yy, c, a)

        glow = hexc(decal.get("glow", style.get("glow", "#B47CFF")))
        light = hexc(style.get("light", "#F0F2F6"))
        dark = hexc(style.get("dark", "#1A1820"))
        base = hexc(style.get("base", "#8A9099"))

        # ==============================================================
        #  マグニートーの兜
        # ==============================================================
        if name == "helm_face":
            # 画像の兜: 顔面はほぼ露出、両側に落ちる頬当て、額に V 字の切り欠き。
            # 面の左右端に金属の頬当てを立て、中央に肌を残す。
            cheek = shade(base, 0.92)
            box(0.00, 0.00, 0.20, 1.00, cheek)
            box(0.80, 0.00, 1.00, 1.00, cheek)
            # 頬当ての内側エッジ（ハイライト）
            line(0.20, 0.00, 0.20, 1.00, shade(base, 1.22))
            line(0.80, 0.00, 0.80, 1.00, shade(base, 1.22))
            # 額の V 字（兜の中央が眉間へ降りてくる）
            tri(0.34, 0.00, 0.66, 0.00, 0.50, 0.30, shade(base, 1.05))
            tri(0.38, 0.00, 0.62, 0.00, 0.50, 0.22, shade(base, 1.30))
            line(0.34, 0.00, 0.50, 0.30, shade(dark, 1.5))
            line(0.66, 0.00, 0.50, 0.30, shade(dark, 1.5))

        elif name == "helm_crest":
            # 兜の前面: 中央から左右へ跳ね上がる二枚のフィン（画像の M 字）
            for uu in range(w):
                for vv in range(h):
                    u, v = uu / max(1, w - 1), vv / max(1, h - 1)
                    # 縦方向のグラデーションで金属の丸みを出す
                    t = 0.5 - abs(u - 0.5)
                    c = mix(shade(base, 0.68), shade(base, 1.30), t * 2)
                    self.put(x0 + uu, y0 + vv, c)
            # 左右のフィンの立ち上がり
            tri(0.00, 1.00, 0.14, 0.00, 0.34, 1.00, shade(base, 1.18))
            tri(1.00, 1.00, 0.86, 0.00, 0.66, 1.00, shade(base, 1.18))
            # 中央の谷
            tri(0.34, 1.00, 0.50, 0.34, 0.66, 1.00, shade(base, 0.74))
            line(0.14, 0.00, 0.34, 1.00, shade(dark, 1.6))
            line(0.86, 0.00, 0.66, 1.00, shade(dark, 1.6))
            line(0.50, 0.34, 0.34, 1.00, shade(light, 0.86))
            line(0.50, 0.34, 0.66, 1.00, shade(light, 0.86))
            # 稜線のハイライト
            line(0.12, 0.02, 0.16, 0.02, light)
            line(0.84, 0.02, 0.88, 0.02, light)

        elif name == "helm_side":
            # 側頭部: 耳を覆う楕円のパネルと排気スリット
            ellipse(0.50, 0.52, 0.26, 0.24, shade(base, 0.86))
            ring(0.50, 0.52, 0.28, 0.26, shade(base, 1.24), 0.30)
            for i in range(3):
                v = 0.36 + i * 0.14
                box(0.34, v, 0.66, v + 0.05, shade(dark, 1.3))
            ellipse(0.50, 0.52, 0.07, 0.07, shade(glow, 0.7), EM)

        elif name == "helm_temple":
            # こめかみのリベット列
            for i in range(4):
                u = 0.16 + i * 0.22
                ellipse(u, 0.50, 0.045, 0.06, shade(base, 1.28))
                ellipse(u, 0.50, 0.022, 0.03, shade(dark, 1.4))

        # ==============================================================
        #  磁力の意匠
        # ==============================================================
        elif name == "mag_sigil":
            # 胸の紋章: 同心の磁界リング＋中心のコア
            ring(0.5, 0.5, 0.42, 0.44, shade(glow, 0.35), 0.16, EM)
            ring(0.5, 0.5, 0.30, 0.32, shade(glow, 0.60), 0.20, EM)
            ellipse(0.5, 0.5, 0.13, 0.14, glow, EM)
            ellipse(0.5, 0.47, 0.055, 0.06, (255, 255, 250), EM)
            # 磁力線の抜け
            for a in (0.0, 0.5):
                line(0.06 + a, 0.5, 0.30 + a, 0.5, shade(glow, 0.8), EM)

        elif name == "mag_lines":
            # 磁力線: 上下に抜ける曲線束
            n = max(2, w // max(2, int(3 * scale)))
            for i in range(n):
                u = (i + 0.5) / n
                amp = 0.16 * math.sin(math.pi * u)
                prev = None
                for step in range(9):
                    v = step / 8
                    uu = u + amp * math.sin(v * math.pi)
                    if prev:
                        line(prev[0], prev[1], uu, v,
                             shade(glow, 0.55 + 0.45 * (1 - abs(v - 0.5) * 2)), EM)
                    prev = (uu, v)

        elif name == "mag_core":
            # 手甲・帯のコア: 六角の窓の奥で紫が脈打つ
            ellipse(0.5, 0.5, 0.36, 0.38, shade(dark, 1.2))
            ring(0.5, 0.5, 0.36, 0.38, shade(base, 1.20), 0.24)
            ellipse(0.5, 0.5, 0.22, 0.24, shade(glow, 0.45), EM)
            ellipse(0.5, 0.5, 0.12, 0.13, glow, EM)
            ellipse(0.5, 0.46, 0.05, 0.05, (255, 252, 255), EM)

        elif name == "cape_clasp":
            # マントの留め具: 左右対称の三角と鎖
            tri(0.10, 0.20, 0.44, 0.20, 0.27, 0.74, shade(base, 1.16))
            tri(0.90, 0.20, 0.56, 0.20, 0.73, 0.74, shade(base, 1.16))
            line(0.27, 0.74, 0.73, 0.74, shade(base, 0.80))
            for i in range(4):
                u = 0.32 + i * 0.12
                ellipse(u, 0.78, 0.035, 0.05, shade(base, 1.30))
            ellipse(0.5, 0.36, 0.09, 0.10, shade(glow, 0.6), EM)
            ellipse(0.5, 0.36, 0.05, 0.055, glow, EM)

        elif name == "cape_fold":
            # マント面の縦の折り目
            n = max(2, w // max(3, int(4 * scale)))
            for i in range(n):
                u = (i + 0.5) / n
                d = 1.16 if i % 2 == 0 else 0.80
                for vv in range(h):
                    v = vv / max(1, h - 1)
                    ux = u + 0.02 * math.sin(v * 3.1)
                    px, py = P(ux, v)
                    self.blend(px, py, shade(base, d), 0.55)

        # ==============================================================
        #  ブラザーフッド
        # ==============================================================
        elif name == "scales":
            sw = max(2.0, 3.0 * scale)
            sh = max(2.0, 2.4 * scale)
            for yy in range(h):
                row = int(yy // sh)
                for xx in range(w):
                    ox = (xx + (sw / 2 if row % 2 else 0)) % sw
                    t = 1.0 - abs(ox - sw / 2) / (sw / 2)
                    c = mix(base, shade(base, 0.68), 0.55 * (1 - t))
                    if ox < 1 or (yy % sh) > sh - 1.1:
                        c = shade(base, 0.52)
                    self.put(x0 + xx, y0 + yy, c)

        elif name == "feral_face":
            # 獣の顔: 太い眉、金色の目、剥き出しの牙
            box(0.0, 0.20, 1.0, 0.30, shade(dark, 1.35))
            for cu in (0.26, 0.74):
                ellipse(cu, 0.42, 0.11, 0.09, shade(dark, 1.1))
                ellipse(cu, 0.42, 0.085, 0.07, (232, 180, 42), EM)
                ellipse(cu, 0.42, 0.030, 0.055, (30, 20, 8), EM)
                ellipse(cu - 0.02, 0.39, 0.025, 0.02, (255, 255, 230), EM)
            # 鼻と口
            ellipse(0.50, 0.60, 0.07, 0.05, shade(dark, 1.3))
            line(0.20, 0.74, 0.80, 0.74, shade(dark, 1.2))
            n = max(3, int(w / max(2, 3 * scale)))
            for i in range(n):
                u = (i + 0.5) / n
                tri(u - 0.4 / n, 0.74, u + 0.4 / n, 0.74, u, 0.88,
                    (244, 240, 226))

        elif name == "goggles":
            box(0.0, 0.30, 1.0, 0.62, shade(dark, 1.1))
            for cu in (0.27, 0.73):
                ellipse(cu, 0.46, 0.16, 0.13, (18, 20, 26))
                ring(cu, 0.46, 0.17, 0.14, shade(base, 1.25), 0.26)
                ellipse(cu, 0.46, 0.10, 0.08, shade(glow, 0.55), EM)
                ellipse(cu - 0.04, 0.42, 0.035, 0.03, (255, 250, 240), EM)
            box(0.44, 0.36, 0.56, 0.56, shade(base, 1.05))

        elif name == "hex_sigil":
            # スカーレット・ウィッチ: 六角の呪紋
            for r, a in ((0.44, 0.35), (0.30, 0.65), (0.16, 1.0)):
                pts = [(0.5 + r * math.cos(math.pi / 3 * i),
                        0.5 + r * math.sin(math.pi / 3 * i)) for i in range(6)]
                for i in range(6):
                    line(pts[i][0], pts[i][1], pts[(i + 1) % 6][0],
                         pts[(i + 1) % 6][1], shade(glow, a), EM)
            ellipse(0.5, 0.5, 0.08, 0.08, glow, EM)

        elif name == "flame_lick":
            rng = random.Random(w * 131 + h)
            for _ in range(max(4, w * h // 30)):
                u = rng.random()
                v0 = 0.75 + rng.random() * 0.25
                hgt = 0.30 + rng.random() * 0.45
                prev = (u, v0)
                for step in range(1, 5):
                    t = step / 4
                    uu = u + 0.10 * math.sin(t * 4 + u * 9)
                    vv = v0 - hgt * t
                    line(prev[0], prev[1], uu, vv,
                         mix(hexc("#FFD86A"), hexc("#E8561E"), t), EM)
                    prev = (uu, vv)

        # ==============================================================
        #  センチネル / MRD
        # ==============================================================
        elif name == "sentinel_face":
            # 目のない装甲面 + 横一文字のオプティックバー
            box(0.0, 0.0, 1.0, 1.0, base)
            box(0.06, 0.34, 0.94, 0.50, (14, 12, 20))
            for xx in range(w):
                u = xx / max(1, w - 1)
                t = 0.30 + 0.70 * math.sin(math.pi * min(1.0, max(0.0, u)))
                for yy in range(h):
                    v = yy / max(1, h - 1)
                    if 0.36 <= v <= 0.48:
                        self.blend(x0 + xx, y0 + yy, glow, t, EM)
            line(0.06, 0.33, 0.94, 0.33, shade(base, 1.3))
            line(0.06, 0.51, 0.94, 0.51, shade(base, 0.66))
            # 顎のグリル
            for i in range(4):
                v = 0.62 + i * 0.09
                box(0.24, v, 0.76, v + 0.04, shade(dark, 1.25))

        elif name == "sentinel_optic":
            ellipse(0.5, 0.5, 0.40, 0.42, (12, 10, 18))
            ring(0.5, 0.5, 0.42, 0.44, shade(base, 1.20), 0.20)
            ellipse(0.5, 0.5, 0.26, 0.27, shade(glow, 0.42), EM)
            ellipse(0.5, 0.5, 0.14, 0.15, glow, EM)
            ellipse(0.5, 0.45, 0.06, 0.06, (255, 250, 240), EM)

        elif name == "hazard_stripe":
            band = max(2.0, 3.0 * scale)
            for yy in range(h):
                for xx in range(w):
                    on = ((xx + yy) % (band * 2)) < band
                    self.put(x0 + xx, y0 + yy,
                             hexc("#D8B42A") if on else hexc("#1A1A1E"))

        elif name == "vent_grill":
            for i in range(4):
                v = 0.14 + i * 0.22
                box(0.14, v, 0.86, v + 0.06, shade(dark, 1.2))
                box(0.16, v + 0.01, 0.84, v + 0.04, shade(glow, 0.55), EM)

        elif name == "panel_seam":
            line(0.0, 0.30, 1.0, 0.30, shade(dark, 1.3))
            line(0.0, 0.70, 1.0, 0.70, shade(dark, 1.3))
            line(0.32, 0.0, 0.32, 1.0, shade(dark, 1.15))
            for u in (0.12, 0.62, 0.88):
                ellipse(u, 0.50, 0.035, 0.045, shade(base, 1.30))

        elif name == "rivets":
            n = max(2, int(w / max(3, 5 * scale)))
            for i in range(n):
                for j in (0.18, 0.82):
                    u = (i + 0.5) / n
                    ellipse(u, j, 0.035, 0.05, shade(base, 1.32))
                    ellipse(u, j, 0.016, 0.024, shade(dark, 1.25))

        elif name == "brotherhood_mark":
            # ブラザーフッドの徽章 — 円の中に交差する二本の斜線
            ellipse(0.5, 0.5, 0.40, 0.42, shade(dark, 1.2))
            ellipse(0.5, 0.5, 0.34, 0.36, hexc("#8E1224"))
            line(0.28, 0.28, 0.72, 0.72, light, 255, 2)
            line(0.72, 0.28, 0.28, 0.72, light, 255, 2)
            ring(0.5, 0.5, 0.40, 0.42, shade(base, 1.25), 0.16)

        else:
            super().decal(rect, decal, style, scale)
