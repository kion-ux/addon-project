# -*- coding: utf-8 -*-
"""アニメーション一式。

回転の規則は hd_space（Mojang 公式サンプルから逆算した統合版の規則）に従う:
  rotation [rx, ry, rz] = Rz(-rz)·Ry(ry)·Rx(-rx)
  * 正の rx: 上端が前（-Z）へ倒れる／下へ垂れたもの（腕・脚）は後ろへ振れる
  * 負の rx: 垂れた腕が前へ上がる
  * 位置 position はモデル空間（+Z が後ろ）

■ 巨人（4 体型でボーン名は共通）
  体型ごとに脚や腰の高さが違うので、位置の値は pre_animation で体型（q.variant）から
  決めた変数 v.hip / v.knee / v.thigh を使う。大きい巨人ほど歩幅が広いので、
  脚の振りの位相は v.stride（= 1 / 拡大率）を掛けて遅くする。
  状態は entity property `aot:state`: idle / grab / eat / kneel / sleep / dying / leap /
  swat / blind
■ 調査兵団: 人型の歩き・走り・斬撃に、`aot:state` が fly（立体機動で飛ぶ）・
  slash（回転斬り）の時の全身姿勢
■ プレイヤー（playanimation で再生）: 刃の構え・飛行姿勢・回転斬り・うなじ斬り・掴まれ
■ アタッチャブル: 刃（右手と左手）、マント（走る・飛ぶと翻る）
"""
from __future__ import annotations

import math
import os

import aot_common as C
from aot_common import ATT_DIR, NS, RP, write_json, write_json_compact
from aot_models import BODIES, titan_metrics
from hd_holds import _mirror, _n, _single, fp_place, frame_x

ANIM_DIR = os.path.join(RP, "animations")
CTRL_DIR = os.path.join(RP, "animation_controllers")

LIMB = "q.modified_distance_moved * 38.17"
SPD = "q.modified_move_speed"
T = "q.anim_time"
STATE = "q.property('aot:state')"


def keys(**frames):
    """keys(t0=[..], t0_25=[..]) — アンダースコアは小数点。"""
    return {k.lstrip("t").replace("_", "."): v for k, v in frames.items()}


def kv(d):
    """{0.0: [..], 0.25: [..]} → 文字列キー。"""
    return {(f"{t:.3f}".rstrip("0").rstrip(".") if t else "0.0"): v for t, v in d.items()}


def clip(bones, length=None, loop=True):
    d = {"loop": loop, "bones": bones}
    if length:
        d["animation_length"] = length
    return d


def rot(x=0, y=0, z=0):
    return {"rotation": [x, y, z]}


def swing(amp, phase=0, limb=LIMB, scale=SPD):
    ph = f" + {phase}" if phase else ""
    return f"math.cos({limb}{ph}) * {amp} * {scale}"


def bob(amp, hz=62, phase=0):
    ph = f" + {phase}" if phase else ""
    return f"math.cos({T} * {hz}{ph}) * {amp}"


A = {}
CTRL = {}

# ===========================================================================
#  巨人
# ===========================================================================
TL = "(q.modified_distance_moved * 38.17 * (v.stride ?? 1.0))"     # 巨人の歩幅


def tswing(amp, phase=0):
    return swing(amp, phase, TL, f"math.min({SPD} * 1.4, 1.0)")


A["animation.aot.titan.look"] = clip({
    "head": rot("math.clamp(q.target_x_rotation, -40, 40) * 0.8",
                "math.clamp(q.target_y_rotation, -60, 60) * 0.8", 0),
    "neck": rot("math.clamp(q.target_x_rotation, -40, 40) * 0.2",
                "math.clamp(q.target_y_rotation, -60, 60) * 0.2", 0),
})

# 待機: 呼吸。口がゆっくり開いたり閉じたりし、首が傾ぐ（不気味さの大半はここ）
A["animation.aot.titan.idle"] = clip({
    "chest": rot(bob(1.2, 40), 0, bob(0.8, 23)),
    "head": rot(bob(2.0, 31, 40), bob(3.0, 13), f"6 * math.sin({T} * 17)"),
    "jaw": rot(f"4 + math.max(0, math.sin({T} * 25)) * 7", 0, 0),
    "rightArm": rot(bob(2.4, 35), 0, f"4 + {bob(1.4, 35)}"),
    "leftArm": rot(bob(2.4, 35, 180), 0, f"-4 - {bob(1.4, 35, 180)}"),
    "rightForearm": rot(f"-6 + {bob(2.0, 35, 60)}", 0, 0),
    "leftForearm": rot(f"-6 + {bob(2.0, 35, 240)}", 0, 0),
    "rightFingers": rot(f"10 + {bob(6, 21)}", 0, 0),
    "leftFingers": rot(f"10 + {bob(6, 21, 90)}", 0, 0),
})

# 歩き: 大股でゆっくり、体を左右に揺らし、腕はだらりと振る
A["animation.aot.titan.walk"] = clip({
    "body": {"rotation": [3, tswing(6), tswing(4)],
             "position": [0, f"math.abs({tswing(0.9)})", 0]},
    "chest": rot(4, tswing(5, 180), tswing(3, 180)),
    "head": rot(0, tswing(4), tswing(5)),
    "rightArm": rot(tswing(34), 0, 6),
    "leftArm": rot(tswing(34, 180), 0, -6),
    "rightForearm": rot(f"-10 - math.max(0, {tswing(20, 90)})", 0, 0),
    "leftForearm": rot(f"-10 - math.max(0, {tswing(20, 270)})", 0, 0),
    "rightLeg": rot(tswing(36, 180), 0, 0),
    "leftLeg": rot(tswing(36), 0, 0),
    "rightShin": rot(f"math.clamp({tswing(40, 250)}, 0, 70)", 0, 0),
    "leftShin": rot(f"math.clamp({tswing(40, 70)}, 0, 70)", 0, 0),
    "rightFoot": rot(tswing(14, 190), 0, 0),
    "leftFoot": rot(tswing(14, 10), 0, 0),
})

# 奇行種の全力疾走: 前のめりで腕を後ろへ流し、首を傾けたまま走る
A["animation.aot.titan.run"] = clip({
    "body": {"rotation": [24, tswing(8), 0], "position": [0, f"math.abs({tswing(1.4)})", 0]},
    "chest": rot(10, tswing(8, 180), 0),
    "neck": rot(-26, 0, 0),
    "head": rot(-10, 0, 24),
    "rightArm": rot(f"60 + {tswing(20)}", 0, 18),
    "leftArm": rot(f"60 + {tswing(20, 180)}", 0, -18),
    "rightForearm": rot(-10, 0, 0),
    "leftForearm": rot(-10, 0, 0),
    "rightLeg": rot(tswing(62, 180), 0, 0),
    "leftLeg": rot(tswing(62), 0, 0),
    "rightShin": rot(f"math.clamp({tswing(70, 250)}, 0, 100)", 0, 0),
    "leftShin": rot(f"math.clamp({tswing(70, 70)}, 0, 100)", 0, 0),
    "jaw": rot(f"16 + {bob(6, 120)}", 0, 0),
})

# 噛みつき（バニラの近接攻撃）: 前へ倒れ込み、両手を伸ばし、口を開けて閉じる
A["animation.aot.titan.attack"] = clip({
    "chest": {"rotation": keys(t0=[0, 0, 0], t0_25=[-6, 0, 0], t0_55=[34, 0, 0], t1_0=[0, 0, 0])},
    "neck": {"rotation": keys(t0=[0, 0, 0], t0_55=[-14, 0, 0], t1_0=[0, 0, 0])},
    "jaw": {"rotation": keys(t0=[0, 0, 0], t0_3=[34, 0, 0], t0_55=[34, 0, 0], t0_62=[0, 0, 0],
                             t1_0=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, 0], t0_3=[-70, 10, 0], t0_55=[-96, -8, 0],
                                  t1_0=[0, 0, 0])},
    "leftArm": {"rotation": keys(t0=[0, 0, 0], t0_3=[-70, -10, 0], t0_55=[-96, 8, 0],
                                 t1_0=[0, 0, 0])},
    "rightFingers": {"rotation": keys(t0=[0, 0, 0], t0_5=[10, 0, 0], t0_6=[70, 0, 0],
                                      t1_0=[0, 0, 0])},
    "leftFingers": {"rotation": keys(t0=[0, 0, 0], t0_5=[10, 0, 0], t0_6=[70, 0, 0],
                                     t1_0=[0, 0, 0])},
}, length=1.0, loop=False)

# 払い: 右腕を横に大きく振る（上半身の前に浮いた兵士を叩き落とす）
A["animation.aot.titan.swat"] = clip({
    "chest": {"rotation": keys(t0=[0, 0, 0], t0_25=[0, -40, 0], t0_5=[6, 50, 0], t0_9=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, 0], t0_25=[-100, -70, -20], t0_5=[-100, 70, -10],
                                  t0_9=[0, 0, 0])},
    "rightForearm": {"rotation": keys(t0=[0, 0, 0], t0_25=[-20, 0, 0], t0_5=[0, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_25=[0, -20, 0], t0_5=[0, 30, 0], t0_9=[0, 0, 0])},
}, length=0.9, loop=False)

# 掴み: 右手を前に伸ばして握り、胸の高さへ引き寄せたまま持つ
A["animation.aot.titan.grab"] = clip({
    "chest": rot(8, -10, 0),
    "rightArm": rot(-74, -14, 0),
    "rightForearm": rot(-34, 0, 0),
    "rightFingers": rot(72, 0, 0),
    "head": rot(14, -10, 0),
    "jaw": rot(f"10 + {bob(4, 90)}", 0, 0),
}, length=2.0)

# 食べる: 掴んだ手を口へ運び、顎を大きく開いて頭を少し反らす。
# 腕の角度は体型ごとに「手が口に届く」よう解いた値（v.eat_*、pre_animation で体型から選ぶ）
A["animation.aot.titan.eat"] = clip({
    "chest": rot(-4, -6, 0),
    "neck": rot(-6, 0, 0),
    "head": rot(-10, -6, 0),
    "jaw": {"rotation": [f"30 + math.sin({T} * 240) * 6", 0, 0]},
    "rightArm": rot("v.eat_x ?? -60", "v.eat_y ?? -45", "v.eat_z ?? 0"),
    "rightForearm": rot("v.eat_f ?? -110", 0, 0),
    "rightFingers": rot(72, 0, 0),
}, length=2.0)

# 膝をつく（腱を削がれた）: 両膝を地面に、上半身は前へ、片手を地につく
A["animation.aot.titan.kneel"] = clip({
    "body": {"rotation": [8, 0, 0], "position": [0, "-(v.knee ?? 15) + 1.5", 0]},
    "rightLeg": rot(-6, 0, 0),
    "leftLeg": rot(-6, 0, 0),
    "rightShin": rot(92, 0, 0),
    "leftShin": rot(92, 0, 0),
    "rightFoot": rot(-60, 0, 0),
    "leftFoot": rot(-60, 0, 0),
    "chest": rot(26, 0, 0),
    "neck": rot(-20, 0, 0),
    "head": rot(-10, 0, f"8 * math.sin({T} * 30)"),
    "rightArm": rot(-30, 0, 10),
    "leftArm": rot(-60, 0, -10),
    "leftForearm": rot(-10, 0, 0),
}, length=2.0)

# 夜: 座り込んで動かない（日光がないと動けない）
A["animation.aot.titan.sleep"] = clip({
    "body": {"rotation": [-6, 0, 0], "position": [0, "-(v.hip ?? 25) + (v.thigh ?? 4) * 0.5", 0]},
    "rightLeg": rot(-84, 6, 0),
    "leftLeg": rot(-84, -6, 0),
    "rightShin": rot(10, 0, 0),
    "leftShin": rot(10, 0, 0),
    "chest": rot(24, 0, 0),
    "neck": rot(16, 0, 0),
    "head": rot(f"18 + {bob(2, 18)}", 0, 12),
    "jaw": rot(12, 0, 0),
    "rightArm": rot(-28, 0, 14),
    "leftArm": rot(-28, 0, -14),
    "rightForearm": rot(-20, 0, 0),
    "leftForearm": rot(-20, 0, 0),
}, length=4.0)

# 討伐: 膝が抜け、前のめりにうつ伏せで倒れる（そのあと 4 秒蒸気を上げて消える）
A["animation.aot.titan.dying"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_45=[14, 0, 4], t1_3=[86, 0, 6]),
             "position": keys(t0=[0, 0, 0], t0_45=["-(v.hip ?? 25) * 0.18", 0, 0],
                              t1_3=[0, "-(v.hip ?? 25) * 0.86", 0])},
    "rightShin": {"rotation": keys(t0=[0, 0, 0], t0_45=[40, 0, 0], t1_3=[8, 0, 0])},
    "leftShin": {"rotation": keys(t0=[0, 0, 0], t0_45=[34, 0, 0], t1_3=[6, 0, 0])},
    "neck": {"rotation": keys(t0=[0, 0, 0], t0_45=[20, 0, 0], t1_3=[-30, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t1_3=[-20, 30, 0])},
    "jaw": {"rotation": keys(t0=[0, 0, 0], t1_3=[22, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, 0], t1_3=[-160, 0, 20])},
    "leftArm": {"rotation": keys(t0=[0, 0, 0], t1_3=[-20, 0, -30])},
}, length=1.3, loop="hold_on_last_frame")

# 奇行種の跳躍: 宙で体を丸め、手足を投げ出す
A["animation.aot.titan.leap"] = clip({
    "body": rot(30, 0, 0),
    "rightLeg": rot(-50, 0, 10),
    "leftLeg": rot(-30, 0, -10),
    "rightShin": rot(70, 0, 0),
    "leftShin": rot(60, 0, 0),
    "rightArm": rot(-150, 0, 30),
    "leftArm": rot(-150, 0, -30),
    "neck": rot(-30, 0, 0),
    "jaw": rot(28, 0, 0),
}, length=1.0)

# 目を潰された: 両手で目を覆ってよろめく（手が目に届く角度を体型ごとに解いてある）
A["animation.aot.titan.blind"] = clip({
    "chest": rot(f"10 + {bob(3, 60)}", 0, bob(5, 40)),
    "head": rot(4, f"{bob(10, 90)}", 0),
    "rightArm": rot("v.bl_x ?? -100", "v.bl_y ?? -50", "v.bl_z ?? 6"),
    "leftArm": rot("v.bl_x ?? -100", "-(v.bl_y ?? -50)", "-(v.bl_z ?? 6)"),
    "rightForearm": rot("v.bl_f ?? -100", 0, 0),
    "leftForearm": rot("v.bl_f ?? -100", 0, 0),
    "jaw": rot(f"20 + {bob(8, 120)}", 0, 0),
}, length=2.0)

A["animation.aot.titan.hurt"] = clip({
    "chest": {"rotation": keys(t0=[0, 0, 0], t0_1=[-10, 0, 6], t0_4=[0, 0, 0])},
    "head": {"rotation": keys(t0=[0, 0, 0], t0_1=[14, 0, -8], t0_4=[0, 0, 0])},
}, length=0.4, loop=False)

# 体力が尽きた（うなじ以外で倒された）時もうつ伏せに
A["animation.aot.titan.death"] = A["animation.aot.titan.dying"]


def tstate(name, expr):
    return {name: f"{STATE} == '{expr}'"}


CTRL["controller.animation.aot.titan.general"] = {
    "initial_state": "stand",
    "states": {
        "stand": {"animations": ["look", "idle"], "blend_transition": 0.3, "transitions": [
            {"dying": f"{STATE} == 'dying' || q.health <= 0"},
            {"sleep": f"{STATE} == 'sleep'"}, {"kneel": f"{STATE} == 'kneel'"},
            {"grab": f"{STATE} == 'grab'"}, {"eat": f"{STATE} == 'eat'"},
            {"leap": f"{STATE} == 'leap'"}, {"blind": f"{STATE} == 'blind'"},
            {"run": "q.modified_move_speed > 0.02 && (v.runner ?? 0) > 0.5"},
            {"walk": "q.modified_move_speed > 0.02"}]},
        "walk": {"animations": ["look", "idle", "walk"], "blend_transition": 0.3, "transitions": [
            {"dying": f"{STATE} == 'dying' || q.health <= 0"},
            {"sleep": f"{STATE} == 'sleep'"}, {"kneel": f"{STATE} == 'kneel'"},
            {"grab": f"{STATE} == 'grab'"}, {"eat": f"{STATE} == 'eat'"},
            {"leap": f"{STATE} == 'leap'"}, {"blind": f"{STATE} == 'blind'"},
            {"run": "(v.runner ?? 0) > 0.5 && q.modified_move_speed > 0.4"},
            {"stand": "q.modified_move_speed <= 0.02"}]},
        "run": {"animations": ["run"], "blend_transition": 0.25, "transitions": [
            {"dying": f"{STATE} == 'dying' || q.health <= 0"},
            {"leap": f"{STATE} == 'leap'"}, {"kneel": f"{STATE} == 'kneel'"},
            {"grab": f"{STATE} == 'grab'"}, {"eat": f"{STATE} == 'eat'"},
            {"blind": f"{STATE} == 'blind'"}, {"sleep": f"{STATE} == 'sleep'"},
            {"walk": "q.modified_move_speed <= 0.4"}]},
    },
}
for st in ("sleep", "kneel", "grab", "eat", "leap", "blind"):
    anims = [st] if st in ("sleep", "kneel", "leap") else ["walk", st]
    CTRL["controller.animation.aot.titan.general"]["states"][st] = {
        "animations": anims, "blend_transition": 0.35,
        "transitions": [{"dying": f"{STATE} == 'dying' || q.health <= 0"},
                        {"stand": f"{STATE} != '{st}'"}]}
CTRL["controller.animation.aot.titan.general"]["states"]["dying"] = {
    "animations": ["dying"], "blend_transition": 0.2, "transitions": []}

CTRL["controller.animation.aot.titan.action"] = {
    "initial_state": "idle",
    "states": {
        "idle": {"transitions": [
            {"swat": f"{STATE} == 'swat'"},
            {"attack": f"q.is_delayed_attacking && {STATE} == 'idle' && q.health > 0"}]},
        "attack": {"animations": ["attack"], "blend_transition": 0.12,
                   "transitions": [{"idle": "q.all_animations_finished || q.health <= 0"}]},
        "swat": {"animations": ["swat"], "blend_transition": 0.1,
                 "transitions": [{"idle": "q.all_animations_finished || q.health <= 0"}]},
    },
}


def solve_hand(body, target_fn, chest=(0, 0, 0), side=-1):
    """手（掌の中心）が target に届く右腕の角度 (rx, ry, rz) と前腕の曲げ。
    hd_space の規則で胸→肩→肘を組み、座標降下で探す。"""
    import numpy as np
    from hd_space import bone_local
    from rig import landmarks
    from aot_models import TITAN_BUILDS
    spec = TITAN_BUILDS[body]
    L = landmarks(spec["build"])
    cx = side * (L.shoulder_w / 2 - L.arm_t / 2)
    chest_p = (0, L.chest_bot, 0)
    arm_p = (cx, L.shoulder_y - L.arm_t * 0.35, 0)
    fore_p = (cx, L.elbow_y, 0)
    hand = np.array([cx, L.wrist_y - L.hand_l * 0.6, -L.forearm_t * 0.6, 1.0])
    stoop = spec.get("stoop", 0)
    target = np.array(target_fn(L))

    def at(r):
        M = (bone_local(chest_p, (chest[0] + stoop, chest[1], chest[2])) @ bone_local(arm_p, r[:3])
             @ bone_local(fore_p, (r[3], 0, 0)))
        return (M @ hand)[:3]
    r = np.array([-90.0, 0.0, 0.0, -60.0])
    best = float(np.sum((at(r) - target) ** 2))
    step = 20.0
    while step > 0.1:
        improved = False
        for i in range(4):
            for sg in (-1, 1):
                q = r.copy()
                q[i] += sg * step
                if q[3] > 5:
                    continue
                e = float(np.sum((at(q) - target) ** 2)) + 0.0005 * q[2] ** 2
                if e < best:
                    r, best, improved = q, e, True
        if not improved:
            step *= 0.5
    return [round(float(x), 1) for x in r]


def hand_angles():
    out = []
    for b in BODIES:
        eat = solve_hand(b, lambda L: (0, L.chin + L.head_h * 0.28, -L.head_d * 0.62), chest=(-4, -6, 0))
        blind = solve_hand(b, lambda L: (-L.head_w * 0.22, L.chin + L.head_h * 0.58, -L.head_d * 0.62),
                           chest=(10, 0, 0))
        out.append({"eat_x": eat[0], "eat_y": eat[1], "eat_z": eat[2], "eat_f": eat[3],
                    "bl_x": blind[0], "bl_y": blind[1], "bl_z": blind[2], "bl_f": blind[3]})
    return out


_HANDS = None


def titan_pre_animation(scale: float, runner: bool) -> list:
    """クライアント定義の pre_animation: 体型（q.variant）ごとの寸法と手の角度、拡大率から歩幅。"""
    global _HANDS
    if _HANDS is None:
        _HANDS = hand_angles()
    ms = [dict(titan_metrics(b), **_HANDS[i]) for i, b in enumerate(BODIES)]

    def pick(key):
        e = f"{ms[-1][key]:.2f}"
        for i in range(len(ms) - 2, -1, -1):
            e = f"(q.variant == {i} ? {ms[i][key]:.2f} : {e})"
        return e
    out = [f"v.hip = {pick('hip')};", f"v.knee = {pick('knee')};",
           f"v.thigh = {pick('thigh')};", f"v.stride = {1.0 / scale:.3f};",
           f"v.runner = {1 if runner else 0};"]
    for k in ("eat_x", "eat_y", "eat_z", "eat_f", "bl_x", "bl_y", "bl_z", "bl_f"):
        out.append(f"v.{k} = {pick(k)};")
    return out


# ===========================================================================
#  調査兵団（NPC）
# ===========================================================================
A["animation.aot.human.look"] = clip({
    "head": rot("math.clamp(q.target_x_rotation, -42, 42)",
                "math.clamp(q.target_y_rotation, -68, 68)", 0),
})
A["animation.aot.human.idle"] = clip({
    "body": {"rotation": [bob(0.6), 0, bob(0.4, 31)]},
    "chest": rot(bob(0.8, 62, 40), 0, 0),
    "rightArm": rot(f"-24 + {bob(2.0, 58)}", 0, f"-6 - {bob(1.0, 58)}"),
    "leftArm": rot(f"-24 + {bob(2.0, 58, 180)}", 0, f"6 + {bob(1.0, 58, 180)}"),
    "rightForearm": rot(f"-30 + {bob(1.4, 58, 40)}", 0, 0),
    "leftForearm": rot(f"-30 + {bob(1.4, 58, 220)}", 0, 0),
    "cloak": rot(f"{bob(2, 40)}", 0, 0),
})
A["animation.aot.human.walk"] = clip({
    "body": {"rotation": [2, 0, swing(1.6)], "position": [0, swing(0.30, 0), 0]},
    "chest": rot(0, swing(3.2, 180), 0),
    "rightArm": rot(f"-16 + {swing(28)}", 0, -6),
    "leftArm": rot(f"-16 + {swing(28, 180)}", 0, 6),
    "rightLeg": rot(swing(46, 180), 0, 0),
    "leftLeg": rot(swing(46), 0, 0),
    "rightShin": rot(f"math.clamp({swing(40, 250)}, 0, 62)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(40, 70)}, 0, 62)", 0, 0),
    "cloak": rot(f"6 + {SPD} * 22", 0, 0),
    "cloak_low": rot(f"{SPD} * 10 + {swing(4)}", 0, 0),
})
A["animation.aot.human.run"] = clip({
    "body": {"rotation": [14, 0, swing(2.4)], "position": [0, swing(0.5, 0), 0]},
    "chest": rot(4, swing(6.0, 180), 0),
    "head": rot(-12, 0, 0),
    "rightArm": rot(f"40 + {swing(30)}", 0, -14),
    "leftArm": rot(f"40 + {swing(30, 180)}", 0, 14),
    "rightForearm": rot(-30, 0, 0),
    "leftForearm": rot(-30, 0, 0),
    "rightLeg": rot(swing(62, 180), 0, 0),
    "leftLeg": rot(swing(62), 0, 0),
    "rightShin": rot(f"math.clamp({swing(66, 250)}, 0, 92)", 0, 0),
    "leftShin": rot(f"math.clamp({swing(66, 70)}, 0, 92)", 0, 0),
    "cloak": rot(f"20 + {SPD} * 20", 0, 0),
    "cloak_low": rot(f"16 + {swing(6)}", 0, 0),
})
# 二刀の斬撃（近接攻撃）: 右で袈裟、左で逆袈裟
A["animation.aot.human.attack"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_12=[-4, 26, 0], t0_3=[8, -26, 0], t0_5=[0, 0, 0])},
    "rightArm": {"rotation": keys(t0=[0, 0, 0], t0_12=[-150, -20, -10], t0_3=[20, 30, 10],
                                  t0_5=[0, 0, 0])},
    "leftArm": {"rotation": keys(t0=[0, 0, 0], t0_2=[-130, 20, 10], t0_4=[10, -30, -10],
                                 t0_5=[0, 0, 0])},
}, length=0.5, loop=False)
A["animation.aot.human.hurt"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_08=[-14, 0, 6], t0_3=[0, 0, 0])},
}, length=0.3, loop=False)
A["animation.aot.human.death"] = clip({
    "body": {"rotation": keys(t0=[0, 0, 0], t0_35=[-24, 0, 0], t1_2=[0, 0, 88]),
             "position": keys(t0=[0, 0, 0], t1_2=[0, -7, 0])},
}, length=1.2, loop="hold_on_last_frame")
# 立体機動で飛ぶ: 体を前へ倒して脚を揃え、刃を後ろへ流す。マントが大きく翻る
A["animation.aot.human.fly"] = clip({
    "body": rot(f"62 + {bob(4, 120)}", 0, bob(6, 70)),
    "head": rot(-50, 0, 0),
    "rightArm": rot(48, 10, -26),
    "leftArm": rot(48, -10, 26),
    "rightForearm": rot(-10, 0, 0),
    "leftForearm": rot(-10, 0, 0),
    "rightLeg": rot(10, 0, 4),
    "leftLeg": rot(24, 0, -4),
    "rightShin": rot(26, 0, 0),
    "leftShin": rot(40, 0, 0),
    "cloak": rot(f"70 + {bob(10, 400)}", 0, 0),
    "cloak_low": rot(f"20 + {bob(14, 400, 60)}", 0, 0),
})
# 回転斬り: うなじの手前で体ごと 2 回転しながら両手の刃を振り抜く
A["animation.aot.human.slash"] = clip({
    "body": {"rotation": keys(t0=[50, 0, 0], t0_5=[40, 720, 0])},
    "rightArm": rot(-90, 0, -70),
    "leftArm": rot(-90, 0, 70),
    "cloak": rot(80, 0, 0),
}, length=0.5, loop=False)
A["animation.aot.human.ponytail"] = clip({
    "tail0": rot(f"14 + {SPD} * 20 + {bob(4, 80)}", 0, bob(5, 50)),
    "tail1": rot(f"6 + {bob(6, 80, 40)}", 0, 0),
    "tail2": rot(f"4 + {bob(6, 80, 80)}", 0, 0),
})
A["animation.aot.human.scarf"] = clip({
    "scarf_tail": rot(f"-8 - {SPD} * 30 + {bob(4, 90)}", 0, 6),
})

CTRL["controller.animation.aot.human.general"] = {
    "initial_state": "stand",
    "states": {
        "stand": {"animations": ["look", "idle"], "blend_transition": 0.2, "transitions": [
            {"fly": f"{STATE} == 'fly'"}, {"walk": "q.modified_move_speed > 0.02"},
            {"death": "q.health <= 0"}]},
        "walk": {"animations": ["look", "walk"], "blend_transition": 0.15, "transitions": [
            {"fly": f"{STATE} == 'fly'"}, {"run": "q.modified_move_speed > 0.7"},
            {"stand": "q.modified_move_speed <= 0.02"}, {"death": "q.health <= 0"}]},
        "run": {"animations": ["look", "run"], "blend_transition": 0.15, "transitions": [
            {"fly": f"{STATE} == 'fly'"}, {"walk": "q.modified_move_speed <= 0.7"},
            {"death": "q.health <= 0"}]},
        "fly": {"animations": ["fly"], "blend_transition": 0.18, "transitions": [
            {"stand": f"{STATE} != 'fly'"}, {"death": "q.health <= 0"}]},
        "death": {"animations": ["death"], "blend_transition": 0.2},
    },
}
CTRL["controller.animation.aot.human.action"] = {
    "initial_state": "idle",
    "states": {
        "idle": {"transitions": [
            {"slash": f"{STATE} == 'slash'"},
            {"attack": "q.is_delayed_attacking && q.health > 0"}]},
        "attack": {"animations": ["attack"], "blend_transition": 0.06,
                   "transitions": [{"idle": "q.all_animations_finished || q.health <= 0"}]},
        "slash": {"animations": ["slash"], "blend_transition": 0.05,
                  "transitions": [{"idle": f"q.all_animations_finished || {STATE} != 'slash'"}]},
    },
}


# ===========================================================================
#  刃（アタッチャブル）の持ち方 — hd_holds の規則で「握りが拳に来る」よう逆算
# ===========================================================================
GRIP = (0.0, -0.3, 0.0)        # 刃の握りの中心（武器空間）
BLADE_SCALE = 0.84


def blade_holds():
    s = BLADE_SCALE
    fwd_r = _n((-0.20, -0.36, -0.91))
    up = (0, 1, 0.25)
    arm_r, ir, ip = _single((-7.4, 12.6, -5.0), fwd_r, up, GRIP, s)
    arm_l, irl, ipl = _single((7.4, 12.6, -5.0), _mirror(fwd_r), up, GRIP, s, left=True)
    fp = fp_place(frame_x(_n((-0.46, 0.58, 0.67)), (0.2, 0.1, -1)), (10.5, -9.5, 14.0), GRIP, 0.62)
    return {"arm_r": arm_r, "arm_l": arm_l,
            "tp": {"rotation": ir, "position": ip, "scale": s},
            "left_tp": {"rotation": irl, "position": ipl, "scale": s},
            "fp": fp}


def spear_hold():
    s = 0.62
    arm, ir, ip = _single((-7.2, 13.0, -4.6), _n((-0.08, -0.10, -0.99)), (0, 1, 0), (0, -1.3, -0.5), s)
    fp = fp_place(frame_x(_n((-0.30, 0.30, 0.90)), (0.2, 0.1, -1)), (10.0, -9.0, 14.0),
                  (0, -1.3, -0.5), 0.6)
    return {"arm_r": arm, "tp": {"rotation": ir, "position": ip, "scale": s}, "fp": fp}


def r2(v):
    return [round(float(x), 2) for x in v]


def tf(d):
    return {"rotation": r2(d["rotation"]), "position": r2(d["position"]),
            "scale": round(float(d.get("scale", 1.0)), 3)}


SW1 = "math.sin(v.aot_sw * 180.0)"
SW2 = "math.sin(v.aot_sw * 360.0)"


def item_anims():
    H = blade_holds()
    S = spear_hold()
    out = {}
    out["animation.aot.blades.tp"] = clip({"hold": tf(H["tp"]), "hold_l": tf(H["left_tp"])})
    out["animation.aot.blades.fp"] = clip({"hold": tf(H["fp"]), "hold_l": {"scale": 0.0}})
    # 振り: 手首の返し（体の大きな振りはバニラ／全身モーション）
    out["animation.aot.blades.swing"] = clip({
        "root": rot(f"-{SW1} * 26.0", f"{SW2} * 14.0", 0),
        "left": rot(f"-{SW1} * 26.0", f"-{SW2} * 14.0", 0),
    })
    out["animation.aot.blades.idle"] = clip({
        "root": {"position": [0, "math.sin(q.anim_time * 90.0) * 0.1", 0]},
        "left": {"position": [0, "math.sin(q.anim_time * 90.0 + 60.0) * 0.1", 0]},
    }, length=4.0)
    out["animation.aot.spear.tp"] = clip({"hold": tf(S["tp"])})
    out["animation.aot.spear.fp"] = clip({"hold": tf(S["fp"])})
    # マント（上着のアタッチャブル）: 走ると後ろへ流れ、空中では大きく翻る
    out["animation.aot.cloak.flutter"] = clip({
        "cloak": rot(f"7 + math.min(q.modified_move_speed, 1.0) * 26 + (q.is_on_ground ? 0 : "
                     f"32 + math.sin(q.anim_time * 520) * 8)", 0, 0),
        "cloak_low": rot(f"math.min(q.modified_move_speed, 1.0) * 14 + (q.is_on_ground ? "
                         f"math.sin(q.anim_time * 140) * 2 : 18 + math.sin(q.anim_time * 520 + 70) * 12)",
                         0, 0),
    })
    return out, H, S


def blades_attachable():
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": f"{NS}:odm_blades",
                "materials": {"default": "entity_alphatest", "enchanted": "entity_alphatest_glint"},
                "textures": {"default": "textures/entity/aot/blades",
                             "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": "geometry.aot.blades"},
                "animations": {
                    "tp": "animation.aot.blades.tp", "fp": "animation.aot.blades.fp",
                    "idle": "animation.aot.blades.idle", "swing": "animation.aot.blades.swing"},
                "scripts": {
                    "pre_animation": [
                        "v.aot_sw = math.clamp(c.owning_entity->v.attack_time, 0.0, 1.0);",
                        "v.aot_fp = c.is_first_person ? 1.0 : 0.0;"],
                    "animate": [{"tp": "1.0 - v.aot_fp"}, {"fp": "v.aot_fp"}, "idle",
                                {"swing": "v.aot_sw > 0.0"}]},
                "render_controllers": ["controller.render.item_default"],
            }
        }
    }


def spear_attachable():
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": f"{NS}:thunder_spear",
                "materials": {"default": "entity_alphatest", "enchanted": "entity_alphatest_glint"},
                "textures": {"default": "textures/entity/aot/thunder_spear",
                             "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": "geometry.aot.thunder_spear"},
                "animations": {"tp": "animation.aot.spear.tp", "fp": "animation.aot.spear.fp"},
                "scripts": {"pre_animation": ["v.aot_fp = c.is_first_person ? 1.0 : 0.0;"],
                            "animate": [{"tp": "1.0 - v.aot_fp"}, {"fp": "v.aot_fp"}]},
                "render_controllers": ["controller.render.item_default"],
            }
        }
    }


def wear_attachable(item, geo, tex, cloak_anim=False):
    desc = {
        "identifier": f"{NS}:{item}",
        "materials": {"default": "entity_alphatest", "enchanted": "entity_alphatest_glint"},
        "textures": {"default": f"textures/entity/aot/{tex}",
                     "enchanted": "textures/misc/enchanted_item_glint"},
        "geometry": {"default": geo},
        "scripts": {"parent_setup": "variable.chest_layer_visible = 0.0; "
                                    "variable.leg_layer_visible = 0.0; "
                                    "variable.boot_layer_visible = 0.0;"},
        "render_controllers": ["controller.render.aot.attachable"],
    }
    if cloak_anim:
        desc["animations"] = {"flutter": "animation.aot.cloak.flutter"}
        desc["scripts"]["animate"] = ["flutter"]
    return {"format_version": "1.10.0", "minecraft:attachable": {"description": desc}}


# ===========================================================================
#  プレイヤーの全身モーション（playanimation）
# ===========================================================================
BONES = {"rA": "rightArm", "lA": "leftArm", "b": "body", "h": "head", "rL": "rightLeg",
         "lL": "leftLeg", "root": "root"}
ARMS = ("rA", "lA")
FPK = 0.25
_ATK = "math.sin((1.0 - math.pow(1.0 - v.attack_time, 4.0)) * 180.0)"
ATK_CANCEL = {
    ("rA", 0): f"({_ATK} * 1.2 + math.sin(v.attack_time * 180.0)) * 30.0",
    ("rA", 1): f"({_ATK} != 0.0 ? 30.0 - 90.0 * {_ATK} : 0.0)",
    ("lA", 0): f"({_ATK} * 1.2 + math.sin(v.attack_time * 180.0)) * 10.0",
    ("b", 1): "-math.sin(360.0 * math.sqrt(v.attack_time)) * 5.0",
}
HOLD_CANCEL = {
    ("rA", 0): "18.0 + 0.375 * (v.tcos0 ?? 0.0)",
    ("lA", 0): "-0.75 * (v.tcos0 ?? 0.0)",
}


def num(x):
    return f"{x:.2f}".rstrip("0").rstrip(".") if abs(x) > 1e-6 else "0"


def chan(bone, axis, value, kind):
    if kind == "hold":
        extra = HOLD_CANCEL.get((bone, axis))
        tp = num(value) + (f" + {extra}" if extra else "")
        if extra or abs(value) > 1e-6:
            return f"v.is_first_person ? 0.0 : ({tp})"
        return 0
    extra = ATK_CANCEL.get((bone, axis)) if kind == "act" else None
    if abs(value) < 1e-6 and not extra:
        return 0
    tp = num(value) + (f" + {extra}" if extra else "")
    if bone in ARMS:
        return f"v.is_first_person ? {num(value * FPK)} : ({tp})"
    return f"v.is_first_person ? 0.0 : ({tp})"


def build_body(length, frames, hold, kind="act", loop=False):
    """frames: {t: {key: (x,y,z)}}。書いていない部位は持ち姿勢のまま。
    出力は持ち姿勢からの差分（kind='hold' なら絶対値）。"""
    keys_ = set(hold)
    for f in frames.values():
        keys_ |= set(f)
    bones = {}
    for key in sorted(keys_):
        is_pos = key.endswith("_pos")
        bk = key[:-4] if is_pos else key
        bone = BONES[bk]
        track = {}
        for t in sorted(frames, key=float):
            base = hold.get(key, (0, 0, 0))
            val = frames[t].get(key, base)
            delta = [val[i] - (0 if kind == "hold" else base[i]) for i in range(3)]
            if is_pos:
                v = [f"v.is_first_person ? 0.0 : {num(d)}" if abs(d) > 1e-6 else 0 for d in delta]
            else:
                v = [chan(bk, i, delta[i], kind) for i in range(3)]
            ts = f"{float(t):.3f}".rstrip("0").rstrip(".") if float(t) else "0.0"
            track[ts] = {"post": v, "lerp_mode": "catmullrom"}
        bones.setdefault(bone, {})["position" if is_pos else "rotation"] = track
    return {"loop": loop, "animation_length": length, "bones": bones}


def pitch_root(th, centre=14.0):
    """root を重心（高さ centre）まわりに前へ th 度倒す姿勢（位置の打ち消し込み）。"""
    r = math.radians(th)
    return {"root": (th, 0, 0), "root_pos": (0, centre * (1 - math.cos(r)), centre * math.sin(r))}


def spin_root(deg, centre=14.0, tilt=0.0):
    r = math.radians(tilt)
    return {"root": (tilt, deg, 0), "root_pos": (0, centre * (1 - math.cos(r)), centre * math.sin(r))}


def player_anims(H, S):
    P = {}
    n = "animation.aot.p."
    hold = {"rA": tuple(H["arm_r"]), "lA": tuple(H["arm_l"]), "b": (3, 0, 0)}
    P[f"{n}hold"] = build_body(2.0, {0: {}, 1.0: {"b": (3.8, 0, 0)}, 2.0: {}}, hold, "hold", True)
    shold = {"rA": tuple(S["arm_r"]), "lA": (-10, 0, 0)}
    P[f"{n}hold_spear"] = build_body(2.0, {0: {}, 2.0: {}}, shold, "hold", True)
    # 飛行姿勢: 体を前へ 58° 倒し、脚を揃え、刃を後ろへ流す。頭は前を見る
    fly = dict(pitch_root(58))
    fly.update({"h": (-48, 0, 0), "rA": (52, 14, 24), "lA": (52, -14, -24),
                "rL": (12, 0, 3), "lL": (26, 0, -3)})
    fly2 = dict(pitch_root(62))
    fly2.update({"h": (-52, 0, 0), "rA": (58, 16, 28), "lA": (56, -16, -28),
                 "rL": (16, 0, 3), "lL": (30, 0, -3)})
    P[f"{n}fly"] = build_body(0.8, {0: fly, 0.4: fly2, 0.8: fly}, hold, "move", True)
    # 回転斬り: 体ごと 2 回転しながら両腕を広げて振り抜く
    frames = {}
    for i in range(11):
        t = i / 10
        e = 0.5 - 0.5 * math.cos(math.pi * t)
        p = spin_root(720 * e, tilt=40 * math.sin(math.pi * t))
        p.update({"rA": (-90, 0, -80), "lA": (-90, 0, 80), "rL": (-30, 0, 0), "lL": (-50, 0, 0)})
        frames[round(0.5 * t, 3)] = p
    P[f"{n}spin"] = build_body(0.5, frames, hold, "act")
    # うなじ斬り: 両手を頭上に振りかぶり、交差させて斬り下ろす
    P[f"{n}slash"] = build_body(0.4, {
        0: {},
        0.1: {"rA": (-170, -20, -10), "lA": (-170, 20, 10), "b": (-10, 0, 0)},
        0.22: {"rA": (-20, 30, 10), "lA": (-20, -30, -10), "b": (24, 0, 0)},
        0.4: {}}, hold, "act")
    # ガス噴射: 一瞬前へ突っ込む
    boost = dict(pitch_root(40))
    boost.update({"rA": (60, 0, 20), "lA": (60, 0, -20), "rL": (20, 0, 0), "lL": (30, 0, 0)})
    P[f"{n}boost"] = build_body(0.35, {0: {}, 0.1: boost, 0.35: {}}, hold, "move")
    # 掴まれた: 腕を体に押し付けられ、脚が宙に揺れる
    P[f"{n}grabbed"] = build_body(1.0, {
        0: {"rA": (-6, 0, -6), "lA": (-6, 0, 6), "rL": (-10, 0, 0), "lL": (14, 0, 0)},
        0.5: {"rA": (-10, 0, -8), "lA": (-4, 0, 8), "rL": (16, 0, 0), "lL": (-12, 0, 0)},
        1.0: {"rA": (-6, 0, -6), "lA": (-6, 0, 6), "rL": (-10, 0, 0), "lL": (14, 0, 0)}},
        hold, "move", True)
    # 刃の交換: 腰の収納箱へ手を下ろして差し替える
    P[f"{n}reload"] = build_body(0.5, {
        0: {}, 0.2: {"rA": (20, 0, -20), "lA": (20, 0, 20)}, 0.5: {}}, hold, "act")
    # 雷槍の発射: 腕を伸ばして反動
    P[f"{n}fire"] = build_body(0.4, {
        0: {}, 0.05: {"rA": (-92, -4, 0)}, 0.14: {"rA": (-110, -4, 0), "b": (-6, 0, 0)}, 0.4: {}},
        shold, "act")
    P[f"{n}none"] = {"loop": False, "animation_length": 0.05, "bones": {}}
    return P


def script_meta(P):
    import json
    meta = {k[len("animation.aot.p."):]: round(v.get("animation_length", 0.05), 3)
            for k, v in P.items()}
    path = os.path.join(C.BP, "scripts", "anim_meta.js")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("// 自動生成（tools/aot/gen_aot_anim.py）。プレイヤーの全身モーションの長さ（秒）\n")
        fh.write("export const ANIM_META = ")
        json.dump(meta, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")


def main() -> None:
    items, H, S = item_anims()
    A.update(items)
    P = player_anims(H, S)
    write_json(os.path.join(ANIM_DIR, "aot_entities.animation.json"),
               {"format_version": "1.10.0", "animations": A})
    write_json_compact(os.path.join(ANIM_DIR, "aot_player.animation.json"),
                       {"format_version": "1.10.0", "animations": P})
    write_json(os.path.join(CTRL_DIR, "aot.animation_controllers.json"),
               {"format_version": "1.10.0", "animation_controllers": CTRL})
    write_json(os.path.join(ATT_DIR, "odm_blades.attachable.json"), blades_attachable())
    write_json(os.path.join(ATT_DIR, "thunder_spear.attachable.json"), spear_attachable())
    write_json(os.path.join(ATT_DIR, "survey_jacket.attachable.json"),
               wear_attachable("survey_jacket", "geometry.aot.wear_jacket", "wear_jacket", True))
    write_json(os.path.join(ATT_DIR, "odm_gear.attachable.json"),
               wear_attachable("odm_gear", "geometry.aot.wear_odm_gear", "wear_odm_gear"))
    write_json(os.path.join(ATT_DIR, "survey_boots.attachable.json"),
               wear_attachable("survey_boots", "geometry.aot.wear_boots", "wear_boots"))
    script_meta(P)
    print(f"  animations: {len(A)} entity/item, {len(P)} player, controllers: {len(CTRL)}")
    print(f"  blade hold: arm_r={H['arm_r']} arm_l={H['arm_l']}")


if __name__ == "__main__":
    main()
