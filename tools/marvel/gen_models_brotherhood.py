# -*- coding: utf-8 -*-
"""ブラザーフッド9人のモデル。

体格は contract.CHARACTERS の cm / heads / sh / limb / bulk から導く。
同じ ``HumanRig`` を使いつつ、キャラごとの装飾を ``DRESS`` の関数で足す。
"""
from __future__ import annotations

import _path  # noqa: F401

import colours  # noqa: E402
import contract as K  # noqa: E402
from common import emit  # noqa: E402
from mcmodel import Cube, Model  # noqa: E402
from rig import Build, HumanRig  # noqa: E402


# ---------------------------------------------------------------- 髪型
HAIR = {
    "mystique": [((-0.52, 0.60, -0.52), (1.04, 0.48, 1.06)),
                 ((-0.54, 0.34, 0.40), (1.08, 0.42, 0.20)),
                 ((-0.56, 0.44, -0.46), (0.14, 0.44, 0.92)),
                 ((0.42, 0.44, -0.46), (0.14, 0.44, 0.92))],
    "sabretooth": [((-0.58, 0.56, -0.58), (1.16, 0.52, 1.18)),
                   ((-0.60, 0.10, 0.34), (1.20, 0.62, 0.34)),
                   ((-0.62, 0.20, -0.50), (0.18, 0.52, 1.10)),
                   ((0.44, 0.20, -0.50), (0.18, 0.52, 1.10))],
    "toad": [((-0.52, 0.62, -0.50), (1.04, 0.40, 1.02)),
             ((-0.52, 0.40, 0.38), (1.04, 0.26, 0.16))],
    "juggernaut": [((-0.52, 0.64, -0.52), (1.04, 0.40, 1.04))],
    "quicksilver": [((-0.52, 0.60, -0.54), (1.04, 0.48, 1.08)),
                    ((-0.54, 0.58, -0.62), (1.08, 0.34, 0.18)),
                    ((-0.26, 1.02, -0.24), (0.24, 0.20, 0.28))],
    "pyro": [((-0.52, 0.60, -0.54), (1.04, 0.46, 1.08)),
             ((-0.54, 0.56, -0.62), (1.08, 0.32, 0.16))],
    "avalanche": [((-0.52, 0.62, -0.52), (1.04, 0.44, 1.06)),
                  ((-0.52, 0.36, 0.40), (1.04, 0.30, 0.16))],
    "blob": [((-0.50, 0.66, -0.50), (1.00, 0.34, 1.00))],
    "scarlet_witch": [((-0.53, 0.60, -0.54), (1.06, 0.48, 1.10)),
                      ((-0.55, 0.56, -0.62), (1.10, 0.34, 0.16)),
                      ((-0.58, 0.00, -0.48), (0.16, 0.62, 1.02)),
                      ((0.42, 0.00, -0.48), (0.16, 0.62, 1.02)),
                      ((-0.40, 0.10, 0.40), (0.80, 0.56, 0.24))]}


# ---------------------------------------------------------------- 衣装
def _bodysuit(rig, style="suit", chest_decal=None):
    L = rig.L
    ch = L.chest_top - L.chest_bot
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.54, L.chest_bot + ch * 0.04, -L.chest_d * 0.60),
        (L.chest_w * 1.08, ch * 0.90, L.chest_d * 1.20), style, uv_scale=4,
        decals={"north": chest_decal} if chest_decal else None))


def _belt(rig, style="belt"):
    L = rig.L
    rig.b("body").add(Cube(
        (-L.hip_w * 0.58, L.abdomen_bot - L.total * 0.016, -L.waist_d * 0.62),
        (L.hip_w * 1.16, L.total * 0.034, L.waist_d * 1.24), style, uv_scale=5,
        decals={"north": "brotherhood_mark"}))


def _boots(rig, style="boot"):
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        lx = sgn * L.stance
        rig.b(f"{side}Shin").add(Cube(
            (lx - L.shin_t * 0.68, L.ankle_y, -L.shin_t * 0.74),
            (L.shin_t * 1.36, (L.knee_y - L.ankle_y) * 0.68, L.shin_t * 1.28),
            style, uv_scale=4))
        rig.b(f"{side}Foot").add(Cube(
            (lx - L.shin_t * 0.66, 0, -L.foot_l * 0.66),
            (L.shin_t * 1.32, L.foot_h * 1.14, L.foot_l * 0.64), style,
            uv_scale=4))


def _claws(rig, style="claw"):
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        hand = rig.b(f"{side}Hand")
        for i in range(3):
            u = (i - 1) * 0.34
            t = L.forearm_t * 0.22
            hand.add(Cube((cx + u * L.forearm_t - t / 2,
                           L.wrist_y - L.hand_l * 1.9, -L.forearm_t * 0.28),
                          (t, L.hand_l * 0.9, t * 1.2), style, uv_scale=5,
                          rotation=(14, 0, 0)))


def dress_mystique(rig):
    _bodysuit(rig, "suit")
    _belt(rig)
    _boots(rig, "cloth")


def dress_sabretooth(rig):
    L = rig.L
    _bodysuit(rig, "suit")
    _belt(rig)
    _boots(rig, "cloth")
    _claws(rig)
    # 鬣（たてがみ）
    rig.b("chest").add(Cube(
        (-L.shoulder_w * 0.52, L.chest_top - L.total * 0.05, -L.chest_d * 0.60),
        (L.shoulder_w * 1.04, L.total * 0.09, L.chest_d * 1.24), "fur",
        uv_scale=3))


def dress_toad(rig):
    L = rig.L
    _bodysuit(rig, "suit")
    _boots(rig, "cloth")
    # 喉袋
    rig.b("neck").add(Cube(
        (-L.head_w * 0.30, L.shoulder_y - L.neck_h * 0.2, -L.head_d * 0.36),
        (L.head_w * 0.60, L.neck_h * 1.1, L.head_d * 0.24), "skin", uv_scale=5))


def dress_juggernaut(rig):
    L = rig.L
    _bodysuit(rig, "suit")
    _belt(rig)
    _boots(rig, "armor")
    head = rig.b("head")
    # ドーム型のヘルメット（顔が見えない）
    head.add(Cube((-L.head_w * 0.62, L.chin + L.head_h * 0.02, -L.head_d * 0.62),
                  (L.head_w * 1.24, L.head_h * 1.06, L.head_d * 1.24), "helm",
                  uv_scale=4, decals={"north": "vent_grill"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - L.arm_t * 0.90, L.shoulder_y - L.arm_t * 1.10, -L.arm_t * 0.90),
            (L.arm_t * 1.80, L.arm_t * 1.30, L.arm_t * 1.80), "armor",
            uv_scale=3, decals={"up": "rivets"}))


def dress_quicksilver(rig):
    _bodysuit(rig, "suit")
    _belt(rig, "accent")
    _boots(rig, "armor")


def dress_pyro(rig):
    L = rig.L
    _bodysuit(rig, "suit")
    _belt(rig)
    _boots(rig, "cloth")
    # 背中の燃料タンク
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.34, L.chest_bot + (L.chest_top - L.chest_bot) * 0.10,
         L.chest_d * 0.42),
        (L.chest_w * 0.68, (L.chest_top - L.chest_bot) * 0.74, L.chest_d * 0.34),
        "armor", uv_scale=4, decals={"south": "panel_seam"}))


def dress_avalanche(rig):
    L = rig.L
    _bodysuit(rig, "suit")
    _belt(rig)
    _boots(rig, "armor")
    rig.b("head").add(Cube(
        (-L.head_w * 0.56, L.chin + L.head_h * 0.42, -L.head_d * 0.62),
        (L.head_w * 1.12, L.head_h * 0.24, L.head_d * 0.16), "goggle",
        uv_scale=6, decals={"north": "goggles"}))


def dress_blob(rig):
    L = rig.L
    _bodysuit(rig, "gut")
    _belt(rig)
    # 腹の張り出し
    rig.b("body").add(Cube(
        (-L.waist_w * 0.62, L.pelvis_bot, -L.waist_d * 0.78),
        (L.waist_w * 1.24, L.chest_bot - L.pelvis_bot, L.waist_d * 1.56), "gut",
        uv_scale=3))


def dress_scarlet_witch(rig):
    L = rig.L
    _bodysuit(rig, "suit", chest_decal="hex_sigil")
    _belt(rig, "armor")
    _boots(rig, "cloth")
    # 短いマント
    bone = rig.model.bone("cape0", (0, L.chest_top, L.chest_d * 0.5), "chest",
                          rotation=(5, 0, 0))
    rig.bones["cape0"] = bone
    bone.add(Cube((-L.shoulder_w * 0.52, L.chest_top - L.total * 0.36,
                   L.chest_d * 0.50),
                  (L.shoulder_w * 1.04, L.total * 0.36, L.total * 0.010),
                  "cape", uv_scale=2, decals={"north": "cape_fold"}))
    # 頭飾り
    rig.b("head").add(Cube(
        (-L.head_w * 0.50, L.chin + L.head_h * 0.78, -L.head_d * 0.56),
        (L.head_w * 1.00, L.head_h * 0.30, L.head_d * 0.20), "armor",
        uv_scale=5, decals={"north": "hex_sigil"}))


DRESS = {
    "mystique": dress_mystique,
    "sabretooth": dress_sabretooth,
    "toad": dress_toad,
    "juggernaut": dress_juggernaut,
    "quicksilver": dress_quicksilver,
    "pyro": dress_pyro,
    "avalanche": dress_avalanche,
    "blob": dress_blob,
    "scarlet_witch": dress_scarlet_witch,
}


def build(key: str) -> Model:
    c = K.CHARACTERS[key]
    m = Model(K.geo(key), uv_scale=3, visible_bounds=(3.6, 4.0),
              vb_offset=(0, 1.3, 0), max_atlas=(512, 512))
    rig = HumanRig(m, Build(c["cm"], c["heads"], c["sh"], c["limb"],
                            female=c["female"], bulk=c["bulk"],
                            hunch=c.get("hunch", 0.0)),
                   player_rig=True)
    rig.flesh()
    DRESS[key](rig)
    if key in HAIR:
        rig.hair(HAIR[key])
    return m


def main() -> None:
    print("brotherhood:")
    for key in K.BROTHERHOOD:
        emit(build(key), colours.ALL[K.CHARACTERS[key]["pal"]], key,
             seed=abs(hash(key)) % 9000 + 7)


if __name__ == "__main__":
    main()
