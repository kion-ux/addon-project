# -*- coding: utf-8 -*-
"""敵（センチネル / MRD）と、技が生む小物エンティティのモデル。

小物 (``K.PROP_ENTITIES``) は技の見た目そのものなので、ここが手を抜くと
どれだけ良いパーティクルを足しても画面が安っぽくなる。芯になる立体は必ず置く。
"""
from __future__ import annotations

import math

import _path  # noqa: F401

import colours  # noqa: E402
import contract as K  # noqa: E402
from common import emit  # noqa: E402
from mcmodel import Cube, Model  # noqa: E402
from rig import Build, HumanRig  # noqa: E402


# ===========================================================================
#  センチネル
# ===========================================================================
def sentinel_dress(rig: HumanRig, prime: bool = False) -> None:
    L = rig.L
    ch = L.chest_top - L.chest_bot
    head = rig.b("head")
    chest = rig.b("chest")
    body = rig.b("body")

    # --- 頭: 目のない装甲面 + オプティックバー
    head.add(Cube((-L.head_w * 0.56, L.chin, -L.head_d * 0.58),
                  (L.head_w * 1.12, L.head_h * 1.02, L.head_d * 1.10), "robot",
                  uv_scale=5, decals={"north": "sentinel_face"}))
    # 側頭のフィン
    for sgn in (-1, 1):
        head.add(Cube((sgn * L.head_w * 0.56 - (L.head_w * 0.10 if sgn > 0 else 0),
                       L.chin + L.head_h * 0.28, -L.head_d * 0.20),
                      (L.head_w * 0.10, L.head_h * 0.52, L.head_d * 0.56),
                      "robot_dark", uv_scale=4))
    # 額のセンサー
    head.add(Cube((-L.head_w * 0.14, L.chin + L.head_h * 0.74, -L.head_d * 0.62),
                  (L.head_w * 0.28, L.head_h * 0.22, L.head_d * 0.10), "optic",
                  uv_scale=6, decals={"north": "sentinel_optic"}))

    # --- 胴: パネル分割と胸部コア
    chest.add(Cube((-L.chest_w * 0.60, L.chest_bot, -L.chest_d * 0.66),
                   (L.chest_w * 1.20, ch, L.chest_d * 1.32), "robot",
                   uv_scale=3, decals={"north": "panel_seam"}))
    chest.add(Cube((-L.chest_w * 0.22, L.chest_bot + ch * 0.42, -L.chest_d * 0.72),
                   (L.chest_w * 0.44, ch * 0.34, L.chest_d * 0.14), "optic",
                   uv_scale=5, decals={"north": "sentinel_optic"}))
    body.add(Cube((-L.waist_w * 0.56, L.pelvis_bot, -L.waist_d * 0.62),
                  (L.waist_w * 1.12, L.chest_bot - L.pelvis_bot,
                   L.waist_d * 1.24), "robot_dark", uv_scale=3,
                  decals={"north": "vent_grill"}))

    for side, sgn in (("right", -1), ("left", 1)):
        cx = sgn * (L.shoulder_w / 2 - L.arm_t / 2)
        lx = sgn * L.stance
        rig.b(f"{side}Shoulder").add(Cube(
            (cx - L.arm_t * 0.94, L.shoulder_y - L.arm_t * 1.16, -L.arm_t * 0.94),
            (L.arm_t * 1.88, L.arm_t * 1.34, L.arm_t * 1.88), "robot",
            uv_scale=3, decals={"up": "rivets"}))
        rig.b(f"{side}Forearm").add(Cube(
            (cx - L.forearm_t * 0.80, L.wrist_y, -L.forearm_t * 0.80),
            (L.forearm_t * 1.60, (L.elbow_y - L.wrist_y) * 0.82,
             L.forearm_t * 1.60), "robot_dark", uv_scale=3))
        # 掌のビーム口
        rig.b(f"{side}Hand").add(Cube(
            (cx - L.forearm_t * 0.44, L.wrist_y - L.hand_l * 1.10,
             -L.forearm_t * 0.44),
            (L.forearm_t * 0.88, L.hand_l * 0.40, L.forearm_t * 0.88), "optic",
            uv_scale=5, decals={"down": "sentinel_optic"}))
        rig.b(f"{side}Shin").add(Cube(
            (lx - L.shin_t * 0.74, L.ankle_y, -L.shin_t * 0.80),
            (L.shin_t * 1.48, (L.knee_y - L.ankle_y) * 0.76, L.shin_t * 1.40),
            "robot_dark", uv_scale=3))
        rig.b(f"{side}Foot").add(Cube(
            (lx - L.shin_t * 0.76, 0, -L.foot_l * 0.72),
            (L.shin_t * 1.52, L.foot_h * 1.24, L.foot_l * 0.78), "robot",
            uv_scale=3))
    if prime:
        # 背部の推進ユニットと警告帯
        chest.add(Cube((-L.chest_w * 0.44, L.chest_bot + ch * 0.20,
                        L.chest_d * 0.56),
                       (L.chest_w * 0.88, ch * 0.60, L.chest_d * 0.42),
                       "hazard", uv_scale=4, decals={"south": "hazard_stripe"}))


def mrd_dress(rig: HumanRig) -> None:
    L = rig.L
    ch = L.chest_top - L.chest_bot
    rig.b("chest").add(Cube(
        (-L.chest_w * 0.56, L.chest_bot + ch * 0.06, -L.chest_d * 0.64),
        (L.chest_w * 1.12, ch * 0.86, L.chest_d * 1.28), "armor", uv_scale=4,
        decals={"north": "hazard_stripe"}))
    rig.b("head").add(Cube(
        (-L.head_w * 0.58, L.chin + L.head_h * 0.16, -L.head_d * 0.60),
        (L.head_w * 1.16, L.head_h * 0.88, L.head_d * 1.16), "armor",
        uv_scale=5))
    rig.b("head").add(Cube(
        (-L.head_w * 0.56, L.chin + L.head_h * 0.40, -L.head_d * 0.66),
        (L.head_w * 1.12, L.head_h * 0.26, L.head_d * 0.14), "goggle",
        uv_scale=6, decals={"north": "goggles"}))
    rig.b("body").add(Cube(
        (-L.hip_w * 0.58, L.abdomen_bot - L.total * 0.018, -L.waist_d * 0.62),
        (L.hip_w * 1.16, L.total * 0.036, L.waist_d * 1.24), "cloth",
        uv_scale=5))


def build_humanoid(key: str, dress, **kw) -> Model:
    c = K.CHARACTERS[key]
    px = c["cm"] * 32.0 / 180.0
    # 巨体ほど 1 モデル単位あたりのテクセルを減らさないとアトラスに収まらない
    scale = 3 if px < 46 else (2 if px < 90 else 1)
    m = Model(K.geo(key), uv_scale=scale,
              visible_bounds=(max(3.0, px / 9), max(3.0, px / 7)),
              vb_offset=(0, px / 32, 0), max_atlas=(1024, 1024))
    rig = HumanRig(m, Build(c["cm"], c["heads"], c["sh"], c["limb"],
                            female=c["female"], bulk=c["bulk"]),
                   player_rig=True)
    rig.flesh()
    dress(rig, **kw)
    return m


def build_drone() -> Model:
    """浮遊する偵察ドローン: 中央のコアを三枚のフィンが囲む。"""
    m = Model(K.geo("sentinel_drone"), uv_scale=4, visible_bounds=(1.6, 1.6),
              vb_offset=(0, 0.4, 0), max_atlas=(256, 256))
    body = m.bone("body", (0, 0, 0))
    body.add(Cube((-4, 2, -4), (8, 8, 8), "robot", uv_scale=4,
                  decals={"north": "sentinel_face"}))
    body.add(Cube((-2.4, 4, -5.2), (4.8, 4, 1.4), "optic", uv_scale=6,
                  decals={"north": "sentinel_optic"}))
    head = m.bone("head", (0, 6, 0), "body")
    head.add(Cube((-2.6, 10, -2.6), (5.2, 2.4, 5.2), "robot_dark", uv_scale=4))
    for i in range(3):
        a = i * 2 * math.pi / 3
        name = f"fin{i}"
        b = m.bone(name, (0, 6, 0), "body",
                   rotation=(0, math.degrees(a), 0))
        b.add(Cube((-1.2, 5.2, 4.0), (2.4, 1.6, 5.0), "robot_dark", uv_scale=4))
        b.add(Cube((-0.9, 4.4, 8.4), (1.8, 1.2, 1.8), "optic", uv_scale=6))
    return m


# ===========================================================================
#  小物 — 技の見た目そのもの
# ===========================================================================
def build_metal_shard() -> Model:
    m = Model(K.geo("metal_shard"), uv_scale=6, visible_bounds=(1.0, 1.0),
              vb_offset=(0, 0, 0), max_atlas=(128, 128))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-0.7, -0.7, -4.0), (1.4, 1.4, 8.0), "shard"))
    b.add(Cube((-1.4, -0.4, -1.6), (2.8, 0.8, 4.0), "shard", inflate=-0.2))
    b.add(Cube((-0.4, -1.4, -1.6), (0.8, 2.8, 4.0), "shard", inflate=-0.2))
    m.pack()
    return m


def build_orbit_shard() -> Model:
    m = Model(K.geo("orbit_shard"), uv_scale=6, visible_bounds=(1.0, 1.0),
              vb_offset=(0, 0, 0), max_atlas=(128, 128))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-1.0, -1.0, -2.6), (2.0, 2.0, 5.2), "shard"))
    b.add(Cube((-0.5, -2.2, -1.2), (1.0, 4.4, 2.4), "shard", inflate=-0.3))
    m.pack()
    return m


def build_debris() -> Model:
    m = Model(K.geo("debris"), uv_scale=3, visible_bounds=(1.6, 1.6),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-4, -4, -4), (8, 8, 8), "rock"))
    b.add(Cube((-5.2, -2.4, -2.4), (10.4, 4.8, 4.8), "rock", inflate=-1.4))
    b.add(Cube((-2.4, -5.2, -2.4), (4.8, 10.4, 4.8), "rock", inflate=-1.4))
    b.add(Cube((-2.4, -2.4, -5.2), (4.8, 4.8, 10.4), "rock", inflate=-1.4))
    m.pack()
    return m


def _bolt(key: str, colour_key: str, radius: float = 2.6) -> Model:
    m = Model(K.geo(key), uv_scale=4, visible_bounds=(1.4, 1.4),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    b = m.bone("body", (0, 0, 0))
    r = radius
    b.add(Cube((-r, -r, -r), (r * 2, r * 2, r * 2), "base"))
    b.add(Cube((-r * 1.5, -r * 0.5, -r * 0.5),
               (r * 3, r, r), "base", inflate=-r * 0.35))
    b.add(Cube((-r * 0.5, -r * 1.5, -r * 0.5),
               (r, r * 3, r), "base", inflate=-r * 0.35))
    b.add(Cube((-r * 0.5, -r * 0.5, -r * 1.5),
               (r, r, r * 3), "base", inflate=-r * 0.35))
    m.pack()
    return m


def build_sentinel_beam() -> Model:
    m = Model(K.geo("sentinel_beam"), uv_scale=3, visible_bounds=(2.4, 1.2),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-1.1, -1.1, -11), (2.2, 2.2, 22), "base"))
    b.add(Cube((-2.2, -2.2, -5), (4.4, 4.4, 9), "base", inflate=-0.9))
    b.add(Cube((-3.2, -3.2, -1.4), (6.4, 6.4, 2.8), "base", inflate=-1.9))
    m.pack()
    return m


def build_barrier_dome() -> Model:
    """磁力障壁。八角柱のリングを三段に積んで球状に見せる。"""
    m = Model(K.geo("barrier_dome"), uv_scale=1, visible_bounds=(8.0, 8.0),
              vb_offset=(0, 0, 0), max_atlas=(256, 256))
    b = m.bone("body", (0, 0, 0))
    for level, (y, r) in enumerate(((-14, 34), (2, 40), (18, 30), (30, 16))):
        n = 8
        for i in range(n):
            a = i * 2 * math.pi / n
            b.add(Cube((r * math.cos(a) - 3, y, r * math.sin(a) - 3),
                       (6, 15, 6), "energy", uv_scale=1,
                       rotation=(0, -math.degrees(a), 0)))
    m.pack()
    return m


def build_ruin_sphere() -> Model:
    """磁界の棺。中心の核と、それを取り巻く圧縮された金属塊。"""
    m = Model(K.geo("ruin_sphere"), uv_scale=1, visible_bounds=(9.0, 9.0),
              vb_offset=(0, 0, 0), max_atlas=(512, 256))
    core = m.bone("core", (0, 0, 0))
    core.add(Cube((-11, -11, -11), (22, 22, 22), "energy"))
    core.add(Cube((-15, -6, -6), (30, 12, 12), "energy", inflate=-4))
    core.add(Cube((-6, -15, -6), (12, 30, 12), "energy", inflate=-4))
    core.add(Cube((-6, -6, -15), (12, 12, 30), "energy", inflate=-4))
    for ring in range(3):
        bone = m.bone(f"shell{ring}", (0, 0, 0), "core",
                      rotation=(ring * 47, ring * 61, ring * 29))
        n = 6
        r = 20 + ring * 6
        for i in range(n):
            a = i * 2 * math.pi / n
            bone.add(Cube((r * math.cos(a) - 4, r * math.sin(a) * 0.4 - 4,
                           r * math.sin(a) - 4), (8, 8, 8), "shard",
                          uv_scale=2, rotation=(i * 23, i * 41, i * 17)))
    m.pack()
    return m


def build_steel_platform() -> Model:
    """鋼鉄の玉座。乗って飛ぶ足場。"""
    m = Model(K.geo("steel_platform"), uv_scale=2, visible_bounds=(3.0, 1.6),
              vb_offset=(0, 0.2, 0), max_atlas=(256, 256))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-13, 0, -13), (26, 3, 26), "shard", uv_scale=2,
               decals={"up": "panel_seam"}))
    b.add(Cube((-15, -2, -15), (30, 2, 30), "shard", uv_scale=2))
    for sx in (-1, 1):
        for sz in (-1, 1):
            b.add(Cube((sx * 11 - 2, 3, sz * 11 - 2), (4, 5, 4), "shard",
                       uv_scale=3, decals={"north": "mag_core"}))
    ring = m.bone("ring", (0, 0, 0), "body")
    for i in range(8):
        a = i * math.pi / 4
        ring.add(Cube((17 * math.cos(a) - 2, -1, 17 * math.sin(a) - 2),
                      (4, 2, 4), "energy", uv_scale=2,
                      rotation=(0, -math.degrees(a), 0)))
    m.pack()
    return m


def build_iron_cage() -> Model:
    """鋼鉄拘束。標的を囲う鉄格子。"""
    m = Model(K.geo("iron_cage"), uv_scale=2, visible_bounds=(3.0, 4.0),
              vb_offset=(0, 1.0, 0), max_atlas=(512, 512))
    b = m.bone("body", (0, 0, 0))
    for i in range(8):
        a = i * math.pi / 4
        r = 11
        b.add(Cube((r * math.cos(a) - 1.4, 0, r * math.sin(a) - 1.4),
                   (2.8, 34, 2.8), "shard", uv_scale=3,
                   rotation=(0, -math.degrees(a), 0)))
    for y in (1, 16, 32):
        for i in range(8):
            a = i * math.pi / 4
            b.add(Cube((11 * math.cos(a) - 2.4, y, 11 * math.sin(a) - 2.4),
                       (4.8, 3, 4.8), "shard", uv_scale=3,
                       rotation=(0, -math.degrees(a), 22)))
    m.pack()
    return m


PROPS = {
    "metal_shard": (build_metal_shard, "shard"),
    "orbit_shard": (build_orbit_shard, "shard"),
    "debris": (build_debris, "debris"),
    "hex_bolt": (lambda: _bolt("hex_bolt", "energy_crimson"), "energy_crimson"),
    "fire_bolt": (lambda: _bolt("fire_bolt", "energy_fire", 3.0), "energy_fire"),
    "sentinel_beam": (build_sentinel_beam, "energy_orange"),
    "barrier_dome": (build_barrier_dome, "energy_violet"),
    "ruin_sphere": (build_ruin_sphere, "energy_violet"),
    "steel_platform": (build_steel_platform, "shard"),
    "iron_cage": (build_iron_cage, "shard"),
}


def main() -> None:
    print("enemies:")
    emit(build_humanoid("sentinel", sentinel_dress), colours.SENTINEL,
         "sentinel", seed=301)
    emit(build_humanoid("prime_sentinel", sentinel_dress, prime=True),
         colours.PRIME_SENTINEL, "prime_sentinel", seed=302)
    emit(build_humanoid("mrd_trooper", mrd_dress), colours.MRD, "mrd_trooper",
         seed=303)
    emit(build_drone(), colours.SENTINEL, "sentinel_drone", seed=304)

    print("props:")
    for key, (fn, pal) in PROPS.items():
        emit(fn(), colours.ALL[pal], key, seed=abs(hash(key)) % 8000 + 11)


if __name__ == "__main__":
    main()
