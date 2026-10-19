# -*- coding: utf-8 -*-
"""金星 — 明星機装 モーニングスター（Morning Star Frame）。v1.1: 7 頭身の女神像。

明けの明星の女神。frame7 の暗い青銅の骨格（bulk 0.92 の細身）の上に、金（plate）とクリーム（plate2）の
縁取りのある多層の装甲を重ねる。
  * 腰: 金とクリームの花弁を二重に重ねたスカート（外の金 3 枚 + 内のクリーム 3 枚 × 左右 + 背の裳裾 1 枚）。
    前は割れて長い脚を見せる（前ほど短く、後ろほど長い）。花弁は細い首・丸い胴・尖った先の槍形で、
    1 枚ずつ extra_* のボーンを持ち蝶番から外へ開く。組み上がりの最後に咲き、空中では花が咲くように
    大きく開き、疾走では後ろへなびく
  * 兜: 小さな金の冠、磁器の面（V の面・鼻筋・薔薇色の唇）、硫黄色の切れ長の目と金のまぶた、
    金のティアラと額で脈打つ八芒星（fx_glow）、薔薇金の尖塔（飾り）、耳の金の円盤、こめかみの唐草、
    後ろへ流れる五本の金の髪の刃（飾り）、頭の後ろで回る八芒の光輪（fx_spin）
  * 肩: 小さな金の肩当ての上の「雲のポッド」（クリームの雲の玉）。外に硫黄色に光る排気口と、中で回る
    排気ファン（fx_spin）、雲を抱く金の輪、下の排気スリット
  * 胸: 金の胸郭と襟、クリームの胸板（金の縁・唐草・リベット）、胸骨に金の八芒星の枠の星核（回る輪）、
    金の下胸帯、コルセット（三段のクリームの板・金の芯と骨・山形の金具・背の交差する紐）。脇の油圧シリンダーは見せる
  * 細い手足: クリームの長手袋（花弁のように開く袖口・金の腕輪・薔薇色の宝玉）、金の指の甲当て、
    金のサイハイブーツ（花弁形の履き口・四芒星の膝当て・膝の脇のピストン・ふくらはぎの排気口と羽根のヒレ）、
    尖ったつま先とピンヒール
  * 背: 丸いクリームの背嚢（排気スリット・四芒星の紋）、羽根の排気フィン（左右 3 枚。飾り）、
    金のノズルの双発スラスター（金色の炎）、腰へ垂れる蛇腹のホース

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A。右側だけ作り `_r` を付ける → 左は自動で
鏡映。回転（統合版の rotation）: rx 正 = 上端が前へ / ry 正 = 正面が右（-X）を向く（+X の端が前へ）/
rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く。横板なら -X の端が上がる）。
"""
from __future__ import annotations

import math

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, finger_chain,  # noqa: F401
                        joint_drum, layered_plate, line_on, mirror_x, octa, piston, polyline,
                        rbox, ring, rivets, rod, sensor, stick, taper, vents)

GOLD_W = 0.24          # 金の縁取りの幅
LX = A.LEG_X           # 脚の軸 -2.15
HZ = A.HEAD_Z          # 頭の中心の奥行き -0.25

# ===========================================================================
#  塗り（astro_paint.suit_styles("venus") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    # 金の縁取りは主装甲（淡い金）より一段濃く、照りを強く（金の上でも縁が読めるように）
    "gold": {"base": (214, 146, 40), "light": (255, 240, 168), "dark": (128, 74, 18),
             "line": (78, 42, 10)},
    # 薔薇金の線条細工・リベット（金の装甲の上に乗せる）
    "rosegold": {"kind": "trim", "base": (236, 150, 132), "light": (255, 226, 208),
                 "dark": (156, 74, 72), "line": (96, 40, 44)},
    # 雲のポッド・背嚢の地（パネル線の無いなめらかなクリーム）
    "cloud": {"kind": "armor", "base": (255, 243, 214), "light": (255, 255, 248),
              "dark": (226, 200, 150), "line": (176, 134, 76), "panel": 0, "sheen": False,
              "outline": False, "bevel": False},
    "petal_gold": {"kind": "armor", "base": (240, 192, 84), "light": (255, 236, 168),
                   "dark": (184, 128, 40), "line": (120, 76, 22), "panel": 0,
                   "stripe": {"dir": "v", "period": 7, "width": 1, "color": (226, 168, 66),
                              "k": 0.5}},
    "petal_cream": {"kind": "armor", "base": (255, 236, 206), "light": (255, 252, 240),
                    "dark": (226, 196, 150), "line": (170, 120, 80), "panel": 0},
    # 冠（金。パネル線なし）と磁器の面
    "helm": {"kind": "armor", "base": (240, 194, 88), "light": (255, 238, 170),
             "dark": (176, 120, 38), "line": (110, 70, 20), "panel": 0},
    "face": {"kind": "armor", "base": (255, 246, 234), "light": (255, 255, 252),
             "dark": (226, 206, 186), "panel": 0, "line": (150, 118, 92)},
    # 額の八芒星（明けの明星の白金の光）
    "star": {"kind": "glowline", "glow": (255, 240, 150), "light": (255, 255, 236),
             "bevel": False, "outline": False},
    "visor": {"glow": (214, 255, 110), "light": (250, 255, 224), "deep": (70, 112, 16),
              "emit": 18},
    "flame": {"glow": (255, 226, 96), "light": (255, 252, 214), "deep": (214, 130, 20)},
    "flame_core": {"kind": "flame", "glow": (255, 250, 190), "light": (255, 255, 255),
                   "deep": (255, 200, 80), "bevel": False, "outline": False},
    "thruster": {"glow": (255, 230, 110), "light": (255, 255, 230), "deep": (176, 104, 16)},
    "vent": {"glow": (226, 255, 96), "deep": (110, 120, 20)},
    "serial": {"text": "VE-02", "under": {"kind": "armor", "base": (255, 238, 204),
                                           "panel": 0, "line": (150, 110, 70)},
               "ink": (150, 92, 30)},
    "hazard": {"c1": (226, 255, 96), "c2": (62, 42, 24)},
    # 骨格: 暗い青銅のボディスーツ
    "inner": {"base": (60, 40, 32)},
}

# ===========================================================================
#  スカートの花弁（名前, 向き°, 長さ, 幅, 開き°, 塗り, 縁, 層）
#  向き 0 = 正面、90 = 右（-X）、180 = 背中。右側だけ書き、左は自動で鏡映。前（±45° の内）は割れて脚を見せる
# ===========================================================================
SKIRT_RX, SKIRT_RZ = 3.65, 2.6      # 蝶番の楕円（横・前後の半径）
SKIRT_Y = 16.4                      # 蝶番の高さ（腰帯の下）
PETALS = [
    # 外の金の花弁（後ろほど長い）
    ("petal_o1_r", 68.0, 5.4, 2.3, 20.0, "petal_gold", "rosegold", 0),
    ("petal_o2_r", 112.0, 6.2, 2.4, 19.0, "petal_gold", "rosegold", 0),
    ("petal_o3_r", 152.0, 6.8, 2.4, 21.0, "petal_gold", "rosegold", 0),
    # 内のクリームの花弁（金の花弁の間からのぞく）
    ("petal_i1_r", 47.0, 4.4, 1.85, 15.0, "petal_cream", "gold", 1),
    ("petal_i2_r", 90.0, 5.2, 1.95, 14.0, "petal_cream", "gold", 1),
    ("petal_i3_r", 132.0, 6.0, 2.0, 16.0, "petal_cream", "gold", 1),
]
TRAIN = ("petal_train", 180.0, 7.4, 2.5, 18.0, "petal_gold", "gold", 0)   # 背の裳裾（左右なし）
HALO_C = (0.0, 30.4, 4.5)          # 光輪の中心（頭の後ろ）
CORE_C = (0.0, 22.25, -3.2)        # 胸の星核の中心


# ===========================================================================
#  部位アニメ（Molang。q.anim_time は 12 秒でループするので周波数は 30°/秒の倍数に）
#  回る物は v.astro_spin（空中・疾走で速く進む累積の位相）× 角速度。重みは振れ幅にだけ掛ける
# ===========================================================================
def _petal_anims():
    idle, thrust, sprint = {}, {}, {}
    for i, (name, hd, _L, _W, _fl, _st, _tr, layer) in enumerate(PETALS + [TRAIN]):
        bone = f"extra_{name}"
        ph = (i * 53) % 360
        idle[bone] = {"rotation": [f"math.sin(q.anim_time * 60.0 + {ph}) * 1.2", 0, 0]}
        # 空中: 花が咲くように開く（外の花弁ほど大きく）
        k_air = 26.0 if layer == 0 else 18.0
        thrust[bone] = {"rotation": [
            f"-v.astro_air * ({k_air} + math.sin(q.anim_time * 360.0 + {ph}) * 2.5)", 0, 0]}
        # 疾走: 前の花弁は脚に押されて開き、後ろの花弁は風になびく
        k_run = 16.0 if hd < 75 or hd > 140 else 9.0
        sprint[bone] = {"rotation": [
            f"-v.astro_run * ({k_run} + math.sin(q.anim_time * 720.0 + {ph}) * 3.0)", 0, 0]}
    return idle, thrust, sprint


_PI, _PT, _PS = _petal_anims()

SUIT_ANIMS = {
    "idle": dict(_PI, **{
        "fx_spin_halo": {"rotation": [0, 0, "v.astro_spin * 30.0"]},
        "extra_halo": {"position": [0, "math.sin(q.anim_time * 90.0) * 0.2", 0]},
        "fx_spin_core": {"rotation": [0, 0, "-v.astro_spin * 60.0"]},
        "fx_spin_fan_r": {"rotation": ["v.astro_spin * 240.0", 0, 0]},
        "back_wing_r": {"rotation": [0, 0, "math.sin(q.anim_time * 60.0) * 2.0"]},
        "helmet_plume": {"rotation": ["math.sin(q.anim_time * 60.0 + 40.0) * 1.5", 0, 0]},
    }),
    "thrust": dict(_PT, **{
        # 羽根のフィンが上外へ広がり、髪が後ろへなびく
        "back_wing_r": {"rotation": ["-v.astro_air * 6.0", "v.astro_air * 10.0",
                                     "-v.astro_air * 16.0"]},
        "helmet_plume": {"rotation": ["v.astro_air * (6.0 + math.sin(q.anim_time * 360.0) * 2.0)",
                                      0, 0]},
    }),
    "sprint": dict(_PS, **{
        "back_wing_r": {"rotation": ["-v.astro_run * 8.0", 0, "-v.astro_run * 6.0"]},
        "helmet_plume": {"rotation": ["v.astro_run * (9.0 + math.sin(q.anim_time * 720.0) * 2.0)",
                                      0, 0]},
    }),
}


# ===========================================================================
def build_suit(s: Suit):
    # 細身の骨格（組み上がりの最初に全身が揃うように、省くのはブーツと同時に包まれる足だけ）
    s.frame7(bulk=0.92, skip=("foot",))
    boots(s)
    legs(s)
    waist(s)
    skirt(s)
    torso(s)
    back(s)
    arms(s)
    hands(s)
    shoulders(s)
    helmet(s)
    halo(s)


# ---------------------------------------------------------------------------
#  局所の道具
# ---------------------------------------------------------------------------
def star8(bone, c, rl, rs, w, t, style_l, style_s=None):
    """正面向き（XY 平面）の八芒星: 縦横の長い光条 2 本 + 斜めの短い光条 2 本（4 個）。"""
    out = [cbox(bone, c, (w, 2 * rl, t), style_l), cbox(bone, c, (2 * rl, w, t), style_l)]
    for a in (45, -45):
        out.append(rbox(bone, (c[0], c[1], c[2] + 0.03), (w * 0.85, 2 * rs, t * 0.9),
                        style_s or style_l, rot=(0, 0, a)))
    return out


def puff(bone, c, r, style):
    """角を落とした雲の玉（4 個）: 中心の箱 + 3 軸に寝かせた 45° の箱。"""
    d = 2 * r
    return [cbox(bone, c, (d * 0.76, d * 0.76, d * 0.76), style),
            rbox(bone, c, (d, d * 0.58, d * 0.58), style, rot=(45, 0, 0)),
            rbox(bone, c, (d * 0.58, d * 0.96, d * 0.58), style, rot=(0, 45, 0)),
            rbox(bone, c, (d * 0.58, d * 0.58, d * 0.98), style, rot=(0, 0, 45))]


def diamond(bone, c, d, t, style, rot=(0, 0)):
    """正面向きの菱形（45° 回した板）。rot = (rx, ry) で面の向き。"""
    return rbox(bone, c, (d, d, t), style, rot=(rot[0], rot[1], 45))


# ---------------------------------------------------------------------------
#  ブーツ（足首から。尖ったつま先・甲・ピンヒール・外くるぶしの宝玉）
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")
    # つま先の箱（金）と靴底、つま先の板、尖った先
    toe = bevel(b, (LX, 0.62, -2.55), (2.25, 1.0, 2.5), "plate", cut=0.34, axis="z")
    cbox(b, (LX, 0.09, -2.6), (2.15, 0.18, 2.6), "dark")                            # 靴底
    rbox(b, (LX, 0.5, -3.7), (1.0, 0.66, 1.0), "gold", rot=(0, 45, 0))             # 尖った先
    tp = rbox(b, (LX, 1.02, -3.05), (1.85, 0.36, 1.1), "plate2", rot=(-14, 0, 0))  # つま先の板
    stick(b, tp, "up", 0.5, 0.15, (1.6, 0.2, 0.16), "gold", sink=0.05)
    rbox(b, (LX, 0.82, -3.62), (0.46, 0.46, 0.24), "gem_accent", rot=(-14, 0, 45))
    line_on(b, toe[0], "west", (0.1, 0.45), (0.92, 0.45), 0.18, 0.16, "glow")
    rivets(b, toe[0], "west", 2, edge="top", margin=0.24, span=(0.3, 0.75), size=0.22,
           style="rosegold")
    # 甲（クリーム）: つま先から足首へ上る板
    ins = rbox(b, (LX, 1.5, -1.42), (2.0, 0.42, 2.05), "plate2", rot=(-34, 0, 0))
    line_on(b, ins, "up", (0.5, 0.1), (0.5, 0.9), 0.2, 0.16, "gold")
    # 土踏まずの金の側壁（つま先から踵へ上る）と暗い靴底の芯
    rbox(b, (LX, 0.95, -0.85), (2.15, 0.9, 1.7), "plate", rot=(-24, 0, 0))
    beam(b, (LX, 0.12, -1.45), (LX, 0.72, 0.25), 1.6, 0.24, "dark")
    # 踵の殻（金）とピンヒール
    hl = chamfer(b, (LX, 1.35, 0.65), (2.3, 1.3, 2.0), "plate", cut=0.4, axis="y")
    cbox(b, (LX, 0.72, 0.85), (1.85, 0.2, 1.6), "dark")                             # 踵の底
    taper(b, (LX, 0.72, 1.25), (LX, 0.12, 1.42), 0.62, 0.4, 2, "gold")             # ピンヒール
    cbox(b, (LX, 0.08, 1.44), (0.46, 0.16, 0.46), "dark")
    line_on(b, hl[0], "south", (0.15, 0.5), (0.85, 0.5), 0.2, 0.16, "glow_soft")
    # 外くるぶしの金の台と薔薇色の宝玉
    octa(b, (LX - 1.24, 1.35, 0.45), 1.0, 0.26, "gold", axis="x")
    rbox(b, (LX - 1.4, 1.35, 0.45), (0.2, 0.52, 0.52), "gem_accent", rot=(45, 0, 0))


# ---------------------------------------------------------------------------
#  脚（腿の板・ガーター・花弁形のブーツの履き口・四芒星の膝当て・脛当て・ふくらはぎ）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前のクリームの板（金の上板・発光線）、外の細い金の板、金のガーターと宝玉。後ろと内は骨格を見せる
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX + 0.05, 11.75, -1.42), (2.1, 2.7, 0.4), "plate", top="petal_cream",
                       rot=(-3, 0, 0), inset=0.24, trim="gold", trim_edge="top",
                       rivet="gold", n_rivets=2, rivet_edge="bottom")
    line_on(t, fr["top"], "north", (0.5, 0.22), (0.5, 0.86), 0.18, 0.16, "rosegold")
    side = rbox(t, (LX - 1.48, 11.45, 0.1), (0.36, 2.4, 2.1), "plate", rot=(0, 0, -3))
    stick(t, side, "west", 0.5, 0.5, (1.4, 1.8, 0.16), "plate2", sink=0.05,
          decals={"west": {"decal": "serial", "text": "VE-02", "ink": (150, 92, 30)}})
    rivets(t, side, "west", 2, edge="bottom", margin=0.22, span=(0.25, 0.75), size=0.22,
           style="rosegold")
    octa(t, (LX, 12.85, 0.0), 2.84, 0.3, "gold", axis="y")                          # ガーター
    rbox(t, (LX + 0.1, 12.85, -1.48), (0.5, 0.5, 0.26), "gem_accent", rot=(0, 0, 45))
    # ブーツの履き口（腿の中ほど）: 金の帯 + 前へ尖る花弁形のクリームの折り返し
    cf = s.part("legs", "cuff_r", "rightLeg", pivot=A.KNEE)
    octa(cf, (LX, 9.95, 0.0), 2.78, 0.36, "gold", axis="y")
    fold = diamond(cf, (LX, 10.25, -1.48), 1.45, 0.3, "plate2", rot=(-6, 0))
    diamond(cf, (LX, 10.22, -1.38), 1.75, 0.24, "gold", rot=(-6, 0))
    stick(cf, fold, "north", 0.5, 0.5, (0.36, 0.36, 0.16), "gem_accent", sink=0.04)
    rbox(cf, (LX - 1.35, 10.2, 0.05), (0.3, 1.0, 1.0), "plate2", rot=(0, 0, -10))   # 外の折り返し
    # 膝: 四芒星の膝当て（金の菱形 → クリームの菱形 → 金の光条 → 宝玉）と外の油圧シリンダー
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    KZ = -1.62
    diamond(k, (LX, 8.5, KZ), 1.95, 0.5, "plate", rot=(-4, 0))
    kc = diamond(k, (LX, 8.5, KZ - 0.28), 1.35, 0.3, "plate2", rot=(-4, 0))
    cbox(k, (LX, 8.5, KZ - 0.48), (0.24, 3.1, 0.2), "gold")                       # 縦の光条
    cbox(k, (LX, 8.5, KZ - 0.48), (2.4, 0.24, 0.2), "gold")                       # 横の光条
    rbox(k, (LX, 8.5, KZ - 0.62), (0.52, 0.52, 0.24), "gem_accent", rot=(0, 0, 45))
    rivets(k, kc, "north", 4, edge="border", margin=0.22, size=0.18, style="gold")
    piston(k, (LX - 1.5, 10.7, 0.55), (LX - 1.42, 6.5, 0.45), r=0.24, style="frame",
           rod_style="chrome", cap_style="dark")
    # 脛: 前の金の板 + クリームの V の稜（発光線）、両脇の板、ふくらはぎの排気口、外の羽根のヒレ
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 5.25, -1.3), (2.35, 4.0, 0.45), "plate", rot=(5, 0, 0))
    low = rbox(g, (LX, 3.05, -1.08), (1.85, 1.6, 0.42), "plate", rot=(-3, 0, 0))
    stick(g, low, "north", 0.5, 0.08, (1.75, GOLD_W, 0.16), "gold", sink=0.05)
    keel = rbox(g, (LX - 0.3, 5.3, -1.6), (0.66, 3.5, 0.4), "plate2", rot=(5, 24, 0))
    mirror_x(g, keel, about=LX)
    line_on(g, front, "north", (0.5, 0.12), (0.5, 0.86), 0.18, 0.18, "glow", lift=0.18)
    sd = rbox(g, (LX - 1.22, 4.75, -0.1), (0.38, 4.4, 2.1), "plate", rot=(0, 0, -6))
    sdr = rivets(g, sd, "west", 1, edge="bottom", margin=0.28, size=0.22, style="rosegold")
    sdl = line_on(g, sd, "west", (0.15, 0.62), (0.85, 0.62), 0.16, 0.16, "glow_soft")
    mirror_x(g, sd, sdr, sdl, about=LX)
    calf = rbox(g, (LX, 5.8, 1.6), (1.95, 2.6, 0.42), "plate_b", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.25, 0.2, 0.75, 0.8))
    fin = rbox(g, (LX - 1.6, 6.0, 1.0), (0.28, 2.7, 1.5), "plate2", rot=(-16, 0, -8))
    stick(g, fin, "west", 0.08, 0.5, (0.22, 2.5, 0.16), "gold", sink=0.04)
    line_on(g, fin, "west", (0.3, 0.2), (0.75, 0.85), 0.16, 0.16, "glow")
    octa(g, (LX, 3.05, 0.15), 2.42, 0.32, "gold", axis="y")                         # 足首の帯


# ---------------------------------------------------------------------------
#  腰（腰帯・宝玉の留め金・前垂れ・腰の脇の板・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    belt = chamfer(w, (0, 16.85, 0.12), (6.7, 0.85, 4.6), "frame", cut=0.5, axis="y")
    chamfer(w, (0, 17.33, 0.12), (6.85, 0.24, 4.72), "gold", cut=0.52, axis="y")    # 金の上縁
    bl = rivets(w, belt[0], "north", 2, edge="bottom", margin=0.42, span=(0.12, 0.3),
                size=0.2, style="gold")
    mirror_x(w, bl)
    # 留め金: 金の八角 + 薔薇色の宝玉 + 小さな四芒星
    octa(w, (0, 16.85, -2.3), 1.5, 0.34, "gold", axis="z")
    rbox(w, (0, 16.85, -2.52), (0.7, 0.7, 0.26), "gem_accent", rot=(0, 0, 45))
    cbox(w, (0, 16.85, -2.62), (0.2, 1.0, 0.16), "star")
    cbox(w, (0, 16.85, -2.62), (1.0, 0.2, 0.16), "star")
    # 前垂れ（細いクリームの花弁。腿の前を隠さない幅）
    fp = rbox(w, (0, 15.05, -2.12), (1.3, 2.5, 0.38), "plate2", rot=(-8, 0, 0))
    diamond(w, (0, 13.75, -2.3), 0.92, 0.36, "plate2", rot=(-8, 0))
    stick(w, fp, "north", 0.5, 0.5, (0.2, 2.2, 0.16), "glow", sink=0.05)
    stick(w, fp, "north", 0.5, 0.97, (1.2, 0.2, 0.16), "gold", sink=0.05)
    # 腰の脇の金の板（股関節の前を覆う）
    hp = rbox(w, (-2.25, 15.85, -1.95), (1.7, 1.1, 0.38), "plate", rot=(-8, 18, 6))
    hpr = rivets(w, hp, "north", 2, edge="top", margin=0.24, span=(0.25, 0.75), size=0.2,
                 style="rosegold")
    mirror_x(w, hp, hpr)
    # 後ろ垂れ（短い。裳裾の花弁の下地）
    rs = rbox(w, (0, 15.3, 2.35), (3.6, 2.0, 0.4), "plate_b", rot=(12, 0, 0))
    rivets(w, rs, "south", 3, edge="top", margin=0.22, size=0.2, style="gold")


def skirt(s):
    for pt in PETALS:
        petal(s, *pt)
    petal(s, *TRAIN)


def petal(s, name, heading, L, W, flare, style, trim, layer):
    """花弁 1 枚。蝶番（上端）を楕円の上に置き、ボーンの rotation (−開き, 向き, 0) で外へ開く。
    キューブは「正面向き（向き 0）・開き 0」の形で蝶番の位置に置く（ボーンの回転がまとめて回す）。
    形（槍形）: 蝶番の金具 → 細い首 → 角を落とした丸い胴 → 尖った先。縁取りの裏板、中央の葉脈（発光）、
    首のリベット、外の花弁は先に宝玉。"""
    a = math.radians(heading)
    rx = SKIRT_RX - 0.2 * layer
    rz = SKIRT_RZ - 0.2 * layer
    H = (round(-rx * math.sin(a), 3), SKIRT_Y - 0.15 * layer, round(-rz * math.cos(a), 3))
    b = s.part("extra", name, "body", pivot=H, rotation=(-flare, heading, 0))
    hx, hy, hz = H
    T = 0.3
    neck = 1.0                                   # 首の長さ
    body_h = L - neck - W * 0.45
    yb = hy - neck - body_h                      # 胴の下端（ここから菱形の先が下へ）
    d = W * 0.72
    zf = hz - 0.08
    cut = W * 0.22
    # 蝶番の金具と首（細い）
    cbox(b, (hx, hy - 0.08, hz + 0.02), (0.95, 0.42, 0.52), "gold")
    nk = cbox(b, (hx, hy - neck / 2 - 0.15, zf), (W * 0.56, neck, T), style)
    # 縁: 一回り大きい裏の板（縁取りの色）と尖った先の裏
    cbox(b, (hx, yb + body_h / 2, hz + 0.14), (W + 0.32, body_h - 2 * cut - 0.1, 0.24), trim)
    diamond(b, (hx, yb + 0.05, hz + 0.14), d + 0.3, 0.22, trim)
    # 表の胴（角を落とした丸い胴）と尖った先
    main = chamfer(b, (hx, yb + body_h / 2, zf), (W, body_h, T), style, cut=cut, axis="z")
    diamond(b, (hx, yb + 0.05, zf), d, T, style)
    # 中央の葉脈（外は発光、内は柔らかい発光）と首のリベット
    line_on(b, main[1], "north", (0.5, 0.0), (0.5, 1.0), 0.2, 0.16,
            "glow" if layer == 0 else "glow_soft", extend=0.7)
    rivets(b, nk, "north", 2, edge="top", margin=0.22, span=(0.25, 0.75), size=0.2,
           style="rosegold" if layer == 0 else "gold")
    if layer == 0:
        rbox(b, (hx, yb - d * 0.3, zf - 0.2), (0.46, 0.46, 0.2), "gem_accent", rot=(0, 0, 45))


# ---------------------------------------------------------------------------
#  胴（金の胸郭・クリームの胸板・八芒星の星核・襟・下胸帯・コルセット）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    # 胸郭の金の殻（上が広い逆三角形）と脇の斜面
    up = bevel(c, (0, 24.45, 0.0), (8.5, 3.0, 5.5), "plate", cut=0.85, axis="y")
    chamfer(c, (0, 22.15, 0.05), (6.9, 2.0, 5.2), "plate_b", cut=0.7, axis="y")
    sl = rbox(c, (-3.8, 22.85, 0.1), (0.45, 2.5, 4.0), "plate", rot=(0, 0, -24))
    rivets(c, up[1], "south", 2, edge="top", margin=0.32, span=(0.3, 0.7), size=0.22,
           style="rosegold")
    # クリームの胸板（丸く V に開く。金の上縁・下の薔薇色の線・リベット・唐草）
    PC, PR = (-1.72, 23.3, -2.92), (10, 15, 8)
    rim = chamfer(c, (PC[0], PC[1], PC[2] + 0.22), (3.5, 2.8, 0.3), "gold", cut=0.72, axis="z",
                  rot=PR)
    pec = chamfer(c, PC, (3.2, 2.5, 0.5), "petal_cream", cut=0.6, axis="z", rot=PR)
    pt = line_on(c, pec[0], "north", (0.12, 0.9), (0.88, 0.9), 0.18, 0.16, "rosegold")
    pg = line_on(c, pec[0], "north", (0.88, 0.16), (0.24, 0.1), 0.18, 0.16, "glow_accent")
    pr = rivets(c, rim[1], "north", 2, edge="top", margin=0.16, span=(0.35, 0.75), size=0.2,
                style="rosegold")
    fil = polyline(c, [(-3.3, 24.2, -2.85), (-2.55, 23.3, -3.38), (-1.6, 22.95, -3.5)],
                   0.18, 0.18, "rosegold")                                           # 唐草
    mirror_x(c, sl, rim, pec, pt, pg, pr, fil)
    # V の襟ぐり: 襟から胸の谷へ降りるクリームの帯（金の縁）と、上の殻の縁のリベットの列
    vn = beam(c, (-1.45, 25.8, -2.78), (-0.18, 23.95, -2.98), 0.62, 0.3, "petal_cream")
    vg = beam(c, (-1.75, 25.65, -2.8), (-0.48, 23.85, -2.98), 0.18, 0.24, "gold")
    vr = rivets(c, up[0], "north", 2, edge="top", margin=0.32, span=(0.12, 0.26), size=0.2,
                style="rosegold")
    mirror_x(c, vn, vg, vr)
    # 金の襟（首の両脇に立つ V の板）と肩の付け根、喉の宝玉
    col = rbox(c, (-1.55, 26.0, 0.2), (1.35, 0.95, 3.3), "plate", rot=(0, 0, -26))
    colt = stick(c, col, "up", 0.5, 0.5, (0.95, 3.0, 0.18), "plate2", sink=0.05)
    cf = rbox(c, (-0.95, 26.1, -2.35), (1.5, 0.7, 0.38), "plate2", rot=(-18, 30, -12))
    yk = rbox(c, (-3.7, 26.0, 0.0), (1.9, 0.5, 3.6), "plate_b", rot=(0, 0, -9))    # 肩の付け根
    mirror_x(c, col, colt, cf, yk)
    rbox(c, (0, 25.55, -2.85), (0.5, 0.5, 0.24), "gem_accent", rot=(-10, 0, 45))
    # 脇の排気口（クリームの板に硫黄色のスリット）
    sv = cbox(c, (-4.28, 23.6, 0.55), (0.36, 1.7, 1.9), "plate2")
    svv = vents(c, sv, "west", 2, box=(0.24, 0.25, 0.76, 0.75))
    mirror_x(c, sv, svv)
    # 星核: 黒い菱形の台 → 金の八芒星の枠 → 金の八角 → 金星の雲の渦 → 回る輪（金と光）
    X, Y, Z = CORE_C
    diamond(c, (X, Y, Z + 0.42), 2.1, 0.4, "dark")
    star8(c, (X, Y, Z + 0.18), 2.2, 1.5, 0.4, 0.3, "gold", "rosegold")
    octa(c, (X, Y, Z), 1.5, 0.3, "gold", axis="z")
    cbox(c, (X, Y, Z - 0.22), (1.0, 1.0, 0.5), "core")
    sp = s.fx("spin", "core", c, pivot=(X, Y, Z - 0.42))
    ring(sp, (X, Y, Z - 0.42), 0.98, 8, (0, 0.2, 0.2), "gold", axis="z",
         styles=["gold", "glow"])
    # 下胸帯（金）
    chamfer(c, (0, 20.85, 0.12), (5.9, 0.42, 4.2), "gold", cut=0.5, axis="y")
    # コルセット: 三段のクリームの板（下ほど細い）・金の芯・金の骨・山形の金具。脇の油圧シリンダーは見せる
    ab = s.part("torso", "corset", "body", pivot=(0, A.WAIST_Y, 0))
    for i, (y, ww) in enumerate(((19.95, 3.3), (18.9, 3.0), (17.88, 2.75))):
        rbox(ab, (0, y, -1.86 + i * 0.03), (ww, 0.95, 0.4), "petal_cream", rot=(-5, 0, 0))
        cv = rbox(ab, (-0.58, y - 0.05, -2.1 + i * 0.03), (0.98, 0.2, 0.16), "gold",
                  rot=(-5, 0, 24))
        mirror_x(ab, cv)
    busk = cbox(ab, (0, 18.9, -2.12), (0.44, 3.2, 0.34), "gold")
    stick(ab, busk, "north", 0.5, 0.5, (0.18, 2.7, 0.16), "glow", sink=0.05)
    bn = beam(ab, (-1.45, 20.3, -2.1), (-1.15, 17.5, -2.06), 0.18, 0.18, "gold")
    mirror_x(ab, bn)
    # 背のコルセット: 背骨の両脇の板と、交差する金の紐
    bp = rbox(ab, (-0.95, 18.7, 2.25), (0.75, 3.2, 0.36), "plate_b", rot=(4, 0, 6))
    mirror_x(ab, bp)
    for y in (19.75, 18.75, 17.75):
        beam(ab, (-0.4, y + 0.28, 2.98), (0.4, y - 0.28, 2.98), 0.16, 0.16, "gold")
        beam(ab, (0.4, y + 0.28, 3.03), (-0.4, y - 0.28, 3.03), 0.16, 0.16, "gold")


# ---------------------------------------------------------------------------
#  背中（丸い背嚢・排気スリット・四芒星の紋・ホース・双発スラスター・羽根の排気フィン）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    pk = bevel(bk, (0, 22.5, 3.35), (3.7, 4.4, 1.7), "cloud", cut=0.55, axis="z")
    rbox(bk, (0, 24.9, 3.1), (3.3, 0.6, 1.7), "plate", rot=(22, 0, 0))              # 上の蓋
    rbox(bk, (0, 20.15, 3.1), (3.0, 0.55, 1.5), "plate", rot=(-18, 0, 0))           # 下の蓋
    vents(bk, pk[0], "south", 4, box=(0.32, 0.12, 0.68, 0.42))
    rivets(bk, pk[0], "south", 4, edge="border", margin=0.22, size=0.2, style="gold")
    # 金の四芒星の紋（薔薇色の宝玉）
    SZ = 4.28
    cbox(bk, (0, 23.45, SZ), (0.3, 2.2, 0.16), "gold")
    cbox(bk, (0, 23.45, SZ), (2.0, 0.3, 0.16), "gold")
    rbox(bk, (0, 23.45, SZ + 0.08), (0.5, 0.5, 0.18), "gem_accent", rot=(0, 0, 45))
    sensor(bk, (0, 24.55, 4.0), 0.24, "glow", "dark", facing=1)
    # 金の側板（縦の帯）とホース
    sd = cbox(bk, (-1.92, 22.5, 3.3), (0.3, 3.8, 1.3), "gold")
    hs = cable(bk, [(-1.4, 20.3, 3.3), (-2.85, 17.3, 1.7)], 0.26, "dark", sag=0.3,
               rib="gold", rib_every=2)
    mirror_x(bk, sd, hs)
    # スラスター（右。下後ろ・少し外へ）: 金の胴・帯・広がったベル・光る縁・噴射口・炎
    th = s.part("back", "thruster_r", bk, pivot=(-1.15, 20.6, 3.9), rotation=(18, 0, -8))
    octa(th, (-1.15, 19.85, 3.9), 1.3, 1.5, "plate", axis="y")
    octa(th, (-1.15, 18.75, 3.9), 1.75, 0.8, "gold", axis="y")
    ring(th, (-1.15, 18.33, 3.9), 0.72, 8, (0, 0.2, 0.2), "glow", axis="y")
    cbox(th, (-1.15, 18.32, 3.9), (1.2, 0.16, 1.2), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.15, 18.28, 3.9))
    taper(fx, (-1.15, 18.28, 3.9), (-1.15, 12.8, 3.9), 1.35, 0.3, 3, "flame")
    taper(fx, (-1.15, 18.24, 3.9), (-1.15, 15.4, 3.9), 0.65, 0.2, 2, "flame_core", round_=False)
    # 羽根の排気フィン（右に 3 枚。背嚢の肩から上外・後ろへ扇に開く。根元が広く先が細い。飾り）
    wg = s.part("back", "wing_r", bk, pivot=(-1.75, 23.9, 4.0), ornament=True)
    root = (-1.75, 23.9, 4.1)
    octa(wg, root, 1.1, 0.7, "gold", axis="x")
    rbox(wg, (root[0] - 0.4, root[1], root[2]), (0.24, 0.5, 0.5), "gem_accent", rot=(45, 0, 0))
    for tip, h, st_ in (((-4.5, 28.6, 6.0), 1.7, "plate2"), ((-5.7, 26.6, 6.4), 1.5, "cloud"),
                        ((-5.9, 24.2, 6.0), 1.25, "plate2")):
        feather(wg, root, tip, h, st_)


def feather(bone, root, tip, h, style):
    """羽根の排気フィン 1 枚: 二段の羽根（根元が広く先が細い）、金の羽軸、硫黄色の排気スリット。"""
    r = [root[i] + (tip[i] - root[i]) * 0.08 for i in range(3)]
    mid = [r[i] + (tip[i] - r[i]) * 0.55 for i in range(3)]
    vane = polyline(bone, [r, mid, tip], [0.24, 0.2], [h, h * 0.55], style)
    beam(bone, r, tip, 0.3, 0.26, "gold", extend=0.1)                               # 羽軸
    for f in (0.36,):
        p0 = [r[i] + (tip[i] - r[i]) * f for i in range(3)]
        p1 = [r[i] + (tip[i] - r[i]) * (f + 0.14) for i in range(3)]
        beam(bone, p0, p1, 0.32, h * (0.62 - f * 0.5), "vent")
    return vane


# ---------------------------------------------------------------------------
#  腕（二の腕の金の板と腕輪・長手袋の履き口・肘当て・花弁のように開く篭手）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.2, 21.4, 0.0), (0.36, 2.6, 1.8), "plate", rot=(0, 0, 3))
    stick(ua, op, "west", 0.5, 0.5, (1.2, 2.0, 0.16), "plate2", sink=0.05)
    line_on(ua, op, "west", (0.5, 0.15), (0.5, 0.85), 0.18, 0.18, "glow", lift=0.14)
    sensor(ua, (X + 0.05, 22.0, -1.12), 0.2, "glow", "dark")
    for y in (22.75, 20.45):                                                         # 腕輪
        octa(ua, (X, y, 0.05), 2.42, 0.3, "gold", axis="y")
    octa(ua, (X - 1.2, 22.75, 0.05), 0.72, 0.26, "gold", axis="x")
    rbox(ua, (X - 1.34, 22.75, 0.05), (0.18, 0.42, 0.42), "gem_accent", rot=(45, 0, 0))
    # 長手袋の履き口（クリーム + 金の線）
    gl = chamfer(ua, (X + 0.02, 19.72, 0.08), (2.5, 0.42, 2.55), "plate2", cut=0.4, axis="y")
    stick(ua, gl[0], "north", 0.5, 0.5, (1.6, 0.18, 0.16), "gold", sink=0.04)
    # 肘当て（後ろ。金の尖った板）
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    cop = bevel(el, (A.ELBOW[0], 18.55, 1.62), (1.6, 1.4, 0.46), "plate", cut=0.28, axis="z")
    diamond(el, (A.ELBOW[0], 17.78, 1.6), 0.78, 0.4, "plate")
    rivets(el, cop[0], "south", 2, edge="top", margin=0.25, span=(0.3, 0.7), size=0.2,
           style="rosegold")
    # 篭手: クリームの長手袋（手首へ少し開く二段）+ 外の金の板（宝玉・発光線）+ 花弁の袖口三枚 + 金の帯
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX_ = A.FOREARM_X
    chamfer(fa, (FX_, 17.35, 0.0), (2.2, 1.3, 2.25), "plate2", cut=0.4, axis="y")
    vb = chamfer(fa, (FX_, 16.0, 0.0), (2.4, 1.5, 2.45), "plate2", cut=0.42, axis="y")
    octa(fa, (FX_, 17.95, 0.0), 2.4, 0.26, "gold", axis="y")
    octa(fa, (FX_, 16.72, 0.0), 2.46, 0.26, "rosegold", axis="y")
    ob = rbox(fa, (FX_ - 1.25, 16.3, 0.0), (0.32, 1.9, 1.4), "plate", rot=(0, 0, 4))
    octa(fa, (FX_ - 1.42, 16.6, 0.0), 0.8, 0.26, "gold", axis="x")
    rbox(fa, (FX_ - 1.54, 16.6, 0.0), (0.18, 0.44, 0.44), "gem_accent", rot=(45, 0, 0))
    line_on(fa, ob, "west", (0.5, 0.06), (0.5, 0.38), 0.16, 0.16, "glow")
    line_on(fa, vb[0], "north", (0.5, 0.12), (0.5, 0.88), 0.18, 0.16, "gold")
    sensor(fa, (FX_ + 0.05, 16.9, 1.18), 0.2, "glow", "dark", facing=1)
    for cc, sz, rot_ in (((FX_ - 1.3, 15.0, 0.0), (0.28, 1.0, 1.9), (0, 0, 16)),      # 外
                         ((FX_, 15.0, -1.32), (1.9, 1.0, 0.28), (-16, 0, 0)),         # 前
                         ((FX_, 15.0, 1.32), (1.9, 1.0, 0.28), (16, 0, 0))):          # 後ろ
        cf = rbox(fa, cc, sz, "petal_cream", rot=rot_)
        face = "west" if sz[0] < 1 else ("north" if rot_[0] < 0 else "south")
        stick(fa, cf, face, 0.5, 0.12, ((sz[2] if sz[0] < 1 else sz[0]) - 0.1, 0.2, 0.15),
              "gold", sink=0.04)


def hands(s):
    """手の甲の金の板と宝玉、指の甲当て（4 本の基節・金）、親指の当て。指そのものは frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.4, 13.62, 0.0), (0.34, 1.65, 2.2), "plate", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.55, (0.55, 0.55, 0.18), "gem_accent", spin=45, sink=0.04)
    stick(h, hb, "west", 0.5, 0.06, (2.0, 0.2, 0.15), "rosegold", sink=0.04)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        n = (-0.81, -0.58, 0.0)
        o = 0.32
        beam(h, (p0[0] + n[0] * o, p0[1] + n[1] * o, zf), (p1[0] + n[0] * o, p1[1] + n[1] * o, zf),
             0.5, 0.2, "plate")
    rbox(h, (-5.62, 13.55, -1.72), (0.58, 0.85, 0.2), "plate", rot=(0, 0, -36))


# ---------------------------------------------------------------------------
#  肩（金の肩当て + 雲のポッド: クリームの雲の玉、外の排気口と回るファン、金の輪、下のスリット）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pod_r", "rightArm")
    cap = chamfer(p, (-6.85, 25.3, 0.0), (3.0, 1.4, 3.6), "plate", cut=0.5, axis="x",
                  rot=(0, 0, -16))
    stick(p, cap[0], "up", 0.5, 0.5, (0.3, 3.3, 0.16), "rosegold", sink=0.05)
    rivets(p, cap[0], "up", 2, edge="right", margin=0.3, span=(0.2, 0.8), size=0.2,
           style="rosegold")
    # 雲の玉: 大きな本体 + 上前・上後ろの小さな玉（輪郭線なしで一つの雲に溶ける）
    C = (-8.05, 24.45, 0.0)
    puff(p, C, 1.42, "cloud")
    puff(p, (-7.55, 25.55, -1.05), 0.92, "cloud")
    puff(p, (-7.6, 25.6, 1.1), 0.98, "cloud")
    # 雲を抱く金の輪（縦の半円）と前の薔薇色の宝玉
    ring(p, C, 1.5, 4, (0, 0.24, 0.34), "gold", axis="x", a0=-90, a1=90,
         styles=["gold", "rosegold"])
    rbox(p, (-8.05, 24.45, -1.62), (0.5, 0.5, 0.24), "gem_accent", rot=(0, 0, 45))
    # 外の排気口: 金の縁 → 硫黄色の口 → 中で回るファン（4 枚羽根と宝玉の軸）
    VX = -9.42
    octa(p, (VX, C[1], C[2]), 1.85, 0.3, "gold", axis="x")
    octa(p, (VX - 0.08, C[1], C[2]), 1.42, 0.26, "vent", axis="x")
    fn = s.fx("spin", "fan_r", p, pivot=(VX - 0.24, C[1], C[2]))
    for a in (0, 45, 90, 135):
        rbox(fn, (VX - 0.24, C[1], C[2]), (0.16, 1.0, 0.26), "frame_lt", rot=(a, 0, 0))
    cbox(fn, (VX - 0.3, C[1], C[2]), (0.2, 0.38, 0.38), "gem")


# ---------------------------------------------------------------------------
#  兜（小さな金の冠・磁器の面・ティアラと八芒星・耳・こめかみの唐草・後ろへ流れる髪）とバイザー
# ---------------------------------------------------------------------------
def helmet(s):
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.98, HZ + 0.3), (4.4, 1.85, 4.65), "helm", cut=0.6, axis="z")
    chamfer(hm, (0, 31.72, HZ + 0.45), (3.3, 0.55, 3.9), "helm", cut=0.45, axis="y")
    cbox(hm, (0, 31.95, HZ + 0.5), (0.6, 0.3, 3.6), "plate2")                       # 頂の稜
    rbox(hm, (0, 30.35, HZ - 2.15), (3.9, 1.0, 0.42), "helm", rot=(-20, 0, 0))      # 額の斜面
    # 後頭部（金の板・排気スリット・しころ）
    bh = cbox(hm, (0, 29.45, HZ + 2.52), (3.5, 2.3, 0.4), "helm")
    vents(hm, bh, "south", 3, box=(0.36, 0.25, 0.64, 0.65), w=0.16)
    rbox(hm, (0, 28.2, HZ + 2.5), (3.1, 0.7, 0.4), "plate_b", rot=(24, 0, 0))
    # こめかみ（クリーム + 金の縁）・耳（金の円盤 + 光）・頬当て
    sd = cbox(hm, (-2.08, 29.15, HZ + 0.65), (0.4, 2.4, 3.3), "plate2")
    sdt = stick(hm, sd, "west", 0.5, 0.95, (3.1, 0.2, 0.15), "gold", sink=0.04)
    ear = octa(hm, (-2.32, 29.2, HZ + 0.6), 1.0, 0.28, "gold", axis="x")
    eg = cbox(hm, (-2.5, 29.2, HZ + 0.6), (0.16, 0.42, 0.42), "glow")
    ck = rbox(hm, (-1.7, 28.35, HZ - 1.2), (0.4, 1.8, 1.9), "plate2", rot=(0, 22, -8))
    ckg = stick(hm, ck, "west", 0.08, 0.5, (0.2, 1.6, 0.15), "gold", sink=0.04)
    # こめかみから後ろ上へ流れる薔薇金の唐草
    v1 = polyline(hm, [(-2.36, 29.95, HZ + 0.5), (-2.2, 30.75, HZ + 1.45), (-1.75, 31.35, HZ + 2.3)],
                  [0.24, 0.2], [0.26, 0.22], "rosegold")
    mirror_x(hm, sd, sdt, ear, eg, ck, ckg, v1)
    # 磁器の面: 額から顎までの一枚の白い面・後ろへ回る頬・顎・鼻筋・薔薇色の唇
    rbox(hm, (0, 28.85, HZ - 2.2), (2.5, 2.6, 0.36), "face", rot=(4, 0, 0))
    fs = rbox(hm, (-1.32, 28.75, HZ - 1.82), (0.42, 2.3, 1.05), "face", rot=(0, 32, -4))
    mirror_x(hm, fs)
    rbox(hm, (0, 27.62, HZ - 2.0), (1.3, 0.5, 0.5), "face", rot=(-24, 0, 0))       # 顎
    cbox(hm, (0, 28.68, HZ - 2.46), (0.24, 0.8, 0.2), "face")                      # 鼻筋
    cbox(hm, (0, 28.02, HZ - 2.42), (0.52, 0.16, 0.16), "glow_accent")             # 唇
    # ティアラ: こめかみから中央へ上る金の帯（V の頂に八芒星）
    tl = rbox(hm, (-1.12, 30.42, HZ - 2.42), (2.3, 0.34, 0.3), "gold", rot=(-14, 18, -18))
    tg = stick(hm, tl, "north", 0.5, 0.5, (1.9, 0.16, 0.15), "glow_accent", sink=0.04)
    mirror_x(hm, tl, tg)
    # 額の八芒星（金の台 + 光条。ゆっくり脈打つ）
    SY, SZ = 30.95, HZ - 2.62
    diamond(hm, (0, SY, SZ + 0.12), 1.2, 0.3, "gold")
    st = s.fx("glow", "star", hm, pivot=(0, SY, SZ - 0.1))
    star8(st, (0, SY, SZ - 0.1), 1.25, 0.82, 0.3, 0.2, "star")
    rbox(st, (0, SY, SZ - 0.26), (0.46, 0.46, 0.2), "gem_accent", rot=(0, 0, 45))
    # 冠の尖塔（ティアラから立ち上がる薔薇金の細い塔。中央の星を囲む。飾り）
    cr = s.part("helmet", "crest", "head", pivot=(0, SY, SZ), ornament=True)
    sp1 = taper(cr, (-0.7, 31.3, SZ + 0.12), (-1.45, 32.75, SZ + 0.2), 0.3, 0.18, 1,
                "rosegold", round_=False)
    mirror_x(cr, sp1)
    taper(cr, (0, 32.0, SZ + 0.2), (0, 33.6, SZ + 0.25), 0.34, 0.18, 1, "gold", round_=False)
    rbox(cr, (0, 33.72, SZ + 0.25), (0.36, 0.36, 0.2), "star", rot=(0, 0, 45))
    # 後ろへ流れる金の髪の刃（5 本。冠の後ろから首の後ろへ、下ほど後ろ・外へ流れる。飾り）
    pl = s.part("helmet", "plume", "head", pivot=(0, 31.6, HZ + 2.2), ornament=True)
    for x, dx, top, ln, w, st_ in ((0.0, 0.0, 31.75, 5.8, 0.8, "petal_gold"),
                                   (-1.0, -0.7, 31.5, 5.1, 0.7, "plate_b"),
                                   (-1.85, -1.35, 31.0, 4.2, 0.6, "petal_gold")):
        pts = [(x, top, HZ + 1.9), (x + dx * 0.4, top - ln * 0.32, HZ + 3.05),
               (x + dx * 0.8, top - ln * 0.7, HZ + 3.55), (x + dx, top - ln, HZ + 3.45)]
        bl = polyline(pl, pts, [w, w * 0.82, w * 0.55], [0.34, 0.3, 0.26], st_)
        lk = line_on(pl, bl[1], "up", (0.5, 0.1), (0.5, 0.9), 0.16, 0.16,
                     "glow_soft" if x == 0 else "rosegold")
        if x:
            mirror_x(pl, bl, lk)
    # バイザー: 磁器の面に切れ込んだ切れ長の目（外の端が上がる）と金のまぶた
    vz = s.part("visor", "eye", "head")
    sock = rbox(vz, (-0.66, 29.42, HZ - 2.4), (1.05, 0.36, 0.16), "dark", rot=(4, 6, 9))
    lid = rbox(vz, (-0.68, 29.7, HZ - 2.43), (1.15, 0.16, 0.16), "gold", rot=(4, 6, 12))
    mirror_x(vz, sock, lid)
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.42, HZ - 2.5))
    eye = rbox(fg, (-0.66, 29.42, HZ - 2.46), (0.88, 0.2, 0.16), "visor", rot=(4, 6, 9))
    mirror_x(fg, eye)


# ---------------------------------------------------------------------------
#  光輪（頭の後ろで回る八芒の輪。金と光の輪 + 八本の光条 + 内の薔薇金の輪）
# ---------------------------------------------------------------------------
def halo(s):
    C = HALO_C
    h = s.part("extra", "halo", "head", pivot=C)
    sp = s.fx("spin", "halo", h, pivot=C)
    R = 3.05
    ring(sp, C, R, 12, (0, 0.26, 0.28), "gold", axis="z", styles=["gold", "glow"])
    for k in range(8):
        a = math.radians(k * 45)
        L = 4.3 if k % 2 == 0 else 3.75
        p0 = (C[0] - (R + 0.1) * math.sin(a), C[1] + (R + 0.1) * math.cos(a), C[2])
        p1 = (C[0] - L * math.sin(a), C[1] + L * math.cos(a), C[2])
        taper(sp, p0, p1, 0.42 if k % 2 == 0 else 0.34, 0.2, 1,
              "star" if k % 2 == 0 else "gold", round_=False)
