# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 武器の共通基盤（近接 gen_nr_weapons.py・飛び道具 gen_nr_weapons_ranged.py が使う）。

約束事は DESIGN.md（§2 ID、§8 武器、§11 上限、§13 描画）と reference/rendering.md（§7 アタッチャブル、
§11 W1〜W4・M1〜M7）、reference/content.md（§3 アイテム、§5.1 レシピ）。ここはそれを 1 か所で守るための道具箱。

■ 座標（武器空間。nr_spec_catalog の docstring と同じ）
  原点 = 利き手の拳の中心（握り）、**-Z = 刃先・銃口**、+Y = 上（峰）、刃は -Y、+X/-X = 刃の平。
  16 単位 = 1 ブロック、人の身長 ≒ 32 単位。回転は統合版の規則 R = Rz(-rz)·Ry(ry)·Rx(-rx)
  （tools/hyperdim/hd_space.rot と同じ。nr_preview もこれで描く）。
  ※ tools/hyperdim/hd_common.beam は tools/preview.py の古い回転の向きで角度を出すので、NR では使わない
    （同じ名前の beam / polyline / fill_tri_yz をここに hd_space の規則で作り直してある）。

■ 使い方（飛び道具の生成器もこの順で呼ぶ）::

    import nr_weapon_common as WC
    wm = WC.WeaponModel("crossbow", uv=5)            # ボーン hold(binding) → root（握り = 原点）
    b = wm.root                                       # 部品は root の子（wm.bone("limb_l") で子ボーンも）
    WC.beam(b, (0, 0, 2), (0, 0, -12), 1.2, 1.4, "stock", tags=("ao",))
    WC.rod(b, p0, p1, d, "pipe")                      # 八角の丸棒（2 個）
    WC.blade(b, [(z, y_spine, y_edge), ...], "blade", "edge", "spine")   # 刃（峰・本体・研いだ縁）
    book = WC.Stylebook(palette).add("stock", "wood_dark").add("blade", "steel_worn") ...
    tex = WC.texture(wm, book, seed, blood=[WC.blood_zone(lo, hi, 0.8, "wet")])   # 塗り＋後処理
    hold = WC.hold_one_hand(wm, fwd=..., up=...) / WC.hold_two_hand(wm, style="two_hand") / 独自
    out = WC.write_weapon(w, wm, tex, hold, frags)    # geo / テクスチャ / アタッチャブル / アニメ / アイテム / レシピ / アイコン
    frags.write()                                     # item_texture・lang の断片（.frag/<種類>/<producer>.json）

■ 公開 API（関数ごとの docstring も参照）
  形:   box, cbox, oriented, beam, polyline, rod, band, hex_prism, disc, ring_of, fill_tri_yz, blade,
        curved_blade, arc_points, lerp, frame, euler_of
  モデル: WeaponModel（.root / .hold / .bone() / .pack() / .cube_count / .length_z() / .bounds()）
  塗り: Stylebook（spec の SURFACES のキー → nr_paint のスタイル）、surface_style(),
        texture(wm, book, seed, blood=..., ao=True, edges=True) → PIL RGBA、TexMap（texel → 武器空間）、
        blood_zone(lo, hi, amount, kind)、blood_zones_from_spec(w)
  持ち方: HOLD_STYLES（anim_set → 持ち方の型）、HOLD_ARMS（型 → 三人称の腕の絶対角。gen_nr_player_anim との契約）、
        hold_one_hand(), hold_two_hand(), hold_spear(), fp_place_cam(), hold_for(w, wm)、clip_report()
  書き出し: write_weapon(w, wm, tex, hold, frags, ...)、attachable_doc(), hold_animation_doc(), item_doc(),
        recipe_doc(), bake_icon(), Frags（item_texture / lang の断片）
  確認: render_model(), render_held(), render_fp(), contact_sheet()（nr_preview の薄い包み）

■ ファイルの置き場所（武器 1 つ = 下のファイル群。ID は DESIGN §2）
  RP  models/entity/weapons/<key>.geo.json      geometry.nr.w.<key>（1.16.0、≤180 キューブ）
  RP  textures/nr/weapons/<key>.png             モデルのテクスチャ（≤256×512、パレット化、発光 α=16）
  RP  textures/nr/items/<key>.png               アイコン（64×64。item_texture のキー nr_w_<key>）
  RP  attachables/weapons/<key>.attachable.json identifier = nr:w_<key>
  RP  animations/weapons/<key>.animation.json   animation.nr.w.<key>.tp / .fp / .tp_use / .fp_use / .idle
  BP  items/weapons/<key>.item.json             nr:w_<key>（1.21.120）
  BP  recipes/weapons/<key>.recipe.json         nr:craft_w_<key>（spec に作業台レシピがあるときだけ）

■ gen_nr_player_anim との契約（HOLD_ARMS）
  三人称で武器を持っている間、プレイヤーの腕は HOLD_ARMS[型] の**絶対角**（バニラの「持つと右腕 -18°」込み）
  になっている前提でアタッチャブルの位置を逆算している。片手（one_hand）はバニラのままの (-18, 0, 0) なので
  持ちモーションが無くても正しく見える。両手（two_hand）・槍（spear）は gen_nr_player_anim の
  hold_2h / hold_spear が腕をこの角度にする（HyperDim の HOLD_CANCEL と同じく、バニラの -18° と歩きの腕振りを
  打ち消してから足す）。左手は柄の二つ目の握り（hold["grip2"]、武器空間）にちょうど届く。
"""
from __future__ import annotations

import json
import math
import os
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
HD = os.path.join(TOOLS, "hyperdim")
for _p in (TOOLS, HERE, HD):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import nr_common as NC  # noqa: E402
from nr_common import (BP, RP, SCRATCH, frag, stable_hash, write_geometry, write_json)  # noqa: E402
from mcmodel import Bone, Cube, Model  # noqa: E402
import hd_space as HS  # noqa: E402  回転・bind のずれ・一人称の腕（HyperDim と共通の規則。コピーしない）
import hd_holds as HH  # noqa: E402  持ち方の逆算（frame / item_rotation / item_position / solve_arm_to / fp_place）
import nr_paint as NP  # noqa: E402
import nr_preview as NV  # noqa: E402

# ===========================================================================
#  定数・置き場所
# ===========================================================================
GEO_DIR = os.path.join(RP, "models", "entity", "weapons")
TEX_REL = "textures/nr/weapons"          # モデルのテクスチャ（拡張子なし）
ICON_REL = "textures/nr/items"           # アイコン
ATT_DIR = os.path.join(RP, "attachables", "weapons")
ANIM_DIR = os.path.join(RP, "animations", "weapons")
ITEM_DIR = os.path.join(BP, "items", "weapons")
RECIPE_DIR = os.path.join(BP, "recipes", "weapons")
PREVIEW_DIR = os.path.join(SCRATCH, "weapons")

MAX_CUBES = 180                          # DESIGN §11
MAX_TEX = (256, 512)                     # rendering.md §6.5 / M6（武器は 256×512 まで）
ICON_SIZE = 64                           # アイテムのアトラス（≤256²）。64 なら GUI 倍率 4 でも潰れない
ITEM_FORMAT = "1.21.120"
RECIPE_FORMAT = "1.20.10"
ATT_FORMAT = "1.10.0"
ANIM_FORMAT = "1.8.0"
BINDING = "q.item_slot_to_bone_name(c.item_slot)"
ENCHANT_GLINT = "textures/misc/enchanted_item_glint"

# パック 1 の中で 2 の冪に近い寸法を順に試す（mcmodel の ATLAS_SIZES には 256×512 が無いので自前で）
PACK_SIZES = [(64, 64), (128, 64), (128, 128), (256, 128), (256, 256), (256, 512)]


def lerp(a, b, t):
    return a + (b - a) * t


def _v3(v) -> np.ndarray:
    return np.asarray(v, float).reshape(3)


def _r(v, n=3):
    return [round(float(x), n) for x in v]


# ===========================================================================
#  形の補助（統合版の回転の規則で）
# ===========================================================================
def frame(fwd, up=(0.0, 1.0, 0.0)) -> np.ndarray:
    """局所 -Z を fwd、局所 +Y をなるべく up に向ける回転行列（列 = 局所 X, Y, Z の向き）。
    fwd と up が平行に近いときは up を自動で選び直す。"""
    f = _v3(fwd)
    f = f / (np.linalg.norm(f) or 1.0)
    u = _v3(up)
    if np.linalg.norm(np.cross(f, u)) < 1e-4 * (np.linalg.norm(u) or 1):
        u = np.array([1.0, 0.0, 0.0]) if abs(f[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    return HH.frame(f, u)


def euler_of(R) -> Tuple[float, float, float]:
    """回転行列 → 統合版の rotation [rx, ry, rz]（hd_space.euler）。"""
    return HS.euler(np.asarray(R, float))


def _tag(c: Cube, tags, style_uv=None) -> Cube:
    c.tags = frozenset(tags or ())
    return c


def oriented(bone: Bone, centre, size, R, style: str, *, inflate=0.0, uv=None, tags=(), decals=None,
             fx=None) -> Cube:
    """中心 centre・大きさ size の箱を、回転行列 R（局所軸の向き）で置く。uv は texel 密度（単位あたり）。
    tags: 後処理の印（"edge" 研いだ縁 / "ragged" ほつれた布 / "noao" 陰を落とさない / "soft" 当たり判定から外す）。
    fx: 模様と切り抜き（_FX の説明: ribs / wrap / knurl / rebar / holes / hazard / sdf）。"""
    centre = _v3(centre)
    size = _v3(size)
    rot = euler_of(R) if R is not None else (0.0, 0.0, 0.0)
    rot = [round(float(x), 2) for x in rot]
    rotated = any(abs(x) > 1e-3 for x in rot)
    c = Cube(centre - size / 2, size, style, inflate=inflate,
             pivot=_r(centre) if rotated else None, rotation=rot if rotated else None,
             uv_scale=uv, decals=decals)
    _tag(c, tags)
    c.fx = dict(fx or {})
    bone.add(c)
    return c


def cbox(bone: Bone, centre, size, style: str, rot=None, **kw) -> Cube:
    """中心と大きさで置く箱。rot は統合版の [rx, ry, rz]（中心まわり）。"""
    R = HS.rot(*rot) if rot is not None and any(abs(float(x)) > 1e-6 for x in rot) else None
    return oriented(bone, centre, size, R, style, **kw)


def box(bone: Bone, origin, size, style: str, **kw) -> Cube:
    o = _v3(origin)
    s = _v3(size)
    return cbox(bone, o + s / 2, s, style, **kw)


def beam(bone: Bone, p0, p1, w: float, h: float, style: str, *, up=(0.0, 1.0, 0.0), roll: float = 0.0,
         extend: float = 0.0, **kw) -> Cube:
    """p0 → p1 へ伸びる角柱。局所 X 幅 w・局所 Y 高さ h、局所 +Y は up の向き（roll で軸まわりに回す）。
    extend は両端を合わせて伸ばす長さ（折れ線の継ぎ目の隙間を隠す）。"""
    p0, p1 = _v3(p0), _v3(p1)
    d = p1 - p0
    L = float(np.linalg.norm(d))
    if L < 1e-6:
        raise ValueError("長さ 0 の beam")
    R = frame(d / L, up)
    if roll:
        a = math.radians(roll)
        c, s = math.cos(a), math.sin(a)
        R = R @ np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    if np.allclose(R, np.eye(3), atol=1e-7):
        R = None
    return oriented(bone, (p0 + p1) / 2, (w, h, L + extend), R, style, **kw)


def polyline(bone: Bone, pts, widths, heights, style: str, *, up=(0.0, 1.0, 0.0), overlap=0.2, **kw):
    """点列に沿って角柱を繋ぐ。widths / heights は数か区間ごとの列（先細り）。"""
    out = []
    for i in range(len(pts) - 1):
        w = widths[i] if isinstance(widths, (list, tuple)) else widths
        h = heights[i] if isinstance(heights, (list, tuple)) else heights
        out.append(beam(bone, pts[i], pts[i + 1], w, h, style, up=up, extend=overlap, **kw))
    return out


def rod(bone: Bone, p0, p1, d: float, style: str, *, star=0.84, roll=0.0, **kw) -> List[Cube]:
    """八角に見える丸棒（同じ軸の角柱 2 本を 45° ずらす）。d は差し渡し、star は 45° 側の比。"""
    return [beam(bone, p0, p1, d, d, style, roll=roll, **kw),
            beam(bone, p0, p1, d * star, d * star, style, roll=roll + 45.0, **kw)]


def band(bone: Bone, centre, axis, d: float, length: float, style: str, *, round_=True, tilt=0.0, **kw):
    """丸棒・角棒に巻いた帯（テープ・針金・金輪）。axis 方向に length、差し渡し d。
    tilt は巻きの傾き（度。螺旋巻きに見せる）。round_ なら 45° の 2 枚目も足す。"""
    c = _v3(centre)
    a = _v3(axis)
    a = a / np.linalg.norm(a)
    p0, p1 = c - a * length / 2, c + a * length / 2
    up = np.array([0.0, 1.0, 0.0]) if abs(a[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    if tilt:
        # 帯の面を軸から少し傾ける（局所 X まわり）。小さい角なので up に足すだけで足りる
        up = up + a * math.tan(math.radians(tilt))
    out = [beam(bone, p0, p1, d, d, style, up=up, **kw)]
    if round_:
        out.append(beam(bone, p0, p1, d * 0.86, d * 0.86, style, up=up, roll=45.0, **kw))
    return out


def hex_prism(bone: Bone, centre, axis, across: float, thick: float, style: str, **kw) -> List[Cube]:
    """六角（ナット・ボルトの頭）。対辺 across、厚み thick。60° ずつ回した 3 枚の箱の和は正六角柱になる。"""
    a = _v3(axis)
    a = a / np.linalg.norm(a)
    R0 = frame(a, (0, 1, 0) if abs(a[1]) < 0.9 else (1, 0, 0))
    side = across / math.sqrt(3.0)                      # 一辺 = 外接円の半径
    out = []
    for k in range(3):
        t = math.radians(60.0 * k)
        Rr = R0 @ np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1.0]])
        out.append(oriented(bone, centre, (across, side, thick), Rr, style, **kw))
    return out


def disc(bone: Bone, centre, axis, radius: float, thick: float, style: str, n: int = 3, star: float = 1.0,
         **kw) -> List[Cube]:
    """円板（軸 axis のまわりに 90/n 度ずつ回した正方形 n 枚）。丸ノコ・歯車・ピストンの断面。
    star < 1 なら 2 枚目以降を縮めて角の尖り（星形）を抑える（小さな鋲の頭は 0.84 で八角に近く）。"""
    a = _v3(axis)
    a = a / np.linalg.norm(a)
    R0 = frame(a, (0, 1, 0) if abs(a[1]) < 0.9 else (1, 0, 0))
    side = 2 * radius * math.cos(math.pi / (4 * n))    # 外接する多角形の角が半径に来るように
    out = []
    for k in range(n):
        t = math.radians(90.0 / n * k)
        Rr = R0 @ np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1.0]])
        sd = side * (star if k else 1.0)
        out.append(oriented(bone, centre, (sd, sd, thick), Rr, style, **kw))
    return out


def octo(bone: Bone, centre, axis, radius: float, thick: float, style: str, *, phase: float = 22.5,
         **kw) -> List[Cube]:
    """辺がまっすぐな正八角柱（ピストン・大ハンマーの頭・太いパイプ）。外接円の半径 radius、軸 axis に厚み thick。
    十字と斜め十字の細長い箱 4 本の和はちょうど正八角形になる（disc() の星形・rod() の角の出っ張りが無い）。
    phase は八角形の向き（22.5 で平らな辺が局所 ±X・±Y を向く）。"""
    a = _v3(axis)
    a = a / np.linalg.norm(a)
    R0 = frame(a, (0, 1, 0) if abs(a[1]) < 0.9 else (1, 0, 0))
    long_ = 2 * radius * math.cos(math.radians(22.5))
    short = 2 * radius * math.sin(math.radians(22.5))
    out = []
    for k in range(4):
        t = math.radians(phase - 22.5 + 45.0 * k)
        Rr = R0 @ np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1.0]])
        out.append(oriented(bone, centre, (long_, short, thick), Rr, style, **kw))
    return out


def ring_of(bone: Bone, centre, axis, radius: float, n: int, size, style: str, *, phase=0.0, skip=(), **kw):
    """軸 axis まわりの円周に n 個の箱（歯・鋲・爪）。箱の局所 +Y が外向き、局所 Z が軸。"""
    a = _v3(axis)
    a = a / np.linalg.norm(a)
    R0 = frame(a, (0, 1, 0) if abs(a[1]) < 0.9 else (1, 0, 0))
    out = []
    for k in range(n):
        if k in skip:
            continue
        t = math.radians(phase + 360.0 / n * k)
        Rr = R0 @ np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1.0]])
        radial = Rr[:, 1]
        out.append(oriented(bone, _v3(centre) + radial * radius, size, Rr, style, **kw))
    return out


def arc_points(centre, radius, a0, a1, n, plane="yz"):
    """平面内の円弧（度）。plane='yz': (x, y + r sin, z - r cos)。"""
    pts = []
    for i in range(n + 1):
        t = math.radians(lerp(a0, a1, i / n))
        cx, cy, cz = centre
        if plane == "yz":
            pts.append((cx, cy + radius * math.sin(t), cz - radius * math.cos(t)))
        elif plane == "xy":
            pts.append((cx + radius * math.cos(t), cy + radius * math.sin(t), cz))
        else:
            pts.append((cx + radius * math.sin(t), cy, cz - radius * math.cos(t)))
    return pts


def fill_tri_yz(bone: Bone, apex, base_a, base_b, x_w, layer_h, style, **kw):
    """YZ 平面の三角形を、辺 apex-base_a に平行な角柱の重ねで埋める（切っ先・斧の扇）。"""
    ay, az = apex[1], apex[2]
    py, pz = base_a[1], base_a[2]
    qy, qz = base_b[1], base_b[2]
    ey, ez = py - ay, pz - az
    el = math.hypot(ey, ez)
    ny, nz = -ez / el, ey / el
    if (qy - ay) * ny + (qz - az) * nz < 0:
        ny, nz = -ny, -nz
    height = abs((qy - ay) * ny + (qz - az) * nz)
    out = []
    d = layer_h / 2
    while d < height - 1e-3:
        oy, oz = ay + ny * d, az + nz * d
        ts = []
        for (sy, sz), (fy, fz) in (((ay, az), (qy, qz)), ((qy, qz), (py, pz)), ((py, pz), (ay, az))):
            dy, dz = fy - sy, fz - sz
            det = ey * (-dz) - ez * (-dy)
            if abs(det) < 1e-9:
                continue
            ry, rz = sy - oy, sz - oz
            t = (ry * (-dz) - rz * (-dy)) / det
            u = (ey * rz - ez * ry) / det
            if -1e-6 <= u <= 1 + 1e-6:
                ts.append(t)
        if len(ts) >= 2:
            t0, t1 = min(ts), max(ts)
            if (t1 - t0) * el > 0.3:
                p0 = (apex[0], oy + ey * t0, oz + ez * t0)
                p1 = (apex[0], oy + ey * t1, oz + ez * t1)
                out.append(beam(bone, p0, p1, x_w, layer_h * 1.08, style, up=(0, ny, nz), **kw))
        d += layer_h
    return out


def _yz_normal(a, b, toward):
    """YZ 平面の線分 a→b の法線のうち toward 側を向くもの（(ny, nz)）。"""
    dy, dz = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dy, dz) or 1.0
    n = (-dz / L, dy / L)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if (toward[0] - mid[0]) * n[0] + (toward[1] - mid[1]) * n[1] < 0:
        n = (-n[0], -n[1])
    return n


def _band_beam(bone, x, a_lo, a_hi, b_lo, b_hi, za, zb, t, style, *, align="mid", ov=0.04, extend=0.1,
               uv=None, tags=(), flip=False, bt=None):
    """YZ 平面の四角形（za で [a_lo, a_hi]、zb で [b_lo, b_hi]）を 1 本の角柱で覆う。
    align="lo" なら下の線に、"hi" なら上の線に、"mid" なら中心線に沿わせる。高さは広い方 + ov。"""
    ga, gb = a_hi - a_lo, b_hi - b_lo
    h = max(ga, gb) + ov
    if align == "lo":
        ya, yb = a_lo, b_lo
        sgn = 1.0
    elif align == "hi":
        ya, yb = a_hi, b_hi
        sgn = -1.0
    else:
        ya, yb = (a_lo + a_hi) / 2, (b_lo + b_hi) / 2
        sgn = 0.0
    dy, dz = yb - ya, zb - za
    L = math.hypot(dy, dz) or 1e-6
    n = (dz / L, -dy / L)                 # 線に直角（YZ）。+Y 寄りを向ける
    if n[0] < 0:
        n = (-n[0], -n[1])
    off = sgn * h / 2
    p0 = (x, ya + n[0] * off, za + n[1] * off)
    p1 = (x, yb + n[0] * off, zb + n[1] * off)
    up = (0, -n[0], -n[1]) if flip else (0, n[0], n[1])
    c = beam(bone, p0, p1, t, h, style, up=up, extend=extend, uv=uv, tags=tags)
    if bt is not None:
        c.bt = (bt[1], bt[0]) if flip else tuple(bt)
    return c


def blade(bone: Bone, prof, body: str, edge: str, spine: Optional[str] = None, *, x=0.0, t_body=0.34,
          t_edge=0.16, t_spine=0.44, bevel=0.5, spine_h=0.3, strips=None, uv=None, edge_uv=None,
          body_tags=("blade",), edge_tags=("edge",), spine_tags=("spine",), extend=0.1,
          double=False, grind=0.7) -> Dict[str, List[Cube]]:
    """片刃（double=True で両刃）の刃を、輪郭から作る。

    prof = [(z, y_spine, y_edge), ...]（根元 → 切っ先。z は単調）。y_edge < y_spine なら刃が -Y 側。
    刃の高さ方向を「刃の線に沿った細長い帯」で重ねる（キューブの継ぎ目が刃の長さ方向に走るので、
    研ぎの段（グラインドライン）に見え、縦の継ぎ目が出ない）:
      * 研いだ縁（edge）: 刃の線に沿った細い角柱（厚み t_edge、幅 bevel）。tags に "edge" → 後処理で
        いちばん外の 1 texel を磨いた銀にする
      * 本体（body）: strips 本の帯。刃側ほど薄く峰側ほど厚い（t_edge → t_body → t_spine を grind で補間）。
        厚い帯が薄い帯の重なりを隠すので、平の面に段の付いた「ベタ研ぎ」の刃になる
      * 峰（spine）: 峰の線に沿った角柱（厚み t_spine）。double なら峰の代わりにもう一本の研いだ縁
    輪郭の点の間隔は、峰と刃の線がほぼ平行になる程度に（先へ細る所は点を増やす）。"""
    out = {"edge": [], "spine": [], "body": []}
    if spine is None:
        spine = body
    up_is_spine = prof[0][1] >= prof[0][2]

    for i in range(len(prof) - 1):
        za, zb = prof[i][0], prof[i + 1][0]
        sa, sb, ea, eb = prof[i][1], prof[i + 1][1], prof[i][2], prof[i + 1][2]
        lo_a, hi_a = (ea, sa) if up_is_spine else (sa, ea)
        lo_b, hi_b = (eb, sb) if up_is_spine else (sb, eb)
        hgt = min(hi_a - lo_a, hi_b - lo_b)
        if hgt < 0.02:
            continue
        H = max(1e-3, (hi_a - lo_a + hi_b - lo_b) / 2)
        bev = min(bevel, max(0.1, hgt * (0.45 if double else 0.55)))
        sh = 0.0 if double else min(spine_h, max(0.08, hgt * 0.3))
        top_bev = bev if double else sh
        # 研いだ縁（刃の線に沿う。局所 -Y が刃の線 = _edge_shine の約束。刃が +Y 側なら上下を返す）
        el, eh = (lo_a, lo_a + bev), (lo_b, lo_b + bev)
        if not up_is_spine:
            el, eh = (hi_a - bev, hi_a), (hi_b - bev, hi_b)
        out["edge"].append(_band_beam(bone, x, el[0], el[1], eh[0], eh[1], za, zb, t_edge, edge,
                                      align="lo" if up_is_spine else "hi", ov=0.05, extend=extend,
                                      uv=edge_uv, tags=edge_tags, flip=not up_is_spine,
                                      bt=(0.0, bev / H) if up_is_spine else (1.0 - bev / H, 1.0)))
        # 峰（上の線に沿う）。両刃なら峰の代わりに 2 本目の研いだ縁（局所 -Y を峰の線へ向ける）
        if double:
            sl, sh_ = (hi_a - top_bev, hi_a), (hi_b - top_bev, hi_b)
            if not up_is_spine:
                sl, sh_ = (lo_a, lo_a + top_bev), (lo_b, lo_b + top_bev)
            out["spine"].append(_band_beam(bone, x, sl[0], sl[1], sh_[0], sh_[1], za, zb, t_edge, edge,
                                           align="hi" if up_is_spine else "lo", ov=0.05, extend=extend,
                                           uv=edge_uv, tags=edge_tags, flip=up_is_spine,
                                           bt=(1.0 - top_bev / H, 1.0) if up_is_spine else (0.0, top_bev / H)))
        elif sh > 0:
            sl, sh_ = (hi_a - sh, hi_a), (hi_b - sh, hi_b)
            if not up_is_spine:
                sl, sh_ = (lo_a, lo_a + sh), (lo_b, lo_b + sh)
            out["spine"].append(_band_beam(bone, x, sl[0], sl[1], sh_[0], sh_[1], za, zb, t_spine, spine,
                                           align="hi" if up_is_spine else "lo", ov=0.03, extend=extend,
                                           uv=uv, tags=spine_tags,
                                           bt=(1.0 - sh / H, 1.0) if up_is_spine else (0.0, sh / H)))
        # 本体の帯（刃側 → 峰側。厚みは段々に増える）
        a0, a1 = (lo_a + bev, hi_a - top_bev) if up_is_spine else (lo_a + top_bev, hi_a - bev)
        b0, b1 = (lo_b + bev, hi_b - top_bev) if up_is_spine else (lo_b + top_bev, hi_b - bev)
        gmax = max(a1 - a0, b1 - b0)
        if gmax < 0.05:
            continue
        K = strips or int(np.clip(round(gmax / 0.75), 1, 4))
        for k in range(K):
            f0, f1 = k / K, (k + 1) / K
            if not up_is_spine:
                f0, f1 = 1 - f1, 1 - f0
            al, ah = lerp(a0, a1, f0), lerp(a0, a1, f1)
            bl, bh = lerp(b0, b1, f0), lerp(b0, b1, f1)
            if max(ah - al, bh - bl) < 0.04:
                continue
            tk = (k + 0.5) / K
            tt = lerp(t_edge + (t_body - t_edge) * grind, t_body, tk) if K > 1 else t_body
            # bt: 局所の下 → 上の t（0 = 刃の線、1 = 峰の線）
            y_lo = ((al + bl) / 2 - (lo_a + lo_b) / 2) / H
            y_hi = ((ah + bh) / 2 - (lo_a + lo_b) / 2) / H
            btv = (y_lo, y_hi) if up_is_spine else (1.0 - y_lo, 1.0 - y_hi)
            out["body"].append(_band_beam(bone, x, al, ah, bl, bh, za, zb, tt, body, align="mid", ov=0.06,
                                          extend=extend, uv=uv, tags=body_tags, bt=btv))
    return out


def curved_blade(bone: Bone, pts, widths, body: str, edge: str, *, edge_side=-1, x=0.0, t_body=0.32,
                 t_edge=0.18, bevel=0.45, uv=None, edge_uv=None, overlap=0.25,
                 body_tags=("blade",), edge_tags=("edge",)) -> Dict[str, List[Cube]]:
    """曲がった刃（鎌・大鎌）。pts は刃の中心線（YZ 平面、x 一定）、widths は点ごとの幅。
    edge_side は中心線の左右どちらが刃か（進む向きに対して +1 = 左（法線 (−dz, dy) 側）, -1 = 右）。"""
    out = {"edge": [], "body": []}
    for i in range(len(pts) - 1):
        a, b = _v3(pts[i]), _v3(pts[i + 1])
        dy, dz = b[1] - a[1], b[2] - a[2]
        L = math.hypot(dy, dz) or 1.0
        nrm = np.array([0.0, -dz / L, dy / L]) * edge_side        # 刃の側
        wa = widths[i] if isinstance(widths, (list, tuple)) else widths
        wb = widths[i + 1] if isinstance(widths, (list, tuple)) else widths
        w = (wa + wb) / 2
        bev = min(bevel, w * 0.45)
        # 本体（刃の側を bevel だけ空ける）
        off_b = -nrm * (bev / 2)
        c = beam(bone, a + off_b, b + off_b, t_body, max(0.1, w - bev), body, up=-nrm,
                 extend=overlap, uv=uv, tags=body_tags)
        c.bt = (bev / w, 1.0)
        out["body"].append(c)
        off_e = nrm * (w / 2 - bev / 2 - 0.06)
        c = beam(bone, a + off_e, b + off_e, t_edge, bev + 0.12, edge, up=-nrm,
                 extend=overlap, uv=edge_uv, tags=edge_tags)
        c.bt = (0.0, (bev + 0.12) / w)
        out["edge"].append(c)
    return out


def fill_poly_yz(bone: Bone, poly, style: str, *, x=0.0, thick=0.4, strip=0.5, along="z", ov=0.06,
                 min_len=0.12, uv=None, tags=(), fx=None, bt=None) -> List[Cube]:
    """YZ 平面の多角形 poly=[(y, z), ...] を、along 方向の細長い板（角柱）の重ねで埋める（走査線塗り）。
    along="z" なら Z に沿う板を Y 方向に strip ずつ、"y" なら Y に沿う板を Z 方向に並べる。
    thick は数か関数 f(y, z) → X 方向の厚み（斧の刃のように縁へ向かって薄くする）。
    斧頭の扇・標識の板・包丁の平など、輪郭のある平たい部品に使う。"""
    ys = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    out = []
    n = len(poly)
    if along == "z":
        lo, hi = min(ys), max(ys)
        k = max(1, int(math.ceil((hi - lo) / strip - 1e-6)))
        hstep = (hi - lo) / k
        for i in range(k):
            yc = lo + (i + 0.5) * hstep
            xs = []
            for j in range(n):
                (y0, z0), (y1, z1) = poly[j], poly[(j + 1) % n]
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    xs.append(z0 + (yc - y0) * (z1 - z0) / (y1 - y0))
            xs.sort()
            for a, b in zip(xs[0::2], xs[1::2]):
                if b - a < min_len:
                    continue
                t = thick((yc, (a + b) / 2)) if callable(thick) else thick
                c = oriented(bone, (x, yc, (a + b) / 2), (t, hstep + ov, b - a), None, style, uv=uv, tags=tags,
                             fx=fx)
                if bt is not None:     # bt=(y の刃の線, y の峰) → 写り込みの階調（_steel_look）
                    ye, ys_ = bt
                    c.bt = ((yc - (hstep + ov) / 2 - ye) / (ys_ - ye), (yc + (hstep + ov) / 2 - ye) / (ys_ - ye))
                out.append(c)
    else:
        lo, hi = min(zs), max(zs)
        k = max(1, int(math.ceil((hi - lo) / strip - 1e-6)))
        hstep = (hi - lo) / k
        for i in range(k):
            zc = lo + (i + 0.5) * hstep
            xs = []
            for j in range(n):
                (y0, z0), (y1, z1) = poly[j], poly[(j + 1) % n]
                if (z0 <= zc < z1) or (z1 <= zc < z0):
                    xs.append(y0 + (zc - z0) * (y1 - y0) / (z1 - z0))
            xs.sort()
            for a, b in zip(xs[0::2], xs[1::2]):
                if b - a < min_len:
                    continue
                t = thick(((a + b) / 2, zc)) if callable(thick) else thick
                out.append(oriented(bone, (x, (a + b) / 2, zc), (t, b - a, hstep + ov), None, style,
                                    uv=uv, tags=tags, fx=fx))
    return out


# ---------------------------------------------------------------------------
#  よく使う部品（テープ巻き・鋲・釘・ボルト・溶接・布切れ・針金）。飛び道具の生成器も使う
# ---------------------------------------------------------------------------
def _axis_frame(axis):
    a = _v3(axis)
    a = a / np.linalg.norm(a)
    return a, frame(a, (0, 1, 0) if abs(a[1]) < 0.9 else (1, 0, 0))


def wrap(bone: Bone, p0, p1, d: float, style: str, *, pitch=0.85, gap=0.0, grow=0.05, tilt=7.0, seed=0,
         round_=True, uv=None, period=None, tail=None, tags=()) -> List[Cube]:
    """p0 → p1 の柄に巻いたテープ・布・革紐。幅 pitch の帯を少しずつ傾けて重ねる（巻きの段差が出る）。
    d は巻いた後の差し渡し（下の柄より grow*2 ほど太く）。tail=(長さ, 向き) で巻き終わりの垂れた端。
    帯には fx wrap（斜めの巻き筋）を付ける。period は巻き筋の周期（既定 pitch*0.55）。"""
    import random as _random
    rng = _random.Random(stable_hash(("wrap", seed, tuple(np.round(_v3(p0), 2)))))
    p0, p1 = _v3(p0), _v3(p1)
    L = float(np.linalg.norm(p1 - p0))
    a = (p1 - p0) / L
    n = max(1, int(round(L / pitch)))
    seg = L / n
    out = []
    fx = {"wrap": period or pitch * 0.55}
    dw, dh = (float(d[0]), float(d[1])) if isinstance(d, (tuple, list)) else (float(d), float(d))
    for i in range(n):
        c = p0 + a * (seg * (i + 0.5))
        g = (grow if i % 2 else 0.0) + rng.uniform(-0.03, 0.03)
        tl = tilt * (1 if i % 2 == 0 else -0.6) + rng.uniform(-2, 2)
        up = np.array([0.0, 1.0, 0.0]) if abs(a[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
        up = up + a * math.tan(math.radians(tl))
        q0, q1 = c - a * (seg / 2 + 0.02 - gap / 2), c + a * (seg / 2 + 0.02 - gap / 2)
        out.append(beam(bone, q0, q1, dw + g, dh + g, style, up=up, uv=uv, tags=tags, fx=fx))
        if round_:
            k = 0.88 if dw == dh else 0.8
            out.append(beam(bone, q0, q1, (dw + g) * k, (dh + g) * k, style, up=up, roll=45.0 if dw == dh else 0.0,
                            uv=uv, tags=tags, fx=fx) if dw == dh else
                       beam(bone, q0, q1, dw + g + 0.12, (dh + g) * 0.72, style, up=up, uv=uv, tags=tags, fx=fx))
    if tail:
        ln, dirv = tail
        dv = _v3(dirv)
        dv = dv / np.linalg.norm(dv)
        start = p1 - a * 0.2
        out.append(beam(bone, start, start + dv * ln, max(0.5, min(dw, dh) * 0.55), 0.08, style,
                        up=np.cross(dv, a) if np.linalg.norm(np.cross(dv, a)) > 1e-3 else (0, 1, 0),
                        uv=uv, tags=tuple(tags) + ("ragged",)))
    return out


def rivet(bone: Bone, centre, normal, d: float = 0.5, h: float = 0.14, style: str = "rivet", **kw) -> List[Cube]:
    """丸い鋲の頭（面 normal の上に乗る、2 枚で八角）。centre は頭の底の中心。"""
    n, _R = _axis_frame(normal)
    c = _v3(centre) + n * (h / 2)
    out = disc(bone, c, n, d / 2 * 0.9, h, style, n=2, star=0.86, **kw)
    return out


def nail(bone: Bone, p0, p1, style: str, *, d: float = 0.22, head: float = 0.0, bend=None, **kw) -> List[Cube]:
    """釘: p0（頭の側）→ p1（先）。head > 0 なら p0 に頭（直径 head）。bend=(長さ, 向き) で先を曲げる。"""
    p0, p1 = _v3(p0), _v3(p1)
    out = [beam(bone, p0, p1, d, d, style, **kw)]
    a = (p1 - p0) / np.linalg.norm(p1 - p0)
    if head > 0:
        out += disc(bone, p0 - a * 0.05, a, head / 2, 0.12, style, n=2, **kw)
    if bend:
        ln, dv = bend
        dv = _v3(dv)
        dv = dv / np.linalg.norm(dv)
        out.append(beam(bone, p1 - a * d * 0.4, p1 - a * d * 0.4 + dv * ln, d * 0.95, d * 0.95, style, **kw))
    return out


def bolt(bone: Bone, centre, axis, length: float, d: float, style: str, *, nut: Optional[str] = None,
         nut_size: float = None, washer: bool = False, ends=(True, True), **kw) -> List[Cube]:
    """ボルトを軸 axis に貫通させ、両端に六角（頭とナット）を付ける。ends で頭・ナットの有無。"""
    a, _R = _axis_frame(axis)
    c = _v3(centre)
    out = rod(bone, c - a * length / 2, c + a * length / 2, d, style, **kw)
    ns = nut_size or d * 1.9
    for sgn, on in ((-1, ends[0]), (1, ends[1])):
        if not on:
            continue
        p = c + a * sgn * (length / 2 - ns * 0.25)
        out += hex_prism(bone, p, a, ns, ns * 0.5, nut or style, **kw)
        if washer:
            out += disc(bone, p - a * sgn * ns * 0.3, a, ns * 0.68, 0.1, nut or style, n=2, **kw)
    return out


def weld(bone: Bone, pts, d: float, style: str, *, seed=0, step=0.45, **kw) -> List[Cube]:
    """溶接のビード: 点列に沿って小さな塊を少しずつずらして並べる（盛り上がった不揃いの粒）。"""
    import random as _random
    rng = _random.Random(stable_hash(("weld", seed)))
    out = []
    pts = [_v3(p) for p in pts]
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        L = float(np.linalg.norm(b - a))
        k = max(1, int(round(L / step)))
        for j in range(k):
            c = a + (b - a) * ((j + 0.5) / k)
            s = d * rng.uniform(0.75, 1.1)
            rot = (rng.uniform(-30, 30), rng.uniform(-40, 40), rng.uniform(-30, 30))
            out.append(cbox(bone, c, (s, s * 0.8, s * 1.1), style, rot=rot, **kw))
    return out


def rag(bone: Bone, top, length: float, width: float, style: str, *, hang=(0.0, -1.0, 0.25), thick=0.08,
        strips: int = 2, spread: float = 0.35, seed=0, uv=None) -> List[Cube]:
    """結んだ所 top から垂れる布切れ（strips 枚の短冊、端はほつれて穴が開く = tags ragged）。"""
    import random as _random
    rng = _random.Random(stable_hash(("rag", seed)))
    out = []
    h = _v3(hang)
    h = h / np.linalg.norm(h)
    side = np.cross(h, np.array([1.0, 0.0, 0.0]))
    if np.linalg.norm(side) < 1e-3:
        side = np.array([0.0, 0.0, 1.0])
    side = side / np.linalg.norm(side)
    for i in range(strips):
        off = (i - (strips - 1) / 2) * spread
        dv = h + side * rng.uniform(-0.25, 0.25) + np.array([rng.uniform(-0.15, 0.15), 0, 0])
        dv = dv / np.linalg.norm(dv)
        ln = length * rng.uniform(0.75, 1.1)
        p0 = _v3(top) + side * off
        mid = p0 + dv * ln * 0.5 + np.array([rng.uniform(-0.15, 0.15), 0, 0])
        # 2 段に折って、布のたるみ（2 枚目は少しよじる）
        w_ = width * rng.uniform(0.75, 1.0)
        out.append(beam(bone, p0, mid, thick, w_, style, up=np.cross(dv, (1, 0, 0)) if abs(dv[0]) < 0.9 else (0, 1, 0),
                        uv=uv, tags=("ragged", "noao")))
        dv2 = dv + np.array([rng.uniform(-0.25, 0.25), 0, rng.uniform(-0.2, 0.2)])
        dv2 = dv2 / np.linalg.norm(dv2)
        out.append(beam(bone, mid - dv * 0.1, mid + dv2 * ln * 0.55, thick, w_ * 0.85, style,
                        up=np.cross(dv2, (1, 0, 0)) if abs(dv2[0]) < 0.9 else (0, 1, 0), roll=rng.uniform(-14, 14),
                        uv=uv, tags=("ragged", "noao")))
    return out


def coil(bone: Bone, centre, axis, d: float, length: float, turns: int, style: str, *, wire=0.16, **kw):
    """針金・銅線の巻き（turns 本の細い輪を並べる。輪は 4 本の角柱で四角に回す）。"""
    a, R = _axis_frame(axis)
    c = _v3(centre)
    out = []
    xa, ya = R[:, 0], R[:, 1]
    r = d / 2
    for i in range(turns):
        t = (i + 0.5) / turns - 0.5
        cc = c + a * (t * length)
        tw = 0.12 * (1 if i % 2 else -1)     # 輪を少しずつ傾ける（巻きの螺旋）
        for k in range(4):
            u = xa * math.cos(k * math.pi / 2) + ya * math.sin(k * math.pi / 2)
            v = np.cross(a, u)
            p_mid = cc + u * r + a * tw * (1 if k % 2 else -1) * 0.5
            out.append(beam(bone, p_mid - v * (r + wire * 0.5), p_mid + v * (r + wire * 0.5), wire, wire, style,
                            up=u, **kw))
    return out


def lash(bone: Bone, centre, axis, w: float, h: float, length: float, turns: int, style: str, *, wire=0.14,
         up=(0.0, 1.0, 0.0), skew=0.18, **kw) -> List[Cube]:
    """四角い束を縛る針金・紐（幅 w × 高さ h の長方形の輪を turns 本。2 本の棒・柄と刃物の柄をまとめる）。
    輪は 1 本おきに傾けて（skew 単位）、巻き付けた螺旋に見せる。局所の高さ方向は up。"""
    a = _v3(axis)
    a = a / np.linalg.norm(a)
    c = _v3(centre)
    yv = _v3(up) - a * float(_v3(up) @ a)
    yv = yv / np.linalg.norm(yv)
    xv = np.cross(yv, a)
    out = []
    for i in range(turns):
        t = ((i + 0.5) / turns - 0.5) * length
        cc = c + a * t
        sk = skew * (1 if i % 2 else -1) * 0.5
        hw, hh = w / 2 + wire / 2, h / 2 + wire / 2
        # 上下の辺（x 方向）と左右の辺（y 方向）。上下で軸方向に少しずらして傾ける
        for sy in (-1, 1):
            p = cc + yv * sy * (h / 2) + a * sk * sy
            out.append(beam(bone, p - xv * hw, p + xv * hw, wire, wire, style, up=yv, **kw))
        for sx in (-1, 1):
            p = cc + xv * sx * (w / 2)
            out.append(beam(bone, p - yv * hh - a * sk, p + yv * hh + a * sk, wire, wire, style, up=xv, **kw))
    return out


def teeth_row(bone: Bone, p0, p1, n: int, size, style: str, *, up=(0.0, 1.0, 0.0), rot45=True, **kw):
    """p0 → p1 に n 個の歯（45° 回した小さな箱 = 三角の山）を並べる。鋸刃・レンチの顎の刻み。"""
    p0, p1 = _v3(p0), _v3(p1)
    d = p1 - p0
    R = frame(d / np.linalg.norm(d), up)
    if rot45:
        a = math.radians(45.0)
        R = R @ np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    out = []
    for i in range(n):
        c = p0 + d * ((i + 0.5) / n)
        out.append(oriented(bone, c, size, R, style, **kw))
    return out


def inside_cubes(cubes, P) -> np.ndarray:
    """武器空間の点 P (n,3) がキューブの集まりのどれかの中にあるか（root と、回転の無いボーンのキューブ用）。"""
    P = np.atleast_2d(np.asarray(P, float))
    ins = np.zeros(len(P), bool)
    for c in cubes:
        o = _v3(c.origin) - c.inflate
        s = _v3(c.size) + 2 * c.inflate
        if c.rotation:
            piv = _v3(c.pivot)
            Q = (P - piv) @ HS.rot(*c.rotation) + piv
        else:
            Q = P
        ins |= np.all((Q >= o) & (Q <= o + s), axis=1)
    return ins


def surface_point(cubes, start, direction, *, step: float = 0.03, max_len: float = 20.0, sink: float = 0.06):
    """不規則な塊（回したキューブの重ね: コンクリの塊・溶接の頭）の表面の点。start（塊の中）から direction へ
    進み、最後に中だった所から sink だけ戻った点を返す（小石・肉片・鋲をそこに貼る）。"""
    p0 = _v3(start)
    d = _v3(direction)
    d = d / np.linalg.norm(d)
    ts = np.arange(0.0, max_len, step)
    ins = inside_cubes(cubes, p0[None, :] + ts[:, None] * d[None, :])
    if not ins[0]:
        return p0
    k = int(np.argmin(ins)) if not ins.all() else len(ts)
    return p0 + d * max(0.0, ts[k - 1] - sink)


def rbeam(bone: Bone, p0, p1, w: float, h: float, style: str, *, k: float = 0.78, **kw) -> List[Cube]:
    """角を落とした角柱（幅 w × 高さ h の箱 2 本: (w, h·k) と (w·k, h)）。柄・握りの丸みのある四角い断面。"""
    return [beam(bone, p0, p1, w, h * k, style, **kw), beam(bone, p0, p1, w * k, h, style, **kw)]


def hairs(bone: Bone, x: float, centre_yz, n: int, length: float, style: str, *, seed=0, spread=(1.0, 1.4),
          side=1, **kw) -> List[Cube]:
    """刃の平に貼り付いた髪の毛（細いうねった線を数本）。x は平の面の位置（その少し外に置く）。"""
    import random as _random
    rng = _random.Random(stable_hash(("hair", seed)))
    out = []
    for i in range(n):
        y0 = centre_yz[0] + rng.uniform(-spread[0], spread[0]) * 0.5
        z0 = centre_yz[1] + rng.uniform(-spread[1], spread[1]) * 0.5
        ang = rng.uniform(-0.8, 0.8) + (math.pi / 2 if i % 3 == 0 else 0)
        pts = [(x + side * 0.03, y0, z0)]
        for j in range(3):
            ang += rng.uniform(-0.6, 0.6)
            yy, zz = pts[-1][1] + math.sin(ang) * length / 3, pts[-1][2] + math.cos(ang) * length / 3
            pts.append((x + side * 0.03, yy, zz))
        out += polyline(bone, pts, 0.05, 0.06, style, up=(1, 0, 0), overlap=0.04, tags=("noao",), **kw)
    return out


# ---------------------------------------------------------------------------
#  武器空間で描く模様（cube.fx["world"] に渡す関数を作る）
# ---------------------------------------------------------------------------
def stamp(text: str, centre_zy, height: float, *, mul=0.55, tint=None, side=0, px_per_unit=None):
    """側面（±X）に打刻・焼き印の文字。centre_zy = (z, y) 武器空間、height は字の高さ（単位）。
    side: +1 なら +X 面だけ、-1 なら -X 面だけ、0 なら両面（-X 面は鏡に映らないよう向きを合わせる）。
    文字は -Z 向き（刃先の方）へ読める。mul は暗くする倍率、tint を渡すとその色で塗る。"""
    from nr_paint import text_mask
    n = len(text)
    gh = 5
    gw = 4 * n - 1
    unit = height / gh
    W = gw * 4
    H = gh * 4
    mask = text_mask(text, W, H, (0.5, 0.5), 4, 1)
    zc, yc = centre_zy

    def fn(P, N, L, size, col):
        sx = np.sign(N[:, 0])
        ok = np.abs(N[:, 0]) > 0.7
        if side:
            ok &= sx == side
        # 読む向き: 刃先（-Z）へ。-X 面は外から見ると z が逆に見えるので反転しない（表と裏で鏡文字にならない）
        u = (-(P[:, 2] - zc) * np.where(sx > 0, -1.0, 1.0)) / unit + gw / 2
        v = (-(P[:, 1] - yc)) / unit + gh / 2
        iu = np.floor(u * 4).astype(np.int64)
        iv = np.floor(v * 4).astype(np.int64)
        inside = ok & (iu >= 0) & (iu < W) & (iv >= 0) & (iv < H)
        m = np.zeros(len(P), bool)
        m[inside] = mask[iv[inside], iu[inside]] > 0.5
        if tint is not None:
            return np.where(m[:, None], np.asarray(tint, np.float32) * (0.85 + 0.15 * col / 255.0), col)
        return np.where(m[:, None], col * mul, col)
    return fn


def prof_fns(prof):
    """blade() の輪郭から (峰の y(z), 刃の y(z)) の関数。"""
    zs = np.array([p[0] for p in prof], float)
    sp = np.array([p[1] for p in prof], float)
    ed = np.array([p[2] for p in prof], float)
    o = np.argsort(zs)
    return (lambda z: np.interp(z, zs[o], sp[o])), (lambda z: np.interp(z, zs[o], ed[o]))


def groove(prof, t_lo: float, t_hi: float, z0: float, z1: float, *, dark=0.55, taper=0.6):
    """樋（フラー）: 刃の輪郭の t_lo〜t_hi（0 = 刃、1 = 峰）、z0〜z1 の帯を暗く、下の縁に照り、上の縁に影。
    両端 taper 単位で細って消える。"""
    spf, edf = prof_fns(prof)
    za, zb = min(z0, z1), max(z0, z1)

    def fn(P, N, L, size, col):
        ok = np.abs(N[:, 0]) > 0.7
        z, y = P[:, 2], P[:, 1]
        ys, ye = spf(z), edf(z)
        t = (y - ye) / np.where(np.abs(ys - ye) < 1e-3, 1e-3, ys - ye)
        e = np.clip(np.minimum(z - za, zb - z) / taper, 0, 1)
        mid = (t_lo + t_hi) / 2
        half = (t_hi - t_lo) / 2 * e
        inn = ok & (z > za) & (z < zb) & (np.abs(t - mid) < half)
        lo_rim = ok & (z > za) & (z < zb) & (t < mid - half) & (t > mid - half - 0.05) & (e > 0.2)
        hi_rim = ok & (z > za) & (z < zb) & (t > mid + half) & (t < mid + half + 0.04) & (e > 0.2)
        col = np.where(inn[:, None], col * dark, col)
        col = np.where(lo_rim[:, None], np.minimum(255, col * 1.25 + 12), col)
        return np.where(hi_rim[:, None], col * 0.8, col)
    return fn


def compose(*fns):
    """world 模様の関数を順に重ねる（抜きは OR）。"""
    def fn(P, N, L, size, col):
        cut = np.zeros(len(P), bool)
        for f in fns:
            r = f(P, N, L, size, col)
            if isinstance(r, tuple):
                col, c2 = r
                cut |= np.asarray(c2, bool)
            else:
                col = r
        return (col, cut) if cut.any() else col
    return fn


def spots(centres_zy, r: float, *, mul=0.6, ring=0.12, ring_mul=1.18, side=0):
    """側面の丸い跡（埋めたボルト穴・溶接の点・打痕）。中は暗く、縁は少し明るい輪。"""
    C = np.asarray(centres_zy, np.float32).reshape(-1, 2)

    def fn(P, N, L, size, col):
        ok = np.abs(N[:, 0]) > 0.7
        if side:
            ok &= np.sign(N[:, 0]) == side
        d = np.min(np.hypot(P[:, 2:3] - C[None, :, 0], P[:, 1:2] - C[None, :, 1]), axis=1)
        inner = ok & (d < r)
        rim = ok & (d >= r) & (d < r + ring)
        col = np.where(inner[:, None], col * mul, col)
        return np.where(rim[:, None], np.minimum(255, col * ring_mul + 4), col)
    return fn


def hamon(edge_fn, *, offset=0.32, amp=0.1, period=1.3, width=0.16, seed=0):
    """刃文: 刃の線 y = edge_fn(z) から offset 上に、波打つ白い帯。帯より刃側は少し白く曇らせる。"""
    def fn(P, N, L, size, col):
        ok = np.abs(N[:, 0]) > 0.7
        z, y = P[:, 2], P[:, 1]
        ye = edge_fn(z)
        wave = amp * np.sin(z * (2 * math.pi / period) + seed) + amp * 0.5 * np.sin(z * 5.1 + seed * 2)
        h = y - ye - offset - wave
        band = ok & (np.abs(h) < width)
        below = ok & (h < -width) & (y > ye)
        col = np.where(below[:, None], np.minimum(255, col * 1.06 + 10), col)
        return np.where(band[:, None], np.minimum(255, col * 0.55 + 118), col)
    return fn


def _u32(v) -> np.ndarray:
    return np.asarray(v, np.int64).astype(np.uint32)


def worley3(P, cell: float, seed: int):
    """3D のセル（ウォーリー）ノイズ: 各点から最も近い特徴点までの距離（単位）と、その特徴点の乱数 0..1 を 3 つ。
    面の上の点で測るので、面と特徴点の距離の分だけ大きさの違う丸（打痕・骨材・錆の点）になる。"""
    P = np.asarray(P, np.float64)
    q = P / cell
    base = np.floor(q).astype(np.int64)
    best = np.full(len(P), 1e9)
    r3 = np.zeros((len(P), 3))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = base + np.array([dx, dy, dz])
                ix, iy, iz = _u32(c[:, 0]), _u32(c[:, 1]), _u32(c[:, 2])
                rnd = np.stack([NP._u01(NP.hash3i(ix, iy, iz, seed + 7919 * k)) for k in range(3)], -1)
                fp = c + 0.1 + 0.8 * rnd
                d = np.linalg.norm(q - fp, axis=1)
                m = d < best
                best[m] = d[m]
                r3[m] = rnd[m]
    return best * cell, r3


def pock(seed: int, *, cell: float = 0.9, r: float = 0.24, frac: float = 0.5, dark: float = 0.6,
         rim: float = 1.16, lo=None, hi=None):
    """打痕・へこみ（全部の面に。world 模様）。frac は特徴点のうち痕になる割合、lo / hi で武器空間の箱に限る。
    中は暗く、縁は少し明るい（叩かれて光った縁）。"""
    lo_ = None if lo is None else _v3(lo)
    hi_ = None if hi is None else _v3(hi)

    def fn(P, N, L, size, col):
        d, rnd = worley3(P, cell, seed)
        ok = rnd[:, 0] < frac
        if lo_ is not None:
            ok &= np.all((P >= lo_) & (P <= hi_), axis=1)
        rr = r * (0.55 + 0.9 * rnd[:, 1])
        inner = ok & (d < rr * 0.68)
        ring = ok & (d >= rr * 0.68) & (d < rr)
        col = np.where(inner[:, None], col * dark, col)
        return np.where(ring[:, None], np.minimum(255, col * rim + 6), col)
    return fn


def paint_band(z0: float, z1: float, rgb, *, seed: int = 0, chip: float = 0.3, edge: float = 0.12,
               gloss: float = 0.12):
    """z0〜z1 の帯に塗ったペンキ（柄の黄色い帯・目印）。chip は剥げの量（下地が見える）。端は少しよれる。"""
    za, zb = min(z0, z1), max(z0, z1)
    rgb_ = np.asarray(rgb, np.float32)

    def fn(P, N, L, size, col):
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        wob = (NP.fbm3(x * 3.0, y * 3.0, z * 0.5, seed, octaves=2) - 0.5) * edge * 2
        inb = (z > za + wob) & (z < zb - wob)
        n = NP.fbm3(x * 2.4, y * 2.4, z * 2.4, seed + 11, octaves=3)
        # 端ほど剥げやすい
        e = np.clip(np.minimum(z - za, zb - z) / 0.6, 0, 1)
        peeled = n < chip * (1.25 - 0.5 * e)
        lum = col.mean(1, keepdims=True) / 255.0
        paint = rgb_[None, :] * (0.78 + 0.3 * lum) * (1.0 + gloss * (n[:, None] - 0.5))
        m = inb & ~peeled
        out = np.where(m[:, None], np.clip(paint, 0, 255), col)
        rim_ = inb & peeled & (n > chip * (1.25 - 0.5 * e) - 0.05)
        return np.where(rim_[:, None], out * 0.72, out)
    return fn


def crack(p0, p1, *, width: float = 0.07, seed: int = 0, wiggle: float = 0.22, dark: float = 0.3,
          branch: float = 0.0, normal=None):
    """表面の割れ（p0 → p1 の線を noise でうねらせた暗い筋、縁はわずかに明るい）。木の柄の割れ・コンクリのひび。
    normal を渡すとその向きの面だけに、面の中でうねる線として描く（柄の +X の面の割れなど）。
    渡さなければ線からの 3D の距離で描くので、線の近くを通る全部の面に出る（角をまたいで続く）。
    branch > 0 で細い枝。"""
    a, b = _v3(p0), _v3(p1)
    d = b - a
    L = float(np.linalg.norm(d)) or 1.0
    u = d / L
    nn = None if normal is None else _v3(normal) / np.linalg.norm(normal)

    def fn(P, N, Lc, size, col):
        t = np.clip((P - a) @ u, 0, L)
        foot = a + np.outer(t, u)
        off = P - foot
        # 線に直角な 2 方向へ、t に沿った noise でうねらせる
        n1 = (NP.fbm3(t * 1.7, t * 0.3, np.zeros_like(t), seed, octaves=3) - 0.5) * 2 * wiggle
        n2 = (NP.fbm3(t * 1.7 + 9.1, t * 0.3, np.zeros_like(t), seed + 3, octaves=3) - 0.5) * 2 * wiggle
        if nn is not None:
            v1 = np.cross(nn, u)
            v1 /= (np.linalg.norm(v1) or 1.0)
            off = off - np.outer(off @ nn, nn)
            dist = np.linalg.norm(off - np.outer(n1, v1), axis=1)
            dist = np.where((N @ nn) > 0.6, dist, 1e9)
        else:
            ref = np.array([0.0, 1.0, 0.0]) if abs(u[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
            v1 = np.cross(u, ref)
            v1 /= np.linalg.norm(v1)
            v2 = np.cross(u, v1)
            dist = np.linalg.norm(off - np.outer(n1, v1) - np.outer(n2, v2), axis=1)
        taper = np.clip(np.minimum(t, L - t) / (0.25 * L + 1e-6), 0.25, 1.0)
        w = width * taper
        m = dist < w
        rim_ = (dist >= w) & (dist < w + 0.05)
        if branch > 0:
            bt = (NP.fbm3(P[:, 0] * 4, P[:, 1] * 4, P[:, 2] * 4, seed + 5, octaves=2))
            m |= (dist < w * 4) & (np.abs(bt - 0.5) < 0.02 * branch) & (dist > w)
        col = np.where(rim_[:, None], np.minimum(255, col * 1.1 + 4), col)
        return np.where(m[:, None], col * dark, col)
    return fn


def stamp_on(text: str, centre, height: float, *, normal=(0.0, 0.0, -1.0), up=(0.0, 1.0, 0.0), mul=0.55,
             tint=None):
    """normal を向いた面（ピストンの冠面・ハンマーの頭の端など、±X 以外）に打刻の文字。外から見て up が上、
    正しく読める向き。WC.stamp の一般化（stamp は ±X の面専用）。"""
    from nr_paint import text_mask
    n_ = _v3(normal) / np.linalg.norm(normal)
    up_ = _v3(up)
    up_ = up_ - n_ * float(up_ @ n_)
    up_ /= np.linalg.norm(up_)
    right = np.cross(up_, n_)
    k = len(text)
    gh, gw = 5, 4 * k - 1
    unit = height / gh
    W, H = gw * 4, gh * 4
    mask = text_mask(text, W, H, (0.5, 0.5), 4, 1)
    c = _v3(centre)

    def fn(P, N, L, size, col):
        ok = (N @ n_) > 0.7
        rel = P - c
        u = (rel @ right) / unit + gw / 2
        v = -(rel @ up_) / unit + gh / 2
        iu = np.floor(u * 4).astype(np.int64)
        iv = np.floor(v * 4).astype(np.int64)
        inside = ok & (iu >= 0) & (iu < W) & (iv >= 0) & (iv < H)
        m = np.zeros(len(P), bool)
        m[inside] = mask[iv[inside], iu[inside]] > 0.5
        if tint is not None:
            return np.where(m[:, None], np.asarray(tint, np.float32) * (0.85 + 0.15 * col / 255.0), col)
        return np.where(m[:, None], col * mul, col)
    return fn


# ===========================================================================
#  モデル
# ===========================================================================
class WeaponModel:
    """geometry.nr.w.<key> の骨組み: hold（binding）→ root（握り = 原点）→ 任意の子ボーン。

    uv は既定の texel 密度（モデル単位あたり）。キューブごとに uv= で上書きできる（刃は細かく、柄は粗く）。
    """

    def __init__(self, key: str, uv: float = 5.0, max_tex=MAX_TEX, visible_bounds=(6, 6),
                 vb_offset=(0, 1.0, 0), ident: Optional[str] = None):
        self.key = key
        self.model = Model(ident or f"geometry.nr.w.{key}", uv_scale=uv, visible_bounds=visible_bounds,
                           vb_offset=vb_offset, max_atlas=max_tex)
        self.max_tex = tuple(max_tex)
        self.hold = self.model.bone("hold", (0, 0, 0), binding=BINDING)
        self.root = self.model.bone("root", (0, 0, 0), parent="hold")
        self.bones: Dict[str, Bone] = {"hold": self.hold, "root": self.root}
        self.idle: Dict[str, dict] = {}         # 待機アニメのボーン（{"saw": {"rotation": [...]}}）
        self.uv_fit = 1.0                       # pack() が縮めた倍率
        self.cuts: List[dict] = []              # 貫通穴（texture() が透明に抜く。cut() で足す）

    def cut(self, centre, axis=(1, 0, 0), r: float = 0.4, half: float = 3.0, rim: float = 0.14,
            shape: str = "round") -> None:
        """武器空間の円柱（軸 axis、半径 r、長さ 2*half）の中の texel を全部透明にする（吊るし穴・肉抜き・
        ククリのチョー）。キューブを削れないので「表と裏の面を同じ形で抜く」ことで穴に見せる。
        穴の周り rim は暗くする。shape="square" なら四角い穴。"""
        a = _v3(axis)
        self.cuts.append({"c": _v3(centre), "a": a / np.linalg.norm(a), "r": float(r), "half": float(half),
                          "rim": float(rim), "shape": shape})

    def bone(self, name: str, pivot=(0, 0, 0), parent: str = "root", rotation=None) -> Bone:
        if name in self.bones:
            return self.bones[name]
        b = self.model.bone(name, _r(pivot), parent=parent, rotation=rotation)
        self.bones[name] = b
        return b

    @property
    def cubes(self) -> List[Cube]:
        return self.model.all_cubes()

    @property
    def cube_count(self) -> int:
        return len(self.cubes)

    def bone_of(self) -> Dict[int, Bone]:
        return {id(c): b for b in self.model.bones for c in b.cubes}

    def pack(self, padding: int = 1) -> Tuple[int, int]:
        """アトラスに詰める。入らなければ全キューブの密度を少しずつ下げる（最後は MAX_TEX の中に必ず収める）。"""
        cubes = self.cubes
        base = {id(c): float(c.uv_scale or self.model.uv_scale) for c in cubes}
        sizes = [s for s in PACK_SIZES if s[0] <= self.max_tex[0] and s[1] <= self.max_tex[1]]
        k = 1.0
        for _ in range(40):
            for c in cubes:
                c._scale = max(0.5, base[id(c)] * k)
                if not c.fixed:
                    c.uv = None
            for w, h in sizes:
                if self.model._try_pack(w, h, padding):
                    self.model.tex_w, self.model.tex_h = w, h
                    self.uv_fit = k
                    return w, h
            k *= 0.94
        raise ValueError(f"{self.key}: {self.max_tex} に入らない（{len(cubes)} キューブ）")

    def bone_world(self) -> Dict[str, np.ndarray]:
        W = {}
        for b in self.model.bones:
            L = HS.bone_local(b.pivot, b.rotation or (0, 0, 0))
            W[b.name] = (W[b.parent] if b.parent else np.eye(4)) @ L
        return W

    def cube_matrix(self, c: Cube, W=None) -> np.ndarray:
        W = W or self.bone_world()
        b = self.bone_of()[id(c)]
        M = np.eye(4)
        if c.rotation:
            piv = _v3(c.pivot)
            R = HS.rot(*c.rotation)
            M[:3, :3] = R
            M[:3, 3] = piv - R @ piv
        return W[b.name] @ M

    def points(self, step: float = 0.6, skip_tags=("soft",)) -> np.ndarray:
        """表面の点（武器空間、N x 3）。めり込み検査・大きさの計測用。"""
        W = self.bone_world()
        bo = self.bone_of()
        pts = []
        for c in self.cubes:
            if set(getattr(c, "tags", ())) & set(skip_tags):
                continue
            M = W[bo[id(c)].name]
            if c.rotation:
                piv = _v3(c.pivot)
                R = HS.rot(*c.rotation)
                Mc = np.eye(4)
                Mc[:3, :3] = R
                Mc[:3, 3] = piv - R @ piv
                M = M @ Mc
            a = _v3(c.origin) - c.inflate
            s = _v3(c.size) + 2 * c.inflate
            n = [max(2, int(math.ceil(s[i] / step)) + 1) for i in range(3)]
            g = np.stack(np.meshgrid(*[np.linspace(0, 1, n[i]) for i in range(3)], indexing="ij"), -1).reshape(-1, 3)
            surf = (g == 0) | (g == 1)
            g = g[surf.any(axis=1)]
            P = a + g * s
            pts.append((M[:3, :3] @ P.T).T + M[:3, 3])
        return np.vstack(pts) if pts else np.zeros((0, 3))

    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        p = self.points(1.0)
        return p.min(0), p.max(0)

    def length_z(self) -> float:
        lo, hi = self.bounds()
        return float(hi[2] - lo[2])

    def geometry_doc(self) -> dict:
        if not self.model.tex_w:
            self.pack()
        return NC.geometry_doc(self.model)

    def stats(self) -> str:
        return f"{self.cube_count} cubes / {self.model.tex_w}x{self.model.tex_h} (uv x{self.uv_fit:.2f})"


# ===========================================================================
#  塗り: spec の SURFACES → nr_paint のスタイル
# ===========================================================================
def _hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def surface_style(key: str, base=None, **over) -> dict:
    """nr_spec_catalog.SURFACES のキー（steel_worn / wood_old / tape_grey …）を nr_paint のスタイルに。
    base で基準色を上書き（spec の palette から）。over は nr_paint のパラメータ（dirt / wear / blood …）。"""
    import nr_spec_catalog as SC
    rgb = tuple(base) if base is not None else tuple(SC.SURFACES.get(key, {}).get("rgb", (128, 128, 128)))
    k = key
    if k == "steel_clean":
        st = NP.style("metal", base=rgb, scratches=0.25, wear=0.6, dirt=0.06)
    elif k == "steel_worn":
        st = NP.style("metal", base=rgb, scratches=0.75, wear=0.5, dirt=0.3)
    elif k == "steel_dark":
        st = NP.style("metal", base=rgb, scratches=0.35, wear=0.85, dirt=0.25)
    elif k == "steel_rusty":
        st = NP.style("rust", base=rgb, amount=0.7, metal=(118, 116, 112), wear=0.3, dirt=0.3)
    elif k == "steel_painted":
        st = NP.style("painted_metal", base=rgb, wear=0.55, rust=0.45, dirt=0.35)
    elif k == "iron_cast":
        st = NP.style("rust", base=(112, 66, 40), amount=0.28, metal=rgb, wear=0.4, dirt=0.45)
    elif k == "chrome":
        st = NP.style("chrome", base=rgb, dirt=0.2, wear=0.3)
    elif k == "aluminium":
        st = NP.style("metal", base=rgb, scratches=0.55, wear=0.3, dirt=0.25)
    elif k in ("brass", "copper_wire"):
        st = NP.style("metal", base=rgb, scratches=0.4, wear=0.6, dirt=0.35)
    elif k == "rebar":
        st = NP.style("rust", base=(124, 70, 44), amount=0.85, metal=(92, 86, 80), wear=0.2, dirt=0.5)
    elif k in ("wood_old", "wood_dark", "wood_raw", "plywood"):
        st = NP.style("wood", base=rgb, grain=1.1 if k != "plywood" else 2.2, wear=0.35 if k == "wood_old" else 0.15,
                      dirt=0.35 if k != "wood_raw" else 0.15)
    elif k == "wood_painted":
        st = NP.style("painted_metal", base=rgb, wear=0.75, rust=0.0, dirt=0.4)
    elif k == "rubber_black":
        st = NP.style("rubber", base=rgb, dirt=0.3, wear=0.3)
    elif k.startswith("plastic_"):
        st = NP.style("plastic", base=rgb, wear=0.45, dirt=0.35)
    elif k in ("tape_grey", "tape_black"):
        st = NP.style("cloth", base=rgb, pattern="plain", dirt=0.45, wear=0.3, folds=0.2, seams=False)
    elif k in ("cloth_rag", "cloth_red", "burlap"):
        st = NP.cloth_style(rgb, pattern="plain", dirt=0.55, blood=0.0, torn=0.0, wear=0.4)
    elif k in ("paracord", "rope"):
        st = NP.cloth_style(rgb, pattern="stripes", alt=tuple(int(v * 0.72) for v in rgb), period=0.35,
                            dirt=0.4, blood=0.0)
    elif k == "leather_brown":
        st = NP.leather_style(rgb, dirt=0.35, blood=0.0, wear=0.6)
    elif k in ("concrete", "concrete_dark"):
        st = NP.style("concrete", base=rgb, cracks=0.5, dirt=0.4)
    elif k.startswith("emissive_"):
        st = NP.style("glow", base=rgb)
    elif k == "blood_wet":
        st = NP.style("blood", base=rgb)
    elif k == "blood_dry":
        st = NP.style("blood_dry", base=rgb)
    elif k == "gore_meat":
        st = NP.style("gore_wet", base=rgb)
    elif k == "bone":
        st = NP.style("bone", base=rgb)
    elif k == "paper":
        st = NP.style("paper", base=rgb, lines=False, dirt=0.4)
    elif k == "fuel":
        st = NP.style("plastic", base=rgb, wear=0.0)
    elif k.startswith("glass"):
        st = NP.style("glass", base=rgb, crack=0.6 if "broken" in k else 0.0)
    elif k.startswith("paint_"):
        st = NP.style("painted_metal", base=rgb, wear=0.4, rust=0.4, dirt=0.35)
    else:
        st = NP.style("metal", base=rgb)
    st.update(over)
    return st


class Stylebook(dict):
    """{スタイル名: nr_paint のスタイル}。palette は spec の色（'#rrggbb' の列）で、色を差し替えるのに使う。"""

    def __init__(self, palette: Sequence[str] = ()):
        super().__init__()
        self.palette = [_hex_rgb(p) for p in palette]

    def pal(self, i: int, default=(128, 128, 128)):
        return self.palette[i] if 0 <= i < len(self.palette) else default

    def add(self, name: str, surface: str, base=None, **over) -> "Stylebook":
        self[name] = surface_style(surface, base=base, **over)
        return self

    def raw(self, name: str, st: dict) -> "Stylebook":
        self[name] = dict(st)
        return self


# ===========================================================================
#  texel → 武器空間の対応（後処理用）
# ===========================================================================
# 面の置き方（nr_preview の表と同じ「実機の向き」）: (左上の角, u の向き, v の向き, 外向きの法線)
#   a = 小さい側, b = 大きい側。east は -X（x = a）。
def _face_geom(face, a, b):
    ax, ay, az = a
    bx, by, bz = b
    if face == "north":
        return (ax, by, az), (bx - ax, 0, 0), (0, -(by - ay), 0), (0, 0, -1)
    if face == "south":
        return (bx, by, bz), (-(bx - ax), 0, 0), (0, -(by - ay), 0), (0, 0, 1)
    if face == "east":
        return (ax, by, bz), (0, 0, -(bz - az)), (0, -(by - ay), 0), (-1, 0, 0)
    if face == "west":
        return (bx, by, az), (0, 0, bz - az), (0, -(by - ay), 0), (1, 0, 0)
    if face == "up":
        return (ax, by, bz), (bx - ax, 0, 0), (0, 0, -(bz - az)), (0, 1, 0)
    return (ax, ay, az), (bx - ax, 0, 0), (0, 0, bz - az), (0, -1, 0)


FACE_IDS = {"up": 0, "down": 1, "east": 2, "north": 3, "west": 4, "south": 5}


class TexMap:
    """アトラスの各 texel が武器空間（静止姿勢）のどこにあるか。

    P (H,W,3) 位置 / N (H,W,3) 外向き法線 / L (H,W,3) キューブ自身の座標（回転前）/ cube (H,W) キューブ番号
    （-1 = 使っていない）/ face (H,W) 面の番号（FACE_IDS）/ fu, fv 面の中の正規化座標。
    """

    def __init__(self, wm: WeaponModel):
        m = wm.model
        if not m.tex_w:
            wm.pack()
        H, W = m.tex_h, m.tex_w
        self.H, self.W = H, W
        self.P = np.zeros((H, W, 3), np.float32)
        self.N = np.zeros((H, W, 3), np.float32)
        self.L = np.zeros((H, W, 3), np.float32)
        self.cube = np.full((H, W), -1, np.int32)
        self.face = np.full((H, W), -1, np.int8)
        self.fu = np.zeros((H, W), np.float32)
        self.fv = np.zeros((H, W), np.float32)
        self.cubes = wm.cubes
        Wb = wm.bone_world()
        bo = wm.bone_of()
        self.mats = []
        self.boxes = []
        for k, c in enumerate(self.cubes):
            M = Wb[bo[id(c)].name]
            if c.rotation:
                piv = _v3(c.pivot)
                R = HS.rot(*c.rotation)
                Mc = np.eye(4)
                Mc[:3, :3] = R
                Mc[:3, 3] = piv - R @ piv
                M = M @ Mc
            self.mats.append(M)
            a = _v3(c.origin) - c.inflate
            b = _v3(c.origin) + _v3(c.size) + c.inflate
            self.boxes.append((a, b))
            for face, rect in c.rects.items():
                x0, y0, w, h = rect
                if w <= 0 or h <= 0:
                    continue
                o, U, V, n = (np.asarray(t, float) for t in _face_geom(face, a, b))
                jj, ii = np.mgrid[0:h, 0:w]
                fu = (ii + 0.5) / w
                fv = (jj + 0.5) / h
                loc = o + fu[..., None] * U + fv[..., None] * V
                wp = loc @ M[:3, :3].T + M[:3, 3]
                self.P[y0:y0 + h, x0:x0 + w] = wp
                self.N[y0:y0 + h, x0:x0 + w] = M[:3, :3] @ n
                self.L[y0:y0 + h, x0:x0 + w] = loc
                self.cube[y0:y0 + h, x0:x0 + w] = k
                self.face[y0:y0 + h, x0:x0 + w] = FACE_IDS[face]
                self.fu[y0:y0 + h, x0:x0 + w] = fu
                self.fv[y0:y0 + h, x0:x0 + w] = fv
        self.valid = self.cube >= 0
        tags = [frozenset(getattr(c, "tags", ())) for c in self.cubes]
        self.tags = tags

    def tagged(self, tag: str) -> np.ndarray:
        """そのタグを持つキューブの texel（bool (H,W)）。"""
        ids = [k for k, t in enumerate(self.tags) if tag in t]
        if not ids:
            return np.zeros((self.H, self.W), bool)
        return np.isin(self.cube, ids)

    def local_frac(self) -> np.ndarray:
        """キューブの中の正規化座標（回転前の箱で 0..1）。(H,W,3)。"""
        out = np.zeros((self.H, self.W, 3), np.float32)
        for k, (a, b) in enumerate(self.boxes):
            m = self.cube == k
            if m.any():
                out[m] = (self.L[m] - a) / np.maximum(b - a, 1e-6)
        return out


# ===========================================================================
#  後処理: 接触の陰（AO）・研いだ縁・血・ぼろ布の切り抜き
# ===========================================================================
def _ao(tm: TexMap, strength=0.5, heights=(0.14, 0.42), skip_tags=("noao",)) -> np.ndarray:
    """他のキューブが面のすぐ上に被さっている所を暗くする係数 (H,W)。
    面から法線方向に h だけ浮かせた点が他の箱にどれだけ近いかを見る（同じ平面で隣り合う箱は 0）。"""
    occl = np.zeros((tm.H, tm.W), np.float32)
    v = tm.valid
    P = tm.P[v]
    N = tm.N[v]
    own = tm.cube[v]
    acc = np.zeros(len(P), np.float32)
    lo_all = P.min(0) - 1
    hi_all = P.max(0) + 1
    for k, (a, b) in enumerate(tm.boxes):
        if set(tm.tags[k]) & set(skip_tags):
            continue
        M = tm.mats[k]
        Minv = np.linalg.inv(M)
        # 箱の世界での外接箱で候補を絞る
        corners = np.array([[a[0] if i & 1 else b[0], a[1] if i & 2 else b[1], a[2] if i & 4 else b[2]]
                            for i in range(8)])
        wc = corners @ M[:3, :3].T + M[:3, 3]
        lo = wc.min(0) - max(heights) - 0.1
        hi = wc.max(0) + max(heights) + 0.1
        if np.any(hi < lo_all) or np.any(lo > hi_all):
            continue
        cand = np.all((P >= lo) & (P <= hi), axis=1) & (own != k)
        if not cand.any():
            continue
        idx = np.nonzero(cand)[0]
        for wgt, h in zip((0.65, 0.35), heights):
            q = P[idx] + N[idx] * h
            ql = q @ Minv[:3, :3].T + Minv[:3, 3]
            d = np.linalg.norm(np.maximum(np.maximum(a - ql, 0), ql - b), axis=1)
            acc[idx] += wgt * np.clip(1.0 - d / h, 0, 1)
    occl[v] = np.clip(acc, 0, 1)
    return 1.0 - strength * occl


def _edge_shine(rgb, tm: TexMap):
    """tags に "edge" を持つキューブ（研いだ縁）: 刃の線のいちばん外 1 texel を磨いた銀に、その内側を少し明るく。
    縁の角柱は局所 -Y（回転前の箱の下）が刃の線になるように beam で置いてある。"""
    m = tm.tagged("edge") & tm.valid
    if not m.any():
        return rgb
    fr = tm.local_frac()
    # 局所の高さ（単位）: 下からの距離
    hb = np.zeros((tm.H, tm.W), np.float32)
    for k, (a, b) in enumerate(tm.boxes):
        mk = tm.cube == k
        if mk.any():
            hb[mk] = (tm.L[mk][:, 1] - a[1])
    face = tm.face
    side = (face == FACE_IDS["east"]) | (face == FACE_IDS["west"])
    down = face == FACE_IDS["down"]
    rnd = NP.texel_rand(np.arange(tm.W)[None, :].repeat(tm.H, 0), np.arange(tm.H)[:, None].repeat(tm.W, 1), 77)
    line = m & ((side & (hb < 0.13)) | down)
    near = m & side & (hb >= 0.13) & (hb < 0.34)
    out = rgb.copy()
    bright = np.array([226, 231, 236], np.float32)
    out[line] = out[line] * 0.25 + bright * (0.72 + 0.12 * rnd[line, None])
    out[near] = np.minimum(255, out[near] * 1.16 + 10)
    # 研ぎ跡（刃に直角の細い筋）: 縁の側面に薄く
    st = NP.vnoise3(tm.P[..., 0] * 0.5, tm.P[..., 1] * 0.5, tm.P[..., 2] * 9.0, 91)
    hone = m & side & ~line
    out[hone] = out[hone] * (0.93 + 0.12 * st[hone, None])
    del fr
    return out


def _steel_look(rgb, tm: TexMap, seed: int):
    """刃（cube.bt を持つキューブ = blade() / curved_blade() の部品）の平に、写り込みの帯を描く。
    t（0 = 刃の線、1 = 峰）で「研いだ縁の明るさ → 研ぎの段 → 平の暗い地平線の帯 → 峰寄りの空の明るさ」の
    階調を掛け、刃の長さ方向に流れるヘアラインの筋を重ねる。帯は z でゆるく波打たせる（定規の線にしない）。"""
    ids = [k for k, c in enumerate(tm.cubes) if getattr(c, "bt", None) is not None]
    if not ids:
        return rgb
    fr = tm.local_frac()
    T = np.full((tm.H, tm.W), -1.0, np.float32)
    for k in ids:
        m = tm.cube == k
        if m.any():
            b0, b1 = tm.cubes[k].bt
            T[m] = b0 + (b1 - b0) * fr[m][:, 1]
    face = tm.face
    side = (face == FACE_IDS["east"]) | (face == FACE_IDS["west"])
    m = (T >= 0) & side & tm.valid
    if not m.any():
        return rgb
    P = tm.P[m]
    t = np.clip(T[m] + 0.07 * np.sin(P[:, 2] * 0.33 + (seed % 97) * 0.1) +
                0.03 * np.sin(P[:, 2] * 1.1 + 1.7), 0, 1)
    xs = [0.0, 0.1, 0.24, 0.42, 0.55, 0.66, 0.8, 0.92, 1.0]
    ys = [1.2, 1.1, 1.02, 0.9, 0.74, 0.82, 1.04, 1.1, 1.0]
    env = np.interp(t, xs, ys).astype(np.float32)
    streak = NP.fbm3(P[:, 0] * 3.0, P[:, 1] * 9.0, P[:, 2] * 0.18, seed + 11, 3) - 0.5
    fine = NP.fbm3(P[:, 0] * 3.0, P[:, 1] * 30.0, P[:, 2] * 0.5, seed + 12, 2) - 0.5
    mult = env * (1.0 + streak * 0.26 + fine * 0.12)
    out = rgb.copy()
    out[m] = np.clip(rgb[m] * mult[:, None], 0, 255)
    return out


def blood_zone(lo, hi, amount: float = 0.8, kind: str = "wet", soft: float = 1.2, drip: float = 1.0) -> dict:
    """血の付く範囲（武器空間の軸平行の箱）。amount 0..1 は覆う割合、kind は wet（濡れて照る）/ dry（乾いて黒い）。"""
    return {"lo": _v3(lo), "hi": _v3(hi), "amount": float(amount), "kind": kind, "soft": float(soft),
            "drip": float(drip)}


def blood_zones_from_spec(w: dict, scale: float = 1.0, grow: float = 0.5) -> List[dict]:
    """spec の model の部品のうち素材が blood_wet / blood_dry / gore_meat のものから血の範囲を作る。"""
    out = []
    for p in w.get("model", []):
        if p["mat"] not in ("blood_wet", "blood_dry", "gore_meat"):
            continue
        c = np.asarray(p["at"]) * scale
        s = np.asarray(p["size"]) * scale / 2 + grow
        for at in [p["at"]] + list(p.get("rep") or []):
            cc = np.asarray(at) * scale
            out.append(blood_zone(cc - s, cc + s, 0.85 if p["mat"] != "blood_dry" else 0.75,
                                  "dry" if p["mat"] == "blood_dry" else "wet"))
        del c
    return out


def _thr(cover):
    import statistics
    cover = min(0.995, max(0.005, float(cover)))
    return 0.5 + 0.18 * statistics.NormalDist().inv_cdf(1.0 - cover)


def _blood(rgb, tm: TexMap, zones: Sequence[dict], seed: int):
    """武器空間の範囲に血を塗る（3D ノイズなのでキューブの継ぎ目をまたいで繋がる）。

    層（下から）: 薄い膜（下地が透ける赤茶）→ 拭った筋（刃の長さ方向 = Z に伸びる）→ 厚い塊（不透明。
    縁が黒く固まり、濡れていれば上の縁に照り）→ 垂れ（-Y へ。塊の下の縁から、先に玉）→ 飛沫（範囲の外の点）。
    形は低い周波数のノイズで大きくまとめる（細かい斑点の砂嵐にしない）。kind: wet / dry。"""
    if not zones:
        return rgb
    v = tm.valid
    P = tm.P[v].astype(np.float32)
    X, Y, Z = P[:, 0], P[:, 1], P[:, 2]
    N = tm.N[v]
    seed = int(seed) & 0x7FFFFFFF
    # 範囲の場（0..1）。境目は 3D ノイズで揺らす
    warp = (NP.fbm3(X * 0.5 + 3.1, Y * 0.5, Z * 0.5, seed + 9, 3) - 0.5) * 2.0
    f = np.zeros(len(P), np.float32)
    wet = np.zeros(len(P), np.float32)
    drip_amt = np.zeros(len(P), np.float32)
    for zn in zones:
        d = np.linalg.norm(np.maximum(np.maximum(zn["lo"] - P, 0), P - zn["hi"]), axis=1)
        inside = np.minimum(P - zn["lo"], zn["hi"] - P).clip(0, None).min(axis=1)
        sd = d - inside * 0.6 + warp * zn["soft"] * 0.8
        fz = zn["amount"] * NP._ss(zn["soft"], -zn["soft"] * 0.6, sd)
        better = fz > f
        wet = np.where(better, 1.0 if zn["kind"] == "wet" else 0.0, wet)
        drip_amt = np.maximum(drip_amt, fz * zn["drip"])
        f = np.maximum(f, fz)
    act = f > 0.01
    if not act.any():
        return rgb
    base = rgb[v]

    def body_val(yoff=0.0):
        yy = Y + yoff
        return (0.62 * NP.fbm3(X * 0.42, yy * 0.42, Z * 0.42, seed + 1, 3) +
                0.38 * NP.fbm3(X * 1.3, yy * 1.3, Z * 1.3, seed + 3, 3))

    bv = body_val()
    sval = f + (bv - 0.5) * 1.25
    film = NP._ss(0.34, 0.40, sval) * act
    thick = NP._ss(0.56, 0.60, sval) * act
    depth = np.clip((sval - 0.58) / 0.35, 0, 1)
    # 拭った筋: Z に長く伸びたノイズ。膜の外側にも少し出る
    wipe_n = NP.fbm3(X * 1.2, Y * 3.6, Z * 0.16, seed + 2, 3)
    wipe = NP._ss(0.58, 0.63, wipe_n + f * 0.25) * NP._ss(0.08, 0.3, f) * (1 - thick)
    # 垂れ: 側面で、上（+Y）に厚い塊がある列から下へ。列は 0.22 単位幅
    side = np.abs(N[:, 1]) < 0.4
    colx = np.floor(X / 0.22 + 0.5).astype(np.int64)
    colz = np.floor(Z / 0.22 + 0.5).astype(np.int64)
    hcol = NP.hash2i((colx * 7919 + colz).astype(np.uint32), np.full(len(X), 17, np.uint32), seed + 6)
    pr = NP._u01(hcol)
    Lc = 0.3 + 2.2 * NP._u01(NP._fin(hcol ^ np.uint32(0x9E3779B9))) ** 1.6
    dr_on = side & (pr < 0.05 + 0.13 * np.clip(drip_amt, 0, 1)) & (f > 0.05) & (thick < 0.5)
    dmask = np.zeros(len(X), bool)
    bead = np.zeros(len(X), bool)
    if dr_on.any():
        idx = np.nonzero(dr_on)[0]
        hit = np.zeros(len(idx), bool)
        dist = np.full(len(idx), 1e9, np.float32)
        for dy in (0.1, 0.25, 0.45, 0.7, 1.0, 1.35, 1.75, 2.2, 2.6):
            yy = Y[idx] + dy
            bvv = (0.62 * NP.fbm3(X[idx] * 0.42, yy * 0.42, Z[idx] * 0.42, seed + 1, 3) +
                   0.38 * NP.fbm3(X[idx] * 1.3, yy * 1.3, Z[idx] * 1.3, seed + 3, 3))
            c = (f[idx] + (bvv - 0.5) * 1.25 > 0.6) & (dy <= Lc[idx])
            newhit = c & ~hit
            dist[newhit] = dy
            hit |= c
        dmask[idx] = hit
        bead[idx] = hit & (np.abs(dist - Lc[idx]) < 0.2)
    # 飛沫（範囲の縁の外側に点々。大小）
    near = NP._ss(0.02, 0.4, f)
    dn = NP.vnoise3(X * 4.2, Y * 4.2, Z * 4.2, seed + 4)
    dots = (dn > 0.93 - 0.05 * near) & (f > 0.015) & (thick < 0.5)
    big = (NP.vnoise3(X * 1.9 + 7, Y * 1.9, Z * 1.9, seed + 8) > 0.9 - 0.05 * near) & (f > 0.04) & (thick < 0.5)
    # 色
    wm_ = wet[:, None]
    rough = (NP.fbm3(X * 6.0, Y * 6.0, Z * 6.0, seed + 10, 2) - 0.5)
    wet_thick = NP._ramp(depth + rough * 0.25, [(0.0, (112, 8, 10)), (0.35, (86, 4, 7)), (1.0, (46, 1, 4))])
    dry_thick = NP._ramp(depth + rough * 0.35, [(0.0, (92, 30, 20)), (0.4, (66, 18, 12)), (1.0, (38, 10, 8))])
    thick_c = wet_thick * wm_ + dry_thick * (1 - wm_)
    film_k = np.clip((sval - 0.34) / 0.26, 0, 1)[:, None]          # 塊に近いほど濃い膜
    film_c = base * (np.array([0.26, 0.07, 0.06], np.float32) * (1 - film_k * 0.5)) + \
        (np.array([62, 4, 6], np.float32) * wm_ + np.array([54, 17, 11], np.float32) * (1 - wm_)) * (1 - film_k * 0.25)
    drip_c = np.array([104, 6, 8], np.float32) * wm_ + np.array([70, 20, 13], np.float32) * (1 - wm_)
    out = NP._mix(base, film_c, np.maximum(film * 0.94, wipe * 0.65))
    out = NP._mix(out, thick_c, thick)
    # 塊の縁（固まりかけて黒い輪）
    rim = thick * (1 - NP._ss(0.0, 0.12, depth))
    out = out * (1 - (rim * 0.3)[:, None])
    # 乾いた血はひび割れ（セルの境目を暗く）
    if (wet < 0.5).any():
        crk = NP.vnoise3(X * 7.0, Y * 7.0, Z * 7.0, seed + 12)
        crack = (np.abs(crk - 0.5) < 0.035) & (thick > 0.5) & (wet < 0.5)
        out = np.where(crack[:, None], out * 0.6, out)
    out = np.where(dmask[:, None], drip_c * (0.9 + 0.2 * NP.texel_rand(colz.astype(np.uint32),
                                                                       colx.astype(np.uint32), seed))[:, None], out)
    out = np.where(bead[:, None], drip_c * 0.7, out)
    out = np.where((dots | big)[:, None], NP._mix(out, thick_c * 0.95 + 6, np.full(len(out), 0.9, np.float32)), out)
    # 照り: 濡れた厚い塊の上側の縁（上に塊が無い所）だけ、まばらに。垂れの玉にも 1 点
    above = NP._ss(0.56, 0.6, f + (body_val(0.16) - 0.5) * 1.25)
    g = NP.texel_rand(colx.astype(np.uint32), (np.floor(Y * 9.0).astype(np.int64) * 31 + colz).astype(np.uint32),
                      seed + 5)
    gl = (thick > 0.6) & (above < 0.5) & (wet > 0.5) & (g > 0.35)
    gl |= (thick > 0.6) & (wet > 0.5) & (depth > 0.5) & (g > 0.97)
    out = np.where(gl[:, None], NP._mix(out, np.array([206, 86, 82], np.float32),
                                        np.full(len(out), 0.55, np.float32)), out)
    res = rgb.copy()
    res[v] = out
    return res


def _thr_vec(cover):
    """_thr のベクトル版（逆正規分布を表引きで）。"""
    xs = np.linspace(0.005, 0.995, 199)
    ys = np.array([_thr(c) for c in xs], np.float32)
    return np.interp(cover, xs, ys).astype(np.float32)


def _ragged(alpha, rgb, tm: TexMap, seed: int):
    """tags に "ragged" を持つキューブ（布切れ）: 局所 -Y の端（垂れた端）ほどほつれて穴が開く。
    穴は RGBA (0,0,0,0)（M2）。表と裏で同じ形になるよう、穴は武器空間の位置のノイズで決める。"""
    m = tm.tagged("ragged") & tm.valid
    if not m.any():
        return alpha, rgb
    fr = tm.local_frac()
    t = 1.0 - fr[..., 1]                      # 0 = 結んだ側（上）、1 = 垂れた端
    n = NP.fbm3(tm.P[..., 0] * 0.0 + tm.P[..., 1] * 2.2, tm.P[..., 2] * 2.2, tm.P[..., 0] * 0.0, seed, 3)
    cut = m & (n < NP._ss(0.45, 1.0, t) * 0.62 + 0.02)
    a = alpha.copy()
    r = rgb.copy()
    a[cut] = 0
    r[cut] = 0
    return a, r


_NORMAL_AXIS = {FACE_IDS["east"]: 0, FACE_IDS["west"]: 0, FACE_IDS["up"]: 1, FACE_IDS["down"]: 1,
                FACE_IDS["north"]: 2, FACE_IDS["south"]: 2}


def _fx(rgb, alpha, tm: TexMap, seed: int):
    """キューブごとの模様と切り抜き（cube.fx）。座標はキューブ自身の（回転前の）単位。

      ribs=周期      長軸に直角の溝（ゴムの握り・発泡グリップ）
      wrap=周期      斜めに重なる巻き（テープ・革紐・布）。段の影と縁の照り
      knurl=周期     菱目の滑り止め（樹脂の握り・ローレット）
      rebar=周期     鉄筋の節（斜めの盛り上がり）
      holes=(周期, 大きさ)  長軸に沿って並ぶ四角い穴（標識の柱）。黒く抜いた穴に下の縁の照り
      hazard=周期    黄黒の斜め縞（警告テープ）。基準色の上に黒の縞
      sdf=関数       f(局所座標 (n,3) 箱の原点から, 箱の大きさ) → 符号付き距離（負が内側）。外は透明に
      border=(rgb, 幅)  sdf の縁取り（標識の白い縁）
      chips=[(z, 半幅, 深さ), ...]  研いだ縁（局所 -Y が刃の線）の V 字の欠け。z は武器空間。欠けは透明
      line=[(高さの割合, 幅, 濃さ), ...]  側面に長軸に沿った線（樋・グラインドの段・刃文の芯）
      world=関数     f(P 武器空間 (n,3), N 法線 (n,3), L 局所 (n,3), size, col (n,3)) → col か (col, 抜く bool)
                     武器空間で描く模様（刃文・打刻・溶接痕・焼き印）。キューブをまたいで繋がる
    """
    out = rgb.copy()
    a = alpha.copy()
    for k, c in enumerate(tm.cubes):
        fx = getattr(c, "fx", None)
        if not fx:
            continue
        m = (tm.cube == k)
        if not m.any():
            continue
        lo, hi = tm.boxes[k]
        size = hi - lo
        Lr = tm.L[m] - lo
        fid = tm.face[m]
        nax = np.vectorize(_NORMAL_AXIS.get)(fid)
        la = int(np.argmax(size))
        # 周りの軸: 面の中の、長軸でない方
        around_ax = np.where(nax == la, -1, 3 - la - nax)
        long_c = Lr[:, la]
        aax = np.clip(around_ax, 0, 2)
        around_raw = np.where(around_ax >= 0, np.take_along_axis(Lr, aax[:, None], 1)[:, 0], 0.0)
        amid = around_raw - size[aax] / 2                     # 面の中央からの距離（周りの向き）
        # 面ごとに周りの座標をずらして、箱を一周したとき模様がずれすぎないように
        around = around_raw + np.where(nax == (la + 1) % 3, size[(la + 2) % 3], 0.0)
        col = out[m]
        side = around_ax >= 0
        if "ribs" in fx:
            p = float(fx["ribs"])
            g = (long_c / p) % 1.0
            col = np.where((side & (g < 0.2))[:, None], col * 0.58, col)
            col = np.where((side & (g >= 0.2) & (g < 0.34))[:, None], np.minimum(255, col * 1.14 + 4), col)
        if "wrap" in fx:
            p = float(fx["wrap"])
            g = ((long_c + around * 0.42) / p) % 1.0
            col = np.where((side & (g < 0.12))[:, None], col * 0.55, col)
            col = np.where((side & (g >= 0.12) & (g < 0.24))[:, None], np.minimum(255, col * 1.18 + 6), col)
            col = np.where((side & (g >= 0.75))[:, None], col * 0.9, col)
        if "knurl" in fx:
            p = float(fx["knurl"])
            g1 = ((long_c + around) / p) % 1.0
            g2 = ((long_c - around) / p) % 1.0
            line = side & ((g1 < 0.2) | (g2 < 0.2))
            col = np.where(line[:, None], col * 0.62, np.minimum(255, col * 1.06 + 3))
        if "rebar" in fx:
            p = float(fx["rebar"])
            g = ((long_c + around * 0.55) / p) % 1.0
            col = np.where((side & (g < 0.16))[:, None], np.minimum(255, col * 1.3 + 14), col)
            col = np.where((side & (g >= 0.16) & (g < 0.3))[:, None], col * 0.55, col)
        if "holes" in fx:
            p, hs = fx["holes"]
            t = (long_c % p) - p / 2
            hole = side & (np.abs(t) < hs / 2) & (np.abs(amid) < hs / 2)
            rimh = side & (np.abs(t) < hs / 2 + 0.12) & (np.abs(amid) < hs / 2 + 0.12) & ~hole
            col = np.where(rimh[:, None], col * 0.7, col)
            col = np.where(hole[:, None], np.array([18, 18, 20], np.float32), col)
        if "hazard" in fx:
            p = float(fx["hazard"])
            g = np.floor((long_c + around) / p) % 2
            col = np.where((g == 1)[:, None], col * 0.16 + np.array([14, 13, 12], np.float32), col)
        if "line" in fx:
            hb = Lr[:, 1] / max(size[1], 1e-6)
            for frac, wid, dark in fx["line"]:
                dl = np.abs(hb - frac) * size[1]
                m_ = side & (nax != 1) & (dl < wid / 2)
                col = np.where(m_[:, None], col * (1.0 - dark), col)
                hi_ = side & (nax != 1) & (dl >= wid / 2) & (dl < wid / 2 + 0.1) & (Lr[:, 1] < frac * size[1])
                col = np.where(hi_[:, None], np.minimum(255, col * (1.0 + dark * 0.4) + 6), col)
        if "chips" in fx:
            Pw = tm.P[m]
            cutm = np.zeros(len(Pw), bool)
            for zc, hw, dep in fx["chips"]:
                dz = np.abs(Pw[:, 2] - zc)
                v = 1.0 - dz / hw
                cutm |= (v > 0) & (Lr[:, 1] < dep * np.clip(v, 0, 1) ** 0.7)
                # 欠けの周り（内側の縁）を少し暗く: 研ぎ直していない荒れ
                rim_ = (v > -0.35) & (Lr[:, 1] < dep * 1.5) & ~cutm
                col = np.where(rim_[:, None], col * 0.78, col)
            am = a[m]
            am[cutm] = 0
            a[m] = am
            col[cutm] = 0
        if "world" in fx:
            r = fx["world"](tm.P[m], tm.N[m], Lr, size, col)
            if isinstance(r, tuple):
                col, cutm = r
                am = a[m]
                am[np.asarray(cutm, bool)] = 0
                a[m] = am
                col = np.where(np.asarray(cutm, bool)[:, None], 0, col)
            else:
                col = r
        if "sdf" in fx:
            sd = np.asarray(fx["sdf"](Lr, size), np.float32)
            if "border" in fx:
                bcol, bw = fx["border"]
                bm = (sd <= 0) & (sd > -float(bw))
                col = np.where(bm[:, None], np.array(bcol, np.float32) * (0.9 + 0.1 * col.mean(1, keepdims=True)
                                                                          / 255.0), col)
            cut = sd > 0
            am = a[m]
            am[cut] = 0
            a[m] = am
            col[cut] = 0
        out[m] = col
    return out, a


def sdf_octagon_half(Lr, size, axes=(2, 1), cut_side=+1):
    """板（キューブ）の中に「八角形の半分」（弦 = 箱の一辺）。axes = (横, 縦) の局所軸、cut_side は弦の側。
    横の中央を八角形の中心、縦は弦が箱の端（cut_side=+1 なら上の端）に来る。"""
    W = size[axes[0]]
    Hh = size[axes[1]]
    x = Lr[:, axes[0]] - W / 2
    y = (Hh - Lr[:, axes[1]]) if cut_side > 0 else Lr[:, axes[1]]
    # 八角形: 中心 (0, 0)、平の距離 a（横幅の半分）
    a_ = W / 2
    yy = -y                                   # 中心から下へ
    d1 = np.maximum(np.abs(x), np.abs(yy)) - a_
    d2 = (np.abs(x) + np.abs(yy)) / math.sqrt(2) - a_
    return np.maximum(d1, d2)


def sdf_circle(Lr, size, axes=(2, 1), r=None, teeth=0, tooth_h=0.0, hole=0.0):
    """板の中の円（丸ノコ・歯車）。teeth > 0 なら外周に三角の歯、hole > 0 なら中心の穴。"""
    cx, cy = size[axes[0]] / 2, size[axes[1]] / 2
    x = Lr[:, axes[0]] - cx
    y = Lr[:, axes[1]] - cy
    rr = np.hypot(x, y)
    R = (min(size[axes[0]], size[axes[1]]) / 2) if r is None else r
    d = rr - R
    if teeth:
        ang = np.arctan2(y, x)
        ph = (ang / (2 * math.pi) * teeth) % 1.0
        d = rr - (R - tooth_h + tooth_h * (1 - ph))          # 鋸歯（片側が立った歯）
    if hole > 0:
        d = np.maximum(d, hole - rr)
    return d


def texture(wm: WeaponModel, book: Stylebook, seed: int, *, blood: Sequence[dict] = (), ao: bool = True,
            edges: bool = True, ao_strength: float = 0.5) -> Image.Image:
    """モデルを塗る: nr_paint（素材）→ 接触の陰 → 研いだ縁 → 血 → ぼろ布の切り抜き。RGBA を返す。

    nr_paint の 3D ノイズの面の置き方が古い向き（east = +X）なら、塗る間だけ east / west の UV を入れ替えて
    「実機の向き」と一致させる（DESIGN §13）。直っていれば入れ替えない（_painter_legacy で自動判定）。"""
    if not wm.model.tex_w:
        wm.pack()
    cubes = wm.cubes
    swap = _painter_legacy()
    if swap:
        _swap_ew(cubes)
    try:
        # 面ごとの陰（縁の AO・面の明るさ）は継ぎ目を作るので切り、陰は下の 3D の AO で付ける
        img = NP.paint_model(wm.model, book, seed=seed, face_light=False, ao=False)
    finally:
        if swap:
            _swap_ew(cubes)
    arr = np.asarray(img, np.uint8).copy()
    rgb = arr[..., :3].astype(np.float32)
    alpha = arr[..., 3].copy()
    tm = TexMap(wm)
    glow = (alpha > 0) & (alpha < 255)
    rgb, alpha = _fx(rgb, alpha, tm, seed + 3000)
    if ao:
        f = _ao(tm, ao_strength)
        rgb = np.where(glow[..., None], rgb, rgb * f[..., None])
    if edges:
        rgb = np.where(glow[..., None], rgb, _steel_look(rgb, tm, seed + 4000))
        rgb = np.where(glow[..., None], rgb, _edge_shine(rgb, tm))
    if blood:
        rgb = np.where(glow[..., None], rgb, _blood(rgb, tm, blood, seed + 1000))
    alpha, rgb = _ragged(alpha, rgb, tm, seed + 2000)
    if wm.cuts:
        alpha, rgb = _cut_holes(alpha, rgb, tm, wm.cuts)
    # M2: 穴は (0,0,0,0)、発光以外の α は 255 か 0
    out = np.zeros_like(arr)
    out[..., :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    out[..., 3] = alpha
    out[alpha == 0, :3] = 0
    return Image.fromarray(out, "RGBA")


def _cut_holes(alpha, rgb, tm: TexMap, cuts):
    """WeaponModel.cut() の円柱・角柱の中を透明に、周りを暗く。"""
    v = tm.valid
    P = tm.P[v]
    a_ = alpha[v].copy()
    col = rgb[v].copy()
    for c in cuts:
        d = P - c["c"]
        t = d @ c["a"]
        radial = d - np.outer(t, c["a"])
        if c["shape"] == "square":
            # 軸に直角な 2 方向のうち大きい方（チェビシェフ距離）
            ref = np.array([0.0, 1.0, 0.0]) if abs(c["a"][1]) < 0.9 else np.array([1.0, 0.0, 0.0])
            u = np.cross(c["a"], ref)
            u = u / np.linalg.norm(u)
            w = np.cross(c["a"], u)
            rr = np.maximum(np.abs(radial @ u), np.abs(radial @ w))
        else:
            rr = np.linalg.norm(radial, axis=1)
        inside = (np.abs(t) <= c["half"]) & (rr < c["r"])
        rim = (np.abs(t) <= c["half"]) & (rr >= c["r"]) & (rr < c["r"] + c["rim"])
        col[rim] = col[rim] * 0.55
        a_[inside] = 0
        col[inside] = 0
    alpha = alpha.copy()
    rgb = rgb.copy()
    alpha[v] = a_
    rgb[v] = col
    return alpha, rgb


def _painter_legacy() -> bool:
    """nr_paint が east を +X に置いているか（古い向き）。"""
    try:
        o, _a, _b = NP._face_frame("east", (0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        return float(o[0]) > 0.5
    except Exception:  # noqa: BLE001
        return False


def _swap_ew(cubes):
    for c in cubes:
        r = c.rects
        if "east" in r and "west" in r:
            r["east"], r["west"] = r["west"], r["east"]
        if c.decals:
            d = dict(c.decals)
            e, w_ = d.pop("east", None), d.pop("west", None)
            if e is not None:
                d["west"] = e
            if w_ is not None:
                d["east"] = w_
            c.decals = d


# ===========================================================================
#  持ち方（三人称・一人称）。hd_space / hd_holds の規則で逆算する
# ===========================================================================
# anim_set（nr_spec_catalog.ANIM_SETS のキー）→ 持ち方の型。飛び道具の生成器は自分の型を足してよい
HOLD_STYLES = {
    "slash_1h": "one_hand", "blunt_1h": "one_hand", "throw": "one_hand",
    "slash_2h": "two_hand", "blunt_2h": "two_hand", "stab": "spear",
}

# 型ごとの拳の目標（体の空間: -Z が前、+Y が上、-X がプレイヤーの右。単位）。
# 腕は肘の無い棒（肩から拳の中心まで 8.86）なので、届く所だけを選んである
FIST_TARGETS = {
    "two_hand": {"r": (-3.4, 14.6, -5.6), "l": (1.4, 19.4, -8.0)},
    "spear": {"r": (-4.6, 14.0, -3.6), "l": (-0.2, 18.6, -8.0)},
}


def _solve_arms(style: str):
    t = FIST_TARGETS[style]
    ar, er = HH.solve_arm_to(t["r"], HH.ARM_R_PIVOT, HS.HAND_R, start=(-40, 10, 0))
    al, el = HH.solve_arm_to(t["l"], HH.ARM_L_PIVOT, HS.HAND_L, start=(-60, 30, 0))
    return tuple(ar), tuple(al)


def _fist(arm, left=False):
    piv = HH.ARM_L_PIVOT if left else HH.ARM_R_PIVOT
    hand = HS.HAND_L if left else HS.HAND_R
    return (HS.bone_local(piv, arm) @ np.array([*hand, 1.0]))[:3]


def _hold_arms_table():
    out = {"one_hand": {"arm_r": (HS.HOLDING_RX, 0.0, 0.0), "arm_l": None}}
    for st in FIST_TARGETS:
        ar, al = _solve_arms(st)
        out[st] = {"arm_r": ar, "arm_l": al}
    return out


# 型 → 三人称の腕の絶対角（gen_nr_player_anim との契約。docstring 冒頭を参照）
HOLD_ARMS = _hold_arms_table()
# ANIM_SETS の idle 名 → 型（gen_nr_player_anim が hold_1h / hold_2h / hold_spear を作るときに引く）
IDLE_TO_STYLE = {"hold_1h": "one_hand", "hold_2h": "two_hand", "hold_spear": "spear"}


def hold_contract() -> dict:
    """gen_nr_player_anim 向け: {idle 名: {"arm_r": (rx,ry,rz), "arm_l": (rx,ry,rz)|None}}（三人称の絶対角）。"""
    return {k: dict(HOLD_ARMS[v]) for k, v in IDLE_TO_STYLE.items()}


def _tf(rot, pos, scale) -> dict:
    return {"rotation": tuple(round(float(x), 2) for x in rot), "position": tuple(round(float(x), 2) for x in pos),
            "scale": round(float(scale), 3)}


def place_tp(arm_r, world_R, anchor, scale) -> dict:
    """三人称: 右腕が arm_r のとき、武器空間の点 anchor が拳に来て、武器が世界で world_R を向く変換。"""
    ir = HH.item_rotation(tuple(arm_r), world_R)
    ip = HH.item_position(tuple(arm_r), ir, anchor, scale=scale)
    return _tf(ir, ip, scale)


def fp_place_cam(fwd, up, cam_point, anchor, scale, flat=None) -> dict:
    """一人称: カメラ空間（+X 右・+Y 上・+Z 奥、目からの相対）で、武器の -Z を fwd、+Y を up（または平 +X を flat）
    に向け、握りの点 anchor を cam_point に置く（hd_holds.fp_place）。"""
    R = HH.frame_x(_v3(fwd) / np.linalg.norm(fwd), flat) if flat is not None else frame(fwd, up)
    p = HH.fp_place(R, cam_point, anchor, scale)
    return _tf(p["rotation"], p["position"], p["scale"])


def _fp_scale(wm: WeaponModel, target_len: float, lo=0.42, hi=0.95) -> float:
    L = wm.length_z()
    return float(np.clip(target_len / max(L, 1e-3), lo, hi))


def hold_one_hand(wm: WeaponModel, *, grip=0.0, scale=1.0, pitch=38.0, yaw=-4.0, roll=0.0,
                  fp=None, use=None) -> dict:
    """片手持ち（バニラの持ち姿勢のまま）。刃は前上へ pitch 度、刃（-Y）は前下を向く。
    fp / use は上書き用の辞書（fp_place_cam の引数）。"""
    arm = HOLD_ARMS["one_hand"]["arm_r"]
    p, y = math.radians(pitch), math.radians(yaw)
    fwd = np.array([math.sin(y) * math.cos(p), math.sin(p), -math.cos(y) * math.cos(p)])
    up = np.array([0.0, math.cos(p), math.sin(p)])
    if roll:
        a = math.radians(roll)
        side = np.cross(fwd, up)
        up = up * math.cos(a) + side * math.sin(a)
    anchor = (0.0, 0.0, grip)
    tp = place_tp(arm, frame(fwd, up), anchor, scale)
    # 構え（右クリック長押しで溜める）: 刃を外（-X = 右）・上・後ろへ担ぎ上げる（腕は垂れたままなので、
    # 腕に沿わせず外へ逃がしてめり込ませない）。刃（-Y）は前上を向く
    fwd_u = np.array([-0.42, 0.82, 0.38])
    up_u = np.array([0.1, -0.45, 0.88])
    tp_use = place_tp(arm, frame(fwd_u, up_u), anchor, scale)
    s_fp = _fp_scale(wm, 17.0, 0.55, 0.95)
    fpd = dict(fwd=(-0.38, 0.6, 0.7), up=(0.55, 0.25, 0.75), cam_point=(7.6, -8.2, 11.0))
    fpd.update(fp or {})
    fpp = fp_place_cam(fpd["fwd"], fpd["up"], fpd["cam_point"], anchor, fpd.get("scale", s_fp))
    fud = dict(fwd=(-0.3, 0.9, -0.2), up=(0.45, 0.2, 0.85), cam_point=(9.5, -7.5, 10.0))
    fud.update(use or {})
    fpu = fp_place_cam(fud["fwd"], fud["up"], fud["cam_point"], anchor, fud.get("scale", s_fp))
    return {"style": "one_hand", "arm_r": tuple(arm), "arm_l": None, "grip1": anchor, "grip2": None,
            "tp": tp, "tp_use": tp_use, "fp": fpp, "fp_use": fpu}


def hold_two_hand(wm: WeaponModel, *, style="two_hand", grip=0.0, scale=1.0, up=(0.0, -0.15, 1.0),
                  fp=None, use=None) -> dict:
    """両手持ち（two_hand / spear）。腕は HOLD_ARMS[style]、柄は右の拳 → 左の拳の向き。
    右手が握り grip（武器空間の z）、左手はそこから拳の間隔ぶん刃先側（grip2）。up は武器の +Y を向けたい向き
    （既定は後ろ = 刃が前を向く）。"""
    arms = HOLD_ARMS[style]
    ar, al = arms["arm_r"], arms["arm_l"]
    Fr, Fl = _fist(ar), _fist(al, left=True)
    d = float(np.linalg.norm(Fl - Fr))
    fwd = (Fl - Fr) / d
    R = frame(fwd, up)
    anchor = (0.0, 0.0, grip)
    tp = place_tp(ar, R, anchor, scale)
    grip2 = (0.0, 0.0, grip - d / scale)
    # 構え（右クリック長押しで溜める。腕は構えの角度のまま、左手は柄から離れてよい — 一瞬の溜め）:
    #   両手: 右の拳から真上へ立て、顔の右前に掲げる（刃は前）。体の前・頭の右を通るのでめり込まない
    #   槍:   穂先を前に向けたまま、肘を引くように手元へ引き寄せる（突きの溜め）
    if style == "two_hand":
        tp_use = place_tp(ar, frame((-0.3, 0.95, -0.1), (0.05, 0.1, 1.0)), anchor, scale)
    else:
        tp_use = place_tp(ar, R, (0.0, 0.0, grip - 3.0 / scale), scale)
    if style == "spear":
        s_fp = _fp_scale(wm, 21.0, 0.42, 0.8)
        fpd = dict(fwd=(-0.22, 0.20, 0.95), up=(0.0, 1.0, 0.1), cam_point=(7.5, -8.5, 6.0))
        fud = dict(fwd=(-0.16, 0.10, 0.98), up=(0.0, 1.0, 0.1), cam_point=(9.0, -7.5, 2.5))
    else:
        s_fp = _fp_scale(wm, 22.0, 0.45, 0.9)
        fpd = dict(fwd=(-0.5, 0.7, 0.5), up=(0.35, 0.25, 0.9), cam_point=(9.0, -10.0, 12.5))
        fud = dict(fwd=(0.18, 0.92, 0.34), up=(0.2, -0.35, 0.9), cam_point=(9.5, -9.5, 12.0))
    fpd.update(fp or {})
    fud.update(use or {})
    fpp = fp_place_cam(fpd["fwd"], fpd["up"], fpd["cam_point"], anchor, fpd.get("scale", s_fp))
    fpu = fp_place_cam(fud["fwd"], fud["up"], fud["cam_point"], anchor, fud.get("scale", s_fp))
    return {"style": style, "arm_r": tuple(ar), "arm_l": tuple(al), "grip1": anchor, "grip2": grip2,
            "fist_gap": d, "tp": tp, "tp_use": tp_use, "fp": fpp, "fp_use": fpu}


def hold_spear(wm: WeaponModel, **kw) -> dict:
    return hold_two_hand(wm, style="spear", **kw)


def hold_for(w: dict, wm: WeaponModel, **kw) -> dict:
    """spec の武器から既定の持ち方（片手 / 両手 / 槍）。kw は hold_* へそのまま。"""
    st = HOLD_STYLES.get(w["anim_set"], "one_hand")
    if st == "one_hand":
        return hold_one_hand(wm, **kw)
    return hold_two_hand(wm, style=st, **kw)


# ---------------------------------------------------------------------------
#  めり込み検査（三人称の持ち姿勢で、武器が頭・胴・脚・腕に入り込んでいないか）
# ---------------------------------------------------------------------------
_BODY_INFLATE = {"head": 0.4, "body": 0.2, "rightLeg": 0.2, "leftLeg": 0.2, "rightArm": 0.0, "leftArm": 0.0}


def _skeleton():
    import hd_scene
    return hd_scene.SKELETON, hd_scene.skeleton_world


def weapon_world(hold_tf: dict, pose_W: dict, pts: np.ndarray, left=False) -> np.ndarray:
    """武器空間の点 → 世界（hold_tf = tp / fp の変換、pose_W = 骨格のワールド行列）。"""
    L = HS.bone_local((0, 0, 0), hold_tf["rotation"], hold_tf["position"], (hold_tf["scale"],) * 3)
    M = pose_W["leftItem" if left else "rightItem"] @ HS.mat4(t=HS.OFF_L if left else HS.OFF_R) @ L
    return pts @ M[:3, :3].T + M[:3, 3]


def clip_report(wm: WeaponModel, hold: dict, use: bool = False) -> dict:
    """{"depth": 最大の深さ(px), "part": 部位, "gap": 左拳と grip2 の距離(px)}。腕は握っている前腕を除き上腕だけ見る。"""
    SK, skel_world = _skeleton()
    pose = {"rightArm": {"rotation": hold["arm_r"]}}
    if hold.get("arm_l"):
        pose["leftArm"] = {"rotation": hold["arm_l"]}
    W = skel_world(pose)
    tf = hold["tp_use" if use else "tp"]
    pts = weapon_world(tf, W, wm.points(0.5))
    worst = (0.0, None)
    for bone, _parent, _pivot, cube in SK:
        if not cube:
            continue
        o, s, _c = cube
        lo, hi = np.array(o, float), np.array(o, float) + np.array(s, float)
        if bone in ("rightArm", "leftArm"):
            if bone == "leftArm" and not hold.get("arm_l"):
                pass
            # 握っている腕は肩から肘まで（拳の周りは握るので当たってよい）
            lo = np.array([o[0], 18.0, o[2]], float)
            hi = np.array([o[0] + s[0], 24.0, o[2] + s[2]], float)
        inf = _BODY_INFLATE.get(bone, 0.0)
        lo, hi = lo - inf, hi + inf
        inv = np.linalg.inv(W[bone])
        q = pts @ inv[:3, :3].T + inv[:3, 3]
        d = np.clip(np.minimum(q - lo, hi - q).min(axis=1), 0, None)
        m = float(d.max()) if len(d) else 0.0
        if m > worst[0]:
            worst = (m, bone)
    gap = None
    if hold.get("grip2") is not None and hold.get("arm_l") and not use:
        g2 = weapon_world(tf, W, np.array([hold["grip2"]], float))[0]
        gap = float(np.linalg.norm(g2 - _fist(hold["arm_l"], left=True)))
    return {"depth": round(worst[0], 2), "part": worst[1], "gap": None if gap is None else round(gap, 2)}


# ===========================================================================
#  書き出し（JSON の形）
# ===========================================================================
def anim_ids(key: str) -> Dict[str, str]:
    base = f"animation.nr.w.{key}"
    return {k: f"{base}.{k}" for k in ("tp", "fp", "tp_use", "fp_use", "idle")}


PRE_ANIMATION = [
    "v.nr_fp = c.is_first_person ? 1.0 : 0.0;",
    "v.nr_use = q.is_using_item ? 1.0 : 0.0;",
    "v.nr_usew = (v.nr_usew ?? 0.0) + (v.nr_use - (v.nr_usew ?? 0.0)) * math.min(1.0, q.delta_time * 10.0);",
]


def attachable_doc(key: str, ident: Optional[str] = None, geo: Optional[str] = None,
                   tex: Optional[str] = None, idle: bool = False) -> dict:
    """アタッチャブル（W1〜W4）。持ち方は tp / fp / tp_use / fp_use を重みで混ぜる（構えは q.is_using_item）。"""
    a = anim_ids(key)
    anims = {k: a[k] for k in ("tp", "fp", "tp_use", "fp_use")}
    animate = [{"tp": "(1.0 - v.nr_fp) * (1.0 - v.nr_usew)"}, {"tp_use": "(1.0 - v.nr_fp) * v.nr_usew"},
               {"fp": "v.nr_fp * (1.0 - v.nr_usew)"}, {"fp_use": "v.nr_fp * v.nr_usew"}]
    if idle:
        anims["idle"] = a["idle"]
        animate.append("idle")
    return {
        "format_version": ATT_FORMAT,
        "minecraft:attachable": {
            "description": {
                "identifier": ident or f"nr:w_{key}",
                "materials": {"default": "entity_emissive_alpha", "enchanted": "entity_alphatest_glint"},
                "textures": {"default": tex or f"{TEX_REL}/{key}", "enchanted": ENCHANT_GLINT},
                "geometry": {"default": geo or f"geometry.nr.w.{key}"},
                "animations": anims,
                "scripts": {"pre_animation": list(PRE_ANIMATION), "animate": animate},
                "render_controllers": ["controller.render.item_default"],
            }
        },
    }


def _tfj(t: dict) -> dict:
    s = float(t["scale"])
    return {"rotation": [round(float(x), 2) for x in t["rotation"]],
            "position": [round(float(x), 2) for x in t["position"]], "scale": [s, s, s]}


def hold_animation_doc(key: str, hold: dict, idle_bones: Optional[dict] = None) -> dict:
    """animation.nr.w.<key>.tp / fp / tp_use / fp_use（hold ボーンの変換を保つループ）と .idle。"""
    a = anim_ids(key)
    out = {}
    for k in ("tp", "fp", "tp_use", "fp_use"):
        out[a[k]] = {"loop": True, "bones": {"hold": _tfj(hold[k])}}
    if idle_bones:
        out[a["idle"]] = {"loop": True, "animation_length": 4.0, "bones": idle_bones}
    return {"format_version": ANIM_FORMAT, "animations": out}


_RARITY_ITEM = {"common": "common", "uncommon": "uncommon", "rare": "rare", "epic": "epic", "legendary": "epic"}
_ENCHANT_VALUE = {"common": 10, "uncommon": 12, "rare": 14, "epic": 16, "legendary": 18}
_AXE_KEYS = ("hatchet", "fire_axe", "sign_axe")


def vanilla_damage(w: dict) -> int:
    """minecraft:damage（バニラの敵・PvP 用の小さな値。ゾンビへの本当のダメージはスクリプトが spec から出す）。"""
    return int(max(1, min(11, round(w["damage"] * 0.55))))


def item_doc(w: dict, *, icon: Optional[str] = None, charge: bool = True, extra: Optional[dict] = None) -> dict:
    """BP のアイテム（content.md §3.6 の形、1.21.120）。"""
    key = w["key"]
    kind = w["kind"]
    tags = ["nr:weapon", f"nr:{kind}", f"nr:{w['anim_set']}", f"nr:{w['dtype']}", f"nr:{w['weight']}",
            f"nr:cls_{w['cls']}"]
    if w["cls"] in ("one_hand_blade", "two_hand_blade"):
        tags.insert(0, "minecraft:is_sword")
    group = None
    slot = "sword"
    if key in _AXE_KEYS:
        group, slot = "minecraft:itemGroup.name.axe", "axe"
    elif w["cls"] in ("one_hand_blade", "two_hand_blade"):
        group = "minecraft:itemGroup.name.sword"
    desc = {"identifier": w["id"], "menu_category": {"category": "equipment"}}
    if group:
        desc["menu_category"]["group"] = group
    comps = {
        "minecraft:icon": icon or f"nr_w_{key}",
        "minecraft:display_name": {"value": f"item.{w['id']}"},
        "minecraft:max_stack_size": 1,
        "minecraft:hand_equipped": True,
        "minecraft:durability": {"max_durability": int(w["durability"]), "damage_chance": {"min": 100, "max": 100}},
        "minecraft:damage": vanilla_damage(w),
        "minecraft:enchantable": {"slot": slot, "value": _ENCHANT_VALUE.get(w["rarity"], 10)},
        "minecraft:repairable": {"repair_items": [
            {"items": ["nr:scrap"], "repair_amount": "query.max_durability * 0.25"},
            {"items": [w["id"]], "repair_amount": "context.other->query.remaining_durability + 0.12 * context.other->query.max_durability"},
        ]},
        "minecraft:can_destroy_in_creative": False,
        "minecraft:swing_duration": {"value": round(float(np.clip(0.55 / max(0.3, w["attack_speed"]), 0.22, 0.85)), 2)},
        "minecraft:rarity": _RARITY_ITEM.get(w["rarity"], "common"),
        "minecraft:tags": {"tags": tags},
        "nr:weapon": {"key": key},
    }
    if charge:
        # 右クリック長押しで重攻撃を溜める（q.is_using_item → アタッチャブルの構え、スクリプトは itemReleaseUse）
        comps["minecraft:use_modifiers"] = {"use_duration": 30.0,
                                            "movement_modifier": 0.62 if w.get("hands", 1) == 1 else 0.48}
    if extra:
        comps.update(extra)
    return {"format_version": ITEM_FORMAT, "minecraft:item": {"description": desc, "components": comps}}


def recipe_doc(w: dict) -> Optional[dict]:
    """spec の作業台レシピ（shaped / shapeless）→ JSON。無ければ None。unlock は最初の nr: 材料（無ければ最初の材料）。"""
    r = w.get("recipe")
    if not r:
        return None
    rid = f"nr:craft_w_{w['key']}"
    if r["type"] == "shaped":
        refs = [r["keys"][ch] for row in r["pattern"] for ch in row if ch != " "]
        body = {"description": {"identifier": rid}, "tags": ["crafting_table"], "pattern": list(r["pattern"]),
                "key": {ch: {"item": it} for ch, it in sorted(r["keys"].items())}}
        kind = "minecraft:recipe_shaped"
    else:
        refs = [i for i, _n in r["ingredients"]]
        ings = []
        for it, n in r["ingredients"]:
            ings += [{"item": it}] * int(n)
        body = {"description": {"identifier": rid}, "tags": ["crafting_table"], "ingredients": ings}
        kind = "minecraft:recipe_shapeless"
    unlock = next((x for x in refs if x.startswith("nr:")), refs[0] if refs else None)
    if unlock:
        body["unlock"] = [{"item": unlock}]
    body["result"] = {"item": w["id"], "count": int(r.get("count", 1))}
    return {"format_version": RECIPE_FORMAT, kind: body}


class Frags:
    """item_texture / lang の断片を集めて最後に 1 回書く（DESIGN §1。producer = 生成器の名前）。"""

    def __init__(self, producer: str):
        self.producer = producer
        self.item_texture: Dict[str, dict] = {}
        self.lang = {"ja_JP": {}, "en_US": {}}

    def icon(self, tex_key: str, path_rel: str):
        self.item_texture[tex_key] = {"textures": path_rel}

    def name(self, ident: str, ja: str, en: str):
        for code, v in (("ja_JP", ja), ("en_US", en)):
            self.lang[code][f"item.{ident}"] = v
            self.lang[code][f"item.{ident}.name"] = v

    def text(self, k: str, ja: str, en: str):
        self.lang["ja_JP"][k] = ja
        self.lang["en_US"][k] = en

    def write(self):
        frag("item_texture", self.producer, dict(sorted(self.item_texture.items())))
        frag("lang", self.producer, {c: dict(sorted(v.items())) for c, v in self.lang.items()})


# ===========================================================================
#  プレビュー（nr_preview の包み）とアイコン
# ===========================================================================
def _geo_and_tex(wm: WeaponModel, tex: Image.Image):
    return NV.load_geometry(wm.geometry_doc()), np.asarray(tex.convert("RGBA"), np.uint8)


def icon_pose(wm: WeaponModel, flip: bool = False, roll: float = 0.0) -> dict:
    """アイコン用: 柄を左下、先を右上に（45°）。flip で刃の向きを反対に。roll（度）で武器を自分の軸まわりに
    回す（横 ±X に広がる爪・刃を正面に見せる。ピッチフォークは 90）。"""
    a = math.radians(45.0)
    fwd = np.array([0.0, math.sin(a), -math.cos(a)])
    up = np.array([0.0, math.cos(a), math.sin(a)])
    if flip:
        up = -up
    if roll:
        r = math.radians(roll)
        up = up * math.cos(r) + np.cross(fwd, up) * math.sin(r)
    return {"root": {"rotation": euler_of(frame(fwd, up))}}


def render_model(wm: WeaponModel, tex: Image.Image, view="three_quarter", size=(420, 260), pose=None,
                 bg=(30, 31, 36), ss=2, **kw) -> Image.Image:
    geo, t = _geo_and_tex(wm, tex)
    return NV.render(geo, t, view=view, size=size, pose=pose, bg=bg, ss=ss, cull=False, **kw)


def bake_icon(wm: WeaponModel, tex: Image.Image, size: int = ICON_SIZE, flip: bool = False,
              yaw: float = 72.0, pitch: float = 12.0, margin: float = 0.04, roll: float = 0.0) -> Image.Image:
    """3D モデルを斜め横から描いて、透過のアイコンにする（α は 0 / 255 の二値、縁に 1px の暗い輪郭）。"""
    geo, t = _geo_and_tex(wm, tex)
    cam = NV.Camera(yaw=yaw, pitch=pitch, margin=margin)
    big = NV.render(geo, t, camera=cam, size=size, pose=icon_pose(wm, flip, roll), bg=None, ss=6, cull=False,
                    light="studio")
    a = np.asarray(big, np.uint8).copy()
    alpha = a[..., 3] >= 96
    rgb = a[..., :3].astype(np.float32)
    # 縁取り: 透過の画素のうち、隣が不透明なら暗い輪郭（アイテム欄の背景で形が読めるように）
    nb = np.zeros_like(alpha)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nb |= np.roll(np.roll(alpha, dy, 0), dx, 1)
    outline = nb & ~alpha
    out = np.zeros_like(a)
    # 少しだけ締める（コントラストと彩度）
    rgb = np.clip((rgb - 128) * 1.08 + 128 + 4, 0, 255)
    out[alpha, :3] = rgb[alpha].astype(np.uint8)
    out[alpha, 3] = 255
    out[outline, :3] = (18, 16, 16)
    out[outline, 3] = 255
    return Image.fromarray(out, "RGBA")


def _player_parts(skin=(196, 150, 118), shirt=(60, 98, 120), pants=(48, 52, 86)):
    """プレビュー用のプレイヤー（hd_scene.SKELETON と同じ骨格）。色は (rgb) の単色。"""
    SK, _sw = _skeleton()
    cols = {"head": skin, "body": shirt, "rightArm": skin, "leftArm": skin, "rightLeg": pants, "leftLeg": pants}
    bones = []
    for name, parent, pivot, cube in SK:
        b = {"name": name, "pivot": list(pivot)}
        if parent:
            b["parent"] = parent
        if cube:
            o, s, _c = cube
            b["cubes"] = [{"origin": list(o), "size": list(s), "colour": cols.get(name, skin)}]
        bones.append(b)
    return bones


def _composite(wm: WeaponModel, tex: Image.Image, with_player=True):
    """プレイヤーと武器を 1 つのジオメトリにまとめる（hold を rightItem の子に）。テクスチャの下に色見本を足す。"""
    doc = wm.geometry_doc()
    g = json.loads(json.dumps(doc["minecraft:geometry"][0]))
    tw, th = g["description"]["texture_width"], g["description"]["texture_height"]
    extra = 8
    t = np.zeros((th + extra, tw, 4), np.uint8)
    t[:th] = np.asarray(tex.convert("RGBA"), np.uint8)
    bones = []
    swatch = {}
    if with_player:
        for b in _player_parts():
            for c in b.get("cubes", []):
                col = tuple(c.pop("colour"))
                if col not in swatch:
                    i = len(swatch)
                    swatch[col] = i
                    t[th:th + extra, i * 4:(i + 1) * 4, :3] = col
                    t[th:th + extra, i * 4:(i + 1) * 4, 3] = 255
                u = swatch[col] * 4 + 1
                c["uv"] = {f: {"uv": [u, th + 2], "uv_size": [2, 2]} for f in
                           ("north", "south", "east", "west", "up", "down")}
            bones.append(b)
    else:
        for name in ("rightArm", "rightItem"):
            pass
        from_sk, _ = _skeleton()
        for name, parent, pivot, _cube in from_sk:
            bb = {"name": name, "pivot": list(pivot)}
            if parent:
                bb["parent"] = parent
            bones.append(bb)
    # 武器のボーン名はプレイヤーの骨格（root など）と重なるので、hold 以外に接頭辞を付ける
    ren = {b["name"]: (b["name"] if b["name"] == "hold" else "wpn_" + b["name"]) for b in g["bones"]}
    for b in g["bones"]:
        b = dict(b)
        b["name"] = ren[b["name"]]
        if b.get("parent"):
            b["parent"] = ren.get(b["parent"], b["parent"])
        if b["name"] == "hold":
            b.pop("binding", None)
            b["parent"] = "rightItem"
        bones.append(b)
    g["bones"] = bones
    g["description"]["texture_height"] = th + extra
    return NV.load_geometry({"format_version": "1.16.0", "minecraft:geometry": [g]}), t


def render_held(wm: WeaponModel, tex: Image.Image, hold: dict, view=(150.0, 12.0), size=(320, 360),
                use=False, bg=(30, 31, 36)) -> Image.Image:
    """三人称の持ち姿勢（プレイヤーの骨格に付けて）。view は (yaw, pitch)（nr_preview の向き）。"""
    geo, t = _composite(wm, tex)
    tf = hold["tp_use" if use else "tp"]
    pose = {"rightArm": {"rotation": list(hold["arm_r"])},
            "hold": {"rotation": list(tf["rotation"]), "position": list(_v3(tf["position"]) + HS.OFF_R),
                     "scale": [tf["scale"]] * 3}}
    if hold.get("arm_l"):
        pose["leftArm"] = {"rotation": list(hold["arm_l"])}
    cam = NV.Camera(yaw=view[0], pitch=view[1], margin=0.05)
    return NV.render(geo, t, camera=cam, size=size, pose=pose, bg=bg, ss=2, cull=False)


def render_fp(wm: WeaponModel, tex: Image.Image, hold: dict, use=False, size=(480, 270), fov=70.0,
              bg=(64, 74, 90)) -> Image.Image:
    """一人称（目 (0,26,0) から +Z を見る。腕は FP_ARM_ROT、rightItem はバニラと同じく (0,0,-1) 動く）。"""
    geo, t = _composite(wm, tex, with_player=False)
    tf = hold["fp_use" if use else "fp"]
    pose = {"rightArm": {"rotation": list(HS.FP_ARM_ROT), "position": list(HS.FP_ARM_POS)},
            "rightItem": {"position": list(HH.FP_ITEM_OFF)},
            "hold": {"rotation": list(tf["rotation"]), "position": list(_v3(tf["position"]) + HS.OFF_R),
                     "scale": [tf["scale"]] * 3}}
    D = 200.0
    cam = NV.Camera(yaw=0.0, pitch=0.0, projection="persp", fov=fov / (size[0] / size[1]) * 1.0,
                    target=(0.0, 26.0, D), distance=D, scale=None, margin=0.0)
    # 画面の縦の画角を fov に（nr_preview の fov は縦）
    cam = NV.Camera(yaw=0.0, pitch=0.0, projection="persp", fov=fov, target=(0.0, 26.0, D), distance=D,
                    scale=(size[1] / 2) / math.tan(math.radians(fov / 2)), margin=0.0)
    return NV.render(geo, t, camera=cam, size=size, pose=pose, bg=bg, ss=2, cull=False)


def contact_sheet(items, cols=None, title=None) -> Image.Image:
    return NV.contact_sheet(items, cols=cols, title=title)


# ===========================================================================
#  まとめて書き出す
# ===========================================================================
def write_weapon(w: dict, wm: WeaponModel, tex: Image.Image, hold: dict, frags: Frags, *,
                 icon: Optional[Image.Image] = None, charge: bool = True, item_extra: Optional[dict] = None,
                 write_recipe: bool = True, icon_flip: bool = False) -> dict:
    """武器 1 つ分を全部書く。戻り値は {"geo", "texture", "icon", "attachable", "anim", "item", "recipe"}（パス）。"""
    key = w["key"]
    n = wm.cube_count
    if n > MAX_CUBES:
        raise ValueError(f"{key}: キューブ {n} 個（上限 {MAX_CUBES}）")
    if not wm.model.tex_w:
        wm.pack()
    if tex.size != (wm.model.tex_w, wm.model.tex_h):
        raise ValueError(f"{key}: テクスチャ {tex.size} とジオメトリ {wm.model.tex_w}x{wm.model.tex_h} が違う")
    out = {}
    p = os.path.join(GEO_DIR, f"{key}.geo.json")
    write_geometry(p, wm.model)
    out["geo"] = p
    p = os.path.join(RP, *TEX_REL.split("/"), f"{key}.png")
    NP.save_png(tex, p, quantize=True)
    out["texture"] = p
    ic = icon if icon is not None else bake_icon(wm, tex, flip=icon_flip)
    p = os.path.join(RP, *ICON_REL.split("/"), f"{key}.png")
    NP.save_png(ic, p, quantize=True)
    out["icon"] = p
    frags.icon(f"nr_w_{key}", f"{ICON_REL}/{key}")
    frags.name(w["id"], w["ja"], w["en"])
    p = os.path.join(ATT_DIR, f"{key}.attachable.json")
    write_json(p, attachable_doc(key, ident=w["id"], idle=bool(wm.idle)))
    out["attachable"] = p
    p = os.path.join(ANIM_DIR, f"{key}.animation.json")
    write_json(p, hold_animation_doc(key, hold, wm.idle or None))
    out["anim"] = p
    p = os.path.join(ITEM_DIR, f"{key}.item.json")
    write_json(p, item_doc(w, charge=charge, extra=item_extra))
    out["item"] = p
    r = recipe_doc(w) if write_recipe else None
    if r:
        p = os.path.join(RECIPE_DIR, f"{key}.recipe.json")
        write_json(p, r)
        out["recipe"] = p
    return out


def clean_outputs(keys: Iterable[str]) -> None:
    """前回の出力のうち、今回作らない武器のファイルを消す（名前を変えた武器の残骸を残さない）。
    keys は今回作る武器のキー。自分の置き場所の中だけ、自分の命名のファイルだけを消す。"""
    keep = set(keys)
    pats = [(GEO_DIR, ".geo.json"), (os.path.join(RP, *TEX_REL.split("/")), ".png"),
            (ATT_DIR, ".attachable.json"), (ANIM_DIR, ".animation.json"), (ITEM_DIR, ".item.json"),
            (RECIPE_DIR, ".recipe.json")]
    del keep, pats   # 近接と飛び道具で同じ置き場所を分け合うので、消すのは各生成器が自分の一覧で行う


def seed_of(key: str) -> int:
    return stable_hash("nr.w." + key) & 0x7FFFFFFF
