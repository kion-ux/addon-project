# -*- coding: utf-8 -*-
"""進撃の巨人のモデル一式（ジオメトリ＋テクスチャ）。

* 無垢の巨人: 体型 4 種（細長い手足 / 肥満 / 筋肉質 / 大頭）。全高 3m で作り、
  クライアント側の scripts.scale で 4m / 7m / 13m / 10m 級へ拡大する。
  顎は別ボーン（噛みつき・食べる）、指は掴みのために曲げられる
* 調査兵団: 身長と等身から骨格を出す rig.HumanRig に、制服（上着・白いズボン・
  ブーツ）、立体機動装置、自由の翼のマント、両手の刃を着せる
* プレイヤーが着るもの: 同じ作り方の装備を、バニラのプレイヤー骨格の寸法
  （体 8×12×4、腕 4×12×4、脚 4×12×4）に合わせて組む（Frame.player）
* 刃・雷槍: 武器空間（握り = 原点、-Z = 刃先、+Y = 刃の幅）で作る
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, Tuple

import aot_common as C
from aot_common import BODIES, GEO_DIR, TEX_DIR
from aot_paint import AotPainter
import aot_palettes as PAL
from hd_common import beam, cbox
from mcmodel import Bone, Cube, Model
from rig import Build, HumanRig

Box = Tuple[float, float, float, float, float, float]   # x0, x1, y0, y1, z0, z1


# ===========================================================================
#  体の箱（NPC の骨格とプレイヤーの骨格を同じ書き方で扱う）
# ===========================================================================
@dataclass
class Part:
    bone: str
    box: Box


class Frame:
    """装備を「どの骨に、どの箱の外側に」付けるかを与える。"""

    def __init__(self, model: Model, parts: Dict[str, Part], bones: Dict[str, Bone],
                 player: bool):
        self.m = model
        self.parts = parts
        self.bones = bones
        self.player = player

    def bone(self, key) -> Bone:
        return self.bones[self.parts[key].bone]

    def box(self, key) -> Box:
        return self.parts[key].box

    # ------------------------------------------------------------------
    @classmethod
    def npc(cls, rig: HumanRig) -> "Frame":
        L = rig.L
        P = {}
        P["chest"] = Part("chest", (-L.chest_w / 2, L.chest_w / 2, L.chest_bot, L.chest_top,
                                    -L.chest_d / 2, L.chest_d / 2))
        P["abdomen"] = Part("body", (-L.waist_w / 2, L.waist_w / 2, L.abdomen_bot, L.chest_bot,
                                     -L.waist_d / 2, L.waist_d / 2))
        P["hips"] = Part("body", (-L.hip_w / 2, L.hip_w / 2, L.pelvis_bot, L.abdomen_bot,
                                  -L.waist_d / 2, L.waist_d / 2))
        P["head"] = Part("head", (-L.head_w / 2, L.head_w / 2, L.chin, L.chin + L.head_h,
                                  -L.head_d * 0.52, L.head_d * 0.48))
        P["neck"] = Part("neck", (-L.head_w * 0.3, L.head_w * 0.3, L.shoulder_y - L.neck_h * 0.3,
                                  L.chin + L.neck_h * 0.2, -L.head_d * 0.24, L.head_d * 0.24))
        for side, sgn in (("right", -1), ("left", 1)):
            cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
            P[f"{side}_upper"] = Part(f"{side}Arm", (cx - L.arm_t / 2, cx + L.arm_t / 2,
                                                     L.elbow_y, L.shoulder_y,
                                                     -L.arm_t / 2, L.arm_t / 2))
            P[f"{side}_fore"] = Part(f"{side}Forearm", (cx - L.forearm_t / 2, cx + L.forearm_t / 2,
                                                        L.wrist_y, L.elbow_y,
                                                        -L.forearm_t / 2, L.forearm_t / 2))
            P[f"{side}_hand"] = Part(f"{side}Hand", (cx - L.forearm_t * 0.52, cx + L.forearm_t * 0.52,
                                                     L.wrist_y - L.hand_l, L.wrist_y,
                                                     -L.forearm_t * 0.42, L.forearm_t * 0.42))
            lx = sgn * L.stance
            P[f"{side}_thigh"] = Part(f"{side}Leg", (lx - L.thigh_t / 2, lx + L.thigh_t / 2,
                                                     L.knee_y, L.hip_y,
                                                     -L.thigh_t / 2, L.thigh_t / 2))
            P[f"{side}_shin"] = Part(f"{side}Shin", (lx - L.shin_t / 2, lx + L.shin_t / 2,
                                                    L.ankle_y, L.knee_y,
                                                    -L.shin_t / 2, L.shin_t / 2))
            P[f"{side}_foot"] = Part(f"{side}Foot", (lx - L.shin_t * 0.6, lx + L.shin_t * 0.6,
                                                    0, L.foot_h, -L.foot_l * 0.62, L.foot_l * 0.33))
        return cls(rig.model, P, rig.bones, False)

    @classmethod
    def player(cls, model: Model, slim: bool = False) -> "Frame":
        """バニラのプレイヤー骨格（geometry.humanoid.custom）の寸法。ボーン名を揃えると
        アタッチャブルの各ボーンがプレイヤーの同名ボーンに付いて動く。"""
        bones = {}
        for name, pivot in (("body", (0, 24, 0)), ("head", (0, 24, 0)),
                            ("rightArm", (-5, 22, 0)), ("leftArm", (5, 22, 0)),
                            ("rightLeg", (-1.9, 12, 0)), ("leftLeg", (1.9, 12, 0))):
            bones[name] = model.bone(name, pivot)
        aw = 3.0 if slim else 4.0
        P = {
            "chest": Part("body", (-4, 4, 18, 24, -2, 2)),
            "abdomen": Part("body", (-4, 4, 15, 18, -2, 2)),
            "hips": Part("body", (-4, 4, 12, 15, -2, 2)),
            "head": Part("head", (-4, 4, 24, 32, -4, 4)),
            "neck": Part("body", (-2, 2, 23.5, 24.5, -1.5, 1.5)),
        }
        for side, sgn in (("right", -1), ("left", 1)):
            x0, x1 = (-4 - aw, -4) if sgn < 0 else (4, 4 + aw)
            P[f"{side}_upper"] = Part(f"{side}Arm", (x0, x1, 18, 24, -2, 2))
            P[f"{side}_fore"] = Part(f"{side}Arm", (x0, x1, 14, 18, -2, 2))
            P[f"{side}_hand"] = Part(f"{side}Arm", (x0, x1, 12, 14, -2, 2))
            lx0, lx1 = (-3.9, 0.1) if sgn < 0 else (-0.1, 3.9)
            P[f"{side}_thigh"] = Part(f"{side}Leg", (lx0, lx1, 6, 12, -2, 2))
            P[f"{side}_shin"] = Part(f"{side}Leg", (lx0, lx1, 1.6, 6, -2, 2))
            P[f"{side}_foot"] = Part(f"{side}Leg", (lx0, lx1, 0, 1.6, -2, 2))
        return cls(model, P, bones, True)


def shell(fr: Frame, key, style, pad=0.3, y0=None, y1=None, uv=4, decals=None,
          pad_y=0.0, inflate=0.0, z_pad=None):
    """部位の箱を一回り大きく覆うキューブ（上着の胴、袖、ブーツ…）。"""
    x0, x1, by0, by1, z0, z1 = fr.box(key)
    ya = by0 if y0 is None else y0
    yb = by1 if y1 is None else y1
    zp = pad if z_pad is None else z_pad
    return fr.bone(key).add(Cube((x0 - pad, ya - pad_y, z0 - zp),
                                 (x1 - x0 + pad * 2, yb - ya + pad_y * 2, z1 - z0 + zp * 2),
                                 style, uv_scale=uv, decals=decals, inflate=inflate))


def band(fr: Frame, key, y, h, style="strap", pad=0.45, uv=6, decals=None):
    """部位を一周する帯（ベルト・ストラップ）。"""
    x0, x1, _y0, _y1, z0, z1 = fr.box(key)
    return fr.bone(key).add(Cube((x0 - pad, y - h / 2, z0 - pad),
                                 (x1 - x0 + pad * 2, h, z1 - z0 + pad * 2), style,
                                 uv_scale=uv, decals=decals))


# ===========================================================================
#  制服と装備
# ===========================================================================
def jacket(fr: Frame, patch=True):
    """調査兵団の上着: 赤みのある茶の革、肋骨の下で切れる短い丈、折り返しの襟。"""
    x0, x1, y0, y1, z0, z1 = fr.box("chest")
    ch = y1 - y0
    crop = y0 - (0.8 if fr.player else ch * 0.12)
    shell(fr, "chest", "jacket", pad=0.42, y0=crop, y1=y1 + 0.15, uv=5,
          decals={"north": {"name": "jacket_front", "patch": patch},
                  "south": {"name": "wings", "shield": True, "size": 0.5, "cv": 0.44}})
    # 裾の縫い目
    fr.bone("chest").add(Cube((x0 - 0.5, crop - 0.05, z0 - 0.5), (x1 - x0 + 1.0, 0.6, z1 - z0 + 1.0),
                              "jacket_dark", uv_scale=6))
    # 折り返しの襟（左右）
    for sgn in (-1, 1):
        cx = sgn * (x1 - x0) * 0.22
        fr.bone("chest").add(Cube((cx - (x1 - x0) * 0.14, y1 - 0.4, z0 - 0.75),
                                  ((x1 - x0) * 0.28, 1.1, (z1 - z0) * 0.55), "jacket_dark",
                                  uv_scale=6, rotation=(-14, 0, sgn * 10)))
    # 立ち襟（首の後ろ）
    fr.bone("chest").add(Cube((-(x1 - x0) * 0.3, y1 - 0.1, (z1 - z0) * 0.05),
                              ((x1 - x0) * 0.6, 1.0, (z1 - z0) * 0.45), "jacket_dark", uv_scale=6))
    for side in ("right", "left"):
        outer = "west" if side == "right" else "east"
        shell(fr, f"{side}_upper", "jacket", pad=0.38, uv=5,
              decals={outer: {"name": "wings", "shield": True, "size": 0.62, "cv": 0.40}}
              if patch else None)
        shell(fr, f"{side}_fore", "jacket", pad=0.36, uv=5)
        hx0, hx1, hy0, hy1, hz0, hz1 = fr.box(f"{side}_fore")
        fr.bone(f"{side}_fore").add(Cube((hx0 - 0.45, hy0 - 0.1, hz0 - 0.45),
                                         (hx1 - hx0 + 0.9, 0.9, hz1 - hz0 + 0.9), "jacket_dark",
                                         uv_scale=6))


def cloak(fr: Frame, length_to="knee"):
    """自由の翼のマント。肩から膝までの一枚布を上下 2 ボーンに分け、走る・飛ぶと翻る。"""
    x0, x1, y0, y1, z0, z1 = fr.box("chest")
    hx0, hx1, hy0, hy1, hz0, hz1 = fr.box("hips")
    tx = fr.box("right_thigh")
    knee = tx[2]
    width = (x1 - x0) * (1.10 if fr.player else 1.12)
    zb = z1 + (0.55 if fr.player else 0.5)
    parent = fr.parts["chest"].bone
    # 少し後ろへ傾けて、腰の立体機動装置の上に掛かるようにする
    top = fr.m.bone("cloak", (0, y1, zb), parent, rotation=(7, 0, 0))
    fr.bones["cloak"] = top
    split = hy1
    top.add(Cube((-width / 2, split, zb), (width, y1 - split + 0.4, 0.5), "cloak", uv_scale=4,
                 decals={"south": {"name": "wings", "size": 0.98, "cv": 0.46}}))
    # 肩に掛かる部分とフードの溜まり
    top.add(Cube((-width / 2, y1 - 0.6, z0 - 0.2), (width, 0.9, zb - z0 + 0.7), "cloak", uv_scale=4))
    top.add(Cube((-(x1 - x0) * 0.36, y1 - 0.5, zb - 0.3), ((x1 - x0) * 0.72, 2.2, 1.6), "cloak_in",
                 uv_scale=5))
    low = fr.m.bone("cloak_low", (0, split, zb), "cloak")
    fr.bones["cloak_low"] = low
    bottom = knee + (0.5 if fr.player else (y0 - knee) * 0.05) if length_to == "knee" else hy0
    low.add(Cube((-width / 2 * 0.98, bottom, zb), (width * 0.98, split - bottom, 0.5), "cloak",
                 uv_scale=4))
    low.add(Cube((-width / 2 * 0.98, bottom - 0.2, zb + 0.05), (width * 0.98, 0.6, 0.55), "cloak_in",
                 uv_scale=5))


def boots(fr: Frame):
    """膝下までの焦茶のロングブーツ。"""
    for side in ("right", "left"):
        sx0, sx1, sy0, sy1, sz0, sz1 = fr.box(f"{side}_shin")
        top = sy1 - (sy1 - sy0) * (0.04 if not fr.player else 0.0)
        shell(fr, f"{side}_shin", "boots", pad=0.4, y0=sy0 - (0.0 if fr.player else 0.4), y1=top,
              uv=5, decals={"north": "boot_top"})
        fx0, fx1, fy0, fy1, fz0, fz1 = fr.box(f"{side}_foot")
        fr.bone(f"{side}_foot").add(Cube((fx0 - 0.4, fy0, fz0 - 0.5),
                                         (fx1 - fx0 + 0.8, fy1 - fy0 + 0.4, fz1 - fz0 + 0.9),
                                         "boots", uv_scale=5))


def harness(fr: Frame, pants=True):
    """立体機動装置のベルト類（腰・胸・腿）。プレイヤー用は白いズボンも重ねる。"""
    x0, x1, y0, y1, z0, z1 = fr.box("hips")
    band(fr, "hips", y1 - 0.5, 1.1, decals={"north": "buckle"})
    band(fr, "abdomen", fr.box("abdomen")[2] + 1.2, 0.7)
    cx0, cx1, cy0, cy1, cz0, cz1 = fr.box("chest")
    band(fr, "chest", cy0 + (cy1 - cy0) * 0.22, 0.7, pad=0.62)
    # 胸から腰へ下りる 2 本のストラップ（前）
    for sgn in (-1, 1):
        x = sgn * (cx1 - cx0) * 0.24
        fr.bone("chest").add(Cube((x - 0.35, fr.box("abdomen")[2], cz0 - 0.7),
                                  (0.7, cy0 + (cy1 - cy0) * 0.3 - fr.box("abdomen")[2], 0.3),
                                  "strap", uv_scale=6))
        # 肩を越えて背中へ回るストラップ
        fr.bone("chest").add(Cube((x - 0.35, cy1 - 0.2, cz0 - 0.65), (0.7, 0.6, cz1 - cz0 + 1.3),
                                  "strap", uv_scale=6))
    for side in ("right", "left"):
        tx0, tx1, ty0, ty1, tz0, tz1 = fr.box(f"{side}_thigh")
        if pants and fr.player:
            shell(fr, f"{side}_thigh", "pants", pad=0.25, uv=4)
            shell(fr, f"{side}_shin", "pants", pad=0.22, uv=4)
        for t in (0.25, 0.7):
            band(fr, f"{side}_thigh", ty0 + (ty1 - ty0) * t, 0.6, pad=0.5)
    if pants and fr.player:
        shell(fr, "hips", "pants", pad=0.25, uv=4)


def odm_device(fr: Frame):
    """立体機動装置本体: 腰の後ろの本体と巻き取り機、腰の左右のアンカー射出機、
    腿の外の刃の収納箱（各 4 枚）と、その上のガスボンベ。"""
    x0, x1, y0, y1, z0, z1 = fr.box("hips")
    b = fr.bone("hips")
    hw = (x1 - x0) / 2
    # 本体（背中側）
    b.add(Cube((-1.5, y0 + 0.2, z1 + 0.15), (3.0, (y1 - y0) + 1.2, 1.0), "steel_dark", uv_scale=6))
    b.add(Cube((-0.6, y0 + 1.0, z1 + 1.1), (1.2, 1.2, 0.2), "steel", uv_scale=8,
               decals={"south": "gauge"}))
    for sgn in (-1, 1):                               # 巻き取り機
        b.add(Cube((sgn * 1.9 - 0.6, y0 + 0.8, z1 + 0.2), (1.2, 1.2, 1.0), "steel", uv_scale=6,
                   rotation=(0, 0, 45)))
    for sgn in (-1, 1):
        side_x = sgn * (hw + 0.35)
        # アンカー射出機（腰の左右、前向き）
        b.add(Cube((side_x - 0.55 if sgn > 0 else side_x - 0.65, y1 - 1.6, z0 - 0.6),
                   (1.2, 1.2, (z1 - z0) + 1.0), "steel_dark", uv_scale=6))
        b.add(Cube((side_x - 0.3 if sgn > 0 else side_x - 0.4, y1 - 1.35, z0 - 1.4),
                   (0.7, 0.7, 1.0), "steel", uv_scale=8))
        # 刃の収納箱（後ろが下がる）
        bx = sgn * (hw + 1.45)
        L = 11.0 if fr.player else (y1 - y0) * 3.6
        Hh = 2.8 if fr.player else (y1 - y0) * 0.95
        Ww = 1.5
        z_front = z0 - 1.2
        b.add(Cube((bx - Ww / 2, y0 - Hh * 0.55, z_front), (Ww, Hh, L), "steel", uv_scale=4,
                   rotation=(-14, sgn * 4, 0), pivot=(bx, y0, z_front),
                   decals={"west" if sgn < 0 else "east": {"name": "slots", "n": 4}}))
        # 箱の前に出ている刃の柄（4 本）
        for i in range(4):
            b.add(Cube((bx - 0.35, y0 - Hh * 0.45 + i * Hh * 0.24, z_front - 0.9),
                       (0.7, Hh * 0.16, 1.0), "grip", uv_scale=8,
                       rotation=(-14, sgn * 4, 0), pivot=(bx, y0, z_front)))
        # ガスボンベ（箱の上）
        b.add(Cube((bx - 0.85, y0 + Hh * 0.45, z_front + L * 0.18), (1.7, 1.7, L * 0.72), "tank",
                   uv_scale=5, rotation=(-14, sgn * 4, 0), pivot=(bx, y0, z_front),
                   decals={"up": "tank_bands", "west" if sgn < 0 else "east": "tank_bands"}))
        # ホース（ボンベから本体へ）
        beam(b, (bx, y0 + Hh * 0.6, z_front + L * 0.6), (sgn * 1.6, y0 + 1.2, z1 + 1.0), 0.4, 0.4,
             "wire", uv_scale=8)


def blades_in_hands(rig: HumanRig, length=17.0):
    """NPC の両手に刃を持たせる（刃先は前下へ）。"""
    for side, name in (("right", "weapon"), ("left", "weapon2")):
        bone, off, s = rig.mount(name, side, (-24, 0, 0), drop=0.45)
        blade_geo(bone, off, s * 0.95, length=length, flip=side == "left")


# ===========================================================================
#  刃・雷槍（武器空間: 握り = 原点、-Z = 刃先、+Y = 刃の幅）
# ===========================================================================
def _mk(bone, off, s):
    def add(origin, size, style, **kw):
        if "pivot" in kw and kw["pivot"] is not None:
            p = kw["pivot"]
            kw["pivot"] = (p[0] * s + off[0], p[1] * s + off[1], p[2] * s + off[2])
        return bone.add(Cube((origin[0] * s + off[0], origin[1] * s + off[1], origin[2] * s + off[2]),
                             (size[0] * s, size[1] * s, size[2] * s), style, **kw))
    return add


def blade_geo(bone, off=(0, 0, 0), s=1.0, length=17.0, flip=False):
    """超硬質スチールの刃と操作装置（握り）。

    握りは拳に収まる縦の柄で、人差し指の引き金と親指のレバーが付く。刃は柄の上の
    差し込み口から前へ伸びる、片刃で幅の狭い長い板。折り線で 6 つに区切ってある
    （欠けたら先を折って新しい刃先を出す構造）。"""
    a = _mk(bone, off, s)
    a((-0.65, -1.9, -0.8), (1.3, 3.2, 1.6), "grip", uv_scale=8)              # 柄
    a((-0.5, -1.2, -1.45), (1.0, 1.6, 0.7), "steel_dark", uv_scale=8,
      decals={"north": "trigger"})                                            # 引き金
    a((-0.8, 1.1, -2.2), (1.6, 1.4, 3.3), "steel", uv_scale=8)                # 差し込み口
    a((-0.3, 1.9, -0.4), (0.6, 0.9, 1.3), "steel_dark", uv_scale=8)          # 親指のレバー
    a((-0.25, 0.85, -2.2 - length), (0.5, 1.9, length), "blade", uv_scale=6,
      decals={"east": {"name": "blade_segments", "n": 6},
              "west": {"name": "blade_segments", "n": 6}})                    # 刃身
    a((-0.12, 0.70, -2.2 - length), (0.24, 0.25, length), "edge", uv_scale=8)  # 刃先（下）
    # 斜めに落とした切先
    a((-0.25, 0.85, -2.2 - length - 1.4), (0.5, 1.2, 1.6), "blade", uv_scale=8,
      rotation=(28, 0, 0), pivot=(0, 0.85, -2.2 - length))
    # ワイヤーの引き出し口
    a((-0.3, -2.4, 0.2), (0.6, 0.6, 1.8), "wire", uv_scale=8)
    _ = flip
    return length + 4.0


def spear_geo(bone, off=(0, 0, 0), s=1.0):
    """雷槍: 前腕に沿わせる筒と、先端の炸薬付きの槍頭。"""
    a = _mk(bone, off, s)
    a((-0.9, -0.9, -6.0), (1.8, 1.8, 9.0), "spear", uv_scale=6,
      decals={"up": {"name": "flare_band", "colour": "#c8a040"}})
    a((-0.6, -0.6, -11.0), (1.2, 1.2, 5.2), "spear_tip", uv_scale=6)
    a((-0.95, -0.95, -12.6), (1.9, 1.9, 1.8), "red", uv_scale=8, decals={"north": "spear_tip"})
    a((-0.35, -0.35, -15.0), (0.7, 0.7, 2.6), "spear_tip", uv_scale=8)
    a((-0.25, -0.25, -16.2), (0.5, 0.5, 1.3), "edge", uv_scale=8)
    for sgn in (-1, 1):                                   # 安定翼
        a((sgn * 0.9 - (0.25 if sgn > 0 else 0.05), -0.15, 1.2), (0.3, 1.6, 2.4), "steel_dark",
          uv_scale=8)
    a((-0.5, -1.9, -1.0), (1.0, 1.2, 2.0), "steel_dark", uv_scale=8)       # 腕の留め具
    return 19.0


# ===========================================================================
#  無垢の巨人
# ===========================================================================
TITAN_BUILDS = {
    # 細長い手足: 小さな頭と長い腕。猫背
    "lanky": dict(build=Build(C.BASE_M * 100, 6.6, 0.235, 0.72, bulk=0.80, arm_len=1.22,
                              leg_ratio=0.54), stoop=14,
                  hair={"cap": {"y": 0.66, "h": 0.46, "out": 0.05, "crown": True},
                        "back": {"y": 0.08, "h": 0.70, "t": 0.16},
                        "bangs": {"y": 0.68, "low": [0.56, 0.62, 0.58, 0.60, 0.55, 0.61],
                                  "t": 0.12},
                        "sides": {"y": 0.10, "h": 0.60, "t": 0.12, "d": 0.56}},
                  eye=dict(eye_v=0.46, eye_r=0.105)),
    # 肥満: 丸い腹、短い脚、太い腕
    "chubby": dict(build=Build(C.BASE_M * 100, 5.0, 0.30, 1.28, bulk=1.55, arm_len=0.96,
                               leg_ratio=0.44),
                   hair=None, belly=True,
                   eye=dict(eye_v=0.46, eye_r=0.11)),
    # 筋肉質: 広い肩、太い四肢
    "muscular": dict(build=Build(C.BASE_M * 100, 6.8, 0.30, 1.18, bulk=1.12, arm_len=1.04,
                                 leg_ratio=0.50),
                     hair={"cap": {"y": 0.78, "h": 0.34, "out": 0.03},
                           "back": {"y": 0.40, "h": 0.46, "t": 0.12}},
                     abs=True, eye=dict(eye_v=0.45, eye_r=0.10)),
    # 大頭: 3.6 等身の大きな頭に満面の笑み
    "bighead": dict(build=Build(C.BASE_M * 100, 3.6, 0.25, 1.0, bulk=1.0, arm_len=0.92,
                                leg_ratio=0.40),
                    hair={"cap": {"y": 0.74, "h": 0.38, "out": 0.03, "crown": True},
                          "back": {"y": 0.30, "h": 0.50, "t": 0.10},
                          "bangs": {"y": 0.76, "low": [0.66, 0.70, 0.67, 0.71, 0.66, 0.70],
                                    "t": 0.08}},
                    eye=dict(eye_v=0.42, eye_r=0.12)),
}


def _rescale(cube: Cube, uv: int) -> None:
    """作った後のキューブの UV 解像度を変える（_scale も揃えないと pack が無視する）。"""
    cube.uv_scale = uv
    cube._scale = uv


def build_titan(body: str) -> Model:
    spec = TITAN_BUILDS[body]
    m = Model(f"geometry.aot.titan_{body}", uv_scale=2, visible_bounds=(14, 16),
              vb_offset=(0, 7, 0), max_atlas=(1024, 1024))
    rig = HumanRig(m, spec["build"], styles={"suit": "skin", "underlay": "skin", "cloth": "skin"})
    face = {"titan": True}
    face.update(spec["eye"])
    rig.flesh(skin="skin", suit="skin", face=face)
    L = rig.L
    head = rig.b("head")
    # 顔の面のキューブを高解像度に（mctexture の目は uv 6 前提）
    # 鼻
    head.add(Cube((-L.head_w * 0.07, L.chin + L.head_h * 0.30, -L.head_d * 0.60),
                  (L.head_w * 0.14, L.head_h * 0.20, L.head_d * 0.10), "skin", uv_scale=6))
    # 顎（別ボーン。口を開ける・噛む）
    jaw = m.bone("jaw", (0, L.chin + L.head_h * 0.30, -L.head_d * 0.05), "head")
    rig.bones["jaw"] = jaw
    jaw.add(Cube((-L.head_w * 0.44, L.chin - L.head_h * 0.02, -L.head_d * 0.56),
                 (L.head_w * 0.88, L.head_h * 0.31, L.head_d * 0.62), "skin", uv_scale=6,
                 decals={"north": "titan_jaw"}))
    # 胸と腹の陰影
    rig.b("chest").cubes[0].decals = {"north": {"name": "titan_chest"},
                                      "south": {"name": "titan_back"}}
    _rescale(rig.b("chest").cubes[0], 3)
    body_bone = rig.b("body")
    body_bone.cubes[1].decals = {"north": {"name": "titan_belly", "abs": spec.get("abs", False)}}
    _rescale(body_bone.cubes[1], 3)
    if spec.get("stoop"):
        # 猫背は胸から上だけを前へ倒す（体のボーンを倒すと脚まで傾く）
        rig.b("chest").rotation = [spec["stoop"], 0, 0]
        rig.b("neck").rotation = [-spec["stoop"] * 0.6, 0, 0]
    if spec.get("belly"):
        # 前に突き出て垂れた丸い腹（横から見て弧になるよう 3 段に重ねる）
        span = L.chest_bot - L.pelvis_bot
        for i, (depth, yk, hk, wk) in enumerate(((1.0, 0.02, 0.98, 1.20), (1.55, 0.10, 0.76, 1.08),
                                                 (1.95, 0.22, 0.48, 0.86))):
            body_bone.add(Cube((-L.waist_w * wk / 2, L.pelvis_bot + span * yk,
                                -L.waist_d / 2 - L.waist_d * depth * 0.5),
                               (L.waist_w * wk, span * hk, L.waist_d * depth * 0.5 + L.waist_d * 0.4),
                               "skin", uv_scale=3,
                               decals={"north": {"name": "titan_belly", "navel": 0.5}}
                               if i == 2 else None))
        # 二重顎
        rig.b("neck").add(Cube((-L.head_w * 0.44, L.shoulder_y, -L.head_d * 0.42),
                               (L.head_w * 0.88, L.neck_h * 1.1, L.head_d * 0.8), "skin",
                               uv_scale=4))
    # 指（掴むために曲げられる）。親指は flesh() のものを使う
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        hand = rig.b(f"{side}Hand")
        hand.cubes[0].decals = {"north": "knuckles"}
        fing = m.bone(f"{side}Fingers", (cx, L.wrist_y - L.hand_l, 0), f"{side}Hand")
        rig.bones[f"{side}Fingers"] = fing
        fw = L.forearm_t * 1.0
        for i in range(4):
            u = -0.5 + (i + 0.5) / 4
            fing.add(Cube((cx + u * fw - fw * 0.11, L.wrist_y - L.hand_l * 1.75,
                           -L.forearm_t * 0.32),
                          (fw * 0.22, L.hand_l * 0.78, L.forearm_t * 0.5), "skin", uv_scale=4))
        foot = rig.b(f"{side}Toe")
        foot.cubes[0].decals = {"up": "toes"}
    if spec.get("hair"):
        rig.hair(spec["hair"])
    m.pack()
    return m


def titan_metrics(body: str) -> dict:
    """アニメーションとスクリプトが使う寸法（モデル px、全高 BASE_M）。"""
    from rig import landmarks
    spec = TITAN_BUILDS[body]
    L = landmarks(spec["build"])
    stoop = math.radians(spec.get("stoop", 0))
    neck_y = (L.shoulder_y + L.chin) / 2
    # うなじ: 首の後ろ。猫背なら胸から上が前へ倒れるぶん前へ出る
    rise = neck_y - L.chest_bot
    nape_y = L.chest_bot + rise * math.cos(stoop)
    nape_z = L.head_d * 0.30 - rise * math.sin(stoop)
    eye_y = L.chin + L.head_h * 0.56
    return {"total": L.total, "hip": L.hip_y, "knee": L.knee_y, "ankle": L.ankle_y,
            "chest_bot": L.chest_bot, "chest_top": L.chest_top, "chin": L.chin,
            "head_h": L.head_h, "chest_d": L.chest_d, "thigh": L.thigh_t,
            "nape_y": nape_y, "nape_z": nape_z, "eye_y": eye_y,
            "head_z": -L.head_d * 0.5 - rise * math.sin(stoop),
            "shoulder_w": L.shoulder_w, "arm_len": L.shoulder_y - L.wrist_y + L.hand_l}


# ===========================================================================
#  調査兵団
# ===========================================================================
SOLDIER_HAIR = {
    # エレン: 首にかかる長さのくせ毛、前髪は眉にかかる
    "eren_yeager": {"cap": {"y": 0.76, "h": 0.36, "out": 0.05, "crown": True},
                    "back": {"y": 0.10, "h": 0.70, "t": 0.17},
                    "bangs": {"y": 0.78, "low": [0.58, 0.64, 0.56, 0.62, 0.57, 0.63],
                              "t": 0.14, "layer2": 0.5},
                    "sides": {"y": 0.16, "h": 0.56, "t": 0.13, "d": 0.56, "tip": 0.08},
                    "spikes": [(-0.22, 1.06, 0.14, -24), (0.20, 1.07, 0.12, -30)]},
    # ミカサ: 顎の長さで切り揃えた黒髪、顔の脇に長い一房
    "mikasa_ackerman": {"cap": {"y": 0.78, "h": 0.34, "out": 0.045},
                        "back": {"y": 0.06, "h": 0.74, "t": 0.16},
                        "bangs": {"y": 0.80, "low": [0.62, 0.60, 0.64, 0.64, 0.60, 0.62],
                                  "t": 0.14, "layer2": 0.5},
                        "sides": {"y": 0.0, "h": 0.66, "t": 0.13, "d": 0.62, "tip": 0.10}},
    # アルミン: 金のおかっぱ
    "armin_arlert": {"cap": {"y": 0.76, "h": 0.36, "out": 0.06, "crown": True},
                     "back": {"y": 0.10, "h": 0.70, "t": 0.18},
                     "bangs": {"y": 0.78, "low": [0.60, 0.59, 0.60, 0.60, 0.59, 0.60],
                               "t": 0.16, "layer2": 0.55},
                     "sides": {"y": 0.06, "h": 0.66, "t": 0.15, "d": 0.64}},
    # リヴァイ: 刈り上げ＋真ん中分けの前髪
    "levi_ackerman": {"cap": {"y": 0.80, "h": 0.32, "out": 0.04},
                      "back": {"y": 0.52, "h": 0.36, "t": 0.12},
                      "bangs": {"y": 0.82, "low": [0.62, 0.66, 0.74, 0.74, 0.66, 0.62],
                                "t": 0.12, "layer2": 0.5, "parting": 0.0},
                      "shaved": True},
    # ハンジ: 無造作な一つ結び
    "hange_zoe": {"cap": {"y": 0.78, "h": 0.34, "out": 0.05, "crown": True},
                  "back": {"y": 0.30, "h": 0.54, "t": 0.14},
                  "bangs": {"y": 0.80, "low": [0.60, 0.68, 0.62, 0.70, 0.61, 0.66],
                            "t": 0.12},
                  "sides": {"y": 0.10, "h": 0.60, "t": 0.11, "d": 0.42, "tip": 0.12}},
    # エルヴィン: 七三分けの金髪
    "erwin_smith": {"cap": {"y": 0.82, "h": 0.30, "out": 0.04, "crown": True},
                    "back": {"y": 0.40, "h": 0.46, "t": 0.12},
                    "bangs": {"y": 0.86, "low": [0.80, 0.80, 0.82, 0.84, 0.86, 0.86], "t": 0.10},
                    "pompadour": {"h": 0.20}, "shaved": True},
    # ジャン: ツーブロック（上は明るい茶、刈り上げは濃い茶）
    "jean_kirstein": {"cap": {"y": 0.82, "h": 0.30, "out": 0.04},
                      "back": {"y": 0.50, "h": 0.36, "t": 0.12},
                      "bangs": {"y": 0.84, "low": [0.70, 0.74, 0.72, 0.76, 0.72, 0.75],
                                "t": 0.12, "parting": 0.2}},
    # サシャ: 高めのポニーテール
    "sasha_blouse": {"cap": {"y": 0.78, "h": 0.34, "out": 0.045},
                     "back": {"y": 0.36, "h": 0.48, "t": 0.14},
                     "bangs": {"y": 0.80, "low": [0.64, 0.70, 0.66, 0.68, 0.66, 0.64],
                               "t": 0.12, "parting": -0.1},
                     "sides": {"y": 0.08, "h": 0.64, "t": 0.11, "d": 0.40}},
    # コニー: 坊主頭
    "connie_springer": {"cap": {"y": 0.70, "h": 0.40, "out": 0.015}},
    "survey_soldier": {"cap": {"y": 0.80, "h": 0.32, "out": 0.035},
                       "back": {"y": 0.34, "h": 0.48, "t": 0.14},
                       "bangs": {"y": 0.82, "low": [0.71, 0.73, 0.69, 0.72, 0.69, 0.72],
                                 "t": 0.13, "layer2": 0.5},
                       "sides": {"y": 0.36, "h": 0.32, "t": 0.11, "d": 0.42}},
}

SOLDIER_BUILD = {
    # 身長は公式プロフィール（進撃の巨人の 850 年時点）、等身は作画からの推定
    "eren_yeager": dict(cm=170, heads=7.2, sh=0.245, limb=0.98, face={"expr": "stern"}),
    "mikasa_ackerman": dict(cm=170, heads=7.4, sh=0.236, limb=0.94, female=True,
                            face={"expr": "stern"}),
    "armin_arlert": dict(cm=163, heads=6.8, sh=0.228, limb=0.88, face={}),
    "levi_ackerman": dict(cm=160, heads=7.0, sh=0.244, limb=0.98,
                          face={"expr": "narrow", "brow_tilt": 1}),
    "hange_zoe": dict(cm=170, heads=7.3, sh=0.236, limb=0.92, female=True,
                      face={"glasses": True}),
    "erwin_smith": dict(cm=188, heads=7.8, sh=0.262, limb=1.10, bulk=1.08,
                        face={"expr": "stern"}),
    "jean_kirstein": dict(cm=175, heads=7.4, sh=0.248, limb=0.98, face={"expr": "stern"}),
    "sasha_blouse": dict(cm=168, heads=7.2, sh=0.230, limb=0.92, female=True,
                         face={"smile": True}),
    "connie_springer": dict(cm=158, heads=6.8, sh=0.236, limb=0.94, face={"smile": True}),
    "survey_soldier": dict(cm=175, heads=7.3, sh=0.244, limb=1.0, face={}),
}


def build_soldier(key: str) -> Model:
    c = SOLDIER_BUILD[key]
    m = Model(f"geometry.aot.{key}", uv_scale=3, visible_bounds=(3.4, 3.6),
              vb_offset=(0, 1.2, 0), max_atlas=(1024, 1024))
    build = Build(c["cm"], c["heads"], c["sh"], c["limb"], female=c.get("female", False),
                  bulk=c.get("bulk", 1.0))
    face = dict(c.get("face") or {})
    if c.get("female"):
        face.setdefault("lashes", True)
    rig = HumanRig(m, build, styles={"suit": "shirt", "underlay": "pants", "cloth": "pants"})
    rig.flesh(skin="skin", suit="shirt", hands_bare=True, face=face)
    # 脚は白いズボン（flesh は脚にも suit を使うので塗り替える）
    for side in ("right", "left"):
        for bn in (f"{side}Leg", f"{side}Shin"):
            for cube in rig.b(bn).cubes:
                cube.style = "pants"
        for bn in (f"{side}Foot", f"{side}Toe"):
            for cube in rig.b(bn).cubes:
                cube.style = "boots"
    for cube in rig.b("body").cubes:
        if cube.origin[1] < rig.L.abdomen_bot - 0.01:
            cube.style = "pants"
    fr = Frame.npc(rig)
    jacket(fr)
    harness(fr, pants=False)
    boots(fr)
    odm_device(fr)
    cloak(fr)
    rig.hair(SOLDIER_HAIR[key])
    L = rig.L
    head = rig.b("head")
    if key == "jean_kirstein":                       # 刈り上げの濃い茶
        rig.hair({"shaved": True}, style="hair2")
    if key == "sasha_blouse":
        rig.ponytail("tail", (0.0, 0.62, 0.50), 3, 1.5, 0.30, tilt=14)
    if key == "hange_zoe":
        rig.ponytail("tail", (0.0, 0.50, 0.50), 3, 1.0, 0.28, tilt=10)
        # 額に上げたゴーグル
        head.add(Cube((-L.head_w * 0.56, L.chin + L.head_h * 0.78, -L.head_d * 0.62),
                      (L.head_w * 1.12, L.head_h * 0.16, L.head_d * 1.16), "goggle",
                      uv_scale=6, decals={"north": "goggle_lens"}))
    neck = rig.b("neck")
    if key == "mikasa_ackerman":                     # 赤いマフラー
        neck.add(Cube((-L.head_w * 0.42, L.shoulder_y - L.neck_h * 0.4, -L.head_d * 0.34),
                      (L.head_w * 0.84, L.neck_h * 1.5, L.head_d * 0.68), "scarf", uv_scale=6,
                      decals={"north": "scarf_fold"}))
        tail = m.bone("scarf_tail", (L.head_w * 0.2, L.shoulder_y - L.neck_h * 0.2,
                                     -L.head_d * 0.34), "chest", rotation=(-8, 0, 6))
        rig.bones["scarf_tail"] = tail
        tail.add(Cube((L.head_w * 0.08, L.shoulder_y - L.total * 0.16, -L.head_d * 0.42),
                      (L.head_w * 0.30, L.total * 0.16, L.head_d * 0.14), "scarf", uv_scale=5))
    if key == "levi_ackerman":                       # 白いクラバット
        neck.add(Cube((-L.head_w * 0.36, L.shoulder_y - L.neck_h * 0.3, -L.head_d * 0.30),
                      (L.head_w * 0.72, L.neck_h * 1.3, L.head_d * 0.60), "cravat", uv_scale=6))
        rig.b("chest").add(Cube((-L.chest_w * 0.12, L.chest_top - (L.chest_top - L.chest_bot) * 0.42,
                                 -L.chest_d * 0.62),
                                (L.chest_w * 0.24, (L.chest_top - L.chest_bot) * 0.44,
                                 L.chest_d * 0.12), "cravat", uv_scale=6))
    if key == "erwin_smith":                         # ループタイ（緑の石）
        rig.b("chest").add(Cube((-L.chest_w * 0.06, L.chest_top - (L.chest_top - L.chest_bot) * 0.26,
                                 -L.chest_d * 0.66),
                                (L.chest_w * 0.12, (L.chest_top - L.chest_bot) * 0.12,
                                 L.chest_d * 0.10), "bolo", uv_scale=8, decals={"north": "gem"}))
    blades_in_hands(rig)
    m.pack()
    return m


# ===========================================================================
#  プレイヤーが着る装備（アタッチャブル）
# ===========================================================================
def build_wear(kind: str) -> Model:
    m = Model(f"geometry.aot.wear_{kind}", uv_scale=4, visible_bounds=(3, 3),
              vb_offset=(0, 1.0, 0), max_atlas=(1024, 1024))
    fr = Frame.player(m)
    if kind == "jacket":
        jacket(fr)
        cloak(fr)
    elif kind == "odm_gear":
        harness(fr, pants=True)
        odm_device(fr)
    elif kind == "boots":
        boots(fr)
    m.pack()
    # 何も付かないボーンは消す（アタッチャブルの空ボーンは害は無いが軽くする）
    m.bones = [b for b in m.bones if b.cubes or b.name in ("body", "cloak")
               or any(c.parent == b.name for c in m.bones)]
    return m


# ===========================================================================
#  手に持つもの（アタッチャブルとアイコン用）
# ===========================================================================
def build_blades_item() -> Model:
    """右手と左手に一振りずつ。左はバインドを入れ替えた別ボーン（超次元の双剣と同じ）。"""
    m = Model("geometry.aot.blades", uv_scale=4, visible_bounds=(4, 4), vb_offset=(0, 1, 0),
              max_atlas=(512, 512))
    hold = m.bone("hold", (0, 0, 0), binding="q.item_slot_to_bone_name(c.item_slot)")
    root = m.bone("root", (0, 0, 0), "hold")
    blade_geo(root)
    hold_l = m.bone("hold_l", (0, 0, 0),
                    binding="c.item_slot == 'main_hand' ? 'leftitem' : 'rightitem'")
    left = m.bone("left", (0, 0, 0), "hold_l")
    blade_geo(left, flip=True)
    _ = hold, hold_l
    m.pack()
    return m


def build_spear_item() -> Model:
    m = Model("geometry.aot.thunder_spear", uv_scale=4, visible_bounds=(3, 3),
              vb_offset=(0, 1, 0), max_atlas=(256, 256))
    hold = m.bone("hold", (0, 0, 0), binding="q.item_slot_to_bone_name(c.item_slot)")
    root = m.bone("root", (0, 0, 0), "hold")
    spear_geo(root)
    _ = hold
    m.pack()
    return m


def build_spear_projectile() -> Model:
    m = Model("geometry.aot.spear_projectile", uv_scale=4, visible_bounds=(2, 2),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    root = m.bone("body", (0, 0, 0))
    spear_geo(root, (0, 0, 8), 1.0)
    m.pack()
    return m


# ---- アイコン用の小物 --------------------------------------------------------
def build_prop(kind: str) -> Model:
    m = Model(f"geometry.aot.prop_{kind}", uv_scale=6, visible_bounds=(2, 2), vb_offset=(0, 0, 0),
              max_atlas=(512, 512))
    b = m.bone("root", (0, 0, 0))
    if kind == "gas_canister":
        cbox(b, (0, 0, 0), (4, 4, 11), "tank", uv_scale=6, decals={"up": "tank_bands",
                                                                   "east": "tank_bands"})
        cbox(b, (0, 0, -6.2), (2, 2, 1.6), "steel_dark", uv_scale=8)
        cbox(b, (0, 0, -7.4), (1.2, 1.2, 1.0), "brass", uv_scale=8)
        cbox(b, (0, 2.3, 0), (0.8, 0.8, 8), "steel", uv_scale=8)
    elif kind == "spare_blades":
        for i in range(3):
            cbox(b, (i * 0.9 - 0.9, i * 0.5, 0), (0.5, 2.2, 15), "blade", uv_scale=6,
                 decals={"east": {"name": "blade_segments", "n": 6}})
            cbox(b, (i * 0.9 - 0.9, i * 0.5 - 1.15, 0), (0.3, 0.3, 15), "edge", uv_scale=8)
    elif kind == "hardened_steel":
        cbox(b, (0, 0, 0), (7, 2.6, 4), "blade", uv_scale=6)
        cbox(b, (0, 1.5, 0), (6, 0.6, 3.2), "steel", uv_scale=6)
    elif kind == "journal":
        cbox(b, (0, 0, 0), (7, 9, 1.6), "book", uv_scale=6,
             decals={"north": {"name": "wings", "size": 0.62, "cv": 0.48}})
        cbox(b, (0.2, 0, 0.1), (6.4, 8.4, 1.3), "paper", uv_scale=6)
    elif kind == "flare_gun":
        cbox(b, (0, 0.8, -2.0), (1.8, 1.8, 7), "steel_dark", uv_scale=6)
        cbox(b, (0, 1.0, -6.0), (2.6, 2.6, 2.0), "steel", uv_scale=6)
        cbox(b, (0, -2.0, 0.8), (1.6, 4.4, 2.0), "grip", uv_scale=6, rotation=(14, 0, 0))
        for i, col in enumerate(("#3fbf5a", "#d03030", "#202020")):
            cbox(b, (-2.6 + i * 1.6, -3.6, -3.0), (1.2, 1.2, 2.6), "paper", uv_scale=8,
                 decals={"north": {"name": "flare_band", "colour": col},
                         "up": {"name": "flare_band", "colour": col}})
    m.pack()
    return m


# ===========================================================================
def emit(model: Model, palette: dict, name: str, seed: int = 7, tex_name=None):
    os.makedirs(GEO_DIR, exist_ok=True)
    os.makedirs(TEX_DIR, exist_ok=True)
    model.write(os.path.join(GEO_DIR, f"{name}.geo.json"))
    p = AotPainter(model.tex_w, model.tex_h, seed)
    p.paint_model(model, palette)
    p.save(os.path.join(TEX_DIR, f"{tex_name or name}.png"))
    return model


def emit_textures(model: Model, palettes, names, seed=7):
    os.makedirs(TEX_DIR, exist_ok=True)
    for i, (pal, tex) in enumerate(zip(palettes, names)):
        p = AotPainter(model.tex_w, model.tex_h, seed + i)
        p.paint_model(model, pal)
        p.save(os.path.join(TEX_DIR, f"{tex}.png"))


def main() -> None:
    import mctexture
    print("models:")
    for body in BODIES:
        m = build_titan(body)
        os.makedirs(GEO_DIR, exist_ok=True)
        m.write(os.path.join(GEO_DIR, f"titan_{body}.geo.json"))
        emit_textures(m, PAL.TITAN_PALETTES, [f"titan_{body}_{k}" for k in range(C.SKINS)],
                      seed=mctexture._h(body) % 9000)
        print(f"  titan_{body:10s} {m.stats()}")
    for key in C.SOLDIERS:
        m = emit(build_soldier(key), PAL.PEOPLE[key], key, mctexture._h(key) % 9000)
        print(f"  {key:18s} {m.stats()}")
    for kind in ("jacket", "odm_gear", "boots"):
        m = emit(build_wear(kind), PAL.GEAR, f"wear_{kind}", 31)
        print(f"  wear_{kind:13s} {m.stats()}")
    m = emit(build_blades_item(), PAL.GEAR, "blades", 41)
    print(f"  blades             {m.stats()}")
    m = emit(build_spear_item(), PAL.GEAR, "thunder_spear", 42)
    print(f"  thunder_spear      {m.stats()}")
    m = emit(build_spear_projectile(), PAL.GEAR, "spear_projectile", 43)
    for kind in ("gas_canister", "spare_blades", "hardened_steel", "journal", "flare_gun"):
        emit(build_prop(kind), PAL.GEAR, f"prop_{kind}", 50)


if __name__ == "__main__":
    main()
