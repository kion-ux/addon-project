# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 腐敗・変異の部品集（nr_spec の MUTATION_VOCAB 全項目。DESIGN.md §3）。

nr_rig.ZombieRig の体（と nr_kit_outfit の服）に、腐敗・変異のキューブとテクスチャの変化を足す。

使い方（nr_kit.build_zombie から）::

    import nr_kit_mut as KM
    added = KM.mutate(rig, z, book)               # z["mutations"] を順に全部（book に追加）
    # 1 項目ずつなら
    ctx = KM.MutCtx(z, key, book)
    added = KM.MUTATIONS[key](rig, nr_spec.mutation_params((key, over)), ctx)

API: ``MUTATIONS = {鍵: fn}``、``fn(rig, params, ctx) -> その変異が足した stylebook の項目 {名前: スタイル}``
（nr_kit_outfit.OUTFITS と同じ形）。ctx は MutCtx（OutfitCtx と同じ rng / z / style() に、
予算の倍率 ``scale``（1 未満なら棘・腫瘍などの数を減らす）を足した物）。

約束:
* キューブはその変異が付く体の部位のボーンへ（DESIGN §3「部位が落ちたら一緒に落ちる」）。
  スタイル名は ``m_*``（服は ``o_*``）。素材は nr_paint の tumor / fungus / flesh / bone / gore_wet / glow
  ほか。光るもの（vocab の glow・ember・発光する血管・爆発結節）は glow 素材か、発光する
  デカール（veins emissive / glow_spot / char の embers）で entity_emissive_alpha の小さな α を出す。
* テクスチャだけの変異（dark_veins / burn_scars / skin_peeled / waterlogged / charred_crust の肌、
  veins_glowing の肌の血管、stitches）は、その部位の体の肌のキューブのスタイルを ``m_skin*`` の派生
  （nr_paint の skin のパラメータ veins / exposed / cracks / emissive_vein / spores / wet …）に替えるか、
  面にデカールを足す。部位ごとの肌の変更は rig._nr_mut_skin に溜まり、後から足す肌のキューブも同じ派生を使う。
* 子ボーン（MUT_BONE_PARENTS。名前ごとに親は一つ）: ``throat_sac``（neck）、``acid_sac_<where>``
  （neck / head / chest / torso）、``extra_head_<n>``（chest）、``lung_r`` / ``lung_l``（chest。叫ぶと膨らむ）、
  ``tendrils_<where>``（head / chest / forearm_*。揺らす根元）、``held_debris``（hand_r）、
  ``glow_<部位>_<印>``（光って明滅する部品。印は p<Hz×10>[f<段階>][a<段階>]）。
  明滅・段階の表示条件は model.nr_vis_terms = {ボーン: [Molang の項]} に入れ、nr_kit.visibility_rules が
  祖先の条件と AND する（part_visibility は子へ伝わらない）。
* 硬い変異（MUTATION_ARMOR: bone_plates / metal_fused）は、その部位が gore.armored にあれば
  nr_kit_outfit と同じ armor_*（段階 N は名前の _N）に、無ければ体の部位のボーンに置く。
* 服の上に出る物（腫瘍・棘・傷の穴・骨）は、服の一番外の殻（rig._nr_outfit_off）の外に置く
  （服を破って出てきた見た目）。肌の下の物（血管・縫い跡・肌の派生）は肌だけ。
* 当たり箱に数えない長い突起（触手・刺さった鉄筋・余分な腕・瓦礫）は cube.nr_nohit = True
  （nr_kit.hitboxes が除く）。粒子の出口はロケータ ``loc_spore_<n>`` / ``loc_acid_<n>``（model.nr_particles）。

自己テスト: ``python3 tools/nightrunner/nr_kit_mut.py`` … 全鍵の実装の確認、標準の体に 1 項目ずつ付けた
確認画像（build_preview/nightrunner/kit_mut_<n>.png、前と後ろ）、nr_kit.build_zombie で作った spec の 6 体、
キューブ数・ボーンの親の一貫性・gib の抽出・アトラスに収まるか・決定的かの検査。
"""
from __future__ import annotations

import copy
import math
import os
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import nr_common as C  # noqa: E402
import nr_kit_outfit as KO  # noqa: E402
import nr_paint as P  # noqa: E402
import nr_rig as R  # noqa: E402
import nr_spec as S  # noqa: E402

# ---------------------------------------------------------------------------
#  定数
# ---------------------------------------------------------------------------
# 体のボーン → 部位の箱（rig.segment の名前）
SEG = {"head": "cranium", "jaw": "jaw", "neck": "neck", "chest": "chest", "torso": "abdomen",
       "pelvis": "pelvis"}
for _s in "rl":
    SEG.update({f"arm_{_s}": f"upper_arm_{_s}", f"forearm_{_s}": f"forearm_{_s}", f"hand_{_s}": f"hand_{_s}",
                f"leg_{_s}": f"thigh_{_s}", f"shin_{_s}": f"shin_{_s}", f"foot_{_s}": f"foot_{_s}"})
BODY_BONES = tuple(SEG)

# 硬い変異の装甲の置き場所: ボーン → nr_kit_outfit.ARMOR_SLOTS の鍵 (部位, 場所)
ARMOR_AT = {"head": ("head", "head"), "chest": ("torso", "chest"), "torso": ("torso", "belly"),
            "pelvis": ("torso", "pelvis")}
for _s in "rl":
    ARMOR_AT.update({f"arm_{_s}": (f"arm_{_s}", "upper"), f"forearm_{_s}": (f"arm_{_s}", "fore"),
                     f"leg_{_s}": (f"leg_{_s}", "upper"), f"shin_{_s}": (f"leg_{_s}", "shin")})

# 変異の子ボーン（名前 → 親）。glow_<部位>_<印> は mut_bone_parent が名前から親を読む
MUT_BONE_PARENTS: Dict[str, str] = {
    "throat_sac": "neck", "acid_sac_neck": "neck", "acid_sac_cheeks": "head", "acid_sac_back": "chest",
    "acid_sac_belly": "torso", "lung_r": "chest", "lung_l": "chest",
    "tendrils_mouth": "head", "tendrils_back": "chest", "tendrils_arm_r": "forearm_r",
    "tendrils_arm_l": "forearm_l", "held_debris": "hand_r", "spawn_sac": "torso",
}
for _n in range(1, 4):
    MUT_BONE_PARENTS[f"extra_head_{_n}"] = "chest"
_GLOW_PARENTS = sorted(R.SKELETON_PARENT, key=len, reverse=True)

# 付ける順（小さいほど先）。肌の派生（テクスチャ）→ 顔 → 体の形 → 傷 → 生えてくる物
DEPTH = {
    "charred_crust": 0, "waterlogged": 0.1, "skin_peeled": 0.2, "dark_veins": 0.3, "burn_scars": 0.4,
    "stitches": 0.5, "veins_glowing": 0.6,
    "eyeless": 1, "missing_nose": 1.1, "split_face": 1.2, "missing_cheek_teeth": 1.3, "elongated_jaw": 1.4,
    "elongated_limbs": 2, "muscle_mass": 2.1, "bloated_belly": 2.2, "bone_plates": 2.3, "metal_fused": 2.4,
    "exposed_ribs": 3, "exposed_lungs": 3.1, "exposed_spine": 3.2, "exposed_skull": 3.3, "torn_throat": 3.4,
    "bite_wound": 3.5, "hanging_skin": 3.6, "missing_fingers": 3.7,
    "tumor_cluster": 4, "pustules": 4.1, "fungal_growth": 4.2, "spore_vents": 4.3, "acid_sacs": 4.4,
    "throat_sac": 4.5, "explosive_nodes": 4.6, "bone_spurs": 4.7, "spine_ridge": 4.8, "claws": 4.9,
    "bone_blades": 5, "fused_bodies": 5.1, "tendrils": 5.2, "surgical_ports": 5.3, "impaled": 5.4,
}

NRM = {"n": (0.0, 0.0, -1.0), "s": (0.0, 0.0, 1.0), "e": (-1.0, 0.0, 0.0), "w": (1.0, 0.0, 0.0),
       "u": (0.0, 1.0, 0.0), "d": (0.0, -1.0, 0.0)}
_FACE_OF = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
# 部位ごとに見えやすい面（デカールを置く面）。e = min-X（体の右）、w = max-X（体の左）
VIS_FACES = {
    "head": ("e", "w", "s"), "jaw": ("n", "e", "w"), "neck": ("n", "e", "w", "s"), "chest": ("n", "s", "e", "w"),
    "torso": ("n", "s", "e", "w"), "pelvis": ("n", "s"),
    "arm_r": ("e", "n", "s"), "arm_l": ("w", "n", "s"), "forearm_r": ("e", "n", "s"), "forearm_l": ("w", "n", "s"),
    "hand_r": ("e",), "hand_l": ("w",), "leg_r": ("n", "e", "s"), "leg_l": ("n", "w", "s"),
    "shin_r": ("n", "e"), "shin_l": ("n", "w"), "foot_r": ("u",), "foot_l": ("u",),
}
_NUMERIC_MAX = ("veins", "exposed", "cracks", "spores", "bruises", "lesions", "rot", "necrosis", "wet")


def _v(*a) -> np.ndarray:
    return np.array(a if len(a) == 3 else a[0], dtype=float)


def _unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else np.array([0.0, 1.0, 0.0])


def _lv(v, lo=1, hi=3) -> int:
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return lo


def _list(v) -> List[str]:
    if v is None:
        return []
    return [v] if isinstance(v, str) else list(v)


def mut_bone_parent(name: str) -> Optional[str]:
    """変異の子ボーンの決まった親（知らない名前は None）。"""
    if name in MUT_BONE_PARENTS:
        return MUT_BONE_PARENTS[name]
    if name.startswith("glow_"):
        for p in _GLOW_PARENTS:
            if name.startswith(f"glow_{p}_"):
                return p
    return None


def pulse_term(hz: float, fast: Optional[Tuple[int, float]] = None) -> str:
    """明滅の Molang（周期の前半だけ表示）。fast = (nr:ability の値, その間の Hz)。"""
    if fast:
        f = f"(q.property('nr:ability') == {int(fast[0])} ? {float(fast[1]):.2f} : {float(hz):.2f})"
    else:
        f = f"{float(hz):.2f}"
    return f"math.mod(q.life_time * {f}, 1.0) < 0.5"


# ---------------------------------------------------------------------------
#  文脈
# ---------------------------------------------------------------------------
class MutCtx(KO.OutfitCtx):
    """変異の関数に渡す文脈。OutfitCtx（rng / z / style()）＋ scale（予算の倍率 0..1）。"""

    def __init__(self, z: Optional[dict] = None, key: str = "", stylebook: Optional[dict] = None,
                 salt: str = "", scale: float = 1.0):
        super().__init__(z, "mut/" + key, stylebook, salt)
        self.key = key
        self.scale = float(scale)

    def style(self, name_hint: str, style_dict: dict) -> str:
        # 中身が同じ m_* は使い回す（塗りの手間はスタイル数で決まる）
        for n, sd in self.book.items():
            if n.startswith("m_") and sd == style_dict:
                return n
        name, i = name_hint, 2
        while name in self.book:
            name = f"{name_hint}_{i}"
            i += 1
        self.book[name] = style_dict
        self.added[name] = style_dict
        return name


# ---------------------------------------------------------------------------
#  道具箱
# ---------------------------------------------------------------------------
class _M(KO._K):
    """1 つの変異を作る間の道具箱（nr_kit_outfit._K の寸法・箱の道具＋変異用の道具）。"""

    def __init__(self, rig, p: dict, ctx, key: str):
        super().__init__(rig, p, ctx, key)
        self.book: dict = ctx.book
        g = self.z.get("gore") or {}
        self.bk = g.get("blood") or (self.book.get("blood") or {}).get("blood_kind", "red")
        self.scale = float(getattr(ctx, "scale", 1.0))
        rig.__dict__.setdefault("_nr_mut_skin", {})
        self.skin_reg: Dict[str, dict] = rig._nr_mut_skin
        if not hasattr(rig.model, "nr_vis_terms"):
            rig.model.nr_vis_terms = {}
        if not hasattr(rig.model, "nr_particles"):
            rig.model.nr_particles = []
        if not hasattr(rig.model, "nr_glow"):
            rig.model.nr_glow = {}
        self.T = rig.L.t / R.REF_T          # 基準の体（176cm）に対する大きさ（棘・腫瘍の寸法に掛ける）

    # ------------------------------------------------------------ キューブ
    def box(self, bone, x0, y0, z0, x1, y1, z1, style, uv=None, decals=None, rot=None, pivot=None):
        c = super().box(bone, x0, y0, z0, x1, y1, z1, style, uv, decals, rot, pivot)
        c.nr_mut = self.key
        if style in ("skin", "skin_dark") or (style.startswith("m_skin") and style in self.book):
            c.nr_skin = "skin_dark" if "dark" in style else "skin"
        return c

    def beam(self, bone, p0, p1, w, d, style, uv=None, over=0.0):
        c = super().beam(bone, p0, p1, w, d, style, uv, over)
        c.nr_mut = self.key
        return c

    def n(self, k: float, lo: int = 1) -> int:
        """数の引数に予算の倍率を掛ける。"""
        return max(lo, int(round(float(k) * self.scale)))

    # ------------------------------------------------------------ スタイル
    def ms(self, hint: str, mat: str, **kw) -> str:
        d = {"mat": mat}
        if mat not in ("glow",):
            d["blood_kind"] = self.bk
        d.update(kw)
        memo = ("m", hint, repr(sorted(d.items())))
        name = self._memo.get(memo)
        if name is None:
            name = self.ctx.style("m_" + hint, d)
            self._memo[memo] = name
            self.styles[name] = d
        return name

    def bs(self, name: str) -> str:
        """体のスタイル（zombie_styles の名前）。無い本でも動くように最低限を作る。"""
        if name in self.book:
            return name
        return self.ms(name, {"skin_dark": "skin"}.get(name, name))

    def skin_st(self, bone: str, fam: str = "skin") -> str:
        """bone の肌（変異で派生していればその名前）。"""
        mods = self.skin_reg.get(bone)
        if not mods or fam not in self.book:
            return self.bs(fam)
        d = copy.deepcopy(self.book[fam])
        d.update(mods)
        name = self.ctx.style(f"m_{fam}", d)
        self.styles[name] = d
        return name

    def derive(self, hint: str, base: str, **kw) -> str:
        """本の base のスタイルを写して kw を上書きした m_* スタイル。"""
        d = copy.deepcopy(self.book.get(base) or {"mat": base})
        d.update(kw)
        name = self.ctx.style("m_" + hint, d)
        self.styles[name] = d
        return name

    def restyle(self, bones: Sequence[str], mods: dict) -> None:
        """bones の体の肌のキューブ（服を除く）の肌を mods で派生させる（後から足す肌も同じ派生）。"""
        for b in bones:
            if b not in self.rig.bones:
                continue
            cur = dict(self.skin_reg.get(b, {}))
            for k, v in mods.items():
                if k in _NUMERIC_MAX and isinstance(v, (int, float)) and isinstance(cur.get(k), (int, float)):
                    cur[k] = max(cur[k], v)
                else:
                    cur[k] = v
            self.skin_reg[b] = cur
            for c in self.rig.bones[b].cubes:
                if getattr(c, "nr_kit", None) and not getattr(c, "nr_mut", None):
                    continue
                fam = getattr(c, "nr_skin", None)
                if fam is None:
                    if c.style not in ("skin", "skin_dark"):
                        continue
                    fam = c.style
                    c.nr_skin = fam
                c.style = self.skin_st(b, fam)

    # ------------------------------------------------------------ 体の面
    def skin_cubes(self, bone: str, rotated: bool = False) -> list:
        b = self.rig.bones.get(bone)
        if b is None:
            return []
        return [c for c in b.cubes if getattr(c, "nr_skin", None) or c.style in ("skin", "skin_dark")
                if not (getattr(c, "nr_kit", None)) and (rotated or not (c.rotation and any(c.rotation)))]

    def add_decal(self, cube, face: str, decal) -> None:
        cur = cube.decals.get(face) if cube.decals else None
        lst = [] if cur is None else ([cur] if isinstance(cur, (str, dict)) else list(cur))
        lst += decal if isinstance(decal, list) else [decal]
        if cube.decals is None:
            cube.decals = {}
        cube.decals[face] = lst

    def decals_on(self, bone: str, make, faces: Optional[Sequence[str]] = None, per_face: int = 1) -> int:
        """bone の体の肌で faces（n/s/e/w/u/d）の向きに一番外の大きな面へ make(face, cube, i) のデカール。"""
        cubes = self.skin_cubes(bone)
        if not cubes:
            return 0
        k = 0
        for f in (faces or VIS_FACES.get(bone, ("n",))):
            face = _FACE_OF[f]
            c = KO._exposed(cubes, face)
            for i in range(per_face):
                d = make(face, c, i)
                if d:
                    self.add_decal(c, face, d)
                    k += 1
        return k

    # ------------------------------------------------------------ 寸法
    def outer(self, seg: str) -> float:
        """seg の服の一番外の余白（服が無ければ 0）。"""
        return float(self.offs.get(seg, 0.0))

    def sring(self, seg: str, y: float) -> Tuple[float, float, float, float]:
        """高さ y の表面の断面 (x0, z0, x1, z1)。服があればその殻（服と同じ正規の輪切り＋余白）、
        無ければ y の前後だけの体のキューブ（細かい凹凸に沿う）。"""
        o = self.outer(seg)
        if o > 0:
            x0, z0, x1, z1 = self.ring_at(seg, y)
            return x0 - o, z0 - o, x1 + o, z1 + o
        sg = self.seg(seg)
        y = min(max(y, sg["lo"][1] + 0.05), sg["hi"][1] - 0.05)
        return self.ring(seg, y - 0.3, y + 0.3)

    def pt(self, seg: str, side: str, a: float, y: float, out: float = 0.0) -> np.ndarray:
        """部位 seg の高さ y・面 side（n/s/e/w）の表面の点。a は面の横の割合（n/s は -X→+X、e/w は -Z→+Z）。"""
        x0, z0, x1, z1 = self.sring(seg, y)
        if side == "n":
            return np.array([x0 + a * (x1 - x0), y, z0 - out])
        if side == "s":
            return np.array([x0 + a * (x1 - x0), y, z1 + out])
        if side == "e":
            return np.array([x0 - out, y, z0 + a * (z1 - z0)])
        if side == "w":
            return np.array([x1 + out, y, z0 + a * (z1 - z0)])
        sg = self.seg(seg)
        return np.array([x0 + a * (x1 - x0), sg["hi"][1] + self.outer(seg) + out, (z0 + z1) / 2])

    def yspan(self, seg: str, f0: float, f1: float) -> Tuple[float, float]:
        sg = self.seg(seg)
        lo, hi = sg["lo"][1], sg["hi"][1]
        return lo + (hi - lo) * f0, lo + (hi - lo) * f1

    def head(self):
        return KO._head(self)

    def eyes(self):
        return KO._eyes(self)

    # ------------------------------------------------------------ 形の道具
    def fbox(self, bone: str, P, side: str, hw: float, hh: float, d0: float, d1: float, style: str,
             uv=None, decals=None, spin: float = 0.0):
        """面の点 P に貼る箱。side の法線方向に d0..d1（負は内側）、横の半幅 hw・縦の半高 hh
        （上下の面なら横 = X、縦 = Z）。spin は法線まわりの回転（度、P 中心）。"""
        nv = NRM[side]
        ax = int(np.argmax(np.abs(nv)))
        sg = 1.0 if nv[ax] > 0 else -1.0
        hor = 0 if ax != 0 else 2
        ver = 1 if ax != 1 else 2
        lo = [float(v) for v in P]
        hi = [float(v) for v in P]
        lo[hor], hi[hor] = P[hor] - hw, P[hor] + hw
        lo[ver], hi[ver] = P[ver] - hh, P[ver] + hh
        a, b = P[ax] + sg * d0, P[ax] + sg * d1
        lo[ax], hi[ax] = min(a, b), max(a, b)
        rot = None
        if abs(spin) > 0.01:
            r = [0.0, 0.0, 0.0]
            r[ax] = round(spin, 2)
            rot = tuple(r)
        return self.box(bone, *lo, *hi, style, uv, decals, rot, tuple(float(v) for v in P) if rot else None)

    def lump(self, bone: str, P, side: str, r: float, h: float, style: str, cap_style: Optional[str] = None,
             uv=None, spin: Optional[float] = None, k: int = 3, flat: float = 1.0) -> list:
        """丸いこぶ（十字に重ねた 2 個＋頂きの 1 個）。r は横の半径、h は表面からの高さ。"""
        sp = self.rng.uniform(-25, 25) if spin is None else spin
        out = [self.fbox(bone, P, side, r, r * 0.68 * flat, -h * 0.35, h * 0.72, style, uv, spin=sp),
               self.fbox(bone, P, side, r * 0.68, r * flat, -h * 0.35, h * 0.72, style, uv, spin=sp)]
        if k >= 3:
            out.append(self.fbox(bone, P, side, r * 0.52, r * 0.52 * flat, h * 0.4, h, cap_style or style, uv,
                                 spin=sp))
        return out

    def blob(self, bone: str, P, side: str, r: float, h: float, style: str, cap_style: Optional[str] = None,
             uv=None, spin: Optional[float] = None) -> list:
        """丸く盛り上がった塊（十字の 2 個＋肩の 1 個＋頂きの 1 個。lump より丸い）。"""
        sp = self.rng.uniform(-25, 25) if spin is None else spin
        cs = cap_style or style
        return [self.fbox(bone, P, side, r, r * 0.72, -h * 0.3, h * 0.55, style, uv, spin=sp),
                self.fbox(bone, P, side, r * 0.72, r, -h * 0.3, h * 0.55, style, uv, spin=sp),
                self.fbox(bone, P, side, r * 0.8, r * 0.8, h * 0.3, h * 0.84, cs, uv, spin=sp),
                self.fbox(bone, P, side, r * 0.5, r * 0.5, h * 0.7, h, cs, uv, spin=sp)]

    def spike(self, bone: str, p0, d, length: float, w0: float, style: str, segs: int = 3,
              bend=(0.0, 0.0, 0.0), uv=None, flat: float = 1.0, aspect=None) -> list:
        """p0 から d の向きへ細くなる棘（segs 節）。bend は節ごとに足す曲がり（単位ベクトルへの加算）。
        aspect = (梁の w の倍率, d の倍率)（刃・背びれのように平たくする。既定は (1, flat)）。"""
        p = np.asarray(p0, float)
        d = _unit(d)
        ax, az = aspect if aspect is not None else (1.0, flat)
        out = []
        for i in range(segs):
            f = 1.0 - i / segs
            ln = length / segs * (1.12 if i == 0 else 1.0)
            q = p + d * ln
            w = max(0.08, w0 * (0.32 + 0.68 * f) if i < segs - 1 else w0 * 0.3)
            out.append(self.beam(bone, p, q, max(0.06, w * ax), max(0.06, w * az), style, uv, over=0.05))
            p = q - d * 0.05
            d = _unit(d + np.asarray(bend, float))
        return out

    def chain(self, bone: str, p0, dirs: Sequence, length: float, w0: float, w1: float, style: str,
              uv=None) -> Tuple[list, np.ndarray]:
        """p0 から dirs の向きの節を順につなぐ（触手・管）。返り値 (キューブ, 先端)。"""
        p = np.asarray(p0, float)
        out = []
        n = len(dirs)
        for i, d in enumerate(dirs):
            f = i / max(1, n - 1)
            w = w0 + (w1 - w0) * f
            q = p + _unit(d) * (length / n)
            out.append(self.beam(bone, p, q, w, w, style, uv, over=0.06))
            p = q
        return out, p

    def drips(self, bone: str, P, side: str, n: int, length=(0.6, 1.8), width=(0.12, 0.22),
              style: Optional[str] = None, spread: float = 0.5) -> list:
        """面の点 P から下へ垂れる血の筋（表面に沿う薄い箱）。"""
        st = style or self.bs("blood")
        out = []
        for _ in range(max(0, n)):
            ln = self.rng.uniform(*length)
            w = self.rng.uniform(*width)
            off = self.rng.uniform(-spread, spread)
            nv = NRM[side]
            ax = int(np.argmax(np.abs(nv)))
            hor = 0 if ax != 0 else 2
            q = np.array(P, float)
            q[hor] += off
            q[1] -= ln / 2
            out.append(self.fbox(bone, q, side, w / 2, ln / 2, -0.02, 0.05, st, uv=self.U["gore"]))
        return out

    def wound(self, bone: str, P, side: str, hw: float, hh: float, style: Optional[str] = None,
              depth: float = 0.06, rim: Optional[str] = None, spin: float = 0.0) -> list:
        """傷の穴（濡れた肉の板）と、めくれた皮の縁（上下の 2 枚）。"""
        st = style or self.ms("wound", "gore_wet")
        out = [self.fbox(bone, P, side, hw, hh, -0.05, depth, st, uv=self.U["gore"], spin=spin)]
        if rim:
            for sy in (-1, 1):
                q = np.array(P, float)
                q[1] += sy * (hh + 0.05)
                out.append(self.fbox(bone, q, side, hw * self.rng.uniform(0.6, 0.95), 0.1, -0.05,
                                     depth + 0.07, rim, spin=spin + self.rng.uniform(-12, 12)))
        return out

    def child_bone(self, name: str, pivot=None, parent: Optional[str] = None) -> str:
        """変異の子ボーン（親は MUT_BONE_PARENTS か glow_ の名前から決まる）。"""
        par = parent or mut_bone_parent(name)
        if par is None:
            raise ValueError(f"nr_kit_mut: 親の決まっていない子ボーン '{name}'")
        b = self.rig.bones.get(name)
        if b is None:
            pb = self.rig.bones[par]
            b = R.NRBone(name, [round(float(v), 3) for v in (pivot if pivot is not None else pb.pivot)], par, None)
            self.rig.model.bones.append(b)
            self.rig.bones[name] = b
        elif b.parent != par:
            raise ValueError(f"nr_kit_mut: ボーン '{name}' の親が {b.parent} と {par} で食い違う")
        return name

    def glow_bone(self, parent: str, hz: float, fast: Optional[Tuple[int, float]] = None,
                  phase: Optional[int] = None) -> str:
        """光って明滅する部品の子ボーン（表示条件の項を model.nr_vis_terms に記録）。"""
        tag = f"p{int(round(hz * 10))}" + (f"f{fast[0]}x{int(round(fast[1] * 10))}" if fast else "") + \
            (f"a{phase}" if phase else "")
        name = f"glow_{parent}_{tag}"
        self.child_bone(name, parent=parent)
        terms = []
        if hz and hz > 0:
            terms.append(pulse_term(hz, fast))
        if phase:
            terms.append(f"q.property('nr:ability') == {int(phase)}")
        self.rig.model.nr_vis_terms[name] = terms
        self.rig.model.nr_glow[name] = dict(parent=parent, hz=hz, fast=fast, phase=phase)
        return name

    def armor_bone(self, bone: str) -> str:
        """硬い変異の置き場所（gore.armored の部位なら armor_*、無ければ体の部位）。"""
        slot = ARMOR_AT.get(bone)
        g = self.z.get("gore") or {}
        if slot and slot[0] in (g.get("armored") or ()):
            return self.armor(*slot)
        return bone

    def locator(self, bone: str, name: str, P) -> str:
        b = self.rig.bones[bone]
        b.locators[name] = [round(float(v), 3) for v in P]
        return name


def _side_of(bone: str) -> Optional[str]:
    if bone.endswith("_r"):
        return "r"
    if bone.endswith("_l"):
        return "l"
    return None


def _outward(bone: str) -> str:
    """手足の外側の面（右 = e = -X、左 = w = +X）。"""
    return "e" if _side_of(bone) == "r" else "w"


def _sides(v) -> Tuple[str, ...]:
    if v in ("both", None):
        return ("r", "l")
    return tuple(c for c in str(v) if c in "rl") or ("r", "l")


def _face_pt(c, face: str, u: float, v: float, out: float = 0.0) -> np.ndarray:
    """回転していないキューブの面の正規化座標 (u, v) → 点（nr_paint の面の向きの約束どおり。
    east = min-X で u→-Z、west = max-X で u→+Z、north: u→+X、south: u→-X、側面の v は上が 0）。"""
    ox, oy, oz = (float(x) for x in c.origin)
    sx, sy, sz = (float(x) for x in c.size)
    if face == "north":
        return np.array([ox + u * sx, oy + sy - v * sy, oz - out])
    if face == "south":
        return np.array([ox + sx - u * sx, oy + sy - v * sy, oz + sz + out])
    if face == "east":
        return np.array([ox - out, oy + sy - v * sy, oz + sz - u * sz])
    if face == "west":
        return np.array([ox + sx + out, oy + sy - v * sy, oz + u * sz])
    if face == "up":
        return np.array([ox + u * sx, oy + sy + out, oz + sz - v * sz])
    return np.array([ox + u * sx, oy - out, oz + v * sz])


_FACE_NRM = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (-1, 0, 0), "west": (1, 0, 0),
             "up": (0, 1, 0), "down": (0, -1, 0)}


def _remove_nose(M: _M) -> int:
    """nr_rig の鼻（顔板の前の中央の細い 3 個）を外し、顔デカールを鼻の穴にする。"""
    L = M.L
    w, d, c, H = L.head_w, L.head_d, L.chin, L.H
    head = M.rig.bones["head"]

    def is_nose(cb) -> bool:
        if getattr(cb, "nr_kit", None) or getattr(cb, "nr_seg", None) != "face":
            return False
        x0, x1 = cb.origin[0], cb.origin[0] + cb.size[0]
        return (abs(x0 + x1) < 0.05 and cb.size[0] < 0.3 * w and cb.origin[2] < -0.40 * d - 0.01
                and c + 0.3 * H < cb.origin[1] < c + 0.6 * H)

    n0 = len(head.cubes)
    head.cubes = [cb for cb in head.cubes if not is_nose(cb)]
    fd = getattr(M.rig, "face_decal", None)
    if fd is not None:
        fd["nose"] = False
    return n0 - len(head.cubes)


# ===========================================================================
#  テクスチャ（肌の派生・デカール）
# ===========================================================================
def m_dark_veins(rig, p, ctx):
    """感染の黒い血管（発光しない）。肌の静脈を濃く・その色にし、面に蜘蛛の巣状の血管のデカール、
    素肌の部位には浮き出た黒い血管の網。"""
    M = _M(rig, p, ctx, "dark_veins")
    dens = _lv(p.get("density", 1))
    col = KO._c3(p.get("color", (60, 20, 40)))
    on = _list(p.get("on", ["neck"]))
    M.restyle(on, {"veins": (0.9, 1.25, 1.7)[dens - 1], "vein": col})
    amt = (0.6, 0.8, 1.0)[dens - 1]
    for b in on:
        M.decals_on(b, lambda f, c, i: dict(name="veins", colour=col, amount=amt))
    st = M.ms("dark_vein", "flesh", base=KO._mul(col, 0.9), wet=0.4)
    for b in on:
        _vein_net(M, b, st, n_sides=dens, w=0.13 + 0.02 * dens, branches=dens - 1)
    return M.done()


def m_burn_scars(rig, p, ctx):
    """ケロイド状の火傷痕。肌に赤茶の斑と照り、面に火傷のデカール、素肌なら盛り上がった瘢痕の板。"""
    M = _M(rig, p, ctx, "burn_scars")
    cov = max(0.05, min(1.0, float(p.get("coverage", 0.3))))
    on = _list(p.get("on", ["head"]))
    M.restyle(on, {"bruises": 0.15 + 0.3 * cov, "lesions": 0.06 + 0.15 * cov, "mottle": (150, 72, 64)})
    scar = M.ms("scar", "skin", tone=dict(base=(178, 108, 96), shadow=(112, 56, 50), highlight=(216, 154, 140)),
                decay=1.0, veins=0.1, wet=0.55, rot=0.0, lesions=0.0, exposed=0.0, cracks=0.3,
                vein=(124, 52, 46), blood=0.0, dirt=0.2)
    n = 1 + int(cov * 2.5)
    for b in on:
        def mk(face, c, i):
            return [dict(name="burn", at=(M.rng.uniform(0.25, 0.75), M.rng.uniform(0.25, 0.75)),
                         size=0.3 + 0.55 * cov) for _ in range(n)]
        M.decals_on(b, mk)
        if b == "head":
            for c in rig.bones["head"].cubes:
                dv = c.decals.get("north") if c.decals else None
                if isinstance(dv, dict) and dv.get("name") == "face":
                    M.add_decal(c, "north", dict(name="burn", at=(M.rng.choice((0.28, 0.72)), 0.45),
                                                 size=0.25 + 0.4 * cov))
        seg = SEG.get(b)
        if not seg or M.outer(seg) > 0 or seg not in rig.segments:
            continue
        sides = [s for s in VIS_FACES.get(b, ("n",)) if s in "nsew"]
        for _ in range(1 + int(cov > 0.35)):
            side = M.rng.choice(sides)
            y0, y1 = M.yspan(seg, 0.25, 0.8)
            q = M.pt(seg, side, M.rng.uniform(0.25, 0.75), M.rng.uniform(y0, y1))
            k = (0.6 + cov) * M.T
            M.fbox(b, q, side, M.rng.uniform(0.3, 0.6) * k, M.rng.uniform(0.25, 0.5) * k, -0.04, 0.07, scar,
                   spin=M.rng.uniform(-30, 30))
    return M.done()


def m_skin_peeled(rig, p, ctx):
    """皮が剥けて赤い筋肉が出た斑（肌の exposed）。素肌ならめくれた皮の端を 1 枚。"""
    M = _M(rig, p, ctx, "skin_peeled")
    cov = max(0.05, min(1.0, float(p.get("coverage", 0.3))))
    on = _list(p.get("on", ["chest"]))
    M.restyle(on, {"exposed": min(0.9, 0.14 + cov * 0.9)})
    if cov >= 0.25:
        under = M.bs("flesh")
        for b in on:
            seg = SEG.get(b)
            if not seg or M.outer(seg) > 0 or seg not in rig.segments:
                continue
            side = M.rng.choice([s for s in VIS_FACES.get(b, ("n",)) if s in "nsew"][:2])
            y0, y1 = M.yspan(seg, 0.3, 0.75)
            q = M.pt(seg, side, M.rng.uniform(0.3, 0.7), M.rng.uniform(y0, y1))
            sp = M.rng.uniform(-40, 40)
            M.fbox(b, q, side, 0.42 * M.T, 0.3 * M.T, -0.02, 0.06, under, spin=sp)
            M.fbox(b, q + np.array([0, 0.3 * M.T, 0]), side, 0.4 * M.T, 0.08, 0.04, 0.2, M.skin_st(b), spin=sp)
    return M.done()


def m_waterlogged(rig, p, ctx):
    """水を吸ってふやけた全身（濡れ・大理石模様の静脈・藻の斑）。手首から手袋のように剥がれかけた皮と藻の塊。"""
    M = _M(rig, p, ctx, "waterlogged")
    cov = max(0.05, min(1.0, float(p.get("coverage", 0.8))))
    algae = p.get("algae")
    mods = {"wet": 0.5 + 0.4 * cov, "veins": 0.8 + 0.6 * cov, "vein": (58, 74, 98), "bruises": 0.2 * cov}
    if algae:
        mods.update(mottle=KO._c3(algae), spores=0.2 + 0.4 * cov)
    M.restyle([b for b in BODY_BONES if b in rig.bones], mods)
    slough = M.derive("slough", "skin", tone=dict(base=(206, 200, 188), shadow=(142, 138, 128),
                                                   highlight=(232, 228, 218)), wet=0.85, exposed=0.0, rot=0.0)
    L = M.L
    for s in "rl":
        hand, fseg = f"hand_{s}", f"forearm_{s}"
        if hand not in rig.bones:
            continue
        for k in range(M.n(1 + 2 * cov)):
            side = ("n", "s", _outward(hand))[k % 3]
            q = M.pt(fseg, side, M.rng.uniform(0.25, 0.75), L.wrist_y + 0.1)
            q[1] = L.wrist_y - L.palm_l * 0.25
            M.fbox(hand, q, side, M.rng.uniform(0.22, 0.4) * M.T, L.palm_l * 0.42, 0.03, 0.12, slough,
                   spin=M.rng.uniform(-14, 14))
    if algae:
        a = KO._c3(algae)
        alg = M.ms("algae", "fungus", base=KO._mul(a, 0.7), alt=KO._mix(a, (200, 220, 160), 0.3))
        for b, side, fy in (("chest", "e", 0.9), ("chest", "s", 0.75), ("head", "w", 0.7), ("arm_l", "w", 0.85)):
            seg = SEG[b]
            if seg not in rig.segments:
                continue
            y = M.yspan(seg, fy, fy)[0]
            q = M.pt(seg, side, M.rng.uniform(0.3, 0.7), y)
            M.lump(b, q, side, M.rng.uniform(0.3, 0.5) * M.T, 0.22 * M.T, alg, k=2)
    return M.done()


def m_charred_crust(rig, p, ctx):
    """炭化した殻: 全身の肌をひび割れ（ember なら割れ目が発光）にし、少し浮いた炭の殻の板を散らす。"""
    M = _M(rig, p, ctx, "charred_crust")
    cov = max(0.05, min(1.0, float(p.get("coverage", 0.8))))
    ember = p.get("ember")
    mods = {"cracks": 0.25 + 0.7 * cov, "vein": KO._c3(ember) if ember else (52, 22, 14), "mottle": (70, 64, 60)}
    if ember:
        mods["emissive_vein"] = True
    M.restyle([b for b in BODY_BONES if b in rig.bones], mods)
    crust = M.ms("crust", "char", embers=(0.7 if ember else False), blood=0.0)
    weights = [("chest", 3), ("torso", 2), ("arm_r", 1), ("arm_l", 1), ("forearm_r", 1), ("forearm_l", 1),
               ("leg_r", 1.2), ("leg_l", 1.2), ("shin_r", 1), ("shin_l", 1), ("head", 1), ("pelvis", 0.6)]
    pool = [(b, w) for b, w in weights if SEG[b] in rig.segments and M.outer(SEG[b]) <= 0]
    tot = sum(w for _, w in pool) or 1.0
    for _ in range(M.n(3 + 10 * cov) if pool else 0):
        r = M.rng.uniform(0, tot)
        for b, w in pool:
            r -= w
            if r <= 0:
                break
        seg = SEG[b]
        side = M.rng.choice([s for s in VIS_FACES.get(b, ("n",)) if s in "nsew"])
        y0, y1 = M.yspan(seg, 0.15, 0.85)
        q = M.pt(seg, side, M.rng.uniform(0.2, 0.8), M.rng.uniform(y0, y1))
        M.fbox(b, q, side, M.rng.uniform(0.35, 0.8) * M.T, M.rng.uniform(0.3, 0.7) * M.T,
               M.rng.uniform(0.0, 0.05), M.rng.uniform(0.12, 0.2), crust, spin=M.rng.uniform(-35, 35))
    return M.done()


def m_stitches(rig, p, ctx):
    """縫い跡。デカール（stitches）に、crude は太い糸、staples はホチキスの金具を素肌の上に足す。"""
    M = _M(rig, p, ctx, "stitches")
    kind = p.get("kind", "surgical")
    on = _list(p.get("on", ["torso"]))
    thread = M.ms("thread", "cloth", base=(30, 24, 20), pattern="plain", folds=0.1, blood=0.4)
    staple = M.ms("staple", "metal", base=(176, 178, 182), scratches=0.3, blood=0.3)
    for b in on:
        seg = SEG.get(b)
        cubes = M.skin_cubes(b)
        if not cubes or not seg:
            continue
        faces = [f for f in VIS_FACES.get(b, ("n",)) if f in "nsewu"][:2]
        if b == "head":
            faces = ["u", "e"]
        for f in faces:
            face = _FACE_OF[f]
            c = KO._exposed(cubes, face)
            u0, v0 = M.rng.uniform(0.12, 0.3), M.rng.uniform(0.12, 0.3)
            u1, v1 = M.rng.uniform(0.7, 0.88), M.rng.uniform(0.7, 0.9)
            if M.rng.random() < 0.5:
                u0, u1 = u1, u0
            M.add_decal(c, face, dict(name="stitches", start=(u0, v0), end=(u1, v1)))
            if kind == "surgical" or M.outer(seg) > 0:
                continue
            nf = np.array(_FACE_NRM[face], float)
            a = _face_pt(c, face, u0, v0, 0.03)
            e = _face_pt(c, face, u1, v1, 0.03)
            dv = e - a
            ln = float(np.linalg.norm(dv))
            if ln < 0.4:
                continue
            perp = _unit(np.cross(nf, dv))
            k = max(3, min(7, int(ln / (0.55 if kind == "crude" else 0.42))))
            for i in range(k):
                t = (i + 0.5) / k
                q = a + dv * t + nf * 0.04
                h = (0.26 if kind == "crude" else 0.2) * M.T
                tilt = dv / ln * (M.rng.uniform(-0.12, 0.12) if kind == "crude" else 0.0)
                if kind == "crude":
                    M.beam(b, q - perp * h + tilt, q + perp * h - tilt, 0.1, 0.1, thread)
                else:
                    M.beam(b, q - perp * h, q + perp * h, 0.09, 0.07, staple)
    return M.done()


def m_veins_glowing(rig, p, ctx):
    """皮膚の下で脈打って光る血管。肌の血管をその色に（only_phase が無ければ発光のデカール）、
    素肌の部位には浮き出た光る血管の網（子ボーン glow_<部位>_<印>。明滅・能力の段階で表示）。"""
    M = _M(rig, p, ctx, "veins_glowing")
    col = KO._c3(p.get("color", (120, 255, 200)))
    hz = float(p.get("pulse_hz") or 0.0)
    on = _list(p.get("on", ["chest"]))
    phase = None
    if p.get("only_phase"):
        try:
            phase = S.ability_states(M.z).get(p["only_phase"])
        except Exception:  # noqa: BLE001  spec の項目でない確認用の z
            phase = None
        phase = phase or 1
    M.restyle(on, {"veins": 1.15, "vein": KO._mul(col, 0.42)})
    if not phase:
        for b in on:
            M.decals_on(b, lambda f, c, i: dict(name="veins", colour=col, amount=0.75, emissive=True))
    glow = M.ms("vein_glow", "glow", base=col)
    for b in on:
        _vein_net(M, b, glow, target=lambda bb: M.glow_bone(bb, hz, phase=phase), n_sides=2, w=0.15, branches=1)
    return M.done()


# ===========================================================================
#  顔
# ===========================================================================
def m_eyeless(rig, p, ctx):
    """眼球が無く眼窩が暗い穴（顔デカールの eyes = none）。bleed で頬に血の涙の筋。"""
    M = _M(rig, p, ctx, "eyeless")
    bleed = bool(p.get("bleed", True))
    fd = getattr(rig, "face_decal", None)
    if fd is not None:
        fd["eyes"] = "none"
        fd["bleed"] = bleed
    hw = rig.bones.get("head_wound")
    if hw is not None:
        hw.cubes = [c for c in hw.cubes if getattr(c, "nr_role", None) != "eyeball"]
    if bleed:
        E = M.eyes()
        for sx in (-1, 1):
            q = np.array([sx * E.dx * 0.95, E.y - 0.12, E.z])
            M.drips("head", q, "n", 1, length=(0.7, 1.2), width=(0.12, 0.16), spread=0.04)
    return M.done()


def m_missing_nose(rig, p, ctx):
    """鼻が欠け、鼻腔の三角の穴（鼻のキューブを外し、暗い穴と骨の縁）。"""
    M = _M(rig, p, ctx, "missing_nose")
    _remove_nose(M)
    L = M.L
    H, w, d, c = L.H, L.head_w, L.head_d, L.chin
    cav = M.ms("nasal", "gore_wet")
    E = M.eyes()
    z = E.z
    M.fbox("head", (0, c + 0.42 * H, z), "n", 0.12 * w, 0.075 * H, -0.04, 0.05, cav)
    M.fbox("head", (0, c + 0.49 * H, z), "n", 0.065 * w, 0.05 * H, -0.04, 0.05, cav)
    M.fbox("head", (0, c + 0.335 * H, z), "n", 0.13 * w, 0.02 * H + 0.03, -0.04, 0.08, M.bs("bone"))
    return M.done()


def m_split_face(rig, p, ctx):
    """顔の正中が縦に裂け、中に二列目の歯と赤い肉（glow で裂け目が発光）。顎先も裂ける。"""
    M = _M(rig, p, ctx, "split_face")
    depth = _lv(p.get("depth", 1))
    glow = p.get("glow")
    L = M.L
    H, w, d, c = L.H, L.head_w, L.head_d, L.chin
    _remove_nose(M)
    E = M.eyes()
    zf = E.z
    hw = (0.05 + 0.035 * depth) * w
    y0 = E.plate_low + 0.05
    y1 = E.plate_top - (0.2 - 0.05 * depth) * (E.plate_top - E.plate_low)
    meat = M.ms("split", "gore_wet")
    teeth = M.bs("teeth")
    ym = (y0 + y1) / 2
    M.fbox("head", (0, ym, zf), "n", hw, (y1 - y0) / 2, -0.06, 0.06, meat)
    if glow:
        inner = M.ms("split_glow", "glow", base=KO._c3(glow))
        M.fbox("head", (0, ym, zf), "n", hw * 0.32, (y1 - y0) / 2 * 0.86, 0.0, 0.09, inner)
    nt = 2 + depth
    for sx in (-1, 1):
        for i in range(nt):
            y = y0 + 0.2 + (y1 - y0 - 0.4) * (i + 0.5) / nt
            M.beam("head", (sx * hw * 1.02, y + 0.06, zf - 0.07), (sx * hw * 0.3, y - 0.1, zf - 0.07), 0.13, 0.12,
                   teeth, uv=M.U["face"])
        # めくれた縁の皮（外へ開く）
        piv = (sx * hw, ym, zf)
        M.box("head", sx * hw, y0 + 0.05, zf - 0.12, sx * (hw + 0.22), y1 - 0.05, zf + 0.04, M.skin_st("head"),
              rot=(0, -sx * (18 + 6 * depth), 0), pivot=piv)
    # 顎先の裂け目
    jl = M.seg("jaw")
    jy0, jy1 = jl["lo"][1] + 0.12, c + 0.17 * H
    jz = jl["lo"][2]
    M.fbox("jaw", (0, (jy0 + jy1) / 2, jz), "n", hw * 0.8, (jy1 - jy0) / 2, -0.06, 0.06, meat)
    for sx in (-1, 1):
        M.beam("jaw", (sx * hw * 0.9, (jy0 + jy1) / 2, jz - 0.07), (sx * hw * 0.25, (jy0 + jy1) / 2 + 0.12, jz - 0.07),
               0.12, 0.11, teeth, uv=M.U["face"])
    return M.done()


def m_missing_cheek_teeth(rig, p, ctx):
    """頬が食い破られ、奥歯と歯茎が横から丸見え（上は head、下は jaw に付けて顎と一緒に開く）。
    口の端から頬へ裂けた正面の穴もあり、正面からも歯がのぞく。"""
    M = _M(rig, p, ctx, "missing_cheek_teeth")
    sx = -1 if p.get("side", "l") == "r" else 1
    size = _lv(p.get("size", 1))
    L = M.L
    H, w, d, c = L.H, L.head_w, L.head_d, L.chin
    side = "w" if sx > 0 else "e"
    xs = sx * (0.485 * w + 0.02)
    yc = c + 0.205 * H
    zc = -0.22 * d
    hz = (0.17 + 0.05 * size) * d
    hy = (0.075 + 0.025 * size) * H
    meat = M.ms("cheek_hole", "gore_wet")
    teeth, gums = M.bs("teeth"), M.bs("gums")
    M.fbox("head", (xs, yc + hy * 0.5, zc), side, hz, hy * 0.5, -0.06, 0.04, meat, uv=M.U["gore"])
    M.fbox("jaw", (xs, yc - hy * 0.5, zc), side, hz, hy * 0.5, -0.06, 0.04, meat, uv=M.U["gore"])
    nt = 3 + size
    tw = 0.8 * hz / nt
    for i in range(nt):
        z = zc - hz * 0.85 + 2 * hz * 0.85 * (i + 0.5) / nt
        M.fbox("head", (xs, yc + 0.13, z), side, tw, 0.12, 0.0, 0.18, teeth, uv=M.U["face"])
        M.fbox("jaw", (xs, yc - 0.13, z), side, tw, 0.12, 0.0, 0.18, teeth, uv=M.U["face"])
    M.fbox("head", (xs, yc + 0.36, zc), side, hz * 0.9, 0.11, -0.02, 0.12, gums)
    M.fbox("jaw", (xs, yc - 0.36, zc), side, hz * 0.9, 0.11, -0.02, 0.12, gums)
    M.fbox("head", (xs, yc + hy + 0.06, zc), side, hz * 0.85, 0.1, -0.03, 0.16, M.skin_st("head", "skin_dark"),
           spin=M.rng.uniform(-10, 10))
    # 正面: 口の端から頬へ裂けた穴（上は顔板の下、下は顎）と、のぞく歯
    E = M.eyes()
    xc = sx * (0.27 + 0.03 * size) * w
    hwf = (0.08 + 0.025 * size) * w
    M.fbox("head", (xc, yc + 0.06 * H, E.z), "n", hwf, 0.065 * H, -0.05, 0.05, meat, uv=M.U["gore"])
    M.fbox("head", (xc, yc + 0.02 * H, E.z), "n", hwf * 0.75, 0.035 * H, 0.0, 0.1, teeth, uv=M.U["face"])
    jz = -0.46 * d
    M.fbox("jaw", (xc, yc - 0.05 * H, jz), "n", hwf * 0.9, 0.055 * H, -0.05, 0.05, meat, uv=M.U["gore"])
    M.fbox("jaw", (xc, yc - 0.015 * H, jz), "n", hwf * 0.7, 0.03 * H, 0.0, 0.1, teeth, uv=M.U["face"])
    M.drips("jaw", (xs + sx * 0.02, yc - hy, zc + hz * 0.3), side, 1 + (size > 1), length=(0.5, 1.2), spread=0.3)
    return M.done()


def m_elongated_jaw(rig, p, ctx):
    """縦に伸びた顎（顎先が下へ伸びる）。split で顎が左右に裂けて外へ開き、内側に歯の列。
    teeth = human（大きめの歯）/ needle（細く長い針の歯）/ tusk（両端から反り上がる牙）。"""
    M = _M(rig, p, ctx, "elongated_jaw")
    ln = max(1.0, float(p.get("length", 1.3)))
    split = bool(p.get("split", False))
    kind = p.get("teeth", "human")
    L = M.L
    H, w, d, c = L.H, L.head_w, L.head_d, L.chin
    ext = (ln - 1.0) * 0.62 * H
    jaw = rig.bones["jaw"]
    sk = M.skin_st("jaw")
    teeth, gums = M.bs("teeth"), M.bs("gums")
    meat = M.ms("maw", "gore_wet")
    yb = c - 0.01 * H - ext
    ytop = c + 0.2 * H
    tw = 0.1 * M.T
    if split:
        jaw.cubes = [cb for cb in jaw.cubes if getattr(cb, "nr_kit", None) or cb.origin[2] > -0.45 * d]
        gap = 0.05 * w + 0.04 * ext
        ang = 8.0 + 5.0 * ln
        M.box("jaw", -gap - 0.05, yb + 0.25, -0.50 * d, gap + 0.05, ytop, -0.30 * d, meat)
        for sx in (-1, 1):
            rot = (0, 0, -sx * ang)
            piv = (sx * gap, ytop, -0.4 * d)
            M.box("jaw", sx * gap, yb, -0.53 * d, sx * 0.27 * w, ytop - 0.05, -0.28 * d, sk, rot=rot, pivot=piv)
            M.box("jaw", sx * (gap + 0.02), yb + 0.15, -0.555 * d, sx * (gap + 0.16), ytop - 0.1, -0.33 * d,
                  gums, rot=rot, pivot=piv)
            nt = 3 + int(2 * ln)
            for i in range(nt):
                y = yb + 0.3 + (ytop - yb - 0.5) * (i + 0.5) / nt
                th = (0.32 if kind == "human" else 0.42) * M.T
                M.box("jaw", sx * (gap - 0.02), y - 0.06, -0.57 * d, sx * (gap - th), y + 0.06, -0.47 * d,
                      teeth, uv=M.U["face"], rot=rot, pivot=piv)
    else:
        M.box("jaw", -0.24 * w, yb, -0.51 * d, 0.24 * w, c + 0.03 * H, -0.28 * d, sk)
        M.box("jaw", -0.37 * w, yb + ext * 0.35, -0.44 * d, 0.37 * w, c + 0.05 * H, -0.03 * d, sk)
    # 下の顎の前の歯（受け口のように上唇の前へ突き出る）・上の牙・端の牙
    zt = -0.555 * d
    if kind == "needle":
        n = 5 + int(2 * ln)
        xs = np.linspace(-0.2 * w, 0.2 * w, n)
        if not split:
            for x in xs:
                h = M.rng.uniform(0.45, 0.8) * M.T * (0.8 + 0.25 * ln)
                M.beam("jaw", (x, c + 0.1 * H, zt), (x * 1.05, c + 0.1 * H + h, zt - 0.06), tw, tw, teeth,
                       uv=M.U["face"])
        for x in (-0.16 * w, -0.06 * w, 0.06 * w, 0.16 * w):
            h = M.rng.uniform(0.45, 0.7) * M.T * (0.8 + 0.2 * ln)
            M.beam("head", (x, c + 0.21 * H, -0.5 * d), (x * 0.9, c + 0.21 * H - h, -0.53 * d), tw, tw, teeth,
                   uv=M.U["face"])
    elif kind == "tusk":
        bone = M.bs("bone")
        for sx in (-1, 1):
            base = np.array([sx * 0.3 * w, yb + ext * 0.45 + 0.4, -0.5 * d])
            M.spike("jaw", base, (sx * 0.35, 1.0, -0.55), (0.55 + 0.25 * ln) * H * 0.5, 0.42 * M.T, bone, segs=3,
                    bend=(sx * 0.05, 0.12, 0.25))
        for x in (-0.12 * w, 0.12 * w):
            M.beam("head", (x, c + 0.21 * H, -0.5 * d), (x, c + 0.21 * H - 0.6 * M.T, -0.54 * d), tw * 1.6,
                   tw * 1.6, teeth, uv=M.U["face"])
    elif not split:
        for i, x in enumerate(np.linspace(-0.18 * w, 0.18 * w, 5)):
            M.box("jaw", x - 0.07 * w, c + 0.12 * H, zt, x + 0.07 * w, c + 0.12 * H + 0.4 * M.T, zt + 0.2, teeth,
                  uv=M.U["face"])
    return M.done()


# ===========================================================================
#  傷（穴・骨・臓器がのぞく）
# ===========================================================================
def m_exposed_ribs(rig, p, ctx):
    """脇腹（胸の前の外寄りから脇へ回り込む）の皮と肉が裂けて肋骨が count 本のぞく。
    肋骨は胸骨側から外へ下がって脇で後ろへ曲がる 2 本の梁、間に残った肉（flesh 0..1）。"""
    M = _M(rig, p, ctx, "exposed_ribs")
    count = max(2, M.n(p.get("count", 3)))
    flesh = max(0.0, min(1.0, float(p.get("flesh", 0.3))))
    L = M.L
    ch = L.chest_top - L.chest_bot
    bone_st, fl = M.bs("bone"), M.bs("flesh")
    meat = M.ms("rib_cavity", "gore_wet")
    rim = M.skin_st("chest", "skin_dark")
    for s in _sides(p.get("side", "l")):
        sx = -1 if s == "r" else 1
        side = "e" if s == "r" else "w"
        ylo = L.chest_bot + 0.04 * ch
        sp = min(0.72 * M.T, 0.8 * ch / count)
        yhi = min(ylo + sp * count, L.chest_top - 0.12 * ch)
        sp = (yhi - ylo) / count
        ym = (ylo + yhi) / 2
        x0, z0, x1, z1 = M.sring("chest", ym)
        xs = x1 if sx > 0 else x0
        xin = sx * 0.16 * (x1 - x0)
        zf, zmid = z0, z0 + 0.55 * (z1 - z0)
        xc, hw = (xin + xs) / 2, abs(xs - xin) / 2
        hh = (yhi - ylo) / 2 + 0.15
        M.fbox("chest", (xc, ym, zf), "n", hw, hh, -0.06, 0.05, meat, uv=M.U["gore"])
        M.fbox("chest", (xs, ym, (zf + zmid) / 2), side, (zmid - zf) / 2, hh, -0.06, 0.05, meat, uv=M.U["gore"])
        rw = 0.34 * M.T
        for i in range(count):
            y = ylo + sp * (i + 0.5)
            a = np.array([xin, y + 0.22 * M.T, zf - 0.12])
            c = np.array([xs + sx * 0.12, y - 0.2 * M.T, zf - 0.12])
            e = np.array([xs + sx * 0.12, y - 0.3 * M.T, zmid])
            M.beam("chest", a, c, rw, rw, bone_st, over=0.05)
            M.beam("chest", c, e, rw, rw, bone_st, over=0.05)
            if flesh > 0.12 and i < count - 1 and M.rng.random() < 0.3 + flesh:
                M.fbox("chest", (xc + sx * M.rng.uniform(-0.25, 0.25) * hw, y + sp * 0.5, zf), "n",
                       hw * M.rng.uniform(0.25, 0.4 + 0.35 * flesh), sp * 0.26, -0.03, 0.15, fl)
        for sy in (-1, 1):
            yy = (yhi if sy > 0 else ylo) + sy * 0.14
            M.fbox("chest", (xc, yy, zf), "n", hw * M.rng.uniform(0.75, 1.0), 0.12, -0.04, 0.2, rim,
                   spin=M.rng.uniform(-8, 8))
        M.drips("chest", (xc, ylo - 0.1, zf), "n", 2, length=(0.8 * M.T, 2.0 * M.T), spread=hw * 0.7)
    return M.done()


def m_exposed_lungs(rig, p, ctx):
    """胸の皮が裂けて、叫ぶと膨らむ桃色の肺がのぞく（肺は子ボーン lung_r / lung_l で、肋骨の間から盛り上がる）。"""
    M = _M(rig, p, ctx, "exposed_lungs")
    L = M.L
    ch = L.chest_top - L.chest_bot
    meat = M.ms("lung_cavity", "gore_wet")
    lung = M.ms("lung", "tumor", base=(232, 146, 156))
    lung2 = M.ms("lung_pale", "tumor", base=(242, 176, 180))
    bone_st = M.bs("bone")
    y0, y1 = L.chest_bot + 0.28 * ch, L.chest_top - 0.15 * ch
    ym, hh = (y0 + y1) / 2, (y1 - y0) / 2
    for s in _sides(p.get("side", "both")):
        sx = -1 if s == "r" else 1
        x0, z0, x1, z1 = M.sring("chest", ym)
        xc = sx * 0.25 * (x1 - x0)
        hw = 0.18 * (x1 - x0)
        P0 = np.array([xc, ym, z0])
        M.fbox("chest", P0, "n", hw, hh, -0.06, 0.05, meat, uv=M.U["gore"])
        lb = M.child_bone(f"lung_{s}", pivot=(xc, ym, z0 + 0.6))
        M.blob(lb, P0, "n", hw * 0.9, 0.62 * M.T, lung, cap_style=lung2, spin=0.0)
        for i in range(2):
            y = y0 + (y1 - y0) * (0.3 + 0.4 * i)
            M.beam("chest", (xc - sx * hw * 1.1, y + 0.12, z0 - 0.3 * M.T), (xc + sx * hw * 1.1, y - 0.25, z0 - 0.3 * M.T),
                   0.22 * M.T, 0.22 * M.T, bone_st)
        for sy in (-1, 1):
            M.fbox("chest", P0 + np.array([0.0, sy * (hh + 0.1), 0.0]), "n", hw * 0.9, 0.11, -0.03, 0.18,
                   M.skin_st("chest", "skin_dark"), spin=M.rng.uniform(-12, 12))
        M.drips("chest", P0 + np.array([0.0, -hh, 0.0]), "n", 1, length=(0.8, 1.6), spread=hw * 0.5)
    return M.done()


def m_exposed_spine(rig, p, ctx):
    """背中の皮が裂けて椎骨が length 個並ぶ（椎体と横突起。spikes で棘突起が棘に）。"""
    M = _M(rig, p, ctx, "exposed_spine")
    n = max(3, M.n(p.get("length", 6)))
    spikes = bool(p.get("spikes", False))
    L = M.L
    ytop = L.chest_top - 0.06 * (L.chest_top - L.chest_bot)
    ybot = L.abdomen_bot + 0.12 * (L.chest_bot - L.abdomen_bot)
    span = min(ytop - ybot, n * 0.72 * M.T)
    sp = span / n
    meat = M.ms("spine_cavity", "gore_wet")
    bone_st = M.bs("bone")
    for bone, seg, ya, yb in (("chest", "chest", max(ytop - span, L.chest_bot), ytop),
                              ("torso", "abdomen", ytop - span, min(L.chest_bot, ytop))):
        if yb - ya < 0.25:
            continue
        ym = (ya + yb) / 2
        z1 = M.sring(seg, ym)[3]
        P0 = np.array([0.0, ym, z1])
        M.fbox(bone, P0, "s", 0.55 * M.T, (yb - ya) / 2 + 0.08, -0.06, 0.05, meat, uv=M.U["gore"])
        for sx in (-1, 1):
            M.fbox(bone, P0 + np.array([sx * 0.62 * M.T, 0.0, 0.0]), "s", 0.1, (yb - ya) / 2 * 0.95, -0.03, 0.16,
                   M.skin_st(bone), spin=sx * M.rng.uniform(2, 8))
    for i in range(n):
        y = ytop - sp * (i + 0.5)
        bone, seg = ("chest", "chest") if y >= L.chest_bot else ("torso", "abdomen")
        P0 = np.array([0.0, y, M.sring(seg, y)[3]])
        M.fbox(bone, P0, "s", 0.3 * M.T, sp * 0.36, -0.05, 0.24 * M.T, bone_st)
        M.fbox(bone, P0, "s", 0.56 * M.T, sp * 0.13, -0.05, 0.12 * M.T, bone_st)
        if spikes:
            k = 0.65 + 0.45 * math.sin(math.pi * (i + 0.5) / n)
            M.spike(bone, P0 + np.array([0.0, 0.0, 0.12 * M.T]), (0.0, -0.35, 1.0), k * M.T, 0.24 * M.T, bone_st,
                    segs=2)
    yb = ytop - span
    seg = "abdomen" if yb < L.chest_bot else "chest"
    M.drips("torso" if seg == "abdomen" else "chest", (0.0, yb - 0.05, M.sring(seg, yb)[3]), "s", 2,
            length=(0.8, 1.8), spread=0.4)
    return M.done()


def m_exposed_skull(rig, p, ctx):
    """頭皮がめくれて頭蓋骨が露出（頭頂から coverage に応じて側面・額・後頭部へ）。骨の縁は赤い肉の輪、
    めくれた頭皮（外は髪か肌、内は肉）が外へ反って垂れる。"""
    M = _M(rig, p, ctx, "exposed_skull")
    cov = max(0.05, min(1.0, float(p.get("coverage", 0.3))))
    Hd = M.head()
    o = min(M.outer("head"), 0.55)
    skull = M.ms("skull", "bone", age=0.3, blood=0.35)
    raw = M.ms("scalp_raw", "flesh", wet=0.8)
    cracks = dict(name="cracks", amount=0.7)
    sx = M.rng.choice((-1, 1))
    top = Hd.top + o
    wx = Hd.w * (0.45 + 0.5 * cov)
    dz = Hd.d * (0.45 + 0.45 * cov)
    cx = Hd.cx + sx * (Hd.w - wx) / 2 * 0.8
    cz = Hd.z0 + dz / 2 + 0.05
    M.fbox("head", (cx, top, cz), "u", wx / 2 + 0.16, dz / 2 + 0.16, -0.1, 0.08, raw, uv=M.U["gore"])
    M.fbox("head", (cx, top, cz), "u", wx / 2, dz / 2, -0.1, 0.16, skull, decals={"up": cracks})
    side = "w" if sx > 0 else "e"
    xs = (Hd.x1 if sx > 0 else Hd.x0) + sx * o
    hh = Hd.top - Hd.low
    if cov > 0.25:
        y = Hd.top - 0.3 * hh
        M.fbox("head", (xs, y, Hd.z0 + Hd.d * 0.42), side, Hd.d * (0.24 + 0.2 * cov) + 0.14, 0.28 * hh + 0.14, -0.1,
               0.06, raw, uv=M.U["gore"])
        M.fbox("head", (xs, y, Hd.z0 + Hd.d * 0.42), side, Hd.d * (0.24 + 0.2 * cov), 0.28 * hh, -0.1, 0.14, skull,
               decals={_FACE_OF[side]: cracks})
    if cov > 0.5:
        yb = Hd.brow + 0.4
        M.fbox("head", (cx * 0.5, (yb + Hd.top) / 2, Hd.z0 - o), "n", wx * 0.42 + 0.12, (Hd.top - yb) / 2 + 0.1, -0.1,
               0.06, raw, uv=M.U["gore"])
        M.fbox("head", (cx * 0.5, (yb + Hd.top) / 2, Hd.z0 - o), "n", wx * 0.42, (Hd.top - yb) / 2, -0.1, 0.14, skull)
    if cov > 0.75:
        M.fbox("head", (0.0, Hd.top - 0.35 * hh, Hd.z1 + o), "s", Hd.w * 0.36, 0.3 * hh, -0.1, 0.14, skull)
    hair = "hair" if "hair" in M.book else M.skin_st("head", "skin_dark")
    for k, fz in enumerate((0.3, 0.66)):
        fx = sx if k == 0 else -sx
        x = cx + fx * (wx / 2 + 0.12)
        z = Hd.z0 + Hd.d * fz
        piv = (x, top - 0.05, z)
        rot = (0, 0, -fx * M.rng.uniform(28, 48))
        M.box("head", x - 0.1, top - 1.0 * M.T, z - 0.45 * M.T, x + 0.1, top - 0.02, z + 0.45 * M.T, hair,
              rot=rot, pivot=piv)
        M.box("head", x - 0.1 - fx * 0.13, top - 0.85 * M.T, z - 0.38 * M.T, x + 0.1 - fx * 0.13, top - 0.05,
              z + 0.38 * M.T, raw, rot=rot, pivot=piv)
    M.drips("head", (cx, Hd.brow + 0.35, Hd.z0 - o), "n", 2, length=(0.5, 1.1), spread=wx * 0.3)
    return M.done()


def m_torn_throat(rig, p, ctx):
    """喉が食い破られ、気管（軟骨の輪）と筋がのぞく。傷は胸骨の上のくぼみまで続き、下へ血が垂れる。"""
    M = _M(rig, p, ctx, "torn_throat")
    size = _lv(p.get("size", 1))
    L = M.L
    ya = L.shoulder_y + 0.05 * (L.chin - L.shoulder_y)
    yb = L.chin - (0.16 - 0.03 * size) * L.H
    ym = (ya + yb) / 2
    x0, z0, x1, z1 = M.sring("neck", ym)
    hw = (0.24 + 0.07 * size) * (x1 - x0)
    P0 = np.array([0.0, ym, z0])
    meat = M.ms("throat", "gore_wet")
    cart = M.ms("cartilage", "bone", base=(230, 204, 194), age=0.1, blood=0.45)
    fl = M.bs("flesh")
    M.fbox("neck", P0, "n", hw, (yb - ya) / 2, -0.06, 0.05, meat, uv=M.U["gore"])
    M.fbox("neck", P0, "n", 0.2 * M.T, (yb - ya) / 2 * 0.92, -0.02, 0.22 * M.T, cart)
    nr = 2 + size // 2
    for k in range(nr):
        M.fbox("neck", (0.0, ya + (yb - ya) * (k + 0.5) / nr, z0), "n", 0.26 * M.T, 0.07, 0.0, 0.28 * M.T, cart)
    for sx in (-1, 1):
        M.beam("neck", (sx * hw * 0.95, yb - 0.1, z0 - 0.08), (sx * hw * 0.35, ya + 0.15, z0 - 0.14), 0.18, 0.15, fl)
    if "chest" in rig.bones:
        yc = L.chest_top - 0.35 * M.T * (1 + 0.3 * size)
        cz = M.sring("chest", yc)[1]
        hc = 0.35 * M.T * (1 + 0.3 * size)
        M.fbox("chest", (0.0, yc, cz), "n", hw * 0.9, hc, -0.06, 0.05, meat, uv=M.U["gore"])
        M.fbox("chest", (0.0, yc, cz), "n", 0.2 * M.T, hc * 0.95, -0.02, 0.22 * M.T, cart)
        M.fbox("chest", (M.rng.choice((-1, 1)) * hw * 0.5, yc - hc - 0.15, cz), "n", 0.32 * M.T, 0.35 * M.T, 0.0, 0.12,
               M.skin_st("chest", "skin_dark"), spin=M.rng.uniform(-20, 20))
        M.drips("chest", (0.0, yc - hc, cz), "n", 1 + size, length=(0.8 * M.T, 2.4 * M.T), spread=hw * 0.8)
    return M.done()


def m_bite_wound(rig, p, ctx):
    """噛み跡: 腫れた皮膚の板に歯形の半月の傷（bite デカール）、噛みちぎられた肉の穴と両脇の腫れ。
    fresh で鮮血が垂れ、古いと黒く化膿して膿が出る。"""
    M = _M(rig, p, ctx, "bite_wound")
    b = p.get("on", "neck")
    if b not in rig.bones or b not in SEG:
        b = "neck"
    size = _lv(p.get("size", 1))
    fresh = bool(p.get("fresh", False))
    seg = SEG[b]
    if b in ("neck", "chest", "torso", "pelvis", "leg_r", "leg_l", "shin_r", "shin_l"):
        side, a = "n", M.rng.choice((0.3, 0.7))
    elif b in ("head", "jaw"):
        side, a = M.rng.choice(("e", "w")), 0.3
    else:
        side, a = _outward(b), 0.35
    y0, y1 = M.yspan(seg, 0.35, 0.7)
    if b == "neck":
        y0 = y1 = (M.L.shoulder_y + M.L.chin) / 2 + 0.05
    q = M.pt(seg, side, a, M.rng.uniform(y0, y1))
    k = (1.0 + 0.35 * size) * M.T
    if fresh:
        rim = M.derive("bite_rim", "skin", bruises=0.8, mottle=(140, 60, 80), exposed=0.0, rot=0.0)
        pit = M.ms("bite_pit", "gore_wet")
    else:
        rim = M.derive("bite_rot", "skin", bruises=0.9, mottle=(70, 76, 44), rot=0.7, veins=1.3, vein=(50, 40, 40),
                       exposed=0.0)
        pit = M.ms("bite_pit_old", "flesh", base=(70, 40, 30), wet=0.5)
    M.fbox(b, q, side, 0.6 * k, 0.5 * k, -0.03, 0.08, rim,
           decals={_FACE_OF[side]: dict(name="bite", size=0.62, at=(0.5, 0.45))})
    M.fbox(b, q, side, 0.2 * k, 0.15 * k, 0.04, 0.12, pit, uv=M.U["gore"])
    nv = np.array(NRM[side])
    ax = int(np.argmax(np.abs(nv)))
    hor = 0 if ax != 0 else 2
    for s_ in (-1, 1):
        qq = q.copy()
        qq[hor] += s_ * 0.45 * k
        M.lump(b, qq, side, 0.2 * k, 0.16 * k + 0.08, rim, k=2)
    if size >= 2:
        top = q + nv * 0.1 - np.array([0.0, 0.1 * k, 0.0])
        M.beam(b, top + np.array([0.0, -0.55 * k, 0.0]) + nv * 0.12, top, 0.22 * M.T, 0.12, M.bs("flesh"))
    if fresh:
        M.drips(b, q - np.array([0.0, 0.35 * k, 0.0]), side, 1 + size // 2, length=(0.5 * k, 1.4 * k), spread=0.3 * k)
    else:
        pus = M.ms("pus", "tumor", base=(206, 196, 120))
        M.drips(b, q - np.array([0.0, 0.3 * k, 0.0]), side, 1, length=(0.3 * k, 0.7 * k), spread=0.2 * k,
                style=M.bs("blood_dry"))
        qq = q.copy()
        qq[1] += 0.2 * k
        qq[hor] += 0.25 * k
        M.fbox(b, qq, side, 0.12, 0.12, 0.05, 0.16, pus)
    return M.done()


def m_hanging_skin(rig, p, ctx):
    """剥がれて垂れ下がった皮膚の弁（外は皮・内は赤い肉の 2 枚。外へ反って裏の肉が見える）と、
    剥がれた跡の赤い肉。flaps 枚を on に配る。"""
    M = _M(rig, p, ctx, "hanging_skin")
    on = [b for b in _list(p.get("on", ["forearm_l"])) if b in rig.bones and SEG.get(b) in rig.segments]
    if not on:
        return M.done()
    total = max(len(on), M.n(p.get("flaps", 1)))
    under = M.ms("peeled_raw", "flesh", wet=0.85)
    for i in range(total):
        b = on[i % len(on)]
        seg = SEG[b]
        side = M.rng.choice([s for s in VIS_FACES.get(b, ("n",)) if s in "nsew"])
        y0, y1 = M.yspan(seg, 0.45, 0.85)
        q = M.pt(seg, side, M.rng.uniform(0.25, 0.75), M.rng.uniform(y0, y1))
        Lf = M.rng.uniform(1.2, 2.1) * M.T
        wf = M.rng.uniform(0.7, 1.1) * M.T
        nv = np.array(NRM[side])
        M.fbox(b, q - np.array([0.0, Lf * 0.1, 0.0]), side, wf * 0.55, Lf * 0.28, -0.03, 0.05, under, uv=M.U["gore"])
        top = q + np.array([0.0, 0.12, 0.0]) + nv * 0.07
        bot = top + np.array([0.0, -Lf, 0.0]) + nv * M.rng.uniform(0.6, 0.95) * Lf * 0.55
        thin = abs(nv[0]) > 0.5
        w_, d_ = (0.14, wf) if thin else (wf, 0.14)
        M.beam(b, bot, top, w_, d_, under)
        w2, d2 = (0.08, wf * 0.9) if thin else (wf * 0.9, 0.08)
        M.beam(b, bot - nv * 0.12 + np.array([0.0, 0.1, 0.0]), top - nv * 0.12, w2, d2, M.skin_st(b, "skin_dark"))
    return M.done()


def m_missing_fingers(rig, p, ctx):
    """指が count 本欠け、残った根元の節の先に骨と赤い断面。"""
    M = _M(rig, p, ctx, "missing_fingers")
    s = p.get("hand", "l")
    s = s if s in ("r", "l") else "l"
    hand = f"hand_{s}"
    hb = rig.bones.get(hand)
    if hb is None:
        return M.done()
    count = max(1, min(4, int(p.get("count", 2))))
    hw = M.L.hand_w
    fz = (-0.36, -0.12, 0.12, 0.36)
    parts = KO._hand_cubes(M, s)
    if not parts["dist"]:
        return M.done()                       # detail 1（指が板）では外せない

    def zc(c):
        P_ = R.cube_matrix(c) @ np.array([*(np.array(c.origin) + np.array(c.size) / 2), 1.0])
        return float(P_[2])

    def finger_of(c) -> int:
        z = zc(c)
        return int(np.argmin([abs(z - f * hw) for f in fz]))

    pick = sorted(M.rng.sample(range(4), count))
    drop = set()
    for c in parts["dist"]:
        if finger_of(c) in pick:
            drop.add(id(c))
    for c in hb.cubes:
        if getattr(c, "nr_role", None) == "nail" and not getattr(c, "nr_kit", None):
            if abs(zc(c) - (-0.40 * hw)) > 0.12 * hw and finger_of(c) in pick:   # 親指の爪は残す
                drop.add(id(c))
    hb.cubes = [c for c in hb.cubes if id(c) not in drop]
    bone_st = M.bs("bone")
    cap = M.ms("finger_cap", "flesh", wet=0.9)
    for c in parts["prox"]:
        if finger_of(c) not in pick:
            continue
        Mx = R.cube_matrix(c)
        d = _unit(Mx[:3, :3] @ np.array([0.0, 1.0, 0.0]))
        tip = np.array(c.pivot if c.pivot else c.origin, float)
        M.beam(hand, tip + d * 0.05, tip - d * 0.28 * M.T, 0.1, 0.1, bone_st, uv=M.U["fine"])
        M.beam(hand, tip + d * 0.06, tip - d * 0.06, c.size[0] * 1.06, c.size[2] * 1.06, cap, uv=M.U["fine"])
    return M.done()


_IMPALE_OBJS = ("knife", "rebar", "arrow", "glass_shard", "pipe")


def m_impaled(rig, p, ctx):
    """体に刺さったままの物（knife / rebar / arrow / glass_shard / pipe）。angle は上向きの傾き（度）。"""
    M = _M(rig, p, ctx, "impaled")
    obj = p.get("obj", "knife")
    b = p.get("on", "torso")
    if b not in rig.bones or SEG.get(b) not in rig.segments:
        b = "torso"
    seg = SEG[b]
    t = math.radians(float(p.get("angle", 20)))
    y = M.yspan(seg, 0.55, 0.55)[0]
    entry = M.pt(seg, "n", M.rng.uniform(0.32, 0.68), y)
    x0, z0, x1, z1 = M.sring(seg, y)
    depth = z1 - z0
    sx = M.rng.choice((-1, 1))
    out = _unit((sx * 0.5, math.sin(t), -math.cos(t)))
    ins = -out
    M.fbox(b, entry, "n", 0.34 * M.T, 0.28 * M.T, -0.02, 0.05, M.bs("blood"), uv=M.U["gore"])
    M.drips(b, entry - np.array([0.0, 0.2, 0.0]), "n", 2, length=(0.6, 1.6), spread=0.25)
    metal = M.ms("blade", "metal", base=(150, 154, 160), scratches=0.6, blood=0.7)
    rust = M.ms("rebar", "rust", amount=0.9)
    cubes = []
    if obj == "knife":
        e = entry + out * 0.05
        cubes.append(M.beam(b, e + ins * 0.2, e + out * 0.35, 0.1, 0.42 * M.T, metal))
        cubes.append(M.beam(b, e + out * 0.35, e + out * 0.47, 0.5 * M.T, 0.18 * M.T, metal))
        grip = M.ms("grip", "plastic", base=(34, 30, 28))
        cubes.append(M.beam(b, e + out * 0.47, e + out * 1.8 * M.T, 0.26 * M.T, 0.3 * M.T, grip))
    elif obj in ("rebar", "pipe"):
        w = 0.26 * M.T if obj == "rebar" else 0.42 * M.T
        st = rust if obj == "rebar" else M.ms("pipe", "painted_metal", base=(96, 100, 104), rust=0.6)
        back = entry + ins * (depth + (2.0 if obj == "rebar" else 1.2) * M.T)
        front = entry + out * (3.0 if obj == "rebar" else 2.4) * M.T
        cubes.append(M.beam(b, back, front, w, w, st))
        if obj == "rebar":
            cubes.append(M.beam(b, front - out * 0.1, front + _unit(out + np.array([0.0, -1.2, 0.0])) * 1.1 * M.T,
                                w, w, st))
        M.fbox(b, M.pt(seg, "s", 0.5, y), "s", 0.32 * M.T, 0.26 * M.T, -0.02, 0.05, M.bs("blood"), uv=M.U["gore"])
    elif obj == "arrow":
        wood = M.ms("shaft", "wood", base=(150, 112, 70))
        e = entry
        tail = e + out * 2.6 * M.T
        cubes.append(M.beam(b, e + ins * 0.4, tail, 0.13, 0.13, wood))
        vane = M.ms("fletch", "plastic", base=(196, 40, 36))
        a0, a1 = tail - out * 0.75 * M.T, tail - out * 0.08
        cubes.append(M.beam(b, a0, a1, 0.04, 0.42 * M.T, vane))
        cubes.append(M.beam(b, a0, a1, 0.42 * M.T, 0.04, vane))
        head = entry + ins * (depth + 0.5 * M.T)
        cubes.append(M.beam(b, head - out * 0.5, head, 0.16, 0.16, metal))
    else:   # glass_shard
        glass = M.ms("shard", "glass", crack=0.5, blood=0.5)
        for k in range(3):
            d = _unit(out + np.array([M.rng.uniform(-0.5, 0.5), M.rng.uniform(-0.4, 0.4), 0.0]))
            e = entry + np.array([M.rng.uniform(-0.35, 0.35), M.rng.uniform(-0.3, 0.3), 0.0]) * M.T
            ln = M.rng.uniform(0.6, 1.25) * M.T
            ww = M.rng.uniform(0.3, 0.55) * M.T
            cubes.append(M.beam(b, e + ins * 0.15, e + d * ln, ww if k % 2 else 0.05, 0.05 if k % 2 else ww, glass))
    for c in cubes:
        c.nr_nohit = True
    return M.done()


# ===========================================================================
#  生えてくる物（腫瘍・膿疱・菌・袋・結節・棘・爪・刃・触手・管）
# ===========================================================================
def _valid_on(M: _M, on) -> List[str]:
    return [b for b in _list(on) if b in M.rig.bones and SEG.get(b) in M.rig.segments]


def _sides_of(b: str, extra: str = "") -> List[str]:
    return [s for s in VIS_FACES.get(b, ("n",)) if s in "nsew" + extra]


def m_tumor_cluster(rig, p, ctx):
    """ぶよぶよの腫瘍の房（丸い塊を寄せ集める。size 1..3、count 個、color）。"""
    M = _M(rig, p, ctx, "tumor_cluster")
    on = _valid_on(M, p.get("on", "torso")) or ["torso"]
    b = on[0]
    seg = SEG[b]
    size = _lv(p.get("size", 1))
    count = M.n(p.get("count", 3))
    col = KO._c3(p.get("color", (200, 150, 140)))
    st = M.ms("tumor", "tumor", base=col)
    st2 = M.ms("tumor_dark", "tumor", base=KO._mul(col, 0.8))
    st3 = M.ms("tumor_pale", "tumor", base=KO._mix(col, (236, 214, 170), 0.35))
    # 首の前（n）に付けると顎・口を塞いで顔が読めない（wrecker・gasbag の QA）ので、首は横と項だけ
    sides = {"head": ["e", "w", "s", "u"], "neck": ["e", "w", "s"], "chest": ["n", "e", "w", "s"],
             "torso": ["n", "e", "w", "n"]}.get(b, _sides_of(b))
    side0 = M.rng.choice(sides)
    a0 = M.rng.uniform(0.3, 0.7)
    fy0 = M.rng.uniform(0.35, 0.7)
    r0 = (0.45 + 0.32 * size) * M.T
    sg = M.seg(seg)
    hgt = sg["hi"][1] - sg["lo"][1]
    for i in range(count):
        r = r0 * M.rng.uniform(0.6, 1.2)
        if i == 0:
            side, a, fy = side0, a0, fy0
        else:
            side = side0 if M.rng.random() < 0.7 else M.rng.choice(sides)
            a = min(0.88, max(0.12, a0 + M.rng.uniform(-0.34, 0.34)))
            fy = min(0.92, max(0.08, fy0 + M.rng.uniform(-1.4, 1.4) * r0 / max(hgt, 0.5)))
        y = M.yspan(seg, fy, fy)[0]
        q = M.pt(seg, side, a, y)
        M.blob(b, q, side, r, r * M.rng.uniform(1.0, 1.6), (st, st2, st)[i % 3], cap_style=(st3, st, st3)[i % 3])
    return M.done()


def m_pustules(rig, p, ctx):
    """膿の詰まった水疱（赤く腫れた土台と膿のドーム。glow でドームが光る）。density 1..3。"""
    M = _M(rig, p, ctx, "pustules")
    on = _valid_on(M, p.get("on", ["torso"]))
    dens = _lv(p.get("density", 1))
    col = KO._c3(p.get("color", (200, 190, 90)))
    glow = p.get("glow")
    rim = M.ms("pustule_rim", "tumor", base=(176, 98, 90))
    dome = M.ms("pus_glow", "glow", base=KO._c3(glow)) if glow else M.ms("pus", "tumor", base=col)
    per = (2, 4, 6)[dens - 1]
    for b in on:
        seg = SEG[b]
        f = {"chest": 1.4, "torso": 1.4, "head": 0.7, "neck": 0.6, "hand_r": 0.4, "hand_l": 0.4}.get(b, 1.0)
        for _ in range(M.n(per * f)):
            side = M.rng.choice(_sides_of(b))
            y = M.yspan(seg, M.rng.uniform(0.15, 0.9), 0)[0]
            q = M.pt(seg, side, M.rng.uniform(0.15, 0.85), y)
            r = M.rng.uniform(0.22, 0.38) * M.T * (0.85 + 0.15 * dens)
            sp = M.rng.uniform(-30, 30)
            M.fbox(b, q, side, r * 1.4, r * 1.4, -0.04, r * 0.32, rim, spin=sp)
            M.fbox(b, q, side, r, r, 0.0, r * 0.95, dome, spin=sp)
    return M.done()


def m_fungal_growth(rig, p, ctx):
    """皮膚から生えた菌糸の膜とキノコの傘（caps 個）。glow で傘のひだと膜の斑点が発光。"""
    M = _M(rig, p, ctx, "fungal_growth")
    on = _valid_on(M, p.get("on", ["chest"]))
    if not on:
        return M.done()
    cov = max(0.05, min(1.0, float(p.get("coverage", 0.3))))
    col = KO._c3(p.get("color", (200, 190, 150)))
    caps = M.n(p.get("caps", 3), lo=0)
    glow = p.get("glow")
    kw = dict(glow_spots=0.22, glow_colour=KO._c3(glow)) if glow else {}
    mem = M.ms("mycelium", "fungus", base=KO._mul(col, 0.8), alt=col, **kw)
    cap_st = M.ms("mushroom", "fungus", base=col, alt=KO._mix(col, (255, 250, 235), 0.4))
    stem = M.ms("stem", "fungus", base=KO._mix(col, (240, 236, 220), 0.5), alt=(245, 240, 228))
    gill = M.ms("gill_glow", "glow", base=KO._c3(glow)) if glow else M.ms("gill", "fungus", base=KO._mul(col, 0.5))
    for b in on:
        seg = SEG[b]
        for _ in range(M.n(1 + cov * 2.6)):
            side = M.rng.choice(_sides_of(b))
            y = M.yspan(seg, M.rng.uniform(0.2, 0.85), 0)[0]
            q = M.pt(seg, side, M.rng.uniform(0.2, 0.8), y)
            k = (0.6 + cov) * M.T
            M.fbox(b, q, side, M.rng.uniform(0.4, 0.85) * k, M.rng.uniform(0.4, 0.95) * k, -0.03,
                   M.rng.uniform(0.07, 0.15), mem, spin=M.rng.uniform(-40, 40))
    for i in range(caps):
        b = on[i % len(on)]
        seg = SEG[b]
        side = M.rng.choice(_sides_of(b, "u" if b == "head" else ""))
        y = M.yspan(seg, M.rng.uniform(0.3, 0.9), 0)[0]
        q = M.pt(seg, side, M.rng.uniform(0.2, 0.8), y)
        nv = np.array(NRM[side])
        d = _unit(nv + np.array([M.rng.uniform(-0.3, 0.3), 0.9, M.rng.uniform(-0.3, 0.3)]))
        hgt = M.rng.uniform(0.5, 1.15) * M.T
        capr = M.rng.uniform(0.55, 0.95) * M.T
        base = q - nv * 0.1
        tip = base + d * hgt
        M.beam(b, base, tip, 0.34 * M.T, 0.34 * M.T, stem)
        M.beam(b, tip - d * 0.1, tip + d * 0.24 * M.T, capr * 2, capr * 2, cap_st)
        M.beam(b, tip - d * 0.2, tip - d * 0.09, capr * 1.7, capr * 1.7, gill)
    return M.done()


def m_spore_vents(rig, p, ctx):
    """煙突のような菌の噴出孔（count 個）。こぶの土台・太い筒・縁、口の奥が胞子の色にほの光る。
    出口にロケータ loc_spore_<n>（model.nr_particles）。"""
    M = _M(rig, p, ctx, "spore_vents")
    on = _valid_on(M, p.get("on", ["chest"]))
    if not on:
        return M.done()
    count = M.n(p.get("count", 4))
    spores = KO._c3(p.get("spores", (180, 240, 200)))
    body = M.ms("vent", "fungus", base=(176, 146, 104), alt=(214, 192, 150))
    rim = M.ms("vent_rim", "fungus", base=(222, 206, 168), alt=(246, 238, 214))
    hole = M.ms("spore_glow", "glow", base=KO._mul(spores, 0.8))
    parts = rig.model.nr_particles
    pref = {"chest": ["s", "s", "e", "w", "n"], "torso": ["s", "e", "w"], "head": ["u", "s", "e", "w"]}
    for i in range(count):
        b = on[i % len(on)]
        seg = SEG[b]
        side = M.rng.choice(pref.get(b, _sides_of(b)))
        y = M.yspan(seg, M.rng.uniform(0.3, 0.85), 0)[0]
        q = M.pt(seg, side, M.rng.uniform(0.2, 0.8), y)
        nv = np.array(NRM[side])
        d = _unit(nv + np.array([M.rng.uniform(-0.25, 0.25), 0.75, M.rng.uniform(-0.25, 0.25)]))
        ln = M.rng.uniform(1.1, 1.8) * M.T
        M.lump(b, q, side, 0.62 * M.T, 0.38 * M.T, body, k=2)
        M.beam(b, q - nv * 0.1, q + d * ln, 0.82 * M.T, 0.82 * M.T, body)
        M.beam(b, q + d * (ln - 0.12), q + d * (ln + 0.26 * M.T), 1.06 * M.T, 1.06 * M.T, rim)
        M.beam(b, q + d * ln, q + d * (ln + 0.29 * M.T), 0.58 * M.T, 0.58 * M.T, hole, uv=M.U["fine"])
        name = M.locator(b, f"loc_spore_{len(parts) + 1}", q + d * (ln + 0.4 * M.T))
        parts.append(dict(locator=name, bone=b, kind="spores", colour=list(spores)))
    return M.done()


def m_acid_sacs(rig, p, ctx):
    """透けて光る酸の袋（子ボーン acid_sac_<where>。where = neck / cheeks / back / belly、count 個）。"""
    M = _M(rig, p, ctx, "acid_sacs")
    where = p.get("where", "neck")
    where = where if where in ("neck", "cheeks", "back", "belly") else "neck"
    count = max(1, M.n(p.get("count", 2)))
    g = KO._c3(p.get("glow", (150, 255, 60)))
    core = M.ms("acid_glow", "glow", base=KO._mul(g, 0.9))
    mem = M.ms("acid_membrane", "tumor", base=KO._mix(g, (200, 186, 120), 0.55))
    L = M.L
    H, w, d, c = L.H, L.head_w, L.head_d, L.chin
    spots = []
    for i in range(count):
        sx = (-1, 1)[i % 2]
        row = i // 2
        if where == "neck":
            y = (L.chin + L.shoulder_y) / 2 + 0.1 - row * 0.55 * M.T
            side = "e" if sx < 0 else "w"
            spots.append((M.pt("neck", side, 0.32, y), side, 0.62 * M.T))
        elif where == "cheeks":
            side = "e" if sx < 0 else "w"
            spots.append((np.array([sx * (0.47 * w + 0.02), c + (0.33 - 0.16 * row) * H, -0.22 * d]), side,
                          0.68 * M.T))
        elif where == "back":
            y = M.yspan("chest", 0.65 - 0.25 * row, 0)[0]
            spots.append((M.pt("chest", "s", 0.5 + sx * 0.22, y), "s", 0.9 * M.T))
        else:
            y = M.yspan("abdomen", 0.6 - 0.3 * row, 0)[0]
            spots.append((M.pt("abdomen", "n", 0.5 + sx * 0.22, y), "n", 0.85 * M.T))
    pivot = np.mean([q for q, _, _ in spots], axis=0)
    bone = M.child_bone(f"acid_sac_{where}", pivot=pivot)
    for q, side, r in spots:
        lumps = M.lump(bone, q, side, r, r * 1.15, core, uv=M.U["fine"])
        for cb in lumps[:2]:
            M.add_decal(cb, _FACE_OF[side], dict(name="veins", colour=KO._mul(g, 0.3), amount=0.55))
        M.fbox(bone, q, side, r * 1.12, r * 0.3, -0.05, r * 0.45, mem)
    return M.done()


def m_throat_sac(rig, p, ctx):
    """喉の下の大きく膨らむ声の袋（子ボーン throat_sac。付け根が pivot なので拡大で膨らむ）。
    顎の下から胸の上へ垂れる丸い袋（十字の箱を重ね、下が膨らむ）。"""
    M = _M(rig, p, ctx, "throat_sac")
    size = _lv(p.get("size", 2))
    veins = bool(p.get("veins", True))
    glow = p.get("glow")
    L = M.L
    r = (0.8 + 0.5 * size) * M.T
    yn = (L.chin + L.shoulder_y) / 2
    zfront = min(M.sring("neck", yn)[1], M.sring("chest", L.chest_top - 0.3)[1])
    yc = L.chin - 0.7 * r
    zc = zfront - 0.42 * r
    bone = M.child_bone("throat_sac", pivot=(0.0, L.chin - 0.1, M.sring("neck", yn)[1] + 0.3))
    tone = dict((M.book.get("skin") or {}).get("tone") or {"base": (180, 160, 150)})
    tb = KO._mix(tone.get("base", (180, 160, 150)), (214, 128, 132), 0.5)
    sac = M.derive("sac", "skin", tone=dict(base=tb, shadow=KO._mul(tb, 0.6), highlight=KO._mix(tb, (255, 232, 226), 0.35)),
                   veins=1.6 if veins else 0.3, vein=(118, 30, 62), wet=0.6, exposed=0.0, rot=0.0, lesions=0.02,
                   blood=0.05)
    dec = None
    if glow:
        g = KO._c3(glow)
        dec = {"north": [dict(name="glow_spot", at=(0.38, 0.42), size=0.15, colour=g),
                         dict(name="glow_spot", at=(0.64, 0.58), size=0.12, colour=g)]}

    def plus(cy, cz, rx, ry, rz, d=None):
        M.box(bone, -rx, cy - ry * 0.72, cz - rz, rx, cy + ry * 0.72, cz + rz, sac)
        M.box(bone, -rx * 0.72, cy - ry, cz - rz * 0.86, rx * 0.72, cy + ry, cz + rz * 0.86, sac, decals=d)

    plus(yc, zc, r, r * 0.95, r * 0.8)
    plus(yc - 0.55 * r, zc - 0.1 * r, r * 0.86, r * 0.7, r * 0.75)
    M.box(bone, -0.6 * r, yc - 0.6 * r, zc - 1.02 * r, 0.6 * r, yc + 0.5 * r, zc - 0.6 * r, sac, decals=dec)
    return M.done()


def m_explosive_nodes(rig, p, ctx):
    """胸から全身に散った光る結節（count 個）。かさぶたの土台と暗い芯は常に、光る芯は子ボーン glow_* で
    明滅（detonate の fuse 段階なら 4 倍速）。"""
    M = _M(rig, p, ctx, "explosive_nodes")
    count = M.n(p.get("count", 6))
    g = KO._c3(p.get("glow", (255, 150, 40)))
    hz = float(p.get("pulse_hz", 1.5) or 0.0)
    fast = None
    try:
        v = S.ability_states(M.z).get("detonate.fuse")
        if v:
            fast = (int(v), hz * 4.0)
    except Exception:  # noqa: BLE001
        fast = None
    crust = M.ms("node", "tumor", base=(120, 58, 50))
    dim = M.ms("node_core", "tumor", base=KO._mul(g, 0.5))
    core = M.ms("node_glow", "glow", base=g)
    order = ["chest", "chest", "torso", "chest", "neck", "arm_r", "arm_l", "torso", "forearm_r", "forearm_l",
             "leg_r", "leg_l", "head", "shin_r", "shin_l", "chest"]
    order = [b for b in order if b in rig.bones and SEG[b] in rig.segments]
    for i in range(count):
        b = order[i % len(order)]
        seg = SEG[b]
        side = M.rng.choice(_sides_of(b))
        y = M.yspan(seg, M.rng.uniform(0.2, 0.85), 0)[0]
        q = M.pt(seg, side, M.rng.uniform(0.2, 0.8), y)
        r = M.rng.uniform(0.45, 0.68) * M.T * (1.25 if b in ("chest", "torso") else 0.9)
        sp = M.rng.uniform(-25, 25)
        M.lump(b, q, side, r, r * 0.7, crust, k=2, spin=sp)
        M.fbox(b, q, side, r * 0.5, r * 0.5, 0.0, r * 0.9, dim, spin=sp)
        gb = M.glow_bone(b, hz, fast=fast)
        M.fbox(gb, q, side, r * 0.56, r * 0.56, 0.0, r * 0.98, core, uv=M.U["fine"], spin=sp)
    return M.done()


def m_bone_spurs(rig, p, ctx):
    """皮膚を突き破って伸びた骨の棘（on のボーンに count 本、長さ length 単位）。頭なら額の両側の角。"""
    M = _M(rig, p, ctx, "bone_spurs")
    on = _valid_on(M, p.get("on", ["forearm_r"]))
    count = M.n(p.get("count", 2))
    length = float(p.get("length", 2.0))
    bone_st = M.bs("bone")
    ring = M.ms("spur_wound", "flesh", wet=0.9)
    for b in on:
        seg = SEG[b]
        if b == "head":
            Hd = M.head()
            o = min(M.outer("head"), 0.6)
            for i in range(count):
                sx = (-1, 1)[i % 2]
                row = i // 2
                base = np.array([Hd.cx + sx * Hd.w * 0.27, Hd.top + o - 0.25 - row * 0.45, Hd.z0 + Hd.d * (0.22 + 0.22 * row)])
                M.spike("head", base, (sx * 0.45, 1.0, -0.4), length * M.T * 0.9, 0.48 * M.T, bone_st, segs=3,
                        bend=(sx * 0.04, -0.08, -0.2))
                M.fbox("head", base + np.array([0.0, 0.2, 0.0]), "u", 0.3 * M.T, 0.3 * M.T, -0.06, 0.1, ring)
            continue
        sides = {"chest": ["s", "e", "w", "s"], "torso": ["s", "e", "w"], "neck": ["s", "e", "w"],
                 "pelvis": ["s", "e", "w"]}.get(b)
        if sides is None:
            sides = [_outward(b), "s", _outward(b), "n"]
        for i in range(count):
            side = sides[i % len(sides)]
            y = M.yspan(seg, M.rng.uniform(0.25, 0.85), 0)[0]
            q = M.pt(seg, side, M.rng.uniform(0.25, 0.75), y, out=-0.15)
            nv = np.array(NRM[side])
            back = 0.0 if side == "s" else 0.35
            d = _unit(nv + np.array([M.rng.uniform(-0.2, 0.2), M.rng.uniform(0.25, 0.7), back + M.rng.uniform(-0.2, 0.2)]))
            ln = length * M.T * M.rng.uniform(0.75, 1.2)
            M.spike(b, q, d, ln, (0.4 + 0.08 * length) * M.T, bone_st, segs=3, bend=(0.0, 0.06, 0.04))
            M.fbox(b, q + nv * 0.15, side, 0.3 * M.T, 0.3 * M.T, -0.02, 0.1, ring)
    return M.done()


def m_spine_ridge(rig, p, ctx):
    """背骨に沿って並ぶ骨の棘（首の付け根から腰まで count 本。背びれのように平たく、上背が一番長い）。"""
    M = _M(rig, p, ctx, "spine_ridge")
    count = max(2, M.n(p.get("count", 8)))
    length = float(p.get("length", 2.0))
    L = M.L
    ytop = L.chin - 0.12 * L.H
    ybot = L.abdomen_bot + 0.15 * (L.chest_bot - L.abdomen_bot)
    bone_st = M.bs("bone")
    for i in range(count):
        t = i / (count - 1)
        y = ytop + (ybot - ytop) * t
        if y > L.shoulder_y:
            bone, seg = "neck", "neck"
        elif y >= L.chest_bot:
            bone, seg = "chest", "chest"
        else:
            bone, seg = "torso", "abdomen"
        z1 = M.sring(seg, y)[3]
        k = 0.55 + 0.45 * math.sin(math.pi * (0.15 + 0.85 * t))
        base = np.array([0.0, y, z1 - 0.12])
        M.spike(bone, base, (0.0, 0.55, 1.0), length * 1.05 * M.T * k, (0.3 + 0.07 * length) * M.T * k, bone_st,
                segs=3, bend=(0.0, -0.05, 0.05), aspect=(0.5, 1.0))
        M.fbox(bone, np.array([0.0, y, z1]), "s", 0.3 * M.T * k, 0.3 * M.T * k, -0.05, 0.13, M.skin_st(bone, "skin_dark"))
    return M.done()


def m_claws(rig, p, ctx):
    """伸びて黒ずんだ爪（指先の爪から手のひら側へ曲がる 2 節の鉤爪）。length 1..4、hands。"""
    M = _M(rig, p, ctx, "claws")
    length = _lv(p.get("length", 1), 1, 4)
    col = KO._c3(p.get("color", (60, 44, 36)))
    st = M.ms("claw", "nail", base=col, blood=0.4)
    Lc = (0.35 + 0.38 * length) * M.T
    for s in _sides(p.get("hands", "both")):
        hand = f"hand_{s}"
        hb = rig.bones.get(hand)
        if hb is None:
            continue
        inward = 1.0 if s == "r" else -1.0
        nails = [c for c in hb.cubes if getattr(c, "nr_role", None) == "nail" and not getattr(c, "nr_kit", None)]
        if nails:
            for c in nails:
                Mx = R.cube_matrix(c)
                o = np.array(c.origin, float)
                sz = np.array(c.size, float)
                lo = (Mx @ np.array([*(o + np.array([sz[0] / 2, 0.0, sz[2] / 2])), 1.0]))[:3]
                hi = (Mx @ np.array([*(o + np.array([sz[0] / 2, sz[1], sz[2] / 2])), 1.0]))[:3]
                tip, root = (lo, hi) if lo[1] < hi[1] else (hi, lo)
                d = _unit(tip - root)
                M.spike(hand, tip - d * 0.08, d, Lc, 0.22 * M.T, st, segs=2, bend=(inward * 0.3, -0.05, 0.0),
                        uv=M.U["fine"])
        else:
            hs = M.seg(hand)
            x = (hs["lo"][0] + hs["hi"][0]) / 2
            for zf in (-0.36, -0.12, 0.12, 0.36):
                base = np.array([x, hs["lo"][1] + 0.12, zf * M.L.hand_w])
                M.spike(hand, base, (inward * 0.2, -1.0, 0.0), Lc, 0.22 * M.T, st, segs=2,
                        bend=(inward * 0.3, 0.0, 0.0), uv=M.U["fine"])
    return M.done()


def m_bone_blades(rig, p, ctx):
    """前腕の骨が皮を破って伸びた刃（手首寄りの外側から下へ、手の先より長く。背にぎざぎざ）。"""
    M = _M(rig, p, ctx, "bone_blades")
    length = _lv(p.get("length", 2), 1, 4)
    col = KO._c3(p.get("color", (230, 220, 200)))
    st = M.ms("blade_bone", "bone", base=col, age=0.15, blood=0.55)
    ring = M.ms("blade_wound", "flesh", wet=0.9)
    L = M.L
    for s in _sides(p.get("hands", "both")):
        fore = f"forearm_{s}"
        if fore not in rig.bones:
            continue
        sx = -1.0 if s == "r" else 1.0
        side = "e" if s == "r" else "w"
        y = L.wrist_y + 0.38 * (L.elbow_y - L.wrist_y)
        q = M.pt(fore, side, 0.6, y, out=-0.12)
        Lb = (2.2 + 1.5 * length) * M.T
        d = _unit((sx * 0.16, -1.0, -0.2))
        cubes = M.spike(fore, q - d * 0.2, d, Lb, 1.0 * M.T, st, segs=3, bend=(0.0, 0.0, -0.1), aspect=(0.26, 1.0))
        for k in range(3):
            t = 0.25 + 0.22 * k
            a = q + d * Lb * t + np.array([0.0, 0.0, 0.42 * M.T * (1.0 - t * 0.6)])
            cubes.append(M.beam(fore, a, a + _unit((0.0, -0.6, 1.0)) * 0.42 * M.T, 0.14, 0.14, st))
        for cb in cubes:
            cb.nr_nohit = True
        M.fbox(fore, M.pt(fore, side, 0.6, y), side, 0.4 * M.T, 0.55 * M.T, -0.02, 0.1, ring)
        M.fbox(fore, M.pt(fore, side, 0.6, y + 0.65 * M.T), side, 0.38 * M.T, 0.12, 0.02, 0.18,
               M.skin_st(fore, "skin_dark"), spin=M.rng.uniform(-15, 15))
        M.drips(fore, M.pt(fore, side, 0.45, y - 0.4 * M.T), side, 1, length=(0.5, 1.2), spread=0.2)
    return M.done()


def m_tendrils(rig, p, ctx):
    """菌糸の触手（where = mouth / back / arms、count 本、長さ length ブロック）。根元の子ボーン
    tendrils_<where> を揺らせる。S 字に曲がりながら先へ細く、色が淡くなる。"""
    M = _M(rig, p, ctx, "tendrils")
    where = p.get("where", "mouth")
    count = M.n(p.get("count", 4))
    reach = float(p.get("length", 1.0)) * 16.0 * 0.5
    st = M.ms("tendril", "fungus", base=(176, 150, 120), alt=(214, 196, 166))
    tip = M.ms("tendril_tip", "fungus", base=(206, 178, 156), alt=(240, 222, 204))
    L = M.L
    H, w, d, c = L.H, L.head_w, L.head_d, L.chin
    rng = M.rng
    roots = []
    if where == "mouth":
        bone = M.child_bone("tendrils_mouth", pivot=(0.0, c + 0.2 * H, -0.45 * d))
        for i in range(count):
            x = (i / max(1, count - 1) - 0.5) * 0.36 * w
            r0 = np.array([x, c + 0.17 * H + rng.uniform(-0.1, 0.1), -0.5 * d])
            roots.append((bone, r0, np.array([x * 0.4, -0.7, -0.7]), np.array([0.0, -1.0, -0.15]), 0.4, 0.55))
    elif where == "back":
        ch = L.chest_top - L.chest_bot
        zb = M.sring("chest", L.chest_bot + 0.6 * ch)[3]
        bone = M.child_bone("tendrils_back", pivot=(0.0, L.chest_bot + 0.6 * ch, zb))
        for i in range(count):
            sx = (-1, 1)[i % 2]
            y = L.chest_bot + ch * rng.uniform(0.35, 0.9)
            r0 = np.array([sx * rng.uniform(0.1, 0.38) * L.chest_w, y, zb - 0.1])
            roots.append((bone, r0, np.array([sx * 0.55, 0.75, 0.8]), np.array([sx * 0.3, -0.25, 1.0]), 0.62, 0.3))
    else:
        for s in ("r", "l"):
            fore = f"forearm_{s}"
            if fore not in rig.bones:
                continue
            sx = -1.0 if s == "r" else 1.0
            bone = M.child_bone(f"tendrils_arm_{s}", pivot=(sx * L.arm_x, L.wrist_y + 0.5, 0.0))
            for i in range(max(1, count // 2)):
                y = L.wrist_y + (L.elbow_y - L.wrist_y) * rng.uniform(0.15, 0.6)
                r0 = M.pt(fore, "e" if s == "r" else "w", rng.uniform(0.3, 0.8), y)
                roots.append((bone, r0, np.array([sx * 0.8, -0.6, 0.2]), np.array([sx * 0.2, -1.0, 0.0]), 0.4, 0.45))
    for bone, r0, d0, grav, w0, pull in roots:
        dirs = _curl_dirs(rng, d0, grav, 6, curl=rng.uniform(22, 38), pull=pull)
        cubes, end = M.chain(bone, r0, dirs, reach * rng.uniform(0.65, 1.0), w0 * M.T, 0.12 * M.T, st)
        cubes[-1].style = tip
        cubes[-2].style = tip
        for cb in cubes:
            cb.nr_nohit = True
    return M.done()


def m_surgical_ports(rig, p, ctx):
    """体に埋め込まれた点滴のポート（テープ・本体・金属の口）と、千切れて垂れた管（tubes 本）。"""
    M = _M(rig, p, ctx, "surgical_ports")
    on = _valid_on(M, p.get("on", ["chest"]))
    if not on:
        return M.done()
    tubes = M.n(p.get("tubes", 4), lo=0)
    plast = M.ms("port", "plastic", base=(214, 216, 210))
    metal = M.ms("port_metal", "chrome")
    tape = M.ms("tape", "cloth", base=(220, 214, 196), pattern="plain", folds=0.2, blood=0.3, dirt=0.4)
    tube = M.ms("tube", "plastic", base=(190, 202, 196), blood=0.5)
    ports = []
    for b in on:
        seg = SEG[b]
        side = {"chest": "n", "torso": "n", "neck": M.rng.choice(("e", "w")), "head": "e"}.get(b, _outward(b))
        y = M.yspan(seg, M.rng.uniform(0.4, 0.75), 0)[0]
        q = M.pt(seg, side, M.rng.uniform(0.3, 0.7), y)
        nv = np.array(NRM[side])
        M.fbox(b, q, side, 0.42 * M.T, 0.42 * M.T, -0.02, 0.09, tape, spin=M.rng.uniform(-30, 30))
        M.fbox(b, q, side, 0.26 * M.T, 0.26 * M.T, 0.05, 0.24 * M.T, plast)
        M.fbox(b, q, side, 0.12 * M.T, 0.12 * M.T, 0.15, 0.44 * M.T, metal, uv=M.U["fine"])
        ports.append((b, q + nv * 0.42 * M.T, nv))
    for i in range(tubes):
        b, a0, nv = ports[i % len(ports)]
        dirs = [nv * 0.7 + np.array([M.rng.uniform(-0.3, 0.3), -0.4, 0.0]), np.array([0.0, -1.0, 0.0]) + nv * 0.25,
                np.array([M.rng.uniform(-0.3, 0.3), -1.0, M.rng.uniform(-0.3, 0.3)])]
        cubes, end = M.chain(b, a0, dirs, M.rng.uniform(1.2, 2.6) * M.T, 0.15, 0.13, tube, uv=M.U["fine"])
        cubes.append(M.cbox(b, tuple(end), (0.2, 0.2, 0.2), M.bs("blood"), uv=M.U["fine"]))
        cubes[-1].nr_mut = M.key
        for cb in cubes:
            cb.nr_nohit = True
    return M.done()


# ===========================================================================
#  体の形（膨れた腹・肥大した筋肉・長い手足・骨と金属の装甲・融合した体）
# ===========================================================================
def _derive_from(M: _M, hint: str, name: str, **kw) -> str:
    d = copy.deepcopy(M.book.get(name) or {"mat": "skin"})
    d.update(kw)
    st = M.ctx.style("m_" + hint, d)
    M.styles[st] = d
    return st


def m_bloated_belly(rig, p, ctx):
    """ガスで膨れた腹（入れ子の十字の箱で丸いドーム、脇の張り出し、へそ）。veins で浮いた血管、
    stretch_marks で裂けかけの線。服の殻の外へはみ出す。"""
    M = _M(rig, p, ctx, "bloated_belly")
    size = _lv(p.get("size", 2))
    L = M.L
    ab, cb = L.abdomen_bot, L.chest_bot
    h = cb - ab
    x0, z0, x1, z1 = M.sring("abdomen", ab + 0.5 * h)
    ww = x1 - x0
    zf = z0
    kw = dict(wet=0.45, exposed=0.0, blood=0.05, lesions=0.03)
    if p.get("veins", True):
        kw.update(veins=1.5, vein=(86, 40, 96))
    st = _derive_from(M, "belly", M.skin_st("torso"), **kw)
    p1 = (0.45 + 0.5 * size) * M.T
    W = 0.5 * ww * (1 + 0.1 * size)
    Hh = 0.52 * h * (1 + 0.06 * size)
    yc = ab + 0.46 * h
    marks = [dict(name="stripe", orient="d", count=3 + size, width=0.03, gap=0.1, colour=(186, 124, 136), wear=0.4)] \
        if p.get("stretch_marks", True) else None
    layers = ((1.0, 1.0, -0.6, p1), (0.84, 0.86, -0.2, p1 * 1.7), (0.6, 0.62, p1, p1 * 2.25),
              (0.32, 0.34, p1 * 1.8, p1 * 2.5))
    for i, (fw, fh, za, zb) in enumerate(layers):
        dec = {"north": marks, "east": marks, "west": marks} if (marks and i == 1) else None
        M.box("torso", -W * fw, yc - Hh * fh * 0.72, zf - zb, W * fw, yc + Hh * fh * 0.72, zf - za, st, decals=dec)
        M.box("torso", -W * fw * 0.72, yc - Hh * fh, zf - zb, W * fw * 0.72, yc + Hh * fh, zf - za, st)
    for sx in (-1, 1):
        xa = sx * 0.46 * ww
        M.box("torso", xa, ab + 0.12 * h, zf - p1 * 0.6, xa + sx * (0.3 + 0.3 * size) * M.T, cb - 0.12 * h,
              z1 - 0.3 * (z1 - z0), st)
    yn = yc - 0.15 * Hh
    zn = zf - p1 * 2.5
    M.box("torso", -0.14 * M.T, yn - 0.17 * M.T, zn - 0.06, 0.14 * M.T, yn + 0.15 * M.T, zn + 0.1,
          M.skin_st("torso", "skin_dark"), uv=M.U["fine"])
    return M.done()


def m_muscle_mass(rig, p, ctx):
    """片側だけ異常に肥大した筋肉（factor 倍）。arm_* なら肩・力こぶ・三頭筋・前腕・拳、chest なら胸筋・
    僧帽筋・広背筋、neck なら猪首と肩へ盛り上がる僧帽筋。張った皮に血管、裂け目から筋。"""
    M = _M(rig, p, ctx, "muscle_mass")
    b = p.get("on", "arm_r")
    f = max(1.0, float(p.get("factor", 1.3)))
    k = 1.0 + (f - 1.0) * 1.25              # 腕の太さ（体の箱）に対する倍率
    L = M.L
    fiber = M.ms("muscle", "flesh", wet=0.6)
    if b in rig.bones:
        M.restyle([b], {"veins": 1.4, "vein": (82, 58, 84)})
    if b.startswith("arm_") and b in rig.bones:
        s = b[-1]
        sx = -1.0 if s == "r" else 1.0
        fore, hand = f"forearm_{s}", f"hand_{s}"
        ax, at = sx * L.arm_x, L.arm_t
        sk = M.skin_st(b)
        sy, ey, wy = L.shoulder_y, L.elbow_y, L.wrist_y
        mid = (sy + ey) / 2
        M.box(b, ax - 0.66 * at * k, sy - 1.45 * at, -0.64 * at * k, ax + 0.66 * at * k, sy + 0.18 * at * k,
              0.62 * at * k, sk)
        M.box(b, ax - 0.55 * at * k, ey + 0.4 * at, -0.76 * at * k, ax + 0.55 * at * k, mid + 0.55 * at, 0.0, sk)
        M.box(b, ax - 0.55 * at * k, ey + 0.6 * at, 0.0, ax + 0.55 * at * k, sy - 0.9 * at, 0.72 * at * k, sk)
        M.box(b, ax - 0.2 * at * k, mid - 0.45 * at, -0.82 * at * k, ax + 0.18 * at * k, mid + 0.3 * at,
              -0.62 * at * k, fiber)
        ft, fl = L.fore_t, ey - wy
        skf = M.skin_st(fore) if fore in rig.bones else sk
        if fore in rig.bones:
            M.box(fore, ax - 0.62 * ft * k, ey - 0.55 * fl, -0.62 * ft * k, ax + 0.62 * ft * k, ey + 0.05 * fl,
                  0.6 * ft * k, skf)
            M.box(fore, ax - 0.46 * ft * k, wy + 0.08 * fl, -0.5 * ft * k, ax + 0.46 * ft * k, ey - 0.5 * fl,
                  0.5 * ft * k, skf)
        if hand in rig.bones:
            hs = M.seg(hand)
            cx = (hs["lo"][0] + hs["hi"][0]) / 2
            M.box(hand, cx - 0.5 * L.hand_th * k - 0.05, wy - L.palm_l * 0.95, -0.55 * L.hand_w * min(k, 1.5),
                  cx + 0.5 * L.hand_th * k + 0.05, wy - 0.05, 0.55 * L.hand_w * min(k, 1.5), M.skin_st(hand))
    elif b == "chest":
        cw, cd = L.chest_w, L.chest_d
        ct, cbt = L.chest_top, L.chest_bot
        ch = ct - cbt
        kk = (f - 1.0) * 2.0
        sk = M.skin_st("chest")
        for sx in (-1, 1):
            M.box("chest", sx * 0.03 * cw, ct - 0.62 * ch, -cd / 2 - (0.45 + 1.4 * kk) * M.T, sx * 0.52 * cw * (1 + 0.4 * kk),
                  ct - 0.08 * ch, -cd / 2 + 0.6, sk)
            M.box("chest", sx * 0.1 * cw, ct - 0.12 * ch, -0.22 * cd, sx * 0.5 * cw, ct + (0.35 + 0.9 * kk) * M.T,
                  0.4 * cd, sk)
            M.box("chest", sx * 0.48 * cw, cbt + 0.25 * ch, -0.3 * cd, sx * (0.5 * cw + (0.25 + 0.5 * kk) * M.T),
                  ct - 0.2 * ch, 0.4 * cd, sk)
        M.box("chest", -0.42 * cw, ct - 0.5 * ch, cd / 2 - 0.3, 0.42 * cw, ct + 0.1, cd / 2 + (0.3 + kk) * M.T, sk)
        M.box("chest", 0.12 * cw, ct - 0.45 * ch, -cd / 2 - (0.3 + 0.9 * kk) * M.T - 0.04, 0.32 * cw, ct - 0.25 * ch,
              -cd / 2 - (0.2 + 0.9 * kk) * M.T, fiber)
    elif b == "neck":
        nw, nd = L.neck_w, L.neck_d
        kk = (f - 1.0) * 2.0
        sk = M.skin_st("neck")
        M.box("neck", -0.5 * nw * (1 + 1.5 * kk), L.shoulder_y - 0.1, L.neck_z - 0.5 * nd * (1 + 0.9 * kk),
              0.5 * nw * (1 + 1.5 * kk), L.chin - 0.05, L.neck_z + 0.5 * nd * (1 + 1.6 * kk), sk)
        for sx in (-1, 1):
            x0 = sx * 0.3 * nw
            M.box("neck", x0, L.shoulder_y - 0.3, -0.2 * L.chest_d, sx * 0.5 * L.chest_w,
                  L.shoulder_y + (0.6 + 1.3 * kk) * M.T, 0.42 * L.chest_d, sk, rot=(0, 0, sx * 16),
                  pivot=(x0, L.shoulder_y + 0.4, 0))
    elif b in rig.bones and SEG.get(b) in rig.segments:
        seg = SEG[b]
        sg = M.seg(seg)
        cx, cz = sg["centre"][0], sg["centre"][2]
        r = max(sg["size"][0], sg["size"][2]) / 2 * k
        y0, y1 = M.yspan(seg, 0.2, 0.85)
        M.box(b, cx - r, y0, cz - r, cx + r, y1, cz + r * 0.9, M.skin_st(b))
    return M.done()


def m_elongated_limbs(rig, p, ctx):
    """異様に長い手足（腕の長さは骨格の arm_len が持つ）: 尖った肘・指先にもう一節（爪も先へ）、
    extra_joint で前腕の途中の関節の瘤、legs > 1 で尖った膝と長い足指。"""
    M = _M(rig, p, ctx, "elongated_limbs")
    arms = float(p.get("arms", 1.3))
    legs = float(p.get("legs", 1.0))
    xj = bool(p.get("extra_joint", False))
    L = M.L
    bone_st = M.bs("bone")
    for s in ("r", "l"):
        sx = -1.0 if s == "r" else 1.0
        arm, fore, hand = f"arm_{s}", f"forearm_{s}", f"hand_{s}"
        ax = sx * L.arm_x
        if arms > 1.0 and arm in rig.bones:
            at = L.arm_t
            M.box(arm, ax - 0.26 * at, L.elbow_y - 0.25 * at, 0.35 * at, ax + 0.26 * at, L.elbow_y + 0.3 * at,
                  0.82 * at, M.skin_st(arm, "skin_dark"))
            parts = KO._hand_cubes(M, s)
            hb = rig.bones.get(hand)
            ext = L.finger_l * 0.5 * (arms - 1.0) * 2.2
            nails = [c for c in (hb.cubes if hb else []) if getattr(c, "nr_role", None) == "nail"
                     and not getattr(c, "nr_kit", None)]
            for c in parts["dist"]:
                Mx = R.cube_matrix(c)
                d = -_unit(Mx[:3, :3] @ np.array([0.0, 1.0, 0.0]))
                tip = np.array(c.pivot if c.pivot else c.origin, float)
                M.beam(hand, tip - d * 0.04, tip + d * ext, c.size[0] * 0.84, c.size[2] * 0.84, M.skin_st(hand),
                       uv=M.U["hand"])
                if nails:
                    zc = tip[2]
                    nail = min(nails, key=lambda n_: abs((n_.origin[2] + n_.size[2] / 2) - zc))
                    sh = d * ext
                    nail.origin = [nail.origin[i] + sh[i] for i in range(3)]
                    if nail.pivot:
                        nail.pivot = [nail.pivot[i] + sh[i] for i in range(3)]
                    nails.remove(nail)
        if xj and fore in rig.bones:
            yj = (L.elbow_y + L.wrist_y) / 2
            ft = L.fore_t
            M.box(fore, ax - 0.56 * ft, yj - 0.22 * ft, -0.52 * ft, ax + 0.56 * ft, yj + 0.24 * ft, 0.6 * ft,
                  M.skin_st(fore, "skin_dark"))
            M.box(fore, ax - 0.2 * ft, yj - 0.16 * ft, 0.5 * ft, ax + 0.2 * ft, yj + 0.26 * ft, 0.92 * ft, bone_st)
            M.fbox(fore, M.pt(fore, "n", 0.5, yj - 0.45 * ft), "n", 0.3 * ft, 0.2 * ft, -0.02, 0.08, M.bs("flesh"))
        if legs > 1.0 and f"shin_{s}" in rig.bones:
            kx, kt = sx * L.knee_x, L.knee_t
            M.box(f"shin_{s}", kx - 0.3 * kt, L.knee_y - 0.28 * kt, -0.5 * kt - (0.25 + 0.6 * (legs - 1.0)) * M.T,
                  kx + 0.3 * kt, L.knee_y + 0.32 * kt, -0.3 * kt, M.skin_st(f"shin_{s}", "skin_dark"))
            fs = M.seg(f"foot_{s}")
            fx = (fs["lo"][0] + fs["hi"][0]) / 2
            ext = (0.6 + 2.2 * (legs - 1.0)) * M.T
            M.box(f"foot_{s}", fx - 0.36 * L.foot_w, 0.0, fs["lo"][2] - ext, fx + 0.36 * L.foot_w, 0.016 * L.t,
                  fs["lo"][2] + 0.25, M.skin_st(f"foot_{s}"))
    return M.done()


def m_bone_plates(rig, p, ctx):
    """骨が板状に盛り上がった天然の装甲（頭は兜と庇・鶏冠、胸は胸板と鎖骨の板、肩は重なる肩当て、
    前腕は籠手、腹は帯）。thickness 1..3。gore.armored の部位なら armor_*（nr:armor で剥がれる）。"""
    M = _M(rig, p, ctx, "bone_plates")
    on = _valid_on(M, p.get("on", ["head"]))
    tl = _lv(p.get("thickness", 1))
    col = KO._c3(p.get("color", (220, 210, 190)))
    st = M.ms("bone_plate", "bone", base=KO._mul(col, 0.94), age=0.45 + 0.1 * tl, blood=0.3)
    st2 = M.ms("bone_plate_dark", "bone", base=KO._mix(col, (120, 96, 70), 0.4), age=0.9, blood=0.3)
    th = (0.3 + 0.2 * tl) * M.T
    cr = dict(name="cracks", amount=0.5)
    L = M.L
    for b in on:
        ab = M.armor_bone(b)
        seg = SEG[b]
        if b == "head":
            Hd = M.head()
            o = min(M.outer("head"), 0.6) + 0.04
            hh = Hd.top - Hd.low
            M.fbox(ab, (Hd.cx, Hd.top + o, Hd.cz), "u", Hd.w / 2 + 0.1, Hd.d / 2 + 0.06, -0.05, th, st,
                   decals={"up": cr})
            M.box(ab, Hd.x0 - o - 0.06, Hd.brow - 0.08, Hd.z0 - o - th - 0.22 * tl * M.T, Hd.x1 + o + 0.06,
                  Hd.brow + 0.55 * M.T, Hd.z0 - o + 0.6, st)
            for sx in (-1, 1):
                xs = (Hd.x1 if sx > 0 else Hd.x0) + sx * o
                M.fbox(ab, (xs, Hd.top - 0.32 * hh, Hd.cz + 0.1), "w" if sx > 0 else "e", Hd.d * 0.45, hh * 0.3,
                       -0.05, th * 0.9, st2, spin=sx * 6)
            M.fbox(ab, (Hd.cx, Hd.top - 0.4 * hh, Hd.z1 + o), "s", Hd.w * 0.45, hh * 0.35, -0.05, th * 0.9, st2)
            if tl >= 2:
                M.fbox(ab, (Hd.cx, Hd.top + o + th, Hd.cz + 0.1), "u", 0.22 * M.T, Hd.d * 0.48, -0.02,
                       (0.25 + 0.22 * tl) * M.T, st)
            if tl >= 3:
                for sx in (-1, 1):
                    xs = (Hd.x1 if sx > 0 else Hd.x0) + sx * (o + th * 0.5)
                    M.fbox(ab, (xs, Hd.eye - 0.45, Hd.z0 + Hd.d * 0.22), "w" if sx > 0 else "e", 0.62 * M.T,
                           0.5 * M.T, -0.05, th * 0.75, st2, spin=-sx * 10)
        elif b == "chest":
            ct, cbt = L.chest_top, L.chest_bot
            ch = ct - cbt
            x0, z0, x1, z1 = M.sring("chest", ct - 0.35 * ch)
            for sx in (-1, 1):
                M.fbox(ab, M.pt("chest", "n", 0.5 + sx * 0.24, ct - 0.35 * ch), "n", 0.24 * (x1 - x0), 0.25 * ch,
                       -0.05, th, st, spin=sx * 4, decals={"north": cr} if sx > 0 else None)
                M.fbox(ab, np.array([sx * 0.3 * L.chest_w, ct + M.outer("chest"), 0.0]), "u", 0.2 * L.chest_w,
                       0.3 * L.chest_d, -0.05, th, st)
            M.fbox(ab, M.pt("chest", "n", 0.5, ct - 0.45 * ch), "n", 0.08 * L.chest_w, 0.32 * ch, -0.02, th * 1.4,
                   st2)
            if tl >= 2:
                for sx in (-1, 1):
                    M.fbox(ab, M.pt("chest", "s", 0.5 + sx * 0.22, ct - 0.4 * ch), "s", 0.2 * (x1 - x0), 0.3 * ch,
                           -0.05, th, st2)
            if tl >= 3:
                M.fbox(ab, M.pt("chest", "n", 0.5, cbt + 0.18 * ch), "n", 0.34 * (x1 - x0), 0.12 * ch, -0.05,
                       th * 0.8, st2)
        elif b.startswith("arm_"):
            s = b[-1]
            sx = -1.0 if s == "r" else 1.0
            side = _outward(b)
            at = L.arm_t
            ax = sx * L.arm_x
            o = M.outer(seg)
            M.fbox(ab, np.array([ax + sx * 0.05 * at, L.shoulder_y + 0.08 * at + o, 0.0]), "u", 0.68 * at,
                   0.66 * at, -0.05, th, st, decals={"up": cr})
            for k in range(1 + tl):
                y = L.shoulder_y - (0.35 + 0.5 * k) * at
                M.fbox(ab, M.pt(seg, side, 0.5, y), side, 0.66 * at - 0.06 * k, 0.32 * at, -0.05,
                       th * (1.1 - 0.12 * k), st if k % 2 == 0 else st2, spin=sx * (8 + 4 * k))
        elif b.startswith("forearm_"):
            side = _outward(b)
            for k in range(2):
                y = M.yspan(seg, 0.3 + 0.38 * k, 0)[0]
                M.fbox(ab, M.pt(seg, side, 0.5, y), side, 0.5 * L.fore_t, 0.2 * (L.elbow_y - L.wrist_y), -0.05, th,
                       st if k == 0 else st2)
        elif b == "torso":
            for k in range(3):
                y = M.yspan("abdomen", 0.2 + 0.28 * k, 0)[0]
                x0, z0, x1, z1 = M.sring("abdomen", y)
                M.fbox(ab, M.pt("abdomen", "n", 0.5, y), "n", 0.42 * (x1 - x0), 0.12 * (L.chest_bot - L.abdomen_bot),
                       -0.05, th, st if k % 2 == 0 else st2)
        else:
            side = "n" if b.startswith(("leg_", "shin_", "neck", "pelvis")) else _outward(b)
            for k in range(2):
                y = M.yspan(seg, 0.3 + 0.38 * k, 0)[0]
                x0, z0, x1, z1 = M.sring(seg, y)
                M.fbox(ab, M.pt(seg, side, 0.5, y), side, 0.4 * max(x1 - x0, z1 - z0),
                       0.18 * (M.seg(seg)["size"][1]), -0.05, th, st if k == 0 else st2)
    return M.done()


def m_metal_fused(rig, p, ctx):
    """肉に食い込んで一体化した金属（plate = ボルト留めの錆びた板、rebar = 貫いた鉄筋、chain = 巻き付いた鎖）。
    gore.armored の部位なら armor_*。"""
    M = _M(rig, p, ctx, "metal_fused")
    on = _valid_on(M, p.get("on", ["forearm_r"]))
    kind = p.get("kind", "plate")
    rust = M.ms("fused_plate", "rust", amount=0.75)
    steel = M.ms("fused_steel", "metal", base=(118, 122, 128), scratches=0.7, blood=0.35)
    bolt = M.ms("bolt", "metal", base=(164, 164, 170), scratches=0.4)
    rebar = M.ms("fused_rebar", "rust", amount=0.95)
    raw = M.ms("fused_wound", "flesh", wet=0.85)
    for b in on:
        ab = M.armor_bone(b)
        seg = SEG[b]
        sg = M.seg(seg)
        y0, y1 = sg["lo"][1], sg["hi"][1]
        if kind == "plate":
            if b == "chest":
                spots = [("n", 0.28), ("n", 0.72), ("s", 0.5)]
            elif b == "torso":
                spots = [("n", 0.5)]
            elif b == "head":
                spots = [(M.rng.choice(("e", "w")), 0.5)]
            else:
                spots = [(_outward(b), 0.5), ("n", 0.5)]
            for i, (side, a) in enumerate(spots):
                y = y0 + (y1 - y0) * M.rng.uniform(0.38, 0.62)
                x0, z0, x1, z1 = M.sring(seg, y)
                face_w = (x1 - x0) if side in "ns" else (z1 - z0)
                hw = face_w * (0.26 if b == "chest" else 0.42)
                hh = (y1 - y0) * (0.22 if b in ("chest", "torso") else 0.3)
                q = M.pt(seg, side, a, y)
                M.fbox(ab, q, side, hw, hh, -0.08, 0.16 * M.T + 0.06, rust if i % 2 == 0 else steel,
                       spin=M.rng.uniform(-8, 8))
                M.fbox(ab, q - np.array([0.0, hh + 0.05, 0.0]), side, hw * 0.9, 0.1, -0.04, 0.1, raw)
                nb = 2 + int(hw > 0.8)
                for kb in range(nb):
                    u = (kb + 0.5) / nb * 2 - 1
                    nv = np.array(NRM[side])
                    ax = int(np.argmax(np.abs(nv)))
                    hor = 0 if ax != 0 else 2
                    qq = q.copy()
                    qq[hor] += u * hw * 0.7
                    qq[1] += hh * 0.6 * (1 if kb % 2 else -1)
                    M.fbox(ab, qq, side, 0.11, 0.11, 0.12, 0.16 * M.T + 0.2, bolt, uv=M.U["fine"])
        elif kind == "rebar":
            for i in range(2):
                ya = y0 + (y1 - y0) * M.rng.uniform(0.2, 0.45)
                yb = ya + (y1 - y0) * M.rng.uniform(0.2, 0.4)
                sa = "n" if i == 0 else _outward(b) if b not in ("chest", "torso", "neck", "head") else "e"
                pa = M.pt(seg, sa, M.rng.uniform(0.3, 0.7), ya, out=0.8 * M.T)
                pb = M.pt(seg, "s", M.rng.uniform(0.3, 0.7), yb, out=0.9 * M.T)
                M.beam(ab, pa, pb, 0.32 * M.T, 0.32 * M.T, rebar)
                M.fbox(ab, M.pt(seg, sa, 0.5, ya), sa, 0.25 * M.T, 0.22 * M.T, -0.02, 0.08, raw)
        else:
            for k in range(2):
                y = y0 + (y1 - y0) * (0.35 + 0.3 * k)
                x0, z0, x1, z1 = M.sring(seg, y)
                cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
                rx, rz = (x1 - x0) / 2 + 0.14, (z1 - z0) / 2 + 0.14
                n = 8
                for i in range(n):
                    a = 2 * math.pi * i / n
                    c = (cx + math.cos(a) * rx, y + 0.12 * math.sin(3 * a), cz + math.sin(a) * rz)
                    sz = (0.55, 0.28, 0.22) if i % 2 == 0 else (0.22, 0.28, 0.55)
                    if abs(math.cos(a)) > 0.7:
                        sz = (sz[2], sz[1], sz[0])
                    M.cbox(ab, c, sz, rebar, uv=M.U["fine"])
            KO._chain(M, ab, (x0 - 0.1, y - 0.2, cz), 3, rebar, drift=(-0.2, -1.0, 0.1), link=0.5)
    return M.done()


def _face_dict(top: float, bot: float, chin: float, H: float, **kw) -> dict:
    """余分な頭の顔板（生え際〜上唇）の顔デカール（nr_rig と同じ位置の決め方）。"""
    fh = top - bot

    def v_of(y):
        return round((top - y) / fh, 3)

    d = dict(name="face", region="upper", eyes="clouded", mouth="gaping", decay=3, gore=0.7, nose=True,
             eye_v=v_of(chin + 0.52 * H), eye_gap=0.25, brow_v=v_of(chin + 0.615 * H), nose_v=v_of(chin + 0.36 * H),
             mouth_v=v_of(chin + 0.225 * H))
    d.update(kw)
    return d


def _extra_head(M: _M, bone: str, base, H: float, w: float, d: float, rot, eyes: str, mouth: str,
                hair: bool, sk: str) -> list:
    """融合した余分な頭（首の切れ端・頭蓋・顔板・顎）。base は首の付け根、rot はその回り。"""
    bx, by, bz = (float(v) for v in base)
    c = by + 0.35 * H                       # 顎先の高さ
    piv = (bx, by, bz)
    out = []

    def bx_(x0, y0, z0, x1, y1, z1, st, uv=None, decals=None):
        out.append(M.box(bone, bx + x0, y0, bz + z0, bx + x1, y1, bz + z1, st, uv, decals, rot, piv))

    bx_(-0.3 * w, by - 0.2, -0.28 * d, 0.3 * w, c + 0.3 * H, 0.3 * d, sk)
    bx_(-0.5 * w, c + 0.4 * H, -0.44 * d, 0.5 * w, c + 0.95 * H, 0.5 * d, sk, M.U["head"])
    top, bot = c + 0.86 * H, c + 0.205 * H
    face = _face_dict(top, bot, c, H, eyes=eyes, mouth=mouth)
    bx_(-0.4 * w, bot, -0.5 * d, 0.4 * w, top, -0.18 * d, sk, M.U["face"], {"north": face})
    jaw = dict(name="face", region="jaw", eyes=eyes, mouth=mouth, decay=3, gore=0.8, mouth_v=-0.03)
    bx_(-0.27 * w, c - 0.02 * H, -0.5 * d, 0.27 * w, c + 0.2 * H, -0.08 * d, sk, M.U["face"], {"north": jaw})
    bx_(-0.22 * w, c + 0.15 * H, -0.47 * d, 0.22 * w, c + 0.21 * H, -0.3 * d, M.bs("teeth"), M.U["face"])
    if hair:
        bx_(-0.53 * w, c + 0.78 * H, -0.42 * d, 0.53 * w, c + 1.02 * H, 0.55 * d, M.bs("hair"), M.U["head"])
    return out


def m_fused_bodies(rig, p, ctx):
    """背中と肩から別の感染者の胴（torsos）・頭（heads、子ボーン extra_head_1..N）・腕（arms）が生える。
    犠牲者の肌は本体と違う色。土台は背中の肉の盛り上がり、継ぎ目に腫瘍の塊。"""
    M = _M(rig, p, ctx, "fused_bodies")
    nt = M.n(p.get("torsos", 2), lo=0)
    nh = max(0, min(3, int(p.get("heads", 3))))
    na = M.n(p.get("arms", 2), lo=0)
    L = M.L
    ct, cbt = L.chest_top, L.chest_bot
    ch = ct - cbt
    sk = M.skin_st("chest")
    mass = M.ms("fused_mass", "tumor", base=(178, 122, 112))
    bone_st = M.bs("bone")
    meat = M.ms("fused_cavity", "gore_wet")
    x0, z0, x1, z1 = M.sring("chest", cbt + 0.6 * ch)
    zb = z1
    cw = x1 - x0
    M.blob("chest", np.array([0.0, cbt + 0.6 * ch, zb]), "s", 0.4 * cw, 0.9 * M.T, mass, cap_style=sk, spin=0.0)
    rng = M.rng
    torso_spots = [(-0.55, 0.72, -28.0), (0.62, 0.5, 34.0), (0.05, 0.9, 6.0), (-0.3, 0.3, -12.0)]
    for i in range(nt):
        vs = _victim_skin(M, i + 1)
        fx, fy, tilt = torso_spots[i % len(torso_spots)]
        P0 = np.array([fx * 0.5 * cw, cbt + fy * ch, zb - 0.3])
        tw, th_, td = 0.42 * L.chest_w, 0.5 * ch, 0.4 * L.chest_d
        rot = (-25.0 + rng.uniform(-10, 10), rng.uniform(-20, 20), tilt)
        piv = tuple(P0)
        M.box("chest", P0[0] - tw / 2, P0[1] - th_ / 2, P0[2], P0[0] + tw / 2, P0[1] + th_ / 2, P0[2] + td, vs,
              rot=rot, pivot=piv)
        sgn = 1 if fx >= 0 else -1
        M.box("chest", P0[0] + sgn * (tw / 2 - 0.1), P0[1] + th_ / 2 - 0.55 * M.T, P0[2] + 0.1,
              P0[0] + sgn * (tw / 2 + 0.65 * M.T), P0[1] + th_ / 2, P0[2] + td * 0.8, vs, rot=rot, pivot=piv)
        M.box("chest", P0[0] - tw * 0.3, P0[1] - th_ * 0.3, P0[2] + td - 0.05, P0[0] + tw * 0.3, P0[1] + th_ * 0.3,
              P0[2] + td + 0.06, meat, uv=M.U["gore"], rot=rot, pivot=piv)
        for k in (-1, 1):
            yy = P0[1] + k * th_ * 0.14
            M.box("chest", P0[0] - tw * 0.32, yy - 0.13 * M.T, P0[2] + td, P0[0] + tw * 0.32, yy + 0.13 * M.T,
                  P0[2] + td + 0.2 * M.T, bone_st, rot=rot, pivot=piv)
    head_spots = [(-0.42 * L.chest_w, ct - 0.05, 0.05 * L.chest_d, (-12.0, -25.0, 18.0)),
                  (0.3 * L.chest_w, ct - 0.25 * ch, zb + 0.1, (-35.0, 160.0, -14.0)),
                  (-0.05 * L.chest_w, ct + 0.1, zb - 0.2, (-50.0, 185.0, 8.0))]
    eyes_pool = ["milky", "clouded", "none", "bloodshot"]
    mouths = ["gaping", "torn", "snarl"]
    for n in range(1, nh + 1):
        bx, by, bz, rot = head_spots[(n - 1) % len(head_spots)]
        rot = (rot[0] + rng.uniform(-8, 8), rot[1] + rng.uniform(-10, 10), rot[2] + rng.uniform(-8, 8))
        hb = M.child_bone(f"extra_head_{n}", pivot=(bx, by, bz))
        hs = rng.uniform(0.82, 0.98)
        _extra_head(M, hb, (bx, by, bz), L.H * hs, L.head_w * hs, L.head_d * hs, rot,
                    eyes_pool[(n - 1) % len(eyes_pool)], mouths[(n - 1) % len(mouths)], n != 3, _victim_skin(M, n - 1))
        M.lump("chest", np.array([bx, by - 0.1, bz]), "s" if bz > 0 else "u", 0.55 * M.T, 0.5 * M.T, mass, k=2)
    for i in range(na):
        vs = _victim_skin(M, i + 2)
        sx = (-1, 1)[i % 2]
        root = np.array([sx * 0.42 * L.chest_w, ct - 0.3 * ch, zb - 0.25])
        ua = L.arm_t * 0.82
        ul = (L.shoulder_y - L.elbow_y) * 0.9
        fl = (L.elbow_y - L.wrist_y) * 0.9
        u = _unit((sx * 0.6, 0.25 - 0.15 * i, -0.55))
        f = _unit((sx * 0.15, -0.85, -0.55))
        elbow = root + u * ul
        wrist = elbow + f * fl
        cubes = [M.beam("chest", root, elbow, ua, ua, vs), M.beam("chest", elbow, wrist, ua * 0.86, ua * 0.86, vs)]
        cubes.append(M.cbox("chest", tuple(wrist + f * 0.45 * M.T), (0.5 * M.T, 0.9 * M.T, 0.75 * M.T), vs))
        for k in (-1, 0, 1):
            a = wrist + f * 0.85 * M.T + np.array([0.0, 0.0, k * 0.24 * M.T])
            cubes.append(M.beam("chest", a, a + _unit(f + np.array([0.0, 0.0, -0.3])) * 0.9 * M.T, 0.18 * M.T,
                                0.18 * M.T, vs))
        for cb in cubes:
            cb.nr_nohit = True
        M.lump("chest", root, "s", 0.5 * M.T, 0.45 * M.T, mass, k=2)
    return M.done()


# ===========================================================================
#  まとめ
# ===========================================================================
def _vein_net(M: _M, b: str, style: str, target=None, n_sides: int = 2, w: float = 0.14, branches: int = 1) -> int:
    """浮き出た血管の網（表面に沿う細い梁の折れ線と枝）。素肌の部位だけ（服の上には出さない）。
    target は置くボーン（文字列か、最初の 1 本を置く時に呼ぶ関数 b -> ボーン名）。"""
    seg = SEG.get(b)
    if not seg or seg not in M.rig.segments or M.outer(seg) > 0:
        return 0
    bone = None
    k = 0
    for side in _sides_of(b)[:max(1, n_sides)]:
        y0, y1 = M.yspan(seg, 0.12, 0.92)
        nseg = 3 if (y1 - y0) > 2.5 else 2
        a = M.rng.uniform(0.25, 0.75)
        y = M.rng.uniform(y0 + (y1 - y0) * 0.55, y1)
        pts = [M.pt(seg, side, a, y, 0.03)]
        for _ in range(nseg):
            a = min(0.9, max(0.1, a + M.rng.uniform(-0.2, 0.2)))
            y = max(y0, y - M.rng.uniform(0.55, 1.05) * M.T)
            pts.append(M.pt(seg, side, a, y, 0.03))
        if bone is None:
            bone = target(b) if callable(target) else (target or b)
        for q0, q1 in zip(pts, pts[1:]):
            M.beam(bone, q0, q1, w, w * 0.75, style, uv=M.U["fine"], over=0.04)
            k += 1
        for j in range(branches):
            q0 = pts[1 + j % (len(pts) - 1)]
            a2 = min(0.92, max(0.08, a + M.rng.choice((-0.32, 0.32))))
            q1 = M.pt(seg, side, a2, q0[1] - M.rng.uniform(0.4, 0.7) * M.T, 0.03)
            M.beam(bone, q0, q1, w * 0.8, w * 0.6, style, uv=M.U["fine"], over=0.03)
            k += 1
    return k


_VICTIM_TONES = ((206, 192, 172), (168, 168, 156), (152, 162, 128), (196, 156, 124))


def _victim_skin(M: _M, i: int) -> str:
    """融合した犠牲者の肌（本体と違う色。種類の肌に埋もれないように）。"""
    b = _VICTIM_TONES[i % len(_VICTIM_TONES)]
    return M.ms(f"victim{i % len(_VICTIM_TONES)}", "skin",
                tone=dict(base=b, shadow=KO._mul(b, 0.6), highlight=KO._mix(b, (255, 250, 240), 0.25)),
                decay=2.5, blood=0.3, dirt=0.4, blood_age=0.6, decay_tint=0.35)


def _render3(model, tex, mode: str = "body"):
    """前（25°）・横（95°）・後ろ（205°）の 3 枚。mode = body / upper / head / hands（部位に寄る）。
    ゴア用ボーン（既定の状態で隠れる物）は隠す。"""
    import nr_preview as NP
    from PIL import Image
    vis = R.visible_bones(model)
    hidden = [b.name for b in model.bones if b.name not in vis]
    # 能力の段階だけ出る部品（瓦礫・叫びの光）は既定の状態では隠す
    hidden += [b for b, ts in (getattr(model, "nr_vis_terms", None) or {}).items()
               if any("nr:ability') ==" in t for t in ts)]
    rig = model.nr_rig
    L = rig.L
    W = R.bone_world(model)
    k = L.t / R.REF_T
    size = {"head": (210, 210), "upper": (210, 250), "hands": (210, 250)}.get(mode, (190, 360))
    shots = []
    for yaw in ((25.0, -65.0, 205.0) if mode == "hands" else (25.0, 95.0, 205.0)):
        if mode in ("head", "upper"):
            seg, span, dy = {"head": ("head", 10.5, 0.3), "upper": ("chest", 19.0, 0.6)}[mode]
            sg = rig.segment(seg)
            cen = W[sg["bone"]] @ np.array([*sg["centre"], 1.0])
            tgt = [float(cen[0]), float(cen[1] + dy * k), float(cen[2])]
            cam = NP.Camera(yaw=yaw, pitch=12.0 if mode == "head" else 8.0, target=tgt, scale=size[1] / (span * k))
            shots.append(NP.render(model, tex, camera=cam, size=size, hidden=hidden, bg=(40, 42, 48), ss=2))
        elif mode == "hands":
            sg = rig.segment("hand_r")
            cen = W[sg["bone"]] @ np.array([*sg["centre"], 1.0])
            cam = NP.Camera(yaw=yaw, pitch=8.0, target=[float(v) for v in cen[:3]], scale=size[1] / (9.0 * k))
            shots.append(NP.render(model, tex, camera=cam, size=size, hidden=hidden, bg=(40, 42, 48), ss=2))
        else:
            shots.append(NP.render(model, tex, view=(yaw, 6.0), size=size, hidden=hidden, bg=(40, 42, 48), ss=2))
    im = Image.new("RGB", (sum(s.size[0] for s in shots), max(s.size[1] for s in shots)), (40, 42, 48))
    x = 0
    for s in shots:
        im.paste(s.convert("RGB"), (x, 0))
        x += s.size[0]
    return im


def _curl_dirs(rng, d0, grav, n: int, curl: float = 30.0, pull: float = 0.35) -> list:
    """触手の節の向き: 最初の向き d0 から、ランダムな面の中で曲がり（curl 度、途中で向きが逆になる S 字）、
    grav の向きへ少しずつ引かれる。"""
    d = _unit(d0)
    g = _unit(grav)
    ax = _unit(np.cross(d, np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)])))
    out = []
    sgn = 1.0
    for k in range(n):
        out.append(d)
        if k == n // 2:
            sgn = -sgn if rng.random() < 0.6 else sgn
        a = math.radians(sgn * curl * rng.uniform(0.6, 1.2))
        perp = _unit(np.cross(ax, d))
        d = _unit(d * math.cos(a) + perp * math.sin(a) + g * pull)
    return out


MUTATIONS = {k[2:]: v for k, v in list(globals().items())
             if k.startswith("m_") and callable(v) and k[2:] in S.MUTATION_VOCAB}


def mutate(rig, z: dict, stylebook: dict, items: Optional[Sequence] = None, scale: float = 1.0) -> Dict[str, dict]:
    """z["mutations"]（か items）を DEPTH の順に付ける。stylebook に足した項目を返す。
    scale < 1 なら棘・腫瘍などの数を減らす（nr_kit が予算に収めるのに使う）。"""
    items = list(z.get("mutations", ()) if items is None else items)
    order = sorted(range(len(items)), key=lambda i: (DEPTH.get(items[i][0], 5.0), i))
    added: Dict[str, dict] = {}
    for i in order:
        key, over = items[i]
        ctx = MutCtx(z, key, stylebook, salt=f"/{i}", scale=scale)
        params = S.mutation_params((key, over))
        added.update(MUTATIONS[key](rig, params, ctx))
    return added


def mut_cubes(model, key: Optional[str] = None) -> int:
    """変異のキューブ数（key を渡すとその変異だけ）。"""
    return sum(1 for c in model.all_cubes()
               if getattr(c, "nr_mut", None) and (key is None or c.nr_mut == key))


# ===========================================================================
#  自己テスト
# ===========================================================================
_OUT = C.SCRATCH
_ARMORED_Z = dict(armored=["head", "torso", "arm_r", "arm_l"], armor_strip={"arm_r": 2, "arm_l": 2})


def _demo_params(key: str) -> List[Tuple[str, dict]]:
    """確認画像に並べる引数の組（既定 + 目立つ変化）。"""
    extra = {
        "exposed_ribs": [("both 6 flesh", dict(side="both", count=6, flesh=0.6))],
        "missing_cheek_teeth": [("r size3", dict(side="r", size=3))],
        "bone_spurs": [("arms chest", dict(on=["arm_r", "arm_l", "chest"], count=3, length=3.0)),
                       ("head horns", dict(on=["head"], count=2, length=3.0))],
        "tumor_cluster": [("chest 3x8", dict(on="chest", size=3, count=8))],
        "fungal_growth": [("glow", dict(on=["head", "neck", "chest"], coverage=0.6, caps=8, glow=(120, 255, 200)))],
        "bloated_belly": [("size3 shirt", dict(size=3, _outfit=[("shirt", dict(color=(200, 196, 180)))]))],
        "acid_sacs": [("cheeks", dict(where="cheeks")), ("back", dict(where="back", count=3))],
        "elongated_jaw": [("split needle 1.8", dict(length=1.8, split=True, teeth="needle")),
                          ("split tusk 2.2", dict(length=2.2, split=True, teeth="tusk"))],
        "claws": [("len4", dict(length=4, color=(24, 20, 20)))],
        "split_face": [("depth3 glow", dict(depth=3, glow=(255, 200, 60)))],
        "exposed_spine": [("12 spikes", dict(length=12, spikes=True))],
        "pustules": [("glow dense", dict(on=["torso", "chest", "arm_r", "arm_l"], density=3, color=(180, 255, 140),
                                         glow=(180, 255, 140)))],
        "veins_glowing": [("all orange", dict(on=["head", "neck", "chest", "torso", "arm_r", "arm_l"],
                                              color=(255, 140, 40), pulse_hz=2.0))],
        "dark_veins": [("dense", dict(on=["head", "neck", "chest", "arm_r", "arm_l"], density=3))],
        "stitches": [("staples", dict(on=["head", "chest"], kind="staples"))],
        "hanging_skin": [("many", dict(on=["chest", "torso", "arm_r", "arm_l"], flaps=4))],
        "impaled": [("rebar", dict(obj="rebar")), ("arrow", dict(obj="arrow", on="chest")),
                    ("glass", dict(obj="glass_shard"))],
        "throat_sac": [("size3 glow", dict(size=3, glow=(255, 80, 60)))],
        "bone_plates": [("thick3 armored", dict(on=["head", "chest", "arm_r", "arm_l", "forearm_r", "torso"],
                                                thickness=3, _z=_ARMORED_Z))],
        "elongated_limbs": [("1.6 joint legs", dict(arms=1.6, legs=1.15, extra_joint=True))],
        "charred_crust": [("ember", dict(coverage=0.95, ember=(255, 120, 30)))],
        "explosive_nodes": [("12", dict(count=12))],
        "spine_ridge": [("13 x3", dict(count=13, length=3.0))],
        "muscle_mass": [("chest", dict(on="chest", factor=1.4)), ("neck", dict(on="neck", factor=1.5))],
        "metal_fused": [("rebar", dict(on=["forearm_l", "arm_l"], kind="rebar")),
                        ("chain", dict(on=["forearm_r", "leg_l"], kind="chain")),
                        ("plate armored", dict(on=["arm_r", "forearm_r", "chest"], kind="plate", _z=_ARMORED_Z))],
        "tendrils": [("back", dict(where="back", count=8, length=2.0)), ("arms", dict(where="arms", count=4))],
    }.get(key, [])
    return [("", {})] + extra


_VIEW = {"missing_cheek_teeth": "head", "elongated_jaw": "head", "split_face": "head", "eyeless": "head",
         "missing_nose": "head", "exposed_skull": "head", "claws": "hands", "missing_fingers": "hands",
         "throat_sac": "upper", "torn_throat": "upper", "exposed_lungs": "upper", "exposed_ribs": "upper",
         "acid_sacs": "upper", "bite_wound": "upper", "surgical_ports": "upper", "stitches": "upper",
         "tumor_cluster": "upper", "dark_veins": "upper", "burn_scars": "upper", "skin_peeled": "upper",
         "pustules": "upper", "muscle_mass": "upper", "bloated_belly": "upper", "hanging_skin": "upper"}
_VIEW_LABEL = {"acid_sacs cheeks": "head", "bone_spurs head horns": "head", "tendrils back": "body",
               "tumor_cluster chest 3x8": "body", "stitches staples": "upper", "acid_sacs back": "body",
               "bite_wound forearm fresh": "body", "hanging_skin many": "body", "muscle_mass": "body",
               "bloated_belly size3 shirt": "body", "pustules glow dense": "body", "dark_veins dense": "body"}


def _mut_one(key: str, over: dict, seed: int = 7):
    over = dict(over)
    zo = over.pop("_z", {})
    outfit = over.pop("_outfit", [])
    m = R.new_model(f"kit_mut_{key}")
    rig = R.ZombieRig(m, dict(KO._STD_BUILD), detail=2, seed=seed)
    book = P.zombie_styles("pale", 2, "clouded", blood=0.08, life_tone=1)
    z = KO._std_z(key="std_mut", armored=zo.get("armored", ()))
    z["gore"]["armor_strip"] = dict(zo.get("armor_strip", {}))
    if outfit:
        KO.dress(rig, z, book, items=outfit)
    added = mutate(rig, z, book, items=[(key, over)])
    return m, rig, book, added


def _selftest(render: bool = True, only: Optional[Sequence[str]] = None, zombies: bool = True) -> int:
    errs: List[str] = []
    missing = [k for k in S.MUTATION_VOCAB if k not in MUTATIONS]
    if missing:
        errs.append(f"未実装の鍵: {missing}")
    extra = [k for k in MUTATIONS if k not in S.MUTATION_VOCAB]
    if extra:
        errs.append(f"語彙に無い鍵: {extra}")
    import nr_kit as KIT          # 遅延 import（nr_kit は nr_kit_mut を使う）
    rules_all, tiles, counts = [], [], {}
    t0 = time.time()
    for key in [k for k in S.MUTATION_VOCAB if (not only or k in only)]:
        for label, over in _demo_params(key):
            lab = f"{key} {label}".strip()
            try:
                m, rig, book, added = _mut_one(key, over)
                n = mut_cubes(m, key)
                counts[lab] = (n, len(added))
                rules_all.append(KIT.visibility_rules(m))
                m.pack(size=(512, 512))
                R.extract_gibs(m, f"kit_mut_{key}")
                for b in m.bones:
                    want = mut_bone_parent(b.name)
                    if want and b.parent != want:
                        errs.append(f"{lab}: ボーン {b.name} の親 {b.parent} != {want}")
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                errs.append(f"{lab}: {type(e).__name__}: {e}")
                continue
            if render:
                tex = P.paint_model(m, book, seed=11)
                tiles.append((f"{lab}  [{n}]", _render3(m, tex, _VIEW_LABEL.get(lab, _VIEW.get(key, "body")))))
    try:
        R.merge_visibility(*rules_all)
    except ValueError as e:
        errs.append(f"merge_visibility: {e}")
    # 同じ入力から同じ物ができるか
    import json
    outs = []
    for _ in range(2):
        m, rig, book, added = _mut_one("fused_bodies", dict(torsos=3, heads=3, arms=2))
        m.pack(size=(512, 512))
        outs.append(json.dumps([m.to_json(), sorted(added)], sort_keys=True, default=str))
    if outs[0] != outs[1]:
        errs.append("同じ入力で結果が変わる（決定的でない）")
    print(f"確認 {len(counts)} 組 ({time.time() - t0:.1f}s)")
    for k, (n, ns) in counts.items():
        print(f"  {k:36s} cubes={n:4d} styles={ns}")
    sheets = []
    if render and tiles:
        import nr_preview as NP
        os.makedirs(_OUT, exist_ok=True)
        per = 12
        for i in range(0, len(tiles), per):
            sheet = NP.contact_sheet(tiles[i:i + per], cols=3, title=f"nr_kit_mut {i // per + 1}")
            path = os.path.join(_OUT, f"kit_mut_{i // per + 1}.png")
            sheet.save(path)
            sheets.append(path)
            print("wrote", path)
    if zombies and not only:
        # nr_kit.build_zombie で作った spec の 6 体（区分ごとに 1 体＋ボス）
        keys = ("patient", "wallcrawler", "klaxon", "volatile", "flesh_colossus", "night_apex")
        ztiles = []
        for k in keys:
            try:
                model, book, info = KIT.build_zombie(S.ZOMBIE_BY_KEY[k])
                for w in info["warnings"]:
                    print(f"  warn {k}: {w}")
                print(f"  {k:16s} cubes={info['cubes']}/{info['cap']} atlas={info['atlas']} texel={info['texel']} "
                      f"styles={info['styles']} bones={info['bones']}")
                if info["cubes"] > info["cap"]:
                    errs.append(f"{k}: キューブ {info['cubes']} > {info['cap']}")
                if render:
                    tex = P.paint_model(model, book, seed=5)
                    ztiles.append((f"{k} [{info['cubes']}/{info['cap']}] {info['atlas'][0]}px",
                                   _render3(model, tex, "body")))
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                errs.append(f"build_zombie {k}: {type(e).__name__}: {e}")
        if render and ztiles:
            import nr_preview as NP
            n = len(sheets) + 1
            path = os.path.join(_OUT, f"kit_mut_{n}.png")
            NP.contact_sheet(ztiles, cols=3, title="nr_kit.build_zombie（spec の 6 体）").save(path)
            print("wrote", path)
    for e in errs:
        print("ERROR", e)
    return 1 if errs else 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-zombies", action="store_true")
    a = ap.parse_args()
    sys.exit(_selftest(render=not a.no_render, only=[k for k in a.only.split(",") if k] or None,
                       zombies=not a.no_zombies))
