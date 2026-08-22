# -*- coding: utf-8 -*-
"""マーベル用のデカール群。

``mctexture.Painter`` を継承して、この addon 固有の模様だけを足す。
kaiju8 側のペインタには一切触らないので、既存アドオンは壊れない。

デカールは *正規化座標* (0..1) で描くので、同じ処理が 12 テクセルの面でも
48 テクセルの面でも成立する。細部を出したい面は ``uv_scale`` を上げるだけでよい。

明暗の扱い
----------
``paint_face`` は既に AO と面ライトを掛けた **暗い側** の絵を置いている。
その上に模様を暗い色で描くと、素材が何であれ最終的に黒へ潰れる。だから
このモジュールの模様は原則 **明るい側** で描く。

* 稜線・擦り傷・面の抑揚 → ``style["light"]`` 側
* 影は「境界の 1px」だけに使い、面を塗り潰さない
* 発光（``EM``）を置く面は、必ず周囲を明るい金属で囲ってから置く。
  下地が暗いままだと emissive は「黒地に浮く点」にしか見えない

``alpha`` は 255 か ``EM``(254) しか置かない。中間のアルファはテクスチャを
半透明にしてしまうので、薄い線は ``blend()`` の混合率で表現する。
"""
from __future__ import annotations

import math
import random

import _path  # noqa: F401  (sys.path を整える。必ず最初に import する)

from mctexture import EM, Painter, hexc, mix, shade  # noqa: E402


def _lift(c, f=1.0):
    """白へ寄せる。``shade`` の倍率は暗い色を持ち上げられないので使い分ける。"""
    t = max(0.0, min(1.0, f))
    return (int(c[0] + (255 - c[0]) * t), int(c[1] + (255 - c[1]) * t),
            int(c[2] + (255 - c[2]) * t))


class MarvelPainter(Painter):
    """kaiju8 のデカールをすべて継承しつつ、マーベル固有のものを追加する。"""

    # ------------------------------------------------------------------
    #  金属面の共通処理（敵・小物からも呼べるように面単位で外へ出してある）
    # ------------------------------------------------------------------
    def scuff(self, rect, colour, seed, count=4, span=(0.18, 0.78),
              strength=(0.24, 0.35)):
        """擦り傷 — 上下方向 1px の細線を 3〜5 本、**不等間隔** で入れる。

        等間隔にすると織物に見える。傷は必ず下地より明るい側だけで描く
        （暗い線は傷ではなく汚れに見える）。混合率 0.24〜0.35 は
        制作ガイドの「``light`` 色 α60〜90」を 0..1 に直したもの。
        """
        x0, y0, w, h = rect
        if w < 3 or h < 3:
            return
        rng = random.Random(seed)
        used = []
        for _ in range(count):
            for _try in range(8):
                u = rng.uniform(0.06, 0.94)
                if all(abs(u - p) > 0.11 for p in used):
                    used.append(u)
                    break
            else:
                continue
            x = x0 + int(u * (w - 1))
            v0 = rng.uniform(span[0] * 0.4, span[0])
            v1 = rng.uniform(span[1], 1.0)
            t = rng.uniform(*strength)
            for yy in range(int(v0 * (h - 1)), int(v1 * (h - 1)) + 1):
                self.blend(x, y0 + yy, colour, t)

    def dents(self, rect, colour, dark, seed, count=3):
        """打痕 — 小さな窪み。下側に影、**上側に明るい縁** を置くと凹んで見える。"""
        x0, y0, w, h = rect
        if w < 6 or h < 6:
            return
        rng = random.Random(seed ^ 0x5EED)
        for _ in range(count):
            cx = x0 + rng.randint(2, w - 3)
            cy = y0 + rng.randint(2, h - 3)
            r = rng.randint(1, max(1, min(w, h) // 8))
            for yy in range(-r, r + 1):
                for xx in range(-r, r + 1):
                    if xx * xx + yy * yy > r * r:
                        continue
                    self.blend(cx + xx, cy + yy, dark, 0.30)
            for xx in range(-r, r + 1):
                self.blend(cx + xx, cy - r, colour, 0.55)

    # ------------------------------------------------------------------
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

        def wash(u0, v0, u1, v1, c, t0, t1=None):
            """帯を縦方向のグラデで混ぜる。面の抑揚はこれで作る。"""
            ax, ay = P(u0, v0)
            bx, by = P(u1, v1)
            lo, hi = min(ay, by), max(ay, by)
            t1 = t0 if t1 is None else t1
            for yy in range(lo, hi + 1):
                k = (yy - lo) / max(1, hi - lo)
                for xx in range(min(ax, bx), max(ax, bx) + 1):
                    self.blend(xx, yy, c, t0 + (t1 - t0) * k)

        def soft(cu, cv, ru, rv, c, tmax):
            """柔らかい楕円。塗り潰さずに混ぜるので、肌の起伏に使える。"""
            cx, cy = P(cu, cv)
            rx = max(1.0, ru * w)
            ry = max(1.0, rv * h)
            for yy in range(-int(ry) - 1, int(ry) + 2):
                for xx in range(-int(rx) - 1, int(rx) + 2):
                    d = (xx / rx) ** 2 + (yy / ry) ** 2
                    if d > 1.0:
                        continue
                    self.blend(cx + xx, cy + yy, c, tmax * (1.0 - d) ** 0.8)

        def stud(u, v, r=0.040):
            """リベット一粒。上に光、下に影の 2 画素だけで丸みを出す。"""
            cx, cy = P(u, v)
            rx = max(1, int(round(r * w)))
            ry = max(1, int(round(r * 1.3 * h)))
            for yy in range(-ry, ry + 1):
                for xx in range(-rx, rx + 1):
                    if (xx / rx) ** 2 + (yy / ry) ** 2 > 1.05:
                        continue
                    t = -yy / max(1, ry)          # 上ほど明るい
                    self.blend(cx + xx, cy + yy,
                               _lift(light, 0.45) if t >= 0 else shade(dark, 1.2),
                               0.30 + 0.45 * abs(t))
            self.blend(cx, cy + ry, shade(dark, 1.3), 0.55)

        glow = hexc(decal.get("glow", style.get("glow", "#B47CFF")))
        light = hexc(style.get("light", "#F0F2F6"))
        dark = hexc(style.get("dark", "#1A1820"))
        base = hexc(style.get("base", "#8A9099"))
        seed = (x0 * 7919 + y0 * 104729 + (hash(name) & 0xFFFF))
        tall = h > w * 1.35          # フィン・頬当てのような細長い面か

        # ==============================================================
        #  マグニートーの兜
        # ==============================================================
        if name == "helm_face":
            # 頬当ての面。前から見ると顔の左右に落ちる二枚の板なので、
            # 「外側の斜面 / 内側の斜面 / その境の稜線」の三層で抑揚を作る。
            if tall:
                # 細長い面 = 頬当て一枚ぶん。折れ線を一本入れて板に見せない。
                fold = 0.58
                wash(0.0, 0.0, fold, 1.0, light, 0.26, 0.06)
                wash(fold, 0.0, 1.0, 1.0, dark, 0.10, 0.34)
                line(fold, 0.0, fold, 1.0, _lift(light, 0.35))
                line(fold + 0.06, 0.0, fold + 0.06, 1.0, shade(dark, 1.2))
                # 顎側の縁は一段暗く落として、肌との境をはっきりさせる
                wash(0.0, 0.86, 1.0, 1.0, dark, 0.12, 0.45)
                line(0.0, 0.03, 1.0, 0.03, _lift(light, 0.25))
                self.dents(rect, light, dark, seed, 2)
                self.scuff(rect, light, seed, 3, (0.10, 0.62))
            else:
                # 幅のある面 = 額から両頬まで一枚で受ける。左右対称に組む。
                cheek = shade(base, 0.90)
                box(0.00, 0.00, 0.20, 1.00, cheek)
                box(0.80, 0.00, 1.00, 1.00, cheek)
                wash(0.00, 0.00, 0.20, 1.00, light, 0.28, 0.04)
                wash(0.80, 0.00, 1.00, 1.00, light, 0.04, 0.28)
                line(0.20, 0.00, 0.20, 1.00, _lift(light, 0.40))
                line(0.80, 0.00, 0.80, 1.00, _lift(light, 0.40))
                line(0.22, 0.00, 0.22, 1.00, shade(dark, 1.2))
                line(0.78, 0.00, 0.78, 1.00, shade(dark, 1.2))
                # 額の V 字（兜の中央が眉間へ降りてくる）
                tri(0.34, 0.00, 0.66, 0.00, 0.50, 0.32, shade(base, 1.10))
                tri(0.38, 0.00, 0.62, 0.00, 0.50, 0.24, _lift(light, 0.20))
                line(0.34, 0.00, 0.50, 0.32, shade(dark, 1.5))
                line(0.66, 0.00, 0.50, 0.32, shade(dark, 1.5))
                self.scuff(rect, light, seed, 4, (0.06, 0.55))

        elif name == "helm_crest":
            # 兜の M 字。**平板に見せない**ことがこのデカールの全て。
            # 面が横長なら M そのものを、細長ければ一本の稜線を描く。
            if tall:
                # フィン / 眉間リッジ: 中央に鋭い稜、両脇を落として断面を V に。
                # 明るくするのは中央 1/3 だけ。全面を持ち上げると白い棒になる。
                for uu in range(w):
                    u = uu / max(1, w - 1)
                    d = abs(u - 0.5) * 2.0
                    for vv in range(h):
                        v = vv / max(1, h - 1)
                        px, py = x0 + uu, y0 + vv
                        if d < 0.42:
                            # 稜の面。先端ほど明るい（光は上から当たる）
                            self.blend(px, py, light,
                                       (1.0 - d / 0.42) * (0.50 - 0.28 * v))
                        else:
                            # 稜から落ちる斜面。ここを沈めて初めて稜が立つ
                            k = (d - 0.42) / 0.58
                            self.blend(px, py, dark, 0.14 + 0.40 * k)
                line(0.5, 0.0, 0.5, 1.0, _lift(light, 0.45))
                line(0.5, 0.0, 0.5, 0.26, (255, 255, 255))
                self.scuff(rect, light, seed, 3, (0.05, 0.70))
            else:
                # 横長の面 = 額の帯。ここで M を作る。
                def m_top(u):
                    a = abs(u - 0.5) * 2.0
                    if a <= 0.56:
                        return 0.66 + (0.04 - 0.66) * (a / 0.56)
                    return 0.04 + (0.74 - 0.04) * ((a - 0.56) / 0.44)

                for uu in range(w):
                    u = uu / max(1, w - 1)
                    top = m_top(u)
                    a = abs(u - 0.5) * 2.0
                    for vv in range(h):
                        v = vv / max(1, h - 1)
                        px, py = x0 + uu, y0 + vv
                        if v < top - 0.02:
                            # M の外側 = 落ち込んだ地。谷ほど深く暗い。
                            # ここを充分に沈めないと、遠景で M が地に溶ける
                            self.blend(px, py, dark, 0.42 + 0.24 * (1 - a))
                        else:
                            # M の内側 = 立ち上がった稜。上端が最も明るい
                            k = (v - top) / max(1e-3, 1.0 - top)
                            self.blend(px, py, light, 0.58 * (1 - k) ** 0.6)
                # 稜線そのもの: M の輪郭を 1px の白で追う
                for uu in range(w):
                    u = uu / max(1, w - 1)
                    yy = y0 + int(round(m_top(u) * (h - 1)))
                    self.put(x0 + uu, yy, _lift(light, 0.55))
                    if yy + 1 < y0 + h:
                        self.blend(x0 + uu, yy + 1, shade(dark, 1.35), 0.55)
                # 谷の底に一段暗い影を残すと二つの山が独立して読める
                line(0.5, m_top(0.5) - 0.02, 0.5, 1.0, shade(dark, 1.15))
                self.scuff(rect, light, seed, 4, (0.35, 0.95))

        elif name == "helm_side":
            # 側頭部: 耳を覆う楕円のパネルと排気スリット。
            # 面全体に斜めの抑揚を先に敷いてから、部品を乗せる。
            wash(0.0, 0.0, 1.0, 0.5, light, 0.28, 0.02)
            wash(0.0, 0.5, 1.0, 1.0, dark, 0.02, 0.30)
            # 円盤は面いっぱいに取る。小さく置くと「ボタン」に見えて
            # 耳を覆う板だと読めない。
            ring(0.50, 0.50, 0.42, 0.46, shade(dark, 1.30), 0.30)
            ellipse(0.50, 0.50, 0.38, 0.42, shade(base, 0.96))
            ring(0.50, 0.50, 0.38, 0.42, _lift(light, 0.36), 0.16)
            # 上半分だけ明るく残すと、円盤が「出っ張って」見える
            wash(0.14, 0.14, 0.86, 0.46, light, 0.26, 0.0)
            for i in range(3):
                v = 0.40 + i * 0.15
                box(0.30, v, 0.70, v + 0.055, shade(dark, 1.35))
                line(0.30, v, 0.70, v, _lift(light, 0.34))
            ellipse(0.50, 0.30, 0.085, 0.085, _lift(glow, 0.50), EM)
            ellipse(0.50, 0.30, 0.040, 0.040, (255, 255, 250), EM)
            self.dents(rect, light, dark, seed, 3)
            self.scuff(rect, light, seed, 4, (0.06, 0.90))

        elif name == "helm_temple":
            # こめかみのリベット列 + 面の抑揚
            wash(0.0, 0.0, 1.0, 0.45, light, 0.24, 0.0)
            wash(0.0, 0.72, 1.0, 1.0, dark, 0.0, 0.24)
            for i in range(4):
                stud(0.16 + i * 0.22, 0.50, 0.052)
            self.scuff(rect, light, seed, 3, (0.10, 0.80))

        # ==============================================================
        #  磁力の意匠
        # ==============================================================
        elif name == "mag_sigil":
            # 胸の紋章。**遠景で読める**ことが条件なので、面いっぱいに取り、
            # 明るい金属の縁で輪郭を切ってから中を光らせる。
            # 発光だけで組むと昼の空で飛び、夜は下地の紫に沈む。
            ring(0.5, 0.5, 0.48, 0.49, shade(dark, 1.1), 0.14)
            ring(0.5, 0.5, 0.45, 0.46, _lift(light, 0.30), 0.13)
            ring(0.5, 0.5, 0.38, 0.39, shade(glow, 0.42), 0.22, EM)
            ring(0.5, 0.5, 0.26, 0.27, _lift(glow, 0.25), 0.30, EM)
            # 四方へ抜ける磁力線（斜めに置くと縦横の cube 稜線と喧嘩しない）
            for a in range(4):
                ang = math.pi / 4 + a * math.pi / 2
                du, dv = math.cos(ang), math.sin(ang)
                line(0.5 + du * 0.20, 0.5 + dv * 0.20,
                     0.5 + du * 0.50, 0.5 + dv * 0.50,
                     _lift(light, 0.35), 255, 1)
            ellipse(0.5, 0.5, 0.155, 0.16, _lift(glow, 0.30), EM)
            ellipse(0.5, 0.5, 0.085, 0.09, (255, 255, 255), EM)
            ellipse(0.5, 0.44, 0.035, 0.035, (255, 255, 255), EM)

        elif name == "mag_lines":
            # 磁力線: 上下に抜ける曲線束。極へ向かうほど間隔を詰める。
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
            # 手甲・帯のコア: 明るい金属のベゼルの奥で紫が脈打つ。
            # ベゼルを明るくしないと、発光が「黒地の点」になる。
            ellipse(0.5, 0.5, 0.40, 0.42, shade(dark, 1.15))
            ring(0.5, 0.5, 0.42, 0.44, _lift(light, 0.32), 0.26)
            ring(0.5, 0.5, 0.38, 0.40, shade(dark, 1.3), 0.10)
            ellipse(0.5, 0.5, 0.26, 0.28, shade(glow, 0.45), EM)
            ellipse(0.5, 0.5, 0.15, 0.16, _lift(glow, 0.15), EM)
            ellipse(0.5, 0.47, 0.06, 0.06, (255, 252, 255), EM)
            for a in range(6):
                ang = a * math.pi / 3
                ellipse(0.5 + math.cos(ang) * 0.42, 0.5 + math.sin(ang) * 0.44,
                        0.030, 0.032, _lift(light, 0.40))

        elif name == "cape_clasp":
            # マントの留め具: 左右対称の三角と鎖
            tri(0.08, 0.18, 0.46, 0.18, 0.27, 0.76, shade(base, 1.10))
            tri(0.92, 0.18, 0.54, 0.18, 0.73, 0.76, shade(base, 1.10))
            tri(0.12, 0.20, 0.42, 0.20, 0.27, 0.60, _lift(light, 0.28))
            tri(0.88, 0.20, 0.58, 0.20, 0.73, 0.60, _lift(light, 0.28))
            line(0.27, 0.76, 0.73, 0.76, shade(dark, 1.2))
            line(0.27, 0.74, 0.73, 0.74, _lift(light, 0.30))
            for i in range(4):
                u = 0.32 + i * 0.12
                ellipse(u, 0.80, 0.038, 0.055, _lift(light, 0.35))
                ellipse(u, 0.81, 0.018, 0.026, shade(dark, 1.3))
            ellipse(0.5, 0.36, 0.11, 0.12, _lift(light, 0.30))
            ellipse(0.5, 0.36, 0.085, 0.09, shade(glow, 0.55), EM)
            ellipse(0.5, 0.36, 0.045, 0.05, (255, 250, 255), EM)

        elif name == "cape_fold":
            # マントの折り目。**片側だけ明るく**しないと折れて見えない。
            # 一本の折り目は「明るい山 → 谷の細い影」の 2px 対で作る。
            # 襞の本数は uv_scale ではなく **テクセル幅** で決める。
            # scale で割ると、面積の大きいマント（uv_scale 4）で 2 本しか
            # 立たず、赤い板にしか見えなくなる。
            n = max(3, min(10, int(round(w / 6.0))))
            rng = random.Random(seed)
            us = sorted(rng.uniform(0.05, 0.95) for _ in range(n))
            for i, u in enumerate(us):
                deep = 0.62 if i % 2 == 0 else 0.38     # 深い襞と浅い襞を交互に
                for vv in range(h):
                    v = vv / max(1, h - 1)
                    # 裾へ向かってわずかに開く（板でも布に見せるため）
                    ux = u + 0.045 * (v ** 1.6) * (1 if u > 0.5 else -1)
                    px, py = P(ux, v)
                    fade = 0.55 + 0.45 * v          # 裾ほど襞が立つ
                    self.blend(px - 1, py, light, deep * 0.40 * fade)
                    self.blend(px, py, light, deep * 0.66 * fade)
                    self.blend(px + 1, py, dark, deep * fade)
                    self.blend(px + 2, py, dark, deep * 0.55 * fade)
            # 裾の影と、肩口の当たり
            wash(0.0, 0.88, 1.0, 1.0, dark, 0.10, 0.46)
            wash(0.0, 0.0, 1.0, 0.12, light, 0.30, 0.02)

        # ==============================================================
        #  顔 — 立体を先に敷いてから、共有エンジンの目鼻を上に乗せる
        # ==============================================================
        elif name == "face" and w >= 18 and h >= 22:
            # ``mctexture._face`` は目・眉・口しか描かない。uv_scale 12 で
            # 39x53 テクセルまで解像度が上がった今、それだけだと
            # 「のっぺりした板に目が二つ」に見える。骨格の陰影を下に敷く。
            skin = hexc(style.get("skin", style.get("base", "#E2BE9E")))
            hi = _lift(skin, 0.30)
            lo = shade(skin, 0.72)
            ev = decal.get("eye_v", 0.50)
            ew = decal.get("eye_w", 0.24)
            gap = decal.get("eye_gap", 0.10)
            # こめかみと顎の外側を落として、面ではなく塊にする
            wash(0.00, 0.00, 0.10, 1.00, lo, 0.34, 0.20)
            wash(0.90, 0.00, 1.00, 1.00, lo, 0.20, 0.34)
            wash(0.00, 0.90, 1.00, 1.00, lo, 0.05, 0.30)
            wash(0.00, 0.00, 1.00, 0.14, lo, 0.26, 0.02)
            # 眉庇の影（目のすぐ上）と、その上の額のハイライト
            wash(0.14, ev - 0.16, 0.86, ev - 0.05, lo, 0.03, 0.20)
            wash(0.22, ev - 0.34, 0.78, ev - 0.18, hi, 0.18, 0.03)
            # 頬骨。目尻の外下に置くと、それだけで彫りが出る。
            # ただし **必ず柔らかく**。塗り潰すと顔に絆創膏を貼った絵になる。
            for cu in (0.5 - gap - ew * 0.85, 0.5 + gap + ew * 0.85):
                soft(cu, ev + 0.10, 0.15, 0.085, hi, 0.24)
                soft(cu + (0.045 if cu > 0.5 else -0.045), ev + 0.21,
                     0.12, 0.070, lo, 0.18)
            # 鼻梁 — 片側に光、反対側に影。中央線は共有エンジンが引く
            soft(0.465, ev + 0.11, 0.035, 0.105, hi, 0.20)
            soft(0.535, ev + 0.11, 0.040, 0.105, lo, 0.20)
            soft(0.500, ev + 0.24, 0.070, 0.045, lo, 0.16)
            # 顎と口の下の影
            soft(0.500, ev + 0.36, 0.20, 0.070, lo, 0.18)
            if decal.get("stubble"):
                # 無精髭。粒で撒くと汚れに見えるので、頬から顎へ
                # 帯として敷いてから粒を足す。
                beard = hexc(decal.get("stubble_col",
                                       style.get("hair_col", "#6E6A62")))
                rng = random.Random(seed ^ 0xBEA5)
                for vv in range(h):
                    v = vv / max(1, h - 1)
                    if v < ev + 0.24:
                        continue
                    k = min(1.0, (v - ev - 0.24) / 0.30)
                    for uu in range(w):
                        u = uu / max(1, w - 1)
                        if abs(u - 0.5) > 0.40 - 0.10 * k:
                            continue
                        if rng.random() < 0.30 + 0.35 * k:
                            self.blend(x0 + uu, y0 + vv, beard,
                                       0.16 + 0.20 * k)
            super().decal(rect, decal, style, scale)

        # ==============================================================
        #  ブラザーフッド
        # ==============================================================
        elif name == "scales":
            # 鱗。一枚ごとに「上辺の明るい弧 + 下辺の影」を入れないと、
            # ただのチェック模様に見えて素材が読めない。
            # 鱗の大きさは uv_scale ではなく **面のテクセル数** で決める。
            # uv_scale を掛けると、顔（scale 10〜12）で鱗一枚が面より
            # 大きくなり、模様ではなく一本の継ぎ目にしか見えなくなる。
            sw = max(2.0, min(8.0, w / 5.0))
            sh = max(2.0, min(6.0, h / 6.0))
            hi = _lift(light, 0.18)
            lo = shade(dark, 1.15)
            for yy in range(h):
                row = int(yy // sh)
                fy = (yy % sh) / sh
                for xx in range(w):
                    ox = (xx + (sw / 2 if row % 2 else 0)) % sw
                    t = 1.0 - abs(ox - sw / 2) / (sw / 2)
                    c = mix(base, shade(base, 0.62), 0.60 * (1 - t))
                    if fy < 0.30:                     # 鱗の上辺 = 光を受ける
                        c = mix(c, hi, 0.34 * t + 0.10)
                    elif fy > 0.80:                   # 鱗の下辺 = 落ちる影
                        c = mix(c, lo, 0.45)
                    if ox < 1:
                        c = mix(c, lo, 0.55)
                    self.put(x0 + xx, y0 + yy, c)

        elif name == "feral_face":
            # 獣の顔: 太い眉、金色の目、剥き出しの牙。毛の流れを一段入れる。
            rng = random.Random(seed)
            for _ in range(max(6, w * h // 18)):
                ux, uv = rng.random(), rng.random()
                px, py = P(ux, uv)
                self.blend(px, py, light if rng.random() < 0.55 else dark, 0.22)
            box(0.0, 0.18, 1.0, 0.30, shade(dark, 1.35))
            line(0.0, 0.17, 1.0, 0.17, _lift(light, 0.22))
            for cu in (0.26, 0.74):
                ellipse(cu, 0.42, 0.125, 0.10, shade(dark, 1.1))
                ellipse(cu, 0.42, 0.095, 0.078, (240, 190, 48), EM)
                ellipse(cu, 0.42, 0.032, 0.060, (26, 16, 6), EM)
                ellipse(cu - 0.025, 0.385, 0.028, 0.024, (255, 255, 235), EM)
            # 鼻と口
            ellipse(0.50, 0.60, 0.075, 0.055, shade(dark, 1.3))
            ellipse(0.50, 0.58, 0.045, 0.030, _lift(light, 0.15))
            line(0.18, 0.74, 0.82, 0.74, shade(dark, 1.2))
            n = max(3, int(w / max(2, 3 * scale)))
            for i in range(n):
                u = (i + 0.5) / n
                tri(u - 0.42 / n, 0.74, u + 0.42 / n, 0.74, u, 0.90,
                    (250, 246, 234))
                line(u, 0.75, u, 0.86, (255, 255, 255))

        elif name == "goggles":
            box(0.0, 0.28, 1.0, 0.64, shade(dark, 1.1))
            line(0.0, 0.27, 1.0, 0.27, _lift(light, 0.30))
            for cu in (0.27, 0.73):
                ring(cu, 0.46, 0.19, 0.16, _lift(light, 0.35), 0.22)
                ellipse(cu, 0.46, 0.155, 0.13, (16, 18, 24))
                ellipse(cu, 0.46, 0.105, 0.085, shade(glow, 0.60), EM)
                ellipse(cu - 0.045, 0.42, 0.038, 0.032, (255, 250, 240), EM)
            box(0.44, 0.34, 0.56, 0.58, _lift(light, 0.20))

        elif name == "hex_sigil":
            # スカーレット・ウィッチ: 六角の呪紋（emissive を使わず布の縁で光らす）
            for r, a in ((0.46, 0.30), (0.31, 0.60), (0.16, 1.0)):
                pts = [(0.5 + r * math.cos(math.pi / 3 * i),
                        0.5 + r * math.sin(math.pi / 3 * i)) for i in range(6)]
                for i in range(6):
                    line(pts[i][0], pts[i][1], pts[(i + 1) % 6][0],
                         pts[(i + 1) % 6][1], _lift(glow, a * 0.45))
            ellipse(0.5, 0.5, 0.085, 0.085, _lift(glow, 0.35))

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
            # 目のない装甲面 + 横一文字のオプティックバー。
            # バーの上下に **明るい金属の唇** を置くのが肝。ここが暗いと
            # 発光が黒地に浮いた点にしか見えず、遠景で目が消える。
            box(0.0, 0.0, 1.0, 1.0, base)
            wash(0.0, 0.0, 1.0, 0.34, light, 0.30, 0.04)     # 額の抑揚
            wash(0.0, 0.52, 1.0, 1.0, dark, 0.04, 0.22)      # 顎へ落ちる影
            box(0.04, 0.28, 0.96, 0.33, _lift(light, 0.30))  # 庇（上唇）
            box(0.04, 0.50, 0.96, 0.54, _lift(light, 0.12))  # 下唇
            box(0.05, 0.33, 0.95, 0.51, (10, 9, 16))         # 窪み
            for xx in range(w):
                u = xx / max(1, w - 1)
                t = 0.25 + 0.75 * math.sin(math.pi * min(1.0, max(0.0, u))) ** 0.6
                for yy in range(h):
                    v = yy / max(1, h - 1)
                    if 0.355 <= v <= 0.485:
                        self.blend(x0 + xx, y0 + yy, glow, t, EM)
                    if 0.40 <= v <= 0.44:
                        self.blend(x0 + xx, y0 + yy, (255, 250, 240),
                                   t * 0.85, EM)
            line(0.04, 0.27, 0.96, 0.27, shade(dark, 1.4))
            # 顎のグリル（上辺だけ明るく）
            for i in range(4):
                v = 0.64 + i * 0.085
                box(0.24, v, 0.76, v + 0.04, shade(dark, 1.30))
                line(0.24, v, 0.76, v, _lift(light, 0.26))
            self.scuff(rect, light, seed, 4, (0.55, 0.98))

        elif name == "sentinel_optic":
            # 単眼。明るいベゼル → 黒い窪み → 発光 → 白芯 の四層。
            ring(0.5, 0.5, 0.48, 0.49, _lift(light, 0.40), 0.18)
            ring(0.5, 0.5, 0.43, 0.44, shade(dark, 1.25), 0.14)
            # 黒い窪みは**縁の一段だけ**。ここを広く取ると、中の発光が
            # 黒に食われて「暗い穴」にしか見えなくなる。
            ellipse(0.5, 0.5, 0.40, 0.41, (12, 10, 18))
            ellipse(0.5, 0.5, 0.34, 0.35, glow, EM)
            ellipse(0.5, 0.5, 0.22, 0.23, _lift(glow, 0.40), EM)
            ellipse(0.5, 0.5, 0.11, 0.11, (255, 252, 246), EM)
            # 横に伸びる光条。単眼が「見ている」ことを一目で読ませる
            line(0.02, 0.50, 0.98, 0.50, _lift(glow, 0.55), EM)
            line(0.50, 0.06, 0.50, 0.94, _lift(glow, 0.20), EM)

        elif name == "hazard_stripe":
            band = max(2.0, 3.0 * scale)
            warm, cold = hexc("#E8C43A"), hexc("#20202A")
            for yy in range(h):
                for xx in range(w):
                    on = ((xx + yy) % (band * 2)) < band
                    self.put(x0 + xx, y0 + yy, warm if on else cold)
            wash(0.0, 0.0, 1.0, 0.5, light, 0.22, 0.0)

        elif name == "vent_grill":
            for i in range(4):
                v = 0.14 + i * 0.22
                box(0.14, v, 0.86, v + 0.06, shade(dark, 1.2))
                line(0.14, v, 0.86, v, _lift(light, 0.30))
                box(0.16, v + 0.015, 0.84, v + 0.045, shade(glow, 0.60), EM)

        elif name == "panel_seam":
            # 板金の継ぎ目。**下地の style から色を取る**ので、兜でも
            # センチネルでも小物でも同じ呼び方で成立する（汎用化）。
            if w < 9:
                # フィンのように細い面ではリベットが点の羅列になって
                # ただのノイズに見える。縦の稜線一本だけに落とす。
                line(0.42, 0.0, 0.42, 1.0, shade(dark, 1.25))
                line(0.58, 0.0, 0.58, 1.0, _lift(light, 0.30))
                self.scuff(rect, light, seed, 2, (0.10, 0.80))
                return
            for v in (0.30, 0.70):
                line(0.0, v, 1.0, v, shade(dark, 1.3))
                line(0.0, v - 0.02, 1.0, v - 0.02, _lift(light, 0.26))
            line(0.32, 0.0, 0.32, 1.0, shade(dark, 1.15))
            line(0.34, 0.0, 0.34, 1.0, _lift(light, 0.18))
            # リベットは面が充分に大きいときだけ。小さい面に打つと
            # 一粒が 3x3 の十字になって、板金ではなく水玉模様に見える。
            if w >= 16 and h >= 12:
                for u in (0.12, 0.62, 0.88):
                    stud(u, 0.50)
            self.scuff(rect, light, seed, 3, (0.08, 0.80))

        elif name == "rivets":
            if w < 7 or h < 5:
                line(0.5, 0.08, 0.5, 0.92, _lift(light, 0.28))
                return
            n = max(2, int(w / max(3, 5 * scale)))
            for i in range(n):
                for j in (0.18, 0.82):
                    stud((i + 0.5) / n, j)

        elif name == "brotherhood_mark":
            # ブラザーフッドの徽章 — 円の中に交差する二本の斜線
            ellipse(0.5, 0.5, 0.42, 0.44, shade(dark, 1.2))
            ellipse(0.5, 0.5, 0.35, 0.37, hexc("#A81830"))
            line(0.28, 0.28, 0.72, 0.72, light, 255, 2)
            line(0.72, 0.28, 0.28, 0.72, light, 255, 2)
            ring(0.5, 0.5, 0.42, 0.44, _lift(light, 0.35), 0.16)

        else:
            super().decal(rect, decal, style, scale)
