# -*- coding: utf-8 -*-
"""README 用の画像（ビルドには含めない。モデルを変えたら手で実行）。

  docs/aot/lineup.png   人と巨人の大きさ比べ（調査兵・4m・7m・奇行種 10m・13m）
  docs/aot/titans.png   巨人の体型 4 種 × 顔と肌 3 種
  docs/aot/corps.png    調査兵団 10 人
  docs/aot/states.png   巨人の状態（膝をつく・食べる・夜に座り込む・討伐されて倒れる）と、兵士の飛行

    python3 tools/aot/gen_aot_docs.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

import aot_common as C
import aot_preview as AP
from aot_models import titan_metrics
from gen_aot_anim import hand_angles
from hd_preview import render

DOCS = os.path.join(C.ROOT, "docs", "aot")
BG = (22, 24, 30, 255)

NAMES = {
    "eren_yeager": "エレン", "mikasa_ackerman": "ミカサ", "armin_arlert": "アルミン",
    "levi_ackerman": "リヴァイ", "hange_zoe": "ハンジ", "erwin_smith": "エルヴィン",
    "jean_kirstein": "ジャン", "sasha_blouse": "サシャ", "connie_springer": "コニー",
    "survey_soldier": "調査兵",
}
BODY_NAMES = {"lanky": "細長い手足", "chubby": "肥満", "muscular": "筋肉質", "bighead": "大頭"}


def font(size):
    for path in ("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
                 "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def label(img, text, size=22, y=None):
    d = ImageDraw.Draw(img)
    f = font(size)
    w = d.textlength(text, font=f)
    d.text(((img.width - w) / 2, y if y is not None else img.height - size - 10), text, font=f,
           fill=(230, 226, 214, 255), stroke_width=2, stroke_fill=(10, 10, 14, 255))
    return img


def geo(name):
    return os.path.join(C.GEO_DIR, f"{name}.geo.json"), os.path.join(C.TEX_DIR, f"{name}.png")


def lineup():
    """足元を揃え、全高どおりの縮尺で並べる。"""
    px_per_m = 52
    cast = [("survey_soldier", "survey_soldier", 1.75, "調査兵 1.75m"),
            ("titan_bighead", "titan_bighead_0", 4.0, "4m級"),
            ("titan_lanky", "titan_lanky_1", 7.0, "7m級"),
            ("titan_chubby", "titan_chubby_2", 10.0, "奇行種 10m"),
            ("titan_muscular", "titan_muscular_0", 13.0, "13m級")]
    tiles = []
    for g, t, h, text in cast:
        size = int(h * px_per_m / 0.9)
        im = render(os.path.join(C.GEO_DIR, f"{g}.geo.json"), os.path.join(C.TEX_DIR, f"{t}.png"),
                    size, 20, -4, margin=0.05, bg=(0, 0, 0, 0), ss=2)
        bbox = im.getbbox()
        if bbox:
            im = im.crop(bbox)
        tiles.append((im, text))
    W = sum(im.width for im, _ in tiles) + 60 * (len(tiles) + 1)
    H = max(im.height for im, _ in tiles) + 110
    out = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(out)
    ground = H - 60
    d.line([(20, ground), (W - 20, ground)], fill=(90, 96, 80, 255), width=3)
    x = 60
    f = font(24)
    for im, text in tiles:
        out.alpha_composite(im, (x, ground - im.height))
        w = d.textlength(text, font=f)
        d.text((x + (im.width - w) / 2, ground + 14), text, font=f, fill=(230, 226, 214, 255))
        x += im.width + 60
    return out


def grid(tiles, cols, pad=8):
    w = max(t.width for t in tiles)
    h = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new("RGBA", (cols * w + pad * (cols + 1), rows * h + pad * (rows + 1)), BG)
    for i, t in enumerate(tiles):
        out.alpha_composite(t, (pad + (i % cols) * (w + pad), pad + (i // cols) * (h + pad)))
    return out


def titans():
    tiles = []
    for body in C.BODIES:
        for k in range(C.SKINS):
            g = os.path.join(C.GEO_DIR, f"titan_{body}.geo.json")
            t = os.path.join(C.TEX_DIR, f"titan_{body}_{k}.png")
            im = render(g, t, 300, 18 + k * 8, -4, ss=2, bg=BG)
            tiles.append(label(im, f"{BODY_NAMES[body]} {k + 1}", 20))
    return grid(tiles, 6)


def corps():
    tiles = []
    for key in C.SOLDIERS:
        g, t = geo(key)
        im = render(g, t, 280, 24, -6, ss=2, bg=BG)
        tiles.append(label(im, NAMES[key], 22))
        back = render(g, t, 280, 200, -6, ss=2, bg=BG)
        tiles.append(label(back, "背中", 18))
    return grid(tiles, 10)


def states():
    tiles = []
    body = "bighead"
    m = titan_metrics(body)
    env = {"v.hip": m["hip"], "v.knee": m["knee"], "v.thigh": m["thigh"], "v.stride": 1.0,
           "q.modified_move_speed": 1.0, "q.modified_distance_moved": 2.0}
    for k, v in hand_angles()[C.BODIES.index(body)].items():
        env["v." + k] = v
    g = os.path.join(C.GEO_DIR, f"titan_{body}.geo.json")
    t = os.path.join(C.TEX_DIR, f"titan_{body}_0.png")
    for st, when, text, yaw in (("attack", 0.55, "噛みつく", 60), ("grab", 1.0, "掴む", 40),
                                ("eat", 1.0, "食べる", 30), ("kneel", 1.0, "腱を削がれて膝をつく", 60),
                                ("sleep", 1.0, "夜は座り込む", 40), ("dying", 1.3, "うなじを削がれて倒れる", 40)):
        p = AP._pose("aot_entities.animation.json", f"animation.aot.titan.{st}", when, env)
        im = render(g, t, 300, yaw, -10, ss=2, pose=p, bg=BG, margin=0.06)
        tiles.append(label(im, text, 20))
    for key, anim, when, text in (("levi_ackerman", "fly", 0.3, "立体機動で飛ぶ"),
                                  ("mikasa_ackerman", "slash", 0.15, "回転斬り")):
        gg, tt = geo(key)
        p = AP._pose("aot_entities.animation.json", f"animation.aot.human.{anim}", when,
                     {"q.anim_time": when})
        im = render(gg, tt, 300, 70, -10, ss=2, pose=p, bg=BG, margin=0.06)
        tiles.append(label(im, text, 20))
    return grid(tiles, 4)


def main():
    os.makedirs(DOCS, exist_ok=True)
    for name, fn in (("lineup", lineup), ("titans", titans), ("corps", corps), ("states", states)):
        img = fn()
        img.convert("RGB").save(os.path.join(DOCS, f"{name}.png"), optimize=True)
        print(f"  docs/aot/{name}.png {img.size}")


if __name__ == "__main__":
    main()
