# -*- coding: utf-8 -*-
"""武器モデルのソフトレンダラ（Minecraft 無しで形と塗りを確認する / アイコンを焼く）。

tools/preview.py のジオメトリ解釈（ボーン階層・キューブ回転の規約）をそのまま使い、
* 発光 texel（アルファが低い）を陰影なしで明るく描く
* 背景透過・スーパーサンプリングでアイテムアイコンを書き出せる
ようにしたもの。
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

import hd_common  # noqa: F401  (sys.path 設定)
from preview import Geo, rot_matrix  # noqa: E402


def _pose_from_anim(anim_path, names, t=0.0):
    if not names or not os.path.exists(anim_path):
        return {}
    doc = json.load(open(anim_path, encoding="utf-8"))["animations"]
    out = {}
    for name in names:
        clip = doc.get(name, {})
        for bone, tracks in clip.get("bones", {}).items():
            e = out.setdefault(bone, {"rotation": [0, 0, 0], "position": [0, 0, 0]})
            for key in ("rotation", "position"):
                v = tracks.get(key)
                if isinstance(v, dict):
                    stamps = sorted(v, key=float)
                    v = v[min(stamps, key=lambda k: abs(float(k) - t))]
                    if isinstance(v, dict):
                        v = v.get("post", v.get("pre"))
                if isinstance(v, list) and all(isinstance(c, (int, float)) for c in v):
                    for i in range(3):
                        e[key][i] += v[i]
    return out


def render(geo_path, tex_path, size=320, yaw=30.0, pitch=-14.0, roll=0.0,
           margin=0.08, bg=(26, 28, 36, 255), pose=None, hide=(), ss=1,
           outline=None):
    geo = Geo(geo_path, pose or {}, hide)
    tex = np.array(Image.open(tex_path).convert("RGBA"), dtype=np.float32)
    th, tw = tex.shape[:2]
    quads = geo.quads()
    S = size * ss
    view = rot_matrix(pitch, yaw, roll)
    verts = np.array([p for q in quads for p in q[0]])
    vv = verts @ view.T
    lo, hi = vv.min(axis=0), vv.max(axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1.0
    scale = S * (1 - 2 * margin) / span
    cx, cy = (hi[0] + lo[0]) / 2, (hi[1] + lo[1]) / 2

    img = np.zeros((S, S, 4), dtype=np.float32)
    img[:, :] = np.array(bg, dtype=np.float32)
    zbuf = np.full((S, S), 1e9, dtype=np.float32)
    light = np.array([0.40, 0.80, -0.45])
    light /= np.linalg.norm(light)

    for pts, uvs, normal in quads:
        n = view @ normal
        if n[2] > 0.05:
            continue
        lit = 0.42 + 0.58 * max(0.0, float(np.dot(n, light)))
        scr = []
        for p in pts:
            q = view @ p
            scr.append(((q[0] - cx) * scale + S / 2, S / 2 - (q[1] - cy) * scale, q[2]))
        for tri in ((0, 1, 2), (0, 2, 3)):
            p0, p1, p2 = (scr[i] for i in tri)
            t0, t1, t2 = (uvs[i] for i in tri)
            minx = max(0, int(min(p0[0], p1[0], p2[0])))
            maxx = min(S - 1, int(max(p0[0], p1[0], p2[0])) + 1)
            miny = max(0, int(min(p0[1], p1[1], p2[1])))
            maxy = min(S - 1, int(max(p0[1], p1[1], p2[1])) + 1)
            if minx > maxx or miny > maxy:
                continue
            d = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
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
            u = w0 * t0[0] + w1 * t1[0] + w2 * t2[0]
            v = w0 * t0[1] + w1 * t1[1] + w2 * t2[1]
            ui = np.clip(u.astype(int), 0, tw - 1)
            vi = np.clip(v.astype(int), 0, th - 1)
            texel = tex[vi, ui]
            # entity_emissive_alpha: アルファが低いほど自己発光
            emit = 1.0 - texel[..., 3:4] / 255.0
            k = lit * (1 - emit) + 1.12 * emit
            col = np.clip(texel[..., :3] * k, 0, 255)
            region = img[miny:maxy + 1, minx:maxx + 1]
            region[mask, :3] = col[mask]
            region[mask, 3] = 255
            sub[mask] = z[mask]

    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA")
    if ss > 1:
        out = out.resize((size, size), Image.LANCZOS)
    if outline is not None:
        a = out.split()[3]
        grown = a.filter(ImageFilter.MaxFilter(3))
        ring = Image.new("RGBA", out.size, tuple(outline) + (255,))
        ring.putalpha(grown)
        ring.alpha_composite(out)
        out = ring
    return out


def sheet(tiles, path, cols=4):
    if not tiles:
        return
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new("RGBA", (cols * w, rows * h), (14, 15, 20, 255))
    for i, t in enumerate(tiles):
        canvas.alpha_composite(t, ((i % cols) * w, (i // cols) * h))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    canvas.convert("RGB").save(path)
    print(f"wrote {path}")


if __name__ == "__main__":
    from hd_common import RP
    names = sys.argv[1:]
    tiles = []
    for n in names:
        g = os.path.join(RP, "models", "entity", f"hd_{n}.geo.json")
        t = os.path.join(RP, "textures", "entity", "hd", f"{n}.png")
        for yaw, pitch in ((90, -8), (30, -18), (150, -10), (0, -80)):
            tiles.append(render(g, t, 360, yaw, pitch, ss=2))
    sheet(tiles, os.path.join(hd_common.SCRATCH, "weapons.png"))
