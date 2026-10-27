# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 乗り物の車体モデル（パラメトリック・作り込み）。

**gen_nr_props（車の残骸 = 小道具）と gen_nr_vehicles（乗れる乗り物）が共有する**（DESIGN.md §1）。
このモジュールは副作用なし（ファイルを書かない。`python3 nr_vehicle_models.py` の自己検査だけが
`build_preview/nightrunner/vehicles.png` を描く）。

■ 座標（DESIGN.md §13・nr_spec_catalog の「小道具空間」）
* 16 単位 = 1 ブロック、1 m ≒ 17.8 単位（人の身長 180cm = 32 単位）。原点 = 地面の中央、+Y が上、
  **-Z = 車の前**。**車の右 = -X**（統合版は描画で X を反転するので、ファイルの -X が実機の右側）。
  だから `*_fl` = 左前 = +X、`*_fr` = 右前 = -X。日本の車なので**運転席は右（-X）**。
* 面の向きは nr_paint・nr_preview と同じ実機の対応（east = min-X）。文字のデカールは側面・前後の面では
  外から正しく読める。上の面（up）の文字は後ろから見て読める向きになる（必要なら flip_u / flip_v）。

■ 公開 API

    vm = build_vehicle(kind, *, key=None, identifier=None, paint=None, paint2=None, paint3=None,
                       wear=None, seed=0, atlas=None, max_scale=None, drivable=False, options=None)
        kind: KINDS のどれか（sedan / taxi / police / ambulance / bus / box_truck / pickup /
              garbage_truck / army_truck / buggy / dirt_bike）
        paint: 車体色（nr_spec_catalog.SURFACES のキー "paint_red" など か "#rrggbb"）。paint2 / paint3 は
              2 色目・3 色目（パトカーの白いドア、バスの白い屋根…）。既定は KINDS の値
        wear: 傷み（下の WEAR_DEFAULTS。足りないキーは既定値）
        atlas: テクスチャの上限 (W, H)。密度（1 単位あたりの texel 数）を max_scale から下げて収める
        drivable: True なら乗り物用（パンク・横転・焼け・開いた扉を無視し、車輪・ハンドルを回せる形で）
        options: 種類ごとの追加（KIND_OPTIONS の説明）
    → VehicleModel

    VehicleModel（mcmodel.Model の包み。nr_common.write_geometry(path, vm) にそのまま渡せる）
        .paint(palette=None, seed=None) -> PIL.Image RGBA   # palette = {"paint": style, ...} の上書き（色違い）
        .to_json() -> ジオメトリ 1 個の辞書（format 1.16.0 の minecraft:geometry の要素）
        .tex_w / .tex_h / .cube_count() / .bone_names()
        .glass_bones   … 割れていない窓のボーン（entity_alphablend の 2 本目の render controller で描く）
        .smash_bones   … 「窓が割れた」状態（nr:glass == 1）で出す破片の縁のボーン（本体の render controller）
        .light_bones   … {ボーン: 種類}。種類は head / tail / hazard / beacon_a / beacon_b / sign / extra
        .open_pose     … {ボーン: {"rotation": [x,y,z]} | {"position": [...]}}（開いた見た目。アニメで足す）
        .meta          … size_blocks（幅・高さ・長さ）、wheels {名前: {center, radius, width}}、
                          seats {名前: [x, y, z]}（座る位置、単位）、roof_y、steer（ハンドル）、kind、wear…
        .locators      … {名前: (ボーン, [x, y, z])}（smoke など。ジオメトリに書く）
    part_visibility_rules(vm, lights="q.property('nr:lights') == 1", alarm="q.property('nr:alarm') == 1",
                          glass="q.property('nr:glass')") -> (body_rules, glass_rules)
        render controller の part_visibility（[{bone: 式}...]、先頭は {"*": true/false}）。灯りは q.life_time で点滅
    vehicle_styles(paint, wear=None, paint2=None, paint3=None, **over) -> stylebook（nr_paint のスタイル辞書）
    WEAR_DEFAULTS / KINDS / KIND_OPTIONS / WINDOWS（窓の名前）/ DOORS（扉の名前）

  組み立ての部品（自前の小道具を作る生成器も使ってよい）:
    VehicleModel(key, identifier, seed=0, atlas=(512, 512), max_scale=4.0, palette=None)
        .bone(name, pivot, parent="body", rotation=None)
        .box(at, size, style, bone="body", rot=None, pivot=None, uv=1.0, drop=(), decals=None, inflate=0)
        .box2(lo, hi, style, ...)（角 2 点で）/ .rod(p0, p1, w, style, h=None, ...) / .cyl(at, d, length, style, axis, n)
        .dec(cubes, faces, name, **params)（面ローカルのデカール）
        .wd(cubes, faces, name, frame="design"|"local", **params)（O/A/B 付き = 座標で描くデカール）
        .window(at, size, state, ...) / .lamp(...) / .plate(...) / .seat(...) / .steering(...) / .wheel(...)
        .locator(name, pos, bone)

■ 傷みのパラメータ（wear。0..1 の量と、部位ごとの状態）
    rust 錆 / dirt 汚れ・泥 / scratches 擦り傷 / dents 凹み（面の陰影と曲がった部品）/ fade 退色 /
    blood 血（扉・窓の手形、座席の血だまり、引きずった跡）/ bullets 弾痕の数 /
    glass: {窓: "intact"|"cracked"|"shattered"|"missing"} と glass_level（指定の無い窓を壊す割合）/
    flat: パンクした車輪の名前の列（"rr" など）/ doors: {扉: "closed"|"ajar"|"open"|"missing"} /
    hood: "closed"|"open"|"missing"|"crumpled" / trunk: "closed"|"open" / burnt 0..1（0.5 以上で焼けた車）/
    overturned: 屋根を下にひっくり返す / crushed: 屋根の潰れ 0..1 / lights_broken: 割れた灯りの名前の列 /
    missing: 無い部品（"hubcap_rl", "mirror_l", "bumper_f" …）/ hanging: 垂れた部品（"mirror_l", "bumper_f"）

■ 描き方（reference/rendering.md §3・§11 M1〜M7）
* テクスチャは 1 枚のアトラス。本体は entity_emissive_alpha（α 255 = 普通、α 16 = 光る、RGBA 0 = 穴）。
  割れていない窓は同じアトラスの半透明の texel（α 90〜235）で、gen_* が 2 本目の render controller
  （entity_alphablend、窓のボーンだけ見せる）で描く。割れた窓は破片の縁だけを α 255 で残し、穴は (0,0,0,0)。
* 灯りは「消えたレンズ」（本体）＋その 0.06 前に置いた「点いた板」（灯りのボーン、α 16 で光る）。
  点灯・点滅は part_visibility（q.property と q.life_time）。
* UV は面ごとに詰める（skyline 法）。箱の展開図の空き（長い箱で 9 割が無駄になる）を使わないので、
  同じアトラスで 1.5〜3 倍の密度になる。見えない面（地面に着いた下面など）は書かない。
"""
from __future__ import annotations

import copy
import math
import os
import random
import sys
import zlib
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcmodel import Bone, Cube, Model  # noqa: E402
import nr_paint as NP  # noqa: E402
import nr_block_paint as NBP  # noqa: E402  （nrb_* デカールを nr_paint に登録する。読むだけ）

f32 = np.float32
FACES = NP.FACES
SIDES = NP.SIDES
_rgb = NP._rgb
_ss = NP._ss
_mix = NP._mix


def _h(*parts) -> int:
    return zlib.crc32(":".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    return [v]


def _faces(faces) -> List[str]:
    if faces == "*":
        return list(FACES)
    if faces == "sides":
        return list(SIDES)
    if faces == "lr":
        return ["east", "west"]
    if faces == "fb":
        return ["north", "south"]
    if isinstance(faces, str):
        return [faces]
    return list(faces)


# ===========================================================================
#  1. 色と素材（スタイル）
# ===========================================================================
try:
    import nr_spec_catalog as _CAT
    _SURF_RGB = {k: v["rgb"] for k, v in _CAT.SURFACES.items()}
except Exception:  # noqa: BLE001  （カタログが読めなくても動く）
    _SURF_RGB = {}

# 車の塗装の見た目の基準色（カタログの rgb より少し深い色。nr_paint が汚れ・退色を重ねる）
PAINT_COLOURS = {
    "paint_white": "#d6d6ce", "paint_black": "#1e2024", "paint_red": "#8e1e1c", "paint_blue": "#28466e",
    "paint_yellow": "#d8a622", "paint_olive": "#4c5436", "paint_green": "#2c5034", "paint_orange": "#c05a22",
    "paint_burnt": "#2c2624", "steel_painted": "#70766f", "decal_stripe": "#e4dac0", "paint_silver": "#9a9ea2",
}


def colour_of(paint) -> str:
    """塗装の指定（SURFACES のキー / '#rrggbb' / (r,g,b)）→ '#rrggbb'。"""
    if paint is None:
        return "#808080"
    if isinstance(paint, (tuple, list)):
        return "#%02x%02x%02x" % tuple(int(v) for v in paint[:3])
    p = str(paint)
    if p.startswith("#"):
        return p
    if p in PAINT_COLOURS:
        return PAINT_COLOURS[p]
    if p in _SURF_RGB:
        return "#%02x%02x%02x" % tuple(_SURF_RGB[p])
    raise KeyError(f"未知の塗装 {paint!r}")


WEAR_DEFAULTS = dict(
    rust=0.3, dirt=0.5, scratches=0.4, dents=0.3, fade=0.2, blood=0.0, bullets=0,
    glass=None, glass_level=0.0, flat=(), doors=None, hood="closed", trunk="closed",
    burnt=0.0, overturned=False, crushed=0.0, lights_broken=(), missing=(), hanging=(),
)


def norm_wear(wear=None, drivable=False) -> dict:
    w = dict(WEAR_DEFAULTS)
    w.update(wear or {})
    w["glass"] = dict(w.get("glass") or {})
    w["doors"] = dict(w.get("doors") or {})
    for k in ("flat", "lights_broken", "missing", "hanging"):
        w[k] = tuple(w.get(k) or ())
    if drivable:
        w.update(flat=(), burnt=0.0, overturned=False, crushed=0.0, hood="closed", trunk="closed")
        w["doors"] = {k: v for k, v in w["doors"].items() if v == "missing"}
    return w


def vehicle_styles(paint="paint_red", wear=None, paint2=None, paint3=None, **over) -> Dict[str, dict]:
    """乗り物の stylebook（名前 → nr_paint のスタイル）。over で個別に上書き。"""
    w = norm_wear(wear)
    rust, dirt, scr, blood = float(w["rust"]), float(w["dirt"]), float(w["scratches"]), float(w["blood"])
    burnt = float(w["burnt"])

    def pm(col, r=rust, d=dirt, sc=scr):
        return NP.painted_metal_style(colour_of(col), dirt=0.12 + 0.62 * d, wear=0.12 + 0.55 * sc,
                                      rust=min(1.0, r), blood=0.0)

    st = {
        "paint": pm(paint), "paint2": pm(paint2 or "paint_white"), "paint3": pm(paint3 or "paint_black"),
        "trim": NP.style("plastic", base="#1c1c1f", wear=0.25, dirt=0.25 + 0.45 * dirt),
        "bumper": NP.style("plastic", base="#29292c", wear=0.45, dirt=0.3 + 0.5 * dirt),
        "rubber": NP.style("rubber", base="#141416", wear=0.25, dirt=0.25 + 0.3 * dirt),
        "chrome": NP.style("chrome", dirt=0.2 + 0.5 * dirt),
        "tyre": NP.style("tire", base="#1b1b1d", axis="x", dirt=0.3 + 0.5 * dirt),
        "tyre_knobby": NP.style("tire", base="#202022", axis="x", dirt=0.5 + 0.4 * dirt),
        "rim": NP.metal_style("#8c9095", dirt=0.3 + 0.45 * dirt, wear=0.45, scratches=0.5),
        "rim_dark": NP.metal_style("#36383c", dirt=0.35 + 0.4 * dirt, wear=0.5, scratches=0.4),
        "rim_white": NP.painted_metal_style("#cfcfc6", dirt=0.4 + 0.4 * dirt, wear=0.4, rust=0.5),
        "hub": NP.metal_style("#55575b", dirt=0.5, wear=0.3, scratches=0.3),
        "glass": NP.style("glass", base="#3a5058", dirt=0.2 + 0.5 * dirt, alpha=108),
        "glass_tint": NP.style("glass", base="#1b2226", dirt=0.15 + 0.4 * dirt, alpha=176),
        "glass_shard": NP.style("glass", base="#8eaab4", dirt=0.25 + 0.3 * dirt),
        "plastic_clear": NP.style("glass", base="#a8b4b4", dirt=0.3 + 0.3 * dirt, alpha=70),
        "lens_w": NP.style("glass", base="#aeb4b0", dirt=0.2 + 0.4 * dirt),
        "lens_r": NP.style("glass", base="#78140f", dirt=0.2 + 0.3 * dirt),
        "lens_a": NP.style("glass", base="#a85a16", dirt=0.2 + 0.3 * dirt),
        "lens_b": NP.style("glass", base="#183a86", dirt=0.2 + 0.3 * dirt),
        "glow_w": NP.style("glow", base="#fff2d6"),
        "glow_r": NP.style("glow", base="#ff2a18"),
        "glow_a": NP.style("glow", base="#ff9a2a"),
        "glow_b": NP.style("glow", base="#3a6aff"),
        "glow_g": NP.style("glow", base="#5aff90"),
        "dash": NP.style("plastic", base="#222225", wear=0.2, dirt=0.3 + 0.3 * dirt),
        "interior": NP.style("plastic", base="#3b3a38", wear=0.3, dirt=0.35 + 0.35 * dirt),
        "seat": NP.cloth_style("#45403a", dirt=0.45 + 0.3 * dirt, blood=0.25 * blood, torn=0.2, seams=True),
        "seat_vinyl": NP.leather_style("#2e2c2a", dirt=0.4 + 0.3 * dirt, blood=0.25 * blood, wear=0.5),
        "seat_bus": NP.cloth_style("#2c4a7a", pattern="check", alt="#24406a", period=0.6, dirt=0.5,
                                   blood=0.2 * blood, torn=0.15, seams=False),
        "carpet": NP.cloth_style("#2a2826", dirt=0.55 + 0.3 * dirt, blood=0.2 * blood, seams=False, folds=0.3),
        "headliner": NP.cloth_style("#8a867c", dirt=0.4 + 0.3 * dirt, seams=False, folds=0.4),
        "under": NP.metal_style("#323234", dirt=min(1.0, 0.6 + 0.3 * dirt), wear=0.2, scratches=0.25),
        "engine": NP.metal_style("#4a4c50", dirt=0.7, wear=0.35, scratches=0.3),
        "exhaust": NP.style("rust", amount=0.92, dirt=0.4),
        "steel": NP.metal_style("#8a8e92", dirt=0.35 + 0.3 * dirt, wear=0.5, scratches=0.5),
        "steel_dark": NP.metal_style("#3a3c40", dirt=0.3 + 0.3 * dirt, wear=0.6, scratches=0.5),
        "steel_rusty": NP.style("rust", amount=0.72, metal="#77736e", dirt=0.3),
        "alu": NP.metal_style("#aeb2b6", dirt=0.3 + 0.35 * dirt, wear=0.25, scratches=0.4),
        "plate": NP.style("plastic", base="#e0e0d6", wear=0.35, dirt=0.3 + 0.3 * dirt),
        "plate_y": NP.style("plastic", base="#e2c032", wear=0.35, dirt=0.3 + 0.3 * dirt),
        "plate_g": NP.style("plastic", base="#1e5432", wear=0.35, dirt=0.3 + 0.3 * dirt),
        "sign": NP.style("plastic", base="#e2dfd2", wear=0.3, dirt=0.3 + 0.3 * dirt),
        "plastic_red": NP.style("plastic", base="#a01c1a", wear=0.35, dirt=0.4),
        "plastic_blue": NP.style("plastic", base="#24508c", wear=0.3, dirt=0.4),
        "plastic_white": NP.style("plastic", base="#d8d6cc", wear=0.3, dirt=0.45),
        "plastic_yellow": NP.style("plastic", base="#deb428", wear=0.35, dirt=0.45),
        "plastic_orange": NP.style("plastic", base="#e06a1c", wear=0.45, dirt=0.5),
        "canvas": NP.cloth_style("#5a5c3c", pattern="plain", dirt=0.55, blood=0.0, torn=0.25, seams=True,
                                 folds=1.2, wear=0.4),
        "wood": NP.style("wood", base="#6e5038", grain=1.2, wear=0.5, dirt=0.45, planks=3.0),
        "cardboard": NP.style("paper", base="#a88050", lines=False, dirt=0.45),
        "leather": NP.leather_style("#4a3020", dirt=0.35, blood=0.0, wear=0.55),
        "cloth": NP.cloth_style("#5a5248", dirt=0.5, blood=0.3, torn=0.3, seams=False),
        "rope": NP.cloth_style("#9c8458", pattern="stripes", alt="#6e5a38", period=0.4, dirt=0.45, seams=False),
        "chain": NP.metal_style("#6c6e70", dirt=0.45, wear=0.6, scratches=0.4),
        "blood": NP.style("blood"), "blood_dry": NP.style("blood_dry"), "gore": NP.style("gore_wet"),
        "skin_dead": NP.style("skin", tone="grey_green", decay=3),
        "bone": NP.style("bone", age=0.6, blood=0.2, dirt=0.3),
        "fuel": NP.style("plastic", base="#1e1a14", wear=0.0, wet=0.95, dirt=0.0),
        "ash": NP.style("char", base="#3c3834"),
        "char": NP.style("char", base="#2a2420"),
        "char_hot": NP.style("char", base="#2a2220", embers=0.8),
        "trash": NP.style("plastic", base="#17171c", wear=0.15, wet=0.55, dirt=0.25),
        "paper": NP.style("paper", base="#d4ccb2"),
        "concrete": NP.style("concrete", base="#7a7a74", cracks=0.5, dirt=0.5),
        "diamond": NP.metal_style("#a4a8ac", dirt=0.35 + 0.3 * dirt, wear=0.4, scratches=0.3),
    }
    if burnt >= 0.5:
        # 焼けた車: 塗装は焼けた鉄（錆・煤・虹色の焼け）、樹脂とゴムは炭、布は灰
        hot = NP.style("rust", amount=0.1, metal="#3a3733", dirt=0.3, burn=min(0.97, 0.6 + 0.4 * burnt))
        for k in ("paint", "paint2", "paint3"):
            st[k] = dict(hot)
        for k in ("trim", "bumper", "rubber", "dash", "interior", "plate", "plate_y", "plate_g", "sign",
                  "plastic_red", "plastic_blue", "plastic_white", "plastic_yellow"):
            st[k] = NP.style("char", base="#262220")
        for k in ("seat", "seat_vinyl", "carpet", "headliner", "seat_bus"):
            st[k] = NP.style("char", base="#34302c")
        for k in ("chrome", "rim", "rim_white", "alu", "steel", "hub"):
            st[k] = NP.style("rust", amount=0.12, metal="#4a4644", dirt=0.5, burn=0.75)
        for k in ("lens_w", "lens_r", "lens_a", "lens_b", "glass_shard"):
            st[k] = NP.style("glass", base="#2c2a28", dirt=0.6, burn=0.6)
    st.update(over)
    return st


# ===========================================================================
#  2. デカール（nrv_*。nr_paint.DECALS にこのプロセスの中だけ足す）
# ===========================================================================
def _wp(fc, d) -> np.ndarray:
    """O/A/B 付きのデカールで、texel の位置（単位）。(h, w, 3)。"""
    O = np.asarray(d["O"], f32)
    A = np.asarray(d["A"], f32)
    B = np.asarray(d["B"], f32)
    return O + A * fc.u[..., None].astype(f32) + B * fc.v[..., None].astype(f32)


def _seg_dist(P, a, b):
    a = np.asarray(a, f32)
    b = np.asarray(b, f32)
    ab = b - a
    L2 = float(ab @ ab)
    if L2 < 1e-12:
        return np.linalg.norm(P - a, axis=-1)
    t = np.clip(((P - a) @ ab) / f32(L2), 0, 1)
    return np.linalg.norm(P - (a + t[..., None] * ab), axis=-1)


def _flatten(P, n, pts):
    n = np.asarray(n, f32)
    if not n.any():
        return P, [np.asarray(p, f32) for p in pts]
    P2 = P - (P @ n)[..., None] * n
    return P2, [np.asarray(p, f32) - float(np.asarray(p, f32) @ n) * n for p in pts]


def _cut(fc, keep):
    k = np.asarray(keep, bool)
    fc.alpha[~k] = 0
    fc.rgb[~k] = 0
    fc.glow[~k] = False


def d_seam(fc, d):
    """パネルの継ぎ目（座標の線分 segs = [(p0, p1), ...]）。暗い溝と、片側の明るい縁。"""
    P = _wp(fc, d)
    w = float(d.get("width", 0.3))
    dist = np.full(P.shape[:2], 1e9, f32)
    for a, b in d.get("segs", []):
        Pf, (af, bf) = _flatten(P, d.get("N", (0, 0, 0)), (a, b))
        dist = np.minimum(dist, _seg_dist(Pf, af, bf))
    s = max(fc.s, 0.5)
    gap = np.clip((w * 0.5 - dist) * s + 0.5, 0, 1)
    fc.mul(gap, float(d.get("dark", 0.34)))
    rim = np.clip((w * 0.5 + 1.0 / s - dist) * s + 0.5, 0, 1) * (1 - gap)
    fc.mul(rim, float(d.get("hi", 1.1)))


def d_band(fc, d):
    """高さ y=(y0, y1) の帯（座標で描くので箱をまたいで続く）。pattern: solid / checker / dash。"""
    P = _wp(fc, d)
    y0, y1 = d["y"]
    s = max(fc.s, 0.5)
    m = np.clip(np.minimum(P[..., 1] - y0, y1 - P[..., 1]) * s + 0.5, 0, 1)
    if "z" in d:
        z0, z1 = d["z"]
        m = m * np.clip(np.minimum(P[..., 2] - z0, z1 - P[..., 2]) * s + 0.5, 0, 1)
    if "x" in d:
        x0, x1 = d["x"]
        m = m * np.clip(np.minimum(P[..., 0] - x0, x1 - P[..., 0]) * s + 0.5, 0, 1)
    if not (m > 0).any():
        return
    col = _rgb(d.get("colour", (230, 230, 220)))
    pat = d.get("pattern", "solid")
    horiz = P[..., 2] if fc.face in ("east", "west") else P[..., 0]
    if pat == "checker":
        cell = float(d.get("cell", 1.0))
        k = (np.floor(horiz / cell) + np.floor((P[..., 1] - y0) / cell)).astype(np.int64) % 2
        alt = _rgb(d.get("alt", (24, 24, 26)))
        c = np.where((k == 0)[..., None], col, alt)
    elif pat == "dash":
        per = float(d.get("period", 3.0))
        k = (np.floor(horiz / per).astype(np.int64) % 2) == 0
        m = m * k
        c = np.broadcast_to(col, P.shape)
    else:
        c = np.broadcast_to(col, P.shape)
    wear = float(d.get("wear", 0.2))
    chip = fc.noise(1.4, fc.seed + 7, 3) > 0.86 - wear * 0.3
    shade = (0.9 + 0.14 * fc.grain(fc.seed + 8))[..., None]
    if d.get("reflective"):
        shade = shade * (0.9 + 0.25 * fc.grain(fc.seed + 9))[..., None]
    fc.paint(m * (~chip), c * shade)


def d_dent(fc, d):
    """凹み（面ローカル）。上から光が来る前提で、上側が暗く下側が明るい。crease で折れ線。"""
    cu, cv = d.get("at", (0.5, 0.5))
    r = max(1.5, float(d.get("size", 0.2)) * max(fc.w, fc.h))
    k = float(d.get("depth", 0.6))
    dx = (fc.px - cu * fc.w) / r
    dy = (fc.py - cv * fc.h) / r
    q = dx * dx + dy * dy
    m = np.exp(-q * 2.2)
    grad = dy * m
    fac = 1.0 - 0.16 * k * m + 0.34 * k * grad
    fc.mul(np.ones((fc.h, fc.w), f32), np.clip(fac, 0.55, 1.35))
    if d.get("crease"):
        a = math.radians(float(d.get("angle", 20)))
        u0, v0 = cu - math.cos(a) * r / fc.w, cv - math.sin(a) * r / fc.h
        u1, v1 = cu + math.cos(a) * r / fc.w, cv + math.sin(a) * r / fc.h
        fc.mul(fc.seg(u0, v0, u1, v1, max(1.0, fc.s * 0.35)), 0.72)
    # 凹みの底の塗装の割れ
    chip = (m > 0.55) & (fc.noise(2.2, fc.seed + 3, 2) > 0.7)
    fc.mul(chip, 0.8)


def d_disc(fc, d):
    """円盤を抜く（キューブのローカル座標で。表裏で同じ形）。ri..ro の輪 + spokes 本のスポーク + hub。"""
    P = _wp(fc, d)
    c = np.asarray(d["c"], f32)
    axis = int(d.get("axis", 2))
    a1, a2 = [i for i in range(3) if i != axis]
    x = P[..., a1] - c[a1]
    y = P[..., a2] - c[a2]
    r = np.sqrt(x * x + y * y)
    ri, ro = float(d.get("ri", 0.0)), float(d["ro"])
    keep = (r >= ri) & (r <= ro)
    sw = float(d.get("spoke_w", 0.6))
    a0 = math.radians(float(d.get("a0", 90.0)))
    for k in range(int(d.get("spokes", 0))):
        a = a0 + k * 2.0 * math.pi / int(d["spokes"])
        along = x * math.cos(a) + y * math.sin(a)
        perp = np.abs(-x * math.sin(a) + y * math.cos(a))
        keep |= (perp <= sw / 2) & (along >= 0) & (r <= ro)
    hub = float(d.get("hub", 0.0))
    if hub > 0:
        keep |= r <= hub
    if d.get("shade", True):
        rim = np.clip(1.0 - np.abs(r - (ri + ro) / 2) / max(0.3, (ro - ri) / 2), 0, 1)
        fc.mul(keep & (r >= ri), 0.85 + 0.3 * rim)
    _cut(fc, keep)


def d_shards(fc, d):
    """割れた窓: 枠に残った破片の縁と、上から垂れた破片だけを残して他を抜く（ローカル座標、表裏で同じ形）。"""
    P = _wp(fc, d)
    lo = np.asarray(d["lo"], f32)
    hi = np.asarray(d["hi"], f32)
    ext = hi - lo
    ax = sorted(range(3), key=lambda i: -float(ext[i]))[:2]
    a1, a2 = ax[0], ax[1]
    up = 1 if 1 in ax else a2
    side = a1 if up != a1 else a2
    u = (P[..., side] - lo[side]) / max(1e-3, float(ext[side]))
    v = (P[..., up] - lo[up]) / max(1e-3, float(ext[up]))
    du = np.minimum(u, 1 - u) * float(ext[side])
    dv = np.minimum(v, 1 - v) * float(ext[up])
    dist = np.minimum(du, dv)
    sd = int(d.get("seed", 0))
    ang = np.arctan2(v - 0.5, u - 0.5)
    rng = np.random.default_rng(sd & 0xFFFFFFFF)
    ph = rng.random(4) * 6.28
    jag = (np.abs(np.sin(ang * 7.0 + ph[0])) * 0.55 + np.abs(np.sin(ang * 13.0 + ph[1])) * 0.35 +
           np.abs(np.sin(ang * 23.0 + ph[2])) * 0.25)
    rim_w = float(d.get("rim", 0.9)) * (0.35 + jag)
    keep = dist <= rim_w
    # 上の縁から垂れた細長い破片（2〜3 本）
    for k in range(int(d.get("hang", 2))):
        cu = 0.2 + 0.6 * rng.random()
        L = 0.25 + 0.45 * rng.random()
        wdt = 0.04 + 0.06 * rng.random()
        tip = (1.0 - v) / max(L, 1e-3)
        keep |= (np.abs(u - cu) < wdt * (1.0 - tip)) & (tip <= 1.0)
    keep &= ~((dist > 0.25) & (fc.grain(sd + 5) > 0.985))
    # 破片のひびと光り
    cr = np.abs(np.sin((u * 3.1 + v * 1.7) * 9.0 + ph[3])) < 0.08
    fc.paint(keep & cr, (210, 222, 228), 0.6)
    fc.mul(keep & (dist < 0.18), 0.7)
    _cut(fc, keep)


def d_crack(fc, d):
    """割れていない窓の蜘蛛の巣のひび（ローカル座標）。hole で穴（抜く）。"""
    P = _wp(fc, d)
    c = np.asarray(d["c"], f32)
    n = int(d.get("axis", 1))
    a1, a2 = [i for i in range(3) if i != n]
    x = P[..., a1] - c[a1]
    y = P[..., a2] - c[a2]
    r = np.sqrt(x * x + y * y)
    ang = np.arctan2(y, x)
    R = float(d.get("r", 6.0))
    sd = int(d.get("seed", 0))
    rng = np.random.default_rng(sd & 0xFFFFFFFF)
    nsp = int(d.get("spokes", 9))
    m = np.zeros(r.shape, f32)
    wl = 0.12 + 0.5 / max(fc.s, 0.5)
    for k in range(nsp):
        a = 2 * math.pi * (k + rng.random() * 0.6) / nsp
        Lk = R * (0.5 + 0.6 * rng.random())
        wob = 0.25 * np.sin(r * (1.3 + rng.random())) * (r / max(R, 1e-3))
        dd = np.abs(-x * math.sin(a + 0.0) + y * math.cos(a)) - wob
        along = x * math.cos(a) + y * math.sin(a)
        m = np.maximum(m, ((np.abs(dd) < wl) & (along > 0) & (r < Lk)).astype(f32))
    for ring in (0.22, 0.45, 0.7):
        rr = R * ring * (1.0 + 0.12 * np.sin(ang * nsp + rng.random() * 6))
        m = np.maximum(m, ((np.abs(r - rr) < wl * 0.8) & (r < R)).astype(f32) * 0.8)
    fc.paint(m, _rgb(d.get("colour", (226, 234, 238))), 0.85)
    hole = float(d.get("hole", 0.0))
    if hole > 0:
        jag = hole * (0.75 + 0.35 * np.abs(np.sin(ang * 5 + rng.random() * 6)))
        fc.paint(r < jag * 1.5, (200, 210, 214), 0.7)
        _cut(fc, r >= jag)


def d_lamp(fc, d):
    """灯りのレンズ。kind: rect（反射板の升目）/ round（同心円）/ twin（丸 2 つ）/ bar（横長の LED）。
    emit なら光る（点いた板）。"""
    col = _rgb(d.get("colour", (230, 230, 220)))
    kind = d.get("kind", "rect")
    x = fc.u
    y = fc.v
    if kind in ("round", "twin"):
        cs = [(0.5, 0.5)] if kind == "round" else [(0.27, 0.5), (0.73, 0.5)]
        best = np.full(x.shape, 9.0, f32)
        for cu, cv in cs:
            rr = np.sqrt(((x - cu) * fc.w) ** 2 + ((y - cv) * fc.h) ** 2) / (0.5 * min(fc.h, fc.w / len(cs)))
            best = np.minimum(best, rr)
        rings = (np.abs(np.sin(best * 9.0)) < 0.25) & (best < 0.95)
        core = best < 0.3
        out = best > 1.0
        fc.mul(out, 0.45)
        fc.mul(rings, 0.82 if not d.get("emit") else 0.9)
        fc.paint(core, np.minimum(255, col * 1.1 + 25), 0.8)
    elif kind == "bar":
        seg = (np.abs(((fc.px / max(fc.s, 0.5)) % 1.0) - 0.5) < 0.2)
        fc.mul(~seg, 0.7)
    else:
        gx = (fc.px / max(fc.s * 0.8, 0.5)) % 1.0
        gy = (fc.py / max(fc.s * 0.8, 0.5)) % 1.0
        cell = (np.abs(gx - 0.5) > 0.38) | (np.abs(gy - 0.5) > 0.38)
        fc.mul(cell, 0.84)
        hot = np.exp(-(((x - 0.5) * 3) ** 2 + ((y - 0.5) * 3) ** 2))
        fc.paint(hot, np.minimum(255, col * 1.15 + 30), 0.5)
    edge = (fc.px < 0.9) | (fc.py < 0.9) | (fc.px > fc.w - 0.9) | (fc.py > fc.h - 0.9)
    fc.mul(edge, 0.7)
    if d.get("emit"):
        # 模様は残したまま全体を光らせる（α 16）
        fc.alpha[...] = np.minimum(fc.alpha, NP.EMISSIVE_ALPHA)
        fc.glow[...] = True


def d_grille(fc, d):
    """グリル。kind: h（横桟）/ v（縦桟）/ mesh（網）/ honey（ハニカム）。box=(u0,v0,u1,v1)。"""
    u0, v0, u1, v1 = d.get("box", (0.0, 0.0, 1.0, 1.0))
    inside = (fc.u > u0) & (fc.u < u1) & (fc.v > v0) & (fc.v < v1)
    kind = d.get("kind", "h")
    n = float(d.get("count", 6))
    if kind == "h":
        t = (fc.v - v0) / max(1e-6, v1 - v0) * n
        gap = (t - np.floor(t)) < 0.55
    elif kind == "v":
        t = (fc.u - u0) / max(1e-6, u1 - u0) * n
        gap = (t - np.floor(t)) < 0.55
    else:
        per = float(d.get("period", 0.9)) * max(fc.s, 0.5)
        gx = fc.px % per
        gy = (fc.py + (np.floor(fc.px / per) % 2) * per * 0.5 * (kind == "honey")) % per
        gap = (gx > per * 0.28) & (gy > per * 0.28)
    deep = _rgb(d.get("deep", (14, 14, 16)))
    fc.paint(inside & gap, deep, 0.92)
    lit = inside & ~gap & (np.roll(gap, 1, axis=0))
    fc.mul(lit, 1.25)


def d_rim(fc, d):
    """ホイールの面（面ローカル・中心）: スポークの間の暗い穴、ナット、センターキャップ。"""
    n = int(d.get("spokes", 5))
    x = (fc.u - 0.5) * 2
    y = (fc.v - 0.5) * 2
    r = np.sqrt(x * x + y * y)
    ang = np.arctan2(y, x)
    kind = d.get("kind", "alloy")
    if kind == "steel":
        holes = (np.abs(r - 0.62) < 0.1) & (np.cos(ang * n) > 0.55)
        fc.paint(holes, (22, 20, 20), 0.95)
        fc.mul(np.abs(r - 0.85) < 0.05, 0.7)
    else:
        spoke = np.cos(ang * n) > 0.25
        gap = (r > 0.36) & (r < 0.86) & ~spoke
        fc.paint(gap, (18, 18, 20), 0.95)
        fc.mul((r > 0.36) & (r < 0.86) & spoke, 1.08)
    nuts = (np.abs(r - 0.24) < 0.06) & (np.cos(ang * n + 0.6) > 0.8)
    fc.mul(nuts, 0.55)
    cap = r < 0.14
    fc.mul(cap, 1.15)
    fc.mul(r > 0.94, 0.6)


def _radial(fc, d):
    """車軸 X の車輪の側面: 中心からの (r, 角度)。ローカル座標。"""
    P = _wp(fc, d)
    c = np.asarray(d["c"], f32)
    y = P[..., 1] - c[1]
    z = P[..., 2] - c[2]
    return np.sqrt(y * y + z * z), np.arctan2(y, z)


def d_tyreside(fc, d):
    """タイヤの側面（ゴムの濃淡・ビード・刻印の輪・肩）。帯の箱どうしで揃う。"""
    r, ang = _radial(fc, d)
    R = float(d["r"])
    ri = float(d.get("ri", R * 0.6))
    t = np.clip((r - ri) / max(1e-3, R - ri), 0, 1)
    base = _rgb((30, 30, 32))
    col = base * (0.85 + 0.25 * t)[..., None] * (0.92 + 0.12 * fc.grain(fc.seed + 1))[..., None]
    fc.paint(np.ones(r.shape, f32), col)
    fc.mul(np.abs(t - 0.06) < 0.06, 0.55)
    letters = (np.abs(t - 0.55) < 0.12) & (np.sin(ang * 26.0) > 0.25) & (np.sin(ang * 1.3 + 0.4) > -0.2)
    fc.paint(letters, (70, 70, 72), 0.75)
    fc.mul(t > 0.88, 0.75)
    fc.mul(r > R * 0.99, 0.6)


def d_rimface(fc, d):
    """ホイールの面（ローカル座標・中心から）: スポーク・その間の暗い穴・ナット・キャップ。kind: alloy / steel。"""
    r, ang = _radial(fc, d)
    R = max(0.3, float(d["r"]))
    q = r / R
    n = int(d.get("spokes", 5))
    if d.get("kind", "alloy") == "steel":
        holes = (np.abs(q - 0.6) < 0.11) & (np.cos(ang * n) > 0.5)
        fc.paint(holes, (22, 20, 20), 0.95)
        fc.mul(np.abs(q - 0.86) < 0.05, 0.7)
    else:
        spoke = np.cos(ang * n) > 0.2
        gap = (q > 0.36) & (q < 0.86) & ~spoke
        fc.paint(gap, (16, 16, 18), 0.95)
        fc.mul((q > 0.36) & (q < 0.86) & spoke, 1.1)
    nuts = (np.abs(q - 0.24) < 0.06) & (np.cos(ang * n + 0.6) > 0.8)
    fc.mul(nuts, 0.55)
    fc.mul(q > 0.93, 0.62)


def d_smear(fc, d):
    """血を引きずった跡: 指 4 本の筋が angle の向きへ length（面の割合）だけ伸び、端から垂れる。"""
    cu, cv = d.get("at", (0.5, 0.4))
    L = float(d.get("length", 0.5))
    a = math.radians(float(d.get("angle", 0)))
    wd = float(d.get("width", 0.12))
    col = _rgb(d.get("colour", (96, 8, 10)))
    m = np.zeros((fc.h, fc.w), f32)
    for i in range(int(d.get("fingers", 4))):
        off = (i - 1.5) * wd * 0.6
        ou, ov = -math.sin(a) * off, math.cos(a) * off
        u0, v0 = cu + ou, cv + ov
        u1, v1 = u0 + math.cos(a) * L * (0.8 + 0.25 * ((i * 37) % 7) / 7), v0 + math.sin(a) * L
        m = np.maximum(m, fc.seg(u0, v0, u1, v1, max(1.0, wd * 0.45 * min(fc.w, fc.h))))
    fade = np.clip(1.0 - (((fc.u - cu) * math.cos(a) + (fc.v - cv) * math.sin(a)) / max(L, 1e-3)), 0, 1)
    m = m * (0.35 + 0.65 * fade) * (fc.noise(1.6, fc.seed + 1, 2) > 0.28)
    fc.paint(m, col, 0.9)
    fc.drips_from((m > 0.5).astype(f32), float(d.get("drip", 0.7)), fc.seed + 2, col=col * 0.9)


def d_splatter(fc, d):
    """血の飛沫（点の散らばり、中心ほど密）。"""
    cu, cv = d.get("at", (0.5, 0.5))
    R = float(d.get("size", 0.3))
    col = _rgb(d.get("colour", (110, 10, 12)))
    rng = np.random.default_rng(int(d.get("seed", fc.seed)) & 0xFFFFFFFF)
    m = np.zeros((fc.h, fc.w), f32)
    for _ in range(int(d.get("count", 26))):
        rr = R * rng.random() ** 1.6
        a = rng.random() * 6.283
        u = cu + math.cos(a) * rr
        v = cv + math.sin(a) * rr * fc.w / max(fc.h, 1)
        s = 0.006 + 0.03 * rng.random() * (1 - rr / max(R, 1e-3))
        m = np.maximum(m, fc.ellipse(u, v, s * 1.6, s * fc.w / max(fc.h, 1)))
    m = np.maximum(m, fc.ellipse(cu, cv, R * 0.22, R * 0.22 * fc.w / max(fc.h, 1)) *
                   (fc.noise(1.2, fc.seed + 4, 2) > 0.35))
    fc.paint(m, col, 0.92)
    if fc.side and d.get("drip", True):
        fc.drips_from((m > 0.5).astype(f32), 0.6, fc.seed + 3, col=col * 0.85)


def d_gauges(fc, d):
    """メーター（丸 2 つと針、真ん中の小さな画面）。"""
    cu, cv = d.get("at", (0.5, 0.5))
    sz = float(d.get("size", 0.45))
    for k, du in enumerate((-0.5, 0.5)):
        u = cu + du * sz
        rr = sz * 0.42
        ring = fc.ellipse(u, cv, rr, rr * fc.w / max(fc.h, 1))
        inner = fc.ellipse(u, cv, rr * 0.82, rr * 0.82 * fc.w / max(fc.h, 1))
        fc.paint(ring, (60, 60, 62))
        fc.paint(inner, (14, 14, 16))
        a = math.radians(200 + 70 * k)
        fc.paint(fc.seg(u, cv, u + math.cos(a) * rr * 0.75, cv + math.sin(a) * rr * 0.75 * fc.w / max(fc.h, 1),
                        1.0), (200, 90, 30))
    fc.paint(fc.ellipse(cu, cv, sz * 0.09, sz * 0.12 * fc.w / max(fc.h, 1)), (30, 40, 34))


def d_star_life(fc, d):
    """生命の星（架空の救急の印: 青い六本腕の星と白い杖）。"""
    cu, cv = d.get("at", (0.5, 0.5))
    R = max(2.0, float(d.get("size", 0.6)) * min(fc.w, fc.h) * 0.5)
    x = (fc.px - cu * fc.w) / R
    y = (fc.py - cv * fc.h) / R
    m = np.zeros(x.shape, bool)
    for k in range(3):
        a = math.radians(90 + 60 * k)
        along = x * math.cos(a) + y * math.sin(a)
        perp = -x * math.sin(a) + y * math.cos(a)
        m |= (np.abs(along) <= 1.0) & (np.abs(perp) <= 0.27)
    border = m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1))
    fc.paint(m, _rgb(d.get("colour", (30, 70, 170))))
    fc.paint(border, (236, 236, 230))
    staff = (np.abs(x) < 0.07) & (np.abs(y) < 0.7)
    fc.paint(staff, (236, 236, 230))
    snake = (np.abs(x - 0.12 * np.sin(y * 9.0)) < 0.06) & (np.abs(y) < 0.55)
    fc.paint(snake, (236, 236, 230))


def d_vtext(fc, d):
    """文字（3x5 の字。複数行は | 区切り）。box、px、flip_u / flip_v、emissive、wear、shadow。"""
    lines = str(d.get("text", "")).split("|")
    u0, v0, u1, v1 = d.get("box", (0.04, 0.08, 0.96, 0.92))
    m = np.zeros((fc.h, fc.w), f32)
    n = len(lines)
    tw = int(round((u1 - u0) * fc.w))
    th = int(round((v1 - v0) * fc.h / n))
    for i, ln in enumerate(lines):
        if tw < 3 or th < 5 or not ln:
            continue
        tm = NP.text_mask(ln, tw, th, (0.5, 0.5), d.get("px"))
        x0 = int(round(u0 * fc.w))
        y0 = int(round(v0 * fc.h)) + i * th
        hh = min(th, fc.h - y0)
        ww = min(tw, fc.w - x0)
        if hh > 0 and ww > 0:
            m[y0:y0 + hh, x0:x0 + ww] = np.maximum(m[y0:y0 + hh, x0:x0 + ww], tm[:hh, :ww])
    if d.get("flip_u"):
        m = m[:, ::-1]
    if d.get("flip_v"):
        m = m[::-1, :]
    wear = float(d.get("wear", 0.15))
    if wear > 0:
        m = m * (fc.grain(fc.seed + 3) > wear * 0.3)
    col = _rgb(d.get("colour", (232, 230, 220)))
    if d.get("shadow"):
        sh = np.roll(np.roll(m, 1, axis=0), 1, axis=1)
        fc.mul(sh * (1 - m), 0.55)
    if d.get("emissive"):
        fc.emit(m, col)
    else:
        fc.paint(m, col * (0.92 + 0.12 * fc.grain(fc.seed + 5))[..., None])


def d_mesh(fc, d):
    """金網・格子を抜く（ローカル座標で表裏同じ）。period（単位）、wire（単位）、diag、border（枠の幅）。"""
    P = _wp(fc, d)
    n = int(d.get("axis", 2))
    a1, a2 = [i for i in range(3) if i != n]
    x = P[..., a1]
    y = P[..., a2]
    per = float(d.get("period", 1.2))
    wire = float(d.get("wire", 0.22))
    if d.get("diag", True):
        p, q = (x + y) / per, (x - y) / per
    else:
        p, q = x / per, y / per
    fp = np.abs(p - np.round(p)) * per
    fq = np.abs(q - np.round(q)) * per
    keep = (fp < wire) | (fq < wire)
    border = float(d.get("border", 0.0))
    if border > 0:
        lo = np.asarray(d["lo"], f32)
        hi = np.asarray(d["hi"], f32)
        keep |= (np.minimum(x - lo[a1], hi[a1] - x) < border) | (np.minimum(y - lo[a2], hi[a2] - y) < border)
    fc.mul(keep, 1.1)
    _cut(fc, keep)


def d_puddle(fc, d):
    """地面の水たまり（上の面）。kind: fuel（虹色の油膜）/ blood / ash / water。外は抜く。"""
    x = (fc.u - 0.5) * 2
    y = (fc.v - 0.5) * 2
    r = np.sqrt(x * x + y * y)
    n = fc.noise(0.7, fc.seed + 1, 3)
    keep = r < 0.72 + (n - 0.5) * 0.7
    kind = d.get("kind", "fuel")
    if kind == "fuel":
        t = (fc.noise(1.1, fc.seed + 2, 2) * 3.0) % 1.0
        sheen = np.stack([np.sin(t * 6.28) * 0.5 + 0.5, np.sin(t * 6.28 + 2.1) * 0.5 + 0.5,
                          np.sin(t * 6.28 + 4.2) * 0.5 + 0.5], -1) * 60 + 18
        fc.paint(keep, sheen, 0.45)
    elif kind == "blood":
        fc.paint(keep, (70, 6, 8), 0.9)
    elif kind == "ash":
        fc.paint(keep, (66, 62, 58), 0.5)
    _cut(fc, keep)


def d_wipe(fc, d):
    """汚れたガラスにワイパーの拭き跡（扇形 2 つ）を描く（きれいなガラスの色に戻す）。"""
    col = _rgb(d.get("colour", (58, 76, 84)))
    m = np.zeros((fc.h, fc.w), f32)
    for cu in d.get("pivots", (0.3, 0.75)):
        x = (fc.u - cu) * fc.w
        y = (fc.v - 1.02) * fc.h
        r = np.sqrt(x * x + y * y) / max(fc.h, 1)
        ang = np.degrees(np.arctan2(-y, x))
        m = np.maximum(m, ((r > 0.15) & (r < 0.95) & (ang > 25) & (ang < 160)).astype(f32))
    fc.paint(m, col, 0.6)


def d_stencil(fc, d):
    """吹き付けのステンシル文字（ブリッジの切れ目つき）。text_mask の字の縦の継ぎ目を一部欠く。"""
    d2 = dict(d)
    d2["wear"] = float(d.get("wear", 0.35))
    d_vtext(fc, d2)


def d_frame(fc, d):
    """枠だけ残して真ん中を抜く（ローカル座標、表裏で同じ）。border（単位）、lo / hi は箱の角。"""
    P = _wp(fc, d)
    lo = np.asarray(d["lo"], f32)
    hi = np.asarray(d["hi"], f32)
    ext = hi - lo
    thin = int(np.argmin(ext))
    a1, a2 = [i for i in range(3) if i != thin]
    b = float(d.get("border", 0.7))
    e = np.minimum(np.minimum(P[..., a1] - lo[a1], hi[a1] - P[..., a1]),
                   np.minimum(P[..., a2] - lo[a2], hi[a2] - P[..., a2]))
    keep = e <= b
    fc.mul(keep & (e > b * 0.6), 0.75)
    _cut(fc, keep)


def d_halfplane(fc, d):
    """平面の片側だけ残す（ローカルか組み立ての座標）。p0 を通り法線 n の側（n·(P-p0) >= 0）を残す。"""
    P = _wp(fc, d)
    p0 = np.asarray(d["p0"], f32)
    n = np.asarray(d["n"], f32)
    keep = ((P - p0) @ n) >= 0
    _cut(fc, keep | ~(fc.alpha > 0))


def d_lettering(fc, d):
    """側面の大きな社名などの文字。d_vtext の別名（影付きが既定）。"""
    d2 = dict(d)
    d2.setdefault("shadow", True)
    d_vtext(fc, d2)


DECALS = {
    "nrv_seam": d_seam, "nrv_band": d_band, "nrv_dent": d_dent, "nrv_disc": d_disc, "nrv_shards": d_shards,
    "nrv_crack": d_crack, "nrv_lamp": d_lamp, "nrv_grille": d_grille, "nrv_rim": d_rim, "nrv_smear": d_smear,
    "nrv_splatter": d_splatter, "nrv_gauges": d_gauges, "nrv_star_life": d_star_life, "nrv_text": d_vtext,
    "nrv_mesh": d_mesh, "nrv_puddle": d_puddle, "nrv_wipe": d_wipe, "nrv_stencil": d_stencil,
    "nrv_lettering": d_lettering, "nrv_frame": d_frame, "nrv_halfplane": d_halfplane,
    "nrv_tyreside": d_tyreside, "nrv_rimface": d_rimface,
}


def register():
    """nr_paint.DECALS に nrv_* を足す（このプロセスの中だけ）。何度呼んでもよい。"""
    NBP.register()
    for k, fn in DECALS.items():
        NP.DECALS[k] = fn


register()


# ===========================================================================
#  3. 面ごとの UV の詰め込み（skyline 法・左下優先）
# ===========================================================================
def skyline_pack(items, W: int, H: int, pad: int = 1):
    """items: [(key, w, h)] → {key: (x, y)}。入らなければ None。高さ・幅の降順に、一番低く左の所へ置く。"""
    order = sorted(items, key=lambda t: (-t[2], -t[1], t[0]))
    sky = [[0, 0, W]]          # [x, y, 幅]（x の昇順）
    out = {}
    for key, w, h in order:
        if w > W or h > H:
            return None
        best = None
        n = len(sky)
        for i in range(n):
            x = sky[i][0]
            if x + w > W:
                break
            need = w + pad
            y = 0
            j = i
            while need > 0 and j < n:
                if sky[j][1] > y:
                    y = sky[j][1]
                need -= sky[j][2]
                j += 1
            if y + h > H:
                continue
            if best is None or y < best[0] or (y == best[0] and x < best[1]):
                best = (y, x, i)
        if best is None:
            return None
        y, x, i = best
        out[key] = (x, y)
        ww = min(w + pad, W - x)
        sky.insert(i, [x, y + h + pad, ww])
        j = i + 1
        end = x + ww
        while j < len(sky):
            seg = sky[j]
            if seg[0] >= end:
                break
            cut = end - seg[0]
            if seg[2] <= cut:
                sky.pop(j)
                continue
            seg[0] += cut
            seg[2] -= cut
            break
        k = 0
        while k < len(sky) - 1:
            if sky[k][1] == sky[k + 1][1]:
                sky[k][2] += sky[k + 1][2]
                sky.pop(k + 1)
            else:
                k += 1
    return out


def rod_rotation(p0, p1):
    """+Z を p0→p1 に向ける回転 [rx, ry, 0] と長さ（R = Ry(ry)·Rx(-rx)、nr_preview と同じ規則）。"""
    d = np.asarray(p1, float) - np.asarray(p0, float)
    L = float(np.linalg.norm(d))
    if L < 1e-9:
        return [0.0, 0.0, 0.0], 0.0
    d = d / L
    rx = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
    ry = math.degrees(math.atan2(d[0], d[2]))
    return [round(rx, 3), round(ry, 3), 0.0], L


# ===========================================================================
#  4. VehicleModel
# ===========================================================================
class VehicleModel:
    """mcmodel.Model の包み。中心と大きさで箱を置き、面ごとに UV を詰め、nr_paint で塗る。"""

    def __init__(self, key: str, identifier: Optional[str] = None, *, seed: int = 0, atlas=(512, 512),
                 max_scale: float = 4.0, min_scale: float = 0.5, palette: Optional[dict] = None):
        self.key = key
        self.identifier = identifier or f"geometry.nr.prop.{key}"
        self.model = Model(self.identifier, uv_scale=1, max_atlas=tuple(atlas))
        self.atlas = (int(atlas[0]), int(atlas[1]))
        self.max_scale = float(max_scale)
        self.min_scale = float(min_scale)
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.palette = dict(palette or vehicle_styles())
        self.styles: Dict[str, dict] = {}
        self.factor: Dict[int, float] = {}
        self.drop: Dict[int, set] = {}
        self.bmap: Dict[str, Bone] = {}
        self.glass_bones: List[str] = []
        self.smash_bones: List[str] = []
        self.light_bones: Dict[str, str] = {}
        self.open_pose: Dict[str, dict] = {}
        self.locators: Dict[str, Tuple[str, list]] = {}
        self.meta: Dict[str, object] = {"wheels": {}, "seats": {}}
        self.notes: List[str] = []
        self.scale = 0.0
        self.face_light = True
        self.bone("root", parent=None)
        self.bone("body", parent="root")

    # ---- mcmodel.Model と同じ顔（nr_common.write_geometry に渡せる） ---------------------------
    @property
    def tex_w(self) -> int:
        return self.model.tex_w

    @property
    def tex_h(self) -> int:
        return self.model.tex_h

    @property
    def bones(self):
        return self.model.bones

    def all_cubes(self) -> List[Cube]:
        return self.model.all_cubes()

    def cube_count(self) -> int:
        return sum(1 for c in self.model.all_cubes() if self._live_faces(c))

    def bone_names(self) -> List[str]:
        return [b.name for b in self.model.bones]

    # ---- ボーン・スタイル -----------------------------------------------------------------
    def bone(self, name: str, pivot=(0, 0, 0), parent: Optional[str] = "body", rotation=None) -> str:
        if name in self.bmap:
            return name
        if parent is not None and parent not in self.bmap:
            raise KeyError(f"{self.key}: ボーン {name} の親 {parent} が無い")
        rot = [round(float(r), 3) for r in rotation] if rotation is not None and any(
            abs(float(r)) > 1e-9 for r in rotation) else None
        b = self.model.bone(name, pivot, parent=parent, rotation=rot)
        self.bmap[name] = b
        return name

    def set_rotation(self, bone: str, rotation) -> None:
        b = self.bmap[bone]
        b.rotation = [round(float(r), 3) for r in rotation] if any(abs(float(r)) > 1e-9 for r in rotation) else None

    def use(self, style: str) -> str:
        if style in self.styles:
            return style
        if style in self.palette:
            self.styles[style] = self.palette[style]
        elif style in NBP.STYLES:
            self.styles[style] = NBP.STYLES[style]
        else:
            raise KeyError(f"{self.key}: 未知のスタイル {style!r}")
        return style

    def locator(self, name: str, pos, bone: str = "body") -> None:
        self.locators[name] = (bone, [round(float(v), 3) for v in pos])

    # ---- 箱 -----------------------------------------------------------------------------
    def box(self, at, size, style, bone: str = "body", rot=None, pivot=None, uv: float = 1.0, drop=(),
            decals=None, inflate: float = 0.0) -> Cube:
        """中心 at・大きさ size の箱。rot は中心（か pivot）まわりの [rx, ry, rz]（度）。"""
        sname = self.use(style)
        at = [float(v) for v in at]
        size = [max(0.02, float(v)) for v in size]
        origin = [at[i] - size[i] / 2 for i in range(3)]
        rotation = [float(r) for r in rot] if rot is not None and any(abs(float(r)) > 1e-9 for r in rot) else None
        piv = [float(v) for v in pivot] if pivot is not None else (at if rotation else None)
        c = Cube(origin, size, sname, inflate=inflate, pivot=piv, rotation=rotation)
        if uv != 1.0:
            self.factor[id(c)] = float(uv)
        if decals:
            for f, dv in decals.items():
                for face in _faces(f):
                    c.decals[face] = _as_list(c.decals.get(face)) + [dict(x) if isinstance(x, dict) else {"name": x}
                                                                    for x in _as_list(dv)]
        if drop:
            self.drop[id(c)] = set(_faces(drop))
        if bone not in self.bmap:
            raise KeyError(f"{self.key}: ボーン {bone} が無い")
        self.bmap[bone].cubes.append(c)
        return c

    def box2(self, lo, hi, style, **kw) -> Cube:
        """角 lo・hi の箱。"""
        at = [(float(a) + float(b)) / 2 for a, b in zip(lo, hi)]
        size = [abs(float(b) - float(a)) for a, b in zip(lo, hi)]
        return self.box(at, size, style, **kw)

    def rod(self, p0, p1, w, style, h=None, ext: float = 0.0, spin: float = 0.0, **kw) -> Cube:
        """p0 から p1 への棒（断面 w×h。長さ方向が箱の Z）。"""
        rot, L = rod_rotation(p0, p1)
        if spin:
            rot = [rot[0], rot[1], float(spin)]
        c = (np.asarray(p0, float) + np.asarray(p1, float)) / 2
        return self.box(c.tolist(), (w, h if h is not None else w, L + 2 * ext), style, rot=rot,
                        pivot=c.tolist(), **kw)

    def cyl(self, at, d, length, style, axis: str = "y", n: int = 2, rot0: float = 0.0, step: float = 0.03,
            **kw) -> List[Cube]:
        """回した箱を n 個重ねた円柱（n=2 で八角、3 で十二角）。step で端の面の z ファイトを避ける。"""
        out = []
        for k in range(n):
            a = rot0 + k * 90.0 / n
            L = length + step * k
            if axis == "y":
                size, rot = (d, L, d), (0.0, a, 0.0)
            elif axis == "x":
                size, rot = (L, d, d), (a, 0.0, 0.0)
            else:
                size, rot = (d, d, L), (0.0, 0.0, a)
            out.append(self.box(at, size, style, rot=rot, pivot=at, **kw))
        return out

    def prism(self, at, d, length, style, axis: str = "x", sides: int = 12, rot0: float = 0.0, step: float = 0.02,
              **kw) -> List[Cube]:
        """正 sides 角柱（sides/2 本の帯を回して重ねる。帯の幅 = d·tan(π/sides) なので星形にならない）。
        d は向かい合う辺の間の距離。step で帯ごとに長さを少し変えて端の面の z ファイトを避ける。"""
        n = max(2, sides // 2)
        wdt = d * math.tan(math.pi / (2 * n))
        out = []
        for k in range(n):
            a = rot0 + k * 180.0 / n
            L = length + step * k
            if axis == "x":
                size, rot = (L, d, wdt), (a, 0.0, 0.0)
            elif axis == "y":
                size, rot = (d, L, wdt), (0.0, a, 0.0)
            else:
                size, rot = (d, wdt, L), (0.0, 0.0, a)
            out.append(self.box(at, size, style, rot=rot, pivot=at, **kw))
        return out

    # ---- デカール ---------------------------------------------------------------------------
    def dec(self, cubes, faces, name, **params) -> None:
        for c in _as_list(cubes):
            for f in _faces(faces):
                c.decals[f] = _as_list(c.decals.get(f)) + [dict(params, name=name)]

    def wd(self, cubes, faces, name, frame: str = "design", **params) -> None:
        """座標で描くデカール（面ごとに O/A/B/N を足す）。frame="design" はキューブの回転込みの
        組み立て座標（ボーンの回転は含めない）、"local" は回す前のキューブの座標（表裏で同じ形にしたいとき）。"""
        for c in _as_list(cubes):
            R = None
            p = None
            if frame == "design" and c.rotation:
                R = NP._rotm(c.rotation)
                p = np.asarray(c.pivot or [c.origin[i] + c.size[i] / 2 for i in range(3)], float)
            for f in _faces(faces):
                O, A, B = NBP.face_frame(c.origin, c.size, f)
                N = NBP.FACE_NORMAL[f]
                O, A, B, N = (np.asarray(v, float) for v in (O, A, B, N))
                if R is not None:
                    O = R @ (O - p) + p
                    A = R @ A
                    B = R @ B
                    N = R @ N
                d = dict(params, name=name, O=[float(v) for v in O], A=[float(v) for v in A],
                         B=[float(v) for v in B], N=[float(v) for v in N])
                c.decals[f] = _as_list(c.decals.get(f)) + [d]

    def drop_faces(self, cubes, faces) -> None:
        for c in _as_list(cubes):
            self.drop.setdefault(id(c), set()).update(_faces(faces))

    def _live_faces(self, c) -> List[str]:
        dr = self.drop.get(id(c), ())
        return [f for f in FACES if f not in dr]

    # ---- 詰め込み ---------------------------------------------------------------------------
    def _rects_at(self, S: float):
        cubes = self.model.all_cubes()
        items = []
        for ci, c in enumerate(cubes):
            s = S * self.factor.get(id(c), 1.0)
            sx = max(1, int(round(c.size[0] * s)))
            sy = max(1, int(round(c.size[1] * s)))
            sz = max(1, int(round(c.size[2] * s)))
            dims = {"up": (sx, sz), "down": (sx, sz), "east": (sz, sy), "north": (sx, sy),
                    "west": (sz, sy), "south": (sx, sy)}
            for fi, f in enumerate(FACES):
                if f in self.drop.get(id(c), ()):
                    continue
                w, h = dims[f]
                items.append(((ci, fi), w, h))
        return cubes, items

    def pack(self, padding: int = 1) -> None:
        W, H = self.atlas
        cubes, items1 = self._rects_at(1.0)
        area1 = sum(max(1e-3, w) * max(1e-3, h) for _, w, h in items1) or 1.0
        # 面積からの見積り（詰め込み率 0.8）から始めて、入るまで 4% ずつ下げる
        S = min(self.max_scale, math.sqrt(0.92 * W * H / area1))
        S = math.floor(S * 20) / 20.0
        last = None
        while S >= self.min_scale - 1e-9:
            cubes, items = self._rects_at(S)
            placed = skyline_pack(items, W, H, padding)
            if placed is not None:
                used_h = max(y + h for (key, w, h), (x, y) in ((it, placed[it[0]]) for it in items))
                th = H
                while th > 16 and used_h <= th // 2:
                    th //= 2
                for c in cubes:
                    c.rects = {f: (0, 0, 0, 0) for f in FACES}
                    c.uv = [0, 0]
                dims = {k: (w, h) for k, w, h in items}
                for (ci, fi), (x, y) in placed.items():
                    w, h = dims[(ci, fi)]
                    cubes[ci].rects[FACES[fi]] = (x, y, w, h)
                for ci, c in enumerate(cubes):
                    s = S * self.factor.get(id(c), 1.0)
                    c._scale = s
                    c.uv_scale = s
                self.model.tex_w, self.model.tex_h = W, th
                self.scale = S
                return
            last = S
            S = math.floor(S * 0.96 * 20) / 20.0
        raise ValueError(f"{self.key}: {W}x{H} に入らない（密度 {last} まで下げた、{len(cubes)} キューブ）")

    # ---- 塗り ---------------------------------------------------------------------------------
    def paint(self, palette: Optional[dict] = None, seed: Optional[int] = None) -> Image.Image:
        if not self.model.tex_w:
            self.pack()
        book = {}
        pal = dict(self.palette)
        pal.update(palette or {})
        for name in self.styles:
            book[name] = pal.get(name, self.styles[name])
        img = NP.paint_model(self.model, book, seed=self.seed if seed is None else seed,
                             face_light=self.face_light, ao=True)
        return self._glass_alpha(img, book)

    def _glass_alpha(self, img: Image.Image, book: dict) -> Image.Image:
        """割れていない窓（glass_bones のキューブ）の texel を半透明にする（α 90〜235）。
        きれいなガラスほど透け、汚れ・ひび・血・映り込みほど不透明。穴（α 0）はそのまま。"""
        if not self.glass_bones:
            return img
        arr = np.array(img)
        for bn in self.glass_bones:
            for c in self.bmap[bn].cubes:
                a0 = float(book.get(c.style, {}).get("alpha", 110))
                for f in FACES:
                    r = c.rects.get(f)
                    if not r or r[2] <= 0 or r[3] <= 0:
                        continue
                    x, y, w, h = r
                    sub = arr[y:y + h, x:x + w]
                    keep = sub[..., 3] > 0
                    if not keep.any():
                        continue
                    rgb = sub[..., :3].astype(f32)
                    ref = np.median(rgb[keep], axis=0)
                    dist = np.linalg.norm(rgb - ref, axis=-1)
                    a = a0 + np.clip(dist / 70.0, 0, 1) * (238.0 - a0)
                    a = np.clip(np.round(a), 60, 238).astype(np.uint8)
                    sub[..., 3] = np.where(keep, a, 0)
        return Image.fromarray(arr, "RGBA")

    # ---- 書き出し -----------------------------------------------------------------------------
    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        mats = NP.cube_world_matrices(self.model)
        pts = []
        for c in self.model.all_cubes():
            if not self._live_faces(c):
                continue
            o = np.asarray(c.origin, float)
            s = np.asarray(c.size, float)
            P = np.array([[o[0] + s[0] * i, o[1] + s[1] * j, o[2] + s[2] * k]
                          for i in (0, 1) for j in (0, 1) for k in (0, 1)])
            M = mats.get(id(c))
            if M is not None:
                P = P @ M[:3, :3].T + M[:3, 3]
            pts.append(P)
        if not pts:
            return np.zeros(3), np.zeros(3)
        P = np.concatenate(pts)
        return P.min(0), P.max(0)

    def to_json(self) -> dict:
        if not self.model.tex_w:
            self.pack()
        lo, hi = self.bounds()
        ext = max(abs(lo[0]), abs(hi[0]), abs(lo[2]), abs(hi[2]), float(self.meta.get("vb_ext", 0.0)))
        vb_w = round(2 * ext / 16.0 + 1.0, 2)
        y0 = min(0.0, float(lo[1]))
        vb_h = round((float(hi[1]) - y0) / 16.0 + 1.0, 2)
        vb_off = [0, round((float(hi[1]) + y0) / 32.0, 2), 0]
        bones = []
        for b in self.model.bones:
            bd: dict = {"name": b.name, "pivot": [round(float(v), 3) for v in b.pivot]}
            if b.parent:
                bd["parent"] = b.parent
            if b.rotation:
                bd["rotation"] = [round(float(v), 3) for v in b.rotation]
            locs = {n: p for n, (bn, p) in sorted(self.locators.items()) if bn == b.name}
            if locs:
                bd["locators"] = locs
            cubes = []
            for c in b.cubes:
                uv = {}
                for f in self._live_faces(c):
                    r = c.rects.get(f)
                    if not r or r[2] <= 0:
                        continue
                    uv[f] = {"uv": [int(r[0]), int(r[1])], "uv_size": [int(r[2]), int(r[3])]}
                if not uv:
                    continue
                cd: dict = {"origin": [round(float(v), 3) for v in c.origin],
                            "size": [round(float(v), 3) for v in c.size], "uv": uv}
                if c.inflate:
                    cd["inflate"] = round(float(c.inflate), 3)
                if c.rotation:
                    piv = c.pivot or [c.origin[i] + c.size[i] / 2 for i in range(3)]
                    cd["pivot"] = [round(float(v), 3) for v in piv]
                    cd["rotation"] = [round(float(v), 3) for v in c.rotation]
                cubes.append(cd)
            if cubes:
                bd["cubes"] = cubes
            bones.append(bd)
        return {"description": {"identifier": self.identifier, "texture_width": self.model.tex_w,
                                "texture_height": self.model.tex_h, "visible_bounds_width": vb_w,
                                "visible_bounds_height": vb_h, "visible_bounds_offset": vb_off},
                "bones": bones}

    # =====================================================================================
    #  部品
    # =====================================================================================
    def window(self, at, size, state: str = "intact", *, tint: bool = False, glass_bone: str = "glass",
               smash_bone: Optional[str] = "glass_smash", frame_bone: str = "body", rot=None, pivot=None,
               decals=None, crack_at=None, uv: float = 1.0, seed: int = 0) -> Optional[Cube]:
        """窓ガラス 1 枚。state: intact / cracked / shattered / missing。
        intact・cracked は glass_bone（半透明）に置き、smash_bone に「割れた時の破片の縁」を重ねる。
        shattered は frame_bone に破片の縁だけ。missing は何も置かない（下の縁に小さな破片だけ）。"""
        size = [float(v) for v in size]
        thin = min(range(3), key=lambda i: size[i])
        seed = seed or _h(self.key, "win", at)
        if state in ("intact", "cracked"):
            if glass_bone not in self.bmap:
                self.bone(glass_bone, parent=frame_bone if frame_bone in self.bmap else "body")
            if glass_bone not in self.glass_bones:
                self.glass_bones.append(glass_bone)
            c = self.box(at, size, "glass_tint" if tint else "glass", bone=glass_bone, rot=rot, pivot=pivot,
                         uv=uv, decals=decals)
            if state == "cracked":
                lo = [c.origin[i] for i in range(3)]
                ctr = [lo[i] + c.size[i] * (crack_at[i] if crack_at else (0.35 + 0.3 * ((seed >> (3 * i)) & 7) / 7))
                       for i in range(3)]
                ctr[thin] = lo[thin] + c.size[thin] / 2
                self.wd(c, "*", "nrv_crack", frame="local", c=ctr, axis=thin,
                        r=0.45 * max(size[i] for i in range(3) if i != thin), seed=seed,
                        hole=0.0 if (seed & 3) else 0.6)
            if smash_bone:
                if smash_bone not in self.bmap:
                    self.bone(smash_bone, parent=frame_bone if frame_bone in self.bmap else "body")
                if smash_bone not in self.smash_bones:
                    self.smash_bones.append(smash_bone)
                s = self.box(at, size, "glass_shard", bone=smash_bone, rot=rot, pivot=pivot, uv=uv)
                self.wd(s, "*", "nrv_shards", frame="local", lo=list(s.origin),
                        hi=[s.origin[i] + s.size[i] for i in range(3)], seed=seed + 1, rim=0.8)
            return c
        if state == "shattered":
            s = self.box(at, size, "glass_shard", bone=frame_bone, rot=rot, pivot=pivot, uv=uv)
            self.wd(s, "*", "nrv_shards", frame="local", lo=list(s.origin),
                    hi=[s.origin[i] + s.size[i] for i in range(3)], seed=seed + 2, rim=0.9,
                    hang=1 + (seed & 1))
            return s
        return None

    def lamp(self, at, size, colour: str, *, face: str = "north", lit_bone: Optional[str] = None,
             kind: str = "rect", broken: bool = False, bezel: Optional[str] = "chrome", bone: str = "body",
             lit_colour: Optional[str] = None, uv: float = 1.5) -> Cube:
        """灯り。colour: w / r / a / b（白・赤・橙・青）。レンズ（本体）＋点いた板（lit_bone、光る）。
        face は灯りが向く面（north = 前、south = 後ろ、east / west = 横、up）。"""
        at = [float(v) for v in at]
        size = [float(v) for v in size]
        ax = {"north": 2, "south": 2, "east": 0, "west": 0, "up": 1, "down": 1}[face]
        sgn = -1.0 if face in ("north", "east", "down") else 1.0
        if bezel:
            bs = list(size)
            for i in range(3):
                if i != ax:
                    bs[i] += 0.6
            bat = list(at)
            bat[ax] -= sgn * 0.15
            self.box(bat, bs, bezel, bone=bone, uv=uv * 0.8)
        lens = self.box(at, size, "glass_shard" if broken else f"lens_{colour}", bone=bone, uv=uv)
        if broken:
            lo = list(lens.origin)
            hi = [lens.origin[i] + lens.size[i] for i in range(3)]
            ctr = [(lo[i] + hi[i]) / 2 for i in range(3)]
            self.wd(lens, face, "nrv_crack", frame="local", c=ctr, axis=ax, r=max(size) * 0.6,
                    seed=_h(self.key, "lamp", at), hole=0.0, colour=(150, 150, 146))
            self.dec(lens, face, "grime", amount=0.8)
            return lens
        self.dec(lens, face, "nrv_lamp", kind=kind, colour=_LAMP_RGB[colour])
        if lit_bone:
            if lit_bone not in self.bmap:
                self.bone(lit_bone, parent=bone if bone in self.bmap else "body")
            ls = list(size)
            ls[ax] = 0.12
            lat = list(at)
            lat[ax] += sgn * (size[ax] / 2 + 0.07)
            lc = lit_colour or colour
            lit = self.box(lat, ls, f"glow_{lc}", bone=lit_bone, uv=uv)
            self.dec(lit, face, "nrv_lamp", kind=kind, colour=_LAMP_RGB[lc], emit=True)
            self.drop_faces(lit, [f for f in FACES if f != face])
            self.light_bones.setdefault(lit_bone, light_kind(lit_bone))
        return lens

    def plate(self, at, face: str, text: str, *, kind: str = "white", bone: str = "body",
              size=(8.0, 2.6, 0.4)) -> Cube:
        """架空のナンバープレート（2 行: 地名の略号と番号）。kind: white / yellow / green。"""
        sx, sy, sz = size
        if face in ("east", "west"):
            sx, sz = sz, sx
        style, ink = {"white": ("plate", (30, 92, 54)), "yellow": ("plate_y", (24, 24, 22)),
                      "green": ("plate_g", (236, 236, 228))}[kind]
        c = self.box(at, (sx, sy, sz), style, bone=bone, uv=2.4)
        self.dec(c, face, "nrb_label", box=(0.0, 0.0, 1.0, 1.0), fill=_PLATE_FILL[kind], ink=ink, border=1,
                 border_colour=ink, text=text, wear=0.3)
        self.dec(c, face, "nrb_rivets", step=6.0, inset=0.5, r=0.25, edges="t")
        return c

    def seat(self, at, w: float, *, depth: float = 9.0, back: float = 10.5, style: str = "seat",
             bone: str = "body", recline: float = 12.0, headrest: bool = True, torn: bool = False,
             blood: bool = False, base: float = 1.4, springs: bool = False) -> List[Cube]:
        """座席（座面・背もたれ・頭当て）。at = 座面の上の面の中心 (x, y, z)。背もたれは +Z 側。"""
        x, y, z = (float(v) for v in at)
        out = []
        if base > 0:
            out.append(self.box((x, y - 2.6 - base / 2, z), (w * 0.8, base, depth * 0.8), "steel_dark", bone=bone,
                                drop="down"))
        cush = self.box((x, y - 1.3, z), (w, 2.6, depth), style, bone=bone)
        out.append(cush)
        bz = z + depth / 2 - 1.2
        piv = (x, y - 1.0, bz)
        bk = self.box((x, y - 1.0 + back / 2, bz), (w, back, 2.4), style, bone=bone, rot=(-recline, 0, 0), pivot=piv)
        out.append(bk)
        if headrest:
            hb = math.radians(recline)
            hy = y - 1.0 + back + 1.6
            hz = bz + math.sin(hb) * (back + 1.6)
            out.append(self.box((x, hy, hz), (w * 0.55, 3.0, 2.0), style, bone=bone, rot=(-recline, 0, 0)))
        if springs:
            self.wd([cush, bk], "*", "nrv_mesh", frame="local", axis=1, period=1.4, wire=0.25, diag=False)
        if torn:
            self.dec(cush, "up", "wound", at=(0.4, 0.5), size=0.5, wet=0.0)
            self.dec(bk, "south", "wound", at=(0.5, 0.4), size=0.45, wet=0.0)
        if blood:
            self.dec(cush, "up", "nrv_splatter", at=(0.5, 0.5), size=0.45, count=30, drip=False)
        return out

    def steering(self, hub, *, radius: float = 3.2, tilt: float = 24.0, column: float = 6.0,
                 parent: str = "body", style: str = "trim", spokes: int = 3) -> None:
        """ハンドル。steering_column（傾き tilt）→ steering_wheel（ここの Z 回転でハンドルを切る）。
        hub はハンドルの中心。リングは円盤を抜いたキューブ 1 枚。"""
        hx, hy, hz = (float(v) for v in hub)
        self.bone("steering_column", pivot=(hx, hy, hz), parent=parent, rotation=(tilt, 0, 0))
        self.box((hx, hy, hz - column / 2 - 0.4), (1.0, 1.0, column), "steel_dark", bone="steering_column")
        self.bone("steering_wheel", pivot=(hx, hy, hz), parent="steering_column")
        ring = self.box((hx, hy, hz), (radius * 2, radius * 2, 0.7), style, bone="steering_wheel", uv=1.6)
        self.wd(ring, "*", "nrv_disc", frame="local", c=[hx, hy, hz], axis=2, ri=radius - 0.75, ro=radius,
                spokes=spokes, spoke_w=0.65, hub=1.0, a0=-90.0)
        self.box((hx, hy, hz + 0.1), (1.8, 1.8, 0.9), "trim", bone="steering_wheel")
        self.meta["steer"] = {"bone": "steering_wheel", "axis": "z", "hub": [hx, hy, hz], "tilt": tilt}

    def wheel(self, name: str, center, radius: float, width: float, *, parent: str = "root",
              tyre: str = "tyre", rim: str = "rim", rim_kind: str = "alloy", spokes: int = 5, flat: bool = False,
              burnt: bool = False, dual: bool = False, hubcap: bool = True, side: float = 1.0,
              rim_ratio: float = 0.62, sides: int = 12) -> None:
        """車輪のボーン name（pivot = 車軸の中心。rotation の X を増やすと前（-Z）へ転がる、Y で切れる）。
        タイヤ（正 12 角柱）・ホイール（正 8 角柱）・ハブ。側面の模様は車軸の中心からの距離で描くので
        帯どうしで揃う。side は外側の向き（+1 = +X）。"""
        cx, cy, cz = (float(v) for v in center)
        self.bone(name, pivot=(cx, cy, cz), parent=parent)
        self.meta["wheels"][name] = {"center": [cx, cy, cz], "radius": radius, "width": width}
        d = radius * 2
        drop_y = 0.24 * radius if flat else 0.0
        if burnt:
            # タイヤは燃え落ちて、裸の鉄のホイールが地面に沈む
            rr = radius * 0.74
            yy = cy - (radius - rr) - 0.6
            cs = self.prism((cx, yy, cz), rr * 2, width * 0.75, "rim_dark", axis="x", sides=8, bone=name)
            self.wd(cs, "lr", "nrv_rimface", frame="local", c=[cx, yy, cz], r=rr, kind="steel", spokes=4)
            self.box((cx + side * 0.2, yy, cz), (width * 0.75 + 0.5, rr * 0.45, rr * 0.45), "hub", bone=name)
            return
        ty = cy - drop_y
        parts = [(cx + off * width * side, width * 0.46) for off in (-0.25, 0.25)] if dual else [(cx, width)]
        for k, (tx, tw) in enumerate(parts):
            cs = self.prism((tx, ty, cz), d, tw, tyre, axis="x", sides=sides, bone=name, rot0=k * 7.5)
            self.wd(cs, "lr", "nrv_tyreside", frame="local", c=[tx, ty, cz], r=radius, ri=radius * rim_ratio,
                    seed=_h(self.key, name, k))
        if flat:
            # 潰れたタイヤの膨らみ
            self.box((cx, max(0.6, ty - radius + 0.9), cz), (width * 1.1, 1.8, d * 0.62), tyre, bone=name)
        rw = (width * 0.5 if dual else width) + 0.3
        rxx = cx + (side * width * 0.25 if dual else 0.0)
        rr = radius * rim_ratio
        cs = self.prism((rxx, ty, cz), rr * 2, rw, rim, axis="x", sides=8, bone=name, rot0=22.5)
        self.wd(cs, "lr", "nrv_rimface", frame="local", c=[rxx, ty, cz], r=rr, kind=rim_kind, spokes=spokes)
        if hubcap:
            self.box((rxx, ty, cz), (rw + 0.4, rr * 0.36, rr * 0.36), "hub", bone=name, rot=(45, 0, 0))

    def mirror(self, root, side: float, *, bone: str = "body", size=(1.8, 2.6, 3.4), arm: float = 1.6,
               style: str = "paint", hanging: bool = False, missing: bool = False) -> None:
        """ドアミラー（腕・殻・鏡）。root は付け根、side は外の向き。"""
        if missing:
            return
        x, y, z = (float(v) for v in root)
        hx = x + side * (arm + size[0] / 2)
        rot = (0, 0, -side * 62) if hanging else None
        piv = (x, y, z)
        hy = y if not hanging else y
        self.box(((x + hx) / 2, y, z), (abs(hx - x), 0.8, 1.2), "trim", bone=bone, rot=rot, pivot=piv)
        shell = self.box((hx, hy, z), size, style, bone=bone, rot=rot, pivot=piv)
        mg = self.box((hx, hy, z + size[2] / 2 + 0.06), (size[0] - 0.5, size[1] - 0.5, 0.12), "chrome", bone=bone,
                      rot=rot, pivot=piv)
        self.drop_faces(mg, ["north"])
        if hanging:
            self.rod((x, y, z), (x + side * 0.6, y - 2.0, z), 0.25, "plastic_red", bone=bone)
        return shell


def light_kind(bone: str) -> str:
    """灯りのボーン名 → 種類（lights_head → head、beacon_a → beacon_a）。"""
    return bone[7:] if bone.startswith("lights_") else bone


_LAMP_RGB = {"w": (236, 232, 214), "r": (210, 30, 20), "a": (240, 140, 40), "b": (50, 90, 230), "g": (90, 240, 140)}
_PLATE_FILL = {"white": (226, 226, 218), "yellow": (226, 192, 50), "green": (30, 84, 50)}


def part_visibility_rules(vm: VehicleModel, lights: str = "q.property('nr:lights') == 1",
                          alarm: str = "q.property('nr:alarm') == 1",
                          glass: str = "q.property('nr:glass')") -> Tuple[list, list]:
    """(本体の part_visibility, 窓の part_visibility)。灯りは q.life_time で点滅する。
    head（前照灯）: 点灯中か、アラーム中は 0.5 秒ごとに点滅 / tail: 点灯中かアラームの点滅 /
    hazard（橙のウインカー）: アラーム中に点滅 / beacon_a・beacon_b（回転灯の 2 色）: 点灯中に交互の 2 連閃 /
    sign（行き先表示など）: 点灯中にゆっくり点滅 / extra（作業灯・行灯など）: 点灯中。"""
    blink = "math.mod(q.life_time, 0.8) < 0.4"
    fast = "math.mod(q.life_time, 0.5) < 0.25"
    step = "math.mod(math.floor(q.life_time * 10.0), 8.0)"
    flash = "math.mod(math.floor(q.life_time * 10.0), 2.0) == 0"
    expr = {
        "head": f"({lights}) || (({alarm}) && {fast})",
        "tail": f"({lights}) || (({alarm}) && {blink})",
        "hazard": f"({alarm}) && {blink}",
        "beacon_a": f"({lights}) && {step} < 4.0 && {flash}",
        "beacon_b": f"({lights}) && {step} >= 4.0 && {flash}",
        "sign": f"({lights}) && math.mod(q.life_time, 1.6) < 1.1",
        "extra": f"{lights}",
    }
    body = [{"*": True}]
    for b in vm.glass_bones:
        body.append({b: False})
    for b in vm.smash_bones:
        body.append({b: f"{glass} == 1"})
    for b, kind in sorted(vm.light_bones.items()):
        body.append({b: expr.get(kind, lights)})
    gl = [{"*": False}] + [{b: f"{glass} == 0"} for b in vm.glass_bones]
    return body, gl


# ===========================================================================
#  5. 共通の手続き（傷みの散らし・ナンバー・名前）
# ===========================================================================
_REGIONS = ("NRC", "KTO", "SNJ", "HKT", "MNT", "ARK", "OSK", "YMT")


def plate_text(seed: int, cls: str = "500") -> str:
    """架空のナンバー（2 行: 地名の略号と分類番号 | 一連番号）。"""
    r = random.Random(seed)
    return f"{r.choice(_REGIONS)} {cls}|{r.randint(1, 99):02d}-{r.randint(0, 99):02d}"


def _face_area(c, f) -> float:
    sx, sy, sz = c.size
    return {"up": sx * sz, "down": sx * sz, "east": sz * sy, "west": sz * sy, "north": sx * sy,
            "south": sx * sy}[f]


def _face_dims(c, f) -> Tuple[float, float]:
    sx, sy, sz = c.size
    return {"up": (sx, sz), "down": (sx, sz), "east": (sz, sy), "west": (sz, sy), "north": (sx, sy),
            "south": (sx, sy)}[f]


def scatter_wear(vm: VehicleModel, panels, w: dict, rng: random.Random, *, bullets: Optional[int] = None,
                 dent_scale: float = 1.0) -> None:
    """塗装の面 [(cube, faces), ...] に凹み・錆の筋・汚れ・弾痕を散らす（決定的）。"""
    dents = float(w["dents"]) * dent_scale
    rust = float(w["rust"])
    dirt = float(w["dirt"])
    nb = int(w["bullets"] if bullets is None else bullets)
    cand = []
    for c, faces in panels:
        for f in _faces(faces):
            cand.append((c, f, _face_area(c, f)))
    total = sum(a for _, _, a in cand) or 1.0
    for c, f, area in cand:
        fw, fh = _face_dims(c, f)
        k = dents * area / 240.0
        n = int(k) + (1 if rng.random() < k - int(k) else 0)
        for _ in range(min(n, 6)):
            r_units = rng.uniform(1.2, 3.6)
            vm.dec(c, f, "nrv_dent", at=(rng.uniform(0.12, 0.88), rng.uniform(0.18, 0.86)),
                   size=r_units / max(fw, fh, 1.0), depth=rng.uniform(0.4, 0.95), crease=rng.random() < 0.35,
                   angle=rng.uniform(-35, 35))
        if f in SIDES and rust > 0.25 and rng.random() < 0.4 + rust * 0.5:
            vm.dec(c, f, "rust_streaks", amount=min(1.0, rust * 0.9))
        if f in SIDES and dirt > 0.3 and rng.random() < 0.5:
            vm.dec(c, f, "grime", amount=dirt * 0.6)
    for _ in range(nb):
        r = rng.random() * total
        for c, f, area in cand:
            r -= area
            if r <= 0:
                fw, fh = _face_dims(c, f)
                vm.dec(c, f, "bullet_hole", at=(rng.uniform(0.1, 0.9), rng.uniform(0.15, 0.85)),
                       size=0.32 / max(0.5, min(fw, fh)))
                break


def _glass_states(w: dict, names: Sequence[str], rng: random.Random, default: str = "intact") -> Dict[str, str]:
    """窓ごとの状態（wear の glass に無い窓は glass_level の割合で壊す）。"""
    out = {}
    lvl = float(w.get("glass_level") or 0.0)
    for n in names:
        st = w["glass"].get(n)
        if st is None:
            st = default
            if lvl > 0 and rng.random() < lvl:
                st = rng.choice(("cracked", "shattered", "shattered", "missing"))
        if float(w["burnt"]) >= 0.5:
            st = "missing"
        out[n] = st
    return out


def _sail_cut(vm, cube, p_lo, p_hi, keep_point):
    """斜めの柱の線（p_lo→p_hi、組み立て座標）の keep_point の側だけ残す。"""
    a = np.asarray(p_lo, float)
    b = np.asarray(p_hi, float)
    t = b - a
    t[0] = 0.0
    n = np.array([0.0, -t[2], t[1]])
    if float(n @ (np.asarray(keep_point, float) - a)) < 0:
        n = -n
    n = n / (np.linalg.norm(n) or 1.0)
    vm.wd(cube, "*", "nrv_halfplane", frame="design", p0=[float(v) for v in a], n=[float(v) for v in n])


def _window_with_frame(vm, at, size, state, *, rot=None, pivot=None, glass_bone="glass", smash_bone="glass_smash",
                       frame_bone="body", tint=False, border=0.7, frame_style="trim", seed=0, out=0.12,
                       normal=None, decals=None):
    """窓ガラスと枠（真ん中を抜いた箱）。枠は窓の外側 out だけ浮かせる（normal は外向き、回す前の座標）。"""
    c = vm.window(at, size, state, tint=tint, glass_bone=glass_bone, smash_bone=smash_bone,
                  frame_bone=frame_bone, rot=rot, pivot=pivot, seed=seed, decals=decals)
    thin = min(range(3), key=lambda i: size[i])
    fs = list(size)
    for i in range(3):
        if i != thin:
            fs[i] += 0.3
    fs[thin] = 0.22
    nrm = list(normal) if normal is not None else [0.0, 0.0, 0.0]
    if normal is None:
        nrm[thin] = 1.0
    fat = [at[i] + nrm[i] * out for i in range(3)]
    fr = vm.box(fat, fs, frame_style, bone=frame_bone, rot=rot, pivot=pivot)
    vm.wd(fr, "*", "nrv_frame", frame="local", lo=list(fr.origin),
          hi=[fr.origin[i] + fr.size[i] for i in range(3)], border=border)
    return c, fr


# ===========================================================================
#  6. 乗用車（セダン・タクシー・パトカー。焼けた車・横転した車もこれ）
# ===========================================================================
CAR_DIMS = dict(
    W=32.0, R=6.0, tw=4.2, af=-25.0, ar=25.0, tx=13.6, zf=-38.8, zr=38.8, arch=6.8,
    floor=4.9, belt=14.6, hood_f=13.2, hood_r=14.5, deck=15.4, roof=25.6, roof_x=13.6,
    ws_b=-17.2, ws_t=-6.6, rw_t=13.4, rw_b=25.6, door_f=(-17.0, -0.2), door_r=(0.6, 17.2), tumble=9.0,
)
CAR_WINDOWS = ("windshield", "rear", "fl", "fr", "rl", "rr", "ql", "qr")
CAR_DOORS = ("fl", "fr", "rl", "rr")


def _build_car(vm: VehicleModel, kind: str, w: dict, o: dict, drivable: bool) -> None:
    D = dict(CAR_DIMS)
    D.update(o.get("dims") or {})
    rng = random.Random(_h(vm.key, "car", vm.seed))
    burnt = float(w["burnt"]) >= 0.5
    dy = -2.2 if burnt else 0.0

    def Y(y):
        return y + dy

    hw = D["W"] / 2.0
    sk = hw - 0.1
    R, af, ar, zf, zr = D["R"], D["af"], D["ar"], D["zf"], D["zr"]
    a0f, a1f, a0r, a1r = af - D["arch"], af + D["arch"], ar - D["arch"], ar + D["arch"]
    belt, deck = D["belt"], D["deck"]
    crushed = float(w["crushed"])
    roof = D["roof"] - 4.8 * crushed - (2.2 if burnt else 0.0)
    rxr = D["roof_x"]
    ws_b, ws_t, rw_t, rw_b = D["ws_b"], D["ws_t"], D["rw_t"], D["rw_b"]
    tilt = D["tumble"]
    P = "paint"
    panels = []
    gst = _glass_states(w, CAR_WINDOWS, rng)
    if drivable:
        gst = {k: ("intact" if v in ("cracked",) else v) for k, v in gst.items()}
    vm.meta.update(kind=kind, roof_y=Y(roof), length=zr - zf + 4.8, width=D["W"])

    # ---- 下回り（底板・燃料タンク・マフラー・サスペンション。ひっくり返ると見える） ----------------
    vm.box2((-13.0, Y(2.5), zf + 2.0), (13.0, Y(3.3), zr - 2.0), "under", drop=() if w["overturned"] else ())
    vm.box2((-7.0, Y(1.7), 16.0), (7.0, Y(3.3), 23.5), "under")
    vm.rod((-8.2, Y(2.3), a1f), (-9.6, Y(2.3), zr - 4.0), 1.0, "exhaust")
    vm.box((-9.6, Y(2.6), 30.0), (4.6, 2.4, 6.0), "exhaust")
    for s in (-1, 1):
        for az in (af, ar):
            vm.rod((s * 11.0, Y(R - 0.6), az), (s * 5.0, Y(3.6), az + 3.0), 0.9, "under")
    # ---- 前（鼻・エンジンルームの内張り・フェンダー・アーチの角） ------------------------------------
    nose = vm.box2((-15.8, Y(4.4), zf), (15.8, Y(13.2), a0f), P)
    panels.append((nose, ["north", "east", "west"]))
    vm.box2((-11.2, Y(4.4), a0f), (11.2, Y(13.4), a1f), "trim")
    vm.box2((-11.2, Y(4.4), a0r), (11.2, Y(12.0), a1r), "trim")
    for s in (-1, 1):
        f1 = vm.box2((s * 11.2, Y(2 * R + 0.6), a0f), (s * sk, Y(belt), a1f), P)
        f2 = vm.box2((s * 11.2, Y(4.4), a1f), (s * sk, Y(belt), D["door_f"][0]), P)
        f3 = vm.box2((s * 11.2, Y(4.4), D["door_r"][1]), (s * sk, Y(belt), a0r), P)
        f4 = vm.box2((s * 11.2, Y(2 * R + 0.6), a0r), (s * sk, Y(deck - 0.7), a1r), P)
        side = "east" if s < 0 else "west"
        panels += [(f1, side), (f2, side), (f3, side), (f4, side)]
        for zc in (a0f, a1f, a0r, a1r):
            vm.box((s * (sk - 0.6), Y(2 * R + 0.6), zc), (1.2, 1.9, 1.9), P, rot=(45, 0, 0))
        sill = vm.box2((s * 14.4, Y(3.2), a1f), (s * sk, Y(5.6), a0r), P)
        panels.append((sill, side))
        # トランクの横の壁（蓋を開けると見える）
        vm.box2((s * 14.6, Y(12.0), a1r), (s * 15.8, Y(deck - 0.7), zr - 1.2), P)
    vm.box2((-14.4, Y(3.2), a1f), (14.4, Y(D["floor"]), a0r), "carpet")
    tail = vm.box2((-15.8, Y(4.4), a1r), (15.8, Y(12.0), zr), P)
    panels.append((tail, ["south", "east", "west"]))
    vm.box2((-15.8, Y(12.0), zr - 1.2), (15.8, Y(deck - 0.7), zr), P)
    vm.box2((-14.4, Y(11.9), rw_b - 0.4), (14.4, Y(12.3), zr - 1.2), "carpet")
    # ---- ボンネット（ボーン hood、窓の根元が蝶番） ------------------------------------------------
    hood_state = w["hood"] if not drivable else "closed"
    hz1 = ws_b - 0.4
    if hood_state != "missing":
        vm.bone("hood", pivot=(0, Y(D["hood_r"]), hz1), parent="body")
        hood = vm.box2((-15.4, Y(D["hood_r"] - 0.9), zf - 0.5), (15.4, Y(D["hood_r"]), hz1), P, bone="hood")
        vm.box2((-6.5, Y(D["hood_r"] - 0.1), zf + 2.5), (6.5, Y(D["hood_r"] + 0.3), hz1 - 1.5), P, bone="hood")
        panels.append((hood, "up"))
        ang = math.degrees(math.atan2(D["hood_r"] - D["hood_f"], hz1 - zf))
        if hood_state == "open":
            ang -= 58.0
        elif hood_state == "crumpled":
            ang -= 16.0
            vm.dec(hood, "up", "nrv_dent", at=(0.5, 0.25), size=0.5, depth=1.0, crease=True, angle=8)
        vm.set_rotation("hood", (ang, 0, 0))
    if hood_state in ("open", "missing", "crumpled") or burnt:
        # エンジン
        vm.box2((-8.5, Y(5.5), zf + 3.0), (8.5, Y(12.4), a1f - 2.5), "engine")
        vm.box2((-6.0, Y(12.4), zf + 5.0), (2.0, Y(13.4), zf + 11.0), "engine")
        vm.box((10.0, Y(11.0), a0f + 6.0), (5.0, 3.6, 4.0), "trim")
        vm.locator("smoke", (0, Y(13.0), (zf + a1f) / 2))
    else:
        vm.locator("smoke", (0, Y(14.0), (zf + a1f) / 2))
    # ---- 窓の根元・ワイパー・前の窓 --------------------------------------------------------------
    vm.box2((-14.6, Y(belt - 0.2), ws_b - 1.2), (14.6, Y(belt + 0.5), ws_b + 0.6), "trim")
    if not burnt:
        vm.rod((-11.0, Y(belt + 0.7), ws_b + 0.2), (-0.5, Y(belt + 1.5), ws_b + 1.4), 0.32, "trim")
        vm.rod((1.0, Y(belt + 0.7), ws_b + 0.2), (11.5, Y(belt + 1.5), ws_b + 1.4), 0.32, "trim")
    top = roof - 0.6
    run, rise = ws_t - ws_b, top - belt
    ws_len = math.hypot(run, rise)
    ws_ang = math.degrees(math.atan2(rise, run))
    ws_at = (0.0, Y((belt + top) / 2), (ws_b + ws_t) / 2)
    wsn = [0.0, math.cos(math.radians(ws_ang)), -math.sin(math.radians(ws_ang))]
    ws, _ = _window_with_frame(vm, ws_at, (2 * (rxr + 0.8), 0.3, ws_len), gst["windshield"], rot=(ws_ang, 0, 0),
                               seed=_h(vm.key, "ws"), border=0.6, normal=[0, 1, 0])
    if ws is not None and gst["windshield"] in ("intact", "cracked"):
        vm.dec(ws, "up", "nrv_wipe", pivots=(0.28, 0.72))
        if float(w["blood"]) > 0.3:
            vm.dec(ws, "down", "nrv_splatter", at=(0.3, 0.55), size=0.35, count=40, drip=False)
    for s in (-1, 1):
        vm.rod((s * (sk - 0.9), Y(belt), ws_b), (s * (rxr - 0.1), Y(top), ws_t), 1.5, P, h=1.4)
    # ---- 屋根・天井・後ろの窓・C ピラー --------------------------------------------------------
    rf = vm.box2((-rxr, Y(roof - 0.8), ws_t - 0.5), (rxr, Y(roof), rw_t + 0.5), P)
    panels.append((rf, "up"))
    vm.box2((-rxr + 0.4, Y(roof - 1.2), ws_t), (rxr - 0.4, Y(roof - 0.8), rw_t), "headliner")
    vm.locator("roof", (0, Y(roof), (ws_t + rw_t) / 2))
    run, rise = rw_b - rw_t, top - deck
    rw_len = math.hypot(run, rise)
    rw_ang = math.degrees(math.atan2(rise, run))
    rw_at = (0.0, Y((top + deck) / 2), (rw_t + rw_b) / 2)
    rwin, _ = _window_with_frame(vm, rw_at, (2 * (rxr + 0.6), 0.3, rw_len), gst["rear"], rot=(-rw_ang, 0, 0),
                                 tint=True, seed=_h(vm.key, "rw"), border=0.6, normal=[0, 1, 0])
    if rwin is not None and o.get("rear_text"):
        vm.dec(rwin, "up", "nrv_text", text=o["rear_text"], colour=(150, 140, 124), px=2, box=(0.25, 0.25, 0.75, 0.6),
               flip_u=True, flip_v=True, wear=0.3)
    cp_lo = (rxr - 0.1, Y(top), rw_t)
    cp_hi = (sk - 0.9, Y(deck - 0.3), rw_b - 0.8)
    for s in (-1, 1):
        a = np.array([s * cp_lo[0], cp_lo[1], cp_lo[2]])
        b = np.array([s * cp_hi[0], cp_hi[1], cp_hi[2]])
        dv = b - a
        nyz = np.array([0.0, dv[2], -dv[1]])
        if nyz[1] > 0:
            nyz = -nyz
        nyz = nyz / (np.linalg.norm(nyz) or 1.0)
        wdt = 4.6
        off = nyz * (wdt / 2 - 0.6)
        cpp = vm.rod((a + off).tolist(), (b + off).tolist(), 1.4, P, h=wdt)
        panels.append((cpp, "east" if s < 0 else "west"))
    # ---- 扉と横の窓 -----------------------------------------------------------------------------
    win_top = top - 1.6
    door_spec = {"fl": (1, D["door_f"], True), "fr": (-1, D["door_f"], True),
                 "rl": (1, D["door_r"], False), "rr": (-1, D["door_r"], False)}
    for name, (s, (z0, z1), front) in door_spec.items():
        st = w["doors"].get(name, "closed")
        side = "east" if s < 0 else "west"
        if st == "missing":
            for zz in (z0 + 1.2, z0 + 6.0):
                vm.box((s * 15.2, Y(zz - z0 + 6.0), z0 + 0.4), (0.9, 1.4, 0.9), "steel_dark")
            continue
        bone = f"door_{name}"
        vm.bone(bone, pivot=(s * 15.5, Y(9.0), z0), parent="body")
        skin_style = o.get("door_style", P)
        skin = vm.box2((s * 15.1, Y(5.6), z0 + 0.12), (s * sk, Y(belt), z1 - 0.12), skin_style, bone=bone)
        panels.append((skin, side))
        vm.box2((s * 14.4, Y(6.0), z0 + 0.5), (s * 15.1, Y(belt - 0.4), z1 - 0.5), "interior", bone=bone)
        vm.box2((s * 13.9, Y(10.0), z0 + 2.0), (s * 14.4, Y(11.0), z1 - 2.5), "interior", bone=bone)
        if not burnt:
            vm.box((s * (sk + 0.25), Y(belt - 2.0), z1 - 3.2), (0.5, 0.9, 2.6), "chrome", bone=bone)
            vm.box2((s * (sk - 0.1), Y(belt - 0.3), z0 + 0.12), (s * (sk + 0.2), Y(belt + 0.25), z1 - 0.12), "trim",
                    bone=bone)
        if o.get("door_text"):
            vm.dec(skin, side, "nrv_lettering", text=o["door_text"], colour=o.get("door_text_rgb", (24, 24, 26)),
                   box=(0.12, 0.42, 0.88, 0.72), px=None, wear=0.2)
        if o.get("door_badge") and front:
            vm.dec(skin, side, "badge", kind="star", colour=(206, 168, 70), at=(0.5, 0.22), size=0.42)
        gb, sb = f"glass_{name}", f"smash_{name}"
        vm.bone(gb, pivot=(s * 15.5, Y(9.0), z0), parent=bone)
        vm.bone(sb, pivot=(s * 15.5, Y(9.0), z0), parent=bone)
        wz0 = (-9.8 if front else z0 + 0.8)
        wz1 = (z1 - 0.6 if front else min(z1 - 0.6, 13.0))
        if not front:
            wz0 = z0 + 0.8
        h = win_top - belt - 0.2
        at = (s * 15.25, Y(belt + 0.1 + h / 2), (wz0 + wz1) / 2)
        piv = (s * 15.25, Y(belt), (wz0 + wz1) / 2)
        _window_with_frame(vm, at, (0.3, h, wz1 - wz0), gst[name], rot=(0, 0, -s * tilt), pivot=piv, glass_bone=gb,
                           smash_bone=sb, frame_bone=bone, seed=_h(vm.key, "win", name), border=0.65,
                           normal=[s, 0, 0], frame_style="trim")
        if front:
            # ミラーの付け根の黒い三角（A ピラーの線の後ろだけ残す）
            sail = vm.box((s * 15.3, Y(belt + 0.1 + h / 2), (z0 + 0.3 + wz0) / 2), (0.4, h, wz0 - z0 - 0.3), "trim",
                          bone=bone, rot=(0, 0, -s * tilt), pivot=(s * 15.3, Y(belt), (z0 + wz0) / 2))
            _sail_cut(vm, sail, (s * 15.3, Y(belt), ws_b), (s * 15.3, Y(top), ws_t),
                      (s * 15.3, Y(belt + 0.5), wz0))
            hanging = f"mirror_{name[1]}" in w["hanging"] or f"mirror_{'l' if s > 0 else 'r'}" in w["hanging"]
            missing = f"mirror_{'l' if s > 0 else 'r'}" in w["missing"] or burnt
            vm.mirror((s * sk, Y(belt + 1.6), wz0 - 2.4), s, bone=bone, style=P, hanging=hanging, missing=missing)
        if st in ("open", "ajar") and not drivable:
            vm.set_rotation(bone, (0, s * (64.0 if st == "open" else 20.0), 0))
    # B ピラー・後ろの小窓
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        bp = vm.box2((s * 14.6, Y(belt), D["door_f"][1] - 0.3), (s * 15.5, Y(top), D["door_r"][0] + 0.3), P,
                     rot=(0, 0, -s * tilt), pivot=(s * 15.5, Y(belt), (D["door_f"][1] + D["door_r"][0]) / 2))
        panels.append((bp, side))
        nm = "ql" if s > 0 else "qr"
        qz0, qz1 = 13.4, D["door_r"][1] + 1.6
        qh = (win_top - belt) * 0.8
        qa = (s * 15.2, Y(belt + 0.1 + qh / 2), (qz0 + qz1) / 2)
        q = vm.window(qa, (0.3, qh, qz1 - qz0), "intact" if gst[nm] == "cracked" else gst[nm], tint=True,
                      rot=(0, 0, -s * tilt), pivot=(s * 15.2, Y(belt), (qz0 + qz1) / 2), seed=_h(vm.key, nm))
    # ---- 内装（ダッシュボード・ハンドル・座席・コンソール・荷物） ---------------------------------------
    dash = vm.box2((-14.4, Y(12.4), ws_b - 0.8), (14.4, Y(16.6), ws_b + 4.6), "dash")
    vm.dec(dash, "south", "nrv_gauges", at=(0.72, 0.38), size=0.22)
    vm.dec(dash, "south", "nrv_grille", box=(0.42, 0.25, 0.58, 0.55), kind="v", count=5)
    vm.box2((-12.0, Y(16.6), ws_b + 1.2), (-3.0, Y(17.5), ws_b + 4.4), "dash")
    vm.steering((-7.4, Y(16.8), ws_b + 8.4), radius=3.2, tilt=24.0, column=5.0)
    con = vm.box2((-2.3, Y(D["floor"]), -14.0), (2.3, Y(8.6), -1.0), "dash")
    vm.rod((0, Y(8.6), -8.0), (0, Y(11.4), -8.8), 0.6, "trim")
    seat_style = "char" if burnt else o.get("seat_style", "seat")
    blood = float(w["blood"])
    vm.seat((-7.4, Y(9.6), -3.6), 10.2, depth=9.0, back=10.4, style=seat_style, torn=True, blood=blood > 0.2,
            springs=burnt)
    vm.seat((7.4, Y(9.6), -3.6), 10.2, depth=9.0, back=10.4, style=seat_style, torn=rng.random() < 0.5,
            springs=burnt)
    vm.meta["seats"] = {"driver": [-7.4, Y(9.6), -3.6], "passenger": [7.4, Y(9.6), -3.6],
                        "rear_l": [7.0, Y(9.4), 10.6], "rear_r": [-7.0, Y(9.4), 10.6]}
    vm.seat((0.0, Y(9.4), 10.6), 27.0, depth=8.6, back=9.4, style=seat_style, headrest=False, recline=16.0,
            torn=rng.random() < 0.4, springs=burnt, base=0.0)
    vm.box2((-13.6, Y(deck - 0.7), a0r - 0.8), (13.6, Y(deck - 0.2), rw_b), "dash")
    if not burnt:
        vm.box((0, Y(top - 1.8), ws_t + 1.8), (4.4, 1.3, 0.5), "trim")
        if o.get("bag", True):
            vm.box((7.0, Y(11.6), 10.2), (6.0, 4.4, 4.2), "leather", rot=(0, 18, 0))
    # ---- 前の顔（グリル・灯り・バンパー・ナンバー） ----------------------------------------------------
    gr = vm.box2((-8.8, Y(8.8), zf - 0.5), (8.8, Y(12.6), zf + 0.2), "trim")
    vm.dec(gr, "north", "nrv_grille", kind="h", count=5, box=(0.04, 0.12, 0.96, 0.9))
    vm.dec(gr, "north", "logo", text="NR", at=(0.5, 0.5), size=0.3, colour=(200, 200, 196))
    lb = set(w["lights_broken"])
    lit_head = o.get("lit_head", ("l", "r"))
    for s in (-1, 1):
        nm = "l" if s > 0 else "r"
        vm.lamp((s * 11.4, Y(11.2), zf - 0.3), (6.0, 3.0, 0.7), "w", face="north", kind="twin",
                lit_bone="lights_head" if nm in lit_head else None, broken=(f"head_{nm}" in lb) or burnt)
        vm.lamp((s * 14.9, Y(9.0), zf - 0.25), (1.8, 1.4, 0.6), "a", face="north", lit_bone="lights_hazard",
                bezel=None, broken=burnt)
        vm.lamp((s * 11.8, Y(11.4), zr + 0.3), (6.4, 2.8, 0.7), "r", face="south",
                lit_bone="lights_tail", broken=(f"tail_{nm}" in lb) or burnt)
        vm.lamp((s * 14.9, Y(10.0), zr + 0.25), (1.6, 1.2, 0.6), "a", face="south", lit_bone="lights_hazard",
                bezel=None, broken=burnt)
    bf = "bumper_f" if "bumper_f" in w["hanging"] and not drivable else "body"
    if bf != "body":
        vm.bone("bumper_f", pivot=(15.0, Y(6.0), zf - 1.0), parent="body", rotation=(0, -6, 7))
    if "bumper_f" not in w["missing"]:
        bm = vm.box2((-16.3, Y(4.0), zf - 2.4), (16.3, Y(8.4), zf + 0.3), "bumper", bone=bf)
        vm.dec(bm, "north", "nrv_grille", kind="mesh", box=(0.3, 0.55, 0.7, 0.9), period=0.8)
        vm.box2((-14.0, Y(3.3), zf - 1.6), (14.0, Y(4.1), zf + 0.2), "trim", bone=bf)
        for s in (-1, 1):
            vm.box2((s * 14.2, Y(4.0), zf + 0.3), (s * 16.3, Y(8.4), zf + 4.4), "bumper", bone=bf)
        vm.plate((0, Y(6.2), zf - 2.65), "north", o.get("plate", plate_text(_h(vm.key, "plate"))),
                 kind=o.get("plate_kind", "white"), bone=bf)
    br = vm.box2((-16.3, Y(4.0), zr - 0.3), (16.3, Y(8.4), zr + 2.4), "bumper")
    for s in (-1, 1):
        vm.box2((s * 14.2, Y(4.0), zr - 4.4), (s * 16.3, Y(8.4), zr - 0.3), "bumper")
    vm.plate((0, Y(10.0), zr + 0.25), "south", o.get("plate", plate_text(_h(vm.key, "plate"))),
             kind=o.get("plate_kind", "white"))
    vm.rod((-9.6, Y(3.0), zr - 3.0), (-9.8, Y(3.0), zr + 1.6), 1.4, "exhaust")
    # ---- トランクの蓋（ボーン trunk。開くと中の荷物） ------------------------------------------------
    vm.bone("trunk", pivot=(0, Y(deck), rw_b), parent="body")
    lid = vm.box2((-15.4, Y(deck - 0.8), rw_b), (15.4, Y(deck), zr + 0.4), P, bone="trunk")
    panels.append((lid, ["up", "south"]))
    vm.open_pose["trunk"] = {"rotation": [72.0, 0, 0]}
    if w["trunk"] == "open" and not drivable:
        vm.set_rotation("trunk", (72.0, 0, 0))
    if not burnt:
        vm.box((-5.0, Y(14.0), 34.0), (8.0, 3.4, 5.0), "cloth", rot=(0, 10, 0))
        vm.box((6.0, Y(13.4), 33.0), (6.0, 2.2, 6.0), "cardboard", rot=(0, -12, 0))
    if not burnt and "antenna" not in w["missing"]:
        vm.rod((12.0, Y(deck - 0.2), 31.0), (12.2, Y(deck + 5.0), 29.0), 0.3, "steel_dark")
        vm.rod((12.2, Y(deck + 5.0), 29.0), (13.6, Y(deck + 8.6), 30.6), 0.3, "steel_dark")
    # ---- 車輪 ----------------------------------------------------------------------------------
    for name, (s, az) in {"fl": (1, af), "fr": (-1, af), "rl": (1, ar), "rr": (-1, ar)}.items():
        flat = name in w["flat"] and not drivable
        vm.wheel(f"wheel_{name}", (s * D["tx"], R, az), R, D["tw"], side=s, flat=flat, burnt=burnt,
                 hubcap=f"hubcap_{name}" not in w["missing"], rim=o.get("rim", "rim"), rim_kind=o.get("rim_kind", "alloy"))
    flats = [n for n in w["flat"] if n in ("fl", "fr", "rl", "rr")] if not drivable else []
    if flats:
        rx = sum((-1.0 if n[0] == "r" else 1.0) for n in flats) * 0.9
        rz = sum((-1.0 if n[1] == "r" else 1.0) for n in flats) * 0.9
        vm.set_rotation("body", (rx, 0, rz))
    # ---- 種類ごと ------------------------------------------------------------------------------
    if kind == "taxi":
        sg = vm.box((0, Y(roof + 1.8), 3.0), (9.0, 3.0, 4.0), "sign")
        vm.box((0, Y(roof + 0.2), 3.0), (7.0, 0.5, 3.0), "trim")
        for f in ("north", "south"):
            vm.dec(sg, f, "nrv_text", text="TAXI", colour=(30, 30, 32), box=(0.1, 0.2, 0.9, 0.8), px=None, wear=0.2)
        vm.wd(sg, "north", "nrv_crack", frame="local", c=[1.0, Y(roof + 2.2), 1.0], axis=2, r=3.0, seed=7,
              colour=(120, 120, 116))
        vm.bone("lights_extra", parent="body")
        lit = vm.box((0, Y(roof + 1.8), 3.0), (9.2, 3.2, 4.2), "glow_a", bone="lights_extra")
        vm.light_bones["lights_extra"] = "extra"
        for f in ("north", "south"):
            vm.dec(lit, f, "nrv_text", text="TAXI", colour=(40, 30, 10), box=(0.1, 0.2, 0.9, 0.8), emissive=True)
        cubes = [c for c in vm.bmap["body"].cubes if c.style == P] + [c for b in vm.bmap.values()
                                                                     if b.name.startswith("door_") for c in b.cubes
                                                                     if c.style == P]
        vm.wd(cubes, "lr", "nrv_band", y=(Y(10.6), Y(12.4)), pattern="checker", cell=0.9,
              colour=(236, 232, 214), alt=(26, 26, 28), wear=0.3)
        mt = vm.box((5.0, Y(17.4), ws_b + 5.6), (4.0, 2.0, 2.4), "trim")
        vm.dec(mt, "south", "nrv_text", text="1280", colour=(255, 40, 30), emissive=True, box=(0.1, 0.25, 0.9, 0.75))
        pt = vm.window((0, Y(belt + 4.4), 4.6), (26.0, 8.4, 0.3), "cracked", glass_bone="glass",
                       smash_bone="glass_smash", seed=_h(vm.key, "partition"))
    if kind == "police":
        vm.box((0, Y(roof + 1.2), 0.0), (22.0, 2.4, 4.2), "trim")
        for s in (-1, 1):
            vm.box((s * 9.0, Y(roof + 0.1), 0.0), (1.2, 0.4, 4.6), "steel_dark")
        vm.lamp((-5.6, Y(roof + 2.6), 0.0), (8.6, 1.8, 3.8), "r", face="up", kind="bar", lit_bone="beacon_a",
                bezel=None)
        vm.lamp((5.6, Y(roof + 2.6), 0.0), (8.6, 1.8, 3.8), "b", face="up", kind="bar", lit_bone="beacon_b",
                bezel=None)
        for b_, x_, col in (("beacon_a", -5.6, "r"), ("beacon_b", 5.6, "b")):
            lc = vm.box((x_, Y(roof + 2.6), 0.0), (8.7, 1.9, 3.9), f"glow_{col}", bone=b_)
            vm.dec(lc, "*", "nrv_lamp", kind="bar", colour=_LAMP_RGB[col], emit=True)
            vm.light_bones[b_] = b_
        # プッシュバンパー
        for s in (-1, 1):
            vm.box((s * 8.0, Y(9.0), zf - 4.6), (1.4, 8.4, 1.4), "steel_dark")
            vm.box((s * 8.0, Y(6.0), zf - 3.4), (1.2, 1.2, 2.6), "steel_dark")
        for yy in (6.0, 9.2, 12.4):
            vm.box((0, Y(yy), zf - 5.2), (19.0, 1.1, 1.1), "steel_dark")
        # スポットライト（運転席側の A ピラー）
        vm.box((-(sk + 0.6), Y(belt + 6.6), ws_b + 5.0), (1.8, 1.8, 3.0), "chrome")
        vm.lamp((-(sk + 0.6), Y(belt + 6.6), ws_b + 3.3), (1.4, 1.4, 0.4), "w", face="north", kind="round",
                bezel=None)
        # 後席の金網と銃架
        cage = vm.box((0, Y(belt + 4.6), 4.4), (26.0, 9.0, 0.3), "steel")
        vm.wd(cage, "*", "nrv_mesh", frame="local", axis=2, period=1.3, wire=0.22, border=0.5,
              lo=list(cage.origin), hi=[cage.origin[i] + cage.size[i] for i in range(3)])
        vm.box((0, Y(belt + 3.6), -5.0), (1.0, 1.0, 10.0), "steel_dark")
        vm.box((0, Y(belt + 2.2), -9.0), (1.6, 2.6, 1.0), "steel_dark")
    # ---- 血・弾痕・汚れ ---------------------------------------------------------------------------
    if blood > 0.05:
        drv = [c for c in vm.bmap.get("door_fr", Bone("x")).cubes if c.style == o.get("door_style", P)]
        for c in drv[:1]:
            vm.dec(c, "east", "nrv_smear", at=(0.25, 0.25), angle=12, length=0.55, width=0.16)
            vm.dec(c, "east", "handprint", at=(0.75, 0.3), size=0.6)
        if blood > 0.4:
            vm.wd([c for c in vm.bmap["body"].cubes if c.style == P and c.size[1] < 3.0][:2], "lr", "nrv_band",
                  y=(Y(3.2), Y(4.4)), colour=(76, 10, 10), wear=0.6)
    scatter_wear(vm, panels, w, rng)
    vm.locator("lightbar", (0, Y(roof + 2.0), 0))
    vm.meta["size_blocks"] = [round(D["W"] / 16, 2), round(Y(roof + (3.4 if kind == "police" else 0)) / 16, 2),
                              round((zr - zf + 5.0) / 16, 2)]


# ===========================================================================
#  7. トラック・バン（運転室 + 後ろの箱・荷台・幌・収集箱）
# ===========================================================================
def side_band(vm, s, x_in, x_out, y_lo, y_hi, z0, z1, arches, style, *, bone="body", chamfer=True, skip=()):
    """車体の横の帯（|x| = x_in〜x_out、y_lo〜y_hi、z0〜z1）。車輪のアーチ (a0, a1, top) の所は top より上だけ。
    skip = [(z0, z1, y_top)] の所は y_top より下だけ置く（扉の開口など）。置いた箱を返す。"""
    out = []
    cuts = sorted([(a0, a1, top) for a0, a1, top in arches if a1 > z0 and a0 < z1])
    pts = sorted({z0, z1} | {max(z0, min(z1, a)) for a0, a1, _ in cuts for a in (a0, a1)}
                 | {max(z0, min(z1, a)) for a0, a1, _ in skip for a in (a0, a1)})
    for za, zb in zip(pts[:-1], pts[1:]):
        if zb - za < 0.05:
            continue
        zm = (za + zb) / 2
        lo, hi = y_lo, y_hi
        for a0, a1, top in cuts:
            if a0 <= zm <= a1:
                lo = max(lo, top)
        for k0, k1, ytop in skip:
            if k0 <= zm <= k1:
                hi = min(hi, ytop)
        if hi - lo > 0.05:
            out.append(vm.box2((s * x_in, lo, za), (s * x_out, hi, zb), style, bone=bone))
    if chamfer:
        for a0, a1, top in cuts:
            for zc in (a0, a1):
                if z0 < zc < z1 and top < y_hi:
                    vm.box((s * (x_out - 0.6), top, zc), (min(1.2, x_out - x_in), 1.9, 1.9), style, bone=bone,
                           rot=(45, 0, 0))
    return out


def _truck_cab(vm, C: dict, w: dict, o: dict, gst: dict, rng, panels: list, drivable: bool) -> None:
    """運転室（ボンネット型か、hood が 0 ならキャブオーバー）。C は寸法の辞書（_TRUCKS の値）。"""
    W = C["W"]
    hw = W / 2.0
    sk = hw - 0.1
    zf, zws, zb = C["zf"], C["zws"], C["zb"]
    y0, belt, roof = C["y0"], C["belt"], C["roof"]
    R, af, tx, tw = C["R"], C["af"], C["tx"], C["tw"]
    P = C.get("paint", "paint")
    ztop = C["ztop"]                       # 前の窓の上の縁の z
    hood_f, hood_r = C.get("hood_h", (belt, belt))
    door0, door1 = C["door"]
    door_lo = C.get("door_lo", y0 + 1.0)
    arch = (af - R - 1.2, af + R + 1.2, 2 * R + 0.8)
    x_in = tx - tw / 2 - 0.4
    has_hood = zws - zf > 2.0
    # ---- 前の下回りとボンネットの塊 -------------------------------------------------------------------
    if has_hood:
        for s in (-1, 1):
            side = "east" if s < 0 else "west"
            for c in side_band(vm, s, x_in, sk, y0, hood_r - 0.9, zf, zws, [arch], P):
                panels.append((c, side))
        vm.box2((-x_in, y0, zf), (x_in, hood_r - 0.9, zws), "trim")
        vm.bone("hood", pivot=(0, hood_r, zws), parent="body")
        hd = vm.box2((-(hw - 0.5), hood_r - 0.9, zf - 0.3), (hw - 0.5, hood_r, zws), P, bone="hood")
        panels.append((hd, ["up", "north"]))
        vm.set_rotation("hood", (math.degrees(math.atan2(hood_r - hood_f, zws - zf)), 0, 0))
        if C.get("vents"):
            vm.dec(hd, "up", "nrb_slits", box=(0.15, 0.55, 0.42, 0.9), rows=6)
            vm.dec(hd, "up", "nrb_slits", box=(0.58, 0.55, 0.85, 0.9), rows=6)
        if C.get("hood_text"):
            vm.dec(hd, "up", "nrv_stencil", text=C["hood_text"], colour=(222, 222, 210), box=(0.2, 0.15, 0.8, 0.45),
                   flip_u=True, flip_v=True)
        gy0, gy1 = y0 + 2.0, hood_f - 1.2
    else:
        gy0, gy1 = y0 + 2.0, belt - 1.0
    # グリル・前の灯り・バンパー・ナンバー
    gr = vm.box2((-(hw - 3.0), gy0, zf - 0.6), (hw - 3.0, gy1, zf + 0.2), C.get("grille_style", "trim"))
    vm.dec(gr, "north", "nrv_grille", kind=C.get("grille", "h"), count=C.get("grille_n", 7), box=(0.04, 0.06, 0.96, 0.94))
    if C.get("grille_text"):
        vm.dec(gr, "north", "nrv_text", text=C["grille_text"], colour=(210, 210, 204), box=(0.3, 0.02, 0.7, 0.22))
    hl = C.get("headlights", "rect")
    hly = C.get("head_y", gy1 - 2.2)
    hlx = C.get("head_x", hw - 4.4)
    lb = set(w["lights_broken"])
    for s in (-1, 1):
        nm = "l" if s > 0 else "r"
        if hl == "round":
            vm.lamp((s * hlx, hly, zf - 0.6), (3.6, 3.6, 0.8), "w", face="north", kind="round",
                    lit_bone="lights_head", broken=f"head_{nm}" in lb)
            if C.get("head_cage"):
                cg = vm.box((s * hlx, hly, zf - 1.4), (4.4, 4.4, 0.3), "steel_dark")
                vm.wd(cg, "*", "nrv_mesh", frame="local", axis=2, period=1.1, wire=0.22, diag=False, border=0.4,
                      lo=list(cg.origin), hi=[cg.origin[i] + cg.size[i] for i in range(3)])
        else:
            vm.lamp((s * hlx, hly, zf - 0.6), (6.0, 3.4, 0.8), "w", face="north", kind="twin",
                    lit_bone="lights_head", broken=f"head_{nm}" in lb)
        vm.lamp((s * (hw - 1.6), hly - 3.4, zf - 0.4), (2.0, 1.6, 0.6), "a", face="north", lit_bone="lights_hazard",
                bezel=None)
    by = C.get("bumper_y", (y0 - 1.0, y0 + 3.6))
    bst = C.get("bumper_style", "steel_dark")
    vm.box2((-(hw + 0.6), by[0], zf - 3.2), (hw + 0.6, by[1], zf - 0.4), bst)
    vm.plate((0, (by[0] + by[1]) / 2, zf - 3.45), "north", o.get("plate", plate_text(_h(vm.key, "plate"), "100")),
             kind=o.get("plate_kind", "white"))
    # ---- 運転室の下（側面の帯・床・前後の壁） ------------------------------------------------------
    cab_arches = [arch] if zws - 0.5 < af < zb + 0.5 else []
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        for c in side_band(vm, s, hw - 1.0, sk, y0, belt, zws, zb, cab_arches, P,
                           skip=[(door0, door1, door_lo)]):
            panels.append((c, side))
        if door_lo > y0 + 3.0 and not cab_arches:
            # 乗り降りの段（扉の下）
            vm.box2((s * (hw - 2.2), door_lo - 3.6, door0 + 1.0), (s * (hw + 0.4), door_lo - 3.0, door1 - 1.0),
                    "diamond")
    if cab_arches:
        vm.box2((-x_in, y0, arch[0]), (x_in, arch[2] + 0.6, arch[1]), "trim")
    vm.box2((-(hw - 1.0), y0, zws), (hw - 1.0, y0 + 1.6, zb), "carpet")
    if not has_hood:
        fw = vm.box2((-hw + 0.1, y0, zf), (hw - 0.1, belt, zf + 1.2), P)
        panels.append((fw, "north"))
    bw = vm.box2((-hw + 0.1, y0, zb - 1.2), (hw - 0.1, roof - 0.9, zb), P)
    panels.append((bw, "south"))
    if C.get("rear_window", True):
        vm.window((0, (belt + roof) / 2 + 0.4, zb + 0.05), (W * 0.42, (roof - belt) * 0.45, 0.3),
                  gst.get("cab_rear", "intact"), tint=True, seed=_h(vm.key, "cabrear"))
    # ---- 窓・屋根・柱 ----------------------------------------------------------------------------------
    top = roof - 0.6
    run, rise = ztop - zws, top - belt
    L = math.hypot(run, rise)
    ang = math.degrees(math.atan2(rise, run))
    at = (0.0, (belt + top) / 2, (zws + ztop) / 2)
    ws, _ = _window_with_frame(vm, at, (W - 3.0, 0.3, L), gst.get("windshield", "intact"), rot=(ang, 0, 0),
                               seed=_h(vm.key, "ws"), border=0.7, normal=[0, 1, 0])
    if ws is not None and gst.get("windshield") in ("intact", "cracked"):
        vm.dec(ws, "up", "nrv_wipe", pivots=(0.3, 0.7))
    if C.get("split_ws"):
        vm.box(at, (0.8, 0.5, L), "trim", rot=(ang, 0, 0))
    for s in (-1, 1):
        vm.rod((s * (hw - 0.8), belt, zws), (s * (hw - 0.8), top, ztop), 1.4, P, h=1.4)
    if C.get("soft_top"):
        ct = vm.box2((-(hw - 0.2), top - 0.6, ztop - 0.4), (hw - 0.2, roof + 0.8, zb + 0.4), "canvas")
    else:
        rf = vm.box2((-(hw - 0.3), top - 0.4, ztop - 0.4), (hw - 0.3, roof, zb), P)
        panels.append((rf, "up"))
    vm.box2((-(hw - 1.2), top - 0.9, ztop + 0.4), (hw - 1.2, top - 0.4, zb - 1.0), "headliner")
    vm.meta["cab_roof_y"] = roof
    # ---- 扉 -------------------------------------------------------------------------------------------
    for name, s in (("fl", 1), ("fr", -1)):
        st = w["doors"].get(name, "closed")
        side = "east" if s < 0 else "west"
        if st == "missing":
            continue
        bone = f"door_{name}"
        vm.bone(bone, pivot=(s * (hw - 0.4), (door_lo + belt) / 2, door0), parent="body")
        skin = vm.box2((s * (hw - 0.8), door_lo, door0 + 0.12), (s * sk, belt, door1 - 0.12), P, bone=bone)
        panels.append((skin, side))
        vm.box2((s * (hw - 1.5), door_lo + 0.5, door0 + 0.5), (s * (hw - 0.8), belt - 0.4, door1 - 0.5), "interior",
                bone=bone)
        vm.box((s * (sk + 0.25), belt - 2.2, door1 - 2.6), (0.5, 0.9, 2.6), "chrome", bone=bone)
        if C.get("door_text"):
            vm.dec(skin, side, "nrv_lettering", text=C["door_text"], colour=C.get("door_text_rgb", (24, 24, 26)),
                   box=(0.1, 0.35, 0.9, 0.7))
        if C.get("door_logo"):
            vm.dec(skin, side, "logo", text=C["door_logo"], at=(0.5, 0.45), size=0.7,
                   colour=C.get("door_logo_rgb", (30, 60, 120)))
        gb, sb = f"glass_{name}", f"smash_{name}"
        vm.bone(gb, pivot=(s * hw, belt, door0), parent=bone)
        vm.bone(sb, pivot=(s * hw, belt, door0), parent=bone)
        h = top - belt - 1.4
        wz0, wz1 = door0 + 0.8, door1 - 0.8
        at = (s * (hw - 0.45), belt + 0.1 + h / 2, (wz0 + wz1) / 2)
        _window_with_frame(vm, at, (0.3, h, wz1 - wz0), gst.get(name, "intact"), glass_bone=gb, smash_bone=sb,
                           frame_bone=bone, seed=_h(vm.key, "win", name), border=0.7, normal=[s, 0, 0])
        mw = C.get("mirror", "truck")
        if mw == "truck":
            mx = s * (hw + 2.6)
            vm.rod((s * hw, belt + 1.0, door0 + 1.5), (mx, belt + 1.0, door0 + 1.2), 0.5, "steel_dark", bone=bone)
            vm.rod((s * hw, top - 1.0, door0 + 1.5), (mx, top - 1.0, door0 + 1.2), 0.5, "steel_dark", bone=bone)
            if not (f"mirror_{'l' if s > 0 else 'r'}" in w["missing"]):
                vm.box((mx, (belt + top) / 2, door0 + 1.2), (1.6, top - belt - 1.0, 2.6), "trim", bone=bone)
                mg = vm.box((mx, (belt + top) / 2, door0 + 2.56), (1.2, top - belt - 1.6, 0.12), "chrome", bone=bone)
                vm.drop_faces(mg, ["north"])
        else:
            vm.mirror((s * sk, belt + 1.4, door0 + 2.0), s, bone=bone, style=P)
        if st in ("open", "ajar") and not drivable:
            vm.set_rotation(bone, (0, s * (66.0 if st == "open" else 22.0), 0))
    # ---- 内装 -----------------------------------------------------------------------------------------
    dz = zws + 1.0
    dash = vm.box2((-(hw - 1.2), belt - 4.0, dz - 1.0), (hw - 1.2, belt + 0.8, dz + 4.0), "dash")
    vm.dec(dash, "south", "nrv_gauges", at=(0.72, 0.4), size=0.2)
    hub = (-(hw * 0.42), belt + 2.2, dz + 8.4)
    vm.steering(hub, radius=C.get("wheel_r", 3.6), tilt=C.get("wheel_tilt", 38.0), column=6.0)
    sy = belt - 4.0
    seat_style = C.get("seat_style", "seat_vinyl")
    vm.seat((-(hw * 0.42), sy, zb - 6.5), hw * 0.8, depth=8.0, back=11.0, style=seat_style, torn=True,
            blood=float(w["blood"]) > 0.3, base=sy - y0 - 4.0 if sy - y0 > 6 else 1.4)
    vm.seat((hw * 0.36, sy, zb - 6.5), hw * 0.9, depth=8.0, back=11.0, style=seat_style, base=1.4)
    vm.meta["seats"] = {"driver": [hub[0], sy, zb - 6.5], "passenger": [hw * 0.36, sy, zb - 6.5]}
    # 前輪
    for name, s in (("fl", 1), ("fr", -1)):
        vm.wheel(f"wheel_{name}", (s * tx, R, af), R, tw, side=s, flat=(name in w["flat"]) and not drivable,
                 rim=C.get("rim", "rim_white"), rim_kind="steel", spokes=6, rim_ratio=C.get("rim_ratio", 0.6))


def _rear_axles(vm, C: dict, w: dict, drivable: bool, names=("rl", "rr", "rl2", "rr2")) -> None:
    R, tx, tw = C["R2"], C["tx2"], C["tw2"]
    k = 0
    for ai, az in enumerate(C["axles"]):
        for s in (1, -1):
            nm = ("rl" if s > 0 else "rr") + ("" if ai == 0 else str(ai + 1))
            vm.wheel(f"wheel_{nm}", (s * tx, R, az), R, tw, side=s, dual=C.get("dual", True),
                     flat=(nm in w["flat"]) and not drivable, rim=C.get("rim", "rim_white"), rim_kind="steel",
                     spokes=6, rim_ratio=C.get("rim_ratio", 0.6))
            k += 1


def _chassis(vm, C: dict, z0: float, z1: float, y: float) -> None:
    """梁 2 本と横の燃料タンク・後ろのバンパー・泥よけ。"""
    for s in (-1, 1):
        vm.box2((s * 7.0, y, z0), (s * 10.0, y + 2.8, z1), "steel_dark")
    for az in C["axles"]:
        vm.box((0, C["R2"], az), (2 * C["tx2"] - C["tw2"], 2.2, 2.2), "under")


def _rear_end(vm, C: dict, zr: float, y0: float, hw: float, w: dict, o: dict, lights_y: float) -> None:
    """後ろのバンパー・灯り・ナンバー・泥よけ。"""
    vm.box2((-(hw - 1.0), y0 - 1.0, zr - 0.6), (hw - 1.0, y0 + 2.0, zr + 1.6), "steel_dark")
    vm.box2((-(hw - 6.0), y0 - 3.2, zr - 0.4), (hw - 6.0, y0 - 2.4, zr + 1.0), "diamond")
    for s in (-1, 1):
        vm.lamp((s * (hw - 3.4), lights_y, zr + 0.2), (4.2, 2.6, 0.7), "r", face="south", lit_bone="lights_tail",
                kind="round")
        vm.lamp((s * (hw - 7.2), lights_y, zr + 0.2), (2.2, 2.0, 0.6), "a", face="south", lit_bone="lights_hazard",
                kind="round", bezel=None)
        vm.box2((s * (C["tx2"] - C["tw2"] / 2 - 0.2), 1.2, C["axles"][-1] + C["R2"] + 1.4),
                (s * (C["tx2"] + C["tw2"] / 2 + 0.2), 7.4, C["axles"][-1] + C["R2"] + 1.8), "rubber")
    vm.plate((0, y0 + 0.6, zr + 1.8), "south", o.get("plate", plate_text(_h(vm.key, "plate"), "100")),
             kind=o.get("plate_kind", "white"))


def _box_body(vm, C: dict, w: dict, o: dict, gst: dict, rng, panels: list) -> dict:
    """箱型の荷台（救急車・引越しトラック）。壁 5 枚・角の柱・擦り板・後ろの扉かシャッター・中身。"""
    hw = C["bw"] / 2.0
    z0, z1 = C["bz"]
    y0, y1 = C["by"]
    st = C.get("box_style", "paint")
    arches = [(az - C["R2"] - 1.4, az + C["R2"] + 1.4, 2 * C["R2"] + 1.0) for az in C["axles"]]
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        wall = vm.box2((s * (hw - 1.0), y0, z0), (s * hw, y1, z1), st)
        panels.append((wall, side))
        C.setdefault("_walls", []).append((wall, side))
        for zz in np.linspace(z0 + 0.6, z1 - 0.6, C.get("posts", 5)):
            vm.box((s * (hw + 0.15), (y0 + y1) / 2, float(zz)), (0.4, y1 - y0, 0.9), "alu")
        vm.box2((s * (hw - 0.2), y0 - 0.2, z0), (s * (hw + 0.5), y0 + 1.2, z1), "alu")
        vm.box2((s * (hw - 0.2), y1 - 1.0, z0), (s * (hw + 0.4), y1 + 0.2, z1), "alu")
        # 箱の下の横（車輪の上のフェンダー）
        side_band(vm, s, hw - 4.0, hw - 0.2, max(y0 - 4.0, 2 * C["R2"] + 1.0), y0, z0 + 2.0, z1, arches, "steel_dark",
                  chamfer=False)
    rf = vm.box2((-hw, y1 - 1.0, z0), (hw, y1, z1), C.get("roof_style", st))
    panels.append((rf, "up"))
    fl = vm.box2((-(hw - 1.0), y0, z0), (hw - 1.0, y0 + 1.2, z1), C.get("floor_style", "diamond"))
    fw = vm.box2((-hw, y0, z0), (hw, y1, z0 + 1.0), st)
    panels.append((fw, "north"))
    C["_front"] = fw
    C["_roof"] = rf
    out = {"walls": (wall, rf), "hw": hw}
    # 後ろの開口の枠
    vm.box2((-hw, y1 - 3.0, z1 - 1.2), (hw, y1, z1), st)
    for s in (-1, 1):
        vm.box2((s * (hw - 2.0), y0, z1 - 1.2), (s * hw, y1, z1), st)
    kind = C.get("rear", "doors")
    ow, oh = hw - 2.0, y1 - 3.0 - y0
    if kind == "doors":
        for name, s in (("rear_l", 1), ("rear_r", -1)):
            bone = f"door_{name}"
            vm.bone(bone, pivot=(s * ow, (y0 + y1) / 2, z1 + 0.4), parent="body")
            dk = vm.box2((s * ow, y0 + 1.2, z1 - 0.2), (0.0 if s > 0 else -0.0, y1 - 3.0, z1 + 0.6), st, bone=bone)
            dw = vm.box2((s * ow * 0.15, y0 + oh * 0.55, z1 + 0.6), (s * ow * 0.85, y0 + oh * 0.85, z1 + 0.62),
                         "trim", bone=bone, drop=["north"])
            vm.window((s * ow * 0.5, y0 + oh * 0.7, z1 + 0.66), (ow * 0.66, oh * 0.28, 0.3),
                      gst.get(name, "intact"), tint=True, glass_bone=f"glass_{name}", smash_bone=f"smash_{name}",
                      frame_bone=bone, seed=_h(vm.key, name))
            vm.box((s * 1.4, y0 + oh * 0.45, z1 + 0.9), (0.6, 2.6, 0.6), "chrome", bone=bone)
            panels.append((dk, "south"))
            out[name] = dk
            vm.open_pose[bone] = {"rotation": [0, s * 155.0, 0]}
            dst = w["doors"].get(name, "closed")
            if dst in ("open", "ajar"):
                vm.set_rotation(bone, (0, s * (105.0 if dst == "open" else 35.0), 0))
    else:
        # シャッター（横の筋）。open_pose で上へ
        vm.bone("shutter", pivot=(0, y1, z1), parent="body")
        frac = float(C.get("shutter_open", 0.5))
        sh_h = oh * (1.0 - frac)
        sh = vm.box2((-ow, y1 - 3.0 - sh_h, z1 - 0.7), (ow, y1 - 3.0, z1 - 0.2), "alu", bone="shutter")
        vm.dec(sh, "south", "nrb_corrugate", period=1.2, axis="v", depth=1.2)
        vm.dec(sh, "south", "nrv_grille", kind="h", count=max(2, int(sh_h / 1.2)), box=(0.0, 0.0, 1.0, 1.0),
               deep=(70, 72, 74))
        vm.box((0, y1 - 3.4 - sh_h, z1 - 0.1), (6.0, 0.8, 0.6), "steel_dark", bone="shutter")
        vm.open_pose["shutter"] = {"position": [0, round(sh_h - 0.4, 2), 0]}
        panels.append((sh, "south"))
    return out


def _bed(vm, C: dict, w: dict, o: dict, rng, panels: list) -> None:
    """ピックアップの荷台（床・側板・前板・下りたテールゲート）。"""
    hw = C["bw"] / 2.0
    z0, z1 = C["bz"]
    y0, y1 = C["by"]
    P = "paint"
    arches = [(az - C["R2"] - 1.2, az + C["R2"] + 1.2, 2 * C["R2"] + 0.8) for az in C["axles"]]
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        for c in side_band(vm, s, hw - 1.0, hw, y0 - 6.0, y1, z0, z1, arches, P):
            panels.append((c, side))
        vm.box2((s * (hw - 1.4), y1, z0), (s * (hw + 0.1), y1 + 0.5, z1), "trim")
        vm.box2((s * (C["tx2"] - C["tw2"] / 2 - 0.4), y0 - 6.0, arches[0][0]),
                (s * (hw - 1.0), y0 + 0.6, arches[0][1]), "trim")
    fl = vm.box2((-(hw - 1.0), y0 - 1.0, z0), (hw - 1.0, y0, z1), "steel")
    vm.dec(fl, "up", "nrb_corrugate", period=2.4, axis="u", depth=1.5)
    vm.box2((-hw, y0 - 6.0, z0), (hw, y1, z0 + 1.0), P)
    vm.box2((-(hw - 1.0), y0 - 6.0, z0 + 1.0), (hw - 1.0, y0 - 1.0, z1), "under")
    vm.bone("tailgate", pivot=(0, y0, z1), parent="body")
    tg = vm.box2((-(hw - 0.2), y0, z1), (hw - 0.2, y1, z1 + 1.2), P, bone="tailgate")
    vm.dec(tg, "south", "nrv_lettering", text=C.get("tailgate_text", "NRTRUCK"), colour=(214, 212, 200),
           box=(0.15, 0.3, 0.85, 0.7))
    panels.append((tg, ["south", "north"]))
    vm.set_rotation("tailgate", (-float(C.get("tailgate", 88.0)), 0, 0))


def _canvas_bed(vm, C: dict, w: dict, o: dict, rng, panels: list) -> dict:
    """軍用の荷台（木の床・側板・弓形の骨・幌。後ろがめくれて中が見える）。"""
    hw = C["bw"] / 2.0
    z0, z1 = C["bz"]
    y0, y1, yc = C["by"][0], C["by"][1], C["canvas_y"]
    fl = vm.box2((-hw, y0 - 1.2, z0), (hw, y0, z1), "wood")
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        sb = vm.box2((s * (hw - 1.0), y0, z0), (s * hw, y1, z1), "paint")
        vm.dec(sb, side, "nrv_grille", kind="v", count=10, box=(0.0, 0.05, 1.0, 0.95), deep=(40, 40, 30))
        panels.append((sb, side))
        side_band(vm, s, hw - 3.0, hw - 0.4, 2 * C["R2"] + 1.0, y0 - 1.2, z0, z1,
                  [(az - C["R2"] - 1.2, az + C["R2"] + 1.2, 2 * C["R2"] + 1.0) for az in C["axles"]],
                  "paint", chamfer=False)
    vm.box2((-hw, y0, z0), (hw, y1, z0 + 1.0), "paint")
    vm.bone("tailgate", pivot=(0, y0, z1), parent="body")
    tg = vm.box2((-(hw - 0.2), y0, z1 - 0.2), (hw - 0.2, y1, z1 + 0.8), "paint", bone="tailgate")
    panels.append((tg, "south"))
    vm.open_pose["tailgate"] = {"rotation": [-85.0, 0, 0]}
    # 弓形の骨と幌
    nb = C.get("bows", 5)
    for zz in np.linspace(z0 + 2.0, z1 - 2.0, nb):
        for s in (-1, 1):
            vm.box((s * (hw - 0.6), (y1 + yc) / 2, float(zz)), (0.8, yc - y1, 0.8), "steel_dark")
        vm.box((0, yc - 0.5, float(zz)), (2 * hw - 1.2, 0.8, 0.8), "steel_dark")
    can = []
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        cv = vm.box2((s * (hw - 0.1), y1 - 0.4, z0 + 0.4), (s * (hw + 0.5), yc - 1.0, z1 - 0.4), "canvas")
        can.append(cv)
    top = vm.box2((-(hw + 0.5), yc - 1.0, z0 + 0.4), (hw + 0.5, yc + 0.4, z1 - 0.4), "canvas")
    for k in range(3):
        vm.box2((-(hw + 0.3), yc + 0.4, z0 + 0.4 + k * (z1 - z0) / 3.0 + 0.5),
                (hw + 0.3, yc + 1.1, z0 + 0.4 + (k + 1) * (z1 - z0) / 3.0 - 0.5), "canvas",
                rot=(0, 0, 0))
    fc = vm.box2((-(hw + 0.4), y1 - 0.4, z0 - 0.2), (hw + 0.4, yc + 0.4, z0 + 0.4), "canvas")
    # 後ろの幌（右半分は下りて、左はめくれて丸めてある）
    vm.box2((-(hw + 0.4), y1 + 2.0, z1 - 0.6), (-0.5, yc + 0.4, z1), "canvas")
    vm.cyl((hw * 0.5, yc - 1.4, z1 - 0.6), 2.6, hw - 0.6, "canvas", axis="x", n=2)
    vm.box2((0.5, yc - 3.0, z1 - 0.8), (hw + 0.4, yc + 0.4, z1 - 0.2), "canvas")
    for c in can + [top]:
        vm.dec(c, "*", "grime", amount=0.5)
    return {"hw": hw}


def _compactor(vm, C: dict, w: dict, o: dict, rng, panels: list) -> None:
    """ゴミ収集車の収集箱（補強のリブ・後ろのホッパーと刃・横のリフターと青いゴミ箱）。"""
    hw = C["bw"] / 2.0
    z0, z1 = C["bz"]
    y0, y1 = C["by"]
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        wl = vm.box2((s * (hw - 1.0), y0, z0), (s * hw, y1, z1), "paint")
        vm.dec(wl, side, "rust_streaks", amount=0.8)
        panels.append((wl, side))
        side_band(vm, s, hw - 4.0, hw - 0.4, 2 * C["R2"] + 1.0, y0, z0 + 2, z1,
                  [(az - C["R2"] - 1.4, az + C["R2"] + 1.4, 2 * C["R2"] + 1.0) for az in C["axles"]],
                  "steel_dark", chamfer=False)
    for zz in np.linspace(z0 + 2.0, z1 - 2.0, C.get("ribs", 6)):
        vm.box((0, (y0 + y1) / 2 + 0.3, float(zz)), (2 * hw + 1.0, y1 - y0 + 0.6, 1.6), "paint")
    rf = vm.box2((-hw, y1 - 1.0, z0), (hw, y1 + 0.4, z1), "paint")
    panels.append((rf, "up"))
    vm.box2((-hw, y0, z0), (hw, y1, z0 + 1.0), "paint")
    # ホッパー（後ろの口が開いていて、黒い汁と布くず）
    hz0, hz1 = C["hz"]
    hy0, hy1 = C["hy"]
    vm.bone("hopper", pivot=(0, hy1, hz0), parent="body")
    for s in (-1, 1):
        hs = vm.box2((s * (hw - 1.0), hy0, hz0), (s * hw, hy1, hz1), "paint", bone="hopper")
        panels.append((hs, "east" if s < 0 else "west"))
    vm.box2((-hw, hy1 - 1.0, hz0), (hw, hy1, hz1 - 6.0), "paint", bone="hopper")
    vm.box2((-hw, hy0, hz0), (hw, hy0 + 4.0, hz1), "paint", bone="hopper")
    inner = vm.box2((-(hw - 1.0), hy0 + 4.0, hz0 + 1.0), (hw - 1.0, hy0 + 4.6, hz1 - 1.0), "trash", bone="hopper")
    vm.dec(inner, "up", "grime", amount=1.0)
    vm.box2((-(hw - 1.0), hy0 + 4.0, hz1 - 2.0), (hw - 1.0, hy0 + 10.0, hz1 - 1.0), "paint", bone="hopper")
    bl = vm.box((0, hy1 - 6.0, (hz0 + hz1) / 2), (2 * hw - 3.0, 1.2, (hz1 - hz0) * 0.7), "steel_rusty",
                bone="hopper", rot=(32, 0, 0))
    vm.box((3.0, hy1 - 7.0, hz0 + 8.0), (6.0, 1.6, 5.0), "cloth", bone="hopper", rot=(20, 30, 0))
    vm.open_pose["hopper"] = {"rotation": [38.0, 0, 0]}
    # リフターとゴミ箱
    lx = -(hw + 3.0)
    vm.box2((-(hw + 0.2), y0 + 2.0, hz0 - 10.0), (-(hw + 1.2), y0 + 18.0, hz0 - 8.0), "steel_dark")
    vm.box((lx, y0 + 12.0, hz0 - 9.0), (5.0, 1.4, 1.4), "steel_dark")
    bn = vm.box((lx - 4.0, y0 + 9.0, hz0 - 9.0), (8.0, 11.0, 8.0), "plastic_blue", rot=(0, 0, -12))
    vm.box((lx - 4.0, y0 + 15.2, hz0 - 9.0), (8.8, 1.0, 8.8), "plastic_blue", rot=(0, 0, -12))
    vm.dec(bn, "*", "grime", amount=0.7)
    # 後ろのステップと手すり
    vm.box2((-(hw - 2.0), 6.8, hz1 - 1.0), (hw - 2.0, 7.6, hz1 + 4.0), "diamond")
    for s in (-1, 1):
        vm.rod((s * (hw - 3.0), 14.0, hz1 + 0.6), (s * (hw - 3.0), 26.0, hz1 + 0.6), 0.7, "steel")
        vm.lamp((s * (hw - 2.0), hy0 + 7.0, hz1 + 0.1), (3.6, 2.4, 0.6), "r", face="south", lit_bone="lights_tail",
                kind="round")
        vm.lamp((s * (hw - 2.0), hy0 + 4.0, hz1 + 0.1), (2.0, 1.8, 0.6), "a", face="south", lit_bone="lights_hazard",
                kind="round", bezel=None)
    vm.plate((0, hy0 + 3.0, hz1 + 0.25), "south", o.get("plate", plate_text(_h(vm.key, "plate"), "800")),
             kind=o.get("plate_kind", "green"))


def _cab_cubes(vm, C) -> list:
    """運転室の塗装の箱（帯を描く先）。"""
    out = []
    for b in vm.model.bones:
        if b.name in ("body", "hood") or b.name.startswith("door_f"):
            out += [c for c in b.cubes if c.style == "paint"]
    return out


def _dress_ambulance(vm, C, w, o, rng, panels, drivable):
    hw = C["bw"] / 2.0
    walls = [c for c, _ in C.get("_walls", [])]
    cab = _cab_cubes(vm, C)
    # 帯: 赤い帯・反射の市松・救急の印・文字
    vm.wd(walls + cab, "lr", "nrv_band", y=(25.6, 28.2), colour=(176, 24, 22), wear=0.25)
    vm.wd(walls, "lr", "nrv_band", y=(15.0, 18.6), pattern="checker", cell=1.8, colour=(200, 30, 28),
          alt=(232, 230, 220), wear=0.25, reflective=True)
    for c, side in C.get("_walls", []):
        vm.dec(c, side, "nrv_star_life", at=(0.3 if side == "west" else 0.7, 0.36), size=0.42)
        vm.dec(c, side, "nrv_lettering", text="AMBULANCE", colour=(176, 24, 22), box=(0.42, 0.18, 0.95, 0.34)
               if side == "west" else (0.05, 0.18, 0.58, 0.34))
        vm.dec(c, side, "nrv_text", text="NR CITY EMS", colour=(40, 60, 140), box=(0.5, 0.36, 0.9, 0.44)
               if side == "west" else (0.1, 0.36, 0.5, 0.44))
    fw = C.get("_front")
    if fw is not None:
        vm.dec(fw, "north", "nrv_lettering", text="AMBULANCE", colour=(176, 24, 22), box=(0.1, 0.12, 0.9, 0.3),
               flip_u=True)
    for name in ("door_rear_l", "door_rear_r"):
        if name in vm.bmap:
            for c in vm.bmap[name].cubes:
                if c.style == "paint":
                    vm.dec(c, "south", "nrv_star_life", at=(0.5, 0.36), size=0.5)
                    vm.wd(c, "south", "nrv_band", y=(15.0, 18.6), pattern="checker", cell=1.8,
                          colour=(200, 30, 28), alt=(232, 230, 220))
    # 回転灯（運転室の屋根）と箱の四隅の赤灯
    ry = C["roof"]
    vm.box((0, ry + 1.2, C["zb"] - 9.0), (26.0, 2.4, 4.6), "trim")
    for k, (x, col, b) in enumerate(((-8.0, "r", "beacon_a"), (0.0, "w", "beacon_b"), (8.0, "r", "beacon_a"))):
        vm.lamp((x, ry + 2.7, C["zb"] - 9.0), (6.6, 1.8, 4.0), col, face="up", kind="bar", lit_bone=b, bezel=None)
        lc = vm.box((x, ry + 2.7, C["zb"] - 9.0), (6.7, 1.9, 4.1), f"glow_{col}", bone=b)
        vm.dec(lc, "*", "nrv_lamp", kind="bar", colour=_LAMP_RGB[col], emit=True)
    y1 = C["by"][1]
    for s in (-1, 1):
        for zz, face, b in ((C["bz"][0] - 0.5, "north", "beacon_b"), (C["bz"][1] + 0.5, "south", "beacon_a")):
            vm.lamp((s * (hw - 2.6), y1 - 2.0, zz), (3.6, 2.4, 0.8), "r", face=face, lit_bone=b, kind="round")
    vm.light_bones["beacon_a"] = "beacon_a"
    vm.light_bones["beacon_b"] = "beacon_b"
    # 中: 棚・長椅子・酸素ボンベ・ストレッチャー（半分外へ）・血のシーツ
    z0, z1 = C["bz"]
    y0 = C["by"][0] + 1.2
    cab_ = vm.box2((hw - 5.0, y0, z0 + 6.0), (hw - 1.0, y0 + 22.0, z0 + 40.0), "plastic_white")
    vm.dec(cab_, "east", "nrv_grille", kind="h", count=5, box=(0.05, 0.05, 0.95, 0.95), deep=(150, 150, 146))
    vm.box2((-(hw - 1.0), y0, z0 + 8.0), (-(hw - 6.0), y0 + 6.0, z0 + 34.0), "seat_vinyl")
    for c in vm.cyl((-(hw - 3.0), y0 + 13.0, z0 + 4.0), 3.0, 12.0, "plastic_white", axis="y", n=2):
        vm.dec(c, "*", "grime", amount=0.4)
    if o.get("stretcher", True):
        sz = z1 - 6.0
        vm.bone("stretcher", pivot=(-4.0, y0, sz), parent="body", rotation=(-9, 0, 0))
        fr = vm.box((-4.0, y0 + 5.0, sz), (8.0, 1.2, 26.0), "alu", bone="stretcher")
        vm.box((-4.0, y0 + 6.2, sz - 2.0), (8.4, 1.4, 20.0), "plastic_white", bone="stretcher")
        sh = vm.box((-4.0, y0 + 7.0, sz - 2.0), (8.6, 0.3, 19.0), "blood", bone="stretcher")
        vm.dec(sh, "up", "nrv_puddle", kind="blood")
        for zz in (sz - 11.0, sz + 11.0):
            vm.box((-4.0, y0 + 2.0, zz), (7.0, 5.0, 0.8), "alu", bone="stretcher")
    vm.dec(vm.bmap["body"].cubes[-1], "up", "grime", amount=0.5)


def _dress_box_truck(vm, C, w, o, rng, panels, drivable):
    z0, z1 = C["bz"]
    y0, y1 = C["by"]
    for c, side in C.get("_walls", []):
        vm.dec(c, side, "nrv_lettering", text=o.get("company", "NR MOVERS"), colour=(30, 70, 140),
               box=(0.12, 0.2, 0.88, 0.42))
        vm.dec(c, side, "nrv_text", text=o.get("phone", "0120-55-81"), colour=(30, 70, 140),
               box=(0.3, 0.46, 0.7, 0.56))
        vm.wd(c, side, "nrv_band", y=(y0 + 2.5, y0 + 5.0), colour=(200, 120, 30), wear=0.3)
    gt = o.get("graffiti")
    if gt:
        for c, side in C.get("_walls", []):
            if side != "west":
                continue
            org = (C["bw"] / 2 + 0.05, y1 - 6.0, z0 + 8.0)
            strokes = NBP.text_strokes(gt, org, (0, 0, 1), (0, -1, 0), 7.0, seed=_h(gt))
            vm.wd(c, side, "nrb_spray", strokes=strokes, colour=(186, 24, 20), width=0.9, drip=0.9)
            strokes = NBP.text_strokes("->", (C["bw"] / 2 + 0.05, y1 - 16.0, z0 + 30.0), (0, 0, 1), (0, -1, 0),
                                       5.0, seed=3)
            vm.wd(c, side, "nrb_spray", strokes=strokes, colour=(186, 24, 20), width=0.9, drip=0.6)
    # 荷物（段ボール）とリフト
    if o.get("cargo", True):
        for k in range(7):
            bx = rng.uniform(-14, 14)
            bz = rng.uniform(z1 - 30, z1 - 6)
            by = y0 + 1.2 + 4.0 + (k // 3) * 7.0
            vm.box((bx, by, bz), (rng.uniform(7, 10), 7.6, rng.uniform(7, 10)), "cardboard",
                   rot=(0, rng.uniform(-20, 20), 0))
    vm.box2((-(C["bw"] / 2 - 2.0), 6.0, z1 + 1.6), (C["bw"] / 2 - 2.0, 7.2, z1 + 12.0), "diamond")
    fuel = vm.cyl((-(C["bw"] / 2 - 1.0), 12.0, -20.0), 6.0, 15.0, "alu", axis="z", n=2)
    vm.locator("fuel", (-(C["bw"] / 2 - 1.0), 12.0, -20.0))


def _dress_garbage_truck(vm, C, w, o, rng, panels, drivable):
    hw = C["bw"] / 2.0
    for b in vm.model.bones:
        for c in b.cubes:
            if c.style == "paint" and abs(c.size[0] - 1.0) < 0.01 and c.size[2] > 60:
                side = "west" if c.origin[0] > 0 else "east"
                vm.dec(c, side, "nrv_lettering", text=o.get("company", "CITY CLEAN"), colour=(232, 230, 214),
                       box=(0.15, 0.25, 0.85, 0.42))
                vm.dec(c, side, "nrv_text", text="NR-17", colour=(232, 230, 214), box=(0.4, 0.46, 0.6, 0.54))
    if "hopper" in vm.bmap:
        for c in vm.bmap["hopper"].cubes:
            if c.style == "paint":
                vm.dec(c, "south", "stripe", hazard=True, orient="v", count=2, width=0.12, colour=(230, 190, 30))
    # 屋根の橙の回転灯
    ry = C["roof"]
    vm.box((0, ry + 0.8, C["zf"] + 10.0), (22.0, 1.6, 3.6), "trim")
    for x, b in ((-6.0, "beacon_a"), (6.0, "beacon_b")):
        vm.lamp((x, ry + 2.4, C["zf"] + 10.0), (4.0, 2.4, 3.0), "a", face="up", kind="round", lit_bone=b, bezel=None)
        lc = vm.box((x, ry + 2.4, C["zf"] + 10.0), (4.1, 2.5, 3.1), "glow_a", bone=b)
        vm.dec(lc, "*", "nrv_lamp", kind="round", colour=_LAMP_RGB["a"], emit=True)
        vm.light_bones[b] = b
    if o.get("spill", True):
        z1 = C["hz"][1]
        for k in range(9):
            vm.box((rng.uniform(-16, 16), rng.uniform(1.6, 3.4), z1 + rng.uniform(4, 26)),
                   (rng.uniform(5, 9), rng.uniform(3.4, 6.0), rng.uniform(5, 9)), "trash",
                   rot=(rng.uniform(-15, 15), rng.uniform(0, 90), rng.uniform(-15, 15)))
        sp = vm.box((0, 0.06, z1 + 14.0), (34.0, 0.12, 26.0), "fuel", drop="down")
        vm.dec(sp, "up", "nrv_puddle", kind="blood")
        vm.box((6.0, 1.4, z1 + 8.0), (5.0, 2.6, 4.0), "cardboard", rot=(0, 30, 10))
        vm.box((-9.0, 0.8, z1 + 18.0), (6.0, 1.4, 3.0), "paper", rot=(0, -20, 0))


def _dress_army_truck(vm, C, w, o, rng, panels, drivable):
    hw = C["W"] / 2.0
    zf = C["zf"]
    # 格子のガードと牽引フック
    for x in np.linspace(-hw + 3.0, hw - 3.0, 7):
        vm.box((float(x), 17.0, zf - 4.0), (1.0, 14.0, 1.0), "steel_dark")
    for yy in (11.5, 23.0):
        vm.box((0, yy, zf - 4.0), (2 * hw - 4.0, 1.0, 1.0), "steel_dark")
    for s in (-1, 1):
        vm.box((s * 9.0, 9.0, zf - 4.4), (1.6, 2.4, 2.6), "steel_rusty")
        vm.dec(vm.bmap["body"].cubes[-1], "*", "grime", amount=0.5)
    # 運転室の後ろのスペアタイヤ
    vm.wheel("spare", (0.0, 26.0, C["zb"] + 2.0), 8.0, 4.0, parent="body", rim="rim_dark", rim_kind="steel",
             hubcap=True)
    vm.set_rotation("spare", (0, 90, 0))
    vm.meta["wheels"].pop("spare", None)
    # 燃料缶・荷台の弾薬箱・土嚢
    for k, zz in enumerate((-6.0, 0.0)):
        jc = vm.box((-(C["bw"] / 2 + 2.2), C["by"][0] - 3.0, zz), (3.4, 8.6, 5.6), "paint")
        vm.dec(jc, "*", "grime", amount=0.6)
    z0, z1 = C["bz"]
    y0 = C["by"][0]
    for k in range(6):
        cx = (-8.0 if k % 2 == 0 else 8.0)
        cz = z1 - 10.0 - (k // 2) * 9.0
        cr = vm.box((cx, y0 + 3.0 + (1 if k % 3 == 0 else 0) * 0.0, cz), (12.0, 6.0, 7.0), "paint",
                    rot=(0, rng.uniform(-8, 8), 0))
        vm.dec(cr, "*", "nrv_stencil", text="AMMO", colour=(222, 222, 206), box=(0.2, 0.3, 0.8, 0.7))
    for k in range(5):
        vm.box((-14.0 + k * 7.0, y0 + 2.0, z1 - 3.0), (6.6, 3.4, 4.0), "canvas", rot=(0, rng.uniform(-6, 6), 0))
        vm.box((-10.5 + k * 7.0, y0 + 5.2, z1 - 3.0), (6.6, 3.2, 4.0), "canvas", rot=(0, rng.uniform(-6, 6), 0))


def _dress_pickup(vm, C, w, o, rng, panels, drivable):
    hw = C["bw"] / 2.0
    z0, z1 = C["bz"]
    y0, y1 = C["by"]
    tb = vm.box((0, y1 + 2.6, z0 + 4.0), (2 * hw - 1.0, 5.0, 6.0), "diamond")
    vm.dec(tb, ["up", "south"], "nrb_diamond_plate")
    vm.bone("toolbox_lid", pivot=(0, y1 + 5.1, z0 + 1.0), parent="body")
    vm.box((0, y1 + 5.3, z0 + 4.0), (2 * hw - 1.0, 0.4, 6.0), "diamond", bone="toolbox_lid")
    vm.open_pose["toolbox_lid"] = {"rotation": [70.0, 0, 0]}
    vm.wheel("spare", (4.0, y0 + 2.0, z0 + 22.0), 7.0, 4.0, parent="body", rim="rim_dark", rim_kind="steel")
    vm.set_rotation("spare", (0, 0, 90))
    vm.meta["wheels"].pop("spare", None)
    jc = vm.box((-10.0, y0 + 4.5, z1 - 6.0), (5.0, 9.0, 8.0), "plastic_red")
    vm.dec(jc, ["east", "west"], "nrb_xpress")
    # ロールバーと作業灯
    rz = z0 + 1.0
    for s in (-1, 1):
        vm.rod((s * (hw - 1.0), y1, rz), (s * (hw - 2.5), C["roof"] + 1.0, rz), 1.2, "steel_dark")
    vm.box((0, C["roof"] + 1.0, rz), (2 * hw - 4.0, 1.2, 1.2), "steel_dark")
    for x in (-8.0, 8.0):
        vm.box((x, C["roof"] + 2.4, rz), (3.6, 2.6, 2.0), "trim")
        vm.lamp((x, C["roof"] + 2.4, rz - 1.1), (3.0, 2.0, 0.4), "w", face="north", kind="round",
                lit_bone="lights_extra", bezel=None)
    vm.light_bones["lights_extra"] = "extra"
    # ブルバー
    zf = C["zf"]
    for s in (-1, 1):
        vm.box((s * 8.0, 12.0, zf - 4.6), (1.4, 13.0, 1.4), "steel_dark")
        vm.rod((s * 8.0, 18.4, zf - 4.6), (s * 15.0, 12.0, zf - 3.2), 1.3, "steel_dark")
    for yy in (8.0, 18.4):
        vm.box((0, yy, zf - 4.6), (18.0, 1.3, 1.3), "steel_dark")
    for c, f in panels:
        vm.dec(c, f, "grime", amount=0.55)


# 種類ごとの寸法（単位）。運転室 C と後ろ（bw / bz / by / axles …）
_TRUCKS = {
    "ambulance": dict(W=36.0, zf=-53.0, zws=-42.0, ztop=-35.0, zb=-19.0, y0=6.0, belt=22.0, roof=35.0,
                      hood_h=(19.0, 21.4), door=(-41.4, -24.0), door_lo=7.0, R=7.0, af=-34.0, tx=14.6, tw=5.0,
                      grille_n=6, mirror="truck", bumper_style="bumper", bumper_y=(4.6, 9.0), head_y=15.0,
                      bw=38.0, bz=(-19.0, 46.0), by=(9.0, 46.0), axles=(28.0,), R2=7.0, tx2=14.6, tw2=8.0,
                      rear="doors", posts=4, box_style="paint", floor_style="diamond"),
    "box_truck": dict(W=38.0, zf=-65.0, zws=-56.0, ztop=-50.0, zb=-33.0, y0=8.0, belt=27.0, roof=40.0,
                      hood_h=(24.0, 26.0), door=(-55.4, -35.0), door_lo=17.4, R=8.0, af=-48.0, tx=15.0, tw=6.0,
                      grille_n=8, grille_style="chrome", mirror="truck", bumper_y=(5.0, 9.6), head_y=19.5,
                      bw=42.0, bz=(-31.0, 55.0), by=(10.0, 54.0), axles=(34.0,), R2=8.0, tx2=15.0, tw2=10.0,
                      rear="shutter", shutter_open=0.5, posts=7, box_style="alu", roof_style="alu"),
    "garbage_truck": dict(W=40.0, zf=-71.0, zws=-70.0, ztop=-68.0, zb=-45.0, y0=7.0, belt=19.0, roof=33.0,
                          door=(-69.0, -59.0), door_lo=8.0, R=9.0, af=-48.0, tx=16.4, tw=6.0, grille="h",
                          grille_n=5, mirror="truck", bumper_y=(5.0, 9.4), head_y=12.5, head_x=15.0,
                          bw=44.0, bz=(-37.0, 45.0), by=(10.0, 56.0), axles=(20.0, 36.0), R2=9.0, tx2=16.0,
                          tw2=10.0, hz=(44.0, 68.0), hy=(11.0, 41.0), ribs=6),
    "army_truck": dict(W=38.0, zf=-80.0, zws=-57.0, ztop=-56.0, zb=-32.0, y0=11.0, belt=30.0, roof=38.0,
                       hood_h=(26.0, 27.0), door=(-55.0, -36.0), door_lo=13.0, R=9.0, af=-66.0, tx=15.6, tw=8.0,
                       grille="v", grille_n=9, headlights="round", head_cage=True, head_y=22.0, head_x=13.0,
                       mirror="truck", bumper_y=(8.0, 12.0), vents=True, soft_top=True, split_ws=True,
                       hood_text="3-27 INF", door_text="NR ARMY", door_text_rgb=(226, 226, 214),
                       rear_window=False, rim="rim_dark", seat_style="canvas",
                       bw=40.0, bz=(-19.0, 55.0), by=(18.0, 24.0), canvas_y=48.0, axles=(20.0, 38.0), R2=9.0,
                       tx2=15.6, tw2=8.0, dual=False, bows=5),
    "pickup": dict(W=34.0, zf=-46.0, zws=-19.0, ztop=-9.0, zb=5.0, y0=6.0, belt=20.6, roof=31.0,
                   hood_h=(19.4, 20.6), door=(-18.4, 4.0), door_lo=6.5, R=7.0, af=-28.0, tx=14.0, tw=6.0,
                   grille_n=4, grille_style="chrome", mirror="car", bumper_y=(5.0, 9.0), head_y=16.5, head_x=12.0,
                   rim="rim_dark", tyre="tyre_knobby",
                   bw=34.0, bz=(7.0, 44.0), by=(14.0, 22.0), axles=(28.0,), R2=7.0, tx2=14.0, tw2=6.0, dual=False,
                   tailgate_text="NR-4X4"),
}


def _build_truck(vm: VehicleModel, kind: str, w: dict, o: dict, drivable: bool) -> None:
    C = dict(_TRUCKS[kind])
    C.update(o.get("dims") or {})
    rng = random.Random(_h(vm.key, "truck", vm.seed))
    panels: list = []
    names = ("windshield", "fl", "fr", "cab_rear", "rear_l", "rear_r")
    gst = _glass_states(w, names, rng)
    if drivable:
        gst = {k: ("intact" if v == "cracked" else v) for k, v in gst.items()}
    vm.meta.update(kind=kind)
    _truck_cab(vm, C, w, o, gst, rng, panels, drivable)
    z_end = C["bz"][1]
    hw_b = C["bw"] / 2.0
    _chassis(vm, C, C["zf"] + 2.0, z_end - 1.0, C.get("frame_y", C["R2"] + 0.6))
    if kind in ("ambulance", "box_truck"):
        C["_walls"] = []
        out = _box_body(vm, C, w, o, gst, rng, panels)
        vm.meta["box_walls"] = [id(c) for c in out["walls"]]
        _rear_end(vm, C, z_end, C["by"][0] - 2.0, hw_b, w, o, C["by"][0] + 3.0)
        vm.meta["roof_y"] = C["by"][1]
    elif kind == "pickup":
        _bed(vm, C, w, o, rng, panels)
        for s in (-1, 1):
            vm.lamp((s * (hw_b - 1.2), C["by"][1] - 3.0, z_end - 0.4), (1.4, 4.0, 1.4), "r", face="south",
                    lit_bone="lights_tail", bezel="trim")
        vm.box2((-(hw_b - 0.5), 4.6, z_end + 1.2), (hw_b - 0.5, 8.0, z_end + 3.2), "chrome")
        vm.plate((0, 6.3, z_end + 3.45), "south", o.get("plate", plate_text(_h(vm.key, "plate"), "400")),
                 kind=o.get("plate_kind", "white"))
        vm.meta["roof_y"] = C["roof"]
    elif kind == "army_truck":
        _canvas_bed(vm, C, w, o, rng, panels)
        _rear_end(vm, C, z_end + 0.8, C["by"][0] - 4.0, hw_b, w, o, C["by"][0] - 2.0)
        vm.meta["roof_y"] = C["canvas_y"]
    elif kind == "garbage_truck":
        _compactor(vm, C, w, o, rng, panels)
        vm.meta["roof_y"] = C["by"][1]
    _rear_axles(vm, dict(C, rim=C.get("rim", "rim_white")), w, drivable)
    dress = globals().get(f"_dress_{kind}")
    if dress:
        dress(vm, C, w, o, rng, panels, drivable)
    scatter_wear(vm, panels, w, rng)
    vm.locator("smoke", (0, C.get("hood_h", (C["belt"], C["belt"]))[1], (C["zf"] + C["zws"]) / 2))
    L = (z_end - C["zf"]) + 6.0
    vm.meta["size_blocks"] = [round(max(C["W"], C["bw"]) / 16, 2), round(vm.meta["roof_y"] / 16, 2), round(L / 16, 2)]


# ===========================================================================
#  8. 路線バス・バギー（乗れる）・オフロードバイク（乗れる）
# ===========================================================================
BUS_DIMS = dict(W=44.0, zf=-102.0, zr=102.0, y0=6.0, floor=8.4, belt=30.0, win_top=42.0, roof=45.0, R=8.0,
                af=-72.0, ar=56.0, tx=18.4, tw=6.0, tw2=10.0, door_f=(-97.0, -83.0), door_m=(2.0, 18.0))


def _build_bus(vm: VehicleModel, kind: str, w: dict, o: dict, drivable: bool) -> None:
    D = dict(BUS_DIMS)
    D.update(o.get("dims") or {})
    rng = random.Random(_h(vm.key, "bus", vm.seed))
    hw = D["W"] / 2.0
    sk = hw - 0.1
    zf, zr, y0, belt, wt, roof, R = D["zf"], D["zr"], D["y0"], D["belt"], D["win_top"], D["roof"], D["R"]
    P, P2 = "paint", "paint2"
    panels = []
    arches = [(D["af"] - R - 1.4, D["af"] + R + 1.4, 2 * R + 1.0), (D["ar"] - R - 1.4, D["ar"] + R + 1.4, 2 * R + 1.0)]
    doors = [D["door_f"], D["door_m"]]
    vm.meta.update(kind=kind, roof_y=roof + 5.0)
    # ---- 下の車体（両側。+X 側は扉の開口） ------------------------------------------------------------
    lug = o.get("luggage")            # (z0, z1, y0, y1): -X 側の床下の荷物入れ（ボーン luggage が上へ開く）
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        skip = [(a, b, y0) for a, b in doors] if s > 0 else []
        if s < 0 and lug:
            skip = [(lug[0], lug[1], lug[2])]
            vm.box2((-sk, lug[3], lug[0]), (-(hw - 1.4), belt, lug[1]), P)
        for c in side_band(vm, s, hw - 1.4, sk, y0, belt, zf + 3.0, zr - 3.0, arches, P, skip=skip):
            panels.append((c, side))
    if lug:
        z0_, z1_, ya, yb = lug
        vm.box2((-(hw - 9.0), ya, z0_), (-(hw - 8.0), yb, z1_), "trim")
        vm.box2((-(hw - 1.4), ya - 0.6, z0_), (-(hw - 9.0), ya, z1_), "diamond")
        vm.bone("luggage", pivot=(-hw - 0.2, yb, 0.0), parent="body")
        dr = vm.box2((-hw - 0.3, ya, z0_ + 0.2), (-hw + 0.5, yb, z1_ - 0.2), P, bone="luggage")
        panels.append((dr, "east"))
        vm.box((-hw - 0.45, ya + 1.6, (z0_ + z1_) / 2), (0.3, 0.8, 4.0), "chrome", bone="luggage")
        vm.open_pose["luggage"] = {"rotation": [0, 0, 80.0]}
        for k, (zz, st) in enumerate(((z0_ + 4.0, "leather"), ((z0_ + z1_) / 2, "cloth"), (z1_ - 4.0, "plastic_blue"))):
            vm.box((-(hw - 4.6), ya + 2.6, zz), (5.0, 5.2, 5.4), st, rot=(0, 8 * k, 0))
        # 窓の下の白い帯
        vm.wd([c for c, _ in panels if c.origin[0] * s > 0], side, "nrv_band", y=(belt - 3.0, belt), colour=(226, 226, 216))
    vm.box2((-(hw - 1.4), y0, zf + 3.0), (hw - 1.4, D["floor"], zr - 3.0), "carpet")
    vm.box2((-(hw - 1.6), 2.6, zf + 6.0), (hw - 1.6, y0, zr - 6.0), "under")
    for a0, a1, top in arches:
        vm.box2((-(D["tx"] - D["tw2"] / 2 - 0.5), y0, a0), (D["tx"] - D["tw2"] / 2 - 0.5, top + 1.0, a1), "trim")
    # ---- 窓の帯と柱 ----------------------------------------------------------------------------------
    zs = list(np.linspace(zf + 8.0, zr - 6.0, 11))
    gnames = []
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        for k, (za, zb) in enumerate(zip(zs[:-1], zs[1:])):
            za, zb = float(za), float(zb)
            in_door = s > 0 and any(a - 1.0 < (za + zb) / 2 < b + 1.0 for a, b in doors)
            vm.box2((s * (hw - 1.2), belt, za - 0.8), (s * sk, roof - 1.0, za + 0.8), P2)
            if in_door:
                continue
            nm = f"w{'l' if s > 0 else 'r'}{k}"
            gnames.append(nm)
        vm.box2((s * (hw - 1.2), belt, zs[-1] - 0.8), (s * sk, roof - 1.0, zr - 3.0), P2)
        vm.box2((s * (hw - 1.2), belt, zf + 3.0), (s * sk, roof - 1.0, zs[0] + 0.8), P2)
    gst = _glass_states(w, gnames + ["windshield", "rear", "door_f", "door_m"], rng)
    for s in (-1, 1):
        for k, (za, zb) in enumerate(zip(zs[:-1], zs[1:])):
            nm = f"w{'l' if s > 0 else 'r'}{k}"
            if nm not in gst:
                continue
            za, zb = float(za) + 0.8, float(zb) - 0.8
            at = (s * (hw - 0.5), (belt + wt) / 2, (za + zb) / 2)
            c = vm.window(at, (0.3, wt - belt - 0.4, zb - za), gst[nm], tint=True, seed=_h(vm.key, nm))
            if c is not None and float(w["blood"]) > 0.3 and s > 0 and rng.random() < 0.5:
                vm.dec(c, "east", "handprint", at=(rng.uniform(0.3, 0.7), rng.uniform(0.4, 0.7)), size=0.4)
    # ---- 屋根・空調の箱・非常口 ------------------------------------------------------------------------
    rf = vm.box2((-(hw - 0.4), roof - 3.0, zf + 2.0), (hw - 0.4, roof, zr - 2.0), P2)
    panels.append((rf, "up"))
    vm.box2((-(hw - 1.6), roof - 3.6, zf + 4.0), (hw - 1.6, roof - 3.0, zr - 4.0), "headliner")
    ac = vm.box((0, roof + 2.5, 40.0), (30.0, 5.0, 36.0), "plastic_white")
    vm.dec(ac, ["east", "west"], "nrb_slits", rows=4, box=(0.08, 0.2, 0.92, 0.8))
    vm.dec(ac, "up", "nrv_grille", kind="mesh", box=(0.1, 0.1, 0.45, 0.9), period=1.0)
    vm.bone("hatch", pivot=(0, roof + 0.2, -25.0), parent="body", rotation=(58, 0, 0))
    vm.box((0, roof + 0.6, -20.0), (10.0, 0.8, 10.0), "steel", bone="hatch")
    vm.box2((-5.0, roof - 0.2, -25.0), (5.0, roof + 0.4, -15.0), "trim")
    vm.locator("roof", (0, roof, 0))
    # ---- 前（大きな窓・行き先表示・顔・自転車ラック・ミラー） ----------------------------------------------
    fm = vm.box2((-hw, y0, zf), (hw, 20.0, zf + 3.0), P2)
    panels.append((fm, "north"))
    vm.box2((-hw, 20.0, zf), (hw, 21.4, zf + 3.0), P)
    vm.box2((-hw, wt + 0.4, zf), (hw, roof, zf + 3.0), P2)
    for s in (-1, 1):
        vm.box2((s * (hw - 1.6), 21.4, zf), (s * hw, wt + 0.4, zf + 3.0), P2)
    vm.window((0, (21.4 + wt) / 2, zf + 0.6), (2 * hw - 3.2, wt - 21.4, 0.3), gst["windshield"],
              seed=_h(vm.key, "ws"))
    vm.box((0, (21.4 + wt) / 2, zf + 0.4), (0.8, wt - 21.4, 0.5), "trim")
    vm.bone("lights_sign", parent="body")
    sgn = vm.box((0, wt + 2.2, zf - 0.1), (30.0, 3.4, 0.4), "trim")
    vm.dec(sgn, "north", "nrv_text", text=o.get("sign_off", "NOT IN SERVICE"), colour=(90, 60, 20),
           box=(0.04, 0.15, 0.96, 0.85))
    lit = vm.box((0, wt + 2.2, zf - 0.36), (30.0, 3.4, 0.12), "glow_a", bone="lights_sign")
    vm.dec(lit, "north", "nrv_text", text=o.get("sign", "NOT IN SERVICE"), colour=(255, 170, 40), emissive=True,
           box=(0.04, 0.15, 0.96, 0.85))
    vm.drop_faces(lit, ["up", "down", "east", "west", "south"])
    vm.light_bones["lights_sign"] = "sign"
    for s in (-1, 1):
        vm.lamp((s * (hw - 5.0), 12.0, zf - 0.3), (6.4, 3.4, 0.8), "w", face="north", kind="twin",
                lit_bone="lights_head")
        vm.lamp((s * (hw - 1.8), 8.6, zf - 0.3), (2.2, 2.0, 0.6), "a", face="north", lit_bone="lights_hazard",
                bezel=None)
        mx = s * (hw + 3.0)
        vm.rod((s * (hw - 1.0), roof - 2.0, zf + 2.0), (mx, roof - 6.0, zf - 4.0), 0.7, "steel_dark")
        vm.box((mx, roof - 10.0, zf - 4.0), (1.4, 8.0, 3.0), "trim")
    gr = vm.box2((-10.0, 9.0, zf - 0.4), (10.0, 15.0, zf + 0.1), "trim")
    vm.dec(gr, "north", "nrv_grille", kind="h", count=4)
    vm.box2((-(hw + 0.4), y0 - 1.0, zf - 2.4), (hw + 0.4, y0 + 3.0, zf + 0.2), "bumper")
    vm.plate((0, y0 + 1.0, zf - 2.65), "north", o.get("plate", plate_text(_h(vm.key, "plate"), "200")),
             kind="green")
    # 曲がった自転車ラック
    vm.rod((-12.0, y0 + 2.0, zf - 2.6), (-11.0, y0 + 10.0, zf - 6.0), 0.8, "steel_dark")
    vm.rod((12.0, y0 + 2.0, zf - 2.6), (10.0, y0 + 8.0, zf - 6.6), 0.8, "steel_dark")
    vm.rod((-11.0, y0 + 10.0, zf - 6.0), (10.0, y0 + 8.0, zf - 6.6), 0.8, "steel_dark")
    # ---- 後ろ --------------------------------------------------------------------------------------------
    rw = vm.box2((-hw, y0, zr - 3.0), (hw, roof, zr), P)
    panels.append((rw, "south"))
    vm.dec(rw, "south", "nrb_slits", box=(0.15, 0.62, 0.85, 0.86), rows=7)
    vm.window((0, 36.0, zr + 0.2), (24.0, 8.0, 0.3), gst["rear"], tint=True, seed=_h(vm.key, "rear"))
    for s in (-1, 1):
        vm.lamp((s * (hw - 3.0), 14.0, zr + 0.3), (3.2, 7.0, 0.7), "r", face="south", lit_bone="lights_tail")
        vm.lamp((s * (hw - 3.0), 9.0, zr + 0.3), (3.2, 2.4, 0.6), "a", face="south", lit_bone="lights_hazard",
                bezel=None)
    vm.box2((-(hw + 0.4), y0 - 1.0, zr - 0.2), (hw + 0.4, y0 + 3.0, zr + 2.2), "bumper")
    vm.plate((0, 20.0, zr + 0.25), "south", o.get("plate", plate_text(_h(vm.key, "plate"), "200")), kind="green")
    # ---- 扉（+X 側。折れ戸 2 枚ずつ、開いている） -----------------------------------------------------------
    for name, (a, b) in (("door_f", D["door_f"]), ("door_m", D["door_m"])):
        half = (b - a) / 2
        for k, (z0, sgn) in enumerate(((a, 1.0), (b, -1.0))):
            bone = f"{name}{'ab'[k]}"
            vm.bone(bone, pivot=(hw - 0.4, D["floor"], z0), parent="body")
            zc = z0 + sgn * half / 2
            fr = vm.box((hw - 0.6, (D["floor"] + wt) / 2, zc), (0.5, wt - D["floor"], half - 0.2), "trim", bone=bone)
            vm.wd(fr, "*", "nrv_frame", frame="local", lo=list(fr.origin),
                  hi=[fr.origin[i] + fr.size[i] for i in range(3)], border=0.8)
            vm.window((hw - 0.6, (D["floor"] + wt) / 2, zc), (0.3, wt - D["floor"] - 1.6, half - 1.6),
                      "intact" if gst[name] == "cracked" else gst[name], glass_bone=f"glass_{bone}",
                      smash_bone=f"smash_{bone}", frame_bone=bone, seed=_h(vm.key, bone))
            ang = float(o.get("door_angle", 78.0)) if not drivable else 0.0
            vm.set_rotation(bone, (0, -sgn * ang, 0))
        vm.box2((hw - 6.0, y0, a), (hw - 1.4, D["floor"] - 2.0, b), "diamond")
    # ---- 内装（座席の列・手すり・柱・運転席） -----------------------------------------------------------
    vm.box2((-(hw - 1.6), D["floor"], zf + 3.0), (-(hw - 12.0), 19.0, zf + 12.0), "dash")
    vm.steering((-(hw - 8.0), 21.0, zf + 15.0), radius=4.0, tilt=58.0, column=6.0)
    vm.seat((-(hw - 8.0), 17.0, zf + 22.0), 8.0, depth=7.0, back=11.0, style="seat_vinyl", base=5.0)
    vm.meta["seats"] = {"driver": [-(hw - 8.0), 17.0, zf + 22.0]}
    k = 0
    for zz in np.arange(zf + 34.0, zr - 12.0, 13.0):
        zz = float(zz)
        for s, wdt in ((-1, 16.0), (1, 8.0)):
            if s > 0 and any(a - 6.0 < zz < b + 6.0 for a, b in doors):
                continue
            x = s * (hw - 2.0 - wdt / 2)
            vm.box((x, D["floor"] + 6.8, zz), (wdt, 2.0, 7.0), "seat_bus")
            vm.box((x, D["floor"] + 11.4, zz + 3.6), (wdt, 9.0, 1.6), "seat_bus", rot=(-8, 0, 0))
            vm.box((x, D["floor"] + 3.2, zz), (wdt * 0.6, 5.4, 1.0), "steel_dark")
            k += 1
    for zz in (-60.0, -20.0, 30.0, 70.0):
        vm.box((6.0, (D["floor"] + roof - 3.6) / 2, zz), (0.7, roof - 3.6 - D["floor"], 0.7), "plastic_yellow")
    for s in (-1, 1):
        vm.box((s * 8.0, roof - 6.0, 0.0), (0.7, 0.7, 180.0), "chrome")
    # 横の広告（架空の飲み物）
    ad = vm.box((-(hw + 0.15), 22.0, 10.0), (0.3, 10.0, 50.0), "paper")
    vm.dec(ad, "east", "nrb_label", box=(0.0, 0.0, 1.0, 1.0), fill=(40, 120, 190), ink=(250, 250, 240),
           text="FROSTY FIZZ|ICE COLD", border=2, border_colour=(250, 220, 60))
    vm.dec(ad, "east", "grime", amount=0.6)
    # ---- 車輪 ---------------------------------------------------------------------------------------------
    for name, (s, az, dual) in {"fl": (1, D["af"], False), "fr": (-1, D["af"], False),
                                "rl": (1, D["ar"], True), "rr": (-1, D["ar"], True)}.items():
        vm.wheel(f"wheel_{name}", (s * (D["tx"] - (0.6 if dual else 0.0)), R, az), R, D["tw2"] if dual else D["tw"],
                 side=s, dual=dual, flat=name in w["flat"] and not drivable, rim="rim", rim_kind="steel", spokes=8)
    if float(w["blood"]) > 0.2:
        for c, f in panels[:6]:
            if f == "west":
                vm.dec(c, f, "nrv_smear", at=(0.3, 0.2), angle=4, length=0.6, width=0.12)
    scatter_wear(vm, panels, w, rng, dent_scale=0.6)
    vm.locator("smoke", (0, 30.0, zr - 10.0))
    vm.meta["size_blocks"] = [round(D["W"] / 16, 2), round((roof + 5.0) / 16, 2), round((zr - zf + 10.0) / 16, 2)]


def _build_buggy(vm: VehicleModel, kind: str, w: dict, o: dict, drivable: bool) -> None:
    """乗れるバギー: 鉄パイプのロールケージ・むき出しの後ろのエンジン・前の棘付きの鋤（ラム）・大きなタイヤ。"""
    rng = random.Random(_h(vm.key, "buggy", vm.seed))
    R, tw, tx, af, ar = 7.4, 6.0, 15.0, -19.0, 19.0
    P = "paint"
    panels = []
    vm.meta.update(kind=kind, roof_y=28.0)
    # 床・側の梁・座席
    fl = vm.box2((-9.0, 6.6, -16.0), (9.0, 7.6, 14.0), "diamond")
    vm.dec(fl, "up", "nrb_diamond_plate")
    for s in (-1, 1):
        vm.rod((s * 9.6, 7.6, -22.0), (s * 9.6, 7.6, 16.0), 1.6, "steel_dark")
        vm.rod((s * 9.6, 7.6, 16.0), (s * 8.0, 10.0, 26.0), 1.4, "steel_dark")
        vm.rod((s * 9.6, 7.6, -22.0), (s * 6.0, 9.0, -30.0), 1.4, "steel_dark")
    seat_style = "seat_vinyl"
    vm.seat((-5.0, 10.6, 1.0), 7.6, depth=7.0, back=11.0, style=seat_style, base=2.0, recline=14.0)
    vm.seat((5.0, 10.6, 1.0), 7.6, depth=7.0, back=11.0, style=seat_style, base=2.0, recline=14.0)
    vm.meta["seats"] = {"driver": [-5.0, 10.6, 1.0], "passenger": [5.0, 10.6, 1.0]}
    # ロールケージ（前の輪・後ろの輪・屋根の棒・筋交い）
    cage = "paint"
    for s in (-1, 1):
        vm.rod((s * 9.6, 8.0, 7.0), (s * 8.4, 27.0, 5.0), 1.2, cage)
        vm.rod((s * 9.6, 8.0, -14.0), (s * 8.4, 27.0, -5.0), 1.2, cage)
        vm.rod((s * 8.4, 27.0, -5.0), (s * 8.4, 27.0, 5.0), 1.2, cage)
        vm.rod((s * 8.4, 27.0, 5.0), (s * 7.6, 12.0, 22.0), 1.1, cage)
        vm.rod((s * 9.6, 8.0, -14.0), (s * 6.0, 11.0, -26.0), 1.1, cage)
    vm.rod((-8.4, 27.0, 5.0), (8.4, 27.0, 5.0), 1.2, cage)
    vm.rod((-8.4, 27.0, -5.0), (8.4, 27.0, -5.0), 1.2, cage)
    vm.rod((-8.4, 27.0, 5.0), (8.4, 9.0, 7.0), 1.0, cage)
    vm.rod((-9.0, 17.0, -10.0), (9.0, 17.0, -10.0), 1.0, cage)
    # 屋根の網と作業灯の列
    rn = vm.box((0, 27.6, 0.0), (16.0, 0.3, 9.6), "steel")
    vm.wd(rn, "*", "nrv_mesh", frame="local", axis=1, period=1.6, wire=0.25, diag=True, border=0.4,
          lo=list(rn.origin), hi=[rn.origin[i] + rn.size[i] for i in range(3)])
    vm.box((0, 28.6, -5.0), (16.0, 1.4, 1.6), "trim")
    for x in (-6.0, -2.0, 2.0, 6.0):
        vm.lamp((x, 28.6, -5.9), (3.0, 1.2, 0.4), "w", face="north", kind="round", lit_bone="lights_extra",
                bezel=None)
    vm.light_bones["lights_extra"] = "extra"
    # 前（鼻・ボンネット・灯り）
    nose = vm.box2((-7.0, 7.0, -30.0), (7.0, 13.0, -16.0), P)
    panels.append((nose, ["up", "north", "east", "west"]))
    vm.box2((-7.4, 12.8, -30.4), (7.4, 13.6, -16.0), P)
    for s in (-1, 1):
        vm.lamp((s * 5.0, 11.0, -30.4), (3.2, 3.2, 0.7), "w", face="north", kind="round", lit_bone="lights_head")
    vm.box2((-10.0, 14.2, -16.0), (10.0, 16.8, -13.0), "dash")
    vm.steering((-5.0, 16.4, -9.0), radius=2.8, tilt=30.0, column=5.0)
    # 棘付きの鋤（V 字の板 2 枚と鉄筋の棘）
    vm.bone("plow", pivot=(0, 10.0, -32.0), parent="body")
    for s in (-1, 1):
        pl = vm.box((s * 6.6, 10.0, -36.4), (14.2, 11.0, 1.2), "steel_rusty", bone="plow", rot=(0, s * 28.0, 0))
        vm.rod((s * 4.0, 8.0, -31.0), (s * 8.0, 9.0, -35.0), 1.0, "steel_dark", bone="plow")
    for k in range(8):
        x = -11.0 + k * (22.0 / 7)
        yy = 7.0 + (k % 2) * 5.0
        z0 = -38.4 + abs(x) * 0.52
        vm.rod((x, yy, z0), (x * 1.05, yy + 0.4, z0 - 6.0), 0.9, "steel_rusty", bone="plow")
        vm.box((x * 1.06, yy + 0.4, z0 - 6.4), (0.5, 0.5, 1.0), "steel", bone="plow")
    # 後ろ（むき出しのエンジン・排気管・タンク・スペアタイヤ・灯り）
    eng = vm.box2((-6.5, 8.0, 12.0), (6.5, 16.0, 22.0), "engine")
    vm.dec(eng, ["east", "west"], "nrv_grille", kind="h", count=6, box=(0.1, 0.1, 0.9, 0.6), deep=(40, 40, 42))
    vm.prism((0, 18.0, 16.0), 5.0, 3.0, "chrome", axis="y", sides=8)
    for s in (-1, 1):
        vm.rod((s * 4.0, 12.0, 22.0), (s * 5.0, 22.0, 26.0), 1.2, "exhaust")
    vm.cyl((0, 12.0, 6.6), 5.0, 14.0, "plastic_red", axis="x", n=2)
    vm.wheel("spare", (0.0, 18.0, 25.6), 6.4, 4.0, parent="body", rim="rim_dark", rim_kind="steel")
    vm.set_rotation("spare", (0, 90, 0))
    vm.meta["wheels"].pop("spare", None)
    for s in (-1, 1):
        vm.lamp((s * 6.0, 12.0, 23.0), (2.4, 1.8, 0.6), "r", face="south", lit_bone="lights_tail", kind="round")
    # サスペンション（A アームとショック）と車輪
    for name, (s, az) in {"fl": (1, af), "fr": (-1, af), "rl": (1, ar), "rr": (-1, ar)}.items():
        vm.rod((s * 8.6, 8.4, az - 2.0), (s * (tx - 2.0), R, az), 1.0, "steel_dark")
        vm.rod((s * 8.6, 8.4, az + 2.0), (s * (tx - 2.0), R, az), 1.0, "steel_dark")
        vm.rod((s * 8.4, 16.0, az), (s * (tx - 2.6), R + 1.0, az), 1.3, "chrome")
        vm.wheel(f"wheel_{name}", (s * tx, R, az), R, tw, side=s, tyre="tyre_knobby", rim="rim_dark",
                 rim_kind="steel", spokes=6, flat=(name in w["flat"]) and not drivable)
    scatter_wear(vm, panels, w, rng)
    vm.locator("smoke", (0, 18.0, 18.0))
    vm.meta["size_blocks"] = [round(2 * (tx + tw / 2) / 16, 2), round(29.0 / 16, 2), round(70.0 / 16, 2)]


def _bike_wheel(vm, name, center, R, tw, parent):
    """スポークのバイクの車輪（中の抜けたタイヤの輪・スポークの円盤・ハブ）。"""
    cx, cy, cz = (float(v) for v in center)
    vm.bone(name, pivot=(cx, cy, cz), parent=parent)
    vm.meta["wheels"][name] = {"center": [cx, cy, cz], "radius": R, "width": tw}
    cs = vm.prism((cx, cy, cz), R * 2, tw, "tyre_knobby", axis="x", sides=12, bone=name)
    vm.wd(cs, "*", "nrv_disc", frame="local", c=[cx, cy, cz], axis=0, ri=R * 0.72, ro=R * 1.2, shade=False)
    vm.wd(cs, "lr", "nrv_tyreside", frame="local", c=[cx, cy, cz], r=R, ri=R * 0.72)
    sp = vm.box((cx, cy, cz), (0.5, R * 1.46, R * 1.46), "rim", bone=name)
    vm.wd(sp, "*", "nrv_disc", frame="local", c=[cx, cy, cz], axis=0, ri=R * 0.62, ro=R * 0.73, spokes=12,
          spoke_w=0.22, hub=0.9)
    vm.box((cx, cy, cz), (tw + 0.6, 1.4, 1.4), "hub", bone=name, rot=(45, 0, 0))


def _build_dirt_bike(vm: VehicleModel, kind: str, w: dict, o: dict, drivable: bool) -> None:
    """乗れるオフロードバイク。fork（ハンドル・前輪）は steer_head（キャスター角）の子で、fork の Y 回転で切る。"""
    R, tw = 7.0, 2.4
    zf_ax, zr_ax = -15.5, 14.5
    rake = 26.0
    hy, hz = 19.0, -9.5                     # ステアリングヘッド
    P = "paint"
    panels = []
    vm.meta.update(kind=kind, roof_y=22.0)
    # フレームとエンジン
    vm.rod((0, hy, hz), (0, 9.0, -2.0), 1.3, "steel_dark")
    vm.rod((0, hy, hz), (0, 16.0, 5.0), 1.2, "steel_dark")
    vm.rod((0, 16.0, 5.0), (0, 15.6, 16.0), 0.9, "steel_dark")
    vm.rod((0, 9.0, 4.0), (0, 15.6, 12.0), 0.9, "steel_dark")
    eng = vm.box((0, 8.6, 0.0), (5.0, 6.4, 8.0), "engine")
    vm.dec(eng, ["east", "west"], "nrv_grille", kind="h", count=5, box=(0.1, 0.05, 0.6, 0.5), deep=(36, 36, 38))
    vm.box((0, 13.0, -2.2), (4.2, 3.4, 4.0), "engine")
    vm.rod((-1.6, 12.0, -4.6), (-2.6, 6.0, -6.0), 1.0, "exhaust")
    vm.rod((-2.6, 6.0, -6.0), (-3.4, 10.0, 6.0), 1.0, "exhaust")
    vm.rod((-3.4, 10.0, 6.0), (-3.4, 14.0, 14.0), 1.0, "exhaust")
    vm.cyl((-3.4, 14.2, 14.0), 2.6, 7.0, "alu", axis="z", n=2)
    # タンク・座席・カウル・後ろのフェンダー・ゼッケン
    tk = vm.box((0, 17.2, -3.0), (6.0, 3.8, 8.6), P)
    panels.append((tk, ["up", "east", "west"]))
    vm.box((0, 17.0, 6.0), (4.8, 1.6, 15.0), "seat_vinyl")
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        sp = vm.box((s * 2.8, 13.0, 8.0), (0.5, 4.8, 7.0), "plastic_white")
        vm.dec(sp, side, "nrv_text", text=o.get("number", "27"), colour=(24, 24, 26), box=(0.2, 0.2, 0.8, 0.8))
        vm.box((s * 3.2, 15.8, -4.0), (0.5, 4.0, 6.0), P)
    fen = vm.box((0, 16.6, 16.0), (4.2, 0.6, 10.0), "plastic_white", rot=(-14, 0, 0))
    vm.lamp((0, 16.4, 20.8), (2.0, 1.2, 0.5), "r", face="south", lit_bone="lights_tail", bezel=None)
    vm.plate((0, 14.2, 21.0), "south", o.get("plate", "NRC 125|7-21"), kind="white", size=(4.0, 2.4, 0.3))
    for s in (-1, 1):
        vm.box((s * 2.6, 8.0, 3.0), (2.4, 0.6, 1.0), "steel_dark")
        vm.rod((s * 1.6, 8.6, 2.0), (s * 1.6, R, zr_ax), 0.9, "steel_dark")
    vm.rod((0, 15.6, 8.0), (0, 9.0, 10.0), 1.0, "chrome")
    vm.box((1.4, R + 0.6, (2.0 + zr_ax) / 2), (0.4, 1.2, zr_ax - 2.0), "chain")
    vm.meta["seats"] = {"rider": [0.0, 17.8, 5.0]}
    # 前（キャスター角の付いた steer_head → fork → wheel_f）
    vm.bone("steer_head", pivot=(0, hy, hz), parent="body", rotation=(-rake, 0, 0))
    vm.bone("fork", pivot=(0, hy, hz), parent="steer_head")
    L = (hy - R) / math.cos(math.radians(rake))
    ay = hy - L
    for s in (-1, 1):
        vm.box((s * 1.7, hy - L / 2, hz), (0.9, L, 0.9), "chrome", bone="fork")
        vm.box((s * 1.7, hy - L * 0.75, hz), (1.3, L * 0.5, 1.3), "steel_dark", bone="fork")
    vm.box((0, hy - 0.5, hz), (4.6, 1.0, 1.6), "steel_dark", bone="fork")
    vm.box((0, hy - 4.0, hz), (4.6, 1.0, 1.6), "steel_dark", bone="fork")
    vm.box((0, hy + 1.6, hz + 0.6), (13.0, 0.7, 0.7), "steel_dark", bone="fork")
    for s in (-1, 1):
        vm.box((s * 5.6, hy + 1.6, hz + 0.6), (2.0, 1.0, 1.0), "rubber", bone="fork")
    vm.box((0, ay + R + 1.4, hz - 0.6), (3.6, 0.5, 9.0), "plastic_white", bone="fork", rot=(8, 0, 0))
    cw = vm.box((0, hy - 2.6, hz - 1.6), (5.0, 5.6, 0.5), "plastic_white", bone="fork")
    vm.dec(cw, "north", "nrv_text", text=o.get("number", "27"), colour=(24, 24, 26), box=(0.2, 0.5, 0.8, 0.9))
    vm.lamp((0, hy - 1.6, hz - 2.0), (2.6, 1.8, 0.5), "w", face="north", kind="round", lit_bone="lights_head",
            bone="fork", bezel=None)
    if "lights_head" in vm.bmap:
        vm.bmap["lights_head"].parent = "fork"
    _bike_wheel(vm, "wheel_f", (0, ay, hz), R, tw, "fork")
    _bike_wheel(vm, "wheel_r", (0, R, zr_ax), R, tw + 0.6, "body")
    vm.meta["steer"] = {"bone": "fork", "axis": "y", "head": [0, hy, hz], "rake": rake}
    scatter_wear(vm, panels, w, random.Random(_h(vm.key, "bike")))
    vm.meta["size_blocks"] = [round(14.0 / 16, 2), round(22.0 / 16, 2), round(40.0 / 16, 2)]


# ===========================================================================
#  9. 入口
# ===========================================================================
# 種類 → (組み立て関数の名前, 既定の塗装 (paint, paint2, paint3), 既定のアトラス, 既定の密度の上限)
KINDS: Dict[str, dict] = {
    "sedan": dict(fn="_build_car", paint=("paint_red", "paint_white", "paint_black"), atlas=(512, 512)),
    "taxi": dict(fn="_build_car", paint=("paint_yellow", "paint_white", "paint_black"), atlas=(512, 512)),
    "police": dict(fn="_build_car", paint=("paint_black", "paint_white", "paint_black"), atlas=(512, 512)),
    "ambulance": dict(fn="_build_truck", paint=("paint_white", "paint_white", "paint_black"), atlas=(512, 512)),
    "box_truck": dict(fn="_build_truck", paint=("paint_white", "paint_white", "paint_black"), atlas=(1024, 1024)),
    "garbage_truck": dict(fn="_build_truck", paint=("paint_green", "paint_white", "paint_black"),
                          atlas=(1024, 1024)),
    "army_truck": dict(fn="_build_truck", paint=("paint_olive", "paint_olive", "paint_black"), atlas=(512, 512)),
    "pickup": dict(fn="_build_truck", paint=("paint_green", "paint_white", "paint_black"), atlas=(512, 512)),
    "bus": dict(fn="_build_bus", paint=("paint_blue", "paint_white", "paint_black"), atlas=(1024, 1024)),
    "buggy": dict(fn="_build_buggy", paint=("paint_orange", "paint_white", "paint_black"), atlas=(512, 512)),
    "dirt_bike": dict(fn="_build_dirt_bike", paint=("paint_red", "paint_white", "paint_black"), atlas=(256, 256)),
}
KIND_OPTIONS = {
    "*": "dims（寸法の上書き）、plate（ナンバーの文字 'ABC 500|12-34'）、plate_kind（white/yellow/green）",
    "sedan / taxi / police": "lit_head（点く前照灯 ('l','r') の部分集合）、rear_text（後ろの窓の埃の字）、"
                             "door_text / door_badge（扉の字・星）、seat_style、bag（後席の鞄）",
}


def build_vehicle(kind: str, *, key: Optional[str] = None, identifier: Optional[str] = None, paint=None,
                  paint2=None, paint3=None, wear=None, seed: int = 0, atlas=None, max_scale: Optional[float] = None,
                  drivable: bool = False, options: Optional[dict] = None) -> VehicleModel:
    """乗り物 1 台を組み立てる（塗りは vm.paint()）。"""
    if kind not in KINDS:
        raise KeyError(f"未知の乗り物 {kind!r}（{sorted(KINDS)}）")
    spec = KINDS[kind]
    w = norm_wear(wear, drivable=drivable)
    p1, p2, p3 = spec["paint"]
    pal = vehicle_styles(paint or p1, w, paint2=paint2 or p2, paint3=paint3 or p3)
    key = key or kind
    vm = VehicleModel(key, identifier or f"geometry.nr.prop.{key}", seed=seed or _h("vehicle", key),
                      atlas=atlas or spec["atlas"], max_scale=max_scale or spec.get("max_scale", 4.0), palette=pal)
    o = dict(options or {})
    fn = globals()[spec["fn"]]
    fn(vm, kind, w, o, drivable)
    if w["overturned"] and not drivable:
        top = float(vm.meta.get("roof_y", 26.0))
        vm.bmap["root"].pivot = [0.0, round(top / 2.0, 3), 0.0]
        vm.set_rotation("root", (0, 0, 180))
        vm.face_light = False
    vm.meta["wear"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in w.items()}
    vm.meta["drivable"] = bool(drivable)
    vm.meta.setdefault("kind", kind)
    return vm


# ===========================================================================
#  10. 確認用の絵（nr_preview。窓は「窓なし」と「窓を不透明に」の 2 枚を混ぜて半透明に見せる）
# ===========================================================================
def preview(vm: VehicleModel, img: Image.Image, view="three_quarter", size: int = 360, props: Optional[dict] = None,
            t: float = 0.0, ss: int = 2, bg=(38, 40, 46), glass_alpha: float = 0.5, extra_hidden=(),
            pose=None) -> Image.Image:
    import nr_preview as V
    props = dict({"nr:lights": 1, "nr:alarm": 0, "nr:glass": 0, "nr:open": 0}, **(props or {}))
    geo = {"format_version": "1.16.0", "minecraft:geometry": [vm.to_json()]}
    body_rules, glass_rules = part_visibility_rules(vm)
    names = vm.bone_names()
    ctx_q = {"life_time": t}
    hid = set(V.part_visibility_hidden(body_rules, names, properties=props, queries=ctx_q)) | set(extra_hidden)
    a = np.array(img)
    body = V.render(geo, a, view=view, size=size, hidden=sorted(hid), hide_mode="exact", ss=ss, bg=bg, floor=False,
                    pose=pose)
    gl_vis = [b for b in vm.glass_bones if props.get("nr:glass", 0) == 0]
    if not gl_vis:
        return body
    a2 = a.copy()
    for bn in gl_vis:
        for c in vm.bmap[bn].cubes:
            for f in FACES:
                r = c.rects.get(f)
                if r and r[2] > 0:
                    x, y, w_, h_ = r
                    sub = a2[y:y + h_, x:x + w_]
                    sub[..., 3] = np.where(sub[..., 3] > 0, 255, 0)
    hid2 = hid - set(gl_vis)
    full = V.render(geo, a2, view=view, size=size, hidden=sorted(hid2), hide_mode="exact", ss=ss, bg=bg, floor=False,
                    pose=pose)
    b0 = np.asarray(body.convert("RGB"), f32)
    b1 = np.asarray(full.convert("RGB"), f32)
    out = b0 + (b1 - b0) * glass_alpha
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGB")


# ===========================================================================
#  11. 自己検査（python3 nr_vehicle_models.py [--sheet]）
# ===========================================================================
def check_textures(vm: VehicleModel, img: Image.Image) -> List[str]:
    """アルファの約束（rendering.md M2・M3・M7）: 窓のボーン以外の texel は α ∈ {0, 16(発光), 255}、
    α 0 は RGB も 0。窓の texel は半透明（60〜238）か 0。違反を文字列で返す。"""
    a = np.array(img)
    probs = []
    glass = np.zeros(a.shape[:2], bool)
    for bn in vm.glass_bones:
        for c in vm.bmap[bn].cubes:
            for f in FACES:
                r = c.rects.get(f)
                if r and r[2] > 0:
                    glass[r[1]:r[1] + r[3], r[0]:r[0] + r[2]] = True
    al = a[..., 3]
    body_bad = (~glass) & ~np.isin(al, (0, NP.EMISSIVE_ALPHA, 255))
    if body_bad.any():
        probs.append(f"{vm.key}: 本体の texel に中間のα {sorted(set(al[body_bad].tolist()))[:6]}")
    zero_rgb = (al == 0) & (a[..., :3].max(-1) > 0)
    if zero_rgb.any():
        probs.append(f"{vm.key}: α 0 なのに RGB が 0 でない texel {int(zero_rgb.sum())}")
    gl_bad = glass & (al > 0) & ((al < 60) | (al > 238))
    if gl_bad.any():
        probs.append(f"{vm.key}: 窓の texel のα が範囲外 {int(gl_bad.sum())}")
    return probs


def _selftest(sheet: bool = False) -> int:
    import time as _t
    errs = []
    cells = []
    for kind in KINDS:
        t0 = _t.time()
        drv = kind in ("buggy", "dirt_bike")
        vm = build_vehicle(kind, seed=3, drivable=drv)
        vm.pack()
        img = vm.paint()
        names = set(vm.bone_names())
        need = {"wheel_f", "wheel_r"} if kind == "dirt_bike" else {"wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"}
        if not need <= names:
            errs.append(f"{kind}: 車輪のボーンが足りない {sorted(need - names)}")
        if kind != "dirt_bike" and "steering_wheel" not in names:
            errs.append(f"{kind}: steering_wheel が無い")
        if vm.cube_count() > 700:
            errs.append(f"{kind}: キューブ {vm.cube_count()}")
        errs += check_textures(vm, img)
        doc = vm.to_json()
        for b in doc["bones"]:
            for c in b.get("cubes", []):
                for f, uv in c["uv"].items():
                    u, v = uv["uv"]
                    w, h = uv["uv_size"]
                    if u < 0 or v < 0 or u + w > vm.tex_w or v + h > vm.tex_h:
                        errs.append(f"{kind}: UV がはみ出す {b['name']}.{f}")
        print(f"  {kind:14s} {vm.cube_count():4d} cubes  {vm.tex_w}x{vm.tex_h}  密度 {vm.scale:.2f}  "
              f"窓 {len(vm.glass_bones)}  灯り {len(vm.light_bones)}  {_t.time() - t0:.1f}s")
        if sheet:
            cells.append((kind, preview(vm, img, view=(35.0, 20.0), size=300)))
    if sheet and cells:
        import nr_preview as V
        out = os.path.join(os.environ.get("NR_SCRATCH", os.path.join(os.path.dirname(TOOLS), "build_preview",
                                                                       "nightrunner")), "vehicles.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        V.contact_sheet(cells, cols=4, title="nr_vehicle_models (kinds)").save(out)
        print(f"  確認画像: {out}")
    for e in errs:
        print("  NG", e)
    print(f"nr_vehicle_models: {len(KINDS)} 種、{'問題なし' if not errs else f'{len(errs)} 件の問題'}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(_selftest(sheet="--sheet" in sys.argv[1:]))
