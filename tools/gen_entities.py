"""Builds every entity geometry + its matching texture."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcmodel import Bone, Cube, Model  # noqa: E402
from mctexture import Painter  # noqa: E402
import palettes  # noqa: E402

RP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "packs", "kaiju8_RP")
GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", "kaiju8")


def emit(model: Model, palette: dict, geo_name: str, tex_name: str, seed: int = 7) -> None:
    os.makedirs(GEO_DIR, exist_ok=True)
    os.makedirs(TEX_DIR, exist_ok=True)
    model.write(os.path.join(GEO_DIR, geo_name + ".geo.json"))
    p = Painter(model.tex_w, model.tex_h, seed)
    p.paint_model(model, palette)
    p.save(os.path.join(TEX_DIR, tex_name + ".png"))
    print(f"  {geo_name:34s} -> {tex_name}.png ({model.tex_w}x{model.tex_h})")


# ===========================================================================
#  怪獣8号 / Kaiju No.8  -- Kafka's transformed body
# ===========================================================================
def build_no8(ident="geometry.kaiju8.no8") -> Model:
    m = Model(ident, 256, 256, (3.6, 3.4), (0, 1.7, 0))
    body = m.bone("body", (0, 26, 0))
    body.add(Cube((-7, 14, -3.5), (14, 14, 7), "hide"))
    body.add(Cube((-6.5, 21, -5), (13, 7, 3), "plate"))          # pectoral armour
    body.add(Cube((-5, 14.5, -4.4), (10, 6, 1.4), "crack"))       # glowing abdomen
    body.add(Cube((-4, 26, 2.6), (8, 5, 2), "plate"))             # nape plate
    for i, (x, y) in enumerate([(-4, 25), (0, 25.5), (4, 25)]):   # dorsal spines
        body.add(Cube((x - 1, y, 3.2), (2, 5, 2), "horn", rotation=(-18, 0, 0)))
    waist = m.bone("waist", (0, 14, 0), "body")
    waist.add(Cube((-6, 8, -3), (12, 7, 6), "hide"))
    waist.add(Cube((-6.2, 9, -3.4), (12.4, 3, 6.8), "plate"))

    head = m.bone("head", (0, 28, 0), "body")
    head.add(Cube((-5, 28, -5), (10, 9, 9), "mask",
                  decals={"north": "mask_no8"}))
    head.add(Cube((-4, 25.5, -6.5), (8, 4, 7), "mask", decals={"north": "fangs"}))
    head.add(Cube((-5.5, 34, -5.5), (11, 3, 10), "plate"))        # crown crest
    for sx, sgn in ((-5.5, -1), (3.5, 1)):                        # horns
        hb = m.bone(f"horn_{'r' if sgn < 0 else 'l'}", (sx + 1, 36, 0), "head",
                    rotation=(-28, 0, 22 * sgn))
        hb.add(Cube((sx, 36, -1.5), (2.5, 7, 3), "horn"))
        hb.add(Cube((sx + 0.2, 42, -1), (2, 4, 2), "horn", rotation=(-24, 0, 0)))
    jaw = m.bone("jaw", (0, 27, -3), "head")
    jaw.add(Cube((-3.5, 23.5, -6), (7, 3, 6), "sinew", decals={"up": "maw"}))

    for side, sgn in (("right", -1), ("left", 1)):
        px = 7.5 * sgn
        arm = m.bone(f"{side}Arm", (px, 26, 0), "body")
        ax = -13.5 if sgn < 0 else 7.5
        arm.add(Cube((ax, 12, -3), (6, 15, 6), "hide"))
        arm.add(Cube((ax - 0.6, 20, -3.6), (7.2, 7, 7.2), "plate"))     # shoulder pad
        arm.add(Cube((ax - 0.4, 11.5, -3.4), (6.8, 6, 6.8), "plate"))   # vambrace
        # NOTE: never name these rightItem/leftItem - those are real player bones,
        # and this geometry is also worn as an attachable during transformation.
        hand = m.bone(f"{side}Claw", (ax + 3, 12, 0), f"{side}Arm")
        hand.add(Cube((ax + 0.4, 6, -2.6), (5.2, 6, 5.2), "hide"))
        for i in range(3):                                              # claws
            hand.add(Cube((ax + 0.6 + i * 1.7, 2.5, -2.2), (1.4, 4, 1.6), "claw",
                          rotation=(14, 0, 0)))

    for side, sgn in (("right", -1), ("left", 1)):
        px = 3.6 * sgn
        leg = m.bone(f"{side}Leg", (px, 14, 0), None)
        lx = -7 if sgn < 0 else 0
        leg.add(Cube((lx, 6.5, -3.2), (7, 8, 6.4), "hide"))
        knee = m.bone(f"{side}Shin", (px, 7, 0), f"{side}Leg")
        knee.add(Cube((lx + 0.4, 0, -3), (6.2, 7.5, 6), "hide"))
        knee.add(Cube((lx + 0.2, 4, -3.4), (6.6, 4, 6.8), "plate"))
        foot = m.bone(f"{side}Foot", (px, 0.5, 0), f"{side}Shin")
        foot.add(Cube((lx + 0.4, 0, -5.5), (6.2, 3, 8.5), "hide"))
        for i in range(3):
            foot.add(Cube((lx + 0.6 + i * 1.9, 0, -7), (1.6, 2, 2), "claw"))
    return m


# ===========================================================================
#  怪獣9号 / Kaiju No.9  -- humanoid, shape-shifting, pale mask face
# ===========================================================================
def build_no9() -> Model:
    m = Model("geometry.kaiju8.no9", 192, 192, (2.6, 3.0), (0, 1.5, 0))
    body = m.bone("body", (0, 24, 0))
    body.add(Cube((-5, 12, -2.5), (10, 13, 5), "coat"))
    body.add(Cube((-5.4, 19, -3), (10.8, 6, 6), "coat"))          # mantle
    body.add(Cube((-3, 14, -3.2), (6, 5, 1), "crack"))
    waist = m.bone("waist", (0, 12, 0), "body")
    waist.add(Cube((-4.5, 6, -2.5), (9, 7, 5), "skin"))

    head = m.bone("head", (0, 25, 0), "body")
    head.add(Cube((-4.5, 25, -4.5), (9, 9, 9), "mask", decals={"north": "mask_no8"}))
    head.add(Cube((-3.5, 25, -5.4), (7, 3, 2), "mask", decals={"north": "fangs"}))
    for i in range(6):                                            # tendril "hair"
        tx = -4.5 + i * 1.6
        tb = m.bone(f"tendril{i}", (tx, 33, 3), "head", rotation=(24 + i * 4, 0, 0))
        tb.add(Cube((tx, 27, 3.5), (1.4, 7, 1.4), "tendril"))
        tb.add(Cube((tx + 0.1, 22, 4.4), (1.2, 5.5, 1.2), "tendril", rotation=(18, 0, 0)))

    for side, sgn in (("right", -1), ("left", 1)):
        arm = m.bone(f"{side}Arm", (5 * sgn, 23, 0), "body")
        ax = -9 if sgn < 0 else 5
        arm.add(Cube((ax, 12, -2), (4, 12, 4), "coat"))
        arm.add(Cube((ax - 0.4, 19, -2.4), (4.8, 5, 4.8), "coat"))
        arm.add(Cube((ax + 0.1, 8, -1.9), (3.8, 4.5, 3.8), "skin"))
        for i in range(3):
            arm.add(Cube((ax + 0.2 + i * 1.3, 4.5, -1.6), (1.1, 4, 1.3), "claw",
                         rotation=(10, 0, 0)))
    for side, sgn in (("right", -1), ("left", 1)):
        leg = m.bone(f"{side}Leg", (2 * sgn, 12, 0), None)
        lx = -4 if sgn < 0 else 0
        leg.add(Cube((lx, 0, -2), (4, 12, 4), "coat"))
        leg.add(Cube((lx - 0.2, 0, -3), (4.4, 3, 5), "skin"))
    return m


# ===========================================================================
#  怪獣10号 / Kaiju No.10 -- winged brute
# ===========================================================================
def build_no10() -> Model:
    m = Model("geometry.kaiju8.no10", 256, 256, (5.2, 4.2), (0, 2.0, 0))
    body = m.bone("body", (0, 30, 0))
    body.add(Cube((-9, 16, -5), (18, 16, 10), "hide"))
    body.add(Cube((-7, 17, -6.2), (14, 12, 2), "belly"))
    body.add(Cube((-6, 30, -4), (12, 6, 8), "hide"))              # shoulders yoke
    body.add(Cube((-5, 20, -6.6), (10, 5, 1.4), "crack"))
    waist = m.bone("waist", (0, 16, 0), "body")
    waist.add(Cube((-7, 9, -4.5), (14, 8, 9), "hide"))

    head = m.bone("head", (0, 34, -2), "body")
    head.add(Cube((-6, 33, -9), (12, 10, 11), "hide"))
    head.add(Cube((-5, 30, -12), (10, 5, 8), "belly", decals={"north": "maw"}))
    head.add(Cube((-6.2, 35, -6), (12.4, 4, 6), "hide", decals={"north": "eyes_red"}))
    for sgn in (-1, 1):
        hb = m.bone(f"horn_{'r' if sgn < 0 else 'l'}", (5 * sgn, 42, -2), "head",
                    rotation=(-34, 0, 30 * sgn))
        hx = -7 if sgn < 0 else 4
        hb.add(Cube((hx, 41, -3), (3, 9, 3.4), "horn"))
        hb.add(Cube((hx + 0.3, 49, -2.4), (2.4, 6, 2.6), "horn", rotation=(-30, 0, 0)))
    jaw = m.bone("jaw", (0, 32, -6), "head")
    jaw.add(Cube((-4.6, 28.5, -12), (9.2, 4, 7), "belly", decals={"up": "maw"}))

    for side, sgn in (("right", -1), ("left", 1)):
        wing = m.bone(f"{side}Wing", (8 * sgn, 32, 4), "body",
                      rotation=(0, -22 * sgn, -12 * sgn))
        wx = -30 if sgn < 0 else 8
        base = 22 if sgn < 0 else 0
        wing.add(Cube((wx + base, 30, 4), (22, 3, 3), "horn"))           # arm bone
        wing.add(Cube((wx + base - (18 if sgn < 0 else -22), 30, 4.6),
                      (18, 2.4, 2.4), "horn"))
        panel = m.bone(f"{side}WingPanel", (8 * sgn, 32, 5), f"{side}Wing")
        panel.add(Cube((wx, 12, 5.2), (30, 19, 1.2), "wing"))
        panel.add(Cube((wx, 30, 5.0), (30, 3, 1.6), "hide"))

    for side, sgn in (("right", -1), ("left", 1)):
        arm = m.bone(f"{side}Arm", (9 * sgn, 30, 0), "body")
        ax = -16 if sgn < 0 else 9
        arm.add(Cube((ax, 14, -4), (7, 17, 8), "hide"))
        arm.add(Cube((ax - 0.6, 24, -4.6), (8.2, 8, 9.2), "hide"))
        arm.add(Cube((ax + 0.4, 8, -3.4), (6.2, 6.5, 6.8), "hide"))
        for i in range(3):
            arm.add(Cube((ax + 0.6 + i * 2.0, 4, -3), (1.8, 5, 2), "horn", rotation=(12, 0, 0)))
    for side, sgn in (("right", -1), ("left", 1)):
        leg = m.bone(f"{side}Leg", (4.5 * sgn, 16, 0), None)
        lx = -9 if sgn < 0 else 0
        leg.add(Cube((lx, 8, -4.5), (9, 9, 9), "hide"))
        shin = m.bone(f"{side}Shin", (4.5 * sgn, 9, 0), f"{side}Leg")
        shin.add(Cube((lx + 0.6, 0, -4), (7.8, 9, 8), "hide"))
        foot = m.bone(f"{side}Foot", (4.5 * sgn, 1, 0), f"{side}Shin")
        foot.add(Cube((lx + 0.6, 0, -8), (7.8, 3.5, 11), "hide"))
        for i in range(3):
            foot.add(Cube((lx + 1 + i * 2.4, 0, -10), (2, 2.5, 2.6), "horn"))
    tail = m.bone("tail", (0, 20, 4), "body", rotation=(18, 0, 0))
    tail.add(Cube((-3, 18, 4), (6, 6, 10), "hide"))
    tail2 = m.bone("tail2", (0, 18, 14), "tail", rotation=(14, 0, 0))
    tail2.add(Cube((-2, 15, 13), (4, 4.5, 12), "hide"))
    tail3 = m.bone("tail3", (0, 15, 25), "tail2", rotation=(12, 0, 0))
    tail3.add(Cube((-1.4, 12.5, 24), (2.8, 3, 11), "hide"))
    tail3.add(Cube((-1, 12.5, 34), (2, 2.4, 6), "horn"))
    return m


# ===========================================================================
#  余獣 / Yoju -- the swarming lesser kaiju
# ===========================================================================
def build_yoju() -> Model:
    m = Model("geometry.kaiju8.yoju", 128, 128, (2.0, 1.6), (0, 0.7, 0))
    body = m.bone("body", (0, 11, 0))
    body.add(Cube((-5, 6, -7), (10, 8, 15), "shell"))
    body.add(Cube((-4, 12, -5), (8, 3, 11), "shell"))
    body.add(Cube((-3.4, 7, -7.6), (6.8, 4, 3), "flesh"))
    for i in range(4):                                            # dorsal spikes
        body.add(Cube((-1, 14, -4 + i * 3.4), (2, 4, 2), "claw", rotation=(-18, 0, 0)))
    head = m.bone("head", (0, 11, -7), "body")
    head.add(Cube((-4, 6.5, -14), (8, 7, 7), "shell",
                  decals={"north": "eyes_gold"}))
    head.add(Cube((-3, 6, -17), (6, 3.5, 4), "flesh", decals={"north": "fangs"}))
    for sgn in (-1, 1):
        mb = m.bone(f"mandible_{'r' if sgn < 0 else 'l'}", (3 * sgn, 8, -15), "head",
                    rotation=(0, 18 * sgn, 0))
        mx = -5 if sgn < 0 else 3
        mb.add(Cube((mx, 6.5, -20), (2, 2, 6), "claw"))
    for i, (name, x, z, ang) in enumerate([
        ("leg_fr", -5.5, -5, -14), ("leg_fl", 4.5, -5, 14),
        ("leg_br", -5.5, 4, -14), ("leg_bl", 4.5, 4, 14),
    ]):
        b = m.bone(name, (x + 0.5, 8, z + 1), "body", rotation=(0, 0, ang))
        b.add(Cube((x - 1, 4, z), (2.5, 5, 2.5), "shell"))
        b.add(Cube((x - 1.6, 0, z - 0.4), (2, 5, 3.2), "shell", rotation=(0, 0, -ang)))
        b.add(Cube((x - 1.8, 0, z - 2.4), (2.2, 1.6, 3), "claw"))
    tail = m.bone("tail", (0, 10, 8), "body", rotation=(-12, 0, 0))
    tail.add(Cube((-2.5, 7.5, 7), (5, 5, 8), "shell"))
    tail2 = m.bone("tail2", (0, 9, 15), "tail", rotation=(-14, 0, 0))
    tail2.add(Cube((-1.6, 7.5, 14), (3.2, 3.2, 8), "shell"))
    tail2.add(Cube((-1, 7.6, 21), (2, 3, 5), "claw"))
    return m


# ===========================================================================
#  本獣 / Honju -- the large main-body kaiju
# ===========================================================================
def build_honju() -> Model:
    m = Model("geometry.kaiju8.honju", 256, 256, (4.4, 4.4), (0, 2.1, 0))
    body = m.bone("body", (0, 32, 0))
    body.add(Cube((-10, 18, -6), (20, 18, 12), "hide"))
    body.add(Cube((-8, 19, -7.4), (16, 14, 2), "belly"))
    body.add(Cube((-8, 33, -5), (16, 6, 10), "plate"))
    body.add(Cube((-6, 22, -7.8), (12, 5, 1.4), "crack"))
    for i in range(4):
        body.add(Cube((-2.5, 35, -4 + i * 3.6), (5, 6, 2.6), "plate", rotation=(-16, 0, 0)))
    waist = m.bone("waist", (0, 18, 0), "body")
    waist.add(Cube((-8, 10, -5), (16, 9, 10), "hide"))

    head = m.bone("head", (0, 37, -3), "body")
    head.add(Cube((-6.5, 35, -12), (13, 11, 12), "hide"))
    head.add(Cube((-6.6, 39, -8), (13.2, 4, 6), "plate", decals={"north": "eyes_red"}))
    head.add(Cube((-5, 34, -8), (10, 4, 4), "hide", decals={"north": "eyes_gold"}))
    head.add(Cube((-5, 33.5, -16), (10, 6, 5), "belly", decals={"north": "maw"}))
    for sgn in (-1, 1):
        hb = m.bone(f"horn_{'r' if sgn < 0 else 'l'}", (6 * sgn, 45, -3), "head",
                    rotation=(-20, 0, 26 * sgn))
        hx = -8 if sgn < 0 else 5
        hb.add(Cube((hx, 44, -4), (3, 8, 3.4), "claw"))
    jaw = m.bone("jaw", (0, 35, -8), "head")
    jaw.add(Cube((-4.8, 31, -16.5), (9.6, 4.5, 9), "belly", decals={"up": "maw"}))

    for side, sgn in (("right", -1), ("left", 1)):
        arm = m.bone(f"{side}Arm", (10 * sgn, 33, 0), "body")
        ax = -17 if sgn < 0 else 10
        arm.add(Cube((ax, 16, -4.5), (7, 18, 9), "hide"))
        arm.add(Cube((ax - 0.8, 27, -5.2), (8.6, 8, 10.4), "plate"))
        arm.add(Cube((ax + 0.4, 9, -4), (6.2, 8, 8), "hide"))
        for i in range(3):
            arm.add(Cube((ax + 0.6 + i * 2.1, 5, -3.6), (1.9, 5, 2.2), "claw", rotation=(12, 0, 0)))
    for side, sgn in (("right", -1), ("left", 1)):
        leg = m.bone(f"{side}Leg", (5 * sgn, 18, 0), None)
        lx = -10 if sgn < 0 else 0
        leg.add(Cube((lx, 9, -5), (10, 10, 10), "hide"))
        shin = m.bone(f"{side}Shin", (5 * sgn, 10, 0), f"{side}Leg")
        shin.add(Cube((lx + 0.8, 0, -4.5), (8.4, 10, 9), "hide"))
        foot = m.bone(f"{side}Foot", (5 * sgn, 1.5, 0), f"{side}Shin")
        foot.add(Cube((lx + 0.8, 0, -9), (8.4, 4, 12), "hide"))
        for i in range(3):
            foot.add(Cube((lx + 1.2 + i * 2.6, 0, -11.5), (2.2, 3, 3), "claw"))
    tail = m.bone("tail", (0, 24, 6), "body", rotation=(16, 0, 0))
    tail.add(Cube((-4, 21, 5), (8, 8, 12), "hide"))
    tail2 = m.bone("tail2", (0, 21, 17), "tail", rotation=(12, 0, 0))
    tail2.add(Cube((-2.6, 19, 16), (5.2, 5.5, 12), "hide"))
    tail3 = m.bone("tail3", (0, 19, 28), "tail2", rotation=(10, 0, 0))
    tail3.add(Cube((-1.6, 17, 27), (3.2, 3.4, 12), "hide"))
    tail3.add(Cube((-1.2, 17, 38), (2.4, 3, 7), "claw"))
    return m


# ===========================================================================
#  討伐隊員 / Defense Force personnel
# ===========================================================================
HAIR_STYLES = {
    "short": [((-4.3, 30.3, -4.3), (8.6, 3.4, 8.6)), ((-4.3, 26, 3.6), (8.6, 5, 1.4)),
              ((-4.4, 28, -4.6), (2.4, 3, 1.2)), ((2, 28, -4.6), (2.4, 3, 1.2))],
    "spiky": [((-4.3, 30.3, -4.3), (8.6, 3.6, 8.6)), ((-4.3, 26, 3.6), (8.6, 5, 1.4)),
              ((-3, 33.4, -3), (2, 2.4, 2)), ((0.5, 33.6, -1), (2, 2, 2)),
              ((-4.4, 27.5, -4.6), (2.6, 4, 1.2)), ((1.8, 27.5, -4.6), (2.6, 4, 1.2))],
    "long": [((-4.3, 30.3, -4.3), (8.6, 3.4, 8.6)), ((-4.5, 12, 3.4), (9, 18, 2.2)),
             ((-4.6, 24, -4.6), (2.6, 7, 1.4)), ((2, 24, -4.6), (2.6, 7, 1.4)),
             ((-4.6, 25, -4.4), (9.2, 6, 1.2))],
    "twin": [((-4.3, 30.3, -4.3), (8.6, 3.4, 8.6)), ((-4.5, 20, 3.4), (9, 10, 2.2)),
             ((-4.6, 24.5, -4.6), (9.2, 6.5, 1.3)),
             ((-7.2, 16, 1.5), (3, 14, 3)), ((4.2, 16, 1.5), (3, 14, 3)),
             ((-7.4, 27, 0.5), (3.4, 5, 4)), ((4.0, 27, 0.5), (3.4, 5, 4))],
    "swept": [((-4.3, 30.3, -4.3), (8.6, 3.4, 8.6)), ((-4.5, 22, 3.4), (9, 8, 2)),
              ((-4.6, 26.5, -4.6), (9.2, 4.6, 1.3)), ((-5.2, 27, -3), (1.2, 5, 7))],
}

WEAPONS = {
    "none": None,
    "rifle": [((-1.5, 9.5, -22), (3, 4, 26), "steel"), ((-1.2, 7.5, -12), (2.4, 3, 7), "suit"),
              ((-1.0, 13.5, -14), (2, 2, 9), "accent"), ((-1.6, 6, -4), (3.2, 5, 6), "suit")],
    "blades": [((-1.2, 10, -18), (2.4, 3.4, 18), "steel"), ((-1.4, 9, -3), (2.8, 4, 5), "suit")],
    "axe": [((-1.4, 8, -6), (2.8, 3, 26), "suit"), ((-4.5, 5, -22), (9, 9, 3), "steel"),
            ((-5.5, 6.5, -20.5), (11, 6, 2), "steel"), ((-1.6, 6.5, 16), (3.2, 4, 5), "steel")],
    "knife": [((-1.0, 10, -12), (2, 3, 11), "steel"), ((-1.3, 9, -2), (2.6, 4, 4), "suit")],
}


def build_soldier(ident, hair="short", weapon="knife", cape=False, coat=False) -> Model:
    m = Model(ident, 128, 128, (3.6, 3.0), (0, 1.2, 0))
    body = m.bone("body", (0, 24, 0))
    body.add(Cube((-4, 12, -2), (8, 12, 4), "suit"))
    body.add(Cube((-4.3, 17.5, -2.4), (8.6, 6.5, 4.8), "armor"))       # chest rig
    body.add(Cube((-4.4, 13, -2.6), (8.8, 3.2, 5.2), "armor"))          # belt
    body.add(Cube((-1.4, 18.5, -3.0), (2.8, 3, 1), "accent", decals={"north": "core"}))
    body.add(Cube((2.2, 19.5, -2.9), (2, 2.4, 1), "red", decals={"north": "emblem"}))
    if coat:
        body.add(Cube((-5.2, 6, -3.2), (10.4, 18, 6.4), "suit"))
    if cape:
        cp = m.bone("cape", (0, 24, 2.4), "body", rotation=(6, 0, 0))
        cp.add(Cube((-5, 4, 2.4), (10, 20, 1.2), "red"))

    head = m.bone("head", (0, 24, 0), "body")
    head.add(Cube((-4, 24, -4), (8, 8, 8), "skin", decals={"north": "face_human"}))
    hair_bone = m.bone("hair", (0, 24, 0), "head")
    for spec in HAIR_STYLES[hair]:
        hair_bone.add(Cube(spec[0], spec[1], "hair"))
    neck = m.bone("collar", (0, 24, 0), "body")
    neck.add(Cube((-4.2, 22.5, -2.4), (8.4, 2.6, 4.8), "armor"))

    for side, sgn in (("right", -1), ("left", 1)):
        arm = m.bone(f"{side}Arm", (5 * sgn, 22, 0), "body")
        ax = -8 if sgn < 0 else 4
        arm.add(Cube((ax, 12, -2), (4, 12, 4), "suit"))
        arm.add(Cube((ax - 0.35, 19, -2.35), (4.7, 5, 4.7), "armor"))   # pauldron
        arm.add(Cube((ax - 0.25, 12.5, -2.25), (4.5, 4, 4.5), "armor"))  # bracer
        arm.add(Cube((ax + 0.5, 20.2, -2.5), (3, 1.6, 1), "accent"))
    for side, sgn in (("right", -1), ("left", 1)):
        leg = m.bone(f"{side}Leg", (1.9 * sgn, 12, 0), None)
        lx = -3.9 if sgn < 0 else -0.1
        leg.add(Cube((lx, 0, -2), (4, 12, 4), "suit"))
        leg.add(Cube((lx - 0.3, 0, -2.4), (4.6, 4.5, 4.8), "armor"))     # boot
        leg.add(Cube((lx - 0.25, 6.5, -2.3), (4.5, 3.5, 4.6), "armor"))  # knee guard

    spec = WEAPONS.get(weapon)
    if spec:
        wb = m.bone("weapon", (-6, 12, 0), "rightArm", rotation=(-8, 0, 0))
        for origin, size, style in spec:
            wb.add(Cube((origin[0] - 6, origin[1], origin[2]), size, style))
        if weapon == "blades":                                           # 双刃刀 = twin
            wb2 = m.bone("weapon2", (6, 12, 0), "leftArm", rotation=(-8, 0, 0))
            for origin, size, style in spec:
                wb2.add(Cube((origin[0] + 6, origin[1], origin[2]), size, style, mirror=True))
    return m


# ===========================================================================
#  Projectiles / small props
# ===========================================================================
def build_beam() -> Model:
    m = Model("geometry.kaiju8.beam", 32, 32, (1.5, 1.0), (0, 0, 0))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-1, -1, -8), (2, 2, 16), "base"))
    b.add(Cube((-2, -2, -4), (4, 4, 6), "base", inflate=-0.6))
    return m


def build_acid() -> Model:
    m = Model("geometry.kaiju8.acid", 32, 32, (1.0, 1.0), (0, 0, 0))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-2.5, -2.5, -2.5), (5, 5, 5), "base"))
    b.add(Cube((-3.5, -1.5, -1.5), (7, 3, 3), "base", inflate=-1.2))
    return m


def build_bullet() -> Model:
    m = Model("geometry.kaiju8.bullet", 16, 16, (0.6, 0.6), (0, 0, 0))
    b = m.bone("body", (0, 0, 0))
    b.add(Cube((-0.5, -0.5, -2), (1, 1, 4), "base"))
    return m


def build_parasite() -> Model:
    """The finger-sized kaiju that crawls into Kafka's mouth."""
    m = Model("geometry.kaiju8.parasite", 32, 32, (0.6, 0.5), (0, 0.2, 0))
    b = m.bone("body", (0, 2, 0))
    b.add(Cube((-1.5, 1, -2), (3, 3, 5), "base"))
    b.add(Cube((-1.2, 1.4, -4), (2.4, 2.4, 2.5), "shell", decals={"north": "eyes_red"}))
    for i in range(3):
        b.add(Cube((-2.4, 1.2, -1 + i * 1.8), (1, 1, 1), "shell"))
        b.add(Cube((1.4, 1.2, -1 + i * 1.8), (1, 1, 1), "shell"))
    t = m.bone("tail", (0, 3, 3), "body", rotation=(-14, 0, 0))
    t.add(Cube((-0.8, 1.6, 2.5), (1.6, 1.6, 5), "base"))
    return m


# ===========================================================================
def main() -> None:
    print("entities:")
    emit(build_no8(), palettes.NO8, "kaiju_no8", "kaiju_no8", 11)
    emit(build_no9(), palettes.NO9, "kaiju_no9", "kaiju_no9", 12)
    emit(build_no10(), palettes.NO10, "kaiju_no10", "kaiju_no10", 13)
    emit(build_yoju(), palettes.YOJU, "yoju", "yoju", 14)
    emit(build_honju(), palettes.HONJU, "honju", "honju", 15)

    troops = [
        ("geometry.kaiju8.soldier", "officer", palettes.OFFICER, "short", "rifle", "soldier", {}),
        ("geometry.kaiju8.kafka", "kafka", palettes.KAFKA, "spiky", "knife", "kafka", {}),
        ("geometry.kaiju8.reno", "reno", palettes.RENO, "short", "knife", "reno", {}),
        ("geometry.kaiju8.mina", "mina", palettes.MINA, "long", "rifle", "mina", {"cape": True}),
        ("geometry.kaiju8.hoshina", "hoshina", palettes.HOSHINA, "swept", "blades", "hoshina", {"coat": True}),
        ("geometry.kaiju8.kikoru", "kikoru", palettes.KIKORU, "twin", "axe", "kikoru", {}),
    ]
    for ident, _key, pal, hair, weapon, tex, extra in troops:
        emit(build_soldier(ident, hair, weapon, **extra), pal, tex.replace("geometry.", ""), tex,
             abs(hash(tex)) % 9000)

    emit(build_beam(), palettes.BEAM, "beam", "beam", 21)
    emit(build_acid(), palettes.ACID, "acid", "acid", 22)
    emit(build_bullet(), palettes.BULLET, "bullet", "bullet", 23)
    emit(build_parasite(), palettes.PARASITE, "parasite", "parasite", 24)


if __name__ == "__main__":
    main()
