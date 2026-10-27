# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 飛び道具（nr_spec_catalog.WEAPONS の kind が bow / crossbow / gun / throwable の全部）を生成する。

近接の gen_nr_weapons.py と同じ道具箱（nr_weapon_common）・同じ置き場所・同じ形で、武器ごとに:
  RP  models/entity/weapons/<key>.geo.json      geometry.nr.w.<key>（1.16.0、hold(binding) → root）
  RP  textures/nr/weapons/<key>.png             テクスチャ（nr_paint ＋ 後処理: 陰・縁の照り・錆・煤・血）
  RP  textures/nr/items/<key>.png               アイコン（3D モデルを斜めから描いた 64×64 の透過 PNG）
  RP  attachables/weapons/<key>.attachable.json identifier = nr:w_<key>
  RP  animations/weapons/<key>.animation.json   持ち方（三人称・一人称・使う間）と待機（弓の弦・炎・火花の揺れ）
  BP  items/weapons/<key>.item.json             1.21.120 のアイテム（下の「アイテムの約束」）
  BP  recipes/weapons/<key>.recipe.json         spec に作業台レシピがあるものだけ（生存者の弓）
  断片 .frag/item_texture/gen_nr_weapons_ranged.json（nr_w_<key>）・.frag/lang/gen_nr_weapons_ranged.json

■ アイテムの約束（packs/nightrunner_BP/scripts/combat/ の ranged.js・throwables.js が nr:proj_* を自分で出して追う）
  * 全部に nr:weapon（耐久のフックと武器表の key）と minecraft:use_modifiers（使う間 = 溜め・引き絞り・押しっぱなしの
    連射。itemStartUse → itemReleaseUse / itemStopUse をスクリプトが読む）。
  * minecraft:shooter / minecraft:throwable / minecraft:projectile は**書かない**（エンジンがもう 1 発飛ばしてしまう）。
  * 銃・弓・クロスボウ: max_stack_size 1 ＋ minecraft:durability（弾倉 nr:mag は ItemStack の動的プロパティなので
    重ねられない物だけ）。投げ物: spec の stack まで重ねられ、耐久なし。弾（nr:ammo_*・nr:bolt・nr:survivor_arrow）と
    飛び道具のエンティティ・モデル（nr:proj_*、nr_proj_models.py）は gen_nr_items / gen_nr_entities の持ち物（ここでは作らない）。

■ 持ち方（三人称は gen_nr_player_anim.hold_arm_angles() の腕の絶対角との契約。アタッチャブルの変換はそこから逆算）
  * 銃（拳銃・長物・クロスボウ）: 契約どおり**銃身は右腕の芯に沿う**（肩 → 拳の延長。gen_nr_player_anim の
    STYLES["pistol"/"rifle"]）。腕に対する銃の向きは構え（hold_pistol / hold_rifle）でも狙い（*_aim）でも同じなので
    tp と tp_use は同じ変換。照準器（+Y）は腕を前へ水平に上げた時に世界の上を向く。長物は銃床が腕に刺さらないよう
    少し内側（体の側）へずらす。左手は構えの契約の角度のまま（長物の狙いでは銃の横に添える形）。
  * 弓: 契約どおり**右手**に持つ（左手が弦を引く。bow_draw → bow_hold）。tp は hold_bow（腕 -18°）で弓の上の弭が上・
    少し前、tp_use は引き絞り（bow_hold の腕）で弓を立て、矢の向き = 腕の向き。弦は v.nr_usew で後ろへ引かれる
    （待機アニメの弦のボーン）。
  * 投げ物: 片手（hold_1h = バニラの持ち姿勢）。振りかぶりはプレイヤーのモーション（throw_wind）が腕ごと動かすので
    tp_use = tp（手の中の物は動かさない）。

使い方:
  python3 tools/nightrunner/gen_nr_weapons_ranged.py                       # 全部書く（build_nr.py --only gen_nr_weapons_ranged と同じ）
  python3 tools/nightrunner/gen_nr_weapons_ranged.py --only pistol,molotov --preview
  （NR_PREVIEW=1 でも確認画像を描く）

確認画像（build_preview/nightrunner/）:
  weapons_ranged.png        全飛び道具の 3/4（テクスチャ付き、キューブ数とアトラス）
  weapons_ranged_held.png   三人称でプレイヤーに持たせた姿（構え・使う間）。めり込み（構え/使う間）と左手の距離を数字で
  weapons_ranged_fp.png     一人称の画面（構え・使う間）
  weapons_ranged_icons.png  アイコン（2 倍）
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import nr_paint as NP  # noqa: E402
import nr_weapon_common as WC  # noqa: E402
from nr_common import PREVIEW, SCRATCH  # noqa: E402
from nr_weapon_common import (band, beam, bolt, box, cbox, coil, disc, hex_prism, lash, nail,  # noqa: E402,F401
                              octo, polyline, rag, rbeam, ring_of, rivet, rod, weld, wrap)
import hd_space as HS  # noqa: E402  （nr_weapon_common が tools/hyperdim を sys.path に足している）
import hd_holds as HH  # noqa: E402
# 近接の生成器の模様の小物（手垢・煤・点・バーコード・落書き・ホースバンド）。import してもファイルは書かない
from gen_nr_weapons import (add_fx, barcode, dots, graffiti, grime, hose_clamp, soot,  # noqa: E402,F401
                            spec_blood, zline)

try:  # 登録データの入口（nr_spec が無い・作り直し中ならカタログを直接）
    import nr_spec as SPEC  # noqa: E402
    _WEAPONS = SPEC.WEAPONS
except Exception:  # noqa: BLE001
    import nr_spec_catalog as SPEC  # type: ignore  # noqa: E402
    _WEAPONS = SPEC.WEAPONS

PRODUCER = "gen_nr_weapons_ranged"
RANGED_KINDS = ("bow", "crossbow", "gun", "throwable")
RANGED = [w for w in _WEAPONS if w["kind"] in RANGED_KINDS]
BY_KEY = {w["key"]: w for w in RANGED}
ANIM_SETS = getattr(SPEC, "ANIM_SETS", {})


@dataclass
class Built:
    """builder の戻り値。hold は持ち方の関数（hold_gun / hold_bow / hold_throw）に渡す引数。"""
    wm: WC.WeaponModel
    book: WC.Stylebook
    blood: List[dict] = field(default_factory=list)
    hold: dict = field(default_factory=dict)
    icon_flip: bool = False
    icon_yaw: float = 72.0
    icon_roll: float = 0.0


BUILDERS: Dict[str, Callable[[dict], Built]] = {}


def builder(key: str):
    def deco(fn):
        BUILDERS[key] = fn
        return fn
    return deco


# ===========================================================================
#  持ち方の契約（gen_nr_player_anim.hold_arm_angles()。読めなければ写し）
# ===========================================================================
_HOLDS_FALLBACK = {
    "hold_1h": {"arm_r": (-18.0, 0.0, 0.0), "arm_l": None},
    "hold_bow": {"arm_r": (-18.0, 0.0, 0.0), "arm_l": None},
    "hold_pistol": {"arm_r": (-30.0, -6.0, 0.0), "arm_l": None},
    "hold_rifle": {"arm_r": (-30.0, -18.0, 0.0), "arm_l": (-62.0, 36.0, 0.0)},
    "bow_hold": {"arm_r": (-79.99, 13.93, 7.55), "arm_l": (-40.51, 59.77, 88.21)},
    "pistol_aim": {"arm_r": (-90.0, -10.0, 0.0), "arm_l": (-86.0, 36.0, 0.0)},
    "rifle_aim": {"arm_r": (-90.0, -6.0, 0.0), "arm_l": (-88.0, 38.0, 0.0)},
    "shotgun_aim": {"arm_r": (-90.0, -6.0, 0.0), "arm_l": (-88.0, 38.0, 0.0)},
    "crossbow_aim": {"arm_r": (-90.0, -6.0, 0.0), "arm_l": (-88.0, 38.0, 0.0)},
}
HOLD_WARNINGS: List[str] = []


def _load_holds() -> Dict[str, dict]:
    try:
        import gen_nr_player_anim as PA  # noqa: WPS433  （import しただけではファイルを書かない）
        h = {k: {"arm_r": tuple(v["arm_r"]), "arm_l": tuple(v["arm_l"]) if v.get("arm_l") else None}
             for k, v in PA.hold_arm_angles().items()}
    except Exception as err:  # noqa: BLE001
        HOLD_WARNINGS.append(f"gen_nr_player_anim を読めなかったので構えの写しを使う: {err!r}")
        h = {}
    for k, v in _HOLDS_FALLBACK.items():
        if k not in h:
            h[k] = dict(v)
        elif any(abs(a - b) > 0.05 for a, b in zip(h[k]["arm_r"], v["arm_r"])):
            HOLD_WARNINGS.append(f"{k}: 契約の腕が写しと違う（{h[k]['arm_r']} / {v['arm_r']}）— _HOLDS_FALLBACK を直すこと")
    return h


HOLDS = _load_holds()
# 腕の芯（肩の軸 → 拳の中心。腕の局所）。銃身・弓の矢はこれに沿う（gen_nr_player_anim の STYLES と同じ）
ARM_DIR = (HS.HAND_R - HH.ARM_R_PIVOT) / np.linalg.norm(HS.HAND_R - HH.ARM_R_PIVOT)
# 腕を前へ水平に上げた（rx = -90°）とき世界の上を向く腕の局所の向き（銃の照準器 +Y をここへ）
ARM_UP = np.array([0.0, 0.0, -1.0])
# 飛び道具の持ち方の型（nr_weapon_common の HOLD_STYLES に足す。アタッチャブルの逆算と確認画像だけが使う）
RANGED_STYLES = {"bow": "bow", "crossbow": "rifle", "pistol": "pistol", "shotgun": "rifle", "rifle": "rifle",
                 "smg": "rifle", "throw": "one_hand"}
for _k, _v in RANGED_STYLES.items():
    WC.HOLD_STYLES.setdefault(_k, _v)


def _tf(rot, pos, scale) -> dict:
    return {"rotation": tuple(round(float(x), 2) for x in rot), "position": tuple(round(float(x), 2) for x in pos),
            "scale": round(float(scale), 3)}


def _arm_tf(R_local, anchor, scale, nudge=(0.0, 0.0, 0.0)) -> dict:
    """腕の局所での武器の向き R_local（列 = 武器の X, Y, Z）と、拳に来る握りの点 anchor から変換を作る
    （腕の角度に依らない。nudge は腕の静止座標でのずらし）。"""
    rot = WC.euler_of(R_local)
    pos = HH.item_position((0.0, 0.0, 0.0), rot, tuple(anchor), nudge=tuple(nudge), scale=scale)
    return _tf(rot, pos, scale)


def _rot_about(v, axis, deg):
    """v を axis まわりに deg 度（右手系）。"""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    v = np.asarray(v, float)
    t = math.radians(deg)
    return v * math.cos(t) + np.cross(a, v) * math.sin(t) + a * (a @ v) * (1 - math.cos(t))


def fist_pos(arm, left=False) -> np.ndarray:
    """腕の角度 → 拳の中心（体の空間）。"""
    piv = HH.ARM_L_PIVOT if left else HH.ARM_R_PIVOT
    hand = HS.HAND_L if left else HS.HAND_R
    return (HS.bone_local(piv, arm) @ np.array([*hand, 1.0]))[:3]


def _fp(d: dict, anchor, scale) -> dict:
    return WC.fp_place_cam(d["fwd"], d["up"], d["cam_point"], anchor, d.get("scale", scale))


def hold_gun(wm: WC.WeaponModel, w: dict, *, scale: float, anchor=(0.0, 0.0, 0.0), nudge=(0.0, 0.0, 0.0),
             pitch: float = 0.0, yaw: float = 0.0, cant: float = 0.0, fp=None, use=None, fp_scale=None) -> dict:
    """銃・クロスボウ: 銃身（-Z）を右腕の芯に沿わせ、照準器（+Y）を ARM_UP へ（構えでも狙いでも同じ変換）。
    pitch / yaw は腕の芯からの小さなずれ（度）、cant は銃身まわりの傾き、nudge は腕の静止座標でのずらし
    （+X = 体の内側）。fp / use は一人称の上書き（fp_place_cam の引数）。"""
    st = ANIM_SETS.get(w["anim_set"], {})
    idle = st.get("idle", "hold_pistol")
    aim = st.get("aim")
    fwd = ARM_DIR.copy()
    side = np.cross(fwd, ARM_UP)
    if pitch:
        fwd = _rot_about(fwd, side, pitch)
    if yaw:
        fwd = _rot_about(fwd, ARM_UP, yaw)
    up = ARM_UP - fwd * float(ARM_UP @ fwd)
    if cant:
        up = _rot_about(up, fwd, cant)
    R = WC.frame(fwd, up)
    tf = _arm_tf(R, anchor, scale, nudge)
    long_gun = RANGED_STYLES.get(w["anim_set"]) == "rifle"
    s_fp = fp_scale or scale * (0.86 if long_gun else 0.95)
    if long_gun:
        fpd = dict(fwd=(-0.04, 0.03, 1.0), up=(0.08, 1.0, 0.0), cam_point=(6.4, -7.2, 9.5))
        fud = dict(fwd=(-0.01, 0.015, 1.0), up=(0.02, 1.0, 0.0), cam_point=(2.6, -6.2, 8.0))
    else:
        fpd = dict(fwd=(-0.06, 0.04, 1.0), up=(0.1, 1.0, 0.0), cam_point=(6.6, -6.6, 11.5))
        fud = dict(fwd=(-0.02, 0.02, 1.0), up=(0.03, 1.0, 0.0), cam_point=(3.2, -5.6, 10.5))
    fpd.update(fp or {})
    fud.update(use or {})
    a = tuple(anchor)
    h = {"style": RANGED_STYLES.get(w["anim_set"], "pistol"), "arm_r": HOLDS[idle]["arm_r"],
         "arm_l": HOLDS[idle]["arm_l"], "grip1": a, "grip2": None, "tp": tf, "tp_use": dict(tf),
         "fp": _fp(fpd, a, s_fp), "fp_use": _fp(fud, a, s_fp), "pose": idle, "pose_use": aim}
    if aim and aim in HOLDS:
        h["arm_r_use"], h["arm_l_use"] = HOLDS[aim]["arm_r"], HOLDS[aim]["arm_l"]
    return h


def hold_bow(wm: WC.WeaponModel, w: dict, *, scale: float, anchor=(0.0, 0.0, 0.0), cant: float = 14.0,
             fp=None, use=None) -> dict:
    """弓（右手）: 構え（hold_bow = 腕 -18°）は弓を体の横に立てて上の弭を少し前へ（gen_nr_player_anim の
    STYLES["bow"] と同じ向き）。引き絞り（bow_hold）は矢 = 右腕の向き、弓は立てて上を顔の側へ cant 度。"""
    arm = HOLDS["hold_bow"]["arm_r"]
    up_w = np.array([0.0, 0.94, -0.34])
    fwd_w = np.array([0.0, -0.34, -0.94])
    tp = WC.place_tp(arm, WC.frame(fwd_w, up_w), tuple(anchor), scale)
    arm_u = HOLDS["bow_hold"]["arm_r"]
    A = HS.rot(*arm_u)
    fwd_u = A @ ARM_DIR
    up_u = np.array([0.0, 1.0, 0.0]) - fwd_u * fwd_u[1]
    up_u /= np.linalg.norm(up_u)
    # 弦を引く左の拳の側へ弓の上を傾ける（弓の面に弦の手が乗る）
    Fl = fist_pos(HOLDS["bow_hold"]["arm_l"], left=True)
    Fr = fist_pos(arm_u)
    to_l = Fl - Fr
    to_l -= fwd_u * (to_l @ fwd_u) + up_u * (to_l @ up_u)
    sgn = 1.0 if (np.cross(fwd_u, up_u) @ to_l) >= 0 else -1.0
    up_u = _rot_about(up_u, fwd_u, -sgn * cant)
    tp_use = WC.place_tp(arm_u, WC.frame(fwd_u, up_u), tuple(anchor), scale)
    s_fp = scale * 0.9
    fpd = dict(fwd=(-0.25, 0.1, 1.0), up=(0.35, 1.0, 0.25), cam_point=(7.0, -5.5, 12.0))
    fud = dict(fwd=(-0.02, 0.0, 1.0), up=(0.16, 1.0, 0.0), cam_point=(2.4, -3.6, 13.0))
    fpd.update(fp or {})
    fud.update(use or {})
    a = tuple(anchor)
    return {"style": "bow", "arm_r": arm, "arm_l": None, "grip1": a, "grip2": None, "tp": tp, "tp_use": tp_use,
            "fp": _fp(fpd, a, s_fp), "fp_use": _fp(fud, a, s_fp), "pose": "hold_bow", "pose_use": "bow_hold",
            "arm_r_use": arm_u, "arm_l_use": HOLDS["bow_hold"]["arm_l"]}


def hold_throw(wm: WC.WeaponModel, w: dict, *, scale: float = 1.0, grip: float = 0.0, pitch: float = 40.0,
               yaw: float = -4.0, roll: float = 0.0, fp=None, use=None) -> dict:
    """投げ物: 片手（バニラの持ち姿勢のまま）。振りかぶりは throw_wind が腕を動かすので tp_use = tp。
    一人称の使う間は手前・右上へ引いて構える。"""
    fpd = dict(fwd=(-0.3, 0.75, 0.6), up=(0.5, 0.2, 0.85), cam_point=(7.0, -7.0, 11.0))
    fud = dict(fwd=(-0.15, 0.9, -0.25), up=(0.6, 0.25, 0.75), cam_point=(10.5, -5.0, 8.5))
    fpd.update(fp or {})
    fud.update(use or {})
    h = WC.hold_one_hand(wm, grip=grip, scale=scale, pitch=pitch, yaw=yaw, roll=roll, fp=fpd, use=fud)
    h["tp_use"] = dict(h["tp"])
    h["pose"], h["pose_use"] = "hold_1h", None
    return h


def hold_for(w: dict, wm: WC.WeaponModel, kw: dict) -> dict:
    kw = dict(kw)
    if w["kind"] in ("gun", "crossbow"):
        return hold_gun(wm, w, **kw)
    if w["kind"] == "bow":
        return hold_bow(wm, w, **kw)
    return hold_throw(wm, w, **kw)


def use_view(hold: dict) -> dict:
    """使う間の姿勢（腕も使う間の角度に）を、clip_report / render_held がそのまま読める形に。"""
    h = dict(hold)
    h["tp"] = hold["tp_use"]
    if hold.get("arm_r_use"):
        h["arm_r"] = hold["arm_r_use"]
        h["arm_l"] = hold.get("arm_l_use")
    return h


def left_gap(wm: WC.WeaponModel, hold: dict) -> Optional[float]:
    """左の拳の中心から武器の表面までの最短距離（体の単位。左手が空きなら None）。"""
    if not hold.get("arm_l"):
        return None
    SK, skel_world = WC._skeleton()
    pose = {"rightArm": {"rotation": hold["arm_r"]}, "leftArm": {"rotation": hold["arm_l"]}}
    W = skel_world(pose)
    pts = WC.weapon_world(hold["tp"], W, wm.points(0.4))
    fl = (W["leftArm"] @ np.array([*HS.HAND_L, 1.0]))[:3]
    return round(float(np.min(np.linalg.norm(pts - fl, axis=1))), 2)


# ===========================================================================
#  模様（cube.fx["world"] に渡す関数）
# ===========================================================================
def bore(z_end: float, c_xy, r: float, *, soot_r: float = 0.18):
    """-Z を向いた銃口の面の、中心 c_xy = (x, y) から半径 r を暗い穴に（周りは煤で黒ずむ）。"""
    cx, cy = c_xy

    def fn(P, N, L, size, col):
        ok = (N[:, 2] < -0.7) & (np.abs(P[:, 2] - z_end) < 0.1)
        d = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
        inn = ok & (d < r)
        rim = ok & (d >= r) & (d < r + soot_r)
        col = np.where(rim[:, None], col * 0.5, col)
        return np.where(inn[:, None], np.array([10, 9, 9], np.float32), col)
    return fn


def serr(z0: float, z1: float, *, period: float = 0.26, y0: float = -99.0, y1: float = 99.0, dark: float = 0.5,
         side: int = 0):
    """±X の面に z0〜z1 の縦溝（スライドのセレーション・握りの滑り止め）。"""
    za, zb = min(z0, z1), max(z0, z1)

    def fn(P, N, L, size, col):
        ok = (np.abs(N[:, 0]) > 0.7) & (P[:, 2] > za) & (P[:, 2] < zb) & (P[:, 1] > y0) & (P[:, 1] < y1)
        if side:
            ok &= np.sign(N[:, 0]) == side
        ph = ((P[:, 2] - za) / period) % 1.0
        g = ok & (ph < 0.42)
        e = ok & (ph >= 0.42) & (ph < 0.58)
        col = np.where(g[:, None], col * dark, col)
        return np.where(e[:, None], np.minimum(255, col * 1.18 + 6), col)
    return fn


def patch(lo, hi, *, normal=None, mul: float = 0.3, rgb=None, rim: float = 0.0, rim_mul: float = 1.25):
    """武器空間の箱 lo〜hi の中の面（normal の向きの面だけ、None なら全部）を暗く（mul）か色 rgb に。
    排莢口・溝・窓・シール。rim > 0 なら周りに明るい縁。"""
    lo_, hi_ = np.asarray(lo, float), np.asarray(hi, float)
    nrm = None if normal is None else np.asarray(normal, float)
    rgbv = None if rgb is None else np.asarray(rgb, np.float32)

    def fn(P, N, L, size, col):
        ok = np.ones(len(P), bool) if nrm is None else (N @ nrm) > 0.7
        inn = ok & np.all((P >= lo_) & (P <= hi_), axis=1)
        if rim > 0:
            ring = ok & np.all((P >= lo_ - rim) & (P <= hi_ + rim), axis=1) & ~inn
            col = np.where(ring[:, None], np.minimum(255, col * rim_mul + 4), col)
        if rgbv is not None:
            return np.where(inn[:, None], rgbv * (0.86 + 0.2 * col.mean(1, keepdims=True) / 255.0), col)
        return np.where(inn[:, None], col * mul, col)
    return fn


def engrave(seed: int, *, cell: float = 0.42, width: float = 0.035, lo=None, hi=None, mul: float = 0.55):
    """唐草風の彫刻（3D のセルの距離の等高線を細い溝に。すり減った所は消える）。"""
    lo_ = None if lo is None else np.asarray(lo, float)
    hi_ = None if hi is None else np.asarray(hi, float)

    def fn(P, N, L, size, col):
        d, rnd = WC.worley3(P, cell, seed)
        ok = np.ones(len(P), bool)
        if lo_ is not None:
            ok &= np.all((P >= lo_) & (P <= hi_), axis=1)
        wear = NP.fbm3(P[:, 0] * 1.3, P[:, 1] * 1.3, P[:, 2] * 1.3, seed + 5, octaves=2)
        lines = ok & ((np.abs(d - cell * 0.32) < width) | (np.abs(d - cell * 0.18) < width * 0.8)) & (wear > 0.38)
        return np.where(lines[:, None], col * mul, col)
    return fn


def stripes(z0: float, z1: float, period: float, *, mul: float = 0.62, axis: int = 2, normal=None, duty=0.35):
    """axis（0=x, 1=y, 2=z）に沿った等間隔の暗い線（フルート・リブの溝・羽根の筋）。"""
    za, zb = min(z0, z1), max(z0, z1)
    nrm = None if normal is None else np.asarray(normal, float)

    def fn(P, N, L, size, col):
        ok = (P[:, axis] > za) & (P[:, axis] < zb)
        if nrm is not None:
            ok &= (N @ nrm) > 0.7
        ph = ((P[:, axis] - za) / period) % 1.0
        return np.where((ok & (ph < duty))[:, None], col * mul, col)
    return fn


def flutes(c_xy, n: int, *, phase: float = 0.0, width: float = 0.22, mul: float = 0.55, z0=-99.0, z1=99.0):
    """軸 Z の円筒（回転弾倉）の側面に n 本の縦溝（中心 c_xy からの角度で）。"""
    cx, cy = c_xy

    def fn(P, N, L, size, col):
        ok = (np.abs(N[:, 2]) < 0.6) & (P[:, 2] > z0) & (P[:, 2] < z1)
        ang = np.degrees(np.arctan2(P[:, 1] - cy, P[:, 0] - cx)) - phase
        ph = ((ang / (360.0 / n)) % 1.0)
        g = ok & (np.abs(ph - 0.5) < width)
        e = ok & (np.abs(ph - 0.5) >= width) & (np.abs(ph - 0.5) < width + 0.07)
        col = np.where(e[:, None], np.minimum(255, col * 1.2 + 8), col)
        return np.where(g[:, None], col * mul, col)
    return fn


def holes_on(centres, r: float, *, normal, dark=(14, 13, 13), rim_mul: float = 0.6):
    """normal の向きの面に丸い穴（弾倉の口・マズルブレーキの横穴・薬室）。centres は武器空間の点。"""
    C = np.asarray(centres, np.float32).reshape(-1, 3)
    nrm = np.asarray(normal, float)
    dk = np.asarray(dark, np.float32)

    def fn(P, N, L, size, col):
        ok = (N @ nrm) > 0.7
        d = np.min(np.linalg.norm(P[:, None, :] - C[None, :, :], axis=2), axis=1)
        inn = ok & (d < r)
        rim = ok & (d >= r) & (d < r + 0.1)
        col = np.where(rim[:, None], col * rim_mul, col)
        return np.where(inn[:, None], dk, col)
    return fn


def glass_windows(*, rim: float = 0.22, keep=None, seed: int = 0, streak: float = 0.22):
    """ガラスの面の真ん中を抜いて（alphatest のガラス）、縁 rim 単位だけ残す。keep(P) が真の所は抜かない
    （ラベル・液の膜）。抜かずに残る縁には斜めの照り（反射の筋）を足す。"""
    def fn(P, N, L, size, col):
        # 面の中の 2 軸での縁からの距離（局所 L は箱の原点から。法線の軸は除く）
        nax = np.argmax(np.abs(N), axis=1)
        d = np.full(len(P), 1e9)
        for ax in range(3):
            m = nax != ax
            dd = np.minimum(L[:, ax], size[ax] - L[:, ax])
            d = np.where(m, np.minimum(d, dd), d)
        cut = d > rim
        if keep is not None:
            cut &= ~keep(P)
        # 照り: 縁に沿った明るい筋
        g = ((P[:, 1] * 0.8 + P[:, 2] * 0.5 + P[:, 0] * 0.5 + seed * 0.13) % 1.4) < streak
        col = np.where((~cut & g)[:, None], np.minimum(255, col * 1.35 + 30), col)
        return col, cut
    return fn


# ===========================================================================
#  部品（銃の共通の形）
# ===========================================================================
def grip(b, top, *, length: float, rake: float, w: float, d: float, style: str, k: float = 0.8, uv=7, fx=None,
         flare: Optional[str] = None):
    """ピストルグリップ: top（握りの上の端の中心）から下へ length、rake 度だけ後ろ（+Z）へ傾ける。
    断面は幅 w（X）× 奥行き d、角を落とす。flare なら下に弾倉の底板（別の素材）。戻り値は (cubes, 下の端の中心, 下向き)。"""
    a = math.radians(rake)
    down = np.array([0.0, -math.cos(a), math.sin(a)])
    front = np.array([0.0, -math.sin(a), -math.cos(a)])
    t = np.asarray(top, float)
    bot = t + down * length
    out = rbeam(b, t, bot, w, d, style, k=k, up=tuple(front), uv=uv, fx=fx or {})
    if flare:
        out += rbeam(b, bot - down * 0.1, bot + down * 0.32, w + 0.12, d + 0.16, flare, k=0.85, up=tuple(front),
                     uv=uv + 2)
    return out, bot, down


def trigger_group(b, *, z_front: float, z_back: float, y_top: float, y_bot: float, guard: str, trig: str,
                  w: float = 0.36, t: float = 0.3, round_: bool = False, uv=11):
    """用心金（前の柱・下の帯・後ろへの返り）と引き金（少し曲げた板 2 枚）。"""
    out = []
    zf, zb = z_front, z_back
    if round_:
        pts = [(0, y_top, zf + 0.15), (0, y_bot + 0.45, zf - 0.05), (0, y_bot, zf + 0.6),
               (0, y_bot - 0.05, (zf + zb) / 2), (0, y_bot + 0.2, zb - 0.1), (0, y_top - 0.3, zb + 0.1)]
        out += polyline(b, pts, w, t, guard, up=(1, 0, 0), overlap=0.12, uv=uv)
    else:
        out.append(beam(b, (0, y_top, zf), (0, y_bot - t / 2, zf - 0.08), w, t, guard, up=(0, 0, -1), uv=uv))
        out.append(beam(b, (0, y_bot, zf - 0.16), (0, y_bot, zb + 0.1), w, t, guard, uv=uv))
        out.append(beam(b, (0, y_bot - 0.02, zb + 0.05), (0, y_top - 0.25, zb + 0.32), w, t, guard, up=(0, 0, -1),
                        uv=uv))
    tz = zf + (zb - zf) * 0.45
    out.append(beam(b, (0, y_top + 0.05, tz - 0.1), (0, (y_top + y_bot) / 2 + 0.05, tz), 0.22, 0.22, trig, uv=uv + 2))
    out.append(beam(b, (0, (y_top + y_bot) / 2 + 0.1, tz), (0, y_bot + 0.32, tz - 0.2), 0.22, 0.2, trig, uv=uv + 2))
    return out


def sight_post(b, at, size, style: str, *, dot: Optional[str] = None, dot_r: float = 0.08, uv=12):
    """照星・照門の柱。dot なら後ろ（+Z、撃つ人の側）の面に発光の点（トリチウム）。"""
    out = [cbox(b, at, size, style, uv=uv)]
    if dot:
        p = np.asarray(at, float) + np.array([0.0, size[1] * 0.18, size[2] / 2 + 0.03])
        out.append(cbox(b, p, (dot_r * 2, dot_r * 2, 0.06), dot, uv=16, tags=("noao",)))
    return out


def shell(b, c, axis, *, d: float = 0.7, length: float = 1.8, hull: str = "shell", head: str = "brass", uv=12):
    """散弾の実包（樹脂の筒 + 真鍮の底）。c は中心、axis は底 → 口の向き。"""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    c = np.asarray(c, float)
    p0 = c - a * length / 2
    out = rod(b, p0 + a * length * 0.3, p0 + a * length, d, hull, uv=uv)
    out += rod(b, p0, p0 + a * length * 0.32, d * 1.06, head, uv=uv + 2)
    return out


def cartridge(b, c, axis, *, d: float = 0.42, length: float = 2.2, case: str = "brass", tip: str = "copper", uv=14):
    """ライフル・拳銃の実包（真鍮の薬莢 + 銅の弾頭）。"""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    c = np.asarray(c, float)
    p0 = c - a * length / 2
    out = [beam(b, p0, p0 + a * length * 0.68, d, d, case, uv=uv)]
    out.append(beam(b, p0 + a * length * 0.64, p0 + a * length, d * 0.72, d * 0.72, tip, uv=uv))
    return out


def strap(b, pts, *, w: float = 0.55, t: float = 0.12, style: str = "sling", up=(1.0, 0.0, 0.0), uv=9, soft=True):
    """吊り紐・スリング（平たい帯を点列に沿って。垂れる物はめり込み検査から外す）。"""
    return polyline(b, pts, t, w, style, up=up, overlap=0.1, uv=uv, tags=("soft",) if soft else ())


def taped_light(b, front, back, *, d: float = 0.9, body: str = "light", lens: str = "lens", tape: str = "tape",
                tape_d=None, uv=9):
    """テープで留めた懐中電灯（胴・頭の膨らみ・レンズ・巻いたテープ 2 本）。front が頭の先。"""
    f, k = np.asarray(front, float), np.asarray(back, float)
    a = (f - k) / np.linalg.norm(f - k)
    L = float(np.linalg.norm(f - k))
    out = rod(b, k, f - a * L * 0.25, d, body, uv=uv)
    out += rod(b, f - a * L * 0.27, f, d * 1.25, body, uv=uv)
    out += disc(b, f + a * 0.02, a, d * 0.5, 0.05, lens, n=2, uv=14, tags=("noao",))
    td = tape_d or (d + 0.16)
    for t_ in (0.3, 0.62):
        out += band(b, k + a * L * t_, a, td, 0.42, tape, uv=uv + 1)
    return out


def scope(b, z0: float, z1: float, y: float, *, d: float = 1.1, bell: float = 1.6, body: str = "scope",
          lens: str = "lens", ring: str = "ring", uv=8):
    """スコープ（胴・前後のベル・調整ノブ・レンズ）。z0 が前（対物）、z1 が後ろ（接眼）。"""
    out = rod(b, (0, y, z0 + 1.6), (0, y, z1 - 1.0), d, body, uv=uv)
    out += rod(b, (0, y, z0), (0, y, z0 + 1.7), bell, body, uv=uv)
    out += rod(b, (0, y, z1 - 1.1), (0, y, z1), bell * 0.86, body, uv=uv)
    out += disc(b, (0, y, z0 - 0.02), (0, 0, 1), bell * 0.42, 0.05, lens, n=2, uv=14, tags=("noao",))
    out += disc(b, (0, y, z1 + 0.02), (0, 0, 1), bell * 0.36, 0.05, lens, n=2, uv=14, tags=("noao",))
    zm = (z0 + z1) / 2 - 0.4
    out += rod(b, (0, y + d * 0.4, zm), (0, y + d * 0.4 + 0.55, zm), 0.62, ring, uv=uv + 3)     # 上の調整ノブ
    out += rod(b, (d * 0.4, y, zm), (d * 0.4 + 0.5, y, zm), 0.6, ring, uv=uv + 3)              # 横のノブ
    return out


def lanyard(b, start, *, drop: float = 2.2, swing: float = 0.5, style: str = "cord", uv=12):
    """握りの尻から垂れたパラコードの輪。"""
    s = np.asarray(start, float)
    pts = [s, s + (0.12, -drop * 0.45, swing * 0.4), s + (0.18, -drop, swing), s + (-0.05, -drop * 0.55, swing * 1.2),
           s + (-0.08, -0.15, 0.25)]
    return polyline(b, pts, 0.2, 0.2, style, overlap=0.1, uv=uv, tags=("soft",))


def add_world(cubes, *fns):
    """cubes に world 模様を足す（既にあれば重ねる）。"""
    for c in cubes:
        c.fx = dict(getattr(c, "fx", {}) or {})
        prev = c.fx.get("world")
        c.fx["world"] = WC.compose(prev, *fns) if prev else (WC.compose(*fns) if len(fns) > 1 else fns[0])


# ===========================================================================
#  拳銃
# ===========================================================================
@builder("pistol")
def b_pistol(w) -> Built:
    """警官の拳銃: 樹脂のフレームに黒染めのスライド。前後のセレーション、排莢口の真鍮、発光の照準点、
    テープで留めた懐中電灯、握りに巻いた汗止めのテープとパラコードの輪。"""
    wm = WC.WeaponModel("pistol", uv=9)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    yb = 3.42                                               # 銃身の芯の高さ（握りの中心 = 原点から）
    # ---- スライド（角を落とした箱）と銃身 ----
    sl = rbeam(b, (0, 3.28, 1.35), (0, 3.28, -6.2), 1.26, 1.52, "slide", k=0.8, uv=10)
    sl += [cbox(b, (0, 3.92, -2.4), (0.86, 0.22, 7.2), "slide", uv=10)]                 # 上の平らな面
    cbox(b, (0, 2.62, -6.0), (1.1, 0.3, 0.5), "slide", uv=12)                            # 前の下の面取り
    add_world(sl, serr(0.1, 1.3, period=0.24, y0=2.6, y1=4.0), serr(-6.0, -4.9, period=0.24, y0=2.7, y1=4.0),
              patch((0.5, 3.05, -2.15), (0.7, 4.1, -0.35), normal=(1, 0, 0), mul=0.22, rim=0.06),
              WC.stamp("NR-PD 17", (-3.1, 3.05), 0.36, mul=0.5, side=-1),
              WC.pock(311, cell=0.7, r=0.16, frac=0.35))
    rod(b, (0, yb, -6.0), (0, yb, -6.55), 0.66, "barrel", uv=14)
    add_world(rod(b, (0, yb, -6.5), (0, yb, -6.62), 0.7, "barrel", uv=14), bore(-6.62, (0, yb), 0.2))
    cbox(b, (0.32, 3.72, -1.15), (0.5, 0.36, 1.0), "brass", uv=14)                     # 排莢口から見える薬莢
    cbox(b, (0.67, 3.5, -0.2), (0.1, 0.24, 0.9), "slide_dark", uv=14)                   # エキストラクター
    # 照準: 前は 1 点、後ろは 2 点（発光）
    sight_post(b, (0, 4.17, -5.7), (0.3, 0.34, 0.42), "sight", dot="glow_white")
    for s in (-1, 1):
        sight_post(b, (s * 0.31, 4.19, 0.95), (0.36, 0.38, 0.42), "sight", dot="glow_white")
    cbox(b, (0, 4.08, 0.95), (0.3, 0.16, 0.42), "sight", uv=14)
    # ---- フレーム（樹脂）とレール ----
    fr = rbeam(b, (0, 2.05, 0.55), (0, 2.05, -5.85), 1.16, 0.96, "frame", k=0.84, uv=9)
    rail = cbox(b, (0, 1.42, -4.6), (0.98, 0.36, 2.5), "frame", uv=12, fx={"ribs": 0.42})
    cbox(b, (-0.62, 2.55, -1.6), (0.1, 0.32, 1.3), "slide_dark", uv=14)                 # スライドストップ（左）
    cbox(b, (-0.62, 2.2, -2.6), (0.08, 0.22, 0.32), "slide_dark", uv=14)                # 分解レバー
    cbox(b, (-0.62, 1.55, -0.55), (0.12, 0.42, 0.42), "slide_dark", uv=14)              # 弾倉の留め金
    add_world(fr + [rail], WC.stamp("17", (-4.0, 2.05), 0.34, mul=0.62, side=1), grime((-1.5, 0.6), dark=0.75, seed=312))
    # ---- 用心金と引き金 ----
    trigger_group(b, z_front=-3.25, z_back=-0.85, y_top=1.55, y_bot=0.48, guard="frame", trig="slide_dark")
    # ---- 握り（14° の傾き、梨地）と弾倉の底、背の膨らみ ----
    gc, gbot, gdown = grip(b, (0, 1.85, -0.52), length=4.05, rake=14.0, w=1.28, d=2.12, style="frame",
                           fx={"knurl": 0.3}, uv=9)
    rbeam(b, gbot - gdown * 0.1, gbot + gdown * 0.4, 1.38, 2.3, "mag", k=0.84, up=(0, -0.24, -0.97), uv=11)
    cbox(b, (0, 1.82, 0.88), (1.16, 0.62, 0.7), "frame", rot=(14, 0, 0), uv=12)          # 背の膨らみ（ビーバーテール）
    for k_, z_ in enumerate((-0.98, -0.62, -0.26)):                                        # 指の溝の山
        p = np.array([0.0, 0.9 - k_ * 0.95, -1.05 + k_ * 0.24])
        cbox(b, p, (1.2, 0.26, 0.22), "frame", rot=(14, 0, 0), uv=14)
    # 汗止めのテープと、尻から垂れたパラコードの輪
    wrap(b, (0, 0.62, -0.18), (0, -1.15, 0.27), (1.42, 2.26), "tape", pitch=0.42, tilt=10, seed=313, uv=10,
         tail=(0.55, (0.6, -0.8, 0.4)))
    lanyard(b, gbot + gdown * 0.38 + np.array([0, 0, 0.55]), drop=2.0, swing=0.7)
    # ---- テープで留めた懐中電灯（レールの下）----
    taped_light(b, (0, 0.72, -6.55), (0, 0.72, -3.6), d=0.86, tape_d=0.98)
    for z_ in (-4.0, -5.4):
        lash(b, (0, 1.12, z_), (0, 0, 1), 1.12, 1.55, 0.32, 1, "tape", wire=0.12)
    book.add("slide", "steel_dark", base=book.pal(0), wear=0.95, scratches=0.55)
    book.add("slide_dark", "steel_dark", base=(40, 41, 44))
    book.add("barrel", "steel_worn", base=(96, 96, 98), scratches=0.5)
    book.add("brass", "brass", base=book.pal(3), wear=0.5)
    book.add("sight", "steel_dark", base=(30, 30, 32))
    book.raw("glow_white", NP.style("glow", base=(214, 255, 196)))
    book.add("frame", "plastic_black", base=book.pal(2), wear=0.55, dirt=0.4)
    book.add("mag", "steel_dark", base=book.pal(1))
    book.add("tape", "tape_grey", base=(150, 150, 146), dirt=0.6)
    book.add("cord", "paracord", base=(58, 74, 52))
    book.add("light", "aluminium", base=(70, 72, 76), dirt=0.4)
    book.add("lens", "glass_tinted", base=(200, 210, 190))
    blood = [WC.blood_zone((-0.8, 2.4, -6.7), (0.8, 4.4, -3.6), 0.3, "dry", soft=0.8),
             WC.blood_zone((-0.8, -2.4, -1.4), (0.8, 0.4, 1.4), 0.16, "dry", soft=0.8)]
    return Built(wm, book, blood, hold=dict(scale=0.78, anchor=(0.0, 0.2, 0.15)), icon_yaw=80.0)


# ===========================================================================
#  投げ物
# ===========================================================================
def flame(b, at, size: float, *, seed: int, styles=("flame_out", "flame_mid", "flame_core")):
    """揺れる炎（芯の黄・橙・外の赤橙を少しずつ回した箱で。全部 glow）。"""
    import random as _random
    rng = _random.Random(WC.stable_hash(("flame", seed)))
    at = np.asarray(at, float)
    out = []
    for i, (k, st) in enumerate(((1.0, styles[0]), (0.7, styles[1]), (0.42, styles[2]))):
        s = size * k
        out.append(cbox(b, at + (0, 0, -s * 0.35), (s * 0.8, s * 0.8, s * 1.3), st,
                        rot=(rng.uniform(-10, 10), rng.uniform(-10, 10), 45.0 * (i % 2) + rng.uniform(-8, 8)),
                        uv=10, tags=("noao", "soft")))
    for j in range(3):
        a = rng.uniform(0, 2 * math.pi)
        tip = at + (math.cos(a) * size * 0.22, math.sin(a) * size * 0.22, -size * (1.05 + 0.22 * j))
        out.append(cbox(b, tip, (size * 0.28, size * 0.28, size * 0.5), styles[0], rot=(0, 0, 45), uv=10,
                        tags=("noao", "soft")))
    return out


def flame_styles(book: WC.Stylebook) -> None:
    book.raw("flame_out", NP.style("glow", base=(255, 112, 26)))
    book.raw("flame_mid", NP.style("glow", base=(255, 168, 52)))
    book.raw("flame_core", NP.style("glow", base=(255, 236, 150)))
    book.raw("spark_core", NP.style("glow", base=(255, 246, 214)))
    book.raw("spark", NP.style("glow", base=(255, 186, 64)))


def spark(b, at, size: float, *, core="spark_core", ray="spark"):
    """導火線の火花（白熱の芯と放射する筋）。"""
    at = np.asarray(at, float)
    out = [cbox(b, at, (size, size, size), core, rot=(45, 45, 0), uv=14, tags=("noao", "soft"))]
    for d in ((1, 0.3, 0), (-1, 0.4, 0), (0.2, 1, 0.1), (0, 0.3, 1), (0, 0.5, -1), (0.7, 0.8, -0.3), (-0.6, 0.9, 0.4)):
        d = np.asarray(d, float)
        d = d / np.linalg.norm(d)
        out.append(beam(b, at + d * size * 0.3, at + d * size * 1.3, size * 0.15, size * 0.15, ray, uv=14,
                        tags=("noao", "soft")))
    return out


@builder("molotov")
def b_molotov(w) -> Built:
    """火炎瓶: 角瓶（alphatest のガラス: 面の真ん中を抜いて縁と照りだけ残す）の中に琥珀色のアルコール、
    破れたラベル、口に詰めて垂れた布、留めたテープ、布の先の炎（待機アニメで揺れる）。瓶の首が -Z（上）。"""
    wm = WC.WeaponModel("molotov", uv=10)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # 握り = 胴の真ん中。胴 z +2.2 〜 -1.9、肩 -1.9 〜 -2.7、首 -2.7 〜 -4.7、口 -4.7 〜 -5.0
    body_w, z_bot, z_sh = 2.3, 2.25, -1.85
    label_keep = (lambda P: (P[:, 2] > -0.85) & (P[:, 2] < 1.05) & (np.abs(P[:, 0]) > body_w / 2 - 0.05))
    shell_ = [cbox(b, (0, 0, (z_bot + z_sh) / 2), (body_w, body_w, z_bot - z_sh), "glass", uv=10)]
    add_world(shell_, glass_windows(rim=0.24, keep=label_keep, seed=1))
    cbox(b, (0, 0, z_bot - 0.18), (body_w + 0.02, body_w + 0.02, 0.36), "glass_dark", uv=10)    # 厚い底
    # 中の酒（琥珀）。液面は胴の 6 割、上は泡の明るい膜
    cbox(b, (0, 0, 0.62), (body_w - 0.3, body_w - 0.3, 3.0), "fuel", uv=9)
    cbox(b, (0, 0, -0.9), (body_w - 0.32, body_w - 0.32, 0.08), "fuel_top", uv=10, tags=("noao",))
    # 肩（2 段で細る）と首・口の輪
    sh = [cbox(b, (0, 0, -2.08), (body_w - 0.2, body_w - 0.2, 0.5), "glass", uv=11),
          cbox(b, (0, 0, -2.5), (1.5, 1.5, 0.42), "glass", uv=12)]
    add_world(sh, glass_windows(rim=0.2, seed=2))
    nk = rod(b, (0, 0, -2.6), (0, 0, -4.6), 0.92, "glass_dark", uv=12)
    band(b, (0, 0, -4.55), (0, 0, 1), 1.08, 0.24, "glass_dark", uv=14)
    # ラベル（胴の ±X の 2 面に紙。片方は破れて半分）と酒の名前
    lab = [cbox(b, (s * (body_w / 2 + 0.03), 0, 0.1), (0.06, body_w - 0.1, 1.9), "label", uv=11, tags=("ragged",))
           for s in (-1, 1)]
    add_world(lab, WC.stamp("RYE", (0.35, 0.3), 0.55, tint=(92, 30, 24)),
              WC.stamp("1987", (-0.45, -0.45), 0.32, tint=(70, 52, 30)))
    # 首に詰めた布と、外へ垂れた端（先が焦げる）。布を留めたテープ
    rod(b, (0, 0, -3.7), (0, 0.05, -5.35), 0.7, "rag", uv=11)
    rag(b, (0.1, 0.25, -5.2), 1.9, 0.62, "rag", hang=(0.3, -0.8, 0.55), strips=2, spread=0.26, seed=5, uv=11)
    rag(b, (-0.2, -0.1, -5.1), 1.2, 0.5, "rag", hang=(-0.5, -0.4, 0.75), strips=1, seed=6, uv=11)
    wrap(b, (0, 0, -3.0), (0, 0, -3.75), 1.18, "tape", pitch=0.36, tilt=8, seed=7, uv=12)
    cbox(b, (0.05, 0.1, -5.55), (0.78, 0.72, 0.46), "rag_burnt", rot=(10, 20, 0), uv=12)
    # 炎（布の先）。待機アニメで揺らす
    fb = wm.bone("flame", pivot=(0.05, 0.1, -5.6))
    flame(fb, (0.05, 0.1, -6.05), 1.25, seed=11)
    wm.idle = {"flame": {"scale": ["1.0 + 0.12 * math.sin(q.anim_time * 1440.0)",
                                   "1.0 + 0.1 * math.sin(q.anim_time * 1080.0 + 40.0)",
                                   "1.0 + 0.16 * math.sin(q.anim_time * 1260.0 + 90.0)"],
                         "rotation": [0.0, 0.0, "6.0 * math.sin(q.anim_time * 900.0)"]}}
    book.add("glass", "glass_tinted", base=(112, 66, 22))
    book.add("glass_dark", "glass_tinted", base=(70, 40, 16))
    book.raw("fuel", NP.style("plastic", base=(196, 120, 34), wear=0.0, dirt=0.05))
    book.raw("fuel_top", NP.style("plastic", base=(236, 196, 120), wear=0.0, dirt=0.0))
    book.raw("label", NP.style("paper", base=(210, 194, 152), lines=False, dirt=0.55))
    book.add("rag", "cloth_rag", base=book.pal(1))
    book.raw("rag_burnt", NP.style("char", embers=0.6))
    book.add("tape", "tape_grey", base=book.pal(3), dirt=0.55)
    flame_styles(book)
    blood = [WC.blood_zone((-1.3, -1.3, 0.8), (1.3, 1.3, 2.4), 0.2, "dry", soft=0.6)]
    return Built(wm, book, blood, hold=dict(scale=0.82, pitch=72.0, yaw=-6.0, grip=0.2), icon_yaw=64.0)


# ===========================================================================
#  アイテム（BP）
# ===========================================================================
_RARITY_ITEM = {"common": "common", "uncommon": "uncommon", "rare": "rare", "epic": "epic", "legendary": "epic"}
_ENCHANT_VALUE = {"common": 10, "uncommon": 12, "rare": 14, "epic": 16, "legendary": 18}
# 使う間（秒）と、その間の歩きの速さ。使う時間はスクリプトが離した時に読むので長め（離すまで続く）
_USE = {"gun": (30.0, 0.72), "bow": (30.0, 0.55), "crossbow": (30.0, 0.62), "throwable": (30.0, 0.82)}


def item_doc_ranged(w: dict) -> dict:
    """飛び道具の BP アイテム（1.21.120）。shooter / throwable / projectile は書かない（スクリプトが飛ばす）。"""
    key, kind = w["key"], w["kind"]
    stackable = kind == "throwable"
    tags = ["nr:weapon", "nr:ranged", f"nr:{kind}", f"nr:{w['anim_set']}", f"nr:{w['dtype']}", f"nr:{w['weight']}",
            f"nr:cls_{w['cls']}"]
    desc = {"identifier": w["id"], "menu_category": {"category": "equipment"}}
    use_s, move = _USE[kind]
    if w["anim_set"] == "pistol":
        move = 0.8
    comps = {
        "minecraft:icon": f"nr_w_{key}",
        "minecraft:display_name": {"value": f"item.{w['id']}"},
        "minecraft:max_stack_size": int(max(1, w.get("stack", 1))) if stackable else 1,
    }
    if not stackable:
        hands2 = int(w.get("hands", 1)) == 2
        comps.update({
            "minecraft:hand_equipped": True,
            "minecraft:durability": {"max_durability": int(w["durability"]), "damage_chance": {"min": 100, "max": 100}},
            # 銃床・弓で殴った時のバニラの値（ゾンビへの本当の値はスクリプトの bashHit）
            "minecraft:damage": 3 if hands2 else 2,
            "minecraft:repairable": {"repair_items": [
                {"items": ["nr:scrap"], "repair_amount": "query.max_durability * 0.25"},
                {"items": [w["id"]], "repair_amount": "context.other->query.remaining_durability + 0.12 * context.other->query.max_durability"},
            ]},
        })
        if kind in ("bow", "crossbow"):
            comps["minecraft:enchantable"] = {"slot": kind, "value": _ENCHANT_VALUE.get(w["rarity"], 10)}
    comps.update({
        "minecraft:can_destroy_in_creative": False,
        "minecraft:rarity": _RARITY_ITEM.get(w["rarity"], "common"),
        "minecraft:tags": {"tags": tags},
        "nr:weapon": {"key": key},
        # 使う間: 銃は押している間（連射・狙い）、弓は引き絞り、クロスボウは構え、投げ物は振りかぶり
        "minecraft:use_modifiers": {"use_duration": use_s, "movement_modifier": move},
    })
    return {"format_version": WC.ITEM_FORMAT, "minecraft:item": {"description": desc, "components": comps}}


# ===========================================================================
#  まとめ
# ===========================================================================
def build(key: str):
    w = BY_KEY[key]
    t0 = time.time()
    bt = BUILDERS[key](w)
    wm = bt.wm
    wm.pack()
    tex = WC.texture(wm, bt.book, WC.seed_of(key), blood=bt.blood)
    hold = hold_for(w, wm, bt.hold)
    return w, bt, wm, tex, hold, time.time() - t0


def all_frags(frags: WC.Frags) -> None:
    """item_texture / lang の断片は spec から全飛び道具分を書く（--only で一部だけ作っても欠けない）。"""
    for w in RANGED:
        frags.icon(f"nr_w_{w['key']}", f"{WC.ICON_REL}/{w['key']}")
        frags.name(w["id"], w["ja"], w["en"])


def clip_line(wm, hold) -> str:
    rep = WC.clip_report(wm, hold)
    repu = WC.clip_report(wm, use_view(hold))
    lg = left_gap(wm, hold)
    lgu = left_gap(wm, use_view(hold))
    s = f"clip {rep['depth']:.2f}@{rep['part']} / use {repu['depth']:.2f}@{repu['part']}"
    if lg is not None or lgu is not None:
        s += f"  左手 {lg} / {lgu}"
    return s


def preview(results, out_dir=SCRATCH) -> List[str]:
    """確認画像（3/4 の一覧・三人称の構えと使う間・一人称・アイコン）。"""
    os.makedirs(out_dir, exist_ok=True)
    sheet, held, fp, icons = [], [], [], []
    for w, bt, wm, tex, hold, _dt in results:
        key = w["key"]
        tw, th = wm.model.tex_w, wm.model.tex_h
        sheet.append((f"{key} {wm.cube_count}c {tw}x{th}", WC.render_model(wm, tex, view=(35.0, 16.0),
                                                                          size=(420, 220))))
        rep = WC.clip_report(wm, hold)
        uv_ = use_view(hold)
        repu = WC.clip_report(wm, uv_)
        held.append((f"{key[:13]} {hold.get('pose')} {rep['depth']}",
                     WC.render_held(wm, tex, hold, view=(35.0, 8.0), size=(230, 270))))
        held.append((f"  {hold.get('pose_use') or 'use'} {repu['depth']}",
                     WC.render_held(wm, tex, uv_, view=(60.0, 8.0), size=(230, 270))))
        fp.append((key, WC.render_fp(wm, tex, hold, size=(320, 180))))
        fp.append(("  use", WC.render_fp(wm, tex, hold, use=True, size=(320, 180))))
        ic = Image.open(os.path.join(WC.RP, *WC.ICON_REL.split("/"), f"{key}.png")).convert("RGBA")
        slot = Image.new("RGBA", (ic.size[0] * 2 + 8, ic.size[1] * 2 + 8), (139, 139, 139, 255))
        slot.alpha_composite(ic.resize((ic.size[0] * 2, ic.size[1] * 2), Image.NEAREST), (4, 4))
        icons.append((key, slot))
    paths = []
    for name, items, cols in (("weapons_ranged", sheet, 4), ("weapons_ranged_held", held, 8),
                              ("weapons_ranged_fp", fp, 6), ("weapons_ranged_icons", icons, 7)):
        img = WC.contact_sheet(items, cols=min(cols, len(items)), title=f"NIGHT RUNNER {name}")
        p = os.path.join(out_dir, name + ".png")
        img.save(p)
        paths.append(p)
    return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="", help="作る武器のキー（カンマ区切り）")
    ap.add_argument("--preview", action="store_true", help="確認画像も描く（NR_PREVIEW=1 と同じ）")
    ap.add_argument("--out", default=SCRATCH, help="確認画像の置き場所")
    a = ap.parse_args(argv)
    for msg in HOLD_WARNINGS:
        print(f"[{PRODUCER}] 警告: {msg}")
    keys = [k for k in a.only.split(",") if k] or [w["key"] for w in RANGED]
    missing = [k for k in keys if k not in BUILDERS]
    if missing:
        unknown = [k for k in missing if k not in BY_KEY]
        if unknown:
            print(f"[{PRODUCER}] 飛び道具ではない / 知らないキー: {unknown}")
            return 2
        print(f"[{PRODUCER}] まだ作っていない武器: {missing}")
        keys = [k for k in keys if k in BUILDERS]
    frags = WC.Frags(PRODUCER)
    all_frags(frags)
    results = []
    t0 = time.time()
    for k in keys:
        w, bt, wm, tex, hold, dt = build(k)
        icon = WC.bake_icon(wm, tex, flip=bt.icon_flip, yaw=bt.icon_yaw, roll=bt.icon_roll)
        out = WC.write_weapon(w, wm, tex, hold, frags, icon=icon, item=item_doc_ranged(w))
        print(f"[{PRODUCER}] {k:16s} {wm.stats():34s} {clip_line(wm, hold)}  ({dt:.2f}s)"
              f"{'' if 'recipe' in out else '  (レシピなし)'}")
        results.append((w, bt, wm, tex, hold, dt))
    frags.write()
    print(f"[{PRODUCER}] {len(results)} 武器 / {time.time() - t0:.1f}s")
    if a.preview or PREVIEW:
        for p in preview(results, a.out):
            print(f"[{PRODUCER}] preview {p}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
