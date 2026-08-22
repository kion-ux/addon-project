# -*- coding: utf-8 -*-
"""アイテムアイコン（32x32）を手続きで描く。

技アイコンが並んだときに見分けられるかが、このモジュールの全て。
``contract.TECHNIQUES[*]["colour"]` は紫が 5 本・水色が 4 本と偏っていて、
**色だけでは 15 種を区別できない**。そこで三つの手掛かりを重ねる。

1. **地の模様（field）** — 同じ色相の技どうしで必ず違う模様を割り当てる。
   放射 / 漏斗 / 縦格子 / 六角 / 地割れ … 図形を見なくても質感で分かれる
2. **図形（glyph）** — ``docs/DIRECTION.md`` §5-5 の「決め絵」と同じ形にする。
   アイコンと実際に出る絵が違うと、技はいつまでも覚えられない
3. **縁（frame）** — 系統（軽 / 保持 / 重 / 必殺）を枠の太さと切れ目で示す

地の明度も技の基調色で染める。全部を同じ暗い板にすると、ホットバーの中で
15 個の黒い四角が並ぶことになる。
"""
from __future__ import annotations

import math

import _path  # noqa: F401

import contract as K  # noqa: E402
from PIL import Image  # noqa: E402

S = 32

#: 系統。枠の描き分けに使う（``contract`` 側に無いので、ここで持つ）
LIGHT_TECH = ("repulse", "attract", "disarm", "lance")
HOLD_TECH = ("flight", "sight", "barrier")
ULT_TECH = ("sphere",)

#: 技ごとの地の模様。**同じ色相の技には同じ field を割り当てないこと。**
FIELDS = {
    "repulse": "burst", "lance": "streak", "flight": "speed",
    "polarity": "grid", "shard_storm": "slash",
    "attract": "funnel", "sight": "scan", "emp": "pulse", "barrier": "hexmesh",
    "iron_bind": "bars", "throne": "strata",
    "crush": "chevron", "sphere": "collapse",
    "disarm": "flakes", "uprising": "crack",
}


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


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
        self.put(x, y, _mix((r, g, b), c, t), max(oa, a))

    def over(self, x, y, c, t):
        """既に塗ってある画素の上にだけ薄く乗せる（地の模様用）。"""
        x, y = int(round(x)), int(round(y))
        if not (0 <= x < self.s and 0 <= y < self.s):
            return
        r, g, b, oa = self.px[x, y]
        if oa == 0:
            return
        self.put(x, y, _mix((r, g, b), c, t), oa)

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

    def arc(self, cx, cy, r, a0, a1, c, thick=1.4, a=255):
        """角度を切ったリング。破線の枠や走査線に使う。"""
        for y in range(int(cy - r - 1), int(cy + r) + 2):
            for x in range(int(cx - r - 1), int(cx + r) + 2):
                d = math.hypot(x - cx, y - cy)
                if not (r - thick <= d <= r):
                    continue
                ang = math.atan2(y - cy, x - cx) % (2 * math.pi)
                if a0 <= ang <= a1 or a0 <= ang + 2 * math.pi <= a1:
                    self.put(x, y, c, a)

    def line(self, x0, y0, x1, y1, c, a=255, thick=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / max(1, n)
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            for dx in range(thick):
                for dy in range(thick):
                    self.put(x + dx, y + dy, c, a)

    def softline(self, x0, y0, x1, y1, c, t=0.30, thick=1):
        """地の模様用。塗ってある画素の上にだけ薄く乗る。"""
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            k = i / max(1, n)
            x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
            for dx in range(thick):
                for dy in range(thick):
                    self.over(x + dx, y + dy, c, t)

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

    def poly(self, pts, c, a=255):
        for i in range(1, len(pts) - 1):
            self.tri([pts[0], pts[i], pts[i + 1]], c, a)

    def outside(self, x, y, cut=4):
        """角を落とした板の外側か。"""
        s = self.s - 1
        return (x + y < cut or (s - x) + y < cut or x + (s - y) < cut
                or (s - x) + (s - y) < cut)

    def plate(self, base=(24, 20, 34), edge=(58, 48, 82)):
        """角を落とした下地。上が明るく下が沈む、金属板の当たり方。"""
        for y in range(self.s):
            for x in range(self.s):
                if self.outside(x, y):
                    continue
                t = y / (self.s - 1)
                c = _mix(edge, base, 0.30 + 0.70 * t)
                # 中心をわずかに持ち上げると、平らな四角に見えない
                v = 1.0 - math.hypot(x - self.s / 2, y - self.s / 2) / self.s
                self.put(x, y, _mix(c, edge, max(0.0, v) * 0.22))
        for x in range(4, self.s - 4):
            self.put(x, 1, edge)
            self.blend(x, 2, edge, 0.45)
        for y in range(4, self.s - 4):
            self.put(1, y, edge)

    def outline(self, c=(14, 13, 20), a=255):
        """不透明画素の外側に 1px の縁を回す。

        板を持たないアイテム（金属片・インゴット）は、明るいインベントリ
        背景に置くと輪郭が消える。縁を一本入れるだけで、明暗どちらの地でも
        シルエットが立つ。
        """
        edge = []
        for y in range(self.s):
            for x in range(self.s):
                if self.px[x, y][3]:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.s and 0 <= ny < self.s \
                            and self.px[nx, ny][3] > 200:
                        edge.append((x, y))
                        break
        for x, y in edge:
            self.put(x, y, c, a)

    def save(self, path):
        self.img.save(path)


# ===========================================================================
#  地の模様 — 同じ色相の技を引き剥がすための第一の手掛かり
# ===========================================================================
def field(ic: Icon, kind: str, c, light):
    h = ic.s / 2
    if kind == "burst":                       # 放射（斥力）
        for i in range(12):
            a = i * math.pi / 6 + 0.13
            ic.softline(h + math.cos(a) * 5, h + math.sin(a) * 5,
                        h + math.cos(a) * 17, h + math.sin(a) * 17, light, 0.22)
    elif kind == "funnel":                    # 漏斗（引力）
        for i in range(5):
            r = 5 + i * 3
            ic.arc(h, h + 2, r, math.pi * 1.08, math.pi * 1.92, c, 1.0)
    elif kind == "streak":                    # 一本の斜線（貫通）
        for k in (-3, 0, 3):
            ic.softline(1 + k, 30, 30 + k, 1, light, 0.16 if k else 0.30, 2)
    elif kind == "speed":                     # 横に流れる帯（飛行）
        for y in (7, 12, 20, 25):
            ic.softline(2, y, 29, y, light, 0.26, 1)
    elif kind == "grid":                      # 浮かぶ格子（磁極反転）
        for i in range(2, 31, 6):
            ic.softline(i, 2, i, 29, light, 0.20)
            ic.softline(2, i, 29, i, light, 0.20)
    elif kind == "slash":                     # 散る刃（鉄片嵐）
        for i in range(9):
            a = i * 2.4 + 0.7
            x, y = h + math.cos(a) * (6 + i % 4 * 2.4), h + math.sin(a) * (6 + i % 3 * 3)
            ic.softline(x - 2, y - 2, x + 2, y + 2, light, 0.30)
    elif kind == "scan":                      # 走査（磁力視）
        for r in (7, 11, 15):
            ic.arc(6, 6, r, 0.0, math.pi / 2, light, 1.0)
    elif kind == "pulse":                     # 細い二重波紋（EMP）
        for r in (9, 13):
            ic.ring(h, h, r, _mix(c, light, 0.4), 1.0)
    elif kind == "hexmesh":                   # 六角メッシュ（障壁）
        for oy in (-8, 0, 8):
            for ox in (-9, 0, 9):
                pts = [(h + ox + 5 * math.cos(math.pi / 3 * i),
                        h + oy + 5 * math.sin(math.pi / 3 * i))
                       for i in range(6)]
                for i in range(6):
                    ic.softline(pts[i][0], pts[i][1], pts[(i + 1) % 6][0],
                                pts[(i + 1) % 6][1], light, 0.18)
    elif kind == "bars":                      # 縦格子（鋼鉄拘束）
        for x in range(3, 30, 4):
            ic.softline(x, 2, x, 29, light, 0.22)
    elif kind == "strata":                    # 積み重なる板（玉座）
        for y in range(4, 30, 5):
            ic.softline(2, y, 29, y, light, 0.24, 2)
    elif kind == "chevron":                   # 内向きの山（圧壊）
        for i in range(4):
            d = 3 + i * 4
            ic.softline(2, d, h, d + 5, light, 0.26)
            ic.softline(29, d, h, d + 5, light, 0.26)
    elif kind == "collapse":                  # 全周が一点へ（必殺）
        for i in range(16):
            a = i * math.pi / 8
            ic.softline(h + math.cos(a) * 16, h + math.sin(a) * 16,
                        h + math.cos(a) * 6, h + math.sin(a) * 6, light, 0.24)
    elif kind == "flakes":                    # 剥がれ落ちる破片（剥奪）
        for i, (x, y) in enumerate(((5, 21), (11, 26), (24, 19), (19, 27),
                                    (27, 25), (7, 12))):
            ic.rect(x, y, x + 2, y + 1, _mix(c, light, 0.35))
    elif kind == "crack":                     # 地割れ（隆起）
        ic.softline(1, 24, 10, 21, light, 0.34, 1)
        ic.softline(10, 21, 17, 25, light, 0.34, 1)
        ic.softline(17, 25, 30, 20, light, 0.34, 1)


def frame(ic: Icon, name: str, c, light):
    """縁 — 系統を示す。軽 = 細一重 / 保持 = 破線 / 重 = 二重 / 必殺 = 棘付き。

    濃淡は **色を混ぜて** 作る。``put`` はアルファを *上書き* するので、
    半透明で薄めるとアイコンにそのまま穴が開き、インベントリの地が透ける。
    """
    h = ic.s / 2
    dim = _mix(c, (0, 0, 0), 0.45)
    if name in ULT_TECH:
        ic.ring(h, h, 15.0, light, 1.4)
        ic.ring(h, h, 12.4, c, 1.6)
        for i in range(4):
            a = i * math.pi / 2 + math.pi / 4
            ic.line(h + math.cos(a) * 13, h + math.sin(a) * 13,
                    h + math.cos(a) * 17, h + math.sin(a) * 17, light, 255, 2)
    elif name in HOLD_TECH:
        for i in range(4):
            a0 = i * math.pi / 2 + 0.24
            ic.arc(h, h, 14.6, a0, a0 + math.pi / 2 - 0.48, c, 1.5)
    elif name in LIGHT_TECH:
        ic.ring(h, h, 14.6, c, 1.3)
    else:                                       # 重
        ic.ring(h, h, 14.8, c, 2.2)
        ic.ring(h, h, 11.8, dim, 1.0)


# ===========================================================================
#  技のグリフ — §5-5「決め絵」と同じ形にする
# ===========================================================================
def glyph(ic: Icon, name: str, c, light):
    h = ic.s / 2
    white = (255, 255, 255)

    def arrow(ang, r0, r1, size=3.0, col=None, tip=None):
        col, tip = col or c, tip or light
        ax, ay = h + math.cos(ang) * r0, h + math.sin(ang) * r0
        bx, by = h + math.cos(ang) * r1, h + math.sin(ang) * r1
        ic.line(ax, ay, bx, by, col, thick=2)
        px, py = -math.sin(ang), math.cos(ang)
        ic.tri([(bx + math.cos(ang) * size, by + math.sin(ang) * size),
                (bx + px * size * 0.8, by + py * size * 0.8),
                (bx - px * size * 0.8, by - py * size * 0.8)], tip)

    if name == "repulse":
        # 手前で潰れた白い一拍 + 地面すれすれの薄い環
        for i in range(6):
            arrow(i * math.pi / 3, 6.0, 12.0)
        for x in range(4, 29):
            k = math.sin((x - 4) / 24 * math.pi)
            ic.blend(x, 25 - k * 2.0, light, 0.85)
            ic.blend(x, 26 - k * 2.0, light, 0.45)
        ic.disc(h, h, 4.2, light)
        ic.disc(h, h, 2.4, white)
    elif name == "attract":
        # 漏斗状の螺旋。粒が中心へ加速して吸い込まれる
        for i in range(6):
            a = i * math.pi / 3 + 0.2
            arrow(a + math.pi, 12.5, 6.0, 2.8)
        for i in range(10):
            t = i / 9
            a = t * 4.2
            r = 12 - t * 9
            ic.put(h + math.cos(a) * r, h + math.sin(a) * r, light)
        ic.disc(h, h, 3.0, light)
        ic.disc(h, h, 1.6, white)
    elif name == "disarm":
        # 胴の鎧の輪郭が黄白に光り、剥がれ落ちる
        ic.poly([(11, 5), (21, 5), (23, 10), (21, 20), (16, 23), (11, 20),
                 (9, 10)], _mix(c, (0, 0, 0), 0.45))
        ic.poly([(12, 6), (20, 6), (21, 10), (16, 12), (11, 10)], light)
        ic.line(11, 5, 9, 10, white, thick=1)
        ic.line(21, 5, 23, 10, white, thick=1)
        ic.line(9, 10, 11, 20, white, thick=1)
        ic.line(23, 10, 21, 20, white, thick=1)
        # 割れて落ちる二片
        ic.tri([(6, 22), (11, 24), (5, 28)], light)
        ic.tri([(26, 21), (21, 24), (27, 27)], light)
    elif name == "lance":
        # 細く長い一本線が視界を貫き、当たった一点だけ白く弾ける
        ic.line(3, 28, 22, 9, c, thick=3)
        ic.line(4, 27, 21, 10, light, thick=1)
        ic.tri([(28, 3), (18, 8), (23, 13)], light)
        ic.disc(26, 5, 3.4, white)
        for i in range(6):
            a = i * math.pi / 3 + 0.4
            ic.line(26 + math.cos(a) * 4, 5 + math.sin(a) * 4,
                    26 + math.cos(a) * 7, 5 + math.sin(a) * 7, white)
    elif name == "flight":
        # マント後方に紫の帯 2 本。離陸の瞬間だけ足元に円い塵。
        # 帯を主役にする（人の形を大きく描くと「星」に見えてしまう）
        for s in (-1, 1):
            ic.poly([(16 + s * 2, 11), (16 + s * 5, 13), (16 + s * 11, 28),
                     (16 + s * 6, 27)], _mix(c, light, 0.35))
            ic.line(16 + s * 3, 12, 16 + s * 9, 27, white, thick=1)
        ic.disc(16, 6, 3.0, light)                       # 頭
        ic.poly([(13, 9), (19, 9), (18, 19), (14, 19)], light)   # 胴
        ic.disc(16, 5, 1.4, white)
        for x in range(6, 27):                           # 足元の円い塵
            k = math.sin((x - 6) / 20 * math.pi)
            ic.blend(x, 30 - k * 1.6, light, 0.60)
            ic.blend(x, 31 - k * 1.6, light, 0.30)
    elif name == "sight":
        # レンズ越しに、壁の向こうの金属だけが輪郭で光る
        ic.ring(h - 1, h - 1, 10.5, c, 2.0)
        ic.disc(h - 1, h - 1, 8.0, _mix(c, (0, 0, 0), 0.55))
        ic.rect(11, 10, 14, 18, light)
        ic.rect(17, 8, 21, 15, light)
        ic.rect(11, 10, 14, 11, white)
        ic.rect(17, 8, 21, 9, white)
        ic.line(22, 22, 29, 29, light, thick=3)
    elif name == "barrier":
        # 六角面が球殻へ順に点灯する
        # 「順に点灯」は明るさで示す。奥の面ほど暗い色を使う
        for oy, ox, r, k in ((-6, 0, 5.4, 1.00), (2, -7, 5.4, 0.62),
                             (2, 7, 5.4, 0.62), (9, 0, 5.0, 0.34)):
            pts = [(h + ox + r * math.cos(math.pi / 3 * i + math.pi / 6),
                    h + oy + r * math.sin(math.pi / 3 * i + math.pi / 6))
                   for i in range(6)]
            dim = _mix(c, (0, 0, 0), 0.72 - 0.32 * k)
            ic.poly(pts, dim)
            for i in range(6):
                ic.line(pts[i][0], pts[i][1], pts[(i + 1) % 6][0],
                        pts[(i + 1) % 6][1], _mix(dim, light, k))
        ic.disc(h, h - 6, 1.8, white)
    elif name == "shard_storm":
        # 自分を巡る水平の鉄片環。そこから 1 発だけ抜けて飛ぶ
        # 環そのものを太く明るく描く。細い線だと地の模様に負ける
        for i in range(37):
            a = i * math.pi * 2 / 36
            x, y = h + math.cos(a) * 13.0, h + 2 + math.sin(a) * 5.2
            ic.disc(x, y, 1.4, light if math.sin(a) > 0 else
                    _mix(c, light, 0.35))
        for a in (0.5, 2.2, 3.9, 5.5):
            x, y = h + math.cos(a) * 13.0, h + 2 + math.sin(a) * 5.2
            ic.tri([(x - 2.4, y + 2), (x + 2.4, y + 2), (x, y - 4)], white)
        ic.tri([(27, 3), (21, 8), (28, 10)], white)      # 抜ける 1 発
        ic.line(18, 13, 24, 7, light, thick=2)           # その軌跡
    elif name == "iron_bind":
        # 足元から縦の鉄格子が編み上がり、交点で溶接火花
        for i in range(4):
            x = 6 + i * 6.5
            ic.rect(x, 5, x + 2, 27, c)
            ic.rect(x, 5, x, 27, light)
        for y in (10, 22):
            ic.rect(4, y, 28, y + 1, _mix(c, light, 0.45))
        for i in range(4):
            x = 7 + i * 6.5
            for y in (10, 22):
                ic.disc(x, y, 1.6, white)
    elif name == "crush":
        # 相手の輪郭が内へ凹み、赤 chevron が内向きに収束する
        ic.poly([(9, 8), (23, 8), (21, 14), (23, 24), (9, 24), (11, 14)],
                _mix(c, light, 0.20))
        ic.poly([(11, 10), (21, 10), (19, 14), (21, 22), (11, 22), (13, 14)],
                _mix(c, (0, 0, 0), 0.55))
        ic.line(9, 8, 11, 14, white, thick=1)
        ic.line(23, 8, 21, 14, white, thick=1)
        ic.line(11, 14, 9, 24, white, thick=1)
        ic.line(21, 14, 23, 24, white, thick=1)
        for d in (0, 5):
            ic.line(2 + d, 10, 7 + d, 16, light, thick=2)
            ic.line(2 + d, 22, 7 + d, 16, light, thick=2)
            ic.line(30 - d, 10, 25 - d, 16, light, thick=2)
            ic.line(30 - d, 22, 25 - d, 16, light, thick=2)
        ic.disc(h, h, 2.2, white)
    elif name == "uprising":
        # 先に地面が割れ、遅れて土柱。この順序を絵にも残す
        ic.rect(2, 25, 29, 27, _mix(c, (0, 0, 0), 0.45))
        ic.line(2, 25, 9, 23, light, thick=1)
        ic.line(9, 23, 15, 26, light, thick=1)
        ic.line(15, 26, 22, 22, light, thick=1)
        ic.line(22, 22, 29, 25, light, thick=1)
        for x, top, w in ((8, 13, 3), (16, 5, 4), (24, 15, 3)):
            ic.poly([(x - w, 25), (x - w + 1, top + 2), (x, top),
                     (x + w - 1, top + 2), (x + w, 25)], c)
            ic.line(x, top, x, 24, light, thick=1)
    elif name == "emp":
        # 無彩色に近い白青の薄い二重波紋 + 消える機械の目
        ic.ring(h, h, 14.0, _mix(c, light, 0.55), 1.2)
        ic.ring(h, h, 10.0, light, 1.2)
        ic.rect(9, 14, 23, 18, _mix(c, (0, 0, 0), 0.62))
        ic.rect(10, 15, 22, 17, _mix(c, (0, 0, 0), 0.25))
        ic.line(9, 12, 23, 12, light, thick=1)
        ic.line(8, 11, 24, 21, white, thick=2)          # 消灯の斜線
        ic.line(19, 3, 13, 13, white, thick=2)
        ic.line(13, 13, 18, 13, white, thick=2)
        ic.line(18, 13, 12, 24, white, thick=2)
    elif name == "polarity":
        # 空中に格子が浮き、周囲の物が同時に上がる
        for i in range(4):
            y = 26 - i * 2
            ic.line(4 + i, y, 28 - i, y, _mix(c, light, 0.25))
        for i in range(3):
            x = 8 + i * 8
            ic.line(x, 27, x + 3, 19, _mix(c, light, 0.25))
        for x, y in ((9, 13), (16, 8), (23, 14)):
            ic.rect(x - 2, y, x + 2, y + 4, c)
            ic.rect(x - 2, y, x + 2, y, light)
            ic.tri([(x, y - 5), (x - 3, y - 1), (x + 3, y - 1)], light)
    elif name == "throne":
        # 足元へ鉄板が集まり、玉座に組み上がる
        ic.rect(5, 22, 27, 25, _mix(c, (0, 0, 0), 0.35))
        ic.rect(5, 22, 27, 22, light)
        ic.rect(3, 26, 29, 28, _mix(c, (0, 0, 0), 0.5))
        ic.rect(3, 26, 29, 26, _mix(c, light, 0.4))
        ic.rect(8, 6, 24, 9, _mix(c, (0, 0, 0), 0.25))    # 背もたれ
        ic.rect(8, 6, 24, 6, light)
        ic.rect(8, 9, 11, 22, c)
        ic.rect(21, 9, 24, 22, c)
        ic.rect(8, 9, 8, 22, light)
        ic.rect(21, 9, 21, 22, light)
    elif name == "sphere":
        # 全てが一点へ吸われ、完全な静止、そして白
        ic.disc(h, h, 10.5, _mix(c, (0, 0, 0), 0.30))
        ic.disc(h, h, 7.5, c)
        ic.disc(h, h, 4.6, _mix(c, white, 0.55))
        ic.disc(h, h, 2.4, white)
        ic.ring(h, h, 10.5, light, 1.4)
        for i in range(8):
            a = i * math.pi / 4 + math.pi / 8
            ic.line(h + math.cos(a) * 16, h + math.sin(a) * 16,
                    h + math.cos(a) * 11.5, h + math.sin(a) * 11.5, light,
                    thick=2)
    else:
        ic.ring(h, h, 9, c, 2.0)
        ic.disc(h, h, 3.0, light)


def tech_icon(ic: Icon, name: str, colour: str):
    """技アイコン一枚。地 → 模様 → 枠 → 図形 の順で重ねる。"""
    c = _hex(colour)
    light = _mix(c, (255, 255, 255), 0.60)
    # 地は基調色で染める。彩度を残したまま暗くすると、暗所でも色相が読める
    ic.plate(base=_mix(c, (10, 9, 16), 0.86), edge=_mix(c, (12, 10, 20), 0.50))
    field(ic, FIELDS.get(name, "burst"), c, light)
    frame(ic, name, c, light)
    glyph(ic, name, c, light)
    ic.outline()


# ===========================================================================
#  中核アイテム
# ===========================================================================
def _helmet_shape(ic: Icon):
    """マグニートーの兜 — ドーム / 跳ね上がる二枚のフィン / 覗く顔。

    32px では細部が一切効かないので、**外形だけ** で兜と判らせる。
    決め手は「上へ跳ねる二本の角」と「顔がほとんど出ている開口」の二つ。
    """
    steel = (158, 166, 178)
    steel_m = (120, 128, 140)
    steel_d = (78, 84, 94)
    steel_l = (224, 231, 240)
    skin = (226, 190, 158)

    # フィン。ドームと同じ鋼色で、根元を太く外上へ流す。
    # ここを白く細く描くと兎の耳に見えるので、幅と色をドームに揃える。
    for s in (-1, 1):
        ic.poly([(16 + s * 4, 10), (16 + s * 7, 4), (16 + s * 13, 0),
                 (16 + s * 15, 4), (16 + s * 10, 9), (16 + s * 8, 14)], steel)
        ic.line(16 + s * 7, 4, 16 + s * 13, 0, steel_l, thick=1)
        ic.line(16 + s * 4, 10, 16 + s * 7, 4, steel_l, thick=1)
        ic.line(16 + s * 8, 14, 16 + s * 10, 9, steel_d, thick=1)
    # ドーム（丸い天頂 → 直に落ちる側面）
    ic.poly([(8, 27), (7, 16), (10, 9), (16, 6), (22, 9), (25, 16), (24, 27)],
            steel)
    ic.poly([(8, 27), (7, 16), (10, 9), (13, 7), (11, 16), (11, 27)], steel_l)
    ic.poly([(22, 9), (25, 16), (24, 27), (21, 27), (21, 16)], steel_m)
    # M 字の谷。**小さく浅く**。大きく抉ると兜が割れて見える
    ic.tri([(14, 6), (18, 6), (16, 11)], steel_d)
    ic.line(14, 6, 16, 11, steel_l)
    ic.line(18, 6, 16, 11, steel_l)
    # 顔の開口（縦長のスリット）と、それを挟む頬当て
    ic.rect(13, 15, 19, 26, skin)
    ic.rect(12, 15, 12, 27, steel_d)
    ic.rect(20, 15, 20, 27, steel_d)
    ic.rect(13, 14, 19, 15, steel_d)
    # 目と顎
    ic.rect(14, 18, 15, 19, (46, 44, 62))
    ic.rect(17, 18, 18, 19, (46, 44, 62))
    ic.rect(13, 25, 19, 26, (198, 162, 132))


def core_icon(ic: Icon, key: str):
    h = ic.s / 2
    if key == "x_gene":
        ic.rect(12, 4, 19, 7, (168, 176, 188))              # 蓋
        ic.rect(11, 7, 20, 28, (36, 40, 52))                # ガラス
        ic.rect(13, 12, 18, 27, (170, 112, 240))            # 中身
        ic.rect(13, 12, 18, 13, (218, 186, 255))
        for i in range(5):                                   # 二重螺旋
            y = 13 + i * 3
            ic.put(13 + int(2 + 2 * math.sin(i)), y, (240, 220, 255))
            ic.put(18 - int(2 + 2 * math.sin(i)), y, (240, 220, 255))
        ic.rect(11, 7, 11, 28, (140, 148, 164))
        ic.rect(20, 7, 20, 28, (78, 84, 96))
    elif key == "magneto_helmet":
        _helmet_shape(ic)
    elif key == "brotherhood_pin":
        ic.disc(h, h, 12, (40, 34, 46))
        ic.disc(h, h, 10, (168, 24, 48))
        ic.disc(h, h - 2, 8, (196, 40, 66))
        ic.line(9, 9, 23, 23, (244, 244, 250), thick=3)
        ic.line(23, 9, 9, 23, (244, 244, 250), thick=3)
        ic.ring(h, h, 12, (198, 204, 216), 1.6)
        ic.arc(h, h, 12, math.pi * 1.1, math.pi * 1.9, (250, 252, 255), 1.6)
    elif key == "cerebro":
        ic.ring(h, h + 2, 12, (176, 184, 198), 2.4)
        ic.arc(h, h + 2, 12, math.pi * 1.05, math.pi * 1.95, (232, 238, 248),
               2.4)
        ic.rect(6, 12, 26, 18, (26, 30, 42))
        for x in range(7, 26):
            t = math.sin((x - 7) / 19 * math.pi)
            ic.blend(x, 14, (110, 220, 255), t)
            ic.blend(x, 15, (170, 240, 255), t)
        ic.rect(4, 10, 7, 20, (140, 148, 164))
        ic.rect(25, 10, 28, 20, (110, 118, 134))
    elif key == "brotherhood_beacon":
        ic.tri([(16, 3), (7, 16), (25, 16)], (206, 48, 72))
        ic.tri([(16, 4), (9, 15), (16, 15)], (238, 88, 110))
        ic.rect(7, 16, 25, 26, (70, 60, 84))
        ic.rect(7, 16, 25, 17, (110, 96, 128))
        ic.disc(16, 21, 4, (255, 130, 160))
        ic.disc(16, 21, 2, (255, 245, 252))
        for i in range(3):
            ic.line(3, 6 + i * 3, 7, 8 + i * 3, (255, 170, 190))
            ic.line(29, 6 + i * 3, 25, 8 + i * 3, (255, 170, 190))
    elif key == "metal_scrap":
        for (x, y, w, ht) in ((6, 14, 9, 5), (16, 9, 8, 6), (12, 20, 11, 5)):
            ic.rect(x, y, x + w, y + ht, (150, 158, 172))
            ic.rect(x, y, x + w, y + 1, (222, 228, 238))
            ic.rect(x, y + ht - 1, x + w, y + ht, (82, 88, 100))
    elif key == "magnetic_alloy":
        ic.tri([(4, 22), (10, 10), (28, 10)], (172, 180, 194))
        ic.rect(4, 22, 28, 26, (134, 142, 156))
        ic.tri([(22, 10), (28, 10), (28, 26)], (92, 98, 112))
        ic.rect(10, 10, 28, 12, (226, 232, 242))
        for i in range(3):
            ic.line(12 + i * 6, 13, 12 + i * 6, 21, (188, 136, 255), thick=2)
    elif key == "sentinel_core":
        ic.disc(h, h, 12, (74, 64, 112))
        ic.ring(h, h, 12, (158, 144, 210), 2.0)
        ic.disc(h, h, 7, (255, 118, 54))
        ic.disc(h, h, 4.2, (255, 190, 118))
        ic.disc(h, h, 2.0, (255, 244, 226))
        for i in range(4):
            a = i * math.pi / 2 + math.pi / 4
            ic.line(h + math.cos(a) * 7, h + math.sin(a) * 7,
                    h + math.cos(a) * 12, h + math.sin(a) * 12,
                    (255, 190, 120), thick=2)
    elif key == "adamantium_ingot":
        ic.tri([(4, 22), (10, 10), (28, 10)], (216, 224, 236))
        ic.rect(4, 22, 28, 26, (182, 190, 204))
        ic.tri([(22, 10), (28, 10), (28, 26)], (134, 142, 156))
        ic.rect(10, 10, 28, 12, (252, 253, 255))
        ic.line(13, 14, 19, 20, (255, 255, 255), thick=2)
        ic.line(19, 14, 13, 20, (236, 242, 252), thick=1)
    else:
        ic.disc(h, h, 10, (126, 106, 178))
        ic.disc(h, h, 5, (208, 182, 255))
    # 素材アイコンは板を持たないので、縁を一本回して地から切り離す
    ic.outline()


def form_icon(ic: Icon, character: str, tech: str | None = None):
    """変身体アイテム — 普段は見えないので、影のシルエットで十分。

    ただし技ごとに 15 枚ずつ増えるので、技のある変身体には基調色の点を
    足しておく。デバッグでアイテム欄を見たときに、どれがどれか判る。
    """
    pal = K.CHARACTERS[character]["egg"]
    base, accent = _hex(pal[0]), _hex(pal[1])
    ic.disc(16, 11, 6, base)
    ic.tri([(16, 15), (6, 30), (26, 30)], base)
    ic.disc(16, 11, 3.4, accent)
    ic.line(9, 24, 23, 24, accent)
    if tech and tech in K.TECHNIQUES:
        ic.disc(27, 5, 3.4, _hex(K.TECHNIQUES[tech]["colour"]))
        ic.disc(27, 5, 1.6, (255, 255, 255))
    ic.outline()


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
        emit(spec["item"],
             lambda ic, n=name, col=spec["colour"]: tech_icon(ic, n, col))

    for character, tech, _g, _n in K.form_variants():
        emit(K.form_key(character, tech),
             lambda ic, c=character, t=tech: form_icon(ic, c, t))

    return atlas
