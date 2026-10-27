# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 飛び道具のモデルとテクスチャ（`geometry.nr.proj.<key>` / `textures/nr/proj/<key>.png`）。

持ち主は `gen_nr_entities.py`（DESIGN.md §1）。この中の関数は gen_nr_entities からだけ呼ぶ。
spec（`nr_spec.ALL_PROJECTILES` の `model`）の部品の大きさ・素材を下敷きに、武器と同じ道具箱（`nr_weapon_common`:
形の関数・Stylebook・`texture()` = nr_paint で塗って AO・縁の照り・血・ほつれ）で細かく作る。

■ 形の約束（クライアントエンティティのアニメ `animation.nr.proj.<key>` との契約）
* ボーンは `body`（向き: 進む向きへ yaw / pitch）→ `root`（spec の spin で回す）→ 部品。どちらも pivot は当たり箱の中心
  （足元から hitbox の高さの半分）。部品は root の下（子ボーンを足してもよい）。
* 武器空間と同じ向き: **-Z = 先（矢じり・刃先・進む向き）**、+Y = 上。弾む・割れる物（瓶・爆弾・筒・塊）は
  地面に寝た姿勢（長い軸を Z）で作る（止まるとアニメが水平に寝かせる）。
* 光る部分（炎・火花・UV・酸）は nr_paint の glow（α = EMISSIVE_ALPHA）。それを持つ物は entity_emissive_alpha、
  ほかは entity_alphatest（`write_all` の戻り値の glow）。
* キューブ ≤ 60 前後、テクスチャ ≤ 256×256（小さい物なので武器の上限 180 / 256×512 よりずっと小さく）。
"""
from __future__ import annotations

import math
import os
import random
import sys
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nr_weapon_common as WC  # noqa: E402
import nr_paint as NP  # noqa: E402
import nr_spec as S  # noqa: E402
from nr_common import stable_hash, write_geometry  # noqa: E402

MAX_TEX = (256, 256)
MAX_CUBES = 90

beam, cbox, box, rod, band, disc, ring_of, wrap, rag, coil, rivet, fill_tri_yz, hex_prism, polyline = (
    WC.beam, WC.cbox, WC.box, WC.rod, WC.band, WC.disc, WC.ring_of, WC.wrap, WC.rag, WC.coil, WC.rivet,
    WC.fill_tri_yz, WC.hex_prism, WC.polyline)


class ProjModel(WC.WeaponModel):
    """WeaponModel の骨組み（hold → root）を、アタッチャブルの binding の無い body → root に替えたもの。"""

    def __init__(self, key: str, uv: float = 6.0):
        super().__init__(key, uv=uv, max_tex=MAX_TEX, visible_bounds=(1.5, 1.5), vb_offset=(0, 0.25, 0),
                         ident=f"geometry.nr.proj.{key}")
        self.hold.name = "body"
        self.hold.binding = None
        self.root.parent = "body"
        self.body = self.hold
        self.bones = {"body": self.hold, "root": self.root}


def lift(wm: ProjModel, dy: float) -> None:
    """全部を dy だけ上げる（足元の原点 → 当たり箱の中心に pivot）。"""
    for b in wm.model.bones:
        b.pivot = [b.pivot[0], round(b.pivot[1] + dy, 3), b.pivot[2]]
    for c in wm.cubes:
        c.origin = [c.origin[0], round(c.origin[1] + dy, 3), c.origin[2]]
        if c.pivot:
            c.pivot = [c.pivot[0], round(c.pivot[1] + dy, 3), c.pivot[2]]


BUILDERS: Dict[str, Callable] = {}


def builder(key: str):
    def deco(fn):
        BUILDERS[key] = fn
        return fn
    return deco


def _radial(k: int, n: int = 3, phase: float = 90.0) -> np.ndarray:
    """Z 軸まわりの放射方向（k 番目 / n 等分）。"""
    a = math.radians(phase + 360.0 / n * k)
    return np.array([math.cos(a), math.sin(a), 0.0])


def vanes(b, z0: float, z1: float, r: float, h: float, style: str, n: int = 3, t: float = 0.08, uv: float = 10):
    """矢羽根 n 枚（120°）。後ろが高く前へ低くなる台形を 2 本の板で。"""
    for k in range(n):
        d = _radial(k, n)
        L = z1 - z0
        beam(b, d * (r + h * 0.35) + (0, 0, z0 + L * 0.18), d * (r + h * 0.35) + (0, 0, z1), t, h * 0.7, style,
             up=tuple(d), uv=uv)
        beam(b, d * (r + h * 0.62) + (0, 0, z0 + L * 0.45), d * (r + h * 0.62) + (0, 0, z1 - L * 0.05), t, h * 0.55,
             style, up=tuple(d), uv=uv)


def point(b, tip_z: float, base_z: float, half_h: float, thick: float, style: str, *, edge: float = 0.26,
          core: Optional[str] = None, uv: float = 12, tags=()):
    """YZ 平面の平たい切っ先（矢じり・刃先）: 2 本の縁の板（直線の縁）と芯の板。tip_z < base_z（先が -Z）。"""
    tip = np.array([0.0, 0.0, tip_z])
    for s in (-1, 1):
        corner = np.array([0.0, s * (half_h - edge * 0.45), base_z])
        beam(b, tip, corner, thick, edge, style, up=(0, 1, 0), extend=0.12, uv=uv, tags=tags)
    L = base_z - tip_z
    beam(b, (0, 0, tip_z + L * 0.32), (0, 0, base_z), thick * 1.25, half_h * 1.05, core or style, uv=uv)
    beam(b, (0, 0, tip_z + L * 0.12), (0, 0, tip_z + L * 0.5), thick * 1.1, half_h * 0.5, core or style, uv=uv)


# ===========================================================================
#  刺さる物（矢・ボルト・投げナイフ・手裏剣）
# ===========================================================================
@builder("arrow")
def b_arrow(p):
    """生存者の矢: 竹の矢柄（節）、刃の破片を研いだ矢じりを針金で巻く、樹脂の羽根 3 枚、ノック、糸巻き。"""
    wm = ProjModel("arrow", uv=8)
    b = wm.root
    rod(b, (0, 0, 5.2), (0, 0, -4.6), 0.34, "shaft", uv=8)
    for z in (3.0, 0.2, -2.6):                         # 竹の節（少し太く、色が濃い）
        band(b, (0, 0, z), (0, 0, 1), 0.44, 0.24, "node", uv=12)
    # 矢じり: 平たい三角を 2 層（刃は鋼、芯は少し暗い）。根元は針金で巻く
    point(b, -7.0, -4.85, 0.66, 0.14, "head", core="head_core", edge=0.3)
    for s in (-1, 1):                                  # 返し（後ろへ尖る小さな棘）
        beam(b, (0, s * 0.5, -5.0), (0, s * 0.62, -4.55), 0.12, 0.18, "head", uv=14)
    coil(b, (0, 0, -4.55), (0, 0, 1), 0.46, 0.7, 4, "wire", wire=0.1, uv=14)
    # 羽根と、その前後の糸巻き
    vanes(b, 2.2, 4.6, 0.12, 0.85, "vane")
    band(b, (0, 0, 2.15), (0, 0, 1), 0.42, 0.3, "thread", uv=12)
    band(b, (0, 0, 4.75), (0, 0, 1), 0.42, 0.3, "thread", uv=12)
    # ノック（弦の溝のある黒い樹脂）
    cbox(b, (0, 0, 5.45), (0.42, 0.42, 0.5), "nock", uv=12)
    cbox(b, (0, 0.17, 5.8), (0.36, 0.12, 0.4), "nock", uv=12)
    cbox(b, (0, -0.17, 5.8), (0.36, 0.12, 0.4), "nock", uv=12)
    book = WC.Stylebook()
    book.add("shaft", "wood_raw", base=(186, 166, 104), dirt=0.25)
    book.add("node", "wood_dark", base=(128, 108, 64))
    book.add("head", "steel_clean", scratches=0.7)
    book.add("head_core", "steel_worn")
    book.add("wire", "copper_wire", base=(176, 112, 64))
    book.add("vane", "plastic_yellow", wear=0.3, dirt=0.25)
    book.add("thread", "rope", base=(196, 186, 160))
    book.add("nock", "plastic_black", base=(34, 34, 36))
    blood = [WC.blood_zone((-0.6, -0.8, -7.2), (0.6, 0.8, -4.2), 0.45, "dry")]
    return wm, book, blood


@builder("bolt")
def b_bolt(p):
    """ボルト: 短い鉄筋の矢柄（節）、四角錐に研いだ先、黒テープ、黄色い羽根 3 枚。"""
    wm = ProjModel("bolt", uv=8)
    b = wm.root
    beam(b, (0, 0, 3.7), (0, 0, -3.2), 0.44, 0.44, "rebar", uv=9, fx={"rebar": 0.42})
    beam(b, (0, 0, 3.7), (0, 0, -3.2), 0.36, 0.36, "rebar", roll=45.0, uv=9, fx={"rebar": 0.42})
    # 先: 四角錐（45° 回した段を 3 つ）
    cbox(b, (0, 0, -3.45), (0.66, 0.66, 0.6), "tip", uv=12)
    cbox(b, (0, 0, -3.95), (0.5, 0.5, 0.55), "tip", rot=(0, 0, 45), uv=12)
    cbox(b, (0, 0, -4.4), (0.32, 0.32, 0.5), "tip", rot=(0, 0, 45), uv=14)
    cbox(b, (0, 0, -4.75), (0.14, 0.14, 0.35), "tip", rot=(0, 0, 45), uv=16)
    wrap(b, (0, 0, -3.1), (0, 0, -2.2), 0.56, "tape", pitch=0.3, tilt=8, seed=3, uv=12)
    vanes(b, 1.6, 3.5, 0.18, 0.95, "vane")
    wrap(b, (0, 0, 1.45), (0, 0, 1.95), 0.54, "tape", pitch=0.25, tilt=6, seed=4, uv=12)
    cbox(b, (0, 0, 3.85), (0.5, 0.5, 0.3), "nock", uv=12)
    book = WC.Stylebook()
    book.add("rebar", "rebar", dirt=0.4)
    book.add("tip", "steel_clean", scratches=0.8)
    book.add("tape", "tape_black")
    book.add("vane", "plastic_yellow", wear=0.4, dirt=0.3)
    book.add("nock", "steel_dark")
    blood = [WC.blood_zone((-0.6, -0.6, -5.0), (0.6, 0.6, -2.6), 0.5, "wet")]
    return wm, book, blood


@builder("throwing_knife")
def b_throwing_knife(p):
    """投げナイフ: 黒染めの両刃（研いだ縁だけ銀）、コード巻きの柄、輪の柄頭。回って飛ぶ。"""
    wm = ProjModel("throwing_knife", uv=8)
    b = wm.root
    # 刃: 芯の板 + 上下の研いだ縁 + 切っ先の三角
    cbox(b, (0, 0, -2.3), (0.22, 0.86, 3.4), "blade", uv=10)
    cbox(b, (0, 0.5, -2.2), (0.12, 0.18, 3.2), "edge", uv=12, tags=("edge",))
    cbox(b, (0, -0.5, -2.2), (0.12, 0.18, 3.2), "edge", uv=12, tags=("edge",))
    point(b, -5.5, -3.85, 0.6, 0.12, "edge", core="blade", edge=0.22, tags=("edge",))
    cbox(b, (0, 0, -0.45), (0.3, 1.02, 0.3), "blade", uv=10)              # 刃元の段
    # 柄: 中子にパラコードを巻く
    cbox(b, (0, 0, 1.4), (0.2, 0.7, 3.4), "tang", uv=8)
    wrap(b, (0, 0, -0.2), (0, 0, 2.8), (0.5, 0.94), "cord", pitch=0.34, tilt=10, seed=7, uv=12)
    # 柄頭の輪（YZ の四角い輪）
    for (p0, p1) in (((0, 0.42, 3.0), (0, 0.42, 4.0)), ((0, -0.42, 3.0), (0, -0.42, 4.0)),
                     ((0, -0.5, 4.05), (0, 0.5, 4.05))):
        beam(b, p0, p1, 0.2, 0.18, "tang", uv=12)
    book = WC.Stylebook()
    book.add("blade", "steel_dark", scratches=0.4)
    book.add("edge", "steel_clean", scratches=0.6)
    book.add("tang", "steel_dark", wear=0.9)
    book.add("cord", "paracord", base=(84, 92, 58))
    blood = [WC.blood_zone((-0.5, -0.8, -5.6), (0.5, 0.8, -2.8), 0.45, "wet")]
    return wm, book, blood


@builder("throwing_star")
def b_throwing_star(p):
    """刃の手裏剣: 平たい 4 枚刃（XZ 平面）。中央の円盤に穴、刃先は研いで銀、根元に鋲。水平に回って飛ぶ。"""
    wm = ProjModel("throwing_star", uv=10)
    b = wm.root
    disc(b, (0, 0, 0), (0, 1, 0), 0.95, 0.26, "core", n=3, uv=12)
    for k in range(4):
        th = math.radians(90.0 * k)
        d = np.array([math.sin(th), 0.0, -math.cos(th)])
        yaw = 90.0 * k
        # 刃: 根元は厚い本体、先は研いだ薄い縁（菱形 = 45° 回した正方形）
        cbox(b, d * 1.35, (1.25, 0.24, 1.25), "body", rot=(0, yaw + 45.0, 0), uv=12)
        cbox(b, d * 2.05, (0.85, 0.16, 0.85), "edge", rot=(0, yaw + 45.0, 0), uv=14, tags=("edge",))
        cbox(b, d * 2.55, (0.42, 0.12, 0.42), "edge", rot=(0, yaw + 45.0, 0), uv=16, tags=("edge",))
    for k in range(4):
        th = math.radians(90.0 * k + 45.0)
        rivet(b, (math.sin(th) * 0.55, 0.13, -math.cos(th) * 0.55), (0, 1, 0), d=0.26, h=0.07, style="rivet", uv=16)
    wm.cut((0, 0, 0), (0, 1, 0), r=0.28, half=0.6)
    book = WC.Stylebook()
    book.add("core", "steel_worn", scratches=0.8, dirt=0.3)
    book.add("body", "steel_worn", scratches=0.7)
    book.add("edge", "steel_clean", scratches=0.5)
    book.add("rivet", "brass", wear=0.8)
    return wm, book, [WC.blood_zone((0.6, -0.4, -2.9), (2.9, 0.4, -0.6), 0.4, "dry")]


# ===========================================================================
#  投げ物（火炎瓶・パイプ爆弾・爆竹・UV 発煙筒）: 地面に寝た姿勢（長い軸 = Z）
# ===========================================================================
def flame(b, at, size: float, seed: int):
    """揺れる炎: 芯の黄色と外の橙を、少しずつ回した箱で（全部 glow）。"""
    rng = random.Random(stable_hash(("flame", seed)))
    at = np.asarray(at, float)
    for i, (k, st) in enumerate(((1.0, "flame_out"), (0.72, "flame_mid"), (0.45, "flame_core"))):
        s = size * k
        cbox(b, at + (0, s * 0.35, 0), (s * 0.8, s * 1.25, s * 0.8), st,
             rot=(rng.uniform(-12, 12), 45.0 * (i % 2) + rng.uniform(-8, 8), rng.uniform(-12, 12)), uv=10,
             tags=("noao",))
    for j in range(3):                                 # 先の舌
        a = rng.uniform(0, 2 * math.pi)
        tip = at + (math.cos(a) * size * 0.25, size * (1.15 + 0.25 * j), math.sin(a) * size * 0.25)
        cbox(b, tip, (size * 0.3, size * 0.55, size * 0.3), "flame_out", rot=(rng.uniform(-20, 20), 45, 0), uv=10,
             tags=("noao",))


def spark(b, at, size: float):
    """導火線の火花: 白熱の芯と放射する短い筋（glow）。"""
    at = np.asarray(at, float)
    cbox(b, at, (size, size, size), "spark_core", rot=(45, 45, 0), uv=12, tags=("noao",))
    for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1), (0.7, 0.7, 0), (-0.7, 0.7, 0)):
        d = np.asarray(d, float)
        beam(b, at + d * size * 0.3, at + d * size * 1.25, size * 0.16, size * 0.16, "spark", uv=12, tags=("noao",))


def _flame_styles(book: WC.Stylebook) -> None:
    book.raw("flame_out", NP.style("glow", base=(255, 116, 28)))
    book.raw("flame_mid", NP.style("glow", base=(255, 170, 54)))
    book.raw("flame_core", NP.style("glow", base=(255, 236, 150)))
    book.raw("spark_core", NP.style("glow", base=(255, 246, 210)))
    book.raw("spark", NP.style("glow", base=(255, 190, 70)))


@builder("molotov")
def b_molotov(p):
    """火炎瓶: 茶色い瓶（底・胴・肩・首・口）、ちぎれたラベル、口に詰めて垂れた布、燃える炎。"""
    wm = ProjModel("molotov", uv=7)
    b = wm.root
    rod(b, (0, 0, 2.5), (0, 0, -0.5), 1.9, "glass", uv=7)            # 胴
    rod(b, (0, 0, 2.7), (0, 0, 2.35), 1.7, "glass_dark", uv=8)       # 底の厚み
    rod(b, (0, 0, -0.45), (0, 0, -1.15), 1.35, "glass", uv=8)        # 肩
    rod(b, (0, 0, -1.1), (0, 0, -2.5), 0.72, "glass", uv=9)          # 首
    band(b, (0, 0, -2.42), (0, 0, 1), 0.86, 0.22, "glass_dark", uv=12)  # 口の輪
    # ラベル（胴の片側に、端がめくれた紙）
    band(b, (0, 0, 1.15), (0, 0, 1), 1.98, 1.3, "label", uv=10)
    beam(b, (0.62, 0.86, 0.45), (0.95, 0.5, -0.05), 0.06, 0.6, "label", uv=12, tags=("ragged",))   # めくれた端
    # 口に詰めた布と、外へ垂れた端（燃えている先は黒く焦げる）
    rod(b, (0, 0, -2.2), (0, 0.05, -3.1), 0.56, "rag", uv=10)
    rag(b, (0, 0.1, -3.0), 1.3, 0.55, "rag", hang=(0.2, -1.0, -0.35), strips=2, spread=0.22, seed=5, uv=10)
    cbox(b, (0, 0.18, -3.25), (0.62, 0.5, 0.42), "rag_burnt", rot=(10, 20, 0), uv=10)
    flame(b, (0, 0.45, -3.3), 1.05, seed=1)
    book = WC.Stylebook()
    book.add("glass", "glass_tinted", base=(118, 70, 22))
    book.add("glass_dark", "glass_tinted", base=(62, 36, 16))
    book.raw("label", NP.style("paper", base=(206, 190, 150), lines=False, dirt=0.5))
    book.add("rag", "cloth_rag", base=(150, 132, 104))
    book.raw("rag_burnt", NP.style("char", embers=0.6))
    _flame_styles(book)
    return wm, book, []


@builder("pipe_bomb")
def b_pipe_bomb(p):
    """パイプ爆弾: 亜鉛めっきの管、六角の端の蓋、ダクトテープで巻いた釘、導火線と火花。"""
    wm = ProjModel("pipe_bomb", uv=7)
    b = wm.root
    rod(b, (0, 0, 2.1), (0, 0, -2.1), 1.5, "pipe", uv=7)
    for s in (-1, 1):
        rod(b, (0, 0, s * 1.9), (0, 0, s * 2.55), 1.78, "cap", uv=9)
        hex_prism(b, (0, 0, s * 2.42), (0, 0, 1), 1.95, 0.42, "cap", uv=10)
    # 釘の束をテープで巻き付け（管に沿って 6 本、テープの帯 2 本）
    for k in range(6):
        d = _radial(k, 6, phase=15.0)
        beam(b, d * 0.86 + (0, 0, 1.3), d * 0.86 + (0, 0, -1.3), 0.14, 0.14, "nail", up=tuple(d), uv=12)
    wrap(b, (0, 0, -1.1), (0, 0, -0.35), 2.0, "tape", pitch=0.38, tilt=6, seed=11, uv=9)
    wrap(b, (0, 0, 0.45), (0, 0, 1.2), 2.0, "tape", pitch=0.38, tilt=-6, seed=12, uv=9)
    # 導火線: 後ろの蓋の穴から曲がって上へ、先に火花
    polyline(b, [(0, 0.2, 2.6), (0, 0.55, 3.05), (0.1, 1.05, 3.25), (0.15, 1.5, 3.1)], 0.2, 0.2, "fuse",
             overlap=0.12, uv=14)
    spark(b, (0.15, 1.62, 3.05), 0.42)
    book = WC.Stylebook()
    book.add("pipe", "steel_worn", base=(150, 152, 146), dirt=0.45)
    book.add("cap", "iron_cast")
    book.add("nail", "steel_rusty", amount=0.5)
    book.add("tape", "tape_grey", dirt=0.6)
    book.add("fuse", "rope", base=(60, 58, 52))
    _flame_styles(book)
    return wm, book, []


@builder("firecracker")
def b_firecracker(p):
    """爆竹: 赤い紙の筒 7 本を麻ひもで束ね、編んだ導火線が 1 本にまとまって火花。"""
    wm = ProjModel("firecracker", uv=7)
    b = wm.root
    pts = [(0.0, 0.0)] + [(math.cos(math.radians(60 * k)) * 0.66, math.sin(math.radians(60 * k)) * 0.66)
                          for k in range(6)]
    for i, (x, y) in enumerate(pts):
        z0 = 1.6 + (0.12 if i % 2 else 0.0)
        beam(b, (x, y, z0), (x, y, -1.5), 0.62, 0.62, "paper_red" if i % 3 else "paper_red2", uv=8)
        cbox(b, (x, y, z0 + 0.06), (0.52, 0.52, 0.14), "paper_end", uv=12)     # 後ろの口
    for z in (-0.8, 0.9):
        band(b, (0, 0, z), (0, 0, 1), 2.06, 0.3, "twine", uv=10)
    # 前から出た細い導火線が 1 本に撚られる
    for (x, y) in pts[1::2]:
        beam(b, (x * 0.7, y * 0.7, -1.5), (0, 0.1, -2.15), 0.1, 0.1, "fuse", uv=14)
    polyline(b, [(0, 0.1, -2.1), (0, 0.25, -2.6), (0.05, 0.55, -2.95)], 0.16, 0.16, "fuse", overlap=0.1, uv=14)
    spark(b, (0.05, 0.62, -3.05), 0.36)
    book = WC.Stylebook()
    book.raw("paper_red", NP.style("paper", base=(176, 30, 26), lines=False, dirt=0.3))
    book.raw("paper_red2", NP.style("paper", base=(150, 22, 22), lines=False, dirt=0.35))
    book.raw("paper_end", NP.style("paper", base=(214, 190, 120), lines=False, dirt=0.4))
    book.add("twine", "rope", base=(170, 140, 90))
    book.add("fuse", "rope", base=(70, 62, 50))
    _flame_styles(book)
    return wm, book, []


@builder("uv_flare")
def b_uv_flare(p):
    """UV 発煙筒: 白い樹脂の筒、黒い擦り蓋、帯のラベル、先の紫外線の光（glow）と光の輪。"""
    wm = ProjModel("uv_flare", uv=8)
    b = wm.root
    rod(b, (0, 0, 2.2), (0, 0, -1.4), 1.0, "tube", uv=8)
    rod(b, (0, 0, 2.15), (0, 0, 2.75), 1.12, "cap", uv=10)          # 擦り蓋
    band(b, (0, 0, 2.55), (0, 0, 1), 1.18, 0.18, "cap_ring", uv=12)
    band(b, (0, 0, 0.6), (0, 0, 1), 1.06, 0.9, "label", uv=10)
    band(b, (0, 0, -0.35), (0, 0, 1), 1.06, 0.16, "stripe", uv=12)
    # 先: 燃える頭（紫の光）と、その手前のガラスの輪
    rod(b, (0, 0, -1.35), (0, 0, -2.35), 1.0, "uv", uv=10)
    rod(b, (0, 0, -2.3), (0, 0, -2.6), 0.7, "uv_hot", uv=12)
    band(b, (0, 0, -1.4), (0, 0, 1), 1.12, 0.16, "cap_ring", uv=12)
    book = WC.Stylebook()
    book.add("tube", "plastic_white", dirt=0.4)
    book.add("cap", "plastic_black")
    book.add("cap_ring", "plastic_black", wear=0.6)
    book.raw("label", NP.style("paper", base=(70, 40, 120), lines=False, dirt=0.3))
    book.add("stripe", "plastic_yellow")
    book.raw("uv", NP.style("glow", base=(168, 84, 255)))
    book.raw("uv_hot", NP.style("glow", base=(232, 200, 255)))
    return wm, book, []


# ===========================================================================
#  ゾンビの弾（酸の唾・投げた瓦礫）
# ===========================================================================
@builder("spit")
def b_spit(p):
    """酸の唾: 黄緑の泡立った塊（ゆがんだ箱の重ね）、表面の光る泡、後ろへ垂れて光る酸の糸。"""
    wm = ProjModel("spit", uv=8)
    b = wm.root
    rng = random.Random(stable_hash("spit"))
    for i, (c, s) in enumerate((((0, 0, 0), (2.0, 1.8, 2.4)), ((0.35, 0.25, 0.4), (1.5, 1.5, 1.7)),
                                ((-0.4, -0.15, -0.3), (1.4, 1.3, 1.6)), ((0.05, 0.45, -0.6), (1.1, 1.0, 1.2)),
                                ((0.1, -0.5, 0.7), (1.2, 0.9, 1.3)))):
        cbox(b, c, s, "acid", rot=(rng.uniform(-25, 25), rng.uniform(-35, 35), rng.uniform(-25, 25)), uv=8)
    for k in range(7):                                  # 表面の光る泡
        a, e = rng.uniform(0, 2 * math.pi), rng.uniform(-0.6, 0.8)
        r = 1.0 + rng.uniform(0.0, 0.15)
        c = (math.cos(a) * math.cos(e) * r, math.sin(e) * r * 0.9, math.sin(a) * math.cos(e) * r * 1.1)
        s = rng.uniform(0.28, 0.5)
        cbox(b, c, (s, s, s), "bubble", rot=(45, 45, 0), uv=12, tags=("noao",))
    # 後ろへ伸びる糸（光る酸）
    polyline(b, [(0.1, -0.2, 1.0), (0.15, -0.45, 1.9), (0.05, -0.85, 2.6), (0.0, -1.3, 3.0)],
             [0.5, 0.36, 0.22], [0.5, 0.36, 0.22], "drip", overlap=0.15, uv=12)
    polyline(b, [(-0.4, 0.3, 0.9), (-0.55, 0.25, 1.7), (-0.6, 0.0, 2.2)], [0.34, 0.2], [0.34, 0.2], "drip",
             overlap=0.12, uv=12)
    book = WC.Stylebook()
    book.raw("acid", NP.style("fungus", base=(124, 156, 44), alt=(214, 236, 120), glow_spots=0.3,
                              glow_colour=(170, 255, 80), wet=0.8))
    book.raw("bubble", NP.style("blood", blood_kind="acid"))
    book.raw("drip", NP.style("blood", blood_kind="acid"))
    return wm, book, []


@builder("debris")
def b_debris(p):
    """投げた瓦礫: 割れたコンクリの塊（欠けた角）、上に張り付いたアスファルトの層、折れて飛び出た鉄筋 2 本。"""
    wm = ProjModel("debris", uv=4)
    b = wm.root
    rng = random.Random(stable_hash("debris"))
    cbox(b, (0, 0, 0), (9.0, 5.2, 7.4), "concrete", uv=4)
    for (c, s, r) in ((((3.6, 1.8, 2.8)), (3.2, 2.4, 2.6), (20, 35, 15)),       # 欠けた角（斜めに削れた塊）
                      (((-3.9, -1.6, -2.6)), (2.8, 2.6, 3.0), (-25, 20, 30)),
                      (((-3.4, 2.0, 2.9)), (2.6, 2.0, 2.2), (35, -20, -10)),
                      (((2.4, -2.0, -3.2)), (3.6, 2.2, 2.4), (-15, -30, 20))):
        cbox(b, c, s, "concrete_dark", rot=r, uv=4)
    for k in range(5):                                  # 割れ口の小さな欠片
        c = (rng.uniform(-4.2, 4.2), rng.uniform(-2.6, -1.6), rng.uniform(-3.4, 3.4))
        s = rng.uniform(0.8, 1.6)
        cbox(b, c, (s, s * 0.7, s), "concrete", rot=(rng.uniform(-40, 40), rng.uniform(0, 90), rng.uniform(-40, 40)),
             uv=5)
    # 上のアスファルト（少し小さく、端が欠ける）
    cbox(b, (0.4, 3.2, 0.2), (7.6, 1.4, 6.4), "asphalt", rot=(2, 6, -3), uv=4)
    cbox(b, (-2.6, 3.0, -2.1), (2.4, 1.2, 2.2), "asphalt", rot=(-8, 25, 6), uv=5)
    # 鉄筋: 片方はまっすぐ横へ、もう片方は上へ曲がる
    rod(b, (1.6, -0.6, 1.0), (1.9, -0.9, 8.0), 0.72, "rebar", uv=6, fx={"rebar": 0.6})
    polyline(b, [(-2.2, 0.8, -1.6), (-2.6, 2.6, -2.4), (-3.0, 5.6, -2.2), (-2.4, 7.4, -1.2)], 0.66, 0.66, "rebar",
             overlap=0.2, uv=6, fx={"rebar": 0.6})
    book = WC.Stylebook()
    book.add("concrete", "concrete", dirt=0.45)
    book.add("concrete_dark", "concrete_dark", dirt=0.5)
    book.raw("asphalt", NP.style("asphalt", base=(52, 52, 56), cracks=0.7))
    book.add("rebar", "rebar")
    return wm, book, [WC.blood_zone((-5, -3, -4), (5, 0, 4), 0.25, "dry")]


# ===========================================================================
#  書き出し・確認
# ===========================================================================
def build(p) -> Tuple[ProjModel, WC.Stylebook, list]:
    key = p["key"]
    if key not in BUILDERS:
        raise KeyError(f"飛び道具 {key} の形が無い（nr_proj_models.BUILDERS に足す）")
    wm, book, blood = BUILDERS[key](p)
    hb = list(p.get("hitbox") or (0.25, 0.25))
    lift(wm, hb[1] * 16.0 / 2.0)
    if wm.cube_count > MAX_CUBES:
        raise ValueError(f"{key}: キューブ {wm.cube_count} 個（上限 {MAX_CUBES}）")
    wm.pack()
    return wm, book, blood


def texture_has_glow(path: str) -> Optional[bool]:
    """書いたテクスチャに発光の画素（0 < α < 255）があるか。無ければ None。"""
    if not os.path.exists(path):
        return None
    a = np.asarray(Image.open(path).convert("RGBA"), np.uint8)[..., 3]
    return bool(((a > 0) & (a < 255)).any())


def write_all(geo_dir: str, tex_dir: str, sheet_dir: Optional[str] = None) -> Dict[str, dict]:
    """全部の飛び道具のジオメトリとテクスチャを書く。{key: {cubes, tex, glow, geo, png}}。"""
    out: Dict[str, dict] = {}
    shots = []
    for p in S.ALL_PROJECTILES:
        key = p["key"]
        wm, book, blood = build(p)
        tex = WC.texture(wm, book, seed=stable_hash(("proj", key)) % 100000, blood=blood)
        gp = os.path.join(geo_dir, f"{key}.geo.json")
        tp = os.path.join(tex_dir, f"{key}.png")
        write_geometry(gp, wm.model)
        NP.save_png(tex, tp, quantize=True)
        a = np.asarray(tex, np.uint8)[..., 3]
        out[key] = {"cubes": wm.cube_count, "tex": (wm.model.tex_w, wm.model.tex_h),
                    "glow": bool(((a > 0) & (a < 255)).any()), "geo": gp, "png": tp}
        if sheet_dir:
            shots.append((key, wm, tex))
    if sheet_dir:
        contact_sheet(shots, os.path.join(sheet_dir, "projectiles.png"))
    return out


def contact_sheet(shots, path: str) -> str:
    """飛び道具ごとに 3 方向（斜め・横・上）を 1 枚に。"""
    items = []
    for key, wm, tex in shots:
        views = []
        for view in ("three_quarter", "right", (0.0, 89.0)):
            views.append(WC.render_model(wm, tex, view=view, size=(220, 170), ss=2))
        w = sum(v.size[0] for v in views)
        row = Image.new("RGB", (w, 170), (30, 31, 36))
        x = 0
        for v in views:
            row.paste(v.convert("RGB"), (x, 0))
            x += v.size[0]
        items.append((f"{key}  {wm.cube_count}c  {wm.model.tex_w}x{wm.model.tex_h}", row))
    img = WC.contact_sheet(items, cols=2, title="NIGHT RUNNER — 飛び道具（斜め / 横 / 上）")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


if __name__ == "__main__":
    import tempfile
    d = tempfile.mkdtemp(prefix="nr_proj_")
    res = write_all(os.path.join(d, "geo"), os.path.join(d, "tex"), sheet_dir=d)
    for k, r in res.items():
        print(k, r["cubes"], r["tex"], "glow" if r["glow"] else "")
    print(os.path.join(d, "projectiles.png"))
