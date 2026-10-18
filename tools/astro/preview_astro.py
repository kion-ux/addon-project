# -*- coding: utf-8 -*-
"""アストロ・ナノギア — プレビュー（ソフトレンダラで形・塗り・アニメを確かめる）。

    python3 tools/astro/preview_astro.py suit earth     # build_preview/astro/suit_earth.png
    python3 tools/astro/preview_astro.py suit earth --packed   # 生成済みの pack の物を読む
    python3 tools/astro/preview_astro.py suit mars --module=path/to/draft.py
                                                        # 下書きの suit.py を mars の配色で描く（suit_mars_draft.png）
    python3 tools/astro/preview_astro.py docs           # docs/astro/suits.png（ある惑星のスーツ全部）

suit は planets/<key>/suit.py をその場で組み立てて塗る（pack は書き換えない）ので、作りながら何度でも回せる。
並べ図（プレイヤーの肌は描かない。変身中は透明なので）: 正面（7 頭身の目盛り + バニラの体の線）/ 背面 /
左側面 / 斜め前 / 斜め後ろ / 内部フレームだけ / 組み上がり 0.45・0.95・1.35・1.8 秒 / 空中（スラスター・マント）/
疾走 / ナノウェポン（生成済みなら）/ 見下ろし / 解除の途中 / 近接（上半身・脚・背中）/ 一人称（fp_hide 後に残る物）。
見出しの 2 行目に計測値（背丈・頭の高さと幅・胸/腰・脚の長さ・細かい部品の割合）。

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
def load_module_file(path):
    """suit.py を任意の場所から読む（--module=PATH。下書きを今の suit.py と差し替えずに見る時）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("suit_draft", os.path.abspath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_asset(key, module=None) -> SC.SuitAsset:
    import gen_astro_suits as G
    s = G.build_suit(key, module=module)
    p = G.paint(s)
    anims = G.suit_animations(s)
    pre = f"animation.{AC.NS}.suit.{key}."
    short = {k[len(pre):]: v for k, v in anims.items()}
    a = SC.SuitAsset(key, s.m.to_json(), p.img.copy(), short)
    a.suit = s
    return a


def asset(key, packed=False, module=None) -> SC.SuitAsset:
    return SC.load_suit(key) if packed else build_asset(key, module)


# ===========================================================================
#  並べ図
# ===========================================================================
TILE = (320, 440)
COLS = 5


def _measure(a):
    s = getattr(a, "suit", None)
    if s is None:
        return None
    try:
        return AS.measure(s)
    except Exception:  # noqa: BLE001
        return None


def suit_tiles(a: SC.SuitAsset, tile=TILE):
    """スーツ 1 着ぶんのタイル（ラベル付き）。プレイヤーの肌は描かない（変身中は透明）。
    正面には 7 頭身の目盛りとバニラのプレイヤーの箱（水色の線）を重ねる。"""
    key = a.key
    P = PLANETS[key]
    tiles = []
    idle = SC.suit_anim(a, ["idle", "thrust"], 0.6)
    m = _measure(a)
    H = m["height"] if m else 32.0
    sc = tile[1] / 46.0
    im = SC.render(a, SC.pose("stand"), idle, "front", tile, scale=sc, ghost=True, ruler=H)
    tiles.append(SC.label(im, "正面（7 頭身の目盛り）", "水色の線 = バニラのプレイヤーの体"))
    for view, ja in (("back", "背面"), ("left", "左側面"), ("q34", "斜め前"),
                     ((146, -10), "斜め後ろ")):
        im = SC.render(a, SC.pose("stand"), idle, view, tile, scale=sc)
        tiles.append(SC.label(im, ja))
    im = SC.render(a, SC.pose("stand"), idle, "q34", tile, scale=sc,
                   hide=SC.hide_except_groups(a, ["inner"]))
    tiles.append(SC.label(im, "内部フレーム（inner だけ）"))
    for t in (0.45, 0.95, 1.35, TRANSFORM["assemble_len"]):
        im = SC.render(a, SC.pose("stand"), SC.assembly_anim(a, t), "q34", tile, scale=sc)
        tiles.append(SC.label(im, f"組み上がり {t:.2f}s"))
    air = SC.suit_anim(a, ["idle", "thrust"], 1.3, {"v.astro_air": 1.0})
    im = SC.render(a, SC.pose("air"), air, (-150, -14), tile, scale=sc)
    tiles.append(SC.label(im, "空中（スラスター）"))
    run = SC.suit_anim(a, ["idle", "thrust", "sprint"], 0.9, {"v.astro_run": 1.0})
    im = SC.render(a, SC.pose("walk", 0.22), run, "right", tile, scale=sc)
    tiles.append(SC.label(im, "疾走"))
    wp = SC.load_attachable(f"weapon_{key}", ("tp", "idle"), 0.6)
    if wp:                                        # その惑星のナノウェポンが生成済みなら持たせる
        im = SC.render(a, SC.pose("hold"), idle, (-50, -8), tile, scale=sc, weapon=wp)
        tiles.append(SC.label(im, "ナノウェポン"))
    im = SC.render(a, SC.pose("stand"), idle, "high", tile, scale=sc)
    tiles.append(SC.label(im, "見下ろし"))
    rel = SC.release_anim(a, 0.35)
    im = SC.render(a, SC.pose("stand"), rel, "q34", tile, scale=sc)
    tiles.append(SC.label(im, "解除 0.35s"))
    im = SC.render(a, SC.pose("stand"), idle, (-28, -8), tile, scale=sc * 2.3,
                   centre=(-1.0, 25.0, 0))
    tiles.append(SC.label(im, "近接: 上半身"))
    im = SC.render(a, SC.pose("stand"), idle, (-40, -6), tile, scale=sc * 1.75,
                   centre=(-1.2, 8.2, 0))
    tiles.append(SC.label(im, "近接: 脚"))
    im = SC.render(a, SC.pose("stand"), idle, (160, -6), tile, scale=sc * 2.3,
                   centre=(-1.0, 21.0, 0))
    tiles.append(SC.label(im, "近接: 背中"))
    fp = SC.suit_anim(a, ["idle", "thrust", "fp_hide"], 0.6)
    im = SC.render_fp(a, fp, (tile[0] * 2, tile[1]), weapon=SC.load_attachable(
        f"weapon_{key}", ("fp", "idle"), 0.6, {"v.astro_fp": 1.0}) if wp else None)
    tiles.append(SC.label(im, "一人称（fp_hide 後）"))
    return tiles


def stat_line(a):
    s = getattr(a, "suit", None)
    if s is None:
        return ""
    m = _measure(a)
    txt = f"{len(s.m.bones)} bones / {len(s.m.all_cubes())} cubes / {s.m.tex_w}x{s.m.tex_h} " \
          f"texel x{s.m.uv_scale:g}"
    if m:
        txt += (f"   H {m['height']:.1f}  head {m['head_h']:.2f} (H/{m['height'] / max(m['head_h'], 1e-6):.2f})"
                f" w{m['head_w']:.1f}  chest/waist {m['chest_w']:.1f}/{m['waist_w']:.1f}"
                f"={m['chest_waist']:.2f}  legs {m['leg_vis'] / max(m['height'], 1e-6):.2f}H"
                f"  fine {100 * m['fine_share']:.0f}%")
    return txt


def suit_sheet(key, packed=False, out=None, module=None):
    from PIL import Image, ImageDraw
    a = asset(key, packed, module)
    tiles = suit_tiles(a)
    w, h = TILE
    fp = tiles.pop()                  # 一人称は 2 枠ぶんの横長
    n = len(tiles) + 2
    rows = (n + COLS - 1) // COLS
    sheet = Image.new("RGB", (w * COLS, h * rows + 44), (12, 13, 18))
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % COLS) * w, 44 + (k // COLS) * h))
    k = len(tiles)
    if k % COLS == COLS - 1:
        k += 1
    sheet.paste(fp, ((k % COLS) * w, 44 + (k // COLS) * h))
    ImageDraw.Draw(sheet).text((12, 4), f"{PLANETS[key]['suit_ja']}  {PLANETS[key]['suit_en']}",
                               font=SC.font(20), fill=(240, 244, 255))
    ImageDraw.Draw(sheet).text((12, 26), stat_line(a), font=SC.font(13), fill=(170, 200, 230))
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
    mod = [a.split("=", 1)[1] for a in args if a.startswith("--module=")]
    keys = [a for a in args if not a.startswith("-")] or AS.available()
    if mod:                      # 下書きの suit.py を <key> の配色で描く: suit <key> --module=path.py
        m = load_module_file(mod[0])
        name = os.path.splitext(os.path.basename(mod[0]))[0]
        return [suit_sheet(k, out=os.path.join(AC.SCRATCH, f"suit_{k}_{name}.png"), module=m)
                for k in keys[:1]]
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
