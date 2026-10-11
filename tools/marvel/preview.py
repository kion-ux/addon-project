# -*- coding: utf-8 -*-
"""モデルを実際に見るための簡易レンダラ（マーベル用）。

この環境には Minecraft が無いので、作ったモデルは **これで見て確かめる**。
ジオメトリを読み、ボーン階層を適用し、テクスチャを貼って z バッファで描く。

使い方:
    python3 tools/marvel/preview.py magneto sentinel mystique
    python3 tools/marvel/preview.py --pose tech.repulse magneto
    python3 tools/marvel/preview.py --all
出力は scratchpad/marvel_preview.png（複数キャラを並べた一枚絵）。
"""
from __future__ import annotations

import os
import sys

import _path  # noqa: F401

import contract as K  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import preview as base  # noqa: E402  (kaiju8 と共有する描画エンジン)

OUT_DIR = os.environ.get(
    "MARVEL_PREVIEW_DIR",
    "/tmp/claude-0/-home-user-addon-project/21bdc9fd-14a0-55af-af9f-d1d71bed5842/scratchpad")


def _load_pose(names):
    """マーベルのアニメーションファイルから、定数キーだけを取り出してポーズにする。"""
    import json
    out = {}
    if not names:
        return out
    for fname in ("marvel.loco.animation.json", "marvel.tech.animation.json"):
        path = os.path.join(K.ANIM_DIR, fname)
        if not os.path.exists(path):
            continue
        doc = json.load(open(path, encoding="utf-8"))["animations"]
        for name in names:
            ident = name if name.startswith("animation.") else K.anim(*name.split(".", 1))
            clip = doc.get(ident)
            if not clip:
                continue
            for bone, tracks in clip.get("bones", {}).items():
                entry = out.setdefault(bone, {"rotation": [0, 0, 0],
                                              "position": [0, 0, 0]})
                for key in ("rotation", "position"):
                    v = tracks.get(key)
                    if isinstance(v, dict):
                        # キーフレームなら「一番動いている」キーを選ぶ（見栄えのため）
                        best, score = None, -1
                        for t, frame in v.items():
                            val = frame.get("post", frame) if isinstance(frame, dict) else frame
                            if not isinstance(val, list):
                                continue
                            s = sum(abs(c) for c in val if isinstance(c, (int, float)))
                            if s > score:
                                best, score = val, s
                        v = best
                    if isinstance(v, list) and all(isinstance(c, (int, float)) for c in v):
                        for i in range(3):
                            entry[key][i] += v[i]
    return out


def render_one(key, pose_names=None, size=380, yaw=26.0, pitch=-10.0):
    geo = K.geo_path(key)
    tex = K.tex_path(key)
    if not os.path.exists(geo):
        raise SystemExit(f"ジオメトリが無い: {geo}")
    saved = base.load_pose
    base.load_pose = lambda names: _load_pose(pose_names or [])
    try:
        return base.render(geo, tex, size, yaw, pitch, pose=pose_names or [])
    finally:
        base.load_pose = saved


def sheet(keys, out_path, pose_names=None, views=((26, -10), (-140, -6)),
          size=340):
    from PIL import Image
    tiles = []
    for key in keys:
        for yaw, pitch in views:
            tiles.append(render_one(key, pose_names, size, yaw, pitch))
    cols = min(4, len(tiles)) or 1
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new("RGB", (cols * size, rows * size), (18, 20, 26))
    for i, im in enumerate(tiles):
        out.paste(im, ((i % cols) * size, (i // cols) * size))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.save(out_path)
    print(f"wrote {out_path} ({len(tiles)} tiles: {', '.join(keys)})")
    return out_path


def main() -> None:
    args = sys.argv[1:]
    poses = []
    keys = []
    i = 0
    while i < len(args):
        if args[i] == "--pose":
            poses.append(args[i + 1]); i += 2
        elif args[i] == "--all":
            keys = K.ALL_CHARACTERS; i += 1
        elif args[i] == "--props":
            keys = list(K.PROP_ENTITIES); i += 1
        else:
            keys.append(args[i]); i += 1
    if not keys:
        keys = [K.MAGNETO]
    sheet(keys, os.path.join(OUT_DIR, "marvel_preview.png"), poses)


if __name__ == "__main__":
    main()
