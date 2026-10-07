# -*- coding: utf-8 -*-
"""アニメーション一式（武器のアタッチャブル＋プレイヤーの全身モーション）。

座標と回転の規則は hd_space（Mojang 公式サンプルから逆算・検証済み）に従う:
  rotation [rx, ry, rz] = Rz(-rz)·Ry(ry)·Rx(-rx)
  - rx が負 = 腕が前へ上がる / ry が正 = 右（-X）を向く / rz が正 = 右腕が外へ開く（左腕は負で外）

■ 武器（アタッチャブル）
  hold   … 手に bind されたボーン。持ち方（三人称・一人称・構え中）を受け持つ。
           持ち方は hd_holds.design() が「握りの点が拳に来る」ように数値で解いたもの
  root   … 握りが原点の子ボーン。振り・溜め・待機の揺れを武器自身の向きで足す
  振りはプレイヤーの公開変数 attack_time（c.owning_entity->v.attack_time）で駆動する。

■ 全身（playanimation で再生）
  hold.<武器>  … 持ち姿勢。バニラの「持つと右腕 -18°」と歩きの腕振りを打ち消し、
                 両手武器では左手が柄の二つ目の握りに届く角度にしてある
  <武器>.<技>  … 連撃・戦技・機動。持ち姿勢からの差分として書き出すので、
                 持ち姿勢と足し合わさって設計どおりの姿勢になる。攻撃の振り（バニラ）も打ち消す
  一人称では体の向き・脚・宙返りは 0、腕だけ 25% にして画面が暴れないようにする。
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hd_common import NS, RP, WEAPONS, write_json  # noqa: E402
from hd_holds import design  # noqa: E402
import hd_pose as HP  # noqa: E402
from gen_hd_weapons import STRING_TIP, WHIP_SEGS  # noqa: E402

ANIM_DIR = os.path.join(RP, "animations")
ATT_DIR = os.path.join(RP, "attachables")
HOLDS = design()


def r2(v):
    return round(float(v), 2) if isinstance(v, (int, float)) else v


def vec(v):
    return [r2(x) for x in v]


# ===========================================================================
#  1. 武器（アタッチャブル）
# ===========================================================================
def tf(d):
    return {"rotation": vec(d["rotation"]), "position": vec(d["position"]),
            "scale": r2(d.get("scale", 1.0))}


S1 = "math.sin(v.hd_sw * 180.0)"
S2 = "math.sin(v.hd_sw * 360.0)"


def weapon_anims():
    A = {}
    for name in WEAPONS:
        h = HOLDS[name]
        base = f"animation.{NS}.{name}"
        tp = {"hold": tf(h["tp"])}
        fp = {"hold": tf(h["fp"])}
        if "left_tp" in h:
            tp["hold_l"] = tf(h["left_tp"])
            fp["hold_l"] = {"scale": 0.0}      # 一人称では左腕が描かれないので畳む
        A[f"{base}.tp"] = {"loop": True, "bones": tp}
        A[f"{base}.fp"] = {"loop": True, "bones": fp}
        if "use" in h:
            A[f"{base}.tp_use"] = {"loop": True, "bones": {"hold": tf(h["use"]["tp"])}}
            A[f"{base}.fp_use"] = {"loop": True, "bones": {"hold": tf(h["use"]["fp"])}}

        # ---- 待機の揺れ（武器自身の向きで） --------------------------------
        idle = {}
        if name == "greatsword":
            idle["ring"] = {"rotation": [0, 0, "q.anim_time * 90.0"]}
            idle["tassel"] = {"rotation": ["math.sin(q.anim_time * 120.0) * 7.0", 0,
                                           "math.sin(q.anim_time * 90.0) * 6.0"]}
        elif name == "dagger":
            idle["tassel"] = {"rotation": ["math.sin(q.anim_time * 140.0) * 8.0", 0,
                                           "math.cos(q.anim_time * 100.0) * 7.0"]}
        elif name == "shield":
            idle["core"] = {"scale": "1.0 + math.sin(q.anim_time * 180.0) * 0.06",
                            "rotation": [0, 0, "q.anim_time * 30.0"]}
        elif name == "whip":
            for i in range(WHIP_SEGS):
                k = 40 if i == 0 else 22
                idle[f"seg{i}"] = {"rotation": [
                    f"{k} + math.sin(q.anim_time * 160.0 - {i * 26}) * 4.0", 0,
                    f"math.sin(q.anim_time * 110.0 - {i * 20}) * 2.5"]}
        elif name == "bow":
            idle["arrow"] = {"scale": "v.hd_draw > 0.02 ? 1.0 : 0.0"}
        # 呼吸ほどの上下（全武器）
        idle["root"] = {"position": [0, "math.sin(q.anim_time * 90.0) * 0.12", 0]}
        A[f"{base}.idle"] = {"loop": True, "animation_length": 4.0, "bones": idle}

        # ---- 振り（攻撃のたびに 0→1）: 体の大きな動きは全身モーションが受け持つので、
        #      ここは手首の返しと武器固有の動き ----------------------------------
        sw = {}
        if name in ("greatsword", "greataxe"):
            sw["root"] = {"rotation": [f"-{S1} * 18.0", 0, f"{S2} * 8.0"]}
            if name == "greatsword":
                sw["ring"] = {"rotation": [0, 0, "v.hd_sw * 360.0"], "scale": f"1.0 + {S1} * 0.3"}
        elif name == "twinblades":
            sw["root"] = {"rotation": [f"-{S1} * 22.0", f"{S2} * 12.0", 0]}
            sw["left"] = {"rotation": [f"-{S1} * 22.0", f"-{S2} * 12.0", 0]}
        elif name == "dagger":
            sw["root"] = {"rotation": [f"{S1} * 30.0", 0, f"{S2} * 25.0"]}
        elif name == "shield":
            sw["root"] = {"position": [0, 0, f"-{S1} * 2.5"]}
            sw["core"] = {"scale": f"1.0 + {S1} * 0.35"}
        elif name == "whip":
            for i in range(WHIP_SEGS):
                k = 40 if i == 0 else 22
                sw[f"seg{i}"] = {"rotation": [
                    f"-{k} * {S1} + math.sin(v.hd_sw * 540.0 - {i * 34}) * 18.0 * {S1}",
                    0, f"math.sin(v.hd_sw * 360.0 - {i * 24}) * 6.0 * {S1}"]}
        elif name == "claws":
            sw["root"] = {"rotation": [f"-{S1} * 15.0", 0, 0]}
            sw["left"] = {"rotation": [f"-{S1} * 15.0", 0, 0]}
        elif name == "bow":
            sw["root"] = {"rotation": [0, f"{S2} * 20.0", 0]}
        A[f"{base}.swing"] = {"loop": True, "bones": sw}

        # ---- 使用中（右クリック保持） --------------------------------------
        use = {}
        u = "v.hd_usew"
        if name == "bow":
            d = "v.hd_draw"
            pull = 8.0
            ang = math.degrees(math.atan2(pull, STRING_TIP))
            stretch = math.hypot(pull, STRING_TIP) / STRING_TIP - 1
            # リムは弦の側（+Z）へ撓み、弦の中央は後ろへ下がる
            use["limb_u"] = {"rotation": [f"-{d} * 9.0", 0, 0]}
            use["limb_l"] = {"rotation": [f"{d} * 9.0", 0, 0]}
            use["str_u"] = {"rotation": [f"{d} * {ang:.1f}", 0, 0],
                            "scale": [1, f"1.0 + {d} * {stretch:.3f}", 1]}
            use["str_l"] = {"rotation": [f"-{d} * {ang:.1f}", 0, 0],
                            "scale": [1, f"1.0 + {d} * {stretch:.3f}", 1]}
            use["arrow"] = {"position": [0, 0, f"{d} * {pull}"]}
            use["root"] = {"position": [0, f"{d} >= 1.0 ? math.sin(q.anim_time * 2200.0) * 0.08 : 0.0", 0]}
        elif name == "shield":
            use["core"] = {"scale": f"1.0 + {u} * 0.3", "rotation": [0, 0, "q.anim_time * 240.0"]}
        elif name == "whip":
            for i in range(WHIP_SEGS):
                k = 40 if i == 0 else 22
                use[f"seg{i}"] = {"rotation": [
                    f"-{k} * {u} + math.sin(q.anim_time * 900.0 - {i * 36}) * 14.0 * {u}", 0,
                    f"math.cos(q.anim_time * 700.0 - {i * 30}) * 10.0 * {u}"]}
        elif name == "greatsword":
            use["ring"] = {"rotation": [0, 0, "q.anim_time * 540.0"], "scale": f"1.0 + {u} * 0.35"}
            use["root"] = {"rotation": [f"-{u} * 8.0", 0, 0]}
        else:
            use["root"] = {"rotation": [f"-{u} * 10.0", 0, 0]}
        A[f"{base}.use"] = {"loop": True, "animation_length": 2.0, "bones": use}
    return A


PRE = [
    # 攻撃の振り: プレイヤーの公開変数 attack_time（0→1）
    "v.hd_sw = math.clamp(c.owning_entity->v.attack_time, 0.0, 1.0);",
    "v.hd_use = q.is_using_item ? 1.0 : 0.0;",
    # 構えの切り替えは 0.1 秒ほどで滑らかに
    "v.hd_usew = (v.hd_usew ?? 0.0) + (v.hd_use - (v.hd_usew ?? 0.0)) * math.min(1.0, q.delta_time * 14.0);",
    # 弓: 引き始めてから 1 秒で最大まで（バニラの弓と同じ数え方）
    "v.hd_draw = q.is_using_item ? math.clamp((q.main_hand_item_max_duration - "
    "q.main_hand_item_use_duration) / 20.0, 0.0, 1.0) : 0.0;",
    "v.hd_fp = c.is_first_person ? 1.0 : 0.0;",
]


def attachable(name, anims):
    base = f"animation.{NS}.{name}"
    keys = {k: f"{base}.{k}" for k in ("tp", "fp", "idle", "swing", "use")}
    has_use = f"{base}.tp_use" in anims
    if has_use:
        keys["tp_use"] = f"{base}.tp_use"
        keys["fp_use"] = f"{base}.fp_use"
        animate = [{"tp": "(1.0 - v.hd_fp) * (1.0 - v.hd_usew)"}, {"tp_use": "(1.0 - v.hd_fp) * v.hd_usew"},
                   {"fp": "v.hd_fp * (1.0 - v.hd_usew)"}, {"fp_use": "v.hd_fp * v.hd_usew"}]
    else:
        animate = [{"tp": "1.0 - v.hd_fp"}, {"fp": "v.hd_fp"}]
    animate += ["idle", {"swing": "v.hd_sw > 0.0"}, {"use": "v.hd_usew > 0.01"}]
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
#  2. 全身モーション
# ===========================================================================
BONES = {"rA": "rightArm", "lA": "leftArm", "b": "body", "h": "head", "rL": "rightLeg",
         "lL": "leftLeg", "root": "root", "w": "waist"}
ARMS = ("rA", "lA")
FPK = 0.25   # 一人称での腕の振れ幅

# バニラの攻撃の振り（animation.player.attack.rotations）を打ち消す項
_ATK = "math.sin((1.0 - math.pow(1.0 - v.attack_time, 4.0)) * 180.0)"
ATK_CANCEL = {
    ("rA", 0): f"({_ATK} * 1.2 + math.sin(v.attack_time * 180.0)) * 30.0",
    ("rA", 1): f"({_ATK} != 0.0 ? 30.0 - 90.0 * {_ATK} : 0.0)",
    ("lA", 0): f"({_ATK} * 1.2 + math.sin(v.attack_time * 180.0)) * 10.0",
    ("b", 1): "-math.sin(360.0 * math.sqrt(v.attack_time)) * 5.0",
}
# 持ち姿勢で打ち消すバニラ: 右腕の -18°（holding）と、歩きの腕振り（75%）
HOLD_CANCEL = {
    ("rA", 0): "18.0 + 0.375 * (v.tcos0 ?? 0.0)",
    ("lA", 0): "-0.75 * (v.tcos0 ?? 0.0)",
}


def num(x):
    return f"{x:.2f}".rstrip("0").rstrip(".") if abs(x) > 1e-6 else "0"


def chan_expr(bone, axis, value, kind):
    """kind: 'hold'（絶対値＋バニラ打ち消し）/ 'act'（差分＋攻撃の振り打ち消し）/ 'move'（差分）。"""
    is_arm = bone in ARMS
    if kind == "hold":
        extra = HOLD_CANCEL.get((bone, axis))
        tp = num(value) + (f" + {extra}" if extra else "")
        if is_arm:
            return f"v.is_first_person ? 0.0 : ({tp})" if (extra or abs(value) > 1e-6) else 0
        return f"v.is_first_person ? 0.0 : ({tp})" if abs(value) > 1e-6 else 0
    extra = ATK_CANCEL.get((bone, axis)) if kind == "act" else None
    if abs(value) < 1e-6 and not extra:
        return 0
    tp = num(value) + (f" + {extra}" if extra else "")
    if is_arm:
        return f"v.is_first_person ? {num(value * FPK)} : ({tp})"
    return f"v.is_first_person ? 0.0 : ({tp})"


_HOLD_CACHE = {}


def hold_pose(name):
    """武器ごとの持ち姿勢（絶対値）。両手武器は hd_holds で両方の拳が柄に届く所に決めてあり、
    それ以外は書いた姿勢から武器が体に入り込まないよう腕を少しだけ解き直す。"""
    if name not in _HOLD_CACHE:
        P = _hold_raw(name)
        if HOLDS[name].get("grip2") is None:
            P = HP.solve_key(_cloud(name), name, P, {"keep": 2.5})
        _HOLD_CACHE[name] = P
    return dict(_HOLD_CACHE[name])


def _hold_raw(name):
    h = HOLDS[name]
    P = {"rA": tuple(h["arm_r"]), "lA": tuple(h["arm_l"])}
    extra = {
        "greatsword": {"b": (4, 0, 0), "h": (-4, 0, 0)},
        "twinblades": {"b": (3, 0, 0)},
        "greataxe": {"b": (0, -8, 0), "h": (0, 8, 0)},
        "dagger": {"lA": (-28, 10, -6), "b": (8, 0, 0), "h": (-8, 0, 0)},
        "bow": {"lA": (-6, 0, -4)},
        "shield": {"rA": (-6, 0, 0), "lA": (-8, 0, -4)},
        "whip": {"lA": (-10, 0, -6)},
        "claws": {"b": (10, 0, 0), "h": (-10, 0, 0)},
    }[name]
    P.update(extra)
    P.update(h.get("body", {}))
    return P


_CLOUDS = {}


def _cloud(name, use=False):
    if (name, use) not in _CLOUDS:
        _CLOUDS[(name, use)] = HP.Cloud(HOLDS, name, use, step=0.7)
    return _CLOUDS[(name, use)]


def use_pose(name):
    h = HOLDS[name].get("use")
    if not h:
        return None
    P = dict(hold_pose(name))
    P["rA"] = tuple(h["arm_r"])
    P["lA"] = tuple(h["arm_l"])
    if name == "shield":
        P.update({"b": (6, -8, 0), "h": (0, 8, 0), "rL": (-14, 0, 0), "lL": (12, 0, 0),
                  "root_pos": (0, -0.8, 0)})
    if name == "bow":
        P.update({"b": (0, 0, 0), "h": (0, 0, 0)})
    return P


def build_anim(length, frames, hold, kind="act", loop=False, smooth=True):
    """frames: {t: {key: (x,y,z)}}。key は rA/lA/b/h/rL/lL/root/w と root_pos。
    書かれていない部位は持ち姿勢のまま。出力は持ち姿勢からの差分（kind='hold' なら絶対値）。"""
    keys = set(hold)
    for f in frames.values():
        keys |= set(f)
    bones = {}
    for key in sorted(keys):
        is_pos = key.endswith("_pos")
        bone_key = key[:-4] if is_pos else key
        bone = BONES[bone_key]
        chan = "position" if is_pos else "rotation"
        track = {}
        moved = False
        for t in sorted(frames, key=float):
            pose = frames[t]
            base = hold.get(key, (0, 0, 0))
            val = pose.get(key, base)
            delta = tuple(val[i] - (0 if kind == "hold" else base[i]) for i in range(3))
            if any(abs(d) > 1e-6 for d in delta):
                moved = True
            if is_pos:
                v = [f"v.is_first_person ? 0.0 : {num(d)}" if abs(d) > 1e-6 else 0 for d in delta]
            else:
                v = [chan_expr(bone_key, i, delta[i], kind) for i in range(3)]
            ts = f"{float(t):.3f}".rstrip("0").rstrip(".") if float(t) else "0.0"
            track[ts] = {"post": v, "lerp_mode": "catmullrom"} if smooth else v
        needs_cancel = kind == "act" and any((bone_key, i) in ATK_CANCEL for i in range(3)) and not is_pos
        if moved or needs_cancel or (kind == "hold" and not is_pos and any(
                (bone_key, i) in HOLD_CANCEL for i in range(3))):
            bones.setdefault(bone, {})[chan] = track
    return {"loop": loop, "animation_length": length, "bones": bones}


# ---------------------------------------------------------------------------
#  キーポーズの記法: P(rA=(..), b=(..), root_pos=(..))。H は「持ち姿勢のまま」
# ---------------------------------------------------------------------------
H = {}


def P(**k):
    return k


def A(phi, hx=-1.5):
    """両手武器の手の高さ（度）。体の正面の弧（両方の拳が柄に届く所）の上で、0 = 肩の高さ、+ が上。"""
    return (float(phi), float(hx), 0.0)


def flip_frames(length, turns=1.0, axis="x", tuck=True, centre=14.0, steps=10):
    """root を重心（高さ centre）まわりに回す。足元を軸にすると頭が地面に埋まるので、
    回転ぶんを position で打ち消す。rx=θ で (0,c,0) は (0, c·cosθ, -c·sinθ) へ動く。"""
    frames = {}
    for i in range(steps + 1):
        t = i / steps
        ease = 0.5 - 0.5 * math.cos(math.pi * t)
        th = 360.0 * turns * ease
        r = math.radians(th)
        k = math.sin(math.pi * t)
        if axis == "x":
            pose = {"root": (th, 0, 0), "root_pos": (0, centre * (1 - math.cos(r)), centre * math.sin(r))}
        else:
            pose = {"root": (0, 0, th), "root_pos": (-centre * math.sin(r), centre * (1 - math.cos(r)), 0)}
        if tuck:
            # 腕は持ち姿勢のまま（武器を握ったまま回る）。脚だけ抱え込む
            pose.update({"rL": (-75 * k, 0, 0), "lL": (-75 * k, 0, 0)})
        frames[round(length * t, 3)] = pose
    return frames


# ---- 武器ごとの三連コンボ（絶対値。両端は持ち姿勢） --------------------------
COMBOS = {
    # 両手武器は「手の高さ hands（正面の弧の上）」と「刃の向き blade（体の向きで）」で書き、
    # hd_pose が 0.05 秒ごとに腕を解く（左の拳は常に柄の上、武器は体に入らない）
    "greatsword": [
        (0.50, {0: H,   # 袈裟斬り: 右肩の上に振りかぶり、左下へ両手で
                0.10: P(hands=A(40), blade=(-0.45, 0.8, -0.35), b=(-10, 35, 0), h=(-14, -18, 0)),
                0.22: P(hands=A(-32), blade=(0.55, -0.45, -0.7), b=(18, -40, 0), h=(0, 30, 0),
                        rL=(-14, 0, 0), lL=(12, 0, 0)),
                0.32: P(hands=A(-36), blade=(0.5, -0.5, -0.7), b=(16, -36, 0), h=(0, 28, 0)),
                0.50: H}),
        (0.50, {0: H,   # 逆袈裟: 左下から右上へ斬り上げる
                0.10: P(hands=A(-40), blade=(0.5, -0.6, -0.6), b=(12, -35, 0), h=(0, 25, 0)),
                0.24: P(hands=A(40), blade=(-0.5, 0.75, -0.4), b=(-12, 40, 0), h=(-14, -20, 0)),
                0.34: P(hands=A(41), blade=(-0.45, 0.8, -0.35), b=(-10, 36, 0), h=(-14, -18, 0)),
                0.50: H}),
        (0.62, {0: H,   # 兜割り: 跳び上がって真上から（左足を踏み込む）
                0.14: P(hands=A(43), blade=(0, 0.95, 0.3), b=(-20, 0, 0), h=(-28, 0, 0), root_pos=(0, 2.0, 0)),
                0.30: P(hands=A(-30), blade=(0, -0.5, -0.85), b=(30, 0, 0), h=(16, 0, 0),
                        root_pos=(0, -2.5, -1.5), rL=(30, 0, 0), lL=(-40, 0, 0)),
                0.44: P(hands=A(-30), blade=(0, -0.5, -0.85), b=(26, 0, 0), h=(14, 0, 0),
                        root_pos=(0, -2.2, -1.3), rL=(28, 0, 0), lL=(-36, 0, 0)),
                0.62: H}),
    ],
    "twinblades": [
        (0.40, {0: H,   # 右の横薙ぎ
                0.08: P(rA=(-95, 70, 0), lA=(-45, -10, 0), b=(0, 25, 0), h=(0, -20, 0)),
                0.20: P(rA=(-85, -55, 0), lA=(-40, 10, 0), b=(0, -30, 0), h=(0, 25, 0),
                        rL=(-12, 0, 0)),
                0.40: H}),
        (0.40, {0: H,   # 左の横薙ぎ
                0.08: P(lA=(-95, -70, 0), rA=(-45, 10, 0), b=(0, -25, 0), h=(0, 20, 0)),
                0.20: P(lA=(-85, 55, 0), rA=(-40, -10, 0), b=(0, 30, 0), h=(0, -25, 0),
                        lL=(-12, 0, 0)),
                0.40: H}),
        (0.50, {0: H,   # 十字斬り
                0.10: P(rA=(-160, 20, 30), lA=(-160, -20, -30), b=(-10, 0, 0), h=(-8, 0, 0)),
                0.24: P(rA=(-55, -40, -10), lA=(-55, 40, 10), b=(18, 0, 0), root_pos=(0, -1.0, -1.0)),
                0.34: P(rA=(-52, -38, -10), lA=(-52, 38, 10), b=(16, 0, 0), root_pos=(0, -0.9, -0.9)),
                0.50: H}),
    ],
    "greataxe": [
        (0.60, {0: H,   # 袈裟懸けの叩き斬り: 右肩へ担ぎ上げ、左下へ
                0.16: P(hands=A(46), blade=(-0.4, 0.85, 0.2), b=(-14, 40, 0), h=(-12, -30, 0)),
                0.32: P(hands=A(-30), blade=(0.5, -0.6, -0.6), b=(20, -45, 0), h=(0, 35, 0),
                        rL=(10, 0, 0), lL=(-18, 0, 0), root_pos=(0, -1.0, 0)),
                0.42: P(hands=A(-32), blade=(0.45, -0.65, -0.6), b=(18, -42, 0), root_pos=(0, -0.9, 0),
                        rL=(8, 0, 0), lL=(-16, 0, 0)),
                0.60: H}),
        (0.60, {0: H,   # 斬り上げ: 左下から右上へ
                0.14: P(hands=A(-42), blade=(0.4, -0.75, -0.5), b=(12, -30, 0), h=(0, 25, 0)),
                0.32: P(hands=A(44), blade=(-0.45, 0.85, -0.25), b=(-14, 35, 0), h=(-12, -25, 0)),
                0.42: P(hands=A(46), blade=(-0.4, 0.85, -0.2), b=(-12, 32, 0), h=(-10, -22, 0)),
                0.60: H}),
        (0.75, {0: H,   # 叩き割り: 頭上へ振りかぶって地面ごと（左足を踏み込む）
                0.20: P(hands=A(48), blade=(0, 0.95, 0.3), b=(-22, 0, 0), h=(-24, 0, 0), root_pos=(0, 1.0, 0)),
                0.38: P(hands=A(-30), blade=(0, -0.7, -0.7), b=(36, 0, 0), h=(18, 0, 0),
                        root_pos=(0, -3.0, -2.0), rL=(34, 0, 0), lL=(-46, 0, 0)),
                0.55: P(hands=A(-30), blade=(0, -0.7, -0.7), b=(33, 0, 0), h=(16, 0, 0),
                        root_pos=(0, -2.8, -1.8), rL=(32, 0, 0), lL=(-44, 0, 0)),
                0.75: H}),
    ],
    "dagger": [
        (0.36, {0: H,   # 逆手の振り下ろし
                0.08: P(rA=(-150, -20, 30), b=(0, 15, 0)),
                0.18: P(rA=(-60, 30, -10), b=(12, -15, 0), root_pos=(0, -0.6, -1.0)),
                0.36: H}),
        (0.36, {0: H,   # 逆手の外への払い
                0.08: P(rA=(-90, -60, 0), b=(0, -30, 0), h=(0, 25, 0)),
                0.20: P(rA=(-90, 70, 0), b=(0, 30, 0), h=(0, -25, 0)),
                0.36: H}),
        (0.44, {0: H,   # 回転斬り
                0.10: P(rA=(-90, 70, 0), root=(0, -120, 0)),
                0.22: P(rA=(-90, 70, 0), root=(0, -250, 0)),
                0.34: P(rA=(-85, 60, 0), root=(0, -360, 0)),
                0.44: P(root=(0, -360, 0))}),
    ],
    "bow": [
        (0.40, {0: H,   # 弓で薙ぐ
                0.10: P(rA=(-80, 60, 0), b=(0, 20, 0)),
                0.22: P(rA=(-80, -45, 0), b=(0, -25, 0)),
                0.40: H}),
        (0.40, {0: H,   # 弓で突き上げる
                0.10: P(rA=(-20, -30, 0), b=(10, 0, 0)),
                0.22: P(rA=(-140, 20, 20), b=(-10, 0, 0)),
                0.40: H}),
        (0.46, {0: H,   # 前蹴り
                0.10: P(rL=(20, 0, 0), b=(5, 0, 0), rA=(-40, 0, 20), lA=(-40, 0, -20)),
                0.20: P(rL=(-95, 0, 0), b=(-15, 0, 0), rA=(-40, 0, 25), lA=(-40, 0, -25),
                        root_pos=(0, 0, 1.0)),
                0.30: P(rL=(-85, 0, 0), b=(-12, 0, 0)),
                0.46: H}),
    ],
    "shield": [
        (0.40, {0: H,   # 盾で殴る
                0.10: P(rA=(-30, 20, 0), b=(0, 15, 0)),
                0.20: P(rA=(-90, -15, 0), b=(5, -15, 0), root_pos=(0, 0, -2.0), rL=(-20, 0, 0)),
                0.40: H}),
        (0.40, {0: H,   # 盾の縁で払う
                0.10: P(rA=(-80, -60, 0), b=(0, -25, 0)),
                0.22: P(rA=(-80, 60, 0), b=(0, 30, 0)),
                0.40: H}),
        (0.50, {0: H,   # 盾で突き上げる
                0.12: P(rA=(10, 0, 10), b=(15, 0, 0), root_pos=(0, -2.0, 0)),
                0.26: P(rA=(-170, 0, 10), b=(-15, 0, 0), root_pos=(0, 2.0, 0)),
                0.50: H}),
    ],
    "whip": [
        (0.50, {0: H,   # 頭上から打ち下ろす
                0.15: P(rA=(-175, 0, 15), b=(-10, 0, 0), h=(-8, 0, 0)),
                0.28: P(rA=(-45, 0, 0), b=(14, 0, 0), root_pos=(0, -0.6, 0)),
                0.50: H}),
        (0.46, {0: H,   # 横に払う
                0.12: P(rA=(-90, 70, 0), b=(0, 25, 0)),
                0.26: P(rA=(-90, -60, 0), b=(0, -25, 0)),
                0.46: H}),
        (0.56, {0: H,   # 回りながら打つ
                0.12: P(rA=(-10, 0, 85), root=(0, 120, 0)),
                0.26: P(rA=(-10, 0, 85), root=(0, 250, 0)),
                0.40: P(rA=(-30, 0, 60), root=(0, 360, 0)),
                0.56: P(root=(0, 360, 0))}),
    ],
    "claws": [
        (0.40, {0: H,   # 右の振り下ろし
                0.08: P(rA=(-160, 20, 30), b=(0, 20, 0)),
                0.20: P(rA=(-40, -50, -10), b=(8, -20, 0)),
                0.40: H}),
        (0.40, {0: H,   # 左の振り下ろし
                0.08: P(lA=(-160, -20, -30), b=(0, -20, 0)),
                0.20: P(lA=(-40, 50, 10), b=(8, 20, 0)),
                0.40: H}),
        (0.50, {0: H,   # 両爪の斬り上げ（小さく跳ぶ）
                0.10: P(rA=(10, 0, 15), lA=(10, 0, -15), b=(20, 0, 0), root_pos=(0, -2.0, 0)),
                0.24: P(rA=(-170, 0, 10), lA=(-170, 0, -10), b=(-15, 0, 0), root_pos=(0, 3.0, 0)),
                0.50: H}),
    ],
}


def old(x, y, z):
    """前の版（左右の回転が逆だった）で書いた値を正しい向きへ。"""
    return (x, -y, -z)


# ---- 技・機動の共通モーション（絶対値。両端は持ち姿勢） ---------------------
TWO_HANDED = ("greatsword", "greataxe")


def two_hand_moves():
    """両手武器の技（両手で柄を握ったまま）。共通の技を上書きする。"""
    T = {}
    T["heavy"] = (1.20, {0: H,   # 溜めて振りかぶり、叩きつける（左足を踏み込む）
        0.25: P(hands=A(46), blade=(0, 0.95, 0.3), b=(-20, 0, 0), h=(-24, 0, 0), root_pos=(0, 0.6, 0)),
        0.60: P(hands=A(48), blade=(0, 0.95, 0.32), b=(-22, 0, 0), h=(-26, 0, 0), root_pos=(0, 0.8, 0)),
        0.74: P(hands=A(-30), blade=(0, -0.6, -0.8), b=(32, 0, 0), root_pos=(0, -2.4, -1.5),
                rL=(30, 0, 0), lL=(-40, 0, 0), h=(16, 0, 0)),
        0.95: P(hands=A(-28), blade=(0, -0.6, -0.8), b=(28, 0, 0), root_pos=(0, -2.2, -1.4),
                rL=(28, 0, 0), lL=(-38, 0, 0)),
        1.20: H})
    T["plunge"] = (0.80, {0: H,  # 跳んで振りかぶり、真下へ
        0.15: P(hands=A(46), blade=(0, 0.95, 0.3), b=(-18, 0, 0), rL=(-62, 0, 0), lL=(-58, 0, 0),
                root_pos=(0, 2.0, 0), h=(-22, 0, 0)),
        0.45: P(hands=A(-30), blade=(0, -0.7, -0.7), b=(34, 0, 0), rL=(12, 0, 0), lL=(-12, 0, 0), h=(22, 0, 0)),
        0.80: H})
    T["ult_slam"] = (0.90, {     # 必殺の振り下ろし（左足を踏み込む）
        0: P(hands=A(48), blade=(0, 0.95, 0.32), b=(-22, 0, 0), h=(-24, 0, 0)),
        0.18: P(hands=A(-30), blade=(0, -0.7, -0.7), b=(38, 0, 0), root_pos=(0, -3.0, -2.0),
                rL=(34, 0, 0), lL=(-46, 0, 0), h=(20, 0, 0)),
        0.60: P(hands=A(-28), blade=(0, -0.7, -0.7), b=(36, 0, 0), root_pos=(0, -2.8, -1.8),
                rL=(32, 0, 0), lL=(-44, 0, 0)),
        0.90: H})
    T["whirl"] = (0.36, {        # 両手で斜め前へ突き出して回る
        0: P(root=(0, 0, 0), hands=A(-5), blade=(-0.6, 0, -0.8)),
        0.18: P(root=(0, 180, 0), hands=A(-5), blade=(-0.6, 0, -0.8)),
        0.36: P(root=(0, 360, 0), hands=A(-5), blade=(-0.6, 0, -0.8))})
    T["dash"] = (0.34, {0: H,    # 前傾で駆ける（武器は両手で前下に構えたまま）
        0.06: P(hands=A(-36), b=(28, 0, 0), root_pos=(0, -1.0, 0), rL=(-30, 0, 0), lL=(36, 0, 0), h=(-22, 0, 0)),
        0.24: P(hands=A(-36), b=(26, 0, 0), root_pos=(0, -1.0, 0), rL=(-28, 0, 0), lL=(34, 0, 0), h=(-20, 0, 0)),
        0.34: H})
    T["step"] = (0.30, {0: H,    # 沈み込んで跳ぶ回避
        0.05: P(hands=A(-34), b=(14, 0, 0), root_pos=(0, -2.2, 0), rL=(-30, 0, 10), lL=(20, 0, -10)),
        0.30: H})
    T["lunge"] = (0.60, {0: H,   # 両手の突き
        0.08: P(hands=A(-22), blade=(0, -0.05, -1), b=(22, 0, 0), root_pos=(0, -1.6, 0),
                rL=(-44, 0, 0), lL=(38, 0, 0), h=(-10, 0, 0)),
        0.45: P(hands=A(-22), blade=(0, -0.05, -1), b=(24, 0, 0), root_pos=(0, -1.6, 0),
                rL=(-46, 0, 0), lL=(40, 0, 0), h=(-12, 0, 0)),
        0.60: H})
    return T


def shared(name=None):
    S = {}
    S["heavy"] = (1.20, {0: H,
        0.25: P(rA=(-172, 0, 6), lA=(-168, 0, -6), b=(-16, 0, 0), h=(-12, 0, 0), root_pos=(0, 0.6, 0)),
        0.60: P(rA=(-176, 0, 6), lA=(-172, 0, -6), b=(-20, 0, 0), h=(-14, 0, 0), root_pos=(0, 0.8, 0)),
        0.74: P(rA=(-28, 0, 0), lA=(-34, 0, 0), b=(34, 0, 0), root_pos=(0, -2.4, -1.5),
                rL=(-40, 0, 0), lL=(30, 0, 0), h=(18, 0, 0)),
        0.95: P(rA=(-26, 0, 0), lA=(-30, 0, 0), b=(30, 0, 0), root_pos=(0, -2.2, -1.4),
                rL=(-38, 0, 0), lL=(28, 0, 0)),
        1.20: H})
    S["lunge"] = (0.60, {0: H,
        0.08: P(b=(22, 0, 0), rA=(-96, 0, 0), lA=(42, 0, -12), root_pos=(0, -1.6, 0),
                rL=(-44, 0, 0), lL=(38, 0, 0)),
        0.45: P(b=(24, 0, 0), rA=(-98, 0, 0), lA=(46, 0, -14), root_pos=(0, -1.6, 0),
                rL=(-46, 0, 0), lL=(40, 0, 0)),
        0.60: H})
    S["whirl"] = (0.36, {
        0: P(root=(0, 0, 0), rA=(-90, 0, 70), lA=(-90, 0, -70)),
        0.18: P(root=(0, 180, 0), rA=(-90, 0, 70), lA=(-90, 0, -70)),
        0.36: P(root=(0, 360, 0), rA=(-90, 0, 70), lA=(-90, 0, -70))})
    S["spin"] = (0.50, {0: H,
        0.25: P(root=(0, 200, 0), rA=(-92, 0, 60), lA=(-40, 0, -40)),
        0.50: P(root=(0, 360, 0))})
    S["plunge"] = (0.80, {0: H,
        0.15: P(rA=(-176, 0, 0), lA=(-170, 0, 0), rL=(-62, 0, 0), lL=(-58, 0, 0),
                root_pos=(0, 2.0, 0), h=(-10, 0, 0)),
        0.45: P(rA=(-18, 0, 0), lA=(-24, 0, 0), b=(36, 0, 0), rL=(-12, 0, 0), lL=(12, 0, 0),
                h=(26, 0, 0)),
        0.80: H})
    S["land"] = (0.70, {0: H,
        0.05: P(root_pos=(0, -4.2, 0), b=(36, 0, 0), rL=(-82, 0, 0), lL=(62, 0, 0),
                lA=old(-38, 0, 36), rA=old(-24, 0, -42), h=(-24, 0, 0)),
        0.45: P(root_pos=(0, -4.0, 0), b=(34, 0, 0), rL=(-80, 0, 0), lL=(60, 0, 0),
                lA=old(-36, 0, 34), rA=old(-22, 0, -40), h=(-22, 0, 0)),
        0.70: H})
    S["throw"] = (0.40, {0: H,
        0.12: P(rA=old(-162, 0, -22), b=old(-8, -26, 0), h=old(0, 22, 0)),
        0.22: P(rA=old(-72, 0, 10), b=old(10, 22, 0), h=old(0, -18, 0), rL=(-16, 0, 0)),
        0.40: H})
    S["rapid"] = (0.64, {0: H,
        0.08: P(rA=old(-112, 42, 0), lA=(-20, 0, 0), b=old(0, 22, 0)),
        0.16: P(rA=old(-70, -52, 0), lA=old(-112, -42, 0), b=old(0, -22, 0)),
        0.24: P(rA=old(-112, 42, 0), lA=old(-70, 52, 0), b=old(0, 22, 0)),
        0.32: P(rA=old(-70, -52, 0), lA=old(-112, -42, 0), b=old(0, -22, 0)),
        0.40: P(rA=old(-112, 42, 0), lA=old(-70, 52, 0), b=old(0, 22, 0)),
        0.48: P(rA=old(-150, 0, -20), lA=old(-150, 0, 20), b=(-10, 0, 0)),
        0.64: H})
    S["spinarm"] = (0.30, {
        0: P(rA=(-170, 0, 10), b=(-6, 0, 0)),
        0.15: P(rA=(-170, 180, 10), b=(-6, 0, 0)),
        0.30: P(rA=(-170, 360, 10), b=(-6, 0, 0))})
    S["ult_rise"] = (1.10, {0: H,
        0.30: P(rA=old(-180, 0, -8), lA=old(-24, 0, 34), h=(-24, 0, 0), b=(-8, 0, 0)),
        0.90: P(rA=old(-182, 0, -8), lA=old(-26, 0, 36), h=(-26, 0, 0), b=(-10, 0, 0)),
        1.10: P(rA=old(-176, 0, -8), lA=old(-22, 0, 30), h=(-20, 0, 0))})
    S["ult_slam"] = (0.90, {
        0: P(rA=old(-180, 0, -6), lA=old(-176, 0, 6), b=(-18, 0, 0)),
        0.18: P(rA=(-20, 0, 0), lA=(-26, 0, 0), b=(42, 0, 0), root_pos=(0, -3.0, -2.0),
                rL=(-48, 0, 0), lL=(36, 0, 0), h=(24, 0, 0)),
        0.60: P(rA=(-18, 0, 0), lA=(-24, 0, 0), b=(40, 0, 0), root_pos=(0, -2.8, -1.8),
                rL=(-46, 0, 0), lL=(34, 0, 0)),
        0.90: H})
    S["roar"] = (1.00, {0: H,
        0.20: P(rA=old(-24, 0, -80), lA=old(-24, 0, 80), b=(-22, 0, 0), h=(-34, 0, 0),
                root_pos=(0, -0.6, 0)),
        0.80: P(rA=old(-30, 0, -84), lA=old(-30, 0, 84), b=(-24, 0, 0), h=(-36, 0, 0),
                root_pos=(0, -0.6, 0)),
        1.00: H})
    S["cast"] = (0.90, {0: H,
        0.20: P(rA=old(-100, -20, 0), lA=old(-100, 20, 0), b=(-6, 0, 0)),
        0.70: P(rA=old(-104, -22, 0), lA=old(-104, 22, 0), b=(-8, 0, 0)),
        0.90: H})
    S["dash"] = (0.34, {0: H,
        0.06: P(b=(32, 0, 0), rA=old(48, 0, -14), lA=old(48, 0, 14), root_pos=(0, -1.0, 0),
                rL=(-30, 0, 0), lL=(36, 0, 0), h=(-26, 0, 0)),
        0.24: P(b=(30, 0, 0), rA=old(50, 0, -14), lA=old(50, 0, 14), root_pos=(0, -1.0, 0),
                rL=(-28, 0, 0), lL=(34, 0, 0), h=(-24, 0, 0)),
        0.34: H})
    S["step"] = (0.30, {0: H,
        0.05: P(b=(14, 0, 0), root_pos=(0, -2.2, 0), rA=old(-50, 20, 0), lA=old(-50, -20, 0),
                rL=old(-30, 0, -10), lL=old(20, 0, 10)),
        0.30: H})
    S["airjump"] = (0.42, flip_frames(0.42))
    S["frontflip"] = (0.55, flip_frames(0.55))
    S["backflip"] = (0.60, flip_frames(0.60, -1.0))
    S["crack"] = (0.50, {0: H,
        0.16: P(rA=old(-172, 0, -12), b=old(-12, -10, 0), h=(-8, 0, 0)),
        0.30: P(rA=old(-58, 0, 2), b=old(14, 12, 0), root_pos=(0, -0.6, 0)),
        0.50: H})
    S["bash"] = (0.40, {0: H,
        0.10: P(b=old(0, -24, 0), rA=old(-60, -30, 0)),
        0.20: P(b=old(14, 22, 0), rA=old(-92, 22, 0), root_pos=(0, -0.8, -3.0),
                rL=(-26, 0, 0), lL=(24, 0, 0)),
        0.40: H})
    S["stab"] = (0.36, {0: H,
        0.10: P(rA=old(-135, 0, -24), b=old(0, -18, 0)),
        0.20: P(rA=old(-48, 34, 12), b=old(16, 20, 0), root_pos=(0, -0.6, -1.0)),
        0.36: H})
    S["thrust"] = (0.40, {0: H,
        0.10: P(b=old(0, -30, 0), rA=old(-60, 0, -10), h=old(0, 28, 0)),
        0.20: P(b=old(12, 26, 0), rA=old(-96, 12, 0), lA=old(30, 0, 12), root_pos=(0, -0.8, -2.5),
                rL=(-30, 0, 0), lL=(28, 0, 0), h=old(-10, -24, 0)),
        0.40: H})
    S["uppercut"] = (0.46, {0: H,
        0.12: P(rA=old(25, 0, -10), b=(16, 0, 0), root_pos=(0, -2.2, 0), rL=(-30, 0, 0), lL=(20, 0, 0)),
        0.26: P(rA=old(-172, 0, 8), lA=old(-20, 0, 18), b=(-16, 0, 0), root_pos=(0, 1.2, 0), h=(-20, 0, 0)),
        0.46: H})
    S["clawx"] = (0.46, {0: H,
        0.12: P(rA=old(-165, 0, -32), lA=old(-165, 0, 32), b=(-10, 0, 0), h=(-10, 0, 0)),
        0.28: P(rA=old(-62, 0, 28), lA=old(-62, 0, -28), b=(16, 0, 0), root_pos=(0, -1.0, -1.0)),
        0.46: H})
    if name in TWO_HANDED:
        S.update(two_hand_moves())
    return S


LOOPING = {"whirl", "spinarm", "use", "aim", "guard"}
MOVE_KIND = {"dash", "step", "airjump", "frontflip", "backflip", "land"}

# 武器ごとに書き出す共通の技（スクリプトが実際に呼ぶもの。test_hd.py が、再生される全身モーションが
# すべて書き出されていることを確かめる）。機動と必殺技の掲げは全武器
COMMON = ("ult_rise", "airjump", "dash", "step", "land")
USES = {
    "greatsword": ("heavy", "lunge", "plunge", "ult_slam"),
    "twinblades": ("backflip", "frontflip", "rapid", "whirl"),
    "greataxe": ("heavy", "plunge", "ult_slam", "whirl"),
    "dagger": ("frontflip", "stab", "throw"),
    "bow": ("backflip",),
    "shield": ("bash", "cast", "lunge", "plunge"),
    "whip": ("cast", "crack", "spinarm"),
    "claws": ("clawx", "rapid", "roar", "uppercut"),
}
# 両手武器でも左手を柄から離す技（片手で掲げる・突く・地面に手をつく・走る）
FREE_L = {"lunge", "land", "ult_rise", "dash", "step"}
# 技ごとの解き方の指定（キーの時刻 → {"blade": 刃の向き, ...}）。武器ごとの上書きは (武器, 技)
MOVE_OPTS = {}

_MOTIONS = {}


def solved_motions(name):
    """{名前: (長さ, 絶対値のキー, 構え中か, 両手で柄を握るか)}。めり込みと両手持ちを解き直したもの。"""
    if name in _MOTIONS:
        return _MOTIONS[name]
    hold = hold_pose(name)
    two = HOLDS[name].get("grip2") is not None
    out = {"hold": (0.0, {0: hold}, False, two)}
    up = use_pose(name)
    if up:
        out["use"] = (0.0, {0: up}, True, False)
    for i, combo in enumerate(COMBOS[name]):
        length, frames = combo[0], combo[1]
        kopt = combo[2] if len(combo) > 2 else {}
        out[f"combo{i + 1}"] = (length, HP.solve_anim(_cloud(name), name, length, frames, hold,
                                                      key_opts=kopt), False, two)
    S = shared(name)
    own = two_hand_moves() if name in TWO_HANDED else {}
    for key in COMMON + USES[name]:
        length, frames = S[key]
        free = key in FREE_L and key not in own
        opts = {"free_l": free}
        kopt = MOVE_OPTS.get((name, key), MOVE_OPTS.get(key, {}))
        out[key] = (length, HP.solve_anim(_cloud(name), name, length, frames, hold, opts, kopt),
                    False, two and not free)
    _MOTIONS[name] = out
    return out


# ---- 解いた姿勢のキャッシュと並列化 -----------------------------------------
# 解くのは重い（武器ごとに数秒〜十数秒）ので、入力（持ち方・キー・モデル・解き方のコード）が
# 変わっていない武器は前回の結果を使い、変わった武器だけを CPU の数だけ並べて解く。
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "poses.json")


def _input_key(name):
    import hashlib
    import json as _json
    h = hashlib.sha256()
    h.update(_json.dumps(HOLDS[name], sort_keys=True, default=str).encode())
    S = shared(name)
    data = (_hold_raw(name), COMBOS[name], {k: S[k] for k in COMMON + USES[name]}, sorted(FREE_L),
            MOVE_OPTS.get(name), use_pose(name), sorted(TWO_HANDED))
    h.update(repr(data).encode())
    here = os.path.dirname(os.path.abspath(__file__))
    for f in ("hd_pose.py", "hd_scene.py", "hd_space.py"):
        h.update(open(os.path.join(here, f), "rb").read())
    h.update(open(os.path.join(RP, "models", "entity", f"hd_{name}.geo.json"), "rb").read())
    return h.hexdigest()


def _to_json(name):
    M = _MOTIONS[name]
    return {"hold": list(map(list, _HOLD_CACHE[name].items())),
            "motions": {k: [L, {repr(float(t)): {b: list(v) for b, v in f.items()} for t, f in fr.items()},
                            use, two] for k, (L, fr, use, two) in M.items()}}


def _from_json(name, d):
    _HOLD_CACHE[name] = {k: tuple(v) for k, v in d["hold"]}
    _MOTIONS[name] = {k: (L, {float(t): {b: tuple(v) for b, v in f.items()} for t, f in fr.items()}, use, two)
                      for k, (L, fr, use, two) in d["motions"].items()}


def _solve_one(name):
    solved_motions(name)
    return name, _to_json(name)


def prepare(names=None, jobs=None):
    """全武器の姿勢を用意する（キャッシュ → 足りない分を並列で解く）。"""
    import json as _json
    names = list(names or WEAPONS)
    try:
        cache = _json.load(open(CACHE, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    todo = []
    for n in names:
        k = _input_key(n)
        if n in _MOTIONS:
            continue
        if cache.get(n, {}).get("key") == k:
            _from_json(n, cache[n]["data"])
        else:
            todo.append((n, k))
    if todo:
        import concurrent.futures as cf
        import multiprocessing as mp
        jobs = jobs or min(len(todo), os.cpu_count() or 1)
        if jobs > 1:
            with cf.ProcessPoolExecutor(jobs, mp_context=mp.get_context("fork")) as ex:
                for n, d in ex.map(_solve_one, [n for n, _k in todo]):
                    _from_json(n, d)
        else:
            for n, _k in todo:
                _from_json(*_solve_one(n))
        for n, k in todo:
            cache[n] = {"key": k, "data": _to_json(n)}
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as fh:
            _json.dump(cache, fh)
    return [n for n, _k in todo]


def player_anims():
    A = {}
    n = f"animation.{NS}.p."
    for name in WEAPONS:
        hold = hold_pose(name)
        M = solved_motions(name)
        # 持ち姿勢（ループ・絶対値）
        A[f"{n}hold.{name}"] = build_anim(2.0, {0: {}, 1.0: {"b": (hold.get("b", (0, 0, 0))[0] + 0.8,
                                                                    *hold.get("b", (0, 0, 0))[1:])},
                                                2.0: {}}, hold, kind="hold", loop=True)
        # 構え（弓を引く・盾を構える）。弓の溜め（aim）と盾のガードも同じ姿勢
        if "use" in M:
            up = M["use"][1][0]
            A[f"{n}{name}.use"] = build_anim(1.0, {0: up, 1.0: up}, hold, kind="move", loop=True, smooth=False)
            A[f"{n}{name}.aim"] = A[f"{n}{name}.use"]
        for key, (length, frames, _use, _two) in M.items():
            if key in ("hold", "use"):
                continue
            kind = "move" if key in MOVE_KIND else "act"
            A[f"{n}{name}.{key}"] = build_anim(length, frames, hold, kind=kind, loop=key in LOOPING)
        A[f"{n}{name}.none"] = {"loop": False, "animation_length": 0.05, "bones": {}}
    A[f"{n}none"] = {"loop": False, "animation_length": 0.05, "bones": {}}
    return A


# 一回転して終わるモーション。終わり際に補間で逆回転しないよう、ブレンドなしで切る
NO_BLEND = {"whirl", "spin", "airjump", "frontflip", "backflip", "combo3"}


def script_meta(pa):
    """スクリプト側が使う情報（モーションの長さ・ブレンドの可否）を JS で書き出す。"""
    import json
    meta = {}
    prefix = f"animation.{NS}.p."
    for full, doc in pa.items():
        key = full[len(prefix):]
        last = key.split(".")[-1]
        spin = last in NO_BLEND and (last != "combo3" or key.split(".")[0] in ("dagger", "whip"))
        meta[key] = [round(doc.get("animation_length", 0.05), 3), 0 if spin else 1]
    path = os.path.join(os.path.dirname(RP), "hyperdim_BP", "scripts", "anim_meta.js")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("// 自動生成（tools/hyperdim/gen_hd_anim.py）。全身モーションの [長さ(秒), ブレンド可否]\n")
        fh.write("export const ANIM_META = ")
        json.dump(meta, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")


def main() -> None:
    solved = prepare()
    if solved:
        print(f"  solved poses: {', '.join(solved)}")
    wa = weapon_anims()
    write_json(os.path.join(ANIM_DIR, "hd_weapons.animation.json"),
               {"format_version": "1.10.0", "animations": wa})
    pa = player_anims()
    write_json(os.path.join(ANIM_DIR, "hd_player.animation.json"),
               {"format_version": "1.10.0", "animations": pa})
    script_meta(pa)
    for name in WEAPONS:
        write_json(os.path.join(ATT_DIR, f"{name}.attachable.json"), attachable(name, wa))
    print(f"  weapon animations: {len(wa)}  player animations: {len(pa)}  attachables: {len(WEAPONS)}")


if __name__ == "__main__":
    main()
