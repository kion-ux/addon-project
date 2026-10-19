# -*- coding: utf-8 -*-
"""アストロ・ナノギア — ナノウェポン／惑星コアのモデル補助と、アタッチャブル・アニメ・アイコンの書き出し。

惑星の担当者は planets/<key>/weapon.py でこのモジュールの補助を使ってモデルを組む
（説明と例は planets/_template/README_weapon.md と planets/earth/weapon.py）。

■ ボーンの構成（DESIGN.md §4.3）
    hold   手に bind（q.item_slot_to_bone_name(c.item_slot)）。持ち方（tp / fp）を受け持つ
     └ origin 握り = 原点（コアは球の中心）。振り・待機の揺れ
              （"root" はプレイヤーのボーン名なので使わない。プレイヤーと同じ名前のボーンは、
               アタッチャブルでもそのボーンに付いて動いてしまう — DESIGN.md §4.5）
        ├ form_0_grip    形成アニメ（持ち替えた瞬間に番号順にポップして現れる）の部品
        ├ form_1_guard     …キューブは必ずどれかの form_ ボーン（またはその子）に入れる
        ├ form_2_blade
        │  └ fx_spin_moon  回る部品（WEAPON_ANIMS で回し方を書く。書かなければ既定の回転）
        └ …
  origin の直下にキューブを置かない（形成アニメで消えないため validate_model が警告する）。
  ボーン名にプレイヤーのボーン名（root waist body head rightArm rightItem cape hat …）を使わない（RESERVED）。

■ 座標（武器空間）: 16 単位 = 1 ブロック。握りの中心 = 原点、刃先 = -Z、+Y = 刃の幅（片刃は -Y が刃）、
  +X = 刃の平の法線。回転は統合版の規則そのまま（astro_common の補助と同じ）。
  手に持った時の大きさは astro_hold.SPEC[kind]["scale"] 倍（剣なら 0.8 倍）。

■ 公開 API（モデル）
  new_model(identifier, max_atlas=(1024, 1024), uv_scale=4) -> Model   hold・origin ボーン入り
  root_of(m) -> Bone                                   origin ボーン（build_weapon(m, root) の root）
  part(m, parent, name, pivot=(0,0,0)) -> Bone        ただのボーン（名前の重複は例外）
  form(m, parent, index, name, pivot=(0,0,0)) -> Bone  form_<index>_<name>
  spin(m, parent, name, pivot=(0,0,0)) -> Bone         fx_spin_<name>
  glow(m, parent, name, pivot=(0,0,0)) -> Bone         fx_glow_<name>（WEAPON_ANIMS で脈動させる）
  sphere(bone, centre, r, style, **kw) -> [Cube]       角を落とした球（7 個）。惑星の球に
  ring(bone, centre, radius, n, seg, style, axis="y", ...)  輪（セグメントは必ず接線向き）
  globe_style(planet, emit=40, **kw) -> dict            球に惑星の模様を継ぎ目なく貼る塗り（kind "globe"）
  spin_expr(axis, speed) / pulse_expr(speed, amount)    WEAPON_ANIMS に書く回転・脈動のチャンネル
  blade_point(bone, z_base, half_w, z_tip, thick, style, **kw)  YZ 平面の切先（三角形を角柱で埋める）
  edge_line(bone, pts, w, h, style, **kw)               polyline の別名（発光の縁取り）
  再輸出: box cbox rbox plate beam polyline octa chamfer bevel ring tri_fan fill_tri_yz arc_points lerp
         （astro_common。回転は全て統合版の角度）

■ 公開 API（書き出し・検証）
  load_planet(key) -> module | None                    planets/<key>/weapon.py
  planet_kind(key, mod=None) -> str                     持ち方の種類（KIND が無ければ astro_data）
  build_models(key, mod=None) -> (weapon Model, core Model)   uv 密度を探してパック済み
  paint_model(m, styles, path, seed)                    astro_paint があればそのペインタで
  weapon_animations(key, geo, mod) / core_animations(key, geo, mod) -> {name: anim}
  form_controller() -> {controller name: controller}
  attachable(key, what, anim_names) -> dict             what = "weapon" | "core"
  make_icon(geo_path, tex_path, out_path, view=(yaw, pitch, turn), size=64, pose=None)
  validate_model(m, kind="weapon"|"core") -> [warning]
  preview(key, build=True) -> path                      build_preview/astro/weapon_<key>.png

python3 tools/astro/astro_weapon.py preview <key> [--no-build]
"""
from __future__ import annotations

import importlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import astro_animcheck as AK  # noqa: E402
import astro_common as AC  # noqa: E402
from astro_common import (arc_points, beam, bevel, box, cbox, chamfer, lerp, octa,  # noqa: E402,F401
                          plate, polyline, rbox, tri_fan, fill_tri_yz)
import astro_data as D  # noqa: E402
import astro_hold as AH  # noqa: E402
from mcmodel import Model  # noqa: E402

NS = D.NS
RP = AC.RP
SCRATCH = AC.SCRATCH
GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", NS)
ATT_DIR = os.path.join(RP, "attachables")
ICON_DIR = os.path.join(RP, "textures", "items", NS)

BIND = "q.item_slot_to_bone_name(c.item_slot)"
ORIGIN = "origin"
# プレイヤー（geometry.humanoid.custom と防具）のボーン名。アタッチャブルで同じ名前のボーンを作ると、
# そのボーンの変換に付いて動いてしまう（大文字小文字は区別しない）
RESERVED = {n.lower() for n in (
    "root", "waist", "body", "head", "hat", "helmet", "cape", "jacket", "bodyArmor", "belt",
    "rightArm", "leftArm", "rightSleeve", "leftSleeve", "rightItem", "leftItem", "rightArmArmor",
    "leftArmArmor", "rightLeg", "leftLeg", "rightPants", "leftPants", "rightSock", "leftSock",
    "rightLegging", "leftLegging", "rightBoot", "leftBoot")}
FORM_CTRL = f"controller.animation.{NS}.weapon_form"
RENDER_CTRL = f"controller.render.{NS}.weapon"

# 形成アニメの時間割（秒）
FORM_LEN = 0.6          # 最後の部品が収まるまで
FORM_POP = 0.22         # 1 部品のポップ（0 → 1.15 → 1.0）
FORM_START = 0.04

# 書き出す目安（README・検証）
BUDGET = {"weapon": (80, 320), "core": (30, 100)}   # v1.1: 細部を足したウェポン 180〜320・コア 40〜100


# ===========================================================================
#  モデルの補助
# ===========================================================================
def new_model(identifier: str, max_atlas=(1024, 1024), uv_scale: int = 4) -> Model:
    """hold（手に bind）→ origin（握り = 原点）入りの空のモデル。"""
    m = Model(identifier, uv_scale=uv_scale, visible_bounds=(4, 4), vb_offset=(0, 1.0, 0),
              max_atlas=tuple(max_atlas))
    m.bone("hold", (0, 0, 0), binding=BIND)
    m.bone(ORIGIN, (0, 0, 0), parent="hold")
    return m


def root_of(m: Model):
    """build_weapon(m, root) に渡す親ボーン（名前は origin）。"""
    return next(b for b in m.bones if b.name == ORIGIN)


def _bone_names(m):
    return {b.name for b in m.bones}


def part(m: Model, parent, name: str, pivot=(0, 0, 0), rotation=None):
    """parent（Bone か名前）の子ボーン。rotation はボーンの静止時の回転（統合版の角度）。
    回るボーンに静止の傾きを付けると、アニメの回転はその上に足される（傾いたまま首を振る歳差運動）。"""
    pname = parent if isinstance(parent, str) else parent.name
    if name.lower() in RESERVED:
        raise ValueError(f"{m.identifier}: bone name {name!r} is a player bone name (reserved)")
    if name in _bone_names(m):
        raise ValueError(f"{m.identifier}: duplicate bone {name}")
    if pname not in _bone_names(m):
        raise ValueError(f"{m.identifier}: unknown parent bone {pname}")
    rot_ = [round(float(a), 2) for a in rotation] if rotation is not None and any(rotation) else None
    return m.bone(name, tuple(pivot), parent=pname, rotation=rot_)


def form(m: Model, parent, index: int, name: str, pivot=(0, 0, 0), rotation=None):
    """形成アニメの部品ボーン form_<index>_<name>。番号の小さい順に現れる（同じ番号は同時）。
    pivot は「生えてくる根元」（刃なら鍔の位置）。"""
    if not (0 <= int(index) <= 9):
        raise ValueError("form index must be 0..9")
    return part(m, parent, f"form_{int(index)}_{name}", pivot, rotation)


def spin(m: Model, parent, name: str, pivot=(0, 0, 0), rotation=None):
    """回る部品 fx_spin_<name>。回し方は WEAPON_ANIMS / CORE_ANIMS（無ければ既定の回転）。"""
    return part(m, parent, f"fx_spin_{name}", pivot, rotation)


def glow(m: Model, parent, name: str, pivot=(0, 0, 0), rotation=None):
    """脈動する発光部品 fx_glow_<name>（既定で 1.0〜1.06 倍にゆっくり脈打つ）。"""
    return part(m, parent, f"fx_glow_{name}", pivot, rotation)


def ring(bone, centre, radius, n, seg, style, axis="y", phase=0.0, a0=0.0, a1=360.0,
         styles=None, **kw):
    """軸 axis まわりの輪を n 個のセグメントで（astro_common.ring と同じ引数・同じ角度の向き）。
    seg = (接線方向の長さ（0 で隙間なく繋がる長さ）, 半径方向の厚み, 軸方向の幅)。styles で交互に塗る。
      axis="y": 水平の輪（XZ 平面）。a=0 で -Z（前）、a=90 で -X
      axis="z": 正面向きの輪（XY 平面）。a=0 で +Y（上）、a=90 で -X
      axis="x": 側面の輪（YZ 平面）。a=0 で +Y（上）、a=90 で -Z
    セグメントは必ず接線の向きに置く（各セグメントの向きを回転行列から解く）。"""
    out = []
    full = abs(a1 - a0) >= 359.9
    count = n if full else n + 1
    step = (a1 - a0) / (n if full else max(1, n))
    tl = seg[0] if seg[0] else 2 * radius * math.tan(math.radians(abs(step) / 2)) + 0.05
    cx, cy, cz = centre
    for i in range(count):
        a = a0 + phase + i * step
        t = math.radians(a)
        st = styles[i % len(styles)] if styles else style
        if axis == "y":
            p = (cx - radius * math.sin(t), cy, cz - radius * math.cos(t))
            tan = (-math.cos(t), 0.0, math.sin(t))
            rad = (-math.sin(t), 0.0, -math.cos(t))
        elif axis == "z":
            p = (cx - radius * math.sin(t), cy + radius * math.cos(t), cz)
            tan = (-math.cos(t), -math.sin(t), 0.0)
            rad = (-math.sin(t), math.cos(t), 0.0)
        else:
            p = (cx, cy + radius * math.cos(t), cz - radius * math.sin(t))
            tan = (0.0, -math.sin(t), -math.cos(t))
            rad = (0.0, math.cos(t), -math.sin(t))
        # 局所 X = 接線、局所 Y = 半径方向、局所 Z = 輪の軸
        ax = np.cross(tan, rad)
        R = np.column_stack([tan, rad, ax])
        out.append(AC.mat_cube(bone, p, (tl, seg[1], seg[2]), st, R, **kw))
    return out


def sphere(bone, centre, r: float, style: str, **kw):
    """角を落とした球（中心の立方体 + 3 方向の板 + 各軸まわりに 45° 回した板）。7 個。
    比率は外形の丸さ（どの向きから見ても半径 r に近い）を数値で探して決めた。
    惑星の模様は style に globe_style(...) を使うと継ぎ目なく貼れる。"""
    c = tuple(centre)
    d = 2 * r
    out = [cbox(bone, c, (d * 0.66,) * 3, style, **kw)]
    for axis in ("x", "y", "z"):
        size = [d * 0.46] * 3
        size[AC.AX[axis]] = d
        out.append(cbox(bone, c, size, style, **kw))
    for axis, r_ in (("x", (45, 0, 0)), ("y", (0, 45, 0)), ("z", (0, 0, 45))):
        size = [d * 0.66] * 3
        size[AC.AX[axis]] = d * 0.86
        out.append(rbox(bone, c, size, style, rot=r_, **kw))
    return out


def blade_point(bone, z_base: float, half_w: float, z_tip: float, thick: float, style: str,
                layer: float = 0.9, y0: float = 0.0, **kw):
    """YZ 平面の切先: 底辺 (y0±half_w, z_base) から頂点 (y0, z_tip) の三角形を、両辺に平行な角柱で埋める。"""
    apex = (0, y0, z_tip)
    out = []
    for s in (-1, 1):
        out += fill_tri_yz(bone, apex, (0, y0 + s * half_w, z_base), (0, y0 - s * half_w, z_base),
                           thick, layer, style, **kw)
    return out


def edge_line(bone, pts, w, h, style, **kw):
    return polyline(bone, pts, w, h, style, **kw)


def validate_model(m: Model, kind: str = "weapon", quiet: bool = False) -> list:
    """命名と構成の検査（警告のリスト）。"""
    warn = []
    names = [b.name for b in m.bones]
    byname = {b.name: b for b in m.bones}
    if names[:2] != ["hold", ORIGIN]:
        warn.append(f"first bones must be hold, {ORIGIN}")
    if byname[ORIGIN].cubes:
        warn.append(f"{ORIGIN} has cubes (put them in form_<n>_<name> bones so the forming animation shows them)")
    for n in names:
        if n.lower() in RESERVED:
            warn.append(f"bone {n} uses a player bone name (it would follow the player's {n})")
    forms = [n for n in names if n.startswith("form_")]
    if kind == "weapon" and not forms:
        warn.append("no form_<n>_<name> bones (no forming animation)")
    for n in forms:
        p = n.split("_")
        if len(p) < 3 or not p[1].isdigit():
            warn.append(f"bad form bone name {n} (form_<digit>_<name>)")

    def under_form(b):
        while b is not None:
            if b.name.startswith("form_"):
                return True
            b = byname.get(b.parent) if b.parent else None
        return False
    if forms:
        loose = [b.name for b in m.bones if b.cubes and not under_form(b)]
        if loose:
            warn.append(f"cubes outside form_ bones: {', '.join(loose)}")
    n = len(m.all_cubes())
    lo, hi = BUDGET[kind]
    if not (lo <= n <= hi):
        warn.append(f"{n} cubes (budget {lo}-{hi})")
    if not quiet:
        for w in warn:
            print(f"  WARN {m.identifier}: {w}")
    return warn


# ===========================================================================
#  惑星パッケージ
# ===========================================================================
def planet_keys_with_weapon():
    out = []
    for key in D.PLANET_KEYS:
        if os.path.exists(os.path.join(AC.PLANETS_DIR, key, "weapon.py")):
            out.append(key)
    return out


def load_planet(key: str):
    """planets/<key>/weapon.py（無ければ None）。"""
    if not os.path.exists(os.path.join(AC.PLANETS_DIR, key, "weapon.py")):
        return None
    return importlib.import_module(f"planets.{key}.weapon")


def planet_kind(key: str, mod=None) -> str:
    mod = mod if mod is not None else load_planet(key)
    k = getattr(mod, "KIND", None) if mod else None
    return k or D.PLANETS[key]["weapon"]["kind"]


def planet_hold(key: str, what: str = "weapon", mod=None) -> dict:
    """weapon.py の HOLD / CORE_HOLD（scale・anchor・tp・fp の上書き）を足した持ち方。"""
    mod = mod if mod is not None else load_planet(key)
    if what == "core":
        over = dict(getattr(mod, "CORE_HOLD", {}) or {}) if mod else {}
        return AH.hold("core", **over)
    over = dict(getattr(mod, "HOLD", {}) or {}) if mod else {}
    return AH.hold(planet_kind(key, mod), **over)


def _density(m: Model, base: int, max_atlas):
    """テクセル密度: できるだけ上げ、max_atlas に収まる最大の倍率を選ぶ（hyperdim と同じ探索）。"""
    m.max_atlas = tuple(max_atlas)
    orig = {id(c): (c.uv_scale or base) for c in m.all_cubes()}
    for k in (2.5, 2.25, 2.0, 1.75, 1.5, 1.25, 1.0, 0.75, 0.5):
        for c in m.all_cubes():
            if c.fixed:
                continue
            c.uv_scale = max(1, int(round(orig[id(c)] * k)))
            c._scale = c.uv_scale
            c.uv = None
        m.uv_scale = max(1, int(round(base * k)))
        try:
            m.pack()
            m.texel_k = k
            return m
        except ValueError:
            continue
    raise ValueError(f"{m.identifier}: does not fit in {max_atlas}")


def build_models(key: str, mod=None):
    """(ウェポン, コア) のモデル。両方 uv を詰めた状態で返す。"""
    mod = mod if mod is not None else load_planet(key)
    if mod is None:
        raise FileNotFoundError(f"planets/{key}/weapon.py")
    w = new_model(f"geometry.{NS}.weapon_{key}", max_atlas=(1024, 1024))
    mod.build_weapon(w, root_of(w))
    _density(w, getattr(mod, "UV_SCALE", 4), (1024, 1024))
    c = new_model(f"geometry.{NS}.core_{key}", max_atlas=(512, 512))
    c.visible_bounds = (2, 2)
    mod.build_core(c, root_of(c))
    _density(c, getattr(mod, "CORE_UV_SCALE", 6), (512, 512))
    return w, c


def _styles(mod, name, key):
    st = getattr(mod, name)
    return st(key) if callable(st) else st


def _base_painter():
    try:
        import astro_paint as AP
        return getattr(AP, "AstroPainter")
    except (ImportError, AttributeError):
        from hd_paint import HDPainter
        return HDPainter


_PAINTER = None


def painter_class():
    """astro_paint.AstroPainter（無ければ hd_paint.HDPainter）に、ウェポン用の素材を足したペインタ。

    追加の kind:
      globe   箱を重ねた球（sphere()）に、継ぎ目なく惑星の模様を貼る。テクセルごとに 3D の点へ戻し、
              箱の中心からの向き（経度・緯度）で astro_paint.planet_color を引く。
              planet="earth" 等 / emit（アルファ。低いほど発光、255 で発光なし）/ spin（経度のずれ 度）/
              halo（面の縁を染める大気の色。None で無し）/ shade（極に向かう陰 0..1）
    """
    global _PAINTER
    if _PAINTER is not None:
        return _PAINTER
    Base = _base_painter()

    class WeaponPainter(Base):
        def paint_model(self, model, styles):
            self._cubes = {}
            for i, cube in enumerate(model.all_cubes()):
                self._cubes[i] = cube
            return super().paint_model(model, styles)

        def p_globe(self, st, c):
            import hd_scene as S
            from hd_space import rot
            cube = c.get("cube") or getattr(self, "_cubes", {}).get(c["key"])
            o = np.asarray(cube.origin, float)
            sz = np.asarray(cube.size, float)
            inf = float(cube.inflate or 0.0)
            a, b = o - inf, o + sz + inf
            P = [np.asarray(v, float) for v in S.FACES[c["face"]](a, b)]
            centre = o + sz / 2
            R = rot(*cube.rotation) if cube.rotation else np.eye(3)
            c["g"] = (P[0], P[1] - P[0], P[3] - P[0], centre, R)

        def k_globe(self, x, y, st, c):
            from astro_paint import ATMOS, planet_color
            P0, du, dv, centre, R = c["g"]
            w, h = c["w"], c["h"]
            p = P0 + du * ((x + 0.5) / w) + dv * ((y + 0.5) / h)
            d = R @ (p - centre)
            n = float(np.linalg.norm(d)) or 1.0
            d = d / n
            name = st.get("planet", "earth")
            lon = math.atan2(d[0], d[2]) + math.radians(st.get("spin", 0))
            lat = math.asin(max(-1.0, min(1.0, d[1])))
            q = (math.cos(lat) * math.sin(lon), math.sin(lat), math.cos(lat) * math.cos(lon))
            col = planet_color(name, lon, lat, q, 0)
            k = st.get("shade", 0.18)
            f = 1.0 - k * abs(d[1]) ** 2
            col = (col[0] * f, col[1] * f, col[2] * f)
            halo = st.get("halo", ATMOS.get(name))
            edge = min(x, y, w - 1 - x, h - 1 - y)
            if halo is not None and edge == 0 and min(w, h) >= 4:
                col = tuple(col[i] + (halo[i] - col[i]) * 0.22 for i in range(3))
            col = tuple(int(max(0, min(255, v))) for v in col)
            return col, st.get("emit", 255)

    _PAINTER = WeaponPainter
    return _PAINTER


def globe_style(planet: str, emit: int = 40, **kw) -> dict:
    """sphere() で作った球に惑星の模様を継ぎ目なく貼るスタイル（kind "globe"）。emit=255 で発光なし。"""
    d = {"kind": "globe", "planet": planet, "emit": emit, "bevel": False, "outline": False}
    d.update(kw)
    return d


def paint_model(m: Model, styles: dict, path: str, seed: int = 0) -> None:
    P = painter_class()
    p = P(m.tex_w, m.tex_h, seed)
    p.paint_model(m, styles)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    p.save(path)


# ===========================================================================
#  アニメーション
# ===========================================================================
def _r(v):
    return round(float(v), 3)


def _num(x):
    s = f"{x:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _ts(t):
    s = f"{t:.3f}".rstrip("0").rstrip(".")
    return s if "." in s else s + ".0"


def geo_bones(geo) -> list:
    """geo: Model か geometry の dict（"bones" を持つ）。ボーンの dict のリスト。"""
    if isinstance(geo, Model):
        return [b.to_json() for b in geo.bones]
    return geo["bones"]


def form_bones(geo):
    out = []
    for b in geo_bones(geo):
        n = b["name"]
        if n.startswith("form_"):
            p = n.split("_")
            if len(p) >= 3 and p[1].isdigit():
                out.append((int(p[1]), n))
    return sorted(out)


def form_animation(geo, axes=None, length=FORM_LEN) -> dict:
    """form_<n>_<name> を番号順に 0 → 1.15 → 1.0 でポップさせる（一回きり）。
    axes = {ボーン名: "z"} なら、そのボーンは z 方向へ伸びる（刃が鍔から伸びる）。"""
    axes = axes or {}
    fb = form_bones(geo)
    idx = sorted({i for i, _ in fb})
    rank = {i: r for r, i in enumerate(idx)}
    n = max(1, len(idx) - 1)
    gap = (length - FORM_POP - FORM_START) / n if len(idx) > 1 else 0.0
    bones = {}
    for i, name in fb:
        t0 = FORM_START + rank[i] * gap
        t1, t2 = t0 + FORM_POP * 0.6, t0 + FORM_POP
        ax = axes.get(name)
        if ax in ("x", "y", "z"):
            k = AC.AX[ax]

            def v(main, side):
                out = [side, side, side]
                out[k] = main
                return [_r(x) for x in out]
            keys = {"0.0": v(0, 0), _ts(t0): v(0, 0.35), _ts(t1): v(1.15, 1.08), _ts(t2): v(1.0, 1.0)}
        else:
            keys = {"0.0": [0, 0, 0], _ts(t0): [0, 0, 0], _ts(t1): [1.15, 1.15, 1.15], _ts(t2): [1, 1, 1]}
        bones[name] = {"scale": keys}
    end = max([FORM_START + rank[i] * gap + FORM_POP for i, _ in fb] or [length])
    # 一回きり: 最後のコマで止め、コントローラが q.all_animations_finished で ready へ
    return {"loop": "hold_on_last_frame", "animation_length": _r(end + 0.02), "bones": bones}


def _merge(dst: dict, src: dict) -> dict:
    """{bone: {channel: value}} を足す（同じボーン・チャンネルは src が勝つ）。"""
    for bone, ch in (src or {}).items():
        dst.setdefault(bone, {}).update(ch)
    return dst


def spin_expr(axis="z", speed=90.0, phase=0.0):
    """回転のチャンネル（{"rotation": [...]}）。speed は度/秒。待機ループの長さは全部の速さから自動で決まる
    （idle_loop_length。どの速さでも継ぎ目で飛ばない。整数の度/秒にしておくとループが短くて済む）。"""
    e = f"q.anim_time * {_num(speed)}" + (f" + {_num(phase)}" if phase else "")
    v = [0, 0, 0]
    v[AC.AX[axis]] = e
    return {"rotation": v}


def pulse_expr(speed=180.0, amount=0.06, base=1.0):
    return {"scale": f"{_num(base)} + math.sin(q.anim_time * {_num(speed)}) * {_num(amount)}"}


# 振り（攻撃のたびに v.astro_sw が 0→1）の形: 速く振り抜いてゆっくり戻る
CUT = "math.sin(math.pow(v.astro_sw, 0.6) * 180.0)"
WIND = "math.sin(v.astro_sw * 360.0)"
# 種類ごとの手首の返し（三人称 / 一人称の角度）。正の rx で刃先が -Y（刃の側）へ倒れる
SWING = {
    "saber": {"rx": (38, 70), "ry": (0, 10)},
    "sword": {"rx": (34, 66), "ry": (0, 8)},
    "greatsword": {"rx": (26, 52), "ry": (0, 6)},
    "scepter": {"rx": (22, 40), "ry": (0, 0)},
    "axe": {"rx": (40, 64), "ry": (0, 0)},
    "hammer": {"rx": (40, 60), "ry": (0, 0)},
    "ring": {"rx": (30, 54), "ry": (0, 0)},
    "crossbow": {"rx": (-14, -18), "pz": (1.5, 2.5)},
    "trident": {"rx": (8, 12), "pz": (-4.0, -6.0)},
    "core": {"rx": (0, 0)},
}


def _sel(tp, fp):
    if abs(tp - fp) < 1e-6:
        return _num(tp)
    return f"(v.astro_fp > 0.5 ? {_num(fp)} : {_num(tp)})"


def swing_channels(kind: str, over=None) -> dict:
    """origin ボーンの振り（手首の返し）。over = WEAPON_ANIMS["swing_root"]（{"rx": (三人称, 一人称), "ry": …,
    "pz": …}）で種類の既定を上書きできる。"""
    s = dict(SWING.get(kind, SWING["sword"]), **(over or {}))
    ch = {}
    rx = s.get("rx", (0, 0))
    ry = s.get("ry", (0, 0))
    rot = [0, 0, 0]
    if any(rx):
        # 少し引いてから振り抜く（一人称は大きく画面を横切る）
        rot[0] = f"{_sel(*rx)} * ({CUT} - 0.18 * {WIND})"
    if any(ry):
        rot[1] = f"{_sel(*ry)} * {CUT}"
    if any(rot):
        ch["rotation"] = rot
    if "pz" in s:
        ch["position"] = [0, 0, f"{_sel(*s['pz'])} * math.sin(v.astro_sw * 180.0)"]
    return ch


def _default_spins(geo, axis, speed, have):
    out = {}
    k = 0
    for b in geo_bones(geo):
        n = b["name"]
        if n.startswith("fx_spin_") and n not in have:
            sgn = 1 if k % 2 == 0 else -1
            out[n] = spin_expr(axis, speed * sgn)
            k += 1
        elif n.startswith("fx_glow_") and n not in have:
            out[n] = pulse_expr(150.0 + 20 * k, 0.06)
    return out


def anim_base(what, key):
    return f"animation.{NS}.{what}.{key}"


def _tf(d):
    s = d["scale"]
    return {"rotation": [_r(v) for v in d["rotation"]], "position": [_r(v) for v in d["position"]],
            "scale": _r(s)}


def weapon_animations(key: str, geo, mod=None) -> dict:
    """ウェポン 1 本分のアニメ: tp / fp / idle / swing / form。"""
    mod = mod if mod is not None else load_planet(key)
    kind = planet_kind(key, mod)
    h = planet_hold(key, "weapon", mod)
    WA = dict(getattr(mod, "WEAPON_ANIMS", {}) or {})
    base = anim_base("weapon", key)
    A = {}
    A[f"{base}.tp"] = {"loop": True, "bones": {"hold": _tf(h["tp"])}}
    A[f"{base}.fp"] = {"loop": True, "bones": {"hold": _tf(h["fp"])}}
    idle = {ORIGIN: {"position": [0, "math.sin(q.anim_time * 90.0) * 0.1", 0]}}
    have = set(WA.get("idle", {}))
    _merge(idle, _default_spins(geo, "z", 120.0, have))
    _merge(idle, WA.get("idle", {}))
    A[f"{base}.idle"] = {"loop": True, "animation_length": idle_loop_length(idle, WA, f"{key} weapon"),
                         "bones": idle}
    ch = swing_channels(kind, WA.get("swing_root"))
    sw = {ORIGIN: ch} if ch else {}
    _merge(sw, WA.get("swing", {}))
    A[f"{base}.swing"] = {"loop": True, "bones": sw}
    A[f"{base}.form"] = form_animation(geo, WA.get("form_axes", getattr(mod, "FORM_AXES", None)))
    return A


def core_animations(key: str, geo, mod=None) -> dict:
    """コア 1 個分のアニメ: tp / fp / idle / use（右クリック中にリングが速く回る）/ form。"""
    mod = mod if mod is not None else load_planet(key)
    h = planet_hold(key, "core", mod)
    CA = dict(getattr(mod, "CORE_ANIMS", {}) or {})
    base = anim_base("core", key)
    A = {}
    A[f"{base}.tp"] = {"loop": True, "bones": {"hold": _tf(h["tp"])}}
    A[f"{base}.fp"] = {"loop": True, "bones": {"hold": _tf(h["fp"])}}
    idle = {ORIGIN: {"position": [0, "math.sin(q.anim_time * 110.0) * 0.35", 0],
                     "rotation": [0, "math.sin(q.anim_time * 40.0) * 8.0", 0]}}
    have = set(CA.get("idle", {}))
    _merge(idle, _default_spins(geo, "y", 90.0, have))
    _merge(idle, CA.get("idle", {}))
    A[f"{base}.idle"] = {"loop": True, "animation_length": idle_loop_length(idle, CA, f"{key} core"),
                         "bones": idle}
    use = {ORIGIN: {"scale": "1.0 + v.astro_usew * 0.12",
                    "position": [0, "v.astro_usew * 1.2", 0]}}
    k = 0
    for b in geo_bones(geo):
        if b["name"].startswith("fx_spin_"):
            sgn = 1 if k % 2 == 0 else -1
            # v.astro_usespin は PRE_CORE が速さ 360°/秒 × v.astro_usew で積み上げる角度（0〜360）。
            # q.anim_time × 重みだと、重みが 0〜1 の途中でループが戻った時に輪が飛ぶ
            use[b["name"]] = {"rotation": [0, f"{'' if sgn > 0 else '-'}v.astro_usespin", 0]}
            k += 1
    _merge(use, CA.get("use", {}))
    A[f"{base}.use"] = {"loop": True, "bones": use}
    if form_bones(geo):
        A[f"{base}.form"] = form_animation(geo, CA.get("form_axes"), length=0.45)
    return A


def idle_loop_length(bones, anims_cfg, where="") -> float:
    """待機ループ（loop: true + animation_length）の長さ: 全ての `q.anim_time * 速さ` が 1 周期で 360° の整数倍に
    なる最短の長さ（idle_length 以上。既定 6 秒）。統合版は animation_length ごとに q.anim_time を 0 に戻すので、
    合わない速さの部品は毎周期ぱっと飛ぶ（DESIGN.md §4.5）。"""
    try:
        return AK.loop_length(bones, float(anims_cfg.get("idle_length", 6.0)))
    except ValueError as exc:
        raise ValueError(f"{where} idle: {exc}") from None


def render_controller() -> dict:
    """片面の既定（閉じた箱）と、fx_* ボーンだけ両面の発光（DESIGN.md §4.5）。"""
    return {RENDER_CTRL: {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}, {"fx_*": "Material.fx"}],
        "textures": ["Texture.default"],
    }}


def form_controller() -> dict:
    return {FORM_CTRL: {
        "initial_state": "form",
        "states": {
            # インベントリの人形（q.is_in_ui。素の q.* は持ち主を評価する）では形成を飛ばす
            "form": {"animations": ["form"],
                     "transitions": [{"ready": "q.all_animations_finished || q.is_in_ui"}]},
            "ready": {},
        },
    }}


PRE = [
    "v.astro_sw = math.clamp(c.owning_entity->v.attack_time, 0.0, 1.0);",
    "v.astro_fp = c.is_first_person ? 1.0 : 0.0;",
    "v.astro_use = q.is_using_item ? 1.0 : 0.0;",
    "v.astro_usew = (v.astro_usew ?? 0.0) + (v.astro_use - (v.astro_usew ?? 0.0)) * "
    "math.min(1.0, q.delta_time * 10.0);",
]


PRE_CORE = [
    "v.astro_usespin = math.mod((v.astro_usespin ?? 0.0) + q.delta_time * 360.0 * v.astro_usew, 360.0);",
]


def attachable(key: str, what: str, anims: dict) -> dict:
    """what = "weapon" | "core"。anims は書き出すアニメの dict（名前の確認に使う）。"""
    base = anim_base(what, key)
    keys = {"tp": f"{base}.tp", "fp": f"{base}.fp", "idle": f"{base}.idle"}
    animate = [{"tp": "1.0 - v.astro_fp"}, {"fp": "v.astro_fp"}, "idle"]
    if f"{base}.swing" in anims:
        keys["swing"] = f"{base}.swing"
        animate.append({"swing": "v.astro_sw > 0.0"})
    if f"{base}.use" in anims:
        keys["use"] = f"{base}.use"
        animate.append({"use": "v.astro_usew > 0.01"})
    if f"{base}.form" in anims:
        keys["form"] = f"{base}.form"
        keys["ctrl"] = FORM_CTRL
        animate.append("ctrl")
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": f"{NS}:{what}_{key}",
                # 閉じた箱は片面（裏面を描かない）、fx_* ボーン（回る輪・薄い板）は両面
                "materials": {"default": "entity_emissive_alpha_one_sided", "fx": "entity_emissive_alpha"},
                "textures": {"default": f"textures/entity/{NS}/{what}_{key}"},
                "geometry": {"default": f"geometry.{NS}.{what}_{key}"},
                "animations": keys,
                "scripts": {"pre_animation": list(PRE) + (list(PRE_CORE) if what == "core" else []),
                            "animate": animate},
                "render_controllers": [RENDER_CTRL],
            }
        },
    }


# ===========================================================================
#  アイコン（64x64、透過、くっきりした輪郭）
# ===========================================================================
ICON_VIEW = {
    "saber": (90, 0, 45), "sword": (90, 0, 45), "greatsword": (90, 0, 45), "scepter": (90, 0, 45),
    "axe": (90, 0, 45), "hammer": (90, 0, 45), "ring": (90, -10, 0), "crossbow": (60, -25, 20),
    "trident": (90, 0, 45), "core": (25, -18, 0),
}


def make_icon(geo_path, tex_path, out_path, view=(90, 0, 45), size=64, pose=None, hide=(),
              outline=(10, 9, 18), margin=1):
    """モデルを描いて size x size のアイコンに（hyperdim の make_icon を 64px にしたもの）。
    view = (yaw, pitch, 画面上の回転)。輪郭は不透明部分を 1px 太らせた暗い縁。"""
    from PIL import Image, ImageFilter
    from hd_preview import render
    yaw, pitch, turn = view
    big = render(geo_path, tex_path, 512, yaw, pitch, 0, margin=0.02, bg=(0, 0, 0, 0), ss=2,
                 hide=hide, pose=pose)
    if turn:
        big = big.rotate(turn, resample=Image.BICUBIC, expand=True)
    big = big.crop(big.getbbox())
    side = max(big.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(big, ((side - big.size[0]) // 2, (side - big.size[1]) // 2))
    inner = size - 2 * (margin + 1)
    im = sq.resize((inner, inner), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(im, (margin + 1, margin + 1))
    a = canvas.split()[3].point(lambda v: 255 if v > 96 else 0)
    canvas.putalpha(a)
    ring_ = Image.new("RGBA", canvas.size, tuple(outline) + (255,))
    ring_.putalpha(a.filter(ImageFilter.MaxFilter(3)))
    ring_.alpha_composite(canvas)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    ring_.save(out_path)
    return ring_


def icon_view(key, what, mod=None):
    mod = mod if mod is not None else load_planet(key)
    icon = dict(getattr(mod, "ICON", {}) or {}) if mod else {}
    if what in icon:
        return tuple(icon[what])
    return ICON_VIEW["core" if what == "core" else planet_kind(key, mod)]


# ===========================================================================
#  プレビュー
# ===========================================================================
def paths(key, what):
    return (os.path.join(GEO_DIR, f"{NS}_{what}_{key}.geo.json"),
            os.path.join(TEX_DIR, f"{what}_{key}.png"),
            os.path.join(ICON_DIR, f"{what}_{key}.png"))


def _label(img, text, sub=None, xy=(10, 8)):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.text(xy, text, fill=(240, 240, 250))
    if sub:
        d.text((xy[0], xy[1] + 14), sub, fill=(150, 156, 176))


def preview(key: str, build: bool = True, swing: bool = False) -> str:
    """ウェポン（4 方向）・コア（4 方向）・手に持った姿（三人称 2 / 一人称）・アイコンを 1 枚に。"""
    from PIL import Image
    import hd_scene as S
    from hd_preview import render
    if build:
        import gen_astro_weapons as G
        G.main([key])
    mod = load_planet(key)
    gw, tw, iw = paths(key, "weapon")
    gc, tc, ic = paths(key, "core")
    T = 300
    rows = []
    # 1. ウェポン単体
    tiles = [render(gw, tw, T, yaw, pitch, ss=2, bg=(22, 24, 32, 255))
             for yaw, pitch in ((90, -6), (35, -22), (150, -12), (0, -80))]
    row = Image.new("RGB", (T * 4, T), (14, 15, 20))
    for i, t in enumerate(tiles):
        row.paste(t.convert("RGB"), (i * T, 0))
    pl = D.PLANETS[key]
    _label(row, f"{pl['weapon']['en']}  ({planet_kind(key, mod)})")
    rows.append(row)
    # 2. コア単体
    tiles = [render(gc, tc, T, yaw, pitch, ss=2, bg=(22, 24, 32, 255))
             for yaw, pitch in ((25, -18), (90, 0), (200, -30), (0, -85))]
    row = Image.new("RGB", (T * 4, T), (14, 15, 20))
    for i, t in enumerate(tiles):
        row.paste(t.convert("RGB"), (i * T, 0))
    _label(row, f"{pl['core_en']}")
    rows.append(row)
    # 3. 手に持った姿（ウェポン: 三人称 2 + 一人称 / コア: 三人称 + 一人称）
    hw = planet_hold(key, "weapon", mod)
    hc = planet_hold(key, "core", mod)
    row = Image.new("RGB", (T * 4, T), (14, 15, 20))
    for i, (g, t, h, yaw) in enumerate(((gw, tw, hw, 205), (gw, tw, hw, 330), (gc, tc, hc, 210))):
        a = {"hold": {"rotation": h["tp"]["rotation"], "position": h["tp"]["position"],
                      "scale": (h["tp"]["scale"],) * 3}}
        im = S.tp(g, t, {"rightArm": {"rotation": h["arm_r"]}}, a, yaw=yaw, pitch=-10,
                  size=(T, T), scale=6.4, centre=(0, 15, -4))
        row.paste(im, (i * T, 0))
    _label(row, "third person (weapon x2, core)")
    fpw = _fp_tile(gw, tw, hw, (T, T // 2))
    fpc = _fp_tile(gc, tc, hc, (T, T // 2))
    row.paste(fpw, (3 * T, 0))
    row.paste(fpc, (3 * T, T // 2))
    rows.append(row)
    # 4. アイコン（等倍・4 倍）と振りのコマ（一人称）
    row = Image.new("RGB", (T * 4, T), (14, 15, 20))
    x = 12
    for p in (iw, ic):
        im = Image.open(p).convert("RGBA")
        bg = Image.new("RGBA", (256 + 16, 256 + 16), (40, 42, 54, 255))
        bg.alpha_composite(im.resize((256, 256), Image.NEAREST), (8, 8))
        row.paste(bg.convert("RGB"), (x, 22))
        small = Image.new("RGBA", (64, 64), (60, 62, 74, 255))
        small.alpha_composite(im)
        row.paste(small.convert("RGB"), (x + 290, 22))
        x += 380
    _label(row, "icons (64x64: x4 and x1)")
    rows.append(row)
    sheet = Image.new("RGB", (T * 4, T * len(rows)), (14, 15, 20))
    for i, r in enumerate(rows):
        sheet.paste(r, (0, i * T))
    os.makedirs(SCRATCH, exist_ok=True)
    out = os.path.join(SCRATCH, f"weapon_{key}.png")
    sheet.save(out)
    print(f"wrote {out}")
    if swing:
        out2 = preview_swing(key)
        print(f"wrote {out2}")
    return out


def _fp_tile(geo, tex, h, size):
    from PIL import ImageDraw
    import hd_scene as S
    a = {"hold": {"rotation": h["fp"]["rotation"], "position": h["fp"]["position"],
                  "scale": (h["fp"]["scale"],) * 3}}
    im = S.fp(geo, tex, a, size=(480, 270))
    d = ImageDraw.Draw(im)
    d.line((235, 135, 245, 135), fill=(255, 255, 255))
    d.line((240, 130, 240, 140), fill=(255, 255, 255))
    return im.resize(size)


def preview_swing(key: str) -> str:
    """一人称・三人称の振り（attack_time 0→1）のコマ。"""
    from PIL import Image
    import hd_scene as S
    mod = load_planet(key)
    gw, tw, _ = paths(key, "weapon")
    h = planet_hold(key, "weapon", mod)
    kind = planet_kind(key, mod)
    tiles = []
    for sw in (0.0, 0.15, 0.3, 0.5, 0.75):
        for fp in (0, 1):
            ang = _eval_swing(kind, sw, fp, (getattr(mod, "WEAPON_ANIMS", {}) or {}).get("swing_root"))
            hh = h["fp"] if fp else h["tp"]
            a = {"hold": {"rotation": hh["rotation"], "position": hh["position"], "scale": (hh["scale"],) * 3},
                 ORIGIN: ang}
            if fp:
                im = S.fp(gw, tw, a, size=(320, 180))
            else:
                im = S.tp(gw, tw, {"rightArm": {"rotation": h["arm_r"]}}, a, yaw=205, pitch=-10,
                          size=(180, 180), scale=4.5, centre=(0, 15, -4))
            tiles.append(im)
    W_ = 320 + 180
    sheet = Image.new("RGB", (W_ * 5, 180), (14, 15, 20))
    for i in range(5):
        sheet.paste(tiles[2 * i], (i * W_, 0))
        sheet.paste(tiles[2 * i + 1], (i * W_ + 180, 0))
    out = os.path.join(SCRATCH, f"weapon_{key}_swing.png")
    sheet.save(out)
    return out


def _eval_swing(kind, sw, fp, over=None):
    """swing_channels の式を Python で評価（プレビュー用）。"""
    s = dict(SWING.get(kind, SWING["sword"]), **(over or {}))
    cut = math.sin(math.radians((sw ** 0.6) * 180.0))
    wind = math.sin(math.radians(sw * 360.0))
    rx = s.get("rx", (0, 0))[fp] * (cut - 0.18 * wind)
    ry = s.get("ry", (0, 0))[fp] * cut
    out = {"rotation": (rx, ry, 0)}
    if "pz" in s:
        out["position"] = (0, 0, s["pz"][fp] * math.sin(math.radians(sw * 180.0)))
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] != "preview" or len(argv) < 2:
        print("usage: python3 tools/astro/astro_weapon.py preview <key> [--no-build] [--swing]")
        return 2
    for key in [a for a in argv[1:] if not a.startswith("--")]:
        preview(key, build="--no-build" not in argv, swing="--swing" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
