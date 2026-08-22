# -*- coding: utf-8 -*-
"""配色 — キャラクターごとのスタイル辞書。

モデル側は ``Cube(style="helm")`` のように **キー名だけ** を渡す。
実際の色・模様・光り方はここで決まるので、モデルを触らずに見た目を
作り込める（テクスチャ担当の作業領域）。

参照する見た目
--------------
マグニートー: 画像のガンメタルの兜（M字クレスト）＋ 古典的な深紫の装甲と
深紅のマント。金属質は ``metal`` / ``brushed`` / ``panel`` パターンで、
磁力の発光は ``glow`` に紫を置いて emissive で拾わせる。
"""
from __future__ import annotations

# ---------------------------------------------------------------- 基本色
VIOLET = "#5B2E86"          # マグニートーの装甲
VIOLET_D = "#3A1C58"
VIOLET_L = "#7E4CB0"
CRIMSON = "#B01423"         # マント / ブーツ / 手袋
CRIMSON_D = "#6E0A16"
CRIMSON_L = "#D8323F"
GUNMETAL = "#8A9099"        # 兜（画像の色）
GUNMETAL_D = "#565C66"
GUNMETAL_L = "#C2C8D0"
STEEL = "#9AA2AC"
STEEL_D = "#5E656E"
MAG_GLOW = "#B47CFF"        # 磁界の光
IRON = "#6E747C"
NIGHT = "#14161C"


def S(base, second=None, pattern="flat", noise=6, **kw):
    """スタイル辞書を組み立てる小さなヘルパ。"""
    d = {"base": base, "pattern": pattern, "noise": noise}
    if second:
        d["second"] = second
    d.update(kw)
    return d


def _common(glow=MAG_GLOW, skin="#E8C4A2", iris="#4A6B8E", hair="#2A2530"):
    """どのキャラでも rig が触る既定スタイル。個別 palette が上書きする。"""
    return {
        "base": S(STEEL, STEEL_D, "brushed", 5, glow=glow),
        "skin": S(skin, "#C99A78", "skin", 3, skin=skin, iris=iris,
                  hair_col=hair, light="#FBFBFB", dark="#241F28"),
        "suit": S(NIGHT, "#1E212A", "weave", 5, glow=glow),
        "underlay": S("#0B0D12", "#05060A", "weave", 4, glow=glow),
        "armor": S(STEEL, STEEL_D, "panel", 4, glow=glow, light="#FFFFFF",
                   dark="#1B1E24"),
        "accent": S(glow, "#3A1C58", "metal", 4, glow=glow),
        "hair": S(hair, "#000000", "hair", 6, light="#FFFFFF", dark="#0D0D12"),
        "steel": S(STEEL, STEEL_D, "brushed", 5, glow=glow),
        "cloth": S("#14161B", "#08090C", "leather", 5, glow=glow),
        "decal": S("#7E868F", "#4C5259", "panel", 3, glow=glow),
        "visor": S("#C8D4E0", "#7E8A96", "glass", 3, glow=glow, light="#FFFFFF"),
        "glow": S(glow, "#2A1450", "flat", 2, glow=glow),
        # モデルが使うかもしれない汎用キー（未指定でも壊れないように）
        "helm": S(GUNMETAL, GUNMETAL_D, "brushed", 4, glow=glow),
        "helm_dark": S(GUNMETAL_D, "#31363E", "metal", 4, glow=glow),
        "helm_crest": S(GUNMETAL_L, GUNMETAL_D, "brushed", 3, glow=glow),
        "cape": S(CRIMSON, CRIMSON_D, "cloth", 6, glow=glow),
        "cape_inner": S(CRIMSON_D, "#3A0710", "cloth", 5, glow=glow),
        "plate": S(VIOLET, VIOLET_D, "panel", 4, glow=glow),
        "plate_dark": S(VIOLET_D, "#24113A", "panel", 4, glow=glow),
        "belt": S(STEEL_D, "#3A3F46", "metal", 4, glow=glow),
        "boot": S(CRIMSON, CRIMSON_D, "leather", 5, glow=glow),
        "glove": S(CRIMSON, CRIMSON_D, "leather", 5, glow=glow),
        "magnet": S(MAG_GLOW, "#3A1C58", "metal", 3, glow=MAG_GLOW),
        "scale": S("#2E6BA8", "#1A3E68", "scale", 5, glow=glow),
        "fur": S("#B08A4E", "#6E552C", "hair", 8, glow=glow),
        "claw": S("#E4E0D4", "#8E8A7E", "brushed", 4, glow=glow),
        "flame": S("#E8721E", "#8E3A0A", "muscle", 8, glow="#FFC24A"),
        "stone": S("#7A6E5E", "#4A423A", "crack", 7, glow="#C8A05A"),
        "hex": S("#B01234", "#5E0A1C", "glass", 5, glow="#FF4A6E"),
        "gut": S("#8E5A4A", "#5E3428", "muscle", 6, glow=glow),
        "tongue": S("#C8607A", "#8E3A4E", "sinew", 5, glow=glow),
        "goggle": S("#2A2E38", "#14161C", "glass", 3, glow="#FF6A2A"),
        "rune": S(MAG_GLOW, "#2A1450", "crack", 3, glow=MAG_GLOW),
        "robot": S("#6E5A9E", "#42356E", "panel", 4, glow="#FF5A2A"),
        "robot_dark": S("#3A2E5E", "#241C3E", "panel", 4, glow="#FF5A2A"),
        "optic": S("#FF5A2A", "#8E2A0A", "glass", 3, glow="#FFB24A"),
        "cable": S("#24262E", "#12141A", "rubber", 4, glow=glow),
        "hazard": S("#D8B42A", "#8E7010", "plate", 5, glow="#FFE24A"),
        "shard": S(IRON, "#3E434A", "metal", 5, glow=glow),
        "rock": S("#6E6458", "#3E382E", "crack", 7, glow="#A88E5A"),
        "energy": S(glow, "#2A1450", "glass", 2, glow=glow),
    }


# ===========================================================================
#  マグニートー  —  画像のガンメタル兜 ＋ 深紫の装甲 ＋ 深紅のマント
# ===========================================================================
MAGNETO = _common(glow=MAG_GLOW, skin="#E2BE9E", iris="#5E7A9E", hair="#B8BCC4")
MAGNETO.update({
    "helm": S(GUNMETAL, GUNMETAL_D, "brushed", 4, glow=MAG_GLOW,
              light="#E4E8EE", dark="#22252B"),
    "helm_dark": S(GUNMETAL_D, "#3A3F47", "metal", 4, glow=MAG_GLOW,
                   light="#B4BAC2", dark="#16181D"),
    "helm_crest": S(GUNMETAL_L, GUNMETAL, "brushed", 3, glow=MAG_GLOW,
                    light="#FFFFFF", dark="#2A2E34"),
    "plate": S(VIOLET, VIOLET_D, "panel", 5, glow=MAG_GLOW, light="#B48EE0",
               dark="#1A0C2A"),
    "plate_dark": S(VIOLET_D, "#25123A", "panel", 4, glow=MAG_GLOW),
    "cape": S(CRIMSON, CRIMSON_D, "cloth", 7, glow=MAG_GLOW, light="#E86A74",
              dark="#42060E"),
    "cape_inner": S(CRIMSON_D, "#3E0710", "cloth", 6, glow=MAG_GLOW),
    "suit": S(VIOLET_D, "#2A1442", "weave", 5, glow=MAG_GLOW),
    "underlay": S("#1A0E2A", "#0E0718", "weave", 4, glow=MAG_GLOW),
    "boot": S(CRIMSON, CRIMSON_D, "leather", 6, glow=MAG_GLOW, light="#E86A74"),
    "glove": S(CRIMSON, CRIMSON_D, "leather", 6, glow=MAG_GLOW, light="#E86A74"),
    "belt": S(STEEL_D, "#3A3F46", "metal", 4, glow=MAG_GLOW, light="#D2D8E0"),
    "armor": S(VIOLET, VIOLET_D, "panel", 5, glow=MAG_GLOW),
    "accent": S(MAG_GLOW, "#3A1C58", "metal", 3, glow=MAG_GLOW),
    "magnet": S(MAG_GLOW, "#3A1C58", "glass", 2, glow=MAG_GLOW),
})

# ===========================================================================
#  ブラザーフッド
# ===========================================================================
MYSTIQUE = _common(glow="#3AA8E0", skin="#2E6BA8", iris="#E8C42A", hair="#C4361E")
MYSTIQUE.update({
    "skin": S("#2E6BA8", "#1A3E68", "scale", 4, skin="#2E6BA8", iris="#E8C42A",
              hair_col="#C4361E", light="#8AC4E8", dark="#0E2038"),
    "scale": S("#2E6BA8", "#1A3E68", "scale", 5, glow="#3AA8E0"),
    "hair": S("#C4361E", "#6E1A0A", "hair", 7, light="#F08A5A", dark="#3A0C04"),
    "suit": S("#12305A", "#081828", "weave", 5, glow="#3AA8E0"),
    "cloth": S("#0E2038", "#06101C", "leather", 4, glow="#3AA8E0"),
})

SABRETOOTH = _common(glow="#E8A02A", skin="#E4C0A0", iris="#D8B42A",
                     hair="#C8A462")
SABRETOOTH.update({
    "fur": S("#B08A4E", "#6E552C", "hair", 9, light="#E4C88E", dark="#3A2C14"),
    "hair": S("#C8A462", "#6E552C", "hair", 9, light="#F0DCA8", dark="#3A2C14"),
    "claw": S("#EFEADC", "#9A9488", "brushed", 3, glow="#FFF4D8",
              light="#FFFFFF", dark="#4A4640"),
    "suit": S("#3A2A1E", "#1E1610", "leather", 6, glow="#E8A02A"),
    "cloth": S("#2A1E14", "#14100A", "leather", 5, glow="#E8A02A"),
})

TOAD = _common(glow="#8EC84B", skin="#7A9A52", iris="#D8C42A", hair="#4A5A2A")
TOAD.update({
    "skin": S("#7A9A52", "#4A6030", "scale", 6, skin="#7A9A52", iris="#D8C42A",
              hair_col="#4A5A2A", light="#C4DC9A", dark="#1E2810"),
    "tongue": S("#C8607A", "#8E3A4E", "sinew", 5, glow="#E88AA0"),
    "suit": S("#3A4A22", "#1E280E", "cloth", 6, glow="#8EC84B"),
    "cloth": S("#2A3418", "#141A0A", "leather", 5, glow="#8EC84B"),
})

JUGGERNAUT = _common(glow="#E8562A", skin="#D8A882", iris="#3A2A20",
                     hair="#8E3A1E")
JUGGERNAUT.update({
    "helm": S("#8E1F1F", "#520E0E", "metal", 5, glow="#E8562A",
              light="#D86A5A", dark="#2A0808"),
    "helm_dark": S("#520E0E", "#2A0606", "metal", 4, glow="#E8562A"),
    "armor": S("#8E1F1F", "#520E0E", "panel", 5, glow="#E8562A"),
    "plate": S("#6E5A48", "#3E3226", "metal", 5, glow="#E8562A"),
    "suit": S("#4A2A1E", "#241410", "weave", 5, glow="#E8562A"),
    "belt": S("#C8A05A", "#6E5428", "metal", 4, glow="#FFD88A"),
})

QUICKSILVER = _common(glow="#8ED8FF", skin="#E8C8AC", iris="#4A8ABE",
                      hair="#DCE2EA")
QUICKSILVER.update({
    "hair": S("#DCE2EA", "#8E96A2", "hair", 5, light="#FFFFFF", dark="#5A6068"),
    "suit": S("#2A5A8E", "#12304E", "weave", 5, glow="#8ED8FF"),
    "armor": S("#C8CBD2", "#7E848C", "brushed", 4, glow="#8ED8FF"),
    "accent": S("#8ED8FF", "#2A5A8E", "metal", 3, glow="#8ED8FF"),
})

PYRO = _common(glow="#FFA02A", skin="#E4C0A0", iris="#8E5A2A", hair="#C8A462")
PYRO.update({
    "suit": S("#2A2A30", "#14141A", "weave", 5, glow="#FFA02A"),
    "armor": S("#D8621E", "#8E3A0A", "panel", 5, glow="#FFC24A"),
    "flame": S("#E8721E", "#8E3A0A", "muscle", 9, glow="#FFD86A"),
    "accent": S("#FFA02A", "#8E4A0A", "metal", 4, glow="#FFC24A"),
})

AVALANCHE = _common(glow="#C8843A", skin="#D8AE86", iris="#4A3A28",
                    hair="#2E241A")
AVALANCHE.update({
    "suit": S("#4A3E30", "#241E18", "weave", 6, glow="#C8843A"),
    "armor": S("#6B5A48", "#3A3026", "plate", 6, glow="#C8843A"),
    "stone": S("#7A6E5E", "#4A423A", "crack", 8, glow="#C8A05A"),
    "goggle": S("#2A2E38", "#14161C", "glass", 3, glow="#FF8A2A"),
})

BLOB = _common(glow="#E8C86A", skin="#E0B48E", iris="#3A2A1E", hair="#3A2A1E")
BLOB.update({
    "skin": S("#E0B48E", "#B4886A", "skin", 4, skin="#E0B48E", iris="#3A2A1E",
              hair_col="#3A2A1E", light="#FFF0DC", dark="#3A281E"),
    "gut": S("#E0B48E", "#B4886A", "muscle", 5, glow="#E8C86A"),
    "suit": S("#3E4A2A", "#1E2814", "cloth", 6, glow="#E8C86A"),
    "cloth": S("#2A3418", "#14180A", "leather", 5, glow="#E8C86A"),
})

SCARLET_WITCH = _common(glow="#FF4A6E", skin="#E8C4A8", iris="#4A8A6E",
                        hair="#4A2A1E")
SCARLET_WITCH.update({
    "suit": S("#8E1224", "#4A0812", "cloth", 6, glow="#FF4A6E",
              light="#E06A80", dark="#2A040A"),
    "cape": S("#B01234", "#5E0A1C", "cloth", 7, glow="#FF4A6E"),
    "cape_inner": S("#5E0A1C", "#2A040A", "cloth", 5, glow="#FF4A6E"),
    "armor": S("#C8A05A", "#6E5428", "metal", 4, glow="#FFD88A"),
    "hex": S("#B01234", "#5E0A1C", "glass", 5, glow="#FF4A6E"),
    "accent": S("#FF4A6E", "#6E0A1C", "metal", 3, glow="#FF4A6E"),
})

# ===========================================================================
#  敵
# ===========================================================================
SENTINEL = _common(glow="#FF5A2A", skin="#6E5A9E", iris="#FF5A2A",
                   hair="#3A2E5E")
SENTINEL.update({
    "robot": S("#6E5A9E", "#42356E", "panel", 4, glow="#FF5A2A",
               light="#B4A2E0", dark="#1E1836"),
    "robot_dark": S("#3A2E5E", "#241C3E", "panel", 4, glow="#FF5A2A"),
    "armor": S("#6E5A9E", "#42356E", "panel", 4, glow="#FF5A2A"),
    "plate": S("#8E5A3A", "#5A3620", "plate", 5, glow="#FF5A2A"),
    "optic": S("#FF5A2A", "#8E2A0A", "glass", 2, glow="#FFB24A"),
    "cable": S("#24262E", "#12141A", "rubber", 4, glow="#FF5A2A"),
    "steel": S("#8A8E9A", "#4E525C", "brushed", 5, glow="#FF5A2A"),
})

PRIME_SENTINEL = dict(SENTINEL)
PRIME_SENTINEL.update({
    "robot": S("#3A2E5E", "#241C3E", "panel", 4, glow="#E8621E",
               light="#8A78C0", dark="#120E22"),
    "robot_dark": S("#241C3E", "#120E22", "panel", 4, glow="#E8621E"),
    "armor": S("#3A2E5E", "#241C3E", "panel", 4, glow="#E8621E"),
    "plate": S("#5A4A2A", "#382C18", "plate", 5, glow="#E8621E"),
    "optic": S("#E8621E", "#8E2A0A", "glass", 2, glow="#FFD86A"),
    "hazard": S("#D8B42A", "#8E7010", "plate", 5, glow="#FFE24A"),
})

MRD = _common(glow="#FF6A2A", skin="#DCB694", iris="#3A3A44", hair="#2A2620")
MRD.update({
    "suit": S("#2A2E38", "#14161C", "weave", 5, glow="#FF6A2A"),
    "armor": S("#4A4E58", "#282C34", "panel", 4, glow="#FF6A2A"),
    "goggle": S("#1A1C22", "#0A0C10", "glass", 3, glow="#FF6A2A"),
    "hazard": S("#8E1F1F", "#4A0E0E", "plate", 5, glow="#FF6A2A"),
    "cloth": S("#1E2028", "#0E1014", "leather", 5, glow="#FF6A2A"),
})

# ===========================================================================
#  小物
# ===========================================================================
SHARD = _common(glow=MAG_GLOW)
SHARD.update({
    "base": S(IRON, "#3E434A", "metal", 6, glow=MAG_GLOW),
    "shard": S(IRON, "#3E434A", "metal", 6, glow=MAG_GLOW),
})
DEBRIS = _common(glow="#A88E5A")
DEBRIS.update({"base": S("#6E6458", "#3E382E", "crack", 8, glow="#A88E5A")})
ENERGY_VIOLET = _common(glow=MAG_GLOW)
ENERGY_VIOLET.update({"base": S(MAG_GLOW, "#3A1C58", "glass", 3, glow=MAG_GLOW)})
ENERGY_CRIMSON = _common(glow="#FF4A6E")
ENERGY_CRIMSON.update({"base": S("#FF4A6E", "#6E0A1C", "glass", 3,
                                 glow="#FF4A6E")})
ENERGY_FIRE = _common(glow="#FFB24A")
ENERGY_FIRE.update({"base": S("#FF8A2A", "#8E3A0A", "glass", 3,
                              glow="#FFD86A")})
ENERGY_ORANGE = _common(glow="#FF7A2A")
ENERGY_ORANGE.update({"base": S("#FF7A2A", "#8E2A0A", "glass", 3,
                                glow="#FFB24A")})

# ===========================================================================
ALL = {
    "magneto": MAGNETO,
    "mystique": MYSTIQUE,
    "sabretooth": SABRETOOTH,
    "toad": TOAD,
    "juggernaut": JUGGERNAUT,
    "quicksilver": QUICKSILVER,
    "pyro": PYRO,
    "avalanche": AVALANCHE,
    "blob": BLOB,
    "scarlet_witch": SCARLET_WITCH,
    "sentinel": SENTINEL,
    "prime_sentinel": PRIME_SENTINEL,
    "mrd": MRD,
    # 小物
    "shard": SHARD,
    "debris": DEBRIS,
    "energy_violet": ENERGY_VIOLET,
    "energy_crimson": ENERGY_CRIMSON,
    "energy_fire": ENERGY_FIRE,
    "energy_orange": ENERGY_ORANGE,
}


def for_character(key: str) -> dict:
    """contract.CHARACTERS[key]["pal"] を引いてスタイル辞書を返す。"""
    from contract import CHARACTERS
    return ALL[CHARACTERS[key]["pal"]]
