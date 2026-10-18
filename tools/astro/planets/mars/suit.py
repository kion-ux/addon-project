# -*- coding: utf-8 -*-
"""火星 — 軍神機装 アレス（Ares Frame）。

全形態でいちばん重い人型の装甲。黒い鉄の骨格に真紅（plate）と錆色（plate2）の厚い板を重ね、
真鍮（brass）の縁と鉄（iron）の鈍いトゲ、橙に光る排気口と溶岩のひび（glow）。
装甲には擦り傷・欠け・赤い砂ぼこり（このファイルで足す塗りの kind "ares"）。

  兜      スパルタ風: 耳から耳へ渡る横向きの扇の鶏冠（transverse crest）・重い眉庇・
          前へ絞ったコリント式の頬当てと、橙に光る T 字のバイザー・広がるしころ
  肩      三段に重ねた巨大な肩当てと、上外へ突き出す鈍い三本のトゲ・裾の警告ストライプ
  胴      上が広い胸郭・真紅の胸板（溶岩のひびの発光）・装甲の籠に収めた火星の星核・高い襟・
          脇の排気口・段の腹当て
  腰      真鍮の鋲のベルトと紋章の留め金・二段の前垂れ（草摺）・三段の横の草摺・後ろ垂れ
  脚      膝に鈍いトゲの付いた重い脛当て・脛の稜・ふくらはぎの排気口・段の鉄靴（サバトン）
  背      炉のバックパック・二本の煙突（先が赤熱）・下後ろへ向く双発の大ノズル（fx_thrust）
  衛星    背中の後ろを回る二つの子機: フォボス（いびつな芋形・速い内側の軌道）と
          ダイモス（小さく滑らか・遅い外側の軌道）。どちらも fx_spin

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。右側だけ作り `_r` を付ける → 左は自動で鏡映。
回転（統合版の rotation）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く /
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import math
import random

from astro_common import bevel, cbox, line_on, octa, rbox, ring, stick, taper
from astro_suit import ARM_X, LEG_X, Suit, mirror_x

# ---------------------------------------------------------------------------
#  色
# ---------------------------------------------------------------------------
CRIMSON = (196, 58, 34)
RUST = (138, 66, 40)
IRON = (40, 34, 34)
OCHRE = (217, 137, 58)
DUST = (166, 104, 66)            # 火星の赤い砂ぼこり
STEEL = (82, 72, 72)             # 黒い鉄の下地の装甲
GLOW = (255, 122, 42)
BRASS_W = 0.42                   # 縁取りの幅


# ===========================================================================
#  塗りの追加: kind "ares"（擦り傷・欠け・砂ぼこりの付いた装甲）と "ares_rock"（衛星の岩肌）
#  astro_paint.AstroPainter に k_/p_ のメソッドを足すだけ（既存の kind は変えない）。
#  weapon.py も同じものを使う（install_painter() を呼ぶ）。
# ===========================================================================
def install_painter():
    from astro_paint import AstroPainter
    if getattr(AstroPainter, "_ares_kinds", False):
        return
    from hd_paint import fbm, hash2, hexc, mix, shade

    def smooth(e0, e1, x):
        t = max(0.0, min(1.0, (x - e0) / ((e1 - e0) or 1e-6)))
        return t * t * (3 - 2 * t)

    def p_ares(self, st, c):
        self.p_armor(st, c)
        w, h = c["w"], c["h"]
        rng = random.Random(c["seed"] * 7 + 13)
        marks = {}
        if w >= 5 and h >= 4:
            n = int(round(w * h * st.get("scratch", 0.008)))
            for _ in range(n):
                x, y = rng.randrange(1, w - 1), rng.randrange(1, h - 1)
                ln = rng.randint(2, max(2, min(7, (w + h) // 6)))
                sl = rng.choice((-0.55, -0.3, 0.0, 0.3, 0.6))
                dx = rng.choice((-1, 1))
                for i in range(ln):
                    px, py = x + i * dx, y + int(round(i * sl))
                    if 1 <= px < w - 1 and 1 <= py < h - 1:
                        marks[(px, py)] = 1
                        marks.setdefault((px, py + 1), 2)
            # 縁の欠け（下地の黒い鉄が覗く）
            for _ in range(int(round((w + h) * st.get("chips", 0.05)))):
                side = rng.randrange(4)
                if side == 0:
                    px, py = rng.randrange(1, w - 1), 1
                elif side == 1:
                    px, py = rng.randrange(1, w - 1), h - 2
                elif side == 2:
                    px, py = 1, rng.randrange(1, h - 1)
                else:
                    px, py = w - 2, rng.randrange(1, h - 1)
                marks[(px, py)] = 3
                if rng.random() < 0.5:
                    marks[(min(w - 2, px + 1), py)] = 3
        c["wear"] = marks

    def k_ares(self, x, y, st, c):
        col, a = self.k_armor(x, y, st, c)
        if a < 200:
            return col, a
        w, h = c["w"], c["h"]
        s = c["seed"]
        n = fbm(x * 0.19 + (s % 61), y * 0.19 + (s % 37), 5, 3)
        col = shade(col, 0.9 + 0.2 * n)
        dust = hexc(st.get("dust", DUST))
        face = c["face"]
        if face == "up":
            k = 0.12 + 0.3 * smooth(0.4, 0.8, n)
        elif face == "down":
            k = 0.0
        else:
            v = y / max(1, h - 1)
            k = smooth(0.45, 1.0, v) * (0.15 + 0.4 * n)
        k *= st.get("dust_k", 0.6)
        if k > 0:
            col = mix(col, dust, k)
        m = c.get("wear", {}).get((x, y))
        if m == 1:
            col = mix(col, st.get("scratch_col", (236, 208, 186)), 0.4)
        elif m == 2:
            col = shade(col, 0.8)
        elif m == 3:
            col = mix(col, (48, 40, 40), 0.7)
        return col, a

    def p_ares_rock(self, st, c):
        w, h = c["w"], c["h"]
        rng = random.Random(c["seed"] * 3 + 5)
        cr = []
        for _ in range(max(1, int(w * h * st.get("craters", 0.012)))):
            r = rng.uniform(1.0, max(1.2, min(w, h) * 0.28))
            cr.append((rng.uniform(0, w - 1), rng.uniform(0, h - 1), r))
        c["craters"] = cr

    def k_ares_rock(self, x, y, st, c):
        base = hexc(st.get("base", (120, 100, 90)))
        s = c["seed"]
        n = fbm(x * 0.3 + (s % 41), y * 0.3 + (s % 29), 11, 3)
        col = shade(base, 0.78 + 0.42 * n)
        if hash2(x, y, s) > 0.93:
            col = shade(col, 0.82)
        for cx, cy, r in c.get("craters", ()):
            d = math.hypot(x - cx, y - cy)
            if d < r - 0.6:
                col = shade(col, 0.72 + 0.12 * (d / r))
            elif d < r + 0.6:
                col = mix(col, (236, 214, 196), 0.28 if y < cy else 0.0)
        tint = st.get("tint")
        if tint:
            col = mix(col, hexc(tint), st.get("tint_k", 0.2))
        return col, 255

    AstroPainter.p_ares = p_ares
    AstroPainter.k_ares = k_ares
    AstroPainter.p_ares_rock = p_ares_rock
    AstroPainter.k_ares_rock = k_ares_rock
    AstroPainter._ares_kinds = True


install_painter()


def _armor(base, **kw):
    """擦り傷・砂ぼこり付きの装甲（kind "ares"）。"""
    from astro_paint import WHITE, mix, shade
    d = {"kind": "ares", "base": base, "light": mix(base, WHITE, 0.4), "dark": shade(base, 0.6),
         "line": shade(base, 0.3), "glow": GLOW, "noise": 3}
    d.update(kw)
    return d


# ===========================================================================
#  塗り（astro_paint.suit_styles("mars") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "plate": _armor(CRIMSON),
    "plate_b": _armor((132, 36, 24), panel=0, scratch=0.004),
    "steel": _armor(STEEL, line=(24, 20, 20), dust_k=0.7, scratch_col=(196, 184, 176)),
    "steel_b": _armor((62, 54, 54), panel=0, line=(20, 16, 16), dust_k=0.6, scratch=0.004,
                      scratch_col=(170, 160, 152)),
    "plate2": _armor(RUST, line=(52, 18, 10)),
    "plate2_b": _armor((104, 50, 32), panel=0, scratch=0.004, line=(46, 20, 12)),
    "accent": _armor(OCHRE, line=(80, 46, 18)),
    "iron": {"kind": "chrome", "base": (112, 102, 100), "light": (214, 202, 190), "line": (26, 20, 20)},
    "brass": {"kind": "trim", "base": (198, 134, 62), "light": (255, 214, 150), "dark": (112, 64, 26),
              "line": (58, 32, 12)},
    "frame": {"kind": "frame", "base": (62, 54, 54), "light": (110, 98, 94), "line": (22, 18, 18)},
    "visor": {"glow": (255, 140, 50), "light": (255, 236, 196), "deep": (150, 34, 8), "emit": 20},
    "flame": {"glow": (255, 116, 36), "light": (255, 238, 186), "deep": (190, 36, 8)},
    "flame_core": {"kind": "flame", "glow": (255, 214, 120), "light": (255, 255, 236),
                   "deep": (255, 120, 40), "bevel": False, "outline": False},
    "thruster": {"glow": (255, 130, 44), "light": (255, 236, 190), "deep": (150, 30, 8)},
    "glow_hot": {"kind": "glowline", "glow": (255, 104, 34), "light": (255, 200, 130),
                 "bevel": False, "outline": False},
    "ember": {"kind": "glowline", "glow": (255, 96, 30), "light": (255, 200, 120), "bevel": False,
              "outline": False, "emit": 60},
    "hazard": {"kind": "decal", "decal": "hazard", "c1": OCHRE, "c2": (44, 36, 34),
               "under": _armor(RUST)},
    "serial": {"kind": "decal", "decal": "serial", "text": "AR-04", "ink": (236, 170, 96),
               "under": _armor(RUST, panel=0)},
    "emblem": {"kind": "decal", "decal": "emblem", "color": GLOW,
               "under": {"kind": "frame", "base": (52, 44, 44), "ribs": 0, "line": (20, 16, 16)}},
    "phobos": {"kind": "ares_rock", "base": (124, 100, 88), "craters": 0.02, "bevel": False,
               "outline": True, "line": (46, 36, 32), "outline_k": 0.4},
    "deimos": {"kind": "ares_rock", "base": (170, 146, 128), "craters": 0.007, "bevel": False,
               "outline": True, "line": (70, 58, 50), "outline_k": 0.4},
}

# ===========================================================================
#  部位アニメ（Molang。q.anim_time は 12 秒でループするので周波数は 30°/秒の倍数に）
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # フォボスは速く（4 秒で一周）、ダイモスはゆっくり（12 秒で一周）。どちらも自分でも転がる
        "fx_spin_phobos": {"rotation": [0, 0, "q.anim_time * 90.0"]},
        "fx_spin_phobos_roll": {"rotation": ["q.anim_time * 120.0", "q.anim_time * 60.0", 0]},
        "fx_spin_deimos": {"rotation": [0, 0, "q.anim_time * 30.0 + 150.0"]},
        "fx_spin_deimos_roll": {"rotation": [0, "q.anim_time * 90.0", "q.anim_time * 30.0"]},
        "extra_orrery": {"position": [0, "math.sin(q.anim_time * 60.0) * 0.3", 0]},
    },
    "thrust": {
        # 空中では軌道が後ろへ倒れ、炎の上に回る
        "extra_orrery": {"rotation": ["-v.astro_air * 14.0", 0, 0]},
    },
    "sprint": {
        "extra_orrery": {"rotation": ["-v.astro_run * 10.0", 0, 0]},
    },
}


# ===========================================================================
def build_suit(s: Suit):
    s.inner_suit(gap=0.3)
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    arms(s)
    shoulders(s)
    helmet(s)
    moons(s)


# ---------------------------------------------------------------------------
#  鉄靴（段のサバトン・踵の噴射口・足首の関節）
# ---------------------------------------------------------------------------
def boots(s):
    X = LEG_X
    b = s.part("boots", "sabaton_r", "rightLeg")
    cbox(b, (X, -0.3, -0.55), (6.0, 1.0, 7.3), "frame")                  # 厚い靴底
    cbox(b, (X, 0.38, -0.5), (5.8, 0.36, 7.0), "brass")                  # 靴底の縁
    cbox(b, (X - 0.05, 1.95, 0.15), (5.7, 3.1, 5.9), "steel")            # 足の殻
    # 段のつま先（三枚が重なって下る）
    rbox(b, (X, 3.15, -2.7), (4.9, 1.7, 1.5), "plate", rot=(-32, 0, 0))
    t2 = rbox(b, (X, 2.15, -3.35), (5.2, 1.6, 1.6), "plate2", rot=(-46, 0, 0))
    stick(b, t2, "north", 0.5, 0.15, (4.8, BRASS_W, 0.2), "brass", sink=0.05)
    rbox(b, (X, 1.0, -3.95), (5.4, 1.5, 1.8), "plate", rot=(-62, 0, 0))
    cbox(b, (X, 0.35, -4.45), (4.4, 0.7, 0.8), "iron")                   # つま先の鉄
    # 踵: 板・噴射口
    rbox(b, (X, 1.9, 3.15), (5.2, 3.0, 1.0), "plate2", rot=(10, 0, 0))
    cbox(b, (X, 0.55, 3.55), (3.0, 1.0, 1.2), "frame")
    cbox(b, (X, 0.0, 3.55), (2.2, 0.2, 0.8), "thruster")
    # 外側: 足首の関節（鉄の円盤と光）と、警告ストライプの側板
    octa(b, (X - 3.05, 2.9, 0.3), 2.3, 0.6, "iron", axis="x")
    octa(b, (X - 3.4, 2.9, 0.3), 1.0, 0.3, "glow", axis="x")
    cbox(b, (X - 2.95, 1.25, -0.6), (0.5, 1.4, 3.6), "plate2",
         decals={"west": {"decal": "hazard", "c1": OCHRE, "c2": (44, 36, 34)}})
    cbox(b, (X + 0.4, 3.55, -2.25), (0.25, 0.25, 0.9), "glow")            # 甲の光る継ぎ目


# ---------------------------------------------------------------------------
#  脚（重い脛当て・膝のトゲ・腿）
# ---------------------------------------------------------------------------
def legs(s):
    X = LEG_X
    g = s.part("legs", "greave_r", "rightLeg")
    cbox(g, (X - 0.05, 5.4, 0.15), (5.6, 4.7, 5.9), "steel")             # 脛の殻（黒い鉄）
    keel = rbox(g, (X - 0.8, 5.25, -3.1), (1.8, 4.6, 0.9), "plate", rot=(0, 24, 0))
    mirror_x(g, keel, about=X)                                           # 脛の稜（真紅の V 字）
    cbox(g, (X, 5.2, -3.62), (0.32, 3.4, 0.2), "glow")                    # 稜の溶岩の線
    cbox(g, (X, 3.25, -3.3), (4.6, BRASS_W, 0.5), "brass")
    cbox(g, (X, 8.15, 0.15), (5.7, 1.5, 5.7), "frame")                   # 膝の関節
    # 膝当て: 面取りの板 + 上の庇 + 鈍いトゲ
    bevel(g, (X, 7.85, -3.2), (4.3, 3.2, 1.4), "plate", cut=0.6, axis="z")
    rbox(g, (X, 9.45, -2.85), (3.9, 1.1, 1.3), "plate2", rot=(35, 0, 0))
    octa(g, (X, 7.85, -4.05), 1.7, 0.5, "brass", axis="z")
    taper(g, (X, 7.85, -4.2), (X, 8.2, -5.5), 1.3, 0.5, 2, "iron", round_=False)
    # ふくらはぎの排気口
    calf = rbox(g, (X, 5.7, 3.1), (5.0, 4.4, 1.0), "plate2", rot=(-8, 0, 0))
    stick(g, calf, "south", 0.5, 0.5, (3.2, 2.8, 0.3), "vent", sink=0.1)
    # 外側の板（下端が外へ）と警告ストライプ
    side = rbox(g, (X - 3.0, 5.6, 0.4), (0.7, 4.3, 4.8), "plate2", rot=(0, 0, 5),
                decals={"west": {"decal": "hazard", "band": "bottom", "c1": OCHRE,
                                 "c2": (44, 36, 34)}})
    line_on(g, side, "west", (0.12, 0.72), (0.88, 0.72), 0.24, 0.2, "glow")
    # 腿
    t = s.part("legs", "thigh_r", "rightLeg", pivot=(X, 11.6, 0))
    cbox(t, (X - 0.05, 10.5, 0.15), (5.5, 3.4, 5.6), "steel_b")
    tf = rbox(t, (X, 10.4, -2.95), (4.8, 3.4, 0.9), "plate", rot=(-6, 0, 0))
    line_on(t, tf, "north", (0.2, 0.25), (0.8, 0.25), 0.24, 0.2, "glow")
    cbox(t, (X, 8.85, -3.05), (4.4, BRASS_W, 0.6), "brass")
    cbox(t, (X - 2.85, 10.3, 0.25), (0.7, 3.2, 4.6), "plate2",
         decals={"west": {"decal": "serial", "text": "AR-04", "ink": (236, 170, 96)}})


# ---------------------------------------------------------------------------
#  腰（鋲のベルト・紋章の留め金・前垂れ・横の草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    cbox(w, (0, 12.55, 0), (10.1, 2.0, 6.3), "frame")
    for x in (-4.2, -3.0, 3.0, 4.2):                                    # 真鍮の鋲
        cbox(w, (x, 12.55, -3.22), (0.55, 0.55, 0.25), "brass")
    bevel(w, (0, 12.55, -3.35), (3.2, 2.5, 0.9), "brass", cut=0.5, axis="z")   # 留め金
    cbox(w, (0, 12.55, -3.85), (2.0, 1.9, 0.2), "emblem")               # 火星の紋章
    # 前垂れ: 二段（真紅 → 錆色）。下の段に真鍮の縁と発光の線
    f1 = rbox(w, (-2.55, 10.25, -3.3), (4.1, 3.0, 0.8), "plate", rot=(-10, 6, 4))
    f1g = line_on(w, f1, "north", (0.15, 0.55), (0.85, 0.55), 0.24, 0.2, "glow")
    f2 = rbox(w, (-2.65, 8.35, -3.6), (3.9, 2.0, 0.7), "plate2", rot=(-14, 6, 5))
    f2t = stick(w, f2, "north", 0.5, 0.1, (3.7, BRASS_W, 0.2), "brass", sink=0.05)
    mirror_x(w, f1, f1g, f2, f2t)
    rbox(w, (0, 9.6, -3.35), (1.8, 4.6, 0.6), "hazard", rot=(-8, 0, 0))   # 中央の垂れ（警告）
    # 横の草摺: 三段（下端が外へ）
    s1 = rbox(w, (-5.3, 10.5, 0.0), (0.9, 4.2, 5.8), "plate", rot=(0, 0, 13))
    s2 = rbox(w, (-5.8, 9.3, 0.0), (0.8, 3.4, 5.2), "plate2", rot=(0, 0, 17))
    s2t = stick(w, s2, "west", 0.5, 0.06, (4.9, BRASS_W, 0.22), "brass", sink=0.05)
    s2g = line_on(w, s2, "west", (0.12, 0.62), (0.88, 0.62), 0.24, 0.2, "glow")
    s3 = rbox(w, (-6.15, 7.9, 0.0), (0.7, 1.8, 4.4), "plate", rot=(0, 0, 20))
    mirror_x(w, s1, s2, s2t, s2g, s3)
    # 後ろ垂れ
    rbox(w, (0, 10.5, 3.25), (8.2, 3.6, 0.8), "plate", rot=(12, 0, 0))
    b2 = rbox(w, (0, 8.75, 3.65), (6.8, 1.9, 0.7), "plate2", rot=(16, 0, 0))
    stick(w, b2, "south", 0.5, 0.1, (6.5, BRASS_W, 0.2), "brass", sink=0.05)


# ---------------------------------------------------------------------------
#  胴（胸郭・胸板と溶岩のひび・火星の星核の籠・襟・脇の排気口・腹）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    bevel(c, (0, 20.85, 0.0), (10.8, 7.5, 6.7), "steel", cut=1.1, axis="y")    # 上が広い胸郭（黒い鉄）
    cbox(c, (0, 15.5, 0.0), (9.3, 4.4, 5.5), "frame")                    # 腹の下地
    for y, wd in ((17.05, 6.6), (15.8, 6.0), (14.55, 5.3)):              # 段の腹当て
        rbox(c, (0, y, -2.98), (wd, 1.3, 0.8), "plate", rot=(-10, 0, 0),
             decals={"north": {"decal": "stripe", "dir": "v", "pos": 0.5, "width": 0.06,
                               "color": (40, 30, 28)}})
    ob = rbox(c, (-3.85, 15.6, -2.2), (1.5, 4.2, 1.2), "plate2", rot=(0, 34, -5))   # 脇腹
    mirror_x(c, ob)
    # 胸板（V 字に外へ開き、内の端が前へ）
    pec = rbox(c, (-2.75, 21.35, -3.45), (5.3, 4.5, 1.1), "plate", rot=(6, 16, 9))
    rim = stick(c, pec, "north", 0.5, 0.04, (5.1, BRASS_W, 0.22), "brass", sink=0.05)
    # 溶岩のひび（星核から外上へ、ぎざぎざに）
    k1 = line_on(c, pec, "north", (0.98, 0.45), (0.7, 0.62), 0.26, 0.2, "glow")
    k2 = line_on(c, pec, "north", (0.7, 0.62), (0.55, 0.9), 0.26, 0.2, "glow")
    k3 = line_on(c, pec, "north", (0.7, 0.62), (0.3, 0.55), 0.24, 0.2, "glow")
    k4 = line_on(c, pec, "north", (0.3, 0.55), (0.12, 0.75), 0.22, 0.2, "glow_hot")
    low = rbox(c, (-2.35, 18.35, -3.15), (4.1, 1.6, 0.9), "plate2", rot=(-8, 12, 13))
    mirror_x(c, pec, rim, k1, k2, k3, k4, low)
    # 襟（首の両脇に高く立ち上がる）
    col = rbox(c, (-3.25, 24.6, -0.2), (2.6, 1.9, 5.8), "plate2", rot=(0, 0, -22))
    colt = stick(c, col, "up", 0.5, 0.5, (2.0, 5.4, 0.25), "brass", sink=0.1)
    mirror_x(c, col, colt)
    rbox(c, (0, 24.05, -3.25), (4.6, 1.3, 0.9), "plate2", rot=(-28, 0, 0))
    # 星核: 鉄の八角の台 → 火星 → 四隅の爪 → 細い籠の桟 → 脈打つ光の輪
    octa(c, (0, 20.15, -3.75), 4.3, 1.0, "iron", axis="z")
    cbox(c, (0, 20.15, -4.2), (2.9, 2.9, 0.8), "core")
    for sx in (-1, 1):
        for sy in (-1, 1):
            rbox(c, (sx * 1.55, 20.15 + sy * 1.55, -4.45), (0.8, 0.8, 0.6), "frame", rot=(0, 0, 45))
    cbox(c, (0, 20.15, -4.68), (3.5, 0.26, 0.26), "iron")
    gl = s.fx("glow", "core", c, pivot=(0, 20.15, -4.65))
    ring(gl, (0, 20.15, -4.55), 2.2, 8, (0, 0.3, 0.3), "glow", axis="z")
    # 脇: 錆色の板と排気口
    fl = cbox(c, (-5.55, 20.7, 0.4), (0.5, 4.0, 3.8), "plate2")
    fv = cbox(c, (-5.85, 20.7, 0.4), (0.15, 2.8, 2.6), "vent")
    mirror_x(c, fl, fv)


# ---------------------------------------------------------------------------
#  背中（背板・炉のバックパック・煙突・双発の大ノズル）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "reactor", "body")
    cbox(bk, (0, 18.9, 3.6), (9.0, 9.8, 0.7), "steel_b")                 # 背板
    cbox(bk, (0, 18.6, 4.15), (2.4, 8.6, 0.8), "frame")                  # 背骨
    bevel(bk, (0, 19.7, 5.15), (6.6, 6.8, 2.6), "plate", cut=0.8, axis="z")   # 炉
    rbox(bk, (0, 23.25, 4.75), (5.6, 1.1, 2.6), "plate2", rot=(25, 0, 0))
    cbox(bk, (0, 16.55, 6.48), (4.6, 1.0, 0.2), "hazard")
    for y in (20.9, 19.4):                                              # 炉の格子（橙に光る）
        cbox(bk, (0, y, 6.5), (3.8, 0.9, 0.2), "vent")
    side = cbox(bk, (-3.38, 19.7, 5.15), (0.3, 4.6, 1.8), "plate2")
    mirror_x(bk, side)
    # 煙突（右。肩の後ろから上へ、先が赤熱）
    st = s.part("back", "stack_r", bk, pivot=(-3.3, 21.5, 5.6), rotation=(-10, 0, 8))
    octa(st, (-3.3, 23.2, 5.6), 1.5, 3.8, "frame", axis="y")
    octa(st, (-3.3, 22.0, 5.6), 1.8, 0.5, "brass", axis="y")
    octa(st, (-3.3, 25.0, 5.6), 1.9, 0.7, "steel", axis="y")
    cbox(st, (-3.3, 25.4, 5.6), (1.2, 0.15, 1.2), "ember")
    # 大ノズル（右。下後ろへ向ける）
    th = s.part("back", "thruster_r", bk, pivot=(-2.0, 16.6, 5.6), rotation=(18, 0, -8))
    octa(th, (-2.0, 15.4, 5.6), 2.4, 2.6, "plate2", axis="y")
    octa(th, (-2.0, 16.4, 5.6), 2.6, 0.45, "brass", axis="y")
    octa(th, (-2.0, 13.55, 5.6), 3.1, 1.3, "iron", axis="y")
    ring(th, (-2.0, 12.88, 5.6), 1.2, 8, (0, 0.28, 0.3), "glow", axis="y")
    cbox(th, (-2.0, 12.86, 5.6), (2.2, 0.2, 2.2), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-2.0, 12.8, 5.6))
    taper(fx, (-2.0, 12.8, 5.6), (-2.0, 5.2, 5.6), 2.5, 0.5, 3, "flame")
    taper(fx, (-2.0, 12.75, 5.6), (-2.0, 8.6, 5.6), 1.1, 0.3, 2, "flame_core", round_=False)


# ---------------------------------------------------------------------------
#  腕（上腕・肘のトゲ・排気口の篭手・鋲の拳）
# ---------------------------------------------------------------------------
def arms(s):
    ar = s.part("arms", "upper_r", "rightArm", pivot=(ARM_X, 20.0, 0))
    bevel(ar, (-6.0, 20.4, 0.0), (5.6, 5.8, 5.9), "steel", cut=0.6, axis="y")
    cbox(ar, (-6.0, 17.95, 0.0), (5.9, 0.8, 6.2), "plate2")              # 腕章
    cbox(ar, (-6.0, 17.95, 0.0), (6.0, 0.24, 6.3), "brass")
    op = rbox(ar, (-8.95, 19.9, 0.0), (0.6, 3.0, 4.0), "plate", rot=(0, 0, 4))
    line_on(ar, op, "west", (0.5, 0.12), (0.5, 0.88), 0.26, 0.2, "glow")
    el = s.part("arms", "elbow_r", "rightArm", pivot=(ARM_X, 16.8, 0))
    cbox(el, (-6.0, 16.9, 0.0), (5.4, 1.5, 5.4), "frame")
    octa(el, (-8.55, 16.9, 0.2), 1.9, 0.5, "iron", axis="x")
    bevel(el, (-6.2, 17.0, 2.95), (3.4, 2.4, 1.0), "plate", cut=0.4, axis="z")   # 肘当て
    taper(el, (-6.2, 17.0, 3.4), (-6.4, 16.6, 4.8), 1.1, 0.45, 2, "iron", round_=False)
    # 前腕: 手首へ開く篭手。外の板に橙の排気口、後ろに排気管
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=(ARM_X, 15.0, 0))
    cbox(fa, (-6.0, 14.65, 0), (5.3, 3.5, 5.5), "plate")
    ob = rbox(fa, (-8.95, 14.6, 0), (0.9, 3.6, 5.2), "plate2", rot=(0, 0, 7))
    stick(fa, ob, "west", 0.42, 0.5, (2.4, 2.4, 0.3), "vent", sink=0.12)
    stick(fa, ob, "west", 0.88, 0.5, (0.5, 2.8, 0.2), "hazard", sink=0.05)
    rbox(fa, (-6.15, 14.6, -2.95), (4.2, 3.3, 0.7), "plate2", rot=(-8, 0, 0))
    rbox(fa, (-6.15, 14.6, 2.95), (4.2, 3.3, 0.7), "steel_b", rot=(8, 0, 0))
    octa(fa, (-8.0, 15.1, 3.35), 0.9, 2.6, "iron", axis="y", rot=(-20, 0, 0),
         pivot=(-8.0, 15.1, 3.35))
    cbox(fa, (-8.0, 16.45, 3.8), (0.7, 0.2, 0.7), "ember")
    cbox(fa, (-6.0, 12.8, 0), (5.7, BRASS_W, 5.9), "brass")
    # 拳: 甲の板・鉄の鋲・指・親指
    h = s.part("arms", "gauntlet_r", "rightArm", pivot=(ARM_X, 13.2, 0))
    cbox(h, (-6.0, 11.95, 0.0), (5.4, 2.6, 5.6), "steel")
    rbox(h, (-6.0, 12.45, -3.0), (4.8, 1.4, 0.8), "plate", rot=(-10, 0, 0))
    for i in range(4):
        x = -7.65 + i * 1.1
        cbox(h, (x, 12.5, -3.5), (0.72, 0.72, 0.45), "iron")
        rbox(h, (x, 11.3, -2.95), (0.9, 1.3, 0.65), "frame", rot=(20, 0, 0))
    rbox(h, (-3.15, 12.0, -1.3), (0.6, 1.8, 1.4), "steel_b", rot=(0, 0, -10))


# ---------------------------------------------------------------------------
#  肩（三段に重ねた巨大な肩当て・鈍い三本のトゲ）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    dome = bevel(p, (-7.5, 24.3, 0.0), (7.2, 3.8, 8.8), "plate", cut=1.3, axis="x",
                 rot=(0, 0, -14))
    top = stick(p, dome[0], "up", 0.45, 0.5, (4.6, 6.4, 0.55), "plate2", sink=0.15)
    stick(p, top, "west", 0.5, 0.5, (6.4, 0.5, 0.25), "brass", sink=0.05)
    # 外の縁（上・外へ反る）
    rim = rbox(p, (-11.1, 24.05, 0.0), (0.9, 2.6, 9.0), "plate2", rot=(0, 0, -30))
    stick(p, rim, "up", 0.5, 0.5, (0.9, 9.0, 0.3), "brass", sink=0.05)
    # 垂れる三段の板
    l1 = rbox(p, (-10.95, 21.95, 0.0), (1.1, 2.8, 8.4), "plate", rot=(0, 0, 20))
    stick(p, l1, "west", 0.5, 0.04, (8.0, BRASS_W, 0.22), "brass", sink=0.05)
    line_on(p, l1, "west", (0.1, 0.6), (0.9, 0.6), 0.26, 0.2, "glow")
    l2 = rbox(p, (-11.35, 20.1, 0.1), (1.0, 2.3, 7.6), "plate2", rot=(0, 0, 15),
              decals={"west": {"decal": "hazard", "c1": OCHRE, "c2": (44, 36, 34)}})
    stick(p, l2, "west", 0.5, 0.05, (7.2, BRASS_W, 0.22), "brass", sink=0.05)
    rbox(p, (-11.45, 18.55, 0.1), (0.9, 1.7, 6.6), "plate", rot=(0, 0, 11))
    # 鈍いトゲ（上外へ。真ん中が長い。真鍮の座金の上に四角錐）
    for z, k in ((-2.7, 0.8), (0.0, 1.0), (2.7, 0.8)):
        base = (-9.1, 25.9, z)
        tip = (-10.2 - 1.1 * k, 26.5 + 2.4 * k, z * 1.1)
        octa(p, base, 2.1, 0.6, "brass", axis="y")
        taper(p, base, tip, 2.0, 0.55, 2, "iron", round_=False)
    # 前後の当て板
    fr = rbox(p, (-7.6, 23.6, -4.65), (5.2, 2.6, 0.8), "plate2", rot=(-14, 0, -12))
    stick(p, fr, "north", 0.5, 0.5, (3.4, 0.4, 0.2), "glow", sink=0.05)
    rbox(p, (-7.6, 23.6, 4.65), (5.2, 2.6, 0.8), "plate2", rot=(14, 0, -12))


# ---------------------------------------------------------------------------
#  兜（ドーム・眉庇・コリント式の頬当て・T 字のバイザー・しころ・横向きの扇の鶏冠）
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 31.15, 0.2), (10.0, 4.7, 10.2), "plate", cut=1.0, axis="z")
    rbox(hm, (0, 32.15, -4.95), (8.8, 2.4, 0.8), "plate", rot=(-32, 0, 0))     # 額の斜面
    rbox(hm, (0, 32.0, 5.35), (8.8, 2.4, 0.8), "plate", rot=(32, 0, 0))        # 後ろの斜面
    # 重い眉庇（中央で下がる V）と真鍮の縁
    br = rbox(hm, (-2.4, 29.75, -5.25), (5.0, 1.5, 1.3), "plate2", rot=(-16, 8, 9))
    brt = stick(hm, br, "down", 0.5, 0.8, (4.8, 0.35, 0.2), "brass", sink=0.05)
    mirror_x(hm, br, brt)
    # 顔: 暗い奥の板 → コリント式の頬当て（中央に縦の隙間を残して前で絞る）
    cbox(hm, (0, 26.2, -4.75), (8.4, 5.2, 0.5), "frame")
    ck = rbox(hm, (-2.55, 25.85, -5.15), (4.1, 4.2, 1.0), "plate", rot=(0, 20, 0))
    ckt = stick(hm, ck, "north", 0.5, 0.94, (3.8, BRASS_W, 0.2), "brass", sink=0.05)
    mirror_x(hm, ck, ckt)
    rbox(hm, (0, 23.95, -5.0), (3.6, 1.0, 1.4), "plate2", rot=(-30, 0, 0))     # 顎
    # 側板・耳の円盤（鶏冠の付け根）
    sd = cbox(hm, (-5.0, 27.6, 0.5), (0.9, 5.6, 8.6), "plate2")
    ear = octa(hm, (-5.55, 28.6, 0.4), 2.9, 0.6, "iron", axis="x")
    eg = octa(hm, (-5.9, 28.6, 0.4), 1.2, 0.3, "glow", axis="x")
    mirror_x(hm, sd, ear, eg)
    # 後頭部としころ（外へ広がる）
    cbox(hm, (0, 27.3, 5.05), (9.0, 5.0, 0.8), "plate",
         decals={"south": {"decal": "serial", "text": "AR-04", "ink": (236, 170, 96), "y": 0.7}})
    rbox(hm, (0, 24.4, 5.55), (9.4, 2.2, 0.9), "plate2", rot=(25, 0, 0))
    rbox(hm, (0, 22.95, 6.05), (8.8, 1.6, 0.8), "plate2_b", rot=(40, 0, 0))
    # 横向きの扇の鶏冠（耳から耳へ）: 真紅と暗い真紅の羽板・先に溶岩の縁・根元に真鍮のレール
    cr = s.part("helmet", "crest", hm, pivot=(0, 33.4, 0.4))
    C = (0.0, 28.4, 0.4)
    n = 13
    for i in range(n):
        a = -60.0 + 120.0 * i / (n - 1)
        r0 = 5.1
        r1 = 9.6 - 2.2 * (a / 60.0) ** 2
        t = math.radians(a)
        d = (-math.sin(t), math.cos(t))
        rm = (r0 + r1) / 2
        dz = 0.12 if i % 2 else -0.12
        cen = (C[0] + d[0] * rm, C[1] + d[1] * rm, C[2] + dz)
        rbox(cr, cen, (1.85, r1 - r0, 1.1), "plate" if i % 2 == 0 else "plate_b", rot=(0, 0, a))
        tip = (C[0] + d[0] * (r1 - 0.1), C[1] + d[1] * (r1 - 0.1), C[2] + dz)
        rbox(cr, tip, (1.95, 0.4, 1.22), "glow_hot", rot=(0, 0, a))
    ring(cr, C, 5.3, 10, (0, 0.6, 1.5), "brass", axis="z", a0=-64, a1=64)
    # バイザー: 横の目の帯 + 縦の口の帯 = T 字
    vz = s.part("visor", "tslit", "head")
    fg = s.fx("glow", "visor", vz, pivot=(0, 27.4, -5.05))
    cbox(fg, (0, 28.5, -5.05), (7.0, 0.9, 0.3), "visor")
    cbox(fg, (0, 26.0, -5.05), (0.95, 4.2, 0.3), "visor")


# ---------------------------------------------------------------------------
#  衛星（背中の後ろの傾いた軌道。フォボス = 内側で速い芋形 / ダイモス = 外側で遅い小さく滑らか）
# ---------------------------------------------------------------------------
def moons(s):
    C = (0.0, 21.5, 10.0)
    orr = s.part("extra", "orrery", "body", pivot=C, rotation=(-10, 0, 0))
    # フォボス: いびつに重ねた岩・真鍮の帯・橙の目（子機）
    sp = s.fx("spin", "phobos", orr, pivot=C)
    M = (C[0] - 5.0, C[1], C[2])
    roll = s.fx("spin", "phobos_roll", sp, pivot=M)
    cbox(roll, M, (3.2, 2.3, 2.4), "phobos")
    rbox(roll, (M[0] + 0.75, M[1] + 0.4, M[2] - 0.25), (2.1, 2.1, 2.0), "phobos", rot=(20, 35, 10))
    rbox(roll, (M[0] - 0.95, M[1] - 0.3, M[2] + 0.3), (1.8, 1.7, 1.9), "phobos", rot=(-15, 20, 30))
    rbox(roll, (M[0] - 0.25, M[1] + 0.8, M[2] + 0.35), (1.4, 1.1, 1.4), "phobos", rot=(10, 45, 0))
    cbox(roll, (M[0], M[1] - 0.1, M[2]), (3.35, 0.36, 2.55), "brass")
    octa(roll, (M[0] - 1.7, M[1] - 0.1, M[2]), 0.9, 0.3, "glow", axis="x")
    # ダイモス: 小さく丸い岩・アンテナ
    sp2 = s.fx("spin", "deimos", orr, pivot=C)
    M2 = (C[0] + 7.2, C[1], C[2])
    roll2 = s.fx("spin", "deimos_roll", sp2, pivot=M2)
    cbox(roll2, M2, (1.9, 1.9, 1.9), "deimos")
    rbox(roll2, M2, (1.75, 1.75, 1.75), "deimos", rot=(45, 0, 45))
    rbox(roll2, M2, (1.7, 1.7, 1.7), "deimos", rot=(0, 45, 0))
    taper(roll2, (M2[0], M2[1] + 0.9, M2[2]), (M2[0] + 0.35, M2[1] + 2.0, M2[2]), 0.24, 0.12, 1,
          "iron", round_=False)
    cbox(roll2, (M2[0] + 0.35, M2[1] + 2.05, M2[2]), (0.32, 0.32, 0.32), "glow")
