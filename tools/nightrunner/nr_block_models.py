# -*- coding: utf-8 -*-
"""NIGHT RUNNER — カスタムブロックのモデル（gen_nr_blocks 専用）。

ブロック空間（`nr_spec_catalog` の約束）: 原点 = ブロックの底面中央、x・z は -8〜8、y は 0〜16（px = 単位）。
**モデルの前は north（-Z）**。置くときは `minecraft:placement_direction` の状態で回す（gen_nr_blocks）。
壁に付く物は +Z が壁側。

* `BlockModel` … mcmodel.Model の薄い包み。中心と大きさで箱を置く `box()`、2 点を結ぶ棒 `rod()`、
  回した箱を重ねた円柱 `cyl()`（n=2 で八角、3 で十二角）、状態で出し入れするボーン
  （`bone(name, vis={状態: [値]})`。状態どうしは AND、値どうしは OR）、テクスチャを共有した姿勢違いの写し
  `clone()`（トラバサミの閉じた顎・開いた蓋・倒れたコーン）、ワールド座標のデカール `wd()`。
* `BUILDERS[key](bm, entry)` … ブロックごとの作り込み。カタログの部品（`entry["model"]`）は大きさ・素材・
  位置の目安で、形が読めるように足したり割ったりする。知らないキーは `build_generic`（部品をそのまま箱に）。
* 状態の名前と値は gen_nr_blocks.state_schema が正（`bm.states`）。ここで使う名前が無ければ生成器が止まる。

1 ブロックのキューブは 50 個まで（Mojang の検証の警告）、形は 30×30×30 px（gen_nr_blocks が検査）。
テクスチャは 1 単位 4 texel（64 px / ブロック）を基本に、256×256 に入らなければ 3 → 2 に落とす
（大事でない箱は `uv=0.5` などで先に密度を下げる）。
回転は nr_preview（= 実機）の約束: R = Rz(-rz)·Ry(ry)·Rx(-rx)。正の rx は +Y を -Z（前）へ倒す。
"""
from __future__ import annotations

import math
import os
import sys
import zlib
from typing import Dict, List, Optional, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcmodel import Cube, Model  # noqa: E402
import nr_paint as NP  # noqa: E402
import nr_block_paint as BP  # noqa: E402

MAX_CUBES = 50
ATLAS_MAX = (256, 256)
UV_SCALES = (4, 3, 2, 1)


def _h(*parts) -> int:
    return zlib.crc32(":".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


def _fmt_val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else str(v)
    return f"'{v}'"


def vis_molang(cond: Dict[str, Sequence]) -> str:
    """{状態: [値...]} → q.block_state の式（状態どうしは AND、値どうしは OR）。"""
    parts = []
    for s in sorted(cond):
        vals = list(cond[s])
        ors = [f"q.block_state('{s}') == {_fmt_val(v)}" for v in vals]
        parts.append(ors[0] if len(ors) == 1 else "(" + " || ".join(ors) + ")")
    return " && ".join(parts) if parts else "true"


def vis_eval(cond: Dict[str, Sequence], states: Dict[str, object]) -> bool:
    for s, vals in cond.items():
        if states.get(s) not in list(vals):
            return False
    return True


def _rot(r):
    import nr_preview as PV
    return PV.rot(*[float(v) for v in r])


def rod_rotation(p0, p1):
    """+Z を p0→p1 に向ける回転 [rx, ry, 0] と長さ。"""
    d = np.asarray(p1, float) - np.asarray(p0, float)
    L = float(np.linalg.norm(d))
    if L < 1e-9:
        return [0.0, 0.0, 0.0], 0.0
    d = d / L
    rx = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    ry = math.degrees(math.atan2(d[0], d[2]))
    return [round(rx, 3), round(ry, 3), 0.0], L


class BlockModel:
    def __init__(self, key: str, seed: int = 0):
        self.key = key
        self.seed = seed
        self.model = Model("geometry.nr.b." + key, uv_scale=4, visible_bounds=(3, 3), vb_offset=(0, 1, 0),
                           max_atlas=ATLAS_MAX)
        self.bones: Dict[str, object] = {}
        self.vis: Dict[str, Dict[str, list]] = {}
        self.styles: Dict[str, dict] = {}
        self.factor: Dict[int, float] = {}
        self.drop: Dict[int, set] = {}
        self.pending_clones: List[tuple] = []
        self.scale = 4
        self.painted = False
        self.notes: List[str] = []
        self.states: Dict[str, list] = {}
        self.rng = np.random.default_rng(seed & 0xFFFFFFFF)
        self.bone("root")

    # ---- ボーン・スタイル -------------------------------------------------------
    def bone(self, name: str, pivot=(0, 0, 0), rotation=None, vis: Optional[Dict[str, list]] = None) -> str:
        """状態で出し入れするボーン（root の子）。vis の状態が bm.states に無ければ条件を付けない。"""
        if vis:
            vis = {k: list(v) for k, v in vis.items() if k in self.states}
        if name in self.bones:
            if vis:
                self.vis[name] = vis
            return name
        b = self.model.bone(name, pivot, parent=None if name == "root" else "root", rotation=rotation)
        self.bones[name] = b
        if vis:
            self.vis[name] = vis
        return name

    def use(self, sname: str, **over) -> str:
        """スタイル名（STYLES のキー）を登録して名前を返す。over があれば色違いの別名を作る。"""
        if not over:
            if sname not in self.styles:
                self.styles[sname] = BP.style_for(sname)
            return sname
        key = sname + "~" + "%08x" % _h(sorted((k, str(v)) for k, v in over.items()))
        if key not in self.styles:
            self.styles[key] = BP.style_for(sname, **over)
        return key

    def has(self, state: str) -> bool:
        return state in self.states

    # ---- 箱 -------------------------------------------------------------------
    def box(self, at, size, style, bone="root", rot=None, pivot=None, uv: float = 1.0, drop=(),
            decals=None, inflate=0.0) -> Cube:
        """中心 at・大きさ size の箱。style は STYLES のキーか use() の戻り値。"""
        sname = style if style in self.styles else self.use(style)
        at = [float(v) for v in at]
        size = [float(v) for v in size]
        origin = [at[i] - size[i] / 2 for i in range(3)]
        rotation = [float(r) for r in rot] if rot is not None and any(abs(r) > 1e-9 for r in rot) else None
        piv = [float(v) for v in pivot] if pivot is not None else (at if rotation else None)
        c = Cube(origin, size, sname, inflate=inflate, pivot=piv, rotation=rotation)
        if uv != 1.0:
            self.factor[id(c)] = uv
        st = self.styles[sname]
        if st.get("_paint"):
            for f in NP.FACES:
                c.decals[f] = [{"name": "nrb_peel", "colour": st["_paint"], "amount": 0.4}] + _as_list(c.decals.get(f))
        if decals:
            for f, dv in decals.items():
                for face in _faces(f):
                    c.decals[face] = _as_list(c.decals.get(face)) + _as_list(dv)
        dr = set(_faces(drop)) if drop else set()
        if origin[1] <= 1e-3 and rotation is None and self.bones[bone].rotation is None:
            dr.add("down")
        if dr:
            self.drop[id(c)] = dr
        self.bones[bone].add(c)
        return c

    def rod(self, p0, p1, w, style, bone="root", h=None, uv: float = 1.0, ext: float = 0.0, decals=None,
            drop=(), spin: float = 0.0) -> Cube:
        """p0 から p1 への棒（断面 w×h、長さ方向が箱の Z）。ext は両端を延ばす長さ。"""
        rot, L = rod_rotation(p0, p1)
        if spin:
            rot = [rot[0], rot[1], float(spin)]
        c = (np.asarray(p0, float) + np.asarray(p1, float)) / 2
        return self.box(c.tolist(), (w, h if h is not None else w, L + 2 * ext), style, bone=bone, rot=rot,
                        pivot=c.tolist(), uv=uv, decals=decals, drop=drop)

    def cyl(self, at, d, h, style, axis="y", n=2, bone="root", uv: float = 1.0, decals=None, drop=(),
            rot0: float = 0.0, tilt=None, step: float = 0.0) -> List[Cube]:
        """回した箱を n 個重ねた円柱（n=2 八角、n=3 十二角）。axis は長さの向き。
        tilt は y 軸なら (rx, rz)、x 軸なら (ry, rz)、z 軸なら (rx, ry)（回す順は X → Y → Z）。
        step は重なった端の面が z ファイトしないよう、箱ごとに長さを少しずつ変える量。"""
        out = []
        for k in range(n):
            a = rot0 + k * 90.0 / n
            hh = h + step * k
            if axis == "y":
                size, rot = (d, hh, d), (0.0, a, 0.0)
                if tilt:
                    rot = (tilt[0], a, tilt[1])
            elif axis == "x":
                size, rot = (hh, d, d), (a, 0.0, 0.0)
                if tilt:
                    rot = (a, tilt[0], tilt[1])
            else:
                size, rot = (d, d, hh), (0.0, 0.0, a)
                if tilt:
                    rot = (tilt[0], tilt[1], a)
            out.append(self.box(at, size, style, bone=bone, rot=rot, pivot=at, uv=uv, decals=decals, drop=drop))
        return out

    def dec(self, cubes, faces, name, **params):
        """普通のデカールを足す（faces は面の名前のリスト / "sides" / "*"）。"""
        for c in _as_list(cubes):
            for f in _faces(faces):
                c.decals[f] = _as_list(c.decals.get(f)) + [dict(params, name=name)]

    def wd(self, cubes, faces, name, **params):
        """ワールド座標のデカール（O/A/B と法線 N を面ごとに足す）。回したキューブでは目安。"""
        for c in _as_list(cubes):
            for f in _faces(faces):
                O, A, B = BP.face_frame(c.origin, c.size, f)
                d = dict(params, name=name, O=O, A=A, B=B, N=BP.FACE_NORMAL[f])
                c.decals[f] = _as_list(c.decals.get(f)) + [d]

    def drop_faces(self, cubes, faces):
        for c in _as_list(cubes):
            self.drop.setdefault(id(c), set()).update(_faces(faces))

    def clone(self, cubes, bone: str):
        """テクスチャを共有した写しを bone に置く（塗った後に作る）。"""
        self.pending_clones.append((bone, list(_as_list(cubes))))

    # ---- 仕上げ -------------------------------------------------------------------
    def cube_count(self) -> int:
        return len(self.model.all_cubes()) + sum(len(cs) for _, cs in self.pending_clones)

    def pack(self):
        last = None
        for S in UV_SCALES:
            for c in self.model.all_cubes():
                f = self.factor.get(id(c))
                if f is not None:
                    c.uv_scale = max(1, int(round(S * f)))
                    c._scale = c.uv_scale
            self.model.uv_scale = S
            try:
                self.model.pack()
                self.scale = S
                return
            except ValueError as ex:
                last = ex
        raise last

    def paint(self, seed: int = 0):
        if not self.model.tex_w:
            self.pack()
        img = NP.paint_model(self.model, self.styles, seed=seed)
        self.painted = True
        for bone, cubes in self.pending_clones:
            for c in cubes:
                k = Cube(c.origin, c.size, c.style, inflate=c.inflate, pivot=c.pivot, rotation=c.rotation,
                         fixed_uv=c.uv, uv_scale=c._scale)
                if id(c) in self.drop:
                    self.drop[id(k)] = set(self.drop[id(c)]) - {"down"}
                self.bones[bone].add(k)
        self.pending_clones = []
        return img

    def to_json(self) -> dict:
        doc = self.model.to_json()
        for bdoc, bone in zip(doc["bones"], self.model.bones):
            for cdoc, c in zip(bdoc.get("cubes", []), bone.cubes):
                for f in self.drop.get(id(c), ()):
                    if isinstance(cdoc.get("uv"), dict):
                        cdoc["uv"].pop(f, None)
        return doc

    def bone_visibility(self) -> Dict[str, str]:
        return {b: vis_molang(c) for b, c in sorted(self.vis.items())}


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    return [v]


def _faces(faces):
    if faces == "*":
        return list(NP.FACES)
    if faces == "sides":
        return list(NP.SIDES)
    if isinstance(faces, str):
        return [faces]
    return list(faces)


def rest_pivot(cubes, rotation, target=(0.0, 0.0, 0.0)):
    """cubes を rotation で回したとき、一番低い点が y=target[1]、x・z の中心が target に来る pivot。"""
    R = _rot(rotation)
    pts = []
    for c in cubes:
        o = np.array(c.origin, float)
        s = np.array(c.size, float)
        P = np.array([[x, y, z] for x in (o[0], o[0] + s[0]) for y in (o[1], o[1] + s[1])
                      for z in (o[2], o[2] + s[2])])
        if c.rotation:
            Rc = _rot(c.rotation)
            piv = np.array(c.pivot or (o + s / 2), float)
            P = (Rc @ (P - piv).T).T + piv
        pts.append(P)
    P = (R @ np.concatenate(pts).T).T
    lo, hi = P.min(0), P.max(0)
    t = np.array([target[0] - (lo[0] + hi[0]) / 2, target[1] - lo[1], target[2] - (lo[2] + hi[2]) / 2])
    # x' = R x + (I - R) p  → (I - R) p = t（回転軸の向きの成分は解けないので最小二乗）
    p, *_ = np.linalg.lstsq(np.eye(3) - R, t, rcond=None)
    return [round(float(v), 3) for v in p]


# ===========================================================================
#  状態の名前（gen_nr_blocks と同じ）と共通の部品
# ===========================================================================
TRAP = "nr:trap_state"
VARIANT = "nr:variant"
WEAR = "nr:wear"
CHARGES = "nr:charges"


def spray_text(bm, cubes, faces, text, origin, height, colour=(178, 22, 20), width=0.62, right=(1, 0, 0),
               down=(0, -1, 0), drip=0.7, slant=0.18, seed=0, **kw):
    strokes = BP.text_strokes(text, origin, right, down, height, slant=slant, seed=seed or _h(text, origin))
    bm.wd(cubes, faces, "nrb_spray", strokes=strokes, colour=colour, width=width, drip=drip, **kw)


def spray_lines(bm, cubes, faces, lines, colour=(178, 22, 20), width=0.62, drip=0.6, **kw):
    bm.wd(cubes, faces, "nrb_spray", strokes=[[tuple(p) for p in ln] for ln in lines], colour=colour,
          width=width, drip=drip, **kw)


def nails_on(bm, cubes, faces, pts, r=0.42, kind="nail", rust=0.7, colour=(70, 66, 62)):
    bm.wd(cubes, faces, "nrb_nails", pts=[tuple(p) for p in pts], r=r, kind=kind, rust=rust, colour=colour)


def flames(bm, at, w, h, bone, n=2, rot0=0.0, tongues=3.0, uv=1.0):
    """交差した炎の板（アルファで抜く）。at は根元の中心。"""
    cs = []
    for k in range(n):
        a = rot0 + k * 180.0 / n
        c = bm.box((at[0], at[1] + h / 2, at[2]), (w, h, 0.1), "emissive_amber", bone=bone, rot=(0, a, 0),
                   pivot=(at[0], at[1], at[2]), uv=uv, drop=("up", "down", "east", "west"))
        bm.dec(c, ["north", "south"], "nrb_flame", tongues=tongues)
        cs.append(c)
    return cs


def plane_y(bm, at, sx, sz, style, bone="root", th=0.1, uv=1.0, rot=None, both=False):
    """床に置く平らな板（上の面だけ。both なら下の面も）。"""
    drop = ("north", "south", "east", "west") if both else ("down", "north", "south", "east", "west")
    return bm.box(at, (sx, th, sz), style, bone=bone, uv=uv, rot=rot, drop=drop)


def plane_z(bm, at, sx, sy, style, bone="root", th=0.1, uv=1.0, rot=None, pivot=None):
    """立てた板（前後の面だけ）。"""
    return bm.box(at, (sx, sy, th), style, bone=bone, uv=uv, rot=rot, pivot=pivot,
                  drop=("up", "down", "east", "west"))


def plane_x(bm, at, sy, sz, style, bone="root", th=0.1, uv=1.0, rot=None, pivot=None):
    """横向きに立てた板（左右の面だけ）。"""
    return bm.box(at, (th, sy, sz), style, bone=bone, uv=uv, rot=rot, pivot=pivot,
                  drop=("up", "down", "north", "south"))


# ===========================================================================
#  バリケード
# ===========================================================================
def build_barricade(bm: BlockModel, e):
    braces = [bm.box((x, 8, 1.6), (3, 16, 1.2), "wood_dark") for x in (-6, 6)]
    bm.dec(braces, "north", "grime", amount=0.5)
    top = bm.box((0, 13, -0.6), (18, 4, 1.4), "wood_old", rot=(0, 0, 4))
    mid = bm.box((0.5, 8, 0.6), (17, 3.6, 1.4), "plywood", rot=(0, 0, -9))
    low = bm.box((0, 3, -0.6), (18, 4, 1.4), "wood_old", rot=(0, 0, -3))
    hang = bm.box((-4.2, 6.3, -1.9), (7.5, 2.6, 1.0), bm.use("wood_old", base="#6a5038"), rot=(0, 0, -31))
    bm.box((9.4, 13.9, -0.6), (1.6, 1.6, 1.2), "wood_old", rot=(0, 0, 25), uv=0.75)
    bm.box((-9.2, 2.3, -0.6), (1.4, 1.8, 1.2), "wood_old", rot=(0, 0, -20), uv=0.75)
    bm.box((3.5, 0.6, 1.9), (6, 1.2, 2.0), bm.use("wood_dark", base="#3e2e22"), rot=(0, 12, 0), uv=0.75)
    planks = [top, mid, low, hang]
    bm.dec(planks, "north", "grime", amount=0.35)
    heads = [(-6, 13, -1.45), (6, 13, -1.45), (-6, 3, -1.45), (6, 3, -1.45), (0, 8, -0.2), (-6.6, 6.9, -2.45)]
    for p in heads:
        bm.box(p, (0.8, 0.8, 0.6), "steel_rusty", uv=0.5)
    nails_on(bm, [top, low, mid, hang], "north",
             heads + [(-7.6, 13.3, -1.3), (7.4, 12.6, -1.3), (-7.4, 2.8, -1.3), (7.6, 3.4, -1.3), (3, 8.4, -0.1)],
             r=0.3, rust=0.9)
    spray_text(bm, [top, mid], "north", "KEEP OUT", (-7.4, 14.7, -1.3), 3.0, seed=11)
    bm.dec(low, "north", "handprint", at=(0.62, 0.55), size=0.42)
    bm.dec(mid, "north", "nrb_claw", at=(0.32, 0.5), size=0.5, angle=78, n=4, blood=0.7)
    bm.dec(low, "north", "nrb_claw", at=(0.25, 0.4), size=0.6, angle=72, n=3, blood=0.5)
    bm.dec(low, "north", "drips", start=0.05, amount=0.4)
    bm.dec(top, "north", "bullet_hole", at=(0.8, 0.6), size=0.05)


def build_metal_barricade(bm: BlockModel, e):
    sheet = bm.box((0, 8, 0), (16, 16, 1.0), "steel_rusty")
    bm.dec(sheet, ["north", "south"], "nrb_corrugate", period=2.0, depth=1.2)
    bm.dec(sheet, "north", "rust_streaks", amount=0.9)
    for i in range(8):
        rib = bm.box((-7 + i * 2, 8, -0.7), (0.9, 16, 0.4), "steel_rusty", uv=0.75)
        bm.dec(rib, "north", "rust_streaks", amount=0.6)
    fr = [bm.box((0, y, -1.2), (17, 1.6, 1.6), "steel_dark") for y in (2, 14)]
    fr += [bm.box((x, 8, -1.2), (1.6, 16, 1.6), "steel_dark") for x in (-7.2, 7.2)]
    bm.dec(fr, "north", "grime", amount=0.5)
    for x in (-7.2, 7.2):
        for y in (2, 14):
            bm.box((x, y, -2.2), (1, 1, 0.6), "steel_worn", uv=0.5)
    patch = bm.box((3.4, 5.2, -1.15), (6.5, 5, 0.5), bm.use("steel_painted", base="#5c6a5a", rust=0.7))
    bm.dec(patch, "north", "nrb_rivets", step=1.6, inset=0.5, r=0.25)
    bm.dec(patch, "north", "bullet_hole", at=(0.3, 0.4), size=0.08)
    bm.dec(sheet, "north", "bullet_hole", at=(0.22, 0.3), size=0.035)
    bm.dec(sheet, "north", "bullet_hole", at=(0.71, 0.2), size=0.03)
    bm.dec(sheet, "north", "nrb_uv_mark", at=(0.62, 0.42), size=0.36)
    bm.wd(fr[0:1] + [sheet], "north", "nrb_spray",
          strokes=BP.text_strokes("NO", (-6.3, 13.0, -0.5), (1, 0, 0), (0, -1, 0), 2.6, seed=5),
          colour=(226, 224, 214), width=0.5, drip=0.5)
    for x in (-5, 5):
        bm.rod((x, 0.5, 6.5), (x, 13, 0.9), 1.4, "wood_dark", uv=0.75)


def build_sandbags(bm: BlockModel, e):
    burlap = bm.use("burlap", blood=0.0)
    dark = bm.use("burlap", base="#8e7c58", dirt=0.75, blood=0.0)
    wet = bm.use("burlap", base="#7a6a4c", dirt=0.85, blood=0.0)
    rows = [((-4.1, 2, 0), (8.2, 4, 9), burlap), ((4.1, 2, 0.2), (8.2, 4, 9), wet),
            ((0, 6, 0.3), (8.2, 4, 8.5), dark), ((-8.0, 6, 0.1), (8.2, 4, 8.5), burlap),
            ((8.0, 6, 0.2), (8.2, 4, 8.5), burlap), ((-4.1, 10, 0.1), (8.2, 4, 8), dark),
            ((4.2, 10, -0.2), (8.2, 4, 8), burlap)]
    cores = []
    for i, (at, size, st) in enumerate(rows):
        x, y, z = at
        sx, sy, sz = size
        yaw = ((i * 7) % 5 - 2) * 1.6
        core = bm.box((x, y - 0.15, z), (sx - 0.5, sy - 0.7, sz), st, rot=(0, yaw, 0))
        bulge = bm.box((x, y + 0.1, z), (sx - 1.8, sy - 0.1, sz - 1.4), st, rot=(0, yaw, 0))
        bm.dec([core], ["north", "south"], "nrb_stitch_ends")
        bm.dec([core, bulge], "up", "grime", amount=0.35)
        cores.append(core)
    bm.box((-8.6, 10.6, -3.9), (1.6, 1.4, 1.2), burlap, rot=(0, 20, 10), uv=0.75)
    bm.box((8.7, 10.4, 3.6), (1.6, 1.4, 1.2), burlap, rot=(0, -15, -8), uv=0.75)
    sand = bm.use("concrete", base="#b09a70", cracks=0.0, dirt=0.2)
    bm.box((5.2, 0.5, -5.0), (3.8, 1.0, 2.4), sand, uv=0.75)
    bm.box((6.5, 0.2, -6.4), (2.2, 0.4, 1.6), sand, uv=0.75)
    bm.dec(cores[1], "north", "bullet_hole", at=(0.55, 0.45), size=0.08)
    bm.dec(cores[0], "north", "nrb_stencil", text="NR-07", at=(0.5, 0.55), h=0.36, colour=(214, 212, 200))
    bm.dec(cores[3], "north", "nrb_stencil", text="07", at=(0.5, 0.5), h=0.36, colour=(214, 212, 200))
    bm.dec(cores[4], "north", "handprint", at=(0.4, 0.5), size=0.6)


# ===========================================================================
#  通り・灯り
# ===========================================================================
def build_traffic_cone(bm: BlockModel, e):
    up = bm.bone("upright", vis={"nr:fallen": [0]})
    fallen = bm.bone("fallen", vis={"nr:fallen": [1]})
    cubes = []
    base = bm.box((0, 0.6, 0), (11, 1.2, 11), "rubber_black", bone=up)
    bm.dec(base, "up", "grime", amount=0.6)
    cubes.append(base)
    cubes.append(bm.box((0, 1.35, 0), (8.2, 0.3, 8.2), "rubber_black", bone=up, uv=0.75))
    orange = bm.use("plastic_orange", wear=0.5, dirt=0.55)
    white = bm.use("plastic_white", base="#e8e6de", dirt=0.45)
    tiers = [(1.5, 1.8, 7.0, orange), (3.3, 1.5, 6.3, orange), (4.8, 1.4, 5.7, white), (6.2, 1.2, 5.1, white),
             (7.4, 1.4, 4.5, orange), (8.8, 1.0, 3.9, white), (9.8, 1.1, 3.3, orange), (10.9, 0.9, 2.6, orange)]
    for y0, h, w, st in tiers:
        cs = bm.cyl((0, y0 + h / 2, 0), w, h, st, bone=up, n=2, step=0.02)
        bm.dec(cs, "sides", "grime", amount=0.5)
        cubes += cs
    rot = [72.0, 0.0, 0.0]
    bm.bones[fallen].rotation = rot
    bm.bones[fallen].pivot = rest_pivot(cubes, rot, target=(0.0, 0.0, -1.0))
    bm.clone(cubes, fallen)


def build_road_barrier(bm: BlockModel, e):
    conc = bm.use("concrete", base="#a4a39b", dirt=0.5)
    lip = bm.box((0, 1.0, 0), (16, 2.0, 10), conc)
    core = bm.box((0, 6.6, 0), (16, 11.2, 4.6), conc)
    s1 = bm.box((0, 3.4, -3.0), (16, 4.2, 2.8), conc, rot=(-30, 0, 0))
    s2 = bm.box((0, 3.4, 3.0), (16, 4.2, 2.8), conc, rot=(30, 0, 0))
    bm.box((0, 12.2, 0), (16, 0.6, 4.2), bm.use("concrete", base="#8e8e88", cracks=0.8))
    bm.dec([lip, core, s1, s2], "sides", "grime", amount=0.6)
    bm.dec([core], ["east", "west"], "cracks", amount=0.8)
    bm.dec(core, "north", "stripe", count=5, orient="d", width=0.07, gap=0.06, colour=(178, 30, 26),
           reflective=True, offset=0.62)
    bm.dec(core, "north", "nrb_label", box=(0.0, 0.16, 1.0, 0.3), fill=(222, 216, 202), wear=0.5)
    bm.dec(lip, "north", "nrb_stencil", text="NR HWY 9", at=(0.5, 0.5), h=0.55, colour=(40, 40, 40))
    for x in (-4, 4):
        bm.box((x, 0.75, 0), (3.0, 1.5, 10.2), bm.use("concrete_dark", base="#262626"), uv=0.5)
    spray_text(bm, [core], "south", "RUN", (5.4, 11.0, 2.35), 3.2, colour=(40, 80, 170), right=(-1, 0, 0), seed=21)
    for x in (-5, 5):
        bm.box((x - 0.9, 13.1, 0), (0.5, 1.4, 0.5), "rebar", uv=0.5)
        bm.box((x + 0.9, 13.1, 0), (0.5, 1.4, 0.5), "rebar", uv=0.5)
        bm.box((x, 13.7, 0), (2.3, 0.5, 0.5), "rebar", uv=0.5)
    chunk = bm.use("concrete", base="#8c8c84")
    bm.box((-6.8, 0.5, -6.0), (2.0, 1.0, 1.6), chunk, rot=(0, 25, 8), uv=0.75)
    bm.box((6.0, 0.4, -5.8), (1.2, 0.8, 1.0), chunk, rot=(0, -15, 0), uv=0.75)


def build_street_lamp_base(bm: BlockModel, e):
    iron = bm.use("paint_green", base="#24342a", wear=0.5, rust=0.6)
    plinth = bm.cyl((0, 1.5, 0), 10, 3, iron, n=2, step=0.04)
    bm.cyl((0, 3.4, 0), 8.6, 0.8, iron, n=2, step=0.04)
    flare = bm.cyl((0, 6.0, 0), 6.6, 4.4, iron, n=2, step=0.04)
    bm.cyl((0, 8.6, 0), 5.6, 0.8, iron, n=2, step=0.04)
    shaft = bm.cyl((0, 12.5, 0), 4.4, 7.0, iron, n=2, step=0.04)
    for c in plinth + flare + shaft:
        bm.dec(c, "sides", "rust_streaks", amount=0.7)
        bm.dec(c, "sides", "grime", amount=0.5)
    panel = bm.box((0, 6.0, -3.45), (2.6, 3.0, 0.4), "steel_dark", rot=(0, 0, 4))
    bm.dec(panel, "north", "nrb_rivets", step=1.2, inset=0.35, r=0.2)
    poster = bm.box((0, 12.4, -2.32), (3.4, 4.4, 0.2), "paper")
    bm.dec(poster, "north", "nrb_poster")
    for x, z in ((-3.6, -3.6), (3.6, -3.6), (-3.6, 3.6), (3.6, 3.6)):
        bm.box((x, 3.25, z), (1.0, 0.9, 1.0), "steel_rusty", uv=0.5)


def build_street_lamp_pole(bm: BlockModel, e):
    paint = bm.use("paint_green", base="#24342a", wear=0.45, rust=0.6)
    pole = bm.cyl((0, 8, 0), 3.4, 16, paint, n=2, step=0.02)
    for c in pole:
        bm.dec(c, "sides", "rust_streaks", amount=0.8)
    bm.cyl((0, 15.5, 0), 4.0, 1.0, "iron_cast", n=2, step=0.04)
    v1 = bm.bone("stickers", vis={VARIANT: [1]})
    sleeve = bm.box((0, 6.2, 0), (3.7, 5.0, 3.7), "paper", bone=v1)
    bm.dec(sleeve, "north", "nrb_poster", title="HELP")
    bm.dec(sleeve, "west", "nrb_poster", title="LOST")
    bm.dec(sleeve, "east", "nrb_label", box=(0.05, 0.1, 0.95, 0.5), fill=(200, 60, 40), text="UV|SAFE")
    bm.box((0, 9.0, 0), (3.8, 0.5, 3.8), "tape_grey", bone=v1, uv=0.5)


def build_street_lamp_head(bm: BlockModel, e):
    paint = bm.use("paint_green", base="#24342a", wear=0.45, rust=0.55)
    bm.cyl((0, 5, 0), 3.4, 10, paint, n=2, step=0.02)
    bm.cyl((0, 10.4, 0), 4.0, 0.8, paint, n=2, step=0.04)
    bm.box((0, 11.4, -8.0), (2.0, 2.0, 17.0), paint, rot=(-6, 0, 0), pivot=(0, 11.4, 0))
    bm.rod((0, 6.0, 0), (0, 10.6, -7.0), 1.0, paint, uv=0.75)
    bm.box((0, 9.8, -7.6), (0.8, 2.4, 0.8), paint, uv=0.5)
    shade = bm.use("paint_green", base="#2a3a30", wear=0.5)
    hous = bm.box((0, 12.9, -18.0), (6.0, 2.4, 9.0), shade)
    hood = bm.box((0, 14.3, -17.6), (4.8, 0.8, 7.0), shade)
    bm.box((0, 12.6, -12.6), (3.6, 2.2, 2.4), paint)
    bm.dec([hous, hood], "sides", "rust_streaks", amount=0.6)
    on = bm.bone("lens_on", vis={"nr:lit": [1]})
    off = bm.bone("lens_off", vis={"nr:lit": [0]})
    lens_on = bm.box((0, 11.45, -18.0), (5.0, 0.5, 7.4), "emissive_white", bone=on)
    bm.dec(lens_on, "down", "nrb_lens", lit=True)
    lens_off = bm.box((0, 11.45, -18.0), (5.0, 0.5, 7.4), bm.use("glass_clear", base="#8a8e86", dirt=0.7), bone=off)
    bm.dec(lens_off, "down", "nrb_lens", lit=False)
    bm.box((0, 15.2, -16.2), (3.0, 1.2, 3.0), "rope", uv=0.75)
    bm.box((0.4, 15.6, -16.0), (4.0, 0.4, 0.4), "wood_dark", rot=(0, 35, 8), uv=0.5)
    bm.box((-0.4, 15.5, -16.4), (0.4, 0.4, 3.8), "wood_dark", rot=(10, 20, 0), uv=0.5)


def build_uv_lamp(bm: BlockModel, e):
    base = bm.cyl((0, 1.0, 0), 8, 2, "plastic_black", n=2, step=0.04)
    bm.dec(base, "up", "grime", amount=0.6)
    batt = bm.box((0, 4.0, 0.4), (5, 4, 4), "plastic_yellow")
    bm.dec(batt, "north", "nrb_label", box=(0.1, 0.25, 0.9, 0.75), fill=(30, 30, 30), ink=(220, 200, 60),
           text="12V", wear=0.4)
    bm.dec(batt, "west", "nrb_warn", box=(0.15, 0.15, 0.85, 0.85), symbol="bolt")
    for x, st in ((-1.3, "plastic_red"), (1.3, "plastic_black")):
        bm.box((x, 6.3, 0.4), (0.9, 0.6, 0.9), st, uv=0.5)
    bm.rod((-1.3, 6.4, 0.4), (-0.6, 9.0, 0.9), 0.5, "rubber_black", uv=0.5)
    post = bm.box((0, 10.0, 0), (2, 8, 2), "aluminium")
    bm.dec(post, "sides", "grime", amount=0.35)
    bm.cyl((0, 13.6, 0), 3.6, 0.8, "plastic_black", n=2, step=0.04)
    on = bm.bone("tube_on", vis={"nr:powered": [1]})
    off = bm.bone("tube_off", vis={"nr:powered": [0]})
    bm.box((0, 19.0, 0), (2.4, 10, 2.4), "emissive_uv", bone=on)
    tube_off = bm.box((0, 19.0, 0), (2.4, 10, 2.4), bm.use("glass_clear", base="#9c8cb4", dirt=0.5), bone=off)
    bm.dec(tube_off, "sides", "grime", amount=0.4)
    cage = bm.box((0, 19.0, 0), (4.0, 11, 4.0), "chainlink", drop=("up", "down"))
    bm.dec(cage, "sides", "nrb_chainlink", pitch=1.0, wire=0.24, edge_rows=0.5)
    for y in (14.0, 24.0):
        bm.cyl((0, y, 0), 4.4, 0.6, "aluminium", n=2, step=0.04)
    bm.cyl((0, 25.0, 0), 4.4, 1.2, "plastic_black", n=2, step=0.04)
    bm.box((0, 26.1, 0), (0.5, 1.0, 1.6), "steel_worn", uv=0.5)


# ===========================================================================
#  瓦礫・ゴミ
# ===========================================================================
def _rubble_variant(bm: BlockModel, bone: str, v: int):
    """瓦礫の山 1 つ分（v ごとに並びと形を変える。約 12 キューブ）。"""
    rng = np.random.default_rng(1000 + v * 77)
    conc = bm.use("concrete", base="#9a9890", dirt=0.5, cracks=0.8)
    dark = bm.use("concrete_dark", base="#6a6862", dirt=0.6)
    brick = bm.use("brick_red", dirt=0.45)
    # 大きな床スラブの破片（斜めに傾く）と、その上に乗った塊
    a = rng.uniform(-30, 30)
    s1 = bm.box((rng.uniform(-2.5, 1.5), 2.2, rng.uniform(-2.5, 0.5)), (11.5, 3.2, 8.5), conc, bone=bone,
                rot=(rng.uniform(-6, 6), a, rng.uniform(7, 13)))
    s2 = bm.box((rng.uniform(1.5, 3.5), 5.0, rng.uniform(1.0, 3.5)), (8.5, 2.8, 7.0), dark, bone=bone,
                rot=(rng.uniform(8, 14), a - rng.uniform(25, 45), rng.uniform(-10, -4)))
    bm.dec([s1, s2], "up", "grime", amount=0.6)
    bm.dec([s1, s2], ["north", "east"], "cracks", amount=0.8)
    # 床スラブの断面に見える鉄筋（突き出た曲がった棒）
    for k in range(2):
        x0, z0 = rng.uniform(-5, 4), rng.uniform(-5, 4)
        p0 = (x0, rng.uniform(2.5, 4.5), z0)
        p1 = (x0 + rng.uniform(-4, 4), p0[1] + rng.uniform(3, 6.5), z0 + rng.uniform(-5, -1))
        p2 = (p1[0] + rng.uniform(-2.5, 2.5), p1[1] + rng.uniform(-1.5, 0.8), p1[2] + rng.uniform(-3, -1))
        bm.rod(p0, p1, 0.6, "rebar", bone=bone, uv=0.75)
        bm.rod(p1, p2, 0.6, "rebar", bone=bone, uv=0.75)
    # 小さな塊とレンガ
    for k in range(4):
        sz = rng.uniform(2.0, 3.6)
        st = conc if k % 2 else dark
        bm.box((rng.uniform(-6.5, 6.5), sz * 0.35, rng.uniform(-6.5, 6.5)), (sz, sz * 0.7, sz * rng.uniform(0.7, 1.1)),
               st, bone=bone, rot=(rng.uniform(-15, 15), rng.uniform(0, 90), rng.uniform(-15, 15)), uv=0.75)
    for k in range(3):
        b = bm.box((rng.uniform(-6.5, 6.5), 0.75 + (k == 2) * rng.uniform(2.5, 4.0), rng.uniform(-6.5, 6.5)),
                   (3.6, 1.4, 1.8), brick, bone=bone,
                   rot=(rng.uniform(-10, 10), rng.uniform(0, 180), rng.uniform(-12, 12)), uv=0.75)
        bm.dec(b, "sides", "grime", amount=0.4)


def build_rubble_pile(bm: BlockModel, e):
    dust = plane_y(bm, (0, 0.06, 0), 16, 16, bm.use("concrete", base="#8e8c84", cracks=0.0))
    bm.dec(dust, "up", "nrb_grit", density=0.55, radius=1.0)
    n = len(bm.states.get(VARIANT, [0]))
    for v in range(n):
        bone = bm.bone(f"v{v}", vis={VARIANT: [v]})
        _rubble_variant(bm, bone, v)


def build_debris_scatter(bm: BlockModel, e):
    grit = plane_y(bm, (0, 0.06, 0), 16, 16, bm.use("concrete", base="#7c7a72", cracks=0.0))
    bm.dec(grit, "up", "nrb_grit", density=0.45, radius=0.95)
    glass = bm.use("glass_broken", base="#9cc0ca", dirt=0.3)
    paper = bm.use("paper", base="#d0c8ae")
    can = bm.use("aluminium", base="#b8bcc0", dirt=0.4)
    n = len(bm.states.get(VARIANT, [0]))
    for v in range(n):
        rng = np.random.default_rng(500 + v * 31)
        bone = bm.bone(f"v{v}", vis={VARIANT: [v]})
        for k in range(2):
            sh = plane_y(bm, (rng.uniform(-6, 6), 0.2 + 0.05 * k, rng.uniform(-6, 6)), rng.uniform(2.4, 3.6),
                         rng.uniform(1.6, 2.8), glass, bone=bone, rot=(0, rng.uniform(0, 180), 0))
            pts = [(rng.uniform(0, 0.3), rng.uniform(0, 0.4)), (rng.uniform(0.6, 1.0), rng.uniform(0, 0.3)),
                   (rng.uniform(0.7, 1.0), rng.uniform(0.6, 1.0)), (rng.uniform(0.1, 0.4), rng.uniform(0.7, 1.0))]
            bm.dec(sh, "up", "nrb_cut_poly", poly=pts)
        pp = plane_y(bm, (rng.uniform(-4, 4), 0.25, rng.uniform(-4, 4)), 5.0, 6.4, paper, bone=bone,
                     rot=(0, rng.uniform(-40, 40), 0))
        bm.dec(pp, "up", "nrb_poster", title=["NEWS", "EVAC", "LOST", "CURE?"][v % 4])
        bm.dec(pp, "up", "grime", amount=0.6)
        if v % 2 == 0:
            cc = bm.cyl((rng.uniform(-6, 6), 0.75, rng.uniform(-6, 6)), 1.5, 2.2, can, axis="x", n=2, bone=bone,
                        tilt=(rng.uniform(0, 180), 0), uv=0.75)
            bm.dec(cc, "sides", "nrb_label", box=(0.0, 0.25, 1.0, 0.75), fill=(170, 30, 30), wear=0.6)
        else:
            gl = bm.use("glass_tinted", base="#2e5a32")
            x, z = rng.uniform(-5, 5), rng.uniform(-5, 5)
            bm.cyl((x, 0.9, z), 1.8, 4.4, gl, axis="z", n=2, bone=bone, tilt=(0, rng.uniform(0, 180)), uv=0.75)
        for k in range(2):
            bm.box((rng.uniform(-6, 6), 0.25, rng.uniform(-6, 6)), (0.4, 0.4, 1.4), "brass", bone=bone,
                   rot=(0, rng.uniform(0, 180), 0), uv=0.5)


def _trash_bag(bm, at, size, style, yaw=0.0, tilt=0.0, tear=None, knot=True):
    x, y, z = at
    sx, sy, sz = size
    a = bm.box((x, y, z), (sx, sy * 0.86, sz), style, rot=(tilt, yaw, 0))
    b = bm.box((x, y + sy * 0.04, z), (sx * 0.84, sy, sz * 0.84), style, rot=(tilt, yaw + 45, 0))
    bm.dec([a, b], "*", "nrb_wrinkle")
    if tear:
        bm.dec(a, tear[0], "nrb_wrinkle", tear=tear[1:])
    if knot:
        k = bm.box((x, y + sy * 0.55, z), (1.6, 1.4, 1.6), style, rot=(tilt + 10, yaw + 20, 12), uv=0.75)
        bm.box((x + 0.6, y + sy * 0.55 + 1.0, z), (0.6, 1.0, 1.4), style, rot=(0, yaw, 35), uv=0.5)
        return [a, b, k]
    return [a, b]


def build_trash_bags(bm: BlockModel, e):
    bag = bm.use("trash_bag")
    bag2 = bm.use("trash_bag", base="#22222a", wet=0.7)
    blue = bm.use("plastic_blue", base="#2c4f88", wear=0.2, wet=0.5)
    _trash_bag(bm, (-3.0, 3.4, -3.0), (9, 7, 9), bag, yaw=20, tilt=4, tear=("north", 0.55, 0.6, 0.16))
    _trash_bag(bm, (4.0, 3.0, 2.0), (8, 6, 8), bag2, yaw=-15, tilt=-5)
    _trash_bag(bm, (-0.6, 8.2, 0.6), (8, 6, 7), bag, yaw=40, tilt=6)
    _trash_bag(bm, (-4.2, 2.4, 4.6), (6, 4.8, 6), blue, yaw=10, knot=False)
    _trash_bag(bm, (4.6, 2.6, -4.4), (6.5, 5.2, 6), bag2, yaw=-35, tilt=-8, knot=False)
    box = bm.box((6.0, 0.8, 5.6), (5.5, 1.6, 4.5), "cardboard", rot=(0, 25, 5))
    bm.dec(box, "up", "nrb_label", box=(0.2, 0.3, 0.8, 0.7), fill=(200, 190, 160), text="FRAGILE", wear=0.6)
    bm.dec(box, "*", "grime", amount=0.7)
    spill = plane_y(bm, (2.8, 0.15, -6.0), 6.5, 3.5, bm.use("cloth_rag", blood=0.0, dirt=0.9), rot=(0, 15, 0))
    bm.dec(spill, "up", "nrb_pool", kind="stain", radius=0.45, splats=4)
    bm.box((-7.0, 0.6, -6.0), (1.2, 1.2, 2.6), bm.use("plastic_white", base="#c8c4b0", dirt=0.8),
           rot=(0, 60, 90), uv=0.5)


def build_tire_stack(bm: BlockModel, e):
    tire = bm.use("tire", axis="y")
    t1 = bm.cyl((0, 2.0, 0), 14, 4, tire, n=3, step=0.1)
    t2 = bm.cyl((0.6, 6.0, -0.4), 13, 4, tire, n=3, step=0.1, rot0=12)
    t3 = bm.cyl((-0.6, 10.1, 0.5), 13.6, 4, tire, n=3, step=0.1, rot0=5, tilt=(2.5, -2.0))
    for t in (t1, t2, t3):
        bm.dec(t, "sides", "nrb_tread", period=1.5)
        bm.dec(t, "up", "nrb_tire_top", ri=0.48, ro=1.0)
    bm.dec(t3, "sides", "grime", amount=0.5)
    # 立てかけたタイヤ（ホイール付き。x 軸の円柱を z で傾ける）
    wheel = bm.use("tire", axis="x")
    lean = bm.cyl((8.0, 6.6, 1.0), 13, 4, wheel, axis="x", n=3, step=0.1, tilt=(0, 22))
    bm.dec(lean, "sides", "nrb_tread", period=1.5)
    bm.dec(lean, ["east", "west"], "nrb_tire_top", ri=0.5, ro=1.0, hub=True)
    # 穴に溜まった水と油、足元の泥
    mud = plane_y(bm, (0, 0.06, 0), 16, 16, bm.use("asphalt", base="#2c2a26", cracks=0.0))
    bm.dec(mud, "up", "nrb_pool", kind="oil", radius=0.45, splats=5, alpha=200)


# ===========================================================================
#  箱・ルート
# ===========================================================================
def build_wooden_crate(bm: BlockModel, e):
    body = bm.box((0, 7, 0), (14, 14, 14), "wood_raw")
    bm.dec(body, "*", "nrb_planks", width=3.5, axis="h", nails=False)
    bm.dec(body, "sides", "grime", amount=0.45)
    frame = bm.use("wood_raw", base="#9c7a50", wear=0.3, dirt=0.4)
    edges = []
    for y in (0.8, 13.2):
        for z in (-6.6, 6.6):
            edges.append(bm.box((0, y, z), (14.8, 1.6, 1.6), frame))
        for x in (-6.6, 6.6):
            edges.append(bm.box((x, y, 0), (1.6, 1.6, 11.6), frame))
    for x in (-6.6, 6.6):
        for z in (-6.6, 6.6):
            edges.append(bm.box((x, 7, z), (1.6, 11.6, 1.6), frame))
    nails_on(bm, edges[:4], "north", [(-6.6, 0.8, -7.4), (6.6, 0.8, -7.4), (-6.6, 13.2, -7.4), (6.6, 13.2, -7.4),
                                      (0, 0.8, -7.4), (0, 13.2, -7.4)], r=0.3)
    d1 = bm.rod((-5.8, 1.6, -7.3), (5.8, 12.4, -7.3), 1.4, frame, h=1.4)
    d2 = bm.rod((7.3, 1.6, -5.8), (7.3, 12.4, 5.8), 1.4, frame, h=1.4)
    bm.dec([d1, d2], "*", "grime", amount=0.4)
    bm.dec(body, "north", "nrb_stencil", text="FRAGILE", at=(0.5, 0.3), h=0.12, colour=(32, 28, 24))
    bm.dec(body, "north", "nrb_stencil", text="NR-AID 03", at=(0.5, 0.78), h=0.1, colour=(150, 30, 26))
    bm.dec(body, "west", "nrb_stencil", text="^ ^", at=(0.5, 0.25), h=0.14, colour=(32, 28, 24))
    bm.dec(body, "west", "nrb_stencil", text="THIS SIDE UP", at=(0.5, 0.45), h=0.08, colour=(32, 28, 24))
    bm.dec(body, "up", "nrb_stencil", text="NR", at=(0.5, 0.5), h=0.2, colour=(32, 28, 24))
    bm.dec(body, "east", "handprint", at=(0.35, 0.6), size=0.4)
    bm.dec(body, "north", "bullet_hole", at=(0.72, 0.55), size=0.03)
    # 縄の取っ手
    bm.box((-7.6, 9.5, 0), (0.6, 0.6, 4.0), "rope", uv=0.75)
    bm.box((-7.6, 9.5, -2.0), (0.6, 2.0, 0.6), "rope", uv=0.5)
    bm.box((-7.6, 9.5, 2.0), (0.6, 2.0, 0.6), "rope", uv=0.5)


def build_survivor_stash(bm: BlockModel, e):
    olive = bm.use("paint_olive", base="#4a5634", wear=0.55, rust=0.45)
    olive2 = bm.use("paint_olive", base="#3e482c", wear=0.6, rust=0.5)
    body = bm.box((0, 3.5, 0), (14, 7, 10), olive)
    bm.dec(body, "up", "nrb_inside", items=[("bandage", (0.25, 0.35, 0.22, 0.3)), ("can", (0.55, 0.3, 0.14, 0.4)),
                                            ("pills", (0.75, 0.32, 0.12, 0.22)), ("cash", (0.35, 0.72, 0.3, 0.25)),
                                            ("ammo", (0.72, 0.72, 0.2, 0.3)), ("battery", (0.12, 0.7, 0.1, 0.3))])
    bm.dec(body, "north", "nrb_stencil", text="NR SUPPLY", at=(0.5, 0.4), h=0.2, colour=(222, 220, 206))
    bm.dec(body, "north", "nrb_uv_mark", at=(0.82, 0.62), size=0.4)
    bm.dec(body, "west", "nrb_tally", box=(0.1, 0.3, 0.9, 0.7), groups=3, last=2)
    bm.dec(body, "sides", "grime", amount=0.55)
    # 底の縁と角の金具
    for x in (-6.7, 6.7):
        for z in (-4.7, 4.7):
            bm.box((x, 0.9, z), (1.4, 1.8, 1.4), "steel_worn", uv=0.5)
    # 蓋（閉じた・開いた）
    lid_c = bm.bone("lid_closed", vis={"nr:open": [0]})
    lid_o = bm.bone("lid_open", vis={"nr:open": [1]})
    lid = [bm.box((0, 8.0, 0), (14.4, 2.0, 10.4), olive2, bone=lid_c)]
    bm.dec(lid[0], "up", "nrb_stencil", text="NR", at=(0.5, 0.5), h=0.3, colour=(222, 220, 206))
    for x in (-3.5, 3.5):
        lid.append(bm.box((x, 8.05, 0), (1.6, 2.2, 10.7), bm.use("cloth_rag", base="#3a3e2a", blood=0.0),
                          bone=lid_c, uv=0.75))
    for x in (-6.8, 6.8):
        lid.append(bm.box((x, 8.0, -4.9), (1.2, 2.2, 1.2), "steel_worn", bone=lid_c, uv=0.5))
    lid.append(bm.box((0, 7.6, -5.45), (2.2, 1.4, 0.4), "steel_dark", bone=lid_c, uv=0.5))   # 掛け金
    rot = [-108.0, 0.0, 0.0]
    bm.bones[lid_o].rotation = rot
    bm.bones[lid_o].pivot = [0.0, 7.0, 5.2]
    bm.clone(lid, lid_o)
    # 取っ手・受け金・南京錠
    for x in (-7.4, 7.4):
        bm.box((x, 5.0, 0), (0.8, 0.8, 3.6), "steel_dark", uv=0.5)
    bm.box((0, 6.2, -5.15), (2.0, 1.2, 0.3), "steel_dark", uv=0.5)
    lock = bm.bone("padlock", vis={"nr:locked": [1], "nr:open": [0]})
    pl = bm.box((0, 5.0, -5.7), (1.8, 2.0, 0.8), "brass", bone=lock, uv=0.75)
    bm.dec(pl, "north", "nrb_label", box=(0.4, 0.45, 0.6, 0.7), fill=(30, 26, 20), wear=0.0)
    bm.box((0, 6.4, -5.7), (1.2, 1.0, 0.3), "steel_clean", bone=lock, uv=0.5)


def build_med_cabinet(bm: BlockModel, e):
    white = bm.use("plastic_white", base="#dcdad0", dirt=0.6, wear=0.4)
    box = bm.box((0, 8, 6), (10, 12, 4), white)
    bm.dec(box, "north", "nrb_inside", floor=(214, 212, 204), wall=(190, 188, 180),
           items=[("pills", (0.25, 0.22, 0.16, 0.14)), ("bandage", (0.6, 0.22, 0.3, 0.14)),
                  ("can", (0.3, 0.55, 0.2, 0.16)), ("pills", (0.7, 0.55, 0.14, 0.12)),
                  ("cloth", (0.5, 0.85, 0.6, 0.1))])
    bm.drop_faces(box, "south")
    shelf = bm.box((0, 8, 6.2), (9.4, 0.4, 3.4), white, uv=0.5)
    door_c = bm.bone("door_closed", vis={"nr:open": [0]})
    door_o = bm.bone("door_open", vis={"nr:open": [1]})
    door = bm.box((0, 8, 3.7), (10.4, 12.4, 0.6), white, bone=door_c)
    bm.dec(door, "north", "nrb_label", box=(0.33, 0.18, 0.67, 0.46), fill=(200, 30, 28), symbol="cross",
           sym_box=(0.36, 0.2, 0.64, 0.44), sym_ink=(236, 234, 228), wear=0.3)
    bm.dec(door, "north", "nrb_stencil", text="FIRST AID", at=(0.5, 0.58), h=0.08, colour=(170, 30, 28))
    bm.dec(door, "north", "handprint", at=(0.72, 0.62), size=0.45)
    bm.dec(door, "north", "rust_streaks", amount=0.4)
    latch = bm.box((4.6, 8, 3.25), (0.6, 1.4, 0.4), "steel_worn", bone=door_c, uv=0.5)
    rot = [0.0, -105.0, 0.0]
    bm.bones[door_o].rotation = rot
    bm.bones[door_o].pivot = [-5.2, 8.0, 3.4]
    bm.clone([door, latch], door_o)
    for y in (4, 12):
        bm.box((-5.25, y, 3.6), (0.5, 2.0, 0.6), "steel_worn", uv=0.5)
    # 壁を伝う血の筋と床に落ちた包帯
    bm.box((2.0, 0.15, 5.0), (3.0, 0.3, 1.4), bm.use("cloth_rag", base="#d8d0bc", blood=0.6), rot=(0, 20, 0),
           uv=0.75)


def build_crafting_bench(bm: BlockModel, e):
    top = bm.box((0, 13, 0), (16, 2, 12), bm.use("wood_old", base="#7a5c40", planks=3.0))
    bm.dec(top, "up", "burn", at=(0.7, 0.35), size=0.22)
    bm.dec(top, "up", "nrb_pool", kind="oil", at=(0.3, 0.6), radius=0.18, splats=3, cut=False)
    bm.dec(top, "up", "nrb_claw", at=(0.45, 0.3), size=0.3, angle=10, n=3, blood=0.0)
    for x in (-7, 7):
        for z in (-5, 5):
            bm.box((x, 6, z), (2, 12, 2), "wood_dark")
    bm.box((0, 3, 0), (14, 1, 10), bm.use("plywood", base="#a88a5e"))
    bm.box((0, 9.5, 5.6), (14, 1.2, 0.8), "wood_dark", uv=0.75)
    # 有孔ボードと吊った工具
    peg = bm.box((0, 19.5, 6.6), (16, 11, 0.8), bm.use("plywood", base="#a4865c", dirt=0.5))
    bm.dec(peg, "north", "nrb_pegboard", step=1.0, shadows=[("wrench", (0.62, 0.45), 0.35), ("saw", (0.85, 0.5), 0.4)])
    bm.dec(peg, "north", "nrb_stencil", text="NO LOOTERS", at=(0.32, 0.12), h=0.1, colour=(160, 30, 26))
    bm.box((-7.2, 19.5, 5.9), (1.0, 11, 1.0), "wood_dark", uv=0.5)
    bm.box((7.2, 19.5, 5.9), (1.0, 11, 1.0), "wood_dark", uv=0.5)
    # 金槌・レンチ・のこぎり
    bm.box((-3.5, 19.0, 5.9), (0.7, 5.0, 0.6), "wood_old", uv=0.75)
    bm.box((-3.5, 21.6, 5.9), (2.6, 1.0, 0.9), "steel_dark", uv=0.75)
    bm.box((1.6, 19.6, 6.0), (0.8, 5.5, 0.4), "steel_clean", uv=0.75)
    saw = bm.box((5.2, 19.0, 6.05), (3.0, 6.0, 0.2), "steel_clean")
    bm.dec(saw, "north", "nrb_teeth", n=10, depth=0.06)
    bm.box((5.2, 22.4, 6.0), (2.2, 1.6, 0.6), "wood_old", uv=0.75)
    # 万力
    vise = bm.use("steel_painted", base="#2e4e7a", rust=0.4)
    bm.box((-5.5, 15.0, -4.6), (3.6, 2.0, 2.6), vise)
    bm.box((-5.5, 16.6, -5.2), (3.6, 1.4, 1.2), vise, uv=0.75)
    bm.box((-5.5, 16.6, -3.4), (3.6, 1.4, 1.2), vise, uv=0.75)
    bm.box((-5.5, 15.2, -6.8), (0.5, 0.5, 2.2), "steel_clean", uv=0.5)
    bm.box((-5.5, 15.2, -7.9), (2.6, 0.4, 0.4), "steel_clean", uv=0.5)
    # 作業灯（クランプの腕と笠、光る電球）
    bm.rod((5.6, 14.0, 4.4), (5.6, 22.0, 2.8), 0.6, "steel_dark", uv=0.5)
    bm.rod((5.6, 22.0, 2.8), (3.6, 22.6, -0.5), 0.6, "steel_dark", uv=0.5)
    shade = bm.box((3.4, 22.2, -1.0), (3.0, 1.6, 3.0), bm.use("paint_green", base="#3a5a3a"), rot=(-15, 0, 0))
    bm.box((3.4, 21.3, -1.2), (1.6, 0.6, 1.6), "emissive_amber", uv=0.75)
    # 天板の上: テープを巻いたマチェーテ・缶・釘の箱
    bm.box((0.0, 14.15, -1.0), (7.0, 0.3, 1.4), bm.use("steel_worn", blood=0.5), rot=(0, 20, 0))
    bm.box((-4.2, 14.4, -0.2), (2.6, 0.8, 1.2), "tape_black", rot=(0, 20, 0), uv=0.75)
    bm.cyl((3.0, 15.4, 2.6), 2.4, 2.8, bm.use("paint_red", base="#963028"), n=2, uv=0.75)
    nb = bm.box((-1.5, 14.6, 3.0), (2.6, 1.2, 1.8), "cardboard", uv=0.75)
    bm.dec(nb, "up", "nrb_inside", floor=(70, 66, 60), items=[("ammo", (0.5, 0.5, 0.8, 0.8))])
    # 棚の上の赤い工具箱と塗料缶
    tb = bm.box((3.5, 5.0, 0.5), (6.0, 3.0, 4.0), "plastic_red")
    bm.box((3.5, 6.8, 0.5), (3.0, 0.6, 0.8), "plastic_black", uv=0.5)
    bm.dec(tb, "north", "nrb_label", box=(0.3, 0.3, 0.7, 0.6), fill=(30, 30, 30), ink=(230, 230, 230), text="NR")
    bm.cyl((-4.0, 4.9, 0.0), 2.6, 2.8, bm.use("paint_white", base="#c8c4b8"), n=2, uv=0.75)


# ===========================================================================
#  ゴアの飾り
# ===========================================================================
def build_blood_pool(bm: BlockModel, e):
    n = len(bm.states.get(VARIANT, [0]))
    wet = bm.use("blood_wet")
    for v in range(n):
        bone = bm.bone(f"v{v}", vis={VARIANT: [v]})
        rng = np.random.default_rng(300 + v * 13)
        p = plane_y(bm, (0, 0.08 + 0.01 * v, 0), 16, 16, wet, bone=bone)
        kw = dict(kind="blood", radius=rng.uniform(0.3, 0.42), splats=int(rng.integers(5, 11)), alpha=236,
                  at=(rng.uniform(0.42, 0.58), rng.uniform(0.42, 0.58)))
        if v == 3:
            kw.update(stretch=2.4, angle=rng.uniform(-30, 30), radius=0.2)       # 引きずった跡
        bm.dec(p, "up", "nrb_pool", **kw)
        # 隣のマスへはみ出す乾いた縁
        q = plane_y(bm, (rng.uniform(-3, 3) + (6 if v % 2 else -6), 0.06, rng.uniform(-3, 3)), 8, 8,
                    bm.use("blood_dry"), bone=bone, rot=(0, rng.uniform(0, 90), 0))
        bm.dec(q, "up", "nrb_pool", kind="stain", radius=0.32, splats=6, alpha=220)


def _bone_rod(bm, p0, p1, w, bone, st):
    c = bm.rod(p0, p1, w, st, bone=bone, uv=0.75)
    for end in (p0, p1):
        bm.box(end, (w * 1.6, w * 1.4, w * 1.6), st, bone=bone, uv=0.5)
    return c


def build_gore_remains(bm: BlockModel, e):
    bone_st = bm.use("bone", age=0.7, blood=0.45, dirt=0.4)
    meat = bm.use("gore_meat")
    rag = bm.use("cloth_rag", blood=0.6, torn=0.6)
    stain = plane_y(bm, (0, 0.06, 0), 16, 16, bm.use("blood_dry"))
    bm.dec(stain, "up", "nrb_pool", kind="stain", radius=0.42, splats=9)
    n = len(bm.states.get(VARIANT, [0]))
    for v in range(n):
        bn = bm.bone(f"v{v}", vis={VARIANT: [v]})
        if v == 0:
            # 胸郭: 背骨と左右の肋骨の弧、残った肉、破れたシャツ
            bm.rod((0, 0.7, -4.5), (0.3, 0.9, 4.5), 1.3, bone_st, bone=bn)
            for k in range(4):
                z = -2.8 + k * 1.7
                for s in (-1, 1):
                    p0 = (0.4 * s, 1.0, z)
                    p1 = (3.0 * s, 3.0 - k * 0.2, z + 0.3)
                    p2 = (3.6 * s, 0.6, z + 0.6)
                    bm.rod(p0, p1, 0.55, bone_st, bone=bn, uv=0.5)
                    bm.rod(p1, p2, 0.55, bone_st, bone=bn, uv=0.5)
            m = bm.box((0.4, 1.1, 1.0), (3.6, 1.6, 3.0), meat, bone=bn, rot=(0, 20, 8))
            bm.dec(m, "up", "wound", size=0.6, wet=1.0)
            r = plane_y(bm, (1.5, 0.2, 2.5), 9, 7, rag, bone=bn, rot=(0, -20, 0))
            bm.dec(r, "up", "nrb_pool", kind="stain", radius=0.4, splats=3, cut=False)
        elif v == 1:
            sk = bm.box((-3.5, 1.7, -3.0), (3.4, 3.4, 3.8), bone_st, bone=bn, rot=(0, 30, 20))
            bm.dec(sk, "north", "nrb_skull")
            bm.dec(sk, "up", "cracks", amount=1.0)
            _bone_rod(bm, (0.5, 0.5, -1.0), (6.0, 0.5, 2.5), 0.9, bn, bone_st)
            _bone_rod(bm, (6.0, 0.5, 2.5), (3.0, 0.45, 6.5), 0.7, bn, bone_st)
            bm.box((2.0, 0.4, 7.0), (2.4, 0.6, 2.0), bone_st, bone=bn, rot=(0, 40, 0), uv=0.5)
            j = plane_y(bm, (-1.0, 0.25, 2.0), 8, 8, bm.use("leather_brown", blood=0.5), bone=bn, rot=(0, 15, 0))
            bm.dec(j, "up", "nrb_pool", kind="stain", radius=0.35, splats=3, cut=False)
            m = bm.box((4.0, 0.7, -4.0), (3.0, 1.4, 2.2), meat, bone=bn, rot=(0, -30, 0))
            bm.dec(m, "up", "wound", size=0.5, wet=1.0)
        else:
            _bone_rod(bm, (-3.5, 0.6, -5.5), (-2.0, 0.6, 2.5), 1.0, bn, bone_st)
            _bone_rod(bm, (-2.0, 0.6, 2.5), (-1.5, 0.5, 7.0), 0.8, bn, bone_st)
            _bone_rod(bm, (2.0, 0.6, -6.0), (4.5, 0.6, 1.0), 1.0, bn, bone_st)
            pel = bm.box((0, 1.2, -6.5), (5.5, 2.4, 3.0), bone_st, bone=bn, rot=(10, 0, 0))
            bm.dec(pel, "up", "wound", size=0.4, wet=0.8)
            for x, z, a in ((-1.6, 7.0, 10), (5.4, 2.6, -30)):
                sh = bm.box((x, 1.0, z), (2.4, 2.0, 4.0), bm.use("leather_brown", base="#2a2622", blood=0.3),
                            bone=bn, rot=(0, a, 0), uv=0.75)
                bm.dec(sh, "up", "nrb_label", box=(0.2, 0.6, 0.8, 0.95), fill=(40, 36, 32), wear=0.0)
            jn = plane_y(bm, (1.0, 0.25, 0.5), 8, 10, bm.use("cloth_rag", base="#3a4a66", blood=0.5, torn=0.5),
                         bone=bn, rot=(0, 10, 0))
            m = bm.box((-4.5, 0.8, 4.0), (2.6, 1.6, 2.6), meat, bone=bn, rot=(10, 30, 0))
            bm.dec(m, "up", "wound", size=0.5, wet=1.0)


# ===========================================================================
#  足場・パルクール
# ===========================================================================
def build_chainlink_fence(bm: BlockModel, e):
    mesh = bm.box((0, 7.8, 0), (16, 14.8, 0.2), "chainlink", drop=("up", "down", "east", "west"))
    bm.dec(mesh, ["north", "south"], "nrb_chainlink", pitch=1.4, wire=0.3, hole=(0.68, 0.72, 0.16, 0.2))
    flap = bm.box((3.6, 4.4, -1.2), (3.2, 2.6, 0.2), "chainlink", rot=(-48, 10, 0),
                  drop=("up", "down", "east", "west"))
    bm.dec(flap, ["north", "south"], "nrb_chainlink", pitch=1.4, wire=0.3)
    al = bm.use("aluminium", dirt=0.5)
    bm.cyl((-7.3, 8, 0), 1.4, 16, al, n=2)
    bm.cyl((-7.3, 16.3, 0), 1.8, 0.6, al, n=2, uv=0.5)
    bm.cyl((0, 15.4, 0), 1.0, 16, al, axis="x", n=2)
    bm.box((0, 0.6, 0), (16, 0.3, 0.3), "steel_worn", uv=0.5)
    for y in (4, 10):
        bm.box((-6.7, y, 0), (0.6, 0.5, 0.5), "steel_worn", uv=0.5)
    # 上の有刺鉄線（腕で持ち上げる）
    bm.rod((-7.3, 15.6, 0), (-7.3, 18.0, -1.6), 0.5, "steel_dark", uv=0.5)
    barb = bm.box((0, 18.0, -1.6), (16, 1.4, 0.1), "steel_rusty", drop=("up", "down", "east", "west"))
    bm.dec(barb, ["north", "south"], "nrb_strand")
    # 引っかかった布と、針金で留めた警告の板
    rag = bm.box((4.0, 10.0, -0.25), (2.2, 3.2, 0.2), bm.use("cloth_red", blood=0.3), rot=(0, 0, 12), uv=0.75)
    sign = bm.box((-2.5, 8.5, -0.25), (5.0, 3.2, 0.2), bm.use("paint_white", base="#d8d4c8", rust=0.6))
    bm.dec(sign, "north", "nrb_label", box=(0.0, 0.0, 1.0, 0.36), fill=(170, 26, 24), wear=0.4)
    bm.dec(sign, "north", "nrb_stencil", text="DANGER", at=(0.5, 0.18), h=0.24, colour=(236, 234, 226))
    bm.dec(sign, "north", "nrb_stencil", text="INFECTED", at=(0.5, 0.62), h=0.22, colour=(26, 26, 28))
    bm.dec(sign, "north", "rust_streaks", amount=0.7)


def build_broken_window(bm: BlockModel, e):
    paint = bm.use("wood_painted")
    bm.box((0, 15, 0), (16, 2, 2), paint)
    sill = bm.box((0, 0.8, -0.4), (16, 1.6, 2.8), paint)
    bm.dec(sill, "up", "handprint", at=(0.35, 0.5), size=0.8)
    bm.dec(sill, "up", "nrb_grit", density=0.6, radius=0.9, cut=False)
    for x in (-7, 7):
        bm.box((x, 8, 0), (2, 12, 2), paint)
    bm.box((-3.5, 9.0, 0), (1.0, 8.0, 1.0), paint, rot=(0, 0, 18), pivot=(-3.5, 13.8, 0))
    glass = bm.use("glass_broken", base="#86a6b0", dirt=0.5)
    shards = [((-4.2, 11.6, 0), (5.4, 5.0), [(0, 0), (1, 0), (0.72, 0.38), (0.4, 0.95), (0.18, 0.5), (0, 1)]),
              ((4.2, 11.8, 0), (5.4, 4.6), [(0, 0), (1, 0), (1, 1), (0.6, 0.55), (0.25, 0.3)]),
              ((4.6, 4.0, 0), (5.2, 5.0), [(1, 0), (1, 1), (0, 1), (0.35, 0.62), (0.7, 0.2)]),
              ((-4.4, 3.2, 0), (5.0, 3.4), [(0, 0.35), (0.3, 0.6), (0.55, 0.2), (0.85, 0.7), (1, 1), (0, 1)])]
    for (at, (sx, sy), poly) in shards:
        sh = bm.box(at, (sx, sy, 0.12), glass, drop=("up", "down", "east", "west"))
        bm.dec(sh, "north", "nrb_cut_poly", poly=poly)
        bm.dec(sh, "south", "nrb_cut_poly", poly=[(1 - u, v) for u, v in poly])
    # 内側に垂れたちぎれたカーテン
    cur = plane_z(bm, (4.4, 8.6, 1.5), 5.6, 12.0, bm.use("cloth_red", blood=0.25, torn=0.7), th=0.2)
    bm.dec(cur, ["north", "south"], "nrb_cut_poly", poly=[(0, 0), (1, 0), (1, 0.62), (0.8, 0.9), (0.62, 0.7),
                                                         (0.45, 1.0), (0.22, 0.78), (0, 0.95)])
    bm.box((4.4, 14.6, 1.5), (6.4, 0.5, 0.5), "steel_worn", uv=0.5)
    # 窓の下に落ちたガラス片
    gp = plane_y(bm, (0, 0.06, -4.5), 14, 6, glass)
    bm.dec(gp, "up", "nrb_grit", density=0.5, radius=0.9)


def build_graffiti_panel(bm: BlockModel, e):
    """壁の板（+Z が壁）。4 つの落書きは板ごとボーンで出し分け（板は左右 2 枚の合板）。"""
    ply = bm.use("plywood", base="#b09068", dirt=0.5)
    ply2 = bm.use("plywood", base="#a08460", dirt=0.6)
    n = len(bm.states.get(VARIANT, [0]))
    zf = 6.6    # 板の前の面
    for v in range(n):
        bn = bm.bone(f"v{v}", vis={VARIANT: [v]})
        L = bm.box((-4.0, 8, 7.2), (8, 16, 1.2), ply, bone=bn)
        R = bm.box((4.0, 8, 7.2), (8, 16, 1.2), ply2, bone=bn)
        bm.drop_faces([L, R], "south")
        both = [L, R]
        bm.dec(both, "north", "grime", amount=0.45)
        if v == 0:
            spray_lines(bm, both, "north", [[(-6.5, 6.5, zf), (3.5, 6.5, zf)], [(1.0, 9.5, zf), (5.0, 6.5, zf),
                                                                                 (1.0, 3.5, zf)]],
                        colour=(196, 28, 24), width=1.1, drip=0.9)
            spray_text(bm, both, "north", "SAFE", (-6.2, 14.0, zf), 4.0, colour=(196, 28, 24), width=0.8)
            spray_text(bm, both, "north", "UV 2 BLKS", (-6.6, 2.6, zf), 1.8, colour=(232, 230, 220), width=0.4,
                       drip=0.3)
        elif v == 1:
            bm.dec(L, "north", "nrb_tally", box=(0.08, 0.5, 0.95, 0.85), groups=4, last=3)
            bm.dec(R, "north", "nrb_tally", box=(0.05, 0.5, 0.9, 0.85), groups=4, last=2)
            spray_text(bm, both, "north", "DAY 47", (-6.0, 14.2, zf), 3.4, colour=(30, 30, 32), width=0.6)
            spray_text(bm, both, "north", "NO FOOD", (-5.6, 8.8, zf), 2.4, colour=(160, 30, 24), width=0.5)
        elif v == 2:
            bm.dec(L, "north", "nrb_label", box=(0.2, 0.18, 1.0, 0.62), fill=(214, 206, 180), symbol="skull",
                   sym_box=(0.25, 0.2, 0.95, 0.6), sym_ink=(24, 22, 20), wear=0.5)
            spray_text(bm, both, "north", "DEAD", (0.5, 14.0, zf), 3.4, colour=(196, 28, 24), width=0.7)
            spray_text(bm, both, "north", "INSIDE", (0.4, 9.8, zf), 2.6, colour=(196, 28, 24), width=0.6)
            spray_text(bm, both, "north", "DONT OPEN", (-6.8, 3.6, zf), 2.0, colour=(232, 230, 220), width=0.45,
                       drip=0.3)
        else:
            bm.dec(R, "north", "nrb_uv_mark", at=(0.5, 0.35), size=0.75)
            spray_text(bm, both, "north", "HELP", (-6.8, 13.0, zf), 3.0, colour=(40, 80, 170), width=0.6)
            spray_lines(bm, both, "north", [[(-7.0, 13.5, zf), (-0.6, 9.4, zf)], [(-7.0, 9.6, zf), (-0.8, 13.4, zf)]],
                        colour=(196, 28, 24), width=0.8, drip=0.6)
            spray_text(bm, both, "north", "RUNNERS", (-6.6, 4.6, zf), 2.2, colour=(60, 170, 80), width=0.5)
    for x in (-7.2, 7.2):
        for y in (1.0, 15.0):
            bm.box((x, y, 6.45), (0.7, 0.7, 0.5), "steel_rusty", uv=0.5)
    bm.box((0, 1.0, 6.45), (0.7, 0.7, 0.5), "steel_rusty", uv=0.5)


def build_scaffold_platform(bm: BlockModel, e):
    deck = bm.use("plywood", base="#b89a68", dirt=0.6)
    planks = []
    for k, z in enumerate((-6.0, -2.0, 2.0, 6.0)):
        p = bm.box((0, 14.4, z), (16, 1.4, 3.8), deck)
        planks.append(p)
    bm.dec(planks, "up", "nrb_footprints", n=3)
    bm.dec(planks[1], "up", "nrb_pool", kind="stain", at=(0.3, 0.5), radius=0.2, splats=3, cut=False)
    bm.dec(planks, "sides", "grime", amount=0.5)
    toe = bm.box((0, 16.2, -7.6), (16, 2.0, 0.6), bm.use("plastic_yellow", wear=0.6, dirt=0.6))
    bm.dec(toe, ["north", "south"], "stripe", hazard=True, width=0.45, colour=(232, 190, 36))
    galv = bm.use("steel_worn", base="#9aa0a2", dirt=0.45)
    for x in (-7.3, 7.3):
        for z in (-7.3, 7.3):
            bm.cyl((x, 8, z), 1.4, 16, galv, n=2, uv=0.75)
            bm.box((x, 0.2, z), (2.4, 0.4, 2.4), "steel_dark", uv=0.5)
    for z in (-7.3, 7.3):
        bm.cyl((0, 13.0, z), 1.2, 16, galv, axis="x", n=2, uv=0.75)
    for x in (-7.3, 7.3):
        bm.box((x, 13.0, 0), (1.2, 1.2, 14.6), galv, uv=0.75)
        bm.rod((x, 1.0, -7.0), (x, 12.6, 7.0), 1.0, galv, uv=0.75)
    for x in (-7.3, 7.3):
        for z in (-7.3, 7.3):
            bm.box((x, 13.0, z), (2.0, 2.0, 2.0), "steel_dark", uv=0.5)
    pail = bm.cyl((4.5, 16.6, 2.0), 3.0, 3.0, bm.use("paint_white", base="#d0ccc0"), n=2, uv=0.75)
    bm.dec(pail, "sides", "drips", start=0.15, amount=0.6)
    bm.dec(pail, "up", "nrb_pool", kind="stain", radius=0.4, splats=0, cut=False)


def build_zipline_anchor(bm: BlockModel, e):
    plate = bm.box((0, 0.75, 0), (8, 1.5, 8), "steel_dark")
    bm.dec(plate, "up", "nrb_diamond_plate", pitch=1.2)
    for x in (-3, 3):
        for z in (-3, 3):
            bm.cyl((x, 1.8, z), 1.0, 0.6, "steel_worn", n=2, uv=0.5)
    yel = bm.use("paint_yellow", wear=0.55, rust=0.65)
    post = bm.cyl((0, 7.5, 0), 3.0, 12.0, yel, n=2)
    bm.dec(post, "sides", "stripe", hazard=True, width=0.18, offset=0.88, colour=(232, 190, 36))
    bm.dec(post, "sides", "rust_streaks", amount=0.7)
    head = bm.box((0, 14.8, 0), (4.6, 3.2, 4.6), "steel_dark")
    bm.dec(head, "north", "nrb_rivets", step=1.2, inset=0.4, r=0.22)
    bm.box((0, 16.6, 0), (2.0, 0.8, 2.0), "steel_worn", uv=0.5)
    wheel = bm.cyl((2.8, 15.0, 0), 3.6, 1.2, "aluminium", axis="x", n=3, step=0.05)
    bm.dec(wheel, ["east", "west"], "nrb_tire_top", ri=0.35, ro=1.0, hub=True)
    bm.box((3.6, 15.0, 0), (0.8, 0.8, 0.8), "steel_clean", uv=0.5)
    bm.rod((2.8, 16.6, -0.5), (2.8, 19.5, -15.0), 0.35, "steel_clean", uv=1.0)
    bm.rod((-1.0, 15.6, 1.5), (-1.0, 1.6, 9.5), 0.3, "steel_clean", uv=1.0)
    tb = bm.box((2.8, 17.2, -3.4), (0.7, 0.7, 2.2), "steel_worn", rot=(-11, 0, 0), uv=0.5)
    tag = bm.box((0, 11.0, -1.65), (2.4, 2.0, 0.2), "paint_white", uv=1.0)
    bm.dec(tag, "north", "nrb_label", box=(0.0, 0.0, 1.0, 1.0), fill=(30, 110, 60), symbol="arrow_r",
           sym_box=(0.15, 0.2, 0.85, 0.8), sym_ink=(236, 236, 228), wear=0.4)


# ===========================================================================
#  屋上
# ===========================================================================
def build_ac_unit(bm: BlockModel, e):
    case = bm.use("plastic_white", base="#c8c4b4", dirt=0.6, wear=0.4)
    body = bm.box((0, 6.2, 0), (16, 10.4, 10), case)
    bm.dec(body, ["east", "west"], "nrb_slits", box=(0.12, 0.15, 0.88, 0.85), rows=9)
    bm.dec(body, "up", "nrb_slits", box=(0.06, 0.1, 0.94, 0.9), rows=12)
    bm.dec(body, "sides", "rust_streaks", amount=0.5)
    bm.dec(body, "sides", "grime", amount=0.6)
    bm.dec(body, "north", "nrb_label", box=(0.68, 0.12, 0.94, 0.3), fill=(210, 208, 200), text="NR AIR", wear=0.5)
    bm.dec(body, "north", "nrb_warn", box=(0.74, 0.62, 0.9, 0.85), symbol="bolt")
    grille = bm.box((-2.5, 6.2, -5.2), (9.2, 9.2, 0.5), "steel_dark")
    bm.dec(grille, "north", "nrb_grille", at=(0.5, 0.5), r=0.47, rings=7, blades=3)
    bm.dec(grille, "north", "rust_streaks", amount=0.6)
    for z in (-3.6, 3.6):
        bm.box((0, 0.5, z), (16.4, 1.0, 1.6), "steel_rusty", uv=0.75)
    for y in (3.0, 5.0):
        bm.rod((6.0, y, 4.9), (6.0, y, 7.4), 1.1, "copper_wire", uv=0.75)
        bm.rod((6.0, y, 7.4), (6.0, y - 2.5, 7.6), 1.1, "rubber_black", uv=0.75)
    sp = bm.box((7.3, 4.0, 0.5), (1.6, 5.0, 4.0), case, uv=0.75)
    bm.dec(sp, "west", "nrb_rivets", step=1.4, inset=0.3, r=0.2)
    bm.dec(sp, "west", "nrb_label", box=(0.2, 0.2, 0.8, 0.5), fill=(226, 190, 40), text="HV", wear=0.4)


def build_roof_vent(bm: BlockModel, e):
    al = bm.use("aluminium", base="#a4a8ac", dirt=0.5)
    flash = bm.box((0, 0.3, 0), (9, 0.6, 9), bm.use("asphalt", base="#3a3836"))
    bm.dec(flash, "up", "grime", amount=0.7)
    duct = bm.box((0, 3.4, 0), (6, 5.6, 6), al)
    bm.dec(duct, "sides", "nrb_rivets", step=1.2, inset=0.35, r=0.2)
    bm.dec(duct, "sides", "rust_streaks", amount=0.6)
    bm.cyl((0, 7.4, 0), 5.0, 2.8, al, n=2)
    bm.cyl((0, 8.9, 0), 6.2, 0.6, al, n=2, uv=0.5)
    tur = bm.cyl((0, 11.2, 0), 9.0, 4.2, al, n=3, step=0.1, rot0=7)
    bm.dec(tur, "sides", "stripe", count=6, orient="d", width=0.05, gap=0.12, colour=(70, 72, 74))
    bm.dec(tur, "sides", "rust_streaks", amount=0.7)
    bm.cyl((0, 13.6, 0), 6.8, 1.0, al, n=3, step=0.08, rot0=7)
    bm.cyl((0, 14.4, 0), 3.4, 0.8, "steel_worn", n=2, uv=0.5)
    bm.box((0, 15.0, 0), (1.0, 0.6, 1.0), "steel_dark", uv=0.5)


def build_water_tower_leg(bm: BlockModel, e):
    st = bm.use("steel_rusty", amount=0.8)
    f1 = bm.box((0, 8, -1.2), (3.0, 16, 0.6), st)
    f2 = bm.box((0, 8, 1.2), (3.0, 16, 0.6), st)
    web = bm.box((0, 8, 0), (0.6, 16, 1.8), st, uv=0.75)
    bm.dec([f1, f2], ["north", "south"], "nrb_rivets", step=2.0, inset=0.4, r=0.22, edges="lr")
    bm.dec([f1, f2], "sides", "rust_streaks", amount=0.9)
    for x in (-2.4, 2.4):
        bm.box((x, 8, -2.6), (0.5, 16, 0.5), "steel_worn", uv=0.75)
    for y in (2, 6, 10, 14):
        bm.box((0, y, -2.6), (5.3, 0.6, 0.6), "steel_worn", uv=0.75)
    bm.box((0, 15.5, 0), (5, 1, 5), "steel_dark")
    bm.box((0, 0.4, 0), (5, 0.8, 5), "steel_dark")
    bm.rod((0, 1.0, 1.6), (0, 15.0, 13.8), 1.0, st, uv=0.75)
    bm.rod((1.6, 1.0, 0), (13.8, 15.0, 0), 1.0, st, uv=0.75)


def build_fire_barrel(bm: BlockModel, e):
    drum_st = bm.use("steel_rusty", amount=0.9, burn=0.6, dirt=0.5)
    drum = bm.cyl((0, 7, 0), 11, 14, drum_st, n=3, step=0.08)
    bm.dec(drum, "up", "nrb_tire_top", ri=0.86, ro=1.0, water=False)
    bm.dec(drum, "sides", "burn", at=(0.5, 0.15), size=0.9)
    bm.dec(drum, "sides", "rust_streaks", amount=0.9)
    for y in (4.5, 9.5):
        bm.cyl((0, y, 0), 11.6, 0.9, bm.use("steel_dark", dirt=0.6), n=3, step=0.05, uv=0.5)
    lit = bm.bone("fire_on", vis={"nr:lit": [1]})
    for x in (-2.2, 2.2):
        bm.box((x, 2.0, -5.45), (1.8, 1.8, 0.3), "emissive_amber", bone=lit, uv=0.75)
    bed = bm.cyl((0, 14.08, 0), 9.4, 0.15, "char_hot", n=3, bone=lit, step=0.01)
    bm.dec(bed, "up", "burn", size=1.0, embers=True)
    flames(bm, (0, 14.0, 0), 8.0, 7.0, lit, n=3, tongues=3.0)
    off = bm.bone("fire_off", vis={"nr:lit": [0]})
    ash = bm.cyl((0, 14.08, 0), 9.4, 0.15, "ash", n=3, bone=off, step=0.01)
    bm.dec(ash, "up", "nrb_grit", density=0.6, radius=1.0, cut=False)
    bm.rod((-3.0, 12.5, -1.0), (4.0, 17.5, 2.0), 1.6, bm.use("wood_dark", burn=0.7), uv=0.75)
    bm.rod((2.5, 12.5, -3.0), (-2.0, 16.5, 3.5), 1.4, bm.use("wood_dark", burn=0.8), uv=0.75)


def build_road_sign(bm: BlockModel, e):
    tilt = (0.0, 0.0, 4.0)
    piv = (0.0, 0.0, 0.0)
    galv = bm.use("steel_worn", base="#9ea2a4", dirt=0.5)
    post = bm.box((0, 11, 0), (1.4, 22, 1.4), galv, rot=tilt, pivot=piv)
    bm.dec(post, "sides", "nrb_holes", step=1.4)
    bm.dec(post, "sides", "rust_streaks", amount=0.6)
    for y in (18.5, 25.0):
        bm.box((0, y, -0.95), (2.0, 0.8, 0.5), "steel_worn", rot=tilt, pivot=piv, uv=0.5)
    back = bm.use("steel_worn", base="#8c9092", dirt=0.5)
    n = len(bm.states.get(VARIANT, [0]))
    kinds = ["stop", "oneway", "evac", "speed"]
    plates = {"stop": ((0, 22, -1.35), (10, 10, 0.3)), "oneway": ((0, 22, -1.35), (11, 4, 0.3)),
              "evac": ((0, 21.5, -1.35), (10, 7, 0.3)), "speed": ((0, 22, -1.35), (7.5, 10, 0.3))}
    for v in range(n):
        kind = kinds[v % 4]
        bn = bm.bone(f"v{v}", vis={VARIANT: [v]})
        at, size = plates[kind]
        p = bm.box(at, size, back, bone=bn, rot=tilt, pivot=piv)
        bm.dec(p, "north", "nrb_sign", kind=kind)
        bm.dec(p, "north", "bullet_hole", at=(0.3 + 0.1 * v, 0.35), size=0.04)
        bm.dec(p, "north", "bullet_hole", at=(0.7, 0.7 - 0.05 * v), size=0.035)
        bm.dec(p, "north", "grime", amount=0.4)
        if kind == "stop":
            k = 0.29
            octa = [(k, 0), (1 - k, 0), (1, k), (1, 1 - k), (1 - k, 1), (k, 1), (0, 1 - k), (0, k)]
            bm.dec(p, "south", "nrb_cut_poly", poly=octa)
            bm.drop_faces(p, ["up", "down", "east", "west"])
        if kind == "evac":
            spray_text(bm, [p], "north", "LIES", (-3.0, 23.2, -1.55), 2.2, colour=(196, 28, 24), width=0.45, drip=0.4)
    st = bm.box((0.0, 14.0, -0.75), (1.5, 2.2, 0.1), "paper", rot=tilt, pivot=piv, uv=1.0)
    bm.dec(st, "north", "nrb_label", box=(0.0, 0.0, 1.0, 1.0), fill=(200, 196, 180), text="NR", wear=0.5)


def build_uv_shroom_patch(bm: BlockModel, e):
    moss = plane_y(bm, (0, 0.1, 0), 13, 13, bm.use("mutated", base="#4a5a34", alt="#6a7a48"))
    bm.dec(moss, "up", "nrb_pool", kind="moss", radius=0.45, splats=8)
    stem = bm.use("plastic_white", base="#d8d0e6", wear=0.1, dirt=0.3)
    cap = bm.use("fungus_uv")
    glow = bm.use("emissive_uv", base="#c890ff")
    shrooms = [(-2.0, -1.0, 6.0, 4.4), (2.5, 2.0, 4.0, 3.2), (0.0, 3.6, 2.8, 2.2), (-4.2, 3.0, 2.2, 1.8),
               (3.8, -3.6, 3.2, 2.6), (-0.6, -4.6, 1.8, 1.6)]
    for i, (x, z, h, d) in enumerate(shrooms):
        lean = ((i * 37) % 11 - 5) * 1.6
        bm.box((x, h / 2, z), (max(0.6, d * 0.24), h, max(0.6, d * 0.24)), stem, rot=(lean, 0, -lean * 0.6),
               pivot=(x, 0, z), uv=0.75)
        top_x = x + math.sin(math.radians(-lean * 0.6)) * -h
        top_z = z - math.sin(math.radians(lean)) * h
        caps = bm.cyl((top_x, h, top_z), d, max(0.6, d * 0.3), cap, n=2, step=0.03)
        bm.dec(caps, "down", "nrb_gills", n=12)
        bm.dec(caps, "up", "glow_spot", at=(0.35, 0.4), size=0.12, colour=(220, 170, 255))
        if d > 2.5:
            bm.cyl((top_x, h + d * 0.18, top_z), d * 0.6, max(0.4, d * 0.16), cap, n=2, step=0.03, uv=0.75)
    for k in range(3):
        a = k * 2.1
        bm.box((math.cos(a) * 5.0, 0.3, math.sin(a) * 5.0), (0.5, 0.5, 0.5), glow, uv=0.5)


# @@BUILDERS_TRAPS@@


# ---------------------------------------------------------------------------
#  何も専用の作りが無いブロック（カタログの部品をそのまま箱に）
# ---------------------------------------------------------------------------
def build_generic(bm: BlockModel, e):
    for p in e["model"]:
        st = p["mat"] if p["mat"] in BP.STYLES else "concrete"
        for c in [p["at"]] + list(p.get("rep", [])):
            bm.box(c, p["size"], st, rot=p.get("rot"))


BUILDERS = {k[len("build_"):]: v for k, v in list(globals().items())
            if k.startswith("build_") and callable(v) and k not in ("build_generic",)}


def build(key: str, entry: dict, seed: int = 0, states: Optional[Dict[str, list]] = None) -> BlockModel:
    """key のブロックを作る。states は gen_nr_blocks.state_schema の表（ボーンの出し入れに使う）。"""
    bm = BlockModel(key, seed)
    bm.states = dict(states or {})
    fn = BUILDERS.get(key, build_generic)
    fn(bm, entry)
    if fn is build_generic:
        bm.notes.append("generic")
    return bm
