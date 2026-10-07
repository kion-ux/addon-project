# -*- coding: utf-8 -*-
"""README 用の画像を描き直す（ビルドには含めない。モデルや持ち方を変えたら手で実行）。

  docs/hyperdim/weapons.png  武器 8 種の単体
  docs/hyperdim/holds.png    武器ごとの持ち方（hd_scene で実機と同じ規則で組んだプレイヤー）
  docs/hyperdim/combos.png   三連コンボの振りかぶり → 振り抜き

    python3 tools/hyperdim/gen_hd_docs.py
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

import gen_hd_anim as GA
from hd_common import ELEMENTS, RP, WEAPONS
from hd_preview import render
from hd_scene import sheet, tp

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "docs", "hyperdim")
BMAP = {"rA": "rightArm", "lA": "leftArm", "b": "body", "h": "head", "rL": "rightLeg",
        "lL": "leftLeg", "root": "root", "w": "waist"}
# 鞭は普段とぐろを巻いている（武器側の idle と同じ曲げ）
WHIP_COIL = {f"seg{i}": {"rotation": (40 if i == 0 else 22, 0, 0)} for i in range(14)}

HOLD_LABEL = {"greatsword": "大剣 — 両手で中段", "twinblades": "双剣 — 二刀", "greataxe": "両手斧 — 下段",
              "dagger": "ダガー — 逆手", "bow": "弓 — 体の横で", "shield": "盾 — 腕の外側",
              "whip": "鞭 — とぐろ", "claws": "かぎ爪 — 獣の構え"}
COMBO_LABEL = {
    "greatsword": ("袈裟斬り", "逆袈裟", "兜割り"),
    "twinblades": ("右の横薙ぎ", "左の横薙ぎ", "十字斬り"),
    "greataxe": ("叩き斬り", "斬り上げ", "叩き割り"),
    "dagger": ("逆手の振り下ろし", "外への払い", "回転斬り"),
    "bow": ("弓で薙ぐ", "弓で突き上げ", "前蹴り"),
    "shield": ("盾で殴る", "縁で払う", "突き上げ"),
    "whip": ("打ち下ろし", "横に払う", "回りながら打つ"),
    "claws": ("右の振り下ろし", "左の振り下ろし", "両爪の斬り上げ"),
}


def font(size):
    for path in ("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
                 "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def paths(name):
    return (os.path.join(RP, "models", "entity", f"hd_{name}.geo.json"),
            os.path.join(RP, "textures", "entity", "hd", f"{name}.png"))


def pose_of(p):
    """gen_hd_anim の記法（rA=..., root_pos=...）→ hd_scene のボーン辞書。"""
    out = {}
    for k, v in p.items():
        if k == "root_pos":
            out.setdefault("root", {})["position"] = v
        else:
            out.setdefault(BMAP[k], {})["rotation"] = v
    return out


def weapon_pose(name, use=False):
    """武器側（アタッチャブル）の持ち位置。"""
    h = GA.HOLDS[name]["use"] if use else GA.HOLDS[name]
    s = h["tp"]["scale"]
    a = {"hold": {"rotation": h["tp"]["rotation"], "position": h["tp"]["position"], "scale": (s, s, s)}}
    if "left_tp" in h:
        ls = h["left_tp"]["scale"]
        a["hold_l"] = {"rotation": h["left_tp"]["rotation"], "position": h["left_tp"]["position"],
                       "scale": (ls, ls, ls)}
    if name == "bow" and not use:
        a["arrow"] = {"scale": (0, 0, 0)}
    if name == "whip":
        a.update(WHIP_COIL)
    return a


def weapons_sheet():
    views = {"greatsword": (60, -18), "twinblades": (55, -18), "greataxe": (60, -18), "dagger": (55, -20),
             "bow": (65, -10), "shield": (205, -12), "whip": (60, -25), "claws": (40, -15)}
    T = 360
    big, small = font(22), font(15)
    out = Image.new("RGBA", (T * 4, T * 2), (16, 18, 26, 255))
    for i, (k, (ja, en, el)) in enumerate(WEAPONS.items()):
        g = ELEMENTS[el]["glow"]
        tile = render(*paths(k), T, *views[k], ss=2, margin=0.12,
                      bg=(16 + g[0] // 14, 18 + g[1] // 14, 26 + g[2] // 14, 255),
                      pose=WHIP_COIL if k == "whip" else None, hide=("arrow", "hold_l", "left"))
        d = ImageDraw.Draw(tile)
        d.text((14, T - 52), ja.split(" ")[0], font=big, fill=g + (255,))
        d.text((14, T - 26), en, font=small, fill=(220, 224, 236, 255))
        out.alpha_composite(tile, ((i % 4) * T, (i // 4) * T))
    path = os.path.join(DOCS, "weapons.png")
    out.convert("RGB").save(path, optimize=True)
    return path


def holds_sheet():
    f = font(19)

    def tile(name, body, weapon, label):
        im = tp(*paths(name), body, weapon, yaw=32, pitch=-10, size=(300, 340), scale=6.4, centre=(0, 15, -3))
        ImageDraw.Draw(im).text((12, 10), label, font=f, fill=(235, 238, 245))
        return im

    tiles = [tile(n, pose_of(GA.hold_pose(n)), weapon_pose(n), HOLD_LABEL[n]) for n in WEAPONS]
    tiles.append(tile("bow", pose_of(GA.use_pose("bow")), weapon_pose("bow", True), "弓 — 引き絞り"))
    tiles.append(tile("shield", pose_of(GA.use_pose("shield")), weapon_pose("shield", True), "盾 — ガード"))
    return sheet(tiles, os.path.join(DOCS, "holds.png"), cols=5)


def combos_sheet():
    """各コンボの「振りかぶり」と「振り抜き」の 2 コマを横に並べる（hd_pose で解いた後の姿勢）。"""
    GA.prepare()
    f, fs = font(16), font(13)
    tiles = []
    for name in WEAPONS:
        for i, combo in enumerate(GA.COMBOS[name]):
            keys = sorted(combo[1], key=float)[1:-1]          # 両端は持ち姿勢
            picks = (keys[0], keys[1]) if len(keys) > 1 else (keys[0], keys[0])
            solved = GA.solved_motions(name)[f"combo{i + 1}"][1]
            for j, t in enumerate(picks):
                p = solved[min(solved, key=lambda x: abs(float(x) - float(t)))]
                im = tp(*paths(name), pose_of(p), weapon_pose(name), yaw=32, pitch=-10,
                        size=(200, 230), scale=4.2, centre=(0, 14, -3))
                d = ImageDraw.Draw(im)
                if j == 0:
                    d.text((8, 6), f"{WEAPONS[name][0].split(' ')[0]} {i + 1}", font=fs, fill=(150, 156, 172))
                    d.text((8, 24), COMBO_LABEL[name][i], font=f, fill=(235, 238, 245))
                else:
                    d.text((8, 6), "→", font=f, fill=(150, 156, 172))
                tiles.append(im)
    return sheet(tiles, os.path.join(DOCS, "combos.png"), cols=6)


def main():
    os.makedirs(DOCS, exist_ok=True)
    for fn in (weapons_sheet, holds_sheet, combos_sheet):
        print(f"  wrote {os.path.relpath(fn(), os.path.dirname(os.path.dirname(DOCS)))}")


if __name__ == "__main__":
    main()
