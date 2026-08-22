# -*- coding: utf-8 -*-
"""移動・待機・一人称のアニメーションと、すべてのコントローラ。

ここが担うのは「常に流れている動き」。技の見せ場は gen_anim_tech.py。
待機と歩きが良いと、技を撃っていない時間まで気持ちよくなる。
"""
from __future__ import annotations

import _path  # noqa: F401

import contract as K  # noqa: E402
from anim import (SPD, bob, bob2, clip, drift, hold, keys, merge, mirror,  # noqa: E402
                  pos, rot, rp, swing)
from common import animations_doc, controllers_doc, write_json  # noqa: E402

A: dict = {}


def put(group, name, body):
    ident = (f"animation.{K.NS}.{name}" if group == "common"
             else K.anim(group, name))
    A[ident] = body
    return ident


# ===========================================================================
#  共通
# ===========================================================================
put("common", "look_at_target", clip({
    "head": rot("math.clamp(query.target_x_rotation, -40, 40)",
                "math.clamp(query.target_y_rotation, -64, 64)", 0),
    "neck": rot("math.clamp(query.target_x_rotation, -40, 40) * 0.30",
                "math.clamp(query.target_y_rotation, -64, 64) * 0.32", 0),
}))

# ===========================================================================
#  人型 NPC
# ===========================================================================
put("humanoid", "idle", clip({
    "body": {"rotation": [bob(0.7), 0, bob(0.5, 31)],
             "position": [0, bob(0.10, 62, 90), 0]},
    "chest": rot(bob2(0.9, 62, 40), 0, 0),
    "neck": rot(bob(0.6, 62, 80), bob(1.6, 21), 0),
    "rightArm": rot(bob(2.0, 58), 0, f"-3 - {bob(1.2, 58)}"),
    "leftArm": rot(bob(2.0, 58, 180), 0, f"3 + {bob(1.2, 58, 180)}"),
    "rightForearm": rot(bob(1.6, 58, 40), 0, 0),
    "leftForearm": rot(bob(1.6, 58, 220), 0, 0),
}))

put("humanoid", "walk", clip({
    "body": {"rotation": [2, 0, swing(1.6)],
             "position": [0, swing(0.30, 0, 2.0), 0]},
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
}))

put("humanoid", "run", clip({
    "body": {"rotation": [12, 0, swing(2.4)],
             "position": [0, swing(0.5, 0, 2.0), 0]},
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
}))

put("humanoid", "air", clip({
    "body": rot(-6, 0, 0),
    "rightArm": rot(-38, 0, -22),
    "leftArm": rot(-38, 0, 22),
    "rightLeg": rot(16, 0, 0),
    "leftLeg": rot(-12, 0, 0),
    "rightShin": rot(28, 0, 0),
    "leftShin": rot(12, 0, 0),
}))

put("humanoid", "sneak", clip({
    "body": {"rotation": [24, 0, 0], "position": [0, -2.2, 2.0]},
    "chest": rot(-6, 0, 0),
    "neck": rot(-14, 0, 0),
    "rightArm": rot(-14, 0, -6),
    "leftArm": rot(-14, 0, 6),
    "rightLeg": rot(-8, 0, 0),
    "leftLeg": rot(-8, 0, 0),
}))

put("humanoid", "attack", clip({
    "rightArm": {"rotation": keys(t0=[0, 0, -3], t0_10=[-138, -22, -10],
                                  t0_26=[48, 16, 4], t0_5=[0, 0, -3])},
    "rightForearm": {"rotation": keys(t0=[0, 0, 0], t0_10=[-52, 0, 0],
                                      t0_26=[26, 0, 0], t0_5=[0, 0, 0])},
    "body": {"rotation": keys(t0=[0, 0, 0], t0_10=[-4, 24, 0],
                              t0_26=[6, -20, 0], t0_5=[0, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_10=[-8, -18, 0],
                              t0_26=[6, 14, 0], t0_5=[0, 0, 0])},
}, length=0.5, loop=False))

put("humanoid", "hurt", clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_08=[-15, 0, 7], t0_3=[0, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_08=[17, 0, -9], t0_3=[0, 0, 0])},
}, length=0.3, loop=False))

put("humanoid", "death", clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_35=[-26, 0, 0], t1_2=[0, 0, 88]),
             "position": keys(t0=[0, 0, 0], t1_2=[0, -7, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t1_2=[28, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, 0], t1_2=[-30, 0, -42])},
    "leftArm": {"rotation": keys(t0=[0, 0, 0], t1_2=[-30, 0, 42])},
}, length=1.2, loop="hold_on_last_frame"))

# ===========================================================================
#  マグニートー  —  常に少し浮いている男
# ===========================================================================
CAPE_IDLE = {f"cape{i}": rot(f"{4 + i * 3} + {drift(3.0 + i * 1.6, 15, i * 40)}",
                             drift(2.2 + i, 11, i * 55),
                             drift(1.6 + i * 0.8, 13, i * 70))
             for i in range(4)}

put("magneto", "idle", clip(merge({
    "body": {"rotation": [bob(0.5, 34), 0, bob(0.4, 27)],
             "position": [0, bob2(0.5, 34, 0), 0]},
    "chest": rot(bob(0.7, 34, 40), 0, 0),
    "neck": rot(bob(0.5, 34, 80), drift(1.4, 9), 0),
    "rightArm": rot(bob(1.4, 34), 0, f"-4 - {bob(1.0, 34)}"),
    "leftArm": rot(bob(1.4, 34, 180), 0, f"4 + {bob(1.0, 34, 180)}"),
    "rightHand": rot(bob(3.0, 46, 20), 0, 0),
    "leftHand": rot(bob(3.0, 46, 200), 0, 0),
}, CAPE_IDLE)))

put("magneto", "walk", clip(merge({
    "body": {"rotation": [1, 0, swing(1.0)],
             "position": [0, f"1.2 + {swing(0.24, 0, 2.0)}", 0]},
    "chest": rot(0, swing(2.2, 180), 0),
    "rightArm": rot(swing(26), 0, -5),
    "leftArm": rot(swing(26, 180), 0, 5),
    "rightLeg": rot(swing(30, 180), 0, 0),
    "leftLeg": rot(swing(30), 0, 0),
    "rightShin": rot(f"math.clamp({swing(26, 250)}, 0, 48)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(26, 70)}, 0, 48)", 0, 0),
}, {f"cape{i}": rot(f"{6 + i * 4} + {swing(5.0 + i * 2, i * 30)}",
                    swing(3.0, 180 + i * 40), 0) for i in range(4)})))

put("magneto", "run", clip(merge({
    "body": {"rotation": [8, 0, swing(1.6)],
             "position": [0, f"1.8 + {swing(0.4, 0, 2.0)}", 0]},
    "chest": rot(3, swing(4.0, 180), 0),
    "rightArm": rot(swing(44), 0, -8),
    "leftArm": rot(swing(44, 180), 0, 8),
    "rightLeg": rot(swing(48, 180), 0, 0),
    "leftLeg": rot(swing(48), 0, 0),
}, {f"cape{i}": rot(f"{16 + i * 8} + {swing(9.0 + i * 3, i * 26)}",
                    swing(5.0, 180 + i * 34), 0) for i in range(4)})))

put("magneto", "air", clip(merge({
    "body": rot(-8, 0, 0),
    "rightArm": rot(-30, 0, -26),
    "leftArm": rot(-30, 0, 26),
    "rightLeg": rot(12, 0, 0),
    "leftLeg": rot(-10, 0, 0),
}, {f"cape{i}": rot(f"{26 + i * 12} + {drift(5.0, 21, i * 50)}",
                    drift(4.0, 17, i * 60), 0) for i in range(4)})))

#: 浮遊。両腕をわずかに開き、足先が下を向く。マントは真下へ流れる。
put("magneto", "hover", clip(merge({
    "body": {"rotation": [f"-4 + {bob(1.6, 21)}", 0, bob(1.2, 17)],
             "position": [0, f"3.0 + {bob2(1.4, 21, 0)}", 0]},
    "chest": rot(bob(1.2, 21, 60), 0, 0),
    "rightArm": rot(f"-14 + {bob(2.4, 21)}", 0, -18),
    "leftArm": rot(f"-14 + {bob(2.4, 21, 180)}", 0, 18),
    "rightForearm": rot(-16, 0, 0),
    "leftForearm": rot(-16, 0, 0),
    "rightLeg": rot(f"6 + {bob(1.6, 19)}", 0, -2),
    "leftLeg": rot(f"6 + {bob(1.6, 19, 180)}", 0, 2),
    "rightFoot": rot(28, 0, 0),
    "leftFoot": rot(28, 0, 0),
}, {f"cape{i}": rot(f"{10 + i * 6} + {drift(4.0, 13, i * 45)}",
                    drift(3.4, 11, i * 60), drift(2.4, 9, i * 30))
    for i in range(4)})))

#: 上昇中。全身が上を向き、マントが下から煽られる。
put("magneto", "levitate", clip(merge({
    "body": {"rotation": [-18, 0, 0], "position": [0, 4.0, 0]},
    "rightArm": rot(-58, 0, -30),
    "leftArm": rot(-58, 0, 30),
    "rightLeg": rot(14, 0, 0),
    "leftLeg": rot(14, 0, 0),
    "rightFoot": rot(34, 0, 0),
    "leftFoot": rot(34, 0, 0),
}, {f"cape{i}": rot(f"{34 + i * 14} + {drift(7.0, 27, i * 40)}", 0, 0)
    for i in range(4)})))

#: 玉座に座る（鋼鉄の玉座に乗っている間）。
put("magneto", "enthrone", clip(merge({
    "body": {"rotation": [-2, 0, 0], "position": [0, -3.0, 0]},
    "chest": rot(-4, 0, 0),
    "rightArm": rot(-8, 0, -14),
    "leftArm": rot(-8, 0, 14),
    "rightForearm": rot(-46, 0, 0),
    "leftForearm": rot(-46, 0, 0),
    "rightLeg": rot(-72, 0, -4),
    "leftLeg": rot(-72, 0, 4),
    "rightShin": rot(74, 0, 0),
    "leftShin": rot(74, 0, 0),
}, {f"cape{i}": rot(f"{2 + i * 2} + {drift(2.0, 11, i * 50)}", 0, 0)
    for i in range(4)})))

put("magneto", "cape_idle", clip(CAPE_IDLE, blend=0.9))
put("magneto", "cape_move", clip(
    {f"cape{i}": rot(f"{10 + i * 6} + {swing(8.0 + i * 3, i * 30)}",
                     swing(4.0, 180 + i * 40), swing(2.0, i * 20))
     for i in range(4)}, blend=0.9))

# ===========================================================================
#  変身体（プレイヤーが着ている状態）
# ===========================================================================
#  プレイヤーの骨に乗るので、動かすのはバニラのボーン名だけ。
#  歩き・走りはプレイヤー本体のアニメが担当するので、ここでは
#  「上乗せする味付け」（マント・浮遊感・呼吸）に絞る。
FORM_CAPE = {f"cape{i}": rot(f"{5 + i * 4} + {drift(3.4 + i * 1.4, 14, i * 42)}",
                             drift(2.4 + i, 10, i * 58), 0) for i in range(4)}

put("form", "idle", clip(merge(FORM_CAPE, {
    "body": {"position": [0, bob2(0.35, 30, 0), 0]},
    "head": rot(bob(0.6, 30, 60), 0, 0),
}), blend=0.85))

put("form", "walk", clip(merge({
    f"cape{i}": rot(f"{8 + i * 5} + {swing(6.0 + i * 2, i * 28)}",
                    swing(3.0, 180 + i * 36), 0) for i in range(4)}, {
    "body": {"position": [0, swing(0.20, 0, 2.0), 0]},
}), blend=0.85))

put("form", "run", clip(merge({
    f"cape{i}": rot(f"{18 + i * 9} + {swing(10.0 + i * 3, i * 24)}",
                    swing(5.0, 180 + i * 32), 0) for i in range(4)}, {
    "body": {"rotation": [4, 0, 0]},
}), blend=0.85))

put("form", "sprint", clip(merge({
    f"cape{i}": rot(f"{28 + i * 12} + {swing(13.0 + i * 4, i * 20)}",
                    swing(6.0, 180 + i * 28), 0) for i in range(4)}, {
    "body": {"rotation": [8, 0, 0]},
}), blend=0.85))

put("form", "crouch", clip(merge({
    f"cape{i}": rot(f"{-4 - i * 3} + {drift(2.0, 12, i * 40)}", 0, 0)
    for i in range(4)}, {}), blend=0.85))

put("form", "air", clip(merge({
    f"cape{i}": rot(f"{30 + i * 13} + {drift(6.0, 23, i * 44)}",
                    drift(4.0, 19, i * 52), 0) for i in range(4)}, {}),
    blend=0.85))

put("form", "swim", clip(merge({
    f"cape{i}": rot(f"{40 + i * 10} + {drift(8.0, 9, i * 50)}",
                    drift(6.0, 7, i * 60), 0) for i in range(4)}, {}),
    blend=0.85))

# ===========================================================================
#  一人称（技アイテムの attachable）
# ===========================================================================
#  手の前に磁界リングが浮いていて、技ごとに違う挙動をする。
#  ここが一人称視点の「主役」なので、待機からして常に動いている。
put("fp", "idle", clip({
    "root": {"rotation": [f"{bob(1.6, 26)}", f"{bob(1.2, 21, 40)}", 0],
             "position": [0, bob2(0.30, 26, 0), 0]},
    "field": {"rotation": [0, 0, f"query.anim_time * 55"]},
    "core": {"scale": [f"1 + {bob(0.08, 46)}", f"1 + {bob(0.08, 46)}",
                       f"1 + {bob(0.08, 46)}"]},
    "shard0": rot(0, 0, "query.anim_time * 140"),
    "shard1": rot(0, 0, "120 + query.anim_time * 140"),
    "shard2": rot(0, 0, "240 + query.anim_time * 140"),
}))

#: 三人称で技アイテムを持っている時の構え（手元に磁力球が浮く）
put("fp", "third", clip({
    "root": {"rotation": [f"-8 + {bob(2.0, 24)}", 0, 0],
             "position": [0, bob(0.24, 24, 40), -1.0]},
    "field": {"rotation": [0, 0, "query.anim_time * 90"]},
    "shard0": rot(0, 0, "query.anim_time * 150"),
    "shard1": rot(0, 0, "120 + query.anim_time * 150"),
    "shard2": rot(0, 0, "240 + query.anim_time * 150"),
}))

FP = {
    # name       root rot / pos keys                       field spin
    "thrust": ("突き出す", [(0, [6, 0, 0], [0, 0, 0]),
                            (0.08, [24, -8, 0], [0, -1.0, 3.0]),
                            (0.20, [-34, 6, 0], [0, 1.6, -7.0]),
                            (0.42, [-8, 2, 0], [0, 0.4, -1.5]),
                            (0.62, [6, 0, 0], [0, 0, 0])], 420),
    "pull": ("引き寄せる", [(0, [-18, 0, 0], [0, 0, -3.0]),
                            (0.12, [-30, -6, 0], [0, 0.8, -5.0]),
                            (0.34, [22, 8, 0], [0, -0.6, 4.0]),
                            (0.60, [6, 0, 0], [0, 0, 0])], -380),
    "grip": ("握り込む", [(0, [4, 0, 0], [0, 0, 0]),
                          (0.10, [-16, -10, 8], [0, 0.6, -2.0]),
                          (0.30, [-24, -4, -6], [0, 0.2, -3.4]),
                          (0.58, [6, 0, 0], [0, 0, 0])], 260),
    "lance": ("槍を放つ", [(0, [8, 0, 0], [0, 0, 0]),
                           (0.10, [34, -14, 0], [0, -1.2, 4.0]),
                           (0.18, [-46, 8, 0], [0, 2.0, -9.0]),
                           (0.40, [-6, 2, 0], [0, 0.3, -1.2]),
                           (0.60, [6, 0, 0], [0, 0, 0])], 520),
    "storm": ("嵐を呼ぶ", [(0, [6, 0, 0], [0, 0, 0]),
                           (0.16, [-48, 0, 0], [0, 3.0, 1.0]),
                           (0.44, [-56, 0, 0], [0, 3.6, 0.0]),
                           (0.72, [-20, 0, 0], [0, 1.2, 0.0]),
                           (0.95, [6, 0, 0], [0, 0, 0])], 680),
    "guard": ("受け", [(0, [6, 0, 0], [0, 0, 0]),
                       (0.12, [-22, 26, 0], [-1.4, 0.8, -2.0]),
                       (0.40, [-16, 20, 0], [-1.0, 0.6, -1.4]),
                       (0.70, [6, 0, 0], [0, 0, 0])], 200),
    "crush": ("握り潰す", [(0, [4, 0, 0], [0, 0, 0]),
                           (0.12, [-30, -12, 0], [0, 1.2, -3.0]),
                           (0.28, [-38, -6, 0], [0, 1.6, -4.4]),
                           (0.40, [-10, 0, 0], [0, 0.2, -0.6]),
                           (0.66, [6, 0, 0], [0, 0, 0])], -300),
    "raise": ("掲げる", [(0, [6, 0, 0], [0, 0, 0]),
                         (0.14, [-62, 0, 0], [0, 3.4, 1.2]),
                         (0.46, [-70, 0, 0], [0, 4.0, 0.6]),
                         (0.80, [6, 0, 0], [0, 0, 0])], 340),
    "pulse": ("パルス", [(0, [6, 0, 0], [0, 0, 0]),
                         (0.10, [-14, 0, 0], [0, 0.6, -1.0]),
                         (0.18, [-4, 0, 0], [0, 0.2, -4.0]),
                         (0.46, [6, 0, 0], [0, 0, 0])], 900),
    "fly": ("飛行", [(0, [-14, 0, 0], [0, -0.6, -1.0]),
                     (0.50, [-18, 0, 0], [0, 0.2, -1.4]),
                     (1.00, [-14, 0, 0], [0, -0.6, -1.0])], 240),
    "focus": ("集中", [(0, [6, 0, 0], [0, 0, 0]),
                       (0.20, [-28, 14, 0], [-1.6, 1.4, 1.0]),
                       (0.60, [-30, 14, 0], [-1.6, 1.5, 1.0]),
                       (0.90, [6, 0, 0], [0, 0, 0])], 160),
}

for name, (_ja, frames, spin) in FP.items():
    length = frames[-1][0]
    rot_keys = {}
    pos_keys = {}
    for t, r, p in frames:
        tag = f"t{str(t).replace('.', '_')}"
        rot_keys[tag] = r
        pos_keys[tag] = p
    put("fp", name, clip({
        "root": {"rotation": keys(**rot_keys), "position": keys(**pos_keys)},
        "field": {"rotation": [0, 0, f"query.anim_time * {spin}"]},
        "core": {"scale": [f"1 + {bob(0.16, 90)}", f"1 + {bob(0.16, 90)}",
                           f"1 + {bob(0.16, 90)}"]},
        "shard0": rot(0, 0, f"query.anim_time * {spin * 1.6}"),
        "shard1": rot(0, 0, f"120 + query.anim_time * {spin * 1.6}"),
        "shard2": rot(0, 0, f"240 + query.anim_time * {spin * 1.6}"),
    }, length=length, loop=(name == "fly")))

# ===========================================================================
#  センチネル  —  重い。加速も減速も鈍い。
# ===========================================================================
put("sentinel", "idle", clip({
    "body": {"rotation": [bob(0.4, 18), 0, bob(0.3, 13)],
             "position": [0, bob(0.16, 18, 90), 0]},
    "head": rot(bob(0.5, 14, 40), drift(6.0, 7), 0),
    "rightArm": rot(bob(0.8, 18), 0, -4),
    "leftArm": rot(bob(0.8, 18, 180), 0, 4),
}))

put("sentinel", "walk", clip({
    "body": {"rotation": [3, 0, swing(2.6)],
             "position": [0, swing(0.6, 0, 2.0), 0]},
    "chest": rot(0, swing(2.0, 180), 0),
    "rightArm": rot(swing(26), 0, -5),
    "leftArm": rot(swing(26, 180), 0, 5),
    "rightLeg": rot(swing(34, 180), 0, 0),
    "leftLeg": rot(swing(34), 0, 0),
    "rightShin": rot(f"math.clamp({swing(30, 250)}, 0, 46)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(30, 70)}, 0, 46)", 0, 0),
    "rightFoot": rot(swing(12, 190), 0, 0),
    "leftFoot": rot(swing(12, 10), 0, 0),
}))

put("sentinel", "beam", clip({
    "rightArm": {"rotation": keys(t0=[0, 0, -4], t0_35=[-96, -12, -6],
                                  t1_1=[-98, -12, -6], t1_6=[0, 0, -4])},
    "rightForearm": {"rotation": keys(t0=[0, 0, 0], t0_35=[-12, 0, 0],
                                      t1_1=[-8, 0, 0], t1_6=[0, 0, 0])},
    "leftArm": {"rotation": keys(t0=[0, 0, 4], t0_45=[-92, 14, 6],
                                 t1_1=[-94, 14, 6], t1_6=[0, 0, 4])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_35=[-10, 0, 0], t1_6=[0, 0, 0])},
    "chest": {"rotation": keys(t0=[0, 0, 0], t0_35=[-6, 0, 0], t1_6=[0, 0, 0])},
}, length=1.6, loop=False))

put("sentinel", "stomp", clip({
    "body": {"position": keys(t0=[0, 0, 0], t0_30=[0, 6, 0], t0_50=[0, -3, 0],
                              t0_9=[0, 0, 0])},
    "rightLeg": {"rotation": keys(t0=[0, 0, 0], t0_30=[-52, 0, 0],
                                  t0_50=[16, 0, 0], t0_9=[0, 0, 0])},
    "rightShin": {"rotation": keys(t0=[0, 0, 0], t0_30=[64, 0, 0],
                                   t0_50=[0, 0, 0], t0_9=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, -4], t0_30=[-34, 0, -18],
                                  t0_50=[22, 0, -4], t0_9=[0, 0, -4])},
    "leftArm": {"rotation": keys(t0=[0, 0, 4], t0_30=[-34, 0, 18],
                                 t0_50=[22, 0, 4], t0_9=[0, 0, 4])},
}, length=0.9, loop=False))

put("sentinel", "scan", clip({
    "head": {"rotation": keys(t0=[0, 0, 0], t0_5=[0, -52, 0], t1_2=[0, 52, 0],
                              t1_8=[0, 0, 0])},
    "chest": {"rotation": keys(t0=[0, 0, 0], t0_5=[0, -14, 0], t1_2=[0, 14, 0],
                               t1_8=[0, 0, 0])},
}, length=1.8, loop=False))

put("sentinel", "hurt", clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_10=[-8, 0, 5], t0_36=[0, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_10=[10, 0, -6], t0_36=[0, 0, 0])},
}, length=0.36, loop=False))

put("sentinel", "death", clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_5=[-18, 0, 6], t1_1=[10, 0, 0],
                              t2_2=[0, 0, 84]),
             "position": keys(t0=[0, 0, 0], t2_2=[0, -12, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_5=[-24, 0, 0], t2_2=[36, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, 0], t1_1=[-52, 0, -30],
                                  t2_2=[-18, 0, -46])},
    "leftArm": {"rotation": keys(t0=[0, 0, 0], t1_1=[-52, 0, 30],
                                 t2_2=[-18, 0, 46])},
    "rightLeg": {"rotation": keys(t0=[0, 0, 0], t2_2=[-26, 0, 0])},
    "leftLeg": {"rotation": keys(t0=[0, 0, 0], t2_2=[-14, 0, 0])},
}, length=2.2, loop="hold_on_last_frame"))

# ===========================================================================
#  小物
# ===========================================================================
put("prop", "spin", clip({
    "body": rot("query.anim_time * 210", "query.anim_time * 340", 0),
}))
put("prop", "orbit", clip({
    "body": {"rotation": [0, "query.anim_time * 260", 0],
             "position": [0, bob(1.4, 42), 0]},
}))
put("prop", "pulse", clip({
    "core": {"scale": [f"1 + {bob(0.22, 78)}", f"1 + {bob(0.22, 78)}",
                       f"1 + {bob(0.22, 78)}"]},
    "ring": rot(0, "query.anim_time * 190", 0),
}))
put("prop", "drift", clip({
    "body": {"rotation": [drift(6.0, 11), "query.anim_time * 40",
                          drift(5.0, 13, 50)],
             "position": [drift(0.6, 9), drift(1.0, 7, 30), drift(0.6, 8, 60)]},
}))

# ===========================================================================
#  コントローラ
# ===========================================================================
C: dict = {}


def controller(name, initial, states):
    C[K.ctrl(name)] = {"initial_state": initial, "states": states}


def state(anims, transitions=None, blend=0.2, on_entry=None):
    d = {"animations": list(anims), "blend_transition": blend}
    if transitions:
        d["transitions"] = [{k: v} for k, v in transitions]
    if on_entry:
        d["on_entry"] = list(on_entry)
    return d


# --- 人型 NPC ---------------------------------------------------------------
controller("humanoid.general", "stand", {
    "stand": state(["look", "idle"],
                   [("air", "!query.is_on_ground"),
                    ("walk", f"{SPD} > 0.02")]),
    "walk": state(["look", "walk"],
                  [("air", "!query.is_on_ground"),
                   ("run", f"{SPD} > 0.26"),
                   ("stand", f"{SPD} <= 0.02")]),
    "run": state(["look", "run"],
                 [("air", "!query.is_on_ground"),
                  ("walk", f"{SPD} <= 0.26")]),
    "air": state(["look", "air"],
                 [("stand", "query.is_on_ground")], blend=0.16),
})

controller("humanoid.action", "none", {
    "none": state([], [("hurt", "query.is_delayed_attacking || variable.hurt"),
                       ("attack", "query.mark_variant == 1"),
                       ("tech", "query.mark_variant == 2"),
                       ("death", "query.is_alive == 0")]),
    "attack": state(["attack"], [("none", "query.mark_variant != 1")],
                    blend=0.10),
    "tech": state(["tech"], [("none", "query.mark_variant != 2")], blend=0.12),
    "hurt": state(["hurt"], [("none", "query.mark_variant != 3")], blend=0.08),
    "death": state(["death"], [], blend=0.2),
})

# --- マグニートー ------------------------------------------------------------
controller("magneto.general", "stand", {
    "stand": state(["look", "idle", "cape"],
                   [("hover", "query.mark_variant == 5"),
                    ("air", "!query.is_on_ground"),
                    ("walk", f"{SPD} > 0.02")]),
    "walk": state(["look", "walk"],
                  [("hover", "query.mark_variant == 5"),
                   ("air", "!query.is_on_ground"),
                   ("run", f"{SPD} > 0.24"),
                   ("stand", f"{SPD} <= 0.02")]),
    "run": state(["look", "run"],
                 [("hover", "query.mark_variant == 5"),
                  ("air", "!query.is_on_ground"),
                  ("walk", f"{SPD} <= 0.24")]),
    "air": state(["look", "air"],
                 [("hover", "query.mark_variant == 5"),
                  ("stand", "query.is_on_ground")], blend=0.16),
    "hover": state(["look", "hover"],
                   [("stand", "query.mark_variant != 5")], blend=0.3),
})

controller("magneto.action", "none", {
    "none": state([], [("attack", "query.mark_variant == 1"),
                       ("tech", "query.mark_variant == 2"),
                       ("hurt", "query.mark_variant == 3"),
                       ("ult", "query.mark_variant == 4"),
                       ("death", "query.is_alive == 0")]),
    "attack": state(["attack"], [("none", "query.mark_variant != 1")],
                    blend=0.10),
    "tech": state(["tech"], [("none", "query.mark_variant != 2")], blend=0.12),
    "hurt": state(["hurt"], [("none", "query.mark_variant != 3")], blend=0.08),
    "ult": state(["ult"], [("none", "query.mark_variant != 4")], blend=0.25),
    "death": state(["death"], [], blend=0.2),
})

# --- センチネル --------------------------------------------------------------
controller("sentinel.general", "stand", {
    "stand": state(["look", "idle"], [("walk", f"{SPD} > 0.02")]),
    "walk": state(["look", "walk"], [("stand", f"{SPD} <= 0.02")]),
})

controller("sentinel.action", "none", {
    "none": state([], [("beam", "query.mark_variant == 2"),
                       ("stomp", "query.mark_variant == 1"),
                       ("scan", "query.mark_variant == 5"),
                       ("hurt", "query.mark_variant == 3"),
                       ("death", "query.is_alive == 0")]),
    "beam": state(["beam"], [("none", "query.mark_variant != 2")], blend=0.2),
    "stomp": state(["stomp"], [("none", "query.mark_variant != 1")], blend=0.14),
    "scan": state(["scan"], [("none", "query.mark_variant != 5")], blend=0.2),
    "hurt": state(["hurt"], [("none", "query.mark_variant != 3")], blend=0.08),
    "death": state(["death"], [], blend=0.2),
})

# --- 変身体（ポーズごとに 1 コントローラ）--------------------------------------
#  技を撃つ瞬間だけ、スクリプトが装備アイテムをポーズ違いに差し替える。
#  差し替わった瞬間にこちらのコントローラが読み込まれ、姿勢が変わる。
def form_controller(name, pose_anim=None):
    states = {
        "base": state(["idle"],
                      [("crouch", "query.is_sneaking"),
                       ("air", "!query.is_on_ground"),
                       ("sprint", "query.is_sprinting"),
                       ("walk", f"{SPD} > 0.02")]),
        "walk": state(["idle", "walk"],
                      [("crouch", "query.is_sneaking"),
                       ("air", "!query.is_on_ground"),
                       ("sprint", "query.is_sprinting"),
                       ("base", f"{SPD} <= 0.02")]),
        "sprint": state(["idle", "sprint"],
                        [("air", "!query.is_on_ground"),
                         ("walk", "!query.is_sprinting")]),
        "crouch": state(["idle", "crouch"],
                        [("base", "!query.is_sneaking")]),
        "air": state(["idle", "air"],
                     [("swim", "query.is_in_water"),
                      ("base", "query.is_on_ground")], blend=0.16),
        "swim": state(["idle", "swim"],
                      [("base", "query.is_on_ground")], blend=0.2),
    }
    if pose_anim:
        # 技の姿勢は全状態に重ねる。歩きながらでも技の形が崩れない。
        for st in states.values():
            st["animations"].append(pose_anim)
            st["blend_transition"] = 0.10
    controller(name, "base", states)


#  変身体は「技ごとに別アイテム」なので、コントローラも技ごとに要る。
for _c, _t, _g, _n in K.form_variants():
    form_controller(K.form_controller_name(_c, _t), "pose" if _t else None)


# --- 一人称 ------------------------------------------------------------------
controller("fp.tech", "idle", {
    "idle": state(["idle"], [("act", "query.is_using_item")], blend=0.14),
    "act": state(["idle", "act"], [("idle", "!query.is_using_item")],
                 blend=0.10),
})

# --- マント（NPC 用に単体で回す）-----------------------------------------------
controller("cape", "still", {
    "still": state(["cape_idle"], [("moving", f"{SPD} > 0.02")], blend=0.3),
    "moving": state(["cape_move"], [("still", f"{SPD} <= 0.02")], blend=0.3),
})

# --- 小物 --------------------------------------------------------------------
controller("prop.spin", "spin", {"spin": state(["spin"])})


# ===========================================================================
#  レンダーコントローラ
# ===========================================================================
RENDER = {
    K.render_ctrl("default"): {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": ["Texture.default"],
    },
    # ダメージ点滅つき
    K.render_ctrl("glow"): {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": ["Texture.default"],
        "overlay_color": {"r": 1.0, "g": 1.0, "b": 1.0,
                          "a": "math.clamp(variable.hurt_flash, 0.0, 0.6)"},
    },
    # ミスティークの擬態 — 明滅しながら色が乗る
    K.render_ctrl("phase"): {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": ["Texture.default"],
        "overlay_color": {
            "r": 0.30, "g": 0.66, "b": 1.0,
            "a": "math.clamp(math.sin(query.life_time * 260) * 0.35 + 0.1,"
                 " 0.0, 0.45) * query.mark_variant",
        },
    },
    # 障壁・磁界の棺のような「実体のない」もの
    K.render_ctrl("hologram"): {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": ["Texture.default"],
        "overlay_color": {
            "r": 0.70, "g": 0.48, "b": 1.0,
            "a": "0.22 + math.sin(query.life_time * 180) * 0.10",
        },
    },
}


def main() -> None:
    K.ensure_dirs()
    write_json(f"{K.ANIM_DIR}/marvel.loco.animation.json", animations_doc(A))
    write_json(f"{K.CTRL_DIR}/marvel.animation_controllers.json",
               controllers_doc(C))
    write_json(f"{K.RENDER_DIR}/marvel.render_controllers.json",
               {"format_version": "1.8.0", "render_controllers": RENDER})
    print(f"animations (loco): {len(A)} clips, {len(C)} controllers, "
          f"{len(RENDER)} render controllers")


if __name__ == "__main__":
    main()
