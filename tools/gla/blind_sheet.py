# -*- coding: utf-8 -*-
"""ブラインド批評用の技カード (企画書 §10 差別化の検収 / §16 ブラインド批評)。

企画書の検収条件は「技名と色を隠して録画を見ても、『伸ばす技』『連打』
『重い一撃』が区別できること」。実機の録画はここでは作れないが、
**技名を伏せたまま** 各技の時間配分・判定の形・命中回数・ノックバックを
1枚に並べることはできる。設計の段階で見分けが付かないものは、
実機でも見分けが付かない。

    python3 tools/gla/blind_sheet.py

    out/blind_techniques.png   技名を伏せたカード24枚（A〜X）
    out/blind_answers.md       答え合わせ用の対応表

カードだけを見て「これは伸ばす技」「これは連打」「これは重い一撃」を
言い当てられるか試し、言い当てられない組があれば spec.py の
windup / active / recover / hits / knockback を離す。
"""
from __future__ import annotations

import os
import string
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import spec                                             # noqa: E402

OUT = os.path.join(ROOT, "out")

TILE_W, TILE_H = 320, 212
COLS = 4
BG = (22, 24, 30)
CARD = (32, 35, 43)
INK = (226, 230, 238)
DIM = (132, 140, 154)

#  時間の3区間。色ではなく **長さと位置** で読めるようにする。
WINDUP = (92, 104, 128)
ACTIVE = (232, 196, 96)
RECOVER = (104, 88, 118)

#  判定の形は輪郭だけで描く。色を手掛かりにしない（ブラインドの主旨）。
SHAPE_INK = (196, 204, 218)

#  日本語が豆腐になると読めないので、CJK を持つフォントを探して使う。
#  無ければ既定のフォントに落ちる（そのときラベルは英字だけになる）。
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


FONT = _font(13)
FONT_BIG = _font(18)


def draw_shape(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
               shape: str, reach: float, radius: float) -> None:
    """判定の形を上から見た図で描く。原点（自分）は左端の点。"""
    cx, cy = x + 14, y + h // 2
    d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=SHAPE_INK)
    scale = (w - 34) / max(6.0, reach if reach else radius * 2)
    r = max(4, min(int(radius * scale * 0.5), h // 2 - 2))
    reach_px = min(int(reach * scale), w - 30)

    if shape == "line":
        d.line([cx, cy, cx + reach_px, cy], fill=SHAPE_INK, width=max(1, r // 2))
    elif shape == "cone":
        d.polygon([(cx, cy), (cx + reach_px, cy - r), (cx + reach_px, cy + r)],
                  outline=SHAPE_INK)
    elif shape == "arc":
        # 弧は半径が大きいのでカードからはみ出す。枠に収まる半径へ丸める。
        # 弧の縦の張り出しは rr*sin(46°)。枠の高さに収まる半径にする。
        rr = max(20, min(reach_px, int((h / 2 - 2) / 0.72)))
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr],
              start=-46, end=46, fill=SHAPE_INK, width=2)
        d.line([cx, cy, cx + int(rr * 0.72), cy - r], fill=DIM)
    elif shape == "slam":
        ex = cx + reach_px
        d.line([cx, cy, ex, cy], fill=DIM)
        d.ellipse([ex - r, cy - r, ex + r, cy + r], outline=SHAPE_INK, width=2)
    elif shape == "delayed":
        ex = cx + reach_px
        for i in range(0, reach_px, 8):
            d.line([cx + i, cy, cx + i + 4, cy], fill=DIM)
        d.ellipse([ex - r, cy - r, ex + r, cy + r], outline=SHAPE_INK, width=2)
    elif shape == "projectile":
        ex = cx + reach_px
        d.line([cx, cy, ex, cy], fill=DIM)
        d.ellipse([ex - 5, cy - 5, ex + 5, cy + 5], fill=SHAPE_INK)
        d.ellipse([ex - r, cy - r, ex + r, cy + r], outline=SHAPE_INK)
    elif shape in ("sphere", "zone"):
        rr = min(r, h // 2 - 2)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=SHAPE_INK, width=2)
    elif shape == "dash":
        d.line([cx, cy, cx + reach_px, cy], fill=DIM)
        for i in range(3):
            k = cx + int(reach_px * (0.3 + i * 0.28))
            d.polygon([(k, cy - 6), (k + 9, cy), (k, cy + 6)], outline=SHAPE_INK)
    else:                                   # self
        d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline=SHAPE_INK)
        d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], outline=DIM)


def card(t: spec.Tech, label: str) -> Image.Image:
    im = Image.new("RGB", (TILE_W, TILE_H), CARD)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, TILE_W - 1, TILE_H - 1], outline=(56, 60, 72))
    d.text((12, 8), label, fill=INK, font=FONT_BIG)

    # --- 時間配分 ----------------------------------------------------
    bar_y, bar_h = 34, 16
    x0, x1 = 12, TILE_W - 12
    total = max(1, t.total)
    px = (x1 - x0) / total
    cuts = [(t.windup, WINDUP), (t.active, ACTIVE), (t.recover, RECOVER)]
    x = x0
    for ticks, colour in cuts:
        wpx = ticks * px
        d.rectangle([x, bar_y, x + wpx, bar_y + bar_h], fill=colour)
        x += wpx
    d.text((12, bar_y + bar_h + 3),
           f"溜め {t.windup} / 有効 {t.active} / 後隙 {t.recover}  (計 {t.total}t)",
           fill=DIM, font=FONT)

    # --- 命中の刻み --------------------------------------------------
    hit_y = bar_y + bar_h + 22
    start = x0 + t.windup * px
    step = t.hit_interval or max(1, t.active // max(1, t.hits))
    gap = step * px
    for i in range(min(t.hits, 24)):
        hx = start + gap * i
        if hx > x1:
            break
        d.line([hx, hit_y, hx, hit_y + 10], fill=INK, width=2)
    d.text((12, hit_y + 13), f"命中 {t.hits} 回 / 1発 {t.damage:g}",
           fill=DIM, font=FONT)

    # --- 判定の形 ----------------------------------------------------
    draw_shape(d, 12, hit_y + 28, TILE_W - 24, 56, t.shape, t.reach, t.radius)

    # --- ノックバック ------------------------------------------------
    kb = int(min(1.0, t.kb_h / 5.0) * 120)
    d.text((12, TILE_H - 24), "反動", fill=DIM, font=FONT)
    d.rectangle([50, TILE_H - 18, 50 + kb, TILE_H - 12], fill=SHAPE_INK)
    return im


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    labels = list(string.ascii_uppercase)
    rows = (len(spec.TECHS) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * TILE_W, rows * TILE_H), BG)
    answers = ["# ブラインド批評の答え合わせ", "",
               "技名を伏せたカードは `blind_techniques.png`。",
               "見分けが付かない組があれば、spec.py の windup / active /",
               "recover / hits / knockback を離すこと（企画書 §10）。", "",
               "| 札 | 技 | 形態 | 判定 | 溜め/有効/後隙 | 命中 |",
               "|---|---|---|---|---|---|"]
    for i, t in enumerate(spec.TECHS):
        label = labels[i]
        sheet.paste(card(t, label), ((i % COLS) * TILE_W, (i // COLS) * TILE_H))
        answers.append(f"| {label} | {t.ja} | {spec.FORM_BY_KEY[t.form].ja} | "
                       f"{t.shape} | {t.windup}/{t.active}/{t.recover} | "
                       f"{t.hits}回 |")
    sheet.save(os.path.join(OUT, "blind_techniques.png"))
    with open(os.path.join(OUT, "blind_answers.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(answers) + "\n")
    print(f"blind sheet: {len(spec.TECHS)} cards -> out/blind_techniques.png")
    print("             answers -> out/blind_answers.md")


if __name__ == "__main__":
    main()
