# -*- coding: utf-8 -*-
"""武器ごとの「持ち方」。

武器は「握り = 原点、刃 = -Z、刃先の幅 = ±Y」で作ってある。ここでは
* 三人称で武器をどの向きに構えるか（世界での刃の向き・刃の平の向き）
* どこを握るか（握りの点。両手武器は右手と左手の 2 点）
* その時の腕の姿勢（全身モーションで出す。バニラの持ち姿勢 -18° と歩きの腕振りは打ち消す）
を決め、hd_space の規則で逆算してアタッチャブルの rotation / position を出す。
左手は「柄の二つ目の握り点」に拳が来るよう、腕の角度を数値的に解く。
"""
from __future__ import annotations

import math

import numpy as np

from hd_space import (FP_ARM_POS, FP_ARM_ROT, GRIP_POS, HAND_L, HAND_R, HOLDING_RX, OFF_L,
                      OFF_R, bone_local, euler, mat4, rot)

ARM_R_PIVOT = np.array([-5.0, 22.0, 0.0])
ARM_L_PIVOT = np.array([5.0, 22.0, 0.0])
FIST_R = np.array([-6.0, 12.6, 0.0])      # 拳の先（腕を下ろした時）
FIST_L = np.array([6.0, 12.6, 0.0])


def frame(fwd, up):
    """前（刃の向き）と上（刃の幅の向き）から、武器空間→世界の回転行列。
    武器空間: -Z = 刃先、+Y = 刃の幅（上の刃）、+X = 平の法線。"""
    f = np.asarray(fwd, float)
    f /= np.linalg.norm(f)
    u = np.asarray(up, float)
    u = u - f * np.dot(u, f)
    u /= np.linalg.norm(u)
    x = np.cross(u, -f)          # +X = Y × Z  (Z = -f)
    return np.column_stack([x, u, -f])


def frame_x(fwd, flat_normal):
    """刃の向き fwd と、平（+X）を向けたい向き flat_normal から回転行列。"""
    f = np.asarray(fwd, float)
    f /= np.linalg.norm(f)
    x = np.asarray(flat_normal, float)
    x = x - f * np.dot(x, f)
    x /= np.linalg.norm(x)
    u = np.cross(-f, x)
    return np.column_stack([x, u, -f])


def frame_axes(la, wa, lb, wb):
    """武器空間の軸 la を世界の wa へ、lb をできるだけ wb へ向ける回転行列。"""
    def ortho(a, b):
        a = np.asarray(a, float)
        a /= np.linalg.norm(a)
        b = np.asarray(b, float)
        b = b - a * np.dot(a, b)
        b /= np.linalg.norm(b)
        return np.column_stack([a, b, np.cross(a, b)])
    L = ortho(la, lb)
    W = ortho(wa, wb)
    return W @ L.T


def arm_matrix(r, pivot):
    return bone_local(pivot, r)


def item_rotation(arm_r, world_R, pivot=ARM_R_PIVOT):
    """腕の姿勢 arm_r のとき、武器が世界で world_R の向きになるアタッチャブルの回転。"""
    A = rot(*arm_r)
    return euler(A.T @ world_R)


def item_position(arm_r, item_r, anchor=(0, 0, 0), left=False, nudge=(0, 0, 0), scale=1.0):
    """握りの点 anchor（武器空間）が拳に来るアタッチャブルの position。

    world = Arm · (OFF + position + R·anchor)。拳 = Arm · HAND。よって
    position = HAND - OFF - R·anchor（腕の回転に依らない）。nudge は拳からのずらし
    （腕の静止座標で。外へ逃がす等）。"""
    R = rot(*item_r)
    hand = HAND_L if left else HAND_R
    off = OFF_L if left else OFF_R
    p = hand - off - R @ (np.asarray(anchor, float) * scale) + np.asarray(nudge, float)
    return tuple(round(float(v), 2) for v in p)


def solve_arm_to(target, pivot=ARM_L_PIVOT, fist=FIST_L, start=(-40, 0, 0)):
    """拳 fist（静止座標）が target（世界）に来る腕の回転を探す。腕は伸びきった棒なので、
    届かない時は最も近い姿勢になる。ねじれ（腕の軸まわり）は 0 に寄せる。"""
    best = None
    t = np.asarray(target, float)

    def err(r):
        M = arm_matrix(r, pivot)
        p = (M @ np.array([*fist, 1.0]))[:3]
        return float(np.sum((p - t) ** 2)) + 0.0004 * (r[2] ** 2)
    r = np.array(start, float)
    step = 20.0
    cur = err(r)
    while step > 0.05:
        improved = False
        for i in range(3):
            for s in (-1, 1):
                q = r.copy()
                q[i] += s * step
                e = err(q)
                if e < cur:
                    r, cur, improved = q, e, True
        if not improved:
            step *= 0.5
    best = tuple(round(float(v), 1) for v in r)
    return best, math.sqrt(max(0.0, cur - 0.0004 * r[2] ** 2))


def world_point(arm_r, item_r, item_pos, local, left=False, scale=1.0):
    """武器空間の点 local が世界のどこに来るか。"""
    pivot = ARM_L_PIVOT if left else ARM_R_PIVOT
    off = OFF_L if left else OFF_R
    A = arm_matrix(arm_r, pivot)
    L = bone_local((0, 0, 0), item_r, item_pos, (scale, scale, scale))
    return (A @ mat4(t=off) @ L @ np.array([*local, 1.0]))[:3]


def fp_rotation(world_R):
    """一人称の腕（95,-45,115）のとき、カメラ空間（+Z が奥）で world_R の向きになる回転。"""
    return euler(rot(*FP_ARM_ROT).T @ world_R)


FP_ITEM_OFF = np.array([0.0, 0.0, -1.0])   # バニラ一人称 empty_hand の rightitem 移動


def fp_position(item_r, anchor=(0, 0, 0), nudge=(0, 0, 0), scale=1.0):
    """一人称では rightitem 自体が (0,0,-1) 動くので、その分を戻す。"""
    return item_position(FP_ARM_ROT, item_r, anchor, scale=scale,
                         nudge=tuple(np.asarray(nudge, float) - FP_ITEM_OFF))


def fp_place(cam_R, cam_point, anchor=(0, 0, 0), scale=1.0):
    """一人称をカメラ空間で直接決める。cam_R: 武器空間→カメラ空間（+X 右・+Y 上・+Z 奥）、
    cam_point: 握りの点を置く場所（目からの相対）。腕は描かれないので手の位置に縛られない。"""
    from hd_space import FP_EYE
    A = bone_local((-5.0, 22.0, 0.0), FP_ARM_ROT, FP_ARM_POS)
    r = euler(rot(*FP_ARM_ROT).T @ cam_R)
    R = rot(*r)
    desired = FP_EYE + np.asarray(cam_point, float)
    local = (np.linalg.inv(A) @ np.array([*desired, 1.0]))[:3]
    pos = local - FP_ITEM_OFF - OFF_R - R @ (np.asarray(anchor, float) * scale)
    return {"rotation": r, "position": tuple(round(float(v), 2) for v in pos), "scale": scale}


__all__ = ["frame", "item_rotation", "item_position", "solve_arm_to", "world_point",
           "fp_rotation", "fp_position", "GRIP_POS", "HOLDING_RX"]


# ===========================================================================
#  武器ごとの持ち方の設計
# ===========================================================================
def _n(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def _deg(d):
    return math.radians(d)


def _mirror(v):
    return (-v[0], v[1], v[2])


def _single(arm_target, fwd, up, anchor, scale, left=False, nudge=(0, 0, 0), start=(-30, 0, 0)):
    pivot, fist = (ARM_L_PIVOT, FIST_L) if left else (ARM_R_PIVOT, FIST_R)
    if isinstance(arm_target, tuple) and len(arm_target) == 3 and isinstance(arm_target[0], (int, float)) \
            and abs(arm_target[1]) > 6:
        arm, _err = solve_arm_to(arm_target, pivot, fist, start=start)
    else:
        arm = tuple(arm_target)
    ir = item_rotation(arm, frame(fwd, up))
    ip = item_position(arm, ir, anchor, left=left, nudge=nudge, scale=scale)
    return arm, ir, ip


# 両手武器の持ち方の調整値（体の空間: -Z が前、+Y が上、-X がプレイヤーの右）
# 手首は固定なので、構えの「前腕と刃の角度」がそのまま全部の振りに残る。振り下ろしの終わりで
# 刃が前〜前下を向くよう、大剣は水平に近い中段（前腕と 30° ほど）、斧は斧頭を前下に置く下段にする
GS_PITCH, GS_X, GS_UP, GS_PREF = 12.0, 0.06, (0, 1, 0), (-1.5, 16.5, -6.5)
AX_FWD = (-0.35, -math.sin(math.radians(45)), -math.cos(math.radians(45)))
AX_UP, AX_PREF = (0, 1, 0), (-1.5, 17.5, -6.5)


def two_hand_place(name, fwd, up, g1, g2, scale, pref, body=None, start=(-45.0, 10.0)):
    """両手武器の持ち方を「両方の拳が柄に届き、武器が体に入り込まない」所で決める。

    腕は肘の無い棒（肩から拳まで約 9.45）なので、両手で一本の柄を握れるのは体の正面の
    狭い範囲だけ。右腕の向き (rx, ry) を探して、右の拳に握り g1 を置いたとき
    * 左の拳が g2 に届く（左腕は g2 の方へまっすぐ向ける）
    * 武器が頭・胴・脚に入り込まない
    * 右の拳が希望の位置 pref に近い
    をなるべく満たす所を選ぶ。fwd / up は刃の向きと刃の幅の向き（体の空間で）。"""
    from hd_pose import aim_arm, penetration, pose_of, weapon_points
    from hd_scene import skeleton_world
    pts = weapon_points(name, 1.2)
    R_w = frame(fwd, up)
    pref = np.asarray(pref, float)
    body = body or {}

    def place(r):
        arm = (float(r[0]), float(r[1]), 0.0)
        ir = item_rotation(arm, R_w)
        ip = item_position(arm, ir, g1, scale=scale)
        lA, gap = aim_arm(world_point(arm, ir, ip, g2, scale=scale), prefer=(-50.0, 40.0, 0.0))
        return arm, ir, ip, lA, gap

    class _C:
        pass

    def cost(r):
        arm, ir, ip, lA, gap = place(r)
        pose = dict(body, rA=arm, lA=lA)
        W = skeleton_world(pose_of(pose))
        c = _C()
        c.parts = {"right": W["rightItem"] @ mat4(t=OFF_R) @ bone_local((0, 0, 0), ir, ip, (scale,) * 3) @ pts}
        c.tags = {"right": None}
        W2 = dict(W)
        W2["rightItem"] = np.eye(4)
        depth = penetration(c, W2, name)[0]
        fist = (arm_matrix(arm, ARM_R_PIVOT) @ np.array([*HAND_R, 1.0]))[:3]
        return (3.0 * max(0.0, gap - 0.3) ** 2 + 40.0 * max(0.0, depth - 0.2) ** 2
                + float(np.sum((fist - pref) ** 2)) / 9.0)

    r = np.array(start, float)
    cur = cost(r)
    step = 16.0
    while step >= 0.25:
        improved = True
        while improved:
            improved = False
            for i in range(2):
                for sgn in (-1.0, 1.0):
                    q = r.copy()
                    q[i] += sgn * step
                    c = cost(q)
                    if c < cur - 1e-9:
                        r, cur, improved = q, c, True
        step *= 0.5
    arm, ir, ip, lA, gap = place(np.round(r, 1))
    return {"arm_r": arm, "arm_l": tuple(round(float(v), 1) for v in lA),
            "tp": {"rotation": ir, "position": ip, "scale": scale}, "grip2": tuple(g2), "gap": gap}


def design():
    """{武器: {"arm_r", "arm_l", "tp", "fp", "left_tp", "use": {...}}}。
    tp / fp / left_tp の値は {"rotation", "position", "scale"}。
    一人称はカメラ空間（+X 右・+Y 上・+Z 奥、目からの相対）で握りの位置と向きを決める。"""
    H = {}

    # ---- 大剣: 両手の中段。刃はほぼ水平に前へ、柄は鍔のすぐ下（右）と柄頭寄り（左）を握る ----
    s = 0.66
    a = _deg(GS_PITCH)
    body = {"b": (4, 0, 0), "h": (-4, 0, 0)}
    H["greatsword"] = two_hand_place("greatsword", _n((GS_X, math.sin(a), -math.cos(a))), GS_UP,
                                     (0, 0, 1.4), (0, 0, 5.6), s, GS_PREF, body)
    H["greatsword"].update(body=body, fp=fp_place(frame_x(_n((-0.40, 0.70, 0.59)), (0.25, 0.1, -1)),
                                                  (10.5, -11.0, 15.0), (0, 0, 1.4), 0.58))

    # ---- 双剣: 両手に一振りずつ、切先を前下・やや外へ ----------------------
    s = 0.74
    fwd_r = _n((-0.22, -0.30, -0.93))
    arm_r, ir, ip = _single((-7.6, 12.8, -5.2), fwd_r, (0, 1, 0.2), (0, 0, 1.6), s)
    arm_l, irl, ipl = _single((7.6, 12.8, -5.2), _mirror(fwd_r), (0, 1, 0.2), (0, 0, 1.6), s, left=True,
                              start=(-30, 0, 0))
    H["twinblades"] = {"arm_r": arm_r, "arm_l": arm_l,
                       "tp": {"rotation": ir, "position": ip, "scale": s},
                       "left_tp": {"rotation": irl, "position": ipl, "scale": s},
                       "fp": fp_place(frame_x(_n((-0.50, 0.55, 0.67)), (0.2, 0.1, -1)), (11.0, -9.5, 14.0),
                                      (0, 0, 1.6), 0.66)}

    # ---- 両手斧: 下段。斧頭を前下（膝の高さ）に置き、柄尻寄りを両手で握る ----
    s = 0.64
    body = {"b": (6, 0, 0), "h": (-6, 0, 0)}
    # 柄尻寄りを両手で（右が上、左が石突き側）。石突きが腹に刺さらない角度にしてある
    H["greataxe"] = two_hand_place("greataxe", _n(AX_FWD), AX_UP, (0, 0, 2.0), (0, 0, 6.3), s, AX_PREF, body)
    H["greataxe"].update(body=body, fp=fp_place(frame_x(_n((-0.52, 0.80, 0.30)), (0.3, 0.1, -1)),
                                                (12.0, -12.0, 16.0), (0, 0, 6.3), 0.5))

    # ---- ダガー: 逆手。刃は拳の小指側から後ろ下へ、腿の外側に沿う ------------
    s = 0.78
    arm_r, ir, ip = _single((-7.4, 12.6, -4.0), _n((-0.18, -0.42, 0.89)), (-1, 0, 0), (0, 0, 2.4), s)
    H["dagger"] = {"arm_r": arm_r, "arm_l": (0, 0, 0),
                   "tp": {"rotation": ir, "position": ip, "scale": s},
                   "fp": fp_place(frame_x(_n((-0.70, -0.20, 0.68)), (0.1, 0.3, -1)), (9.5, -7.0, 12.0),
                                  (0, 0, 2.4), 0.8)}

    # ---- 弓: 体の横で前に傾けて持つ。引くと腕を前へ伸ばし、弓を立てる ----------
    s = 0.6
    arm_r, ir, ip = _single((-7.0, 12.8, -3.0), _n((0, -0.72, -0.69)), _n((0, 0.69, -0.72)), (0, 0, 0), s)
    aim_r = (-90.0, -6.0, 0.0)
    air = item_rotation(aim_r, frame((0, 0, -1), (0, 1, 0)))
    aip = item_position(aim_r, air, (0, 0, 0), scale=s)
    aim_l, _e = solve_arm_to((1.0, 23.0, -6.0), ARM_L_PIVOT, FIST_L, start=(-80, 30, 0))
    H["bow"] = {"arm_r": arm_r, "arm_l": (0, 0, 0),
                "tp": {"rotation": ir, "position": ip, "scale": s},
                "fp": fp_place(frame(_n((0.15, -0.30, 0.94)), _n((-0.25, 0.94, 0.25))), (10.5, -6.5, 15.0),
                               (0, 0, 0), 0.52),
                "use": {"arm_r": aim_r, "arm_l": aim_l,
                        "tp": {"rotation": air, "position": aip, "scale": s},
                        "fp": fp_place(frame(_n((0.22, 0.02, 1)), (-0.28, 1, 0)), (3.5, -3.0, 15.0), (0, 0, 0), 0.52)}}

    # ---- 盾: 前腕の外側に、面を外へ向けて（バニラの盾と同じ持ち方） ------------
    s = 0.7
    arm_r = (0.0, 0.0, 0.0)
    ir = item_rotation(arm_r, frame((-1, 0, 0), (0, 1, 0)))
    ip = item_position(arm_r, ir, (0, 0, 0), nudge=(-1.2, 3.6, 0), scale=s)
    g_arm, _e = solve_arm_to((-2.0, 17.0, -9.5), ARM_R_PIVOT, FIST_R, start=(-70, 20, 0))
    gir = item_rotation(g_arm, frame((0.15, 0, -1), (0, 1, 0)))
    gip = item_position(g_arm, gir, (0, 0, 0), scale=s)
    H["shield"] = {"arm_r": arm_r, "arm_l": (0, 0, 0),
                   "tp": {"rotation": ir, "position": ip, "scale": s},
                   "fp": fp_place(frame(_n((-0.85, 0.0, -0.53)), (0, 1, 0.05)), (11.0, -9.5, 14.0), (0, 0, 0), 0.6),
                   "use": {"arm_r": g_arm, "arm_l": (-45.0, 20.0, 0.0),
                           "tp": {"rotation": gir, "position": gip, "scale": s},
                           "fp": fp_place(frame(_n((-0.12, 0.0, 1.0)), (0, 1, 0)), (2.5, -4.5, 13.0), (0, 0, 0), 0.6)}}

    # ---- 鞭: 柄を前下に、鎖はとぐろを巻いて垂れる ---------------------------
    s = 0.8
    arm_r, ir, ip = _single((-6.6, 12.8, -3.6), _n((0.05, -0.30, -0.95)), (0, 1, 0), (0, 0, 2.8), s)
    H["whip"] = {"arm_r": arm_r, "arm_l": (0, 0, 0),
                 "tp": {"rotation": ir, "position": ip, "scale": s},
                 "fp": fp_place(frame_x(_n((-0.30, 0.55, 0.78)), (0.3, 0.1, -1)), (11.0, -10.0, 14.0),
                                (0, 0, 2.8), 0.62)}

    # ---- かぎ爪: 篭手が前腕を包む。腕を前に構えると爪が前下を向く ------------
    s = 1.0
    arm_r = (-48.0, -6.0, 6.0)
    arm_l = (-48.0, 6.0, -6.0)
    ir = (0.0, 0.0, 0.0)
    ip = item_position(arm_r, ir, (0, -1.4, -1.0), scale=s)
    ipl = item_position(arm_l, ir, (0, -1.4, -1.0), left=True, scale=s)
    H["claws"] = {"arm_r": arm_r, "arm_l": arm_l,
                  "tp": {"rotation": ir, "position": ip, "scale": s},
                  "left_tp": {"rotation": ir, "position": ipl, "scale": s},
                  "fp": fp_place(frame_axes((0, -1, 0), _n((-0.22, 0.10, 0.97)), (0, 0, -1), (0, 1, 0.1)),
                                 (10.0, -6.5, 12.0), (0, -1.4, -1.0), 0.75)}
    return H
