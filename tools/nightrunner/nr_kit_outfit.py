# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 服・装備の部品集（nr_spec の OUTFIT_VOCAB 全項目。DESIGN.md §3）。

nr_rig.ZombieRig の体の外側に、服・帽子・靴・装備のキューブを足す。

使い方（gen_nr_zombies から）::

    import nr_kit_outfit as KO
    rig = nr_rig.ZombieRig(model, build)
    book = nr_paint.zombie_styles(...)             # 体の stylebook
    added = KO.dress(rig, z, book)                 # z["outfit"] を重ね順に全部着せる（book に追加）
    # 1 項目ずつなら
    ctx = KO.OutfitCtx(z, key, book)
    added = KO.OUTFITS[key](rig, nr_spec.outfit_params((key, over)), ctx)

API: ``OUTFITS = {鍵: fn}``、``fn(rig, params, ctx) -> その部品が足した stylebook の項目 {名前: スタイル}``。
ctx は ``rng``（ゾンビの鍵＋部品の鍵で seed）・``z``（spec の項目。無ければ {}）・
``style(name_hint, style_dict) -> 重ならないスタイル名`` を持つ（OutfitCtx が既定の実装）。

約束:
* キューブは覆う体の部位のボーンへ（袖 → arm_* / forearm_*、ズボン → pelvis / leg_* / shin_*、
  靴 → foot_*（深い靴の筒は shin_*）、上着 → chest / torso、ベルト → pelvis、髪 → head、ひげ → jaw）。
* 足す子ボーンは名前ごとに親が決まっている（``bone_parent()``。merge_visibility が種類をまたいで
  同じ式を要求するため）:
  ``hat`` → head（装甲でない帽子・ヘルメット）、
  ``armor_head`` → head、``armor_chest`` → chest、``armor_belly`` → torso、``armor_pelvis`` → pelvis、
  ``armor_arm_<s>`` → arm_<s>、``armor_forearm_<s>`` → forearm_<s>、``armor_leg_<s>`` → leg_<s>、
  ``armor_shin_<s>`` → shin_<s>（どれも段階 N > 1 なら名前の末尾に ``_N``。nr_rig が nr:armor >= N に変換）、
  ``gear_tank`` / ``gear_flashlight`` → chest、``gear_flashlight_hand`` → hand_l、``gear_shield`` → forearm_l、
  ``held_tool`` → hand_r、``held_tool_l`` → hand_l。
* 硬い部品（layer = hard）は z["gore"]["armored"] にその部位がある時だけ armor_* に置く
  （armor_strip の段階 N が名前の _N）。無ければ普通に体の部位（頭は hat）の子。
* 服は体の外側の殻（部位の体のキューブの断面 + 余白）。同じ部位に重ねるたびに余白を増やす
  （rig._nr_outfit_off に部位ごとの一番外の余白を記録）ので、面が重なって z-fighting しない。
  dress() は内側の服から順に着せる（DEPTH）。
* 共通引数（OUTFIT_COMMON_PARAMS）: color → base、color2 → 柄・縁・ロゴの色、torn → nr_paint の torn
  （破れ目の下は肌の色）＋形の破れ（袖・裾が千切れて短く、ぼろ布が垂れ、殻が欠けて肌が見える）、
  bloody / dirty / burnt / wet → blood / dirt / burn / wet。

自己テスト: ``python3 tools/nightrunner/nr_kit_outfit.py`` … 全鍵の実装の確認、標準の体に 1 項目ずつ着せた
確認画像（build_preview/nightrunner/kit_outfit_<n>.png、前と後ろ）と spec の 3 体の着せ替え、
キューブ数・ボーンの親の一貫性・gib の抽出・アトラスに収まるかの検査。
"""
from __future__ import annotations

import math
import os
import random
import re
import sys
import time
from types import SimpleNamespace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import nr_common as C  # noqa: E402
import nr_paint as P  # noqa: E402
import nr_rig as R  # noqa: E402
import nr_spec as S  # noqa: E402

# ---------------------------------------------------------------------------
#  定数
# ---------------------------------------------------------------------------
_GAP = 0.10        # 重ね着: 前の服の一番外（細部込み）からさらに空ける余白
_DETAIL = 0.10     # 服の殻の外に出る細部（襟・袖口・ポケット）の厚みの見込み

# 共通引数 0..3 → nr_paint の量
_BLOOD = (0.08, 0.45, 1.0, 2.0)
_DIRT = (0.22, 0.45, 0.68, 0.92)
_BURN = (0.0, 0.34, 0.64, 0.95)
_TORN = (0.0, 0.22, 0.45, 0.75)
_TORNABLE = ("cloth", "denim", "knit", "hi_vis")

# 着せる順（小さいほど内側）。同じ部位では後から着た服ほど外側の殻になる
DEPTH = {
    "tattoo": 0, "bandage_wrap": 0.5, "hair": 0.5, "beard": 0.5,
    "jeans": 1, "slacks": 1, "work_pants": 1, "pencil_skirt": 1, "running_shorts": 1,
    "t_shirt": 1.5, "hospital_gown": 2, "scrubs": 2, "shirt": 2, "police_uniform": 2,
    "camo_fatigues": 2.5, "prison_jumpsuit": 2.5, "coveralls": 2.5, "chef_coat": 2.6,
    "torn_dress": 2.6, "necktie": 3, "cardigan": 3.2, "hoodie": 3.4,
    "suit_jacket": 4, "leather_jacket": 4, "rain_jacket": 4,
    "firefighter_coat": 4.5, "hazmat_suit": 4.6, "bomb_suit": 4.8,
    "sneakers": 5, "dress_shoes": 5, "boots": 5.2, "gloves": 5.3, "wristwatch": 5.4,
    "hi_vis_vest": 5.5, "apron": 5.6, "life_vest": 5.7, "layered_rags": 5.8,
    "military_vest": 6, "riot_armor": 6.2, "tool_belt": 6.4, "chain_shackles": 6.5,
    "skull_cap": 6.6, "surgical_mask": 6.7, "gas_mask": 6.8, "glasses": 6.9, "headphones": 7,
    "hard_hat": 7.2, "police_cap": 7.2, "riot_helmet": 7.2, "helmet_military": 7.2,
    "firefighter_helmet": 7.2, "scooter_helmet": 7.2, "baseball_cap": 7.2, "bridal_veil": 7.4,
    "name_badge": 7.6, "backpack": 7.8, "air_tank": 7.8, "flashlight": 8, "riot_shield": 8.2,
    "held_tool": 8.4,
}

# 子ボーン（名前 → 親）。名前ごとに親は一つ
BONE_PARENTS: Dict[str, str] = {
    "hat": "head",
    "gear_tank": "chest", "gear_flashlight": "chest", "gear_flashlight_hand": "hand_l",
    "gear_shield": "forearm_l", "held_tool": "hand_r", "held_tool_l": "hand_l",
}
# 装甲の置き場所: (部位, 場所) → (ボーン名の元, 親)
ARMOR_SLOTS: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("head", "head"): ("armor_head", "head"),
    ("torso", "chest"): ("armor_chest", "chest"),
    ("torso", "belly"): ("armor_belly", "torso"),
    ("torso", "pelvis"): ("armor_pelvis", "pelvis"),
}
for _s in "rl":
    ARMOR_SLOTS[(f"arm_{_s}", "upper")] = (f"armor_arm_{_s}", f"arm_{_s}")
    ARMOR_SLOTS[(f"arm_{_s}", "fore")] = (f"armor_forearm_{_s}", f"forearm_{_s}")
    ARMOR_SLOTS[(f"leg_{_s}", "upper")] = (f"armor_leg_{_s}", f"leg_{_s}")
    ARMOR_SLOTS[(f"leg_{_s}", "shin")] = (f"armor_shin_{_s}", f"shin_{_s}")
_ARMOR_BASE_PARENT = {b: p for (b, p) in ARMOR_SLOTS.values()}


def bone_parent(name: str) -> Optional[str]:
    """服・装備の子ボーンの決まった親（知らない名前は None）。"""
    if name in BONE_PARENTS:
        return BONE_PARENTS[name]
    base = re.sub(r"_[123]$", "", name)
    return _ARMOR_BASE_PARENT.get(base)


# ---------------------------------------------------------------------------
#  色の補助
# ---------------------------------------------------------------------------
def _c3(c) -> Tuple[int, int, int]:
    if isinstance(c, str):
        v = P._rgb(c)
        return tuple(int(x) for x in v)  # type: ignore[return-value]
    return tuple(int(max(0, min(255, round(float(v))))) for v in c[:3])  # type: ignore[return-value]


def _mul(c, k: float) -> Tuple[int, int, int]:
    return _c3([v * k for v in _c3(c)])


def _mix(a, b, t: float) -> Tuple[int, int, int]:
    a, b = _c3(a), _c3(b)
    return _c3([x + (y - x) * t for x, y in zip(a, b)])


def _lum(c) -> float:
    r, g, b = _c3(c)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _contrast(c) -> Tuple[int, int, int]:
    """c の上で読める文字の色（明るい地には黒っぽく、暗い地には白っぽく）。"""
    return (30, 30, 32) if _lum(c) > 140 else (232, 230, 222)


def _lv(v) -> int:
    if isinstance(v, bool):
        return 3 if v else 0
    try:
        return max(0, min(3, int(v)))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
#  文脈（スタイル名の割り当てと乱数）
# ---------------------------------------------------------------------------
class OutfitCtx:
    """部品の関数に渡す文脈の既定の実装。

    rng … random.Random（ゾンビの鍵＋部品の鍵＋salt で seed。nr_common.stable_hash）
    z … spec のゾンビの項目（gore.armored / armor_strip / skin / tone を見る）。無ければ {}
    style(name_hint, style_dict) … stylebook に入れて名前を返す（同じ中身なら同じ名前を使い回す）
    """

    def __init__(self, z: Optional[dict] = None, key: str = "", stylebook: Optional[dict] = None,
                 salt: str = ""):
        self.z = z if z is not None else {}
        self.key = key
        zk = self.z.get("key", "standard")
        self.rng = random.Random(C.stable_hash(f"{zk}/{key}{salt}"))
        self.book = stylebook if stylebook is not None else {}
        self.added: Dict[str, dict] = {}

    def style(self, name_hint: str, style_dict: dict) -> str:
        # 中身が同じなら（別の部品が作った物でも）使い回す → スタイル数（塗りの手間）を減らす
        for n, sd in self.book.items():
            if n.startswith("o_") and sd == style_dict:
                return n
        name, i = name_hint, 2
        while name in self.book:
            name = f"{name_hint}_{i}"
            i += 1
        self.book[name] = style_dict
        self.added[name] = style_dict
        return name


# ---------------------------------------------------------------------------
#  部位の断面（体のキューブの AABB を部位ごとに集める）
# ---------------------------------------------------------------------------
def _seg_boxes(rig) -> Dict[str, list]:
    cache = getattr(rig, "_nr_kit_segbox", None)
    if cache is None:
        cache = {}
        for bone in rig.model.bones:
            if bone.name in R.GORE_BONES:
                continue
            for c in bone.cubes:
                seg = getattr(c, "nr_seg", None)
                if not seg or getattr(c, "nr_kit", None):
                    continue
                pts = (R.cube_matrix(c) @ R.cube_corners(c).T).T[:, :3]
                cache.setdefault(seg, []).append((pts.min(axis=0), pts.max(axis=0)))
        rig._nr_kit_segbox = cache
    return cache


_LIMB_SEGS = ("thigh", "shin", "upper_arm", "forearm")


class _K:
    """1 項目を作る間の道具箱（寸法・スタイル・キューブ・子ボーン・重ね着の余白）。"""

    def __init__(self, rig, p: dict, ctx, key: str):
        self.rig, self.ctx, self.key = rig, ctx, key
        self.p = dict(p)
        self.L, self.U = rig.L, rig.U
        self.rng: random.Random = ctx.rng
        self.z = getattr(ctx, "z", None) or {}
        self.styles: Dict[str, dict] = {}
        self.cubes: list = []
        self._memo: Dict[tuple, str] = {}
        self.col = _c3(p.get("color", (128, 128, 128)))
        self.col2 = _c3(p["color2"]) if p.get("color2") is not None else None
        self.torn = _lv(p.get("torn", 0))
        self.bloody = _lv(p.get("bloody", 0))
        self.dirty = _lv(p.get("dirty", 0))
        self.burnt = _lv(p.get("burnt", 0))
        self.wet = bool(p.get("wet", False))
        self.box_cache = _seg_boxes(rig)
        if not hasattr(rig, "_nr_outfit_off"):
            rig._nr_outfit_off = {}
        self.offs: Dict[str, float] = rig._nr_outfit_off
        sk = self.z.get("skin")
        try:
            tone = P.skin_tone(sk, self.z.get("tone")) if sk else dict(R.GENERIC_TONE)
            self.skin = _c3(tone["base"])
        except Exception:  # noqa: BLE001  未知の肌でも服は作れるように
            self.skin = _c3(R.GENERIC_TONE["base"])

    # ------------------------------------------------------------ スタイル
    def st(self, hint: str, mat: str, *, wear: bool = True, torn: Optional[float] = None,
           blood: Optional[float] = None, dirt: Optional[float] = None, **kw) -> str:
        """部品のスタイル。wear=True なら共通引数の血・汚れ・焦げ・濡れ・破れを足す。"""
        d = {"mat": mat}
        if wear:
            d["blood"] = _BLOOD[self.bloody] if blood is None else blood
            d["dirt"] = _DIRT[self.dirty] if dirt is None else dirt
            if self.burnt:
                d["burn"] = _BURN[self.burnt]
            if self.wet:
                d["wet"] = 0.75
            if mat in _TORNABLE:
                t = _TORN[self.torn] if torn is None else torn
                if t > 0:
                    d["torn"] = t
                    d["under"] = _mul(self.skin, 0.62)
        elif blood is not None:
            d["blood"] = blood
        d.update(kw)
        memo = (hint, repr(sorted(d.items())))
        name = self._memo.get(memo)
        if name is None:
            name = self.ctx.style("o_" + hint, d)
            self._memo[memo] = name
            self.styles[name] = d
        return name

    def cloth(self, hint="cloth", base=None, pattern="plain", alt=None, mat="cloth", **kw) -> str:
        base = _c3(base if base is not None else self.col)
        args = dict(base=base, pattern=pattern, folds=kw.pop("folds", 1.0))
        if alt is not None:
            args["alt"] = _c3(alt)
        args.update(kw)
        return self.st(hint, mat, **args)

    # ------------------------------------------------------------ ボーン
    def child(self, name: str) -> str:
        parent = bone_parent(name)
        if parent is None:
            raise ValueError(f"nr_kit_outfit: 親の決まっていない子ボーン '{name}'")
        b = self.rig.bones.get(name)
        if b is None:
            pb = self.rig.bones[parent]
            b = R.NRBone(name, list(pb.pivot), parent, None)
            self.rig.model.bones.append(b)
            self.rig.bones[name] = b
        elif b.parent != parent:
            raise ValueError(f"nr_kit_outfit: ボーン '{name}' の親が {b.parent} と {parent} で食い違う")
        return name

    def armor(self, part: str, slot: str) -> str:
        """装甲の部品を置くボーン。gore.armored にその部位があれば armor_*（段階 N>1 は _N）、
        無ければ体の部位（頭は hat）。"""
        base, parent = ARMOR_SLOTS[(part, slot)]
        g = self.z.get("gore") or {}
        if part in (g.get("armored") or ()):
            n = int((g.get("armor_strip") or {}).get(part, 1))
            return self.child(base if n <= 1 else f"{base}_{n}")
        return self.child("hat") if part == "head" else parent

    # ------------------------------------------------------------ 寸法
    def seg(self, name: str) -> dict:
        return self.rig.segment(name)

    def slices(self, seg: str) -> List[Tuple[float, float]]:
        """部位の正規の輪切り（どの服も同じ切り方で断面を取る → 重ねても面が交差しない）。"""
        sg = self.seg(seg)
        lo, hi = sg["lo"][1], sg["hi"][1]
        if seg.startswith(_LIMB_SEGS):
            m = round((lo + hi) / 2, 3)
            return [(lo, m), (m, hi)]
        return [(lo, hi)]

    def ring(self, seg: str, y0: float, y1: float) -> Tuple[float, float, float, float]:
        """y0..y1 に掛かる体のキューブの x / z の範囲 (x0, z0, x1, z1)。"""
        boxes = self.box_cache.get(seg) or []
        sel = [(lo, hi) for lo, hi in boxes if hi[1] > y0 + 1e-3 and lo[1] < y1 - 1e-3] or boxes
        if not sel:
            sg = self.seg(seg)
            return sg["lo"][0], sg["lo"][2], sg["hi"][0], sg["hi"][2]
        x0 = min(float(lo[0]) for lo, _ in sel)
        z0 = min(float(lo[2]) for lo, _ in sel)
        x1 = max(float(hi[0]) for _, hi in sel)
        z1 = max(float(hi[2]) for _, hi in sel)
        return x0, z0, x1, z1

    def ring_at(self, seg: str, y: float) -> Tuple[float, float, float, float]:
        """高さ y を含む正規の輪切りの断面。"""
        for a, b in self.slices(seg):
            if a - 1e-3 <= y <= b + 1e-3:
                return self.ring(seg, a, b)
        sl = self.slices(seg)
        a, b = sl[0] if y < sl[0][0] else sl[-1]
        return self.ring(seg, a, b)

    def off(self, segs: Sequence[str], base: float) -> float:
        """segs に重ねる殻の余白（前の服の外側 + _GAP 以上）を決めて記録する。"""
        cur = [self.offs[s] for s in segs if s in self.offs]
        o = max([base] + [c + _GAP for c in cur])
        for s in segs:
            self.offs[s] = max(self.offs.get(s, 0.0), o + _DETAIL)
        return round(o, 3)

    # ------------------------------------------------------------ キューブ
    def box(self, bone: str, x0, y0, z0, x1, y1, z1, style: str, uv: Optional[float] = None,
            decals=None, rot=None, pivot=None):
        c = self.rig.box(bone, x0, y0, z0, x1, y1, z1, style, uv=uv or self.U["body"],
                         rot3=rot, pivot=pivot, decals=decals)
        c.nr_kit = self.key
        self.cubes.append(c)
        return c

    def cbox(self, bone: str, centre, size, style: str, uv=None, decals=None, rot=None, pivot=None):
        """中心と大きさで箱（回転の中心は既定で箱の中心）。"""
        cx, cy, cz = centre
        sx, sy, sz = size
        if rot is not None and pivot is None:
            pivot = (cx, cy, cz)
        return self.box(bone, cx - sx / 2, cy - sy / 2, cz - sz / 2, cx + sx / 2, cy + sy / 2,
                        cz + sz / 2, style, uv, decals, rot, pivot)

    def beam(self, bone: str, p0, p1, w: float, d: float, style: str, uv=None, over: float = 0.0):
        c = self.rig.beam(bone, p0, p1, w, d, style, uv=uv or self.U["body"], over=over)
        c.nr_kit = self.key
        self.cubes.append(c)
        return c

    def wrap(self, bone: str, seg: str, off: float, style: str, y0: float = -1e9, y1: float = 1e9,
             decals=None, uv=None, gap: float = 0.0, front_decals=None, grow=(0, 0, 0, 0),
             gap_side: str = "n") -> list:
        """部位 seg を y0..y1 で覆う殻（正規の輪切りごとに 1 個）。最初の輪切りは y0 まで、最後は y1 まで伸ばす。

        gap > 0 なら開きを作る（gap_side = n: 前、s: 後ろ。開いた側を右・左の 2 枚、反対側を 1 枚）。
        decals は全部の箱か輪切りごとのリスト。front_decals = {"r": .., "l": ..}（開いた側の 2 枚）。
        grow = (x0, z0, x1, z1) の各辺だけさらに外へ。"""
        out = []
        sl = self.slices(seg)
        n = len(sl)
        for i, (a, b) in enumerate(sl):
            ya = y0 if i == 0 else max(a, y0)
            yb = y1 if i == n - 1 else min(b, y1)
            if yb - ya < 0.04:
                continue
            x0, z0, x1, z1 = self.ring(seg, a, b)
            x0, z0 = x0 - off - grow[0], z0 - off - grow[1]
            x1, z1 = x1 + off + grow[2], z1 + off + grow[3]
            d = decals[i] if isinstance(decals, list) else decals
            if gap <= 0:
                out.append(self.box(bone, x0, ya, z0, x1, yb, z1, style, uv, d))
                continue
            zm = (z0 + z1) / 2
            face = "north" if gap_side == "n" else "south"
            rest = {k: v for k, v in (d or {}).items() if k != face} or None
            fd = front_decals[i] if isinstance(front_decals, list) else front_decals
            if gap_side == "n":
                out.append(self.box(bone, x0, ya, zm, x1, yb, z1, style, uv, rest))
                za, zb = z0, zm
            else:
                out.append(self.box(bone, x0, ya, z0, x1, yb, zm, style, uv, rest))
                za, zb = zm, z1
            out.append(self.box(bone, x0, ya, za, -gap / 2, yb, zb, style, uv, (fd or {}).get("r")))
            out.append(self.box(bone, gap / 2, ya, za, x1, yb, zb, style, uv, (fd or {}).get("l")))
        return out

    def band(self, bone: str, seg: str, off: float, y0: float, y1: float, style: str, uv=None,
             decals=None):
        """細い帯（袖口・裾・ベルト）。y の位置の輪切りの断面 + off。"""
        x0, z0, x1, z1 = self.ring_at(seg, (y0 + y1) / 2)
        return self.box(bone, x0 - off, y0, z0 - off, x1 + off, y1, z1 + off, style, uv, decals)

    def rags(self, bone: str, x0, x1, z0, z1, y: float, style: str, n: int,
             length=(0.6, 1.8), width=(0.3, 0.75), sides: str = "nsew", th: float = 0.1,
             swing: float = 14.0) -> list:
        """y の縁から下へ垂れるぼろ布 n 本（箱 x0..x1 / z0..z1 の外側に貼る）。"""
        out = []
        rng = self.rng
        for _ in range(max(0, n)):
            side = rng.choice(sides)
            ln = rng.uniform(*length)
            w = rng.uniform(*width)
            top = y + 0.25
            if side in "ns":
                u = rng.uniform(x0 + w / 2, max(x0 + w / 2, x1 - w / 2))
                zz = z0 - th - 0.03 if side == "n" else z1 + 0.03
                rz = rng.uniform(-swing, swing)
                out.append(self.box(bone, u - w / 2, top - ln, zz, u + w / 2, top, zz + th, style,
                                    rot=(rng.uniform(-6, 6), 0, rz), pivot=(u, top, zz + th / 2)))
            else:
                u = rng.uniform(z0 + w / 2, max(z0 + w / 2, z1 - w / 2))
                xx = x0 - th - 0.03 if side == "e" else x1 + 0.03
                rx = rng.uniform(-swing, swing)
                out.append(self.box(bone, xx, top - ln, u - w / 2, xx + th, top, u + w / 2, style,
                                    rot=(rx, 0, rng.uniform(-6, 6)), pivot=(xx + th / 2, top, u)))
        return out

    def n_rags(self, scale: float = 1.0) -> int:
        """torn の段階に応じたぼろの本数。"""
        base = (0, self.rng.randint(0, 1), self.rng.randint(2, 3), self.rng.randint(4, 6))[self.torn]
        return int(round(base * scale))

    def done(self) -> Dict[str, dict]:
        return dict(self.styles)


def _sides(p: dict, key: str = "hands") -> Tuple[str, ...]:
    v = p.get(key, "both")
    return ("r", "l") if v in ("both", None, "") else (v,)


# ---------------------------------------------------------------------------
#  よく使う形（上半身・袖・脚・裾・襟）
# ---------------------------------------------------------------------------
TORSO = ("chest", "abdomen")
ARMS = ("upper_arm_r", "upper_arm_l", "forearm_r", "forearm_l")
LEGS = ("thigh_r", "thigh_l", "shin_r", "shin_l")


def _torso(K: _K, off: float, st: str, *, gap_chest: float = 0.0, gap_belly: float = 0.0,
           crop: float = 0.0, chest_decals=None, belly_decals=None, front_decals=None,
           y_top: Optional[float] = None, gap_side: str = "n", uv=None) -> dict:
    """胸と腹の殻。crop > 0 で裾を上げる（腹が出る）。"""
    L = K.L
    ch, ab = K.seg("chest"), K.seg("abdomen")
    top = ch["hi"][1] + 0.12 if y_top is None else y_top
    out = {}
    out["chest"] = K.wrap("chest", "chest", off, st, y0=L.chest_bot - 0.05, y1=top,
                          decals=chest_decals, gap=gap_chest, front_decals=front_decals,
                          gap_side=gap_side, uv=uv)
    lo = ab["lo"][1] - 0.05 + crop
    if lo < L.chest_bot - 0.1:
        out["belly"] = K.wrap("torso", "abdomen", off, st, y0=lo, y1=L.chest_bot + 0.15,
                              decals=belly_decals, gap=gap_belly, front_decals=front_decals,
                              gap_side=gap_side, uv=uv)
    return out


def _skirt(K: _K, off: float, st: str, y_bot: float, y_top: Optional[float] = None, gap: float = 0.0,
           flare: float = 0.0, decals=None, gap_side: str = "n", front_decals=None) -> list:
    """腰から下の裾（pelvis のボーン。上着の裾・スカート・ガウン）。flare で外へ広げる。"""
    L = K.L
    y_top = L.abdomen_bot + 0.25 if y_top is None else y_top
    return K.wrap("pelvis", "pelvis", off, st, y0=y_bot, y1=y_top, decals=decals, gap=gap,
                  grow=(flare, flare, flare, flare), gap_side=gap_side, front_decals=front_decals)


def _hood(K: _K, st: str, mode: str) -> list:
    """フード。up = 頭を覆う（head の子・顔の前は開く）、down = 背中に垂れる（chest の子）。"""
    L = K.L
    out = []
    if mode == "up":
        H = _head(K)
        o = K.off(("head",), 0.3)
        x0, x1, z0, z1 = H.x0 - o, H.x1 + o, H.z0 - o, H.z1 + o
        top = H.top + o + 0.12
        fz = H.face_z - 0.12
        out.append(K.box("head", x0, H.brow + 0.25, fz, x1, top, z1, st))
        for sgn in (-1, 1):
            xa, xb = (x0, x0 + 0.38) if sgn < 0 else (x1 - 0.38, x1)
            out.append(K.box("head", xa, H.jaw_low - 0.7, fz + 0.25, xb, H.brow + 0.3, z1, st))
        out.append(K.box("head", x0 + 0.1, H.jaw_low - 1.2, H.cz + 0.5, x1 - 0.1, H.brow + 0.3, z1, st))
        return out
    ch = K.seg("chest")
    x0_, z0_, x1_, z1_ = K.ring("chest", L.chest_bot, ch["hi"][1])
    o = K.offs.get("chest", 0.3)
    out.append(K.box("chest", -1.7, ch["hi"][1] - 2.1, z1_ + o - 0.05, 1.7, ch["hi"][1] + 0.3,
                     z1_ + o + 0.7, st, rot=(-6, 0, 0), pivot=(0, ch["hi"][1], z1_ + o)))
    out.append(K.box("chest", -1.35, ch["hi"][1] - 0.35, z1_ - 0.55, 1.35, ch["hi"][1] + 0.45,
                     z1_ + o + 0.35, st))
    return out


def _tied_sleeves(K: _K, st: str, off: float) -> list:
    """上を脱いで袖を腰で結んだ形（つなぎ・囚人服）: 腰の帯 + 前の結び目 + 垂れた袖 2 本。"""
    L = K.L
    o = K.off(("pelvis",), off)
    y = L.abdomen_bot - 0.1
    out = [K.band("pelvis", "pelvis", o + 0.1, y - 0.35, y + 0.65, st)]
    x0, z0, x1, z1 = K.ring_at("pelvis", y)
    zf = z0 - o - 0.1
    out.append(K.cbox("pelvis", (0.15, y + 0.1, zf - 0.25), (1.0, 0.9, 0.6), st))
    for sgn in (-1, 1):
        out.append(K.beam("pelvis", (sgn * 0.3 + 0.15, y - 0.1, zf - 0.3),
                          (sgn * 0.9 + 0.15, y - 3.2 - K.rng.uniform(0, 0.6), zf - 0.45), 0.85, 0.5, st))
    # 背中側に垂れた上半身の布
    out.append(K.box("pelvis", x0 - o - 0.12, y - 2.6, z1 + o + 0.02, x1 + o + 0.12, y + 0.5,
                     z1 + o + 0.22, st, rot=(6, 0, 0), pivot=(0, y + 0.5, z1 + o)))
    return out


def _pocket_flaps(K: _K, bone: str, seg: str, off: float, y: float, st: str, xs=(-1.2, 1.2),
                  w: float = 1.1, h: float = 0.42) -> list:
    """胸ポケットなどの蓋（前面に貼る薄い板）。"""
    x0, z0, x1, z1 = K.ring_at(seg, y)
    out = []
    for xc in xs:
        out.append(K.box(bone, xc - w / 2, y - h, z0 - off - 0.11, xc + w / 2, y, z0 - off + 0.01, st))
    return out


def _sleeve(K: _K, s: str, off: float, st: str, length: str = "long", cuff: Optional[str] = None,
            roll: Optional[str] = None, decals=None) -> list:
    """袖。length = long（手首）/ three_q（前腕の中ほど）/ elbow / short（上腕の中ほど）/ cap（肩だけ）/ none。
    cuff = 袖口の帯のスタイル、roll = まくった袖の巻きのスタイル（short / elbow の端に太い輪）。"""
    if length == "none":
        return []
    L = K.L
    ua, fa = K.seg(f"upper_arm_{s}"), K.seg(f"forearm_{s}")
    ua_lo, ua_hi = ua["lo"][1], ua["hi"][1]
    fa_lo, fa_hi = fa["lo"][1], fa["hi"][1]
    out = []
    end_u = {"long": ua_lo - 0.1, "three_q": ua_lo - 0.1, "elbow": ua_lo - 0.1,
             "short": ua_lo + 0.48 * (ua_hi - ua_lo), "cap": ua_hi - 0.25 * (ua_hi - ua_lo)}[length]
    out += K.wrap(f"arm_{s}", f"upper_arm_{s}", off, st, y0=end_u, y1=ua_hi + 0.15, decals=decals)
    end_y, end_bone, end_seg = end_u, f"arm_{s}", f"upper_arm_{s}"
    if length in ("long", "three_q"):
        y0 = L.wrist_y + 0.1 if length == "long" else fa_lo + 0.5 * (fa_hi - fa_lo)
        out += K.wrap(f"forearm_{s}", f"forearm_{s}", off, st, y0=y0, y1=fa_hi, decals=decals)
        end_y, end_bone, end_seg = y0, f"forearm_{s}", f"forearm_{s}"
    if roll:
        out.append(K.band(end_bone, end_seg, off + 0.14, end_y - 0.05, end_y + 0.55, roll))
    elif cuff and length in ("long", "three_q", "short", "elbow"):
        out.append(K.band(end_bone, end_seg, off + 0.07, end_y - 0.02, end_y + 0.32, cuff))
    return out


def _sleeve_len(K: _K, want: str) -> Dict[str, str]:
    """破れ具合で左右の袖の長さを変える（torn 2 で片袖、3 で両袖が千切れる）。"""
    order = ("long", "three_q", "elbow", "short", "cap", "none")
    out = {}
    for s in "rl":
        L_ = want
        if K.torn >= 2 and want in order:
            i = order.index(want)
            if K.torn == 3 or (s == ("r" if K.rng.random() < 0.5 else "l")):
                L_ = order[min(len(order) - 2, i + K.rng.randint(1, 2))]
        out[s] = L_
    return out


def _sleeve_rags(K: _K, s: str, off: float, st: str, length: str, n: int) -> list:
    """千切れた袖の端のぼろ。"""
    if n <= 0 or length == "none":
        return []
    if length in ("long", "three_q"):
        seg, bone = f"forearm_{s}", f"forearm_{s}"
        y = K.L.wrist_y + 0.1 if length == "long" else K.seg(seg)["lo"][1] + \
            0.5 * (K.seg(seg)["hi"][1] - K.seg(seg)["lo"][1])
    else:
        seg, bone = f"upper_arm_{s}", f"arm_{s}"
        sg = K.seg(seg)
        y = {"elbow": sg["lo"][1] - 0.1, "short": sg["lo"][1] + 0.48 * (sg["hi"][1] - sg["lo"][1]),
             "cap": sg["hi"][1] - 0.25 * (sg["hi"][1] - sg["lo"][1])}[length]
    x0, z0, x1, z1 = K.ring_at(seg, y + 0.05)
    return K.rags(bone, x0 - off, x1 + off, z0 - off, z1 + off, y, st, n, length=(0.4, 1.1),
                  width=(0.25, 0.5))


def _hem_rags(K: _K, bone: str, seg: str, off: float, y: float, st: str, n: int, **kw) -> list:
    x0, z0, x1, z1 = K.ring_at(seg, y + 0.05)
    return K.rags(bone, x0 - off, x1 + off, z0 - off, z1 + off, y, st, n, **kw)


def _collar(K: _K, kind: str, off: float, st: str, open_: int = 0) -> list:
    """襟。kind = crew / v / shirt / band / turtle / none。胸のボーンに付ける（首が飛んでも残る）。"""
    if kind == "none":
        return []
    L = K.L
    nk = K.seg("neck")
    nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
    ch_top = K.seg("chest")["hi"][1]
    y0 = ch_top - 0.35
    out = []
    o = off + 0.08
    if kind in ("crew", "band", "turtle"):
        h = {"crew": 0.42, "band": 0.62, "turtle": 1.3}[kind]
        out.append(K.box("chest", nx0 - o, y0, nz0 - o, nx1 + o, y0 + h + 0.3, nz1 + o, st))
    elif kind == "v":
        out.append(K.box("chest", nx0 - o, y0, nz0 + 0.35, nx1 + o, y0 + 0.62, nz1 + o, st))
        for sgn in (-1, 1):
            out.append(K.box("chest", sgn * 0.05, y0 - 1.1, nz0 - o - 0.08, sgn * 0.5, y0 + 0.55,
                             nz0 - o + 0.1, st, rot=(0, 0, sgn * 24), pivot=(sgn * 0.5, y0 + 0.55, nz0)))
    elif kind == "shirt":
        # 首の後ろと横を回る台襟 + 前に折れた襟先 2 枚
        out.append(K.box("chest", nx0 - o, y0, nz0 + 0.25, nx1 + o, y0 + 0.82, nz1 + o, st))
        spread = 18 + 12 * open_
        for sgn in (-1, 1):
            xi = sgn * (0.12 + 0.1 * open_)
            out.append(K.box("chest", xi, y0 - 0.55, nz0 - o - 0.14, xi + sgn * 0.95, y0 + 0.45,
                             nz0 - o + 0.02, st, rot=(-8, 0, sgn * spread),
                             pivot=(xi, y0 + 0.45, nz0 - o)))
    return out


def _legs(K: _K, off: float, st: str, *, length: str = "full", waist: bool = True,
          pelvis_decals=None, thigh_decals=None, shin_decals=None, hem: Optional[str] = None,
          knee_gap: bool = False, sides=("r", "l"), waist_st: Optional[str] = None) -> dict:
    """ズボンの殻。length = full（足首）/ short_full（くるぶしが出る）/ capri / knee / shorts / brief。"""
    L = K.L
    pv = K.seg("pelvis")
    out = {"pelvis": [], "legs": []}
    top = L.abdomen_bot + 0.32
    if waist:
        out["pelvis"] += K.wrap("pelvis", "pelvis", off, st, y0=pv["lo"][1] - 0.12, y1=top,
                                decals=pelvis_decals)
        if waist_st:
            out["pelvis"].append(K.band("pelvis", "pelvis", off + 0.06, top - 0.42, top + 0.02,
                                        waist_st))
    for s in sides:
        th, sh = K.seg(f"thigh_{s}"), K.seg(f"shin_{s}")
        t_lo = {"brief": th["hi"][1] - 0.52 * (th["hi"][1] - th["lo"][1]),
                "shorts": th["lo"][1] + 0.45 * (th["hi"][1] - th["lo"][1])}.get(length, th["lo"][1] - 0.1)
        if knee_gap and length in ("full", "short_full"):
            t_lo = L.knee_y + 0.8
        out["legs"] += K.wrap(f"leg_{s}", f"thigh_{s}", off, st, y0=t_lo, y1=th["hi"][1],
                              decals=thigh_decals)
        end_bone, end_seg, end_y = f"leg_{s}", f"thigh_{s}", t_lo
        if length in ("full", "short_full", "capri", "knee"):
            s_lo = {"full": L.ankle_y + 0.08, "short_full": L.ankle_y + 0.9,
                    "capri": sh["lo"][1] + 0.45 * (sh["hi"][1] - sh["lo"][1]),
                    "knee": sh["hi"][1] - 1.4}[length]
            s_hi = sh["hi"][1] + 0.05
            if knee_gap and length in ("full", "short_full"):
                s_hi = L.knee_y - 0.6
                # 膝の裏だけ残す（前が破れて膝が出る）
                x0, z0, x1, z1 = K.ring_at(f"shin_{s}", sh["hi"][1] - 0.3)
                zm = (z0 + z1) / 2
                out["legs"].append(K.box(f"shin_{s}", x0 - off, s_hi - 0.05, zm, x1 + off,
                                         sh["hi"][1] + 0.05, z1 + off, st))
            out["legs"] += K.wrap(f"shin_{s}", f"shin_{s}", off, st, y0=s_lo, y1=s_hi,
                                  decals=shin_decals)
            end_bone, end_seg, end_y = f"shin_{s}", f"shin_{s}", s_lo
        if hem:
            out["legs"].append(K.band(end_bone, end_seg, off + 0.07, end_y - 0.04, end_y + 0.3, hem))
        out[f"end_{s}"] = (end_bone, end_seg, end_y)
    return out


def _belt(K: _K, off: float, st: str, buckle_st: Optional[str] = None, y: Optional[float] = None,
          h: float = 0.42) -> list:
    L = K.L
    y = L.abdomen_bot + 0.05 if y is None else y
    out = [K.band("pelvis", "pelvis", off, y, y + h, st)]
    if buckle_st:
        x0, z0, x1, z1 = K.ring_at("pelvis", y + 0.2)
        out.append(K.box("pelvis", -0.32, y - 0.06, z0 - off - 0.12, 0.32, y + h + 0.06,
                         z0 - off + 0.02, buckle_st, uv=K.U["fine"]))
    return out


# ---------------------------------------------------------------------------
#  頭の寸法
# ---------------------------------------------------------------------------
def _head(K: _K) -> SimpleNamespace:
    cr, fc = K.seg("cranium"), K.seg("face")
    jw = K.seg("jaw")
    x0, z0, x1, z1 = K.ring("cranium", fc["hi"][1] - 0.4, cr["hi"][1])   # 耳より上の頭蓋
    ex0, _, ex1, _ = K.ring("cranium", cr["lo"][1], cr["hi"][1])           # 耳込みの幅
    E = _eyes(K)
    return SimpleNamespace(
        x0=x0, x1=x1, z0=z0, z1=z1, top=cr["hi"][1], low=cr["lo"][1],
        ex0=ex0, ex1=ex1, face_z=fc["lo"][2], face_top=fc["hi"][1], face_low=fc["lo"][1],
        jaw_low=jw["lo"][1], jaw_z=jw["lo"][2], w=x1 - x0, d=z1 - z0,
        cx=(x0 + x1) / 2, cz=(z0 + z1) / 2,
        eye=E.y, brow=E.y + 0.5, hair=E.y + 0.95,   # 帽子の前の下端（眉の上）・生え際
    )


# ===========================================================================
#  髪・ひげ
# ===========================================================================
_HAIR_MAT = {"short": "short", "buzz": "buzz", "balding": "balding", "long": "long",
             "ponytail": "long", "bun": "long", "bob": "long", "mohawk": "short",
             "messy": "matted", "matted": "matted", "shaved": "buzz"}


def o_hair(rig, p, ctx):
    K = _K(rig, p, ctx, "hair")
    H = _head(K)
    style = p.get("style", "short")
    patchy = _lv(p.get("patchy", 0))
    length = float(p.get("length", 1.0))
    mstyle = _HAIR_MAT.get(style, "short")
    if patchy >= 1 and mstyle in ("short", "buzz", "matted"):
        mstyle = "patchy"
    st = K.st("hair", "hair", base=K.col, style=mstyle, skin=K.skin, dirt=_DIRT[K.dirty] * 0.8)
    st_cap = st
    if style == "mohawk":
        st_cap = K.st("stubble", "hair", base=_mix((40, 32, 28), K.skin, 0.45), style="buzz",
                      skin=K.skin)
    rng = K.rng
    o = K.off(("head",), 0.1)
    thin = {"shaved": 0.06, "buzz": 0.08, "mohawk": 0.07}.get(style, o)
    x0, x1, z0, z1 = H.x0 - thin, H.x1 + thin, H.z0 - thin, H.z1 + thin
    top = H.top + thin + (0.12 if style in ("messy", "matted", "bob", "long") else 0.0)
    brow = H.hair - 0.25              # 生え際（前の箱の下端は brow + 0.25 = H.hair）
    nape = H.low + 0.15
    if style == "balding":
        # 馬蹄形: 後ろと両横だけ（頭頂は地肌）
        K.box("head", x0, nape, H.cz + 0.5, x1, H.top - 0.7, z1, st)
        for sgn in (-1, 1):
            xa = x0 if sgn < 0 else x1 - 0.2
            K.box("head", xa, H.face_top - 1.2, H.z0 + 0.6, xa + 0.2, H.top - 0.9, H.cz + 0.6, st)
        if patchy < 2:
            K.box("head", -0.5, H.top - 0.02, -0.6, 0.5, H.top + 0.05, 0.5, st)   # 頭頂の残り毛
        return K.done()
    # 頭を覆う帽子状の髪（上・横・後ろ）。前は生え際まで
    K.box("head", x0, brow + 0.25, z0, x1, top, z1, st_cap)
    K.box("head", x0 + 0.05, nape, H.cz + 0.3, x1 - 0.05, brow + 0.3, z1, st_cap)  # 後頭部〜襟足
    if style in ("short", "buzz", "shaved"):
        if style == "short":
            K.box("head", x0 + 0.1, brow - 0.1, z0 - 0.06, x1 - 0.1, brow + 0.45, z0 + 0.3, st)  # 前髪の縁
        return K.done()
    if style == "mohawk":
        n = 5
        for i in range(n):
            t = i / (n - 1)
            zc = H.z0 + 0.2 + t * (H.d - 0.3)
            hgt = 1.1 + 0.7 * math.sin(t * math.pi) + rng.uniform(-0.15, 0.2)
            K.box("head", -0.28, top - 0.1, zc - 0.42, 0.28, top + hgt, zc + 0.42, st,
                  rot=(-12 + 22 * t, 0, rng.uniform(-4, 4)), pivot=(0, top, zc))
        return K.done()
    if style in ("long", "bob"):
        bob = style == "bob"
        drop = (H.top - H.jaw_low) + (0.4 if bob else 2.6 * length)
        bot = H.top - drop
        K.box("head", x0 - 0.06, bot, H.z1 - 0.1, x1 + 0.06, brow + 0.5, z1 + 0.22, st)   # 背中へ垂れる髪
        for sgn in (-1, 1):
            xa = x0 - 0.2 if sgn < 0 else x1
            K.box("head", xa, bot + (0.0 if bob else 0.8), H.z0 + 0.35, xa + 0.2, brow + 0.4,
                  H.z1 + 0.1, st)
        K.box("head", H.x0 + 0.15, brow - (0.5 if bob else 0.25), z0 - 0.08, H.x1 - 0.15, brow + 0.35,
              z0 + 0.25, st)   # 前髪
        if not bob and length >= 1.2:
            for sgn in (-1, 1):   # 肩の前へ垂れる房
                xa = sgn * (H.w / 2 - 0.15)
                K.beam("head", (xa, brow - 0.2, H.z0 + 0.6), (xa + sgn * 0.5, bot + 0.6, H.z0 + 0.2),
                       0.5, 0.35, st)
        return K.done()
    if style == "ponytail":
        K.box("head", H.x0 + 0.15, brow - 0.1, z0 - 0.06, H.x1 - 0.15, brow + 0.35, z0 + 0.25, st)
        tie_y, tz = H.top - 0.9, z1 + 0.05
        K.cbox("head", (0, tie_y, tz + 0.25), (0.75, 0.6, 0.55), K.st("tie", "rubber", wear=False,
                                                                     base=(40, 36, 44)))
        p1 = (0.1, tie_y - 1.6 * length, tz + 1.0)
        K.beam("head", (0, tie_y, tz + 0.4), p1, 0.75, 0.6, st)
        K.beam("head", p1, (0.25, tie_y - 3.2 * length, tz + 0.75), 0.55, 0.45, st)
        return K.done()
    if style == "bun":
        K.box("head", H.x0 + 0.15, brow - 0.1, z0 - 0.06, H.x1 - 0.15, brow + 0.35, z0 + 0.25, st)
        K.cbox("head", (0, H.top - 0.55, z1 + 0.45), (1.35, 1.2, 1.0), st)
        K.cbox("head", (0, H.top - 0.5, z1 + 0.9), (0.9, 0.85, 0.5), st)
        return K.done()
    # messy / matted: 房が跳ねる・垂れる
    n = 6 + rng.randint(0, 3)
    for i in range(n):
        side = rng.choice("tsew" if style == "messy" else "sewn")
        ln = rng.uniform(0.6, 1.3) if style == "messy" else rng.uniform(1.0, 2.6) * length
        if side == "t":
            p0 = (rng.uniform(x0 + 0.3, x1 - 0.3), top - 0.1, rng.uniform(z0 + 0.3, z1 - 0.3))
            p1 = (p0[0] + rng.uniform(-0.7, 0.7), p0[1] + ln * 0.6, p0[2] + rng.uniform(-0.7, 0.7))
        elif side == "s":
            p0 = (rng.uniform(x0 + 0.3, x1 - 0.3), rng.uniform(H.low + 0.4, top - 0.6), z1 - 0.05)
            p1 = (p0[0] + rng.uniform(-0.4, 0.4), p0[1] - ln, p0[2] + rng.uniform(0.1, 0.5))
        elif side == "n":
            p0 = (rng.uniform(-0.8, 0.8), brow + 0.3, z0 + 0.1)
            p1 = (p0[0] + rng.uniform(-0.3, 0.3), p0[1] - ln * 0.55, z0 - 0.2)
        else:
            sx = -1 if side == "e" else 1
            xx = x0 if sx < 0 else x1
            p0 = (xx, rng.uniform(H.face_top - 0.6, top - 0.5), rng.uniform(H.z0 + 0.5, z1 - 0.3))
            p1 = (xx + sx * rng.uniform(0.15, 0.5), p0[1] - ln, p0[2] + rng.uniform(-0.3, 0.3))
        K.beam("head", p0, p1, rng.uniform(0.35, 0.6), rng.uniform(0.3, 0.5), st)
    return K.done()


def o_beard(rig, p, ctx):
    K = _K(rig, p, ctx, "beard")
    H = _head(K)
    style = p.get("style", "stubble")
    jw = K.seg("jaw")
    jx0, jz0, jx1, jz1 = K.ring("jaw", jw["lo"][1], jw["hi"][1])
    lip = H.face_low + 0.02             # 上唇の下端（顔板の下端）
    mst = K.st("beard", "hair", base=K.col, style="short" if style != "stubble" else "buzz",
               skin=K.skin)
    if style == "stubble":
        st = K.st("stubble", "hair", base=_mix(K.col, K.skin, 0.35), style="buzz", skin=K.skin)
        K.box("jaw", jx0 - 0.06, jw["lo"][1] - 0.06, jz0 + 0.25, jx1 + 0.06, lip - 0.25, jz1 - 0.15, st)
        K.box("jaw", -0.85, jw["lo"][1] - 0.07, jz0 - 0.07, 0.85, lip - 0.42, jz0 + 0.5, st)
        return K.done()
    # 口ひげ（上唇の上。head の子）
    mz = H.face_z
    K.box("head", -0.85, lip + 0.02, mz - 0.18, 0.85, lip + 0.36, mz + 0.25, mst)
    if style == "mustache":
        for sgn in (-1, 1):
            K.box("head", sgn * 0.7, lip - 0.35, mz - 0.14, sgn * 0.98, lip + 0.2, mz + 0.2, mst)
        return K.done()
    if style == "goatee":
        K.box("jaw", -0.5, jw["lo"][1] - 0.55, jz0 - 0.16, 0.5, lip - 0.45, jz0 + 0.45, mst)
        return K.done()
    # full: 顎の下へ垂れるひげ + 頬から顎のライン
    K.box("jaw", jx0 - 0.1, jw["lo"][1] - 1.05, jz0 - 0.18, jx1 + 0.1, lip - 0.45, jz0 + 1.1, mst)
    K.box("jaw", jx0 - 0.12, jw["lo"][1] - 0.15, jz0 + 0.9, jx1 + 0.12, lip + 0.2, jz1 + 0.1, mst)
    for sgn in (-1, 1):   # もみあげ
        xa = H.x0 - 0.1 if sgn < 0 else H.x1
        K.box("head", xa, lip + 0.1, H.z0 + 0.7, xa + 0.12, H.face_top - 1.0, H.z0 + 1.6, mst)
    return K.done()


# ===========================================================================
#  上半身
# ===========================================================================
def _pattern(p: dict, cut: str = "") -> Tuple[str, Optional[tuple]]:
    pat = p.get("pattern", "plain")
    if pat == "stripe":
        return ("pinstripe" if cut == "dress" else "stripes"), None
    if pat == "check":
        return ("plaid" if cut in ("flannel", "work") else "check"), None
    if pat == "dots":
        return "print", None
    return "plain", None


def o_shirt(rig, p, ctx):
    K = _K(rig, p, ctx, "shirt")
    L = K.L
    cut = p.get("cut", "dress")
    pat, _ = _pattern(p, cut)
    if cut == "flannel" and p.get("pattern", "plain") == "plain":
        pat = "plaid"
    alt = K.col2 or (_mul(K.col, 0.45) if pat in ("plaid", "check") else _mul(K.col, 0.72))
    st = K.cloth("shirt", pattern=pat, alt=alt, period=1.1 if pat == "pinstripe" else 1.3)
    opn = _lv(p.get("open", 0))
    tucked = bool(p.get("tucked", True))
    o = K.off(TORSO + ARMS, 0.15)
    bt = dict(name="buttons", count=4, u=0.5, colour=(226, 222, 210))
    pk = dict(name="pocket", box=(0.58, 0.18, 0.85, 0.48))
    chest_d = {"north": [pk] + ([bt] if opn == 0 else [])}
    gap_c = (0.0, 0.55, 1.0, 1.5)[opn]
    gap_b = 0.0 if opn < 3 else 0.7
    crop = 0.0
    if K.torn >= 3:
        crop = 1.2 + K.rng.uniform(0, 0.8)
    _torso(K, o, st, gap_chest=gap_c, gap_belly=gap_b, crop=crop, chest_decals=chest_d,
           belly_decals={"north": [dict(bt, count=3)] if opn < 3 else []})
    if not tucked and crop == 0:
        op = K.off(("pelvis",), o)
        tail = 1.1 + K.rng.uniform(0, 0.4)
        K.wrap("pelvis", "pelvis", op, st, y0=L.abdomen_bot - tail, y1=L.abdomen_bot + 0.3)
        if K.torn:
            _hem_rags(K, "pelvis", "pelvis", op, L.abdomen_bot - tail, st, K.n_rags())
    elif K.torn:
        y = K.seg("abdomen")["lo"][1] + crop
        _hem_rags(K, "torso", "abdomen", o, y, st, K.n_rags())
    _collar(K, "shirt" if cut != "blouse" else "crew", o, st, opn)
    if cut == "work":
        for sgn in (-1, 1):   # 胸ポケットの蓋
            x0, z0, x1, z1 = K.ring_at("chest", L.chest_bot + 1.2)
            K.box("chest", sgn * 0.5, L.shoulder_y - 1.5, z0 - o - 0.12, sgn * 1.9, L.shoulder_y - 1.05,
                  z0 - o + 0.02, st)
    want = p.get("sleeves", "long")
    lens = _sleeve_len(K, {"torn_off": "none", "rolled": "elbow"}.get(want, want))
    for s in "rl":
        roll = st if want == "rolled" and lens[s] == "elbow" else None
        _sleeve(K, s, o, st, lens[s], cuff=st, roll=roll)
        if K.torn >= 2 or want == "torn_off":
            _sleeve_rags(K, s, o, st, "cap" if lens[s] == "none" else lens[s],
                         max(1, K.n_rags(0.5)) if K.torn >= 2 or want == "torn_off" else 0)
    return K.done()


_T_PRINTS = ("ROT", "GRAVE", "NOISE", "DEAD AIR", "HOWL")


def o_t_shirt(rig, p, ctx):
    K = _K(rig, p, ctx, "t_shirt")
    L = K.L
    cut = p.get("cut", "crew")
    prn = p.get("print", "none")
    if cut == "jersey" and prn == "none":
        prn = "number"
    ink = K.col2 or _contrast(K.col)
    st = K.cloth("tee", folds=1.2)
    o = K.off(TORSO + (ARMS if cut != "tank" else ()), 0.15)
    front, back = [], []
    if prn == "logo":
        front.append(dict(name="logo", at=(0.5, 0.42), size=0.7, colour=ink,
                          text=K.rng.choice(("NR", "ZX", "OK"))))
    elif prn == "band":
        front.append(dict(name="badge", kind="star", at=(0.5, 0.36), size=0.55, colour=ink))
        front.append(dict(name="text", text=K.rng.choice(_T_PRINTS), at=(0.5, 0.82), colour=ink,
                          wear=0.35))
    elif prn == "number":
        num = str(p.get("number") or K.rng.randint(1, 99))
        front.append(dict(name="number", text=num, at=(0.5, 0.55), colour=ink, wear=0.3))
        back.append(dict(name="number", text=num, at=(0.5, 0.5), colour=ink, wear=0.3))
    crop = 0.0 if K.torn < 3 else 1.0 + K.rng.uniform(0, 1.0)
    uv = K.U["fine"] if prn != "none" else None
    ch = K.seg("chest")
    if cut == "tank":
        # 袖ぐりの大きいタンクトップ: 胸の下部 + 肩ひも 2 本
        cut_y = L.shoulder_y - 1.25
        K.wrap("chest", "chest", o, st, y0=L.chest_bot - 0.05, y1=cut_y,
               decals={"north": front, "south": back}, uv=uv)
        x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
        for sgn in (-1, 1):
            xa, xb = sorted((sgn * 0.75, sgn * 1.75))
            K.box("chest", xa, cut_y - 0.05, z0 - o, xb, ch["hi"][1] + 0.12, z1 + o, st)
        if crop < 9:
            ab = K.seg("abdomen")
            K.wrap("torso", "abdomen", o, st, y0=ab["lo"][1] - 0.05 + crop, y1=L.chest_bot + 0.15)
    else:
        _torso(K, o, st, crop=crop, chest_decals={"north": front, "south": back})
        col_st = K.cloth("tee_rib", base=K.col2 if cut == "jersey" and K.col2 else _mul(K.col, 0.85))
        _collar(K, "v" if cut == "jersey" else "crew", o, col_st)
        lens = _sleeve_len(K, "short" if cut != "jersey" else "elbow")
        for s in "rl":
            _sleeve(K, s, o + (0.08 if cut == "jersey" else 0), st, lens[s], cuff=col_st)
            if K.torn >= 2:
                _sleeve_rags(K, s, o, st, lens[s], K.n_rags(0.4))
    if cut == "jersey" and K.col2:
        for sgn in (-1, 1):   # 脇の線
            x0, z0, x1, z1 = K.ring_at("abdomen", L.chest_bot - 1.0)
            xa = x0 - o - 0.06 if sgn < 0 else x1 + o
            K.box("torso", xa, K.seg("abdomen")["lo"][1] + 0.2, -0.35, xa + 0.06, L.chest_bot + 0.1,
                  0.35, col_st)
    if K.torn:
        y = K.seg("abdomen")["lo"][1] + crop
        _hem_rags(K, "torso", "abdomen", o, y, st, K.n_rags())
    return K.done()


def o_hoodie(rig, p, ctx):
    K = _K(rig, p, ctx, "hoodie")
    L = K.L
    st = K.cloth("hoodie", folds=1.3, wear=0.4)
    rib = K.st("hoodie_rib", "knit", base=_mul(K.col, 0.9), wear=True)
    o = K.off(TORSO + ARMS + ("pelvis",), 0.28)
    zip_ = bool(p.get("zip", False))
    dz = {"north": [dict(name="zipper", u=0.5)]} if zip_ else None
    crop = 0.0 if K.torn < 3 else 0.8
    _torso(K, o, st, chest_decals=dz, belly_decals=dz, crop=crop)
    hem_y = L.abdomen_bot - 0.9
    if crop == 0:
        _skirt(K, o, st, hem_y, decals=dz)
        K.band("pelvis", "pelvis", o + 0.07, hem_y - 0.05, hem_y + 0.4, rib)
        # 腹のポケット
        x0, z0, x1, z1 = K.ring_at("abdomen", L.abdomen_bot + 0.6)
        K.box("torso", -1.75, L.abdomen_bot - 0.2, z0 - o - 0.13, 1.75, L.abdomen_bot + 1.5, z0 - o + 0.02, st)
    if K.torn:
        y = (K.seg("abdomen")["lo"][1] + crop) if crop else hem_y
        _hem_rags(K, "torso" if crop else "pelvis", "abdomen" if crop else "pelvis", o, y, st, K.n_rags())
    lens = _sleeve_len(K, "long")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=rib)
        if K.torn >= 2:
            _sleeve_rags(K, s, o, st, lens[s], K.n_rags(0.4))
    _hood(K, st, p.get("hood", "down"))
    # ひも
    cord = K.st("hoodie_cord", "cloth", base=(220, 220, 214), wear=False, folds=0.0)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    for sgn in (-1, 1):
        K.beam("chest", (sgn * 0.45, ch["hi"][1] - 0.2, z0 - o - 0.12),
               (sgn * 0.5, ch["hi"][1] - 2.0, z0 - o - 0.15), 0.12, 0.1, cord)
    return K.done()


def o_suit_jacket(rig, p, ctx):
    K = _K(rig, p, ctx, "suit_jacket")
    L = K.L
    st = K.cloth("suit", pattern="pinstripe" if K.col2 else "plain", alt=K.col2, folds=0.8, wear=0.3)
    o = K.off(TORSO + ARMS + ("pelvis",), 0.38)
    opn = bool(p.get("open", True))
    gap_c, gap_b = (1.5, 0.9) if opn else (0.0, 0.0)
    btn = dict(name="buttons", count=2, u=0.62 if not opn else 0.85, colour=(26, 24, 24))
    fr = {"r": None, "l": {"north": [dict(btn, u=0.18)]}} if opn else None
    pocket = dict(name="pocket", box=(0.62, 0.15, 0.9, 0.3))
    _torso(K, o, st, gap_chest=gap_c, gap_belly=gap_b,
           chest_decals={"north": [pocket] if not opn else []},
           belly_decals={"north": [btn] if not opn else []}, front_decals=fr)
    # 裾（尻を覆う）と後ろのベント
    skirt_bot = L.crotch - 0.35
    _skirt(K, o, st, skirt_bot, gap=0.5 if opn else 0.0,
           decals={"south": [dict(name="stripe", orient="v", width=0.04, offset=0.5,
                                  colour=_mul(K.col, 0.55))]})
    _pocket_flaps(K, "pelvis", "pelvis", o, L.abdomen_bot - 0.3, st, xs=(-1.55, 1.55), w=1.3, h=0.35)
    if K.torn:
        _hem_rags(K, "pelvis", "pelvis", o, skirt_bot, st, K.n_rags())
    # 襟（立ち襟の後ろ + 胸の V の下襟 2 枚）
    ch = K.seg("chest")
    nk = K.seg("neck")
    nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
    top = ch["hi"][1] + 0.12
    K.box("chest", nx0 - o - 0.1, top - 0.45, nz0 + 0.2, nx1 + o + 0.1, top + 0.55, nz1 + o + 0.1, st)
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    zf = z0 - o
    for sgn in (-1, 1):
        xa = sgn * (gap_c / 2 + 0.05 if opn else 0.15)
        K.box("chest", xa, L.chest_bot + 0.2, zf - 0.13, xa + sgn * 1.05, top - 0.15, zf + 0.02, st,
              rot=(0, 0, sgn * -16), pivot=(xa, L.chest_bot + 0.2, zf))
    if p.get("pocket_square", False):
        sq = K.st("pocket_square", "cloth", base=K.col2 or (236, 236, 230), wear=False, folds=0.0)
        K.box("chest", 1.0, L.shoulder_y - 1.55, zf - 0.16, 1.55, L.shoulder_y - 1.1, zf + 0.0, sq)
    miss = p.get("missing_sleeve", "none")
    lens = _sleeve_len(K, "long")
    for s in "rl":
        if miss in (s, "both"):
            _sleeve_rags(K, s, o, st, "cap", max(2, K.n_rags(0.6)))
            continue
        _sleeve(K, s, o, st, lens[s], cuff=st)
        if K.torn >= 2:
            _sleeve_rags(K, s, o, st, lens[s], K.n_rags(0.4))
    return K.done()


def o_necktie(rig, p, ctx):
    K = _K(rig, p, ctx, "necktie")
    L = K.L
    pat = p.get("pattern", "plain")
    c2 = K.col2 or _mix(K.col, (230, 220, 200), 0.55)
    dec = None
    if pat == "stripe":
        dec = {"north": [dict(name="stripe", orient="d", count=4, width=0.12, gap=0.22, colour=c2)]}
        st = K.cloth("tie", folds=0.3)
    elif pat == "dot":
        st = K.cloth("tie", pattern="print", alt=c2, folds=0.3)
    else:
        st = K.cloth("tie", folds=0.3)
    o = K.off(TORSO, 0.24)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    bx0, bz0, bx1, bz1 = K.ring("abdomen", K.seg("abdomen")["lo"][1], L.chest_bot)
    loose = bool(p.get("loosened", True))
    ky = ch["hi"][1] - (1.35 if loose else 0.35)
    zf = z0 - o
    tilt = K.rng.uniform(4, 10) * (1 if loose else 0.2)
    K.cbox("chest", (0, ky, zf - 0.15), (0.6, 0.55, 0.32), st, rot=(0, 0, tilt))
    K.box("chest", -0.38, L.chest_bot - 0.05, zf - 0.14, 0.38, ky - 0.2, zf + 0.0, st, uv=K.U["fine"],
          decals=dec, rot=(0, 0, tilt * 0.6), pivot=(0, ky, zf))
    tip = K.seg("abdomen")["lo"][1] + 0.6
    K.box("torso", -0.44, tip, bz0 - o - 0.14, 0.44, L.chest_bot + 0.1, bz0 - o + 0.0, st, uv=K.U["fine"],
          decals=dec, rot=(0, 0, tilt * 0.3), pivot=(0, L.chest_bot, bz0 - o))
    K.cbox("torso", (0, tip - 0.05, bz0 - o - 0.07), (0.62, 0.62, 0.12), st, rot=(0, 0, 45 + tilt * 0.3))
    if loose:   # 首の後ろを回る輪（開いた襟から見える）
        nk = K.seg("neck")
        nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
        K.box("chest", nx0 - o, ch["hi"][1] - 0.1, nz0 + 0.3, nx1 + o, ch["hi"][1] + 0.18, nz1 + o, st)
    return K.done()


def o_cardigan(rig, p, ctx):
    K = _K(rig, p, ctx, "cardigan")
    L = K.L
    st = K.st("cardigan", "knit", base=K.col, pattern="stripes" if K.col2 else "plain",
              alt=K.col2 or _mul(K.col, 0.8))
    o = K.off(TORSO + ARMS + ("pelvis",), 0.3)
    nmiss = _lv(p.get("buttons_missing", 0)) if int(p.get("buttons_missing", 0)) < 4 else 4
    nb = max(0, 5 - nmiss)
    fr = {"r": {"north": [dict(name="buttons", count=nb, u=0.85, colour=(90, 70, 50))] if nb else []},
          "l": {"north": [dict(name="pocket", box=(0.25, 0.45, 0.75, 0.85))]}}
    _torso(K, o, st, gap_chest=0.9, gap_belly=0.45, front_decals=fr)
    hem = L.abdomen_bot - 1.2
    _skirt(K, o, st, hem, gap=0.4, front_decals={"r": {"north": [dict(name="pocket", box=(0.3, 0.2, 0.8, 0.7))]},
                                                   "l": {"north": [dict(name="pocket", box=(0.2, 0.2, 0.7, 0.7))]}})
    K.band("pelvis", "pelvis", o + 0.06, hem - 0.04, hem + 0.35, st)
    _collar(K, "v", o, st)
    lens = _sleeve_len(K, "long")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=st)
    if K.torn:
        _hem_rags(K, "pelvis", "pelvis", o, hem, st, K.n_rags())
    return K.done()


def o_leather_jacket(rig, p, ctx):
    K = _K(rig, p, ctx, "leather_jacket")
    L = K.L
    st = K.st("leather_jacket", "leather", base=K.col, wear=0.6)
    o = K.off(TORSO + ARMS, 0.34)
    npatch = max(0, min(3, int(p.get("patches", 0))))
    back = [dict(name="badge", kind="patch", at=(0.5, 0.3 + 0.22 * i), size=0.42,
                 colour=((200, 60, 40), (220, 200, 60), (90, 120, 200))[i]) for i in range(npatch)]
    _torso(K, o, st, chest_decals={"north": [dict(name="zipper", u=0.38)], "south": back[:2]},
           belly_decals={"north": [dict(name="zipper", u=0.38)], "south": back[2:]})
    belt_y = K.seg("abdomen")["lo"][1] - 0.05
    K.band("torso", "abdomen", o + 0.08, belt_y - 0.3, belt_y + 0.35, st)
    # 襟と下襟（大きく折り返す）
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    top = ch["hi"][1] + 0.12
    zf = z0 - o
    nk = K.seg("neck")
    nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
    K.box("chest", nx0 - o - 0.2, top - 0.4, nz0 + 0.1, nx1 + o + 0.2, top + 0.6, nz1 + o + 0.15, st)
    for sgn in (-1, 1):
        K.box("chest", sgn * 0.25, top - 2.4, zf - 0.14, sgn * 1.9, top - 0.1, zf + 0.02, st,
              rot=(0, 0, sgn * -12), pivot=(sgn * 0.25, top - 0.1, zf))
    if p.get("studs", False):
        met = K.st("studs", "chrome", wear=False, base=(200, 200, 204))
        for s, sgn in (("r", -1), ("l", 1)):
            ua = K.seg(f"upper_arm_{s}")
            ax0, az0, ax1, az1 = K.ring(f"upper_arm_{s}", ua["hi"][1] - 1.0, ua["hi"][1])
            for k in range(3):
                zc = -0.7 + 0.7 * k
                K.cbox(f"arm_{s}", ((ax0 + ax1) / 2, ua["hi"][1] + o + 0.12, zc), (0.22, 0.2, 0.22), met)
    sleeveless = bool(p.get("sleeveless", False))
    lens = _sleeve_len(K, "none" if sleeveless else "long")
    for s in "rl":
        if lens[s] == "none":
            if sleeveless or K.torn >= 2:
                _sleeve_rags(K, s, o, st, "cap", 1 if sleeveless else K.n_rags(0.5))
            continue
        _sleeve(K, s, o, st, lens[s], cuff=st)
    return K.done()


def o_rain_jacket(rig, p, ctx):
    K = _K(rig, p, ctx, "rain_jacket")
    L = K.L
    st = K.cloth("rain", folds=1.7, wear=0.15)
    o = K.off(TORSO + ARMS + ("pelvis",), 0.3)
    refl = bool(p.get("reflective", True))
    band = dict(name="stripe", orient="h", width=0.16, offset=0.45, colour=(200, 204, 200), reflective=True)
    zp = dict(name="zipper", u=0.5)
    _torso(K, o, st, chest_decals={"north": [zp] + ([band] if refl else []), "south": [band] if refl else []},
           belly_decals={"north": [zp]})
    hem = L.crotch + 0.2
    _skirt(K, o, st, hem, decals={"north": [zp]})
    if K.torn:
        _hem_rags(K, "pelvis", "pelvis", o, hem, st, K.n_rags())
    lens = _sleeve_len(K, "long")
    sd = {"east": [dict(band, offset=0.3)], "west": [dict(band, offset=0.3)]} if refl else None
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=st, decals=sd)
        if K.torn >= 2:
            _sleeve_rags(K, s, o, st, lens[s], K.n_rags(0.4))
    _hood(K, st, p.get("hood", "down"))
    return K.done()


def o_hi_vis_vest(rig, p, ctx):
    K = _K(rig, p, ctx, "hi_vis_vest")
    L = K.L
    st = K.st("hivis", "hi_vis", base=K.col, bands=(0.3, 0.72), band_h=0.13)
    o = K.off(TORSO, 0.42)
    strip = _c3(p.get("strips", (200, 200, 200)))
    _torso(K, o, st, gap_chest=0.25, gap_belly=0.25)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    # 肩の反射帯（前から後ろへ）
    tape = K.st("hivis_tape", "cloth", base=strip, wear=True, folds=0.2)
    for sgn in (-1, 1):
        xa, xb = sorted((sgn * 0.9, sgn * 1.55))
        K.box("chest", xa, ch["hi"][1] + 0.05, z0 - o - 0.04, xb, ch["hi"][1] + 0.24, z1 + o + 0.04, tape)
    if K.torn:
        _hem_rags(K, "torso", "abdomen", o, K.seg("abdomen")["lo"][1], st, K.n_rags())
    return K.done()


def o_police_uniform(rig, p, ctx):
    K = _K(rig, p, ctx, "police_uniform")
    L = K.L
    guard = p.get("style", "police") == "guard"
    st = K.cloth("uniform", folds=0.8)
    o = K.off(TORSO + ARMS, 0.15)
    _torso(K, o, st, chest_decals={"north": [dict(name="buttons", count=3, u=0.5, colour=(40, 40, 46)),
                                             dict(name="pocket", box=(0.12, 0.2, 0.4, 0.5)),
                                             dict(name="pocket", box=(0.6, 0.2, 0.88, 0.5))]},
           belly_decals={"north": [dict(name="buttons", count=2, u=0.5, colour=(40, 40, 46))]})
    _collar(K, "shirt", o, st)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    zf = z0 - o
    _pocket_flaps(K, "chest", "chest", o, L.shoulder_y - 1.25, st, xs=(-1.25, 1.25), w=1.2, h=0.36)
    # 肩章
    for sgn in (-1, 1):
        xa, xb = sorted((sgn * 1.1, sgn * (x1 + o)))
        K.box("chest", xa, ch["hi"][1] + 0.0, -0.45, xb, ch["hi"][1] + 0.2, 0.45, st)
    if p.get("badge", True):
        if guard:
            plate = K.st("guard_patch", "cloth", base=(30, 32, 36), wear=True, folds=0.0)
            _label(K, "chest", (1.25, L.shoulder_y - 2.0, zf - 0.12), 1.6, 0.6, "north", "SECURITY",
                   (230, 220, 120), plate)
        else:
            gold = K.st("police_badge", "chrome", wear=False, base=(214, 180, 90))
            K.cbox("chest", (1.25, L.shoulder_y - 1.05, zf - 0.14), (0.62, 0.72, 0.1), gold, uv=K.U["face"],
                   decals={"north": [dict(name="badge", kind="star", at=(0.5, 0.5), size=0.9, colour=(220, 190, 100))]})
    patch = {"west" if True else "east": [dict(name="badge", kind="shield" if not guard else "patch",
                                                 at=(0.5, 0.25), size=0.55, colour=(200, 170, 70) if not guard
                                                 else (200, 200, 60))]}
    for s in "rl":
        sd = {"west": patch["west"]} if s == "l" else {"east": patch["west"]}
        _sleeve(K, s, o, st, "long" if not guard else "short", cuff=st, decals=sd)
    if p.get("radio", True):
        rad = K.st("radio", "plastic", base=(26, 26, 28), wear=True)
        K.cbox("chest", (1.6, L.shoulder_y - 0.35, zf - 0.25), (0.6, 0.9, 0.4), rad)
        K.beam("chest", (1.75, L.shoulder_y + 0.05, zf - 0.25), (1.85, L.shoulder_y + 0.9, zf - 0.2), 0.1, 0.1, rad)
    if p.get("belt", True):
        bl = K.st("duty_belt", "leather", base=(18, 18, 20), wear=True)
        met = K.st("duty_metal", "chrome", wear=False, base=(170, 170, 176))
        ob = K.off(("pelvis",), 0.32)
        _belt(K, ob, bl, met, h=0.55)
        px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot)
        yb = L.abdomen_bot + 0.1
        if not guard:
            # ホルスター（右腰）と銃把
            K.box("pelvis", px0 - ob - 0.45, yb - 1.9, -0.55, px0 - ob + 0.05, yb + 0.2, 0.45, bl)
            K.box("pelvis", px0 - ob - 0.4, yb + 0.15, -0.45, px0 - ob - 0.02, yb + 0.75, 0.1, bl)
            # 手錠のケース（腰の後ろ）
            K.cbox("pelvis", (-0.9, yb, pz1 + ob + 0.2), (0.8, 0.6, 0.35), bl)
        # 警棒・懐中電灯（左腰）
        K.beam("pelvis", (px1 + ob + 0.15, yb + 0.3, -0.3), (px1 + ob + 0.3, yb - 2.8, -0.55), 0.24, 0.24, bl)
        K.cbox("pelvis", (px1 + ob + 0.15, yb, 0.6), (0.4, 0.6, 0.5), bl)
    return K.done()


def o_chef_coat(rig, p, ctx):
    K = _K(rig, p, ctx, "chef_coat")
    L = K.L
    st = K.cloth("chef", folds=0.9, wear=0.2)
    o = K.off(TORSO + ARMS + ("pelvis",), 0.22)
    dbl = bool(p.get("double_breasted", True))
    btn_c = _mul(K.col, 0.92)
    bt = [dict(name="buttons", count=3, u=0.3, colour=btn_c), dict(name="buttons", count=3, u=0.7, colour=btn_c)] \
        if dbl else [dict(name="buttons", count=4, u=0.5, colour=btn_c)]
    _torso(K, o, st, chest_decals={"north": bt}, belly_decals={"north": bt})
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    if dbl:   # 前の重なり（左前が右へ被さる）
        K.box("chest", -0.6, L.chest_bot - 0.05, z0 - o - 0.1, x1 + o - 0.15, ch["hi"][1] - 0.3, z0 - o + 0.01, st,
              decals={"north": [dict(name="buttons", count=3, u=0.12, colour=btn_c)]})
    hem = L.crotch + 0.4
    _skirt(K, o, st, hem)
    _collar(K, "band", o, st)
    roll = bool(p.get("rolled_sleeves", False))
    lens = _sleeve_len(K, "elbow" if roll else "long")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=st, roll=st if roll and lens[s] == "elbow" else None)
    if K.torn:
        _hem_rags(K, "pelvis", "pelvis", o, hem, st, K.n_rags())
    return K.done()


def o_apron(rig, p, ctx):
    K = _K(rig, p, ctx, "apron")
    L = K.L
    kind = p.get("kind", "cloth")
    stains = _lv(p.get("stains", 1))
    blood = max(_BLOOD[K.bloody], (0.1, 0.5, 1.1, 2.0)[stains])
    if kind == "butcher_leather":
        st = K.st("apron", "leather", base=K.col, blood=blood, wear=0.5)
    elif kind == "rubber":
        st = K.st("apron", "rubber", base=K.col, blood=blood)
    else:
        st = K.cloth("apron", folds=1.1, blood=blood)
    tie = K.st("apron_tie", "cloth", base=_mul(K.col, 0.8) if kind == "cloth" else (200, 196, 186), wear=True,
               folds=0.2)
    full = p.get("length", "waist") == "full"
    o = K.off(("pelvis",) + TORSO, 0.45)
    th = 0.16 if kind == "cloth" else 0.24
    py = L.abdomen_bot + 0.2
    px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot - 0.5)
    w = max(px1, -px0) + 0.2
    bot = (L.knee_y - 1.2) if full else (L.knee_y + 1.6)
    zf = pz0 - o
    K.box("pelvis", -w, bot, zf - th, w, py, zf, st, decals={"north": [dict(name="pocket", box=(0.3, 0.15, 0.7, 0.32))]}
          if kind == "cloth" else None)
    K.band("pelvis", "pelvis", o, py - 0.35, py, tie)
    K.beam("pelvis", (0.0, py - 0.15, pz1 + o + 0.05), (0.35, py - 1.3, pz1 + o + 0.35), 0.25, 0.08, tie)
    if K.torn:
        K.rags("pelvis", -w, w, zf - th, zf, bot, st, K.n_rags(), sides="n")
    if full:
        ch = K.seg("chest")
        cx0, cz0, cx1, cz1 = K.ring("chest", L.chest_bot, ch["hi"][1])
        bx0, bz0, bx1, bz1 = K.ring("abdomen", K.seg("abdomen")["lo"][1], L.chest_bot)
        K.box("torso", -1.7, K.seg("abdomen")["lo"][1], bz0 - o - th, 1.7, L.chest_bot + 0.15, bz0 - o, st)
        top = ch["hi"][1] - 0.6
        K.box("chest", -1.6, L.chest_bot - 0.05, cz0 - o - th, 1.6, top, cz0 - o, st)
        for sgn in (-1, 1):   # 首ひも
            K.beam("chest", (sgn * 1.4, top - 0.05, cz0 - o - th / 2), (sgn * 0.9, ch["hi"][1] + 0.25, 0.4), 0.22, 0.08, tie)
    return K.done()


def o_hospital_gown(rig, p, ctx):
    K = _K(rig, p, ctx, "hospital_gown")
    L = K.L
    pat = "print" if p.get("pattern", "dots") == "dots" else "plain"
    st = K.cloth("gown", pattern=pat, alt=_mul(K.col, 0.62), folds=1.4, period=0.9)
    o = K.off(TORSO + ARMS + ("pelvis",), 0.16)
    back = bool(p.get("open_back", True))
    _torso(K, o, st, gap_chest=0.9 if back else 0.0, gap_belly=1.4 if back else 0.0, gap_side="s")
    hem = L.knee_y + 0.7 - (0.6 if K.torn >= 2 else 0.0)
    _skirt(K, o, st, hem, gap=1.6 if back else 0.0, gap_side="s", flare=0.15)
    if K.torn:
        _hem_rags(K, "pelvis", "pelvis", o + 0.15, hem, st, K.n_rags(1.3), length=(0.5, 1.6))
    if back:   # 背中の結びひも
        tie = K.st("gown_tie", "cloth", base=_mul(K.col, 0.9), wear=True, folds=0.0)
        ch = K.seg("chest")
        x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
        for yy in (ch["hi"][1] - 0.8, L.chest_bot + 0.6):
            K.beam("chest", (-0.4, yy, z1 + o + 0.05), (0.5, yy - 0.9, z1 + o + 0.25), 0.15, 0.08, tie)
    _collar(K, "crew", o, st)
    lens = _sleeve_len(K, "short")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=st)
    if p.get("iv_line", False):
        fx0, fz0, fx1, fz1 = K.ring_at("forearm_l", L.wrist_y + 1.5)
        tape = K.st("iv_tape", "cloth", base=(232, 230, 222), wear=True, folds=0.0)
        tube = K.st("iv_tube", "glass", wear=False, base=(200, 214, 220))
        y = L.wrist_y + 1.6
        K.box("forearm_l", fx0 + 0.2, y - 0.45, fz0 - 0.12, fx1 - 0.2, y + 0.45, fz0 + 0.1, tape)
        K.cbox("forearm_l", ((fx0 + fx1) / 2, y + 0.2, fz0 - 0.2), (0.3, 0.3, 0.3), tube)
        K.beam("forearm_l", ((fx0 + fx1) / 2, y + 0.2, fz0 - 0.25), ((fx0 + fx1) / 2 + 0.6, y - 3.2, fz0 - 0.9),
               0.12, 0.12, tube)
    if p.get("wrist_tag", True):
        tag = K.st("wrist_tag", "plastic", base=(236, 236, 232), wear=True)
        K.band("forearm_l", "forearm_l", 0.08, L.wrist_y + 0.15, L.wrist_y + 0.5, tag, uv=K.U["face"],
               decals={"west": [dict(name="text", text="ID", at=(0.5, 0.5), colour=(40, 40, 60), wear=0.1)]})
    return K.done()


def o_scrubs(rig, p, ctx):
    K = _K(rig, p, ctx, "scrubs")
    L = K.L
    st = K.cloth("scrubs", folds=1.0, wear=0.2)
    o = K.off(TORSO + ARMS, 0.15)
    _torso(K, o, st, chest_decals={"north": [dict(name="pocket", box=(0.6, 0.3, 0.85, 0.6))]})
    _collar(K, "v", o, st)
    gown = bool(p.get("gown", False))
    for s in "rl":
        _sleeve(K, s, o, st, "short", cuff=st)
    ol = K.off(("pelvis",) + LEGS, 0.15)
    _legs(K, ol, st, hem=st, pelvis_decals={"north": [dict(name="stripe", orient="v", width=0.04, offset=0.5,
                                                            colour=_mul(K.col, 0.7))]})
    if gown:
        gst = K.cloth("surgical_gown", base=_mix(K.col, (210, 220, 220), 0.45), folds=1.5)
        og = K.off(TORSO + ARMS + ("pelvis",), 0.3)
        _torso(K, og, gst, gap_chest=0.7, gap_belly=1.0, gap_side="s")
        hem = L.knee_y + 0.4
        _skirt(K, og, gst, hem, gap=1.2, gap_side="s", flare=0.2)
        lens = _sleeve_len(K, "long")
        for s in "rl":
            _sleeve(K, s, og, gst, lens[s], cuff=K.st("gown_cuff", "knit", base=_mul(K.col, 0.8)))
        _collar(K, "crew", og, gst)
        if K.torn:
            _hem_rags(K, "pelvis", "pelvis", og, hem, gst, K.n_rags())
    if p.get("stethoscope", False):
        tube = K.st("stetho", "rubber", base=(30, 30, 34), wear=False)
        met = K.st("stetho_metal", "chrome", wear=False, base=(200, 202, 206))
        ch = K.seg("chest")
        x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
        oo = K.off(("chest",), 0.35)
        top = ch["hi"][1] + 0.15
        K.box("chest", -1.25, top - 0.15, -0.6, 1.25, top + 0.12, z1 - 0.5, tube)          # 首の後ろ
        for sgn in (-1, 1):
            K.beam("chest", (sgn * 1.2, top, -0.5), (sgn * 0.75, L.chest_bot + 0.6, z0 - oo - 0.1), 0.14, 0.14, tube)
        K.cbox("chest", (0.75, L.chest_bot + 0.45, z0 - oo - 0.18), (0.5, 0.5, 0.22), met)
    return K.done()


def _coverall(K: _K, st: str, *, rolled: bool, chest_label: Optional[str] = None,
              back_label: Optional[str] = None, label_col=(30, 30, 30), plate_st: Optional[str] = None) -> None:
    """つなぎ（作業着・囚人服）の共通の形。rolled = 上半身を脱いで袖を腰で結ぶ。"""
    L = K.L
    ol = K.off(("pelvis",) + LEGS, 0.18)
    _legs(K, ol, st, hem=st, thigh_decals={"north": [dict(name="pocket", box=(0.2, 0.15, 0.8, 0.45))]})
    if rolled:
        _tied_sleeves(K, st, ol + 0.1)
        return
    o = K.off(TORSO + ARMS, ol)
    _torso(K, o, st, chest_decals={"north": [dict(name="zipper", u=0.5)]},
           belly_decals={"north": [dict(name="zipper", u=0.5)]})
    _collar(K, "shirt", o, st)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    if chest_label:
        _label(K, "chest", (-1.2, L.shoulder_y - 1.3, z0 - o - 0.05), 1.5, 0.55, "north", chest_label,
               label_col, plate_st or st)
    if back_label:
        _label(K, "chest", (0, L.shoulder_y - 1.6, z1 + o + 0.02), 2.6, 0.75, "south", back_label,
               label_col, plate_st or st)
    lens = _sleeve_len(K, "long")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=st)
        if K.torn >= 2:
            _sleeve_rags(K, s, o, st, lens[s], K.n_rags(0.4))
    K.band("torso", "abdomen", o + 0.06, K.seg("abdomen")["lo"][1] + 0.1, K.seg("abdomen")["lo"][1] + 0.5, st)


def o_coveralls(rig, p, ctx):
    K = _K(rig, p, ctx, "coveralls")
    st = K.cloth("coveralls", folds=1.0, wear=0.45)
    plate = K.st("name_patch", "cloth", base=(232, 230, 222), wear=True, folds=0.0)
    name = K.rng.choice(("JOE", "SAM", "RAY", "LEE", "TED", "KEN"))
    _coverall(K, st, rolled=bool(p.get("rolled_top", False)),
              chest_label=name if p.get("name_patch", True) else None, label_col=(160, 30, 30),
              plate_st=plate)
    return K.done()


def o_prison_jumpsuit(rig, p, ctx):
    K = _K(rig, p, ctx, "prison_jumpsuit")
    st = K.cloth("jumpsuit", folds=1.0, wear=0.35)
    num = str(p.get("number", "0000"))[:6]
    _coverall(K, st, rolled=bool(p.get("top_tied_waist", False)), chest_label=num, back_label="INMATE",
              label_col=(24, 24, 24))
    return K.done()


def _camo(p: dict, col, col2):
    pat = p.get("pattern", "woodland")
    if pat == "urban":
        return dict(base=col, alt=col2 or (60, 62, 58), alt2=(32, 32, 34), alt3=(176, 176, 170))
    if pat == "desert":
        return dict(base=(192, 170, 128), alt=(150, 122, 86), alt2=(112, 92, 66), alt3=(214, 202, 172))
    return dict(base=(86, 92, 60), alt=(52, 62, 40), alt2=(32, 30, 24), alt3=(122, 106, 72))


def o_camo_fatigues(rig, p, ctx):
    K = _K(rig, p, ctx, "camo_fatigues")
    L = K.L
    cm = _camo(p, K.col, K.col2)
    st = K.cloth("camo", pattern="camo", alt=cm["alt"], base=cm["base"], alt2=cm["alt2"], alt3=cm["alt3"],
                 folds=1.1)
    ol = K.off(("pelvis",) + LEGS, 0.16)
    _legs(K, ol, st, hem=st)
    for s in "rl":   # 腿の横のポケット
        th = K.seg(f"thigh_{s}")
        x0, z0, x1, z1 = K.ring_at(f"thigh_{s}", th["lo"][1] + 2.0)
        sgn = -1 if s == "r" else 1
        xa = (x0 - ol - 0.28) if sgn < 0 else (x1 + ol)
        K.box(f"leg_{s}", xa, th["lo"][1] + 1.0, -0.75, xa + 0.28, th["lo"][1] + 2.6, 0.75, st)
    bl = K.st("web_belt", "kevlar", base=(50, 50, 42), wear=True)
    _belt(K, ol + 0.06, bl, K.st("belt_buckle", "metal", base=(120, 120, 110), wear=0.5))
    o = K.off(TORSO + ARMS, ol)
    _torso(K, o, st, chest_decals={"north": [dict(name="buttons", count=4, u=0.5, colour=(40, 40, 36))]})
    _pocket_flaps(K, "chest", "chest", o, L.shoulder_y - 1.2, st, xs=(-1.25, 1.25), w=1.25, h=0.42)
    _collar(K, "shirt", o, st)
    lens = _sleeve_len(K, "long")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=st)
        if K.torn >= 2:
            _sleeve_rags(K, s, o, st, lens[s], K.n_rags(0.4))
    return K.done()


def o_firefighter_coat(rig, p, ctx):
    K = _K(rig, p, ctx, "firefighter_coat")
    L = K.L
    st = K.cloth("turnout", folds=1.2, wear=0.5)
    bc = _c3(p.get("bands", (220, 220, 90)))
    band = dict(name="stripe", orient="h", count=2, width=0.09, gap=0.04, offset=0.62, colour=bc, reflective=True)
    if p.get("pants", True):
        ol = K.off(("pelvis",) + LEGS, 0.4)
        _legs(K, ol, st, hem=st, shin_decals=[{"north": [dict(band, offset=0.5)], "south": [dict(band, offset=0.5)],
                                               "east": [dict(band, offset=0.5)], "west": [dict(band, offset=0.5)]}, None])
    o = K.off(TORSO + ARMS + ("pelvis",), 0.55)
    clasp = dict(name="stripe", orient="v", width=0.05, offset=0.5, colour=(30, 28, 24))
    _torso(K, o, st, chest_decals={"north": [band, clasp], "south": [band]},
           belly_decals={"north": [clasp]})
    hem = L.crotch - 1.1
    _skirt(K, o, st, hem, decals={"north": [dict(band, offset=0.82), clasp], "south": [dict(band, offset=0.82)],
                                  "east": [dict(band, offset=0.82)], "west": [dict(band, offset=0.82)]})
    _pocket_flaps(K, "pelvis", "pelvis", o, L.abdomen_bot - 0.4, st, xs=(-1.6, 1.6), w=1.5, h=0.55)
    met = K.st("turnout_clasp", "chrome", wear=False, base=(170, 170, 160))
    x0, z0, x1, z1 = K.ring_at("abdomen", L.chest_bot - 1.0)
    for k in range(3):
        K.cbox("torso" if k < 2 else "chest", (0.0, L.abdomen_bot + 1.0 + 1.6 * k, z0 - o - 0.08 if k < 2 else
                                               K.ring("chest", L.chest_bot, L.shoulder_y)[1] - o - 0.08),
               (0.55, 0.22, 0.16), met)
    if p.get("collar_up", True):
        _collar(K, "turtle", o, st)
    else:
        _collar(K, "band", o, st)
    sd = {f: [dict(band, offset=0.25)] for f in ("north", "south", "east", "west")}
    lens = _sleeve_len(K, "long")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=st, decals=[None, sd])
    if K.torn:
        _hem_rags(K, "pelvis", "pelvis", o, hem, st, K.n_rags())
    return K.done()


def o_hazmat_suit(rig, p, ctx):
    K = _K(rig, p, ctx, "hazmat_suit")
    L = K.L
    st = K.cloth("hazmat", folds=1.9, wear=0.15)
    tape = K.st("hazmat_tape", "plastic", base=(150, 150, 146), wear=True) if p.get("taped", True) else None
    ol = K.off(("pelvis",) + LEGS, 0.5)
    out = _legs(K, ol, st, hem=tape)
    o = K.off(TORSO + ARMS, 0.55)
    _torso(K, o, st, chest_decals={"north": [dict(name="zipper", u=0.5),
                                             dict(name="badge", kind="circle", at=(0.75, 0.3), size=0.35,
                                                  colour=(30, 30, 30))]},
           belly_decals={"north": [dict(name="zipper", u=0.5)]})
    _skirt(K, o, st, L.abdomen_bot - 1.0)
    lens = _sleeve_len(K, "long")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s], cuff=tape)
        if K.torn >= 2:
            _sleeve_rags(K, s, o, st, lens[s], K.n_rags(0.4))
    if p.get("hood", True):
        H = _head(K)
        oh = K.off(("head",), 0.45)
        x0, x1, z0, z1 = H.x0 - oh, H.x1 + oh, H.z0 - oh, H.z1 + oh
        top = H.top + oh + 0.15
        fz = H.face_z - 0.55
        K.box("head", x0, H.brow + 0.2, fz, x1, top, z1, st)                             # 天井と額
        K.box("head", x0, H.jaw_low - 1.0, H.cz - 0.4, x1, H.brow + 0.3, z1, st)          # 後ろと横
        K.box("head", x0, H.jaw_low - 1.0, fz, x1, H.jaw_low - 0.15, H.cz - 0.3, st)      # 顎の下
        for sgn in (-1, 1):
            xa, xb = (x0, x0 + 0.35) if sgn < 0 else (x1 - 0.35, x1)
            K.box("head", xa, H.jaw_low - 0.2, fz + 0.2, xb, H.brow + 0.25, H.cz - 0.3, st)
        fog = _lv(p.get("visor_fog", 1))
        glass = K.st("hazmat_visor", "glass", wear=False, base=_mix((150, 170, 170), (226, 226, 220), fog / 3.0))
        _visor_frame(K, "head", x0 + 0.35, x1 - 0.35, H.jaw_low - 0.15, H.brow + 0.25, fz + 0.18,
                     tape or st, glass, cracked=fog)
    if K.torn:
        _hem_rags(K, "torso", "abdomen", o, K.seg("abdomen")["lo"][1], st, K.n_rags())
    return K.done()


def o_riot_armor(rig, p, ctx):
    K = _K(rig, p, ctx, "riot_armor")
    L = K.L
    full = p.get("coverage", "full") == "full"
    text = str(p.get("text", "POLICE"))
    plate = K.st("riot_plate", "plastic", base=K.col, wear=0.6)
    vest = K.st("riot_vest", "kevlar", base=_mix(K.col, (40, 44, 40), 0.3), pattern="molle")
    strap = K.st("riot_strap", "kevlar", base=(20, 20, 22), wear=True)
    white = _c3((232, 232, 226))
    o = K.off(TORSO, 0.45)
    bc, bb = K.armor("torso", "chest"), K.armor("torso", "belly")
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    bx0, bz0, bx1, bz1 = K.ring("abdomen", K.seg("abdomen")["lo"][1], L.chest_bot)
    top = ch["hi"][1] + 0.1
    K.box(bc, x0 - o, L.chest_bot - 0.1, z0 - o, x1 + o, top, z1 + o, vest)
    K.box(bb, bx0 - o, K.seg("abdomen")["lo"][1] - 0.2, bz0 - o, bx1 + o, L.chest_bot + 0.2, bz1 + o, vest)
    # 胸・腹・背中の板
    K.box(bc, x0 - o + 0.2, L.chest_bot + 0.1, z0 - o - 0.32, x1 + o - 0.2, top - 0.5, z0 - o, plate)
    _label(K, bc, (0, L.chest_bot + 1.0, z0 - o - 0.32), 2.4, 0.6, "north", text, white, plate)
    K.box(bb, -1.9, K.seg("abdomen")["lo"][1] + 0.1, bz0 - o - 0.3, 1.9, L.chest_bot - 0.05, bz0 - o, plate)
    K.box(bc, x0 - o + 0.2, L.chest_bot - 0.3, z1 + o, x1 + o - 0.2, top - 0.3, z1 + o + 0.3, plate)
    _label(K, bc, (0, L.chest_bot + 1.5, z1 + o + 0.3), 3.0, 0.8, "south", text, white, plate)
    # 襟（首の後ろ）
    nk = K.seg("neck")
    nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
    K.box(bc, nx0 - 0.45, top - 0.2, nz0 + 0.3, nx1 + 0.45, top + 0.75, nz1 + 0.5, vest)
    if not full:
        return K.done()
    for s, sgn in (("r", -1), ("l", 1)):
        ua, fa = K.seg(f"upper_arm_{s}"), K.seg(f"forearm_{s}")
        ba, bf = K.armor(f"arm_{s}", "upper"), K.armor(f"arm_{s}", "fore")
        oa = K.off((f"upper_arm_{s}", f"forearm_{s}"), 0.3)
        ax0, az0, ax1, az1 = K.ring(f"upper_arm_{s}", ua["hi"][1] - 1.5, ua["hi"][1])
        # 肩当て（2 段）
        K.box(ba, ax0 - oa - 0.15, ua["hi"][1] - 1.7, az0 - oa - 0.2, ax1 + oa + 0.15, ua["hi"][1] + 0.45,
              az1 + oa + 0.2, plate)
        K.box(ba, ax0 - oa - 0.3, ua["hi"][1] - 2.7, az0 - oa - 0.1, ax1 + oa + 0.3, ua["hi"][1] - 1.5,
              az1 + oa + 0.1, plate, rot=(0, 0, sgn * 8), pivot=((ax0 + ax1) / 2, ua["hi"][1] - 1.6, 0))
        # 前腕の当て板 + 帯
        fx0, fz0, fx1, fz1 = K.ring(f"forearm_{s}", fa["lo"][1], fa["hi"][1])
        K.box(bf, fx0 - oa - 0.1, L.wrist_y + 0.4, fz0 - oa - 0.25, fx1 + oa + 0.1, fa["hi"][1] - 0.4, fz1 + oa,
              plate)
        K.band(bf, f"forearm_{s}", oa + 0.3, L.wrist_y + 1.2, L.wrist_y + 1.5, strap)
        # 腿の板・膝・脛当て
        th, sh = K.seg(f"thigh_{s}"), K.seg(f"shin_{s}")
        bl, bs = K.armor(f"leg_{s}", "upper"), K.armor(f"leg_{s}", "shin")
        ol = K.off((f"thigh_{s}", f"shin_{s}"), 0.4)
        tx0, tz0, tx1, tz1 = K.ring(f"thigh_{s}", th["lo"][1], th["hi"][1])
        K.box(bl, tx0 - ol + 0.1, L.knee_y + 1.2, tz0 - ol - 0.28, tx1 + ol - 0.1, th["hi"][1] - 1.2, tz0 - ol, plate)
        K.band(bl, f"thigh_{s}", ol, L.knee_y + 2.6, L.knee_y + 2.95, strap)
        sx0, sz0, sx1, sz1 = K.ring(f"shin_{s}", sh["lo"][1], sh["hi"][1])
        K.box(bs, sx0 - ol, L.ankle_y + 0.9, sz0 - ol - 0.3, sx1 + ol, sh["hi"][1] - 0.3, sz0 - ol + 0.2, plate)
        K.cbox(bs, ((sx0 + sx1) / 2, sh["hi"][1] + 0.05, sz0 - ol - 0.2), (sx1 - sx0 + 0.5, 1.2, 0.6), plate)
        K.band(bs, f"shin_{s}", ol + 0.32, L.ankle_y + 2.5, L.ankle_y + 2.8, strap)
    return K.done()


def o_military_vest(rig, p, ctx):
    K = _K(rig, p, ctx, "military_vest")
    L = K.L
    st = K.st("plate_carrier", "kevlar", base=K.col, pattern="molle")
    pouch = K.st("mag_pouch", "kevlar", base=_mul(K.col, 0.92), pattern="plain")
    o = K.off(TORSO, 0.5)
    bc, bb = K.armor("torso", "chest"), K.armor("torso", "belly")
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    bx0, bz0, bx1, bz1 = K.ring("abdomen", K.seg("abdomen")["lo"][1], L.chest_bot)
    top = ch["hi"][1] - 0.5
    plates = bool(p.get("plates", True))
    th = 0.45 if plates else 0.25
    # 前と後ろの板（胸から腹の上まで）
    K.box(bc, x0 + 0.15, L.chest_bot - 0.3, z0 - o - th, x1 - 0.15, top, z0 - o, st)
    K.box(bc, x0 + 0.15, L.chest_bot - 0.3, z1 + o, x1 - 0.15, top + 0.3, z1 + o + th, st)
    # 腹巻き（カマーバンド）
    K.box(bb, bx0 - o, L.abdomen_bot + 0.6, bz0 - o, bx1 + o, L.chest_bot + 0.1, bz1 + o, st)
    # 肩ひも
    for sgn in (-1, 1):
        xa, xb = sorted((sgn * 0.8, sgn * 1.7))
        K.box(bc, xa, top - 0.2, z0 - o - 0.1, xb, ch["hi"][1] + o + 0.2, z1 + o + 0.1, st)
    n = max(0, min(8, int(p.get("pouches", 6))))
    per = 3 if n > 4 else max(1, n)
    for i in range(n):
        row, col = divmod(i, per)
        xc = (col - (per - 1) / 2) * 1.05
        if row == 0:
            K.cbox(bb, (xc, L.abdomen_bot + 1.25, bz0 - o - 0.32), (0.9, 1.15, 0.6), pouch,
                   decals={"north": [dict(name="stripe", orient="h", width=0.14, offset=0.15, colour=_mul(K.col, 0.7))]})
        else:
            K.cbox(bc, (xc, L.chest_bot + 0.55, z0 - o - th - 0.25), (0.9, 1.0, 0.5), pouch)
    if p.get("radio", True):
        rad = K.st("mil_radio", "plastic", base=(40, 42, 36), wear=True)
        K.cbox(bc, (-1.3, top - 0.6, z0 - o - th - 0.25), (0.6, 1.0, 0.45), rad)
        K.beam(bc, (-1.4, top - 0.1, z0 - o - th - 0.25), (-1.6, top + 1.6, z0 - o - th), 0.08, 0.08, rad)
    return K.done()


def _dress_skirt(K: _K, st: str, o: float, y_bot: float, tiers: int, flare: float, gap_s: float = 0.0) -> list:
    """段になって広がるスカート（pelvis の子）。上の段ほど細い。"""
    L = K.L
    out = []
    y_top = L.abdomen_bot + 0.25
    h = (y_top - y_bot) / tiers
    for i in range(tiers):
        yb = y_top - h * (i + 1) - (0.05 if i < tiers - 1 else 0.0)
        yt = y_top - h * i + (0.15 if i else 0.0)
        out += _skirt(K, o + flare * i * 0.5, st, yb, yt, flare=flare * i * 0.5,
                      gap=gap_s if i == tiers - 1 else 0.0)
    return out


def _aline(K: _K, st: str, o: float, y_bot: float, flare: float, y_top: Optional[float] = None,
           slit: float = 0.0) -> list:
    """裾が広がるスカート（pelvis の子）: 腰の芯 + 腰から下がる前後左右の 4 枚を外へ傾ける。
    flare = 裾での広がり（単位）。slit > 0 で前の板を左右に分けて切れ込みを作る。"""
    L = K.L
    y_top = L.abdomen_bot + 0.25 if y_top is None else y_top
    pv = K.seg("pelvis")
    x0, z0, x1, z1 = K.ring_at("pelvis", L.abdomen_bot - 0.5)
    x0, z0, x1, z1 = x0 - o, z0 - o, x1 + o, z1 + o
    ln = max(0.5, y_top - y_bot)
    a = round(math.degrees(math.atan2(flare, ln)), 2)
    th = 0.16
    w = flare * 0.55                 # 前後の板を少し広げて裾の角の隙間を塞ぐ
    out = [K.box("pelvis", x0, pv["lo"][1] - 0.2, z0, x1, y_top, z1, st)]
    if slit > 0:
        for sx0, sx1 in ((x0 - w, -slit / 2), (slit / 2, x1 + w)):
            out.append(K.box("pelvis", sx0, y_bot, z0 - th, sx1, y_top, z0, st, rot=(-a, 0, 0),
                             pivot=(0, y_top, z0)))
    else:
        out.append(K.box("pelvis", x0 - w, y_bot, z0 - th, x1 + w, y_top, z0, st, rot=(-a, 0, 0),
                         pivot=(0, y_top, z0)))
    out.append(K.box("pelvis", x0 - w, y_bot, z1, x1 + w, y_top, z1 + th, st, rot=(a, 0, 0), pivot=(0, y_top, z1)))
    out.append(K.box("pelvis", x0 - th, y_bot, z0, x0, y_top, z1, st, rot=(0, 0, a), pivot=(x0, y_top, 0)))
    out.append(K.box("pelvis", x1, y_bot, z0, x1 + th, y_top, z1, st, rot=(0, 0, -a), pivot=(x1, y_top, 0)))
    return out


def o_torn_dress(rig, p, ctx):
    K = _K(rig, p, ctx, "torn_dress")
    L = K.L
    style = p.get("style", "wedding")
    floor = p.get("length", "floor") == "floor"
    pat = "print" if style == "sundress" else "plain"
    st = K.cloth("dress", pattern=pat, alt=K.col2 or _mix(K.col, (200, 60, 60), 0.5), folds=1.4,
                 wear=0.2)
    o = K.off(TORSO, 0.15)
    ch = K.seg("chest")
    # 胸当て（肩は出す）
    cut_y = L.shoulder_y - (0.9 if style != "sundress" else 1.1)
    K.wrap("chest", "chest", o, st, y0=L.chest_bot - 0.05, y1=cut_y)
    ab = K.seg("abdomen")
    K.wrap("torso", "abdomen", o, st, y0=ab["lo"][1] - 0.05, y1=L.chest_bot + 0.15)
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    if style == "sundress":
        for sgn in (-1, 1):
            xa, xb = sorted((sgn * 0.9, sgn * 1.3))
            K.box("chest", xa, cut_y - 0.05, z0 - o, xb, ch["hi"][1] + 0.1, z1 + o, st)
    elif style == "wedding":   # レースの縁
        lace = K.cloth("dress_lace", base=_mul(K.col, 0.96), pattern="check", alt=_mul(K.col, 0.82),
                       period=0.35, folds=0.3)
        K.box("chest", x0 - o - 0.08, cut_y - 0.3, z0 - o - 0.08, x1 + o + 0.08, cut_y + 0.12, z1 + o + 0.08, lace)
    op = K.off(("pelvis",) + LEGS, o)
    y_bot = 0.35 if floor else L.knee_y - 0.4
    if K.torn >= 2:
        y_bot += K.rng.uniform(0.3, 1.2)
    flare = {"wedding": 2.4, "evening": 0.5, "sundress": 1.3}.get(style, 1.0) * (1.0 if floor else 0.6)
    _aline(K, st, op, y_bot, flare, slit=1.0 if style == "evening" else 0.0)
    if p.get("train", False):
        pv = K.seg("pelvis")
        px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot)
        zb = pz1 + op + flare
        K.box("pelvis", px0 - op - 0.3, 0.02, zb - 0.6, px1 + op + 0.3, 0.3, zb + 4.2, st,
              rot=(-2, 0, 0), pivot=(0, 0.3, zb))
        K.box("pelvis", px0 - op, 0.3, zb - 0.5, px1 + op, L.knee_y, zb + 0.2, st, rot=(12, 0, 0),
              pivot=(0, L.knee_y, zb))
    if K.torn:
        pv = K.seg("pelvis")
        px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot)
        g = op + flare + 0.2
        K.rags("pelvis", px0 - g, px1 + g, pz0 - g, pz1 + g, y_bot, st, K.n_rags(1.5), length=(0.6, 2.0),
               width=(0.4, 0.9))
    return K.done()


def o_bomb_suit(rig, p, ctx):
    K = _K(rig, p, ctx, "bomb_suit")
    L = K.L
    st = K.cloth("bomb_suit", folds=1.3, wear=0.5)
    plate = K.st("bomb_plate", "kevlar", base=_mul(K.col, 0.85), pattern="plain")
    # 脚・腰
    for s in "rl":
        ol = K.off((f"thigh_{s}", f"shin_{s}"), 0.6)
        th, sh = K.seg(f"thigh_{s}"), K.seg(f"shin_{s}")
        K.wrap(K.armor(f"leg_{s}", "upper"), f"thigh_{s}", ol, st, y0=th["lo"][1] - 0.1, y1=th["hi"][1])
        bs = K.armor(f"leg_{s}", "shin")
        K.wrap(bs, f"shin_{s}", ol, st, y0=L.ankle_y + 0.1, y1=sh["hi"][1] + 0.05)
        sx0, sz0, sx1, sz1 = K.ring(f"shin_{s}", sh["lo"][1], sh["hi"][1])
        K.box(bs, sx0 - ol - 0.05, L.ankle_y + 1.0, sz0 - ol - 0.35, sx1 + ol + 0.05, sh["hi"][1] + 0.4, sz0 - ol + 0.1,
              plate)
    op = K.off(("pelvis",), 0.6)
    bp = K.armor("torso", "pelvis")
    K.wrap(bp, "pelvis", op, st, y0=K.seg("pelvis")["lo"][1] - 0.2, y1=L.abdomen_bot + 0.3)
    px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot)
    K.box(bp, -1.6, L.crotch - 1.6, pz0 - op - 0.4, 1.6, L.abdomen_bot + 0.1, pz0 - op, plate)   # 股の垂れ
    # 胴・腕
    o = K.off(TORSO, 0.7)
    bc, bb = K.armor("torso", "chest"), K.armor("torso", "belly")
    ch = K.seg("chest")
    K.wrap(bc, "chest", o, st, y0=L.chest_bot - 0.05, y1=ch["hi"][1] + 0.15)
    K.wrap(bb, "abdomen", o, st, y0=K.seg("abdomen")["lo"][1] - 0.1, y1=L.chest_bot + 0.15)
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    K.box(bc, x0 - o + 0.1, L.chest_bot - 0.6, z0 - o - 0.55, x1 + o - 0.1, ch["hi"][1] - 0.1, z0 - o, plate)
    bx0, bz0, bx1, bz1 = K.ring("abdomen", K.seg("abdomen")["lo"][1], L.chest_bot)
    K.box(bb, bx0 - o + 0.1, L.abdomen_bot - 0.2, bz0 - o - 0.5, bx1 + o - 0.1, L.chest_bot - 0.4, bz0 - o, plate)
    if p.get("collar", True):
        nk = K.seg("neck")
        nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
        K.box(bc, nx0 - 0.9, ch["hi"][1] - 0.2, nz0 - 0.9, nx1 + 0.9, ch["hi"][1] + 1.5, nz1 + 0.8, plate)
    for s in "rl":
        oa = K.off((f"upper_arm_{s}", f"forearm_{s}"), 0.55)
        ua, fa = K.seg(f"upper_arm_{s}"), K.seg(f"forearm_{s}")
        K.wrap(K.armor(f"arm_{s}", "upper"), f"upper_arm_{s}", oa, st, y0=ua["lo"][1] - 0.1, y1=ua["hi"][1] + 0.2)
        K.wrap(K.armor(f"arm_{s}", "fore"), f"forearm_{s}", oa, st, y0=L.wrist_y + 0.1, y1=fa["hi"][1])
    if p.get("helmet", True):
        H = _head(K)
        bh = K.armor("head", "head")
        oh = K.off(("head",), 0.65)
        x0h, x1h, z0h, z1h = H.x0 - oh, H.x1 + oh, H.z0 - oh, H.z1 + oh
        top = H.top + oh + 0.3
        fz = H.face_z - 0.7
        K.box(bh, x0h, H.brow + 0.35, fz, x1h, top, z1h, plate)
        K.box(bh, x0h, H.jaw_low - 1.2, H.cz - 0.2, x1h, H.brow + 0.4, z1h, plate)
        for sgn in (-1, 1):
            xa, xb = (x0h, x0h + 0.5) if sgn < 0 else (x1h - 0.5, x1h)
            K.box(bh, xa, H.jaw_low - 1.2, fz, xb, H.brow + 0.4, H.cz - 0.15, plate)
        K.box(bh, x0h, H.jaw_low - 1.2, fz, x1h, H.jaw_low - 0.3, H.cz - 0.15, plate)
        vm = p.get("visor", "intact")
        glass = K.st("bomb_visor", "glass", wear=False, base=(110, 130, 120), crack=0.9 if vm != "intact" else 0.0)
        _visor_frame(K, bh, x0h + 0.5, x1h - 0.5, H.jaw_low - 0.3, H.brow + 0.4, fz + 0.05, plate, glass,
                     cracked=(0, 2, 3)[("intact", "cracked", "shattered").index(vm) if vm in
                                       ("intact", "cracked", "shattered") else 0])
    return K.done()


def o_life_vest(rig, p, ctx):
    K = _K(rig, p, ctx, "life_vest")
    L = K.L
    defl = bool(p.get("deflated", False))
    st = K.cloth("life_vest", folds=2.0 if defl else 0.6, wear=0.3)
    strap = K.st("life_strap", "kevlar", base=(30, 30, 34), wear=True)
    o = K.off(TORSO, 0.45 if not defl else 0.3)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    bx0, bz0, bx1, bz1 = K.ring("abdomen", K.seg("abdomen")["lo"][1], L.chest_bot)
    puff = 0.75 if not defl else 0.3
    sag = 0.0 if not defl else 0.5
    for sgn in (-1, 1):   # 前の浮力室（左右 2 つ）
        xa, xb = sorted((sgn * 0.2, sgn * (x1 + o - 0.1)))
        K.box("chest", xa, L.chest_bot - 0.2 - sag, z0 - o - puff, xb, ch["hi"][1] - 0.4 - sag, z0 - o + 0.05, st)
        K.box("torso", xa, K.seg("abdomen")["lo"][1] + 0.3 - sag, bz0 - o - puff * 0.8, xb, L.chest_bot + 0.1,
              bz0 - o + 0.05, st)
    K.box("chest", x0 - o, L.chest_bot - 0.3, z1 + o - 0.1, x1 + o, ch["hi"][1] - 0.3, z1 + o + puff * 0.6, st)
    # 首の後ろの枕
    nk = K.seg("neck")
    nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
    K.box("chest", nx0 - 0.7, ch["hi"][1] - 0.3, nz0 + 0.4, nx1 + 0.7, ch["hi"][1] + 0.6 + puff * 0.6, nz1 + 0.7, st)
    for sgn in (-1, 1):
        xa, xb = sorted((sgn * (nx1 + 0.1), sgn * (nx1 + 0.75)))
        K.box("chest", xa, ch["hi"][1] - 0.4, z0 - o - 0.3, xb, ch["hi"][1] + 0.4, nz1 + 0.5, st)
    # 締め帯とバックル
    met = K.st("life_buckle", "plastic", base=(20, 20, 22), wear=True)
    for yy in (L.abdomen_bot + 1.0, L.chest_bot + 0.7):
        bone, seg_ = ("torso", "abdomen") if yy < L.chest_bot else ("chest", "chest")
        K.band(bone, seg_, o + puff * 0.85, yy - 0.18, yy + 0.18, strap)
        zz = (bz0 if bone == "torso" else z0) - o - puff * 0.85 - 0.1
        K.cbox(bone, (0, yy, zz), (0.7, 0.42, 0.2), met)
    if p.get("whistle", True):
        wh = K.st("whistle", "plastic", base=(236, 200, 40), wear=False)
        K.cbox("chest", (1.2, L.shoulder_y - 0.8, z0 - o - puff - 0.15), (0.25, 0.25, 0.55), wh)
    if K.torn:
        _hem_rags(K, "torso", "abdomen", o, K.seg("abdomen")["lo"][1], st, K.n_rags(0.6))
    return K.done()


def o_layered_rags(rig, p, ctx):
    K = _K(rig, p, ctx, "layered_rags")
    L = K.L
    kind = p.get("kind", "coat")
    layers = max(1, min(3, int(p.get("layers", 2))))
    c2 = K.col2 or _mix(K.col, (60, 70, 80), 0.5)
    st = K.cloth("rags", folds=1.8, wear=0.8)
    st2 = K.cloth("rags2", base=c2, pattern="hstripes", alt=_mul(c2, 0.75), period=1.6, folds=1.6, wear=0.8)
    rng = K.rng
    if kind == "loincloth":
        o = K.off(("pelvis",), 0.15)
        K.band("pelvis", "pelvis", o, L.abdomen_bot - 0.6, L.abdomen_bot + 0.2, st)
        px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot)
        K.box("pelvis", -1.2, L.crotch - 2.4, pz0 - o - 0.15, 1.2, L.abdomen_bot - 0.3, pz0 - o, st,
              rot=(-4, 0, 0), pivot=(0, L.abdomen_bot, pz0 - o))
        K.box("pelvis", -1.4, L.crotch - 1.8, pz1 + o, 1.4, L.abdomen_bot - 0.3, pz1 + o + 0.15, st,
              rot=(5, 0, 0), pivot=(0, L.abdomen_bot, pz1 + o))
        K.rags("pelvis", -1.2, 1.2, pz0 - o - 0.15, pz1 + o + 0.15, L.crotch - 1.8, st, 2 + layers, sides="ns")
        return K.done()
    if kind == "wraps":
        # 体に斜めに巻いた布の帯（layers × 数本）
        o = K.off(TORSO + ARMS + ("pelvis",) + LEGS, 0.2)
        spots = [("chest", "chest", L.chest_bot + 1.2), ("chest", "chest", L.shoulder_y - 0.9),
                 ("torso", "abdomen", L.abdomen_bot + 1.5), ("pelvis", "pelvis", L.abdomen_bot - 0.6),
                 ("arm_r", "upper_arm_r", L.elbow_y + 2.0), ("forearm_l", "forearm_l", L.wrist_y + 1.5),
                 ("leg_l", "thigh_l", L.knee_y + 2.5), ("shin_r", "shin_r", L.knee_y - 2.0),
                 ("arm_l", "upper_arm_l", L.elbow_y + 1.5), ("forearm_r", "forearm_r", L.wrist_y + 1.0)]
        n = 3 + 2 * layers
        for i, (bone, seg_, y) in enumerate(spots[:n]):
            stx = st if i % 2 == 0 else st2
            x0, z0, x1, z1 = K.ring_at(seg_, y)
            ang = rng.uniform(-22, 22)
            K.box(bone, x0 - o, y - 0.35, z0 - o, x1 + o, y + 0.35, z1 + o, stx, rot=(0, 0, ang),
                  pivot=((x0 + x1) / 2, y, (z0 + z1) / 2))
            if rng.random() < 0.5:
                K.rags(bone, x0 - o, x1 + o, z0 - o, z1 + o, y - 0.3, stx, 1, length=(0.6, 1.6))
        if layers >= 2:
            px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot)
            K.box("pelvis", -1.3, L.crotch - 1.5, pz0 - o - 0.15, 1.3, L.abdomen_bot, pz0 - o, st2)
        return K.done()
    # coat / robe: 長い外套（裾と袖がぼろぼろ）+ 肩掛け
    robe = kind == "robe"
    o = K.off(TORSO + ARMS + ("pelvis",), 0.4)
    _torso(K, o, st, gap_chest=0.0 if robe else 0.8, gap_belly=0.0 if robe else 1.0)
    hem = (L.ankle_y + 0.6) if robe else (L.knee_y - 0.8)
    _dress_skirt(K, st, o, hem, 2, 0.25 if robe else 0.15, gap_s=0.0 if robe else 1.2)
    K.rags("pelvis", -L.hip_w / 2 - o - 0.3, L.hip_w / 2 + o + 0.3, -L.pelvis_d / 2 - o - 0.4,
           L.pelvis_d / 2 + o + 0.4, hem, st, 3 + K.n_rags(), length=(0.5, 1.8), width=(0.4, 0.9))
    lens = _sleeve_len(K, "long")
    for s in "rl":
        _sleeve(K, s, o, st, lens[s])
        _sleeve_rags(K, s, o, st, lens[s], 1 + K.n_rags(0.4))
    if robe:
        _hood(K, st2 if layers >= 2 else st, "down")
        rope = K.st("rope", "cloth", base=(150, 130, 90), wear=True, folds=0.3)
        K.band("pelvis", "pelvis", o + 0.35, L.abdomen_bot - 0.05, L.abdomen_bot + 0.3, rope)
        px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot)
        K.beam("pelvis", (0.4, L.abdomen_bot, pz0 - o - 0.45), (0.6, L.crotch - 1.8, pz0 - o - 0.6), 0.22, 0.22, rope)
    if layers >= 2:
        # 肩に掛けた布（ケープ）
        oc = K.off(("chest",), o)
        ch = K.seg("chest")
        x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
        K.box("chest", x0 - oc - 0.5, L.shoulder_y - 2.2, z0 - oc, x1 + oc + 0.5, ch["hi"][1] + 0.3, z1 + oc, st2)
        K.rags("chest", x0 - oc - 0.5, x1 + oc + 0.5, z0 - oc, z1 + oc, L.shoulder_y - 2.2, st2, 2 + layers,
               length=(0.4, 1.4))
    if layers >= 3:
        sc = K.cloth("rags3", base=_mix(K.col, (120, 40, 30), 0.4), folds=1.5)
        nk = K.seg("neck")
        nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
        K.box("chest", nx0 - 0.5, K.seg("chest")["hi"][1] - 0.3, nz0 - 0.5, nx1 + 0.5,
              K.seg("chest")["hi"][1] + 0.9, nz1 + 0.5, sc)
        K.beam("chest", (0.5, K.seg("chest")["hi"][1], nz0 - 0.5), (0.8, L.chest_bot - 1.0, -L.chest_d / 2 - o - 0.6),
               0.7, 0.2, sc)
    return K.done()


# ===========================================================================
#  下半身
# ===========================================================================
def o_jeans(rig, p, ctx):
    K = _K(rig, p, ctx, "jeans")
    st = K.st("jeans", "denim", base=K.col, wear=True, seams=True)
    o = K.off(("pelvis",) + LEGS, 0.15)
    cut = p.get("cut", "full")
    rip = bool(p.get("ripped_knees", False))
    pk = [dict(name="pocket", box=(0.12, 0.25, 0.42, 0.62)), dict(name="pocket", box=(0.58, 0.25, 0.88, 0.62))]
    fly = dict(name="zipper", u=0.5)
    hem = None if cut == "shorts" else st
    length = "shorts" if cut == "shorts" else "full"
    out = _legs(K, o, st, length=length, pelvis_decals={"south": pk, "north": [fly]}, hem=hem,
                knee_gap=rip, waist_st=st)
    if rip:
        thread = K.st("thread", "cloth", base=(206, 210, 214), wear=False, folds=0.2)
        for s in "rl":
            x0, z0, x1, z1 = K.ring_at(f"shin_{s}", K.L.knee_y + 0.2)
            for k in range(2):
                y = K.L.knee_y + 0.05 + k * 0.5
                K.box(f"leg_{s}", x0 - o + 0.15, y, z0 - o - 0.05, x1 + o - 0.15, y + 0.1, z0 - o + 0.05,
                      thread, rot=(0, 0, K.rng.uniform(-8, 8)))
    if cut == "shorts":
        for s in "rl":
            b, sg, y = out[f"end_{s}"]
            K.band(b, sg, o + 0.06, y - 0.02, y + 0.38, st)     # 折り返し
            if K.torn:
                _hem_rags(K, b, sg, o, y, st, K.n_rags(0.6), length=(0.3, 0.9))
    elif K.torn >= 2:
        for s in "rl":
            b, sg, y = out[f"end_{s}"]
            _hem_rags(K, b, sg, o, y + 0.2, st, K.n_rags(0.5), length=(0.3, 0.8))
    return K.done()


def o_slacks(rig, p, ctx):
    K = _K(rig, p, ctx, "slacks")
    st = K.cloth("slacks", folds=0.7, wear=0.2)
    o = K.off(("pelvis",) + LEGS, 0.15)
    short = bool(p.get("short", False))
    crease = dict(name="stripe", orient="v", width=0.05, offset=0.5, colour=_mul(K.col, 0.62))
    out = _legs(K, o, st, length="short_full" if short else "full",
                pelvis_decals={"south": [dict(name="pocket", box=(0.15, 0.3, 0.42, 0.45)),
                                         dict(name="pocket", box=(0.58, 0.3, 0.85, 0.45))]},
                thigh_decals={"north": [crease]}, shin_decals={"north": [crease]}, hem=st)
    belt = K.st("belt", "leather", base=(30, 24, 22), wear=True)
    buckle = K.st("buckle", "chrome", wear=False, base=(180, 178, 170))
    _belt(K, o + 0.06, belt, buckle)
    if short:
        sock = K.cloth("sock", base=(40, 40, 46), folds=0.3)
        for s in "rl":
            K.band(f"shin_{s}", f"shin_{s}", 0.08, K.L.ankle_y - 0.1, K.L.ankle_y + 0.75, sock)
    if K.torn >= 2:
        for s in "rl":
            b, sg, y = out[f"end_{s}"]
            _hem_rags(K, b, sg, o, y + 0.2, st, K.n_rags(0.5), length=(0.3, 0.9))
    return K.done()


# ===========================================================================
#  靴
# ===========================================================================
def _foot(K: _K, s: str) -> SimpleNamespace:
    fs = K.seg(f"foot_{s}")
    x0, z0, x1, z1 = fs["lo"][0], fs["lo"][2], fs["hi"][0], fs["hi"][2]
    top = fs["hi"][1]
    return SimpleNamespace(x0=x0, x1=x1, z0=z0, z1=z1, top=top, toe_z=z0, heel_z=z1,
                           mid_z=z0 + 0.36 * (z1 - z0), cx=(x0 + x1) / 2, w=x1 - x0, l=z1 - z0)


def _shoe(K: _K, s: str, upper: str, sole: str, *, o: float = 0.14, sole_h: float = 0.32,
          toe_h: float = 0.95, top_extra: float = 0.12, lace: Optional[str] = None,
          lace_col=(220, 220, 214), heel_h: float = 0.0, toe_point: float = 0.0,
          cutaway: bool = False, sole_out: float = 0.12, decals_side=None) -> list:
    """低い靴の形: 靴底・後ろ半分の甲・つま先。lace = 紐の帯の色を塗る。"""
    F = _foot(K, s)
    b = f"foot_{s}"
    out = []
    so = o + sole_out
    out.append(K.box(b, F.x0 - so, -0.05, F.z0 - so - toe_point, F.x1 + so, sole_h, F.z1 + so, sole))
    top = F.top + top_extra
    if cutaway:
        top = F.top * 0.62
    side = decals_side or {}
    up_d = dict(side)
    if lace:
        up_d["up"] = [dict(name="stripe", orient="h", count=4, width=0.1, gap=0.08, colour=lace_col)]
    out.append(K.box(b, F.x0 - o, sole_h - 0.05, F.mid_z, F.x1 + o, top, F.z1 + o, upper,
                     decals=up_d or None))
    out.append(K.box(b, F.x0 - o + 0.04, sole_h - 0.05, F.z0 - o - toe_point, F.x1 + o - 0.04,
                     toe_h, F.mid_z + 0.05, upper))
    if heel_h > 0:
        out.append(K.box(b, F.cx - 0.45, -0.05, F.z1 - 0.2, F.cx + 0.45, sole_h + heel_h, F.z1 + so,
                         sole))
    return out


def o_sneakers(rig, p, ctx):
    K = _K(rig, p, ctx, "sneakers")
    kind = p.get("kind", "runner")
    c2 = K.col2 or (60, 60, 60)
    upper = K.st("sneaker", "cloth", base=K.col, folds=0.4, wear=True)
    sole = K.st("sole", "rubber", base=c2 if kind != "runner" else _mix(c2, (236, 234, 228), 0.6),
                wear=True)
    swoosh = dict(name="stripe", orient="d", width=0.16, offset=0.55, colour=c2)
    side = {"east": [swoosh], "west": [swoosh]}
    o = K.off(("foot_r", "foot_l"), 0.14)
    for s in "rl":
        _shoe(K, s, upper, sole, o=o, lace=upper, lace_col=_mix(K.col, (255, 255, 255), 0.6),
              decals_side=side)
        F = _foot(K, s)
        b = f"foot_{s}"
        K.box(b, F.cx - 0.35, F.top - 0.2, F.z1 + o - 0.05, F.cx + 0.35, F.top + 0.55, F.z1 + o + 0.12,
              sole)   # かかとのつまみ
        if kind == "high_top":
            K.band(f"shin_{s}", f"shin_{s}", o + 0.08, K.L.ankle_y - 0.05, K.L.ankle_y + 1.35, upper,
                   decals={"north": [dict(name="stripe", orient="h", count=3, width=0.12, gap=0.12,
                                          colour=_mix(K.col, (255, 255, 255), 0.6))]})
        if kind == "cleats":
            for zc in (F.z0 + 0.6, F.mid_z + 0.4, F.z1 - 0.5):
                for xc in (F.x0 + 0.35, F.x1 - 0.35):
                    K.cbox(b, (xc, -0.12, zc), (0.3, 0.16, 0.3), sole)
    return K.done()


def o_dress_shoes(rig, p, ctx):
    K = _K(rig, p, ctx, "dress_shoes")
    kind = p.get("kind", "oxford")
    miss = p.get("missing", "none")
    o = K.off(("foot_r", "foot_l"), 0.13)
    if kind == "clog":
        up = K.st("clog", "plastic", base=K.col, wear=True)
        sole = K.st("clog_sole", "rubber", base=_mul(K.col, 0.6), wear=True)
    else:
        up = K.st("shoe", "leather", base=K.col, wear=True)
        sole = K.st("shoe_sole", "leather", base=_mul(K.col, 0.55) if _lum(K.col) > 60 else (14, 12, 12),
                    wear=False)
    for s in "rl":
        if miss == s:
            continue
        F = _foot(K, s)
        b = f"foot_{s}"
        if kind == "oxford":
            _shoe(K, s, up, sole, o=o, sole_h=0.22, toe_h=0.85, lace=up, lace_col=(16, 14, 14),
                  heel_h=0.12)
        elif kind == "loafer":
            _shoe(K, s, up, sole, o=o, sole_h=0.22, toe_h=0.85, heel_h=0.1,
                  decals_side=None)
            K.box(b, F.x0 - o - 0.04, F.top * 0.62, F.mid_z - 0.25, F.x1 + o + 0.04, F.top * 0.62 + 0.28,
                  F.mid_z + 0.2, up)   # 甲のベルト
        elif kind == "heels":
            _shoe(K, s, up, sole, o=o, sole_h=0.14, toe_h=0.7, toe_point=0.35, cutaway=True)
            K.box(b, F.cx - 0.17, -0.05, F.z1 + o - 0.1, F.cx + 0.17, 1.45, F.z1 + o + 0.25, up)  # ピンヒール
        else:   # clog
            _shoe(K, s, up, sole, o=o + 0.08, sole_h=0.42, toe_h=1.1, top_extra=-0.2, sole_out=0.05)
    return K.done()


# ===========================================================================
#  頭（帽子・ヘルメット・マスク・眼鏡）
# ===========================================================================
def _eyes(K: _K) -> SimpleNamespace:
    """顔デカールの目の高さ・左右の間隔・顔板の前面（nr_rig の eye_v / eye_gap と同じ式）。"""
    L = K.L
    fp = None
    for c in K.rig.bones["head"].cubes:
        dv = c.decals.get("north") if c.decals else None
        if isinstance(dv, dict) and dv.get("name") == "face":
            fp = c
            break
    if fp is None:
        return SimpleNamespace(y=L.chin + 0.52 * L.H, dx=0.6, z=-L.head_d * 0.5, w=L.head_w * 0.8)
    d = fp.decals["north"]
    top = fp.origin[1] + fp.size[1]
    y = top - float(d.get("eye_v", 0.52)) * fp.size[1]
    dx = float(d.get("eye_gap", 0.25)) * fp.size[0]
    return SimpleNamespace(y=y, dx=dx, z=fp.origin[2], w=fp.size[0], plate_top=top,
                           plate_low=fp.origin[1])


def _dome(K: _K, bone: str, H, o: float, st: str, brow: float, back_low: Optional[float] = None,
          crown: float = 0.5, inset: float = 0.38, top_extra: float = 0.0, decals=None,
          crown_st: Optional[str] = None, uv=None) -> list:
    """丸みのある帽体: 額の高さ brow から上の箱 + 一回り小さい天辺 + 後ろの垂れ（back_low まで）。"""
    x0, x1, z0, z1 = H.x0 - o, H.x1 + o, H.z0 - o, H.z1 + o
    top = H.top + o + top_extra
    out = [K.box(bone, x0, brow, z0, x1, top - crown, z1, st, uv, decals)]
    out.append(K.box(bone, x0 + inset, top - crown - 0.02, z0 + inset, x1 - inset, top, z1 - inset,
                     crown_st or st, uv))
    if back_low is not None and back_low < brow - 0.05:
        out.append(K.box(bone, x0, back_low, H.cz - 0.1, x1, brow + 0.02, z1, st, uv))
    return out


def _visor_frame(K: _K, bone: str, x0, x1, y0, y1, z: float, frame: str, glass: str,
                 cracked: int = 0, th: float = 0.22) -> list:
    """透明の面体の代わり: 枠（上・下・左右）と映り込みの細い筋。中は開けて顔が見えるようにする。"""
    out = [K.box(bone, x0, y1 - 0.32, z - th, x1, y1, z, frame),
           K.box(bone, x0, y0, z - th, x1, y0 + 0.22, z, frame),
           K.box(bone, x0, y0, z - th, x0 + 0.22, y1, z, frame),
           K.box(bone, x1 - 0.22, y0, z - th, x1, y1, z, frame)]
    rng = K.rng
    n = 2 + cracked * 2
    for i in range(n):
        u = x0 + 0.4 + (x1 - x0 - 0.8) * (i + rng.uniform(0.2, 0.8)) / n
        ln = (y1 - y0) * rng.uniform(0.45, 0.85)
        ang = rng.uniform(-40, -25) if i < 2 else rng.uniform(-70, 70)
        out.append(K.box(bone, u - 0.05, y0 + 0.3, z - th * 0.6, u + 0.05, y0 + 0.3 + ln, z - th * 0.4,
                         glass, rot=(0, 0, ang), pivot=(u, y0 + 0.3, z - th * 0.5)))
    return out


def _label(K: _K, bone: str, centre, w: float, h: float, face: str, text: str, colour, st: str,
           th: float = 0.06, wear: float = 0.15, rot=None):
    """文字を読ませる薄い板（texel 密度を上げる）。face = 文字を描く面（north / south / east / west）。"""
    cx, cy, cz = centre
    d = {face: [dict(name="text", text=text, at=(0.5, 0.5), colour=colour, wear=wear)]}
    if face in ("north", "south"):
        sz = (w, h, th)
        cz = cz - th / 2 if face == "north" else cz + th / 2
    else:
        sz = (th, h, w)
        cx = cx - th / 2 if face == "east" else cx + th / 2
    return K.cbox(bone, (cx, cy, cz), sz, st, uv=K.U["face"], decals=d, rot=rot)


def _chinstrap(K: _K, bone: str, H, o: float, st: str, mode: str, y_top: float) -> list:
    """あごひも: on = 顎の下を回る、dangling = 両側から垂れる。"""
    out = []
    jaw_y = H.jaw_low - 0.15
    for sgn in (-1, 1):
        x = (H.x0 - o - 0.04) if sgn < 0 else (H.x1 + o + 0.04)
        if mode == "on":
            out.append(K.beam(bone, (x, y_top, H.z0 + 1.3), (sgn * 0.6, jaw_y, H.z0 + 0.2), 0.14, 0.1, st))
        else:
            out.append(K.beam(bone, (x, y_top, H.z0 + 1.2),
                              (x + sgn * 0.2, y_top - 2.3 - K.rng.uniform(0, 0.5), H.z0 + 0.9 + K.rng.uniform(0, 0.4)),
                              0.14, 0.1, st))
    return out


def o_hard_hat(rig, p, ctx):
    K = _K(rig, p, ctx, "hard_hat")
    H = _head(K)
    bone = K.armor("head", "head")
    dent = _lv(p.get("dented", 0))
    st = K.st("hardhat", "plastic", base=K.col, wear=0.4 + 0.15 * dent)
    o = K.off(("head",), 0.32)
    brow = H.brow
    dec = {"north": [dict(name="cracks", amount=0.25 * dent)] if dent else []}
    if p.get("sticker", True):
        dec["west"] = [dict(name="badge", kind="circle", at=(0.5, 0.45), size=0.5, colour=(220, 40, 40))]
        dec["east"] = [dict(name="stripe", orient="h", width=0.18, offset=0.45, colour=(30, 90, 190))]
    _dome(K, bone, H, o, st, brow, crown=0.55, inset=0.42, top_extra=0.12, decals=dec)
    # 天辺の峰とつば（前が長い）
    top = H.top + o + 0.12
    K.box(bone, -0.32, top - 0.1, H.z0 - o + 0.1, 0.32, top + 0.22, H.z1 + o - 0.2, st)
    K.box(bone, H.x0 - o - 0.32, brow - 0.08, H.z0 - o - 1.05, H.x1 + o + 0.32, brow + 0.16,
          H.z1 + o + 0.4, st, rot=(-4 if dent < 2 else -9, 0, 0), pivot=(0, brow, H.cz))
    # 内側の吊りバンド（耳の上に見える帯）
    band = K.st("hardhat_band", "plastic", base=(40, 38, 36), wear=True)
    K.box(bone, H.x0 - 0.12, brow - 0.32, H.z0 + 0.3, H.x1 + 0.12, brow + 0.02, H.z1 - 0.1, band)
    return K.done()


def o_police_cap(rig, p, ctx):
    K = _K(rig, p, ctx, "police_cap")
    H = _head(K)
    bone = K.child("hat")
    guard = p.get("style", "police") == "guard"
    st = K.cloth("cap", folds=0.4, wear=0.2)
    blk = K.st("cap_visor", "leather", base=(14, 14, 16), wear=False, blood=_BLOOD[K.bloody])
    o = K.off(("head",), 0.16)
    brow = H.brow + 0.05
    band_d = None
    if p.get("badge", True):
        band_d = {"north": [dict(name="badge", kind="patch" if guard else "shield", at=(0.5, 0.5), size=0.7,
                                 colour=(200, 200, 60) if guard else (212, 176, 72),
                                 text="SEC" if guard else "")]}
    K.box(bone, H.x0 - o, brow, H.z0 - o, H.x1 + o, brow + 0.75, H.z1 + o, blk)          # 帽子の帯
    K.box(bone, H.x0 - o - 0.32, brow + 0.72, H.z0 - o - 0.42, H.x1 + o + 0.32, brow + 1.45,
          H.z1 + o + 0.3, st, uv=K.U["fine"], decals=band_d)                             # 平たい天井
    K.box(bone, H.x0 - o + 0.05, brow - 0.06, H.z0 - o - 1.0, H.x1 + o - 0.05, brow + 0.1, H.z0 - o + 0.1,
          blk, rot=(-14, 0, 0), pivot=(0, brow, H.z0 - o))                              # つば
    if not guard:
        gold = K.st("cap_cord", "chrome", wear=False, base=(214, 180, 90))
        K.box(bone, H.x0 - o - 0.02, brow + 0.08, H.z0 - o - 0.08, H.x1 + o + 0.02, brow + 0.22,
              H.z0 - o + 0.3, gold)                                                     # あご紐の金の飾り
    return K.done()


def o_riot_helmet(rig, p, ctx):
    K = _K(rig, p, ctx, "riot_helmet")
    H = _head(K)
    bone = K.armor("head", "head")
    st = K.st("riot_helmet", "plastic", base=K.col, wear=0.5)
    frame = K.st("riot_visor_frame", "rubber", base=(24, 24, 26), wear=True)
    vmode = p.get("visor", "down")
    glass = K.st("riot_visor", "glass", wear=False, base=(170, 196, 210),
                 crack=0.8 if vmode == "cracked" else 0.0)
    o = K.off(("head",), 0.32)
    brow = H.brow + 0.05
    _dome(K, bone, H, o, st, brow, back_low=H.jaw_low + 0.3, crown=0.6, inset=0.45, top_extra=0.15)
    _label(K, bone, (0, brow + 0.55, H.z1 + o), 2.6, 0.62, "south", "POLICE", (232, 232, 224), st)
    zf = H.face_z - 0.45
    if vmode in ("down", "cracked"):
        _visor_frame(K, bone, H.x0 - o + 0.05, H.x1 + o - 0.05, H.jaw_low - 0.3, brow + 0.3, zf, frame,
                     glass, cracked=2 if vmode == "cracked" else 0)
    else:   # 上げたバイザー（額の上に斜めに乗る）
        K.box(bone, H.x0 - o + 0.05, brow + 0.2, H.z0 - o - 0.45, H.x1 + o - 0.05, brow + 0.42,
              H.z0 - o + 1.6, glass, rot=(-28, 0, 0), pivot=(0, brow + 0.3, H.z0 - o))
    if p.get("neck_guard", True):
        K.box(bone, H.x0 - o + 0.2, H.jaw_low - 1.6, H.z1 + o - 0.05, H.x1 + o - 0.2, H.jaw_low + 0.5,
              H.z1 + o + 0.22, frame, rot=(14, 0, 0), pivot=(0, H.jaw_low + 0.5, H.z1 + o))
    return K.done()


def o_helmet_military(rig, p, ctx):
    K = _K(rig, p, ctx, "helmet_military")
    H = _head(K)
    bone = K.armor("head", "head")
    cover = p.get("cover", "camo")
    if cover == "camo":
        st = K.cloth("mil_helmet", pattern="camo", alt=_mul(K.col, 0.62), alt2=(52, 48, 36),
                     alt3=_mix(K.col, (150, 140, 100), 0.5), folds=0.6)
    else:
        st = K.st("mil_helmet", "painted_metal", base=K.col, rust=0.2, wear=0.4)
    o = K.off(("head",), 0.36)
    brow = H.brow
    _dome(K, bone, H, o, st, brow, back_low=H.eye - 0.4, crown=0.6, inset=0.42, top_extra=0.18)
    # 縁の張り出し
    K.box(bone, H.x0 - o - 0.12, brow - 0.08, H.z0 - o - 0.2, H.x1 + o + 0.12, brow + 0.2, H.z1 + o + 0.12, st)
    strap = K.st("mil_strap", "kevlar", base=(54, 52, 40), wear=True)
    if p.get("goggles", True):
        lens = K.st("goggle_lens", "glass", wear=False, base=(70, 86, 70))
        gy = brow + 0.55
        K.box(bone, H.x0 - o - 0.16, gy - 0.18, H.z0 - o - 0.16, H.x1 + o + 0.16, gy + 0.18, H.z1 + o + 0.16,
              strap)
        for sgn in (-1, 1):
            K.cbox(bone, (sgn * 0.62, gy, H.z0 - o - 0.3), (1.0, 0.72, 0.4), lens)
    _chinstrap(K, bone, H, o, strap, p.get("chinstrap", "dangling"), brow)
    return K.done()


def o_firefighter_helmet(rig, p, ctx):
    K = _K(rig, p, ctx, "firefighter_helmet")
    H = _head(K)
    bone = K.child("hat")
    st = K.st("fire_helmet", "painted_metal", base=K.col, rust=0.05, wear=0.45)
    o = K.off(("head",), 0.34)
    brow = H.brow
    _dome(K, bone, H, o, st, brow, crown=0.6, inset=0.4, top_extra=0.2)
    top = H.top + o + 0.2
    K.box(bone, -0.25, top - 0.15, H.z0 - o + 0.2, 0.25, top + 0.2, H.z1 + o - 0.2, st)   # 峰
    # つば: 前は短く、後ろは長く下がる
    K.box(bone, H.x0 - o - 0.35, brow - 0.1, H.z0 - o - 0.55, H.x1 + o + 0.35, brow + 0.14, H.cz, st)
    K.box(bone, H.x0 - o - 0.5, brow - 0.1, H.cz - 0.05, H.x1 + o + 0.5, brow + 0.14, H.z1 + o + 1.0, st,
          rot=(14, 0, 0), pivot=(0, brow, H.cz))
    # 前章（番号）
    leather = K.st("fire_shield", "leather", base=(30, 26, 24), wear=True)
    K.box(bone, -0.75, brow + 0.15, H.z0 - o - 0.22, 0.75, brow + 1.55, H.z0 - o + 0.02, leather,
          uv=K.U["face"] * 0.7,
          decals={"north": [dict(name="badge", kind="shield", at=(0.5, 0.5), size=0.95, colour=(200, 40, 30)),
                            dict(name="text", text=str(p.get("shield_text", "7"))[:3], at=(0.5, 0.5),
                                 colour=(240, 236, 220), wear=0.1)]})
    vis = K.st("fire_visor", "glass", wear=False, base=(150, 130, 70))
    if p.get("visor", "up") == "up":
        K.box(bone, H.x0 - o + 0.1, brow + 0.6, H.z0 - o - 0.3, H.x1 + o - 0.1, brow + 0.82, H.z0 - o + 1.3,
              vis, rot=(-30, 0, 0), pivot=(0, brow + 0.7, H.z0 - o))
    else:
        _visor_frame(K, bone, H.x0 - o + 0.1, H.x1 + o - 0.1, H.jaw_low + 0.6, brow, H.face_z - 0.45,
                     leather, vis)
    if p.get("neck_flap", True):
        flap = K.st("fire_flap", "cloth", base=(150, 120, 70), folds=1.2)
        K.box(bone, H.x0 - 0.2, H.jaw_low - 0.2, H.z1 + 0.1, H.x1 + 0.2, brow + 0.1, H.z1 + 0.32, flap,
              rot=(10, 0, 0), pivot=(0, brow, H.z1))
    return K.done()


def o_scooter_helmet(rig, p, ctx):
    K = _K(rig, p, ctx, "scooter_helmet")
    H = _head(K)
    bone = K.armor("head", "head")
    cr = _lv(p.get("cracked", 0))
    st = K.st("scooter_helmet", "plastic", base=K.col, wear=0.5)
    dec = {"west": [dict(name="stripe", orient="h", width=0.12, offset=0.55, colour=(200, 40, 40))],
           "east": [dict(name="stripe", orient="h", width=0.12, offset=0.55, colour=(200, 40, 40))]}
    if cr:
        dec["north"] = [dict(name="cracks", amount=0.35 * cr)]
        dec["west"].append(dict(name="cracks", amount=0.35 * cr))
    o = K.off(("head",), 0.36)
    brow = H.brow + 0.05
    _dome(K, bone, H, o, st, brow, back_low=H.jaw_low + 0.1, crown=0.62, inset=0.45, top_extra=0.15,
          decals=dec)
    for sgn in (-1, 1):   # 耳を覆う横
        xa = H.x0 - o if sgn < 0 else H.x1 + o - 0.32
        K.box(bone, xa, H.jaw_low + 0.15, H.z0 - o + 0.55, xa + 0.32, brow + 0.05, H.cz + 0.4, st)
    vm = p.get("visor", "up")
    vis = K.st("scooter_visor", "glass", wear=False, base=(120, 130, 140), crack=0.25 * cr)
    if vm == "up":
        K.box(bone, H.x0 - o, brow + 0.25, H.z0 - o - 0.32, H.x1 + o, brow + 0.47, H.z0 - o + 1.7, vis,
              rot=(-22, 0, 0), pivot=(0, brow + 0.35, H.z0 - o))
    elif vm == "down":
        frame = K.st("scooter_rim", "rubber", base=(28, 28, 30), wear=False)
        _visor_frame(K, bone, H.x0 - o + 0.05, H.x1 + o - 0.05, H.jaw_low + 0.2, brow + 0.25,
                     H.face_z - 0.4, frame, vis, cracked=cr)
    strap = K.st("scooter_strap", "kevlar", base=(30, 30, 32), wear=True)
    _chinstrap(K, bone, H, o, strap, p.get("strap", "dangling"), H.jaw_low + 0.5)
    return K.done()


def o_baseball_cap(rig, p, ctx):
    K = _K(rig, p, ctx, "baseball_cap")
    H = _head(K)
    bone = K.child("hat")
    st = K.cloth("ball_cap", folds=0.5)
    back = bool(p.get("backwards", False))
    o = K.off(("head",), 0.16)
    brow = H.brow + 0.1
    ink = K.col2 or _contrast(K.col)
    logo = {"north" if not back else "south": [dict(name="logo", at=(0.5, 0.55), size=0.8, colour=ink,
                                                   text="NR")]} if p.get("logo", True) else None
    _dome(K, bone, H, o, st, brow, crown=0.45, inset=0.35, top_extra=0.15, decals=logo, uv=K.U["fine"])
    K.cbox(bone, (0, H.top + o + 0.2, H.cz), (0.36, 0.14, 0.36), st)          # 天辺のボタン
    if not back:
        K.box(bone, H.x0 - o + 0.1, brow - 0.04, H.z0 - o - 1.45, H.x1 + o - 0.1, brow + 0.12,
              H.z0 - o + 0.2, st, rot=(-10, 0, 0), pivot=(0, brow, H.z0 - o))
    else:
        K.box(bone, H.x0 - o + 0.1, brow - 0.04, H.z1 + o - 0.2, H.x1 + o - 0.1, brow + 0.12,
              H.z1 + o + 1.45, st, rot=(10, 0, 0), pivot=(0, brow, H.z1 + o))
        strap = K.st("cap_strap", "plastic", base=(30, 30, 30), wear=False)
        K.box(bone, -0.6, brow + 0.1, H.z0 - o - 0.04, 0.6, brow + 0.55, H.z0 - o + 0.05, strap)
    return K.done()


def o_skull_cap(rig, p, ctx):
    K = _K(rig, p, ctx, "skull_cap")
    H = _head(K)
    kind = p.get("kind", "surgical")
    o = K.off(("head",), 0.14)
    brow = H.brow + 0.2
    if kind == "hairnet":
        st = K.cloth("hairnet", pattern="check", alt=(30, 30, 32), period=0.5, folds=0.3)
        _dome(K, "head", H, o, st, brow + 0.2, back_low=H.low + 0.3, crown=0.3, inset=0.25)
        return K.done()
    pat = "print" if kind == "surgical" else "plain"
    st = K.cloth("skull_cap", pattern=pat, alt=_mul(K.col, 0.75), folds=0.8)
    if kind == "kitchen":
        _dome(K, "head", H, o, st, brow, crown=0.3, inset=0.2, top_extra=0.1)
        K.box("head", H.x0 - o - 0.08, brow - 0.05, H.z0 - o - 0.08, H.x1 + o + 0.08, brow + 0.5,
              H.z1 + o + 0.08, st)                                              # 折り返しの縁
        return K.done()
    _dome(K, "head", H, o, st, brow, back_low=H.low + 0.3, crown=0.35, inset=0.28, top_extra=0.12)
    for sgn in (-1, 1):   # 後ろで結んだひも
        K.beam("head", (sgn * 0.3, H.low + 0.6, H.z1 + o), (sgn * 0.7, H.low - 0.9, H.z1 + o + 0.3),
               0.18, 0.08, st)
    return K.done()


def o_bridal_veil(rig, p, ctx):
    K = _K(rig, p, ctx, "bridal_veil")
    H = _head(K)
    L = K.L
    st = K.cloth("veil", folds=1.6, wear=0.1, pattern="print", alt=_mul(K.col, 0.93))
    o = K.off(("head",), 0.22)
    long_ = p.get("length", "long") == "long"
    H.face_top = H.hair
    bot = (L.crotch - 1.0) if long_ else (L.shoulder_y - 2.5)
    top = H.top + o
    # 頭頂から背中へ垂れる布（広がりながら）
    K.box("head", H.x0 - o, H.face_top - 0.3, H.cz - 0.1, H.x1 + o, top, H.z1 + o, st)
    K.box("head", H.x0 - o - 0.25, bot, H.z1 + o - 0.1, H.x1 + o + 0.25, H.face_top + 0.2, H.z1 + o + 0.15,
          st, rot=(6, 0, 0), pivot=(0, H.face_top, H.z1 + o))
    for sgn in (-1, 1):
        xa = (H.x0 - o - 0.3) if sgn < 0 else (H.x1 + o + 0.15)
        K.box("head", xa, bot + 2.5, H.cz - 0.2, xa + 0.15, H.face_top, H.z1 + o + 0.1, st,
              rot=(4, 0, sgn * -5), pivot=(xa, H.face_top, H.cz))
    if K.torn:
        K.rags("head", H.x0 - o - 0.25, H.x1 + o + 0.25, H.z1 + o - 0.1, H.z1 + o + 0.15, bot, st,
               K.n_rags(), length=(0.6, 2.0), sides="s")
    if p.get("tiara", True):
        met = K.st("tiara", "chrome", wear=False, base=(230, 226, 214))
        K.box("head", H.x0 - o + 0.3, top - 0.1, H.z0 + 0.1, H.x1 - 0.3 + o, top + 0.28, H.z0 + 0.45, met,
              uv=K.U["fine"])
        K.cbox("head", (0, top + 0.35, H.z0 + 0.25), (0.4, 0.4, 0.3), met, rot=(0, 0, 45))
    return K.done()


def o_gas_mask(rig, p, ctx):
    K = _K(rig, p, ctx, "gas_mask")
    H = _head(K)
    E = _eyes(K)
    rub = K.st("gasmask", "rubber", base=K.col, wear=True)
    lens_k = p.get("lens", "intact")
    o = K.off(("head",), 0.3)
    zf = H.face_z - 0.25          # 面体の前面（鼻より前）
    zb = H.z0 + 1.0
    xw = E.w / 2 + 0.45
    y_top = E.y + 0.85
    y_bot = H.jaw_low - 0.35
    ew = 0.62                      # 目の窓の半幅
    eh = 0.5
    # 窓を空けた面体: 額・頬から下・鼻筋・両側
    K.box("head", -xw, E.y + eh, zf, xw, y_top, zb, rub)
    K.box("head", -xw, y_bot, zf - 0.15, xw, E.y - eh, zb, rub)
    K.box("head", -E.dx + ew, E.y - eh - 0.02, zf, E.dx - ew, E.y + eh + 0.02, zb, rub)
    for sgn in (-1, 1):
        xo = sgn * (E.dx + ew)
        xa, xb = sorted((xo, sgn * xw))
        K.box("head", xa, E.y - eh - 0.02, zf, xb, E.y + eh + 0.02, zb, rub)
    # レンズ（無傷 / ひび / 割れて穴）
    if lens_k != "shattered":
        lens = K.st("gasmask_lens", "glass", wear=False, base=(90, 110, 104),
                    crack=0.85 if lens_k == "cracked" else 0.0)
        for sgn in (-1, 1):
            K.cbox("head", (sgn * E.dx, E.y, zf + 0.12), (ew * 2 - 0.08, eh * 2 - 0.08, 0.22), lens)
    else:
        shard = K.st("gasmask_shard", "glass", wear=False, base=(150, 170, 164))
        for sgn in (-1, 1):
            for k in range(3):
                a = K.rng.uniform(0, 360)
                K.cbox("head", (sgn * E.dx + math.cos(math.radians(a)) * ew * 0.75,
                                E.y + math.sin(math.radians(a)) * eh * 0.75, zf + 0.05),
                       (0.32, 0.16, 0.1), shard, rot=(0, 0, a))
    # 吸収缶
    can = K.st("gasmask_filter", "painted_metal", base=_mix(K.col, (90, 96, 80), 0.6), rust=0.3, wear=0.5)
    nf = max(1, min(2, int(p.get("filters", 2))))
    my = (y_bot + E.y - eh) / 2 - 0.15
    if nf == 1:
        K.cbox("head", (0, my, zf - 0.55), (1.2, 1.2, 0.9), can)
        K.cbox("head", (0, my, zf - 0.55), (0.85, 0.85, 1.05), can)
    else:
        for sgn in (-1, 1):
            K.cbox("head", (sgn * 1.0, my - 0.1, zf - 0.35), (0.95, 0.95, 0.85), can,
                   rot=(0, sgn * 30, 0))
        K.cbox("head", (0, my - 0.2, zf - 0.3), (0.7, 0.6, 0.5), rub)            # 排気弁
    # 頭を回るベルト
    for yy in (E.y + 0.2, y_top - 0.1):
        K.box("head", -H.w / 2 - o, yy - 0.12, zb - 0.05, H.w / 2 + o, yy + 0.12, H.z1 + o, rub)
    return K.done()


def o_surgical_mask(rig, p, ctx):
    K = _K(rig, p, ctx, "surgical_mask")
    H = _head(K)
    E = _eyes(K)
    st = K.cloth("mask", folds=1.4, wear=0.1, pattern="hstripes", alt=_mul(K.col, 0.88), period=0.5)
    pos = p.get("position", "mouth")
    o = K.off(("head",), 0.12)
    jw = K.seg("jaw")
    jx0, jz0, jx1, jz1 = K.ring("jaw", jw["lo"][1], jw["hi"][1])
    zf = H.face_z - 0.12
    loop = K.st("mask_loop", "cloth", base=(236, 236, 236), wear=False, folds=0.0)
    if pos == "mouth":
        K.box("head", -1.15, H.face_low - 0.05, zf - 0.08, 1.15, E.y - 0.35, zf + 0.75, st)
        K.box("jaw", jx0 - 0.1, jw["lo"][1] - 0.12, jz0 - 0.15, jx1 + 0.1, H.face_low + 0.05, jz0 + 0.7, st)
        for sgn in (-1, 1):
            K.beam("head", (sgn * 1.12, E.y - 0.45, zf + 0.5), (sgn * (H.w / 2 + 0.12), E.y - 0.1, H.cz),
                   0.1, 0.08, loop)
            K.beam("head", (sgn * 1.12, H.face_low + 0.1, zf + 0.5), (sgn * (H.w / 2 + 0.12), E.y - 0.6, H.cz),
                   0.1, 0.08, loop)
    elif pos == "chin":
        K.box("jaw", jx0 - 0.12, jw["lo"][1] - 0.3, jz0 - 0.15, jx1 + 0.12, jw["lo"][1] + 0.55, jz0 + 1.2, st)
        for sgn in (-1, 1):
            K.beam("head", (sgn * 1.2, H.jaw_low + 0.2, H.z0 + 1.0), (sgn * (H.w / 2 + 0.12), E.y - 0.1, H.cz),
                   0.1, 0.08, loop)
    else:   # ear: 右耳からぶら下がる
        ex = H.ex0 - 0.08
        K.beam("head", (ex, E.y - 0.1, H.cz), (ex - 0.1, E.y - 1.2, H.cz - 0.4), 0.1, 0.08, loop)
        K.box("head", ex - 0.3, E.y - 2.6, H.cz - 1.2, ex - 0.12, E.y - 1.1, H.cz + 0.2, st,
              rot=(8, 0, -6), pivot=(ex - 0.2, E.y - 1.1, H.cz - 0.5))
    return K.done()


def o_glasses(rig, p, ctx):
    K = _K(rig, p, ctx, "glasses")
    H = _head(K)
    E = _eyes(K)
    kind = p.get("kind", "clear")
    cracked = bool(p.get("cracked", False))
    frame = K.st("glasses", "plastic" if kind != "clear" else "chrome", wear=False,
                 base=K.col if kind != "clear" else (120, 120, 126))
    tint = {"clear": (170, 190, 196), "sun": (24, 26, 30), "thick": (196, 206, 210),
            "loupe": (150, 170, 176)}[kind]
    lens = K.st("glasses_lens", "glass", wear=False, base=tint, crack=0.7 if cracked else 0.0)
    zf = E.z - 0.32
    th = 0.12 if kind != "thick" else 0.22
    lw, lh = (0.95, 0.62) if kind != "thick" else (1.05, 0.78)
    for sgn in (-1, 1):
        K.cbox("head", (sgn * E.dx, E.y, zf), (lw, lh, th), lens, uv=K.U["fine"])
        K.cbox("head", (sgn * E.dx, E.y + lh / 2, zf - 0.02), (lw + 0.1, 0.12, th + 0.06), frame)   # 上の縁
        # つる（耳まで）
        xs = sgn * (E.dx + lw / 2)
        xa, xb = sorted((xs, sgn * (H.w / 2 + 0.1)))
        K.box("head", xa, E.y + 0.12, zf, xb, E.y + 0.26, zf + 0.25, frame)
        K.box("head", sgn * (H.w / 2 + 0.02) - 0.06, E.y + 0.12, zf, sgn * (H.w / 2 + 0.02) + 0.06, E.y + 0.26,
              H.cz + 0.5, frame)
        if kind == "loupe":
            K.cbox("head", (sgn * E.dx, E.y - 0.05, zf - 0.45), (0.45, 0.45, 0.7), frame)
    K.cbox("head", (0, E.y + 0.1, zf - 0.02), (2 * E.dx - lw + 0.1, 0.12, 0.12), frame)    # ブリッジ
    return K.done()


def o_headphones(rig, p, ctx):
    K = _K(rig, p, ctx, "headphones")
    H = _head(K)
    L = K.L
    kind = p.get("kind", "over_ear")
    worn = p.get("worn", "head")
    st = K.st("headphones", "plastic", base=K.col, wear=True)
    pad = K.st("headphone_pad", "leather", base=(30, 30, 32), wear=False)
    ex, ey, ez = H.ex1, H.face_top - 1.55, H.cz - 0.05
    cord = K.st("earbud_cord", "rubber", base=K.col, wear=False)
    if kind == "over_ear" and worn == "head":
        o = K.off(("head",), 0.2)
        for sgn in (-1, 1):
            xa = sgn * (ex + 0.05)
            K.cbox("head", (xa + sgn * 0.12, ey, ez), (0.3, 1.25, 1.25), pad)
            K.cbox("head", (xa + sgn * 0.42, ey, ez), (0.35, 1.05, 1.05), st)
            K.box("head", min(xa, xa + sgn * 0.25), ey + 0.5, ez - 0.2, max(xa, xa + sgn * 0.25),
                  H.top + o, ez + 0.2, st)
        K.box("head", -ex - 0.25, H.top + o - 0.05, ez - 0.2, ex + 0.25, H.top + o + 0.25, ez + 0.2, st)
    elif kind == "over_ear":
        # 首に掛けたヘッドホン（胸のボーン、鎖骨の上）
        nk = K.seg("neck")
        nx0, nz0, nx1, nz1 = K.ring("neck", nk["lo"][1], nk["lo"][1] + 1.0)
        y = K.seg("chest")["hi"][1] + 0.1
        for sgn in (-1, 1):
            xc = sgn * (nx1 + 0.45)
            K.cbox("chest", (xc, y, nz0 + 0.1), (0.45, 1.1, 1.1), st, rot=(0, 0, sgn * -25))
        K.box("chest", nx0 - 0.25, y - 0.2, nz1 + 0.05, nx1 + 0.25, y + 0.15, nz1 + 0.35, st)
    else:   # earbuds
        y_ch = L.chest_bot + 1.6
        for sgn in (-1, 1):
            if worn == "head":
                bud = (sgn * (ex + 0.08), ey, ez - 0.1)
                K.cbox("head", bud, (0.28, 0.32, 0.32), st)
                K.beam("chest", (sgn * 0.9, L.shoulder_y + 0.6, -0.6), (sgn * 0.25, y_ch, K.seg("chest")["lo"][2] - 0.25),
                       0.08, 0.08, cord)
            else:
                end = (sgn * 0.45, y_ch - 0.3, K.seg("chest")["lo"][2] - 0.3)
                K.beam("chest", (sgn * 0.95, L.shoulder_y + 0.5, 0.2), end, 0.08, 0.08, cord)
                K.cbox("chest", (end[0], end[1] - 0.15, end[2]), (0.26, 0.32, 0.26), st)
        K.beam("chest", (-0.9, L.shoulder_y + 0.55, 0.3), (0.9, L.shoulder_y + 0.55, 0.3), 0.08, 0.08, cord)
    if p.get("cord_dangling", False):
        z_ = K.seg("chest")["lo"][2] - 0.4
        K.beam("chest", (0.3, L.chest_bot + 1.0, z_), (0.6, L.chest_bot - 2.0, z_ - 0.1), 0.08, 0.08, cord)
        K.beam("torso", (0.6, L.chest_bot - 1.95, z_ - 0.1), (0.4, L.abdomen_bot - 0.6, z_ - 0.05), 0.08, 0.08,
               cord)
    return K.done()


# ===========================================================================
#  下半身（続き）
# ===========================================================================
def o_work_pants(rig, p, ctx):
    K = _K(rig, p, ctx, "work_pants")
    L = K.L
    if K.col2 is not None:   # 2 色目があれば細かい千鳥（コックのズボン）
        st = K.cloth("work_pants", pattern="check", alt=K.col2, period=0.45, folds=0.9)
    else:
        st = K.cloth("work_pants", folds=1.0, wear=0.5)
    o = K.off(("pelvis",) + LEGS, 0.17)
    out = _legs(K, o, st, hem=st, pelvis_decals={"south": [dict(name="pocket", box=(0.12, 0.25, 0.42, 0.55)),
                                                           dict(name="pocket", box=(0.58, 0.25, 0.88, 0.55))]})
    belt = K.st("belt", "leather", base=(46, 34, 26), wear=True)
    _belt(K, o + 0.06, belt, K.st("buckle", "chrome", wear=False, base=(170, 168, 160)))
    if p.get("cargo", True):
        for s in "rl":
            th = K.seg(f"thigh_{s}")
            x0, z0, x1, z1 = K.ring_at(f"thigh_{s}", th["lo"][1] + 2.0)
            sgn = -1 if s == "r" else 1
            xa = (x0 - o - 0.3) if sgn < 0 else (x1 + o)
            K.box(f"leg_{s}", xa, th["lo"][1] + 0.9, -0.8, xa + 0.3, th["lo"][1] + 2.7, 0.8, st,
                  decals={"east" if sgn < 0 else "west": [dict(name="pocket", box=(0.1, 0.05, 0.9, 0.3))]})
    if p.get("knee_pads", False):
        pad = K.st("knee_pad", "rubber", base=(30, 30, 32), wear=True)
        for s in "rl":
            sh = K.seg(f"shin_{s}")
            x0, z0, x1, z1 = K.ring_at(f"shin_{s}", sh["hi"][1] - 0.5)
            K.box(f"shin_{s}", x0 - o - 0.08, sh["hi"][1] - 1.5, z0 - o - 0.4, x1 + o + 0.08, sh["hi"][1] + 0.5,
                  z0 - o + 0.3, pad)
            K.band(f"shin_{s}", f"shin_{s}", o + 0.12, sh["hi"][1] - 1.2, sh["hi"][1] - 0.95, pad)
    if K.torn >= 2:
        for s in "rl":
            b, sg, y = out[f"end_{s}"]
            _hem_rags(K, b, sg, o, y + 0.2, st, K.n_rags(0.5), length=(0.3, 0.9))
    return K.done()


def o_pencil_skirt(rig, p, ctx):
    K = _K(rig, p, ctx, "pencil_skirt")
    L = K.L
    st = K.cloth("pencil_skirt", folds=0.6, wear=0.25)
    o = K.off(("pelvis",) + LEGS, 0.16)
    pv = K.seg("pelvis")
    K.wrap("pelvis", "pelvis", o, st, y0=pv["lo"][1] - 0.1, y1=L.abdomen_bot + 0.35)
    K.band("pelvis", "pelvis", o + 0.06, L.abdomen_bot - 0.05, L.abdomen_bot + 0.38, st)
    hem = L.knee_y + 0.35
    slit = bool(p.get("slit", True))
    for s in "rl":   # 腿に沿う 2 枚（後ろにスリット）
        th = K.seg(f"thigh_{s}")
        x0, z0, x1, z1 = K.ring(f"thigh_{s}", th["lo"][1], th["hi"][1])
        sgn = -1 if s == "r" else 1
        xi = sgn * 0.02
        xo = x0 - o if sgn < 0 else x1 + o
        xa, xb = sorted((xi, xo))
        K.box(f"leg_{s}", xa, hem, z0 - o, xb, pv["lo"][1] + 0.3, z1 + o - (0.0 if not slit else 0.0), st)
    if K.torn:
        for s in "rl":
            th = K.seg(f"thigh_{s}")
            x0, z0, x1, z1 = K.ring(f"thigh_{s}", th["lo"][1], th["hi"][1])
            K.rags(f"leg_{s}", x0 - o, x1 + o, z0 - o, z1 + o, hem, st, K.n_rags(0.5), length=(0.3, 0.9))
    if p.get("pantyhose", True):
        ph = K.cloth("pantyhose", base=_mix(K.skin, (40, 34, 36), 0.55), folds=0.2, wear=0.0,
                     torn=0.0)
        oh = 0.07
        ladder = dict(name="stripe", orient="v", width=0.06, offset=0.4, colour=_mix(K.skin, (230, 220, 210), 0.3))
        for s in "rl":
            sh = K.seg(f"shin_{s}")
            K.wrap(f"shin_{s}", f"shin_{s}", oh, ph, y0=L.ankle_y - 0.1, y1=sh["hi"][1] + 0.05,
                   decals={"north": [ladder]} if s == "l" else None)
            th = K.seg(f"thigh_{s}")
            K.wrap(f"leg_{s}", f"thigh_{s}", oh, ph, y0=th["lo"][1] - 0.1, y1=hem + 0.3)
    return K.done()


def o_running_shorts(rig, p, ctx):
    K = _K(rig, p, ctx, "running_shorts")
    L = K.L
    st = K.cloth("shorts", folds=0.9, wear=0.2)
    o = K.off(("pelvis",) + LEGS, 0.15)
    sd = None
    if p.get("stripe", True):
        c2 = K.col2 or _contrast(K.col)
        sd = {"east": [dict(name="stripe", orient="v", width=0.18, offset=0.5, colour=c2)],
              "west": [dict(name="stripe", orient="v", width=0.18, offset=0.5, colour=c2)]}
    out = _legs(K, o, st, length="brief", thigh_decals=sd, pelvis_decals=sd, hem=st)
    K.band("pelvis", "pelvis", o + 0.06, L.abdomen_bot - 0.05, L.abdomen_bot + 0.35, st)
    if K.torn:
        for s in "rl":
            b, sg, y = out[f"end_{s}"]
            _hem_rags(K, b, sg, o, y, st, K.n_rags(0.5), length=(0.3, 0.8))
    return K.done()


# ===========================================================================
#  ブーツ
# ===========================================================================
def o_boots(rig, p, ctx):
    K = _K(rig, p, ctx, "boots")
    L = K.L
    kind = p.get("kind", "work")
    o = K.off(("foot_r", "foot_l"), 0.16)
    if kind in ("rubber", "waders", "fire"):
        up = K.st("boot", "rubber", base=K.col, wear=True)
    else:
        up = K.st("boot", "leather", base=K.col, wear=0.6)
    sole = K.st("boot_sole", "rubber", base=(26, 24, 22) if kind != "work" else (60, 46, 30), wear=True)
    shaft_top = {"work": L.ankle_y + 1.4, "combat": L.ankle_y + 3.0, "rubber": L.knee_y - 1.2,
                 "fire": L.knee_y - 0.6, "waders": L.knee_y - 0.6}.get(kind, L.ankle_y + 1.4)
    for s in "rl":
        F = _foot(K, s)
        b = f"foot_{s}"
        lace = up if kind in ("work", "combat") else None
        _shoe(K, s, up, sole, o=o, sole_h=0.42 if kind != "rubber" else 0.32, toe_h=1.05, lace=lace,
              lace_col=(30, 26, 22) if kind == "work" else (14, 14, 14), heel_h=0.15 if kind != "rubber" else 0.0)
        if kind == "work":   # 鉄芯のつま先
            K.box(b, F.x0 - o - 0.05, 0.3, F.z0 - o - 0.12, F.x1 + o + 0.05, 1.12, F.z0 - o + 1.0, up)
        # 筒（脛のボーン）
        os_ = K.off((f"shin_{s}",), 0.2)
        d = None
        if kind == "combat":
            d = {"north": [dict(name="stripe", orient="h", count=5, width=0.07, gap=0.07, colour=(10, 10, 10))]}
        elif kind == "fire":
            d = {f: [dict(name="stripe", orient="h", width=0.14, offset=0.25, colour=(220, 220, 80),
                          reflective=True)] for f in ("north", "south", "east", "west")}
        K.wrap(f"shin_{s}", f"shin_{s}", os_, up, y0=L.ankle_y - 0.25, y1=shaft_top, decals=d)
        if kind in ("rubber", "fire", "waders"):
            K.band(f"shin_{s}", f"shin_{s}", os_ + 0.08, shaft_top - 0.45, shaft_top + 0.02, up)
        if kind == "fire":   # 引き上げの取っ手
            x0, z0, x1, z1 = K.ring_at(f"shin_{s}", shaft_top - 0.3)
            for sgn in (-1, 1):
                xx = x0 - os_ - 0.12 if sgn < 0 else x1 + os_
                K.box(f"shin_{s}", xx, shaft_top - 0.2, -0.25, xx + 0.12, shaft_top + 0.45, 0.25, up)
        if K.torn >= 2:
            x0, z0, x1, z1 = K.ring_at(f"shin_{s}", shaft_top - 0.3)
            K.rags(f"shin_{s}", x0 - os_, x1 + os_, z0 - os_, z1 + os_, shaft_top - 0.6, up, K.n_rags(0.4),
                   length=(0.3, 0.7))
    if kind == "waders":
        # 胸までの胴長: 脚・腰・腹・胸当て + 肩ひも
        ol = K.off(("pelvis",) + LEGS + TORSO, 0.4)
        for s in "rl":
            th, sh = K.seg(f"thigh_{s}"), K.seg(f"shin_{s}")
            K.wrap(f"shin_{s}", f"shin_{s}", ol, up, y0=shaft_top - 0.2, y1=sh["hi"][1] + 0.05)
            K.wrap(f"leg_{s}", f"thigh_{s}", ol, up, y0=th["lo"][1] - 0.1, y1=th["hi"][1])
        pv = K.seg("pelvis")
        K.wrap("pelvis", "pelvis", ol, up, y0=pv["lo"][1] - 0.15, y1=L.abdomen_bot + 0.3)
        ab = K.seg("abdomen")
        bx0, bz0, bx1, bz1 = K.ring("abdomen", ab["lo"][1], L.chest_bot)
        K.box("torso", bx0 - ol, ab["lo"][1] - 0.1, bz0 - ol, bx1 + ol, L.chest_bot + 0.2, bz1 + ol, up)
        ch = K.seg("chest")
        x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
        K.box("chest", -1.8, L.chest_bot - 0.05, z0 - ol, 1.8, L.chest_bot + 1.6, z0 - ol + 0.25, up)
        sus = K.st("wader_strap", "kevlar", base=(30, 30, 30), wear=True)
        for sgn in (-1, 1):
            K.box("chest", sgn * 1.0 - 0.25, L.chest_bot + 1.4, z0 - ol - 0.05, sgn * 1.0 + 0.25, ch["hi"][1] + 0.2,
                  z1 + ol + 0.05, sus)
    return K.done()


# ===========================================================================
#  手・腕
# ===========================================================================
def _hand_cubes(K: _K, s: str) -> Dict[str, list]:
    """手のキューブを手のひら・指の根元の節・先の節・親指に分ける（nr_rig の手そのまま）。"""
    out = {"palm": [], "prox": [], "dist": [], "thumb": []}
    for c in K.rig.bones[f"hand_{s}"].cubes:
        if getattr(c, "nr_kit", None) or getattr(c, "nr_seg", None) != f"hand_{s}":
            continue
        if getattr(c, "nr_role", None) == "nail":
            continue
        rot = c.rotation or [0, 0, 0]
        if not any(abs(v) > 0.01 for v in rot):
            out["palm"].append(c)
        elif abs(rot[0]) > 1.0:
            out["thumb"].append(c)
        elif abs(rot[2]) < 20:
            out["prox"].append(c)
        else:
            out["dist"].append(c)
    return out


def _cover(K: _K, bone: str, c, pad: float, style: str, uv=None, shorten: float = 0.0):
    """体のキューブ c を pad だけ太らせた写し（同じ回転と回転の中心）。手袋・包帯に使う。
    shorten > 0 なら局所 +Y の端（梁の上端）を残して下端を詰める。"""
    from mcmodel import Cube
    o = [c.origin[0] - pad, c.origin[1] - pad + shorten, c.origin[2] - pad]
    sz = [c.size[0] + 2 * pad, max(0.05, c.size[1] + 2 * pad - shorten), c.size[2] + 2 * pad]
    piv = c.pivot
    if c.rotation and any(c.rotation) and piv is None:
        piv = [c.origin[i] + c.size[i] / 2 for i in range(3)]
    cube = Cube(o, sz, style, uv_scale=uv or K.U["hand"], rotation=c.rotation, pivot=piv)
    cube.nr_kit = K.key
    cube.nr_role = None
    cube.nr_seg = None
    K.rig.bones[bone].add(cube)
    K.cubes.append(cube)
    return cube


def o_gloves(rig, p, ctx):
    K = _K(rig, p, ctx, "gloves")
    L = K.L
    kind = p.get("kind", "work")
    mat = {"work": "leather", "rubber": "rubber", "surgical": "rubber", "leather": "leather",
           "fingerless": "cloth", "satin": "cloth"}[kind]
    if mat == "cloth":
        st = K.cloth("glove", folds=0.5 if kind == "satin" else 0.8, wear=0.3)
    else:
        st = K.st("glove", mat, base=K.col, wear=0.5)
    pad = {"work": 0.1, "rubber": 0.08, "surgical": 0.045, "leather": 0.07, "fingerless": 0.09,
           "satin": 0.05}[kind]
    cuff_top = {"work": L.wrist_y + 0.9, "rubber": L.wrist_y + 2.6, "surgical": L.wrist_y + 0.8,
                "leather": L.wrist_y + 0.7, "fingerless": L.wrist_y + 0.6, "satin": L.elbow_y + 1.2}[kind]
    for s in _sides(p):
        hc = _hand_cubes(K, s)
        b = f"hand_{s}"
        for c in hc["palm"]:
            _cover(K, b, c, pad, st)
        if kind == "fingerless":
            for c in hc["prox"]:
                _cover(K, b, c, pad, st, shorten=c.size[1] * 0.55)
            for c in hc["thumb"][:1]:
                _cover(K, b, c, pad, st)
        else:
            for c in hc["prox"] + hc["dist"] + hc["thumb"]:
                _cover(K, b, c, pad, st)
        # 袖口（前腕の先）
        oc = K.off((f"forearm_{s}",), pad + 0.08)
        if kind == "satin":
            K.wrap(f"forearm_{s}", f"forearm_{s}", oc, st, y0=L.wrist_y - 0.1, y1=K.seg(f"forearm_{s}")["hi"][1])
            K.wrap(f"arm_{s}", f"upper_arm_{s}", oc, st, y0=K.seg(f"upper_arm_{s}")["lo"][1] - 0.1, y1=cuff_top)
        else:
            K.wrap(f"forearm_{s}", f"forearm_{s}", oc, st, y0=L.wrist_y - 0.15, y1=cuff_top)
            if kind in ("work", "rubber"):
                K.band(f"forearm_{s}", f"forearm_{s}", oc + 0.1, cuff_top - 0.35, cuff_top + 0.02, st)
    return K.done()


def o_wristwatch(rig, p, ctx):
    K = _K(rig, p, ctx, "wristwatch")
    L = K.L
    s = p.get("side", "l")
    kind = p.get("kind", "steel")
    sgn = -1 if s == "r" else 1
    b = f"forearm_{s}"
    if kind == "dress":
        band = K.st("watch_band", "leather", base=(60, 36, 24), wear=True)
    elif kind == "fitness":
        band = K.st("watch_band", "rubber", base=K.col, wear=False)
    else:
        band = K.st("watch_band", "chrome", wear=False, base=K.col)
    o = K.off((f"forearm_{s}",), 0.1)
    y0, y1 = L.wrist_y + 0.2, L.wrist_y + 0.55
    K.band(b, f"forearm_{s}", o, y0, y1, band)
    x0, z0, x1, z1 = K.ring_at(f"forearm_{s}", (y0 + y1) / 2)
    xo = (x0 - o - 0.16) if sgn < 0 else (x1 + o)
    if kind == "fitness":
        face = K.st("watch_screen", "glow", wear=False, base=(60, 200, 120))
    else:
        face = K.st("watch_face", "glass", wear=False, base=(214, 210, 196) if kind != "gold" else (230, 210, 150),
                    crack=0.8 if p.get("cracked", False) else 0.0)
    rim = band if kind != "dress" else K.st("watch_rim", "chrome", wear=False, base=(214, 186, 110))
    K.box(b, xo, y0 - 0.12, -0.42, xo + 0.16, y1 + 0.12, 0.42, rim)
    K.box(b, xo + (0.1 if sgn > 0 else -0.04), y0 - 0.04, -0.32, xo + (0.2 if sgn > 0 else 0.06), y1 + 0.04, 0.32,
          face, uv=K.U["face"])
    return K.done()


def _chain(K: _K, bone: str, p0, n: int, st: str, drift=(0.0, -1.0, 0.0), link: float = 0.62) -> list:
    """鎖: 縦横交互の輪を n 個、p0 から drift の向きへ垂らす。"""
    out = []
    d = np.asarray(drift, float)
    d = d / (np.linalg.norm(d) or 1.0)
    x, y, z = p0
    for i in range(n):
        c = (x + d[0] * link * (i + 0.5), y + d[1] * link * (i + 0.5), z + d[2] * link * (i + 0.5))
        # 輪の向きは鎖の向きに合わせて傾ける（縦横交互）
        rx = round(math.degrees(math.atan2(-d[2], -d[1])), 2) if abs(d[1]) > 1e-3 else 0.0
        sz = (0.18, link + 0.12, 0.42) if i % 2 == 0 else (0.42, link + 0.12, 0.18)
        out.append(K.cbox(bone, c, sz, st, rot=(rx, 0, 0)))
    return out


def o_chain_shackles(rig, p, ctx):
    K = _K(rig, p, ctx, "chain_shackles")
    L = K.L
    kind = p.get("kind", "chain")
    n = max(1, min(8, int(p.get("chain_len", 4))))
    broken = bool(p.get("broken", False))
    if kind == "chain":
        st = K.st("shackle", "rust" if K.dirty >= 2 else "metal", base=K.col, wear=0.6, amount=0.5,
                  metal=K.col)
    else:
        st = K.st("strap", "leather", base=K.col, wear=0.7)
    met = K.st("shackle_buckle", "metal", base=(150, 150, 150), wear=0.5)
    spots = []
    if p.get("wrists", True):
        spots += [(f"forearm_{s}", f"forearm_{s}", L.wrist_y + 0.1, L.wrist_y + 0.75, s) for s in "rl"]
    if p.get("ankles", False):
        spots += [(f"shin_{s}", f"shin_{s}", L.ankle_y + 0.1, L.ankle_y + 0.75, s) for s in "rl"]
    for bone, seg, y0, y1, s in spots:
        o = K.off((seg,), 0.14)
        K.band(bone, seg, o + (0.06 if kind != "chain" else 0.0), y0, y1, st)
        x0, z0, x1, z1 = K.ring_at(seg, (y0 + y1) / 2)
        sgn = -1 if s == "r" else 1
        if kind == "chain":
            inward = 1 if s == "r" else -1
            start = ((x0 + x1) / 2 + inward * 0.1, y0 + 0.15, z0 - o - 0.35)
            m = n + 1 if broken else max(3, n)
            # 手の前（親指より前）へ垂れる。足首の鎖は前の地面へ
            drift = (inward * 0.15, -1.0, -0.95) if not bone.startswith("shin") else (inward * 0.6, -0.3, -0.6)
            _chain(K, bone, start, m, st, drift)
        else:
            K.cbox(bone, ((x0 + x1) / 2, (y0 + y1) / 2, z0 - o - 0.12), (0.45, 0.4, 0.14), met)
            ln = 1.2 + (1.4 if broken else 0.0)
            K.beam(bone, ((x0 + x1) / 2 + sgn * 0.2, y0, z0 - o - 0.05),
                   ((x0 + x1) / 2 + sgn * 0.5, y0 - ln, z0 - o - 0.25), 0.35, 0.08, st)
    return K.done()


_WRAP_SEG = {"arm_r": "upper_arm_r", "arm_l": "upper_arm_l", "forearm_r": "forearm_r", "forearm_l": "forearm_l",
             "leg_r": "thigh_r", "leg_l": "thigh_l", "shin_r": "shin_r", "shin_l": "shin_l", "chest": "chest",
             "torso": "abdomen", "neck": "neck", "pelvis": "pelvis", "foot_r": "foot_r", "foot_l": "foot_l"}


def o_bandage_wrap(rig, p, ctx):
    K = _K(rig, p, ctx, "bandage_wrap")
    L = K.L
    st = K.cloth("bandage", folds=0.9, wear=0.4, pattern="hstripes", alt=_mul(K.col, 0.86), period=0.4)
    on = p.get("on", ["forearm_r"])
    on = [on] if isinstance(on, str) else list(on)
    rng = K.rng
    for bone in on:
        if bone in ("hand_r", "hand_l"):
            s = bone[-1]
            hc = _hand_cubes(K, s)
            for c in hc["palm"]:
                _cover(K, bone, c, 0.08, st)
            for c in hc["prox"]:
                _cover(K, bone, c, 0.06, st, shorten=c.size[1] * 0.45)
            o = K.off((f"forearm_{s}",), 0.1)
            K.wrap(f"forearm_{s}", f"forearm_{s}", o, st, y0=L.wrist_y - 0.1, y1=L.wrist_y + 1.2)
            continue
        if bone in ("head", "jaw"):
            H = _head(K)
            o = K.off(("head",), 0.12)
            K.box("head", H.x0 - o, H.brow + 0.05, H.z0 - o - 0.25, H.x1 + o, H.brow + 0.75, H.z1 + o, st)
            K.box("head", H.x0 - o - 0.02, H.eye - 0.25, H.z0 - o - 0.27, 0.15, H.brow + 0.7, H.z0 - o + 0.6, st,
                  rot=(0, 0, -24), pivot=(-0.4, H.brow, H.z0))
            K.beam("head", (H.x1 * 0.4, H.brow + 0.3, H.z1 + o), (H.x1 * 0.6, H.brow - 1.6, H.z1 + o + 0.4),
                   0.35, 0.08, st)
            continue
        seg = _WRAP_SEG.get(bone)
        if seg is None:
            continue
        sg = K.seg(seg)
        o = K.off((seg,), 0.12)
        lo, hi = sg["lo"][1], sg["hi"][1]
        nb = 3 if hi - lo > 2.5 else 2
        for i in range(nb):
            y = lo + (hi - lo) * (0.2 + 0.6 * i / max(1, nb - 1))
            x0, z0, x1, z1 = K.ring_at(seg, y)
            K.box(bone, x0 - o, y - 0.38, z0 - o, x1 + o, y + 0.38, z1 + o, st,
                  rot=(rng.uniform(-8, 8), 0, rng.uniform(-10, 10)), pivot=((x0 + x1) / 2, y, (z0 + z1) / 2))
        x0, z0, x1, z1 = K.ring_at(seg, lo + (hi - lo) * 0.2)
        K.beam(bone, ((x0 + x1) / 2, lo + (hi - lo) * 0.2, z0 - o), ((x0 + x1) / 2 + 0.3, lo - 0.9, z0 - o - 0.3),
               0.35, 0.08, st)
    return K.done()


_TATTOO_FACES = {"arm_r": ("east", "north"), "arm_l": ("west", "north"), "forearm_r": ("east", "north"),
                 "forearm_l": ("west", "north"), "chest": ("north",), "torso": ("north",), "neck": ("north", "east"),
                 "leg_r": ("north", "east"), "leg_l": ("north", "west"), "shin_r": ("north",), "shin_l": ("north",),
                 "head": ("east",), "hand_r": ("east",), "hand_l": ("west",), "pelvis": ("north",)}


def _tattoo_decals(motif: str, ink, accent, rng) -> list:
    if motif == "skull":
        return [dict(name="badge", kind="circle", at=(0.5, 0.45), size=0.42, colour=ink)]
    if motif == "script":
        return [dict(name="text", text=rng.choice(("MOM", "HATE", "LOVE", "FATE", "SIN")), at=(0.5, 0.5),
                     colour=ink, wear=0.2)]
    if motif == "koi":
        return [dict(name="stripe", orient="d", count=3, width=0.08, gap=0.14, colour=ink),
                dict(name="badge", kind="star", at=(0.45, 0.5), size=0.35, colour=accent)]
    if motif == "barbed":
        return [dict(name="stripe", orient="h", count=2, width=0.05, gap=0.04, offset=0.45, colour=ink),
                dict(name="stripe", orient="d", count=5, width=0.035, gap=0.12, offset=0.45, colour=ink)]
    return [dict(name="stripe", orient="d", count=3, width=0.11, gap=0.12, colour=ink),
            dict(name="stripe", orient="h", width=0.08, offset=0.2, colour=ink)]


def _exposed(cubes: list, face: str):
    """face の向きに一番外へ出ているキューブ（その面の面積が大きい物の中から）。"""
    ax = {"north": 2, "south": 2, "east": 0, "west": 0, "up": 1, "down": 1}[face]
    other = [i for i in range(3) if i != ax]

    def area(c):
        return c.size[other[0]] * c.size[other[1]]

    def ext(c):
        if face in ("north", "east", "down"):
            return -c.origin[ax]
        return c.origin[ax] + c.size[ax]

    amax = max(area(c) for c in cubes)
    return max([c for c in cubes if area(c) >= 0.25 * amax], key=ext)


def o_tattoo(rig, p, ctx):
    """入れ墨: キューブは足さず、指定のボーンの一番大きな肌のキューブの外側の面にデカールを描く。"""
    K = _K(rig, p, ctx, "tattoo")
    on = p.get("on", ["arm_r"])
    on = [on] if isinstance(on, str) else list(on)
    motif = p.get("motif", "tribal")
    ink = K.col
    accent = K.col2 or (210, 90, 40)
    for bone in on:
        b = K.rig.bones.get(bone)
        if b is None:
            continue
        skin = [c for c in b.cubes if c.style in ("skin", "skin_dark") and not getattr(c, "nr_kit", None)
                and getattr(c, "nr_seg", None) and not (c.rotation and any(c.rotation))]
        if not skin:
            continue
        for face in _TATTOO_FACES.get(bone, ("north",)):
            c = _exposed(skin, face)
            cur = c.decals.get(face)
            lst = [] if cur is None else ([cur] if isinstance(cur, (str, dict)) else list(cur))
            if any(isinstance(d, dict) and d.get("name") == "face" for d in lst):
                continue
            lst += _tattoo_decals(motif, ink, accent, K.rng)
            c.decals[face] = lst
    return K.done()


# ===========================================================================
#  装備
# ===========================================================================
def _straps(K: _K, st: str, o: float, xs=(-1.05, 1.05), w: float = 0.42, bot: Optional[float] = None) -> list:
    """背負い物の肩ベルト: 胸の前の縦の帯 + 肩の上を越えて背中へ。"""
    L = K.L
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    top = ch["hi"][1] + o + 0.05
    bot = L.chest_bot - 0.3 if bot is None else bot
    out = []
    for xc in xs:
        out.append(K.box("chest", xc - w / 2, bot, z0 - o - 0.14, xc + w / 2, top, z0 - o, st))
        out.append(K.box("chest", xc - w / 2, top - 0.2, z0 - o - 0.1, xc + w / 2, top + 0.02, z1 + o + 0.1, st))
    return out


def o_backpack(rig, p, ctx):
    K = _K(rig, p, ctx, "backpack")
    L = K.L
    kind = p.get("kind", "daypack")
    o = K.off(TORSO, 0.35)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    zb = z1 + o
    st = K.cloth("pack", folds=0.7, wear=0.6) if kind != "delivery_box" else \
        K.st("delivery_box", "plastic", base=K.col, wear=0.6)
    strap = K.st("pack_strap", "kevlar", base=(28, 28, 30), wear=True)
    _straps(K, strap, o)
    if kind == "delivery_box":
        bw, bh, bd = 4.4, 4.2, 3.0
        y0 = L.chest_bot - 2.4
        logo = dict(name="logo", at=(0.5, 0.5), size=0.8, colour=_contrast(K.col), text="EATS")
        K.box("chest", -bw / 2, y0, zb, bw / 2, y0 + bh, zb + bd, st, uv=K.U["fine"],
              decals={"south": [logo], "east": [dict(logo, text="GO")], "west": [dict(logo, text="GO")]})
        if p.get("lid_open", False):
            K.box("chest", -bw / 2, y0 + bh, zb + bd - 0.15, bw / 2, y0 + bh + 0.25, zb + bd + bd - 0.2, st,
                  rot=(-70, 0, 0), pivot=(0, y0 + bh + 0.1, zb + bd))
            inner = K.st("delivery_inner", "plastic", base=(170, 170, 166), wear=True)
            K.box("chest", -bw / 2 + 0.2, y0 + bh - 0.6, zb + 0.2, bw / 2 - 0.2, y0 + bh - 0.05, zb + bd - 0.2, inner)
        else:
            K.box("chest", -bw / 2 - 0.05, y0 + bh, zb - 0.05, bw / 2 + 0.05, y0 + bh + 0.25, zb + bd + 0.05, st)
        return K.done()
    if kind == "rucksack":
        bw, bh, bd = 3.4, 6.0, 1.9
        y0 = L.abdomen_bot - 0.3
    else:
        bw, bh, bd = 3.0, 4.2, 1.5
        y0 = L.chest_bot - 1.6
    zd = [dict(name="zipper", u=0.5)]
    K.box("chest", -bw / 2, y0, zb, bw / 2, y0 + bh, zb + bd, st,
          decals={"south": [dict(name="pocket", box=(0.15, 0.55, 0.85, 0.9))], "up": zd})
    K.box("chest", -bw / 2 + 0.35, y0 + 0.2, zb + bd - 0.05, bw / 2 - 0.35, y0 + bh * 0.5, zb + bd + 0.6, st)
    K.beam("chest", (-0.45, y0 + bh, zb + 0.6), (0.45, y0 + bh + 0.01, zb + 0.6), 0.2, 0.25, strap)
    if kind == "rucksack":
        roll = K.cloth("bedroll", base=(110, 30, 30) if not K.col2 else K.col2, folds=1.3)
        K.box("chest", -bw / 2 - 0.4, y0 + bh, zb + 0.2, bw / 2 + 0.4, y0 + bh + 1.2, zb + 1.4, roll)
        for sgn in (-1, 1):   # 横のポケット
            xa = -bw / 2 - 0.5 if sgn < 0 else bw / 2
            K.box("chest", xa, y0 + 0.4, zb + 0.2, xa + 0.5, y0 + 2.2, zb + bd - 0.3, st)
    if K.torn >= 2:
        K.beam("chest", (bw / 2 - 0.3, y0 + 0.2, zb + bd), (bw / 2 + 0.2, y0 - 1.8, zb + bd + 0.3), 0.4, 0.1, strap)
    return K.done()


def o_tool_belt(rig, p, ctx):
    K = _K(rig, p, ctx, "tool_belt")
    L = K.L
    st = K.st("tool_belt", "leather", base=K.col, wear=0.7)
    met = K.st("tool_metal", "metal", base=(140, 142, 146), wear=0.6)
    o = K.off(("pelvis",), 0.35)
    _belt(K, o, st, K.st("tool_buckle", "chrome", wear=False, base=(170, 168, 160)), h=0.55)
    px0, pz0, px1, pz1 = K.ring_at("pelvis", L.abdomen_bot)
    yb = L.abdomen_bot
    for sgn in (-1, 1):   # 両腰のポーチ
        xa = px0 - o - 0.65 if sgn < 0 else px1 + o
        K.box("pelvis", xa, yb - 1.6, -1.0, xa + 0.65, yb + 0.25, 0.6, st)
    tools = p.get("tools", ["hammer", "tape"])
    tools = [tools] if isinstance(tools, str) else list(tools)
    wood = K.st("tool_handle", "wood", base=(150, 110, 70), wear=0.4)
    for i, t in enumerate(tools):
        side = -1 if i % 2 == 0 else 1
        xs = (px0 - o - 0.35) if side < 0 else (px1 + o + 0.35)
        if t == "hammer":
            K.beam("pelvis", (xs, yb - 0.2, -1.15), (xs + side * 0.2, yb - 2.8, -1.3), 0.3, 0.3, wood)
            K.cbox("pelvis", (xs, yb + 0.05, -1.15), (0.36, 0.42, 1.1), met)
        elif t == "tape":
            yel = K.st("tape_measure", "plastic", base=(230, 190, 30), wear=True)
            K.cbox("pelvis", (side * 0.9, yb - 0.4, pz0 - o - 0.3), (0.8, 0.8, 0.45), yel)
        elif t == "pliers":
            red = K.st("plier_grip", "rubber", base=(180, 30, 30), wear=True)
            for k in (-1, 1):
                K.beam("pelvis", (xs + k * 0.08, yb - 0.1, 0.9), (xs + k * 0.22, yb - 1.9, 1.0), 0.14, 0.14, red)
            K.cbox("pelvis", (xs, yb + 0.15, 0.9), (0.26, 0.6, 0.18), met)
        elif t == "knife":
            K.box("pelvis", xs - 0.18, yb - 1.9, 0.75, xs + 0.18, yb + 0.1, 1.05, st)
            K.cbox("pelvis", (xs, yb + 0.45, 0.9), (0.24, 0.7, 0.24), wood)
    return K.done()


def o_air_tank(rig, p, ctx):
    K = _K(rig, p, ctx, "air_tank")
    L = K.L
    bone = K.child("gear_tank")
    dent = _lv(p.get("dented", 0))
    tank = K.st("air_tank", "painted_metal", base=K.col, rust=0.15, wear=0.5)
    frame = K.st("tank_frame", "metal", base=(60, 60, 64), wear=0.5)
    strap = K.st("tank_strap", "kevlar", base=(30, 30, 32), wear=True)
    o = K.off(TORSO, 0.4)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    zb = z1 + o
    _straps(K, strap, o)
    # 背負い枠（chest。ボンベが割れても残る）
    K.box("chest", -1.5, L.chest_bot - 2.4, zb, 1.5, ch["hi"][1] - 0.4, zb + 0.3, frame)
    # ボンベ（十字の 2 個で丸く）。弁は下
    r = 1.15
    yb, yt = L.chest_bot - 2.6, ch["hi"][1] + 0.5
    zc = zb + 0.3 + r
    dec = {"south": [dict(name="cracks", amount=0.3 * dent)] if dent else [],
           "east": [dict(name="stripe", orient="h", width=0.1, offset=0.15, colour=(30, 30, 30))]}
    K.box(bone, -r, yb, zc - r * 0.62, r, yt, zc + r * 0.62, tank, decals=dec)
    K.box(bone, -r * 0.62, yb - 0.01, zc - r, r * 0.62, yt + 0.25, zc + r, tank)
    K.cbox(bone, (0, yb - 0.35, zc), (0.7, 0.7, 0.7), frame)                                   # 弁
    K.cbox(bone, (0.5, yb - 0.35, zc), (0.5, 0.36, 0.36), K.st("tank_knob", "rubber", base=(170, 30, 30),
                                                            wear=False))
    if p.get("hose", True):
        hose = K.st("tank_hose", "rubber", base=(26, 26, 28), wear=False)
        side = 1.0
        K.beam("chest", (side * 0.3, yb - 0.35, zc), (side * (x1 + o + 0.2), L.chest_bot - 0.8, 0.2), 0.22, 0.22, hose)
        K.beam("chest", (side * (x1 + o + 0.2), L.chest_bot - 0.8, 0.2), (side * 0.5, L.chest_bot + 0.3, z0 - o - 0.4),
               0.22, 0.22, hose)
        if p.get("mask", "hanging") == "hanging":
            rub = K.st("tank_mask", "rubber", base=(30, 30, 32), wear=True)
            lens = K.st("tank_mask_lens", "glass", wear=False, base=(120, 140, 140))
            K.box("chest", -0.5, L.chest_bot - 0.6, z0 - o - 0.9, 1.3, L.chest_bot + 1.3, z0 - o - 0.2, rub,
                  rot=(0, 0, 8))
            K.box("chest", -0.3, L.chest_bot + 0.2, z0 - o - 1.0, 1.1, L.chest_bot + 1.1, z0 - o - 0.8, lens,
                  rot=(0, 0, 8), pivot=(0.4, L.chest_bot + 0.35, z0 - o - 0.5))
    return K.done()


def o_name_badge(rig, p, ctx):
    K = _K(rig, p, ctx, "name_badge")
    L = K.L
    style = p.get("style", "lanyard")
    o = K.off(TORSO, 0.3)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    zf = z0 - o
    if style == "dogtag":
        met = K.st("dogtag", "chrome", wear=False, base=(186, 186, 190))
        top = ch["hi"][1] + 0.1
        for sgn in (-1, 1):
            K.beam("chest", (sgn * 1.1, top, 0.2), (sgn * 0.12, L.chest_bot + 1.6, zf - 0.08), 0.08, 0.08, met)
        K.cbox("chest", (0.0, L.chest_bot + 1.25, zf - 0.08), (0.48, 0.75, 0.08), met, rot=(0, 0, 6))
        K.cbox("chest", (0.18, L.chest_bot + 1.1, zf - 0.14), (0.48, 0.75, 0.08), met, rot=(0, 0, -10))
        return K.done()
    card = K.st("id_card", "plastic", base=(236, 234, 228), wear=True)
    name = K.rng.choice(("STAFF", "VISITOR", "A.KANE", "M.ROSS", "J.DOE"))
    dec = {"north": [dict(name="stripe", orient="h", width=0.22, offset=0.1, colour=K.col),
                     dict(name="badge", kind="patch", at=(0.3, 0.5), size=0.55, colour=(150, 130, 120)),
                     dict(name="text", text=name[:6], at=(0.5, 0.82), colour=(30, 30, 40), wear=0.1)]}
    if style == "lanyard":
        cord = K.st("lanyard", "cloth", base=K.col, wear=True, folds=0.0)
        cy = L.chest_bot + 0.6
        top = ch["hi"][1] + 0.15
        for sgn in (-1, 1):
            K.beam("chest", (sgn * 1.15, top, 0.0), (sgn * 0.15, cy + 0.85, zf - 0.08), 0.14, 0.08, cord)
        K.box("chest", -1.25, top - 0.12, 0.0, 1.25, top + 0.06, z1 + o, cord)
        K.cbox("chest", (0, cy, zf - 0.1), (1.1, 1.5, 0.08), card, uv=K.U["face"], decals=dec)
    else:   # clip: 左胸
        K.cbox("chest", (1.25, L.shoulder_y - 1.5, zf - 0.08), (1.2, 0.85, 0.08), card, uv=K.U["face"],
               decals={"north": [dict(name="stripe", orient="h", width=0.25, offset=0.12, colour=K.col),
                                 dict(name="text", text=name[:6], at=(0.5, 0.65), colour=(30, 30, 40), wear=0.1)]})
        K.cbox("chest", (1.25, L.shoulder_y - 1.0, zf - 0.12), (0.3, 0.3, 0.1),
               K.st("badge_clip", "chrome", wear=False, base=(180, 180, 186)))
    return K.done()


def o_flashlight(rig, p, ctx):
    K = _K(rig, p, ctx, "flashlight")
    L = K.L
    mount = p.get("mount", "shoulder")
    lit = bool(p.get("lit", True))
    body = K.st("flashlight", "plastic", base=K.col, wear=0.5)
    lens = K.st("flashlight_lens", "glow", wear=False, base=_c3(p.get("beam", (255, 240, 200)))) if lit else \
        K.st("flashlight_lens", "glass", wear=False, base=(200, 200, 190))
    if mount == "hand":
        bone = K.child("gear_flashlight_hand")
        ax = K.L.arm_x
        g = np.array([ax - 0.35, L.wrist_y - L.palm_l * 0.8, 0.0])
        d = np.array([0.0, -0.45, -1.0])
        d /= np.linalg.norm(d)
        K.beam(bone, g - d * 0.9, g + d * 1.9, 0.5, 0.5, body)
        tip = g + d * 1.9
        K.cbox(bone, tuple(tip + d * 0.15), (0.7, 0.7, 0.3), lens, rot=(math.degrees(math.atan2(-d[1], -d[2])), 0, 0))
        return K.done()
    bone = K.child("gear_flashlight")
    o = K.off(TORSO, 0.3)
    ch = K.seg("chest")
    x0, z0, x1, z1 = K.ring("chest", L.chest_bot, ch["hi"][1])
    y = ch["hi"][1] - 0.9
    xc = 1.35
    zf = z0 - o
    K.box(bone, xc - 0.3, y - 0.3, zf - 1.3, xc + 0.3, y + 0.3, zf + 0.05, body)             # 胴
    K.box(bone, xc - 0.4, y - 0.4, zf - 1.55, xc + 0.4, y + 0.4, zf - 1.2, body)             # 頭
    K.box(bone, xc - 0.3, y - 0.3, zf - 1.62, xc + 0.3, y + 0.3, zf - 1.5, lens)             # レンズ
    clip = K.st("flashlight_clip", "kevlar", base=(30, 30, 32), wear=True)
    K.box("chest", xc - 0.35, y - 0.55, zf - 0.12, xc + 0.35, ch["hi"][1] + o, zf + 0.0, clip)
    if lit:   # 光のにじみ（短い円錐の代わりに、広がる 2 枚の薄い光）
        K.box(bone, xc - 0.55, y - 0.55, zf - 1.75, xc + 0.55, y + 0.55, zf - 1.66, lens)
    return K.done()


def o_riot_shield(rig, p, ctx):
    K = _K(rig, p, ctx, "riot_shield")
    L = K.L
    bone = K.child("gear_shield")
    cr = _lv(p.get("cracked", 0))
    rim = K.st("shield_rim", "rubber", base=(30, 32, 36), wear=True)
    glass = K.st("shield_glare", "glass", wear=False, base=K.col, crack=0.3 * cr)
    fa = K.seg("forearm_l")
    fx0, fz0, fx1, fz1 = K.ring("forearm_l", fa["lo"][1], fa["hi"][1])
    xc = (fx0 + fx1) / 2 - 0.4
    zf = fz0 - 1.0
    w, h = 6.2, 10.0
    yc = (L.wrist_y + L.elbow_y) / 2 - 0.6
    x0, x1, y0, y1 = xc - w / 2, xc + w / 2, yc - h / 2, yc + h / 2
    # 枠だけを作って中を開ける（透明の盾）。中ほどに POLICE の帯
    _visor_frame(K, bone, x0, x1, y0, y1, zf, rim, glass, cracked=cr, th=0.25)
    text = str(p.get("text", "POLICE"))
    band = K.st("shield_band", "plastic", base=(26, 28, 32), wear=True)
    _label(K, bone, (xc, yc + 1.2, zf - 0.2), w - 0.4, 0.95, "north", text, (236, 236, 230), band, th=0.12)
    # 取っ手（前腕へ）
    for yy in (L.wrist_y + 0.8, L.elbow_y - 0.6):
        K.box(bone, (fx0 + fx1) / 2 - 0.2, yy - 0.2, zf, (fx0 + fx1) / 2 + 0.2, yy + 0.2, fz0 + 0.05, rim)
    return K.done()


_TOOLS = ("wrench", "cleaver", "pipe", "hammer", "scalpel", "rebar_sledge", "fire_axe")


def o_held_tool(rig, p, ctx):
    K = _K(rig, p, ctx, "held_tool")
    L = K.L
    kind = p.get("kind", "wrench")
    side = p.get("hand", "r")
    bone = K.child("held_tool" if side == "r" else "held_tool_l")
    sgn = -1 if side == "r" else 1
    inward = -sgn
    ax = sgn * L.arm_x
    g = np.array([ax + inward * 0.25, L.wrist_y - L.palm_l * 0.75, -0.1])     # 握りの中心
    d = np.array([sgn * 0.12, -1.0, -0.8])                                     # 前下へ（振ると前を向く）
    d /= np.linalg.norm(d)
    metal = lambda: K.st("tool_steel", "metal", base=K.col, wear=0.6)                # noqa: E731
    wood = lambda: K.st("tool_wood", "wood", base=(140, 100, 60), wear=0.5)           # noqa: E731
    rubber = K.st("tool_grip", "rubber", base=(30, 30, 32), wear=True)

    def P(t, off=(0, 0, 0)):
        return tuple(g + d * t + np.asarray(off, float))

    if kind == "wrench":
        m = metal()
        K.beam(bone, P(-0.8), P(4.4), 0.42, 0.26, m)
        side = np.array([0.0, d[2], -d[1]])            # 柄に直角（前後の面内）
        K.cbox(bone, P(4.75), (0.42, 1.25, 1.25), m, rot=(round(math.degrees(math.atan2(d[2], -d[1])), 2), 0, 0))
        K.beam(bone, P(5.1, side * 0.42), P(5.75, side * 0.42), 0.4, 0.36, m)
        K.beam(bone, P(5.1, -side * 0.42), P(5.75, -side * 0.42), 0.4, 0.36, m)
    elif kind == "cleaver":
        K.beam(bone, P(-0.8), P(1.1), 0.4, 0.4, wood())
        bl = K.st("cleaver_blade", "metal", base=(170, 172, 176), wear=0.3, blood=_BLOOD[K.bloody] + 0.3)
        K.beam(bone, P(1.1, (0, 0, -0.85)), P(4.2, (0, 0, -0.85)), 0.1, 2.0, bl)
    elif kind == "pipe":
        rust = K.st("pipe_rust", "rust", base=K.col, amount=0.6, metal=K.col)
        K.beam(bone, P(-1.2), P(7.2), 0.5, 0.5, rust)
        K.cbox(bone, P(7.3), (0.75, 0.75, 0.75), rust)
    elif kind == "hammer":
        K.beam(bone, P(-0.8), P(3.7), 0.38, 0.38, wood())
        K.beam(bone, P(3.8, (0, 0, 0.8)), P(3.8, (0, 0, -0.95)), 0.58, 0.58, metal())
    elif kind == "scalpel":
        K.beam(bone, P(-0.5), P(1.2), 0.2, 0.15, metal())
        bl = K.st("scalpel_blade", "chrome", wear=False, base=(220, 222, 226), blood=_BLOOD[K.bloody] + 0.4)
        K.beam(bone, P(1.2), P(1.85), 0.07, 0.24, bl)
    elif kind == "rebar_sledge":
        # 引きずる鉄筋（握りから地面へ）の先にコンクリの塊
        rebar = K.st("rebar", "rust", base=(120, 90, 70), amount=0.8, metal=(110, 100, 90))
        conc = K.st("rubble", "concrete", base=(150, 146, 140), cracks=0.8, blood=_BLOOD[K.bloody] + 0.4)
        end = np.array([g[0] + inward * 0.4, 0.9, g[2] - 1.6])
        K.beam(bone, tuple(g + np.array([0, 0.9, 0.1])), tuple(end), 0.26, 0.26, rebar)
        K.cbox(bone, tuple(end + np.array([0, 0.1, -0.2])), (2.2, 1.8, 2.0), conc, rot=(8, 25, -6))
        K.cbox(bone, tuple(end + np.array([0.5, 0.5, -0.9])), (1.2, 1.0, 1.2), conc, rot=(-12, 10, 18))
        for k in range(3):
            q = end + np.array([K.rng.uniform(-0.9, 0.9), K.rng.uniform(0.3, 1.0), K.rng.uniform(-1.2, 0.6)])
            K.beam(bone, tuple(q), tuple(q + np.array([K.rng.uniform(-0.6, 0.6), 0.9, K.rng.uniform(-0.5, 0.5)])),
                   0.14, 0.14, rebar)
    elif kind == "fire_axe":
        red = K.st("axe_head", "painted_metal", base=(190, 30, 30), rust=0.2, wear=0.5)
        K.beam(bone, P(-1.0), P(5.8), 0.42, 0.42, K.st("axe_handle", "wood", base=(170, 120, 60), wear=0.4))
        K.beam(bone, P(5.4, (0, 0, 0.25)), P(5.4, (0, 0, -1.8)), 0.22, 1.0, red)
        K.beam(bone, P(5.4, (0, 0, 0.25)), P(5.4, (0, 0, 1.3)), 0.24, 0.36, red)
    K.cbox(bone, tuple(g), (0.5, 0.5, 0.5), rubber)    # 握った所の巻き
    return K.done()


# ===========================================================================
#  語彙に後から増えた鍵の受け皿（形の無い部品。自己テストが「まだ形の無い鍵」として報告する）
# ===========================================================================
def _todo(key):
    def fn(rig, p, ctx):
        K = _K(rig, p, ctx, key)
        return K.done()
    fn.__name__ = f"o_{key}"
    fn._todo = True
    return fn


OUTFITS = {k[2:]: v for k, v in list(globals().items())
           if k.startswith("o_") and callable(v) and k[2:] in S.OUTFIT_VOCAB}
for _k in S.OUTFIT_VOCAB:
    if _k not in OUTFITS:
        OUTFITS[_k] = _todo(_k)


# ===========================================================================
#  着せる
# ===========================================================================
def dress(rig, z: dict, stylebook: dict, items: Optional[Sequence] = None) -> Dict[str, dict]:
    """z["outfit"]（か items）を内側から順に着せる。stylebook に足した項目を返す。"""
    items = list(z.get("outfit", ()) if items is None else items)
    order = sorted(range(len(items)), key=lambda i: (DEPTH.get(items[i][0], 5.0), i))
    added: Dict[str, dict] = {}
    for i in order:
        key, over = items[i]
        ctx = OutfitCtx(z, key, stylebook, salt=f"/{i}")
        params = S.outfit_params((key, over))
        added.update(OUTFITS[key](rig, params, ctx))
    return added


def outfit_cubes(model, key: Optional[str] = None) -> int:
    """服・装備のキューブ数（key を渡すとその部品だけ）。"""
    return sum(1 for c in model.all_cubes()
               if getattr(c, "nr_kit", None) and (key is None or c.nr_kit == key))


# ===========================================================================
#  自己テスト
# ===========================================================================
_OUT = os.path.join(C.SCRATCH)
_STD_BUILD = dict(height_cm=176, heads=7.4, bulk=1.0, limb=1.0, hunch=10, arm_len=1.03)
_FEM_BUILD = dict(height_cm=166, heads=7.3, bulk=0.92, limb=0.9, hunch=6, arm_len=1.0, female=True)
_FEMALE_ITEMS = ("torn_dress", "pencil_skirt", "bridal_veil")
_HEAD_ITEMS = ("hair", "beard", "hard_hat", "police_cap", "riot_helmet", "helmet_military",
               "firefighter_helmet", "scooter_helmet", "baseball_cap", "skull_cap", "bridal_veil",
               "gas_mask", "surgical_mask", "glasses", "headphones")


def _std_z(key="standard", armored=()):
    return dict(key=key, skin="pale", tone=1,
                gore=dict(armored=list(armored), armor_strip={}, breakables={}))


def _demo_params(key: str) -> List[Tuple[str, dict]]:
    """確認画像に並べる引数の組（既定 + 目立つ変化）。"""
    out = [("", {})]
    extra = {
        "hair": [("long", dict(style="long", length=1.3)), ("mohawk", dict(style="mohawk", color=(210, 30, 90))),
                 ("bun", dict(style="bun")), ("messy", dict(style="messy"))],
        "beard": [("full", dict(style="full"))],
        "shirt": [("flannel torn3", dict(cut="flannel", pattern="check", color=(150, 40, 36), torn=3,
                                         tucked=False)),
                  ("rolled open3", dict(sleeves="rolled", open=3, tucked=False, bloody=3))],
        "t_shirt": [("tank", dict(cut="tank", color=(230, 60, 120))),
                    ("jersey 12", dict(cut="jersey", number="12", color=(180, 30, 40), color2=(240, 240, 240)))],
        "jeans": [("shorts torn", dict(cut="shorts", torn=2)), ("ripped", dict(ripped_knees=True, torn=3))],
        "slacks": [("short", dict(short=True))],
        "sneakers": [("high_top", dict(kind="high_top", color2=(200, 30, 30)))],
        "dress_shoes": [("heels", dict(kind="heels", color=(180, 20, 30))), ("clog", dict(kind="clog"))],
        "riot_helmet": [("up", dict(visor="up")), ("cracked", dict(visor="cracked"))],
        "helmet_military": [("plain on", dict(cover="plain", chinstrap="on", goggles=False))],
        "scooter_helmet": [("down cracked2", dict(visor="down", cracked=2, color=(200, 40, 40)))],
        "baseball_cap": [("backwards", dict(backwards=True, color=(30, 60, 140)))],
        "skull_cap": [("kitchen", dict(kind="kitchen", color=(230, 230, 230))), ("hairnet", dict(kind="hairnet"))],
        "gas_mask": [("1 shattered", dict(filters=1, lens="shattered"))],
        "surgical_mask": [("chin", dict(position="chin")), ("ear", dict(position="ear"))],
        "glasses": [("sun", dict(kind="sun")), ("thick cracked", dict(kind="thick", cracked=True)),
                    ("loupe", dict(kind="loupe"))],
        "headphones": [("neck", dict(worn="neck", color=(30, 30, 30))),
                       ("earbuds cord", dict(kind="earbuds", worn="neck", cord_dangling=True))],
        "bridal_veil": [("short torn", dict(length="short", torn=2, tiara=False))],
        "hoodie": [("up zip torn2", dict(hood="up", zip=True, torn=2, color=(130, 40, 50)))],
        "suit_jacket": [("closed miss_l", dict(open=False, missing_sleeve="l", pocket_square=True, torn=2))],
        "necktie": [("stripe tight", dict(pattern="stripe", loosened=False, color2=(200, 170, 90)))],
        "leather_jacket": [("studs patches", dict(studs=True, patches=3, torn=1)),
                           ("sleeveless", dict(sleeveless=True))],
        "rain_jacket": [("hood up", dict(hood="up", torn=2))],
        "police_uniform": [("guard", dict(style="guard", color=(70, 74, 82), radio=False))],
        "chef_coat": [("rolled", dict(rolled_sleeves=True, bloody=3))],
        "apron": [("butcher full", dict(kind="butcher_leather", length="full", color=(70, 40, 30), stains=3))],
        "hospital_gown": [("iv torn3", dict(iv_line=True, torn=3, bloody=2))],
        "scrubs": [("gown stetho", dict(gown=True, stethoscope=True, color=(40, 90, 80)))],
        "coveralls": [("rolled_top", dict(rolled_top=True, color=(60, 90, 60)))],
        "prison_jumpsuit": [("tied", dict(top_tied_waist=True))],
        "camo_fatigues": [("urban", dict(pattern="urban", color=(110, 112, 104), color2=(60, 62, 58)))],
        "riot_armor": [("armored", dict(_z=dict(armored=["head", "torso", "arm_r", "arm_l", "leg_r", "leg_l"],
                                               armor_strip={"arm_r": 3, "arm_l": 3, "leg_r": 3, "leg_l": 3,
                                                            "torso": 2})))],
        "torn_dress": [("evening knee", dict(style="evening", length="knee", color=(40, 30, 40), torn=3)),
                       ("sundress", dict(style="sundress", length="knee", color=(230, 200, 90)))],
        "life_vest": [("deflated", dict(deflated=True, wet=True))],
        "layered_rags": [("robe", dict(kind="robe", color=(20, 20, 24), color2=(230, 230, 230))),
                         ("wraps 3", dict(kind="wraps", layers=3, torn=3)),
                         ("loincloth", dict(kind="loincloth", layers=1))],
        "bomb_suit": [("armored cracked", dict(visor="cracked", _z=dict(armored=list(S.HIT_PARTS),
                                                                        armor_strip={"arm_r": 3})))],
        "work_pants": [("knee_pads", dict(knee_pads=True, cargo=False, color=(40, 40, 44), color2=(220, 220, 220)))],
        "pencil_skirt": [("torn", dict(torn=2, pantyhose=False))],
        "running_shorts": [("red", dict(color=(200, 30, 30), color2=(240, 240, 240)))],
        "boots": [("combat", dict(kind="combat", color=(20, 20, 20))), ("fire", dict(kind="fire", color=(20, 20, 20))),
                  ("waders", dict(kind="waders", color=(50, 60, 50)))],
        "gloves": [("rubber", dict(kind="rubber", color=(200, 120, 30))), ("fingerless", dict(kind="fingerless")),
                   ("satin", dict(kind="satin", color=(244, 240, 232)))],
        "wristwatch": [("fitness r", dict(kind="fitness", side="r", color=(30, 30, 30)))],
        "chain_shackles": [("straps ankles", dict(kind="leather_straps", ankles=True, broken=True,
                                                  color=(90, 70, 50)))],
        "bandage_wrap": [("hands head", dict(on=["hand_r", "hand_l", "head"]))],
        "tattoo": [("barbed", dict(on=["arm_r", "arm_l", "chest"], motif="barbed")),
                   ("koi script", dict(on=["forearm_r", "chest"], motif="koi"))],
        "backpack": [("rucksack", dict(kind="rucksack", color=(70, 80, 60), torn=2)),
                     ("delivery open", dict(kind="delivery_box", color=(30, 120, 60), lid_open=True))],
        "tool_belt": [("all tools", dict(tools=["hammer", "tape", "pliers", "knife"]))],
        "name_badge": [("clip", dict(style="clip")), ("dogtag", dict(style="dogtag"))],
        "flashlight": [("hand", dict(mount="hand"))],
        "riot_shield": [("cracked3", dict(cracked=3))],
        "held_tool": [(k, dict(kind=k)) for k in _TOOLS[1:]],
    }.get(key, [])
    return out + extra


_VIEW_MODE = {k: "head" for k in _HEAD_ITEMS}
_VIEW_MODE.update({k: "feet" for k in ("sneakers", "dress_shoes", "boots")})
_VIEW_MODE.update({k: "hands" for k in ("gloves", "wristwatch", "bandage_wrap", "chain_shackles",
                                        "riot_shield")})
_VIEW_MODE.update({"held_tool": "body_side", "riot_shield": "body_side"})
_VIEW_LABEL = {"flashlight hand": "hands"}
_VIEW_MODE.update({k: "upper" for k in ("bridal_veil", "necktie", "name_badge", "headphones",
                                        "gas_mask", "flashlight", "air_tank", "backpack", "tattoo",
                                        "life_vest", "military_vest", "hi_vis_vest")})


def _render_pair(model, tex, mode: str = "body"):
    """前（右寄り 22°）と後ろの 2 枚。mode = body / upper / head / feet / hands（部位に寄る）。
    ゴア用ボーン（既定の状態で隠れる物）は隠す。"""
    import nr_preview as NP
    from PIL import Image
    vis = R.visible_bones(model)
    hidden = [b.name for b in model.bones if b.name not in vis]
    rig = model.nr_rig
    W = R.bone_world(model)
    focus = {"head": ("head", 9.5, (0, 0.4, 0)), "upper": ("chest", 17.0, (0, -0.5, 0)),
             "feet": ("shin_r", 9.0, (1.4, -3.6, 0)), "hands": ("forearm_r", 13.0, (3.2, -2.0, 0))}
    shots = []
    size = (250, 250) if not mode.startswith("body") else (220, 380)
    yaws = (22.0, 202.0) if mode != "body_side" else (58.0, 238.0)
    for yaw in yaws:
        if mode in focus:
            seg_bone, span, d = focus[mode]
            sg = {"head": "head", "chest": "chest", "shin_r": "shin_r", "forearm_r": "forearm_r"}[seg_bone]
            cen = W[rig.segment(sg)["bone"]] @ np.array([*rig.segment(sg)["centre"], 1.0])
            cam = NP.Camera(yaw=yaw, pitch=8.0, target=[float(v) for v in cen[:3] + np.array(d)],
                            scale=size[1] / span)
            shots.append(NP.render(model, tex, camera=cam, size=size, hidden=hidden, bg=(40, 42, 48),
                                   ss=2))
        else:
            shots.append(NP.render(model, tex, view=(yaw, 6.0), size=size, hidden=hidden,
                                   bg=(40, 42, 48), ss=2))
    w = sum(im.size[0] for im in shots)
    im = Image.new("RGB", (w, max(i.size[1] for i in shots)), (40, 42, 48))
    x = 0
    for a in shots:
        im.paste(a.convert("RGB"), (x, 0))
        x += a.size[0]
    return im


def _dress_one(key: str, over: dict, z: dict, build: dict, seed: int = 7):
    m = R.new_model(f"kit_{key}")
    rig = R.ZombieRig(m, dict(build), detail=2, seed=seed)
    book = P.zombie_styles(R.GENERIC_TONE, 2, "clouded", blood=0.3)
    added = dress(rig, z, book, items=[(key, over)])
    return m, rig, book, added


def spec_build(z: dict) -> dict:
    """spec のゾンビの骨格欄 → ZombieRig の build。"""
    return dict(height_cm=z["height_cm"], heads=z["heads"], bulk=z["bulk"], limb=z["limb"],
                hunch=z["hunch"], arm_len=z["arm_len"], female=bool(z.get("female", False)))


_BUDGET = {"common": 450, "viral": 450, "special": 650, "night": 650, "boss": 1100}


def _dress_spec(z: dict, detail: int = 2):
    m = R.new_model(z["key"], max_atlas=(1024, 1024) if z.get("boss") else (512, 512))
    rig = R.ZombieRig(m, spec_build(z), detail=detail, seed=C.stable_hash(z["key"]))
    book = P.zombie_styles(z["skin"], int(z.get("decay", 2)), z.get("eyes", "clouded"), blood=0.35,
                           life_tone=z.get("tone"), blood_kind=z["gore"].get("blood", "red"))
    added = dress(rig, z, book)
    return m, rig, book, added


def _spec_check(render: bool, errs: List[str]) -> list:
    """spec の全 50 体に着せて、キューブ数・アトラス・ボーンの親の一貫性・gib を確かめる。
    3 体（会社員・消防士・機動隊）は前後の絵も返す。"""
    tiles = []
    rules = []
    rows = []
    for z in S.ZOMBIES:
        if not z["outfit"]:
            continue
        try:
            m, rig, book, added = _dress_spec(z)
            n_out = outfit_cubes(m)
            total = len(m.all_cubes())
            rules.append(R.visibility_rules(m))
            size = (1024, 1024) if z.get("boss") else (512, 512)
            m.pack(size=size)
            R.extract_gibs(m, z["key"])
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            errs.append(f"spec {z['key']}: {type(e).__name__}: {e}")
            continue
        cap = _BUDGET.get(z["cls"], 450)
        rows.append((z["key"], z["cls"], n_out, total, cap, len(added)))
        # 変異の分を残して、服は上限の残りの 6 割まで
        if total > cap:
            errs.append(f"spec {z['key']}: キューブ {total} > {cap}")
        if render and z["key"] in ("office_worker", "firefighter", "riot_police"):
            tex = P.paint_model(m, book, seed=5)
            tiles.append((f"spec {z['key']}  [{n_out} / {total}]", _render_pair(m, tex, "body")))
    try:
        R.merge_visibility(*rules)
    except ValueError as e:
        errs.append(f"spec merge_visibility: {e}")
    print("spec の着せ替え（服のキューブ / 全体 / 上限 / スタイル数）")
    for k, c, n, t, cap, ns in rows:
        print(f"  {k:20s} {c:8s} outfit={n:4d} total={t:4d}/{cap:4d} styles={ns}")
    return tiles


def _selftest(render: bool = True, only: Optional[Sequence[str]] = None) -> int:
    errs: List[str] = []
    missing = [k for k in S.OUTFIT_VOCAB if k not in OUTFITS]
    todo = [k for k, f in OUTFITS.items() if getattr(f, "_todo", False)]
    if missing:
        errs.append(f"未実装の鍵: {missing}")
    extra = [k for k in OUTFITS if k not in S.OUTFIT_VOCAB]
    if extra:
        errs.append(f"語彙に無い鍵: {extra}")
    rules_all = []
    tiles = []
    counts = {}
    keys = [k for k in S.OUTFIT_VOCAB if (not only or k in only)]
    t0 = time.time()
    for key in keys:
        for label, over in _demo_params(key):
            build = _FEM_BUILD if key in _FEMALE_ITEMS else _STD_BUILD
            over = dict(over)
            zo = over.pop("_z", {})
            z = _std_z(armored=zo.get("armored", ()))
            z["gore"]["armor_strip"] = dict(zo.get("armor_strip", {}))
            try:
                m, rig, book, added = _dress_one(key, over, z, build)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                errs.append(f"{key} {label}: {type(e).__name__}: {e}")
                continue
            n = outfit_cubes(m)
            counts[f"{key} {label}".strip()] = (n, len(added))
            try:
                rules_all.append(R.visibility_rules(m))
                m.pack(size=(512, 512))
                R.extract_gibs(m, f"kit_{key}")
            except Exception as e:  # noqa: BLE001
                errs.append(f"{key} {label}: {type(e).__name__}: {e}")
                continue
            if render:
                tex = P.paint_model(m, book, seed=11)
                tiles.append((f"{key} {label}".strip() + f"  [{n}]",
                              _render_pair(m, tex, _VIEW_LABEL.get(f"{key} {label}".strip(),
                                                                   _VIEW_MODE.get(key, "body")))))
    try:
        R.merge_visibility(*rules_all)
    except ValueError as e:
        errs.append(f"merge_visibility: {e}")
    if not only:
        tiles += _spec_check(render, errs)
        # 同じ入力から同じ物ができるか（乱数は stable_hash で seed、hash() は使わない）
        import json
        outs = []
        for _ in range(2):
            m, rig, book, added = _dress_spec(S.ZOMBIE_BY_KEY["office_worker"])
            m.pack(size=(512, 512))
            outs.append(json.dumps([m.to_json(), sorted(added)], sort_keys=True, default=str))
        if outs[0] != outs[1]:
            errs.append("同じ入力で結果が変わる（決定的でない）")
    print(f"確認 {len(counts)} 組 ({time.time() - t0:.1f}s)")
    for k, (n, ns) in counts.items():
        print(f"  {k:32s} cubes={n:4d} styles={ns}")
    if todo:
        print(f"まだ形の無い鍵 {len(todo)}: {', '.join(todo)}")
    if render and tiles:
        import nr_preview as NP
        os.makedirs(_OUT, exist_ok=True)
        per = 12
        for i in range(0, len(tiles), per):
            sheet = NP.contact_sheet(tiles[i:i + per], cols=3, title=f"nr_kit_outfit {i // per + 1}")
            path = os.path.join(_OUT, f"kit_outfit_{i // per + 1}.png")
            sheet.save(path)
            print("wrote", path)
    for e in errs:
        print("ERROR", e)
    return 1 if errs else 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    sys.exit(_selftest(render=not a.no_render, only=[k for k in a.only.split(",") if k] or None))
