# -*- coding: utf-8 -*-
"""NIGHT RUNNER — プレイヤーのモーション（パルクール・素手の戦闘・武器・道具）を生成する。

出力: packs/nightrunner_RP/animations/nr_player.animation.json（animation.nr.p.<名前>）
      nr_registry.PLAYER_ANIMS の**全部**と animation.nr.p.none（0.05 秒の空アニメ）。
      モーションの中身（キーの姿勢）は nr_player_motions.py、ここは解き方・Molang・検査・確認画像。

スクリプトは player.playAnimation("animation.nr.p.<名前>", {controller, blendOutTime, stopExpression,
nextState}) で重ねる（DESIGN.md §13、reference/rendering.md §5・§9、チェックリスト P1〜P6）。
推奨の層・ブレンド・止め方・次に流すモーションは PLAYER_ANIM_META（anim_meta()）にまとめてあり、
gen_nr_data_js などから import できる（下の「公開 API」）。

────────────────────────────────────────────────────────────────────────────
■ バニラのプレイヤーの骨格（bedrock-samples geometry.humanoid.custom）
    root(0,0,0) ─ waist(0,12,0) ─ body(0,24,0) ─ head(0,24,0) / rightArm(-5,22,0) / leftArm(5,22,0)
               └ rightLeg(-1.9,12,0) / leftLeg(1.9,12,0)          ← 脚は root の子（waist の子ではない）
  回転 [rx, ry, rz] = Rz(-rz)·Ry(ry)·Rx(-rx)（nr_preview.rot と同じ）。負の rx で腕・脚が前へ、
  正の rx で胴が前へ倒れる、正の ry で右（-X）を向く、正の rz で右腕が外へ開き胴の上が左（+X）へ傾く。
  前 = -Z、右 = -X、上 = +Y（モデル単位 1/16 ブロック）。腕・脚に肘・膝は無い（一本の箱）。

■ 決め事（なぜこう書くか）
* **root の回転は書かない**。バニラのしゃがみ（animation.player.sneaking）が root.rotation.x に
  "28.0 - this" を書くので、評価順しだいで root の回転が消える。全身の回転（前転・寝そべり）は
  waist と両脚に同じ回転を与え、root の position で回転の中心を合わせる（脚と waist の pivot は
  同じ高さ・同じ z なので「腰の線まわりの全身の回転」を任意の中心まわりに直せる。HyperDim の
  flip_frames の「回転ぶんを position で打ち消す」と同じ考え）。
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
    歩きの腕振り   rightArm.x -tcos0 / leftArm.x +tcos0、持つと右腕 -18° で振りが半分（HOLD_CANCEL）
    歩きの脚振り   rightLeg.x +1.4·tcos0 / leftLeg.x -1.4·tcos0
    攻撃の振り     animation.player.attack.rotations（HyperDim の ATK_CANCEL と同じ式。重みなし）
  一発ものは最初と最後のキーで w = 0（P3: 最初と最後のキーが 0）。ループは w = 1。
* **層**（PLAYER_ANIM_META の layer。controller 名）:
    nr.p.hold   武器の構え・全力疾走のループ（hold_* / sprint_*）。絶対姿勢（バニラの持つ -18° と
                腕振りを打ち消して、武器ごとに一部だけ振りを残す）。両手・槍の腕は nr_weapon_common の
                HOLD_ARMS（武器のアタッチャブルとの契約）にぴったり合わせる
    nr.p.act    武器の振り・装填・投擲・狙い（*_aim は loop）・道具。武器の動きは ANIM_SETS の idle（hold_*）
                **からの差分**なので、構えの層が流れている前提（流れていなくても大きくは崩れない）
    nr.p.recoil 撃った反動・ポンプ・ボルト（小さな加算。狙いを止めずに重ねる）
    nr.p.move   パルクールと全身の技（蹴り・回避・受け流し・とどめ・掴まれ）。**再生中は nr.p.hold を止める**
                （none を流し、終わったら構えを流し直す）— 構えの腕に足されると腕が回り過ぎるため
* 一回転して終わるもの（roll）は最後のキーが 360°。blendOutTime 0 で切ること（meta の blend_out が 0）。
* 続きもの: glide_open → glide、throw_wind → throw_overhand、bow_draw → bow_hold → bow_release は
  前の最後の姿勢 = 次の最初の姿勢（meta の then / from）。前の方は "hold_on_last_frame"。

■ 公開 API（他の生成器から import してよい。import しただけではファイルを書かない）
  build_animations() -> dict             animation ファイルの中身（{"format_version", "animations"}）
  anim_lengths() -> {名前: 秒}            PLAYER_ANIM_LENGTHS（nr_registry の長さと一致することを検査済み）
  anim_meta() -> {名前: {...}}            PLAYER_ANIM_META（layer / loop / blend_out / stop / stops_hold / base / then）
  hold_arm_angles() -> {hold名: {"arm_r", "arm_l"}}   三人称の構えの腕の絶対角（飛び道具の構え hold_bow /
                                         hold_pistol / hold_rifle と狙い *_aim も。アタッチャブルの逆算用）
  CLIPS                                  {名前: Clip}（キーの姿勢の定義）

■ 確認
  python3 tools/nightrunner/gen_nr_player_anim.py --qa   # build_preview/nightrunner/player_anim/ に確認画像
  （NR_PREVIEW=1 でも描く）。Steve と同じ寸法・ボーン名の模型（bedrock-samples の geometry.humanoid.custom
  があればそれ）を nr_preview で描く。書き出した JSON を nr_preview の Molang 評価器で評価し、バニラの
  三人称のアニメ（歩き・持つ・攻撃の振り・しゃがみ）を足して、頭の relative_to も再現する。
  --check は描かずに検査だけ（打ち消しが効くか・最初と最後が 0 か・長さ・登録簿の網羅）。
"""
from __future__ import annotations

import argparse
import json
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
from nr_common import PREVIEW, ROOT, RP, SCRATCH, write_json  # noqa: E402

try:  # 登録データの入口（無ければカタログを直接）
    import nr_spec as SPEC  # noqa: E402
    _ = SPEC.ANIM_SETS
except Exception:  # noqa: BLE001
    import nr_spec_catalog as SPEC  # type: ignore  # noqa: E402

OUT = os.path.join(RP, "animations", "nr_player.animation.json")
PREFIX = "animation.nr.p."
QA_DIR = os.path.join(SCRATCH, "player_anim")
ANIM_FORMAT = "1.8.0"
TICK = 0.05

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


def frame(fwd, up=(0.0, 1.0, 0.0)) -> np.ndarray:
    """局所の -Z を fwd、+Y をなるべく up へ向ける回転行列（列 = 局所の x, y, z 軸）。"""
    f = np.asarray(fwd, float)
    f = f / max(np.linalg.norm(f), 1e-9)
    z = -f
    u = np.asarray(up, float)
    x = np.cross(u, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.cross(np.array([1.0, 0, 0]) if abs(z[0]) < 0.9 else np.array([0, 0, 1.0]), z)
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


def kabsch(src, dst, weights) -> np.ndarray:
    """重み付きで src の向きの組を dst へ一番よく重ねる回転（Wahba の問題）。"""
    H = np.zeros((3, 3))
    for a, b, w in zip(src, dst, weights):
        a = np.asarray(a, float) / max(np.linalg.norm(a), 1e-9)
        b = np.asarray(b, float) / max(np.linalg.norm(b), 1e-9)
        H += w * np.outer(b, a)
    U, _S, Vt = np.linalg.svd(H)
    D = np.diag([1.0, 1.0, float(np.sign(np.linalg.det(U @ Vt)) or 1.0)])
    return U @ D @ Vt


def _look_gn(d, a0, twist, x):
    x = np.asarray(x, float).copy()
    for _ in range(60):
        f = rot((x[0], x[1], twist)) @ a0 - d
        J = np.zeros((3, 2))
        for i in range(2):
            dx = np.zeros(2)
            dx[i] = 1e-3
            J[:, i] = (rot((x[0] + dx[0], x[1] + dx[1], twist)) @ a0 - d - f) / 1e-3
        step, *_ = np.linalg.lstsq(J, -f, rcond=None)
        x = x + np.clip(step, -40, 40)
        if np.linalg.norm(step) < 1e-5:
            break
    return x, float(np.linalg.norm(rot((x[0], x[1], twist)) @ a0 - d))


def _rot_angle(R) -> float:
    return math.degrees(math.acos(float(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0))))


def look_rot(d, a0, twist=0.0, guess=None) -> np.ndarray:
    """腕・脚の向き: 休みの向き a0（局所の単位ベクトル）を d へ向ける [rx, ry, twist]。ガウス・ニュートン。
    ねじれ（twist）を決めると向きの解は二つ（腕が自分の軸まわりに 180° 回ったもの）。回転の小さい方を取る
    （180° 回った解は箱が体の内側へずれて胴に刺さり、肌の向きも裏返る）。guess があれば 360° の倍数で寄せる。"""
    d = np.asarray(d, float)
    d = d / max(np.linalg.norm(d), 1e-9)
    rx0 = -math.degrees(math.acos(float(np.clip(-d[1], -1, 1))))
    s = math.sin(math.radians(rx0))
    ry0 = math.degrees(math.atan2(d[0] / s, d[2] / s)) if abs(s) > 1e-6 else 0.0
    starts = [(rx0, ry0), (-rx0, ry0 + 180.0)]
    if guess is not None:
        starts.append((guess[0], guess[1]))
    sols = []
    for st in starts:
        x, res = _look_gn(d, a0, twist, st)
        if res < 1e-3:
            sols.append(x)
    if not sols:
        x, _res = _look_gn(d, a0, twist, starts[-1])
        sols = [x]
    ang = [_rot_angle(rot((x[0], x[1], twist))) for x in sols]
    best = min(ang)
    near = [x for x, a in zip(sols, ang) if a < best + 8.0]   # ほぼ同じなら前のキーに近い方
    if guess is not None:
        g2 = np.array([guess[0], guess[1]], float)
        near = [g2 + (x - g2 + 180.0) % 360.0 - 180.0 for x in near]
        x = min(near, key=lambda v: float(np.sum((v - g2) ** 2)))
    else:
        x = near[0]
    return np.array([x[0], x[1], twist])


def rodrigues(w) -> np.ndarray:
    """回転ベクトル（ラジアン）→ 回転行列。"""
    w = np.asarray(w, float)
    th = float(np.linalg.norm(w))
    if th < 1e-12:
        return np.eye(3)
    k = w / th
    K = np.array([[0.0, -k[2], k[1]], [k[2], 0.0, -k[0]], [-k[1], k[0], 0.0]])
    return np.eye(3) + math.sin(th) * K + (1.0 - math.cos(th)) * (K @ K)


def nelder_mead(f, x0, step=0.15, iters=400, tol=1e-9):
    """小さな決定的なネルダー＝ミード法（scipy 無しで動くように）。(x, f(x)) を返す。"""
    n = len(x0)
    pts = [np.asarray(x0, float)] + [np.asarray(x0, float) + step * np.eye(n)[i] for i in range(n)]
    vals = [f(q) for q in pts]
    for _ in range(iters):
        order = np.argsort(vals, kind="stable")
        pts = [pts[i] for i in order]
        vals = [vals[i] for i in order]
        if vals[-1] - vals[0] < tol:
            break
        cen = np.mean(pts[:-1], axis=0)
        xr = cen + (cen - pts[-1])
        fr = f(xr)
        if fr < vals[0]:
            xe = cen + 2.0 * (cen - pts[-1])
            fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = cen + 0.5 * (pts[-1] - cen)
            fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0]] + [pts[0] + 0.5 * (q - pts[0]) for q in pts[1:]]
                vals = [vals[0]] + [f(q) for q in pts[1:]]
    i = int(np.argmin(vals))
    return pts[i], vals[i]


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


def fist_world(W, bone="rightArm") -> np.ndarray:
    return (W[bone] @ np.append(FIST[bone], 1.0))[:3]


# ===========================================================================
#  3. 構えの契約（武器のアタッチャブルと同じ腕の絶対角）と持ち物の軸
# ===========================================================================
# nr_weapon_common.hold_contract() の写し（import できないときだけ使う。値が変わったら検査が警告する）
_HOLD_FALLBACK = {
    "hold_1h": {"arm_r": (-18.0, 0.0, 0.0), "arm_l": None},
    "hold_2h": {"arm_r": (-37.1, -23.7, -2.3), "arm_l": (-74.1, 31.4, -1.6)},
    "hold_spear": {"arm_r": (-23.5, -22.3, 0.0), "arm_l": (-70.2, 39.9, 0.0)},
}
# 飛び道具の構え（ここが正。飛び道具の生成器は hold_arm_angles() を読んでアタッチャブルを逆算する。
# nr_weapon_common.hold_contract() に同じ名前が足されたら、そちらを優先する）
RANGED_HOLDS = {
    "hold_bow": {"arm_r": (-18.0, 0.0, 0.0), "arm_l": None},           # 片手武器と同じ（弓は右手）
    "hold_pistol": {"arm_r": (-30.0, -6.0, 0.0), "arm_l": None},       # 銃口を前下へ下げる
    "hold_rifle": {"arm_r": (-30.0, -18.0, 0.0), "arm_l": (-62.0, 36.0, 0.0)},   # 胸の前に斜めに抱える
}
HOLD_WARNINGS: List[str] = []


def _load_contract() -> Dict[str, dict]:
    try:
        import nr_weapon_common as WC  # noqa: WPS433
        c = {k: {"arm_r": tuple(v["arm_r"]), "arm_l": tuple(v["arm_l"]) if v.get("arm_l") else None}
             for k, v in WC.hold_contract().items()}
    except Exception as err:  # noqa: BLE001
        HOLD_WARNINGS.append(f"nr_weapon_common を読めなかったので構えの写しを使う: {err!r}")
        c = {k: dict(v) for k, v in _HOLD_FALLBACK.items()}
    for k, v in _HOLD_FALLBACK.items():
        if k in c and any(abs(a - b) > 0.05 for a, b in zip(c[k]["arm_r"], v["arm_r"])):
            HOLD_WARNINGS.append(f"{k}: 契約の腕が写しと違う（{c[k]['arm_r']} / {v['arm_r']}）— _HOLD_FALLBACK を直すこと")
    for k, v in RANGED_HOLDS.items():
        c.setdefault(k, dict(v))
    return c


HOLDS = _load_contract()


def _arm_world_dir_at_rest(arm_e) -> np.ndarray:
    return rot(arm_e)


def _style_axes() -> Dict[str, dict]:
    """持ち方の型 → {"axis": 右腕の局所での持ち物の向き（単位）, "gap": 両手の拳の間隔}。"""
    out = {}
    # 片手: nr_weapon_common.hold_one_hand の既定（腕 -18° のとき刃が前上へ 38°、左へ 4°）
    p, y = math.radians(38.0), math.radians(-4.0)
    fwd = np.array([math.sin(y) * math.cos(p), math.sin(p), -math.cos(y) * math.cos(p)])
    out["one_hand"] = {"axis": rot(HOLDS["hold_1h"]["arm_r"]).T @ fwd, "gap": None}
    for style, hold in (("two_hand", "hold_2h"), ("spear", "hold_spear")):
        ar, al = HOLDS[hold]["arm_r"], HOLDS[hold]["arm_l"]
        Fr = (bone_local("rightArm", ar) @ np.append(FIST["rightArm"], 1.0))[:3]
        Fl = (bone_local("leftArm", al) @ np.append(FIST["leftArm"], 1.0))[:3]
        d = Fl - Fr
        out[style] = {"axis": rot(ar).T @ (d / np.linalg.norm(d)), "gap": float(np.linalg.norm(d)),
                      "fists": (Fr, Fl)}
    # 銃: 銃身は腕の向きに沿う（肩 → 拳の延長。構えでも狙いでも腕の指す方を撃つ）
    arm_dir = FIST["rightArm"] - np.array(PIV["rightArm"])
    out["pistol"] = {"axis": arm_dir.copy(), "gap": None}
    out["rifle"] = {"axis": arm_dir.copy(), "gap": None}
    # 弓: 腕 -18° のとき弓の上の弭が上・少し前（握りは拳）
    out["bow"] = {"axis": rot(HOLDS["hold_bow"]["arm_r"]).T @ np.array([0.0, 0.94, -0.34]), "gap": None}
    for v in out.values():
        v["axis"] = v["axis"] / np.linalg.norm(v["axis"])
    return out


STYLES = _style_axes()
# 両手持ちの拳の間隔の範囲（持ち物の軸に沿って。剣の柄は短く、斧・槌・槍の柄は長い）
GRIP_RANGE = {"two_hand": (2.4, 8.0), "spear": (3.0, 12.0), "rifle": (5.0, 11.0)}

# ===========================================================================
#  4. キーの姿勢 → ボーンのチャンネル
# ===========================================================================
#  姿勢の書き方（キーごとの辞書。書かない部位は休み（または構え）のまま）:
#    fb=(x,y,z)  全身の回転（中心 c、既定はクリップの centre）   tr=(x,y,z) 全身の平行移動
#    w=(x,y,z)   胴（waist、腰まわり）  b=(x,y,z) 胸（body、首の付け根まわり。主に y のひねり）
#    rA/lA       腕（胸に対して）     rAw/lAw 腕（体＝エンティティ基準の向き）
#    rAt/lAt     腕で指す点（体の座標、fb の前 = 全身の回転と一緒に動く）。rAz/lAz はそのときの腕のねじり
#    rAg/lAg     腕で指す点（エンティティの座標。全身を回しても動かない = 障害物・地面に手をつく）
#    rAc/lAc     腕で指す点（胸の座標。腰・胸のひねりと一緒に動く。両手武器の「体の正面の弧」）
#    rB / rBc    右手の持ち物の向き（体の座標 / 胸の座標。rBg はエンティティの座標）。腕の向きと合わせて
#                腕のねじりを解く（Kabsch）。
#                両手の型で rAc と lAc を書けば、持ち物の向き = 右の拳 → 左の拳、握りの間隔 = 二点の距離
#    gap         両手持ちの拳の間隔の好み（既定は構えの間隔）。実際は左の拳が柄に乗る間隔を GRIP_RANGE の
#                範囲で探し、好みに近いものを使う
#    lA="grip"   両手持ち（右手の持ち物の軸に沿って左手を置く。両手の型は書かなければ自動）
#    rL/lL       脚（fb の枠で）      rLw/lLw 脚（体基準の向き）
#    h           頭（胸に対して。胴と一緒に回る）  hw 頭（体基準）  hl 頭（視線に足すだけ）
#    rAp/lAp/bp  腕・胸の位置のずれ   ground=True 一番低い点を y=0 に（接地。数値ならその高さ）
#    wgt         打ち消しの重み（既定: 一発ものは両端 0・中 1）  aim 狙い（q.target_x/y_rotation を腕へ）の重み
#    bw          持ち物の向き（rB/rBc）の重み（既定 1 = 腕の向き優先。槍の突きのように刃先の向きが大事なら大きく）

_ZERO = np.zeros(3)
_GROUPS = {
    "rA": ("rA", "rAw", "rAt", "rAg", "rAc", "rAz", "rAp", "rB", "rBc", "rBg", "bw"),
    "lA": ("lA", "lAw", "lAt", "lAg", "lAc", "lAz", "lAp", "gap"),
    "rL": ("rL", "rLw"), "lL": ("lL", "lLw"), "h": ("h", "hw", "hl"), "w": ("w",), "b": ("b",), "bp": ("bp",),
}


def _v(P, k, d=_ZERO):
    v = P.get(k)
    return np.asarray(v, float) if v is not None else np.asarray(d, float)


@dataclass
class Clip:
    name: str
    length: float
    keys: List[Tuple[float, dict]]
    kind: str = "move"           # move / item / act / hold / aim / recoil
    loop: object = False         # False / True / "hold_on_last_frame"
    base: Optional[str] = None   # 差分の元にする構え（hold_*）。act / aim / recoil は構えの層の上に足す
    style: Optional[str] = None  # 持ち物の型（one_hand / two_hand / spear / rifle / pistol / bow）
    fp: Optional[float] = None   # 一人称の腕の倍率（None で種類の既定）
    unsneak: Optional[bool] = None
    head: str = "look"           # look / follow
    centre: Tuple[float, float, float] = (0.0, 12.0, 0.0)
    grip: Optional[float] = None  # 両手持ち: 左手を右手の持ち物の軸に沿ってずらす量（既定は型の拳の間隔）
    grip_side: float = 0.0       # 両手持ち: 左手を横（+X = 体の左）へずらす量
    legs: Optional[bool] = None  # 脚の歩きを打ち消すか
    atk: Optional[bool] = None   # 攻撃の振りを打ち消すか
    arms: Optional[str] = None   # 腕の打ち消し: None / "always" / "if_empty" / "hold"
    keep: Tuple[float, float] = (0.0, 0.0)  # hold: 歩きの腕振りを残す割合（右, 左。左に負で右と同じ向き）
    aim: Optional[str] = None    # "crossbow" / "bow" / "point"（右腕だけ）
    first_w: Optional[float] = None   # 最初のキーの打ち消しの重み（続きのモーションは 1）
    last_w: Optional[float] = None
    desc: str = ""
    proxy: str = ""              # 確認画像の持ち物: "" / blade / blade2 / club / club2 / spear / pistol / rifle / bow / small
    views: Tuple = ("side", "tq")  # 確認画像の向き
    meta: dict = field(default_factory=dict)


KIND_DEFAULTS = {
    #        fp    unsneak legs   atk    arms
    "move":  (0.25, True,  True,  False, "always"),
    "item":  (0.25, False, False, False, "always"),
    "act":   (0.25, False, False, True,  None),
    "hold":  (0.0,  False, False, False, "hold"),
    "aim":   (0.0,  False, False, True,  None),
    "recoil": (0.5, False, False, False, None),
}


def _dflt(c: Clip, attr, idx):
    v = getattr(c, attr)
    return KIND_DEFAULTS[c.kind][idx] if v is None else v


def two_handed(clip: Clip) -> bool:
    return bool(clip.style and STYLES.get(clip.style, {}).get("gap"))


def merge_base(P: dict, BP: Optional[dict], skip=()) -> dict:
    """構えの姿勢 BP のうち、P が書いていない部位だけを足す（部位ごと。腕なら rA/rAw/rAt… のどれか）。"""
    if not BP:
        return dict(P)
    out = dict(P)
    for g, keys in _GROUPS.items():
        if g in skip or any(k in P for k in keys):
            continue
        for k in keys:
            if k in BP:
                out[k] = BP[k]
    return out


class Solved:
    """1 キーの解: ch[bone] = {"rot": e, "pos": p}（三人称・しゃがみ無し）と、しゃがみ時の値 sn。"""

    def __init__(self):
        self.ch: Dict[str, dict] = {}
        self.sn: Dict[str, dict] = {}
        self.W = None
        self.head_written = False
        self.reach = 0.0          # 両手持ち: 左の拳と柄の二つ目の握りの距離
        self.gap = 0.0            # 両手持ち: 実際に使った握りの間隔


ARM_LEN = float(np.linalg.norm(FIST["leftArm"] - np.array(PIV["leftArm"])))


def _grip_pref(P: dict, clip: Clip) -> float:
    if isinstance(P.get("gap"), (int, float)):
        return float(P["gap"])
    if "rAc" in P and "lAc" in P:
        return float(np.linalg.norm(np.asarray(P["lAc"], float) - np.asarray(P["rAc"], float)))
    st = STYLES[clip.style or "two_hand"]
    return clip.grip if clip.grip is not None else (st.get("gap") or 4.0)


def grip_gap(fist, axis, sh, side, clip: Clip, pref: float) -> Tuple[float, float]:
    """柄の上で左の拳が乗る間隔と、そのときの届かなさ（腕の長さとの差）。座標は何でもよい（同じ枠なら）。"""
    lo, hi = GRIP_RANGE.get(clip.style or "two_hand", (2.5, 8.0))
    gs = np.unique(np.append(np.arange(lo, hi + 1e-6, 0.05), min(max(pref, lo), hi)))   # 好みそのものも候補に
    miss = np.abs(np.linalg.norm(fist[None, :] + gs[:, None] * axis[None, :] + side[None, :] - sh[None, :],
                                 axis=1) - ARM_LEN)
    i = int(np.argmin(miss + 0.04 * np.abs(gs - pref)))
    return float(gs[i]), float(miss[i])


_TORSO_LO = np.array(BOXES["body"][0], float)
_TORSO_HI = _TORSO_LO + np.array(BOXES["body"][1], float)


def seg_depth(a, b) -> float:
    """胸の座標の線分 a→b（腕の芯）が胴の箱へ入る深さの最大（外なら負）。肩の近くは除く。"""
    us = np.linspace(0.2, 1.0, 9)[:, None]
    pts = a[None, :] + (b - a)[None, :] * us
    return float(np.max(np.min(np.minimum(pts - _TORSO_LO, _TORSO_HI - pts), axis=1)))


def refine_two_hand(R0, a0, d, b, bw, clip: Clip, pref: float) -> np.ndarray:
    """両手持ち: 右腕の回転を「腕の向き・持ち物の向き・左の拳が柄に届くこと・腕が胴に刺さらないこと」の和が
    最小になるよう解き直す（胸の座標。肘が無いので、柄の向きと右腕の向きは持ち物の型で決まった角度でしか組めない）。"""
    st = STYLES[clip.style]
    pr = np.array(PIV["rightArm"])
    sh = np.array(PIV["leftArm"])
    fr0 = FIST["rightArm"] - pr
    top_r, top_l = np.array([-6.0, 22.0, 0.0]), np.array([6.0, 22.0, 0.0])   # 腕の芯の上端（肩の外）
    side = np.array([clip.grip_side, 0.0, 0.0])
    d = np.asarray(d, float) / max(np.linalg.norm(d), 1e-9)
    b = np.asarray(b, float) / max(np.linalg.norm(b), 1e-9)

    def parts(R):
        fist = pr + R @ fr0
        axis = R @ st["axis"]
        g, miss = grip_gap(fist, axis, sh, side, clip, pref)
        tgt = fist + axis * g + side
        pen = max(seg_depth(pr + R @ (top_r - pr), fist), seg_depth(top_l, tgt))
        return miss, pen

    def cost(w):
        R = rodrigues(w) @ R0
        miss, pen = parts(R)
        return (6.0 * float(np.sum((R @ a0 - d) ** 2)) + bw * float(np.sum((R @ st["axis"] - b) ** 2))
                + 1.5 * miss * miss + 2.0 * max(0.0, pen - 0.2) ** 2)

    miss0, pen0 = parts(R0)
    if miss0 < 0.05 and pen0 < 0.5:
        return R0
    w, _f = nelder_mead(cost, np.zeros(3), step=0.12)
    return rodrigues(w) @ R0


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
    # 両手持ちの左手は自動で柄へ（右腕に何か書いたキーか、構えの上の差分のときだけ。空のキーは休みのまま）。
    # gap（握りの間隔）・lAz（ねじり）・lAp・lAc は握りの指定なので自動の握りを止めない
    l_free = any(k in P for k in ("lAw", "lAt", "lAg")) or P.get("lA") not in (None, "grip")
    auto_grip = (two_handed(clip) and not l_free
                 and (base is not None or any(k in P for k in _GROUPS["rA"])))
    # 持ち物の向き（右手）: rB = 体の座標の向き（全身の回転と一緒に回る）、rBc = 胸の座標の向き、
    # 両手で rAc と lAc があれば右の拳 → 左の拳の向き
    blade = None
    if "rBg" in P:
        blade = np.asarray(P["rBg"], float)
    elif "rB" in P:
        blade = Rfb @ np.asarray(P["rB"], float)
    elif "rBc" in P:
        blade = C @ np.asarray(P["rBc"], float)
    elif two_handed(clip) and "rAc" in P and "lAc" in P:
        blade = C @ (np.asarray(P["lAc"], float) - np.asarray(P["rAc"], float))
    for side, bone in (("r", "rightArm"), ("l", "leftArm")):
        key = f"{side}A"
        a0 = FIST[bone] - np.array(PIV[bone])
        a0 = a0 / np.linalg.norm(a0)
        g = pv(bone)
        if P.get(key) == "grip" or (side == "l" and auto_grip):
            continue                                     # 右腕のあと
        if f"{key}w" in P:
            e = euler(C.T @ rot(_v(P, f"{key}w")), g)
        elif f"{key}t" in P or f"{key}g" in P or f"{key}c" in P:
            sh = W["body"] @ np.append(PIV[bone], 1.0)
            if f"{key}t" in P:
                tgt = F(P[f"{key}t"])
            elif f"{key}g" in P:
                tgt = np.asarray(P[f"{key}g"], float)
            else:
                tgt = (W["body"] @ np.append(np.asarray(P[f"{key}c"], float), 1.0))[:3]
            d = C.T @ (tgt - sh[:3])
            if side == "r" and blade is not None and clip.style in STYLES:
                bw = float(P.get("bw", 1.0))
                R = kabsch([a0, STYLES[clip.style]["axis"]], [d, C.T @ blade], [6.0, bw])
                if auto_grip:
                    R = refine_two_hand(R, a0, d, C.T @ blade, bw, clip, _grip_pref(P, clip))
                e = euler(R, g)
            else:
                e = look_rot(d, a0, float(P.get(f"{key}z", 0.0)), g if prev else None)
        elif key in P:
            e = _v(P, key)
        elif base is not None:
            e = np.asarray(base.ch[bone]["rot"], float)
        else:
            e = _ZERO
        S.ch[bone] = {"rot": np.asarray(e, float), "pos": _v(P, f"{key}p")}
    if P.get("lA") == "grip" or auto_grip:
        st = STYLES[clip.style or "two_hand"]
        W = fk(S.ch)
        Wr = W["rightArm"]
        fist = (Wr @ np.append(FIST["rightArm"], 1.0))[:3]
        axis = Wr[:3, :3] @ st["axis"]
        sh = (W["body"] @ np.append(PIV["leftArm"], 1.0))[:3]
        # 握りの間隔: 書いた値（または構えの間隔）は「好み」。肘の無い腕の拳は肩から腕の長さちょうどの所にしか
        # 来ないので、柄の上でそうなる点を型ごとの範囲で探す（剣は手を寄せ、槍は広く）。好みに近い方を取る
        side = W["body"][:3, :3] @ np.array([clip.grip_side, 0, 0])
        gap, _miss = grip_gap(fist, axis, sh, side, clip, _grip_pref(P, clip))
        target = fist + axis * gap + side
        a0 = FIST["leftArm"] - np.array(PIV["leftArm"])
        a0 = a0 / np.linalg.norm(a0)
        d = C.T @ (target - sh)
        base_l = base.ch["leftArm"]["rot"] if base is not None else None
        twist = float(P.get("lAz", base_l[2] if base_l is not None else 0.0))
        guess = pv("leftArm") if prev else base_l
        S.ch["leftArm"] = {"rot": look_rot(d, a0, twist, guess), "pos": _v(P, "lAp")}
        W2 = fk(S.ch)
        S.reach = float(np.linalg.norm(fist_world(W2, "leftArm") - target))
        S.gap = float(gap)
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
#  5. Molang の組み立て
# ===========================================================================


def num(x, nd=2) -> str:
    v = round(float(x), nd)
    if abs(v) < 10 ** -nd / 2:
        return "0"
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return s


_AT = "math.clamp(v.attack_time, 0.0, 1.0)"
_S4 = f"math.sin((1.0 - math.pow(1.0 - {_AT}, 4.0)) * 180.0)"
# バニラの攻撃の振り（animation.player.attack.rotations）を打ち消す項（三人称。HyperDim の ATK_CANCEL）
ATK_TERMS = {
    ("rightArm", 0): f"({_S4} * 1.2 + math.sin({_AT} * 180.0)) * 30.0",
    ("rightArm", 1): f"({_S4} != 0.0 ? 30.0 - 90.0 * {_S4} : 0.0)",
    ("leftArm", 0): f"({_S4} * 1.2 + math.sin({_AT} * 180.0)) * 10.0",
    ("body", 1): f"math.sin(360.0 * math.sqrt({_AT})) * -5.0",
}
# 歩きの腕振り・持つ -18° の打ち消し（HyperDim の HOLD_CANCEL を左右・持つ持たないで分けたもの）
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
    "bow": {("rightArm", 0): _AX, ("rightArm", 1): "math.clamp(q.target_y_rotation, -60.0, 45.0)",
            ("leftArm", 0): _AX, ("leftArm", 1): "math.clamp(q.target_y_rotation, -45.0, 45.0)"},
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
    return f"{num(w, 3)} * ({expr})"


# ===========================================================================
#  6. クリップ → JSON
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
    elif clip.last_w is not None:
        w[-1] = clip.last_w
    return w


_BASE_CACHE: Dict[str, Tuple[Solved, dict]] = {}


def base_solved(name: Optional[str]) -> Optional[Tuple[Solved, dict]]:
    if not name:
        return None
    if name not in _BASE_CACHE:
        bc = CLIPS[name]
        _BASE_CACHE[name] = (solve_pose(bc.keys[0][1], bc, None), bc.keys[0][1])
    return _BASE_CACHE[name]


def _base_of(clip: Clip):
    return base_solved(clip.base) if clip.kind in ("act", "aim", "recoil") and clip.base else None


def solve_clip(clip: Clip) -> List[Tuple[float, Solved, dict]]:
    bb = _base_of(clip)
    base, bP = (bb if bb else (None, None))
    if clip.kind == "recoil":     # 反動・ポンプ・ボルトは狙いの上の小さな加算。書いていない部位は 0 のまま
        base, bP = None, None
    skip = ("lA",) if two_handed(clip) else ()
    out = []
    prev = base
    for t, P in clip.keys:
        Pm = merge_base(P, bP, skip) if (bP and clip.kind != "recoil") else P
        S = solve_pose(Pm, clip, prev, base)
        out.append((t, S, P))
        prev = S
    return out


def build_clip(clip: Clip) -> dict:
    sol = solve_clip(clip)
    n = len(sol)
    wts = [float(P.get("wgt", w)) for (_t, _S, P), w in zip(sol, _key_weights(clip, n))]
    aimw = [float(P.get("aim", w)) for (_t, _S, P), w in zip(sol, wts)]
    bb = _base_of(clip)
    base = bb[0] if (bb and clip.kind != "recoil") else None
    fp_k = _dflt(clip, "fp", 0)
    unsneak = _dflt(clip, "unsneak", 1)
    legs = _dflt(clip, "legs", 2)
    atk = _dflt(clip, "atk", 3)
    arms = _dflt(clip, "arms", 4)
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
    for bone in ORDER:
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
                svals = [np.zeros(3) for _ in svals]
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
    if clip.kind == "hold":
        doc["loop"] = True
    return doc


# ===========================================================================
#  7. モーションの定義（中身は nr_player_motions.py）
# ===========================================================================
CLIPS: Dict[str, Clip] = {}


def P(**k):
    return k


def clip(name, length, keys, **kw):
    if name in CLIPS:
        raise ValueError(f"duplicate clip {name}")
    keys = sorted(((round(float(t), 4), dict(p)) for t, p in keys), key=lambda x: x[0])
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
        for s in ("w", "t", "g", "p", "z"):
            if k.endswith(s) and k[:-1] in sw:
                base, suffix = k[:-1], s
        nk = sw.get(base, base) + suffix if base in sw else k
        if isinstance(v, (tuple, list)) and len(v) == 3:
            if suffix in ("t", "g", "p") or k in ("tr", "c", "bp"):
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


class Ctx:
    """nr_player_motions.define_all に渡す道具箱。"""
    clip = staticmethod(clip)
    P = staticmethod(P)
    Z = Z
    mirror_keys = staticmethod(mirror_keys)
    mirror_pose = staticmethod(mirror_pose)
    HOLDS = HOLDS
    STYLES = STYLES
    ANIM_SETS = SPEC.ANIM_SETS
    TICK = TICK


import nr_player_motions as MOT  # noqa: E402  モーションの中身

MOT.define_all(Ctx)


# ===========================================================================
#  8. 書き出し・長さ・メタ情報
# ===========================================================================
NONE_CLIP = {"loop": False, "animation_length": 0.05, "bones": {}}


def build_animations() -> dict:
    anims = {f"{PREFIX}none": dict(NONE_CLIP)}
    for name in sorted(CLIPS):
        if name == "none":
            continue
        anims[f"{PREFIX}{name}"] = build_clip(CLIPS[name])
    return {"format_version": ANIM_FORMAT, "animations": anims}


def anim_lengths() -> Dict[str, float]:
    out = {"none": 0.05}
    for n, c in CLIPS.items():
        out[n] = round(c.length, 3)
    return dict(sorted(out.items()))


LAYER_OF_KIND = {"move": "nr.p.move", "item": "nr.p.act", "act": "nr.p.act", "aim": "nr.p.act",
                 "hold": "nr.p.hold", "recoil": "nr.p.recoil"}


def anim_meta() -> Dict[str, dict]:
    """スクリプト向けの推奨（DESIGN §13 / rendering.md §9 / チェックリスト P1〜P4）。"""
    out = {"none": {"layer": "*", "loop": False, "length": 0.05, "blend_out": 0.0,
                    "stop": "q.any_animation_finished", "stops_hold": False}}
    for n, c in sorted(CLIPS.items()):
        m = {"layer": c.meta.get("layer", LAYER_OF_KIND[c.kind]), "loop": c.loop if c.kind != "hold" else True,
             "length": round(c.length, 3), "blend_out": c.meta.get("blend_out", 0.1),
             "stop": c.meta.get("stop", "q.any_animation_finished" if c.loop is False else "0.0"),
             "stops_hold": c.meta.get("stops_hold", c.kind == "move")}
        if c.base:
            m["base"] = c.base
        for k in ("then", "from", "hit", "note"):
            if k in c.meta:
                m[k] = c.meta[k]
        out[n] = m
    return out


def hold_arm_angles() -> Dict[str, dict]:
    """構え・狙いの三人称の腕の絶対角（{名前: {"arm_r", "arm_l"}}。arm_l が None なら左手は空き）。
    hold_* は契約そのもの、*_aim / bow_hold は構えに差分を足した狙いの姿勢（視線 0° のとき）。"""
    out = {k: {"arm_r": tuple(v["arm_r"]), "arm_l": tuple(v["arm_l"]) if v["arm_l"] else None}
           for k, v in HOLDS.items()}
    for n, c in CLIPS.items():
        if c.kind == "aim" and c.keys:
            S = solve_clip(c)[0][1]
            out[n] = {"arm_r": tuple(round(float(x), 2) for x in S.ch["rightArm"]["rot"]),
                      "arm_l": tuple(round(float(x), 2) for x in S.ch["leftArm"]["rot"])}
    return out


# ===========================================================================
#  9. 検査（--check と生成のたび）
# ===========================================================================


def _registry_lengths() -> Dict[str, float]:
    import importlib
    reg = importlib.reload(REG)       # 別の作業者が足したばかりの名前も読む
    return {n: float(v[1]) for n, v in reg.PLAYER_ANIMS.items()}


def check_all(doc: dict) -> Tuple[List[str], List[str]]:
    """(errors, warnings)。errors があれば生成を失敗にする。"""
    errs, warns = [], list(HOLD_WARNINGS)
    anims = doc["animations"]
    reg = _registry_lengths()
    for n in reg:
        if f"{PREFIX}{n}" not in anims:
            errs.append(f"登録簿の {n} を作っていない")
    for full in anims:
        n = full[len(PREFIX):]
        if n not in reg:
            warns.append(f"{n} は登録簿に無い（スクリプトからは使えない）")
    lens = anim_lengths()
    for n, sec in reg.items():
        if n in lens and abs(lens[n] - sec) > 1e-6:
            errs.append(f"{n}: 長さ {lens[n]} 秒が登録簿の {sec} 秒と違う（登録簿を直すこと）")
    # ANIM_SETS の tick とキーの時刻
    for sk, s in SPEC.ANIM_SETS.items():
        for item in list(s.get("swings", [])) + ([s["heavy"]] if s.get("heavy") else []):
            name, wind, hit, end = item[0], item[1], item[2], item[3]
            c = CLIPS.get(name)
            if not c:
                continue
            if abs(c.length - end * TICK) > 1e-6:
                errs.append(f"{name}: 長さ {c.length} が ANIM_SETS の終わり {end} tick と違う")
            ts = [t for t, _ in c.keys]
            if not any(abs(t - hit * TICK) < 1e-6 for t in ts):
                errs.append(f"{name}: 当たる tick {hit}（{hit * TICK:.2f} 秒）にキーが無い")
        for k, v in s.items():
            if isinstance(v, str) and k not in ("ja",) and v not in CLIPS and v != "none":
                errs.append(f"ANIM_SETS {sk}.{k} = {v} を作っていない")
    # 骨・時刻・形
    for n, c in CLIPS.items():
        ts = [t for t, _ in c.keys]
        if ts[0] != 0.0:
            errs.append(f"{n}: 最初のキーが 0 秒でない")
        if c.loop is not True and c.kind != "hold" and abs(ts[-1] - c.length) > 1e-6:
            errs.append(f"{n}: 最後のキー {ts[-1]} が長さ {c.length} と違う")
        if c.loop is True and abs(ts[-1] - c.length) > 1e-6 and len(ts) > 1:
            errs.append(f"{n}: ループの最後のキーが長さと違う")
        if c.base and c.base not in CLIPS:
            errs.append(f"{n}: 構え {c.base} が無い")
    return errs, warns


# ===========================================================================
#  10. 確認画像（nr_preview）。バニラの三人称のアニメも足して実機の見え方に近づける
# ===========================================================================
_VANILLA_GEO = os.path.join(ROOT, "build_preview", "nr_research", "bedrock-samples", "resource_pack",
                            "models", "entity", "humanoid.custom.geo.json")
_STEVE = os.path.join(ROOT, "build_preview", "nr_research", "bedrock-samples", "resource_pack",
                      "textures", "entity", "steve.png")
PROXY_COLORS = {"steel": (0, 64), "wood": (8, 64), "dark": (16, 64), "red": (24, 64), "skin": (32, 64),
                "olive": (40, 64)}
PROXIES = {
    # 形: [(色, 拳からの始まり, 終わり, 太さ)]（持ち物の軸に沿って。負は柄頭の側）
    "blade": [("wood", -2.5, 2.0, 1.2), ("dark", 1.5, 2.5, 2.6), ("steel", 2.5, 14.0, 1.6)],
    "club": [("wood", -2.0, 9.0, 1.4), ("dark", 9.0, 14.0, 2.8)],
    "blade2": [("wood", -3.0, 8.0, 1.3), ("dark", 8.0, 9.0, 3.0), ("steel", 9.0, 26.0, 2.0)],
    "club2": [("wood", -3.0, 15.0, 1.5), ("dark", 15.0, 22.0, 4.0)],
    "spear": [("wood", -8.0, 22.0, 1.2), ("steel", 22.0, 28.0, 1.8)],
    "pistol": [("dark", -1.5, 5.5, 1.6)],
    "rifle": [("wood", -8.0, 1.5, 1.8), ("dark", 1.5, 16.0, 1.4)],
    "bow": [("wood", -10.0, 10.0, 1.0)],
    "small": [("red", -1.0, 1.5, 2.2)],
}


def _qa_assets():
    """Steve 型の模型（ジオメトリ辞書）とテクスチャ（64×80: 下 16 行が持ち物の色）。"""
    from PIL import Image
    if os.path.exists(_VANILLA_GEO):
        with open(_VANILLA_GEO, encoding="utf-8") as fh:
            g = json.load(fh)["minecraft:geometry"][0]
        g = json.loads(json.dumps(g))
    else:   # 無ければ同じ寸法の箱を組む（ボックス UV はスキンの標準配置）
        uv = {"head": (0, 0), "body": (16, 16), "rightArm": (40, 16), "leftArm": (32, 48),
              "rightLeg": (0, 16), "leftLeg": (16, 48)}
        bones = [{"name": "root", "pivot": [0, 0, 0]}, {"name": "waist", "parent": "root", "pivot": [0, 12, 0]}]
        for b in ("body", "head", "rightArm", "leftArm", "rightLeg", "leftLeg"):
            o, s = BOXES[b]
            bones.append({"name": b, "parent": PARENT[b], "pivot": list(PIV[b]),
                          "cubes": [{"origin": list(o), "size": list(s), "uv": list(uv[b])}]})
        g = {"description": {"identifier": "geometry.qa", "texture_width": 64, "texture_height": 64},
             "bones": bones}
    g["description"]["texture_width"] = 64
    g["description"]["texture_height"] = 80
    if os.path.exists(_STEVE):
        skin = Image.open(_STEVE).convert("RGBA")
    else:
        skin = Image.new("RGBA", (64, 64), (150, 120, 100, 255))
    tex = Image.new("RGBA", (64, 80), (0, 0, 0, 0))
    tex.paste(skin.resize((64, 64)), (0, 0))
    cols = {"steel": (196, 200, 208), "wood": (110, 74, 44), "dark": (52, 52, 58), "red": (190, 40, 40),
            "skin": (220, 180, 150), "olive": (90, 100, 60)}
    for k, (u, v) in PROXY_COLORS.items():
        for x in range(u, u + 8):
            for y in range(v, v + 8):
                tex.putpixel((x, y), (*cols[k], 255))
    return g, tex


def _with_proxy(g: dict, proxy: str, style: Optional[str]) -> dict:
    """右手に持ち物の目印（色の棒）を足したジオメトリ。"""
    g = json.loads(json.dumps(g))
    if not proxy:
        return g
    axis = STYLES.get(style or "one_hand", STYLES["one_hand"])["axis"]
    R = frame(axis, (0.0, 0.0, 1.0) if abs(axis[1]) > 0.9 else (0.0, 1.0, 0.0))
    e = euler(R)
    fx, fy, fz = FIST["rightArm"]
    cubes = []
    for col, z0, z1, th in PROXIES[proxy]:
        u, v = PROXY_COLORS[col]
        faces = {f: {"uv": [u + 1, v + 1], "uv_size": [4, 4]} for f in ("north", "south", "east", "west", "up", "down")}
        cubes.append({"origin": [fx - th / 2, fy - th / 2, fz - z1], "size": [th, th, z1 - z0], "uv": faces})
    g["bones"].append({"name": "nr_item", "parent": "rightArm", "pivot": [fx, fy, fz],
                       "rotation": [float(e[0]), float(e[1]), float(e[2])], "cubes": cubes})
    return g


def vanilla_pose(vars_: dict) -> Dict[str, dict]:
    """バニラの三人称のアニメ（humanoid_base_pose / move.arms / move.legs / holding / bob / attack / sneaking）
    の和。controller.animation.player.root の third_person の順。NR のアニメはこの後に足される前提。"""
    tc = float(vars_.get("v.tcos0", 0.0))
    hr = float(vars_.get("v.is_holding_right", 0.0))
    hl = float(vars_.get("v.is_holding_left", 0.0))
    at = float(vars_.get("v.attack_time", -1.0))
    sneak = float(vars_.get("q.is_sneaking", 0.0))
    life = float(vars_.get("q.life_time", 0.0))
    p = {b: {"rotation": np.zeros(3), "position": np.zeros(3)} for b in ORDER}
    p["rightArm"]["rotation"][0] += -tc
    p["leftArm"]["rotation"][0] += tc
    p["rightLeg"]["rotation"] += [tc * 1.4, 0.1, 0.1]
    p["leftLeg"]["rotation"] += [-tc * 1.4, -0.1, -0.1]
    if hr:
        x = p["rightArm"]["rotation"][0]
        p["rightArm"]["rotation"][0] = x + (-x * 0.5 - 18.0)
    if hl:
        x = p["leftArm"]["rotation"][0]
        p["leftArm"]["rotation"][0] = x + (-x * 0.5 - 18.0)
    if sneak:
        p["body"]["position"][1] -= 2.0
        p["head"]["position"][1] -= 1.0
        p["rightArm"]["rotation"][0] -= 5.7
        p["leftArm"]["rotation"][0] -= 5.7
        p["rightLeg"]["rotation"] += [-28.0, 0.1, 0.1]
        p["leftLeg"]["rotation"] += [-28.0, -0.1, -0.1]
        p["root"]["position"] += SNEAK_ROOT_POS
        p["root"]["rotation"][0] = 28.0
    bob = math.cos(math.radians(life * 103.2)) * 2.865 + 2.865
    p["rightArm"]["rotation"][2] += bob
    p["leftArm"]["rotation"][2] -= bob
    if at >= 0.0:
        s4 = math.sin(math.radians((1 - (1 - at) ** 4) * 180))
        sw = s4 * 1.2 + math.sin(math.radians(at * 180))
        p["rightArm"]["rotation"][0] += -sw * 30.0
        p["rightArm"]["rotation"][1] += -((-90.0 * s4 + 30.0) if s4 else 0.0)
        p["leftArm"]["rotation"][0] += -sw * 10.0
        p["body"]["rotation"][1] += math.sin(math.radians(360 * math.sqrt(at))) * 5.0
    return p


_VAR_KEYS = ("v.tcos0", "v.is_holding_right", "v.is_holding_left", "v.attack_time", "v.is_first_person")
_Q_KEYS = ("q.is_sneaking", "q.target_x_rotation", "q.target_y_rotation", "q.life_time")


def stack_pose(anims: dict, layers: List[Tuple[str, float]], vars_: dict) -> Tuple[Dict[str, dict], List[str]]:
    """バニラ + NR の層（[(名前, 時刻)]）の和。頭は relative_to entity として返す（rotation は体基準）。"""
    import nr_preview as NPV
    v = {k: vars_.get(k, 0.0) for k in _VAR_KEYS}
    v["v.attack_time"] = vars_.get("v.attack_time", -1.0)
    q = {k: vars_.get(k, 0.0) for k in _Q_KEYS}
    total = vanilla_pose(vars_)
    warns: List[str] = []
    for name, t in layers:
        pose, _w = NPV.animation_pose(anims, name, t, variables=v, queries=q, warnings=warns)
        for b, ent in pose.items():
            b = {x.lower(): x for x in ORDER}.get(b.lower(), b)
            tgt = total.setdefault(b, {"rotation": np.zeros(3), "position": np.zeros(3)})
            for ch in ("rotation", "position"):
                if ch in ent:
                    tgt[ch] = tgt[ch] + np.asarray(ent[ch], float)
    # 頭: バニラの look_at_target.default（relative_to entity）を足す
    total["head"]["rotation"] = total["head"]["rotation"] + np.array(
        [float(q.get("q.target_x_rotation", 0.0)), float(q.get("q.target_y_rotation", 0.0)), 0.0])
    return total, warns


def stack_world(total: Dict[str, dict]) -> Dict[str, np.ndarray]:
    return fk({b: {"rot": total[b]["rotation"], "pos": total[b]["position"]} for b in ORDER})


def preview_pose(total: Dict[str, dict]) -> Dict[str, dict]:
    """nr_preview 用: 頭の relative_to entity を「body に対する回転」に直す。"""
    W = stack_world(total)
    Rb = W["body"][:3, :3]
    he = euler(Rb.T @ rot(total["head"]["rotation"]))
    out = {}
    for b, v in total.items():
        out[b] = {"rotation": [float(x) for x in v["rotation"]], "position": [float(x) for x in v["position"]]}
    out["head"]["rotation"] = [float(x) for x in he]
    return out


def _layers_for(c: Clip, t: float) -> List[Tuple[str, float]]:
    """実機の重なり: 構え（nr.p.hold）→ 狙い・振り（nr.p.act）→ 反動（nr.p.recoil）。base を辿って下から積む。"""
    L = [(PREFIX + c.name, t)]
    b = c.base if c.kind in ("act", "aim", "recoil") else None
    while b:
        L.insert(0, (PREFIX + b, 0.0))
        bc = CLIPS.get(b)
        b = bc.base if (bc and bc.kind in ("act", "aim", "recoil")) else None
    return L


def _qa_vars(c: Clip, **over) -> dict:
    holding = 1.0 if (c.proxy or c.base or c.kind in ("hold", "act", "aim", "recoil")) else 0.0
    v = {"v.is_holding_right": holding, "v.tcos0": 0.0, "v.attack_time": -1.0, "q.is_sneaking": 0.0}
    v.update(over)
    return v


def check_cancel(doc: dict, names=None, tol=0.6) -> List[str]:
    """打ち消しの検査: 歩き・攻撃の振り・しゃがみを入れても、重み 1 のキーの姿勢が変わらないか。
    比べるのは拳・足先・頭の位置（モデル単位）。"""
    anims = doc["animations"]
    probs = []
    for n in sorted(names or CLIPS):
        c = CLIPS[n]
        wts = _key_weights(c, len(c.keys))
        for (t, P), w in zip(c.keys, wts):
            if w < 0.999 or P.get("wgt") is not None:
                continue
            base = _qa_vars(c)
            tests = []
            if c.kind == "hold":       # 構えは歩きの腕振りを keep の割合だけ残す（_hold_keep_check で別に見る）
                pass
            elif _dflt(c, "arms", 4) or _dflt(c, "legs", 2):
                tests.append(("walk", {"v.tcos0": 35.0}))
            if _dflt(c, "atk", 3):
                tests.append(("attack", {"v.attack_time": 0.35}))
            if _dflt(c, "unsneak", 1):
                tests.append(("sneak", {"q.is_sneaking": 1.0}))
            W0 = stack_world(stack_pose(anims, _layers_for(c, t), base)[0])
            pts0 = _probe_points(W0, c)
            for label, ov in tests:
                v = dict(base)
                v.update(ov)
                W1 = stack_world(stack_pose(anims, _layers_for(c, t), v)[0])
                pts1 = _probe_points(W1, c)
                err = max(float(np.linalg.norm(pts0[k] - pts1[k])) for k in pts0)
                if err > tol:
                    worst = max(pts0, key=lambda k: float(np.linalg.norm(pts0[k] - pts1[k])))
                    probs.append(f"{n} t={t}: {label} で {worst} が {err:.2f} ずれる")
    return probs


def check_hold_keep(doc: dict) -> List[str]:
    """構えのループ: 歩きの腕振りが右 -keep[0]·tcos0、左 +keep[1]·tcos0 だけ残るか（持つ持たない両方）。"""
    probs = []
    for n, c in sorted(CLIPS.items()):
        if c.kind != "hold":
            continue
        for hr in (0.0, 1.0):
            base = _qa_vars(c, **{"v.is_holding_right": hr})
            p0 = stack_pose(doc["animations"], [(PREFIX + n, 0.0)], base)[0]
            p1 = stack_pose(doc["animations"], [(PREFIX + n, 0.0)], dict(base, **{"v.tcos0": 30.0}))[0]
            dr = p1["rightArm"]["rotation"][0] - p0["rightArm"]["rotation"][0]
            dl = p1["leftArm"]["rotation"][0] - p0["leftArm"]["rotation"][0]
            if abs(dr + c.keep[0] * 30.0) > 0.2 or abs(dl - c.keep[1] * 30.0) > 0.2:
                probs.append(f"{n}: 持つ={hr} の歩きの腕振り 右 {dr:.1f} / 左 {dl:.1f}（期待 {-c.keep[0] * 30:.1f} / "
                             f"{c.keep[1] * 30:.1f}）")
            want = np.asarray(HOLDS[n]["arm_r"], float) if n in HOLDS else None
            if want is not None and hr:
                got = p0["rightArm"]["rotation"] - np.array([0.0, 0.0, p0["rightArm"]["rotation"][2] - want[2]
                                                              if abs(want[2]) < 1e-9 else 0.0])
                if np.max(np.abs(got[:2] - want[:2])) > 0.11:
                    probs.append(f"{n}: 右腕 {np.round(got, 2)} が契約 {want} と違う")
    return probs


def pose_metrics(W) -> Dict[str, float]:
    """腕・脚の芯線が胴の箱へ入る深さ（正 = 中。手足の太さ 4 の半分 2 を超えると芯まで刺さっている）と、
    胴に対する脚の振り（前 = 正、横 = 開き）。"""
    Tb = np.linalg.inv(W["body"])
    o, s = np.array(BOXES["body"][0], float), np.array(BOXES["body"][1], float)
    out = {}
    for limb, cx in (("rightArm", -6.0), ("leftArm", 6.0), ("rightLeg", -1.9), ("leftLeg", 1.9)):
        y0, y1 = (13.0, 20.0) if "Arm" in limb else (1.0, 9.0)
        worst = -9.0
        for y in np.linspace(y0, y1, 8):
            p = (Tb @ (W[limb] @ np.array([cx, y, 0.0, 1.0])))[:3]
            worst = max(worst, float(np.minimum(p - o, o + s - p).min()))
        out["pen_" + limb] = worst
    Rw = W["waist"][:3, :3]
    for limb in ("rightLeg", "leftLeg"):
        d = Rw.T @ (W[limb][:3, :3] @ np.array([0.0, -1.0, 0.0]))     # 腰の座標での脚の向き
        out["fwd_" + limb] = math.degrees(math.atan2(-d[2], -d[1]))
        out["side_" + limb] = math.degrees(math.asin(float(np.clip(abs(d[0]), 0, 1))))
    return out


def check_poses(names=None, pen_tol=0.5, reach_tol=0.8) -> List[str]:
    """全キーの解いた姿勢: 手足が胴に刺さる・両手の握りが届かない・脚が後ろへ反り過ぎ（膝の無い脚で 60° 超）。"""
    probs = []
    for n in sorted(names or CLIPS):
        c = CLIPS[n]
        for t, S, P in solve_clip(c):
            m = pose_metrics(S.W)
            bad = [f"{k[4:]} {v:+.1f}" for k, v in m.items() if k.startswith("pen_") and v > pen_tol]
            if two_handed(c) and S.reach > reach_tol and P:
                bad.append(f"握り {S.reach:.1f}")
            bad += [f"{k[4:]} 後ろ {-v:.0f}°" for k, v in m.items() if k.startswith("fwd_") and v < -60]
            if bad:
                probs.append(f"{n} t={t}: " + ", ".join(bad))
    return probs


def _probe_points(W, c: Clip) -> Dict[str, np.ndarray]:
    pts = {"fist_r": fist_world(W, "rightArm"), "fist_l": fist_world(W, "leftArm"),
           "head": (W["head"] @ np.array([0, 28, -4, 1.0]))[:3]}
    if c.kind not in ("act", "aim", "recoil", "hold", "item"):
        pts["foot_r"] = (W["rightLeg"] @ np.array([-1.9, 0, 0, 1.0]))[:3]
        pts["foot_l"] = (W["leftLeg"] @ np.array([1.9, 0, 0, 1.0]))[:3]
    return pts


def check_ends(doc: dict) -> List[str]:
    """P3: 一発ものの最初と最後のキーで全チャンネルが 0（続きもの・一回転は meta に書いた例外）。"""
    import nr_preview as NPV
    probs = []
    for n, c in sorted(CLIPS.items()):
        if c.loop is True or c.kind in ("hold", "aim"):
            continue
        ends = []
        if not c.meta.get("from"):
            ends.append(0.0)
        if c.loop != "hold_on_last_frame" and not c.meta.get("spin"):
            ends.append(c.length)
        for t in ends:
            pose, _ = NPV.animation_pose(doc["animations"], PREFIX + n, t,
                                         variables={"v.is_first_person": 0.0, "v.tcos0": 0.0, "v.attack_time": -1.0},
                                         queries={"q.is_sneaking": 0.0})
            worst = max((abs(x) for e in pose.values() for ch in ("rotation", "position") for x in e.get(ch, [])),
                        default=0.0)
            if worst > 0.051:
                probs.append(f"{n}: t={t} で {worst:.2f}（最初と最後のキーは 0 のはず）")
    return probs


def qa_render(doc: dict, names=None, out_dir: str = QA_DIR, frames: int = 7, size: int = 190) -> List[str]:
    """クリップごとの連続写真（側面＋斜め）と、全体の一覧を描く。返り値は書いたファイル。"""
    import nr_preview as NPV
    from PIL import Image
    os.makedirs(out_dir, exist_ok=True)
    g0, tex = _qa_assets()
    anims = doc["animations"]
    written = []
    views = {"side": (90.0, 4.0), "tq": (35.0, 12.0), "front": (0.0, 6.0), "back": (180.0, 8.0),
             "tql": (-40.0, 12.0), "top": (0.0, 70.0), "rear": (150.0, 12.0)}
    groups: Dict[str, List[str]] = {}
    for n in sorted(names or CLIPS):
        c = CLIPS[n]
        g = NPV.load_geometry({"format_version": "1.16.0", "minecraft:geometry": [_with_proxy(g0, c.proxy, c.style)]})
        if c.loop is True or c.kind in ("hold", "aim"):
            ts = list(np.linspace(0.0, c.length, frames, endpoint=False)) if c.length > 0.05 else [0.0]
        else:
            ts = sorted(set([round(t, 3) for t, _ in c.keys] + list(np.round(np.linspace(0, c.length, frames), 3))))
            if len(ts) > 10:
                keyts = [round(t, 3) for t, _ in c.keys]
                ts = sorted(set(keyts))
                while len(ts) < 7:
                    ts = sorted(set(ts + [round((a + b) / 2, 3) for a, b in zip(ts, ts[1:])]))
                ts = ts[:12]
        cells = []
        for vw in c.views:
            yaw, pitch = views[vw]
            for t in ts:
                total, _w = stack_pose(anims, _layers_for(c, t), _qa_vars(c))
                pose = preview_pose(total)
                cam = NPV.Camera(yaw=yaw, pitch=pitch, target=(0.0, 16.0, -2.0), scale=size / 46.0)
                img = NPV.render(g, tex, camera=cam, size=(size, int(size * 1.15)), pose=pose, floor=True,
                                 bg=(40, 42, 48))
                cells.append((f"{vw} {t:.2f}", img))
        sheet = NPV.contact_sheet(cells, cols=len(ts),
                                  title=f"{n}  ({c.length:.2f}s, {c.kind}, loop={c.loop})  {c.desc}")
        path = os.path.join(out_dir, f"{n}.png")
        sheet.save(path)
        written.append(path)
        groups.setdefault(c.meta.get("group", c.kind), []).append(n)
    return written


# 一覧の組（--sheet）: パルクール・全身 / 近接と構え / 飛び道具・投擲・道具
SHEET_GROUPS = {
    "move": lambda c: c.kind == "move",
    "melee": lambda c: c.kind == "hold" or (c.kind == "act" and c.style in ("one_hand", "two_hand", "spear")
                                            and not c.name.startswith("throw")),
    "ranged": lambda c: True,
}


def _sheet_times(c: Clip, k: int) -> List[float]:
    """一覧に載せる時刻: 一発ものは中のキー（多ければ当たりを含めて k 個に間引く）、ループは等間隔。"""
    if c.kind == "hold":
        return [0.0]
    if c.loop is True or c.kind == "aim":
        return [round(float(x), 3) for x in np.linspace(0.0, c.length, min(k, 4), endpoint=False)]
    inner = [round(t, 3) for t, _ in c.keys[1:-1]] or [round(c.length / 2, 3)]
    if c.loop == "hold_on_last_frame" or c.meta.get("from"):
        inner = [round(t, 3) for t, _ in c.keys]
    if len(inner) > k:
        hit = c.meta.get("hit")
        idx = sorted(set(int(round(i)) for i in np.linspace(0, len(inner) - 1, k)))
        pick = [inner[i] for i in idx]
        if hit is not None and not any(abs(t - hit) < 1e-6 for t in pick):
            pick[min(range(len(pick)), key=lambda i: abs(pick[i] - hit))] = round(hit, 3)
        inner = sorted(set(pick))
    return inner


def qa_sheets(doc: dict, out_dir: str = QA_DIR, per_clip: int = 5, size: int = 118,
              groups=("move", "melee", "ranged"), names=None, all_views: bool = False) -> List[str]:
    """全クリップのキーの姿勢を少数の一覧にまとめる（1 クリップ = 最初の向きで数コマ、1 行に 2 クリップ）。
    all_views なら clip.views の向きごとに 1 段（細部の確認用。--only と一緒に）。"""
    import nr_preview as NPV
    from PIL import Image
    os.makedirs(out_dir, exist_ok=True)
    g0, tex = _qa_assets()
    anims = doc["animations"]
    views = {"side": (90.0, 4.0), "tq": (35.0, 12.0), "front": (0.0, 6.0), "back": (180.0, 8.0),
             "tql": (-40.0, 12.0), "top": (0.0, 70.0), "rear": (150.0, 12.0)}
    left = [n for n in sorted(CLIPS) if not names or n in names]
    written = []
    geo_cache: Dict[Tuple[str, str], object] = {}
    for gname in groups:
        mine = [n for n in left if SHEET_GROUPS[gname](CLIPS[n])]
        left = [n for n in left if n not in mine]
        if not mine:
            continue
        cells = []
        for n in mine:
            c = CLIPS[n]
            key = (c.proxy, c.style or "")
            if key not in geo_cache:
                geo_cache[key] = NPV.load_geometry({"format_version": "1.16.0",
                                                    "minecraft:geometry": [_with_proxy(g0, c.proxy, c.style)]})
            g = geo_cache[key]
            ts = _sheet_times(c, per_clip)
            for vw in (c.views if all_views else c.views[:1]):
                yaw, pitch = views[vw]
                row = []
                for t in ts:
                    total, _w = stack_pose(anims, _layers_for(c, t), _qa_vars(c))
                    cam = NPV.Camera(yaw=yaw, pitch=pitch, target=(0.0, 15.0, -2.0), scale=size / 44.0)
                    img = NPV.render(g, tex, camera=cam, size=(size, int(size * 1.2)), pose=preview_pose(total),
                                     floor=True, bg=(40, 42, 48))
                    row.append((f"{n} {t:.2f}" + (f" {vw}" if all_views else ""), img))
                while len(row) < per_clip:
                    row.append(("", Image.new("RGB", (size, int(size * 1.2)), (16, 17, 21))))
                cells += row
        sheet = NPV.contact_sheet(cells, cols=per_clip * 2, title=f"nr_player {gname}: {len(mine)} clips")
        path = os.path.join(out_dir, f"_sheet_{gname}.png")
        sheet.save(path)
        written.append(path)
    return written


# ===========================================================================
#  11. 入口
# ===========================================================================


def generate(write=True) -> Tuple[dict, List[str], List[str]]:
    doc = build_animations()
    errs, warns = check_all(doc)
    if write:
        write_json(OUT, doc)
    return doc, errs, warns


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--qa", action="store_true", help="確認画像を描く（NR_PREVIEW=1 でも）")
    ap.add_argument("--only", default="", help="確認画像を描くクリップ（カンマ区切り・前方一致）")
    ap.add_argument("--check", action="store_true", help="打ち消し・両端 0 の数値検査も走らせる（遅い）")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--sheet", default="", help="全クリップの一覧を描く（move,melee,ranged のどれか・カンマ区切り。all で全部）")
    ap.add_argument("--size", type=int, default=118, help="一覧の 1 コマの幅（画素）")
    ap.add_argument("--views", action="store_true", help="一覧でクリップの向きを全部描く")
    a = ap.parse_args(argv)
    doc, errs, warns = generate(write=not a.no_write)
    n = len(doc["animations"])
    print(f"gen_nr_player_anim: {n} 本 → {os.path.relpath(OUT, ROOT)}")
    for w in warns:
        print("  注意:", w)
    if a.check or PREVIEW or a.qa:
        probs = check_ends(doc) + check_hold_keep(doc)
        names = [x for x in CLIPS if not a.only or any(x.startswith(p) for p in a.only.split(","))]
        probs += check_cancel(doc, names) + check_poses(names)
        for p_ in probs:
            print("  検査:", p_)
        print(f"  数値検査: {len(probs)} 件")
    if a.qa or PREVIEW:
        names = [x for x in CLIPS if not a.only or any(x.startswith(p) for p in a.only.split(","))]
        files = qa_render(doc, names)
        print(f"  確認画像: {len(files)} 枚 → {os.path.relpath(QA_DIR, ROOT)}")
    if a.sheet:
        gs = tuple(SHEET_GROUPS) if a.sheet == "all" else tuple(x for x in a.sheet.split(",") if x in SHEET_GROUPS)
        names = [x for x in CLIPS if not a.only or any(x.startswith(p) for p in a.only.split(","))]
        for f in qa_sheets(doc, groups=gs, names=names if a.only else None, size=a.size, all_views=a.views):
            print("  一覧:", f)
    for e in errs:
        print("  NG:", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
