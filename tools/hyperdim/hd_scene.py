# -*- coding: utf-8 -*-
"""プレイヤーと武器を「実機と同じ変換規則」で描くシーンレンダラ。

hd_space の規則（回転の向き・bind のずれ・持ち姿勢・一人称の腕とカメラ）で
プレイヤーの骨格を組み、武器のアタッチャブルを手に付けて描く。
* tp(): 三人称（正射影）。体へのめり込み・握りの位置・向きを確認する
* fp(): 一人称（透視投影）。画面のどこに武器が出るかを確認する
画面は統合版と同じく X を鏡映して描く（右手が画面の右に来る）。
"""
from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image

import hd_common  # noqa: F401
from hd_space import FP_ARM_POS, FP_ARM_ROT, FP_EYE, OFF_L, OFF_R, bone_local, mat4, rot

FACES = {
    "north": lambda a, b: [(a[0], b[1], a[2]), (b[0], b[1], a[2]), (b[0], a[1], a[2]), (a[0], a[1], a[2])],
    "south": lambda a, b: [(b[0], b[1], b[2]), (a[0], b[1], b[2]), (a[0], a[1], b[2]), (b[0], a[1], b[2])],
    "west":  lambda a, b: [(a[0], b[1], b[2]), (a[0], b[1], a[2]), (a[0], a[1], a[2]), (a[0], a[1], b[2])],
    "east":  lambda a, b: [(b[0], b[1], a[2]), (b[0], b[1], b[2]), (b[0], a[1], b[2]), (b[0], a[1], a[2])],
    "up":    lambda a, b: [(a[0], b[1], b[2]), (b[0], b[1], b[2]), (b[0], b[1], a[2]), (a[0], b[1], a[2])],
    "down":  lambda a, b: [(a[0], a[1], a[2]), (b[0], a[1], a[2]), (b[0], a[1], b[2]), (a[0], a[1], b[2])],
}

# プレイヤーの骨格（geometry.humanoid.custom）
SKELETON = [
    ("root", None, (0, 0, 0), None),
    ("waist", "root", (0, 12, 0), None),
    ("body", "waist", (0, 24, 0), ((-4, 12, -2), (8, 12, 4), (60, 150, 160))),
    ("head", "body", (0, 24, 0), ((-4, 24, -4), (8, 8, 8), (214, 168, 132))),
    ("rightArm", "body", (-5, 22, 0), ((-8, 12, -2), (4, 12, 4), (196, 150, 118))),
    ("rightItem", "rightArm", (-6, 15, 1), None),
    ("leftArm", "body", (5, 22, 0), ((4, 12, -2), (4, 12, 4), (196, 150, 118))),
    ("leftItem", "leftArm", (6, 15, 1), None),
    ("rightLeg", "root", (-1.9, 12, 0), ((-3.9, 0, -2), (4, 12, 4), (52, 60, 120))),
    ("leftLeg", "root", (1.9, 12, 0), ((-0.1, 0, -2), (4, 12, 4), (52, 60, 120))),
]


def skeleton_world(pose):
    """pose: bone -> {"rotation": (..), "position": (..)}。各ボーンのワールド行列。"""
    W = {}
    for name, parent, pivot, _ in SKELETON:
        p = pose.get(name, {})
        L = bone_local(pivot, p.get("rotation", (0, 0, 0)), p.get("position", (0, 0, 0)))
        W[name] = (W[parent] if parent else np.eye(4)) @ L
    return W


def player_quads(W, hide=()):
    out = []
    for name, _parent, _pivot, cube in SKELETON:
        if not cube or name in hide:
            continue
        o, s, col = cube
        a = np.array(o, float)
        b = a + np.array(s, float)
        M = W[name]
        for face, fn in FACES.items():
            pts = [(M @ np.array([*q, 1.0]))[:3] for q in fn(a, b)]
            out.append((pts, None, col))
    return out


def load_geo(path):
    g = json.load(open(path, encoding="utf-8"))["minecraft:geometry"][0]
    return g


def weapon_quads(geo, tex, W, anim, first_person=False, hide=(), tag=False):
    """武器のアタッチャブル。anim: bone -> {"rotation","position","scale"}。
    tag=True なら各面にボーン名を 4 つ目の要素として付ける（めり込み検査用）。"""
    bones = {b["name"]: b for b in geo["bones"]}
    order = [b["name"] for b in geo["bones"]]
    world = {}

    def wm(name):
        if name in world:
            return world[name]
        b = bones[name]
        a = anim.get(name, {})
        L = bone_local(b.get("pivot", (0, 0, 0)),
                       np.add(b.get("rotation", (0, 0, 0)), a.get("rotation", (0, 0, 0))),
                       a.get("position", (0, 0, 0)), a.get("scale", (1, 1, 1)))
        if b.get("parent"):
            M = wm(b["parent"]) @ L
        elif b.get("binding") and W is not None:
            left = "leftitem" in b["binding"] and "main_hand" in b["binding"]
            target = W["leftItem" if left else "rightItem"]
            M = target @ mat4(t=OFF_L if left else OFF_R) @ L
        else:
            M = L
        world[name] = M
        return M

    tw, th = tex.size
    out = []
    hidden = set()
    for name in order:
        par = bones[name].get("parent")
        if name in hide or (par and par in hidden):
            hidden.add(name)
    for name in order:
        if name in hidden:
            continue
        M = wm(name)
        for ci, c in enumerate(bones[name].get("cubes", [])):
            o = np.array(c["origin"], float)
            s = np.array(c["size"], float)
            inf = c.get("inflate", 0.0)
            a, b2 = o - inf, o + s + inf
            CM = M
            if c.get("rotation"):
                cp = np.array(c.get("pivot", o + s / 2), float)
                CM = M @ mat4(t=cp) @ mat4(rot(*c["rotation"])) @ mat4(t=-cp)
            for face, fn in FACES.items():
                f = c["uv"].get(face)
                if not f:
                    continue
                u0, v0 = f["uv"]
                du, dv = f["uv_size"]
                pts = [(CM @ np.array([*q, 1.0]))[:3] for q in fn(a, b2)]
                uvs = [(u0, v0), (u0 + du, v0), (u0 + du, v0 + dv), (u0, v0 + dv)]
                out.append((pts, uvs, None, f"{name}#{ci}") if tag else (pts, uvs, None))
    return out


def raster(quads, tex, size, project, bg=(24, 26, 34)):
    W_, H_ = size
    img = np.zeros((H_, W_, 3), np.float32)
    img[:, :] = bg
    z = np.full((H_, W_), 1e9, np.float32)
    tpx = np.asarray(tex.convert("RGBA"), np.float32) if tex is not None else None
    light = np.array([0.3, 0.8, -0.5])
    light /= np.linalg.norm(light)
    for pts, uvs, col in quads:
        scr = [project(p) for p in pts]
        if any(s is None for s in scr):
            continue
        e1, e2 = np.subtract(pts[1], pts[0]), np.subtract(pts[3], pts[0])
        nrm = np.cross(e1, e2)
        nl = np.linalg.norm(nrm) or 1
        lit = 0.45 + 0.55 * abs(float(np.dot(nrm / nl, light)))
        for tri in ((0, 1, 2), (0, 2, 3)):
            p0, p1, p2 = (scr[i] for i in tri)
            minx = max(0, int(min(p0[0], p1[0], p2[0])))
            maxx = min(W_ - 1, int(max(p0[0], p1[0], p2[0])) + 1)
            miny = max(0, int(min(p0[1], p1[1], p2[1])))
            maxy = min(H_ - 1, int(max(p0[1], p1[1], p2[1])) + 1)
            if minx > maxx or miny > maxy:
                continue
            d = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
            if abs(d) < 1e-9:
                continue
            ys, xs = np.mgrid[miny:maxy + 1, minx:maxx + 1].astype(np.float32)
            xs += 0.5
            ys += 0.5
            w0 = ((p1[1] - p2[1]) * (xs - p2[0]) + (p2[0] - p1[0]) * (ys - p2[1])) / d
            w1 = ((p2[1] - p0[1]) * (xs - p2[0]) + (p0[0] - p2[0]) * (ys - p2[1])) / d
            w2 = 1 - w0 - w1
            m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
            if not m.any():
                continue
            zz = w0 * p0[2] + w1 * p1[2] + w2 * p2[2]
            sub = z[miny:maxy + 1, minx:maxx + 1]
            m &= zz < sub
            if not m.any():
                continue
            reg = img[miny:maxy + 1, minx:maxx + 1]
            if uvs is not None and tpx is not None:
                t0, t1, t2 = (uvs[i] for i in tri)
                u = w0 * t0[0] + w1 * t1[0] + w2 * t2[0]
                v = w0 * t0[1] + w1 * t1[1] + w2 * t2[1]
                ui = np.clip(u.astype(int), 0, tpx.shape[1] - 1)
                vi = np.clip(v.astype(int), 0, tpx.shape[0] - 1)
                tx = tpx[vi, ui]
                emit = 1 - tx[..., 3:4] / 255
                c = tx[..., :3] * (lit * (1 - emit) + 1.1 * emit)
                reg[m] = np.clip(c[m], 0, 255)
            else:
                reg[m] = np.clip(np.array(col, np.float32) * lit, 0, 255)
            sub[m] = zz[m]
    return Image.fromarray(img.astype(np.uint8))


def ortho(yaw, pitch, centre, scale, size):
    """正射影。yaw=0 で正面（-Z 側）から、yaw=180 で背後から。X は鏡映。"""
    from hd_space import Rx, Ry
    V = Rx(pitch) @ Ry(yaw)
    W_, H_ = size

    def project(p):
        q = V @ (np.array(p, float) - centre)
        # 統合版はモデルの X を鏡映して描く（正面から見ると右腕 (-X) が画面の左）
        return (W_ / 2 + q[0] * scale, H_ / 2 - q[1] * scale, q[2])
    return project


def tp(geo_path, tex_path, pose, anim, yaw=200, pitch=-12, size=(420, 420), scale=7.0,
       centre=(0, 16, 0), hide=(), show_player=True):
    geo = load_geo(geo_path)
    tex = Image.open(tex_path)
    W = skeleton_world(pose)
    quads = weapon_quads(geo, tex, W, anim, hide=hide)
    pq = player_quads(W) if show_player else []
    proj = ortho(yaw, pitch, np.array(centre, float), scale, size)
    # 2 パス: プレイヤー（色）と武器（テクスチャ）を同じ z バッファで
    return raster_combined(pq, quads, tex, size, proj)


def raster_combined(player_q, weapon_q, tex, size, proj):
    allq = [(p, None, c) for p, _u, c in player_q] + weapon_q
    return raster(allq, tex, size, proj)


def fp(geo_path, tex_path, anim, size=(480, 270), fov=70.0, hide=()):
    """一人称。腕は (95,-45,115)/(13.5,-10,12)、目 (0,26,0) から +Z を見る。"""
    geo = load_geo(geo_path)
    tex = Image.open(tex_path)
    pose = {"rightArm": {"rotation": FP_ARM_ROT, "position": FP_ARM_POS}}
    W = skeleton_world(pose)
    quads = weapon_quads(geo, tex, W, anim, first_person=True, hide=hide)
    W_, H_ = size
    f = (H_ / 2) / np.tan(np.radians(fov / 2))

    def project(p):
        q = np.array(p, float) - FP_EYE
        if q[2] < 0.5:
            return None
        return (W_ / 2 + q[0] / q[2] * f, H_ / 2 - q[1] / q[2] * f, q[2])
    return raster(quads, tex, size, project)


def sheet(images, path, cols=4, bg=(14, 15, 20)):
    w = max(i.size[0] for i in images)
    h = max(i.size[1] for i in images)
    rows = (len(images) + cols - 1) // cols
    out = Image.new("RGB", (w * cols, h * rows), bg)
    for k, im in enumerate(images):
        out.paste(im, ((k % cols) * w, (k // cols) * h))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)
    return path
