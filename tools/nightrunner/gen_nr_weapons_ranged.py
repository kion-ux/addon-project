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


def shell(b, c, axis, *, d: float = 0.7, length: float = 1.8, hull: str = "shell", head: str = "brass", uv=12,
          simple: bool = False):
    """散弾の実包（樹脂の筒 + 真鍮の底）。c は中心、axis は底 → 口の向き。simple なら筒も底も 1 個の角柱
    （並べて差す予備の弾など、数が多い所でキューブを節約）。"""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    c = np.asarray(c, float)
    p0 = c - a * length / 2
    if simple:
        return [beam(b, p0 + a * length * 0.3, p0 + a * length, d, d, hull, uv=uv),
                beam(b, p0, p0 + a * length * 0.32, d * 1.08, d * 1.08, head, uv=uv + 2)]
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
#  拳銃（片手。原点 = 握りの中心、-Z = 銃口、+Y = 照準器、+X = 銃の右）
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
    # ---- 握り（14° の傾き、梨地）と弾倉の底、背の膨らみ、指の溝 ----
    _gc, gbot, gdown = grip(b, (0, 1.85, -0.52), length=4.05, rake=14.0, w=1.28, d=2.12, style="frame",
                            fx={"knurl": 0.3}, uv=9)
    rbeam(b, gbot - gdown * 0.1, gbot + gdown * 0.4, 1.38, 2.3, "mag", k=0.84, up=(0, -0.24, -0.97), uv=11)
    cbox(b, (0, 1.82, 0.88), (1.16, 0.62, 0.7), "frame", rot=(14, 0, 0), uv=12)          # 背の膨らみ
    for k_ in range(3):                                                                  # 指の溝の山
        cbox(b, (0.0, 0.9 - k_ * 0.95, -1.05 + k_ * 0.24), (1.2, 0.26, 0.22), "frame", rot=(14, 0, 0), uv=14)
    # 汗止めのテープと、尻から垂れたパラコードの輪
    wrap(b, (0, 0.62, -0.18), (0, -1.15, 0.27), (1.42, 2.26), "tape", pitch=0.42, tilt=10, seed=313, uv=10,
         tail=(0.55, (0.6, -0.8, 0.4)))
    lanyard(b, gbot + gdown * 0.38 + np.array([0, 0, 0.55]), drop=2.0, swing=0.7)
    # ---- テープで留めた懐中電灯（レールの下）----
    taped_light(b, (0, 0.72, -6.55), (0, 0.72, -3.6), d=0.86, tape_d=0.98)
    for z_ in (-4.0, -5.4):
        lash(b, (0, 1.12, z_), (0, 0, 1), 1.12, 1.55, 0.32, 1, "tape", wire=0.12)
    book.add("slide", "steel_dark", base=(58, 60, 64), wear=0.95, scratches=0.6)
    book.add("slide_dark", "steel_dark", base=(44, 45, 48))
    book.add("barrel", "steel_worn", base=(104, 104, 106), scratches=0.5)
    book.add("brass", "brass", base=book.pal(3), wear=0.5)
    book.add("sight", "steel_dark", base=(34, 34, 36))
    book.raw("glow_white", NP.style("glow", base=(214, 255, 196)))
    book.add("frame", "plastic_black", base=(52, 52, 54), wear=0.55, dirt=0.4)
    book.add("mag", "steel_dark", base=book.pal(1))
    book.add("tape", "tape_grey", base=(150, 150, 146), dirt=0.6)
    book.add("cord", "paracord", base=(64, 82, 56))
    book.add("light", "aluminium", base=(74, 76, 80), dirt=0.4)
    book.add("lens", "glass_tinted", base=(200, 210, 190))
    blood = [WC.blood_zone((-0.8, 2.4, -6.7), (0.8, 4.4, -3.6), 0.3, "dry", soft=0.8),
             WC.blood_zone((-0.8, -2.4, -1.4), (0.8, 0.4, 1.4), 0.16, "dry", soft=0.8)]
    return Built(wm, book, blood, hold=dict(scale=0.92, anchor=(0.0, 0.25, 0.15)), icon_yaw=80.0)


@builder("revolver")
def b_revolver(w) -> Built:
    """.44 リボルバー: 曇ったクロームの長い銃身（通気のリブ・照星の赤い差し込み・排莢桿の覆い）、溝 6 本の
    回転弾倉（前に 6 つの薬室）、トップストラップ、ギザ付きの撃鉄、丸い用心金、市松の木の握りと真鍮のメダル、
    割れを巻いたテープ、尻のランヤードリング。"""
    wm = WC.WeaponModel("revolver", uv=9)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    yb, yc = 3.25, 2.62                                     # 銃身の芯・弾倉の軸
    # ---- 銃身・リブ・照星・排莢桿 ----
    br = rbeam(b, (0, yb, -3.9), (0, yb, -10.4), 1.0, 1.2, "chrome", k=0.78, uv=10)
    rib = cbox(b, (0, yb + 0.72, -7.15), (0.44, 0.3, 6.3), "chrome", uv=12)
    add_world([rib], stripes(-10.2, -4.2, 0.55, mul=0.3, normal=(1, 0, 0)),
              stripes(-10.2, -4.2, 0.55, mul=0.3, normal=(-1, 0, 0)))
    add_world(br, bore(-10.4, (0, yb), 0.26), WC.stamp(".44 MAG", (-7.4, yb - 0.05), 0.4, mul=0.42, side=-1),
              soot(-10.4, -8.4, dark=0.45, seed=401), WC.pock(402, cell=0.7, r=0.14, frac=0.3))
    sight_post(b, (0, yb + 1.08, -9.95), (0.26, 0.55, 0.8), "steel_dark")
    cbox(b, (0, yb + 1.2, -10.05), (0.28, 0.2, 0.26), "sight_red", uv=16)
    rbeam(b, (0, 2.34, -4.1), (0, 2.34, -9.2), 0.66, 0.66, "chrome", k=0.8, uv=11)
    rod(b, (0, 2.34, -9.15), (0, 2.34, -9.45), 0.36, "steel_dark", uv=14)
    # ---- 回転弾倉（正八角柱 + 溝 6 本 + 前の薬室）----
    cyl = octo(b, (0, yc, -2.75), (0, 0, 1), 1.27, 2.55, "cyl", uv=10)
    ch = [(0.63 * math.cos(math.radians(90 + 60 * k)), yc + 0.63 * math.sin(math.radians(90 + 60 * k)), -4.03)
          for k in range(6)]
    add_world(cyl, flutes((0, yc), 6, phase=0.0, width=0.17), holes_on(ch, 0.2, normal=(0, 0, -1)))
    rod(b, (0, yc, -4.0), (0, yc, -4.3), 0.5, "steel_dark", uv=14)                      # 軸のブッシュ
    # ---- フレーム: 上の帯・後ろの壁・下・前の受け ----
    fr = [cbox(b, (0, 4.1, -1.95), (1.02, 0.44, 4.5), "chrome", uv=10),
          cbox(b, (0, 2.7, -0.55), (1.22, 3.0, 1.9), "chrome", uv=10),
          cbox(b, (0, 1.15, -2.7), (1.12, 0.5, 2.8), "chrome", uv=11),
          cbox(b, (0, 2.55, -4.25), (1.12, 2.3, 0.5), "chrome", uv=11)]
    add_world(fr, grime((-1.6, 0.4), dark=0.8, seed=403), WC.pock(404, cell=0.6, r=0.12, frac=0.3))
    for s in (-1, 1):                                                                     # 照門の溝
        cbox(b, (s * 0.3, 4.42, 0.12), (0.26, 0.2, 0.36), "steel_dark", uv=16)
    for p in ((-0.62, 2.0, -0.4), (-0.62, 3.4, -0.9), (-0.62, 1.5, -2.2)):               # 側板のねじ
        rivet(b, p, (-1, 0, 0), d=0.32, h=0.06, style="steel_dark", uv=16)
    cbox(b, (-0.66, 2.55, -1.05), (0.14, 0.42, 0.66), "steel_dark", uv=14)              # 弾倉の留め金
    # ---- 撃鉄（ギザ付きの頭）----
    beam(b, (0, 3.3, 0.35), (0, 4.42, 0.88), 0.44, 0.5, "steel_dark", up=(0, 0.42, -1), uv=12)
    beam(b, (0, 4.3, 0.82), (0, 4.72, 1.55), 0.52, 0.26, "steel_dark", uv=14, fx={"ribs": 0.16})
    # ---- 丸い用心金と引き金 ----
    trigger_group(b, z_front=-3.2, z_back=-0.75, y_top=1.0, y_bot=0.2, guard="chrome", trig="steel_dark",
                  round_=True)
    # ---- 木の握り（18°、市松）・背の金具・尻の帽子とリング・真鍮のメダル・割れのテープ ----
    gc, gbot, gdown = grip(b, (0, 1.95, -0.25), length=4.3, rake=18.0, w=1.42, d=2.0, style="wood",
                           fx={"knurl": 0.28}, uv=9)
    back = -np.array([0.0, -math.sin(math.radians(18)), -math.cos(math.radians(18))])
    top = np.array([0.0, 1.95, -0.25])
    beam(b, top + back * 1.02, gbot + back * 1.02 - gdown * 0.1, 0.86, 0.16, "chrome", up=tuple(back), uv=12)
    rbeam(b, gbot - gdown * 0.12, gbot + gdown * 0.3, 1.32, 1.9, "chrome", k=0.78, up=(0, -0.31, -0.95), uv=12)
    band(b, gbot + gdown * 0.42 + back * 0.3, (1, 0, 0), 0.62, 0.22, "steel_dark", uv=16)
    add_world(gc, dots([(s * 0.72, 0.05, 0.42) for s in (-1, 1)], 0.34, book.pal(3)),
              WC.crack((0.72, -0.6, 0.9), (0.72, -1.9, 0.5), width=0.05, seed=405, normal=(1, 0, 0)))
    wrap(b, top + gdown * 2.7, top + gdown * 3.7, (1.55, 2.12), "tape", pitch=0.48, tilt=9, seed=406, uv=10,
         tail=(0.5, (0.5, -0.7, 0.6)))
    book.add("chrome", "chrome", base=book.pal(0), dirt=0.32, wear=0.5)
    book.add("cyl", "chrome", base=tuple(int(v * 0.9) for v in book.pal(0)), dirt=0.35)
    book.add("steel_dark", "steel_dark", base=(52, 52, 56))
    book.add("sight_red", "plastic_red", base=(196, 40, 30))
    book.add("wood", "wood_dark", base=book.pal(1), dirt=0.4, grain=1.6)
    book.add("tape", "tape_black", base=(46, 46, 48), dirt=0.5)
    blood = [WC.blood_zone((-0.8, 2.2, -10.6), (0.8, 4.6, -7.0), 0.34, "dry", soft=0.8),
             WC.blood_zone((-0.9, 1.0, -4.2), (0.9, 4.2, -1.4), 0.14, "dry", soft=0.6)]
    return Built(wm, book, blood, hold=dict(scale=0.84, anchor=(0.0, 0.3, 0.3)), icon_yaw=80.0)


# ===========================================================================
#  長物（両手。原点 = 右手の握り、-Z = 銃口）
# ===========================================================================
LONG_NUDGE = (1.9, 0.0, 0.3)       # 腕の静止座標で体の内側（+X）へ: 銃床を腕の横（胸の前）へ逃がす


@builder("pump_shotgun")
def b_pump_shotgun(w) -> Built:
    """ポンプ式散弾銃: 機関部（排莢口の赤い実包・左のサイドサドルに 4 発）、照星の真鍮玉の銃身、
    下のチューブ弾倉、溝付きのポンプとアクションバー、骨組みの銃床（弾差しに 4 発）、ゴムの床尾、
    銃身バンドのスイベルから垂れるパラコードのスリング。"""
    wm = WC.WeaponModel("pump_shotgun", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    yb, ym = 3.05, 1.72
    # ---- 機関部 ----
    rc = rbeam(b, (0, 2.42, -0.4), (0, 2.42, -6.9), 1.62, 2.72, "receiver", k=0.86, uv=7)
    add_world(rc, patch((0.55, 2.55, -4.5), (0.9, 3.5, -1.7), normal=(1, 0, 0), mul=0.18, rim=0.06),
              patch((-0.62, 1.0, -5.6), (0.62, 1.12, -1.6), normal=(0, -1, 0), mul=0.25),
              WC.stamp("RIOT 870", (-3.7, 2.3), 0.42, mul=0.5, side=-1),
              WC.pock(511, cell=0.8, r=0.2, frac=0.4), grime((-1.4, -0.4), dark=0.8, seed=519))
    cbox(b, (0.66, 3.0, -3.1), (0.3, 0.62, 1.5), "shell_red", uv=12)                    # 排莢口の実包
    cbox(b, (0, 3.86, -0.9), (0.5, 0.22, 0.5), "steel", uv=14)                           # 安全装置
    cbox(b, (-0.84, 1.3, -1.9), (0.12, 0.32, 0.7), "steel", uv=14)                        # スライドの解除
    # 左のサイドサドル（板 + 実包 4 発、真鍮を上に）
    cbox(b, (-0.88, 2.45, -3.35), (0.14, 1.9, 3.6), "saddle", uv=9)
    for i in range(4):
        shell(b, (-1.24, 2.5, -4.75 + i * 0.94), (0, -1, 0), d=0.66, length=1.8, simple=True)
    # ---- 銃身・照星・チューブ弾倉・銃身バンド ----
    bl = rod(b, (0, yb, -6.8), (0, yb, -22.6), 1.0, "barrel", uv=6)
    add_world(bl, bore(-22.6, (0, yb), 0.3), soot(-22.6, -20.2, dark=0.42, seed=512),
              WC.paint_band(-19.6, -20.4, book.pal(3), seed=513, chip=0.4), WC.pock(514, cell=0.9, r=0.18, frac=0.3))
    cbox(b, (0, yb + 0.58, -22.15), (0.24, 0.24, 0.24), "bead", uv=16)
    rod(b, (0, ym, -6.8), (0, ym, -18.4), 0.9, "barrel", uv=7)
    rod(b, (0, ym, -18.35), (0, ym, -18.95), 1.0, "cap", uv=12)
    cbox(b, (0, (yb + ym) / 2, -18.0), (1.14, 2.45, 0.5), "clamp", uv=10)
    bolt(b, (0, (yb + ym) / 2, -18.0), (1, 0, 0), 1.6, 0.2, "clamp", nut="clamp", nut_size=0.42, uv=14)
    band(b, (0, ym - 0.75, -18.0), (1, 0, 0), 0.42, 0.18, "steel", round_=False, uv=14)  # スイベル
    # ---- ポンプ（溝 6 本）とアクションバー ----
    pm = rbeam(b, (0, 1.62, -10.1), (0, 1.62, -15.2), 1.64, 1.56, "pump", k=0.82, fx={"ribs": 0.72}, uv=8)
    add_world(pm, grime((-11.0, -14.4), dark=0.72, seed=515))
    for s in (-1, 1):
        beam(b, (s * 0.58, 1.95, -10.2), (s * 0.58, 1.95, -6.8), 0.12, 0.26, "steel", uv=12)
    # ---- 用心金と引き金・握り ----
    trigger_group(b, z_front=-3.3, z_back=-0.75, y_top=1.12, y_bot=0.18, guard="receiver", trig="steel")
    gc, gbot, gdown = grip(b, (0, 1.3, -0.62), length=3.5, rake=20.0, w=1.42, d=1.92, style="poly",
                           fx={"ribs": 0.42}, uv=8)
    # ---- 骨組みの銃床（上の梁・下の梁・床尾の柱・ゴム）----
    st = rbeam(b, (0, 3.02, -0.5), (0, 2.72, 8.55), 1.42, 1.48, "poly", k=0.84, uv=7)
    st += rbeam(b, gbot + np.array([0, 0.3, 0.05]), (0, 0.18, 8.55), 1.36, 1.0, "poly", k=0.84, uv=7)
    st += rbeam(b, (0, -0.3, 8.78), (0, 3.62, 8.78), 1.5, 0.92, "poly", k=0.85, up=(0, 0, 1), uv=8)
    add_world(st, WC.pock(516, cell=0.7, r=0.16, frac=0.35))
    cbox(b, (0, 1.66, 9.48), (1.62, 4.4, 0.56), "rubber", uv=9, fx={"ribs": 0.3})
    # 銃床の弾差し（右、4 発）と割れを巻いたテープ
    cbox(b, (0.8, 2.75, 4.25), (0.16, 1.5, 3.2), "elastic", uv=9)
    for i in range(4):
        shell(b, (0.98, 2.78, 3.0 + i * 0.84), (0, -1, 0), d=0.6, length=1.7, simple=True)
    wrap(b, (0, 2.95, 0.9), (0, 2.9, 2.3), (1.58, 1.62), "tape", pitch=0.5, tilt=8, seed=517, uv=9,
         tail=(0.6, (0.3, -1.0, 0.2)))
    # ---- スリング（パラコード、垂れる）----
    strap(b, [(0, ym - 0.85, -18.0), (0.2, -1.1, -13.0), (0.32, -2.2, -6.0), (0.3, -2.0, 0.5), (0.1, -0.8, 5.5),
              (0, 0.05, 8.2)], w=0.32, t=0.24, style="cord")
    book.add("receiver", "steel_dark", base=(52, 54, 58), wear=0.9, scratches=0.5)
    book.add("barrel", "steel_dark", base=book.pal(0), wear=0.8)
    book.add("cap", "steel_rusty", amount=0.55)
    book.add("clamp", "steel_worn", base=(110, 110, 112))
    book.add("steel", "steel_worn", base=(96, 98, 100))
    book.add("bead", "brass", wear=0.4)
    book.add("pump", "plastic_black", base=book.pal(1), wear=0.5, dirt=0.4)
    book.add("poly", "plastic_black", base=(48, 48, 50), wear=0.5, dirt=0.45)
    book.add("rubber", "rubber_black")
    book.add("saddle", "plastic_black", base=(40, 40, 42))
    book.add("elastic", "cloth_rag", base=(48, 52, 40))
    book.add("shell_red", "plastic_red", base=book.pal(3))
    book.add("shell", "plastic_red", base=book.pal(3), wear=0.4)
    book.add("brass", "brass", wear=0.5)
    book.add("tape", "tape_grey", dirt=0.6)
    book.add("cord", "paracord", base=(70, 78, 60))
    blood = [WC.blood_zone((-0.8, 1.0, -22.8), (0.8, 3.8, -17.5), 0.34, "dry", soft=0.9),
             WC.blood_zone((-0.9, 0.6, -15.4), (0.9, 2.6, -11.0), 0.2, "wet", soft=0.7)]
    return Built(wm, book, blood, hold=dict(scale=0.58, nudge=LONG_NUDGE), icon_yaw=84.0)


@builder("double_barrel")
def b_double_barrel(w) -> Built:
    """水平二連: 並んだ 2 本の銃身と間のリブ（真鍮の照星）、市松の木の先台、唐草の彫刻がすり減った機関部、
    外に出た撃鉄 2 つとトップレバー、引き金 2 本、割れた銃床をテープとねじで留めた跡、ゴムの床尾、
    銃床のゴム紐に挟んだ予備の 2 発、革のスリング。"""
    wm = WC.WeaponModel("double_barrel", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    yb = 1.72
    for s in (-1, 1):
        bl = rod(b, (s * 0.47, yb, -4.3), (s * 0.47, yb, -20.2), 0.94, "barrel", uv=6)
        add_world(bl, bore(-20.2, (s * 0.47, yb), 0.28, soot_r=0.1), soot(-20.2, -18.0, dark=0.45, seed=601 + s),
                  WC.pock(603, cell=0.9, r=0.16, frac=0.3))
    cbox(b, (0, yb + 0.46, -12.25), (0.42, 0.26, 15.8), "rib", uv=8)
    cbox(b, (0, yb - 0.44, -12.25), (0.5, 0.3, 15.8), "barrel", uv=8)
    cbox(b, (0, yb + 0.66, -19.85), (0.22, 0.22, 0.22), "bead", uv=16)
    cbox(b, (0, yb - 0.78, -5.1), (0.92, 0.72, 1.6), "action", uv=11)                    # 銃身の根元の突起
    # ---- 先台（木、市松）と先の金具 ----
    fe = rbeam(b, (0, 0.82, -5.6), (0, 0.82, -10.5), 1.52, 1.16, "wood", k=0.8, fx={"knurl": 0.34}, uv=8)
    add_world(fe, grime((-6.5, -9.5), dark=0.72, seed=604))
    cbox(b, (0, 0.82, -10.65), (1.32, 1.0, 0.36), "action", uv=12)
    # ---- 機関部（彫刻）・立ち上がり・トップレバー・撃鉄 2 つ ----
    ac = rbeam(b, (0, 1.12, -0.95), (0, 1.12, -4.45), 1.62, 2.32, "action", k=0.86, uv=10)
    add_world(ac, engrave(605, lo=(-1, -0.2, -4.5), hi=(1, 2.4, -0.9)), WC.pock(606, cell=0.6, r=0.12, frac=0.25))
    cbox(b, (0, 2.48, -1.2), (1.3, 0.5, 0.74), "action", uv=12)
    beam(b, (0, 2.62, -1.15), (0.58, 2.64, 0.22), 0.3, 0.22, "steel", uv=14)
    for s in (-1, 1):
        beam(b, (s * 0.42, 1.9, -1.3), (s * 0.44, 2.86, -0.38), 0.32, 0.46, "steel", up=(0, 0.3, -1), uv=12)
        beam(b, (s * 0.44, 2.78, -0.45), (s * 0.47, 3.06, 0.26), 0.36, 0.2, "steel", uv=14, fx={"ribs": 0.12})
    # ---- 用心金・引き金 2 本 ----
    polyline(b, [(0, 0.05, -3.4), (0, -0.62, -2.7), (0, -0.75, -1.3), (0, -0.45, -0.25), (0, 0.05, 0.3)], 0.34, 0.26,
             "steel", up=(1, 0, 0), overlap=0.12, uv=12)
    for z_ in (-2.45, -1.6):
        beam(b, (0, 0.05, z_), (0, -0.5, z_ + 0.15), 0.22, 0.22, "steel", uv=14)
    # ---- 銃床: 握りの首（市松）→ 上の線（櫛）・下の線（腹）→ ゴムの床尾 ----
    wr = rbeam(b, (0, 0.62, -1.0), (0, -0.02, 1.95), 1.34, 1.9, "wood", k=0.8, fx={"knurl": 0.3}, uv=8)
    bt = rbeam(b, (0, 0.28, 1.6), (0, -0.02, 8.8), 1.56, 1.62, "wood", k=0.86, uv=7)
    bt += rbeam(b, (0, -0.55, 1.8), (0, -1.72, 8.8), 1.5, 1.52, "wood", k=0.86, uv=7)
    add_world(wr + bt, WC.crack((0.78, 0.4, 3.0), (0.78, -1.2, 6.6), width=0.06, seed=607, normal=(1, 0, 0), branch=0.6),
              WC.crack((-0.78, 0.2, 3.4), (-0.78, -0.8, 5.8), width=0.05, seed=608, normal=(-1, 0, 0)),
              grime((-0.8, 1.6), dark=0.75, seed=609))
    cbox(b, (0, -0.86, 9.06), (1.62, 3.42, 0.5), "rubber", uv=9, fx={"ribs": 0.26})
    # 割れの補修: テープの帯 2 本とねじ
    for z_ in (4.0, 5.6):
        rbeam(b, (0, -0.72, z_ - 0.32), (0, -0.82, z_ + 0.32), 1.66, 3.14, "tape", k=0.9, fx={"wrap": 0.3}, uv=9)
    for p in ((0.8, 0.3, 4.8), (0.8, -1.1, 6.6)):
        rivet(b, p, (1, 0, 0), d=0.3, h=0.06, style="steel", uv=16)
    # 右のゴム紐と予備の 2 発
    cbox(b, (-0.82, -0.75, 7.0), (0.12, 1.9, 0.5), "elastic", uv=12)
    for i in range(2):
        shell(b, (-0.98, -0.75, 6.62 + i * 0.76), (0, -1, 0), d=0.62, length=1.7, simple=True)
    # 革のスリング（先台の金具 → 銃床の下）
    strap(b, [(0, 0.3, -10.6), (0.25, -1.4, -6.0), (0.3, -2.4, 0.0), (0.2, -2.6, 5.0), (0, -2.15, 8.2)], w=0.55,
          t=0.12, style="sling")
    book.add("barrel", "steel_dark", base=book.pal(0), wear=0.85)
    book.add("rib", "steel_worn", base=(82, 84, 88))
    book.add("bead", "brass", wear=0.4)
    book.add("action", "steel_worn", base=(150, 146, 136), scratches=0.7, dirt=0.4)
    book.add("steel", "steel_dark", base=(56, 56, 60))
    book.add("wood", "wood_old", base=book.pal(1), dirt=0.45, grain=1.4)
    book.add("rubber", "rubber_black")
    book.add("tape", "tape_grey", dirt=0.6)
    book.add("elastic", "cloth_rag", base=(36, 36, 38))
    book.add("shell", "plastic_red", base=(150, 30, 28), wear=0.4)
    book.add("brass", "brass", base=book.pal(2), wear=0.5)
    book.add("sling", "leather_brown")
    blood = [WC.blood_zone((-1.0, 0.8, -20.4), (1.0, 2.6, -16.0), 0.32, "dry", soft=0.9),
             WC.blood_zone((-0.9, -2.6, 5.0), (0.9, 0.9, 9.4), 0.18, "dry", soft=0.7)]
    return Built(wm, book, blood, hold=dict(scale=0.6, nudge=LONG_NUDGE), icon_yaw=84.0)


@builder("hunting_rifle")
def b_hunting_rifle(w) -> Built:
    """狩猟用ライフル: 一本の木の銃床（市松の握り・布を縛った頬当て・パラコードを巻いた先台・ゴムの床尾）、
    円い機関部と右へ出たボルトの取っ手、細い銃身の先に横穴のマズルブレーキ、リングで留めたスコープ
    （開いた前蓋・レンズの照り・テープ）、箱形弾倉の底板、革のスリングと真鍮の金具、左の弾差しに 5 発。"""
    wm = WC.WeaponModel("hunting_rifle", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    yb = 2.95
    # ---- 握り（市松）・握りの帽子 ----
    gc, gbot, gdown = grip(b, (0, 1.55, -0.62), length=3.0, rake=22.0, w=1.42, d=1.86, style="wood",
                           fx={"knurl": 0.26}, uv=8)
    rbeam(b, gbot - gdown * 0.08, gbot + gdown * 0.24, 1.3, 1.7, "wood_dark", k=0.8, up=(0, -0.37, -0.93), uv=12)
    # ---- 銃床（後ろ 3 段で太る）・頬当て・床尾 ----
    bt = [beam(b, (0, 1.78, 0.6), (0, 1.58, 3.45), 1.5, 2.4, "wood", uv=7),
          beam(b, (0, 1.52, 3.35), (0, 1.32, 5.65), 1.56, 3.0, "wood", uv=7),
          beam(b, (0, 1.3, 5.55), (0, 1.2, 7.65), 1.6, 3.4, "wood", uv=7)]
    add_world(bt + gc, grime((-0.8, 1.0), dark=0.72, seed=701), WC.crack((0.76, 0.8, 4.0), (0.76, 0.2, 6.8),
                                                                        width=0.05, seed=702, normal=(1, 0, 0)))
    cbox(b, (0, 3.18, 3.3), (1.34, 0.52, 3.3), "cloth", uv=9, fx={"wrap": 0.35})
    for z_ in (2.2, 4.4):
        lash(b, (0, 1.95, z_), (0, 0, 1), 1.62, 3.0, 0.2, 1, "cord", wire=0.16)
    cbox(b, (0, 1.22, 7.92), (1.66, 3.52, 0.5), "rubber", uv=9, fx={"ribs": 0.24})
    # ---- 機関部の下と先台（先に暗い木の帽子、パラコードの巻き）----
    md = rbeam(b, (0, 1.95, 0.9), (0, 1.95, -6.7), 1.6, 1.7, "wood", k=0.82, uv=7)
    fe = rbeam(b, (0, 2.05, -6.6), (0, 2.15, -15.0), 1.5, 1.42, "wood", k=0.82, uv=7)
    add_world(md + fe, WC.pock(703, cell=1.0, r=0.2, frac=0.3))
    cbox(b, (0, 2.15, -15.17), (1.4, 1.3, 0.36), "wood_dark", uv=12)
    wrap(b, (0, 2.08, -9.0), (0, 2.12, -11.9), (1.66, 1.58), "cord", pitch=0.5, tilt=9, seed=704, uv=9)
    # ---- 機関部・ボルト・排莢口 ----
    rc = rbeam(b, (0, yb, -0.7), (0, yb, -6.6), 1.32, 1.5, "receiver", k=0.8, uv=9)
    add_world(rc, patch((0.5, 2.6, -4.7), (0.8, 3.65, -2.4), normal=(1, 0, 0), mul=0.2, rim=0.05),
              WC.stamp("NR .308", (-4.4, 2.75), 0.36, mul=0.5, side=-1))
    cbox(b, (0.55, 2.95, -3.5), (0.14, 0.5, 1.6), "bolt", uv=14)                         # 排莢口から見えるボルト
    rod(b, (0, yb, -0.75), (0, yb, 0.55), 1.02, "receiver", uv=11)                       # ボルトの後ろの覆い
    cbox(b, (0, yb + 0.1, 0.72), (0.5, 0.62, 0.42), "receiver", uv=14)
    beam(b, (0.55, yb, -1.45), (1.65, 2.42, -1.2), 0.34, 0.34, "bolt", uv=14)
    disc(b, (1.95, 2.33, -1.15), (1, 0.3, 0), 0.42, 0.62, "bolt", n=2, uv=14)
    # ---- 銃身（2 段で細る）とマズルブレーキ（横穴 3 つずつ）----
    bl = rod(b, (0, yb, -6.6), (0, yb, -15.0), 0.86, "barrel", uv=7)
    bl += rod(b, (0, yb, -14.95), (0, yb, -23.6), 0.74, "barrel", uv=7)
    add_world(bl, soot(-23.6, -21.0, dark=0.45, seed=705))
    mb = rbeam(b, (0, yb, -23.5), (0, yb, -25.3), 1.1, 1.1, "brake", k=0.86, uv=12)
    ports = [(s * 0.55, yb, z_) for s in (-1, 1) for z_ in (-23.9, -24.4, -24.9)]
    add_world(mb, holes_on([p for p in ports if p[0] > 0], 0.17, normal=(1, 0, 0)),
              holes_on([p for p in ports if p[0] < 0], 0.17, normal=(-1, 0, 0)), bore(-25.3, (0, yb), 0.22))
    # ---- スコープ（リング 2 つ・台・開いた前蓋・テープ）----
    sc = scope(b, -9.9, 0.9, 4.75, d=1.08, bell=1.72, uv=8)
    for z_ in (-6.1, -1.7):
        band(b, (0, 4.75, z_), (0, 0, 1), 1.3, 0.55, "ring", uv=12)
        cbox(b, (0, 3.98, z_), (0.8, 0.82, 0.6), "ring", uv=12)
    cbox(b, (0, 5.95, -10.0), (1.24, 0.95, 0.12), "plastic", rot=(-12, 0, 0), uv=14)      # 開いた前蓋
    band(b, (0, 4.75, -3.9), (0, 0, 1), 1.2, 0.85, "tape", uv=10)
    add_world(sc, WC.stamp("4x32", (-4.6, 4.75), 0.32, mul=0.45, side=-1))
    # ---- 弾倉の底板・用心金・引き金 ----
    cbox(b, (0, 1.02, -4.4), (1.0, 0.3, 2.2), "receiver", uv=12)
    trigger_group(b, z_front=-3.0, z_back=-0.7, y_top=1.12, y_bot=0.28, guard="receiver", trig="bolt")
    # ---- スイベルと革のスリング（真鍮の金具）----
    for c_ in ((0, -0.42, 5.4), (0, 1.22, -12.8)):
        band(b, c_, (1, 0, 0), 0.5, 0.16, "brass", round_=False, uv=16)
    strap(b, [(0, 1.0, -12.8), (0.25, -1.3, -9.0), (0.35, -2.5, -3.0), (0.25, -2.1, 2.0), (0, -0.58, 5.4)],
          w=0.55, t=0.12, style="sling")
    cbox(b, (0.36, -2.42, -2.4), (0.2, 0.7, 0.62), "brass", uv=14)                      # スリングの尾錠
    # ---- 左の弾差し（ゴム紐 + 5 発）----
    cbox(b, (-0.84, 1.55, 4.45), (0.16, 1.2, 2.8), "elastic", uv=10)
    for i in range(5):
        cartridge(b, (-1.0, 1.7, 3.35 + i * 0.55), (0, 1, 0), d=0.34, length=1.95)
    book.add("wood", "wood_old", base=book.pal(1), dirt=0.4, grain=1.5)
    book.add("wood_dark", "wood_dark", base=(58, 38, 26))
    book.add("receiver", "steel_dark", base=(48, 50, 54), wear=0.9)
    book.add("barrel", "steel_dark", base=book.pal(0), wear=0.7)
    book.add("bolt", "steel_clean", base=(150, 152, 156))
    book.add("brake", "steel_dark", base=(44, 44, 46))
    book.add("scope", "steel_dark", base=(36, 38, 40), wear=0.8)
    book.add("ring", "steel_worn", base=(70, 72, 74))
    book.add("lens", "glass_tinted", base=(70, 120, 150))
    book.add("plastic", "plastic_black")
    book.add("cloth", "cloth_rag", base=(92, 84, 64))
    book.add("cord", "paracord", base=(60, 70, 52))
    book.add("rubber", "rubber_black")
    book.add("tape", "tape_black", dirt=0.5)
    book.add("sling", "leather_brown")
    book.add("elastic", "cloth_rag", base=(40, 40, 40))
    book.add("brass", "brass", base=book.pal(2), wear=0.5)
    book.add("copper", "brass", base=(176, 102, 60), wear=0.3)
    blood = [WC.blood_zone((-0.8, 1.4, -15.4), (0.8, 3.4, -10.0), 0.22, "dry", soft=0.9),
             WC.blood_zone((-0.9, -0.6, 4.0), (0.9, 3.2, 8.2), 0.14, "dry", soft=0.7)]
    return Built(wm, book, blood, hold=dict(scale=0.56, nudge=LONG_NUDGE), icon_yaw=86.0)


@builder("scrap_smg")
def b_scrap_smg(w) -> Built:
    """手製サブマシンガン: 水道管の機関部（継ぎ手・溶接のビード・端の蓋）、穴あきの放熱筒、左へ突き出した
    横差しの長い弾倉（テープ巻き）、右の真鍮のコッキング、黒いテープを巻いた握り、針金の用心金、
    ホースバンドで留めた木の前握り、曲げた鉄筋のストックとチューブを巻いた肩当て、スプレーの落書き。"""
    wm = WC.WeaponModel("scrap_smg", uv=7)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    yb = 2.25
    # ---- 握り（芯 + 黒テープの巻き）----
    gc, gbot, gdown = grip(b, (0, 1.62, -0.35), length=3.6, rake=12.0, w=1.2, d=1.62, style="grip_core", uv=8)
    top = np.array([0.0, 1.62, -0.35])
    wrap(b, top + gdown * 0.15, top + gdown * 3.45, (1.4, 1.84), "tape_black", pitch=0.46, tilt=11, seed=801, uv=9,
         tail=(0.5, (0.4, -0.6, 0.7)))
    # ---- 機関部（水道管）・継ぎ手・蓋・溶接 ----
    rc = rod(b, (0, yb, 2.2), (0, yb, -6.9), 1.6, "pipe", uv=7)
    add_world(rc, patch((0.6, 2.05, -3.8), (0.9, 2.45, 0.6), normal=(1, 0, 0), mul=0.15, rim=0.05),
              graffiti((214, 196, 70), [[(-5.8, 2.3), (-5.2, 2.8), (-4.6, 2.2), (-4.0, 2.75)]], side=1, width=0.13),
              WC.stamp("NR", (-1.6, 2.25), 0.5, tint=(200, 60, 40), side=-1), WC.pock(802, cell=0.6, r=0.14, frac=0.4))
    for z_, ln in ((-6.6, 0.7), (1.85, 0.6)):
        band(b, (0, yb, z_), (0, 0, 1), 1.9, ln, "coupling", uv=10)
    octo(b, (0, yb, 2.45), (0, 0, 1), 1.0, 0.5, "coupling", uv=12)
    for z_ in (-6.2, -7.0, 1.5):
        weld(b, [(math.cos(t) * 0.84, yb + math.sin(t) * 0.84, z_) for t in np.linspace(0.3, 2.85, 4)], 0.24,
             "weld", seed=int(abs(z_) * 10), step=0.55, uv=14)
    # ---- 放熱筒（穴）・蓋・銃口・照星（曲げた釘）・照門（座金）----
    sh = rod(b, (0, yb, -6.9), (0, yb, -12.8), 1.42, "shroud", uv=8, fx={"holes": (0.62, 0.26)})
    add_world(sh, soot(-12.8, -10.0, dark=0.5, seed=803))
    band(b, (0, yb, -12.72), (0, 0, 1), 1.52, 0.3, "coupling", uv=12)
    tip = rod(b, (0, yb, -12.8), (0, yb, -13.7), 0.7, "barrel", uv=14)
    add_world(tip, bore(-13.7, (0, yb), 0.2))
    beam(b, (0, yb + 0.65, -12.3), (0.04, yb + 1.25, -12.38), 0.18, 0.18, "barrel", uv=16)
    disc(b, (0, yb + 1.2, 1.0), (0, 0, 1), 0.36, 0.12, "barrel", n=2, uv=16)
    beam(b, (0, yb + 0.7, 1.0), (0, yb + 0.95, 1.0), 0.16, 0.16, "barrel", uv=16)
    # ---- 左の弾倉受けと長い弾倉（テープの帯 2 本）----
    beam(b, (-0.6, yb, -4.4), (-2.1, yb, -4.4), 1.82, 1.12, "pipe", uv=10)
    mg = beam(b, (-2.0, yb, -4.4), (-6.3, yb - 0.12, -4.48), 1.56, 0.86, "mag", uv=9)
    add_world([mg], WC.pock(804, cell=0.5, r=0.12, frac=0.35))
    beam(b, (-6.25, yb - 0.12, -4.48), (-6.55, yb - 0.13, -4.48), 1.72, 1.02, "mag", uv=12)
    for x_ in (-3.3, -5.0):
        beam(b, (x_ + 0.3, yb - 0.06, -4.42), (x_ - 0.3, yb - 0.08, -4.44), 1.66, 0.96, "tape_yellow",
             fx={"wrap": 0.3}, uv=10)
    # ---- コッキング（右、真鍮）・引き金の箱と鋲 ----
    rod(b, (0.72, 2.32, -1.3), (1.28, 2.32, -1.3), 0.5, "brass", uv=14)
    disc(b, (1.3, 2.32, -1.3), (1, 0, 0), 0.34, 0.14, "brass", n=2, uv=16)
    cbox(b, (0, 1.32, -1.5), (1.12, 0.62, 2.7), "plate", uv=10)
    for p in ((0.57, 1.32, -2.4), (0.57, 1.32, -0.6), (-0.57, 1.32, -2.4), (-0.57, 1.32, -0.6)):
        rivet(b, p, (np.sign(p[0]), 0, 0), d=0.26, h=0.05, style="weld", uv=16)
    # ---- 針金の用心金と引き金 ----
    polyline(b, [(0, 1.05, -2.75), (0, 0.42, -2.6), (0, 0.26, -1.9), (0, 0.28, -0.9), (0, 0.88, -0.5)], 0.18, 0.18,
             "wire", up=(1, 0, 0), overlap=0.08, uv=16)
    beam(b, (0, 1.05, -1.75), (0, 0.55, -1.65), 0.24, 0.2, "plate", uv=14)
    beam(b, (0, 0.6, -1.65), (0, 0.36, -1.4), 0.22, 0.18, "plate", uv=14)
    # ---- 木の前握り（ホースバンドとねじ）----
    beam(b, (0, 1.4, -7.8), (0.05, -1.35, -7.6), 1.02, 1.22, "wood", up=(0, 0, -1), uv=8,
         fx={"world": grime((-8.5, -7.0), dark=0.7, seed=805)})
    band(b, (0, yb, -7.8), (0, 0, 1), 1.62, 0.5, "clamp", uv=12)
    cbox(b, (0.86, yb + 0.2, -7.8), (0.3, 0.42, 0.5), "clamp", uv=14)
    # ---- 鉄筋のストック（2 本）・肩当て・チューブの巻き・溶接 ----
    polyline(b, [(0, 2.85, 2.2), (0, 2.6, 5.2), (0, 2.08, 9.6)], 0.4, 0.4, "rebar", overlap=0.12, uv=10,
             fx={"rebar": 0.36})
    polyline(b, [(0, 1.5, 1.4), (0, 0.42, 5.0), (0, -0.12, 9.6)], 0.4, 0.4, "rebar", overlap=0.12, uv=10,
             fx={"rebar": 0.36})
    beam(b, (0, -0.55, 9.8), (0, 2.5, 9.8), 0.62, 0.72, "rebar", up=(0, 0, 1), uv=10)
    rbeam(b, (0, -0.35, 9.82), (0, 2.3, 9.82), 0.95, 1.02, "rubber", k=0.82, up=(0, 0, 1), uv=9, fx={"ribs": 0.3})
    weld(b, [(0, 2.82, 2.3), (0, 2.6, 2.6)], 0.26, "weld", seed=806, step=0.4, uv=14)
    weld(b, [(0, 1.5, 1.5), (0, 1.25, 1.8)], 0.26, "weld", seed=807, step=0.4, uv=14)
    # ---- スリング（オリーブの帯）----
    strap(b, [(0, 2.9, 9.4), (0.3, 3.9, 4.0), (0.4, 3.6, -3.0), (0.3, 3.1, -7.6)], w=0.5, t=0.12, style="sling",
          up=(1, 0, 0))
    book.add("grip_core", "wood_raw", dirt=0.4)
    book.add("tape_black", "tape_black", base=book.pal(1), dirt=0.45)
    book.add("pipe", "steel_worn", base=book.pal(0), scratches=0.7, dirt=0.5)
    book.add("coupling", "iron_cast", base=(96, 92, 86))
    book.add("weld", "steel_rusty", amount=0.45, metal=(110, 104, 96))
    book.add("shroud", "steel_dark", base=(64, 66, 70), wear=0.7)
    book.add("barrel", "steel_dark", base=(52, 54, 58))
    book.add("mag", "steel_dark", base=(60, 62, 64), wear=0.85)
    book.add("tape_yellow", "tape_grey", base=(196, 168, 52), dirt=0.55)
    book.add("brass", "brass", base=book.pal(3), wear=0.6)
    book.add("plate", "steel_worn", base=book.pal(2), dirt=0.5)
    book.add("wire", "steel_worn", base=(120, 118, 112))
    book.add("wood", "wood_raw", base=(150, 116, 74), dirt=0.45)
    book.add("clamp", "steel_clean", base=(170, 172, 174), dirt=0.3)
    book.add("rebar", "rebar")
    book.add("rubber", "rubber_black", dirt=0.4)
    book.add("sling", "cloth_rag", base=book.pal(4), dirt=0.5)
    blood = [WC.blood_zone((-0.9, 1.2, -13.9), (0.9, 3.4, -9.5), 0.3, "dry", soft=0.9),
             WC.blood_zone((-6.6, 1.4, -5.4), (-3.5, 3.0, -3.4), 0.2, "dry", soft=0.6)]
    return Built(wm, book, blood, hold=dict(scale=0.64, nudge=LONG_NUDGE), icon_yaw=84.0)


# ===========================================================================
#  弓・クロスボウ
# ===========================================================================
@builder("crossbow")
def b_crossbow(w) -> Built:
    """改造クロスボウ: ライフルの廃材の銃床（布を巻いた頬当て・ゴムの床尾）、溝付きのアルミのレール、
    車の板バネ 2 枚のリム（U ボルトと錆びた留め金）、引いた弦と止め金、装填中のボルト（黄色の羽根・広刃）、
    鉄筋の足掛け、古い光学照準、針金の用心金、パラコードを巻いた前握り、右に縛った予備のボルト 2 本。"""
    wm = WC.WeaponModel("crossbow", uv=6)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    yr = 3.75                                               # レールの芯
    # ---- 握り・銃床・頬当て・床尾 ----
    gc, gbot, gdown = grip(b, (0, 1.75, -0.5), length=3.6, rake=16.0, w=1.42, d=1.8, style="wood",
                           fx={"knurl": 0.3}, uv=8)
    st = rbeam(b, (0, 2.3, 0.4), (0, 1.95, 9.0), 1.6, 2.2, "wood", k=0.84, uv=7)
    st += [beam(b, (0, 1.0, 5.2), (0, 0.62, 9.0), 1.54, 1.3, "wood", uv=7)]
    add_world(st, WC.crack((0.8, 2.2, 3.0), (0.8, 1.4, 7.6), width=0.05, seed=901, normal=(1, 0, 0)),
              grime((0.2, 2.2), dark=0.75, seed=902))
    cbox(b, (0, 3.32, 3.9), (1.46, 0.56, 3.4), "cloth", uv=9, fx={"wrap": 0.32})
    for z_ in (2.5, 5.3):
        lash(b, (0, 2.35, z_), (0, 0, 1), 1.66, 2.6, 0.22, 1, "cord", wire=0.15)
    cbox(b, (0, 1.4, 9.26), (1.66, 3.3, 0.46), "rubber", uv=9, fx={"ribs": 0.26})
    # ---- 前の台（木）とレール（アルミの溝）----
    tl = rbeam(b, (0, 2.5, 0.6), (0, 2.62, -12.8), 1.5, 1.62, "wood", k=0.84, uv=7)
    add_world(tl, WC.pock(903, cell=1.0, r=0.2, frac=0.3))
    rl = cbox(b, (0, yr, -8.2), (1.22, 0.72, 14.0), "rail", uv=8)
    add_world([rl], patch((-0.2, yr + 0.3, -15.3), (0.2, yr + 0.4, -1.1), normal=(0, 1, 0), mul=0.35, rim=0.04),
              WC.stamp("NR-XB", (-11.0, yr), 0.34, mul=0.5, side=1))
    # ---- 止め金と引いた弦 ----
    cbox(b, (0, yr + 0.5, -6.4), (1.0, 0.82, 1.5), "steel", uv=11)
    cbox(b, (0, yr + 0.98, -6.0), (0.5, 0.22, 0.7), "steel", uv=14)
    zt, xt = -12.3, 7.95
    for s in (-1, 1):
        beam(b, (s * xt, yr + 0.2, zt), (s * 0.3, yr + 0.45, -7.05), 0.16, 0.16, "string", uv=16, tags=("soft",))
    # ---- 板バネのリム（主の板・補助の板・目玉）と留め金・U ボルト ----
    zp = -14.6
    for s in (-1, 1):
        pts = [(0, yr - 0.2, zp), (s * 2.8, yr - 0.2, zp + 0.15), (s * 5.4, yr - 0.2, zp + 0.75),
               (s * 7.2, yr - 0.2, zp + 1.65), (s * xt, yr - 0.2, zt)]
        polyline(b, pts, 0.46, 1.0, "spring", up=(0, 1, 0), overlap=0.14, uv=8)
        polyline(b, [(0, yr - 0.2, zp - 0.45), (s * 2.6, yr - 0.2, zp - 0.32), (s * 4.3, yr - 0.2, zp + 0.05)], 0.36,
                 0.9, "spring", up=(0, 1, 0), overlap=0.12, uv=9)
        rod(b, (s * xt, yr - 0.85, zt), (s * xt, yr + 0.45, zt), 0.6, "steel", uv=12)
    cl = cbox(b, (0, yr - 0.2, zp + 0.05), (2.4, 2.0, 1.8), "rust", uv=9)
    add_world([cl], WC.pock(904, cell=0.5, r=0.14, frac=0.5))
    for s in (-1, 1):
        beam(b, (s * 1.32, yr - 1.35, zp - 0.15), (s * 1.32, yr + 1.0, zp - 0.15), 0.22, 0.22, "steel", uv=14)
        hex_prism(b, (s * 1.32, yr + 1.05, zp - 0.15), (0, 1, 0), 0.5, 0.26, "steel", uv=16)
    beam(b, (-1.42, yr - 1.35, zp - 0.15), (1.42, yr - 1.35, zp - 0.15), 0.22, 0.22, "steel", uv=14)
    # ---- 足掛け（鉄筋の U）----
    for p0, p1 in (((-1.25, yr - 0.4, zp - 0.9), (-1.5, yr - 0.45, -18.1)),
                   ((1.25, yr - 0.4, zp - 0.9), (1.5, yr - 0.45, -18.1)),
                   ((-1.62, yr - 0.45, -18.1), (1.62, yr - 0.45, -18.1))):
        beam(b, p0, p1, 0.32, 0.32, "rebar", uv=12, fx={"rebar": 0.3})
    # ---- 装填中のボルト（軸・広刃・黄色い羽根 3 枚）----
    yv = yr + 0.55
    rod(b, (0, yv, -7.05), (0, yv, -15.7), 0.34, "bolt", uv=12)
    cbox(b, (0, yv, -16.2), (0.12, 0.8, 1.1), "head", rot=(45, 0, 0), uv=16, tags=("edge",))
    cbox(b, (0, yv, -16.2), (0.8, 0.12, 1.1), "head", rot=(0, 45, 0), uv=16)
    cbox(b, (0, yv, -15.75), (0.36, 0.36, 0.36), "head", uv=16)
    for ang in (90.0, 210.0, 330.0):
        d = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0.0])
        beam(b, (0, yv, -7.4) + d * 0.32, (0, yv, -8.9) + d * 0.32, 0.06, 0.46, "vane", up=tuple(d), uv=16)
    # ---- 古い光学照準と台 ----
    scope(b, -5.6, -1.6, yr + 1.9, d=0.86, bell=1.18, uv=10)
    for z_ in (-2.4, -4.9):
        cbox(b, (0, yr + 1.12, z_), (0.5, 1.0, 0.5), "steel", uv=14)
    # ---- 針金の用心金・引き金（長いレバー）----
    polyline(b, [(0, 1.55, -2.7), (0, 0.6, -2.6), (0, 0.42, -1.6), (0, 0.55, -0.85), (0, 1.15, -0.7)], 0.2, 0.2, "wire",
             up=(1, 0, 0), overlap=0.08, uv=16)
    beam(b, (0, 1.65, -1.9), (0, 0.72, -1.7), 0.26, 0.24, "steel", uv=14)
    # ---- パラコードの前握り ----
    wrap(b, (0, 2.6, -8.4), (0, 2.62, -11.0), (1.64, 1.76), "cord", pitch=0.5, tilt=9, seed=905, uv=9)
    # ---- 右に縛った予備のボルト 2 本 ----
    for i, y_ in enumerate((1.6, 2.5)):
        rod(b, (0.98, y_, 0.6), (0.98, y_, 8.2), 0.3, "bolt", uv=12)
        cbox(b, (0.98, y_, 0.35), (0.12, 0.62, 0.7), "head", rot=(45, 0, 0), uv=16)
        beam(b, (0.98, y_ + 0.12, 7.0), (0.98, y_ + 0.12, 8.2), 0.06, 0.4, "vane", uv=16)
    for z_ in (2.5, 6.4):
        cbox(b, (0.98, 2.05, z_), (0.4, 1.6, 0.4), "strap", uv=12)
    book.add("wood", "wood_old", base=book.pal(1), dirt=0.45, grain=1.4)
    book.add("cloth", "cloth_rag", base=(120, 40, 34))
    book.add("cord", "paracord", base=(60, 66, 54))
    book.add("rubber", "rubber_black")
    book.add("rail", "aluminium", base=book.pal(2), dirt=0.45)
    book.add("steel", "steel_dark", base=book.pal(0))
    book.add("string", "rope", base=(60, 58, 52))
    book.add("spring", "steel_painted", base=(40, 42, 46), rust=0.6)
    book.add("rust", "steel_rusty", amount=0.8)
    book.add("rebar", "rebar")
    book.add("bolt", "aluminium", base=(66, 70, 74))
    book.add("head", "steel_clean", base=(172, 176, 178))
    book.raw("vane", NP.style("plastic", base=book.pal(3), wear=0.2))
    book.add("scope", "steel_dark", base=(40, 42, 44), wear=0.8)
    book.add("ring", "steel_worn", base=(80, 80, 82))
    book.add("lens", "glass_tinted", base=(80, 130, 150))
    book.add("wire", "steel_worn", base=(120, 118, 112))
    book.add("strap", "leather_brown", base=(70, 48, 30))
    blood = [WC.blood_zone((-0.6, 3.6, -17.0), (0.6, 4.8, -15.0), 0.4, "wet", soft=0.6),
             WC.blood_zone((-3.0, 2.6, -15.6), (3.0, 4.6, -13.4), 0.16, "dry", soft=0.8)]
    return Built(wm, book, blood, hold=dict(scale=0.56, nudge=LONG_NUDGE), icon_yaw=70.0)


@builder("survivor_bow")
def b_survivor_bow(w) -> Built:
    """生存者の弓（右手で持つ。+Y = 上の弭、-Z = 矢の向き、弦は +Z）: 肉抜きの穴の金属のライザー、
    パラコードの握り、スキー板を切った反りのリム（黄色いロゴの名残・板の底の色・補修テープ）、先の滑車、
    矢の置き台、発光の照準ピン、布の重りの安定棒、結んだ赤い布。弦（上下 2 本のボーン）と番えた矢は
    使う間（v.nr_usew）に後ろへ引かれる。"""
    wm = WC.WeaponModel("survivor_bow", uv=8)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    # ---- ライザー（握り・矢の棚・上は左へ寄せて窓・下）とリムの受け ----
    rs = [beam(b, (0, -1.95, 0.2), (0, 1.15, 0.2), 1.16, 1.86, "riser", up=(0, 0, 1), uv=9),
          cbox(b, (-0.1, 1.32, 0.05), (1.0, 0.36, 1.7), "riser", uv=11),
          beam(b, (-0.42, 1.3, -0.12), (-0.25, 4.8, 0.3), 0.72, 1.5, "riser", up=(0, 0, 1), uv=9),
          beam(b, (0, -1.8, 0.05), (0, -4.8, 0.32), 1.1, 1.5, "riser", up=(0, 0, 1), uv=9)]
    add_world(rs, WC.pock(951, cell=0.6, r=0.12, frac=0.35), WC.stamp("NR", (0.2, -3.2), 0.42, mul=0.5, side=1))
    wm.cut((0, 3.15, 0.1), (1, 0, 0), r=0.36, half=1.2)
    wm.cut((0, -3.35, 0.2), (1, 0, 0), r=0.38, half=1.2)
    for s in (-1, 1):
        cbox(b, (-0.1 if s > 0 else 0.0, s * 5.0, 0.42), (1.32, 0.7, 1.62), "riser", uv=11)
        hex_prism(b, (0, s * 5.0, -0.45), (0, 0, 1), 0.56, 0.24, "bolt", uv=16)
    # ---- 握りのパラコード ----
    wrap(b, (0, -1.8, 0.24), (0, 0.95, 0.24), (2.06, 1.4), "cord", pitch=0.4, tilt=9, seed=952, uv=10)
    # ---- 反りのリム（上下。スキー板）と補修テープ・先の滑車 ----
    up_pts = [(4.6, 0.55), (6.6, 1.05), (8.8, 1.55), (10.8, 1.85), (12.2, 1.72), (13.05, 1.2)]
    limbs = []
    for s in (-1, 1):
        pts = [(0.0, s * y, z) for y, z in up_pts]
        limbs += polyline(b, pts, [1.14, 1.1, 1.02, 0.94, 0.86], [0.5, 0.46, 0.42, 0.38, 0.36], "limb",
                          up=(0, 0, 1), overlap=0.16, uv=9)
        c = np.array([0.0, s * 13.1, 1.62])
        disc(b, c, (1, 0, 0), 0.8, 0.42, "cam", n=3, uv=12)
        rod(b, c - (0.42, 0, 0), c + (0.42, 0, 0), 0.26, "bolt", uv=16)
    # スキー板の名残: 背（-Z）に黄色いロゴの帯、腹（+Z、弦の側）は滑走面の赤
    add_world(limbs, patch((-1, 6.2, -9), (1, 8.6, 9), normal=(0, 0, -1), rgb=(214, 180, 44)),
              patch((-1, -8.6, -9), (1, -6.2, 9), normal=(0, 0, -1), rgb=(214, 180, 44)),
              patch((-1, -14, -9), (1, 14, 9), normal=(0, 0, 1), rgb=(140, 34, 28)))
    for y_ in (-7.8, -9.1):
        beam(b, (0, y_ + 0.3, 1.36 + (y_ + 7.8) * -0.22), (0, y_ - 0.3, 1.46 + (y_ + 7.8) * -0.22), 1.24, 0.6,
             "tape", up=(0, 0, 1), uv=10, fx={"wrap": 0.3})
    # ---- 弦（上下のボーン。使う間に後ろへ）と番えた矢 ----
    T, B_, N = (0.0, 12.95, 2.38), (0.0, -12.95, 2.38), (0.0, 1.66, 2.38)
    su = wm.bone("str_u", pivot=T)
    beam(su, T, N, 0.14, 0.14, "string", uv=16, tags=("soft",))
    cbox(su, (0, 1.95, 2.38), (0.24, 0.5, 0.24), "serving", uv=16)
    sd = wm.bone("str_d", pivot=B_)
    beam(sd, B_, N, 0.14, 0.14, "string", uv=16, tags=("soft",))
    cbox(sd, (0, 1.2, 2.38), (0.22, 0.6, 0.22), "serving", uv=16)
    ar = wm.bone("arrow", pivot=N)
    xa = 0.2
    rod(ar, (xa, 1.66, 2.3), (xa, 1.66, -11.6), 0.24, "shaft", uv=12, tags=("soft",))
    cbox(ar, (xa, 1.66, -12.15), (0.1, 0.72, 1.1), "head", rot=(45, 0, 0), uv=16, tags=("soft", "edge"))
    cbox(ar, (xa, 1.66, -12.15), (0.72, 0.1, 1.1), "head", rot=(0, 45, 0), uv=16, tags=("soft",))
    for ang in (90.0, 210.0, 330.0):
        d = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0.0])
        beam(ar, (xa, 1.66, 0.4) + d * 0.22, (xa, 1.66, 1.9) + d * 0.22, 0.05, 0.42, "vane", up=tuple(d), uv=16,
             tags=("soft",))
    cbox(ar, (xa, 1.66, 2.42), (0.3, 0.3, 0.28), "nock", uv=16, tags=("soft",))
    D = 9.0
    ku, kd = D / (T[1] - N[1]), D / (N[1] - B_[1])
    wm.idle = {
        "str_u": {"rotation": [f"math.atan({ku:.4f} * v.nr_usew)", 0.0, 0.0],
                  "scale": [1.0, f"math.sqrt(1.0 + {ku * ku:.4f} * v.nr_usew * v.nr_usew)", 1.0]},
        "str_d": {"rotation": [f"-math.atan({kd:.4f} * v.nr_usew)", 0.0, 0.0],
                  "scale": [1.0, f"math.sqrt(1.0 + {kd * kd:.4f} * v.nr_usew * v.nr_usew)", 1.0]},
        "arrow": {"position": [0.0, 0.0, f"{D:.1f} * v.nr_usew"],
                  "scale": ["v.nr_usew > 0.12 ? 1.0 : 0.0"] * 3},
    }
    # ---- 矢の置き台・照準ピン（発光）・安定棒と布の重り・結んだ赤い布 ----
    cbox(b, (0.36, 1.42, 0.02), (0.5, 0.16, 1.1), "steel", uv=16)
    beam(b, (0.55, 2.6, 0.05), (1.15, 2.6, -0.55), 0.3, 0.5, "alu", uv=14)
    cbox(b, (1.25, 2.62, -0.72), (0.36, 1.36, 0.5), "alu", uv=14)
    cbox(b, (1.25, 2.8, -0.44), (0.14, 0.14, 0.1), "glow_green", uv=16, tags=("noao",))
    beam(b, (1.25, 2.1, -0.74), (1.25, 3.2, -0.74), 0.08, 0.08, "glow_green", uv=16, tags=("noao",))
    rod(b, (0, -2.75, -0.5), (0, -2.75, -4.6), 0.56, "riser", uv=12)
    band(b, (0, -2.75, -4.2), (0, 0, 1), 1.0, 0.95, "rag", uv=10)
    rag(b, (0, -3.2, -4.3), 1.4, 0.5, "rag", hang=(0.1, -1.0, 0.2), strips=2, spread=0.25, seed=953, uv=10)
    rag(b, (0.55, 5.7, 0.7), 1.7, 0.5, "rag_red", hang=(0.35, -1.0, 0.3), strips=2, spread=0.3, seed=954, uv=10)
    band(b, (0, 5.75, 0.62), (0, 1, 0.2), 1.4, 0.3, "rag_red", round_=False, uv=12)
    book.add("riser", "steel_painted", base=book.pal(0), rust=0.25, wear=0.7)
    book.add("bolt", "steel_worn", base=(120, 120, 118))
    book.add("cord", "paracord", base=book.pal(1))
    book.add("limb", "plastic_black", base=(30, 30, 32), wear=0.6, dirt=0.35)
    book.add("tape", "tape_grey", dirt=0.6)
    book.add("cam", "aluminium", base=book.pal(3))
    book.add("string", "rope", base=(50, 50, 46))
    book.add("serving", "rope", base=(30, 30, 30))
    book.add("shaft", "plastic_black", base=(34, 34, 36))
    book.add("head", "steel_clean", base=(176, 178, 180))
    book.raw("vane", NP.style("plastic", base=(220, 120, 34), wear=0.2))
    book.raw("nock", NP.style("plastic", base=(210, 200, 60), wear=0.1))
    book.add("steel", "steel_worn")
    book.add("alu", "aluminium", base=(110, 112, 116))
    book.raw("glow_green", NP.style("glow", base=(120, 255, 90)))
    book.add("rag", "cloth_rag", base=book.pal(2))
    book.add("rag_red", "cloth_red", base=book.pal(4))
    blood = [WC.blood_zone((-0.8, -2.0, -0.8), (0.8, 1.2, 1.4), 0.12, "dry", soft=0.6),
             WC.blood_zone((-0.8, 9.5, 0.6), (0.8, 13.5, 2.4), 0.18, "dry", soft=0.6)]
    return Built(wm, book, blood, hold=dict(scale=0.74), icon_yaw=88.0, icon_roll=0.0)


# ===========================================================================
#  投げ物（片手。原点 = 握る所、-Z = 先・上。重ねて持つ物は束で見せる）
# ===========================================================================
def flame(b, at, size: float, *, seed: int, styles=("flame_out", "flame_mid", "flame_core")):
    """揺れる炎（芯の黄・橙・外の赤橙を少しずつ回した箱で。全部 glow）。-Z へ立ち上がる。"""
    import random as _random
    rng = _random.Random(WC.stable_hash(("flame", seed)))
    at = np.asarray(at, float)
    out = []
    for i, (k, st) in enumerate(((1.0, styles[0]), (0.68, styles[1]), (0.4, styles[2]))):
        s = size * k
        out.append(cbox(b, at + (0, 0, -s * 0.45), (s * 0.66, s * 0.66, s * 1.5), st,
                        rot=(rng.uniform(-10, 10), rng.uniform(-10, 10), 45.0 * (i % 2) + rng.uniform(-8, 8)),
                        uv=10, tags=("noao", "soft")))
    for j in range(3):
        a = rng.uniform(0, 2 * math.pi)
        tip = at + (math.cos(a) * size * 0.2, math.sin(a) * size * 0.2, -size * (1.2 + 0.25 * j))
        out.append(cbox(b, tip, (size * 0.24, size * 0.24, size * 0.5), styles[0 if j else 1], rot=(0, 0, 45), uv=10,
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


FLICKER = ["1.0 + 0.22 * math.sin(q.anim_time * 2160.0)", "1.0 + 0.18 * math.sin(q.anim_time * 1700.0 + 50.0)",
           "1.0 + 0.2 * math.sin(q.anim_time * 1930.0 + 120.0)"]


def knife(b, x: float, *, seed: int, cord: bool = True):
    """投げナイフ 1 本（局所: 柄の中心 = (x, 0, 0.8)、刃は -Z）。黒染めの両刃（研ぎ出しの縁 2 本・菱形の切っ先）、
    肉抜きの柄（パラコード巻き）、柄尻の輪。"""
    out = [cbox(b, (x, 0, -2.5), (0.26, 1.0, 3.8), "kblade", uv=12)]
    out.append(cbox(b, (x, 0.58, -2.42), (0.13, 0.2, 3.6), "kedge", rot=(0, 0, 180), uv=14, tags=("edge",)))
    out.append(cbox(b, (x, -0.58, -2.42), (0.13, 0.2, 3.6), "kedge", uv=14, tags=("edge",)))
    out.append(cbox(b, (x, 0, -4.45), (0.2, 0.92, 0.92), "kedge", rot=(45, 0, 0), uv=14))
    out.append(cbox(b, (x, 0, -5.0), (0.14, 0.42, 0.42), "kedge", rot=(45, 0, 0), uv=16))
    add_world(out[:1], WC.stamp("NR", (-1.4, 0.0), 0.32, mul=0.6))
    out.append(cbox(b, (x, 0, -0.42), (0.32, 1.06, 0.36), "khandle", uv=14))                # 刃元の段
    out.append(cbox(b, (x, 0, 1.0), (0.3, 0.84, 2.6), "khandle", uv=12))
    if cord:
        out += wrap(b, (x, 0, -0.12), (x, 0, 1.75), (0.5, 1.04), "kcord", pitch=0.36, tilt=10, seed=seed, uv=12)
    # 柄尻の輪（YZ の四角い輪）
    for p0, p1 in (((x, 0.4, 2.2), (x, 0.4, 3.15)), ((x, -0.4, 2.2), (x, -0.4, 3.15)),
                   ((x, -0.5, 3.2), (x, 0.5, 3.2))):
        out.append(beam(b, p0, p1, 0.24, 0.2, "kring", uv=14))
    return out


@builder("throwing_knives")
def b_throwing_knives(w) -> Built:
    """投げナイフの束（3 本を少しずつ扇に開いて持つ）: 黒染めの両刃に銀の研ぎ出し、パラコードの柄、
    柄尻の輪。束ねたゴムの帯。"""
    wm = WC.WeaponModel("throwing_knives", uv=10)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    knife(b, 0.0, seed=1001)
    k2 = wm.bone("knife_b", pivot=(0, 0, 1.0), rotation=(-9.0, 0.0, 0.0))
    knife(k2, -0.34, seed=1002, cord=False)
    k3 = wm.bone("knife_c", pivot=(0, 0, 1.0), rotation=(10.0, 0.0, 0.0))
    knife(k3, 0.34, seed=1003, cord=False)
    lash(b, (0, 0, 2.05), (0, 0, 1), 1.12, 1.2, 0.26, 1, "band", wire=0.14)
    book.add("kblade", "steel_dark", base=book.pal(0), scratches=0.5)
    book.add("kedge", "steel_clean", base=book.pal(1))
    book.add("khandle", "steel_dark", base=book.pal(2), wear=0.9)
    book.add("kcord", "paracord", base=(84, 92, 58))
    book.add("kring", "steel_worn")
    book.add("band", "rubber_black", base=(110, 40, 30))
    blood = [WC.blood_zone((-0.6, -0.9, -5.4), (0.6, 0.9, -3.0), 0.35, "wet", soft=0.6)]
    return Built(wm, book, blood, hold=dict(scale=1.0, grip=0.9, pitch=30.0), icon_yaw=88.0)


def blade_star(b, c, *, seed: int):
    """刃の手裏剣 1 枚（YZ の面、中心 c）: 丸ノコの芯の円板に鋸の歯の名残、四つ角の刃（本体・研いだ縁・切っ先）、
    鋲 4 つ。"""
    c = np.asarray(c, float)
    out = disc(b, c, (1, 0, 0), 0.98, 0.24, "score", n=3, uv=14)
    for k in range(4):
        th = math.radians(45.0 + 90.0 * k)
        d = np.array([0.0, math.sin(th), -math.cos(th)])
        # 軸に沿った正方形の対角線は 45° の向き = 刃の向き（回さずに菱形の角が外を向く）
        out.append(cbox(b, c + d * 1.3, (0.22, 1.28, 1.28), "sbody", uv=14))
        out.append(cbox(b, c + d * 2.0, (0.16, 0.86, 0.86), "sedge", uv=16))
        out.append(cbox(b, c + d * 2.52, (0.12, 0.42, 0.42), "sedge", uv=16))
    out += ring_of(b, c, (1, 0, 0), 1.02, 8, (0.2, 0.3, 0.3), "steeth", phase=0.0, uv=16)
    for k in range(4):
        th = math.radians(90.0 * k)
        out += rivet(b, c + (0.12, 0.55 * math.sin(th), -0.55 * math.cos(th)), (1, 0, 0), d=0.26, h=0.06,
                     style="srivet", uv=16)
    return out


@builder("throwing_stars")
def b_throwing_stars(w) -> Built:
    """刃の手裏剣 2 枚（少し回して重ね、指で挟む）: 丸ノコを四つ角に切った刃、芯の軸穴と鋲、錆びた歯の名残、
    切っ先の血。"""
    wm = WC.WeaponModel("throwing_stars", uv=12)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    c = (0.0, 0.0, -1.85)
    blade_star(b, c, seed=1101)
    s2 = wm.bone("star_b", pivot=c, rotation=(22.0, 0.0, 0.0))
    blade_star(s2, (0.3, 0.0, -1.85), seed=1102)
    wm.cut(c, (1, 0, 0), r=0.28, half=0.6)
    book.add("score", "steel_worn", base=book.pal(0), scratches=0.8, dirt=0.3)
    book.add("sbody", "steel_worn", base=book.pal(0), scratches=0.7)
    book.add("sedge", "steel_clean", base=book.pal(1))
    book.add("steeth", "steel_rusty", amount=0.7, metal=book.pal(2))
    book.add("srivet", "brass", wear=0.8)
    blood = [WC.blood_zone((-0.6, 0.6, -4.6), (0.9, 2.6, -2.6), 0.42, "dry", soft=0.6),
             WC.blood_zone((-0.6, -2.6, -1.0), (0.9, -0.6, 0.8), 0.3, "wet", soft=0.6)]
    return Built(wm, book, blood, hold=dict(scale=1.0, grip=0.0, pitch=24.0), icon_yaw=88.0)


def liquid(z_level: float, rgb, *, edge=(236, 200, 128)):
    """瓶の中身: z が z_level より大きい（下 = +Z の側）面を液の色に（ガラス越し）、液面の線は明るく。"""
    rgbv = np.asarray(rgb, np.float32)
    ev = np.asarray(edge, np.float32)

    def fn(P, N, L, size, col):
        sub = P[:, 2] > z_level
        lum = col.mean(1, keepdims=True) / 255.0
        col = np.where(sub[:, None], rgbv * (0.6 + 0.7 * lum), col)
        line = np.abs(P[:, 2] - z_level) < 0.07
        return np.where(line[:, None], ev * (0.8 + 0.3 * lum), col)
    return fn


@builder("molotov")
def b_molotov(w) -> Built:
    """火炎瓶: 角瓶（alphatest のガラス: 液面より上の空の所は面の真ん中を抜いて縁と照りだけ）、液はガラス越しの
    琥珀、破れたラベル 2 枚、首の帯、口に詰めて垂れた布とそれを留めたテープと針金、垂れた燃料の筋、
    布の先の炎（待機アニメで揺れる）。瓶の首が -Z（上）。"""
    wm = WC.WeaponModel("molotov", uv=11)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    bw, z_bot, z_sh, z_lv = 2.3, 2.25, -1.85, -0.25
    lab_lo, lab_hi = -0.7, 1.35

    def keep(P):
        lab = (P[:, 2] > lab_lo - 0.05) & (P[:, 2] < lab_hi + 0.05) & (np.abs(P[:, 0]) > bw / 2 - 0.05)
        return (P[:, 2] > z_lv) | lab
    body = [cbox(b, (0, 0, (z_bot + z_sh) / 2), (bw, bw, z_bot - z_sh), "glass", uv=11)]
    add_world(body, liquid(z_lv, (176, 96, 26)), glass_windows(rim=0.16, keep=keep, seed=1),
              dots([(s * bw / 2, y_, z_) for s in (-1, 1) for y_ in (-0.7, 0.7) for z_ in (1.8,)], 0.12, (150, 96, 50)))
    cbox(b, (0, 0, z_bot - 0.16), (bw + 0.04, bw + 0.04, 0.32), "glass_dark", uv=11)
    cbox(b, (0, 0, z_lv + 0.02), (bw - 0.12, bw - 0.12, 0.06), "fuel_top", uv=12, tags=("noao",))   # 液面（窓から見える）
    sh = [cbox(b, (0, 0, -2.08), (bw - 0.24, bw - 0.24, 0.5), "glass", uv=12),
          cbox(b, (0, 0, -2.48), (1.5, 1.5, 0.36), "glass", uv=12)]
    add_world(sh, glass_windows(rim=0.16, seed=2))
    rod(b, (0, 0, -2.6), (0, 0, -4.6), 0.92, "glass_dark", uv=12)
    band(b, (0, 0, -4.55), (0, 0, 1), 1.08, 0.24, "glass_dark", uv=14)
    band(b, (0, 0, -3.15), (0, 0, 1), 1.0, 0.4, "label", uv=14)                                # 首の帯
    lab = [cbox(b, (s * (bw / 2 + 0.03), 0, (lab_lo + lab_hi) / 2), (0.06, bw - 0.12, lab_hi - lab_lo), "label",
                uv=12, tags=("ragged",)) for s in (-1, 1)]
    add_world(lab, WC.stamp("RYE", (0.55, 0.32), 0.62, tint=(96, 30, 24)),
              WC.stamp("1987", (-0.2, -0.5), 0.34, tint=(70, 52, 30)), patch((-2, -1.2, 1.0), (2, 1.2, 1.4), rgb=(150, 40, 32)))
    # 口に詰めた布（外へ垂れる）・留めたテープと針金・焦げた先
    rod(b, (0, 0, -3.7), (0, 0.05, -5.35), 0.7, "rag", uv=11)
    rag(b, (0.15, 0.3, -5.1), 2.3, 0.62, "rag", hang=(0.25, 0.35, 1.0), strips=2, spread=0.28, seed=5, uv=11)
    rag(b, (-0.25, -0.15, -5.0), 1.4, 0.5, "rag", hang=(-0.6, -0.2, 1.0), strips=1, seed=6, uv=11)
    wrap(b, (0, 0, -3.4), (0, 0, -4.15), 1.18, "tape", pitch=0.36, tilt=8, seed=7, uv=12)
    coil(b, (0, 0, -4.3), (0, 0, 1), 1.02, 0.3, 2, "wire", wire=0.1, uv=16)
    cbox(b, (0.05, 0.1, -5.5), (0.78, 0.72, 0.46), "rag_burnt", rot=(10, 20, 0), uv=12)
    # 垂れた燃料の筋（瓶の外）
    for x_, y_, z0, z1 in ((bw / 2 + 0.02, 0.35, -1.6, -0.6), (0.4, bw / 2 + 0.02, -1.7, -1.0)):
        cbox(b, (x_, y_, (z0 + z1) / 2), (0.06 if x_ > 1 else 0.18, 0.18 if x_ > 1 else 0.06, z1 - z0), "fuel_wet",
             uv=14, tags=("noao",))
    # 炎（布の先）。待機アニメで揺らす
    fb = wm.bone("flame", pivot=(0.05, 0.1, -5.65))
    flame(fb, (0.05, 0.1, -5.75), 1.0, seed=11)
    wm.idle = {"flame": {"scale": list(FLICKER), "rotation": [0.0, 0.0, "8.0 * math.sin(q.anim_time * 900.0)"]}}
    book.add("glass", "glass_tinted", base=(104, 74, 40))
    book.add("glass_dark", "glass_tinted", base=(70, 44, 20))
    book.raw("fuel_top", NP.style("plastic", base=(214, 150, 60), wear=0.0, dirt=0.0))
    book.raw("fuel_wet", NP.style("plastic", base=(150, 92, 30), wear=0.0, dirt=0.1))
    book.raw("label", NP.style("paper", base=(210, 194, 152), lines=False, dirt=0.55))
    book.add("rag", "cloth_rag", base=book.pal(1))
    book.raw("rag_burnt", NP.style("char", embers=0.6))
    book.add("tape", "tape_grey", base=(150, 146, 136), dirt=0.55)
    book.add("wire", "copper_wire", base=(176, 110, 60))
    flame_styles(book)
    blood = [WC.blood_zone((-1.3, -1.3, 1.0), (1.3, 1.3, 2.4), 0.16, "dry", soft=0.6)]
    return Built(wm, book, blood, hold=dict(scale=0.96, pitch=70.0, yaw=-6.0, grip=0.25), icon_yaw=64.0)


@builder("pipe_bomb")
def b_pipe_bomb(w) -> Built:
    """パイプ爆弾: 亜鉛めっきの管とねじ込みの蓋（八角）、黒テープで巻き付けた釘 10 本（頭を交互に）、赤い危険の
    シール、後ろの蓋の穴から曲がって立つ黄色い導火線と火花（待機アニメで瞬く）。"""
    wm = WC.WeaponModel("pipe_bomb", uv=10)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    pp = rod(b, (0, 0, 2.1), (0, 0, -2.1), 1.62, "pipe", uv=10)
    add_world(pp, WC.pock(1201, cell=0.6, r=0.14, frac=0.35))
    for s in (-1, 1):
        cp = octo(b, (0, 0, s * 2.45), (0, 0, 1), 1.1, 0.82, "cap", uv=11)
        add_world(cp, stripes(s * 2.1, s * 2.8, 0.18, mul=0.7, axis=2))
        if s > 0:
            add_world(cp, holes_on([(0, 0.4, 2.86)], 0.16, normal=(0, 0, 1)))
        band(b, (0, 0, s * 1.98), (0, 0, 1), 1.76, 0.18, "cap", uv=14)
    for k in range(10):
        a = math.radians(18.0 + 36.0 * k)
        x_, y_ = 0.9 * math.cos(a), 0.9 * math.sin(a)
        z0, z1 = (1.65, -1.55) if k % 2 else (-1.65, 1.55)
        nail(b, (x_, y_, z0), (x_, y_, z1), "nail", d=0.16, head=0.36, uv=16)
    wrap(b, (0, 0, -1.5), (0, 0, -0.62), 2.1, "tape", pitch=0.44, tilt=6, seed=1202, uv=10)
    wrap(b, (0, 0, 0.62), (0, 0, 1.5), 2.1, "tape", pitch=0.44, tilt=-6, seed=1203, uv=10,
         tail=(0.65, (0.35, -1.0, 0.25)))
    st = cbox(b, (0, 1.04, 0.0), (1.05, 0.08, 1.1), "sticker", uv=16)
    add_world([st], WC.stamp_on("!", (0, 1.09, 0.0), 0.62, normal=(0, 1, 0), up=(0, 0, -1), tint=(242, 232, 214)))
    fb = wm.bone("fuse", pivot=(0, 0.4, 2.9))
    polyline(fb, [(0, 0.4, 2.8), (0, 0.85, 3.35), (0.08, 1.45, 3.62), (0.15, 2.0, 3.5)], 0.24, 0.24, "fuse",
             overlap=0.1, uv=14, tags=("soft",))
    sp = wm.bone("spark", pivot=(0.17, 2.15, 3.45))
    spark(sp, (0.17, 2.15, 3.45), 0.42)
    wm.idle = {"spark": {"scale": list(FLICKER), "rotation": [0.0, "q.anim_time * 720.0", 0.0]}}
    book.add("pipe", "steel_worn", base=book.pal(0), scratches=0.6, dirt=0.5)
    book.add("cap", "iron_cast", base=(88, 86, 82))
    book.add("nail", "steel_rusty", amount=0.5)
    book.add("tape", "tape_black", base=book.pal(2), dirt=0.45)
    book.add("sticker", "plastic_red", base=book.pal(3))
    book.add("fuse", "rope", base=book.pal(1))
    flame_styles(book)
    return Built(wm, book, [], hold=dict(scale=0.95, pitch=24.0, grip=0.3), icon_yaw=76.0)


@builder("firecracker")
def b_firecracker(w) -> Built:
    """爆竹の束: 赤い紙筒 8 本（2 列 × 4、底は粘土の栓）、金色の帯と赤い菱形の紙、麻ひもの縛り、
    筒ごとの細い導火線が撚り合わさって 1 本に、先の火花（待機アニメで瞬く）。筒の先が -Z（上）。"""
    wm = WC.WeaponModel("firecracker", uv=10)
    b = wm.root
    book = WC.Stylebook(w["palette"])
    tops = []
    for i, x_ in enumerate((-0.81, -0.27, 0.27, 0.81)):
        for j, y_ in enumerate((-0.28, 0.28)):
            zt = -1.45 - (0.12 if (i + j) % 2 else 0.0)
            rod(b, (x_, y_, 1.55), (x_, y_, zt), 0.54, "paper_red" if (i + j) % 3 else "paper_red2", uv=10)
            cbox(b, (x_, y_, 1.6), (0.46, 0.46, 0.1), "clay", uv=14)
            tops.append((x_, y_, zt))
    for z_ in (-0.95, 1.0):
        lash(b, (0, 0, z_), (0, 0, 1), 2.2, 1.12, 0.24, 1, "twine", wire=0.12)
    gb = rbeam(b, (0, 0, -0.25), (0, 0, 0.55), 2.26, 1.2, "gold", k=0.92, uv=11)
    add_world(gb, stripes(-0.25, 0.55, 0.2, mul=0.72, axis=2))
    dm = cbox(b, (0, 0.6, 0.15), (0.9, 0.06, 0.9), "paper_red2", rot=(0, 45, 0), uv=14)          # 赤い菱形の紙
    add_world([dm], dots([(0, 0.68, 0.15)], 0.22, (226, 190, 60)))
    # 細い導火線 → 撚り合わせた 1 本 → 火花
    hub = np.array([0.0, 0.0, -2.05])
    for t in tops:
        beam(b, t, hub, 0.08, 0.08, "fuse", uv=16, tags=("soft",))
    fb = wm.bone("fuse", pivot=tuple(hub))
    polyline(fb, [hub, hub + (0.15, 0.18, -0.5), hub + (-0.08, 0.32, -1.0), hub + (0.1, 0.55, -1.4)], 0.16, 0.16,
             "fuse", overlap=0.08, uv=16, tags=("soft",))
    sp = wm.bone("spark", pivot=tuple(hub + (0.12, 0.62, -1.55)))
    spark(sp, hub + (0.12, 0.62, -1.55), 0.36)
    wm.idle = {"spark": {"scale": list(FLICKER), "rotation": [0.0, 0.0, "q.anim_time * 900.0"]}}
    book.raw("paper_red", NP.style("paper", base=book.pal(0), lines=False, dirt=0.3))
    book.raw("paper_red2", NP.style("paper", base=tuple(int(v * 0.84) for v in book.pal(0)), lines=False, dirt=0.35))
    book.raw("clay", NP.style("paper", base=(176, 156, 120), lines=False, dirt=0.5))
    book.add("twine", "rope", base=(170, 140, 90))
    book.add("gold", "brass", base=book.pal(1), wear=0.3)
    book.add("fuse", "rope", base=(78, 70, 56))
    flame_styles(book)
    return Built(wm, book, [], hold=dict(scale=1.0, pitch=62.0, grip=0.6), icon_yaw=70.0)


@builder("uv_flare")
def b_uv_flare(w) -> Built:
    """UV 発煙筒（手製）: 廃材のアルミ管に UV キノコの練り物（発光）を詰め、横の細い窓から紫に光るのが見える。
    紫の帯 2 本と注意書き、黒い擦り蓋（滑り止めの溝・ランヤードの輪）、先の燃える頭（強い紫と白熱の芯・
    火の粉の冠）、点火の銅線 2 本をテープで留め、横に鉄のクリップ。頭が -Z（上）。"""
    wm = WC.WeaponModel("uv_flare", uv=11)
    b = wm.root
    book = WC.Stylebook(w["palette"])

    def win(P, N, L, size, col):
        # ±X の面の細い窓 2 本（抜く）
        ok = np.abs(N[:, 0]) > 0.7
        cut = ok & (np.abs(P[:, 1]) < 0.2) & (((P[:, 2] > -1.3) & (P[:, 2] < -0.2)) | ((P[:, 2] > 0.35) & (P[:, 2] < 1.15)))
        return col, cut
    tb = rod(b, (0, 0, 2.3), (0, 0, -1.9), 1.12, "tube", uv=11)
    add_world(tb, win, WC.pock(1301, cell=0.5, r=0.1, frac=0.3))
    rod(b, (0, 0, 1.7), (0, 0, -1.8), 0.78, "uv_core", uv=10)                         # 中の練り物（窓から光る）
    for z_ in (1.55, -1.45):
        band(b, (0, 0, z_), (0, 0, 1), 1.22, 0.32, "band", uv=12)
    lb = band(b, (0, 0, 0.12), (0, 0, 1), 1.18, 0.36, "label", uv=14)
    add_world(lb, stripes(-1, 1, 0.16, mul=0.25, axis=0, normal=(0, 1, 0)))
    # 擦り蓋（後ろ）と輪
    cp = rod(b, (0, 0, 2.2), (0, 0, 3.25), 1.3, "cap", uv=11, fx={"ribs": 0.2})
    band(b, (0, 0, 3.3), (0, 0, 1), 0.92, 0.18, "cap", uv=14)
    band(b, (0, 0, 3.62), (1, 0, 0), 0.62, 0.14, "steel", round_=False, uv=16)
    # 燃える頭と白熱の芯、火の粉の冠
    hd = wm.bone("head", pivot=(0, 0, -2.4))
    rod(hd, (0, 0, -1.85), (0, 0, -2.95), 1.02, "uv_glow", uv=11)
    rod(hd, (0, 0, -2.9), (0, 0, -3.3), 0.66, "uv_hot", uv=12)
    ring_of(hd, (0, 0, -2.4), (0, 0, 1), 0.66, 6, (0.2, 0.2, 0.34), "uv_hot", phase=15.0, uv=14,
            tags=("noao", "soft"))
    wm.idle = {"head": {"scale": ["1.0 + 0.06 * math.sin(q.anim_time * 1500.0)"] * 3}}
    # 点火の銅線 2 本とテープ、鉄のクリップ
    for s in (-1, 1):
        polyline(b, [(s * 0.3, 0.6, 2.25), (s * 0.34, 0.62, 0.6), (s * 0.3, 0.6, -1.6), (s * 0.18, 0.4, -2.0)], 0.1,
                 0.1, "wire", overlap=0.06, uv=16)
    wrap(b, (0, 0, 2.0), (0, 0, 1.75), 1.3, "tape", pitch=0.26, tilt=6, seed=1302, uv=14,
         tail=(0.45, (0.2, -1.0, 0.3)))
    beam(b, (0.62, 0.0, 1.8), (0.62, 0.0, -0.4), 0.1, 0.42, "steel", up=(0, 1, 0), uv=14)
    cbox(b, (0.6, 0.0, 1.95), (0.2, 0.42, 0.3), "steel", uv=16)
    book.add("tube", "aluminium", base=(186, 188, 192), dirt=0.45)
    book.raw("uv_core", NP.style("glow", base=(170, 90, 255)))
    book.raw("uv_glow", NP.style("glow", base=(150, 70, 255)))
    book.raw("uv_hot", NP.style("glow", base=book.pal(1)))
    book.add("band", "plastic_blue", base=book.pal(0))
    book.raw("label", NP.style("paper", base=(226, 214, 120), lines=False, dirt=0.4))
    book.add("cap", "plastic_black", base=book.pal(2))
    book.add("steel", "steel_worn")
    book.add("wire", "copper_wire", base=(184, 112, 64))
    book.add("tape", "tape_grey", dirt=0.5)
    return Built(wm, book, [], hold=dict(scale=1.0, pitch=56.0, grip=0.4), icon_yaw=70.0)


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
