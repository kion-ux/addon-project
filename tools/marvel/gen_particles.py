# -*- coding: utf-8 -*-
"""パーティクル — スプライトアトラスと、そこから引く効果の定義。

方針
----
* **一枚絵で勝負しない。** 一つの見せ場は「芯 + 光 + 破片 + 煙 + 衝撃波」のように
  複数のエミッタを重ねて作る。ここでは素材となる個々のエミッタを量産する。
* 色は技ごとの基調色 (contract.TECHNIQUES[*]["colour"]) に揃える。
* 発光させたいものは ``particles_add`` (加算合成)、煙や瓦礫は ``particles_blend``。
"""
from __future__ import annotations

import math
import random

import _path  # noqa: F401

import contract as K  # noqa: E402
from common import write_json  # noqa: E402
from PIL import Image  # noqa: E402

ATLAS = 256
CELL = 32
TEXTURE = "textures/particle/marvel_particles"
TEX_PATH = K.RP + "/textures/particle/marvel_particles.png"

# セル座標 (列, 行) — 32px グリッド
CELLS = {
    "dot": (0, 0), "spark": (1, 0), "streak": (2, 0), "ring": (3, 0),
    "shock": (4, 0), "flash": (5, 0), "hex": (6, 0), "chevron": (7, 0),
    "smoke": (0, 1), "dust": (1, 1), "debris": (2, 1), "shard": (3, 1),
    "crescent": (4, 1), "arc": (5, 1), "beam": (6, 1), "bolt": (7, 1),
    "swirl": (0, 2), "glyph": (1, 2), "ember": (2, 2), "drop": (3, 2),
    "crack": (4, 2), "plume": (5, 2), "lens": (6, 2), "grid": (7, 2),
}


# ===========================================================================
#  アトラス
# ===========================================================================
def build_atlas() -> None:
    img = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 0))
    px = img.load()
    rng = random.Random(77)
    h = CELL / 2

    def cell(name):
        cx, cy = CELLS[name]
        return cx * CELL, cy * CELL

    def put(ox, oy, x, y, a, c=(255, 255, 255)):
        if 0 <= x < CELL and 0 <= y < CELL and a > 0:
            px[ox + int(x), oy + int(y)] = (c[0], c[1], c[2], min(255, int(a)))

    def pw(v, e):
        return max(0.0, v) ** e

    ox, oy = cell("dot")                       # 柔らかい丸い光
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            put(ox, oy, x, y, pw(1 - d, 2.2) * 255)

    ox, oy = cell("spark")                     # 四光星
    for y in range(CELL):
        for x in range(CELL):
            dx, dy = abs(x - h + .5), abs(y - h + .5)
            v = max(0.0, 1 - pw(dx / h, 0.55) - pw(dy / h, 0.55) + 0.35)
            put(ox, oy, x, y, min(255, v * 420))

    ox, oy = cell("streak")                    # 横に伸びる尾
    for y in range(CELL):
        for x in range(CELL):
            fy = 1 - abs(y - h + .5) / (h * 0.26)
            fx = 1 - abs(x - h + .5) / h
            put(ox, oy, x, y, max(0.0, fy) * pw(fx, 0.6) * 255)

    ox, oy = cell("ring")                      # 細いリング
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            put(ox, oy, x, y, pw(1 - abs(d - 0.84) / 0.11, 1.7) * 255)

    ox, oy = cell("shock")                     # 厚い衝撃リング
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            a = pw(1 - abs(d - 0.70) / 0.30, 1.15) * 255
            put(ox, oy, x, y, a if d < 0.99 else 0)

    ox, oy = cell("flash")                     # 十字フレア
    for y in range(CELL):
        for x in range(CELL):
            dx, dy = abs(x - h + .5) / h, abs(y - h + .5) / h
            v = (max(0.0, 1 - dx * 7) + max(0.0, 1 - dy * 7)
                 + max(0.0, 1 - math.hypot(dx, dy) * 2.1))
            put(ox, oy, x, y, min(255, v * 215))

    ox, oy = cell("hex")                       # 六角形の枠
    for y in range(CELL):
        for x in range(CELL):
            u, v = abs(x - h + .5) / h, abs(y - h + .5) / h
            d = max(u * 0.866 + v * 0.5, v)
            put(ox, oy, x, y, max(0.0, 1 - abs(d - 0.74) / 0.10) * 255)

    ox, oy = cell("chevron")                   # 磁力線の矢
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            d = abs(abs(u) * 0.9 + v * 0.6)
            put(ox, oy, x, y, max(0.0, 1 - abs(d - 0.30) / 0.16) * 255)

    ox, oy = cell("smoke")                     # 煙
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            n = 0.94 + 0.26 * math.sin(x * 0.72) * math.cos(y * 0.61)
            put(ox, oy, x, y, pw(1 - d / n, 1.5) * 210)

    ox, oy = cell("dust")                      # 粒立った塵
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            a = pw(1 - d, 1.8) * 205
            if rng.random() < 0.34:
                a *= 0.38
            put(ox, oy, x, y, a)

    ox, oy = cell("debris")                    # 角ばった塊
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            if abs(u) + abs(v * 1.35) < 0.78 and (x * 7 + y * 3) % 11 != 0:
                put(ox, oy, x, y, 255)

    ox, oy = cell("shard")                     # 細長い鉄片
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / (h * 0.36), (y - h + .5) / h
            if abs(u) + abs(v) < 1.0:
                edge = 1 - (abs(u) + abs(v))
                put(ox, oy, x, y, min(255, 140 + edge * 400))

    for name, thick, span in (("arc", 0.10, 0.55), ("crescent", 0.18, 0.86)):
        ox, oy = cell(name)                    # 斬撃の弧
        for y in range(CELL):
            for x in range(CELL):
                u, v = (x - h + .5) / h, (y - h + .5) / h
                d = math.hypot(u, v)
                ang = math.atan2(v, u)
                if abs(ang) > math.pi * span:
                    continue
                a = pw(1 - abs(d - 0.72) / thick, 1.3)
                a *= max(0.0, 1 - (abs(ang) / (math.pi * span)) ** 2)
                put(ox, oy, x, y, a * 255)

    ox, oy = cell("beam")                      # カプセル状の芯
    for y in range(CELL):
        for x in range(CELL):
            fy = 1 - abs(y - h + .5) / (h * 0.40)
            put(ox, oy, x, y, pw(fy, 0.5) * 255 if 1 < x < CELL - 2 else 0)

    ox, oy = cell("bolt")                      # 稲妻
    for i in range(3):
        x, y = CELL // 2 + (i - 1) * 5, 1
        while y < CELL - 2:
            x += rng.choice((-2, -1, 1, 2))
            y += rng.choice((1, 2))
            for k in (-1, 0, 1):
                put(ox, oy, x + k, y, 255 - abs(k) * 110)

    ox, oy = cell("swirl")                     # 渦
    for t in range(520):
        a = t * 0.055
        r = h * (t / 520) ** 0.62
        for k in (0, math.pi):
            x = h + math.cos(a + k) * r
            y = h + math.sin(a + k) * r
            put(ox, oy, x, y, 255 - (t / 520) * 120)

    ox, oy = cell("glyph")                     # 磁界の紋
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            a = max(0.0, 1 - abs(d - 0.86) / 0.08) * 255
            a = max(a, max(0.0, 1 - abs(d - 0.46) / 0.06) * 200)
            put(ox, oy, x, y, a)
    for i in range(6):
        a = i * math.pi / 3
        for t in range(int(h * 0.46), int(h * 0.86)):
            put(ox, oy, h + math.cos(a) * t, h + math.sin(a) * t, 210)

    ox, oy = cell("ember")                     # 火の粉
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot((x - h + .5) / (h * 0.42), (y - h + .5) / (h * 0.74))
            put(ox, oy, x, y, pw(1 - d, 1.4) * 255)

    ox, oy = cell("drop")                      # 雫
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            if math.hypot(u, v * 0.8) < 0.55 * (1 - v * 0.55):
                put(ox, oy, x, y, 255)

    ox, oy = cell("crack")                     # 亀裂
    for i in range(3):
        x, y = CELL // 2, 2
        for _ in range(CELL - 6):
            x += rng.choice((-1, 0, 0, 1))
            y += 1
            for k in range(-1 + i, 2 - i):
                put(ox, oy, x + k, y, 255 - abs(k) * 90)

    ox, oy = cell("plume")                     # 立ち上る土煙
    for y in range(CELL):
        for x in range(CELL):
            v = y / CELL
            wid = h * (0.30 + 0.70 * v)
            d = abs(x - h + .5) / max(1.0, wid)
            a = pw(1 - d, 1.6) * (1 - v * 0.55) * 235
            if rng.random() < 0.28:
                a *= 0.5
            put(ox, oy, x, y, a)

    ox, oy = cell("lens")                      # レンズフレア
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot((x - h + .5) / h, (y - h + .5) / (h * 0.30))
            put(ox, oy, x, y, pw(1 - d, 1.9) * 255)

    ox, oy = cell("grid")                      # 走査グリッド
    for y in range(CELL):
        for x in range(CELL):
            on = (x % 8 < 1) or (y % 8 < 1)
            d = math.hypot(x - h + .5, y - h + .5) / h
            put(ox, oy, x, y, 235 * max(0.0, 1 - d) if on else 0)

    img.save(TEX_PATH)
    print(f"  atlas {ATLAS}x{ATLAS} / {len(CELLS)} cells")


# ===========================================================================
#  エミッタ
# ===========================================================================
def C(hexstr, fade=True, boost=1.0):
    s = hexstr.lstrip("#")
    r, g, b = (int(s[i:i + 2], 16) / 255 * boost for i in (0, 2, 4))
    a = "1 - v.particle_age / v.particle_lifetime" if fade else "1"
    return (f"{min(1.0, r):.3f}", f"{min(1.0, g):.3f}", f"{min(1.0, b):.3f}", a)


def effect(identifier, cell, *, count=12, life=0.6, speed=4.0, size=(0.25, 0.25),
           colour=("1", "1", "1", "1"), shape="sphere", radius=0.6,
           direction="outwards", drag=2.0, gravity=0.0, add=True,
           local=False, spin=None, size_expr=None, active=0.05, steady=None,
           plane="y", offset=("0", "0", "0"), facing="lookat_xyz"):
    """一つのエミッタ。重ねる前提なので、単体では控えめでよい。"""
    comps = {
        "minecraft:emitter_lifetime_once": {"active_time": active},
        "minecraft:particle_lifetime_expression": {"max_lifetime": life},
        "minecraft:particle_initial_speed": speed,
        "minecraft:particle_motion_dynamic": {
            "linear_acceleration": [0, -gravity, 0],
            "linear_drag_coefficient": drag,
        },
        "minecraft:particle_appearance_billboard": {
            "size": list(size_expr or size),
            "facing_camera_mode": facing,
            "uv": {"texture_width": ATLAS, "texture_height": ATLAS,
                   "uv": [CELLS[cell][0] * CELL, CELLS[cell][1] * CELL],
                   "uv_size": [CELL, CELL]},
        },
        "minecraft:particle_appearance_tinting": {"color": list(colour)},
    }
    if steady:
        comps["minecraft:emitter_rate_steady"] = {"spawn_rate": steady[0],
                                                  "max_particles": steady[1]}
    else:
        comps["minecraft:emitter_rate_instant"] = {"num_particles": count}
    if shape == "sphere":
        comps["minecraft:emitter_shape_sphere"] = {
            "offset": list(offset), "radius": radius,
            "direction": direction, "sample_coordinate": True}
    elif shape == "disc":
        comps["minecraft:emitter_shape_disc"] = {
            "plane_normal": plane, "offset": list(offset), "radius": radius,
            "direction": direction, "sample_coordinate": True}
    elif shape == "point":
        comps["minecraft:emitter_shape_point"] = {
            "offset": list(offset), "direction": [0, 1, 0]}
    elif shape == "box":
        comps["minecraft:emitter_shape_box"] = {
            "offset": list(offset), "half_dimensions": [radius, radius, radius],
            "direction": direction}
    if local:
        comps["minecraft:emitter_local_space"] = {"position": True,
                                                  "rotation": True,
                                                  "velocity": False}
    if spin:
        comps["minecraft:particle_initial_spin"] = {"rotation": spin[0],
                                                    "rotation_rate": spin[1]}
    return {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {
                "identifier": identifier,
                "basic_render_parameters": {
                    "material": "particles_add" if add else "particles_blend",
                    "texture": TEXTURE},
            },
            "components": comps,
        },
    }


VIOLET = "#B47CFF"
DEEP = "#6B3AC8"
STEEL = "#B8C0CC"
WHITE = "#FFFFFF"
ORANGE = "#FF7A2A"
CRIMSON = "#FF4A6E"
GREEN = "#8EC84B"
CYAN = "#4BE0FF"
EARTH = "#C8A05A"

#: name -> effect() のキーワード引数。contract.PARTICLES を必ず全部埋める。
SPEC = {
    # --- 磁力の基礎 -----------------------------------------------------
    "mag_field": dict(cell="glyph", count=1, life=0.9, speed=0, drag=6,
                      size=(1.9, 1.9), colour=C(VIOLET), shape="point",
                      spin=(0, 42)),
    "mag_pull": dict(cell="chevron", count=16, life=0.55, speed=-7.5, drag=0.6,
                     size=(0.34, 0.34), colour=C(VIOLET), radius=2.6,
                     direction="inwards"),
    "mag_push": dict(cell="chevron", count=16, life=0.5, speed=9.0, drag=1.2,
                     size=(0.34, 0.34), colour=C(VIOLET), radius=0.4),
    "mag_line": dict(cell="streak", count=8, life=0.4, speed=6.0, drag=1.0,
                     size=(0.6, 0.13), colour=C(VIOLET)),
    "mag_glyph": dict(cell="hex", count=3, life=0.8, speed=0.4, drag=4,
                      size=(0.9, 0.9), colour=C(DEEP), spin=(0, 90)),
    "mag_spark": dict(cell="spark", count=14, life=0.45, speed=6.5, drag=2.4,
                      size=(0.17, 0.17), colour=C(WHITE), gravity=1.5),
    "mag_aura": dict(cell="dot", cellsize=None, count=0, life=1.1, speed=0.5,
                     drag=1.2, size=(0.35, 0.35), colour=C(VIOLET),
                     steady=(14, 26), active=1.2, radius=0.9),
    "mag_aura_max": dict(cell="glyph", count=0, life=1.3, speed=0.35, drag=1.0,
                         size=(0.7, 0.7), colour=C(VIOLET), steady=(20, 40),
                         active=1.4, radius=1.3, spin=(0, 60)),
    "mag_ring": dict(cell="ring", count=1, life=0.5, speed=0, drag=6,
                     size_expr=("0.6 + v.particle_age * 7", "0.6 + v.particle_age * 7"),
                     colour=C(VIOLET), shape="point", facing="rotate_y"),
    "mag_ring_wide": dict(cell="shock", count=1, life=0.75, speed=0, drag=6,
                          size_expr=("1.0 + v.particle_age * 16",
                                     "1.0 + v.particle_age * 16"),
                          colour=C(DEEP), shape="point", facing="rotate_y"),
    "mag_dust": dict(cell="dust", count=12, life=0.9, speed=1.6, drag=2.2,
                     size=(0.26, 0.26), colour=C(STEEL), add=False,
                     gravity=1.0),
    # --- 金属 -------------------------------------------------------------
    "shard_spark": dict(cell="spark", count=10, life=0.4, speed=7.0, drag=2.0,
                        size=(0.15, 0.15), colour=C(WHITE), gravity=3.0),
    "shard_trail": dict(cell="shard", count=4, life=0.32, speed=1.2, drag=3.0,
                        size=(0.30, 0.10), colour=C(STEEL), add=False),
    "shard_burst": dict(cell="shard", count=22, life=0.7, speed=11.0, drag=1.1,
                        size=(0.34, 0.12), colour=C(STEEL), add=False,
                        gravity=2.0, spin=(0, 260)),
    "metal_glint": dict(cell="lens", count=3, life=0.35, speed=0.6, drag=4,
                        size=(0.55, 0.20), colour=C(WHITE)),
    "metal_rip": dict(cell="crescent", count=5, life=0.35, speed=5.0, drag=2.5,
                      size=(0.7, 0.7), colour=C(STEEL), spin=(0, 180)),
    "debris_chunk": dict(cell="debris", count=14, life=1.1, speed=7.0, drag=0.9,
                         size=(0.42, 0.42), colour=C(EARTH), add=False,
                         gravity=9.0, spin=(0, 200)),
    "debris_dust": dict(cell="smoke", count=10, life=1.3, speed=2.2, drag=2.6,
                        size=(0.85, 0.85), colour=C("#8E8272"), add=False),
    "rust_flake": dict(cell="drop", count=8, life=1.0, speed=2.0, drag=2.0,
                       size=(0.16, 0.16), colour=C("#A2673A"), add=False,
                       gravity=4.0),
    # --- 技の決め絵 -------------------------------------------------------
    "repulse_wave": dict(cell="shock", count=1, life=0.55, speed=0, drag=6,
                         size_expr=("0.8 + v.particle_age * 22",
                                    "0.8 + v.particle_age * 22"),
                         colour=C(VIOLET), shape="point", facing="rotate_y"),
    "attract_funnel": dict(cell="swirl", count=6, life=0.65, speed=-5.0,
                           drag=0.8, size=(0.9, 0.9), colour=C(DEEP),
                           radius=3.2, direction="inwards", spin=(0, 200)),
    "disarm_flash": dict(cell="flash", count=4, life=0.3, speed=3.0, drag=3.0,
                         size=(0.8, 0.8), colour=C("#E8E04B")),
    "lance_streak": dict(cell="beam", count=3, life=0.28, speed=1.0, drag=4.0,
                         size=(1.5, 0.28), colour=C(VIOLET)),
    "lance_impact": dict(cell="flash", count=6, life=0.35, speed=6.0, drag=2.2,
                         size=(0.75, 0.75), colour=C(WHITE)),
    "storm_swirl": dict(cell="shard", count=26, life=0.9, speed=9.0, drag=0.7,
                        size=(0.36, 0.13), colour=C(STEEL), add=False,
                        radius=3.0, spin=(0, 320)),
    "barrier_hex": dict(cell="hex", count=0, life=1.0, speed=0.2, drag=3.0,
                        size=(0.85, 0.85), colour=C(CYAN), steady=(22, 44),
                        active=1.5, radius=2.6),
    "barrier_break": dict(cell="hex", count=18, life=0.6, speed=7.0, drag=1.4,
                          size=(0.7, 0.7), colour=C(CYAN), radius=2.4,
                          spin=(0, 200)),
    "bind_weld": dict(cell="spark", count=16, life=0.5, speed=4.5, drag=2.6,
                      size=(0.18, 0.18), colour=C("#FFC24A"), gravity=4.0),
    "crush_implode": dict(cell="chevron", count=20, life=0.45, speed=-11.0,
                          drag=0.5, size=(0.32, 0.32), colour=C("#FF4A6E"),
                          radius=2.8, direction="inwards"),
    "crush_blood": dict(cell="drop", count=10, life=0.7, speed=5.0, drag=1.6,
                        size=(0.20, 0.20), colour=C("#B0142A"), add=False,
                        gravity=8.0),
    "uprising_soil": dict(cell="plume", count=14, life=1.2, speed=6.5, drag=1.6,
                          size=(0.9, 0.9), colour=C("#8E7A5A"), add=False,
                          shape="disc", radius=2.4, plane="y"),
    "uprising_pillar": dict(cell="beam", count=6, life=0.8, speed=9.0, drag=1.0,
                            size=(0.5, 1.8), colour=C(EARTH), add=False),
    "emp_wave": dict(cell="ring", count=1, life=0.7, speed=0, drag=6,
                     size_expr=("0.6 + v.particle_age * 26",
                                "0.6 + v.particle_age * 26"),
                     colour=C(CYAN), shape="point", facing="rotate_y"),
    "emp_arc": dict(cell="bolt", count=14, life=0.4, speed=5.0, drag=2.0,
                    size=(0.55, 0.55), colour=C(CYAN), radius=2.0,
                    spin=(0, 300)),
    "polarity_field": dict(cell="grid", count=0, life=1.4, speed=0.3, drag=2.0,
                           size=(1.1, 1.1), colour=C(DEEP), steady=(16, 40),
                           active=2.0, radius=3.4),
    "throne_dust": dict(cell="dust", count=10, life=0.8, speed=2.4, drag=2.4,
                        size=(0.32, 0.32), colour=C(STEEL), add=False,
                        shape="disc", radius=1.4),
    "sight_ping": dict(cell="hex", count=1, life=0.9, speed=0, drag=6,
                       size=(0.5, 0.5), colour=C(CYAN, fade=True),
                       shape="point", spin=(0, 120)),
    "sphere_core": dict(cell="dot", count=1, life=1.6, speed=0, drag=6,
                        size_expr=("3.4 - v.particle_age * 1.4",
                                   "3.4 - v.particle_age * 1.4"),
                        colour=C(CRIMSON, fade=False), shape="point"),
    "sphere_orbit": dict(cell="shard", count=0, life=1.2, speed=2.0, drag=0.6,
                         size=(0.42, 0.15), colour=C(STEEL), add=False,
                         steady=(26, 60), active=2.6, radius=3.6,
                         direction="inwards", spin=(0, 300)),
    "sphere_collapse": dict(cell="chevron", count=34, life=0.8, speed=-14.0,
                            drag=0.4, size=(0.42, 0.42), colour=C(CRIMSON),
                            radius=7.0, direction="inwards"),
    "sphere_detonate": dict(cell="shock", count=1, life=1.1, speed=0, drag=6,
                            size_expr=("1.5 + v.particle_age * 46",
                                       "1.5 + v.particle_age * 46"),
                            colour=C(CRIMSON), shape="point",
                            facing="rotate_y"),
    # --- 移動・変身 -------------------------------------------------------
    "flight_trail": dict(cell="streak", count=5, life=0.5, speed=1.4, drag=2.4,
                         size=(0.55, 0.14), colour=C(VIOLET)),
    "flight_burst": dict(cell="lens", count=8, life=0.4, speed=6.0, drag=2.0,
                         size=(0.7, 0.24), colour=C(VIOLET)),
    "cape_wind": dict(cell="smoke", count=4, life=0.7, speed=1.2, drag=2.6,
                      size=(0.5, 0.5), colour=C("#8E1424"), add=False),
    "transform_burst": dict(cell="flash", count=14, life=0.7, speed=10.0,
                            drag=1.2, size=(1.1, 1.1), colour=C(VIOLET)),
    "transform_ring": dict(cell="ring", count=1, life=0.8, speed=0, drag=6,
                           size_expr=("0.5 + v.particle_age * 18",
                                      "0.5 + v.particle_age * 18"),
                           colour=C(VIOLET), shape="point", facing="rotate_y"),
    "revert_smoke": dict(cell="smoke", count=12, life=1.1, speed=2.4, drag=2.4,
                         size=(0.8, 0.8), colour=C("#5A4A6E"), add=False),
    "levitate_dust": dict(cell="dust", count=8, life=0.9, speed=-1.6, drag=1.6,
                          size=(0.24, 0.24), colour=C(VIOLET), shape="disc",
                          radius=1.2, direction="inwards"),
    # --- ブラザーフッド ----------------------------------------------------
    "shift_shimmer": dict(cell="hex", count=14, life=0.6, speed=2.6, drag=2.0,
                          size=(0.4, 0.4), colour=C("#3AA8E0")),
    "venom_drip": dict(cell="drop", count=8, life=0.8, speed=2.4, drag=1.8,
                       size=(0.2, 0.2), colour=C("#3AC86B"), add=False,
                       gravity=6.0),
    "claw_slash": dict(cell="crescent", count=3, life=0.28, speed=2.0, drag=4.0,
                       size=(1.4, 1.4), colour=C("#FFD8D8"), spin=(0, 60)),
    "roar_wave": dict(cell="shock", count=1, life=0.6, speed=0, drag=6,
                      size_expr=("0.8 + v.particle_age * 18",
                                 "0.8 + v.particle_age * 18"),
                      colour=C("#E8A02A"), shape="point", facing="rotate_y"),
    "regen_knit": dict(cell="spark", count=12, life=0.7, speed=1.6, drag=2.4,
                       size=(0.18, 0.18), colour=C("#8EF0A0")),
    "tongue_slime": dict(cell="drop", count=6, life=0.6, speed=3.0, drag=2.0,
                         size=(0.22, 0.22), colour=C(GREEN), add=False,
                         gravity=5.0),
    "leap_dust": dict(cell="plume", count=10, life=0.7, speed=4.0, drag=2.2,
                      size=(0.6, 0.6), colour=C("#9A9A8A"), add=False,
                      shape="disc", radius=0.9),
    "slime_splat": dict(cell="smoke", count=10, life=0.9, speed=3.4, drag=2.0,
                        size=(0.6, 0.6), colour=C(GREEN), add=False),
    "quake_dust": dict(cell="plume", count=16, life=1.2, speed=5.0, drag=1.8,
                       size=(0.9, 0.9), colour=C("#8E8272"), add=False,
                       shape="disc", radius=2.6),
    "quake_crack": dict(cell="crack", count=8, life=0.9, speed=1.0, drag=4.0,
                        size=(1.0, 1.0), colour=C("#5A4A38"), add=False,
                        shape="disc", radius=2.2, facing="rotate_y"),
    "rock_fall": dict(cell="debris", count=12, life=1.4, speed=2.0, drag=0.6,
                      size=(0.5, 0.5), colour=C("#7A6E5E"), add=False,
                      gravity=14.0, spin=(0, 160)),
    "blur_after": dict(cell="smoke", count=3, life=0.35, speed=0.4, drag=4.0,
                       size=(0.9, 1.5), colour=C("#8EB4E0"), add=False),
    "speed_line": dict(cell="streak", count=10, life=0.3, speed=8.0, drag=1.4,
                       size=(0.7, 0.10), colour=C("#C8E0FF")),
    "flame_wave": dict(cell="ember", count=20, life=0.7, speed=8.0, drag=1.4,
                       size=(0.45, 0.45), colour=C("#FF8A2A")),
    "flame_serpent": dict(cell="swirl", count=8, life=0.9, speed=4.0, drag=1.2,
                          size=(0.8, 0.8), colour=C("#FFB24A"), spin=(0, 240)),
    "ember_rise": dict(cell="ember", count=10, life=1.1, speed=-2.0, drag=1.6,
                       size=(0.2, 0.2), colour=C("#FFD86A"), gravity=-2.0),
    "hex_wave": dict(cell="shock", count=1, life=0.7, speed=0, drag=6,
                     size_expr=("0.7 + v.particle_age * 20",
                                "0.7 + v.particle_age * 20"),
                     colour=C(CRIMSON), shape="point", facing="rotate_y"),
    "hex_bolt_trail": dict(cell="dot", count=4, life=0.35, speed=0.8, drag=3.0,
                           size=(0.34, 0.34), colour=C(CRIMSON)),
    "chaos_motes": dict(cell="spark", count=0, life=1.0, speed=1.2, drag=2.0,
                        size=(0.22, 0.22), colour=C(CRIMSON), steady=(12, 26),
                        active=1.6, radius=2.0),
    "tk_lift": dict(cell="chevron", count=10, life=0.6, speed=-3.0, drag=1.4,
                    size=(0.3, 0.3), colour=C(CRIMSON), radius=1.6,
                    direction="inwards"),
    "slam_ring": dict(cell="shock", count=1, life=0.5, speed=0, drag=6,
                      size_expr=("0.8 + v.particle_age * 14",
                                 "0.8 + v.particle_age * 14"),
                      colour=C(EARTH), shape="point", facing="rotate_y"),
    # --- 敵 ---------------------------------------------------------------
    "sentinel_beam_charge": dict(cell="dot", count=1, life=0.9, speed=0, drag=6,
                                 size_expr=("0.2 + v.particle_age * 1.8",
                                            "0.2 + v.particle_age * 1.8"),
                                 colour=C(ORANGE, fade=False), shape="point"),
    "sentinel_beam_trail": dict(cell="beam", count=3, life=0.3, speed=0.8,
                                drag=4.0, size=(1.2, 0.32), colour=C(ORANGE)),
    "sentinel_beam_impact": dict(cell="flash", count=8, life=0.45, speed=7.0,
                                 drag=2.0, size=(0.9, 0.9), colour=C(ORANGE)),
    "sentinel_spark": dict(cell="spark", count=12, life=0.5, speed=6.0,
                           drag=2.2, size=(0.18, 0.18), colour=C("#FFD86A"),
                           gravity=6.0),
    "sentinel_smoke": dict(cell="smoke", count=10, life=1.4, speed=2.0,
                           drag=2.4, size=(0.8, 0.8), colour=C("#3A3A44"),
                           add=False),
    "sentinel_scan": dict(cell="grid", count=1, life=0.8, speed=0, drag=6,
                          size_expr=("0.6 + v.particle_age * 12",
                                     "0.6 + v.particle_age * 12"),
                          colour=C(ORANGE), shape="point", facing="rotate_y"),
    "core_break": dict(cell="flash", count=12, life=0.8, speed=9.0, drag=1.4,
                       size=(1.0, 1.0), colour=C(ORANGE)),
    "mrd_muzzle": dict(cell="flash", count=3, life=0.18, speed=2.0, drag=4.0,
                       size=(0.35, 0.35), colour=C("#FFE0A0")),
    # --- 汎用 -------------------------------------------------------------
    "impact_dust": dict(cell="smoke", count=8, life=0.8, speed=3.0, drag=2.4,
                        size=(0.6, 0.6), colour=C("#9A9A8A"), add=False),
    "heavy_land": dict(cell="shock", count=1, life=0.45, speed=0, drag=6,
                       size_expr=("0.6 + v.particle_age * 12",
                                  "0.6 + v.particle_age * 12"),
                       colour=C("#B0A894"), shape="point", facing="rotate_y",
                       add=False),
    "hurt_spark": dict(cell="spark", count=6, life=0.35, speed=4.0, drag=2.6,
                       size=(0.16, 0.16), colour=C(WHITE), gravity=4.0),
    "blood_red": dict(cell="drop", count=8, life=0.6, speed=4.0, drag=1.8,
                      size=(0.18, 0.18), colour=C("#8E0E1A"), add=False,
                      gravity=8.0),
}


def main() -> None:
    K.ensure_dirs()
    print("particles:")
    build_atlas()
    missing = [n for n in K.PARTICLES if n not in SPEC]
    if missing:
        raise SystemExit(f"SPEC に無いパーティクル: {missing}")
    for name in K.PARTICLES:
        kw = dict(SPEC[name])
        kw.pop("cellsize", None)
        cell = kw.pop("cell")
        write_json(f"{K.PART_DIR}/{name}.particle.json",
                   effect(K.part(name), cell, **kw))
    print(f"  {len(K.PARTICLES)} effects")


if __name__ == "__main__":
    main()
