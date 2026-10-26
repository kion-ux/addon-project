# -*- coding: utf-8 -*-
"""NIGHT RUNNER — カスタムブロックのモデル（gen_nr_blocks 専用）。

ブロック空間（`nr_spec_catalog` の約束）: 原点 = ブロックの底面中央、x・z は -8〜8、y は 0〜16（px = 単位）。
**モデルの前は north（-Z）**。置くときは `minecraft:placement_direction` の状態で回す（gen_nr_blocks）。

* `BlockModel` … mcmodel.Model の薄い包み。中心と大きさで箱を置く `box()`、正八角柱 `oct()`、
  状態で出し入れするボーン（`bone(name, vis={状態: [値]})`）、テクスチャを共有した姿勢違いの写し `clone()`
  （トラバサミの閉じた顎・開いた蓋・倒れたコーン）、ワールド座標のデカール `wd()`。
* `BUILDERS[key](bm, entry)` … ブロックごとの作り込み。カタログの部品（`entry["model"]`）は大きさ・素材・
  位置の目安で、形が読めるように足したり割ったりする。知らないキーは `build_generic`（部品をそのまま箱に）。

1 ブロックのキューブは 50 個まで（Mojang の検証の警告）、形は 30×30×30 px（gen_nr_blocks が検査）。
テクスチャは 1 単位 4 texel（64 px / ブロック）を基本に、256×256 に入らなければ 3 → 2 に落とす。
"""
from __future__ import annotations

import math
import os
import sys
import zlib
from typing import Dict, List, Optional, Sequence

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


class _GeoView:
    """nr_common.write_geometry に渡すための包み（見えない面を省いた to_json）。"""

    def __init__(self, bm: "BlockModel"):
        self.bm = bm
        self.tex_w = bm.model.tex_w
        self.tex_h = bm.model.tex_h

    def to_json(self):
        return self.bm.to_json()


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
        self.bone("root")

    # ---- ボーン・スタイル -------------------------------------------------------
    def bone(self, name: str, pivot=(0, 0, 0), rotation=None, vis: Optional[Dict[str, list]] = None) -> str:
        if name in self.bones:
            if vis:
                self.vis[name] = {k: list(v) for k, v in vis.items()}
            return name
        b = self.model.bone(name, pivot, parent=None if name == "root" else "root", rotation=rotation)
        self.bones[name] = b
        if vis:
            self.vis[name] = {k: list(v) for k, v in vis.items()}
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

    def add_style(self, name: str, st: dict) -> str:
        self.styles[name] = st
        return name

    # ---- 箱 -------------------------------------------------------------------
    def box(self, at, size, style, bone="root", rot=None, pivot=None, uv: float = 1.0, drop=(),
            decals=None, inflate=0.0) -> Cube:
        """中心 at・大きさ size の箱。style は STYLES のキーか use() の戻り値。"""
        sname = style if style in self.styles else self.use(style)
        at = [float(v) for v in at]
        size = [float(v) for v in size]
        origin = [at[i] - size[i] / 2 for i in range(3)]
        rotation = list(rot) if rot and any(abs(r) > 1e-9 for r in rot) else None
        piv = list(pivot) if pivot is not None else (at if rotation else None)
        c = Cube(origin, size, sname, inflate=inflate, pivot=piv, rotation=rotation)
        if uv != 1.0:
            self.factor[id(c)] = uv
        st = self.styles[sname]
        if st.get("_paint"):
            for f in NP.FACES:
                c.decals.setdefault(f, [])
                c.decals[f] = _as_list(c.decals[f])
                c.decals[f].insert(0, {"name": "nrb_peel", "colour": st["_paint"], "amount": 0.4})
        if decals:
            for f, dv in decals.items():
                for face in (NP.FACES if f == "*" else (NP.SIDES if f == "sides" else [f])):
                    c.decals[face] = _as_list(c.decals.get(face)) + _as_list(dv)
        dr = set(drop)
        if origin[1] <= 1e-3 and rotation is None and bone == "root":
            dr.add("down")
        if dr:
            self.drop[id(c)] = dr
        self.bones[bone].add(c)
        return c

    def oct(self, at, size, style, bone="root", uv: float = 1.0, decals=None, drop=()) -> List[Cube]:
        """正八角柱（同じ箱を Y で 45 度回したものと重ねる）。size の x と z は同じにする。"""
        a = self.box(at, size, style, bone=bone, uv=uv, decals=decals, drop=drop)
        b = self.box(at, size, style, bone=bone, rot=(0, 45, 0), pivot=at, uv=uv, decals=decals, drop=drop)
        return [a, b]

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

    def clone(self, cubes, bone: str):
        """テクスチャを共有した写しを bone に置く（塗った後に作る）。"""
        self.pending_clones.append((bone, list(_as_list(cubes))))

    # ---- 仕上げ -------------------------------------------------------------------
    def cubes(self) -> List[Cube]:
        return self.model.all_cubes()

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
                    self.drop[id(k)] = set(self.drop[id(c)])
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

    def geo_view(self) -> _GeoView:
        return _GeoView(self)

    def bone_visibility(self) -> Dict[str, str]:
        return {b: vis_molang(c) for b, c in sorted(self.vis.items())}


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, (tuple,)):
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


# ===========================================================================
#  共通の部品
# ===========================================================================
TRAP = "nr:trap_state"
VARIANT = "nr:variant"
ARMED = {TRAP: ["armed"]}
TRIGGERED = {TRAP: ["triggered"]}
IDLE = {TRAP: ["idle"]}


def spray_text(bm, cubes, faces, text, origin, height, colour=(178, 22, 20), width=0.62, right=(1, 0, 0),
               down=(0, -1, 0), drip=0.7, slant=0.18, seed=0, **kw):
    strokes = BP.text_strokes(text, origin, right, down, height, slant=slant, seed=seed or _h(text, origin))
    bm.wd(cubes, faces, "nrb_spray", strokes=strokes, colour=colour, width=width, drip=drip, **kw)


def nails_on(bm, cubes, faces, pts, r=0.42, kind="nail", rust=0.7, colour=(70, 66, 62)):
    bm.wd(cubes, faces, "nrb_nails", pts=[tuple(p) for p in pts], r=r, kind=kind, rust=rust, colour=colour)


# ===========================================================================
#  ブロックごとの作り込み
# ===========================================================================
def build_barricade(bm: BlockModel, e):
    # 裏の縦の添え木
    braces = [bm.box((x, 8, 1.6), (3, 16, 1.2), "wood_dark") for x in (-6, 6)]
    bm.dec(braces, "north", "grime", amount=0.5)
    top = bm.box((0, 13, -0.6), (18, 4, 1.4), "wood_old", rot=(0, 0, 4))
    mid = bm.box((0.5, 8, 0.6), (17, 3.6, 1.4), "plywood", rot=(0, 0, -9))
    low = bm.box((0, 3, -0.6), (18, 4, 1.4), "wood_old", rot=(0, 0, -3))
    # 割れて垂れた短い板と、板の端のささくれ
    hang = bm.box((-4.2, 6.3, -1.9), (7.5, 2.6, 1.0), bm.use("wood_old", base="#6a5038"), rot=(0, 0, -31))
    spl1 = bm.box((9.4, 13.9, -0.6), (1.6, 1.6, 1.2), "wood_old", rot=(0, 0, 25))
    spl2 = bm.box((-9.2, 2.3, -0.6), (1.4, 1.8, 1.2), "wood_old", rot=(0, 0, -20))
    planks = [top, mid, low, hang]
    bm.dec(planks, "north", "grime", amount=0.35)
    # 釘（頭は立体で 5 本、周りの錆と小さな釘はテクスチャで）
    heads = [(-6, 13, -1.45), (6, 13, -1.45), (-6, 3, -1.45), (6, 3, -1.45), (0, 8, -0.2), (-6.6, 6.9, -2.45)]
    for p in heads:
        bm.box(p, (0.8, 0.8, 0.6), "steel_rusty")
    nails_on(bm, [top, low, mid, hang], "north",
             heads + [(-7.6, 13.3, -1.3), (7.4, 12.6, -1.3), (-7.4, 2.8, -1.3), (7.6, 3.4, -1.3), (3, 8.4, -0.1)],
             r=0.3, rust=0.9)
    # 赤いスプレー「KEEP OUT」・血の手形・引っかき傷
    spray_text(bm, [top, mid], "north", "KEEP OUT", (-7.4, 14.7, -1.3), 3.0, seed=11)
    bm.dec(low, "north", "handprint", at=(0.62, 0.55), size=0.42)
    bm.dec(mid, "north", "nrb_claw", at=(0.32, 0.5), size=0.5, angle=78, n=4, blood=0.7)
    bm.dec(low, "north", "nrb_claw", at=(0.25, 0.4), size=0.6, angle=72, n=3, blood=0.5)
    bm.dec(low, "north", "drips", start=0.05, amount=0.4)


def build_metal_barricade(bm: BlockModel, e):
    sheet = bm.box((0, 8, 0), (16, 16, 1.0), "steel_rusty", uv=1.0)
    bm.dec(sheet, ["north", "south"], "nrb_corrugate", period=2.0, depth=1.2)
    bm.dec(sheet, "north", "rust_streaks", amount=0.9)
    # 波の山（立体）
    for i in range(8):
        x = -7 + i * 2
        rib = bm.box((x, 8, -0.7), (0.9, 16, 0.4), "steel_rusty")
        bm.dec(rib, "north", "rust_streaks", amount=0.6)
    # 山形鋼の枠
    fr = [bm.box((0, y, -1.2), (17, 1.6, 1.6), "steel_dark") for y in (2, 14)]
    fr += [bm.box((x, 8, -1.2), (1.6, 16, 1.6), "steel_dark") for x in (-7.2, 7.2)]
    bm.dec(fr, "north", "grime", amount=0.5)
    # ボルト
    for x in (-7.2, 7.2):
        for y in (2, 14):
            bm.box((x, y, -2.2), (1, 1, 0.6), "steel_worn")
    # 当て板（リベット留め）と内側から叩かれた凹み
    patch = bm.box((3.4, 5.2, -1.15), (6.5, 5, 0.5), bm.use("steel_painted", base="#5c6a5a", rust=0.7))
    bm.dec(patch, "north", "nrb_rivets", step=1.6, inset=0.5, r=0.25)
    bm.dec(patch, "north", "bullet_hole", at=(0.3, 0.4), size=0.08)
    bm.dec(sheet, "north", "bullet_hole", at=(0.22, 0.3), size=0.035)
    bm.dec(sheet, "north", "bullet_hole", at=(0.71, 0.2), size=0.03)
    # 生存者の UV の印
    bm.dec(sheet, "north", "nrb_uv_mark", at=(0.62, 0.42), size=0.36)
    bm.wd(fr[0:1] + [sheet], "north", "nrb_spray",
          strokes=BP.text_strokes("NO", (-6.3, 13.0, -0.5), (1, 0, 0), (0, -1, 0), 2.6, seed=5),
          colour=(226, 224, 214), width=0.5, drip=0.5)


def build_sandbags(bm: BlockModel, e):
    burlap = "burlap"
    dark = bm.use("burlap", base="#8e7c58", dirt=0.7)
    rows = [((-4, 2, 0), (8.4, 4, 9), burlap), ((4, 2, 0), (8.4, 4, 9), dark),
            ((0, 6, 0.2), (8.4, 4, 8.5), burlap), ((-8.2, 6, 0.2), (8.4, 4, 8.5), dark),
            ((8.2, 6, 0.2), (8.4, 4, 8.5), burlap), ((-4, 10, 0), (8.4, 4, 8), dark), ((4, 10, 0), (8.4, 4, 8), burlap)]
    for i, (at, size, st) in enumerate(rows):
        x, y, z = at
        sx, sy, sz = size
        # ふくらんだ袋: 芯 + 少し細い上下のふくらみ
        core = bm.box((x, y - 0.1, z), (sx - 0.4, sy - 0.6, sz), st, rot=(0, (i % 3 - 1) * 2.5, 0))
        bulge = bm.box((x, y + 0.15, z), (sx - 1.6, sy - 0.1, sz - 1.2), st, rot=(0, (i % 3 - 1) * 2.5, 0))
        bm.dec([core], ["north", "south"], "nrb_stitch_ends")
        bm.dec([core, bulge], "up", "grime", amount=0.3)
    # 破れて漏れた砂
    leak = bm.box((5, 0.5, -5.2), (3.4, 1.0, 2.6), bm.use("concrete", base="#b09a70", cracks=0.0))
    bm.box((6.4, 0.25, -6.4), (2.0, 0.5, 1.6), bm.use("concrete", base="#a89268", cracks=0.0))
    # 白いステンシル番号
    first = bm.model.bones[0].cubes[0]
    bm.dec(first, "north", "text", text="NR-07", colour=(214, 212, 200), at=(0.5, 0.55), wear=0.5)


def build_traffic_cone(bm: BlockModel, e):
    up = bm.bone("upright", vis={"nr:fallen": [0]})
    fallen = bm.bone("fallen", pivot=(0, 0, 0), rotation=None, vis={"nr:fallen": [1]})
    cubes = []
    base = bm.box((0, 0.6, 0), (11, 1.2, 11), "rubber_black", bone=up)
    bm.dec(base, "up", "grime", amount=0.6)
    cubes.append(base)
    orange = "plastic_orange"
    white = bm.use("plastic_white", base="#e6e4dc", dirt=0.4)
    tiers = [(1.2, 2.0, 7.4, orange), (3.2, 1.6, 6.6, orange), (4.8, 1.0, 6.0, white), (5.8, 1.0, 5.6, white),
             (6.8, 1.4, 5.0, orange), (8.2, 0.8, 4.4, white), (9.0, 0.8, 4.0, white), (9.8, 1.2, 3.4, orange),
             (11.0, 1.2, 2.6, orange), (12.0, 0.6, 1.8, orange)]
    for y0, h, w, st in tiers:
        c = bm.box((0, y0 + h / 2, 0), (w, h, w), st, bone=up)
        bm.dec(c, "sides", "grime", amount=0.45)
        cubes.append(c)
    # 倒れた姿: 先端を -Z に向けて寝かせ、台の角と先端で接地（約 72 度）
    bm.bones[fallen].rotation = [-72.0, 25.0, 0.0]
    bm.bones[fallen].pivot = [0.0, 5.5, 0.0]
    bm.clone(cubes, fallen)


def build_road_barrier(bm: BlockModel, e):
    conc = bm.use("concrete", base="#a2a29a", dirt=0.5)
    base = bm.box((0, 1.6, 0), (16, 3.2, 10), conc)
    core = bm.box((0, 8.6, 0), (16, 10.8, 4.4), conc)
    # 斜面（ジャージー型の膨らみ）
    s1 = bm.box((0, 4.6, -2.95), (16, 4.4, 2.6), conc, rot=(-24, 0, 0))
    s2 = bm.box((0, 4.6, 2.95), (16, 4.4, 2.6), conc, rot=(24, 0, 0))
    top = bm.box((0, 14.25, 0), (16, 0.5, 4.0), bm.use("concrete", base="#8e8e88", cracks=0.8))
    bm.dec([base, core, s1, s2], "sides", "grime", amount=0.55)
    bm.dec([core], "east", "cracks", amount=0.8)
    # 赤白の斜めの反射材（前）
    bm.dec(core, "north", "stripe", count=5, orient="d", width=0.07, gap=0.06, colour=(178, 30, 26),
           reflective=True, offset=0.62)
    bm.dec(core, "north", "nrb_label", box=(0.0, 0.18, 1.0, 0.3), fill=(220, 214, 200), wear=0.5)
    # フォークの穴（黒い溝）
    for x in (-4, 4):
        bm.box((x, 0.8, 0), (3.0, 1.6, 10.2), bm.use("concrete_dark", base="#2c2c2c"))
    # 裏の落書き
    spray_text(bm, [core, s2], "south", "RUN", (5.4, 13.0, 2.25), 3.2, colour=(40, 80, 170), right=(-1, 0, 0),
               seed=21)
    bm.box((-6.5, 14.7, -1.0), (2.2, 0.6, 1.5), bm.use("concrete", base="#7c7c76"), rot=(0, 20, 6))


def build_street_lamp_base(bm: BlockModel, e):
    iron = bm.use("paint_green", base="#24342a", wear=0.5, rust=0.6)
    plinth = bm.oct((0, 1.5, 0), (10, 3, 10), iron)
    lip = bm.oct((0, 3.4, 0), (8.6, 0.8, 8.6), iron)
    flare = bm.oct((0, 6.0, 0), (6.6, 4.4, 6.6), iron)
    ring = bm.oct((0, 8.6, 0), (5.6, 0.8, 5.6), iron)
    shaft = bm.oct((0, 12.5, 0), (4.4, 7.0, 4.4), iron)
    for c in plinth + flare + shaft:
        bm.dec(c, "sides", "rust_streaks", amount=0.7)
        bm.dec(c, "sides", "grime", amount=0.5)
    panel = bm.box((0, 6.0, -3.45), (2.6, 3.0, 0.4), bm.use("steel_dark"), rot=(0, 0, 4))
    bm.dec(panel, "north", "nrb_rivets", step=1.2, inset=0.35, r=0.2)
    poster = bm.box((0, 12.4, -2.32), (3.4, 4.4, 0.2), "paper")
    bm.dec(poster, "north", "nrb_poster")
    for x, z in ((-3.6, -3.6), (3.6, -3.6), (-3.6, 3.6), (3.6, 3.6)):
        bm.box((x, 3.25, z), (1.0, 0.9, 1.0), "steel_rusty")


def build_street_lamp_pole(bm: BlockModel, e):
    paint = bm.use("paint_green", base="#24342a", wear=0.45, rust=0.6)
    pole = bm.oct((0, 8, 0), (3.4, 16, 3.4), paint)
    for c in pole:
        bm.dec(c, "sides", "rust_streaks", amount=0.8)
    collar = bm.oct((0, 15.5, 0), (4.0, 1.0, 4.0), bm.use("iron_cast"))
    v1 = bm.bone("stickers", vis={VARIANT: [1]})
    sleeve = bm.box((0, 6.2, 0), (3.7, 5.0, 3.7), "paper", bone=v1)
    bm.dec(sleeve, "north", "nrb_poster", title="HELP")
    bm.dec(sleeve, "west", "nrb_poster", title="LOST")
    bm.dec(sleeve, "east", "nrb_label", box=(0.05, 0.1, 0.95, 0.5), fill=(200, 60, 40), text="UV|SAFE")
    tape = bm.box((0, 9.0, 0), (3.8, 0.5, 3.8), "tape_grey", bone=v1)


def build_street_lamp_head(bm: BlockModel, e):
    paint = bm.use("paint_green", base="#24342a", wear=0.45, rust=0.55)
    pole = bm.oct((0, 5, 0), (3.4, 10, 3.4), paint)
    cap = bm.oct((0, 10.4, 0), (4.0, 0.8, 4.0), paint)
    arm = bm.box((0, 11.4, -8.0), (2.0, 2.0, 17.0), paint, rot=(-6, 0, 0), pivot=(0, 11.4, 0))
    brace = bm.box((0, 8.4, -3.8), (1.0, 1.0, 9.0), paint, rot=(-38, 0, 0))
    curl = bm.box((0, 9.8, -7.6), (0.8, 2.4, 0.8), paint)
    # コブラ型の笠
    hous = bm.box((0, 12.9, -18.0), (6.0, 2.4, 9.0), bm.use("paint_green", base="#2a3a30", wear=0.5))
    hood = bm.box((0, 14.3, -17.6), (4.8, 0.8, 7.0), bm.use("paint_green", base="#2a3a30", wear=0.5))
    rear = bm.box((0, 12.6, -12.6), (3.6, 2.2, 2.4), paint)
    bm.dec([hous, hood], "sides", "rust_streaks", amount=0.6)
    on = bm.bone("lens_on", vis={"nr:lit": [1]})
    off = bm.bone("lens_off", vis={"nr:lit": [0]})
    bm.box((0, 11.45, -18.0), (5.0, 0.5, 7.4), "emissive_white", bone=on)
    lens_off = bm.box((0, 11.45, -18.0), (5.0, 0.5, 7.4), bm.use("glass_clear", base="#8a8e86", dirt=0.7), bone=off)
    bm.dec(lens_off, "down", "cracks", amount=0.8)
    # 笠の上の鳥の巣
    nest = bm.box((0, 15.2, -16.2), (3.0, 1.2, 3.0), "rope")
    twig1 = bm.box((0.4, 15.6, -16.0), (4.0, 0.4, 0.4), "wood_dark", rot=(0, 35, 8))
    twig2 = bm.box((-0.4, 15.5, -16.4), (0.4, 0.4, 3.8), "wood_dark", rot=(10, 20, 0))


def build_uv_lamp(bm: BlockModel, e):
    base = bm.oct((0, 1.0, 0), (8, 2, 8), "plastic_black")
    bm.dec(base, "up", "grime", amount=0.6)
    batt = bm.box((0, 4.0, 0.4), (5, 4, 4), "plastic_yellow")
    bm.dec(batt, "north", "nrb_label", box=(0.1, 0.25, 0.9, 0.75), fill=(30, 30, 30), ink=(220, 200, 60),
           text="12V", wear=0.4)
    bm.dec(batt, "west", "nrb_label", box=(0.15, 0.2, 0.85, 0.8), fill=(228, 196, 40), symbol="bolt",
           sym_box=(0.3, 0.25, 0.7, 0.75), border=1)
    for x, st in ((-1.3, "plastic_red"), (1.3, "plastic_black")):
        bm.box((x, 6.3, 0.4), (0.9, 0.6, 0.9), st)
    cable = bm.box((-0.9, 7.0, 1.6), (0.5, 3.0, 0.5), "rubber_black", rot=(15, 0, 0))
    post = bm.box((0, 10.0, 0), (2, 8, 2), "aluminium")
    bm.dec(post, "sides", "grime", amount=0.35)
    collar = bm.oct((0, 13.6, 0), (3.6, 0.8, 3.6), "plastic_black")
    on = bm.bone("tube_on", vis={"nr:powered": [1]})
    off = bm.bone("tube_off", vis={"nr:powered": [0]})
    bm.box((0, 19.0, 0), (2.4, 10, 2.4), "emissive_uv", bone=on)
    bm.box((0, 19.0, 0), (2.4, 10, 2.4), bm.use("glass_clear", base="#9c8cb4", dirt=0.5), bone=off)
    cage = bm.box((0, 19.0, 0), (4.0, 11, 4.0), "chainlink")
    bm.dec(cage, "sides", "nrb_chainlink", pitch=1.0, wire=0.24, edge_rows=0.5)
    bm.dec(cage, ["up", "down"], "nrb_clear")
    for y in (14.0, 24.0):
        bm.oct((0, y, 0), (4.4, 0.6, 4.4), "aluminium")
    cap = bm.oct((0, 25.0, 0), (4.4, 1.2, 4.4), "plastic_black")
    hook = bm.box((0, 26.1, 0), (0.5, 1.0, 1.6), "steel_worn")


# ---------------------------------------------------------------------------
#  何も専用の作りが無いブロック（カタログの部品をそのまま箱に）
# ---------------------------------------------------------------------------
_SURF_FALLBACK = {"fuel": "fuel"}


def build_generic(bm: BlockModel, e):
    for p in e["model"]:
        st = p["mat"] if p["mat"] in BP.STYLES else "concrete"
        centres = [p["at"]] + list(p.get("rep", []))
        for c in centres:
            bm.box(c, p["size"], st, rot=p.get("rot"))


BUILDERS = {
    "barricade": build_barricade,
    "metal_barricade": build_metal_barricade,
    "sandbags": build_sandbags,
    "traffic_cone": build_traffic_cone,
    "road_barrier": build_road_barrier,
    "street_lamp_base": build_street_lamp_base,
    "street_lamp_pole": build_street_lamp_pole,
    "street_lamp_head": build_street_lamp_head,
    "uv_lamp": build_uv_lamp,
}


def build(key: str, entry: dict, seed: int = 0) -> BlockModel:
    bm = BlockModel(key, seed)
    fn = BUILDERS.get(key, build_generic)
    fn(bm, entry)
    if fn is build_generic:
        bm.notes.append("generic")
    return bm
