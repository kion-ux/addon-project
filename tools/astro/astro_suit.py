# -*- coding: utf-8 -*-
"""アストロ・ナノギア — スーツの骨格・部位ボーン・左右の鏡映・被覆検査。

スーツは頭スロットのアタッチャブルとして着る全身モデル。トップレベルのボーンをプレイヤーと同名・同ピボットに
すると、統合版はそのボーンをプレイヤーの同名ボーンに重ねて動かす（kaiju8 の no8_form と同じ仕組み）。

    body (0,24,0)  head (0,24,0)  rightArm (-5,22,0)  leftArm (5,22,0)
    rightLeg (-1.9,12,0)  leftLeg (1.9,12,0)

キューブは必ず「部位ボーン」（`<群>_<名前>`）に入れる。群は組み上がりの順番（astro_data.ASSEMBLE_ORDER）:
    inner boots legs waist torso back arms shoulders helmet visor extra
動かす部品はさらに子ボーン `fx_thrust_*`（空中で伸びる炎）/ `fx_glow_*`（脈動・バイザーの閃光）/
`fx_spin_*`（回転体）に分ける。

左右: 右側（-X）だけ作り、名前の末尾を `_r` にしておくと、Suit.mirror_all() が左（`_l`）を作る
（build() が自動で呼ぶ）。片側だけの部品（ルナ・ビット等）は `_r` を付けない。

使い方（planets/<key>/suit.py）:
    from astro_suit import Suit, R, L, ARM_X, LEG_X
    from astro_common import cbox, rbox, plate, beam, octa, bevel, ring
    def build_suit(s: Suit):
        s.inner_suit()                                        # 肌を確実に覆う黒いインナー
        chest = s.part("torso", "chest", "body")              # → ボーン torso_chest
        rbox(chest, (0, 20, -3.2), (8.6, 6, 1.2), "plate", rot=(8, 0, 0))
        g = s.part("arms", "gauntlet_r", "rightArm")          # 右だけ書く → arms_gauntlet_l が自動で出来る
        ...
"""
from __future__ import annotations

import copy
import importlib
import os
import sys
from typing import Dict, Iterable, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import astro_common as AC  # noqa: E402
from astro_common import NS, Bone, Cube, Model, cbox, cube_matrix  # noqa: E402
from astro_data import ASSEMBLE_ORDER, PLANETS  # noqa: E402
from hd_space import bone_local, mat4, rot  # noqa: E402

# ---------------------------------------------------------------------------
#  骨格と肌
# ---------------------------------------------------------------------------
TOP = {
    "body": (0.0, 24.0, 0.0), "head": (0.0, 24.0, 0.0),
    "rightArm": (-5.0, 22.0, 0.0), "leftArm": (5.0, 22.0, 0.0),
    "rightLeg": (-1.9, 12.0, 0.0), "leftLeg": (1.9, 12.0, 0.0),
}
TOP_NAMES = tuple(TOP)
SKIN = {
    "head": ((-4, 24, -4), (8, 8, 8)),
    "body": ((-4, 12, -2), (8, 12, 4)),
    "rightArm": ((-8, 12, -2), (4, 12, 4)),
    "leftArm": ((4, 12, -2), (4, 12, 4)),
    "rightLeg": ((-3.9, 0, -2), (4, 12, 4)),
    "leftLeg": ((-0.1, 0, -2), (4, 12, 4)),
}
LAYER = {"head": 0.5, "body": 0.25, "rightArm": 0.25, "leftArm": 0.25,
         "rightLeg": 0.25, "leftLeg": 0.25}
MIRROR_TOP = {"rightArm": "leftArm", "leftArm": "rightArm", "rightLeg": "leftLeg",
              "leftLeg": "rightLeg", "body": "body", "head": "head"}

GROUPS = ("inner", "boots", "legs", "waist", "torso", "back", "arms", "shoulders",
          "helmet", "visor", "extra")
FX_KINDS = ("thrust", "glow", "spin")

# 右側の基準（左は X を反転）
R, L = -1, 1                 # 右 = -X
ARM_X = -6.0                 # 右腕の中心の X
LEG_X = -1.9                 # 右脚の中心の X
HAND_Y = 13.2                # 拳の中心の高さ（腕を下ろした時）

# 部位ボーンの既定の pivot（右側。「生えてくる根元」）。None は親の pivot
DEFAULT_PIVOT = {
    ("boots", "leg"): (LEG_X, 2.5, 0.0),
    ("legs", "leg"): (LEG_X, 7.0, -0.5),
    ("waist", "body"): (0.0, 12.5, 0.0),
    ("torso", "body"): (0.0, 18.0, 0.0),
    ("back", "body"): (0.0, 19.0, 2.5),
    ("arms", "arm"): (ARM_X, 16.0, 0.0),
    ("shoulders", "arm"): (-5.5, 23.0, 0.0),
    ("helmet", "head"): (0.0, 28.0, 0.0),
    ("visor", "head"): (0.0, 28.0, -4.5),
}

# 被覆検査で既定で見ない所（いつも他の部位の中に隠れる面）
DEFAULT_ALLOW = [
    ("rightLeg", "up"), ("leftLeg", "up"),       # 脚の上面は胴の中
]


def group_of(name: str) -> Optional[str]:
    """部位ボーン名の群（`torso_chest` → `torso`）。fx_* やトップレベルは None。"""
    head = name.split("_", 1)[0]
    return head if head in GROUPS and "_" in name else None


def is_fx(name: str) -> bool:
    return any(name.startswith(f"fx_{k}_") for k in FX_KINDS)


def _side_top(top: str) -> str:
    if top in ("rightArm", "leftArm"):
        return "arm"
    if top in ("rightLeg", "leftLeg"):
        return "leg"
    return top


# ===========================================================================
#  Suit
# ===========================================================================
class Suit:
    """スーツの組み立て台。`s.m` が mcmodel.Model（書き出しはこれ）。"""

    def __init__(self, key: str, uv_scale: float = 4):
        self.key = key
        self.m = Model(f"geometry.{NS}.suit_{key}", uv_scale=uv_scale,
                       visible_bounds=(4, 4), vb_offset=(0, 1.2, 0), max_atlas=(1024, 1024))
        self.top: Dict[str, Bone] = {n: self.m.bone(n, p) for n, p in TOP.items()}
        self.mirror_styles: Dict[str, str] = {}
        self.allow: List = list(DEFAULT_ALLOW)

    # ---- ボーン ---------------------------------------------------------
    def bone(self, name: str) -> Bone:
        for b in self.m.bones:
            if b.name == name:
                return b
        raise KeyError(name)

    def has(self, name: str) -> bool:
        return any(b.name == name for b in self.m.bones)

    def _top_of(self, name: str) -> str:
        b = self.bone(name)
        while b.parent:
            b = self.bone(b.parent)
        return b.name

    def part(self, group: str, name: str, parent="body", pivot=None, rotation=None) -> Bone:
        """部位ボーン `<group>_<name>` を作る。parent はトップレベル名・部位ボーン名・Bone。
        pivot 省略時は群と親から既定（DEFAULT_PIVOT。左側の親なら X を反転）。"""
        if group not in GROUPS:
            raise ValueError(f"unknown group '{group}' (use one of {GROUPS})")
        pname = parent.name if isinstance(parent, Bone) else parent
        full = f"{group}_{name}"
        if self.has(full):
            raise ValueError(f"duplicate bone '{full}'")
        if pivot is None:
            top = self._top_of(pname)
            pv = DEFAULT_PIVOT.get((group, _side_top(top)))
            if pv is None:
                pv = self.bone(pname).pivot
            elif top in ("leftArm", "leftLeg"):
                pv = (-pv[0], pv[1], pv[2])
            pivot = pv
        return self.m.bone(full, pivot, parent=pname, rotation=rotation)

    def fx(self, kind: str, name: str, parent, pivot=None, rotation=None) -> Bone:
        """アニメで動かす子ボーン `fx_<kind>_<name>`（kind: thrust / glow / spin）。
        parent は部位ボーン（トップレベルの直下には置けない）。"""
        if kind not in FX_KINDS:
            raise ValueError(f"fx kind must be one of {FX_KINDS}")
        pname = parent.name if isinstance(parent, Bone) else parent
        if pname in TOP:
            raise ValueError("fx bones go under a part bone, not a top-level bone")
        full = f"fx_{kind}_{name}"
        if self.has(full):
            raise ValueError(f"duplicate bone '{full}'")
        return self.m.bone(full, pivot or self.bone(pname).pivot, parent=pname,
                           rotation=rotation)

    # ---- インナー（肌を確実に覆う） --------------------------------------
    def inner_suit(self, style: str = "inner", gap: float = 0.45, hood: bool = True,
                   uv_scale: Optional[float] = None, head_style: Optional[str] = None):
        """肌の 6 部位に、外側レイヤー + gap の殻を張る（群 inner、最初に現れるボディスーツ）。
        左右の脚は正面の面が同じ平面に並ばないよう、左だけ前後を 0.05 厚くする（Z ファイト避け）。
        hood=False なら頭は張らない（兜で完全に覆う場合）。戻り値: {部位: Bone}"""
        out = {}
        for top, (o, sz) in SKIN.items():
            if top == "head" and not hood:
                continue
            inf = LAYER[top] + gap
            if top == "head":
                inf = LAYER[top] + max(0.12, gap * 0.5)
            side = {"rightArm": "arm_r", "leftArm": "arm_l", "rightLeg": "leg_r",
                    "leftLeg": "leg_l"}.get(top, top)
            b = self.part("inner", side, top, pivot=TOP[top])
            c = [o[i] + sz[i] / 2 for i in range(3)]
            size = [sz[i] + 2 * inf for i in range(3)]
            if top in ("leftLeg", "leftArm"):
                size[2] += 0.1
            kw = {"uv_scale": uv_scale} if uv_scale else {}
            cbox(b, c, size, head_style if (top == "head" and head_style) else style, **kw)
            out[top] = b
        return out

    # ---- 左右の鏡映 -----------------------------------------------------
    def mirror_all(self, style_map: Optional[Dict[str, str]] = None) -> List[str]:
        """`_r` で終わる部位ボーンの部分木を左（`_l`）へ写す。既に `_l` があるものは飛ばす。
        X を反転し、回転は (rx, -ry, -rz)、デカールの east/west を入れ替える。"""
        smap = dict(self.mirror_styles, **(style_map or {}))
        names = {b.name for b in self.m.bones}
        made = []
        roots = [b for b in self.m.bones
                 if b.name.endswith("_r") and not (b.parent or "").endswith("_r")
                 and b.name[:-2] + "_l" not in names]
        for root in roots:
            sub = self._subtree(root.name)
            for b in sub:
                if not b.name.endswith("_r"):
                    raise ValueError(f"'{b.name}' is under mirrored '{root.name}' but does not "
                                     "end with _r (name every bone of a mirrored part *_r)")
            for b in sub:
                nb = Bone(b.name[:-2] + "_l", (-b.pivot[0], b.pivot[1], b.pivot[2]),
                          parent=(MIRROR_TOP.get(b.parent, b.parent[:-2] + "_l"
                                                 if b.parent.endswith("_r") else b.parent)),
                          rotation=([b.rotation[0], -b.rotation[1], -b.rotation[2]]
                                    if b.rotation else None))
                for c in b.cubes:
                    nb.cubes.append(mirror_cube(c, smap))
                self.m.bones.append(nb)
                made.append(nb.name)
        return made

    def _subtree(self, name: str) -> List[Bone]:
        out = []
        todo = [name]
        while todo:
            n = todo.pop(0)
            b = self.bone(n)
            out.append(b)
            todo.extend(c.name for c in self.m.bones if c.parent == n)
        return out

    # ---- 情報 -----------------------------------------------------------
    def parts(self) -> List[Bone]:
        return [b for b in self.m.bones if b.name not in TOP]

    def stats(self) -> str:
        return self.m.stats()


def mirror_cube(c: Cube, smap=None) -> Cube:
    o = list(c.origin)
    s = list(c.size)
    o[0] = -(o[0] + s[0])
    piv = [-c.pivot[0], c.pivot[1], c.pivot[2]] if c.pivot else None
    rot_ = [c.rotation[0], -c.rotation[1], -c.rotation[2]] if c.rotation else None
    dec = {}
    for f, d in (c.decals or {}).items():
        dec[{"east": "west", "west": "east"}.get(f, f)] = copy.deepcopy(d)
    style = (smap or {}).get(c.style, c.style)
    n = Cube(o, s, style, inflate=c.inflate, pivot=piv, rotation=rot_, decals=dec,
             uv_scale=c.uv_scale)
    return n


# ===========================================================================
#  惑星パッケージの読み込みと組み立て
# ===========================================================================
def available(keys: Optional[Iterable[str]] = None) -> List[str]:
    """planets/<key>/suit.py がある惑星（PLANETS の順）。keys で絞れる。"""
    out = []
    for k in PLANETS:
        if keys and k not in keys:
            continue
        if os.path.exists(os.path.join(AC.PLANETS_DIR, k, "suit.py")):
            out.append(k)
    return out


def load_module(key: str):
    if AC.HERE not in sys.path:
        sys.path.insert(0, AC.HERE)
    name = f"planets.{key}.suit"
    if name in sys.modules:
        return importlib.reload(sys.modules[name])
    return importlib.import_module(name)


def build(key: str, module=None) -> Suit:
    """惑星 key のスーツを組み立てる（未パック）。suit.py の build_suit(s) を呼び、左右を写す。"""
    mod = module or load_module(key)
    s = Suit(key, uv_scale=getattr(mod, "UV_SCALE", 4))
    s.mirror_styles.update(getattr(mod, "MIRROR_STYLES", {}))
    s.allow.extend(getattr(mod, "COVER_ALLOW", []))
    mod.build_suit(s)
    if getattr(mod, "MIRROR", True):
        s.mirror_all()
    s.module = mod
    return s


def pack(s: Suit, base: float = 4.0, ks=(2.0, 1.75, 1.5, 1.375, 1.25, 1.125, 1.0, 0.875, 0.75,
                                           0.625, 0.5)) -> float:
    """テクセル密度の探索: 倍率 k を大きい方から試し、1024x1024 に収まる最大を選ぶ
    （hyperdim の build_model と同じ）。キューブの uv_scale は「基準 4 に対する相対」で効く。"""
    m = s.m
    base0 = {id(c): c.uv_scale for c in m.all_cubes()}
    for k in ks:
        for c in m.all_cubes():
            s0 = base0[id(c)] or base
            c.uv_scale = max(0.5, s0 * k)
            c._scale = c.uv_scale
            c.uv = None
        m.uv_scale = base * k
        try:
            m.pack()
            m.texel_k = k
            return k
        except ValueError:
            continue
    raise ValueError(f"suit_{s.key}: does not fit in 1024x1024")


# ===========================================================================
#  変換（レンダラ・検査が使う）
# ===========================================================================
def geo_of(s_or_geo) -> dict:
    """Suit / Model / geometry dict のどれでも geometry dict（description + bones）に。"""
    if isinstance(s_or_geo, Suit):
        m = s_or_geo.m
    elif isinstance(s_or_geo, Model):
        m = s_or_geo
    else:
        return s_or_geo
    if not m.tex_w:
        # UV 無しでも形だけ欲しい時: 仮の UV を振る
        bones = []
        for b in m.bones:
            d = {"name": b.name, "pivot": b.pivot}
            if b.parent:
                d["parent"] = b.parent
            if b.rotation:
                d["rotation"] = b.rotation
            cubes = []
            for c in b.cubes:
                cd = {"origin": c.origin, "size": c.size, "style": c.style}
                if c.inflate:
                    cd["inflate"] = c.inflate
                if c.rotation:
                    cd["rotation"] = c.rotation
                    cd["pivot"] = c.pivot or [c.origin[i] + c.size[i] / 2 for i in range(3)]
                cubes.append(cd)
            if cubes:
                d["cubes"] = cubes
            bones.append(d)
        return {"description": {"identifier": m.identifier}, "bones": bones}
    return m.to_json()


def suit_world(geo: dict, player_W: Optional[dict] = None, anim: Optional[dict] = None) -> dict:
    """スーツの各ボーンのワールド行列。トップレベル（プレイヤーと同名）は player_W[名前]
    （姿勢を付けたプレイヤーの骨格。None なら立ち姿 = 各 pivot の恒等変換）に重ねる。
    anim: bone -> {"rotation","position","scale"}（アニメの値を足す）。"""
    anim = anim or {}
    bones = {b["name"]: b for b in geo["bones"]}
    out = {}

    def wm(name):
        if name in out:
            return out[name]
        b = bones[name]
        a = anim.get(name, {})
        if name in TOP and not b.get("parent"):
            base = player_W[name] if player_W is not None and name in player_W else np.eye(4)
            L_ = bone_local(b.get("pivot", (0, 0, 0)),
                            np.add(b.get("rotation", (0, 0, 0)), a.get("rotation", (0, 0, 0))),
                            a.get("position", (0, 0, 0)), a.get("scale", (1, 1, 1)))
            M = base @ L_
        else:
            L_ = bone_local(b.get("pivot", (0, 0, 0)),
                            np.add(b.get("rotation", (0, 0, 0)), a.get("rotation", (0, 0, 0))),
                            a.get("position", (0, 0, 0)), a.get("scale", (1, 1, 1)))
            par = b.get("parent")
            M = (wm(par) if par else np.eye(4)) @ L_
        out[name] = M
        return M

    for n in bones:
        wm(n)
    return out


def top_of(geo: dict, name: str) -> str:
    bones = {b["name"]: b for b in geo["bones"]}
    b = bones[name]
    while b.get("parent"):
        b = bones[b["parent"]]
    return b["name"]


def ancestors(geo: dict, name: str) -> List[str]:
    bones = {b["name"]: b for b in geo["bones"]}
    out = []
    b = bones[name]
    while b.get("parent"):
        out.append(b["parent"])
        b = bones[b["parent"]]
    return out


# ===========================================================================
#  被覆検査
# ===========================================================================
FACE_N = {"up": (1, 1), "down": (1, -1), "east": (0, 1), "west": (0, -1),
          "south": (2, 1), "north": (2, -1)}   # 軸, 向き（east = +X、south = +Z）


def skin_samples(top: str, spacing: float = 0.5):
    """外側レイヤーの表面の標本点 (N,3) と、その点の面名のリスト。"""
    o, sz = SKIN[top]
    inf = LAYER[top]
    lo = np.array(o, float) - inf
    hi = np.array(o, float) + np.array(sz, float) + inf
    pts, faces = [], []
    for face, (ax, sgn) in FACE_N.items():
        a, b = [i for i in range(3) if i != ax]
        na = int(round((hi[a] - lo[a]) / spacing)) + 1
        nb = int(round((hi[b] - lo[b]) / spacing)) + 1
        for i in range(na):
            for j in range(nb):
                p = [0.0, 0.0, 0.0]
                p[ax] = hi[ax] if sgn > 0 else lo[ax]
                p[a] = lo[a] + (hi[a] - lo[a]) * i / (na - 1)
                p[b] = lo[b] + (hi[b] - lo[b]) * j / (nb - 1)
                pts.append(p)
                faces.append(face)
    return np.array(pts), faces


def coverage(s_or_geo, spacing: float = 0.5, margin: float = 0.05, allow=None,
             skip=lambda name: name.startswith("extra_") or is_fx(name)) -> dict:
    """肌の外側レイヤーの表面（帽子 0.5・他 0.25 膨らませた箱）を spacing 間隔で標本化し、
    各点が同じトップレベルボーン配下のどれかのキューブ（回転・inflate 込み、表面から margin 以上内側）
    に入っているかを調べる。extra_* と fx_*（動く部品）の配下は数えない。
    allow: [(トップ名, 面名)] または [(トップ名, (lo xyz), (hi xyz))] の除外リスト。
    戻り値: {トップ名: {"total", "uncovered", "pct", "points": 外に出た点 (M,3)}}"""
    geo = geo_of(s_or_geo)
    if allow is None:
        allow = list(s_or_geo.allow) if isinstance(s_or_geo, Suit) else list(DEFAULT_ALLOW)
    W = suit_world(geo)
    bones = {b["name"]: b for b in geo["bones"]}
    by_top: Dict[str, list] = {t: [] for t in TOP}
    for name, b in bones.items():
        if name in TOP:
            continue
        if any(skip(x) for x in [name] + ancestors(geo, name)):
            continue
        t = top_of(geo, name)
        for c in b.get("cubes", []):
            M = W[name] @ cube_matrix(c)
            inf = c.get("inflate", 0.0)
            lo = np.array(c["origin"], float) - inf + margin
            hi = np.array(c["origin"], float) + np.array(c["size"], float) + inf - margin
            if np.any(hi <= lo):
                continue
            by_top[t].append((np.linalg.inv(M), lo, hi))
    res = {}
    for top in TOP:
        pts, faces = skin_samples(top, spacing)
        keep = np.ones(len(pts), bool)
        for a in allow:
            if a[0] != top:
                continue
            if len(a) == 2:
                keep &= np.array([f != a[1] for f in faces])
            else:
                lo, hi = np.array(a[1], float), np.array(a[2], float)
                inside = np.all((pts >= lo) & (pts <= hi), axis=1)
                keep &= ~inside
        P = pts[keep]
        cov = np.zeros(len(P), bool)
        H = np.c_[P, np.ones(len(P))]
        for Minv, lo, hi in by_top[top]:
            q = (H @ Minv.T)[:, :3]
            cov |= np.all((q > lo) & (q < hi), axis=1)
        unc = P[~cov]
        res[top] = {"total": int(len(P)), "uncovered": int(len(unc)),
                    "pct": 100.0 * (1 - len(unc) / max(1, len(P))), "points": unc}
    return res


def coverage_report(res: dict, limit: float = 99.0) -> (bool, str):
    ok = True
    lines = []
    for top, r in res.items():
        flag = "ok" if r["pct"] >= limit else "NG"
        ok &= r["pct"] >= limit
        line = f"    {top:9s} {r['pct']:6.2f}%  ({r['uncovered']}/{r['total']} uncovered) {flag}"
        if r["uncovered"] and r["pct"] < limit:
            P = r["points"]
            lo, hi = P.min(axis=0), P.max(axis=0)
            line += f"  e.g. {np.round(P[0], 2).tolist()}  span {np.round(lo, 1).tolist()}..{np.round(hi, 1).tolist()}"
        lines.append(line)
    return ok, "\n".join(lines)


# ===========================================================================
#  命名の検査
# ===========================================================================
def naming_errors(s_or_geo) -> List[str]:
    geo = geo_of(s_or_geo)
    errs = []
    seen = set()
    for b in geo["bones"]:
        n = b["name"]
        if n in seen:
            errs.append(f"duplicate bone name '{n}'")
        seen.add(n)
        if n in TOP:
            if b.get("parent"):
                errs.append(f"top-level bone '{n}' must not have a parent")
            if list(b.get("pivot", [])) != list(TOP[n]):
                errs.append(f"top-level bone '{n}' pivot {b.get('pivot')} != {list(TOP[n])}")
            if b.get("cubes"):
                errs.append(f"top-level bone '{n}' has cubes (put them in a part bone)")
            if b.get("rotation"):
                errs.append(f"top-level bone '{n}' must not be rotated")
            continue
        if not b.get("parent"):
            errs.append(f"bone '{n}' has no parent (only the 6 skeleton bones are roots)")
        if is_fx(n):
            if b.get("parent") in TOP:
                errs.append(f"fx bone '{n}' must be under a part bone")
            continue
        if group_of(n) is None:
            errs.append(f"bone '{n}' is not '<group>_<name>' (groups: {', '.join(GROUPS)}) "
                        "nor fx_thrust_/fx_glow_/fx_spin_")
    for t in TOP:
        if t not in seen:
            errs.append(f"missing top-level bone '{t}'")
    return errs
