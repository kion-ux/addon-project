# -*- coding: utf-8 -*-
"""アストロ・ナノギア — 生成スクリプト共通のパス・定数・ジオメトリ補助。

座標: 16 単位 = 1 ブロック、プレイヤーは -Z が正面、右手が -X、+Y が上。
回転: **ここの補助が受け取る / 書き出す rotation は全て統合版の規則そのまま**
      （tools/hyperdim/hd_space.py: R = Rz(-rz)·Ry(ry)·Rx(-rx)、X→Y→Z の順）。
        * rx が正 … 上端が前（-Z）へ倒れる（下端は後ろへ）。腕なら負の rx で前へ上がる。
                    負の rx は面が前上を向く（つま先・斜めの装甲）
        * ry が正 … 前（-Z）を向いていた面が右（-X）を向く（+X の端が前へ出る）
        * rz が正 … 上端が左（+X）へ、下端が右（-X）へ。右側の部品なら「下端が外へ開く」
                    （スカート・肩当ての垂れ）。横板の外（-X）の端を下げたい時は rz を負に
      右側（-X）だけ作って鏡映すれば、左は (rx, -ry, -rz) に自動で直る（astro_suit.mirror_all）。
      hyperdim の beam/polyline/fill_tri_yz は旧プレビューの規則で角度を出すので、
      ここでは統合版の規則で解き直した版を同じ名前で提供する（形の意味は同じ）。

ジオメトリ補助（どれも作ったキューブを返す。リストのものはリスト）:
  box(bone, origin, size, style, **kw)            原点と大きさ
  cbox(bone, centre, size, style, **kw)           中心と大きさ（rotation は中心まわり）
  rbox(bone, centre, size, style, rot, pivot=None) 中心＋回転（統合版の角度）
  plate(bone, centre, size, style, tilt=(rx,ry,rz)) rbox の別名（傾けた装甲板）
  surface(cube, face, a, b, lift)                  キューブの面の上の点と法線（回転込み）
  stick(bone, cube, face, a, b, size, style, lift) 面に貼る小箱（同じ傾きで。ボルト・宝玉・板の重ね）
  line_on(bone, cube, face, ab0, ab1, w, t, style) 面の上を走る線（発光ライン・縁取り）
  beam(bone, p0, p1, w, h, style, roll=0)          p0→p1 の角柱（局所 X 幅 w・Y 高さ h）
  polyline(bone, pts, widths, heights, style)      点列に沿った角柱の列（先細り可）
  octa(bone, centre, w, length, style, axis)       八角柱（箱＋45°の箱）
  chamfer(bone, centre, size, style, cut, axis)    角を落とした箱（2 個の箱で段々の面取り）
  bevel(bone, centre, size, style, cut, axis)      本当の 45° 面取り（6 個: 十字＋4 本の稜）
  ring(bone, centre, radius, n, seg, style, axis)  輪をセグメントで（axis 方向が輪の軸）
  taper(bone, p0, p1, w0, w1, n, style)            先細りの段（炎・トゲ・角。45° の段も重ねて丸く）
  fill_tri_yz(bone, apex, a, b, x_w, layer_h, style) YZ 平面の三角形を角柱で埋める

細かい部品（v1.1。ファイルの末尾。astro_suit からも同じ名前で使える）:
  rod(bone, p0, p1, w, style, sides=8)             p0→p1 の丸棒（八角柱）
  ball(bone, centre, r, style, style2=None)        球関節（4 個）
  piston(bone, p0, p1, r=0.42, style, rod_style, cap_style, split=0.55)  油圧シリンダー（筒+ロッド+締め輪+目）
  cable(bone, pts, w=0.26, style, sag=0, seg=0.8, rib=None)  垂れるケーブル・蛇腹のホース
  rivets(bone, cube, face, n, edge="bottom"|"top"|"left"|"right"|"border", margin, size, style, line=)
  vents(bone, cube, face, n, box=(a0,b0,a1,b1), axis="h"|"v", w, style="vent", rim=None)  排気スリット
  layered_plate(bone, centre, size, style, top, rot, face, inset, trim, trim_edge, rivet, n_rivets)
  joint_drum(bone, centre, r, length, axis, style, cap, hub, glow, caps=(-1, 1), bolts=0)  関節ドラム
  finger_chain(bone, pts, w, h, style, knuckle, tip=None)  指の関節の連なり
  greebles(bone, cube, face, n, seed, styles, size, h, region)  パネルの小物
  sensor(bone, centre, size, style="glow", bezel="dark", axis="z", facing=-1)  センサーの灯り
  mx(p)                                            点の X を反転
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
        r = [round(float(a), 2) + 0.0 for a in kw["rotation"]]
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


# ---------------------------------------------------------------------------
#  面に貼る（傾いた板の上に、同じ傾きで部品・線を載せる）
# ---------------------------------------------------------------------------
# 面の中の 2 軸（a, b）。側面は b が高さ（Y）。a, b は 0..1（面の端から端）
FACE_AXES = {"north": (0, 1, 2, -1), "south": (0, 1, 2, 1), "east": (2, 1, 0, 1),
             "west": (2, 1, 0, -1), "up": (0, 2, 1, 1), "down": (0, 2, 1, -1)}


def cube_rot(c) -> np.ndarray:
    return rot(*c.rotation) if c.rotation else np.eye(3)


def cube_pivot(c) -> np.ndarray:
    if c.pivot is not None:
        return np.array(c.pivot, float)
    return np.array(c.origin, float) + np.array(c.size, float) / 2


def surface(c, face, a=0.5, b=0.5, lift=0.0):
    """キューブ c の面 face 上の点（a, b は面の 2 軸の 0..1。north/south は (x, y)、
    east/west は (z, y)、up/down は (x, z)）と外向きの法線（モデル空間）。lift で法線方向に浮かす。"""
    ia, ib, inn, sg = FACE_AXES[face]
    o = np.array(c.origin, float) - c.inflate
    s = np.array(c.size, float) + 2 * c.inflate
    q = o.copy()
    q[ia] += s[ia] * a
    q[ib] += s[ib] * b
    q[inn] += s[inn] if sg > 0 else 0.0
    n = np.zeros(3)
    n[inn] = sg
    R = cube_rot(c)
    p = cube_pivot(c)
    nn = R @ n
    return R @ (q - p) + p + nn * lift, nn


def stick(bone, c, face, a, b, size, style, lift=0.0, spin=0.0, sink=0.0, **kw) -> Cube:
    """キューブ c の面 face の (a, b) に、同じ傾きの小箱を貼る。size = (面の a 方向, b 方向,
    厚み)。sink で面へ沈める（隙間なく重ねる）。spin は面の法線まわりの回転（度）。"""
    ia, ib, inn, sg = FACE_AXES[face]
    pt, n = surface(c, face, a, b)
    loc = [0.0, 0.0, 0.0]
    loc[ia], loc[ib], loc[inn] = size[0], size[1], size[2]
    centre = pt + n * (lift + size[2] / 2 - sink)
    R = cube_rot(c)
    if spin:
        axis = np.zeros(3)
        axis[inn] = 1.0
        R = R @ _axis_matrix(axis, spin * sg)
    return mat_cube(bone, centre, loc, style, R, **kw)


def _axis_matrix(axis, deg):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * (K @ K)


def line_on(bone, c, face, ab0, ab1, w, t, style, lift=0.0, sink=0.08, extend=0.0, **kw):
    """キューブ c の面の上を (a0,b0) から (a1,b1) へ走る帯（幅 w・厚み t）。発光ライン・縁取りに。"""
    p0, n = surface(c, face, *ab0)
    p1, _ = surface(c, face, *ab1)
    return line3(bone, p0, p1, n, w, t, style, lift=lift, sink=sink, extend=extend, **kw)


def line3(bone, p0, p1, normal, w, t, style, lift=0.0, sink=0.08, extend=0.0, **kw) -> Cube:
    """p0→p1 の帯を、厚みの向きを normal に合わせて置く（面に沿う線）。"""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    L = float(np.linalg.norm(d))
    z = -d / L
    y = np.asarray(normal, float)
    y = y - z * float(np.dot(y, z))
    y /= np.linalg.norm(y)
    x = np.cross(y, z)
    R = np.column_stack([x, y, z])
    centre = (p0 + p1) / 2 + y * (lift + t / 2 - sink)
    return mat_cube(bone, centre, (w, t, L + extend), style, R, **kw)


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


# 重ねた部品の端の面を同じ平面に置かないためのずらし量（統合版は同一平面の面がちらつく）
ZF_INSET = 0.04

AX = {"x": 0, "y": 1, "z": 2}


def _axis_rot(axis, a):
    return {"x": (a, 0, 0), "y": (0, a, 0), "z": (0, 0, a)}[axis]


def _group(bone, parts, rot_=None, pivot=None, centre=None, **kw):
    """部品の組 [(中心, 大きさ, 局所の回転行列, スタイル)] を、組ごと rot_（統合版の角度）で
    pivot（省略で centre）まわりに回して置く。"""
    G = rot(*rot_) if rot_ is not None and any(abs(a) > 1e-6 for a in rot_) else np.eye(3)
    P = np.asarray(pivot if pivot is not None else centre, float)
    out = []
    for c, sz, R, st in parts:
        c2 = G @ (np.asarray(c, float) - P) + P
        out.append(mat_cube(bone, c2, sz, st, G @ R, **kw))
    return out


def octa(bone, centre, w, length, style, axis="z", style2=None, rot=None, pivot=None, **kw):
    """八角柱（箱 + 軸まわりに 45° 回した箱）。ノズル・関節の円盤・柄に。rot で組ごと傾ける。"""
    size = [w, w, w]
    size[AX[axis]] = length
    # 45° の箱は軸方向を少し短くして、端の面が同じ平面に重ならない（Z ファイトでちらつかない）ようにする
    s2 = [v * 0.94 if i != AX[axis] else v - 2 * ZF_INSET for i, v in enumerate(size)]
    r45 = globals()["rot"](*_axis_rot(axis, 45))
    return _group(bone, [(centre, size, np.eye(3), style), (centre, s2, r45, style2 or style)],
                  rot, pivot, centre, **kw)


def chamfer(bone, centre, size, style, cut=0.5, axis="z", rot=None, pivot=None, **kw):
    """角を落とした箱（axis に沿う 4 本の稜を cut だけ段々に落とす。2 個）。"""
    i = AX[axis]
    j, k = [n for n in range(3) if n != i]
    s1 = list(size)
    s1[j] -= 2 * cut
    s2 = list(size)
    s2[k] -= 2 * cut
    s2[i] -= 2 * ZF_INSET          # 端の面をずらす（Z ファイト防止）
    return _group(bone, [(centre, s1, np.eye(3), style), (centre, s2, np.eye(3), style)],
                  rot, pivot, centre, **kw)


def bevel(bone, centre, size, style, cut=0.5, axis="z", edge_style=None, rot=None, pivot=None,
          **kw):
    """45° の面取り（axis に沿う 4 本の稜）。十字の 2 個 + 稜の 4 本 = 6 個。
    edge_style で稜だけ別の塗り（金の縁取りなど）。rot で組ごと傾ける（pivot 省略で中心）。
    戻り値のリストの [0] は「a 方向に長い本体」、[1] は「b 方向に長い本体」。"""
    i = AX[axis]
    j, k = [n for n in range(3) if n != i]
    s1 = list(size)
    s1[j] -= 2 * cut
    s2 = list(size)
    s2[k] -= 2 * cut
    s2[i] -= 2 * ZF_INSET          # 重ねる部品の端の面を少しずつずらす（Z ファイト防止）
    parts = [(centre, s1, np.eye(3), style), (centre, s2, np.eye(3), style)]
    e = cut * math.sqrt(2)
    r45 = globals()["rot"](*_axis_rot(axis, 45))
    for sj in (-1, 1):
        for sk in (-1, 1):
            c = list(centre)
            c[j] += sj * (size[j] / 2 - cut)
            c[k] += sk * (size[k] / 2 - cut)
            es = [e, e, e]
            es[i] = size[i] - 4 * ZF_INSET
            parts.append((c, es, r45, edge_style or style))
    return _group(bone, parts, rot, pivot, centre, **kw)


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
            # rz = -a で局所 X が接線に沿う（rot の rz は Rz(-rz) として掛かる）
            out.append(rbox(bone, p, (tl, seg[1], seg[2]), st, rot=(0, 0, -a), **kw))
        else:                # 側面の輪（YZ 平面）。a=0 で上、a=90 で -Z
            p = (centre[0], centre[1] + radius * math.cos(t), centre[2] - radius * math.sin(t))
            out.append(rbox(bone, p, (seg[2], seg[1], tl), st, rot=(a, 0, 0), **kw))
    return out


def taper(bone, p0, p1, w0, w1, n, style, round_=True, style_r=None, **kw):
    """p0 から p1 へ先細りする角柱の段（炎・トゲ・角）。n 段、根元の幅 w0 → 先の幅 w1。
    round_=True で 45° 回した段も重ねて丸く見せる。"""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    out = []
    R = frame_to(p1 - p0)
    R45 = R @ _Rz(45)
    L = float(np.linalg.norm(p1 - p0))
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        w = w0 + (w1 - w0) * (t0 + t1) / 2
        seg = L / n * 1.15
        cen = p0 + (p1 - p0) * (t0 + t1) / 2
        out.append(mat_cube(bone, cen, (w, w, seg), style, R, **kw))
        if round_:
            out.append(mat_cube(bone, cen, (w * 0.92, w * 0.92, seg * 0.96), style_r or style,
                                R45, **kw))
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


# ===========================================================================
#  細かい部品（v1.1 の 7 頭身スーツ用。ウェポンでも使える）
#  どれも作ったキューブのリストを返す（stick 系の面の座標 (a, b) は surface() と同じ 0..1）
# ===========================================================================
MIN_PART = 0.15            # これより細い部品は作らない（DESIGN §4.3b）


def _v(p):
    return np.asarray(p, float)


def rod(bone, p0, p1, w, style, sides=8, style2=None, roll=0.0, extend=0.0, h=None, **kw):
    """p0→p1 の丸棒。sides=8 で八角柱（角柱 + 45° 回した角柱の 2 個）、4 で角柱 1 個。
    w は太さ（h を渡すと縦横を変えた楕円っぽい棒）。"""
    h = w if h is None else h
    out = [beam(bone, p0, p1, w, h, style, roll=roll, extend=extend, **kw)]
    if sides >= 8:
        out.append(beam(bone, p0, p1, w * 0.94, h * 0.94, style2 or style, roll=roll + 45.0,
                        extend=extend - 2 * ZF_INSET, **kw))
    return out


def ball(bone, centre, r, style, style2=None, **kw):
    """丸い球関節（4 個: 立方体 + 3 軸それぞれの 45° の棒）。肩・股関節・首の付け根に。"""
    c = _v(centre)
    s2 = style2 or style
    out = [cbox(bone, c, (1.62 * r, 1.62 * r, 1.62 * r), style, **kw)]
    out.append(rbox(bone, c, (2 * r, 1.16 * r, 1.16 * r), s2, rot=(45, 0, 0), **kw))
    out.append(rbox(bone, c, (1.16 * r, 2 * r - 0.04, 1.16 * r), s2, rot=(0, 45, 0), **kw))
    out.append(rbox(bone, c, (1.16 * r, 1.16 * r, 2 * r - 0.08), s2, rot=(0, 0, 45), **kw))
    return out


def piston(bone, p0, p1, r=0.42, style="frame", rod_style="chrome", cap_style="dark",
           split=0.55, rod_r=None, eyes=True, gland=True, sides=8, **kw):
    """油圧シリンダー: p0 側の太い筒（半径 r、全長の split まで）+ p1 側から差し込まれた細いロッド
    + 筒の口の締め輪（gland）+ 両端の取り付け目（eyes）。肘・膝・足首・首の後ろ・腹の脇に。
    伸び縮みに見せたい時は p0, p1 を関節の両側（別の部位）に置く。6〜8 個。"""
    p0, p1 = _v(p0), _v(p1)
    d = p1 - p0
    L = float(np.linalg.norm(d))
    if L < 0.6:
        raise ValueError("piston too short (< 0.6)")
    u = d / L
    rr = rod_r if rod_r is not None else max(MIN_PART / 2, r * 0.48)
    m = p0 + u * L * split
    out = []
    out += rod(bone, p0 + u * 0.1, m, 2 * r, style, sides=sides, **kw)
    out += rod(bone, m - u * 0.35, p1 - u * 0.05, 2 * rr, rod_style, sides=4, **kw)
    if gland:
        out += rod(bone, m - u * 0.16, m + u * 0.1, 2 * r * 1.2, cap_style, sides=sides, **kw)
    if eyes:
        R = frame_to(d)
        out.append(mat_cube(bone, p0, (2 * r * 1.15, 2 * r * 1.15, max(MIN_PART, 2 * r * 0.7)),
                            cap_style, R, **kw))
        out.append(mat_cube(bone, p1, (max(MIN_PART, 2 * rr * 1.7), max(MIN_PART, 2 * rr * 1.7),
                                       max(MIN_PART, 2 * rr * 1.2)), cap_style, R, **kw))
    return out


def _catmull(pts, n_per=8):
    """一様 Catmull-Rom で点列を細かく（端は複製）。"""
    P = [_v(p) for p in pts]
    if len(P) < 3:
        return P
    ext = [P[0] + (P[0] - P[1]) * 0.0] + P + [P[-1]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n_per):
            t = k / n_per
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


def cable(bone, pts, w=0.26, style="dark", sag=0.0, seg=0.8, h=None, rib=None, rib_every=2,
          rib_scale=1.45, **kw):
    """ケーブル・ホース: 点列を滑らかに通る細い角柱の列（1 区間 ≈ seg、継ぎ目は少し重ねる）。
    2 点だけなら sag ぶん下（-Y）へ垂れる（放物線）。3 点以上は Catmull-Rom で滑らかに通り、
    sag は各区間に足す。rib に塗りの名前を渡すと rib_every 区間ごとに太い輪（蛇腹）を付ける。
    1 区間が 1.0 以下になるので「細かい部品」に数えられる。"""
    P = [_v(p) for p in pts]
    if len(P) == 2:
        p0, p1 = P
        c = (p0 + p1) / 2 - np.array([0.0, 2.0 * sag, 0.0])
        dense = [(1 - t) ** 2 * p0 + 2 * (1 - t) * t * c + t * t * p1
                 for t in np.linspace(0, 1, 24)]
    else:
        dense = _catmull(P, 10)
        if sag:
            # 元の各区間に sag の垂れを足す（端点は動かさない）
            n_seg = len(P) - 1
            for i in range(len(dense)):
                s = i / max(1, len(dense) - 1) * n_seg
                f = s - math.floor(s)
                dense[i] = dense[i] - np.array([0.0, sag * 4 * f * (1 - f), 0.0])
    # 弧長で seg ごとに取り直す
    acc = [0.0]
    for i in range(1, len(dense)):
        acc.append(acc[-1] + float(np.linalg.norm(dense[i] - dense[i - 1])))
    total = acc[-1]
    if total < 1e-6:
        return []
    n = max(1, int(math.ceil(total / seg)))
    samples = []
    j = 0
    for k in range(n + 1):
        target = total * k / n
        while j < len(acc) - 2 and acc[j + 1] < target:
            j += 1
        span = (acc[j + 1] - acc[j]) or 1.0
        t = (target - acc[j]) / span
        samples.append(dense[j] + (dense[j + 1] - dense[j]) * t)
    h = w if h is None else h
    ov = min(w, h, 0.18) * 0.8
    out = []
    for i in range(len(samples) - 1):
        a, b = samples[i], samples[i + 1]
        if np.linalg.norm(b - a) < 1e-4:
            continue
        out.append(beam(bone, a, b, w, h, style, extend=ov, **kw))
        if rib and i % rib_every == rib_every - 1 and i < len(samples) - 2:
            out.append(mat_cube(bone, b, (w * rib_scale, h * rib_scale, max(MIN_PART, w * 0.6)),
                                rib, frame_to(samples[i + 2] - a), **kw))
    return out


def _face_dims(c, face):
    ia, ib, _inn, _sg = FACE_AXES[face]
    return c.size[ia] + 2 * c.inflate, c.size[ib] + 2 * c.inflate


def rivets(bone, c, face, n=4, edge="bottom", margin=0.3, size=0.26, h=0.16, style="silver",
           line=None, span=(0.14, 0.86), sink=0.06, **kw):
    """ボルト・リベットの列をキューブ c の面 face に打つ（面と同じ傾き）。
    edge: "bottom" / "top"（b 方向の端。側面なら下・上）/ "left" / "right"（a 方向の端）/ "border"（四辺）。
    margin は端からの距離（単位）、span は列の範囲（0..1）。line=((a0,b0),(a1,b1)) で自由な直線。
    size × size × h（h ≥ 0.15）。1 個 1 キューブの細かい部品。"""
    sa, sb = _face_dims(c, face)
    ma, mb = min(0.45, margin / max(sa, 1e-6)), min(0.45, margin / max(sb, 1e-6))
    pts = []
    if line is not None:
        (a0, b0), (a1, b1) = line
        pts = [(a0 + (a1 - a0) * i / max(1, n - 1), b0 + (b1 - b0) * i / max(1, n - 1))
               for i in range(n)]
    elif edge == "border":
        corners = [(ma, mb), (1 - ma, mb), (1 - ma, 1 - mb), (ma, 1 - mb)]
        per = max(0, (n - 4) // 4)
        for k in range(4):
            (a0, b0), (a1, b1) = corners[k], corners[(k + 1) % 4]
            for i in range(per + 1):
                t = i / (per + 1)
                pts.append((a0 + (a1 - a0) * t, b0 + (b1 - b0) * t))
    else:
        lo, hi = span
        ts = [lo + (hi - lo) * i / max(1, n - 1) for i in range(n)] if n > 1 else [0.5]
        for t in ts:
            if edge == "bottom":
                pts.append((t, mb))
            elif edge == "top":
                pts.append((t, 1 - mb))
            elif edge == "left":
                pts.append((ma, t))
            elif edge == "right":
                pts.append((1 - ma, t))
            else:
                raise ValueError(f"edge must be bottom/top/left/right/border, not {edge!r}")
    hh = max(MIN_PART, h)
    return [stick(bone, c, face, a, b, (size, size, hh), style, sink=sink, **kw) for a, b in pts]


def vents(bone, c, face, n=4, box=(0.15, 0.18, 0.85, 0.82), axis="h", w=0.2, depth=0.16,
          style="vent", rim=None, rim_w=0.16, sink=0.1, **kw):
    """排気スリット: 面 face の box=(a0,b0,a1,b1) の中に n 本の細い帯（axis "h" は a 方向に長い帯を
    b 方向へ並べる、"v" はその逆）。style は vent（奥が光る暗い溝）など。rim に塗りを渡すと枠も付ける。"""
    a0, b0, a1, b1 = box
    sa, sb = _face_dims(c, face)
    out = []
    dd = max(MIN_PART, depth)
    for i in range(n):
        t = (i + 0.5) / n
        if axis == "h":
            out.append(stick(bone, c, face, (a0 + a1) / 2, b0 + (b1 - b0) * t,
                             (max(MIN_PART, sa * (a1 - a0)), max(MIN_PART, w), dd), style,
                             sink=sink, **kw))
        else:
            out.append(stick(bone, c, face, a0 + (a1 - a0) * t, (b0 + b1) / 2,
                             (max(MIN_PART, w), max(MIN_PART, sb * (b1 - b0)), dd), style,
                             sink=sink, **kw))
    if rim:
        rw = max(MIN_PART, rim_w)
        fa, fb = sa * (a1 - a0) + 2 * rw, sb * (b1 - b0) + 2 * rw
        da, db = rw / max(sa, 1e-6) / 2, rw / max(sb, 1e-6) / 2
        out.append(stick(bone, c, face, (a0 + a1) / 2, b0 - db, (fa, rw, dd), rim, sink=sink - 0.03, **kw))
        out.append(stick(bone, c, face, (a0 + a1) / 2, b1 + db, (fa, rw, dd), rim, sink=sink - 0.03, **kw))
        out.append(stick(bone, c, face, a0 - da, (b0 + b1) / 2, (rw, fb - 2 * rw, dd), rim,
                         sink=sink - 0.03, **kw))
        out.append(stick(bone, c, face, a1 + da, (b0 + b1) / 2, (rw, fb - 2 * rw, dd), rim,
                         sink=sink - 0.03, **kw))
    return out


def layered_plate(bone, centre, size, style, top="plate2", rot=(0, 0, 0), face="north",
                  inset=0.35, thick=0.22, top_ab=(0.5, 0.5), trim="gold", trim_edge="bottom",
                  trim_w=0.26, rivet=None, n_rivets=0, rivet_edge="top", **kw):
    """縁取りのある多層の装甲板: 下の板（style）→ 面 face に一回り小さい上の板（top。inset だけ内側、
    厚み thick）→ 下の板の縁に金の帯（trim、trim_edge 側）→ 上の板にリベット（rivet / n_rivets）。
    戻り値 {"base", "top", "trim", "rivets"}（上に更に stick / line_on で重ねられる）。"""
    base = rbox(bone, centre, size, style, rot=rot, **kw)
    sa, sb = _face_dims(base, face)
    out = {"base": base, "top": None, "trim": None, "rivets": []}
    if top:
        out["top"] = stick(bone, base, face, top_ab[0], top_ab[1],
                           (max(MIN_PART, sa - 2 * inset), max(MIN_PART, sb - 2 * inset),
                            max(MIN_PART, thick)), top, sink=0.05, **kw)
    if trim:
        tw = max(MIN_PART, trim_w)
        if trim_edge in ("bottom", "top"):
            b = tw / 2 / sb if trim_edge == "bottom" else 1 - tw / 2 / sb
            out["trim"] = stick(bone, base, face, 0.5, b, (sa + 0.04, tw, max(MIN_PART, thick * 0.9)),
                                trim, sink=0.06, **kw)
        else:
            a = tw / 2 / sa if trim_edge == "left" else 1 - tw / 2 / sa
            out["trim"] = stick(bone, base, face, a, 0.5, (tw, sb + 0.04, max(MIN_PART, thick * 0.9)),
                                trim, sink=0.06, **kw)
    if rivet and n_rivets and out["top"] is not None:
        out["rivets"] = rivets(bone, out["top"], face, n_rivets, edge=rivet_edge, margin=0.25,
                               style=rivet, **kw)
    return out


def joint_drum(bone, centre, r, length, axis="x", style="frame", cap="chrome", hub="dark",
               glow=None, caps=(-1, 1), bolts=0, bolt_style="silver", **kw):
    """八角柱の関節ドラム（肘・膝・足首・手首）。軸 axis、半径 r、長さ length。
    caps: 端の蓋を付ける側（-1 = 軸の負の端、+1 = 正の端。右側の部品の外側は -1）。蓋は一回り小さい
    八角の円盤＋中央の軸受け（hub）。glow に塗りを渡すと軸受けの真ん中が光る。bolts で蓋の縁にボルト。"""
    c = _v(centre)
    i = AX[axis]
    e = np.zeros(3)
    e[i] = 1.0
    out = octa(bone, c, 2 * r, length, style, axis=axis, **kw)
    for sg in caps:
        cc = c + e * sg * (length / 2 + 0.05)
        out += octa(bone, cc, 2 * r * 0.76, 0.3, cap, axis=axis, **kw)
        hs = [max(MIN_PART, r * 0.62)] * 3
        hs[i] = 0.24
        hc = c + e * sg * (length / 2 + 0.2)
        out.append(cbox(bone, hc, hs, hub, **kw))
        if glow:
            gs = [max(MIN_PART, r * 0.3)] * 3
            gs[i] = 0.16
            out.append(cbox(bone, c + e * sg * (length / 2 + 0.3), gs, glow, **kw))
        if bolts:
            out += ring(bone, tuple(cc + e * sg * 0.12), r * 0.62, bolts,
                        (0.18, 0.18, 0.16), bolt_style, axis=axis, **kw)
    return out


def finger_chain(bone, pts, w=0.5, h=None, style="frame", knuckle="dark", kscale=1.14,
                 tip=None, **kw):
    """指（関節の連なり）: 点列の区間ごとに角柱、内側の関節ごとに一回り太い関節の箱。
    w は幅（局所 X、水平）、h は厚み。tip に塗りを渡すと先端に小さな爪。"""
    P = [_v(p) for p in pts]
    h = w if h is None else h
    out = []
    for i in range(len(P) - 1):
        out.append(beam(bone, P[i], P[i + 1], w, h, style, extend=-0.02, **kw))
    for i in range(1, len(P) - 1):
        d = (P[i + 1] - P[i - 1])
        out.append(mat_cube(bone, P[i], (w * kscale, h * kscale, max(MIN_PART, min(w, h) * 0.8)),
                            knuckle, frame_to(d), **kw))
    if tip:
        d = P[-1] - P[-2]
        L = float(np.linalg.norm(d))
        out.append(mat_cube(bone, P[-1] - d / L * 0.12, (w * 0.8, max(MIN_PART, h * 0.5), 0.3),
                            tip, frame_to(d), **kw))
    return out


def greebles(bone, c, face, n=5, seed=0, styles=("frame", "dark", "silver"), size=(0.22, 0.6),
             h=(0.15, 0.24), region=(0.12, 0.12, 0.88, 0.88), **kw):
    """パネルの小物（グリーブル）: 面の region の中に n 個の小箱を決定的な乱数で散らす。"""
    import random as _random
    rng = _random.Random(seed)
    out = []
    for _ in range(n):
        a = rng.uniform(region[0], region[2])
        b = rng.uniform(region[1], region[3])
        sz = (rng.uniform(*size), rng.uniform(*size), max(MIN_PART, rng.uniform(*h)))
        out.append(stick(bone, c, face, a, b, sz, rng.choice(styles), sink=0.05, **kw))
    return out


def sensor(bone, centre, size=0.36, style="glow", bezel="dark", axis="z", facing=-1, **kw):
    """小さなセンサーの灯り（暗い縁 + 発光の点、2 個）。axis と facing（-1/+1）で向く方向。
    例: 正面向き axis="z", facing=-1 / 右外向き axis="x", facing=-1。"""
    c = _v(centre)
    i = AX[axis]
    e = np.zeros(3)
    e[i] = facing
    bs = [size * 1.6] * 3
    bs[i] = 0.2
    ls = [max(MIN_PART, size)] * 3
    ls[i] = 0.2
    return [cbox(bone, c, bs, bezel, **kw), cbox(bone, c + e * 0.06, ls, style, **kw)]


def mx(p):
    """点の X を反転（右 → 左）。"""
    return (-p[0], p[1], p[2])
