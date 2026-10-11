# -*- coding: utf-8 -*-
"""進撃の巨人用のテクスチャ描画。

mctexture.Painter（UV 矩形に直接描くプロシージャルペインタ）に、この作品に
必要な描画を足したもの:

* 巨人の顔 … 大きな目・小さな瞳・歯茎まで見える笑い・開いた口。顎は別ボーンなので、
  顔の面には「上の歯」と「口の中」、顎の面には「下の歯・唇・顎先」を描き分ける
* 巨人の体 … 生殖器の無い滑らかな裸体。胸筋の陰影とへそだけを入れる
* 自由の翼 … 調査兵団の紋章（手前が白、奥が青の二枚の翼）。マントと上着の背に
* 制服 … 上着の前合わせと縫い目、ベルトの金具、ブーツの折り返し
* 立体機動装置 … 圧力計、刃の収納箱の仕切り、ガスボンベの帯
"""
from __future__ import annotations

import math
import random

import aot_common  # noqa: F401  (sys.path)
from mctexture import EM, Painter, hexc, mix, shade, style_skin


def _poly_fill(put, x0, y0, w, h, pts, colour, a=255):
    """正規化座標の多角形を塗る（偶奇規則）。"""
    px = [(x0 + u * (w - 1), y0 + v * (h - 1)) for u, v in pts]
    ys = [p[1] for p in px]
    for yy in range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1):
        cy = yy + 0.5
        xs = []
        n = len(px)
        for i in range(n):
            (ax, ay), (bx, by) = px[i], px[(i + 1) % n]
            if (ay <= cy < by) or (by <= cy < ay):
                xs.append(ax + (cy - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            for xx in range(int(math.ceil(xs[i] - 0.5)), int(math.floor(xs[i + 1] - 0.5)) + 1):
                put(xx, yy, colour, a)


def wing_polys(mirror=False):
    """片翼の羽根（外側から内側へ）。u は右へ、v は下へ。羽根の付け根は中央下。
    mirror=True で左右反転。返り値: [(多角形, 明るさ)]"""
    feathers = []
    # 付け根 (0.50, 0.78) から左上へ広がる 5 枚の風切り羽根
    root = (0.50, 0.80)
    tips = [(0.04, 0.10), (0.08, 0.30), (0.12, 0.48), (0.18, 0.62), (0.28, 0.74)]
    widths = [0.11, 0.10, 0.09, 0.08, 0.07]
    for i, ((tu, tv), wd) in enumerate(zip(tips, widths)):
        # 羽根 1 枚: 付け根→先端の細長い菱形
        mu, mv = (root[0] + tu) / 2, (root[1] + tv) / 2
        du, dv = tu - root[0], tv - root[1]
        L = math.hypot(du, dv) or 1
        nu, nv = -dv / L * wd, du / L * wd
        poly = [root, (mu + nu, mv + nv), (tu, tv), (mu - nu * 0.4, mv - nv * 0.4)]
        feathers.append((poly, 1.0 - i * 0.05))
    # 翼の肩（上の覆い羽）
    feathers.append(([(0.50, 0.80), (0.22, 0.18), (0.36, 0.30), (0.50, 0.56)], 1.08))
    if mirror:
        feathers = [([(1 - u, v) for u, v in poly], k) for poly, k in feathers]
    return feathers


class AotPainter(Painter):
    """mctexture.Painter に巨人の顔・紋章・制服の描画を足したもの。"""

    def decal(self, rect, decal, style, scale):
        if isinstance(decal, str):
            decal = {"name": decal}
        name = decal.get("name", "")
        x0, y0, w, h = rect
        if w < 2 or h < 2:
            return
        if name == "multi":                      # 1 面に複数の飾りを重ねる
            for d in decal.get("items", []):
                self.decal(rect, d, style, scale)
            return None
        if name == "face" and decal.get("titan"):
            return self._titan_face(rect, style, decal)
        if name == "face":
            super().decal(rect, decal, style, scale)
            if decal.get("glasses"):
                self.d_glasses(rect, style, {"eye_v": decal.get("eye_v", 0.52)}, scale)
            return None
        fn = getattr(self, "d_" + name, None)
        if fn:
            return fn(rect, style, decal, scale)
        return super().decal(rect, decal, style, scale)

    # ------------------------------------------------------------------
    #  道具
    # ------------------------------------------------------------------
    def _tools(self, rect):
        x0, y0, w, h = rect

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
            rx = max(0.6, ru * w)
            ry = max(0.6, rv * h)
            for yy in range(int(-ry) - 1, int(ry) + 2):
                for xx in range(int(-rx) - 1, int(rx) + 2):
                    if (xx / rx) ** 2 + (yy / ry) ** 2 <= 1.0:
                        self.put(cx + xx, cy + yy, c, a)

        def line(u0, v0, u1, v1, c, a=255):
            ax, ay = P(u0, v0)
            bx, by = P(u1, v1)
            steps = max(abs(bx - ax), abs(by - ay), 1)
            for i in range(steps + 1):
                self.put(ax + (bx - ax) * i // steps, ay + (by - ay) * i // steps, c, a)

        def blend(u, v, c, t):
            x, y = P(u, v)
            self.blend(x, y, c, t)

        return P, box, ellipse, line, blend

    # ==================================================================
    #  巨人
    # ==================================================================
    def _titan_face(self, rect, style, decal):
        """巨人の顔（頭の正面）。v は上から下へ。顎（別キューブ）が下 28% を覆う前提で、
        口の線より下は口の中として描く（顎を開くとそこが見える）。"""
        x0, y0, w, h = rect
        P, box, ellipse, line, blend = self._tools(rect)
        skin = style_skin(style)
        dark = hexc(style.get("dark", "#2a1c18"))
        iris = hexc(style.get("iris", decal.get("iris", "#5a4030")))
        expr = style.get("expr", decal.get("expr", "grin"))
        eye_v = decal.get("eye_v", 0.44)
        eye_u = decal.get("eye_u", 0.27)
        eye_r = decal.get("eye_r", 0.115)
        mouth_v = decal.get("mouth_v", 0.72)
        sclera = (244, 240, 232)
        shadow = shade(skin, 0.72)
        deep = shade(skin, 0.55)

        # 頬・眼窩の陰影（不気味さはここで決まる）
        for cu in (eye_u, 1 - eye_u):
            ellipse(cu, eye_v + 0.01, eye_r * 1.55, eye_r * 1.25, shade(skin, 0.86))
        # 鼻筋と小鼻
        line(0.5, eye_v + 0.04, 0.5, mouth_v - 0.12, shade(skin, 0.84))
        ellipse(0.5, mouth_v - 0.11, 0.07, 0.035, shade(skin, 0.80))
        for cu in (0.455, 0.545):
            ellipse(cu, mouth_v - 0.10, 0.014, 0.012, deep)

        # ---- 目 ----
        for i, cu in enumerate((eye_u, 1 - eye_u)):
            if expr == "grin":
                # 目を細めて笑う（下瞼が持ち上がる三日月）
                ellipse(cu, eye_v, eye_r, eye_r * 0.55, sclera)
                ellipse(cu, eye_v + 0.01, eye_r * 0.42, eye_r * 0.42, iris)
                ellipse(cu, eye_v + 0.01, eye_r * 0.2, eye_r * 0.2, (16, 12, 12))
                # 下から持ち上がる頬で目の下半分を隠す
                box(cu - eye_r * 1.1, eye_v + eye_r * 0.28, cu + eye_r * 1.1,
                    eye_v + eye_r * 0.9, shade(skin, 0.92))
                line(cu - eye_r, eye_v + eye_r * 0.28, cu + eye_r, eye_v + eye_r * 0.20, deep)
            else:
                big = 1.25 if expr == "gape" else 1.0
                ellipse(cu, eye_v, eye_r * big, eye_r * 0.82 * big, sclera)
                pr = eye_r * (0.26 if expr == "blank" else 0.34)
                off = 0.012 * (1 if i == 0 else -1) if expr == "blank" else 0.0
                ellipse(cu + off, eye_v + 0.005, pr * 1.3, pr * 1.3, iris)
                ellipse(cu + off, eye_v + 0.005, pr * 0.7, pr * 0.7, (14, 10, 10))
                self.put(*P(cu + off - pr * 0.4, eye_v - pr * 0.5), (255, 255, 255))
                # 下瞼の皺（目の大きさを強調）
                line(cu - eye_r * big, eye_v + eye_r * 0.95 * big, cu + eye_r * big,
                     eye_v + eye_r * 0.95 * big, shade(skin, 0.80))
            # 上瞼
            line(cu - eye_r * 1.05, eye_v - eye_r * 0.62, cu + eye_r * 1.05,
                 eye_v - eye_r * 0.70, dark)
            # 眉（薄く、高い位置）
            bv = eye_v - eye_r * 1.75
            tilt = -0.02 if i == 0 else 0.02
            line(cu - eye_r * 1.1, bv + tilt, cu + eye_r * 1.0, bv - tilt,
                 hexc(style.get("hair_col", "#3a2a20")))

        # ---- 口 ----
        teeth = (246, 242, 228)
        gum = (196, 104, 104)
        inside = (70, 18, 22)
        # 口の線より下は口の中（顎が閉じていれば隠れる）
        box(0.14, mouth_v + 0.02, 0.86, 1.0, inside)
        box(0.30, mouth_v + 0.10, 0.70, 1.0, (110, 34, 40))   # 舌
        if expr == "grin":
            # 耳まで裂けた笑い。両端が上がる弧に沿って歯を並べる
            n = 12
            for k in range(n):
                u = 0.08 + (k + 0.5) / n * 0.84
                curve = 0.07 * ((u - 0.5) / 0.42) ** 2
                vt = mouth_v - 0.06 - curve
                box(u - 0.84 / n * 0.46, vt, u + 0.84 / n * 0.42, mouth_v + 0.02 - curve * 0.5, teeth)
                line(u + 0.84 / n * 0.44, vt, u + 0.84 / n * 0.44, mouth_v + 0.01, shade(teeth, 0.72))
            # 歯茎と唇
            for k in range(40):
                u = 0.06 + k / 39 * 0.88
                curve = 0.07 * ((u - 0.5) / 0.44) ** 2
                blend(u, mouth_v - 0.075 - curve, gum, 0.9)
                blend(u, mouth_v - 0.095 - curve, shade(skin, 0.70), 0.8)
            # ほうれい線
            line(0.30, mouth_v - 0.18, 0.12, mouth_v - 0.04, shade(skin, 0.78))
            line(0.70, mouth_v - 0.18, 0.88, mouth_v - 0.04, shade(skin, 0.78))
        elif expr == "gape":
            n = 8
            for k in range(n):
                u = 0.22 + (k + 0.5) / n * 0.56
                box(u - 0.56 / n * 0.44, mouth_v - 0.035, u + 0.56 / n * 0.40, mouth_v + 0.03, teeth)
            line(0.20, mouth_v - 0.05, 0.80, mouth_v - 0.05, gum)
            line(0.20, mouth_v - 0.06, 0.80, mouth_v - 0.06, shade(skin, 0.66))
        else:
            # 薄く笑ったまま閉じた口
            for k in range(30):
                u = 0.24 + k / 29 * 0.52
                curve = 0.03 * ((u - 0.5) / 0.26) ** 2
                blend(u, mouth_v - 0.01 - curve, shade(skin, 0.50), 0.95)
                blend(u, mouth_v + 0.01 - curve, shade(skin, 0.80), 0.6)
            box(0.24, mouth_v + 0.012, 0.76, mouth_v + 0.02, shade(skin, 0.86))

    def d_titan_jaw(self, rect, style, decal, scale):
        """顎の正面: 上端に下の歯（または唇）、その下に顎先。"""
        P, box, ellipse, line, blend = self._tools(rect)
        skin = style_skin(style)
        expr = style.get("expr", decal.get("expr", "grin"))
        teeth = (240, 236, 222)
        if expr in ("grin", "gape"):
            n = 12 if expr == "grin" else 8
            span = 0.84 if expr == "grin" else 0.6
            u0 = 0.5 - span / 2
            for k in range(n):
                u = u0 + (k + 0.5) / n * span
                box(u - span / n * 0.44, 0.0, u + span / n * 0.40, 0.16, teeth)
                line(u + span / n * 0.43, 0.0, u + span / n * 0.43, 0.15, shade(teeth, 0.72))
            line(u0, 0.18, u0 + span, 0.18, (190, 100, 100))
            line(u0, 0.20, u0 + span, 0.20, shade(skin, 0.70))
        else:
            line(0.24, 0.04, 0.76, 0.04, shade(skin, 0.62))
            box(0.30, 0.06, 0.70, 0.14, shade(skin, 0.90))
        # 顎先の割れと影
        ellipse(0.5, 0.78, 0.18, 0.10, shade(skin, 0.90))
        line(0.5, 0.70, 0.5, 0.86, shade(skin, 0.84))

    def d_titan_chest(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        skin = style_skin(style)
        k = decal.get("k", 1.0)
        # 胸筋の下縁（二つの弧）と胸骨
        for side in (0, 1):
            for i in range(24):
                t = i / 23
                u = (0.10 + t * 0.36) if side == 0 else (0.54 + t * 0.36)
                v = 0.62 + 0.10 * math.sin(t * math.pi) * (1 if side == 0 else 1)
                blend(u, v, shade(skin, 0.72), 0.55 * k)
                blend(u, v + 0.03, shade(skin, 0.86), 0.4 * k)
        line(0.5, 0.18, 0.5, 0.70, shade(skin, 0.84))
        # 鎖骨
        line(0.10, 0.10, 0.44, 0.16, shade(skin, 0.82))
        line(0.90, 0.10, 0.56, 0.16, shade(skin, 0.82))

    def d_titan_belly(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        skin = style_skin(style)
        abs_ = decal.get("abs", False)
        if abs_:
            for v in (0.22, 0.44):
                line(0.30, v, 0.70, v, shade(skin, 0.84))
            line(0.5, 0.05, 0.5, 0.60, shade(skin, 0.80))
        ellipse(0.5, decal.get("navel", 0.68), 0.045, 0.06, shade(skin, 0.55))
        ellipse(0.5, decal.get("navel", 0.68) - 0.02, 0.03, 0.03, shade(skin, 0.75))

    def d_titan_back(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        skin = style_skin(style)
        line(0.5, 0.0, 0.5, 1.0, shade(skin, 0.86))
        for cu in (0.24, 0.76):                      # 肩甲骨の下縁だけを薄く
            line(cu - 0.14, 0.42, cu + 0.10, 0.50, shade(skin, 0.90))

    def d_knuckles(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        skin = style_skin(style)
        for i in range(1, 4):
            line(i / 4, 0.0, i / 4, 0.85, shade(skin, 0.78))

    def d_toes(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        skin = style_skin(style)
        for i in range(1, 5):
            line(i / 5, 0.2, i / 5, 1.0, shade(skin, 0.78))

    # ==================================================================
    #  調査兵団
    # ==================================================================
    def d_wings(self, rect, style, decal, scale):
        """自由の翼。奥が青（右）、手前が白（左）。shield=True で盾形の縁取り。

        翼は付け根から扇形に開く 6 枚の風切り羽根と、付け根を覆う覆い羽で描く。
        4 倍で描いてから縮めるので、小さな面でも羽根の切れ目が残る。"""
        from PIL import Image, ImageDraw
        x0, y0, w, h = rect
        SS = 4
        W, H = w * SS, h * SS
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        blue = hexc(decal.get("blue", "#2c58a6"))
        white = hexc(decal.get("white", "#f4f4f0"))
        line = hexc(decal.get("outline", "#15171c"))
        cu, cv, size = decal.get("cu", 0.5), decal.get("cv", 0.45), decal.get("size", 0.62)
        side = size * min(W, H)
        ox, oy = cu * W - side / 2, cv * H - side / 2

        def pt(u, v):
            return (ox + u * side, oy + v * side)

        if decal.get("shield"):
            sh = [(0.06, 0.02), (0.94, 0.02), (0.94, 0.60), (0.5, 0.99), (0.06, 0.60)]
            d.polygon([pt(*p) for p in sh], fill=line + (255,))
            inner = [(0.12, 0.07), (0.88, 0.07), (0.88, 0.58), (0.5, 0.92), (0.12, 0.58)]
            d.polygon([pt(*p) for p in inner], fill=hexc(decal.get("field", "#e2dccb")) + (255,))

        def wing(base, a0, a1, lengths, colour, mirror):
            """a0..a1: 羽根の向き（外向きの水平を 0°、真上を 90°）。"""
            n = len(lengths)
            feathers = []
            for i, L in enumerate(lengths):
                a = math.radians(a0 + (a1 - a0) * i / max(1, n - 1))
                sx = -1 if mirror else 1
                tip = (base[0] + sx * math.cos(a) * L, base[1] - math.sin(a) * L)
                mid = (base[0] + (tip[0] - base[0]) * 0.62, base[1] + (tip[1] - base[1]) * 0.62)
                nx, ny = -(tip[1] - base[1]), (tip[0] - base[0])
                nl = math.hypot(nx, ny) or 1
                wd = 0.075
                nx, ny = nx / nl * wd, ny / nl * wd
                feathers.append([base, (mid[0] + nx, mid[1] + ny), tip, (mid[0] - nx, mid[1] - ny)])
            # 覆い羽（付け根の塊）
            c0 = math.radians(a0)
            c1 = math.radians(a1)
            sx = -1 if mirror else 1
            k = max(lengths) * 0.46
            cover = [base, (base[0] + sx * math.cos(c0) * k, base[1] - math.sin(c0) * k),
                     (base[0] + sx * math.cos((c0 + c1) / 2) * k * 1.05,
                      base[1] - math.sin((c0 + c1) / 2) * k * 1.05),
                     (base[0] + sx * math.cos(c1) * k, base[1] - math.sin(c1) * k)]
            grow = 0.018 * side
            for f in feathers:                       # 輪郭（少し太らせて黒で）
                d.polygon([pt(*p) for p in f], fill=line + (255,), outline=line + (255,),
                          width=max(1, int(grow)))
            d.polygon([pt(*p) for p in cover], fill=line + (255,), outline=line + (255,),
                      width=max(1, int(grow)))
            for i, f in enumerate(feathers):
                d.polygon([pt(*p) for p in f], fill=shade(colour, 1.0 - 0.05 * (i % 2)) + (255,))
            d.polygon([pt(*p) for p in cover], fill=shade(colour, 0.96) + (255,))
            # 羽根の切れ目
            for f in feathers:
                d.line([pt(*f[0]), pt(*f[2])], fill=shade(colour, 0.70) + (255,),
                       width=max(1, int(grow * 0.6)))

        lengths = [0.40, 0.52, 0.62, 0.70, 0.68, 0.58]
        wing((0.51, 0.85), 14, 104, lengths, blue, mirror=False)    # 奥の青: 右へ開く
        wing((0.48, 0.88), 14, 104, lengths, white, mirror=True)    # 手前の白: 左へ開く
        small = img.resize((w, h), Image.LANCZOS)
        px = small.load()
        for yy in range(h):
            for xx in range(w):
                r, g, b, a = px[xx, yy]
                if a > 24:
                    self.blend(x0 + xx, y0 + yy, (r, g, b), min(1.0, a / 200))

    def d_jacket_front(self, rect, style, decal, scale):
        """上着の前（開いた前合わせ・胸ポケット・下の白いシャツ）。"""
        P, box, ellipse, line, blend = self._tools(rect)
        base = hexc(style.get("base", "#8b5a35"))
        shirt = hexc(decal.get("shirt", "#efece4"))
        box(0.40, 0.0, 0.60, 1.0, shirt)                       # 開いた前から見えるシャツ
        line(0.40, 0.0, 0.40, 1.0, shade(base, 0.55))
        line(0.60, 0.0, 0.60, 1.0, shade(base, 0.55))
        for cu in (0.20, 0.80):                                 # 胸ポケット
            box(cu - 0.12, 0.30, cu + 0.12, 0.52, shade(base, 0.92))
            line(cu - 0.12, 0.30, cu + 0.12, 0.30, shade(base, 0.60))
            line(cu - 0.12, 0.40, cu + 0.12, 0.40, shade(base, 0.70))
        if decal.get("patch"):
            self.d_wings(rect, style, {"cu": 0.2, "cv": 0.42, "size": 0.20, "shield": True}, scale)

    def d_seam(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        base = hexc(style.get("base", "#8b5a35"))
        v = decal.get("v", 0.86)
        line(0.0, v, 1.0, v, shade(base, 0.62))
        for i in range(0, 20, 2):
            blend(i / 19, v - 0.06, shade(base, 1.25), 0.5)

    def d_buckle(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        brass = hexc(decal.get("brass", "#c2a468"))
        box(0.36, 0.05, 0.64, 0.95, shade(brass, 0.75))
        box(0.40, 0.20, 0.60, 0.80, brass)
        box(0.46, 0.30, 0.54, 0.70, shade(brass, 0.55))

    def d_boot_top(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        base = hexc(style.get("base", "#4a2e1d"))
        box(0.0, 0.0, 1.0, 0.14, shade(base, 1.18))
        line(0.0, 0.15, 1.0, 0.15, shade(base, 0.55))
        line(0.5, 0.2, 0.5, 1.0, shade(base, 0.80))

    def d_gauge(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        ellipse(0.5, 0.5, 0.30, 0.30, (24, 24, 26))
        ellipse(0.5, 0.5, 0.24, 0.24, (232, 226, 206))
        line(0.5, 0.5, 0.66, 0.36, (170, 30, 30))
        for a in range(0, 360, 45):
            r = math.radians(a)
            blend(0.5 + math.cos(r) * 0.2, 0.5 + math.sin(r) * 0.2, (40, 40, 40), 0.8)

    def d_slots(self, rect, style, decal, scale):
        """刃の収納箱の側面: 4 枚の刃の仕切りと留め具。"""
        P, box, ellipse, line, blend = self._tools(rect)
        base = hexc(style.get("base", "#8f959c"))
        n = decal.get("n", 4)
        for i in range(1, n):
            v = i / n
            line(0.04, v, 0.96, v, shade(base, 0.60))
            line(0.04, v + 0.03, 0.96, v + 0.03, shade(base, 1.20))
        for cu in (0.18, 0.82):
            box(cu - 0.04, 0.0, cu + 0.04, 1.0, shade(base, 0.75))

    def d_tank_bands(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        base = hexc(style.get("base", "#b8bcc2"))
        for u in (0.12, 0.88):
            box(u - 0.04, 0.0, u + 0.04, 1.0, shade(base, 0.62))
        box(0.0, 0.0, 1.0, 0.18, shade(base, 1.18))

    def d_scarf_fold(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        base = hexc(style.get("base", "#b81f2a"))
        for v in (0.3, 0.62):
            line(0.0, v, 1.0, v + 0.08, shade(base, 0.72))
        for v in (0.36, 0.68):
            line(0.0, v, 1.0, v + 0.08, shade(base, 1.15))

    def d_glasses(self, rect, style, decal, scale):
        """ハンジの眼鏡（顔の上に重ねる）。"""
        P, box, ellipse, line, blend = self._tools(rect)
        frame = (40, 32, 28)
        ev = decal.get("eye_v", 0.52)
        for cu in (0.30, 0.70):
            line(cu - 0.15, ev - 0.08, cu + 0.15, ev - 0.08, frame)
            line(cu - 0.15, ev + 0.09, cu + 0.15, ev + 0.09, frame)
            line(cu - 0.15, ev - 0.08, cu - 0.15, ev + 0.09, frame)
            line(cu + 0.15, ev - 0.08, cu + 0.15, ev + 0.09, frame)
        line(0.45, ev - 0.02, 0.55, ev - 0.02, frame)

    def d_goggle_lens(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        for cu in (0.27, 0.73):
            ellipse(cu, 0.5, 0.20, 0.36, (30, 26, 22))
            ellipse(cu, 0.5, 0.15, 0.28, (150, 196, 210))
            self.put(*P(cu - 0.06, 0.36), (240, 250, 255))

    def d_gem(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        ellipse(0.5, 0.5, 0.40, 0.40, (30, 70, 40))
        ellipse(0.5, 0.5, 0.30, 0.30, (60, 168, 92))
        self.put(*P(0.4, 0.38), (220, 255, 230))

    def d_trigger(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        line(0.2, 0.3, 0.8, 0.3, (20, 20, 22))
        line(0.2, 0.6, 0.8, 0.6, (20, 20, 22))

    def d_blade_segments(self, rect, style, decal, scale):
        """刃の折り線（折って新しい刃先を出す構造）。"""
        P, box, ellipse, line, blend = self._tools(rect)
        n = decal.get("n", 6)
        for i in range(1, n):
            u = i / n
            line(u, 0.0, u - 0.05, 1.0, (120, 126, 136))

    def d_spear_tip(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        box(0.0, 0.0, 1.0, 0.25, (210, 60, 40))
        line(0.0, 0.5, 1.0, 0.5, (40, 40, 44))

    def d_flare_band(self, rect, style, decal, scale):
        P, box, ellipse, line, blend = self._tools(rect)
        col = hexc(decal.get("colour", "#3fbf5a"))
        box(0.0, 0.3, 1.0, 0.7, col)


def paint(model, styles, seed=0):
    p = AotPainter(model.tex_w, model.tex_h, seed)
    p.paint_model(model, styles)
    return p


__all__ = ["AotPainter", "paint", "wing_polys", "EM"]
_ = random  # 将来の乱れ描き用
