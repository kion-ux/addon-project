# -*- coding: utf-8 -*-
"""火星 — 軍神機装 アレス（Ares Frame）。v1.1: 7 頭身の重装の戦神。

全形態でいちばん重い人型の装甲。frame7 の暗い機械の骨格の上に、黒い鉄（steel）の下地・真紅（plate）と
錆色（plate2）の厚い多層の板・真鍮（brass）の縁と鋲・鈍い鉄（iron）のトゲ、橙に光る排気口と溶岩のひび（glow）。
装甲には擦り傷・欠け・赤い砂ぼこり（このファイルで足す塗りの kind "ares"）。7 頭身でも肩幅の広い逆三角形の戦士。

  兜      スパルタ風の小さな兜: 耳から耳へ渡る横向きの扇の鶏冠（15 枚の羽板・先が溶岩色・真鍮の櫛）・
          重い V の眉庇・前へ絞ったコリント式の頬当て・橙に光る T 字のバイザー・外へ開くしころ・耳の円盤
  肩      三段に垂れる肩当て（真紅・錆・真紅、真鍮の縁と鋲・警告ストライプ・紋章）と、上外へ突き出す鈍い二本の角
  胴      黒い鉄の胸郭・溶岩のひびが走る真紅の胸板・鉄の桟の籠に収めた火星の星核（脈打つ光の輪）・高い襟・
          脇の排気口・段の腹当て
  腰      真鍮の鋲のベルトと紋章の留め金・警告ストライプの前垂れ・腰の脇の板・三段の草摺・後ろ垂れ
  腕      錆色の二の腕・肘の鈍いトゲ・外に排気口と排気管の付いた重い篭手・鋲の拳（指の甲当て）
  脚      腿の多層の板（型番）・鈍いトゲの膝当てと外の油圧シリンダー・V の稜と溶岩の線の脛当て・
          ふくらはぎの排気口・段のつま先の鉄靴と踵の噴射（fx_thrust）
  背      炉のバックパック（回るタービン fx_spin・炉の光）・二本の煙突（先が赤熱 fx_glow）・
          下後ろへ向く双発の大ノズル（fx_thrust）・蛇腹のホース
  衛星    背中の後ろの傾いた軌道を回る二つの子機: フォボス（いびつな芋形・速い内側の軌道）と
          ダイモス（小さく滑らか・遅い外側の軌道）。どちらも fx_spin（v.astro_spin で空中・疾走で速まる）

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A（7 頭身の目安）。
右側だけ作り `_r` を付ける → 左は自動で鏡映。回転（統合版の rotation）: rx 正 = 上端が前へ /
ry 正 = 正面が右（-X）を向く / rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

import math
import random

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, layered_plate,  # noqa: F401
                        line_on, mirror_x, octa, piston, polyline, rbox, ring, rivets, rod,
                        sensor, stick, taper, vents)

LX = A.LEG_X                     # 脚の軸 -2.15
BW = 0.26                        # 真鍮の縁の幅

# ---------------------------------------------------------------------------
#  色
# ---------------------------------------------------------------------------
CRIMSON = (196, 58, 34)
RUST = (146, 74, 44)
IRON = (40, 34, 34)
OCHRE = (217, 137, 58)
DUST = (166, 104, 66)            # 火星の赤い砂ぼこり
STEEL = (82, 72, 72)             # 黒い鉄の下地の装甲
GLOW = (255, 122, 42)
HAZ = {"decal": "hazard", "c1": OCHRE, "c2": (44, 36, 34)}


# ===========================================================================
#  塗りの追加: kind "ares"（擦り傷・欠け・砂ぼこりの付いた装甲）と "ares_rock"（衛星の岩肌）
#  astro_paint.AstroPainter に k_/p_ のメソッドを足すだけ（既存の kind は変えない）。
#  weapon.py も同じものを使う（install_painter() を呼ぶ）。乱数は面ごとの seed で決まる（決定的）。
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


BRASS = {"kind": "trim", "base": (198, 134, 62), "light": (255, 214, 150), "dark": (112, 64, 26),
         "line": (58, 32, 12)}

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
    "brass": dict(BRASS),
    "gold": dict(BRASS),
    "rivet": {"kind": "trim", "base": (150, 134, 124), "light": (240, 226, 210), "dark": (72, 60, 56),
              "line": (30, 24, 22), "bevel": False},
    "rivet_b": {"kind": "trim", "base": (210, 150, 74), "light": (255, 226, 168),
                "dark": (118, 70, 30), "line": (60, 34, 12), "bevel": False},
    # 骨格（frame7）の金属も火星の温かい鉄に
    "frame": {"kind": "frame", "base": (62, 54, 54), "light": (110, 98, 94), "line": (22, 18, 18)},
    "frame_lt": {"kind": "frame", "base": (98, 86, 82), "light": (150, 136, 128), "line": (30, 24, 24)},
    "dark": {"kind": "frame", "base": (36, 30, 30), "ribs": 0, "line": (14, 10, 10)},
    "chrome": {"kind": "chrome", "base": (168, 156, 150), "light": (236, 226, 214), "line": (40, 32, 30)},
    "visor": {"glow": (255, 140, 50), "light": (255, 236, 196), "deep": (150, 34, 8), "emit": 20},
    "flame": {"glow": (255, 116, 36), "light": (255, 238, 186), "deep": (190, 36, 8)},
    "flame_core": {"kind": "flame", "glow": (255, 214, 120), "light": (255, 255, 236),
                   "deep": (255, 120, 40), "bevel": False, "outline": False},
    "thruster": {"glow": (255, 130, 44), "light": (255, 236, 190), "deep": (150, 30, 8)},
    # 後ろ（south）を向いた炉・噴射口（thruster は既定で下の面だけ光る）
    "furnace": {"kind": "thruster", "base": (62, 54, 54), "glow": (255, 130, 44),
                "light": (255, 236, 190), "deep": (150, 30, 8), "line": (22, 18, 18),
                "bevel": False, "faces": ("south",)},
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
#  部位アニメ（Molang）。回る物は v.astro_spin（空中・疾走で速まる累積の位相）、揺れは v.astro_t。
#  q.anim_time を使う時は 30°/秒の倍数（12 秒のループ）。`_r` は左へ自動で鏡映
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        # フォボスは速く（4 秒で一周）、ダイモスはゆっくり（12 秒で一周）。どちらも自分でも転がる
        "fx_spin_phobos": {"rotation": [0, 0, "v.astro_spin * 90.0"]},
        "fx_spin_phobos_roll": {"rotation": ["v.astro_spin * 120.0", "v.astro_spin * 60.0", 0]},
        "fx_spin_deimos": {"rotation": [0, 0, "v.astro_spin * 30.0 + 150.0"]},
        "fx_spin_deimos_roll": {"rotation": [0, "v.astro_spin * 90.0", "v.astro_spin * 30.0"]},
        "extra_orrery": {"position": [0, "math.sin(v.astro_t * 60.0) * 0.3", 0]},
        # 炉のタービン
        "fx_spin_rotor": {"rotation": [0, 0, "v.astro_spin * 240.0"]},
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
    # 鉄靴が足を包むので骨格の足は省く。背骨の脇のケーブルは炉の陰なので省く
    s.frame7(skip=("foot", "cables"), bulk=1.05)
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    arms(s)
    hands(s)
    shoulders(s)
    helmet(s)
    moons(s)


# ---------------------------------------------------------------------------
#  鉄靴（段のつま先・踵の噴射口・足首の外の板）
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "sabaton_r", "rightLeg")
    cbox(b, (LX, 0.17, -1.2), (3.05, 0.34, 6.0), "frame")                        # 厚い靴底
    cbox(b, (LX, 0.4, -1.2), (3.12, 0.16, 6.05), "brass")                        # 靴底の縁
    shell = bevel(b, (LX, 1.15, -0.55), (2.95, 1.5, 4.0), "steel", cut=0.42, axis="z")
    line_on(b, shell[0], "west", (0.15, 0.4), (0.88, 0.4), 0.18, 0.16, "glow")
    rivets(b, shell[0], "west", 2, edge="top", margin=0.3, span=(0.25, 0.75))
    # 段のつま先（三枚が重なって下る）
    rbox(b, (LX, 1.95, -1.95), (2.4, 0.5, 1.8), "plate", rot=(-30, 0, 0))
    t2 = rbox(b, (LX, 1.2, -2.95), (2.75, 0.9, 1.05), "plate2", rot=(-18, 0, 0))
    stick(b, t2, "north", 0.5, 0.12, (2.6, BW, 0.16), "brass", sink=0.05)
    cbox(b, (LX, 0.66, -3.5), (2.4, 0.3, 0.3), "dark")
    rbox(b, (LX, 0.64, -3.88), (2.6, 0.72, 0.85), "plate", rot=(-26, 0, 0))
    cbox(b, (LX, 0.33, -4.32), (2.25, 0.42, 0.36), "iron")                       # つま先の鉄
    # 踵: 錆色の板・噴射口・小さな炎
    hl = cbox(b, (LX, 1.15, 1.3), (2.65, 1.6, 0.95), "plate2")
    stick(b, hl, "up", 0.5, 0.5, (2.4, 0.7, 0.16), "hazard", sink=0.05)
    octa(b, (LX, 0.85, 1.92), 1.3, 0.5, "iron", axis="z")
    cbox(b, (LX, 0.85, 2.2), (0.95, 0.95, 0.16), "furnace")
    fx = s.fx("thrust", "heel_r", b, pivot=(LX, 0.85, 2.3), rotation=(-70, 0, 0))
    taper(fx, (LX, 0.85, 2.3), (LX, -1.35, 2.3), 0.8, 0.22, 2, "flame")
    # 足首の外を守る板（ドラムは見せる）と甲の光る継ぎ目
    ag = rbox(b, (LX - 1.52, 2.45, 0.9), (0.32, 1.1, 1.3), "plate2", rot=(0, 0, -6))
    rivets(b, ag, "west", 2, edge="bottom", margin=0.25, span=(0.3, 0.7), size=0.22)
    cbox(b, (LX - 1.49, 1.25, -1.6), (0.16, 0.5, 1.4), "hazard")


# ---------------------------------------------------------------------------
#  脚（腿・膝・脛）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前の多層の板（錆 → 真紅・真鍮の下縁・鋲・溶岩の線）・外の型番の板・後ろは骨格を見せる
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.6, -1.88), (2.95, 4.2, 0.6), "plate2", top="plate",
                       rot=(-3, 0, 0), inset=0.3, trim="brass", trim_edge="bottom",
                       rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(t, fr["top"], "north", (0.24, 0.12), (0.3, 0.55), 0.18, 0.16, "glow")
    line_on(t, fr["top"], "north", (0.3, 0.55), (0.16, 0.86), 0.18, 0.16, "glow")
    side = rbox(t, (LX - 1.8, 11.3, 0.05), (0.5, 3.1, 2.9), "plate2", rot=(0, 0, -3),
                decals={"west": {"decal": "serial", "text": "AR4", "ink": (236, 170, 96)}})
    rivets(t, side, "west", 3, edge="bottom", margin=0.3, size=0.22)
    cbox(t, (LX - 1.66, 9.62, 0.05), (0.42, 0.4, 2.7), "brass")
    rbox(t, (LX + 1.5, 11.0, -0.35), (0.36, 2.6, 2.0), "steel_b", rot=(0, 0, 3))
    # 腿の裏の錆の板（膝裏のピストンの上。鋲）
    hb = rbox(t, (LX - 0.1, 11.05, 1.62), (2.4, 2.8, 0.42), "plate2_b", rot=(4, 0, 0))
    rivets(t, hb, "south", 2, edge="bottom", margin=0.25, span=(0.3, 0.7), size=0.2)
    # 膝: 鈍いトゲの付いた真紅の膝当て・上の錆の庇・外の油圧シリンダー
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    kg = bevel(k, (LX, 8.4, -1.9), (2.45, 2.3, 0.8), "plate", cut=0.4, axis="z")
    rbox(k, (LX, 9.6, -1.72), (2.1, 0.75, 0.75), "plate2", rot=(30, 0, 0))
    stick(k, kg[0], "north", 0.5, 0.06, (2.0, BW, 0.18), "brass", sink=0.05)
    rivets(k, kg[0], "north", 2, edge="top", margin=0.3, span=(0.15, 0.85), size=0.22)
    octa(k, (LX, 8.4, -2.36), 1.25, 0.3, "brass", axis="z")
    taper(k, (LX, 8.45, -2.4), (LX, 9.25, -3.35), 0.95, 0.4, 2, "iron", style_r="steel")
    cbox(k, (LX, 9.3, -3.4), (0.36, 0.36, 0.36), "iron")
    piston(k, (LX - 1.65, 10.9, 0.55), (LX - 1.52, 6.3, 0.45), r=0.27, style="frame",
           rod_style="chrome", cap_style="dark")
    # 脛: 前の真紅の板・黒い鉄の V の稜（溶岩の線）・両脇の錆の板・ふくらはぎの排気口・前へ反る裾
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 4.75, -1.45), (2.85, 5.0, 0.55), "plate", rot=(4, 0, 0))
    keel = rbox(g, (LX - 0.38, 4.95, -1.8), (0.8, 4.0, 0.48), "steel", rot=(4, 24, 0))
    mirror_x(g, keel, about=LX)
    gl = s.fx("glow", "shin_r", g, pivot=(LX, 4.9, -2.1))
    cbox(gl, (LX, 4.95, -2.08), (0.24, 3.6, 0.2), "glow_hot", rotation=(4, 0, 0))
    sd = rbox(g, (LX - 1.48, 4.85, -0.1), (0.45, 4.8, 2.75), "plate2", rot=(0, 0, -4),
              decals={"west": dict(HAZ, band="bottom")})
    sdr = rivets(g, sd, "west", 2, edge="top", margin=0.3, span=(0.25, 0.75), size=0.22)
    mirror_x(g, sd, sdr, about=LX)
    calf = rbox(g, (LX, 6.1, 1.62), (2.35, 2.6, 0.48), "plate_b", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.22, 0.18, 0.78, 0.82), axis="v", w=0.24)
    stick(g, calf, "south", 0.5, 0.97, (2.1, BW, 0.16), "brass", sink=0.05)
    lip = rbox(g, (LX, 2.55, -1.62), (2.95, 0.8, 0.5), "plate2", rot=(-22, 0, 0))
    stick(g, lip, "north", 0.5, 0.15, (2.8, BW, 0.16), "brass", sink=0.05)


# ---------------------------------------------------------------------------
#  腰（鋲のベルト・紋章の留め金・前垂れ・腰の脇の板・三段の草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    belt = chamfer(w, (0, 16.95, 0.12), (6.9, 1.0, 4.6), "frame", cut=0.4, axis="y")
    bl = rivets(w, belt[0], "north", 3, edge="bottom", margin=0.5, span=(0.08, 0.3),
                style="rivet_b", size=0.3)
    mirror_x(w, bl)
    chamfer(w, (0, 16.95, -2.42), (2.1, 1.45, 0.5), "brass", cut=0.3, axis="z")    # 留め金
    cbox(w, (0, 16.95, -2.72), (1.3, 1.05, 0.16), "emblem")                       # 火星の紋章
    # 前垂れ（細い警告ストライプの板。腿の前を隠さない幅）と真鍮の裾
    fp = rbox(w, (0, 15.15, -2.1), (1.8, 2.6, 0.48), "hazard", rot=(-8, 0, 0))
    stick(w, fp, "north", 0.5, 0.06, (1.7, BW, 0.18), "brass", sink=0.05)
    fr_ = rivets(w, fp, "north", 2, edge="top", margin=0.25, span=(0.2, 0.8), size=0.22)
    # 腰の脇の真紅の板（股関節の前を覆う）
    hp = rbox(w, (-2.35, 15.8, -2.0), (2.1, 1.45, 0.45), "plate", rot=(-8, 14, 4))
    hpr = rivets(w, hp, "north", 2, edge="top", margin=0.28, span=(0.25, 0.75), size=0.22)
    mirror_x(w, hp, hpr)
    # 後ろ垂れ（真紅 → 錆の二段）
    rs = rbox(w, (0, 15.1, 2.45), (4.6, 2.5, 0.5), "plate", rot=(14, 0, 0))
    rivets(w, rs, "south", 3, edge="top", margin=0.3, span=(0.2, 0.8), size=0.22)
    r2 = rbox(w, (0, 13.85, 2.85), (3.6, 0.9, 0.45), "plate2", rot=(20, 0, 0))
    stick(w, r2, "south", 0.5, 0.12, (3.4, BW, 0.16), "brass", sink=0.05)
    _ = fr_
    # 三段の草摺（腰の横。付け根で外へ開く。下の段ほど外へ）
    # 腿の外の装甲（y 12.85 まで）の上で終わり、篭手の内側（x -4.5）より内に収める
    ts = s.part("waist", "tasset_r", w, pivot=(-3.3, 16.6, 0.0), rotation=(0, 0, 7))
    t1 = layered_plate(ts, (-3.58, 15.6, 0.0), (0.45, 1.9, 3.5), "plate", top="steel",
                       face="west", inset=0.32, trim="brass", trim_edge="bottom",
                       rivet="rivet", n_rivets=3, rivet_edge="top")
    _ = t1
    t2 = rbox(ts, (-3.78, 14.6, 0.05), (0.42, 1.3, 3.25), "plate2", rot=(0, 0, 4))
    stick(ts, t2, "west", 0.5, 0.1, (3.2, BW, 0.16), "brass", sink=0.05)
    line_on(ts, t2, "west", (0.12, 0.6), (0.88, 0.6), 0.16, 0.16, "glow")
    t3 = rbox(ts, (-3.92, 13.75, 0.1), (0.4, 0.75, 2.9), "plate", rot=(0, 0, 8))
    rivets(ts, t3, "west", 2, edge="bottom", margin=0.2, span=(0.25, 0.75), size=0.2,
           style="rivet_b")
    cbox(ts, (-3.38, 16.3, 0.0), (0.5, 0.55, 1.6), "dark")                        # 蝶番


# ---------------------------------------------------------------------------
#  胴（黒い鉄の胸郭・真紅の胸板と溶岩のひび・籠に収めた火星の星核・襟・脇の排気口・腹の板）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.25, 0.0), (9.5, 3.5, 5.15), "steel", cut=0.85, axis="y")   # 上が広い
    bevel(c, (0, 21.65, -0.05), (7.3, 2.3, 4.7), "steel_b", cut=0.7, axis="y")
    sl = rbox(c, (-3.95, 22.2, 0.0), (0.5, 2.9, 4.1), "steel", rot=(0, 0, -24))     # 脇の斜面
    mirror_x(c, sl)
    # 真紅の胸板: 外へ開き、内側の端が前へ、下辺が中央へ（錆の上板・真鍮の上縁・溶岩のひび・鋲）
    pec = rbox(c, (-2.6, 24.2, -2.72), (3.8, 2.6, 0.6), "plate", rot=(6, 17, 9))
    pt = stick(c, pec, "north", 0.5, 0.94, (3.65, BW, 0.18), "brass", sink=0.05)
    k1 = line_on(c, pec, "north", (0.96, 0.3), (0.72, 0.46), 0.2, 0.16, "glow")
    k2 = line_on(c, pec, "north", (0.72, 0.46), (0.6, 0.78), 0.18, 0.16, "glow")
    k3 = line_on(c, pec, "north", (0.72, 0.46), (0.38, 0.38), 0.18, 0.16, "glow")
    k4 = line_on(c, pec, "north", (0.38, 0.38), (0.16, 0.62), 0.16, 0.16, "glow_hot")
    pr = rivets(c, pec, "north", 3, edge="bottom", margin=0.24, span=(0.15, 0.85), size=0.22)
    low = rbox(c, (-1.95, 21.95, -2.45), (3.3, 1.5, 0.55), "plate2", rot=(-8, 12, 12))
    mirror_x(c, pec, pt, k1, k2, k3, k4, pr, low)
    # 胸の中央の稜（錆）: 胸板の間を縦に通り、下の星核へ
    kl = rbox(c, (0, 25.0, -2.92), (1.15, 2.2, 0.5), "plate2", rot=(-8, 0, 0))
    stick(c, kl, "north", 0.5, 0.5, (0.26, 1.9, 0.16), "brass", sink=0.06)
    # 星核: 黒い菱形の台 → 鉄の八角の枠 → 真鍮の輪 → 火星 → 四隅の爪 → 鉄の桟の籠 → 脈打つ光の輪
    CY, CZ = 22.75, -2.75
    rbox(c, (0, CY, CZ), (2.9, 2.9, 0.5), "dark", rot=(0, 0, 45))
    octa(c, (0, CY, CZ - 0.25), 2.6, 0.36, "iron", axis="z")
    octa(c, (0, CY, CZ - 0.5), 2.25, 0.26, "brass", axis="z")
    cbox(c, (0, CY, CZ - 0.45), (1.8, 1.8, 0.7), "core")
    for sx in (-1, 1):
        for sy in (-1, 1):
            rbox(c, (sx * 1.0, CY + sy * 1.0, CZ - 0.78), (0.42, 0.42, 0.36), "brass",
                 rot=(0, 0, 45))
    for k_ in (-0.52, 0.52):                     # 籠の桟（# 字。真ん中の窓から火星が見える）
        cbox(c, (k_, CY, CZ - 0.92), (0.18, 1.9, 0.18), "iron")
        cbox(c, (0, CY + k_, CZ - 0.96), (1.9, 0.18, 0.18), "iron")
    gl_ = s.fx("glow", "core", c, pivot=(0, CY, CZ - 0.7))
    ring(gl_, (0, CY, CZ - 0.7), 1.45, 10, (0, 0.24, 0.24), "glow", axis="z")
    # 高い襟（錆の板 + 真紅の上板 + 真鍮）と喉の板
    col = rbox(c, (-1.85, 26.35, 0.3), (1.5, 1.45, 3.7), "plate2", rot=(0, 0, -22))
    colt = stick(c, col, "up", 0.5, 0.5, (1.15, 3.4, 0.2), "plate", sink=0.06)
    colg = stick(c, col, "west", 0.5, 0.06, (3.5, BW, 0.18), "brass", sink=0.05)
    colr = rivets(c, col, "west", 2, edge="top", margin=0.3, span=(0.3, 0.7), size=0.2)
    cf = rbox(c, (-0.95, 25.95, -1.98), (1.6, 0.9, 0.45), "plate", rot=(-20, 30, -10))
    mirror_x(c, col, colt, colg, colr, cf)
    sensor(c, (-1.45, 25.25, -2.68), 0.24, "glow", "dark")
    sensor(c, (1.45, 25.25, -2.68), 0.24, "glow", "dark")
    # 肩の付け根（肩当ての下）と脇の排気口
    yk = rbox(c, (-3.95, 25.95, 0.0), (2.0, 0.55, 3.5), "plate_b", rot=(0, 0, -8))
    sv = cbox(c, (-4.45, 23.55, 0.35), (0.4, 2.0, 2.4), "plate2")
    svv = vents(c, sv, "west", 3, box=(0.2, 0.25, 0.8, 0.75), axis="v", w=0.22)
    mirror_x(c, yk, sv, svv)
    _ = up
    # 背中の肩甲骨の板（錆。真鍮の上縁・鋲・排気スリット）: 炉の両脇の黒い鉄を埋める
    sc_ = rbox(c, (-3.5, 24.15, 2.82), (2.1, 2.5, 0.45), "plate2", rot=(8, -14, 0))
    scg = stick(c, sc_, "south", 0.5, 0.93, (1.95, BW, 0.16), "brass", sink=0.05)
    scr = rivets(c, sc_, "south", 2, edge="bottom", margin=0.25, span=(0.2, 0.8), size=0.22)
    scv = vents(c, sc_, "south", 3, box=(0.3, 0.32, 0.72, 0.72), axis="v", w=0.2)
    mirror_x(c, sc_, scg, scr, scv)
    # 腹: 下ほど細い三枚の板（真紅・錆・真紅）と中央の溝・脇の鋲
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))
    for i, (y, ww, st) in enumerate(((19.95, 4.1, "plate"), (18.95, 3.7, "plate2"),
                                     (17.95, 3.3, "plate"))):
        p = rbox(ab, (0, y, -1.98 + i * 0.05), (ww, 0.82, 0.5), st, rot=(-8, 0, 0))
        stick(ab, p, "north", 0.5, 0.5, (0.18, 0.62, 0.16), "dark", sink=0.08)
        r_ = rivets(ab, p, "north", 1, line=((0.12, 0.5), (0.12, 0.5)), size=0.22,
                    style="rivet_b")
        mirror_x(ab, r_)
    cbox(ab, (0, 18.9, 2.08), (2.2, 2.6, 0.45), "steel_b")                        # 背の腰板


# ---------------------------------------------------------------------------
#  背中（炉のバックパック・タービン・煙突・双発の大ノズル・ホース）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "reactor", "body")
    pk = bevel(bk, (0, 22.3, 3.55), (4.6, 5.4, 2.1), "plate", cut=0.6, axis="z")
    rbox(bk, (0, 25.2, 3.25), (4.0, 0.8, 2.1), "plate2", rot=(20, 0, 0))            # 上の蓋
    rivets(bk, pk[0], "south", 4, edge="border", margin=0.26)
    # 炉の窓: 光る炉（同心円）の前で回るタービン（真鍮の輪・6 枚の羽根）
    R0 = (0, 22.95, 4.62)
    octa(bk, (R0[0], R0[1], 4.55), 2.9, 0.3, "iron", axis="z")
    cbox(bk, (R0[0], R0[1], 4.72), (2.2, 2.2, 0.16), "furnace")
    ring(bk, (R0[0], R0[1], 4.82), 1.32, 10, (0, 0.26, 0.3), "brass", axis="z")
    rt = s.fx("spin", "rotor", bk, pivot=(R0[0], R0[1], 4.85))
    for i in range(6):
        a = math.radians(i * 60 + 15)
        p1 = (R0[0] - 1.05 * math.sin(a), R0[1] + 1.05 * math.cos(a), 4.86)
        beam(rt, (R0[0], R0[1], 4.86), p1, 0.42, 0.16, "steel_b", roll=0.0)
    octa(rt, (R0[0], R0[1], 4.92), 0.62, 0.3, "brass", axis="z")
    # 炉の下: 縦の排気スリット・警告ストライプ
    vents(bk, pk[0], "south", 4, box=(0.2, 0.06, 0.8, 0.24), axis="v", w=0.22)
    cbox(bk, (0, 25.0, 4.38), (2.6, 0.36, 0.2), "hazard")
    sensor(bk, (-1.75, 24.75, 4.68), 0.24, "glow", "dark", facing=1)
    # 炉の脇の冷却フィン（右。鏡映）
    fins = [cbox(bk, (-2.42, 21.4 + i * 0.7, 3.5), (0.3, 0.3, 1.7), "frame_lt") for i in range(3)]
    mirror_x(bk, fins)
    # ホース: 炉の下から腰の両脇へ（垂れる蛇腹）
    hs = cable(bk, [(-1.6, 19.9, 3.6), (-2.9, 17.6, 2.4)], 0.3, "dark", sag=0.35,
               rib="frame_lt", rib_every=2)
    mirror_x(bk, hs)
    # 煙突（右。炉の上の角から上へ、少し外へ開く。先が赤熱）
    st = s.part("back", "stack_r", bk, pivot=(-2.35, 23.4, 3.95), rotation=(-8, 0, -9))
    octa(st, (-2.35, 26.0, 3.95), 1.1, 5.2, "steel", axis="y")
    for y in (24.2, 26.2):
        octa(st, (-2.35, y, 3.95), 1.3, 0.3, "brass", axis="y")
    octa(st, (-2.35, 28.45, 3.95), 1.45, 0.6, "iron", axis="y")
    cbox(st, (-2.35, 28.0, 3.35), (0.3, 0.3, 0.2), "rivet")
    cbox(st, (-2.35, 27.2, 3.35), (0.3, 0.3, 0.2), "rivet")
    eg = s.fx("glow", "stack_r", st, pivot=(-2.35, 28.75, 3.95))
    cbox(eg, (-2.35, 28.8, 3.95), (0.95, 0.16, 0.95), "ember")
    cbox(st, (-2.35, 23.55, 3.95), (1.5, 0.45, 1.5), "frame")                      # 根元の座
    # 大ノズル（右。下後ろへ向ける）: 胴・真鍮の帯・広がったベル・光る縁の輪・噴射口・炎
    th = s.part("back", "thruster_r", bk, pivot=(-1.45, 20.4, 4.3), rotation=(20, 0, -8))
    octa(th, (-1.45, 19.45, 4.3), 1.6, 1.9, "plate2", axis="y")
    octa(th, (-1.45, 20.2, 4.3), 1.8, 0.3, "brass", axis="y")
    octa(th, (-1.45, 18.75, 4.3), 1.8, 0.26, "brass", axis="y")
    octa(th, (-1.45, 17.95, 4.3), 2.25, 1.05, "iron", axis="y")
    octa(th, (-1.45, 17.4, 4.3), 2.0, 0.24, "glow", axis="y")
    cbox(th, (-1.45, 17.36, 4.3), (1.55, 0.16, 1.55), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.45, 17.4, 4.3))
    taper(fx, (-1.45, 17.4, 4.3), (-1.45, 10.6, 4.3), 1.8, 0.38, 3, "flame")
    taper(fx, (-1.45, 17.35, 4.3), (-1.45, 13.6, 4.3), 0.85, 0.22, 2, "flame_core", round_=False)


# ---------------------------------------------------------------------------
#  腕（錆の二の腕・肘のトゲ・排気口の篭手）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.32, 21.3, 0.0), (0.45, 3.1, 2.55), "plate2", rot=(0, 0, 3))
    line_on(ua, op, "west", (0.5, 0.12), (0.5, 0.88), 0.18, 0.16, "glow")
    rivets(ua, op, "west", 4, edge="left", margin=0.28, span=(0.15, 0.85), size=0.22)
    upf = rbox(ua, (X + 0.05, 21.35, -1.38), (2.2, 2.9, 0.42), "plate", rot=(-3, 0, 0))
    stick(ua, upf, "north", 0.5, 0.5, (0.5, 2.4, 0.16), "steel_b", sink=0.06)
    sensor(ua, (X + 0.05, 22.5, -1.66), 0.22, "glow", "dark")
    rbox(ua, (X + 0.05, 21.6, 1.36), (2.0, 2.3, 0.4), "steel_b", rot=(3, 0, 0))
    octa(ua, (X, 19.72, 0.02), 2.9, 0.34, "brass", axis="y")                      # 腕輪
    # 肘当て（後ろ）と鈍いトゲ
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    ex = A.ELBOW[0]
    cop = chamfer(el, (ex, 18.5, 1.62), (2.15, 1.9, 0.6), "plate", cut=0.32, axis="z")
    rivets(el, cop[0], "south", 2, edge="top", margin=0.28, span=(0.25, 0.75), size=0.2)
    octa(el, (ex, 18.45, 1.98), 1.0, 0.24, "brass", axis="z")
    taper(el, (ex, 18.4, 2.0), (ex - 0.1, 18.05, 3.0), 0.8, 0.32, 2, "steel", style_r="steel_b")
    cbox(el, (ex - 0.1, 18.02, 3.05), (0.3, 0.3, 0.3), "iron")
    # 篭手: 手首へ開く真紅・外の錆の板（橙の排気口・警告）・前の板・後ろの排気管・真鍮の袖口
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX_ = A.FOREARM_X
    bevel(fa, (FX_, 17.15, 0.0), (2.9, 1.9, 3.0), "plate", cut=0.45, axis="y")
    chamfer(fa, (FX_ - 0.04, 15.7, 0.0), (3.1, 1.75, 3.2), "plate", cut=0.42, axis="y")
    ob = rbox(fa, (FX_ - 1.72, 16.3, 0.0), (0.42, 3.1, 2.65), "plate2", rot=(0, 0, 5))
    vents(fa, ob, "west", 4, box=(0.2, 0.3, 0.75, 0.75), axis="v", w=0.2)
    stick(fa, ob, "west", 0.9, 0.5, (0.3, 2.6, 0.16), "hazard", sink=0.05)
    rivets(fa, ob, "west", 3, edge="top", margin=0.22, span=(0.15, 0.7), size=0.2)
    fv = rbox(fa, (FX_ - 0.02, 16.45, -1.64), (2.0, 2.2, 0.35), "plate2", rot=(-5, 0, 0))
    fvb = stick(fa, fv, "north", 0.5, 0.5, (1.3, 1.7, 0.18), "plate", sink=0.06)
    line_on(fa, fvb, "north", (0.3, 0.12), (0.55, 0.55), 0.16, 0.16, "glow")
    line_on(fa, fvb, "north", (0.55, 0.55), (0.42, 0.9), 0.16, 0.16, "glow_hot")
    rivets(fa, fv, "north", 2, edge="bottom", margin=0.18, span=(0.12, 0.88), size=0.2)
    chamfer(fa, (FX_ - 0.04, 14.72, 0.0), (3.12, 0.34, 3.25), "brass", cut=0.4, axis="y")  # 袖口
    # 後ろの排気管（篭手の背に沿って上へ。先が赤熱）
    rod(fa, (FX_ - 0.9, 15.4, 1.62), (FX_ - 0.95, 18.0, 1.75), 0.42, "iron")
    for y in (15.9, 17.2):
        octa(fa, (FX_ - 0.92, y, 1.68), 0.58, 0.26, "brass", axis="y")
    cbox(fa, (FX_ - 0.95, 18.1, 1.76), (0.32, 0.16, 0.32), "ember")
    sensor(fa, (FX_ + 0.25, 15.5, 1.7), 0.24, "glow", "dark", facing=1)


def hands(s):
    """手の甲の黒い鉄の板と真鍮の鋲、指の甲当て（4 本の基節 + 鉄の鋲）、親指の当て。指そのものは frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.42, 13.62, 0.0), (0.38, 1.75, 2.35), "steel", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.55, (0.62, 0.62, 0.2), "brass", sink=0.05)
    rivets(h, hb, "west", 2, edge="top", margin=0.22, span=(0.2, 0.8), size=0.2)
    n = (-0.81, -0.58, 0.0)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        o = 0.34
        beam(h, (p0[0] + n[0] * o, p0[1] + n[1] * o, zf), (p1[0] + n[0] * o, p1[1] + n[1] * o, zf),
             0.56, 0.22, "plate")
        cbox(h, (-7.33, 12.32, zf), (0.24, 0.3, 0.3), "iron")                     # 拳の鉄の鋲
    rbox(h, (-5.62, 13.55, -1.72), (0.62, 0.9, 0.22), "plate", rot=(0, 0, -36))


# ---------------------------------------------------------------------------
#  肩（三段に垂れる肩当て・鈍い二本の角）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    dome = bevel(p, (-7.25, 25.7, 0.0), (4.0, 2.5, 5.0), "plate", cut=0.78, axis="x",
                 rot=(0, 0, -14))
    top = stick(p, dome[0], "up", 0.45, 0.5, (2.5, 3.8, 0.3), "plate2", sink=0.1)
    stick(p, top, "up", 0.08, 0.5, (BW, 3.8, 0.18), "brass", sink=0.08)
    rdg = stick(p, top, "up", 0.58, 0.5, (0.55, 4.0, 0.3), "steel", sink=0.08)      # 中央の稜
    line_on(p, rdg, "up", (0.5, 0.1), (0.5, 0.9), 0.18, 0.16, "glow_hot")
    rivets(p, top, "up", 6, edge="border", margin=0.24, size=0.22, style="rivet_b")
    cbox(p, (-6.5, 24.2, 0.0), (2.2, 0.5, 3.8), "dark")                              # 裏の縁
    # 外の縁: 上・外へ反り返る錆の板（上端に真鍮）
    rim = rbox(p, (-9.15, 25.35, 0.0), (0.45, 1.9, 5.0), "plate2", rot=(0, 0, -30))
    stick(p, rim, "up", 0.5, 0.5, (0.45, 5.0, 0.2), "brass", sink=0.05)
    # 垂れる三段の板（真紅・錆・真紅）と真鍮の縁・紋章・警告・鋲・溶岩の線
    l1 = rbox(p, (-8.68, 23.6, 0.0), (0.55, 2.3, 4.7), "plate", rot=(0, 0, 15),
              decals={"west": {"decal": "emblem", "color": GLOW}})
    stick(p, l1, "west", 0.5, 0.06, (4.5, BW, 0.18), "brass", sink=0.05)
    rivets(p, l1, "west", 4, edge="top", margin=0.24, size=0.22)
    l2 = rbox(p, (-8.92, 21.95, 0.05), (0.5, 1.6, 4.25), "plate2", rot=(0, 0, 12),
              decals={"west": dict(HAZ, band="bottom")})
    stick(p, l2, "west", 0.5, 0.08, (4.0, BW, 0.18), "brass", sink=0.05)
    rivets(p, l2, "west", 3, edge="top", margin=0.22, size=0.22)
    l3 = rbox(p, (-9.08, 20.65, 0.1), (0.45, 1.15, 3.8), "plate", rot=(0, 0, 9))
    stick(p, l3, "west", 0.5, 0.1, (3.6, BW, 0.18), "brass", sink=0.05)
    line_on(p, l3, "west", (0.1, 0.62), (0.9, 0.62), 0.16, 0.16, "glow")
    # 前後の当て板とセンサー
    fr = rbox(p, (-7.25, 24.45, -2.45), (2.6, 1.3, 0.4), "plate_b", rot=(-12, 0, 0))
    sensor(p, (-7.6, 24.45, -2.7), 0.24, "glow", "dark")
    rbox(p, (-7.25, 24.55, 2.45), (2.6, 1.3, 0.4), "plate_b", rot=(12, 0, 0))
    # 鈍い角（肩の上から外上へ。前が少し短い。真鍮の座金 → 先細りの黒い鉄 → 鉄の先）
    for z, k in ((-1.3, 0.85), (1.3, 1.0)):
        base = (-7.8, 26.6, z)
        tip = (-9.2 - 0.5 * k, 28.0 + 1.35 * k, z * 1.35)
        octa(p, (-7.8, 26.5, z), 1.35, 0.32, "brass", axis="y", rot=(0, 0, -26), pivot=base)
        taper(p, base, tip, 1.2, 0.5, 3, "steel", style_r="steel_b")
        cbox(p, tip, (0.46, 0.46, 0.46), "iron")


# ---------------------------------------------------------------------------
#  兜（ドーム・額・V の眉庇・コリント式の頬当て・T 字のバイザー・しころ・耳の円盤・横向きの扇の鶏冠）
# ---------------------------------------------------------------------------
def helmet(s):
    hz = A.HEAD_Z
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.6, hz + 0.3), (4.5, 2.2, 4.9), "plate", cut=0.6, axis="z")
    bevel(hm, (0, 31.6, hz + 0.4), (3.5, 0.8, 4.3), "plate", cut=0.3, axis="z")   # 冠
    rbox(hm, (0, 30.88, hz - 2.05), (4.0, 1.2, 0.5), "plate", rot=(-24, 0, 0))     # 額の斜面
    # 重い V の眉庇（錆・真鍮の下縁）と額の真鍮の鋲
    br = rbox(hm, (-1.1, 30.05, hz - 2.42), (2.35, 0.62, 0.62), "plate2", rot=(-10, 8, 10))
    brt = stick(hm, br, "north", 0.5, 0.12, (2.2, 0.2, 0.16), "brass", sink=0.04)
    # こめかみの板（錆）と鋲
    sd = cbox(hm, (-2.1, 29.05, hz + 0.6), (0.42, 2.5, 3.4), "plate2")
    sdr = rivets(hm, sd, "west", 2, edge="top", margin=0.28, span=(0.25, 0.75), size=0.2)
    # コリント式の頬当て（前へ絞り、中央に縦の隙間を残す）と顎・頬の吸気口
    ck = rbox(hm, (-1.2, 28.4, hz - 2.0), (1.95, 1.85, 0.5), "plate", rot=(3, 24, -3))
    ckt = stick(hm, ck, "north", 0.95, 0.5, (0.2, 1.7, 0.16), "brass", sink=0.05)
    ckv = stick(hm, ck, "north", 0.45, 0.22, (0.9, 0.2, 0.16), "vent", sink=0.05)
    jw = rbox(hm, (-0.75, 27.72, hz - 1.95), (1.1, 0.65, 0.45), "plate", rot=(0, 26, -20))
    ear = octa(hm, (-2.38, 29.2, hz + 0.6), 1.35, 0.32, "iron", axis="x")         # 耳の円盤
    eg = cbox(hm, (-2.57, 29.2, hz + 0.6), (0.16, 0.45, 0.45), "glow")
    mirror_x(hm, br, brt, sd, sdr, ck, ckt, ckv, jw, ear, eg)
    cbox(hm, (0, 30.05, hz - 2.72), (0.42, 0.5, 0.3), "brass")                    # 眉の中央の鋲
    # 後頭部（型番・小さな排気口）と外へ開くしころ
    bh = cbox(hm, (0, 29.35, hz + 2.55), (4.0, 2.4, 0.45), "plate",
              decals={"south": {"decal": "serial", "text": "AR-04", "ink": (236, 170, 96),
                                "y": 0.72}})
    vents(hm, bh, "south", 3, box=(0.3, 0.12, 0.7, 0.42), w=0.16)
    rbox(hm, (0, 31.15, hz + 2.45), (3.4, 1.4, 0.45), "plate", rot=(32, 0, 0))
    rbox(hm, (0, 27.95, hz + 2.75), (4.0, 0.8, 0.45), "plate2", rot=(26, 0, 0))
    rbox(hm, (0, 27.55, hz + 2.98), (3.5, 0.55, 0.4), "plate2_b", rot=(40, 0, 0))
    # T 字のバイザー: 骨格の暗い顔の板の上に、横の目の帯 + 縦の口の帯
    vz = s.part("visor", "tslit", "head")
    fg = s.fx("glow", "visor", vz, pivot=(0, A.EYE_Y, hz - 2.42))
    cbox(fg, (0, A.EYE_Y, hz - 2.42), (3.3, 0.36, 0.2), "visor")
    cbox(fg, (0, 28.45, hz - 2.42), (0.36, 1.75, 0.2), "visor")
    # 横向きの扇の鶏冠（耳から耳へ。飾り = 計測しない）: 羽板は 3 節（暗い真紅 → 真紅）・先に溶岩の縁・
    # 根元に真鍮の櫛
    cr = s.part("helmet", "crest", "head", pivot=(0, 31.6, hz + 0.45), ornament=True)
    C = (0.0, 29.0, hz + 0.45)
    n = 13
    for i in range(n):
        a = -80.0 + 160.0 * i / (n - 1)
        q = (a / 80.0) ** 2
        r0 = 2.75 - 0.55 * q
        r1 = 5.5 - 1.45 * q
        t = math.radians(a)
        d = (-math.sin(t), math.cos(t))
        dz = 0.07 if i % 2 else -0.07
        rt = r1 - 0.32
        nseg = 2
        for k in range(nseg):
            ra = r0 + (rt - r0) * k / nseg
            rb = r0 + (rt - r0) * (k + 1) / nseg
            rm = (ra + rb) / 2
            wd = 0.8 + 0.3 * (rm - r0) / max(0.1, rt - r0)
            st = ("plate_b", "plate")[k] if i % 2 == 0 else ("steel_b", "plate_b")[k]
            cen = (C[0] + d[0] * rm, C[1] + d[1] * rm, C[2] + dz)
            rbox(cr, cen, (wd, rb - ra + 0.06, 0.56), st, rot=(0, 0, -a))
        tip = (C[0] + d[0] * (r1 - 0.16), C[1] + d[1] * (r1 - 0.16), C[2] + dz)
        rbox(cr, tip, (0.94, 0.32, 0.62), "glow_hot", rot=(0, 0, -a))
        comb = (C[0] + d[0] * (r0 + 0.1), C[1] + d[1] * (r0 + 0.1), C[2])
        rbox(cr, comb, (0.8, 0.36, 0.84), "brass", rot=(0, 0, -a))


# ---------------------------------------------------------------------------
#  衛星（背中の後ろの傾いた軌道。フォボス = 内側で速い芋形 / ダイモス = 外側で遅い小さく滑らか）
# ---------------------------------------------------------------------------
def moons(s):
    C = (0.0, 22.6, 8.2)
    orr = s.part("extra", "orrery", "body", pivot=C, rotation=(-10, 0, 0))
    # フォボス: いびつに重ねた岩・真鍮の帯・橙の目（子機）
    sp = s.fx("spin", "phobos", orr, pivot=C)
    M = (C[0] - 3.7, C[1], C[2])
    roll = s.fx("spin", "phobos_roll", sp, pivot=M)
    cbox(roll, M, (2.0, 1.45, 1.5), "phobos")
    rbox(roll, (M[0] + 0.48, M[1] + 0.25, M[2] - 0.15), (1.3, 1.3, 1.25), "phobos", rot=(20, 35, 10))
    rbox(roll, (M[0] - 0.6, M[1] - 0.2, M[2] + 0.2), (1.12, 1.05, 1.2), "phobos",
         rot=(-15, 20, 30))
    rbox(roll, (M[0] - 0.15, M[1] + 0.5, M[2] + 0.22), (0.9, 0.7, 0.9), "phobos", rot=(10, 45, 0))
    cbox(roll, (M[0], M[1] - 0.05, M[2]), (2.08, 0.24, 1.58), "brass")
    octa(roll, (M[0] - 1.06, M[1] - 0.05, M[2]), 0.56, 0.26, "glow", axis="x")
    cbox(roll, (M[0] + 1.07, M[1] - 0.05, M[2]), (0.2, 0.4, 0.4), "iron")
    # ダイモス: 小さく丸い岩・アンテナ
    sp2 = s.fx("spin", "deimos", orr, pivot=C)
    M2 = (C[0] + 5.3, C[1], C[2])
    roll2 = s.fx("spin", "deimos_roll", sp2, pivot=M2)
    cbox(roll2, M2, (1.15, 1.15, 1.15), "deimos")
    rbox(roll2, M2, (1.06, 1.06, 1.06), "deimos", rot=(45, 0, 45))
    rbox(roll2, M2, (1.02, 1.02, 1.02), "deimos", rot=(0, 45, 0))
    taper(roll2, (M2[0], M2[1] + 0.55, M2[2]), (M2[0] + 0.25, M2[1] + 1.45, M2[2]), 0.2, 0.16, 1,
          "iron", round_=False)
    cbox(roll2, (M2[0] + 0.25, M2[1] + 1.5, M2[2]), (0.26, 0.26, 0.26), "glow")
