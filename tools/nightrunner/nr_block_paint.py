# -*- coding: utf-8 -*-
"""NIGHT RUNNER — カスタムブロック用の塗りの部品（gen_nr_blocks 専用）。

nr_paint（写実寄りの素材ペインタ）の上に、ブロックで要る物を足す:

* `STYLES` … カタログの素材キー（`nr_spec_catalog.SURFACES`）→ nr_paint のスタイル。
  ブロックごとの色違いは `style_for("steel_painted", base=...)` で作る。
* **独自のデカール**（名前は `nrb_` で始まる）を `nr_paint.DECALS` に登録する（このプロセスの中だけ。
  nr_paint.py 自体は書き換えない）。ブロックに要る模様: スプレーの落書き（手書きの線の字体）、釘、レンガ、
  金網・有刺鉄線（アルファで抜く）、波板、ルーバー、ファンの格子、リベット、ラベルと警告の記号、
  道路標識、縞鋼板、LED の粒、コイルの巻き線、有孔ボード、剥げたペンキ、引っかき傷、尋ね人のビラ、
  床の砂利（アルファ）、血だまり・油膜（半透明）、タイヤの側面、炎の舌（アルファ）、鋼の歯（アルファ）…
* **ワールド座標のデカール**: パラメータ `O`, `A`, `B`（面の左上の角と u・v 方向のベクトル、ブロック座標）を
  渡すと、texel をブロックの空間の点に直して模様を引く。隣り合う板・袋をまたいで落書きや釘の列が続く。
  面の向きは nr_preview と同じ実機の対応（east = min-X、u は -Z へ）。

ブロックは画素単位で光れない（rendering.md §8）。発光の素材（glow）は gen_nr_blocks がアルファを 255 に
戻して「明るい色」として使う（光は light_emission で出す）。
"""
from __future__ import annotations

import math
import os
import sys
import zlib
from typing import Dict, List, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import nr_paint as NP  # noqa: E402

f32 = np.float32
_rgb = NP._rgb
_ss = NP._ss
_mix = NP._mix

# ---------------------------------------------------------------------------
#  素材キー → nr_paint のスタイル
# ---------------------------------------------------------------------------
STYLES: Dict[str, dict] = {
    # 金属
    "steel_clean": NP.metal_style(base="#c4cace", dirt=0.15, wear=0.3, scratches=0.7),
    "steel_worn": NP.metal_style(base="#8e9294", dirt=0.4, wear=0.55, scratches=0.6),
    "steel_rusty": NP.style("rust", amount=0.72, metal="#77736e", dirt=0.3),
    "steel_dark": NP.metal_style(base="#3a3c40", dirt=0.3, wear=0.6, scratches=0.5),
    "steel_painted": NP.painted_metal_style("#6e766e", dirt=0.35, wear=0.45, rust=0.5),
    "iron_cast": NP.style("rust", amount=0.32, metal="#4a4a4c", dirt=0.35),
    "chrome": NP.style("chrome", dirt=0.25),
    "aluminium": NP.metal_style(base="#aeb2b6", dirt=0.35, wear=0.2, scratches=0.4),
    "brass": NP.metal_style(base="#a8843c", dirt=0.45, wear=0.4, scratches=0.3),
    "copper_wire": NP.metal_style(base="#b4643a", dirt=0.2, wear=0.3, scratches=0.15),
    "rebar": NP.style("rust", amount=0.95, dirt=0.45),
    "chainlink": NP.metal_style(base="#9aa0a0", dirt=0.25, wear=0.3, scratches=0.2),
    # 木
    "wood_old": NP.style("wood", base="#7a5c40", grain=1.3, wear=0.6, dirt=0.45),
    "wood_dark": NP.style("wood", base="#4e382a", grain=1.1, wear=0.3, dirt=0.35),
    "wood_raw": NP.style("wood", base="#b48e60", grain=1.4, wear=0.12, dirt=0.25),
    "plywood": NP.style("wood", base="#b49668", grain=0.6, wear=0.4, dirt=0.4),
    "wood_painted": NP.style("wood", base="#6e563e", grain=1.2, wear=0.4, dirt=0.3, _paint="#d8d4c8"),
    # 樹脂・ゴム・布
    "rubber_black": NP.style("rubber", base="#1e1e20", wear=0.45, dirt=0.35),
    "tire": NP.style("tire", base="#1c1c1e", dirt=0.35, axis="y"),
    "plastic_black": NP.style("plastic", base="#28282c", wear=0.3, dirt=0.35),
    "plastic_orange": NP.style("plastic", base="#e06a1c", wear=0.45, dirt=0.5),
    "plastic_yellow": NP.style("plastic", base="#deb428", wear=0.35, dirt=0.45),
    "plastic_white": NP.style("plastic", base="#d8d6cc", wear=0.3, dirt=0.5),
    "plastic_red": NP.style("plastic", base="#a81e1c", wear=0.35, dirt=0.4),
    "plastic_blue": NP.style("plastic", base="#24508c", wear=0.3, dirt=0.4),
    "tape_grey": NP.style("cloth", base="#98988f", pattern="plain", dirt=0.3, seams=False, folds=0.4),
    "tape_black": NP.style("plastic", base="#1a1a1c", wear=0.2, wet=0.3),
    "cloth_rag": NP.cloth_style("#8a7a62", dirt=0.65, blood=0.25, torn=0.25, seams=False),
    "cloth_red": NP.cloth_style("#86201e", dirt=0.45, blood=0.0, torn=0.3, seams=False),
    "leather_brown": NP.leather_style("#5e3c26"),
    "paracord": NP.cloth_style("#5c623e", pattern="stripes", alt="#3e4228", period=0.35, seams=False),
    "rope": NP.cloth_style("#9c8458", pattern="stripes", alt="#6e5a38", period=0.4, dirt=0.45, seams=False),
    "burlap": NP.cloth_style("#a6926a", pattern="check", alt="#8a7652", period=0.3, dirt=0.55, folds=1.4,
                             seams=False, wear=0.4),
    "trash_bag": NP.style("plastic", base="#17171c", wear=0.15, wet=0.55, dirt=0.15),
    "tarp_blue": NP.style("plastic", base="#24528e", wear=0.4, dirt=0.4),
    "cardboard": NP.style("paper", base="#a88050", lines=False, dirt=0.45),
    # 石・道路
    "concrete": NP.style("concrete", base="#96968e", cracks=0.55, dirt=0.4),
    "concrete_dark": NP.style("concrete", base="#5e5e5a", cracks=0.7, dirt=0.5),
    "asphalt": NP.style("asphalt", base="#3a3a3e", cracks=0.5),
    "brick_red": NP.style("concrete", base="#8a4232", cracks=0.15, dirt=0.25),
    "mortar": NP.style("concrete", base="#a8a498", cracks=0.2, dirt=0.4),
    # ガラス・灯り
    "glass_clear": NP.style("glass", base="#9ec0cc", dirt=0.4),
    "glass_broken": NP.style("glass", base="#8eb0bc", crack=0.9, dirt=0.4),
    "glass_tinted": NP.style("glass", base="#343e46", dirt=0.3),
    "emissive_white": NP.style("glow", base="#fff4d8"),
    "emissive_amber": NP.style("glow", base="#ffa838"),
    "emissive_red": NP.style("glow", base="#ff3020"),
    "emissive_blue": NP.style("glow", base="#3c84ff"),
    "emissive_uv": NP.style("glow", base="#b060ff"),
    "emissive_green": NP.style("glow", base="#5aff96"),
    # 塗装
    "paint_white": NP.painted_metal_style("#d4d4cc", dirt=0.4, wear=0.35, rust=0.4),
    "paint_black": NP.painted_metal_style("#202226", dirt=0.3, wear=0.35, rust=0.3),
    "paint_red": NP.painted_metal_style("#962220", dirt=0.35, wear=0.4, rust=0.4),
    "paint_blue": NP.painted_metal_style("#2c4876", dirt=0.35, wear=0.4, rust=0.4),
    "paint_yellow": NP.painted_metal_style("#d8aa24", dirt=0.4, wear=0.45, rust=0.5),
    "paint_olive": NP.painted_metal_style("#4e5638", dirt=0.4, wear=0.45, rust=0.35),
    "paint_green": NP.painted_metal_style("#2e5236", dirt=0.4, wear=0.45, rust=0.45),
    "paint_orange": NP.painted_metal_style("#c45c22", dirt=0.4, wear=0.4, rust=0.4),
    "paint_burnt": NP.style("char", base="#2c2624"),
    "decal_stripe": NP.painted_metal_style("#e4dac0", dirt=0.35, wear=0.3, rust=0.2),
    # 体・ゴア
    "blood_wet": NP.style("blood"),
    "blood_dry": NP.style("blood_dry"),
    "gore_meat": NP.style("gore_wet"),
    "flesh": NP.style("flesh", fat=0.15),
    "bone": NP.style("bone", age=0.6, blood=0.25, dirt=0.3),
    "mutated": NP.style("fungus", base="#6e8a42", alt="#a2b870"),
    "fungus_uv": NP.style("fungus", base="#7a4cc0", alt="#cfa8ff", glow_spots=0.5, glow_colour="#d090ff"),
    "fuel": NP.style("plastic", base="#221c16", wear=0.0, wet=0.95, dirt=0.0),
    "paper": NP.style("paper", base="#d4ccb2"),
    "ash": NP.style("char", base="#3a3634"),
    "char_hot": NP.style("char", base="#2a2220", embers=0.8),
}


def style_for(surface: str, **over) -> dict:
    """素材キーのスタイル（上書き付きの写し）。知らないキーは KeyError。"""
    if surface not in STYLES:
        raise KeyError(f"未知の素材 {surface}（{sorted(STYLES)}）")
    d = dict(STYLES[surface])
    d.update(over)
    return d


def _seed(*parts) -> int:
    return zlib.crc32(":".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


# ---------------------------------------------------------------------------
#  ワールド座標の補助
# ---------------------------------------------------------------------------
def face_frame(origin, size, face):
    """面の左上の角 O と u・v 方向のベクトル A・B（ブロック座標、実機の向き）。

    nr_preview の表と同じ: north u→+X / south u→-X / east（min-X）u→-Z / west（max-X）u→+Z /
    up u→+X, v→-Z / down u→+X, v→+Z。側面の v は下向き（-Y）。
    """
    ax, ay, az = (float(v) for v in origin)
    sx, sy, sz = (float(v) for v in size)
    bx, by, bz = ax + sx, ay + sy, az + sz
    if face == "north":
        return (ax, by, az), (sx, 0, 0), (0, -sy, 0)
    if face == "south":
        return (bx, by, bz), (-sx, 0, 0), (0, -sy, 0)
    if face == "east":
        return (ax, by, bz), (0, 0, -sz), (0, -sy, 0)
    if face == "west":
        return (bx, by, az), (0, 0, sz), (0, -sy, 0)
    if face == "up":
        return (ax, by, bz), (sx, 0, 0), (0, 0, -sz)
    return (ax, ay, az), (sx, 0, 0), (0, 0, sz)


FACE_NORMAL = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (-1, 0, 0), "west": (1, 0, 0),
               "up": (0, 1, 0), "down": (0, -1, 0)}


def _world(fc, d) -> np.ndarray:
    O = np.asarray(d["O"], f32)
    A = np.asarray(d["A"], f32)
    B = np.asarray(d["B"], f32)
    return O + A * fc.u[..., None] + B * fc.v[..., None]


def _flat(d, P, pts):
    """面の法線 N の成分を落とす（面と少し前後にずれた線・点も面の上で測る）。"""
    N = d.get("N")
    if N is None:
        return P, [np.asarray(p, f32) for p in pts]
    n = np.asarray(N, f32)
    P2 = P - (P @ n)[..., None] * n
    return P2, [np.asarray(p, f32) - float(np.asarray(p, f32) @ n) * n for p in pts]


def _seg_dist(P, a, b):
    a = np.asarray(a, f32)
    b = np.asarray(b, f32)
    ab = b - a
    L2 = float(ab @ ab)
    if L2 < 1e-12:
        return np.linalg.norm(P - a, axis=-1)
    t = np.clip(((P - a) @ ab) / f32(L2), 0, 1)
    Q = a + t[..., None] * ab
    return np.linalg.norm(P - Q, axis=-1)


def _poly_mask(x, y, poly) -> np.ndarray:
    """点 (x, y)（配列）が多角形の内側か（偶奇則）。"""
    inside = np.zeros(x.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xs = (x2 - x1) * (y - y1) / ((y2 - y1) if y2 != y1 else 1e-9) + x1
        inside ^= cond & (x < xs)
    return inside


def _soft_poly(fc, poly_uv) -> np.ndarray:
    """面の正規化座標の多角形を 1 texel ぼかしたマスク（2x2 の超標本）。"""
    acc = np.zeros((fc.h, fc.w), f32)
    for ox in (-0.25, 0.25):
        for oy in (-0.25, 0.25):
            acc += _poly_mask((fc.px + ox) / fc.w, (fc.py + oy) / fc.h, poly_uv)
    return acc / 4.0


def _cut(fc, keep_mask):
    """keep_mask が偽の texel を透明（RGBA 0）にする。"""
    k = np.asarray(keep_mask, bool)
    fc.alpha[~k] = 0
    fc.rgb[~k] = 0
    fc.glow[~k] = False


def _mulk(fc, mask, k):
    """texel ごとの倍率 k（(h,w) か スカラー か (3,)）を mask の所に掛ける。"""
    m = np.clip(np.asarray(mask, f32), 0, 1)
    k = np.asarray(k, f32)
    if k.ndim == 2:
        k = k[..., None]
    fc.rgb[...] = fc.rgb * (1.0 + (k - 1.0) * m[..., None])


# ---------------------------------------------------------------------------
#  手書きの線の字体（スプレーの落書き用）。字は幅 2・高さ 4、y は下向き
# ---------------------------------------------------------------------------
_SG = {
    "A": [[(0, 4), (1, 0), (2, 4)], [(0.45, 2.5), (1.55, 2.5)]],
    "B": [[(0, 4), (0, 0), (1.4, 0), (1.9, 0.5), (1.9, 1.5), (1.4, 2), (0, 2)],
          [(1.4, 2), (2, 2.5), (2, 3.5), (1.5, 4), (0, 4)]],
    "C": [[(2, 0.6), (1.5, 0), (0.5, 0), (0, 0.6), (0, 3.4), (0.5, 4), (1.5, 4), (2, 3.4)]],
    "D": [[(0, 0), (0, 4), (1.2, 4), (2, 3.1), (2, 0.9), (1.2, 0), (0, 0)]],
    "E": [[(2, 0), (0, 0), (0, 4), (2, 4)], [(0, 2), (1.5, 2)]],
    "F": [[(2, 0), (0, 0), (0, 4)], [(0, 2), (1.5, 2)]],
    "G": [[(2, 0.6), (1.5, 0), (0.5, 0), (0, 0.6), (0, 3.4), (0.5, 4), (1.5, 4), (2, 3.4), (2, 2.2), (1.1, 2.2)]],
    "H": [[(0, 0), (0, 4)], [(2, 0), (2, 4)], [(0, 2), (2, 2)]],
    "I": [[(1, 0), (1, 4)], [(0.3, 0), (1.7, 0)], [(0.3, 4), (1.7, 4)]],
    "J": [[(2, 0), (2, 3.3), (1.4, 4), (0.5, 4), (0, 3.3)]],
    "K": [[(0, 0), (0, 4)], [(2, 0), (0, 2.3)], [(0.7, 1.6), (2, 4)]],
    "L": [[(0, 0), (0, 4), (2, 4)]],
    "M": [[(0, 4), (0, 0), (1, 2.2), (2, 0), (2, 4)]],
    "N": [[(0, 4), (0, 0), (2, 4), (2, 0)]],
    "O": [[(0.5, 0), (1.5, 0), (2, 0.6), (2, 3.4), (1.5, 4), (0.5, 4), (0, 3.4), (0, 0.6), (0.5, 0)]],
    "P": [[(0, 4), (0, 0), (1.5, 0), (2, 0.5), (2, 1.5), (1.5, 2), (0, 2)]],
    "R": [[(0, 4), (0, 0), (1.5, 0), (2, 0.5), (2, 1.5), (1.5, 2), (0, 2)], [(1, 2), (2, 4)]],
    "S": [[(2, 0.6), (1.5, 0), (0.5, 0), (0, 0.6), (0, 1.5), (0.5, 2), (1.5, 2), (2, 2.5), (2, 3.4),
           (1.5, 4), (0.5, 4), (0, 3.4)]],
    "T": [[(0, 0), (2, 0)], [(1, 0), (1, 4)]],
    "U": [[(0, 0), (0, 3.4), (0.5, 4), (1.5, 4), (2, 3.4), (2, 0)]],
    "V": [[(0, 0), (1, 4), (2, 0)]],
    "W": [[(0, 0), (0.5, 4), (1, 2), (1.5, 4), (2, 0)]],
    "X": [[(0, 0), (2, 4)], [(2, 0), (0, 4)]],
    "Y": [[(0, 0), (1, 2), (2, 0)], [(1, 2), (1, 4)]],
    "Z": [[(0, 0), (2, 0), (0, 4), (2, 4)]],
    "0": [[(0.5, 0), (1.5, 0), (2, 0.6), (2, 3.4), (1.5, 4), (0.5, 4), (0, 3.4), (0, 0.6), (0.5, 0)]],
    "1": [[(0.4, 0.8), (1.1, 0), (1.1, 4)]],
    "2": [[(0, 0.7), (0.6, 0), (1.5, 0), (2, 0.7), (2, 1.5), (0, 4), (2, 4)]],
    "3": [[(0, 0.4), (0.5, 0), (1.5, 0), (2, 0.6), (2, 1.4), (1.3, 2), (2, 2.6), (2, 3.4), (1.5, 4), (0.5, 4),
           (0, 3.6)], [(0.6, 2), (1.3, 2)]],
    "!": [[(1, 0), (1, 2.7)], [(1, 3.5), (1, 4)]],
    "'": [[(1, 0), (0.9, 1.0)]],
    "-": [[(0.3, 2), (1.7, 2)]],
    ">": [[(-0.6, 2), (2.2, 2)], [(1.2, 0.9), (2.2, 2), (1.2, 3.1)]],
    "<": [[(2.6, 2), (-0.2, 2)], [(0.8, 0.9), (-0.2, 2), (0.8, 3.1)]],
    "^": [[(1, 4), (1, 0)], [(0, 1.1), (1, 0), (2, 1.1)]],
    "X_": [[(0, 0), (2, 4)], [(2, 0), (0, 4)]],
}


def text_strokes(text, origin, right, down, height, slant=0.18, spacing=0.55, jitter=0.12, seed=0):
    """文字列を 3D の折れ線の束に。origin = 1 文字目の左上、right / down = 字の右・下の単位ベクトル。"""
    o = np.asarray(origin, float)
    r = np.asarray(right, float)
    dn = np.asarray(down, float)
    sc = height / 4.0
    rng = np.random.default_rng(seed & 0xFFFFFFFF)
    out = []
    cur = 0.0
    for ch in str(text).upper():
        if ch == " ":
            cur += 1.6
            continue
        g = _SG.get(ch)
        if g is None:
            cur += 2.0 + spacing
            continue
        lift = rng.normal(0, 0.18)
        for line in g:
            pts = []
            for gx, gy in line:
                jx, jy = rng.normal(0, jitter, 2)
                x = (cur + gx + slant * (4 - gy) + jx) * sc
                y = (gy + jy + lift) * sc
                pts.append(tuple(o + r * x + dn * y))
            out.append(pts)
        cur += 2.0 + spacing + rng.normal(0, 0.12)
    return out


def text_width(text, height, spacing=0.55):
    n = 0.0
    for ch in str(text).upper():
        n += 1.6 if ch == " " else 2.0 + spacing
    return n * height / 4.0


# ---------------------------------------------------------------------------
#  デカール（fc は nr_paint._Face。d はパラメータの辞書）
# ---------------------------------------------------------------------------
def d_spray(fc, d):
    """スプレー（ワールド座標の折れ線）。colour, width（単位）, drip, cover, overspray, chalk。"""
    P = _world(fc, d)
    col = _rgb(d.get("colour", (190, 20, 18)))
    width = float(d.get("width", 0.7))
    dist = np.full(P.shape[:2], 1e9, f32)
    P0 = P
    for line in d.get("strokes", []):
        P, pts = _flat(d, P0, line)
        for a, b in zip(pts[:-1], pts[1:]):
            dist = np.minimum(dist, _seg_dist(P, a, b))
    if not np.isfinite(dist).any() or dist.min() > width * 3:
        return
    jit = (fc.noise(1.3, fc.seed + 1, 2) - 0.5) * width * 0.55
    dd = dist + jit
    core = np.clip((width * 0.5 - dd) * fc.s + 0.5, 0, 1)
    if d.get("chalk"):
        streak = fc.grain(fc.seed + 7) > 0.38
        fc.paint(core * streak, col * (0.85 + 0.2 * fc.grain(fc.seed + 8))[..., None])
        return
    halo = np.exp(-(dd / (width * 1.15)) ** 2) * (1 - core) * float(d.get("overspray", 0.3))
    fc.paint(halo * (fc.grain(fc.seed + 3) > 0.45), col * 0.9, 0.8)
    cover = float(d.get("cover", 0.9))
    hit = (fc.grain(fc.seed + 4) < cover).astype(f32)
    shade = (0.86 + 0.2 * fc.grain(fc.seed + 5))[..., None]
    fc.paint(core * np.maximum(hit, 0.6), col * shade)
    drip = float(d.get("drip", 0.0))
    if drip > 0 and fc.side:
        fc.drips_from((core > 0.5).astype(f32), drip, fc.seed + 6, col=col * 0.92)


def d_nails(fc, d):
    """釘・ボルトの頭（ワールド座標の点 pts）。r 半径（単位）、kind nail|bolt|rivet、rust 錆の輪。"""
    P = _world(fc, d)
    r = float(d.get("r", 0.42))
    kind = d.get("kind", "nail")
    rust = float(d.get("rust", 0.7))
    P, cs = _flat(d, P, d.get("pts", []))
    for i, c in enumerate(cs):
        dist = np.linalg.norm(P - c, axis=-1)
        if dist.min() > r * 4:
            continue
        rel = (P - c)
        # 面の中での右上方向（光の向き）: u と -v
        A = np.asarray(d["A"], f32)
        B = np.asarray(d["B"], f32)
        ua = A / max(1e-6, float(np.linalg.norm(A)))
        vb = B / max(1e-6, float(np.linalg.norm(B)))
        lx = rel @ ua
        ly = rel @ vb
        if rust > 0:
            halo = np.clip(1 - dist / (r * 2.6), 0, 1) * (fc.noise(2.0, fc.seed + i, 2) > 0.35)
            fc.paint(halo, (92, 46, 22), 0.45 * rust)
            if fc.side:
                fc.drips_from((dist < r * 1.4).astype(f32), 0.4 * rust, fc.seed + 30 + i, col=(96, 50, 26))
        head = np.clip((r - dist) * fc.s + 0.5, 0, 1)
        if kind == "bolt":
            hexm = np.maximum(np.abs(lx), np.abs(lx) * 0.5 + np.abs(ly) * 0.866) < r
            head = hexm.astype(f32)
        base = _rgb(d.get("colour", (70, 66, 62)))
        lit = np.clip(1.0 - (lx - ly) / max(r, 1e-3) * 0.45, 0.45, 1.5)
        fc.paint(head, base * lit[..., None])
        rim = np.clip((r - np.abs(dist - r * 0.8)) * fc.s - 0.2, 0, 1) * head
        fc.mul(rim * (lx + ly > 0), 0.7)


def d_brick(fc, d):
    """レンガ積み（ワールド座標）。h 段の高さ、L レンガの長さ、m 目地の幅（単位）。"""
    P = _world(fc, d)
    n = FACE_NORMAL[fc.face]
    if n[1] != 0:
        x, y = P[..., 0], P[..., 2]
    elif n[0] != 0:
        x, y = P[..., 2], P[..., 1]
    else:
        x, y = P[..., 0], P[..., 1]
    h = float(d.get("h", 1.3))
    L = float(d.get("L", 2.6))
    m = float(d.get("m", 0.22))
    row = np.floor(y / h)
    xo = x + (row % 2) * L * 0.5
    col_ = np.floor(xo / L)
    fx = xo - col_ * L
    fy = y - row * h
    mort = (fx < m) | (fy < m)
    hsh = NP.hash2i(col_.astype(np.int64).astype(np.uint32), row.astype(np.int64).astype(np.uint32),
                    fc.seed + 11)
    rnd = NP._u01(NP._fin(hsh))
    base = _rgb(d.get("colour", (138, 66, 50)))
    tint = _ramp_np(rnd, [(0.0, base * 0.72), (0.5, base), (0.85, base * 1.18), (1.0, (116, 84, 70))])
    tex = 0.88 + 0.18 * fc.grain(fc.seed + 12) + (fc.noise(1.6, fc.seed + 13, 2) - 0.5) * 0.25
    bcol = tint * tex[..., None]
    # 目地の上の縁は明るく、下の縁は暗く（立体）
    bcol = bcol * np.where((fy > h - m * 1.8)[..., None], 0.82, 1.0)
    bcol = bcol * np.where((fy < m * 2.0)[..., None] & ~mort[..., None], 1.1, 1.0)
    mcol = _rgb(d.get("mortar", (150, 144, 132))) * (0.85 + 0.2 * fc.grain(fc.seed + 14))[..., None]
    out = np.where(mort[..., None], mcol, bcol)
    chip = (fc.noise(1.1, fc.seed + 15, 3) > 0.7) & ~mort
    out = np.where(chip[..., None], out * 0.75, out)
    amt = float(d.get("amount", 1.0))
    fc.rgb[...] = fc.rgb + (out - fc.rgb) * f32(amt)


def _ramp_np(t, stops):
    xs = [float(s[0]) for s in stops]
    cols = np.array([_rgb(s[1]) for s in stops], f32)
    out = np.empty(t.shape + (3,), f32)
    for ch in range(3):
        out[..., ch] = np.interp(t, xs, cols[:, ch])
    return out


def d_chainlink(fc, d):
    """菱形の金網（面のローカル座標、アルファで抜く）。pitch, wire（単位）、hole=(cu,cv,ru,rv)。"""
    x = fc.px / fc.s
    y = fc.py / fc.s
    p = float(d.get("pitch", 1.5))
    w = float(d.get("wire", 0.32))
    a = (x + y) / p
    b = (x - y) / p
    da = np.abs(a - np.round(a)) * p * 0.7071
    db = np.abs(b - np.round(b)) * p * 0.7071
    wa = da < w * 0.5
    wb = db < w * 0.5
    wire = wa | wb
    # 撚り（螺旋に巻いた線の明暗）
    sa = 0.75 + 0.45 * np.abs(np.sin((b) * math.pi * 2.0))
    sb = 0.75 + 0.45 * np.abs(np.sin((a) * math.pi * 2.0))
    lit = np.where(wa & ~wb, sa, np.where(wb & ~wa, sb, 1.15))
    fc.rgb[...] = fc.rgb * lit[..., None]
    keep = wire
    hole = d.get("hole")
    if hole:
        cu, cv, ru, rv = hole
        e = ((fc.u - cu) / ru) ** 2 + ((fc.v - cv) / rv) ** 2
        rag = (fc.noise(2.0, fc.seed + 3, 2) - 0.5) * 0.6
        keep = keep & (e + rag > 1.0)
    edge = d.get("edge_rows", 0)
    if edge:
        keep = keep | (fc.py < edge * fc.s) | (fc.py > fc.h - edge * fc.s)
    _cut(fc, keep)


def d_clear(fc, d):
    """面を丸ごと透明に。"""
    _cut(fc, np.zeros((fc.h, fc.w), bool))


def d_cut_poly(fc, d):
    """面の正規化座標の多角形の外（invert なら内）を抜く。"""
    m = _soft_poly(fc, d["poly"]) > 0.5
    if d.get("invert"):
        m = ~m
    _cut(fc, m)


def d_corrugate(fc, d):
    """波板の陰影（u 方向に period 単位で繰り返す）。"""
    q = fc.px / fc.s / float(d.get("period", 2.0))
    if d.get("axis", "u") == "v":
        q = fc.py / fc.s / float(d.get("period", 2.0))
    s = np.sin(q * 2 * math.pi)
    c = np.cos(q * 2 * math.pi)
    k = 1.0 + 0.22 * s * float(d.get("depth", 1.0)) + 0.18 * _ss(0.85, 1.0, c)
    _mulk(fc, np.ones_like(k), k)


def d_slits(fc, d):
    """ルーバー（横長のスリットの列）。box=(u0,v0,u1,v1), rows, gap。"""
    u0, v0, u1, v1 = d.get("box", (0.1, 0.15, 0.9, 0.85))
    rows = int(d.get("rows", 6))
    inside = (fc.u > u0) & (fc.u < u1) & (fc.v > v0) & (fc.v < v1)
    t = (fc.v - v0) / max(1e-6, (v1 - v0)) * rows
    fr = t - np.floor(t)
    dark = inside & (fr < 0.45)
    hi = inside & (fr >= 0.45) & (fr < 0.6)
    fc.paint(dark, (22, 22, 24), 0.9)
    fc.mul(hi, 1.25)


def d_grille(fc, d):
    """丸いファンの格子と奥の羽根。at, r（面の短い辺に対する割合）、rings, blades。"""
    cu, cv = d.get("at", (0.5, 0.5))
    rr = float(d.get("r", 0.42)) * min(fc.w, fc.h)
    x = fc.px - cu * fc.w
    y = fc.py - cv * fc.h
    r = np.sqrt(x * x + y * y)
    ang = np.arctan2(y, x)
    inside = r < rr
    # 奥（暗い）と羽根
    blades = int(d.get("blades", 3))
    bl = np.cos((ang + r / max(rr, 1) * 1.2) * blades) > 0.35
    deep = np.where(bl & (r > rr * 0.18), 52.0, 18.0)
    fc.paint(inside, np.stack([deep, deep, deep * 1.05], -1))
    hub = r < rr * 0.18
    fc.paint(hub, (70, 72, 76))
    # 同心円の針金と十字
    rings = int(d.get("rings", 6))
    ringm = inside & (np.abs((r / max(rr, 1) * rings) - np.round(r / max(rr, 1) * rings)) * rr / rings < 0.55)
    spoke = inside & ((np.abs(x) < 0.6) | (np.abs(y) < 0.6))
    wire_col = _rgb(d.get("colour", (150, 152, 150)))
    fc.paint(ringm | spoke, wire_col * (0.8 + 0.3 * fc.grain(fc.seed + 1))[..., None])
    rim = (r >= rr) & (r < rr + 1.2)
    fc.paint(rim, wire_col * 0.6)


def d_rivets(fc, d):
    """面の縁に沿ったリベットの列（面のローカル）。step（単位）, inset（単位）, edges='tblr'。"""
    step = float(d.get("step", 2.0)) * fc.s
    ins = float(d.get("inset", 0.6)) * fc.s
    r = max(0.6, float(d.get("r", 0.3)) * fc.s)
    edges = d.get("edges", "tblr")
    pts = []
    if "t" in edges or "b" in edges:
        n = max(1, int((fc.w - 2 * ins) / step) + 1)
        xs = np.linspace(ins, fc.w - ins, n)
        if "t" in edges:
            pts += [(x, ins) for x in xs]
        if "b" in edges:
            pts += [(x, fc.h - ins) for x in xs]
    if "l" in edges or "r" in edges:
        n = max(1, int((fc.h - 2 * ins) / step) + 1)
        ys = np.linspace(ins, fc.h - ins, n)
        if "l" in edges:
            pts += [(ins, y) for y in ys]
        if "r" in edges:
            pts += [(fc.w - ins, y) for y in ys]
    for (cx, cy) in pts:
        x = fc.px - cx
        y = fc.py - cy
        dd = np.sqrt(x * x + y * y)
        m = dd < r + 0.3
        if not m.any():
            continue
        lit = np.clip(1.15 - (x - y) / max(r, 0.5) * 0.35, 0.55, 1.5)
        _mulk(fc, m, lit)
        fc.mul((dd < r + 1.2) & ~m & (x + y > 0), 0.8)


# ---- 記号（面の正規化座標の多角形） --------------------------------------------
def _sym_polys(kind):
    """記号の多角形（-1..1 の箱の中、y は下向き）。[(多角形, 色の名前)]。"""
    if kind == "bolt":
        return [([(0.15, -0.95), (-0.45, 0.1), (-0.05, 0.1), (-0.25, 0.95), (0.45, -0.15), (0.05, -0.15),
                  (0.3, -0.95)], "ink")]
    if kind == "flame":
        return [([(0.0, -0.95), (0.3, -0.4), (0.55, -0.6), (0.6, 0.0), (0.5, 0.55), (0.2, 0.85), (-0.2, 0.85),
                  (-0.5, 0.55), (-0.6, 0.05), (-0.35, -0.3), (-0.25, 0.05), (-0.1, -0.5)], "ink")]
    if kind == "cross":
        return [([(-0.3, -0.9), (0.3, -0.9), (0.3, -0.3), (0.9, -0.3), (0.9, 0.3), (0.3, 0.3), (0.3, 0.9),
                  (-0.3, 0.9), (-0.3, 0.3), (-0.9, 0.3), (-0.9, -0.3), (-0.3, -0.3)], "ink")]
    if kind == "arrow_r":
        return [([(-0.9, -0.25), (0.2, -0.25), (0.2, -0.65), (0.95, 0.0), (0.2, 0.65), (0.2, 0.25),
                  (-0.9, 0.25)], "ink")]
    if kind == "arrow_up":
        return [([(-0.25, 0.9), (-0.25, -0.2), (-0.65, -0.2), (0.0, -0.95), (0.65, -0.2), (0.25, -0.2),
                  (0.25, 0.9)], "ink")]
    if kind == "runner":
        # 走る人（避難経路）
        return [([(0.15, -0.9), (0.35, -0.75), (0.2, -0.55), (0.0, -0.7)], "ink"),
                ([(-0.05, -0.5), (0.25, -0.45), (0.45, -0.15), (0.6, -0.25), (0.65, -0.15), (0.4, 0.05),
                  (0.25, -0.15), (0.2, 0.15), (0.45, 0.45), (0.35, 0.9), (0.2, 0.85), (0.25, 0.5), (0.0, 0.3),
                  (-0.2, 0.55), (-0.55, 0.65), (-0.6, 0.5), (-0.3, 0.35), (-0.1, 0.05), (-0.05, -0.2),
                  (-0.3, 0.0), (-0.45, -0.1), (-0.15, -0.4)], "ink")]
    if kind == "skull":
        return [([(-0.6, -0.4), (-0.45, -0.8), (0.0, -0.95), (0.45, -0.8), (0.6, -0.4), (0.5, 0.15), (0.3, 0.3),
                  (0.3, 0.6), (-0.3, 0.6), (-0.3, 0.3), (-0.5, 0.15)], "ink"),
                ([(-0.4, -0.35), (-0.1, -0.35), (-0.1, -0.05), (-0.4, -0.05)], "bg"),
                ([(0.1, -0.35), (0.4, -0.35), (0.4, -0.05), (0.1, -0.05)], "bg"),
                ([(-0.05, 0.05), (0.05, 0.05), (0.1, 0.2), (-0.1, 0.2)], "bg")]
    if kind == "triangle":
        return [([(0.0, -0.95), (0.95, 0.85), (-0.95, 0.85)], "ink")]
    return []


def _draw_symbol(fc, kind, box, colours):
    """box=(u0,v0,u1,v1) に記号を描く。colours = {"ink": rgb, "bg": rgb}。"""
    u0, v0, u1, v1 = box
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    hu, hv = (u1 - u0) / 2, (v1 - v0) / 2
    for poly, cname in _sym_polys(kind):
        pts = [(cu + x * hu, cv + y * hv) for x, y in poly]
        m = _soft_poly(fc, pts)
        fc.paint(m, _rgb(colours.get(cname, (20, 20, 20))))


def d_label(fc, d):
    """ラベル。box, fill, border, text（3x5 の字、複数行は | 区切り）, ink, symbol, sym_box, wear。"""
    u0, v0, u1, v1 = d.get("box", (0.1, 0.1, 0.9, 0.9))
    fill = _rgb(d.get("fill", (226, 190, 40)))
    ink = _rgb(d.get("ink", (24, 22, 20)))
    m = _soft_poly(fc, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    shade = (0.9 + 0.14 * fc.grain(fc.seed + 1))[..., None]
    fc.paint(m, fill * shade)
    bw = d.get("border")
    if bw:
        bpx = float(bw)
        inner = (fc.px > u0 * fc.w + bpx) & (fc.px < u1 * fc.w - bpx) & (fc.py > v0 * fc.h + bpx) & \
                (fc.py < v1 * fc.h - bpx)
        fc.paint((m > 0.5) & ~inner, _rgb(d.get("border_colour", ink)))
    if d.get("symbol"):
        sb = d.get("sym_box", (u0 + 0.08 * (u1 - u0), v0 + 0.1 * (v1 - v0), u0 + 0.42 * (u1 - u0), v1 - 0.1 * (v1 - v0)))
        _draw_symbol(fc, d["symbol"], sb, {"ink": d.get("sym_ink", ink), "bg": fill})
    if d.get("text"):
        lines = str(d["text"]).split("|")
        tb = d.get("text_box", (u0, v0, u1, v1))
        nlines = len(lines)
        for i, ln in enumerate(lines):
            tw = int((tb[2] - tb[0]) * fc.w)
            th = int((tb[3] - tb[1]) * fc.h / nlines)
            if tw < 3 or th < 5:
                continue
            tm = NP.text_mask(ln, tw, th, (0.5, 0.5), d.get("px"))
            full = np.zeros((fc.h, fc.w), f32)
            x0 = int(tb[0] * fc.w)
            y0 = int(tb[1] * fc.h + i * th)
            hh = min(th, fc.h - y0)
            ww = min(tw, fc.w - x0)
            if hh > 0 and ww > 0:
                full[y0:y0 + hh, x0:x0 + ww] = tm[:hh, :ww]
                fc.paint(full, ink)
    wear = float(d.get("wear", 0.25))
    if wear > 0:
        chip = (fc.noise(1.6, fc.seed + 9, 3) > 0.78 - wear * 0.3) & (m > 0.5)
        fc.mul(chip, 0.72)
        dirt = (fc.noise(0.7, fc.seed + 10, 2) * fc.v) * wear
        fc.paint(m * dirt, (70, 60, 44), 0.6)


def d_sign(fc, d):
    """道路標識の板（面いっぱい）。kind: stop / oneway / evac / speed / keep_out。"""
    kind = d.get("kind", "stop")
    shade = (0.92 + 0.12 * fc.grain(fc.seed + 1))[..., None]
    if kind == "stop":
        k = 0.29
        poly = [(k, 0), (1 - k, 0), (1, k), (1, 1 - k), (1 - k, 1), (k, 1), (0, 1 - k), (0, k)]
        m = _soft_poly(fc, poly) > 0.5
        fc.paint(m, np.array([168, 24, 26], f32) * shade)
        kb = 0.06
        inner = [(k + kb * 0.4, kb), (1 - k - kb * 0.4, kb), (1 - kb, k + kb * 0.4), (1 - kb, 1 - k - kb * 0.4),
                 (1 - k - kb * 0.4, 1 - kb), (k + kb * 0.4, 1 - kb), (kb, 1 - k - kb * 0.4), (kb, k + kb * 0.4)]
        mi = _soft_poly(fc, inner) > 0.5
        fc.paint(m & ~mi, (226, 222, 212))
        kb2 = 0.1
        inner2 = [(k + kb2 * 0.4, kb2), (1 - k - kb2 * 0.4, kb2), (1 - kb2, k + kb2 * 0.4),
                  (1 - kb2, 1 - k - kb2 * 0.4), (1 - k - kb2 * 0.4, 1 - kb2), (k + kb2 * 0.4, 1 - kb2),
                  (kb2, 1 - k - kb2 * 0.4), (kb2, k + kb2 * 0.4)]
        mi2 = _soft_poly(fc, inner2) > 0.5
        fc.paint(mi & ~mi2, np.array([168, 24, 26], f32) * shade)
        tm = NP.text_mask("STOP", fc.w, fc.h, (0.5, 0.5))
        fc.paint(tm, (232, 230, 222))
        if d.get("cut", True):
            _cut(fc, m)
        return
    if kind == "oneway":
        fc.paint(np.ones((fc.h, fc.w)), np.array([24, 24, 26], f32) * shade)
        _draw_symbol(fc, "arrow_r", (0.05, 0.12, 0.95, 0.88), {"ink": (228, 226, 218)})
        tm = NP.text_mask("ONE WAY", int(fc.w * 0.6), int(fc.h * 0.36), (0.5, 0.5))
        full = np.zeros((fc.h, fc.w), f32)
        y0 = int(fc.h * 0.32)
        x0 = int(fc.w * 0.08)
        full[y0:y0 + tm.shape[0], x0:x0 + tm.shape[1]] = tm[:fc.h - y0, :fc.w - x0]
        fc.paint(full, (24, 24, 26))
        return
    if kind == "evac":
        fc.paint(np.ones((fc.h, fc.w)), np.array([26, 108, 64], f32) * shade)
        bor = (fc.px < 1.2) | (fc.px > fc.w - 1.2) | (fc.py < 1.2) | (fc.py > fc.h - 1.2)
        fc.paint(bor, (224, 224, 216))
        _draw_symbol(fc, "runner", (0.08, 0.1, 0.5, 0.62), {"ink": (232, 232, 224), "bg": (26, 108, 64)})
        _draw_symbol(fc, "arrow_r", (0.52, 0.18, 0.92, 0.55), {"ink": (232, 232, 224)})
        tm = NP.text_mask("EVAC", int(fc.w * 0.9), int(fc.h * 0.3), (0.5, 0.5))
        full = np.zeros((fc.h, fc.w), f32)
        y0 = int(fc.h * 0.66)
        x0 = int(fc.w * 0.05)
        hh = min(tm.shape[0], fc.h - y0)
        full[y0:y0 + hh, x0:x0 + tm.shape[1]] = tm[:hh, :fc.w - x0]
        fc.paint(full, (232, 232, 224))
        return
    if kind == "speed":
        fc.paint(np.ones((fc.h, fc.w)), np.array([222, 220, 210], f32) * shade)
        bor = (fc.px < 1.4) | (fc.px > fc.w - 1.4) | (fc.py < 1.4) | (fc.py > fc.h - 1.4)
        fc.paint(bor, (26, 26, 28))
        for txt, at, hfrac in (("SPEED", 0.16, 0.18), ("LIMIT", 0.36, 0.18), ("30", 0.7, 0.42)):
            tm = NP.text_mask(txt, fc.w - 4, int(fc.h * hfrac), (0.5, 0.5))
            full = np.zeros((fc.h, fc.w), f32)
            y0 = int(fc.h * at - tm.shape[0] / 2)
            hh = min(tm.shape[0], fc.h - y0)
            full[y0:y0 + hh, 2:2 + tm.shape[1]] = tm[:hh]
            fc.paint(full, (26, 26, 28))
        return
    if kind == "keep_out":
        fc.paint(np.ones((fc.h, fc.w)), np.array([226, 222, 210], f32) * shade)
        top = fc.v < 0.32
        fc.paint(top, (170, 26, 24))
        tm = NP.text_mask("DANGER", fc.w - 2, int(fc.h * 0.26), (0.5, 0.5))
        full = np.zeros((fc.h, fc.w), f32)
        full[1:1 + tm.shape[0], 1:1 + tm.shape[1]] = tm[:fc.h - 1, :fc.w - 1]
        fc.paint(full, (236, 234, 226))
        tm2 = NP.text_mask("KEEP OUT", fc.w - 2, int(fc.h * 0.3), (0.5, 0.5))
        full2 = np.zeros((fc.h, fc.w), f32)
        y0 = int(fc.h * 0.5)
        full2[y0:y0 + tm2.shape[0], 1:1 + tm2.shape[1]] = tm2[:fc.h - y0, :fc.w - 1]
        fc.paint(full2, (26, 26, 28))


def d_diamond_plate(fc, d):
    """縞鋼板（斜めの凸が互い違い）。"""
    x = fc.px / fc.s
    y = fc.py / fc.s
    p = float(d.get("pitch", 1.6))
    i = np.floor(x / p)
    j = np.floor(y / p)
    fx = x / p - i - 0.5
    fy = y / p - j - 0.5
    flip = ((i + j) % 2) == 0
    a = np.where(flip, fx + fy, fx - fy)
    b = np.where(flip, fx - fy, fx + fy)
    lug = (np.abs(a) < 0.42) & (np.abs(b) < 0.1)
    hi = lug & (b < 0)
    lo = lug & (b >= 0)
    fc.mul(hi, 1.35)
    fc.mul(lo, 0.7)


def d_led(fc, d):
    """LED の粒の格子（明るい色）。cols, rows, colour, dark（消えている）。"""
    cols = int(d.get("cols", 9))
    rows = int(d.get("rows", 6))
    col = _rgb(d.get("colour", (200, 140, 255)))
    fc.paint(np.ones((fc.h, fc.w)), (24, 18, 30))
    gx = fc.u * cols
    gy = fc.v * rows
    dx = gx - np.floor(gx) - 0.5
    dy = gy - np.floor(gy) - 0.5
    r = np.sqrt(dx * dx + dy * dy)
    dot = r < 0.36
    if d.get("dark"):
        fc.paint(dot, (58, 46, 70))
        fc.paint(dot & (dx + dy < -0.2), (96, 84, 110))
    else:
        core = r < 0.2
        fc.paint(dot, col)
        fc.paint(core, np.minimum(255, col * 0.5 + 140))


def d_coil(fc, d):
    """コイルの巻き線（v 方向に 1 texel ごとの線）と円筒の陰影。"""
    rows = (fc.py.astype(np.int64) % 2) == 0
    cyl = 0.62 + 0.55 * np.sin(np.clip(fc.u, 0, 1) * math.pi)
    hi = np.exp(-((fc.u - 0.35) / 0.12) ** 2) * 0.35
    k = cyl + hi
    k = k * np.where(rows, 1.0, 0.8)
    if fc.side:
        _mulk(fc, np.ones_like(k), k)
    else:
        r = np.sqrt((fc.u - 0.5) ** 2 + (fc.v - 0.5) ** 2)
        fc.paint(r < 0.22, (52, 52, 56))
        rings = (np.abs(np.sin(r * fc.w * 1.6)) < 0.35) & (r >= 0.22)
        fc.mul(rings, 0.8)


def d_pegboard(fc, d):
    """有孔ボードの穴の格子（step 単位）と、工具の影絵。"""
    step = float(d.get("step", 1.0)) * fc.s
    x = (fc.px % step) - step / 2
    y = (fc.py % step) - step / 2
    hole = (x * x + y * y) < (step * 0.18) ** 2
    fc.paint(hole, (30, 24, 18))
    for sh in d.get("shadows", []):
        kind, (cu, cv), sz = sh
        if kind == "wrench":
            poly = [(cu - sz * 0.08, cv - sz * 0.5), (cu + sz * 0.08, cv - sz * 0.5), (cu + sz * 0.08, cv + sz * 0.3),
                    (cu + sz * 0.2, cv + sz * 0.42), (cu + sz * 0.05, cv + sz * 0.5), (cu - sz * 0.05, cv + sz * 0.5),
                    (cu - sz * 0.2, cv + sz * 0.42), (cu - sz * 0.08, cv + sz * 0.3)]
        else:   # saw / generic
            poly = [(cu - sz * 0.25, cv - sz * 0.5), (cu + sz * 0.25, cv - sz * 0.5), (cu + sz * 0.1, cv + sz * 0.5),
                    (cu - sz * 0.25, cv + sz * 0.5)]
        m = _soft_poly(fc, poly)
        edge = m * (1 - _soft_poly(fc, [(cu + (px - cu) * 0.82, cv + (py - cv) * 0.86) for px, py in poly]))
        fc.paint(edge, (36, 30, 26), 0.75)


def d_peel(fc, d):
    """剥げかけのペンキ（下地は今の色＝木など）。colour, amount。"""
    col = _rgb(d.get("colour", (216, 212, 200)))
    amt = float(d.get("amount", 0.35))
    n = fc.noise(1.2, fc.seed + 1, 3)
    edge = np.minimum(np.minimum(fc.px, fc.w - fc.px), np.minimum(fc.py, fc.h - fc.py)) / max(fc.s, 1)
    chip_f = n + _ss(1.5, 0.2, edge) * 0.25
    th = 0.72 - amt * 0.3
    painted = chip_f < th
    rim = (chip_f >= th - 0.05) & painted
    paint = col * (0.88 + 0.12 * fc.grain(fc.seed + 2))[..., None]
    paint = paint * (1.0 - 0.18 * (fc.noise(0.5, fc.seed + 3, 2) - 0.5))[..., None]
    fc.paint(painted, paint)
    fc.mul(rim, 0.82)
    grime = (fc.noise(0.6, fc.seed + 4, 2) * (fc.v if fc.side else 0.5))
    fc.paint(painted * grime, (90, 80, 62), 0.35)


def d_claw(fc, d):
    """引っかき傷（平行な 3〜4 本、木の白い地肌と血）。at, size, angle, n, blood。"""
    cu, cv = d.get("at", (0.5, 0.5))
    size = float(d.get("size", 0.5))
    ang = math.radians(float(d.get("angle", 70)))
    n = int(d.get("n", 4))
    dx, dy = math.cos(ang) * size * 0.5, math.sin(ang) * size * 0.5
    for i in range(n):
        off = (i - (n - 1) / 2) * 0.06
        ox, oy = -math.sin(ang) * off, math.cos(ang) * off
        a = (cu + ox - dx * (0.8 + 0.05 * i), cv + oy - dy)
        b = (cu + ox + dx, cv + oy + dy * (0.9 - 0.1 * i))
        m = fc.seg(a[0], a[1], b[0], b[1], 1.3)
        mm = fc.seg(a[0], a[1], b[0], b[1], 2.6)
        fc.mul(mm, 0.75)
        fc.paint(m, (196, 168, 128))
        if d.get("blood", 0.6) > 0:
            bl = fc.seg(a[0], a[1], a[0] + (b[0] - a[0]) * 0.45, a[1] + (b[1] - a[1]) * 0.45, 1.4)
            fc.paint(bl * (fc.grain(fc.seed + i) > 0.25), (96, 10, 10), float(d.get("blood", 0.6)))


def d_poster(fc, d):
    """尋ね人のビラ（紙の上に見出し・写真・文字の行）。"""
    fc.paint(fc.v < 0.2, (40, 34, 30), 0.0)
    head = NP.text_mask(d.get("title", "MISSING"), fc.w - 2, max(5, int(fc.h * 0.18)), (0.5, 0.5))
    full = np.zeros((fc.h, fc.w), f32)
    full[1:1 + head.shape[0], 1:1 + head.shape[1]] = head[:fc.h - 1, :fc.w - 1]
    fc.paint(full, (150, 24, 20))
    ph = (fc.u > 0.2) & (fc.u < 0.8) & (fc.v > 0.25) & (fc.v < 0.62)
    fc.paint(ph, (120, 116, 108))
    face = ((fc.u - 0.5) / 0.14) ** 2 + ((fc.v - 0.4) / 0.1) ** 2 < 1
    fc.paint(face & ph, (176, 160, 140))
    sh = ((fc.u - 0.5) / 0.26) ** 2 + ((fc.v - 0.62) / 0.12) ** 2 < 1
    fc.paint(sh & ph, (60, 60, 64))
    for k in range(4):
        v = 0.68 + k * 0.07
        ln = (np.abs(fc.v - v) * fc.h < 0.5) & (fc.u > 0.12) & (fc.u < 0.88 - 0.1 * (k % 2))
        fc.paint(ln & (fc.grain(fc.seed + k) > 0.3), (60, 56, 52))
    stain = fc.noise(0.8, fc.seed + 9, 2) * fc.v
    fc.paint(stain, (120, 100, 60), 0.35)


def d_grit(fc, d):
    """床の砂利・ガラス片・紙くず（アルファで抜く）。density, radius（中心からの広がり 0..1）。"""
    dens = float(d.get("density", 0.5))
    rad = float(d.get("radius", 0.9))
    x = fc.px / fc.s
    y = fc.py / fc.s
    F1, F2, cid, _, _ = NP.worley2(x.reshape(-1) * f32(1.4), y.reshape(-1) * f32(1.4), fc.seed + 1)
    F1 = F1.reshape(fc.h, fc.w)
    cid = cid.reshape(fc.h, fc.w)
    r = np.sqrt((fc.u - 0.5) ** 2 + (fc.v - 0.5) ** 2) / 0.5
    fall = np.clip(1.0 - (r - rad * 0.6) / max(1e-3, rad * 0.5), 0, 1)
    pebble = (cid < dens * fall) & (F1 < 0.32)
    dust = (fc.noise(0.7, fc.seed + 2, 3) * fall > 0.62)
    keep = pebble | dust
    pc = _ramp_np(cid / max(dens, 1e-3), [(0.0, (120, 116, 108)), (0.5, (88, 84, 78)), (0.8, (140, 128, 110)),
                                          (1.0, (70, 66, 62))])
    fc.paint(pebble, pc * (0.8 + 0.4 * (1 - F1 / 0.32))[..., None])
    fc.paint(dust & ~pebble, (104, 100, 92), 0.7)
    glass = pebble & (cid < dens * fall * 0.18)
    fc.paint(glass, (176, 206, 214))
    fc.paint(glass & (F1 < 0.12), (236, 244, 246))
    _cut(fc, keep)


def d_pool(fc, d):
    """不規則な広がり（アルファ）。kind: blood / oil / burnt / stain / moss、radius, alpha, splats。"""
    kind = d.get("kind", "blood")
    rad = float(d.get("radius", 0.42))
    cu, cv = d.get("at", (0.5, 0.5))
    ax = (fc.u - cu)
    ay = (fc.v - cv)
    r = np.sqrt(ax * ax + ay * ay) / rad
    n = fc.noise(0.35, fc.seed + 1, 3)
    n2 = fc.noise(1.2, fc.seed + 2, 2)
    edge = r + (n - 0.5) * 0.9 + (n2 - 0.5) * 0.25
    inside = edge < 1.0
    # 飛び散った滴
    sp = np.zeros_like(inside)
    nspl = int(d.get("splats", 7))
    rng = np.random.default_rng(fc.seed + 3)
    for _ in range(nspl):
        a = rng.uniform(0, 2 * math.pi)
        dd = rad * rng.uniform(1.05, 1.6)
        sr = rng.uniform(0.012, 0.035)
        sp |= ((fc.u - cu - math.cos(a) * dd) ** 2 + (fc.v - cv - math.sin(a) * dd) ** 2) < sr * sr
    m = inside | sp
    depth = np.clip(1.0 - edge, 0, 1)
    alpha_in = int(d.get("alpha", 255))
    if kind == "blood":
        dark = _ramp_np(depth + (n2 - 0.5) * 0.2, [(0.0, (64, 10, 8)), (0.15, (96, 8, 10)), (0.45, (74, 4, 6)),
                                                  (1.0, (46, 2, 4))])
        fc.paint(m, dark)
        rim = m & (edge > 0.82) & inside
        fc.paint(rim, (40, 14, 10))
        gl = inside & (fc.noise(1.0, fc.seed + 4, 2) > 0.62) & (depth > 0.25)
        fc.paint(gl, (150, 40, 40), 0.55)
        fc.paint(gl & (fc.grain(fc.seed + 5) > 0.82), (220, 170, 170), 0.6)
    elif kind == "oil":
        t = (fc.noise(0.5, fc.seed + 6, 3) * 3.0 + depth * 1.5) % 1.0
        hue = _ramp_np(t, [(0.0, (60, 40, 80)), (0.2, (40, 70, 90)), (0.4, (60, 90, 50)), (0.6, (110, 90, 40)),
                           (0.8, (100, 50, 60)), (1.0, (60, 40, 80))])
        base = np.array([30, 26, 22], f32)
        film = _ss(0.15, 0.6, depth) * (fc.noise(0.8, fc.seed + 7, 2) > 0.4)
        col = base + (hue - base) * (film * 0.55)[..., None]
        fc.paint(m, col)
        fc.paint(inside & (fc.grain(fc.seed + 8) > 0.93), (150, 150, 150), 0.4)
    elif kind == "burnt":
        col = _ramp_np(n2, [(0.0, (16, 14, 12)), (0.6, (34, 30, 28)), (1.0, (70, 66, 62))])
        fc.paint(m, col)
        fc.paint(m & (fc.grain(fc.seed + 9) > 0.9), (130, 126, 120), 0.6)
    elif kind == "moss":
        col = _ramp_np(n2, [(0.0, (38, 52, 30)), (0.6, (66, 84, 44)), (1.0, (100, 112, 70))])
        fc.paint(m, col * (0.85 + 0.3 * fc.grain(fc.seed + 10))[..., None])
        glow = m & (fc.noise(1.5, fc.seed + 11, 2) > 0.66)
        fc.paint(glow, (186, 120, 255))
    else:   # stain（乾いた血の染み）
        col = _ramp_np(n2, [(0.0, (44, 14, 10)), (1.0, (82, 30, 22))])
        fc.paint(m, col, 0.9)
    if d.get("cut", True):
        _cut(fc, m)
    if alpha_in < 255:
        a = np.where(m, alpha_in - (1.0 - np.clip(depth * 3, 0, 1)) * 40, 0)
        fc.alpha[m] = np.clip(a[m], 1, 255).astype(np.uint8)


def d_tire_side(fc, d):
    """タイヤの側面（ワールド座標の中心 c=(x,z) と内径・外径）。"""
    P = _world(fc, d)
    cx, cz = d["c"]
    r = np.sqrt((P[..., 0] - cx) ** 2 + (P[..., 2] - cz) ** 2)
    ri, ro = float(d["ri"]), float(d["ro"])
    t = (r - ri) / max(1e-3, ro - ri)
    bead = np.abs(t - 0.1) < 0.06
    letters = (np.abs(t - 0.6) < 0.12) & (np.sin(np.arctan2(P[..., 2] - cz, P[..., 0] - cx) * 22) > 0.1)
    shoulder = t > 0.88
    fc.mul(bead, 0.6)
    fc.paint(letters, (64, 64, 66), 0.7)
    fc.mul(shoulder, 0.75)
    _mulk(fc, np.ones_like(t), 0.9 + 0.2 * np.clip(t, 0, 1))


def d_ring(fc, d):
    """有刺鉄線の輪（面いっぱいの円、棘付き、外はアルファで抜く）。r, wire（texel）, barbs。"""
    x = fc.u - 0.5
    y = fc.v - 0.5
    r = np.sqrt(x * x + y * y)
    R = float(d.get("r", 0.44))
    w = float(d.get("wire", 1.3)) / max(fc.w, 1)
    wob = (fc.noise(0.8, fc.seed + 1, 2) - 0.5) * 0.04
    wire = np.abs(r - R + wob) < w * 0.75
    keep = wire.copy()
    ang = np.arctan2(y, x)
    nb = int(d.get("barbs", 9))
    for i in range(nb):
        a = (i + 0.3 * math.sin(i * 1.7)) / nb * 2 * math.pi
        bx, by = 0.5 + math.cos(a) * R, 0.5 + math.sin(a) * R
        L = 0.06
        for da in (0.8, -0.8):
            m = fc.seg(bx - math.cos(a + da) * L, by - math.sin(a + da) * L,
                       bx + math.cos(a + da) * L, by + math.sin(a + da) * L, 1.0) > 0.5
            keep |= m
    shade = 0.8 + 0.45 * np.abs(np.sin(ang * 6.0))
    _mulk(fc, np.ones_like(shade), shade)
    _cut(fc, keep)


def d_strand(fc, d):
    """真っすぐな有刺鉄線（u 方向、2 本撚り、棘）。外はアルファで抜く。"""
    w = fc.w
    h = fc.h
    yc = h / 2.0
    amp = max(0.6, h * 0.18)
    per = max(3.0, fc.s * 1.1)
    y1 = yc + amp * np.sin(fc.px / per * 2 * math.pi)
    y2 = yc - amp * np.sin(fc.px / per * 2 * math.pi)
    keep = (np.abs(fc.py - y1) < 0.75) | (np.abs(fc.py - y2) < 0.75)
    step = max(6.0, fc.s * 3.0)
    for i in range(int(w / step) + 1):
        bx = (i + 0.5) * step
        m = (np.abs(fc.px - bx) < 0.7) | (np.abs((fc.px - bx) - (fc.py - yc)) < 0.7) & (np.abs(fc.px - bx) < h * 0.5)
        keep |= m & (np.abs(fc.px - bx) < h * 0.5)
    _mulk(fc, np.ones((h, w)), 0.85 + 0.3 * fc.grain(fc.seed + 1))
    _cut(fc, keep)


def d_teeth(fc, d):
    """鋼の歯（面の上側をのこぎり状に抜く）。n 歯の数、depth 歯の深さ（面の高さに対する割合）。"""
    n = float(d.get("n", 8))
    dep = float(d.get("depth", 0.6))
    q = fc.u * n
    tri = 1.0 - np.abs((q - np.floor(q)) - 0.5) * 2.0
    top = (1.0 - fc.v)
    keep = top < (1.0 - dep) + dep * (1.0 - tri)
    _mulk(fc, np.ones_like(tri), 0.85 + 0.3 * tri)
    _cut(fc, keep)


def d_flame(fc, d):
    """炎の舌（アルファで抜く）。側面: 下から上へ不規則な舌。上面は中央だけ。"""
    if fc.face == "up" or fc.face == "down":
        r = np.sqrt((fc.u - 0.5) ** 2 + (fc.v - 0.5) ** 2)
        keep = r < 0.3 + (fc.noise(1.2, fc.seed + 1, 2) - 0.5) * 0.2
        fc.paint(np.ones((fc.h, fc.w)), (255, 230, 150))
        _cut(fc, keep)
        return
    n = fc.noise(0.9, fc.seed + 2, 3)
    tongues = 0.55 + 0.35 * np.abs(np.sin(fc.u * math.pi * float(d.get("tongues", 3.0)) + n * 2.0))
    ht = tongues + (n - 0.5) * 0.4
    y = 1.0 - fc.v
    keep = y < ht
    t = np.clip(y / np.maximum(ht, 0.05), 0, 1)
    col = _ramp_np(t, [(0.0, (255, 248, 210)), (0.35, (255, 206, 90)), (0.7, (250, 130, 30)),
                       (1.0, (200, 50, 16))])
    fc.paint(np.ones((fc.h, fc.w)), col)
    _cut(fc, keep)


def d_xpress(fc, d):
    """携行缶の X 字のプレス（凹みの陰影）と縁の段。"""
    w = 1.6 / max(fc.w, 1) * fc.s / 4.0 * 1.6
    m1 = fc.seg(0.12, 0.12, 0.88, 0.88, max(1.5, fc.s * 0.55))
    m2 = fc.seg(0.88, 0.12, 0.12, 0.88, max(1.5, fc.s * 0.55))
    up1 = fc.seg(0.12, 0.12 - w, 0.88, 0.88 - w, 1.0)
    up2 = fc.seg(0.88, 0.12 - w, 0.12, 0.88 - w, 1.0)
    fc.mul(np.maximum(m1, m2), 0.82)
    fc.mul(np.maximum(up1, up2) * (1 - np.maximum(m1, m2)), 1.2)
    bor = (np.abs(fc.px - 1.5) < 0.6) | (np.abs(fc.px - (fc.w - 1.5)) < 0.6) | \
          (np.abs(fc.py - 1.5) < 0.6) | (np.abs(fc.py - (fc.h - 1.5)) < 0.6)
    fc.mul(bor, 0.8)


def d_holes(fc, d):
    """角柱の穴の列（v 方向）。step（単位）。"""
    step = float(d.get("step", 1.4)) * fc.s
    cy = (fc.py % step) - step / 2
    cx = fc.px - fc.w / 2
    hole = (np.abs(cx) < max(0.6, fc.w * 0.16)) & (np.abs(cy) < max(0.6, step * 0.2))
    fc.paint(hole, (20, 20, 22))
    fc.mul(np.roll(hole, 1, axis=0) & ~hole, 1.25)


def d_footprints(fc, d):
    """泥の靴跡（上面、ワールド座標でなく面のローカル）。n, colour。"""
    rng = np.random.default_rng(fc.seed + 1)
    col = _rgb(d.get("colour", (74, 58, 40)))
    u, v = rng.uniform(0.15, 0.3), rng.uniform(0.7, 0.85)
    for i in range(int(d.get("n", 4))):
        ang = rng.uniform(-0.6, -0.3)
        side = 0.06 if i % 2 else -0.06
        cu, cv = u + side * math.cos(ang), v + side * math.sin(ang)
        sole = (((fc.u - cu) / 0.05) ** 2 + ((fc.v - cv) / 0.09) ** 2) < 1
        heel = (((fc.u - cu) / 0.045) ** 2 + ((fc.v - cv - 0.12) / 0.04) ** 2) < 1
        tread = (fc.py.astype(np.int64) % 2 == 0)
        fc.paint((sole | heel) & tread, col, 0.75)
        fc.paint((sole | heel) & ~tread, col * 0.8, 0.5)
        u += 0.16
        v -= 0.17


def d_wrinkle(fc, d):
    """ゴミ袋のしわ（艶の筋と谷）と破れ目から見える中身。tear=(cu,cv,r)。"""
    n = fc.noise(0.55, fc.seed + 1, 3)
    crease = 1.0 - _ss(0.0, 0.05, np.abs(n - 0.5))
    ridge = _ss(0.52, 0.6, n) * (1 - _ss(0.6, 0.7, n))
    fc.mul(crease, 0.55)
    fc.paint(ridge, (110, 112, 124), 0.55)
    spec = (fc.noise(1.1, fc.seed + 2, 2) > 0.72) & (fc.v < 0.55)
    fc.paint(spec, (150, 152, 162), 0.45)
    tear = d.get("tear")
    if tear:
        cu, cv, r = tear
        m = ((fc.u - cu) / r) ** 2 + ((fc.v - cv) / (r * 0.7)) ** 2 + (fc.noise(1.5, fc.seed + 3, 2) - 0.5) * 0.8 < 1
        junk = _ramp_np(fc.grain(fc.seed + 4), [(0.0, (60, 50, 34)), (0.3, (150, 120, 70)), (0.5, (200, 196, 180)),
                                                (0.7, (90, 120, 60)), (0.85, (170, 40, 30)), (1.0, (40, 40, 40))])
        fc.paint(m, junk)
        rim = m & ~(((fc.u - cu) / (r * 0.8)) ** 2 + ((fc.v - cv) / (r * 0.56)) ** 2 < 1)
        fc.paint(rim, (36, 36, 42))


def d_stitch_ends(fc, d):
    """土嚢の両端の縫い目と結び口のしわ（u の両端）。"""
    for e in (1.5, fc.w - 1.5):
        ln = np.abs(fc.px - e) < 0.6
        dots = ln & (fc.py.astype(np.int64) % 3 != 0)
        fc.paint(dots, (80, 66, 44), 0.8)
        fold = np.abs(fc.px - e) < 3.0
        k = 0.85 + 0.25 * np.sin(fc.py * 1.3 + fc.seed % 7)
        _mulk(fc, fold, k)


def d_tally(fc, d):
    """チョークの集計の線（5 本ずつ）。ワールド座標でなく面のローカル。box, groups, colour。"""
    u0, v0, u1, v1 = d.get("box", (0.1, 0.55, 0.9, 0.9))
    groups = int(d.get("groups", 5))
    col = _rgb(d.get("colour", (226, 224, 214)))
    gw = (u1 - u0) / groups
    rng = np.random.default_rng(fc.seed + 1)
    for g in range(groups):
        n = 5 if g < groups - 1 else int(d.get("last", 3))
        for i in range(min(n, 4)):
            u = u0 + g * gw + (i + 0.5) * gw * 0.18 + rng.normal(0, 0.004)
            m = fc.seg(u, v0 + rng.normal(0, 0.01), u + rng.normal(0, 0.01), v1, 1.1)
            fc.paint(m * (fc.grain(fc.seed + g * 7 + i) > 0.3), col)
        if n >= 5:
            m = fc.seg(u0 + g * gw - 0.01, v1 - 0.05, u0 + g * gw + gw * 0.8, v0 + 0.05, 1.1)
            fc.paint(m * (fc.grain(fc.seed + 99 + g) > 0.3), col)


def d_uv_mark(fc, d):
    """生存者の UV 塗料の印（円と矢印）。蛍光の紫で明るく塗る（ブロックは光れないので色だけ）。"""
    cu, cv = d.get("at", (0.5, 0.5))
    s = float(d.get("size", 0.35))
    col = _rgb(d.get("colour", (196, 120, 255)))
    x = fc.u - cu
    y = fc.v - cv
    r = np.sqrt(x * x + (y * fc.h / max(fc.w, 1)) ** 2)
    ring = np.abs(r - s * 0.45) < max(1.2 / fc.w, s * 0.06)
    arrow = fc.seg(cu - s * 0.3, cv + s * 0.3, cu + s * 0.32, cv - s * 0.3, max(1.2, fc.w * s * 0.08)) > 0.5
    head = fc.seg(cu + s * 0.32, cv - s * 0.3, cu + s * 0.05, cv - s * 0.32, max(1.2, fc.w * s * 0.08)) > 0.5
    head |= fc.seg(cu + s * 0.32, cv - s * 0.3, cu + s * 0.3, cv - s * 0.02, max(1.2, fc.w * s * 0.08)) > 0.5
    m = (ring | arrow | head) & (fc.grain(fc.seed + 1) > 0.12)
    halo = (r < s * 0.62) & ~m
    fc.paint(halo, col * 0.6, 0.18)
    fc.paint(m, col)
    fc.paint(m & (fc.grain(fc.seed + 2) > 0.7), np.minimum(255, col * 0.5 + 130))


DECALS = {
    "nrb_spray": d_spray, "nrb_nails": d_nails, "nrb_brick": d_brick, "nrb_chainlink": d_chainlink,
    "nrb_clear": d_clear, "nrb_cut_poly": d_cut_poly, "nrb_corrugate": d_corrugate, "nrb_slits": d_slits,
    "nrb_grille": d_grille, "nrb_rivets": d_rivets, "nrb_label": d_label, "nrb_sign": d_sign,
    "nrb_diamond_plate": d_diamond_plate, "nrb_led": d_led, "nrb_coil": d_coil, "nrb_pegboard": d_pegboard,
    "nrb_peel": d_peel, "nrb_claw": d_claw, "nrb_poster": d_poster, "nrb_grit": d_grit, "nrb_pool": d_pool,
    "nrb_tire_side": d_tire_side, "nrb_ring": d_ring, "nrb_strand": d_strand, "nrb_teeth": d_teeth,
    "nrb_flame": d_flame, "nrb_xpress": d_xpress, "nrb_holes": d_holes, "nrb_footprints": d_footprints,
    "nrb_wrinkle": d_wrinkle, "nrb_stitch_ends": d_stitch_ends, "nrb_tally": d_tally, "nrb_uv_mark": d_uv_mark,
}


def register():
    """nr_paint.DECALS に nrb_* を足す（このプロセスの中だけ）。何度呼んでもよい。"""
    for k, fn in DECALS.items():
        NP.DECALS[k] = fn


register()
