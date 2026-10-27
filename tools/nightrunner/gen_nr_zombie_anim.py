# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — ゾンビ 50 体のアニメーションとアニメコントローラ（DESIGN.md §3 / §12 / §13）。

出力（packs/nightrunner_RP/）:
  animations/nr_zombie_move.animation.json       移動（walk_/run_/idle_<移動> 13 種）・状態（這う・上半身だけ・片脚跳び・
                                                  片脚引きずり・壁登り・よろめき・倒れ・起き上がり・首なし・死体 dead_0..7）・
                                                  重ね（見る・生きている揺れ・折れた腕・腸・燃える・感電・被弾）
  animations/nr_zombie_attack.animation.json     攻撃 atk_<攻撃>（ATTACK_VOCAB の 24 種すべて。windup/active/recover の tick に合わせる）
  animations/nr_zombie_ability.animation.json    能力 ab_<能力>_<段階>（ABILITY_VOCAB の全段階）と ab_<能力>（anim=True）
  animations/nr_zombie_oneshot.animation.json    nr_registry.ZOMBIE_ONESHOTS（react_* ほか。加算・最初と最後のキーが 0）
  animations/nr_zombie_gib.animation.json        nr:gib の空中の回転（nr:spin）と寝姿（nr:rest）
  animation_controllers/nr_zombie.animation_controllers.json      ゾンビ（全 50 体で共通）
  animation_controllers/nr_zombie_gib.animation_controllers.json  nr:gib

────────────────────────────────────────────────────────────────────────────
■ 約束（gen_nr_entities・手書きスクリプトとの契約）
* すべてのアニメは**加算**（バインドポーズ = nr_rig.rest_pose の猫背・腕の外転の上に足す）。
  override_previous_animation は使わない。
* ゾンビの常時の見た目はプロパティ駆動のコントローラ（reference/rendering.md A2〜A7）:
    move   … nr:state・脚・胴の状態 → 立ち（idle/walk/run の混ぜ）/ 片脚引きずり / 片脚跳び / 這う / 上半身だけ /
              壁登り / よろめき / 倒れ→起き上がり / 首なし / 特殊 / 死体 dead_<nr:pose>（hold_on_last_frame）
    arm_r / arm_l / leg_r / leg_l / head / torso … 部位の状態。折れた腕はぶら下がる、断面は bleed_stump、
              切れた直後の数秒は blood_fountain（v.nr_age で「読み込み直後」を除く）
    burn / shock / hurt … 燃えてもがく（q.is_on_fire）・感電の震え（nr:shock）・被弾ののけぞり（q.hurt_time）
    ability … nr:ability の値 1..7 → 短い名前 ab_1..ab_7（種類ごとに ability_states(z) の段階のアニメへ写す）
* 攻撃 atk_* と一発もの（ZOMBIE_ONESHOTS）は**スクリプトの playAnimation**（v.attack_time は使わない）。
    攻撃:    zombieAnim(z, "atk_<攻撃>", {controller: "nr.z.atk", blendOutTime: 0.1})   — windup の始まりに呼ぶ
    一発もの: zombieAnim(z, "<名前>")（既定 controller "nr.z.os"）
  どちらも加算で最初と最後のキーが 0（P3）。長さは ONESHOT_META / ATTACK_META（下）。
  能力の段階 ab_*_* は nr:ability を入れれば自動で出る（スクリプトは playAnimation しない。するなら controller "nr.z.ab"）。
* 移動の周期は q.modified_distance_moved に固定（足が滑らない）。pre_animation が v.nr_ph（0..1）を積算し、
  歩き・走り・這い・跳びのアニメは anim_time_update = v.nr_ph。1 周期の距離は種類の脚の長さから決める。
  idle は v.nr_age（個体ごとに乱数でずらす）で回す。
* 体格の違い: 位置のチャンネルは v.nr_s（身長 / 176cm）倍、寝た姿勢の床合わせは種類ごとの定数 v.nr_gl_*
  （このファイルが素体のリグで順運動学を解いて決め、initialize に書く）。猫背の打ち消しは v.nr_hn（hunch）。
* 腕の動き（arm_*・forearm_*・hand_*）は v.nr_awr / v.nr_awl 倍（折れた腕 = 0.3。代わりに arm_*_broken がぶら下げる）。

■ gen_nr_entities へ（このモジュールを import して使う）
    client_animations(z)      -> {短い名前: アニメ／コントローラの ID}   client entity の description.animations
    client_animate(z)         -> scripts.animate のリスト
    client_initialize(z)      -> scripts.initialize（Molang の行のリスト）
    client_pre_animation(z)   -> scripts.pre_animation（Molang の行のリスト）
    client_particle_effects(z)-> {短い名前: パーティクル ID}            description.particle_effects
    client_sound_effects(z)   -> {}（今は使わない）
    gib_client()              -> {"animations", "animate", "initialize", "pre_animation", "particle_effects"}（nr:gib）
    ONESHOT_META / ATTACK_META -> {短い名前: {"length", "controller", "blend"}}（スクリプト向けの推奨）

■ 確認
    python3 tools/nightrunner/gen_nr_zombie_anim.py            # 生成 + 検査
    python3 tools/nightrunner/gen_nr_zombie_anim.py --qa       # + build_preview/nightrunner/zombie_anim/ に確認画像
    （NR_PREVIEW=1 でも描く）。nr_preview のアニメ評価器で、書き出した JSON そのものを素体のリグに当てて描く。
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import sys
import zlib
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import nr_registry as REG  # noqa: E402
import nr_rig as RIG  # noqa: E402
from nr_common import PREVIEW, RP, SCRATCH, write_json  # noqa: E402

try:  # 登録データの入口（nr_spec が無い・壊れているときはゾンビの spec を直接）
    import nr_spec as SPEC  # noqa: E402
    if not hasattr(SPEC, "zombie_animations"):
        raise ImportError
except Exception:  # noqa: BLE001
    import nr_spec_zombies as SPEC  # type: ignore  # noqa: E402

PRODUCER = "gen_nr_zombie_anim"
ZP = "animation.nr.z."
GP = "animation.nr.gib."
CZ = "controller.animation.nr.z."
CG = "controller.animation.nr.gib."
ANIM_DIR = os.path.join(RP, "animations")
CTRL_DIR = os.path.join(RP, "animation_controllers")
ANIM_FILES = {
    "move": "nr_zombie_move.animation.json",
    "attack": "nr_zombie_attack.animation.json",
    "ability": "nr_zombie_ability.animation.json",
    "oneshot": "nr_zombie_oneshot.animation.json",
    "gib": "nr_zombie_gib.animation.json",
}
CTRL_FILES = {"z": "nr_zombie.animation_controllers.json", "gib": "nr_zombie_gib.animation_controllers.json"}
QA_DIR = os.path.join(SCRATCH, "zombie_anim")

ANIM_FORMAT = "1.8.0"       # バニラのアニメと同じ
CTRL_FORMAT = "1.10.0"

TICK = 1.0 / 20.0
REF_BUILD = dict(height_cm=176, heads=7.4, bulk=1.0, limb=1.0, hunch=14, arm_len=1.03)
REF_L = RIG.landmarks(REF_BUILD)
REF_T = REF_L.t

ARM_R = ("arm_r", "forearm_r", "hand_r")
ARM_L = ("arm_l", "forearm_l", "hand_l")
LEG_R = ("leg_r", "shin_r", "foot_r")
LEG_L = ("leg_l", "shin_l", "foot_l")
MIRROR = {"arm_r": "arm_l", "forearm_r": "forearm_l", "hand_r": "hand_l",
          "leg_r": "leg_l", "shin_r": "shin_l", "foot_r": "foot_l",
          "arm_r_wound": "arm_l_wound", "stump_arm_r_lower": "stump_arm_l_lower",
          "stump_arm_r_upper": "stump_arm_l_upper", "stump_leg_r_lower": "stump_leg_l_lower",
          "stump_leg_r_upper": "stump_leg_l_upper"}
MIRROR.update({v: k for k, v in list(MIRROR.items())})


# ===========================================================================
#  1. 種類の骨格（spec → nr_rig の build）と素体のリグ
# ===========================================================================
def rig_build(z) -> dict:
    """spec の骨格欄 → nr_rig.ZombieRig の build（gen_nr_zombies と同じ寸法）。"""
    return dict(height_cm=z["height_cm"], heads=z["heads"], bulk=z["bulk"], limb=z["limb"],
                hunch=z["hunch"], arm_len=z["arm_len"], female=bool(z.get("female", False)))


_RIG_CACHE: Dict[str, Tuple[object, object]] = {}


def bare_rig(name: str, build: dict):
    """素体（服なし）のリグ（model, rig）。ボーンの pivot・休みの回転・体の箱が本物と同じ。"""
    key = name + "|" + repr(sorted(build.items()))
    if key not in _RIG_CACHE:
        m = RIG.new_model("anim_" + name)
        r = RIG.ZombieRig(m, dict(build), detail=1, seed=zlib.crc32(name.encode()))
        _RIG_CACHE[key] = (m, r)
    return _RIG_CACHE[key]


def zscale(z) -> float:
    """位置のチャンネルの倍率（身長 / 基準 176cm）。"""
    return RIG.landmarks(rig_build(z)).t / REF_T


# ===========================================================================
#  2. 回転・順運動学（nr_rig / nr_preview と同じ規則: R = Rz(-rz)·Ry(ry)·Rx(-rx)）
# ===========================================================================
rot = RIG.rot
euler = RIG.euler


def _T(t) -> np.ndarray:
    M = np.eye(4)
    M[:3, 3] = t
    return M


def _R4(R) -> np.ndarray:
    M = np.eye(4)
    M[:3, :3] = R
    return M


class Skel:
    """素体リグの骨格（pivot・休みの回転・親）。pose = {bone: {"rot": [..], "pos": [..]}}（休みへの加算）。"""

    def __init__(self, model):
        self.model = model
        self.bones = {b.name: b for b in model.bones}
        self.parent = {b.name: b.parent for b in model.bones}
        self.piv = {b.name: np.array(b.pivot, float) for b in model.bones}
        self.rest = {b.name: np.array(b.rotation if b.rotation else (0.0, 0.0, 0.0), float)
                     for b in model.bones}
        self.rig = getattr(model, "nr_rig", None)
        self.L = self.rig.L if self.rig is not None else None
        self.hunch = float(self.rig.hunch) if self.rig is not None else 0.0

    def local(self, name, rot3=(0, 0, 0), pos=(0, 0, 0)) -> np.ndarray:
        p = self.piv[name]
        R = rot(*(self.rest[name] + np.asarray(rot3, float)))
        return _T(np.asarray(pos, float) + p) @ _R4(R) @ _T(-p)

    def world(self, pose: Optional[dict] = None) -> Dict[str, np.ndarray]:
        pose = pose or {}
        out: Dict[str, np.ndarray] = {}

        def w(n):
            if n in out:
                return out[n]
            e = pose.get(n, {})
            L = self.local(n, e.get("rot", (0, 0, 0)), e.get("pos", (0, 0, 0)))
            par = self.parent.get(n)
            M = (w(par) @ L) if par and par in self.bones else L
            out[n] = M
            return M

        for n in self.bones:
            w(n)
        return out

    def point(self, W, bone, p) -> np.ndarray:
        return (W[bone] @ np.array([*p, 1.0]))[:3]

    def min_y(self, W, skip=()) -> float:
        """見えている体のキューブ（ゴア用ボーンを除く）の一番低い点（単位）。"""
        lo = 1e9
        for n, b in self.bones.items():
            if n in RIG.GORE_BONES or n in skip or not b.cubes:
                continue
            for c in b.cubes:
                P = (W[n] @ (RIG.cube_matrix(c) @ RIG.cube_corners(c).T)).T
                lo = min(lo, float(P[:, 1].min()))
        return lo


# ---------------------------------------------------------------------------
#  逆運動学（2 本の骨: 股→膝→足首 / 肩→肘→手首）
# ---------------------------------------------------------------------------
def _aim(skel: Skel, W_parent: np.ndarray, bone: str, vec_local: np.ndarray, target: np.ndarray,
         ry: float = 0.0) -> Tuple[float, float]:
    """bone の休みの空間でのベクトル vec_local（pivot から）を、世界の target へ向ける rx, rz（ry 固定。
    値は休みの回転を含む「全体の」Euler）。ガウス・ニュートンで解く。"""
    p = skel.piv[bone]
    piv_w = (W_parent @ np.array([*p, 1.0]))[:3]
    Rp = W_parent[:3, :3]
    d = np.asarray(target, float) - piv_w
    want = np.linalg.solve(Rp, d)                       # 親の空間での向き
    n_want = np.linalg.norm(want)
    if n_want < 1e-6:
        return 0.0, 0.0
    want = want / n_want
    v = vec_local / max(1e-9, np.linalg.norm(vec_local))
    # 初期値: 球面座標の近似
    x = np.array([0.0, 0.0])
    best = None
    for guess in ((0.0, 0.0), (-60.0, 0.0), (60.0, 0.0), (-120.0, 0.0), (0.0, 60.0), (0.0, -60.0)):
        x = np.array(guess, float)
        for _ in range(40):
            f = rot(x[0], ry, x[1]) @ v - want
            J = np.zeros((3, 2))
            for k in range(2):
                dx = np.zeros(2)
                dx[k] = 1e-3
                J[:, k] = (rot((x + dx)[0], ry, (x + dx)[1]) @ v - want - f) / 1e-3
            step, *_ = np.linalg.lstsq(J, -f, rcond=None)
            x = x + np.clip(step, -30, 30)
            if np.linalg.norm(f) < 1e-7:
                break
        err = np.linalg.norm(rot(x[0], ry, x[1]) @ v - want)
        if best is None or err < best[0] - 1e-9:
            best = (err, x.copy())
        if err < 1e-5:
            break
    x = best[1]
    return float(_wrap(x[0])), float(_wrap(x[1]))


def _wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def solve_limb(skel: Skel, W: Dict[str, np.ndarray], upper: str, lower: str, end: str,
               target: np.ndarray, bend_axis: int = 0, bend_sign: float = 1.0,
               ry: float = 0.0, max_bend: float = 160.0) -> Tuple[np.ndarray, np.ndarray]:
    """upper（股・肩）→ lower（膝・肘）→ end（足首・手首の pivot）が target に届く回転（休みへの加算）。

    bend は lower の rx（脚: 正 = 膝が曲がって脛が後ろ、腕: 負 = 肘が曲がって前腕が前）。
    W は upper の親までが正しい世界行列（pose 適用済み）。"""
    pu, pl, pe = skel.piv[upper], skel.piv[lower], skel.piv[end]
    l1 = np.linalg.norm(pl - pu)
    l2 = np.linalg.norm(pe - pl)
    par = skel.parent[upper]
    Wp = W[par]
    piv_w = (Wp @ np.array([*pu, 1.0]))[:3]
    dist = float(np.linalg.norm(np.asarray(target) - piv_w))
    dist = min(dist, (l1 + l2) * 0.9995)
    # 余弦定理で曲げ角（lower の休みの回転は 0 を前提）
    u1 = pl - pu
    best_th, best_err = 0.0, 1e9
    for th in np.linspace(0.0, max_bend, 321):
        v = u1 + rot(bend_sign * th, 0, 0) @ (pe - pl)
        err = abs(np.linalg.norm(v) - dist)
        if err < best_err:
            best_err, best_th = err, th
    # 細かく
    lo, hi = max(0.0, best_th - 0.6), min(max_bend, best_th + 0.6)
    for _ in range(30):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        e1 = abs(np.linalg.norm(u1 + rot(bend_sign * m1, 0, 0) @ (pe - pl)) - dist)
        e2 = abs(np.linalg.norm(u1 + rot(bend_sign * m2, 0, 0) @ (pe - pl)) - dist)
        if e1 < e2:
            hi = m2
        else:
            lo = m1
    th = (lo + hi) / 2
    v = u1 + rot(bend_sign * th, 0, 0) @ (pe - pl)
    rx, rz = _aim(skel, Wp, upper, v, target, ry=ry + skel.rest[upper][1])
    up_total = np.array([rx, ry + skel.rest[upper][1], rz])
    up = up_total - skel.rest[upper]
    low = np.array([bend_sign * th, 0.0, 0.0]) - skel.rest[lower]
    return up, low


def orient_end(skel: Skel, W_lower: np.ndarray, end: str, R_target: np.ndarray) -> np.ndarray:
    """end（足・手）の世界の向きを R_target にする回転（休みへの加算）。"""
    Rw = W_lower[:3, :3]
    R_local = np.linalg.solve(Rw, R_target)
    e = np.array(euler(R_local))
    return e - skel.rest[end]


# ===========================================================================
#  3. クリップ（キーは「その時刻の全身のポーズ」。書かないボーンは 0 = 休み）
# ===========================================================================
def P(**bones) -> dict:
    """ポーズを書く補助: P(arm_r=(-30, 0, 10), root_pos=(0, -1, 0))。
    `<bone>=(rx, ry, rz)` は回転、`<bone>_pos=(x, y, z)` は位置、値に文字列（Molang）も可。"""
    out: Dict[str, dict] = {}
    for k, v in bones.items():
        if v is None:
            continue
        if k.endswith("_pos"):
            out.setdefault(k[:-4], {})["pos"] = list(v)
        elif k.endswith("_scl"):
            out.setdefault(k[:-4], {})["scl"] = list(v)
        else:
            out.setdefault(k, {})["rot"] = list(v)
    return out


def padd(*poses) -> dict:
    """ポーズの和（回転・位置は足す。文字列が混ざれば Molang の和）。"""
    out: Dict[str, dict] = {}
    for p in poses:
        for b, e in (p or {}).items():
            o = out.setdefault(b, {})
            for ch, v in e.items():
                if ch == "scl":
                    o[ch] = [_mul(a, c) for a, c in zip(o.get(ch, [1, 1, 1]), v)]
                else:
                    o[ch] = [_add(a, c) for a, c in zip(o.get(ch, [0, 0, 0]), v)]
    return out


def pscale(p: dict, k: float, chans=("rot", "pos")) -> dict:
    out = {}
    for b, e in (p or {}).items():
        out[b] = {}
        for ch, v in e.items():
            if ch in chans:
                out[b][ch] = [_mulk(x, k) for x in v]
            else:
                out[b][ch] = list(v)
    return out


def pmirror(p: dict) -> dict:
    """左右反転（ボーンを入れ替え、ry・rz と位置 x の符号を反転）。"""
    out = {}
    for b, e in (p or {}).items():
        mb = MIRROR.get(b, b)
        o = {}
        for ch, v in e.items():
            if ch == "rot":
                o[ch] = [v[0], _mulk(v[1], -1), _mulk(v[2], -1)]
            elif ch == "pos":
                o[ch] = [_mulk(v[0], -1), v[1], v[2]]
            else:
                o[ch] = list(v)
        out[mb] = o
    return out


def _isnum(x) -> bool:
    return isinstance(x, (int, float, np.floating, np.integer))


def _add(a, b):
    if _isnum(a) and _isnum(b):
        return float(a) + float(b)
    if _isnum(a) and abs(float(a)) < 1e-9:
        return b
    if _isnum(b) and abs(float(b)) < 1e-9:
        return a
    return f"({fmt(a)}) + ({fmt(b)})"


def _mul(a, b):
    if _isnum(a) and _isnum(b):
        return float(a) * float(b)
    return f"({fmt(a)}) * ({fmt(b)})"


def _mulk(a, k: float):
    if _isnum(a):
        return float(a) * k
    if abs(k - 1.0) < 1e-12:
        return a
    return f"({a}) * {fmt(k)}"


def fmt(x, nd: int = 2) -> str:
    """数を短い文字列に（-0 を 0 に、末尾の 0 を落とす）。"""
    if not _isnum(x):
        return str(x)
    v = round(float(x), nd)
    if v == 0:
        v = 0.0
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-") else "0"


def num(x, nd: int = 2):
    v = round(float(x), nd)
    return 0.0 if v == 0 else v


@dataclass
class Clip:
    """1 本のアニメーション。keys = [(時刻, ポーズ, lerp)]（ポーズは全身。書かないボーンは 0）。"""
    name: str                      # 短い名前（ZP / GP は書き出しで付ける）
    length: float
    loop: object = False           # True / False / "hold_on_last_frame"
    keys: List[Tuple[float, dict, str]] = field(default_factory=list)
    expr: Dict[str, Dict[str, list]] = field(default_factory=dict)   # キーを持たないチャンネルの式
    anim_time_update: Optional[str] = None
    blend_weight: Optional[str] = None
    lerp: str = "catmullrom"
    particles: Dict[float, list] = field(default_factory=dict)
    kind: str = "move"             # move / attack / ability / oneshot / gib
    prefix: str = ZP
    oneshot: bool = False          # P3（最初と最後のキーが 0）を検査する
    weight_arms: bool = True       # 腕のチャンネルを v.nr_awr / v.nr_awl 倍
    scale_pos: bool = True         # 位置を v.nr_s 倍
    pos_var: str = "v.nr_s"
    note: str = ""

    @property
    def id(self) -> str:
        return self.prefix + self.name

    def key(self, t: float, pose: dict, lerp: Optional[str] = None) -> "Clip":
        self.keys.append((float(t), pose or {}, lerp or self.lerp))
        return self

    def channels(self) -> Dict[Tuple[str, str], bool]:
        out = {}
        for _t, p, _l in self.keys:
            for b, e in p.items():
                for ch in e:
                    out[(b, ch)] = True
        return out


def _arm_weight(bone: str) -> Optional[str]:
    if bone in ARM_R:
        return "v.nr_awr"
    if bone in ARM_L:
        return "v.nr_awl"
    return None


def _component(x, ch: str, bone: str, clip: Clip):
    """1 成分を書き出す値（数 or Molang 文字列）に。"""
    nd = 2
    w = _arm_weight(bone) if clip.weight_arms and ch in ("rot", "pos") else None
    sv = clip.pos_var if (clip.scale_pos and ch == "pos") else None
    if _isnum(x):
        v = num(x, nd)
        if v == 0.0 and ch != "scl":
            return 0.0
        if not w and not sv:
            return v
        s = fmt(v, nd)
    else:
        s = f"({x})"
    for m in (sv, w):
        if m:
            s = f"{s} * {m}"
    return s


def _vec(v, ch, bone, clip) -> list:
    return [_component(x, ch, bone, clip) for x in v]


def _is_zero(vec, ch) -> bool:
    if ch == "scl":
        return all(_isnum(x) and abs(float(x) - 1.0) < 1e-4 for x in vec)
    return all(_isnum(x) and abs(float(x)) < 5e-3 for x in vec)


CH_JSON = {"rot": "rotation", "pos": "position", "scl": "scale"}


def clip_json(clip: Clip) -> dict:
    """Bedrock のアニメーション 1 本（ボーン名は小文字のまま）。"""
    out: Dict[str, object] = {}
    if clip.loop is not False:
        out["loop"] = clip.loop
    out["animation_length"] = round(float(clip.length), 4)
    if clip.anim_time_update:
        out["anim_time_update"] = clip.anim_time_update
    if clip.blend_weight:
        out["blend_weight"] = clip.blend_weight
    bones: Dict[str, dict] = {}
    chans = clip.channels()
    keys = sorted(clip.keys, key=lambda k: k[0])
    for (b, ch) in sorted(chans):
        seq = []
        for t, p, lerp in keys:
            e = p.get(b, {})
            v = e.get(ch)
            if v is None:
                v = [1.0, 1.0, 1.0] if ch == "scl" else [0.0, 0.0, 0.0]
            seq.append((t, v, lerp))
        if all(_is_zero(v, ch) for _t, v, _l in seq):
            continue
        # 同じ値が 3 つ以上続く中間のキーを落とす（線形のときだけ。catmullrom は形が変わるので残す）
        if len(seq) == 1:
            val = _vec(seq[0][1], ch, b, clip)
        else:
            val = {}
            for t, v, lerp in seq:
                ts = fmt(t, 4)
                vv = _vec(v, ch, b, clip)
                if lerp == "linear":
                    val[ts] = vv
                elif lerp == "step":
                    val[ts] = {"pre": vv, "post": vv}
                else:
                    val[ts] = {"post": vv, "lerp_mode": lerp}
        bones.setdefault(b, {})[CH_JSON[ch]] = val
    for b, chs in clip.expr.items():
        for ch, v in chs.items():
            if (b, ch) in chans and CH_JSON[ch] in bones.get(b, {}):
                raise ValueError(f"{clip.name}: {b}.{ch} has both keys and expr")
            bones.setdefault(b, {})[CH_JSON[ch]] = _vec(v, ch, b, clip)
    if not bones:
        bones = {"root": {"rotation": [0.0, 0.0, 0.0]}}
    out["bones"] = {b: bones[b] for b in sorted(bones)}
    if clip.particles:
        pe = {}
        for t in sorted(clip.particles):
            effs = clip.particles[t]
            pe[fmt(t, 4)] = effs if len(effs) > 1 else effs[0]
        out["particle_effects"] = pe
    return out


# ===========================================================================
#  4. 姿勢のソルバ（足を床に・手を床／壁に）
# ===========================================================================
SIDES = (("r", -1.0), ("l", 1.0))


def ref_skel(name: str = "ref", build: Optional[dict] = None) -> Skel:
    m, _r = bare_rig(name, build or REF_BUILD)
    return Skel(m)


def leg_rest(skel: Skel, s: str) -> np.ndarray:
    """休みの足首の位置（単位）。"""
    return skel.piv[f"foot_{s}"].copy()


def _foot_rot(pitch: float, yaw: float, roll: float = 0.0) -> np.ndarray:
    """世界での足の向き（pitch 正 = つま先が下、yaw 正 = つま先が右へ、roll 正 = 外側が下）。"""
    return rot(pitch, yaw, roll)


def solve_legs(skel: Skel, pose: dict, feet: Dict[str, tuple], fix_ground: bool = True,
               bend_hint: float = 1.0) -> dict:
    """pose（root / waist / pelvis まで決めたもの）に、feet = {s: (足首の世界の位置, pitch, yaw, roll?)} を
    満たす脚の回転を書き足して返す。fix_ground なら足のキューブが床（y=0）より下へ出ないよう足首を上げる。"""
    pose = copy.deepcopy(pose)
    for s, spec in feet.items():
        tgt = np.array(spec[0], float)
        pitch, yaw = float(spec[1]), float(spec[2])
        roll = float(spec[3]) if len(spec) > 3 else 0.0
        thigh_ry = float(spec[4]) if len(spec) > 4 else 0.0
        lift = 0.0
        for _it in range(4):
            W = skel.world(pose)
            t2 = tgt + np.array([0.0, lift, 0.0])
            up, low = solve_limb(skel, W, f"leg_{s}", f"shin_{s}", f"foot_{s}", t2, bend_sign=bend_hint,
                                 ry=thigh_ry)
            pose.setdefault(f"leg_{s}", {})["rot"] = list(up)
            pose.setdefault(f"shin_{s}", {})["rot"] = list(low)
            W = skel.world(pose)
            ft = orient_end(skel, W[f"shin_{s}"], f"foot_{s}", _foot_rot(pitch, yaw, roll))
            pose.setdefault(f"foot_{s}", {})["rot"] = list(ft)
            if not fix_ground:
                break
            W = skel.world(pose)
            lo = _bone_min_y(skel, W, f"foot_{s}")
            if lo >= -0.02:
                break
            lift += -lo
    return pose


def _bone_min_y(skel: Skel, W, bone) -> float:
    lo = 1e9
    for c in skel.bones[bone].cubes:
        Pp = (W[bone] @ (RIG.cube_matrix(c) @ RIG.cube_corners(c).T)).T
        lo = min(lo, float(Pp[:, 1].min()))
    return lo


def solve_arms(skel: Skel, pose: dict, hands: Dict[str, tuple], ry: Optional[Dict[str, float]] = None) -> dict:
    """hands = {s: (手首の世界の位置, 手の世界の回転行列 or None)}。肘は前（前腕の rx 負）へ曲げる。"""
    pose = copy.deepcopy(pose)
    for s, spec in hands.items():
        tgt = np.array(spec[0], float)
        W = skel.world(pose)
        r_ = (ry or {}).get(s, 0.0)
        up, low = solve_limb(skel, W, f"arm_{s}", f"forearm_{s}", f"hand_{s}", tgt, bend_sign=-1.0, ry=r_)
        pose.setdefault(f"arm_{s}", {})["rot"] = list(up)
        pose.setdefault(f"forearm_{s}", {})["rot"] = list(low)
        if len(spec) > 1 and spec[1] is not None:
            W = skel.world(pose)
            pose.setdefault(f"hand_{s}", {})["rot"] = list(orient_end(skel, W[f"forearm_{s}"], f"hand_{s}", spec[1]))
    return pose


def _smooth(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _frac(x: float) -> float:
    return x - math.floor(x)


# ===========================================================================
#  5. 歩容エンジン（2 歩で 1 周期。周期の時刻 = 移動距離の位相 v.nr_ph）
# ===========================================================================
@dataclass
class Gait:
    stride: float = 0.40          # 接地中に足が後ろへ動く距離（脚の長さ LL に対する割合）
    duty: float = 0.62            # 接地の割合（0.5 未満で両足が浮く走り）
    lift: float = 0.07            # 振り出しの足の高さ（LL に対する割合）
    knee: float = 10.0            # 接地中の膝の曲げ（度、最小）
    width: float = 0.0            # 足の横の開き（単位、外へ正）
    offset: float = 0.5           # 左脚の位相のずれ（0.5 = 交互、0.1 = 両脚で跳ぶ）
    toe_drag: float = 0.0         # 振り出し中のつま先の下がり（度）。引きずる歩き
    heel: float = 8.0             # 踵から着く角度（つま先が上、度）
    toeoff: float = 18.0          # 蹴り出しの踵の上がり（度）
    toe_out: float = 6.0          # つま先の外向き（度）
    drop: float = 0.0             # 腰を落とす量（単位。しゃがみ歩き）
    bob: float = 0.0              # 追加の上下（単位。正 = 接地の中ほどで上）
    flight: float = 0.0           # 両足が浮く間の跳ね（単位）
    sway: float = 0.3             # 左右の揺れ（単位）
    roll: float = 4.0             # 腰の傾き（度、遊脚側が下がる）
    twist: float = 5.0            # 腰のねじれ（度）
    lean: float = 6.0             # 腹の前傾（度、猫背に加える）
    chest: float = 4.0            # 胸の前傾（度）
    length: float = 1.0           # 周期の長さ（1 = 2 歩、2 = 4 歩）
    keys: int = 16                # 1 周期のキーの数
    legs: Dict[str, dict] = field(default_factory=dict)   # 片脚だけの上書き（limp の悪い脚など）
    upper: Optional[Callable] = None                       # (phase, ctx) -> ポーズ（腕・首・頭・顎）
    surge: float = 0.0            # 前後の揺れ（単位。接地で後ろへ）
    drag_leg: str = ""            # 引きずる脚（その脚は膝をほぼ伸ばしたまま、足の甲で地面を擦る）


def leg_len(skel: Skel) -> float:
    return float(skel.piv["leg_r"][1] - skel.piv["foot_r"][1])


def gait_feet(g: Gait, skel: Skel, phi: float) -> Dict[str, dict]:
    """周期 phi（0..length）での各足の情報: 足首の位置（root の移動前、床基準）・向き・接地か・前後の割合。"""
    LL = leg_len(skel)
    out = {}
    for s, sgn in SIDES:
        prm = dict(stride=g.stride, duty=g.duty, lift=g.lift, toe_drag=g.toe_drag, heel=g.heel,
                   toeoff=g.toeoff, toe_out=g.toe_out, width=g.width, knee=g.knee, abduct=0.0)
        prm.update(g.legs.get(s, {}))
        psi = _frac(phi + (g.offset if s == "l" else 0.0))
        S = prm["stride"] * LL
        d = prm["duty"]
        base = leg_rest(skel, s)
        x = base[0] + sgn * prm["width"]
        foot_l = skel.L.foot_l
        ball, heel_d = 0.55 * foot_l, 0.22 * foot_l
        y = base[1]
        if psi < d:
            u = psi / d
            z = -S / 2 + S * u
            pitch = 0.0
            hs = 0.12
            if u < hs:                                   # 踵から着く
                k = 1.0 - _smooth(u / hs)
                pitch = -prm["heel"] * k
                y += heel_d * math.sin(math.radians(prm["heel"] * k))
            to = 0.22
            if u > 1.0 - to:                              # 踵が上がる
                k = _smooth((u - (1.0 - to)) / to)
                pitch = prm["toeoff"] * k
                y += ball * math.sin(math.radians(pitch))
                z += ball * (1 - math.cos(math.radians(pitch))) * 0.0
            stance = True
            fwd = 1.0 - 2.0 * u
        else:
            u = (psi - d) / (1.0 - d)
            e = 0.5 - 0.5 * math.cos(math.pi * u)
            z = S / 2 - S * e
            y += prm["lift"] * LL * math.sin(math.pi * u) ** 0.8
            # 蹴り出しの角度 → 引きずり → 踵の上がり
            p0, p1 = prm["toeoff"], -prm["heel"]
            pitch = p0 + (p1 - p0) * _smooth(u) + prm["toe_drag"] * math.sin(math.pi * min(1.0, u * 1.2))
            if u < 0.25:
                y += ball * math.sin(math.radians(prm["toeoff"])) * (1.0 - u / 0.25)
            stance = False
            fwd = -1.0 + 2.0 * e
            x += sgn * prm.get("abduct", 0.0) * math.sin(math.pi * u)
        out[s] = dict(pos=np.array([x, y, z]), pitch=pitch, yaw=-sgn * prm["toe_out"], stance=stance,
                      fwd=fwd, psi=psi, u=u, prm=prm)
    return out


def _hip_height_for(skel: Skel, s: str, ankle: np.ndarray, knee: float) -> float:
    """足首 ankle に膝 knee 度で届く股関節の高さ（y）。"""
    pu, pl, pe = skel.piv[f"leg_{s}"], skel.piv[f"shin_{s}"], skel.piv[f"foot_{s}"]
    v = (pl - pu) + rot(knee, 0, 0) @ (pe - pl)
    Le = float(np.linalg.norm(v))
    dx = ankle[0] - pu[0]
    dz = ankle[2] - pu[2]
    h2 = Le * Le - dx * dx - dz * dz
    return ankle[1] + math.sqrt(max(h2, 1.0))


def gait_pose(g: Gait, skel: Skel, phi: float, cache: Optional[dict] = None) -> dict:
    """周期 phi の全身のポーズ（脚は逆運動学、腰の高さは接地脚が届く高さ）。"""
    feet = gait_feet(g, skel, phi)
    hip0 = float(skel.piv["leg_r"][1])
    duty = g.duty
    # 腰の高さ: 接地脚の要求の小さい方。両脚が浮くときは前後の接地から放物線
    def need(ph):
        ff = gait_feet(g, skel, ph)
        hs = [_hip_height_for(skel, s, ff[s]["pos"], ff[s]["prm"]["knee"]) for s, _ in SIDES if ff[s]["stance"]]
        return min(hs) if hs else None
    h = need(phi)
    if h is None:                                          # 空中: 前後の接地の値を探して放物線で結ぶ
        a = b = None
        for k in range(1, 200):
            if a is None:
                ha = need(phi - k * 0.005)
                if ha is not None:
                    a = (k * 0.005, ha)
            if b is None:
                hb = need(phi + k * 0.005)
                if hb is not None:
                    b = (k * 0.005, hb)
            if a and b:
                break
        ta, tb = a[0], b[0]
        w = ta / (ta + tb)
        h = a[1] + (b[1] - a[1]) * w + g.flight * 4 * w * (1 - w)
    rooty = h - hip0 - g.drop
    # 追加の上下・左右・前後
    rooty += g.bob * math.cos(2 * math.pi * (phi - duty / 2) * 2)
    sx = -g.sway * math.cos(2 * math.pi * (phi - duty / 2))
    sz = g.surge * math.cos(2 * math.pi * (phi - duty / 2) * 2)
    roll = g.roll * math.cos(2 * math.pi * (phi - duty / 2))
    twist = g.twist * math.cos(2 * math.pi * (phi - duty / 2))
    pose = P(root_pos=(sx, rooty, sz), waist=(0.0, twist, roll))
    ctx = dict(phi=phi, feet=feet, twist=twist, roll=roll, rooty=rooty, sway=sx, g=g, skel=skel)
    up = g.upper(phi, ctx) if g.upper else {}
    pose = padd(pose, {k: v for k, v in up.items() if not k.startswith(("leg_", "shin_", "foot_"))})
    # 足（root の位置は足首の世界座標に影響しない: 足は床に固定）
    tg = {}
    for s, _sgn in SIDES:
        f = feet[s]
        tg[s] = (f["pos"], f["pitch"], f["yaw"])
    num_pose = _numeric(pose, skel)
    solved = solve_legs(skel, num_pose, tg)
    # 接地脚が届かなかったら腰を下げてやり直す
    W = skel.world(solved)
    worst = 0.0
    for s, _ in SIDES:
        if feet[s]["stance"]:
            got = skel.point(W, f"foot_{s}", skel.piv[f"foot_{s}"])
            worst = max(worst, got[1] - feet[s]["pos"][1])
    if worst > 0.03:
        pose["root"]["pos"][1] = pose["root"]["pos"][1] - worst - 0.02
        num_pose = _numeric(pose, skel)
        solved = solve_legs(skel, num_pose, tg)
    for b in ("leg_r", "shin_r", "foot_r", "leg_l", "shin_l", "foot_l"):
        pose[b] = {"rot": solved[b]["rot"]}
    # 上半身の追加（脚の上書きを持つ upper は脚にも足す）
    extra = {k: v for k, v in up.items() if k.startswith(("leg_", "shin_", "foot_"))}
    return padd(pose, extra)


DESIGN_VARS: Dict[str, float] = {"v.nr_s": 1.0, "v.nr_awr": 1.0, "v.nr_awl": 1.0, "v.nr_hn": 14.0,
                                 "v.nr_reach": 0.0, "v.nr_tilt": 0.0, "v.nr_limp": 0.0}


def _numeric(pose: dict, skel: Optional["Skel"] = None) -> dict:
    """Molang を含むポーズを数にする（逆運動学の計算用。変数は DESIGN_VARS、v.nr_hn は skel の猫背）。"""
    import nr_preview as NP
    var = dict(DESIGN_VARS)
    if skel is not None:
        var["v.nr_hn"] = skel.hunch
    out = {}
    for b, e in pose.items():
        out[b] = {}
        for ch, v in e.items():
            out[b][ch] = [float(x) if _isnum(x) else float(NP.molang(str(x), variables=var)) for x in v]
    return out


def gait_clip(name: str, g: Gait, skel: Optional[Skel] = None, note: str = "") -> Clip:
    skel = skel or ref_skel()
    c = Clip(name, g.length, loop=True, anim_time_update="v.nr_ph", note=note)
    n = int(round(g.keys * g.length))
    poses = []
    for i in range(n):
        phi = g.length * i / n
        poses.append(gait_pose(g, skel, phi))
    for i, p in enumerate(poses + [poses[0]]):
        c.key(g.length * i / n, p)
    return c


def cycle_blocks(g: Gait, scale: float = 1.0, skel: Optional[Skel] = None) -> float:
    """位相 1 あたりに体が進む距離（ブロック）。接地の足の速さ = 体の速さ（滑らない）。"""
    skel = skel or ref_skel()
    S = g.stride * leg_len(skel)
    return S / g.duty / 16.0 * scale


# ===========================================================================
#  6. 上半身（腕の振り・前傾・頭の揺れ・顎）
# ===========================================================================
def _sin(x):
    return math.sin(2 * math.pi * x)


def _cos(x):
    return math.cos(2 * math.pi * x)


def make_upper(U: dict) -> Callable:
    """歩容の上半身の関数を作る。U の鍵:
      arms  = dict(rx 前へ上げる基本(負), A 振り幅, lag 遅れ(周期), rz 外へ開く, rzA, fore 肘(負=曲げ), foreA,
                   foreLag, hand 手首, sync 0=脚と逆に交互 / 1=両腕そろえる, cancel 前傾の打ち消し 0..1, ry)
      reach = 個体差で腕を前へ伸ばすポーズ（P(...)、v.nr_reach 倍で足す）
      head  = dict(keep 視線を前へ戻す 0..1, nod 縦揺れ, nodLag, loll 首の傾げ, lollLag, yaw, yawF, neck)
      jaw   = (開き, 揺れ, 周波数)
      torso = dict(ct ねじれの打ち消し, cr 傾きの打ち消し, lurch=(量, 鋭さ), rollA, rollF)
      extra = (phi, ctx) -> ポーズ"""
    arms = dict(rx=0.0, A=10.0, lag=0.08, rz=4.0, rzA=0.0, fore=-10.0, foreA=6.0, foreLag=0.12, hand=6.0,
                sync=0, cancel=0.9, ry=0.0, handA=0.0)
    arms.update(U.get("arms", {}))
    head = dict(keep=0.6, nod=3.0, nodLag=0.05, loll=4.0, lollLag=0.15, yaw=0.0, yawF=0.5, neck=0.0, tilt=True)
    head.update(U.get("head", {}))
    torso = dict(ct=0.6, cr=0.7, lurch=(0.0, 4.0), rollA=0.0, rollF=0.5, twist=0.0)
    torso.update(U.get("torso", {}))
    jaw = U.get("jaw", (4.0, 2.0, 2.0))
    reach = U.get("reach")
    extra = U.get("extra")

    def upper(phi, ctx):
        g, skel = ctx["g"], ctx["skel"]
        tw, rl = ctx["twist"], ctx["roll"]
        d = g.duty
        ln = g.lean
        # つんのめり（接地の瞬間に上体が前へ落ちる）
        lu = 0.0
        if torso["lurch"][0]:
            for k in (0.0, g.offset):
                x = _frac(phi - k)
                lu += torso["lurch"][0] * math.exp(-torso["lurch"][1] * x) * min(1.0, x * 25)
        troll = -rl * torso["cr"] + torso["rollA"] * _sin(phi * torso["rollF"])
        pose = P(torso=(ln + lu * 0.6, -tw * torso["ct"] * 0.5 + torso["twist"] * _sin(phi), troll),
                 chest=(g.chest + lu * 0.4, -tw * torso["ct"] * 0.5, troll * 0.4))
        tot_lean = ln + g.chest + lu
        # 腕
        ff = gait_feet(g, skel, phi - arms["lag"])
        for s, sgn in SIDES:
            o = "l" if s == "r" else "r"
            sw = ff["r"]["fwd"] if arms["sync"] else ff[o]["fwd"]       # 反対の脚が前 → この腕が前
            ffl = gait_feet(g, skel, phi - arms["foreLag"])
            swf = ffl["r"]["fwd"] if arms["sync"] else ffl[o]["fwd"]
            rx = arms["rx"] - arms["A"] * sw + tot_lean * arms["cancel"]
            rz = -sgn * (arms["rz"] + arms["rzA"] * (0.5 + 0.5 * sw))
            fx = arms["fore"] + arms["foreA"] * (0.5 - 0.5 * swf) * -1.0
            hx = arms["hand"] + arms["handA"] * swf
            pose = padd(pose, {f"arm_{s}": {"rot": [rx, -sgn * arms["ry"], rz]},
                               f"forearm_{s}": {"rot": [fx, 0.0, 0.0]},
                               f"hand_{s}": {"rot": [hx, 0.0, 0.0]}})
        # 首・頭
        nod = head["nod"] * _cos((phi - head["nodLag"]) * 2)
        loll = head["loll"] * _cos(phi - d / 2 - head["lollLag"])
        yaw = head["yaw"] * _sin(phi * head["yawF"])
        keep = -tot_lean * head["keep"]
        pose = padd(pose, P(neck=(head["neck"] + keep * 0.4, yaw * 0.4, loll * 0.4),
                            head=(keep * 0.6 + nod, yaw * 0.6 + tw * 0.3, loll * 0.6)))
        if head["tilt"]:
            pose = padd(pose, {"head": {"rot": [0.0, 0.0, "v.nr_tilt"]}})
        pose = padd(pose, P(jaw=(jaw[0] + jaw[1] * _sin(phi * jaw[2]), 0, 0)))
        if reach:
            pose = padd(pose, mul_var(reach, "v.nr_reach"))
        if extra:
            pose = padd(pose, extra(phi, ctx))
        return pose
    return upper


def mul_var(pose: dict, var: str) -> dict:
    """ポーズの数値を Molang の変数倍に（"(-60) * v.nr_reach"）。"""
    out = {}
    for b, e in pose.items():
        out[b] = {}
        for ch, v in e.items():
            out[b][ch] = [(f"{fmt(x)} * {var}" if (_isnum(x) and abs(x) > 1e-6) else (0.0 if _isnum(x) else f"({x}) * {var}"))
                          for x in v]
    return out


def select_clip(name: str, a: Clip, b: Clip, var: str) -> Clip:
    """同じ時刻のキーを持つ 2 本を「var ? b : a」で 1 本に（左右の向きを個体で切り替える）。"""
    if len(a.keys) != len(b.keys):
        raise ValueError("select_clip: key count differs")
    c = copy.deepcopy(a)
    c.name = name
    c.keys = []
    for (ta, pa, la), (tb, pb, _lb) in zip(a.keys, b.keys):
        if abs(ta - tb) > 1e-6:
            raise ValueError("select_clip: key times differ")
        bones = set(pa) | set(pb)
        pose = {}
        for bn in bones:
            ea, eb = pa.get(bn, {}), pb.get(bn, {})
            o = {}
            for ch in set(ea) | set(eb):
                dflt = [1.0, 1.0, 1.0] if ch == "scl" else [0.0, 0.0, 0.0]
                va, vb = ea.get(ch, dflt), eb.get(ch, dflt)
                vv = []
                for xa, xb in zip(va, vb):
                    if _isnum(xa) and _isnum(xb) and abs(float(xa) - float(xb)) < 0.05:
                        vv.append(float(xa))
                    else:
                        vv.append(f"{var} ? {fmt(xb) if _isnum(xb) else '(' + xb + ')'} : "
                                  f"{fmt(xa) if _isnum(xa) else '(' + xa + ')'}")
                o[ch] = vv
            pose[bn] = o
        c.keys.append((ta, pose, la))
    return c


# ===========================================================================
#  7. QA（書き出した JSON を評価して床との関係を数で確かめる）
# ===========================================================================
QA_VARS = {"v.nr_s": 1.0, "v.nr_awr": 1.0, "v.nr_awl": 1.0, "v.nr_hn": 14.0, "v.nr_reach": 0.0,
           "v.nr_tilt": 0.0, "v.nr_limp": 0.0, "v.nr_ph": 0.0}


def eval_pose(lib: dict, full_id: str, t: float, variables: Optional[dict] = None) -> dict:
    import nr_preview as NP
    var = dict(QA_VARS)
    var.update(variables or {})
    var["v.nr_ph"] = t
    p, _w = NP.animation_pose(lib, full_id, t, variables=var)
    return {b: {"rot": e.get("rotation", [0, 0, 0]), "pos": e.get("position", [0, 0, 0])} for b, e in p.items()}


def feet_report(lib: dict, full_id: str, skel: Skel, n: int = 32, length: float = 1.0,
                variables: Optional[dict] = None) -> dict:
    """周期を n 点で評価して、両足の一番低い点（単位）の最小・最大、全身の一番低い点の最小を返す。"""
    lows, body = [], []
    for i in range(n):
        t = length * i / n
        W = skel.world(eval_pose(lib, full_id, t, variables))
        lows.append(min(_bone_min_y(skel, W, "foot_r"), _bone_min_y(skel, W, "foot_l")))
        body.append(skel.min_y(W))
    return dict(foot_min=min(lows), foot_max=max(lows), body_min=min(body))


# ===========================================================================
#  8. 移動の型（LOCOMOTION_VOCAB の 13 種）: 歩き（徘徊）と走り（追跡）
# ===========================================================================
# 腕を前へ伸ばす個体差（v.nr_reach = 1 の個体。初期化で 45% の確率）
REACH = P(arm_r=(-58, -6, 4), forearm_r=(-14, 0, 0), hand_r=(-12, 0, 0),
          arm_l=(-42, 8, -6), forearm_l=(-26, 0, 0), hand_l=(-8, 0, 0))


def _flail(phi, amp, freq=1.0, seed=0.0):
    """不規則な振り（3 つの正弦の和。周期内で閉じる整数倍の周波数）。"""
    return amp * (0.6 * _sin(phi * freq + seed) + 0.3 * _sin(phi * freq * 2 + seed * 1.7)
                  + 0.2 * _sin(phi * freq * 3 + seed * 2.3))


def _shamble_extra(phi, ctx):
    # 引きずる足の内股・つま先の向きの不揃い、指のだらり
    return P(hand_r=(0, 0, 4 * _sin(phi + 0.2)), hand_l=(0, 0, -4 * _sin(phi + 0.6)))


def _run_extra(phi, ctx):
    # 感染して間もない走り: 頭が周期の途中でかくっと横へ振れる
    k = math.exp(-14 * _frac(phi - 0.36)) * min(1.0, _frac(phi - 0.36) * 30)
    return P(head=(4 * k, 16 * k, -8 * k), neck=(0, 6 * k, 0))


def _sprint_extra(phi, ctx):
    return P(head=(0, _flail(phi, 6, 1, 0.3), _flail(phi, 5, 1, 1.1)),
             arm_r=(0, _flail(phi, 10, 1, 0.5), _flail(phi, 8, 2, 0.2)),
             arm_l=(0, _flail(phi, 10, 1, 1.5), _flail(phi, 8, 2, 1.2)))


def _stagger_extra(phi, ctx):
    # 4 歩で 1 周期。3 歩目で前のめりに倒れかけて腕を振り回し、踏みとどまる
    k = _smooth((phi - 1.15) / 0.25) * (1 - _smooth((phi - 1.55) / 0.35)) if 1.1 < phi < 1.95 else 0.0
    wob = _flail(phi / 2, 1.0, 1, 0.7)
    return P(torso=(10 * k, 0, 9 * wob), chest=(6 * k, 0, 4 * wob),
             arm_r=(-50 * k + _flail(phi / 2, 14, 2, 0.1), 0, 30 * k + 6 * wob),
             arm_l=(-38 * k + _flail(phi / 2, 14, 2, 1.3), 0, -26 * k - 6 * wob),
             forearm_r=(-20 * k, 0, 0), forearm_l=(-30 * k, 0, 0),
             head=(-14 * k + _flail(phi / 2, 6, 3, 0.4), _flail(phi / 2, 9, 1, 0.9), 14 * wob),
             root_pos=(1.3 * wob, 0, -0.6 * k))


def _brute_extra(phi, ctx):
    # 肩を揺らす（胸のねじれを大きく）・接地で頭が沈む
    return P(chest=(0, -8 * _cos(phi - 0.3), 3 * _cos(phi - 0.3)),
             head=(3 * abs(_sin(phi * 1.0)), 0, 0))


def _stalk_extra(phi, ctx):
    # 頭をゆっくり左右に振って匂いを嗅ぐ・指が獲物を探る
    return P(head=(2 * _sin(phi * 2), 14 * _sin(phi * 0.5), 5 * _sin(phi * 0.5 + 0.25)),
             hand_r=(-10 * _sin(phi * 2), 0, 0), hand_l=(-10 * _sin(phi * 2 + 0.5), 0, 0))


def _waddle_extra(phi, ctx):
    # 腹が左右に揺れる（胴を横揺れと逆へ）
    sw = -_cos(phi - ctx["g"].duty / 2)
    return P(torso=(0, 0, -7 * sw), chest=(0, 0, 3 * sw), head=(0, 0, 5 * sw),
             torso_scl=(1.0 + 0.015 * _sin(phi * 2), 1.0, 1.0 + 0.015 * _sin(phi * 2)))


def _lurch_extra(phi, ctx):
    # 接地のたびに頭がかくっと前へ落ち、跳ね返る
    k = 0.0
    for o in (0.0, 0.5):
        x = _frac(phi - o)
        k += math.exp(-12 * x) * min(1.0, x * 30)
    return P(head=(10 * k, 0, 0), neck=(4 * k, 0, 0), jaw=(6 * k, 0, 0))


def _limp_extra(bad: str):
    def f(phi, ctx):
        # 悪い脚の側の腕は腿を押さえるように垂れ、頭はその側へ傾ぐ
        sgn = -1.0 if bad == "r" else 1.0
        return P(**{f"arm_{bad}": (-14, 0, -sgn * -6), f"forearm_{bad}": (-24, 0, 0),
                    f"hand_{bad}": (10, 0, 0)}, head=(0, 0, 6 * -sgn))
    return f


def loco_gaits() -> Dict[str, Dict[str, Gait]]:
    """{移動: {"walk": Gait, "run": Gait}}（crawl / scuttle / knuckle は別の作り方）。"""
    out: Dict[str, Dict[str, Gait]] = {}
    # --- shamble: 典型的な足を引きずる歩き / 追うと前のめりのよろけ走り
    out["shamble"] = dict(
        walk=Gait(stride=0.36, duty=0.66, lift=0.045, knee=12, toe_drag=16, heel=4, toeoff=10, toe_out=10,
                  sway=0.45, roll=6, twist=5, lean=5, chest=4,
                  upper=make_upper(dict(arms=dict(rx=0, A=9, lag=0.14, rz=6, fore=-12, foreA=7, foreLag=0.22,
                                                  hand=10, cancel=0.85),
                                        head=dict(keep=0.45, nod=3, loll=7, lollLag=0.2, neck=4),
                                        jaw=(7, 3, 1), reach=REACH, extra=_shamble_extra))),
        run=Gait(stride=0.62, duty=0.47, lift=0.10, knee=16, toe_drag=6, flight=0.25, sway=0.5, roll=6, twist=9,
                 lean=14, chest=8, heel=6, toeoff=16,
                 upper=make_upper(dict(arms=dict(rx=-62, A=20, lag=0.05, rz=10, rzA=6, fore=-22, foreA=16,
                                                 hand=-12, handA=8, cancel=0.3),
                                       head=dict(keep=0.85, nod=5, loll=5, neck=-4),
                                       jaw=(18, 7, 2), extra=lambda p, c: P(head=(0, _flail(p, 6, 1, 0.2), 0))))),
    )
    # --- limp: 悪い脚（v.nr_limp で左右）を引きずる
    out["limp"] = {}
    for mode, (st, du, bad_du, kn, lean_) in dict(walk=(0.34, 0.70, 0.52, 10, 8), run=(0.50, 0.56, 0.38, 14, 12)).items():
        out["limp"][mode] = {}
        for bad in ("r", "l"):
            sb = st * bad_du / du
            out["limp"][mode][bad] = Gait(
                stride=st, duty=du, lift=0.06, knee=kn, sway=0.7, roll=9, twist=6, lean=lean_, chest=4,
                toe_out=8, flight=0.15 if mode == "run" else 0.0,
                legs={bad: dict(stride=sb, duty=bad_du, lift=0.012, knee=3, toe_drag=26, heel=0, toeoff=4,
                                abduct=1.6, toe_out=22)},
                upper=make_upper(dict(arms=dict(rx=-6 if mode == "walk" else -30, A=10 if mode == "walk" else 22,
                                                lag=0.1, rz=8, fore=-14, foreA=8, hand=8, cancel=0.8),
                                      head=dict(keep=0.5, nod=5, loll=9, neck=3),
                                      jaw=(6, 4, 1), reach=REACH if mode == "walk" else None,
                                      extra=_limp_extra(bad))))
    # --- stagger: 酔ったような不規則なよろめき（4 歩で 1 周期）
    out["stagger"] = dict(
        walk=Gait(stride=0.32, duty=0.64, lift=0.06, knee=12, toe_drag=8, sway=0.9, roll=8, twist=6, lean=6,
                  chest=4, width=0.5, length=2.0, toe_out=14,
                  upper=make_upper(dict(arms=dict(rx=-8, A=8, lag=0.2, rz=16, rzA=8, fore=-18, foreA=10, hand=12,
                                                  cancel=0.8),
                                        head=dict(keep=0.4, nod=4, loll=12, lollLag=0.3, neck=5),
                                        jaw=(9, 5, 1), extra=_stagger_extra))),
        run=Gait(stride=0.54, duty=0.47, lift=0.10, knee=16, flight=0.2, sway=1.1, roll=8, twist=9, lean=14,
                 chest=8, width=0.5, length=2.0,
                 upper=make_upper(dict(arms=dict(rx=-40, A=26, lag=0.1, rz=22, rzA=10, fore=-26, foreA=18, hand=-6,
                                                 cancel=0.3),
                                       head=dict(keep=0.7, nod=5, loll=10, neck=-2),
                                       jaw=(16, 8, 2), extra=_stagger_extra))),
    )
    # --- run: 上体を起こしたぎこちない小走り（感染して間もない）
    out["run"] = dict(
        walk=Gait(stride=0.44, duty=0.62, lift=0.07, knee=8, toe_out=4, sway=0.25, roll=3, twist=6, lean=2, chest=0,
                  upper=make_upper(dict(arms=dict(rx=-18, A=8, lag=0.3, rz=6, fore=-16, foreA=6, hand=4, cancel=0.6),
                                        head=dict(keep=0.5, nod=3, loll=3), jaw=(2, 1, 1), extra=_run_extra))),
        run=Gait(stride=0.78, duty=0.42, lift=0.14, knee=18, flight=0.7, sway=0.3, roll=4, twist=10, lean=10, chest=6,
                 upper=make_upper(dict(arms=dict(rx=-28, A=34, lag=0.08, rz=10, fore=-68, foreA=16, hand=-6,
                                                 cancel=0.3),
                                       head=dict(keep=0.8, nod=4, loll=3, neck=-3), jaw=(10, 5, 2),
                                       extra=_run_extra))),
    )
    # --- sprint: 俊敏型。歩きは低い徘徊、走りは前傾で腕を振り回す全力疾走
    out["sprint"] = dict(
        walk=Gait(stride=0.40, duty=0.62, lift=0.08, knee=22, drop=0.8, sway=0.3, roll=3, twist=6, lean=10, chest=8,
                  upper=make_upper(dict(arms=dict(rx=-24, A=12, lag=0.12, rz=10, fore=-22, foreA=8, hand=-6,
                                                  cancel=0.7),
                                        head=dict(keep=0.9, nod=2, loll=3, yaw=10, yawF=0.5, neck=-4),
                                        jaw=(5, 3, 2)))),
        run=Gait(stride=1.0, duty=0.36, lift=0.20, knee=22, flight=1.0, sway=0.35, roll=4, twist=12, lean=24,
                 chest=10, heel=4, toeoff=24,
                 upper=make_upper(dict(arms=dict(rx=-40, A=55, lag=0.06, rz=26, rzA=10, fore=-38, foreA=26,
                                                 hand=-10, handA=10, cancel=0.2),
                                       head=dict(keep=0.95, nod=4, loll=4, neck=-6), jaw=(16, 8, 2),
                                       extra=_sprint_extra))),
    )
    # --- brute: 肩を揺らし地面を踏みしめる重い歩み
    out["brute"] = dict(
        walk=Gait(stride=0.36, duty=0.66, lift=0.08, knee=16, width=1.4, toe_out=14, heel=10, sway=0.6, roll=3,
                  twist=10, lean=6, chest=6, bob=0.15,
                  upper=make_upper(dict(arms=dict(rx=-6, A=16, lag=0.15, rz=16, fore=-20, foreA=10, hand=-4,
                                                  cancel=0.8),
                                        head=dict(keep=0.6, nod=3, loll=3, neck=6), jaw=(3, 2, 1),
                                        torso=dict(ct=1.0), extra=_brute_extra))),
        run=Gait(stride=0.56, duty=0.50, lift=0.12, knee=20, width=1.4, flight=0.3, sway=0.7, roll=4, twist=12,
                 lean=12, chest=10, toe_out=12,
                 upper=make_upper(dict(arms=dict(rx=-20, A=30, lag=0.1, rz=20, fore=-40, foreA=16, hand=-6,
                                                 cancel=0.4),
                                       head=dict(keep=0.7, nod=4, loll=3, neck=4), jaw=(10, 4, 2),
                                       torso=dict(ct=1.0), extra=_brute_extra))),
    )
    # --- stalk: 低く身をかがめて忍び寄る / 低く速い駆け足
    out["stalk"] = dict(
        walk=Gait(stride=0.34, duty=0.70, lift=0.10, knee=38, drop=2.2, sway=0.2, roll=2, twist=4, lean=18, chest=12,
                  heel=0, toeoff=26, toe_out=4,
                  upper=make_upper(dict(arms=dict(rx=-40, A=8, lag=0.3, rz=8, fore=-40, foreA=6, hand=-20,
                                                  cancel=0.3),
                                        head=dict(keep=0.95, nod=1, loll=2, neck=-6, tilt=True), jaw=(4, 2, 1),
                                        extra=_stalk_extra))),
        run=Gait(stride=0.95, duty=0.38, lift=0.20, knee=30, drop=1.2, flight=0.8, sway=0.25, roll=3, twist=10,
                 lean=26, chest=14, heel=2, toeoff=26,
                 upper=make_upper(dict(arms=dict(rx=-55, A=30, lag=0.06, rz=12, fore=-50, foreA=14, hand=-18,
                                                 cancel=0.15),
                                       head=dict(keep=0.95, nod=3, loll=2, neck=-8), jaw=(12, 6, 2)))),
    )
    # --- leap: 弾むような歩き / 両脚で跳ねて間合いを詰める
    out["leap"] = dict(
        walk=Gait(stride=0.38, duty=0.58, lift=0.12, knee=30, drop=1.4, bob=0.35, sway=0.25, roll=3, twist=6,
                  lean=14, chest=8, toeoff=24,
                  upper=make_upper(dict(arms=dict(rx=-30, A=10, lag=0.1, rz=10, fore=-45, foreA=8, hand=-14,
                                                  cancel=0.4),
                                        head=dict(keep=0.9, nod=4, loll=3, neck=-4), jaw=(6, 3, 2)))),
        run=Gait(stride=1.1, duty=0.34, lift=0.22, knee=34, drop=1.0, flight=2.0, offset=0.12, sway=0.1, roll=2,
                 twist=3, lean=22, chest=12, surge=0.3, heel=0, toeoff=28,
                 upper=make_upper(dict(arms=dict(rx=-30, A=48, lag=0.05, rz=14, fore=-30, foreA=20, hand=-16,
                                                 sync=1, cancel=0.2),
                                       head=dict(keep=0.95, nod=6, loll=2, neck=-6), jaw=(14, 8, 1)))),
    )
    # --- waddle: 膨れた腹を左右に揺らすよちよち歩き
    out["waddle"] = dict(
        walk=Gait(stride=0.24, duty=0.70, lift=0.05, knee=14, width=1.2, toe_out=18, sway=1.2, roll=2, twist=3,
                  lean=-3, chest=-4, heel=2, toeoff=8,
                  upper=make_upper(dict(arms=dict(rx=-10, A=6, lag=0.15, rz=26, rzA=4, fore=-16, foreA=6, hand=6,
                                                  cancel=0.6),
                                        head=dict(keep=0.3, nod=5, loll=6, neck=2), jaw=(8, 4, 1),
                                        torso=dict(cr=0.2), extra=_waddle_extra))),
        run=Gait(stride=0.34, duty=0.58, lift=0.08, knee=18, width=1.2, toe_out=16, sway=1.4, roll=3, twist=4,
                 lean=2, chest=0, flight=0.1,
                 upper=make_upper(dict(arms=dict(rx=-20, A=14, lag=0.1, rz=30, rzA=6, fore=-24, foreA=10, hand=0,
                                                 cancel=0.5),
                                       head=dict(keep=0.4, nod=6, loll=6), jaw=(14, 6, 2),
                                       torso=dict(cr=0.2), extra=_waddle_extra))),
    )
    # --- lurch: 上体を硬直させ、つんのめるように大きく踏み出す
    out["lurch"] = dict(
        walk=Gait(stride=0.52, duty=0.64, lift=0.07, knee=24, heel=12, toeoff=14, sway=0.4, roll=3, twist=1,
                  lean=4, chest=2,
                  upper=make_upper(dict(arms=dict(rx=-12, A=4, lag=0.2, rz=4, fore=-6, foreA=3, hand=8, cancel=0.9),
                                        head=dict(keep=0.5, nod=1, loll=2, neck=2), jaw=(5, 2, 1),
                                        torso=dict(ct=0.2, lurch=(12.0, 6.0)), extra=_lurch_extra))),
        run=Gait(stride=0.72, duty=0.52, lift=0.10, knee=26, heel=10, flight=0.2, sway=0.45, roll=4, twist=2,
                 lean=10, chest=4,
                 upper=make_upper(dict(arms=dict(rx=-30, A=8, lag=0.2, rz=8, fore=-12, foreA=4, hand=0, cancel=0.5),
                                       head=dict(keep=0.6, nod=2, loll=2), jaw=(10, 4, 2),
                                       torso=dict(ct=0.2, lurch=(16.0, 6.0)), extra=_lurch_extra))),
    )
    return out


# ===========================================================================
#  9. 四つ足・這いのエンジン（手と足を床に。scuttle / knuckle / crawl / drag）
# ===========================================================================
HAND_FLAT = {"r": rot(-90, 0, 90), "l": rot(-90, 0, -90)}       # 手のひらを下・指を前
HAND_FIST = {"r": rot(-18, 0, 0), "l": rot(-18, 0, 0)}          # 拳を下（指の背で地面を突く）


@dataclass
class Quad:
    """四つ足／這いの歩容。limbs = {"hand_r": dict(offset, x, z, ...), "foot_l": ...}（x, z は床の上の接地の中心、
    単位・体の休みの座標）。body(phi) -> ポーズ（root / waist / torso / chest / neck / head / jaw と、
    動かす脚・腕の追加）。"""
    body: Callable
    limbs: Dict[str, dict]
    stride: float = 4.0           # 単位
    duty: float = 0.6
    lift: float = 1.2             # 単位
    length: float = 1.0
    keys: int = 16
    hand: Dict[str, np.ndarray] = field(default_factory=lambda: dict(HAND_FLAT))
    arm_ry: Dict[str, float] = field(default_factory=lambda: {"r": 0.0, "l": 0.0})
    knee_out: float = 0.0         # 脚の逆運動学の曲げの向き（正 = 膝が前）
    ground_hands: bool = True


def quad_limb(Q: Quad, name: str, phi: float) -> dict:
    lm = Q.limbs[name]
    psi = _frac(phi + lm.get("offset", 0.0))
    S = lm.get("stride", Q.stride)
    d = lm.get("duty", Q.duty)
    lift = lm.get("lift", Q.lift)
    if psi < d:
        u = psi / d
        z = lm["z"] - S / 2 + S * u
        y = 0.0
        st = True
    else:
        u = (psi - d) / (1 - d)
        e = 0.5 - 0.5 * math.cos(math.pi * u)
        z = lm["z"] + S / 2 - S * e
        y = lift * math.sin(math.pi * u)
        st = False
    return dict(x=lm["x"], y=y, z=z, stance=st, u=u)


def quad_pose(Q: Quad, skel: Skel, phi: float) -> dict:
    pose = Q.body(phi)
    num_pose = _numeric(pose, skel)
    feet = {}
    for s, _sgn in SIDES:
        n = f"foot_{s}"
        if n in Q.limbs:
            lm = quad_limb(Q, n, phi)
            yb = skel.piv[n][1]
            feet[s] = (np.array([lm["x"], yb + lm["y"], lm["z"]]), Q.limbs[n].get("pitch", 0.0),
                       Q.limbs[n].get("yaw", 0.0), Q.limbs[n].get("roll", 0.0), Q.limbs[n].get("ry", 0.0))
    solved = solve_legs(skel, num_pose, feet, bend_hint=1.0) if feet else num_pose
    hands = {}
    for s, _sgn in SIDES:
        n = f"hand_{s}"
        if n in Q.limbs:
            lm = quad_limb(Q, n, phi)
            hands[s] = (np.array([lm["x"], Q.limbs[n].get("y0", 0.6) + lm["y"], lm["z"]]), Q.hand[s])
    if hands:
        solved = solve_arms(skel, solved, hands, ry=Q.arm_ry)
        if Q.ground_hands:                       # 手のキューブが床に埋まったら手首を上げてやり直す
            W = skel.world(solved)
            for s in list(hands):
                lo = _bone_min_y(skel, W, f"hand_{s}")
                if lo < -0.02:
                    p0, R = hands[s]
                    solved = solve_arms(skel, solved, {s: (p0 + np.array([0, -lo, 0]), R)}, ry=Q.arm_ry)
    out = copy.deepcopy(pose)
    for b in ("leg_r", "shin_r", "foot_r", "leg_l", "shin_l", "foot_l"):
        if f"foot_{b[-1]}" in Q.limbs:
            out[b] = {"rot": solved[b]["rot"]}
    for b in ("arm_r", "forearm_r", "hand_r", "arm_l", "forearm_l", "hand_l"):
        if f"hand_{b[-1]}" in Q.limbs and b in solved:
            prev = pose.get(b, {}).get("rot")
            out[b] = {"rot": solved[b]["rot"]}
            if prev is not None and b.startswith("hand"):
                out[b] = {"rot": [a + (c if _isnum(c) else 0.0) for a, c in zip(solved[b]["rot"], prev)]}
    return out


def quad_clip(name: str, Q: Quad, skel: Skel, note: str = "", anim_time: str = "v.nr_ph") -> Clip:
    c = Clip(name, Q.length, loop=True, anim_time_update=anim_time, note=note)
    n = int(round(Q.keys * Q.length))
    poses = [quad_pose(Q, skel, Q.length * i / n) for i in range(n)]
    for i, p in enumerate(poses + [poses[0]]):
        c.key(Q.length * i / n, p)
    return c


def shoulder_ground(skel: Skel, pose: dict, s: str) -> np.ndarray:
    W = skel.world(_numeric(pose, skel))
    return skel.point(W, f"arm_{s}", skel.piv[f"arm_{s}"])


def hip_ground(skel: Skel, pose: dict, s: str) -> np.ndarray:
    W = skel.world(_numeric(pose, skel))
    return skel.point(W, f"leg_{s}", skel.piv[f"leg_{s}"])


def style_build(loco: str) -> dict:
    """その移動の型を使う種類の平均の骨格（腕の長さ・猫背が型ごとに大きく違うので）。"""
    zs = [z for z in SPEC.ZOMBIES if z["locomotion"] == loco]
    if not zs:
        return dict(REF_BUILD)
    b = dict(REF_BUILD)
    for k in ("heads", "bulk", "limb", "hunch", "arm_len"):
        b[k] = round(sum(float(z[k]) for z in zs) / len(zs), 3)
    b["height_cm"] = 176
    return b


# ---------------------------------------------------------------------------
#  scuttle: 四つ足で頭を低くした蜘蛛のような這い歩き
# ---------------------------------------------------------------------------
def scuttle_quad(skel: Skel, mode: str) -> Quad:
    run = mode == "run"
    drop = skel.piv["leg_r"][1] * (0.60 if not run else 0.56)
    lean_t, lean_c = (30.0, 18.0)

    def body(phi):
        bob = (0.35 if run else 0.2) * _cos(phi * 2)
        rl = (6 if run else 4) * _sin(phi)
        return P(root_pos=(0.25 * _sin(phi), -drop + bob, 0.0),
                 waist=(8, 4 * _sin(phi), 0),
                 torso=(lean_t, -5 * _sin(phi), rl), chest=(lean_c, -6 * _sin(phi), rl * 0.5),
                 neck=(f"{fmt(-30)} - 0.3 * v.nr_hn", 6 * _sin(phi + 0.1), 0),
                 head=(f"{fmt(-28 + 4 * _cos(phi * 2))} - 0.3 * v.nr_hn", _flail(phi, 8, 1, 0.4), _flail(phi, 6, 1, 1.2)),
                 jaw=(10 + 6 * _sin(phi * 2), 0, 0))
    base = body(0.0)
    sh = {s: shoulder_ground(skel, base, s) for s, _ in SIDES}
    hp = {s: hip_ground(skel, base, s) for s, _ in SIDES}
    S = (7.0 if run else 4.4)
    limbs = {}
    # 横に大きく開いた手足（蜘蛛）。walk = 横の順（LF, LH, RF, RH）、run = 斜めの組（トロット）
    offs = (dict(foot_l=0.0, hand_l=0.25, foot_r=0.5, hand_r=0.75) if not run
            else dict(hand_r=0.0, foot_l=0.0, hand_l=0.5, foot_r=0.5))
    for s, sgn in SIDES:
        limbs[f"hand_{s}"] = dict(offset=offs[f"hand_{s}"], x=sh[s][0] + sgn * 2.6, z=sh[s][2] - 3.0, y0=0.5)
        limbs[f"foot_{s}"] = dict(offset=offs[f"foot_{s}"], x=hp[s][0] + sgn * 5.6, z=hp[s][2] - 0.6,
                                  yaw=-sgn * 40, pitch=0.0, roll=sgn * 10, ry=-sgn * 62)
    return Quad(body=body, limbs=limbs, stride=S, duty=0.62 if not run else 0.5,
                lift=1.4 if not run else 2.2, arm_ry={"r": 30.0, "l": -30.0})


# ---------------------------------------------------------------------------
#  knuckle: 長い腕の拳を地面について進むゴリラのような歩き
# ---------------------------------------------------------------------------
def knuckle_quad(skel: Skel, mode: str) -> Quad:
    run = mode == "run"
    drop = skel.piv["leg_r"][1] * (0.10 if not run else 0.16)

    def body(phi):
        if run:
            bob = 0.6 * _cos(phi)
            pitch = 6 * _sin(phi)
        else:
            bob = 0.3 * _cos(phi * 2)
            pitch = 2 * _sin(phi * 2)
        return P(root_pos=(0.5 * _sin(phi) * (0 if run else 1), -drop + bob, 0.0),
                 waist=(10 + pitch, 6 * _sin(phi), 0),
                 torso=(16 + pitch * 0.5, -6 * _sin(phi), 4 * _sin(phi)),
                 chest=(10, -8 * _sin(phi), 2 * _sin(phi)),
                 neck=("-20 - 0.25 * v.nr_hn", 0, 0),
                 head=(f"{fmt(-20 - pitch)} - 0.3 * v.nr_hn", 6 * _sin(phi * 0.5), 3 * _sin(phi)),
                 jaw=(6 + 3 * _sin(phi * 2), 0, 0))
    base = body(0.0)
    sh = {s: shoulder_ground(skel, base, s) for s, _ in SIDES}
    hp = {s: hip_ground(skel, base, s) for s, _ in SIDES}
    S = 8.0 if run else 5.0
    offs = (dict(hand_l=0.0, foot_r=0.2, hand_r=0.5, foot_l=0.7) if not run
            else dict(hand_r=0.0, hand_l=0.08, foot_r=0.55, foot_l=0.62))
    limbs = {}
    for s, sgn in SIDES:
        limbs[f"hand_{s}"] = dict(offset=offs[f"hand_{s}"], x=sh[s][0] + sgn * 1.4, z=sh[s][2] - 2.5,
                                  y0=skel.L.hand_l * 0.62)
        limbs[f"foot_{s}"] = dict(offset=offs[f"foot_{s}"], x=hp[s][0] + sgn * 0.8, z=hp[s][2] - 0.5,
                                  yaw=-sgn * 12)
    return Quad(body=body, limbs=limbs, stride=S, duty=0.64 if not run else 0.42, lift=1.6 if not run else 2.6,
                hand=dict(HAND_FIST), arm_ry={"r": 12.0, "l": -12.0})


# ---------------------------------------------------------------------------
#  うつ伏せ（這う・上半身だけ）: 股関節の高さを原点に前へ倒し、頭が +f（ジオメトリの -Z）
# ---------------------------------------------------------------------------
def prone_base(skel: Skel, half: bool = False) -> dict:
    """うつ伏せの全身（root を前へ 90° 倒し、股関節を原点の真上に、体の前面を床に）。"""
    hip = skel.piv["leg_r"][1]
    lift = skel.L.chest_d / 2 + 0.15
    return P(root=(90.0, 0, 0), root_pos=(0.0, lift, hip),
             torso=("-0.45 * v.nr_hn", 0, 0), chest=("-0.55 * v.nr_hn", 0, 0))


def crawl_quad(skel: Skel, mode: str, half: bool = False) -> Quad:
    """這う（脚が無い・折れた・nr:state crawl）/ 上半身だけ（half）。腕を交互に前へ伸ばして体を引き寄せる。"""
    run = mode == "run"
    pb = prone_base(skel, half)

    def body(phi):
        heave = 0.8 * max(0.0, _sin(phi * 2 - 0.1)) * (1.4 if run else 1.0)
        rl = (12 if run else 8) * _sin(phi)
        p = padd(pb, P(root_pos=(0.0, heave * 0.5, 0.0),
                       torso=(-4 * heave, 0, 0), chest=(-6 * heave, 3 * _sin(phi), rl),
                       waist=(0, 4 * _sin(phi), rl * 0.4),
                       neck=(-38 - 4 * heave, 4 * _sin(phi), 0),
                       head=(-30 + 3 * _sin(phi * 2), 6 * _sin(phi + 0.2), rl * -0.5),
                       jaw=(14 + 10 * max(0.0, _sin(phi * 2 + 0.3)), 0, 0)))
        # 脚は後ろへだらりと伸び、引きずられて揺れる（切れていれば見えない）
        if not half:
            for s, sgn in SIDES:
                p = padd(p, {f"leg_{s}": {"rot": [8 + 4 * _sin(phi + (0.5 if s == 'l' else 0)), 0, -sgn * 6]},
                             f"shin_{s}": {"rot": [10 + 8 * max(0.0, _sin(phi * 2)), 0, 0]},
                             f"foot_{s}": {"rot": [40, 0, -sgn * 20]}})
        return p
    base = body(0.0)
    sh = {s: shoulder_ground(skel, base, s) for s, _ in SIDES}
    S = 6.0 if run else 4.6
    limbs = {}
    for s, sgn in SIDES:
        limbs[f"hand_{s}"] = dict(offset=0.0 if s == "r" else 0.5, x=sh[s][0] + sgn * 1.2, z=sh[s][2] - 4.0, y0=0.45)
    return Quad(body=body, limbs=limbs, stride=S, duty=0.55, lift=2.0 if not run else 2.8,
                arm_ry={"r": 10.0, "l": -10.0})


# ---------------------------------------------------------------------------
#  QA の素体（塗った素体のリグ）と描画
# ---------------------------------------------------------------------------
_QA_ASSETS: Dict[str, tuple] = {}


def qa_assets(name: str, build: dict):
    """素体のリグを nr_paint で塗って (Geometry, texture, Skel) に（確認画像用）。"""
    key = name + repr(sorted(build.items()))
    if key in _QA_ASSETS:
        return _QA_ASSETS[key]
    import nr_preview as NP
    m = RIG.new_model("qa_" + name)
    RIG.ZombieRig(m, dict(build), detail=2, seed=zlib.crc32(name.encode()))
    m.pack(size=(512, 512))
    img, _how = RIG._paint(m, build, zlib.crc32(name.encode()) & 0xFFFF, blood=0.45)
    geo = NP.load_geometry(m)
    tex = NP.load_texture(img, geo)
    out = (geo, tex, Skel(m))
    _QA_ASSETS[key] = out
    return out


def qa_frames(lib: dict, full_id: str, times: Sequence[float], name: str, build: dict,
              views=("right",), size=240, variables=None, properties=None, label=None) -> list:
    """クリップの何コマかを [(ラベル, 画像)] に（縮尺は全コマ共通）。"""
    import nr_preview as NP
    geo, tex, skel = qa_assets(name, build)
    var = dict(QA_VARS)
    var["v.nr_hn"] = float(build.get("hunch", 14))
    var.update(variables or {})
    hidden = None
    if properties:
        rules = RIG.visibility_rules(skel.model)
        hidden = NP.part_visibility_hidden(rules, geo, properties=properties, defaults=NP.NR_ZOMBIE_DEFAULTS)
    items = []
    for view in views:
        fr = NP.render_clip(geo, tex, lib, full_id, list(times), view=view, size=size, variables=var,
                            properties=properties, hidden=hidden, hide_mode="exact", floor=True,
                            per_frame=lambda t: {"v.nr_ph": t})
        for (lab, img), t in zip(fr, times):
            items.append(((label or full_id.split(".")[-1]) + f" {view[:5]} t={t:.2f}", img))
    return items
