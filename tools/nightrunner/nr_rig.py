# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — ゾンビ 50 体の共通骨格（DESIGN.md §3 / §5）。

ここが持つもの:

* `ZombieRig(model, build)` … §3 のボーン名・親子関係そのままの骨格と、キューブ単位で作り込んだ体
  （肋骨・胸筋・腹・背中・鎖骨・三角筋・肘・細くなる前腕・指 4 本＋親指と爪・太腿・膝・脹脛・踵とつま先、
  眉弓・頬骨・鼻・耳・顎のある頭蓋、歯と歯茎の見える関節付きの下顎、腱の浮いた首）。
* ゴア用ボーン（既定は隠す。ジオメトリは常にある）: 断面（皮膚の縁・脂肪・筋肉・骨と髄・垂れた腱と皮・
  滴る血）、顔の裂傷、割れた頭蓋と脳、首の断面（背骨・食道）、腹の切り傷、垂れた腸、胴の断面。
* パーティクル用ロケータ（`loc_neck` ほか）。mcmodel の Bone を継承して `locators` を書き出す。
* `visibility_rules()` … §3 のプロパティ表から part_visibility を生成（祖先の条件を全部 AND する）。
* `hitboxes()` … スクリプト用の部位の当たり箱（DESIGN §12 の `{c:[r,u,f], h:[hr,hu,hf]}`）。
* `extract_gibs(model, key)` … ちぎれた部位の gib ジオメトリ（同じ UV・同じテクスチャ・切り口の断面付き）。
* `build_generic_gibs()` … 汎用の肉片（腸・脳・肉・骨・目玉）。

座標の約束（統合版のジオメトリ空間。tools/hyperdim/reference/README.md と同じ規則）:

* 16 単位 = 1 ブロック、+Y が上、**顔は -Z（north 面）**、**体の右は -X**（バニラの rightArm は x=-5）。
* 回転 [rx, ry, rz] はモデル空間の右手系で R = Rz(-rz)·Ry(ry)·Rx(-rx)。正の rx で前へ傾く。
* ワールドへ: ヨー 0 のエンティティは +Z（南）を向き、ジオメトリの (x, y, z) はワールドの (x, y, -z)。
  つまり「ゾンビ自身の右 r = -x、上 u = y、前 f = -z」（当たり箱・ロケータの [r, u, f] はこれ）。

`nr_paint` との約束: 体のスタイル名は "skin" "skin_dark" "flesh" "cut_flesh" "bone" "teeth" "gums"
"guts" "brain" "blood" "blood_dry" "eye" "hair" "nail" だけを使う。顔は頭の顔板（face plate）の north 面に
"face" デカール。顎が別ボーンなので顔板は「生え際〜上唇」までで、目・鼻・口の位置を正規化座標
（eye_v / eye_dx / brow_v / nose_v / mouth_v、v は上端 0 → 下端 1、u は左端 0 → 右端 1）で渡す。

* 目は顔デカールが描く（3D の目玉キューブは体に置かない）。顔の裂傷（head_wound）の眼窩と、視神経で
  垂れた目玉は、顔デカールの左目の位置（eye_gap / eye_v）から計算して描いた目を覆うので、目が 2 つ
  重なって見えることはない。目の無い種類（eyes = none）は眼窩だけ。"eye" のスタイルは顔と同じ種類で塗る
  （zombie_styles(..., eyes=build["eyes"])。光る目なら垂れた目玉も光る）。
* 断面（手足・首・胴の切り口の円板）は cut_flesh に nr_paint の "section" デカールを面ごとに付ける:
  手足は骨 1 本、首は頸椎（背中側）・気管（前）、胴は腰椎（背中側）と腸の輪切り。ファイル座標の面の
  向き（up の v は -Z へ、down の v は +Z へ）で背中側を決める。gib の切り口は stump の矩形を上下入れ替えて
  借りるので、v を反転（負の uv_size）して前後を保つ。
* 体の血は少なめ（zombie_styles の既定）。血は傷・断面・口元に任せる（無傷の体が血のそばかすに見えない）。
* 自己検査（python3 tools/nightrunner/nr_rig.py）: ジオメトリは nr_common.write_geometry（1.16.0）で書き、
  確認画像は nr_preview（統合版と同じ面の対応）で描く。最後に build_preview/nightrunner/foundation_check.png
  （2 体 × 6 状態と gib）を作る。--foundation でそれだけ、--no-render で画像なし。
"""
from __future__ import annotations

import copy
import math
import os
import random
import sys
import zlib
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcmodel import Bone, Cube, Model  # noqa: E402
from rig import PX_PER_CM  # noqa: E402  180cm ≒ 32 単位（既存の rig.py と同じ物差し）

# ---------------------------------------------------------------------------
# §3 の骨格（名前と親。順番は親が先）
# ---------------------------------------------------------------------------


def _side_bones(s: str):
    return [
        (f"leg_{s}", "pelvis"), (f"shin_{s}", f"leg_{s}"), (f"foot_{s}", f"shin_{s}"),
        (f"stump_leg_{s}_lower", f"leg_{s}"), (f"stump_leg_{s}_upper", "pelvis"),
    ]


def _arm_bones(s: str):
    return [
        (f"arm_{s}", "chest"), (f"forearm_{s}", f"arm_{s}"), (f"hand_{s}", f"forearm_{s}"),
        (f"arm_{s}_wound", f"arm_{s}"), (f"stump_arm_{s}_lower", f"arm_{s}"),
        (f"stump_arm_{s}_upper", "chest"),
    ]


SKELETON: List[Tuple[str, Optional[str]]] = (
    [("root", None), ("waist", "root"), ("pelvis", "waist")]
    + _side_bones("r") + _side_bones("l")
    + [("torso", "waist"), ("torso_wound", "torso"), ("guts", "torso"),
       ("stump_torso", "torso"), ("chest", "torso"),
       ("neck", "chest"), ("head", "neck"), ("jaw", "head"), ("head_wound", "head"),
       ("skull_open", "head"), ("stump_neck", "neck")]
    + _arm_bones("r") + _arm_bones("l")
)
SKELETON_PARENT: Dict[str, Optional[str]] = dict(SKELETON)
BONE_NAMES: Tuple[str, ...] = tuple(n for n, _ in SKELETON)

# 既定で隠れているゴア用ボーン
GORE_BONES = frozenset(
    ["torso_wound", "guts", "stump_torso", "head_wound", "skull_open", "stump_neck"]
    + [f"stump_leg_{s}_{w}" for s in "rl" for w in ("lower", "upper")]
    + [f"stump_arm_{s}_{w}" for s in "rl" for w in ("lower", "upper")]
    + [f"arm_{s}_wound" for s in "rl"]
)

# 体のスタイル名（nr_paint.zombie_styles が返すキー）
BODY_STYLES = ("skin", "skin_dark", "flesh", "cut_flesh", "bone", "teeth", "gums", "guts",
               "brain", "blood", "blood_dry", "eye", "hair", "nail")

# ---------------------------------------------------------------------------
# エンティティプロパティ（§3 の表）と part_visibility の規則
# ---------------------------------------------------------------------------

LIMB_STATES = ("intact", "wounded", "broken", "cut_lower", "cut_upper")
PROPERTIES: Dict[str, dict] = {
    "nr:head": dict(type="enum", values=("intact", "wounded", "jawless", "cracked", "severed",
                                         "crushed"), default="intact"),
    "nr:arm_r": dict(type="enum", values=LIMB_STATES, default="intact"),
    "nr:arm_l": dict(type="enum", values=LIMB_STATES, default="intact"),
    "nr:leg_r": dict(type="enum", values=LIMB_STATES, default="intact"),
    "nr:leg_l": dict(type="enum", values=LIMB_STATES, default="intact"),
    "nr:torso": dict(type="enum", values=("intact", "slashed", "gutted", "halved"),
                     default="intact"),
    "nr:blood": dict(type="int", range=(0, 3), default=0),
    "nr:burn": dict(type="int", range=(0, 3), default=0),
    "nr:shock": dict(type="int", range=(0, 1), default=0),
    "nr:armor": dict(type="int", range=(0, 3), default=3),
    "nr:state": dict(type="enum", values=("normal", "crawl", "climb", "stagger", "down",
                                          "special", "dead"), default="normal"),
    "nr:pose": dict(type="int", range=(0, 7), default=0),
    "nr:ability": dict(type="int", range=(0, 7), default=0),
    "nr:variant": dict(type="int", range=(0, 3), default=0),
}


def _only(prop, *vals):
    return (prop, frozenset(vals))


def _except(prop, *vals):
    return (prop, frozenset(v for v in PROPERTIES[prop]["values"] if v not in vals))


# ボーン自身の表示条件（祖先の条件は visibility_rules が足す）。値は「表示してよい値の集合」。
OWN_RULES: Dict[str, List[Tuple[str, frozenset]]] = {
    "pelvis": [_except("nr:torso", "halved")],
    "torso_wound": [_only("nr:torso", "slashed", "gutted", "halved")],
    "guts": [_only("nr:torso", "gutted", "halved")],
    "stump_torso": [_only("nr:torso", "halved")],
    "head": [_except("nr:head", "severed", "crushed")],
    "jaw": [_except("nr:head", "jawless")],
    "head_wound": [_only("nr:head", "wounded", "jawless", "cracked")],
    "skull_open": [_only("nr:head", "cracked")],
    "stump_neck": [_only("nr:head", "severed", "crushed")],
}
for _s in "rl":
    OWN_RULES[f"arm_{_s}"] = [_except(f"nr:arm_{_s}", "cut_upper")]
    OWN_RULES[f"forearm_{_s}"] = [_except(f"nr:arm_{_s}", "cut_lower", "cut_upper")]
    OWN_RULES[f"arm_{_s}_wound"] = [_only(f"nr:arm_{_s}", "wounded", "broken")]
    OWN_RULES[f"stump_arm_{_s}_lower"] = [_only(f"nr:arm_{_s}", "cut_lower")]
    OWN_RULES[f"stump_arm_{_s}_upper"] = [_only(f"nr:arm_{_s}", "cut_upper")]
    OWN_RULES[f"leg_{_s}"] = [_except(f"nr:leg_{_s}", "cut_upper")]
    OWN_RULES[f"shin_{_s}"] = [_except(f"nr:leg_{_s}", "cut_lower", "cut_upper")]
    OWN_RULES[f"stump_leg_{_s}_lower"] = [_only(f"nr:leg_{_s}", "cut_lower")]
    OWN_RULES[f"stump_leg_{_s}_upper"] = [_only(f"nr:leg_{_s}", "cut_upper")]

# ロケータ: 名前 -> 付くボーン（その部位が落ちても残る側に付ける）
LOCATOR_BONES = {
    "loc_neck": "neck", "loc_head": "head", "loc_mouth": "head", "loc_chest": "chest",
    "loc_waist": "torso", "loc_belly": "torso",
    "loc_shoulder_r": "chest", "loc_shoulder_l": "chest",
    "loc_elbow_r": "arm_r", "loc_elbow_l": "arm_l",
    "loc_hand_r": "hand_r", "loc_hand_l": "hand_l",
    "loc_hip_r": "pelvis", "loc_hip_l": "pelvis",
    "loc_knee_r": "leg_r", "loc_knee_l": "leg_l",
}
REQUIRED_LOCATORS = ("loc_neck", "loc_shoulder_r", "loc_shoulder_l", "loc_elbow_r",
                     "loc_elbow_l", "loc_hip_r", "loc_hip_l", "loc_knee_r", "loc_knee_l",
                     "loc_waist", "loc_head", "loc_mouth", "loc_chest")

# gib（§5）: nr:part の番号 -> ボーン名
GIB_PARTS = ("p_head", "p_jaw", "p_arm_r", "p_arm_l", "p_forearm_r", "p_forearm_l",
             "p_leg_r", "p_leg_l", "p_shin_r", "p_shin_l", "p_lower",
             "p_guts", "p_brain", "p_chunk", "p_bone", "p_eye")
GIB_PART_INDEX = {n: i for i, n in enumerate(GIB_PARTS)}
GIB_TYPE_PARTS = GIB_PARTS[:11]          # 種類ごとの geometry.nr.gib.<key>
GIB_GENERIC_PARTS = GIB_PARTS[11:]       # geometry.nr.gib.generic
GIB_GENERIC_ZTYPE = 63

# part -> (切り離す部分木の根, 除くボーン, 断面を借りる stump ボーン)
GIB_SOURCES = {
    "p_head": ("head", ("head_wound", "skull_open"), "stump_neck"),
    "p_jaw": ("jaw", (), "stump_neck"),
    "p_arm_r": ("arm_r", ("arm_r_wound", "stump_arm_r_lower"), "stump_arm_r_upper"),
    "p_arm_l": ("arm_l", ("arm_l_wound", "stump_arm_l_lower"), "stump_arm_l_upper"),
    "p_forearm_r": ("forearm_r", (), "stump_arm_r_lower"),
    "p_forearm_l": ("forearm_l", (), "stump_arm_l_lower"),
    "p_leg_r": ("leg_r", ("stump_leg_r_lower",), "stump_leg_r_upper"),
    "p_leg_l": ("leg_l", ("stump_leg_l_lower",), "stump_leg_l_upper"),
    "p_shin_r": ("shin_r", (), "stump_leg_r_lower"),
    "p_shin_l": ("shin_l", (), "stump_leg_l_lower"),
    "p_lower": ("pelvis", ("stump_leg_r_upper", "stump_leg_l_upper",
                           "stump_leg_r_lower", "stump_leg_l_lower"), "stump_torso"),
}

# UV の密度（1 単位あたりの texel）。基準の体（176cm・bulk 1.0）での値で、実際は体の大きさで
# 割り戻す（大きい体ほど 1 単位あたりの texel を減らし、アトラスに占める割合をほぼ一定にする）。
# 基準の体で裸の体＋ゴア ≒ アトラス 512×512 の 30%（残りを服・装備に回す）。
UV_BODY = 4.6
UV_HAND = 5.0
UV_HEAD = 7.0
UV_FACE = 12.0
UV_GORE = 3.6
UV_CAP = 8.0            # 断面（首・胴・手足の切り口）は輪切りの絵が読めるよう細かく
UV_FINE = 6.0            # 爪などの細かい部品
REF_T = 176 * PX_PER_CM  # 基準の身長（単位）
CAP_DEPTH = 0.30         # 断面の円板が切り口から外へ出る厚み（側面に裂けた肉の輪が見える）
ARM_ABDUCT = 5.0         # 腕の休みの外転（度）
# 手足の断面ボーンの休みの回転: 切り口（下向き）を前へ 14° 向け、正面の目の高さから見える
# ようにする（負の rx で下面が前を向く）。切り株の箱は逆に回して元の位置に残す
STUMP_TILT = (-14.0, 0, 0)



def section_decal(faces=("down",), **params) -> Dict[str, dict]:
    """断面デカール（nr_paint の "section"）を面ごとに置く辞書。nr_paint.section_decal と同じ形
    （nr_rig を nr_paint 無しでも読めるように、ここにも同じものを置く）。"""
    return {f: dict(params, name="section") for f in faces}


# ---------------------------------------------------------------------------
# 回転の数学（hd_space.py と同じ規則。依存を増やさないためここに置く）
# ---------------------------------------------------------------------------


def _Rx(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _Ry(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _Rz(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot(rx, ry, rz) -> np.ndarray:
    """統合版の rotation [rx, ry, rz] をモデル空間の回転行列に（R = Rz(-rz)·Ry(ry)·Rx(-rx)）。"""
    return _Rz(-rz) @ _Ry(ry) @ _Rx(-rx)


def euler(M) -> Tuple[float, float, float]:
    """rot() の逆（M = Rz(-c)·Ry(b)·Rx(-a) を (a, b, c) に）。"""
    cb = math.hypot(M[2, 1], M[2, 2])
    b = math.degrees(math.atan2(-M[2, 0], cb))
    if cb > 1e-6:
        a = -math.degrees(math.atan2(M[2, 1], M[2, 2]))
        c = -math.degrees(math.atan2(M[1, 0], M[0, 0]))
    else:
        a = -math.degrees(math.atan2(-M[1, 2], M[1, 1]))
        c = 0.0
    return (round(a, 3) + 0.0, round(b, 3) + 0.0, round(c, 3) + 0.0)


def _mat4(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def _bone_local(pivot, rotation):
    p = np.asarray(pivot, float)
    if not rotation or not any(rotation):
        return np.eye(4)
    return _mat4(t=p) @ _mat4(rot(*rotation)) @ _mat4(t=-p)


def bone_world(model: Model) -> Dict[str, np.ndarray]:
    """各ボーンの（休みの姿勢での）ワールド行列。ジオメトリの rotation だけを使う。"""
    by = {b.name: b for b in model.bones}
    out: Dict[str, np.ndarray] = {}

    def w(name):
        if name in out:
            return out[name]
        b = by[name]
        L = _bone_local(b.pivot, b.rotation)
        M = (w(b.parent) @ L) if b.parent and b.parent in by else L
        out[name] = M
        return M

    for b in model.bones:
        w(b.name)
    return out


def cube_matrix(cube: Cube) -> np.ndarray:
    """キューブ自身の回転（ボーン内）。"""
    if not cube.rotation or not any(cube.rotation):
        return np.eye(4)
    piv = cube.pivot or [cube.origin[i] + cube.size[i] / 2 for i in range(3)]
    return _bone_local(piv, cube.rotation)


def cube_corners(cube: Cube) -> np.ndarray:
    o = np.array(cube.origin, float) - cube.inflate
    s = np.array(cube.size, float) + 2 * cube.inflate
    pts = np.array([[o[0] + s[0] * i, o[1] + s[1] * j, o[2] + s[2] * k, 1.0]
                    for i in (0, 1) for j in (0, 1) for k in (0, 1)])
    return pts


def geo_to_ruf(p) -> List[float]:
    """ジオメトリの点（単位）→ ゾンビ自身の [右 r, 上 u, 前 f]（ブロック）。"""
    return [round(-p[0] / 16.0, 4) + 0.0, round(p[1] / 16.0, 4) + 0.0,
            round(-p[2] / 16.0, 4) + 0.0]


# ---------------------------------------------------------------------------
# mcmodel の拡張: ロケータを書き出すボーンとモデル
# ---------------------------------------------------------------------------


class NRBone(Bone):
    """mcmodel.Bone ＋ locators（1.12.0 形式: {"名前": [x, y, z]}、モデル空間の座標）。"""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.locators: Dict[str, List[float]] = {}

    def to_json(self) -> dict:
        out = super().to_json()
        if self.locators:
            out["locators"] = {k: [round(float(v), 3) + 0.0 for v in p]
                               for k, p in self.locators.items()}
        return out


class NRModel(Model):
    """ボーンを NRBone で作る Model。`pack(size=(512, 512))` で寸法を固定できる。"""

    def bone(self, name: str, pivot=(0, 0, 0), parent=None, rotation=None,
             binding=None) -> Bone:
        b = NRBone(name, pivot, parent, rotation, binding=binding)
        self.bones.append(b)
        return b

    def pack(self, padding: int = 1, size: Optional[Tuple[int, int]] = None) -> None:
        if size is None:
            return super().pack(padding)
        for cube in self.all_cubes():
            if cube.uv_scale is None:
                cube._scale = self.uv_scale
                if not cube.fixed:
                    cube.uv = None
        if not self._try_pack(size[0], size[1], padding):
            raise ValueError(f"{self.identifier}: does not fit in {size} "
                             f"({len(self.all_cubes())} cubes)")
        self.tex_w, self.tex_h = size


def new_model(key: str, kind: str = "z", uv_scale: int = 4,
              max_atlas: Tuple[int, int] = (512, 512),
              visible_bounds: Tuple[float, float] = (3.5, 3.5),
              vb_offset: Tuple[float, float, float] = (0, 1.25, 0)) -> NRModel:
    """`geometry.nr.<kind>.<key>` の空のモデル（ゾンビは kind="z"）。"""
    return NRModel(f"geometry.nr.{kind}.{key}", uv_scale=uv_scale, visible_bounds=visible_bounds,
                   vb_offset=vb_offset, max_atlas=max_atlas)


# ---------------------------------------------------------------------------
# 寸法（landmarks）
# ---------------------------------------------------------------------------


def landmarks(build: dict) -> SimpleNamespace:
    """身長・等身・体格から関節の位置と各部の太さを出す（単位はモデル単位）。

    比率は成人の人体計測の平均（身長に対する割合）を基にし、Minecraft のキューブで読めるよう
    少しだけ誇張している。bulk は胴の幅・厚み（と少し手足）を、limb は手足の太さを、
    arm_len は腕の長さを、scale は全体の大きさを掛ける。"""
    t = float(build["height_cm"]) * PX_PER_CM * float(build.get("scale", 1.0))
    heads = float(build.get("heads", 7.5))
    bulk = float(build.get("bulk", 1.0))
    limb = float(build.get("limb", 1.0))
    arm_len = float(build.get("arm_len", 1.0))
    fem = bool(build.get("female", False))
    H = t / heads
    chin = t - H
    shoulder_y = chin - 0.040 * t
    crotch = 0.470 * t
    hip_y = 0.520 * t
    knee_y = 0.285 * t
    ankle_y = 0.045 * t
    torso_len = shoulder_y - crotch
    abdomen_bot = crotch + 0.33 * torso_len          # 腸骨稜（骨盤の上端）
    chest_bot = crotch + 0.655 * torso_len           # 肋骨の下端
    lt = limb * bulk ** 0.4
    chest_w = 0.170 * t * bulk ** 0.6 * (0.90 if fem else 1.0)
    chest_d = 0.118 * t * bulk ** 0.85 * (0.94 if fem else 1.0)
    waist_w = 0.150 * t * bulk ** 0.75 * (0.84 if fem else 1.0)
    waist_d = 0.105 * t * bulk ** 0.95
    hip_w = 0.185 * t * bulk ** 0.5 * (1.08 if fem else 1.0)
    pelvis_d = 0.112 * t * bulk ** 0.6 * (1.05 if fem else 1.0)
    arm_t = 0.055 * t * lt * (0.88 if fem else 1.0)
    fore_t = 0.050 * t * lt * (0.88 if fem else 1.0)
    thigh_t = 0.088 * t * lt * (1.02 if fem else 1.0)
    knee_t = 0.060 * t * lt
    calf_t = 0.066 * t * lt
    ankle_t = 0.040 * t * limb ** 0.5
    elbow_y = shoulder_y - 0.186 * t * arm_len
    wrist_y = elbow_y - 0.146 * t * arm_len
    hand_l = 0.108 * t * arm_len ** 0.5
    head_w = 0.72 * H
    head_d = 0.86 * H
    neck_w = 0.068 * t * bulk ** 0.45 * (0.86 if fem else 1.0)
    neck_d = 0.072 * t * bulk ** 0.35 * (0.90 if fem else 1.0)
    stance = max(hip_w / 2 - thigh_t * 0.5, thigh_t * 0.5 + 0.004 * t)
    arm_x = chest_w / 2 + arm_t * 0.40
    return SimpleNamespace(
        t=t, H=H, heads=heads, bulk=bulk, limb=limb, female=fem,
        total=t, chin=chin, shoulder_y=shoulder_y, chest_top=shoulder_y, chest_bot=chest_bot,
        abdomen_bot=abdomen_bot, crotch=crotch, hip_y=hip_y, knee_y=knee_y, ankle_y=ankle_y,
        elbow_y=elbow_y, wrist_y=wrist_y,
        chest_w=chest_w, chest_d=chest_d, waist_w=waist_w, waist_d=waist_d, hip_w=hip_w,
        pelvis_d=pelvis_d, arm_t=arm_t, fore_t=fore_t, wrist_t=0.64 * fore_t,
        thigh_t=thigh_t, knee_t=knee_t, calf_t=calf_t, ankle_t=ankle_t,
        hand_l=hand_l, palm_l=0.56 * hand_l, finger_l=0.46 * hand_l,
        hand_w=0.050 * t * lt ** 0.5, hand_th=0.018 * t * lt ** 0.5,
        foot_l=0.152 * t, foot_w=0.058 * t * limb ** 0.4,
        head_w=head_w, head_d=head_d, neck_w=neck_w, neck_d=neck_d, neck_z=0.004 * t,
        stance=stance, arm_x=arm_x, knee_x=stance - 0.010 * t,
        shoulder_w=2 * (arm_x + arm_t * 0.62),
    )


# ---------------------------------------------------------------------------
# 骨格
# ---------------------------------------------------------------------------


class ZombieRig:
    """§3 の骨格と体・ゴアのキューブ。

    build = dict(height_cm, heads, bulk, limb, hunch, arm_len, female=False, scale=1.0)
    （spec の骨格欄）。任意で decay / eyes / mouth / gore（顔デカール）、nose（False で鼻を削ぐ）、
    detail（2 = 全部、1 = 指を板にし爪と一部の血を省く）、seed。

    使い方:
        model = new_model("office_worker")
        rig = ZombieRig(model, spec_build)
        rig.b("chest").add(Cube(...))          # 服は付く部位のボーンへ
        rig.L.chest_w, rig.segment("upper_arm_r")  # 寸法・部位の箱
        model.pack(size=(512, 512))
        rules = visibility_rules(model); hit = rig.hitboxes(); gib = extract_gibs(model, key)
    """

    def __init__(self, model: Model, build: dict, face: Optional[dict] = None,
                 detail: Optional[int] = None, seed: Optional[int] = None):
        self.model = model
        self.build = dict(build)
        self.L = landmarks(self.build)
        self.detail = int(detail if detail is not None else self.build.get("detail", 2))
        if seed is None:
            seed = self.build.get("seed")
        if seed is None:
            seed = zlib.crc32(repr(sorted((k, str(v)) for k, v in self.build.items()))
                              .encode("utf-8"))
        self.rng = random.Random(seed)
        self.hunch = float(self.build.get("hunch", 0.0))
        self.face = dict(face or {})
        # texel 密度: 体が大きいほど下げる（texel 数を体格に依らずほぼ一定に）。texel で全体を倍率
        L_ = self.L
        tex = float(self.build.get("texel", 1.0))
        k = min(1.25, max(0.5, (REF_T / L_.t) / L_.bulk ** 0.45)) * tex
        kh = min(1.3, max(0.55, (REF_T / 7.4) / L_.H)) * tex
        r2 = lambda v: round(v, 2)  # noqa: E731
        self.U = {"body": r2(UV_BODY * k), "hand": r2(UV_HAND * k), "gore": r2(UV_GORE * k),
                  "cap": r2(UV_CAP * k), "fine": r2(UV_FINE * k), "head": r2(UV_HEAD * kh),
                  "face": r2(UV_FACE * kh)}
        self.bones: Dict[str, Bone] = {}
        self.locators: Dict[str, Tuple[str, Tuple[float, float, float]]] = {}
        self.cuts: Dict[str, dict] = {}          # gib の切り口の定義
        self.segments: Dict[str, dict] = {}      # 服を巻くための部位の箱
        model.nr_rig = self                      # extract_gibs が切り口の定義を見つけるため
        self._skeleton()
        self._torso()
        self._neck_head()
        for s in "rl":
            self._arm(s)
            self._hand(s)
            self._leg(s)
        self._gore()
        self._place_locators()
        self._measure_segments()

    # ------------------------------------------------------------------ 基本
    def b(self, name: str) -> Bone:
        """ボーン（服・装備の部品はこれの .add(Cube) か、これを親に子ボーンを足す）。"""
        return self.bones[name]

    def segment(self, name: str) -> dict:
        """部位の箱 {lo, hi, bone, centre, size}（bind 空間・単位）。服を巻く寸法に使う。

        名前: head, face, cranium, jaw, neck, chest, abdomen, pelvis, upper_arm_r/l, forearm_r/l,
        hand_r/l, thigh_r/l, shin_r/l, foot_r/l。"""
        return self.segments[name]

    def _bone(self, name, pivot, rotation=None) -> Bone:
        parent = SKELETON_PARENT[name]
        bone = NRBone(name, pivot, parent, rotation)
        self.model.bones.append(bone)
        self.bones[name] = bone
        return bone

    def box(self, bone: str, x0, y0, z0, x1, y1, z1, style: str, uv: Optional[float] = None,
            rot3=None, pivot=None, decals=None, role: Optional[str] = None,
            seg: Optional[str] = None, inflate: float = 0.0) -> Cube:
        """2 隅の座標で箱を足す（順不同）。role は gore の部品の役割、seg は部位の箱の集計先。"""
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        za, zb = sorted((z0, z1))
        size = (max(0.02, xb - xa), max(0.02, yb - ya), max(0.02, zb - za))
        c = Cube((xa, ya, za), size, style, uv_scale=uv or self.U["body"], inflate=inflate,
                 rotation=list(rot3) if rot3 and any(rot3) else None,
                 pivot=[round(float(v), 3) for v in pivot] if (pivot is not None and rot3
                                                               and any(rot3)) else None,
                 decals=decals)
        c.nr_role = role
        c.nr_seg = seg
        self.bones[bone].add(c)
        return c

    def beam(self, bone: str, p0, p1, w: float, d: float, style: str, uv: Optional[float] = None,
             role: Optional[str] = None, seg: Optional[str] = None, over: float = 0.0) -> Cube:
        """p0 → p1 の線分に沿った角柱（断面 w × d、局所 +Y が線分）。腱・指・腸・血の筋に使う。

        回転を小さく保つため、下向きの線分は端を入れ替えて上向きに作る。over は両端の延長。"""
        p0 = np.asarray(p0, float)
        p1 = np.asarray(p1, float)
        if p1[1] < p0[1]:
            p0, p1 = p1, p0
        v = p1 - p0
        L = float(np.linalg.norm(v)) or 1e-3
        d_ = v / L
        p0 = p0 - d_ * over
        L += 2 * over
        rx = -math.degrees(math.asin(max(-1.0, min(1.0, d_[2]))))
        rz = math.degrees(math.atan2(d_[0], d_[1]))
        rx, rz = round(rx, 2), round(rz, 2)
        c = Cube((p0[0] - w / 2, p0[1], p0[2] - d / 2), (w, L, d), style,
                 uv_scale=uv or self.U["body"],
                 rotation=[rx, 0, rz] if (abs(rx) > 0.01 or abs(rz) > 0.01) else None,
                 pivot=[round(float(p0[0]), 3), round(float(p0[1]), 3), round(float(p0[2]), 3)])
        c.nr_role = role
        c.nr_seg = seg
        self.bones[bone].add(c)
        return c

    # ------------------------------------------------------------------ 骨格
    def _skeleton(self) -> None:
        L = self.L
        h = self.hunch
        r = lambda v: (round(v, 2), 0, 0) if abs(v) > 0.01 else None  # noqa: E731
        self._bone("root", (0, 0, 0))
        self._bone("waist", (0, L.hip_y, 0))
        self._bone("pelvis", (0, L.hip_y, 0))
        for s, sgn in (("r", -1), ("l", 1)):
            lx = sgn * L.stance
            self._bone(f"leg_{s}", (lx, L.hip_y, 0))
            kx = sgn * L.knee_x
            self._bone(f"shin_{s}", (kx, L.knee_y, 0))
            self._bone(f"foot_{s}", (kx, L.ankle_y, 0))
            self._bone(f"stump_leg_{s}_lower", (kx, L.knee_y - 0.02 * L.t, 0), STUMP_TILT)
            self._bone(f"stump_leg_{s}_upper",
                       (lx + sgn * 0.06 * L.thigh_t, L.hip_y - 0.05 * L.t, -0.01 * L.thigh_t),
                       STUMP_TILT)
        # 猫背: 腹 45%・胸 55% で前へ倒し、首と頭で顔を前へ戻す
        self._bone("torso", (0, L.abdomen_bot, 0), r(h * 0.45))
        mid = (L.abdomen_bot + L.chest_bot) / 2
        self._bone("torso_wound", (0, mid, -L.waist_d / 2))
        self._bone("guts", (0, L.abdomen_bot + 0.3 * (L.chest_bot - L.abdomen_bot),
                            -L.waist_d / 2))
        self._bone("stump_torso", (0, L.abdomen_bot, 0))
        self._bone("chest", (0, L.chest_bot, 0), r(h * 0.55))
        self._bone("neck", (0, L.shoulder_y + 0.005 * L.t, L.neck_z), r(-h * 0.35))
        head_piv = (0, L.chin + 0.20 * L.H, L.neck_z)
        self._bone("head", head_piv, r(-h * 0.55))
        self._bone("jaw", (0, L.chin + 0.40 * L.H, -0.02 * L.head_d))
        self._bone("head_wound", (0, L.chin + 0.40 * L.H, -0.30 * L.head_d))
        self._bone("skull_open", (0, L.chin + 0.95 * L.H, 0))
        self._bone("stump_neck", (0, L.chin + 0.25 * L.H, L.neck_z))
        for s, sgn in (("r", -1), ("l", 1)):
            ax = sgn * L.arm_x
            # 腕は猫背の 80% を打ち消して、ほぼ真下（少し前）に垂らし、5° だけ外へ開く
            # （手が腰の横に来る）。正の rz で右腕が外へ開く（hd_space の規則）
            ab = -sgn * ARM_ABDUCT
            self._bone(f"arm_{s}", (ax, L.shoulder_y - 0.45 * L.arm_t, 0),
                       (round(-h * 0.8, 2), 0, ab))
            self._bone(f"forearm_{s}", (ax, L.elbow_y, 0))
            self._bone(f"hand_{s}", (ax, L.wrist_y, 0))
            self._bone(f"arm_{s}_wound", (ax, (L.shoulder_y + L.elbow_y) / 2, 0))
            self._bone(f"stump_arm_{s}_lower", (ax, L.elbow_y - 0.22 * L.arm_t, 0.03 * L.arm_t),
                       STUMP_TILT)
            self._bone(f"stump_arm_{s}_upper",
                       (ax + sgn * 0.04 * L.arm_t, L.shoulder_y - 1.6 * L.arm_t, 0), STUMP_TILT)
        # §3 の順に並べ直す（親が先）
        order = {n: i for i, n in enumerate(BONE_NAMES)}
        rig_bones = [b for b in self.model.bones if b.name in order]
        others = [b for b in self.model.bones if b.name not in order]
        rig_bones.sort(key=lambda b: order[b.name])
        self.model.bones[:] = others + rig_bones

    # ------------------------------------------------------------------ 胴
    def _torso(self) -> None:
        L = self.L
        t = L.t
        ct, cb, ab, cr = L.chest_top, L.chest_bot, L.abdomen_bot, L.crotch
        ch = ct - cb
        cw, cd = L.chest_w, L.chest_d
        bulk = L.bulk
        # --- 胸（胸郭・胸筋・背中・広背筋・僧帽筋・鎖骨）
        self.box("chest", -cw / 2, cb + 0.36 * ch, -cd / 2, cw / 2, ct - 0.004 * t, cd / 2,
                 "skin", seg="chest")
        self.box("chest", -0.45 * cw, cb, -0.47 * cd, 0.45 * cw, cb + 0.40 * ch, 0.47 * cd,
                 "skin", seg="chest")
        if L.female:
            for sgn in (-1, 1):
                self.box("chest", sgn * 0.05 * cw, ct - 0.66 * ch, -cd / 2 - 0.022 * t,
                         sgn * 0.46 * cw, ct - 0.20 * ch, -cd / 2 + 0.3, "skin", seg="chest")
                self.box("chest", sgn * 0.11 * cw, ct - 0.63 * ch, -cd / 2 - 0.034 * t,
                         sgn * 0.40 * cw, ct - 0.30 * ch, -cd / 2 - 0.018 * t, "skin",
                         seg="chest")
        else:
            pe = 0.010 * t * bulk ** 0.5
            for sgn in (-1, 1):
                self.box("chest", sgn * 0.025 * cw, ct - 0.56 * ch, -cd / 2 - pe,
                         sgn * 0.48 * cw, ct - 0.10 * ch, -cd / 2 + 0.3, "skin", seg="chest")
        # 背中（菱形筋・僧帽筋の下部）と広背筋の張り出し
        self.box("chest", -0.46 * cw, cb + 0.24 * ch, cd / 2 - 0.3, 0.46 * cw, ct - 0.05 * ch,
                 cd / 2 + 0.009 * t, "skin", seg="chest")
        for sgn in (-1, 1):
            self.box("chest", sgn * 0.40 * cw, cb + 0.30 * ch, -0.30 * cd,
                     sgn * (0.5 * cw + 0.008 * t * bulk), ct - 0.14 * ch, 0.44 * cd, "skin",
                     seg="chest")
        # 僧帽筋: 首の付け根から肩先へ下る斜面（外側が下がる回転）
        for sgn in (-1, 1):
            x0 = sgn * 0.12 * cw
            self.box("chest", x0, ct - 0.022 * t, -0.18 * cd, sgn * (0.5 * cw + 0.05 * L.arm_t),
                     ct + 0.020 * t, 0.42 * cd, "skin", rot3=(0, 0, sgn * 21),
                     pivot=(x0, ct + 0.02 * t, 0), seg="chest")
        # 鎖骨（外側が少し上がる）
        for sgn in (-1, 1):
            x0 = sgn * 0.05 * cw
            self.box("chest", x0, ct - 0.014 * t, -cd / 2 - 0.006 * t, sgn * 0.50 * cw,
                     ct - 0.003 * t, -cd / 2 + 0.25, "skin", rot3=(0, 0, -sgn * 6),
                     pivot=(x0, ct - 0.01 * t, -cd / 2), seg="chest")
        # --- 腹（腹直筋・腹斜筋・脊柱起立筋）
        ww, wd = L.waist_w, L.waist_d
        belly = 0.006 * t + max(0.0, bulk - 1.0) * 0.030 * t
        self.box("torso", -ww / 2, ab, -wd / 2, ww / 2, cb + 0.012 * t, wd / 2, "skin",
                 seg="abdomen")
        self.box("torso", -0.30 * ww, ab + 0.06 * (cb - ab), -wd / 2 - belly, 0.30 * ww,
                 cb - 0.01 * t, -wd / 2 + 0.3, "skin", seg="abdomen")
        self.box("torso", -0.53 * ww, ab - 0.006 * t, -0.40 * wd, 0.53 * ww,
                 ab + 0.42 * (cb - ab), 0.38 * wd, "skin", seg="abdomen")
        self.box("torso", -0.30 * ww, ab, wd / 2 - 0.3, 0.30 * ww, cb + 0.01 * t,
                 wd / 2 + 0.008 * t, "skin", seg="abdomen")
        # --- 骨盤（骨盤・尻・股）
        hw, pd = L.hip_w, L.pelvis_d
        self.box("pelvis", -hw / 2, cr + 0.015 * t, -pd / 2, hw / 2, ab + 0.004 * t, pd / 2,
                 "skin", seg="pelvis")
        gl = 0.020 * t * bulk ** 0.5 + (0.010 * t if L.female else 0.0)
        for sgn in (-1, 1):
            self.box("pelvis", sgn * 0.02 * hw, cr - 0.022 * t, pd / 2 - 0.45, sgn * 0.48 * hw,
                     L.hip_y + 0.035 * t, pd / 2 + gl, "skin", seg="pelvis")
        self.box("pelvis", -0.20 * hw, cr - 0.018 * t, -0.40 * pd, 0.20 * hw, cr + 0.04 * t,
                 0.25 * pd, "skin_dark", seg="pelvis")

    # ------------------------------------------------------------------ 首と頭
    def _neck_head(self) -> None:
        L = self.L
        t, H, w, d, c = L.t, L.H, L.head_w, L.head_d, L.chin
        ct = L.chest_top
        nw, nd, nz = L.neck_w, L.neck_d, L.neck_z
        # --- 首: 円柱・胸鎖乳突筋（耳の後ろ → 胸骨）・うなじ・喉仏
        self.box("neck", -nw / 2, ct - 0.02 * t, nz - nd / 2, nw / 2, c + 0.25 * H, nz + nd / 2,
                 "skin", seg="neck")
        for sgn in (-1, 1):
            self.beam("neck", (sgn * 0.40 * nw, c + 0.22 * H, nz + 0.22 * nd),
                      (sgn * 0.10 * nw, ct - 0.006 * t, nz - 0.54 * nd), 0.20 * nw, 0.16 * nd,
                      "skin", seg="neck")
        self.box("neck", -0.42 * nw, ct - 0.012 * t, nz + 0.10 * nd, 0.42 * nw, ct + 0.035 * t,
                 nz + 0.60 * nd, "skin", seg="neck")
        if not L.female:
            self.box("neck", -0.09 * nw, c - 0.024 * t, nz - nd / 2 - 0.005 * t, 0.09 * nw,
                     c - 0.004 * t, nz - nd / 2 + 0.1, "skin", uv=self.U["fine"], seg="neck")
        # --- 頭蓋（頭頂・後頭部）
        self.box("head", -0.50 * w, c + 0.40 * H, -0.44 * d, 0.50 * w, c + 0.93 * H, 0.50 * d,
                 "skin", uv=self.U["head"], seg="cranium")
        self.box("head", -0.42 * w, c + 0.93 * H, -0.36 * d, 0.42 * w, c + 1.00 * H, 0.42 * d,
                 "skin", uv=self.U["head"], seg="cranium")
        self.box("head", -0.40 * w, c + 0.30 * H, 0.40 * d, 0.40 * w, c + 0.78 * H, 0.56 * d,
                 "skin", uv=self.U["head"], seg="cranium")
        # --- 顔板（生え際〜上唇）。north 面に "face" デカール
        top, bot = c + 0.86 * H, c + 0.205 * H
        fh = top - bot

        def v_of(y):
            return round((top - y) / fh, 3)

        nose = bool(self.build.get("nose", True))
        face = {
            "name": "face",
            "region": "upper",          # 下顎は別ボーン。顔板は生え際〜上唇（下端が口の線）
            "eyes": self.build.get("eyes", "clouded"),
            "mouth": self.build.get("mouth", "snarl"),
            "decay": self.build.get("decay", 2),
            "gore": self.build.get("gore_face", 0.4),
            "nose": nose,
            # 顔の部品の正規化座標（v は上端 0 → 下端 1。目は u = 0.5 ± eye_gap）。3D の眉弓・頬骨・
            # 鼻のキューブはこの位置に合わせて置いてある
            "eye_v": v_of(c + 0.52 * H),
            "eye_gap": 0.25,
            "brow_v": v_of(c + 0.615 * H),
            "nose_v": v_of(c + 0.36 * H),
            "mouth_v": v_of(c + 0.225 * H),
        }
        face.update(self.face)
        self.face_decal = face
        # 下顎の正面（顎先）: 同じ顔の "jaw" 領域（下唇の影・顎先の陰影・口から垂れる血）
        jaw_face = {k: face[k] for k in ("eyes", "mouth", "decay", "gore") if k in face}
        jaw_face.update({"name": "face", "region": "jaw", "mouth_v": -0.03})
        self.jaw_decal = jaw_face
        plate = self.box("head", -0.40 * w, bot, -0.50 * d, 0.40 * w, top, -0.18 * d, "skin",
                         uv=self.U["face"], decals={"north": face}, seg="face")
        # 顔板の寸法（目の位置を 3D の部品 = 顔の裂傷の眼窩と目玉 に合わせるため）
        self.face_plate = dict(x0=-0.40 * w, x1=0.40 * w, bot=bot, top=top, z=-0.50 * d,
                               scale=float(plate.uv_scale or self.U["face"]))
        # 頬骨・咬筋・眉弓
        for sgn in (-1, 1):
            self.box("head", sgn * 0.30 * w, c + 0.385 * H, -0.53 * d, sgn * 0.47 * w,
                     c + 0.48 * H, -0.22 * d, "skin", uv=self.U["head"], seg="face")
            self.box("head", sgn * 0.38 * w, c + 0.21 * H, -0.40 * d, sgn * 0.485 * w,
                     c + 0.42 * H, 0.06 * d, "skin", uv=self.U["head"], seg="face")
        self.box("head", -0.37 * w, c + 0.585 * H, -0.535 * d, 0.37 * w, c + 0.64 * H, -0.30 * d,
                 "skin", uv=self.U["head"], seg="face")
        # 鼻（腐って削げた種類は nose=False。nr_paint が鼻の穴の空洞を描く）
        if nose:
            self.box("head", -0.055 * w, c + 0.40 * H, -0.555 * d, 0.055 * w, c + 0.585 * H,
                     -0.40 * d, "skin", uv=self.U["face"], seg="face")
            self.box("head", -0.085 * w, c + 0.33 * H, -0.60 * d, 0.085 * w, c + 0.43 * H,
                     -0.42 * d, "skin", uv=self.U["face"], seg="face")
            self.box("head", -0.13 * w, c + 0.325 * H, -0.545 * d, 0.13 * w, c + 0.385 * H,
                     -0.42 * d, "skin", uv=self.U["face"], seg="face")
        # 耳（耳介＋耳たぶ）
        for sgn in (-1, 1):
            self.box("head", sgn * 0.50 * w, c + 0.34 * H, -0.02 * d, sgn * 0.575 * w,
                     c + 0.64 * H, 0.20 * d, "skin_dark", uv=self.U["head"], seg="cranium")
        # 上の歯・歯茎・口の中（顎が開くと見える）
        self.box("head", -0.26 * w, c + 0.165 * H, -0.485 * d, 0.26 * w, c + 0.215 * H,
                 -0.30 * d, "teeth", uv=self.U["face"])
        self.box("head", -0.27 * w, c + 0.195 * H, -0.47 * d, 0.27 * w, c + 0.24 * H,
                 -0.28 * d, "gums", uv=self.U["head"])
        self.box("head", -0.25 * w, c + 0.10 * H, -0.42 * d, 0.25 * w, c + 0.20 * H, 0.02 * d,
                 "gums", uv=self.U["head"])
        # --- 下顎: 顎先・下唇・下顎体・下顎枝・下の歯・歯茎・舌
        self.box("jaw", -0.25 * w, c - 0.01 * H, -0.51 * d, 0.25 * w, c + 0.155 * H, -0.28 * d,
                 "skin", uv=self.U["face"], decals={"north": jaw_face}, seg="jaw")
        self.box("jaw", -0.20 * w, c + 0.15 * H, -0.525 * d, 0.20 * w, c + 0.205 * H,
                 -0.40 * d, "skin_dark", uv=self.U["face"], seg="jaw")
        self.box("jaw", -0.40 * w, c + 0.02 * H, -0.44 * d, 0.40 * w, c + 0.19 * H, 0.00 * d,
                 "skin", uv=self.U["head"], seg="jaw")
        for sgn in (-1, 1):
            self.box("jaw", sgn * 0.36 * w, c + 0.03 * H, -0.06 * d, sgn * 0.45 * w,
                     c + 0.38 * H, 0.14 * d, "skin", uv=self.U["head"], seg="jaw")
        self.box("jaw", -0.235 * w, c + 0.165 * H, -0.47 * d, 0.235 * w, c + 0.21 * H,
                 -0.32 * d, "teeth", uv=self.U["face"])
        self.box("jaw", -0.245 * w, c + 0.14 * H, -0.46 * d, 0.245 * w, c + 0.175 * H,
                 -0.30 * d, "gums", uv=self.U["head"])
        self.box("jaw", -0.16 * w, c + 0.14 * H, -0.40 * d, 0.16 * w, c + 0.18 * H, -0.06 * d,
                 "gums", uv=self.U["head"])

    # ------------------------------------------------------------------ 腕
    def _arm(self, s: str) -> None:
        L = self.L
        sgn = -1 if s == "r" else 1
        ax, at = sgn * L.arm_x, L.arm_t
        sy, ey, wy = L.shoulder_y, L.elbow_y, L.wrist_y
        ul = sy - ey
        arm, fore = f"arm_{s}", f"forearm_{s}"
        seg_u, seg_f = f"upper_arm_{s}", f"forearm_{s}"
        # 三角筋（肩の丸み）・上腕・力こぶ・三頭筋・肘・肘頭
        dx = ax + sgn * 0.05 * at
        self.box(arm, dx - 0.60 * at, sy - 1.30 * at, -0.60 * at, dx + 0.60 * at,
                 sy - 0.20 * at, 0.56 * at, "skin", seg=seg_u)
        self.box(arm, dx - 0.47 * at, sy - 0.30 * at, -0.46 * at, dx + 0.43 * at,
                 sy + 0.06 * at, 0.44 * at, "skin", seg=seg_u)
        self.box(arm, ax - 0.46 * at, ey + 0.10 * at, -0.46 * at, ax + 0.46 * at,
                 sy - 0.70 * at, 0.46 * at, "skin", seg=seg_u)
        self.box(arm, ax - 0.36 * at, ey + 0.45 * at, -0.58 * at, ax + 0.36 * at,
                 ey + 0.58 * ul, -0.05 * at, "skin", seg=seg_u)
        self.box(arm, ax - 0.40 * at, ey + 0.55 * at, 0.05 * at, ax + 0.40 * at,
                 sy - 0.95 * at, 0.57 * at, "skin", seg=seg_u)
        self.box(arm, ax - 0.40 * at, ey - 0.22 * at, -0.38 * at, ax + 0.40 * at,
                 ey + 0.30 * at, 0.44 * at, "skin", seg=seg_u)
        self.box(arm, ax - 0.20 * at, ey - 0.18 * at, 0.30 * at, ax + 0.20 * at, ey + 0.22 * at,
                 0.56 * at, "skin_dark", seg=seg_u)
        # 前腕: 肘側は太く、手首へ細くなる（手首は前後 = Z に広い）
        ft = L.fore_t
        fl = ey - wy
        self.box(fore, ax - 0.48 * ft, ey - 0.50 * fl, -0.50 * ft, ax + 0.48 * ft,
                 ey + 0.04 * fl, 0.48 * ft, "skin", seg=seg_f)
        bx = ax + sgn * 0.06 * ft
        self.box(fore, bx - 0.36 * ft, ey - 0.40 * fl, -0.62 * ft, bx + 0.36 * ft,
                 ey + 0.02 * fl, -0.05 * ft, "skin", seg=seg_f)
        self.box(fore, ax - 0.33 * ft, wy + 0.02 * fl, -0.44 * ft, ax + 0.33 * ft,
                 ey - 0.46 * fl, 0.44 * ft, "skin", seg=seg_f)
        self.box(fore, ax - 0.31 * ft, wy - 0.006 * L.t, -0.42 * ft, ax + 0.31 * ft,
                 wy + 0.05 * fl, 0.42 * ft, "skin_dark", seg=seg_f)

    # ------------------------------------------------------------------ 手
    def _hand(self, s: str) -> None:
        """手のひらは体側（右手は +X）、親指は前（-Z）、指は下。指は手のひら側へ少し曲がる。"""
        L = self.L
        sgn = -1 if s == "r" else 1
        inward = -sgn
        ax, wy = sgn * L.arm_x, L.wrist_y
        hand = f"hand_{s}"
        seg = f"hand_{s}"
        pl, hw, ht = L.palm_l, L.hand_w, L.hand_th
        # 手の甲・手のひら
        self.box(hand, ax - ht / 2, wy - pl, -0.48 * hw, ax + ht / 2, wy + 0.004 * L.t,
                 0.48 * hw, "skin", uv=self.U["hand"], seg=seg)
        knuckle_y = wy - pl + 0.05
        fz = (-0.36, -0.12, 0.12, 0.36)
        flen = (0.92, 1.0, 0.95, 0.76)
        fw = 0.21 * hw
        fth = 0.78 * ht
        curl1, curl2 = 10.0 + self.rng.uniform(-3, 3), 26.0 + self.rng.uniform(-4, 6)
        if self.detail <= 1:
            # 指を一枚の板（曲げた 2 節）に
            p0 = np.array([ax, knuckle_y, 0.0])
            a1 = math.radians(curl1)
            L1 = L.finger_l * 0.55
            p1 = p0 + L1 * np.array([inward * math.sin(a1), -math.cos(a1), 0])
            a2 = math.radians(curl1 + curl2)
            p2 = p1 + L.finger_l * 0.42 * np.array([inward * math.sin(a2), -math.cos(a2), 0])
            self.beam(hand, p0, p1, fth, 0.88 * hw, "skin", uv=self.U["hand"], seg=seg, over=0.03)
            self.beam(hand, p1, p2, fth * 0.9, 0.84 * hw, "skin", uv=self.U["hand"], seg=seg,
                      over=0.03)
        else:
            for zf, lf in zip(fz, flen):
                FL = L.finger_l * lf
                p0 = np.array([ax, knuckle_y, zf * hw])
                a1 = math.radians(curl1 + self.rng.uniform(-3, 3))
                d1 = np.array([inward * math.sin(a1), -math.cos(a1), 0])
                p1 = p0 + FL * 0.55 * d1
                a2 = math.radians(curl1 + curl2 + self.rng.uniform(-5, 5))
                d2 = np.array([inward * math.sin(a2), -math.cos(a2), 0])
                p2 = p1 + FL * 0.45 * d2
                self.beam(hand, p0, p1, fth, fw, "skin", uv=self.U["hand"], seg=seg, over=0.02)
                self.beam(hand, p1, p2, fth * 0.92, fw * 0.94, "skin", uv=self.U["hand"], seg=seg,
                          over=0.02)
                # 爪: 末節の甲側。指先から少しはみ出す（爪を伸ばす変異の土台）
                n = np.array([-inward * math.cos(a2), -math.sin(a2), 0])
                off = n * (fth * 0.92 / 2 + 0.02)
                self.beam(hand, p2 - d2 * FL * 0.22 + off, p2 + d2 * 0.06 + off, 0.05,
                          fw * 0.80, "nail", uv=self.U["fine"], role="nail", seg=seg)
        # 親指（母指球から前下・内へ 2 節）
        b0 = np.array([ax + inward * 0.20 * ht, wy - 0.28 * pl, -0.40 * hw])
        d = np.array([inward * 0.32, -0.80, -0.50])
        d /= np.linalg.norm(d)
        TL = L.finger_l * 0.82
        b1 = b0 + TL * 0.55 * d
        d2 = np.array([inward * 0.55, -0.78, -0.30])
        d2 /= np.linalg.norm(d2)
        b2 = b1 + TL * 0.45 * d2
        tw = 0.25 * hw
        self.beam(hand, b0, b1, ht * 0.95, tw, "skin", uv=self.U["hand"], seg=seg, over=0.03)
        self.beam(hand, b1, b2, ht * 0.85, tw * 0.92, "skin", uv=self.U["hand"], seg=seg, over=0.02)
        if self.detail >= 2:
            n0 = np.array([-inward * 0.45, 0.0, -0.9])
            n0 = n0 - d2 * float(np.dot(n0, d2))
            n0 /= np.linalg.norm(n0)
            off = n0 * (ht * 0.85 / 2 + 0.02)
            self.beam(hand, b2 - d2 * TL * 0.2 + off, b2 + d2 * 0.05 + off, 0.05, tw * 0.78,
                      "nail", uv=self.U["fine"], role="nail", seg=seg)

    # ------------------------------------------------------------------ 脚
    def _leg(self, s: str) -> None:
        L = self.L
        t = L.t
        sgn = -1 if s == "r" else 1
        inward = -sgn
        lx = sgn * L.stance
        kx = sgn * L.knee_x                     # 膝から下の中心（股関節より少し内）
        hy, ky, ay = L.hip_y, L.knee_y, L.ankle_y
        tl = hy - ky
        tt, kt = L.thigh_t, L.knee_t
        leg, shin, foot = f"leg_{s}", f"shin_{s}", f"foot_{s}"
        seg_t, seg_s, seg_f = f"thigh_{s}", f"shin_{s}", f"foot_{s}"
        # 太腿: 上は太く外へ、膝の上で細く。大腿四頭筋・内側広筋（涙滴）・ハムストリング・膝
        ux = lx + sgn * 0.06 * tt
        self.box(leg, ux - 0.5 * tt, ky + 0.48 * tl, -0.5 * tt, ux + 0.5 * tt, hy + 0.025 * t,
                 0.48 * tt, "skin", seg=seg_t)
        k2 = kt * 1.1
        self.box(leg, kx - 0.52 * k2, ky + 0.03 * t, -0.5 * k2, kx + 0.52 * k2, ky + 0.55 * tl,
                 0.5 * k2, "skin", seg=seg_t)
        mx = (lx + kx) / 2
        self.box(leg, mx - 0.40 * tt, ky + 0.04 * t, -0.5 * tt - 0.008 * t, mx + 0.40 * tt,
                 ky + 0.80 * tl, -0.10 * tt, "skin", seg=seg_t)
        vx = kx + inward * 0.28 * kt
        self.box(leg, vx - 0.26 * kt, ky + 0.022 * t, -0.56 * kt, vx + 0.26 * kt,
                 ky + 0.30 * tl, 0.05 * kt, "skin", seg=seg_t)
        self.box(leg, mx - 0.40 * tt, ky + 0.06 * t, 0.05 * tt, mx + 0.40 * tt, hy - 0.02 * t,
                 0.5 * tt + 0.006 * t, "skin", seg=seg_t)
        self.box(leg, kx - 0.48 * kt, ky - 0.020 * t, -0.46 * kt, kx + 0.48 * kt, ky + 0.035 * t,
                 0.46 * kt, "skin", seg=seg_t)
        # 脛: 膝蓋骨・上・脹脛（腓腹筋）・中・下（アキレス腱）・くるぶし
        sl = ky - ay
        cf, ak = L.calf_t, L.ankle_t
        self.box(shin, kx - 0.26 * kt, ky - 0.016 * t, -0.5 * kt - 0.010 * t, kx + 0.26 * kt,
                 ky + 0.022 * t, -0.25 * kt, "skin_dark", seg=seg_s)
        self.box(shin, kx - 0.44 * cf, ky - 0.42 * sl, -0.44 * cf, kx + 0.44 * cf,
                 ky - 0.010 * t, 0.40 * cf, "skin", seg=seg_s)
        self.box(shin, kx - 0.46 * cf, ky - 0.50 * sl, 0.0, kx + 0.46 * cf, ky - 0.10 * sl,
                 0.5 * cf + 0.010 * t, "skin", seg=seg_s)
        self.box(shin, kx - 0.36 * cf, ky - 0.72 * sl, -0.38 * cf, kx + 0.36 * cf,
                 ky - 0.38 * sl, 0.40 * cf, "skin", seg=seg_s)
        self.box(shin, kx - 0.5 * ak, ay + 0.012 * t, -0.5 * ak, kx + 0.5 * ak, ky - 0.68 * sl,
                 0.5 * ak + 0.006 * t, "skin", seg=seg_s)
        self.box(shin, kx - 0.5 * ak - 0.005 * t, ay - 0.006 * t, -0.28 * ak,
                 kx + 0.5 * ak + 0.005 * t, ay + 0.020 * t, 0.28 * ak, "skin_dark", seg=seg_s)
        # 足: 踵・甲・母指球・親指・残りの指・親指の爪
        fl, fw = L.foot_l, L.foot_w
        self.box(foot, kx - 0.020 * t, 0, 0.04 * fl, kx + 0.020 * t, 0.040 * t, 0.24 * fl,
                 "skin", seg=seg_f)
        self.box(foot, kx - 0.024 * t, 0, -0.38 * fl, kx + 0.024 * t, ay + 0.006 * t,
                 0.10 * fl, "skin", seg=seg_f)
        self.box(foot, kx - 0.5 * fw, 0, -0.62 * fl, kx + 0.5 * fw, 0.027 * t, -0.30 * fl,
                 "skin", seg=seg_f)
        bx = kx + inward * 0.30 * fw
        self.box(foot, bx - 0.18 * fw, 0, -0.77 * fl, bx + 0.18 * fw, 0.020 * t, -0.58 * fl,
                 "skin", seg=seg_f)
        sx = kx - inward * 0.17 * fw
        self.box(foot, sx - 0.31 * fw, 0, -0.71 * fl, sx + 0.31 * fw, 0.015 * t, -0.58 * fl,
                 "skin", seg=seg_f)
        if self.detail >= 2:
            self.box(foot, bx - 0.12 * fw, 0.019 * t, -0.77 * fl, bx + 0.12 * fw, 0.0215 * t,
                     -0.70 * fl, "nail", uv=self.U["fine"], role="nail", seg=seg_f)

    # ------------------------------------------------------------------ ゴア
    def _gore(self) -> None:
        L = self.L
        t = L.t
        # 肘・膝・肩・股関節の断面
        for s, sgn in (("r", -1), ("l", 1)):
            ax, at = sgn * L.arm_x, L.arm_t
            ey, sy = L.elbow_y, L.shoulder_y
            # 肘: 上腕の下端（肘の箱の下）
            self._limb_stump(f"stump_arm_{s}_lower", (ax, ey - 0.22 * at, 0.03 * at),
                             0.40 * at, 0.41 * at, sgn, part=f"forearm_{s}")
            # 肩: 三角筋の切り株（上腕の上 30%）＋断面
            dx = ax + sgn * 0.04 * at
            stub = self.box(f"stump_arm_{s}_upper", dx - 0.58 * at, sy - 1.6 * at, -0.58 * at,
                            dx + 0.58 * at, sy + 0.10 * at, 0.55 * at, "skin",
                            uv=self.U["gore"], role="stub", rot3=(-STUMP_TILT[0], 0, 0),
                            pivot=(dx, sy - 1.6 * at, 0))
            self._limb_stump(f"stump_arm_{s}_upper", (dx, sy - 1.6 * at, 0), 0.52 * at,
                             0.52 * at, sgn, part=f"arm_{s}", stub=stub, chunk=True)
            # 膝: 太腿の下端
            lx, kt = sgn * L.stance, L.knee_t
            self._limb_stump(f"stump_leg_{s}_lower", (sgn * L.knee_x, L.knee_y - 0.02 * t, 0),
                             0.47 * kt,
                             0.45 * kt, sgn, part=f"shin_{s}")
            # 股関節: 太腿の付け根の切り株
            tt = L.thigh_t
            ux = lx + sgn * 0.06 * tt
            y_cut = L.hip_y - 0.05 * t
            stub = self.box(f"stump_leg_{s}_upper", ux - 0.5 * tt, y_cut, -0.5 * tt,
                            ux + 0.5 * tt, L.hip_y + 0.025 * t, 0.48 * tt, "skin",
                            uv=self.U["gore"], role="stub", rot3=(-STUMP_TILT[0], 0, 0),
                            pivot=(ux, y_cut, -0.01 * tt))
            self._limb_stump(f"stump_leg_{s}_upper", (ux, y_cut, -0.01 * tt), 0.48 * tt,
                             0.47 * tt, sgn, part=f"leg_{s}", stub=stub, chunk=True)
            self._arm_wound(s)
        self._neck_stump()
        self._head_wound()
        self._skull_open()
        self._torso_wound()
        self._guts()
        self._torso_stump()

    def _limb_stump(self, bone: str, centre, rx: float, rz: float, sgn: int, part: str,
                    stub: Optional[Cube] = None, chunk: bool = False) -> None:
        """下向きの断面: 断面の円板（cut_flesh。下面に皮膚の縁・脂肪・筋肉・骨と髄の断面が
        描かれる）・突き出た骨・めくれた皮・垂れた腱・滴る血（・筋肉の塊）。centre は切り口の中心。"""
        rng = self.rng
        cx, cy, cz = centre
        out = sgn                                   # 体の外側の向き（x）
        full = self.detail >= 2
        U = self.U
        # 断面の円板（下へ少し出す。下面が見える面）
        th = CAP_DEPTH
        br = min(rx, rz) * 0.30
        # 下面（見える切り口）に皮膚の縁・脂肪・筋肉・骨の輪切り（nr_paint の section デカール）
        sec = section_decal(("down",), kind="limb", bone_at=(0.5, 0.5), bone_r=round(br / (min(rx, rz) * 1.01), 3))
        self.box(bone, cx - rx * 1.01, cy - th, cz - rz * 1.01, cx + rx * 1.01, cy + 0.12,
                 cz + rz * 1.01, "cut_flesh", uv=U["cap"], role="cap", decals=sec)
        # 骨（上腕骨・大腿骨）: 断面に描かれた骨の位置（中心）から突き出す
        bl = 0.22 + min(rx, rz) * 0.50
        self.box(bone, cx - br, cy - th - bl, cz - br, cx + br, cy - 0.02, cz + br, "bone",
                 uv=U["gore"], role="bone")
        # めくれた皮（外側）
        flen = 0.35 + min(rx, rz) * 0.5
        self.beam(bone, (cx + out * rx * 0.92, cy + 0.02, cz - rz * 0.1),
                  (cx + out * (rx * 1.18), cy - flen, cz - rz * 0.2), 0.07, rz * 0.9, "skin",
                  uv=U["gore"], role="flap")
        if chunk and full:
            # 筋肉の塊（断面から垂れる）
            self.box(bone, cx - out * rx * 0.75, cy - th - 0.16, cz - rz * 0.2,
                     cx - out * rx * 0.2, cy - th + 0.05, cz + rz * 0.55, "flesh",
                     uv=U["gore"], role="chunk")
        # 腱（細く長い筋）
        tl_ = 0.6 + rng.uniform(0.2, 0.6) + min(rx, rz) * 0.4
        if full:
            self.beam(bone, (cx - out * rx * 0.35, cy - th + 0.02, cz + rz * 0.35),
                      (cx - out * rx * 0.45 + rng.uniform(-0.1, 0.1), cy - th - tl_,
                       cz + rz * 0.5),
                      0.11, 0.11, "flesh", uv=U["gore"], role="tendon")
        # 滴る血
        dl = 0.45 + rng.uniform(0.1, 0.5)
        self.box(bone, cx + out * rx * 0.3 - 0.06, cy - th - dl, cz - rz * 0.45 - 0.06,
                 cx + out * rx * 0.3 + 0.06, cy - th + 0.02, cz - rz * 0.45 + 0.06, "blood",
                 uv=U["gore"], role="drip")
        self.cuts[bone] = dict(part=part, centre=(cx, cy, cz), rx=rx, rz=rz, facing=-1,
                               stub=stub)

    def _neck_stump(self) -> None:
        """首の断面（上向き）: 断面・頸椎・気管と食道・めくれた皮・首を伝う血・血だまり。"""
        L = self.L
        t, H, c = L.t, L.H, L.chin
        nw, nd, nz = L.neck_w, L.neck_d, L.neck_z
        y = c + 0.25 * H
        b = "stump_neck"
        U = self.U
        rx, rz = nw / 2, nd / 2
        top = y + CAP_DEPTH * 0.8
        # 上面（見える切り口）: up 面の v は -Z へ増える（v=0 が背中側）。頸椎は後ろ、気管は前
        z0, z1 = nz - rz * 1.01, nz + rz * 1.01

        def v_up(z):
            return round((z1 - z) / (z1 - z0), 3)

        sec = section_decal(("up",), kind="neck", bone_at=(0.5, v_up(nz + 0.26 * nd)),
                            trachea_at=(0.5, v_up(nz - 0.33 * nd)),
                            bone_r=round(0.15 * nw / (min(rx, rz) * 1.01), 3))
        self.box(b, -rx * 1.01, y - 0.12, z0, rx * 1.01, top, z1,
                 "cut_flesh", uv=U["cap"], role="cap", decals=sec)
        # 頸椎（後ろ寄りに突き出す）
        self.box(b, -0.16 * nw, y - 0.05, nz + 0.12 * nd, 0.16 * nw, top + 0.36, nz + 0.40 * nd,
                 "bone", uv=U["gore"], role="bone")
        # 気管（前。軟骨の輪＝歯茎色の管）
        self.box(b, -0.15 * nw, y - 0.05, nz - 0.46 * nd, 0.15 * nw, top + 0.18, nz - 0.20 * nd,
                 "gums", uv=U["gore"], role="chunk")
        # めくれた皮（左右へ）
        for sgn in ((-1, 1) if self.detail >= 2 else (-1,)):
            self.beam(b, (sgn * rx * 0.92, y + 0.06, nz - rz * 0.1),
                      (sgn * rx * 1.25, y + 0.32, nz - rz * 0.25), 0.07, rz * 1.1, "skin",
                      uv=U["gore"], role="flap")
        # 首を伝って胸へ流れる血（前と横）
        for k, (xx, ln) in enumerate(((-0.25 * nw, 0.10 * t), (0.47 * nw, 0.06 * t))):
            if k == 1 and self.detail < 2:
                break
            zf = nz - rz - 0.03 if k == 0 else nz - rz * 0.3
            xo = xx if k == 0 else nw / 2 + 0.03
            self.box(b, xo - 0.07, y - ln, zf - 0.06, xo + 0.07, y + 0.02, zf + 0.06, "blood",
                     uv=U["gore"], role="drip")
        # 血だまり（断面の前の縁に溜まった薄い膜。断面の絵＝筋肉・気管を隠さない小ささ）
        self.box(b, -rx * 0.55, top, nz - rz * 0.98, rx * 0.1, top + 0.04, nz - rz * 0.62,
                 "blood", uv=U["gore"], role="pool")
        self.cuts[b] = dict(part="head", centre=(0, y, nz), rx=rx, rz=rz, facing=1, stub=None)

    def _head_wound(self) -> None:
        """顔の裂傷: 右頬が裂けて奥歯が覗く・めくれた頬の皮・左目が飛び出して垂れる・
        上顎から垂れた肉（顎が無い時に見える）・血の筋。"""
        L = self.L
        H, w, d, c = L.H, L.head_w, L.head_d, L.chin
        b = "head_wound"
        U = self.U
        # 右頬（-X）の裂け目と覗く奥歯
        self.box(b, -0.44 * w, c + 0.22 * H, -0.535 * d, -0.16 * w, c + 0.40 * H, -0.40 * d,
                 "cut_flesh", uv=U["face"], role="cap")
        self.box(b, -0.38 * w, c + 0.24 * H, -0.555 * d, -0.22 * w, c + 0.30 * H, -0.45 * d,
                 "teeth", uv=U["face"], role="teeth")
        self.beam(b, (-0.42 * w, c + 0.24 * H, -0.545 * d), (-0.47 * w, c + 0.06 * H, -0.58 * d),
                  0.09 * w, 0.04 * d, "cut_flesh", uv=U["head"], role="flap")
        # 空っぽの左の眼窩と、視神経でぶら下がる目玉。位置は顔デカールの左目（u = 0.5 + eye_gap、
        # v = eye_v）から計算するので、顔の部品の位置を変えても「描いた目」と「眼窩」がずれて
        # 目が 2 つ見えることはない。眼窩は描いた目（＋瞼）より一回り大きく、顔板から少し浮かせる。
        # 目の無い種類（eyes = none）は眼窩だけ（ぶら下がる目玉は無い）
        fd, fp = self.face_decal, self.face_plate
        pw, ph = fp["x1"] - fp["x0"], fp["top"] - fp["bot"]
        gap = float(fd.get("eye_gap", fd.get("eye_dx", 0.25)))
        ex = fp["x0"] + (0.5 + gap) * pw
        ey = fp["top"] - float(fd.get("eye_v", 0.52)) * ph
        sc = fp["scale"]
        glow = str(fd.get("eyes", "clouded")).startswith("glowing")
        ehw = max(1.6, pw * sc * (0.064 if glow else 0.075)) / sc      # nr_paint の目の半幅（単位）
        ehh = max(0.7, ph * sc * 0.03) / sc
        sx_, sy_ = max(0.09 * w, ehw * 1.45 + 1.0 / sc), max(0.045 * H, ehh * 2.6 + 1.0 / sc)
        self.box(b, ex - sx_, ey - sy_, fp["z"] - 0.012 * d, ex + sx_, ey + sy_, fp["z"] + 0.05 * d,
                 "blood_dry", uv=U["face"], role="socket")
        if fd.get("eyes", "clouded") != "none":
            eb = 0.065 * w
            eyc = np.array([ex + 0.02 * w, ey - 0.17 * H, -0.60 * d])
            self.beam(b, (ex, ey - 0.02 * H, fp["z"] - 0.02 * d), eyc + np.array([0, eb, 0]),
                      0.03 * w, 0.03 * w, "flesh", uv=U["head"], role="nerve")
            self.box(b, eyc[0] - eb, eyc[1] - eb, eyc[2] - eb, eyc[0] + eb, eyc[1] + eb,
                     eyc[2] + eb, "eye", uv=U["face"], role="eyeball")
        # 上顎から垂れた肉（顎があると下顎の中に隠れる）
        strips = ((-0.15 * w, 0.17), (0.17 * w, 0.15)) if self.detail >= 2 else ((0.0, 0.15),)
        for xx, ln in strips:
            self.beam(b, (xx, c + 0.20 * H, -0.42 * d), (xx * 1.1, c + (0.20 - ln) * H, -0.43 * d),
                      0.08 * w, 0.06 * d, "cut_flesh", uv=U["head"], role="strip")
        # 血の筋（裂け目から顎へ）
        self.box(b, -0.33 * w, c - 0.04 * H, -0.545 * d, -0.29 * w, c + 0.23 * H, -0.52 * d,
                 "blood", uv=U["head"], role="drip")

    def _skull_open(self) -> None:
        """割れた頭蓋: 頭頂から盛り上がる脳（左右の半球と回）・外へ開いた骨の破片・額を伝う血。"""
        L = self.L
        H, w, d, c = L.H, L.head_w, L.head_d, L.chin
        b = "skull_open"
        U = self.U
        for sgn in (-1, 1):
            self.box(b, sgn * 0.02 * w, c + 0.86 * H, -0.30 * d, sgn * 0.38 * w, c + 1.07 * H,
                     0.38 * d, "brain", uv=U["head"], role="brain")
        self.box(b, -0.24 * w, c + 1.05 * H, -0.14 * d, 0.12 * w, c + 1.11 * H, 0.20 * d,
                 "brain", uv=U["head"], role="brain")
        # 骨の破片（開いた蓋）: 前・左・後ろ
        y0 = c + 0.93 * H
        plates = [
            ((-0.36 * w, y0, -0.47 * d), (0.30 * w, y0 + 0.12 * H, -0.41 * d), (-28, 0, 0),
             (0, y0, -0.44 * d)),
            ((-0.53 * w, y0, -0.30 * d), (-0.47 * w, y0 + 0.12 * H, 0.32 * d), (0, 0, -30),
             (-0.50 * w, y0, 0)),
            ((-0.30 * w, y0, 0.44 * d), (0.36 * w, y0 + 0.10 * H, 0.50 * d), (24, 0, 0),
             (0, y0, 0.47 * d)),
        ]
        for p0, p1, r3, pv in plates[:3 if self.detail >= 2 else 2]:
            self.box(b, *p0, *p1, "bone", uv=U["head"], rot3=r3, pivot=pv, role="plate")
        # 額を伝う血
        for xx, y1 in ((-0.16 * w, 0.64), (0.22 * w, 0.58)):
            self.box(b, xx - 0.025 * w, c + y1 * H, -0.515 * d, xx + 0.025 * w, c + 0.94 * H,
                     -0.495 * d, "blood", uv=U["head"], role="drip")

    def _arm_wound(self, s: str) -> None:
        """腕の傷（wounded / broken で表示）: 上腕外側の噛みちぎられた穴（皮膚の縁・脂肪・筋肉の
        断面の絵）・肘の上の開放骨折（前の裂けた穴から突き出た上腕骨と骨片）・肘へ流れる血。"""
        L = self.L
        sgn = -1 if s == "r" else 1
        ax, at = sgn * L.arm_x, L.arm_t
        ey, sy = L.elbow_y, L.shoulder_y
        ul = sy - ey
        b = f"arm_{s}_wound"
        U = self.U
        # 体の外側の面: ファイル座標では右腕（-X）の外は east、左腕（+X）の外は west（DESIGN §13）
        out_face = "east" if sgn < 0 else "west"
        x_out = ax + sgn * 0.46 * at
        self.box(b, x_out - sgn * 0.05, ey + 0.30 * ul, -0.34 * at, x_out + sgn * 0.06,
                 ey + 0.66 * ul, 0.26 * at, "cut_flesh", uv=U["cap"], role="cap",
                 decals=section_decal((out_face,), kind="plain", fat=0.68, skin=0.84))
        # 開放骨折: 力こぶの前の面に裂けた穴（断面の絵）、そこから折れた骨が前下へ突き出す
        zf = -0.58 * at
        hy = ey + 0.68 * at
        self.box(b, ax - 0.30 * at, hy - 0.28 * at, zf - 0.04, ax + 0.30 * at, hy + 0.28 * at,
                 zf + 0.10, "cut_flesh", uv=U["cap"], role="hole",
                 decals=section_decal(("north",), kind="plain", fat=0.64, skin=0.82))
        self.beam(b, (ax, ey + 0.35 * at, -0.10 * at), (ax + sgn * 0.10 * at, ey + 0.98 * at, -1.02 * at),
                  0.24 * at, 0.22 * at, "bone", uv=U["gore"], role="bone")
        if self.detail >= 2:
            # 縦に割れた骨片
            self.beam(b, (ax + sgn * 0.05 * at, hy - 0.10 * at, -0.50 * at),
                      (ax - sgn * 0.14 * at, hy + 0.30 * at, -0.92 * at), 0.10 * at, 0.09 * at,
                      "bone", uv=U["gore"], role="shard")
        # 流れる血（外側の穴から肘へ・前の穴から下へ）
        self.box(b, x_out - 0.05, ey + 0.05 * ul, -0.20 * at - 0.05, x_out + 0.05 + sgn * 0.02,
                 ey + 0.36 * ul, -0.20 * at + 0.05, "blood", uv=U["gore"], role="drip")
        self.box(b, ax - 0.05 * at - 0.05, ey + 0.10 * at, zf - 0.06, ax - 0.05 * at + 0.05,
                 hy - 0.20 * at, zf + 0.02, "blood", uv=U["gore"], role="drip")

    def _belly_front(self) -> float:
        L = self.L
        belly = 0.006 * L.t + max(0.0, L.bulk - 1.0) * 0.030 * L.t
        return -L.waist_d / 2 - belly

    def _torso_wound(self) -> None:
        """腹の切り傷: 腹直筋の面に沿った斜めの深い裂け目（縁は裂けた皮と脂肪、奥は筋肉）・
        浅い裂け目・流れる血。出っ張らないよう面から 0.03〜0.05 だけ浮かせる。"""
        L = self.L
        t = L.t
        ab, cb = L.abdomen_bot, L.chest_bot
        ww = L.waist_w
        zf = self._belly_front()
        mid = (ab + cb) / 2
        b = "torso_wound"
        U = self.U
        self.box(b, -0.27 * ww, mid - 0.013 * t, zf - 0.03, 0.27 * ww, mid + 0.013 * t,
                 zf + 0.25, "cut_flesh", uv=U["gore"], rot3=(0, 0, 24), pivot=(0, mid, zf),
                 role="gash")
        self.box(b, -0.23 * ww, mid - 0.005 * t, zf - 0.05, 0.23 * ww, mid + 0.004 * t,
                 zf + 0.2, "flesh", uv=U["gore"], rot3=(0, 0, 24), pivot=(0, mid, zf),
                 role="gash")
        if self.detail >= 2:
            m2 = ab + 0.22 * (cb - ab)
            self.box(b, -0.25 * ww, m2 - 0.006 * t, zf - 0.03, 0.18 * ww, m2 + 0.006 * t,
                     zf + 0.2, "cut_flesh", uv=U["gore"], rot3=(0, 0, -12), pivot=(0, m2, zf),
                     role="gash")
        # 裂け目から下へ流れる血（裂け目は 24° 傾いているので、その線の上から垂らす）
        tan = math.tan(math.radians(24))
        for xx, ln in ((-0.18 * ww, 0.06 * t), (0.14 * ww, 0.085 * t)):
            y_top = mid - xx * tan
            self.box(b, xx - 0.06, y_top - ln, zf - 0.035, xx + 0.06, y_top, zf + 0.05,
                     "blood", uv=U["gore"], role="drip")

    def _guts(self) -> None:
        """垂れた腸: 腹の裂け目から溢れ、腿の高さまで垂れて戻る輪。"""
        L = self.L
        t = L.t
        ab, cb = L.abdomen_bot, L.chest_bot
        ww = L.waist_w
        zf = self._belly_front()
        b = "guts"
        U = self.U
        g = 0.032 * t
        pts = [
            (0.10 * ww, ab + 0.35 * (cb - ab), zf + 0.15),
            (0.20 * ww, ab - 0.02 * t, zf - 0.55),
            (0.12 * ww, ab - 0.10 * t, zf - 0.75),
            (-0.08 * ww, ab - 0.155 * t, zf - 0.55),
            (-0.20 * ww, ab - 0.10 * t, zf - 0.40),
            (-0.13 * ww, ab - 0.03 * t, zf - 0.35),
            (-0.02 * ww, ab + 0.10 * (cb - ab), zf + 0.10),
        ]
        if self.detail < 2:
            pts = pts[:5]
        for i in range(len(pts) - 1):
            self.beam(b, pts[i], pts[i + 1], g, g * 0.92, "guts", uv=U["gore"], role="gut",
                      over=g * 0.35)
        # 裂け目から溢れた腸の塊
        self.box(b, -0.14 * ww, ab + 0.18 * (cb - ab), zf - 0.30, 0.20 * ww,
                 ab + 0.42 * (cb - ab), zf + 0.25, "guts", uv=U["gore"], role="gut")
        # 輪の底から滴る血
        self.box(b, -0.02 * ww - 0.06, ab - 0.155 * t - g * 0.4 - 0.4, zf - 0.55 - 0.06,
                 -0.02 * ww + 0.06, ab - 0.155 * t - g * 0.3, zf - 0.55 + 0.06, "blood",
                 uv=U["gore"], role="drip")

    def _torso_stump(self) -> None:
        """胴の断面（下向き）: 断面・背骨（腰椎 2 つ）・こぼれる腸・めくれた皮・血。"""
        L = self.L
        t = L.t
        ab = L.abdomen_bot
        ww, wd = L.waist_w, L.waist_d
        b = "stump_torso"
        U = self.U
        rx, rz = 0.5 * ww, 0.5 * wd
        # 下面（見える切り口）: down 面の v は +Z へ増える（v=1 が背中側）。腰椎は後ろ、前は腸
        sec = section_decal(("down",), kind="torso",
                            bone_at=(0.5, round((0.35 * wd + rz * 1.01) / (2.02 * rz), 3)),
                            bone_r=round(0.085 * ww / (min(rx, rz) * 1.01), 3))
        self.box(b, -rx * 1.01, ab - CAP_DEPTH, -rz * 1.01, rx * 1.01, ab + 0.12, rz * 1.01,
                 "cut_flesh", uv=U["cap"], role="cap", decals=sec)
        self.box(b, -0.08 * ww, ab - 0.030 * t, 0.26 * wd, 0.08 * ww, ab - 0.05, 0.44 * wd,
                 "bone", uv=U["gore"], role="bone")
        self.box(b, -0.06 * ww, ab - 0.050 * t, 0.29 * wd, 0.06 * ww, ab - 0.028 * t, 0.41 * wd,
                 "bone", uv=U["gore"], role="bone2")
        g = 0.030 * t
        chain = [(-0.18 * ww, ab - 0.05, -0.15 * wd), (-0.22 * ww, ab - 0.06 * t, -0.25 * wd),
                 (-0.10 * ww, ab - 0.10 * t, -0.10 * wd)]
        for i in range(len(chain) - 1):
            self.beam(b, chain[i], chain[i + 1], g, g * 0.9, "guts", uv=U["gore"], role="gut",
                      over=g * 0.3)
        if self.detail >= 2:
            self.beam(b, (0.15 * ww, ab - 0.05, 0.0), (0.20 * ww, ab - 0.05 * t, -0.20 * wd), g,
                      g * 0.9, "guts", uv=U["gore"], role="gut", over=g * 0.3)
        self.beam(b, (rx * 0.95, ab + 0.02, -0.2 * rz), (rx * 1.15, ab - 0.035 * t, -0.3 * rz),
                  0.07, rz * 0.9, "skin", uv=U["gore"], role="flap")
        self.box(b, -0.30 * ww - 0.07, ab - 0.10 - 0.05 * t, -0.30 * wd - 0.07,
                 -0.30 * ww + 0.07, ab - 0.08, -0.30 * wd + 0.07, "blood", uv=U["gore"],
                 role="drip")
        self.cuts[b] = dict(part="pelvis", centre=(0, ab, 0), rx=rx, rz=rz, facing=-1, stub=None)

    # ------------------------------------------------------------------ ロケータ
    def _place_locators(self) -> None:
        L = self.L
        t, H, c = L.t, L.H, L.chin
        at = L.arm_t
        locs = {
            "loc_neck": (0, c + 0.25 * H, L.neck_z),
            "loc_head": (0, c + 0.55 * H, 0.0),
            "loc_mouth": (0, c + 0.20 * H, -0.52 * L.head_d),
            "loc_chest": (0, (L.chest_bot + L.chest_top) / 2, -L.chest_d / 2 - 0.1),
            "loc_waist": (0, L.abdomen_bot - 0.1, 0.0),
            "loc_belly": (0, (L.abdomen_bot + L.chest_bot) / 2, -L.waist_d / 2 - 0.1),
        }
        for s, sgn in (("r", -1), ("l", 1)):
            ax = sgn * L.arm_x
            lx = sgn * L.stance
            locs[f"loc_shoulder_{s}"] = (ax + sgn * 0.04 * at, L.shoulder_y - 1.6 * at - 0.1, 0)
            locs[f"loc_elbow_{s}"] = (ax, L.elbow_y - 0.22 * at - 0.1, 0.03 * at)
            locs[f"loc_hand_{s}"] = (ax, L.wrist_y - L.palm_l * 0.7, 0.0)
            locs[f"loc_hip_{s}"] = (lx + sgn * 0.06 * L.thigh_t, L.hip_y - 0.05 * t - 0.1, 0)
            locs[f"loc_knee_{s}"] = (sgn * L.knee_x, L.knee_y - 0.02 * t - 0.1, 0)
        for name, pos in locs.items():
            bone = LOCATOR_BONES[name]
            self.bones[bone].locators[name] = [round(float(v), 3) for v in pos]
            self.locators[name] = (bone, tuple(round(float(v), 3) for v in pos))

    # ------------------------------------------------------------------ 部位の箱
    def _measure_segments(self) -> None:
        acc: Dict[str, list] = {}
        for bone in self.model.bones:
            for cube in bone.cubes:
                seg = getattr(cube, "nr_seg", None)
                if not seg:
                    continue
                pts = (cube_matrix(cube) @ cube_corners(cube).T).T[:, :3]
                lo, hi = pts.min(axis=0), pts.max(axis=0)
                if seg in acc:
                    acc[seg][0] = np.minimum(acc[seg][0], lo)
                    acc[seg][1] = np.maximum(acc[seg][1], hi)
                else:
                    acc[seg] = [lo, hi, bone.name]
        head_parts = [acc[k] for k in ("cranium", "face", "jaw") if k in acc]
        if head_parts:
            acc["head"] = [np.min([p[0] for p in head_parts], axis=0),
                           np.max([p[1] for p in head_parts], axis=0), "head"]
        for k, (lo, hi, bone) in acc.items():
            self.segments[k] = dict(
                lo=[round(float(v), 3) for v in lo], hi=[round(float(v), 3) for v in hi],
                bone=bone, centre=[round(float(v), 3) for v in (lo + hi) / 2],
                size=[round(float(v), 3) for v in hi - lo])

    # ------------------------------------------------------------------ まとめ
    def visibility_rules(self) -> List[Tuple[str, str]]:
        return visibility_rules(self.model)

    def part_visibility(self) -> list:
        return part_visibility(self.visibility_rules())

    def hitboxes(self) -> dict:
        return hitboxes(self.model)

    def counts(self) -> dict:
        body = gore = 0
        gore_bones = set(GORE_BONES)
        for b in self.model.bones:
            if b.name in gore_bones:
                gore += len(b.cubes)
            elif b.name in SKELETON_PARENT:
                body += len(b.cubes)
        return dict(body=body, gore=gore, total=body + gore)


# ---------------------------------------------------------------------------
# part_visibility の生成
# ---------------------------------------------------------------------------


def _armor_rule(name: str) -> Optional[Tuple[str, int]]:
    """armor_<部位>[_<N>] は装甲の段階 nr:armor >= N（N 省略は 1）で表示。"""
    if not name.startswith("armor_"):
        return None
    tail = name.rsplit("_", 1)[-1]
    n = int(tail) if tail.isdigit() and 1 <= int(tail) <= 3 and name.count("_") >= 2 else 1
    return ("nr:armor", n)


def _bone_constraints(bones: Dict[str, Bone], name: str):
    """ボーンと全祖先の条件を合わせた {enum プロパティ: 許す値}, {int プロパティ: 最小値}。"""
    enum_c: Dict[str, frozenset] = {}
    int_c: Dict[str, int] = {}
    cur: Optional[str] = name
    seen = set()
    while cur and cur not in seen:
        seen.add(cur)
        for prop, allowed in OWN_RULES.get(cur, ()):
            enum_c[prop] = enum_c.get(prop, frozenset(PROPERTIES[prop]["values"])) & allowed
        ar = _armor_rule(cur)
        if ar:
            int_c[ar[0]] = max(int_c.get(ar[0], 0), ar[1])
        parent = bones[cur].parent if cur in bones else SKELETON_PARENT.get(cur)
        cur = parent
    return enum_c, int_c


def _expr(enum_c: Dict[str, frozenset], int_c: Dict[str, int]) -> Optional[str]:
    terms = []
    for prop in sorted(enum_c):
        allowed = enum_c[prop]
        values = PROPERTIES[prop]["values"]
        if len(allowed) == len(values):
            continue
        if not allowed:
            return "false"
        q = f"q.property('{prop}')"
        excluded = [v for v in values if v not in allowed]
        incl = [v for v in values if v in allowed]
        if len(incl) <= len(excluded):
            parts = [f"{q} == '{v}'" for v in incl]
            terms.append(parts[0] if len(parts) == 1 else "(" + " || ".join(parts) + ")")
        else:
            terms.extend(f"{q} != '{v}'" for v in excluded)
    for prop in sorted(int_c):
        terms.append(f"q.property('{prop}') >= {int_c[prop]}")
    if not terms:
        return None
    return " && ".join(terms)


def visibility_rules(model: Optional[Model] = None) -> List[Tuple[str, str]]:
    """part_visibility の (ボーン名, Molang) の並び。

    条件は §3 のプロパティ表（OWN_RULES）と armor_* の規則から作り、**祖先全員の条件を AND** する
    （エンジンが子へ非表示を伝えるかどうかに依らない）。model を渡すと服・装備の子ボーンも含める
    （model 無しなら §3 の骨格だけ）。常に表示のボーンは載せない（先頭の {"*": true} が受け持つ）。"""
    if model is None:
        bones = {n: Bone(n, (0, 0, 0), p) for n, p in SKELETON}
        order = list(BONE_NAMES)
    else:
        bones = {b.name: b for b in model.bones}
        order = [b.name for b in model.bones]
    out = []
    for name in order:
        e = _expr(*_bone_constraints(bones, name))
        if e:
            out.append((name, e))
    return out


def part_visibility(rules: Sequence[Tuple[str, str]]) -> list:
    """render controller の part_visibility 配列（[{"*": true}, {ボーン: 式}, ...]）。"""
    return [{"*": True}] + [{bone: expr} for bone, expr in rules]


def merge_visibility(*rule_lists: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """全種類で共通の render controller 用に規則を合わせる。同じ名前のボーンが種類によって
    違う親（＝違う式）を持つと一つの式にできないので ValueError（服の子ボーンは付く部位ごとに
    名前を分けること。例 `hat` は必ず head の子）。"""
    merged: Dict[str, str] = {}
    order: List[str] = []
    for rules in rule_lists:
        for bone, expr in rules:
            if bone in merged:
                if merged[bone] != expr:
                    raise ValueError(f"part_visibility conflict for bone '{bone}': "
                                     f"{merged[bone]!r} vs {expr!r}")
                continue
            merged[bone] = expr
            order.append(bone)
    return [(b, merged[b]) for b in order]


def rest_pose(model: Model) -> Dict[str, List[float]]:
    """ジオメトリに焼いた休みの回転 {ボーン: [rx, ry, rz]}（0 でないものだけ）。

    統合版のアニメーションの rotation はこの上に足される。リグが焼くのは:
    torso / chest = 猫背の 45% / 55%（正の rx = 前傾）、neck / head = 顔を前へ戻す負の rx、
    arm_* = 猫背の 80% を打ち消す負の rx と外転 5°（右腕 +rz、左腕 -rz）、
    stump_arm_* / stump_leg_* = STUMP_TILT（切り口を前へ向ける）。
    下顎は正の rx で開く（顎先が下・後ろへ）。"""
    return {b.name: list(b.rotation) for b in model.bones if b.rotation and any(b.rotation)}


def default_state() -> Dict[str, object]:
    return {k: v["default"] for k, v in PROPERTIES.items()}


def visible_bones(model: Model, state: Optional[dict] = None) -> set:
    """プロパティの状態 → 見えるボーンの集合（Python で評価。プレビューと検査用）。"""
    st = default_state()
    st.update(state or {})
    bones = {b.name: b for b in model.bones}
    vis = set()
    for name in bones:
        enum_c, int_c = _bone_constraints(bones, name)
        ok = all(st[p] in allowed for p, allowed in enum_c.items())
        ok = ok and all(int(st[p]) >= n for p, n in int_c.items())
        if ok:
            vis.add(name)
    return vis


def molang_eval(expr: str, state: dict) -> bool:
    """このモジュールが出す Molang の部分集合（q.property・==・!=・>=・&&・||・括弧）を評価する。
    生成した文字列そのものが意図通りかの検査に使う。"""
    import re
    st = default_state()
    st.update(state)
    py = re.sub(r"q\.property\('([^']+)'\)", lambda m: repr(st[m.group(1)]), expr)
    py = py.replace("&&", " and ").replace("||", " or ")
    if re.search(r"[^\w\s'=!<>().:\-]", py):
        raise ValueError(f"unexpected token in {expr!r}")
    return bool(eval(py, {"__builtins__": {}}, {"false": False, "true": True}))  # noqa: S307


def gib_visibility_rules() -> List[Tuple[str, str]]:
    """controller.render.nr.gib 用: p_* の 1 本だけを nr:part で表示する。"""
    return [(name, f"q.property('nr:part') == {i}") for i, name in enumerate(GIB_PARTS)]


# ---------------------------------------------------------------------------
# 当たり箱
# ---------------------------------------------------------------------------

_HIT_ANCHORS = {
    "head": ("head", 0), "neck": ("head", 0), "chest": ("torso", 0), "torso": ("torso", 1),
    "pelvis": ("torso", 1), "waist": ("torso", 1), "root": ("torso", 1),
    "arm_r": ("arm_r", 0), "forearm_r": ("arm_r", 1), "hand_r": ("arm_r", 1),
    "arm_l": ("arm_l", 0), "forearm_l": ("arm_l", 1), "hand_l": ("arm_l", 1),
    "leg_r": ("leg_r", 0), "shin_r": ("leg_r", 1), "foot_r": ("leg_r", 1),
    "leg_l": ("leg_l", 0), "shin_l": ("leg_l", 1), "foot_l": ("leg_l", 1),
}
HIT_PARTS = ("head", "torso", "arm_r", "arm_l", "leg_r", "leg_l")


def _box_json(lo, hi) -> dict:
    c = (np.asarray(lo) + np.asarray(hi)) / 2
    h = (np.asarray(hi) - np.asarray(lo)) / 2
    return {"c": [round(float(v), 3) + 0.0 for v in c],
            "h": [round(max(0.02, float(v)), 3) + 0.0 for v in h]}


def hitboxes(model: Model, pad: float = 0.02) -> dict:
    """部位の当たり箱（DESIGN §12: `SHAPES[key]` の中身）。

    返り値 = {"height", "width", "depth", "stand": {部位: [{c, h}, ...]}, "lie": {...},
    "prone": {...}, "locators": {名前: [r, u, f]}}。単位はブロック、原点はゾンビの足元、
    軸は r = ゾンビ自身の右、u = 上、f = ゾンビが向いている前（ジオメトリの (-x, y, -z)/16）。
    箱はその軸に沿った直方体（c = 中心、h = 半分の大きさ）。部位ごとに
    head（頭＋首）[1 箱]、torso（胸 / 腹＋骨盤）[2 箱]、arm_*（上腕 / 前腕＋手）、
    leg_*（太腿 / 脛＋足）。ゴア用ボーンは数えず、服・装備の子ボーンは付いた部位に数える。

    * stand: 立ち姿勢（ジオメトリの猫背などの回転を含む）。
    * lie: 仰向け（DESIGN §12）。足元を軸に後ろへ倒した姿勢で、頭が -f、体の前面が上。
      (r, u, f) → (r, f - f_back, -u)。f_back は体のいちばん後ろ。
    * prone: うつ伏せの這い（追加）。股関節の高さを原点に前へ倒し、頭が +f。
      (r, u, f) → (r, f_front - f, u - hip_u)。

    向きの根拠: 顔は north 面（-Z。バニラの肌の箱 UV で顔の (8,8) が north の矩形）、体の右は -X
    （バニラの rightArm の pivot は x=-5）、ヨー 0 のエンティティは +Z（南）を向く。よって
    r = -x、f = -z。スクリプトでは yaw = getRotation().y（度）から
        前 F = (-sin yaw, 0, cos yaw)、右 R = (-cos yaw, 0, -sin yaw)
        ワールド = 足元 + r·R + u·(0,1,0) + f·F
    （ヨー 0 で前が南、右が西）。
    """
    W = bone_world(model)
    bones = {b.name: b for b in model.bones}

    def anchor(name):
        cur = name
        while cur:
            if cur in GORE_BONES:
                return None
            if cur in _HIT_ANCHORS:
                return _HIT_ANCHORS[cur]
            cur = bones[cur].parent if cur in bones else None
        return None

    rig = getattr(model, "nr_rig", None)
    # 首は肩より上だけを頭に数える（胸の箱と大きく重ならないように）
    neck_floor = (rig.L.shoulder_y + 0.01 * rig.L.t) if rig is not None else None
    pts: Dict[Tuple[str, int], list] = {}
    allp = []
    for b in model.bones:
        a = anchor(b.name)
        if a is None:
            continue
        for cube in b.cubes:
            C = cube_matrix(cube) @ cube_corners(cube).T
            if b.name == "neck" and neck_floor is not None:
                C[1] = np.maximum(C[1], neck_floor)
            P = (W[b.name] @ C).T[:, :3]
            ruf = np.stack([-P[:, 0], P[:, 1], -P[:, 2]], axis=1) / 16.0
            pts.setdefault(a, []).append(ruf)
            allp.append(ruf)
    allp = np.concatenate(allp)
    hip_u = None
    if "leg_r" in bones:
        hip_u = bones["leg_r"].pivot[1] / 16.0
    else:
        hip_u = float(allp[:, 1].max()) * 0.52
    f_back = float(allp[:, 2].min())
    f_front = float(allp[:, 2].max())

    def boxes(transform):
        out: Dict[str, list] = {}
        for part in HIT_PARTS:
            lst = []
            for k in range(2):
                arr = pts.get((part, k))
                if arr is None:
                    continue
                q = transform(np.concatenate(arr))
                lst.append(_box_json(q.min(axis=0) - pad, q.max(axis=0) + pad))
            out[part] = lst
        return out

    stand = boxes(lambda q: q)
    lie = boxes(lambda q: np.stack([q[:, 0], q[:, 2] - f_back, -q[:, 1]], axis=1))
    prone = boxes(lambda q: np.stack([q[:, 0], f_front - q[:, 2], q[:, 1] - hip_u], axis=1))
    # ロケータ（立ち姿勢）
    locs = {}
    for b in model.bones:
        for name, p in getattr(b, "locators", {}).items():
            P = W[b.name] @ np.array([*p, 1.0])
            locs[name] = geo_to_ruf(P[:3])
    return {
        "height": round(float(allp[:, 1].max()), 3),
        "width": round(float(allp[:, 0].max() - allp[:, 0].min()), 3),
        "depth": round(float(allp[:, 2].max() - allp[:, 2].min()), 3),
        "stand": stand, "lie": lie, "prone": prone, "locators": locs,
    }


# ---------------------------------------------------------------------------
# gib（ちぎれた部位）
# ---------------------------------------------------------------------------


def _subtree(bones: Dict[str, Bone], root: str, exclude: Iterable[str]) -> List[str]:
    ex = set(exclude)
    children: Dict[str, List[str]] = {}
    for b in bones.values():
        if b.parent:
            children.setdefault(b.parent, []).append(b.name)
    out = []
    stack = [root]
    while stack:
        n = stack.pop(0)
        if n in ex or n not in bones:
            continue
        out.append(n)
        stack.extend(children.get(n, []))
    return out


def _bake(cube: Cube, M: np.ndarray) -> Cube:
    """キューブ（自身の回転込み）にアフィン M（回転＋平行移動）を焼き込んだ複製。UV はそのまま。"""
    c = copy.copy(cube)
    c.rects = dict(cube.rects)
    c.uv = list(cube.uv) if cube.uv else None
    c.decals = copy.deepcopy(cube.decals)
    c.fixed = True
    o = np.array(cube.origin, float)
    s = np.array(cube.size, float)
    pc = np.array(cube.pivot if cube.pivot else o + s / 2, float)
    Rc = rot(*cube.rotation) if cube.rotation and any(cube.rotation) else np.eye(3)
    A = M[:3, :3] @ Rc
    q = M[:3, :3] @ pc + M[:3, 3]                 # 新しい回転の中心（元の pivot の行き先）
    new_o = o + (q - pc)
    c.origin = [round(float(v), 3) + 0.0 for v in new_o]
    if np.allclose(A, np.eye(3), atol=1e-6):
        c.rotation = None
        c.pivot = None
    else:
        c.rotation = list(euler(A))
        c.pivot = [round(float(v), 3) + 0.0 for v in q]
    return c


def _shift(cube: Cube, d) -> None:
    cube.origin = [round(cube.origin[i] + float(d[i]), 3) + 0.0 for i in range(3)]
    if cube.pivot:
        cube.pivot = [round(cube.pivot[i] + float(d[i]), 3) + 0.0 for i in range(3)]


def _flip_v(r):
    """面の矩形 (u, v, du, dv) の上下を反転（負の uv_size）。"""
    u, v, du, dv = r
    return (u, v + dv, du, -dv)


def rect_key(r):
    """反転した矩形も元の矩形と同じものとして比べるための正規形。"""
    u, v, du, dv = r
    if du < 0:
        u, du = u + du, -du
    if dv < 0:
        v, dv = v + dv, -dv
    return (u, v, du, dv)


def _fixed_cube(origin, size, src: Cube, style: Optional[str] = None,
                swap_ud: bool = False, rotation=None, pivot=None) -> Cube:
    """src の UV（各面の矩形）を借りた新しいキューブ。swap_ud で上面と下面の矩形を入れ替える。

    入れ替えた矩形は v を反転する（負の uv_size）: up 面の v は -Z へ、down 面の v は +Z へ増えるので、
    そのまま貼ると前後が逆になる（首の断面の頸椎が gib の頭では前に来てしまう）。反転すると
    断面の絵の前後（背骨は背中側）がモデル空間で元と同じ向きに保たれる。"""
    c = Cube(origin, size, style or src.style, uv_scale=src.uv_scale, rotation=rotation,
             pivot=pivot)
    c.fixed = True
    c.uv = list(src.uv) if src.uv else [0, 0]
    c.rects = dict(src.rects)
    if swap_ud:
        c.rects["up"], c.rects["down"] = _flip_v(src.rects["down"]), _flip_v(src.rects["up"])
    c._scale = src._scale
    return c


def _role_cubes(bone: Optional[Bone]) -> Dict[str, Cube]:
    out: Dict[str, Cube] = {}
    if bone is None:
        return out
    for c in bone.cubes:
        role = getattr(c, "nr_role", None)
        if role is None:                      # JSON から戻したモデル等: スタイルで代用
            role = {"cut_flesh": "cap", "bone": "bone", "blood_dry": "marrow", "skin": "flap",
                    "blood": "drip", "flesh": "tendon"}.get(c.style)
        if role and role not in out:
            out[role] = c
    return out


def _cut_def(model: Model, part: str, root_name: str, stump: str, bones: Dict[str, Bone],
             W: Dict[str, np.ndarray]) -> dict:
    """gib の切り口（部分木の根の bind 空間）: centre, rx, rz, facing(+1 上 / -1 下), stub。"""
    rig = getattr(model, "nr_rig", None)
    L = rig.L if rig is not None else None
    if rig is not None and stump in rig.cuts:
        cut = dict(rig.cuts[stump])
        cx, cy, cz = cut["centre"]
        if part == "p_head":
            # 頭の側: 首を少し残し（首の皮の UV を借りる）、その下端に断面
            neck_cube = bones["neck"].cubes[0] if bones.get("neck") and bones["neck"].cubes \
                else None
            return dict(centre=(cx, cy - 0.15 * L.H, cz), rx=cut["rx"], rz=cut["rz"],
                        facing=-1, stub_src=neck_cube, stub_from=cy + 0.02, part_root=root_name,
                        bone_dz=0.26 * L.neck_d)
        if part == "p_jaw":
            return dict(centre=(0, L.chin + 0.19 * L.H, -0.22 * L.head_d), rx=0.38 * L.head_w,
                        rz=0.20 * L.head_d, facing=1, stub_src=None, part_root=root_name,
                        bone=False)
        if part.startswith("p_arm_"):
            s = part[-1]
            sgn = -1 if s == "r" else 1
            at = L.arm_t
            return dict(centre=(sgn * L.arm_x + sgn * 0.05 * at, L.shoulder_y + 0.10 * at, 0),
                        rx=0.56 * at, rz=0.55 * at, facing=1, stub_src=None, part_root=root_name)
        if part.startswith("p_forearm_"):
            s = part[-1]
            sgn = -1 if s == "r" else 1
            ft = L.fore_t
            return dict(centre=(sgn * L.arm_x, L.elbow_y + 0.04 * (L.elbow_y - L.wrist_y), 0),
                        rx=0.46 * ft, rz=0.47 * ft, facing=1, stub_src=None, part_root=root_name)
        if part.startswith("p_leg_"):
            s = part[-1]
            sgn = -1 if s == "r" else 1
            tt = L.thigh_t
            return dict(centre=(sgn * L.stance + sgn * 0.06 * tt, L.hip_y + 0.025 * L.t, 0),
                        rx=0.48 * tt, rz=0.47 * tt, facing=1, stub_src=None, part_root=root_name)
        if part.startswith("p_shin_"):
            s = part[-1]
            sgn = -1 if s == "r" else 1
            cf = L.calf_t
            return dict(centre=(sgn * L.knee_x, L.knee_y - 0.010 * L.t, -0.02 * cf),
                        rx=0.43 * cf, rz=0.42 * cf, facing=1, stub_src=None, part_root=root_name)
        if part == "p_lower":
            return dict(centre=(0, L.abdomen_bot + 0.004 * L.t, 0), rx=0.48 * L.hip_w,
                        rz=0.48 * L.pelvis_d, facing=1, stub_src=None, part_root=root_name,
                        bone_dz=0.34 * L.waist_d)
    # 予備: 部分木の根の箱から測る（根の上端か下端）
    root = bones[root_name]
    pts = [cube_corners(c)[:, :3] for c in root.cubes] or [np.zeros((1, 3))]
    P = np.concatenate(pts)
    lo, hi = P.min(axis=0), P.max(axis=0)
    facing = -1 if part == "p_head" else 1
    y = lo[1] if facing < 0 else hi[1]
    return dict(centre=((lo[0] + hi[0]) / 2, y, (lo[2] + hi[2]) / 2),
                rx=(hi[0] - lo[0]) * 0.40, rz=(hi[2] - lo[2]) * 0.40, facing=facing,
                stub_src=None, part_root=root_name)


def _cap_cubes(cut: dict, roles: Dict[str, Cube], seed: int) -> List[Cube]:
    """gib の切り口: 断面の円板・突き出た骨と髄・めくれた皮・垂れる血。UV は stump から借りる。"""
    rng = random.Random(seed)
    cx, cy, cz = cut["centre"]
    rx, rz, f = cut["rx"], cut["rz"], cut["facing"]
    out: List[Cube] = []
    stub_src = cut.get("stub_src")
    if stub_src is not None and cut.get("stub_from") is not None:
        y0, y1 = sorted((cy, cut["stub_from"]))
        out.append(_fixed_cube((cx - rx, y0, cz - rz), (2 * rx, y1 - y0, 2 * rz), stub_src))
    cap = roles.get("cap")
    if cap is None:
        return out
    # 円板（切り口の面から 0.08 外へ）。stump の断面は下面（首は上面）が見える面なので、向きが
    # 逆なら上下の矩形を入れ替える
    swap = (f != cut.get("src_facing", -1))
    y_a, y_b = (cy - 0.10, cy + CAP_DEPTH) if f > 0 else (cy - CAP_DEPTH, cy + 0.10)
    out.append(_fixed_cube((cx - rx * 1.01, y_a, cz - rz * 1.01),
                           (rx * 2.02, y_b - y_a, rz * 2.02), cap, swap_ud=swap))
    bone = roles.get("bone")
    if bone is not None and cut.get("bone", True):
        br = min(rx, rz) * (0.22 if cut.get("bone_dz") else 0.30)
        bl = 0.20 + min(rx, rz) * 0.5
        bx = cx + rng.uniform(-0.06, 0.06) * rx
        bz = cz + cut.get("bone_dz", 0.0)
        ya, yb = (cy, cy + CAP_DEPTH + bl) if f > 0 else (cy - CAP_DEPTH - bl, cy)
        out.append(_fixed_cube((bx - br, ya, bz - br), (2 * br, yb - ya, 2 * br), bone,
                               swap_ud=swap))
    flap = roles.get("flap")
    if flap is not None:
        ln = 0.3 + min(rx, rz) * 0.4
        ang = rng.choice((-1, 1)) * 28.0
        ya = cy if f > 0 else cy - ln
        out.append(_fixed_cube((cx + rx * 0.80, ya, cz - rz * 0.45), (0.07, ln, rz * 0.9), flap,
                               rotation=[0, 0, ang],
                               pivot=[round(cx + rx * 0.85, 3), round(cy, 3), round(cz, 3)]))
    drip = roles.get("drip")
    if drip is not None:
        ln = 0.25 + rng.uniform(0, 0.25)
        ya = cy + 0.05 if f > 0 else cy - 0.06 - ln
        out.append(_fixed_cube((cx - rx * 0.4 - 0.05, ya, cz + rz * 0.5 - 0.05),
                               (0.10, ln if f < 0 else 0.10, 0.10), drip))
    return out


def extract_gibs(model: Model, key: str, uv_check: bool = True) -> Model:
    """ゾンビ本体のモデルから `geometry.nr.gib.<key>` を作る（DESIGN §5）。

    * ボーン p_head p_jaw p_arm_r p_arm_l p_forearm_r p_forearm_l p_leg_r p_leg_l p_shin_r p_shin_l
      p_lower（GIB_TYPE_PARTS）。各ボーンは部分木（他のコードが子ボーンとして付けた服・装備も
      含む。ゴア用ボーンは除く）のキューブを、部分木の根から見た形のまま 1 本のボーンへ焼き込む
      （中のボーンの回転はキューブの回転に合成する）。
    * 部位の重心（体積の重み付き）が原点に来るように平行移動する。p_* の pivot は (0,0,0)。
    * 切り口に断面（円板・骨・髄・皮・血）を足す。UV は対応する stump のキューブから借りるので、
      テクスチャはゾンビと同じアトラス。全キューブの面ごとの UV は元のまま保つ（切り口の向きが stump と
      逆のときだけ、上下の面の矩形を入れ替えて v を反転する = 断面の背骨が背中側に来る。rect_key で比べる）。
    * 返すモデルの `gib_info[p] = {"half": [x,y,z] 単位, "src": [r,u,f] ブロック, "cubes": n}`。
      half は原点からの箱の半分の大きさ（寝姿で地面から浮かせる量）、src は本体での重心の位置
      （gib を出す場所）。
    """
    if not model.tex_w:
        model.pack()
    bones = {b.name: b for b in model.bones}
    W = bone_world(model)
    gib = NRModel(f"geometry.nr.gib.{key}", uv_scale=model.uv_scale,
                  visible_bounds=(2.5, 2.5), vb_offset=(0, 0.5, 0),
                  max_atlas=(model.tex_w, model.tex_h))
    gib.tex_w, gib.tex_h = model.tex_w, model.tex_h
    gib.gib_info = {}
    seed0 = zlib.crc32(key.encode("utf-8"))
    for part in GIB_TYPE_PARTS:
        root, exclude, stump = GIB_SOURCES[part]
        pb = gib.bone(part, (0, 0, 0))
        if root not in bones:
            gib.gib_info[part] = dict(half=[0, 0, 0], src=[0, 0, 0], cubes=0)
            continue
        names = _subtree(bones, root, set(exclude) | (GORE_BONES - {root}))
        Winv = np.linalg.inv(W[root])
        cubes: List[Cube] = []
        for n in names:
            M = Winv @ W[n]
            for c in bones[n].cubes:
                bc = _bake(c, M)
                bc.nr_src = (n, c)                 # 元のボーンとキューブ（検査用）
                cubes.append(bc)
        # 切り口
        cut = _cut_def(model, part, root, stump, bones, W)
        rig = getattr(model, "nr_rig", None)
        if rig is not None and stump in rig.cuts:
            cut["src_facing"] = rig.cuts[stump]["facing"]
        roles = _role_cubes(bones.get(stump))
        cubes.extend(_cap_cubes(cut, roles, seed0 + GIB_PART_INDEX[part]))
        # 重心を原点へ
        vol = np.array([max(1e-4, c.size[0] * c.size[1] * c.size[2]) for c in cubes])
        cen = []
        for c in cubes:
            P = (cube_matrix(c) @ np.array([*(np.array(c.origin) + np.array(c.size) / 2), 1.0]))
            cen.append(P[:3])
        cen = np.array(cen)
        centroid = (cen * vol[:, None]).sum(axis=0) / vol.sum()
        for c in cubes:
            _shift(c, -centroid)
        pb.cubes = cubes
        allp = np.concatenate([(cube_matrix(c) @ cube_corners(c).T).T[:, :3] for c in cubes])
        half = np.maximum(np.abs(allp.min(axis=0)), np.abs(allp.max(axis=0)))
        src = W[root] @ np.array([*centroid, 1.0])
        gib.gib_info[part] = dict(half=[round(float(v), 3) for v in half],
                                  src=geo_to_ruf(src[:3]), cubes=len(cubes),
                                  centroid=[round(float(v), 4) for v in centroid], root=root)
    if uv_check:
        for c in gib.all_cubes():
            for face, (u, v, du, dv) in c.rects.items():
                if u < 0 or v < 0 or u + du > gib.tex_w or v + dv > gib.tex_h:
                    raise ValueError(f"{gib.identifier}: UV out of atlas on {face}")
    return gib


# ---------------------------------------------------------------------------
# 汎用の肉片 geometry.nr.gib.generic
# ---------------------------------------------------------------------------

GENERIC_TONE = dict(base=(150, 150, 128), shadow=(92, 96, 84), highlight=(186, 182, 160))


def build_generic_gibs(paint: bool = True, seed: int = 4242) -> Model:
    """`geometry.nr.gib.generic`（p_guts p_brain p_chunk p_bone p_eye）。

    それぞれ重心が原点。自前の小さなテクスチャ（128 か 256）を使い、nr_paint が import できれば
    `model.texture` に塗った画像を入れる（無ければ None。gen_nr_zombies が後で
    `paint_generic_gibs(model)` を呼んで塗る）。"""
    m = NRModel("geometry.nr.gib.generic", uv_scale=8, visible_bounds=(1.5, 1.5),
                vb_offset=(0, 0.25, 0), max_atlas=(256, 256))
    def add(bone, origin, size, style, uv=8, rotation=None, pivot=None):
        c = Cube(origin, size, style, uv_scale=uv, rotation=rotation, pivot=pivot)
        bone.add(c)
        return c

    def beam(bone, p0, p1, w, d, style, uv=8):
        p0 = np.asarray(p0, float)
        p1 = np.asarray(p1, float)
        if p1[1] < p0[1]:
            p0, p1 = p1, p0
        v = p1 - p0
        L = float(np.linalg.norm(v)) or 1e-3
        dd = v / L
        rx = -math.degrees(math.asin(max(-1, min(1, dd[2]))))
        rz = math.degrees(math.atan2(dd[0], dd[1]))
        return add(bone, (p0[0] - w / 2, p0[1], p0[2] - d / 2), (w, L, d), style, uv,
                   rotation=[round(rx, 2), 0, round(rz, 2)],
                   pivot=[round(float(x), 3) for x in p0])

    # 腸: 平たく渦を巻いた鎖
    g = m.bone("p_guts", (0, 0, 0))
    pts = []
    for i in range(10):
        a = i * 0.95
        r = 2.4 - i * 0.18
        pts.append((math.cos(a) * r, 0.35 + 0.25 * math.sin(i * 1.7), math.sin(a) * r))
    for i in range(len(pts) - 1):
        beam(g, pts[i], pts[i + 1], 1.0, 0.95, "guts")
    add(g, (-0.6, -0.1, -0.6), (1.2, 0.5, 1.2), "blood", 8)
    # 脳: 左右の半球・小脳・脳幹・頭蓋の欠片
    b = m.bone("p_brain", (0, 0, 0))
    add(b, (-1.45, -0.6, -1.6), (1.4, 1.5, 3.1), "brain")
    add(b, (0.05, -0.6, -1.6), (1.4, 1.5, 3.1), "brain")
    add(b, (-0.9, -0.95, 0.9), (1.8, 0.8, 0.9), "brain")
    add(b, (-0.3, -1.6, 0.4), (0.6, 0.9, 0.6), "flesh")
    add(b, (-1.2, 0.7, -0.9), (1.6, 0.25, 1.4), "bone", rotation=[0, 0, 22], pivot=[-0.4, 0.8, 0])
    # 肉片: 断面・皮・脂肪
    k = m.bone("p_chunk", (0, 0, 0))
    add(k, (-1.0, -0.7, -0.8), (2.0, 1.4, 1.6), "cut_flesh")
    add(k, (-1.1, 0.6, -0.9), (2.2, 0.2, 1.8), "skin")
    add(k, (0.6, -0.4, -0.3), (0.9, 0.7, 0.8), "flesh", rotation=[0, 25, 15],
        pivot=[1.0, 0, 0])
    add(k, (-0.5, -0.9, -0.4), (0.8, 0.25, 0.8), "blood")
    # 骨: 曲がった肋骨と髄の見える折れ口
    o = m.bone("p_bone", (0, 0, 0))
    beam(o, (-2.0, -0.4, 0), (-0.6, 0.3, 0), 0.5, 0.6, "bone")
    beam(o, (-0.6, 0.3, 0), (0.9, 0.35, 0), 0.5, 0.6, "bone")
    beam(o, (0.9, 0.35, 0), (2.1, -0.3, 0), 0.45, 0.55, "bone")
    add(o, (1.9, -0.45, -0.2), (0.4, 0.2, 0.4), "blood_dry")
    add(o, (-0.4, 0.1, -0.45), (0.9, 0.5, 0.9), "flesh")
    # 目玉: 眼球・視神経・こびりついた肉
    e = m.bone("p_eye", (0, 0, 0))
    add(e, (-0.55, -0.55, -0.55), (1.1, 1.1, 1.1), "eye", 12)
    beam(e, (0, 0, 0.5), (0.2, -0.3, 1.6), 0.25, 0.25, "flesh")
    add(e, (-0.4, -0.6, 0.35), (0.8, 0.4, 0.4), "flesh")
    m.pack()
    m.texture = paint_generic_gibs(m, seed) if paint else None
    return m


def paint_generic_gibs(model: Model, seed: int = 4242):
    """汎用の肉片を nr_paint で塗る（nr_paint が無ければ None）。"""
    try:
        import nr_paint  # type: ignore
    except Exception:  # noqa: BLE001  まだ無い時は後で塗る（TODO: nr_paint ができたら必ず塗る）
        return None
    styles = nr_paint.zombie_styles(GENERIC_TONE, 2, "clouded", blood=0.6)
    return nr_paint.paint_model(model, styles, seed)


# ---------------------------------------------------------------------------
# 自己検査とプレビュー（python3 tools/nightrunner/nr_rig.py）
# ---------------------------------------------------------------------------

_FALLBACK_COLOURS = {
    "skin": (146, 150, 124), "skin_dark": (112, 104, 92), "flesh": (150, 44, 42),
    "cut_flesh": (128, 26, 28), "bone": (226, 214, 186), "teeth": (214, 200, 150),
    "gums": (118, 40, 52), "guts": (176, 96, 98), "brain": (204, 146, 152),
    "blood": (112, 6, 8), "blood_dry": (62, 12, 10), "eye": (214, 214, 196),
    "hair": (44, 38, 32), "nail": (182, 170, 136),
}


def _fallback_paint(model: Model, seed: int = 1):
    """nr_paint が無い時のプレビュー用の仮塗り（本番では使わない）。"""
    from PIL import Image
    rng = np.random.default_rng(seed)
    img = np.zeros((model.tex_h, model.tex_w, 4), np.uint8)
    for c in model.all_cubes():
        base = np.array(_FALLBACK_COLOURS.get(c.style, (200, 0, 200)), float)
        for face, (u, v, du, dv) in c.rects.items():
            du, dv = max(1, du), max(1, dv)
            n = rng.normal(0, 9, (dv, du, 1))
            col = np.clip(base + n, 0, 255)
            if c.style == "cut_flesh":
                yy, xx = np.mgrid[0:dv, 0:du]
                r = np.maximum(np.abs((xx + 0.5) / du - 0.5), np.abs((yy + 0.5) / dv - 0.5)) * 2
                col[r > 0.82] = (150, 140, 118)
                col[(r > 0.66) & (r <= 0.82)] = (214, 182, 92)
                col[r < 0.26] = (230, 220, 196)
            img[v:v + dv, u:u + du, :3] = col.astype(np.uint8)
            img[v:v + dv, u:u + du, 3] = 255
            dec = (c.decals or {}).get(face)
            if isinstance(dec, dict) and dec.get("name") == "face":
                def P(uu, vv):
                    return int(u + uu * du), int(v + vv * dv)
                ey = dec.get("eye_v", 0.5)
                for sx in (-1, 1):
                    ex = 0.5 + sx * dec.get("eye_dx", 0.25)
                    x0, y0 = P(ex - 0.08, ey - 0.035)
                    x1, y1 = P(ex + 0.08, ey + 0.035)
                    img[y0:y1 + 1, x0:x1 + 1, :3] = (205, 205, 180)
                    img[y0 - 2:y0, x0:x1 + 1, :3] = (70, 64, 56)
                    cx_, cy_ = P(ex, ey)
                    img[cy_:cy_ + 1, cx_ - 1:cx_ + 1, :3] = (90, 90, 80)
                x0, y0 = P(0.30, dec.get("mouth_v", 0.95) - 0.03)
                x1, y1 = P(0.70, dec.get("mouth_v", 0.95) + 0.02)
                img[y0:y1, x0:x1, :3] = (70, 20, 24)
    return Image.fromarray(img, "RGBA")


def _paint(model: Model, build: dict, seed: int, blood: Optional[float] = None):
    """自己検査用の塗り。体の血は zombie_styles の既定（少なめ）。血は傷・断面に任せる。
    顔デカールの eyes と同じ目の種類で "eye"（垂れた目玉）を塗る。"""
    try:
        import nr_paint  # type: ignore
    except ImportError:
        return _fallback_paint(model, seed), "fallback"
    kw = {} if blood is None else {"blood": blood}
    styles = nr_paint.zombie_styles(build.get("skin", GENERIC_TONE), int(build.get("decay", 2)),
                                    build.get("eyes", "clouded"), **kw)
    return nr_paint.paint_model(model, styles, seed), "nr_paint"


SAMPLE_BUILDS = {
    "average": dict(height_cm=176, heads=7.4, bulk=1.0, limb=1.0, hunch=14, arm_len=1.03),
    "tall_thin": dict(height_cm=190, heads=7.8, bulk=0.82, limb=0.82, hunch=8, arm_len=1.08),
    "brute": dict(height_cm=210, heads=7.6, bulk=1.6, limb=1.35, hunch=22, arm_len=1.1),
    "female": dict(height_cm=165, heads=7.3, bulk=0.92, limb=0.9, hunch=10, arm_len=1.0,
                   female=True),
}

PREVIEW_STATES = [
    ("intact", {}),
    ("arms_upper+severed", {"nr:arm_r": "cut_upper", "nr:arm_l": "cut_upper",
                            "nr:head": "severed"}),
    ("legs_lower", {"nr:leg_r": "cut_lower", "nr:leg_l": "cut_lower", "nr:arm_r": "cut_lower"}),
    ("halved", {"nr:torso": "halved", "nr:arm_l": "wounded"}),
    ("cracked", {"nr:head": "cracked", "nr:torso": "gutted", "nr:arm_r": "broken"}),
    ("jawless", {"nr:head": "jawless", "nr:torso": "slashed"}),
]


def _selftest(out_dir: str, render: bool = True) -> int:
    import json
    import nr_common  # type: ignore  # 1.16.0 の書き出し（DESIGN §13）
    os.makedirs(out_dir, exist_ok=True)
    errors = []
    results = {}
    for name, build in SAMPLE_BUILDS.items():
        model = new_model(f"rigtest_{name}")
        rig = ZombieRig(model, build)
        model.pack(size=(512, 512))
        names = [b.name for b in model.bones]
        # 名前・親・重複
        if len(names) != len(set(names)):
            errors.append(f"{name}: duplicate bones")
        bmap = {b.name: b for b in model.bones}
        for n, p in SKELETON:
            if n not in bmap:
                errors.append(f"{name}: missing bone {n}")
            elif bmap[n].parent != p:
                errors.append(f"{name}: {n} parent {bmap[n].parent} != {p}")
        # ロケータ
        locs = {k for b in model.bones for k in getattr(b, "locators", {})}
        for k in REQUIRED_LOCATORS:
            if k not in locs:
                errors.append(f"{name}: missing locator {k}")
        # スタイル
        for c in model.all_cubes():
            if c.style not in BODY_STYLES:
                errors.append(f"{name}: unknown style {c.style}")
        # UV がアトラスの中
        used = 0
        for c in model.all_cubes():
            for (u, v, du, dv) in c.rects.values():
                if u < 0 or v < 0 or u + du > model.tex_w or v + dv > model.tex_h:
                    errors.append(f"{name}: uv out of atlas")
            w_, h_ = c.uv_extent()
            used += w_ * h_
        # 可視性: Python 評価と生成した Molang 文字列の評価が一致するか
        rules = dict(visibility_rules(model))
        for label, st in PREVIEW_STATES + [("all_cut", {"nr:arm_r": "cut_lower",
                                                         "nr:leg_l": "cut_upper",
                                                         "nr:head": "crushed",
                                                         "nr:armor": 0})]:
            vis = visible_bones(model, st)
            for bname in bmap:
                expr = rules.get(bname)
                mv = True if expr is None else molang_eval(expr, st)
                if mv != (bname in vis):
                    errors.append(f"{name}/{label}: molang mismatch on {bname}")
        # 断面ボーンは既定で隠れている
        vis0 = visible_bones(model, {})
        for g in GORE_BONES:
            if g in vis0:
                errors.append(f"{name}: gore bone {g} visible by default")
        # gib
        gib = extract_gibs(model, f"rigtest_{name}")
        gnames = [b.name for b in gib.bones]
        for p in GIB_TYPE_PARTS:
            if p not in gnames:
                errors.append(f"{name}: gib missing {p}")
        for p, info in gib.gib_info.items():
            if info["cubes"] == 0:
                errors.append(f"{name}: gib {p} empty")
        # gib のキューブが元の形（部分木の根から見た形）と UV をそのまま保っているか
        Wm = bone_world(model)
        all_rects = {rect_key(r) for c in model.all_cubes() for r in c.rects.values()}
        worst = 0.0
        for gb in gib.bones:
            info = gib.gib_info[gb.name]
            if not info["cubes"]:
                continue
            Winv = np.linalg.inv(Wm[info["root"]])
            cen = np.array(info["centroid"])
            for gc in gb.cubes:
                if any(rect_key(r) not in all_rects for r in gc.rects.values()):
                    errors.append(f"{name}: gib {gb.name} cube has foreign UV")
                    break
                src = getattr(gc, "nr_src", None)
                if src is None:
                    continue
                bn, oc = src
                if gc.rects != oc.rects:
                    errors.append(f"{name}: gib {gb.name} cube UV changed")
                A = (Winv @ Wm[bn] @ cube_matrix(oc) @ cube_corners(oc).T).T[:, :3]
                B = (cube_matrix(gc) @ cube_corners(gc).T).T[:, :3] + cen
                worst = max(worst, float(np.abs(A - B).max()))
        if worst > 0.02:
            errors.append(f"{name}: gib geometry drift {worst:.4f}")
        gib_drift = worst
        hb = hitboxes(model)
        for part in HIT_PARTS:
            if len(hb["stand"][part]) != (1 if part == "head" else 2):
                errors.append(f"{name}: hitbox {part} has {len(hb['stand'][part])} boxes")
        cnt = rig.counts()
        tex, painter = _paint(model, build, 7)
        geo_path = os.path.join(out_dir, f"{name}.geo.json")
        tex_path = os.path.join(out_dir, f"{name}.png")
        nr_common.write_geometry(geo_path, model)
        tex.save(tex_path)
        gib_path = os.path.join(out_dir, f"{name}.gib.geo.json")
        nr_common.write_geometry(gib_path, gib)
        for pth in (geo_path, gib_path):
            fv = nr_common.load_json(pth).get("format_version")
            if fv != nr_common.GEOMETRY_FORMAT:
                errors.append(f"{name}: {os.path.basename(pth)} format_version {fv}")
        with open(os.path.join(out_dir, f"{name}.hitboxes.json"), "w", encoding="utf-8") as fh:
            json.dump(hb, fh, indent=1)
        results[name] = dict(model=model, rig=rig, geo=geo_path, tex=tex_path, gib=gib_path,
                             gib_model=gib)
        print(f"{name:10s} bones={len(model.bones):3d} cubes body={cnt['body']:3d} "
              f"gore={cnt['gore']:3d} total={cnt['total']:3d} atlas={model.tex_w}x{model.tex_h} "
              f"uv_used={used / (model.tex_w * model.tex_h) * 100:4.1f}% shelf_h="
              f"{model.used_height} height={hb['height']:.2f}b gib={len(gib.all_cubes())} "
              f"drift={gib_drift:.4f} "
              f"paint={painter}")
    # 回転したボーンを含む部分木（肘・手首を曲げ、帽子の子ボーンを斜めに付ける）の gib
    m2 = new_model("rigtest_bent")
    rig2 = ZombieRig(m2, SAMPLE_BUILDS["average"])
    rig2.b("forearm_r").rotation = [-35.0, 12.0, 6.0]
    rig2.b("hand_r").rotation = [14.0, -22.0, 18.0]
    hat = m2.bone("hat", (0, rig2.L.t, 0), "head", [8.0, 15.0, -6.0])
    hat.add(Cube((-2, rig2.L.t - 0.6, -2.2), (4, 1.2, 4.4), "hair", uv_scale=4,
                 rotation=[0, 0, 10], pivot=[0, rig2.L.t, 0]))
    m2.pack(size=(512, 512))
    g2 = extract_gibs(m2, "rigtest_bent")
    W2 = bone_world(m2)
    worst = 0.0
    hat_in = False
    for gb in g2.bones:
        info = g2.gib_info[gb.name]
        Winv = np.linalg.inv(W2[info["root"]])
        cen = np.array(info["centroid"])
        for gc in gb.cubes:
            src = getattr(gc, "nr_src", None)
            if src is None:
                continue
            bn, oc = src
            hat_in = hat_in or (bn == "hat" and gb.name == "p_head")
            A = (Winv @ W2[bn] @ cube_matrix(oc) @ cube_corners(oc).T).T[:, :3]
            B = (cube_matrix(gc) @ cube_corners(gc).T).T[:, :3] + cen
            worst = max(worst, float(np.abs(A - B).max()))
    print(f"bent gib drift={worst:.4f} hat_in_head_gib={hat_in}")
    if worst > 0.02:
        errors.append(f"bent gib geometry drift {worst:.4f}")
    if not hat_in:
        errors.append("outfit child bone 'hat' missing from p_head")
    vr = dict(visibility_rules(m2))
    if vr.get("hat") != vr.get("head"):
        errors.append("hat visibility does not inherit head's rule")
    gen = build_generic_gibs()
    for p in GIB_GENERIC_PARTS:
        if p not in [b.name for b in gen.bones]:
            errors.append(f"generic gib missing {p}")
    print(f"generic gib: {gen.stats()} painted={'yes' if gen.texture is not None else 'no'}")
    nr_common.write_geometry(os.path.join(out_dir, "generic.gib.geo.json"), gen)
    if gen.texture is None:
        gen.texture = _fallback_paint(gen, 3)
    gen.texture.save(os.path.join(out_dir, "generic.gib.png"))
    # 共通 render controller 用に全員の規則が合わせられるか
    merge_visibility(*[visibility_rules(r["model"]) for r in results.values()])
    for e in errors[:40]:
        print("ERROR", e)
    print(f"{len(errors)} errors")
    if render:
        _render_previews(results, out_dir)
    return 1 if errors else 0


def _hidden_for(model: Model, state: Optional[dict] = None, extra_hide: Iterable[str] = (),
                extra_show: Iterable[str] = ()) -> List[str]:
    """状態で見えないボーンの一覧（nr_preview の hidden に渡す。hide_mode="exact" で使う）。"""
    vis = (visible_bones(model, state) | set(extra_show)) - set(extra_hide)
    return [b.name for b in model.bones if b.name not in vis]


def _render_previews(results: dict, out_dir: str) -> None:
    """確認画像（nr_preview: 統合版と同じ面の対応で描く）。体の状態 / 顔 / 手 / gib。"""
    import nr_preview as V  # type: ignore
    tw, th = 300, 420
    for name, r in results.items():
        model, L = r["model"], r["rig"].L
        tex = V.load_texture(r["tex"])
        hb_h = hitboxes(model)["height"] * 16
        full = dict(target=(0, hb_h / 2, 0), scale=th * 0.86 / (hb_h * 1.05))
        tiles = []
        for label, st in PREVIEW_STATES:
            hide = _hidden_for(model, st)
            for yaw in (30, 200):
                cam = V.Camera(yaw=yaw, pitch=8, **full)
                tiles.append((f"{label} y{yaw}", V.render(model, tex, camera=cam, size=(tw, th),
                                                          hidden=hide, hide_mode="exact")))
        V.contact_sheet(tiles, cols=6).save(os.path.join(out_dir, f"preview_{name}.png"))
        # 顔のアップ（顎を開いた姿・横・顎なし・割れた頭）
        head = dict(target=(0, L.chin + L.H * 0.5, -0.2 * L.head_d), scale=th * 0.8 / (L.H * 1.6))
        hide = _hidden_for(model, {})
        jaw_open = {"jaw": {"rotation": [22, 0, 0]}}
        faces = []
        for lab, yaw, pitch, pose, st in (("front", 0, 4, None, {}), ("jaw open", 30, 4, jaw_open, {}),
                                          ("side", 90, 4, None, {}), ("wounded", 0, 4, None, {"nr:head": "wounded"}),
                                          ("jawless", 25, 4, None, {"nr:head": "jawless"}),
                                          ("cracked", 25, 25, None, {"nr:head": "cracked"})):
            cam = V.Camera(yaw=yaw, pitch=pitch, **head)
            faces.append((lab, V.render(model, tex, camera=cam, size=(tw, th), pose=pose,
                                        hidden=_hidden_for(model, st), hide_mode="exact")))
        V.contact_sheet(faces, cols=6).save(os.path.join(out_dir, f"face_{name}.png"))
        # 手のアップ
        hc = (-L.arm_x, L.wrist_y - L.palm_l, 0)
        hands = [(f"y{yaw}", V.render(model, tex, camera=V.Camera(yaw=yaw, pitch=5, target=hc,
                                                                  scale=th * 0.8 / (L.hand_l * 2.2)),
                                      size=(tw, th), hidden=hide, hide_mode="exact"))
                 for yaw in (0, 90, 180, 270)]
        V.contact_sheet(hands, cols=4).save(os.path.join(out_dir, f"hand_{name}.png"))
        # gib（部位ごと。同じテクスチャ）
        gtiles = []
        for p_ in GIB_TYPE_PARTS:
            hide_g = [q for q in GIB_TYPE_PARTS if q != p_]
            gtiles.append((p_, V.render(r["gib"], tex, view=(35, 20), size=(tw, tw), hidden=hide_g,
                                        hide_mode="exact")))
        V.contact_sheet(gtiles, cols=6).save(os.path.join(out_dir, f"gib_{name}.png"))
        print("wrote previews for", name)


# 統合の確認画像（foundation_check.png）: 2 体 × 6 状態（全身と見どころのアップ）＋ gib
FOUNDATION_BODIES = (
    ("average / grey_green / clouded",
     dict(SAMPLE_BUILDS["average"], eyes="clouded", decay=2, mouth="snarl"), "grey_green"),
    ("brute / jaundiced / glowing_yellow",
     dict(SAMPLE_BUILDS["brute"], eyes="glowing_yellow", decay=3, mouth="gaping"), "jaundiced"),
)
# (ラベル, 状態, さらに隠すボーン, アップの見どころ)
FOUNDATION_STATES = (
    ("intact", {}, (), "face"),
    ("arm_r cut_upper + head severed", {"nr:arm_r": "cut_upper", "nr:head": "severed"}, (), "neck"),
    ("legs cut_lower", {"nr:leg_r": "cut_lower", "nr:leg_l": "cut_lower"}, (), "knees"),
    ("torso halved", {"nr:torso": "halved"}, (), "waist"),
    ("head cracked + jawless", {"nr:head": "cracked"}, ("jaw",), "head"),     # 2 つの見た目を重ねる
    ("arm_l broken + gutted", {"nr:arm_l": "broken", "nr:torso": "gutted"}, (), "belly"),
)


def foundation_check(path: str, seed: int = 7) -> str:
    """painter と rig の統合確認画像（DESIGN の断面: 皮膚の縁・脂肪の輪・赤い筋肉・白い骨、腸）。"""
    import nr_paint  # type: ignore
    import nr_preview as V  # type: ignore
    from PIL import Image
    tw, th = 236, 320
    sheets = []
    first = None
    for title, build, skin in FOUNDATION_BODIES:
        key = "fc_" + title.split(" ")[0]
        model = new_model(key)
        rig = ZombieRig(model, build)
        model.pack(size=(512, 512))
        styles = nr_paint.zombie_styles(skin, build["decay"], build["eyes"])
        tex = nr_paint.paint_model(model, styles, seed)
        L = rig.L
        hb_h = hitboxes(model)["height"] * 16
        full = dict(target=(0, hb_h / 2, 0), scale=th * 0.88 / (hb_h * 1.04))
        near = {
            "face": dict(view=(14, 4), target=(0, L.chin + 0.5 * L.H, -0.3 * L.head_d), span=1.5 * L.H),
            "neck": dict(view=(-35, 38), target=(0, L.shoulder_y, 0), span=0.42 * L.t),
            "knees": dict(view=(24, -14), target=(0, L.knee_y, 0), span=0.38 * L.t),
            "waist": dict(view=(25, -42), target=(0, L.abdomen_bot, 0), span=0.42 * L.t),
            "head": dict(view=(28, 22), target=(0, L.chin + 0.6 * L.H, 0), span=1.9 * L.H),
            "belly": dict(view=(-38, 6), target=(0.3 * L.arm_x, (L.abdomen_bot + L.chest_bot) / 2 - 0.05 * L.t, 0),
                          span=0.55 * L.t),
        }
        tiles, details = [], []
        for label, st, extra, focus in FOUNDATION_STATES:
            hide = _hidden_for(model, st, extra_hide=extra)
            cam = V.Camera(yaw=30, pitch=10, **full)
            tiles.append((label, V.render(model, tex, camera=cam, size=(tw, th), hidden=hide,
                                          hide_mode="exact")))
            nz = near[focus]
            cam = V.Camera(yaw=nz["view"][0], pitch=nz["view"][1], target=nz["target"],
                           scale=th * 0.8 / nz["span"])
            details.append((f"{focus} (yaw {nz['view'][0]}, pitch {nz['view'][1]})",
                            V.render(model, tex, camera=cam, size=(tw, th), hidden=hide,
                                     hide_mode="exact")))
        sheets.append(V.contact_sheet(tiles + details, cols=6, title=title))
        if first is None:
            first = (model, tex, key)
    # gib: 1 体目の部位（同じアトラス）＋汎用の肉片
    model, tex, key = first
    gib = extract_gibs(model, key)
    gtiles = []
    for p_ in GIB_TYPE_PARTS:
        hide_g = [q for q in GIB_TYPE_PARTS if q != p_]
        gtiles.append((p_, V.render(gib, tex, view=(35, 22), size=(170, 170), hidden=hide_g,
                                    hide_mode="exact")))
        if p_ in ("p_head", "p_lower"):
            # 断面の向きの確認（首は背骨が後ろ、胴は腰椎が後ろ）: 切り口の正面から
            pitch = -70 if p_ == "p_head" else 70
            gtiles.append((p_ + " cut", V.render(gib, tex, view=(0, pitch), size=(170, 170),
                                                 hidden=hide_g, hide_mode="exact")))
    gen = build_generic_gibs()
    gtex = gen.texture if gen.texture is not None else _fallback_paint(gen, 3)
    for p_ in GIB_GENERIC_PARTS:
        hide_g = [q for q in GIB_GENERIC_PARTS if q != p_]
        gtiles.append((p_, V.render(gen, gtex, view=(35, 22), size=(170, 170), hidden=hide_g,
                                    hide_mode="exact")))
    sheets.append(V.contact_sheet(gtiles, cols=9, title="gib parts (body 1) + generic"))
    W_ = max(sh.size[0] for sh in sheets)
    H_ = sum(sh.size[1] for sh in sheets)
    out = Image.new("RGB", (W_, H_), (16, 17, 21))
    y = 0
    for sh in sheets:
        out.paste(sh, (0, y))
        y += sh.size[1]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    out.save(path)
    return path


if __name__ == "__main__":
    _base = os.environ.get("NR_SCRATCH", os.path.join(os.path.dirname(TOOLS), "build_preview",
                                                      "nightrunner"))
    if "--foundation" in sys.argv:
        print("wrote", foundation_check(os.path.join(_base, "foundation_check.png")))
        sys.exit(0)
    rc = _selftest(os.path.join(_base, "rig"), render="--no-render" not in sys.argv)
    if "--no-render" not in sys.argv:
        print("wrote", foundation_check(os.path.join(_base, "foundation_check.png")))
    sys.exit(rc)
