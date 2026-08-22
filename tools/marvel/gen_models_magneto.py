# -*- coding: utf-8 -*-
"""マグニートーのモデル。

本作の主役なので、ここだけは他のキャラと別モジュールにしてある。
兜・マント・装甲を専用パーツとして組み、``player_rig=True`` で
バニラのプレイヤー骨格に載るようにしておく（＝変身体としてそのまま着られる）。
"""
from __future__ import annotations

import math

import _path  # noqa: F401  (sys.path を整える。必ず最初に import する)

import contract as K  # noqa: E402
import colours  # noqa: E402
from common import emit  # noqa: E402
from mcmodel import Cube, Model  # noqa: E402
from rig import Build, HumanRig  # noqa: E402


def helmet(rig: HumanRig) -> None:
    """画像の兜: ガンメタルの半球に、左右へ跳ね上がる M 字のクレスト。"""
    L = rig.L
    head = rig.b("head")
    # 頭蓋を覆う本体
    head.add(Cube((-L.head_w * 0.58, L.chin + L.head_h * 0.34, -L.head_d * 0.58),
                  (L.head_w * 1.16, L.head_h * 0.74, L.head_d * 1.16), "helm",
                  uv_scale=5, decals={"east": "helm_side", "west": "helm_side"}))
    # 前面のクレスト
    head.add(Cube((-L.head_w * 0.60, L.chin + L.head_h * 0.62, -L.head_d * 0.68),
                  (L.head_w * 1.20, L.head_h * 0.52, L.head_d * 0.22),
                  "helm_crest", uv_scale=6, decals={"north": "helm_crest"}))
    # 頬当て（顔の左右を落ちる板）
    for sgn in (-1, 1):
        head.add(Cube((sgn * L.head_w * 0.40 - L.head_w * 0.12,
                       L.chin + L.head_h * 0.06, -L.head_d * 0.62),
                      (L.head_w * 0.24, L.head_h * 0.56, L.head_d * 0.30),
                      "helm", uv_scale=5))
    # 顔の露出部（兜の窓）
    head.add(Cube((-L.head_w * 0.40, L.chin + L.head_h * 0.10, -L.head_d * 0.60),
                  (L.head_w * 0.80, L.head_h * 0.48, L.head_d * 0.08), "skin",
                  uv_scale=6, decals={"north": "face"}))
    # 後頭部の襟
    head.add(Cube((-L.head_w * 0.52, L.chin + L.head_h * 0.20, L.head_d * 0.34),
                  (L.head_w * 1.04, L.head_h * 0.46, L.head_d * 0.22),
                  "helm_dark", uv_scale=4, decals={"south": "helm_temple"}))


def cape(rig: HumanRig, segments: int = 4) -> None:
    """関節を持つマント。段ごとにボーンを切ってあるので、風になびかせられる。"""
    L = rig.L
    width = L.shoulder_w * 1.10
    total = L.total * 0.62
    seg = total / segments
    parent = "chest"
    y = L.chest_top + L.total * 0.01
    z = L.chest_d * 0.48
    for i in range(segments):
        name = f"cape{i}"
        b = rig.model.bone(name, (0, y, z), parent, rotation=(3 + i * 2, 0, 0))
        rig.bones[name] = b
        w = width * (1.0 + 0.20 * i / max(1, segments - 1))
        b.add(Cube((-w / 2, y - seg, z), (w, seg, L.total * 0.010), "cape",
                   uv_scale=2, decals={"north": "cape_fold",
                                       "south": "cape_fold"}))
        parent = name
        y -= seg
    # 肩の留め具
    rig.b("chest").add(Cube(
        (-L.shoulder_w * 0.34, L.chest_top - L.total * 0.030, -L.chest_d * 0.16),
        (L.shoulder_w * 0.68, L.total * 0.034, L.chest_d * 0.86), "helm",
        uv_scale=5, decals={"north": "cape_clasp"}))


def armour(rig: HumanRig) -> None:
    """深紫の装甲板・帯・深紅のブーツと手甲。"""
    L = rig.L
    ch = L.chest_top - L.chest_bot
    chest = rig.b("chest")
    body = rig.b("body")
    # 胸当て（磁力紋章つき）
    chest.add(Cube((-L.chest_w * 0.56, L.chest_bot + ch * 0.06, -L.chest_d * 0.64),
                   (L.chest_w * 1.12, ch * 0.86, L.chest_d * 0.36), "plate",
                   uv_scale=4, decals={"north": "mag_sigil"}))
    # 腹〜腰
    body.add(Cube((-L.waist_w * 0.56, L.abdomen_bot, -L.waist_d * 0.60),
                  (L.waist_w * 1.12, L.chest_bot - L.abdomen_bot,
                   L.waist_d * 1.20), "plate_dark", uv_scale=4))
    body.add(Cube((-L.hip_w * 0.60, L.abdomen_bot - L.total * 0.020,
                   -L.waist_d * 0.64),
                  (L.hip_w * 1.20, L.total * 0.042, L.waist_d * 1.28), "belt",
                  uv_scale=5, decals={"north": "mag_core"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        lx = sgn * L.stance
        # パウルドロン
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - L.arm_t * 0.84, L.shoulder_y - L.arm_t * 1.08, -L.arm_t * 0.84),
            (L.arm_t * 1.68, L.arm_t * 1.24, L.arm_t * 1.68), "plate",
            uv_scale=4, decals={"up": "panel_seam"}))
        # 手甲（磁力コア）
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.74, L.wrist_y + (L.elbow_y - L.wrist_y) * 0.04,
             -L.forearm_t * 0.74),
            (L.forearm_t * 1.48, (L.elbow_y - L.wrist_y) * 0.66,
             L.forearm_t * 1.48), "glove", uv_scale=4,
            decals={"north": "mag_core"}))
        # 手袋
        rig.b(f"{side}Hand").add(Cube(
            (cx - L.forearm_t * 0.58, L.wrist_y - L.hand_l * 1.06,
             -L.forearm_t * 0.48),
            (L.forearm_t * 1.16, L.hand_l * 1.08, L.forearm_t * 0.98), "glove",
            uv_scale=4))
        # ブーツ
        rig.b(f"{side}Shin").add(Cube(
            (lx - L.shin_t * 0.70, L.ankle_y, -L.shin_t * 0.76),
            (L.shin_t * 1.40, (L.knee_y - L.ankle_y) * 0.74, L.shin_t * 1.30),
            "boot", uv_scale=4))
        rig.b(f"{side}Foot").add(Cube(
            (lx - L.shin_t * 0.68, 0, -L.foot_l * 0.68),
            (L.shin_t * 1.36, L.foot_h * 1.16, L.foot_l * 0.66), "boot",
            uv_scale=4))


def build_magneto() -> Model:
    c = K.CHARACTERS[K.MAGNETO]
    m = Model(K.geo(K.MAGNETO), uv_scale=3, visible_bounds=(3.8, 4.2),
              vb_offset=(0, 1.4, 0), max_atlas=(512, 512))
    rig = HumanRig(m, Build(c["cm"], c["heads"], c["sh"], c["limb"],
                            female=c["female"], bulk=c["bulk"]),
                   player_rig=True)
    rig.flesh(hands_bare=False)
    armour(rig)
    cape(rig)
    helmet(rig)
    return m


# ===========================================================================
#  一人称の手元
# ===========================================================================
def build_fp_hand() -> Model:
    """技アイテムを持つと一人称で見える磁力ガントレット。

    ボーン構成は「手 → 甲 → 磁界リング → 浮遊する鉄片」。
    リングと鉄片が別ボーンなので、技ごとに違う動きをさせられる。
    """
    m = Model(K.geo("fp_hand"), uv_scale=6, visible_bounds=(1.6, 1.6),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    root = m.bone("root", (0, 0, 0))
    hand = m.bone("hand", (0, 0, 0), "root")
    hand.add(Cube((-2.2, -2.0, -2.2), (4.4, 4.6, 4.4), "glove", uv_scale=6))
    hand.add(Cube((-2.6, 2.4, -2.6), (5.2, 1.6, 5.2), "helm", uv_scale=6,
                  decals={"up": "mag_core"}))
    # 指（親指 + 3 本）
    for i in range(3):
        u = (i - 1) * 1.5
        f = m.bone(f"finger{i}", (u, -2.0, -1.0), "hand", rotation=(-12, 0, 0))
        f.add(Cube((u - 0.6, -4.6, -1.6), (1.2, 2.8, 1.6), "glove", uv_scale=6))
    thumb = m.bone("thumb", (2.0, -1.0, 0), "hand", rotation=(0, 0, -34))
    thumb.add(Cube((1.6, -3.2, -1.0), (1.2, 2.4, 1.6), "glove", uv_scale=6))
    # 甲の磁力コア
    gaunt = m.bone("gauntlet", (0, 1.0, 0), "hand")
    gaunt.add(Cube((-2.8, 0.6, -2.8), (5.6, 2.6, 5.6), "helm", uv_scale=6,
                   decals={"north": "mag_core"}))
    # 手の前に浮かぶ磁界リング
    field = m.bone("field", (0, -1.0, -4.0), "root", rotation=(0, 0, 0))
    for i in range(6):
        a = i * math.pi / 3
        field.add(Cube((5.0 * math.cos(a) - 0.7, -1.0 + 5.0 * math.sin(a) - 0.7,
                        -4.6), (1.4, 1.4, 1.0), "magnet", uv_scale=6,
                       rotation=(0, 0, -math.degrees(a))))
    core = m.bone("core", (0, -1.0, -4.4), "field")
    core.add(Cube((-1.6, -2.6, -5.0), (3.2, 3.2, 1.2), "magnet", uv_scale=6,
                  decals={"north": "mag_sigil"}))
    # 周囲を回る鉄片
    for i in range(3):
        b = m.bone(f"shard{i}", (0, -1.0, -4.0), "field",
                   rotation=(0, 0, i * 120))
        b.add(Cube((7.0, -1.8, -4.6), (2.6, 0.9, 0.9), "shard", uv_scale=6))
    root.add(Cube((-0.01, -0.01, -0.01), (0.02, 0.02, 0.02), "magnet",
                  uv_scale=1))
    m.pack()
    return m


def build_tech_orb() -> Model:
    """技アイテムを持っている時に三人称で手元に浮く磁力球。"""
    m = Model(K.geo("tech_orb"), uv_scale=5, visible_bounds=(1.0, 1.0),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    core = m.bone("core", (0, 0, 0))
    core.add(Cube((-1.8, -1.8, -1.8), (3.6, 3.6, 3.6), "magnet", uv_scale=5,
                  decals={"north": "mag_sigil"}))
    ring = m.bone("ring", (0, 0, 0), "core")
    for i in range(4):
        a = i * math.pi / 2
        ring.add(Cube((4.0 * math.cos(a) - 0.6, 4.0 * math.sin(a) - 0.6, -0.6),
                      (1.2, 1.2, 1.2), "shard", uv_scale=5))
    m.pack()
    return m


def main() -> None:
    print("magneto:")
    emit(build_magneto(), colours.MAGNETO, K.MAGNETO, seed=101)
    emit(build_fp_hand(), colours.MAGNETO, "fp_hand", seed=102)
    emit(build_tech_orb(), colours.MAGNETO, "tech_orb", seed=103)


if __name__ == "__main__":
    main()
