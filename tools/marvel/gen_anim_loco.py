# -*- coding: utf-8 -*-
"""移動・待機・一人称のアニメーションと、すべてのコントローラ。

ここが担うのは「常に流れている動き」。技の見せ場は gen_anim_tech.py。
待機と歩きが良いと、技を撃っていない時間まで気持ちよくなる。

作り方の三原則
--------------
1. **周期を揃えない。** 待機を一本の cos で作ると、二往復目で必ず飽きる。
   呼吸・重心・浮遊・微動を互いに整数比でない周期で重ねる（``anim.HZ``）。
2. **キャラごとに別の物理を与える。** 同じ humanoid.* を全員で共有すると、
   遠景では体格差しか残らない。センチネルは重く、マグニートーは浮く。
3. **一人称は手ではなく場を見せる。** 手の軌跡は視界の隅にしか映らない。
   磁界リング（field）の回転と鉄片（shard）の半径が一人称の主役。
"""
from __future__ import annotations

import _path  # noqa: F401

import contract as K  # noqa: E402
from anim import (SPD, cape6_drift, cape6_loop, cape_fan, clip,  # noqa: E402
                  gait, merge, rot, spin_track, swing, tag, thud, track,
                  waves)
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
    # 首は頭の 3 割だけ付いていく。全部付いていくと頭と胴が一枚板に見える。
    "neck": rot("math.clamp(query.target_x_rotation, -40, 40) * 0.30",
                "math.clamp(query.target_y_rotation, -64, 64) * 0.32", 0),
    "chest": rot(0, "math.clamp(query.target_y_rotation, -64, 64) * 0.14", 0),
}))

# ===========================================================================
#  人型 NPC  —  9 人のブラザーフッドと MRD が共有する土台
# ===========================================================================
#  共有なので「誰にでも当てはまる呼吸」に留める。個性は体格とテクスチャ、
#  そして各自の技クリップが担う。
put("humanoid", "idle", clip({
    "body": {"rotation": [waves((0.6, "breath"), (0.3, "sway", 40)),
                          waves((0.5, "sway")),
                          waves((0.5, "weight"), (0.2, "breath", 70))],
             "position": [waves((0.20, "weight", 90)),
                          waves((0.14, "breath", 180)), 0]},
    # 胸は呼吸の主動。腹（body）より一拍遅れて膨らむ。
    "chest": rot(waves((0.9, "breath", 34), (0.3, "float", 12)),
                 waves((0.6, "weight", 200)), 0),
    "neck": rot(waves((-0.5, "breath", 34), (0.4, "sway", 180)),
                waves((1.6, "sway", 25)), 0),
    "rightShoulder": rot(0, 0, waves((0.8, "breath", 60), base=-1.5)),
    "leftShoulder": rot(0, 0, waves((-0.8, "breath", 60), base=1.5)),
    "rightArm": rot(waves((1.6, "breath"), (0.5, "float", 30)), 0,
                    waves((-1.0, "breath"), base=-3)),
    "leftArm": rot(waves((1.6, "breath", 180), (0.5, "float", 210)), 0,
                   waves((1.0, "breath", 180), base=3)),
    "rightForearm": rot(waves((1.3, "breath", 40), (0.6, "weight", 90)), 0, 0),
    "leftForearm": rot(waves((1.3, "breath", 220), (0.6, "weight", 270)), 0, 0),
    # 指の無いリグなので、手首の微動で「生きている手」を作る。
    "rightHand": rot(waves((0.9, "tremor"), (1.2, "weight", 30)), 0, 0),
    "leftHand": rot(waves((0.9, "tremor", 140), (1.2, "weight", 210)), 0, 0),
}))

put("humanoid", "walk", clip({
    "body": {"rotation": [2, swing(1.2, 90), swing(1.6)],
             "position": [swing(0.22, 90), swing(0.30, 0, 2.0), 0]},
    "chest": rot(0, swing(3.2, 180), swing(1.2, 90)),
    "neck": rot(0, swing(2.0, 0), 0),
    "rightShoulder": rot(0, 0, swing(3.0, 180)),
    "leftShoulder": rot(0, 0, swing(3.0, 0)),
    "rightArm": rot(swing(42), 0, -3),
    "leftArm": rot(swing(42, 180), 0, 3),
    # 前腕は上腕を追い越す（しなり）。90° 遅らせるのがその位相差。
    "rightForearm": rot(f"math.clamp({swing(26, 90)}, -6, 44)", 0, 0),
    "leftForearm": rot(f"math.clamp({swing(26, 270)}, -6, 44)", 0, 0),
    "rightHand": rot(swing(12, 120), 0, 0),
    "leftHand": rot(swing(12, 300), 0, 0),
    "rightLeg": rot(swing(46, 180), 0, 0),
    "leftLeg": rot(swing(46), 0, 0),
    "rightShin": rot(f"math.clamp({swing(40, 250)}, 0, 62)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(40, 70)}, 0, 62)", 0, 0),
    "rightFoot": rot(swing(16, 190), 0, 0),
    "leftFoot": rot(swing(16, 10), 0, 0),
    "rightToe": rot(f"math.clamp({swing(18, 160)}, -4, 26)", 0, 0),
    "leftToe": rot(f"math.clamp({swing(18, 340)}, -4, 26)", 0, 0),
}))

put("humanoid", "run", clip({
    "body": {"rotation": [12, swing(2.6, 90), swing(2.4)],
             "position": [swing(0.30, 90), swing(0.5, 0, 2.0), 0]},
    "chest": rot(4, swing(6.0, 180), swing(2.0, 90)),
    "neck": rot(-10, swing(3.0, 0), 0),
    "rightShoulder": rot(0, 0, swing(5.0, 180)),
    "leftShoulder": rot(0, 0, swing(5.0, 0)),
    "rightArm": rot(swing(64), 0, -8),
    "leftArm": rot(swing(64, 180), 0, 8),
    "rightForearm": rot(f"-52 + math.clamp({swing(30, 90)}, -8, 40)", 0, 0),
    "leftForearm": rot(f"-52 + math.clamp({swing(30, 270)}, -8, 40)", 0, 0),
    "rightLeg": rot(swing(62, 180), 0, 0),
    "leftLeg": rot(swing(62), 0, 0),
    "rightShin": rot(f"math.clamp({swing(66, 250)}, 0, 92)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(66, 70)}, 0, 92)", 0, 0),
    "rightFoot": rot(swing(20, 190), 0, 0),
    "leftFoot": rot(swing(20, 10), 0, 0),
}))

put("humanoid", "air", clip({
    "body": rot(-6, 0, waves((1.4, "float"))),
    "chest": rot(-4, 0, 0),
    "neck": rot(6, 0, 0),
    "rightArm": rot(f"-38 + {waves((3.0, 'float'))}", 0, -22),
    "leftArm": rot(f"-38 + {waves((3.0, 'float', 180))}", 0, 22),
    "rightForearm": rot(-24, 0, 0),
    "leftForearm": rot(-24, 0, 0),
    "rightLeg": rot(16, 0, 0),
    "leftLeg": rot(-12, 0, 0),
    "rightShin": rot(28, 0, 0),
    "leftShin": rot(12, 0, 0),
    "rightToe": rot(14, 0, 0),
    "leftToe": rot(14, 0, 0),
}))

put("humanoid", "sneak", clip({
    "body": {"rotation": [24, 0, waves((0.5, "breath"))],
             "position": [0, -2.2, 2.0]},
    "chest": rot(-6, 0, 0),
    "neck": rot(-14, 0, 0),
    "rightShoulder": rot(0, 0, -3),
    "leftShoulder": rot(0, 0, 3),
    "rightArm": rot(f"-14 + {waves((1.0, 'breath'))}", 0, -6),
    "leftArm": rot(f"-14 + {waves((1.0, 'breath', 180))}", 0, 6),
    "rightForearm": rot(-30, 0, 0),
    "leftForearm": rot(-30, 0, 0),
    "rightLeg": rot(-8, 0, 0),
    "leftLeg": rot(-8, 0, 0),
    "rightShin": rot(18, 0, 0),
    "leftShin": rot(18, 0, 0),
}))

#: 殴る。撃発（0.10）だけ linear で止め、残りは曲線で繋ぐ。
put("humanoid", "attack", clip({
    "rightArm": {"rotation": track([(0, [0, 0, -3]),
                                    (0.10, [-138, -22, -10], "linear"),
                                    (0.26, [48, 16, 4]),
                                    (0.5, [0, 0, -3], "linear")])},
    "rightForearm": {"rotation": track([(0, [0, 0, 0]),
                                        (0.12, [-52, 0, 0], "linear"),
                                        (0.28, [26, 0, 0]),
                                        (0.5, [0, 0, 0], "linear")])},
    "rightHand": {"rotation": track([(0, [0, 0, 0]),
                                     (0.14, [-30, 0, 0], "linear"),
                                     (0.30, [22, 0, 0]),
                                     (0.5, [0, 0, 0], "linear")])},
    "rightShoulder": {"rotation": track([(0, [0, 0, 0]),
                                         (0.08, [0, 0, -7], "linear"),
                                         (0.5, [0, 0, 0], "linear")])},
    "body": {"rotation": track([(0, [0, 0, 0]), (0.10, [-4, 24, 0], "linear"),
                                (0.26, [6, -20, 0]),
                                (0.5, [0, 0, 0], "linear")])},
    "chest": {"rotation": track([(0, [0, 0, 0]), (0.13, [-2, 13, 0]),
                                 (0.29, [3, -11, 0]),
                                 (0.5, [0, 0, 0], "linear")])},
    # 首は逆へ。頭が置いていかれるほど、腕が速く見える。
    "neck": {"rotation": track([(0, [0, 0, 0]), (0.16, [0, -9, 0]),
                                (0.5, [0, 0, 0], "linear")])},
    "head": {"rotation": track([(0, [0, 0, 0]), (0.10, [-8, -18, 0]),
                                (0.26, [6, 14, 0]),
                                (0.5, [0, 0, 0], "linear")])},
}, length=0.5, loop=False))

put("humanoid", "hurt", clip({
    "body": {"rotation": track([(0, [0, 0, 0]), (0.08, [-15, 0, 7], "linear"),
                                (0.3, [0, 0, 0], "linear")])},
    "chest": {"rotation": track([(0, [0, 0, 0]), (0.11, [-8, 0, 4]),
                                 (0.3, [0, 0, 0], "linear")])},
    "head": {"rotation": track([(0, [0, 0, 0]), (0.10, [17, 0, -9], "linear"),
                                (0.3, [0, 0, 0], "linear")])},
}, length=0.3, loop=False))

put("humanoid", "death", clip({
    "body": {"rotation": track([(0, [0, 0, 0]), (0.35, [-26, 0, 0]),
                                (1.2, [0, 0, 88], "linear")]),
             "position": track([(0, [0, 0, 0]), (1.2, [0, -7, 0], "linear")])},
    "chest": {"rotation": track([(0, [0, 0, 0]), (0.45, [-14, 0, 0]),
                                 (1.2, [16, 0, 0], "linear")])},
    "head": {"rotation": track([(0, [0, 0, 0]), (1.2, [28, 0, 0], "linear")])},
    "rightArm": {"rotation": track([(0, [0, 0, 0]), (0.5, [-46, 0, -20]),
                                    (1.2, [-30, 0, -42], "linear")])},
    "leftArm": {"rotation": track([(0, [0, 0, 0]), (0.5, [-46, 0, 20]),
                                   (1.2, [-30, 0, 42], "linear")])},
}, length=1.2, loop="hold_on_last_frame"))

# ===========================================================================
#  マグニートー  —  常に少し浮いている男
# ===========================================================================
#  地に足がついた待機にしない。踵はいつも紙一枚ぶん浮いていて、
#  体重を支えているのは脚ではなく磁界である、と一目で判るようにする。

#: 待機のマント。段ごとに周期をずらして、6 段が一枚板として動かないようにする。
CAPE_REST = cape_fan(12)      # 累積 12°。垂れているが板ではない
CAPE_IDLE = cape6_drift(CAPE_REST, cape_fan(9))

put("magneto", "idle", clip(merge({
    # 三本の波（呼吸 4.3 秒 / 重心 7.1 秒 / 浮遊 11.3 秒）を重ねる。
    # 最小公倍数が実用上存在しないので、見ている限り同じ形に戻らない。
    "body": {"rotation": [waves((0.8, "breath"), (0.45, "float", 40)),
                          waves((0.9, "sway"), (0.3, "weight", 120)),
                          waves((0.7, "weight"), (0.35, "float", 90))],
             "position": [waves((0.30, "weight", 90), (0.12, "sway")),
                          waves((0.55, "float"), (0.22, "breath", 60),
                                base=0.9),
                          waves((0.20, "sway", 40))]},
    "chest": rot(waves((1.0, "breath", 34), (0.35, "float", 12)),
                 waves((0.7, "sway", 200)), 0),
    # 頭は胴の揺れを打ち消して水平を保つ。ここを揃えると人形に見える。
    "neck": rot(waves((-0.6, "breath", 34), (0.5, "sway", 180)),
                waves((1.5, "sway", 25), (0.6, "float", 90)), 0),
    "rightShoulder": rot(0, 0, waves((0.9, "breath", 60), base=-2.0)),
    "leftShoulder": rot(0, 0, waves((-0.9, "breath", 60), base=2.0)),
    "rightArm": rot(waves((1.2, "breath"), (0.6, "float", 25)), 0,
                    waves((-0.9, "breath"), base=-5)),
    "leftArm": rot(waves((1.2, "breath", 180), (0.6, "float", 205)), 0,
                   waves((0.9, "breath", 180), base=5)),
    "rightForearm": rot(waves((1.1, "weight", 40), (0.5, "breath", 90)), 0, 0),
    "leftForearm": rot(waves((1.1, "weight", 220), (0.5, "breath", 270)), 0, 0),
    # 指先の微動。1.15 秒周期の細かい震えが、磁力を掌に溜めている感を作る。
    "rightHand": rot(waves((1.4, "tremor"), (1.8, "weight", 30)),
                     waves((0.8, "tremor", 60)), 0),
    "leftHand": rot(waves((1.4, "tremor", 137), (1.8, "weight", 210)),
                    waves((-0.8, "tremor", 200)), 0),
    # 爪先が下を向く。接地していない足の形。
    "rightLeg": rot(waves((0.5, "float", 20), base=-1.5), 0, -1),
    "leftLeg": rot(waves((0.5, "float", 200), base=-1.5), 0, 1),
    "rightFoot": rot(waves((1.2, "float", 60), base=7), 0, 0),
    "leftFoot": rot(waves((1.2, "float", 240), base=7), 0, 0),
    "rightToe": rot(6, 0, 0),
    "leftToe": rot(6, 0, 0),
}, CAPE_IDLE)))

#: 歩きではなく滑走。脚は歩幅の半分の周期でゆっくり鋏を切るだけで、
#: 前へ進める力は磁界が出している。踵は一度も着かない。
put("magneto", "walk", clip(merge({
    "body": {"rotation": [waves((0.6, "float"), base=1),
                          swing(1.4, 90, 0.5),
                          swing(1.2, 0, 0.5)],
             "position": [swing(0.30, 90, 0.5),
                          waves((0.45, "float"), base=1.6), 0]},
    "chest": rot(0, swing(2.4, 180, 0.5), 0),
    "neck": rot(0, swing(1.6, 0, 0.5), 0),
    "rightArm": rot(swing(14, 0, 0.5), 0, -6),
    "leftArm": rot(swing(14, 180, 0.5), 0, 6),
    "rightForearm": rot(f"-8 + {swing(8, 90, 0.5)}", 0, 0),
    "leftForearm": rot(f"-8 + {swing(8, 270, 0.5)}", 0, 0),
    "rightHand": rot(waves((1.2, "tremor")), 0, 0),
    "leftHand": rot(waves((1.2, "tremor", 137)), 0, 0),
    "rightLeg": rot(swing(18, 180, 0.5), 0, -1),
    "leftLeg": rot(swing(18, 0, 0.5), 0, 1),
    "rightShin": rot(f"math.clamp({swing(12, 250, 0.5)}, 0, 22)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(12, 70, 0.5)}, 0, 22)", 0, 0),
    "rightFoot": rot(f"10 + {swing(5, 190, 0.5)}", 0, 0),
    "leftFoot": rot(f"10 + {swing(5, 10, 0.5)}", 0, 0),
}, cape6_loop(cape_fan(20), cape_fan(16), lag=26))))

#: 疾走ではなく低空飛行。前傾して脚を後ろへ流し、マントだけが荒れる。
put("magneto", "run", clip(merge({
    "body": {"rotation": [f"9 + {waves((0.8, 'float'))}",
                          swing(2.0, 90, 0.5), swing(1.8, 0, 0.5)],
             "position": [swing(0.4, 90, 0.5),
                          waves((0.6, "float"), base=2.6), 0]},
    "chest": rot(3, swing(3.4, 180, 0.5), 0),
    "neck": rot(-7, swing(2.0, 0, 0.5), 0),
    "rightShoulder": rot(0, 0, -4),
    "leftShoulder": rot(0, 0, 4),
    "rightArm": rot(f"22 + {swing(10, 0, 0.5)}", 0, -12),
    "leftArm": rot(f"22 + {swing(10, 180, 0.5)}", 0, 12),
    "rightForearm": rot(-20, 0, 0),
    "leftForearm": rot(-20, 0, 0),
    "rightLeg": rot(f"16 + {swing(14, 180, 0.5)}", 0, -2),
    "leftLeg": rot(f"16 + {swing(14, 0, 0.5)}", 0, 2),
    "rightShin": rot(f"math.clamp({swing(20, 250, 0.5)}, 0, 34)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(20, 70, 0.5)}, 0, 34)", 0, 0),
    "rightFoot": rot(22, 0, 0),
    "leftFoot": rot(22, 0, 0),
    "rightToe": rot(10, 0, 0),
    "leftToe": rot(10, 0, 0),
}, cape6_loop(cape_fan(52), cape_fan(26), lag=22, span=(-8, 62)))))

put("magneto", "air", clip(merge({
    "body": {"rotation": [f"-9 + {waves((1.4, 'float'))}", 0,
                          waves((1.6, "sway"))],
             "position": [0, 0, 0]},
    "chest": rot(-5, 0, 0),
    "neck": rot(7, 0, 0),
    "rightArm": rot(f"-30 + {waves((3.4, 'float'))}", 0, -26),
    "leftArm": rot(f"-30 + {waves((3.4, 'float', 180))}", 0, 26),
    "rightForearm": rot(-18, 0, 0),
    "leftForearm": rot(-18, 0, 0),
    "rightLeg": rot(12, 0, -2),
    "leftLeg": rot(-10, 0, 2),
    "rightShin": rot(20, 0, 0),
    "leftShin": rot(8, 0, 0),
    "rightToe": rot(12, 0, 0),
    "leftToe": rot(12, 0, 0),
}, cape6_drift(cape_fan(66), cape_fan(22), flare=0.52))))

#: その場に浮く。腕はわずかに開き、爪先まで力が抜けている。
#: 上下動は 11.3 秒周期を主にして、待機より *ゆっくり* 上下させる。
put("magneto", "hover", clip(merge({
    "body": {"rotation": [waves((1.8, "float"), (0.6, "breath", 30), base=-4),
                          waves((1.4, "sway")),
                          waves((1.2, "weight"), (0.4, "float", 90))],
             "position": [waves((0.5, "weight", 90)),
                          waves((1.5, "float"), (0.5, "breath", 40), base=3.4),
                          waves((0.4, "sway", 60))]},
    "chest": rot(waves((1.2, "breath", 60)), waves((0.9, "sway", 180)), 0),
    "neck": rot(waves((-0.8, "float", 30)), waves((2.0, "sway", 40)), 0),
    "rightShoulder": rot(0, 0, -4),
    "leftShoulder": rot(0, 0, 4),
    "rightArm": rot(waves((2.2, "float"), (0.8, "breath", 40), base=-14),
                    0, -18),
    "leftArm": rot(waves((2.2, "float", 180), (0.8, "breath", 220), base=-14),
                   0, 18),
    "rightForearm": rot(waves((1.6, "weight"), base=-16), 0, 0),
    "leftForearm": rot(waves((1.6, "weight", 180), base=-16), 0, 0),
    "rightHand": rot(waves((1.6, "tremor"), (1.0, "float", 20)), 0, 0),
    "leftHand": rot(waves((1.6, "tremor", 137), (1.0, "float", 200)), 0, 0),
    "rightLeg": rot(waves((1.4, "float", 10), base=6), 0, -2),
    "leftLeg": rot(waves((1.4, "float", 190), base=6), 0, 2),
    "rightShin": rot(waves((1.0, "weight"), base=6), 0, 0),
    "leftShin": rot(waves((1.0, "weight", 180), base=6), 0, 0),
    "rightFoot": rot(28, 0, 0),
    "leftFoot": rot(28, 0, 0),
    "rightToe": rot(10, 0, 0),
    "leftToe": rot(10, 0, 0),
}, cape6_drift(cape_fan(34), cape_fan(16)))))

#: 段階 3 の常時浮遊（0.35 ブロック = 5.6）。歩行クリップをこれに差し替える。
#: 速度が乗るほど前傾し、脚が後ろへ流れる。止まっていても成立する。
_LEAN = "math.clamp(query.modified_move_speed * 26, 0, 14)"
put("magneto", "levitate", clip(merge({
    "body": {"rotation": [f"-{_LEAN} + {waves((1.2, 'float'), (0.4, 'breath', 30))}",
                          waves((1.0, "sway")),
                          waves((1.0, "weight"), (0.3, "float", 90))],
             "position": [waves((0.4, "weight", 90)),
                          waves((1.1, "float"), (0.4, "breath", 50), base=5.6),
                          0]},
    "chest": rot(waves((1.0, "breath", 40), base=-2),
                 waves((0.8, "sway", 180)), 0),
    "neck": rot(f"{_LEAN} * 0.5 + {waves((0.8, 'float', 30))}",
                waves((1.6, "sway", 40)), 0),
    "rightShoulder": rot(0, 0, -5),
    "leftShoulder": rot(0, 0, 5),
    "rightArm": rot(waves((1.8, "float"), base=-8), 0, -13),
    "leftArm": rot(waves((1.8, "float", 180), base=-8), 0, 13),
    "rightForearm": rot(-22, 0, 0),
    "leftForearm": rot(-22, 0, 0),
    "rightHand": rot(waves((1.5, "tremor")), 0, 0),
    "leftHand": rot(waves((1.5, "tremor", 137)), 0, 0),
    # 脚は「立っている」のではなく「垂れている」。膝を伸ばし切らない。
    "rightLeg": rot(f"{_LEAN} * 0.9 + {waves((1.0, 'float', 15), base=8)}",
                    0, -2),
    "leftLeg": rot(f"{_LEAN} * 0.9 + {waves((1.0, 'float', 195), base=8)}",
                   0, 2),
    "rightShin": rot(f"12 + {waves((1.2, 'weight'))}", 0, 0),
    "leftShin": rot(f"12 + {waves((1.2, 'weight', 180))}", 0, 0),
    "rightFoot": rot(30, 0, 0),
    "leftFoot": rot(30, 0, 0),
    "rightToe": rot(12, 0, 0),
    "leftToe": rot(12, 0, 0),
}, cape6_drift(cape_fan(56), cape_fan(20), flare=0.44))))

#: 玉座に座る（鋼鉄の玉座に乗っている間）。背筋は絶対に丸めない。
put("magneto", "enthrone", clip(merge({
    "body": {"rotation": [waves((0.5, "breath"), base=-3),
                          waves((0.5, "sway")), 0],
             "position": [0, waves((0.3, "float"), base=-3.0), 0]},
    "chest": rot(waves((0.7, "breath", 40), base=-4), 0, 0),
    "neck": rot(waves((-0.5, "breath", 40)), waves((2.2, "sway", 30)), 0),
    "rightShoulder": rot(0, 0, -3),
    "leftShoulder": rot(0, 0, 3),
    "rightArm": rot(waves((0.8, "breath"), base=-8), 0, -14),
    "leftArm": rot(waves((0.8, "breath", 180), base=-8), 0, 14),
    "rightForearm": rot(-46, 0, 0),
    "leftForearm": rot(-46, 0, 0),
    "rightHand": rot(waves((1.0, "tremor")), 0, -8),
    "leftHand": rot(waves((1.0, "tremor", 137)), 0, 8),
    "rightLeg": rot(-72, 0, -4),
    "leftLeg": rot(-72, 0, 4),
    "rightShin": rot(74, 0, 0),
    "leftShin": rot(74, 0, 0),
    "rightFoot": rot(-4, 0, 0),
    "leftFoot": rot(-4, 0, 0),
}, cape6_drift(cape_fan(8), cape_fan(5)))))

#: マント単体（NPC の待機に重ねたいときの予備）。移動クリップが自前で
#: マントを持っているので、既定のコントローラからは外してある。
put("magneto", "cape_idle", clip(CAPE_IDLE, blend=0.9))
put("magneto", "cape_move", clip(
    cape6_loop(cape_fan(26), cape_fan(20), lag=26),
    blend=0.9))

# ===========================================================================
#  変身体（プレイヤーが着ている状態）
# ===========================================================================
#  プレイヤーの骨（body / head / *Arm / *Leg）は **バニラのアニメが動かす**。
#  ここで同じ骨を触ると二重駆動になって形が壊れるので、
#  触るのは *バニラに無い骨だけ* —— マント・胸・首・前腕・手・肩に絞る。
def form_clip(cape, extra=None, blend=0.85):
    body = dict(cape)
    if extra:
        body = merge(body, extra)
    return clip(body, blend=blend)


put("form", "idle", form_clip(
    cape6_drift(cape_fan(12), cape_fan(9)), {
        "chest": rot(waves((0.9, "breath", 30), (0.3, "float")), 0, 0),
        "neck": rot(waves((-0.5, "breath", 30)), waves((1.2, "sway")), 0),
        "rightHand": rot(waves((1.3, "tremor")), 0, 0),
        "leftHand": rot(waves((1.3, "tremor", 137)), 0, 0),
    }))

put("form", "walk", form_clip(
    cape6_loop(cape_fan(22), cape_fan(16), lag=26), {
        "chest": rot(0, swing(2.6, 180), 0),
        "rightForearm": rot(swing(9, 90), 0, 0),
        "leftForearm": rot(swing(9, 270), 0, 0),
    }))

put("form", "run", form_clip(
    cape6_loop(cape_fan(42), cape_fan(22), lag=24), {
        "chest": rot(-2, swing(4.0, 180), 0),
        "rightForearm": rot(swing(13, 90), 0, 0),
        "leftForearm": rot(swing(13, 270), 0, 0),
    }))

put("form", "sprint", form_clip(
    cape6_loop(cape_fan(58), cape_fan(28), lag=20), {
        "chest": rot(-5, swing(5.4, 180), 0),
        "rightForearm": rot(swing(16, 90), 0, 0),
        "leftForearm": rot(swing(16, 270), 0, 0),
    }))

#: しゃがみ。マントは体に沿って落ち、裾だけが床で溜まる。
put("form", "crouch", form_clip(
    cape6_drift(cape_fan(-6), cape_fan(5)), {
        "chest": rot(waves((0.6, "breath", 30), base=-4), 0, 0),
        "neck": rot(-6, 0, 0),
    }))

put("form", "air", form_clip(
    cape6_drift(cape_fan(66), cape_fan(22), flare=0.52), {
        "chest": rot(-4, 0, 0),
    }))

put("form", "swim", form_clip(
    cape6_drift(cape_fan(72), cape_fan(26),
                speed=("sway", "float", "weight"), flare=0.46), {
        "chest": rot(waves((2.0, "float")), 0, 0),
    }))

# ===========================================================================
#  一人称（技アイテムの attachable）
# ===========================================================================
#  ボーンは root / hand / finger0-2 / thumb / gauntlet / field / core /
#  shard0-2。shard の位相 0 / 104 / 248 は **ジオメトリ側に焼いてある** ので、
#  アニメーションでは位相を足さない（足すと 0/224/128 に崩れる）。
#
#  ここでの主役は手ではなく **場**。
#    field  回転の *急停止* が「掴んだ」感を作る。加速では作れない。
#    core   溜めで吸い込み（0.72）、撃発の 1 キーだけ 1.35。
#    shard  半径 = 局所 X のスケール。伸びるので軌跡そのものが速度に見える。
#
#  そして **画面を埋めないこと**。root は position ≤3.0 / rotation ≤40° に収め、
#  全体を 0.86 倍して手前に寄りすぎないようにしてある。

FP_BASE_ROT = (4.0, 0.0, 0.0)
#  -Z が「奥」（指の向き）。少し下・少し奥へ逃がして視界の中央を空ける。
FP_BASE_POS = (0.0, -1.0, -1.6)
FP_SCALE = 0.86                  # 一人称で画面の 1/4 を超えないための倍率

#: 指の開閉（拍とは別系統の細部）。握り 0.08 秒 / 開き 0.12 秒。
#: 指の X は **正で掌側へ折れる**（負にすると反り返って甲側へ開く）。
FINGER_OPEN = -4
FINGER_SHUT = 54
THUMB_OPEN = (0, 22, -30)
THUMB_SHUT = (16, 40, -46)


def fp_beats(family, length):
    """docs/DIRECTION.md §4-1 の式。撃発は絶対秒で固定する。"""
    if family == "ult":
        b, c = 0.08 * length, 0.50 * length
        still = 0.60 * length
        d = still + 0.08
        e = d + 0.18
    elif family == "heavy":
        b, c, still = 0.12 * length, 0.46 * length, None
        d = c + 0.09
        e = d + 0.20
    else:  # light / hold
        b, c, still = 0.18 * length, 0.28 * length, None
        d = c + 0.06
        e = d + 0.13
    return dict(a=0.0, b=b, c=c, still=still, d=d, e=e, f=length)


def fp_length(tech, default):
    """contract に length が入ったらそちらを正典とする（まだ無ければ既定値）。"""
    return float(K.TECHNIQUES.get(tech, {}).get("length", default))


def _root(delta_rot, delta_pos):
    r = [FP_BASE_ROT[i] + delta_rot[i] for i in range(3)]
    p = [FP_BASE_POS[i] + delta_pos[i] for i in range(3)]
    return r, p


def fp_root(bt, spec):
    """root の軌跡。撃発は必ず ``linear``（曲線で繋ぐと接線が暴走する）。"""
    rows_r, rows_p = [], []

    def add(t, key, mode="smooth"):
        r, p = _root(*spec[key])
        rows_r.append((t, r, mode))
        rows_p.append((t, p, mode))

    add(bt["a"], "n", "linear")
    add(bt["b"], "b")
    add(bt["c"], "c", "linear")          # 撃発の直前キー
    if bt["still"] is not None:
        add(bt["still"], "c", "linear")  # 完全静止（同値 2 キー）
    add(bt["d"], "d", "linear")          # 撃発 = オーバーシュート頂点
    add(bt["e"], "e", "linear")          # 戻り着地（目標の 3% 手前）
    add(bt["f"], "n", "linear")
    return {"rotation": track(rows_r), "position": track(rows_p),
            "scale": [FP_SCALE, FP_SCALE, FP_SCALE]}


def fp_field(bt, speeds, direction=1):
    """磁界リングの回転。**速度の折れ線**で書くので急停止が正確に出る。"""
    idle, wind, top, halt = speeds
    rows = [(bt["a"], idle), (bt["b"], wind)]
    if bt["still"] is not None:
        # 必殺だけは溜めきりで完全に止め、撃発の一拍で叩き回す。
        rows += [(bt["c"], 0.0), (bt["still"], top * 2.6)]
    else:
        rows += [(bt["c"], top)]
    rows += [(bt["d"], halt), (bt["d"] + 0.06, max(halt * 1.6, 60)),
             (bt["e"], idle * 1.4), (bt["f"], idle)]
    scaled = [(t, s * direction) for t, s in rows]
    return {"rotation": spin_track(scaled)}


def fp_shards(bt, radius, orbit, direction=1):
    """周回する鉄片。半径は局所 X のスケールで作る。

    3 枚に **0.02 秒ずつ遅れ** を与える。同時に動くと 1 枚の輪に見える。
    """
    def sc(v):
        # 半径は局所 X の伸び。太さも 4 割だけ追従させて、
        # 伸び切った瞬間に紙のような薄板に見えないようにする。
        return [v, round(1 + (v - 1) * 0.4, 3), round(1 + (v - 1) * 0.4, 3)]

    out = {}
    for i in range(3):
        lag = 0.02 * i
        rows = [(bt["a"], orbit[0]), (bt["b"] + lag, orbit[1])]
        if bt["still"] is not None:
            rows += [(bt["c"] + lag, 0.0), (bt["still"] + lag, orbit[1] * 2.2)]
        else:
            rows += [(bt["c"] + lag, orbit[1])]
        rows += [(bt["d"] + lag, orbit[2]), (bt["f"], orbit[2])]
        n, w, s, back = radius
        out[f"shard{i}"] = {
            "rotation": spin_track([(t, v * direction) for t, v in rows]),
            "scale": track([
                (bt["a"], sc(n), "linear"),
                (bt["b"] + lag, sc(n + (w - n) * 0.45)),
                (bt["c"] + lag, sc(w), "linear"),
                (bt["d"] + lag, sc(s), "linear"),
                (bt["d"] + lag + 0.12, sc(back), "linear"),
                (bt["f"], sc(back), "linear"),
            ]),
        }
    return out


def fp_core(bt):
    """芯。溜めで吸い込み、撃発の 1 キーだけ膨らみ、0.10 秒で戻る。"""
    rows = [(bt["a"], [1, 1, 1], "linear"), (bt["b"], [1.07] * 3)]
    if bt["still"] is not None:
        rows += [(bt["c"], [0.72] * 3, "linear"),
                 (bt["still"], [0.68] * 3, "linear")]
    else:
        rows += [(bt["c"], [0.72] * 3, "linear")]
    rows += [(bt["d"], [1.35] * 3, "linear"),
             (bt["d"] + 0.10, [1.0] * 3, "linear"),
             (bt["f"], [1, 1, 1], "linear")]
    return {"scale": track(rows)}


def fp_fingers(bt, mode):
    """握り 0.08 秒 / 開き 0.12 秒。指ごとに 0.012 秒ずらす。

    3 本が同時に動くとミトンに見える。
    """
    out = {}
    for i in range(3):
        lag = 0.012 * i
        if mode == "clench":       # 撃発で握り込む（剥奪・圧壊・拘束）
            rows = [(bt["a"], [0, 0, 0], "linear"),
                    (max(0.02, bt["c"] - 0.12) + lag, [FINGER_OPEN, 0, 0]),
                    (bt["d"] - 0.08 + lag, [FINGER_OPEN, 0, 0], "linear"),
                    (bt["d"] + lag, [FINGER_SHUT, 0, 0], "linear"),
                    (bt["e"] + lag, [FINGER_SHUT * 0.7, 0, 0], "linear"),
                    (bt["f"], [0, 0, 0], "linear")]
            thumb = [(bt["a"], [0, 0, 0], "linear"),
                     (bt["d"] - 0.08, [-4, -6, 4], "linear"),
                     (bt["d"], [t - o for t, o in zip(THUMB_SHUT, THUMB_OPEN)],
                      "linear"),
                     (bt["f"], [0, 0, 0], "linear")]
        elif mode == "steady":     # 構えたまま（障壁・集中・飛行）
            rows = [(bt["a"], [0, 0, 0], "linear"),
                    (bt["c"] + lag, [FINGER_SHUT * 0.35, 0, 0], "linear"),
                    (bt["f"], [FINGER_SHUT * 0.35, 0, 0], "linear")]
            thumb = [(bt["a"], [0, 0, 0], "linear"),
                     (bt["c"], [8, 8, -8], "linear"),
                     (bt["f"], [8, 8, -8], "linear")]
        else:                      # splay — 溜めで握り、撃発で開き切る
            rows = [(bt["a"], [0, 0, 0], "linear"),
                    (bt["c"] - 0.08 + lag, [FINGER_SHUT * 0.5, 0, 0]),
                    (bt["c"] + lag, [FINGER_SHUT, 0, 0], "linear"),
                    (bt["d"] + lag, [FINGER_SHUT, 0, 0], "linear"),
                    (bt["d"] + 0.12 + lag, [FINGER_OPEN * 2.2, 0, 0], "linear"),
                    (bt["f"], [0, 0, 0], "linear")]
            thumb = [(bt["a"], [0, 0, 0], "linear"),
                     (bt["c"], [12, 14, -12], "linear"),
                     (bt["d"] + 0.12, [-6, -8, 6], "linear"),
                     (bt["f"], [0, 0, 0], "linear")]
        out[f"finger{i}"] = {"rotation": track(rows)}
    out["thumb"] = {"rotation": track(thumb)}
    return out


#: 手首。腕の主動より 0.09 秒遅れて振れる（遅れ振り）。
def fp_wrist(bt, amount):
    return {"hand": {"rotation": track([
        (bt["a"], [0, 0, 0], "linear"),
        (bt["c"], [-amount * 0.4, 0, 0]),
        (bt["d"] + 0.04, [amount, 0, 0], "linear"),
        (bt["e"] + 0.05, [-amount * 0.25, 0, 0]),
        (bt["f"], [0, 0, 0], "linear"),
    ])}}


# --- 技ごとの性格 -----------------------------------------------------------
#  n/b/c/d/e は root の (rotation, position) の *差分*。
#  field  = (待機, 溜め, 溜めきり, 撃発後)  °/秒。落差が大きいほど「掴んだ」。
#  orbit  = (待機, 溜め, 撃発後)            °/秒。
#  radius = (中立, 溜め, 撃発, 残心)        鉄片の半径倍率。
FP_ACTS = {
    "thrust": dict(  # 磁力斥力 — 掌で押し出す。場が止まり、鉄片が飛ぶ。
        tech="repulse", family="light", ja="突き出す", fingers="splay",
        n=([0, 0, 0], [0, 0, 0]),
        b=([15, -6, 2], [0.3, -0.4, 1.3]),
        c=([23, -9, 3], [0.5, -0.8, 2.1]),
        d=([-31, 7, -4], [-0.4, 1.0, -2.7]),
        e=([-5, 2, -1], [0, 0.2, -0.5]),
        field=(55, 620, 900, 110), orbit=(150, 760, 120),
        radius=(1.0, 0.52, 1.62, 1.0), wrist=16,
        fx=("mag_field", "repulse_wave")),
    "pull": dict(   # 磁力引力 — 逆回り。鉄片は撃発で *内へ* 落ちる。
        tech="attract", family="light", ja="引き寄せる", fingers="clench",
        n=([0, 0, 0], [0, 0, 0]),
        b=([-14, -4, 0], [0, -0.3, -1.6]),
        c=([-22, -7, 2], [-0.3, -0.6, -2.6]),
        d=([26, 9, -3], [0.4, 0.9, 2.6]),
        e=([5, 2, 0], [0, 0.2, 0.5]),
        field=(55, 540, 820, 90), orbit=(140, 700, 150),
        radius=(1.0, 1.45, 0.34, 0.9), wrist=-18, direction=-1,
        fx=("mag_field", "attract_funnel")),
    "grip": dict(   # 金属剥奪 — root はほとんど動かない。指と鉄片で語る。
        tech="disarm", family="light", ja="握り込む", fingers="clench",
        n=([0, 0, 0], [0, 0, 0]),
        b=([-9, -7, 5], [0, 0.3, -1.0]),
        c=([-15, -4, -3], [0, 0.5, -1.7]),
        d=([-24, 3, -8], [0, 0.9, -2.2]),
        e=([-6, 1, -2], [0, 0.2, -0.5]),
        field=(55, 480, 760, 40), orbit=(130, 620, 60),
        radius=(1.0, 1.30, 0.42, 0.78), wrist=12,
        fx=("mag_field", "disarm_flash")),
    "lance": dict(  # 磁界斬 — 一直線。鉄片が槍状に伸び切る（radius 2.2）。
        tech="lance", family="light", ja="槍を放つ", fingers="splay",
        n=([0, 0, 0], [0, 0, 0]),
        b=([18, -10, 0], [0.4, -0.5, 1.5]),
        c=([27, -13, 1], [0.7, -0.9, 2.4]),
        d=([-36, 6, -2], [-0.5, 0.7, -2.9]),
        e=([-6, 1, 0], [0, 0.2, -0.6]),
        field=(55, 700, 980, 70), orbit=(160, 880, 80),
        radius=(1.0, 0.46, 2.20, 1.0), wrist=20,
        fx=("mag_field", "lance_streak")),
    "storm": dict(  # 鉄片嵐 — 止まらない。撃発の後も場が回り続ける。
        tech="shard_storm", family="heavy", ja="嵐を呼ぶ", fingers="splay",
        n=([0, 0, 0], [0, 0, 0]),
        b=([10, 8, -4], [-0.4, -0.5, 0.8]),
        c=([-34, 14, -6], [-0.8, 2.4, 1.2]),
        d=([-39, -6, 5], [0.6, 2.8, -1.4]),
        e=([-14, -2, 2], [0.2, 1.0, -0.4]),
        field=(55, 760, 1040, 420), orbit=(170, 900, 520),
        radius=(1.0, 0.60, 1.85, 1.45), wrist=14,
        fx=("mag_field", "storm_swirl")),
    "guard": dict(  # 磁力障壁 — 構えたら動かない。保持は最後のキーで固める。
        tech="barrier", family="hold", ja="受け", fingers="steady",
        n=([0, 0, 0], [0, 0, 0]),
        b=([-12, 18, 4], [-1.0, 0.4, -1.2]),
        c=([-19, 24, 6], [-1.6, 0.7, -1.9]),
        d=([-24, 27, 8], [-2.0, 1.0, -2.4]),
        e=([-21, 25, 7], [-1.8, 0.9, -2.1]),
        field=(55, 300, 480, 30), orbit=(120, 340, 46),
        radius=(1.0, 0.85, 1.30, 1.22), wrist=8, loop="hold_on_last_frame",
        fx=("mag_field", "barrier_hex")),
    "crush": dict(  # 磁気圧壊 — 溜めが長い。鉄片が内へ潰れて出てこない。
        tech="crush", family="heavy", ja="握り潰す", fingers="clench",
        n=([0, 0, 0], [0, 0, 0]),
        b=([-11, -9, 3], [0, 0.4, -1.2]),
        c=([-26, -12, 6], [-0.5, 1.2, -2.2]),
        d=([-33, -5, -4], [0.3, 1.5, -2.8]),
        e=([-10, -1, -1], [0, 0.4, -0.7]),
        field=(55, 420, 880, 24), orbit=(110, 640, 30),
        radius=(1.0, 1.25, 0.28, 0.36), wrist=-14, direction=-1,
        fx=("mag_field", "crush_implode")),
    "raise": dict(  # 掲げる（大地隆起・磁極反転・玉座）— 場が大きく開く。
        tech="polarity", family="heavy", ja="掲げる", fingers="splay",
        n=([0, 0, 0], [0, 0, 0]),
        b=([12, 0, 0], [0, -0.7, 1.0]),
        c=([-33, 4, -2], [0, 2.6, 0.6]),
        d=([-38, -3, 3], [0, 2.9, -0.8]),
        e=([-12, -1, 1], [0, 1.0, -0.2]),
        field=(55, 560, 900, 150), orbit=(120, 700, 190),
        radius=(1.0, 0.72, 1.90, 1.55), wrist=12,
        fx=("mag_field", "polarity_field")),
    "pulse": dict(  # EMP — 手はほぼ動かない。落差だけで見せる（900 → 25）。
        tech="emp", family="heavy", ja="パルス", fingers="splay",
        n=([0, 0, 0], [0, 0, 0]),
        b=([-8, 2, 0], [0, 0.3, -0.8]),
        c=([-14, 3, 0], [0, 0.5, -1.4]),
        d=([-4, -1, 0], [0, 0.1, -2.9]),
        e=([-2, 0, 0], [0, 0, -0.4]),
        field=(55, 880, 1200, 25), orbit=(140, 980, 34),
        radius=(1.0, 0.40, 2.05, 1.0), wrist=10,
        fx=("mag_field", "emp_wave")),
    "bind": dict(   # 鋼鉄拘束 — 撃発で場が *完全に* 止まり、鉄片が檻になる。
        tech="iron_bind", family="heavy", ja="縫い止める", fingers="clench",
        n=([0, 0, 0], [0, 0, 0]),
        b=([-10, -6, 4], [0, 0.3, -1.0]),
        c=([-21, -9, 7], [-0.4, 0.9, -1.8]),
        d=([-28, 2, -6], [0.3, 1.2, -2.4]),
        e=([-9, 0, -2], [0, 0.4, -0.6]),
        field=(55, 640, 940, 8), orbit=(120, 720, 10),
        radius=(1.0, 1.10, 1.62, 1.62), wrist=13,
        fx=("mag_field", "bind_weld")),
    "focus": dict(  # 磁力視 — 動きを最小限に。場は遅く、鉄片は広く開いて止まる。
        tech="sight", family="hold", ja="集中", fingers="steady",
        n=([0, 0, 0], [0, 0, 0]),
        b=([-14, 10, 0], [-0.9, 0.7, 0.4]),
        c=([-22, 13, 0], [-1.5, 1.2, 0.8]),
        d=([-25, 14, 0], [-1.7, 1.4, 0.9]),
        e=([-24, 13, 0], [-1.6, 1.3, 0.9]),
        field=(55, 160, 220, 26), orbit=(90, 200, 32),
        radius=(1.0, 1.20, 1.44, 1.40), wrist=6, loop="hold_on_last_frame",
        fx=("mag_field", "sight_ping")),
    "sphere": dict(  # 磁界の棺 — 溜めきりで完全静止。無音の 0.30 秒が効く。
        tech="sphere", family="ult", ja="棺を閉じる", fingers="splay",
        n=([0, 0, 0], [0, 0, 0]),
        b=([14, 4, -2], [0, -0.6, 1.2]),
        c=([-30, 6, -3], [0, 2.7, 0.4]),
        d=([-40, -5, 4], [0, 3.0, -2.4]),
        e=([-13, -2, 1], [0, 1.1, -0.5]),
        field=(55, 900, 1300, 60), orbit=(160, 1080, 70),
        radius=(1.0, 0.24, 2.40, 1.30), wrist=18,
        fx=("sphere_core", "sphere_detonate")),
}

#: 技クリップの既定の尺（contract に length が入るまでの正典。§4-2 の表）。
FP_LENGTH = {
    "repulse": 0.72, "attract": 0.75, "disarm": 0.70, "lance": 0.68,
    "shard_storm": 1.30, "barrier": 0.86, "crush": 1.16, "polarity": 1.36,
    "emp": 1.10, "iron_bind": 1.06, "sight": 0.78, "sphere": 3.00,
}

for _name, _spec in FP_ACTS.items():
    _L = fp_length(_spec["tech"], FP_LENGTH[_spec["tech"]])
    _bt = fp_beats(_spec["family"], _L)
    _dir = _spec.get("direction", 1)
    _bones = merge(
        {"root": fp_root(_bt, _spec)},
        fp_wrist(_bt, _spec["wrist"]),
        fp_fingers(_bt, _spec["fingers"]),
        {"field": fp_field(_bt, _spec["field"], _dir)},
        {"core": fp_core(_bt)},
        fp_shards(_bt, _spec["radius"], _spec["orbit"], _dir),
    )
    # 一人称の VFX は **芯と閃光だけ**。0.3〜2.5m の煙や破片を置くと
    # 視界が全部潰れる（あれは三人称専用）。
    _fx = {tag(_bt["c"]): {"effect": K.part(_spec["fx"][0])},
           tag(_bt["d"]): {"effect": K.part(_spec["fx"][1])}}
    put("fp", _name, clip(_bones, length=round(_bt["f"], 3),
                          loop=_spec.get("loop", False), particles=_fx))

#: 飛行だけは「撃つ」ものではなく乗り続けるもの。唯一の真のループ。
put("fp", "fly", clip(merge({
    "root": {"rotation": [waves((2.2, "float"), (0.8, "breath", 40), base=-12),
                          waves((1.8, "sway")), waves((1.4, "weight"))],
             "position": [waves((0.5, "weight", 90)),
                          waves((0.7, "float"), base=-0.4),
                          waves((0.4, "sway"), base=1.2)],
             "scale": [FP_SCALE, FP_SCALE, FP_SCALE]},
    "hand": rot(waves((1.6, "breath", 60)), 0, 0),
    "field": rot(0, 0, "query.anim_time * 240"),
    "core": {"scale": [waves((0.10, "breath"), (0.04, "tremor"), base=1.0)] * 3},
}, {f"shard{i}": {
    "rotation": [0, 0, f"query.anim_time * {300 + i * 34}"],
    # 3 枚が違う速さで息をする。同じ式を配ると輪が 1 枚に見える。
    "scale": [waves((0.16, ("float", "weight", "sway")[i], i * 47), base=1.22),
              1, 1]}
    for i in range(3)}), loop=True))

#: 一人称の待機。ここが一番長く画面に映るので、常に動かし続ける。
put("fp", "idle", clip(merge({
    "root": {"rotation": [waves((1.3, "breath"), (0.6, "float", 40)),
                          waves((1.0, "sway"), (0.4, "weight", 90)),
                          waves((0.8, "weight"))],
             "position": [waves((0.30, "weight", 90)),
                          waves((0.34, "float"), (0.14, "breath", 60),
                                base=FP_BASE_POS[1]),
                          waves((0.24, "sway"), base=FP_BASE_POS[2])],
             "scale": [FP_SCALE, FP_SCALE, FP_SCALE]},
    "hand": rot(waves((0.9, "tremor"), (1.1, "weight", 30)), 0, 0),
    "finger0": rot(waves((2.4, "tremor"), (1.2, "weight", 20)), 0, 0),
    "finger1": rot(waves((2.4, "tremor", 24), (1.2, "weight", 40)), 0, 0),
    "finger2": rot(waves((2.4, "tremor", 48), (1.2, "weight", 60)), 0, 0),
    "thumb": rot(waves((1.8, "tremor", 90)), 0, 0),
    "field": rot(0, 0, "query.anim_time * 55"),
    "core": {"scale": [waves((0.07, "breath"), (0.03, "tremor", 30),
                             base=1.0)] * 3},
}, {f"shard{i}": {
    # 待機でも 3 枚の速度を 1 割ずつ変える。ずれ続けるので飽きない。
    "rotation": [0, 0, f"query.anim_time * {126 + i * 13}"],
    "scale": [waves((0.10, ("sway", "float", "weight")[i], i * 53), base=1.0),
              1, 1]}
    for i in range(3)})))

#: 三人称で技アイテムを持っている時（手元に磁力球が浮いて見える）。
put("fp", "third", clip(merge({
    "root": {"rotation": [waves((2.0, "breath"), base=-8),
                          waves((1.2, "sway")), 0],
             "position": [0, waves((0.24, "breath", 40)), -1.0]},
    "field": rot(0, 0, "query.anim_time * 90"),
    "core": {"scale": [waves((0.09, "breath"), base=1.0)] * 3},
}, {f"shard{i}": rot(0, 0, f"query.anim_time * {150 + i * 11}")
    for i in range(3)})))

# ===========================================================================
#  センチネル  —  重い。加速も減速も鈍い。
# ===========================================================================
#  歩幅を人間の半分の周期にして、一歩を大きく遅くする。体重は腕の振りでは
#  なく **接地のたびの沈み込み**（thud）で読ませる。
SENT_GAIT = gait(0.55, 1.05, 1.6)

put("sentinel", "idle", clip({
    # 機械の待機 = ほぼ静止 + 遅いサーボのうねり + 速い電気的な震え。
    "body": {"rotation": [waves((0.35, "servo"), (0.06, "jitter", 40)),
                          waves((0.30, "sway")),
                          waves((0.25, "servo", 90))],
             "position": [0, waves((0.14, "servo", 90)), 0]},
    "chest": rot(waves((0.20, "servo", 40)), waves((0.5, "sway", 120)), 0),
    "neck": rot(waves((0.10, "jitter")), waves((1.2, "sway", 60)), 0),
    # 頭だけが索敵で振れる。生き物ではなく機械の「見回し」。
    "head": rot(waves((0.4, "servo", 20)),
                waves((7.0, "sway"), (1.4, "servo", 60)), 0),
    "rightShoulder": rot(0, 0, waves((0.3, "servo"), base=-3)),
    "leftShoulder": rot(0, 0, waves((-0.3, "servo"), base=3)),
    "rightArm": rot(waves((0.5, "servo"), (0.08, "jitter")), 0, -4),
    "leftArm": rot(waves((0.5, "servo", 180), (0.08, "jitter", 90)), 0, 4),
    "rightForearm": rot(waves((0.4, "servo", 60), base=-6), 0, 0),
    "leftForearm": rot(waves((0.4, "servo", 240), base=-6), 0, 0),
    "rightHand": rot(waves((0.20, "jitter")), 0, 0),
    "leftHand": rot(waves((0.20, "jitter", 150)), 0, 0),
}))

put("sentinel", "walk", clip({
    # 半分の周期 = 一歩が二倍長い。巨体はこれだけで「遅く大きく」なる。
    "body": {"rotation": [f"4 + {swing(1.4, 0, 0.5, SENT_GAIT)}",
                          swing(3.4, 90, 0.5, SENT_GAIT),
                          swing(4.2, 0, 0.5, SENT_GAIT)],
             "position": [swing(0.7, 90, 0.5, SENT_GAIT),
                          thud(2.1, 0.5, 0, 0.55, SENT_GAIT), 0]},
    "chest": rot(f"-2 + {swing(1.0, 0, 0.5, SENT_GAIT)}",
                 swing(3.0, 180, 0.5, SENT_GAIT),
                 swing(1.6, 90, 0.5, SENT_GAIT)),
    # 首は胴と逆へ。頭が一拍遅れて付いてくると質量が乗る。
    "neck": rot(swing(-1.6, 0, 0.5, SENT_GAIT),
                swing(-2.0, 180, 0.5, SENT_GAIT), 0),
    # 接地の沈み込みと逆向きに頭だけ跳ねる。首から上が一拍遅れて見える。
    "head": rot(f"0 - ({thud(3.0, 0.5, 0, 0.5, SENT_GAIT)})", 0, 0),
    "rightShoulder": rot(0, 0, swing(5.0, 180, 0.5, SENT_GAIT)),
    "leftShoulder": rot(0, 0, swing(5.0, 0, 0.5, SENT_GAIT)),
    # 腕は小さくしか振らない。重い腕は振れないから重い。
    "rightArm": rot(swing(17, 0, 0.5, SENT_GAIT), 0, -6),
    "leftArm": rot(swing(17, 180, 0.5, SENT_GAIT), 0, 6),
    "rightForearm": rot(f"-14 + {swing(7, 80, 0.5, SENT_GAIT)}", 0, 0),
    "leftForearm": rot(f"-14 + {swing(7, 260, 0.5, SENT_GAIT)}", 0, 0),
    "rightLeg": rot(swing(30, 180, 0.5, SENT_GAIT), 0, -1),
    "leftLeg": rot(swing(30, 0, 0.5, SENT_GAIT), 0, 1),
    "rightShin": rot(
        f"math.clamp({swing(34, 250, 0.5, SENT_GAIT)}, 0, 40)", 0, 0),
    "leftShin": rot(
        f"math.clamp({swing(34, 70, 0.5, SENT_GAIT)}, 0, 40)", 0, 0),
    # 足裏は真っ平らに落とす（つま先から着かない）。これが「踏む」音になる。
    "rightFoot": rot(
        f"math.clamp({swing(20, 200, 0.5, SENT_GAIT)}, -6, 14)", 0, 0),
    "leftFoot": rot(
        f"math.clamp({swing(20, 20, 0.5, SENT_GAIT)}, -6, 14)", 0, 0),
    "rightToe": rot(f"math.clamp({swing(10, 170, 0.5, SENT_GAIT)}, 0, 12)",
                    0, 0),
    "leftToe": rot(f"math.clamp({swing(10, 350, 0.5, SENT_GAIT)}, 0, 12)",
                   0, 0),
}))

put("sentinel", "beam", clip({
    "rightArm": {"rotation": track([(0, [0, 0, -4]), (0.20, [12, -4, -2]),
                                    (0.35, [-96, -12, -6], "linear"),
                                    (1.1, [-98, -12, -6], "linear"),
                                    (1.6, [0, 0, -4], "linear")])},
    "rightForearm": {"rotation": track([(0, [0, 0, 0]),
                                        (0.35, [-12, 0, 0], "linear"),
                                        (1.1, [-8, 0, 0], "linear"),
                                        (1.6, [0, 0, 0], "linear")])},
    "rightShoulder": {"rotation": track([(0, [0, 0, 0]), (0.30, [0, 0, -9]),
                                         (1.1, [0, 0, -9], "linear"),
                                         (1.6, [0, 0, 0], "linear")])},
    "leftArm": {"rotation": track([(0, [0, 0, 4]), (0.25, [10, 5, 2]),
                                   (0.45, [-92, 14, 6], "linear"),
                                   (1.1, [-94, 14, 6], "linear"),
                                   (1.6, [0, 0, 4], "linear")])},
    "leftShoulder": {"rotation": track([(0, [0, 0, 0]), (0.40, [0, 0, 9]),
                                        (1.1, [0, 0, 9], "linear"),
                                        (1.6, [0, 0, 0], "linear")])},
    "head": {"rotation": track([(0, [0, 0, 0]), (0.35, [-10, 0, 0], "linear"),
                                (1.1, [-10, 0, 0], "linear"),
                                (1.6, [0, 0, 0], "linear")])},
    "chest": {"rotation": track([(0, [0, 0, 0]), (0.35, [-6, 0, 0], "linear"),
                                 (1.1, [-6, 0, 0], "linear"),
                                 (1.6, [0, 0, 0], "linear")])},
    "body": {"position": track([(0, [0, 0, 0]), (0.35, [0, 0, 1.2], "linear"),
                                (1.1, [0, 0, 1.2], "linear"),
                                (1.6, [0, 0, 0], "linear")])},
}, length=1.6, loop=False))

put("sentinel", "stomp", clip({
    "body": {"position": track([(0, [0, 0, 0]), (0.30, [0, 6, 0]),
                                (0.46, [0, -3.4, 0], "linear"),
                                (0.9, [0, 0, 0], "linear")]),
             "rotation": track([(0, [0, 0, 0]), (0.30, [-6, 0, 0]),
                                (0.46, [7, 0, 0], "linear"),
                                (0.9, [0, 0, 0], "linear")])},
    "rightLeg": {"rotation": track([(0, [0, 0, 0]), (0.30, [-52, 0, 0]),
                                    (0.46, [16, 0, 0], "linear"),
                                    (0.9, [0, 0, 0], "linear")])},
    "rightShin": {"rotation": track([(0, [0, 0, 0]), (0.30, [64, 0, 0]),
                                     (0.46, [0, 0, 0], "linear"),
                                     (0.9, [0, 0, 0], "linear")])},
    "rightFoot": {"rotation": track([(0, [0, 0, 0]), (0.30, [-18, 0, 0]),
                                     (0.46, [4, 0, 0], "linear"),
                                     (0.9, [0, 0, 0], "linear")])},
    "rightArm": {"rotation": track([(0, [0, 0, -4]), (0.30, [-34, 0, -18]),
                                    (0.46, [22, 0, -4], "linear"),
                                    (0.9, [0, 0, -4], "linear")])},
    "leftArm": {"rotation": track([(0, [0, 0, 4]), (0.30, [-34, 0, 18]),
                                   (0.46, [22, 0, 4], "linear"),
                                   (0.9, [0, 0, 4], "linear")])},
    "head": {"rotation": track([(0, [0, 0, 0]), (0.30, [-8, 0, 0]),
                                (0.48, [12, 0, 0], "linear"),
                                (0.9, [0, 0, 0], "linear")])},
}, length=0.9, loop=False))

put("sentinel", "scan", clip({
    # 首の振りは等速ではなく、両端で 0.1 秒止める。機械の走査に見える。
    "head": {"rotation": track([(0, [0, 0, 0]), (0.5, [0, -52, 0], "linear"),
                                (0.62, [0, -52, 0], "linear"),
                                (1.2, [0, 52, 0], "linear"),
                                (1.32, [0, 52, 0], "linear"),
                                (1.8, [0, 0, 0], "linear")])},
    "neck": {"rotation": track([(0, [0, 0, 0]), (0.5, [0, -12, 0], "linear"),
                                (1.2, [0, 12, 0], "linear"),
                                (1.8, [0, 0, 0], "linear")])},
    "chest": {"rotation": track([(0, [0, 0, 0]), (0.5, [0, -14, 0], "linear"),
                                 (1.2, [0, 14, 0], "linear"),
                                 (1.8, [0, 0, 0], "linear")])},
}, length=1.8, loop=False))

put("sentinel", "hurt", clip({
    "body": {"rotation": track([(0, [0, 0, 0]), (0.10, [-8, 0, 5], "linear"),
                                (0.36, [0, 0, 0], "linear")])},
    "head": {"rotation": track([(0, [0, 0, 0]), (0.10, [10, 0, -6], "linear"),
                                (0.36, [0, 0, 0], "linear")])},
    "chest": {"rotation": track([(0, [0, 0, 0]), (0.13, [-5, 0, 3]),
                                 (0.36, [0, 0, 0], "linear")])},
}, length=0.36, loop=False))

put("sentinel", "death", clip({
    # 膝から落ちる。巨体は倒れる前に一度「立て直そうとして」失敗する。
    "body": {"rotation": track([(0, [0, 0, 0]), (0.5, [-18, 0, 6]),
                                (1.1, [10, 0, -3]), (1.5, [4, 0, 10]),
                                (2.2, [0, 0, 84], "linear")]),
             "position": track([(0, [0, 0, 0]), (1.1, [0, -4, 0]),
                                (2.2, [0, -12, 0], "linear")])},
    "head": {"rotation": track([(0, [0, 0, 0]), (0.5, [-24, 0, 0]),
                                (1.3, [8, 0, 0]),
                                (2.2, [36, 0, 0], "linear")])},
    "rightArm": {"rotation": track([(0, [0, 0, 0]), (1.1, [-52, 0, -30]),
                                    (2.2, [-18, 0, -46], "linear")])},
    "leftArm": {"rotation": track([(0, [0, 0, 0]), (1.1, [-52, 0, 30]),
                                   (2.2, [-18, 0, 46], "linear")])},
    "rightLeg": {"rotation": track([(0, [0, 0, 0]), (0.9, [-40, 0, 0]),
                                    (2.2, [-26, 0, 0], "linear")])},
    "leftLeg": {"rotation": track([(0, [0, 0, 0]), (1.2, [-24, 0, 0]),
                                   (2.2, [-14, 0, 0], "linear")])},
    "rightShin": {"rotation": track([(0, [0, 0, 0]), (0.9, [70, 0, 0]),
                                     (2.2, [46, 0, 0], "linear")])},
}, length=2.2, loop="hold_on_last_frame"))

# ===========================================================================
#  小物
# ===========================================================================
put("prop", "spin", clip({
    "body": rot("query.anim_time * 210", "query.anim_time * 340", 0),
}))
put("prop", "orbit", clip({
    "body": {"rotation": [0, "query.anim_time * 260", 0],
             "position": [0, waves((1.4, 137), (0.5, "float", 40)), 0]},
}))
put("prop", "pulse", clip({
    "core": {"scale": [waves((0.20, 156), (0.07, "tremor", 40),
                             base=1.0)] * 3},
    "ring": rot(0, "query.anim_time * 190", 0),
}))
put("prop", "drift", clip({
    "body": {"rotation": [waves((6.0, "sway"), (2.0, "float", 50)),
                          "query.anim_time * 40",
                          waves((5.0, "weight", 50), (1.6, "sway", 120))],
             "position": [waves((0.6, "float")), waves((1.0, "sway", 30)),
                          waves((0.6, "weight", 60))]},
}))

# ===========================================================================
#  コントローラ
# ===========================================================================
#  blend_transition は「その状態を出入りするときに何秒かけて溶かすか」。
#  ここを一律 0.2 にすると、全部の切り替えが同じ鈍さになる。
#  **止めたい所と溶かしたい所を分ける** のがこの節の全て。
C: dict = {}

#: 用途別の溶け時間（秒）。数字ではなく *意味* で選べるように名前を付ける。
BLEND = {
    "snap": 0.04,     # 撃発・被弾。溶かした瞬間に切れ味が死ぬ
    "act": 0.09,      # 技の構えへ。予備動作があるので少しだけ溶かす
    "leap": 0.12,     # 離地・着地。接地は事実なので曖昧にしない
    "cycle": 0.26,    # 歩き ↔ 走り。位相が繋がっているので長めに溶かす
    "settle": 0.20,   # 立ち止まる
    "float": 0.38,    # 浮遊へ。重力から解放される所だけは思い切り溶かす
    "fall": 0.30,     # 死亡。最後は急がない
}


def controller(name, initial, states):
    C[K.ctrl(name)] = {"initial_state": initial, "states": states}


def state(anims, transitions=None, blend=BLEND["settle"], on_entry=None):
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
                    ("walk", f"{SPD} > 0.02")], blend=BLEND["settle"]),
    "walk": state(["look", "walk"],
                  [("air", "!query.is_on_ground"),
                   ("run", f"{SPD} > 0.26"),
                   ("stand", f"{SPD} <= 0.02")], blend=BLEND["cycle"]),
    "run": state(["look", "run"],
                 [("air", "!query.is_on_ground"),
                  ("walk", f"{SPD} <= 0.26")], blend=BLEND["cycle"]),
    "air": state(["look", "air"],
                 [("stand", "query.is_on_ground")], blend=BLEND["leap"]),
})

controller("humanoid.action", "none", {
    # none は「次に飛び込む先」を決める側。ここを短くしないと技が鈍る。
    "none": state([], [("hurt", "query.is_delayed_attacking || variable.hurt"),
                       ("attack", "query.mark_variant == 1"),
                       ("tech", "query.mark_variant == 2"),
                       ("death", "query.is_alive == 0")], blend=BLEND["snap"]),
    "attack": state(["attack"], [("none", "query.mark_variant != 1")],
                    blend=BLEND["act"]),
    "tech": state(["tech"], [("none", "query.mark_variant != 2")],
                  blend=BLEND["act"]),
    "hurt": state(["hurt"], [("none", "query.mark_variant != 3")],
                  blend=BLEND["snap"]),
    "death": state(["death"], [], blend=BLEND["fall"]),
})

# --- マグニートー ------------------------------------------------------------
#  移動クリップが自前でマントを持っているので、cape コントローラは重ねない
#  （重ねると cape0-5 が二重に駆動されて振れ幅が倍になる）。
controller("magneto.general", "stand", {
    "stand": state(["look", "idle"],
                   [("hover", "query.mark_variant == 5"),
                    ("air", "!query.is_on_ground"),
                    ("walk", f"{SPD} > 0.02")], blend=BLEND["settle"]),
    "walk": state(["look", "walk"],
                  [("hover", "query.mark_variant == 5"),
                   ("air", "!query.is_on_ground"),
                   ("run", f"{SPD} > 0.24"),
                   ("stand", f"{SPD} <= 0.02")], blend=BLEND["cycle"]),
    "run": state(["look", "run"],
                 [("hover", "query.mark_variant == 5"),
                  ("air", "!query.is_on_ground"),
                  ("walk", f"{SPD} <= 0.24")], blend=BLEND["cycle"]),
    "air": state(["look", "air"],
                 [("hover", "query.mark_variant == 5"),
                  ("stand", "query.is_on_ground")], blend=BLEND["leap"]),
    # 浮遊へ入る所だけは長く溶かす。重力を抜ける瞬間は輪郭を曖昧にしていい。
    "hover": state(["look", "hover"],
                   [("stand", "query.mark_variant != 5")],
                   blend=BLEND["float"]),
})

controller("magneto.action", "none", {
    "none": state([], [("attack", "query.mark_variant == 1"),
                       ("tech", "query.mark_variant == 2"),
                       ("hurt", "query.mark_variant == 3"),
                       ("ult", "query.mark_variant == 4"),
                       ("death", "query.is_alive == 0")], blend=BLEND["snap"]),
    "attack": state(["attack"], [("none", "query.mark_variant != 1")],
                    blend=BLEND["act"]),
    "tech": state(["tech"], [("none", "query.mark_variant != 2")],
                  blend=BLEND["act"]),
    "hurt": state(["hurt"], [("none", "query.mark_variant != 3")],
                  blend=BLEND["snap"]),
    # 必殺は予備動作から始まるので、入りだけは溶かしてよい。
    "ult": state(["ult"], [("none", "query.mark_variant != 4")], blend=0.16),
    "death": state(["death"], [], blend=BLEND["fall"]),
})

# --- センチネル --------------------------------------------------------------
#  重い機体は切り替えも鈍い。ここだけ意図的に長めの溶け時間を使う。
controller("sentinel.general", "stand", {
    "stand": state(["look", "idle"], [("walk", f"{SPD} > 0.02")], blend=0.34),
    "walk": state(["look", "walk"], [("stand", f"{SPD} <= 0.02")], blend=0.34),
})

controller("sentinel.action", "none", {
    "none": state([], [("beam", "query.mark_variant == 2"),
                       ("stomp", "query.mark_variant == 1"),
                       ("scan", "query.mark_variant == 5"),
                       ("hurt", "query.mark_variant == 3"),
                       ("death", "query.is_alive == 0")], blend=BLEND["leap"]),
    "beam": state(["beam"], [("none", "query.mark_variant != 2")], blend=0.24),
    # 踏みつけだけは機械でも速い。ここを溶かすと重量が伝わらない。
    "stomp": state(["stomp"], [("none", "query.mark_variant != 1")],
                   blend=BLEND["snap"]),
    "scan": state(["scan"], [("none", "query.mark_variant != 5")], blend=0.24),
    "hurt": state(["hurt"], [("none", "query.mark_variant != 3")],
                  blend=BLEND["snap"]),
    "death": state(["death"], [], blend=BLEND["fall"]),
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
                       ("walk", f"{SPD} > 0.02")], blend=BLEND["settle"]),
        "walk": state(["idle", "walk"],
                      [("crouch", "query.is_sneaking"),
                       ("air", "!query.is_on_ground"),
                       ("sprint", "query.is_sprinting"),
                       ("run", f"{SPD} > 0.24"),
                       ("base", f"{SPD} <= 0.02")], blend=BLEND["cycle"]),
        # 走りは今まで生成だけされて誰も再生していなかった。歩→走→疾走の
        # 三段にすると、マントの角度が速度の目盛りとして読めるようになる。
        "run": state(["idle", "run"],
                     [("crouch", "query.is_sneaking"),
                      ("air", "!query.is_on_ground"),
                      ("sprint", "query.is_sprinting"),
                      ("walk", f"{SPD} <= 0.24")], blend=BLEND["cycle"]),
        "sprint": state(["idle", "sprint"],
                        [("air", "!query.is_on_ground"),
                         ("run", "!query.is_sprinting")], blend=BLEND["cycle"]),
        "crouch": state(["idle", "crouch"],
                        [("base", "!query.is_sneaking")], blend=BLEND["settle"]),
        "air": state(["idle", "air"],
                     [("swim", "query.is_in_water"),
                      ("base", "query.is_on_ground")], blend=BLEND["leap"]),
        "swim": state(["idle", "swim"],
                      [("base", "query.is_on_ground")], blend=BLEND["float"]),
    }
    if pose_anim:
        # 技の姿勢は全状態に重ねる。歩きながらでも技の形が崩れないよう、
        # 技クリップ側で override_previous_animation を立ててある前提。
        for st in states.values():
            st["animations"].append(pose_anim)
            st["blend_transition"] = BLEND["act"]
    controller(name, "base", states)


#  変身体は「技ごとに別アイテム」なので、コントローラも技ごとに要る。
for _c, _t, _g, _n in K.form_variants():
    form_controller(K.form_controller_name(_c, _t), "pose" if _t else None)


# --- 一人称 ------------------------------------------------------------------
#  act に idle を重ねない。重ねると field の回転式が二重に効いて、
#  一人称の生命線である「急停止」が平均化されて消える。
controller("fp.tech", "idle", {
    "idle": state(["idle"], [("act", "query.is_using_item")],
                  blend=BLEND["snap"]),
    "act": state(["act"], [("idle", "!query.is_using_item")], blend=0.16),
})

# --- マント（NPC 用に単体で回す）-----------------------------------------------
controller("cape", "still", {
    "still": state(["cape_idle"], [("moving", f"{SPD} > 0.02")], blend=0.30),
    "moving": state(["cape_move"], [("still", f"{SPD} <= 0.02")], blend=0.30),
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
