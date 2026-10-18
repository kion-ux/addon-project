# -*- coding: utf-8 -*-
"""アストロ・ナノギア — プレビュー（ソフトレンダラで形・塗り・アニメを確かめる）。

    python3 tools/astro/preview_astro.py suit earth     # build_preview/astro/suit_earth.png
    python3 tools/astro/preview_astro.py suit earth --packed   # 生成済みの pack の物を読む
    python3 tools/astro/preview_astro.py docs           # docs/astro/suits.png（ある惑星のスーツ全部）

suit は planets/<key>/suit.py をその場で組み立てて塗る（pack は書き換えない）ので、作りながら何度でも回せる。
並べ図: 正面 / 背面 / 左側面 / 斜め前 / 見下ろし / 組み上がり 0.3・0.8・1.2・1.8 秒 / 空中（スラスター・マント）/
歩き / 解除の途中 / 一人称（fp_hide 後に残る物）。

拡張（ウェポン・コア・HUD の担当へ）:
  * COMMANDS に `"weapon": fn(args)` のように足す（fn は引数リストを受け取り、書いたパスを返す）
  * DOC_SECTIONS に `fn() -> [書いたパス]` を足すと `docs` で一緒に作られる
  * 武器を持たせた絵: astro_scene.render(asset, pose("hold"), anim, view, weapon={"geo":…, "tex":…,
    "anim": {"hold": {...}}})（hd_scene.weapon_quads と同じ規則で右手に付く）
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import astro_common as AC  # noqa: E402
import astro_scene as SC  # noqa: E402
import astro_suit as AS  # noqa: E402
from astro_data import PLANETS, TRANSFORM  # noqa: E402


# ===========================================================================
#  スーツの資産（その場で組み立てる / pack から読む）
# ===========================================================================
def build_asset(key) -> SC.SuitAsset:
    import gen_astro_suits as G
    s = G.build_suit(key)
    p = G.paint(s)
    anims = G.suit_animations(s)
    pre = f"animation.{AC.NS}.suit.{key}."
    short = {k[len(pre):]: v for k, v in anims.items()}
    a = SC.SuitAsset(key, s.m.to_json(), p.img.copy(), short)
    a.suit = s
    return a


def asset(key, packed=False) -> SC.SuitAsset:
    return SC.load_suit(key) if packed else build_asset(key)


# ===========================================================================
#  並べ図
# ===========================================================================
TILE = (300, 400)


def suit_tiles(a: SC.SuitAsset, tile=TILE):
    """スーツ 1 着ぶんのタイル（ラベル付き）。"""
    key = a.key
    P = PLANETS[key]
    tiles = []
    idle = SC.suit_anim(a, ["idle", "thrust"], 0.6)
    for view, ja in (("front", "正面"), ("back", "背面"), ("left", "左側面"),
                     ("q34", "斜め前"), ("high", "見下ろし")):
        im = SC.render(a, SC.pose("stand"), idle, view, tile)
        tiles.append(SC.label(im, ja, P["suit_ja"] if view == "front" else None))
    for t in (0.3, 0.8, 1.2, TRANSFORM["assemble_len"]):
        im = SC.render(a, SC.pose("stand"), SC.assembly_anim(a, t), "q34", tile)
        tiles.append(SC.label(im, f"組み上がり {t:.1f}s"))
    air = SC.suit_anim(a, ["idle", "thrust"], 1.3, {"v.astro_air": 1.0})
    im = SC.render(a, SC.pose("air"), air, (-150, -14), tile)
    tiles.append(SC.label(im, "空中（スラスター）"))
    run = SC.suit_anim(a, ["idle", "thrust", "sprint"], 0.9, {"v.astro_run": 1.0})
    im = SC.render(a, SC.pose("walk", 0.22), run, "right", tile)
    tiles.append(SC.label(im, "疾走"))
    wp = SC.load_attachable(f"weapon_{key}", ("tp", "idle"), 0.6)
    if wp:                                        # その惑星のナノウェポンが生成済みなら持たせる
        im = SC.render(a, SC.pose("hold"), idle, (-50, -8), tile, weapon=wp)
        tiles.append(SC.label(im, "ナノウェポン"))
    rel = SC.release_anim(a, 0.35)
    im = SC.render(a, SC.pose("stand"), rel, "q34", tile)
    tiles.append(SC.label(im, "解除 0.35s"))
    fp = SC.suit_anim(a, ["idle", "thrust", "fp_hide"], 0.6)
    im = SC.render_fp(a, fp, (tile[0] * 2, tile[1]))
    tiles.append(SC.label(im, "一人称（fp_hide 後）"))
    return tiles


def suit_sheet(key, packed=False, out=None):
    a = asset(key, packed)
    tiles = suit_tiles(a)
    # 一人称は 2 枠ぶんの横長なので、最後の行で 2 枠を使う
    from PIL import Image
    cols = 5
    w, h = TILE
    fp = tiles.pop()
    rows = (len(tiles) + 2 + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows + 44), (12, 13, 18))
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * w, 44 + (k // cols) * h))
    k = len(tiles)
    sheet.paste(fp, ((k % cols) * w, 44 + (k // cols) * h))
    s = getattr(a, "suit", None)
    stat = (f"{len(s.m.bones)} bones / {len(s.m.all_cubes())} cubes / "
            f"{s.m.tex_w}x{s.m.tex_h}" if s else "")
    from PIL import ImageDraw
    ImageDraw.Draw(sheet).text((12, 10), f"{PLANETS[key]['suit_ja']}  {PLANETS[key]['suit_en']}"
                               f"   {stat}", font=SC.font(22), fill=(240, 244, 255))
    out = out or os.path.join(AC.SCRATCH, f"suit_{key}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print(f"wrote {out}")
    return out


def suits_doc(packed=False):
    """docs/astro/suits.png: ある惑星のスーツを 1 行ずつ（正面・斜め・背面・空中）。"""
    from PIL import Image, ImageDraw
    keys = AS.available()
    if not keys:
        print("no suits")
        return []
    tile = (260, 360)
    rows = []
    for key in keys:
        a = asset(key, packed)
        P = PLANETS[key]
        idle = SC.suit_anim(a, ["idle", "thrust"], 0.6)
        air = SC.suit_anim(a, ["idle", "thrust"], 1.3, {"v.astro_air": 1.0})
        ims = [SC.render(a, SC.pose("stand"), idle, "front", tile),
               SC.render(a, SC.pose("stand"), idle, "q34", tile),
               SC.render(a, SC.pose("stand"), idle, "back", tile),
               SC.render(a, SC.pose("air"), air, (-150, -14), tile)]
        g = P["colors"]["glow"]
        SC.label(ims[0], P["suit_ja"], P["suit_en"], col=tuple(g))
        rows.append(ims)
    W = tile[0] * 4
    out = Image.new("RGB", (W, tile[1] * len(rows)), (12, 13, 18))
    for r, ims in enumerate(rows):
        for c, im in enumerate(ims):
            out.paste(im, (c * tile[0], r * tile[1]))
    path = os.path.join(AC.DOCS, "suits.png")
    os.makedirs(AC.DOCS, exist_ok=True)
    out.save(path)
    print(f"wrote {path}")
    return [path]


DOC_SECTIONS = [suits_doc]          # 他の担当は fn() -> [paths] を足す


def cmd_suit(args):
    packed = "--packed" in args
    keys = [a for a in args if not a.startswith("-")] or AS.available()
    return [suit_sheet(k, packed) for k in keys]


def cmd_docs(args):
    out = []
    for fn in DOC_SECTIONS:
        out += fn(packed="--packed" in args) if fn is suits_doc else fn()
    return out


COMMANDS = {"suit": cmd_suit, "docs": cmd_docs}


def main(argv):
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        raise SystemExit(2)
    COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
