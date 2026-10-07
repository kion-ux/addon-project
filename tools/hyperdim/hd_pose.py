# -*- coding: utf-8 -*-
"""全身モーションのキーポーズを、武器ごとに解き直す。

モーションは腕の角度で書いてあるが、武器は手首で固定されている（アタッチャブルは腕に
付いて一緒に回るだけ）。そのまま腕を大きく振ると、武器が頭や胴を通り抜けたり、
両手武器の左手が柄から離れたりする。そこで、手で書いたキーポーズを出発点にして
武器ごとに

  * 武器が頭・胴・脚・空いている腕に入り込まない
  * 両手武器は左の拳が柄の二つ目の握りに届く（左腕は解析的にそこへ向ける）
  * 刃の向きの指定（blade=(x,y,z)、体の向きで）があれば、なるべくその向きに
  * 書いた腕の向きからはなるべく離れない

となるよう、武器を持つ腕の角度を座標降下で探す。キーの間は統合版と同じ catmullrom で
補間して調べ、入り込むところにはその時刻のキーを足して解き直す。

座標と規則は hd_space / hd_scene と同じ（体の正面が -Z、+Y が上、-X がプレイヤーの右）。
"""
from __future__ import annotations

import math

import numpy as np

from hd_common import RP
from hd_scene import SKELETON, load_geo, skeleton_world, weapon_quads
from hd_space import OFF_L, OFF_R, bone_local, mat4, rot

LIMIT = 0.6            # これより深く入り込んだら「めり込み」（px）
MARGIN = 0.0           # 解くときはこれより浅くする
REPAIR = 0.4           # 補間の途中でこれより深ければキーを足す（LIMIT より手前で）
BMAP = {"rA": "rightArm", "lA": "leftArm", "b": "body", "h": "head", "rL": "rightLeg",
        "lL": "leftLeg", "root": "root", "w": "waist"}
INFLATE = {"head": 0.5, "body": 0.25, "rightArm": 0.25, "leftArm": 0.25, "rightLeg": 0.25, "leftLeg": 0.25}
UPPER = {"rightArm": ((-8, 17, -2), (4, 7, 4)), "leftArm": ((4, 17, -2), (4, 7, 4))}
R_PIV, R_FIST = np.array([-5.0, 22.0, 0.0]), np.array([-6.0, 12.6, 0.0])
L_PIV, L_FIST = np.array([5.0, 22.0, 0.0]), np.array([6.0, 12.6, 0.0])
# 握りは拳の中心（hd_space.HAND_R / HAND_L）。右手の握りもここに置いてある
R_HAND, L_HAND = np.array([-6.0, 13.2, 0.0]), np.array([6.0, 13.2, 0.0])
ARM_LEN = float(np.linalg.norm(L_HAND - L_PIV))

# 握っている腕（その腕は上腕だけ調べる）。盾・かぎ爪は前腕に着けるので腕は調べない
GRIP_ARMS = {
    "greatsword": ("rightArm", "leftArm"), "greataxe": ("rightArm", "leftArm"),
    "twinblades": ("rightArm", "leftArm"), "claws": ("rightArm", "leftArm"),
    "dagger": ("rightArm",), "bow": ("rightArm",), "shield": ("rightArm",), "whip": ("rightArm",),
}
NO_ARM_CHECK = {"shield", "claws"}
DUAL = {"twinblades", "claws"}


# ---------------------------------------------------------------------------
#  補間（統合版の catmullrom）
# ---------------------------------------------------------------------------
def catmull(p0, p1, p2, p3, s):
    return 0.5 * (2 * p1 + (p2 - p0) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s
                  + (3 * p1 - p0 - 3 * p2 + p3) * s * s * s)


INTENT = ("hands", "blade")     # 両手武器の意図: 手の高さ（前の弧の上）と刃の向き


def keys_of(frames, hold):
    ks = set(hold)
    for f in frames.values():
        ks |= {k for k in f if k in BMAP or k == "root_pos" or k in INTENT}
    return ks


def sample(frames, hold, t):
    """絶対値のキー frames を時刻 t で評価（書かれていない部位は持ち姿勢）。"""
    times = sorted(frames, key=float)
    ts = [float(x) for x in times]
    out = {}
    for k in keys_of(frames, hold):
        vals = [np.array(frames[x].get(k, hold.get(k, (0, 0, 0))), float) for x in times]
        if t <= ts[0]:
            out[k] = vals[0]
        elif t >= ts[-1]:
            out[k] = vals[-1]
        else:
            i = max(j for j in range(len(ts)) if ts[j] <= t)
            s = (t - ts[i]) / (ts[i + 1] - ts[i])
            out[k] = catmull(vals[max(0, i - 1)], vals[i], vals[i + 1], vals[min(len(vals) - 1, i + 2)], s)
    return out


def sample_mono(frames, hold, t):
    """意図の補間（はみ出さない三次: Fritsch-Carlson）。キーの間で値が鍵の範囲を越えない。"""
    times = sorted(frames, key=float)
    ts = np.array([float(x) for x in times])
    out = {}
    for k in keys_of(frames, hold):
        vals = np.array([np.array(frames[x].get(k, hold.get(k, (0, 0, 0))), float) for x in times])
        if t <= ts[0]:
            out[k] = vals[0]
            continue
        if t >= ts[-1]:
            out[k] = vals[-1]
            continue
        i = int(np.searchsorted(ts, t, side="right") - 1)
        h = ts[i + 1] - ts[i]
        u = (t - ts[i]) / h

        def tangent(j):
            if j == 0 or j == len(ts) - 1:
                return np.zeros_like(vals[0])
            d0 = (vals[j] - vals[j - 1]) / (ts[j] - ts[j - 1])
            d1 = (vals[j + 1] - vals[j]) / (ts[j + 1] - ts[j])
            same = d0 * d1 > 0
            m = np.zeros_like(d0)
            m[same] = 2.0 * d0[same] * d1[same] / (d0[same] + d1[same])   # 調和平均（同じ向きの時だけ）
            return m
        m0, m1 = tangent(i), tangent(i + 1)
        h00, h10 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u
        h01, h11 = -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        out[k] = h00 * vals[i] + h10 * h * m0 + h01 * vals[i + 1] + h11 * h * m1
    return out


def pose_of(p):
    out = {}
    for k, v in p.items():
        if k == "root_pos":
            out.setdefault("root", {})["position"] = tuple(v)
        elif k in BMAP:
            out.setdefault(BMAP[k], {})["rotation"] = tuple(v)
    return out


# ---------------------------------------------------------------------------
#  武器の表面（手のボーン空間の点群）
# ---------------------------------------------------------------------------
def surface_points(quads, step, tags=None):
    pts = []
    for q in quads:
        p0, p1, _p2, p3 = (np.asarray(v, float) for v in q[0])
        a, b = p1 - p0, p3 - p0
        nu = max(2, min(24, int(math.ceil(np.linalg.norm(a) / step)) + 1))
        nv = max(2, min(24, int(math.ceil(np.linalg.norm(b) / step)) + 1))
        U, V = np.meshgrid(np.linspace(0, 1, nu), np.linspace(0, 1, nv))
        pts.append(p0 + U.reshape(-1, 1) * a + V.reshape(-1, 1) * b)
        if tags is not None:
            tags.extend([q[3]] * (nu * nv))
    return np.vstack(pts) if pts else np.zeros((0, 3))


def attach_pose(holds, name, use=False):
    """アタッチャブルの tp（または tp_use）と、待機の形（鞭のとぐろ）。"""
    h = holds[name]["use"] if use else holds[name]
    s = h["tp"]["scale"]
    a = {"hold": {"rotation": h["tp"]["rotation"], "position": h["tp"]["position"], "scale": (s, s, s)}}
    if "left_tp" in h:
        ls = h["left_tp"]["scale"]
        a["hold_l"] = {"rotation": h["left_tp"]["rotation"], "position": h["left_tp"]["position"],
                       "scale": (ls, ls, ls)}
    if name == "whip":
        for i in range(14):
            a[f"seg{i}"] = {"rotation": (40 if i == 0 else 22, 0, 0)}
    return a


class Cloud:
    """武器の表面の点（右手・左手それぞれのボーン空間）と、刃の向き・二つ目の握り。"""

    def __init__(self, holds, name, use=False, step=1.0, tags=False):
        from PIL import Image
        self.name = name
        geo = load_geo(f"{RP}/models/entity/hd_{name}.geo.json")
        tex = Image.new("RGBA", (geo["description"]["texture_width"], geo["description"]["texture_height"]))
        ident = {"rightItem": np.eye(4), "leftItem": np.eye(4)}
        anim = attach_pose(holds, name, use)
        hide_arrow = ("arrow",) if (name == "bow" and not use) else ()
        self.parts, self.tags = {}, {}
        sides = [("right", ("hold_l",) + hide_arrow)]
        if any(b["name"] == "hold_l" for b in geo["bones"]):
            sides.append(("left", ("hold",)))
        self.chunks = {}
        for side, hide in sides:
            tg = []
            p = surface_points(weapon_quads(geo, tex, ident, anim, hide=hide, tag=True), step, tg)
            # 柔らかい飾り（房・飾り紐）は揺れるので当たりに入れない
            keep = np.array([not t.startswith("tassel") for t in tg], bool)
            p = p[keep]
            tg = [t for t, k in zip(tg, keep) if k]
            self.parts[side] = np.c_[p, np.ones(len(p))].T          # 4 x N
            self.tags[side] = tg if tags else None
            # キューブごとの塊（中心と半径）: 体の箱から遠い塊は調べない
            names = sorted(set(tg))
            idx = {n: i for i, n in enumerate(names)}
            which = np.array([idx[t] for t in tg], int)
            cen = np.zeros((4, len(names)))
            rad = np.zeros(len(names))
            for i in range(len(names)):
                q = p[which == i]
                c = q.mean(axis=0)
                cen[:3, i] = c
                cen[3, i] = 1.0
                rad[i] = float(np.linalg.norm(q - c, axis=1).max())
            self.chunks[side] = (which, cen, rad)
        # 武器空間 → 手のボーン空間（刃の向き = 武器の -Z、握りの点）
        hh = holds[name]["use"] if use else holds[name]
        h = hh["tp"]
        self.item = mat4(t=OFF_R) @ bone_local((0, 0, 0), h["rotation"], h["position"], (h["scale"],) * 3)
        self.item_l = None
        if "left_tp" in hh:
            h = hh["left_tp"]
            self.item_l = mat4(t=OFF_L) @ bone_local((0, 0, 0), h["rotation"], h["position"], (h["scale"],) * 3)
        self.grip2 = holds[name].get("grip2")
        self.l_base = tuple(holds[name].get("arm_l", (0, 0, 0)))
        self.r_base = tuple(holds[name].get("arm_r", (0, 0, 0)))


def weapon_points(name, step=1.0):
    """武器空間（握り = 原点、刃先 = -Z）の表面の点（4 x N）。両手武器の持ち方を決めるのに使う。"""
    from PIL import Image
    geo = load_geo(f"{RP}/models/entity/hd_{name}.geo.json")
    tex = Image.new("RGBA", (geo["description"]["texture_width"], geo["description"]["texture_height"]))
    p = surface_points(weapon_quads(geo, tex, None, {}, hide=("hold_l", "arrow")), step)
    return np.c_[p, np.ones(len(p))].T


def arm_world(rA, piv=R_PIV):
    return bone_local(piv, rA)


# ---------------------------------------------------------------------------
#  左腕を点へ向ける（ねじれ 0）
# ---------------------------------------------------------------------------
def aim_arm(target, pivot=L_PIV, fist=L_HAND, prefer=(0, 0, 0)):
    """拳が target の方を向く腕の回転 (rx, ry, 0) と、届かなさ（px）。"""
    d = np.asarray(target, float) - pivot
    dist = float(np.linalg.norm(d)) or 1e-6
    d = d / dist
    a = (fist - pivot) / np.linalg.norm(fist - pivot)
    c = max(-1.0, min(1.0, d[1] / a[1]))
    best = None
    for sgn in (1, -1):
        rx = sgn * math.degrees(math.acos(c))
        v = np.array([a[0], -a[1] * math.sin(math.radians(rx))])        # (x, z)
        ry = math.degrees(math.atan2(v[1], v[0]) - math.atan2(d[2], d[0]))
        cand = np.array([rx, ry, 0.0])
        cand = unwrap(cand, prefer)
        dd = float(np.abs(cand - np.asarray(prefer, float)).sum())
        if best is None or dd < best[0]:
            best = (dd, cand)
    return tuple(best[1]), abs(dist - ARM_LEN)


def shortest_arc(a, b):
    """a を b へ最短で回す回転行列。"""
    a = np.asarray(a, float) / np.linalg.norm(a)
    b = np.asarray(b, float) / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.999999:
        p = np.cross(a, [1.0, 0.0, 0.0])
        if np.linalg.norm(p) < 1e-6:
            p = np.cross(a, [0.0, 1.0, 0.0])
        p /= np.linalg.norm(p)
        return 2.0 * np.outer(p, p) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1.0 + c)


def aim_arm_from(target, base, near, pivot=L_PIV, fist=L_HAND):
    """基準の姿勢 base から最小の回転で拳を target の方へ向ける。ねじれは向きだけで決まる
    （通ってきた道に依らない）ので、構えに戻った時に腕がねじれ戻らない。
    オイラー角は near（前のキー）に最も近い表し方にして、キーの間の補間が跳ばないようにする。"""
    d = np.asarray(target, float) - pivot
    dist = float(np.linalg.norm(d)) or 1e-6
    a0 = (fist - pivot) / np.linalg.norm(fist - pivot)
    R_ref = rot(*base)
    R = shortest_arc(R_ref @ a0, d) @ R_ref
    return tuple(float(x) for x in euler_near(R, near)), abs(dist - ARM_LEN)


def unwrap(e, ref):
    """角度を ref に近い表し方（±360）へ。"""
    e = np.array(e, float)
    ref = np.asarray(ref, float)
    return e - 360.0 * np.round((e - ref) / 360.0)


def euler_near(R, ref):
    """回転行列を ref に最も近いオイラー角（2 通りの分解 × 360° の巻き）で。"""
    from hd_space import euler
    a, b, c = euler(R)
    cands = [np.array([a, b, c]), np.array([a + 180.0, 180.0 - b, c + 180.0])]
    cands = [unwrap(x, ref) for x in cands]
    return min(cands, key=lambda x: float(np.abs(x - ref).sum()))


# ---------------------------------------------------------------------------
#  めり込みの深さ
# ---------------------------------------------------------------------------
def body_boxes(W, name):
    held = GRIP_ARMS[name]
    out = []
    for bone, _parent, _pivot, cube in SKELETON:
        if not cube:
            continue
        o, s, _col = cube
        inf = INFLATE.get(bone, 0.0)
        if bone in ("rightArm", "leftArm"):
            if name in NO_ARM_CHECK:
                continue
            if bone in held:
                o, s = UPPER[bone]
                inf = 0.0
        lo = np.array(o, float) - inf
        hi = lo + np.array(s, float) + 2 * inf
        out.append((bone, np.linalg.inv(W[bone]), lo, hi))
    return out


def penetration(cloud, W, name, detail=False, only=None):
    """(最大の深さ, 部位, 側)。detail なら (部位, 武器のキューブ) ごとの深さも。only: "right"/"left" だけ調べる。"""
    worst = (0.0, None, None)
    parts = {}
    boxes = body_boxes(W, name)
    for side, pts in cloud.parts.items():
        if only and side != only:
            continue
        pw = W["rightItem" if side == "right" else "leftItem"] @ pts
        for bone, inv, lo, hi in boxes:
            q = (inv @ pw)[:3].T
            d = np.clip(np.minimum(q - lo, hi - q).min(axis=1), 0, None)
            m = float(d.max()) if len(d) else 0.0
            if detail and m > LIMIT and cloud.tags[side] is not None:
                for i in np.nonzero(d > LIMIT)[0]:
                    k = (bone, cloud.tags[side][i])
                    parts[k] = max(parts.get(k, 0.0), float(d[i]))
            if m > worst[0]:
                worst = (m, bone, side)
    return (worst, parts) if detail else worst


# ---------------------------------------------------------------------------
#  1 キーを解く
# ---------------------------------------------------------------------------
def arm_dir(r, piv, fist):
    A = bone_local(piv, r)
    return (A[:3, :3] @ (fist - piv)) / np.linalg.norm(fist - piv)


def blade_dir(cloud, W, side="right"):
    """武器の -Z（刃先の向き）を体の root 空間で。"""
    M = W["rightItem"] @ cloud.item if side == "right" else W["leftItem"] @ cloud.item_l
    root_inv = np.linalg.inv(W["root"])[:3, :3]
    d = root_inv @ (M[:3, :3] @ np.array([0.0, 0.0, -1.0]))
    return d / np.linalg.norm(d)


def left_on_grip(cloud, rA, near):
    """両手武器: 右腕 rA のとき、左の拳を柄の二つ目の握りへ。体空間で解ける（両腕とも体の子）。
    左腕は構え（cloud.l_base）から最小の回転で向ける。near は前のキーの左腕。"""
    g = np.array([*cloud.grip2, 1.0])
    T = (arm_world(rA) @ cloud.item @ g)[:3]
    return aim_arm_from(T, cloud.l_base, near)


# 両手で一本の柄を握れるのは、両肩から腕の長さ（拳の中心まで 8.86）の所が交わる
# 体の正面の弧の近くだけ（中心 (0,22,0)、半径 √(8.86²-5²)≈7.3、x=0 の面）。
ARC_R = 7.0


def arc_target(phi, hx=-1.5):
    """手の高さ phi（度。0 = 肩の高さで真正面、+ が上）の、右の拳の目標（体空間）。"""
    a = math.radians(phi)
    return np.array([hx, 22.0 + ARC_R * math.sin(a), -ARC_R * math.cos(a)])


def hands_of(rA):
    """右腕 rA のときの右の拳の (phi, x)。"""
    p = (bone_local(R_PIV, rA) @ np.array([*R_HAND, 1.0]))[:3]
    return math.degrees(math.atan2(p[1] - 22.0, -p[2])), float(p[0])


class _Fast:
    """1 キーを解く間の速い評価。動かす腕以外（体・頭・脚・もう一方の腕）の箱は固定なので先に作り、
    武器の点群は箱ごとに「箱の逆行列 × 手の行列」を一度掛けるだけにする。遠い箱は球で弾く。"""

    def __init__(self, cloud, name, pose, side):
        self.cloud, self.name, self.side = cloud, name, side
        self.W0 = skeleton_world(pose_of(pose))
        self.pts = cloud.parts[side]
        held = GRIP_ARMS[name]
        self.fixed, self.moving = [], []
        for bone, _parent, _pivot, cube in SKELETON:
            if not cube:
                continue
            o, sz, _col = cube
            inf = INFLATE.get(bone, 0.0)
            if bone in ("rightArm", "leftArm"):
                if name in NO_ARM_CHECK:
                    continue
                if bone in held:
                    o, sz = UPPER[bone]
                    inf = 0.0
            lo = np.array(o, float) - inf
            hi = lo + np.array(sz, float) + 2 * inf
            box = (bone, lo, hi, (lo + hi) / 2, float(np.linalg.norm(hi - lo)) / 2)
            (self.moving if bone in ("rightArm", "leftArm") else self.fixed).append(box)
        self.fixed_inv = [(b, np.linalg.inv(self.W0[b[0]]), (self.W0[b[0]] @ np.array([*b[3], 1.0]))[:3])
                          for b in self.fixed]

    def depth(self, arms):
        """arms: {"rightArm": 体空間の行列, "leftArm": ...}。武器のこの側の最大の入り込み。"""
        Wb = self.W0["body"]
        W = {k: Wb @ v for k, v in arms.items()}
        item = W.get("rightArm" if self.side == "right" else "leftArm",
                     self.W0["rightItem" if self.side == "right" else "leftItem"])
        which, cen, rad = self.cloud.chunks[self.side]
        cw = (item @ cen)[:3]                                   # 塊の中心（世界）
        worst = 0.0
        boxes = [(b, inv, midw) for b, inv, midw in self.fixed_inv]
        for b in self.moving:
            Wbone = W.get(b[0], self.W0[b[0]])
            boxes.append((b, np.linalg.inv(Wbone), (Wbone @ np.array([*b[3], 1.0]))[:3]))
        for (bone, lo, hi, mid, half), inv, midw in boxes:
            near = np.linalg.norm(cw - midw[:, None], axis=0) <= rad + half + 0.3
            if not near.any():
                continue
            pts = self.pts[:, near[which]]
            q = ((inv @ item) @ pts)[:3]
            d = np.minimum(q - lo[:, None], hi[:, None] - q).min(axis=0)
            m = float(d.max())
            if m > worst:
                worst = m
        return worst


def solve_key(cloud, name, pose, opts=None, prev=None):
    return solve_key2(cloud, name, pose, opts, prev)[0]


def solve_key2(cloud, name, pose, opts=None, prev=None, delta=None):
    """pose（絶対値の dict）を解き直す。返り値 (解いた dict, 補正 {"rA": Δ, "lA": Δ})。opts:
    free_l   両手武器でも左手を柄から離してよい
    blade    右の武器の刃の向き（root 空間）。blade_l は左手の武器
    keep     書いた腕の向きをどれだけ守るか（大きいほど動かさない）
    step     探し始めの刻み（度）
    prev は一つ前のキー（解いた後）。両手武器の左腕はそこから最小の回転で柄へ向ける。
    delta は一つ前のキーでの補正（書いた角度からのずれ）。補正が時間で滑らかに変わるよう、
    そこから探し始め、急に変えるほど高くつくようにする（キーの間で腕が跳ばない）。"""
    opts = dict(opts or {})
    pose = {k: tuple(v) for k, v in pose.items()}
    hands = pose.pop("hands", None)
    if "blade" in pose:
        opts["blade"] = pose.pop("blade")
    delta = delta or {}
    out_delta = {}
    l_ref = np.array((prev or pose).get("lA", (0, 0, 0)), float)
    two_hand = cloud.grip2 is not None and not opts.get("free_l")
    sides = ["right"] + (["left"] if name in DUAL else [])
    for side in sides:
        key = "rA" if side == "right" else "lA"
        piv, fist = (R_PIV, R_FIST) if side == "right" else (L_PIV, L_FIST)
        r0 = np.array(pose.get(key, (0, 0, 0)), float)
        first_step = opts.get("step", 24.0)
        if hands is not None and side == "right" and two_hand:
            # 手の高さの指定: 構えの腕から最小の回転で、右の拳を正面の弧の上へ
            near = np.array((prev or pose).get("rA", r0), float)
            r0 = np.array(aim_arm_from(arc_target(hands[0], hands[1]), cloud.r_base, near, R_PIV, R_HAND)[0])
            first_step = min(first_step, 8.0)
        dprev = np.asarray(delta.get(key, (0.0, 0.0, 0.0)), float)
        if np.any(dprev):
            first_step = min(first_step, 12.0)
        d0 = arm_dir(r0, piv, fist)
        want = opts.get("blade" if side == "right" else "blade_l")
        want = None if want is None else np.asarray(want, float) / np.linalg.norm(want)
        keep = opts.get("keep", 1.0)
        fast = _Fast(cloud, name, pose, side)
        root_inv = np.linalg.inv(fast.W0["root"])[:3, :3]
        item = cloud.item if side == "right" else cloud.item_l

        def arms_of(r):
            arms = {("rightArm" if side == "right" else "leftArm"): bone_local(piv, r)}
            gap = 0.0
            lA = None
            if two_hand and side == "right":
                lA, gap = left_on_grip(cloud, r, l_ref)
                arms["leftArm"] = bone_local(L_PIV, lA)
            return arms, gap, lA

        def cost(r):
            arms, gap, _lA = arms_of(r)
            depth = fast.depth(arms)
            c = 40.0 * max(0.0, depth - MARGIN) ** 2
            c += 3.0 * max(0.0, gap - 0.6) ** 2
            ang = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(arm_dir(r, piv, fist), d0))))))
            c += keep * (ang / 18.0) ** 2 + 0.15 * keep * float(np.sum(((r - r0) / 45.0) ** 2))
            # 補正の連続性（前のキーの補正からの変化）
            c += 0.6 * float(np.sum((((r - r0) - dprev) / 15.0) ** 2))
            if want is not None:
                A = fast.W0["body"] @ arms["rightArm" if side == "right" else "leftArm"] @ item
                bd = root_inv @ (A[:3, :3] @ np.array([0.0, 0.0, -1.0]))
                bd /= np.linalg.norm(bd)
                c += 1.6 * (math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(bd, want)))))) / 25.0) ** 2
            return c

        def descend(start, step):
            r = np.array(start, float)
            cur = cost(r)
            while step >= 0.75:
                improved = True
                while improved:
                    improved = False
                    for i in range(3):
                        for sgn in (-1.0, 1.0):
                            q = r.copy()
                            q[i] += sgn * step
                            c = cost(q)
                            if c < cur - 1e-9:
                                r, cur, improved = q, c, True
                step *= 0.5
            return r, cur

        r, cur = descend(r0 + dprev, first_step)
        if not np.any(dprev):
            pass
        else:
            r1, c1 = descend(r0, first_step)
            if c1 < cur:
                r, cur = r1, c1
        # まだ入り込んでいれば、少しずらした所からも探して一番良いものを（局所解の回避）
        if fast.depth(arms_of(r)[0]) > MARGIN + 0.3:
            for dv in ((25, 0, 0), (-25, 0, 0), (0, 25, 0), (0, -25, 0), (0, 0, 25), (0, 0, -25)):
                r2, c2 = descend(r0 + dprev + np.array(dv, float), min(first_step, 12.0))
                if c2 < cur:
                    r, cur = r2, c2
        r = np.round(r, 1)
        pose[key] = tuple(r)
        if two_hand and side == "right":
            pose["lA"] = arms_of(r)[2]
        out_delta[key] = r - r0
    return {k: tuple(round(float(x), 1) for x in v) for k, v in pose.items()}, out_delta


def check(cloud, name, pose):
    W = skeleton_world(pose_of(pose))
    d = penetration(cloud, W, name)[0]
    gap = 0.0
    if cloud.grip2 is not None:
        g = np.array([*cloud.grip2, 1.0])
        T = (arm_world(pose.get("rA", (0, 0, 0))) @ cloud.item @ g)[:3]
        A = bone_local(L_PIV, pose.get("lA", (0, 0, 0)))
        fist = (A @ np.array([*L_HAND, 1.0]))[:3]
        # 拳の中心と柄の握りの距離
        gap = float(np.linalg.norm(fist - T))
    return d, gap


# ---------------------------------------------------------------------------
#  1 本のモーションを解く
# ---------------------------------------------------------------------------
def solve_anim(cloud, name, length, frames, hold, opts=None, key_opts=None, step=0.02, rounds=24):
    """frames: {t: 絶対値の dict（書かれていない部位は持ち姿勢）}。
    両端（持ち姿勢）以外の各キーを解き、補間の途中で入り込むところにキーを足す。"""
    opts = opts or {}
    key_opts = key_opts or {}
    times = sorted(frames, key=float)
    out = {}
    prev = hold
    two = cloud.grip2 is not None and not opts.get("free_l")
    if two and any("hands" in f for f in frames.values()):
        out = _solve_intent(cloud, name, length, frames, hold, opts)
    else:
        # 書いたキーを、はみ出さない補間で DENSE 秒ごとに刻んでから解く。疎なキーのままだと
        # 統合版の catmullrom が「止め」の区間で膨らみ（速い動きの直後ほど大きい）、武器が体に入る
        raw = {float(t): frames[t] for t in times}
        first, last = float(times[0]), float(times[-1])
        delta = {}
        ts = set(raw)
        n = max(1, int(round(length / DENSE))) if length > 0 else 0
        ts |= {round(first + (last - first) * k / n, 3) for k in range(n + 1)} if n else set()
        for t in sorted(ts):
            f = raw.get(t)
            o = dict(opts)
            o.update(key_opts.get(t, {}))
            if f is not None and (f is hold or (not f and t in (first, last))):
                out[t] = dict(hold)
            else:
                p = sample_mono({x: {k: v for k, v in raw[x].items() if k in BMAP or k == "root_pos"}
                                 for x in raw}, hold, t)
                out[t], delta = solve_key2(cloud, name, {k: tuple(v) for k, v in p.items()}, o, prev, delta)
            prev = out[t]
    two_hand = two
    tried, ignored = set(), []
    for _ in range(rounds):
        worst = (REPAIR, None)
        ts = sorted(out, key=float)
        for k in range(len(ts) - 1):
            a, b = float(ts[k]), float(ts[k + 1])
            n = max(2, int(math.ceil((b - a) / step)))
            for j in range(1, n):
                t = a + (b - a) * j / n
                if any(abs(t - x) < 0.006 for x in ignored):
                    continue
                p = sample(out, hold, t)
                d, gap = check(cloud, name, {kk: tuple(v) for kk, v in p.items()})
                score = d if not two_hand else max(d, (gap - 1.6) * 0.5 + REPAIR if gap > 1.6 else 0.0)
                if score > worst[0] + 1e-6:
                    worst = (score, round(t, 3))
        if worst[1] is None:
            break
        t = worst[1]
        keys = sorted(out, key=float)
        near = min(keys, key=lambda x: abs(float(x) - t))
        o = dict(opts, step=8.0)        # 補間の途中の修理は近くだけを探す（枝が跳ばないように）
        if abs(float(near) - t) < 0.008:
            # キーを詰めすぎると catmullrom が暴れるので、近くのキーそのものを解き直す（一度だけ）
            if near in tried or near in (keys[0], keys[-1]):
                ignored.append(t)
                continue
            tried.add(near)
            i = keys.index(near)
            o["step"] = 16.0
            out[near] = solve_key(cloud, name, dict(out[near]), o, out[keys[i - 1]] if i else hold)
            continue
        p = {kk: tuple(v) for kk, v in sample(out, hold, t).items()}
        before = [x for x in keys if float(x) < t]
        out[t] = solve_key(cloud, name, p, o, out[before[-1]] if before else hold)
    return out


DENSE = 0.05


def _solve_intent(cloud, name, length, frames, hold, opts):
    """両手武器: 手の高さ（弧の上）と刃の向きを時間で補間し、DENSE 秒ごとにキーを置いて解く。
    どのコマでも左の拳が柄に乗り、武器が体に入らないように。"""
    rA = hold["rA"]
    phi, hx = hands_of(rA)
    W = skeleton_world(pose_of(hold))
    base = dict(hold, hands=(phi, hx, 0.0), blade=tuple(blade_dir(cloud, W)))
    times = sorted(frames, key=float)
    ts = {float(t) for t in times}
    n = max(1, int(round(length / DENSE)))
    ts |= {round(length * k / n, 3) for k in range(n + 1)}
    first, last = float(times[0]), float(times[-1])
    raw = {float(t): frames[t] for t in times}
    out = {}
    prev = hold
    delta = {}
    for t in sorted(ts):
        if (t == first and not raw.get(first)) or (t == last and not raw.get(last)):
            out[t] = dict(hold)
            delta = {}
        else:
            p = sample_mono(raw, base, t)
            b = np.asarray(p["blade"], float)
            p["blade"] = tuple(b / (np.linalg.norm(b) or 1.0))
            out[t], delta = solve_key2(cloud, name, {k: tuple(v) for k, v in p.items()}, opts, prev, delta)
        prev = out[t]
    return out
