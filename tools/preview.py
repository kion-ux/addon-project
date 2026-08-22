# -*- coding: utf-8 -*-
"""Tiny software renderer for .geo.json + its texture.

There is no Minecraft in this environment, so this is how the models get looked
at: parse the geometry, apply the bone hierarchy, rasterise the textured boxes
with a z-buffer, and write a PNG contact sheet.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "packs", "kaiju8_RP")

FACE_CORNERS = {
    "north": lambda a, b: [(a[0], b[1], a[2]), (b[0], b[1], a[2]),
                           (b[0], a[1], a[2]), (a[0], a[1], a[2])],
    "south": lambda a, b: [(b[0], b[1], b[2]), (a[0], b[1], b[2]),
                           (a[0], a[1], b[2]), (b[0], a[1], b[2])],
    "west":  lambda a, b: [(a[0], b[1], b[2]), (a[0], b[1], a[2]),
                           (a[0], a[1], a[2]), (a[0], a[1], b[2])],
    "east":  lambda a, b: [(b[0], b[1], a[2]), (b[0], b[1], b[2]),
                           (b[0], a[1], b[2]), (b[0], a[1], a[2])],
    "up":    lambda a, b: [(a[0], b[1], b[2]), (b[0], b[1], b[2]),
                           (b[0], b[1], a[2]), (a[0], b[1], a[2])],
    "down":  lambda a, b: [(a[0], a[1], a[2]), (b[0], a[1], a[2]),
                           (b[0], a[1], b[2]), (a[0], a[1], b[2])],
}
FACE_NORMAL = {"north": (0, 0, -1), "south": (0, 0, 1), "west": (-1, 0, 0),
               "east": (1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}


def rot_matrix(rx, ry, rz):
    # Bedrock stores rotations with X and Y negated relative to a right-handed
    # Y-up frame (this is what Blockbench's bedrock codec does on import), and
    # composes them XYZ.
    rx, ry, rz = math.radians(-rx), math.radians(-ry), math.radians(rz)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mx @ my @ mz


def load_pose(names):
    """Constant (non-molang) rotations/positions from our animation clips."""
    path = os.path.join(RP, "animations", "kaiju8.animation.json")
    if not os.path.exists(path) or not names:
        return {}
    doc = json.load(open(path, encoding="utf-8"))["animations"]
    out = {}
    for name in names:
        clip = doc.get(name)
        if not clip:
            continue
        for bone, tracks in clip.get("bones", {}).items():
            entry = out.setdefault(bone, {"rotation": [0, 0, 0], "position": [0, 0, 0]})
            for key in ("rotation", "position"):
                v = tracks.get(key)
                if isinstance(v, dict):          # keyframed - take the first frame
                    v = v[sorted(v, key=float)[0]]
                if isinstance(v, list) and all(isinstance(c, (int, float)) for c in v):
                    for i in range(3):
                        entry[key][i] += v[i]
    return out


class Geo:
    def __init__(self, path, pose=None, hide=()):
        self.pose = pose or {}
        self.hide = set(hide)
        doc = json.load(open(path, encoding="utf-8"))
        g = doc["minecraft:geometry"][0]
        self.tw = g["description"]["texture_width"]
        self.th = g["description"]["texture_height"]
        self.bones = {b["name"]: b for b in g["bones"]}
        self.order = [b["name"] for b in g["bones"]]

    def world(self, name, cache):
        if name in cache:
            return cache[name]
        bone = self.bones[name]
        pivot = np.array(bone.get("pivot", [0, 0, 0]), dtype=float)
        rot = list(bone.get("rotation") or [0, 0, 0])
        shift = np.zeros(3)
        posed = self.pose.get(name)
        if posed:
            rot = [rot[i] + posed["rotation"][i] for i in range(3)]
            shift = np.array(posed["position"], dtype=float) * np.array([1, 1, -1])
        m = rot_matrix(*rot) if any(rot) else np.eye(3)
        parent = bone.get("parent")
        if parent and parent in self.bones:
            pm, pt = self.world(parent, cache)
        else:
            pm, pt = np.eye(3), np.zeros(3)
        # local: p -> m @ (p - pivot) + pivot ; then parent transform
        out_m = pm @ m
        out_t = pm @ (pivot - m @ pivot + shift) + pt
        cache[name] = (out_m, out_t)
        return cache[name]

    def quads(self):
        cache = {}
        out = []
        hidden = set()
        for name in self.order:
            parent = self.bones[name].get("parent")
            if name in self.hide or (parent and parent in hidden):
                hidden.add(name)
        for name in self.order:
            if name in hidden:
                continue
            m, t = self.world(name, cache)
            for cube in self.bones[name].get("cubes", []):
                origin = np.array(cube["origin"], dtype=float)
                size = np.array(cube["size"], dtype=float)
                inf = cube.get("inflate", 0.0)
                a = origin - inf
                b = origin + size + inf
                cm, ct = m, t
                if cube.get("rotation"):
                    cp = np.array(cube.get("pivot", (origin + size / 2)), dtype=float)
                    lm = rot_matrix(*cube["rotation"])
                    cm = m @ lm
                    ct = m @ (cp - lm @ cp) + t
                uv = cube["uv"]
                for face, fn in FACE_CORNERS.items():
                    if isinstance(uv, dict):
                        if face not in uv:
                            continue
                        u0, v0 = uv[face]["uv"]
                        du, dv = uv[face]["uv_size"]
                    else:
                        continue
                    pts = [cm @ np.array(p, dtype=float) + ct for p in fn(a, b)]
                    n = cm @ np.array(FACE_NORMAL[face], dtype=float)
                    uvs = [(u0, v0), (u0 + du, v0), (u0 + du, v0 + dv), (u0, v0 + dv)]
                    out.append((pts, uvs, n))
        return out


def render(geo_path, tex_path, size=360, yaw=28.0, pitch=-12.0, margin=0.10,
           bg=(28, 30, 38), pose=None, hide=()):
    geo = Geo(geo_path, load_pose(pose), hide)
    tex = Image.open(tex_path).convert("RGBA")
    tw, th = tex.size
    tpx = np.array(tex, dtype=np.float32)

    quads = geo.quads()
    if not quads:
        return Image.new("RGB", (size, size), bg)
    view = rot_matrix(pitch, yaw, 0)

    verts = np.array([p for q in quads for p in q[0]])
    vv = verts @ view.T
    lo, hi = vv.min(axis=0), vv.max(axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1.0
    scale = size * (1 - 2 * margin) / span
    cx = (hi[0] + lo[0]) / 2
    cy = (hi[1] + lo[1]) / 2

    img = np.zeros((size, size, 3), dtype=np.float32)
    img[:, :] = np.array(bg, dtype=np.float32)
    # カメラは -Z 側から +Z を向いているので、z が小さいほど手前。
    zbuf = np.full((size, size), 1e9, dtype=np.float32)
    light = np.array([0.45, 0.82, -0.35])
    light /= np.linalg.norm(light)

    def project(p):
        q = view @ p
        return ((q[0] - cx) * scale + size / 2,
                size / 2 - (q[1] - cy) * scale,
                q[2])

    for pts, uvs, normal in quads:
        n = view @ normal
        if n[2] > 0.05:          # back-face cull (camera looks down -Z)
            continue
        shade = 0.35 + 0.65 * max(0.0, float(np.dot(n, light)))
        scr = [project(p) for p in pts]
        for tri in ((0, 1, 2), (0, 2, 3)):
            p0, p1, p2 = (scr[i] for i in tri)
            t0, t1, t2 = (uvs[i] for i in tri)
            minx = max(0, int(min(p0[0], p1[0], p2[0])))
            maxx = min(size - 1, int(max(p0[0], p1[0], p2[0])) + 1)
            miny = max(0, int(min(p0[1], p1[1], p2[1])))
            maxy = min(size - 1, int(max(p0[1], p1[1], p2[1])) + 1)
            if minx > maxx or miny > maxy:
                continue
            d = ((p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1]))
            if abs(d) < 1e-9:
                continue
            ys, xs = np.mgrid[miny:maxy + 1, minx:maxx + 1]
            xs = xs + 0.5
            ys = ys + 0.5
            w0 = ((p1[1] - p2[1]) * (xs - p2[0]) + (p2[0] - p1[0]) * (ys - p2[1])) / d
            w1 = ((p2[1] - p0[1]) * (xs - p2[0]) + (p0[0] - p2[0]) * (ys - p2[1])) / d
            w2 = 1.0 - w0 - w1
            mask = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
            if not mask.any():
                continue
            z = w0 * p0[2] + w1 * p1[2] + w2 * p2[2]
            sub = zbuf[miny:maxy + 1, minx:maxx + 1]
            mask &= z < sub
            if not mask.any():
                continue
            u = (w0 * t0[0] + w1 * t1[0] + w2 * t2[0])
            v = (w0 * t0[1] + w1 * t1[1] + w2 * t2[1])
            ui = np.clip(u.astype(int), 0, tw - 1)
            vi = np.clip(v.astype(int), 0, th - 1)
            texel = tpx[vi, ui]
            mask &= texel[..., 3] > 8
            if not mask.any():
                continue
            colour = texel[..., :3] * shade
            region = img[miny:maxy + 1, minx:maxx + 1]
            region[mask] = colour[mask]
            sub[mask] = z[mask]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def sheet(entries, out_path, size=300, views=((24, -10),), poses=None):
    tiles = []
    for entry in entries:
        label, geo, tex = entry[0], entry[1], entry[2]
        pose = entry[3] if len(entry) > 3 else (poses or {}).get(label)
        for yaw, pitch in views:
            im = render(geo, tex, size, yaw, pitch, pose=pose)
            tiles.append((label, im))
    cols = min(5, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new("RGB", (cols * size, rows * size), (18, 20, 26))
    for i, (label, im) in enumerate(tiles):
        out.paste(im, ((i % cols) * size, (i // cols) * size))
    out.save(out_path)
    print(f"wrote {out_path} ({len(tiles)} tiles)")


if __name__ == "__main__":
    geo_dir = os.path.join(RP, "models", "entity")
    tex_dir = os.path.join(RP, "textures", "entity", "kaiju8")
    names = sys.argv[1:] or ["kafka", "mina", "kikoru", "hoshina", "soldier"]
    entries = []
    for n in names:
        g = os.path.join(geo_dir, f"{n}.geo.json")
        t = os.path.join(tex_dir, f"{n}.png")
        if not os.path.exists(g):
            g = os.path.join(geo_dir, f"weapon_{n}.geo.json")
            t = os.path.join(tex_dir, "weapons", f"{n}.png")
        entries.append((n, g, t))
    sheet(entries, "/tmp/claude-0/-home-user-addon-project/13952f93-4d98-5dcc-8872-3d0adfba1fd3/scratchpad/preview.png")
