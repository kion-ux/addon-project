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
  大きく回る区間に自動でキーを足す）。

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
    一人称では体・頭・脚・全身は 0、腕は自然体からの差の 25%（画面が暴れないように）。

■ 公開 API
    H, P(*bases, **parts), anim(length, frames, kind="act", loop=False, blend=None)
    aim(dir, twist=0), wield(blade, arm=None, edge=None, roll=0), dirv(f, u, r), flip(...)
    resolve(spec, wkind="sword", name="", hold=None, cloud=None) -> Resolved
                                    部位ごとのトラック（絶対値の Euler）。cloud（武器の表面の点）を渡すと
                                    wield の腕を体に入らない向きへ回し、補間の途中で入るコマにキーを足す
    to_json(res) -> 統合版のアニメーション dict
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


def _repair(res, cloud, hold, rounds=16, step=0.02):
    """統合版と同じ catmullrom で 0.02 秒ごとに調べ、武器が体に入るコマに腕のキーを足して直す。"""
    if cloud is None or "rA" not in res.tracks:
        return
    tr = res.tracks["rA"]
    blade_l = np.asarray(hold["blade_arm"], float)
    tried = set()
    first, last = min(tr), max(tr)
    for _ in range(rounds):
        worst = (REPAIR_AT, None)
        n = max(2, int(math.ceil(res.length / step)))
        for i in range(1, n):
            t = res.length * i / n
            d, _b = clip_depth(sample(res, t), cloud)
            if d > worst[0] + 1e-6:
                worst = (d, round(t, 3))
        t = worst[1]
        if t is None:
            break
        near = min(tr, key=lambda x: abs(x - t))
        if abs(near - t) < 0.012:
            if near in tried or near in (first, last):
                # 自然体のキー（最初・最後）や一度直したキーは動かさない: 少しずらした所に足す
                t = round(t + (0.015 if t < near or near == first else -0.015), 3)
                if t <= first or t >= last or t in tr:
                    break
            else:
                t = near
        tried.add(t)
        parts = sample_parts(res, t)
        R_cur = rot(*parts["rA"])
        bt = R_cur @ blade_l
        R = _clear(R_cur, bt, R_cur @ ARM_DOWN, ARM_DOWN, parts, cloud, blade_l=blade_l)
        tr[t] = tuple(float(x) for x in euler_near(R, np.array(parts["rA"])))
        res.mats["rA"][t] = R
        refine_euler(res.tracks, res.mats)


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
    if cloud is not None:
        _repair(res, cloud, hold if hold is not None else _hold_info(wkind))
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
    refine_euler(tracks, mats)


EULER_TOL = 6.0      # 統合版はオイラー角を成分ごとに補間する。回転のままの補間とこれ以上ずれる所にはキーを足す


def _rot_angle(Ra, Rb):
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(Ra.T @ Rb) - 1) / 2))))


def refine_euler(tracks, mats, depth=6):
    """腕のトラックで、オイラー角の成分ごとの補間が回転のままの補間（slerp）から EULER_TOL° 以上ずれる区間に、
    slerp の中点のキーを足す（表し方は両端の平均に最も近い物）。ジンバルロックの近くで腕が暴れて武器が
    体を通り抜けるのを防ぐ。行列から出したキー（aim / wield / 直し）を端に持つ区間だけ。"""
    for k in ARMS:
        if k not in tracks:
            continue
        tr = tracks[k]
        mk = mats.setdefault(k, {})

        def split(a, b, d):
            ea, eb = np.array(tr[a]), np.array(tr[b])
            Ra, Rb = rot(*ea), rot(*eb)
            qa, qb = _quat(Ra), _quat(Rb)
            worst = max(_rot_angle(rot(*(ea + (eb - ea) * s_)), _mat(_slerp(qa, qb, s_)))
                        for s_ in (0.25, 0.5, 0.75))
            if worst < EULER_TOL or d == 0:
                return
            m = round((a + b) / 2, 3)
            if m <= a or m >= b:
                return
            Rm = _mat(_slerp(qa, qb, 0.5))
            tr[m] = tuple(float(x) for x in euler_near(Rm, (ea + eb) / 2))
            mk[m] = Rm
            split(a, m, d - 1)
            split(m, b, d - 1)
        ts = sorted(tr)
        for a, b in zip(ts, ts[1:]):
            if mk.get(a) is not None or mk.get(b) is not None:
                split(a, b, depth)


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


def _chan(part, axis, value, kind):
    """1 チャンネルの値（数か Molang）。value は絶対値。"""
    rest = REST.get(part, (0.0, 0.0, 0.0))[axis]
    delta = value - rest
    if part in ARMS:
        terms = [num(delta)] if abs(delta) > 1e-6 else []
        if kind in ("act", "pose") and (part, axis) in WALK_CANCEL:
            terms.append(WALK_CANCEL[(part, axis)])
        if kind == "act" and (part, axis) in ATK_CANCEL:
            terms.append(ATK_CANCEL[(part, axis)])
        if not terms:
            return 0
        tp = " + ".join(terms)
        return f"v.is_first_person ? {num(delta * FPK)} : ({tp})"
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
        track = {}
        moved = False
        for t in sorted(tr):
            v = [_chan(part, i, tr[t][i], res.kind) for i in range(3)]
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
