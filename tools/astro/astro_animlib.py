# -*- coding: utf-8 -*-
"""アストロ・ナノギア — 全身モーション（playanimation）の記法と、全形態で共通のモーション。

■ 書き方（planets/<key>/body.py の BODY_ANIMS と、この下の library()）
    from astro_animlib import H, P, anim, aim, wield, dirv, flip, FWD, UP, DOWN, LEFT, RIGHT, BACK

    BODY_ANIMS = {
        "combo1": anim(0.5, {
            0.0: H,                                            # H = 自然体（バニラの持ち姿勢）
            0.08: P(rA=wield(blade=dirv(r=0.8, f=-0.5), arm=dirv(r=1, u=-0.3)), b=(0, 35, 0)),
            0.20: P(rA=wield(blade=dirv(f=1, r=-0.2), edge=LEFT), b=(0, -10, 0), lL=(-25, 0, 0),
                    ground=True),
            0.50: H,
        }),
    }

  キー（秒 → 姿勢）は「その時刻の全身の姿勢（絶対値）」。書かなかった部位は自然体。
  前の姿勢を土台に一部だけ変えるなら P(前の姿勢, rA=...)。
  キーの間は統合版と同じ catmullrom で補間される（武器で解いた腕は回転のまま補間されるよう、
  大きく回る区間に自動でキーを足す。腕のオイラー角は隣のキーと連続な表し方に揃え（_relift）、
  catmullrom で実際に補間して回転からのずれ・速すぎる所にだけ間隔 MIN_DT 以上のキーを足す（_refine）。
  書き出した腕は 1/120 秒ごとに角速度を検査する（gen_astro_anim.motion_check / arm_speeds）。

■ 部位（統合版の回転 [rx, ry, rz]、度。hd_space の規則）
    rA / lA  右腕 / 左腕（体の子）  rx 負 = 前へ上がる、rz 正 = 右腕が外へ開く（左腕は負で外）
    b        体（首の付け根 (0,24,0) まわり）  rx 正 = 前かがみ、ry 正 = 右（-X）を向く
    w        腰（(0,12,0) まわり。上半身ごと曲げる）  rx 正 = 前へ倒れる
    h        頭  rx 負 = 見上げる
    rL / lL  右脚 / 左脚  rx 負 = 前へ蹴り出す、rz 正 = 右脚が外へ
    root     全身（足元 (0,0,0) まわり）。宙返り・回転斬り
    root_pos 全身の位置 (x, y, z)（単位。y 負 = しゃがむ。z 負 = 前へ）
    ground=True  root_pos の y を「低い方の足の裏が地面 (y=0) に着く」高さにする（脚を開いた構え・膝つき）

■ 向き（体の空間: -Z が前、+Y が上、-X がプレイヤーの右）
    dirv(f=前, u=上, r=右) で作るのが分かりやすい。FWD BACK UP DOWN RIGHT LEFT は単位ベクトル。

■ 腕の指定（rA / lA に Euler の代わりに渡せる。体・腰のひねりは自動で打ち消す）
    aim(dir, twist=0)               腕（肩→拳）を dir へ向ける。twist は腕の軸まわりのひねり（度）
    wield(blade, arm=None, edge=None, roll=0)
                                    右手の武器の刃先を blade へ向ける（持ち方 astro_hold の手首の角度のまま）。
                                    腕は arm の向きにできるだけ近く（省略時は前下）、edge を渡すと
                                    「刃（武器の -Y）を edge へ向ける」方を優先する（斬撃は刃を進む向きへ）。
                                    惑星の武器の種類（sword, axe…）ごとに解くので、同じ指定で全種類に合う。

■ 種類（anim の kind）と、バニラとの足し合わせ（hyperdim の gen_hd_anim と同じ考え方）
    act   技・コンボ（コントローラ astro.act）。腕はバニラの持ち姿勢（右腕 -18°）・歩きの腕振り・
          攻撃の振り（attack_time）を打ち消して、書いた角度そのものになる
    pose  変身・解除（astro.pose）。持ち姿勢と歩きの腕振りを打ち消す（攻撃の振りはそのまま）
    move  機動・ホバー（astro.move / astro.pose）。持ち姿勢からの差分だけ足す（打ち消し無し。
          他のモーションと重なっても壊れないよう、腕は控えめに）
    一人称では体・頭・脚・全身は 0、腕は自然体からの回転を同じ軸まわりに 25%（fp_track。自然体の真反対に
    近い姿勢では 0 へ減らす。オイラー角の成分を 25% にすると ±360° の巻きが 90° のねじれになるので使わない）。

■ 公開 API
    H, P(*bases, **parts), anim(length, frames, kind="act", loop=False, blend=None)
    aim(dir, twist=0), wield(blade, arm=None, edge=None, roll=0), dirv(f, u, r), flip(...)
    resolve(spec, wkind="sword", name="", hold=None, cloud=None) -> Resolved
                                    部位ごとのトラック（絶対値の Euler）。cloud（武器の表面の点）を渡すと
                                    wield の腕を体に入らない向きへ回し、補間の途中で入るコマにキーを足す
    to_json(res) -> 統合版のアニメーション dict
    fp_track(res, part) -> {秒: (x, y, z)}   一人称の腕の値
    arm_speeds(res, part) / arm_speed_report(res)   catmullrom で見た腕の角速度と上限
    sample(res, t) / sample_parts(res, t)   その時刻の姿勢（三人称・物を持った自然体の上で）
    clip_depth(pose, cloud) -> (深さ px, 部位)   スーツを着た体への武器の入り込み
    describe(res) -> [str]          書いたキーごとの腕・刃先の向き（gen_astro_anim --describe）
    uses_wield(spec) -> bool
    library() -> {名前: spec}       共通モーション（DESIGN.md §4.6）
    TR                              astro_data.TRANSFORM を秒に（TR["weapon_form"] = 2.0 …）
    PREFIX = "animation.astro.p."
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import astro_common as AC  # noqa: E402,F401  (sys.path)
from astro_data import NS, TRANSFORM  # noqa: E402
from hd_holds import frame_axes  # noqa: E402
from hd_space import bone_local, euler, rot  # noqa: E402

PREFIX = f"animation.{NS}.p."

BONES = {"rA": "rightArm", "lA": "leftArm", "b": "body", "h": "head", "rL": "rightLeg",
         "lL": "leftLeg", "root": "root", "w": "waist"}
ORDER = ("root", "w", "b", "h", "rA", "lA", "rL", "lL")
SOLVE_ORDER = ("root", "w", "b", "h", "lA", "rL", "lL", "rA")    # 武器の腕は最後に（他の部位を見て避ける）
ARMS = ("rA", "lA")
REST = {"rA": (-18.0, 0.0, 0.0)}           # バニラの持ち姿勢（三人称で右手に物を持つ）
FPK = 0.25                                 # 一人称での腕の振れ幅
PIVOT = {"root": (0, 0, 0), "w": (0, 12, 0), "b": (0, 24, 0), "h": (0, 24, 0),
         "rA": (-5, 22, 0), "lA": (5, 22, 0), "rL": (-1.9, 12, 0), "lL": (1.9, 12, 0)}

FWD = (0.0, 0.0, -1.0)
BACK = (0.0, 0.0, 1.0)
UP = (0.0, 1.0, 0.0)
DOWN = (0.0, -1.0, 0.0)
RIGHT = (-1.0, 0.0, 0.0)
LEFT = (1.0, 0.0, 0.0)


def dirv(f=0.0, u=0.0, r=0.0):
    """前 f・上 u・右 r の向き（体の空間の単位ベクトル）。"""
    v = np.array([-r, u, -f], float)
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        raise ValueError("dirv: zero vector")
    return tuple(float(x) for x in v / n)


# ===========================================================================
#  記法
# ===========================================================================
H = {}


def P(*bases, **parts):
    """姿勢。bases（前の姿勢）を土台に parts で上書き。"""
    out = {}
    for b in bases:
        out.update(b)
    for k, v in parts.items():
        if k not in BONES and k not in ("root_pos", "ground"):
            raise KeyError(f"unknown part {k!r} (rA lA b h rL lL w root root_pos ground)")
        out[k] = v
    return out


class Aim:
    def __init__(self, d, twist=0.0):
        self.d = np.asarray(d, float) / np.linalg.norm(d)
        self.twist = float(twist)

    def __repr__(self):
        return f"aim({tuple(round(float(x), 3) for x in self.d)}, {self.twist})"


class Wield:
    def __init__(self, blade, arm=None, edge=None, roll=0.0):
        self.blade = np.asarray(blade, float) / np.linalg.norm(blade)
        self.arm = None if arm is None else np.asarray(arm, float) / np.linalg.norm(arm)
        self.edge = None if edge is None else np.asarray(edge, float) / np.linalg.norm(edge)
        self.roll = float(roll)

    def __repr__(self):
        f = lambda v: None if v is None else tuple(round(float(x), 3) for x in v)  # noqa: E731
        return f"wield({f(self.blade)}, arm={f(self.arm)}, edge={f(self.edge)}, roll={self.roll})"


def aim(d, twist=0.0):
    return Aim(d, twist)


def wield(blade, arm=None, edge=None, roll=0.0):
    return Wield(blade, arm, edge, roll)


def anim(length, frames, kind="act", loop=False, blend=None):
    """モーション 1 本。frames = {秒: 姿勢}。kind = act / pose / move。
    blend=False で終わりのブレンドをしない（一回転して終わる物。省略時は全身の 300° 以上の回転で自動）。"""
    if kind not in ("act", "pose", "move"):
        raise ValueError("kind must be act / pose / move")
    fr = {round(float(t), 3): dict(p) for t, p in frames.items()}
    if any(t < 0 or t > length + 1e-6 for t in fr):
        raise ValueError("key time outside 0..length")
    return {"length": float(length), "frames": fr, "kind": kind, "loop": bool(loop), "blend": blend}


def flip(t0, t1, turns=1.0, axis="x", centre=14.0, steps=8, tuck=True, base=None):
    """t0〜t1 秒で全身を重心（高さ centre）まわりに回すキーの dict（frames に足して使う）。
    axis="x" で前宙（turns 負で後ろ宙）、"y" で水平に回る、"z" で側宙。base は各キーの土台の姿勢。"""
    out = {}
    for i in range(steps + 1):
        s = i / steps
        ease = 0.5 - 0.5 * math.cos(math.pi * s)
        th = 360.0 * turns * ease
        r = math.radians(th)
        k = math.sin(math.pi * s)
        pose = dict(base or {})
        if axis == "x":
            pose["root"] = (th, 0, 0)
            pose["root_pos"] = (0, centre * (1 - math.cos(r)), centre * math.sin(r))
        elif axis == "z":
            pose["root"] = (0, 0, th)
            pose["root_pos"] = (-centre * math.sin(r), centre * (1 - math.cos(r)), 0)
        else:
            pose["root"] = (0, th, 0)
        if tuck:
            pose.update({"rL": (-70 * k, 0, 0), "lL": (-70 * k, 0, 0)})
        out[round(t0 + (t1 - t0) * s, 3)] = pose
    return out


def uses_wield(spec) -> bool:
    return any(isinstance(v, Wield) for f in spec["frames"].values() for v in f.values())


# ===========================================================================
#  解く（キー → 部位ごとの絶対値の Euler トラック）
# ===========================================================================
def _unwrap(e, ref):
    e = np.array(e, float)
    return e - 360.0 * np.round((e - np.asarray(ref, float)) / 360.0)


def euler_near(R, ref):
    """回転行列を ref に最も近いオイラー角（2 通りの分解 × 360° の巻き）で。"""
    a, b, c = euler(R)
    cands = [np.array([a, b, c]), np.array([a + 180.0, 180.0 - b, c + 180.0])]
    cands = [_unwrap(x, ref) for x in cands]
    return min(cands, key=lambda x: float(np.abs(x - ref).sum()))


def _arc(a, b, pref_axis=(1.0, 0.0, 0.0)):
    """a を b へ最短で回す回転行列（正反対の時は pref_axis まわりに 180°）。"""
    a = np.asarray(a, float) / np.linalg.norm(a)
    b = np.asarray(b, float) / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.9999:
        p = np.asarray(pref_axis, float)
        p = p - a * np.dot(p, a)
        p /= np.linalg.norm(p)
        return 2.0 * np.outer(p, p) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1.0 + c)


def _axis_angle(axis, deg):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


ARM_DOWN = np.array([0.0, -1.0, 0.0])
DEFAULT_ARM = np.array(dirv(f=0.6, u=-0.8))


class Resolved:
    """解いたモーション: tracks = {部位: {秒: (x, y, z)}}（絶対値）、R = {部位: {秒: 回転行列}}。"""

    def __init__(self, name, length, kind, loop, blend, tracks, mats, wkind):
        self.name, self.length, self.kind, self.loop = name, length, kind, loop
        self.blend = blend
        self.tracks = tracks
        self.mats = mats
        self.wkind = wkind
        self.keys = []          # 書いたキーの時刻（足したキーを除く）


def _parent_R(pose):
    """腕の親（腰・体）の回転（全身 root は含めない = 体の空間で向きを書く）。"""
    R = np.eye(3)
    for k in ("w", "b"):
        v = pose.get(k)
        if v is not None and not isinstance(v, (Aim, Wield)):
            R = R @ rot(*v)
    return R


def _hold_info(wkind, hold=None):
    if hold is not None:
        return hold
    import astro_hold as AH
    return AH.hold(wkind)


def _arm_matrix(v, side, pose, hold, cloud=None, solved=None):
    """Aim / Wield → 腕の局所の回転行列（体・腰のひねりを打ち消して）。
    cloud（武器の点）があれば、wield は武器が体に入らない所へ腕を回す（solved = 解いた他の部位）。"""
    Rp = _parent_R(pose)
    if isinstance(v, Aim):
        d = Rp.T @ v.d
        R = _arc(ARM_DOWN, d) @ _axis_angle(ARM_DOWN, v.twist)
        return R
    if side != "rA":
        raise ValueError("wield() is for the right arm (rA)")
    blade_l = np.asarray(hold["blade_arm"], float)
    edge_l = -np.asarray(hold["up_arm"], float)
    bt = Rp.T @ v.blade
    if v.edge is not None:
        want, loc = Rp.T @ v.edge, edge_l
        R = frame_axes(blade_l, bt, edge_l, want)
    else:
        want, loc = Rp.T @ (v.arm if v.arm is not None else DEFAULT_ARM), ARM_DOWN
        R = frame_axes(blade_l, bt, ARM_DOWN, want)
    if v.roll:
        R = _axis_angle(bt, v.roll) @ R
    if cloud is not None and solved is not None:
        R = _clear(R, bt, want / np.linalg.norm(want), loc, solved, cloud, blade_l=blade_l)
    return R


# ---------------------------------------------------------------------------
#  武器と体の当たり（スーツを着た体: 素の箱 + 装甲の厚み。右腕は上腕だけ — 拳は武器を握っている）
# ---------------------------------------------------------------------------
SUIT_PAD = {"head": 1.0, "body": 0.9, "leftArm": 0.6, "rightArm": 0.6, "rightLeg": 0.6, "leftLeg": 0.6}
UPPER_R = ((-8, 17, -2), (4, 7, 4))


def parts_pose(parts):
    """{部位: 値} → hd_scene の姿勢。"""
    pose = {}
    for k, v in parts.items():
        if k == "root_pos":
            pose.setdefault("root", {})["position"] = tuple(v)
        elif k in BONES and not isinstance(v, (Aim, Wield)):
            pose.setdefault(BONES[k], {})["rotation"] = tuple(v)
    return pose


def clip_depth(pose, cloud, skip=()):
    """姿勢 pose（hd_scene の形）で、右手の武器の点 cloud（rightItem 空間 4xN）が体に入る最大の深さと部位。"""
    import hd_scene as S
    W_ = S.skeleton_world(pose)
    pw = W_["rightItem"] @ cloud
    worst = (0.0, None)
    for bone, _p, _pv, cube in S.SKELETON:
        if not cube or bone in skip:
            continue
        o, sz, _c = cube
        if bone == "rightArm":
            o, sz = UPPER_R
        pad = SUIT_PAD.get(bone, 0.5)
        lo = np.array(o, float) - pad
        hi = np.array(o, float) + np.array(sz, float) + pad
        q = (np.linalg.inv(W_[bone]) @ pw)[:3].T
        d = np.clip(np.minimum(q - lo, hi - q).min(axis=1), 0, None)
        m = float(d.max()) if len(d) else 0.0
        if m > worst[0]:
            worst = (m, bone)
    return worst


def _angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(a, b))))))


def _clear(R0, bt, want_dir, local_vec, parts, cloud, blade_l=None, tilt=True):
    """体に入らない腕の向きを探す。まず刃先の向き bt を保ったまま腕を刃の軸まわりに回し（手首の角度は一定）、
    それでも入るなら刃先を少し（〜36°）傾けることも許す。want_dir / local_vec: 守りたい向きと、その腕の局所の
    ベクトル（腕の向き or 刃の向き）。返り値は腕の局所の回転行列。"""
    blade_l = None if blade_l is None else np.asarray(blade_l, float)

    def cost(R):
        d, _b = clip_depth(parts_pose(dict(parts, rA=euler(R))), cloud)
        c = 60.0 * max(0.0, d - 0.15) ** 2 + (_angle(R @ local_vec, want_dir) / 30.0) ** 2
        if blade_l is not None:
            c += 2.0 * (_angle(R @ blade_l, bt) / 25.0) ** 2
        return c, d
    c0, d0 = cost(R0)
    if d0 <= 0.3:
        return R0
    best = (c0, R0, d0)
    for phi in range(-170, 180, 10):
        R = _axis_angle(bt, phi) @ R0
        c, d = cost(R)
        if c < best[0]:
            best = (c, R, d)
    if tilt and best[2] > 0.3 and blade_l is not None:
        base = best[1]
        perp = np.cross(bt, [0.0, 1.0, 0.0])
        if np.linalg.norm(perp) < 1e-3:
            perp = np.cross(bt, [1.0, 0.0, 0.0])
        perp /= np.linalg.norm(perp)
        for k in range(8):
            ax = _axis_angle(bt, k * 45.0) @ perp
            for ang in (12.0, 24.0, 36.0):
                for phi in range(-150, 180, 30):
                    R = _axis_angle(ax, ang) @ _axis_angle(bt, phi) @ base
                    c, d = cost(R)
                    if c < best[0]:
                        best = (c, R, d)
    # 近くを細かく
    R = best[1]
    for step in (6.0, 3.0, 1.5):
        improved = True
        while improved:
            improved = False
            for ax in (bt, np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])):
                for sgn in (-1, 1):
                    Rc = _axis_angle(ax, sgn * step) @ best[1]
                    c, d = cost(Rc)
                    if c < best[0] - 1e-9:
                        best = (c, Rc, d)
                        improved = True
    return best[1]


REPAIR_AT = 0.6      # 補間の途中でこれより深く入り込むコマにはキーを足して直す（px）
REPAIR_STEP = 0.03   # 直す区間で腕のねじりを選ぶ間隔（秒。足すキーの間隔はこれ以上）
REPAIR_SPEED = 800.0  # ねじりの速さ（度/秒）がこれだと、体に 0.13 px 入るのと同じ重さ
REPAIR_MAX_STEP = 90.0   # 隣り合うキーの間のねじりの差の上限（度。これを超えると補間の向きが曖昧になる）
TWISTS = tuple(range(-180, 180, 10))


def _twist_segment(res, cloud, blade_l, a, b, factor, gap):
    """書いたキー a〜b の間で、腕を刃の軸まわりにねじる角度（刃先の向きは変えない）を gap 秒ごとに Viterbi で
    選ぶ。ねじりは a・b で 0、隣り合うキーの差は REPAIR_MAX_STEP 以下、キーの間の回る速さは
    factor × max(ARM_SPEED_MAX, a〜b の速さ × 1.6) 以下（もとの動きが既に速い所は、それより速くしない）。"""
    tr = res.tracks["rA"]
    mk = res.mats["rA"]
    INF = 1e18
    pts = [a] + sorted(x for x in tr if a < x < b) + [b]
    S = set(pts[1:-1])
    for p, q in zip(pts, pts[1:]):
        m = int((q - p) / gap + 1e-9)
        S |= {round(p + (q - p) * k / m, 3) for k in range(1, m)}
    S = sorted(x for x in S if a < x < b)
    if not S:
        return
    base = [_key_R(tr, mk, t) if t in tr else rot(*_eval_track(tr, t)) for t in S]
    node = []
    for t, R0 in zip(S, base):
        parts = sample_parts(res, t)
        bt = R0 @ blade_l
        arm0 = R0 @ ARM_DOWN
        row = []
        for phi in TWISTS:
            R = _axis_angle(bt, phi) @ R0
            d, _b = clip_depth(parts_pose(dict(parts, rA=euler(R))), cloud)
            row.append(60.0 * max(0.0, d - 0.15) ** 2 + (_angle(R @ ARM_DOWN, arm0) / 30.0) ** 2
                       + 0.1 * (phi / 90.0) ** 2)
        node.append(np.array(row))
    T = [a] + S + [b]
    ph = np.array(TWISTS, float)
    diff = (ph[None, :] - ph[:, None] + 180.0) % 360.0 - 180.0     # diff[i, j] = 前 i → 次 j
    RT = [_key_R(tr, mk, a)] + base + [_key_R(tr, mk, b)]
    TW = [np.stack([_axis_angle(R0 @ blade_l, phi) @ R0 for phi in TWISTS]) for R0 in RT]
    allow = factor * max(ARM_SPEED_MAX, 1.6 * _rot_angle(RT[0], RT[-1]) / max(b - a, 1e-3))
    nt = len(TWISTS)

    def edge(k):
        """k → k+1 の重さ: もとの動きより速く回る分。上限を超える組・ねじりの差が大きい組は不可。"""
        dt = max(T[k + 1] - T[k], 1e-3)
        A = np.repeat(TW[k], nt, axis=0)
        B = np.tile(TW[k + 1], (nt, 1, 1))
        ang = angle_many(A, B).reshape(nt, nt)
        base_ang = _rot_angle(RT[k], RT[k + 1])
        e = (np.maximum(0.0, ang - base_ang) / dt / REPAIR_SPEED) ** 2
        fast = (ang / dt > allow) & (ang > base_ang * 1.02 + 0.5)
        e[(np.abs(diff) > REPAIR_MAX_STEP + 1e-6) | fast] = INF
        return e
    i0 = TWISTS.index(0)
    cost = edge(0)[i0] + node[0]
    back = []
    for k in range(1, len(S)):
        tot = cost[:, None] + edge(k)
        back.append(np.argmin(tot, axis=0))
        cost = tot.min(axis=0) + node[k]
    cost = cost + edge(len(S))[:, i0]
    idx = [int(np.argmin(cost))]
    for bk in reversed(back):
        idx.append(int(bk[idx[-1]]))
    idx.reverse()
    if all(TWISTS[i] == 0 for i in idx):
        return
    for t, R0, i in zip(S, base, idx):
        R = _axis_angle(R0 @ blade_l, TWISTS[i]) @ R0
        tr[t] = tuple(float(x) for x in euler(R))
        mk[t] = R


def _repair(res, cloud, hold, rounds=5, step=0.02):
    """統合版と同じ catmullrom で 0.02 秒ごとに調べ、武器が体に入るコマを含む「書いたキーの間」の区間を、
    腕を刃の軸まわりにねじって直す（_twist_segment。速くねじるほど高くつき、腕の速さの上限は超えない。
    体を避けきれない時は少し入るのを許す）。区間はいつも直す前の状態から解き直す: 直した結果が
    arm_speeds の上限を超えた区間は、速さの余裕を減らして解き直す（最後はねじらない）。"""
    if cloud is None or "rA" not in res.tracks:
        return
    tr = res.tracks["rA"]
    mk = res.mats["rA"]
    blade_l = np.asarray(hold["blade_arm"], float)
    auth = sorted(set(res.keys) | {min(tr), max(tr)})
    snap_tr, snap_mk = dict(tr), dict(mk)
    fac = {}
    gap = {}

    def seg_of(t):
        return min(max(k for k in range(len(auth) - 1) if auth[k] <= t + 1e-9), len(auth) - 2)

    def restore(j):
        a, b = auth[j], auth[j + 1]
        for x in [x for x in tr if a < x < b]:
            del tr[x]
            mk.pop(x, None)
        for x, v in snap_tr.items():
            if a < x < b:
                tr[x] = v
                mk[x] = snap_mk.get(x)
    n = max(2, int(math.ceil(res.length / step)))
    for _rnd in range(rounds):
        todo = set()
        for i in range(1, n):
            t = res.length * i / n
            d, _b = clip_depth(sample(res, t), cloud)
            if d > REPAIR_AT:
                j = seg_of(t)
                if fac.get(j, 1.0) > 0.4 and gap.get(j, 1.0) > MIN_DT + 1e-6:
                    todo.add(j)
        tm, w, allow = arm_speeds(res, "rA")
        for m in np.where(w > allow * 0.995)[0]:
            j = seg_of(float(tm[m]))
            if j in fac:                       # 直した区間が速すぎる → 余裕を減らして解き直す
                todo.add(j)
                fac[j] = fac[j] - 0.15
                gap[j] = gap[j] / 0.75          # 解き直す時は細かくしない（下で 0.75 倍に戻る）
        if not todo:
            break
        for j in sorted(todo):
            fac.setdefault(j, 0.9)
            gap[j] = max(MIN_DT, gap.get(j, REPAIR_STEP / 0.75) * 0.75)
            restore(j)
            if fac[j] > 0.4:
                _twist_segment(res, cloud, blade_l, auth[j], auth[j + 1], fac[j], gap[j])
        _finalize_arms(res.tracks, res.mats, res.plain, res.keys, only=("rA",))


def _foot_min(pose):
    """root_pos の y を 0 とした時の、低い方の足の裏の高さ。"""
    Rr = rot(*pose.get("root", (0, 0, 0)))
    pos = np.asarray(pose.get("root_pos", (0, 0, 0)), float) * np.array([1, 0, 1])
    low = 1e9
    for leg, x0 in (("rL", -3.9), ("lL", -0.1)):
        M = bone_local(PIVOT[leg], pose.get(leg, (0, 0, 0)))
        for x in (x0, x0 + 4):
            for z in (-2, 2):
                p = M @ np.array([x, 0.0, z, 1.0])
                q = Rr @ p[:3] + pos
                low = min(low, q[1])
    return low


def resolve(spec, wkind="sword", name="", hold=None, cloud=None) -> Resolved:
    """spec（anim() の戻り値）を、武器の種類 wkind の持ち方で解く。
    cloud（gen_astro_anim.weapon_cloud の武器の表面の点）を渡すと、wield() の腕は武器がスーツを着た体に
    入り込まない向きへ自動で回す（刃先の向きは変えず、手首の角度のまま腕を刃の軸まわりに）。"""
    hold = _hold_info(wkind, hold) if uses_wield(spec) else hold
    frames = spec["frames"]
    times = sorted(frames)
    parts = set()
    for f in frames.values():
        parts |= {k for k in f if k in BONES}
    if spec["kind"] in ("act", "pose"):
        parts |= set(ARMS)                 # 打ち消しのトラックが要る
    tracks = {k: {} for k in parts}
    mats = {k: {} for k in ARMS}
    plains = {k: {} for k in ARMS}     # 腕の書いたオイラー角のキー（_relift の錨）
    has_pos = any("root_pos" in f or f.get("ground") for f in frames.values())
    if has_pos:
        tracks["root_pos"] = {}
    prev = {k: np.array(REST.get(k, (0, 0, 0)), float) for k in parts}
    for t in times:
        f = frames[t]
        pose = {}
        plain = {k: f.get(k, REST.get(k, (0.0, 0.0, 0.0))) for k in ORDER if k in parts}
        plain = {k: v for k, v in plain.items() if not isinstance(v, (Aim, Wield))}
        if "root_pos" in f:
            plain["root_pos"] = f["root_pos"]
        for k in SOLVE_ORDER:
            if k not in parts:
                continue
            v = f.get(k, REST.get(k, (0.0, 0.0, 0.0)))
            if isinstance(v, (Aim, Wield)):
                R = _arm_matrix(v, k, f, hold, cloud, dict(plain, **{kk: pose[kk] for kk in pose}))
                e = euler_near(R, prev[k])
                if k in mats:
                    mats[k][t] = R
            else:
                e = np.array(v, float)
                if k in mats:
                    mats[k][t] = None
                    plains[k][t] = tuple(float(x) for x in e)
            prev[k] = e
            pose[k] = tuple(float(x) for x in e)
            tracks[k][t] = pose[k]
        if has_pos:
            rp = list(f.get("root_pos", (0.0, 0.0, 0.0)))
            if f.get("ground"):
                rp[1] = 0.0
                rp[1] = -_foot_min(dict(pose, root_pos=tuple(rp)))
            tracks["root_pos"][t] = tuple(float(x) for x in rp)
    _densify_arms(tracks, mats)
    _finalize_arms(tracks, mats, plains, times)
    blend = spec["blend"]
    if blend is None:
        rt = tracks.get("root", {})
        span = 0.0
        if rt:
            vals = np.array(list(rt.values()))
            span = float(np.max(np.abs(vals.max(axis=0) - vals.min(axis=0))))
        blend = span < 300.0
    res = Resolved(name, spec["length"], spec["kind"], spec["loop"], blend, tracks, mats, wkind)
    res.keys = list(times)
    res.plain = plains
    if cloud is not None:
        _repair(res, cloud, hold if hold is not None else _hold_info(wkind))
    for k in ARMS:
        # 腕が一回転して終わる（最後の自然体のキーが 360° 巻いた・分解の違う値で終わる）なら、終わりのブレンドを
        # しない（ブレンドは成分を比例して縮めるので、巻いた分だけ腕が回ってしまう。回転は自然体と同じなので
        # ブレンドしなくても見た目は飛ばない）
        tr = tracks.get(k)
        if tr and max(tr) in plains[k] and \
                max(abs(a - b) for a, b in zip(tr[max(tr)], plains[k][max(tr)])) > 0.05:
            res.blend = False
    return res


def _quat(R):
    m = R
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    return q / np.linalg.norm(q)


def _mat(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def _slerp(q0, q1, s):
    d = float(np.dot(q0, q1))
    if d < 0:
        q1, d = -q1, -d
    if d > 0.9995:
        q = q0 + s * (q1 - q0)
        return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - s) * th) * q0 + math.sin(s * th) * q1) / math.sin(th)


MAX_STEP = 32.0      # 武器で解いた腕のキーの間がこれ以上回るなら、回転のまま補間したキーを足す


def _densify_arms(tracks, mats):
    """武器で解いた腕（行列から出したキー）の間が大きく回る所に、回転のまま補間したキーを足す。
    行列から出したキーは、直前のキーに最も近いオイラー角の表し方に揃え直す（補間で一回転しない）。"""
    for k in ARMS:
        if k not in tracks:
            continue
        tr = tracks[k]
        ts = sorted(tr)
        if not any(mats[k].get(t) is not None for t in ts):
            continue
        add = {}
        for a, b in zip(ts, ts[1:]):
            Ra = mats[k].get(a) if mats[k].get(a) is not None else rot(*tr[a])
            Rb = mats[k].get(b) if mats[k].get(b) is not None else rot(*tr[b])
            if mats[k].get(b) is not None:
                tr[b] = tuple(float(x) for x in euler_near(Rb, np.array(tr[a])))
            ang = math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(Ra.T @ Rb) - 1) / 2))))
            n = int(math.ceil(ang / MAX_STEP))
            if n <= 1:
                continue
            qa, qb = _quat(Ra), _quat(Rb)
            ref = np.array(tr[a])
            for i in range(1, n):
                s = i / n
                e = euler_near(_mat(_slerp(qa, qb, s)), ref)
                ref = e
                add[round(a + (b - a) * s, 3)] = tuple(float(x) for x in e)
            if mats[k].get(b) is not None:
                tr[b] = tuple(float(x) for x in euler_near(Rb, ref))
        tr.update(add)
        for t, e in add.items():
            mats[k][t] = rot(*e)


EULER_TOL = 6.0      # 統合版はオイラー角を成分ごとに補間する。回転のままの補間とこれ以上ずれる所にはキーを足す
MIN_DT = 0.02        # 補間を直すために足すキーの最小の間隔（秒。1 コマ = 1/60 秒より短くしない）
ARM_SPEED_MAX = 1500.0   # 腕の角速度の上限（度/秒）。書いたキーの間の速さの 1.6 倍まではそれを上限にする
REFINE_MAX = 48      # 1 本のトラックに直しで足すキーの上限
END_WRAP = 2.0       # 最初・最後の自然体のキーを巻いた値にする重さ（区間で切り替えて腕を回すより軽い時だけ）


def _rot_angle(Ra, Rb):
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(Ra.T @ Rb) - 1) / 2))))


def _key_R(tr, mk, t):
    m = mk.get(t)
    return m if m is not None else rot(*tr[t])


def rot_many(E) -> np.ndarray:
    """rot() を (N, 3) の Euler にまとめて（(N, 3, 3)）。"""
    E = np.radians(np.asarray(E, float).reshape(-1, 3))
    ca, sa = np.cos(-E[:, 0]), np.sin(-E[:, 0])
    cb, sb = np.cos(E[:, 1]), np.sin(E[:, 1])
    cc, sc = np.cos(-E[:, 2]), np.sin(-E[:, 2])
    return np.stack([
        np.stack([cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa], -1),
        np.stack([sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa], -1),
        np.stack([-sb, cb * sa, cb * ca], -1)], -2)


def angle_many(A, B) -> np.ndarray:
    """回転行列の組 A[i], B[i] の間の角度（度）。"""
    c = (np.einsum("nij,nij->n", A, B) - 1.0) / 2.0
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def _forms(R, ref):
    """R の 2 通りのオイラー角を、それぞれ ref に最も近い巻きで。"""
    a, b, c = euler(R)
    ref = np.asarray(ref, float)
    return [_unwrap(np.array([a, b, c]), ref), _unwrap(np.array([a + 180.0, 180.0 - b, c + 180.0]), ref)]


def _catmull_many(P, s):
    """P = (4, 3) の制御点、s = (M,) → (M, 3)。"""
    s = np.asarray(s, float)[:, None]
    p0, p1, p2, p3 = P
    return 0.5 * (2 * p1 + (p2 - p0) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                  + (3 * p1 - p0 - 3 * p2 + p3) * s * s * s)


_S3 = np.array([0.25, 0.5, 0.75])
_S8 = np.linspace(0.0, 1.0, 9)


def _intended(Ra, Rb, ea, eb, plain_seg, s):
    """区間の「意図した」回転（s ごと）: 書いたオイラー角どうし（自然体など）は成分ごとの補間、
    それ以外（武器で解いた腕・足したキー）は回転のままの補間（slerp）。"""
    if plain_seg:
        return rot_many(ea[None] + (eb - ea)[None] * np.asarray(s)[:, None])
    qa, qb = _quat(Ra), _quat(Rb)
    return np.stack([_mat(_slerp(qa, qb, float(x))) for x in s])


def _relift(tr, mk, rest, pv):
    """腕のトラックの各キーを、どのオイラー角の表し方（2 通りの分解 × 360° の巻き）で書くかを選び直す。
    統合版は成分ごとに catmullrom で補間するので、隣り合うキーの表し方が違う（分解が入れ替わる・360° 巻く）と、
    回転はほとんど同じでも成分が大きく飛び、その区間と前後の区間の接線が暴れて腕が振り回される。
      * 書いたオイラー角のキー pv（自然体 H など）は書いた値のまま。腕が本当に一回転する動き（巻きが
        戻らない）だけ、最初・最後のキーを同じ回転の別の値にするのを許す（END_WRAP。その時 resolve は
        終わりのブレンドを切る — ブレンドは成分を比例して縮めるので、巻いた値のままでは腕が回る）
      * 行列から出したキーは、その錨（書いたキー、または最初・最後のキーの 2 通り）から回転を連続に
        たどった値（lift）のどれか
      * 錨どうしでたどった値が食い違う時だけ、切り替える区間を Viterbi で選ぶ（成分の補間が回転の
        補間から最もずれない・長い区間で）"""
    ts = sorted(tr)
    n = len(ts)
    if n < 2 or not any(mk.get(t) is not None for t in ts):
        return
    Rs = [_key_R(tr, mk, t) for t in ts]
    plain = [mk.get(t) is None and t in pv for t in ts]
    auth = [np.array(pv[t] if plain[i] else tr[t], float) for i, t in enumerate(ts)]

    def lift(i0, e0):
        out = [None] * n
        out[i0] = np.array(e0, float)
        for i in range(i0 + 1, n):
            out[i] = euler_near(Rs[i], out[i - 1])
        for i in range(i0 - 1, -1, -1):
            out[i] = euler_near(Rs[i], out[i + 1])
        return out
    anchors = [(i, auth[i]) for i in range(n) if plain[i]]
    for i in (n - 1, 0):
        if not plain[i]:
            anchors += [(i, f) for f in sorted(_forms(Rs[i], rest), key=lambda f: float(np.abs(f - rest).sum()))]
    lifts = []
    for i, e in anchors:
        if any(np.abs(L[i] - e).max() < 0.05 for L in lifts):
            continue
        lifts.append(lift(i, e))

    def fits(L):
        return all(np.abs(L[i] - auth[i]).max() < 0.05 for i in range(n) if plain[i])
    good = [L for L in lifts if fits(L)]
    if good:
        # 1 本の lift で全部の錨が合う（ほとんどのトラック）。最初・最後の小さい方
        best = min(good, key=lambda L: float(np.abs(L[0] - rest).sum() + np.abs(L[-1] - rest).sum()))
        for i, t in enumerate(ts):
            tr[t] = tuple(float(x) for x in best[i])
        return
    # ---- 食い違う: Viterbi -------------------------------------------------------------
    cands = []
    for i in range(n):
        c = []
        for L in lifts:
            if not any(np.abs(L[i] - x).max() < 0.05 for x in c):
                c.append(L[i])
        if plain[i] and not any(np.abs(auth[i] - x).max() < 0.05 for x in c):
            c.append(auth[i])
        cands.append(c)
    INF = 1e18

    def node(i, e):
        if plain[i]:
            if np.abs(e - auth[i]).max() < 0.05:
                return 0.0
            return END_WRAP if i in (0, n - 1) else 4.0
        return 1e-3 * float(np.abs(e - rest).sum()) if i in (0, n - 1) else 0.0
    cost = [np.array([node(0, e) for e in cands[0]])]
    back = []
    for i in range(1, n):
        dt = max(ts[i] - ts[i - 1], 1e-3)
        plain_seg = plain[i - 1] and plain[i]
        Rint = _intended(Rs[i - 1], Rs[i], auth[i - 1], auth[i], plain_seg, _S3)
        ci, bi = [], []
        for e in cands[i]:
            best = (INF, 0)
            for j, x in enumerate(cands[i - 1]):
                if cost[-1][j] >= INF:
                    continue
                path = x[None] + (e - x)[None] * _S3[:, None]
                dev = float(angle_many(rot_many(path), Rint).max())
                c = cost[-1][j] + (dev / EULER_TOL) ** 2 + (dev / (dt * 400.0)) ** 2 \
                    + 1e-3 * float(np.abs(e - x).sum())
                if c < best[0]:
                    best = (c, j)
            ci.append(best[0] + node(i, e))
            bi.append(best[1])
        cost.append(np.array(ci))
        back.append(bi)
    j = int(np.argmin(cost[-1]))
    for i in range(n - 1, -1, -1):
        tr[ts[i]] = tuple(float(x) for x in cands[i][j])
        if i:
            j = back[i - 1][j]


def _seg_badness(ts, E, Rs, plain, i, limit_speed=None):
    """区間 i（ts[i]→ts[i+1]）を統合版の catmullrom で補間した時の悪さ: max(意図した回転からのずれ / EULER_TOL,
    角速度 / 許す速さ)。1 を超えると直す。"""
    n = len(ts)
    P = np.stack([E[max(0, i - 1)], E[i], E[i + 1], E[min(n - 1, i + 2)]])
    got = rot_many(_catmull_many(P, _S8))
    dt = max(ts[i + 1] - ts[i], 1e-4)
    want = _intended(Rs[i], Rs[i + 1], E[i], E[i + 1], plain[i] and plain[i + 1], _S8)
    dev = float(angle_many(got, want).max())
    speed = float(angle_many(got[1:], got[:-1]).max()) / (dt / (len(_S8) - 1))
    # 許す速さ: この区間と両隣の区間の、意図した速さの 1.5 倍（最低 360 度/秒）
    v = []
    for j in (i - 1, i, i + 1):
        if 0 <= j < n - 1:
            v.append(_rot_angle(Rs[j], Rs[j + 1]) / max(ts[j + 1] - ts[j], 1e-4))
    allow = max(360.0, 1.5 * max(v))
    if limit_speed:
        allow = min(allow, limit_speed)
    return max(dev / EULER_TOL, speed / allow)


def _speed_limits(tr, mk, keys, ts):
    """区間ごと（ts[i]→ts[i+1]）の腕の速さの上限 = arm_speeds と同じ max(ARM_SPEED_MAX, 書いたキーの間 × 1.6)。"""
    ak = sorted(set(keys) | {ts[0], ts[-1]})
    ak = [t for t in ak if t in tr]
    sp = [_rot_angle(_key_R(tr, mk, a), _key_R(tr, mk, b)) / max(b - a, 1e-3) for a, b in zip(ak, ak[1:])]
    out = []
    for a, b in zip(ts, ts[1:]):
        m = (a + b) / 2
        j = max([i for i in range(len(ak) - 1) if ak[i] <= m] or [0])
        out.append(max(ARM_SPEED_MAX, 1.6 * (sp[j] if sp else 0.0)))
    return out


def _refine(tr, mk, keys=()):
    """統合版と同じ catmullrom で補間した腕が、意図した回転から EULER_TOL° 以上ずれる・速く回りすぎる区間に、
    回転のまま補間した中点のキーを足す（その区間か隣の区間の、いちばん良くなる方）。足すキーは MIN_DT 以上
    離す（近すぎるキーは、前後の長い区間に大きな接線を持ち込んで腕を振り回す）。"""
    if not any(v is not None for v in mk.values()):
        return
    stuck = set()
    added = 0
    while added < REFINE_MAX:
        ts = sorted(tr)
        n = len(ts)
        E = [np.array(tr[t], float) for t in ts]
        Rs = [_key_R(tr, mk, t) for t in ts]
        plain = [mk.get(t) is None for t in ts]
        lim = _speed_limits(tr, mk, keys, ts)
        bad = [(_seg_badness(ts, E, Rs, plain, i, 0.95 * lim[i]), i) for i in range(n - 1)]
        cand = [(b, i) for b, i in bad if b > 1.0 and ts[i] not in stuck]
        if not cand:
            return
        b0, i = max(cand)
        lo, hi = max(0, i - 2), min(n - 2, i + 2)
        cur = max(bb for bb, j in bad if lo <= j <= hi)
        best = None
        for j in (i, i - 1, i + 1):
            if not 0 <= j < n - 1 or ts[j + 1] - ts[j] < 2 * MIN_DT - 1e-6:
                continue
            tm = round((ts[j] + ts[j + 1]) / 2, 3)
            if tm in tr:
                continue
            if plain[j] and plain[j + 1]:
                em = (E[j] + E[j + 1]) / 2
                Rm = rot(*em)
            else:
                Rm = _mat(_slerp(_quat(Rs[j]), _quat(Rs[j + 1]), 0.5))
                em = euler_near(Rm, (E[j] + E[j + 1]) / 2)
            ts2 = ts[:j + 1] + [tm] + ts[j + 1:]
            E2 = E[:j + 1] + [em] + E[j + 1:]
            R2 = Rs[:j + 1] + [Rm] + Rs[j + 1:]
            p2 = plain[:j + 1] + [False] + plain[j + 1:]
            l2 = lim[:j + 1] + [lim[j]] + lim[j + 1:]
            new = max(_seg_badness(ts2, E2, R2, p2, k, 0.95 * l2[k])
                      for k in range(lo, min(len(ts2) - 2, hi + 1) + 1))
            if best is None or new < best[0]:
                best = (new, tm, em, Rm)
        if best is None or best[0] >= cur - 1e-3:
            stuck.add(ts[i])
            continue
        _new, tm, em, Rm = best
        tr[tm] = tuple(float(x) for x in em)
        mk[tm] = Rm
        added += 1


def _finalize_arms(tracks, mats, plains, keys, only=ARMS):
    """腕のトラックの表し方を選び直し（_relift）、補間を catmullrom で確かめて直す（_refine）。"""
    for k in only:
        if k not in tracks:
            continue
        mk = mats.setdefault(k, {})
        pv = plains.get(k, {})
        rest = np.array(REST.get(k, (0.0, 0.0, 0.0)), float)
        _relift(tracks[k], mk, rest, pv)
        _refine(tracks[k], mk, keys)
        _relift(tracks[k], mk, rest, pv)


def arm_speeds(res, part, step=1.0 / 120.0):
    """(時刻の中点, 角速度 度/秒, 許す速さ) の配列: 統合版の catmullrom で step 秒ごとに見た腕の角速度と、
    その時刻の上限 max(ARM_SPEED_MAX, 書いたキーの間の速さ × 1.6)。"""
    tr = res.tracks.get(part)
    if not tr or len(tr) < 2:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    keys = sorted(set(res.keys) | {0.0, round(res.length, 3)})
    n = max(2, int(math.ceil(res.length / step)))
    T = np.linspace(0.0, res.length, n + 1)
    R = rot_many(np.stack([_eval_track(tr, float(t)) for t in T]))
    w = angle_many(R[1:], R[:-1]) / (res.length / n)
    Rk = [rot(*_eval_track(tr, t)) for t in keys]
    seg = [_rot_angle(Rk[i], Rk[i + 1]) / max(keys[i + 1] - keys[i], 1e-3) for i in range(len(keys) - 1)]
    tm = (T[1:] + T[:-1]) / 2
    idx = np.clip(np.searchsorted(keys, tm, side="right") - 1, 0, len(seg) - 1)
    allow = np.maximum(ARM_SPEED_MAX, 1.6 * np.asarray(seg)[idx])
    return tm, w, allow


def arm_speed_report(res, step=1.0 / 120.0):
    """[(部位, 時刻, 角速度, 許す速さ)]: 上限を超えた腕（部位ごとに最悪の 1 つ）。"""
    out = []
    for k in ARMS:
        tm, w, allow = arm_speeds(res, k, step)
        if len(w) and (w > allow).any():
            m = int(np.argmax(w / allow))
            out.append((k, round(float(tm[m]), 3), float(w[m]), float(allow[m])))
    return out


FP_FADE = (110.0, 170.0)   # 一人称の腕: 自然体からの回転 θ がこの間で 25% → 0 へなめらかに減る（真反対の近くで軸が飛ぶので）


def fp_track(res, part) -> dict:
    """一人称の腕 {秒: (x, y, z)}: 自然体からの回転 D = R · R_rest⁻¹（最短の向き、角度 θ ≤ 180°）を、同じ軸
    まわりに f(θ) = FPK·θ·(1 − smoothstep(FP_FADE))（≤ 28°）だけ回した物のオイラー角（隣のキーに最も近い表し方）。
    成分を 25% にするのではない（±360° の巻きや分解の違いで一人称の腕が 90° ねじれないように）。θ が 180° に
    近い所（腕が自然体の真反対の近く）では最短の軸が入れ替わるので f = 0 にして、一人称の腕が飛ばないようにする。"""
    tr = res.tracks.get(part)
    if not tr:
        return {}
    R0 = rot(*REST.get(part, (0.0, 0.0, 0.0)))
    out = {}
    prev = np.zeros(3)
    for t in sorted(tr):
        q = _quat(rot(*tr[t]) @ R0.T)
        if q[0] < 0:
            q = -q
        s = float(np.linalg.norm(q[1:]))
        if s < 1e-9:
            F = np.eye(3)
        else:
            th = 2.0 * math.degrees(math.atan2(s, float(q[0])))
            x = min(1.0, max(0.0, (th - FP_FADE[0]) / (FP_FADE[1] - FP_FADE[0])))
            F = _axis_angle(q[1:] / s, FPK * th * (1.0 - x * x * (3.0 - 2.0 * x)))
        e = euler_near(F, prev)
        out[t] = tuple(float(x) for x in e)
        prev = e
    return out


# ===========================================================================
#  統合版の JSON
# ===========================================================================
_ATK = "math.sin((1.0 - math.pow(1.0 - v.attack_time, 4.0)) * 180.0)"
ATK_CANCEL = {      # バニラの攻撃の振り（animation.player.attack.rotations）を打ち消す（hyperdim と同じ）
    ("rA", 0): f"({_ATK} * 1.2 + math.sin(v.attack_time * 180.0)) * 30.0",
    ("rA", 1): f"({_ATK} != 0.0 ? 30.0 - 90.0 * {_ATK} : 0.0)",
    ("lA", 0): f"({_ATK} * 1.2 + math.sin(v.attack_time * 180.0)) * 10.0",
    ("b", 1): "-math.sin(360.0 * math.sqrt(v.attack_time)) * 5.0",
}
WALK_CANCEL = {     # 持ち姿勢で半分になった歩きの腕振り
    ("rA", 0): "0.375 * (v.tcos0 ?? 0.0)",
    ("lA", 0): "-0.75 * (v.tcos0 ?? 0.0)",
}


def num(x):
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _chan(part, axis, value, kind, fp=0.0):
    """1 チャンネルの値（数か Molang）。value は絶対値（三人称）、fp は一人称の値（fp_track）。"""
    rest = REST.get(part, (0.0, 0.0, 0.0))[axis]
    delta = value - rest
    if part in ARMS:
        terms = [num(delta)] if abs(delta) > 1e-6 else []
        if kind in ("act", "pose") and (part, axis) in WALK_CANCEL:
            terms.append(WALK_CANCEL[(part, axis)])
        if kind == "act" and (part, axis) in ATK_CANCEL:
            terms.append(ATK_CANCEL[(part, axis)])
        if not terms and num(fp) == "0":
            return 0
        tp = " + ".join(terms) if terms else "0.0"
        return f"v.is_first_person ? {num(fp)} : ({tp})"
    terms = [num(value)] if abs(value) > 1e-6 else []
    if kind == "act" and (part, axis) in ATK_CANCEL:
        terms.append(ATK_CANCEL[(part, axis)])
    if not terms:
        return 0
    return f"v.is_first_person ? 0.0 : ({' + '.join(terms)})"


def _ts(t):
    s = f"{t:.3f}".rstrip("0").rstrip(".")
    return s if "." in s else s + ".0"


def to_json(res: Resolved, smooth=True) -> dict:
    bones = {}
    for part in ORDER:
        if part not in res.tracks:
            continue
        tr = res.tracks[part]
        fp = fp_track(res, part) if part in ARMS else {}
        track = {}
        moved = False
        for t in sorted(tr):
            v = [_chan(part, i, tr[t][i], res.kind, fp[t][i] if fp else 0.0) for i in range(3)]
            if any(x != 0 for x in v):
                moved = True
            track[_ts(t)] = {"post": v, "lerp_mode": "catmullrom"} if smooth else v
        if moved:
            bones[BONES[part]] = {"rotation": track}
    if "root_pos" in res.tracks:
        tr = res.tracks["root_pos"]
        track = {}
        moved = False
        for t in sorted(tr):
            v = [f"v.is_first_person ? 0.0 : {num(x)}" if abs(x) > 1e-6 else 0 for x in tr[t]]
            moved |= any(x != 0 for x in v)
            track[_ts(t)] = {"post": v, "lerp_mode": "catmullrom"} if smooth else v
        if moved:
            bones.setdefault("root", {})["position"] = track
    out = {"loop": res.loop, "animation_length": round(res.length, 3), "bones": bones}
    return out


# ===========================================================================
#  評価（プレビュー・検査）: 統合版の catmullrom と同じ補間で、三人称・物を持った自然体の上の姿勢
# ===========================================================================
def _catmull(p0, p1, p2, p3, s):
    return 0.5 * (2 * p1 + (p2 - p0) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                  + (3 * p1 - p0 - 3 * p2 + p3) * s * s * s)


def _eval_track(tr, t):
    ts = sorted(tr)
    vals = [np.array(tr[x], float) for x in ts]
    if t <= ts[0]:
        return vals[0]
    if t >= ts[-1]:
        return vals[-1]
    i = max(j for j in range(len(ts)) if ts[j] <= t)
    s = (t - ts[i]) / (ts[i + 1] - ts[i])
    return _catmull(vals[max(0, i - 1)], vals[i], vals[i + 1], vals[min(len(vals) - 1, i + 2)], s)


def sample_parts(res: Resolved, t: float) -> dict:
    """{部位: 絶対値}（書かれていない部位は自然体）。"""
    out = {}
    for k, tr in res.tracks.items():
        if tr:
            out[k] = tuple(float(x) for x in _eval_track(tr, t))
    out.setdefault("rA", REST["rA"])
    return out


def sample(res: Resolved, t: float) -> dict:
    """hd_scene / astro_scene 用の姿勢 {bone: {rotation, position}}。"""
    p = sample_parts(res, t)
    pose = {}
    for k, v in p.items():
        if k == "root_pos":
            pose.setdefault("root", {})["position"] = v
        else:
            pose.setdefault(BONES[k], {})["rotation"] = v
    return pose


def describe(res: Resolved) -> list:
    """書いたキーごとに、右腕・刃先が体の空間でどちらを向いたか（f 前 / u 上 / r 右）と腕の Euler。"""
    import astro_hold as AH
    hold = AH.hold(res.wkind)
    out = []

    def fur(v):
        return f"f{-v[2]:+.2f} u{v[1]:+.2f} r{-v[0]:+.2f}"
    for t in res.keys:
        p = sample_parts(res, t)
        Rp = rot(*p.get("w", (0, 0, 0))) @ rot(*p.get("b", (0, 0, 0)))
        R = Rp @ rot(*p["rA"])
        arm = R @ ARM_DOWN
        blade = R @ np.asarray(hold["blade_arm"], float)
        out.append(f"t={t:5.2f}  rA=({p['rA'][0]:7.1f},{p['rA'][1]:7.1f},{p['rA'][2]:7.1f})  "
                   f"arm[{fur(arm)}]  blade[{fur(blade)}]")
    return out


# ===========================================================================
#  共通モーション（DESIGN.md §4.6）
# ===========================================================================
TR = {k: v / 20.0 for k, v in TRANSFORM.items() if isinstance(v, (int, float)) and k != "assemble_len"}


def library() -> dict:
    """{名前: spec}。武器の向きを wield() で書いた物は、惑星の武器の種類ごとに解き直した版
    （<惑星>.<名前>）も gen_astro_anim が書き出す。"""
    L = {}
    L["none"] = anim(0.05, {0.0: H}, kind="move")

    # ---- 変身（3.0 秒。TRANSFORM と同期: コアが浮く 0 / 奔流 0.4 / スーツ 0.7 / ウェポン 2.0 /
    #      バイザー 2.3 / 惑星の力 2.5 / カメラ 3.0） -------------------------------------------
    wf = TR["weapon_form"]
    raise_core = P(rA=aim(dirv(f=1.0, u=0.4, r=-0.12)), lA=(-12, 0, -14), b=(-6, 0, 0), h=(-18, 0, 0))
    cross = P(rA=aim(dirv(f=1.0, u=-0.12, r=-0.72), twist=-35), lA=aim(dirv(f=1.0, u=0.02, r=0.68), twist=35),
              b=(14, 0, 0), h=(12, 0, 0), rL=(-26, 0, 9), lL=(18, 0, -9), ground=True)
    cross2 = P(cross, b=(18, 0, 0), h=(16, 0, 0), rA=aim(dirv(f=1.0, u=-0.08, r=-0.76), twist=-35),
               lA=aim(dirv(f=1.0, u=0.06, r=0.72), twist=35), rL=(-30, 0, 10), lL=(22, 0, -10))
    spread = P(rA=aim(dirv(r=1.0, u=-0.25, f=0.15)), lA=aim(dirv(r=-1.0, u=-0.25, f=0.15)),
               b=(-12, 0, 0), h=(-22, 0, 0), rL=(0, 0, 11), lL=(0, 0, -11), ground=True)
    hero = P(rA=wield(blade=dirv(f=0.55, u=-0.55, r=0.62), arm=dirv(r=0.75, u=-0.7, f=0.1)),
             lA=aim(dirv(f=1.0, u=0.05, r=-0.25)), b=(4, -18, 0), h=(2, 14, 0),
             rL=(-14, 0, 12), lL=(16, 0, -10), ground=True)
    L["henshin"] = anim(3.0, {
        0.0: H,
        0.18: P(raise_core, h=(-20, 0, 0)),
        TR["swarm_start"]: P(raise_core, rA=aim(dirv(f=1.0, u=0.62, r=-0.1)), h=(-26, 0, 0), b=(-9, 0, 0)),
        0.58: cross,
        1.05: cross2,
        1.5: P(cross, b=(18, 0, 0)),
        1.82: spread,
        wf: P(spread, rA=aim(dirv(r=1.0, u=-0.1, f=0.2)), lA=aim(dirv(r=-1.0, u=-0.1, f=0.2))),
        2.35: hero,
        2.8: P(hero, b=(2, -16, 0)),
        3.0: H,
    }, kind="pose")

    # ---- 解除（1.0 秒）: 腕がほどけ、息をつく ---------------------------------------------------
    L["revert"] = anim(1.0, {
        0.0: H,
        0.15: P(rA=aim(dirv(r=0.5, u=-1.0, f=0.1)), lA=aim(dirv(r=-0.5, u=-1.0, f=0.1)), b=(-8, 0, 0),
                h=(-18, 0, 0)),
        0.55: P(rA=aim(dirv(r=0.15, u=-1.0, f=0.1)), lA=aim(dirv(r=-0.15, u=-1.0, f=0.1)), b=(12, 0, 0),
                h=(16, 0, 0), root_pos=(0, -0.6, 0)),
        1.0: H,
    }, kind="pose")

    # ---- 二段ジャンプ（前宙 0.45 秒） ----------------------------------------------------------
    tuck_arms = P(rA=(-40, 0, 14), lA=(-40, 0, -14))
    fr = flip(0.0, 0.45, 1.0, "x", base=tuck_arms)
    fr[0.0] = H
    fr[0.45] = P(root=(360, 0, 0))
    L["airjump"] = anim(0.45, fr, kind="move", blend=False)

    # ---- ブースト・ダッシュ（前傾の突進 0.5 秒） ------------------------------------------------
    boost = P(w=(34, 0, 0), h=(-30, 0, 0), rA=(42, 0, 16), lA=(42, 0, -16), rL=(16, 0, 3), lL=(34, 0, -3))
    L["boost"] = anim(0.5, {0.0: H, 0.06: boost, 0.38: P(boost, w=(30, 0, 0), lL=(30, 0, -3)), 0.5: H},
                      kind="move")

    # ---- ホバー（ループ 2.0 秒）: 膝を曲げたように脚を前後に、腕は少し開く ----------------------
    hov = P(rA=(-24, 0, 16), lA=(-8, 0, -18), rL=(-24, 0, 5), lL=(20, 0, -5), b=(5, 0, 0), h=(-4, 0, 0))
    L["hover"] = anim(2.0, {
        0.0: P(hov, root_pos=(0, 0, 0)),
        0.5: P(hov, root_pos=(0, 0.6, 0), rL=(-28, 0, 5), lL=(16, 0, -5), lA=(-8, 0, -22)),
        1.0: P(hov, root_pos=(0, 0.1, 0)),
        1.5: P(hov, root_pos=(0, -0.4, 0), rL=(-20, 0, 5), lL=(24, 0, -5), lA=(-8, 0, -14)),
        2.0: P(hov, root_pos=(0, 0, 0)),
    }, kind="move", loop=True)

    # ---- 回避ステップ（0.35 秒）: 沈み込んで低く跳ぶ --------------------------------------------
    step = P(w=(18, 0, 0), h=(-14, 0, 0), rA=(-38, 0, 30), lA=(-30, 0, -34), rL=(-30, 0, 12), lL=(24, 0, -12),
             ground=True)
    L["step"] = anim(0.35, {0.0: H, 0.06: step, 0.2: P(step, w=(14, 0, 0)), 0.35: H}, kind="move")

    # ---- 着地（ヒーロー着地 0.8 秒）: 片膝をつき、左の拳を地面へ ---------------------------------
    kneel = P(w=(32, 0, 0), h=(-34, 0, 0), b=(4, 0, 0),
              rL=(62, 0, 6), lL=(-58, 0, -6),
              lA=aim(dirv(f=0.55, u=-1.0, r=-0.2)),
              rA=wield(blade=dirv(r=0.55, f=-0.8, u=-0.12), arm=dirv(r=0.8, u=-0.6, f=-0.25)), ground=True)
    L["land"] = anim(0.8, {
        0.0: P(kneel, w=(14, 0, 0), rL=(30, 0, 6), lL=(-30, 0, -6), ground=True),
        0.06: kneel,
        0.45: P(kneel, w=(30, 0, 0), h=(-30, 0, 0)),
        0.8: H,
    }, kind="move")

    # ---- ナノ・バリア（0.8 秒）: 武器を立てて構え、左腕を重ねて十字に --------------------------
    guard = P(rA=wield(blade=dirv(u=1.0, f=0.25, r=-0.15), arm=dirv(f=1.0, u=-0.15, r=-0.25)),
              lA=aim(dirv(f=1.0, u=0.55, r=0.45), twist=25), b=(10, 0, 0), h=(12, 0, 0),
              rL=(-22, 0, 9), lL=(16, 0, -9), ground=True)
    L["barrier"] = anim(0.8, {0.0: H, 0.07: guard, 0.62: P(guard, b=(8, 0, 0)), 0.8: H})

    # ---- 必殺の掲げ（1.2 秒）: 武器を天へ ----------------------------------------------------
    rise = P(rA=wield(blade=dirv(u=1.0, f=0.12), arm=dirv(u=1.0, f=0.4, r=0.1)),
             lA=aim(dirv(f=0.6, u=-0.6, r=-0.5), twist=20), b=(-10, 0, 0), h=(-30, 0, 0),
             rL=(-6, 0, 10), lL=(6, 0, -10), ground=True)
    L["ult_rise"] = anim(1.2, {0.0: H, 0.25: rise, 0.95: P(rise, b=(-12, 0, 0), h=(-34, 0, 0)), 1.2: H})

    # ---- 掲げる（0.7 秒）: 片手を高く（武器の先を空へ）------------------------------------------
    cast = P(rA=wield(blade=dirv(u=1.0, f=0.5, r=0.1), arm=dirv(u=1.0, f=0.55, r=0.15)),
             lA=(-10, 0, -22), b=(-6, 0, 0), h=(-20, 0, 0))
    L["cast"] = anim(0.7, {0.0: H, 0.15: cast, 0.5: P(cast, b=(-8, 0, 0)), 0.7: H})

    # ---- 投げる（0.55 秒）: 右後ろへ引き、頭の右を通して前へ投げる（長柄でも頭に当たらない横手投げ） ----
    L["throw"] = anim(0.55, {
        0.0: H,
        0.13: P(rA=wield(blade=dirv(f=-0.45, r=0.35, u=0.8), arm=dirv(r=0.8, f=-0.3, u=0.5)),
                lA=aim(dirv(f=1.0, u=0.15, r=-0.15)), b=(-4, 36, 0), h=(0, -30, 0), rL=(14, 0, 6),
                lL=(-20, 0, -6), ground=True),
        0.21: P(rA=wield(blade=dirv(r=0.8, f=0.55, u=0.15), arm=dirv(r=1.0, f=0.2, u=0.25)),
                lA=aim(dirv(f=0.6, u=-0.4, r=-0.5)), b=(4, 6, 0), h=(0, -4, 0), rL=(16, 0, 6),
                lL=(-26, 0, -6), ground=True),
        0.29: P(rA=wield(blade=dirv(f=1.0, r=0.05, u=-0.1), arm=dirv(f=0.85, r=0.4, u=0.0)),
                lA=aim(dirv(f=-0.3, u=-1.0, r=-0.4)), b=(14, -24, 0), h=(-8, 22, 0),
                rL=(18, 0, 6), lL=(-30, 0, -6), root_pos=(0, 0, -1.0), ground=True),
        0.4: P(rA=wield(blade=dirv(f=0.8, r=0.4, u=-0.45), arm=dirv(f=0.55, r=0.55, u=-0.65)),
               lA=aim(dirv(f=-0.3, u=-1.0, r=-0.4)), b=(12, -18, 0), h=(-6, 16, 0),
               rL=(16, 0, 6), lL=(-26, 0, -6), root_pos=(0, 0, -1.0), ground=True),
        0.55: H,
    })

    # ---- 叩きつける（0.8 秒）: 跳んで頭上から地面へ ---------------------------------------------
    up = P(rA=wield(blade=dirv(u=0.7, f=-0.7, r=0.1), arm=dirv(u=1.0, f=0.1, r=0.3)),
           lA=aim(dirv(u=1.0, f=0.25, r=-0.15)),
           b=(-16, 0, 0), h=(-20, 0, 0), rL=(-30, 0, 0), lL=(-12, 0, 0), root_pos=(0, 2.4, 0))
    down = P(rA=wield(blade=dirv(f=1.0, u=-0.95), arm=dirv(f=1.0, u=-0.75)),
             lA=aim(dirv(f=0.7, u=-1.0, r=0.15)), w=(30, 0, 0), h=(-24, 0, 0),
             rL=(-46, 0, 8), lL=(40, 0, -8), ground=True)
    over = P(up, rA=wield(blade=dirv(u=0.8, f=0.45, r=0.15), arm=dirv(u=0.9, f=0.45, r=0.45)), b=(-4, 0, 0),
             root_pos=(0, 1.6, 0))
    rise = P(rA=wield(blade=dirv(f=0.6, u=-0.45, r=0.65), arm=dirv(r=0.75, u=-0.65, f=0.1)), w=(10, 0, 0),
             h=(-8, 0, 0), rL=(-14, 0, 6), lL=(12, 0, -6), ground=True)
    L["slam"] = anim(0.8, {0.0: H, 0.2: up, 0.27: over, 0.34: down, 0.58: P(down, w=(28, 0, 0)), 0.7: rise,
                           0.8: H})

    # ---- 突き（0.45 秒）: 踏み込んで真っすぐ ---------------------------------------------------
    pull = P(rA=wield(blade=dirv(f=1.0, u=0.05), arm=dirv(f=-0.6, u=-1.0, r=0.35)),
             lA=aim(dirv(f=1.0, u=0.1, r=0.1)), b=(0, 24, 0), h=(0, -20, 0))
    lunge = P(rA=wield(blade=dirv(f=1.0, u=-0.02), arm=dirv(f=1.0, u=0.05, r=-0.05)),
              lA=aim(dirv(f=-0.6, u=-1.0, r=-0.5)), b=(16, -20, 0), h=(-14, 16, 0),
              rL=(30, 0, 4), lL=(-42, 0, -4), root_pos=(0, 0, -1.5), ground=True)
    L["thrust"] = anim(0.45, {0.0: H, 0.1: pull, 0.2: lunge, 0.32: P(lunge, b=(14, -18, 0)), 0.45: H})

    # ---- 回転斬り（0.5 秒、一回転）: 武器の腕を横へ伸ばして全身で回る ---------------------------
    out_arm = P(rA=wield(blade=dirv(r=1.0, f=0.35, u=-0.05), arm=dirv(r=1.0, f=0.35, u=-0.15)),
                lA=aim(dirv(r=-1.0, u=-0.4, f=-0.2)), b=(6, 0, 0), rL=(-14, 0, 8), lL=(14, 0, -8))
    L["spin"] = anim(0.5, {
        0.0: H,
        0.06: P(out_arm, root=(0, 30, 0)),
        0.18: P(out_arm, root=(0, -120, 0)),
        0.3: P(out_arm, root=(0, -250, 0)),
        0.42: P(out_arm, root=(0, -340, 0)),
        0.5: P(root=(0, -360, 0)),
    }, blend=False)
    return L
