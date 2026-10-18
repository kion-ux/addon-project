# -*- coding: utf-8 -*-
"""アストロ・ナノギア — 生成スクリプト共通のパス・定数・ジオメトリ補助。

座標: 16 単位 = 1 ブロック、プレイヤーは -Z が正面、右手が -X、+Y が上。
回転: **ここの補助が受け取る / 書き出す rotation は全て統合版の規則そのまま**
      （tools/hyperdim/hd_space.py: R = Rz(-rz)·Ry(ry)·Rx(-rx)、X→Y→Z の順）。
        * rx が正 … 上端が前（-Z）へ倒れる（下端は後ろへ）。腕なら負の rx で前へ上がる
        * ry が正 … 前（-Z）を向いていた面が右（-X）を向く
        * rz が正 … 上端が右（-X）へ倒れる（右腕なら外へ開く）
      hyperdim の beam/polyline/fill_tri_yz は旧プレビューの規則で角度を出すので、
      ここでは統合版の規則で解き直した版を同じ名前で提供する（形の意味は同じ）。

ジオメトリ補助（どれも作ったキューブを返す。リストのものはリスト）:
  box(bone, origin, size, style, **kw)            原点と大きさ
  cbox(bone, centre, size, style, **kw)           中心と大きさ（rotation は中心まわり）
  rbox(bone, centre, size, style, rot, pivot=None) 中心＋回転（統合版の角度）
  plate(bone, centre, size, style, tilt=(rx,ry,rz)) rbox の別名（傾けた装甲板）
  beam(bone, p0, p1, w, h, style, roll=0)          p0→p1 の角柱（局所 X 幅 w・Y 高さ h）
  polyline(bone, pts, widths, heights, style)      点列に沿った角柱の列（先細り可）
  octa(bone, centre, w, length, style, axis)       八角柱（箱＋45°の箱）
  chamfer(bone, centre, size, style, cut, axis)    角を落とした箱（2 個の箱で段々の面取り）
  bevel(bone, centre, size, style, cut, axis)      本当の 45° 面取り（6 個: 十字＋4 本の稜）
  ring(bone, centre, radius, n, seg, style, axis)  輪をセグメントで（axis 方向が輪の軸）
  fill_tri_yz(bone, apex, a, b, x_w, layer_h, style) YZ 平面の三角形を角柱で埋める
"""
from __future__ import annotations

import json
import math
import os
import sys
from typing import Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
HD = os.path.join(TOOLS, "hyperdim")
for _p in (HD, TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

import hd_common as _hd  # noqa: E402
from hd_space import beam_angles, euler, rot  # noqa: E402
from mcmodel import Cube, Model, Bone  # noqa: E402,F401
from astro_data import NS, PLANETS, PLANET_KEYS, TRANSFORM, ASSEMBLE_ORDER  # noqa: E402,F401

BP = os.path.join(ROOT, "packs", "astro_BP")
RP = os.path.join(ROOT, "packs", "astro_RP")
SCRATCH = os.environ.get("ASTRO_SCRATCH", os.path.join(ROOT, "build_preview", "astro"))
DOCS = os.path.join(ROOT, "docs", "astro")
PLANETS_DIR = os.path.join(HERE, "planets")

GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", "astro")
ATT_DIR = os.path.join(RP, "attachables")
ANIM_DIR = os.path.join(RP, "animations")
CTRL_DIR = os.path.join(RP, "animation_controllers")

lerp = _hd.lerp
arc_points = _hd.arc_points


def write_json(path: str, doc) -> None:
    """UTF-8・インデント 2・末尾改行。ディレクトリは作る。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def r3(v):
    return [round(float(x), 3) for x in v]


# ---------------------------------------------------------------------------
#  基本の箱
# ---------------------------------------------------------------------------
def box(bone, origin, size, style, **kw) -> Cube:
    return bone.add(Cube(origin, size, style, **kw))


def cbox(bone, centre, size, style, **kw) -> Cube:
    """中心と大きさで置く箱。rotation（統合版の角度）は中心まわり（pivot を渡せばそこ）。"""
    o = [centre[i] - size[i] / 2 for i in range(3)]
    if kw.get("rotation") is not None:
        r = [round(float(a), 2) for a in kw["rotation"]]
        if not any(abs(a) > 1e-3 for a in r):
            kw.pop("rotation")
            kw.pop("pivot", None)
        else:
            kw["rotation"] = r
            if kw.get("pivot") is None:
                kw["pivot"] = r3(centre)
    return bone.add(Cube(o, size, style, **kw))


def rbox(bone, centre, size, style, rot=(0, 0, 0), pivot=None, **kw) -> Cube:
    """中心・大きさ・回転（統合版の rotation そのまま）。pivot 省略で中心まわり。"""
    return cbox(bone, centre, size, style, rotation=rot, pivot=pivot, **kw)


def plate(bone, centre, size, style, tilt=(0, 0, 0), **kw) -> Cube:
    """傾けた装甲板。tilt は統合版の rotation（rx 正 = 上端が前へ / rz 正 = 上端が右(-X)へ）。"""
    return rbox(bone, centre, size, style, rot=tilt, **kw)


def mat_cube(bone, centre, size, style, R, **kw) -> Cube:
    """任意の回転行列 R（モデル空間）で置く箱。統合版のオイラー角に分解して書く。"""
    return rbox(bone, centre, size, style, rot=euler(np.asarray(R, float)), **kw)


# ---------------------------------------------------------------------------
#  向きのある部品
# ---------------------------------------------------------------------------
def _Rz(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def frame_to(d, roll=0.0):
    """局所 -Z を方向 d へ向け、局所 X を水平に保つ回転行列（roll は自分の軸まわり、度）。"""
    if math.sqrt(sum(float(v) * float(v) for v in d)) < 1e-9:
        raise ValueError("zero direction")
    rx, ry = beam_angles(d)          # rot(rx, ry, 0) @ (0,0,-1) = d
    return rot(rx, ry, 0) @ _Rz(roll)


def _check_frame():
    for d in ((0, 0, -1), (1, 0, 0), (0, 1, 0.2), (0.3, -0.8, 0.5), (0, -1, 0.001)):
        M = frame_to(d)
        v = M @ np.array([0, 0, -1.0])
        dn = np.asarray(d, float) / np.linalg.norm(d)
        assert np.allclose(v, dn, atol=1e-6), (d, v)


_check_frame()


def beam(bone, p0: Sequence[float], p1: Sequence[float], w: float, h: float,
         style: str, roll: float = 0.0, extend: float = 0.0, **kw) -> Cube:
    """p0 から p1 へ伸びる角柱（統合版の回転で解く）。局所 X 幅 w（水平）・Y 高さ h。
    roll は自分の軸まわりの回転（度）。extend は長さの足し（継ぎ目の重なり）。"""
    d = np.subtract(p1, p0).astype(float)
    L = float(np.linalg.norm(d))
    if L < 1e-6:
        raise ValueError("zero-length beam")
    centre = (np.asarray(p0, float) + np.asarray(p1, float)) / 2
    R = frame_to(d, roll)
    return mat_cube(bone, centre, (w, h, L + extend), style, R, **kw)


def polyline(bone, pts, widths, heights, style, roll=0.0, overlap=0.25, **kw):
    """点列に沿って角柱を繋げる。幅・高さ・roll は区間ごとのリストでも可（先細り）。"""
    out = []
    for i in range(len(pts) - 1):
        w = widths[i] if isinstance(widths, (list, tuple)) else widths
        h = heights[i] if isinstance(heights, (list, tuple)) else heights
        r = roll[i] if isinstance(roll, (list, tuple)) else roll
        out.append(beam(bone, pts[i], pts[i + 1], w, h, style, roll=r, extend=overlap, **kw))
    return out


def fill_tri_yz(bone, apex, base_a, base_b, x_w, layer_h, style, **kw):
    """hd_common.fill_tri_yz と同じ形を、統合版の回転に直して置く。"""
    from preview import rot_matrix as designed      # 旧規則（hd_common.beam が使う）
    n0 = len(bone.cubes)
    _hd.fill_tri_yz(bone, apex, base_a, base_b, x_w, layer_h, style, **kw)
    for c in bone.cubes[n0:]:
        if c.rotation:
            c.rotation = list(euler(designed(*c.rotation)))
    return bone.cubes[n0:]


AX = {"x": 0, "y": 1, "z": 2}


def _axis_rot(axis, a):
    return {"x": (a, 0, 0), "y": (0, a, 0), "z": (0, 0, a)}[axis]


def octa(bone, centre, w, length, style, axis="z", style2=None, **kw):
    """八角柱（箱 + 軸まわりに 45° 回した箱）。柄・ノズル・関節の円盤に。"""
    size = [w, w, w]
    size[AX[axis]] = length
    a = cbox(bone, centre, size, style, **kw)
    s2 = [v * 0.94 if i != AX[axis] else v for i, v in enumerate(size)]
    b = rbox(bone, centre, s2, style2 or style, rot=_axis_rot(axis, 45), **kw)
    return [a, b]


def chamfer(bone, centre, size, style, cut=0.5, axis="z", **kw):
    """角を落とした箱（axis に沿う 4 本の稜を cut だけ段々に落とす。2 個）。"""
    i = AX[axis]
    j, k = [n for n in range(3) if n != i]
    s1 = list(size)
    s1[j] -= 2 * cut
    s2 = list(size)
    s2[k] -= 2 * cut
    return [cbox(bone, centre, s1, style, **kw), cbox(bone, centre, s2, style, **kw)]


def bevel(bone, centre, size, style, cut=0.5, axis="z", edge_style=None, **kw):
    """45° の面取り（axis に沿う 4 本の稜）。十字の 2 個 + 稜の 4 本 = 6 個。
    edge_style を渡すと稜だけ別の塗り（金の縁取りなど）。"""
    i = AX[axis]
    j, k = [n for n in range(3) if n != i]
    out = chamfer(bone, centre, size, style, cut, axis, **kw)
    s = cut * math.sqrt(2)
    for sj in (-1, 1):
        for sk in (-1, 1):
            c = list(centre)
            c[j] += sj * (size[j] / 2 - cut)
            c[k] += sk * (size[k] / 2 - cut)
            es = [s, s, s]
            es[i] = size[i]
            out.append(rbox(bone, c, es, edge_style or style, rot=_axis_rot(axis, 45), **kw))
    return out


def ring(bone, centre, radius, n, seg, style, axis="y", phase=0.0, a0=0.0, a1=360.0,
         styles=None, **kw):
    """軸 axis まわりの輪を n 個のセグメントで。seg = (接線方向の長さ, 半径方向の厚み,
    軸方向の幅)。接線長を省くと隙間なく繋がる長さ。styles を渡すと交互に塗る。"""
    out = []
    full = abs(a1 - a0) >= 359.9
    count = n if full else n + 1
    step = (a1 - a0) / (n if full else max(1, n))
    tl = seg[0] if seg[0] else 2 * radius * math.tan(math.radians(abs(step) / 2)) + 0.05
    for i in range(count):
        a = a0 + phase + i * step
        t = math.radians(a)
        st = styles[i % len(styles)] if styles else style
        if axis == "y":      # 水平の輪（XZ 平面）。a=0 で -Z（前）、a=90 で -X（右）
            p = (centre[0] - radius * math.sin(t), centre[1], centre[2] - radius * math.cos(t))
            out.append(rbox(bone, p, (tl, seg[2], seg[1]), st, rot=(0, a, 0), **kw))
        elif axis == "z":    # 正面向きの輪（XY 平面）。a=0 で上、a=90 で -X
            p = (centre[0] - radius * math.sin(t), centre[1] + radius * math.cos(t), centre[2])
            out.append(rbox(bone, p, (tl, seg[1], seg[2]), st, rot=(0, 0, a), **kw))
        else:                # 側面の輪（YZ 平面）。a=0 で上、a=90 で -Z
            p = (centre[0], centre[1] + radius * math.cos(t), centre[2] - radius * math.sin(t))
            out.append(rbox(bone, p, (seg[2], seg[1], tl), st, rot=(a, 0, 0), **kw))
    return out


def tri_fan(bone, apex, pts, w, style, **kw):
    """apex から点列への角柱の扇（羽根・ヒレ・光輪のトゲ）。"""
    return [beam(bone, apex, p, w, w, style, **kw) for p in pts]


# ---------------------------------------------------------------------------
#  幾何の検算（被覆検査・レンダラが使う）
# ---------------------------------------------------------------------------
def cube_matrix(c) -> np.ndarray:
    """キューブの回転（pivot まわり）を 4x4 行列で。回転なしは単位行列。"""
    M = np.eye(4)
    if c.get("rotation") if isinstance(c, dict) else c.rotation:
        r = c["rotation"] if isinstance(c, dict) else c.rotation
        o = np.array(c["origin"] if isinstance(c, dict) else c.origin, float)
        s = np.array(c["size"] if isinstance(c, dict) else c.size, float)
        p = c.get("pivot") if isinstance(c, dict) else c.pivot
        p = np.array(p if p is not None else o + s / 2, float)
        T = np.eye(4)
        T[:3, 3] = p
        Ti = np.eye(4)
        Ti[:3, 3] = -p
        Rm = np.eye(4)
        Rm[:3, :3] = rot(*r)
        M = T @ Rm @ Ti
    return M
