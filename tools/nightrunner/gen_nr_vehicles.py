# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 乗れる乗り物（バギー・セダン・ピックアップ・オフロードバイク）。

`nr_spec.VEHICLES`（nr_spec_catalog の「乗り物」の節）の全部について書く（このファイルが持ち主。走るたびに
下のフォルダの自分のファイルを消してから書き直す）:

| 書くもの | 場所 |
|---|---|
| ジオメトリ `geometry.nr.veh.<key>`（1.16.0、nr_common.write_geometry） | RP `models/entity/nr/vehicles/<key>.geo.json` |
| テクスチャ（血の段階 nr:blood 0..3 の 4 枚: `<key>` / `<key>_b1` / `_b2` / `_b3`） | RP `textures/nr/vehicles/` |
| クライアントエンティティ（format 1.10.0） | RP `entity/vehicles/<key>.entity.json` |
| レンダーコントローラ `controller.render.nr.veh.<key>`（本体）と `.<key>.glass`（窓） | RP `render_controllers/nr_vehicles.render_controllers.json` |
| アニメ `animation.nr.veh.<key>.drive`（車輪・ハンドル・サスペンション・傾き） | RP `animations/nr_vehicles.animation.json` |
| BP エンティティ `nr:veh_<key>`（format 1.21.120） | BP `entities/vehicles/<key>.json` |
| 乗り物の表（spec の数値 + 形: 鼻先・後ろ・幅・座席） | BP `scripts/data/vehicles.js`（`nr_common.write_data_js`） |
| 名前（エンティティ・スポーンエッグ・乗る操作・操作の案内） | `.frag/lang/gen_nr_vehicles.json` |
| 確認用のコンタクトシート（4 台の 3/4、上の段 = きれい・灯り、下の段 = 血 3） | `build_preview/nightrunner/vehicles_drivable.png` |

車体は `nr_vehicle_models.build_vehicle(kind, drivable=True, …)`（gen_nr_props と共有。読むだけ）。

■ BP（vanilla の形。〔BS:horse/camel/boat/minecart/strider.json〕）:
  `minecraft:rideable`（座席は車体の meta["seats"]。先頭が運転席 = controlling_seat 0、family_types [player]、
  座席 i は「乗っている人数 ≥ i」で使える camel と同じ min/max_rider_count の並べ方）・
  `minecraft:input_ground_controlled`（乗り手の入力で走る。馬・ラクダと同じ）・`movement` + `movement.basic`・
  `physics`・`collision_box`・`custom_hit_test`（乗るとき触れる範囲を少し広く）・`variable_max_auto_step`
  （1 段の縁石を乗り越える。ラクダと同じ）・`health`（車の耐久）・`damage_sensor`（落下・窒息・溺れは無し、
  プレイヤーの素手は半分）・`pushable` false・`knockback_resistance`・`persistent`・
  `type_family [nr_vehicle, nr_drivable, inanimate]`・`nr:despawn`（instant_despawn）。
  `is_stackable` は付けない（上に乗れる箱にしない）。
  プロパティ（int・client_sync）: `nr:blood` 0..3（轢いた血の段階。テクスチャを切り替える）、`nr:lights` 0..1
  （前照灯・尾灯・作業灯）。イベント `nr:despawn` / `nr:lights_on` / `nr:lights_off`。
■ RP（rendering.md §3・§4・§11）: 本体 `entity_emissive_alpha`、割れていない窓は 2 本目の render controller
  （`entity_alphablend`）。血は**テクスチャの差し替え**（`Array.skins[q.property('nr:blood')]`）で、
  車体の前の面・ボンネット・鋤・タイヤに描く（浮いた板のデカールより z ファイトが無く形に沿う）。
  アニメは client の変数で: 車輪は `q.ground_speed`（前後は `q.movement_direction` と向きの内積）で転がし、
  ハンドル・前輪（バイクはフォーク）は向きの変化（`q.body_y_rotation` の差 / 秒）で切る。
  サスペンションの上下・加減速の前後の傾き（ブレーキで鼻先が沈む）・バイクの傾き・ブレーキで尾灯。
  回転の符号は nr_preview の規則（rx を増やすと前へ転がる、ry 正で右へ切る、rz 負でハンドルを右へ回す）。

使い方: `python3 tools/nightrunner/gen_nr_vehicles.py [--only key,key] [--no-preview] [--sheet-only]`
（普通は build_nr.py から）。
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
import time
from typing import Dict, List

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from nr_common import (SCRATCH, frag, load_json, rp_path, bp_path, write_data_js,  # noqa: E402
                       write_geometry, write_json)
import nr_paint as NP  # noqa: E402
import nr_spec as S  # noqa: E402
import nr_vehicle_models as VM  # noqa: E402

PRODUCER = "gen_nr_vehicles"
GEO_DIR = rp_path("models", "entity", "nr", "vehicles")
TEX_DIR = rp_path("textures", "nr", "vehicles")
TEX_REF = "textures/nr/vehicles/"
ENT_RP_DIR = rp_path("entity", "vehicles")
ENT_BP_DIR = bp_path("entities", "vehicles")
RC_PATH = rp_path("render_controllers", "nr_vehicles.render_controllers.json")
ANIM_PATH = rp_path("animations", "nr_vehicles.animation.json")
CACHE_PATH = os.path.join(HERE, ".cache", "vehicle_assets.json")
SHEET_PATH = os.path.join(SCRATCH, "vehicles_drivable.png")
ENTITY_FORMAT = "1.21.120"
CLIENT_FORMAT = "1.10.0"
MAX_CUBES = 700                 # DESIGN.md §11
BLOOD_LEVELS = 3                # nr:blood 0..3（0 = きれい）
SEAT_DROP = 0.12                # 座面の上の面から rideable の座席の位置を下げる量（ブロック。vanilla の馬・ラクダの鞍と座席の差）
MAT_BODY = "entity_emissive_alpha"
MAT_GLASS = "entity_alphablend"
FAMILY = ["nr_vehicle", "nr_drivable", "inanimate"]
PROPERTIES = ("nr:blood", "nr:lights")
INTERACT_TEXT = "action.interact.nr.drive"


def vehicle_spec(key: str) -> dict:
    return S.vehicle(key)


# ===========================================================================
#  1. 轢いた血（テクスチャの差分。nr_paint のデカール nrveh_roadgore）
# ===========================================================================
def d_roadgore(fc, d):
    """轢いた血と肉片。段階 level 1..3 で前から後ろへ広がる。O/A/B/N 付き（frame="design"）で、
    texel の組み立て座標から「鼻先からの距離」「面の向き」「高さ」を見て塗る（3D ノイズなので面の継ぎ目で揃う）。"""
    P = VM._wp(fc, d)
    N = np.asarray(d.get("N", (0, 0, 0)), np.float32)
    lv = int(d.get("level", 1))
    z0 = float(d["front"])
    L = max(1.0, float(d["length"]))
    top = max(1.0, float(d["top"]))
    seed = int(d.get("seed", 0))
    t = np.clip((P[..., 2] - z0) / L, 0.0, 1.5)
    reach = (0.0, 0.16, 0.30, 0.52)[lv]
    nf = max(0.0, -float(N[2]))       # 前（-Z）を向いた面
    nu = max(0.0, float(N[1]))        # 上
    nx = abs(float(N[0]))             # 横
    nb = max(0.0, float(N[2]))        # 後ろ（鋤の裏・座席の背など。わずかに）
    if d.get("wheel"):
        # タイヤは踏んだ血を転がして付ける: 接地面（トレッド）に筋、横の面はわずか
        wgt = np.full(t.shape, (0.0, 0.18, 0.36, 0.55)[lv] * (1.0 - 0.75 * nx), np.float32)
    else:
        wgt = (nf * np.clip(1.0 - t / (reach * 1.35), 0, 1)
               + nu * np.clip(1.0 - t / reach, 0, 1) * 0.9
               + nx * np.clip(1.0 - t / (reach * 0.8), 0, 1) * 0.75
               + nb * np.clip(1.0 - t / (reach * 0.5), 0, 1) * 0.35)
    hy = np.clip(1.3 - P[..., 1] / top, 0.4, 1.3)            # 低い所（バンパー・鋤の高さ）ほど濃い
    n1 = NP.fbm3(P[..., 0] * 0.21, P[..., 1] * 0.21, P[..., 2] * 0.21, seed, 3)
    n2 = NP.fbm3(P[..., 0] * 0.95, P[..., 1] * 0.95, P[..., 2] * 0.95, seed + 7, 2)
    dens = wgt * hy * (0.3 + 1.2 * n1) + (n2 - 0.5) * 0.35
    thr = (9.0, 0.80, 0.62, 0.46)[lv]
    m = np.clip((dens - thr) / 0.07, 0, 1)
    specks = ((n2 > 0.75 - 0.025 * lv) & (wgt * hy > 0.22)).astype(np.float32)
    m = np.maximum(m, specks * 0.9)
    if not m.any():
        return
    age = np.clip(n1 * 1.5 - 0.25, 0, 1)[..., None]
    col = NP._BLOOD_HI * (1.0 - age) + NP._BLOOD_DK * age
    fc.paint(m, col, 0.95)
    if lv >= 2 and not d.get("wheel"):
        n3 = NP.fbm3(P[..., 0] * 1.7, P[..., 1] * 1.7, P[..., 2] * 1.7, seed + 13, 2)
        chunk = ((n3 > 0.79 - 0.025 * lv) & (wgt * hy > 0.5)).astype(np.float32)
        fc.paint(chunk, (150, 62, 56), 0.9)            # 肉片
        fc.paint(chunk * (n2 > 0.6), (214, 196, 170), 0.8)   # 骨のかけら
    fc.drips_from((m > 0.6).astype(np.float32), 0.35 + 0.25 * lv, seed + 3)


NP.DECALS["nrveh_roadgore"] = d_roadgore


def _gore_decals(vm: VM.VehicleModel, level: int) -> Dict[int, dict]:
    """全キューブの見える面に血のデカールを足す。戻り値は元の decals（_restore で戻す）。"""
    lo, hi = vm.bounds()
    snap = {}
    wheel_cubes = set()
    for b in vm.bones:
        if b.name.startswith("wheel"):
            wheel_cubes.update(id(c) for c in b.cubes)
    for c in vm.all_cubes():
        faces = vm._live_faces(c)
        if not faces:
            continue
        snap[id(c)] = (c, dict(c.decals))
        vm.wd(c, faces, "nrveh_roadgore", frame="design", level=level, front=float(lo[2]),
              length=float(hi[2] - lo[2]), top=float(hi[1]), seed=VM._h(vm.key, "gore"),
              wheel=id(c) in wheel_cubes)
    return snap


def _restore(snap: Dict[int, dict]) -> None:
    for c, dec in snap.values():
        c.decals = dec


# ===========================================================================
#  2. 組み立て・塗り
# ===========================================================================
def build_vehicle_model(v: dict) -> VM.VehicleModel:
    look = v["look"]
    vm = VM.build_vehicle(v["kind"], key=v["key"], identifier=v["geometry"], paint=look.get("paint"),
                          paint2=look.get("paint2"), paint3=look.get("paint3"), wear=look.get("wear"),
                          seed=int(look.get("seed", 0)), drivable=True, options=look.get("options"))
    n = vm.cube_count()
    if n > MAX_CUBES:
        raise ValueError(f"{v['key']}: キューブ {n} 個（上限 {MAX_CUBES}）")
    vm.pack()
    return vm


def paint_all(vm: VM.VehicleModel) -> List[Image.Image]:
    """[きれい, 血 1, 血 2, 血 3]。"""
    imgs = [vm.paint()]
    for lv in range(1, BLOOD_LEVELS + 1):
        snap = _gore_decals(vm, lv)
        try:
            imgs.append(vm.paint())
        finally:
            _restore(snap)
    for im in imgs:
        probs = VM.check_textures(vm, im)
        if probs:
            raise ValueError("; ".join(probs))
    if max(vm.tex_w, vm.tex_h) > 512:
        raise ValueError(f"{vm.key}: テクスチャ {vm.tex_w}x{vm.tex_h}（上限 512）")
    return imgs


# ===========================================================================
#  3. 形（スクリプト向け）と座席
# ===========================================================================
def shape_of(v: dict, vm: VM.VehicleModel) -> dict:
    """鼻先・後ろ・半幅・高さ（ブロック、エンティティの位置から）と座席・車輪。"""
    lo, hi = vm.bounds()
    seats = seat_positions(v, vm)
    wheels = vm.meta.get("wheels") or {}
    return {
        "front": round(-float(lo[2]) / 16.0, 3), "back": round(float(hi[2]) / 16.0, 3),
        "half_w": round(max(-float(lo[0]), float(hi[0])) / 16.0, 3), "height": round(float(hi[1]) / 16.0, 3),
        "seats": [{"name": n, "pos": p} for n, p in zip(v["seats"], seats)],
        "wheel_radius": round(max([w["radius"] for w in wheels.values()] or [7.0]) / 16.0, 3),
        "smoke": [round(x / 16.0, 3) for x in (vm.locators.get("smoke", ("body", [0.0, 16.0, 0.0]))[1])],
    }


def seat_positions(v: dict, vm: VM.VehicleModel) -> List[List[float]]:
    """rideable の座席の位置（ブロック、エンティティ空間: +Z が前、-X が右）。
    小道具空間（-Z が前、-X が右）の座面の上の面 (x, y, z) → [x/16, y/16 - SEAT_DROP, -z/16]。"""
    meta = vm.meta.get("seats") or {}
    out = []
    for name in v["seats"]:
        if name in v["extra_seats"]:
            x, y, z = v["extra_seats"][name]
        elif name in meta:
            x, y, z = meta[name]
        else:
            raise KeyError(f"{v['key']}: 座席 {name} の位置が無い（meta {sorted(meta)} / extra_seats）")
        out.append([round(float(x) / 16.0, 3) + 0.0, round(float(y) / 16.0 - SEAT_DROP, 3) + 0.0,
                    round(-float(z) / 16.0, 3) + 0.0])
    return out


# ===========================================================================
#  4. BP エンティティ
# ===========================================================================
def _properties() -> dict:
    return {
        "nr:blood": {"type": "int", "range": [0, BLOOD_LEVELS], "default": 0, "client_sync": True},
        "nr:lights": {"type": "int", "range": [0, 1], "default": 0, "client_sync": True},
    }


def bp_entity(v: dict, vm: VM.VehicleModel) -> dict:
    seats = seat_positions(v, vm)
    n = len(seats)
    seat_rows = [{"position": p, "min_rider_count": i, "max_rider_count": n} for i, p in enumerate(seats)]
    cw, ch = v["collision"]
    light = v["weight"] == "light"
    return {
        "format_version": ENTITY_FORMAT,
        "minecraft:entity": {
            "description": {"identifier": v["id"], "is_spawnable": True, "is_summonable": True,
                            "properties": _properties()},
            "component_groups": {"nr:despawn": {"minecraft:instant_despawn": {}}},
            "components": {
                "minecraft:type_family": {"family": list(FAMILY)},
                "minecraft:health": {"value": v["health"], "max": v["health"]},
                "minecraft:damage_sensor": {"triggers": [
                    {"cause": "fall", "deals_damage": "no"},
                    {"cause": "suffocation", "deals_damage": "no"},
                    {"cause": "drowning", "deals_damage": "no"},
                    {"cause": "contact", "deals_damage": "no"},
                    {"on_damage": {"filters": {"test": "is_family", "subject": "other", "value": "player"}},
                     "cause": "entity_attack", "deals_damage": "yes", "damage_multiplier": 0.5},
                ]},
                "minecraft:collision_box": {"width": cw, "height": ch},
                "minecraft:custom_hit_test": {"hitboxes": [
                    {"width": v["hit_width"], "height": ch, "pivot": [0, round(ch / 2, 3), 0]}]},
                "minecraft:physics": {},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                "minecraft:knockback_resistance": {"value": 0.6 if light else 1.0},
                "minecraft:movement": {"value": v["speed"]},
                "minecraft:movement.basic": {},
                "minecraft:input_ground_controlled": {},
                "minecraft:variable_max_auto_step": {"base_value": 0.5625, "controlled_value": v["step"],
                                                     "jump_prevented_value": 0.5625},
                "minecraft:rideable": {
                    "seat_count": n, "controlling_seat": 0, "crouching_skip_interact": True,
                    "family_types": ["player"], "interact_text": INTERACT_TEXT, "pull_in_entities": False,
                    "seats": seat_rows if n > 1 else seat_rows[0],
                },
                "minecraft:persistent": {},
            },
            "events": {
                "nr:despawn": {"add": {"component_groups": ["nr:despawn"]}},
                "nr:lights_on": {"set_property": {"nr:lights": 1}},
                "nr:lights_off": {"set_property": {"nr:lights": 0}},
            },
        },
    }


# ===========================================================================
#  5. RP: クライアントエンティティ・レンダーコントローラ・アニメ
# ===========================================================================
def _texture_names(v: dict) -> Dict[str, str]:
    out = {"default": TEX_REF + v["key"]}
    for i in range(1, BLOOD_LEVELS + 1):
        out[f"b{i}"] = TEX_REF + f"{v['key']}_b{i}"
    return out


def _radii(vm: VM.VehicleModel) -> List[float]:
    """車輪の半径（単位）の種類。同じ半径の車輪は同じ変数で転がす。"""
    out = []
    for w in (vm.meta.get("wheels") or {}).values():
        r = round(float(w["radius"]), 2)
        if r not in out:
            out.append(r)
    return out or [7.0]


def pre_animation(v: dict, vm: VM.VehicleModel) -> List[str]:
    """毎フレームの client 変数（速さ・前後・転がり・切れ角・加速度・上下動）。"""
    bike = v["kind"] == "dirt_bike"
    lines = [
        # 前後: 動いた向きと車体の向きの内積（後退なら負）
        "v.nr_dir = q.movement_direction(0) * -math.sin(q.body_y_rotation) + q.movement_direction(2) * "
        "math.cos(q.body_y_rotation);",
        "v.nr_gs = q.ground_speed * (v.nr_dir < -0.25 ? -1.0 : 1.0);",
        "v.nr_dt = math.clamp(q.delta_time, 0.0, 0.1);",
    ]
    for i, r in enumerate(_radii(vm)):
        k = 57.29578 * 16.0 / r       # 1 ブロック進むと何度回るか
        lines.append(f"v.nr_roll{i} = math.mod(v.nr_roll{i} + v.nr_gs * v.nr_dt * {k:.3f} + 360.0, 360.0);")
    lines += [
        # 向きの変化（度/秒）→ 切れ角。後退なら逆に切る。止まっているときは小さく
        "v.nr_dyaw = math.mod(q.body_y_rotation - v.nr_pyaw + 540.0, 360.0) - 180.0;",
        "v.nr_pyaw = q.body_y_rotation;",
        "v.nr_steer = math.lerp(v.nr_steer, math.clamp(v.nr_dyaw / math.max(v.nr_dt, 0.005) * 0.12 * "
        "(v.nr_gs < -0.3 ? -1.0 : 1.0) * (q.ground_speed > 0.4 ? 1.0 : 0.3), -30.0, 30.0), "
        "math.clamp(v.nr_dt * 5.0, 0.0, 1.0));",
        # 加速度（m/s²、なめらかに）と、ブレーキの尾灯
        "v.nr_acc = math.lerp(v.nr_acc, (v.nr_gs - v.nr_pgs) / math.max(v.nr_dt, 0.005), "
        "math.clamp(v.nr_dt * 3.0, 0.0, 1.0));",
        "v.nr_pgs = v.nr_gs;",
        "v.nr_brake = (v.nr_acc < -5.0 && q.ground_speed > 1.0) ? 1.0 : 0.0;",
        "v.nr_spd01 = math.clamp(q.ground_speed / 12.0, 0.0, 1.0);",
        # 上下動（単位 = 1/16 ブロック）: エンジンの震え + 速さに比例した路面の揺れ
        "v.nr_bob = (q.has_rider ? 0.07 * math.sin(q.life_time * 2200.0) : 0.0) + v.nr_spd01 * "
        "(0.32 * math.sin(q.life_time * 410.0 + 30.0) + 0.16 * math.sin(q.life_time * 977.0));",
        # 前後の傾き（ブレーキで鼻先が沈む = +X、加速で上がる）
        "v.nr_pitch = math.clamp(-v.nr_acc * 0.3, -2.5, 2.5) + v.nr_spd01 * 0.35 * math.sin(q.life_time * 530.0);",
    ]
    if bike:
        lines.append("v.nr_lean = math.clamp(-v.nr_steer * 0.35 * v.nr_spd01, -9.0, 9.0);")   # 曲がる内側へ
    else:
        lines.append("v.nr_lean = math.clamp(v.nr_steer * 0.06 * v.nr_spd01, -2.0, 2.0);")    # 外側へロール
    return lines


def initialize_lines(vm: VM.VehicleModel) -> List[str]:
    vs = [f"v.nr_roll{i} = 0.0;" for i in range(len(_radii(vm)))]
    return [" ".join(vs) + " v.nr_steer = 0.0; v.nr_acc = 0.0; v.nr_pgs = 0.0; v.nr_brake = 0.0; "
            "v.nr_pyaw = q.body_y_rotation;"]


def drive_animation(v: dict, vm: VM.VehicleModel) -> dict:
    """animation.nr.veh.<key>.drive（ループ。値は全部 client の変数）。"""
    radii = _radii(vm)
    wheels = vm.meta.get("wheels") or {}
    names = set(vm.bone_names())
    bones = {}
    front = {"wheel_fl", "wheel_fr"}
    for name, w in sorted(wheels.items()):
        if name not in names:
            continue
        i = radii.index(round(float(w["radius"]), 2))
        rot = [f"v.nr_roll{i}", "v.nr_steer" if name in front else 0, 0]
        bones[name] = {"rotation": rot}
    steer = vm.meta.get("steer") or {}
    if v["kind"] == "dirt_bike":
        if "fork" in names:
            bones["fork"] = {"rotation": [0, "v.nr_steer * 0.8", 0]}
        bones["root"] = {"rotation": [0, 0, "v.nr_lean"]}
        bones["body"] = {"position": [0, "v.nr_bob * 0.7", 0], "rotation": ["v.nr_pitch * 0.6", 0, 0]}
    else:
        if steer.get("bone") == "steering_wheel" and "steering_wheel" in names:
            bones["steering_wheel"] = {"rotation": [0, 0, "-v.nr_steer * 2.6"]}
        bones["body"] = {"position": [0, "v.nr_bob", 0], "rotation": ["v.nr_pitch", 0, "v.nr_lean"]}
    return {f"animation.nr.veh.{v['key']}.drive": {"loop": True, "bones": bones}}


def render_controllers(v: dict, vm: VM.VehicleModel) -> dict:
    lights = "q.property('nr:lights') == 1"
    body, glass = VM.part_visibility_rules(vm, lights=lights, alarm="0.0", glass="0.0")
    for rule in body:
        for bn in list(rule):
            if VM.light_kind(bn) == "tail":
                rule[bn] = f"({lights}) || v.nr_brake > 0.5"
    skins = ["Texture.default"] + [f"Texture.b{i}" for i in range(1, BLOOD_LEVELS + 1)]
    base = {"arrays": {"textures": {"Array.skins": skins}}, "geometry": "Geometry.default",
            "textures": ["Array.skins[q.property('nr:blood')]"]}
    key = v["key"]
    out = {f"controller.render.nr.veh.{key}": dict(copy.deepcopy(base), materials=[{"*": "Material.default"}],
                                                   part_visibility=body)}
    if vm.glass_bones:
        out[f"controller.render.nr.veh.{key}.glass"] = dict(copy.deepcopy(base), materials=[{"*": "Material.glass"}],
                                                            part_visibility=glass)
    return out


def client_entity(v: dict, vm: VM.VehicleModel) -> dict:
    key = v["key"]
    mats = {"default": MAT_BODY}
    rcs = [f"controller.render.nr.veh.{key}"]
    if vm.glass_bones:
        mats["glass"] = MAT_GLASS
        rcs.append(f"controller.render.nr.veh.{key}.glass")
    base_c, over_c = v["egg"]
    desc = {
        "identifier": v["id"], "materials": mats, "textures": _texture_names(v),
        "geometry": {"default": v["geometry"]},
        "animations": {"drive": f"animation.nr.veh.{key}.drive"},
        "scripts": {"initialize": initialize_lines(vm), "pre_animation": pre_animation(v, vm),
                    "animate": ["drive"]},
        "render_controllers": rcs,
        "spawn_egg": {"base_color": base_c, "overlay_color": over_c},
    }
    return {"format_version": CLIENT_FORMAT, "minecraft:client_entity": {"description": desc}}


# ===========================================================================
#  6. 名前・データ JS
# ===========================================================================
LANG_EXTRA = {
    "ja_JP": {INTERACT_TEXT: "乗る", "nr.veh.hint.driver": "運転中  ジャンプ: クラクション  しゃがむ: 降りる",
              "nr.veh.hint.passenger": "同乗中  しゃがむ: 降りる", "nr.veh.wrecked": "乗り物が壊れた！",
              "nr.prop.empty": "もう何も無い"},
    "en_US": {INTERACT_TEXT: "Get in", "nr.veh.hint.driver": "Driving  Jump: horn  Sneak: get out",
              "nr.veh.hint.passenger": "Riding  Sneak: get out", "nr.veh.wrecked": "Your ride is wrecked!",
              "nr.prop.empty": "Nothing left here"},
}


def lang_doc() -> dict:
    ja, en = dict(LANG_EXTRA["ja_JP"]), dict(LANG_EXTRA["en_US"])
    for v in S.VEHICLES:
        ja[f"entity.{v['id']}.name"] = v["ja"]
        en[f"entity.{v['id']}.name"] = v["en"]
        ja[f"item.spawn_egg.entity.{v['id']}.name"] = f"{v['ja']}のスポーンエッグ"
        en[f"item.spawn_egg.entity.{v['id']}.name"] = f"Spawn {v['en']}"
    return {"ja_JP": ja, "en_US": en}


def data_row(v: dict, shape: dict) -> dict:
    row = {k: copy.deepcopy(v[k]) for k in ("key", "id", "ja", "en", "kind", "seats", "seat_count", "speed",
                                             "max_mps", "health", "weight", "roadkill", "shield", "collision",
                                             "wreck", "lights_on_night")}
    row["seats"] = list(row["seats"])
    row["collision"] = list(row["collision"])
    row["shape"] = shape
    row["craft"] = ({"inputs": [list(x) for x in v["craft"]["inputs"]], "unlock": v["craft"].get("unlock"),
                     "ticks": v["craft"].get("ticks", 200), "output": v["id"] + "_spawn_egg"}
                    if v.get("craft") else None)
    return row


# ===========================================================================
#  7. 確認用の絵
# ===========================================================================
def preview_cell(vm: VM.VehicleModel, img: Image.Image, size: int = 330, pose=None, view=(35.0, 20.0)) -> Image.Image:
    return VM.preview(vm, img, view=view, size=size, props={"nr:lights": 1}, pose=pose)


# ===========================================================================
#  8. 本体
# ===========================================================================
def _clean(folder: str, keep: set, suffix: str) -> None:
    if not os.path.isdir(folder):
        return
    for f in os.listdir(folder):
        if f.endswith(suffix) and f[:-len(suffix)] not in keep:
            os.remove(os.path.join(folder, f))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", default="", help="この鍵だけ作り直す（カンマ区切り）。JSON・データは全部書く")
    ap.add_argument("--no-preview", action="store_true", help="確認用の画像を描かない")
    ap.add_argument("--sheet-only", action="store_true", help="パックに書かず画像だけ")
    args = ap.parse_args(argv)
    t0 = time.time()
    keys = [v["key"] for v in S.VEHICLES]
    only = [k.strip() for k in args.only.split(",") if k.strip()]
    for k in only:
        if k not in keys:
            raise SystemExit(f"--only {k}: そんな乗り物は無い（{keys}）")
    write = not args.sheet_only
    cache = (load_json(CACHE_PATH) if os.path.exists(CACHE_PATH) else {}) if only else {}
    rcs, anims, rows, records = {}, {}, [], {}
    cells, cells_blood = [], []
    for v in S.VEHICLES:
        key = v["key"]
        if only and key not in only and key in (cache.get("vehicles") or {}):
            rec = cache["vehicles"][key]
            rcs.update(rec["render_controllers"])
            anims.update(rec["animations"])
            rows.append(rec["row"])
            records[key] = rec
            continue
        tk = time.time()
        vm = build_vehicle_model(v)
        imgs = paint_all(vm)
        if write:
            write_geometry(os.path.join(GEO_DIR, f"{key}.geo.json"), vm)
            os.makedirs(TEX_DIR, exist_ok=True)
            for i, im in enumerate(imgs):
                NP.save_png(im, os.path.join(TEX_DIR, f"{key}{'' if i == 0 else f'_b{i}'}.png"), quantize=True)
            write_json(os.path.join(ENT_BP_DIR, f"{key}.json"), bp_entity(v, vm))
            write_json(os.path.join(ENT_RP_DIR, f"{key}.entity.json"), client_entity(v, vm))
        rc = render_controllers(v, vm)
        an = drive_animation(v, vm)
        row = data_row(v, shape_of(v, vm))
        rcs.update(rc)
        anims.update(an)
        rows.append(row)
        records[key] = {"render_controllers": rc, "animations": an, "row": row,
                        "texture_size": [vm.tex_w, vm.tex_h], "cubes": vm.cube_count(),
                        "bones": vm.bone_names()}
        print(f"  {key:16s} {v['kind']:10s} {vm.cube_count():4d} cubes  {vm.tex_w}x{vm.tex_h} x{len(imgs)}  "
              f"密度 {vm.scale:.2f}  座席 {v['seat_count']}  {time.time() - tk:.1f}s", flush=True)
        if not args.no_preview:
            cells.append((f"{key}  {vm.cube_count()}c {vm.tex_w}x{vm.tex_h}", preview_cell(vm, imgs[0])))
            cells_blood.append((f"{key}  nr:blood 3", preview_cell(vm, imgs[-1])))
    if write:
        if not only:
            _clean(GEO_DIR, set(keys), ".geo.json")
            _clean(ENT_BP_DIR, set(keys), ".json")
            _clean(ENT_RP_DIR, set(keys), ".entity.json")
            texkeep = {k for k in keys} | {f"{k}_b{i}" for k in keys for i in range(1, BLOOD_LEVELS + 1)}
            _clean(TEX_DIR, texkeep, ".png")
        write_json(RC_PATH, {"format_version": "1.10.0", "render_controllers": dict(sorted(rcs.items()))})
        write_json(ANIM_PATH, {"format_version": "1.10.0", "animations": dict(sorted(anims.items()))})
        rows.sort(key=lambda r: keys.index(r["key"]))
        write_data_js("vehicles", {
            "VEHICLES": rows,
            "VEHICLE_BY_ID": {r["id"]: r for r in rows},
            "VEHICLE_PROPERTIES": list(PROPERTIES),
            "VEHICLE_FAMILY": "nr_drivable",
        }, header=(
            "gen_nr_vehicles: 乗れる乗り物（nr_spec_catalog の VEHICLES + 車体の形）。VEHICLES[i] = {key, id, ja, en, kind,\n"
            "seats（先頭が運転席）, seat_count, speed（minecraft:movement）, max_mps（目安の最高速 m/s）, health, weight,\n"
            "roadkill {min_mps, full_mps, damage, power, sever, head, plow, self_damage}, shield, collision, wreck（小道具の鍵）,\n"
            "lights_on_night, shape {front, back, half_w, height（ブロック、エンティティの位置から。前 = 向いている方）, seats:\n"
            "[{name, pos: [x, y, z]（rideable の座席、+Z が前・-X が右）}], wheel_radius, smoke: [x, y, z]（小道具空間）}, craft}。"))
        frag("lang", PRODUCER, lang_doc())
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        write_json(CACHE_PATH, {"vehicles": records})
    if cells and not args.no_preview:
        import nr_preview as V
        sheet = V.contact_sheet(cells + cells_blood, cols=4,
                                title="NIGHT RUNNER — drivable vehicles (3/4; top: clean + lights, bottom: nr:blood 3)")
        os.makedirs(os.path.dirname(SHEET_PATH), exist_ok=True)
        sheet.save(SHEET_PATH)
        print(f"  確認画像: {SHEET_PATH}")
    print(f"gen_nr_vehicles: {len(keys)} 台（{time.time() - t0:.1f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
