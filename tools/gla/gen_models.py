# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — 3Dモデルとテクスチャ (企画書 §04 / §05 / §06)。

形態ごとに「同じモデルの色替え」で済ませないための作り分けをここに置く:

* 通常とギア2は基本造形を共有し、前傾・肌の色味・蒸気だけを変える
* ギア3は通常の輪郭のまま、前腕と脛に膨張用の別パーツを持たせる
  （胴体まで一律に巨大化させない。技中の拡大はアニメ側の scale で行う）
* ギア4はバウンドマンとスネイクマンで体型そのものを分ける
* ギア5は髪・眉・口・雲を個別のボーンにして、演出から別々に動かせるようにする

どの形態も、変身中のプレイヤーにアタッチャブルとして着せる前提なので、
関節の枢軸をバニラのプレイヤー骨格へ固定してある (player_anchor / player_rig)。
これを外すとボーンがプレイヤー側の位置へ引き寄せられてモデルが崩れる。
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import mctexture                                        # noqa: E402
from mcmodel import Cube, Model                         # noqa: E402
from mctexture import Painter                           # noqa: E402
from rig import Build, HumanRig                         # noqa: E402

import palette                                          # noqa: E402
import spec                                             # noqa: E402

RP = os.path.join(ROOT, spec.RP_DIR)
GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", spec.NS)


def emit(model: Model, pal: dict, geo_name: str, tex_name: str,
         seed: int | None = None) -> Model:
    """pack → geo.json → Painter → png。この順序は入れ替えられない。

    Painter は model.tex_w / tex_h を読むので、pack() より前に作ると 0x0 の
    空 PNG ができる。model.write() が pack 済みでなければ pack してくれる。
    """
    os.makedirs(GEO_DIR, exist_ok=True)
    os.makedirs(TEX_DIR, exist_ok=True)
    model.write(os.path.join(GEO_DIR, geo_name + ".geo.json"))
    if seed is None:
        seed = mctexture._h(geo_name) % 9000
    p = Painter(model.tex_w, model.tex_h, seed)
    p.paint_model(model, pal)
    p.save(os.path.join(TEX_DIR, tex_name + ".png"))
    print(f"  {geo_name:30s} {model.stats()}")
    return model


# ===========================================================================
#  ルフィの顔と髪
# ===========================================================================
#  企画書 §06「顔が小画面で読める」。目を大きめ、眉は水平寄り、口角を上げる。
FACE_NORMAL = dict(eye_w=0.23, eye_h=0.17, eye_v=0.50, eye_gap=0.10,
                   brow_tilt=0, smile=True)
FACE_FOCUS = dict(eye_w=0.23, eye_h=0.13, eye_v=0.50, eye_gap=0.10,
                  brow_tilt=1, expr="narrow")
FACE_NIKA = dict(eye_w=0.25, eye_h=0.18, eye_v=0.49, eye_gap=0.11,
                 brow_tilt=0, smile=True, no_brow=True)

#  黒い短髪。房の前後差を出すため spikes を散らす。
HAIR_LUFFY = {
    "cap": {"y": 0.58, "h": 0.52, "out": 0.05, "crown": True},
    "back": {"y": 0.26, "h": 0.46, "t": 0.17},
    "bangs": {"y": 0.64, "low": [0.58, 0.52, 0.56, 0.54, 0.51, 0.59],
              "t": 0.15, "layer2": 0.55},
    "sides": {"t": 0.14, "h": 0.42, "y": 0.22, "z0": -0.52, "d": 0.60,
              "tip": 0.10},
    "spikes": [(-0.32, 0.98, 0.20, -16), (-0.15, 1.02, 0.24, -24),
               (0.02, 1.03, 0.26, -9), (0.19, 1.01, 0.22, -20),
               (0.33, 0.97, 0.19, -6)],
}

#  ニカの髪。房を長く、上へ大きく広げる。色はパレット側で白に振る。
HAIR_NIKA = {
    "cap": {"y": 0.58, "h": 0.54, "out": 0.07, "crown": True},
    "back": {"y": 0.18, "h": 0.56, "t": 0.20},
    "bangs": {"y": 0.66, "low": [0.60, 0.54, 0.58, 0.56, 0.53, 0.61],
              "t": 0.17, "layer2": 0.60},
    "sides": {"t": 0.16, "h": 0.48, "y": 0.16, "z0": -0.54, "d": 0.64,
              "tip": 0.14},
    "spikes": [(-0.42, 1.00, 0.34, -30), (-0.24, 1.06, 0.42, -20),
               (-0.06, 1.09, 0.46, -8), (0.12, 1.07, 0.42, -14),
               (0.30, 1.03, 0.36, -26), (0.44, 0.98, 0.28, -36),
               (-0.34, 0.92, 0.26, -46), (0.38, 0.90, 0.24, 44)],
}


def straw_hat(rig: HumanRig, on: str = "head") -> None:
    """麦わら帽子。つば・山・赤い帯の3段。輪郭が主役なので薄く広く作る。"""
    L = rig.L
    bone = rig.b(on)
    top = L.chin + L.head_h * 0.94
    brim_w = L.head_w * 1.78
    brim_d = L.head_d * 1.62
    # つば — 1枚の薄い板だと安っぽいので、外周を一段下げて厚みを付ける
    bone.add(Cube((-brim_w / 2, top - L.head_h * 0.06, -brim_d * 0.52),
                  (brim_w, L.head_h * 0.06, brim_d), "straw", uv_scale=3))
    bone.add(Cube((-brim_w * 0.40, top - L.head_h * 0.11, -brim_d * 0.42),
                  (brim_w * 0.80, L.head_h * 0.05, brim_d * 0.82), "straw",
                  uv_scale=3))
    # 山
    bone.add(Cube((-L.head_w * 0.58, top, -L.head_d * 0.60),
                  (L.head_w * 1.16, L.head_h * 0.30, L.head_d * 1.16),
                  "straw", uv_scale=4))
    bone.add(Cube((-L.head_w * 0.50, top + L.head_h * 0.28, -L.head_d * 0.52),
                  (L.head_w * 1.00, L.head_h * 0.07, L.head_d * 1.00),
                  "straw", uv_scale=4))
    # 赤い帯
    bone.add(Cube((-L.head_w * 0.60, top + L.head_h * 0.03, -L.head_d * 0.62),
                  (L.head_w * 1.20, L.head_h * 0.09, L.head_d * 1.20),
                  "hatband", uv_scale=5))
    # つばの縁 — 四角い板に見せないよう、外周を8枚で丸める (企画書 §06 帽子の縁)
    for i in range(8):
        a = (i / 8.0) * math.pi * 2
        ex = math.cos(a) * brim_w * 0.44
        ez = math.sin(a) * brim_d * 0.44
        bone.add(Cube((ex - brim_w * 0.13, top - L.head_h * 0.085,
                       ez - brim_d * 0.13),
                      (brim_w * 0.26, L.head_h * 0.05, brim_d * 0.26),
                      "straw", uv_scale=4, rotation=(0, -math.degrees(a), 6)))


def chest_scar(rig: HumanRig) -> None:
    """胸の傷。デカールだと遠目で消えるので、細い立体を2本たすき掛けにする。"""
    L = rig.L
    chest = rig.b("chest")
    y = L.chest_bot + (L.chest_top - L.chest_bot) * 0.28
    h = (L.chest_top - L.chest_bot) * 0.62
    for sgn, rot in ((-1, 26.0), (1, -26.0)):
        chest.add(Cube((sgn * L.chest_w * 0.06 - L.chest_w * 0.05, y,
                        -L.chest_d * 0.56),
                       (L.chest_w * 0.10, h, L.chest_d * 0.06), "scar",
                       uv_scale=6, rotation=(0, 0, rot)))


def eye_scar(rig: HumanRig) -> None:
    """左目の下の小さな傷。"""
    L = rig.L
    rig.b("head").add(Cube(
        (L.head_w * 0.10, L.chin + L.head_h * 0.40, -L.head_d * 0.55),
        (L.head_w * 0.05, L.head_h * 0.13, L.head_d * 0.04), "scar",
        uv_scale=8))


def anatomy(rig: HumanRig, skin: str = "skin") -> None:
    """胸郭・腹・肩・骨盤の連続性を作る (企画書 §06)。

    胴体が直方体1個に見えないよう、胸筋・腹・脇腹・肩甲骨を重ねる。
    腕を上げたときに首や脇へ穴が空かないよう、継ぎ目には必ず塊を置く。
    """
    L = rig.L
    chest = rig.b("chest")
    body = rig.b("body")
    ch = L.chest_top - L.chest_bot

    # 胸筋 — 左右を割って、間に谷を作る
    for sgn in (-1, 1):
        chest.add(Cube((sgn * L.chest_w * 0.06, L.chest_bot + ch * 0.34,
                        -L.chest_d * 0.56),
                       (L.chest_w * 0.40, ch * 0.40, L.chest_d * 0.16), skin,
                       uv_scale=4))
    # 腹 — 2段
    ab = L.chest_bot - L.abdomen_bot
    for i, w in ((0, 0.60), (1, 0.54)):
        body.add(Cube((-L.waist_w * w * 0.5, L.abdomen_bot + ab * (0.10 + i * 0.42),
                       -L.waist_d * 0.56),
                      (L.waist_w * w, ab * 0.34, L.waist_d * 0.14), skin,
                      uv_scale=4))
    # 脇腹 — 胸から腰への絞り
    for sgn in (-1, 1):
        body.add(Cube((sgn * L.waist_w * 0.42 - L.waist_w * 0.09,
                       L.abdomen_bot, -L.waist_d * 0.40),
                      (L.waist_w * 0.18, ab * 0.92, L.waist_d * 0.80), skin,
                      uv_scale=4))
    # 肩甲骨
    for sgn in (-1, 1):
        chest.add(Cube((sgn * L.chest_w * 0.10, L.chest_bot + ch * 0.38,
                        L.chest_d * 0.42),
                       (L.chest_w * 0.34, ch * 0.42, L.chest_d * 0.14), skin,
                       uv_scale=4))
    # 骨盤
    body.add(Cube((-L.hip_w * 0.46, L.pelvis_bot, -L.waist_d * 0.44),
                  (L.hip_w * 0.92, (L.abdomen_bot - L.pelvis_bot) * 0.42,
                   L.waist_d * 0.88), skin, uv_scale=4))
    # 首の付け根 — 腕上げでも穴を作らない
    rig.b("neck").add(Cube(
        (-L.head_w * 0.36, L.shoulder_y - L.neck_h * 0.6, -L.head_d * 0.30),
        (L.head_w * 0.72, L.neck_h * 0.8, L.head_d * 0.60), skin, uv_scale=4))
    # 脇の詰め物
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        chest.add(Cube((cx - L.arm_t * 0.30 - (0 if sgn > 0 else L.arm_t * 0.20),
                        L.shoulder_y - L.arm_t * 1.25, -L.arm_t * 0.40),
                       (L.arm_t * 0.50, L.arm_t * 0.80, L.arm_t * 0.80), skin,
                       uv_scale=5))
    # 膝と足首 — 走行で折れる位置に塊を置く
    for side, sgn in (("right", -1), ("left", 1)):
        lx = sgn * L.stance
        rig.b(f"{side}Shin").add(Cube(
            (lx - L.thigh_t * 0.52, L.knee_y - (L.knee_y - L.ankle_y) * 0.08,
             -L.thigh_t * 0.54),
            (L.thigh_t * 1.04, (L.knee_y - L.ankle_y) * 0.20, L.thigh_t * 1.02),
            skin, uv_scale=5))
        rig.b(f"{side}Foot").add(Cube(
            (lx - L.shin_t * 0.48, L.ankle_y, -L.shin_t * 0.50),
            (L.shin_t * 0.96, L.foot_h * 0.9, L.shin_t * 0.96), skin,
            uv_scale=5))


def fingers(rig: HumanRig, skin: str = "skin") -> None:
    """指。伸ばす拳が主役の企画なので、手だけは必ず作り込む。"""
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        hand = rig.b(f"{side}Hand")
        w = L.forearm_t * 0.24
        for i in range(4):
            hand.add(Cube((cx - L.forearm_t * 0.50 + i * w * 1.06,
                           L.wrist_y - L.hand_l * 1.30,
                           -L.forearm_t * 0.38),
                          (w, L.hand_l * 0.46, L.forearm_t * 0.72), skin,
                          uv_scale=6))
        # 拳の山（第2関節）
        hand.add(Cube((cx - L.forearm_t * 0.52, L.wrist_y - L.hand_l * 0.98,
                       -L.forearm_t * 0.46),
                      (L.forearm_t * 1.04, L.hand_l * 0.30, L.forearm_t * 0.30),
                      skin, uv_scale=6))


def face_shape(rig: HumanRig, skin: str = "skin") -> None:
    """頬と顎。正面・斜め・横のどれでも輪郭が読めるようにする (企画書 §06)。"""
    L = rig.L
    head = rig.b("head")
    # 頬
    for sgn in (-1, 1):
        head.add(Cube((sgn * L.head_w * 0.24 - L.head_w * 0.13,
                       L.chin + L.head_h * 0.22, -L.head_d * 0.56),
                      (L.head_w * 0.26, L.head_h * 0.26, L.head_d * 0.10),
                      skin, uv_scale=6))
    # 顎
    head.add(Cube((-L.head_w * 0.26, L.chin + L.head_h * 0.02,
                   -L.head_d * 0.48),
                  (L.head_w * 0.52, L.head_h * 0.18, L.head_d * 0.82), skin,
                  uv_scale=6))
    # 鼻すじ
    head.add(Cube((-L.head_w * 0.07, L.chin + L.head_h * 0.36,
                   -L.head_d * 0.58),
                  (L.head_w * 0.14, L.head_h * 0.14, L.head_d * 0.06), skin,
                  uv_scale=8))


def limbs_detail(rig: HumanRig, skin: str = "skin") -> None:
    """肩・胸・腰・脚に太さの差を付ける (企画書 §05)。全身を同じ太さの筒にしない。"""
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        lx = sgn * L.stance
        arm_h = L.shoulder_y - L.elbow_y
        fore_h = L.elbow_y - L.wrist_y
        # 上腕の膨らみ（肘に向かって細くなる）
        rig.b(f"{side}Arm").add(Cube(
            (cx - L.arm_t * 0.56, L.elbow_y + arm_h * 0.30, -L.arm_t * 0.52),
            (L.arm_t * 1.12, arm_h * 0.52, L.arm_t * 1.04), skin, uv_scale=4))
        # 肘
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.58, L.elbow_y - fore_h * 0.14,
             -L.forearm_t * 0.56),
            (L.forearm_t * 1.16, fore_h * 0.22, L.forearm_t * 1.12), skin,
            uv_scale=5))
        # 手首（前腕から手への絞り）
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.40, L.wrist_y, -L.forearm_t * 0.40),
            (L.forearm_t * 0.80, fore_h * 0.14, L.forearm_t * 0.80), skin,
            uv_scale=5))
        # 腿の前後差
        thigh_h = L.hip_y - L.knee_y
        rig.b(f"{side}Leg").add(Cube(
            (lx - L.thigh_t * 0.54, L.knee_y + thigh_h * 0.22,
             -L.thigh_t * 0.56),
            (L.thigh_t * 1.08, thigh_h * 0.56, L.thigh_t * 1.06), skin,
            uv_scale=4))
        # 指先 — サンダルから出るつま先
        toe = rig.b(f"{side}Toe")
        for i in range(3):
            toe.add(Cube((lx - L.shin_t * 0.42 + i * L.shin_t * 0.30,
                          L.ankle_y + L.foot_h * 0.10,
                          -L.foot_l * 0.72),
                         (L.shin_t * 0.26, L.foot_h * 0.60, L.foot_l * 0.16),
                         skin, uv_scale=6))
    # 鎖骨
    for sgn in (-1, 1):
        rig.b("chest").add(Cube(
            (sgn * L.chest_w * 0.10, L.chest_top - L.arm_t * 0.55,
             -L.chest_d * 0.52),
            (L.chest_w * 0.34, L.arm_t * 0.22, L.chest_d * 0.16), skin,
            uv_scale=5, rotation=(0, 0, -sgn * 8)))


def hair_depth(rig: HumanRig, style: str = "hair", long_back: bool = False) -> None:
    """髪束の前後差 (企画書 §06)。cap の上に、奥行きの違う房を重ねる。"""
    L = rig.L
    bone = rig.b("hair")
    rows = ((0.86, -0.30, 0.22), (0.80, 0.10, 0.26), (0.74, 0.42, 0.20))
    for y, z, h in rows:
        for i in range(4):
            u = -0.34 + i * 0.23
            bone.add(Cube((u * L.head_w - L.head_w * 0.11,
                           L.chin + L.head_h * y,
                           z * L.head_d - L.head_d * 0.12),
                          (L.head_w * 0.22, L.head_h * h, L.head_d * 0.24),
                          style, uv_scale=4,
                          rotation=(-10 - i * 3, i * 6 - 9, 0)))
    if long_back:
        for i in range(4):
            u = -0.30 + i * 0.20
            bone.add(Cube((u * L.head_w - L.head_w * 0.10,
                           L.chin + L.head_h * 0.10,
                           L.head_d * 0.34),
                          (L.head_w * 0.20, L.head_h * 0.52, L.head_d * 0.20),
                          style, uv_scale=4, rotation=(12 + i * 4, 0, 0)))


def vest(rig: HumanRig, style: str = "vest", sleeves: bool = False) -> None:
    """前を開けた赤いベスト。素肌を主役にしたいので前身頃を左右に分ける。"""
    L = rig.L
    chest = rig.b("chest")
    top = L.chest_top - L.arm_t * 0.10
    h = (L.chest_top - L.chest_bot) * 1.06
    t = L.chest_d * 0.13
    for sgn in (-1, 1):
        chest.add(Cube((sgn * L.chest_w * 0.14, L.chest_bot - h * 0.16,
                        -L.chest_d * 0.52 - t * 0.5),
                       (L.chest_w * 0.34, h, t), style, uv_scale=4))
    # 背中は1枚で
    chest.add(Cube((-L.chest_w * 0.50, L.chest_bot - h * 0.16,
                    L.chest_d * 0.50 - t * 0.5),
                   (L.chest_w * 1.00, h, t), style, uv_scale=4))
    # 襟 — 首まわりを一周させる
    for dz, w in ((-1, 0.46), (1, 0.52)):
        chest.add(Cube((-L.chest_w * w * 0.5, top - L.arm_t * 0.30,
                        dz * L.chest_d * 0.52 - t * 0.7),
                       (L.chest_w * w, L.arm_t * 0.46, t * 1.4), style,
                       uv_scale=5))
    for sgn in (-1, 1):
        chest.add(Cube((sgn * L.chest_w * 0.42 - L.chest_w * 0.05,
                        top - L.arm_t * 0.30, -L.chest_d * 0.52),
                       (L.chest_w * 0.10, L.arm_t * 0.46, L.chest_d * 1.04),
                       style, uv_scale=5))
    # 裾のしわ — 前身頃の下端を左右で少しずらす
    for sgn, drop in ((-1, 0.16), (1, 0.10)):
        chest.add(Cube((sgn * L.chest_w * 0.14, L.chest_bot - h * (0.16 + drop),
                        -L.chest_d * 0.52 - t * 0.6),
                       (L.chest_w * 0.34, h * drop, t * 1.2), style,
                       uv_scale=5))
    # 肩の縁
    for side, sgn in (("right", -1), ("left", 1)):
        sh = rig.b(f"{side}Shoulder")
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        sh.add(Cube((cx - L.arm_t * 0.62, L.shoulder_y - L.arm_t * 0.92,
                     -L.arm_t * 0.62),
                    (L.arm_t * 1.24, L.arm_t * 0.42, L.arm_t * 1.24), style,
                    uv_scale=4))
        if sleeves:
            arm = rig.b(f"{side}Arm")
            arm.add(Cube((cx - L.arm_t * 0.58, L.elbow_y + (L.shoulder_y - L.elbow_y) * 0.42,
                          -L.arm_t * 0.58),
                         (L.arm_t * 1.16, (L.shoulder_y - L.elbow_y) * 0.55,
                          L.arm_t * 1.16), style, uv_scale=4))


def shorts(rig: HumanRig, style: str = "shorts", sash_style: str = "sash",
           length: float = 0.86) -> None:
    """短パンと帯。腰から腿の途中まで。"""
    L = rig.L
    body = rig.b("body")
    hip_h = L.hip_y - L.pelvis_bot
    body.add(Cube((-L.hip_w * 0.54, L.pelvis_bot - hip_h * 0.30,
                   -L.waist_d * 0.56),
                  (L.hip_w * 1.08, hip_h * 1.42, L.waist_d * 1.12), style,
                  uv_scale=4))
    # 帯
    body.add(Cube((-L.hip_w * 0.56, L.abdomen_bot - hip_h * 0.20,
                   -L.waist_d * 0.58),
                  (L.hip_w * 1.12, hip_h * 0.46, L.waist_d * 1.16), sash_style,
                  uv_scale=5))
    # 結び目
    body.add(Cube((-L.hip_w * 0.14, L.abdomen_bot - hip_h * 0.34,
                   -L.waist_d * 0.66),
                  (L.hip_w * 0.28, hip_h * 0.50, L.waist_d * 0.16), sash_style,
                  uv_scale=6))
    # 裾
    for side, sgn in (("right", -1), ("left", 1)):
        leg = rig.b(f"{side}Leg")
        cx = sgn * L.stance
        drop = (L.hip_y - L.knee_y) * length
        leg.add(Cube((cx - L.thigh_t * 0.60, L.hip_y - drop, -L.thigh_t * 0.60),
                     (L.thigh_t * 1.20, drop, L.thigh_t * 1.20), style,
                     uv_scale=4))


def sandals(rig: HumanRig, style: str = "sandal") -> None:
    """サンダル。厚みを出して素足と区別する。"""
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        foot = rig.b(f"{side}Foot")
        cx = sgn * L.stance
        foot.add(Cube((cx - L.shin_t * 0.62, 0.0, -L.foot_l * 0.62),
                      (L.shin_t * 1.24, L.foot_h * 0.62, L.foot_l * 1.06),
                      style, uv_scale=4))
        # 甲のベルト
        foot.add(Cube((cx - L.shin_t * 0.58, L.foot_h * 0.52, -L.foot_l * 0.36),
                      (L.shin_t * 1.16, L.foot_h * 0.34, L.foot_l * 0.24),
                      style, uv_scale=5))
        # 鼻緒と踵の留め — サンダルの厚みを見せる (企画書 §06)
        foot.add(Cube((cx - L.shin_t * 0.10, L.foot_h * 0.50, -L.foot_l * 0.60),
                      (L.shin_t * 0.20, L.foot_h * 0.40, L.foot_l * 0.26),
                      style, uv_scale=6))
        foot.add(Cube((cx - L.shin_t * 0.52, L.foot_h * 0.48, L.foot_l * 0.26),
                      (L.shin_t * 1.04, L.foot_h * 0.52, L.foot_l * 0.14),
                      style, uv_scale=6))
        foot.add(Cube((cx - L.shin_t * 0.66, 0.0, -L.foot_l * 0.66),
                      (L.shin_t * 1.32, L.foot_h * 0.22, L.foot_l * 1.14),
                      style, uv_scale=5))


def haki_sleeves(rig: HumanRig, upper: bool = True, torso: bool = False,
                 style: str = "haki", line: str = "haki_line") -> None:
    """覇気に覆われた腕。黒い筒に見せないよう、上腕と前腕で太さを変え、
    炎状の模様を別 style の細い立体で入れる (企画書 §06 覇気)。"""
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        if upper:
            arm = rig.b(f"{side}Arm")
            arm.add(Cube((cx - L.arm_t * 0.58, L.elbow_y, -L.arm_t * 0.58),
                         (L.arm_t * 1.16, L.shoulder_y - L.elbow_y,
                          L.arm_t * 1.16), style, uv_scale=4))
        fore = rig.b(f"{side}Forearm")
        fore.add(Cube((cx - L.forearm_t * 0.62, L.wrist_y, -L.forearm_t * 0.62),
                      (L.forearm_t * 1.24, L.elbow_y - L.wrist_y,
                       L.forearm_t * 1.24), style, uv_scale=4))
        hand = rig.b(f"{side}Hand")
        hand.add(Cube((cx - L.forearm_t * 0.60, L.wrist_y - L.hand_l * 1.04,
                       -L.forearm_t * 0.50),
                      (L.forearm_t * 1.20, L.hand_l * 1.04, L.forearm_t * 1.00),
                      style, uv_scale=4))
        # 炎状の模様 — 上腕に3枚、前腕に2枚
        for i, (y0, h, w) in enumerate(((0.18, 0.30, 0.34), (0.46, 0.26, 0.28),
                                        (0.70, 0.22, 0.22))):
            arm_h = L.shoulder_y - L.elbow_y
            rig.b(f"{side}Arm").add(Cube(
                (cx - L.arm_t * w * 0.5, L.elbow_y + arm_h * y0,
                 -L.arm_t * 0.64),
                (L.arm_t * w, arm_h * h, L.arm_t * 0.06), line, uv_scale=6))
        for i, (y0, h, w) in enumerate(((0.22, 0.28, 0.30), (0.56, 0.24, 0.24))):
            fh = L.elbow_y - L.wrist_y
            fore.add(Cube((cx - L.forearm_t * w * 0.5, L.wrist_y + fh * y0,
                           -L.forearm_t * 0.68),
                          (L.forearm_t * w, fh * h, L.forearm_t * 0.06), line,
                          uv_scale=6))
    if torso:
        chest = rig.b("chest")
        ch = L.chest_top - L.chest_bot
        chest.add(Cube((-L.chest_w * 0.52, L.chest_bot, -L.chest_d * 0.54),
                       (L.chest_w * 1.04, ch * 0.86, L.chest_d * 1.08), style,
                       uv_scale=3))
        for sgn in (-1, 1):
            chest.add(Cube((sgn * L.chest_w * 0.10 - L.chest_w * 0.09,
                            L.chest_bot + ch * 0.14, -L.chest_d * 0.60),
                           (L.chest_w * 0.18, ch * 0.56, L.chest_d * 0.06),
                           line, uv_scale=5))


def steam_vents(rig: HumanRig, style: str = "steam") -> None:
    """ギア2の蒸気。柔らかい輪郭が要るので inflate で角を丸める。
    効果が消えても形態が分かるよう、量は控えめにする (企画書 §06)。"""
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - L.arm_t * 0.44, L.shoulder_y - L.arm_t * 0.20,
             -L.arm_t * 0.44),
            (L.arm_t * 0.88, L.arm_t * 0.34, L.arm_t * 0.88), style,
            uv_scale=3, inflate=0.28))
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.34, L.chest_top - (L.chest_top - L.chest_bot) * 0.22,
         L.chest_d * 0.42),
        (L.chest_w * 0.68, (L.chest_top - L.chest_bot) * 0.26,
         L.chest_d * 0.20), style, uv_scale=3, inflate=0.24))


def inflate_pads(rig: HumanRig, style: str = "inflate") -> None:
    """ギア3の膨張用パーツ。常時はやや太い前腕・脛にとどめ、技中の拡大は
    アニメーションの scale に任せる。胴体には一切足さない (企画書 §04)。"""
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        fore = rig.b(f"{side}Forearm")
        fore.add(Cube((cx - L.forearm_t * 0.74, L.wrist_y + (L.elbow_y - L.wrist_y) * 0.10,
                       -L.forearm_t * 0.74),
                      (L.forearm_t * 1.48, (L.elbow_y - L.wrist_y) * 0.82,
                       L.forearm_t * 1.48), style, uv_scale=3, inflate=0.1))
        hand = rig.b(f"{side}Hand")
        hand.add(Cube((cx - L.forearm_t * 0.78, L.wrist_y - L.hand_l * 1.12,
                       -L.forearm_t * 0.66),
                      (L.forearm_t * 1.56, L.hand_l * 1.12, L.forearm_t * 1.32),
                      style, uv_scale=3, inflate=0.1))
        shin = rig.b(f"{side}Shin")
        lx = sgn * L.stance
        shin.add(Cube((lx - L.shin_t * 0.74, L.ankle_y + (L.knee_y - L.ankle_y) * 0.08,
                       -L.shin_t * 0.74),
                      (L.shin_t * 1.48, (L.knee_y - L.ankle_y) * 0.84,
                       L.shin_t * 1.48), style, uv_scale=3, inflate=0.1))


def nika_extras(rig: HumanRig) -> None:
    """ギア5の「個別制御」— 眉・口・雲をそれぞれ別ボーンにする (企画書 §04)。

    眉と口は常時見える造形にしてある。アニメーションが走らなかったときに
    「口が開きっぱなし」「眉が消える」にならない側へ倒した。
    """
    L = rig.L
    # 眉 — 白く太い。笑いのときに上がる。
    brow = rig.model.bone("brow", (0, L.chin + L.head_h * 0.60, 0), "head")
    rig.bones["brow"] = brow
    for sgn in (-1, 1):
        brow.add(Cube((sgn * L.head_w * 0.12 - L.head_w * 0.11,
                       L.chin + L.head_h * 0.58, -L.head_d * 0.56),
                      (L.head_w * 0.23, L.head_h * 0.07, L.head_d * 0.05),
                      "hair", uv_scale=8))
    # 口 — 歯を見せた笑い。大爆笑で縦に伸びる。
    mouth = rig.model.bone("mouth", (0, L.chin + L.head_h * 0.26, -L.head_d * 0.52),
                           "head")
    rig.bones["mouth"] = mouth
    mouth.add(Cube((-L.head_w * 0.26, L.chin + L.head_h * 0.18, -L.head_d * 0.56),
                   (L.head_w * 0.52, L.head_h * 0.15, L.head_d * 0.05),
                   "scar", uv_scale=8))
    mouth.add(Cube((-L.head_w * 0.24, L.chin + L.head_h * 0.28, -L.head_d * 0.57),
                   (L.head_w * 0.48, L.head_h * 0.05, L.head_d * 0.04),
                   "cloud", uv_scale=8))
    # 雲 — 肩と腰のまわりを巡る飾り。4つを別ボーンにして回せるようにする。
    anchors = [
        ("cloud0", (-L.shoulder_w * 0.56, L.chest_top - L.arm_t * 0.2, 0.0)),
        ("cloud1", (L.shoulder_w * 0.56, L.chest_top - L.arm_t * 0.2, 0.0)),
        ("cloud2", (-L.hip_w * 0.66, L.abdomen_bot, L.waist_d * 0.30)),
        ("cloud3", (L.hip_w * 0.66, L.abdomen_bot, L.waist_d * 0.30)),
    ]
    for name, (px, py, pz) in anchors:
        parent = "chest" if name in ("cloud0", "cloud1") else "body"
        b = rig.model.bone(name, (px, py, pz), parent)
        rig.bones[name] = b
        r = L.head_w * 0.30
        for dx, dy, dz, s in ((0, 0, 0, 1.0), (-0.8, 0.25, 0.1, 0.66),
                              (0.8, 0.18, -0.1, 0.6), (0.0, 0.5, 0.2, 0.5)):
            b.add(Cube((px + dx * r - r * s, py + dy * r, pz + dz * r - r * s),
                       (r * 2 * s, r * 1.4 * s, r * 2 * s), "cloud",
                       uv_scale=3, inflate=0.2))


def nika_shirt(rig: HumanRig) -> None:
    """ニカの白い衣装。ベストではなく前開きのシャツ＋短パン＋帯。"""
    L = rig.L
    chest = rig.b("chest")
    h = (L.chest_top - L.chest_bot) * 1.10
    t = L.chest_d * 0.14
    for sgn in (-1, 1):
        chest.add(Cube((sgn * L.chest_w * 0.12, L.chest_bot - h * 0.18,
                        -L.chest_d * 0.54 - t * 0.5),
                       (L.chest_w * 0.38, h, t), "shirt", uv_scale=4))
    chest.add(Cube((-L.chest_w * 0.52, L.chest_bot - h * 0.18,
                    L.chest_d * 0.52 - t * 0.5),
                   (L.chest_w * 1.04, h, t), "shirt", uv_scale=4))
    # 袖は肘まで
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        rig.b(f"{side}Arm").add(Cube(
            (cx - L.arm_t * 0.62, L.elbow_y + (L.shoulder_y - L.elbow_y) * 0.30,
             -L.arm_t * 0.62),
            (L.arm_t * 1.24, (L.shoulder_y - L.elbow_y) * 0.68,
             L.arm_t * 1.24), "shirt", uv_scale=4))


# ===========================================================================
#  形態モデル
# ===========================================================================
def _base_rig(model: Model, cm: float, heads: float, sh: float, limb: float,
              bulk: float, arm_len: float, hunch: float = 0.0) -> HumanRig:
    return HumanRig(model, Build(cm, heads, sh, limb, bulk=bulk,
                                 arm_len=arm_len, hunch=hunch,
                                 player_anchor=True),
                    player_rig=True)


def build_normal() -> Model:
    m = Model(f"geometry.{spec.NS}.luffy_normal", uv_scale=3,
              visible_bounds=(4.6, 4.4), vb_offset=(0, 1.5, 0),
              max_atlas=(512, 512))
    rig = _base_rig(m, 174, 4.9, 0.250, 0.94, 0.94, 1.00)
    rig.flesh(skin="skin", suit="skin", face=dict(FACE_NORMAL))
    anatomy(rig)
    limbs_detail(rig)
    fingers(rig)
    face_shape(rig)
    eye_scar(rig)
    chest_scar(rig)
    vest(rig)
    shorts(rig)
    sandals(rig)
    rig.hair(HAIR_LUFFY)
    hair_depth(rig)
    straw_hat(rig)
    m.pack()
    return m


def build_gear2() -> Model:
    """基本造形は通常と共有。前傾・蒸気・肌の色味だけを専用調整する。"""
    m = Model(f"geometry.{spec.NS}.luffy_gear2", uv_scale=3,
              visible_bounds=(4.6, 4.4), vb_offset=(0, 1.5, 0),
              max_atlas=(512, 512))
    rig = _base_rig(m, 174, 4.9, 0.250, 0.94, 0.94, 1.00, hunch=7.0)
    rig.flesh(skin="skin", suit="skin", face=dict(FACE_FOCUS))
    anatomy(rig)
    limbs_detail(rig)
    fingers(rig)
    face_shape(rig)
    eye_scar(rig)
    chest_scar(rig)
    vest(rig)
    shorts(rig)
    sandals(rig)
    steam_vents(rig)
    rig.hair(HAIR_LUFFY)
    hair_depth(rig)
    straw_hat(rig)
    m.pack()
    return m


def build_gear3() -> Model:
    """通常の輪郭のまま、前腕と脛だけ膨張用パーツを持つ。"""
    m = Model(f"geometry.{spec.NS}.luffy_gear3", uv_scale=3,
              visible_bounds=(5.6, 5.0), vb_offset=(0, 1.6, 0),
              max_atlas=(512, 512))
    rig = _base_rig(m, 174, 4.9, 0.250, 0.94, 0.94, 1.04)
    rig.flesh(skin="skin", suit="skin", face=dict(FACE_FOCUS))
    anatomy(rig)
    limbs_detail(rig)
    fingers(rig)
    face_shape(rig)
    eye_scar(rig)
    chest_scar(rig)
    vest(rig)
    shorts(rig)
    sandals(rig)
    inflate_pads(rig)
    rig.hair(HAIR_LUFFY)
    hair_depth(rig)
    straw_hat(rig)
    m.pack()
    return m


def build_g4_bound() -> Model:
    """バウンドマン — 胸と腕のボリューム、弾む重心、覇気の模様。"""
    m = Model(f"geometry.{spec.NS}.luffy_g4_bound", uv_scale=2,
              visible_bounds=(5.4, 4.8), vb_offset=(0, 1.6, 0),
              max_atlas=(1024, 1024))
    rig = _base_rig(m, 178, 5.2, 0.300, 1.34, 1.42, 1.06)
    rig.flesh(skin="skin", suit="skin", face=dict(FACE_FOCUS))
    anatomy(rig)
    limbs_detail(rig)
    fingers(rig)
    face_shape(rig)
    eye_scar(rig)
    chest_scar(rig)
    haki_sleeves(rig, upper=True, torso=True)
    shorts(rig)
    sandals(rig)
    rig.hair(HAIR_LUFFY)
    hair_depth(rig)
    straw_hat(rig)
    m.pack()
    return m


def build_g4_snake() -> Model:
    """スネイクマン — バウンドマンとは別の輪郭。細身で腕が長い。"""
    m = Model(f"geometry.{spec.NS}.luffy_g4_snake", uv_scale=2,
              visible_bounds=(5.8, 4.6), vb_offset=(0, 1.5, 0),
              max_atlas=(1024, 1024))
    rig = _base_rig(m, 176, 5.0, 0.258, 1.00, 1.04, 1.28)
    rig.flesh(skin="skin", suit="skin", face=dict(FACE_FOCUS))
    anatomy(rig)
    limbs_detail(rig)
    fingers(rig)
    face_shape(rig)
    eye_scar(rig)
    chest_scar(rig)
    haki_sleeves(rig, upper=True, torso=False)
    vest(rig)
    shorts(rig)
    sandals(rig)
    rig.hair(HAIR_LUFFY)
    hair_depth(rig)
    straw_hat(rig)
    m.pack()
    return m


def build_gear5() -> Model:
    """ニカ — 髪・眉・口・雲を個別のボーンに分ける。"""
    m = Model(f"geometry.{spec.NS}.luffy_gear5", uv_scale=2,
              visible_bounds=(6.0, 5.4), vb_offset=(0, 1.8, 0),
              max_atlas=(1024, 1024))
    rig = _base_rig(m, 182, 4.6, 0.268, 1.08, 1.10, 1.14)
    rig.flesh(skin="skin", suit="skin", face=dict(FACE_NIKA))
    anatomy(rig)
    limbs_detail(rig)
    fingers(rig)
    face_shape(rig)
    chest_scar(rig)
    nika_shirt(rig)
    shorts(rig, style="shorts", sash_style="sash", length=0.78)
    sandals(rig)
    rig.hair(HAIR_NIKA)
    hair_depth(rig, long_back=True)
    nika_extras(rig)
    straw_hat(rig)
    m.pack()
    return m


FORM_BUILDERS = {
    "normal": build_normal,
    "gear2": build_gear2,
    "gear3": build_gear3,
    "gear4_bound": build_g4_bound,
    "gear4_snake": build_g4_snake,
    "gear5": build_gear5,
}


# ===========================================================================
#  訓練用の標的と、演出用の表示体
# ===========================================================================
def build_dummy(small: bool = False) -> Model:
    """藁と丸太の標的。派手にせず、どこに当たったか分かる印だけ置く。"""
    key = "dummy_small" if small else "dummy"
    s = 0.62 if small else 1.0
    m = Model(f"geometry.{spec.NS}.{key}", uv_scale=4,
              visible_bounds=(1.6 * s, 2.4 * s), vb_offset=(0, 1.0 * s, 0),
              max_atlas=(256, 256))
    root = m.bone("body", (0, 0, 0))
    head = m.bone("head", (0, 22 * s, 0), "body")
    arms = m.bone("arms", (0, 17 * s, 0), "body")
    # 杭
    root.add(Cube((-2.0 * s, 0, -2.0 * s), (4.0 * s, 13 * s, 4.0 * s), "wood"))
    # 藁の胴
    root.add(Cube((-4.0 * s, 11 * s, -3.0 * s), (8.0 * s, 10 * s, 6.0 * s),
                  "straw", uv_scale=3))
    root.add(Cube((-4.4 * s, 12 * s, -3.4 * s), (8.8 * s, 1.4 * s, 6.8 * s),
                  "rope", uv_scale=5))
    root.add(Cube((-4.4 * s, 18 * s, -3.4 * s), (8.8 * s, 1.4 * s, 6.8 * s),
                  "rope", uv_scale=5))
    # 当たり位置の印
    root.add(Cube((-2.2 * s, 14 * s, -3.3 * s), (4.4 * s, 4.4 * s, 0.5 * s),
                  "mark", uv_scale=6))
    # 頭
    head.add(Cube((-3.0 * s, 22 * s, -3.0 * s), (6.0 * s, 5.5 * s, 6.0 * s),
                  "straw", uv_scale=4))
    head.add(Cube((-3.4 * s, 21.4 * s, -3.4 * s), (6.8 * s, 1.2 * s, 6.8 * s),
                  "rope", uv_scale=6))
    # 腕（横木）
    arms.add(Cube((-9.0 * s, 16.4 * s, -1.2 * s), (18.0 * s, 2.4 * s, 2.4 * s),
                  "wood", uv_scale=3))
    for sgn in (-1, 1):
        arms.add(Cube((sgn * 8.0 * s - 1.6 * s, 12.0 * s, -1.8 * s),
                      (3.2 * s, 5.0 * s, 3.6 * s), "straw", uv_scale=4))
    m.pack()
    return m


def build_vfx_fist() -> Model:
    """伸びる拳を立体で見せるための表示体 (企画書 §11: 拳はモデルで作る)。"""
    m = Model(f"geometry.{spec.NS}.vfx_fist", uv_scale=4,
              visible_bounds=(2.4, 2.4), vb_offset=(0, 0.4, 0),
              max_atlas=(256, 256))
    root = m.bone("body", (0, 0, 0))
    knuckle = m.bone("knuckle", (0, 4, -3), "body")
    # 手首から拳へ
    root.add(Cube((-3.2, -1.0, 1.0), (6.4, 6.4, 5.0), "skin", uv_scale=3))
    knuckle.add(Cube((-4.2, -1.6, -5.0), (8.4, 8.0, 6.6), "skin", uv_scale=3))
    # 指の段差
    for i in range(4):
        knuckle.add(Cube((-4.2 + i * 2.1, 4.4, -5.4), (2.0, 2.2, 2.0), "skin",
                         uv_scale=6))
    # 親指
    knuckle.add(Cube((3.4, -0.6, -3.4), (2.2, 2.6, 4.2), "skin", uv_scale=6))
    # 覇気の縁 — 黒くしすぎず、面方向のハイライトで形を残す
    knuckle.add(Cube((-4.5, -1.9, -5.3), (9.0, 1.4, 7.0), "haki", uv_scale=5))
    m.pack()
    return m


def build_vfx_bolt() -> Model:
    """投げた雷。平面のパーティクルでは立体感が出ないので段違いの角柱で作る。"""
    m = Model(f"geometry.{spec.NS}.vfx_bolt", uv_scale=6,
              visible_bounds=(1.6, 2.0), vb_offset=(0, 0.4, 0),
              max_atlas=(128, 128))
    root = m.bone("body", (0, 0, 0))
    segs = [(0.0, 0.0, 0.0, 22.0), (1.6, -4.0, 8.0, -30.0),
            (-1.4, -8.0, 16.0, 26.0), (0.8, -12.0, 24.0, -18.0)]
    for i, (x, y, z, rot) in enumerate(segs):
        w = 1.8 - i * 0.24
        root.add(Cube((x - w / 2, y + 12 - i * 0.6, -z * 0.32 - w / 2),
                      (w, 5.2, w), "bolt", uv_scale=6,
                      rotation=(rot, rot * 0.4, 0)))
        root.add(Cube((x - w * 0.9, y + 12.4 - i * 0.6, -z * 0.32 - w * 0.9),
                      (w * 1.8, 1.2, w * 1.8), "edge", uv_scale=6,
                      rotation=(rot, rot * 0.4, 0)))
    m.pack()
    return m


# ===========================================================================
def main() -> None:
    print("models:")
    for key, builder in FORM_BUILDERS.items():
        form = spec.FORM_BY_KEY[key]
        emit(builder(), palette.PALETTES[key], form.geo, form.texture)
    emit(build_dummy(False), palette.DUMMY, "dummy", "dummy")
    emit(build_dummy(True), palette.DUMMY, "dummy_small", "dummy_small")
    emit(build_vfx_fist(), palette.VFX_FIST, "vfx_fist", "vfx_fist")
    emit(build_vfx_bolt(), palette.VFX_BOLT, "vfx_bolt", "vfx_bolt")


if __name__ == "__main__":
    palette.check()
    main()
