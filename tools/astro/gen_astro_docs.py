# -*- coding: utf-8 -*-
"""アストロ・ナノギア — README 用の画像（docs/astro/*.png）を、生成済みのパックから描く。

    python3 tools/astro/gen_astro_docs.py

* lineup.png    9 形態がナノウェポンを構えた並び
* transform.png 変身の組み上がり（ナノマシンが部位ごとに装甲を組む）
* weapons.png   ナノウェポンと惑星コア
* enemies.png   宇宙からの侵略者
* suits.png     全スーツの正面・斜め・背面・空中（preview_astro の docs）
hud.png は gen_astro_ui.py が書く。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw  # noqa: E402

import astro_common as AC  # noqa: E402
import astro_scene as SC  # noqa: E402
from astro_data import ENEMIES, PLANETS, TRANSFORM  # noqa: E402

DOCS = AC.DOCS
BG = (12, 13, 18)


def _title(img, text, sub=None):
    d = ImageDraw.Draw(img)
    d.text((16, 12), text, font=SC.font(26), fill=(240, 244, 255))
    if sub:
        d.text((16, 46), sub, font=SC.font(16), fill=(150, 158, 182))


def lineup():
    tile = (300, 420)
    cols = 3
    keys = list(PLANETS)
    head = 80
    out = Image.new("RGB", (tile[0] * cols, head + tile[1] * ((len(keys) + cols - 1) // cols)), BG)
    for i, key in enumerate(keys):
        a = SC.load_suit(key)
        idle = SC.suit_anim(a, ["idle", "thrust"], 0.6)
        wp = SC.load_attachable(f"weapon_{key}", ("tp", "idle"), 0.6)
        im = SC.render(a, SC.pose("hold"), idle, (-38, -8), tile, weapon=wp)
        P = PLANETS[key]
        SC.label(im, f"{P['ja']} {P['form_ja']}", P["weapon"]["ja"], col=tuple(P["colors"]["glow"]))
        out.paste(im, ((i % cols) * tile[0], head + (i // cols) * tile[1]))
    _title(out, "アストロ・ナノギア — 9 つの星装形態", "Astro Nanogear: nine planet forms and their nano weapons")
    return _save(out, "lineup.png")


def transform(key="earth"):
    tile = (240, 340)
    a = SC.load_suit(key)
    times = [0.05, 0.3, 0.6, 0.9, 1.2, 1.5, TRANSFORM["assemble_len"]]
    tiles = []
    for t in times:
        im = SC.render(a, SC.pose("stand"), SC.assembly_anim(a, t), "q34", tile)
        tiles.append(SC.label(im, f"{t:.1f}s"))
    wp = SC.load_attachable(f"weapon_{key}", ("tp", "idle"), 0.6)
    idle = SC.suit_anim(a, ["idle", "thrust"], 0.6)
    im = SC.render(a, SC.pose("hold"), idle, (-38, -8), tile, weapon=wp)
    tiles.append(SC.label(im, "ウェポン形成"))
    head = 80
    out = Image.new("RGB", (tile[0] * len(tiles), head + tile[1]), BG)
    for i, t in enumerate(tiles):
        out.paste(t, (i * tile[0], head))
    P = PLANETS[key]
    _title(out, f"変身 — {P['suit_ja']} の組み上がり",
           "ナノマシンがブーツ → 脚 → 腰 → 胴 → 背 → 腕 → 肩 → 兜 → バイザーの順に装甲を組む")
    return _save(out, "transform.png")


def weapons():
    from hd_preview import render
    T = 260
    keys = list(PLANETS)
    head = 80
    out = Image.new("RGB", (T * len(keys), head + T * 2 + 40), BG)
    for i, key in enumerate(keys):
        for row, what in enumerate(("weapon", "core")):
            geo = os.path.join(AC.RP, "models", "entity", f"{AC.NS}_{what}_{key}.geo.json")
            tex = os.path.join(AC.RP, "textures", "entity", AC.NS, f"{what}_{key}.png")
            if not (os.path.exists(geo) and os.path.exists(tex)):
                continue
            yaw, pitch = ((35, -22) if what == "weapon" else (25, -18))
            im = render(geo, tex, T, yaw, pitch, ss=2, bg=BG + (255,), margin=0.1)
            out.paste(im.convert("RGB"), (i * T, head + row * T))
        P = PLANETS[key]
        d = ImageDraw.Draw(out)
        d.text((i * T + 10, head + 2 * T + 6), P["weapon"]["ja"].split(" ")[-1],
               font=SC.font(15), fill=tuple(P["colors"]["glow"]))
    _title(out, "ナノウェポンと惑星コア", "上: 変身中に手のコアが変わるナノウェポン / 下: 変身の核になる惑星コア")
    return _save(out, "weapons.png")


def enemies():
    src = os.path.join(AC.SCRATCH, "enemy_{}.png")
    ids = ["void_drone", "void_sentinel", "nemesis", "hologram_target"]
    missing = [i for i in ids if not os.path.exists(src.format(i))]
    if missing:
        import subprocess
        subprocess.run([sys.executable, os.path.join(HERE, "gen_astro_entities.py"), "--preview"],
                       check=False)
    tiles = []
    for i in ids:
        p = src.format(i)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        w, h = im.size
        # 先頭の 1 枚（正面）を切り出す: 見出しの帯の下、横 4 枚並び
        top = 22
        tw = w // 4
        tile = im.crop((0, top, tw, top + min(tw, h - top)))
        tile = tile.resize((360, 360 * tile.height // tile.width))
        e = ENEMIES[i]
        SC.label(tile, e["ja"], f"HP {e['health']}")
        tiles.append(tile)
    if not tiles:
        return None
    head = 80
    out = Image.new("RGB", (sum(t.width for t in tiles), head + max(t.height for t in tiles)), BG)
    x = 0
    for t in tiles:
        out.paste(t, (x, head))
        x += t.width
    _title(out, "宇宙からの侵略者", "夜の地上に現れるドローンとセンチネル、ヴォイド・シグナルで降臨するボス、練習用のホログラム標的")
    return _save(out, "enemies.png")


def _save(img, name):
    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, name)
    img.save(path)
    print(f"wrote {path}")
    return path


def main(argv):
    only = set(argv)
    jobs = {"lineup": lineup, "transform": transform, "weapons": weapons, "enemies": enemies}
    for name, fn in jobs.items():
        if not only or name in only:
            fn()
    if not only or "suits" in only:
        import preview_astro
        preview_astro.suits_doc(packed=True)


if __name__ == "__main__":
    main(sys.argv[1:])
