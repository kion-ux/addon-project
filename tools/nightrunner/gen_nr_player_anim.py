# -*- coding: utf-8 -*-
"""NIGHT RUNNER — プレイヤーのモーション（パルクール・素手の戦闘・武器・道具）を生成する。

出力: packs/nightrunner_RP/animations/nr_player.animation.json（animation.nr.p.<名前>）
      nr_registry.PLAYER_ANIMS の**全部**と animation.nr.p.none（0.05 秒の空アニメ）。

スクリプトは player.playAnimation("animation.nr.p.<名前>", {controller, blendOutTime, stopExpression,
nextState}) で重ねる（DESIGN.md §13、reference/rendering.md §5・§9、チェックリスト P1〜P6）。
推奨の層・ブレンド・止め方は PLAYER_ANIM_META（下）にまとめてあり、gen_nr_data_js から import できる。

────────────────────────────────────────────────────────────────────────────
■ バニラのプレイヤーの骨格（bedrock-samples geometry.humanoid.custom）
    root(0,0,0) ─ waist(0,12,0) ─ body(0,24,0) ─ head(0,24,0) / rightArm(-5,22,0) / leftArm(5,22,0)
               └ rightLeg(-1.9,12,0) / leftLeg(1.9,12,0)          ← 脚は root の子（waist の子ではない）
  回転 [rx, ry, rz] = Rz(-rz)·Ry(ry)·Rx(-rx)（nr_preview.rot と同じ）。負の rx で腕・脚が前へ、
  正の rx で胴が前へ倒れる、正の ry で右（-X）を向く、正の rz で右腕が外へ開き胴の上が左（+X）へ傾く。
  前 = -Z、右 = -X、上 = +Y（モデル単位 1/16 ブロック）。

■ 決め事（なぜこう書くか）
* **root の回転は書かない**。バニラのしゃがみ（animation.player.sneaking）が root.rotation.x に
  "28.0 - this" を書くので、評価順しだいで root の回転が消える。全身の回転（前転・寝そべり）は
  waist と両脚に同じ回転を与え、root の position で回転の中心を合わせる（脚と waist の pivot は
  同じ高さ・同じ z なので X 軸まわりは厳密に「腰の線まわりの全身の回転」になる）。
* **しゃがみの打ち消し**（unsneak）: パルクールの多く（スライディング = ダッシュ中のスニーク、受け身、
  ドロップキック）はスニーク中に再生される。q.is_sneaking のときバニラの root（回転 28°・位置
  (0,1.25,9)）・脚 -28°・胴と頭の沈み・腕 -5.7° を行列で厳密に打ち消す値を "q.is_sneaking ? A : B" で書く。
  root の回転には触らないので評価順に依らない。
* **頭は relative_to entity**（バニラの look_at_target.default と同じ）。頭の値は「体（エンティティ）基準の
  向き」で書く。何も書かなければ頭は視線を向いたまま（体を倒しても顔は前）。宙返りなど体と一緒に
  回したいクリップは胴の回転を頭へ足す（head="follow"）。
* **一人称**: 全チャンネルを v.is_first_person ? … で包む。胴・脚・頭・位置は一人称で 0、腕だけ
  FP 倍（既定 0.25）。構え・狙いは 0（一人称の持ち方は武器のアタッチャブル側）。
* **バニラの打ち消し**（三人称だけ・キーの重み w で出入り）:
    歩きの腕振り   rightArm.x -tcos0 / leftArm.x +tcos0、持つと右腕 -18° で振りが半分
    歩きの脚振り   rightLeg.x +1.4·tcos0 / leftLeg.x -1.4·tcos0
    攻撃の振り     animation.player.attack.rotations（HyperDim の ATK_CANCEL と同じ式。重みなし）
  一発ものは最初と最後のキーで w = 0（P3: 最初と最後のキーが 0）。ループは w = 1。
* **層**（PLAYER_ANIM_META の layer）:
    nr.p.hold   武器の構え・全力疾走のループ（hold_* / sprint_*）。絶対姿勢（バニラの持つ -18° と
                腕振りを打ち消して、武器ごとに一部だけ振りを残す）
    nr.p.act    武器の振り・装填・投擲・狙い（*_aim は loop）・道具・素手の技。武器の動きは
                ANIM_SETS の idle（hold_*）**からの差分**なので、構えの層が流れている前提
    nr.p.recoil 撃った反動・ポンプ・ボルト（小さな加算。狙いを止めずに重ねる）
    nr.p.move   パルクールの全身。**再生中は nr.p.hold を止める**（none を流し、終わったら構えを流し直す）
                — 構えの腕に足されると登り・ぶら下がりの腕が回り過ぎるため
* 一回転して終わるもの（roll、slash_2h_heavy の回転）は最後のキーが 360°。blendOutTime 0 で切ること
  （meta の blend が 0）。

■ 確認
  python3 tools/nightrunner/gen_nr_player_anim.py --qa   # build_preview/nightrunner/player_anim/ に確認画像
  （NR_PREVIEW=1 でも描く）。Steve と同じ寸法・ボーン名の模型を nr_preview で描き、頭の relative_to も再現する。
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import nr_registry as REG  # noqa: E402
from nr_common import PREVIEW, RP, SCRATCH, write_json  # noqa: E402

try:  # 登録データの入口（無ければカタログを直接）
    import nr_spec as SPEC  # noqa: E402
except Exception:  # noqa: BLE001
    import nr_spec_catalog as SPEC  # type: ignore  # noqa: E402

OUT = os.path.join(RP, "animations", "nr_player.animation.json")
PREFIX = "animation.nr.p."
QA_DIR = os.path.join(SCRATCH, "player_anim")

# ===========================================================================
#  1. 骨格（バニラの geometry.humanoid.custom と同じ pivot・箱）
# ===========================================================================
PIV = {
    "root": (0.0, 0.0, 0.0), "waist": (0.0, 12.0, 0.0), "body": (0.0, 24.0, 0.0), "head": (0.0, 24.0, 0.0),
    "rightArm": (-5.0, 22.0, 0.0), "leftArm": (5.0, 22.0, 0.0),
    "rightLeg": (-1.9, 12.0, 0.0), "leftLeg": (1.9, 12.0, 0.0),
}
PARENT = {"waist": "root", "body": "waist", "head": "body", "rightArm": "body", "leftArm": "body",
          "rightLeg": "root", "leftLeg": "root"}
ORDER = ("root", "waist", "body", "head", "rightArm", "leftArm", "rightLeg", "leftLeg")
# 箱（origin, size）。接地・重心・確認画像に使う
BOXES = {
    "head": ((-4, 24, -4), (8, 8, 8)), "body": ((-4, 12, -2), (8, 12, 4)),
    "rightArm": ((-8, 12, -2), (4, 12, 4)), "leftArm": ((4, 12, -2), (4, 12, 4)),
    "rightLeg": ((-3.9, 0, -2), (4, 12, 4)), "leftLeg": ((-0.1, 0, -2), (4, 12, 4)),
}
HIP = np.array(PIV["waist"])
FIST = {"rightArm": np.array([-6.0, 13.2, 0.0]), "leftArm": np.array([6.0, 13.2, 0.0])}
# 手に持った物の向き（腕の局所）。腕を下ろした時に前・少し上（バニラの三人称の持ち方に近い）
ITEM_DIR = np.array([0.0, math.sin(math.radians(15)), -math.cos(math.radians(15))])

# しゃがみ（animation.player.sneaking）: root 回転 28°（"28 - this"）・位置 (0,1.25,9)、脚 -28°、
# body 位置 -2、head 位置 -1、両腕 -5.7°
SNEAK_ROOT_ROT = 28.0
SNEAK_ROOT_POS = np.array([0.0, 1.25, 9.0])
SNEAK_LEG_X = -28.0
SNEAK_ARM_X = -5.7

# ===========================================================================
#  2. 回転の数学
# ===========================================================================


def _rx(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1.0, 0], [-s, 0, c]])


def _rz(a):
    a = math.radians(a)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rot(e) -> np.ndarray:
    """統合版の rotation [rx, ry, rz] → 回転行列 Rz(-rz)·Ry(ry)·Rx(-rx)。"""
    return _rz(-e[2]) @ _ry(e[1]) @ _rx(-e[0])


def euler(R: np.ndarray, prev=(0.0, 0.0, 0.0)) -> np.ndarray:
    """回転行列 → [rx, ry, rz]。二つの解と 360° の倍数のうち prev に一番近いもの（キーの間で跳ばない）。"""
    prev = np.asarray(prev, float)
    sb = float(np.clip(-R[2, 0], -1.0, 1.0))
    b1 = math.asin(sb)
    if abs(math.cos(b1)) > 1e-7:
        a1 = math.atan2(R[2, 1], R[2, 2])
        c1 = math.atan2(R[1, 0], R[0, 0])
    else:                                  # ジンバルロック: a と c は和（差）しか決まらない
        c1 = math.radians(-prev[2])
        a1 = math.atan2(-R[1, 2], R[1, 1]) + (c1 if sb > 0 else -c1)
    best, bd = None, 1e18
    for a, b, c in ((a1, b1, c1), (a1 + math.pi, math.pi - b1, c1 + math.pi)):
        e = np.degrees([-a, b, -c])
        e = prev + (e - prev + 180.0) % 360.0 - 180.0
        d = float(np.sum((e - prev) ** 2))
        if d < bd:
            best, bd = e, d
    return best


def look_rot(d, a0, twist=0.0, guess=None) -> np.ndarray:
    """腕・脚の向き: 休みの向き a0（局所の単位ベクトル）を d へ向ける [rx, ry, twist]。ガウス・ニュートン。"""
    d = np.asarray(d, float)
    d = d / max(np.linalg.norm(d), 1e-9)
    if guess is None:
        rx0 = -math.degrees(math.acos(float(np.clip(-d[1], -1, 1))))
        s = math.sin(math.radians(rx0))
        ry0 = math.degrees(math.atan2(d[0] / s, d[2] / s)) if abs(s) > 1e-6 else 0.0
        x = np.array([rx0, ry0])
    else:
        x = np.array([guess[0], guess[1]], float)
    for _ in range(30):
        f = rot((x[0], x[1], twist)) @ a0 - d
        J = np.zeros((3, 2))
        for i in range(2):
            dx = np.zeros(2)
            dx[i] = 1e-3
            J[:, i] = (rot((x[0] + dx[0], x[1] + dx[1], twist)) @ a0 - d - f) / 1e-3
        step, *_ = np.linalg.lstsq(J, -f, rcond=None)
        x = x + np.clip(step, -40, 40)
        if np.linalg.norm(step) < 1e-4:
            break
    return np.array([x[0], x[1], twist])


def _T(R=None, t=(0, 0, 0)) -> np.ndarray:
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    M[:3, 3] = t
    return M


def bone_local(bone, e, pos=(0, 0, 0)) -> np.ndarray:
    """T(position)·T(pivot)·R·T(-pivot)。"""
    p = np.array(PIV[bone])
    R = rot(e)
    return _T(R, np.asarray(pos, float) + p - R @ p)


def fk(ch: Dict[str, dict], root_rot=(0.0, 0.0, 0.0)) -> Dict[str, np.ndarray]:
    """チャンネル {bone: {"rot", "pos"}} → ワールド行列。頭は relative_to entity（回転は体基準）。"""
    W = {}
    for b in ORDER:
        c = ch.get(b, {})
        e = np.asarray(c.get("rot", (0, 0, 0)), float)
        pos = np.asarray(c.get("pos", (0, 0, 0)), float)
        if b == "root":
            W[b] = bone_local(b, np.asarray(root_rot) + e, pos)
            continue
        if b == "head":
            wp = W["body"] @ np.append(np.array(PIV["head"]) + pos, 1.0)
            R = rot(e)
            W[b] = _T(R, wp[:3] - R @ np.array(PIV["head"]))
            continue
        W[b] = W[PARENT[b]] @ bone_local(b, e, pos)
    return W


def box_corners(bone) -> np.ndarray:
    o, s = BOXES[bone]
    o = np.array(o, float)
    s = np.array(s, float)
    return np.array([o + s * np.array([i, j, k]) for i in (0, 1) for j in (0, 1) for k in (0, 1)])


def min_y(W) -> float:
    ys = []
    for b in BOXES:
        P = box_corners(b)
        ys.append(((W[b][:3, :3] @ P.T).T + W[b][:3, 3])[:, 1].min())
    return float(min(ys))


def centre_of_mass(W) -> np.ndarray:
    tot, acc = 0.0, np.zeros(3)
    for b, (o, s) in BOXES.items():
        m = s[0] * s[1] * s[2]
        cen = np.array(o, float) + np.array(s, float) / 2
        acc += m * ((W[b] @ np.append(cen, 1.0))[:3])
        tot += m
    return acc / tot


# ===========================================================================
#  3. キーの姿勢 → ボーンのチャンネル
# ===========================================================================
#  姿勢の書き方（キーごとの辞書。書かない部位は休み（または構え）のまま）:
#    fb=(x,y,z)  全身の回転（中心 c、既定はクリップの centre）   tr=(x,y,z) 全身の平行移動
#    w=(x,y,z)   胴（waist、腰まわり）  b=(x,y,z) 胸（body、首の付け根まわり。主に y のひねり）
#    rA/lA       腕（胸に対して）     rAw/lAw 腕（体＝エンティティ基準の向き）
#    rAt/lAt     腕で指す点（体の座標、fb の前）  lA="grip" 両手持ち（右手の持ち物の軸に沿って左手を置く）
#    rL/lL       脚（fb の枠で）      rLw/lLw 脚（体基準の向き）
#    h           頭（胸に対して。胴と一緒に回る）  hw 頭（体基準）  hl 頭（視線に足すだけ）
#    rAp/lAp/bp  腕・胸の位置のずれ   ground=True 一番低い点を y=0 に（接地）   wgt 打ち消しの重み
#    aim         狙い（q.target_x/y_rotation を腕へ足す）の重み

_ZERO = np.zeros(3)


def _v(P, k, d=_ZERO):
    v = P.get(k)
    return np.asarray(v, float) if v is not None else np.asarray(d, float)


@dataclass
class Clip:
    name: str
    length: float
    keys: List[Tuple[float, dict]]
    kind: str = "move"           # move / free / item / act / hold / aim / recoil
    loop: object = False         # False / True / "hold_on_last_frame"
    base: Optional[str] = None   # 差分の元にする構え（hold_*）
    fp: Optional[float] = None   # 一人称の腕の倍率（None で種類の既定）
    unsneak: Optional[bool] = None
    head: str = "look"           # look / follow
    centre: Tuple[float, float, float] = (0.0, 12.0, 0.0)
    grip: Optional[float] = None  # 両手持ち: 左手を右手の持ち物の軸に沿ってずらす量（+ 前・- 柄頭）
    grip_side: float = 0.0       # 両手持ち: 左手を横（+X = 体の左）へずらす量
    legs: Optional[bool] = None  # 脚の歩きを打ち消すか
    atk: Optional[bool] = None   # 攻撃の振りを打ち消すか
    arms: Optional[str] = None   # 腕の打ち消し: None / "always" / "if_empty" / "hold"
    keep: Tuple[float, float] = (0.0, 0.0)  # hold: 歩きの腕振りを残す割合（右, 左。左に負で右と同じ向き）
    aim: Optional[str] = None    # "crossbow" / "bow" / "point"（右腕だけ）
    first_w: Optional[float] = None   # 最初のキーの打ち消しの重み（続きのモーションは 1）
    last_w: Optional[float] = None
    desc: str = ""
    proxy: str = ""              # 確認画像の持ち物: "" / blade / blade2 / spear / gun / bow / small
    meta: dict = field(default_factory=dict)


KIND_DEFAULTS = {
    #        fp    unsneak legs   atk    arms
    "move":  (0.25, True,  True,  False, "always"),
    "free":  (0.25, False, True,  True,  "if_empty"),
    "item":  (0.25, False, False, False, "always"),
    "act":   (0.25, False, False, True,  None),
    "hold":  (0.0,  False, False, False, "hold"),
    "aim":   (0.0,  False, False, True,  None),
    "recoil": (0.5, False, False, False, None),
}


def _dflt(c: Clip, attr, idx):
    v = getattr(c, attr)
    return KIND_DEFAULTS[c.kind][idx] if v is None else v


class Solved:
    """1 キーの解: ch[bone] = {"rot": e, "pos": p}（三人称・しゃがみ無し）と、しゃがみ時の値 sn。"""

    def __init__(self):
        self.ch: Dict[str, dict] = {}
        self.sn: Dict[str, dict] = {}
        self.W = None
        self.head_written = False


def solve_pose(P: dict, clip: Clip, prev: Optional[Solved], base: Optional[Solved] = None) -> Solved:
    """姿勢の辞書を解く。base（構え）があれば書かれていない腕は構えのまま（絶対値）。"""
    S = Solved()
    pv = (lambda b, k="rot": prev.ch.get(b, {}).get(k, _ZERO)) if prev else (lambda b, k="rot": _ZERO)
    c = _v(P, "c", clip.centre)
    tr = _v(P, "tr")
    Rfb = rot(_v(P, "fb"))
    Rw = rot(_v(P, "w"))
    Rb = rot(_v(P, "b"))
    I3 = np.eye(3)
    # root（位置だけ）: 腰の線まわりの回転を中心 c まわりに直す
    S.ch["root"] = {"pos": tr + (Rfb - I3) @ (HIP - c)}
    S.ch["waist"] = {"rot": euler(Rfb @ Rw, pv("waist"))}
    S.ch["body"] = {"rot": euler(Rb, pv("body")), "pos": _v(P, "bp")}
    # 脚
    for side, bone in (("r", "rightLeg"), ("l", "leftLeg")):
        if f"{side}Lw" in P:
            RL = rot(_v(P, f"{side}Lw"))
        else:
            RL = Rfb @ rot(_v(P, f"{side}L"))
        p = np.array(PIV[bone])
        S.ch[bone] = {"rot": euler(RL, pv(bone)), "pos": (Rfb - I3) @ (p - HIP)}
    # ここまでで胸のワールド行列を出す（腕の向き・狙いの点に使う）
    W = fk(S.ch)
    C = W["body"][:3, :3]
    F = lambda x: Rfb @ (np.asarray(x, float) - c) + c + tr  # noqa: E731  体の座標 → ワールド
    for side, bone in (("r", "rightArm"), ("l", "leftArm")):
        key = f"{side}A"
        a0 = FIST[bone] - np.array(PIV[bone])
        a0 = a0 / np.linalg.norm(a0)
        g = pv(bone)
        if P.get(key) == "grip":
            continue                                     # 右腕のあと
        if f"{key}w" in P:
            e = euler(C.T @ rot(_v(P, f"{key}w")), g)
        elif f"{key}t" in P:
            sh = W["body"] @ np.append(PIV[bone], 1.0)
            d = C.T @ (F(P[f"{key}t"]) - sh[:3])
            e = look_rot(d, a0, float(P.get(f"{key}z", 0.0)), g if prev else None)
        elif key in P:
            e = _v(P, key)
        elif base is not None:
            e = np.asarray(base.ch[bone]["rot"], float)
        else:
            e = _ZERO
        S.ch[bone] = {"rot": np.asarray(e, float), "pos": _v(P, f"{key}p")}
    if P.get("lA") == "grip" or (clip.grip is not None and "lA" not in P and "lAw" not in P and "lAt" not in P):
        W = fk(S.ch)
        Wr = W["rightArm"]
        fist = (Wr @ np.append(FIST["rightArm"], 1.0))[:3]
        axis = Wr[:3, :3] @ ITEM_DIR
        side = np.array([clip.grip_side, 0, 0])
        target = fist + axis * float(clip.grip or 0.0) + W["body"][:3, :3] @ side
        sh = (W["body"] @ np.append(PIV["leftArm"], 1.0))[:3]
        a0 = FIST["leftArm"] - np.array(PIV["leftArm"])
        a0 = a0 / np.linalg.norm(a0)
        d = C.T @ (target - sh)
        guess = pv("leftArm") if prev else (base.ch["leftArm"]["rot"] if base is not None else None)
        S.ch["leftArm"] = {"rot": look_rot(d, a0, float(P.get("lAz", 0.0)), guess), "pos": _v(P, "lAp")}
    # 頭（体基準の向き）
    if "hw" in P:
        S.ch["head"] = {"rot": euler(rot(_v(P, "hw")), pv("head"))}
        S.head_written = True
    elif "h" in P or clip.head == "follow":
        S.ch["head"] = {"rot": euler(C @ rot(_v(P, "h")), pv("head"))}
        S.head_written = True
    else:
        S.ch["head"] = {"rot": _v(P, "hl")}
        S.head_written = "hl" in P
    # 接地: 一番低い点を y = ground に
    S.W = fk(S.ch)
    if P.get("ground") is not None and P.get("ground") is not False:
        gy = 0.0 if P["ground"] is True else float(P["ground"])
        dy = gy - min_y(S.W)
        S.ch["root"]["pos"] = S.ch["root"]["pos"] + np.array([0.0, dy, 0.0])
        S.W = fk(S.ch)
    # しゃがみ時の値（M = T(root)·Rx(28) を子で打ち消す。§ 冒頭）
    U = rot((-SNEAK_ROOT_ROT, 0.0, 0.0))
    for b, cv in S.ch.items():
        S.sn[b] = {k: np.array(v, float) for k, v in cv.items()}
    S.sn["root"]["pos"] = S.ch["root"]["pos"] - SNEAK_ROOT_POS
    h = HIP
    S.sn["waist"]["rot"] = euler(U @ rot(S.ch["waist"]["rot"]), S.ch["waist"]["rot"] - [SNEAK_ROOT_ROT, 0, 0])
    S.sn["waist"]["pos"] = U @ h - h
    for bone in ("rightLeg", "leftLeg"):
        p = np.array(PIV[bone])
        R = rot(S.ch[bone]["rot"])
        e = euler(U @ R, S.ch[bone]["rot"] - [SNEAK_ROOT_ROT, 0, 0]) - [SNEAK_LEG_X, 0, 0]
        S.sn[bone]["rot"] = e
        S.sn[bone]["pos"] = U @ S.ch[bone]["pos"] + (U @ p - p)
    S.sn["body"]["pos"] = S.ch["body"].get("pos", _ZERO) + np.array([0.0, 2.0, 0.0])
    S.sn["head"]["pos"] = np.array([0.0, 1.0, 0.0])
    for bone in ("rightArm", "leftArm"):
        S.sn[bone]["rot"] = S.ch[bone]["rot"] - [SNEAK_ARM_X, 0, 0]
    return S


# ===========================================================================
#  4. Molang の組み立て
# ===========================================================================


def num(x, nd=2) -> str:
    v = round(float(x), nd)
    if abs(v) < 10 ** -nd / 2:
        return "0"
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return s


_AT = "math.clamp(v.attack_time, 0.0, 1.0)"
_S4 = f"math.sin((1.0 - math.pow(1.0 - {_AT}, 4.0)) * 180.0)"
# バニラの攻撃の振り（animation.player.attack.rotations）を打ち消す項（三人称）
ATK_TERMS = {
    ("rightArm", 0): f"({_S4} * 1.2 + math.sin({_AT} * 180.0)) * 30.0",
    ("rightArm", 1): f"({_S4} != 0.0 ? 30.0 - 90.0 * {_S4} : 0.0)",
    ("leftArm", 0): f"({_S4} * 1.2 + math.sin({_AT} * 180.0)) * 10.0",
    ("body", 1): f"math.sin(360.0 * math.sqrt({_AT})) * -5.0",
}
# 歩きの腕振り・持つ -18° の打ち消し
ARM_TERMS = {
    "always": {("rightArm", 0): "(v.is_holding_right ? 18.0 + v.tcos0 * 0.5 : v.tcos0)",
               ("leftArm", 0): "((v.is_holding_left ?? 0.0) ? 18.0 - v.tcos0 * 0.5 : -v.tcos0)"},
    "if_empty": {("rightArm", 0): "(v.is_holding_right ? 0.0 : v.tcos0)",
                 ("leftArm", 0): "(v.is_holding_right ? 0.0 : -v.tcos0)"},
}
LEG_TERMS = {("rightLeg", 0): "v.tcos0 * -1.4", ("leftLeg", 0): "v.tcos0 * 1.4"}
# 狙い: 視線の上下・左右を腕へ（バニラの crossbow_hold / bow_equipped と同じ。しゃがむと体が 28° 前へ傾く分を戻す）
_AX = "q.target_x_rotation - q.is_sneaking * 27.0"
AIM_TERMS = {
    "crossbow": {("rightArm", 0): _AX, ("rightArm", 1): "math.clamp(q.target_y_rotation, -60.0, 45.0)",
                 ("leftArm", 0): _AX, ("leftArm", 1): "math.clamp(q.target_y_rotation, -45.0, 5.0)"},
    "bow": {("rightArm", 0): _AX, ("rightArm", 1): "q.target_y_rotation",
            ("leftArm", 0): _AX, ("leftArm", 1): "q.target_y_rotation"},
    "point": {("rightArm", 0): _AX, ("rightArm", 1): "math.clamp(q.target_y_rotation, -60.0, 45.0)"},
}


def hold_terms(keep):
    kr, kl = keep
    return {("rightArm", 0): f"(v.is_holding_right ? 18.0 + v.tcos0 * {num(0.5 - kr, 3)} : v.tcos0 * {num(1 - kr, 3)})",
            ("leftArm", 0): f"((v.is_holding_left ?? 0.0) ? 18.0 - v.tcos0 * {num(0.5 - kl, 3)} : "
                            f"v.tcos0 * {num(kl - 1, 3)})"}


def _sum(base: str, terms: List[str]) -> str:
    parts = [base] if base != "0" else []
    parts += terms
    if not parts:
        return "0"
    return " + ".join(parts)


def _weighted(expr: str, w: float) -> Optional[str]:
    if abs(w) < 1e-4:
        return None
    if abs(w - 1.0) < 1e-4:
        return expr
    return f"{num(w, 3)} * {expr}"


# ===========================================================================
#  5. クリップ → JSON
# ===========================================================================
ARM_BONES = ("rightArm", "leftArm")
ROT_ND, POS_ND = 1, 2


def _key_weights(clip: Clip, n: int) -> List[float]:
    if clip.loop is True or clip.kind in ("hold", "aim"):
        return [1.0] * n
    w = [1.0] * n
    w[0] = 0.0 if clip.first_w is None else clip.first_w
    if clip.loop != "hold_on_last_frame":
        w[-1] = 0.0 if clip.last_w is None else clip.last_w
    return w


_BASE_CACHE: Dict[str, Solved] = {}


def base_solved(name: Optional[str]) -> Optional[Solved]:
    if not name:
        return None
    if name not in _BASE_CACHE:
        bc = CLIPS[name]
        _BASE_CACHE[name] = solve_pose(bc.keys[0][1], bc, None)
    return _BASE_CACHE[name]


def solve_clip(clip: Clip) -> List[Tuple[float, Solved, dict]]:
    base = base_solved(clip.base) if clip.kind in ("act", "aim") else None
    out = []
    prev = base
    for t, P in clip.keys:
        S = solve_pose(P, clip, prev, base)
        out.append((t, S, P))
        prev = S
    return out


def build_clip(clip: Clip) -> dict:
    sol = solve_clip(clip)
    n = len(sol)
    wts = [float(P.get("wgt", w)) for (_t, _S, P), w in zip(sol, _key_weights(clip, n))]
    aimw = [float(P.get("aim", w)) for (_t, _S, P), w in zip(sol, wts)]
    base = base_solved(clip.base) if clip.kind in ("act", "aim") else None
    fp_k = _dflt(clip, "fp", 0)
    unsneak = _dflt(clip, "unsneak", 1)
    legs = _dflt(clip, "legs", 2)
    atk = _dflt(clip, "atk", 3)
    arms = _dflt(clip, "arms", 4)
    absolute = clip.kind == "hold"
    # 項（bone, axis）→ [(式, 重みの並び)]
    terms: Dict[Tuple[str, int], List[Tuple[str, List[float]]]] = {}

    def add_terms(tbl, weights):
        for k, e in tbl.items():
            terms.setdefault(k, []).append((e, weights))

    if arms == "hold":
        add_terms(hold_terms(clip.keep), [1.0] * n)
    elif arms in ARM_TERMS:
        add_terms(ARM_TERMS[arms], wts)
    if legs:
        add_terms(LEG_TERMS, wts)
    if atk:
        add_terms(ATK_TERMS, [1.0] * n)
    if clip.aim:
        add_terms(AIM_TERMS[clip.aim], aimw)

    bones_out = {}
    for bone in ("root", "waist", "body", "head", "rightArm", "leftArm", "rightLeg", "leftLeg"):
        for chan in ("rot", "pos"):
            is_rot = chan == "rot"
            if bone == "root" and is_rot:
                continue
            nd = ROT_ND if is_rot else POS_ND
            vals, svals = [], []
            for (t, S, P) in sol:
                v = np.asarray(S.ch.get(bone, {}).get(chan, _ZERO), float)
                sv = np.asarray(S.sn.get(bone, {}).get(chan, v), float)
                if base is not None and bone in base.ch:
                    b0 = np.asarray(base.ch[bone].get(chan, _ZERO), float)
                    v = v - b0
                    sv = sv - b0
                vals.append(v)
                svals.append(sv)
            if bone == "head" and is_rot and not any(S.head_written for _t, S, _P in sol):
                vals = [np.zeros(3) for _ in vals]
            keys = {}
            moved = False
            for i, (t, S, P) in enumerate(sol):
                comp = []
                for ax in range(3):
                    tp = vals[i][ax]
                    sn = tp + wts[i] * (svals[i][ax] - tp) if unsneak else tp
                    tl = []
                    if is_rot:
                        for e, ws in terms.get((bone, ax), []):
                            we = _weighted(e, ws[i])
                            if we:
                                tl.append(we)
                    a, s_ = num(tp, nd), num(sn, nd)
                    if a == "0" and s_ == "0" and not tl:
                        comp.append(0)
                        continue
                    moved = True
                    tp_s = _sum(a, tl)
                    if s_ != a:
                        tp_s = f"q.is_sneaking ? {_sum(s_, tl)} : {tp_s}"
                    if bone in ARM_BONES and is_rot and fp_k:
                        fpv = num(vals[i][ax] * fp_k, nd)
                        comp.append(f"v.is_first_person ? {fpv} : ({tp_s})")
                    else:
                        comp.append(f"v.is_first_person ? 0.0 : ({tp_s})")
                ts = num(t, 3) if t else "0.0"
                if "." not in ts:
                    ts += ".0"
                keys[ts] = {"post": comp, "lerp_mode": "catmullrom"} if n > 2 else comp
            if not moved:
                continue
            ent = bones_out.setdefault(bone, {})
            if n == 1:
                ent["rotation" if is_rot else "position"] = list(keys.values())[0]
            else:
                ent["rotation" if is_rot else "position"] = keys
            if bone == "head" and is_rot:
                ent["relative_to"] = {"rotation": "entity"}
    doc = {"loop": clip.loop, "animation_length": round(clip.length, 3), "bones": bones_out}
    if absolute:
        doc["loop"] = True
    return doc


# ===========================================================================
#  6. モーションの定義
# ===========================================================================
CLIPS: Dict[str, Clip] = {}


def P(**k):
    return k


def clip(name, length, keys, **kw):
    if name in CLIPS:
        raise ValueError(f"duplicate clip {name}")
    keys = sorted(((float(t), dict(p)) for t, p in keys), key=lambda x: x[0])
    c = Clip(name, float(length), keys, **kw)
    if c.desc == "" and name in REG.PLAYER_ANIMS:
        c.desc = REG.PLAYER_ANIMS[name][0]
    CLIPS[name] = c
    return c


def mirror_pose(p: dict) -> dict:
    """左右反転（x → -x）。rx はそのまま、ry・rz は符号反転、左右の部位を入れ替える。"""
    sw = {"rA": "lA", "lA": "rA", "rL": "lL", "lL": "rL"}
    out = {}
    for k, v in p.items():
        base = k
        suffix = ""
        for s in ("w", "t", "p", "z"):
            if k.endswith(s) and k[:-1] in sw:
                base, suffix = k[:-1], s
        nk = sw.get(base, base) + suffix if base in sw else k
        if isinstance(v, (tuple, list)) and len(v) == 3:
            if suffix in ("t", "p") or k in ("tr", "c", "bp"):
                v = (-v[0], v[1], v[2])
            else:
                v = (v[0], -v[1], -v[2])
        elif suffix == "z":
            v = -v
        out[nk] = v
    return out


def mirror_keys(keys):
    return [(t, mirror_pose(p)) for t, p in keys]


Z = {}   # 休み（差分 0）

from gen_nr_player_motions import define_all  # noqa: E402  モーションの中身は別ファイル

define_all(clip, P, Z, mirror_keys)
