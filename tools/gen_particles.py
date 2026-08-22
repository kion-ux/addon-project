# -*- coding: utf-8 -*-
"""Custom particle effects + the sprite atlas they read from."""
from __future__ import annotations

import json
import math
import os
import random

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "packs", "kaiju8_RP")
PART_DIR = os.path.join(RP, "particles")
TEX = os.path.join(RP, "textures", "particle")
ATLAS_W = 256
ATLAS_H = 128
CELL = 32
TEXTURE = "textures/particle/kaiju8_particles"

# ---------------------------------------------------------------- atlas
# 16セルでは技ごとの描き分けができなくなったので 8x8 に広げた。上4行は従来の
# 並びをそのまま維持している（uv は自動計算なので既存エフェクトはそのまま動く）。
CELLS = {
    "dot": (0, 0), "spark": (1, 0), "streak": (2, 0), "ring": (3, 0),
    "smoke": (0, 1), "debris": (1, 1), "arc": (2, 1), "crescent": (3, 1),
    "beam": (0, 2), "shock": (1, 2), "drop": (2, 2), "ember": (3, 2),
    "hex": (0, 3), "crack": (1, 3), "dust": (2, 3), "flash": (3, 3),
    # --- 追加分 ---------------------------------------------------------
    "bolt": (4, 0),        # 稲妻。折れ線の落雷
    "thin_arc": (5, 0),    # 細く速い斬撃線
    "burst": (6, 0),       # 放射状の閃光
    "shard": (7, 0),       # 鋭い破片・氷片
    "swirl": (4, 1),       # 渦。回転系の技に
    "splash": (5, 1),      # 飛沫。体液・水切
    "halo": (6, 1),        # 二重の細いリング
    "plume": (7, 1),       # 縦に伸びる噴煙
    "chevron": (4, 2),     # 山形。突き・射線の指向マーク
    "petal": (5, 2),       # 花弁状。炎雨・十二単
    "grid": (6, 2),        # 走査線の入った矩形。ユニソケット表示
    "star4": (7, 2),       # 十字の鋭い輝き
    "wedge": (4, 3),       # くさび。斧の食い込み
    "coil": (5, 3),        # 螺旋。帯電
    "mote": (6, 3),        # ごく小さな粒
    "slashx": (7, 3),      # 交差する二本の斬線
}


def build_atlas() -> None:
    os.makedirs(TEX, exist_ok=True)
    img = Image.new("RGBA", (ATLAS_W, ATLAS_H), (0, 0, 0, 0))
    px = img.load()
    rng = random.Random(8)

    def cell(name):
        cx, cy = CELLS[name]
        return cx * CELL, cy * CELL

    def put(ox, oy, x, y, a, c=(255, 255, 255)):
        if 0 <= x < CELL and 0 <= y < CELL and a > 0:
            px[ox + x, oy + y] = (c[0], c[1], c[2], min(255, int(a)))

    h = CELL / 2

    def pw(v, e):          # guard against fractional powers of negatives
        return max(0.0, v) ** e

    ox, oy = cell("dot")                                   # soft round glow
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            put(ox, oy, x, y, pw(1 - d, 2.2) * 255)

    ox, oy = cell("spark")                                 # 4-point star
    for y in range(CELL):
        for x in range(CELL):
            dx, dy = abs(x - h + .5), abs(y - h + .5)
            v = max(0.0, 1 - pw(dx / h, 0.55) - pw(dy / h, 0.55) + 0.35)
            put(ox, oy, x, y, min(255, v * 420))

    ox, oy = cell("streak")                                # horizontal streak
    for y in range(CELL):
        for x in range(CELL):
            fy = 1 - abs(y - h + .5) / (h * 0.28)
            fx = 1 - abs(x - h + .5) / h
            put(ox, oy, x, y, max(0.0, fy) * pw(fx, 0.6) * 255)

    ox, oy = cell("ring")                                  # thin ring
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            put(ox, oy, x, y, pw(1 - abs(d - 0.82) / 0.13, 1.6) * 255)

    ox, oy = cell("shock")                                 # thick shock ring
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            a = pw(1 - abs(d - 0.72) / 0.28, 1.2) * 255
            put(ox, oy, x, y, a if d < 0.98 else 0)

    ox, oy = cell("smoke")                                 # billowy puff
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            n = 0.96 + 0.24 * math.sin(x * 0.7) * math.cos(y * 0.6)
            put(ox, oy, x, y, pw(1 - d / n, 1.5) * 215)

    ox, oy = cell("dust")                                  # grainy dust
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            a = pw(1 - d, 1.8) * 210
            if rng.random() < 0.35:
                a *= 0.4
            put(ox, oy, x, y, a)

    ox, oy = cell("debris")                                # angular chunk
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            if abs(u) + abs(v * 1.4) < 0.75 and (x * 7 + y * 3) % 11 != 0:
                put(ox, oy, x, y, 255)

    for name, thick, span in (("arc", 0.10, 0.55), ("crescent", 0.19, 0.85)):
        ox, oy = cell(name)                                # slash arc
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

    ox, oy = cell("beam")                                  # capsule beam
    for y in range(CELL):
        for x in range(CELL):
            fy = 1 - abs(y - h + .5) / (h * 0.42)
            put(ox, oy, x, y, pw(fy, 0.5) * 255 if 1 < x < CELL - 2 else 0)

    ox, oy = cell("drop")                                  # teardrop
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            r = 0.55 * (1 - v * 0.55)
            if math.hypot(u, v * 0.8) < r:
                put(ox, oy, x, y, 255)

    ox, oy = cell("ember")                                 # small hot mote
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot((x - h + .5) / (h * 0.45), (y - h + .5) / (h * 0.72))
            put(ox, oy, x, y, pw(1 - d, 1.4) * 255)

    ox, oy = cell("hex")                                   # tech hexagon
    for y in range(CELL):
        for x in range(CELL):
            u, v = abs(x - h + .5) / h, abs(y - h + .5) / h
            d = max(u * 0.866 + v * 0.5, v)
            put(ox, oy, x, y, max(0.0, 1 - abs(d - 0.72) / 0.12) * 255)

    ox, oy = cell("crack")                                 # 枝分かれする放電・亀裂
    # 幹を1本引いてから、そこから3本の枝を出す。細い線が1本だけだと粒に
    # したとき何も見えないので、幹は3px幅、枝は2px幅で明るさを落とす。
    def _branch(sx, sy, dx_bias, length, width, bright):
        x, y = sx, sy
        pts = []
        for _ in range(length):
            if not 1 <= x < CELL - 1 or not 0 <= y < CELL:
                break
            pts.append((x, y))
            for k in range(-(width // 2), width // 2 + 1):
                put(ox, oy, x + k, y, bright - abs(k) * (bright // 3))
            x += rng.choice((-1, 0, 1)) + dx_bias
            y += 1
        return pts

    trunk = _branch(CELL // 2, 0, 0, CELL, 3, 255)
    for frac, bias in ((0.28, -1), (0.52, 1), (0.74, -1)):
        if len(trunk) > 4:
            bx, by = trunk[int(len(trunk) * frac)]
            _branch(bx, by, bias, int(CELL * 0.30), 2, 170)

    ox, oy = cell("flash")                                 # bright cross flare
    for y in range(CELL):
        for x in range(CELL):
            dx, dy = abs(x - h + .5) / h, abs(y - h + .5) / h
            v = max(0.0, 1 - dx * 6) + max(0.0, 1 - dy * 6) + max(0.0, 1 - math.hypot(dx, dy) * 2.2)
            put(ox, oy, x, y, min(255, v * 210))

    # ---- 追加スプライト -------------------------------------------------
    ox, oy = cell("bolt")                                  # 折れ線の稲妻
    for i in range(2):
        x, y = CELL // 2 + (i * 6 - 3), 1
        while y < CELL - 1:
            step = rng.choice((3, 4, 5))
            dx = rng.choice((-5, -4, 4, 5))
            for k in range(step):
                if y + k >= CELL - 1:
                    break
                xx = int(x + dx * k / step)
                for w in (-1, 0, 1):
                    put(ox, oy, xx + w, y + k, 255 if w == 0 else 110)
            x += dx
            y += step
            x = max(2, min(CELL - 3, x))

    ox, oy = cell("thin_arc")                              # 細く速い斬撃線
    # 弧が一周してしまうと輪に見えて斬撃にならない。三分の一周ぶんだけ描き、
    # 両端は細く消す。
    span = 0.36
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            d = math.hypot(u, v)
            ang = math.atan2(v, u)
            if abs(ang) > math.pi * span:
                continue
            taper = max(0.0, 1 - (abs(ang) / (math.pi * span)) ** 2.2)
            a = pw(1 - abs(d - 0.84) / (0.045 + 0.035 * taper), 1.0)
            put(ox, oy, x, y, a * taper * 255)

    ox, oy = cell("burst")                                 # 放射状の閃光
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            d = math.hypot(u, v)
            if d > 1:
                continue
            ang = math.atan2(v, u)
            spokes = abs(math.cos(ang * 6)) ** 6
            a = pw(1 - d, 1.1) * (0.22 + 0.78 * spokes)
            put(ox, oy, x, y, a * 255)

    ox, oy = cell("shard")                                 # 鋭い破片
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            if abs(u) < 0.30 * pw(1 - abs(v), 0.7) + 0.02 and abs(v) < 0.95:
                put(ox, oy, x, y, 255 if abs(u) > 0.10 * (1 - abs(v)) else 190)

    ox, oy = cell("swirl")                                 # 渦
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            d = math.hypot(u, v)
            if d > 0.98 or d < 0.08:
                continue
            ang = math.atan2(v, u)
            band = abs(((ang / math.pi * 1.5 + d * 2.4) % 2.0) - 1.0)
            put(ox, oy, x, y, pw(1 - band, 2.6) * pw(1 - d, 0.5) * 255)

    ox, oy = cell("splash")                                # 飛沫
    for _ in range(26):
        ang = rng.random() * math.tau
        r = 0.25 + rng.random() * 0.72
        cx = h + math.cos(ang) * r * h
        cy = h + math.sin(ang) * r * h
        rad = rng.choice((1, 1, 2, 2, 3))
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                if dx * dx + dy * dy <= rad * rad:
                    put(ox, oy, int(cx) + dx, int(cy) + dy, 255)

    ox, oy = cell("halo")                                  # 二重の細いリング
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / h
            a = max(pw(1 - abs(d - 0.92) / 0.07, 1.4),
                    pw(1 - abs(d - 0.62) / 0.05, 1.4) * 0.7)
            put(ox, oy, x, y, a * 255)

    ox, oy = cell("plume")                                 # 縦に伸びる噴煙
    for y in range(CELL):
        for x in range(CELL):
            v = (y - h + .5) / h
            width = 0.30 + 0.55 * max(0.0, (v + 1) / 2) ** 1.4
            u = abs(x - h + .5) / h
            n = 0.92 + 0.20 * math.sin(x * 0.8 + y * 0.5)
            put(ox, oy, x, y, pw(1 - u / (width * n), 1.3) * 215
                if abs(v) < 0.98 else 0)

    ox, oy = cell("chevron")                               # 山形の指向マーク
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            d = abs(abs(u) * 0.95 + v)
            if abs(u) < 0.92 and abs(v) < 0.92:
                put(ox, oy, x, y, pw(1 - abs(d - 0.30) / 0.16, 1.3) * 255)

    ox, oy = cell("petal")                                 # 花弁
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / (h * 0.98)
            vv = (v + 1) / 2
            width = math.sin(min(1.0, max(0.0, vv)) * math.pi) ** 0.75 * 0.52
            if abs(u) < width:
                edge = 1 - abs(u) / max(width, 1e-6)
                put(ox, oy, x, y, (0.55 + 0.45 * pw(edge, 0.6)) * 255)

    ox, oy = cell("grid")                                  # 走査線の入った矩形
    for y in range(CELL):
        for x in range(CELL):
            u, v = abs(x - h + .5) / h, abs(y - h + .5) / h
            if u > 0.86 or v > 0.86:
                continue
            frame = 1.0 if (u > 0.78 or v > 0.78) else 0.0
            scan = 0.55 if y % 4 == 0 else 0.0
            put(ox, oy, x, y, max(frame, scan) * 255)

    ox, oy = cell("star4")                                 # 十字の鋭い輝き
    for y in range(CELL):
        for x in range(CELL):
            dx, dy = abs(x - h + .5) / h, abs(y - h + .5) / h
            v = max(0.0, 1 - dx * 11) * max(0.0, 1 - dy * 1.05) \
                + max(0.0, 1 - dy * 11) * max(0.0, 1 - dx * 1.05) \
                + max(0.0, 1 - math.hypot(dx, dy) * 5)
            put(ox, oy, x, y, min(255, v * 255))

    ox, oy = cell("wedge")                                 # くさび
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            if v < -0.9 or v > 0.9:
                continue
            width = 0.08 + 0.52 * (v + 0.9) / 1.8
            if abs(u) < width:
                put(ox, oy, x, y, 255 if abs(u) > width - 0.16 else 175)

    ox, oy = cell("coil")                                  # 螺旋の帯電
    for y in range(CELL):
        v = (y - h + .5) / h
        if abs(v) > 0.94:
            continue
        cx = h + math.sin(v * math.pi * 2.6) * h * 0.62
        for k in (-1, 0, 1):
            put(ox, oy, int(cx) + k, y, 255 if k == 0 else 120)

    ox, oy = cell("mote")                                  # ごく小さな粒
    for y in range(CELL):
        for x in range(CELL):
            d = math.hypot(x - h + .5, y - h + .5) / (h * 0.34)
            put(ox, oy, x, y, pw(1 - d, 1.6) * 255)

    ox, oy = cell("slashx")                                # 交差する二本の斬線
    for y in range(CELL):
        for x in range(CELL):
            u, v = (x - h + .5) / h, (y - h + .5) / h
            if math.hypot(u, v) > 0.98:
                continue
            a = max(pw(1 - abs(u - v) / 0.14, 1.2),
                    pw(1 - abs(u + v) / 0.11, 1.2) * 0.85)
            put(ox, oy, x, y, a * 255)

    img.save(os.path.join(TEX, "kaiju8_particles.png"))
    print(f"  particle atlas {ATLAS_W}x{ATLAS_H} ({len(CELLS)} sprites)")


# ------------------------------------------------------------- effects
def uv_of(cell_name):
    cx, cy = CELLS[cell_name]
    return [cx * CELL, cy * CELL]


def effect(identifier, cell, *, count=12, life=0.5, speed=4.0, size=(0.25, 0.25),
           colour=("1", "1", "1", "1"), shape="sphere", radius=0.6,
           direction="outwards", drag=2.0, gravity=0.0, material="particles_blend",
           local=False, spin=None, size_expr=None, active=0.05, steady=None,
           plane="y", offset=("0", "0", "0"), facing="lookat_xyz", stretch=None):
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
            "uv": {"texture_width": ATLAS_W, "texture_height": ATLAS_H,
                   "uv": uv_of(cell), "uv_size": [CELL, CELL]},
        },
        "minecraft:particle_appearance_tinting": {"color": list(colour)},
    }
    if steady:
        comps["minecraft:emitter_rate_steady"] = {"spawn_rate": steady[0],
                                                  "max_particles": steady[1]}
        comps["minecraft:emitter_lifetime_once"] = {"active_time": active}
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
        comps["minecraft:emitter_local_space"] = {"position": True, "rotation": True,
                                                  "velocity": False}
    if spin:
        comps["minecraft:particle_initial_spin"] = {"rotation": spin[0],
                                                    "rotation_rate": spin[1]}
    if stretch:
        comps["minecraft:particle_appearance_billboard"]["facing_camera_mode"] = \
            "direction_x"
    return {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {
                "identifier": identifier,
                "basic_render_parameters": {"material": material, "texture": TEXTURE},
            },
            "components": comps,
        },
    }


def C(hexstr, fade=True):
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    a = "1 - v.particle_age / v.particle_lifetime" if fade else "1"
    return (f"{r:.3f}", f"{g:.3f}", f"{b:.3f}", a)


# 仕様書 §5 エフェクト辞書の色をそのまま使う
TEAL = C("#25E5D8")          # 怪獣8号の発光
TEAL_CORE = C("#CFFFFA")
TEAL_DIM = C("#0A9FA8")
WHITE = C("#EDEFF2")         # 斬撃線
STEEL = C("#9AA3AC")
ICE = C("#BFE3FF")           # 斧の放電
ICE_SOFT = C("#9FD8FF")
FROST = C("#7FD8F0")
MUZZLE = C("#FFE9A8")        # 砲口炎
EMBER = C("#E86A28")         # 体内熱・炸裂
CAUTER = C("#FF6A2A")        # 焼灼
THUNDER = C("#F0D24A")
CRIMSON = C("#C4142A")
VIOLET = C("#3A2450")        # 怪獣の体液
RAIL = C("#E8FFFC")
RAIL_EDGE = C("#7FB6FF")
NUM10 = C("#6BE07A")
DUST = ("0.541", "0.502", "0.439", "0.75 - 0.75 * v.particle_age / v.particle_lifetime")
SMOKE = ("0.078", "0.094", "0.110", "0.62 - 0.62 * v.particle_age / v.particle_lifetime")
STEAM = ("0.902", "0.902", "0.902", "0.6 - 0.6 * v.particle_age / v.particle_lifetime")

EFFECTS = {
    # ---- 変身 -------------------------------------------------------
    "kaiju8:transform_burst": effect("kaiju8:transform_burst", "dot", count=52,
                                     life=0.75, speed=14, size=(0.8, 0.8),
                                     colour=TEAL, radius=0.4, drag=3.4),
    "kaiju8:transform_smoke": effect("kaiju8:transform_smoke", "smoke", count=32,
                                     life=1.5, speed=5.5, size=(1.6, 1.6),
                                     colour=SMOKE, radius=0.8, drag=3.0),
    # ---- 怪獣8号 ----------------------------------------------------
    "kaiju8:seam_glow": effect("kaiju8:seam_glow", "ember", count=8, life=0.9,
                               speed=1.6, size=(0.16, 0.42), colour=TEAL_DIM,
                               radius=0.8, drag=0.9, gravity=-1.6),
    "kaiju8:no8_aura": effect("kaiju8:no8_aura", "ember", count=8, life=0.9,
                              speed=2.2, size=(0.18, 0.46), colour=TEAL,
                              radius=0.75, drag=0.8, gravity=-2.0),
    "kaiju8:energy_roar": effect("kaiju8:energy_roar", "beam", count=10, life=0.55,
                                 speed=16, size=(2.4, 1.0), colour=TEAL_CORE,
                                 radius=0.2, drag=0.6, facing="direction_x"),
    "kaiju8:energy_boost": effect("kaiju8:energy_boost", "streak", count=8, life=0.2,
                                  speed=7, size=(0.7, 0.14), colour=TEAL,
                                  radius=0.4, drag=6, facing="direction_x"),
    "kaiju8:fist_shock": effect("kaiju8:fist_shock", "shock", count=1, life=0.4,
                                speed=0, shape="point", drag=0, colour=TEAL_CORE,
                                facing="lookat_xyz",
                                size_expr=("v.particle_age * 24", "v.particle_age * 24")),
    "kaiju8:regen_knit": effect("kaiju8:regen_knit", "spark", count=12, life=1.0,
                                speed=1.4, size=(0.18, 0.18), colour=TEAL,
                                radius=0.9, drag=1.8),
    "kaiju8:afterimage": effect("kaiju8:afterimage", "dot", count=5, life=0.45,
                                speed=0.4, size=(0.9, 1.6),
                                colour=("0.145", "0.898", "0.847",
                                        "0.45 - 0.45 * v.particle_age / v.particle_lifetime"),
                                radius=0.3, drag=2.0),
    # ---- 保科流 -----------------------------------------------------
    "kaiju8:slash_air": effect("kaiju8:slash_air", "crescent", count=1, life=0.20,
                               speed=0, size=(2.6, 2.6), colour=WHITE, shape="point",
                               spin=("v.particle_random_1 * 360", "0"), drag=0),
    "kaiju8:slash_cross": effect("kaiju8:slash_cross", "arc", count=2, life=0.25,
                                 speed=1.0, size=(3.2, 3.2), colour=WHITE,
                                 shape="point", drag=1,
                                 spin=("v.particle_random_1 * 180 + 45", "0")),
    "kaiju8:slash_scatter": effect("kaiju8:slash_scatter", "streak", count=18,
                                   life=0.30, speed=10, size=(0.8, 0.10),
                                   colour=STEEL, radius=0.6, drag=6,
                                   facing="direction_x"),
    "kaiju8:slash_heavy": effect("kaiju8:slash_heavy", "crescent", count=3, life=0.26,
                                 speed=1.2, size=(4.2, 4.2), colour=WHITE,
                                 shape="point", radius=0.4, drag=1.5,
                                 spin=("v.particle_random_1 * 40 - 20", "0")),
    "kaiju8:slash_12": effect("kaiju8:slash_12", "streak", count=12, life=0.28,
                              speed=-11, size=(1.1, 0.14), colour=NUM10,
                              radius=3.2, drag=3, direction="inwards",
                              facing="direction_x"),
    # ---- 隊式斧術 ---------------------------------------------------
    "kaiju8:axe_arc": effect("kaiju8:axe_arc", "crack", count=8, life=0.30,
                             speed=3.4, size=(0.9, 0.9), colour=ICE, radius=0.5,
                             drag=3.0, spin=("v.particle_random_1 * 360", "0")),
    "kaiju8:axe_backblast": effect("kaiju8:axe_backblast", "smoke", count=14,
                                   life=0.22, speed=9, size=(0.7, 0.7),
                                   colour=ICE_SOFT, radius=0.4, drag=6),
    "kaiju8:axe_frontblast": effect("kaiju8:axe_frontblast", "shock", count=1,
                                    life=0.35, speed=0, shape="point", drag=0,
                                    colour=ICE, facing="lookat_xyz",
                                    size_expr=("v.particle_age * 20",
                                               "v.particle_age * 20")),
    "kaiju8:axe_crescent": effect("kaiju8:axe_crescent", "crescent", count=1,
                                  life=0.4, speed=0, size=(4.0, 4.0),
                                  colour=ICE_SOFT, shape="point", drag=0,
                                  spin=("v.particle_random_1 * 360", "90")),
    # ---- 砲撃 -------------------------------------------------------
    "kaiju8:cannon_muzzle": effect("kaiju8:cannon_muzzle", "flash", count=1,
                                   life=0.20, speed=0, size=(2.4, 2.4),
                                   colour=MUZZLE, shape="point", drag=0),
    "kaiju8:muzzle_flash": effect("kaiju8:muzzle_flash", "flash", count=1, life=0.10,
                                  speed=0, size=(1.4, 1.4), colour=MUZZLE,
                                  shape="point", drag=0),
    "kaiju8:muzzle_sparks": effect("kaiju8:muzzle_sparks", "spark", count=10,
                                   life=0.28, speed=8, size=(0.16, 0.16),
                                   colour=MUZZLE, radius=0.15, drag=5, gravity=3),
    "kaiju8:muzzle_smoke": effect("kaiju8:muzzle_smoke", "smoke", count=10, life=1.5,
                                  speed=2.5, size=(0.9, 0.9), colour=SMOKE,
                                  radius=0.3, drag=2.5, gravity=-0.4),
    "kaiju8:railgun_lance": effect("kaiju8:railgun_lance", "beam", count=1, life=0.6,
                                   speed=0, size=(3.0, 0.8), colour=RAIL,
                                   shape="point", drag=0, facing="direction_x"),
    "kaiju8:beam_trail": effect("kaiju8:beam_trail", "beam", count=1, life=0.30,
                                speed=0, size=(1.6, 0.42), colour=RAIL_EDGE,
                                shape="point", drag=0, facing="direction_x"),
    "kaiju8:beam_impact": effect("kaiju8:beam_impact", "dot", count=16, life=0.45,
                                 speed=7, size=(0.55, 0.55), colour=RAIL,
                                 radius=0.3, drag=4),
    "kaiju8:cannon_charge": effect("kaiju8:cannon_charge", "dot", count=20, life=0.5,
                                   speed=-3.5, size=(0.30, 0.30), colour=MUZZLE,
                                   radius=2.0, drag=1.0, direction="inwards"),
    # ---- 隊式銃剣術 -------------------------------------------------
    "kaiju8:cauterize": effect("kaiju8:cauterize", "ember", count=12, life=2.0,
                               speed=1.2, size=(0.24, 0.24), colour=CAUTER,
                               radius=0.7, drag=2.2, gravity=-0.6),
    "kaiju8:burst_slash": effect("kaiju8:burst_slash", "flash", count=4, life=0.5,
                                 speed=4.0, size=(1.6, 1.6), colour=CAUTER,
                                 radius=0.8, drag=3.0),
    "kaiju8:branch_blast": effect("kaiju8:branch_blast", "streak", count=7, life=0.6,
                                  speed=11, size=(1.3, 0.18), colour=MUZZLE,
                                  radius=0.3, drag=3.5, facing="direction_x"),
    # ---- ユニソケット -----------------------------------------------
    "kaiju8:socket_burst": effect("kaiju8:socket_burst", "dot", count=12, life=0.3,
                                  speed=8, size=(0.5, 0.5), colour=EMBER,
                                  radius=0.2, drag=5),
    "kaiju8:socket_freeze": effect("kaiju8:socket_freeze", "spark", count=16,
                                   life=0.9, speed=5, size=(0.42, 0.42),
                                   colour=FROST, radius=0.4, drag=4.5),
    "kaiju8:socket_thunder": effect("kaiju8:socket_thunder", "crack", count=7,
                                    life=0.25, speed=5, size=(0.8, 0.8),
                                    colour=THUNDER, radius=0.3, drag=4,
                                    spin=("v.particle_random_1 * 360", "0")),
    # ---- 怪獣 -------------------------------------------------------
    "kaiju8:kaiju_blood": effect("kaiju8:kaiju_blood", "drop", count=14, life=0.6,
                                 speed=5, size=(0.30, 0.38), colour=VIOLET,
                                 radius=0.5, drag=1.2, gravity=8),
    "kaiju8:core_break": effect("kaiju8:core_break", "shock", count=1, life=0.5,
                                speed=0, shape="point", drag=0, colour=FROST,
                                facing="lookat_xyz",
                                size_expr=("v.particle_age * 22", "v.particle_age * 22")),
    "kaiju8:roar_wave": effect("kaiju8:roar_wave", "ring", count=1, life=0.7, speed=0,
                               shape="point", drag=0, colour=EMBER,
                               facing="lookat_xyz",
                               size_expr=("v.particle_age * 18", "v.particle_age * 18")),
    "kaiju8:kaiju_aura": effect("kaiju8:kaiju_aura", "ember", count=10, life=0.8,
                                speed=1.8, size=(0.22, 0.42), colour=EMBER,
                                radius=0.9, drag=1.0, gravity=-1.4),
    "kaiju8:acid_splash": effect("kaiju8:acid_splash", "drop", count=18, life=0.8,
                                 speed=6, size=(0.30, 0.38), colour=VIOLET,
                                 radius=0.4, drag=1.5, gravity=7),
    "kaiju8:no9_regen": effect("kaiju8:no9_regen", "spark", count=12, life=0.6,
                               speed=2.2, size=(0.22, 0.22), colour=CRIMSON,
                               radius=0.8, drag=1.6, gravity=-2.0),
    "kaiju8:kaiju10_seam": effect("kaiju8:kaiju10_seam", "ember", count=8, life=0.9,
                                  speed=1.4, size=(0.18, 0.36),
                                  colour=C("#E0329B"), radius=1.0, drag=1.0,
                                  gravity=-1.0),
    "kaiju8:steam_vent": effect("kaiju8:steam_vent", "smoke", count=20, life=2.0,
                                speed=7, size=(1.2, 1.2), colour=STEAM, radius=0.7,
                                drag=3.5, gravity=-1.0),
    "kaiju8:molt": effect("kaiju8:molt", "debris", count=22, life=1.4, speed=6,
                          size=(0.32, 0.32), colour=C("#D8CBB0"), radius=0.6,
                          drag=1.0, gravity=8,
                          spin=("v.particle_random_2 * 360", "180")),
    # ---- 地形・衝撃 -------------------------------------------------
    "kaiju8:impact_dust": effect("kaiju8:impact_dust", "dust", count=26, life=0.9,
                                 speed=5.5, size=(0.7, 0.7), colour=DUST,
                                 shape="disc", radius=1.2, drag=3.2, gravity=1.2),
    "kaiju8:debris": effect("kaiju8:debris", "debris", count=18, life=1.1, speed=7,
                            size=(0.22, 0.22), colour=DUST, radius=0.5, drag=0.6,
                            gravity=9.0, spin=("v.particle_random_2 * 360", "220")),
    "kaiju8:heavy_land": effect("kaiju8:heavy_land", "smoke", count=22, life=1.0,
                                speed=6, size=(1.1, 1.1), colour=DUST, shape="disc",
                                radius=1.6, drag=4.0),
    "kaiju8:shock_ring": effect("kaiju8:shock_ring", "shock", count=1, life=0.42,
                                speed=0, shape="point", drag=0, colour=FROST,
                                facing="rotate_y",
                                size_expr=("v.particle_age * 14", "v.particle_age * 14")),
    "kaiju8:shock_ring_gold": effect("kaiju8:shock_ring_gold", "shock", count=1,
                                     life=0.5, speed=0, shape="point", drag=0,
                                     colour=THUNDER, facing="rotate_y",
                                     size_expr=("v.particle_age * 16",
                                                "v.particle_age * 16")),
    "kaiju8:crack_burst": effect("kaiju8:crack_burst", "crack", count=8, life=0.5,
                                 speed=3.0, size=(0.8, 0.8), colour=DUST, radius=0.4,
                                 drag=3.0, spin=("v.particle_random_1 * 360", "0")),
    "kaiju8:dash_dust": effect("kaiju8:dash_dust", "dust", count=14, life=0.55,
                               speed=3.5, size=(0.55, 0.55), colour=DUST,
                               shape="disc", radius=0.5, drag=3.5),
    # ---- 装備・UI 演出 ----------------------------------------------
    "kaiju8:suit_shield": effect("kaiju8:suit_shield", "hex", count=14, life=1.2,
                                 speed=1.0, size=(0.7, 0.7), colour=FROST,
                                 radius=1.4, drag=1.0),
    "kaiju8:release_aura": effect("kaiju8:release_aura", "spark", count=10, life=0.7,
                                  speed=2.4, size=(0.16, 0.16), colour=THUNDER,
                                  radius=0.7, drag=1.2, gravity=-3.0),
    "kaiju8:release_burst": effect("kaiju8:release_burst", "hex", count=10, life=0.6,
                                   speed=4.0, size=(0.5, 0.5), colour=THUNDER,
                                   radius=0.5, drag=2.5),
    "kaiju8:alert_flare": effect("kaiju8:alert_flare", "hex", count=14, life=1.6,
                                 speed=1.4, size=(0.6, 0.6), colour=CRIMSON,
                                 shape="disc", radius=3.0, drag=0.8, gravity=-0.7),
}


# ===========================================================================
#  技ごとの演出用エフェクト
#
#  同じ「斬撃線ひとつ」が全部の技から出ていたのをやめるための追加分。
#  役割ごとに family() でまとめてあるので、色違いを増やすのが安い。
#  色は原作の描写（白い斬撃線・青白い放電・砲口の橙・怪獣の紫の体液）に寄せた。
# ===========================================================================
def A(hexstr, peak=1.0):
    """peak を落とした着色。霞や残像のように薄く残るものに使う。"""
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return (f"{r:.3f}", f"{g:.3f}", f"{b:.3f}",
            f"{peak} - {peak} * v.particle_age / v.particle_lifetime")


def grow(rate, aspect=1.0):
    """生まれてから広がり続ける輪。衝撃波・凍結殻・虹彩。"""
    return (f"v.particle_age * {rate}", f"v.particle_age * {rate * aspect}")


def add(identifier, cell, **kw):
    EFFECTS[identifier] = effect(identifier, cell, **kw)


def family(base, cell, variants, **shared):
    """同じ形・同じ動きで色だけ違う一族をまとめて定義する。"""
    for suffix, colour in variants.items():
        over = {}
        if isinstance(colour, tuple) and len(colour) == 2 and isinstance(colour[1], dict):
            colour, over = colour
        add(f"kaiju8:{base}_{suffix}", cell, colour=colour, **{**shared, **over})


# ---- 斬撃線 -----------------------------------------------------------
# 刃が通った跡に残る棒。太さと残る長さで技を描き分ける。
CUT = C("#DFF3FF")
CUT_HEAVY = C("#EDEFF2")
add("kaiju8:cut_line", "beam", count=1, life=0.30, speed=0, size=(2.4, 0.09),
    colour=CUT, shape="point", drag=0, spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:cut_line_heavy", "beam", count=1, life=0.85, speed=0, size=(3.4, 0.20),
    colour=CUT_HEAVY, shape="point", drag=0,
    spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:cut_line_faint", "beam", count=1, life=0.22, speed=0, size=(2.0, 0.06),
    colour=A("#E0E6EC", 0.30), shape="point", drag=0,
    spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:cut_slat", "beam", count=1, life=0.75, speed=0, size=(4.2, 0.05),
    colour=CUT, shape="point", drag=0)
# 囮の線。本物より細く暗い。「弱く見える」ことが役目なので薄さは仕様。
add("kaiju8:feint_line", "beam", count=1, life=0.22, speed=0, size=(2.0, 0.06),
    colour=A("#E0E6EC", 0.30), shape="point", drag=0,
    spin=("v.particle_random_1 * 360", "0"))
# 順の太刀と逆の太刀。角度を焼き込んであるので、交差討ちでは2tick差で X に、
# 逆拍子では7tick差で「割れた拍子」になる。回転を乱数にしないのが肝。
add("kaiju8:cut_line_ko", "beam", count=1, life=0.30, speed=0, size=(2.6, 0.10),
    colour=CUT, shape="point", drag=0, spin=("-42", "0"))
add("kaiju8:cut_line_gyaku", "beam", count=1, life=0.38, speed=0, size=(2.6, 0.10),
    colour=STEEL, shape="point", drag=0, spin=("42", "6"))
# 二刀ぶんの対の弧
add("kaiju8:twin_arc", "arc", count=2, life=0.22, speed=1.4, size=(2.8, 2.8),
    colour=CUT, radius=0.35, drag=3,
    spin=("v.particle_random_1 * 104 - 52", "0"))

# 曲がった斬撃線。細く速い。
family("cut_arc", "thin_arc",
       {"white": CUT_HEAVY, "gold": C("#FFF4B0"), "green": C("#EAFFF0")},
       count=1, life=0.22, speed=0, size=(3.4, 3.4), shape="point", drag=0,
       spin=("v.particle_random_1 * 360", "0"))

# 交差する二刀・十字斬り
add("kaiju8:cut_cross", "slashx", count=1, life=0.22, speed=0, size=(2.6, 2.6),
    colour=CUT_HEAVY, shape="point", drag=0,
    spin=("v.particle_random_1 * 90", "0"))
add("kaiju8:tail_edge", "slashx", count=1, life=0.26, speed=0, size=(2.8, 2.8),
    colour=NUM10, shape="point", drag=0, spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:cross_flash", "flash", count=1, life=0.15, speed=0, size=(1.9, 1.9),
    colour=CUT_HEAVY, shape="point", drag=0)

# ---- 真空・弧 ---------------------------------------------------------
add("kaiju8:vacuum_edge", "crescent", count=1, life=0.16, speed=0,
    colour=CUT_HEAVY, shape="point", drag=0, size_expr=grow(9.0),
    spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:moon_arc", "crescent", count=1, life=0.55, speed=0, size=(5.2, 5.2),
    colour=C("#DCEEFF"), shape="point", drag=0,
    spin=("v.particle_random_1 * 360", "40"))
add("kaiju8:vacuum_wake", "streak", count=8, life=0.25, speed=-7, size=(0.8, 0.08),
    colour=STEEL, radius=1.3, drag=4, direction="inwards", facing="direction_x")
add("kaiju8:air_ring", "ring", count=1, life=0.45, speed=0, colour=C("#EAF6FF"),
    shape="point", drag=0, size_expr=grow(7.0), facing="rotate_y")
add("kaiju8:midare_shard", "arc", count=6, life=0.34, speed=8, size=(0.65, 0.65),
    colour=CUT_HEAVY, radius=0.4, drag=3,
    spin=("v.particle_random_1 * 360", "v.particle_random_2 * 700 - 350"))

# ---- 抜刀・霞・残像 ---------------------------------------------------
add("kaiju8:draw_gleam", "star4", count=1, life=0.13, speed=0, size=(1.2, 1.2),
    colour=CUT, shape="point", drag=0)
add("kaiju8:oboro_ghost", "dot", count=3, life=0.55, speed=0.3, size=(0.85, 1.75),
    colour=A("#B8C7D6", 0.32), radius=0.35, drag=3)
add("kaiju8:kasumi_haze", "smoke", count=10, life=1.15, speed=1.2, size=(1.35, 1.35),
    colour=A("#E0E6EC", 0.26), radius=1.6, drag=2.6, gravity=-0.25)
add("kaiju8:haze_burst", "dust", count=14, life=0.40, speed=9, size=(0.9, 0.9),
    colour=A("#E0E6EC", 0.45), radius=0.6, drag=5)

# ---- 怪獣の体液 -------------------------------------------------------
add("kaiju8:sever_spurt", "drop", count=12, life=0.65, speed=9, size=(0.20, 0.36),
    colour=VIOLET, radius=0.35, drag=2.6, gravity=5.5, facing="direction_y")
add("kaiju8:blood_mist", "smoke", count=8, life=0.95, speed=3.2, size=(0.6, 0.6),
    colour=A("#3A2450", 0.50), radius=0.5, drag=3.4, gravity=-0.6)
add("kaiju8:blood_splash", "splash", count=10, life=0.50, speed=8, size=(0.45, 0.45),
    colour=VIOLET, radius=0.4, drag=4)
add("kaiju8:wound_hole", "ring", count=1, life=0.70, speed=0, colour=VIOLET,
    shape="point", drag=0, size_expr=grow(1.6))

# ---- 刃と破片 ---------------------------------------------------------
add("kaiju8:blade_dust", "dust", count=10, life=0.50, speed=2.6, size=(0.16, 0.16),
    colour=STEEL, radius=0.5, drag=3, gravity=1.4)
add("kaiju8:steel_shard", "shard", count=10, life=0.55, speed=9, size=(0.13, 0.30),
    colour=STEEL, radius=0.4, drag=3, gravity=4.5, facing="direction_y")

# ---- 7式「十二単」 ----------------------------------------------------
add("kaiju8:junihitoe_ring", "ring", count=1, life=0.42, speed=0, size=(2.8, 2.8),
    colour=NUM10, shape="point", drag=0)
add("kaiju8:junihitoe_bloom", "shock", count=1, life=0.45, speed=0, colour=NUM10,
    shape="point", drag=0, size_expr=grow(26.0))

# ---- 放電と落雷 -------------------------------------------------------
family("charge_arc", "crack", {"ice": ICE, "gold": THUNDER},
       count=5, life=0.22, speed=-2.6, size=(0.45, 0.45), radius=1.1, drag=1.6,
       direction="inwards", spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:bolt_strike", "bolt", count=1, life=0.16, speed=0, size=(1.2, 4.6),
    colour=C("#FFF7D2"), shape="point", drag=0)
add("kaiju8:bolt_fringe", "bolt", count=5, life=0.20, speed=5, size=(0.7, 1.8),
    colour=ICE, radius=0.5, drag=4)
add("kaiju8:bolt_spit", "bolt", count=5, life=0.16, speed=6, size=(0.55, 0.55),
    colour=THUNDER, radius=0.3, drag=5)
add("kaiju8:coil_charge", "coil", count=3, life=0.30, speed=0.6, size=(0.42, 0.90),
    colour=ICE, radius=0.2, drag=2)

# ---- 地面 -------------------------------------------------------------
add("kaiju8:ground_fissure", "crack", count=12, life=0.75, speed=5, size=(1.5, 1.5),
    colour=C("#6E777F"), radius=0.4, drag=5, shape="disc", plane="y",
    spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:ejecta", "debris", count=12, life=0.90, speed=9, size=(0.34, 0.34),
    colour=C("#B9C4CC"), radius=0.5, drag=2.2, gravity=7.0, shape="disc", plane="y",
    spin=("v.particle_random_1 * 360", "v.particle_random_2 * 500 - 250"))

# ---- 2式「水切」 ------------------------------------------------------
add("kaiju8:skim_bead", "drop", count=8, life=0.45, speed=7.5, size=(0.22, 0.30),
    colour=ICE_SOFT, radius=0.4, drag=2.4, gravity=6.0)
add("kaiju8:skim_wake", "streak", count=9, life=0.22, speed=12, size=(1.4, 0.16),
    colour=ICE, radius=0.3, drag=5, facing="direction_x")
add("kaiju8:flat_slab", "streak", count=1, life=0.22, speed=0, size=(7.0, 0.5),
    colour=C("#D6ECFF"), shape="point", drag=0)

# ---- 照準 -------------------------------------------------------------
add("kaiju8:aim_line", "beam", count=1, life=0.12, speed=0, size=(1.9, 0.09),
    colour=A("#8FD0FF", 0.55), shape="point", drag=0)
add("kaiju8:aim_dot", "mote", count=1, life=0.40, speed=0, size=(0.08, 0.08),
    colour=C("#7FB6FF", fade=False), shape="point", drag=0)
add("kaiju8:aim_lock", "halo", count=1, life=0.45, speed=0, colour=C("#7FB6FF"),
    shape="point", drag=0, size_expr=("2.6 - v.particle_age * 3.6",
                                      "2.6 - v.particle_age * 3.6"))
add("kaiju8:lock_reticle", "chevron", count=4, life=0.70, speed=-1.6,
    size=(0.5, 0.5), colour=C("#FF3B30"), radius=1.4, drag=1.4,
    direction="inwards", spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:scan_grid", "grid", count=1, life=0.60, speed=0, size=(0.9, 0.9),
    colour=A("#FF6B5A", 0.7), shape="point", drag=0)

# ---- 貫通 -------------------------------------------------------------
add("kaiju8:pierce_lance", "beam", count=1, life=0.22, speed=0, size=(2.6, 0.30),
    colour=RAIL, shape="point", drag=0)
add("kaiju8:pierce_hole", "ring", count=1, life=0.30, speed=0, size=(1.2, 1.2),
    colour=C("#CFF6FF"), shape="point", drag=0)
add("kaiju8:round_impact", "burst", count=1, life=0.18, speed=0, size=(0.95, 0.95),
    colour=RAIL, shape="point", drag=0)

# ---- 銃口まわり -------------------------------------------------------
add("kaiju8:muzzle_brake", "smoke", count=8, life=0.32, speed=13, size=(0.5, 0.5),
    colour=A("#C9CDD4", 0.8), radius=0.2, drag=6)
add("kaiju8:muzzle_star", "star4", count=1, life=0.09, speed=0, size=(1.05, 1.05),
    colour=MUZZLE, shape="point", drag=0)
# 拳銃の火は小さい。サイドアームであることが一目で読めなければ意味がない
add("kaiju8:pistol_flash", "star4", count=1, life=0.07, speed=0, size=(0.55, 0.55),
    colour=MUZZLE, shape="point", drag=0)
# 髪の毛のような弾道。砲撃線(beam_trail 1.6x0.42)と絶対に混ざらない細さ
add("kaiju8:bullet_line", "beam", count=1, life=0.16, speed=0, size=(1.3, 0.05),
    colour=RAIL, shape="point", drag=0)
# 発射筒の火。弾種で色が変わるので、撃つ前に何が出るか分かる
add("kaiju8:tube_flash", "burst", count=1, life=0.16, speed=0, size=(2.0, 2.0),
    colour=MUZZLE, shape="point", drag=0)
add("kaiju8:tube_flash_hot", "burst", count=1, life=0.16, speed=0, size=(1.7, 1.7),
    colour=CAUTER, shape="point", drag=0)
add("kaiju8:muzzle_frost", "burst", count=1, life=0.16, speed=0, size=(1.6, 1.6),
    colour=ICE, shape="point", drag=0)
# ユニソケットは銃口の火だけで弾種が分かる。炸裂=橙の放射、凍結=冷気環、発雷=十字
add("kaiju8:muzzle_he", "burst", count=1, life=0.14, speed=0, size=(1.5, 1.5),
    colour=EMBER, shape="point", drag=0)
add("kaiju8:barrel_vent", "smoke", count=10, life=1.2, speed=6, size=(0.6, 0.9),
    colour=A("#FADBA0", 0.65), radius=0.4, drag=4, gravity=-1.2)
add("kaiju8:brass_case", "debris", count=1, life=1.1, speed=4.5, size=(0.14, 0.20),
    colour=C("#D9A441", fade=False), radius=0.15, drag=1.2, gravity=9.0,
    spin=("v.particle_random_1 * 360", "v.particle_random_2 * 900 - 450"))
add("kaiju8:slide_puff", "smoke", count=2, life=0.50, speed=1.2, size=(0.26, 0.26),
    colour=A("#14181C", 0.55), radius=0.15, drag=3, gravity=-0.8)

# 曳光。弾がいまどこにいるかを示す短い尾。
family("tracer", "streak",
       {"gold": C("#FFD98A"), "round": C("#7FB6FF")},
       count=1, life=0.16, speed=0, size=(0.9, 0.13), shape="point", drag=0,
       facing="direction_x")
add("kaiju8:tracer_frost", "shard", count=1, life=0.20, speed=0, size=(0.46, 0.16),
    colour=ICE, shape="point", drag=0, facing="direction_x")
add("kaiju8:tracer_volt", "coil", count=1, life=0.18, speed=0, size=(0.34, 0.34),
    colour=THUNDER, shape="point", drag=0)

# ---- レールガン -------------------------------------------------------
add("kaiju8:rail_lock", "hex", count=6, life=0.50, speed=-2, size=(0.55, 0.55),
    colour=C("#7FB6FF"), radius=1.0, drag=1.2, direction="inwards")
add("kaiju8:rail_core", "beam", count=1, life=0.45, speed=0, size=(3.4, 0.34),
    colour=C("#FFFFFF"), shape="point", drag=0)

# ---- 煙と土砂 ---------------------------------------------------------
add("kaiju8:backblast", "smoke", count=14, life=0.70, speed=16, size=(1.3, 1.3),
    colour=A("#262B31", 0.85), radius=0.5, drag=5)
add("kaiju8:blast_smoke", "plume", count=3, life=1.6, speed=3, size=(1.5, 2.2),
    colour=A("#14181C", 0.7), radius=0.8, drag=2.4, gravity=-1.0)
add("kaiju8:shell_smoke", "smoke", count=2, life=0.85, speed=0.9, size=(0.42, 0.42),
    colour=A("#8A806F", 0.7), radius=0.3, drag=3, gravity=-0.7)
add("kaiju8:dirt_column", "plume", count=2, life=1.0, speed=6, size=(0.85, 1.5),
    colour=A("#8A806F", 0.85), radius=0.5, drag=3, gravity=3.0)
add("kaiju8:dust_wave", "dust", count=3, life=0.80, speed=4.5, size=(0.9, 0.55),
    colour=A("#8A806F", 0.7), radius=0.6, drag=4, shape="disc", plane="y")
add("kaiju8:updraft", "plume", count=6, life=0.70, speed=2, size=(0.65, 1.8),
    colour=A("#8A8070", 0.6), radius=1.0, drag=2.5, gravity=-2.2,
    shape="disc", plane="y")

# ---- 炸裂 -------------------------------------------------------------
family("detonation", "burst",
       {"gold": MUZZLE, "ember": EMBER, "hot": CAUTER, "teal": TEAL_CORE},
       count=1, life=0.26, speed=0, size=(4.2, 4.2), shape="point", drag=0)

# ---- 輪 ---------------------------------------------------------------
family("halo", "halo",
       {"gold": THUNDER, "ice": ICE, "sky": C("#7EA8FF"), "pale": C("#EAF2FF"),
        "green": C("#C8FFD2"), "teal": TEAL, "red": C("#FF3B30")},
       count=1, life=0.32, speed=0, shape="point", drag=0, size_expr=grow(11.0))

# ---- 衝撃波 -----------------------------------------------------------
family("quake", "shock",
       {"dust": C("#E0D2B4"), "teal": TEAL_CORE, "green": NUM10},
       count=1, life=0.55, speed=0, shape="point", drag=0, size_expr=grow(24.0),
       facing="rotate_y")

# ---- 指向マーク -------------------------------------------------------
family("chevron", "chevron",
       {"white": CUT_HEAVY, "ember": CAUTER, "sky": C("#7EA8FF"), "teal": TEAL_DIM},
       count=1, life=0.20, speed=0, size=(0.8, 0.8), shape="point", drag=0)

# ---- 火 ---------------------------------------------------------------
add("kaiju8:wound_fire", "petal", count=6, life=0.55, speed=4.5, size=(0.35, 0.75),
    colour=CAUTER, radius=0.35, drag=3.4, gravity=-1.6, facing="direction_y")
add("kaiju8:fire_gel", "drop", count=12, life=0.90, speed=7, size=(0.24, 0.32),
    colour=EMBER, radius=0.4, drag=2.4, gravity=6.5, facing="direction_y")
add("kaiju8:scorch_ring", "ring", count=1, life=0.60, speed=0, colour=CAUTER,
    shape="point", drag=0, size_expr=grow(3.2), facing="rotate_y")
add("kaiju8:ember_rain", "ember", count=7, life=1.1, speed=2.2, size=(0.14, 0.30),
    colour=CAUTER, radius=0.7, drag=2.0, gravity=-1.8)
add("kaiju8:heat_smoke", "plume", count=3, life=1.5, speed=2.2, size=(1.0, 1.6),
    colour=A("#4A3226", 0.65), radius=0.6, drag=2.6, gravity=-1.4)
add("kaiju8:powder_burn", "mote", count=6, life=0.90, speed=1.4, size=(0.10, 0.10),
    colour=EMBER, radius=0.5, drag=2.2, gravity=-1.0)

# ---- 氷 ---------------------------------------------------------------
add("kaiju8:frost_mist", "smoke", count=8, life=1.6, speed=1.6, size=(1.0, 0.7),
    colour=A("#BFE6FA", 0.55), radius=1.2, drag=3, shape="disc", plane="y")
add("kaiju8:frost_trail", "shard", count=4, life=0.35, speed=1, size=(0.22, 0.50),
    colour=C("#F2FDFF"), radius=0.3, drag=2.4)
add("kaiju8:ice_shard", "shard", count=10, life=0.70, speed=7, size=(0.20, 0.55),
    colour=C("#F2FDFF"), radius=0.4, drag=3, gravity=4.0, facing="direction_y")
add("kaiju8:frost_creep", "crack", count=6, life=1.2, speed=1.4, size=(1.1, 1.1),
    colour=C("#3FA8D8"), radius=0.9, drag=4, shape="disc", plane="y",
    spin=("v.particle_random_1 * 360", "0"))
add("kaiju8:ice_spike", "shard", count=2, life=1.1, speed=0.6, size=(0.45, 1.5),
    colour=ICE, radius=0.5, drag=3, gravity=-1.0)
add("kaiju8:frost_dust", "mote", count=10, life=1.4, speed=1.2, size=(0.10, 0.10),
    colour=ICE, radius=0.9, drag=2.2, gravity=0.8)

# ---- ユニソケットの表示チップ / 機関部の灯 -----------------------------
family("chit", "grid",
       {"he": EMBER, "ice": FROST, "thunder": THUNDER, "drone": C("#5FE8FF")},
       count=1, life=0.28, speed=0.8, size=(0.42, 0.30), shape="point", drag=1.0)
add("kaiju8:drone_link", "mote", count=1, life=0.50, speed=0, size=(0.09, 0.09),
    colour=C("#5FE8FF", fade=False), shape="point", drag=0)
add("kaiju8:drone_beam", "beam", count=1, life=0.18, speed=0, size=(1.4, 0.16),
    colour=C("#5FE8FF"), shape="point", drag=0)

# ---- 怪獣8号 ---------------------------------------------------------
add("kaiju8:no8_charge", "mote", count=6, life=0.28, speed=-6, size=(0.12, 0.12),
    colour=TEAL_CORE, radius=1.2, drag=1.4, direction="inwards")
add("kaiju8:no8_launch", "plume", count=10, life=0.50, speed=9, size=(0.8, 1.9),
    colour=A("#0A9FA8", 0.8), radius=1.0, drag=4, shape="disc", plane="y")
add("kaiju8:no8_seam_trail", "ember", count=2, life=0.50, speed=1.2, size=(0.10, 0.26),
    colour=TEAL, radius=0.45, drag=1.6, gravity=-1.4)
add("kaiju8:no8_maw", "dot", count=1, life=0.60, speed=0, size=(2.3, 2.3),
    colour=TEAL_CORE, shape="point", drag=0)
add("kaiju8:no8_coil", "coil", count=2, life=0.30, speed=0, size=(1.4, 1.4),
    colour=TEAL_DIM, shape="point", drag=0)

# ---- ナンバーズ2 (メインバースト) ------------------------------------
add("kaiju8:burst_charge", "mote", count=14, life=0.45, speed=-5, size=(0.14, 0.14),
    colour=C("#FFB347"), radius=1.5, drag=1.2, direction="inwards")
add("kaiju8:burst_core", "coil", count=1, life=0.30, speed=0, size=(1.1, 1.1),
    colour=C("#FFB347"), shape="point", drag=0)
add("kaiju8:sonic_wake", "streak", count=1, life=0.25, speed=0, size=(0.9, 0.06),
    colour=C("#FAFAFF"), shape="point", drag=0, facing="direction_x")
add("kaiju8:impact_wind", "plume", count=1, life=0.50, speed=2, size=(0.5, 1.4),
    colour=A("#D9D4CC", 0.6), shape="point", drag=0)

# ---- ナンバーズ4 ------------------------------------------------------
add("kaiju8:thrust_flame", "plume", count=6, life=0.35, speed=3, size=(0.30, 0.75),
    colour=C("#EAF2FF"), radius=0.3, drag=3.5)
add("kaiju8:overheat_vent", "plume", count=5, life=0.80, speed=3, size=(0.35, 0.70),
    colour=A("#FF9E5C", 0.7), radius=0.4, drag=3, gravity=-1.6)
add("kaiju8:launch_bloom", "star4", count=4, life=0.30, speed=4, size=(0.7, 0.7),
    colour=C("#7EA8FF"), radius=0.4, drag=3)
add("kaiju8:spin_wind", "swirl", count=1, life=0.50, speed=0, size=(4.5, 4.5),
    colour=A("#9AA3AC", 0.55), shape="point", drag=0,
    spin=("v.particle_random_1 * 360", "420"))

# ---- ナンバーズ10 -----------------------------------------------------
add("kaiju8:tail_gust", "streak", count=1, life=0.30, speed=0, size=(1.0, 0.08),
    colour=C("#D9FFE6"), shape="point", drag=0, facing="direction_x")
add("kaiju8:release_intake", "mote", count=16, life=0.60, speed=-6, size=(0.13, 0.13),
    colour=NUM10, radius=2.0, drag=1.2, direction="inwards")
add("kaiju8:release_pillar", "beam", count=1, life=0.60, speed=0, size=(0.55, 2.4),
    colour=C("#C8FFD2"), shape="point", drag=0)
add("kaiju8:release_ember", "ember", count=6, life=1.0, speed=2, size=(0.16, 0.40),
    colour=NUM10, radius=0.8, drag=1.6, gravity=-2.0)

# ---- ナンバーズ1 ------------------------------------------------------
add("kaiju8:eye_flash", "star4", count=3, life=0.28, speed=2, size=(0.9, 0.9),
    colour=C("#FFF1EC"), radius=0.7, drag=3)

# ---- 銃剣の枝 ---------------------------------------------------------
add("kaiju8:branch_lance", "wedge", count=1, life=0.30, speed=0, size=(0.5, 2.2),
    colour=C("#FFF0C0"), shape="point", drag=0)
add("kaiju8:branch_bloom", "star4", count=1, life=0.28, speed=0, size=(2.4, 2.4),
    colour=MUZZLE, shape="point", drag=0)


def main() -> None:
    print("particles:")
    build_atlas()
    os.makedirs(PART_DIR, exist_ok=True)
    keep = {i.split(":")[1] + ".particle.json" for i in EFFECTS}
    for stale in os.listdir(PART_DIR):
        if stale.endswith(".particle.json") and stale not in keep:
            os.remove(os.path.join(PART_DIR, stale))
    for identifier, doc in EFFECTS.items():
        name = identifier.split(":")[1]
        with open(os.path.join(PART_DIR, name + ".particle.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    print(f"  {len(EFFECTS)} particle effects")


if __name__ == "__main__":
    main()
