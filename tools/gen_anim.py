# -*- coding: utf-8 -*-
"""Animation + animation-controller generation.

Written as code because the addon needs ~50 clips (gait, techniques, kaiju
behaviour, wield poses) that share structure; hand-editing that much JSON is how
bones get mistyped.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_weapons  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "packs", "kaiju8_RP")

# ---------------------------------------------------------------- molang
LIMB = "query.modified_distance_moved * 38.17"
SPD = "query.modified_move_speed"
T = "query.anim_time"


def swing(amp, phase=0, speed=1.0, scale=SPD):
    ph = f" + {phase}" if phase else ""
    return f"math.cos({LIMB} * {speed}{ph}) * {amp} * {scale}"


def bob(amp, hz=62, phase=0):
    ph = f" + {phase}" if phase else ""
    return f"math.cos({T} * {hz}{ph}) * {amp}"


def rot(x=0, y=0, z=0):
    return {"rotation": [x, y, z]}


def pos(x=0, y=0, z=0):
    return {"position": [x, y, z]}


def rp(r, p):
    return {"rotation": list(r), "position": list(p)}


def keys(**frames):
    """keys(t0=[0,0,0], t0_2=[...]) - underscores in the key become dots."""
    return {k.lstrip("t").replace("_", "."): v for k, v in frames.items()}


def clip(bones, length=None, loop=True, blend=None):
    d = {"loop": loop, "bones": bones}
    if length:
        d["animation_length"] = length
    if blend:
        d["blend_weight"] = blend
    return d


A = {}          # identifier -> clip


# ======================================================================
#  common
# ======================================================================
A["animation.kaiju8.look_at_target"] = clip({
    "head": rot("math.clamp(query.target_x_rotation, -42, 42)",
                "math.clamp(query.target_y_rotation, -68, 68)", 0),
    "neck": rot("math.clamp(query.target_x_rotation, -42, 42) * 0.28",
                "math.clamp(query.target_y_rotation, -68, 68) * 0.30", 0),
})

# ======================================================================
#  humanoid  (隊員 / 人型)
# ======================================================================
A["animation.kaiju8.humanoid.idle"] = clip({
    "body": {"rotation": [bob(0.7), 0, bob(0.5, 31)],
             "position": [0, bob(0.10, 62, 90), 0]},
    "chest": rot(bob(0.9, 62, 40), 0, 0),
    "neck": rot(bob(0.6, 62, 80), bob(1.6, 21), 0),
    "rightArm": rot(bob(2.0, 58), 0, f"-3 - {bob(1.2, 58)}"),
    "leftArm": rot(bob(2.0, 58, 180), 0, f"3 + {bob(1.2, 58, 180)}"),
    "rightForearm": rot(bob(1.6, 58, 40), 0, 0),
    "leftForearm": rot(bob(1.6, 58, 220), 0, 0),
})

A["animation.kaiju8.humanoid.walk"] = clip({
    "body": {"rotation": [2, 0, swing(1.6)], "position": [0, swing(0.30, 0, 2.0), 0]},
    "chest": rot(0, swing(3.2, 180), 0),
    "rightArm": rot(swing(42), 0, -3),
    "leftArm": rot(swing(42, 180), 0, 3),
    "rightForearm": rot(f"math.clamp({swing(26, 90)}, -6, 44)", 0, 0),
    "leftForearm": rot(f"math.clamp({swing(26, 270)}, -6, 44)", 0, 0),
    "rightLeg": rot(swing(46, 180), 0, 0),
    "leftLeg": rot(swing(46), 0, 0),
    "rightShin": rot(f"math.clamp({swing(40, 250)}, 0, 62)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(40, 70)}, 0, 62)", 0, 0),
    "rightFoot": rot(swing(16, 190), 0, 0),
    "leftFoot": rot(swing(16, 10), 0, 0),
})

A["animation.kaiju8.humanoid.run"] = clip({
    "body": {"rotation": [12, 0, swing(2.4)], "position": [0, swing(0.5, 0, 2.0), 0]},
    "chest": rot(4, swing(6.0, 180), 0),
    "neck": rot(-10, 0, 0),
    "rightArm": rot(swing(64), 0, -8),
    "leftArm": rot(swing(64, 180), 0, 8),
    "rightForearm": rot(f"-52 + math.clamp({swing(30, 90)}, -8, 40)", 0, 0),
    "leftForearm": rot(f"-52 + math.clamp({swing(30, 270)}, -8, 40)", 0, 0),
    "rightLeg": rot(swing(62, 180), 0, 0),
    "leftLeg": rot(swing(62), 0, 0),
    "rightShin": rot(f"math.clamp({swing(66, 250)}, 0, 92)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(66, 70)}, 0, 92)", 0, 0),
})

A["animation.kaiju8.humanoid.attack"] = clip({
    "rightArm": {"rotation": keys(t0=[0, 0, -3], t0_12=[-142, -20, -10],
                                  t0_28=[46, 14, 4], t0_5=[0, 0, -3])},
    "rightForearm": {"rotation": keys(t0=[0, 0, 0], t0_12=[-48, 0, 0],
                                      t0_28=[24, 0, 0], t0_5=[0, 0, 0])},
    "body": {"rotation": keys(t0=[0, 0, 0], t0_12=[-4, 22, 0],
                              t0_28=[6, -18, 0], t0_5=[0, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_12=[-8, -16, 0],
                              t0_28=[6, 12, 0], t0_5=[0, 0, 0])},
}, length=0.5, loop=False)

A["animation.kaiju8.humanoid.hurt"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_08=[-14, 0, 6], t0_3=[0, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_08=[16, 0, -8], t0_3=[0, 0, 0])},
}, length=0.3, loop=False)

A["animation.kaiju8.humanoid.death"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_35=[-24, 0, 0], t1_2=[0, 0, 88]),
             "position": keys(t0=[0, 0, 0], t1_2=[0, -7, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t1_2=[26, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, 0], t1_2=[-30, 0, -40])},
    "leftArm": {"rotation": keys(t0=[0, 0, 0], t1_2=[-30, 0, 40])},
}, length=1.2, loop="hold_on_last_frame")

# ---------------------------------------------------------------- poses
A["animation.kaiju8.pose.rifle"] = clip({
    "rightArm": rp([-74, -8, 0], [0, 0, -1]),
    "rightForearm": rot(-14, 22, 0),
    "leftArm": rp([-66, 30, 0], [-1, 0, -2.5]),
    "leftForearm": rot(-22, -30, 0),
    "chest": rot(0, -12, 0),
})
A["animation.kaiju8.pose.cannon"] = clip({
    "rightArm": rp([-70, -10, 0], [0, 0, -1]),
    "rightForearm": rot(-18, 26, 0),
    "leftArm": rp([-58, 34, 0], [-1.5, -0.5, -3.5]),
    "leftForearm": rot(-26, -34, 0),
    "chest": rot(-2, -18, 0),
    "head": rot(0, -14, 0),
})
A["animation.kaiju8.pose.twin"] = clip({
    "rightArm": rot(-22, 0, -16),
    "rightForearm": rot(-36, 0, -10),
    "leftArm": rot(-14, 0, 22),
    "leftForearm": rot(-52, 0, 14),
    "chest": rot(0, 14, 0),
})
A["animation.kaiju8.pose.axe"] = clip({
    "rightArm": rp([-124, -10, 0], [0, 0, 0]),
    "rightForearm": rot(-30, 0, 0),
    "leftArm": rp([-104, 26, 0], [-1, 0, -1.5]),
    "leftForearm": rot(-34, -18, 0),
    "chest": rot(-4, -8, 0),
})
A["animation.kaiju8.pose.gunblade"] = clip({
    "rightArm": rp([-96, -8, 0], [0, 0, 0]),
    "rightForearm": rot(-26, 0, 0),
    "leftArm": rp([-84, 24, 0], [-1, 0, -2]),
    "leftForearm": rot(-30, -16, 0),
    "chest": rot(-2, -10, 0),
})
A["animation.kaiju8.pose.knife"] = clip({
    "rightArm": rot(-24, 0, -6),
    "rightForearm": rot(-56, 0, 0),
    "leftArm": rot(-10, 0, 10),
})
A["animation.kaiju8.pose.blade"] = clip({
    "rightArm": rot(-30, 0, -8),
    "rightForearm": rot(-42, 0, 0),
    "leftArm": rot(-8, 0, 10),
})

# ======================================================================
#  技  (techniques)
# ======================================================================
A["animation.kaiju8.tech.slash"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_1=[-6, 46, 0], t0_26=[8, -40, 0],
                              t0_6=[0, 0, 0])},
    "chest": {"rotation": keys(t0=[0, 0, 0], t0_1=[0, 20, 0], t0_26=[0, -22, 0],
                               t0_6=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[-30, 0, -8], t0_1=[-96, -46, -30],
                                  t0_26=[-8, 40, 22], t0_6=[-30, 0, -8])},
    "rightForearm": {"rotation": keys(t0=[-42, 0, 0], t0_1=[-72, 0, 0],
                                      t0_26=[-6, 0, 0], t0_6=[-42, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_1=[0, -26, 0], t0_26=[0, 22, 0],
                              t0_6=[0, 0, 0])},
    "rightLeg": {"rotation": keys(t0=[0, 0, 0], t0_26=[-24, 0, 0], t0_6=[0, 0, 0])},
}, length=0.6, loop=False)

A["animation.kaiju8.tech.iai"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_14=[10, 58, 0], t0_3=[-4, -52, 0],
                              t0_7=[0, 0, 0]),
             "position": keys(t0=[0, 0, 0], t0_14=[0, -1.6, 0], t0_3=[0, 0, -2.5],
                              t0_7=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[-20, 0, -6], t0_14=[-40, -70, -18],
                                  t0_3=[-16, 62, 30], t0_7=[-20, 0, -6])},
    "rightForearm": {"rotation": keys(t0=[-30, 0, 0], t0_14=[-92, 0, 0],
                                      t0_3=[-4, 0, 0], t0_7=[-30, 0, 0])},
    "leftArm": {"rotation": keys(t0=[0, 0, 6], t0_14=[-24, 40, 30], t0_7=[0, 0, 6])},
    "rightLeg": {"rotation": keys(t0=[0, 0, 0], t0_14=[26, 0, 0], t0_3=[-38, 0, 0],
                                  t0_7=[0, 0, 0])},
    "leftLeg": {"rotation": keys(t0=[0, 0, 0], t0_14=[-16, 0, 0], t0_3=[30, 0, 0],
                                 t0_7=[0, 0, 0])},
}, length=0.7, loop=False)

A["animation.kaiju8.tech.twin_slash"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_08=[0, 40, 0], t0_2=[0, -42, 0],
                              t0_34=[0, 34, 0], t0_5=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[-22, 0, -16], t0_08=[-82, -40, -34],
                                  t0_2=[-10, 44, 16], t0_34=[-70, -30, -28],
                                  t0_5=[-22, 0, -16])},
    "leftArm": {"rotation": keys(t0=[-14, 0, 22], t0_08=[-16, 36, 38],
                                 t0_2=[-78, -34, 24], t0_34=[-12, 40, 40],
                                 t0_5=[-14, 0, 22])},
    "rightForearm": {"rotation": keys(t0=[-36, 0, -10], t0_2=[-6, 0, 0],
                                      t0_5=[-36, 0, -10])},
    "leftForearm": {"rotation": keys(t0=[-52, 0, 14], t0_2=[-8, 0, 0],
                                     t0_5=[-52, 0, 14])},
}, length=0.5, loop=False)

A["animation.kaiju8.tech.storm"] = clip({
    "body": {"rotation": [0, f"math.cos({T} * 1400) * 34", 0]},
    "rightArm": {"rotation": [f"-50 + math.cos({T} * 1400) * 46",
                              f"math.cos({T} * 1400 + 90) * 40", -20]},
    "leftArm": {"rotation": [f"-50 + math.cos({T} * 1400 + 180) * 46",
                             f"math.cos({T} * 1400 + 270) * 40", 20]},
    "rightForearm": rot(-30, 0, 0),
    "leftForearm": rot(-30, 0, 0),
    "head": {"rotation": [0, f"math.cos({T} * 1400) * 16", 0]},
}, length=1.0, loop=False)

A["animation.kaiju8.tech.axe_smash"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_2=[-30, 0, 0], t0_42=[38, 0, 0],
                              t0_9=[0, 0, 0]),
             "position": keys(t0=[0, 0, 0], t0_2=[0, 1.5, 0], t0_42=[0, -2.4, 0],
                              t0_9=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[-124, -10, 0], t0_2=[-172, -6, 0],
                                  t0_42=[-46, -4, 0], t0_9=[-124, -10, 0])},
    "leftArm": {"rotation": keys(t0=[-104, 26, 0], t0_2=[-160, 14, 0],
                                 t0_42=[-40, 10, 0], t0_9=[-104, 26, 0])},
    "rightForearm": {"rotation": keys(t0=[-30, 0, 0], t0_2=[-58, 0, 0],
                                      t0_42=[-4, 0, 0], t0_9=[-30, 0, 0])},
    "rightLeg": {"rotation": keys(t0=[0, 0, 0], t0_42=[-30, 0, 0], t0_9=[0, 0, 0])},
    "leftLeg": {"rotation": keys(t0=[0, 0, 0], t0_42=[22, 0, 0], t0_9=[0, 0, 0])},
}, length=0.9, loop=False)

A["animation.kaiju8.tech.axe_sweep"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_14=[0, 74, 0], t0_38=[0, -84, 0],
                              t0_8=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[-124, -10, 0], t0_14=[-92, -60, -40],
                                  t0_38=[-72, 50, -30], t0_8=[-124, -10, 0])},
    "leftArm": {"rotation": keys(t0=[-104, 26, 0], t0_14=[-70, -20, 20],
                                 t0_38=[-60, 60, 30], t0_8=[-104, 26, 0])},
    "leftLeg": {"rotation": keys(t0=[0, 0, 0], t0_38=[-18, 0, 0], t0_8=[0, 0, 0])},
}, length=0.8, loop=False)

A["animation.kaiju8.tech.snipe"] = clip({
    "chest": {"rotation": keys(t0=[-2, -18, 0], t0_08=[-8, -18, 0], t0_4=[-2, -18, 0])},
    "rightArm": {"rotation": keys(t0=[-70, -10, 0], t0_08=[-58, -10, 0],
                                  t0_4=[-70, -10, 0])},
    "leftArm": {"rotation": keys(t0=[-58, 34, 0], t0_08=[-48, 34, 0],
                                 t0_4=[-58, 34, 0])},
    "body": {"position": keys(t0=[0, 0, 0], t0_08=[0, 0, 1.6], t0_4=[0, 0, 0])},
}, length=0.4, loop=False)

A["animation.kaiju8.tech.suppress"] = clip({
    "chest": rot(-4, -18, f"math.cos({T} * 900) * 1.6"),
    "rightArm": rot(f"-70 + math.cos({T} * 900) * 6", -10, 0),
    "leftArm": rot(f"-58 + math.cos({T} * 900) * 5", 34, 0),
    "body": {"position": [0, 0, f"0.6 + math.cos({T} * 900) * 0.6"]},
}, length=1.2, loop=False)

A["animation.kaiju8.tech.punch"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_14=[-6, 52, 0], t0_3=[10, -46, 0],
                              t0_7=[0, 0, 0]),
             "position": keys(t0=[0, 0, 0], t0_3=[0, 0, -3.2], t0_7=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, -6], t0_14=[26, -34, -22],
                                  t0_3=[-96, 12, -6], t0_7=[0, 0, -6])},
    "rightForearm": {"rotation": keys(t0=[0, 0, 0], t0_14=[-70, 0, 0],
                                      t0_3=[-6, 0, 0], t0_7=[0, 0, 0])},
    "leftArm": {"rotation": keys(t0=[0, 0, 6], t0_14=[-52, 20, 26],
                                 t0_3=[24, -8, 14], t0_7=[0, 0, 6])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_14=[-10, -22, 0], t0_3=[8, 16, 0],
                              t0_7=[0, 0, 0])},
    "jaw": {"rotation": keys(t0=[0, 0, 0], t0_3=[26, 0, 0], t0_7=[0, 0, 0])},
}, length=0.7, loop=False)

A["animation.kaiju8.tech.leap"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_16=[-34, 0, 0], t0_4=[16, 0, 0],
                              t0_9=[0, 0, 0])},
    "rightLeg": {"rotation": keys(t0=[0, 0, 0], t0_16=[62, 0, 0], t0_4=[-30, 0, 0],
                                  t0_9=[0, 0, 0])},
    "leftLeg": {"rotation": keys(t0=[0, 0, 0], t0_16=[62, 0, 0], t0_4=[-30, 0, 0],
                                 t0_9=[0, 0, 0])},
    "rightShin": {"rotation": keys(t0=[0, 0, 0], t0_16=[-72, 0, 0], t0_4=[10, 0, 0],
                                   t0_9=[0, 0, 0])},
    "leftShin": {"rotation": keys(t0=[0, 0, 0], t0_16=[-72, 0, 0], t0_4=[10, 0, 0],
                                  t0_9=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, -3], t0_16=[52, 0, -20],
                                  t0_4=[-140, 0, -30], t0_9=[0, 0, -3])},
    "leftArm": {"rotation": keys(t0=[0, 0, 3], t0_16=[52, 0, 20],
                                 t0_4=[-140, 0, 30], t0_9=[0, 0, 3])},
}, length=0.9, loop=False)

# ======================================================================
#  怪獣  (kaiju)
# ======================================================================
A["animation.kaiju8.kaiju.idle"] = clip({
    "body": {"rotation": [bob(1.4, 42), 0, bob(0.8, 27)],
             "position": [0, bob(0.34, 42, 90), 0]},
    "chest": rot(bob(1.6, 42, 40), 0, 0),
    "neck": rot(bob(1.2, 42, 90), bob(2.6, 19), 0),
    "jaw": rot(f"3 + {bob(3.0, 42)}", 0, 0),
    "rightArm": rot(bob(2.6, 40), 0, f"-7 - {bob(2.0, 40)}"),
    "leftArm": rot(bob(2.6, 40, 180), 0, f"7 + {bob(2.0, 40, 180)}"),
    "rightForearm": rot(f"-12 + {bob(3.0, 40, 40)}", 0, 0),
    "leftForearm": rot(f"-12 + {bob(3.0, 40, 220)}", 0, 0),
})

A["animation.kaiju8.kaiju.walk"] = clip({
    "body": {"rotation": [f"4 + {swing(2.0, 0, 0.68)}", 0, swing(2.6, 0, 0.68)],
             "position": [0, swing(0.9, 0, 1.36), 0]},
    "chest": rot(0, swing(4.0, 180, 0.68), 0),
    "rightArm": rot(swing(30, 0, 0.68), 0, -7),
    "leftArm": rot(swing(30, 180, 0.68), 0, 7),
    "rightForearm": rot(f"-14 + math.clamp({swing(22, 90, 0.68)}, -8, 34)", 0, 0),
    "leftForearm": rot(f"-14 + math.clamp({swing(22, 270, 0.68)}, -8, 34)", 0, 0),
    "rightLeg": rot(swing(40, 180, 0.68), 0, 0),
    "leftLeg": rot(swing(40, 0, 0.68), 0, 0),
    "rightShin": rot(f"math.clamp({swing(44, 250, 0.68)}, 0, 70)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(44, 70, 0.68)}, 0, 70)", 0, 0),
    "rightFoot": rot(swing(18, 190, 0.68), 0, 0),
    "leftFoot": rot(swing(18, 10, 0.68), 0, 0),
})

A["animation.kaiju8.kaiju.attack"] = clip({
    "body": {"rotation": keys(t0=[4, 0, 0], t0_2=[-8, 34, 0], t0_44=[18, -30, 0],
                              t0_8=[4, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, -7], t0_2=[-156, -30, -26],
                                  t0_44=[62, 24, 8], t0_8=[0, 0, -7])},
    "rightForearm": {"rotation": keys(t0=[-14, 0, 0], t0_2=[-58, 0, 0],
                                      t0_44=[-4, 0, 0], t0_8=[-14, 0, 0])},
    "leftArm": {"rotation": keys(t0=[0, 0, 7], t0_2=[-46, 14, 22], t0_8=[0, 0, 7])},
    "jaw": {"rotation": keys(t0=[3, 0, 0], t0_2=[38, 0, 0], t0_5=[10, 0, 0],
                             t0_8=[3, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_2=[-18, -22, 0], t0_44=[14, 16, 0],
                              t0_8=[0, 0, 0])},
}, length=0.8, loop=False)

A["animation.kaiju8.kaiju.roar"] = clip({
    "head": {"rotation": keys(t0=[0, 0, 0], t0_35=[-38, 0, 0], t1_5=[-32, 0, 0],
                              t2_0=[0, 0, 0])},
    "neck": {"rotation": keys(t0=[0, 0, 0], t0_35=[-16, 0, 0], t2_0=[0, 0, 0])},
    "jaw": {"rotation": keys(t0=[0, 0, 0], t0_35=[52, 0, 0], t1_5=[46, 0, 0],
                             t2_0=[0, 0, 0])},
    "body": {"rotation": keys(t0=[0, 0, 0], t0_35=[-12, 0, 0], t1_5=[-9, 0, 0],
                              t2_0=[0, 0, 0]),
             "position": keys(t0=[0, 0, 0], t0_4=[0, 1.4, 0], t1_5=[0, 0.9, 0],
                              t2_0=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, -7], t0_4=[-46, 0, -52],
                                  t1_5=[-40, 0, -46], t2_0=[0, 0, -7])},
    "leftArm": {"rotation": keys(t0=[0, 0, 7], t0_4=[-46, 0, 52],
                                 t1_5=[-40, 0, 46], t2_0=[0, 0, 7])},
    "rightForearm": {"rotation": keys(t0=[-14, 0, 0], t0_4=[-58, 0, 0], t2_0=[-14, 0, 0])},
    "leftForearm": {"rotation": keys(t0=[-14, 0, 0], t0_4=[-58, 0, 0], t2_0=[-14, 0, 0])},
}, length=2.0, loop=False)

A["animation.kaiju8.kaiju.hurt"] = clip({
    "body": {"rotation": keys(t0=[4, 0, 0], t0_1=[-12, 0, 8], t0_35=[4, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_1=[18, 0, -10], t0_35=[0, 0, 0])},
    "jaw": {"rotation": keys(t0=[3, 0, 0], t0_1=[24, 0, 0], t0_35=[3, 0, 0])},
}, length=0.35, loop=False)

A["animation.kaiju8.kaiju.death"] = clip({
    "body": {"rotation": keys(t0=[4, 0, 0], t0_5=[-26, 0, 0], t2_2=[6, 0, 92]),
             "position": keys(t0=[0, 0, 0], t2_2=[0, -12, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_5=[-32, 0, 0], t2_2=[28, 0, 0])},
    "jaw": {"rotation": keys(t0=[0, 0, 0], t0_5=[44, 0, 0], t2_2=[18, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, -7], t2_2=[-24, 0, -54])},
    "leftArm": {"rotation": keys(t0=[0, 0, 7], t2_2=[-24, 0, 54])},
}, length=2.2, loop="hold_on_last_frame")

# ---------------------------------------------------------------- add-ons
def chain(prefix, count, amp, hz, step, axis="y"):
    out = {}
    for i in range(count):
        v = bob(amp * (0.6 + 0.4 * i / max(1, count - 1)), hz, -step * i)
        out[f"{prefix}{i}"] = rot(0, v, 0) if axis == "y" else rot(v, 0, 0)
    return out


A["animation.kaiju8.tail"] = clip({
    **chain("tail", 8, 8.0, 54, 34),
})
A["animation.kaiju8.tendrils"] = clip({
    **{f"tendril{i}{j}": rot(bob(5.0, 48, -26 * (i + j * 2)),
                             bob(6.0, 39, -22 * (i + j * 2)), 0)
       for i in range(6) for j in range(3)},
})
A["animation.kaiju8.hair_sway"] = clip({
    **{f"tail{s}{i}": rot(bob(4.5, 44, -30 * i), bob(5.5, 33, -26 * i), 0)
       for s in ("R", "L") for i in range(3)},
    "cape": rot(f"4 + {bob(3.0, 36)}", 0, 0),
})
A["animation.kaiju8.wings.idle"] = clip({
    "rightWing": rot(0, -34, f"-8 - {bob(6, 52)}"),
    "leftWing": rot(0, 34, f"8 + {bob(6, 52)}"),
    "rightWingFore": rot(0, -46, 0),
    "leftWingFore": rot(0, 46, 0),
})
A["animation.kaiju8.wings.flap"] = clip({
    "rightWing": rot(0, -20, f"-14 - math.cos({T} * 260) * 40"),
    "leftWing": rot(0, 20, f"14 + math.cos({T} * 260) * 40"),
    "rightWingFore": rot(0, f"-24 - math.cos({T} * 260 - 50) * 22", 0),
    "leftWingFore": rot(0, f"24 + math.cos({T} * 260 - 50) * 22", 0),
    "rightWingPanel": rot(0, f"math.cos({T} * 260 - 90) * 10", 0),
    "leftWingPanel": rot(0, f"-math.cos({T} * 260 - 90) * 10", 0),
})
A["animation.kaiju8.horns_idle"] = clip({
    "horn_r0": rot(bob(1.6, 38), 0, 0),
    "horn_l0": rot(bob(1.6, 38, 180), 0, 0),
})

# ======================================================================
#  余獣 (hexapod)
# ======================================================================
def leg_swing(side, row, amp=38):
    phase = 180 * ((row + (0 if side == "r" else 1)) % 2)
    return rot(swing(amp, phase, 0.9), 0, -18 if side == "r" else 18)


A["animation.kaiju8.beast.idle"] = clip({
    "body": {"position": [0, bob(0.4, 56), 0], "rotation": [bob(1.2, 56, 40), 0, 0]},
    "neck": rot(bob(2.0, 56, 90), bob(2.4, 27), 0),
    "head": rot(bob(1.6, 56, 120), bob(3.0, 23), 0),
    "jaw": rot(f"4 + {bob(4, 120)}", 0, 0),
    "mandible_r": rot(0, f"-10 - {bob(9, 130)}", 0),
    "mandible_l": rot(0, f"10 + {bob(9, 130)}", 0),
    **chain("tail", 4, 7.0, 46, 40),
})
A["animation.kaiju8.beast.walk"] = clip({
    "body": {"rotation": [0, swing(4.0, 0, 0.45), 0],
             "position": [0, swing(0.6, 0, 1.8), 0]},
    **{f"leg_{s}{r}": leg_swing(s, r) for s in ("r", "l") for r in range(3)},
    **{f"leg_{s}{r}_lower": rot(
        f"math.clamp({swing(30, 180 * ((r + (0 if s == 'r' else 1)) % 2) + 90, 0.9)}, -4, 48)",
        0, 34 if s == "l" else -34) for s in ("r", "l") for r in range(3)},
    **chain("tail", 4, 5.0, 46, 40),
})
A["animation.kaiju8.beast.attack"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_16=[-26, 0, 0], t0_34=[18, 0, 0],
                              t0_55=[0, 0, 0]),
             "position": keys(t0=[0, 0, 0], t0_34=[0, 0, -3], t0_55=[0, 0, 0])},
    "neck": {"rotation": keys(t0=[0, 0, 0], t0_16=[-24, 0, 0], t0_34=[26, 0, 0],
                              t0_55=[0, 0, 0])},
    "jaw": {"rotation": keys(t0=[0, 0, 0], t0_16=[42, 0, 0], t0_34=[4, 0, 0],
                             t0_55=[0, 0, 0])},
    "mandible_r": {"rotation": keys(t0=[0, 0, 0], t0_16=[0, -40, 0], t0_34=[0, 6, 0],
                                    t0_55=[0, 0, 0])},
    "mandible_l": {"rotation": keys(t0=[0, 0, 0], t0_16=[0, 40, 0], t0_34=[0, -6, 0],
                                    t0_55=[0, 0, 0])},
}, length=0.55, loop=False)
A["animation.kaiju8.beast.death"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t1_2=[0, 0, 98]),
             "position": keys(t0=[0, 0, 0], t1_2=[0, -4, 0])},
    **{f"leg_{s}{r}": {"rotation": keys(t0=[0, 0, 0], t1_2=[0, 0, -50 if s == "r" else 50])}
       for s in ("r", "l") for r in range(3)},
}, length=1.2, loop="hold_on_last_frame")
A["animation.kaiju8.beast.hurt"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_08=[0, 0, 14], t0_3=[0, 0, 0])},
}, length=0.3, loop=False)

# ======================================================================
#  怪獣8号 attachable extras (played on top of the player's own animation)
# ======================================================================
A["animation.kaiju8.no8.form_idle"] = clip({
    "chest": rot(bob(1.8, 44), 0, 0),
    "neck": rot(bob(1.2, 44, 60), 0, 0),
    "jaw": rot(f"2 + {bob(2.6, 44)}", 0, 0),
    "horn_r0": rot(bob(1.4, 38), 0, 0),
    "horn_l0": rot(bob(1.4, 38, 180), 0, 0),
    **{f"{s}Finger{i}": rot(f"10 + {bob(4, 50, -40 * i)}", 0, 0)
       for s in ("right", "left") for i in range(3)},
})
A["animation.kaiju8.no8.crouch"] = clip({
    "chest": rot(18, 0, 0),
    "neck": rot(-10, 0, 0),
    **{f"{s}Finger{i}": rot(34, 0, 0) for s in ("right", "left") for i in range(3)},
})
A["animation.kaiju8.no8.air"] = clip({
    "chest": rot(-8, 0, 0),
    "jaw": rot(16, 0, 0),
    **{f"{s}Finger{i}": rot(-14, 0, 0) for s in ("right", "left") for i in range(3)},
})
A["animation.kaiju8.no8.charge"] = clip({
    "chest": rot(-14, 0, 0),
    "jaw": rot(30, 0, 0),
    "horn_r0": rot(-12, 0, 0),
    "horn_l0": rot(-12, 0, 0),
    **{f"{s}Finger{i}": rot(48, 0, 0) for s in ("right", "left") for i in range(3)},
})

# ---------------------------------------------------------------- wield
A.update(gen_weapons.wield_animations())


# ======================================================================
#  animation controllers
# ======================================================================
def state(animations=None, transitions=None, blend=None, sounds=None,
          particles=None):
    d = {}
    if animations:
        d["animations"] = animations
    if transitions:
        d["transitions"] = transitions
    if blend is not None:
        d["blend_transition"] = blend
    if particles:
        d["particle_effects"] = particles
    if sounds:
        d["sound_effects"] = sounds
    return d


CONTROLLERS = {
    # -------- humanoid ------------------------------------------------
    "controller.animation.kaiju8.humanoid.general": {
        "initial_state": "stand",
        "states": {
            "stand": state(["look", "idle"], [
                {"walk": "query.modified_move_speed > 0.02"},
                {"death": "query.health <= 0"},
            ], 0.2),
            "walk": state(["look", "idle", "walk"], [
                {"run": "query.modified_move_speed > 0.72"},
                {"stand": "query.modified_move_speed <= 0.02"},
                {"death": "query.health <= 0"},
            ], 0.15),
            "run": state(["look", "run"], [
                {"walk": "query.modified_move_speed <= 0.72"},
                {"death": "query.health <= 0"},
            ], 0.15),
            "death": state(["death"], [], 0.2),
        },
    },
    "controller.animation.kaiju8.humanoid.action": {
        "initial_state": "idle",
        "states": {
            "idle": state(None, [
                {"tech": "query.mark_variant >= 2 && query.health > 0"},
                {"attack": "query.is_delayed_attacking && query.health > 0"},
                {"hurt": "query.mark_variant == 4"},
            ]),
            "attack": state(["attack"], [
                {"idle": "query.all_animations_finished || query.health <= 0"},
            ], 0.06),
            "tech": state(["tech"], [
                {"idle": "query.mark_variant < 2 || query.health <= 0"},
            ], 0.10),
            "hurt": state(["hurt"], [
                {"idle": "query.all_animations_finished || query.mark_variant != 4"},
            ], 0.05),
        },
    },
    # -------- kaiju ---------------------------------------------------
    "controller.animation.kaiju8.kaiju.general": {
        "initial_state": "stand",
        "states": {
            "stand": state(["look", "idle", "extras"], [
                {"walk": "query.modified_move_speed > 0.02"},
                {"roar": "query.mark_variant == 1"},
                {"death": "query.health <= 0"},
            ], 0.25),
            "walk": state(["look", "idle", "walk", "extras"], [
                {"stand": "query.modified_move_speed <= 0.02"},
                {"roar": "query.mark_variant == 1"},
                {"death": "query.health <= 0"},
            ], 0.2),
            "roar": state(["roar", "extras"], [
                {"death": "query.health <= 0"},
                {"stand": "query.mark_variant != 1 || query.all_animations_finished"},
            ], 0.25),
            "death": state(["death"], [], 0.3),
        },
    },
    "controller.animation.kaiju8.kaiju.action": {
        "initial_state": "idle",
        "states": {
            "idle": state(None, [
                {"attack": "query.is_delayed_attacking && query.mark_variant != 1 "
                           "&& query.health > 0"},
                {"hurt": "query.mark_variant == 4"},
            ]),
            "attack": state(["attack"], [
                {"idle": "query.all_animations_finished || query.health <= 0"},
            ], 0.1),
            "hurt": state(["hurt"], [
                {"idle": "query.all_animations_finished || query.mark_variant != 4"},
            ], 0.06),
        },
    },
    # -------- 余獣 ----------------------------------------------------
    "controller.animation.kaiju8.beast.general": {
        "initial_state": "stand",
        "states": {
            "stand": state(["look", "idle"], [
                {"walk": "query.modified_move_speed > 0.02"},
                {"death": "query.health <= 0"},
            ], 0.2),
            "walk": state(["look", "idle", "walk"], [
                {"stand": "query.modified_move_speed <= 0.02"},
                {"death": "query.health <= 0"},
            ], 0.15),
            "death": state(["death"], [], 0.2),
        },
    },
    "controller.animation.kaiju8.beast.action": {
        "initial_state": "idle",
        "states": {
            "idle": state(None, [
                {"attack": "query.is_delayed_attacking && query.health > 0"},
                {"hurt": "query.mark_variant == 4"},
            ]),
            "attack": state(["attack"], [
                {"idle": "query.all_animations_finished || query.health <= 0"},
            ], 0.06),
            "hurt": state(["hurt"], [
                {"idle": "query.all_animations_finished || query.mark_variant != 4"},
            ], 0.05),
        },
    },
    # -------- wings ---------------------------------------------------
    "controller.animation.kaiju8.wings": {
        "initial_state": "ground",
        "states": {
            "ground": state(["wings_idle"], [{"fly": "!query.is_on_ground"}], 0.3),
            "fly": state(["wings_flap"], [{"ground": "query.is_on_ground"}], 0.3),
        },
    },
    # -------- 怪獣8号 attachable --------------------------------------
    "controller.animation.kaiju8.no8_form": {
        "initial_state": "stand",
        "states": {
            "stand": state(["form_idle"], [
                {"crouch": "query.is_sneaking"},
                {"air": "!query.is_on_ground"},
                {"charge": "query.is_using_item"},
            ], 0.18),
            "crouch": state(["form_idle", "crouch"], [
                {"charge": "query.is_using_item"},
                {"stand": "!query.is_sneaking"},
            ], 0.18),
            "air": state(["form_idle", "air"], [
                {"stand": "query.is_on_ground"},
            ], 0.2),
            "charge": state(["form_idle", "charge"], [
                {"stand": "!query.is_using_item"},
            ], 0.12),
        },
    },
}


def main() -> None:
    os.makedirs(os.path.join(RP, "animations"), exist_ok=True)
    os.makedirs(os.path.join(RP, "animation_controllers"), exist_ok=True)
    with open(os.path.join(RP, "animations", "kaiju8.animation.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"format_version": "1.8.0", "animations": A}, fh, indent=2,
                  ensure_ascii=False)
        fh.write("\n")
    with open(os.path.join(RP, "animation_controllers",
                           "kaiju8.animation_controllers.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"format_version": "1.10.0",
                   "animation_controllers": CONTROLLERS}, fh, indent=2,
                  ensure_ascii=False)
        fh.write("\n")
    print(f"animations: {len(A)} clips, {len(CONTROLLERS)} controllers")


if __name__ == "__main__":
    main()
