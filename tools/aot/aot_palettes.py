# -*- coding: utf-8 -*-
"""配色。アニメの作画を基準にした hex。

* 調査兵団の上着は赤みのある茶の革、シャツは生成りの白、ズボンは白、ブーツは焦茶
* マントは深緑、背に自由の翼（手前が白、奥が青）
* 立体機動装置は銀灰の鋼、ガスボンベは明るい銀、刃は青みの鋼
* 巨人は桃色がかった肌。目は大きく瞳は小さい。口の中は暗い赤
"""
from __future__ import annotations

import aot_common  # noqa: F401
from mctexture import shade, hexc


def S(base, second=None, pattern="flat", noise=6, **kw):
    d = {"base": base, "pattern": pattern, "noise": noise}
    if second:
        d["second"] = second
    d.update(kw)
    return d


def _hex(c):
    return "#%02x%02x%02x" % c


# ---------------------------------------------------------------------------
#  装備（NPC・アタッチャブル共通）
# ---------------------------------------------------------------------------
JACKET = "#8a5634"
GEAR = {
    "jacket": S(JACKET, "#6c4126", "leather", 4, dark="#2a1a10", light="#c99a72"),
    "jacket_dark": S("#5f3a22", "#47291a", "leather", 4),
    "shirt": S("#efece4", "#d6d1c4", "cloth", 3),
    "pants": S("#e8e3d4", "#cdc6b2", "cloth", 3),
    "strap": S("#3a2517", "#22150c", "leather", 3, rim=False),
    "boots": S("#4b2f1e", "#2f1d12", "leather", 4, ao=0.2),
    "cloak": S("#2d4f3a", "#203a2a", "weave", 3, ao=0.18),
    "cloak_in": S("#253f2f", "#1a2e22", "weave", 3),
    "steel": S("#9ca2a9", "#6c7279", "brushed", 4, light="#e4e8ec", dark="#2a2d31"),
    "steel_dark": S("#4b5057", "#33373c", "metal", 4, light="#a8aeb5", dark="#141518"),
    "tank": S("#c5c9ce", "#9fa4aa", "brushed", 3),
    "brass": S("#bb995c", "#8b6c39", "metal", 3),
    "blade": S("#d6dce4", "#aab3be", "brushed", 2, light="#ffffff"),
    "edge": S("#f4f7fb", "#dfe6ee", "flat", 1),
    "grip": S("#2b2a2e", "#18171a", "leather", 3),
    "wire": S("#2a2a2c", "#151516", "flat", 1),
    "scarf": S("#b51f2b", "#7e1119", "weave", 4),
    "cravat": S("#f2f2ee", "#d9d9d2", "cloth", 2),
    "bolo": S("#2a2420", "#1a1512", "flat", 2),
    "goggle": S("#5a4632", "#3a2c1e", "leather", 3),
    "decal": S("#d8d2c0", "#bdb6a2", "flat", 2),
    "spear": S("#6d737a", "#4d5258", "metal", 3),
    "spear_tip": S("#c9cfd6", "#9aa2ab", "brushed", 2),
    "red": S("#b8302a", "#7a1a16", "flat", 2),
    "paper": S("#e9dfc4", "#cfc2a0", "cloth", 2),
    "book": S("#2f4f3a", "#203628", "leather", 3),
}


# ---------------------------------------------------------------------------
#  調査兵団（人物）: 髪 / 瞳 / 肌
# ---------------------------------------------------------------------------
def person(hair, iris, skin="#f2d3b6", **extra):
    pal = dict(GEAR)
    pal.update({
        "base": S("#efece4", "#d6d1c4", "cloth", 3),
        "skin": S(skin, _hex(shade(hexc(skin), 0.84)), "skin", 2, skin=skin, iris=iris,
                  hair_col=hair, light="#fbfbfb", dark="#2a2026"),
        "hair": S(hair, "#000000", "hair", 5, light="#ffffff", dark="#0d0d12"),
        "hair2": S(_hex(shade(hexc(hair), 0.6)), "#000000", "hair", 4),
        "underlay": S("#efece4", "#d6d1c4", "cloth", 3),
        "suit": S("#efece4", "#d6d1c4", "cloth", 3),
        "cloth": S("#efece4", "#d6d1c4", "cloth", 3),
    })
    pal.update(extra)
    return pal


PEOPLE = {
    # 体格は rig.Build（身長 cm・等身・肩幅・手足の太さ）、見た目は hair/iris/skin
    "eren_yeager": person("#3d2a1f", "#2c9a8c"),
    "mikasa_ackerman": person("#141418", "#3e3c44", skin="#f4dcc6"),
    "armin_arlert": person("#e9cf7c", "#3b78c8", skin="#f6dcc6"),
    "levi_ackerman": person("#121216", "#5c6670", skin="#f1d9c4"),
    "hange_zoe": person("#6b4a32", "#6a4630"),
    "erwin_smith": person("#e3c47c", "#3d6eb8", skin="#efcfb2"),
    "jean_kirstein": person("#a47c4e", "#8a6a3a", hair2=S("#5a4026", "#000000", "hair", 4)),
    "sasha_blouse": person("#7a5232", "#8a5a2a"),
    "connie_springer": person("#a2a2a6", "#5a5a60", skin="#eccbaa"),
    "survey_soldier": person("#4a3626", "#4a4a58"),
}


# ---------------------------------------------------------------------------
#  巨人: 肌 / 髪 / 瞳 / 表情。3 種を全体型で使い回す
# ---------------------------------------------------------------------------
TITAN_LOOKS = [
    {"skin": "#e3a98e", "hair": "#3b2b20", "iris": "#5a4030", "expr": "grin"},
    {"skin": "#eec5ac", "hair": "#d2b46e", "iris": "#4c5c6c", "expr": "blank"},
    {"skin": "#cb8f6e", "hair": "#1e1a1a", "iris": "#3a2a24", "expr": "gape"},
]


def titan(look):
    skin = look["skin"]
    sk = S(skin, _hex(shade(hexc(skin), 0.86)), "skin", 2, skin=skin, iris=look["iris"],
           hair_col=look["hair"], expr=look["expr"], dark="#3a201a", grad=0.10, ao=0.18)
    return {
        "base": sk, "skin": sk, "suit": sk, "underlay": sk, "cloth": sk,
        "hair": S(look["hair"], "#000000", "hair", 5, light="#ffffff", dark="#0d0d12"),
        "nail": S(_hex(shade(hexc(skin), 1.08)), _hex(shade(hexc(skin), 0.9)), "flat", 2),
        "lip": S(_hex(shade(hexc(skin), 0.78)), _hex(shade(hexc(skin), 0.6)), "flat", 2),
        "mouth": S("#5a1a1e", "#3a0e12", "flat", 2),
    }


TITAN_PALETTES = [titan(x) for x in TITAN_LOOKS]
