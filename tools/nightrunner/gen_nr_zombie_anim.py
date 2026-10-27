# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — ゾンビ 50 体のアニメーションとアニメコントローラ（DESIGN.md §3 / §5 / §12 / §13）。

出力（packs/nightrunner_RP/）:
  animations/nr_zombie_move.animation.json       移動 walk_/run_/idle_<型>（LOCOMOTION_VOCAB の 13 型。歩き・走りは移動距離の
                                                  位相 v.nr_ph で回るので足が滑らない）・体の状態（st_gimp 折れた脚を引きずる /
                                                  st_crawl1 片脚で蹴る這い / st_drag 上半身だけで腸を引きずる / st_climb /
                                                  st_stagger / st_down 倒れる / st_rise 起き上がる）・死体 dead_0..7（death.js の
                                                  POSE）と dead_half / dead_down（hold_on_last_frame）・重ね ov_*（生きている揺れと
                                                  顎のカチカチ・標的を見る・被弾・燃えてもがく・感電・折れた腕・腸・盾の構え）・fx_trail
  animations/nr_zombie_attack.animation.json     攻撃 atk_<攻撃>（ATTACK_VOCAB の 24 種。windup / active / recover の tick どおり）
  animations/nr_zombie_ability.animation.json    能力の段階 ab_<能力>_<段階>（31）と ab_wall_climb（anim=True）
  animations/nr_zombie_oneshot.animation.json    nr_registry.ZOMBIE_ONESHOTS（加算・最初と最後のキーが 0）
  animations/nr_zombie_gib.animation.json        nr:gib の空中の回転（nr:spin）・寝姿（nr:rest × nr:side）・血の尾
  animation_controllers/nr_zombie.animation_controllers.json      ゾンビ（全 50 体で共通の 12 本）
  animation_controllers/nr_zombie_gib.animation_controllers.json  nr:gib（2 本）

────────────────────────────────────────────────────────────────────────────
■ 約束（gen_nr_entities・手書きスクリプトとの契約）
* すべてのアニメは**加算**（バインドポーズ = nr_rig.rest_pose の猫背・腕の外転の上に足す）。
  override_previous_animation は使わない。ボーン名は §3 の骨格（+ throat_sac・gib の p_*）だけ。
* ゾンビの常時の見た目はプロパティ駆動のコントローラ（rendering.md A2〜A7。条件は pre_animation の v.nr_* だけを読む）:
    move    init → stand（idle/walk/run を v.nr_mv・v.nr_run で混ぜる）/ gimp / crawl / crawl1 / drag / climb /
            stagger / down → rise / owned（体ごとの能力の段階の間は空）/ dead_<nr:pose>（這い・上半身だけ・倒れから
            死ぬと dead_5 / dead_half / dead_down）。死体のまま読み込まれたら held_<n>（倒れる動きを飛ばす）
    alive   生きている揺れ・標的を見る・被弾ののけぞり（q.hurt_time）。死体・体ごとの能力の間は止まる
    fx      燃えてもがく（q.is_on_fire）・感電の震え（nr:shock。loc_chest に放電）
    arm_r / arm_l / leg_r / leg_l / head / torso
            断面のロケータから bleed_stump（持続）。切れた直後の 1.6 秒は blood_fountain も（読み込み直後 v.nr_age <= 1.5・
            死体・炭化 nr:burn 3 は噴かない）。折れた腕はぶら下がる（腕の動きは v.nr_aw* = 0.3 倍）
    guts    裂けた腹から垂れた腸が揺れて滴る / trail 下半身に断面のある体が這うと血の跡
    ability nr:ability 1..7 → ab_1..ab_7（種類ごとに ability_states(z) の段階のアニメへ写す。無い値は none）。
            0 の間は盾持ちの構え（ov_shield_guard）
* 攻撃 atk_* と一発もの（ZOMBIE_ONESHOTS）は**スクリプトの playAnimation**（v.attack_time は使わない）。
    攻撃:    zombieAnim(z, "atk_<攻撃>", {controller: "nr.z.atk", blendOutTime: 0.1})   — windup の始まりに呼ぶ
    一発もの: zombieAnim(z, "<名前>")（既定 controller "nr.z.os"）。knockdown / getup は nr:state down の倒れ・起き上がり
             （コントローラの st_down / st_rise）と同時に流れる「手応え」
  どちらも加算で最初と最後のキーが 0（P3）。長さ・当たりの時刻は ATTACK_META / ONESHOT_META。
  能力の段階 ab_*_* は nr:ability を入れれば自動で出る（スクリプトは playAnimation しない）。
* 移動の位相: pre_animation が q.modified_distance_moved の増分を「今の状態の 1 周期の距離」で割って v.nr_ph（0..4）に
  積算し、歩き・走り・這いのアニメは anim_time_update = math.mod(v.nr_ph, 長さ)。周期の距離は型の歩幅 × 種類の脚の長さ。
* 体格の違い: 位置のチャンネルは v.nr_s（身長 / 176cm）倍。寝た姿勢の床合わせは種類ごとの v.nr_gl_*（このファイルが
  素体のリグで順運動学を解き、v.nr_s で割った値を initialize に書く）。猫背の打ち消しは v.nr_hn（hunch）。
  死体・倒れの置き方は gore/hitloc.js の箱に合わせる（pose 1・5 = prone: 股関節が原点で頭が前、ほか = lie: 足元が原点で頭が後ろ）。

■ gen_nr_entities へ（このモジュールを import して使う。クリップを作らずに呼べる）
    client_animations(z)       -> {短い名前: アニメ／コントローラの ID}   client entity の description.animations
    client_animate(z)          -> scripts.animate のリスト（コントローラ 12 本）
    client_initialize(z)       -> scripts.initialize（Molang の行のリスト）
    client_pre_animation(z)    -> scripts.pre_animation（Molang の行のリスト）
    client_particle_effects(z) -> {短い名前: パーティクル ID}            description.particle_effects
    client_sound_effects(z)    -> {}（今は使わない）
    gib_client()               -> {"animations", "animate", "initialize", "pre_animation", "particle_effects"}（nr:gib）
    ATTACK_META / ONESHOT_META -> {短い名前: {"length", "controller", "blend", ...}}（スクリプト向けの推奨。build_all 後）
    AB_FULL                    -> 体ごとの能力の段階（その間 move は owned）

■ 確認
    python3 tools/nightrunner/gen_nr_zombie_anim.py            # 生成 + 検査（全 50 体の名前・コントローラの短い名前・
                                                               #   P3・ロケータ・変数・Molang の構文）
    python3 tools/nightrunner/gen_nr_zombie_anim.py --floor    # + 床との関係の数字
    python3 tools/nightrunner/gen_nr_zombie_anim.py --qa       # + build_preview/nightrunner/zombie_anim/zombie_anim_qa.png
    （NR_PREVIEW=1 でも描く）。nr_preview のアニメ評価器で、書き出した JSON そのものを素体のリグに当てて描く。
"""
from __future__ import annotations

import argparse
import copy
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


def _tkey(t: float) -> str:
    """キーフレームの時刻の文字列（バニラと同じく小数点を必ず付ける: "0.0"、"0.0625"）。"""
    s = fmt(t, 4)
    return s if "." in s else s + ".0"


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
                ts = _tkey(t)
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
    if bones or not clip.particles:          # 演出だけのアニメは bones を書かない（バニラの breeze と同じ）
        out["bones"] = {b: bones[b] for b in sorted(bones)}
    if clip.particles:
        pe = {}
        for t in sorted(clip.particles):
            effs = clip.particles[t]
            pe[_tkey(t)] = effs if len(effs) > 1 else effs[0]
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
#  4b. 床合わせの定数（v.nr_gl*）
# ===========================================================================
#  寝た姿勢（死体・倒れ・這い）は、体のいちばん低い点が床（y=0）に来るよう root を持ち上げる。
#  持ち上げる量は体格で大きく違う（bulk 0.75〜2.4）ので、種類ごとに素体のリグで順運動学を解いて
#  「身長の倍率で割った値」を initialize の v.nr_gl* に書く（アニメ側は位置に v.nr_s を掛けるので
#  (v.nr_gl*) * v.nr_s = その種類の本当の持ち上げ量）。
GROUND_FITS: Dict[str, Tuple[Callable, tuple]] = {}     # 変数名 -> (骨格 -> ポーズ, 数えないボーン)


def ground_fit(var: str, skip: tuple = ()):
    """寝た姿勢の床合わせを登録する飾り。関数は skel -> ポーズ（root の位置 y = 0 のもの）。"""
    def deco(fn):
        GROUND_FITS[var] = (fn, tuple(skip))
        return fn
    return deco


def skel_scale(skel: Skel) -> float:
    return float(skel.L.t) / REF_T


def ground_lift(skel: Skel, pose: dict, skip=()) -> float:
    """pose（root の y = 0）で体のいちばん低い点を床へ合わせる持ち上げ量（その骨格の単位）。"""
    W = skel.world(_numeric(pose, skel))
    return -skel.min_y(W, skip)


def ensure_vars(skel: Skel) -> dict:
    """skel.vars に v.nr_gl*（身長の倍率で割った値）を入れる（クリップの逆運動学・QA が使う）。"""
    if getattr(skel, "vars", None) is not None and skel.vars.get("_done"):
        return skel.vars
    skel.vars = {"v.nr_s": 1.0}
    s = skel_scale(skel)
    for var, (fn, skip) in GROUND_FITS.items():
        skel.vars[var] = round(ground_lift(skel, fn(skel), skip) / s, 3)
    skel.vars["_done"] = 1.0
    return skel.vars


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
        var.update(getattr(skel, "vars", None) or {})      # その骨格の床合わせの定数（v.nr_gl*）
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
    upper.U = U                       # idle が同じ構えを作り直すため
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
#  （gore/hitloc.js の prone の箱と同じ置き方。床からの高さは種類ごとの v.nr_glp / v.nr_glh）
# ---------------------------------------------------------------------------
ARM_BONES = ARM_R + ARM_L
LEG_BONES = LEG_R + LEG_L


def prone_base(skel: Skel, half: bool = False, lift=None) -> dict:
    """うつ伏せの全身（root を前へ 90° 倒し、股関節を原点の真上に、体の前面を床に）。
    lift = None なら床合わせの変数（v.nr_glp / 上半身だけは v.nr_glh）。"""
    hip = float(skel.piv["leg_r"][1]) / skel_scale(skel)
    y = ("v.nr_glh" if half else "v.nr_glp") if lift is None else lift
    return P(root=(90.0, 0, 0), root_pos=(0.0, y, hip),
             torso=("-0.45 * v.nr_hn", 0, 0), chest=("-0.55 * v.nr_hn", 0, 0),
             neck=(-38, 0, 0), head=(-30, 0, 0))


@ground_fit("v.nr_glp", skip=ARM_BONES + LEG_BONES)
def _fit_prone(skel: Skel) -> dict:
    return prone_base(skel, False, 0.0)


@ground_fit("v.nr_glh", skip=ARM_BONES + LEG_BONES + ("pelvis",))
def _fit_half(skel: Skel) -> dict:
    return prone_base(skel, True, 0.0)


PRONE_FOOT = 62.0        # うつ伏せの足の甲を床につける（つま先を後ろへ伸ばす）
PRONE_SHIN = 4.0


def _settle_legs(skel: Skel, pose: dict) -> float:
    """うつ伏せで脚（太腿・脛・足の甲）が床に乗る股の rx（加算）。"""
    best = (1e9, 0.0)
    for rx in np.linspace(-40, 30, 141):
        p = padd(pose, {f"leg_{s}": {"rot": [float(rx), 0, 0]} for s in "rl"},
                 {f"shin_{s}": {"rot": [PRONE_SHIN, 0, 0]} for s in "rl"},
                 {f"foot_{s}": {"rot": [PRONE_FOOT, 0, 0]} for s in "rl"})
        W = skel.world(_numeric(p, skel))
        lo = min(_bone_min_y(skel, W, b) for b in LEG_BONES)
        if lo >= 0.35 and lo < best[0]:                  # 揺れの分だけ少し浮かせる
            best = (lo, float(rx))
    return best[1]


CRAWL_LEGS = {"trail": "両脚を引きずる", "half": "下半身なし（腸を引きずる）",
              "one_r": "右脚だけで床を蹴る", "one_l": "左脚だけで床を蹴る"}


def crawl_quad(skel: Skel, mode: str, legs: str = "trail") -> Quad:
    """這う（脚が無い・折れた・nr:state crawl）。腕を交互に前へ伸ばして体を引き寄せる。
    legs = "trail"（脚を引きずる）/ "half"（上半身だけ・腸を引きずる）/ "one_r" "one_l"（片脚で蹴る）。
    肘は外へ張る（腕の ry ±90。肘が床へ潜らない）。"""
    run = mode == "run"
    half = legs == "half"
    pb = prone_base(skel, half)
    sk_vars = ensure_vars(skel)
    base_y = sk_vars["v.nr_glh" if half else "v.nr_glp"]
    pb_num = prone_base(skel, half, base_y)
    leg_rx = _settle_legs(skel, pb_num) if not half else 0.0
    good = legs[-1] if legs.startswith("one_") else ""

    def body(phi):
        heave = 0.8 * max(0.0, _sin(phi * 2 - 0.1)) * (1.4 if run else 1.0) * (0.7 if half else 1.0)
        rl = (12 if run else 8) * _sin(phi)
        p = padd(pb, P(root_pos=(0.0, heave * 0.5, 0.0),
                       torso=(-4 * heave, 0, 0), chest=(-6 * heave, 3 * _sin(phi), rl),
                       waist=(0, 4 * _sin(phi), rl * 0.4),
                       neck=(-4 * heave, 4 * _sin(phi), 0),
                       head=(3 * _sin(phi * 2), 6 * _sin(phi + 0.2), rl * -0.5),
                       jaw=(14 + 10 * max(0.0, _sin(phi * 2 + 0.3)), 0, 0)))
        if half:                                  # 腸が後ろへ伸びて床を擦り、のたうつ
            p = padd(p, P(guts=(-20 + 8 * _sin(phi * 2), 10 * _sin(phi), 14 * _sin(phi + 0.3))))
            return p
        for s, sgn in SIDES:
            if s == good:                         # 蹴る脚: 膝を横へ引き上げてから伸ばして押す
                k = 0.5 - 0.5 * _cos(phi + (0.0 if s == "r" else 0.5))
                # 太腿を ry で 90° ひねると膝の曲げが床と平行になる（足が宙に上がらない蛙足）
                p = padd(p, {f"leg_{s}": {"rot": [leg_rx - 10 * k, sgn * 90, -sgn * (10 + 32 * k)]},
                             f"shin_{s}": {"rot": [10 + 56 * k, 0, 0]},
                             f"foot_{s}": {"rot": [30 - 10 * k, 0, 0]}})
                continue
            # 引きずられる脚: 床の上でだらりと揺れる（切れていれば見えない）
            o = 0.5 if s == "l" else 0.0
            p = padd(p, {f"leg_{s}": {"rot": [leg_rx + 2 * _sin(phi + o), 0, -sgn * (5 + 2 * _sin(phi + o))]},
                         f"shin_{s}": {"rot": [PRONE_SHIN + 4 * max(0.0, _sin(phi * 2 + o)), 0, 0]},
                         f"foot_{s}": {"rot": [PRONE_FOOT, 0, -sgn * 12]}})
        return p
    base = body(0.0)
    sh = {s: shoulder_ground(skel, base, s) for s, _ in SIDES}
    S = (6.0 if run else 4.6) * (0.85 if half else 1.0)
    limbs = {}
    for s, sgn in SIDES:
        limbs[f"hand_{s}"] = dict(offset=0.0 if s == "r" else 0.5, x=sh[s][0] + sgn * 1.6, z=sh[s][2] - 4.0,
                                  y0=0.45)
    return Quad(body=body, limbs=limbs, stride=S, duty=0.55, lift=2.0 if not run else 2.8,
                arm_ry={"r": 90.0, "l": -90.0})


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


# ===========================================================================
#  10. 型ごとの骨格（移動の型の平均）
# ===========================================================================
_STYLE_SKEL: Dict[str, Skel] = {}


def style_skel(loco: str) -> Skel:
    """移動の型の平均の骨格（身長 176cm にそろえる = v.nr_s 1 の「正規化した単位」）。"""
    if loco not in _STYLE_SKEL:
        sk = ref_skel("style_" + loco, style_build(loco))
        ensure_vars(sk)
        _STYLE_SKEL[loco] = sk
    return _STYLE_SKEL[loco]


def design_skel() -> Skel:
    """状態・攻撃・能力・一発ものを作る基準の骨格（REF_BUILD）。"""
    if "_ref" not in _STYLE_SKEL:
        sk = ref_skel("ref", REF_BUILD)
        ensure_vars(sk)
        _STYLE_SKEL["_ref"] = sk
    return _STYLE_SKEL["_ref"]


def phase_time(length: float) -> str:
    """移動の位相 v.nr_ph（0..4 で折り返す）を、長さ length のクリップの時刻に。"""
    return f"math.mod(v.nr_ph, {fmt(length)})"


# ===========================================================================
#  11. 移動のクリップ（walk_/run_/idle_<型>）と周期の距離
# ===========================================================================
LOCO_CYCLES: Dict[str, dict] = {}       # 型 -> {"walk": ブロック/位相, "run": ..., "LL": 脚の長さ（単位）}
IDLE_LEN = 3.2                          # 立ち止まった時の重心移動の周期（秒）


def _idle_upper(U: dict) -> Callable:
    """歩きの上半身の構え（U）から、振りを小さくした立ち姿の上半身を作る。"""
    arms = dict(U.get("arms", {}))
    arms.update(A=1.6, foreA=1.2, handA=0.0, rzA=0.0, lag=0.15)
    head = dict(U.get("head", {}))
    head.update(nod=1.2, loll=min(4.0, float(head.get("loll", 4.0))), lollLag=0.3)
    torso = dict(U.get("torso", {}))
    torso["lurch"] = (0.0, 4.0)
    jaw = U.get("jaw", (4.0, 2.0, 2.0))
    ex = U.get("extra")

    def breath(phi, ctx):
        p = P(chest=(1.6 * _sin(phi * 3), 0, 0), torso=(0.8 * _sin(phi * 3 - 0.1), 0, 0),
              neck=(-0.8 * _sin(phi * 3), 0, 0))
        if ex is not None:                       # 型の癖（頭の振り・腹の揺れ）は弱めて残す
            p = padd(p, pscale(ex(phi, ctx), 0.35, chans=("rot",)))
        return p
    U2 = dict(U, arms=arms, head=head, torso=torso, jaw=(jaw[0] * 0.8, jaw[1] * 0.6, 3), extra=breath)
    return make_upper(U2)


def idle_gait_clip(loco: str, g: Gait, skel: Skel, name: Optional[str] = None, extra: Optional[dict] = None) -> Clip:
    """二足の型の立ち姿（両足を床に固定し、重心だけゆっくり左右へ移す）。extra = 足す固定のポーズ。"""
    gi = Gait(**{**g.__dict__})
    gi.stride, gi.lift, gi.flight, gi.bob, gi.surge = 0.0, 0.0, 0.0, 0.0, 0.0
    gi.toe_drag, gi.heel, gi.toeoff = 0.0, 0.0, 0.0
    gi.sway, gi.roll, gi.twist = g.sway * 0.6, g.roll * 0.5, g.twist * 0.3
    gi.length, gi.keys, gi.offset, gi.legs, gi.drag_leg = 1.0, 12, 0.5, {}, ""
    gi.upper = _idle_upper(g.upper.U) if g.upper is not None and hasattr(g.upper, "U") else None
    if extra:
        up0 = gi.upper
        gi.upper = lambda phi, ctx, _u=up0: padd(_u(phi, ctx) if _u else {}, extra)
    c = Clip(name or f"idle_{loco}", IDLE_LEN, loop=True, note=f"{loco} の立ち姿")
    n = gi.keys
    poses = [gait_pose(gi, skel, i / n) for i in range(n)]
    for i, p in enumerate(poses + [poses[0]]):
        c.key(IDLE_LEN * i / n, p)
    return c


def idle_quad_clip(loco: str, Q: Quad, skel: Skel) -> Clip:
    """四つ足・這いの型の止まった姿（手足を床に固定し、体だけ息をする）。"""
    Qi = Quad(**{**Q.__dict__})
    Qi.stride, Qi.lift, Qi.keys = 0.0, 0.0, 12
    c = Clip(f"idle_{loco}", IDLE_LEN, loop=True, note=f"{loco} の止まった姿")
    n = Qi.keys
    poses = [quad_pose(Qi, skel, i / n) for i in range(n)]
    for i, p in enumerate(poses + [poses[0]]):
        c.key(IDLE_LEN * i / n, padd(p, P(chest=(1.5 * _sin(i / n * 3), 0, 0))))
    return c


def _phase_clip(c: Clip) -> Clip:
    c.anim_time_update = phase_time(c.length)
    return c


QUAD_BUILDERS = {"scuttle": scuttle_quad, "knuckle": knuckle_quad,
                 "crawl": lambda sk, mode: crawl_quad(sk, mode)}


def build_locomotion() -> List[Clip]:
    """LOCOMOTION_VOCAB の全型の walk_ / run_ / idle_ と LOCO_CYCLES。"""
    ensure_cycles()
    gaits = loco_gaits()
    out: List[Clip] = []
    for loco in SPEC.LOCOMOTION_VOCAB:
        sk = style_skel(loco)
        if loco in QUAD_BUILDERS:
            qs = {m: QUAD_BUILDERS[loco](sk, m) for m in ("walk", "run")}
            for m, Q in qs.items():
                out.append(_phase_clip(quad_clip(f"{m}_{loco}", Q, sk, note=f"{loco} {m}")))
            out.append(idle_quad_clip(loco, qs["walk"], sk))
        elif loco == "limp":
            for m in ("walk", "run"):
                a = gait_clip(f"{m}_limp_r", gaits["limp"][m]["r"], sk)
                b = gait_clip(f"{m}_limp_l", gaits["limp"][m]["l"], sk)
                out.append(_phase_clip(select_clip(f"{m}_limp", a, b, "v.nr_limp")))
            out.append(idle_gait_clip(loco, gaits["limp"]["walk"]["r"], sk))
        else:
            g = gaits[loco]
            for m in ("walk", "run"):
                out.append(_phase_clip(gait_clip(f"{m}_{loco}", g[m], sk, note=f"{loco} {m}")))
            out.append(idle_gait_clip(loco, g["walk"], sk))
    return out


def ensure_cycles() -> None:
    """LOCO_CYCLES / STATE_CYCLES（位相 1 あたりのブロック）を、クリップを作らずに求める
    （gen_nr_entities が client_initialize / client_pre_animation だけを呼んでも使えるように）。"""
    if LOCO_CYCLES and STATE_CYCLES:
        return
    gaits = loco_gaits()
    for loco in SPEC.LOCOMOTION_VOCAB:
        sk = style_skel(loco)
        LL = leg_len(sk)
        if loco in QUAD_BUILDERS:
            qw, qr = QUAD_BUILDERS[loco](sk, "walk"), QUAD_BUILDERS[loco](sk, "run")
            LOCO_CYCLES[loco] = dict(walk=qw.stride / qw.duty / 16.0, run=qr.stride / qr.duty / 16.0, LL=LL)
        else:
            g = gaits[loco]
            gw, gr = (g["walk"]["r"], g["run"]["r"]) if loco == "limp" else (g["walk"], g["run"])
            LOCO_CYCLES[loco] = dict(walk=cycle_blocks(gw, 1.0, sk), run=cycle_blocks(gr, 1.0, sk), LL=LL)
    sk = design_skel()
    STATE_CYCLES["gimp"] = cycle_blocks(gaits["limp"]["walk"]["r"], 1.0, sk)
    q1 = crawl_quad(sk, "walk", "one_r")
    STATE_CYCLES["crawl1"] = q1.stride / q1.duty / 16.0
    qh = crawl_quad(sk, "walk", "half")
    STATE_CYCLES["drag"] = qh.stride / qh.duty / 16.0
    STATE_CYCLES["crawl_walk"] = LOCO_CYCLES["crawl"]["walk"]
    STATE_CYCLES["crawl_run"] = LOCO_CYCLES["crawl"]["run"]


# ===========================================================================
#  12. 姿勢を組む道具（キーのクリップ・床合わせ・手足を床に寝かせる）
# ===========================================================================
TK = 1.0 / 20.0     # 1 tick（秒）


def keyed(name: str, length: float, keys, loop=False, lerp: str = "catmullrom", **kw) -> Clip:
    """keys = [(時刻, ポーズ[, lerp])] からクリップを作る。"""
    c = Clip(name, float(length), loop=loop, lerp=lerp, **kw)
    for k in keys:
        c.key(k[0], k[1], k[2] if len(k) > 2 else None)
    return c


def timed(c: Clip, seconds: float, name: Optional[str] = None) -> Clip:
    """位相で作ったクリップを秒の長さに伸ばす（q.anim_time で回す）。"""
    k = seconds / c.length
    out = copy.deepcopy(c)
    out.name = name or c.name
    out.length = seconds
    out.keys = [(t * k, p, l) for t, p, l in c.keys]
    out.anim_time_update = None
    return out


# 寝た姿勢では猫背（休みの回転に焼いてある）をまっすぐに戻す
STRAIGHT = P(torso=("-0.45 * v.nr_hn", 0, 0), chest=("-0.55 * v.nr_hn", 0, 0),
             neck=("0.35 * v.nr_hn", 0, 0), head=("0.55 * v.nr_hn", 0, 0))


def lift_to(pose: dict, y) -> dict:
    """root の位置の y を y（数か Molang）に置き換える。"""
    p = copy.deepcopy(pose)
    r = p.setdefault("root", {})
    pos = list(r.get("pos", [0.0, 0.0, 0.0]))
    pos[1] = y
    r["pos"] = pos
    return p


def grounded(skel: Skel, pose: dict, extra: float = 0.0, skip=()) -> dict:
    """いちばん低い点を床に置く root の y（設計の骨格で計算した正規化の数）を書いたポーズ。"""
    L = ground_lift(skel, lift_to(pose, 0.0), skip) / skel_scale(skel)
    return lift_to(pose, round(L + extra, 3))


def settle(skel: Skel, pose: dict, bones: Sequence[str], axis: int, lo: float, hi: float,
           check: Sequence[str], clear: float = 0.2, steps: int = 121) -> dict:
    """bones の回転の axis 成分に lo..hi の角度を足し、check のボーンの一番低い点が床から clear 以上で
    いちばん床に近い角度を選ぶ（寝た手足を床に乗せる）。root の y はその時点の値のまま。"""
    best = fallback = None
    for a in np.linspace(lo, hi, steps):
        add = {b: {"rot": [float(a) if i == axis else 0.0 for i in range(3)]} for b in bones}
        p = padd(pose, add)
        W = skel.world(_numeric(p, skel))
        m = min(_bone_min_y(skel, W, b) for b in check)
        if m >= clear and (best is None or m < best[0]):
            best = (m, float(a))
        if m < clear and (fallback is None or m > fallback[0]):
            fallback = (m, float(a))
    if best is None:                       # どの角度でも床に潜る → いちばん浅いもの
        best = fallback
    return padd(pose, {b: {"rot": [best[1] if i == axis else 0.0 for i in range(3)]} for b in bones})


def _arm(s: str, rx=0.0, ry=0.0, rz=0.0, fx=0.0, hx=0.0, hz=0.0) -> dict:
    """片腕のポーズ（rz は「外へ開く」が正。左腕は符号を反転して書く）。"""
    sgn = 1.0 if s == "r" else -1.0
    return {f"arm_{s}": {"rot": [rx, sgn * ry, sgn * rz]}, f"forearm_{s}": {"rot": [fx, 0.0, 0.0]},
            f"hand_{s}": {"rot": [hx, 0.0, sgn * hz]}}


def _leg(s: str, rx=0.0, ry=0.0, rz=0.0, kx=0.0, fx=0.0, fz=0.0) -> dict:
    """片脚（rz は「外へ開く」が正。kx = 膝の曲げ、fx = 足首）。"""
    sgn = 1.0 if s == "r" else -1.0
    return {f"leg_{s}": {"rot": [rx, sgn * ry, sgn * rz]}, f"shin_{s}": {"rot": [kx, 0.0, 0.0]},
            f"foot_{s}": {"rot": [fx, 0.0, sgn * fz]}}


def body(*parts) -> dict:
    return padd(*parts)


# ===========================================================================
#  13. 寝た姿勢（死体 dead_0..7・倒れ・這ったままの死）
# ===========================================================================
#  death.js の POSE: 0 BACK 仰向け / 1 FRONT うつ伏せ / 2 LEFT 左へ / 3 RIGHT 右へ / 4 CRUMPLE 膝から崩れる /
#  5 CRAWL 這ったまま突っ伏す / 6 HALF 上半身だけ / 7 BLOWN 大の字に吹き飛ぶ。
#  置き方は gore/hitloc.js に合わせる: 1・5 は prone（股関節が原点・頭が前）、ほかは lie（足元が原点・頭が後ろ）。
SUP = padd(P(root=(-90, 0, 0)), STRAIGHT)         # 仰向け（足元を軸に後ろへ倒れた）


def _trunk(skel: Skel, pose: dict, half: bool = False) -> dict:
    """胴（手足を除く）のいちばん低い点を床に置いた高さへ root を上げる（手足を床に乗せる前に）。"""
    skip = ARM_BONES + LEG_BONES + (("pelvis",) if half else ())
    p0 = lift_to(pose, 0.0)
    return lift_to(p0, ground_lift(skel, p0, skip))


def _sup_limbs(skel: Skel, pose: dict) -> dict:
    """仰向けの腕・脚を床に乗せる（腕は後ろ = 床へ、脚も床へ）。"""
    pose = _trunk(skel, pose)
    p = settle(skel, pose, ["arm_r"], 0, -40, 70, ["arm_r", "forearm_r", "hand_r"], clear=0.15)
    p = settle(skel, p, ["arm_l"], 0, -40, 70, ["arm_l", "forearm_l", "hand_l"], clear=0.15)
    p = settle(skel, p, ["leg_r"], 0, -60, 30, ["leg_r", "shin_r", "foot_r"], clear=0.15)
    p = settle(skel, p, ["leg_l"], 0, -60, 30, ["leg_l", "shin_l", "foot_l"], clear=0.15)
    return p


def _pro_limbs(skel: Skel, pose: dict) -> dict:
    """うつ伏せの腕・脚を床に乗せる（腕は前 = 床へ）。"""
    pose = _trunk(skel, pose)
    p = settle(skel, pose, ["arm_r"], 0, -60, 20, ["arm_r", "forearm_r", "hand_r"], clear=0.15)
    p = settle(skel, p, ["arm_l"], 0, -60, 20, ["arm_l", "forearm_l", "hand_l"], clear=0.15)
    p = settle(skel, p, ["leg_r"], 0, -40, 30, ["leg_r", "shin_r", "foot_r"], clear=0.15)
    p = settle(skel, p, ["leg_l"], 0, -40, 30, ["leg_l", "shin_l", "foot_l"], clear=0.15)
    return p


_LYING_CACHE: Dict[Tuple[str, str], dict] = {}


def _pose_skel() -> Skel:
    """寝た姿勢の手足の角度を決める骨格（REF_BUILD。床合わせの変数は使わない）。"""
    if "_pose" not in _STYLE_SKEL:
        _STYLE_SKEL["_pose"] = ref_skel("ref", REF_BUILD)
    return _STYLE_SKEL["_pose"]


def lying(name: str, skel: Optional[Skel] = None) -> dict:
    """寝た姿勢の最終形（root の y = 0）。手足の角度は基準の骨格で一度だけ決める（クリップと同じ回転）。
    種類ごとの床合わせ（GROUND_FITS → v.nr_gl_*）は、この同じ回転をその種類の骨格に当てて測る。"""
    if name not in _LYING_CACHE:
        _LYING_CACHE[name] = lift_to(LYING_DEFS[name](_pose_skel()), 0.0)
    return copy.deepcopy(_LYING_CACHE[name])


def _l_back(sk):            # 0 BACK: 仰向け、腕を投げ出し、頭は横へ
    p = body(SUP, P(head=(0, 55, 8), neck=(0, 15, 0), jaw=(24, 0, 6)),
             _arm("r", 0, -10, 62, -18, 0, 8), _arm("l", 0, 14, 38, -46, 10, 0),
             _leg("r", 0, 6, 9, 6, 10, 26), _leg("l", -34, -8, 15, 46, 20, 30))
    return _sup_limbs(sk, p)


def _l_front(sk):           # 1 FRONT: うつ伏せ（股関節が原点）、片腕は頭の先へ
    p = body(prone_base(sk, False, 0.0), P(neck=(34, 0, 0), head=(28, 72, 0), jaw=(16, 0, 0)),
             _arm("r", -150, 0, 18, -20, -10, 0), _arm("l", 8, 20, 14, -10, 30, 0),
             _leg("r", 0, -10, 6, PRONE_SHIN, PRONE_FOOT, 12), _leg("l", 0, 22, 26, 38, PRONE_FOOT, 10))
    return _pro_limbs(sk, p)


def _l_left(sk):            # 2 LEFT: 仰向けから左へ転がって横向き、膝を曲げる
    p = body(padd(P(root=(-90, 0, 64)), STRAIGHT), P(head=(10, 20, 30), neck=(6, 0, 10), jaw=(18, 0, 0)),
             _arm("l", -70, 0, 10, -40, 0, 0), _arm("r", -100, 0, 0, -30, 0, 0),
             _leg("l", -30, 0, 4, 40, 20, 0), _leg("r", -46, 0, -6, 52, 26, 0))
    return _sup_limbs(sk, p)


def _l_right(sk):           # 3 RIGHT: 2 の左右反転
    return pmirror(_l_left(sk))


def _l_crumple(sk):         # 4 CRUMPLE: 膝から崩れて仰向けに、膝を立てて左へ倒す
    p = body(padd(P(root=(-90, 0, 18)), STRAIGHT), P(head=(0, 30, 10), jaw=(30, 0, 0)),
             _arm("r", 0, 0, 30, -60, 30, 0), _arm("l", 0, 0, 44, -20, 0, 10),
             _leg("r", -64, 0, -22, 96, 30, 0), _leg("l", -56, 0, -30, 92, 24, 0))
    return _sup_limbs(sk, p)


def _l_crawl(sk):           # 5 CRAWL: 這ったまま突っ伏す（腕は前へ投げ出し、頭は横）
    p = body(prone_base(sk, False, 0.0), P(neck=(30, 0, 0), head=(26, -70, 0), jaw=(20, 0, 0)),
             _arm("r", -120, 0, 30, -40, 0, 0), _arm("l", -160, 0, 12, -10, 0, 0),
             _leg("r", 0, 0, 6, PRONE_SHIN, PRONE_FOOT, 12), _leg("l", 0, 0, 10, PRONE_SHIN + 8, PRONE_FOOT, 12))
    return _pro_limbs(sk, p)


def _l_half(sk):            # 6 HALF: 上半身だけ仰向けに（腕は頭の上へ）、腸がこぼれる
    p = body(SUP, P(head=(-8, -40, 0), jaw=(30, 0, 0), guts=(40, 0, 80)),
             _arm("r", -175, 0, 24, -30, 0, 0), _arm("l", 0, 0, 72, -50, 0, 0))
    p = _trunk(sk, p, half=True)
    p = settle(sk, p, ["arm_r"], 0, -30, 30, ["arm_r", "forearm_r", "hand_r"], clear=0.15)
    return settle(sk, p, ["arm_l"], 0, -40, 70, ["arm_l", "forearm_l", "hand_l"], clear=0.15)


def _l_blown(sk):           # 7 BLOWN: 大の字
    p = body(SUP, P(head=(-6, -20, 10), jaw=(34, 0, 0)),
             _arm("r", 0, 0, 84, -8, 0, 0), _arm("l", 0, 0, 78, -14, 0, 0),
             _leg("r", 0, 0, 24, 4, 20, 20), _leg("l", 0, 0, 30, 10, 20, 26))
    return _sup_limbs(sk, p)


def _l_down(sk):            # 倒れて（生きて）仰向け: 片膝を立て、腕は胸の横
    p = body(SUP, P(head=(14, 16, 0), neck=(10, 0, 0), jaw=(10, 0, 0)),
             _arm("r", 0, 0, 30, -60, 10, 0), _arm("l", 0, 0, 22, -30, 0, 0),
             _leg("r", -50, 0, 6, 80, 20, 0), _leg("l", 0, 0, 10, 10, 10, 18))
    return _sup_limbs(sk, p)


def _l_half_prone(sk):      # 上半身だけで這っていて死ぬ（うつ伏せのまま）
    p = body(prone_base(sk, True, 0.0), P(neck=(30, 0, 0), head=(24, 70, 0), jaw=(24, 0, 0), guts=(-30, 10, 20)),
             _arm("r", -160, 0, 24, -30, 0, 0), _arm("l", 10, 0, 30, -40, 0, 0))
    p = _trunk(sk, p, half=True)
    p = settle(sk, p, ["arm_r"], 0, -40, 40, ["arm_r", "forearm_r", "hand_r"], clear=0.15)
    return settle(sk, p, ["arm_l"], 0, -30, 40, ["arm_l", "forearm_l", "hand_l"], clear=0.15)


LYING_DEFS: Dict[str, Callable] = {
    "back": _l_back, "front": _l_front, "left": _l_left, "right": _l_right, "crumple": _l_crumple,
    "crawl": _l_crawl, "half": _l_half, "blown": _l_blown, "down": _l_down, "half_prone": _l_half_prone,
}
# 床合わせの変数（v.nr_gl_<名前>）。half / half_prone は骨盤・脚が無い（切れて消えている）ので数えない
for _n in LYING_DEFS:
    _skip = (("pelvis",) + LEG_BONES) if _n.startswith("half") else ()
    GROUND_FITS[f"v.nr_gl_{_n}"] = ((lambda sk, n=_n: lying(n, sk)), _skip)
DEAD_POSES = ("back", "front", "left", "right", "crumple", "crawl", "half", "blown")   # nr:pose 0..7


# ===========================================================================
#  14. 倒れる・死ぬ・起き上がる（dead_0..7・dead_half・dead_down・st_down・st_rise）
# ===========================================================================
_HALF_SKIP = ("pelvis",) + LEG_BONES


def _final(name: str, add: float = 0.0, pose_add: Optional[dict] = None) -> dict:
    """寝た姿勢の最終形（root の y = 種類ごとの v.nr_gl_<名前>）。"""
    p = lying(name, design_skel())
    if pose_add:
        p = padd(p, pose_add)
    return lift_to(p, f"v.nr_gl_{name}" + (f" + {fmt(add)}" if add else ""))


def _mid(name: str, w: float, flavor: Optional[dict] = None, start: Optional[dict] = None) -> dict:
    """倒れる途中: start（既定は立ち姿 = 0）と最終形を w で混ぜ、flavor を足して床に置く。"""
    sk = design_skel()
    fin = lift_to(lying(name, sk), 0.0)
    p = pscale(fin, w)
    if start:
        p = padd(p, pscale(lift_to(start, 0.0), 1.0 - w))
    if flavor:
        p = padd(p, flavor)
    return grounded(sk, p, skip=_HALF_SKIP if name.startswith("half") else ())


def densify(keys, n: int = 2, skip=(), upto: Optional[float] = None) -> list:
    """キーの間に「床に置き直した中間の姿勢」を n 個ずつ挟む（catmull-rom の行き過ぎで床に潜らないように。
    挟んだ区間は線形補間）。upto より後の区間はそのまま。"""
    sk = design_skel()
    out = []
    for (t0, p0), (t1, p1) in zip(keys[:-1], keys[1:]):
        out.append((t0, p0, "linear"))
        if upto is not None and t1 > upto + 1e-6:
            continue
        for k in range(1, n + 1):
            f = k / (n + 1)
            out.append((t0 + (t1 - t0) * f, grounded(sk, padd(pscale(p0, 1 - f), pscale(p1, f)), skip=skip), "linear"))
    out.append((keys[-1][0], keys[-1][1], "linear"))
    return out


def fall_clip(name: str, final: str, steps, impact: float, length: float, start: Optional[dict] = None,
              bounce: float = 0.55, note: str = "") -> Clip:
    """立ち姿（か start）から寝た姿勢へ倒れて止まる（hold_on_last_frame）。
    steps = [(時刻, 混ぜ具合 w, 足すポーズ)]。impact で床に当たり、小さく跳ねて落ち着く。"""
    keys = [(0.0, start if start is not None else {})]
    for t, w, fl in steps:
        keys.append((t, _mid(final, w, fl, start)))
    keys.append((impact, _final(final)))
    tail = [(impact + 0.09, _final(final, bounce), "linear"), (impact + 0.22, _final(final), "linear"),
            (length, _final(final), "linear")]
    skip = _HALF_SKIP if final.startswith("half") else ()
    return keyed(name, length, densify(keys, 2, skip) + tail, loop="hold_on_last_frame", note=note)


def _both_legs(rx=0.0, kx=0.0, rz=0.0, fx=0.0) -> dict:
    return padd(_leg("r", rx, 0, rz, kx, fx), _leg("l", rx, 0, rz, kx, fx))


def _both_arms(rx=0.0, rz=0.0, fx=0.0, ry=0.0) -> dict:
    return padd(_arm("r", rx, ry, rz, fx), _arm("l", rx, ry, rz, fx))


def crawl_stance(skel: Skel, legs: str = "trail") -> dict:
    """這いの止まった姿（手を床についたうつ伏せ）。死ぬ・倒れる時の始まりの姿勢。"""
    Q = crawl_quad(skel, "walk", legs)
    Qi = Quad(**{**Q.__dict__})
    Qi.stride, Qi.lift = 0.0, 0.0
    return quad_pose(Qi, skel, 0.0)


def build_falls() -> List[Clip]:
    sk = design_skel()
    react_back = padd(P(head=(-25, 0, 0), chest=(-12, 0, 0), neck=(-10, 0, 0), jaw=(30, 0, 0)),
                      _both_arms(-50, 30, -20), _both_legs(-6, 14))
    react_front = padd(P(head=(22, 0, 0), chest=(16, 0, 0), torso=(8, 0, 0), jaw=(26, 0, 0)),
                       _both_arms(30, 16, -10), _both_legs(4, 18))
    react_left = padd(P(head=(0, 0, -18), chest=(0, 0, 10), torso=(0, 0, 8), jaw=(28, 0, 0)),
                      _arm("r", -40, 0, 64, -30), _arm("l", -20, 0, 24, -10), _both_legs(0, 16))
    out = [
        fall_clip("dead_0", "back", [(0.10, 0.0, react_back),
                                     (0.32, 0.28, padd(_both_arms(-110, 20, -30), _both_legs(-10, 26))),
                                     (0.56, 0.74, padd(_both_arms(-140, 40, -20), P(head=(20, 0, 0))))],
                  impact=0.72, length=1.3, note="仰向けに倒れる（前から打たれた）"),
        fall_clip("dead_1", "front", [(0.10, 0.0, react_front),
                                      (0.34, 0.30, padd(_both_arms(-70, 20, -30), _both_legs(-4, 36))),
                                      (0.55, 0.76, padd(_both_arms(-110, 30, -20), P(head=(-10, 30, 0))))],
                  impact=0.70, length=1.3, note="うつ伏せに倒れる（後ろから打たれた）"),
        fall_clip("dead_2", "left", [(0.10, 0.0, react_left),
                                     (0.34, 0.32, padd(_arm("r", -90, 0, 80, -40), _both_legs(-6, 24))),
                                     (0.55, 0.75, _arm("r", -110, 0, 60, -30))],
                  impact=0.72, length=1.3, note="左へ倒れる"),
        fall_clip("dead_3", "right", [(0.10, 0.0, pmirror(react_left)),
                                      (0.34, 0.32, pmirror(padd(_arm("r", -90, 0, 80, -40), _both_legs(-6, 24)))),
                                      (0.55, 0.75, pmirror(_arm("r", -110, 0, 60, -30)))],
                  impact=0.72, length=1.3, note="右へ倒れる"),
        fall_clip("dead_4", "crumple", [(0.14, 0.0, padd(_both_legs(-24, 64), _both_arms(10, 6), P(torso=(14, 0, 0), chest=(8, 0, 0)))),
                                        (0.40, 0.12, padd(_both_legs(-8, 112, 0, 30), _both_arms(14, 8), P(torso=(24, 0, 0), chest=(14, 0, 0)))),
                                        (0.68, 0.55, padd(_both_legs(-30, 90), _both_arms(-30, 30)))],
                  impact=0.88, length=1.5, note="膝から崩れ落ちる（首・頭を失った）"),
        fall_clip("dead_5", "crawl", [(0.22, 0.45, P(neck=(14, 0, 0), head=(10, -30, 0))),
                                      (0.42, 0.85, None)],
                  impact=0.55, length=1.0, start=crawl_stance(sk), bounce=0.25, note="這ったまま突っ伏す"),
        fall_clip("dead_6", "half", [(0.08, 0.0, padd(_both_arms(-130, 40, -20), P(head=(-20, 0, 0), jaw=(40, 0, 0)))),
                                     (0.30, 0.35, padd(_arm("r", -160, 0, 30, -40), _arm("l", -60, 0, 80, -20)))],
                  impact=0.55, length=1.2, note="上半身だけ落ちて仰向けに（胴が真っ二つ）"),
        fall_clip("dead_7", "blown", [(0.08, 0.0, padd(P(torso=(26, 0, 0), chest=(16, 0, 0), head=(20, 0, 0), jaw=(36, 0, 0)),
                                                       _both_arms(-80, 20, -20), _both_legs(-36, 22))),
                                      (0.24, 0.25, padd(_both_arms(-150, 60), _both_legs(-50, 10, 20), P(chest=(-14, 0, 0)))),
                                      (0.44, 0.70, padd(_both_arms(-40, 80), _both_legs(-20, 0, 26)))],
                  impact=0.60, length=1.2, bounce=0.8, note="大の字に吹き飛ぶ（爆発・オーバーキル）"),
        fall_clip("dead_half", "half_prone", [(0.25, 0.5, P(neck=(10, 0, 0)))], impact=0.5, length=0.9,
                  start=crawl_stance(sk, "half"), bounce=0.2, note="上半身だけで這っていて死ぬ"),
        fall_clip("st_down", "down", [(0.10, 0.0, react_back),
                                      (0.30, 0.30, padd(_both_arms(-100, 30, -30), _both_legs(-10, 30))),
                                      (0.50, 0.75, _both_arms(-120, 40, -30))],
                  impact=0.64, length=0.95, note="倒れる（nr:state down の間このまま）"),
    ]
    # dead_down: 倒れていたまま死ぬ（体が一度引きつって力が抜ける）
    out.append(keyed("dead_down", 1.0, [
        (0.0, _final("down")),
        (0.14, _final("down", 0.2, padd(P(chest=(-8, 0, 0), head=(-12, 0, 0), jaw=(30, 0, 0)), _both_arms(-20, 10, -20)))),
        (0.45, _final("down", 0.0, P(head=(-10, 34, 0), jaw=(20, 0, 0)))),
        (1.0, _final("down", 0.0, P(head=(-14, 40, 0), jaw=(24, 0, 0))))], loop="hold_on_last_frame",
        note="倒れていたまま死ぬ"))
    out.append(build_rise("st_rise", 1.25))
    return out


def build_rise(name: str, length: float, from_name: str = "down") -> Clip:
    """仰向けから起き上がる（体を起こす → 片膝 → 立つ）。最後は 0（立ち姿）。"""
    sk = design_skel()
    k = length / 1.25
    sit = padd(P(root=(-48, 0, 0), torso=(26, 0, 0), chest=(14, 0, 0), head=(16, 0, 0)),
               _both_arms(46, 18, -30), _leg("r", -70, 0, 6, 96, 20), _leg("l", -40, 0, 10, 60, 10))
    kneel = padd(P(torso=(28, 0, 0), chest=(10, 0, 0), head=(-14, 0, 0)),
                 _leg("r", -4, 0, 4, 100, 34), _leg("l", -86, 0, 8, 88, -8),
                 _arm("r", -40, 0, 14, -30), _arm("l", -60, 0, 10, -60))
    crouch = padd(P(torso=(22, 0, 0), chest=(6, 0, 0), head=(-12, 0, 0)),
                  _leg("r", -40, 0, 4, 60, -10), _leg("l", -50, 0, 6, 70, -14), _both_arms(-30, 12, -20))
    return keyed(name, length, densify([
        (0.0, _final(from_name)),
        (0.30 * k, grounded(sk, sit)),
        (0.62 * k, grounded(sk, kneel)),
        (0.92 * k, grounded(sk, crouch)),
        (length, {})], 2), note="仰向けから起き上がる")


# ===========================================================================
#  15. 体の状態のクリップ（片脚が折れた歩き・片脚の這い・上半身だけ・壁登り・よろめき）
# ===========================================================================
STATE_CYCLES: Dict[str, float] = {}     # 状態 -> 位相 1 あたりのブロック（基準の身長。v.nr_s 倍で使う）


def build_states() -> List[Clip]:
    ensure_cycles()
    sk = design_skel()
    gaits = loco_gaits()
    out: List[Clip] = []
    # --- gimp: 片脚が折れて（broken）引きずる歩き。v.nr_gimpl = 左脚が折れている
    lw = gaits["limp"]["walk"]
    a = gait_clip("st_gimp_r", lw["r"], sk)
    b = gait_clip("st_gimp_l", lw["l"], sk)
    out.append(_phase_clip(select_clip("st_gimp", a, b, "v.nr_gimpl")))
    broken = {s: padd(_leg(s, -16, 0, 6, 36, 6, 14), P(waist=(0, 0, (4 if s == "r" else -4)))) for s in "rl"}
    ia = idle_gait_clip("limp", lw["r"], sk, "st_gimp_idle_r", extra=broken["r"])
    ib = idle_gait_clip("limp", lw["l"], sk, "st_gimp_idle_l", extra=broken["l"])
    out.append(select_clip("st_gimp_idle", ia, ib, "v.nr_gimpl"))
    # --- crawl1: 片脚だけ使える這い（v.nr_c1l = 使える脚が左）
    qr, ql = crawl_quad(sk, "walk", "one_r"), crawl_quad(sk, "walk", "one_l")
    out.append(_phase_clip(select_clip("st_crawl1", quad_clip("st_crawl1_r", qr, sk), quad_clip("st_crawl1_l", ql, sk),
                                       "v.nr_c1l")))
    # --- drag: 胴が真っ二つ（上半身だけ）。腸を引きずる
    qh = crawl_quad(sk, "walk", "half")
    out.append(_phase_clip(quad_clip("st_drag", qh, sk)))
    di = idle_quad_clip("crawl", qh, sk)
    di.name = "st_drag_idle"
    out.append(di)
    # --- stagger: その場でよろめく（nr:state stagger。足は床に固定したまま小さく踏み替える）
    g = Gait(**{**gaits["stagger"]["walk"].__dict__})
    g.stride, g.keys = 0.10, 16
    st = gait_clip("st_stagger", g, sk)
    st = timed(st, 2.4)
    st.loop = True
    out.append(padd_clip(st, lambda t: padd(_both_arms(-24 * _smooth(t / 0.3), 34 * _smooth(t / 0.3), -20),
                                            P(head=(8 * _sin(t / 2.4 * 3), 10 * _sin(t / 2.4 * 2), 0)))))
    # --- 壁登り（nr:state climb）: ab_wall_climb（能力。素早い）と st_climb（不器用な汎用）
    out.append(climb_clip("ab_wall_climb", 0.8, agile=True))
    out.append(climb_clip("st_climb", 1.3, agile=False))
    return out


def padd_clip(c: Clip, fn: Callable) -> Clip:
    """各キーに fn(時刻) のポーズを足す（ただし最初と最後で 0 にならない足し方は呼ぶ側の責任）。"""
    c.keys = [(t, padd(p, fn(t)), l) for t, p, l in c.keys]
    return c


def climb_clip(name: str, length: float, agile: bool) -> Clip:
    """壁に向かって登る（両手を交互に上へ伸ばし、反対の膝を引き上げて蹴る）。ループ。"""
    lean = P(torso=(10, 0, 0), chest=(6, 0, 0), neck=(-14, 0, 0), head=(-26, 0, 0), jaw=(10, 0, 0))
    reach = padd(_arm("r", -168, 0, 12, -12, -20), _arm("l", -112, 0, 18, -76, -10),
                 _leg("r", -12, 0, 6, 22, 20), _leg("l", -78, 0, 10, 98, -12), P(root_pos=(0.0, 0.0, 0.0)))
    pull = padd(_arm("r", -140, 0, 16, -60, -10), _arm("l", -150, 0, 14, -40, -20),
                _leg("r", -40, 0, 8, 60, 6), _leg("l", -40, 0, 8, 60, 6), P(root_pos=(0.0, 0.8, 0.0)))
    sway = 1.0 if agile else 2.2
    k0 = padd(lean, reach, P(waist=(0, 6 * sway, 3 * sway), head=(0, -8 * sway, 0)))
    k1 = padd(lean, pull, P(waist=(0, 0, 0), chest=(4, 0, 0)))
    k2 = padd(lean, pmirror(reach), P(waist=(0, -6 * sway, -3 * sway), head=(0, 8 * sway, 0)))
    keys = [(0.0, k0), (0.25 * length, k1), (0.5 * length, k2), (0.75 * length, pmirror(k1) if agile else padd(k1, P(head=(6, 12, 0)))),
            (length, k0)]
    return keyed(name, length, keys, loop=True, note="壁登り" + ("（素早い）" if agile else "（不器用）"))


# ===========================================================================
#  16. 重ね（生きている揺れ・見る・被弾・燃える・感電・折れた腕・腸）と演出だけのクリップ
# ===========================================================================
_LT = "(q.life_time + v.nr_seed * 13.0)"


def _pulse(freq: float, phase: float, sharp: int) -> str:
    """ときどき鋭く立ち上がるパルス（0..1。sin の山を sharp 乗して尖らせる。度の単位）。"""
    return f"math.pow(math.max(0.0, math.sin({_LT} * {fmt(freq)} + {fmt(phase)})), {sharp})"


def _jit(freq: float, amp: float, phase: float = 0.0) -> str:
    return f"{fmt(amp)} * math.sin(q.life_time * {fmt(freq)} + {fmt(phase)})"


def expr_clip(name: str, chans: Dict[str, Dict[str, list]], length: float = 1.0, weight_arms: bool = True,
              note: str = "") -> Clip:
    """式だけのクリップ（キー無し。毎フレーム評価）。chans = {bone: {"rot": [..], "pos": [..]}}。"""
    c = Clip(name, length, loop=True, weight_arms=weight_arms, note=note)
    c.expr = copy.deepcopy(chans)
    return c


def fx_clip(name: str, length: float, effects: List[dict], note: str = "") -> Clip:
    """パーティクルを出すだけのループ（各周回の頭で 1 回）。"""
    c = Clip(name, length, loop=True, note=note)
    c.particles = {0.0: list(effects)}
    return c


def build_overlays() -> List[Clip]:
    out: List[Clip] = []
    # --- 生きている揺れ: 顎のカチカチ・ときどき首がかくっと引きつる・肩の痙攣・指の握り・呼吸
    out.append(expr_clip("ov_alive", {
        "jaw": {"rot": [f"3.0 * math.sin({_LT} * 60) + 7.0 * {_pulse(47, 0, 6)} * math.abs(math.sin({_LT} * 1400))", 0, 0]},
        "head": {"rot": [f"5 * {_pulse(41, 60, 40)}", f"7 * {_pulse(23, 200, 40)}",
                         f"10 * {_pulse(33, 0, 40)} - 8 * {_pulse(29, 120, 40)}"]},
        "neck": {"rot": [0, 0, f"4 * {_pulse(33, 0, 40)}"]},
        "chest": {"rot": [f"1.4 * math.sin({_LT} * 80)", 0, 0]},
        "arm_r": {"rot": [0, 0, f"6 * {_pulse(17, 40, 60)}"]},
        "arm_l": {"rot": [0, 0, f"-6 * {_pulse(19, 220, 60)}"]},
        "hand_r": {"rot": [f"14 * {_pulse(53, 10, 20)}", 0, 0]},
        "hand_l": {"rot": [f"14 * {_pulse(49, 160, 20)}", 0, 0]},
    }, note="生きている揺れ（顎・首の引きつり・指）"))
    # --- 標的を見る（首と頭で分け合う）
    tx = "math.clamp(q.target_x_rotation, -40, 40)"
    ty = "math.clamp(q.target_y_rotation, -70, 70)"
    out.append(expr_clip("ov_look", {"neck": {"rot": [f"{tx} * 0.3", f"{ty} * 0.3", 0]},
                                     "head": {"rot": [f"{tx} * 0.5", f"{ty} * 0.5", 0]}}, note="標的を見る"))
    # --- 被弾ののけぞり（q.hurt_time。スクリプトを待たない）
    f = "math.sin(math.clamp(q.hurt_time / 10, 0, 1) * 180)"
    out.append(expr_clip("ov_hurt", {
        "torso": {"rot": [f"-7 * {f}", 0, 0]}, "chest": {"rot": [f"-6 * {f}", f"5 * {f}", 0]},
        "head": {"rot": [f"-14 * {f}", 0, f"6 * {f}"]}, "jaw": {"rot": [f"16 * {f}", 0, 0]},
        "arm_r": {"rot": [f"-18 * {f}", 0, f"12 * {f}"]}, "arm_l": {"rot": [f"-18 * {f}", 0, f"-12 * {f}"]},
    }, note="被弾ののけぞり"))
    # --- 燃えてもがく（q.is_on_fire の間ループ）
    k0 = padd(_arm("r", -130, 0, 40, -60, 10), _arm("l", -60, 0, 30, -90, -20),
              P(head=(10, 25, 0), torso=(4, 15, 0), chest=(0, 10, 0), jaw=(36, 0, 0)))
    k1 = padd(_arm("r", -70, 0, 60, -100, -10), _arm("l", -150, 0, 30, -40, 20),
              P(head=(-16, -20, 10), torso=(-4, -15, 0), chest=(-6, -10, 0), jaw=(44, 0, 0)))
    k2 = padd(pmirror(k0), P(jaw=(30, 0, 0)))
    k3 = padd(pmirror(k1), P(head=(4, 0, -12)))
    out.append(keyed("ov_burning", 1.2, [(0.0, k0), (0.3, k1), (0.6, k2), (0.9, k3), (1.2, k0)], loop=True,
                     note="燃えてもがく"))
    # --- 感電の震え（nr:shock = 1）: 体を反らせて硬直し、全身が細かく震える
    out.append(expr_clip("ov_shock", {
        "root": {"pos": [_jit(8300, 0.18), _jit(9100, 0.12, 40), 0]},
        "torso": {"rot": [f"-6 + {_jit(7700, 3)}", _jit(8900, 3, 10), _jit(9500, 3, 70)]},
        "chest": {"rot": [f"-10 + {_jit(7900, 4)}", _jit(8700, 3, 30), _jit(9300, 3)]},
        "head": {"rot": [f"-22 + {_jit(8100, 7)}", _jit(7300, 6, 50), _jit(9700, 6)]},
        "jaw": {"rot": [f"26 + {_jit(8800, 12)}", 0, 0]},
        "arm_r": {"rot": [f"-30 + {_jit(7700, 8)}", 0, f"40 + {_jit(8500, 6, 20)}"]},
        "arm_l": {"rot": [f"-30 + {_jit(8100, 8, 90)}", 0, f"-40 + {_jit(8300, 6)}"]},
        "forearm_r": {"rot": [f"-20 + {_jit(9100, 10)}", 0, 0]},
        "forearm_l": {"rot": [f"-20 + {_jit(8900, 10, 33)}", 0, 0]},
        "hand_r": {"rot": [f"-50 + {_jit(8300, 12)}", 0, 0]},
        "hand_l": {"rot": [f"-50 + {_jit(8700, 12, 21)}", 0, 0]},
        "leg_r": {"rot": [_jit(7900, 3), 0, _jit(8700, 2)]},
        "leg_l": {"rot": [_jit(8300, 3, 50), 0, _jit(9100, 2)]},
    }, note="感電の震え"))
    # --- 折れた腕がぶら下がる（腕の動きは v.nr_aw* = 0.3 に落とし、これが垂れ下がりと振り子を足す）
    swing = "math.sin(v.nr_ph * 720) * v.nr_mv"
    for s, sgn in (("r", 1.0), ("l", -1.0)):
        out.append(expr_clip(f"ov_arm_{s}_broken", {
            f"arm_{s}": {"rot": [f"10 + 14 * {swing}", 0, fmt(-6 * sgn)]},
            f"forearm_{s}": {"rot": [f"6 + 10 * {swing}", fmt(48 * sgn), 0]},
            f"hand_{s}": {"rot": [f"46 + 8 * {swing}", 0, fmt(24 * sgn)]},
        }, weight_arms=False, note="折れた腕がぶら下がる"))
    # --- 裂けた腹から垂れた腸が揺れる（nr:torso = gutted）
    out.append(expr_clip("ov_guts", {"guts": {"rot": [
        f"6 * math.sin(q.life_time * 140) + 12 * math.sin(v.nr_ph * 720) * v.nr_mv", 0,
        "8 * math.sin(q.life_time * 95)"]}}, note="腸が揺れる"))
    # --- 這う体が血の跡を残す（下半身に断面がある時。0.45 秒ごと）
    out.append(fx_clip("fx_trail", 0.45, [{"effect": "trail", "locator": "loc_waist"}], note="這った跡の血"))
    return out


# ===========================================================================
#  17. 攻撃 atk_<攻撃>（ATTACK_VOCAB の全部。windup / active / recover の tick に合わせる）
# ===========================================================================
#  スクリプト（zombies/ai.js）は windup の始まりに playAnimation する。加算・最初と最後のキーが 0（P3）。
#  体を前へ運ぶ攻撃（lunge / charge / tackle / pounce）の移動はスクリプトが applyImpulse で行い、
#  アニメは姿勢だけ（root の位置の変化は小さく、最後は 0 に戻す）。
ATTACK_META: Dict[str, dict] = {}


def _crouch(depth: float = 1.0) -> dict:
    """足を床に残したまま膝を曲げて沈む（depth 1 = 深いしゃがみ）。root の y は grounded で決める。"""
    return padd(_both_legs(-38 * depth, 70 * depth, 4, -30 * depth), P(torso=(16 * depth, 0, 0)))


def _g(pose: dict, extra: float = 0.0) -> dict:
    """足が床に着いた姿勢に（しゃがみ・踏み込みの root の y を自動で）。"""
    return grounded(design_skel(), pose, extra)


def attack(name: str, w: int, a: int, r: int, keys, note: str = "", hits: Optional[List[float]] = None) -> Clip:
    """keys = [(時刻(秒), ポーズ)]。0 と最後（windup + active + recover）の 0 のキーは自動で足す。"""
    L = (w + a + r) * TK
    ks = [(0.0, {})] + [(t, p) for t, p in keys if 0.0 < t < L - 1e-6] + [(L, {})]
    c = keyed(f"atk_{name}", L, ks, kind="attack", oneshot=True, note=note)
    ATTACK_META[f"atk_{name}"] = {"length": round(L, 3), "controller": "nr.z.atk", "blend": 0.1,
                                  "windup": round(w * TK, 3), "active": round(a * TK, 3), "recover": round(r * TK, 3),
                                  "hits": hits or [round(w * TK, 3)]}
    return c


def _swing_r(rx, rz, fx=-20.0, ry=0.0, hx=0.0) -> dict:
    return _arm("r", rx, ry, rz, fx, hx)


def build_attacks() -> List[Clip]:
    A = SPEC.ATTACK_VOCAB
    out: Dict[str, Clip] = {}

    def T(k):
        return (A[k]["windup"], A[k]["active"], A[k]["recover"])

    # swipe: 右腕を高く振りかぶり、体をひねって横に振り抜く
    w, a, r = T("swipe")
    tw, ta = w * TK, (w + a) * TK
    out["swipe"] = attack("swipe", w, a, r, [
        (tw * 0.6, padd(_swing_r(-110, 60, -60), P(torso=(0, 14, 0), chest=(0, 10, 0), head=(-6, 8, 0), jaw=(12, 0, 0)))),
        (tw, padd(_swing_r(-140, 70, -40, 0, -20), P(torso=(-4, 22, 0), chest=(0, 14, 0), jaw=(26, 0, 0)))),
        (tw + (ta - tw) * 0.5, padd(_swing_r(-80, 10, -20, 0, -10), P(torso=(10, -10, 0), chest=(0, -16, 0)))),
        (ta, padd(_swing_r(-40, -30, -30), P(torso=(12, -24, 0), chest=(4, -20, 0), jaw=(30, 0, 0)))),
        (ta + 0.25, padd(_swing_r(-20, -10, -20), P(torso=(6, -10, 0), jaw=(14, 0, 0))))], "片腕の引っかき")
    # double_swipe: 両腕を頭上へ上げ、右・左と交互に振り下ろす
    w, a, r = T("double_swipe")
    tw, ta = w * TK, (w + a) * TK
    up2 = padd(_both_arms(-160, 20, -50), P(torso=(-8, 0, 0), jaw=(20, 0, 0), head=(-8, 0, 0)))
    out["double_swipe"] = attack("double_swipe", w, a, r, [
        (tw * 0.6, padd(_both_arms(-120, 24, -60), P(torso=(-4, 0, 0)))), (tw, up2),
        (tw + 0.12, padd(_arm("r", -30, 0, 0, -10), _arm("l", -150, 0, 20, -50), P(torso=(14, -10, 0), jaw=(34, 0, 0)))),
        (tw + 0.26, padd(_arm("r", -100, 0, 20, -50), _arm("l", -30, 0, 0, -10), P(torso=(14, 10, 0), jaw=(30, 0, 0)))),
        (ta, padd(_both_arms(-34, 4, -14), P(torso=(16, 0, 0), chest=(6, 0, 0)))),
        (ta + 0.3, padd(_both_arms(-16, 6, -14), P(torso=(6, 0, 0))))], "両腕で二度振り下ろす",
        hits=[round(tw + 0.12, 3), round(tw + 0.26, 3)])
    # grab_bite: 両手で掴んで引き寄せ、何度も首に噛みつく
    w, a, r = T("grab_bite")
    tw, ta = w * TK, (w + a) * TK
    reach = padd(_both_arms(-95, 10, -10, 0), P(torso=(14, 0, 0), head=(-6, 0, 0), jaw=(30, 0, 0)))
    hold = padd(_both_arms(-70, -4, -95), P(torso=(10, 0, 0)))
    keys = [(tw * 0.6, padd(_both_arms(-70, 14, -20), P(torso=(8, 0, 0), jaw=(20, 0, 0)))), (tw, reach),
            (tw + 0.15, padd(_both_arms(-80, -6, -60), P(torso=(12, 0, 0), jaw=(30, 0, 0))))]
    t = tw + 0.4
    while t < ta - 0.1:
        keys.append((t, padd(hold, P(neck=(-6, 0, 0), head=(-10, 0, 0), jaw=(42, 0, 0)))))
        keys.append((t + 0.15, padd(hold, P(neck=(22, 0, 0), head=(18, 12, 0), jaw=(2, 0, 0)))))
        t += 0.4
    keys += [(ta, padd(hold, P(jaw=(20, 0, 0)))), (ta + 0.3, padd(_both_arms(-40, 6, -40), P(torso=(6, 0, 0))))]
    out["grab_bite"] = attack("grab_bite", w, a, r, keys, "掴んで引き寄せ噛みつく")
    # bite: 頭を引いてから突き出して噛む
    w, a, r = T("bite")
    tw, ta = w * TK, (w + a) * TK
    out["bite"] = attack("bite", w, a, r, [
        (tw, padd(P(neck=(-18, 0, 0), head=(-20, 0, 0), jaw=(40, 0, 0), torso=(-6, 0, 0)), _both_arms(10, 10, -10))),
        (tw + (ta - tw) * 0.5, P(neck=(26, 0, 0), head=(20, 0, 0), torso=(14, 0, 0), jaw=(42, 0, 0))),
        (ta, P(neck=(28, 0, 0), head=(22, 0, 0), torso=(14, 0, 0), jaw=(0, 0, 0))),
        (ta + 0.15, P(neck=(24, 0, 0), head=(18, 14, 0), torso=(12, 0, 0), jaw=(4, 0, 0))),
        (ta + 0.3, P(neck=(16, 0, 0), head=(12, -12, 0), torso=(8, 0, 0), jaw=(6, 0, 0)))], "噛みつく")
    # bite_low: 這ったまま頭を突き出して足首に噛みつく（這いの姿勢に加算）
    w, a, r = T("bite_low")
    tw, ta = w * TK, (w + a) * TK
    out["bite_low"] = attack("bite_low", w, a, r, [
        (tw, P(neck=(-14, 0, 0), head=(-8, 0, 0), jaw=(42, 0, 0), root_pos=(0, 0.3, 1.0))),
        (tw + (ta - tw) * 0.5, P(neck=(22, 0, 0), head=(14, 0, 0), jaw=(42, 0, 0), root_pos=(0, 0, -1.6))),
        (ta, P(neck=(22, 0, 0), head=(14, 0, 0), jaw=(0, 0, 0), root_pos=(0, 0, -1.6))),
        (ta + 0.2, P(neck=(18, 0, 0), head=(10, 16, 0), jaw=(4, 0, 0), root_pos=(0, 0, -1.2))),
        (ta + 0.4, P(neck=(14, 0, 0), head=(8, -14, 0), jaw=(6, 0, 0), root_pos=(0, 0, -0.6)))], "這ったまま足首に噛む")
    # lunge: 身をかがめてから一気に飛びかかる
    w, a, r = T("lunge")
    tw, ta = w * TK, (w + a) * TK
    out["lunge"] = attack("lunge", w, a, r, [
        (tw, _g(padd(_crouch(0.8), _both_arms(30, 20, -30), P(torso=(24, 0, 0), head=(-20, 0, 0), jaw=(20, 0, 0))))),
        (tw + (ta - tw) * 0.5, padd(_both_legs(20, 16, 0, 20), _both_arms(-100, 15, -10),
                                   P(torso=(26, 0, 0), head=(-10, 0, 0), jaw=(42, 0, 0), root_pos=(0, 1.0, -2.0)))),
        (ta, padd(_both_arms(-80, -5, -40), P(torso=(20, 0, 0), jaw=(30, 0, 0), root_pos=(0, 0, -1.0)))),
        (ta + 0.35, padd(_both_arms(-40, 4, -30), P(torso=(10, 0, 0))))], "飛びかかる")
    # slam: 両手を組んで頭上から叩き下ろす
    w, a, r = T("slam")
    tw, ta = w * TK, (w + a) * TK
    out["slam"] = attack("slam", w, a, r, [
        (tw * 0.6, padd(_both_arms(-130, -10, -40), P(torso=(-6, 0, 0)))),
        (tw, padd(_both_arms(-175, -18, -30), P(torso=(-14, 0, 0), chest=(-6, 0, 0), head=(-10, 0, 0), jaw=(30, 0, 0),
                                                 root_pos=(0, 0.3, 0)))),
        (tw + (ta - tw) * 0.6, _g(padd(_both_arms(-60, -10, -10), _crouch(0.5),
                                       P(torso=(30, 0, 0), chest=(14, 0, 0), head=(14, 0, 0), jaw=(40, 0, 0))))),
        (ta + 0.1, _g(padd(_both_arms(-50, -6, -10), _crouch(0.5), P(torso=(32, 0, 0), chest=(14, 0, 0))))),
        (ta + 0.5, _g(padd(_both_arms(-30, 4, -20), _crouch(0.2), P(torso=(14, 0, 0)))))], "両手を組んで叩き下ろす")
    # headbutt: 頭を反らしてから額を叩きつける
    w, a, r = T("headbutt")
    tw, ta = w * TK, (w + a) * TK
    out["headbutt"] = attack("headbutt", w, a, r, [
        (tw, padd(P(neck=(-20, 0, 0), head=(-22, 0, 0), torso=(-10, 0, 0), chest=(-8, 0, 0), jaw=(8, 0, 0)),
                  _both_arms(20, 20, -20))),
        (tw + (ta - tw) * 0.6, P(torso=(22, 0, 0), chest=(14, 0, 0), neck=(20, 0, 0), head=(24, 0, 0), root_pos=(0, 0, -1.0))),
        (ta + 0.1, P(torso=(18, 0, 0), chest=(10, 0, 0), neck=(16, 0, 0), head=(18, 0, 0), root_pos=(0, 0, -0.8))),
        (ta + 0.35, P(torso=(6, 0, 0), head=(-6, 10, 6)))], "頭突き")
    # claw_flurry: 爪で四連続の引っかき（右・左・右・左）
    w, a, r = T("claw_flurry")
    tw, ta = w * TK, (w + a) * TK
    up = padd(_both_arms(-130, 50, -60), P(torso=(10, 0, 0), jaw=(30, 0, 0)))
    keys, hits = [(tw, up)], []
    for i in range(4):
        ti = tw + (ta - tw) * (i + 0.6) / 4.0
        s = "r" if i % 2 == 0 else "l"
        o = "l" if s == "r" else "r"
        tw_ = 18.0 if s == "r" else -18.0
        keys.append((ti, padd(_arm(s, -50, 0, -20, -20), _arm(o, -140, 0, 55, -60),
                              P(torso=(14, -tw_, 0), chest=(4, -tw_ * 0.6, 0), jaw=(36 + 4 * i, 0, 0)))))
        hits.append(round(ti, 3))
    keys.append((ta + 0.3, padd(_both_arms(-40, 10, -30), P(torso=(8, 0, 0)))))
    out["claw_flurry"] = attack("claw_flurry", w, a, r, keys, "四連続の引っかき", hits=hits)
    # spit: 胸を膨らませて反り、前へ吐く
    w, a, r = T("spit")
    tw, ta = w * TK, (w + a) * TK
    out["spit"] = attack("spit", w, a, r, [
        (tw * 0.6, padd(P(chest=(-12, 0, 0), head=(-26, 0, 0), neck=(-16, 0, 0), jaw=(10, 0, 0)), _both_arms(10, 25, -10))),
        (tw, padd(P(torso=(-10, 0, 0), chest=(-16, 0, 0), head=(-30, 0, 0), neck=(-16, 0, 0), jaw=(4, 0, 0),
                    throat_sac_scl=(1.6, 1.6, 1.6)), _both_arms(20, 28, -10))),
        (tw + 0.06, P(torso=(16, 0, 0), chest=(12, 0, 0), neck=(18, 0, 0), head=(16, 0, 0), jaw=(52, 0, 0))),
        (ta + 0.1, P(torso=(14, 0, 0), chest=(10, 0, 0), neck=(16, 0, 0), head=(14, 0, 0), jaw=(48, 0, 0))),
        (ta + 0.4, P(torso=(6, 0, 0), jaw=(26, 0, 0)))], "酸を吐く")
    # explode: 体を震わせて膨れ上がる（最後の瞬間に爆発。スクリプトが消す）
    w, a, r = T("explode")
    L = (w + a + r) * TK
    keys = []
    n = int(L / 0.075)
    for i in range(1, n):
        t = i * 0.075
        k = min(1.0, t / (w * TK))
        j = (1 if i % 2 else -1) * (2 + 6 * k)
        keys.append((t, padd(_both_arms(-30 * k + j, 40 * k, -20 * k), _both_legs(0, 8 * k),
                             P(torso=(j * 0.5, j, j * 0.4), chest=(-10 * k + j, -j, 0), head=(-24 * k + j, j * 2, j),
                               jaw=(40 * k + abs(j), 0, 0), torso_scl=(1 + 0.22 * k, 1 + 0.08 * k, 1 + 0.25 * k),
                               chest_scl=(1 + 0.18 * k, 1 + 0.06 * k, 1 + 0.2 * k), root_pos=(j * 0.05, 0, 0)))))
    out["explode"] = attack("explode", w, a, r, keys, "震えて膨れ、自爆する", hits=[round(w * TK, 3)])
    out["explode"].keys = [(t, p, "linear") for t, p, _l in out["explode"].keys]
    # scream: 息を吸って反り、前へ金切り声
    w, a, r = T("scream")
    tw, ta = w * TK, (w + a) * TK
    sc = padd(P(torso=(14, 0, 0), chest=(8, 0, 0), neck=(16, 0, 0), head=(6, 0, 0), jaw=(56, 0, 0)),
              _both_arms(40, 45, -10), P(hand_r=(-30, 0, 0), hand_l=(-30, 0, 0)))
    keys = [(tw * 0.6, padd(P(chest=(-10, 0, 0), head=(-20, 0, 0), jaw=(8, 0, 0)), _both_arms(10, 20, 0))),
            (tw, padd(P(chest=(-14, 0, 0), head=(-26, 0, 0), jaw=(6, 0, 0)), _both_arms(30, 30, 0))),
            (tw + 0.1, sc)]
    t, i = tw + 0.2, 0
    while t < ta:
        keys.append((t, padd(sc, P(head=(0, 0, 3 if i % 2 else -3), jaw=(2 if i % 2 else -2, 0, 0)))))
        t += 0.1
        i += 1
    keys.append((ta + 0.4, padd(pscale(sc, 0.4))))
    out["scream"] = attack("scream", w, a, r, keys, "金切り声")
    # charge: 吠えてから頭を下げ、肩を前に突進の構えを保つ（脚の走りは移動のアニメ）
    w, a, r = T("charge")
    tw, ta = w * TK, (w + a) * TK
    ram = padd(P(neck=(30, 0, 0), head=(20, 0, 0), torso=(28, 0, 0), chest=(14, 0, 0), jaw=(30, 0, 0)), _both_arms(30, 18, -30))
    keys = [(tw * 0.4, padd(P(head=(-20, 0, 0), jaw=(44, 0, 0), chest=(-10, 0, 0)), _both_arms(20, 40, -20))),
            (tw, ram)]
    t, i = tw + 0.3, 0
    while t < ta - 0.1:
        keys.append((t, padd(ram, P(head=(0, 4 if i % 2 else -4, 0), chest=(0, 3 if i % 2 else -3, 0)))))
        t += 0.3
        i += 1
    keys.append((ta + 0.5, pscale(ram, 0.3)))
    out["charge"] = attack("charge", w, a, r, keys, "頭を下げて突進")
    # throw: 瓦礫を頭の後ろへ振りかぶって投げる
    w, a, r = T("throw")
    tw, ta = w * TK, (w + a) * TK
    out["throw"] = attack("throw", w, a, r, [
        (tw * 0.4, _g(padd(_crouch(0.7), _both_arms(-40, 10, -20), P(torso=(40, 0, 0))))),
        (tw * 0.75, padd(_both_arms(-150, 12, -40), P(torso=(-6, 0, 0)))),
        (tw, padd(_both_arms(-185, 15, -60), P(torso=(-16, 0, 0), chest=(-12, 0, 0), head=(-6, 0, 0), jaw=(24, 0, 0)))),
        (tw + (ta - tw) * 0.7, padd(_both_arms(-60, 8, -10), P(torso=(26, 0, 0), chest=(16, 0, 0), jaw=(34, 0, 0),
                                                                root_pos=(0, 0, -0.8)))),
        (ta + 0.4, padd(_both_arms(-30, 6, -10), P(torso=(10, 0, 0))))], "瓦礫を投げる")
    # ground_pound: 両拳を高く上げ、深くしゃがんで地面を叩く
    w, a, r = T("ground_pound")
    tw, ta = w * TK, (w + a) * TK
    low = _g(padd(_crouch(1.0), _both_arms(-40, 10, -10), P(torso=(46, 0, 0), chest=(18, 0, 0), head=(18, 0, 0), jaw=(40, 0, 0))))
    out["ground_pound"] = attack("ground_pound", w, a, r, [
        (tw * 0.5, padd(_both_arms(-150, 30, -70), P(torso=(-10, 0, 0), root_pos=(0, 0.3, 0)))),
        (tw, padd(_both_arms(-185, 20, -40), P(torso=(-16, 0, 0), head=(-10, 0, 0), jaw=(30, 0, 0)))),
        (tw + (ta - tw) * 0.7, low), (ta + 0.1, low),
        (ta + 0.7, _g(padd(_crouch(0.6), _both_arms(-30, 10, -10), P(torso=(30, 0, 0))))),
        (ta + 1.1, _g(padd(_crouch(0.2), P(torso=(10, 0, 0)))))], "地面を叩く")
    # pounce: しゃがんで跳びかかり、押し倒す
    w, a, r = T("pounce")
    tw, ta = w * TK, (w + a) * TK
    out["pounce"] = attack("pounce", w, a, r, [
        (tw, _g(padd(_crouch(1.0), _both_arms(40, 20, -20), P(torso=(30, 0, 0), head=(-20, 0, 0), jaw=(20, 0, 0))))),
        (tw + (ta - tw) * 0.35, padd(_both_legs(-60, 80, 6, -10), _both_arms(-120, 25, -20),
                                     P(torso=(20, 0, 0), head=(-10, 0, 0), jaw=(44, 0, 0), root_pos=(0, 2.0, -1.0)))),
        (tw + (ta - tw) * 0.8, _g(padd(_crouch(0.6), _both_arms(-80, 14, -30), P(torso=(30, 0, 0), jaw=(30, 0, 0))))),
        (ta + 0.4, _g(padd(_crouch(0.3), _both_arms(-40, 10, -20), P(torso=(14, 0, 0)))))], "跳びかかって押し倒す")
    # tool_swing: 持った道具（右手）を頭上から振り下ろす
    w, a, r = T("tool_swing")
    tw, ta = w * TK, (w + a) * TK
    out["tool_swing"] = attack("tool_swing", w, a, r, [
        (tw * 0.6, padd(_swing_r(-140, 20, -90), _arm("l", -30, 0, 10, -20), P(torso=(-4, 12, 0)))),
        (tw, padd(_swing_r(-178, 10, -70), _arm("l", -40, 0, 14, -20), P(torso=(-8, 18, 0), chest=(-4, 6, 0), jaw=(20, 0, 0)))),
        (tw + (ta - tw) * 0.6, padd(_swing_r(-40, -5, -10), _arm("l", -10, 0, 10, -10),
                                     P(torso=(20, -10, 0), chest=(6, -6, 0), jaw=(30, 0, 0)))),
        (ta + 0.1, padd(_swing_r(-30, -5, -10), P(torso=(20, -12, 0)))),
        (ta + 0.45, padd(_swing_r(-20, 0, -20), P(torso=(8, -4, 0))))], "道具を振り下ろす")
    # shield_bash: 左腕の盾を引いてから押し出す
    w, a, r = T("shield_bash")
    tw, ta = w * TK, (w + a) * TK
    out["shield_bash"] = attack("shield_bash", w, a, r, [
        (tw, padd(_arm("l", -50, 0, 24, -90), P(torso=(-4, -18, 0), chest=(0, -10, 0)), _leg("l", -10, 0, 0, 10))),
        (tw + (ta - tw) * 0.6, padd(_arm("l", -82, 0, 6, -70), P(torso=(14, 20, 0), chest=(4, 10, 0), root_pos=(0, 0, -1.0),
                                                                  jaw=(24, 0, 0)))),
        (ta + 0.1, padd(_arm("l", -80, 0, 6, -70), P(torso=(12, 18, 0), root_pos=(0, 0, -0.8)))),
        (ta + 0.4, padd(_arm("l", -50, 0, 10, -60), P(torso=(4, 6, 0))))], "盾で殴る")
    # tackle: 肩を落として体当たり
    w, a, r = T("tackle")
    tw, ta = w * TK, (w + a) * TK
    out["tackle"] = attack("tackle", w, a, r, [
        (tw, _g(padd(_crouch(0.5), _both_arms(30, 10, -100), P(torso=(30, -24, 0), chest=(10, -10, 0), head=(-10, 0, 0))))),
        (tw + (ta - tw) * 0.5, padd(_both_legs(18, 10), _both_arms(30, 10, -100),
                                     P(torso=(40, -26, 0), chest=(12, -10, 0), root_pos=(0, 0, -2.0), jaw=(30, 0, 0)))),
        (ta, padd(_both_arms(10, 20, -60), P(torso=(30, -20, 0), root_pos=(0, 0, -1.4)))),
        (ta + 0.45, padd(_both_arms(-10, 10, -30), P(torso=(12, -6, 0))))], "体当たり")
    # grab_throw: 掴んで持ち上げ、横へ振りかぶって投げ飛ばす
    w, a, r = T("grab_throw")
    tw, ta = w * TK, (w + a) * TK
    out["grab_throw"] = attack("grab_throw", w, a, r, [
        (tw, padd(_both_arms(-80, 15, -10), P(torso=(20, 0, 0), jaw=(20, 0, 0)))),
        (tw + 0.25, padd(_both_arms(-90, 6, -50), P(torso=(16, 0, 0)))),
        (tw + 0.6, padd(_both_arms(-170, 10, -30), P(torso=(-12, 0, 0), chest=(-6, 0, 0), root_pos=(0, 0.5, 0), jaw=(30, 0, 0)))),
        (ta - 0.2, padd(_both_arms(-150, 40, -40), P(torso=(-6, 30, 0), chest=(0, 14, 0)))),
        (ta, padd(_both_arms(-60, -20, -10), P(torso=(14, -30, 0), chest=(6, -14, 0), jaw=(40, 0, 0)))),
        (ta + 0.5, padd(_both_arms(-30, 0, -20), P(torso=(6, -10, 0))))], "掴んで投げ飛ばす")
    # blade_slash: 前腕の骨の刃で素早く斬る
    w, a, r = T("blade_slash")
    tw, ta = w * TK, (w + a) * TK
    out["blade_slash"] = attack("blade_slash", w, a, r, [
        (tw, padd(_swing_r(-100, 70, -10, 0, -10), P(torso=(8, 20, 0), chest=(0, 10, 0), jaw=(16, 0, 0)))),
        (tw + (ta - tw) * 0.5, padd(_swing_r(-90, -30, -6), P(torso=(10, -26, 0), chest=(0, -14, 0), jaw=(30, 0, 0)))),
        (ta, padd(_swing_r(-70, -45, -10), P(torso=(10, -30, 0), chest=(2, -16, 0)))),
        (ta + 0.25, padd(_swing_r(-30, -10, -20), P(torso=(4, -10, 0))))], "刃で斬る")
    # vomit: 体を折って吐き気をこらえ、前へ吐き続ける
    w, a, r = T("vomit")
    tw, ta = w * TK, (w + a) * TK
    sp = padd(P(torso=(24, 0, 0), chest=(14, 0, 0), neck=(20, 0, 0), head=(10, 0, 0), jaw=(50, 0, 0)), _both_arms(-20, 10, -20))
    keys = [(tw * 0.35, P(torso=(20, 0, 0), chest=(14, 0, 0), head=(10, 0, 0), jaw=(10, 0, 0))),
            (tw * 0.75, P(torso=(-6, 0, 0), chest=(-12, 0, 0), head=(-16, 0, 0), jaw=(6, 0, 0))), (tw, sp)]
    t, i = tw + 0.3, 0
    while t < ta:
        keys.append((t, padd(sp, P(torso=(4 if i % 2 else -2, 0, 0), jaw=(4 if i % 2 else -4, 0, 0)))))
        t += 0.3
        i += 1
    keys.append((ta + 0.5, pscale(sp, 0.3)))
    out["vomit"] = attack("vomit", w, a, r, keys, "吐瀉物を浴びせる")
    # stomp: 右膝を高く上げて踏み鳴らす
    w, a, r = T("stomp")
    tw, ta = w * TK, (w + a) * TK
    out["stomp"] = attack("stomp", w, a, r, [
        (tw, padd(_leg("r", -80, 0, 6, 90, -10), _both_arms(-20, 30, -20), P(torso=(-6, 0, 0), root_pos=(0, 0.3, 0)))),
        (tw + (ta - tw) * 0.6, _g(padd(_crouch(0.3), _both_arms(-10, 26, -20), P(torso=(18, 0, 0), jaw=(30, 0, 0))))),
        (ta + 0.1, _g(padd(_crouch(0.35), P(torso=(18, 0, 0))))),
        (ta + 0.45, _g(padd(_crouch(0.1), P(torso=(6, 0, 0)))))], "踏み鳴らす")
    # long_grab: 長い右腕を前へ伸ばして掴み、引き寄せる
    w, a, r = T("long_grab")
    tw, ta = w * TK, (w + a) * TK
    out["long_grab"] = attack("long_grab", w, a, r, [
        (tw * 0.6, padd(_swing_r(-60, 20, -60), P(torso=(-4, 10, 0)))),
        (tw, padd(_swing_r(-95, 10, 0, 0, -10), P(torso=(16, -16, 0), chest=(4, -10, 0), jaw=(30, 0, 0)))),
        (tw + 0.15, padd(_swing_r(-95, 8, 0, 0, 24), P(torso=(16, -16, 0), jaw=(36, 0, 0)))),
        (tw + 0.8, padd(_swing_r(-80, 6, -40, 0, 24), P(torso=(4, -8, 0), root_pos=(0, 0, 0.4)))),
        (ta, padd(_swing_r(-70, 4, -80, 0, 24), P(torso=(-6, 0, 0), jaw=(40, 0, 0), root_pos=(0, 0, 0.6)))),
        (ta + 0.5, padd(_swing_r(-30, 4, -40), P(torso=(0, 0, 0))))], "長い腕で掴んで引き寄せる")
    missing = sorted(set(A) - set(out))
    if missing:
        raise ValueError(f"attack animations missing: {missing}")
    return [out[k] for k in A]


# ===========================================================================
#  18. 一発もの（nr_registry.ZOMBIE_ONESHOTS。加算・最初と最後のキーが 0。controller "nr.z.os"）
# ===========================================================================
ONESHOT_META: Dict[str, dict] = {}


def oneshot(name: str, length: float, keys, note: str = "", blend: float = 0.15, lerp: str = "catmullrom") -> Clip:
    ks = [(0.0, {})] + [(t, p) for t, p in keys if 0.0 < t < length - 1e-6] + [(length, {})]
    c = keyed(name, length, ks, kind="oneshot", oneshot=True, note=note, lerp=lerp)
    ONESHOT_META[name] = {"length": round(length, 3), "controller": "nr.z.os", "blend": blend}
    return c


def build_oneshots() -> List[Clip]:
    out: Dict[str, Clip] = {}
    out["none"] = keyed("none", 0.05, [(0.0, {})], kind="oneshot", oneshot=True, note="何もしない（止める）")
    ONESHOT_META["none"] = {"length": 0.05, "controller": "nr.z.os", "blend": 0.0}
    out["react_head"] = oneshot("react_head", 0.5, [
        (0.06, P(head=(-28, 6, 8), neck=(-12, 0, 0), chest=(-8, 0, 0), jaw=(30, 0, 0))),
        (0.2, P(head=(-10, 4, 4), neck=(-4, 0, 0), chest=(-3, 0, 0), jaw=(18, 0, 0))),
        (0.32, P(head=(4, 0, 0), jaw=(8, 0, 0)))], "頭に当たって仰け反る")
    out["react_torso"] = oneshot("react_torso", 0.6, [
        (0.07, padd(P(torso=(18, 0, 0), chest=(10, 0, 0), head=(8, 0, 0), jaw=(26, 0, 0), root_pos=(0, 0, 0.8)),
                    _both_arms(-30, 10, -20))),
        (0.25, padd(P(torso=(8, 0, 0), chest=(4, 0, 0), root_pos=(0, 0, 0.6)), _both_arms(-10, 6, -10))),
        (0.42, P(torso=(-3, 0, 0)))], "胴に当たってよろめく")
    rar = padd(_arm("r", 40, 0, 30, 10, 20), P(torso=(0, 18, 0), chest=(-4, 10, 0), head=(0, -10, 0)))
    out["react_arm_r"] = oneshot("react_arm_r", 0.45, [(0.06, rar), (0.22, pscale(rar, 0.35))], "右腕を弾かれる")
    out["react_arm_l"] = oneshot("react_arm_l", 0.45, [(0.06, pmirror(rar)), (0.22, pscale(pmirror(rar), 0.35))],
                                 "左腕を弾かれる")
    rlr = _g(padd(_leg("r", -20, 0, 0, 64, -20), _leg("l", -10, 0, 0, 16, -8), _both_arms(-30, 30, -20),
                  P(torso=(12, 0, 6), head=(-10, 0, 0), jaw=(20, 0, 0))))
    out["react_leg_r"] = oneshot("react_leg_r", 0.7, [(0.1, rlr), (0.35, rlr), (0.55, pscale(rlr, 0.3))],
                                 "右脚を払われて膝が落ちる")
    out["react_leg_l"] = oneshot("react_leg_l", 0.7, [(0.1, pmirror(rlr)), (0.35, pmirror(rlr)),
                                                       (0.55, pscale(pmirror(rlr), 0.3))], "左脚を払われて膝が落ちる")
    rh = padd(P(torso=(-20, 0, 0), chest=(-14, 0, 0), head=(-20, 0, 0), jaw=(36, 0, 0), root_pos=(0, 0, 2.0)),
              _both_arms(-70, 40, -30), _leg("r", 20, 0, 0, 10), _leg("l", -20, 0, 0, 24))
    out["react_heavy"] = oneshot("react_heavy", 0.9, [
        (0.08, rh), (0.3, padd(pscale(rh, 0.7), P(torso=(8, 0, 0)))), (0.55, pscale(rh, 0.25))],
        "重い一撃で大きく後ろへよろける")
    # knockdown / getup は nr:state down の倒れ（st_down）・起き上がり（st_rise）と同時に流れる「手応え」
    out["knockdown"] = oneshot("knockdown", 0.9, [
        (0.12, padd(_both_arms(-40, 30, -20), P(head=(-12, 0, 0), jaw=(30, 0, 0)))),
        (0.5, _both_arms(-20, 10, -10)),
        (0.66, padd(_both_arms(10, 10, 10), P(head=(-14, 0, 0), jaw=(24, 0, 0), root_pos=(0, 0.4, 0)))),
        (0.78, P(head=(4, 0, 0)))], "倒れる（st_down と同時に流れる手応え）")
    out["getup"] = oneshot("getup", 1.25, [
        (0.3, P(head=(0, 15, 0), jaw=(10, 0, 0))), (0.6, P(head=(0, -15, 0), jaw=(24, 0, 0))),
        (0.9, P(chest=(0, 0, 6), head=(6, 0, -6))), (1.1, P(head=(-4, 0, 0)))], "起き上がる（st_rise と同時）")
    out["grab"] = oneshot("grab", 1.0, [
        (0.2, padd(_both_arms(-95, 12, -10), P(torso=(12, 0, 0), jaw=(30, 0, 0)))),
        (0.4, padd(_both_arms(-80, -4, -70), P(torso=(10, 0, 0), jaw=(20, 0, 0)))),
        (0.75, padd(_both_arms(-60, 0, -80), P(torso=(6, 0, 0))))], "組みつく")
    out["bite"] = oneshot("bite", 0.8, [
        (0.15, P(neck=(-16, 0, 0), head=(-16, 0, 0), jaw=(40, 0, 0))),
        (0.3, P(neck=(24, 0, 0), head=(18, 0, 0), torso=(10, 0, 0), jaw=(0, 0, 0))),
        (0.45, P(neck=(20, 0, 0), head=(14, 14, 0), torso=(8, 0, 0), jaw=(4, 0, 0))),
        (0.6, P(neck=(10, 0, 0), head=(6, -10, 0), jaw=(10, 0, 0)))], "噛む")
    sh = padd(P(torso=(-14, 0, 0), chest=(-8, 0, 0), head=(10, 0, 0), root_pos=(0, 0, 1.5), jaw=(20, 0, 0)),
              _both_arms(-60, 30, -20), _leg("l", 16, 0, 0, 10))
    out["shoved"] = oneshot("shoved", 0.6, [(0.08, sh), (0.3, pscale(sh, 0.5))], "押しのけられる")
    out["climb_up"] = oneshot("climb_up", 1.0, [
        (0.2, padd(_both_arms(-170, 10, -20), _leg("r", -80, 0, 6, 90, -10), P(head=(-20, 0, 0)))),
        (0.5, padd(_both_arms(-30, 20, -90), _leg("r", -60, 0, 6, 80), P(torso=(40, 0, 0), chest=(10, 0, 0)))),
        (0.75, padd(_both_arms(-10, 14, -30), _leg("l", -70, 0, 6, 90), P(torso=(24, 0, 0))))], "縁へよじ登る")
    st = padd(P(head=(10, 0, 18), neck=(6, 0, 6), torso=(8, 0, -6), jaw=(20, 0, 0)), _both_arms(14, 4, 4),
              _both_legs(-8, 18))
    out["stunned"] = oneshot("stunned", 1.2, [
        (0.15, _g(st)), (0.45, _g(padd(st, P(head=(0, 0, -30), torso=(0, 0, 10))))),
        (0.75, _g(padd(st, P(head=(-6, 10, 10))))), (1.0, pscale(st, 0.3))], "感電・気絶")
    b0 = padd(_arm("r", -150, 0, 40, -60), _arm("l", -60, 0, 50, -90), P(head=(14, 30, 0), torso=(6, 20, 0), jaw=(46, 0, 0)))
    b1 = padd(_arm("r", -60, 0, 60, -100), _arm("l", -160, 0, 30, -40), P(head=(-20, -30, 10), torso=(-6, -20, 0), jaw=(50, 0, 0)))
    out["burn_flail"] = oneshot("burn_flail", 1.4, [(0.15, b0), (0.4, b1), (0.65, pmirror(b0)), (0.9, pmirror(b1)),
                                                    (1.15, pscale(b0, 0.3))], "燃えてもがく")
    uv = padd(_both_arms(-120, -20, -110), P(head=(14, 40, 0), neck=(6, 10, 0), torso=(-10, 14, 0), root_pos=(0, 0, 1.0),
                                             jaw=(30, 0, 0)))
    out["uv_recoil"] = oneshot("uv_recoil", 0.9, [(0.1, uv), (0.5, padd(uv, P(head=(0, -10, 0)))), (0.75, pscale(uv, 0.3))],
                               "UV にひるむ")
    out["alert"] = oneshot("alert", 0.8, [
        (0.15, P(head=(-15, 30, 0), neck=(-6, 10, 0), jaw=(30, 0, 0))),
        (0.4, padd(P(head=(-10, 0, 0), chest=(-8, 0, 0), jaw=(44, 0, 0)), _both_arms(-30, 20, -20))),
        (0.62, P(head=(-4, 0, 0), jaw=(16, 0, 0)))], "気づいて振り向く")
    sv = padd(P(torso=(-16, 0, 0), chest=(-12, 0, 0), head=(-24, 0, 10), jaw=(44, 0, 0), root_pos=(0, 0, 0.6)),
              _arm("r", -60, 0, 60, -20), _arm("l", -30, 0, 40, -30))
    out["sever_recoil"] = oneshot("sever_recoil", 0.8, [(0.06, sv), (0.2, padd(pscale(sv, 0.8), P(head=(0, 0, -16)))),
                                                        (0.45, pscale(sv, 0.3))], "部位を失ってのけぞる")
    kk = padd(P(torso=(30, 0, 0), chest=(16, 0, 0), head=(10, 0, 0), jaw=(30, 0, 0), root_pos=(0, 0.6, 2.5)),
              _both_arms(-60, 20, -20), _both_legs(20, 20))
    out["kicked"] = oneshot("kicked", 0.9, [(0.08, kk), (0.35, padd(pscale(kk, 0.6), P(torso=(-10, 0, 0)))),
                                            (0.65, pscale(kk, 0.2))], "蹴り飛ばされる")
    missing = sorted(set(REG.ZOMBIE_ONESHOTS) - set(out))
    if missing:
        raise ValueError(f"one-shot animations missing: {missing}")
    return [out[k] for k in REG.ZOMBIE_ONESHOTS]


# ===========================================================================
#  19. 能力の段階 ab_<能力>_<段階>（nr:ability がその値の間だけ流れる）と ab_<能力>（anim=True）
# ===========================================================================
#  「体ごと」の段階（AB_FULL）は全身の姿勢を自分で持つ: その間、移動のコントローラは空の状態（owned）へ
#  移って足し算が二重にならない（pre_animation の v.nr_abfull）。それ以外は今の動きに足す上半身の重ね。
AB_FULL = {"ankle_grab.lurk", "ankle_grab.grab", "pounce_pin.pin", "ceiling_ambush.hang", "ceiling_ambush.drop",
           "dodge.dodge", "parkour_chase.vault", "play_dead.feign", "play_dead.rise", "debris_throw.lift",
           "long_leap.crouch", "long_leap.air", "hive_summon.birth", "boss_phases.roar", "blade_dash.crouch",
           "blade_dash.dash"}


def _alt(a: dict, b: dict, length: float, n: int = 2) -> list:
    """a と b を交互に並べたループのキー（n 往復、最後は a）。"""
    keys = []
    for i in range(2 * n + 1):
        keys.append((length * i / (2 * n), a if i % 2 == 0 else b))
    return keys


def build_abilities() -> List[Clip]:
    sk = design_skel()
    H = float(sk.L.t) / skel_scale(sk)
    out: Dict[str, Clip] = {}

    def ab(key: str, length: float, keys, loop=True, note: str = "", lerp: str = "catmullrom"):
        out[key] = keyed(f"ab_{key}", length, keys, loop=loop, kind="ability", note=note, lerp=lerp)

    # --- 盾: 弾かれて下がった左腕（普段の構えは ov_shield_guard が ability の none 状態で出す）
    low = padd(_arm("l", 18, 0, 10, -6, 20), P(torso=(0, -6, 0), head=(0, -6, 0)))
    ab("shield_block_lowered", 1.0, [(0.0, low), (0.5, padd(low, P(torso=(2, -4, 0)))), (1.0, low)], note="盾が下がる")
    # --- 足首掴み: 伏せて待つ / 腕を伸ばして掴み噛む（這いの全身）
    lurk = _final("crawl", 0.0, P(head=(0, 40, 0), neck=(-6, 0, 0)))
    ab("ankle_grab_lurk", 3.0, [(0.0, lurk), (1.5, _final("crawl", 0.05, P(head=(0, 40, 0), neck=(-6, 0, 0), chest=(1.5, 0, 0)))),
                                (3.0, lurk)], note="伏せて待つ")
    cs = crawl_stance(sk)
    grab_arm = {"arm_r": {"rot": [-176.0, 0.0, 10.0]}, "forearm_r": {"rot": [-6.0, 0.0, 0.0]}, "hand_r": {"rot": [24.0, 0.0, 0.0]}}
    g0 = {**copy.deepcopy(cs), **grab_arm}
    g0 = padd(g0, P(neck=(-12, 0, 0), head=(-10, 0, 0), jaw=(40, 0, 0)))
    g1 = padd(g0, P(neck=(16, 0, 0), head=(12, 0, 0), jaw=(-38, 0, 0), root_pos=(0, 0, -0.8)))
    ab("ankle_grab_grab", 0.6, _alt(g0, g1, 0.6, 1), note="足首を掴んで噛む")
    # --- 押さえ込み: 覆いかぶさって噛む
    pin = _g(padd(_crouch(1.1), P(torso=(50, 0, 0), chest=(10, 0, 0)), _both_arms(-50, 16, -20)))
    ab("pounce_pin_pin", 0.5, _alt(padd(pin, P(neck=(0, 0, 0), head=(-10, 0, 0), jaw=(40, 0, 0))),
                                   padd(pin, P(neck=(30, 0, 0), head=(20, 10, 0), jaw=(0, 0, 0))), 0.5, 1), note="押さえ込んで噛む")
    # --- 天井に逆さに張り付く / 落ちてくる
    hang = padd(P(root=(0, 0, 180), root_pos=(0, H, 0), head=(-40, 0, 0), neck=(-14, 0, 0), jaw=(24, 0, 0)),
                _both_arms(-168, 18, -30, 0), _both_legs(-40, 80, 10, -20))
    ab("ceiling_ambush_hang", 2.0, [(0.0, hang), (0.7, padd(hang, P(root=(0, 0, 4), head=(0, 16, 0)))),
                                    (1.4, padd(hang, P(root=(0, 0, -4), head=(0, -16, 0), jaw=(10, 0, 0)))), (2.0, hang)],
       note="天井に逆さに張り付いて待つ")
    land = _g(padd(_crouch(1.0), _both_arms(-60, 30, -30), P(torso=(30, 0, 0), jaw=(40, 0, 0))))
    ab("ceiling_ambush_drop", 0.8, [(0.0, hang),
                                    (0.2, padd(P(root=(0, 0, 90), root_pos=(0, H * 0.6, 0), jaw=(44, 0, 0)),
                                               _both_arms(-120, 60, -20), _both_legs(-40, 60))),
                                    (0.42, land), (0.8, {})], loop="hold_on_last_frame", note="落ちて襲う")
    # --- 横跳びで避ける
    ab("dodge_dodge", 0.55, [(0.0, {}), (0.08, _g(padd(_crouch(0.6), P(torso=(10, 0, -10))))),
                             (0.22, padd(P(root=(0, 0, 25), root_pos=(0, 2.5, 0), torso=(14, 0, 0)),
                                         _both_legs(-50, 70), _both_arms(-30, 50, -20))),
                             (0.38, _g(padd(_crouch(0.8), _both_arms(-20, 30, -20)))), (0.55, {})],
       loop="hold_on_last_frame", note="横跳び")
    # --- 障害物を乗り越える
    ab("parkour_chase_vault", 0.8, [(0.0, {}), (0.15, _g(padd(_crouch(0.5), _both_arms(-70, 10, -10), P(torso=(40, 0, 0))))),
                                    (0.35, padd(P(root_pos=(0, 5.0, 0), torso=(30, 0, 0)), _both_arms(-30, 10, 0),
                                                _leg("r", -80, 0, 30, 100), _leg("l", -70, 0, 20, 110))),
                                    (0.55, _g(padd(_crouch(0.6), _both_arms(-40, 20, -20)))), (0.8, {})],
       loop="hold_on_last_frame", note="乗り越え")
    # --- 狂乱: 腕を振り回し頭を振る
    f0 = padd(_arm("r", -150, 0, 40, -40), _arm("l", -60, 0, 30, -70), P(head=(0, 20, 10), jaw=(50, 0, 0), torso=(10, 10, 0)))
    f1 = padd(_arm("r", -50, 0, 20, -80), _arm("l", -140, 0, 40, -30), P(head=(6, -20, -10), jaw=(12, 0, 0), torso=(12, -10, 0)))
    ab("frenzy_frenzy", 0.6, [(0.0, f0), (0.15, f1), (0.3, pmirror(f0)), (0.45, pmirror(f1)), (0.6, f0)], note="狂乱")
    # --- 死んだふり / 跳ね起き
    ab("play_dead_feign", 1.0, [(0.0, _final("back"))], note="死体のふり")
    rise = build_rise("ab_play_dead_rise", 0.75, from_name="back")
    rise.kind, rise.loop = "ability", "hold_on_last_frame"
    out["play_dead_rise"] = rise
    # --- 喉の袋を膨らませて遠吠え
    inf = padd(P(head=(-30, 0, 0), neck=(-14, 0, 0), chest=(-10, 0, 0), jaw=(4, 0, 0)), _both_arms(10, 20, -10))
    ab("howl_alarm_inflate", 1.0, [(0.0, {}), (0.5, padd(pscale(inf, 0.6), P(throat_sac_scl=(1.5, 1.5, 1.5)))),
                                   (1.0, padd(inf, P(throat_sac_scl=(2.2, 2.2, 2.2))))], loop="hold_on_last_frame",
       note="喉の袋が膨らむ")
    howl = padd(P(head=(-40, 0, 0), neck=(-20, 0, 0), jaw=(62, 0, 0), chest=(-12, 0, 0)), _both_arms(30, 40, -10))
    ab("howl_alarm_howl", 0.8, _alt(padd(howl, P(throat_sac_scl=(2.0, 2.0, 2.0))),
                                    padd(howl, P(throat_sac_scl=(2.4, 2.4, 2.4), jaw=(4, 0, 0), head=(0, 0, 4))), 0.8, 2),
       note="遠吠え")
    # --- 瓦礫をもぎ取って頭上へ
    ab("debris_throw_lift", 1.2, [(0.0, {}), (0.4, _g(padd(_crouch(1.0), _both_arms(-40, 10, -10), P(torso=(40, 0, 0))))),
                                  (0.8, _g(padd(_crouch(0.3), _both_arms(-120, 12, -30)))),
                                  (1.2, padd(_both_arms(-180, 14, -50), P(torso=(-12, 0, 0), chest=(-8, 0, 0), jaw=(20, 0, 0))))],
       loop="hold_on_last_frame", note="瓦礫を掲げる")
    # --- 起爆までの震え（式の細かい震え）
    out["detonate_fuse"] = expr_clip("ab_detonate_fuse", {
        "torso": {"rot": [_jit(7300, 4), _jit(8100, 5, 20), _jit(9100, 4)],
                  "scl": [f"1 + 0.05 * math.abs(math.sin(q.life_time * 1600))", 1.0, f"1 + 0.05 * math.abs(math.sin(q.life_time * 1600))"]},
        "chest": {"rot": [f"-8 + {_jit(8800, 4)}", _jit(7700, 4), _jit(8300, 3, 60)]},
        "head": {"rot": [f"-20 + {_jit(9300, 6)}", _jit(8700, 8, 30), _jit(7900, 6)]},
        "jaw": {"rot": [f"30 + {_jit(9900, 10)}", 0, 0]},
        "arm_r": {"rot": [f"-20 + {_jit(8100, 6)}", 0, f"40 + {_jit(7700, 6)}"]},
        "arm_l": {"rot": [f"-20 + {_jit(8500, 6, 45)}", 0, f"-40 + {_jit(9300, 6)}"]},
    }, note="起爆までの震え")
    out["detonate_fuse"].kind = "ability"
    # --- 大跳躍: しゃがみ / 空中
    ab("long_leap_crouch", 0.5, [(0.0, {}), (0.5, _g(padd(_crouch(1.1), _both_arms(40, 20, -20),
                                                          P(torso=(34, 0, 0), head=(-24, 0, 0), jaw=(20, 0, 0)))))],
       loop="hold_on_last_frame", note="踏み切りのしゃがみ")
    air = padd(_both_arms(-110, 70, -20), _both_legs(20, 40), P(torso=(20, 0, 0), head=(-16, 0, 0), jaw=(40, 0, 0)))
    ab("long_leap_air", 1.0, [(0.0, air), (0.5, padd(air, _both_arms(-10, 6, 0))), (1.0, air)], note="空中")
    # --- 詠唱: 両腕を広げて掲げる
    ch = padd(_both_arms(-100, 80, -20), P(hand_r=(-30, 0, 0), hand_l=(-30, 0, 0), head=(-30, 0, 0), chest=(-8, 0, 0)))
    ab("reanimate_chant", 2.0, [(0.0, padd(ch, P(jaw=(10, 0, 0), torso=(0, 0, 4)))), (0.5, padd(ch, P(jaw=(30, 0, 0)))),
                                (1.0, padd(ch, P(jaw=(10, 0, 0), torso=(0, 0, -4)))), (1.5, padd(ch, P(jaw=(32, 0, 0)))),
                                (2.0, padd(ch, P(jaw=(10, 0, 0), torso=(0, 0, 4))))], note="詠唱")
    # --- 胞子を噴く（身震い）
    v0 = padd(P(chest=(-8, 0, 3), jaw=(30, 0, 0), torso_scl=(1.06, 1.0, 1.06)), _both_arms(-10, 30, -10))
    ab("spore_cloud_vent", 0.4, _alt(v0, padd(v0, P(chest=(0, 0, -6), torso=(3, 0, 0))), 0.4, 2), note="胞子を噴く")
    # --- 激昂の咆哮（一度）
    roar = padd(P(torso=(16, 0, 0), chest=(6, 0, 0), neck=(14, 0, 0), jaw=(64, 0, 0)), _both_arms(40, 30, -30))
    ab("enrage_unarmored_roar", 1.6, [(0.0, {}), (0.3, padd(P(chest=(-12, 0, 0), head=(-20, 0, 0), jaw=(10, 0, 0)), _both_arms(10, 20, -10))),
                                      (0.6, roar), (1.0, padd(roar, P(head=(0, 0, 5)))), (1.6, roar)],
       loop="hold_on_last_frame", note="激昂の咆哮")
    # --- 長い腕で引き寄せて噛む
    dr = padd(_arm("r", -70, 0, 4, -90, 24), P(torso=(-6, -6, 0)))
    ab("long_grab_drag_drag", 0.8, _alt(padd(dr, P(jaw=(40, 0, 0), neck=(0, 0, 0))),
                                        padd(dr, P(jaw=(0, 0, 0), neck=(20, 0, 0), head=(12, 0, 0))), 0.8, 1), note="引き寄せて噛む")
    # --- UV で焼ける: 腕で目を覆って身をよじる
    uv = padd(_both_arms(-125, -25, -110), P(head=(20, 0, 0), jaw=(30, 0, 0)))
    ab("uv_weak_burn", 0.8, _alt(padd(uv, P(head=(0, 25, 0), torso=(6, 15, 0))), padd(uv, P(head=(0, -25, 0), torso=(6, -15, 0))),
                                 0.8, 1), note="腕で目を覆って身をよじる")
    # --- 天を仰いで叫ぶ（夜の追跡の呼び声）
    call = padd(P(head=(-42, 0, 0), neck=(-26, 0, 0), jaw=(70, 0, 0), chest=(-14, 0, 0)), _both_arms(30, 30, -10))
    ab("chase_call_call", 1.0, _alt(call, padd(call, P(jaw=(-6, 0, 0), head=(0, 0, 3))), 1.0, 3), note="天を仰いで叫ぶ")
    # --- 透明化中の忍び寄り
    cl_ = padd(P(torso=(10, 0, 0), neck=(10, 0, 0), head=(-10, 0, 0)), _both_arms(-20, 10, -20))
    ab("shadow_cloak_cloaked", 3.0, [(0.0, cl_), (1.5, padd(cl_, P(head=(0, 12, 0), torso=(0, 0, 2)))), (3.0, cl_)],
       note="透明化中の忍び寄り")
    # --- 背中の袋から産み落とす（身をかがめて波打つ）
    birth = _g(padd(_crouch(1.0), P(torso=(60, 0, 0), chest=(10, 0, 0), head=(20, 0, 0), jaw=(30, 0, 0)), _both_arms(-60, 20, -10)))
    ab("hive_summon_birth", 1.6, _alt(birth, padd(birth, P(chest=(-8, 0, 0), torso_scl=(1.08, 1.04, 1.1), jaw=(10, 0, 0))), 1.6, 1),
       note="背中の袋が裂ける")
    # --- ボスの段階移行の咆哮（足を開いて両腕を広げる）
    br = _g(padd(_leg("r", -6, 0, 14, 10), _leg("l", -6, 0, 14, 10), _both_arms(-20, 60, -40),
                 P(chest=(-14, 0, 0), head=(-16, 0, 0), jaw=(68, 0, 0))))
    ab("boss_phases_roar", 1.0, _alt(br, padd(br, P(head=(0, 0, 4), chest=(0, 0, -3), jaw=(-6, 0, 0))), 1.0, 3), note="咆哮")
    # --- 腫瘍の袋を振り落とす（身をよじる）
    t0 = padd(P(torso=(0, 20, 0), chest=(0, 0, 10), jaw=(40, 0, 0)), _arm("r", -60, 0, 50, -40), _arm("l", -20, 0, 30, -20))
    ab("tumor_spawn_drop", 0.8, [(0.0, t0), (0.4, pmirror(t0)), (0.8, t0)], note="腫瘍を振り落とす")
    # --- 腕が生え戻る身震い
    rg = padd(P(chest=(-14, 0, 0), head=(-20, 0, 0), jaw=(40, 0, 0)), _both_arms(-10, 50, -10))
    ab("regenerate_regrow", 1.0, [(0.0, {}), (0.2, rg), (0.35, padd(rg, P(head=(0, 0, 6)))), (0.5, rg),
                                  (1.0, pscale(rg, 0.2))], loop="hold_on_last_frame", note="生え戻る身震い")
    # --- 刃の突進: かがむ / 駆け抜け（脚の走りも自分で持つ）
    ab("blade_dash_crouch", 0.4, [(0.0, {}), (0.4, _g(padd(_crouch(1.0), _both_arms(50, 20, -10), P(torso=(40, 0, 0), head=(-24, 0, 0)))))],
       loop="hold_on_last_frame", note="刃を構えてかがむ")
    g = Gait(**{**loco_gaits()["sprint"]["run"].__dict__})
    g.upper = make_upper(dict(arms=dict(rx=50, A=6, lag=0.06, rz=24, fore=-10, foreA=4, hand=-10, cancel=0.0),
                              head=dict(keep=0.95, nod=3, loll=2, neck=-8), jaw=(30, 6, 2)))
    g.lean = 34
    dash = timed(gait_clip("ab_blade_dash_dash", g, sk), 0.36)
    dash.loop, dash.kind = True, "ability"
    out["blade_dash_dash"] = dash
    # --- UV を砕く叫び
    sh = padd(P(chest=(-20, 0, 0), head=(-35, 0, 0), jaw=(70, 0, 0)), _both_arms(30, 40, -10), P(hand_r=(-40, 0, 0), hand_l=(-40, 0, 0)))
    ab("uv_shatter_shriek", 1.0, _alt(sh, padd(sh, P(head=(0, 0, 4), jaw=(-6, 0, 0))), 1.0, 3), note="胸を反らして叫ぶ")
    # --- 遠吠えで呼ぶ
    sv = padd(_both_arms(-150, 40, -30), P(head=(-40, 0, 0), neck=(-20, 0, 0), jaw=(66, 0, 0), chest=(-16, 0, 0)))
    ab("summon_volatiles_call", 1.2, _alt(sv, padd(sv, P(jaw=(-8, 0, 0), head=(0, 0, 4))), 1.2, 2), note="遠吠えで呼ぶ")
    # 名前の検査（zombie_animations が使う全段階 + ab_wall_climb は build_states が作る）
    need = {f"{k}_{ph}" for k, a in SPEC.ABILITY_VOCAB.items() for ph in a["phases"]}
    missing = sorted(need - set(out))
    if missing:
        raise ValueError(f"ability phase animations missing: {missing}")
    return [out[k] for k in sorted(out)]


def build_guard() -> Clip:
    """盾持ち（shield_block）の普段の構え: 左の前腕の盾を胸の前へ（ability の none 状態で v.nr_guard 倍）。"""
    return keyed("ov_shield_guard", 1.0, [(0.0, padd(_arm("l", -64, 0, 14, -84, 10), P(torso=(0, -4, 0))))], loop=True,
                 note="盾を構える")


# ===========================================================================
#  20. ちぎれた部位 nr:gib（空中の回転 nr:spin・寝姿 nr:rest・裏返し nr:side・動く間の血の尾）
# ===========================================================================
#  ジオメトリ（nr_rig.extract_gibs）は p_* の各ボーンの pivot が部位の重心 (0,0,0)。エンティティの原点は
#  当たり箱の底（床）なので、寝姿は「回したあとのいちばん低い点が床に来る」高さへ持ち上げる。
#  持ち上げ量は基準の体で部位・寝姿・裏表ごとに計算し、種類の大きさの倍率 v.gs（nr:ztype から）を掛ける
#  （汎用の肉片 p_guts.. は種類に依らないので倍率なし）。
GIB_SPINS = {1: (720, 0, 0), 2: (0, 0, 720), 3: (540, 360, 0), 4: (0, 420, 600), 5: (300, 0, 200),
             6: (900, 600, 300), 7: (200, 800, 100)}          # nr:spin -> 度/秒（x, y, z）
GIB_RESTS = {0: (8.0, 0.0, 90.0), 1: (-6.0, 0.0, -90.0), 2: (90.0, 20.0, 0.0), 3: (-90.0, -30.0, 0.0)}
_GIB_GEO: Dict[str, object] = {}


def _gib_models(build: dict, key: str):
    if key not in _GIB_GEO:
        m, _r = bare_rig("gib_" + key, build)
        if not m.tex_w:                    # 形だけ欲しいので大きなアトラスに詰める（大きな体は 512 に入らない）
            m.pack(size=(2048, 2048))
        _GIB_GEO[key] = RIG.extract_gibs(m, key, uv_check=False)
    return _GIB_GEO[key]


def _part_points(model, part: str) -> Optional[np.ndarray]:
    for b in model.bones:
        if b.name == part and b.cubes:
            return np.concatenate([(RIG.cube_matrix(c) @ RIG.cube_corners(c).T).T[:, :3] for c in b.cubes])
    return None


def gib_lifts(model) -> Dict[str, dict]:
    """{部位: {"r": 半径, (寝姿, 裏表): 持ち上げ量}}（単位）。"""
    out = {}
    for part in [b.name for b in model.bones]:
        pts = _part_points(model, part)
        if pts is None:
            continue
        d = {"r": float(np.linalg.norm(pts, axis=1).max())}
        for rest, (rx, ry, rz) in GIB_RESTS.items():
            for side in (0, 1):
                R = rot(rx, ry + 180.0 * side, rz)
                d[(rest, side)] = float(-(pts @ R.T)[:, 1].min())
        out[part] = d
    return out


def gib_scales() -> Dict[int, float]:
    """nr:ztype -> 部位の大きさの倍率（基準の体に対する持ち上げ量の比の中央値）。"""
    ref = gib_lifts(_gib_models(REF_BUILD, "ref"))
    out = {}
    for z in SPEC.ZOMBIES:
        lz = gib_lifts(_gib_models(rig_build(z), z["key"]))
        ratios = [lz[p][k] / ref[p][k] for p in ref if p in lz for k in ref[p] if k != "r" and ref[p][k] > 0.3]
        out[int(SPEC.ztype(z["key"]))] = round(float(np.median(ratios)) * 20) / 20 if ratios else 1.0
    return out


def _chain(var: str, table: Dict[int, float], default: float) -> str:
    """{値: 結果} を 3 項演算の連鎖に（同じ結果の値はまとめる）。"""
    groups: Dict[float, List[int]] = {}
    for k, v in sorted(table.items()):
        groups.setdefault(float(v), []).append(int(k))
    expr = fmt(default)
    for v, ks in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if abs(v - default) < 1e-9:
            continue
        cond = " || ".join(f"{var} == {k}" for k in ks)
        expr = f"(({cond}) ? {fmt(v)} : {expr})"
    return expr


def build_gibs() -> List[Clip]:
    ref = gib_lifts(_gib_models(REF_BUILD, "ref"))
    gen = gib_lifts(RIG.build_generic_gibs(paint=False))
    parts = {**ref, **gen}
    out: List[Clip] = []
    # 空中: nr:spin の軸と速さで回る（重心のまわり）。少し持ち上げて床に潜りにくく
    spin = Clip("spin", 1.0, loop=True, prefix=GP, kind="gib", weight_arms=False, scale_pos=False, note="空中で回る")
    for p, d in parts.items():
        k = "v.gs * " if p in ref else ""
        spin.expr[p] = {"rot": ["math.mod(q.life_time * v.gsx, 360)", "math.mod(q.life_time * v.gsy, 360)",
                                "math.mod(q.life_time * v.gsz, 360)"],
                        "pos": [0, f"{k}{fmt(0.75 * d['r'])}", 0]}
    out.append(spin)
    # 寝姿 0..3（nr:side で裏返し = 長い軸のまわりに 180°）
    for rest, (rx, ry, rz) in GIB_RESTS.items():
        c = Clip(f"rest_{rest}", 1.0, loop=True, prefix=GP, kind="gib", weight_arms=False, scale_pos=False,
                 note=f"寝姿 {rest}")
        for p, d in parts.items():
            k = "v.gs * " if p in ref else ""
            l0, l1 = d[(rest, 0)], d[(rest, 1)]
            c.expr[p] = {"rot": [rx, f"{fmt(ry)} + v.gside * 180", rz],
                         "pos": [0, f"{k}(v.gside ? {fmt(l1)} : {fmt(l0)})", 0]}
        out.append(c)
    tr = fx_clip("trail", 0.12, [{"effect": "trail"}], note="動く間の血の尾")
    tr.prefix, tr.kind = GP, "gib"
    out.append(tr)
    return out


# ===========================================================================
#  21. アニメーションコントローラ（全 50 体で共通。短い名前は client_animations(z) が種類ごとに写す）
# ===========================================================================
def _state(anims=None, trans=None, blend: Optional[float] = None, particles=None, shortest: bool = True) -> dict:
    st: Dict[str, object] = {}
    if anims:
        st["animations"] = anims
    if particles:
        st["particle_effects"] = particles
    st["transitions"] = [{k: v} for k, v in (trans or [])]
    if blend:
        st["blend_transition"] = blend
        if shortest:
            st["blend_via_shortest_path"] = True
    return st


def ctrl_move() -> dict:
    """移動と体の状態: stand / gimp / crawl / crawl1 / drag / climb / stagger / down / rise / owned / dead_*。"""
    dead_by_pose = [(f"dead_{i}", f"v.nr_dead && v.nr_pose == {i}") for i in range(8)]
    dead_any = dead_by_pose + [("dead_0", "v.nr_dead")]
    dead_prone = [("dead_7", "v.nr_dead && v.nr_pose == 7"), ("dead_5", "v.nr_dead")]
    common = [("owned", "v.nr_abfull"), ("down", "v.nr_down"), ("drag", "v.nr_half"),
              ("crawl1", "v.nr_c1"), ("crawl", "v.nr_crawl"), ("climb", "v.nr_climb"),
              ("stagger", "v.nr_stag"), ("gimp", "v.nr_gimp")]

    def others(me, extra=()):
        return [(k, c) for k, c in common if k != me] + list(extra)

    stand_ok = ("stand", "!v.nr_abfull && !v.nr_down && !v.nr_crawl && !v.nr_climb && !v.nr_stag && !v.nr_gimp")
    walk3 = [{"idle": "1.0 - v.nr_mv"}, {"walk": "v.nr_mv * (1.0 - v.nr_run)"}, {"run": "v.nr_mv * v.nr_run"}]
    states = {
        "stand": _state(walk3, dead_any + others("stand"), 0.3),
        "gimp": _state([{"gimp_idle": "1.0 - v.nr_mv"}, {"gimp": "v.nr_mv"}], dead_any + others("gimp", [stand_ok]), 0.3),
        "crawl": _state([{"crawl_idle": "1.0 - v.nr_mv"}, {"crawl_walk": "v.nr_mv * (1.0 - v.nr_run)"},
                         {"crawl_run": "v.nr_mv * v.nr_run"}],
                        dead_prone + others("crawl", [stand_ok]), 0.4),
        "crawl1": _state([{"crawl_idle": "1.0 - v.nr_mv"}, {"crawl1": "v.nr_mv"}],
                         dead_prone + [(k, c) for k, c in others("crawl1") if k != "crawl"]
                         + [("crawl", "v.nr_crawl && !v.nr_c1"), stand_ok], 0.3),
        "drag": _state([{"drag_idle": "1.0 - v.nr_mv"}, {"drag": "v.nr_mv"}],
                       [("dead_half", "v.nr_dead"), ("owned", "v.nr_abfull"), ("crawl", "!v.nr_half && v.nr_crawl"),
                        ("down", "!v.nr_half && v.nr_down"), ("stand", "!v.nr_half && !v.nr_crawl && !v.nr_down")], 0.3),
        "climb": _state(["climb"], dead_any + others("climb", [stand_ok]), 0.25),
        "stagger": _state(["stagger"], dead_any + others("stagger", [stand_ok]), 0.25),
        "down": _state(["down"], [("dead_down", "v.nr_dead"), ("owned", "v.nr_abfull"), ("drag", "v.nr_half"),
                                  ("crawl", "v.nr_crawl && !v.nr_down"), ("rise", "!v.nr_down")], 0.12),
        "rise": _state(["rise"], dead_any + [("owned", "v.nr_abfull"), ("down", "v.nr_down"), ("drag", "v.nr_half"),
                                             ("crawl", "v.nr_crawl"), ("stand", "q.all_animations_finished || q.state_time > 1.6")],
                       0.1),
        "owned": _state(None, dead_any + [("down", "!v.nr_abfull && v.nr_down"), ("drag", "!v.nr_abfull && v.nr_half"),
                                          ("crawl", "!v.nr_abfull && v.nr_crawl"),
                                          ("stand", "!v.nr_abfull && !v.nr_down && !v.nr_crawl")], 0.2),
    }
    revive = [("stand", "!v.nr_dead")]
    for i in range(8):
        states[f"dead_{i}"] = _state([f"dead_{i}"], revive, 0.2)
        states[f"held_{i}"] = _state([f"dead_{i}"], revive)
    states["dead_half"] = _state(["dead_half"], revive, 0.2)
    states["dead_down"] = _state(["dead_down"], revive, 0.15)
    held = [(f"held_{i}", f"v.nr_dead && v.nr_pose == {i}") for i in range(8)] + [("held_0", "v.nr_dead")]
    states = {"init": _state(None, held + common + [("stand", "1.0")]), **states}
    return {"initial_state": "init", "states": states}


def ctrl_alive() -> dict:
    """生きている揺れ・標的を見る・被弾ののけぞり（死体・体ごとの能力の間は止める）。"""
    return {"initial_state": "live", "states": {
        "live": _state(["alive", {"look": "v.nr_look"}, "hurt"], [("still", "v.nr_dead || v.nr_abfull")], 0.2),
        "still": _state(None, [("live", "!v.nr_dead && !v.nr_abfull")], 0.3),
    }}


def ctrl_fx() -> dict:
    """燃えてもがく（q.is_on_fire）・感電（nr:shock。体のまわりの放電）。"""
    arcs = [{"effect": "arcs", "locator": "loc_chest"}]
    return {"initial_state": "calm", "states": {
        "calm": _state(None, [("shock", "v.nr_shock"), ("burning", "v.nr_fire")], 0.2),
        "shock": _state(["shock"], [("burning", "!v.nr_shock && v.nr_fire"), ("calm", "!v.nr_shock")], 0.1,
                        particles=arcs),
        "burning": _state([{"burning": "v.nr_upright ? 1.0 : 0.35"}], [("shock", "v.nr_shock"), ("calm", "!v.nr_fire")], 0.25),
    }}


FOUNTAIN_SCRIPT = {"up": "v.dx = 0; v.dy = 1; v.dz = 0; v.life = 1.4; v.size = 0.9; v.gore = 1;",
                   "down": "v.dx = 0; v.dy = -0.5; v.dz = -0.5; v.life = 1.2; v.size = 0.7; v.gore = 1;"}


def ctrl_part(part: str, levels, broken_anim: Optional[str] = None) -> dict:
    """部位の状態: 断面から滴る（bleed_stump）、切れた直後の数秒は噴水（blood_fountain）、折れた腕はぶら下がる。
    levels = [(状態名, 条件, ロケータ, 噴く向き or None)]（強い順）。読み込み直後（v.nr_age）と死体・炭化（v.nr_dry）は
    噴水を出さない。"""
    states: Dict[str, dict] = {}
    order = []
    for name, cond, loc, fdir in levels:
        bleed = [{"effect": "bleed", "locator": loc}]
        if fdir:
            order.append((f"{name}_new", f"{cond} && !v.nr_dry && !v.nr_dead && v.nr_age > 1.5", bleed +
                          [{"effect": "fountain", "locator": loc, "pre_effect_script": FOUNTAIN_SCRIPT[fdir]}], name))
        order.append((name, f"{cond} && !v.nr_dry", bleed, None))
        order.append((f"{name}_dry", f"{cond} && v.nr_dry", None, None))
    if broken_anim:
        order.append(("broken", f"v.nr_brk_{part}", None, None))
    any_cut = " || ".join(f"({c})" for _n, c, _l, _f in levels)
    order.append(("intact", f"!({any_cut})" + (f" && !v.nr_brk_{part}" if broken_anim else ""), None, None))
    for name, _cond, parts, settles_to in order:
        trans = []
        for other, ocond, _p, _s in order:
            if other == name:
                continue
            if settles_to is None and other.endswith("_new") and other[:-4] == name:
                continue                        # 落ち着いた断面から「切れた直後」へは戻らない
            if settles_to is not None and other == settles_to:
                trans.append((other, "q.state_time > 1.6"))
                continue
            if name.endswith("_new") is False and other.endswith("_new"):
                base = other[:-4]
                if name == base or name == f"{base}_dry":
                    continue
            trans.append((other, ocond))
        anims = [broken_anim] if (name == "broken" and broken_anim) else None
        states[name] = _state(anims, trans, 0.2, particles=parts)
    return {"initial_state": "intact", "states": states}


def ctrl_torso_extra() -> dict:
    """腹を裂かれて垂れた腸が揺れて滴る（nr:torso = gutted）。"""
    return {"initial_state": "closed", "states": {
        "closed": _state(None, [("gutted", "v.nr_gutted")], 0.3),
        "gutted": _state(["guts"], [("closed", "!v.nr_gutted")], 0.3,
                         particles=[{"effect": "drip", "locator": "loc_belly"}]),
    }}


def ctrl_trail() -> dict:
    """下半身に断面のある体が這うと血の跡を残す。"""
    return {"initial_state": "off", "states": {
        "off": _state(None, [("on", "v.nr_lowstump && v.nr_mv > 0.2 && !v.nr_dry && !v.nr_dead")]),
        "on": _state(["trail"], [("off", "!v.nr_lowstump || v.nr_mv <= 0.2 || v.nr_dry || v.nr_dead")]),
    }}


MAX_AB = 7


def ctrl_ability() -> dict:
    """nr:ability 1..7 → ab_1..ab_7（種類ごとに ability_states(z) の段階のアニメへ写す）。0 = 盾の構えなど普段の重ね。"""
    states = {"none": _state([{"guard": "v.nr_guard"}], [(f"ab_{i}", f"v.nr_ab == {i}") for i in range(1, MAX_AB + 1)], 0.2)}
    for i in range(1, MAX_AB + 1):
        tr = [("none", f"v.nr_ab != {i} && v.nr_ab == 0")] + [(f"ab_{j}", f"v.nr_ab == {j}") for j in range(1, MAX_AB + 1) if j != i]
        states[f"ab_{i}"] = _state([f"ab_{i}"], tr, 0.2)
    return {"initial_state": "none", "states": states}


ZCTRLS = {
    "move": ctrl_move, "alive": ctrl_alive, "fx": ctrl_fx,
    "arm_r": lambda: ctrl_part("ar", [("up", "v.nr_cut_ar_up", "loc_shoulder_r", "up"),
                                      ("lo", "v.nr_cut_ar_lo", "loc_elbow_r", "down")], "arm_r_broken"),
    "arm_l": lambda: ctrl_part("al", [("up", "v.nr_cut_al_up", "loc_shoulder_l", "up"),
                                      ("lo", "v.nr_cut_al_lo", "loc_elbow_l", "down")], "arm_l_broken"),
    "leg_r": lambda: ctrl_part("lr", [("up", "v.nr_cut_lr_up", "loc_hip_r", "down"),
                                      ("lo", "v.nr_cut_lr_lo", "loc_knee_r", "down")]),
    "leg_l": lambda: ctrl_part("ll", [("up", "v.nr_cut_ll_up", "loc_hip_l", "down"),
                                      ("lo", "v.nr_cut_ll_lo", "loc_knee_l", "down")]),
    "head": lambda: ctrl_part("hd", [("neck", "v.nr_neck", "loc_neck", "up"),
                                     ("skull", "v.nr_cracked", "loc_head", None),
                                     ("jaw", "v.nr_jawless", "loc_mouth", None)]),
    "torso": lambda: ctrl_part("to", [("half", "v.nr_half", "loc_waist", "down")]),
    "guts": ctrl_torso_extra, "trail": ctrl_trail, "ability": ctrl_ability,
}


def gib_controllers() -> dict:
    rests = [(f"rest_{i}", f"v.gspin == 0 && v.grest == {i}") for i in range(4)]
    states = {"fly": _state(["spin"], rests, 0.0)}
    for i in range(4):
        states[f"rest_{i}"] = _state([f"rest_{i}"], [("fly", "v.gspin > 0")] + [r for r in rests if r[0] != f"rest_{i}"],
                                     0.12)
    move = {"initial_state": "fly", "states": states}
    bleed = {"initial_state": "dry", "states": {
        "dry": _state(None, [("trail", "v.gbleed && v.gspin > 0"), ("drip", "v.gbleed && v.gspin == 0")]),
        "trail": _state(["trail"], [("dry", "!v.gbleed"), ("drip", "v.gspin == 0")]),
        "drip": _state(None, [("dry", "!v.gbleed"), ("trail", "v.gspin > 0")], particles=[{"effect": "bleed"}]),
    }}
    return {CG + "move": move, CG + "bleed": bleed}


# ===========================================================================
#  22. gen_nr_entities へ渡す client entity の中身（種類ごと）
# ===========================================================================
PARTICLE_SHORT = {"bleed": "nr:bleed_stump", "fountain": "nr:blood_fountain", "trail": "nr:blood_trail",
                  "drip": "nr:blood_drip", "arcs": "nr:shock_arcs"}
GIB_PARTICLE_SHORT = {"trail": "nr:blood_trail", "bleed": "nr:bleed_stump"}
CTRL_ORDER = ("move", "alive", "fx", "arm_r", "arm_l", "leg_r", "leg_l", "head", "torso", "guts", "trail", "ability")


def _zkey(z) -> dict:
    return z if isinstance(z, dict) else SPEC.zombie(z)


def ability_phase_map(z) -> Dict[int, str]:
    """nr:ability の値 -> そのアニメの完全な ID（ability_states(z) の順）。"""
    z = _zkey(z)
    out = {}
    for name, v in SPEC.ability_states(z).items():
        k, ph = name.split(".", 1)
        out[int(v)] = f"{ZP}ab_{k}_{ph}"
    return out


def full_body_values(z) -> List[int]:
    """「体ごと」の段階（AB_FULL）の nr:ability の値。"""
    z = _zkey(z)
    return sorted(int(v) for name, v in SPEC.ability_states(z).items() if name in AB_FULL)


def has_ability(z, key: str) -> bool:
    return key in SPEC.ability_keys(_zkey(z))


def client_animations(z) -> Dict[str, str]:
    """description.animations（短い名前 -> アニメ／コントローラの完全な ID）。共通のコントローラが使う
    短い名前は全種類に必ずある（無い能力の段階・盾の構えは animation.nr.z.none に写す）。"""
    z = _zkey(z)
    loco = z["locomotion"]
    out: Dict[str, str] = dict(SPEC.zombie_animations(z))
    out.update({
        "idle": f"{ZP}idle_{loco}", "walk": f"{ZP}walk_{loco}", "run": f"{ZP}run_{loco}",
        "gimp": f"{ZP}st_gimp", "gimp_idle": f"{ZP}st_gimp_idle",
        "crawl_idle": f"{ZP}idle_crawl", "crawl_walk": f"{ZP}walk_crawl", "crawl_run": f"{ZP}run_crawl",
        "crawl1": f"{ZP}st_crawl1", "drag": f"{ZP}st_drag", "drag_idle": f"{ZP}st_drag_idle",
        "climb": f"{ZP}ab_wall_climb" if has_ability(z, "wall_climb") else f"{ZP}st_climb",
        "stagger": f"{ZP}st_stagger", "down": f"{ZP}st_down", "rise": f"{ZP}st_rise",
        "dead_half": f"{ZP}dead_half", "dead_down": f"{ZP}dead_down",
        "alive": f"{ZP}ov_alive", "look": f"{ZP}ov_look", "hurt": f"{ZP}ov_hurt", "burning": f"{ZP}ov_burning",
        "shock": f"{ZP}ov_shock", "arm_r_broken": f"{ZP}ov_arm_r_broken", "arm_l_broken": f"{ZP}ov_arm_l_broken",
        "guts": f"{ZP}ov_guts", "trail": f"{ZP}fx_trail",
        "guard": f"{ZP}ov_shield_guard" if has_ability(z, "shield_block") else f"{ZP}none",
    })
    for i in range(8):
        out[f"dead_{i}"] = f"{ZP}dead_{i}"
    phases = ability_phase_map(z)
    for i in range(1, MAX_AB + 1):
        out[f"ab_{i}"] = phases.get(i, f"{ZP}none")
    for k in CTRL_ORDER:
        out[f"ctrl_{k}"] = CZ + k
    return out


def client_animate(z=None) -> List[str]:
    """scripts.animate（コントローラだけ。順番は重ねる順）。"""
    return [f"ctrl_{k}" for k in CTRL_ORDER]


_ZCONST_CACHE: Dict[str, dict] = {}


def _zconsts(z) -> dict:
    """種類ごとの定数（身長の倍率・猫背・周期の距離・寝た姿勢の床合わせ）。"""
    z = _zkey(z)
    if z["key"] in _ZCONST_CACHE:
        return _ZCONST_CACHE[z["key"]]
    b = rig_build(z)
    s = RIG.landmarks(b).t / REF_T
    sk = ref_skel("z_" + z["key"], b)
    ensure_vars(sk)
    ensure_cycles()
    cyc = LOCO_CYCLES[z["locomotion"]]
    LL = leg_len(sk) / s                                   # 正規化した脚の長さ
    k = LL / cyc["LL"]
    c = {"v.nr_s": round(s, 4), "v.nr_hn": round(float(z["hunch"]), 2),
         "v.nr_cw": round(cyc["walk"] * k * s, 4), "v.nr_cr": round(cyc["run"] * k * s, 4)}
    for var in GROUND_FITS:
        c[var] = sk.vars[var]
    _ZCONST_CACHE[z["key"]] = c
    return c


def client_initialize(z) -> List[str]:
    """scripts.initialize（Molang の行）。"""
    c = _zconsts(z)
    lines = [f"{k} = {fmt(v, 4)};" for k, v in c.items()]
    lines += ["v.nr_seed = math.random(0.0, 1.0);", "v.nr_ph = 0.0;", "v.nr_run = 0.0;", "v.nr_mv = 0.0;", "v.nr_age = 0.0;"]
    return lines


def _prop_is(prop: str, *vals) -> str:
    if len(vals) == 1:
        return f"q.property('{prop}') == '{vals[0]}'"
    return "(" + " || ".join(f"q.property('{prop}') == '{v}'" for v in vals) + ")"


def client_pre_animation(z) -> List[str]:
    """scripts.pre_animation（Molang の行）。プロパティを v.nr_* に落とす（rendering.md A2）。"""
    z = _zkey(z)
    full = full_body_values(z)
    abfull = " || ".join(f"v.nr_ab == {v}" for v in full) if full else "0.0"
    ensure_cycles()
    sc = STATE_CYCLES
    lines = [
        "v.nr_age = (v.nr_age ?? 0.0) + q.delta_time;",
        "v.nr_dead = " + _prop_is("nr:state", "dead") + ";",
        "v.nr_bd = v.nr_bd ?? (v.nr_dead && v.nr_age < 0.3);",
        "v.nr_pose = q.property('nr:pose');",
        "v.nr_ab = v.nr_dead ? 0.0 : q.property('nr:ability');",
        f"v.nr_abfull = !v.nr_dead && ({abfull});",
        "v.nr_down = " + _prop_is("nr:state", "down") + ";",
        "v.nr_climb = " + _prop_is("nr:state", "climb") + ";",
        "v.nr_stag = " + _prop_is("nr:state", "stagger") + ";",
        "v.nr_half = " + _prop_is("nr:torso", "halved") + ";",
        "v.nr_gutted = " + _prop_is("nr:torso", "gutted") + ";",
    ]
    for p, s_ in (("leg_r", "lr"), ("leg_l", "ll"), ("arm_r", "ar"), ("arm_l", "al")):
        lines += [f"v.nr_cut_{s_}_lo = " + _prop_is(f"nr:{p}", "cut_lower") + ";",
                  f"v.nr_cut_{s_}_up = " + _prop_is(f"nr:{p}", "cut_upper") + ";",
                  f"v.nr_brk_{s_} = " + _prop_is(f"nr:{p}", "broken") + ";",
                  f"v.nr_ok_{s_} = " + _prop_is(f"nr:{p}", "intact", "wounded") + ";"]
    lines += [
        # 脚が切れた・両脚が使えない・胴が真っ二つ → 這う（倒れている間は倒れのまま）
        "v.nr_crawl = !v.nr_dead && !v.nr_down && (" + _prop_is("nr:state", "crawl")
        + " || v.nr_half || v.nr_cut_lr_lo || v.nr_cut_lr_up || v.nr_cut_ll_lo || v.nr_cut_ll_up || (!v.nr_ok_lr && !v.nr_ok_ll));",
        "v.nr_c1 = v.nr_crawl && !v.nr_half && (v.nr_ok_lr != v.nr_ok_ll);",
        "v.nr_c1l = v.nr_ok_ll;",
        "v.nr_gimp = !v.nr_crawl && (v.nr_brk_lr || v.nr_brk_ll);",
        "v.nr_gimpl = v.nr_brk_ll;",
        "v.nr_lowstump = v.nr_half || v.nr_cut_lr_lo || v.nr_cut_lr_up || v.nr_cut_ll_lo || v.nr_cut_ll_up;",
        "v.nr_neck = " + _prop_is("nr:head", "severed", "crushed") + ";",
        "v.nr_jawless = " + _prop_is("nr:head", "jawless") + ";",
        "v.nr_cracked = " + _prop_is("nr:head", "cracked") + ";",
        "v.nr_dry = q.property('nr:burn') >= 3;",
        "v.nr_shock = !v.nr_dead && q.property('nr:shock') > 0;",
        "v.nr_fire = !v.nr_dead && q.is_on_fire;",
        "v.nr_upright = !v.nr_dead && !v.nr_crawl && !v.nr_down && !v.nr_abfull;",
        "v.nr_look = v.nr_upright || v.nr_crawl;",
        "v.nr_guard = q.property('nr:armor') >= 1 && v.nr_ok_al;",
        "v.nr_awr = v.nr_brk_ar ? 0.3 : 1.0;",
        "v.nr_awl = v.nr_brk_al ? 0.3 : 1.0;",
        "v.nr_limp = math.mod(q.property('nr:variant'), 2);",
        "v.nr_reach = q.property('nr:variant') >= 2;",
        "v.nr_tilt = q.property('nr:variant') == 1 ? 7.0 : (q.property('nr:variant') == 3 ? -6.0 : 0.0);",
        # 追うと走る（0.4 秒でなめらかに）・動いている量
        "v.nr_run = math.clamp((v.nr_run ?? 0.0) + (q.has_target ? 2.5 : -2.5) * q.delta_time, 0.0, 1.0);",
        "v.nr_mv = math.lerp(v.nr_mv ?? 0.0, math.clamp(q.ground_speed / 0.6, 0.0, 1.0), math.min(1.0, q.delta_time * 8.0));",
        # 歩みの位相（足が滑らないよう移動距離で進める。周期の距離は今の状態のもの）
        "v.nr_dm = q.modified_distance_moved;",
        "v.nr_dd = math.clamp(v.nr_dm - (v.nr_dm0 ?? v.nr_dm), 0.0, 0.6);",
        "v.nr_dm0 = v.nr_dm;",
        f"v.nr_cyc = v.nr_half ? {fmt(sc['drag'], 4)} * v.nr_s : (v.nr_c1 ? {fmt(sc['crawl1'], 4)} * v.nr_s : "
        f"(v.nr_crawl ? math.lerp({fmt(sc['crawl_walk'], 4)}, {fmt(sc['crawl_run'], 4)}, v.nr_run) * v.nr_s : "
        f"(v.nr_gimp ? {fmt(sc['gimp'], 4)} * v.nr_s : math.lerp(v.nr_cw, v.nr_cr, v.nr_run))));",
        "v.nr_ph = math.mod((v.nr_ph ?? 0.0) + v.nr_dd / math.max(0.05, v.nr_cyc), 4.0);",
    ]
    return lines


def client_particle_effects(z=None) -> Dict[str, str]:
    return dict(PARTICLE_SHORT)


def client_sound_effects(z=None) -> Dict[str, str]:
    return {}


def gib_client() -> dict:
    """nr:gib の client entity の中身（animations / animate / initialize / pre_animation / particle_effects）。"""
    sc = gib_scales()
    sx = {k: v[0] for k, v in GIB_SPINS.items()}
    sy = {k: v[1] for k, v in GIB_SPINS.items()}
    sz = {k: v[2] for k, v in GIB_SPINS.items()}
    anims = {"spin": GP + "spin", "trail": GP + "trail", "ctrl_move": CG + "move", "ctrl_bleed": CG + "bleed"}
    for i in range(4):
        anims[f"rest_{i}"] = f"{GP}rest_{i}"
    return {
        "animations": anims,
        "animate": ["ctrl_move", "ctrl_bleed"],
        "initialize": ["v.gs = 1.0;", "v.gst = -1.0;"],
        "pre_animation": [
            "v.gspin = q.property('nr:spin');",
            "v.grest = q.property('nr:rest');",
            "v.gside = q.property('nr:side');",
            "v.gbleed = q.property('nr:bleed');",
            f"v.gsx = {_chain('v.gspin', sx, 0.0)};",
            f"v.gsy = {_chain('v.gspin', sy, 0.0)};",
            f"v.gsz = {_chain('v.gspin', sz, 0.0)};",
            # 種類の大きさの倍率（nr:ztype が変わった時だけ引き直す）
            "v.gs = (v.gst == q.property('nr:ztype')) ? v.gs : " + _chain("q.property('nr:ztype')", sc, 1.0) + ";",
            "v.gst = q.property('nr:ztype');",
        ],
        "particle_effects": dict(GIB_PARTICLE_SHORT),
    }


# ===========================================================================
#  23. 組み立て・書き出し・検査
# ===========================================================================
DEAD_TIME = "v.nr_bd ? 10.0 : (q.anim_time + q.delta_time)"   # 死体で読み込まれたら最後の姿勢から


def build_all() -> Dict[str, List[Clip]]:
    """ファイル -> クリップ。順番が大事（移動の周期 → 状態 → …）。"""
    loco = build_locomotion()
    states = build_states()
    falls = build_falls()
    for c in falls:
        if c.name.startswith("dead_"):
            c.anim_time_update = DEAD_TIME
    move = loco + [c for c in states if c.name != "ab_wall_climb"] + falls + build_overlays() + [build_guard()]
    ability = [c for c in states if c.name == "ab_wall_climb"] + build_abilities()
    return {"move": move, "attack": build_attacks(), "ability": ability, "oneshot": build_oneshots(),
            "gib": build_gibs()}


def anim_docs(files: Dict[str, List[Clip]]) -> Dict[str, dict]:
    return {k: {"format_version": ANIM_FORMAT, "animations": {c.id: clip_json(c) for c in cl}} for k, cl in files.items()}


def ctrl_docs() -> Dict[str, dict]:
    z = {CZ + k: f() for k, f in ZCTRLS.items()}
    return {"z": {"format_version": CTRL_FORMAT, "animation_controllers": z},
            "gib": {"format_version": CTRL_FORMAT, "animation_controllers": gib_controllers()}}


def _strings(obj, out: list, where: str = ""):
    """JSON の中の文字列（Molang の候補）を全部集める。"""
    if isinstance(obj, str):
        out.append((where, obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _strings(v, out, f"{where}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _strings(v, out, f"{where}[{i}]")


def _balanced(s: str) -> bool:
    d = 0
    for ch in s:
        if ch in "([{":
            d += 1
        elif ch in ")]}":
            d -= 1
            if d < 0:
                return False
    return d == 0 and s.count("'") % 2 == 0


MOLANG_HINT = re.compile(r"\b(q|v|math|query|variable)\.|[()?:*/+<>=!&|]")


def _molang_ok(s: str) -> Optional[str]:
    """括弧の対応と nr_preview の構文解析で Molang を確かめる（エラーの説明 or None）。"""
    import nr_preview as NP
    if not _balanced(s):
        return "unbalanced parentheses/quotes"
    try:
        for part in s.split(";"):
            if part.strip():
                NP._parse(part.strip())
    except Exception as exc:  # noqa: BLE001
        return f"parse: {exc}"
    return None


def validate(adocs: Dict[str, dict], cdocs: Dict[str, dict], files: Dict[str, List[Clip]]) -> Tuple[List[str], List[str]]:
    """生成物の検査。(errors, notes) を返す。"""
    errs: List[str] = []
    notes: List[str] = []
    anims: Dict[str, dict] = {}
    for d in adocs.values():
        for aid, a in d["animations"].items():
            if aid in anims:
                errs.append(f"duplicate animation id {aid}")
            anims[aid] = a
    ctrls: Dict[str, dict] = {}
    for d in cdocs.values():
        ctrls.update(d["animation_controllers"])
    # 1) spec の全種類のアニメ・登録簿の一発もの
    for z in SPEC.ZOMBIES:
        for short, full in SPEC.zombie_animations(z).items():
            if full not in anims:
                errs.append(f"{z['key']}: zombie_animations {short} -> {full} not generated")
    for n in REG.ZOMBIE_ONESHOTS:
        if ZP + n not in anims:
            errs.append(f"registry one-shot {n} not generated")
    for n in REG.all_zombie_anim_names(SPEC):
        if ZP + n not in anims:
            errs.append(f"registry derived anim {n} not generated")
    # 2) 一発もの・攻撃: 加算で最初と最後のキーが 0（P3）
    for cl in (files["oneshot"], files["attack"]):
        for c in cl:
            ks = sorted(c.keys, key=lambda k: k[0])
            for t, p, _l in (ks[0], ks[-1]):
                for b, e in p.items():
                    for ch, v in e.items():
                        if not _is_zero(v, ch):
                            errs.append(f"{c.id}: key at {t:.2f}s is not zero ({b}.{ch}={v})")
            if c.loop:
                errs.append(f"{c.id}: one-shot must not loop")
    # 3) 種類ごとの短い名前: コントローラが使う名前が全部ある・指す先が全部ある
    used_by_ctrl: Dict[str, set] = {}
    for cid, c in ctrls.items():
        names = set()
        for st in c["states"].values():
            for a in st.get("animations", []):
                names.add(a if isinstance(a, str) else next(iter(a)))
        used_by_ctrl[cid] = names
    for z in SPEC.ZOMBIES:
        ca = client_animations(z)
        for short, full in ca.items():
            if full.startswith("controller."):
                if full not in ctrls:
                    errs.append(f"{z['key']}: {short} -> controller {full} missing")
            elif full not in anims:
                errs.append(f"{z['key']}: {short} -> {full} not generated")
        for cid in [ca[k] for k in client_animate(z)]:
            for n in used_by_ctrl.get(cid, ()):
                if n not in ca:
                    errs.append(f"{z['key']}: {cid} uses '{n}' which is not in client_animations")
        # nr:ability の値の割り当てとアニメの対応
        for name, v in SPEC.ability_states(z).items():
            k, ph = name.split(".", 1)
            if ca.get(f"ab_{v}") != f"{ZP}ab_{k}_{ph}":
                errs.append(f"{z['key']}: ab_{v} should map to ab_{k}_{ph}")
        if len(SPEC.ability_states(z)) > MAX_AB:
            errs.append(f"{z['key']}: more than {MAX_AB} ability phases")
    gc = gib_client()
    for cid in [gc["animations"][k] for k in gc["animate"]]:
        for n in used_by_ctrl.get(cid, ()):
            if n not in gc["animations"]:
                errs.append(f"gib: {cid} uses '{n}' which is not in gib_client animations")
    for short, full in gc["animations"].items():
        if full not in anims and full not in ctrls:
            errs.append(f"gib: {short} -> {full} missing")
    # 4) パーティクル・ロケータ
    reg_parts = set(REG.all_particle_ids())
    for short, pid in {**PARTICLE_SHORT, **GIB_PARTICLE_SHORT}.items():
        if pid not in reg_parts:
            errs.append(f"particle {short} -> {pid} is not in nr_registry.PARTICLES")
    for cid, c in ctrls.items():
        shorts = GIB_PARTICLE_SHORT if cid.startswith(CG) else PARTICLE_SHORT
        for sname, st in c["states"].items():
            for pe in st.get("particle_effects", []):
                if pe["effect"] not in shorts:
                    errs.append(f"{cid}.{sname}: particle short name {pe['effect']} not registered")
                loc = pe.get("locator")
                if loc and loc not in RIG.LOCATOR_BONES:
                    errs.append(f"{cid}.{sname}: locator {loc} is not an nr_rig locator")
    for aid, a in anims.items():
        shorts = GIB_PARTICLE_SHORT if aid.startswith(GP) else PARTICLE_SHORT
        for t, pe in (a.get("particle_effects") or {}).items():
            for e in (pe if isinstance(pe, list) else [pe]):
                if e["effect"] not in shorts:
                    errs.append(f"{aid}@{t}: particle short name {e['effect']} not registered")
                if e.get("locator") and e["locator"] not in RIG.LOCATOR_BONES:
                    errs.append(f"{aid}@{t}: locator {e['locator']} is not an nr_rig locator")
    # 5) ボーン名（§3 の骨格 + 部品の子ボーン。ゾンビのアニメ）・gib のボーン
    known = set(SPEC.RIG_BONES) | set(RIG.GORE_BONES) | {"throat_sac"}
    gib_bones = set(RIG.GIB_PARTS)
    for aid, a in anims.items():
        ok = gib_bones if aid.startswith(GP) else known
        bad = sorted(b for b in a.get("bones", {}) if b not in ok)
        if bad:
            errs.append(f"{aid}: unknown bones {bad}")
    # 6) Molang（括弧・構文）
    lines = []
    for z in SPEC.ZOMBIES[:1] + [SPEC.zombie("subject_zero")]:
        lines += [("pre_animation", s) for s in client_pre_animation(z)]
        lines += [("initialize", s) for s in client_initialize(z)]
    lines += [("gib.pre_animation", s) for s in gc["pre_animation"]]
    strs: List[Tuple[str, str]] = []
    _strings(anims, strs, "anims")
    for cid, c in ctrls.items():
        for sname, st in c["states"].items():
            for tr in st.get("transitions", []):
                for k, v in tr.items():
                    strs.append((f"{cid}.{sname}->{k}", v))
            for a in st.get("animations", []):
                if isinstance(a, dict):
                    for k, v in a.items():
                        strs.append((f"{cid}.{sname}.{k}", v))
            for pe in st.get("particle_effects", []):
                if "pre_effect_script" in pe:
                    strs.append((f"{cid}.{sname}.pre_effect_script", pe["pre_effect_script"]))
    checked = 0
    seen = set()
    for where, s in lines + strs:
        if where.endswith(("/effect", "/locator", "/lerp_mode")) or s in seen:
            continue
        if not MOLANG_HINT.search(s):
            continue
        seen.add(s)
        checked += 1
        why = _molang_ok(s)
        if why:
            errs.append(f"molang {where}: {why}: {s[:120]}")
    notes.append(f"Molang strings checked: {checked}")
    # 6b) アニメ・コントローラが読む変数は initialize / pre_animation で必ず作る（ゾンビ・gib）
    var_re = re.compile(r"\bv(?:ariable)?\.([a-z_][a-z0-9_]*)")
    q_re = re.compile(r"\bq(?:uery)?\.([a-z_][a-z0-9_]*)")
    z_set = {m for s in client_initialize(SPEC.ZOMBIES[0]) + client_pre_animation(SPEC.ZOMBIES[0])
             for m in re.findall(r"\bv\.([a-z_][a-z0-9_]*)\s*=(?!=)", s)}
    g_set = {m for s in gc["initialize"] + gc["pre_animation"] for m in re.findall(r"\bv\.([a-z_][a-z0-9_]*)\s*=(?!=)", s)}
    pre_fx = {"dx", "dy", "dz", "life", "size", "gore"}          # pre_effect_script がパーティクルへ渡す変数
    used_q = set()
    for where, s in strs + lines:
        is_gib = where.startswith(("anims/" + GP, CG, "gib."))
        have = g_set if is_gib else z_set
        for m in var_re.findall(s):
            if m not in have and m not in pre_fx:
                errs.append(f"variable v.{m} used in {where} is never set by initialize/pre_animation")
        used_q.update(q_re.findall(s))
    qmeta = os.path.join(os.path.dirname(TOOLS), "build_preview", "nr_research", "bedrock-samples", "metadata",
                         "molang_modules", "mojang-molang-queries.json")
    if os.path.exists(qmeta):
        known_q = set(re.findall(r'"query\.([a-z_0-9]+)"', open(qmeta, encoding="utf-8").read()))
        for qn in sorted(used_q - known_q):
            errs.append(f"unknown query q.{qn}")
        notes.append(f"queries used: {', '.join(sorted(used_q))}")
    # 7) 長さ・ループ
    for aid, a in anims.items():
        if a["animation_length"] <= 0:
            errs.append(f"{aid}: animation_length <= 0")
        if aid.startswith(ZP + "dead_") and a.get("loop") != "hold_on_last_frame":
            errs.append(f"{aid}: death pose must hold_on_last_frame")
    notes.append(f"animations {len(anims)} / controllers {len(ctrls)} / zombies {len(SPEC.ZOMBIES)}")
    return errs, notes


def floor_report(files: Dict[str, List[Clip]], lib: Dict[str, dict]) -> List[str]:
    """移動・寝た姿勢の床との関係（数字で）。設計の骨格での値。"""
    out = []
    for c in files["move"]:
        if not (c.name.startswith(("walk_", "run_", "idle_", "dead_", "st_"))):
            continue
        if c.name.startswith(("walk_", "run_", "idle_")):
            loco = c.name.split("_", 1)[1]
            sk = style_skel(loco)
        else:
            sk = design_skel()
        v = dict(sk.vars)
        v["v.nr_hn"] = sk.hunch
        times = [c.length * i / 12 for i in range(13)] if c.loop is not True else [c.length * i / 12 for i in range(12)]
        if c.name.startswith("dead_") or c.name in ("st_down",):
            times = [c.length]
        lows, feet = [], []
        skip = _HALF_SKIP if c.name in ("dead_6", "dead_half", "st_drag", "st_drag_idle") else ()
        for t in times:
            W = sk.world(eval_pose(lib, c.id, t, v))
            lows.append(sk.min_y(W, skip))
            if not c.name.startswith(("dead_", "st_drag", "st_crawl1")) and "crawl" not in c.name:
                feet.append(min(_bone_min_y(sk, W, "foot_r"), _bone_min_y(sk, W, "foot_l")))
        msg = f"{c.name:16s} body_min {min(lows):6.2f} .. {max(lows):6.2f}"
        if feet:
            msg += f"  foot_min {min(feet):6.2f}"
        out.append(msg)
    return out


def write_all(adocs: Dict[str, dict], cdocs: Dict[str, dict]) -> List[str]:
    paths = []
    for k, d in adocs.items():
        pth = os.path.join(ANIM_DIR, ANIM_FILES[k])
        write_json(pth, d)
        paths.append(pth)
    for k, d in cdocs.items():
        pth = os.path.join(CTRL_DIR, CTRL_FILES[k])
        write_json(pth, d)
        paths.append(pth)
    return paths


# ===========================================================================
#  24. 確認画像（書き出した JSON を nr_preview のアニメ評価器で素体のリグに当てて描く）
# ===========================================================================
QA_ROWS = ["walk_shamble", "run_shamble", "walk_limp", "walk_sprint", "run_sprint", "walk_brute", "walk_stalk",
           "run_leap", "walk_waddle", "walk_lurch", "walk_scuttle", "walk_knuckle",
           "atk_swipe", "atk_slam", "atk_pounce", "atk_claw_flurry",
           "walk_crawl", "st_crawl1", "st_drag"]
QA_DEATHS = [f"dead_{i}" for i in range(8)] + ["dead_half", "dead_down"]
QA_PROPS = {"st_crawl1": {"nr:leg_l": "cut_upper"}, "st_drag": {"nr:torso": "halved"},
            "dead_6": {"nr:torso": "halved"}, "dead_half": {"nr:torso": "halved"}, "dead_4": {"nr:head": "severed"},
            "walk_crawl": {"nr:leg_r": "cut_lower", "nr:leg_l": "cut_upper"}}


def _qa_build_for(name: str) -> Tuple[str, dict, Skel]:
    loco = name.split("_", 1)[1] if name.startswith(("walk_", "run_", "idle_")) else ""
    if loco in SPEC.LOCOMOTION_VOCAB:
        return "style_" + loco, style_build(loco), style_skel(loco)
    return "ref", dict(REF_BUILD), design_skel()


def qa_sheet(lib: Dict[str, dict], out_path: str, cols: int = 5, size: int = 150) -> str:
    """frame strips: 移動の型・攻撃 4 種・這い・死体の姿勢を 1 枚に。"""
    import nr_preview as NP
    items = []
    for name in QA_ROWS:
        aid = ZP + name
        a = lib[aid]
        L = float(a["animation_length"])
        times = [L * i / cols for i in range(cols)] if a.get("loop") is True else [L * i / (cols - 1) for i in range(cols)]
        key, build, sk = _qa_build_for(name)
        var = dict(sk.vars)
        items += qa_frames(lib, aid, times, key, build, views=("three_quarter",), size=size, variables=var,
                           properties=QA_PROPS.get(name), label=name)
    for name in QA_DEATHS:
        aid = ZP + name
        L = float(lib[aid]["animation_length"])
        key, build, sk = _qa_build_for(name)
        items += qa_frames(lib, aid, [L], key, build, views=("three_quarter",), size=size, variables=dict(sk.vars),
                           properties=QA_PROPS.get(name), label=name)
    img = NP.contact_sheet(items, cols=cols, title="NIGHT RUNNER zombie animations (QA)")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)
    return out_path


# ===========================================================================
#  25. 入口
# ===========================================================================
def main(argv=None) -> int:
    import time
    ap = argparse.ArgumentParser(description="NIGHT RUNNER: ゾンビのアニメーションとアニメコントローラ")
    ap.add_argument("--qa", action="store_true", help="確認画像を build_preview/nightrunner/zombie_anim/ に描く")
    ap.add_argument("--floor", action="store_true", help="床との関係の数字の表を出す")
    ap.add_argument("--no-write", action="store_true", help="書き出さずに検査だけ")
    a = ap.parse_args(argv)
    t0 = time.time()
    files = build_all()
    adocs = anim_docs(files)
    cdocs = ctrl_docs()
    errs, notes = validate(adocs, cdocs, files)
    if not a.no_write:
        for pth in write_all(adocs, cdocs):
            print(f"  wrote {os.path.relpath(pth, os.path.dirname(TOOLS))} ({os.path.getsize(pth) // 1024} KB)")
    counts = {k: len(v) for k, v in files.items()}
    print(f"[{PRODUCER}] clips {counts} / {'; '.join(notes)} / {time.time() - t0:.1f}s")
    lib = {aid: an for d in adocs.values() for aid, an in d["animations"].items()}
    if a.floor:
        print("\n".join(floor_report(files, lib)))
    if a.qa or PREVIEW:
        pth = qa_sheet(lib, os.path.join(QA_DIR, "zombie_anim_qa.png"))
        print(f"  QA: {os.path.relpath(pth, os.path.dirname(TOOLS))}")
    if errs:
        print(f"[{PRODUCER}] {len(errs)} error(s):")
        for e in errs[:80]:
            print("  NG", e)
        return 1
    print(f"[{PRODUCER}] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
