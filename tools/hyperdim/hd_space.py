# -*- coding: utf-8 -*-
"""統合版の「回転の向き」と「アタッチャブルの付き方」を、Mojang 公式サンプルの
実データ（盾・トライデント・望遠鏡・一人称の腕）から逆算した規則。

検証の要点（tools/hyperdim/reference/README.md に詳細）:

* ボーン／キューブの rotation [rx, ry, rz] は、モデル空間の右手系で
      R = Rz(-rz) · Ry(+ry) · Rx(-rx)      （X → Y → Z の順に掛かる）
  負の rx で腕が前に上がり、正の ry で右（-X 側）を向き、正の rz で右腕が外へ開く。
* `binding` で手のボーンに付けたボーンは、対象ボーンの pivot から (0, 24, 0) を引いた
  ずれを持つ。右手 (rightItem pivot [-6, 15, 1]) では (-6, -9, -1)、左手は (6, -9, -1)。
  つまり握りの位置を手 (-6, 13.2, 0) に置くには、ボーンを (0, 22.2, 1) 動かす。
* 三人称で何かを持つと、バニラの "holding" で右腕に rx = -18 が足される。
* 一人称の腕は rotation (95, -45, 115)・position (13.5, -10, 12)。一人称のカメラは
  この腕の空間で目の高さ (0, 26, 0) から +Z を向いて見ている（X は鏡映）。
"""
from __future__ import annotations

import math

import numpy as np

OFF_R = np.array([-6.0, -9.0, -1.0])     # 右手に bind したボーンのずれ
OFF_L = np.array([6.0, -9.0, -1.0])
HAND_R = np.array([-6.0, 13.2, 0.0])     # 腕を下ろした時の右の拳の中心（モデル空間）
HAND_L = np.array([6.0, 13.2, 0.0])
GRIP_POS = (HAND_R - OFF_R).round(3)     # 握りを拳へ運ぶボーン移動量 = (0, 22.2, 1)

HOLDING_RX = -18.0                        # バニラの持ち姿勢（右腕）
FP_ARM_ROT = (95.0, -45.0, 115.0)
FP_ARM_POS = (13.5, -10.0, 12.0)
FP_EYE = np.array([0.0, 26.0, 0.0])


def Rx(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot(rx, ry, rz) -> np.ndarray:
    """統合版の rotation [rx, ry, rz] をモデル空間の回転行列に。"""
    return Rz(-rz) @ Ry(ry) @ Rx(-rx)


def euler(M) -> tuple:
    """rot() の逆。M = Rz(-c) Ry(b) Rx(-a) を (a, b, c) に分解する。"""
    # M[2,0] = -sin(b)、cos(b) = |(M[2,1], M[2,2])|（極の近くでも精度が落ちない形）
    cb = math.hypot(M[2, 1], M[2, 2])
    b = math.degrees(math.atan2(-M[2, 0], cb))
    if cb > 1e-6:
        # M[2,1] = cos(b) * sin(-a), M[2,2] = cos(b) * cos(-a)
        a = -math.degrees(math.atan2(M[2, 1], M[2, 2]))
        # M[1,0] = sin(-c) cos(b), M[0,0] = cos(-c) cos(b)
        c = -math.degrees(math.atan2(M[1, 0], M[0, 0]))
    else:
        a = -math.degrees(math.atan2(-M[1, 2], M[1, 1]))
        c = 0.0
    return (round(a, 2), round(b, 2), round(c, 2))


def mat4(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def bone_local(pivot, rotation=(0, 0, 0), position=(0, 0, 0), scale=(1, 1, 1)):
    """統合版のボーンの局所変換: T(position) · T(pivot) · R · S · T(-pivot)。"""
    p = np.asarray(pivot, float)
    S = np.diag(np.broadcast_to(np.asarray(scale, float), (3,)))
    return mat4(t=np.asarray(position, float) + p) @ mat4(rot(*rotation) @ S) @ mat4(t=-p)


def beam_angles(d):
    """局所 -Z を方向 d へ向ける (rx, ry)。rot(rx, ry, 0) @ (0,0,-1) = d。"""
    x, y, z = d
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    x, y, z = x / n, y / n, z / n
    rx = math.degrees(math.asin(max(-1.0, min(1.0, -y))))
    ry = math.degrees(math.atan2(-x, -z))
    return rx, ry
