# -*- coding: utf-8 -*-
"""Every entity model + its texture, built from the proportional rig."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcmodel import Cube, Model  # noqa: E402
import mctexture  # noqa: E402
from mctexture import Painter  # noqa: E402
from rig import (Build, BeastRig, HumanRig, KaijuParts, HAIR,  # noqa: E402
                 HAIR_FRONT, PLAYER_PIVOTS)

PLAYER_ARM_X = abs(PLAYER_PIVOTS["rightArm"][0])
import gen_weapons  # noqa: E402
import palettes  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "packs", "kaiju8_RP")
GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", "kaiju8")


# ---------------------------------------------------------------------------
#  Character sheet.  height_cm / 等身 drive the whole silhouette.
# ---------------------------------------------------------------------------
CHARACTERS = {
    # 身長は公式プロフィール、等身と肩幅は作画からの推定
    "kafka": dict(cm=181, heads=7.5, sh=0.252, limb=1.05, female=False, bulk=1.08,
                  hair="kafka", pal="kafka", weapon="combat_knife",
                  mount=(-10, 0, 0), face={"stubble": True}),
    "reno": dict(cm=174, heads=7.5, sh=0.236, limb=0.94, female=False,
                 hair="reno", pal="reno", weapon="df_rifle", mount=(-84, 0, 0)),
    "mina": dict(cm=169, heads=7.5, sh=0.226, limb=0.90, female=True,
                 hair="mina", pal="mina", weapon="cannon_t25", mount=(-86, 0, 0),
                 face={"moles": True, "expr": "stern"},
                 ponytail=("tail", (0.0, 0.50, 0.52), 4, 3.2, 0.34), visor=True),
    "hoshina": dict(cm=171, heads=7.0, sh=0.244, limb=0.99, female=False,
                    hair="hoshina", pal="hoshina", weapon="twin_sw2033",
                    mount=(-30, 0, 0), twin=True,
                    face={"expr": "narrow", "smile": True}),
    "kikoru": dict(cm=157, heads=6.5, sh=0.222, limb=0.88, female=True,
                   hair="kikoru", pal="kikoru", weapon="axe_03ax",
                   mount=(-34, 0, 0), face={"expr": "stern"}, ribbons=True,
                   twintail=((-0.50, 0.36, 0.30), (0.50, 0.36, 0.30), 4, 3.0, 0.28)),
    "narumi": dict(cm=175, heads=8.0, sh=0.240, limb=0.98, female=False,
                   hair="narumi", pal="narumi", weapon="gunblade_gs3305",
                   mount=(-40, 0, 0), front_hair=True,
                   face={"expr": "grin"}),
    "furuhashi": dict(cm=177, heads=7.5, sh=0.244, limb=1.00, female=False,
                      hair="furuhashi", pal="furuhashi", weapon="combat_knife",
                      mount=(-10, 0, 0), face={"expr": "grin"}),
    "izumo": dict(cm=178, heads=8.0, sh=0.234, limb=0.94, female=False,
                  hair="izumo", pal="izumo", weapon="df_rifle", mount=(-84, 0, 0)),
    "kaguragi": dict(cm=183, heads=8.0, sh=0.256, limb=1.10, female=False, bulk=1.10,
                     hair="kaguragi", pal="kaguragi", weapon="axe_03ax",
                     mount=(-34, 0, 0), face={"no_brow": True, "expr": "stern"}),
    "isao": dict(cm=190, heads=8.0, sh=0.262, limb=1.16, female=False, bulk=1.14,
                 hair="isao", pal="isao", weapon="cannon_t25", mount=(-86, 0, 0),
                 face={"expr": "stern"}),
    "soldier": dict(cm=175, heads=7.4, sh=0.242, limb=1.00, female=False,
                    hair="crew", pal="officer", weapon="df_rifle",
                    mount=(-84, 0, 0)),
}


def emit(model: Model, palette: dict, geo_name: str, tex_name: str, seed: int = 7):
    os.makedirs(GEO_DIR, exist_ok=True)
    os.makedirs(TEX_DIR, exist_ok=True)
    model.write(os.path.join(GEO_DIR, geo_name + ".geo.json"))
    p = Painter(model.tex_w, model.tex_h, seed)
    p.paint_model(model, palette)
    p.save(os.path.join(TEX_DIR, tex_name + ".png"))
    print(f"  {geo_name:34s} {model.stats()}")
    return model


# ===========================================================================
#  日本防衛隊 隊員
# ===========================================================================
def build_character(key: str) -> Model:
    c = CHARACTERS[key]
    m = Model(f"geometry.kaiju8.{key}", uv_scale=3,
              visible_bounds=(3.4, 3.6), vb_offset=(0, 1.2, 0),
              max_atlas=(512, 512))
    build = Build(c["cm"], c["heads"], c["sh"], c["limb"], female=c["female"],
                  bulk=c.get("bulk", 1.0))
    face = dict(c.get("face") or {})
    if c["female"]:
        face.setdefault("lashes", True)
    rig = HumanRig(m, build)
    rig.flesh(face=face)
    rig.combat_suit()
    rig.hair(HAIR[c["hair"]])
    if c.get("front_hair"):
        rig.hair(HAIR_FRONT[c["hair"]], style="decal")
    if c.get("ponytail"):
        name, anchor, seg, length, thick = c["ponytail"]
        rig.ponytail(name, anchor, seg, length, thick, tilt=12)
    if c.get("twintail"):
        aL, aR, seg, length, thick = c["twintail"]
        rig.ponytail("tailR", aL, seg, length, thick, tilt=9)
        rig.ponytail("tailL", aR, seg, length, thick, tilt=9)
        if c.get("ribbons"):                       # 黒リボンで結んだ根本
            L = rig.L
            for name, anchor in (("tailR", aL), ("tailL", aR)):
                rig.b(f"{name}0").add(Cube(
                    (anchor[0] * L.head_w - L.head_w * 0.13,
                     L.chin + anchor[1] * L.head_h - L.head_h * 0.10,
                     anchor[2] * L.head_d - L.head_d * 0.13),
                    (L.head_w * 0.26, L.head_h * 0.16, L.head_d * 0.26),
                    "cloth", uv_scale=6, decals={"north": "ribbon"}))
    if c.get("visor"):
        rig.visor_bar()

    weapon = c.get("weapon")
    if weapon:
        bone, off, s = rig.mount("weapon", "right", c.get("mount", (0, 0, 0)))
        scale = s * (0.86 if weapon in ("cannon_t25", "gunblade_gs3305") else 1.0)
        if c.get("twin"):
            gen_weapons.twin_sw2033(bone, off, scale)
            bone2, off2, s2 = rig.mount("weapon2", "left", c.get("mount", (0, 0, 0)))
            gen_weapons.twin_sw2033(bone2, off2, scale)
        else:
            gen_weapons.BUILDERS[weapon](bone, off, scale)
    m.pack()
    return m


# ===========================================================================
#  怪獣8号 — カフカの「もう一つの体」。全高2.05m、人間とほぼ同スケール。
#  プレイヤーのアタッチャブルとして着られるよう、バニラのボーン名を保つ。
# ===========================================================================
def build_no8() -> Model:
    """怪獣8号。モブと変身後のプレイヤーで同一のジオメトリを使うため、関節の枢軸を
    バニラのプレイヤー骨格に固定してある(player_anchor)。こうしないとアタッチャブル
    として着せたときにボーンがプレイヤー側の位置へ引き寄せられてモデルが崩れる。"""
    m = Model("geometry.kaiju8.no8", uv_scale=4, visible_bounds=(3.2, 3.4),
              vb_offset=(0, 1.2, 0), max_atlas=(1024, 1024))
    rig = HumanRig(m, Build(205, 5.6, 0.34, 1.06, bulk=0.94, arm_len=1.06,
                            player_anchor=True), player_rig=True)
    rig.flesh(skin="hide", suit="hide")
    k = KaijuParts(rig)
    k.mask(horns=2, crest=True, damage=True, throat_teeth=True, skull=True)
    k.plates(limb_style="bone")
    k.mantle(plate="plate", top="bone", spines=5)
    k.claws(fingers=3)
    L = rig.L
    # 発光する亀裂 — 腹部が最大面積、次いで手首・足首
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.30, L.chest_bot + (L.chest_top - L.chest_bot) * 0.16,
         -L.chest_d * 0.70), (L.chest_w * 0.60,
                              (L.chest_top - L.chest_bot) * 0.44, L.chest_d * 0.10),
        "crack", uv_scale=6, decals={"north": "veins"}))
    rig.b("body").add(Cube(
        (-L.waist_w * 0.34, L.abdomen_bot, -L.waist_d * 0.66),
        (L.waist_w * 0.68, (L.chest_bot - L.abdomen_bot) * 0.9, L.waist_d * 0.10),
        "crack", uv_scale=6, decals={"north": "veins"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = PLAYER_ARM_X * sgn
        rig.b(f"{side}Hand").add(Cube(
            (cx - L.forearm_t * 0.34, L.wrist_y - L.hand_l * 0.2, -L.forearm_t * 0.56),
            (L.forearm_t * 0.68, L.hand_l * 0.5, L.forearm_t * 0.10), "crack",
            uv_scale=6))
        rig.b(f"{side}Foot").add(Cube(
            (sgn * L.stance - L.shin_t * 0.34, L.foot_h * 0.2, -L.foot_l * 0.10),
            (L.shin_t * 0.68, L.foot_h * 0.6, L.foot_l * 0.10), "crack", uv_scale=6))
    m.pack()
    return m


# ===========================================================================
#  怪獣9号 γ形態（脱皮後）— 全高3.7m、暗灰の筋肉質、クリムゾンの突起、赤い眼
# ===========================================================================
def build_no9() -> Model:
    m = Model("geometry.kaiju8.no9", uv_scale=2, visible_bounds=(4.0, 5.0),
              vb_offset=(0, 2.0, 0), max_atlas=(1024, 1024))
    rig = HumanRig(m, Build(370, 6.6, 0.262, 0.94, bulk=1.02, arm_len=1.16))
    rig.flesh(skin="skin", suit="suit")
    k = KaijuParts(rig)
    k.mask(style="mask", horn_style="horn", jaw_style="sinew", horns=1,
           crest=False, glow_decal="brow_eyes", skull=False)
    k.claws(fingers=4, feet=True)
    k.spurs(count=2)
    L = rig.L
    # 頭部側面のシュモクザメ状突起
    for sgn in (-1, 1):
        rig.b("head").add(Cube(
            (sgn * L.head_w * 0.52 - (L.head_w * 0.34 if sgn > 0 else 0),
             L.chin + L.head_h * 0.42, -L.head_d * 0.30),
            (L.head_w * 0.34, L.head_h * 0.26, L.head_d * 0.52), "horn",
            uv_scale=4))
    # 血管の浮いた胸郭
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.46, L.chest_bot + (L.chest_top - L.chest_bot) * 0.16,
         -L.chest_d * 0.64),
        (L.chest_w * 0.92, (L.chest_top - L.chest_bot) * 0.60, L.chest_d * 0.14),
        "crack", uv_scale=3, decals={"north": "veins"}))
    m.pack()
    return m


# ===========================================================================
#  怪獣10号 — 全高5.0m、西洋甲冑のような装甲人型。翼なし、長い棘の尾9節
# ===========================================================================
def build_no10() -> Model:
    m = Model("geometry.kaiju8.no10", uv_scale=2, visible_bounds=(6.0, 6.5),
              vb_offset=(0, 2.6, 0), max_atlas=(1024, 1024))
    rig = HumanRig(m, Build(500, 5.6, 0.350, 1.58, bulk=1.62, hunch=8,
                            arm_len=1.08))
    rig.flesh(skin="hide", suit="hide")
    k = KaijuParts(rig)
    k.cross_face()
    k.plates(seams=True)
    k.claws(fingers=3)
    k.spine(9, style="horn", scale=1.2)
    k.tail(9, length=1.55, thickness=0.34, style="hide", tip_style="horn",
           droop=-7, spikes=True)
    L = rig.L
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.40, L.chest_bot + (L.chest_top - L.chest_bot) * 0.12,
         -L.chest_d * 0.70),
        (L.chest_w * 0.80, (L.chest_top - L.chest_bot) * 0.56, L.chest_d * 0.12),
        "crack", uv_scale=3, decals={"north": "veins"}))
    m.pack()
    return m


# ===========================================================================
#  本獣 — 原作は全高30m級だが、Bedrockの当たり判定と経路探索の都合で8mに縮小
# ===========================================================================
def build_honju() -> Model:
    m = Model("geometry.kaiju8.honju", uv_scale=1, visible_bounds=(7.0, 7.0),
              vb_offset=(0, 2.6, 0), max_atlas=(1024, 1024))
    rig = HumanRig(m, Build(520, 4.6, 0.390, 1.90, bulk=1.88, arm_len=1.10,
                            digitigrade=True, hunch=30))
    rig.flesh(skin="hide", suit="hide")
    k = KaijuParts(rig)
    k.mask(horns=2, crest=True, glow_decal="brow_eyes", skull=True)
    k.plates(seams=True)
    k.mantle(plate="plate", top="plate", spines=6)
    k.claws(fingers=3)
    k.spine(9, style="horn", scale=1.4)
    k.tail(7, length=1.5, thickness=0.42, style="hide", tip_style="claw",
           droop=-9)
    L = rig.L
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.42, L.chest_bot, -L.chest_d * 0.72),
        (L.chest_w * 0.84, (L.chest_top - L.chest_bot) * 0.70, L.chest_d * 0.16),
        "belly", uv_scale=2, decals={"north": "core"}))     # 胸腹部のコア
    rig.b("head").add(Cube(
        (-L.head_w * 0.50, L.chin + L.head_h * 0.58, -L.head_d * 0.66),
        (L.head_w * 1.00, L.head_h * 0.20, L.head_d * 0.14), "plate",
        uv_scale=4, decals={"north": "eye_rows"}))
    m.pack()
    return m


# ===========================================================================
#  余獣 — 全高2.5m、ずんぐりした甲殻の四足獣。発光なし
# ===========================================================================
def build_yoju() -> Model:
    m = Model("geometry.kaiju8.yoju", uv_scale=2, visible_bounds=(3.6, 3.0),
              vb_offset=(0, 1.1, 0), max_atlas=(1024, 512))
    rig = BeastRig(m, length_px=54, height_px=40, legs=4)
    rig.build(segments=3, tail_segments=3, back_plates=4, horns=2)
    m.pack()
    return m


def build_parasite() -> Model:
    m = Model("geometry.kaiju8.parasite", uv_scale=4, visible_bounds=(1.0, 0.8),
              vb_offset=(0, 0.25, 0), max_atlas=(256, 256))
    rig = BeastRig(m, length_px=8.0, height_px=4.5, legs=4)
    rig.build(segments=2, tail_segments=2, back_plates=2, horns=1, head_scale=1.2)
    m.pack()
    return m


# ===========================================================================
#  識別怪獣兵器（ナンバーズ）— 着る武器。プレイヤー骨格に固定した全身モデル
# ===========================================================================
def _numbers_rig(bulk=1.0, limb=1.0, heads=6.6):
    m = Model("", uv_scale=4, visible_bounds=(3.0, 3.2), vb_offset=(0, 1.2, 0),
              max_atlas=(1024, 1024))
    rig = HumanRig(m, Build(180, heads, 0.30, limb, bulk=bulk,
                            player_anchor=True), player_rig=True)
    rig.flesh()
    return m, rig


def build_numbers_1() -> Model:
    """ナンバーズ1 Rt-0001（鳴海弦）— 全身のねじ穴から眼球が突出する。"""
    m, rig = _numbers_rig(bulk=1.0, limb=1.0)
    m.identifier = "geometry.kaiju8.numbers_1"
    rig.combat_suit(spine=7, holster=False)
    L = rig.M if False else rig.L
    sockets = [("chest", (-0.26, 0.62, -0.60)), ("chest", (0.10, 0.44, -0.60)),
               ("body", (-0.18, 0.20, -0.62)), ("body", (0.22, 0.34, -0.62))]
    for bone, (u, v, d) in sockets:
        rig.b(bone).add(Cube(
            (u * L.chest_w, L.hip_y + v * (L.chest_top - L.hip_y), d * L.chest_d),
            (L.chest_w * 0.20, L.chest_w * 0.20, L.chest_d * 0.14), "eye",
            uv_scale=8, decals={"north": "single_eye"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = PLAYER_ARM_X * sgn
        rig.b(f"{side}Arm").add(Cube(
            (cx - L.arm_t * 0.18, L.elbow_y + (L.shoulder_y - L.elbow_y) * 0.35,
             -L.arm_t * 0.64), (L.arm_t * 0.36, L.arm_t * 0.36, L.arm_t * 0.12),
            "eye", uv_scale=8, decals={"north": "single_eye"}))
        rig.b(f"{side}Leg").add(Cube(
            (sgn * L.stance - L.thigh_t * 0.18,
             L.knee_y + (L.hip_y - L.knee_y) * 0.45, -L.thigh_t * 0.62),
            (L.thigh_t * 0.36, L.thigh_t * 0.36, L.thigh_t * 0.12), "eye",
            uv_scale=8, decals={"north": "single_eye"}))
    m.pack()
    return m


def build_numbers_2() -> Model:
    """ナンバーズ2 FS-1002（四ノ宮功）— 手から前腕を覆う巨大ガントレット。"""
    m, rig = _numbers_rig(bulk=1.12, limb=1.06)
    m.identifier = "geometry.kaiju8.numbers_2"
    rig.combat_suit(spine=7, holster=False)
    L = rig.L
    for side, sgn in (("right", -1), ("left", 1)):
        cx = PLAYER_ARM_X * sgn
        fore = rig.b(f"{side}Forearm")
        fore.add(Cube((cx - L.forearm_t * 1.05, L.wrist_y - L.hand_l * 0.5,
                       -L.forearm_t * 1.05),
                      (L.forearm_t * 2.10, (L.elbow_y - L.wrist_y) + L.hand_l * 0.5,
                       L.forearm_t * 2.10), "armor", uv_scale=3))
        fore.add(Cube((cx - L.forearm_t * 0.90, L.wrist_y - L.hand_l * 0.7,
                       -L.forearm_t * 1.15),
                      (L.forearm_t * 1.80, L.forearm_t * 1.10, L.forearm_t * 0.40),
                      "accent", uv_scale=5, decals={"north": "core"}))
        for i in range(3):
            fore.add(Cube((cx - L.forearm_t * (0.95 - i * 0.10),
                           L.wrist_y + (L.elbow_y - L.wrist_y) * (0.15 + i * 0.28),
                           L.forearm_t * 0.60),
                          (L.forearm_t * (1.90 - i * 0.20), L.forearm_t * 0.34,
                           L.forearm_t * 0.55), "plate", uv_scale=4,
                          rotation=(-16, 0, 0)))
        hand = rig.b(f"{side}Hand")
        hand.add(Cube((cx - L.forearm_t * 0.86, L.wrist_y - L.hand_l * 1.25,
                       -L.forearm_t * 0.80),
                      (L.forearm_t * 1.72, L.hand_l * 1.30, L.forearm_t * 1.60),
                      "armor", uv_scale=4))
    m.pack()
    return m


def build_numbers_4() -> Model:
    """ナンバーズ4（四ノ宮キコル）— ワルキューレ意匠の全身鎧、腰のスカート、背の翼。"""
    m, rig = _numbers_rig(bulk=0.96, limb=0.96, heads=6.8)
    m.identifier = "geometry.kaiju8.numbers_4"
    rig.combat_suit(spine=5, holster=False, green="gold")
    L = rig.L
    chest = rig.b("chest")
    ch = L.chest_top - L.chest_bot
    chest.add(Cube((-L.chest_w * 0.58, L.chest_bot + ch * 0.10, -L.chest_d * 0.70),
                   (L.chest_w * 1.16, ch * 0.82, L.chest_d * 0.34), "armor",
                   uv_scale=3, decals={"north": "emblem"}))
    for sgn in (-1, 1):                                     # 肩の羽根飾り
        chest.add(Cube((sgn * L.chest_w * 0.52 - (L.chest_w * 0.30 if sgn > 0 else 0),
                        L.chest_top - ch * 0.10, -L.chest_d * 0.20),
                       (L.chest_w * 0.30, ch * 0.55, L.chest_d * 0.20), "gold",
                       uv_scale=4, rotation=(0, 0, -28 * sgn)))
    body = rig.b("body")
    for i, (w, h, z) in enumerate(((1.30, 0.42, -0.62), (1.16, 0.34, 0.50))):
        body.add(Cube((-L.hip_w * w / 2, L.pelvis_bot - L.total * (0.10 + i * 0.02),
                       z * L.waist_d),
                      (L.hip_w * w, L.total * h * 0.36, L.waist_d * 0.18), "gold",
                      uv_scale=3))                          # 腰から伸びるスカート
    for side, sgn in (("right", -1), ("left", 1)):
        cx = PLAYER_ARM_X * sgn
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.80, L.wrist_y + (L.elbow_y - L.wrist_y) * 0.10,
             -L.forearm_t * 0.95),
            (L.forearm_t * 1.60, (L.elbow_y - L.wrist_y) * 0.60, L.forearm_t * 0.70),
            "accent", uv_scale=5, decals={"north": "core"}))   # リパルサー
        wing = m.bone(f"{side}Wing", (sgn * L.chest_w * 0.34, L.chest_top - ch * 0.2,
                                      L.chest_d * 0.45), "chest",
                      rotation=(0, -34 * sgn, -14 * sgn))
        rig.bones[f"{side}Wing"] = wing
        for i in range(3):
            wx = sgn * L.chest_w * 0.34
            wing.add(Cube((min(wx, wx + sgn * L.total * (0.30 + i * 0.14)),
                           L.chest_top - ch * (0.10 + i * 0.30), L.chest_d * 0.46),
                          (L.total * (0.30 + i * 0.14), ch * 0.34, L.total * 0.010),
                          "wing", uv_scale=2))
            wing.add(Cube((min(wx, wx + sgn * L.total * (0.30 + i * 0.14)),
                           L.chest_top - ch * (0.10 + i * 0.30), L.chest_d * 0.44),
                          (L.total * (0.30 + i * 0.14), ch * 0.05, L.total * 0.016),
                          "gold", uv_scale=3))
    m.pack()
    return m


def build_numbers_6() -> Model:
    """ナンバーズ6 FN-0006（市川レノ）— 全身密着型、配管とピストン、胸に006。"""
    m, rig = _numbers_rig(bulk=0.94, limb=0.94, heads=6.8)
    m.identifier = "geometry.kaiju8.numbers_6"
    rig.combat_suit(spine=6, holster=False, green="accent")
    L = rig.L
    ch = L.chest_top - L.chest_bot
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.34, L.chest_bot + ch * 0.30, -L.chest_d * 0.70),
        (L.chest_w * 0.68, ch * 0.30, L.chest_d * 0.10), "decal", uv_scale=8,
        decals={"north": "number"}))
    for side, sgn in (("right", -1), ("left", 1)):
        cx = PLAYER_ARM_X * sgn
        for i in range(3):                                   # 背と肩の配管
            rig.b("chest").add(Cube(
                (sgn * L.chest_w * (0.20 + i * 0.16) - L.chest_w * 0.06,
                 L.chest_bot + ch * 0.10, L.chest_d * 0.44),
                (L.chest_w * 0.12, ch * 0.80, L.chest_d * 0.26), "armor",
                uv_scale=4))
        rig.b(f"{side}Arm").add(Cube(
            (cx - L.arm_t * 0.62, L.elbow_y, L.arm_t * 0.30),
            (L.arm_t * 1.24, (L.shoulder_y - L.elbow_y) * 0.9, L.arm_t * 0.44),
            "armor", uv_scale=4))                            # ピストン
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.52, L.wrist_y + (L.elbow_y - L.wrist_y) * 0.2,
             -L.forearm_t * 0.86),
            (L.forearm_t * 1.04, (L.elbow_y - L.wrist_y) * 0.5, L.forearm_t * 0.34),
            "accent", uv_scale=5, decals={"north": "powerline"}))
    m.pack()
    return m


def build_numbers_10() -> Model:
    """ナンバーズ10（保科宗四郎）— 淡紫の鱗鎧、長い機械の尾、胸に十字の単眼。"""
    m, rig = _numbers_rig(bulk=1.0, limb=1.0, heads=6.6)
    m.identifier = "geometry.kaiju8.numbers_10"
    rig.combat_suit(spine=7, holster=False, green="accent")
    L = rig.L
    ch = L.chest_top - L.chest_bot
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.22, L.chest_bot + ch * 0.34, -L.chest_d * 0.72),
        (L.chest_w * 0.44, ch * 0.36, L.chest_d * 0.10), "red", uv_scale=8,
        decals={"north": "cross_slit"}))                     # 胸の十字眼
    k = KaijuParts(rig)
    k.tail(6, length=1.25, thickness=0.26, style="armor", tip_style="accent",
           droop=-6, spikes=True)
    for side, sgn in (("right", -1), ("left", 1)):
        cx = PLAYER_ARM_X * sgn
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.24, L.wrist_y, -L.forearm_t * 0.88),
            (L.forearm_t * 0.48, (L.elbow_y - L.wrist_y) * 0.8, L.forearm_t * 0.20),
            "accent", uv_scale=6, decals={"north": "powerline"}))
    m.pack()
    return m


NUMBERS = {
    "numbers_1": (build_numbers_1, "numbers_1"),
    "numbers_2": (build_numbers_2, "numbers_2"),
    "numbers_4": (build_numbers_4, "numbers_4"),
    "numbers_6": (build_numbers_6, "numbers_6"),
    "numbers_10": (build_numbers_10, "numbers_10"),
}


# ===========================================================================
#  projectiles
# ===========================================================================
def build_beam() -> Model:
    m = Model("geometry.kaiju8.beam", uv_scale=3, visible_bounds=(2.0, 1.0),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-0.9, -0.9, -9), (1.8, 1.8, 18), "base"))
    b.add(Cube((-1.8, -1.8, -4), (3.6, 3.6, 7), "base", inflate=-0.7))
    b.add(Cube((-2.6, -2.6, -1), (5.2, 5.2, 2), "base", inflate=-1.5))
    m.pack()
    return m


def build_acid() -> Model:
    m = Model("geometry.kaiju8.acid", uv_scale=4, visible_bounds=(1.2, 1.2),
              max_atlas=(256, 256), vb_offset=(0, 0, 0))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-2.4, -2.4, -2.4), (4.8, 4.8, 4.8), "base"))
    b.add(Cube((-3.4, -1.4, -1.4), (6.8, 2.8, 2.8), "base", inflate=-1.0))
    b.add(Cube((-1.4, -3.4, -1.4), (2.8, 6.8, 2.8), "base", inflate=-1.0))
    m.pack()
    return m


def build_bullet() -> Model:
    m = Model("geometry.kaiju8.bullet", uv_scale=6, visible_bounds=(0.6, 0.6),
              max_atlas=(128, 128), vb_offset=(0, 0, 0))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-0.4, -0.4, -2.2), (0.8, 0.8, 4.4), "base"))
    m.pack()
    return m


# ===========================================================================
def main() -> None:
    print("entities:")
    emit(build_no8(), palettes.NO8, "kaiju_no8", "kaiju_no8", 11)
    emit(build_no9(), palettes.NO9, "kaiju_no9", "kaiju_no9", 12)
    emit(build_no10(), palettes.NO10, "kaiju_no10", "kaiju_no10", 13)
    emit(build_honju(), palettes.HONJU, "honju", "honju", 15)
    emit(build_yoju(), palettes.YOJU, "yoju", "yoju", 14)
    emit(build_parasite(), palettes.PARASITE, "parasite", "parasite", 24)

    for key in CHARACTERS:
        pal = dict(palettes.ALL[CHARACTERS[key]["pal"]])
        pal.update({k: v for k, v in palettes.WEAPON.items() if k not in pal})
        emit(build_character(key), pal, key, key, mctexture._h(key) % 9000)

    for name, (builder, pal) in NUMBERS.items():
        emit(builder(), palettes.ALL[pal], name, name, mctexture._h(name) % 9000)

    emit(build_beam(), palettes.BEAM, "beam", "beam", 21)
    emit(build_acid(), palettes.ACID, "acid", "acid", 22)
    emit(build_bullet(), palettes.BULLET, "bullet", "bullet", 23)


if __name__ == "__main__":
    main()
