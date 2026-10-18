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


