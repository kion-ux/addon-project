# -*- coding: utf-8 -*-
"""Colour palettes, following the researched anime references.

Notable corrections against a first-guess reading of the series:
* the 防衛隊戦闘服 is **black** with silver hard plates and olive-green rig
  panels — not a white suit, and it has no helmet, visor or backpack;
* 怪獣8号 glows teal/cyan, not blue-white, and carries asymmetric damage on the
  left of its skull;
* 怪獣9号's post-molt form is dark grey with crimson spurs and red eyes;
* 怪獣10号 is crimson plate armour with magenta seams and a single blue eye;
* kaiju bleed dark violet, never red.
"""

# --- 日本防衛隊 戦闘服 G-X4552 ---------------------------------------------
DF_BASE = "#12141A"      # 全身インナー（マット漆黒）
DF_BASE_HI = "#1D2028"
DF_GREEN = "#35422F"     # 胸・膝・ポーチ
DF_GREEN_D = "#232C20"
DF_PLATE = "#D2D6D9"     # 硬質プレート
DF_PLATE_D = "#9AA1A8"
DF_DECAL = "#7E868F"
DF_SENSOR = "#25E5D8"
DF_VISOR = "#EDEFF2"     # 亜白ミナ専用バイザー
DF_RED = "#C4142A"


def S(base, second=None, pattern="flat", noise=7, **kw):
    d = {"base": base, "pattern": pattern, "noise": noise}
    if second:
        d["second"] = second
    d.update(kw)
    return d


def soldier(hair, iris, skin="#eec9a8", accent=DF_SENSOR):
    return {
        "base": S(DF_BASE, DF_BASE_HI, "weave", 5, glow=accent),
        "suit": S(DF_BASE, DF_BASE_HI, "weave", 5, glow=accent),
        "underlay": S("#0b0d12", "#05060a", "weave", 4, glow=accent),
        "armor": S(DF_PLATE, DF_PLATE_D, "panel", 4, glow=accent,
                   light="#ffffff", dark="#1b1e24"),
        "green": S(DF_GREEN, DF_GREEN_D, "cloth", 5, glow=accent,
                   light="#8f9c86", dark="#151a12"),
        "cloth": S("#14161b", "#08090c", "leather", 5, glow=accent),
        "accent": S(accent, "#0e5c58", "metal", 4, glow=accent),
        "visor": S(DF_VISOR, "#a8b0b8", "glass", 3, glow=accent, light="#ffffff"),
        "skin": S(skin, "#c9967a", "skin", 3, skin=skin, iris=iris,
                  hair_col=hair, light="#fbfbfb", dark="#241f28"),
        "hair": S(hair, "#000000", "hair", 6, light="#ffffff", dark="#0d0d12"),
        "steel": S("#8E959C", "#565c64", "brushed", 5, glow=accent),
        "red": S(DF_RED, "#6d0a17", "panel", 4, glow=DF_RED),
        "gold": S("#d8b45c", "#7a5f22", "metal", 5, glow="#ffd98a"),
        "decal": S(DF_DECAL, "#4c5259", "panel", 3, glow=accent),
    }


# --- キャラクター（アニメ版パレット） ---------------------------------------
KAFKA = soldier("#1E1A19", "#2B2320")
RENO = soldier("#C9CDD4", "#8B5FD6")
MINA = soldier("#14161C", "#C8712A")
HOSHINA = soldier("#3B2E5A", "#7B4FA8")
KIKORU = soldier("#F0D480", "#4CB86A", skin="#f6dcc4")
NARUMI = soldier("#1A1A1F", "#D3357F")
ISAO = soldier("#D9B25E", "#D8B23A")
OFFICER = soldier("#2b2823", "#4c4a58")

# --- 怪獣8号 ---------------------------------------------------------------
NO8_GLOW = "#25E5D8"
NO8_CORE = "#CFFFFA"
NO8 = {
    "base": S("#12161C", "#0B0E12", "carapace", 7, glow=NO8_GLOW),
    "hide": S("#12161C", "#0B0E12", "carapace", 7, glow=NO8_GLOW),
    "skin": S("#12161C", "#0B0E12", "carapace", 7, glow=NO8_GLOW),
    "suit": S("#12161C", "#0B0E12", "carapace", 7, glow=NO8_GLOW),
    "underlay": S("#0B0E12", "#05070a", "muscle", 6, glow=NO8_GLOW),
    "cloth": S("#0E1116", "#06080c", "carapace", 6, glow=NO8_GLOW),
    "crack": S("#0D1116", NO8_GLOW, "crack", 4, glow=NO8_GLOW),
    "plate": S("#1A1F26", "#0E1219", "plate", 5, glow=NO8_GLOW,
               light="#EFEAE0", dark="#05070a"),
    "bone": S("#EFEAE0", "#C8C2B4", "plate", 4, glow=NO8_GLOW,
              light="#fdfbf6", dark="#2a2820"),
    "mask": S("#EFEAE0", "#C8C2B4", "flat", 3, glow=NO8_GLOW,
              light="#fdfbf6", dark="#14161a"),
    "horn": S("#EFEAE0", "#C8C2B4", "flat", 3, glow=NO8_GLOW),
    "claw": S("#F4F0E6", "#CFC9BA", "flat", 3, glow=NO8_GLOW),
    "sinew": S("#3A2450", "#1c1028", "sinew", 6, glow=NO8_GLOW),
    "armor": S("#1A1F26", "#0E1219", "plate", 5, glow=NO8_GLOW, light="#EFEAE0"),
    "accent": S(NO8_GLOW, "#0A9FA8", "metal", 4, glow=NO8_CORE),
    "wing": S("#12161C", "#242c36", "muscle", 6, glow=NO8_GLOW),
    "visor": S("#EFEAE0", "#C8C2B4", "flat", 3, glow=NO8_GLOW),
    "hair": S("#12161C", "#0B0E12", "carapace", 6),
    "green": S("#12161C", "#0B0E12", "carapace", 6, glow=NO8_GLOW),
}

# --- 怪獣9号（γ形態・脱皮後） -----------------------------------------------
NO9_GLOW = "#FF2A2A"
NO9_SPUR = "#C4142A"
NO9 = {
    "base": S("#26282C", "#141518", "muscle", 7, glow=NO9_GLOW),
    "hide": S("#26282C", "#141518", "muscle", 7, glow=NO9_GLOW),
    "skin": S("#2C2E33", "#17181c", "muscle", 7, glow=NO9_GLOW),
    "suit": S("#26282C", "#141518", "muscle", 7, glow=NO9_GLOW),
    "underlay": S("#17181c", "#0a0b0d", "sinew", 6, glow=NO9_GLOW),
    "cloth": S("#1c1e22", "#0d0e10", "muscle", 6, glow=NO9_GLOW),
    "crack": S("#1e2024", NO9_GLOW, "crack", 4, glow=NO9_GLOW),
    "plate": S("#32343a", "#1a1b1f", "plate", 5, glow=NO9_GLOW),
    "bone": S("#D8CBB0", "#8A6E4E", "plate", 4, glow=NO9_GLOW),
    "mask": S("#2E3036", "#1a1b1f", "flat", 4, glow=NO9_GLOW,
              light="#D8CBB0", dark="#0a0b0d"),
    "horn": S(NO9_SPUR, "#6d0a17", "flat", 4, glow=NO9_GLOW),
    "claw": S(NO9_SPUR, "#6d0a17", "flat", 4, glow=NO9_GLOW),
    "sinew": S("#5A2A6E", "#2c1236", "sinew", 6, glow=NO9_GLOW),
    "armor": S("#32343a", "#1a1b1f", "plate", 5, glow=NO9_GLOW),
    "accent": S(NO9_SPUR, "#6d0a17", "metal", 4, glow=NO9_GLOW),
    "hair": S("#1a1b1f", "#0a0b0d", "hair", 5, glow=NO9_GLOW),
    "visor": S("#2E3036", "#1a1b1f", "flat", 4, glow=NO9_GLOW),
    "wing": S("#26282C", "#3a3d44", "muscle", 6, glow=NO9_GLOW),
    "green": S("#26282C", "#141518", "muscle", 6, glow=NO9_GLOW),
}

# --- 怪獣10号 --------------------------------------------------------------
NO10_SEAM = "#E0329B"
NO10_EYE = "#2A9BE0"
NO10 = {
    "base": S("#C4202A", "#7A1218", "plate", 7, glow=NO10_SEAM),
    "hide": S("#C4202A", "#7A1218", "plate", 7, glow=NO10_SEAM),
    "skin": S("#C4202A", "#7A1218", "plate", 7, glow=NO10_SEAM),
    "suit": S("#C4202A", "#7A1218", "plate", 7, glow=NO10_SEAM),
    "underlay": S("#5A2A6E", "#2c1236", "sinew", 6, glow=NO10_SEAM),
    "cloth": S("#8e1a20", "#4a0d12", "plate", 6, glow=NO10_SEAM),
    "crack": S("#8e1a20", NO10_SEAM, "crack", 4, glow=NO10_SEAM),
    "plate": S("#E0424A", "#8a1a20", "plate", 6, glow=NO10_SEAM,
               light="#ffd6d8", dark="#2a0a0e"),
    "belly": S("#8e1a20", "#4a0d12", "carapace", 6, glow=NO10_SEAM),
    "bone": S("#E0424A", "#8a1a20", "plate", 5, glow=NO10_SEAM),
    "mask": S("#C4202A", "#7A1218", "plate", 5, glow=NO10_EYE,
              light="#ffd6d8", dark="#2a0a0e"),
    "horn": S("#E0424A", "#7A1218", "flat", 4, glow=NO10_SEAM),
    "claw": S("#E0424A", "#7A1218", "flat", 4, glow=NO10_SEAM),
    "sinew": S("#5A2A6E", "#2c1236", "sinew", 6, glow=NO10_SEAM),
    "armor": S("#E0424A", "#8a1a20", "plate", 6, glow=NO10_SEAM),
    "accent": S(NO10_SEAM, "#7a1a52", "metal", 4, glow=NO10_SEAM),
    "eye": S("#1a0a10", NO10_EYE, "flat", 3, glow=NO10_EYE),
    "hair": S("#7A1218", "#3a080c", "hair", 5),
    "visor": S("#C4202A", "#7A1218", "flat", 4, glow=NO10_EYE),
    "wing": S("#8e1a20", "#4a0d12", "muscle", 6, glow=NO10_SEAM),
    "green": S("#C4202A", "#7A1218", "plate", 6, glow=NO10_SEAM),
}

# --- 本獣 ------------------------------------------------------------------
HONJU_GLOW = "#E86A28"
HONJU = {
    "base": S("#4A4238", "#2A2620", "scale", 9, glow=HONJU_GLOW),
    "hide": S("#4A4238", "#2A2620", "scale", 9, glow=HONJU_GLOW),
    "skin": S("#4A4238", "#2A2620", "scale", 9, glow=HONJU_GLOW),
    "suit": S("#4A4238", "#2A2620", "scale", 9, glow=HONJU_GLOW),
    "underlay": S("#2A2620", "#16130f", "scale", 7, glow=HONJU_GLOW),
    "cloth": S("#3a342c", "#1f1c17", "scale", 8, glow=HONJU_GLOW),
    "shell": S("#4A4238", "#2A2620", "scale", 9, glow=HONJU_GLOW),
    "flesh": S("#7A2B3A", "#3f141d", "muscle", 8, glow=HONJU_GLOW),
    "belly": S("#8A8070", "#565044", "plate", 7, glow=HONJU_GLOW),
    "plate": S("#3a342c", "#1f1c17", "carapace", 8, glow=HONJU_GLOW),
    "crack": S("#3a342c", HONJU_GLOW, "crack", 4, glow=HONJU_GLOW),
    "bone": S("#8A8070", "#565044", "plate", 6, glow=HONJU_GLOW),
    "mask": S("#4A4238", "#2A2620", "flat", 5, glow=HONJU_GLOW,
              light="#8A8070", dark="#16130f"),
    "horn": S("#8A8070", "#565044", "flat", 5, glow=HONJU_GLOW),
    "claw": S("#9a9082", "#5e5849", "flat", 4, glow=HONJU_GLOW),
    "sinew": S("#7A2B3A", "#3f141d", "sinew", 7, glow=HONJU_GLOW),
    "armor": S("#3a342c", "#1f1c17", "carapace", 8, glow=HONJU_GLOW),
    "accent": S(HONJU_GLOW, "#8c3410", "metal", 4, glow=HONJU_GLOW),
    "hair": S("#3a342c", "#1f1c17", "hair", 6),
    "visor": S("#4A4238", "#2A2620", "flat", 4, glow=HONJU_GLOW),
    "wing": S("#3a342c", "#4A4238", "muscle", 7, glow=HONJU_GLOW),
    "green": S("#4A4238", "#2A2620", "scale", 8, glow=HONJU_GLOW),
}

# --- 余獣 ------------------------------------------------------------------
YOJU = {
    "base": S("#6B6459", "#3E3A33", "carapace", 10, glow="#7FD8F0"),
    "shell": S("#6B6459", "#3E3A33", "carapace", 10, glow="#7FD8F0"),
    "hide": S("#6B6459", "#3E3A33", "carapace", 10, glow="#7FD8F0"),
    "underlay": S("#3E3A33", "#21201c", "carapace", 8, glow="#7FD8F0"),
    "flesh": S("#9A8E7C", "#5e5648", "muscle", 8, glow="#7FD8F0"),
    "belly": S("#9A8E7C", "#5e5648", "plate", 8, glow="#7FD8F0"),
    "claw": S("#3E3A33", "#21201c", "flat", 5, glow="#7FD8F0"),
    "horn": S("#3E3A33", "#21201c", "flat", 5, glow="#7FD8F0"),
    "crack": S("#4a463d", "#7FD8F0", "crack", 4, glow="#7FD8F0"),
    "plate": S("#57514a", "#302d28", "carapace", 8, glow="#7FD8F0"),
    "mask": S("#6B6459", "#3E3A33", "flat", 5, glow="#0C0E11",
              light="#9A8E7C", dark="#0C0E11"),
    "sinew": S("#5A2530", "#2c1218", "sinew", 6, glow="#7FD8F0"),
}

PARASITE = {
    "base": S("#8A8070", "#565044", "muscle", 9, glow="#7A2B3A"),
    "shell": S("#3E3A33", "#21201c", "carapace", 7, glow="#7A2B3A"),
    "flesh": S("#7A2B3A", "#3f141d", "muscle", 9, glow="#7A2B3A"),
    "claw": S("#9A8E7C", "#5e5648", "flat", 4),
    "hide": S("#8A8070", "#565044", "muscle", 9, glow="#7A2B3A"),
    "underlay": S("#3E3A33", "#21201c", "carapace", 7),
    "horn": S("#3E3A33", "#21201c", "flat", 5),
    "mask": S("#8A8070", "#565044", "flat", 5, dark="#0C0E11", light="#c8bfae"),
    "sinew": S("#5A2530", "#2c1218", "sinew", 6),
}

# --- 投射物 ----------------------------------------------------------------
BEAM = {"base": S("#E8FFFC", "#7FB6FF", "metal", 3, glow="#E8FFFC")}
ACID = {"base": S("#7A2B3A", "#3f141d", "muscle", 10, glow="#E86A28")}
BULLET = {"base": S("#8E959C", "#565c64", "metal", 5, glow="#FFE9A8")}

# --- 武器 ------------------------------------------------------------------
WEAPON = {
    "base": S("#8E959C", "#565c64", "brushed", 5, glow="#9FD8FF"),
    # SW-2033 保科の二刀: 黒染め、発光なし
    "sw_blade": S("#23262B", "#111317", "brushed", 4, glow="#9AA3AC",
                  light="#9AA3AC", dark="#0a0b0d"),
    "sw_edge": S("#9AA3AC", "#585e66", "metal", 3, light="#dfe4ea"),
    "sw_wrap": S("#15171A", "#080909", "weave", 4),
    # 03Ax-0112 キコルの大戦斧: 青白い放電
    "axe_head": S("#8E959C", "#565c64", "brushed", 5, glow="#9FD8FF"),
    "axe_edge": S("#E2E6EA", "#9aa0a8", "metal", 3, glow="#BFE3FF",
                  light="#ffffff"),
    "axe_haft": S("#1C1F24", "#0c0e11", "leather", 5),
    "axe_cell": S("#3A3F45", "#9FD8FF", "crack", 4, glow="#9FD8FF"),
    # T-25101985 亜白ミナの大型砲
    "gun_barrel": S("#4A5058", "#272b31", "brushed", 5, glow="#FFE9A8"),
    "gun_body": S("#1A1D21", "#0b0c0e", "panel", 4, glow="#FFE9A8"),
    "gun_bore": S("#0C0E11", "#050607", "flat", 2, glow="#FFE9A8"),
    # GS-3305 鳴海の巨大銃剣
    "gs_blade": S("#2E3238", "#161a1e", "brushed", 4, glow="#FF6A2A"),
    "gs_edge": S("#B8BEC6", "#6c727a", "metal", 3, glow="#FF6A2A",
                 light="#eef1f5"),
    "gs_body": S("#52585F", "#2b2f34", "panel", 4, glow="#FF6A2A"),
    # 共通
    "steel": S("#8E959C", "#565c64", "brushed", 5, glow="#9FD8FF",
               light="#e6eaee", dark="#1b1e22"),
    "edge": S("#E2E6EA", "#9aa0a8", "metal", 3, light="#ffffff", dark="#1b1e22"),
    "dark": S("#1A1D21", "#0b0c0e", "panel", 4, glow="#9FD8FF"),
    "grip": S("#15171A", "#080909", "leather", 5),
    "wrap": S("#1C1F24", "#0c0e11", "weave", 5),
    "accent": S("#9FD8FF", "#3c6f8c", "metal", 4, glow="#BFE3FF"),
    "core": S("#0C0E11", "#25E5D8", "flat", 3, glow="#CFFFFA"),
    "decal": S("#7E868F", "#4c5259", "panel", 3, glow="#9FD8FF"),
    "green": S("#35422F", "#232C20", "cloth", 5),
    "gold": S("#d8b45c", "#7a5f22", "metal", 5, glow="#FFE9A8"),
    "red": S("#C4142A", "#6d0a17", "panel", 4, glow="#C4142A"),
    "no8": S("#12161C", "#0B0E12", "carapace", 7, glow="#25E5D8"),
}

ALL = {
    "no8": NO8, "no9": NO9, "no10": NO10, "yoju": YOJU, "honju": HONJU,
    "kafka": KAFKA, "reno": RENO, "mina": MINA, "hoshina": HOSHINA,
    "kikoru": KIKORU, "narumi": NARUMI, "isao": ISAO, "officer": OFFICER,
    "beam": BEAM, "acid": ACID, "bullet": BULLET, "parasite": PARASITE,
    "weapon": WEAPON,
}
