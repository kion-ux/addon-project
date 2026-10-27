# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 小道具エンティティ（車の残骸・バス・コンテナ・ゴミ箱・墜落したヘリ・ボンベ・杭丸太）。

DESIGN.md §1 の `gen_nr_props.py`。`nr_spec.PROPS`（16 種）の全部について書く（このファイルが持ち主。
走るたびに下のフォルダの自分のファイルを消してから書き直す）:

| 書くもの | 場所 |
|---|---|
| ジオメトリ `geometry.nr.prop.<key>`（1.16.0、nr_common.write_geometry） | RP `models/entity/nr/props/<key>.geo.json` |
| テクスチャ（色違いは `<key>_v1`…。≤512²、1024² は `ATLAS_1024` の 4 種だけ） | RP `textures/nr/props/<key>.png` |
| クライアントエンティティ（format 1.10.0） | RP `entity/props/<key>.entity.json` |
| レンダーコントローラ `controller.render.nr.prop.<key>`（本体）と `.<key>.glass`（窓） | RP `render_controllers/nr_props.render_controllers.json` |
| アニメ（開く・揺れる・煙）とコントローラ | RP `animations/nr_props.animation.json`、`animation_controllers/nr_props.animation_controllers.json` |
| BP エンティティ `nr:prop_<key>`（format 1.21.120） | BP `entities/props/<key>.json` |
| バリアのマスと使う場所の表 | BP `scripts/data/prop_shapes.js`（`nr_common.write_data_js`） |
| 名前（`entity.<id>.name`・`item.spawn_egg.entity.<id>.name`） | `.frag/lang/gen_nr_props.json` |
| 他の生成器向けの一覧（prop_assets の中身） | `tools/nightrunner/.cache/prop_assets.json` |
| 確認用のコンタクトシート（全部 3/4。乗り物の部品のバギー・バイクも） | `build_preview/nightrunner/props.png` |

車体は `nr_vehicle_models.py`（gen_nr_vehicles と共有）で組み、ここでは残骸としての傷み・血・中身を決める。
コンテナ・ゴミ箱・ヘリ・ボンベ・杭丸太はここで同じ部品（VehicleModel）から組む。

■ BP（content.md §1）: AI なし・重力なし（`physics` の has_gravity / has_collision が false）・押せない・
  `damage_sensor` で全ダメージ無効（体力 1000 のプールは殴った・撃った判定 entityHitEntity のため）・
  `minecraft:persistent`・`nr:despawn` → `instant_despawn`・`is_spawnable`（スポーンエッグ）。
  当たり（歩けない所・屋根）はエンティティではなく**バリアブロック**（`prop_shapes.js` のマス）。
  プロパティ（全部 int・client_sync。全小道具で同じ 5 つ。スクリプトは setProperty かイベントで変える）:
    `nr:variant` 0..n-1（色違い。セダンは 4 色、生まれた時に乱数）/ `nr:open` 0|1（トランク・扉・蓋・シャッターが開く。
    杭丸太は 1 で縄が切れて揺れる）/ `nr:lights` 0|1（前照灯・回転灯・行き先表示・残り火。既定は種類ごと）/
    `nr:alarm` 0|1（車のアラーム: 前照灯とウインカーが点滅）/ `nr:glass` 0|1（窓が割れた見た目）
  イベント: `nr:despawn` / `nr:open` / `nr:close` / `nr:lights_on` / `nr:lights_off` / `nr:alarm_on` /
    `nr:alarm_off` / `nr:smash_glass`
■ RP（rendering.md §3.3・§11）: 本体 `entity_emissive_alpha`（灯りの texel だけ α 16、穴は RGBA 0）。
  割れていない窓は 2 本目の render controller（`entity_alphablend`、窓のボーンだけ、最後に描く。M7）。
  灯り・回転灯の点滅は part_visibility（q.property と q.life_time）。開く・揺れるはアニメ（`v.nr_open` を
  q.property('nr:open') へ滑らかに寄せて重みにする）。煙は client のループアニメの particle_effects。

公開 API（gen_nr_structures・データ JS・スクリプト担当向け）:

    prop_assets(key) -> {key, id, geometry, geo_file, textures, texture_size, cubes, bones, glass_bones,
                         smash_bones, light_bones, materials, render_controllers, properties, animations,
                         size_blocks, barrier, anchor, points}
    barrier_cells(key, rot) -> [(dx, dy, dz), ...]   # rot = 0 / 90 / 180 / 270（エンティティの yaw。270 = -90）
    spawn_offset(key, rot) -> (ex, ez)              # 原点のマス B の角からエンティティを置く位置
    interaction_points(key) -> [{kind, c: [r, u, f], radius}, ...]
    ROTATIONS = (0, 90, 180, 270)

使い方: `python3 tools/nightrunner/gen_nr_props.py [--only key,key] [--no-preview] [--sheet-only]`（普通は build_nr.py から）。
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from nr_common import (BP, RP, SCRATCH, frag, load_json, rp_path, bp_path, stable_hash,  # noqa: E402
                       write_data_js, write_geometry, write_json)
import nr_paint as NP  # noqa: E402
import nr_spec as S  # noqa: E402
import nr_vehicle_models as VM  # noqa: E402

PRODUCER = "gen_nr_props"
GEO_DIR = rp_path("models", "entity", "nr", "props")
TEX_DIR = rp_path("textures", "nr", "props")
TEX_REF = "textures/nr/props/"
ENT_RP_DIR = rp_path("entity", "props")
ENT_BP_DIR = bp_path("entities", "props")
RC_PATH = rp_path("render_controllers", "nr_props.render_controllers.json")
ANIM_PATH = rp_path("animations", "nr_props.animation.json")
CTRL_PATH = rp_path("animation_controllers", "nr_props.animation_controllers.json")
CACHE_PATH = os.path.join(HERE, ".cache", "prop_assets.json")
SHEET_PATH = os.path.join(SCRATCH, "props.png")
ENTITY_FORMAT = "1.21.120"
CLIENT_FORMAT = "1.10.0"

MAX_CUBES = 700                 # DESIGN.md §11
ATLAS_1024 = ("city_bus", "garbage_truck", "box_truck", "army_truck")   # 1024² は 4 枚まで（rendering.md M6）
LIGHTS_ON = ("sedan_wreck", "police_car", "ambulance", "city_bus", "helicopter_crash")
ROTATIONS = (0, 90, 180, 270)
PROPERTIES = ("nr:variant", "nr:open", "nr:lights", "nr:alarm", "nr:glass")
SMOKE_PARTICLE = "nr:smoke_dark"
MAT_BODY = "entity_emissive_alpha"
MAT_GLASS = "entity_alphablend"


def prop_spec(key: str) -> dict:
    for p in S.PROPS:
        if p["key"] == key:
            return p
    raise KeyError(f"小道具 {key} が spec に無い")


# ===========================================================================
#  1. 乗り物の小道具（nr_vehicle_models で組み、残骸の傷みを決める）
# ===========================================================================
def _vehicle(key: str, kind: str, p: dict, *, paint=None, paint2=None, wear=None, options=None) -> VM.VehicleModel:
    atlas = (1024, 1024) if key in ATLAS_1024 else (512, 512)
    vm = VM.build_vehicle(kind, key=key, identifier=p["geometry"], paint=paint, paint2=paint2, wear=wear,
                          seed=stable_hash("nr_prop:" + key) & 0xFFFFFF, atlas=atlas, options=options)
    return vm


def build_sedan_wreck(p):
    paints = list(p.get("variant_paints") or ["paint_red"])
    vm = _vehicle("sedan_wreck", "sedan", p, paint=paints[0], wear=dict(
        rust=0.35, dirt=0.6, dents=0.45, blood=0.55, bullets=3, flat=("rr",),
        glass={"windshield": "cracked", "fl": "shattered", "fr": "shattered", "rl": "intact", "rr": "intact",
               "rear": "intact"},
        hanging=("mirror_l", "bumper_f"), lights_broken=("head_l", "tail_l"), missing=("hubcap_rl",)),
        options={"rear_text": "HELP", "lit_head": ("r",)})
    # 地面の油漏れ（エンジンの下）
    vm.bone("ground", parent=None)
    lk = vm.box((4.0, 0.06, -28.0), (14.0, 0.12, 11.0), "fuel", bone="ground", drop="down")
    vm.dec(lk, "up", "nrv_puddle", kind="fuel")
    pals = [None] + [{"paint": VM.vehicle_styles(c, vm.meta["wear"])["paint"]} for c in paints[1:]]
    return vm, pals


def build_taxi_wreck(p):
    vm = _vehicle("taxi_wreck", "taxi", p, wear=dict(
        rust=0.3, dirt=0.55, dents=0.35, blood=0.6, bullets=1,
        glass={"windshield": "cracked", "fr": "shattered", "rr": "cracked", "rear": "intact"},
        missing=("hubcap_fl",)), options={"plate_kind": "green", "seat_style": "seat_vinyl", "bag": False})
    # 後席に乗ったままの客（窓にもたれている）
    vm.bone("passenger", pivot=(-7.0, 9.4, 11.0), parent="body", rotation=(-6, 0, -16))
    vm.box((-7.0, 14.0, 11.6), (8.0, 9.0, 4.4), "cloth", bone="passenger")
    vm.box((-7.8, 20.6, 11.4), (4.6, 5.0, 4.6), "skin_dead", bone="passenger", rot=(10, 20, -14))
    vm.box((-11.2, 13.6, 9.6), (1.8, 7.0, 1.8), "cloth", bone="passenger", rot=(-20, 0, 10))
    vm.box((-2.8, 13.0, 8.0), (1.8, 6.6, 1.8), "cloth", bone="passenger", rot=(-50, 0, -10))
    for x in (-9.0, -5.0):
        vm.box((x, 10.6, 7.0), (2.6, 2.4, 7.4), "cloth", bone="passenger")
    for c in vm.bmap["passenger"].cubes[:1]:
        vm.dec(c, "*", "nrv_splatter", at=(0.5, 0.3), size=0.4, count=24)
    return vm, [None]


def build_police_car(p):
    vm = _vehicle("police_car", "police", p, wear=dict(
        rust=0.2, dirt=0.45, dents=0.4, blood=0.45, bullets=9, doors={"fr": "ajar"},
        glass={"windshield": "cracked", "fr": "shattered", "rl": "intact", "rr": "cracked", "rear": "intact"}),
        options={"door_style": "paint2", "door_text": "POLICE", "door_text_rgb": (24, 26, 30), "door_badge": True,
                 "plate_kind": "white"})
    return vm, [None]


def build_ambulance(p):
    vm = _vehicle("ambulance", "ambulance", p, wear=dict(
        rust=0.25, dirt=0.5, dents=0.3, blood=0.6, bullets=2, doors={"rear_l": "open"},
        glass={"windshield": "cracked", "rear_r": "intact"}))
    # 右の扉の窓に血の手形・側面を引きずった血
    for c in vm.bmap.get("glass_rear_r", VM.Bone("x")).cubes:
        VM.VehicleModel.dec(vm, c, "south", "handprint", at=(0.5, 0.5), size=0.7)
    for b in vm.model.bones:
        for c in b.cubes:
            if c.style == "paint" and c.size[2] > 60 and c.origin[0] < 0 and c.size[0] <= 1.01:
                vm.dec(c, "east", "nrv_smear", at=(0.3, 0.42), angle=-4, length=0.45, width=0.1)
    return vm, [None]


def build_city_bus(p):
    vm = _vehicle("city_bus", "bus", p, paint2="paint_white", wear=dict(
        rust=0.4, dirt=0.55, dents=0.3, blood=0.5, bullets=4,
        glass={"windshield": "shattered", "wl3": "shattered", "wl6": "shattered", "wr5": "shattered",
               "wl8": "cracked", "wr2": "cracked"}),
        options={"sign": "NOT IN SERVICE", "luggage": (18.0, 40.0, 9.0, 21.0)})
    return vm, [None]


def build_box_truck(p):
    vm = _vehicle("box_truck", "box_truck", p, wear=dict(
        rust=0.3, dirt=0.55, dents=0.35, blood=0.25, bullets=2, glass={"windshield": "shattered", "fl": "cracked"}),
        options={"graffiti": "GO NORTH", "company": "NR MOVERS"})
    return vm, [None]


def build_pickup_truck(p):
    vm = _vehicle("pickup_truck", "pickup", p, wear=dict(
        rust=0.45, dirt=0.75, dents=0.4, blood=0.35, bullets=1, glass={"windshield": "shattered"}))
    for c in vm.bmap.get("door_fl", VM.Bone("x")).cubes[:1]:
        vm.dec(c, "west", "nrv_smear", at=(0.3, 0.3), angle=10, length=0.5, width=0.14)
    return vm, [None]


def build_burnt_car(p):
    vm = _vehicle("burnt_car", "sedan", p, paint="paint_burnt", wear=dict(
        rust=0.8, dirt=0.4, dents=0.6, burnt=1.0, hood="crumpled", lights_broken=("head_l", "head_r", "tail_l", "tail_r"),
        missing=("antenna", "bumper_f")), options={"bag": False})
    # 運転席の黒焦げの人影（骨の形）と周りの灰
    vm.bone("victim", pivot=(-7.4, 7.4, -1.0), parent="body", rotation=(-14, 0, 6))
    vm.box((-7.4, 11.6, -0.6), (6.4, 8.0, 3.6), "char", bone="victim")
    vm.box((-7.6, 17.2, -1.4), (3.8, 4.4, 4.0), "char", bone="victim", rot=(24, 0, 8))
    vm.box((-7.4, 8.4, -3.0), (6.0, 2.4, 6.0), "char", bone="victim")
    for s in (-1, 1):
        vm.rod((-7.4 + s * 3.6, 14.6, -0.4), (-7.4 + s * 2.6, 10.4, -6.4), 1.3, "char", bone="victim")
        vm.rod((-7.4 + s * 1.6, 8.0, -5.0), (-7.4 + s * 1.8, 4.0, -10.0), 1.5, "char", bone="victim")
    vm.box((-7.6, 17.6, -3.4), (2.4, 1.6, 0.4), "bone", bone="victim")
    vm.bone("ground", parent=None)
    ash = vm.box((0, 0.05, 0), (40.0, 0.1, 92.0), "ash", bone="ground", drop="down")
    vm.dec(ash, "up", "nrv_puddle", kind="ash")
    return vm, [None]


def build_overturned_car(p):
    vm = _vehicle("overturned_car", "sedan", p, paint="paint_blue", wear=dict(
        rust=0.4, dirt=0.55, dents=0.6, blood=0.3, bullets=0, overturned=True, crushed=0.55,
        glass={"windshield": "shattered", "fl": "shattered", "fr": "shattered", "rl": "missing", "rear": "cracked"},
        hanging=("mirror_r",), missing=("antenna",)), options={"bag": True})
    vm.bone("ground", parent=None)
    pd = vm.box((6.0, 0.06, 20.0), (18.0, 0.12, 16.0), "fuel", bone="ground", drop="down")
    vm.dec(pd, "up", "nrv_puddle", kind="fuel")
    vm.locator("fuel", (6.0, 0.5, 20.0), bone="ground")
    return vm, [None]


def build_garbage_truck(p):
    vm = _vehicle("garbage_truck", "garbage_truck", p, wear=dict(
        rust=0.45, dirt=0.75, dents=0.35, blood=0.3, bullets=0, glass={"windshield": "shattered"}))
    return vm, [None]


def build_army_truck(p):
    vm = _vehicle("army_truck", "army_truck", p, wear=dict(
        rust=0.25, dirt=0.6, dents=0.3, blood=0.2, bullets=6, glass={"windshield": "cracked"}))
    return vm, [None]


# ===========================================================================
#  2. 乗り物でない小道具（同じ部品で組む）
# ===========================================================================
def _vm(key, p, atlas, palette, max_scale=4.0):
    return VM.VehicleModel(key, p["geometry"], seed=stable_hash("nr_prop:" + key) & 0xFFFFFF, atlas=atlas,
                           max_scale=max_scale, palette=palette)


def build_shipping_container(p):
    w = dict(rust=0.65, dirt=0.5, dents=0.5, scratches=0.5)
    pal = VM.vehicle_styles("paint_orange", w)
    vm = _vm("shipping_container", p, (512, 512), pal)
    rng = random.Random(stable_hash("container"))
    hw, H, hl = 21.5, 45.4, 53.5
    P = "paint"
    panels = []
    vm.box2((-(hw - 1.0), 0.8, -(hl - 1.0)), (hw - 1.0, 2.4, hl - 1.0), "wood")
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        vm.box2((s * (hw - 2.0), 0.0, -hl), (s * hw, 2.6, hl), P)
        vm.box2((s * (hw - 1.6), H - 2.2, -hl), (s * hw, H, hl), P)
        wall = vm.box2((s * (hw - 1.0), 2.6, -(hl - 1.2)), (s * (hw - 0.45), H - 2.2, hl - 1.2), P)
        panels.append((wall, side))
        for zc in np.linspace(-(hl - 6.0), hl - 6.0, 12):
            rb = vm.box2((s * (hw - 0.5), 2.8, float(zc) - 1.7), (s * (hw - 0.02), H - 2.4, float(zc) + 1.7), P)
            panels.append((rb, side))
        for zz in (-hl, hl - 2.6):
            vm.box2((s * (hw - 2.6), 0.0, zz), (s * hw, H, zz + 2.6), P)
    fw = vm.box2((-(hw - 1.0), 2.6, -hl), (hw - 1.0, H - 2.2, -(hl - 0.9)), P)
    panels.append((fw, "north"))
    for xc in np.linspace(-(hw - 6.0), hw - 6.0, 5):
        vm.box2((float(xc) - 1.8, 2.8, -hl - 0.4), (float(xc) + 1.8, H - 2.4, -hl + 0.2), P)
    rf = vm.box2((-(hw - 1.0), H - 1.4, -(hl - 1.0)), (hw - 1.0, H - 0.5, hl - 1.0), P)
    vm.dec(rf, "up", "nrb_corrugate", period=4.0, axis="v", depth=1.0)
    vm.dec(rf, "up", "nrv_dent", at=(0.5, 0.42), size=0.35, depth=1.0)
    panels.append((rf, "up"))
    vm.box2((-hw, H - 2.2, -hl), (hw, H, -(hl - 1.6)), P)
    vm.box2((-hw, 0.0, -hl), (hw, 2.6, -(hl - 1.6)), P)
    vm.box2((-hw, H - 3.0, hl - 1.6), (hw, H, hl), P)
    vm.box2((-hw, 0.0, hl - 1.6), (hw, 2.6, hl), P)
    for sx in (-1, 1):
        for sy, yy in ((0, 2.0), (1, H - 2.0)):
            for sz in (-1, 1):
                c = vm.box((sx * (hw - 2.0), yy, sz * (hl - 2.0)), (4.2, 4.2, 4.2), "steel_dark")
                vm.dec(c, "*", "nrv_grille", kind="mesh", box=(0.3, 0.3, 0.7, 0.7), period=1.4, deep=(10, 10, 10))
    # 横の社名（架空）: 波板のリブと壁をまたぐので、座標で描くステンシルの線（白い塗料）
    text = "NRX LINES"
    th = 9.0
    tw = VM.NBP.text_width(text, th)
    for s in (-1, 1):
        side = "east" if s < 0 else "west"
        cubes = [c for c, sd in panels if sd == side]
        right = (0, 0, 1) if s > 0 else (0, 0, -1)
        org = (s * (hw + 0.05), 33.0, -s * tw / 2)
        strokes = VM.NBP.text_strokes(text, org, right, (0, -1, 0), th, slant=0.0, jitter=0.0, seed=3)
        vm.wd(cubes, side, "nrb_spray", strokes=strokes, colour=(232, 232, 224), width=1.6, drip=0.0, overspray=0.0,
              cover=1.0)
    # 後ろの扉（観音開き。open で開く）と閂
    for name, s in (("door_l", 1), ("door_r", -1)):
        bone = f"{name}"
        vm.bone(bone, pivot=(s * (hw - 1.4), H / 2, hl - 0.6), parent="body")
        dp = vm.box2((s * (hw - 1.4), 2.8, hl - 1.1), (0.0, H - 3.2, hl - 0.4), P, bone=bone)
        vm.dec(dp, "south", "nrb_corrugate", period=3.0, axis="u", depth=0.8)
        vm.dec(dp, "south", "nrv_dent", at=(0.4, 0.6), size=0.3, depth=0.8)
        panels.append((dp, "south"))
        for xr in (0.32, 0.72):
            vm.box((s * hw * xr, (H + 2.0) / 2, hl - 0.05), (0.8, H - 6.0, 0.8), "steel", bone=bone)
            vm.box((s * hw * xr + s * 1.2, H * 0.45, hl + 0.4), (2.6, 0.7, 0.7), "steel_dark", bone=bone)
        if s > 0:
            vm.dec(dp, "south", "nrv_text", text="NRXU 418352 1|22G1", colour=(236, 236, 228),
                   box=(0.1, 0.06, 0.9, 0.2))
            vm.dec(dp, "south", "nrb_label", box=(0.55, 0.78, 0.9, 0.9), fill=(200, 200, 190), ink=(30, 30, 30),
                   text="CSC")
        vm.open_pose[bone] = {"rotation": [0, s * 118.0, 0]}
    # 中の荷（パレットと箱）
    for k in range(6):
        zz = hl - 8.0 - (k // 2) * 11.0
        xx = -9.0 if k % 2 == 0 else 9.0
        vm.box((xx, 3.4, zz), (16.0, 1.6, 10.0), "wood")
        vm.box((xx, 9.6, zz), (14.0, 11.0, 9.0), "cardboard" if k % 3 else "plastic_blue", rot=(0, rng.uniform(-6, 6), 0))
    VM.scatter_wear(vm, panels, VM.norm_wear(w), rng, dent_scale=0.5)
    vm.meta.update(size_blocks=[round(2 * hw / 16, 2), round(H / 16, 2), round(2 * hl / 16, 2)], roof_y=H)
    vm.locator("roof", (0, H, 0))
    return vm, [None]


def build_dumpster(p):
    w = dict(rust=0.55, dirt=0.7, dents=0.6, scratches=0.5, blood=0.5)
    pal = VM.vehicle_styles("paint_green", w)
    vm = _vm("dumpster", p, (512, 512), pal)
    rng = random.Random(stable_hash("dumpster"))
    P = "paint"
    panels = []
    body = vm.box2((-15.0, 3.0, -6.6), (15.0, 19.0, 9.0), P)
    panels.append((body, ["east", "west", "south"]))
    sl = vm.box((0, 11.0, -7.4), (30.0, 16.6, 1.2), P, rot=(-20, 0, 0), pivot=(0, 3.0, -6.6))
    panels.append((sl, "north"))
    vm.box2((-15.0, 3.0, -9.2), (15.0, 4.6, -6.6), P)
    rim = vm.box2((-15.6, 18.6, -9.6), (15.6, 20.2, 9.6), P)
    for s in (-1, 1):
        pk = vm.box2((s * 15.0, 12.4, -3.4), (s * 16.6, 15.6, 3.4), "steel_dark")
        vm.dec(pk, "east" if s < 0 else "west", "nrv_grille", kind="mesh", box=(0.1, 0.15, 0.9, 0.85), period=3.0)
        for zz in (-6.0, 6.0):
            vm.box((s * 12.0, 2.2, zz), (2.4, 1.2, 2.6), "steel_dark")
            vm.prism((s * 12.0, 1.4, zz), 2.8, 1.6, "rubber", axis="x", sides=8)
    # 蓋: 左は閉じて（open で開く）、右は開いて後ろへ倒れている
    vm.bone("lid", pivot=(-7.6, 20.4, 9.4), parent="body")
    ld = vm.box2((-15.2, 20.2, -9.8), (-0.2, 21.4, 9.4), "trim", bone="lid")
    vm.dec(ld, "up", "nrv_grille", kind="h", count=3, box=(0.1, 0.2, 0.9, 0.8), deep=(30, 30, 32))
    vm.open_pose["lid"] = {"rotation": [-100.0, 0, 0]}
    vm.bone("lid_r", pivot=(7.6, 20.6, 9.6), parent="body", rotation=(-112, 0, 0))
    lo = vm.box2((0.2, 20.2, -9.8), (15.2, 21.4, 9.6), "trim", bone="lid_r")
    vm.dec(lo, ["up", "down"], "nrv_grille", kind="h", count=3, box=(0.1, 0.2, 0.9, 0.8), deep=(30, 30, 32))
    vm.dec(lo, "*", "grime", amount=0.6)
    for s in (-1, 1):
        for zz in (-2.0, 5.0):
            vm.box((s * 15.3, 11.0, zz), (0.8, 15.6, 1.4), P)
        vm.box2((s * 15.0, 17.6, -8.4), (s * 16.2, 18.6, 8.4), "steel_dark")
    # あふれたゴミ袋と、蓋の隙間から垂れた腕
    for k in range(4):
        vm.box((rng.uniform(1.0, 13.0), 20.0 + rng.uniform(0.5, 2.5), rng.uniform(-6.0, 6.0)),
               (rng.uniform(6.0, 8.0), rng.uniform(5.0, 6.5), rng.uniform(5.0, 7.0)), "trash",
               rot=(rng.uniform(-20, 20), rng.uniform(0, 90), rng.uniform(-20, 20)))
    vm.rod((-6.0, 20.6, -9.0), (-5.0, 15.0, -11.4), 1.8, "skin_dead")
    hd = vm.box((-4.9, 14.0, -11.6), (2.0, 2.4, 1.4), "skin_dead", rot=(20, 0, 0))
    vm.dec(sl, "north", "drips", amount=0.8, start=0.06)
    vm.dec(sl, "north", "nrv_text", text="NR WASTE 03", colour=(230, 230, 220), box=(0.08, 0.12, 0.5, 0.26))
    tag = VM.NBP.text_strokes("NR", (8.0, 15.5, -8.6), (-1, 0, 0), (0, -1, 0), 6.0, seed=11)
    vm.wd(sl, "north", "nrb_spray", strokes=tag, colour=(232, 232, 226), width=0.8, drip=0.6)
    VM.scatter_wear(vm, panels, VM.norm_wear(w), rng)
    vm.meta.update(size_blocks=[2.0, 1.4, 1.2], roof_y=20.2)
    return vm, [None]


def build_helicopter_crash(p):
    w = dict(rust=0.25, dirt=0.55, dents=0.7, scratches=0.6, blood=0.5, bullets=3)
    pal = VM.vehicle_styles("paint_white", w, paint2="paint_blue")
    vm = _vm("helicopter_crash", p, (512, 512), pal)
    rng = random.Random(stable_hash("heli"))
    P = "paint"
    panels = []
    # 胴体（ボーン airframe。右の腹の縁を支点に 25 度傾き、腹が潰れている）
    A = "airframe"
    vm.bone(A, pivot=(15.0, 0.6, -30.0), parent="body", rotation=(0, 0, 25))
    cab = vm.box2((-15.0, 4.0, -58.0), (15.0, 28.0, -14.0), P, bone=A)
    panels.append((cab, ["east", "west", "up"]))
    for s in (-1, 1):
        vm.box((s * 14.2, 27.4, -36.0), (3.2, 3.2, 44.0), P, bone=A, rot=(0, 0, 45))
        vm.box((s * 14.2, 4.6, -36.0), (3.0, 3.0, 44.0), "under", bone=A, rot=(0, 0, 45))
    vm.box2((-13.0, 2.2, -56.0), (13.0, 4.2, -16.0), "under", bone=A)
    nose = vm.box2((-13.0, 6.0, -68.0), (13.0, 21.0, -58.0), P, bone=A)
    panels.append((nose, ["north", "east", "west"]))
    vm.box2((-9.0, 8.0, -73.0), (9.0, 17.0, -68.0), P, bone=A)
    vm.prism((0, 9.0, -70.0), 4.0, 3.0, "trim", axis="y", sides=8, bone=A)
    cam = vm.box((0, 4.6, -66.0), (4.0, 4.0, 4.0), "steel_dark", bone=A, rot=(0, 45, 0))
    vm.lamp((0, 4.6, -68.2), (2.2, 2.2, 0.4), "w", face="north", kind="round", bone=A, bezel=None)
    # 操縦席の風防（大きな曲面を割れた 3 枚で）と枠
    for k, (at, size, rot) in enumerate((((0, 24.6, -63.0), (24.0, 0.3, 12.0), (32, 0, 0)),
                                         ((-12.4, 17.0, -63.0), (0.3, 9.0, 9.0), (0, 0, -10)),
                                         ((12.4, 17.0, -63.0), (0.3, 9.0, 9.0), (0, 0, 10)))):
        vm.window(at, size, "shattered", rot=rot, frame_bone=A, seed=stable_hash(("heli", k)))
    vm.rod((0, 28.0, -58.0), (0, 20.0, -68.5), 1.2, P, bone=A)
    # 横の窓（左の後ろだけ割れていない）と、外れた側扉の開口
    for s in (-1, 1):
        for k, zc in enumerate((-48.0, -24.0)):
            st = "intact" if (s > 0 and k == 1) else "shattered"
            vm.window((s * 15.15, 18.0, zc), (0.3, 8.0, 11.0), st, frame_bone=A, glass_bone="glass",
                      smash_bone="glass_smash", seed=stable_hash(("hw", s, k)))
    op = vm.box((-15.2, 14.0, -36.0), (0.3, 18.0, 16.0), "trim", bone=A)
    vm.wd(op, "*", "nrv_frame", frame="local", lo=list(op.origin), hi=[op.origin[i] + op.size[i] for i in range(3)],
          border=0.9)
    # 機関部・排気・マスト・ハブ（羽根の根元）
    eng = vm.box2((-9.0, 28.0, -36.0), (9.0, 34.0, -12.0), P, bone=A)
    vm.dec(eng, ["east", "west"], "nrv_grille", kind="h", count=5, box=(0.2, 0.2, 0.6, 0.8), deep=(30, 28, 26))
    vm.dec(eng, "*", "burn", at=(0.65, 0.5), size=0.9)
    vm.box2((-3.0, 32.0, -14.0), (3.0, 35.0, -8.0), "exhaust", bone=A)
    vm.prism((0, 36.0, -26.0), 3.0, 4.0, "steel_dark", axis="y", sides=8, bone=A)
    vm.box((0, 38.6, -26.0), (6.0, 2.4, 6.0), "steel_dark", bone=A)
    vm.box((0, 38.6, -26.0), (16.0, 1.0, 3.0), "steel_dark", bone=A, rot=(0, 30, 0))
    vm.locator("smoke", (0, 35.0, -22.0), bone=A)
    # 中（床・計器盤・座席・血）
    vm.box2((-13.0, 4.2, -57.0), (13.0, 5.0, -15.0), "carpet", bone=A)
    ip = vm.box2((-12.0, 10.0, -61.0), (12.0, 15.0, -57.0), "dash", bone=A)
    vm.dec(ip, "south", "nrv_gauges", at=(0.3, 0.4), size=0.25)
    vm.dec(ip, "south", "nrv_gauges", at=(0.7, 0.4), size=0.25)
    for x in (-6.5, 6.5):
        vm.seat((x, 9.0, -51.0), 8.0, depth=7.0, back=10.0, style="seat_vinyl", bone=A, base=2.0, blood=x < 0)
    vm.box2((-12.0, 5.0, -40.0), (12.0, 8.0, -34.0), "seat_vinyl", bone=A)
    bl = vm.box((-6.0, 5.1, -55.0), (12.0, 0.2, 8.0), "blood", bone=A)
    vm.dec(bl, "up", "nrv_puddle", kind="blood")
    # 報道の塗り（青い帯・局の名前）
    vm.wd([cab, nose], ["east", "west"], "nrv_band", y=(9.0, 12.5), colour=(30, 70, 150), wear=0.2)
    for side in ("east", "west"):
        vm.dec(cab, side, "nrv_lettering", text="NR NEWS 7", colour=(30, 70, 150), box=(0.08, 0.6, 0.7, 0.8))
    # 尾部（根元は胴体と一緒、途中で折れて地面へ）
    vm.box2((-5.0, 15.0, -14.0), (5.0, 26.0, 8.0), P, bone=A)
    tb = vm.box2((-4.0, 16.0, 8.0), (4.0, 24.0, 28.0), P, bone=A)
    vm.dec(tb, ["east", "west"], "nrv_text", text="JA-7NR", colour=(30, 30, 34), box=(0.15, 0.25, 0.85, 0.75))
    vm.bone("tail", pivot=(6.0, 12.0, 30.0), parent="body", rotation=(-12, 10, 16))
    t2 = vm.box2((-3.5, 9.0, 30.0), (3.5, 16.0, 70.0), P, bone="tail")
    vm.wd(t2, ["east", "west"], "nrv_band", y=(11.0, 13.0), colour=(30, 70, 150))
    vm.box2((-1.0, 12.0, 64.0), (1.0, 29.0, 74.0), P, bone="tail")
    vm.box2((-9.0, 10.0, 60.0), (9.0, 11.4, 66.0), P, bone="tail")
    vm.box((2.4, 24.0, 72.0), (0.8, 14.0, 2.0), "steel_dark", bone="tail", rot=(0, 0, 32))
    vm.box((2.4, 24.0, 72.0), (0.8, 2.0, 12.0), "steel_dark", bone="tail", rot=(20, 0, 0))
    vm.box2((-3.6, 9.0, 29.0), (3.6, 16.4, 31.6), "char", bone="tail")
    # ローターの羽根（1 枚は地面に刺さり、1 枚は下へ折れる）
    vm.box((10.0, 30.0, 6.0), (4.0, 1.0, 58.0), "steel_dark", rot=(22, 12, 4))
    vm.box((-22.0, 22.0, -30.0), (4.0, 1.0, 48.0), "steel_dark", rot=(-12, 70, 28))
    vm.box((28.0, 3.0, -48.0), (4.0, 1.0, 26.0), "steel_dark", rot=(-34, -40, 6))
    # スキッド（胴体と一緒に傾く。右は潰れて曲がる）
    for s, rot in ((-1, (0, 0, 0)), (1, (0, 6, -10))):
        vm.box((s * 13.0, 0.0, -34.0), (2.0, 2.0, 58.0), "alu", bone=A, rot=rot)
        for zz in (-48.0, -22.0):
            vm.rod((s * 13.0, 0.8, zz), (s * 9.0, 4.4, zz), 1.2, "alu", bone=A)
    # 外れた側扉（地面）と放り出された物資箱（open で蓋が開く）
    dr = vm.box((-30.0, 0.6, -26.0), (18.0, 1.0, 16.0), P, rot=(0, 18, 4))
    vm.dec(dr, "up", "nrv_dent", at=(0.5, 0.5), size=0.4, depth=1.0, crease=True)
    vm.dec(dr, "up", "nrv_text", text="NR NEWS", colour=(30, 70, 150), box=(0.2, 0.3, 0.8, 0.6))
    cr = vm.box((-30.0, 4.0, -6.0), (10.0, 8.0, 10.0), "paint3", rot=(0, -24, 0))
    vm.dec(cr, ["north", "south", "east", "west"], "nrv_stencil", text="SUPPLY", colour=(226, 226, 210),
           box=(0.1, 0.35, 0.9, 0.65))
    vm.bone("crate_lid", pivot=(-30.0, 8.0, -1.0), parent="body", rotation=(0, -24, 0))
    vm.box((-30.0, 8.4, -6.0), (10.4, 0.8, 10.4), "paint3", bone="crate_lid")
    vm.open_pose["crate_lid"] = {"rotation": [62.0, -24.0, 0]}
    for k in range(4):
        vm.box((rng.uniform(-40, -20), 0.5, rng.uniform(-24, 10)), (rng.uniform(2, 5), 0.8, rng.uniform(2, 5)),
               rng.choice(["paper", "steel_dark", "alu"]), rot=(0, rng.uniform(0, 90), 0))
    # 残り火（発光の炎の板。nr:lights で消える）
    vm.bone("lights_extra", parent="body")
    for k in range(2):
        f = vm.box((6.0, 33.0, -22.0), (9.0, 7.0, 0.1), "glow_a", bone="lights_extra", rot=(0, 30 + 90 * k, 25),
                   pivot=(6.0, 30.0, -22.0), drop=("up", "down", "east", "west"))
        vm.dec(f, ["north", "south"], "nrb_flame", tongues=3.0)
    vm.light_bones["lights_extra"] = "extra"
    VM.scatter_wear(vm, panels, VM.norm_wear(w), rng)
    vm.meta.update(size_blocks=[3.2, 2.4, 13.0], roof_y=36.0)
    return vm, [None]


def build_propane_tank(p):
    w = dict(rust=0.6, dirt=0.5, dents=0.5, scratches=0.5)
    pal = VM.vehicle_styles("paint_white", w)
    vm = _vm("propane_tank", p, (256, 256), pal, max_scale=6.0)
    vm.prism((0, 1.2, 0), 11.0, 2.4, "steel_rusty", axis="y", sides=8)
    body = vm.prism((0, 11.2, 0), 12.0, 17.6, "paint", axis="y", sides=8)
    vm.prism((0, 21.0, 0), 9.6, 2.4, "paint", axis="y", sides=8)
    # 保護リング（中が空いた輪。前後に取っ手の穴）
    col = vm.prism((0, 23.4, 0), 10.0, 4.4, "steel", axis="y", sides=8)
    vm.wd(col, "*", "nrv_disc", frame="local", c=[0.0, 23.4, 0.0], axis=1, ri=3.9, ro=7.0, shade=False)
    for c in (col[2],):
        vm.dec(c, ["east", "west"], "nrb_cut_poly", poly=[(0.22, 0.18), (0.78, 0.18), (0.78, 0.55), (0.22, 0.55)],
               invert=True)
    vm.prism((0, 22.6, 0), 2.4, 3.0, "alu", axis="y", sides=8)
    vm.box((0, 24.4, 0), (3.6, 0.6, 0.6), "alu")
    vm.box((0, 24.4, 0), (0.6, 0.6, 3.6), "alu")
    vm.box((1.6, 22.4, 0), (2.0, 0.8, 0.8), "alu")
    # 赤い札（前 = 90 度の帯の west 面、横 = 0 度の帯の east / west 面）
    for c, f in ((body[2], "west"), (body[0], "east"), (body[0], "west")):
        vm.dec(c, f, "nrb_label", box=(0.02, 0.3, 0.98, 0.62), fill=(188, 26, 22), ink=(244, 240, 230),
               text="LPG|GAS", border=1, border_colour=(244, 240, 230))
    for c in body:
        vm.dec(c, "*", "rust_streaks", amount=0.6)
    VM.scatter_wear(vm, [(c, ["north", "south", "east", "west"]) for c in body], VM.norm_wear(w),
                    random.Random(5))
    vm.locator("valve", (0, 24.0, 0))
    vm.meta.update(size_blocks=[0.8, 1.6, 0.8], roof_y=24.8)
    return vm, [None]


SPIKE_HOLD = 75.0


def build_spike_log(p):
    w = dict(rust=0.7, dirt=0.5, dents=0.2, scratches=0.4, blood=0.7)
    pal = VM.vehicle_styles("paint_red", w)
    pal["log"] = dict(VM.NBP.STYLES["wood_old"], blood=0.15)
    vm = _vm("spike_log", p, (256, 256), pal, max_scale=5.0)
    # 梁の下の板（原点 = 吊り点）と鎖の金具
    for x in (-16.0, 16.0):
        vm.box((x, -0.6, 0.0), (6.0, 1.2, 6.0), "wood")
        vm.box((x, -1.6, 0.0), (1.4, 1.2, 1.4), "steel_dark")
    vm.box((0, -0.6, 40.0), (5.0, 1.2, 4.0), "wood")
    vm.bone("swing", pivot=(0, 0, 0), parent="body")
    for x in (-16.0, 16.0):
        ch = vm.box((x, -26.0, 0.0), (1.0, 49.0, 1.0), "chain", bone="swing")
        vm.dec(ch, "*", "nrb_holes", step=1.6)
    logs = vm.prism((0, -56.0, 0.0), 12.0, 48.0, "log", axis="x", sides=8, bone="swing")
    for c in logs:
        vm.wd(c, "lr", "nrv_rings", frame="local", c=[0.0, -56.0, 0.0], r=6.0)
    rng = random.Random(stable_hash("spike_log"))
    for k in range(12):
        x = -20.0 + k * (40.0 / 11.0)
        yy = -56.0 + (3.2 if k % 2 else -3.2) + rng.uniform(-0.8, 0.8)
        z0 = -4.6
        z1 = -13.0 - rng.uniform(0.0, 2.0)
        st = "steel_rusty" if k % 3 else "wood"
        vm.rod((x, yy, z0), (x + rng.uniform(-0.8, 0.8), yy + rng.uniform(-0.8, 0.8), z1), 1.3 if st == "wood" else 0.9,
               st, bone="swing")
    bl = logs[0]
    vm.dec(bl, "north", "nrv_splatter", at=(0.5, 0.5), size=0.6, count=50)
    vm.box((-6.0, -55.0, -11.0), (2.4, 1.8, 2.0), "gore", bone="swing")
    vm.box((9.0, -59.0, -10.0), (2.0, 2.2, 2.4), "gore", bone="swing")
    # 止めの縄（引いた姿勢の丸太の上から、後ろの板へ）。nr:open（縄を切った）で消える
    vm.bone("rope", parent="body")
    a = math.radians(SPIKE_HOLD)
    top = (0.0, -50.0 * math.cos(a), 50.0 * math.sin(a))
    vm.rod(top, (0.0, -1.2, 40.0), 1.2, "rope", bone="rope")
    vm.box((0.0, top[1], top[2]), (2.4, 2.4, 2.4), "rope", bone="rope")
    vm.locator("rope", ((top[0]) / 2, (top[1] - 1.2) / 2, (top[2] + 40.0) / 2))
    vm.meta.update(size_blocks=[3.0, 4.5, 1.0], vb_ext=64.0, roof_y=0.0)
    return vm, [None]


BUILDERS = {
    "sedan_wreck": build_sedan_wreck, "taxi_wreck": build_taxi_wreck, "police_car": build_police_car,
    "ambulance": build_ambulance, "city_bus": build_city_bus, "box_truck": build_box_truck,
    "pickup_truck": build_pickup_truck, "burnt_car": build_burnt_car, "overturned_car": build_overturned_car,
    "garbage_truck": build_garbage_truck, "shipping_container": build_shipping_container,
    "dumpster": build_dumpster, "helicopter_crash": build_helicopter_crash, "army_truck": build_army_truck,
    "propane_tank": build_propane_tank, "spike_log": build_spike_log,
}
SMOKE = ("burnt_car", "helicopter_crash")


def _rings_decal(fc, d):
    """丸太の木口の年輪（ローカル座標、中心からの距離）。"""
    r, ang = VM._radial(fc, d)
    R = max(0.5, float(d.get("r", 6.0)))
    q = r / R
    rings = (np.abs(np.sin(q * 30.0 + np.sin(ang * 3.0) * 0.6)) < 0.3)
    fc.paint(np.ones(r.shape, np.float32), (150, 118, 80))
    fc.mul(rings, 0.78)
    fc.mul(q > 0.86, 0.55)
    fc.mul(np.abs(np.sin(ang * 5.0 + q * 3.0)) < 0.05, 0.6)


NP.DECALS["nrv_rings"] = _rings_decal


# ===========================================================================
#  3. 組み立て・塗り（色違い）
# ===========================================================================
def build_prop(key: str) -> Tuple[VM.VehicleModel, List[Image.Image]]:
    """(vm, [テクスチャ...])。テクスチャの 0 番が既定、1 番から色違い。"""
    p = prop_spec(key)
    vm, pals = BUILDERS[key](p)
    budget = min(MAX_CUBES, int(p.get("cube_budget") or MAX_CUBES))
    n = vm.cube_count()
    if n > budget:
        raise ValueError(f"{key}: キューブ {n} 個（上限 {budget}）")
    vm.pack()
    imgs = [vm.paint(palette=pal) for pal in pals]
    for im in imgs:
        probs = VM.check_textures(vm, im)
        if probs:
            raise ValueError("; ".join(probs))
    W, H = vm.tex_w, vm.tex_h
    lim = 1024 if key in ATLAS_1024 else 512
    if max(W, H) > lim:
        raise ValueError(f"{key}: テクスチャ {W}x{H}（上限 {lim}）")
    return vm, imgs


# ===========================================================================
#  4. バリアのマス・置き方・使う場所（prop_shapes.js）
# ===========================================================================
def _T(x: float, z: float, rot: int) -> Tuple[float, float]:
    """小道具空間の (x, z)（ブロック）→ 世界の (dx, dz)（yaw = rot）。前（-Z）= yaw の向き、右 = -X。"""
    t = math.radians(rot)
    c, s = round(math.cos(t), 6), round(math.sin(t), 6)
    return x * c + z * s, x * s - z * c


def _cells0(p: dict) -> List[Tuple[int, int, int]]:
    out = set()
    for x0, z0, x1, z1, h in p["barrier"]:
        for i in range(int(min(x0, x1)), int(max(x0, x1)) + 1):
            for k in range(int(min(z0, z1)), int(max(z0, z1)) + 1):
                for j in range(int(h)):
                    out.add((i, j, k))
    return sorted(out)


def barrier_cells(key: str, rot: int = 0) -> List[Tuple[int, int, int]]:
    """バリアを置くマス（原点のマス B からの (dx, dy, dz)）。rot はエンティティの yaw（0/90/180/270）。"""
    rot = int(rot) % 360
    if rot not in ROTATIONS:
        raise ValueError(f"rot は {ROTATIONS} のどれか")
    out = set()
    for i, j, k in _cells0(prop_spec(key)):
        dx, dz = _T(i, k, rot)
        out.add((int(round(dx)), j, int(round(dz))))
    return sorted(out)


def spawn_offset(key: str, rot: int = 0) -> Tuple[float, float]:
    """原点のマス B（整数の角）から、エンティティを置く位置 (ex, ez)。y は B の床。"""
    ax, az = prop_spec(key)["anchor"]
    cx, cz = _T(0.5 - ax, 0.5 - az, int(rot) % 360)
    return round(0.5 - cx, 4), round(0.5 - cz, 4)


def _footprint(p: dict):
    """バリアの足跡の小道具空間での範囲（ブロック）: (x0, x1, z0, z1, top)。無ければ None。"""
    cells = _cells0(p)
    if not cells:
        return None
    ax, az = p["anchor"]
    xs = [i for i, _, _ in cells]
    zs = [k for _, _, k in cells]
    return (min(xs) - ax, max(xs) + 1 - ax, min(zs) - az, max(zs) + 1 - az, max(j for _, j, _ in cells) + 1)


def _rf(x, y, z):
    """小道具空間（ブロック）→ [r, u, f]（r = 右 = -x、f = 前 = -z）。"""
    return [round(-x, 3) + 0.0, round(y, 3) + 0.0, round(-z, 3) + 0.0]


def interaction_points(key: str, vm: Optional[VM.VehicleModel] = None) -> List[dict]:
    """使う場所（spec の interactions ごと）。c = [r, u, f]（ブロック、エンティティの位置から）。
    場所はバリアの足跡から決める（後ろ・運転席側・屋根）。窓・灯り・煙・燃料・縄はモデルの位置から。"""
    p = prop_spec(key)
    fp = _footprint(p)
    pts = []
    meta = vm.meta if vm is not None else {}
    locs = vm.locators if vm is not None else {}

    def loc(name, default):
        if name in locs:
            x, y, z = locs[name][1]
            return x / 16, y / 16, z / 16
        return default

    if fp:
        x0, x1, z0, z1, top = fp
        cz = (z0 + z1) / 2
    else:
        x0, x1, z0, z1, top, cz = -0.5, 0.5, -0.5, 0.5, 1, 0.0
    for kind in p["interactions"]:
        if kind == "loot_trunk":
            pts.append(dict(kind=kind, c=_rf(0.0, 0.8, z1 + 0.5), radius=1.2))
        elif kind == "loot_glovebox":
            pts.append(dict(kind=kind, c=_rf(x0 - 0.5, 0.9, z0 + (z1 - z0) * 0.35), radius=1.0))
        elif kind == "loot_cargo":
            if key == "dumpster":
                pts.append(dict(kind=kind, c=_rf(0.0, 1.0, z0 - 0.5), radius=1.2))
            elif key == "helicopter_crash":
                pts.append(dict(kind=kind, c=_rf(-30 / 16, 0.5, -6 / 16), radius=1.2))
            elif key == "city_bus":
                pts.append(dict(kind=kind, c=_rf(x0 - 0.5, 0.8, 29 / 16), radius=1.4))
            else:
                pts.append(dict(kind=kind, c=_rf(0.0, 0.9, z1 + 0.5), radius=1.4))
        elif kind == "lightbar":
            pts.append(dict(kind=kind, c=_rf(0.0, float(meta.get("roof_y", top * 16)) / 16 + 0.25, 0.0), radius=0.8))
        elif kind == "climb_roof":
            pts.append(dict(kind=kind, c=_rf(0.0, float(top), cz), radius=max(1.0, (x1 - x0) / 2)))
        elif kind == "fuel_leak":
            x, y, z = loc("fuel", (0.0, 0.2, z0 + (z1 - z0) * 0.3))
            pts.append(dict(kind=kind, c=_rf(x, y, z), radius=1.5))
        elif kind == "smoke":
            x, y, z = loc("smoke", (0.0, top, z0 + 1.0))
            pts.append(dict(kind=kind, c=_rf(x, y, z), radius=0.5))
        elif kind == "car_alarm":
            pts.append(dict(kind=kind, c=_rf(0.0, 0.8, cz), radius=max(1.5, (z1 - z0) / 2)))
        elif kind == "open_doors":
            if key == "city_bus":
                for zz in (-90 / 16, 10 / 16):
                    pts.append(dict(kind=kind, c=_rf(x1 + 0.5, 0.5, zz), radius=1.0))
            else:
                pts.append(dict(kind=kind, c=_rf(0.0, 1.0, z1 + 0.5), radius=1.4))
        elif kind == "breakable_glass":
            for gb in (vm.glass_bones if vm is not None else []):
                for c in vm.bmap[gb].cubes:
                    x, y, z = (c.origin[i] + c.size[i] / 2 for i in range(3))
                    pts.append(dict(kind=kind, c=_rf(x / 16, y / 16, z / 16), radius=0.6))
        elif kind == "vent_jet":
            x, y, z = loc("valve", (0.0, 1.5, 0.0))
            pts.append(dict(kind=kind, c=_rf(x, y, z), radius=0.4))
        elif kind == "swing":
            x, y, z = loc("rope", (0.0, -0.4, 1.2))
            pts.append(dict(kind=kind, c=_rf(x, y, z), radius=0.6, note="rope"))
            pts.append(dict(kind="swing_log", c=_rf(0.0, -56 / 16, 0.0), radius=1.5, width=3.0,
                            pivot=[0.0, 0.0, 0.0], length=3.5, hold_deg=SPIKE_HOLD))
    return pts


def _world_pt(c, rot):
    """[r, u, f] → yaw rot の世界のずれ [dx, dy, dz]（エンティティの位置から）。"""
    r, u, f = c
    t = math.radians(rot)
    fw = (-math.sin(t), math.cos(t))
    rt = (-math.cos(t), -math.sin(t))
    return [round(r * rt[0] + f * fw[0], 3) + 0.0, round(u, 3) + 0.0, round(r * rt[1] + f * fw[1], 3) + 0.0]


def shape_entry(key: str, vm: Optional[VM.VehicleModel]) -> dict:
    p = prop_spec(key)
    pts = interaction_points(key, vm)
    rots = {}
    for r in ROTATIONS:
        rots[str(r)] = {"yaw": r if r != 270 else -90, "spawn": list(spawn_offset(key, r)),
                        "cells": [list(c) for c in barrier_cells(key, r)],
                        "points": [dict(kind=q["kind"], p=_world_pt(q["c"], r)) for q in pts]}
    fp = _footprint(p)
    return {
        "id": p["id"], "size": list(p["size_blocks"]), "anchor": list(p["anchor"]), "rects": p["barrier"],
        "top": int(fp[4]) if fp else 0, "variants": int(p["variants"]),
        "lights": 1 if key in LIGHTS_ON else 0, "open": _open_kind(key, vm),
        "points": pts, "rot": rots,
    }


def _open_kind(key, vm) -> str:
    if key == "spike_log":
        return "swing"
    if vm is None or not vm.open_pose:
        return "none"
    return ",".join(sorted(vm.open_pose))


# ===========================================================================
#  5. JSON（BP エンティティ・クライアントエンティティ・レンダーコントローラ・アニメ）
# ===========================================================================
def _properties(p: dict) -> dict:
    nv = max(2, int(p["variants"]))
    return {
        "nr:variant": {"type": "int", "range": [0, nv - 1], "default": 0, "client_sync": True},
        "nr:open": {"type": "int", "range": [0, 1], "default": 0, "client_sync": True},
        "nr:lights": {"type": "int", "range": [0, 1], "default": 1 if p["key"] in LIGHTS_ON else 0,
                      "client_sync": True},
        "nr:alarm": {"type": "int", "range": [0, 1], "default": 0, "client_sync": True},
        "nr:glass": {"type": "int", "range": [0, 1], "default": 0, "client_sync": True},
    }


def bp_entity(p: dict) -> dict:
    sx, sy, sz = p["size_blocks"]
    events = {
        "nr:despawn": {"add": {"component_groups": ["nr:despawn"]}},
        "nr:open": {"set_property": {"nr:open": 1}},
        "nr:close": {"set_property": {"nr:open": 0}},
        "nr:lights_on": {"set_property": {"nr:lights": 1}},
        "nr:lights_off": {"set_property": {"nr:lights": 0}},
        "nr:alarm_on": {"set_property": {"nr:alarm": 1}},
        "nr:alarm_off": {"set_property": {"nr:alarm": 0}},
        "nr:smash_glass": {"set_property": {"nr:glass": 1}},
    }
    if int(p["variants"]) > 1:
        events["minecraft:entity_spawned"] = {"randomize": [
            {"weight": 1, "set_property": {"nr:variant": i}} for i in range(int(p["variants"]))]}
    fam = ["nr_prop", "inanimate"]
    if p.get("trap"):
        fam.append("nr_trap")
    if any(k in p["key"] for k in ("car", "taxi", "sedan", "bus", "truck", "ambulance")):
        fam.append("nr_vehicle")
    return {
        "format_version": ENTITY_FORMAT,
        "minecraft:entity": {
            "description": {"identifier": p["id"], "is_spawnable": True, "is_summonable": True,
                            "properties": _properties(p)},
            "component_groups": {"nr:despawn": {"minecraft:instant_despawn": {}}},
            "components": {
                "minecraft:type_family": {"family": fam},
                "minecraft:health": {"value": 1000, "max": 1000},
                "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                "minecraft:collision_box": {"width": round(max(0.5, min(sx, sz, 2.0)), 2),
                                            "height": round(max(0.5, min(sy, 3.0)), 2)},
                "minecraft:physics": {"has_gravity": False, "has_collision": False},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                "minecraft:knockback_resistance": {"value": 1.0},
                "minecraft:persistent": {},
                "minecraft:fire_immune": {},
                "minecraft:conditional_bandwidth_optimization": {},
            },
            "events": events,
        },
    }


def _texture_names(p: dict, n: int) -> Dict[str, str]:
    out = {"default": TEX_REF + p["key"]}
    for i in range(1, n):
        out[f"v{i}"] = TEX_REF + f"{p['key']}_v{i}"
    return out


def _egg(p: dict) -> dict:
    paints = {"sedan_wreck": ("paint_red", "paint_white"), "taxi_wreck": ("paint_yellow", "paint_black"),
              "police_car": ("paint_black", "paint_white"), "ambulance": ("paint_white", "paint_red"),
              "city_bus": ("paint_blue", "paint_white"), "box_truck": ("paint_white", "paint_blue"),
              "pickup_truck": ("paint_green", "paint_black"), "burnt_car": ("paint_burnt", "paint_orange"),
              "overturned_car": ("paint_blue", "paint_black"), "garbage_truck": ("paint_green", "paint_white"),
              "shipping_container": ("paint_orange", "steel_painted"), "dumpster": ("paint_green", "paint_black"),
              "helicopter_crash": ("paint_white", "paint_blue"), "army_truck": ("paint_olive", "paint_black"),
              "propane_tank": ("paint_white", "paint_red"), "spike_log": ("paint_burnt", "paint_red")}
    a, b = paints.get(p["key"], ("steel_painted", "paint_black"))
    return {"base_color": VM.colour_of(a), "overlay_color": VM.colour_of(b)}


def client_entity(p: dict, vm: VM.VehicleModel, ntex: int) -> dict:
    key = p["key"]
    mats = {"default": MAT_BODY}
    rcs = [f"controller.render.nr.prop.{key}"]
    if vm.glass_bones:
        mats["glass"] = MAT_GLASS
        rcs.append(f"controller.render.nr.prop.{key}.glass")
    anims = {}
    scripts = {}
    animate = []
    particles = {}
    if key == "spike_log":
        anims = {"held": f"animation.nr.prop.{key}.held", "swing": f"animation.nr.prop.{key}.swing",
                 "ctrl": f"controller.animation.nr.prop.{key}"}
        animate.append("ctrl")
    elif vm.open_pose:
        anims["open"] = f"animation.nr.prop.{key}.open"
        scripts["initialize"] = ["v.nr_open = 0.0;"]
        scripts["pre_animation"] = [
            "v.nr_open = math.lerp(v.nr_open, q.property('nr:open'), math.clamp(q.delta_time * 3.0, 0.0, 1.0));"]
        animate.append({"open": "v.nr_open"})
    if key in SMOKE:
        anims["smoke"] = "animation.nr.prop.smoke"
        particles["smoke"] = SMOKE_PARTICLE
        animate.append("smoke")
    if animate:
        scripts["animate"] = animate
    desc = {"identifier": p["id"], "materials": mats, "textures": _texture_names(p, ntex),
            "geometry": {"default": p["geometry"]}}
    if anims:
        desc["animations"] = anims
    if particles:
        desc["particle_effects"] = particles
    if scripts:
        desc["scripts"] = scripts
    desc["render_controllers"] = rcs
    desc["spawn_egg"] = _egg(p)
    return {"format_version": CLIENT_FORMAT, "minecraft:client_entity": {"description": desc}}


def render_controllers(p: dict, vm: VM.VehicleModel, ntex: int) -> dict:
    key = p["key"]
    body, glass = VM.part_visibility_rules(vm)
    if key == "spike_log" and "rope" in vm.bmap:
        body.append({"rope": "q.property('nr:open') == 0"})
    base = {"geometry": "Geometry.default"}
    if ntex > 1:
        base["arrays"] = {"textures": {"Array.skins": ["Texture.default"] + [f"Texture.v{i}" for i in range(1, ntex)]}}
        tex = ["Array.skins[q.property('nr:variant')]"]
    else:
        tex = ["Texture.default"]
    out = {f"controller.render.nr.prop.{key}": dict(base, materials=[{"*": "Material.default"}], textures=tex,
                                                    part_visibility=body)}
    if vm.glass_bones:
        out[f"controller.render.nr.prop.{key}.glass"] = dict(copy.deepcopy(base), materials=[{"*": "Material.glass"}],
                                                             textures=list(tex), part_visibility=glass)
    return out


def _bind_rot(vm, bone):
    b = vm.bmap[bone]
    return list(b.rotation) if b.rotation else [0.0, 0.0, 0.0]


def animations(p: dict, vm: VM.VehicleModel) -> Tuple[dict, dict]:
    """(アニメ, コントローラ)。開く: 開いた姿勢 - 今の姿勢（ジオメトリの rotation に足すので差だけ）。"""
    key = p["key"]
    anims, ctrls = {}, {}
    if key == "spike_log":
        anims[f"animation.nr.prop.{key}.held"] = {"loop": True, "bones": {"swing": {"rotation": [SPIKE_HOLD, 0, 0]}}}
        anims[f"animation.nr.prop.{key}.swing"] = {
            "loop": "hold_on_last_frame", "animation_length": 8.0,
            "bones": {"swing": {"rotation": [
                f"{SPIKE_HOLD} * math.cos(q.anim_time * 120.0) * math.exp(-q.anim_time * 0.45)", 0, 0]}}}
        ctrls[f"controller.animation.nr.prop.{key}"] = {
            "initial_state": "held",
            "states": {
                "held": {"animations": ["held"], "transitions": [{"swing": "q.property('nr:open') == 1"}],
                         "blend_transition": 1.5},
                "swing": {"animations": ["swing"], "transitions": [{"held": "q.property('nr:open') == 0"}]},
            }}
        return anims, ctrls
    if vm.open_pose:
        bones = {}
        for bn, pose in sorted(vm.open_pose.items()):
            d = {}
            if "rotation" in pose:
                cur = _bind_rot(vm, bn)
                d["rotation"] = [round(float(pose["rotation"][i]) - cur[i], 3) for i in range(3)]
            if "position" in pose:
                d["position"] = [round(float(v), 3) for v in pose["position"]]
            bones[bn] = d
        anims[f"animation.nr.prop.{key}.open"] = {"loop": True, "bones": bones}
    return anims, ctrls


def smoke_animation() -> dict:
    return {"animation.nr.prop.smoke": {
        "loop": True, "animation_length": 2.4,
        "particle_effects": {"0.0": {"effect": "smoke", "locator": "smoke",
                                     "pre_effect_script": "v.size = 1.6; v.life = 3.2;"}}}}


def lang_doc() -> dict:
    ja, en = {}, {}
    for p in S.PROPS:
        ja[f"entity.{p['id']}.name"] = p["ja"]
        en[f"entity.{p['id']}.name"] = p["en"]
        ja[f"item.spawn_egg.entity.{p['id']}.name"] = f"{p['ja']}のスポーンエッグ"
        en[f"item.spawn_egg.entity.{p['id']}.name"] = f"Spawn {p['en']}"
    return {"ja_JP": ja, "en_US": en}


# ===========================================================================
#  6. 一覧（他の生成器向け）
# ===========================================================================
def _assets_record(p: dict, vm: VM.VehicleModel, ntex: int) -> dict:
    key = p["key"]
    return {
        "key": key, "id": p["id"], "geometry": p["geometry"],
        "geo_file": f"models/entity/nr/props/{key}.geo.json",
        "textures": list(_texture_names(p, ntex).values()), "texture_size": [vm.tex_w, vm.tex_h],
        "cubes": vm.cube_count(), "bones": vm.bone_names(), "glass_bones": list(vm.glass_bones),
        "smash_bones": list(vm.smash_bones), "light_bones": dict(vm.light_bones),
        "materials": {"default": MAT_BODY, **({"glass": MAT_GLASS} if vm.glass_bones else {})},
        "render_controllers": [f"controller.render.nr.prop.{key}"] +
                              ([f"controller.render.nr.prop.{key}.glass"] if vm.glass_bones else []),
        "properties": _properties(p), "open": _open_kind(key, vm),
        "animations": sorted(animations(p, vm)[0]) + (["animation.nr.prop.smoke"] if key in SMOKE else []),
        "size_blocks": list(p["size_blocks"]), "barrier": p["barrier"], "anchor": list(p["anchor"]),
        "points": interaction_points(key, vm), "texel_density": round(vm.scale, 3),
    }


def _assets_doc() -> dict:
    if os.path.exists(CACHE_PATH):
        try:
            return load_json(CACHE_PATH)
        except Exception:  # noqa: BLE001
            return {}
    return {}


def prop_assets(key: str) -> dict:
    """小道具 1 種の資産の一覧（gen_nr_props を走らせた後は .cache から。無ければ spec から決まる分だけ）。"""
    doc = _assets_doc().get("props") or {}
    if key in doc:
        return copy.deepcopy(doc[key])
    p = prop_spec(key)
    return {"key": key, "id": p["id"], "geometry": p["geometry"], "geo_file": f"models/entity/nr/props/{key}.geo.json",
            "textures": list(_texture_names(p, max(1, int(p["variants"]))).values()),
            "render_controllers": [f"controller.render.nr.prop.{key}"], "properties": _properties(p),
            "size_blocks": list(p["size_blocks"]), "barrier": p["barrier"], "anchor": list(p["anchor"]),
            "points": interaction_points(key, None)}


# ===========================================================================
#  7. 確認用の絵
# ===========================================================================
def preview_cell(key: str, vm: VM.VehicleModel, img: Image.Image, size: int = 330) -> Image.Image:
    pose = {"swing": [SPIKE_HOLD, 0, 0]} if key == "spike_log" else None
    view = (35.0, 20.0) if key not in ("spike_log", "propane_tank") else (35.0, 12.0)
    return VM.preview(vm, img, view=view, size=size, props={"nr:lights": 1 if key in LIGHTS_ON else 0},
                      pose=pose)


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
    keys = [p["key"] for p in S.PROPS]
    missing = [k for k in keys if k not in BUILDERS]
    if missing:
        raise SystemExit(f"組み立て方の無い小道具: {missing}")
    only = [k.strip() for k in args.only.split(",") if k.strip()]
    for k in only:
        if k not in keys:
            raise SystemExit(f"--only {k}: そんな小道具は無い")
    write = not args.sheet_only
    old = (_assets_doc().get("props") or {}) if only else {}
    rcs, anims, ctrls = {}, {}, {}
    shapes = {}
    records = {}
    cells = []
    for p in S.PROPS:
        key = p["key"]
        if only and key not in only and key in old:
            # 作り直さない: 書いた JSON を読み戻して RC・アニメ・形の表を揃える
            rec = old[key]
            records[key] = rec
            prev_rc = load_json(RC_PATH)["render_controllers"] if os.path.exists(RC_PATH) else {}
            for rid in rec.get("render_controllers", []):
                if rid in prev_rc:
                    rcs[rid] = prev_rc[rid]
            prev_an = load_json(ANIM_PATH)["animations"] if os.path.exists(ANIM_PATH) else {}
            for aid in rec.get("animations", []):
                if aid in prev_an:
                    anims[aid] = prev_an[aid]
            prev_ct = load_json(CTRL_PATH)["animation_controllers"] if os.path.exists(CTRL_PATH) else {}
            cid = f"controller.animation.nr.prop.{key}"
            if cid in prev_ct:
                ctrls[cid] = prev_ct[cid]
            shapes[key] = shape_entry(key, None)
            shapes[key]["points"] = rec.get("points", shapes[key]["points"])
            continue
        tk = time.time()
        vm, imgs = build_prop(key)
        ntex = len(imgs)
        if write:
            write_geometry(os.path.join(GEO_DIR, f"{key}.geo.json"), vm)
            os.makedirs(TEX_DIR, exist_ok=True)
            for i, im in enumerate(imgs):
                NP.save_png(im, os.path.join(TEX_DIR, f"{key}{'' if i == 0 else f'_v{i}'}.png"), quantize=True)
            write_json(os.path.join(ENT_BP_DIR, f"{key}.json"), bp_entity(p))
            write_json(os.path.join(ENT_RP_DIR, f"{key}.entity.json"), client_entity(p, vm, ntex))
        rcs.update(render_controllers(p, vm, ntex))
        a, c = animations(p, vm)
        anims.update(a)
        ctrls.update(c)
        shapes[key] = shape_entry(key, vm)
        records[key] = _assets_record(p, vm, ntex)
        print(f"  {key:20s} {vm.cube_count():4d} cubes  {vm.tex_w}x{vm.tex_h} x{ntex}  "
              f"密度 {vm.scale:.2f}  {time.time() - tk:.1f}s", flush=True)
        if not args.no_preview:
            cells.append((f"{key}  {vm.cube_count()}c {vm.tex_w}²", preview_cell(key, vm, imgs[0])))
    if any(k in SMOKE for k in keys):
        anims.update(smoke_animation())
    if write:
        if not only:
            _clean(GEO_DIR, set(keys), ".geo.json")
            _clean(ENT_BP_DIR, set(keys), ".json")
            _clean(ENT_RP_DIR, set(keys), ".entity.json")
            texkeep = set()
            for k in keys:
                for t in records[k]["textures"]:
                    texkeep.add(os.path.basename(t))
            _clean(TEX_DIR, texkeep, ".png")
        write_json(RC_PATH, {"format_version": "1.10.0", "render_controllers": dict(sorted(rcs.items()))})
        write_json(ANIM_PATH, {"format_version": "1.10.0", "animations": dict(sorted(anims.items()))})
        write_json(CTRL_PATH, {"format_version": "1.10.0", "animation_controllers": dict(sorted(ctrls.items()))})
        write_data_js("prop_shapes", {
            "PROP_SHAPES": shapes,
            "PROP_ROTATIONS": list(ROTATIONS),
            "PROP_PROPERTIES": list(PROPERTIES),
        }, header=(
            "gen_nr_props: 小道具のバリアのマスと使う場所（DESIGN §12）。PROP_SHAPES[key] = {id, size, anchor, rects, top,\n"
            "variants, lights（nr:lights の既定）, open（nr:open で動くボーン / swing / none）, points, rot}。\n"
            "rot[\"0\"|\"90\"|\"180\"|\"270\"] = {yaw（setRotation の y。270 は -90）, spawn: [ex, ez]（原点のマス B の角から\n"
            "エンティティを置く x・z のずれ）, cells: [[dx, dy, dz]...]（B からのバリアのマス）, points: [{kind, p: [dx, dy, dz]}]\n"
            "（エンティティの位置からの世界のずれ）}。points の c は [r, u, f]（ブロック。r = 右、u = 上、f = 前）で、\n"
            "yaw θ のとき 前 = (-sin θ, 0, cos θ)、右 = (-cos θ, 0, -sin θ)。"))
        frag("lang", PRODUCER, lang_doc())
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        write_json(CACHE_PATH, {"props": records})
    if cells and not args.no_preview:
        sheet_extra = []
        for kind in ("buggy", "dirt_bike"):
            v = VM.build_vehicle(kind, key=kind, identifier=f"geometry.nr.vehicle.{kind}", seed=7,
                                 wear=dict(rust=0.25, dirt=0.4, dents=0.2), drivable=True)
            v.pack()
            sheet_extra.append((f"({kind} 部品)  {v.cube_count()}c", VM.preview(v, v.paint(), view=(35.0, 20.0),
                                                                              size=330)))
        import nr_preview as V
        sheet = V.contact_sheet(cells + sheet_extra, cols=6, title="NIGHT RUNNER — props (3/4)")
        os.makedirs(os.path.dirname(SHEET_PATH), exist_ok=True)
        sheet.save(SHEET_PATH)
        print(f"  確認画像: {SHEET_PATH}")
    print(f"gen_nr_props: {len(keys)} 種（{time.time() - t0:.1f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
