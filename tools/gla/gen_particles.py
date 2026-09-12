# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — パーティクルとスプライト表 (企画書 §11)。

企画書 §11 の「5つの層」をそのまま実装した層。技の見た目は

    1 予兆  次にどちらへ動くかを見せる。収束し、遅く、身体を隠さない
    2 軌道  始点と終点がはっきりある。動く向きに沿わせる
    3 接触  短く強い。当たった時だけ出す（空振りに見せない）
    4 広がり 外へ開く。寿命は短く、地面と相手を読ませ続ける
    5 余韻  消える。ぷつっと消さない。次の入力を邪魔しない

の5層に分かれていて、品質設定 (spec.QUALITY) はこの層番号で削る。だから
ここでも層ごとに節を分け、節の頭にその層が「何を守るのか」を書いてある。
層の約束（寿命・明るさ・大きさ）は check_layers() が生成物を読み直して
検査するので、書いた意図と出力がずれたままビルドは通らない。

色は palette.py（形態ごとの色設計）から引く。技ごとに色を打ち直すと、
形態の色とパーティクルの色が別々に腐るため。spec.py と palette.py に
無いものだけ、この file のローカル定数として置いてある。

加算合成 (particles_add) は使わない。白飛びが企画書 §08「強い点滅は使わない」
に正面からぶつかるので、すべて particles_blend で、上限の明るさで抑える。
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import mctexture                                        # noqa: E402
from mctexture import Painter                           # noqa: E402

import palette                                          # noqa: E402
import spec                                             # noqa: E402

RP = os.path.join(ROOT, spec.RP_DIR)
PART_DIR = os.path.join(RP, "particles")
TEX_DIR = os.path.join(RP, "textures", "particle", spec.NS)

# スプライト表。1枚に集約し、UV の小窓で切り出す（怪獣8号側と同じ作り）。
# 相対パスは RP から見た位置で、そのまま basic_render_parameters.texture になる。
SHEET = f"{spec.NS}_particles"
TEXTURE = f"textures/particle/{spec.NS}/{SHEET}"

CELL = 32
COLS = 8
ATLAS_W = CELL * COLS

# 同時表示の見積り上限。企画書 §11 は画面全体で 900（標準）なので、
# 同時に技を振るのは多くて3人と見て 900/3、さらに余白を取ってこの値にする。
SOLO_BUDGET = 260

# ---------------------------------------------------------------------------
#  スプライト表 — 1セル 32x32。技ではなく「質感の族」で並べる。
#  行を跨いで族が割れると描き足すときに迷うので、1行に2〜3族まで。
# ---------------------------------------------------------------------------
CELLS = {
    # 0行: ゴムの伸縮と、速さそのもの
    "coil": (0, 0),        # 伸ばす前の巻き。同心の楕円
    "band": (1, 0),        # 伸びきったゴムの帯
    "snap": (2, 0),        # 弾けて戻る帯。折れた線
    "pop": (3, 0),         # 小さく弾ける輪
    "streak": (4, 0),      # 速度線。細い紡錘
    "dart": (5, 0),        # 矢羽。ギア2の鋭さ
    "blur": (6, 0),        # 連打の残像。横に流れた塊
    "ghost": (7, 0),       # 回避の残像。人影の輪郭だけ
    # 1行: 蒸気・炎・膨張
    "wisp": (0, 1),        # 巻き上がる蒸気の尾
    "vapor": (1, 1),       # 柔らかい蒸気の塊
    "flame": (2, 1),       # 炎の舌
    "spark": (3, 1),       # 火の粉。尾を引く粒
    "bulge": (4, 1),       # 張った面。ギア3の膨張
    "puff": (5, 1),        # 三つ葉の綿。抜ける空気
    "fist": (6, 1),        # 拳のシルエット。猿神銃の線に置く
    "sweep": (7, 1),       # 太い三日月。振り下ろし
    # 2行: 覇気・蛇・ニカ
    "haki_orb": (0, 2),    # 覇気の塊。中は暗く縁だけ明るい
    "haki_flake": (1, 2),  # 覇気の破片
    "haki_band": (2, 2),   # 覇気の帯。上縁が光る
    "serp": (3, 2),        # S字のリボン。スネイクマン
    "fang": (4, 2),        # 鉤爪。曲がって食いつく
    "cloud": (5, 2),       # 雲の房。ギア5
    "bloom": (6, 2),       # 柔らかい広がり。芯を作らない
    "glint": (7, 2),       # 六方の小さな輝き
    # 3行: 雷・土砂・輪
    "bolt": (0, 3),        # 稲妻
    "fork": (1, 3),        # 枝分かれの小火花
    "chunk": (2, 3),       # 岩片
    "grit": (3, 3),        # ざらついた砂
    "fissure": (4, 3),     # 地割れ
    "ring": (5, 3),        # 細い輪
    "shock": (6, 3),       # 太い衝撃輪。外縁が明るい
    "halo2": (7, 3),       # 二重の輪。風
    # 4行: 接触の跡と指向
    "dashring": (0, 4),    # 破線の輪。ゴムの波
    "burst": (1, 4),       # 放射。軽い接触
    "cross": (2, 4),       # 十字の芯。重い接触
    "crater": (3, 4),      # 割れを含む輪。最も重い接触
    "chevron": (4, 4),     # 指向マーク
    "wedge": (5, 4),       # 押し出すくさび
    "dome": (6, 4),        # 地面の盛り上がり
    "mote": (7, 4),        # ごく小さな粒
}
ATLAS_H = CELL * (max(c[1] for c in CELLS.values()) + 1)

H = CELL / 2.0


def _pw(v: float, e: float) -> float:
    """負の値の分数乗を避けた冪。0未満は0に潰す。"""
    return max(0.0, v) ** e


def _near(u, v, a, b):
    """線分 a-b への距離と、その点での太さ（頂点ごとに補間）。"""
    ax, ay, aw = a
    bx, by, bw = b
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = 0.0 if ll <= 1e-9 else max(0.0, min(1.0, ((u - ax) * dx +
                                                  (v - ay) * dy) / ll))
    return math.hypot(u - (ax + dx * t), v - (ay + dy * t)), aw + (bw - aw) * t


def build_atlas() -> Painter:
    """スプライト表を描く。

    塗りは白＋アルファが原則（色は tinting で乗せる）。覇気だけは例外で、
    明度を焼き込む — 単色の tint では「暗い塊＋明るい縁」が作れず、
    palette.py が禁じている「真っ黒な筒」になってしまうため (企画書 §04)。
    """
    p = Painter(ATLAS_W, ATLAS_H, mctexture._h(SHEET) % 9000)

    def cell(name):
        cx, cy = CELLS[name]
        return cx * CELL, cy * CELL

    def paint(name, fn):
        """fn(u, v) -> a  または (a, 明度)。u,v は -1..1、v は下が正。"""
        ox, oy = cell(name)
        for y in range(CELL):
            for x in range(CELL):
                r = fn((x - H + 0.5) / H, (y - H + 0.5) / H)
                a, lum = r if isinstance(r, tuple) else (r, 1.0)
                if a > 0.004:
                    p.put(ox + x, oy + y, (int(255 * lum),) * 3,
                          min(255, int(a * 255)))

    def stroke(name, pts, soft=0.7, lum=1.0, extra=None):
        """(x, y, 太さ) の折れ線。線だけの絵はこちらで描く。"""
        def fn(u, v):
            best = 9.0
            for i in range(len(pts) - 1):
                d, w = _near(u, v, pts[i], pts[i + 1])
                best = min(best, d / max(w, 1e-6))
            a = _pw(1 - best, soft)
            if extra:
                a = max(a, extra(u, v))
            return (a, lum) if a > 0 else 0.0
        paint(name, fn)

    # ---- ゴムの伸縮 -----------------------------------------------------
    # 「伸びる」を1枚で見せられないので、巻き→帯→弾けの3枚に分けてある。
    def coil(u, v):
        best = 0.0
        for i in range(3):
            rr = 0.90 - i * 0.27
            d = math.hypot(u, (v - (i - 1) * 0.11) / 0.66)
            best = max(best, _pw(1 - abs(d - rr) / 0.12, 1.3) * (1 - i * 0.16))
        return best
    paint("coil", coil)

    def band(u, v):
        if abs(u) > 0.97:
            return 0.0
        bow = 0.15 * math.cos(u * math.pi * 0.5)
        t = 0.30 * _pw(1 - u * u, 0.45) + 0.02
        return _pw(1 - abs(v - bow) / t, 0.65)
    paint("band", band)

    stroke("snap", [(-0.92, 0.48, 0.05), (-0.20, -0.34, 0.11),
                    (0.26, 0.30, 0.09), (0.86, -0.44, 0.04)], soft=0.8)

    def pop(u, v):
        d = math.hypot(u, v)
        ring = _pw(1 - abs(d - 0.46) / 0.15, 1.2)
        ang = math.atan2(v, u)
        spike = 0.0
        if 0.54 < d < 0.96:
            spike = _pw(abs(math.cos(ang * 3.0)), 14) * (1 - (d - 0.54) / 0.42)
        return max(ring, spike)
    paint("pop", pop)

    # ---- 速さ -----------------------------------------------------------
    def streak(u, v):
        t = 0.13 * _pw(1 - u * u, 0.6) + 0.008
        return _pw(1 - abs(v) / t, 0.5)
    paint("streak", streak)

    def dart(u, v):
        if u > 0.94 or u < -0.94:
            return 0.0
        w = 0.36 * _pw((0.94 - u) / 1.88, 0.75)
        if abs(v) > w:
            return 0.0
        notch = 0.42 * max(0.0, (-0.42 - u) / 0.52)
        if abs(v) < notch:
            return 0.0
        return 0.55 + 0.45 * _pw(1 - abs(v) / max(w, 1e-6), 0.5)
    paint("dart", dart)

    def blur(u, v):
        body = _pw(1 - math.hypot(u, v / 0.44), 1.3) * 0.72
        smear = 0.0
        for k in (-0.24, 0.0, 0.24):
            smear = max(smear, _pw(1 - abs(v - k) / 0.055, 0.8) *
                        _pw(1 - abs(u), 0.5) * 0.85)
        return max(body, smear)
    paint("blur", blur)

    def ghost(u, v):
        # 残像は補助。薄すぎると何も見えないので、輪郭だけは残す濃さにする。
        body = _pw(1 - math.hypot(u / 0.54, (v + 0.04) / 0.96), 0.9) * 0.85
        head = _pw(1 - math.hypot(u / 0.30, (v + 0.62) / 0.30), 1.0) * 0.55
        return max(body, head)
    paint("ghost", ghost)

    # ---- 蒸気 -----------------------------------------------------------
    # ギア2の蒸気。輪郭を柔らかくし、消えても形態が読めるよう薄く作る。
    def wisp(u, v):
        vv = (v + 1) * 0.5
        cx = 0.42 * math.sin((1 - vv) * 2.1) - 0.12
        w = 0.34 * _pw(vv, 0.85) + 0.05
        return _pw(1 - abs(u - cx) / w, 1.05) * 0.82
    paint("wisp", wisp)

    def vapor(u, v):
        n = 0.90 + 0.22 * math.sin(u * 5.1) * math.cos(v * 4.3)
        return _pw(1 - math.hypot(u, v) / n, 1.7) * 0.76
    paint("vapor", vapor)

    # ---- 炎 -------------------------------------------------------------
    def flame(u, v):
        vv = (1 - v) * 0.5
        if not 0.0 < vv < 0.99:
            return 0.0
        w = 0.44 * _pw(1 - vv, 0.55) * (0.55 + 0.45 * math.sin(vv * 3.0))
        cx = 0.22 * vv * vv * math.sin(vv * 4.2)
        d = abs(u - cx)
        if d > w:
            return 0.0
        a = 0.5 + 0.5 * _pw(1 - d / max(w, 1e-6), 0.6)
        if vv < 0.16 and d < w * 0.36:       # 根元は中空。べた塗りに見せない
            a *= 0.35
        return a
    paint("flame", flame)

    def spark(u, v):
        core = _pw(1 - math.hypot(u / 0.26, (v - 0.34) / 0.26), 1.3)
        tail = 0.0
        if -0.62 < v < 0.34:
            tw = 0.16 * (v + 0.62) / 0.96 + 0.02
            tail = _pw(1 - abs(u) / tw, 0.9) * 0.55
        return max(core, tail)
    paint("spark", spark)

    # ---- 膨張 -----------------------------------------------------------
    # ギア3。中身が詰まって張っている面。輪郭より「張り」で読ませる。
    def bulge(u, v):
        d = math.hypot(u, v)
        if d > 1.0:
            return 0.0
        body = _pw(1 - d, 0.85) * 0.55
        lit = max(0.0, -0.45 * u - 0.72 * v + 0.45)
        rim = _pw(1 - abs(d - 0.86) / 0.14, 1.3) * (0.40 + 0.60 * lit)
        return max(body, rim)
    paint("bulge", bulge)

    def puff(u, v):
        best = 0.0
        for cx, cy, r in ((-0.38, 0.18, 0.54), (0.34, 0.22, 0.50),
                          (0.0, -0.32, 0.58)):
            best = max(best, _pw(1 - math.hypot(u - cx, v - cy) / r, 1.2))
        return best * 0.88
    paint("puff", puff)

    # ---- 拳と振り下ろし ---------------------------------------------------
    def fist(u, v):
        body = 1.0 - (abs(u / 0.70) ** 3 + abs((v - 0.16) / 0.50) ** 3)
        a = _pw(body, 0.30)
        for cx in (-0.50, -0.17, 0.16, 0.49):
            a = max(a, _pw(1 - math.hypot(u - cx, v + 0.34) / 0.21, 0.4))
        a = max(a, _pw(1 - math.hypot(u - 0.64, v - 0.28) / 0.23, 0.4))
        return a
    paint("fist", fist)

    def sweep(u, v):
        d1 = math.hypot(u, v)
        d2 = math.hypot(u - 0.36, v * 1.04)
        if d1 > 0.97 or d2 < 0.60:
            return 0.0
        return min(_pw((0.97 - d1) / 0.16, 0.7), _pw((d2 - 0.60) / 0.16, 0.7))
    paint("sweep", sweep)

    # ---- 覇気 -----------------------------------------------------------
    # ここだけ明度を焼く。暗い基本色に面方向のハイライト (palette.py §覇気)。
    HAKI_BODY = 0.26
    def haki_orb(u, v):
        d = math.hypot(u, v)
        if d > 0.99:
            return 0.0
        a = 1.0 if d < 0.90 else _pw((0.99 - d) / 0.09, 0.6)
        rim = _pw(1 - abs(d - 0.85) / 0.17, 1.5)
        lit = 0.35 + 0.65 * max(0.0, -0.5 * u - 0.7 * v + 0.5)
        return a, HAKI_BODY + (1 - HAKI_BODY) * rim * lit
    paint("haki_orb", haki_orb)

    def haki_flake(u, v):
        f = abs(u * 0.92 + v * 0.30) ** 0.8 + abs(v * 1.15 - u * 0.24) ** 0.8
        if f > 0.86:
            return 0.0
        rim = _pw(1 - (0.86 - f) / 0.22, 1.1)
        return 1.0, HAKI_BODY + (1 - HAKI_BODY) * rim
    paint("haki_flake", haki_flake)

    def haki_band(u, v):
        if abs(u) > 0.96:
            return 0.0
        t = 0.32 * _pw(1 - u * u, 0.40) + 0.02
        if abs(v) > t:
            return 0.0
        rel = (v + t) / (2 * t)                 # 0 が上縁
        a = _pw(1 - abs(v) / t, 0.35)
        return a, HAKI_BODY + (1 - HAKI_BODY) * _pw(1 - rel / 0.26, 0.8)
    paint("haki_band", haki_band)

    # ---- 蛇 -------------------------------------------------------------
    def serp(u, v):
        vv = (v + 1) * 0.5
        cx = 0.52 * math.sin(v * 2.7)
        w = 0.21 * _pw(1 - vv, 0.7) + 0.035
        a = _pw(1 - abs(u - cx) / w, 0.85)
        head = _pw(1 - math.hypot((u - 0.52 * math.sin(-2.7)) / 0.20,
                                  (v + 1.0) / 0.26), 0.7)
        return max(a, head)
    paint("serp", serp)

    def fang(u, v):
        d = math.hypot(u + 0.18, v)
        ang = math.atan2(v, u + 0.18)
        t = (ang + math.pi * 0.25) / (math.pi * 1.20)
        if not 0.0 <= t <= 1.0:
            return 0.0
        w = 0.17 * _pw(1 - t, 0.9) + 0.015
        return _pw(1 - abs(d - 0.66) / w, 0.85)
    paint("fang", fang)

    # ---- ニカ -----------------------------------------------------------
    # 雲は柔らかく、広がりは芯を作らない。純白の閃光にしない (企画書 §08)。
    def cloud(u, v):
        best = 0.0
        for cx, cy, r in ((-0.56, 0.16, 0.42), (-0.18, -0.08, 0.52),
                          (0.24, 0.00, 0.48), (0.58, 0.20, 0.38),
                          (0.02, 0.30, 0.52)):
            best = max(best, _pw(1 - math.hypot(u - cx, v - cy) / r, 1.25))
        return best * 0.86 * (1.0 if v < 0.52 else _pw((0.96 - v) / 0.44, 1.0))
    paint("cloud", cloud)

    def bloom(u, v):
        d = math.hypot(u, v)
        soft = _pw(1 - d, 2.4) * 0.62
        corona = _pw(1 - abs(d - 0.52) / 0.34, 1.6) * 0.26
        return min(0.88, soft + corona)
    paint("bloom", bloom)

    def glint(u, v):
        best = 0.0
        for k in range(3):
            a = k * math.pi / 3.0
            uu = u * math.cos(a) + v * math.sin(a)
            vv = -u * math.sin(a) + v * math.cos(a)
            best = max(best, _pw(1 - abs(vv) / 0.055, 0.6) *
                       _pw(1 - abs(uu), 1.3))
        return max(best, _pw(1 - math.hypot(u, v) / 0.26, 1.6))
    paint("glint", glint)

    # ---- 雷 -------------------------------------------------------------
    stroke("bolt", [(0.02, -0.96, 0.055), (0.40, -0.52, 0.050),
                    (-0.26, -0.10, 0.045), (0.30, 0.36, 0.040),
                    (-0.10, 0.96, 0.030)], soft=0.55)
    stroke("fork", [(0.0, 0.92, 0.05), (0.04, 0.16, 0.055),
                    (-0.42, -0.66, 0.035)], soft=0.6,
           extra=lambda u, v: _pw(1 - min(
               _near(u, v, (0.04, 0.16, 0.05), (0.46, -0.58, 0.03))[0] / 0.05,
               9.0), 0.6))

    # ---- 土砂 -----------------------------------------------------------
    def chunk(u, v):
        d = math.hypot(u, v)
        ang = math.atan2(v, u)
        r = 0.60 + 0.20 * math.sin(ang * 3 + 0.7) + 0.10 * math.cos(ang * 5)
        if d > r:
            return 0.0
        return 1.0 if (u * 0.7 + v * 0.7) < 0.12 else 0.72
    paint("chunk", chunk)

    def grit(u, v):
        a = _pw(1 - math.hypot(u, v), 1.7) * 0.9
        return a * (0.35 if p.rng.random() < 0.32 else 1.0)
    paint("grit", grit)

    stroke("fissure", [(-0.96, 0.10, 0.045), (-0.34, -0.06, 0.055),
                       (0.20, 0.08, 0.050), (0.94, -0.12, 0.030)], soft=0.7,
           extra=lambda u, v: max(
               _pw(1 - _near(u, v, (-0.34, -0.06, 0.03),
                             (-0.52, 0.62, 0.012))[0] / 0.03, 0.7),
               _pw(1 - _near(u, v, (0.20, 0.08, 0.03),
                             (0.34, -0.68, 0.012))[0] / 0.03, 0.7)))

    # ---- 輪 -------------------------------------------------------------
    def ring(u, v):
        d = math.hypot(u, v)
        return max(_pw(1 - abs(d - 0.84) / 0.11, 1.4),
                   _pw(1 - d, 3.6) * 0.16)
    paint("ring", ring)

    def shock(u, v):
        d = math.hypot(u, v)
        if d > 1.0:
            return 0.0
        return _pw(1 - (1.0 - d) / 0.42, 1.0)
    paint("shock", shock)

    def halo2(u, v):
        d = math.hypot(u, v)
        a = max(_pw(1 - abs(d - 0.93) / 0.065, 1.3),
                _pw(1 - abs(d - 0.64) / 0.05, 1.3) * 0.62)
        ang = math.atan2(v, u)
        if 0.70 < d < 0.88:
            a = max(a, _pw(abs(math.cos(ang * 4)), 22) * 0.5)
        return a
    paint("halo2", halo2)

    def dashring(u, v):
        d = math.hypot(u, v)
        gate = _pw((abs(math.sin(math.atan2(v, u) * 6)) - 0.34) / 0.66, 0.5)
        return _pw(1 - abs(d - 0.80) / 0.15, 1.2) * gate
    paint("dashring", dashring)

    # ---- 接触の跡 -------------------------------------------------------
    # 軽い→放射、重い→十字、最も重い→割れを含む輪。当たった重さで形が変わる。
    def burst(u, v):
        d = math.hypot(u, v)
        if d > 1.0:
            return 0.0
        spokes = _pw(abs(math.cos(math.atan2(v, u) * 2.5)), 4)
        return _pw(1 - d, 0.9) * (0.18 + 0.82 * spokes)
    paint("burst", burst)

    def cross(u, v):
        ax = _pw(1 - abs(v) / (0.16 * _pw(1 - abs(u), 0.8) + 0.02), 0.8)
        ay = _pw(1 - abs(u) / (0.16 * _pw(1 - abs(v), 0.8) + 0.02), 0.8)
        return max(ax, ay, _pw(1 - math.hypot(u, v) / 0.30, 1.4))
    paint("cross", cross)

    def crater(u, v):
        d = math.hypot(u, v)
        ring_a = _pw(1 - abs(d - 0.74) / 0.17, 1.2)
        crack = 0.0
        if 0.18 < d < 1.0:
            crack = _pw(abs(math.cos(math.atan2(v, u) * 3)), 26) * \
                _pw(1 - d, 0.5)
        return max(ring_a, crack, _pw(1 - d, 1.6) * 0.18)
    paint("crater", crater)

    # ---- 指向と地形 -----------------------------------------------------
    def chevron(u, v):
        if abs(v) > 0.86:
            return 0.0
        return _pw(1 - abs(u + 0.85 * abs(v) - 0.22) / 0.15, 1.0)
    paint("chevron", chevron)

    def wedge(u, v):
        if abs(u) > 0.92:
            return 0.0
        hh = 0.08 + 0.60 * (u + 0.92) / 1.84
        if abs(v) > hh:
            return 0.0
        edge = _pw((abs(v) - (hh - 0.16)) / 0.16, 0.7)
        return (0.42 + 0.58 * edge) * _pw((0.96 - u) / 1.9, 0.35)
    paint("wedge", wedge)

    def dome(u, v):
        if v < -0.06 or v > 0.62:
            return 0.0
        f = 1.0 - ((u / 0.86) ** 2 + ((v - 0.60) / 0.74) ** 2)
        if f < 0:
            return 0.0
        return max(_pw(f, 0.35) * 0.55, _pw(1 - abs(f - 0.06) / 0.16, 1.0))
    paint("dome", dome)

    paint("mote", lambda u, v: _pw(1 - math.hypot(u, v) / 0.30, 1.6))

    os.makedirs(TEX_DIR, exist_ok=True)
    # 明度を焼いた覇気が posterize で潰れないよう量子化はしない。
    p.save(os.path.join(TEX_DIR, SHEET + ".png"), posterize=1)
    print(f"  atlas {ATLAS_W}x{ATLAS_H} ({len(CELLS)} sprites) -> {TEXTURE}.png")
    return p


# ---------------------------------------------------------------------------
#  パーティクル定義
# ---------------------------------------------------------------------------
def uv_of(name):
    cx, cy = CELLS[name]
    return [cx * CELL, cy * CELL]


def effect(identifier, cell, *, count=12, life=0.5, speed=4.0,
           size=(0.25, 0.25), colour=("1", "1", "1", "1"), shape="sphere",
           radius=0.6, direction="outwards", drag=2.0, gravity=0.0,
           material="particles_blend", spin=None, size_expr=None, active=0.05,
           plane="y", offset=("0", "0", "0"), facing="lookat_xyz"):
    """1エフェクト = この1関数。書き方を1つに縛って差分を読めるようにする。

    gravity は符号が反転して linear_acceleration に入る（正で落ち、負で昇る）。
    収束は direction="inwards" だけで表し、速度は正のまま持つ — 速度の符号と
    direction の両方で向きを反転させると、後から読んだとき必ず間違える。
    """
    comps = {
        "minecraft:emitter_lifetime_once": {"active_time": active},
        "minecraft:emitter_rate_instant": {"num_particles": count},
        "minecraft:particle_lifetime_expression": {"max_lifetime": life},
        "minecraft:particle_initial_speed": speed,
        "minecraft:particle_motion_dynamic": {
            "linear_acceleration": [0, -gravity, 0],
            "linear_drag_coefficient": drag,
        },
        "minecraft:particle_appearance_billboard": {
            "size": list(size_expr or size),
            "facing_camera_mode": facing,
            "uv": {"texture_width": ATLAS_W, "texture_height": ATLAS_H,
                   "uv": uv_of(cell), "uv_size": [CELL, CELL]},
        },
        "minecraft:particle_appearance_tinting": {"color": list(colour)},
    }
    if shape == "sphere":
        comps["minecraft:emitter_shape_sphere"] = {
            "offset": list(offset), "radius": radius,
            "direction": direction, "sample_coordinate": True}
    elif shape == "disc":
        comps["minecraft:emitter_shape_disc"] = {
            "plane_normal": plane, "offset": list(offset), "radius": radius,
            "direction": direction, "sample_coordinate": True}
    elif shape == "point":
        comps["minecraft:emitter_shape_point"] = {
            "offset": list(offset), "direction": [0, 1, 0]}
    else:
        raise SystemExit(f"{identifier}: 未知の emitter shape {shape}")
    if spin:
        comps["minecraft:particle_initial_spin"] = {
            "rotation": spin[0], "rotation_rate": spin[1]}
    return {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {
                "identifier": identifier,
                "basic_render_parameters": {"material": material,
                                            "texture": TEXTURE},
            },
            "components": comps,
        },
    }


def C(hexstr, fade=True):
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    a = "1 - v.particle_age / v.particle_lifetime" if fade else "1"
    return (f"{r:.3f}", f"{g:.3f}", f"{b:.3f}", a)


def A(hexstr, peak=1.0):
    """頂点の濃さを落とした着色。薄く残るもの・身体を隠さないものに使う。"""
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return (f"{r:.3f}", f"{g:.3f}", f"{b:.3f}",
            f"{peak} - {peak} * v.particle_age / v.particle_lifetime")


def grow(rate, aspect=1.0):
    """生まれてから開き続ける。層4（広がり）はこれで作る。"""
    return (f"v.particle_age * {rate}", f"v.particle_age * {rate * aspect}")


def shrink(start, rate):
    """縮んで消える。溜め（層1）と萎み（層5）で使う。"""
    return (f"math.max(0.0, {start} - v.particle_age * {rate})",
            f"math.max(0.0, {start} - v.particle_age * {rate})")


def lift(hexstr, t, towards="#FFFFFF"):
    """palette.py の色を持ち上げる。色を打ち直さずに派生色を作るため。"""
    c = mctexture.mix(mctexture.hexc(hexstr), mctexture.hexc(towards), t)
    return "#%02X%02X%02X" % c


def _glow(form_key: str) -> str:
    """形態ごとのアクセント色。palette.py の haki_line が唯一の定義元。"""
    return palette.PALETTES[form_key]["haki_line"]["glow"]


EFFECTS: dict = {}


def add(name, cell, **kw):
    """識別子は namespace を spec から組む。ここで文字列を打たない。"""
    ident = f"{spec.NS}:{name}"
    if ident in EFFECTS:
        raise SystemExit(f"{ident}: 二重定義")
    EFFECTS[ident] = effect(ident, cell, **kw)


def family(base, cell, variants, **shared):
    """形と動きは同じで色だけ違う一族。色替えを安く保つ。"""
    for suffix, colour in variants.items():
        add(f"{base}_{suffix}", cell, colour=colour, **shared)


# ---------------------------------------------------------------------------
#  色 — 形態の色設計 (palette.py) から引く。ここで新しく決めるのは
#  「палette に無いもの」だけ。
# ---------------------------------------------------------------------------
FIRE_HEX = "#F2521E"        # 火拳。肌にも蒸気にも無い色なのでここで持つ
EMBER_HEX = "#FF9640"
DUST_HEX = "#B2A184"        # 土埃。訓練場の地面に合わせた中間色
DUST_DEEP_HEX = "#6E6252"

RUBBER = C(palette.SKIN)
RUBBER_SOFT = A(palette.SKIN, 0.70)
RUBBER_FADE = A(palette.SKIN, 0.55)        # 層5 用。濃さの上限が違う
RUBBER_LIT = A(palette.SKIN_L, 0.85)
STEAM = A(palette.STEAM, 0.50)
STEAM_THIN = A(palette.STEAM, 0.32)
HEAT = C(_glow("gear2"))
HEAT_OMEN = A(_glow("gear2"), 0.75)
HEAT_SOFT = A(_glow("gear2"), 0.70)
FIRE = C(FIRE_HEX)
EMBER = A(EMBER_HEX, 0.85)
EMBER_SOFT = A(EMBER_HEX, 0.55)
INFLATE = C(palette.GEAR3["inflate"]["base"])
INFLATE_SOFT = A(palette.GEAR3["inflate"]["base"], 0.55)
# 覇気は「暗い基本色＋明るい縁」。tint は縁の色で、暗さはスプライトが持つ。
HAKI_RIM = C(lift(palette.HAKI_HI, 0.34))
HAKI_OMEN = A(lift(palette.HAKI_HI, 0.34), 0.78)
HAKI_SOFT = A(lift(palette.HAKI_HI, 0.34), 0.45)
SNAKE_RIM = C(_glow("gear4_snake"))
NIKA = A(palette.G5_WARM, 0.72)
NIKA_LIT = A(palette.G5_WARM, 0.85)
CLOUD = A(palette.G5_CLOUD, 0.55)
CLOUD_THIN = A(palette.G5_CLOUD, 0.42)
BOLT = A(palette.VFX_BOLT["bolt"]["base"], 0.88)
BOLT_OMEN = A(palette.VFX_BOLT["bolt"]["base"], 0.75)
BOLT_EDGE = C(palette.VFX_BOLT["edge"]["base"])
IMPACT = A(palette.G5_WARM, 0.85)
IMPACT_SOFT = A(palette.G5_WARM, 0.70)
DUST = A(DUST_HEX, 0.55)
DUST_HARD = A(DUST_HEX, 0.85)              # 破片。砂埃より濃く見せる
DUST_DEEP = A(DUST_DEEP_HEX, 0.50)
WARN = A(palette.SASH, 0.45)

SPIN_ANY = ("v.particle_random_1 * 360", "0")
SPIN_TUMBLE = ("v.particle_random_1 * 360", "v.particle_random_2 * 360 - 180")

# ===========================================================================
#  層1 予兆 — 「次にどちらへ動くか」だけを伝える。
#  収束する / 遅い / 小さい / 薄い。身体と表情を隠したらこの層の負けなので、
#  大きさは 1.8 ブロック以下、濃さは 0.8 以下に抑える（check_layers が検査）。
# ===========================================================================
add("stretch_coil", "coil", count=1, life=0.40, speed=1.8,
    direction="inwards", size=(0.60, 0.60), colour=RUBBER_SOFT,
    radius=0.55, drag=2.6)
# 溜めは「閉じる輪」。開く輪は層4が使うので、向きだけで役割が分かれる。
add("charge_draw", "ring", count=1, life=0.42, speed=1.4, direction="inwards",
    size_expr=shrink(1.25, 2.6), colour=A(palette.SKIN_L, 0.70), radius=0.55,
    drag=2.4)
add("inflate_puff", "bulge", count=1, life=0.50, speed=0.9,
    size_expr=grow(2.4), colour=INFLATE_SOFT, radius=0.45, drag=2.2)
add("lift_dust", "grit", count=2, life=0.55, speed=1.6, size=(0.34, 0.34),
    colour=DUST, shape="disc", plane="y", radius=0.50, drag=3.0, gravity=-0.6)
add("ignite_coil", "spark", count=2, life=0.45, speed=2.0, direction="inwards",
    size=(0.26, 0.34), colour=HEAT_OMEN, radius=0.55, drag=2.8,
    gravity=-0.8)
# 蒸気は予兆と余韻の両方で出る。同じ粒で両方を賄えるよう、薄く長めに。
add("steam_wisp", "wisp", count=2, life=0.70, speed=1.3, size=(0.50, 0.72),
    colour=STEAM, radius=0.42, drag=2.4, gravity=-1.1)
# 覇気の予兆は腕へ寄る。塊は暗く、縁だけが光る。
add("haki_coat", "haki_orb", count=1, life=0.48, speed=1.6,
    direction="inwards", size=(0.62, 0.62), colour=HAKI_OMEN, radius=0.60,
    drag=2.6)
add("compress", "haki_flake", count=2, life=0.34, speed=2.6,
    direction="inwards", size=(0.34, 0.34), colour=HAKI_OMEN, radius=0.75,
    drag=2.2, spin=SPIN_ANY)
add("nika_pulse", "bloom", count=1, life=0.55, speed=0.8, size_expr=grow(2.2),
    colour=A(palette.G5_WARM, 0.55), radius=0.40, drag=2.0)
add("bolt_gather", "fork", count=2, life=0.36, speed=2.4, direction="inwards",
    size=(0.30, 0.42), colour=BOLT_OMEN, radius=0.80, drag=2.4,
    spin=SPIN_ANY)
# 地面が盛り上がる予兆。これが見えてから打ち上げまで8tickある（避けられる）。
add("ground_bulge", "dome", count=1, life=0.50, speed=0.6, size=(1.10, 0.70),
    colour=DUST, shape="disc", plane="y", radius=0.40, drag=3.0)
# 看板演出の「息を吸う」。静かな段なので、これだけは極端に薄い。
add("heart_thud", "ring", count=1, life=0.60, speed=0.5, size_expr=grow(1.6),
    colour=A(palette.G5_WARM, 0.40), radius=0.35, drag=1.8)

# ===========================================================================
#  層2 軌道 — 始点と終点をはっきり見せ、進む向きに沿わせる。
#  伸びる技は帯、連打は残像、飛ぶ技は尾。寿命は 0.40 秒まで（残ると軌跡が
#  太って、どこを通ったのか読めなくなる）。看板演出だけは別枠で長く取る。
# ===========================================================================
add("fist_trail", "band", count=1, life=0.26, speed=0, shape="point", drag=0,
    size=(1.30, 0.42), colour=RUBBER, facing="direction_x")
add("speed_line", "streak", count=1, life=0.18, speed=0, shape="point",
    drag=0, size=(1.05, 0.11), colour=A(palette.SKIN_L, 0.80),
    facing="direction_x")
add("palm_push", "wedge", count=1, life=0.24, speed=1.2, size=(1.05, 0.85),
    colour=RUBBER_SOFT, radius=0.30, drag=3.0, facing="direction_x")
# 連打は1発を軽く。数で見せるので、1粒あたりは小さく短い。
add("fist_blur", "blur", count=1, life=0.22, speed=2.2, size=(0.72, 0.52),
    colour=RUBBER_SOFT, radius=0.35, drag=4.0)
add("jet_streak", "dart", count=1, life=0.16, speed=0, shape="point", drag=0,
    size=(1.45, 0.30), colour=HEAT, facing="direction_x")
add("jet_blur", "blur", count=1, life=0.16, speed=2.8, size=(0.60, 0.44),
    colour=HEAT_SOFT, radius=0.30, drag=5.0)
add("flame_trail", "flame", count=2, life=0.30, speed=1.6, size=(0.42, 0.70),
    colour=FIRE, radius=0.28, drag=3.2, gravity=-1.4, facing="direction_y")
# 回避の残像。補助技なので、当たる技の軌道より必ず薄い。
add("after_image", "ghost", count=1, life=0.32, speed=0.4, size=(0.80, 1.55),
    colour=A(palette.STEAM, 0.30), radius=0.25, drag=3.0)
add("heavy_trail", "band", count=1, life=0.30, speed=0, shape="point", drag=0,
    size=(2.20, 0.95), colour=INFLATE, facing="direction_x")
add("heavy_arc", "sweep", count=1, life=0.26, speed=0, shape="point", drag=0,
    size=(2.60, 2.60), colour=INFLATE,
    spin=("v.particle_random_1 * 30 - 15", "0"))
add("heavy_push", "wedge", count=1, life=0.28, speed=1.4, size=(1.70, 1.30),
    colour=INFLATE, radius=0.40, drag=3.2, facing="direction_x")
add("haki_trail", "haki_band", count=1, life=0.28, speed=0, shape="point",
    drag=0, size=(1.70, 0.52), colour=HAKI_RIM, facing="direction_x")
# 弾む足取り。上へ抜ける空気なので重力は負（昇る）。
add("bounce_puff", "puff", count=2, life=0.40, speed=2.4, size=(0.52, 0.52),
    colour=RUBBER_SOFT, radius=0.40, drag=3.4, gravity=-1.2)
# 蛇は曲がる。同じ「線」でも、リボンと回転で猿王銃の直線と混ざらない。
add("snake_trail", "serp", count=1, life=0.30, speed=1.0, size=(0.75, 1.05),
    colour=SNAKE_RIM, radius=0.30, drag=3.0,
    spin=("v.particle_random_1 * 360", "40"))
add("bolt_trail", "bolt", count=1, life=0.16, speed=0, shape="point", drag=0,
    size=(0.55, 1.70), colour=BOLT, spin=SPIN_ANY)
add("bolt_fringe", "fork", count=2, life=0.22, speed=3.4, size=(0.30, 0.42),
    colour=BOLT_EDGE, radius=0.40, drag=4.5, spin=SPIN_ANY)
# 足元のゴム化。破線の輪＝弾性、という読み分けをここだけで使う。
add("rubber_wave", "dashring", count=1, life=0.38, speed=1.2,
    size_expr=grow(2.8), colour=RUBBER_SOFT, shape="disc", plane="y",
    radius=0.30, drag=2.0, facing="rotate_y")
add("ground_run", "dome", count=1, life=0.30, speed=0.8, size=(0.95, 0.60),
    colour=DUST, shape="disc", plane="y", radius=0.25, drag=3.0)
# 猿神銃の拳。線に沿って並ぶので、1枚を大きくしすぎると画面が埋まる。
add("giant_fist", "fist", count=1, life=0.34, speed=0, shape="point", drag=0,
    size=(2.00, 2.00), colour=A(palette.SKIN, 0.85),
    spin=("v.particle_random_1 * 10 - 5", "0"))
# 看板演出の雲。4.5秒の見せ場なので、戦闘中の軌道より長く漂わせてよい。
add("cloud_curl", "cloud", count=1, life=0.75, speed=1.1, size=(0.85, 0.70),
    colour=CLOUD, radius=0.50, drag=2.2, gravity=-0.5,
    spin=("v.particle_random_1 * 360", "18"))
add("cloud_orbit", "cloud", count=1, life=0.80, speed=0.6, size=(0.95, 0.75),
    colour=CLOUD_THIN, radius=0.35, drag=1.8, gravity=-0.3,
    spin=("v.particle_random_1 * 360", "22"))

# ===========================================================================
#  層3 接触 — 当たった時だけ出す。短く、強く、1枚で終わる。
#  空振りで出してはいけないので、スクリプト側は命中判定の後で呼ぶこと。
#  重さで形を変える: 軽い=放射 / 重い=十字 / 最も重い=割れを含む輪。
#  どれも 0.24 秒以内・4ブロック以内。画面を白く飛ばさない (企画書 §08)。
# ===========================================================================
add("impact_core", "burst", count=1, life=0.16, speed=0, shape="point",
    drag=0, size=(1.50, 1.50), colour=IMPACT)
add("impact_core_big", "cross", count=1, life=0.20, speed=0, shape="point",
    drag=0, size=(2.40, 2.40), colour=IMPACT)
add("slam_core", "crater", count=1, life=0.22, speed=0, shape="point", drag=0,
    size=(3.20, 3.20), colour=IMPACT)
add("flame_burst", "burst", count=1, life=0.20, speed=0, shape="point",
    drag=0, size=(2.20, 2.20), colour=A(FIRE_HEX, 0.85))
# ニカの発光。暖色白で、芯を作らない。純白の閃光にはしない。
add("nika_flash", "bloom", count=1, life=0.22, speed=0, shape="point", drag=0,
    size=(2.80, 2.80), colour=NIKA)
add("bolt_strike", "bolt", count=1, life=0.14, speed=0, shape="point", drag=0,
    size=(0.70, 1.60), colour=BOLT)
add("rubber_pop", "pop", count=1, life=0.20, speed=3.0, size=(0.55, 0.55),
    colour=RUBBER_LIT, radius=0.30, drag=4.0)
# 看板演出の縁取り。接触ではないが、身体の輪郭を1度だけ強く見せる段。
add("nika_rim", "halo2", count=1, life=0.24, speed=0, shape="point", drag=0,
    size_expr=grow(6.0), colour=NIKA)

# ===========================================================================
#  層4 広がり — 外へ開く。寿命は短い。
#  長く残る輪は地面と相手の足元を覆って、次の一手を読めなくする。だから
#  「開ききる前に消える」くらいで丁度いい。破片だけは落ちきる時間を許す。
# ===========================================================================
add("impact_ring", "ring", count=1, life=0.30, speed=0, shape="point", drag=0,
    size_expr=grow(4.2), colour=IMPACT_SOFT)
add("shock_fan", "shock", count=1, life=0.30, speed=1.6, size_expr=grow(3.6),
    colour=IMPACT_SOFT, radius=0.30, drag=3.0)
add("shock_ring_big", "shock", count=1, life=0.38, speed=1.4,
    size_expr=grow(4.4), colour=IMPACT_SOFT, radius=0.40, drag=3.0)
add("ground_crack", "fissure", count=1, life=0.45, speed=0.6,
    size=(1.20, 1.20), colour=DUST_DEEP, shape="disc", plane="y", radius=0.30,
    drag=3.0, facing="rotate_y", spin=SPIN_ANY)
add("debris", "chunk", count=1, life=0.70, speed=6.5, size=(0.26, 0.26),
    colour=DUST_HARD, radius=0.40, drag=1.0, gravity=8.0,
    spin=SPIN_TUMBLE)
add("ember_fan", "spark", count=2, life=0.38, speed=5.0, size=(0.22, 0.30),
    colour=EMBER, radius=0.30, drag=4.0, gravity=-1.0)
# 風の輪。足元で開くので、地面に寝かせる (rotate_y)。
add("wind_ring", "halo2", count=1, life=0.35, speed=0, shape="point", drag=0,
    size_expr=grow(5.0), colour=CLOUD, facing="rotate_y")
add("star_shard", "glint", count=1, life=0.40, speed=5.5, size=(0.34, 0.34),
    colour=NIKA_LIT, radius=0.35, drag=3.5, spin=SPIN_ANY)

# ===========================================================================
#  層5 余韻 — 消え方の層。
#  ぷつっと消さない（濃さは必ず0へ落とす）、濃くしない、速く動かさない。
#  次の入力の邪魔をしないことが唯一の仕事なので、濃さは 0.60 まで。
# ===========================================================================
add("rubber_snap", "snap", count=1, life=0.50, speed=2.6, size=(0.50, 0.50),
    colour=RUBBER_FADE, radius=0.35, drag=3.4, spin=SPIN_TUMBLE)
add("dust_low", "grit", count=1, life=1.00, speed=1.8, size=(0.62, 0.62),
    colour=DUST, shape="disc", plane="y", radius=0.70, drag=3.0, gravity=0.8)
add("ember_drift", "spark", count=1, life=1.10, speed=1.2, size=(0.18, 0.26),
    colour=EMBER_SOFT, radius=0.60, drag=2.0, gravity=-1.6)
# 萎む。膨張の逆再生に見えるよう、開く輪ではなく縮む綿で返す。
add("deflate_puff", "puff", count=1, life=0.80, speed=1.4,
    size_expr=shrink(0.90, 1.0), colour=INFLATE_SOFT, radius=0.50, drag=2.6)
add("haki_wisp", "haki_flake", count=1, life=0.90, speed=1.0,
    size=(0.30, 0.30), colour=HAKI_SOFT, radius=0.60, drag=2.2, gravity=-0.5,
    spin=SPIN_ANY)
add("cloud_drift", "cloud", count=1, life=1.30, speed=0.9, size=(0.80, 0.62),
    colour=A(palette.G5_CLOUD, 0.45), radius=0.70, drag=2.0, gravity=-0.4)

# ===========================================================================
#  層に属さないもの (spec.all_particles の追加分)
#  変身・待機・警告・解放・照準。戦闘の5層とは別の用途なので節を分ける。
#  常時出し続けるものは emitter_rate_steady を使わず、1回分を薄く作って
#  スクリプト側の再発火に任せる（怪獣8号側でも steady は未使用の経路）。
# ===========================================================================
add("transform_burst", "burst", count=10, life=0.45, speed=6.0,
    size=(0.55, 0.55), colour=NIKA_LIT, radius=0.35, drag=3.6)
add("revert_puff", "vapor", count=8, life=0.55, speed=2.2,
    direction="inwards", size=(0.60, 0.60), colour=STEAM, radius=0.80,
    drag=3.0)
add("steam_idle", "wisp", count=2, life=0.90, speed=0.9, size=(0.36, 0.52),
    colour=STEAM_THIN, radius=0.45, drag=2.4, gravity=-0.9)
add("cloud_idle", "cloud", count=2, life=1.20, speed=0.5, size=(0.55, 0.44),
    colour=A(palette.G5_CLOUD, 0.35), radius=0.60, drag=2.0, gravity=-0.3)
add("haki_idle", "haki_flake", count=2, life=0.80, speed=0.8,
    size=(0.24, 0.24), colour=A(lift(palette.HAKI_HI, 0.34), 0.40),
    radius=0.55, drag=2.4)
# 気力切れの予告。視界を塞ぐと警告にならないので、足元に寝かせた細い輪。
add("low_energy", "ring", count=1, life=0.70, speed=0, shape="disc",
    plane="y", radius=0.45, drag=0, size=(0.70, 0.70), colour=WARN,
    facing="rotate_y")
add("unlock_spark", "glint", count=8, life=0.55, speed=3.6, size=(0.28, 0.28),
    colour=NIKA_LIT, radius=0.40, drag=3.2)
# 照準。指向マークが内へ寄って的を囲む。
add("target_mark", "chevron", count=3, life=0.50, speed=1.2,
    direction="inwards", size=(0.42, 0.42), colour=IMPACT_SOFT, radius=0.90,
    drag=2.0, spin=SPIN_ANY)


# ---------------------------------------------------------------------------
#  検査 — 書いた意図と出力がずれたままビルドが通らないようにする
# ---------------------------------------------------------------------------
def _comps(ident):
    return EFFECTS[ident]["particle_effect"]["components"]


def _lead(expr, default=1.0) -> float:
    """molang の先頭にある定数を取り出す。生まれた瞬間の値になる。"""
    if isinstance(expr, (int, float)):
        return float(expr)
    num = ""
    for ch in str(expr).strip():
        if ch.isdigit() or ch in ".-":
            num += ch
        else:
            break
    try:
        return float(num)
    except ValueError:
        return default


def peak_alpha(ident) -> float:
    return _lead(_comps(ident)["minecraft:particle_appearance_tinting"]
                 ["color"][3], 1.0)


def extent(ident) -> float:
    """生きている間に到達する最大の見かけ大きさ（ブロック）。"""
    c = _comps(ident)
    life = c["minecraft:particle_lifetime_expression"]["max_lifetime"]
    out = 0.0
    for s in c["minecraft:particle_appearance_billboard"]["size"]:
        if isinstance(s, (int, float)):
            out = max(out, float(s))
        elif str(s).startswith("v.particle_age"):
            out = max(out, float(str(s).split("*")[1]) * life)
        else:                                    # shrink(start, rate)
            out = max(out, _lead(str(s).split(",")[1], 0.0))
    return out


def layers_of_fx() -> dict:
    """どのパーティクルがどの層で使われているかを spec から集める。"""
    out: dict = {}
    for t in spec.TECHS:
        for s in t.stages:
            out.setdefault(s["fx"], set()).add(s["layer"])
    for step in spec.SHOWPIECE:
        for s in step["stages"]:
            out.setdefault(s["fx"], set()).add(s["layer"])
    return out


def showpiece_only() -> set:
    """看板演出だけが使うもの。4.5秒の見せ場なので寿命の上限を緩める。"""
    in_tech = {s["fx"] for t in spec.TECHS for s in t.stages}
    in_show = {s["fx"] for step in spec.SHOWPIECE for s in step["stages"]}
    return in_show - in_tech


#  層ごとの約束。数値は企画書 §11 の狙いを、検査できる形に落としたもの。
LAYER_RULE = {
    spec.LAYER_OMEN: dict(life=(0.30, 0.80), alpha=0.80, size=1.80),
    spec.LAYER_TRAIL: dict(life=(0.10, 0.40), alpha=1.00, size=3.00),
    spec.LAYER_IMPACT: dict(life=(0.10, 0.24), alpha=0.90, size=4.00),
    spec.LAYER_SPREAD: dict(life=(0.20, 0.75), alpha=0.90, size=4.00),
    spec.LAYER_ECHO: dict(life=(0.45, 1.40), alpha=0.60, size=2.00),
}


def check_coverage() -> None:
    """spec が呼ぶものを全部作り、余計なものを作っていないことを確かめる。"""
    want = list(spec.all_particles())
    missing = [i for i in want if i not in EFFECTS]
    extra = [i for i in EFFECTS if i not in want]
    if missing or extra:
        raise SystemExit(f"particles: 不足 {missing} / 余分 {extra}")


def check_layers() -> None:
    """層の約束を生成物から読み直して検査する。"""
    layers = layers_of_fx()
    loose = showpiece_only()
    bad = []
    for ident, ls in layers.items():
        primary = min(ls)                     # 兼用は最初に出る層の約束で見る
        rule = LAYER_RULE[primary]
        life = _comps(ident)["minecraft:particle_lifetime_expression"][
            "max_lifetime"]
        lo, hi = rule["life"]
        if ident in loose:
            hi = max(hi, 1.00)
        if not lo <= life <= hi:
            bad.append(f"{ident}: 層{primary} の寿命 {lo}..{hi} に対し {life}")
        if peak_alpha(ident) > rule["alpha"] + 1e-6:
            bad.append(f"{ident}: 層{primary} の濃さ上限 {rule['alpha']} 超過")
        if extent(ident) > rule["size"] + 1e-6:
            bad.append(f"{ident}: 層{primary} の大きさ上限 {rule['size']} 超過")
        c = _comps(ident)
        speed = c["minecraft:particle_initial_speed"]
        if primary == spec.LAYER_OMEN and speed > 2.8:
            bad.append(f"{ident}: 予兆が速すぎる（読む時間が要る）")
        if primary == spec.LAYER_IMPACT and \
                c["minecraft:emitter_rate_instant"]["num_particles"] > 4:
            bad.append(f"{ident}: 接触は1枚で終わらせる（粒を撒かない）")
        if primary == spec.LAYER_SPREAD:
            grows = any(str(v).startswith("v.particle_age") for v in
                        c["minecraft:particle_appearance_billboard"]["size"])
            if not grows and speed <= 0:
                bad.append(f"{ident}: 広がりが外へ開いていない")
        if primary == spec.LAYER_ECHO and speed > 3.0:
            bad.append(f"{ident}: 余韻が速すぎる")
    if bad:
        raise SystemExit("layer: " + "\n       ".join(bad))


def peak_load(tech, quality: str) -> int:
    """emission rate x lifetime。技1本の同時表示数の設計時見積り。"""
    q = spec.QUALITY[quality]
    events = []
    for s in tech.stages:
        if s["layer"] not in q["layers"]:
            continue
        c = _comps(s["fx"])
        born = s.get("n", 1) * c["minecraft:emitter_rate_instant"][
            "num_particles"]
        born = int(round(born * q["density"]))
        life = c["minecraft:particle_lifetime_expression"]["max_lifetime"]
        events.append((s["t"], born))
        events.append((s["t"] + life * 20.0, -born))
    live = peak = 0
    for _, delta in sorted(events):
        live += delta
        peak = max(peak, live)
    return peak


def check_budget(quality: str = "standard"):
    worst, worst_n = None, 0
    for t in spec.TECHS:
        n = peak_load(t, quality)
        if n > worst_n:
            worst, worst_n = t, n
    if worst_n > SOLO_BUDGET:
        raise SystemExit(f"budget: {worst.slug} が {worst_n} 粒 "
                         f"(上限 {SOLO_BUDGET})")
    return worst, worst_n


# ---------------------------------------------------------------------------
def main() -> None:
    print("particles:")
    build_atlas()
    check_coverage()
    check_layers()
    worst, worst_n = check_budget()

    os.makedirs(PART_DIR, exist_ok=True)
    keep = {i.split(":")[1] + ".particle.json" for i in EFFECTS}
    for stale in os.listdir(PART_DIR):
        if stale.endswith(".particle.json") and stale not in keep:
            os.remove(os.path.join(PART_DIR, stale))
    for ident, doc in EFFECTS.items():
        path = os.path.join(PART_DIR, ident.split(":")[1] + ".particle.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    layers = layers_of_fx()
    tally = {k: 0 for k in spec.LAYER_JA}
    for ls in layers.values():
        tally[min(ls)] += 1
    per_layer = " / ".join(f"{spec.LAYER_JA[k]}{tally[k]}"
                           for k in sorted(tally))
    print(f"  {per_layer} / 層外{len(EFFECTS) - len(layers)}")
    print(f"  標準品質の最大同時表示 {worst_n} 粒 ({worst.ja}) "
          f"— 1技あたり上限 {SOLO_BUDGET}")
    print(f"  {len(EFFECTS)} particle effects, {len(CELLS)} sprites")


if __name__ == "__main__":
    main()
