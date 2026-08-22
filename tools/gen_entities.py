# -*- coding: utf-8 -*-
"""Every entity model + its texture, built from the proportional rig."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcmodel import Cube, Model  # noqa: E402
from mctexture import Painter  # noqa: E402
from rig import Build, BeastRig, HumanRig, KaijuParts, HAIR, HAIR_FRONT  # noqa: E402
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
                  mount=(-10, 0, 0), stubble=True),
    "reno": dict(cm=174, heads=7.5, sh=0.236, limb=0.94, female=False,
                 hair="reno", pal="reno", weapon="df_rifle", mount=(-84, 0, 0)),
    "mina": dict(cm=169, heads=7.5, sh=0.226, limb=0.90, female=True,
                 hair="mina", pal="mina", weapon="cannon_t25", mount=(-86, 0, 0),
                 ponytail=("tail", (0.0, 0.50, 0.52), 4, 3.2, 0.34), visor=True),
    "hoshina": dict(cm=171, heads=7.0, sh=0.244, limb=0.99, female=False,
                    hair="hoshina", pal="hoshina", weapon="twin_sw2033",
                    mount=(-30, 0, 0), twin=True),
    "kikoru": dict(cm=157, heads=6.5, sh=0.222, limb=0.88, female=True,
                   hair="kikoru", pal="kikoru", weapon="axe_03ax",
                   mount=(-34, 0, 0),
                   twintail=((-0.50, 0.36, 0.30), (0.50, 0.36, 0.30), 4, 3.0, 0.28)),
    "narumi": dict(cm=175, heads=8.0, sh=0.240, limb=0.98, female=False,
                   hair="narumi", pal="narumi", weapon="gunblade_gs3305",
                   mount=(-40, 0, 0), front_hair=True),
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
    rig = HumanRig(m, build)
    rig.flesh()
    rig.combat_suit()
    rig.hair(HAIR[c["hair"]])
    if c.get("front_hair"):
        for origin, size in HAIR_FRONT[c["hair"]]:
            L = rig.L
            rig.b("hair").add(Cube(
                (origin[0] * L.head_w, L.chin + origin[1] * L.head_h,
                 origin[2] * L.head_d),
                (size[0] * L.head_w, size[1] * L.head_h, size[2] * L.head_d),
                "decal", uv_scale=3))
    if c.get("ponytail"):
        name, anchor, seg, length, thick = c["ponytail"]
        rig.ponytail(name, anchor, seg, length, thick, tilt=12)
    if c.get("twintail"):
        aL, aR, seg, length, thick = c["twintail"]
        rig.ponytail("tailR", aL, seg, length, thick, tilt=9)
        rig.ponytail("tailL", aR, seg, length, thick, tilt=9)
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
    m = Model("geometry.kaiju8.no8", uv_scale=3, visible_bounds=(4.0, 4.0),
              vb_offset=(0, 1.5, 0), max_atlas=(1024, 1024))
    rig = HumanRig(m, Build(205, 7.0, 0.345, 1.42, bulk=1.40, arm_len=1.14),
                   player_rig=True)
    rig.flesh(skin="hide", suit="hide")
    k = KaijuParts(rig)
    k.mask(horns=2, crest=True, damage=True, throat_teeth=True, skull=True)
    k.plates(limb_style="bone")
    k.mantle(plate="plate", top="bone", spines=5)
    k.claws(fingers=3)
    L = rig.L
    # 発光ラインは腹部が最大面積、次いで手首・足首・背骨
    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        rig.b(f"{side}Hand").add(Cube(
            (cx - L.forearm_t * 0.34, L.wrist_y - L.hand_l * 0.2, -L.forearm_t * 0.52),
            (L.forearm_t * 0.68, L.hand_l * 0.5, L.forearm_t * 0.08), "crack",
            uv_scale=5))
        rig.b(f"{side}Foot").add(Cube(
            (sgn * L.stance - L.shin_t * 0.34, L.foot_h * 0.2, -L.foot_l * 0.10),
            (L.shin_t * 0.68, L.foot_h * 0.6, L.foot_l * 0.08), "crack", uv_scale=5))
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
        emit(build_character(key), pal, key, key, abs(hash(key)) % 9000)

    emit(build_beam(), palettes.BEAM, "beam", "beam", 21)
    emit(build_acid(), palettes.ACID, "acid", "acid", 22)
    emit(build_bullet(), palettes.BULLET, "bullet", "bullet", 23)


if __name__ == "__main__":
    main()
