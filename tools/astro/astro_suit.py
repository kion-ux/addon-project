# -*- coding: utf-8 -*-
"""アストロ・ナノギア — スーツの骨格・7 頭身の解剖（A）・内部フレーム（frame7）・細かい部品・検査の計測。

スーツは頭スロットのアタッチャブルとして着る全身モデル。トップレベルのボーンをプレイヤーと同名・同ピボットに
すると、統合版はそのボーンをプレイヤーの同名ボーンに重ねて動かす（kaiju8 の no8_form と同じ仕組み）。

    body (0,24,0)  head (0,24,0)  rightArm (-5,22,0)  leftArm (5,22,0)
    rightLeg (-1.9,12,0)  leftLeg (1.9,12,0)

v1.1 から **7 頭身の全身像**（DESIGN §4.3b）。変身中はスクリプトがプレイヤーを透明化するので、肌は覆わなくてよい。
寸法は `A`（解剖の目安。右側 = -X の値）を使って置く:

    from astro_suit import A, Suit, mirror_x, piston, cable, rivets, joint_drum ...
    def build_suit(s: Suit):
        f = s.frame7()                                    # 暗い機械の骨格（inner 群）。これだけで 7 頭身のロボ
        chest = s.part("torso", "chest", "body")          # → ボーン torso_chest
        rbox(chest, (0, A.CHEST_Y, A.CHEST_FRONT - 0.3), (9.6, 5.0, 0.8), "plate", rot=(6, 0, 0))
        g = s.part("arms", "gauntlet_r", "rightArm")      # 右だけ書く → arms_gauntlet_l が自動で出来る
        piston(g, (A.ELBOW[0], A.ELBOW_Y + 1.2, 1.3), (A.FIST[0], A.WRIST_Y + 0.3, 1.1))

キューブは必ず「部位ボーン」（`<群>_<名前>`）に入れる。群は組み上がりの順番（astro_data.ASSEMBLE_ORDER）:
    inner boots legs waist torso back arms shoulders helmet visor extra
動かす部品はさらに子ボーン `fx_thrust_*`（空中で伸びる炎）/ `fx_glow_*`（脈動・バイザーの閃光）/
`fx_spin_*`（回転体）に分ける。角・鶏冠・アンテナなどの飾りは `s.part(..., ornament=True)`（または名前に
crest / horn / antenna / plume / halo / ornament を含める）にすると、背丈・頭の計測から外れる。

左右: 右側（-X）だけ作り、名前の末尾を `_r` にしておくと、Suit.mirror_all() が左（`_l`）を作る
（build() が自動で呼ぶ）。片側だけの部品（ルナ・ビット等）は `_r` を付けない。

旧版（v1.0, 4 頭身）の `inner_suit()`・`coverage()`・`ARM_X`/`LEG_X`/`HAND_Y` は互換のために残してある（新しい
スーツでは使わない）。
"""
from __future__ import annotations

import copy
import importlib
import math
import os
import sys
from typing import Dict, Iterable, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import astro_common as AC  # noqa: E402
from astro_common import NS, Bone, Cube, Model, cbox, cube_matrix  # noqa: E402
# 形の道具（planets/<key>/suit.py が astro_suit からまとめて import できるように再輸出）
from astro_common import (bevel, beam, chamfer, line_on, octa, plate, polyline, rbox,  # noqa: E402,F401
                          ring, stick, surface, taper, tri_fan, mat_cube, frame_to, line3,
                          rod, ball, piston, cable, rivets, vents, layered_plate, joint_drum,
                          finger_chain, greebles, sensor, mx, MIN_PART)
from astro_data import PLANETS  # noqa: E402
from hd_space import bone_local  # noqa: E402

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
# スリム（Alex）の腕: 幅 3・pivot y 21.5。肌の外側は y 11.25..23.75 まで下がる（DESIGN §4.5 の調査）
SKIN_SLIM = {
    "rightArm": ((-7, 11.5, -2), (3, 12, 4)),
    "leftArm": ((4, 11.5, -2), (3, 12, 4)),
}
LAYER = {"head": 0.5, "body": 0.25, "rightArm": 0.25, "leftArm": 0.25,
         "rightLeg": 0.25, "leftLeg": 0.25}
MIRROR_TOP = {"rightArm": "leftArm", "leftArm": "rightArm", "rightLeg": "leftLeg",
              "leftLeg": "rightLeg", "body": "body", "head": "head"}

# プレイヤーのボーン名（大文字小文字を区別せず一致すると、そのボーンに付いて動いてしまう）。
# トップレベルの 6 つ以外にこの名前を付けてはいけない
RESERVED = {n.lower() for n in (
    "root", "waist", "body", "head", "hat", "cape", "jacket", "rightArm", "leftArm", "rightLeg",
    "leftLeg", "rightItem", "leftItem", "helmet", "bodyArmor", "belt", "leftSleeve",
    "rightSleeve", "leftPants", "rightPants", "rightSock", "leftSock", "rightBoot", "leftBoot",
    "leftLegging", "rightLegging", "leftArmArmor", "rightArmArmor")}

GROUPS = ("inner", "boots", "legs", "waist", "torso", "back", "arms", "shoulders",
          "helmet", "visor", "extra")
FX_KINDS = ("thrust", "glow", "spin")
# 名前にこれを含むボーン（とその子）は飾り扱い（背丈・頭の計測に入れない）
ORNAMENT_TAGS = ("crest", "horn", "antenna", "plume", "halo", "ornament")

# 右側の基準（左は X を反転）
R, L = -1, 1                 # 右 = -X
# v1.0（4 頭身）の定数。互換のために残す。新しいスーツは A.* を使う
ARM_X = -6.0                 # 右腕の中心の X
LEG_X = -1.9                 # 右脚の中心の X（v1.0）
HAND_Y = 13.2                # 拳の中心の高さ（腕を下ろした時）


# ===========================================================================
#  7 頭身の解剖（DESIGN §4.3b の表）。y は地面から、正面 -Z、右手 -X（点・X は右側の値）
# ===========================================================================
class A:
    """7 頭身の目安の寸法。`from astro_suit import A` → `A.KNEE_Y` のように使う。
    点（タプル）は右側。左は X を反転（右だけ作れば鏡映は自動）。幅 *_W は X 方向の全幅、奥行き *_D は Z。"""
    H = 32.0                         # 頭頂（角・鶏冠を除く）
    UNIT = H / 7.0                   # 1 頭身 ≈ 4.571
    GROUND = 0.0
    # --- 頭と首（head ボーン。ピボット (0,24,0) で曲がる） ---
    HEAD_TOP, HEAD_BOT = 32.0, 27.4
    HEAD_Y = 29.7                    # 頭の中心の高さ
    HEAD_Z = -0.25                   # 頭の中心の奥行き（首より少し前）
    HEAD_W, HEAD_D = 4.6, 5.0        # 兜の幅 4.2〜5.0（検査は 5.4 以下）・奥行き 4.6〜5.4
    EYE_Y = 29.5                     # バイザー（目）の高さ
    CHIN_Y = 27.4
    FACE_Z = HEAD_Z - HEAD_D / 2     # 顔の前面 ≈ -2.75
    NECK_BOT, NECK_TOP = 25.6, 27.8
    NECK_W = 2.4
    NECK_Z = 0.15
    # --- 胴（body ボーン。ピボット (0,24,0)） ---
    SHOULDER_Y = 26.0                # 肩の線
    DELTOID_X = -7.5                 # 三角筋（肩当て）の外側の目安（-7.0〜-8.0）
    CHEST_TOP, CHEST_BOT = 26.2, 20.5
    CHEST_Y = 23.4
    CHEST_W, CHEST_D = 9.8, 5.2      # 9.2〜10.5 / 4.8〜5.6（逆三角形: 上が広い）
    CHEST_FRONT, CHEST_BACK = -2.6, 2.6
    WAIST_TOP, WAIST_BOT = 20.5, 16.8
    WAIST_Y = 18.6
    WAIST_W, WAIST_D = 6.0, 3.9      # 5.6〜6.6 / 3.6〜4.2（胸の幅は腰の 1.45 倍以上）
    WAIST_Z = 0.15
    PELVIS_TOP, PELVIS_BOT = 17.0, 13.6
    PELVIS_Y = 15.3
    PELVIS_W, PELVIS_D = 7.4, 4.4
    CROTCH_Y = 13.6
    BACKPACK = (0.0, 22.2, 3.4)      # 背中の中心（バックパック・スラスターの付け根の目安）
    # --- 脚（rightLeg。ピボット (-1.9,12,0)） ---
    LEG_X = -2.15                    # 脚の軸の X（腿・膝・脛・足の中心）
    HIP = (-2.2, 14.6, 0.0)          # 股関節の球（骨盤・草摺で隠す。ピボットより上）
    HIP_Y = 14.6
    THIGH_TOP, THIGH_BOT = 15.0, 9.0
    THIGH_W = 3.3                    # 3.0〜3.6
    KNEE = (-2.15, 8.5, -0.05)
    KNEE_Y = 8.5
    KNEE_TOP, KNEE_BOT = 9.4, 7.6
    SHIN_TOP, SHIN_BOT = 7.8, 1.8
    SHIN_W = 2.9                     # 2.6〜3.2（ふくらはぎで膨らむ）
    CALF_Y = 5.8
    ANKLE = (-2.15, 2.1, 0.3)
    ANKLE_Y = 2.1
    FOOT_TOP = 1.8
    TOE_Z, HEEL_Z = -4.0, 1.6        # 足の長さ 5.5〜6.5
    FOOT_W = 2.7
    # --- 腕（rightArm。ピボット (-5,22,0)） ---
    SHOULDER = (-6.4, 24.4, 0.0)     # 肩関節の球（肩当てで隠す。ピボットより上）
    UPPER_ARM_TOP, UPPER_ARM_BOT = 24.0, 19.0
    UPPER_ARM_W = 2.6                # 2.4〜2.8
    UPPER_ARM_X = -6.3
    ELBOW = (-6.2, 18.5, 0.1)
    ELBOW_Y = 18.5
    ELBOW_TOP, ELBOW_BOT = 19.2, 17.8
    FOREARM_TOP, FOREARM_BOT = 18.2, 14.6
    FOREARM_W = 2.9                  # 2.6〜3.2（籠手）
    FOREARM_X = -6.1
    WRIST = (-6.05, 14.75, 0.0)
    WRIST_Y = 14.75
    FIST = (-6.0, 13.0, 0.0)         # 拳の中心
    FIST_TOP, FIST_BOT = 14.6, 11.4
    FIST_W, FIST_D = 2.6, 2.8
    GRIP = (-6.0, 13.2, 0.0)         # 武器の握りの点（hd_space.HAND_R）。拳はこれを包む

    @staticmethod
    def left(p):
        """右側の点を左側へ（X を反転）。"""
        return (-p[0], p[1], p[2])

    @classmethod
    def table(cls) -> Dict[str, object]:
        return {k: v for k, v in vars(cls).items() if k.isupper()}


# 部位ボーンの既定の pivot（右側。「生えてくる根元」= 組み上がりでポップする中心）。None は親の pivot
DEFAULT_PIVOT = {
    ("boots", "leg"): A.ANKLE,
    ("legs", "leg"): A.KNEE,
    ("waist", "body"): (0.0, A.PELVIS_TOP, 0.0),
    ("torso", "body"): (0.0, A.CHEST_Y - 1.0, 0.0),
    ("back", "body"): (0.0, A.BACKPACK[1], A.CHEST_BACK),
    ("arms", "arm"): A.ELBOW,
    ("shoulders", "arm"): A.SHOULDER,
    ("helmet", "head"): (0.0, A.NECK_TOP, 0.0),
    ("visor", "head"): (0.0, A.EYE_Y, A.FACE_Z),
    ("inner", "head"): (0.0, A.NECK_TOP, 0.0),
    ("inner", "body"): (0.0, A.WAIST_Y, 0.0),
    ("inner", "arm"): A.ELBOW,
    ("inner", "leg"): A.KNEE,
}

# 被覆検査（v1.0）で既定で見ない所
DEFAULT_ALLOW = [
    ("rightLeg", "up"), ("leftLeg", "up"),       # 脚の上面は胴の中
]

# frame7 の塗りの役割 → 既定のスタイル名（astro_paint.suit_styles にある名前）
FRAME7_STYLES = {
    "suit": "inner",        # 筋肉にあたる芯（六角メッシュの黒いボディスーツ）
    "metal": "frame",       # 骨・節・支柱（溝のある暗い金属）
    "band": "frame_lt",     # 手足の節の輪・肋骨（少し明るい金属。暗い芯との境目を見せる）
    "dark": "dark",         # 隙間・指の関節・軸受け（無地の暗い金属）
    "joint": "chrome",      # 球関節・ドラムの蓋・ピストンのロッド（鏡面）
    "glow": "glow_soft",    # センサーの灯り（半発光）
}


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
        self.inner_box: Dict[str, tuple] = {}     # inner_suit()（v1.0）の殻の (lo, hi)
        self.allow: List = list(DEFAULT_ALLOW)
        self.ornaments: set = set()               # 計測から外す飾りのボーン（部分木ごと）
        self.frame_roots: List[str] = []          # frame7 が作った右側のボーン（MIRROR=False でも鏡映）
        self.frame = None

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

    def part(self, group: str, name: str, parent="body", pivot=None, rotation=None,
             ornament: bool = False) -> Bone:
        """部位ボーン `<group>_<name>` を作る。parent はトップレベル名・部位ボーン名・Bone。
        pivot 省略時は群と親から既定（DEFAULT_PIVOT。左側の親なら X を反転）。
        ornament=True で飾り（角・鶏冠・アンテナ）として背丈・頭の計測から外す。"""
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
        b = self.m.bone(full, pivot, parent=pname, rotation=rotation)
        if ornament:
            self.ornaments.add(full)
        return b

    def fx(self, kind: str, name: str, parent, pivot=None, rotation=None,
           ornament: bool = False) -> Bone:
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
        b = self.m.bone(full, pivot or self.bone(pname).pivot, parent=pname, rotation=rotation)
        if ornament:
            self.ornaments.add(full)
        return b

    def ornament(self, bone) -> Bone:
        """既にあるボーン（とその子）を飾りにする（背丈・頭の計測から外す）。"""
        b = bone if isinstance(bone, Bone) else self.bone(bone)
        self.ornaments.add(b.name)
        return b

    def is_ornament(self, name: str) -> bool:
        chain = [name]
        b = self.bone(name)
        while b.parent:
            chain.append(b.parent)
            b = self.bone(b.parent)
        for n in chain:
            if n in self.ornaments or any(t in n.lower() for t in ORNAMENT_TAGS):
                return True
        return False

    # ==================================================================
    #  7 頭身の内部フレーム
    # ==================================================================
    def frame7(self, style=None, bulk: float = 1.0, skip: Iterable[str] = (),
               fingers: bool = True) -> "Frame":
        """7 頭身の暗い機械の骨格（群 inner。変身で最初に現れる）。これだけで「装甲を外したロボ」に見える:
        兜の芯と首（喉の輪・腱・首の後ろのピストン）、胸郭（肋骨・鎖骨・胸筋・胸骨・灯り）、背骨（椎骨と 2 本のケーブル）、
        細い腰（腹の節・脇の油圧シリンダー）、骨盤（股の箱・股関節の受け）、肩と股の球関節、肘・膝・足首・手首の八角の
        関節ドラム、節のある二の腕・前腕・腿・脛（芯 + 支柱 + 輪）、膝裏と足首のピストン、指 4 本（3 節）+ 親指の拳
        （武器の握りの点 A.GRIP を包む）、つま先の板の付いた足。右側は `_r` で作り、左は鏡映される。

        style: 塗りの役割の上書き。文字列ならボディスーツ（"suit" の役割）の名前、辞書なら
               {"suit","metal","band","dark","joint","glow"} の一部（FRAME7_STYLES）。
        bulk:  手足と胸の太さの倍率（0.85〜1.2。細身の水星 0.9、巨体の木星 1.15 など）。
        skip:  作らない部分の名前（"head" "neck" "chest" "spine" "waist" "pelvis" "shoulder" "upper_arm"
               "elbow" "forearm" "wrist" "hand" "hip" "thigh" "knee" "shin" "ankle" "foot" "pistons" "cables"）。
               装甲で完全に隠れる所を省くとキューブとテクスチャの節約になる（例: 兜で覆うなら "head"）。
        fingers: False で指を省く（籠手で拳を作る場合）。
        戻り値: Frame（{"head","neck","chest","spine","waist","pelvis","shoulder_r","upper_arm_r","forearm_r",
               "hand_r","thigh_r","knee_r","shin_r","foot_r": Bone} の辞書。装甲の親にしてもよい）。"""
        return build_frame7(self, style, bulk, set(skip), fingers)

    # ---- インナー（v1.0。肌を確実に覆う。新しいスーツでは使わない） ----------
    def inner_suit(self, style: str = "inner", gap: float = 0.45, hood: bool = True,
                   uv_scale: Optional[float] = None, head_style: Optional[str] = None):
        """（v1.0 の互換）肌の 6 部位に、外側レイヤー + gap の殻を張る（群 inner）。
        7 頭身のスーツでは frame7() を使うこと（肌は透明化で隠れる）。戻り値: {部位: Bone}"""
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
            lo = [o[i] - inf for i in range(3)]
            hi = [o[i] + sz[i] + inf for i in range(3)]
            if top in ("rightArm", "leftArm"):
                lo[1] = min(lo[1], 11.25 - gap)        # スリムの腕は 0.5 低くまで来る
            c = [(lo[i] + hi[i]) / 2 for i in range(3)]
            size = [hi[i] - lo[i] for i in range(3)]
            if top in ("leftLeg", "leftArm"):
                size[2] += 0.1
            self.inner_box[top] = (tuple(round(c[i] - size[i] / 2, 3) for i in range(3)),
                                   tuple(round(c[i] + size[i] / 2, 3) for i in range(3)))
            kw = {"uv_scale": uv_scale} if uv_scale else {}
            cbox(b, c, size, head_style if (top == "head" and head_style) else style, **kw)
            out[top] = b
        return out

    # ---- 左右の鏡映 -----------------------------------------------------
    def mirror_all(self, style_map: Optional[Dict[str, str]] = None,
                   only: Optional[Iterable[str]] = None) -> List[str]:
        """`_r` で終わる部位ボーンの部分木を左（`_l`）へ写す。既に `_l` があるものは飛ばす。
        X を反転し、回転は (rx, -ry, -rz)、デカールの east/west を入れ替える。
        only を渡すと、その名前の根だけを写す（MIRROR=False のスーツでも frame7 は左右対称に）。"""
        smap = dict(self.mirror_styles, **(style_map or {}))
        names = {b.name for b in self.m.bones}
        made = []
        roots = [b for b in self.m.bones
                 if b.name.endswith("_r") and not (b.parent or "").endswith("_r")
                 and b.name[:-2] + "_l" not in names]
        if only is not None:
            only = set(only)
            roots = [b for b in roots if b.name in only]
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
                if b.name in self.ornaments:
                    self.ornaments.add(nb.name)
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


class Frame(dict):
    """frame7() の戻り値: 役割名 → Bone（右側は "_r"）。s.frame にも入る。"""


# ---------------------------------------------------------------------------
#  frame7 の中身
# ---------------------------------------------------------------------------
def build_frame7(s: Suit, style=None, bulk=1.0, skip=frozenset(), fingers=True) -> Frame:
    st = dict(FRAME7_STYLES)
    if isinstance(style, str):
        st["suit"] = style
    elif isinstance(style, dict):
        unknown = set(style) - set(st)
        if unknown:
            raise ValueError(f"frame7 style roles are {sorted(st)}, not {sorted(unknown)}")
        st.update(style)
    SU, ME, DK, JO, GL = st["suit"], st["metal"], st["dark"], st["joint"], st["glow"]
    BA = st["band"]
    k = max(0.8, min(1.25, float(bulk)))
    F = Frame()
    want = lambda n: n not in skip  # noqa: E731
    pist = want("pistons")
    cab = want("cables")
    LX = A.LEG_X

    def part(name, parent, pivot):
        b = s.part("inner", name, parent, pivot=pivot)
        if name.endswith("_r"):
            s.frame_roots.append(b.name)
        return b

    # ------------------------------------------------------------ 頭と首
    if want("head"):
        h = part("head", "head", (0.0, A.NECK_TOP, 0.0))
        F["head"] = h
        hz = A.HEAD_Z
        bevel(h, (0, 29.75, hz + 0.1), (3.8, 4.1, 4.2), ME, cut=0.6, axis="z")
        cbox(h, (0, 29.15, hz - 2.08), (2.9, 2.3, 0.3), DK)                       # 顔の板
        cbox(h, (0, 29.6, hz - 2.25), (2.3, 0.3, 0.16), GL)                       # 目の溝
        rbox(h, (0, 28.05, hz - 0.9), (2.5, 0.9, 2.5), ME, rot=(-14, 0, 0))       # 顎
        sensor(h, (-1.98, 29.7, hz + 0.3), 0.36, GL, DK, axis="x", facing=-1)
        sensor(h, (1.98, 29.7, hz + 0.3), 0.36, GL, DK, axis="x", facing=1)
    if want("neck"):
        n = part("neck", "head", (0.0, A.NECK_BOT + 0.8, A.NECK_Z))
        F["neck"] = n
        octa(n, (0, 26.7, A.NECK_Z), 2.2, 2.6, SU, axis="y")
        for y in (25.95, 26.65, 27.35):
            octa(n, (0, y, A.NECK_Z), 2.42, 0.26, BA, axis="y")
        if cab:
            for sx in (-1, 1):
                beam(n, (sx * 0.9, 27.9, -0.55), (sx * 1.35, 25.5, 0.15), 0.3, 0.3, DK)
        if pist:
            piston(n, (0, 28.1, 1.25), (0, 25.3, 1.65), r=0.28, style=ME, rod_style=JO,
                   cap_style=DK)
    # ------------------------------------------------------------ 胸郭
    if want("chest"):
        c = part("chest", "body", (0.0, A.CHEST_Y, 0.0))
        F["chest"] = c
        chamfer(c, (0, 24.85, 0.05), (6.3 * k, 2.7, 4.2), SU, cut=0.75, axis="y")   # 上が広い
        chamfer(c, (0, 22.15, 0.1), (5.0 * k, 2.9, 3.7), SU, cut=0.7, axis="y")
        cbox(c, (0, 23.1, -2.25), (0.95, 4.6, 0.5), ME)                              # 胸骨
        sensor(c, (0, 24.6, -2.53), 0.34, GL, DK)
        for i, y in enumerate((24.9, 23.75, 22.6, 21.5)):                           # 肋骨（籠）
            wx = (4.25 - i * 0.32) * k
            rib = polyline(c, [(-0.45, y, -2.3), (-wx + 0.55, y - 0.2, -2.0),
                                (-wx, y - 0.4, -0.2), (-wx + 0.45, y - 0.5, 1.7)],
                           0.42, 0.48, BA)
            mirror_x(c, rib)
        cl = beam(c, (-0.5, 25.95, -1.5), (-4.6 * k, 25.55, -0.5), 0.5, 0.5, BA)   # 鎖骨
        pec = rbox(c, (-1.95 * k, 24.6, -2.3), (2.6 * k, 1.9, 0.5), ME, rot=(-4, 12, 0))
        sock = octa(c, (-4.15 * k, 24.4, 0.0), 1.9, 0.6, DK, axis="x")             # 肩の受け
        lat = beam(c, (-3.7 * k, 25.4, 1.6), (-3.0 * k, 20.9, 1.35), 0.42, 0.55, ME)
        mirror_x(c, cl, pec, sock, lat)
    if want("spine"):
        sp = part("spine", "body", (0.0, A.WAIST_Y, 2.2))
        F["spine"] = sp
        for i in range(9):
            y = 25.5 - i * 1.17
            z = 2.45 if y > 20.6 else 2.25
            cbox(sp, (0, y, z), (1.0, 0.62, 0.9), ME)
            if i < 8:
                cbox(sp, (0, y - 0.58, z - 0.1), (0.7, 0.5, 0.7), DK)
        if cab:
            cb = cable(sp, [(-0.8, 25.7, 2.3), (-1.0, 21.5, 2.65), (-0.85, 17.4, 2.25),
                            (-0.95, 15.6, 2.0)], 0.28, DK, seg=0.85)
            mirror_x(sp, cb)
    # ------------------------------------------------------------ 腰と骨盤
    if want("waist"):
        w = part("waist", "body", (0.0, A.WAIST_Y, A.WAIST_Z))
        F["waist"] = w
        chamfer(w, (0, 18.75, A.WAIST_Z + 0.05), (4.9, 4.6, 3.5), SU, cut=0.7, axis="y")
        for i, (y, ww) in enumerate(((20.05, 3.5), (19.0, 3.25), (17.95, 3.0))):  # 腹の節
            cbox(w, (0, y, -1.62 + i * 0.04), (ww, 0.82, 0.36), BA)
        cbox(w, (0, 18.7, 1.95), (2.5, 3.4, 0.5), ME)                              # 腰椎の箱
        if pist:
            pw = piston(w, (-2.62, 21.1, -0.05), (-2.42, 16.7, 0.15), r=0.3, style=ME,
                        rod_style=JO, cap_style=DK)
            mirror_x(w, pw)
    if want("pelvis"):
        p = part("pelvis", "body", (0.0, A.PELVIS_Y, 0.0))
        F["pelvis"] = p
        chamfer(p, (0, 15.55, 0.1), (6.4, 2.5, 3.9), ME, cut=0.6, axis="y")
        rbox(p, (0, 14.15, -0.3), (2.0, 1.2, 2.6), ME, rot=(-6, 0, 0))             # 股の箱
        cbox(p, (0, 16.95, 0.15), (6.0, 0.45, 4.1), DK)                             # 腰の帯
        cbox(p, (0, 15.7, -2.08), (0.9, 0.7, 0.2), GL)
        hs = octa(p, (-2.95, 14.75, 0.0), 1.9, 0.5, DK, axis="x")                   # 股関節の受け
        mirror_x(p, hs)
    # ------------------------------------------------------------ 腕
    if want("shoulder"):
        sh = part("shoulder_r", "rightArm", A.SHOULDER)
        F["shoulder_r"] = sh
        ball(sh, A.SHOULDER, 1.22 * k, JO, ME)
        octa(sh, (-5.3, 24.4, 0.0), 1.8, 0.5, DK, axis="x")
    ax = A.UPPER_ARM_X
    if want("upper_arm") or want("elbow"):
        ua = part("upper_arm_r", "rightArm", A.SHOULDER)
        F["upper_arm_r"] = ua
        if want("upper_arm"):
            octa(ua, (ax, 21.45, 0.05), 2.1 * k, 4.3, SU, axis="y")                 # 二の腕の芯
            for y in (22.75, 20.15):
                octa(ua, (ax, y, 0.05), 2.45 * k, 0.3, BA, axis="y")
            beam(ua, (ax, 23.5, -1.08 * k), (ax + 0.05, 19.6, -1.02 * k), 0.6, 0.4, ME)
            beam(ua, (ax - 1.08 * k, 23.2, 0.05), (ax - 1.0 * k, 19.8, 0.05), 0.5, 0.44, ME)
            if pist:
                piston(ua, (ax, 22.9, 1.32 * k), (A.ELBOW[0], 17.3, 1.18 * k), r=0.27,
                       style=ME, rod_style=JO, cap_style=DK)
        if want("elbow"):
            ex = A.ELBOW
            joint_drum(ua, ex, 1.25 * k, 2.55 * k, axis="x", style=ME, cap=JO, hub=DK,
                       glow=GL, caps=(-1,))
            rbox(ua, (ex[0], ex[1] + 0.1, 1.3 * k), (1.9, 1.5, 0.45), ME, rot=(-14, 0, 0))
    fx_ = A.FOREARM_X
    if want("forearm") or want("wrist"):
        fa = part("forearm_r", "rightArm", A.ELBOW)
        F["forearm_r"] = fa
        if want("forearm"):
            taper(fa, (fx_, 18.0, 0.05), (fx_ + 0.06, 14.95, 0.0), 2.35 * k, 1.95 * k, 2, SU)
            for y, ww in ((17.15, 2.62), (15.65, 2.32)):
                octa(fa, (fx_, y, 0.02), ww * k, 0.26, BA, axis="y")
            beam(fa, (fx_, 17.7, -1.12 * k), (fx_ + 0.06, 15.2, -0.94 * k), 0.42, 0.4, ME)
            beam(fa, (fx_ - 0.05, 17.7, 1.1 * k), (fx_ + 0.04, 15.2, 0.94 * k), 0.42, 0.4, ME)
        if want("wrist"):
            joint_drum(fa, A.WRIST, 0.88, 2.05, axis="x", style=ME, cap=JO, hub=DK,
                       caps=(-1,))
    if want("hand"):
        hd = part("hand_r", "rightArm", A.WRIST)
        F["hand_r"] = hd
        _fist(hd, ME, DK, JO, GL, fingers)
    # ------------------------------------------------------------ 脚
    if want("hip") or want("thigh"):
        th = part("thigh_r", "rightLeg", A.HIP)
        F["thigh_r"] = th
        if want("hip"):
            ball(th, A.HIP, 1.12, JO, ME)
        if want("thigh"):
            taper(th, (LX - 0.05, 14.3, 0.05), (LX, 9.35, -0.05), 2.75 * k, 2.3 * k, 2, SU)
            for y, ww in ((12.9, 2.95), (10.6, 2.7)):
                octa(th, (LX, y, 0.0), ww * k, 0.3, BA, axis="y")
            beam(th, (LX - 1.3 * k, 13.7, 0.25), (LX - 1.12 * k, 9.7, 0.1), 0.5, 0.6, ME)
            beam(th, (LX + 1.15 * k, 13.2, 0.1), (LX + 1.0 * k, 9.7, 0.0), 0.42, 0.48, ME)
            rbox(th, (LX, 11.9, -1.3 * k), (1.8 * k, 3.8, 0.45), ME, rot=(-4, 0, 0))
    if want("knee"):
        kn = part("knee_r", "rightLeg", A.KNEE)
        F["knee_r"] = kn
        joint_drum(kn, A.KNEE, 1.3 * k, 2.75 * k, axis="x", style=ME, cap=JO, hub=DK,
                   glow=GL, caps=(-1, 1))
        rbox(kn, (LX, 8.6, -1.38 * k), (1.45, 1.45, 0.45), ME, rot=(0, 0, 45))     # 膝の皿
        if pist:
            piston(kn, (LX, 11.2, 1.38 * k), (LX, 6.4, 1.42 * k), r=0.3, style=ME,
                   rod_style=JO, cap_style=DK)
    if want("shin") or want("ankle"):
        sn = part("shin_r", "rightLeg", A.KNEE)
        F["shin_r"] = sn
        if want("shin"):
            taper(sn, (LX, 7.75, 0.1), (LX, 2.55, 0.2), 2.3 * k, 1.85 * k, 2, SU)
            chamfer(sn, (LX, 5.85, 0.9), (2.0 * k, 3.3, 1.3), SU, cut=0.45, axis="y")  # ふくらはぎ
            for y, ww in ((6.75, 2.48), (3.55, 2.12)):
                octa(sn, (LX, y, 0.12), ww * k, 0.26, BA, axis="y")
            beam(sn, (LX, 7.4, -1.08 * k), (LX, 2.75, -0.92 * k), 0.7, 0.4, ME)
            beam(sn, (LX - 1.05 * k, 7.2, 0.15), (LX - 0.9 * k, 3.0, 0.2), 0.42, 0.45, ME)
        if want("ankle"):
            joint_drum(sn, A.ANKLE, 0.92, 2.3 * k, axis="x", style=ME, cap=JO, hub=DK,
                       caps=(-1, 1))
            if pist:
                piston(sn, (LX, 5.2, 1.48 * k), (LX, 1.25, 1.62), r=0.25, style=ME,
                       rod_style=JO, cap_style=DK)
    if want("foot"):
        ft = part("foot_r", "rightLeg", A.ANKLE)
        F["foot_r"] = ft
        cbox(ft, (LX, 0.2, -1.15), (2.6, 0.4, 5.6), DK)                             # 靴底
        chamfer(ft, (LX, 0.95, -0.55), (2.35, 1.2, 3.3), ME, cut=0.4, axis="z")
        cbox(ft, (LX, 0.92, 1.12), (2.15, 1.05, 0.95), ME)                          # 踵
        rbox(ft, (LX, 1.62, -1.2), (1.95, 0.75, 1.6), ME, rot=(-30, 0, 0))         # 甲
        rbox(ft, (LX, 0.62, -2.72), (2.25, 0.62, 1.05), ME, rot=(-12, 0, 0))       # つま先の板 1
        cbox(ft, (LX, 0.42, -3.24), (1.9, 0.36, 0.4), DK)                          # 関節
        rbox(ft, (LX, 0.42, -3.62), (2.15, 0.46, 0.82), ME, rot=(-20, 0, 0))       # つま先の板 2
    s.frame = F
    return F


def _fist(hd, ME, DK, JO, GL, fingers=True):
    """拳（右手）。握りの点 A.GRIP = (-6, 13.2, 0) を通る柄（Z 方向）を、外（-X）側の手の甲から
    4 本の指が下を回って内側へ包み、親指が前から押さえる。手の大きさは A.FIST_*（幅 2.6・奥行き 2.8）。"""
    cbox(hd, (-6.78, 13.6, 0.0), (1.05, 1.95, 2.5), ME)                             # 手の甲
    cbox(hd, (-6.25, 14.35, 0.0), (1.4, 0.55, 2.2), DK)                             # 手首の付け根
    cbox(hd, (-6.98, 12.48, 0.0), (0.82, 0.52, 2.62), DK)                           # 指の付け根の関節
    sensor(hd, (-7.33, 13.75, 0.0), 0.3, GL, DK, axis="x", facing=-1)
    if not fingers:
        cbox(hd, (-6.0, 12.1, 0.0), (2.4, 1.3, 2.5), ME)
        return
    for i, zf in enumerate((-0.93, -0.31, 0.31, 0.93)):
        sc = (1.0, 1.04, 1.0, 0.9)[i]
        p0 = (-6.98, 12.45, zf)
        p1 = (-6.98 + 0.5 * sc, 12.45 - 0.7 * sc, zf)
        p2 = (p1[0] + 0.98 * sc, p1[1] + 0.12, zf)
        p3 = (p2[0] + 0.3 * sc, p2[1] + 0.82 * sc, zf)
        finger_chain(hd, [p0, p1, p2, p3], w=0.5, h=0.54, style=ME, knuckle=DK)
    finger_chain(hd, [(-5.72, 13.95, -1.02), (-5.2, 13.35, -1.5), (-5.55, 12.72, -1.62)],
                 w=0.5, h=0.52, style=ME, knuckle=DK)                               # 親指
    cbox(hd, (-5.86, 14.02, -0.98), (0.62, 0.62, 0.62), JO)                         # 親指の付け根


def mirror_cube(c: Cube, smap=None, about: float = 0.0) -> Cube:
    """X = about の面で鏡映したキューブ（回転は (rx, -ry, -rz)、デカールの east/west 入れ替え）。"""
    o = list(c.origin)
    s = list(c.size)
    o[0] = 2 * about - (o[0] + s[0])
    piv = [2 * about - c.pivot[0], c.pivot[1], c.pivot[2]] if c.pivot else None
    rot_ = [c.rotation[0], -c.rotation[1], -c.rotation[2]] if c.rotation else None
    dec = {}
    for f, d in (c.decals or {}).items():
        dec[{"east": "west", "west": "east"}.get(f, f)] = copy.deepcopy(d)
    style = (smap or {}).get(c.style, c.style)
    n = Cube(o, s, style, inflate=c.inflate, pivot=piv, rotation=rot_, decals=dec,
             uv_scale=c.uv_scale)
    return n


def mirror_x(bone: Bone, *cubes, style_map=None, about: float = 0.0) -> List[Cube]:
    """同じボーンの中で、渡したキューブ（リスト可）の X 鏡映を足す（胸・兜など中央の部品の左右対称）。
    about で鏡の位置（脚の中心 A.LEG_X など）。"""
    flat = []

    def add(c):
        if isinstance(c, (list, tuple)):
            for x in c:
                add(x)
        elif isinstance(c, dict):
            for x in c.values():
                if x is not None:
                    add(x)
        else:
            flat.append(c)
    for c in cubes:
        add(c)
    out = [mirror_cube(c, style_map, about) for c in flat]
    bone.cubes.extend(out)
    return out


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
    """惑星 key のスーツを組み立てる（未パック）。suit.py の build_suit(s) を呼び、左右を写す
    （MIRROR=False でも frame7 の骨格だけは左右対称に写す）。"""
    mod = module or load_module(key)
    s = Suit(key, uv_scale=getattr(mod, "UV_SCALE", 4))
    s.mirror_styles.update(getattr(mod, "MIRROR_STYLES", {}))
    s.allow.extend(getattr(mod, "COVER_ALLOW", []))
    for o in getattr(mod, "ORNAMENTS", ()):
        s.ornaments.add(o)
    mod.build_suit(s)
    if getattr(mod, "MIRROR", True):
        s.mirror_all()
    elif s.frame_roots:
        s.mirror_all(only=s.frame_roots)
    s.module = mod
    return s


def pack(s: Suit, base: float = 4.0, ks=(2.0, 1.75, 1.5, 1.375, 1.25, 1.125, 1.0, 0.875, 0.75,
                                           0.6875, 0.625, 0.5625, 0.5)) -> float:
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
#  プロポーションと細かさの計測（check_astro_suits・preview が使う。DESIGN §4.3b）
# ===========================================================================
# 検査の閾値
LIMITS = {
    "height": (31.0, 35.0),          # 背丈（飾りを除く、足の裏から頭頂）
    "head_tol": 0.12,                # 頭の高さ = 背丈/7 ± 12%
    "head_w": 5.4,                   # 頭の幅の上限
    "chest_waist": 1.45,             # 胸の幅 ≥ 1.45 × 腰の幅
    "leg_vis": 0.44,                 # 見えている脚の長さ ≥ 0.44 × 背丈
    "cubes": (600, 1400),            # キューブ数
    "fine": 0.35,                    # 3 辺とも 1.0 以下のキューブの割合
    "fine_dim": 1.0,
}


def _measured(s, name):
    """計測に入れるボーンか: 飾り・extra_*（マント・衛星・環）・fx_thrust_*（炎）・fx_spin_*（回転体）を除く。"""
    b = s.bone(name)
    chain = [name]
    while b.parent:
        chain.append(b.parent)
        b = s.bone(b.parent)
    if any(n.startswith(("extra_", "fx_thrust_", "fx_spin_")) for n in chain):
        return False
    return not s.is_ornament(name)


def _face_points(M, lo, hi, step):
    """箱 [lo, hi]（局所）の 6 面を step 間隔で標本化 → ワールドの点 (N,3)。"""
    pts = []
    for ax in range(3):
        a, b = [i for i in range(3) if i != ax]
        na = max(2, int(math.ceil((hi[a] - lo[a]) / step)) + 1)
        nb = max(2, int(math.ceil((hi[b] - lo[b]) / step)) + 1)
        ga, gb = np.meshgrid(np.linspace(lo[a], hi[a], na), np.linspace(lo[b], hi[b], nb))
        for v in (lo[ax], hi[ax]):
            P = np.zeros((ga.size, 3))
            P[:, a] = ga.ravel()
            P[:, b] = gb.ravel()
            P[:, ax] = v
            pts.append(P)
    P = np.vstack(pts)
    return (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]


def region_points(s: Suit, step: float = 0.1):
    """計測に入れるキューブの表面の点と、その点のトップレベル名。立ち姿（各ピボットの恒等変換）。"""
    geo = geo_of(s)
    W = suit_world(geo)
    P, R = [], []
    for b in geo["bones"]:
        name = b["name"]
        if name in TOP or not b.get("cubes") or not _measured(s, name):
            continue
        top = top_of(geo, name)
        for c in b["cubes"]:
            M = W[name] @ cube_matrix(c)
            inf = c.get("inflate", 0.0)
            lo = np.array(c["origin"], float) - inf
            hi = lo + np.array(c["size"], float) + 2 * inf
            pts = _face_points(M, lo, hi, step)
            P.append(pts)
            R.extend([top] * len(pts))
    return np.vstack(P), np.array(R)


def _profile(P, y0, y1, dy=0.1):
    """y の帯ごとの (y, X 方向の幅, Z 方向の幅)。"""
    out = []
    if not len(P):
        return out
    ys = np.arange(y0, y1, dy)
    idx = np.floor((P[:, 1] - y0) / dy).astype(int)
    for i, y in enumerate(ys):
        m = idx == i
        if not m.any():
            out.append((y, 0.0, 0.0))
            continue
        Q = P[m]
        out.append((y, float(Q[:, 0].max() - Q[:, 0].min()), float(Q[:, 2].max() - Q[:, 2].min())))
    return out


def measure(s: Suit, step: float = 0.1) -> dict:
    """7 頭身の計測（立ち姿・飾り/extra/炎/回転体を除く）:
    height（足の裏 → 頭頂）, ground, top, head_h（頭頂 → 顎: 断面積が頭の 36% を切る所）, head_w,
    chest_w（胸の帯 A.CHEST_BOT..CHEST_TOP+0.5 の body の最大幅）, waist_w（腰の帯の body の最小幅）,
    leg_vis（正面から見て脚が見えている一番上 − 足の裏）, leg_len（脚の部品の一番上 − 足の裏）,
    cubes, fine（3 辺とも 1.0 以下の数）, fine_share。"""
    P, R = region_points(s, step)
    out = {}
    legs = P[np.isin(R, ("rightLeg", "leftLeg"))]
    ground = float(legs[:, 1].min()) if len(legs) else float(P[:, 1].min())
    top = float(P[:, 1].max())
    out.update(ground=ground, top=top, height=top - ground)
    # 頭: 断面積（X 幅 × Z 幅）の輪郭で首を見つける
    H = P[R == "head"]
    if len(H):
        htop = float(H[:, 1].max())
        prof = _profile(H, float(H[:, 1].min()), htop + 0.1)
        area = [(y, wx * wz) for y, wx, wz in prof]
        amax = max([a for y, a in area if y >= htop - 4.8] or [1.0])
        neck = [(a, y) for y, a in area if htop - 7.5 <= y <= htop - 2.5 and a > 0.12 * amax]
        hbot = float(H[:, 1].min())
        if neck:
            amin, yn = min(neck)
            if amin < 0.6 * amax:             # 首のくびれがある → その上で断面が戻る所が顎
                thr = amin + 0.4 * (amax - amin)
                for y, a in area:
                    if y > yn and a >= thr:
                        hbot = y
                        break
        out["head_top"], out["head_bot"] = htop, hbot
        out["head_h"] = htop - hbot
        out["head_w"] = max([wx for y, wx, _wz in prof if y >= hbot] or [0.0])
        out["head_d"] = max([wz for y, _wx, wz in prof if y >= hbot] or [0.0])
    else:
        out.update(head_top=0.0, head_bot=0.0, head_h=0.0, head_w=0.0, head_d=0.0)
    # 胸と腰（body のみ。腕の部品は入らない）
    B = P[R == "body"]
    chest = _profile(B, A.CHEST_BOT, A.CHEST_TOP + 0.5)
    waist = _profile(B, A.WAIST_BOT + 0.2, A.WAIST_TOP - 0.2)
    out["chest_w"] = max([wx for _y, wx, _z in chest] or [0.0])
    wv = [(wx, y) for y, wx, _z in waist if wx > 0]
    out["waist_w"], out["waist_y"] = min(wv) if wv else (0.0, 0.0)
    out["chest_waist"] = out["chest_w"] / out["waist_w"] if out["waist_w"] else 0.0
    # 脚: 正面（-Z から）の深さバッファで、脚の点が手前に見えている一番上
    cell = 0.15
    ix = np.floor(P[:, 0] / cell).astype(int)
    iy = np.floor(P[:, 1] / cell).astype(int)
    ix -= ix.min()
    iy -= iy.min()
    zb = np.full((ix.max() + 1, iy.max() + 1), np.inf)
    np.minimum.at(zb, (ix, iy), P[:, 2])
    isleg = np.isin(R, ("rightLeg", "leftLeg"))
    vis = isleg & (P[:, 2] <= zb[ix, iy] + 0.06)
    vis_top = {}
    for side, top_name in (("r", "rightLeg"), ("l", "leftLeg")):
        m = vis & (R == top_name)
        vis_top[side] = float(P[m, 1].max()) if m.any() else ground
    out["leg_vis"] = min(vis_top.values()) - ground
    out["leg_len"] = (float(legs[:, 1].max()) - ground) if len(legs) else 0.0
    # キューブ数と細かさ
    cubes = s.m.all_cubes()
    fine = sum(1 for c in cubes if max(c.size) <= LIMITS["fine_dim"] + 1e-6)
    out["cubes"] = len(cubes)
    out["fine"] = fine
    out["fine_share"] = fine / max(1, len(cubes))
    out["unit"] = out["height"] / 7.0
    return out


def proportion_checks(m: dict) -> List[tuple]:
    """measure() の結果を閾値と比べる → [(ok, 名前, 説明)]。"""
    Lm = LIMITS
    H = m["height"]
    hh = H / 7.0
    lo_h, hi_h = hh * (1 - Lm["head_tol"]), hh * (1 + Lm["head_tol"])
    rows = [
        (Lm["height"][0] <= H <= Lm["height"][1], "height",
         f"{H:.2f} (want {Lm['height'][0]:g}..{Lm['height'][1]:g}; ornaments excluded)"),
        (lo_h <= m["head_h"] <= hi_h, "head height",
         f"{m['head_h']:.2f} = H/{H / max(m['head_h'], 1e-6):.2f} (want {lo_h:.2f}..{hi_h:.2f} = H/7 ±12%;"
         f" head y {m['head_bot']:.1f}..{m['head_top']:.1f})"),
        (m["head_w"] <= Lm["head_w"], "head width", f"{m['head_w']:.2f} (want <= {Lm['head_w']:g})"),
        (m["chest_waist"] >= Lm["chest_waist"], "chest/waist",
         f"chest {m['chest_w']:.2f} / waist {m['waist_w']:.2f} (at y {m['waist_y']:.1f}) = "
         f"{m['chest_waist']:.2f} (want >= {Lm['chest_waist']:g})"),
        (m["leg_vis"] >= Lm["leg_vis"] * H, "visible legs",
         f"{m['leg_vis']:.2f} = {m['leg_vis'] / max(H, 1e-6):.3f}H (want >= {Lm['leg_vis']:g}H = "
         f"{Lm['leg_vis'] * H:.2f}; front view, extra_* ignored)"),
        (Lm["cubes"][0] <= m["cubes"] <= Lm["cubes"][1], "cubes",
         f"{m['cubes']} (want {Lm['cubes'][0]}..{Lm['cubes'][1]})"),
        (m["fine_share"] >= Lm["fine"], "fine parts",
         f"{m['fine']}/{m['cubes']} = {100 * m['fine_share']:.1f}% of cubes have all dims <= "
         f"{Lm['fine_dim']:g} (want >= {100 * Lm['fine']:.0f}%)"),
    ]
    return rows


# ===========================================================================
#  被覆検査（v1.0。7 頭身では使わない。互換のために残す）
# ===========================================================================
FACE_N = {"up": (1, 1), "down": (1, -1), "east": (0, 1), "west": (0, -1),
          "south": (2, 1), "north": (2, -1)}   # 軸, 向き（east = +X、south = +Z）


def skin_samples(top: str, spacing: float = 0.5, slim=False):
    """外側レイヤーの表面の標本点 (N,3) と、その点の面名のリスト。slim=True でスリムの腕。"""
    o, sz = (SKIN_SLIM if slim else SKIN)[top]
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
    """（v1.0）肌の外側レイヤーの表面を spacing 間隔で標本化し、各点が同じトップレベルボーン配下の
    どれかのキューブに入っているかを調べる。v1.1 の 7 頭身では肌は透明化で隠すので検査に使わない。
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
        if top in SKIN_SLIM:                       # スリムの腕も同時に覆う
            p2, f2 = skin_samples(top, spacing, slim=True)
            pts = np.vstack([pts, p2])
            faces = faces + f2
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
        if n.lower() in RESERVED:
            errs.append(f"bone '{n}' uses a player bone name (it would follow that bone); "
                        "prefix it, e.g. 'helmet_crest'")
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


def small_part_errors(s: Suit, limit: float = MIN_PART - 0.005) -> List[str]:
    """0.15 未満の辺を持つキューブ（DESIGN §4.3b: 作らない）。"""
    out = []
    for b in s.m.bones:
        for c in b.cubes:
            if min(c.size) < limit:
                out.append(f"{b.name}: cube {c.size} (style {c.style}) has a side < {MIN_PART}")
    return out
