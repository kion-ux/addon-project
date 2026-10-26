# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — QA 画像・README 用のソフトウェアレンダラ（nr_preview）。

Minecraft の無い環境で .geo.json + テクスチャを「実機と同じ変換規則」で描く。
部位破壊（ボーンを隠す）・ポーズ・アニメーション（Molang 込み）・render controller の
part_visibility を評価して、ゾンビ 50 体・武器・小道具の見た目を確かめるための道具。

使い方（CLI）::

    python3 tools/nightrunner/nr_preview.py <geo.json> <tex.png> [-o out.png] [--hide bone,bone]
        [--anim file.json --clip name --t 0.5] [--views front,back,left,right,three_quarter]
        [--size 512] [--persp] [--ss 2] [--floor] [--exact] [--legacy-faces]
        [--var v.x=1] [--query q.modified_distance_moved=3] [--prop nr:head=severed --rc rc.json]
        [--frames 8]                       # クリップを 8 コマ並べた絵にする
    python3 tools/nightrunner/nr_preview.py --selftest

API（他の生成器から import して使う）::

    geo = load_geometry(path | doc | mcmodel.Model, identifier=None)
    tex = load_texture(path | PIL.Image | ndarray | None)
    img = render(geo, tex, view="three_quarter", size=512, pose=None, hidden=None, bg=(32, 32, 36), ...)
    img = render_views(geo, tex, views=[...], size=512, pose=None, hidden=None, bg=(32, 32, 36))
    img = contact_sheet([(label, Image), ...], cols=None, title=None)
    pose, warnings = animation_pose(anim_json | path, "animation.nr.z.walk_shamble", t, bones=geo, variables={...})
    hidden = part_visibility_hidden(rc_json | path | rules, geo, properties={"nr:head": "severed"})
    value = molang(expr, variables=..., queries=..., properties=..., anim_time=..., warnings=[...])

────────────────────────────────────────────────────────────────────────────
■ 座標と変換の規則（ファイルに書かれた数値 = 統合版のモデル空間）
────────────────────────────────────────────────────────────────────────────
* 16 単位 = 1 ブロック、+Y が上。顔は -Z（north 面）、体の右は -X（バニラの rightArm は x=-5）。
* 回転 [rx, ry, rz]（度）はモデル空間の右手系で
      R = Rz(-rz) · Ry(+ry) · Rx(-rx)          （X → Y → Z の順に掛かる）
  tools/hyperdim/hd_space.rot と同じ（--selftest で一致を確かめる）。負の rx で腕が前へ上がり、
  正の ry で右（-X 側）を向き、正の rz で右腕が外へ開く。
  （tools/preview.py の rot_matrix は ry と rz の符号が逆。新しいコードはこちらに合わせること）
* ボーンの局所変換:  T(position) · T(pivot) · R · S · T(-pivot)、ワールド = 親のワールド · 局所。
  pivot はモデル空間の絶対座標（親からの相対ではない）。アニメーション・pose の rotation は
  ジオメトリの rotation に**足し**、position は足し、scale は掛ける。
* キューブ: origin〜origin+size を inflate だけ膨らませた箱。rotation があればキューブの pivot
  （無ければ膨らませる前の箱の中心）で回す。UV は inflate の影響を受けない。
* 面と UV の向き（Blockbench の bedrock コーデックと three_custom.setShape を読んで確認した、実機の向き）。
  a = 箱の小さい側、b = 大きい側。「左上」はテクスチャの (u0, v0) が来る角:

      面     置かれる所  左上の角        u が増える向き  v が増える向き
      north  z = a       (ax, by, az)    +X              -Y
      south  z = b       (bx, by, bz)    -X              -Y
      east   x = a  (!)  (ax, by, bz)    -Z              -Y
      west   x = b  (!)  (bx, by, az)    +Z              -Y
      up     y = b       (ax, by, bz)    +X              -Z
      down   y = a       (ax, ay, az)    +X              +Z

  **east は -X（体の右）側**。ボックス UV の最初の帯（スキンの「頭の右側」）が east で、帯は
  east → north → west → south の順に箱を一周する（Java の ModelBox と同じ）。
  注意: tools/preview.py・tools/hyperdim/hd_scene.py（と nr_paint.py の説明）は east を +X に置いていて、
  east と west のテクスチャが入れ替わって見える。faces="legacy"（CLI は --legacy-faces）で
  その並びを再現できる（比較用）。他の 4 面の向きは同じ。
  uv_size が負なら反転、uv_rotation（90 度刻み）も読む。テクスチャの実寸が texture_width/height と
  違えば比で拡縮する。ボックス UV（"uv": [u, v]）は寸法を小数のまま使い:
      east (u, v+sz, sz, sy)  north (u+sz, v+sz, sx, sy)  west (u+sz+sx, v+sz, sz, sy)
      south (u+2sz+sx, v+sz, sx, sy)  up (u+sz, v, sx, sz)  down (u+sz+sx, v+sz, sx, -sz)（下面は v が逆）
  mirror（キューブかボーン）で east/west を入れ替え、全部の面の u を反転する。
* 画面: 統合版はモデルを X について鏡映して描く。だから「正面から見ると体の右 (-X) が画面の左」に
  なる（hd_scene.ortho・preview.py と同じ見え方）。ここでは X を反転した右手系へ移してから普通の
  カメラで撮る。カメラは
      yaw   0 = 正面（-Z 側から顔を見る）、+90 = 体の右側から、180 = 背後、-90 = 体の左側から
      pitch 正で上から見下ろす（90 = 真上）
  hd_scene.ortho(yaw=θ, pitch=φ) と同じ絵は Camera(yaw=-θ, pitch=-φ)。
* 光: light="studio"（既定。カメラの左上からのキーライト＋正面のフィル）/ "mc"（世界に固定した
  Minecraft 風の 2 灯）/ "hd"（hd_scene.raster と同じ）/ None（陰影なし）。
* アルファ: alpha < alpha_test の texel は捨てる（既定 1 = alpha 0 だけ捨てる。entity_alphatest の
  見え方は 128）。emissive=True なら alpha 1〜254 の texel は 1 - alpha/255 の割合で陰影なしに光る
  （nr_paint の EMISSIVE_ALPHA=16 / EMISSIVE_HALO=160、entity_emissive_alpha 系）。
* 裏面: cull=True（既定）で外向きの法線がカメラの反対を向く面を捨てる（厚さ 0 の板は
  カメラに向いた側だけが描かれる）。
* part_visibility でボーンを隠すと子も隠れる（DESIGN.md §3）。hidden の既定もそれに合わせて
  hide_mode="subtree"。"exact" ならそのボーン自身のキューブだけを隠す。名前は大文字小文字を
  区別せず、`stump_*` のようなワイルドカードが使える。

■ アニメーション
* 値: 数・文字列（Molang）・3 要素の配列・キーフレーム {"時刻": 値 | {"pre", "post", "lerp_mode"}}。
* キーの間: linear / catmullrom（統合版・Blockbench と同じ一様 Catmull-Rom。端は同じ値を複製）/ step。
  キーちょうどの時刻は pre、キーより前は最初のキーの pre、最後のキーより後は post。
  loop: true は anim_time を長さで折り返し（前後のキーも折り返して補間）、それ以外は長さで止める。
* Molang: 四則・比較・論理・三項・`a ? b`・`??`・`->`（自分に読み替え）・`;` と return・代入・
  `{}` ブロック・loop()、math.*（三角関数は度）、q.anim_time / q.life_time / q.property('nr:x')、
  呼び出し側が渡す variable / query / context。分からないものは 0 にして warnings に積む。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import random
import re
import sys
import time
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:  # nr_common と同じ置き場所（NR_SCRATCH で変えられる）
    from nr_common import SCRATCH  # type: ignore
except Exception:  # noqa: BLE001
    SCRATCH = os.environ.get("NR_SCRATCH", os.path.join(ROOT, "build_preview", "nightrunner"))

__all__ = [
    "Geometry", "Camera", "VIEW_PRESETS", "FACE_NAMES",
    "load_geometry", "load_texture", "rot", "bone_local", "bone_matrices", "locator_positions",
    "render", "render_views", "render_clip", "contact_sheet", "scene_bounds",
    "load_animations", "animation_pose", "merge_poses", "molang", "MolangContext",
    "part_visibility_hidden",
]

# ===========================================================================
#  回転（hd_space.rot と同じ）
# ===========================================================================


def _Rx(a: float) -> np.ndarray:
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


def _Ry(a: float) -> np.ndarray:
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1.0, 0], [-s, 0, c]])


def _Rz(a: float) -> np.ndarray:
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rot(rx: float, ry: float, rz: float) -> np.ndarray:
    """統合版の rotation [rx, ry, rz] → モデル空間の回転行列 Rz(-rz)·Ry(ry)·Rx(-rx)。"""
    return _Rz(-rz) @ _Ry(ry) @ _Rx(-rx)


def bone_local(pivot, rotation=(0, 0, 0), position=(0, 0, 0), scale=(1, 1, 1)) -> np.ndarray:
    """ボーンの局所変換 T(position)·T(pivot)·R·S·T(-pivot)（4x4）。"""
    p = np.asarray(pivot, float)
    RS = rot(*[float(v) for v in rotation]) @ np.diag(np.broadcast_to(np.asarray(scale, float), (3,)))
    M = np.eye(4)
    M[:3, :3] = RS
    M[:3, 3] = np.asarray(position, float) + p - RS @ p
    return M


# ===========================================================================
#  面の表（module docstring の表そのもの）
# ===========================================================================

FACE_NAMES = ("north", "south", "east", "west", "up", "down")
# 角は 左上・右上・右下・左下 の順（テクスチャの (u0,v0) (u1,v0) (u1,v1) (u0,v1)）。0 = a 側、1 = b 側
_CORNERS = {
    "north": ((0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)),
    "south": ((1, 1, 1), (0, 1, 1), (0, 0, 1), (1, 0, 1)),
    "east": ((0, 1, 1), (0, 1, 0), (0, 0, 0), (0, 0, 1)),
    "west": ((1, 1, 0), (1, 1, 1), (1, 0, 1), (1, 0, 0)),
    "up": ((0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0)),
    "down": ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
}
_NORMALS = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (-1, 0, 0), "west": (1, 0, 0),
            "up": (0, 1, 0), "down": (0, -1, 0)}


def _face_tables(mode: str):
    """(角の選び方 (6,4,3), 外向きの法線 (6,3))。mode="legacy" は east/west を入れ替えた旧来の並び。"""
    corners = dict(_CORNERS)
    normals = dict(_NORMALS)
    if mode == "legacy":
        corners["east"], corners["west"] = _CORNERS["west"], _CORNERS["east"]
        normals["east"], normals["west"] = _NORMALS["west"], _NORMALS["east"]
    elif mode != "bedrock":
        raise ValueError(f"faces must be 'bedrock' or 'legacy', not {mode!r}")
    S = np.array([corners[f] for f in FACE_NAMES], float)
    N = np.array([normals[f] for f in FACE_NAMES], float)
    return S, N


def box_uv_rects(u: float, v: float, size: Sequence[float], mirror: bool = False) -> Dict[str, Tuple]:
    """ボックス UV → 面ごとの (u0, v0, du, dv)（統合版の per-face と同じ意味）。"""
    sx, sy, sz = (float(s) for s in size)
    r = {
        "east": (u, v + sz, sz, sy),
        "north": (u + sz, v + sz, sx, sy),
        "west": (u + sz + sx, v + sz, sz, sy),
        "south": (u + 2 * sz + sx, v + sz, sx, sy),
        "up": (u + sz, v, sx, sz),
        "down": (u + sz + sx, v + sz, sx, -sz),
    }
    if mirror:
        r = {k: (u0 + du, v0, -du, dv) for k, (u0, v0, du, dv) in r.items()}
        r["east"], r["west"] = r["west"], r["east"]
    return r


# ===========================================================================
#  ジオメトリ
# ===========================================================================


class Geometry:
    """1 つのジオメトリ（pose に依らない部分を numpy の配列にしておく）。"""

    def __init__(self, desc: dict, bones: List[dict], source: str = ""):
        self.source = source
        self.warnings: List[str] = []
        self.identifier = desc.get("identifier", "?")
        self.tex_w = float(desc.get("texture_width", desc.get("texturewidth", 64)) or 64)
        self.tex_h = float(desc.get("texture_height", desc.get("textureheight", 64)) or 64)
        self.names: List[str] = [str(b.get("name", f"bone{i}")) for i, b in enumerate(bones)]
        self.lower = {n.lower(): i for i, n in enumerate(self.names)}
        nb = len(bones)
        self.parent = np.full(nb, -1, int)
        self.pivot = np.zeros((nb, 3))
        self.rotation = np.zeros((nb, 3))
        self.locators: Dict[str, Tuple[int, np.ndarray]] = {}
        for i, b in enumerate(bones):
            par = b.get("parent")
            if par is not None:
                j = self.lower.get(str(par).lower())
                if j is None:
                    self.warnings.append(f"bone {self.names[i]}: parent {par} not found (treated as root)")
                elif j != i:
                    self.parent[i] = j
            self.pivot[i] = _vec3(b.get("pivot", (0, 0, 0)))
            self.rotation[i] = _vec3(b.get("rotation", (0, 0, 0)))
            for lname, lv in (b.get("locators") or {}).items():
                off = lv.get("offset", (0, 0, 0)) if isinstance(lv, dict) else lv
                self.locators[lname] = (i, _vec3(off))
            if b.get("poly_mesh"):
                self.warnings.append(f"bone {self.names[i]}: poly_mesh is not drawn")
        # 親が先に来る順（ファイルの並びに依らない）
        self.order: List[int] = []
        state = [0] * nb

        def visit(i, depth=0):
            if state[i] == 2:
                return
            if state[i] == 1 or depth > nb:
                self.warnings.append(f"bone {self.names[i]}: parent cycle (cut)")
                self.parent[i] = -1
                return
            state[i] = 1
            if self.parent[i] >= 0:
                visit(self.parent[i], depth + 1)
            state[i] = 2
            self.order.append(i)

        for i in range(nb):
            visit(i)
        # キューブ
        cb, A, B, L, rect, urot, has = [], [], [], [], [], [], []
        for i, b in enumerate(bones):
            bmirror = bool(b.get("mirror", False))
            binflate = float(b.get("inflate", 0.0) or 0.0)
            for c in b.get("cubes") or []:
                origin = _vec3(c.get("origin", (0, 0, 0)))
                size = _vec3(c.get("size", (0, 0, 0)))
                inf = float(c.get("inflate", binflate) or 0.0)
                cb.append(i)
                A.append(origin - inf)
                B.append(origin + size + inf)
                r = c.get("rotation")
                M = np.eye(4)
                if r is not None and any(float(x) for x in r):
                    piv = _vec3(c["pivot"]) if c.get("pivot") is not None else origin + size / 2
                    R = rot(*_vec3(r))
                    M[:3, :3] = R
                    M[:3, 3] = piv - R @ piv
                L.append(M)
                fr, fu, fh = self._cube_uv(c, size, bmirror)
                rect.append(fr)
                urot.append(fu)
                has.append(fh)
        n = len(cb)
        self.c_bone = np.array(cb, int)
        self.c_a = np.array(A, float).reshape(n, 3)
        self.c_b = np.array(B, float).reshape(n, 3)
        self.c_local = np.array(L, float).reshape(n, 4, 4)
        self.c_rect = np.array(rect, float).reshape(n, 6, 4)
        self.c_urot = np.array(urot, int).reshape(n, 6)
        self.c_has = np.array(has, bool).reshape(n, 6)

    @staticmethod
    def _cube_uv(c: dict, size: np.ndarray, bone_mirror: bool):
        uv = c.get("uv", [0, 0])
        sx, sy, sz = (float(v) for v in size)
        natural = {"north": (sx, sy), "south": (sx, sy), "east": (sz, sy), "west": (sz, sy),
                   "up": (sx, sz), "down": (sx, sz)}
        rects = np.zeros((6, 4))
        urot = np.zeros(6, int)
        has = np.zeros(6, bool)
        if isinstance(uv, dict):
            for k, face in enumerate(FACE_NAMES):
                f = uv.get(face)
                if not isinstance(f, dict):
                    continue
                u0, v0 = (float(x) for x in (f.get("uv") or (0, 0))[:2])
                du, dv = (float(x) for x in (f.get("uv_size") or natural[face])[:2])
                rects[k] = (u0, v0, du, dv)
                urot[k] = int(round(float(f.get("uv_rotation", 0) or 0) / 90.0)) % 4
                has[k] = True
        else:
            u0, v0 = (float(x) for x in (uv if isinstance(uv, (list, tuple)) and len(uv) >= 2 else (0, 0))[:2])
            r = box_uv_rects(u0, v0, size, bool(c.get("mirror", bone_mirror)))
            for k, face in enumerate(FACE_NAMES):
                rects[k] = r[face]
                has[k] = True
        return rects, urot, has

    # -- 便利 ----------------------------------------------------------------
    def find(self, name: str) -> Optional[int]:
        return self.lower.get(str(name).lower())

    @property
    def cube_count(self) -> int:
        return int(len(self.c_bone))

    def children(self) -> Dict[int, List[int]]:
        out: Dict[int, List[int]] = {}
        for i, p in enumerate(self.parent):
            out.setdefault(int(p), []).append(i)
        return out

    def __repr__(self) -> str:
        return (f"<Geometry {self.identifier} bones={len(self.names)} cubes={self.cube_count} "
                f"tex={self.tex_w:g}x{self.tex_h:g}>")


def _vec3(v) -> np.ndarray:
    if isinstance(v, (int, float)):
        return np.array([float(v)] * 3)
    a = [float(x) for x in list(v)[:3]]
    while len(a) < 3:
        a.append(0.0)
    return np.array(a)


def load_geometry(src, identifier: Optional[str] = None, index: int = 0) -> Geometry:
    """geo.json のパス / 読み込んだ辞書 / mcmodel.Model / Geometry → Geometry。

    format 1.12.0 / 1.16.0（"minecraft:geometry" の配列）と 1.8 / 1.10 の旧形式（"geometry.xxx" キー）を読む。
    複数入っていれば identifier（無ければ index 番目）を選ぶ。
    """
    if isinstance(src, Geometry):
        return src
    source = ""
    if hasattr(src, "to_json") and hasattr(src, "bones"):  # mcmodel.Model
        if not getattr(src, "tex_w", 1):
            src.pack()
        doc = {"format_version": "1.12.0", "minecraft:geometry": [src.to_json()]}
        source = f"<Model {getattr(src, 'identifier', '?')}>"
    elif isinstance(src, (str, os.PathLike)):
        source = os.fspath(src)
        with open(source, encoding="utf-8") as fh:
            doc = json.load(fh)
    else:
        doc = src
    geos: List[Tuple[dict, List[dict]]] = []
    if "minecraft:geometry" in doc:
        for g in doc["minecraft:geometry"]:
            geos.append((g.get("description", {}), g.get("bones", [])))
    else:
        for k, g in doc.items():
            if isinstance(g, dict) and k.startswith("geometry."):
                desc = dict(g)
                desc["identifier"] = k.split(":")[0]
                geos.append((desc, g.get("bones", [])))
    if not geos:
        raise ValueError(f"no geometry in {source or 'document'}")
    if identifier is not None:
        for desc, bones in geos:
            if desc.get("identifier") == identifier:
                return Geometry(desc, bones, source)
        raise KeyError(f"{identifier} not in {source}")
    desc, bones = geos[index]
    return Geometry(desc, bones, source)


def load_texture(src, geo: Optional[Geometry] = None) -> np.ndarray:
    """パス / PIL.Image / ndarray → (H, W, 4) uint8。None なら市松の「テクスチャ無し」模様。"""
    if src is None:
        w = int(geo.tex_w) if geo else 64
        h = int(geo.tex_h) if geo else 64
        yy, xx = np.mgrid[0:h, 0:w]
        chk = ((xx // 4 + yy // 4) % 2).astype(bool)
        out = np.zeros((h, w, 4), np.uint8)
        out[..., 3] = 255
        out[chk] = (200, 60, 200, 255)
        out[~chk] = (40, 40, 48, 255)
        return out
    if isinstance(src, np.ndarray):
        a = src
        if a.ndim == 2:
            a = np.stack([a, a, a, np.full_like(a, 255)], -1)
        elif a.shape[2] == 3:
            a = np.concatenate([a, np.full(a.shape[:2] + (1,), 255, a.dtype)], -1)
        return np.ascontiguousarray(a.astype(np.uint8))
    if isinstance(src, Image.Image):
        return np.asarray(src.convert("RGBA"), np.uint8).copy()
    return np.asarray(Image.open(src).convert("RGBA"), np.uint8).copy()


# ===========================================================================
#  pose・ボーンの行列・隠すボーン
# ===========================================================================

PoseLike = Optional[Dict[str, Any]]


def _norm_pose(pose: PoseLike, geo: Geometry, warn: Optional[List[str]] = None):
    """{bone: [rx,ry,rz] | {"rotation","position","scale"}} → {index: (rot, pos, scale)}。"""
    out: Dict[int, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for name, v in (pose or {}).items():
        i = geo.find(name)
        if i is None:
            if warn is not None:
                msg = f"pose: bone '{name}' not in geometry"
                if msg not in warn:
                    warn.append(msg)
            continue
        if isinstance(v, dict):
            r = _vec3(v.get("rotation", 0.0))
            p = _vec3(v.get("position", 0.0))
            s = _vec3(v.get("scale", 1.0))
        else:
            r, p, s = _vec3(v), np.zeros(3), np.ones(3)
        if i in out:  # 同じボーンが大文字小文字違いで 2 回 → 足す
            r0, p0, s0 = out[i]
            r, p, s = r0 + r, p0 + p, s0 * s
        out[i] = (r, p, s)
    return out


def bone_matrices(geo: Geometry, pose: PoseLike = None, warn: Optional[List[str]] = None) -> np.ndarray:
    """各ボーンのワールド行列 (B, 4, 4)（geo.names の並び）。"""
    P = _norm_pose(pose, geo, warn)
    W = np.zeros((len(geo.names), 4, 4))
    for i in geo.order:
        r, p, s = P.get(i, (np.zeros(3), np.zeros(3), np.ones(3)))
        L = bone_local(geo.pivot[i], geo.rotation[i] + r, p, s)
        par = geo.parent[i]
        W[i] = W[par] @ L if par >= 0 else L
    return W


def locator_positions(geo: Geometry, pose: PoseLike = None) -> Dict[str, np.ndarray]:
    """ロケータのモデル空間の位置（pose 込み）。"""
    W = bone_matrices(geo, pose)
    return {k: (W[i] @ np.append(off, 1.0))[:3] for k, (i, off) in geo.locators.items()}


def _hidden_mask(geo: Geometry, hidden: Optional[Iterable[str]], mode: str = "subtree") -> np.ndarray:
    nb = len(geo.names)
    mask = np.zeros(nb, bool)
    pats = [str(h).lower() for h in (hidden or [])]
    if not pats:
        return mask
    for i, n in enumerate(geo.names):
        ln = n.lower()
        mask[i] = any(fnmatch.fnmatchcase(ln, p) for p in pats)
    if mode == "subtree":
        for i in geo.order:
            if geo.parent[i] >= 0 and mask[geo.parent[i]]:
                mask[i] = True
    elif mode != "exact":
        raise ValueError("hide_mode must be 'subtree' or 'exact'")
    return mask


# ===========================================================================
#  シーン（pose を当てた面の一覧。カメラに依らない）
# ===========================================================================


class _Scene:
    def __init__(self, geo: Geometry, pose: PoseLike = None, hidden=None, hide_mode="subtree",
                 faces="bedrock"):
        self.geo = geo
        self.warnings: List[str] = list(geo.warnings)
        self.W = bone_matrices(geo, pose, self.warnings)
        hid = _hidden_mask(geo, hidden, hide_mode)
        self.hidden_bones = {geo.names[i] for i in np.nonzero(hid)[0]}
        keep = ~hid[geo.c_bone] if geo.cube_count else np.zeros(0, bool)
        ci = np.nonzero(keep)[0]
        S, N = _face_tables(faces)
        if len(ci) == 0:
            self.P = np.zeros((0, 4, 3))
            self.n = np.zeros((0, 3))
            self.nout = np.zeros((0, 3))
            self.rect = np.zeros((0, 4))
            self.urot = np.zeros(0, int)
            self.cube = np.zeros(0, int)
            self.face = np.zeros(0, int)
            return
        CM = self.W[geo.c_bone[ci]] @ geo.c_local[ci]                     # (n,4,4)
        A = geo.c_a[ci][:, None, None, :]
        B = geo.c_b[ci][:, None, None, :]
        Ploc = A * (1.0 - S[None]) + B * S[None]                          # (n,6,4,3)
        R3 = CM[:, :3, :3]
        Pw = np.einsum("nij,nfkj->nfki", R3, Ploc) + CM[:, None, None, :3, 3]
        nout = np.einsum("nij,fj->nfi", R3, N)                            # (n,6,3)
        has = geo.c_has[ci]
        fi = np.nonzero(has)
        P = Pw[fi]                                                        # (F,4,3)
        nout = nout[fi]
        e1 = P[:, 1] - P[:, 0]
        e2 = P[:, 3] - P[:, 0]
        n = np.cross(e1, e2)
        area = np.linalg.norm(n, axis=1)
        ok = area > 1e-10
        n = n[ok] / area[ok, None]
        nout = nout[ok]
        nl = np.linalg.norm(nout, axis=1)
        nout = nout / np.maximum(nl, 1e-12)[:, None]
        flip = np.einsum("ij,ij->i", n, nout) < 0
        n[flip] *= -1
        self.P = P[ok]
        self.n = n
        self.nout = nout
        self.rect = geo.c_rect[ci][fi][ok]
        self.urot = geo.c_urot[ci][fi][ok]
        self.cube = ci[fi[0]][ok]
        self.face = fi[1][ok]

    def bounds_points(self) -> np.ndarray:
        return self.P.reshape(-1, 3)


def scene_bounds(geo, pose: PoseLike = None, hidden=None, hide_mode="subtree") -> Tuple[np.ndarray, np.ndarray]:
    """見えているキューブの (最小, 最大)（モデル空間）。"""
    sc = _Scene(load_geometry(geo), pose, hidden, hide_mode)
    pts = sc.bounds_points()
    if len(pts) == 0:
        return np.zeros(3), np.zeros(3)
    return pts.min(0), pts.max(0)


# ===========================================================================
#  カメラ
# ===========================================================================


@dataclass
class Camera:
    """yaw: 0 正面 / +90 体の右から / 180 背後。pitch: 正で見下ろす。

    scale: ortho なら出力画像での 1 単位あたりのピクセル、persp なら焦点距離（ピクセル）。
    None なら見えている範囲が収まるように自動で決める（target も None なら自動で中心に置く）。
    """
    yaw: float = 35.0
    pitch: float = 14.0
    roll: float = 0.0
    projection: str = "ortho"          # "ortho" / "persp"
    fov: float = 32.0                  # persp の縦の画角（度）
    target: Optional[Sequence[float]] = None
    scale: Optional[float] = None
    distance: Optional[float] = None   # persp: 注視点からの距離（None で自動）
    margin: float = 0.07


VIEW_PRESETS: Dict[str, Tuple[float, float]] = {
    "front": (0.0, 0.0),
    "back": (180.0, 0.0),
    "right": (90.0, 0.0),             # 体の右側（-X）から
    "left": (-90.0, 0.0),             # 体の左側（+X）から
    "three_quarter": (35.0, 14.0),    # 正面右寄りから少し見下ろす
    "three_quarter_left": (-35.0, 14.0),
    "back_three_quarter": (145.0, 14.0),
    "back_three_quarter_left": (-145.0, 14.0),
    "top": (0.0, 90.0),
    "bottom": (0.0, -90.0),
    "hero": (28.0, 6.0),              # README 用（persp と合わせる）
    "low": (25.0, -12.0),
}


def camera_preset(view: Union[str, Camera, Tuple[float, float], None] = "three_quarter",
                  projection: Optional[str] = None, fov: Optional[float] = None,
                  margin: Optional[float] = None) -> Camera:
    if isinstance(view, Camera):
        cam = view
    elif isinstance(view, (tuple, list)):
        cam = Camera(yaw=float(view[0]), pitch=float(view[1]) if len(view) > 1 else 0.0)
    else:
        name = view or "three_quarter"
        if name not in VIEW_PRESETS:
            raise KeyError(f"unknown view {name!r} (have {', '.join(VIEW_PRESETS)})")
        y, p = VIEW_PRESETS[name]
        cam = Camera(yaw=y, pitch=p)
    kw = {}
    if projection is not None:
        kw["projection"] = projection
    if fov is not None:
        kw["fov"] = fov
    if margin is not None:
        kw["margin"] = margin
    return replace(cam, **kw) if kw else cam


_MIRROR = np.array([-1.0, 1.0, 1.0])


class _Proj:
    """カメラを解決したもの。V の行 = 画面の右・上・奥（モデル空間。X の鏡映込み）。"""

    def __init__(self, cam: Camera, W: int, H: int, pts: np.ndarray, fit_scale: Optional[float] = None):
        self.cam, self.W, self.H = cam, W, H
        y, p, rl = (math.radians(v) for v in (cam.yaw, cam.pitch, cam.roll))
        cdir = np.array([math.sin(y) * math.cos(p), math.sin(p), -math.cos(y) * math.cos(p)])
        f = -cdir
        r = np.array([-math.cos(y), 0.0, -math.sin(y)])
        u = np.cross(r, f)
        if rl:
            r, u = r * math.cos(rl) + u * math.sin(rl), -r * math.sin(rl) + u * math.cos(rl)
        # 描画空間（X 鏡映）→ モデル空間へ
        self.r, self.u, self.f = r * _MIRROR, u * _MIRROR, f * _MIRROR
        self.cdir = cdir * _MIRROR
        self.V = np.stack([self.r, self.u, self.f])
        self.persp = cam.projection.startswith("p")
        m = cam.margin
        pts = pts if len(pts) else np.zeros((1, 3))
        auto_target = cam.target is None
        lo, hi = pts.min(0), pts.max(0)
        self.target = (lo + hi) / 2 if auto_target else np.asarray(cam.target, float)
        self.radius = float(np.linalg.norm(pts - self.target, axis=1).max()) or 1.0
        if not self.persp:
            self.origin = self.target
            q = (pts - self.origin) @ self.V.T
            if auto_target:
                qlo, qhi = q[:, :2].min(0), q[:, :2].max(0)
                self.ox, self.oy = (qlo + qhi) / 2
                half = np.maximum((qhi - qlo) / 2, 1e-6)
            else:
                self.ox = self.oy = 0.0
                half = np.maximum(np.abs(q[:, :2]).max(0), 1e-6)
            self.fit = float(min(W / 2 * (1 - 2 * m) / half[0], H / 2 * (1 - 2 * m) / half[1]))
            self.scale = float(cam.scale or fit_scale or self.fit)
            self.near = -1e18
        else:
            fv = math.radians(cam.fov)
            fh = 2 * math.atan(math.tan(fv / 2) * W / H)
            dist = cam.distance or self.radius / math.sin(min(fv, fh) / 2) * (1 + m)
            self.dist = float(dist)
            self.origin = self.target + self.cdir * self.dist          # 目の位置
            self.near = max(1e-3, self.dist * 1e-3)
            q = (pts - self.origin) @ self.V.T
            front = q[:, 2] > self.near
            qq = q[front] if front.any() else np.array([[0.0, 0.0, 1.0]])
            nx, ny = qq[:, 0] / qq[:, 2], qq[:, 1] / qq[:, 2]
            if auto_target:
                self.ox, self.oy = (nx.min() + nx.max()) / 2, (ny.min() + ny.max()) / 2
                hx = max((nx.max() - nx.min()) / 2, 1e-6)
                hy = max((ny.max() - ny.min()) / 2, 1e-6)
            else:
                self.ox = self.oy = 0.0
                hx = max(np.abs(nx).max(), 1e-6)
                hy = max(np.abs(ny).max(), 1e-6)
            self.fit = float(min(W / 2 * (1 - 2 * m) / hx, H / 2 * (1 - 2 * m) / hy))
            self.scale = float(cam.scale or fit_scale or self.fit)

    def cam_coords(self, P: np.ndarray) -> np.ndarray:
        return (P - self.origin) @ self.V.T

    def to_px(self, Q: np.ndarray, ss: int = 1) -> np.ndarray:
        """カメラ座標 (..., 3) → ピクセル (..., 2)（ss 倍の画像での座標）。"""
        if self.persp:
            z = np.where(Q[..., 2] > self.near, Q[..., 2], self.near)
            x = Q[..., 0] / z - self.ox
            y = Q[..., 1] / z - self.oy
        else:
            x = Q[..., 0] - self.ox
            y = Q[..., 1] - self.oy
        k = self.scale * ss
        return np.stack([(self.W / 2) * ss + x * k, (self.H / 2) * ss - y * k], -1)

    def project(self, P: np.ndarray, ss: int = 1) -> np.ndarray:
        return self.to_px(self.cam_coords(np.asarray(P, float)), ss)


# ===========================================================================
#  ラスタライザ（全部の面の断片をまとめて numpy で処理する）
# ===========================================================================

_CHUNK = 1 << 20      # 1 回に扱う断片（面の外接矩形のピクセル）の数


def _shade(n: np.ndarray, proj: _Proj, light) -> np.ndarray:
    if light in (None, False, "none", "flat"):
        return np.ones(len(n))
    if light == "hd":
        L = np.array([0.3, 0.8, -0.5])
        L /= np.linalg.norm(L)
        return 0.45 + 0.55 * np.abs(n @ L)
    if light == "mc":
        L0 = np.array([0.2, 1.0, -0.7]) * _MIRROR
        L1 = np.array([-0.2, 1.0, 0.7]) * _MIRROR
        L0 /= np.linalg.norm(L0)
        L1 /= np.linalg.norm(L1)
        return np.minimum(1.0, 0.4 + 0.6 * (np.maximum(0, n @ L0) + np.maximum(0, n @ L1)))
    # studio: 画面の左上・手前からのキーライト + 正面からのフィル + 上からの空の明かり
    key = -0.45 * proj.r + 0.78 * proj.u - 0.50 * proj.f
    key /= np.linalg.norm(key)
    sky = np.array([0.0, 1.0, 0.0])
    s = (0.30 + 0.55 * np.maximum(0, n @ key) + 0.20 * np.maximum(0, -(n @ proj.f))
         + 0.08 * np.maximum(0, n @ sky))
    return np.minimum(s, 1.08)


def _uv_affine(rect: np.ndarray, urot: np.ndarray, kx: float, ky: float):
    """面ごとの UV（テクスチャのピクセル単位）: uv = o + s*ds + t*dt と、はみ出し止めの範囲。"""
    u0, v0, du, dv = rect[:, 0], rect[:, 1], rect[:, 2], rect[:, 3]
    TL = np.stack([u0, v0], -1)
    TR = np.stack([u0 + du, v0], -1)
    BR = np.stack([u0 + du, v0 + dv], -1)
    BL = np.stack([u0, v0 + dv], -1)
    C = np.stack([TL, TR, BR, BL], 1)                                   # (F,4,2)
    for k in (1, 2, 3):                                                 # uv_rotation: 新しい左上 = 元の左下
        m = urot == k
        if m.any():
            C[m] = np.roll(C[m], k, axis=1)
    C = C * np.array([kx, ky])
    o = C[:, 0]
    ds = C[:, 1] - C[:, 0]
    dt = C[:, 3] - C[:, 0]
    lo = C.min(1)
    hi = C.max(1)
    umin = np.floor(lo[:, 0] + 1e-6).astype(np.int64)
    vmin = np.floor(lo[:, 1] + 1e-6).astype(np.int64)
    umax = np.maximum(np.ceil(hi[:, 0] - 1e-6).astype(np.int64) - 1, umin)
    vmax = np.maximum(np.ceil(hi[:, 1] - 1e-6).astype(np.int64) - 1, vmin)
    return o, ds, dt, umin, umax, vmin, vmax


def _rasterize(scene: _Scene, proj: _Proj, tex: np.ndarray, img: np.ndarray, zbuf: np.ndarray,
               cover: np.ndarray, ss: int, light, alpha_test: int, emissive: bool, emit_gain: float,
               cull: bool, stats: Optional[dict] = None) -> None:
    Wp, Hp = proj.W * ss, proj.H * ss
    P = scene.P
    if len(P) == 0:
        return
    Q = proj.cam_coords(P)                                              # (F,4,3)
    keep = np.ones(len(P), bool)
    if cull:
        if proj.persp:
            v = P.mean(1) - proj.origin
            keep &= np.einsum("ij,ij->i", scene.nout, v) < 0
        else:
            keep &= scene.nout @ proj.f < 0
    if proj.persp:
        keep &= (Q[..., 2] > proj.near).all(1)
    S = proj.to_px(Q, ss)                                               # (F,4,2)
    mn = S.min(1)
    mx = S.max(1)
    x0 = np.clip(np.ceil(mn[:, 0] - 0.5), 0, Wp).astype(np.int64)
    x1 = np.clip(np.floor(mx[:, 0] - 0.5) + 1, 0, Wp).astype(np.int64)
    y0 = np.clip(np.ceil(mn[:, 1] - 0.5), 0, Hp).astype(np.int64)
    y1 = np.clip(np.floor(mx[:, 1] - 0.5) + 1, 0, Hp).astype(np.int64)
    w = np.maximum(x1 - x0, 0)
    h = np.maximum(y1 - y0, 0)
    keep &= (w > 0) & (h > 0)
    # 画面 → 面の (s, t) の係数。s = cs·(x,y,1)/cw·(x,y,1)
    if proj.persp:
        k = proj.scale * ss
        K = np.array([[k, 0.0, Wp / 2 - k * proj.ox], [0.0, -k, Hp / 2 + k * proj.oy], [0.0, 0.0, 1.0]])
        Hf = np.einsum("ij,fjk->fik", K, np.stack([Q[:, 1] - Q[:, 0], Q[:, 3] - Q[:, 0], Q[:, 0]], -1))
        det = np.linalg.det(Hf)
        keep &= np.abs(det) > 1e-12
        Hi = np.zeros_like(Hf)
        Hi[keep] = np.linalg.inv(Hf[keep])
        cs, ct, cw = Hi[:, 0], Hi[:, 1], Hi[:, 2]
        cz = None
    else:
        p0 = S[:, 0]
        e1 = S[:, 1] - p0
        e2 = S[:, 3] - p0
        det = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
        keep &= np.abs(det) > 1e-9
        d = np.where(np.abs(det) > 1e-9, det, 1.0)
        cs = np.stack([e2[:, 1] / d, -e2[:, 0] / d, (-p0[:, 0] * e2[:, 1] + p0[:, 1] * e2[:, 0]) / d], -1)
        ct = np.stack([-e1[:, 1] / d, e1[:, 0] / d, (-e1[:, 0] * p0[:, 1] + e1[:, 1] * p0[:, 0]) / d], -1)
        z0 = Q[:, 0, 2]
        dz1 = Q[:, 1, 2] - z0
        dz3 = Q[:, 3, 2] - z0
        cz = cs * dz1[:, None] + ct * dz3[:, None]
        cz[:, 2] += z0
        cw = None
    th, tw = tex.shape[:2]
    kx, ky = tw / scene.geo.tex_w, th / scene.geo.tex_h
    uo, uds, udt, umin, umax, vmin, vmax = _uv_affine(scene.rect, scene.urot, kx, ky)
    umin = np.clip(umin, 0, tw - 1)
    umax = np.clip(umax, 0, tw - 1)
    vmin = np.clip(vmin, 0, th - 1)
    vmax = np.clip(vmax, 0, th - 1)
    shade = _shade(scene.n, proj, light)
    faces = np.nonzero(keep)[0]
    area = (w * h)[faces]
    if stats is not None:
        stats["faces"] = int(len(faces))
        stats["fragments"] = int(area.sum())
    if len(faces) == 0:
        return
    texf = tex.reshape(-1, 4)
    eps = 1e-6
    # 断片を _CHUNK 個ずつ（面の並びは保つ = z が同じなら先の面が勝つ）
    csum = np.cumsum(area)
    start = 0
    while start < len(faces):
        base = csum[start - 1] if start else 0
        end = int(np.searchsorted(csum, base + _CHUNK, side="right"))
        end = max(end, start + 1)
        fids = faces[start:end]
        a = area[start:end]
        start = end
        n = int(a.sum())
        fi = np.repeat(fids, a)
        loc = np.arange(n, dtype=np.int64) - np.repeat(np.cumsum(a) - a, a)
        wi = w[fi]
        yy = y0[fi] + loc // wi
        xx = x0[fi] + loc % wi
        qx = xx + 0.5
        qy = yy + 0.5
        sn = cs[fi, 0] * qx + cs[fi, 1] * qy + cs[fi, 2]
        tn = ct[fi, 0] * qx + ct[fi, 1] * qy + ct[fi, 2]
        if cw is not None:
            wv = cw[fi, 0] * qx + cw[fi, 1] * qy + cw[fi, 2]
            ok = wv > 0
            wv = np.where(ok, wv, 1.0)
            s = sn / wv
            t = tn / wv
            z = 1.0 / wv
        else:
            ok = np.ones(n, bool)
            s, t = sn, tn
            z = cz[fi, 0] * qx + cz[fi, 1] * qy + cz[fi, 2]
        ok &= (s >= -eps) & (s <= 1 + eps) & (t >= -eps) & (t <= 1 + eps)
        # 同じ平面に重なった面（耳・爪・デカールの貼り損ね）は浮動小数の誤差で勝ち負けが揺れるので、
        # 深さを 2^-16 単位に丸めて「同じ深さ = ファイルで先の面が勝つ」に揃える（毎回同じ絵になる）
        z = np.round(z * 65536.0) / 65536.0
        pix = yy * Wp + xx
        ok &= z < zbuf[pix]
        sel = np.nonzero(ok)[0]
        if len(sel) == 0:
            continue
        fi, s, t, z, pix = fi[sel], s[sel], t[sel], z[sel], pix[sel]
        u = uo[fi, 0] + s * uds[fi, 0] + t * udt[fi, 0]
        v = uo[fi, 1] + s * uds[fi, 1] + t * udt[fi, 1]
        ui = np.clip(np.floor(u).astype(np.int64), umin[fi], umax[fi])
        vi = np.clip(np.floor(v).astype(np.int64), vmin[fi], vmax[fi])
        texel = texf[vi * tw + ui]
        al = texel[:, 3]
        if alpha_test > 0:
            vis = al >= alpha_test
            if not vis.all():
                sel = np.nonzero(vis)[0]
                fi, z, pix, texel, al = fi[sel], z[sel], pix[sel], texel[sel], al[sel]
        if len(pix) == 0:
            continue
        k = shade[fi]
        if emissive:
            a = al.astype(np.float64) / 255.0
            k = k * a + emit_gain * (1.0 - a)
        col = texel[:, :3].astype(np.float32) * k[:, None].astype(np.float32)
        # 一番手前だけを残す（同じ深さなら先の面）
        np.minimum.at(zbuf, pix, z)
        win = np.nonzero(z <= zbuf[pix])[0][::-1]
        img[pix[win]] = col[win]
        cover[pix[win]] = True


def _floor(proj: _Proj, img: np.ndarray, zbuf: np.ndarray, cover: np.ndarray, ss: int,
           bg: np.ndarray, y_level: float = 0.0) -> None:
    """y = y_level の床（1 ブロックの市松と細い線。遠くは背景に溶かす）。"""
    Wp, Hp = proj.W * ss, proj.H * ss
    ys, xs = np.mgrid[0:Hp, 0:Wp]
    k = proj.scale * ss
    X = (xs + 0.5 - Wp / 2) / k + proj.ox
    Y = (Hp / 2 - (ys + 0.5)) / k + proj.oy
    if proj.persp:
        d = X[..., None] * proj.r + Y[..., None] * proj.u + proj.f        # 光線の向き
        o = np.broadcast_to(proj.origin, d.shape)
        dy = d[..., 1]
        lam = np.where(np.abs(dy) > 1e-9, (y_level - o[..., 1]) / np.where(np.abs(dy) > 1e-9, dy, 1), -1)
        hit = lam > proj.near
        Pw = o + d * lam[..., None]
        z = lam
    else:
        base = proj.origin + X[..., None] * proj.r + Y[..., None] * proj.u
        fy = proj.f[1]
        if abs(fy) < 1e-6:
            return
        D = (y_level - base[..., 1]) / fy
        Pw = base + D[..., None] * proj.f
        z = D
        hit = np.ones_like(D, bool)
    gx, gz = Pw[..., 0] / 16.0, Pw[..., 2] / 16.0
    chk = (np.floor(gx) + np.floor(gz)) % 2
    fx, fz = gx - np.floor(gx), gz - np.floor(gz)
    line = (np.minimum(fx, 1 - fx) < 0.015) | (np.minimum(fz, 1 - fz) < 0.015)
    c = np.where(chk[..., None] > 0, np.array([58, 60, 66.0]), np.array([50, 52, 58.0]))
    c = np.where(line[..., None], np.array([74, 76, 84.0]), c)
    dist = np.hypot(Pw[..., 0] - proj.target[0], Pw[..., 2] - proj.target[2])
    fade = np.clip(1.0 - dist / (proj.radius * 2.6 + 16), 0, 1)[..., None]
    c = bg[:3] * (1 - fade) + c * fade
    m = (hit & (z < zbuf.reshape(Hp, Wp))).reshape(-1)
    img[m] = c.reshape(-1, 3)[m]
    zbuf[m] = z.reshape(-1)[m]


def _size2(size) -> Tuple[int, int]:
    if isinstance(size, (tuple, list)):
        return int(size[0]), int(size[1])
    return int(size), int(size)


def _render_scene(scene: _Scene, tex: np.ndarray, cam: Camera, size, bg, *, ss: int = 1,
                  light="studio", alpha_test: int = 1, emissive: bool = True, emit_gain: float = 1.0,
                  cull: bool = True, floor: Union[bool, float] = False, show_locators: bool = False,
                  fit_scale: Optional[float] = None, stats: Optional[dict] = None) -> Image.Image:
    W, H = _size2(size)
    ss = max(1, int(ss))
    proj = _Proj(cam, W, H, scene.bounds_points(), fit_scale)
    Wp, Hp = W * ss, H * ss
    transparent = bg is None or (len(bg) == 4 and bg[3] < 255)
    bgc = np.array((bg or (0, 0, 0, 0))[:3], np.float32)
    img = np.empty((Hp * Wp, 3), np.float32)
    img[:] = bgc
    zbuf = np.full(Hp * Wp, np.inf)
    cover = np.zeros(Hp * Wp, bool)
    if floor is not False and floor is not None:
        _floor(proj, img, zbuf, cover, ss, bgc, 0.0 if floor is True else float(floor))
    t0 = time.perf_counter()
    _rasterize(scene, proj, tex, img, zbuf, cover, ss, light, alpha_test, emissive, emit_gain, cull, stats)
    if stats is not None:
        stats["raster_s"] = time.perf_counter() - t0
    rgb = np.clip(img, 0, 255).reshape(Hp, Wp, 3)
    if transparent:
        alpha = (cover | np.isfinite(zbuf)).reshape(Hp, Wp, 1).astype(np.float32) * 255
        out = Image.fromarray(np.concatenate([rgb, alpha], -1).round().astype(np.uint8), "RGBA")
    else:
        out = Image.fromarray(rgb.round().astype(np.uint8), "RGB")
    if ss > 1:
        out = out.reduce(ss)
    if show_locators and scene.geo.locators:
        dr = ImageDraw.Draw(out)
        font = _font(11)
        for name, (bi, off) in scene.geo.locators.items():
            if scene.geo.names[bi] in scene.hidden_bones:
                continue
            p = (scene.W[bi] @ np.append(off, 1.0))[:3]
            x, y = proj.project(p[None])[0]
            dr.line((x - 4, y, x + 4, y), fill=(255, 220, 40))
            dr.line((x, y - 4, x, y + 4), fill=(255, 220, 40))
            dr.text((x + 5, y - 6), name, fill=(255, 220, 40), font=font)
    return out


def render(geo, tex=None, view="three_quarter", size=512, pose: PoseLike = None, hidden=None,
           bg=(32, 32, 36), *, camera: Optional[Camera] = None, projection: Optional[str] = None,
           fov: Optional[float] = None, margin: Optional[float] = None, hide_mode: str = "subtree",
           faces: str = "bedrock", light="studio", alpha_test: int = 1, emissive: bool = True,
           emit_gain: float = 1.0, cull: bool = True, ss: int = 1, floor: Union[bool, float] = False,
           show_locators: bool = False, fit_scale: Optional[float] = None,
           warnings: Optional[List[str]] = None, stats: Optional[dict] = None) -> Image.Image:
    """1 枚描く。

    geo: パス / 辞書 / mcmodel.Model / Geometry。tex: パス / PIL / ndarray / None（市松）。
    view: VIEW_PRESETS の名前 / (yaw, pitch) / Camera（camera= でも渡せる）。
    pose: {bone: [rx,ry,rz] | {"rotation","position","scale"}}。hidden: 隠すボーン（ワイルドカード可）。
    bg: (r,g,b) / (r,g,b,a) / None（透過 PNG）。ss: スーパーサンプリング倍率。
    floor: True で y=0 に床、数値ならその高さ。stats: 渡すと面数・断片数・時間を書き込む。
    """
    t0 = time.perf_counter()
    g = load_geometry(geo)
    t = load_texture(tex, g)
    cam = camera_preset(camera if camera is not None else view, projection, fov, margin)
    scene = _Scene(g, pose, hidden, hide_mode, faces)
    out = _render_scene(scene, t, cam, size, bg, ss=ss, light=light, alpha_test=alpha_test,
                        emissive=emissive, emit_gain=emit_gain, cull=cull, floor=floor,
                        show_locators=show_locators, fit_scale=fit_scale, stats=stats)
    if warnings is not None:
        warnings.extend(w for w in scene.warnings if w not in warnings)
    if stats is not None:
        stats["total_s"] = time.perf_counter() - t0
        stats["cubes"] = g.cube_count
    return out


def render_views(geo, tex=None, views=("front", "back", "left", "right", "three_quarter"), size=512,
                 pose: PoseLike = None, hidden=None, bg=(32, 32, 36), *, cols: Optional[int] = None,
                 labels: Optional[Sequence[str]] = None, uniform: bool = True, title: Optional[str] = None,
                 projection: Optional[str] = None, fov: Optional[float] = None,
                 margin: Optional[float] = None, hide_mode: str = "subtree", faces: str = "bedrock",
                 warnings: Optional[List[str]] = None, **kw) -> Image.Image:
    """同じモデルを何方向かから描いて、ラベル付きの 1 枚に並べる。

    uniform=True なら全部の視点で同じ縮尺（一番きつい視点に合わせる）。kw は render と同じ。
    """
    g = load_geometry(geo)
    t = load_texture(tex, g)
    scene = _Scene(g, pose, hidden, hide_mode, faces)
    cams = [camera_preset(v, projection, fov, margin) for v in views]
    W, H = _size2(size)
    pts = scene.bounds_points()
    fits: Dict[bool, float] = {}
    if uniform:
        for c in cams:
            pr = _Proj(c, W, H, pts)
            fits[pr.persp] = min(fits.get(pr.persp, 1e18), pr.fit)
    tiles = []
    for i, (v, c) in enumerate(zip(views, cams)):
        fs = fits.get(c.projection.startswith("p")) if uniform else None
        im = _render_scene(scene, t, c, (W, H), bg, fit_scale=fs, **kw)
        if labels is not None:
            lab = labels[i]
        elif isinstance(v, str):
            lab = v
        else:
            lab = f"yaw {c.yaw:g} / pitch {c.pitch:g}"
        tiles.append((lab, im))
    if warnings is not None:
        warnings.extend(w for w in scene.warnings if w not in warnings)
    return contact_sheet(tiles, cols=cols or min(len(tiles), 5), title=title)


# ===========================================================================
#  コンタクトシート
# ===========================================================================

_FONT_PATHS = (
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
_FONT_CACHE: Dict[int, Any] = {}


def _font(size: int):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    f = None
    for p in _FONT_PATHS:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                break
            except OSError:
                continue
    if f is None:
        try:
            f = ImageFont.load_default(size=size)
        except TypeError:
            f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


def contact_sheet(items: Sequence[Tuple[str, Image.Image]], cols: Optional[int] = None, *, pad: int = 6,
                  bg=(16, 17, 21), fg=(230, 230, 232), font_size: Optional[int] = None,
                  title: Optional[str] = None) -> Image.Image:
    """[(ラベル, 画像), ...] → ラベル付きの格子（日本語のラベルも書ける）。"""
    items = list(items)
    if not items:
        return Image.new("RGB", (64, 64), bg)
    n = len(items)
    cols = cols or min(n, max(1, int(math.ceil(math.sqrt(n)))))
    rows = (n + cols - 1) // cols
    cw = max(im.size[0] for _, im in items)
    ch = max(im.size[1] for _, im in items)
    fs = font_size or max(11, min(18, cw // 22))
    font = _font(fs)
    lh = fs + 8 if any(lab for lab, _ in items) else 0
    th = (fs + 14) if title else 0
    Wt = cols * cw + (cols + 1) * pad
    Ht = th + rows * (ch + lh) + (rows + 1) * pad
    out = Image.new("RGB", (Wt, Ht), bg)
    dr = ImageDraw.Draw(out)
    if title:
        dr.text((pad + 2, pad // 2 + 3), title, fill=fg, font=_font(fs + 2))
    for i, (lab, im) in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = th + pad + r * (ch + lh + pad)
        if lab:
            dr.text((x + 3, y + 3), str(lab), fill=fg, font=font)
        ox = x + (cw - im.size[0]) // 2
        oy = y + lh + (ch - im.size[1]) // 2
        if im.mode == "RGBA":
            out.paste(im, (ox, oy), im)
        else:
            out.paste(im.convert("RGB"), (ox, oy))
    return out


# ===========================================================================
#  Molang（アニメーションと render controller で使う分）
# ===========================================================================


class MolangError(Exception):
    pass


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


_TOK_RE = re.compile(
    r"\s*(?:"
    r"((?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)f?"            # 1 数
    r"|('[^']*')"                                                # 2 文字列
    r"|([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"  # 3 名前（q.anim_time など）
    r"|(->|\?\?|&&|\|\||==|!=|<=|>=|[-+*/!<>?:(),;=\[\]{}])"    # 4 記号
    r")")


def _tokenize(src: str) -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    pos, n = 0, len(src)
    while pos < n:
        m = _TOK_RE.match(src, pos)
        if not m or m.end() == pos:
            if not src[pos:].strip():
                break
            raise MolangError(f"unexpected {src[pos:pos + 12]!r}")
        pos = m.end()
        num, s, name, op = m.groups()
        if num is not None:
            out.append(("num", float(num)))
        elif s is not None:
            out.append(("str", s[1:-1]))
        elif name is not None:
            out.append(("name", name.lower()))
        else:
            out.append(("op", op))
    return out


# 結合の強さ（大きいほど強い）。三項 < ?? < || < && < 等号 < 比較 < 加減 < 乗除 < 単項 < ->
_BP = {"?": 10, "??": 15, "||": 20, "&&": 30, "==": 40, "!=": 40, "<": 50, "<=": 50, ">": 50,
       ">=": 50, "+": 60, "-": 60, "*": 70, "/": 70, "->": 90}


class _Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self, k: int = 0):
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else ("eof", None)

    def next(self):
        t = self.peek()
        self.i += 1
        return t

    def accept(self, op: str) -> bool:
        if self.peek() == ("op", op):
            self.i += 1
            return True
        return False

    def expect(self, op: str):
        if not self.accept(op):
            raise MolangError(f"expected {op!r}, got {self.peek()[1]!r}")

    def program(self, until: Optional[str] = None):
        stmts = []
        while True:
            tok = self.peek()
            if tok[0] == "eof" or (until and tok == ("op", until)):
                break
            if self.accept(";"):
                continue
            stmts.append(self.statement())
            if not self.accept(";"):
                tok = self.peek()
                if tok[0] == "eof" or (until and tok == ("op", until)):
                    break
                raise MolangError(f"unexpected {tok[1]!r}")
        return stmts

    def statement(self):
        tok = self.peek()
        if tok == ("name", "return"):
            self.next()
            return ("return", self.expr(0))
        if tok == ("name", "break"):
            self.next()
            return ("break",)
        if tok == ("name", "continue"):
            self.next()
            return ("continue",)
        if tok[0] == "name" and self.peek(1) == ("op", "="):
            self.i += 2
            return ("assign", tok[1], self.expr(0))
        return ("expr", self.expr(0))

    def expr(self, rbp: int):
        left = self.nud()
        while True:
            tok = self.peek()
            if tok[0] != "op" or tok[1] not in _BP:
                break
            lbp = _BP[tok[1]]
            if lbp <= rbp:
                break
            self.next()
            op = tok[1]
            if op == "?":
                then = self.expr(0)
                if self.accept(":"):
                    left = ("tern", left, then, self.expr(lbp - 1))
                else:
                    left = ("cond", left, then)
            elif op == "??":
                left = ("coalesce", left, self.expr(lbp - 1))
            elif op == "->":
                left = ("arrow", left, self.expr(lbp))
            else:
                left = ("bin", op, left, self.expr(lbp))
        return left

    def nud(self):
        tok = self.next()
        kind, val = tok
        if kind == "num":
            return ("num", val)
        if kind == "str":
            return ("str", val)
        if kind == "name":
            if self.accept("("):
                args = []
                if not self.accept(")"):
                    while True:
                        args.append(self.expr(0))
                        if self.accept(")"):
                            break
                        self.expect(",")
                return ("call", val, args)
            if self.peek() == ("op", "["):
                raise MolangError("array indexing is not supported")
            return ("name", val)
        if kind == "op":
            if val == "(":
                e = self.expr(0)
                self.expect(")")
                return e
            if val == "-":
                return ("neg", self.expr(80))
            if val == "+":
                return self.expr(80)
            if val == "!":
                return ("not", self.expr(80))
            if val == "{":
                body = self.program(until="}")
                self.expect("}")
                return ("block", body)
        raise MolangError(f"unexpected {val!r}")


_PARSE_CACHE: Dict[str, Tuple[list, bool]] = {}


def _parse(src: str):
    hit = _PARSE_CACHE.get(src)
    if hit is None:
        toks = _tokenize(src)
        prog = _Parser(toks).program()
        simple = ("op", ";") not in toks
        hit = (prog, simple)
        if len(_PARSE_CACHE) > 20000:
            _PARSE_CACHE.clear()
        _PARSE_CACHE[src] = hit
    return hit


def _norm_keys(d: Optional[dict], prefixes: Sequence[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (d or {}).items():
        k = str(k).lower()
        for p in prefixes:
            if k.startswith(p):
                k = k[len(p):]
                break
        out[k] = v
    return out


class MolangContext:
    """Molang を評価する時の値。variables / queries / context は "v.x"・"variable.x"・"x" のどれでも渡せる。

    queries の値は数か呼べるもの（引数付きの query 用）。properties は q.property('nr:head') の値。
    """
    _MISSING = object()

    def __init__(self, variables=None, queries=None, properties=None, context=None, anim_time=0.0,
                 life_time=None, this=0.0, seed=0, warnings: Optional[List[str]] = None):
        self.vars = _norm_keys(variables, ("v.", "variable."))
        self.queries = _norm_keys(queries, ("q.", "query."))
        self.props = {str(k).lower(): v for k, v in (properties or {}).items()}
        self.ctxv = _norm_keys(context, ("c.", "context."))
        self.temps: Dict[str, Any] = {}
        self.anim_time = float(anim_time)
        self.life_time = float(anim_time if life_time is None else life_time)
        self.this = float(this)
        self.rng = random.Random(seed)
        self.warnings = warnings if warnings is not None else []

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    # -- 名前 ---------------------------------------------------------------
    def lookup(self, name: str, missing=_MISSING):
        head, _, rest = name.partition(".")
        if head in ("q", "query"):
            if rest == "anim_time":
                return self.anim_time
            if rest == "life_time":
                return self.life_time
            if rest in self.queries:
                v = self.queries[rest]
                return v() if callable(v) else v
        elif head in ("v", "variable"):
            if rest in self.vars:
                return self.vars[rest]
        elif head in ("t", "temp"):
            if rest in self.temps:
                return self.temps[rest]
        elif head in ("c", "context"):
            if rest in self.ctxv:
                return self.ctxv[rest]
        elif head == "math" and rest == "pi":
            return math.pi
        elif name == "this":
            return self.this
        elif name == "true":
            return 1.0
        elif name == "false":
            return 0.0
        if missing is not MolangContext._MISSING:
            return missing
        self.warn(f"molang: unknown name '{name}' -> 0")
        return 0.0

    def assign(self, name: str, value) -> None:
        head, _, rest = name.partition(".")
        if head in ("t", "temp"):
            self.temps[rest] = value
        elif head in ("v", "variable"):
            self.vars[rest] = value
        elif head in ("c", "context"):
            self.ctxv[rest] = value
        else:
            self.warn(f"molang: cannot assign to '{name}'")

    def call(self, name: str, args: list):
        head, _, rest = name.partition(".")
        if head == "math":
            fn = _MATH.get(rest)
            if fn is not None:
                try:
                    return float(fn(self, *[_num(a, self) for a in args]))
                except (TypeError, ValueError, OverflowError, ZeroDivisionError) as e:
                    self.warn(f"molang: math.{rest}{tuple(args)} failed ({e}) -> 0")
                    return 0.0
        elif head in ("q", "query"):
            if rest in ("property", "actor_property", "has_property") and args:
                key = str(args[0]).lower()
                if rest == "has_property":
                    return 1.0 if key in self.props else 0.0
                if key in self.props:
                    return self.props[key]
                self.warn(f"molang: property '{key}' not given -> 0")
                return 0.0
            if rest in self.queries:
                v = self.queries[rest]
                return v(*args) if callable(v) else v
        self.warn(f"molang: unsupported function '{name}' -> 0")
        return 0.0


def _num(v, ctx: MolangContext) -> float:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            ctx.warn(f"molang: string '{v}' used as a number -> 0")
            return 0.0
    if v is None:
        return 0.0
    ctx.warn(f"molang: value {v!r} used as a number -> 0")
    return 0.0


def _truth(v) -> bool:
    if isinstance(v, str):
        return v != ""
    return bool(v)


def _ev(node, ctx: MolangContext):
    k = node[0]
    if k == "num" or k == "str":
        return node[1]
    if k == "name":
        return ctx.lookup(node[1])
    if k == "bin":
        op = node[1]
        if op == "&&":
            return 1.0 if _truth(_ev(node[2], ctx)) and _truth(_ev(node[3], ctx)) else 0.0
        if op == "||":
            return 1.0 if _truth(_ev(node[2], ctx)) or _truth(_ev(node[3], ctx)) else 0.0
        a = _ev(node[2], ctx)
        b = _ev(node[3], ctx)
        if op in ("==", "!="):
            if isinstance(a, str) or isinstance(b, str):
                eq = isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()
            else:
                eq = abs(_num(a, ctx) - _num(b, ctx)) < 1e-9
            return 1.0 if eq == (op == "==") else 0.0
        a, b = _num(a, ctx), _num(b, ctx)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                ctx.warn("molang: division by zero -> 0")
                return 0.0
            return a / b
        if op == "<":
            return 1.0 if a < b else 0.0
        if op == "<=":
            return 1.0 if a <= b else 0.0
        if op == ">":
            return 1.0 if a > b else 0.0
        if op == ">=":
            return 1.0 if a >= b else 0.0
    if k == "neg":
        return -_num(_ev(node[1], ctx), ctx)
    if k == "not":
        return 0.0 if _truth(_ev(node[1], ctx)) else 1.0
    if k == "tern":
        return _ev(node[2], ctx) if _truth(_ev(node[1], ctx)) else _ev(node[3], ctx)
    if k == "cond":
        return _ev(node[2], ctx) if _truth(_ev(node[1], ctx)) else 0.0
    if k == "coalesce":
        left = node[1]
        if left[0] == "name":
            v = ctx.lookup(left[1], missing=None)
            return _ev(node[2], ctx) if v is None else v
        return _ev(left, ctx)
    if k == "arrow":
        ctx.warn("molang: '->' evaluated on the previewed entity itself")
        return _ev(node[2], ctx)
    if k == "call":
        name = node[1]
        if name == "loop":
            if len(node[2]) != 2:
                ctx.warn("molang: loop() needs 2 arguments -> 0")
                return 0.0
            count = int(min(max(_num(_ev(node[2][0], ctx), ctx), 0), 1024))
            body = node[2][1]
            for _ in range(count):
                try:
                    _ev(body, ctx)
                except _Break:
                    break
                except _Continue:
                    continue
            return 0.0
        if name == "for_each":
            ctx.warn("molang: for_each is not supported -> 0")
            return 0.0
        return ctx.call(name, [_ev(a, ctx) for a in node[2]])
    if k == "block":
        for st in node[1]:
            _exec(st, ctx)
        return 0.0
    raise MolangError(f"bad node {k}")


def _exec(st, ctx: MolangContext):
    k = st[0]
    if k == "expr":
        return _ev(st[1], ctx)
    if k == "assign":
        ctx.assign(st[1], _ev(st[2], ctx))
        return None
    if k == "return":
        raise _Return(_ev(st[1], ctx))
    if k == "break":
        raise _Break()
    if k == "continue":
        raise _Continue()
    raise MolangError(f"bad statement {k}")


def molang(expr, variables=None, queries=None, properties=None, context=None, anim_time=0.0,
           life_time=None, this=0.0, warnings: Optional[List[str]] = None,
           ctx: Optional[MolangContext] = None):
    """Molang の式を評価して値（数か文字列）を返す。分からない物は 0 にして warnings に積む。"""
    if isinstance(expr, bool):
        return 1.0 if expr else 0.0
    if isinstance(expr, (int, float)):
        return float(expr)
    if ctx is None:
        ctx = MolangContext(variables, queries, properties, context, anim_time, life_time, this,
                            warnings=warnings)
    src = str(expr)
    try:
        prog, simple = _parse(src)
    except MolangError as e:
        ctx.warn(f"molang: cannot parse {src[:60]!r} ({e}) -> 0")
        return 0.0
    ctx.temps = {}
    try:
        if simple and len(prog) == 1 and prog[0][0] == "expr":
            return _ev(prog[0][1], ctx)
        for st in prog:
            _exec(st, ctx)
        return 0.0
    except _Return as r:
        return r.value
    except (_Break, _Continue):
        return 0.0
    except MolangError as e:
        ctx.warn(f"molang: {e} in {src[:60]!r} -> 0")
        return 0.0
    except RecursionError:
        ctx.warn(f"molang: too deep {src[:60]!r} -> 0")
        return 0.0


# -- math.* ------------------------------------------------------------------


def _round(x):
    return math.floor(x + 0.5)


def _lerprotate(a, b, t):
    d = ((b - a + 180.0) % 360.0) - 180.0
    return a + d * t


def _min_angle(a):
    return ((a + 180.0) % 360.0) - 180.0


def _bounce_out(t):
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


_EASE_IN = {
    "quad": lambda t: t * t,
    "cubic": lambda t: t ** 3,
    "quart": lambda t: t ** 4,
    "quint": lambda t: t ** 5,
    "sine": lambda t: 1 - math.cos(t * math.pi / 2),
    "expo": lambda t: 0.0 if t <= 0 else 2 ** (10 * t - 10),
    "circ": lambda t: 1 - math.sqrt(max(0.0, 1 - t * t)),
    "back": lambda t: 2.70158 * t ** 3 - 1.70158 * t * t,
    "elastic": lambda t: (t if t in (0.0, 1.0) else
                          -(2 ** (10 * t - 10)) * math.sin((t * 10 - 10.75) * (2 * math.pi) / 3)),
    "bounce": lambda t: 1 - _bounce_out(1 - t),
}


def _make_ease(kind: str, mode: str):
    fin = _EASE_IN[kind]

    def e(t):
        t = min(max(t, 0.0), 1.0)
        if mode == "in":
            return fin(t)
        if mode == "out":
            return 1 - fin(1 - t)
        return fin(2 * t) / 2 if t < 0.5 else 1 - fin(2 - 2 * t) / 2

    return lambda c, a, b, t: a + (b - a) * e(t)


_MATH = {
    "abs": lambda c, x: abs(x),
    "acos": lambda c, x: math.degrees(math.acos(min(1.0, max(-1.0, x)))),
    "asin": lambda c, x: math.degrees(math.asin(min(1.0, max(-1.0, x)))),
    "atan": lambda c, x: math.degrees(math.atan(x)),
    "atan2": lambda c, y, x: math.degrees(math.atan2(y, x)),
    "ceil": lambda c, x: math.ceil(x),
    "clamp": lambda c, v, lo, hi: min(max(v, lo), hi),
    "cos": lambda c, x: math.cos(math.radians(x)),
    "sin": lambda c, x: math.sin(math.radians(x)),
    "exp": lambda c, x: math.exp(x),
    "floor": lambda c, x: math.floor(x),
    "hermite_blend": lambda c, t: 3 * t * t - 2 * t ** 3,
    "lerp": lambda c, a, b, t: a + (b - a) * t,
    "lerprotate": lambda c, a, b, t: _lerprotate(a, b, t),
    "inverse_lerp": lambda c, a, b, v: 0.0 if b == a else (v - a) / (b - a),
    "ln": lambda c, x: math.log(x),
    "max": lambda c, a, b: max(a, b),
    "min": lambda c, a, b: min(a, b),
    "min_angle": lambda c, a: _min_angle(a),
    "mod": lambda c, a, b: 0.0 if b == 0 else math.fmod(a, b),
    "pow": lambda c, a, b: a ** b,
    "random": lambda c, lo, hi: c.rng.uniform(lo, hi),
    "random_integer": lambda c, lo, hi: c.rng.randint(int(min(lo, hi)), int(max(lo, hi))),
    "die_roll": lambda c, n, lo, hi: sum(c.rng.uniform(lo, hi) for _ in range(max(0, int(n)))),
    "die_roll_integer": lambda c, n, lo, hi: sum(c.rng.randint(int(lo), int(hi)) for _ in range(max(0, int(n)))),
    "round": lambda c, x: _round(x),
    "sqrt": lambda c, x: math.sqrt(x) if x >= 0 else 0.0,
    "trunc": lambda c, x: math.trunc(x),
    "sign": lambda c, x: -1.0 if x < 0 else 1.0,
    "copy_sign": lambda c, a, b: math.copysign(a, b),
    "pi": lambda c: math.pi,
}
for _k in _EASE_IN:
    for _m in ("in", "out", "in_out"):
        _MATH[f"ease_{_m}_{_k}"] = _make_ease(_k, _m)


# ===========================================================================
#  アニメーション
# ===========================================================================


def load_animations(src) -> Dict[str, dict]:
    """animation.json のパス / 辞書 → {クリップ名: クリップ}。"""
    if isinstance(src, (str, os.PathLike)):
        with open(src, encoding="utf-8") as fh:
            src = json.load(fh)
    if not isinstance(src, dict):
        raise TypeError("animation must be a path or a dict")
    if "animations" in src:
        return src["animations"]
    if "bones" in src or "animation_length" in src:
        return {"clip": src}
    return src


class _Key:
    __slots__ = ("t", "pre", "post", "lerp", "split")

    def __init__(self, t, pre, post, lerp, split):
        self.t, self.pre, self.post, self.lerp, self.split = t, pre, post, lerp, split


def _raw3(v):
    """チャンネルの値（数・文字列・配列）→ 3 要素。"""
    if isinstance(v, (list, tuple)):
        a = list(v)
        if len(a) == 1:
            return [a[0]] * 3
        while len(a) < 3:
            a.append(0)
        return a[:3]
    return [v, v, v]


def _keys_of(ch) -> List[_Key]:
    if isinstance(ch, dict):
        try:
            times = [(float(k), k) for k in ch]
        except ValueError:
            times = None
        if times is not None and times:
            out = []
            for tf, k in sorted(times):
                kv = ch[k]
                if isinstance(kv, dict):
                    pre = kv.get("pre", kv.get("post", kv.get("vector", 0)))
                    post = kv.get("post", kv.get("pre", kv.get("vector", 0)))
                    split = "pre" in kv and "post" in kv
                    lerp = str(kv.get("lerp_mode", "linear")).lower()
                else:
                    pre = post = kv
                    split = False
                    lerp = "linear"
                out.append(_Key(tf, _raw3(pre), _raw3(post), lerp, split))
            return out
        v = ch.get("post", ch.get("pre", ch.get("vector", 0)))
        return [_Key(0.0, _raw3(v), _raw3(v), "linear", False)]
    return [_Key(0.0, _raw3(ch), _raw3(ch), "linear", False)]


def _eval3(raw, ctx: MolangContext) -> np.ndarray:
    out = np.zeros(3)
    for i, v in enumerate(raw):
        r = molang(v, ctx=ctx) if isinstance(v, str) else v
        out[i] = _num(r, ctx)
    return out


def _catmull(p0, p1, p2, p3, s):
    return 0.5 * (2 * p1 + (p2 - p0) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                  + (3 * p1 - p0 - 3 * p2 + p3) * s * s * s)


def _sample_keys(keys: List[_Key], tau: float, ctx: MolangContext, loop: bool, length: float) -> np.ndarray:
    eps = 1.0 / 1200.0
    if len(keys) == 1:
        k = keys[0]
        return _eval3(k.pre if tau <= k.t + eps else k.post, ctx)
    before = after = None
    bt = at = 0.0
    for k in keys:
        if k.t < tau:
            if before is None or k.t > bt:
                before, bt = k, k.t
        elif after is None or k.t < at:
            after, at = k, k.t
    if loop and length > 0:
        if before is None:
            before, bt = keys[-1], keys[-1].t - length
        if after is None:
            after, at = keys[0], keys[0].t + length
    if before is not None and abs(bt - tau) < eps:
        return _eval3(before.pre, ctx)
    if after is not None and abs(at - tau) < eps:
        return _eval3(after.pre, ctx)
    if before is not None and before.lerp == "step":
        return _eval3(before.post, ctx)
    if after is None:
        return _eval3(before.post, ctx)
    if before is None:
        return _eval3(after.pre, ctx)
    alpha = (tau - bt) / (at - bt) if at > bt else 0.0
    p1 = _eval3(before.post, ctx)
    p2 = _eval3(after.pre, ctx)
    if before.lerp == "catmullrom" or after.lerp == "catmullrom":
        bi = keys.index(before)
        ai = keys.index(after)
        bp = keys[bi - 1] if bi - 1 >= 0 else None
        ap = keys[ai + 1] if ai + 1 < len(keys) else None
        if loop and len(keys) >= 3:
            bp = bp if bp is not None else keys[-2]
            ap = ap if ap is not None else keys[1]
        p0 = _eval3(bp.post, ctx) if (bp is not None and not before.split) else p1
        p3 = _eval3(ap.pre, ctx) if (ap is not None and not after.split) else p2
        return _catmull(p0, p1, p2, p3, alpha)
    if before.lerp not in ("linear", "step") or after.lerp not in ("linear", "step"):
        ctx.warn(f"anim: lerp_mode '{before.lerp}/{after.lerp}' treated as linear")
    return p1 + (p2 - p1) * alpha


def _clip_length(clip: dict) -> float:
    L = clip.get("animation_length")
    if isinstance(L, (int, float)):
        return float(L)
    mx = 0.0
    for tracks in (clip.get("bones") or {}).values():
        for ch in tracks.values():
            if isinstance(ch, dict):
                for k in ch:
                    try:
                        mx = max(mx, float(k))
                    except ValueError:
                        pass
    return mx


def animation_pose(anims, clip, t: float = 0.0, *, bones=None, variables=None, queries=None,
                   properties=None, context=None, life_time: Optional[float] = None, weight: float = 1.0,
                   seed: int = 0, warnings: Optional[List[str]] = None) -> Tuple[Dict[str, dict], List[str]]:
    """アニメーションのクリップを時刻 t（秒）で評価して (pose, warnings) を返す。

    anims: animation.json のパス / 辞書 / {名前: クリップ} / クリップそのもの。
    clip: クリップ名、または [(名前, t), (名前, t, weight), ...] で複数を足し合わせる。
    bones: Geometry / ボーン名の並び（与えると大文字小文字を合わせ、無いボーンを warnings に書く）。
    pose は render(pose=...) にそのまま渡せる {bone: {"rotation", "position", "scale"}}。
    """
    warns = warnings if warnings is not None else []
    lib = load_animations(anims)
    if isinstance(clip, (list, tuple)) and clip and isinstance(clip[0], (list, tuple)):
        poses = []
        for item in clip:
            name, tt = item[0], float(item[1])
            w = float(item[2]) if len(item) > 2 else 1.0
            p, _ = animation_pose(lib, name, tt, bones=bones, variables=variables, queries=queries,
                                  properties=properties, context=context, life_time=life_time,
                                  weight=w * weight, seed=seed, warnings=warns)
            poses.append(p)
        return merge_poses(*poses), warns
    if isinstance(clip, dict):                       # クリップそのもの
        c, cname = clip, "clip"
    elif clip in lib:
        c, cname = lib[clip], clip
    elif list(lib) == ["clip"]:                       # anims がクリップ 1 本だけだった
        c, cname = lib["clip"], str(clip)
    else:
        low = {k.lower(): k for k in lib}
        if str(clip).lower() not in low:
            raise KeyError(f"animation {clip!r} not found")
        cname = low[str(clip).lower()]
        c = lib[cname]
    length = _clip_length(c)
    loop = c.get("loop", False)
    tau_keys = None
    if loop is True and length > 0:
        tau = math.fmod(max(t, 0.0), length)
    elif length > 0:
        tau = min(max(t, 0.0), length)
        if t > length:              # 終わった後は最後のキーの post で止まる（キーちょうどの pre にしない）
            tau_keys = length + 0.002
    else:
        tau = max(t, 0.0)
    ctx = MolangContext(variables, queries, properties, context, anim_time=tau,
                        life_time=t if life_time is None else life_time, seed=seed, warnings=warns)
    if "anim_time_update" in c:
        ctx.warn(f"anim {cname}: anim_time_update ignored (anim_time = t)")
    w = weight
    if "blend_weight" in c:
        w *= _num(molang(c["blend_weight"], ctx=ctx), ctx)
    names = None
    if bones is not None:
        names = {n.lower(): n for n in (bones.names if isinstance(bones, Geometry) else bones)}
    pose: Dict[str, dict] = {}
    for bname, tracks in (c.get("bones") or {}).items():
        target = bname
        if names is not None:
            target = names.get(bname.lower())
            if target is None:
                ctx.warn(f"anim {cname}: bone '{bname}' not in geometry")
                continue
        if not isinstance(tracks, dict):
            continue
        entry: Dict[str, list] = {}
        for chn in ("rotation", "position", "scale"):
            if chn not in tracks:
                continue
            val = _sample_keys(_keys_of(tracks[chn]), tau if tau_keys is None else tau_keys, ctx,
                               loop is True, length)
            if chn == "scale":
                val = 1.0 + (val - 1.0) * w
            else:
                val = val * w
            entry[chn] = [float(x) for x in val]
        for extra in tracks:
            if extra not in ("rotation", "position", "scale", "relative_to"):
                ctx.warn(f"anim {cname}: channel '{extra}' ignored")
        if entry:
            pose[target] = entry
    return pose, warns


def merge_poses(*poses: PoseLike) -> Dict[str, dict]:
    """pose を足し合わせる（rotation / position は和、scale は積）。[rx,ry,rz] 形式も混ぜてよい。"""
    out: Dict[str, dict] = {}
    for p in poses:
        for b, v in (p or {}).items():
            e = out.setdefault(b, {})
            if not isinstance(v, dict):
                v = {"rotation": v}
            for ch in ("rotation", "position"):
                if ch in v:
                    e[ch] = list(np.add(e.get(ch, [0.0, 0.0, 0.0]), _vec3(v[ch])))
            if "scale" in v:
                e["scale"] = list(np.multiply(e.get("scale", [1.0, 1.0, 1.0]), _vec3(v["scale"])))
    return out


def render_clip(geo, tex, anims, clip: str, times: Sequence[float], view="three_quarter", size=320,
                *, variables=None, queries=None, properties=None, hidden=None, per_frame=None,
                warnings: Optional[List[str]] = None, **kw) -> List[Tuple[str, Image.Image]]:
    """クリップを何コマか描いて [(ラベル, 画像), ...] を返す（contact_sheet に渡す）。縮尺は全コマ共通。

    per_frame: t → {"q.modified_distance_moved": ..., "v.x": ...} のような関数。コマごとに queries /
    variables へ足す（歩きのように anim_time ではなく移動距離で動くクリップ用）。
    """
    g = load_geometry(geo)
    t = load_texture(tex, g)
    warns = warnings if warnings is not None else []
    poses = []
    for tt in times:
        q = dict(queries or {})
        v = dict(variables or {})
        for k, val in (per_frame(tt) if per_frame else {}).items():
            (v if str(k).lower().startswith(("v.", "variable.")) else q)[k] = val
        poses.append(animation_pose(anims, clip, tt, bones=g, variables=v, queries=q,
                                    properties=properties, warnings=warns)[0])
    cam = camera_preset(view, kw.pop("projection", None), kw.pop("fov", None), kw.pop("margin", None))
    W, H = _size2(size)
    hide_mode = kw.pop("hide_mode", "subtree")
    faces = kw.pop("faces", "bedrock")
    bg = kw.pop("bg", (32, 32, 36))
    scenes = [_Scene(g, p, hidden, hide_mode, faces) for p in poses]
    pts = np.concatenate([s.bounds_points() for s in scenes] or [np.zeros((1, 3))])
    proj = _Proj(cam, W, H, pts)
    if cam.target is None:
        cam = replace(cam, target=tuple(proj.target))
        proj = _Proj(cam, W, H, pts)
    out = []
    for tt, sc in zip(times, scenes):
        out.append((f"{clip.split('.')[-1]} t={tt:.2f}",
                    _render_scene(sc, t, cam, (W, H), bg, fit_scale=proj.fit, **kw)))
    return out


# ===========================================================================
#  render controller の part_visibility
# ===========================================================================


# DESIGN.md §3 のゾンビのエンティティプロパティの既定値（render controller を評価する時の土台）
NR_ZOMBIE_DEFAULTS: Dict[str, Any] = {
    "nr:head": "intact", "nr:arm_r": "intact", "nr:arm_l": "intact", "nr:leg_r": "intact",
    "nr:leg_l": "intact", "nr:torso": "intact", "nr:blood": 0, "nr:burn": 0, "nr:shock": 0,
    "nr:armor": 3, "nr:state": "normal", "nr:pose": 0, "nr:ability": 0, "nr:variant": 0,
}


def part_visibility_hidden(rc, bones, properties=None, variables=None, queries=None,
                           controller: Optional[str] = None,
                           warnings: Optional[List[str]] = None,
                           defaults: Optional[Dict[str, Any]] = None) -> set:
    """part_visibility を評価して「隠れるボーン名」の集合を返す（render の hidden に渡す）。

    rc: RP の render_controllers JSON のパス / 辞書 / 1 つのコントローラ / [{"pat": expr}, ...] /
        [(pat, expr), ...]（nr_rig.visibility_rules の形）。後に書いた規則が前を上書きする（統合版と同じ）。
    bones: Geometry かボーン名の並び。子が隠れるのは render の hide_mode="subtree" に任せる。
    defaults: properties に無いプロパティの値（ゾンビなら NR_ZOMBIE_DEFAULTS）。
    """
    if defaults:
        merged = dict(defaults)
        merged.update(properties or {})
        properties = merged
    if isinstance(rc, (str, os.PathLike)):
        with open(rc, encoding="utf-8") as fh:
            rc = json.load(fh)
    rules: List[Tuple[str, Any]] = []
    if isinstance(rc, dict):
        if "render_controllers" in rc:
            ctrls = rc["render_controllers"]
            if controller is None:
                if len(ctrls) != 1:
                    raise ValueError(f"choose controller= from {list(ctrls)}")
                controller = next(iter(ctrls))
            rc = ctrls[controller]
        pv = rc.get("part_visibility", [])
    else:
        pv = rc
    for item in pv:
        if isinstance(item, dict):
            rules.extend(item.items())
        else:
            rules.append((item[0], item[1]))
    names = bones.names if isinstance(bones, Geometry) else list(bones)
    ctx = MolangContext(variables, queries, properties, warnings=warnings)
    vis = {n: True for n in names}
    for pat, expr in rules:
        p = str(pat).lower()
        val = _truth(molang(expr, ctx=ctx)) if not isinstance(expr, bool) else expr
        for n in names:
            if fnmatch.fnmatchcase(n.lower(), p):
                vis[n] = val
    return {n for n, v in vis.items() if not v}


# ===========================================================================
#  CLI
# ===========================================================================


def _kv_list(items: Optional[List[str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"expected key=value, got {it!r}")
        k, v = it.split("=", 1)
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = v
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="NIGHT RUNNER のモデルを描く（QA・README 用）")
    ap.add_argument("geo", nargs="?", help="geo.json")
    ap.add_argument("tex", nargs="?", help="texture PNG（省略で市松）")
    ap.add_argument("-o", "--out", help="出力 PNG（既定 build_preview/nightrunner/<名前>.png）")
    ap.add_argument("--identifier", help="複数のジオメトリが入っている時に選ぶ")
    ap.add_argument("--hide", default="", help="隠すボーン（カンマ区切り・ワイルドカード可）")
    ap.add_argument("--exact", action="store_true", help="隠すのはそのボーンだけ（子は残す）")
    ap.add_argument("--views", default="front,back,left,right,three_quarter")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--persp", action="store_true", help="透視投影")
    ap.add_argument("--fov", type=float, default=None)
    ap.add_argument("--ss", type=int, default=1, help="スーパーサンプリング倍率")
    ap.add_argument("--floor", action="store_true")
    ap.add_argument("--locators", action="store_true")
    ap.add_argument("--light", default="studio", choices=["studio", "mc", "hd", "none"])
    ap.add_argument("--bg", default="32,32,36", help="r,g,b か 'none'（透過）")
    ap.add_argument("--legacy-faces", action="store_true", help="east/west を旧来（preview.py）の並びで")
    ap.add_argument("--no-cull", action="store_true")
    ap.add_argument("--anim", help="animation.json")
    ap.add_argument("--clip", help="クリップ名（--anim と一緒に）")
    ap.add_argument("--t", type=float, default=0.0, help="時刻（秒）")
    ap.add_argument("--frames", type=int, default=0, help="クリップを N コマ並べる")
    ap.add_argument("--var", action="append", help="v.x=1（何度でも）")
    ap.add_argument("--query", action="append", help="q.x=1（何度でも）")
    ap.add_argument("--prop", action="append", help="nr:head=severed（何度でも）")
    ap.add_argument("--rc", help="render_controllers JSON（--prop で part_visibility を評価）")
    ap.add_argument("--rc-name", help="render controller の名前")
    ap.add_argument("--no-nr-defaults", action="store_true",
                    help="--rc の評価でゾンビのプロパティ既定値（DESIGN §3）を土台にしない")
    ap.add_argument("--move-speed", type=float, default=None,
                    help="q.modified_distance_moved = 速さ×t、q.modified_move_speed = 1 にする（歩き用）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest(SCRATCH)
    if not a.geo:
        ap.error("geo.json is required")
    geo = load_geometry(a.geo, a.identifier)
    tex = load_texture(a.tex, geo)
    warns: List[str] = []
    hidden = {h for h in a.hide.split(",") if h}
    props = _kv_list(a.prop)
    queries = _kv_list(a.query)
    if a.move_speed is not None:
        queries.setdefault("modified_move_speed", 1.0)
    if a.rc:
        hidden |= part_visibility_hidden(a.rc, geo, props, _kv_list(a.var), queries, a.rc_name, warns,
                                         defaults=None if a.no_nr_defaults else NR_ZOMBIE_DEFAULTS)
    bg = None if a.bg == "none" else tuple(int(x) for x in a.bg.split(","))
    common = dict(hide_mode="exact" if a.exact else "subtree",
                  faces="legacy" if a.legacy_faces else "bedrock",
                  light=None if a.light == "none" else a.light, ss=a.ss, floor=a.floor,
                  show_locators=a.locators, cull=not a.no_cull)
    proj = "persp" if a.persp else None
    pose = None
    if a.anim and a.clip:
        if a.frames > 0:
            lib = load_animations(a.anim)
            length = _clip_length(lib[a.clip]) or 1.0
            n = a.frames
            times = [length * i / (n if lib[a.clip].get("loop") is True else max(1, n - 1)) for i in range(n)]
            view = a.views.split(",")[0]
            speed = a.move_speed
            per = (lambda tt: {"modified_distance_moved": speed * tt}) if speed is not None else None
            tiles = render_clip(geo, tex, lib, a.clip, times, view=view, size=a.size,
                                variables=_kv_list(a.var), queries=queries, properties=props,
                                hidden=hidden, per_frame=per, warnings=warns, projection=proj, fov=a.fov,
                                bg=bg, **common)
            img = contact_sheet(tiles, cols=min(n, 6), title=f"{os.path.basename(a.geo)}  {a.clip}")
            return _save_cli(img, a, warns)
        if a.move_speed is not None:
            queries.setdefault("modified_distance_moved", a.move_speed * a.t)
        pose, _ = animation_pose(a.anim, a.clip, a.t, bones=geo, variables=_kv_list(a.var),
                                 queries=queries, properties=props, warnings=warns)
    views = [v for v in a.views.split(",") if v]
    if len(views) == 1 and bg is None:          # 透過 PNG 1 枚（README・アイコン用）はラベル無しでそのまま
        img = render(geo, tex, views[0], a.size, pose, hidden, None, projection=proj, fov=a.fov,
                     warnings=warns, **common)
        return _save_cli(img, a, warns)
    title = os.path.basename(a.geo)
    if a.clip:
        title += f"  {a.clip} t={a.t:g}"
    if hidden:
        title += f"  hidden: {','.join(sorted(hidden))[:80]}"
    img = render_views(geo, tex, views, a.size, pose, hidden, bg, projection=proj, fov=a.fov,
                       title=title, warnings=warns, **common)
    return _save_cli(img, a, warns)


def _save_cli(img: Image.Image, a, warns: List[str]) -> int:
    out = a.out or os.path.join(SCRATCH, os.path.basename(a.geo).split(".")[0] + ".png")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out)
    for w in warns:
        print("WARN", w)
    print(f"wrote {out} ({img.size[0]}x{img.size[1]})")
    return 0


# ===========================================================================
#  自己テスト
# ===========================================================================


def _selftest(out_dir: str) -> int:  # noqa: C901
    os.makedirs(out_dir, exist_ok=True)
    errors: List[str] = []
    notes: List[str] = []

    def check(cond, msg):
        print(("ok  " if cond else "NG  ") + msg)
        if not cond:
            errors.append(msg)

    # 1) 回転の規則が hd_space.rot と同じ
    sys.path.insert(0, os.path.join(TOOLS, "hyperdim"))
    try:
        import hd_space  # type: ignore
        rng = np.random.default_rng(7)
        worst = max(float(np.abs(rot(*a) - hd_space.rot(*a)).max())
                    for a in rng.uniform(-180, 180, (64, 3)))
        check(worst < 1e-12, f"rot() == hd_space.rot (max diff {worst:.1e})")
    except ImportError as e:
        check(False, f"hd_space import ({e})")
    arm = rot(-90, 0, 0) @ np.array([0, -1.0, 0])
    check(np.allclose(arm, [0, 0, -1]), "rx=-90 raises a hanging arm forward (-Z)")
    check(np.allclose(rot(0, 90, 0) @ np.array([0, 0, -1.0]), [-1, 0, 0]),
          "ry=+90 turns the face (-Z) to the body's right (-X)")

    # 2) 面の表: 各面の色で east/west と UV の向きを確かめる
    tex = np.zeros((16, 64, 4), np.uint8)
    tex[..., 3] = 255
    face_col = {"north": (230, 40, 40), "south": (40, 200, 40), "east": (40, 80, 240),
                "west": (240, 200, 40), "up": (240, 240, 240), "down": (160, 60, 200)}
    for k, f in enumerate(FACE_NAMES):
        x0 = k * 8
        tex[0:8, x0:x0 + 8, :3] = face_col[f]
        tex[0:4, x0:x0 + 4, :3] = (0, 0, 0)          # 左上の 4x4 を黒（UV の向きの目印）
    cube_doc = {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.test.faces", "texture_width": 64, "texture_height": 16},
        "bones": [{"name": "root", "pivot": [0, 0, 0], "cubes": [{
            "origin": [-4, 0, -4], "size": [8, 8, 8],
            "uv": {f: {"uv": [k * 8, 0], "uv_size": [8, 8]} for k, f in enumerate(FACE_NAMES)}}]}]}]}
    g = load_geometry(cube_doc)

    def probe(view, faces="bedrock"):
        im = np.asarray(render(g, tex, view, 64, light=None, faces=faces, bg=(0, 0, 0),
                               camera=Camera(*VIEW_PRESETS[view], margin=0.0)).convert("RGB"))
        # 面の中心近くの右下（色）と左上（黒の目印）
        return tuple(int(x) for x in im[44, 44]), tuple(int(x) for x in im[18, 18])

    expect = {"front": "north", "back": "south", "right": "east", "left": "west", "top": "up",
              "bottom": "down"}
    for view, face in expect.items():
        col, mark = probe(view)
        check(col == face_col[face] and mark == (0, 0, 0),
              f"view {view:6s} shows '{face}' unmirrored (got {col}, mark {mark})")
    col, _ = probe("right", "legacy")
    check(col == face_col["west"], "faces='legacy' reproduces preview.py/hd_scene (west on the -X side)")
    # ボックス UV: スキンの頭（最初の帯 = 体の右 = east）
    r = box_uv_rects(0, 0, (8, 8, 8))
    check(r["east"] == (0, 8, 8, 8) and r["north"] == (8, 8, 8, 8) and r["up"] == (8, 0, 8, 8)
          and r["down"] == (16, 8, 8, -8) and r["south"] == (24, 8, 8, 8), "box uv layout (skin head)")
    rm = box_uv_rects(0, 0, (8, 8, 8), mirror=True)
    check(rm["east"] == (24, 8, -8, 8) and rm["west"] == (8, 8, -8, 8), "box uv mirror")

    # 3) Molang
    warns: List[str] = []
    cases = [
        ("1 + 2 * 3", {}, 7.0),
        ("-2 * -3 + 1", {}, 7.0),
        ("(1 + 2) * 3", {}, 9.0),
        ("math.sin(90) + math.cos(0)", {}, 2.0),
        ("math.clamp(5, 0, 2) + math.abs(-1)", {}, 3.0),
        ("q.anim_time * 2", {"anim_time": 1.5}, 3.0),
        ("v.is_first_person ? 1 : (-2)", {"variables": {"v.is_first_person": 0}}, -2.0),
        ("v.a ?? 4", {}, 4.0),
        ("v.a ?? 4", {"variables": {"variable.a": 1}}, 1.0),
        ("v.x > 1 && v.x < 3", {"variables": {"x": 2}}, 1.0),
        ("t.a = 3; t.b = t.a * 2; return t.b + 1;", {}, 7.0),
        ("q.property('nr:head') == 'severed'", {"properties": {"nr:head": "severed"}}, 1.0),
        ("q.property('nr:head') != 'severed' && q.property('nr:armor') >= 1",
         {"properties": {"nr:head": "intact", "nr:armor": 2}}, 1.0),
        ("Math.Lerp(0, 10, 0.25)", {}, 2.5),
        ("v.n = 0; loop(4, {v.n = v.n + 2;}); return v.n;", {}, 8.0),
        ("1 ? 5", {}, 5.0),
        ("0 ? 5", {}, 0.0),
        ("math.ease_in_out_quad(0, 10, 0.5)", {}, 5.0),
        ("c.owning_entity->v.attack_time", {"variables": {"attack_time": 0.5}}, 0.5),
        ("math.mod(7, 3) + math.round(2.5) + math.trunc(-1.7)", {}, 3.0),
    ]
    for src, kw, want in cases:
        got = molang(src, warnings=warns, **kw)
        check(abs(_num(got, MolangContext()) - want) < 1e-9, f"molang {src!r} = {got} (want {want})")
    w2: List[str] = []
    check(molang("q.unknown_thing + v.nope + query.nothing(2)", warnings=w2) == 0.0 and len(w2) == 3,
          f"unknown molang -> 0 with warnings ({len(w2)})")
    w3: List[str] = []
    check(molang("1 + + (", warnings=w3) == 0.0 and w3, "unparsable molang -> 0 with a warning")
    # nr_rig が作る part_visibility を、nr_rig 自身の Python 評価（visible_bones）と突き合わせる
    try:
        import nr_rig  # type: ignore
        m = nr_rig.new_model("pv_check")
        nr_rig.ZombieRig(m, nr_rig.SAMPLE_BUILDS["average"])
        m.pack(size=(512, 512))
        pv = nr_rig.part_visibility(nr_rig.visibility_rules(m))
        RGm = load_geometry(m)
        rsv = random.Random(11)
        agree = 0
        total = 120
        for _ in range(total):
            st = {k: (rsv.choice(v["values"]) if "values" in v else rsv.randint(*v["range"]))
                  for k, v in nr_rig.PROPERTIES.items() if "values" in v or "range" in v}
            wv: List[str] = []
            hid = part_visibility_hidden(pv, RGm, st, warnings=wv, defaults=NR_ZOMBIE_DEFAULTS)
            mask = _hidden_mask(RGm, hid, "subtree")
            mine_vis = {RGm.names[i] for i in range(len(RGm.names)) if not mask[i]}
            agree += int(mine_vis == nr_rig.visible_bones(m, st) and not wv)
        check(agree == total, f"part_visibility of nr_rig agrees with nr_rig.visible_bones ({agree}/{total})")
    except Exception as e:  # noqa: BLE001  （nr_rig は別の担当が書いている途中のことがある）
        notes.append(f"skip nr_rig part_visibility cross-check ({type(e).__name__}: {e})")

    # 4) キーフレーム
    clip = {"loop": False, "animation_length": 2.0, "bones": {"b": {
        "rotation": {"0.0": [0, 0, 0], "1.0": [10, 20, 30], "2.0": {"pre": [40, 0, 0], "post": [0, 0, 0]}},
        "position": {"0.0": {"post": [0, 0, 0], "lerp_mode": "catmullrom"},
                     "1.0": {"post": [0, 10, 0], "lerp_mode": "catmullrom"},
                     "2.0": {"post": [0, 0, 0], "lerp_mode": "catmullrom"}},
        "scale": "1 + q.anim_time"}}}
    p, _ = animation_pose(clip, "clip", 0.5)
    check(np.allclose(p["b"]["rotation"], [5, 10, 15]), "linear keyframes")
    check(abs(p["b"]["position"][1] - 5.625) < 1e-9, f"catmullrom keyframes ({p['b']['position'][1]})")
    check(np.allclose(p["b"]["scale"], [1.5] * 3), "molang channel uses q.anim_time")
    p, _ = animation_pose(clip, "clip", 1.5)
    check(np.allclose(p["b"]["rotation"], [25, 10, 15]), "lerp toward 'pre' of the next key")
    p, _ = animation_pose(clip, "clip", 9.0)
    check(np.allclose(p["b"]["rotation"], [0, 0, 0]), "non-loop clip holds the last 'post'")
    loopclip = {"loop": True, "animation_length": 1.0, "bones": {"b": {"rotation": {
        "0.25": [10, 0, 0], "0.75": [30, 0, 0]}}}}
    p, _ = animation_pose(loopclip, "clip", 1.0)   # 折り返し: 0.75(30) → 1.25(10) の中間 = 20
    check(np.allclose(p["b"]["rotation"], [20, 0, 0]), "loop wraps keys around the end")

    # 5) 実際のモデル: hd_scene と比べる（faces="legacy"・同じ光で画素が一致するか）
    compare_tiles: List[Tuple[str, Image.Image]] = []
    try:
        import hd_scene  # type: ignore
        models = [
            ("kaiju8 honju", os.path.join(ROOT, "packs/kaiju8_RP/models/entity/honju.geo.json"),
             os.path.join(ROOT, "packs/kaiju8_RP/textures/entity/kaiju8/honju.png"), (30, -12)),
            ("hd greatsword", os.path.join(ROOT, "packs/hyperdim_RP/models/entity/hd_greatsword.geo.json"),
             os.path.join(ROOT, "packs/hyperdim_RP/textures/entity/hd/greatsword.png"), (60, -20)),
        ]
        for label, gp, tp, (yaw, pitch) in models:
            if not (os.path.exists(gp) and os.path.exists(tp)):
                notes.append(f"skip compare {label} (missing)")
                continue
            G = load_geometry(gp)
            T = Image.open(tp)
            with open(gp, encoding="utf-8") as fh:
                gjson = json.load(fh)["minecraft:geometry"][0]
            sc = _Scene(G, None, None, "subtree", "legacy")
            pts = sc.bounds_points()
            lo, hi = pts.min(0), pts.max(0)
            centre = (lo + hi) / 2
            sz = (360, 360)
            scale = 300 / float((hi - lo).max())
            for yw, pt in ((yaw, pitch), (yaw + 180, pitch)):
                quads = hd_scene.weapon_quads(gjson, T, None, {})
                ref = hd_scene.raster(quads, T, sz, hd_scene.ortho(yw, pt, centre, scale, sz), bg=(24, 26, 34))
                t0 = time.perf_counter()
                mine = render(G, T, None, sz, bg=(24, 26, 34), faces="legacy", light="hd", alpha_test=0,
                              emit_gain=1.1, cull=False,
                              camera=Camera(yaw=-yw, pitch=-pt, target=tuple(centre), scale=scale))
                dt = time.perf_counter() - t0
                a = np.asarray(ref, np.int16)
                b = np.asarray(mine.convert("RGB"), np.int16)
                fg = (np.abs(a - np.array([24, 26, 34])).sum(-1) > 0) | (np.abs(b - np.array([24, 26, 34])).sum(-1) > 0)
                same = (np.abs(a - b).max(-1) <= 3) & fg
                frac = same.sum() / max(1, fg.sum())
                check(frac > 0.985, f"{label} yaw {yw}: matches hd_scene on {frac * 100:.2f}% of pixels "
                                    f"({dt * 1000:.0f} ms)")
                diff = Image.fromarray((np.abs(a - b).clip(0, 255) * 4).clip(0, 255).astype(np.uint8))
                compare_tiles += [(f"hd_scene {label} {yw}", ref), (f"nr_preview legacy {yw}", mine.convert("RGB")),
                                  ("|diff| x4", diff)]
            bed = render(G, T, None, sz, bg=(24, 26, 34), light="hd", alpha_test=0, emit_gain=1.1,
                         camera=Camera(yaw=-yaw, pitch=-pitch, target=tuple(centre), scale=scale))
            compare_tiles.append((f"nr_preview bedrock (east=-X)", bed))
    except ImportError as e:
        check(False, f"hd_scene import ({e})")

    # 6) 速さ: 400 キューブ・512px
    rs = random.Random(1234)
    bones = [{"name": "root", "pivot": [0, 0, 0]}]
    for i in range(20):
        bones.append({"name": f"b{i}", "parent": "root" if i < 4 else f"b{rs.randrange(i)}",
                      "pivot": [rs.uniform(-8, 8), rs.uniform(0, 30), rs.uniform(-4, 4)],
                      "rotation": [rs.uniform(-30, 30), rs.uniform(-30, 30), rs.uniform(-30, 30)], "cubes": []})
    for i in range(400):
        b = bones[1 + i % 20]
        o = [b["pivot"][0] + rs.uniform(-4, 4), b["pivot"][1] + rs.uniform(-6, 2), b["pivot"][2] + rs.uniform(-3, 3)]
        s = [rs.uniform(0.5, 5), rs.uniform(0.5, 8), rs.uniform(0.5, 4)]
        cube = {"origin": o, "size": s, "uv": {f: {"uv": [rs.randrange(0, 480), rs.randrange(0, 480)],
                                                    "uv_size": [rs.randrange(2, 30), rs.randrange(2, 30)]}
                                               for f in FACE_NAMES}}
        if i % 3 == 0:
            cube["rotation"] = [rs.uniform(-40, 40), rs.uniform(-40, 40), rs.uniform(-40, 40)]
        b["cubes"].append(cube)
    perf_doc = {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.test.perf", "texture_width": 512, "texture_height": 512},
        "bones": bones}]}
    nrng = np.random.default_rng(3)
    ptex = (nrng.random((512, 512, 4)) * 255).astype(np.uint8)
    ptex[..., 3] = 255
    PG = load_geometry(perf_doc)
    times_ = []
    for view in ("three_quarter", "front"):
        st: dict = {}
        render(PG, ptex, view, 512, stats=st)
        times_.append(st["total_s"])
        print(f"     perf {view}: {st['cubes']} cubes, {st['faces']} faces, {st['fragments']} fragments, "
              f"{st['total_s'] * 1000:.0f} ms")
    st = {}
    render(PG, ptex, "three_quarter", 512, projection="persp", stats=st)
    print(f"     perf persp: {st['total_s'] * 1000:.0f} ms")
    check(max(times_) < 2.0, f"400 cubes @512px in {max(times_):.2f} s (< 2 s)")

    # 7) 見本の絵
    sheets: List[Image.Image] = []
    kafka_g = os.path.join(ROOT, "packs/kaiju8_RP/models/entity/kafka.geo.json")
    kafka_t = os.path.join(ROOT, "packs/kaiju8_RP/textures/entity/kaiju8/kafka.png")
    anim_k = os.path.join(ROOT, "packs/kaiju8_RP/animations/kaiju8.animation.json")
    honju_g = os.path.join(ROOT, "packs/kaiju8_RP/models/entity/honju.geo.json")
    honju_t = os.path.join(ROOT, "packs/kaiju8_RP/textures/entity/kaiju8/honju.png")
    if os.path.exists(honju_g):
        t0 = time.perf_counter()
        sheets.append(render_views(honju_g, honju_t, size=300, title="kaiju8 honju — render_views (ortho, uniform scale)"))
        print(f"     render_views honju 5x300px: {(time.perf_counter() - t0) * 1000:.0f} ms")
    if os.path.exists(kafka_g):
        aw: List[str] = []
        # 歩きは anim_time ではなく移動距離で動く → コマごとに q.modified_distance_moved を進める
        tiles = render_clip(kafka_g, kafka_t, anim_k, "animation.kaiju8.humanoid.walk",
                            [0.0, 0.15, 0.3, 0.45, 0.6, 0.75], view="three_quarter", size=240,
                            queries={"modified_move_speed": 1.0},
                            per_frame=lambda tt: {"q.modified_distance_moved": 4.3 * tt},
                            floor=True, ss=2, warnings=aw)
        pose, _ = animation_pose(anim_k, "animation.kaiju8.humanoid.walk", 0.0, bones=load_geometry(kafka_g),
                                 queries={"modified_distance_moved": 1.0, "modified_move_speed": 1.0},
                                 warnings=aw)
        tiles.append(("walk dist=1 (render pose=)", render(kafka_g, kafka_t, "three_quarter", 240, pose=pose,
                                                           floor=True, ss=2)))
        cross = render_clip(kafka_g, kafka_t, anim_k, "animation.kaiju8.tech.cross", [0.0, 0.2, 0.4, 0.6],
                            view="front", size=240, warnings=aw)
        tiles += cross
        tiles.append(("persp hero ss2 floor", render(kafka_g, kafka_t, "hero", 240, projection="persp",
                                                     ss=2, floor=True)))
        tiles.append(("hide arms (subtree)", render(kafka_g, kafka_t, "three_quarter", 240,
                                                    hidden={"rightarm", "leftForearm"})))
        tiles.append(("hide 'body' exact", render(kafka_g, kafka_t, "three_quarter", 240,
                                                  hidden={"body"}, hide_mode="exact")))
        sheets.append(contact_sheet(tiles, cols=6, title="kaiju8 kafka — animation (Molang) / persp / floor / hidden"))
        for w in aw:
            print("     anim warn:", w)
    rig_dir = os.path.join(out_dir, "rig")
    rig_geo = os.path.join(rig_dir, "average.geo.json")
    if os.path.exists(rig_geo):
        gore_default = {"stump_*", "*_wound", "guts", "skull_open"}
        states = [
            ("intact", gore_default),
            ("arm_r cut_lower", (gore_default - {"stump_*"}) | {"stump_leg*", "stump_arm_l*", "stump_arm_r_upper",
                                                                 "stump_neck", "stump_torso", "forearm_r"}),
            ("head severed", (gore_default - {"stump_*"}) | {"stump_leg*", "stump_arm*", "stump_torso", "head"}),
            ("torso halved", (gore_default - {"stump_*", "guts"}) | {"stump_leg*", "stump_arm*", "stump_neck",
                                                                    "pelvis"}),
        ]
        tiles = []
        RG = load_geometry(rig_geo)
        RT = load_texture(os.path.join(rig_dir, "average.png"))
        for label, hid in states:
            st = {}
            tiles.append((label, render(RG, RT, "three_quarter", 260, hidden=hid, stats=st, floor=True)))
        tiles.append(("intact back", render(RG, RT, "back_three_quarter", 260, hidden=gore_default)))
        tiles.append(("legacy faces (east/west swapped)", render(RG, RT, "three_quarter", 260,
                                                                 hidden=gore_default, faces="legacy")))
        sheets.append(contact_sheet(tiles, cols=6, title=f"NIGHT RUNNER rig sample (nr_rig) — gore states via hidden "
                                                         f"({RG.cube_count} cubes)"))
    # 面の表のテスト用キューブ
    cube_tiles = [(v, render(g, tex, v, 120, light=None, bg=(0, 0, 0))) for v in expect]
    cube_tiles.append(("right, legacy", render(g, tex, "right", 120, light=None, bg=(0, 0, 0), faces="legacy")))
    sheets.append(contact_sheet(cube_tiles, cols=7, title="face table: N=red S=green E=blue W=yellow up=white "
                                                          "down=purple, black = (u0,v0) corner"))
    if compare_tiles:
        sheets.append(contact_sheet(compare_tiles, cols=7, title="hd_scene vs nr_preview (faces=legacy, light=hd)"))
    Wt = max(s.size[0] for s in sheets)
    Ht = sum(s.size[1] for s in sheets)
    canvas = Image.new("RGB", (Wt, Ht), (12, 12, 15))
    y = 0
    for s in sheets:
        canvas.paste(s, (0, y))
        y += s.size[1]
    path = os.path.join(out_dir, "preview_selftest.png")
    canvas.save(path)
    for n in notes:
        print("note", n)
    print(f"wrote {path} ({Wt}x{Ht})")
    print(f"{len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
