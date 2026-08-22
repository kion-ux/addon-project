"""Colour palettes for every entity, keyed by the `style` tag used on cubes."""

# Japan Anti-Kaiju Defense Force combat suit: white shell, charcoal under-suit,
# blue power lines.
DF_WHITE = (224, 228, 234)
DF_DARK = (46, 50, 60)
DF_BLUE = (74, 158, 236)
DF_RED = (198, 42, 54)
SKIN = (238, 202, 172)
SKIN_PALE = (244, 216, 192)


def _s(base, second=None, pattern="flat", noise=8, **kw):
    d = {"base": base, "pattern": pattern, "noise": noise}
    if second:
        d["second"] = second
    d.update(kw)
    return d


# --------------------------------------------------------------- kaiju no.8
NO8_GLOW = (126, 216, 255)
NO8 = {
    "base": _s((36, 40, 54), (20, 22, 32), "muscle", 10, glow=NO8_GLOW),
    "hide": _s((36, 40, 54), (19, 21, 31), "muscle", 10, glow=NO8_GLOW),
    "crack": _s((30, 33, 46), NO8_GLOW, "crack", 6, glow=NO8_GLOW),
    "plate": _s((224, 221, 208), (166, 162, 146), "plate", 6, glow=NO8_GLOW),
    "mask": _s((230, 227, 214), (180, 176, 160), "flat", 4, glow=NO8_GLOW,
               light=(245, 244, 238), dark=(40, 38, 44)),
    "horn": _s((238, 235, 224), (188, 184, 170), "flat", 5),
    "claw": _s((242, 240, 232), (196, 192, 180), "flat", 4),
    "sinew": _s((92, 46, 52), (58, 26, 32), "muscle", 8, glow=NO8_GLOW),
}

# --------------------------------------------------------------- kaiju no.9
NO9_GLOW = (255, 62, 148)
NO9 = {
    "base": _s((186, 184, 196), (140, 138, 152), "flat", 6, glow=NO9_GLOW),
    "skin": _s((190, 188, 200), (144, 142, 156), "flat", 6, glow=NO9_GLOW),
    "coat": _s((28, 26, 36), (14, 13, 20), "cloth", 6, glow=NO9_GLOW),
    "mask": _s((236, 234, 240), (186, 184, 194), "flat", 4, glow=NO9_GLOW,
               light=(250, 250, 252), dark=(24, 22, 30)),
    "tendril": _s((22, 20, 30), (10, 9, 16), "hair", 5, glow=NO9_GLOW),
    "crack": _s((170, 168, 182), NO9_GLOW, "crack", 5, glow=NO9_GLOW),
    "claw": _s((236, 234, 240), (180, 178, 190), "flat", 4),
}

# -------------------------------------------------------------- kaiju no.10
NO10_GLOW = (255, 96, 56)
NO10 = {
    "base": _s((78, 50, 92), (46, 28, 56), "carapace", 10, glow=NO10_GLOW),
    "hide": _s((78, 50, 92), (46, 28, 56), "carapace", 10, glow=NO10_GLOW),
    "belly": _s((150, 118, 128), (104, 78, 90), "plate", 8, glow=NO10_GLOW),
    "wing": _s((60, 36, 72), (98, 60, 108), "muscle", 8, glow=NO10_GLOW),
    "horn": _s((228, 218, 200), (176, 166, 148), "flat", 5),
    "crack": _s((60, 38, 72), NO10_GLOW, "crack", 6, glow=NO10_GLOW),
}

# -------------------------------------------------------- yoju (lesser kaiju)
YOJU_GLOW = (255, 196, 66)
YOJU = {
    "base": _s((98, 112, 88), (62, 72, 56), "carapace", 12, glow=YOJU_GLOW),
    "shell": _s((98, 112, 88), (62, 72, 56), "carapace", 12, glow=YOJU_GLOW),
    "flesh": _s((156, 118, 106), (108, 78, 70), "muscle", 10, glow=YOJU_GLOW),
    "claw": _s((226, 220, 202), (170, 164, 148), "flat", 5),
}

# ---------------------------------------------------------- honju (main kaiju)
HONJU_GLOW = (255, 138, 48)
HONJU = {
    "base": _s((112, 94, 76), (72, 60, 48), "scale", 12, glow=HONJU_GLOW),
    "hide": _s((112, 94, 76), (72, 60, 48), "scale", 12, glow=HONJU_GLOW),
    "plate": _s((80, 68, 56), (50, 42, 34), "carapace", 10, glow=HONJU_GLOW),
    "belly": _s((162, 142, 116), (118, 102, 84), "plate", 9, glow=HONJU_GLOW),
    "claw": _s((230, 224, 208), (176, 170, 154), "flat", 5),
    "crack": _s((92, 76, 60), HONJU_GLOW, "crack", 6, glow=HONJU_GLOW),
}


# ------------------------------------------------------------ defense force
def soldier_palette(hair, iris=(52, 48, 66), skin=SKIN, accent=DF_BLUE, cloth=DF_DARK):
    return {
        "base": _s(DF_WHITE, (176, 182, 192), "plate", 5, glow=accent),
        "armor": _s(DF_WHITE, (172, 178, 190), "plate", 5, glow=accent,
                    light=(246, 248, 252), dark=(30, 32, 40)),
        "suit": _s(cloth, (26, 28, 36), "cloth", 6, glow=accent),
        "accent": _s(accent, (30, 78, 128), "metal", 5, glow=accent),
        "skin": _s(skin, (int(skin[0] * 0.82), int(skin[1] * 0.78), int(skin[2] * 0.76)),
                   "flat", 4, skin=skin, iris=iris, light=(250, 250, 250), dark=(40, 36, 48)),
        "hair": _s(hair, (int(hair[0] * 0.6), int(hair[1] * 0.6), int(hair[2] * 0.62)),
                   "hair", 7),
        "steel": _s((176, 182, 192), (118, 124, 136), "metal", 6),
        "red": _s(DF_RED, (120, 22, 32), "plate", 5, glow=DF_RED),
    }


KAFKA = soldier_palette((38, 34, 42))
RENO = soldier_palette((214, 210, 196), iris=(96, 120, 150))
MINA = soldier_palette((54, 40, 72), iris=(196, 40, 56))
HOSHINA = soldier_palette((70, 50, 92), iris=(148, 116, 196))
KIKORU = soldier_palette((236, 234, 228), iris=(92, 172, 226), skin=SKIN_PALE)
OFFICER = soldier_palette((44, 40, 46))

# ------------------------------------------------------------- misc / effects
BEAM = {"base": _s((196, 236, 255), (86, 178, 255), "metal", 4, glow=(196, 236, 255))}
ACID = {"base": _s((146, 214, 92), (86, 152, 52), "muscle", 14, glow=(198, 255, 120))}
BULLET = {"base": _s((208, 198, 150), (140, 128, 90), "metal", 6)}
PARASITE = {
    "base": _s((150, 120, 132), (96, 70, 84), "muscle", 12, glow=(255, 96, 120)),
    "shell": _s((66, 58, 74), (38, 32, 44), "carapace", 8, glow=(255, 96, 120)),
}

ALL = {
    "no8": NO8, "no9": NO9, "no10": NO10, "yoju": YOJU, "honju": HONJU,
    "kafka": KAFKA, "reno": RENO, "mina": MINA, "hoshina": HOSHINA,
    "kikoru": KIKORU, "officer": OFFICER, "beam": BEAM, "acid": ACID,
    "bullet": BULLET, "parasite": PARASITE,
}
