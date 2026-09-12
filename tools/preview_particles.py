"""Renders every generated particle effect as a labelled contact sheet.

Minecraft cannot be run here, so a particle's colour, sprite and aspect ratio
are otherwise invisible until someone loads the pack.  This reads the emitted
.particle.json files back, pulls out the uv cell, the tint expression and the
billboard size, and draws each effect the way a single particle of it would
look at birth — so a mistyped uv, a colour that vanishes against the world, or
a sprite that is the wrong shape for the effect shows up here.

  python3 tools/preview_particles.py                    # 怪獣8号のすべて
  python3 tools/preview_particles.py slash axe          # id の部分一致で絞る
  python3 tools/preview_particles.py --pack gla         # ワンピース側
"""
from __future__ import annotations

import json
import os
import re
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#  2本のアドオンのどちらを見るか。パーティクルの置き場が少し違う。
PACKS = {
    "kaiju8": ("kaiju8_RP", "textures/particle/kaiju8_particles.png", "kaiju8:"),
    "gla": ("gla_RP", "textures/particle/gla/gla_particles.png", "gla:"),
}
PACK = "kaiju8"
RP = os.path.join(ROOT, "packs", "kaiju8_RP")
PART_DIR = os.path.join(RP, "particles")
ATLAS = os.path.join(RP, "textures", "particle", "kaiju8_particles.png")
OUT = os.environ.get("ADDON_PREVIEW_DIR",
                    os.environ.get("KAIJU8_PREVIEW_DIR", "/tmp"))
PREFIX = "kaiju8:"

TILE = 132
COLS = 8
BG = (26, 28, 34)
FRAME = (58, 62, 72)


def leading_number(expr, default=1.0):
    """The tint channels are molang; the constant at the front is the value at
    birth, which is what a fresh particle actually shows."""
    if isinstance(expr, (int, float)):
        return float(expr)
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(expr))
    return float(m.group(1)) if m else default


def read_effect(path):
    doc = json.load(open(path, encoding="utf-8"))["particle_effect"]
    comps = doc["components"]
    bill = comps["minecraft:particle_appearance_billboard"]
    uv = bill["uv"]
    tint = comps.get("minecraft:particle_appearance_tinting", {}).get(
        "color", ["1", "1", "1", "1"])
    size = bill.get("size", [0.25, 0.25])
    rate = comps.get("minecraft:emitter_rate_instant", {}).get("num_particles")
    steady = comps.get("minecraft:emitter_rate_steady", {}).get("spawn_rate")
    shape = next((k.split("_")[-1] for k in comps
                  if k.startswith("minecraft:emitter_shape_")), "?")
    return {
        "id": doc["description"]["identifier"],
        "uv": uv["uv"], "uv_size": uv["uv_size"],
        "rgba": [leading_number(c, 1.0) for c in tint],
        "size": [leading_number(v, 0.25) for v in size],
        "count": rate if rate is not None else f"{steady}/s",
        "life": comps.get("minecraft:particle_lifetime_expression",
                          {}).get("max_lifetime", "?"),
        "shape": shape,
        "facing": bill.get("facing_camera_mode", ""),
    }


def draw(effects, out_path):
    atlas = Image.open(ATLAS).convert("RGBA")
    rows = (len(effects) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TILE, rows * TILE), BG)
    pen = ImageDraw.Draw(sheet)

    for i, e in enumerate(effects):
        ox, oy = (i % COLS) * TILE, (i // COLS) * TILE
        pen.rectangle([ox, oy, ox + TILE - 1, oy + TILE - 1], outline=FRAME)

        u, v = e["uv"]
        uw, uh = e["uv_size"]
        sprite = atlas.crop((u, v, u + uw, v + uh))

        # a particle is drawn size[0] wide by size[1] tall in world units;
        # normalise so the larger side fills most of the tile
        w, h = max(0.02, e["size"][0]), max(0.02, e["size"][1])
        box = TILE - 42
        scale = box / max(w, h)
        pw, ph = max(3, round(w * scale)), max(3, round(h * scale))
        sprite = sprite.resize((pw, ph), Image.NEAREST)

        r, g, b, a = e["rgba"]
        tint = Image.new("RGBA", sprite.size,
                         (round(r * 255), round(g * 255), round(b * 255), 255))
        tint.putalpha(sprite.split()[3].point(
            lambda px: int(px * max(0.05, min(1.0, a)))))
        sheet.paste(tint, (ox + (TILE - pw) // 2, oy + 6 + (box - ph) // 2), tint)

        name = e["id"].replace(PREFIX, "")
        pen.text((ox + 5, oy + TILE - 26), name[:22], fill=(226, 230, 238))
        pen.text((ox + 5, oy + TILE - 14),
                 f'x{e["count"]}  {e["life"]}s  {e["shape"]}',
                 fill=(140, 146, 158))

    sheet.save(out_path)
    print(f"wrote {out_path} ({len(effects)} effects)")


def main():
    global RP, PART_DIR, ATLAS, PREFIX, PACK
    argv = sys.argv[1:]
    if "--pack" in argv:
        i = argv.index("--pack")
        PACK = argv[i + 1]
        del argv[i:i + 2]
    rp_name, atlas_rel, PREFIX = PACKS[PACK]
    RP = os.path.join(ROOT, "packs", rp_name)
    PART_DIR = os.path.join(RP, "particles")
    ATLAS = os.path.join(RP, atlas_rel)
    filters = [a.lower() for a in argv]
    effects = []
    for name in sorted(os.listdir(PART_DIR)):
        if not name.endswith(".particle.json"):
            continue
        e = read_effect(os.path.join(PART_DIR, name))
        if filters and not any(f in e["id"].lower() for f in filters):
            continue
        effects.append(e)
    if not effects:
        print("no matching particles")
        return 1
    draw(effects, os.path.join(OUT, "particles.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
