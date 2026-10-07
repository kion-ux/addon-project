# -*- coding: utf-8 -*-
"""アニメーション一式。

1. 武器側（アタッチャブル）
   * 三人称 / 一人称の持ち位置
   * 常時動く部品: 大剣の次元環の回転、房飾りの揺れ、盾の核の脈動、鞭のとぐろ
   * 振り: v.attack_time（0→1）をそのまま関数に通す。キーフレームの再生タイミングに
     依存しないので、連打しても振りが途切れない
   * 使用中（右クリック保持）: 弓の引き絞り（リムが撓み、弦が下がり、光の矢が出る）、
     盾のガード、鞭のしなり、近接武器の溜め構え
2. プレイヤーの全身モーション（スクリプトから playanimation で再生）
   * 連撃・戦技・空中技・必殺技・機動（二段ジャンプの宙返り、回避、着地）
   * 腕の回転は一人称では 25% に抑える（画面から腕が飛び出さないように）

座標の規約: アニメーションの position はジオメトリと同じ向き（+Z = 後方）、
rotation は X/Y が右手系に対して反転（Blockbench の bedrock 書き出しと同じ）。
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hd_common import NS, RP, WEAPONS, write_json  # noqa: E402
from gen_hd_weapons import STRING_TIP, WHIP_LEN, WHIP_SEGS  # noqa: E402

ANIM_DIR = os.path.join(RP, "animations")
ATT_DIR = os.path.join(RP, "attachables")

# ===========================================================================
#  1. 武器の持ち方
#  tp/fp = (position, rotation, scale)。実機で手元がずれる場合はここだけ直せばよい
# ===========================================================================
WIELD = {
    "greatsword": {"tp": ([0, 0, 0], [-18, 0, 0], 0.72), "fp": ([0, 0, 0], [-8, 0, 0], 0.55)},
    "twinblades": {"tp": ([0, 0, 0], [-12, 0, 0], 0.78), "fp": ([0, 0, 0], [-6, 0, 0], 0.66)},
    "greataxe":   {"tp": ([0, 0, 2], [-22, 0, 0], 0.70), "fp": ([0, 0, 2], [-10, 0, 0], 0.52)},
    "dagger":     {"tp": ([0, 0, 0], [10, 180, 0], 0.66), "fp": ([0, 0, 0], [0, 180, 0], 0.62)},
    "bow":        {"tp": ([0, 2, 0], [0, 0, 0], 0.62), "fp": ([0, 1, 0], [0, 0, 0], 0.5)},
    "shield":     {"tp": ([-1, 4, 0], [0, -90, 0], 0.72), "fp": ([0, 3, 0], [0, -70, 0], 0.6)},
    "whip":       {"tp": ([0, 0, 0], [0, 0, 0], 0.80), "fp": ([0, 0, 0], [-10, 0, 0], 0.7)},
    "claws":      {"tp": ([0, 0, 0], [0, 0, 0], 1.00), "fp": ([0, 0, 0], [0, 0, 0], 0.9)},
}

# 振りの型（v.hd_sw = 0→1 の関数として書く）
SWING = {
    "greatsword": "heavy", "greataxe": "heavy", "twinblades": "slash",
    "dagger": "stab", "bow": "none", "shield": "bash", "whip": "whip", "claws": "none",
}

PRE = [
    "v.hd_sw = math.clamp(v.attack_time ?? 0.0, 0.0, 1.0);",
    "v.hd_use = q.is_using_item ? 1.0 : 0.0;",
    # 弓: 引き始めてから 1 秒で最大まで引き絞る（バニラの弓と同じ数え方）
    "v.hd_draw = q.is_using_item ? math.clamp((q.main_hand_item_max_duration - "
    "q.main_hand_item_use_duration) / 20.0, 0.0, 1.0) : 0.0;",
]


def r2(v):
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return v


def vec(*xs):
    return [r2(x) for x in xs]


def weapon_anims() -> dict:
    A = {}
    for name, w in WIELD.items():
        base = f"animation.{NS}.{name}"
        (tp, tr, ts), (fp, fr, fs) = w["tp"], w["fp"]
        tp_bones = {"root": {"position": tp, "rotation": tr, "scale": ts}}
        fp_bones = {"root": {"position": fp, "rotation": fr, "scale": fs}}
        if name in ("twinblades", "claws"):
            tp_bones["left"] = {"position": tp, "rotation": tr, "scale": ts}
            # 一人称では左腕が描かれないので、左手側は畳んでおく
            fp_bones["left"] = {"scale": 0.0}
        A[f"{base}.tp"] = {"loop": True, "bones": tp_bones}
        A[f"{base}.fp"] = {"loop": True, "bones": fp_bones}

        # ---- 常時の動き ------------------------------------------------
        idle = {}
        if name == "greatsword":
            idle["ring"] = {"rotation": [0, 0, "q.anim_time * 90.0"]}
            idle["tassel"] = {"rotation": ["math.sin(q.anim_time * 120.0) * 6.0", 0,
                                           "math.sin(q.anim_time * 90.0) * 5.0"]}
        elif name == "dagger":
            idle["tassel"] = {"rotation": ["math.sin(q.anim_time * 140.0) * 7.0", 0,
                                           "math.cos(q.anim_time * 100.0) * 6.0"]}
        elif name == "shield":
            idle["core"] = {"scale": "1.0 + math.sin(q.anim_time * 180.0) * 0.06",
                            "rotation": [0, 0, "q.anim_time * 30.0"]}
        elif name == "whip":
            # とぐろ: 各節が 22° ずつ曲がって輪になり、波がゆっくり伝わる
            for i in range(WHIP_SEGS):
                k = 40 if i == 0 else 22
                idle[f"seg{i}"] = {"rotation": [
                    f"{k} + math.sin(q.anim_time * 160.0 - {i * 26}) * 4.0", 0,
                    f"math.sin(q.anim_time * 110.0 - {i * 20}) * 2.5"]}
        elif name == "bow":
            idle["arrow"] = {"scale": "v.hd_draw > 0.02 ? 1.0 : 0.0"}
        if idle:
            A[f"{base}.idle"] = {"loop": True, "animation_length": 4.0, "bones": idle}

        # ---- 振り ------------------------------------------------------
        kind = SWING[name]
        sw = {}
        s1 = "math.sin(v.hd_sw * 180.0)"
        s2 = "math.sin(v.hd_sw * 360.0)"
        if kind == "heavy":
            sw["root"] = {"rotation": [f"-{s1} * 34.0", f"{s2} * 14.0", f"{s1} * 10.0"],
                          "position": [0, f"{s1} * 1.2", f"-{s1} * 2.0"]}
        elif kind == "slash":
            sw["root"] = {"rotation": [f"-{s1} * 26.0", f"{s2} * 22.0", f"{s1} * 18.0"]}
            sw["left"] = {"rotation": [f"{s1} * 24.0", f"-{s2} * 20.0", 0]}
        elif kind == "stab":
            sw["root"] = {"position": [0, 0, f"-{s1} * 3.0"],
                          "rotation": [f"{s1} * 20.0", 0, f"{s2} * 15.0"]}
        elif kind == "bash":
            sw["root"] = {"position": [f"{s1} * 2.0", 0, f"-{s1} * 3.0"],
                          "rotation": [0, f"{s1} * 60.0", 0]}
        elif kind == "whip":
            for i in range(WHIP_SEGS):
                k = 40 if i == 0 else 22
                # とぐろを解き、根元から先へ鞭の波が走る
                sw[f"seg{i}"] = {"rotation": [
                    f"-{k} * {s1} + math.sin(v.hd_sw * 540.0 - {i * 34}) * 18.0 * {s1}",
                    0, f"math.sin(v.hd_sw * 360.0 - {i * 24}) * 6.0 * {s1}"]}
        if sw:
            A[f"{base}.swing"] = {"loop": True, "bones": sw}

        # ---- 使用中（右クリック保持） --------------------------------------
        use = {}
        u = "v.hd_use"
        if name == "bow":
            d = "v.hd_draw"
            pull = 8.0
            ang = math.degrees(math.atan2(pull, STRING_TIP))
            stretch = math.hypot(pull, STRING_TIP) / STRING_TIP - 1
            use["root"] = {"rotation": [f"{u} * 90.0", 0, 0]}
            use["limb_u"] = {"rotation": [f"-{d} * 9.0", 0, 0]}
            use["limb_l"] = {"rotation": [f"{d} * 9.0", 0, 0]}
            use["str_u"] = {"rotation": [f"{d} * {ang:.1f}", 0, 0],
                            "scale": [1, f"1.0 + {d} * {stretch:.3f}", 1]}
            use["str_l"] = {"rotation": [f"-{d} * {ang:.1f}", 0, 0],
                            "scale": [1, f"1.0 + {d} * {stretch:.3f}", 1]}
            use["arrow"] = {"position": [0, 0, f"{d} * {pull}"]}
        elif name == "shield":
            # 腕を前に上げる全身モーション（-65°）を打ち消し、盾の面を正面へ
            use["root"] = {"rotation": [f"{u} * 65.0", f"{u} * 90.0", 0],
                           "position": [f"{u} * 2.0", f"-{u} * 2.0", 0]}
            use["core"] = {"scale": f"1.0 + {u} * 0.25"}
        elif name == "whip":
            for i in range(WHIP_SEGS):
                k = 40 if i == 0 else 22
                use[f"seg{i}"] = {"rotation": [
                    f"-{k} * {u} + math.sin(q.anim_time * 900.0 - {i * 36}) * 14.0", 0,
                    f"math.cos(q.anim_time * 700.0 - {i * 30}) * 10.0"]}
        else:
            use["root"] = {"rotation": [f"-{u} * 22.0", f"{u} * 8.0", 0],
                           "position": [0, f"{u} * 1.0", 0]}
            if name == "greatsword":
                use["ring"] = {"rotation": [0, 0, "q.anim_time * 540.0"],
                               "scale": f"1.0 + {u} * 0.35"}
            if name in ("twinblades", "claws"):
                use["left"] = {"rotation": [f"-{u} * 22.0", f"-{u} * 8.0", 0]}
        A[f"{base}.use"] = {"loop": True, "animation_length": 2.0, "bones": use}
    return A


def attachable(name: str, anims: dict) -> dict:
    base = f"animation.{NS}.{name}"
    keys = {"tp": f"{base}.tp", "fp": f"{base}.fp", "use": f"{base}.use"}
    animate = [{"tp": "!c.is_first_person"}, {"fp": "c.is_first_person"}]
    if f"{base}.idle" in anims:
        keys["idle"] = f"{base}.idle"
        animate.append("idle")
    if f"{base}.swing" in anims:
        keys["swing"] = f"{base}.swing"
        animate.append({"swing": "v.hd_sw > 0.0"})
    animate.append({"use": "v.hd_use > 0.0" if name != "bow" else "v.hd_use"})
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": f"{NS}:{name}",
                "materials": {"default": "entity_emissive_alpha",
                              "enchanted": "entity_alphatest_glint"},
                "textures": {"default": f"textures/entity/hd/{name}",
                             "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": f"geometry.{NS}.{name}"},
                "animations": keys,
                "scripts": {"pre_animation": PRE, "animate": animate},
                "render_controllers": ["controller.render.item_default"],
            }
        },
    }


# ===========================================================================
#  2. プレイヤーの全身モーション
# ===========================================================================
ARMS = ("rightArm", "leftArm")
FP = "(c.is_first_person ? 0.25 : 1.0)"


def _key(bone, chan, v):
    if bone in ARMS and chan == "rotation":
        return [f"{r2(x)} * {FP}" if abs(x) > 1e-6 else 0 for x in v]
    return vec(*v)


def body(length, frames, loop=False, smooth=True):
    """frames = {time: {bone: {"rotation": (x,y,z), "position": (x,y,z)}}}。
    指定の無いボーン・チャンネルは 0 として扱い、全キーで揃える（補間が破綻しない）。"""
    bones = {}
    used = {}
    for t, pose in frames.items():
        for bone, chans in pose.items():
            for chan in chans:
                used.setdefault(bone, set()).add(chan)
    for bone, chans in used.items():
        out = {}
        for chan in sorted(chans):
            track = {}
            for t in sorted(frames, key=float):
                v = frames[t].get(bone, {}).get(chan, (0, 0, 0))
                val = _key(bone, chan, v)
                key = f"{float(t):.2f}".rstrip("0").rstrip(".") if float(t) else "0.0"
                track[key] = {"post": val, "lerp_mode": "catmullrom"} if smooth else val
            out[chan] = track
        bones[bone] = out
    doc = {"loop": loop, "animation_length": length, "bones": bones}
    return doc


Z = {}  # 中立


def P(**bones):
    """P(rightArm=(-90,0,0), root_pos=(0,-2,0)) のような簡易記法。"""
    out = {}
    for k, v in bones.items():
        if k.endswith("_pos"):
            out.setdefault(k[:-4], {})["position"] = v
        else:
            out.setdefault(k, {})["rotation"] = v
    return out


def flip(length, turns=1.0, axis="x", tuck=True, centre=14.0, lift=0.0, steps=10):
    """root を体の中心（高さ centre）まわりに回す。足元を軸にすると頭が地面に
    めり込むので、回転ぶんを position で打ち消して重心で回す。"""
    frames = {}
    for i in range(steps + 1):
        t = i / steps
        ease = 0.5 - 0.5 * math.cos(math.pi * t)
        th = 360.0 * turns * ease
        r = math.radians(th)
        pose = {}
        if axis == "x":
            # rx=θ のとき (0,c,0) は (0, c cosθ, -c sinθ) へ動く → 差を戻す
            pose["root"] = {"rotation": (th, 0, 0),
                            "position": (0, centre * (1 - math.cos(r)) + lift * math.sin(math.pi * t),
                                         centre * math.sin(r))}
        else:  # 側転（z 軸）
            pose["root"] = {"rotation": (0, 0, th),
                            "position": (centre * math.sin(r), centre * (1 - math.cos(r)), 0)}
        if tuck:
            k = math.sin(math.pi * t)
            pose["rightLeg"] = {"rotation": (-75 * k, 0, 0)}
            pose["leftLeg"] = {"rotation": (-75 * k, 0, 0)}
            pose["rightArm"] = {"rotation": (-40 * k, 0, -20 * k)}
            pose["leftArm"] = {"rotation": (-40 * k, 0, 20 * k)}
        frames[round(length * t, 3)] = pose
    return body(length, frames, smooth=False)


def player_anims() -> dict:
    A = {}
    n = f"animation.{NS}.p."

    # ---- 通常攻撃の三連（当たるたびに 1→2→3 と進む） ---------------------
    A[n + "combo1"] = body(0.42, {          # 右からの横薙ぎ
        0: Z,
        0.08: P(body=(0, -38, 0), rightArm=(-105, 0, -35), leftArm=(-25, 0, 18),
                head=(0, 30, 0)),
        0.20: P(body=(0, 42, 0), rightArm=(-88, 70, 12), leftArm=(25, 0, 10),
                head=(0, -34, 0), rightLeg=(-12, 0, 0), leftLeg=(14, 0, 0)),
        0.42: Z})
    A[n + "combo2"] = body(0.42, {          # 返しの逆薙ぎ
        0: Z,
        0.08: P(body=(0, 40, 0), rightArm=(-95, 60, 10), leftArm=(20, 0, 15),
                head=(0, -32, 0)),
        0.20: P(body=(0, -40, 0), rightArm=(-80, -65, -15), leftArm=(-30, 0, 20),
                head=(0, 34, 0), rightLeg=(14, 0, 0), leftLeg=(-12, 0, 0)),
        0.42: Z})
    A[n + "combo3"] = body(0.58, {          # 跳び上がっての兜割り
        0: Z,
        0.14: P(body=(-14, 0, 0), rightArm=(-178, 0, -6), leftArm=(-172, 0, 6),
                root_pos=(0, 1.5, 0), head=(-15, 0, 0)),
        0.30: P(body=(30, 0, 0), rightArm=(-35, 0, 0), leftArm=(-40, 0, 0),
                root_pos=(0, -2.0, -1.5), rightLeg=(-38, 0, 0), leftLeg=(26, 0, 0),
                head=(20, 0, 0)),
        0.42: P(body=(24, 0, 0), rightArm=(-30, 0, 0), leftArm=(-36, 0, 0),
                root_pos=(0, -1.8, -1.2), rightLeg=(-34, 0, 0), leftLeg=(24, 0, 0)),
        0.58: Z})
    A[n + "thrust"] = body(0.40, {
        0: Z,
        0.10: P(body=(0, -30, 0), rightArm=(-60, 0, -10), head=(0, 28, 0)),
        0.20: P(body=(12, 26, 0), rightArm=(-96, 12, 0), leftArm=(30, 0, 12),
                root_pos=(0, -0.8, -2.5), rightLeg=(-30, 0, 0), leftLeg=(28, 0, 0),
                head=(-10, -24, 0)),
        0.40: Z})
    A[n + "uppercut"] = body(0.46, {
        0: Z,
        0.12: P(rightArm=(25, 0, -10), body=(16, 0, 0), root_pos=(0, -2.2, 0),
                rightLeg=(-30, 0, 0), leftLeg=(20, 0, 0)),
        0.26: P(rightArm=(-172, 0, 8), leftArm=(-20, 0, 18), body=(-16, 0, 0),
                root_pos=(0, 1.2, 0), head=(-20, 0, 0)),
        0.46: Z})
    A[n + "clawx"] = body(0.46, {
        0: Z,
        0.12: P(rightArm=(-165, 0, -32), leftArm=(-165, 0, 32), body=(-10, 0, 0),
                head=(-10, 0, 0)),
        0.28: P(rightArm=(-62, 0, 28), leftArm=(-62, 0, -28), body=(16, 0, 0),
                root_pos=(0, -1.0, -1.0)),
        0.46: Z})
    A[n + "crack"] = body(0.50, {           # 鞭: 頭上から振り下ろす
        0: Z,
        0.16: P(rightArm=(-172, 0, -12), body=(-12, -10, 0), head=(-8, 0, 0)),
        0.30: P(rightArm=(-58, 0, 2), body=(14, 12, 0), root_pos=(0, -0.6, 0)),
        0.50: Z})
    A[n + "bash"] = body(0.40, {            # 盾で殴る
        0: Z,
        0.10: P(body=(0, -24, 0), rightArm=(-60, -30, 0)),
        0.20: P(body=(14, 22, 0), rightArm=(-92, 22, 0), root_pos=(0, -0.8, -3.0),
                rightLeg=(-26, 0, 0), leftLeg=(24, 0, 0)),
        0.40: Z})
    A[n + "stab"] = body(0.36, {            # 逆手の斬り下ろし
        0: Z,
        0.10: P(rightArm=(-135, 0, -24), body=(0, -18, 0)),
        0.20: P(rightArm=(-48, 34, 12), body=(16, 20, 0), root_pos=(0, -0.6, -1.0)),
        0.36: Z})

    # ---- 戦技 ---------------------------------------------------------
    A[n + "heavy"] = body(1.20, {           # 溜めてからの叩きつけ
        0: Z,
        0.25: P(rightArm=(-172, 0, -6), leftArm=(-168, 0, 6), body=(-16, 0, 0),
                head=(-12, 0, 0), root_pos=(0, 0.6, 0)),
        0.60: P(rightArm=(-176, 0, -6), leftArm=(-172, 0, 6), body=(-20, 0, 0),
                head=(-14, 0, 0), root_pos=(0, 0.8, 0)),
        0.74: P(rightArm=(-28, 0, 0), leftArm=(-34, 0, 0), body=(34, 0, 0),
                root_pos=(0, -2.4, -1.5), rightLeg=(-40, 0, 0), leftLeg=(30, 0, 0),
                head=(18, 0, 0)),
        0.95: P(rightArm=(-26, 0, 0), leftArm=(-30, 0, 0), body=(30, 0, 0),
                root_pos=(0, -2.2, -1.4), rightLeg=(-38, 0, 0), leftLeg=(28, 0, 0)),
        1.20: Z})
    A[n + "lunge"] = body(0.60, {
        0: Z,
        0.08: P(body=(22, 0, 0), rightArm=(-96, 0, 0), leftArm=(42, 0, 12),
                root_pos=(0, -1.6, 0), rightLeg=(-44, 0, 0), leftLeg=(38, 0, 0)),
        0.45: P(body=(24, 0, 0), rightArm=(-98, 0, 0), leftArm=(46, 0, 14),
                root_pos=(0, -1.6, 0), rightLeg=(-46, 0, 0), leftLeg=(40, 0, 0)),
        0.60: Z})
    A[n + "whirl"] = body(0.36, {           # 回転斬り（ループ）
        0: P(root=(0, 0, 0), rightArm=(-90, 0, -70), leftArm=(-90, 0, 70)),
        0.18: P(root=(0, 180, 0), rightArm=(-90, 0, -70), leftArm=(-90, 0, 70)),
        0.36: P(root=(0, 360, 0), rightArm=(-90, 0, -70), leftArm=(-90, 0, 70))},
        loop=True, smooth=False)
    A[n + "spin"] = body(0.50, {
        0: Z,
        0.25: P(root=(0, 200, 0), rightArm=(-92, 0, -60), leftArm=(-40, 0, 40)),
        0.50: P(root=(0, 360, 0))}, smooth=False)
    A[n + "plunge"] = body(0.80, {          # 空中からの突き下ろし
        0: Z,
        0.15: P(rightArm=(-176, 0, 0), leftArm=(-170, 0, 0), rightLeg=(-62, 0, 0),
                leftLeg=(-58, 0, 0), root_pos=(0, 2.0, 0), head=(-10, 0, 0)),
        0.45: P(rightArm=(-18, 0, 0), leftArm=(-24, 0, 0), body=(36, 0, 0),
                rightLeg=(-12, 0, 0), leftLeg=(12, 0, 0), head=(26, 0, 0)),
        0.80: Z})
    A[n + "land"] = body(0.70, {            # スーパーヒーロー着地
        0: Z,
        0.05: P(root_pos=(0, -4.2, 0), body=(36, 0, 0), rightLeg=(-82, 0, 0),
                leftLeg=(62, 0, 0), leftArm=(-38, 0, 36), rightArm=(-24, 0, -42),
                head=(-24, 0, 0)),
        0.45: P(root_pos=(0, -4.0, 0), body=(34, 0, 0), rightLeg=(-80, 0, 0),
                leftLeg=(60, 0, 0), leftArm=(-36, 0, 34), rightArm=(-22, 0, -40),
                head=(-22, 0, 0)),
        0.70: Z})
    A[n + "throw"] = body(0.40, {
        0: Z,
        0.12: P(rightArm=(-162, 0, -22), body=(-8, -26, 0), head=(0, 22, 0)),
        0.22: P(rightArm=(-72, 0, 10), body=(10, 22, 0), head=(0, -18, 0),
                rightLeg=(-16, 0, 0)),
        0.40: Z})
    A[n + "rapid"] = body(0.64, {           # 左右交互の連撃
        0: Z,
        0.08: P(rightArm=(-112, 42, 0), leftArm=(-20, 0, 10), body=(0, 22, 0)),
        0.16: P(rightArm=(-70, -52, 0), leftArm=(-112, -42, 0), body=(0, -22, 0)),
        0.24: P(rightArm=(-112, 42, 0), leftArm=(-70, 52, 0), body=(0, 22, 0)),
        0.32: P(rightArm=(-70, -52, 0), leftArm=(-112, -42, 0), body=(0, -22, 0)),
        0.40: P(rightArm=(-112, 42, 0), leftArm=(-70, 52, 0), body=(0, 22, 0)),
        0.48: P(rightArm=(-150, 0, -20), leftArm=(-150, 0, 20), body=(-10, 0, 0)),
        0.64: Z})
    A[n + "aim"] = body(1.0, {              # 弓を引く（使用中ループ）
        0: P(rightArm=(-90, 4, 0), leftArm=(-88, -46, 0), body=(0, 8, 0), head=(0, -6, 0)),
        1.0: P(rightArm=(-90, 4, 0), leftArm=(-88, -46, 0), body=(0, 8, 0), head=(0, -6, 0))},
        loop=True, smooth=False)
    A[n + "guard"] = body(1.0, {            # 盾を構える（使用中ループ）
        0: P(rightArm=(-65, 20, 0), leftArm=(-40, 0, 10), body=(6, -10, 0),
             root_pos=(0, -0.8, 0), rightLeg=(-14, 0, 0), leftLeg=(12, 0, 0)),
        1.0: P(rightArm=(-65, 20, 0), leftArm=(-40, 0, 10), body=(6, -10, 0),
               root_pos=(0, -0.8, 0), rightLeg=(-14, 0, 0), leftLeg=(12, 0, 0))},
        loop=True, smooth=False)
    A[n + "spinarm"] = body(0.30, {          # 頭上で鞭を回す（ループ）
        0: P(rightArm=(-170, 0, -10), body=(-6, 0, 0)),
        0.15: P(rightArm=(-170, 180, -10), body=(-6, 0, 0)),
        0.30: P(rightArm=(-170, 360, -10), body=(-6, 0, 0))}, loop=True, smooth=False)

    # ---- 必殺技 --------------------------------------------------------
    A[n + "ult_rise"] = body(1.10, {        # 武器を天に掲げる（カットイン）
        0: Z,
        0.30: P(rightArm=(-180, 0, -8), leftArm=(-24, 0, 34), head=(-24, 0, 0),
                body=(-8, 0, 0)),
        0.90: P(rightArm=(-182, 0, -8), leftArm=(-26, 0, 36), head=(-26, 0, 0),
                body=(-10, 0, 0)),
        1.10: P(rightArm=(-176, 0, -8), leftArm=(-22, 0, 30), head=(-20, 0, 0))})
    A[n + "ult_slam"] = body(0.90, {
        0: P(rightArm=(-180, 0, -6), leftArm=(-176, 0, 6), body=(-18, 0, 0)),
        0.18: P(rightArm=(-20, 0, 0), leftArm=(-26, 0, 0), body=(42, 0, 0),
                root_pos=(0, -3.0, -2.0), rightLeg=(-48, 0, 0), leftLeg=(36, 0, 0),
                head=(24, 0, 0)),
        0.60: P(rightArm=(-18, 0, 0), leftArm=(-24, 0, 0), body=(40, 0, 0),
                root_pos=(0, -2.8, -1.8), rightLeg=(-46, 0, 0), leftLeg=(34, 0, 0)),
        0.90: Z})
    A[n + "roar"] = body(1.00, {            # 獣の咆哮
        0: Z,
        0.20: P(rightArm=(-24, 0, -80), leftArm=(-24, 0, 80), body=(-22, 0, 0),
                head=(-34, 0, 0), root_pos=(0, -0.6, 0)),
        0.80: P(rightArm=(-30, 0, -84), leftArm=(-30, 0, 84), body=(-24, 0, 0),
                head=(-36, 0, 0), root_pos=(0, -0.6, 0)),
        1.00: Z})
    A[n + "cast"] = body(0.90, {            # 両手を前へ（結界・矢の雨の詠唱）
        0: Z,
        0.20: P(rightArm=(-100, -20, 0), leftArm=(-100, 20, 0), body=(-6, 0, 0)),
        0.70: P(rightArm=(-104, -22, 0), leftArm=(-104, 22, 0), body=(-8, 0, 0)),
        0.90: Z})

    # ---- 機動 ----------------------------------------------------------
    A[n + "dash"] = body(0.34, {            # 前傾の突進（腕は後ろへ流す）
        0: Z,
        0.06: P(body=(32, 0, 0), rightArm=(48, 0, -14), leftArm=(48, 0, 14),
                root_pos=(0, -1.0, 0), rightLeg=(-30, 0, 0), leftLeg=(36, 0, 0),
                head=(-26, 0, 0)),
        0.24: P(body=(30, 0, 0), rightArm=(50, 0, -14), leftArm=(50, 0, 14),
                root_pos=(0, -1.0, 0), rightLeg=(-28, 0, 0), leftLeg=(34, 0, 0),
                head=(-24, 0, 0)),
        0.34: Z})
    A[n + "step"] = body(0.30, {            # 回避ステップ
        0: Z,
        0.05: P(body=(14, 0, 0), root_pos=(0, -2.2, 0), rightArm=(-50, 20, 0),
                leftArm=(-50, -20, 0), rightLeg=(-30, 0, -10), leftLeg=(20, 0, 10)),
        0.30: Z})
    A[n + "airjump"] = flip(0.42, 1.0, tuck=True, centre=14.0)
    A[n + "frontflip"] = flip(0.55, 1.0, tuck=True, centre=14.0)
    A[n + "backflip"] = flip(0.60, -1.0, tuck=True, centre=14.0)
    A[n + "cartwheel"] = flip(0.50, 1.0, axis="z", tuck=False, centre=14.0)

    # ---- 持ち姿勢（武器を持っている間ループ） ---------------------------
    A[n + "hold_2h"] = body(1.0, {          # 大剣・大斧: 左手を柄へ添える
        0: P(rightArm=(-24, 14, 0), leftArm=(-38, -42, 0)),
        1.0: P(rightArm=(-24, 14, 0), leftArm=(-38, -42, 0))}, loop=True, smooth=False)
    A[n + "hold_claw"] = body(2.0, {        # かぎ爪: 前屈みの獣の構え
        0: P(rightArm=(-22, 10, -12), leftArm=(-22, -10, 12), body=(6, 0, 0)),
        1.0: P(rightArm=(-26, 10, -14), leftArm=(-26, -10, 14), body=(8, 0, 0)),
        2.0: P(rightArm=(-22, 10, -12), leftArm=(-22, -10, 12), body=(6, 0, 0))},
        loop=True)
    A[n + "hold_dual"] = body(2.0, {        # 双剣: 両の切先を前へ
        0: P(rightArm=(-18, 8, -6), leftArm=(-18, -8, 6)),
        1.0: P(rightArm=(-21, 8, -7), leftArm=(-21, -8, 7)),
        2.0: P(rightArm=(-18, 8, -6), leftArm=(-18, -8, 6))}, loop=True)
    A[n + "none"] = {"loop": False, "animation_length": 0.05, "bones": {}}
    return A


def main() -> None:
    wa = weapon_anims()
    write_json(os.path.join(ANIM_DIR, "hd_weapons.animation.json"),
               {"format_version": "1.8.0", "animations": wa})
    pa = player_anims()
    write_json(os.path.join(ANIM_DIR, "hd_player.animation.json"),
               {"format_version": "1.8.0", "animations": pa})
    for name in WEAPONS:
        write_json(os.path.join(ATT_DIR, f"{name}.attachable.json"), attachable(name, wa))
    print(f"  weapon animations: {len(wa)}  player animations: {len(pa)}  "
          f"attachables: {len(WEAPONS)}")


if __name__ == "__main__":
    main()
