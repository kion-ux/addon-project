# -*- coding: utf-8 -*-
"""パーティクル: スプライトアトラスと、色・大きさ・寿命をスクリプトから渡す汎用パーティクル。

超次元の作り方（白で描いたスプライトを MolangVariableMap の v.cr/v.cg/v.cb で染める）を
そのまま使い、スプライト関数と部品（instant / P_sphere / motion …）は gen_hd_particles から借りる。

スクリプトから渡す変数（全て任意）:
  v.cr v.cg v.cb  色 (0..1)     v.size 大きさ    v.life 寿命 (秒)   v.count 粒数
  v.speed 初速    v.vx v.vy v.vz 向き    v.spread 散らばり   v.rot 回転   v.len 線の長さ
"""
from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image

import aot_common as C
from aot_common import NS, RP, write_json
import gen_hd_particles as HP
from gen_hd_particles import (AGE, COL, FADE, FADE_IN_OUT, P_disc, P_point, P_sphere, field,
                              instant, life, merge, motion, rgba_from, speed, spin)

PART_DIR = os.path.join(RP, "particles")
TEX = "textures/particle/aot_atlas"
AW, AH = 256, 256


# ---------------------------------------------------------------------------
#  この作品用のスプライト
# ---------------------------------------------------------------------------
def sp_cloud(w, h, seed=7, lumps=11):
    """蒸気・ガスの柔らかい塊。縁がぼけ、上側が明るい。"""
    rng = np.random.RandomState(seed)
    x, y = field(w, h)
    a = np.zeros_like(x)
    for _ in range(lumps):
        cx, cy, rr = rng.uniform(-0.34, 0.34), rng.uniform(-0.30, 0.34), rng.uniform(0.28, 0.48)
        a += np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (rr * rr) * 2.2)
    a = 1 - np.exp(-a * 1.4)                       # 重なりを柔らかく飽和させる
    a = a * np.clip(1.05 - np.sqrt(x * x + y * y), 0, 1) ** 0.8
    shade_ = 0.72 + 0.28 * np.clip(-y * 0.6 + 0.5, 0, 1)
    return rgba_from(np.clip(a * 1.25, 0, 1) * 0.85, white=shade_)


def sp_wire(w, h):
    """ワイヤー: 縦に通った細い線（lookat_direction で縦が線の向きになる）。"""
    x, _y = field(w, h)
    a = np.clip(1 - np.abs(x) * 2.2, 0, 1) ** 0.6
    return rgba_from(a, white=np.clip(0.55 + 0.45 * (1 - np.abs(x) * 3), 0.5, 1))


def sp_drop(w, h):
    x, y = field(w, h)
    r = np.sqrt(x * x + (y * 0.8 + 0.1) ** 2)
    return rgba_from(np.clip((0.7 - r) * 5, 0, 1), white=np.clip(1.1 - r, 0.6, 1))


LAYOUT = {}
SPRITES = []


def place(name, x, y, w, h, fn, *args):
    LAYOUT[name] = (x, y, w, h)
    SPRITES.append((name, x, y, w, h, fn, args))


place("glow", 0, 0, 64, 64, HP.sp_glow)
place("spark", 64, 0, 64, 64, HP.sp_spark)
place("ring", 128, 0, 64, 64, HP.sp_ring)
place("ring_thick", 192, 0, 64, 64, HP.sp_ring_thick)
place("impact", 0, 64, 64, 64, HP.sp_impact)
place("slash", 64, 64, 64, 64, HP.sp_slash, 0.36, 200)
place("smoke", 128, 64, 64, 64, HP.sp_smoke)
place("drop", 192, 64, 32, 32, sp_drop)
place("dot", 224, 64, 32, 32, HP.sp_dot)
place("cloud", 0, 128, 64, 64, sp_cloud, 7)
place("cloud2", 64, 128, 64, 64, sp_cloud, 19, 8)
place("flare", 128, 128, 128, 32, HP.sp_flare)
place("wire", 128, 160, 16, 64, sp_wire)
place("cloud3", 0, 192, 64, 64, sp_cloud, 31, 14)


def build_atlas():
    atlas = np.zeros((AH, AW, 4), np.float32)
    for name, x, y, w, h, fn, args in SPRITES:
        atlas[y:y + h, x:x + w] = fn(w, h, *args)
    img = Image.fromarray((np.clip(atlas, 0, 1) * 255).astype(np.uint8), "RGBA")
    out = os.path.join(RP, "textures", "particle", "aot_atlas.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, optimize=True)
    return img


def uv(name):
    x, y, w, h = LAYOUT[name]
    return {"texture_width": AW, "texture_height": AH, "uv": [x, y], "uv_size": [w, h]}


def bb(size, sprite, mode="lookat_xyz"):
    return {"minecraft:particle_appearance_billboard": {"size": size, "facing_camera_mode": mode,
                                                        "uv": uv(sprite)}}


def tint(alpha, whiten=None, default=(1.0, 1.0, 1.0)):
    col = [f"v.cr ?? {default[0]}", f"v.cg ?? {default[1]}", f"v.cb ?? {default[2]}"]
    if whiten:
        col = [f"math.lerp({c}, 1.0, math.clamp(1.0 - {AGE} * {whiten}, 0.0, 1.0))" for c in col]
    return {"minecraft:particle_appearance_tinting": {"color": col + [alpha]}}


def effect(ident, material, comps):
    return {"format_version": "1.10.0", "particle_effect": {
        "description": {"identifier": f"{NS}:{ident}",
                        "basic_render_parameters": {"material": material, "texture": TEX}},
        "components": comps}}


def lit():
    return {"minecraft:particle_appearance_lighting": {}}


def particles():
    S = "(v.size ?? 1.0)"
    E = {}
    # ---- ワイヤー: 1 本の線分を 1 粒で描く（中点に置き、向きを速度で与える） --------
    E["wire"] = effect("wire", "particles_blend", merge(
        instant(1), P_point(["v.vx ?? 0", "v.vy ?? 1", "v.vz ?? 0"]), speed("0.05"),
        motion(), life("v.life ?? 0.1"),
        bb([f"{S} * 0.035", "(v.len ?? 1.0) * 0.5"], "wire", "lookat_direction"),
        tint("1.0", default=(0.16, 0.16, 0.17))))
    # ---- 蒸気（巨人の再生・討伐の蒸発） ---------------------------------------
    for ident, sprite in (("steam", "cloud"), ("steam2", "cloud3")):
        E[ident] = effect(ident, "particles_blend", merge(
            instant("v.count ?? 4"), P_sphere("v.spread ?? 0.6"),
            speed("(v.speed ?? 0.6) * v.particle_random_1"), motion((0, "v.rise ?? 1.4", 0), 1.4),
            life("(v.life ?? 2.4) * (0.6 + v.particle_random_2 * 0.6)"),
            bb([f"{S} * (0.6 + {AGE} * 1.6)"] * 2, sprite),
            spin("v.particle_random_3 * 360", "(v.particle_random_4 - 0.5) * 40"),
            tint(f"0.85 * math.clamp(math.min({AGE} * 6.0, (1.0 - {AGE}) * 1.6), 0.0, 1.0)",
                 default=(0.94, 0.94, 0.95)), lit()))
    # ---- ガス（立体機動装置の噴射）: 噴いた向きへ飛んですぐ散る ---------------------
    E["gas"] = effect("gas", "particles_blend", merge(
        instant("v.count ?? 3"), P_sphere("v.spread ?? 0.12", ["v.vx ?? 0", "v.vy ?? -1", "v.vz ?? 0"]),
        speed("(v.speed ?? 4.0) * (0.6 + v.particle_random_1 * 0.6)"), motion((0, 0.4, 0), 4.0),
        life("(v.life ?? 0.55) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * (0.25 + {AGE} * 0.9)"] * 2, "cloud2"), spin("v.particle_random_3 * 360", 60),
        tint(f"0.7 * {FADE}", default=(0.96, 0.97, 0.98)), lit()))
    # ---- 火花 / 斬撃 / 閃光 ---------------------------------------------------
    E["spark"] = effect("spark", "particles_add", merge(
        instant("v.count ?? 8"), P_sphere("0.05"),
        speed("(v.speed ?? 6.0) * (0.5 + v.particle_random_1)"), motion((0, -12, 0), 3.0),
        life("(v.life ?? 0.32) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.06", f"{S} * 0.36 * (1.0 - {AGE})"], "spark", "lookat_direction"),
        tint(FADE, whiten=5, default=(1.0, 0.85, 0.5))))
    E["slash"] = effect("slash", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.2"),
        bb([f"{S} * 2.0 * (0.85 + {AGE} * 0.35)"] * 2, "slash"), spin(),
        tint(f"math.clamp((1.0 - {AGE}) * 1.8, 0.0, 1.0)", whiten=3, default=(0.75, 0.9, 1.0))))
    E["flash"] = effect("flash", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.16"),
        bb([f"{S} * (0.6 + {AGE} * 1.6)"] * 2, "impact"), spin("v.particle_random_1 * 360"),
        tint(FADE, whiten=2.5, default=(1.0, 0.8, 0.45))))
    E["glow"] = effect("glow", "particles_add", merge(
        instant(), P_point(), speed(), motion(drag=2.5), life("v.life ?? 0.3"),
        bb([f"{S} * 0.5 * (1.0 - {AGE} * 0.5)"] * 2, "glow"), tint(FADE, whiten=4)))
    E["ring"] = effect("ring", "particles_add", merge(
        instant(), P_point(), life("v.life ?? 0.4"),
        bb([f"{S} * 2.0 * math.pow({AGE}, 0.5)"] * 2, "ring"), tint(FADE, whiten=3)))
    E["ring_flat"] = effect("ring_flat", "particles_blend", merge(
        instant(), P_point(), life("v.life ?? 0.6"),
        bb([f"{S} * 2.0 * math.pow({AGE}, 0.45)"] * 2, "ring_thick", "emitter_transform_xz"),
        tint(f"0.8 * {FADE}", default=(0.62, 0.56, 0.48))))
    E["speedline"] = effect("speedline", "particles_add", merge(
        instant("v.count ?? 4"), P_sphere("v.spread ?? 0.8", ["v.vx ?? 0", "v.vy ?? 0", "v.vz ?? 1"]),
        speed("(v.speed ?? 14.0) * (0.7 + v.particle_random_1 * 0.6)"), motion(drag=3.0),
        life("(v.life ?? 0.22) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.04", f"{S} * 0.9"], "flare", "lookat_direction"),
        tint(f"0.6 * {FADE}")))
    # ---- 血（巨人の血は赤く、すぐ蒸気になる） ---------------------------------
    E["blood"] = effect("blood", "particles_blend", merge(
        instant("v.count ?? 10"), P_sphere("v.spread ?? 0.3"),
        speed("(v.speed ?? 4.0) * (0.4 + v.particle_random_1 * 0.8)"), motion((0, -14, 0), 0.8),
        life("(v.life ?? 0.8) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.12"] * 2, "drop"),
        tint(FADE, default=(0.62, 0.05, 0.06)), lit()))
    E["blood_mist"] = effect("blood_mist", "particles_blend", merge(
        instant("v.count ?? 4"), P_sphere("v.spread ?? 0.4"),
        speed("(v.speed ?? 1.0) * v.particle_random_1"), motion((0, 1.2, 0), 1.6),
        life("(v.life ?? 1.6) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * (0.4 + {AGE} * 1.2)"] * 2, "cloud"), spin("v.particle_random_3 * 360", 20),
        {"minecraft:particle_appearance_tinting": {"color": [
            f"math.lerp(0.65, 0.95, math.clamp({AGE} * 1.6, 0, 1))",
            f"math.lerp(0.06, 0.94, math.clamp({AGE} * 1.6, 0, 1))",
            f"math.lerp(0.07, 0.95, math.clamp({AGE} * 1.6, 0, 1))",
            f"0.8 * {FADE_IN_OUT}"]}}, lit()))
    # ---- 煙（信煙弾・爆発のあと） ---------------------------------------------
    E["smoke"] = effect("smoke", "particles_blend", merge(
        instant("v.count ?? 3"), P_sphere("v.spread ?? 0.5"),
        speed("(v.speed ?? 0.4) * v.particle_random_1"), motion((0, "v.rise ?? 0.5", 0), 0.6),
        life("(v.life ?? 6.0) * (0.7 + v.particle_random_2 * 0.5)"),
        bb([f"{S} * (0.7 + {AGE} * 1.8)"] * 2, "cloud3"),
        spin("v.particle_random_3 * 360", "(v.particle_random_4 - 0.5) * 30"),
        tint(f"0.92 * math.clamp(math.min({AGE} * 8.0, (1.0 - {AGE}) * 1.4), 0.0, 1.0)",
             default=(0.3, 0.3, 0.32)), lit()))
    E["dust"] = effect("dust", "particles_blend", merge(
        instant("v.count ?? 12"), P_disc("v.spread ?? 0.6"),
        speed("(v.speed ?? 5.0) * (0.5 + v.particle_random_1 * 0.5)"), motion((0, 0.4, 0), 3.0),
        life("(v.life ?? 1.0) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * (0.4 + {AGE} * 0.8)"] * 2, "smoke"), spin("v.particle_random_3 * 360", 30),
        tint(f"0.7 * {FADE}", default=(0.6, 0.54, 0.46)), lit()))
    E["debris"] = effect("debris", "particles_blend", merge(
        instant("v.count ?? 8"), P_sphere("v.spread ?? 0.3"),
        speed("(v.speed ?? 6.0) * (0.4 + v.particle_random_1 * 0.8)"), motion((0, -18, 0), 0.6),
        life("(v.life ?? 1.0) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * 0.14"] * 2, "dot"), spin("v.particle_random_3 * 360", 200),
        tint(FADE, default=(0.32, 0.28, 0.24)), lit()))
    E["fire"] = effect("fire", "particles_add", merge(
        instant("v.count ?? 10"), P_sphere("v.spread ?? 0.6"),
        speed("(v.speed ?? 3.0) * v.particle_random_1"), motion((0, 2.0, 0), 2.4),
        life("(v.life ?? 0.6) * (0.6 + v.particle_random_2 * 0.6)"),
        bb([f"{S} * (0.7 - {AGE} * 0.4)"] * 2, "glow"),
        {"minecraft:particle_appearance_tinting": {"color": [
            "1.0", f"math.lerp(0.85, 0.25, {AGE})", f"math.lerp(0.4, 0.05, {AGE})", FADE]}}))
    return E


def main():
    atlas = build_atlas()
    os.makedirs(PART_DIR, exist_ok=True)
    for f in os.listdir(PART_DIR):
        if f.endswith(".particle.json"):
            os.remove(os.path.join(PART_DIR, f))
    E = particles()
    for name, doc in E.items():
        write_json(os.path.join(PART_DIR, f"{name}.particle.json"), doc)
    if os.environ.get("AOT_PREVIEW"):
        bg = Image.new("RGBA", atlas.size, (40, 60, 50, 255))
        bg.alpha_composite(atlas)
        os.makedirs(C.SCRATCH, exist_ok=True)
        bg.resize((768, 768), Image.NEAREST).save(os.path.join(C.SCRATCH, "atlas.png"))
    print(f"  particles: {len(E)}  sprites: {len(LAYOUT)}")
    _ = (COL, math)


if __name__ == "__main__":
    main()
